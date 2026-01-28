from fastapi import APIRouter, Depends, Request, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime as dt

from app.database import get_db
from app.logic import (
    get_monthly_forecast,
    get_card_status,
    calculate_monthly_totals,
    get_global_updates_fragment,
)
from app.models import CardMonthlyStatus, Card
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


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


@router.get("/get-forecast", response_class=HTMLResponse)
async def get_forecast(
    request: Request,
    forecast_period: str = Query(None),
    db: Session = Depends(get_db),
):
    # Parse period string "YYYY-MM"
    year, month = None, None
    if forecast_period:
        year, month = map(int, forecast_period.split("-"))

    # 1. Get the unified data object
    stats = calculate_monthly_totals(db, year, month)

    # 2. Render the partial with the full context
    # This prevents 'total_burn' or 'items' from being Undefined
    forecast_html = templates.TemplateResponse(
        "partials/forecast.html",
        {
            "request": request,
            **stats,  # This unpacks all keys (total_burn, items, month_name, etc.)
        },
    ).body.decode()

    # 3. Append the OOB update for the Navbar
    global_updates = get_global_updates_fragment(db, stats["year"], stats["month"])

    return HTMLResponse(content=forecast_html + global_updates)


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

    # 1. Toggle Logic
    if status_obj:
        status_obj.is_paid = not status_obj.is_paid
        status_obj.paid_at = dt.now() if status_obj.is_paid else None
    else:
        status_obj = CardMonthlyStatus(
            card_id=card_id, month_year=month_year, is_paid=True, paid_at=dt.now()
        )
        db.add(status_obj)

    db.commit()

    # 2. Get Updated Totals and Separated Lists
    stats = calculate_monthly_totals(db, year, month)

    # 3. Render the updated Card Status Container
    # We use hx-swap-oob="true" on the container wrapper in this template
    status_container_html = templates.TemplateResponse(
        "partials/card_status_container.html",
        {
            "request": {},  # Empty request or pass actual if needed
            "year": year,
            "month": month,
            **stats,
        },
    ).body.decode()

    # 4. Get Global UI Updates (Burnout + Toast)
    msg = f"{status_obj.card.name if status_obj.card else 'Card'} Updated!"
    global_html = get_global_updates_fragment(db, year, month, toast_msg=msg)

    return HTMLResponse(content=status_container_html + global_html)


# def render_status_fragment(card_id, status, year, month):
#     """Helper to return the exact HTML fragment for the row."""
#     is_paid = status == "PAID"
#     badge_cls = (
#         "bg-emerald-100 text-emerald-700 border-emerald-200"
#         if is_paid
#         else "bg-amber-100 text-amber-700 border-amber-200"
#     )
#     btn_cls = (
#         "bg-gray-50 border-gray-200 text-gray-500"
#         if is_paid
#         else "bg-emerald-50 border-emerald-200 text-emerald-600"
#     )
#     icon = "🔄" if is_paid else "✅"

#     return f"""
#     <div id="status-container-{card_id}" class="flex items-center gap-3">
#         <span class="px-2 py-1 rounded text-[10px] font-black uppercase border {badge_cls}">
#             {status}
#         </span>
#         <button hx-post="/toggle-card-status/{card_id}/{year}/{month}"
#                 hx-target="#status-container-{card_id}"
#                 hx-confirm="Are you sure you want to change status of the card?"
#                 hx-swap="outerHTML"
#                 class="p-1.5 rounded-md border transition-all duration-200 {btn_cls} hover:opacity-80">
#             {icon}
#         </button>
#     </div>
#     """
