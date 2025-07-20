from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.session import Base
from enum import Enum


class ConnectionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    DISCONNECTED = "disconnected"


class UserToolkitConnection(Base):
    __tablename__ = "user_toolkit_connections"

    connection_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=False)
    toolkit_slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    connection_status: Mapped[str] = mapped_column(String(20), default=ConnectionStatus.PENDING, nullable=False)
    connected_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_config_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connection_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="toolkit_connections")

    class Config:
        from_attributes = True 