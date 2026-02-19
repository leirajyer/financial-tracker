from fastapi import FastAPI
from datetime import datetime as dt

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, Payee, CashFlow, Installment  # Grouped models together
from app.services import category as category_service
from app.services.debt import get_global_updates_fragment  # Needed for your OOB updates

# Import our new Modular Services
from app.services import debt, cashflow, horizon as horizon_service

app = FastAPI()
templates = Jinja2Templates(directory="templates")
router = APIRouter()


@router.get("/get-summary")
async def get_summary(request: Request, db: Session = Depends(get_db)):
    try:
        # 1. Get Debt Engine stats (Current Month)
        # Note: 'debt' refers to the module app.services.debt
        stats = debt.calculate_monthly_totals(db)

        # 2. Get Income/Expenses (Day 11 Logic)
        # Using the year/month derived from the debt stats to stay in sync
        cash = cashflow.get_monthly_cashflow(db, stats["year"], stats["month"])

        # 3. Get the Long-term Projection (12 Months)
        # We renamed the import to horizon_service to avoid shadowing the variable 'projection'
        projection = horizon_service.get_12_month_forecast(db)
        freedom_date = debt.get_freedom_date(db)

        # 4. Final Calculation: Disposable Cash
        # Cash Balance (Income - Other Exp) minus what's still owed to CCs this month
        disposable_cash = cash["liquid_cash"] - stats["total_burn"]

        return templates.TemplateResponse(
            "partials/summary.html",
            {
                "request": request,
                "disposable_cash": round(disposable_cash, 2),
                "future_forecast": projection,
                "freedom_month": freedom_date,
                **stats,  # Unpacks total_burn, percentage_paid, etc.
                **cash,  # Unpacks total_income, total_other_expenses, liquid_cash
            },
        )
    except Exception as e:
        print(f"Error in get_summary: {e}")
        return HTMLResponse(content="Error loading summary", status_code=500)


@router.get("/add")
async def add_page(request: Request, db: Session = Depends(get_db)):
    # Keep the 'Add' page context aware of the current month's burn
    stats = debt.calculate_monthly_totals(db)

    return templates.TemplateResponse(
        "add_page.html",
        {
            "request": request,
            "now": dt.now(),
            "total_burn": stats.get("total_burn", 0),
        },
    )


@router.get("/add-form")
async def get_add_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "partials/form.html",
        {
            "request": request,
            "cards": db.query(Card).all(),
            "payees": db.query(Payee).all(),
            "categories": category_service.get_all_categories(db),
            "now": dt.now(),
        },
    )


@router.get("/cashflow-form")
async def get_cashflow_form(request: Request, db: Session = Depends(get_db)):
    categories = category_service.get_all_categories(db)
    return templates.TemplateResponse(
        "partials/cashflow_form.html",
        {"request": request, "categories": categories, "now": dt.now()},
    )


@router.post("/add-cashflow")
async def add_cashflow(
    request: Request,
    description: str = Form(...),
    amount: float = Form(...),
    type: str = Form(...),
    category_id: int = Form(...),
    date: str = Form(...),
    db: Session = Depends(get_db),
):
    # ... (Keep your existing DB save logic here) ...

    # NEW: Check if request is from the dedicated page or the dashboard
    # If we want a full redirect after a page entry:
    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = "/cashflow"
    return response


@router.get("/cashflow")
async def cashflow_page(request: Request, db: Session = Depends(get_db)):
    # Fetch data for the initial view
    categories = category_service.get_all_categories(db)
    # We'll fetch the recent transactions here too
    transactions = db.query(CashFlow).order_by(CashFlow.date.desc()).limit(20).all()

    return templates.TemplateResponse(
        "cashflow.html",
        {
            "request": request,
            "categories": categories,
            "transactions": transactions,
            "now": dt.now(),
        },
    )


@router.get("/cashflow/add")
async def cashflow_add_page(request: Request, db: Session = Depends(get_db)):
    categories = category_service.get_all_categories(db)
    return templates.TemplateResponse(
        "cashflow_add.html",
        {"request": request, "categories": categories, "now": dt.now()},
    )
