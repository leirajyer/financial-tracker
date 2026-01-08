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
