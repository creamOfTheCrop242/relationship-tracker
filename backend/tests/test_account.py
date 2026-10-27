import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.auth import SESSION_COOKIE, token_hash
from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.main import app
from backend.app.models import (AuthAccount, Event, NeedUpdate, Relationship,
                                RelationshipNeed, RelationshipSummary, User,
                                UserSession)
from test_database import DatabaseTestCase


class AccountPrivacyTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.other = self.user(), self.user()
        self.tokens = [str(uuid4()), str(uuid4())]
        for index, (user, token) in enumerate(zip((self.owner, self.other), self.tokens)):
            self.session.add_all([
                UserSession(user_id=user.id, token_hash=token_hash(token),
                            expires_at=datetime.now(timezone.utc) + timedelta(days=1)),
                AuthAccount(user_id=user.id, provider='google', provider_subject=f'subject-{index}',
                            email=user.email),
            ])
        self.session.flush()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app, headers={'Origin': get_settings().frontend_url.rstrip('/')})
        self.client.cookies.set(SESSION_COOKIE, self.tokens[0])

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        super().tearDown()

    def add_relationship_data(self):
        event = self.client.post('/api/events', json={
            'category': 'kindness', 'description': 'Made breakfast',
            'occurred_at': '2026-10-01T12:00:00Z', 'notes': 'A quiet morning', 'details': {},
        })
        self.assertEqual(event.status_code, 201, event.text)
        need = self.client.post('/api/needs', json={
            'person': 'me', 'name': 'Quality time', 'importance': 'high',
            'desired_amount': 2, 'desired_period': 'per_week', 'custom_period_days': None,
            'confirmed_by_partner': 'unknown', 'active': True,
        })
        self.assertEqual(need.status_code, 201, need.text)
        update = self.client.post(f"/api/needs/{need.json()['id']}/updates", json={
            'occurred_on': '2026-10-02', 'status': 'met', 'what_happened': 'Went for a walk',
            'satisfaction': 5,
        })
        self.assertEqual(update.status_code, 201, update.text)
        relationship = self.session.scalar(select(Relationship).where(Relationship.owner_id == self.owner.id))
        self.session.add(RelationshipSummary(
            relationship_id=relationship.id, period_type='daily',
            period_start=date(2026, 10, 1), period_end=date(2026, 10, 2),
            score=80, confidence='medium', coverage_days=1, total_days=1,
            events_analyzed=1, need_updates_analyzed=0, data_summary='One event.',
            positive_factors=['Kindness'], friction_factors=[], interpretation='A kind moment was recorded.',
            comparison='No comparison.', unresolved_issues=[], suggested_actions=[],
            reflection='Notice the kind moment.', limitations='Limited data.', model='test-model',
            response_id='response-1',
        ))
        self.session.flush()

    def test_export_contains_owned_data_and_excludes_sessions(self):
        self.add_relationship_data()
        response = self.client.get('/api/account/export')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertIn('attachment;', response.headers['content-disposition'])
        data = response.json()
        self.assertEqual(data['export_version'], 1)
        self.assertEqual(data['account']['email'], self.owner.email)
        self.assertEqual([row['provider_subject'] for row in data['account']['connected_providers']], ['subject-0'])
        self.assertEqual(data['relationship']['events'][0]['description'], 'Made breakfast')
        self.assertEqual(data['relationship']['needs'][0]['updates'][0]['what_happened'], 'Went for a walk')
        self.assertEqual(data['relationship']['reflections'][0]['score'], 80)
        self.assertNotIn('token_hash', json.dumps(data))
        self.client.cookies.set(SESSION_COOKIE, self.tokens[1])
        other = self.client.get('/api/account/export').json()
        self.assertEqual(other['account']['email'], self.other.email)
        self.assertIsNone(other['relationship'])

    def test_delete_requires_confirmation_origin_and_removes_only_current_user(self):
        self.add_relationship_data()
        self.assertEqual(self.client.request('DELETE', '/api/account', json={'confirmation': 'delete'}).status_code, 422)
        self.assertEqual(self.client.request('DELETE', '/api/account', json={'confirmation': 'DELETE'},
                                             headers={'Origin': 'https://evil.test'}).status_code, 403)
        response = self.client.request('DELETE', '/api/account', json={'confirmation': 'DELETE'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'ok': True})
        self.assertIsNone(self.session.get(User, self.owner.id))
        self.assertIsNotNone(self.session.get(User, self.other.id))
        for model in (AuthAccount, UserSession, Relationship, Event, RelationshipNeed,
                      NeedUpdate, RelationshipSummary):
            self.assertEqual(self.session.scalar(select(func.count()).select_from(model)),
                             1 if model in (AuthAccount, UserSession) else 0)
        self.assertIsNone(self.client.get('/api/auth/me').json()['user'])
