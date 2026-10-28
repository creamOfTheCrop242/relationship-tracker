"""Relationship tasks, reminder preferences, and web push subscriptions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0007_mobile_reminders'
down_revision = '0006_ai_reflections'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('reminders_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('reminder_time', sa.Time(), nullable=False, server_default='09:00:00'))
    op.add_column('users', sa.Column('ai_suggestion_frequency', sa.Text(), nullable=False, server_default='weekly'))
    op.add_column('users', sa.Column('completed_task_prompt', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.create_check_constraint('users_ai_suggestion_frequency_check', 'users', "ai_suggestion_frequency IN ('off', 'weekly', 'monthly')")
    op.add_column('relationship_needs', sa.Column('reminders_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')))

    op.create_table('relationship_tasks',
        sa.Column('id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('relationship_id', sa.Uuid(), sa.ForeignKey('relationships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('need_id', sa.Uuid(), sa.ForeignKey('relationship_needs.id', ondelete='SET NULL')),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('snoozed_until', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('notified_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source IN ('cadence', 'ai', 'manual')", name='relationship_tasks_source_check'),
        sa.CheckConstraint("status IN ('pending', 'completed', 'snoozed', 'dismissed')", name='relationship_tasks_status_check'))
    op.create_index('relationship_tasks_due_idx', 'relationship_tasks', ['relationship_id', 'status', 'due_at'])

    op.create_table('push_subscriptions',
        sa.Column('id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False, unique=True),
        sa.Column('p256dh', sa.Text(), nullable=False),
        sa.Column('auth', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('push_subscriptions_user_idx', 'push_subscriptions', ['user_id'])


def downgrade():
    op.drop_table('push_subscriptions')
    op.drop_table('relationship_tasks')
    op.drop_column('relationship_needs', 'reminders_enabled')
    op.drop_constraint('users_ai_suggestion_frequency_check', 'users', type_='check')
    op.drop_column('users', 'completed_task_prompt')
    op.drop_column('users', 'ai_suggestion_frequency')
    op.drop_column('users', 'reminder_time')
    op.drop_column('users', 'reminders_enabled')
