from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.auth import SESSION_COOKIE, token_hash
from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.main import app
from backend.app.models import RelationshipTask, UserSession
from backend.app.reminder_jobs import (TaskSuggestionContent, generate_ai_task,
                                       generate_cadence_tasks, generate_task_suggestion)
from test_database import DatabaseTestCase


class TaskTests(DatabaseTestCase):
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

    def test_task_lifecycle_settings_and_ownership(self):
        due = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        created = self.client.post('/api/tasks', json={
            'title': 'Plan a walk', 'description': 'After dinner', 'due_at': due, 'need_id': None})
        self.assertEqual(created.status_code, 201, created.text)
        task_id = created.json()['id']
        self.assertEqual(created.json()['source'], 'manual')

        snooze = self.client.post(f'/api/tasks/{task_id}/action', json={
            'action': 'snooze', 'until': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
        self.assertEqual(snooze.json()['status'], 'snoozed')
        self.assertEqual(self.client.post(f'/api/tasks/{task_id}/action', json={
            'action': 'snooze', 'until': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}).status_code, 422)
        self.assertEqual(self.client.post(f'/api/tasks/{task_id}/action', json={'action': 'complete'}).json()['status'], 'completed')
        self.assertEqual(self.client.post(f'/api/tasks/{task_id}/action', json={'action': 'reopen'}).json()['status'], 'pending')

        settings = {'enabled': True, 'reminder_time': '10:00:00',
                    'ai_suggestion_frequency': 'monthly', 'completed_task_prompt': False,
                    'timezone': 'America/New_York'}
        self.assertEqual(self.client.put('/api/reminder-settings', json=settings).json(), settings)
        daily = settings | {'ai_suggestion_frequency': 'daily'}
        self.assertEqual(self.client.put('/api/reminder-settings', json=daily).json(), daily)

        self.client.cookies.set(SESSION_COOKIE, self.tokens[1])
        self.assertEqual(self.client.get('/api/tasks').json(), [])
        self.assertEqual(self.client.post(f'/api/tasks/{task_id}/action', json={'action': 'dismiss'}).status_code, 404)

    def test_cadence_job_creates_one_task_per_period(self):
        relationship = self.client.put('/api/relationship', json={'partner_name': 'Partner'}).json()
        need_data = {'person': 'me', 'name': 'Quality time', 'description': None, 'why_matters': None,
                     'importance': 'high', 'desired_amount': 1, 'desired_period': 'per_week',
                     'custom_period_days': None, 'confirmed_by_partner': 'unknown', 'active': True,
                     'reminders_enabled': True}
        self.assertEqual(self.client.post('/api/needs', json=need_data).status_code, 201)
        self.owner.reminders_enabled = True
        local_now = datetime.now(timezone.utc).replace(hour=self.owner.reminder_time.hour)
        from backend.app.models import Relationship
        relationship_row = self.session.get(Relationship, relationship['id'])
        self.assertEqual(generate_cadence_tasks(self.session, self.owner, relationship_row, local_now), 1)
        self.session.flush()
        self.assertEqual(generate_cadence_tasks(self.session, self.owner, relationship_row, local_now), 0)
        self.assertEqual(len(self.session.scalars(select(RelationshipTask)).all()), 1)

    def test_specific_request_drives_cadence_task(self):
        relationship = self.client.put('/api/relationship', json={'partner_name': 'Jay'}).json()
        need = self.client.post('/api/needs', json={
            'person': 'partner', 'name': 'Love and consideration', 'description': None, 'why_matters': None,
            'importance': 'high', 'desired_amount': None, 'desired_period': 'no_target',
            'custom_period_days': None, 'confirmed_by_partner': 'yes', 'active': True,
            'reminders_enabled': True}).json()
        request = self.client.post(f"/api/needs/{need['id']}/requests", json={
            'title': 'Give Jay a foot rub', 'description': None, 'desired_amount': 1,
            'desired_period': 'per_day', 'custom_period_days': None,
            'confirmed_by_person': 'yes', 'active': True}).json()
        self.owner.reminders_enabled = True
        local_now = datetime.now(timezone.utc).replace(hour=self.owner.reminder_time.hour)
        from backend.app.models import Relationship
        relationship_row = self.session.get(Relationship, relationship['id'])
        self.assertEqual(generate_cadence_tasks(self.session, self.owner, relationship_row, local_now), 1)
        self.session.flush()
        task = self.session.scalar(select(RelationshipTask).where(RelationshipTask.request_id == request['id']))
        self.assertEqual(task.title, 'Give Jay a foot rub')
        self.assertEqual(str(task.need_id), need['id'])

    def test_linked_journal_entry_satisfies_specific_request_cadence(self):
        relationship = self.client.put('/api/relationship', json={'partner_name': 'Jay'}).json()
        need = self.client.post('/api/needs', json={
            'person': 'partner', 'name': 'Love and consideration', 'description': None,
            'why_matters': None, 'importance': 'high', 'desired_amount': None,
            'desired_period': 'no_target', 'custom_period_days': None,
            'confirmed_by_partner': 'yes', 'active': True, 'reminders_enabled': True,
        }).json()
        request = self.client.post(f"/api/needs/{need['id']}/requests", json={
            'title': 'Do something thoughtful', 'description': None, 'desired_amount': 1,
            'desired_period': 'per_day', 'custom_period_days': None,
            'confirmed_by_person': 'yes', 'active': True,
        }).json()
        local_now = datetime.now(timezone.utc).replace(hour=self.owner.reminder_time.hour)
        logged = self.client.post('/api/events', json={
            'category': 'kindness', 'description': 'Left a thoughtful note',
            'occurred_at': local_now.isoformat(), 'need_id': need['id'], 'request_id': request['id'],
        })
        self.assertEqual(logged.status_code, 201, logged.text)
        self.owner.reminders_enabled = True
        from backend.app.models import Relationship
        relationship_row = self.session.get(Relationship, relationship['id'])
        self.assertEqual(generate_cadence_tasks(self.session, self.owner, relationship_row, local_now), 0)
        self.assertIsNone(self.session.scalar(select(RelationshipTask).where(
            RelationshipTask.request_id == request['id'])))

    def test_push_subscription_validation_and_account_isolation(self):
        payload = {'endpoint': 'https://push.example/one', 'keys': {'p256dh': 'key', 'auth': 'auth'}}
        self.assertEqual(self.client.post('/api/push/subscriptions', json=payload).status_code, 201)
        self.assertEqual(self.client.post('/api/push/subscriptions', json={
            'endpoint': 'https://push.example/bad', 'keys': {'p256dh': 'key'}}).status_code, 422)
        self.client.cookies.set(SESSION_COOKIE, self.tokens[1])
        self.assertEqual(self.client.post('/api/push/subscriptions', json=payload).status_code, 409)

    def test_daily_ai_task_uses_fresh_owned_context_and_avoids_cadence_request(self):
        relationship = self.client.put('/api/relationship', json={'partner_name': 'Jay'}).json()
        need = self.client.post('/api/needs', json={
            'person': 'partner', 'name': 'Love and consideration', 'description': 'Feeling considered',
            'why_matters': 'Connection', 'importance': 'high', 'desired_amount': None,
            'desired_period': 'no_target', 'custom_period_days': None,
            'confirmed_by_partner': 'yes', 'active': True, 'reminders_enabled': True}).json()
        request = self.client.post(f"/api/needs/{need['id']}/requests", json={
            'title': 'Daily foot rub', 'description': None, 'desired_amount': 1,
            'desired_period': 'per_day', 'custom_period_days': None,
            'confirmed_by_person': 'yes', 'active': True}).json()
        self.client.put('/api/profiles/partner', json={
            'love_languages': ['acts_of_service'], 'hobbies': ['Reading'], 'interests': [],
            'goals': ['Rest more'], 'notes': None})
        self.owner.reminders_enabled = True
        self.owner.ai_analysis_enabled = True
        self.owner.ai_suggestion_frequency = 'daily'
        local_now = datetime.now(timezone.utc).replace(hour=self.owner.reminder_time.hour)
        from backend.app.models import Relationship
        relationship_row = self.session.get(Relationship, relationship['id'])
        suggestion = TaskSuggestionContent(
            title='Leave Jay a thoughtful note', description='Write one specific thing you appreciate today.',
            need_id=need['id'], request_id=None)
        settings = SimpleNamespace(openai_api_key='test-key', openai_model='test-model')
        with patch('backend.app.reminder_jobs.get_settings', return_value=settings), \
             patch('backend.app.reminder_jobs.generate_task_suggestion', return_value=suggestion) as generate:
            self.assertEqual(generate_ai_task(self.session, self.owner, relationship_row, local_now), 1)
        payload = generate.call_args.args[0]
        self.assertEqual([row['name'] for row in payload['active_needs']], ['Love and consideration'])
        self.assertTrue(payload['active_needs'][0]['specific_requests'][0]['has_automatic_cadence'])
        task = self.session.scalar(select(RelationshipTask).where(RelationshipTask.source == 'ai'))
        self.assertEqual(task.title, 'Leave Jay a thoughtful note')
        self.assertIsNone(task.request_id)

    def test_openai_task_suggestion_disables_storage(self):
        suggestion = TaskSuggestionContent(
            title='Send a kind message', description='Share one thing you appreciate.',
            need_id=uuid4(), request_id=None)
        with patch('backend.app.reminder_jobs.OpenAI') as client_class:
            client_class.return_value.responses.parse.return_value = SimpleNamespace(output_parsed=suggestion)
            parsed = generate_task_suggestion({'active_needs': []}, 'secret', 'test-model')
        self.assertEqual(parsed, suggestion)
        client_class.assert_called_once_with(api_key='secret', timeout=60.0, max_retries=1)
        call = client_class.return_value.responses.parse.call_args
        self.assertIs(call.kwargs['text_format'], TaskSuggestionContent)
        self.assertFalse(call.kwargs['store'])
