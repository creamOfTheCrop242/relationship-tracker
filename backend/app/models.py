"""Account tables compatible with the original Netlify schema."""

from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text, Time, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    ai_analysis_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text('false'))
    ai_timezone: Mapped[str] = mapped_column(Text, server_default='UTC')
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text('false'))
    reminder_time: Mapped[time] = mapped_column(Time, server_default='09:00:00')
    ai_suggestion_frequency: Mapped[str] = mapped_column(Text, server_default='weekly')
    completed_task_prompt: Mapped[bool] = mapped_column(Boolean, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuthAccount(Base):
    __tablename__ = "auth_accounts"
    __table_args__ = (Index("auth_accounts_provider_subject_idx", "provider", "provider_subject", unique=True),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    provider_subject: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("sessions_user_id_idx", "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Relationship(Base):
    __tablename__ = 'relationships'
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    partner_name: Mapped[str] = mapped_column(Text, server_default='Partner')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = 'events'
    __table_args__ = (
        Index('events_relationship_time_idx', 'relationship_id', 'occurred_at', 'id'),
        Index('events_need_time_idx', 'need_id', 'occurred_at'),
        Index('events_request_time_idx', 'request_id', 'occurred_at'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    relationship_id: Mapped[UUID] = mapped_column(ForeignKey('relationships.id', ondelete='CASCADE'))
    need_id: Mapped[UUID | None] = mapped_column(ForeignKey('relationship_needs.id', ondelete='SET NULL'))
    request_id: Mapped[UUID | None] = mapped_column(ForeignKey('need_requests.id', ondelete='SET NULL'))
    category: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    person: Mapped[str | None] = mapped_column(Text)
    mood: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RelationshipNeed(Base):
    __tablename__ = 'relationship_needs'
    __table_args__ = (
        Index('relationship_needs_relationship_active_idx', 'relationship_id', 'active', 'created_at'),
        CheckConstraint("person IN ('me', 'partner')", name='relationship_needs_person_check'),
        CheckConstraint("importance IN ('low', 'medium', 'high')", name='relationship_needs_importance_check'),
        CheckConstraint("desired_period IN ('per_day', 'per_week', 'per_month', 'custom', 'as_needed', 'no_target')", name='relationship_needs_period_check'),
        CheckConstraint("confirmed_by_partner IN ('yes', 'no', 'unknown')", name='relationship_needs_confirmation_check'),
        CheckConstraint('desired_amount IS NULL OR desired_amount > 0', name='relationship_needs_amount_check'),
        CheckConstraint('custom_period_days IS NULL OR custom_period_days > 0', name='relationship_needs_custom_days_check'),
        CheckConstraint("(desired_period IN ('per_day', 'per_week', 'per_month', 'custom') AND desired_amount IS NOT NULL) OR (desired_period IN ('as_needed', 'no_target') AND desired_amount IS NULL)", name='relationship_needs_cadence_check'),
        CheckConstraint("(desired_period = 'custom' AND custom_period_days IS NOT NULL) OR (desired_period <> 'custom' AND custom_period_days IS NULL)", name='relationship_needs_custom_period_check'),
        CheckConstraint("person = 'partner' OR confirmed_by_partner = 'unknown'", name='relationship_needs_person_confirmation_check'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    relationship_id: Mapped[UUID] = mapped_column(ForeignKey('relationships.id', ondelete='CASCADE'))
    person: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    why_matters: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[str] = mapped_column(Text)
    desired_amount: Mapped[int | None] = mapped_column(Integer)
    desired_period: Mapped[str] = mapped_column(Text)
    custom_period_days: Mapped[int | None] = mapped_column(Integer)
    confirmed_by_partner: Mapped[str] = mapped_column(Text, server_default='unknown')
    active: Mapped[bool] = mapped_column(Boolean, server_default=text('true'))
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updates: Mapped[list['NeedUpdate']] = relationship(back_populates='need', cascade='all, delete-orphan',
                                                        order_by=lambda: (NeedUpdate.occurred_on.desc(), NeedUpdate.id.desc()))
    requests: Mapped[list['NeedRequest']] = relationship(back_populates='need', cascade='all, delete-orphan',
                                                          order_by=lambda: (NeedRequest.active.desc(), NeedRequest.created_at.desc()))


class NeedUpdate(Base):
    __tablename__ = 'need_updates'
    __table_args__ = (
        Index('need_updates_need_date_idx', 'need_id', 'occurred_on', 'id'),
        CheckConstraint("status IN ('met', 'partly_met', 'not_met')", name='need_updates_status_check'),
        CheckConstraint('satisfaction BETWEEN 1 AND 5', name='need_updates_satisfaction_check'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    need_id: Mapped[UUID] = mapped_column(ForeignKey('relationship_needs.id', ondelete='CASCADE'))
    occurred_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text)
    what_happened: Mapped[str] = mapped_column(Text)
    satisfaction: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    need: Mapped[RelationshipNeed] = relationship(back_populates='updates')


class NeedRequest(Base):
    __tablename__ = 'need_requests'
    __table_args__ = (
        Index('need_requests_need_active_idx', 'need_id', 'active', 'created_at'),
        CheckConstraint("desired_period IN ('per_day', 'per_week', 'per_month', 'custom', 'as_needed', 'no_target')", name='need_requests_period_check'),
        CheckConstraint("confirmed_by_person IN ('yes', 'no', 'unknown')", name='need_requests_confirmation_check'),
        CheckConstraint('desired_amount IS NULL OR desired_amount > 0', name='need_requests_amount_check'),
        CheckConstraint('custom_period_days IS NULL OR custom_period_days > 0', name='need_requests_custom_days_check'),
        CheckConstraint("(desired_period IN ('per_day', 'per_week', 'per_month', 'custom') AND desired_amount IS NOT NULL) OR (desired_period IN ('as_needed', 'no_target') AND desired_amount IS NULL)", name='need_requests_cadence_check'),
        CheckConstraint("(desired_period = 'custom' AND custom_period_days IS NOT NULL) OR (desired_period <> 'custom' AND custom_period_days IS NULL)", name='need_requests_custom_period_check'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    need_id: Mapped[UUID] = mapped_column(ForeignKey('relationship_needs.id', ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    desired_amount: Mapped[int | None] = mapped_column(Integer)
    desired_period: Mapped[str] = mapped_column(Text, server_default='no_target')
    custom_period_days: Mapped[int | None] = mapped_column(Integer)
    confirmed_by_person: Mapped[str] = mapped_column(Text, server_default='unknown')
    active: Mapped[bool] = mapped_column(Boolean, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    need: Mapped[RelationshipNeed] = relationship(back_populates='requests')


class RelationshipSummary(Base):
    __tablename__ = 'relationship_summaries'
    __table_args__ = (
        Index('relationship_summaries_period_idx', 'relationship_id', 'period_type', 'period_start', 'period_end', unique=True),
        CheckConstraint("period_type IN ('daily', 'weekly', 'monthly', 'yearly')", name='relationship_summaries_period_type_check'),
        CheckConstraint("confidence IN ('low', 'medium', 'high')", name='relationship_summaries_confidence_check'),
        CheckConstraint('score IS NULL OR score BETWEEN 0 AND 100', name='relationship_summaries_score_check'),
        CheckConstraint('period_end > period_start', name='relationship_summaries_dates_check'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    relationship_id: Mapped[UUID] = mapped_column(ForeignKey('relationships.id', ondelete='CASCADE'))
    period_type: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    score: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(Text)
    coverage_days: Mapped[int] = mapped_column(Integer)
    total_days: Mapped[int] = mapped_column(Integer)
    events_analyzed: Mapped[int] = mapped_column(Integer)
    need_updates_analyzed: Mapped[int] = mapped_column(Integer)
    data_summary: Mapped[str] = mapped_column(Text)
    positive_factors: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    friction_factors: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    interpretation: Mapped[str] = mapped_column(Text)
    comparison: Mapped[str] = mapped_column(Text)
    unresolved_issues: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    suggested_actions: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    reflection: Mapped[str] = mapped_column(Text)
    limitations: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    response_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RelationshipTask(Base):
    __tablename__ = 'relationship_tasks'
    __table_args__ = (
        Index('relationship_tasks_due_idx', 'relationship_id', 'status', 'due_at'),
        Index('relationship_tasks_request_idx', 'request_id', 'status', 'created_at'),
        CheckConstraint("source IN ('cadence', 'ai', 'manual')", name='relationship_tasks_source_check'),
        CheckConstraint("status IN ('pending', 'completed', 'snoozed', 'dismissed')", name='relationship_tasks_status_check'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    relationship_id: Mapped[UUID] = mapped_column(ForeignKey('relationships.id', ondelete='CASCADE'))
    need_id: Mapped[UUID | None] = mapped_column(ForeignKey('relationship_needs.id', ondelete='SET NULL'))
    request_id: Mapped[UUID | None] = mapped_column(ForeignKey('need_requests.id', ondelete='SET NULL'))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default='pending')
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PushSubscription(Base):
    __tablename__ = 'push_subscriptions'
    __table_args__ = (Index('push_subscriptions_user_idx', 'user_id'),)
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PersonProfile(Base):
    __tablename__ = 'person_profiles'
    __table_args__ = (
        CheckConstraint("person IN ('me', 'partner')", name='person_profiles_person_check'),
        Index('person_profiles_relationship_person_key', 'relationship_id', 'person', unique=True),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    relationship_id: Mapped[UUID] = mapped_column(ForeignKey('relationships.id', ondelete='CASCADE'))
    person: Mapped[str] = mapped_column(Text)
    love_languages: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    hobbies: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    interests: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    goals: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
