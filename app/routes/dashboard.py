from fastapi import FastAPI
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse

from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Card, Payee, CashFlow, Installment
from app.services import debt, cashflow, category as category_service


app = FastAPI()
templates = Jinja2Templates(directory="templates")
router = APIRouter()

# ==========================================
# 🏠 DASHBOARD ROUTER (/dashboard)
# ==========================================
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dashboard_router.get("")
async def dashboard_main(request: Request, db: Session = Depends(get_db)):
    # 1. Fetch Monthly Totals (Burn rate, Income vs Expenses)
    stats = debt.calculate_monthly_totals(db)

    # 2. Get ONLY the last 5 cashflow entries for the mini-list
    recent_cashflow = db.query(CashFlow).order_by(CashFlow.date.desc()).limit(5).all()

    # 3. Get Active Installments for the current month
    active_installments = (
        db.query(Installment).filter(Installment.status == "active").all()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "recent_cashflow": recent_cashflow,
            "installments": active_installments,
            "now": datetime.now(),
            **stats,  # Spreads total_burn, total_income, etc., into context
        },
    )


# ==========================================
# 💳 INSTALLMENT ROUTER (/installment)
# ==========================================
installment_router = APIRouter(prefix="/installment", tags=["Installments"])


@installment_router.get("")
async def installment_list(request: Request, db: Session = Depends(get_db)):
    all_installments = (
        db.query(Installment).order_by(Installment.start_date.desc()).all()
    )
    return templates.TemplateResponse(
        "installments_list.html", {"request": request, "installments": all_installments}
    )


@installment_router.get("/add")
async def installment_add_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "installment_add.html",
        {
            "request": request,
            "cards": db.query(Card).all(),
            "payees": db.query(Payee).all(),
            "now": datetime.now(),
        },
    )


@installment_router.delete("/delete/{id}")
async def delete_installment(id: int, db: Session = Depends(get_db)):
    item = db.query(Installment).get(id)
    if item:
        db.delete(item)
        db.commit()
    return HTMLResponse(content="", headers={"HX-Redirect": "/installment"})


# ==========================================
# 💸 CASHFLOW ROUTER (/cashflow)
# ==========================================
cashflow_router = APIRouter(prefix="/cashflow", tags=["Cashflow"])


@cashflow_router.get("")
async def cashflow_full_list(request: Request, db: Session = Depends(get_db)):
    transactions = db.query(CashFlow).order_by(CashFlow.date.desc()).all()
    return templates.TemplateResponse(
        "cashflow.html", {"request": request, "transactions": transactions}
    )


@cashflow_router.get("/add")
async def cashflow_add_page(request: Request, db: Session = Depends(get_db)):
    categories = category_service.get_all_categories(db)
    return templates.TemplateResponse(
        "cashflow_add.html",
        {"request": request, "categories": categories, "now": datetime.now()},
    )


@cashflow_router.post("/update/{id}")
async def update_cashflow(
    id: int,
    description: str = Form(...),
    amount: float = Form(...),
    db: Session = Depends(get_db),
):
    item = db.query(CashFlow).get(id)
    if item:
        item.description = description
        item.amount = amount
        db.commit()
    return HTMLResponse(content="", headers={"HX-Redirect": "/cashflow"})


@cashflow_router.delete("/delete/{id}")
async def delete_cashflow(id: int, db: Session = Depends(get_db)):
    item = db.query(CashFlow).get(id)
    if item:
        db.delete(item)
        db.commit()
    return HTMLResponse(content="")  # HTMX will remove the row from the DOM
