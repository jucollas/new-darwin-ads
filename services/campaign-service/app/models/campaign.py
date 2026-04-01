import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.session import Base


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = {"schema": "campaign_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    user_prompt: Mapped[str]
    status: Mapped[str] = mapped_column(default="draft")
    selected_proposal_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"), onupdate=datetime.utcnow)

    proposals: Mapped[list["Proposal"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = {"schema": "campaign_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign_schema.campaigns.id", ondelete="CASCADE"))
    copy_text: Mapped[str]
    script: Mapped[str]
    image_prompt: Mapped[str]
    target_audience: Mapped[dict] = mapped_column(JSON)
    cta_type: Mapped[str] = mapped_column(default="whatsapp_chat")
    whatsapp_number: Mapped[str | None] = mapped_column(default=None)
    is_selected: Mapped[bool] = mapped_column(default=False)
    is_edited: Mapped[bool] = mapped_column(default=False)
    image_url: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    campaign: Mapped["Campaign"] = relationship(back_populates="proposals")
