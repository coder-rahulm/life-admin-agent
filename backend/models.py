"""SQLAlchemy models for Life Admin Agent."""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    DateTime, Boolean, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./life_admin.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    email_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    due_date = Column(String, nullable=True)
    amount = Column(Float, default=0.0)
    category = Column(String, default="reminder")   # bill|deadline|subscription|renewal|reminder
    priority = Column(String, default="P3")          # P1|P2|P3
    priority_score = Column(Float, default=0.0)
    explanation = Column(Text, nullable=True)
    status = Column(String, default="pending")       # pending|done|snoozed
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    source_email_subject = Column(String, nullable=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True)
    service_name = Column(String, nullable=False)
    amount = Column(Float, default=0.0)
    billing_cycle = Column(String, default="monthly")
    last_seen_date = Column(DateTime, default=datetime.utcnow)
    detected_active = Column(Boolean, default=True)
    cancel_score = Column(Float, default=0.0)
    days_since_seen = Column(Integer, default=0)


class EmailRecord(Base):
    __tablename__ = "email_records"

    id = Column(String, primary_key=True)
    gmail_message_id = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    sender = Column(String, nullable=True)
    body_text = Column(Text, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)
    task_count = Column(Integer, default=0)


class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    id = Column(String, primary_key=True)
    action_type = Column(String, nullable=False)   # cancel_subscription|mark_paid|send_notification
    task_id = Column(String, nullable=True)
    payload = Column(Text, nullable=True)           # JSON string
    status = Column(String, default="pending")      # pending|approved|rejected
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def create_tables():
    Base.metadata.create_all(bind=engine)
