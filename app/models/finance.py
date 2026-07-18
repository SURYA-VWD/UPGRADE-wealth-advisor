import uuid
import re
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, String, ForeignKey, Numeric, Float, Integer
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.core.database import Base

# ==========================================
# SQLAlchemy Database Models
# ==========================================

class FinancialLog(Base):
    __tablename__ = "financial_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    month_year = Column(String(7), nullable=False)  # Formatted as strict YYYY-MM

    monthly_salary = Column(Numeric(12, 2), nullable=False)
    monthly_expenses = Column(Numeric(12, 2), nullable=False)
    monthly_savings = Column(Numeric(12, 2), nullable=False)
    projection_years = Column(Integer, nullable=False, default=10)

    # Relationships
    user = relationship("User", back_populates="financial_logs")
    asset_allocation = relationship("AssetAllocation", back_populates="financial_log", uselist=False, cascade="all, delete-orphan")


class AssetAllocation(Base):
    __tablename__ = "asset_allocations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    financial_log_id = Column(String(36), ForeignKey("financial_logs.id", ondelete="CASCADE"), nullable=False, unique=True)

    mutual_funds = Column(Numeric(12, 2), nullable=False, default=0.0)
    stocks = Column(Numeric(12, 2), nullable=False, default=0.0)
    gold_silver = Column(Numeric(12, 2), nullable=False, default=0.0)
    real_estate = Column(Numeric(12, 2), nullable=False, default=0.0)
    others = Column(Numeric(12, 2), nullable=False, default=0.0)
    expected_return_pct = Column(Float, nullable=False, default=0.0)

    # Relationships
    financial_log = relationship("FinancialLog", back_populates="asset_allocation")


# ==========================================
# Pydantic v2 Serialization/Validation Models
# ==========================================

class AssetAllocationBase(BaseModel):
    mutual_funds: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    stocks: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    gold_silver: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    real_estate: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    others: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    expected_return_pct: float = Field(default=0.0, ge=0, le=100)


class AssetAllocationCreate(AssetAllocationBase):
    pass


class AssetAllocationResponse(AssetAllocationBase):
    id: str
    financial_log_id: str

    model_config = ConfigDict(from_attributes=True)


class FinancialLogBase(BaseModel):
    month_year: str = Field(..., description="Date formatted strictly as YYYY-MM")
    monthly_salary: Decimal = Field(..., ge=0, decimal_places=2)
    monthly_expenses: Decimal = Field(..., ge=0, decimal_places=2)
    monthly_savings: Decimal = Field(..., ge=0, decimal_places=2)
    projection_years: int = Field(default=10, ge=1, le=50)

    @field_validator("month_year")
    @classmethod
    def validate_month_year(cls, value: str) -> str:
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", value):
            raise ValueError("month_year must follow the strict format 'YYYY-MM'")
        return value


class FinancialLogCreate(FinancialLogBase):
    asset_allocation: AssetAllocationCreate


class FinancialLogResponse(FinancialLogBase):
    id: str
    user_id: str
    asset_allocation: Optional[AssetAllocationResponse] = None

    model_config = ConfigDict(from_attributes=True)
