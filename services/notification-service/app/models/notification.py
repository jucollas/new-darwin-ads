import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.session import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "notification_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    type: Mapped[str]
    title: Mapped[str]
    body: Mapped[str | None] = mapped_column(default=None)
    data: Mapped[dict | None] = mapped_column(JSON, default=None)
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
