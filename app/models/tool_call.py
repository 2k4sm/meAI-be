from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.types import JSON
from app.db.session import Base


class ToolCall(Base):
    __tablename__ = "tool_calls"

    tool_call_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("messages.message_id"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    input_params: Mapped[str | None] = mapped_column(JSON, nullable=True)
    tool_response: Mapped[str | None] = mapped_column(JSON, nullable=True)
    executed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message = relationship("Message", back_populates="tool_call")
