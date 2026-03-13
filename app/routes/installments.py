from datetime import datetime as dt
from typing import Optional
from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from dateutil.relativedelta import relativedelta

from app.database import get_db
from app.models import Installment, Card, Payee, Category
from app.services.debt import calculate_monthly_totals, get_global_updates_fragment
from app.core.ui import templates

router = APIRouter(prefix="/installments", tags=["Installments"])


@router.get("/")
async def list_all_installments(request: Request, db: Session = Depends(get_db)):
    user = request.state.user
    installments = (
        db.query(Installment)
        .filter(Installment.owner_id == user.id)
        .options(joinedload(Installment.card))
        .order_by(Installment.start_date.desc())
        .all()
    )

    stats = calculate_monthly_totals(db, user_id=user.id)
    total_remaining = stats["total_remaining_debt"]
    total_due = stats["total_due"]
    active_count = len([i for i in installments if i.status == "active"])

    cards = db.query(Card).filter(Card.owner_id == user.id).order_by(Card.name).all()
    payees = db.query(Payee).filter(or_(Payee.owner_id == user.id, Payee.owner_id == None)).order_by(Payee.name).all()
    categories = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id == None)).all()

    from app.core.ui import render_template
    return render_template(
        "installments/full.html",
        request,
        {
            "installments": installments,
            "total_remaining": total_remaining,
            "total_due": total_due,
            "active_count": active_count,
            "cards": cards,
            "categories": categories,
            "payees": payees,
        },
    )


@router.get("/add", response_class=HTMLResponse)
async def add_installment_form(request: Request, db: Session = Depends(get_db)):
    user = request.state.user
    cards = db.query(Card).filter(Card.owner_id == user.id).order_by(Card.name).all()
    payees = db.query(Payee).filter(or_(Payee.owner_id == user.id, Payee.owner_id == None)).order_by(Payee.name).all()
    categories = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id == None)).all()
    
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
    from app.core.ui import render_template
    return render_template(
        "installments/form.html",
        request,
        {
            "cards": cards,
            "payees": payees,
            "categories": categories,
            "payment_terms": payment_terms,
            "today_month": dt.now().strftime("%Y-%m"),
        },
    )


@router.get("/list", response_class=HTMLResponse)
async def get_installments_list(request: Request, db: Session = Depends(get_db)):
    user = request.state.user
    records = (
        db.query(Installment)
        .filter(Installment.owner_id == user.id)
        .options(joinedload(Installment.card), joinedload(Installment.payee))
        .order_by(Installment.start_date.desc())
        .all()
    )
    stats = calculate_monthly_totals(db, user_id=user.id)

    from app.core.ui import render_template
    return render_template(
        "partials/list.html",
        request,
        {"records": records, "total_burn": stats["total_burn"]},
    )


@router.post("/add")
async def create_installment(
    request: Request,
    description: str = Form(..., alias="item_name"),
    total_amount: float = Form(...),
    interest_rate: float = Form(0.0, alias="interest_rate"),
    total_months: int = Form(..., alias="months"),
    card_id: int = Form(...),
    payee_id: int = Form(...),
    category_id: int = Form(...),
    start_period: str = Form(..., alias="start_date_str"),
    db: Session = Depends(get_db),
):
    user = request.state.user
    start_date = dt.strptime(start_period, "%Y-%m").date()

    total_interest_amt = total_amount * (interest_rate / 100) * total_months
    monthly_payment = (total_amount + total_interest_amt) / total_months

    new_item = Installment(
        description=description,
        total_amount=total_amount,
        interest_rate=interest_rate,
        monthly_payment=monthly_payment,
        payment_terms=total_months,
        start_date=start_date,
        card_id=card_id,
        payee_id=payee_id,
        category_id=category_id,
        status="active",
        owner_id=user.id
    )

    db.add(new_item)
    db.commit()

    return RedirectResponse(url="/installments/", status_code=303)


@router.delete("/{rec_id}", response_class=HTMLResponse)
async def delete_installment_htmx(
    request: Request, rec_id: int, db: Session = Depends(get_db)
):
    user = request.state.user
    item = db.query(Installment).filter(Installment.id == rec_id, Installment.owner_id == user.id).first()
    if item:
        db.delete(item)
        db.commit()

    now = dt.now()
    return get_global_updates_fragment(
        db, now.year, now.month, toast_msg="Installment removed.", user_id=user.id
    )


@router.get("/options/cards")
async def get_card_options(request: Request, db: Session = Depends(get_db)):
    user = request.state.user
    cards = db.query(Card).filter(Card.owner_id == user.id).order_by(Card.name).all()
    return HTMLResponse(
        "".join([f'<option value="{c.id}">{c.name}</option>' for c in cards])
    )


@router.post("/edit/{installment_id}")
async def update_installment(
    request: Request,
    installment_id: int,
    description: str = Form(..., alias="item_name"),
    card_id: int = Form(...),
    category_id: int = Form(...),
    payee_id: int = Form(...),
    total_amount: float = Form(...),
    months: int = Form(...),
    interest_rate: float = Form(0.0),
    start_date_str: str = Form(...),
    db: Session = Depends(get_db),
):
    user = request.state.user
    inst = db.query(Installment).filter(Installment.id == installment_id, Installment.owner_id == user.id).first()

    if not inst:
        return RedirectResponse(url="/installments/?error=not_found", status_code=303)

    inst.description = description
    inst.card_id = card_id
    inst.category_id = category_id
    inst.payee_id = payee_id
    inst.total_amount = total_amount
    inst.payment_terms = months
    inst.interest_rate = interest_rate
    inst.monthly_payment = (total_amount + interest_rate) / months
    inst.start_date = dt.strptime(start_date_str, "%Y-%m").date()

    db.commit()
    return RedirectResponse(url="/installments/", status_code=303)


@router.post("/delete/{installment_id}")
async def delete_installment_redirect(request: Request, installment_id: int, db: Session = Depends(get_db)):
    user = request.state.user
    inst = db.query(Installment).filter(Installment.id == installment_id, Installment.owner_id == user.id).first()

    if not inst:
        return RedirectResponse(url="/installments/?error=not_found", status_code=303)

    db.delete(inst)
    db.commit()

    return RedirectResponse(url="/installments/", status_code=303)
