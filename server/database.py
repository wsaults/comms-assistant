#!/usr/bin/env python3
"""
Database layer for Slack Monitor
Uses SQLite for persistent storage with automatic deduplication
"""

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import os

# Database file location
DB_PATH = os.path.expanduser("~/Library/Application Support/slack-monitor")
os.makedirs(DB_PATH, exist_ok=True)
DB_FILE = os.path.join(DB_PATH, "slack_monitor.db")

# SQLAlchemy setup
DATABASE_URL = f"sqlite:///{DB_FILE}"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# =============================================================================
# MODELS
# =============================================================================

class DBMention(Base):
    """Mention record"""
    __tablename__ = "mentions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)
    user = Column(String, nullable=False)
    text = Column(String, nullable=False)  # Full text, no truncation
    is_question = Column(Boolean, default=False)
    responded = Column(Boolean, default=False)
    client_id = Column(String, nullable=False, index=True)
    workspace = Column(String, nullable=False, default="unknown", index=True)  # Slack workspace or Teams org
    created_at = Column(DateTime, default=datetime.now)

    # Unique constraint to prevent duplicates
    __table_args__ = (
        UniqueConstraint('timestamp', 'channel', 'user', 'client_id', name='_mention_unique'),
        Index('idx_timestamp_client', 'timestamp', 'client_id'),
    )


class DBChannelActivity(Base):
    """Channel activity tracking"""
    __tablename__ = "channel_activity"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, nullable=False, index=True)
    message_count = Column(Integer, default=0)
    hour = Column(Integer, nullable=False)  # 0-23
    date = Column(String, nullable=False)  # YYYY-MM-DD
    client_id = Column(String, nullable=False, index=True)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('channel', 'hour', 'date', 'client_id', name='_activity_unique'),
        Index('idx_channel_date', 'channel', 'date'),
    )


class DBClient(Base):
    """Connected client tracking"""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, unique=True, nullable=False, index=True)
    hostname = Column(String)
    last_seen = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    first_seen = Column(DateTime, default=datetime.now)


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)
    print(f"✓ Database initialized at {DB_FILE}")


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, caller must close


# =============================================================================
# CRUD OPERATIONS
# =============================================================================

def add_mention(
    db: Session,
    timestamp: datetime,
    channel: str,
    user: str,
    text: str,
    is_question: bool,
    responded: bool,
    client_id: str,
    workspace: str = "unknown"
) -> Optional[DBMention]:
    """Add mention with deduplication"""
    try:
        mention = DBMention(
            timestamp=timestamp,
            channel=channel,
            user=user,
            text=text,
            is_question=is_question,
            responded=responded,
            client_id=client_id,
            workspace=workspace
        )
        db.add(mention)
        db.commit()
        db.refresh(mention)
        return mention
    except Exception as e:
        db.rollback()
        # Likely duplicate, ignore
        return None


def get_recent_mentions(
    db: Session,
    hours: int = 24,
    client_id: Optional[str] = None,
    limit: int = 1000
) -> List[DBMention]:
    """Get recent mentions"""
    cutoff = datetime.now() - timedelta(hours=hours)
    query = db.query(DBMention).filter(DBMention.timestamp > cutoff)

    if client_id:
        query = query.filter(DBMention.client_id == client_id)

    return query.order_by(DBMention.timestamp.desc()).limit(limit).all()


def get_unread_mentions(
    db: Session,
    client_id: Optional[str] = None
) -> List[DBMention]:
    """Get unread mentions"""
    query = db.query(DBMention).filter(DBMention.responded == False)

    if client_id:
        query = query.filter(DBMention.client_id == client_id)

    return query.order_by(DBMention.timestamp.desc()).all()


def mark_mention_responded(db: Session, mention_id: int):
    """Mark a mention as responded"""
    mention = db.query(DBMention).filter(DBMention.id == mention_id).first()
    if mention:
        mention.responded = True
        db.commit()


def add_channel_activity(
    db: Session,
    channel: str,
    message_count: int,
    hour: int,
    date: str,
    client_id: str
):
    """Add or update channel activity"""
    try:
        activity = db.query(DBChannelActivity).filter(
            DBChannelActivity.channel == channel,
            DBChannelActivity.hour == hour,
            DBChannelActivity.date == date,
            DBChannelActivity.client_id == client_id
        ).first()

        if activity:
            activity.message_count += message_count
            activity.last_updated = datetime.now()
        else:
            activity = DBChannelActivity(
                channel=channel,
                message_count=message_count,
                hour=hour,
                date=date,
                client_id=client_id
            )
            db.add(activity)

        db.commit()
        return activity
    except Exception as e:
        db.rollback()
        print(f"Error adding channel activity: {e}")
        return None


def get_channel_activity(
    db: Session,
    hours: int = 24,
    client_id: Optional[str] = None
) -> List[DBChannelActivity]:
    """Get channel activity"""
    cutoff = datetime.now() - timedelta(hours=hours)
    query = db.query(DBChannelActivity).filter(
        DBChannelActivity.last_updated > cutoff
    )

    if client_id:
        query = query.filter(DBChannelActivity.client_id == client_id)

    return query.all()


def update_client(db: Session, client_id: str, hostname: Optional[str] = None):
    """Update or create client record"""
    client = db.query(DBClient).filter(DBClient.client_id == client_id).first()

    if client:
        client.last_seen = datetime.now()
        if hostname:
            client.hostname = hostname
    else:
        client = DBClient(
            client_id=client_id,
            hostname=hostname
        )
        db.add(client)

    db.commit()
    return client


def get_active_clients(db: Session, minutes: int = 10) -> List[DBClient]:
    """Get recently active clients"""
    cutoff = datetime.now() - timedelta(minutes=minutes)
    return db.query(DBClient).filter(DBClient.last_seen > cutoff).all()


def cleanup_old_data(db: Session, days: int = 7):
    """Remove data older than specified days"""
    cutoff = datetime.now() - timedelta(days=days)

    # Clean mentions
    deleted_mentions = db.query(DBMention).filter(
        DBMention.timestamp < cutoff
    ).delete()

    # Clean channel activity
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    deleted_activity = db.query(DBChannelActivity).filter(
        DBChannelActivity.date < cutoff_date
    ).delete()

    db.commit()

    return {
        "mentions": deleted_mentions,
        "channel_activity": deleted_activity
    }


def get_stats(db: Session) -> Dict:
    """Get database statistics"""
    total_mentions = db.query(DBMention).count()
    unread_mentions = db.query(DBMention).filter(DBMention.responded == False).count()
    total_clients = db.query(DBClient).count()
    active_clients = len(get_active_clients(db))

    # Recent mentions by hour
    cutoff = datetime.now() - timedelta(hours=24)
    recent = db.query(DBMention).filter(DBMention.timestamp > cutoff).count()

    return {
        "total_mentions": total_mentions,
        "unread_mentions": unread_mentions,
        "total_clients": total_clients,
        "active_clients": active_clients,
        "mentions_last_24h": recent
    }


# Initialize database on module import
init_db()
