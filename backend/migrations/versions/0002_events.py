"""Relationships and private journal entries."""
from alembic import op
import sqlalchemy as sa

revision = '0002_events'
down_revision = '0001_accounts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('relationships',
        sa.Column('id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('partner_name', sa.Text(), nullable=False, server_default='Partner'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table('events',
        sa.Column('id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('relationship_id', sa.Uuid(), sa.ForeignKey('relationships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('person', sa.Text()), sa.Column('mood', sa.Text()),
        sa.Column('impact', sa.Text()), sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('events_relationship_time_idx', 'events', ['relationship_id', 'occurred_at', 'id'])


def downgrade():
    op.drop_table('events')
    op.drop_table('relationships')
