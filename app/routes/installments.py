from fastapi import APIRouter, Depends, Form, Response, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse  # Added for safety
from sqlalchemy.orm import Session, joinedload
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
from fastapi.templating import Jinja2Templates
from typing import Optional

# Initialize router and templates
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Local App Imports
from app.database import get_db
from app.models import Installment, Card, Payee
from app.logic import calculate_monthly_totals, get_monthly_forecast


@router.post("/add-installment")
async def add_installment(
    description: str = Form(...),
    card_id: int = Form(...),
    total_amount: float = Form(...),
    total_months: int = Form(...),
    payee_id: int = Form(...),
    start_period: str = Form(...),
    db: Session = Depends(get_db),
):
    start_date = dt.strptime(start_period, "%Y-%m").date()
    actual_months = max(total_months, 1)
    monthly = total_amount / actual_months

    end_date = start_date + relativedelta(months=actual_months - 1)

    new_item = Installment(
        description=description,
        card_id=card_id,
        total_amount=total_amount,
        monthly_payment=monthly,
        payee_id=payee_id,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(new_item)
    db.commit()
    return Response(headers={"HX-Location": "/records"})


@router.get("/get-list")
async def get_list(request: Request, db: Session = Depends(get_db)):
    records = (
        db.query(Installment)
        .options(joinedload(Installment.card), joinedload(Installment.payee))
        .order_by(Installment.start_date.desc())
        .all()
    )

    stats = calculate_monthly_totals(db)
    return templates.TemplateResponse(
        "partials/list.html",
        {"request": request, "records": records, "total_burn": stats["total_burn"]},
    )


@router.get("/get-payee")
async def get_payee(db: Session = Depends(get_db)):
    payee = db.query(Payee).all()
    # Ensure value="{o.id}" has no extra escaped quotes
    options = '<option value="" disabled selected>Select Payee</option>'
    for o in payee:
        options += f"<option value={o.id}>{o.name}</option>"
    return options


@router.get("/get-cards")
async def get_cards(db: Session = Depends(get_db)):
    cards = db.query(Card).all()
    options = '<option value="" disabled selected>Select Card</option>'
    for c in cards:
        options += f"<option value={c.id}>{c.name}</option>"
    return options


# app/routes/forecast.py (or installments.py)


@router.get("/get-forecast")
async def get_forecast(
    request: Request,
    forecast_period: Optional[str] = Query(None),  # Standardized Optional
    card_id: Optional[str] = Query(None),
    payee_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),  # <--- ADDED Dependency Injection
):
    # 1. Standardize Date Handling
    now_obj = dt.now()

    if not forecast_period or not forecast_period.strip():
        yr, mo = now_obj.year, now_obj.month
    else:
        try:
            yr, mo = map(int, forecast_period.split("-"))
        except (ValueError, AttributeError):
            yr, mo = now_obj.year, now_obj.month

    # 2. Convert Query Strings to Integers for the DB logic
    c_id = int(card_id) if card_id and card_id.strip() and card_id != "None" else None
    p_id = (
        int(payee_id) if payee_id and payee_id.strip() and payee_id != "None" else None
    )

    # 3. Use 'db' from Depends (No SessionLocal or db.close needed)
    data = get_monthly_forecast(db, yr, mo, card_id=c_id, payee_id=p_id)

    return templates.TemplateResponse(
        "partials/forecast.html",
        {
            "request": request,
            "now": now_obj,
            "items": data.get("items", []),
            "total_due": data.get("total_due", 0.0),
            "card_data": data.get("card_data", {}),
            "card_split": data.get("card_data", {}),  # Keeping alias for compatibility
            "month_name": data.get("month_name", "Unknown"),
            "year": yr,
            "month": mo,
        },
    )
