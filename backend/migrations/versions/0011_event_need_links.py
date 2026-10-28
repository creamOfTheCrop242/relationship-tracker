"""Link journal events to broad needs and specific requests."""
from alembic import op
import sqlalchemy as sa

revision = '0011_event_need_links'
down_revision = '0010_need_requests'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('need_id', sa.Uuid(), sa.ForeignKey('relationship_needs.id', ondelete='SET NULL')))
    op.add_column('events', sa.Column('request_id', sa.Uuid(), sa.ForeignKey('need_requests.id', ondelete='SET NULL')))
    op.create_index('events_need_time_idx', 'events', ['need_id', 'occurred_at'])
    op.create_index('events_request_time_idx', 'events', ['request_id', 'occurred_at'])


def downgrade():
    op.drop_index('events_request_time_idx', table_name='events')
    op.drop_index('events_need_time_idx', table_name='events')
    op.drop_column('events', 'request_id')
    op.drop_column('events', 'need_id')
