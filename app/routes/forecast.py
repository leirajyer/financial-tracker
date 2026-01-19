from fastapi import APIRouter, Depends, Request, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime as dt

from app.database import get_db
from app.logic import get_monthly_forecast, get_card_status
from app.models import CardMonthlyStatus, Card

router = APIRouter()


# Helper for the HTMX badge
def render_status_badge(status, card_id, year, month, card_name="this card"):
    styles = {
        "PAID": "bg-emerald-100 text-emerald-700 border-emerald-200",
        "OVERDUE": "bg-rose-100 text-rose-700 border-rose-200 animate-pulse",
        "PENDING": "bg-amber-100 text-amber-700 border-amber-200",
    }
    return f"""
    <div id="status-badge-{card_id}" 
         hx-post="/toggle-card-status/{card_id}/{year}/{month}"
         hx-confirm="Are you sure you want to change status for {card_name}?"
         hx-swap="outerHTML"
         class="cursor-pointer px-3 py-1 rounded-full text-[10px] font-black border {styles.get(status)}">
        {status}
    </div>
    """


@router.get("/get-forecast")
async def get_forecast(
    request: Request,
    forecast_period: str = None,
    card_id: str = Query(None),
    db: Session = Depends(get_db),
):
    # (Same logic as before, just using 'router' decorator)
    pass


# Change the path to include {year} and {month}
from fastapi.responses import HTMLResponse


@router.post(
    "/toggle-card-status/{card_id}/{year}/{month}", response_class=HTMLResponse
)
async def toggle_card_status(
    card_id: int, year: int, month: int, db: Session = Depends(get_db)
):
    month_year = f"{year}-{month:02d}"
    status_obj = (
        db.query(CardMonthlyStatus)
        .filter(
            CardMonthlyStatus.card_id == card_id,
            CardMonthlyStatus.month_year == month_year,
        )
        .first()
    )

    # Toggle Logic
    if status_obj:
        status_obj.is_paid = not status_obj.is_paid
        status_obj.paid_at = dt.now() if status_obj.is_paid else None
    else:
        status_obj = CardMonthlyStatus(
            card_id=card_id, month_year=month_year, is_paid=True, paid_at=dt.now()
        )
        db.add(status_obj)

    db.commit()

    # Determine new state for the UI
    new_status = "PAID" if status_obj.is_paid else "PENDING"

    # Return ONLY the updated fragment
    return render_status_fragment(card_id, new_status, year, month)


def render_status_fragment(card_id, status, year, month):
    """Helper to return the exact HTML fragment for the row."""
    is_paid = status == "PAID"
    badge_cls = (
        "bg-emerald-100 text-emerald-700 border-emerald-200"
        if is_paid
        else "bg-amber-100 text-amber-700 border-amber-200"
    )
    btn_cls = (
        "bg-gray-50 border-gray-200 text-gray-500"
        if is_paid
        else "bg-emerald-50 border-emerald-200 text-emerald-600"
    )
    icon = "↪️" if is_paid else "✅"

    return f"""
    <div id="status-container-{card_id}" class="flex items-center gap-3">
        <span class="px-2 py-1 rounded text-[10px] font-black uppercase border {badge_cls}">
            {status}
        </span>
        <button hx-post="/toggle-card-status/{card_id}/{year}/{month}"
                hx-target="#status-container-{card_id}"
                hx-swap="outerHTML"
                class="p-1.5 rounded-md border transition-all duration-200 {btn_cls} hover:opacity-80">
            {icon}
        </button>
    </div>
    """
