from fastapi import APIRouter, Request, Depends, Form, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, or_
from datetime import date, datetime as dt
from typing import Optional

from app.database import get_db
from app.models import CashFlow, Category, Installment, Card, CardMonthlyStatus

router = APIRouter(prefix="/cashflow", tags=["cashflow"])

@router.get("/get-installments-by-category/{category_id}")
async def get_installments_by_category(
    request: Request,
    category_id: int,
    db: Session = Depends(get_db)
):
    user = request.state.user
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category or category.name != "Credit Card":
        return Response(content="")

    from app.services.debt import calculate_monthly_totals
    stats = calculate_monthly_totals(db, user_id=user.id)
    
    # We want to show cards that have pending payments
    pending_cards = stats.get("pending_cards", {})
    
    from app.core.ui import templates
    return templates.TemplateResponse(
        "cashflow/partials/card_selector.html",
        {
            "request": request,
            "pending_cards": pending_cards,
        }
    )


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
    
    from app.services.debt import calculate_monthly_totals
    stats = calculate_monthly_totals(db, user_id=user.id)
    
    categories = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id == None)).all()
    cards = db.query(Card).filter(Card.owner_id == user.id).order_by(Card.name).all()
    current_date = date.today().strftime("%Y-%m-%d")

    from app.core.ui import render_template
    return render_template(
        "cashflow/form.html",
        request,
        {"categories": categories, "cards": cards, "today": current_date, **stats},
    )


@router.post("/add")
async def create_cashflow(
    request: Request,
    description: str = Form(...),
    amount: float = Form(...),
    transaction_type: str = Form(..., alias="type"),
    category_id: int = Form(None),
    card_id: Optional[int] = Form(None),
    expense_card_id: Optional[int] = Form(None),
    date_str: str = Form(None, alias="date"),
    db: Session = Depends(get_db),
):
    user = request.state.user
    try:
        entry_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        entry_date = date.today()

    category = db.query(Category).filter(Category.id == category_id).first() if category_id else None
    is_cc_payment = category and category.name == "Credit Card"
    
    # Resolving final card ID based on category
    final_card_id = card_id if is_cc_payment else expense_card_id
    if transaction_type != "expense":
        final_card_id = None

    new_entry = CashFlow(
        description=description,
        amount=amount,
        type=transaction_type,
        category_id=category_id if category_id else None,
        date=entry_date,
        owner_id=user.id,
        card_id=final_card_id
    )

    db.add(new_entry)
    
    # NEW: Automated Credit Card Payment Logic
    if transaction_type == "expense" and is_cc_payment and final_card_id:
            month_year = f"{entry_date.year}-{entry_date.month:02d}"
            
            # Check if status exists
            status_obj = db.query(CardMonthlyStatus).filter(
                CardMonthlyStatus.card_id == card_id,
                CardMonthlyStatus.month_year == month_year
            ).first()
            
            if status_obj:
                status_obj.is_paid = True
                status_obj.paid_at = dt.now()
            else:
                status_obj = CardMonthlyStatus(
                    card_id=card_id,
                    month_year=month_year,
                    is_paid=True,
                    paid_at=dt.now()
                )
                db.add(status_obj)

    db.commit()

    return RedirectResponse(url="/", status_code=303)


@router.post("/edit/{transaction_id}")
async def update_transaction(
    request: Request,
    transaction_id: int,
    description: str = Form(...),
    amount: float = Form(...),
    category_id: int = Form(None),
    card_id: Optional[int] = Form(None),
    expense_card_id: Optional[int] = Form(None),
    transaction_type: str = Form(..., alias="type"),
    db: Session = Depends(get_db),
):
    user = request.state.user
    tx = db.query(CashFlow).filter(CashFlow.id == transaction_id, CashFlow.owner_id == user.id).first()

    if not tx:
        return RedirectResponse(url="/cashflow/?error=not_found", status_code=303)

    category = db.query(Category).filter(Category.id == category_id).first() if category_id else None
    is_cc_payment = category and category.name == "Credit Card"
    
    final_card_id = card_id if is_cc_payment else expense_card_id
    if transaction_type != "expense":
        final_card_id = None

    tx.description = description.strip()
    tx.amount = abs(amount)
    tx.category_id = category_id if category_id else None
    tx.card_id = final_card_id
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
