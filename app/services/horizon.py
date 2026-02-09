# app/services/horizon.py
from datetime import date
from sqlalchemy.orm import Session
from app.models import Installment


def get_12_month_forecast(db: Session):
    today = date.today()
    forecast = []
    items = db.query(Installment).all()

    for i in range(12):
        target_month = (today.month + i - 1) % 12 + 1
        target_year = today.year + (today.month + i - 1) // 12
        target_date = date(target_year, target_month, 1)

        total = sum(
            item.monthly_payment
            for item in items
            if item.start_date <= target_date <= item.end_date
        )

        forecast.append(
            {"month": target_date.strftime("%b %Y"), "total": round(total, 2)}
        )

    return forecast
