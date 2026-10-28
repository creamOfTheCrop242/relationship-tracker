from datetime import datetime, time, timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .journal import current_user, ensure_relationship, private_request
from .models import PushSubscription, Relationship, RelationshipTask, User

router = APIRouter(prefix='/api', dependencies=[Depends(private_request)])


class TaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    due_at: datetime
    need_id: UUID | None = None


class TaskOutput(TaskInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    relationship_id: UUID
    request_id: UUID | None
    source: Literal['cadence', 'ai', 'manual']
    status: Literal['pending', 'completed', 'snoozed', 'dismissed']
    snoozed_until: datetime | None
    completed_at: datetime | None
    notified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['complete', 'snooze', 'dismiss', 'reopen']
    until: datetime | None = None


class ReminderSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    reminder_time: time
    ai_suggestion_frequency: Literal['off', 'daily', 'weekly', 'monthly']
    completed_task_prompt: bool
    timezone: str = Field(min_length=1, max_length=100)

    def model_post_init(self, __context):
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError('Unknown timezone') from exc


class PushKeys(BaseModel):
    model_config = ConfigDict(extra='forbid')
    p256dh: str = Field(min_length=1, max_length=1000)
    auth: str = Field(min_length=1, max_length=1000)


class PushSubscriptionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    endpoint: str = Field(min_length=1, max_length=4000)
    keys: PushKeys


def owned_task(task_id: UUID, user: User, db: Session) -> RelationshipTask:
    task = db.scalar(select(RelationshipTask).join(Relationship).where(
        RelationshipTask.id == task_id, Relationship.owner_id == user.id))
    if task is None:
        raise HTTPException(404, 'Task not found')
    return task


@router.get('/tasks', response_model=list[TaskOutput])
def list_tasks(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(RelationshipTask).join(Relationship).where(
        Relationship.owner_id == user.id).order_by(RelationshipTask.due_at, RelationshipTask.created_at)).all()


@router.post('/tasks', response_model=TaskOutput, status_code=201)
def create_task(data: TaskInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    relationship = ensure_relationship(db, user)
    if data.need_id is not None:
        from .models import RelationshipNeed
        owned = db.scalar(select(RelationshipNeed.id).where(
            RelationshipNeed.id == data.need_id, RelationshipNeed.relationship_id == relationship.id))
        if owned is None:
            raise HTTPException(404, 'Need not found')
    task = RelationshipTask(relationship_id=relationship.id, source='manual', **data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put('/tasks/{task_id}', response_model=TaskOutput)
def update_task(task_id: UUID, data: TaskInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(task_id, user, db)
    for key, value in data.model_dump().items():
        setattr(task, key, value)
    task.notified_at = None
    db.commit()
    db.refresh(task)
    return task


@router.post('/tasks/{task_id}/action', response_model=TaskOutput)
def task_action(task_id: UUID, data: TaskAction, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(task_id, user, db)
    now = datetime.now(timezone.utc)
    if data.action == 'complete':
        task.status, task.completed_at, task.snoozed_until = 'completed', now, None
    elif data.action == 'dismiss':
        task.status, task.snoozed_until = 'dismissed', None
    elif data.action == 'reopen':
        task.status, task.completed_at, task.snoozed_until, task.notified_at = 'pending', None, None, None
    else:
        if data.until is None or data.until <= now:
            raise HTTPException(422, 'Snooze time must be in the future')
        task.status, task.snoozed_until, task.notified_at = 'snoozed', data.until, None
    db.commit()
    db.refresh(task)
    return task


@router.get('/reminder-settings', response_model=ReminderSettings)
def reminder_settings(user: User = Depends(current_user)):
    return ReminderSettings(enabled=user.reminders_enabled, reminder_time=user.reminder_time,
                            ai_suggestion_frequency=user.ai_suggestion_frequency,
                            completed_task_prompt=user.completed_task_prompt, timezone=user.ai_timezone)


@router.put('/reminder-settings', response_model=ReminderSettings)
def update_reminder_settings(data: ReminderSettings, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.reminders_enabled = data.enabled
    user.reminder_time = data.reminder_time
    user.ai_suggestion_frequency = data.ai_suggestion_frequency
    user.completed_task_prompt = data.completed_task_prompt
    user.ai_timezone = data.timezone
    db.commit()
    db.refresh(user)
    return data


@router.get('/push/config')
def push_config():
    key = get_settings().vapid_public_key
    return {'enabled': bool(key), 'public_key': key}


@router.post('/push/subscriptions', status_code=201)
def save_push_subscription(data: PushSubscriptionInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == data.endpoint))
    if row is None:
        row = PushSubscription(user_id=user.id, endpoint=data.endpoint,
                               p256dh=data.keys.p256dh, auth=data.keys.auth)
        db.add(row)
    else:
        if row.user_id != user.id:
            raise HTTPException(409, 'Subscription already belongs to another account')
        row.p256dh, row.auth = data.keys.p256dh, data.keys.auth
    db.commit()
    return {'ok': True}


@router.delete('/push/subscriptions')
def delete_push_subscription(endpoint: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(PushSubscription).where(
        PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id))
    if row:
        db.delete(row)
        db.commit()
    return Response(status_code=204)
