from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.auth import SESSION_COOKIE, token_hash
from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.main import app
from backend.app.models import NeedUpdate, RelationshipNeed, UserSession
from test_database import DatabaseTestCase


class NeedTests(DatabaseTestCase):
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
        self.data = {
            'person': 'me', 'name': 'Quality time', 'description': 'Time without distractions',
            'why_matters': 'Helps me feel connected', 'importance': 'high',
            'desired_amount': 2, 'desired_period': 'per_week', 'custom_period_days': None,
            'confirmed_by_partner': 'unknown', 'active': True,
        }

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_need_create_edit_archive_and_list(self):
        created = self.client.post('/api/needs', json=self.data)
        self.assertEqual(created.status_code, 201, created.text)
        need_id = created.json()['id']
        self.assertEqual(created.json()['updates'], [])
        self.assertEqual(self.client.get('/api/needs').json()[0]['name'], 'Quality time')

        changed = self.client.put('/api/needs/' + need_id, json=self.data | {
            'name': 'Intentional time', 'desired_amount': None, 'desired_period': 'as_needed'})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()['name'], 'Intentional time')

        archived = self.client.patch('/api/needs/' + need_id + '/archive', json={'active': False})
        self.assertEqual(archived.status_code, 200)
        self.assertFalse(archived.json()['active'])
        self.assertEqual(self.client.get('/api/needs').json(), [])
        self.assertEqual(self.client.get('/api/needs?include_archived=true').json()[0]['id'], need_id)

        restored = self.client.patch('/api/needs/' + need_id + '/archive', json={'active': True})
        self.assertTrue(restored.json()['active'])

    def test_need_update_history_edit_and_delete(self):
        need_id = self.client.post('/api/needs', json=self.data).json()['id']
        updates = [
            {'occurred_on': '2026-10-01', 'status': 'partly_met', 'what_happened': 'Dinner together',
             'satisfaction': 3, 'notes': 'Phones came out'},
            {'occurred_on': '2026-10-03', 'status': 'met', 'what_happened': 'Long walk',
             'satisfaction': 5, 'notes': None},
        ]
        ids = []
        for data in updates:
            response = self.client.post(f'/api/needs/{need_id}/updates', json=data)
            self.assertEqual(response.status_code, 201, response.text)
            ids.append(response.json()['id'])
        history = self.client.get('/api/needs').json()[0]['updates']
        self.assertEqual([row['occurred_on'] for row in history], ['2026-10-03', '2026-10-01'])

        edited = self.client.put(f'/api/needs/{need_id}/updates/{ids[0]}', json=updates[0] | {
            'status': 'met', 'satisfaction': 4})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()['satisfaction'], 4)
        self.assertEqual(self.client.delete(f'/api/needs/{need_id}/updates/{ids[1]}').status_code, 204)
        self.assertEqual(len(self.client.get('/api/needs').json()[0]['updates']), 1)

    def test_partner_confirmation_and_cadence_validation(self):
        partner = self.data | {'person': 'partner', 'confirmed_by_partner': 'yes', 'name': 'Personal space'}
        self.assertEqual(self.client.post('/api/needs', json=partner).status_code, 201)
        valid_custom = self.data | {'desired_period': 'custom', 'desired_amount': 3, 'custom_period_days': 14}
        self.assertEqual(self.client.post('/api/needs', json=valid_custom).status_code, 201)
        invalid = [
            {'person': 'both'}, {'name': ' '}, {'importance': 'urgent'},
            {'desired_amount': None, 'desired_period': 'per_week'},
            {'desired_amount': 2, 'desired_period': 'as_needed'},
            {'desired_period': 'custom', 'desired_amount': 2, 'custom_period_days': None},
            {'desired_period': 'per_month', 'desired_amount': 2, 'custom_period_days': 30},
            {'confirmed_by_partner': 'yes'}, {'unexpected': 'value'},
        ]
        for patch in invalid:
            response = self.client.post('/api/needs', json=self.data | patch)
            self.assertEqual(response.status_code, 422, (patch, response.text))

    def test_need_and_update_ownership(self):
        need_id = self.client.post('/api/needs', json=self.data).json()['id']
        update_data = {'occurred_on': '2026-10-03', 'status': 'met', 'what_happened': 'A walk', 'satisfaction': 5}
        update_id = self.client.post(f'/api/needs/{need_id}/updates', json=update_data).json()['id']
        self.client.cookies.set(SESSION_COOKIE, self.tokens[1])
        self.assertEqual(self.client.get('/api/needs').json(), [])
        self.assertEqual(self.client.put('/api/needs/' + need_id, json=self.data).status_code, 404)
        self.assertEqual(self.client.patch('/api/needs/' + need_id + '/archive', json={'active': False}).status_code, 404)
        self.assertEqual(self.client.post(f'/api/needs/{need_id}/updates', json=update_data).status_code, 404)
        self.assertEqual(self.client.put(f'/api/needs/{need_id}/updates/{update_id}', json=update_data).status_code, 404)
        self.assertEqual(self.client.delete(f'/api/needs/{need_id}/updates/{update_id}').status_code, 404)

    def test_need_update_validation_and_cascade(self):
        need_id = self.client.post('/api/needs', json=self.data).json()['id']
        base = {'occurred_on': '2026-10-03', 'status': 'met', 'what_happened': 'A walk', 'satisfaction': 5}
        for patch in ({'status': 'maybe'}, {'what_happened': ' '}, {'satisfaction': 0},
                      {'satisfaction': 6}, {'occurred_on': 'not-a-date'}, {'need_id': str(uuid4())}):
            response = self.client.post(f'/api/needs/{need_id}/updates', json=base | patch)
            self.assertEqual(response.status_code, 422, (patch, response.text))
        self.client.post(f'/api/needs/{need_id}/updates', json=base)
        self.session.delete(self.owner)
        self.session.flush()
        self.assertEqual(self.session.scalars(select(RelationshipNeed)).all(), [])
        self.assertEqual(self.session.scalars(select(NeedUpdate)).all(), [])
