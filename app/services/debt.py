from datetime import date
from sqlalchemy.orm import joinedload
from sqlalchemy import extract, func
from app.models import Installment, CardMonthlyStatus, Loan, CashFlow, Category, Card
import calendar
from types import SimpleNamespace
from dateutil.relativedelta import relativedelta


def calculate_monthly_totals(
    db_session, year=None, month=None, card_id=None, payee_id=None, category_id=None, user_id=None
):
    """Calculates summary stats and separates cards by their payment status."""
    today = date.today()
    yr = int(year) if year else today.year
    mo = int(month) if month else today.month

    target_date = date(yr, mo, 1)
    month_year_str = f"{yr}-{mo:02d}"

    # FETCH CC CATEGORY ID EARLY
    cc_category = db_session.query(Category).filter(Category.name == "Credit Card").first()
    cc_cat_id = cc_category.id if cc_category else -1

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
    statuses = status_query.all()
    paid_status_map = {s.card_id: s for s in statuses}

    total_burn = 0  # To be recalculated
    total_paid = 0  # To be recalculated
    total_remaining_debt = 0

    pending_cards = {}
    paid_cards = {}
    active_items = []

    # TRACK BILLING PER CARD
    card_billing = {} # card_id -> amount

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
            c_id = card.id if card else 0
            payment = item.monthly_payment
            
            card_billing[c_id] = card_billing.get(c_id, 0.0) + payment

    # --- ADD DAILY SWIPES FROM CASHFLOW ---
    # Fetch all cashflows for this month that are tied to a card (EXCLUDING CC PAYMENTS)
    swipes_q = db_session.query(CashFlow).options(joinedload(CashFlow.card)).filter(
        CashFlow.owner_id == user_id,
        CashFlow.card_id.is_not(None),
        extract("year", CashFlow.date) == yr,
        extract("month", CashFlow.date) == mo,
        CashFlow.category_id != cc_cat_id
    )
    if card_id:
        swipes_q = swipes_q.filter(CashFlow.card_id == card_id)
    
    swipes = swipes_q.all()
    
    for swipe in swipes:
        c_id = swipe.card_id
        card_billing[c_id] = card_billing.get(c_id, 0.0) + swipe.amount

    # --- ADD LOANS ---
    loans_q = db_session.query(Loan).options(joinedload(Loan.card)).filter(Loan.owner_id == user_id, Loan.status == "active")
    if card_id:
        loans_q = loans_q.filter(Loan.card_id == card_id)
    if category_id:
        loans_q = loans_q.filter(Loan.category_id == category_id)
    
    loans = loans_q.all()
    loan_total_monthly = 0.0
    loan_unlinked_total = 0.0
    for loan in loans:
        if not loan.start_date or not loan.end_date:
            continue
            
        if loan.start_date <= target_date <= loan.end_date:
            monthly_payment = loan.monthly_payment or 0.0
            loan_total_monthly += monthly_payment
            
            if loan.card_id:
                c_id = loan.card_id
                card_billing[c_id] = card_billing.get(c_id, 0.0) + monthly_payment
                
                if not hasattr(loan, 'payee') or loan.payee is None:
                    loan.payee = SimpleNamespace(name="Loan (Credit)")
                active_items.append(loan)
            else:
                loan_unlinked_total += monthly_payment

    # --- CARRYOVER & ACTUAL PAYMENTS LOGIC ---
    # 1. Fetch all cards involved
    relevant_card_ids = set(card_billing.keys())
    if card_id:
        relevant_card_ids.add(card_id)
    
    cards = db_session.query(Card).filter(Card.id.in_(relevant_card_ids)).all()
    card_map = {c.id: c for c in cards}

    # 2. Fetch ACTUAL payments made THIS month
    actual_payments_q = db_session.query(
        CashFlow.card_id,
        func.sum(CashFlow.amount)
    ).filter(
        CashFlow.owner_id == user_id,
        CashFlow.category_id == cc_cat_id,
        extract("year", CashFlow.date) == yr,
        extract("month", CashFlow.date) == mo
    ).group_by(CashFlow.card_id).all()
    
    actual_payments = {cid: amt for cid, amt in actual_payments_q}

    # 3. Process All Cards for this user to determine Final Status and Carryover
    # Note: We must check all cards because a card might have 0 billing this month but still have a carryover balance.
    if card_id:
        cards_to_check = [c for c in cards if c.id == card_id]
    else:
        cards_to_check = cards

    for card in cards_to_check:
        c_id = card.id
        card_name = card.name
        billed_this_month = card_billing.get(c_id, 0.0)
        
        # Calculate Balance from PREVIOUS months
        prev_balance = get_card_balance_at_date(db_session, user_id, c_id, target_date - relativedelta(months=1))
        
        amt_paid_this_month = actual_payments.get(c_id, 0.0)
        
        # total_due_for_this_card = what was owed before + what was billed now
        total_due_for_card = prev_balance + billed_this_month
        
        # remaining_for_card = total_due - what was paid now
        remaining_for_card = total_due_for_card - amt_paid_this_month
        
        is_paid = remaining_for_card <= 0.01 # Small epsilon for float logic
        
        # If manually marked as PAID, we might want to respect that even if math says otherwise?
        # But for overpayment, the math is better.
        status_obj = paid_status_map.get(c_id)
        if status_obj and status_obj.is_paid:
            is_paid = True
        
        # Final Assignment to collections
        target_collection = paid_cards if is_paid else pending_cards
        target_collection[card_name] = {
            "id": c_id,
            "total": round(max(0, remaining_for_card if not is_paid else billed_this_month), 2),
            "status": "PAID" if is_paid else "PENDING",
            "color": card.color if card else "#94a3b8",
            "billed_this_month": round(billed_this_month, 2),
            "prev_balance": round(prev_balance, 2),
            "actual_paid": round(amt_paid_this_month, 2)
        }

        if is_paid:
            total_paid += billed_this_month # We count the billed amount as "covered"
            # But wait, if they overpaid, should total_paid reflect that?
            # Usually total_paid in the dashboard is part of "How much of my debt is gone".
            # If they paid $1100 for $1000, $1100 is gone.
            # But $1000 is this month's debt.
        else:
            total_burn += max(0, remaining_for_card)

    # Cleanup: Mark items in active_items as paid if their card is paid
    for item in active_items:
        c_id = getattr(item, 'card_id', None)
        if c_id:
            card = card_map.get(c_id)
            if card and card.name in paid_cards:
                item.is_paid_current = True
            else:
                item.is_paid_current = False

    # --- CASHFLOW AGGREGATES FOR TOP STATS ---
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


    # MATH CLEANUP (Final Totals)
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


