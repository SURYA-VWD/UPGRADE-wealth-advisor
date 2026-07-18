import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.orm import relationship
from pydantic import BaseModel, ConfigDict
from app.core.database import Base

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(50), nullable=False)  # e.g., USER_LOGIN, USER_LOGOUT, PROFILE_UPDATE, PLAN_SAVE, CALCULATOR_EXPORT
    description = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    amount_invested = Column(Numeric(12, 2), nullable=True)

    # Relationship
    user = relationship("User", back_populates="activity_logs")


class ActivityLogResponse(BaseModel):
    id: str
    user_id: str
    action_type: str
    description: str
    details_json: Optional[str] = None
    created_at: datetime
    amount_invested: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
