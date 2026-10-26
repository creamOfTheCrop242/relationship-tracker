"""Enforce valid need cadence and confirmation combinations."""
from alembic import op

revision = '0005_need_integrity'
down_revision = '0004_relationship_needs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        'relationship_needs_cadence_check', 'relationship_needs',
        "(desired_period IN ('per_day', 'per_week', 'per_month', 'custom') AND desired_amount IS NOT NULL) OR (desired_period IN ('as_needed', 'no_target') AND desired_amount IS NULL)")
    op.create_check_constraint(
        'relationship_needs_custom_period_check', 'relationship_needs',
        "(desired_period = 'custom' AND custom_period_days IS NOT NULL) OR (desired_period <> 'custom' AND custom_period_days IS NULL)")
    op.create_check_constraint(
        'relationship_needs_person_confirmation_check', 'relationship_needs',
        "person = 'partner' OR confirmed_by_partner = 'unknown'")


def downgrade():
    op.drop_constraint('relationship_needs_person_confirmation_check', 'relationship_needs', type_='check')
    op.drop_constraint('relationship_needs_custom_period_check', 'relationship_needs', type_='check')
    op.drop_constraint('relationship_needs_cadence_check', 'relationship_needs', type_='check')
