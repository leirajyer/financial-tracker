from datetime import datetime
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
from app.services import debt, cashflow, horizon
from app.services.debt import get_global_updates_fragment
from app.services.debt import calculate_monthly_totals


@router.post("/add-installment")
async def add_installment(
    request: Request,
    description: str = Form(...),
    total_amount: float = Form(...),
    total_months: int = Form(...),
    card_id: int = Form(...),
    category_id: int = Form(None),
    payee_id: int = Form(...),
    start_period: str = Form(...),
    db: Session = Depends(get_db),
):
    # 1. Parse the starting date (e.g., "2026-02")
    start_date = datetime.strptime(start_period, "%Y-%m").date()

    # 2. Logic
    calc_monthly_payment = total_amount / total_months
    end_date = start_date + relativedelta(months=total_months - 1)

    # 3. Save to DB
    new_item = Installment(
        description=description,
        total_amount=total_amount,
        monthly_payment=calc_monthly_payment,
        start_date=start_date,
        end_date=end_date,
        card_id=card_id,
        category_id=category_id,
        payee_id=payee_id,
    )

    db.add(new_item)
    db.commit()

    # 4. Global Update (Nav bar stats + Toast)
    now = datetime.now()
    return HTMLResponse(
        content=get_global_updates_fragment(
            db, now.year, now.month, toast_msg=f"Added {description}!"
        )
    )


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


@router.get("/get-cards")
async def get_cards_options(db: Session = Depends(get_db)):
    cards = db.query(Card).order_by(Card.name).all()
    options = "".join([f'<option value="{c.id}">{c.name}</option>' for c in cards])
    return HTMLResponse(content=options)


@router.get("/get-payee")
async def get_payee_options(db: Session = Depends(get_db)):
    payees = db.query(Payee).order_by(Payee.name).all()
    options = "".join([f'<option value="{p.id}">{p.name}</option>' for p in payees])
    return HTMLResponse(content=options)


# app/routes/forecast.py (or installments.py)


# Updated /get-forecast in installment.py
# installments.py


@router.get("/get-forecast", response_class=HTMLResponse)
async def get_forecast(
    request: Request,
    forecast_period: Optional[str] = Query(None),
    card_id: Optional[str] = Query(None),
    payee_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    # 1. Date Parsing
    now_obj = dt.now()
    yr, mo = now_obj.year, now_obj.month
    if forecast_period and "-" in forecast_period:
        try:
            yr, mo = map(int, forecast_period.split("-"))
        except (ValueError, IndexError):
            pass

    # 2. Convert Filter Strings to Integers
    c_id = int(card_id) if card_id and card_id.strip() and card_id != "None" else None
    p_id = (
        int(payee_id) if payee_id and payee_id.strip() and payee_id != "None" else None
    )

    # 3. Get Filtered Data
    stats = calculate_monthly_totals(db, yr, mo, card_id=c_id, payee_id=p_id)

    # 4. Render main partial
    forecast_html = templates.TemplateResponse(
        "partials/forecast.html",
        {
            "request": request,
            "now": now_obj,
            "year": yr,
            "month": mo,
            **stats,  # Unpack so pending_cards/paid_cards are top-level
        },
    ).body.decode()

    # 5. Sync Navbar with filtered total
    global_updates = get_global_updates_fragment(
        db, yr, mo, card_id=c_id, payee_id=p_id
    )

    return HTMLResponse(content=forecast_html + global_updates)


@router.delete("/delete-installment/{rec_id}", response_class=HTMLResponse)
async def delete_installment(
    request: Request, rec_id: int, db: Session = Depends(get_db)
):
    # 1. Perform the deletion
    item = db.query(Installment).filter(Installment.id == rec_id).first()
    if item:
        db.delete(item)
        db.commit()

    # 2. Re-fetch all records for the refreshed list
    records = (
        db.query(Installment)
        .options(joinedload(Installment.card), joinedload(Installment.payee))
        .order_by(Installment.start_date.desc())
        .all()
    )

    # 3. Calculate current totals for the OOB navbar update
    now = dt.now()
    stats = calculate_monthly_totals(db, now.year, now.month)

    # 4. Render the list partial
    list_html = templates.TemplateResponse(
        "partials/list.html",
        {
            "request": request,
            "records": records,
            **stats,  # Unpacks total_burn for the list view
        },
    ).body.decode()

    # 5. Get Global Navbar/Burnout Updates
    global_html = get_global_updates_fragment(
        db, now.year, now.month, toast_msg="Installment deleted!"
    )

    return HTMLResponse(content=list_html + global_html)
