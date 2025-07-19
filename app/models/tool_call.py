from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base


class ToolCall(Base):
    __tablename__ = "tool_calls"

    tool_call_id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.message_id"), nullable=False)
    tool_name = Column(String(255), nullable=False)
    input_params = Column(JSON, nullable=True)
    tool_response = Column(JSON, nullable=True)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    message = relationship("Message", back_populates="tool_call")
