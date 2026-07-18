from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.finance import (
    FinancialLog, 
    AssetAllocation, 
    FinancialLogCreate, 
    FinancialLogResponse
)
from app.services.advisory_engine import run_advisory_analysis

router = APIRouter()

from app.models.activity import ActivityLog, ActivityLogResponse
from pydantic import BaseModel
import json

class CustomActivityCreate(BaseModel):
    action_type: str
    description: str
    details_json: Optional[str] = None
    amount_invested: Optional[float] = None

@router.post("/analyze")
async def analyze_finance(
    payload: FinancialLogCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts financial logs and asset allocation allocations.
    Executes transactionally, committing data and invoking the advisory calculation engine.
    """
    # Query for pre-existing log entries for this user and month
    query = select(FinancialLog).where(
        FinancialLog.user_id == current_user.id,
        FinancialLog.month_year == payload.month_year
    ).options(selectinload(FinancialLog.asset_allocation))
    
    result = await db.execute(query)
    log = result.scalars().first()
    
    is_update = bool(log)
    if log:
        # Update main log metrics
        log.monthly_salary = payload.monthly_salary
        log.monthly_expenses = payload.monthly_expenses
        log.monthly_savings = payload.monthly_savings
        log.projection_years = payload.projection_years
        
        # Update associated asset allocation
        alloc = log.asset_allocation
        if not alloc:
            alloc = AssetAllocation(financial_log_id=log.id)
            db.add(alloc)
            
        alloc.mutual_funds = payload.asset_allocation.mutual_funds
        alloc.stocks = payload.asset_allocation.stocks
        alloc.gold_silver = payload.asset_allocation.gold_silver
        alloc.real_estate = payload.asset_allocation.real_estate
        alloc.others = payload.asset_allocation.others
        alloc.expected_return_pct = payload.asset_allocation.expected_return_pct
    else:
        # Create fresh financial log
        log = FinancialLog(
            user_id=current_user.id,
            month_year=payload.month_year,
            monthly_salary=payload.monthly_salary,
            monthly_expenses=payload.monthly_expenses,
            monthly_savings=payload.monthly_savings,
            projection_years=payload.projection_years
        )
        db.add(log)
        await db.flush()  # Populates log.id for the foreign key reference
        
        # Initialize associated asset allocation
        alloc = AssetAllocation(
            financial_log_id=log.id,
            mutual_funds=payload.asset_allocation.mutual_funds,
            stocks=payload.asset_allocation.stocks,
            gold_silver=payload.asset_allocation.gold_silver,
            real_estate=payload.asset_allocation.real_estate,
            others=payload.asset_allocation.others,
            expected_return_pct=payload.asset_allocation.expected_return_pct
        )
        db.add(alloc)

    # Calculate total monthly investment across asset classes
    total_invested = (
        payload.asset_allocation.mutual_funds +
        payload.asset_allocation.stocks +
        payload.asset_allocation.gold_silver +
        payload.asset_allocation.real_estate +
        payload.asset_allocation.others
    )

    # Log PLAN_SUBMISSION / PLAN_UPDATE activity with invested amount details
    activity_action = "PLAN_UPDATE" if is_update else "PLAN_SUBMISSION"
    activity_desc = f"{'Updated' if is_update else 'Configured'} investment plan for {payload.month_year} — Total Invested: ₹{total_invested:,.2f}/mo (Salary: ₹{payload.monthly_salary:,.2f})."
    activity_details = {
        "month_year": payload.month_year,
        "monthly_salary": float(payload.monthly_salary),
        "monthly_expenses": float(payload.monthly_expenses),
        "total_invested": float(total_invested),
        "mutual_funds": float(payload.asset_allocation.mutual_funds),
        "stocks": float(payload.asset_allocation.stocks),
        "gold_silver": float(payload.asset_allocation.gold_silver),
        "real_estate": float(payload.asset_allocation.real_estate),
        "others": float(payload.asset_allocation.others)
    }

    activity = ActivityLog(
        user_id=current_user.id,
        action_type=activity_action,
        description=activity_desc,
        details_json=json.dumps(activity_details),
        amount_invested=total_invested
    )
    db.add(activity)

    # Commit changes inside database transaction block
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record financial log data: {str(e)}"
        )

    # Perform analysis with the advisory engine
    analysis_results = run_advisory_analysis(
        monthly_salary=payload.monthly_salary,
        monthly_expenses=payload.monthly_expenses,
        monthly_savings=payload.monthly_savings,
        mutual_funds=payload.asset_allocation.mutual_funds,
        stocks=payload.asset_allocation.stocks,
        gold_silver=payload.asset_allocation.gold_silver,
        real_estate=payload.asset_allocation.real_estate,
        others=payload.asset_allocation.others,
        expected_return_pct=payload.asset_allocation.expected_return_pct,
        projection_years=payload.projection_years
    )
    
    # Return metrics + charting points + advisory notifications
    return analysis_results

@router.get("/history", response_model=List[FinancialLogResponse])
async def get_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves all historical financial logs for the authenticated user, sorted chronologically."""
    query = select(FinancialLog).where(
        FinancialLog.user_id == current_user.id
    ).options(selectinload(FinancialLog.asset_allocation)).order_by(FinancialLog.month_year.desc())
    
    result = await db.execute(query)
    logs = result.scalars().all()
    return logs

@router.post("/log_activity", response_model=ActivityLogResponse)
async def create_activity(
    payload: CustomActivityCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Records a custom activity audit log for the account holder."""
    log = ActivityLog(
        user_id=current_user.id,
        action_type=payload.action_type,
        description=payload.description,
        details_json=payload.details_json,
        amount_invested=payload.amount_invested
    )
    db.add(log)
    try:
        await db.commit()
        await db.refresh(log)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record activity log: {str(e)}"
        )
    return log

@router.get("/activities", response_model=List[ActivityLogResponse])
async def get_activities(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves all activity audit logs for the authenticated account holder."""
    query = select(ActivityLog).where(
        ActivityLog.user_id == current_user.id
    ).order_by(ActivityLog.created_at.desc())
    
    result = await db.execute(query)
    activities = result.scalars().all()
    return activities
