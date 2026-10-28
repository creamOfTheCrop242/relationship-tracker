from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .journal import current_user, ensure_relationship, private_request
from .models import PersonProfile, Relationship, User

router = APIRouter(prefix='/api/profiles', dependencies=[Depends(private_request)])
Person = Literal['me', 'partner']
LoveLanguage = Literal['words_of_affirmation', 'quality_time', 'physical_touch', 'acts_of_service', 'receiving_gifts']


class ProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    love_languages: list[LoveLanguage] = Field(default_factory=list, max_length=5)
    hobbies: list[str] = Field(default_factory=list, max_length=50)
    interests: list[str] = Field(default_factory=list, max_length=50)
    goals: list[str] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator('love_languages', 'hobbies', 'interests', 'goals')
    @classmethod
    def clean_lists(cls, values: list[str]):
        cleaned = []
        for value in values:
            item = value.strip()
            if not item or item in cleaned:
                continue
            if len(item) > 200:
                raise ValueError('Profile items must be 200 characters or fewer')
            cleaned.append(item)
        return cleaned


class ProfileOutput(ProfileInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    relationship_id: UUID
    person: Person
    display_name: str
    created_at: datetime
    updated_at: datetime


def output(row: PersonProfile, relationship: Relationship, user: User) -> ProfileOutput:
    data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    data['display_name'] = (user.display_name or 'You') if row.person == 'me' else relationship.partner_name
    return ProfileOutput.model_validate(data)


def ensure_profiles(db: Session, user: User) -> tuple[Relationship, list[PersonProfile]]:
    relationship = ensure_relationship(db, user)
    rows = list(db.scalars(select(PersonProfile).where(
        PersonProfile.relationship_id == relationship.id).order_by(PersonProfile.person)).all())
    existing = {row.person for row in rows}
    for person in ('me', 'partner'):
        if person not in existing:
            row = PersonProfile(relationship_id=relationship.id, person=person)
            db.add(row)
            rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return relationship, sorted(rows, key=lambda row: 0 if row.person == 'me' else 1)


@router.get('', response_model=list[ProfileOutput])
def profiles(user: User = Depends(current_user), db: Session = Depends(get_db)):
    relationship, rows = ensure_profiles(db, user)
    return [output(row, relationship, user) for row in rows]


@router.put('/{person}', response_model=ProfileOutput)
def update_profile(person: Person, data: ProfileInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    relationship, rows = ensure_profiles(db, user)
    row = next(item for item in rows if item.person == person)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return output(row, relationship, user)
