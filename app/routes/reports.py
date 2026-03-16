from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime as dt

from app.database import get_db
from app.models import CashFlow, Category, Installment
from app.services.debt import calculate_monthly_totals
from app.core.ui import render_template
import calendar
from datetime import date

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/")
async def reports_page(
    request: Request,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None),  # YYYY-MM
    tx_type: Optional[str] = Query(None, alias="type"),
    inst_year: Optional[int] = Query(None),
):
    user = request.state.user
    from sqlalchemy import extract

    today = date.today()
    cur_y, cur_m = today.year, today.month
    if period and isinstance(period, str) and period.strip():
        try:
            y, m = map(int, period.split("-"))
            cur_y, cur_m = y, m
        except (ValueError, AttributeError):
            pass

    # Basic query for the selected month
    query = db.query(CashFlow).filter(
        CashFlow.owner_id == user.id,
        extract("year", CashFlow.date) == cur_y,
        extract("month", CashFlow.date) == cur_m
    )

    transactions = query.order_by(CashFlow.date.desc()).all()

    # Build category breakdown (Expenses only for the pie)
    category_totals: dict[str, dict] = {}
    uncategorized_total = 0.0

    for tx in transactions:
        if tx.type != "expense":
            continue
            
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
            "count": sum(1 for t in transactions if t.type == "expense" and not t.category),
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

    # NEW: Flowchart data (last 12 months)
    from sqlalchemy import func
    flowchart_data = []
    today = date.today()
    for i in range(11, -1, -1):
        m = (today.month - i - 1) % 12 + 1
        y = today.year + (today.month - i - 1) // 12
        
        month_income = db.query(func.sum(CashFlow.amount)).filter(
            CashFlow.owner_id == user.id,
            CashFlow.type == "income",
            extract("year", CashFlow.date) == y,
            extract("month", CashFlow.date) == m,
        ).scalar() or 0.0
        
        month_expense = db.query(func.sum(CashFlow.amount)).filter(
            CashFlow.owner_id == user.id,
            CashFlow.type == "expense",
            extract("year", CashFlow.date) == y,
            extract("month", CashFlow.date) == m,
        ).scalar() or 0.0
        
        flowchart_data.append({
            "label": dt(y, m, 1).strftime("%b %y"),
            "income": round(month_income, 2),
            "expense": round(month_expense, 2)
        })

    # NEW: Installment Report (Yearly filter)
    selected_inst_year = inst_year or today.year
    installment_report_data = []
    installments = db.query(Installment).filter(Installment.owner_id == user.id).all()
    
    for month in range(1, 13):
        target_date = date(selected_inst_year, month, 1)
        monthly_total = sum(
            item.monthly_payment for item in installments
            if item.start_date <= target_date <= item.end_date
        )
        installment_report_data.append({
            "month": calendar.month_name[month],
            "total": round(monthly_total, 2)
        })

    cur_y, cur_m = today.year, today.month
    if period and period.strip():
        try:
            cur_y, cur_m = map(int, period.split("-"))
        except:
            pass
    stats = calculate_monthly_totals(db, year=cur_y, month=cur_m, user_id=user.id)

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
            "flowchart_data": flowchart_data,
            "installment_report_data": installment_report_data,
            "selected_inst_year": selected_inst_year,
            "available_years": range(today.year - 2, today.year + 3), # Simple year range
            **stats,
        },
    )
