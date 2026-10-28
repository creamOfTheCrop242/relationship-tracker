"""Generate due reflections. Run hourly with Heroku Scheduler or another trusted scheduler."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_engine
from .models import Relationship, RelationshipSummary, User
from .reflections import GenerateInput, PeriodType, create_or_update_reflection, period_bounds


def due_periods(local_now: datetime) -> list[tuple[PeriodType, date]]:
    if local_now.hour < 3:
        return []
    yesterday = local_now.date() - timedelta(days=1)
    due: list[tuple[PeriodType, date]] = [('daily', yesterday)]
    if local_now.weekday() == 0:
        due.append(('weekly', yesterday))
    if local_now.day == 1:
        due.append(('monthly', yesterday))
    if local_now.month == 1 and local_now.day == 1:
        due.append(('yearly', yesterday))
    return due


def already_generated(db: Session, user_id, period_type: PeriodType, anchor: date) -> bool:
    start, end = period_bounds(period_type, anchor)
    return db.scalar(select(RelationshipSummary.id).join(Relationship).where(
        Relationship.owner_id == user_id, RelationshipSummary.period_type == period_type,
        RelationshipSummary.period_start == start, RelationshipSummary.period_end == end)) is not None


def run():
    from .reminder_jobs import run as run_reminders
    try:
        run_reminders()
    except Exception:
        print('Reminder job failed; continuing with AI reflections')
    settings = get_settings()
    if not settings.openai_api_key:
        print('AI reflections skipped: OPENAI_API_KEY is not configured')
        return
    generated = failed = 0
    with Session(get_engine()) as db:
        user_ids = db.scalars(select(User.id).where(User.ai_analysis_enabled.is_(True))).all()
        for user_id in user_ids:
            user = db.get(User, user_id)
            local_now = datetime.now(timezone.utc).astimezone(ZoneInfo(user.ai_timezone))
            for period_type, anchor in due_periods(local_now):
                if already_generated(db, user_id, period_type, anchor):
                    continue
                try:
                    create_or_update_reflection(GenerateInput(period_type=period_type, anchor_date=anchor), user, db, settings)
                    generated += 1
                except Exception:
                    db.rollback()
                    failed += 1
    print(f'AI reflection job complete: generated={generated} failed={failed}')


if __name__ == '__main__':
    run()
