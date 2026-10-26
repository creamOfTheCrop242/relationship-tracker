from datetime import date, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .db import get_db
from .journal import current_user, private_request
from .models import Event, Relationship, RelationshipNeed, User


router = APIRouter(prefix='/api', dependencies=[Depends(private_request)])
DASHBOARD_CATEGORIES = ('intimacy', 'kindness', 'conflict', 'outing', 'alcohol', 'childcare')


class DashboardEvent(BaseModel):
    id: UUID
    category: str
    description: str
    occurred_at: datetime
    person: str | None


class DashboardNeed(BaseModel):
    id: UUID
    name: str
    person: Literal['me', 'partner']
    importance: Literal['low', 'medium', 'high']
    latest_status: Literal['met', 'partly_met', 'not_met'] | None
    latest_satisfaction: int | None
    latest_update_on: date | None
    low_satisfaction: bool
    stale: bool
    trend: Literal['improving', 'declining', 'steady', 'not_enough_data']


class DashboardOutput(BaseModel):
    latest_events: dict[str, DashboardEvent | None]
    latest_upset: DashboardEvent | None
    recent_events: list[DashboardEvent]
    needs: list[DashboardNeed]


def event_output(row: Event | None) -> DashboardEvent | None:
    if row is None:
        return None
    return DashboardEvent.model_validate(row, from_attributes=True)


def need_output(row: RelationshipNeed, stale_before: date) -> DashboardNeed:
    updates = row.updates
    latest = updates[0] if updates else None
    if len(updates) >= 4:
        recent_average = sum(update.satisfaction for update in updates[:2]) / 2
        previous_average = sum(update.satisfaction for update in updates[2:4]) / 2
        difference = recent_average - previous_average
        trend = 'improving' if difference >= .5 else 'declining' if difference <= -.5 else 'steady'
    else:
        trend = 'not_enough_data'
    return DashboardNeed(
        id=row.id, name=row.name, person=row.person, importance=row.importance,
        latest_status=latest.status if latest else None,
        latest_satisfaction=latest.satisfaction if latest else None,
        latest_update_on=latest.occurred_on if latest else None,
        low_satisfaction=bool(latest and latest.satisfaction <= 2),
        stale=latest is None or latest.occurred_on < stale_before,
        trend=trend,
    )


@router.get('/dashboard', response_model=DashboardOutput)
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner = Relationship.owner_id == user.id
    ranked_events = select(
        Event.id.label('event_id'),
        func.row_number().over(partition_by=Event.category,
                               order_by=(Event.occurred_at.desc(), Event.id.desc())).label('position'),
    ).join(Relationship).where(owner, Event.category.in_(DASHBOARD_CATEGORIES)).subquery()
    latest_rows = db.scalars(
        select(Event).join(ranked_events, ranked_events.c.event_id == Event.id)
        .where(ranked_events.c.position == 1))
    latest = {category: None for category in DASHBOARD_CATEGORIES}
    for row in latest_rows:
        latest[row.category] = event_output(row)

    latest_upset_row = db.scalar(
        select(Event).join(Relationship).where(
            owner, Event.category == 'conflict', Event.details['upset'].astext.in_(('me', 'partner', 'both')))
        .order_by(Event.occurred_at.desc(), Event.id.desc()).limit(1))
    recent_rows = db.scalars(
        select(Event).join(Relationship).where(owner)
        .order_by(Event.occurred_at.desc(), Event.id.desc()).limit(5)).all()
    need_rows = db.scalars(
        select(RelationshipNeed).join(Relationship).options(selectinload(RelationshipNeed.updates))
        .where(owner, RelationshipNeed.active.is_(True))
        .order_by(RelationshipNeed.created_at.desc())).all()
    need_rows.sort(key=lambda row: {'high': 0, 'medium': 1, 'low': 2}[row.importance])
    stale_before = date.today() - timedelta(days=14)
    return DashboardOutput(
        latest_events=latest, latest_upset=event_output(latest_upset_row),
        recent_events=[event_output(row) for row in recent_rows],
        needs=[need_output(row, stale_before) for row in need_rows],
    )
