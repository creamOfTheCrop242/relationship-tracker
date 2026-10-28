"""Specific requests beneath broad relationship needs."""
from alembic import op
import sqlalchemy as sa

revision = '0010_need_requests'
down_revision = '0009_person_profiles'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('need_requests',
        sa.Column('id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('need_id', sa.Uuid(), sa.ForeignKey('relationship_needs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('desired_amount', sa.Integer()),
        sa.Column('desired_period', sa.Text(), nullable=False, server_default='no_target'),
        sa.Column('custom_period_days', sa.Integer()),
        sa.Column('confirmed_by_person', sa.Text(), nullable=False, server_default='unknown'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("desired_period IN ('per_day', 'per_week', 'per_month', 'custom', 'as_needed', 'no_target')", name='need_requests_period_check'),
        sa.CheckConstraint("confirmed_by_person IN ('yes', 'no', 'unknown')", name='need_requests_confirmation_check'),
        sa.CheckConstraint('desired_amount IS NULL OR desired_amount > 0', name='need_requests_amount_check'),
        sa.CheckConstraint('custom_period_days IS NULL OR custom_period_days > 0', name='need_requests_custom_days_check'),
        sa.CheckConstraint("(desired_period IN ('per_day', 'per_week', 'per_month', 'custom') AND desired_amount IS NOT NULL) OR (desired_period IN ('as_needed', 'no_target') AND desired_amount IS NULL)", name='need_requests_cadence_check'),
        sa.CheckConstraint("(desired_period = 'custom' AND custom_period_days IS NOT NULL) OR (desired_period <> 'custom' AND custom_period_days IS NULL)", name='need_requests_custom_period_check'))
    op.create_index('need_requests_need_active_idx', 'need_requests', ['need_id', 'active', 'created_at'])
    op.add_column('relationship_tasks', sa.Column('request_id', sa.Uuid(), sa.ForeignKey('need_requests.id', ondelete='SET NULL')))
    op.create_index('relationship_tasks_request_idx', 'relationship_tasks', ['request_id', 'status', 'created_at'])


def downgrade():
    op.drop_index('relationship_tasks_request_idx', table_name='relationship_tasks')
    op.drop_column('relationship_tasks', 'request_id')
    op.drop_table('need_requests')
