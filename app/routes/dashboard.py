from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from datetime import datetime as dt
from app.database import get_db
from app.logic import calculate_monthly_totals
from fastapi.templating import Jinja2Templates

# Define templates locally in this file
templates = Jinja2Templates(directory="templates")
router = APIRouter()


@router.get("/get-summary")
async def get_summary(request: Request, db: Session = Depends(get_db)):
    try:
        stats = calculate_monthly_totals(db)

        return templates.TemplateResponse(
            "partials/summary.html",
            {
                "request": request,
                "total_burn": stats.get("total_burn", 0),
                "card_totals": stats.get("card_totals", {}),
                "total_remaining": stats.get("total_remaining", 0),
            },
        )
    except Exception as e:
        print(f"Error: {e}")
        return HTMLResponse(content="Error loading summary", status_code=500)


@router.get("/add")
async def add_page(request: Request, db: Session = Depends(get_db)):
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
    # We pass 'now' so the 'Starting Month' input can default to the current month
    return templates.TemplateResponse(
        "partials/form.html", {"request": request, "now": dt.now()}
    )
