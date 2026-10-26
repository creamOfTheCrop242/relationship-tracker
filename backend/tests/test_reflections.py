from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.auth import SESSION_COOKIE, token_hash
from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.main import app
from backend.app.models import UserSession
from backend.app.reflection_jobs import due_periods
from backend.app.reflections import ReflectionContent, generate_content, period_bounds
from test_database import DatabaseTestCase


class ReflectionTests(DatabaseTestCase):
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
        self.ai_settings = SimpleNamespace(openai_api_key='test-key', openai_model='test-model')

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        super().tearDown()

    def enable(self, timezone_name='UTC'):
        with patch('backend.app.reflections.get_settings', return_value=self.ai_settings):
            response = self.client.put('/api/analysis/settings', json={'enabled': True, 'timezone': timezone_name})
        self.assertEqual(response.status_code, 200, response.text)

    def test_settings_default_validation_and_availability(self):
        with patch('backend.app.reflections.get_settings', return_value=SimpleNamespace(openai_api_key=None, openai_model='test-model')):
            data = self.client.get('/api/analysis/settings').json()
        self.assertEqual(data, {'enabled': False, 'timezone': 'UTC', 'available': False, 'model': 'test-model'})
        self.assertEqual(self.client.put('/api/analysis/settings', json={'enabled': True, 'timezone': 'Mars/Olympus'}).status_code, 422)
        self.assertEqual(self.client.put('/api/analysis/settings', json={'enabled': True, 'timezone': 'UTC', 'extra': True}).status_code, 422)
        self.enable('America/New_York')
        self.session.refresh(self.owner)
        self.assertTrue(self.owner.ai_analysis_enabled)
        self.assertEqual(self.owner.ai_timezone, 'America/New_York')

    def test_generation_requires_opt_in_and_configuration(self):
        request = {'period_type': 'daily', 'anchor_date': '2026-10-01'}
        with patch('backend.app.reflections.get_settings', return_value=self.ai_settings), \
             patch('backend.app.reflections.generate_content') as generate:
            self.assertEqual(self.client.post('/api/reflections/generate', json=request).status_code, 403)
            generate.assert_not_called()
        self.enable()
        with patch('backend.app.reflections.get_settings', return_value=SimpleNamespace(openai_api_key=None, openai_model='test-model')):
            self.assertEqual(self.client.post('/api/reflections/generate', json=request).status_code, 503)

    def test_sparse_reflection_is_stored_without_model_call(self):
        self.enable()
        with patch('backend.app.reflections.get_settings', return_value=self.ai_settings), \
             patch('backend.app.reflections.generate_content') as generate:
            response = self.client.post('/api/reflections/generate', json={
                'period_type': 'weekly', 'anchor_date': '2026-10-01'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()['score'])
        self.assertEqual(response.json()['confidence'], 'low')
        self.assertEqual(response.json()['coverage_days'], 0)
        self.assertEqual(response.json()['total_days'], 7)
        generate.assert_not_called()

    def test_structured_generation_period_boundaries_regeneration_and_ownership(self):
        self.enable('America/New_York')
        events = [
            ('Start boundary', '2026-10-01T04:00:00Z'),
            ('End boundary inside', '2026-10-02T03:59:00Z'),
            ('Outside', '2026-10-02T04:00:00Z'),
        ]
        for description, occurred_at in events:
            response = self.client.post('/api/events', json={
                'category': 'kindness', 'description': description,
                'occurred_at': occurred_at, 'details': {},
            })
            self.assertEqual(response.status_code, 201, response.text)
        content = ReflectionContent(
            score=78, confidence='medium', data_summary='Two kind moments were recorded.',
            positive_factors=['Kindness'], friction_factors=[], interpretation='Connection may have felt present.',
            comparison='No previous summary.', unresolved_issues=[], suggested_actions=['Keep noticing kind moments.'],
            reflection='The recorded day included two kind moments.', limitations='Only one day of records is available.',
        )
        request = {'period_type': 'daily', 'anchor_date': '2026-10-01'}
        with patch('backend.app.reflections.get_settings', return_value=self.ai_settings), \
             patch('backend.app.reflections.generate_content', return_value=(content, 'resp_1')) as generate:
            first = self.client.post('/api/reflections/generate', json=request)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()['events_analyzed'], 2)
        self.assertEqual(first.json()['coverage_days'], 1)
        payload = generate.call_args.args[0]
        self.assertEqual([row['description'] for row in payload['events']], ['Start boundary', 'End boundary inside'])

        replacement = content.model_copy(update={'score': 82, 'reflection': 'Regenerated.'})
        with patch('backend.app.reflections.get_settings', return_value=self.ai_settings), \
             patch('backend.app.reflections.generate_content', return_value=(replacement, 'resp_2')):
            second = self.client.post('/api/reflections/generate', json=request)
        self.assertEqual(second.json()['id'], first.json()['id'])
        self.assertEqual(second.json()['score'], 82)
        self.assertEqual(len(self.client.get('/api/reflections').json()), 1)

        reflection_id = second.json()['id']
        self.client.cookies.set(SESSION_COOKIE, self.tokens[1])
        self.assertEqual(self.client.get('/api/reflections').json(), [])
        self.assertEqual(self.client.delete('/api/reflections/' + reflection_id).status_code, 404)
        self.client.cookies.set(SESSION_COOKIE, self.tokens[0])
        self.assertEqual(self.client.delete('/api/reflections/' + reflection_id).status_code, 204)
        self.assertEqual(self.client.get('/api/reflections').json(), [])

    def test_period_bounds(self):
        self.assertEqual(period_bounds('daily', date(2026, 10, 7)), (date(2026, 10, 7), date(2026, 10, 8)))
        self.assertEqual(period_bounds('weekly', date(2026, 10, 7)), (date(2026, 10, 5), date(2026, 10, 12)))
        self.assertEqual(period_bounds('monthly', date(2026, 12, 7)), (date(2026, 12, 1), date(2027, 1, 1)))
        self.assertEqual(period_bounds('yearly', date(2026, 10, 7)), (date(2026, 1, 1), date(2027, 1, 1)))

    def test_openai_call_disables_storage_and_uses_structured_output(self):
        content = ReflectionContent(
            score=70, confidence='medium', data_summary='Summary', positive_factors=[], friction_factors=[],
            interpretation='Interpretation', comparison='Comparison', unresolved_issues=[], suggested_actions=[],
            reflection='Reflection', limitations='Limitations')
        with patch('backend.app.reflections.OpenAI') as client_class:
            client_class.return_value.responses.parse.return_value = SimpleNamespace(output_parsed=content, id='resp_test')
            parsed, response_id = generate_content({'events': []}, 'secret', 'test-model')
        self.assertEqual(parsed, content)
        self.assertEqual(response_id, 'resp_test')
        client_class.assert_called_once_with(api_key='secret', timeout=60.0, max_retries=1)
        call = client_class.return_value.responses.parse.call_args
        self.assertEqual(call.kwargs['model'], 'test-model')
        self.assertIs(call.kwargs['text_format'], ReflectionContent)
        self.assertFalse(call.kwargs['store'])

    def test_scheduled_periods_run_after_three_local_time(self):
        self.assertEqual(due_periods(datetime(2026, 10, 26, 2, 59)), [])
        self.assertEqual(due_periods(datetime(2026, 10, 27, 3, 0)), [('daily', date(2026, 10, 26))])
        self.assertEqual(due_periods(datetime(2026, 10, 26, 3, 0)), [
            ('daily', date(2026, 10, 25)), ('weekly', date(2026, 10, 25))])
        self.assertEqual(due_periods(datetime(2027, 1, 1, 3, 0)), [
            ('daily', date(2026, 12, 31)), ('monthly', date(2026, 12, 31)),
            ('yearly', date(2026, 12, 31))])
