from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from datetime import datetime as dt
from app.database import get_db
from app.logic import calculate_monthly_totals, get_debt_burn_down, get_freedom_date
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

templates = Jinja2Templates(directory="templates")
router = APIRouter()


@router.get("/get-summary")
async def get_summary(request: Request, db: Session = Depends(get_db)):
    try:
        # 1. Fetch current month's health stats
        stats = calculate_monthly_totals(db)

        # 2. Day 10 Intelligence: Get the 6-month burn-down forecast
        future_forecast = get_debt_burn_down(db, months_to_forecast=12)

        # 3. Calculate the light at the end of the tunnel
        freedom_month = get_freedom_date(db)

        return templates.TemplateResponse(
            "partials/summary.html",
            {
                "request": request,
                "future_forecast": future_forecast,
                "freedom_month": freedom_month,
                **stats,  # Dynamically passes total_burn, percentage_paid, etc.
            },
        )
    except Exception as e:
        print(f"Error loading summary: {e}")
        return HTMLResponse(content="Error loading summary", status_code=500)


@router.get("/add")
async def add_page(request: Request, db: Session = Depends(get_db)):
    # We still get stats so the Add page knows the context of the current month
    stats = calculate_monthly_totals(db)

    return templates.TemplateResponse(
        "add_page.html",
        {
            "request": request,
            "now": dt.now(),
            "total_burn": stats.get("total_burn", 0),
        },
    )


@router.get("/add-form")
async def get_add_form(request: Request):
    return templates.TemplateResponse(
        "partials/form.html", {"request": request, "now": dt.now()}
    )
