from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Integer, Text
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    timezone = Column(String, default="Europe/Moscow")
    digest_time = Column(String, default="21:00")
    is_onboarded = Column(Boolean, default=False)
    role = Column(String, default="owner")  # owner | guest
    is_subscribed = Column(Boolean, default=False)
    trial_start = Column(DateTime, default=datetime.utcnow)
    subscription_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Entry(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="owner")  # owner | guest
    guest_name = Column(String, nullable=True)
    guest_telegram_id = Column(BigInteger, nullable=True)  # ID гостя для уведомления
    raw_text = Column(Text, nullable=True)
    transcription = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    remind_at = Column(DateTime, nullable=True)
    remind_count = Column(Integer, default=0)
    last_reminded_at = Column(DateTime, nullable=True)
    is_done = Column(Boolean, default=False)
    archived_at = Column(DateTime, nullable=True)


class Digest(Base):
    __tablename__ = "digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    date = Column(String, nullable=False)
    content_json = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)


class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    event_type = Column(String, nullable=False)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)