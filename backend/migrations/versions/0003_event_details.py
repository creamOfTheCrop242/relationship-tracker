"""Add validated category-specific event details."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003_event_details'
down_revision = '0002_events'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column(
        'details', postgresql.JSONB(astext_type=sa.Text()),
        nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade():
    op.drop_column('events', 'details')
