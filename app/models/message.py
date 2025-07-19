from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.db.session import Base


class MessageType(str, enum.Enum):
    HUMAN = "Human"
    AI = "AI"
    SYSTEM = "System"
    TOOL = "Tool"


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.conversation_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)  # Nullable for AI/System messages
    type = Column(Enum(MessageType), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", back_populates="messages")
    tool_call = relationship("ToolCall", back_populates="message", uselist=False, cascade="all, delete-orphan")
