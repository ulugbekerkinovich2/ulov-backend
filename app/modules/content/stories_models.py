"""Stories module for promotional content."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin, UUIDMixin

class Story(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stories"

    center_id = Column(UUID(as_uuid=True), ForeignKey("service_centers.id", ondelete="CASCADE"), nullable=True)
    title = Column(String(255), nullable=False)
    image_url = Column(String(500), nullable=False)
    content = Column(String(1000), nullable=True)
    discount_label = Column(String(50), nullable=True)
    valid_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
