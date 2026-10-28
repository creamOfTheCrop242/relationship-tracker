from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db import get_db
from .journal import current_user, ensure_relationship, private_request
from .models import NeedRequest, NeedUpdate, Relationship, RelationshipNeed, User


router = APIRouter(prefix='/api', dependencies=[Depends(private_request)])


class NeedUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    occurred_on: date
    status: Literal['met', 'partly_met', 'not_met']
    what_happened: str = Field(min_length=1, max_length=1000)
    satisfaction: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=10000)


class NeedUpdateOutput(NeedUpdateInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    need_id: UUID
    created_at: datetime
    updated_at: datetime


class NeedInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    person: Literal['me', 'partner']
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    why_matters: str | None = Field(default=None, max_length=2000)
    importance: Literal['low', 'medium', 'high'] = 'medium'
    desired_amount: int | None = Field(default=None, ge=1, le=1000)
    desired_period: Literal['per_day', 'per_week', 'per_month', 'custom', 'as_needed', 'no_target'] = 'no_target'
    custom_period_days: int | None = Field(default=None, ge=1, le=3650)
    confirmed_by_partner: Literal['yes', 'no', 'unknown'] = 'unknown'
    active: bool = True
    reminders_enabled: bool = True

    @model_validator(mode='after')
    def validate_cadence(self):
        targeted = self.desired_period in ('per_day', 'per_week', 'per_month', 'custom')
        if targeted and self.desired_amount is None:
            raise ValueError('Desired amount is required for a cadence')
        if not targeted and self.desired_amount is not None:
            raise ValueError('Desired amount is only allowed for a cadence')
        if self.desired_period == 'custom' and self.custom_period_days is None:
            raise ValueError('Custom period days are required')
        if self.desired_period != 'custom' and self.custom_period_days is not None:
            raise ValueError('Custom period days are only allowed for a custom cadence')
        if self.person == 'me' and self.confirmed_by_partner != 'unknown':
            raise ValueError('Partner confirmation only applies to partner needs')
        return self


class NeedOutput(NeedInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    relationship_id: UUID
    created_at: datetime
    updated_at: datetime
    updates: list[NeedUpdateOutput] = Field(default_factory=list)
    requests: list['NeedRequestOutput'] = Field(default_factory=list)


class NeedRequestInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    desired_amount: int | None = Field(default=None, ge=1, le=1000)
    desired_period: Literal['per_day', 'per_week', 'per_month', 'custom', 'as_needed', 'no_target'] = 'no_target'
    custom_period_days: int | None = Field(default=None, ge=1, le=3650)
    confirmed_by_person: Literal['yes', 'no', 'unknown'] = 'unknown'
    active: bool = True

    @model_validator(mode='after')
    def validate_cadence(self):
        targeted = self.desired_period in ('per_day', 'per_week', 'per_month', 'custom')
        if targeted and self.desired_amount is None:
            raise ValueError('Desired amount is required for a cadence')
        if not targeted and self.desired_amount is not None:
            raise ValueError('Desired amount is only allowed for a cadence')
        if self.desired_period == 'custom' and self.custom_period_days is None:
            raise ValueError('Custom period days are required')
        if self.desired_period != 'custom' and self.custom_period_days is not None:
            raise ValueError('Custom period days are only allowed for a custom cadence')
        return self


class NeedRequestOutput(NeedRequestInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    need_id: UUID
    created_at: datetime
    updated_at: datetime


NeedOutput.model_rebuild()


class ArchiveInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    active: bool


def owned_need(need_id: UUID, user: User, db: Session) -> RelationshipNeed:
    row = db.scalar(select(RelationshipNeed).join(Relationship).options(selectinload(RelationshipNeed.updates), selectinload(RelationshipNeed.requests)).where(
        RelationshipNeed.id == need_id, Relationship.owner_id == user.id))
    if row is None:
        raise HTTPException(404, 'Need not found')
    return row


def owned_request(need_id: UUID, request_id: UUID, user: User, db: Session) -> NeedRequest:
    row = db.scalar(select(NeedRequest).join(RelationshipNeed).join(Relationship).where(
        NeedRequest.id == request_id, NeedRequest.need_id == need_id, Relationship.owner_id == user.id))
    if row is None:
        raise HTTPException(404, 'Request not found')
    return row


def owned_update(need_id: UUID, update_id: UUID, user: User, db: Session) -> NeedUpdate:
    row = db.scalar(select(NeedUpdate).join(RelationshipNeed).join(Relationship).where(
        NeedUpdate.id == update_id, NeedUpdate.need_id == need_id, Relationship.owner_id == user.id))
    if row is None:
        raise HTTPException(404, 'Need update not found')
    return row


@router.get('/needs', response_model=list[NeedOutput])
def needs(include_archived: bool = Query(False), user: User = Depends(current_user), db: Session = Depends(get_db)):
    filters = [Relationship.owner_id == user.id]
    if not include_archived:
        filters.append(RelationshipNeed.active.is_(True))
    return db.scalars(select(RelationshipNeed).join(Relationship).options(selectinload(RelationshipNeed.updates), selectinload(RelationshipNeed.requests))
                      .where(*filters).order_by(RelationshipNeed.active.desc(), RelationshipNeed.created_at.desc())).all()


@router.post('/needs', response_model=NeedOutput, status_code=201)
def create_need(data: NeedInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = RelationshipNeed(relationship_id=ensure_relationship(db, user).id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    row.updates
    row.requests
    return row


@router.put('/needs/{need_id}', response_model=NeedOutput)
def update_need(need_id: UUID, data: NeedInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_need(need_id, user, db)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.patch('/needs/{need_id}/archive', response_model=NeedOutput)
def archive_need(need_id: UUID, data: ArchiveInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_need(need_id, user, db)
    row.active = data.active
    db.commit()
    db.refresh(row)
    return row


@router.post('/needs/{need_id}/updates', response_model=NeedUpdateOutput, status_code=201)
def create_update(need_id: UUID, data: NeedUpdateInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_need(need_id, user, db)
    row = NeedUpdate(need_id=need_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put('/needs/{need_id}/updates/{update_id}', response_model=NeedUpdateOutput)
def update_need_update(need_id: UUID, update_id: UUID, data: NeedUpdateInput,
                       user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_update(need_id, update_id, user, db)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete('/needs/{need_id}/updates/{update_id}', status_code=204)
def delete_need_update(need_id: UUID, update_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned_update(need_id, update_id, user, db))
    db.commit()
    return Response(status_code=204, headers={'Cache-Control': 'no-store'})


@router.post('/needs/{need_id}/requests', response_model=NeedRequestOutput, status_code=201)
def create_request(need_id: UUID, data: NeedRequestInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    need = owned_need(need_id, user, db)
    values = data.model_dump()
    if need.person == 'me':
        values['confirmed_by_person'] = 'unknown'
    row = NeedRequest(need_id=need.id, **values)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put('/needs/{need_id}/requests/{request_id}', response_model=NeedRequestOutput)
def update_request(need_id: UUID, request_id: UUID, data: NeedRequestInput,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    need = owned_need(need_id, user, db)
    row = owned_request(need_id, request_id, user, db)
    values = data.model_dump()
    if need.person == 'me':
        values['confirmed_by_person'] = 'unknown'
    for key, value in values.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.patch('/needs/{need_id}/requests/{request_id}/archive', response_model=NeedRequestOutput)
def archive_request(need_id: UUID, request_id: UUID, data: ArchiveInput,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_request(need_id, request_id, user, db)
    row.active = data.active
    db.commit()
    db.refresh(row)
    return row
