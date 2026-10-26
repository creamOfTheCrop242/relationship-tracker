"""Account tables compatible with the original Netlify schema."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
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
    __table_args__ = (Index('events_relationship_time_idx', 'relationship_id', 'occurred_at', 'id'),)
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))
    relationship_id: Mapped[UUID] = mapped_column(ForeignKey('relationships.id', ondelete='CASCADE'))
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updates: Mapped[list['NeedUpdate']] = relationship(back_populates='need', cascade='all, delete-orphan',
                                                        order_by=lambda: (NeedUpdate.occurred_on.desc(), NeedUpdate.id.desc()))


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
