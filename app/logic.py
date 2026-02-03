from datetime import datetime as dt, date
from sqlalchemy.orm import joinedload
from .models import Installment, CardMonthlyStatus
import calendar


def calculate_monthly_totals(
    db_session, year=None, month=None, card_id=None, payee_id=None
):
    """Calculates summary stats and separates cards by their payment status."""
    today = date.today()
    yr = int(year) if year else today.year
    mo = int(month) if month else today.month

    target_date = date(yr, mo, 1)
    month_year_str = f"{yr}-{mo:02d}"

    query = db_session.query(Installment).options(joinedload(Installment.card))

    if card_id:
        query = query.filter(Installment.card_id == card_id)
    if payee_id:
        query = query.filter(Installment.payee_id == payee_id)

    all_items = query.all()

    statuses = (
        db_session.query(CardMonthlyStatus)
        .filter(CardMonthlyStatus.month_year == month_year_str)
        .all()
    )

    paid_status_map = {s.card_id: s.is_paid for s in statuses}

    total_burn = 0  # Unpaid amount
    total_paid = 0  # Paid amount
    total_remaining_debt = 0

    pending_cards = {}
    paid_cards = {}
    active_items = []

    for item in all_items:
        total_remaining_debt += item.get_remaining_balance()

        if item.start_date <= target_date <= item.end_date:
            active_items.append(item)
            card = item.card
            c_id = (
                card.id if card else 0
            )  # Use c_id to avoid overwriting function param card_id
            card_name = card.name if card else "Unknown"
            payment = item.monthly_payment
            is_paid = paid_status_map.get(c_id, False)

            target_collection = paid_cards if is_paid else pending_cards

            if card_name not in target_collection:
                target_collection[card_name] = {
                    "id": c_id,
                    "total": 0,
                    "status": "PAID" if is_paid else "PENDING",
                }

            target_collection[card_name]["total"] += payment

            if is_paid:
                total_paid += payment
            else:
                total_burn += payment

    # --- MATH CLEANUP (After the loop) ---

    # 1. total_due is the sum of what's paid and what's left
    total_due = round(total_burn + total_paid, 2)

    # 2. Calculate percentage based on actual totals calculated in the loop
    percentage_paid = 0
    if total_due > 0:
        percentage_paid = round((total_paid / total_due) * 100)

    # Trend Analysis Logic
    three_months_out = get_debt_burn_down(db_session, months_to_forecast=4)[3]
    future_total = three_months_out["total"]
    savings_delta = total_due - future_total
    percent_drop = round((savings_delta / total_due * 100)) if total_due > 0 else 0

    return {
        "total_burn": round(total_burn, 2),
        "total_paid": round(total_paid, 2),
        "total_due": total_due,
        "total_remaining_debt": round(total_remaining_debt, 2),
        "percentage_paid": percentage_paid,
        "pending_cards": pending_cards,
        "paid_cards": paid_cards,
        "items": active_items,
        "month_name": calendar.month_name[mo],
        "year": yr,
        "month": mo,
        "savings_delta": savings_delta,
        "percent_drop": percent_drop,
        "avg_monthly_burn": round(total_due, 2),
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


def get_global_updates_fragment(
    db, year, month, card_id=None, payee_id=None, toast_msg=None
):
    """Standardized helper for Out-of-Band UI updates with Fully Paid state."""
    stats = calculate_monthly_totals(
        db, year, month, card_id=card_id, payee_id=payee_id
    )
    total_val = stats.get("total_burn", 0)

    # Check if balance is zero or less
    if total_val < 0.01:
        burn_display = '<span class="text-emerald-400 font-black animate-pulse">FULLY PAID 🎉</span>'
    else:
        burn_display = f"₱{total_val:,.2f}"

    # 1. Burnout Fragment (targets your navbar ID)
    fragments = [f'<span id="total-burnout" hx-swap-oob="true">{burn_display}</span>']
    fragments.append(
        f'<span id="nav-remaining-value" class="text-sm font-bold text-red-600 bg-white border border-slate-200 px-3 py-1 rounded-lg shadow-sm bg-red-100" hx-swap-oob="true">{burn_display}</span>'
    )

    # 2. Toast Fragment
    if toast_msg:
        fragments.append(f"""
            <div id="toast-container" hx-swap-oob="true" _="on load wait 3s then remove me"
                 class="fixed bottom-5 right-5 bg-emerald-600 text-white px-6 py-3 rounded-xl shadow-2xl flex items-center gap-3 transition-opacity duration-500 z-50">
                <span class="text-lg">🎉</span>
                <span class="font-bold text-sm">{toast_msg}</span>
            </div>
        """)
    else:
        # Use hx-swap-oob to target the container and wipe its inner HTML AND classes
        fragments.append(
            '<div id="toast-container" hx-swap-oob="true" class="hidden"></div>'
        )

    return "".join(fragments)


def get_debt_burn_down(db_session, months_to_forecast=12):
    """Day 10: Calculates the total monthly bill for the next X months."""
    today = date.today()
    forecast = []
    items = db_session.query(Installment).all()

    for i in range(months_to_forecast):
        target_month = (today.month + i - 1) % 12 + 1
        target_year = today.year + (today.month + i - 1) // 12
        target_date = date(target_year, target_month, 1)

        monthly_total = sum(
            item.monthly_payment
            for item in items
            if item.start_date <= target_date <= item.end_date
        )

        forecast.append(
            {"month": target_date.strftime("%b %Y"), "total": round(monthly_total, 2)}
        )
    return forecast


def get_freedom_date(db_session):
    """Day 10: Finds the furthest end_date for the 'Freedom' milestone."""
    items = db_session.query(Installment).all()
    if not items:
        return "No active debt"
    return max(item.end_date for item in items).strftime("%B %Y")
