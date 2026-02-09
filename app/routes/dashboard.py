from datetime import datetime
from app.models import Payee
from app.models import Card
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from datetime import datetime as dt
from app.database import get_db
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.services import category as category_service

# Import our new Modular Services
from app.services import debt, cashflow, horizon as horizon_service

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
            "now": datetime.now(),
        },
    )
