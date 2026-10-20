"""OAuth authorization-code flows and database-backed browser sessions."""
import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AuthAccount, User, UserSession

router = APIRouter(prefix='/api/auth')
SESSION_COOKIE = 'relationship_session'
STATE_COOKIE = 'relationship_oauth_state'
SESSION_SECONDS = 30 * 24 * 60 * 60
PROVIDERS = {
    'google': ('https://accounts.google.com/o/oauth2/v2/auth', 'https://oauth2.googleapis.com/token', 'https://www.googleapis.com/oauth2/v3/certs', ['https://accounts.google.com', 'accounts.google.com']),
    'apple': ('https://appleid.apple.com/auth/authorize', 'https://appleid.apple.com/auth/token', 'https://appleid.apple.com/auth/keys', ['https://appleid.apple.com']),
}


def token_hash(token: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(token.encode()).digest()).decode().rstrip('=')


def provider_config(provider: str):
    if provider not in PROVIDERS:
        raise HTTPException(404, 'Unsupported provider')
    settings = get_settings()
    client_id = getattr(settings, f'{provider}_client_id')
    callback = getattr(settings, f'{provider}_callback_url')
    required = ('google_client_secret',) if provider == 'google' else ('apple_team_id', 'apple_key_id', 'apple_private_key')
    if not client_id or not callback or any(not getattr(settings, key) for key in required):
        raise HTTPException(503, 'Sign-in provider is not configured')
    if provider == 'apple' and not callback.startswith('https://'):
        raise HTTPException(503, 'Apple sign-in requires HTTPS')
    return settings, client_id, callback


def fail():
    response = RedirectResponse(get_settings().frontend_url.rstrip('/') + '/?auth_error=signin_failed', status_code=303)
    response.delete_cookie(STATE_COOKIE, path='/api/auth')
    response.headers['Cache-Control'] = 'no-store'
    return response


@router.get('/{provider}/start')
def start(provider: str):
    settings, client_id, callback = provider_config(provider)
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    payload = {'state': state, 'nonce': nonce, 'verifier': verifier, 'provider': provider,
               'exp': datetime.now(timezone.utc) + timedelta(minutes=10)}
    params = dict(client_id=client_id, redirect_uri=callback, response_type='code',
                  scope='openid email profile' if provider == 'google' else 'name email', state=state, nonce=nonce)
    if provider == 'google':
        params.update(code_challenge=token_hash(verifier), code_challenge_method='S256', prompt='select_account')
    else:
        params['response_mode'] = 'form_post'
    response = RedirectResponse(PROVIDERS[provider][0] + '?' + urlencode(params), status_code=302)
    response.set_cookie(STATE_COOKIE, jwt.encode(payload, settings.session_secret, algorithm='HS256'),
                        max_age=600, httponly=True, secure=callback.startswith('https://'),
                        samesite='none' if provider == 'apple' else 'lax', path='/api/auth')
    response.headers['Cache-Control'] = 'no-store'
    return response


@lru_cache
def key_client(provider: str):
    return jwt.PyJWKClient(PROVIDERS[provider][2], timeout=10)


def verify_identity(provider: str, token: str, client_id: str, nonce: str):
    key = key_client(provider).get_signing_key_from_jwt(token).key
    claims = jwt.decode(token, key, algorithms=['RS256'], audience=client_id,
                        issuer=PROVIDERS[provider][3], options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'nonce']})
    if not isinstance(claims['sub'], str) or not claims['sub'] or not secrets.compare_digest(str(claims['nonce']), nonce):
        raise ValueError('Invalid identity')
    return claims


def client_secret(provider: str, settings, client_id: str):
    if provider == 'google':
        return settings.google_client_secret
    now = datetime.now(timezone.utc)
    return jwt.encode({'iss': settings.apple_team_id, 'sub': client_id, 'aud': 'https://appleid.apple.com',
                       'iat': now, 'exp': now + timedelta(minutes=5)},
                      settings.apple_private_key.replace('\\n', '\n'), algorithm='ES256',
                      headers={'kid': settings.apple_key_id})


