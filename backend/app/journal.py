from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .auth import SESSION_COOKIE, token_hash
from .config import get_settings
from .db import get_db
from .models import Event, Relationship, User, UserSession


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user = None
    if token:
        user = db.scalar(select(User).join(UserSession, UserSession.user_id == User.id).where(
            UserSession.token_hash == token_hash(token), UserSession.expires_at > datetime.now(timezone.utc)))
    if user is None:
        raise HTTPException(401, 'Please sign in again')
    return user


def private_request(request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    if request.method not in ('GET', 'HEAD') and request.headers.get('origin') != get_settings().frontend_url.rstrip('/'):
        raise HTTPException(403, 'Invalid origin')


router = APIRouter(prefix='/api', dependencies=[Depends(private_request)])


class RelationshipInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    partner_name: str = Field(default='Partner', min_length=1, max_length=100)


class RelationshipOutput(RelationshipInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class DetailModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')


class IntimacyDetails(DetailModel):
    type: Literal['sex', 'kissing', 'cuddling', 'affection', 'emotional_closeness', 'custom'] | None = None
    custom_type: str | None = Field(default=None, max_length=100)
    satisfaction: int | None = Field(default=None, ge=1, le=5)


class KindnessDetails(DetailModel):
    initiated_by: Literal['me', 'partner', 'both'] | None = None
    appreciation: int | None = Field(default=None, ge=1, le=5)


class ConflictDetails(DetailModel):
    upset: Literal['me', 'partner', 'both'] | None = None
    initiated_by: Literal['me', 'partner', 'both'] | None = None
    cause: str | None = Field(default=None, max_length=500)
    resolved: bool | None = None
    intensity: int | None = Field(default=None, ge=1, le=5)


class OutingDetails(DetailModel):
    activity: str | None = Field(default=None, max_length=200)
    attended_by: Literal['me', 'partner', 'both', 'others'] | None = None
    enjoyment: int | None = Field(default=None, ge=1, le=5)


class AlcoholDetails(DetailModel):
    drank: Literal['me', 'partner', 'both'] | None = None
    level: Literal['light', 'moderate', 'heavy'] | None = None
    context: str | None = Field(default=None, max_length=500)


class ChildcareDetails(DetailModel):
    provided_by: Literal['me', 'partner', 'both', 'other'] | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    felt_fair: bool | None = None


class CustomDetails(DetailModel):
    rating: int | None = Field(default=None, ge=1, le=5)


DETAIL_MODELS = {
    'intimacy': IntimacyDetails, 'kindness': KindnessDetails,
    'conflict': ConflictDetails, 'outing': OutingDetails,
    'alcohol': AlcoholDetails, 'childcare': ChildcareDetails,
    'custom': CustomDetails,
}


class EventInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    category: Literal['intimacy', 'kindness', 'conflict', 'outing', 'alcohol', 'childcare', 'custom']
    description: str = Field(min_length=1, max_length=500)
    occurred_at: AwareDatetime
    person: Literal['me', 'partner', 'both', 'neither'] | None = None
    mood: str | None = Field(default=None, max_length=100)
    impact: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=10000)
    details: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_details(self):
        self.details = DETAIL_MODELS[self.category](**self.details).model_dump(exclude_none=True)
        if self.category == 'intimacy' and self.details.get('type') == 'custom' and not self.details.get('custom_type'):
            raise ValueError('Custom intimacy type is required when type is custom')
        return self


class EventOutput(EventInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    relationship_id: UUID
    created_at: datetime
    updated_at: datetime


def ensure_relationship(db: Session, user: User) -> Relationship:
    db.execute(insert(Relationship).values(owner_id=user.id).on_conflict_do_nothing(index_elements=['owner_id']))
    return db.scalar(select(Relationship).where(Relationship.owner_id == user.id))


@router.get('/relationship', response_model=RelationshipOutput | None)
def relationship(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalar(select(Relationship).where(Relationship.owner_id == user.id))


@router.put('/relationship', response_model=RelationshipOutput)
def update_relationship(data: RelationshipInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = ensure_relationship(db, user)
    row.partner_name = data.partner_name
    db.commit()
    db.refresh(row)
    return row


@router.get('/events', response_model=list[EventOutput])
def events(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Event).join(Relationship).where(Relationship.owner_id == user.id)
                      .order_by(Event.occurred_at.desc(), Event.id.desc()).limit(limit).offset(offset)).all()


@router.post('/events', response_model=EventOutput, status_code=201)
def create_event(data: EventInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = Event(relationship_id=ensure_relationship(db, user).id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def owned_event(event_id: UUID, user: User, db: Session) -> Event:
    row = db.scalar(select(Event).join(Relationship).where(Event.id == event_id, Relationship.owner_id == user.id))
    if row is None:
        raise HTTPException(404, 'Entry not found')
    return row


@router.put('/events/{event_id}', response_model=EventOutput)
def update_event(event_id: UUID, data: EventInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_event(event_id, user, db)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete('/events/{event_id}', status_code=204)
def delete_event(event_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned_event(event_id, user, db))
    db.commit()
    return Response(status_code=204, headers={'Cache-Control': 'no-store'})
