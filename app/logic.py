from sqlalchemy.orm import joinedload
from datetime import date
from .models import Installment


def calculate_monthly_totals(db_session):
    today = date.today()
    all_items = db_session.query(Installment).all()

    total_burn = 0
    total_remaining_debt = 0
    card_totals = {}

    for item in all_items:
        # Check if item is active this month
        if item.start_date <= today <= item.end_date:
            total_burn += item.monthly_payment
            name = item.card.name if item.card else "Unknown"
            card_totals[name] = card_totals.get(name, 0) + item.monthly_payment

        # Add up all future payments
        total_remaining_debt += item.get_remaining_balance()

    return {
        "total_burn": total_burn,
        "card_totals": card_totals,
        "total_remaining": total_remaining_debt,
    }


def get_monthly_forecast(db, year, month):
    target_date = date(year, month, 1)

    # Use joinedload to fetch Card and Payee data in the same query
    all_items = (
        db.query(Installment)
        .options(joinedload(Installment.card), joinedload(Installment.payee))
        .all()
    )

    active_items = []
    total_due = 0.0
    card_split = {}

    for item in all_items:
        if item.start_date <= target_date <= item.end_date:
            active_items.append(item)
            total_due += item.monthly_payment

            c_name = item.card.name if item.card else "Unknown"
            card_split[c_name] = card_split.get(c_name, 0) + item.monthly_payment

    return {
        "items": active_items,
        "total_due": total_due,
        "card_split": card_split,
        "month_name": target_date.strftime("%B %Y"),
    }
