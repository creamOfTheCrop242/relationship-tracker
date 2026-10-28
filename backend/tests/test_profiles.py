from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.auth import SESSION_COOKIE, token_hash
from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.main import app
from backend.app.models import UserSession
from test_database import DatabaseTestCase


class ProfileTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.other = self.user(), self.user()
        self.owner.display_name = 'Alex Owner'
        self.tokens = [str(uuid4()), str(uuid4())]
        for user, token in zip((self.owner, self.other), self.tokens):
            self.session.add(UserSession(user_id=user.id, token_hash=token_hash(token),
                                         expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        self.session.flush()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app, headers={'Origin': get_settings().frontend_url.rstrip('/')})
        self.client.cookies.set(SESSION_COOKIE, self.tokens[0])

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_profiles_are_private_editable_and_named_from_relationship(self):
        self.client.put('/api/relationship', json={'partner_name': 'Jordan'})
        profiles = self.client.get('/api/profiles')
        self.assertEqual(profiles.status_code, 200, profiles.text)
        self.assertEqual([(row['person'], row['display_name']) for row in profiles.json()],
                         [('me', 'Alex Owner'), ('partner', 'Jordan')])
        payload = {
            'love_languages': ['quality_time', 'acts_of_service'],
            'hobbies': ['Hiking', 'Hiking', ''], 'interests': ['Live music'],
            'goals': ['Plan a vacation'], 'notes': 'Prefers quiet mornings',
        }
        updated = self.client.put('/api/profiles/partner', json=payload)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['hobbies'], ['Hiking'])

        self.client.cookies.set(SESSION_COOKIE, self.tokens[1])
        other = self.client.get('/api/profiles').json()
        self.assertEqual(other[1]['display_name'], 'Partner')
        self.assertEqual(other[1]['hobbies'], [])

    def test_profile_validation(self):
        base = {'love_languages': [], 'hobbies': [], 'interests': [], 'goals': [], 'notes': None}
        self.assertEqual(self.client.put('/api/profiles/someone', json=base).status_code, 422)
        self.assertEqual(self.client.put('/api/profiles/me', json=base | {
            'love_languages': ['unknown']} ).status_code, 422)
        self.assertEqual(self.client.put('/api/profiles/me', json=base | {
            'hobbies': ['x' * 201]}).status_code, 422)
        self.assertEqual(self.client.put('/api/profiles/me', json=base | {
            'unexpected': True}).status_code, 422)
