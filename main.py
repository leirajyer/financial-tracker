from fastapi import FastAPI, Request, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime as dt
import alembic.config
import alembic.command

# 1. Standardize your Base import (Use the one from your models package)
from app.database import engine, get_db, SessionLocal
from app.models.base import Base

# 2. IMPORT THE MODELS EXPLICITLY
# This fixes the NameError for CashFlow and Installment in your index function
from app.models import CashFlow, Installment

from app.services.debt import calculate_monthly_totals

# REMOVED top-level metadata creation: it's now in startup_event

from app.routes import (
    installments_router,
    forecast_router,
    settings_router,
    cashflow_router,
    auth_router,
    reports_router,
    loans_router,
)

from starlette.middleware.sessions import SessionMiddleware
from app.core.auth import get_current_user, SECRET_KEY, RequiresLoginException, require_user

from app.core.ui import templates
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

app = FastAPI(title="Salapi")

# Handle proxy headers for HTTPS redirection (critical for Railway/Render)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Required for Google OAuth state tracking
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

@app.exception_handler(RequiresLoginException)
async def requires_login_exception_handler(request: Request, exc: RequiresLoginException):
    return RedirectResponse(url="/login", status_code=303)

# Standardize templates to always include current_user
templates.env.globals["current_user"] = None # Placeholder
templates.env.globals["app_version"] = "1.2.4"


from app.seed import seed_db

@app.on_event("startup")
async def startup_event():
    # Auto-run migrations on startup
    try:
        print("🚀 Running migrations...")
        alembic_cfg = alembic.config.Config("alembic.ini")
        alembic.command.upgrade(alembic_cfg, "head")
        print("✅ Migrations applied successfully!")
    except Exception as e:
        print(f"⚠️ Migration Startup Warning: {e}")

    try:
        seed_db()
    except Exception as e:
        print(f"⚠️ Startup Seed Warning: {e}")


# ... router includes ...
app.include_router(installments_router, dependencies=[Depends(require_user)])
app.include_router(forecast_router, dependencies=[Depends(require_user)])
app.include_router(settings_router, dependencies=[Depends(require_user)])
app.include_router(cashflow_router, dependencies=[Depends(require_user)])
app.include_router(auth_router)
app.include_router(reports_router, dependencies=[Depends(require_user)])
app.include_router(loans_router, dependencies=[Depends(require_user)])


@app.get("/")
async def index(
    request: Request, 
    db: Session = Depends(get_db),
    user=Depends(require_user),
    card_id: Optional[int] = Query(None),
    payee_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
):
    from datetime import date
    from sqlalchemy import extract, func
    from app.models import Loan, Card, Payee, Category
    
    today = date.today()
    cur_y, cur_m = today.year, today.month
    
    # 1. Installment Stats
    stats = calculate_monthly_totals(db, user_id=user.id)
    
    # 2. Cashflow Expense Total for current month
    # We separate regular expenses from credit card payments to avoid double counting in the aggregate
    cc_category = db.query(Category).filter(Category.name == "Credit Card").first()
    cc_cat_id = cc_category.id if cc_category else -1

    all_cashflow_expenses = db.query(CashFlow).filter(
        CashFlow.owner_id == user.id,
        CashFlow.type == "expense",
        extract("year", CashFlow.date) == cur_y,
        extract("month", CashFlow.date) == cur_m
    ).all()

    cashflow_expense_total = sum(cat.amount for cat in all_cashflow_expenses)
    cashflow_cc_payment_total = sum(cat.amount for cat in all_cashflow_expenses if cat.category_id == cc_cat_id)
    cashflow_regular_expense_total = cashflow_expense_total - cashflow_cc_payment_total
    
    # 3. Loan Total for current month
    loans = db.query(Loan).filter(Loan.owner_id == user.id, Loan.status == "active").all()
    loan_total_monthly = 0.0
    target_dt = date(cur_y, cur_m, 1)
    for loan in loans:
        if loan.start_date <= target_dt <= loan.end_date:
            loan_total_monthly += loan.monthly_payment

    # Aggregate Remaining Payment (Remaining Dues = Unpaid Installments + Scheduled Loans + Regular Expenses)
    aggregate_monthly_payment = cashflow_regular_expense_total + stats["total_burn"] + loan_total_monthly
    
    recent_cashflow = (
        db.query(CashFlow)
        .filter(CashFlow.owner_id == user.id)
        .order_by(CashFlow.id.desc())
        .limit(5)
        .all()
    )

    # Filtered Installments
    inst_query = db.query(Installment).filter(Installment.owner_id == user.id, Installment.status == "active")
    if card_id:
        inst_query = inst_query.filter(Installment.card_id == card_id)
    if payee_id:
        inst_query = inst_query.filter(Installment.payee_id == payee_id)
    if category_id:
        inst_query = inst_query.filter(Installment.category_id == category_id)
    
    active_installments = inst_query.all()

    # Dropdowns for filters
    cards = db.query(Card).filter(Card.owner_id == user.id).all()
    payees = db.query(Payee).filter(or_(Payee.owner_id == user.id, Payee.owner_id.is_(None))).order_by(Payee.name).all()
    
    # Deduplicate categories by name, prioritizing user-owned ones
    all_cats = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id.is_(None))).order_by(Category.name).all()
    cat_dict = {}
    for cat in all_cats:
        if cat.name not in cat_dict or cat.owner_id is not None:
            cat_dict[cat.name] = cat
    categories = sorted(cat_dict.values(), key=lambda x: x.name)

    from app.core.ui import render_template
    return render_template(
        "index.html",
        request,
        {
            "recent_cashflow": recent_cashflow,
            "installments": active_installments,
            "cashflow_expense_total": cashflow_expense_total,
            "loan_total_monthly": loan_total_monthly,
            "aggregate_monthly_payment": aggregate_monthly_payment,
            "cards": cards,
            "payees": payees,
            "categories": categories,
            "filter_card": card_id,
            "filter_payee": payee_id,
            "filter_category": category_id,
            "now": dt.now(),
            **stats,
        },
    )
