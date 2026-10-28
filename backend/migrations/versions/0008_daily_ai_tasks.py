"""Allow daily AI task suggestions."""
from alembic import op

revision = '0008_daily_ai_tasks'
down_revision = '0007_mobile_reminders'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('users_ai_suggestion_frequency_check', 'users', type_='check')
    op.create_check_constraint('users_ai_suggestion_frequency_check', 'users',
                               "ai_suggestion_frequency IN ('off', 'daily', 'weekly', 'monthly')")


def downgrade():
    op.execute("UPDATE users SET ai_suggestion_frequency = 'weekly' WHERE ai_suggestion_frequency = 'daily'")
    op.drop_constraint('users_ai_suggestion_frequency_check', 'users', type_='check')
    op.create_check_constraint('users_ai_suggestion_frequency_check', 'users',
                               "ai_suggestion_frequency IN ('off', 'weekly', 'monthly')")
