from fastapi import APIRouter, Depends, Request, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime as dt

from app.database import get_db
from app.services.debt import calculate_monthly_totals, get_global_updates_fragment
from app.models import CardMonthlyStatus, Card
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

router = APIRouter()


@router.get("/get-forecast", response_class=HTMLResponse)
async def get_forecast(
    request: Request,
    forecast_period: str = Query(None),
    db: Session = Depends(get_db),
):
    user = request.state.user
    year, month = None, None
    if forecast_period:
        year, month = map(int, forecast_period.split("-"))

    stats = calculate_monthly_totals(db, year, month, user_id=user.id)

    forecast_html = templates.TemplateResponse(
        "partials/forecast.html",
        {
            "request": request,
            **stats,
        },
    ).body.decode()

    global_updates = get_global_updates_fragment(db, stats["year"], stats["month"], user_id=user.id)

    return HTMLResponse(content=forecast_html + global_updates)


@router.post(
    "/toggle-card-status/{card_id}/{year}/{month}", response_class=HTMLResponse
)
async def toggle_card_status(
    request: Request, card_id: int, year: int, month: int, db: Session = Depends(get_db)
):
    user = request.state.user
    # Ensure card belongs to user
    card = db.query(Card).filter(Card.id == card_id, Card.owner_id == user.id).first()
    if not card:
        return Response(status_code=403)

    month_year = f"{year}-{month:02d}"
    status_obj = (
        db.query(CardMonthlyStatus)
        .filter(
            CardMonthlyStatus.card_id == card_id,
            CardMonthlyStatus.month_year == month_year,
        )
        .first()
    )

    if status_obj:
        status_obj.is_paid = not status_obj.is_paid
        status_obj.paid_at = dt.now() if status_obj.is_paid else None
    else:
        status_obj = CardMonthlyStatus(
            card_id=card_id, month_year=month_year, is_paid=True, paid_at=dt.now()
        )
        db.add(status_obj)

    db.commit()

    stats = calculate_monthly_totals(db, year, month, user_id=user.id)

    status_container_html = templates.TemplateResponse(
        "partials/card_status_container.html",
        {
            "request": request,
            "year": year,
            "month": month,
            **stats,
        },
    ).body.decode()

    msg = f"{card.name} Updated!"
    global_html = get_global_updates_fragment(db, year, month, toast_msg=msg, user_id=user.id)

    return HTMLResponse(content=status_container_html + global_html)
