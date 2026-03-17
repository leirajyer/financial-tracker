from datetime import date
from sqlalchemy.orm import joinedload
from sqlalchemy import extract, func
from app.models import Installment, CardMonthlyStatus, Loan, CashFlow, Category
import calendar
from types import SimpleNamespace


def calculate_monthly_totals(
    db_session, year=None, month=None, card_id=None, payee_id=None, category_id=None, user_id=None
):
    """Calculates summary stats and separates cards by their payment status."""
    today = date.today()
    yr = int(year) if year else today.year
    mo = int(month) if month else today.month

    target_date = date(yr, mo, 1)
    month_year_str = f"{yr}-{mo:02d}"

    query = db_session.query(Installment).options(joinedload(Installment.card))

    if user_id:
        query = query.filter(Installment.owner_id == user_id)
    if card_id:
        query = query.filter(Installment.card_id == card_id)
    if payee_id:
        query = query.filter(Installment.payee_id == payee_id)
    if category_id:
        query = query.filter(Installment.category_id == category_id)

    all_items = query.all()

    status_query = db_session.query(CardMonthlyStatus).filter(CardMonthlyStatus.month_year == month_year_str)
    
    # If we want to be strict, CardMonthlyStatus should also have owner_id
    # But currently it relates to Card, and if we filter Installments by user_id, 
    # we only get cards belonging to that user.
    # However, let's filter statuses by checking the card's owner.
    
    statuses = status_query.all()
    # Map card_id to its status object for richer checks
    paid_status_map = {s.card_id: s for s in statuses}

    total_burn = 0  # Unpaid amount
    total_paid = 0  # Paid amount
    total_remaining_debt = 0

    pending_cards = {}
    paid_cards = {}
    active_items = []

    for item in all_items:
        if not item.start_date or not item.end_date:
            continue
            
        total_remaining_debt += item.get_remaining_balance()

        # Monthly Normalization for comparison
        item_start_norm = date(item.start_date.year, item.start_date.month, 1)
        item_end_norm = date(item.end_date.year, item.end_date.month, 1)

        if item_start_norm <= target_date <= item_end_norm:
            active_items.append(item)
            card = item.card
            c_id = (
                card.id if card else 0
            )  # Use c_id to avoid overwriting function param card_id
            card_name = card.name if card else "Unknown"
            payment = item.monthly_payment
            # Master override from manual marking (CardMonthlyStatus)
            status_obj = paid_status_map.get(c_id)
            item_is_paid = status_obj.is_paid if status_obj else False
            
            # CRITICAL FIX: If the card was marked as PAID, but this SPECIFIC installment 
            # was added AFTER the payment occurred, it should stay PENDING.
            if item_is_paid and status_obj and status_obj.paid_at and item.created_at:
                if item.created_at > status_obj.paid_at:
                    item_is_paid = False
            
            if status_obj is None:
                # DEFAULT LOGIC: All items start as PENDING
                item_is_paid = False
            
            # Carry the status for the templates
            item.is_paid_current = item_is_paid

            target_collection = paid_cards if item_is_paid else pending_cards

            if card_name not in target_collection:
                target_collection[card_name] = {
                    "id": c_id,
                    "total": 0,
                    "status": "PAID" if item_is_paid else "PENDING",
                    "color": card.color if card else "#94a3b8",
                }

            target_collection[card_name]["total"] += payment

            if item_is_paid:
                total_paid += payment
            else:
                total_burn += payment

    # --- ADD DAILY SWIPES FROM CASHFLOW ---
    # Fetch all cashflows for this month that are tied to a card
    swipes_query = db_session.query(CashFlow).options(joinedload(CashFlow.card)).filter(
        CashFlow.owner_id == user_id,
        CashFlow.card_id.is_not(None),
        extract("year", CashFlow.date) == yr,
        extract("month", CashFlow.date) == mo
    )
    
    swipes = swipes_query.all()
    
    for swipe in swipes:
        card = swipe.card
        if not card:
            continue
            
        c_id = card.id
        card_name = card.name
        payment = swipe.amount
        
        # Check payment status of the card
        status_obj = paid_status_map.get(c_id)
        item_is_paid = status_obj.is_paid if status_obj else False
        
        # CRITICAL: If the card was paid but swipe happened AFTER, it's pending
        if item_is_paid and status_obj and status_obj.paid_at and swipe.created_at:
            if swipe.created_at > status_obj.paid_at:
                item_is_paid = False
        
        target_collection = paid_cards if item_is_paid else pending_cards

        if card_name not in target_collection:
            target_collection[card_name] = {
                "id": c_id,
                "total": 0,
                "status": "PAID" if item_is_paid else "PENDING",
                "color": card.color if card else "#94a3b8",
            }

        target_collection[card_name]["total"] += payment

        if item_is_paid:
            total_paid += payment
        else:
            total_burn += payment

    # --- ADD LOANS & CASHFLOW AGGREGATES ---
    cc_category = db_session.query(Category).filter(Category.name == "Credit Card").first()
    cc_cat_id = cc_category.id if cc_category else -1

    cashflow_aggregates = db_session.query(
        CashFlow.category_id,
        func.sum(CashFlow.amount)
    ).filter(
        CashFlow.owner_id == user_id,
        CashFlow.type == "expense",
        extract("year", CashFlow.date) == yr,
        extract("month", CashFlow.date) == mo
    ).group_by(CashFlow.category_id).all()

    cashflow_expense_total = 0.0
    cashflow_cc_payment_total = 0.0

    for cat_id, amount in cashflow_aggregates:
        amount = amount or 0.0
        cashflow_expense_total += amount
        if cat_id == cc_cat_id:
            cashflow_cc_payment_total += amount

    cashflow_regular_expense_total = cashflow_expense_total - cashflow_cc_payment_total

    loans_q = db_session.query(Loan).options(joinedload(Loan.card)).filter(Loan.owner_id == user_id, Loan.status == "active")
    if card_id:
        loans_q = loans_q.filter(Loan.card_id == card_id)
    if category_id:
        loans_q = loans_q.filter(Loan.category_id == category_id)
    # Note: Loans don't currently have a payee_id field, but if they did, we'd filter it here.
    
    loans = loans_q.all()
    loan_total_monthly = 0.0
    loan_unlinked_total = 0.0
    for loan in loans:
        if not loan.start_date or not loan.end_date:
            continue
            
        if loan.start_date <= target_date <= loan.end_date:
            monthly_payment = loan.monthly_payment or 0.0
            loan_total_monthly += monthly_payment
            
            # If tied to a card, add to card totals
            if loan.card_id:
                c_id = loan.card_id
                card_name = loan.card.name
                
                status_obj = paid_status_map.get(c_id)
                item_is_paid = status_obj.is_paid if status_obj else False
                
                # Check creation date logic for late-added loans (similar to installments)
                if item_is_paid and status_obj and status_obj.paid_at and loan.created_at:
                    if loan.created_at > status_obj.paid_at:
                        item_is_paid = False

                target_collection = paid_cards if item_is_paid else pending_cards

                if card_name not in target_collection:
                    target_collection[card_name] = {
                        "id": c_id,
                        "total": 0,
                        "status": "PAID" if item_is_paid else "PENDING",
                        "color": loan.card.color if loan.card else "#94a3b8",
                    }

                target_collection[card_name]["total"] += monthly_payment

                if item_is_paid:
                    total_paid += monthly_payment
                else:
                    total_burn += monthly_payment
                
                # Add to active items for summary display
                loan.is_paid_current = item_is_paid
                
                # Dynamically add a payee attribute for the template if it doesn't exist
                if not hasattr(loan, 'payee') or loan.payee is None:
                    loan.payee = SimpleNamespace(name="Loan (Credit)")
                
                active_items.append(loan)
            else:
                loan_unlinked_total += monthly_payment

    # --- MATH CLEANUP (Final Totals) ---

    # 1. total_due is the sum of what's paid and what's left
    total_due = round(total_burn + total_paid, 2)

    # 2. Calculate percentage based on actual totals calculated in the loop
    percentage_paid = 0
    if total_due > 0:
        percentage_paid = round((total_paid / total_due) * 100)

    # Trend Analysis Logic
    burn_down = get_debt_burn_down(db_session, months_to_forecast=4, user_id=user_id)
    three_months_out = burn_down[3]
    future_total = three_months_out["total"]
    savings_delta = total_due - future_total
    percent_drop = round((savings_delta / total_due * 100)) if total_due > 0 else 0

    # Total Remaining Aggregate (What's still due or already spent this month)
    # Remaining Payment = Regular Expenses + Unpaid Credit Items + Unlinked Loans
    aggregate_monthly_payment = cashflow_regular_expense_total + total_burn + loan_unlinked_total

    return {
        "total_burn": round(total_burn, 2),
        "total_paid": round(total_paid, 2),
        "total_due": total_due,
        "total_remaining_debt": round(total_remaining_debt, 2),
        "percentage_paid": percentage_paid,
        "pending_cards": pending_cards,
        "paid_cards": paid_cards,
        "items": active_items,
        "paid_status_map": paid_status_map,
        "month_name": calendar.month_name[mo],
        "year": yr,
        "month": mo,
        "savings_delta": savings_delta,
        "percent_drop": percent_drop,
        "avg_monthly_burn": round(total_due, 2),
        "loan_total_monthly": loan_total_monthly,
        "loan_unlinked_total": loan_unlinked_total,
        "cashflow_expense_total": cashflow_expense_total,
        "cashflow_regular_expense_total": cashflow_regular_expense_total,
        "aggregate_monthly_payment": aggregate_monthly_payment,
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


def get_monthly_forecast(db, year, month, card_id=None, payee_id=None, user_id=None):
    """Aggregates all installments for a specific month and groups them by card."""
    target_date = date(year, month, 1)

    # 1. Fetch items with eager loading for both card and payee
    query = db.query(Installment).options(
        joinedload(Installment.card), joinedload(Installment.payee)
    )

    all_items = query.all()

    # Fetch loans as well
    loan_query = db.query(Loan).options(joinedload(Loan.card))
    if user_id:
        loan_query = loan_query.filter(Loan.owner_id == user_id)
    if card_id:
        loan_query = loan_query.filter(Loan.card_id == card_id)
    
    all_loans = loan_query.all()

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

    # 3. Process loans and group by Card
    for loan in all_loans:
        if loan.start_date <= target_date <= loan.end_date:
            total_due += loan.monthly_payment
            
            if loan.card_id:
                c_name = loan.card.name
                c_id = loan.card_id
                
                if c_name not in card_data:
                    status = get_card_status(db, c_id, year, month)
                    card_data[c_name] = {"total": 0.0, "id": c_id, "status": status}
                
                card_data[c_name]["total"] += loan.monthly_payment

    return {
        "items": active_items,
        "total_due": total_due,
        "card_data": card_data,
        "month_name": target_date.strftime("%B %Y"),
        "year": year,
        "month": month,
    }


def get_global_updates_fragment(
    db, year, month, card_id=None, payee_id=None, toast_msg=None, user_id=None
):
    """Standardized helper for Out-of-Band UI updates with Fully Paid state."""
    stats = calculate_monthly_totals(
        db, year, month, card_id=card_id, payee_id=payee_id, user_id=user_id
    )
    total_val = stats.get("total_burn", 0)

    from app.core.ui import templates
    template = templates.get_template("partials/toast_oob.html")
    return template.render({"total_val": total_val, "toast_msg": toast_msg})


def get_debt_burn_down(db_session, months_to_forecast=12, user_id=None):
    """Day 10: Calculates the total monthly bill for the next X months."""
    today = date.today()
    forecast = []
    
    query = db_session.query(Installment)
    loan_query = db_session.query(Loan).filter(Loan.status == "active")
    if user_id:
        query = query.filter(Installment.owner_id == user_id)
        loan_query = loan_query.filter(Loan.owner_id == user_id)
    
    items = query.all()
    loans = loan_query.all()

    for i in range(months_to_forecast):
        target_month = (today.month + i - 1) % 12 + 1
        target_year = today.year + (today.month + i - 1) // 12
        target_date = date(target_year, target_month, 1)

        monthly_total = sum(
            item.monthly_payment
            for item in items
            if item.start_date <= target_date <= item.end_date
        )
        
        monthly_total += sum(
            loan.monthly_payment
            for loan in loans
            if loan.start_date <= target_date <= loan.end_date
        )

        forecast.append(
            {"month": target_date.strftime("%b %Y"), "total": round(monthly_total, 2)}
        )
    return forecast


def get_freedom_date(db_session, user_id=None):
    """Day 10: Finds the furthest end_date for the 'Freedom' milestone."""
    query = db_session.query(Installment)
    loan_query = db_session.query(Loan).filter(Loan.status == "active")
    if user_id:
        query = query.filter(Installment.owner_id == user_id)
        loan_query = loan_query.filter(Loan.owner_id == user_id)
        
    items = query.all()
    loans = loan_query.all()
    
    if not items and not loans:
        return "No active debt"
        
    dates = []
    if items:
        dates.extend([i.end_date for i in items if i.end_date])
    if loans:
        dates.extend([l.end_date for l in loans if l.end_date])
            
    if not dates:
        return "No active debt"
        
    return max(dates).strftime("%B %Y")
