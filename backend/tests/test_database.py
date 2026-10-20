"""Run against a dedicated, migrated PostgreSQL database (TEST_DATABASE_URL)."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_engine
from backend.app.main import app
from backend.app.models import AuthAccount, User, UserSession


class HealthTests(unittest.TestCase):
    def test_liveness_does_not_require_database(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/health').status_code, 200)

    def test_missing_database_returns_generic_unavailable(self):
        with patch('backend.app.main.get_engine', side_effect=RuntimeError('private configuration')):
            with TestClient(app) as client:
                response = client.get('/api/ready')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable', 'database': 'not_ready'})


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'Set TEST_DATABASE_URL to a migrated test database')
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = patch.dict(os.environ, {'DATABASE_URL': os.environ['TEST_DATABASE_URL']})
        cls.env.start()
        get_settings.cache_clear()
        get_engine.cache_clear()

    @classmethod
    def tearDownClass(cls):
        get_engine().dispose()
        get_engine.cache_clear()
        cls.env.stop()
        get_settings.cache_clear()

    def setUp(self):
        self.connection = get_engine().connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, join_transaction_mode='create_savepoint')

    def tearDown(self):
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def user(self):
        user = User(email=f'{uuid4()}@example.test')
        self.session.add(user)
        self.session.flush()
        return user

    def test_defaults_and_cascade_delete(self):
        user = self.user()
        self.assertIsNotNone(user.id)
        self.assertIsNotNone(user.created_at.tzinfo)
        self.session.add_all([
            AuthAccount(user_id=user.id, provider='google', provider_subject='subject', email=user.email),
            UserSession(user_id=user.id, token_hash='hash', expires_at=datetime.now(timezone.utc) + timedelta(days=1)),
        ])
        self.session.flush()
        self.session.delete(user)
        self.session.flush()
        for model in (AuthAccount, UserSession):
            self.assertEqual(self.session.scalar(select(func.count()).select_from(model)), 0)

    def test_provider_subject_is_unique_within_provider(self):
        user = self.user()
        for provider in ('google', 'apple'):
            self.session.add(AuthAccount(user_id=user.id, provider=provider, provider_subject='same', email=user.email))
        self.session.flush()
        with self.assertRaises(IntegrityError), self.session.begin_nested():
            self.session.add(AuthAccount(user_id=user.id, provider='google', provider_subject='same', email=user.email))
            self.session.flush()

    def test_orphan_session_is_rejected(self):
        with self.assertRaises(IntegrityError), self.session.begin_nested():
            self.session.add(UserSession(user_id=uuid4(), token_hash='orphan', expires_at=datetime.now(timezone.utc)))
            self.session.flush()

    def test_duplicate_email_and_session_hash_are_rejected(self):
        user = self.user()
        with self.assertRaises(IntegrityError), self.session.begin_nested():
            self.session.add(User(email=user.email))
            self.session.flush()
        self.session.add(UserSession(user_id=user.id, token_hash='unique', expires_at=datetime.now(timezone.utc)))
        self.session.flush()
        with self.assertRaises(IntegrityError), self.session.begin_nested():
            self.session.add(UserSession(user_id=user.id, token_hash='unique', expires_at=datetime.now(timezone.utc)))
            self.session.flush()

    def test_migrated_database_is_ready(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/ready').status_code, 200)
