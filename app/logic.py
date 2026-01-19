from datetime import datetime as dt, date
from sqlalchemy.orm import joinedload
from .models import Installment, CardMonthlyStatus


def calculate_monthly_totals(db_session, year=None, month=None):
    """Calculates summary stats, excluding PAID cards from the active burnout."""
    today = date.today()
    # Use provided year/month or default to current
    yr = year or today.year
    mo = month or today.month

    target_month_start = date(yr, mo, 1)
    month_year_str = f"{yr}-{mo:02d}"

    # 1. Fetch all items and the status of cards for this month
    all_items = (
        db_session.query(Installment).options(joinedload(Installment.card)).all()
    )

    # Get set of card IDs that are marked as PAID this month
    from app.models import CardMonthlyStatus

    paid_card_ids = {
        row.card_id
        for row in db_session.query(CardMonthlyStatus.card_id)
        .filter(
            CardMonthlyStatus.month_year == month_year_str,
            CardMonthlyStatus.is_paid == True,
        )
        .all()
    }

    total_burn = 0  # This will now represent "Remaining to Pay"
    total_paid = 0
    total_remaining_debt = 0
    card_totals = {}

    for item in all_items:
        # Check if item is active for the viewed month
        if item.start_date <= target_month_start <= item.end_date:
            name = item.card.name if item.card else "Unknown"
            payment = item.monthly_payment

            # Group by card for the breakdown
            card_totals[name] = card_totals.get(name, 0) + payment

            # LOGIC: If the card is PAID, it doesn't count towards the active burnout
            if item.card_id in paid_card_ids:
                total_paid += payment
            else:
                total_burn += payment

        # Overall debt remains unaffected by monthly paid status
        total_remaining_debt += item.get_remaining_balance()

    # Calculate payment progress
    grand_total = total_burn + total_paid
    progress = (total_paid / grand_total * 100) if grand_total > 0 else 0

    return {
        "total_burn": total_burn,  # Remaining "Pending" amount
        "total_paid": total_paid,  # Amount already cleared
        "progress": round(progress, 1),
        "card_totals": card_totals,
        "total_remaining": total_remaining_debt,
    }


def get_card_status(db, card_id, year, month):
    """Simplified status: Only PAID or PENDING."""
    from app.models import CardMonthlyStatus

    month_year_str = f"{year}-{month:02d}"

    # 1. Check if marked as PAID in the database
    status_rec = (
        db.query(CardMonthlyStatus)
        .filter(
            CardMonthlyStatus.card_id == card_id,
            CardMonthlyStatus.month_year == month_year_str,
        )
        .first()
    )

    if status_rec and status_rec.is_paid:
        return "PAID"

    # 2. Everything else is PENDING by default
    return "PENDING"


def get_monthly_forecast(db, year, month, card_id=None, payee_id=None):
    """Aggregates all installments for a specific month and groups them by card."""
    target_date = date(year, month, 1)

    # 1. Fetch items with eager loading for both card and payee
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
    card_data = {}

    # 2. Process items and group by Card
    for item in all_items:
        if item.start_date <= target_date <= item.end_date:
            active_items.append(item)
            total_due += item.monthly_payment

            c_name = item.card.name if item.card else "Unknown"
            c_id = item.card_id if item.card else None

            if c_name not in card_data:
                # Fetch the smart status for this card grouping
                status = get_card_status(db, c_id, year, month) if c_id else "PENDING"
                card_data[c_name] = {"total": 0.0, "id": c_id, "status": status}

            card_data[c_name]["total"] += item.monthly_payment

    return {
        "items": active_items,
        "total_due": total_due,
        "card_data": card_data,
        "month_name": target_date.strftime("%B %Y"),
        "year": year,
        "month": month,
    }
