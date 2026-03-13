from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, or_
from datetime import date, datetime as dt
from typing import Optional

from app.database import get_db
from app.models import CashFlow, Category

router = APIRouter(prefix="/cashflow", tags=["cashflow"])


@router.get("/")
async def show_all_cashflow(
    request: Request,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None), # YYYY-MM
    category_id: Optional[str] = Query(None),
    tx_type: Optional[str] = Query(None, alias="type")
):
    user = request.state.user
    query = db.query(CashFlow).filter(CashFlow.owner_id == user.id)

    if period and period.strip():
        try:
            y, m = map(int, period.split("-"))
            query = query.filter(extract('year', CashFlow.date) == y, extract('month', CashFlow.date) == m)
        except:
            pass
    
    cat_id_int = None
    if category_id and category_id.strip():
        try:
            cat_id_int = int(category_id)
            query = query.filter(CashFlow.category_id == cat_id_int)
        except:
            pass
    
    if tx_type:
        query = query.filter(CashFlow.type == tx_type)

    transactions = query.order_by(CashFlow.date.desc()).all()
    
    # Categories: show user's categories or global ones (though we should migrate to user-only)
    categories = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id == None)).all()

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    net_balance = total_income - total_expense

    from app.services.debt import calculate_monthly_totals
    stats = calculate_monthly_totals(db, user_id=user.id)

    from app.core.ui import render_template
    return render_template(
        "cashflow/full.html",
        request,
        {
            "transactions": transactions,
            "categories": categories,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_balance": net_balance,
            "filter_period": period,
            "filter_cat": cat_id_int,
            "filter_type": tx_type,
            **stats
        },
    )


@router.get("/add")
async def add_cashflow_form(request: Request, db: Session = Depends(get_db)):
    user = request.state.user
    categories = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id == None)).all()
    current_date = date.today().strftime("%Y-%m-%d")

    from app.core.ui import render_template
    return render_template(
        "cashflow/form.html",
        request,
        {"categories": categories, "today": current_date},
    )


@router.post("/add")
async def create_cashflow(
    request: Request,
    description: str = Form(...),
    amount: float = Form(...),
    transaction_type: str = Form(..., alias="type"),
    category_id: int = Form(None),
    date_str: str = Form(None, alias="date"),
    db: Session = Depends(get_db),
):
    user = request.state.user
    try:
        entry_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        entry_date = date.today()

    new_entry = CashFlow(
        description=description,
        amount=amount,
        type=transaction_type,
        category_id=category_id if category_id else None,
        date=entry_date,
        owner_id=user.id
    )

    db.add(new_entry)
    db.commit()

    return RedirectResponse(url="/", status_code=303)


@router.post("/edit/{transaction_id}")
async def update_transaction(
    request: Request,
    transaction_id: int,
    description: str = Form(...),
    amount: float = Form(...),
    category_id: int = Form(None),
    transaction_type: str = Form(..., alias="type"),
    db: Session = Depends(get_db),
):
    user = request.state.user
    tx = db.query(CashFlow).filter(CashFlow.id == transaction_id, CashFlow.owner_id == user.id).first()

    if not tx:
        return RedirectResponse(url="/cashflow/?error=not_found", status_code=303)

    tx.description = description.strip()
    tx.amount = abs(amount)
    tx.category_id = category_id if category_id else None
    tx.type = transaction_type

    db.commit()
    return RedirectResponse(url="/cashflow/", status_code=303)


@router.post("/delete/{transaction_id}")
async def delete_transaction(request: Request, transaction_id: int, db: Session = Depends(get_db)):
    user = request.state.user
    tx = db.query(CashFlow).filter(CashFlow.id == transaction_id, CashFlow.owner_id == user.id).first()

    if tx:
        db.delete(tx)
        db.commit()

    return RedirectResponse(url="/cashflow/", status_code=303)
