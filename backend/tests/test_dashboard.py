from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.auth import SESSION_COOKIE, token_hash
from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.main import app
from backend.app.models import UserSession
from test_database import DatabaseTestCase


class DashboardTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.other = self.user(), self.user()
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

    def event(self, category, description, occurred_at, details=None):
        response = self.client.post('/api/events', json={
            'category': category, 'description': description, 'occurred_at': occurred_at,
            'person': 'both', 'details': details or {},
        })
        self.assertEqual(response.status_code, 201, response.text)

    def need(self, name, importance='medium'):
        response = self.client.post('/api/needs', json={
            'person': 'me', 'name': name, 'importance': importance,
            'desired_amount': None, 'desired_period': 'no_target',
            'custom_period_days': None, 'confirmed_by_partner': 'unknown', 'active': True,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def update(self, need_id, day, satisfaction, status='met'):
        response = self.client.post(f'/api/needs/{need_id}/updates', json={
            'occurred_on': day.isoformat(), 'status': status,
            'what_happened': f'Update {satisfaction}', 'satisfaction': satisfaction,
        })
        self.assertEqual(response.status_code, 201, response.text)

    def test_empty_dashboard(self):
        response = self.client.get('/api/dashboard')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data['latest_events']), {'intimacy', 'kindness', 'conflict', 'outing', 'alcohol', 'childcare'})
        self.assertTrue(all(value is None for value in data['latest_events'].values()))
        self.assertIsNone(data['latest_upset'])
        self.assertEqual(data['recent_events'], [])
        self.assertEqual(data['needs'], [])

    def test_activity_cards_recent_events_and_owner_isolation(self):
        self.event('kindness', 'Older kindness', '2026-10-01T12:00:00Z')
        self.event('conflict', 'Upset conversation', '2026-10-02T12:00:00Z', {'upset': 'both'})
        self.event('kindness', 'New kindness', '2026-10-03T12:00:00Z')
        self.event('conflict', 'Calm disagreement', '2026-10-04T12:00:00Z')
        self.client.cookies.set(SESSION_COOKIE, self.tokens[1])
        self.event('outing', 'Other user private event', '2026-10-05T12:00:00Z')
        self.client.cookies.set(SESSION_COOKIE, self.tokens[0])

        data = self.client.get('/api/dashboard').json()
        self.assertEqual(data['latest_events']['kindness']['description'], 'New kindness')
        self.assertEqual(data['latest_events']['conflict']['description'], 'Calm disagreement')
        self.assertIsNone(data['latest_events']['outing'])
        self.assertEqual(data['latest_upset']['description'], 'Upset conversation')
        self.assertEqual([row['description'] for row in data['recent_events']],
                         ['Calm disagreement', 'New kindness', 'Upset conversation', 'Older kindness'])

    def test_need_flags_and_trends(self):
        improving = self.need('Connection', 'high')
        low = self.need('Support')
        missing = self.need('Space', 'low')
        today = date.today()
        for days_ago, satisfaction in ((8, 1), (7, 2), (2, 4), (1, 5)):
            self.update(improving, today - timedelta(days=days_ago), satisfaction)
        self.update(low, today - timedelta(days=30), 2, 'not_met')

        rows = {row['name']: row for row in self.client.get('/api/dashboard').json()['needs']}
        self.assertEqual(rows['Connection']['trend'], 'improving')
        self.assertFalse(rows['Connection']['low_satisfaction'])
        self.assertFalse(rows['Connection']['stale'])
        self.assertEqual(rows['Support']['latest_status'], 'not_met')
        self.assertTrue(rows['Support']['low_satisfaction'])
        self.assertTrue(rows['Support']['stale'])
        self.assertIsNone(rows['Space']['latest_update_on'])
        self.assertEqual(rows['Space']['trend'], 'not_enough_data')
        self.assertTrue(rows['Space']['stale'])

        self.client.cookies.set(SESSION_COOKIE, self.tokens[1])
        self.need('Private need')
        self.client.cookies.set(SESSION_COOKIE, self.tokens[0])
        self.assertNotIn('Private need', {row['name'] for row in self.client.get('/api/dashboard').json()['needs']})
