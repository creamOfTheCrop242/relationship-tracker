from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import SESSION_COOKIE, STATE_COOKIE
from .db import get_db
from .journal import current_user, private_request
from .models import (AuthAccount, Event, NeedRequest, NeedUpdate, Relationship, RelationshipNeed,
                     PersonProfile, RelationshipSummary, RelationshipTask, User)


router = APIRouter(prefix='/api/account', dependencies=[Depends(private_request)])


class DeleteAccountInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmation: Literal['DELETE']


def row_dict(row) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


@router.get('/export')
def export_account(user: User = Depends(current_user), db: Session = Depends(get_db)):
    providers = db.scalars(select(AuthAccount).where(AuthAccount.user_id == user.id)
                           .order_by(AuthAccount.created_at, AuthAccount.id)).all()
    relationship = db.scalar(select(Relationship).where(Relationship.owner_id == user.id))
    relationship_data = None
    if relationship:
        events = db.scalars(select(Event).where(Event.relationship_id == relationship.id)
                            .order_by(Event.occurred_at, Event.id)).all()
        needs = db.scalars(select(RelationshipNeed).where(RelationshipNeed.relationship_id == relationship.id)
                           .order_by(RelationshipNeed.created_at, RelationshipNeed.id)).all()
        updates = db.scalars(select(NeedUpdate).join(RelationshipNeed).where(
            RelationshipNeed.relationship_id == relationship.id)
            .order_by(NeedUpdate.occurred_on, NeedUpdate.id)).all()
        updates_by_need: dict = {need.id: [] for need in needs}
        for update in updates:
            updates_by_need.setdefault(update.need_id, []).append(row_dict(update))
        requests = db.scalars(select(NeedRequest).join(RelationshipNeed).where(
            RelationshipNeed.relationship_id == relationship.id)
            .order_by(NeedRequest.created_at, NeedRequest.id)).all()
        requests_by_need: dict = {need.id: [] for need in needs}
        for request in requests:
            requests_by_need.setdefault(request.need_id, []).append(row_dict(request))
        summaries = db.scalars(select(RelationshipSummary).where(
            RelationshipSummary.relationship_id == relationship.id)
            .order_by(RelationshipSummary.period_start, RelationshipSummary.id)).all()
        tasks = db.scalars(select(RelationshipTask).where(RelationshipTask.relationship_id == relationship.id)
                           .order_by(RelationshipTask.created_at, RelationshipTask.id)).all()
        profiles = db.scalars(select(PersonProfile).where(PersonProfile.relationship_id == relationship.id)
                              .order_by(PersonProfile.person)).all()
        relationship_data = row_dict(relationship) | {
            'events': [row_dict(event) for event in events],
            'needs': [row_dict(need) | {'updates': updates_by_need.get(need.id, []),
                                       'requests': requests_by_need.get(need.id, [])} for need in needs],
            'reflections': [row_dict(summary) for summary in summaries],
            'tasks': [row_dict(task) for task in tasks],
            'profiles': [row_dict(profile) for profile in profiles],
        }
    payload = {
        'export_version': 1,
        'exported_at': datetime.now(timezone.utc),
        'account': row_dict(user) | {
            'connected_providers': [row_dict(provider) for provider in providers],
        },
        'relationship': relationship_data,
    }
    filename = f'so-about-us-export-{datetime.now(timezone.utc).date().isoformat()}.json'
    return JSONResponse(jsonable_encoder(payload), headers={
        'Cache-Control': 'no-store',
        'Content-Disposition': f'attachment; filename="{filename}"',
        'X-Content-Type-Options': 'nosniff',
    })


@router.delete('')
def delete_account(data: DeleteAccountInput, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    db.delete(user)
    db.commit()
    response = JSONResponse({'ok': True}, headers={'Cache-Control': 'no-store'})
    response.delete_cookie(SESSION_COOKIE, path='/')
    response.delete_cookie(STATE_COOKIE, path='/api/auth')
    return response
