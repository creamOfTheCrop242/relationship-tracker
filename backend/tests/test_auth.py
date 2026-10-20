import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app import auth
from backend.app.config import Settings
from backend.app.db import get_db, get_engine
from backend.app.main import app
from backend.app.models import AuthAccount, User, UserSession
from test_database import DatabaseTestCase


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None, session_secret='test-secret-that-is-at-least-32-characters',
            frontend_url='https://journal.example', google_client_id='google-test', google_client_secret='secret',
            google_callback_url='https://journal.example/api/auth/google/callback',
            apple_client_id='apple-test', apple_team_id='team', apple_key_id='key', apple_private_key='key',
            apple_callback_url='https://journal.example/api/auth/apple/callback')
        self.patch = patch.object(auth, 'get_settings', return_value=self.settings)
        self.patch.start()
        self.db = Mock()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app, base_url='https://journal.example', follow_redirects=False)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.patch.stop()

    def begin(self, provider='google'):
        response = self.client.get(f'/api/auth/{provider}/start')
        self.assertEqual(response.status_code, 302)
        return parse_qs(urlsplit(response.headers['location']).query)

    def test_root_and_anonymous_session(self):
        self.assertEqual(self.client.get('/').json()['docs'], '/docs')
        self.assertEqual(self.client.get('/api/auth/me').json(), {'user': None})
        self.db.execute.assert_not_called()

    def test_google_state_pkce_and_secure_cookie(self):
        params = self.begin()
        cookie = self.client.cookies.get(auth.STATE_COOKIE)
        stored = jwt.decode(cookie, self.settings.session_secret, algorithms=['HS256'])
        self.assertEqual(params['code_challenge'], [auth.token_hash(stored['verifier'])])
        self.assertEqual(params['nonce'], [stored['nonce']])
        self.assertNotIn(stored['verifier'], params['state'])

    def test_apple_cookie_supports_cross_site_post(self):
        response = self.client.get('/api/auth/apple/start')
        cookie = response.headers['set-cookie']
        for flag in ('HttpOnly', 'Secure', 'SameSite=none'):
            self.assertIn(flag, cookie)

    def test_invalid_state_never_exchanges_code(self):
        self.begin()
        with patch.object(auth.httpx, 'post') as exchange:
            result = self.client.get('/api/auth/google/callback?code=code&state=wrong')
        exchange.assert_not_called()
        self.assertIn('auth_error', result.headers['location'])

    def test_expired_state_and_provider_mixup_rejected(self):
        params = self.begin()
        with patch.object(auth.httpx, 'post') as exchange:
            self.client.post('/api/auth/apple/callback', data={'code': 'code', 'state': params['state'][0]})
        exchange.assert_not_called()
        expired = jwt.encode({'exp': 1, 'state': 's', 'provider': 'google', 'nonce': 'n', 'verifier': 'v'}, self.settings.session_secret, algorithm='HS256')
        self.client.cookies.set(auth.STATE_COOKIE, expired)
        with patch.object(auth.httpx, 'post') as exchange:
            self.client.get('/api/auth/google/callback?code=code&state=s')
        exchange.assert_not_called()

    def test_valid_callback_sets_session_and_clears_state(self):
        params = self.begin()
        response = Mock()
        response.json.return_value = {'id_token': 'signed-token'}
        with patch.object(auth.httpx, 'post', return_value=response), patch.object(auth, 'verify_identity', return_value={'sub': 's', 'name': 'Person'}), patch.object(auth, 'save_session', return_value='opaque-token'):
            result = self.client.get('/api/auth/google/callback', params={'state': params['state'][0], 'code': 'code'})
        self.assertEqual(result.headers['location'], self.settings.frontend_url)
        self.assertIn('relationship_session=opaque-token', result.headers['set-cookie'])
        self.assertIsNone(self.client.cookies.get(auth.STATE_COOKIE))

    def test_logout_requires_origin_and_revokes_token(self):
        self.client.cookies.set(auth.SESSION_COOKIE, 'token')
        self.assertEqual(self.client.post('/api/auth/logout', headers={'Origin': 'https://evil.example'}).status_code, 403)
        self.db.commit.assert_not_called()
        self.assertEqual(self.client.post('/api/auth/logout', headers={'Origin': self.settings.frontend_url}).status_code, 200)
        self.db.commit.assert_called_once()
        self.assertEqual(self.client.get('/api/auth/logout').status_code, 405)

    def test_identity_signature_audience_expiry_and_nonce(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        claims = {'sub': 's', 'iss': 'https://accounts.google.com', 'aud': 'google-test', 'nonce': 'n',
                  'iat': datetime.now(timezone.utc), 'exp': datetime.now(timezone.utc) + timedelta(minutes=5)}
        key_client = Mock()
        key_client.get_signing_key_from_jwt.return_value.key = private.public_key()
        with patch.object(auth, 'key_client', return_value=key_client):
            token = jwt.encode(claims, private, algorithm='RS256')
            self.assertEqual(auth.verify_identity('google', token, 'google-test', 'n')['sub'], 's')
            for change in ({'aud': 'wrong'}, {'iss': 'https://evil.example'}, {'exp': 1}, {'nonce': 'wrong'}):
                with self.assertRaises((jwt.PyJWTError, ValueError)):
                    auth.verify_identity('google', jwt.encode(claims | change, private, algorithm='RS256'), 'google-test', 'n')


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'Needs migrated test database')
class SessionTests(DatabaseTestCase):
    def test_session_roundtrip_and_expiry(self):
        claims = {'sub': 'subject', 'email': 'person@example.test', 'email_verified': True}
        token = auth.save_session(self.session, 'google', claims, 'Person', None)
        saved = self.session.scalar(select(UserSession))
        self.assertEqual(saved.token_hash, auth.token_hash(token))
        self.assertNotEqual(saved.token_hash, token)
        app.dependency_overrides[get_db] = lambda: self.session
        try:
            with TestClient(app) as client:
                client.cookies.set(auth.SESSION_COOKIE, token)
                self.assertEqual(client.get('/api/auth/me').json()['user']['email'], claims['email'])
                saved.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                self.session.flush()
                self.assertIsNone(client.get('/api/auth/me').json()['user'])
        finally:
            app.dependency_overrides.clear()

    def test_repeated_provider_identity_keeps_user_and_rotates_session(self):
        claims = {'sub': 'subject', 'email': 'person@example.test', 'email_verified': True}
        first = auth.save_session(self.session, 'apple', claims, 'Person', None)
        user_id = self.session.scalar(select(User.id))
        auth.save_session(self.session, 'apple', {'sub': 'subject'}, None, first)
        self.assertEqual(self.session.scalar(select(User.id)), user_id)
        self.assertEqual(len(self.session.scalars(select(UserSession)).all()), 1)
        self.assertEqual(self.session.scalar(select(User.display_name)), 'Person')

    def test_logout_invalidates_copied_session_cookie(self):
        claims = {'sub': 'subject', 'email': 'person@example.test', 'email_verified': True}
        token = auth.save_session(self.session, 'google', claims, 'Person', None)
        app.dependency_overrides[get_db] = lambda: self.session
        try:
            with TestClient(app) as client:
                client.cookies.set(auth.SESSION_COOKIE, token)
                origin = auth.get_settings().frontend_url.rstrip('/')
                self.assertEqual(client.post('/api/auth/logout', headers={'Origin': origin}).status_code, 200)
                client.cookies.set(auth.SESSION_COOKIE, token)
                self.assertIsNone(client.get('/api/auth/me').json()['user'])
        finally:
            app.dependency_overrides.clear()

    def test_unverified_email_and_implicit_link_rejected(self):
        with self.assertRaises(ValueError):
            auth.save_session(self.session, 'google', {'sub': 's', 'email': 'a@example.test', 'email_verified': False}, None, None)
        claims = {'sub': 's', 'email': 'a@example.test', 'email_verified': True}
        auth.save_session(self.session, 'google', claims, None, None)
        with self.assertRaises(ValueError):
            auth.save_session(self.session, 'apple', claims, None, None)
