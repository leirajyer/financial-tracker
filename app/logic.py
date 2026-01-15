import datetime
from app.models import CardMonthlyStatus
from sqlalchemy.orm import joinedload
from datetime import datetime, date
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


def get_monthly_forecast(db, year, month, card_id=None, payee_id=None):
    target_date = date(year, month, 1)

    # 1. Fetch all items with eager loading
    query = db.query(Installment).options(
        joinedload(Installment.card), joinedload(Installment.payee)
    )

    if card_id:
        query = query.filter(Installment.card_id == card_id)
    if payee_id:
        query = query.filter(Installment.payee_id == payee_id)

    all_items = query.all()

    active_items = []
    total_due = 0.0

    # We change card_split to store more info: { "Card Name": {"total": 0, "id": 1, "status": "..."} }
    card_data = {}

    # 2. Process items and group by Card
    for item in all_items:
        if item.start_date <= target_date <= item.end_date:
            active_items.append(item)
            total_due += item.monthly_payment

            c_name = item.card.name if item.card else "Unknown"
            c_id = item.card.id if item.card else None

            if c_name not in card_data:
                # Fetch the smart status for this card
                status = get_card_status(db, c_id, year, month) if c_id else "PENDING"
                card_data[c_name] = {"total": 0.0, "id": c_id, "status": status}

            card_data[c_name]["total"] += item.monthly_payment

    return {
        "items": active_items,
        "total_due": total_due,
        "card_data": card_data,  # This replaces card_split
        "month_name": target_date.strftime("%B %Y"),
        "year": year,
        "month": month,
    }


def get_card_status(db, card_id, year, month):
    period = f"{year}-{month:02d}"

    status_record = (
        db.query(CardMonthlyStatus)
        .filter(
            CardMonthlyStatus.card_id == card_id, CardMonthlyStatus.month_year == period
        )
        .first()
    )

    if status_record and status_record.is_paid:
        return "PAID"

    # FIX: Use 'datetime.now()' because you imported the class directly
    current_date = datetime.now()

    # FIX: Use 'date' (which you also imported) for a clean comparison
    view_date = date(year, month, 1)
    current_month_start = date(current_date.year, current_date.month, 1)

    if view_date < current_month_start:
        return "OVERDUE"

    return "PENDING"
