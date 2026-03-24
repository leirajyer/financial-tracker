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
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Salapi")
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    
    # 1. Fetch Summary Stats and Combined Items
    stats = calculate_monthly_totals(
        db, 
        user_id=user.id, 
        card_id=card_id, 
        payee_id=payee_id,
        category_id=category_id
    )
    
    # 2. Extract specific totals for readability
    loan_total_monthly = stats["loan_total_monthly"]
    loan_unlinked_total = stats["loan_unlinked_total"]
    aggregate_monthly_payment = stats["aggregate_monthly_payment"]
    cashflow_expense_total = stats["cashflow_expense_total"]

    recent_cashflow = (
        db.query(CashFlow)
        .filter(CashFlow.owner_id == user.id)
        .order_by(CashFlow.id.desc())
        .limit(5)
        .all()
    )

    def get_sort_key(item):
        val = getattr(item, "created_at", None) or getattr(item, "start_date", None)
        if hasattr(val, "timestamp"):
            return val.timestamp()
        elif hasattr(val, "toordinal"):
            return float(val.toordinal())
        return 0.0

    active_installments = sorted(stats["items"], key=get_sort_key, reverse=True)[:5]

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

    try:
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
    except Exception as e:
        import traceback
        from fastapi.responses import PlainTextResponse
        error_msg = traceback.format_exc()
        return PlainTextResponse(f"HOMEPAGE CRASH:\n\n{error_msg}", status_code=200)
