from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, User, Entry, Digest, Analytics
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)


# ── USERS ──────────────────────────────────────────────
def get_or_create_user(user_id, username=None, first_name=None):
    with Session() as session:
        user = session.get(User, user_id)
        if not user:
            user = User(
                user_id=user_id,
                username=username.lower() if username else None,
                first_name=first_name,
                trial_start=datetime.utcnow()
            )
            session.add(user)
            session.commit()
        else:
            # Всегда обновляем данные из Telegram
            if username:
                user.username = username.lower()
            if first_name:
                user.first_name = first_name
            session.commit()
        session.refresh(user)
        return user


def update_user(user_id, **kwargs):
    with Session() as session:
        user = session.get(User, user_id)
        if user:
            for key, value in kwargs.items():
                setattr(user, key, value)
            session.commit()


# ── ENTRIES ────────────────────────────────────────────
def save_entry(user_id, **kwargs):
    with Session() as session:
        entry = Entry(user_id=user_id, **kwargs)
        session.add(entry)
        session.commit()
        return entry.id


def get_entry(entry_id):
    with Session() as session:
        return session.get(Entry, entry_id)


def mark_done(entry_id):
    with Session() as session:
        entry = session.get(Entry, entry_id)
        if entry:
            entry.is_done = True
            session.commit()


def archive_entry(entry_id):
    with Session() as session:
        entry = session.get(Entry, entry_id)
        if entry:
            entry.archived_at = datetime.utcnow()
            session.commit()


def increment_remind_count(entry_id):
    with Session() as session:
        entry = session.get(Entry, entry_id)
        if entry:
            entry.remind_count += 1
            entry.last_reminded_at = datetime.utcnow()
            session.commit()


def get_entries_by_date(user_id, date_str):
    with Session() as session:
        return session.query(Entry).filter(
            Entry.user_id == user_id,
            Entry.created_at >= date_str + " 00:00:00",
            Entry.created_at <= date_str + " 23:59:59",
            Entry.archived_at == None
        ).all()


def get_open_tasks(user_id):
    with Session() as session:
        return session.query(Entry).filter(
            Entry.user_id == user_id,
            Entry.category == "task",
            Entry.is_done == False,
            Entry.archived_at == None
        ).all()


# ── DIGESTS ────────────────────────────────────────────
def save_digest(user_id, date, content_json):
    with Session() as session:
        digest = Digest(user_id=user_id, date=date, content_json=content_json)
        session.add(digest)
        session.commit()


def get_all_owner_users():
    """Все активные пользователи с ролью owner для рассылки сводок"""
    with Session() as session:
        return session.query(User).filter(
            User.is_onboarded == True,
            User.role == "owner"
        ).all()


def get_user_by_username(username: str):
    """Найти пользователя по username"""
    with Session() as session:
        return session.query(User).filter(
            User.username == username.lower().lstrip("@")
        ).first()


def get_all_pending_reminders():
    """Все незакрытые задачи с remind_at для восстановления после перезапуска"""
    with Session() as session:
        return session.query(Entry).filter(
            Entry.remind_at != None,
            Entry.is_done == False,
            Entry.archived_at == None
        ).all()


def update_entry_remind_at(entry_id, remind_at):
    with Session() as session:
        entry = session.get(Entry, entry_id)
        if entry:
            entry.remind_at = remind_at
            session.commit()