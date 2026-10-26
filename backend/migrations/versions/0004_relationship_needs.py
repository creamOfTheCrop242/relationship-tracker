"""Relationship needs and dated need updates."""
from alembic import op
import sqlalchemy as sa

revision = '0004_relationship_needs'
down_revision = '0003_event_details'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('relationship_needs',
        sa.Column('id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('relationship_id', sa.Uuid(), sa.ForeignKey('relationships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('why_matters', sa.Text()),
        sa.Column('importance', sa.Text(), nullable=False),
        sa.Column('desired_amount', sa.Integer()),
        sa.Column('desired_period', sa.Text(), nullable=False),
        sa.Column('custom_period_days', sa.Integer()),
        sa.Column('confirmed_by_partner', sa.Text(), nullable=False, server_default='unknown'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("person IN ('me', 'partner')", name='relationship_needs_person_check'),
        sa.CheckConstraint("importance IN ('low', 'medium', 'high')", name='relationship_needs_importance_check'),
        sa.CheckConstraint("desired_period IN ('per_day', 'per_week', 'per_month', 'custom', 'as_needed', 'no_target')", name='relationship_needs_period_check'),
        sa.CheckConstraint("confirmed_by_partner IN ('yes', 'no', 'unknown')", name='relationship_needs_confirmation_check'),
        sa.CheckConstraint('desired_amount IS NULL OR desired_amount > 0', name='relationship_needs_amount_check'),
        sa.CheckConstraint('custom_period_days IS NULL OR custom_period_days > 0', name='relationship_needs_custom_days_check'))
    op.create_index('relationship_needs_relationship_active_idx', 'relationship_needs', ['relationship_id', 'active', 'created_at'])
    op.create_table('need_updates',
        sa.Column('id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('need_id', sa.Uuid(), sa.ForeignKey('relationship_needs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('occurred_on', sa.Date(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('what_happened', sa.Text(), nullable=False),
        sa.Column('satisfaction', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('met', 'partly_met', 'not_met')", name='need_updates_status_check'),
        sa.CheckConstraint('satisfaction BETWEEN 1 AND 5', name='need_updates_satisfaction_check'))
    op.create_index('need_updates_need_date_idx', 'need_updates', ['need_id', 'occurred_on', 'id'])


def downgrade():
    op.drop_table('need_updates')
    op.drop_table('relationship_needs')