def get_card_balance_at_date(db_session, user_id, card_id, target_date):
    """
    Calculates cumulative balance (Billed - Paid) up to target_date (last day of that month).
    """
    cc_category = db_session.query(Category).filter(Category.name == "Credit Card").first()
    cc_cat_id = cc_category.id if cc_category else -1

    # End of target month
    last_day = calendar.monthrange(target_date.year, target_date.month)[1]
    end_of_month = date(target_date.year, target_date.month, last_day)

    # 1. Total Paid (CC Payments up to end_of_month)
    total_paid = db_session.query(func.sum(CashFlow.amount)).filter(
        CashFlow.owner_id == user_id,
        CashFlow.card_id == card_id,
        CashFlow.category_id == cc_cat_id,
        CashFlow.date <= end_of_month
    ).scalar() or 0.0

    # 2. Total Swipes (Non-CC payments up to end_of_month)
    total_swipes = db_session.query(func.sum(CashFlow.amount)).filter(
        CashFlow.owner_id == user_id,
        CashFlow.card_id == card_id,
        CashFlow.category_id != cc_cat_id,
        CashFlow.type == "expense",
        CashFlow.date <= end_of_month
    ).scalar() or 0.0

    # 3. Total Installments up to end_of_month
    all_inst = db_session.query(Installment).filter(
        Installment.owner_id == user_id,
        Installment.card_id == card_id,
        Installment.start_date <= end_of_month
    ).all()
    
    total_inst = 0.0
    for inst in all_inst:
        if not inst.start_date: continue
        # How many months from start_date up to end_of_month?
        start = date(inst.start_date.year, inst.start_date.month, 1)
        end = date(end_of_month.year, end_of_month.month, 1)
        
        months_passed = (end.year - start.year) * 12 + (end.month - start.month) + 1
        months_to_bill = min(months_passed, inst.payment_terms or 1)
        total_inst += inst.monthly_payment * months_to_bill

    # 4. Total Loans up to end_of_month
    all_loans = db_session.query(Loan).filter(
        Loan.owner_id == user_id,
        Loan.card_id == card_id,
        Loan.start_date <= end_of_month
    ).all()
    
    total_loans = 0.0
    for loan in all_loans:
        if not loan.start_date: continue
        start = date(loan.start_date.year, loan.start_date.month, 1)
        end = date(end_of_month.year, end_of_month.month, 1)
        
        months_passed = (end.year - start.year) * 12 + (end.month - start.month) + 1
        # Loans might not have payment_terms, use end_date if exists
        if loan.end_date:
            loan_end = date(loan.end_date.year, loan.end_date.month, 1)
            months_possible = (loan_end.year - start.year) * 12 + (loan_end.month - start.month) + 1
            months_to_bill = min(months_passed, months_possible)
        else:
            months_to_bill = months_passed
            
        total_loans += (loan.monthly_payment or 0.0) * months_to_bill

    return (total_swipes + total_inst + total_loans) - total_paid


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
        dates.extend([inst.end_date for inst in items if inst.end_date])
    if loans:
        dates.extend([loan.end_date for loan in loans if loan.end_date])
            
    if not dates:
        return "No active debt"
        
    return max(dates).strftime("%B %Y")
