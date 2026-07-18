from decimal import Decimal
from typing import Dict, List, Any

def run_advisory_analysis(
    monthly_salary: Decimal,
    monthly_expenses: Decimal,
    monthly_savings: Decimal,
    mutual_funds: Decimal,
    stocks: Decimal,
    gold_silver: Decimal,
    real_estate: Decimal,
    others: Decimal,
    expected_return_pct: float,
    projection_years: int = 10
) -> Dict[str, Any]:
    """
    Executes financial sanity checks, projects compound wealth curves, and generates
    custom, actionable advisory recommendations based on portfolio inputs.
    """
    # 1. Outflow Audit and Savings Rate
    total_investments = mutual_funds + stocks + gold_silver + real_estate + others
    outflow_sum = monthly_expenses + total_investments + monthly_savings
    variance = monthly_salary - outflow_sum
    
    warnings: List[Dict[str, str]] = []
    
    # Check for absolute variance warning
    if abs(variance) > Decimal("0.01"):
        warnings.append({
            "category": "CRITICAL",
            "message": f"Outflow Audit Failure! Monthly salary (₹{monthly_salary}) does not equal total outflows (₹{outflow_sum}). "
                       f"There is an unallocated variance of ₹{variance:+.2f}. Please review your logged allocations."
        })
        
    # Calculate Savings Rate
    if monthly_salary > 0:
        savings_rate = float(((monthly_savings + total_investments) / monthly_salary) * Decimal("100"))
    else:
        savings_rate = 0.0

    # 2. Compound Wealth Engine Projections (Strategy A vs B)
    rate_m = expected_return_pct / 1200.0  # Monthly return rate
    r_m_decimal = Decimal(str(rate_m))
    
    # Base monthly deposit is total investments + monthly savings (non-expense surplus)
    monthly_deposit_a = total_investments + monthly_savings
    monthly_deposit_b = total_investments + monthly_savings
    
    balance_a = Decimal("0.00")
    balance_b = Decimal("0.00")
    
    coordinates_a: List[Dict[str, Any]] = []
    coordinates_b: List[Dict[str, Any]] = []
    
    months_total = projection_years * 12
    
    for month in range(1, months_total + 1):
        # Apply 10% Step-Up to Strategy B monthly contributions at the start of every 12-month block (excluding year 1)
        if month > 1 and (month - 1) % 12 == 0:
            monthly_deposit_b *= Decimal("1.10")
            
        balance_a = balance_a * (Decimal("1.0") + r_m_decimal) + monthly_deposit_a
        balance_b = balance_b * (Decimal("1.0") + r_m_decimal) + monthly_deposit_b
        
        # Capture monthly coordinates for high-fidelity charting
        coordinates_a.append({"month": month, "value": float(round(balance_a, 2))})
        coordinates_b.append({"month": month, "value": float(round(balance_b, 2))})
        
    terminal_a = float(round(balance_a, 2))
    terminal_b = float(round(balance_b, 2))
    terminal_delta = float(round(balance_b - balance_a, 2))

    # 3. Heuristic Advisory Guardrails
    
    # A. Budget Burn (50/30/20 target trims)
    if monthly_salary > 0:
        expense_ratio = monthly_expenses / monthly_salary
    else:
        expense_ratio = Decimal("0.0")
        
    if expense_ratio > Decimal("0.50"):
        excess_amount = monthly_expenses - (monthly_salary * Decimal("0.50"))
        warnings.append({
            "category": "CRITICAL",
            "message": f"Budget Burn Alert! Your monthly expenses constitute {expense_ratio*100:.1f}% of your salary, exceeding the 50% target threshold. "
                       f"Under the 50/30/20 framework, allocate up to 50% for Needs, 30% for Wants, and at least 20% for Savings. "
                       f"We recommend trimming discretionary expenses by ₹{excess_amount:.2f} to restore structural balance."
        })
        
    # B. Liquidity Drag (Cash Drag vs. 5% inflation)
    total_portfolio = total_investments + monthly_savings
    if total_portfolio > 0:
        idle_cash_ratio = monthly_savings / total_portfolio
    else:
        idle_cash_ratio = Decimal("0.0")
        
    if idle_cash_ratio > Decimal("0.20"):
        # Calculate 5-year opportunity cost lost to 5% inflation vs expected returns
        # Inflation purchasing power degradation: S * (1 - 1 / (1.05^5))
        # Growth lost: S * ((1 + r)^5 - 1)
        # Total Opportunity Cost = S * (1 + r)^5 - S / (1.05^5)
        # Let's run it with Python floats for safety in exponentials
        s_float = float(monthly_savings)
        r_annual = expected_return_pct / 100.0
        future_growth = s_float * ((1.0 + r_annual) ** 5)
        inflation_adjusted_value = s_float / (1.05 ** 5)
        opportunity_cost = future_growth - inflation_adjusted_value
        
        # Suggest deployment target to pull idle cash ratio down to 10%
        target_idle = total_portfolio * Decimal("0.10")
        suggested_deployment = monthly_savings - target_idle
        
        warnings.append({
            "category": "OPTIMIZATION",
            "message": f"Liquidity Drag Detected! Idle savings represent {idle_cash_ratio*100:.1f}% of your portfolio. "
                       f"Over 5 years, leaving this surplus uninvested will cost you an estimated ₹{opportunity_cost:.2f} in buying power lost to inflation and missed compounding growth. "
                       f"Action step: Reallocate at least ₹{suggested_deployment:.2f} from cash into productive assets like Mutual Funds or Stocks."
        })
        
    # C. Hedging & Risk Mismatch
    equity_exposure = stocks + mutual_funds
    if expected_return_pct >= 15.0 and equity_exposure == Decimal("0.0"):
        warnings.append({
            "category": "CRITICAL",
            "message": f"Asset-Liability Mismatch! You target a high return threshold of {expected_return_pct}%, but have 0% allocated to high-growth assets (Stocks or Mutual Funds). "
                       f"Reallocate a portion of your monthly savings to equity vehicles to realign your portfolio with your yield targets."
        })
        
    # D. Gold/Silver Cushion
    if gold_silver == Decimal("0.0"):
        gold_buffer_pct = total_investments * Decimal("0.05")
        warnings.append({
            "category": "GROWTH OPPORTUNITY",
            "message": f"Hedging Cushion Recommended! You have no allocation in Gold or Silver. "
                       f"Adding a structural 5% buffer allocation (approx. ₹{gold_buffer_pct:.2f} monthly) to precious metals provides essential downside hedging against systematic market corrections."
        })

    # Add a growth recommendation explaining the step-up opportunity cost
    warnings.append({
        "category": "GROWTH OPPORTUNITY",
        "message": f"Compounding Catalyst: Implementing a compounding 10% Step-Up to your monthly investments (Strategy B) "
                   f"is projected to boost your terminal wealth from ₹{terminal_a:.2f} to ₹{terminal_b:.2f} over {projection_years} years. "
                   f"This simple adjustment unlocks an additional ₹{terminal_delta:.2f} in long-term capital gains."
    })

    return {
        "savings_rate": savings_rate,
        "total_investments": float(total_investments),
        "outflow_sum": float(outflow_sum),
        "variance": float(variance),
        "terminal_wealth_flat": terminal_a,
        "terminal_wealth_stepup": terminal_b,
        "opportunity_cost_delta": terminal_delta,
        "coordinates_flat": coordinates_a,
        "coordinates_stepup": coordinates_b,
        "advice_logs": warnings
    }
