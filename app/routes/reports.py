from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime as dt

from app.database import get_db
from app.models import CashFlow, Category
from app.services.debt import calculate_monthly_totals
from app.core.ui import render_template

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/")
async def reports_page(
    request: Request,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None),  # YYYY-MM
    tx_type: Optional[str] = Query(None, alias="type"),
):
    user = request.state.user
    from sqlalchemy import extract

    query = db.query(CashFlow).filter(CashFlow.owner_id == user.id)

    if period and period.strip():
        try:
            y, m = map(int, period.split("-"))
            query = query.filter(
                extract("year", CashFlow.date) == y,
                extract("month", CashFlow.date) == m,
            )
        except Exception:
            pass

    if tx_type and tx_type.strip():
        query = query.filter(CashFlow.type == tx_type)

    transactions = query.order_by(CashFlow.date.desc()).all()

    # Build category breakdown
    category_totals: dict[str, dict] = {}
    uncategorized_total = 0.0

    for tx in transactions:
        if tx.category:
            key = tx.category.name
            if key not in category_totals:
                category_totals[key] = {
                    "name": tx.category.name,
                    "color": tx.category.color,
                    "total": 0.0,
                    "count": 0,
                }
            category_totals[key]["total"] += tx.amount
            category_totals[key]["count"] += 1
        else:
            uncategorized_total += tx.amount

    if uncategorized_total > 0:
        category_totals["Uncategorized"] = {
            "name": "Uncategorized",
            "color": "#94a3b8",
            "total": uncategorized_total,
            "count": sum(1 for t in transactions if not t.category),
        }

    grand_total = sum(v["total"] for v in category_totals.values())

    # Add percentage to each category
    breakdown = []
    for item in sorted(category_totals.values(), key=lambda x: x["total"], reverse=True):
        item["percentage"] = round((item["total"] / grand_total * 100), 1) if grand_total > 0 else 0
        breakdown.append(item)

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    net_balance = total_income - total_expense

    stats = calculate_monthly_totals(db, user_id=user.id)

    # Month name for display
    month_label = None
    if period and period.strip():
        try:
            month_label = dt.strptime(period, "%Y-%m").strftime("%B %Y")
        except Exception:
            pass

    return render_template(
        "reports.html",
        request,
        {
            "breakdown": breakdown,
            "grand_total": grand_total,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_balance": net_balance,
            "filter_period": period,
            "filter_type": tx_type,
            "month_label": month_label,
            "transaction_count": len(transactions),
            **stats,
        },
    )
