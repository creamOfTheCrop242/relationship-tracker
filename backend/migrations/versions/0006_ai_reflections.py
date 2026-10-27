"""AI privacy settings and persisted period reflections."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006_ai_reflections'
down_revision = '0005_need_integrity'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('ai_analysis_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('ai_timezone', sa.Text(), nullable=False, server_default='UTC'))
    op.create_table('relationship_summaries',
        sa.Column('id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('relationship_id', sa.Uuid(), sa.ForeignKey('relationships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('period_type', sa.Text(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('score', sa.Integer()),
        sa.Column('confidence', sa.Text(), nullable=False),
        sa.Column('coverage_days', sa.Integer(), nullable=False),
        sa.Column('total_days', sa.Integer(), nullable=False),
        sa.Column('events_analyzed', sa.Integer(), nullable=False),
        sa.Column('need_updates_analyzed', sa.Integer(), nullable=False),
        sa.Column('data_summary', sa.Text(), nullable=False),
        sa.Column('positive_factors', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('friction_factors', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('interpretation', sa.Text(), nullable=False),
        sa.Column('comparison', sa.Text(), nullable=False),
        sa.Column('unresolved_issues', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('suggested_actions', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('reflection', sa.Text(), nullable=False),
        sa.Column('limitations', sa.Text(), nullable=False),
        sa.Column('model', sa.Text()),
        sa.Column('response_id', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("period_type IN ('daily', 'weekly', 'monthly', 'yearly')", name='relationship_summaries_period_type_check'),
        sa.CheckConstraint("confidence IN ('low', 'medium', 'high')", name='relationship_summaries_confidence_check'),
        sa.CheckConstraint('score IS NULL OR score BETWEEN 0 AND 100', name='relationship_summaries_score_check'),
        sa.CheckConstraint('period_end > period_start', name='relationship_summaries_dates_check'))
    op.create_index('relationship_summaries_period_idx', 'relationship_summaries',
                    ['relationship_id', 'period_type', 'period_start', 'period_end'], unique=True)


def downgrade():
    op.drop_table('relationship_summaries')
    op.drop_column('users', 'ai_timezone')
    op.drop_column('users', 'ai_analysis_enabled')
