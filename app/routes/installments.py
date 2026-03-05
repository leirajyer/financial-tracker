from app.models import Category
from datetime import datetime as dt
from typing import Optional
from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from dateutil.relativedelta import relativedelta

from app.database import get_db
from app.models import Installment, Card, Payee, Category
from app.services.debt import calculate_monthly_totals, get_global_updates_fragment
from app.core.ui import templates  # Use shared template engine if available

router = APIRouter(prefix="/installments", tags=["Installments"])


# ==========================================
# 📖 VIEW ROUTES
# ==========================================
@router.get("/")
async def list_all_installments(request: Request, db: Session = Depends(get_db)):
    installments = (
        db.query(Installment)
        .options(joinedload(Installment.card))
        .order_by(Installment.start_date.desc())
        .all()
    )

    # Calculate global credit health
    total_remaining = sum(
        (inst.total_amount - (inst.monthly_payment * inst.get_progress()["current"]))
        for inst in installments
    )
    active_count = len([i for i in installments if i.status == "active"])

    cards = db.query(Card).order_by(Card.name).all()
    payees = db.query(Payee).order_by(Payee.name).all()
    categories = db.query(Category).all()

    return templates.TemplateResponse(
        "installments/full.html",
        {
            "request": request,
            "installments": installments,
            "total_remaining": total_remaining,
            "active_count": active_count,
            "cards": cards,
            "categories": categories,
            "payees": payees,
        },
    )


@router.get("/add", response_class=HTMLResponse)
async def add_installment_form(request: Request, db: Session = Depends(get_db)):
    """Renders the full page form to add a new installment."""
    cards = db.query(Card).order_by(Card.name).all()
    payees = db.query(Payee).order_by(Payee.name).all()
    categories = db.query(Category).all()
    payment_terms = [
        {"label": "Straight", "value": 1},
        {"label": "3 Months", "value": 3},
        {"label": "6 Months", "value": 6},
        {"label": "12 Months (1 year)", "value": 12},
        {"label": "24 Months (2 years)", "value": 24},
        {"label": "36 Months (3 years)", "value": 36},
        {"label": "48 Months (4 years)", "value": 48},
        {"label": "60 Months (5 years)", "value": 60},
    ]
    return templates.TemplateResponse(
        "installments/form.html",
        {
            "request": request,
            "cards": cards,
            "payees": payees,
            "categories": categories,
            "payment_terms": payment_terms,
            "today_month": dt.now().strftime("%Y-%m"),
        },
    )


@router.get("/list", response_class=HTMLResponse)
async def get_installments_list(request: Request, db: Session = Depends(get_db)):
    """HTMX endpoint to get the scrollable list of installments."""
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


# ==========================================
# ⚡ ACTION ROUTES (POST/DELETE)
# ==========================================


@router.post("/add")
async def create_installment(
    description: str = Form(..., alias="item_name"),
    total_amount: float = Form(...),
    # The interest rate sent from the form (defaulting to 0 for 0% promos)
    interest_rate: float = Form(0.0, alias="interest_rate"),
    total_months: int = Form(..., alias="months"),
    card_id: int = Form(...),
    payee_id: int = Form(...),
    category_id: int = Form(...),
    start_period: str = Form(..., alias="start_date_str"),
    db: Session = Depends(get_db),
):
    # 1. Parse date
    start_date = dt.strptime(start_period, "%Y-%m").date()

    # 2. Logic: Monthly Add-on Interest Calculation
    # Formula: Total Interest = Principal * (Monthly Rate / 100) * Number of Months
    total_interest_amt = total_amount * (interest_rate / 100) * total_months
    monthly_payment = (total_amount + total_interest_amt) / total_months

    # End date calculation (Inclusive of start month)
    end_date = start_date + relativedelta(months=total_months - 1)

    # 3. Database Save
    new_item = Installment(
        description=description,
        total_amount=total_amount,
        interest_rate=interest_rate,
        monthly_payment=monthly_payment,
        payment_terms=total_months,
        start_date=start_date,
        end_date=end_date,
        card_id=card_id,
        payee_id=payee_id,
        category_id=category_id,
        status="active",
    )

    db.add(new_item)
    db.commit()

    return RedirectResponse(url="/installments/", status_code=303)


@router.delete("/{rec_id}", response_class=HTMLResponse)
async def delete_installment(
    request: Request, rec_id: int, db: Session = Depends(get_db)
):
    item = db.query(Installment).filter(Installment.id == rec_id).first()
    if item:
        db.delete(item)
        db.commit()

    # Return the HTMX global update to refresh UI state without reload
    now = dt.now()
    return get_global_updates_fragment(
        db, now.year, now.month, toast_msg="Installment removed."
    )


# ==========================================
# 🔍 DATA HELPERS (For HTMX Selects)
# ==========================================


@router.get("/options/cards")
async def get_card_options(db: Session = Depends(get_db)):
    cards = db.query(Card).order_by(Card.name).all()
    return HTMLResponse(
        "".join([f'<option value="{c.id}">{c.name}</option>' for c in cards])
    )


from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from datetime import datetime as dt
from app.models.installment import Installment


@router.post("/edit/{installment_id}")
async def update_installment(
    installment_id: int,
    description: str = Form(..., alias="item_name"),
    card_id: int = Form(...),
    category_id: int = Form(...),
    payee_id: int = Form(...),
    total_amount: float = Form(...),
    months: int = Form(...),
    interest_rate: float = Form(0.0),  # Flat interest amount
    start_date_str: str = Form(...),
    db: Session = Depends(get_db),
):
    inst = db.query(Installment).filter(Installment.id == installment_id).first()

    if not inst:
        return RedirectResponse(url="/installments/?error=not_found", status_code=303)

    # 1. Update Info
    inst.description = description
    inst.card_id = card_id
    inst.category_id = category_id
    inst.payee_id = payee_id
    inst.total_amount = total_amount
    inst.payment_terms = months
    inst.interest_rate = interest_rate

    # 2. Recalculate Monthly Payment (Principal + Flat Interest) / Months
    inst.monthly_payment = (total_amount + interest_rate) / months

    # 3. Update Date (Expects YYYY-MM)
    inst.start_date = dt.strptime(start_date_str, "%Y-%m").date()

    db.commit()
    return RedirectResponse(url="/installments/", status_code=303)


@router.post("/delete/{installment_id}")
async def delete_installment(installment_id: int, db: Session = Depends(get_db)):
    # Fetch the installment record
    inst = db.query(Installment).filter(Installment.id == installment_id).first()

    if not inst:
        return RedirectResponse(url="/installments/?error=not_found", status_code=303)

    db.delete(inst)
    db.commit()

    return RedirectResponse(url="/installments/", status_code=303)
