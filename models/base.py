import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String

def utc_now():
    return datetime.now(timezone.utc)

def generate_uuid():
    return str(uuid.uuid4())

class Base(DeclarativeBase):
    pass
