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

    return templates.TemplateResponse(
        "installments/full.html",
        {
            "request": request,
            "installments": installments,
            "total_remaining": total_remaining,
            "active_count": active_count,
        },
    )


@router.get("/add", response_class=HTMLResponse)
async def add_installment_form(request: Request, db: Session = Depends(get_db)):
    """Renders the full page form to add a new installment."""
    cards = db.query(Card).order_by(Card.name).all()
    payees = db.query(Payee).order_by(Payee.name).all()
    categories = db.query(Category).all()

    return templates.TemplateResponse(
        "installments/form.html",
        {
            "request": request,
            "cards": cards,
            "payees": payees,
            "categories": categories,
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
    total_months: int = Form(..., alias="months_total"),
    card_id: int = Form(...),
    payee_id: int = Form(...),
    start_period: str = Form(..., alias="start_date"),
    db: Session = Depends(get_db),
):
    # 1. Logic: Parse date and calculate fields
    start_date = dt.strptime(start_period, "%Y-%m").date()
    monthly_payment = total_amount / total_months
    # End date is total_months - 1 from start because start month counts as Month 1
    end_date = start_date + relativedelta(months=total_months - 1)

    # 2. Database Save
    new_item = Installment(
        description=description,
        total_amount=total_amount,
        monthly_payment=monthly_payment,
        months_total=total_months,
        start_date=start_date,
        end_date=end_date,
        card_id=card_id,
        payee_id=payee_id,
        status="active",
    )
    db.add(new_item)
    db.commit()

    # 3. Redirect to dashboard (if standard form) or return HTMX fragment
    # Given your current setup, a redirect is safer for a full-page form
    return RedirectResponse(url="/", status_code=303)


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
