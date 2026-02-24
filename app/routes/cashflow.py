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
    # 1. Fetch all transactions (newest first)
    transactions = db.query(CashFlow).order_by(CashFlow.date.desc()).all()

    # 2. Calculate Totals
    # We filter by type to get the sum of income and expenses separately
    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")

    # 3. Calculate the Net Balance
    net_balance = total_income - total_expense

    return templates.TemplateResponse(
        "cashflow/full.html",
        {
            "request": request,
            "transactions": transactions,
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
    type: str = Form(...),  # 'income' or 'expense'
    category_id: int = Form(None),
    date_str: str = Form(alias="date"),  # Matches name="date" in HTML
    db: Session = Depends(get_db),
):
    # Convert string date from form to Python date object
    entry_date = date.fromisoformat(date_str) if date_str else date.today()

    new_entry = CashFlow(
        description=description,
        amount=amount,
        type=type,
        category_id=category_id if category_id else None,
        date=entry_date,
    )

    db.add(new_entry)
    db.commit()

    # Redirect to homepage (index) to see the updated "Recent Activity"
    return RedirectResponse(url="/", status_code=303)
