from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from pydantic import BaseModel, ConfigDict

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)  # Firebase UID (string)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    financial_logs = relationship("FinancialLog", back_populates="user", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")

# Pydantic Schemas for user serialization
class UserResponse(BaseModel):
    id: str
    name: Optional[str]
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
