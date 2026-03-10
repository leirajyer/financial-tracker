from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime as dt
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.models import CashFlow, Category  # Note the modular import

router = APIRouter(prefix="/cashflow", tags=["cashflow"])

templates = Jinja2Templates(directory="templates")


@router.get("/")
async def show_all_cashflow(request: Request, db: Session = Depends(get_db)):
    transactions = db.query(CashFlow).order_by(CashFlow.date.desc()).all()
    # You MUST fetch categories here for the edit modal to work
    categories = db.query(Category).all()

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    net_balance = total_income - total_expense

    return templates.TemplateResponse(
        "cashflow/full.html",
        {
            "request": request,
            "transactions": transactions,
            "categories": categories,  # Pass it to the template
            "total_income": total_income,
            "total_expense": total_expense,
            "net_balance": net_balance,
        },
    )


@router.get("/add")
async def add_cashflow_form(request: Request, db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    # Ensure this is exactly YYYY-MM-DD
    current_date = date.today().strftime("%Y-%m-%d")

    return templates.TemplateResponse(
        "cashflow/form.html",
        {"request": request, "categories": categories, "today": current_date},
    )


@router.post("/add")
async def create_cashflow(
    description: str = Form(...),
    amount: float = Form(...),
    transaction_type: str = Form(..., alias="type"),  # Use alias to match HTML 'type'
    category_id: int = Form(None),
    date_str: str = Form(None, alias="date"),
    db: Session = Depends(get_db),
):
    # 1. Parse the date safely
    try:
        entry_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        entry_date = date.today()

    # 2. Create the entry
    # Match your model columns: description, amount, type, category_id, date
    new_entry = CashFlow(
        description=description,
        amount=amount,
        type=transaction_type,  # Fixed: using the variable from arguments
        category_id=category_id if category_id else None,
        date=entry_date,
    )

    db.add(new_entry)
    db.commit()

    return RedirectResponse(url="/", status_code=303)


@router.post("/edit/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    description: str = Form(...),
    amount: float = Form(...),
    category_id: int = Form(...),
    transaction_type: str = Form(..., alias="transaction_type"),
    db: Session = Depends(get_db),
):
    # Change 'Transaction' to 'CashFlow'
    tx = db.query(CashFlow).filter(CashFlow.id == transaction_id).first()

    if not tx:
        return RedirectResponse(url="/cashflow/?error=not_found", status_code=303)

    tx.description = description
    tx.amount = abs(amount)
    tx.category_id = category_id
    tx.type = transaction_type

    db.commit()
    return RedirectResponse(url="/cashflow/", status_code=303)


@router.post("/delete/{transaction_id}")
async def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    # Query using the correct model name 'CashFlow'
    tx = db.query(CashFlow).filter(CashFlow.id == transaction_id).first()

    if not tx:
        return RedirectResponse(url="/cashflow/?error=not_found", status_code=303)

    db.delete(tx)
    db.commit()

    return RedirectResponse(url="/cashflow/", status_code=303)
