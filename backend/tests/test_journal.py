from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.auth import SESSION_COOKIE, token_hash
from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.main import app
from backend.app.models import Event, Relationship, UserSession
from test_database import DatabaseTestCase


class JournalTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.other = self.user(), self.user()
        self.tokens = [str(uuid4()), str(uuid4())]
        for user, token in zip((self.owner, self.other), self.tokens):
            self.session.add(UserSession(user_id=user.id, token_hash=token_hash(token), expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        self.session.flush()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app, headers={'Origin': get_settings().frontend_url.rstrip('/')})
        self.client.cookies.set(SESSION_COOKIE, self.tokens[0])
        self.data = {'category': 'kindness', 'description': 'Made dinner together', 'occurred_at': '2026-10-01T19:30:00-04:00', 'notes': 'A quiet evening.'}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_create_reload_edit_delete(self):
        self.assertIsNone(self.client.get('/api/relationship').json())
        created = self.client.post('/api/events', json=self.data)
        self.assertEqual(created.status_code, 201, created.text)
        event_id = created.json()['id']
        self.assertEqual(self.client.get('/api/relationship').json()['partner_name'], 'Partner')
        self.session.expire_all()
        rows = self.client.get('/api/events')
        self.assertEqual(rows.headers['cache-control'], 'no-store')
        self.assertEqual(rows.json()[0]['description'], self.data['description'])
        self.assertEqual(datetime.fromisoformat(rows.json()[0]['occurred_at']), datetime.fromisoformat(self.data['occurred_at']))
        updated = self.client.put('/api/events/' + event_id, json=self.data | {'description': 'Updated', 'notes': None})
        self.assertEqual(updated.status_code, 200)
        self.assertIsNone(updated.json()['notes'])
        self.assertEqual(self.client.delete('/api/events/' + event_id).status_code, 204)
        self.assertEqual(self.client.get('/api/events').json(), [])
        self.assertEqual(self.client.delete('/api/events/' + event_id).status_code, 404)

    def test_other_user_cannot_list_edit_or_delete(self):
        event_id = self.client.post('/api/events', json=self.data).json()['id']
        self.client.put('/api/relationship', json={'partner_name': 'Alex'})
        self.client.cookies.set(SESSION_COOKIE, self.tokens[1])
        self.assertEqual(self.client.get('/api/events').json(), [])
        self.assertIsNone(self.client.get('/api/relationship').json())
        self.assertEqual(self.client.put('/api/events/' + event_id, json=self.data).status_code, 404)
        self.assertEqual(self.client.delete('/api/events/' + event_id).status_code, 404)
        self.client.put('/api/relationship', json={'partner_name': 'Sam'})
        self.client.cookies.set(SESSION_COOKIE, self.tokens[0])
        self.assertEqual(self.client.get('/api/relationship').json()['partner_name'], 'Alex')
        self.assertEqual(len(self.client.get('/api/events').json()), 1)

    def test_authentication_expiry_and_origin(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/events').status_code, 401)
        self.assertEqual(self.client.post('/api/events', json=self.data).status_code, 401)
        self.client.cookies.set(SESSION_COOKIE, self.tokens[0])
        self.assertEqual(self.client.post('/api/events', json=self.data, headers={'Origin': 'https://evil.test'}).status_code, 403)
        session = self.session.scalar(select(UserSession).where(UserSession.token_hash == token_hash(self.tokens[0])))
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.session.flush()
        self.assertEqual(self.client.get('/api/relationship').status_code, 401)

    def test_validation_and_owner_injection(self):
        for patch in ({'category': 'unknown'}, {'description': '  '}, {'occurred_at': '2026-10-01T12:00:00'},
                      {'notes': 'a' * 10001}, {'relationship_id': str(uuid4())}, {'person': 'anyone'}):
            result = self.client.post('/api/events', json=self.data | patch)
            self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(self.client.get('/api/events?limit=1000').status_code, 422)
        self.assertEqual(self.client.get('/api/events?offset=-1').status_code, 422)

    def test_relationship_upsert_and_ordering(self):
        first = self.client.put('/api/relationship', json={'partner_name': ' Alex '}).json()
        second = self.client.put('/api/relationship', json={'partner_name': 'Sam'}).json()
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['partner_name'], 'Alex')
        for day in (1, 3, 2):
            self.client.post('/api/events', json=self.data | {'occurred_at': f'2026-10-0{day}T12:00:00Z', 'description': str(day)})
        self.assertEqual([row['description'] for row in self.client.get('/api/events?limit=2').json()], ['3', '2'])
        self.assertEqual(self.client.get('/api/events?offset=2').json()[0]['description'], '1')
        self.session.delete(self.owner)
        self.session.flush()
        self.assertEqual(self.session.scalars(select(Event)).all(), [])
        self.assertEqual(self.session.scalars(select(Relationship)).all(), [])