def save_session(db: Session, provider: str, claims: dict, name: str | None, old_token: str | None):
    account = db.scalar(select(AuthAccount).where(AuthAccount.provider == provider, AuthAccount.provider_subject == claims['sub']))
    email = claims.get('email')
    verified = claims.get('email_verified') in (True, 'true')
    if account:
        user = db.get(User, account.user_id)
    else:
        if not isinstance(email, str) or not email or not verified:
            raise ValueError('A verified email is required')
        # Never link independent provider identities just because email addresses match.
        if db.scalar(select(User.id).where(User.email == email)):
            raise ValueError('Sign in with the previously linked provider')
        user = User(email=email, display_name=name, avatar_url=claims.get('picture') if provider == 'google' else None)
        db.add(user)
        db.flush()
        db.add(AuthAccount(user_id=user.id, provider=provider, provider_subject=claims['sub'], email=email))
    if name:
        user.display_name = name
    if old_token:
        db.execute(delete(UserSession).where(UserSession.token_hash == token_hash(old_token)))
    token = secrets.token_urlsafe(32)
    db.add(UserSession(user_id=user.id, token_hash=token_hash(token), expires_at=datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)))
    db.commit()
    return token


def callback(provider: str, request: Request, code: str | None, state: str | None, submitted_user: str | None, db: Session):
    try:
        settings, client_id, callback_url = provider_config(provider)
        stored = jwt.decode(request.cookies.get(STATE_COOKIE, ''), settings.session_secret, algorithms=['HS256'],
                            options={'require': ['exp', 'state', 'nonce', 'verifier', 'provider']})
        if not code or not state or stored['provider'] != provider or not secrets.compare_digest(stored['state'], state):
            return fail()
        data = dict(client_id=client_id, client_secret=client_secret(provider, settings, client_id),
                    code=code, grant_type='authorization_code', redirect_uri=callback_url)
        if provider == 'google':
            data['code_verifier'] = stored['verifier']
        response = httpx.post(PROVIDERS[provider][1], data=data, timeout=15)
        response.raise_for_status()
        claims = verify_identity(provider, response.json()['id_token'], client_id, stored['nonce'])
        name = claims.get('name') if provider == 'google' else None
        if provider == 'apple' and submitted_user:
            try:
                parts = json.loads(submitted_user).get('name', {})
                name = ' '.join(str(parts.get(k, '')) for k in ('firstName', 'lastName')).strip() or None
            except (ValueError, AttributeError, TypeError):
                pass
        token = save_session(db, provider, claims, name, request.cookies.get(SESSION_COOKIE))
        result = RedirectResponse(settings.frontend_url, status_code=303)
        result.set_cookie(SESSION_COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                          secure=callback_url.startswith('https://'), samesite='lax', path='/')
        result.delete_cookie(STATE_COOKIE, path='/api/auth')
        result.headers['Cache-Control'] = 'no-store'
        return result
    except (jwt.PyJWTError, httpx.HTTPError, ValueError, KeyError, HTTPException):
        db.rollback()
        return fail()


@router.get('/google/callback')
def google_callback(request: Request, code: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    return callback('google', request, code, state, None, db)


@router.post('/apple/callback')
def apple_callback(request: Request, code: str | None = Form(None), state: str | None = Form(None),
                   user: str | None = Form(None), db: Session = Depends(get_db)):
    return callback('apple', request, code, state, user, db)


@router.get('/me')
def me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    user_data = None
    if token:
        row = db.execute(select(User, AuthAccount.provider).join(UserSession, UserSession.user_id == User.id)
                         .join(AuthAccount, AuthAccount.user_id == User.id)
                         .where(UserSession.token_hash == token_hash(token), UserSession.expires_at > datetime.now(timezone.utc))).first()
        if row:
            user, provider = row
            user_data = dict(id=str(user.id), provider=provider, email=user.email, name=user.display_name, pictureUrl=user.avatar_url)
    return JSONResponse({'user': user_data}, headers={'Cache-Control': 'no-store'})


@router.post('/logout')
def logout(request: Request, db: Session = Depends(get_db)):
    # Same-origin proxy keeps cookies first-party. Require an explicit browser Origin.
    if request.headers.get('origin') != get_settings().frontend_url.rstrip('/'):
        raise HTTPException(403, 'Invalid origin')
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == token_hash(token)))
        db.commit()
    response = JSONResponse({'ok': True}, headers={'Cache-Control': 'no-store'})
    response.delete_cookie(SESSION_COOKIE, path='/')
    response.delete_cookie(STATE_COOKIE, path='/api/auth')
    return response
