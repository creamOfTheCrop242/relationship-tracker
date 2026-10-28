"""Private user and partner profiles."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0009_person_profiles'
down_revision = '0008_daily_ai_tasks'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('person_profiles',
        sa.Column('id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('relationship_id', sa.Uuid(), sa.ForeignKey('relationships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person', sa.Text(), nullable=False),
        sa.Column('love_languages', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('hobbies', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('interests', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('goals', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("person IN ('me', 'partner')", name='person_profiles_person_check'),
        sa.UniqueConstraint('relationship_id', 'person', name='person_profiles_relationship_person_key'))


def downgrade():
    op.drop_table('person_profiles')
