from sqlalchemy.orm import Session, joinedload
from app.models import CashFlow


def get_monthly_cashflow(db: Session, year: int, month: int):
    month_str = f"{year}-{month:02d}"

    # We fetch the flows and join the category to get the colors/names
    flows = (
        db.query(CashFlow)
        .options(joinedload(CashFlow.category))
        .filter((CashFlow.is_recurring == True) | (CashFlow.month_year == month_str))
        .all()
    )

    total_income = sum(f.amount for f in flows if f.amount > 0)
    total_expenses = sum(abs(f.amount) for f in flows if f.amount < 0)

    return {
        "items": flows,  # Passing the actual objects so UI can access .category.color
        "total_income": round(total_income, 2),
        "total_other_expenses": round(total_expenses, 2),
        "liquid_cash": round(total_income - total_expenses, 2),
    }
