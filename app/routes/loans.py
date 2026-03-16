from datetime import datetime as dt, date
from typing import Optional
from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Loan, Category
from app.core.ui import render_template

router = APIRouter(prefix="/loans", tags=["Loans"])

@router.get("/")
async def list_loans(request: Request, db: Session = Depends(get_db)):
    user = request.state.user
    loans = (
        db.query(Loan)
        .filter(Loan.owner_id == user.id)
        .order_by(Loan.start_date.desc())
        .all()
    )
    
    # Calculate totals
    total_amount = sum(loan.amount for loan in loans)
    total_monthly = sum(loan.monthly_payment for loan in loans)
    active_loans = [loan for loan in loans if loan.status == "active"]
    
    categories = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id == None)).all()
    
    from app.services.debt import calculate_monthly_totals
    stats = calculate_monthly_totals(db, user_id=user.id)

    return render_template(
        "loans/list.html",
        request,
        {
            "loans": loans,
            "total_amount": total_amount,
            "total_monthly": total_monthly,
            "active_count": len(active_loans),
            "categories": categories,
            **stats
        },
    )

@router.get("/add", response_class=HTMLResponse)
async def add_loan_form(request: Request, db: Session = Depends(get_db)):
    user = request.state.user
    categories = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id is None)).all()
    
    from app.services.debt import calculate_monthly_totals
    stats = calculate_monthly_totals(db, user_id=user.id)
    
    terms_options = [
        {"label": "1 Year", "value": 1},
        {"label": "2 Years", "value": 2},
        {"label": "3 Years", "value": 3},
        {"label": "5 Years", "value": 5},
        {"label": "10 Years", "value": 10},
    ]
    
    return render_template(
        "loans/form.html",
        request,
        {
            "categories": categories,
            "terms_options": terms_options,
            "today": date.today().strftime("%Y-%m-%d"),
            **stats
        },
    )

@router.post("/add")
async def create_loan(
    request: Request,
    description: str = Form(...),
    amount: float = Form(...),
    fix_rate: float = Form(..., alias="interest_rate"),
    terms: int = Form(...),
    category_id: int = Form(...),
    start_date_str: str = Form(..., alias="start_date"),
    db: Session = Depends(get_db),
):
    user = request.state.user
    start_date = dt.strptime(start_date_str, "%Y-%m-%d").date()

    new_loan = Loan(
        description=description,
        amount=amount,
        interest_rate=fix_rate,
        terms_years=terms,
        category_id=category_id,
        start_date=start_date,
        owner_id=user.id,
        status="active"
    )
    
    new_loan.calculate_payment()
    
    db.add(new_loan)
    db.commit()

    return RedirectResponse(url="/loans/", status_code=303)

@router.post("/delete/{loan_id}")
async def delete_loan(request: Request, loan_id: int, db: Session = Depends(get_db)):
    user = request.state.user
    loan = db.query(Loan).filter(Loan.id == loan_id, Loan.owner_id == user.id).first()
    if loan:
        db.delete(loan)
        db.commit()
    return RedirectResponse(url="/loans/", status_code=303)
