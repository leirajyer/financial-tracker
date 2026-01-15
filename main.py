from app.models import CardMonthlyStatus
from fastapi import FastAPI, Request, Form, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import joinedload
from typing import Optional

import datetime
from datetime import datetime as dt
import bcrypt

# Modular Imports from your app folder
from app.database import engine, SessionLocal, Base
from app.models import User, Card, Payee, Installment
from app.seed import seed_db
from app.logic import get_monthly_forecast
from app.logic import calculate_monthly_totals
from app.logic import get_card_status

# Initialize Database - Create tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_event():
    seed_db()


# --- AUTH ROUTES ---
@app.get("/")
async def index(request: Request):
    db = SessionLocal()
    try:
        # 1. Use the full path for now
        now_obj = datetime.datetime.now()

        # 2. Get your existing stats
        stats = calculate_monthly_totals(db)
        cards = db.query(Card).all()
        payees = db.query(Payee).all()

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "now": now_obj,  # Pass the fixed object
                "total_burn": stats["total_burn"],
                "cards": cards,
                "payees": payees,
            },
        )
    finally:
        db.close()


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()

    if user and bcrypt.checkpw(
        password.encode("utf-8"), user.hashed_password.encode("utf-8")
    ):
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="is_logged_in", value="true")
        return response

    return HTMLResponse(
        content="<p class='text-red-500'>Invalid credentials</p>", status_code=401
    )


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("is_logged_in")
    return response


@app.get("/get-list")
async def get_list(request: Request):
    db = SessionLocal()
    try:
        # We explicitly JOIN card and payee here
        records = (
            db.query(Installment)
            .options(joinedload(Installment.card), joinedload(Installment.payee))
            .order_by(Installment.start_date.desc())
            .all()
        )

        # Calculate stats for the summary/list total if needed
        stats = calculate_monthly_totals(db)

        return templates.TemplateResponse(
            "partials/list.html",
            {"request": request, "records": records, "total_burn": stats["total_burn"]},
        )
    finally:
        db.close()  # Now the door closes, but the data is already inside 'records'


# --- HTMX SELECT LOADERS ---


@app.get("/get-payee")
async def get_payee():
    db = SessionLocal()
    payee = db.query(Payee).all()
    db.close()
    # Ensure value="{o.id}" has no extra escaped quotes
    options = '<option value="" disabled selected>Select Payee</option>'
    for o in payee:
        options += f"<option value={o.id}>{o.name}</option>"
    return options


@app.get("/get-cards")
async def get_cards():
    db = SessionLocal()
    cards = db.query(Card).all()
    db.close()
    options = '<option value="" disabled selected>Select Card</option>'
    for c in cards:
        options += f"<option value={c.id}>{c.name}</option>"
    return options


# --- ADD DATA ROUTES ---


@app.post("/add-card")
async def add_card(response: Response, name: str = Form(...)):
    db = SessionLocal()
    db.add(Card(name=name))
    db.commit()
    db.close()
    response.headers["HX-Trigger"] = "cardListChanged"
    return ""


@app.post("/add-payee")
async def add_payee(response: Response, name: str = Form(...)):
    db = SessionLocal()
    db.add(Payee(name=name))
    db.commit()
    db.close()
    response.headers["HX-Trigger"] = "ownerListChanged"
    return ""


@app.post("/add-installment")
async def add_installment(
    request: Request,
    description: str = Form(...),
    card_id: int = Form(...),
    total_amount: float = Form(...),
    total_months: int = Form(...),
    payee_id: int = Form(...),
    start_period: str = Form(...),
):
    # 1. Logic for Date Calculation (Keep this exactly as you had it)
    start_date = datetime.datetime.strptime(start_period, "%Y-%m").date()
    actual_months = total_months if total_months > 1 else 1
    monthly = total_amount / actual_months

    if actual_months == 1:
        end_date = start_date
    else:
        end_date = start_date + relativedelta(months=actual_months - 1)

    # 2. Database Save
    db = SessionLocal()
    new_item = Installment(
        description=description,
        card_id=card_id,
        total_amount=total_amount,
        monthly_payment=monthly,
        payee_id=payee_id,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(new_item)
    db.commit()
    db.close()

    # 3. REDIRECT vs SWAP
    # Since we are on a dedicated /add page, we want to go back to the list.
    # We use the HX-Location header to tell HTMX to "navigate" to the records page.

    return Response(headers={"HX-Location": "/records"})


@app.delete("/delete-installment/{item_id}")
async def delete_installment(request: Request, item_id: int):
    db = SessionLocal()
    try:
        # 1. Find and delete the item
        item = db.query(Installment).filter(Installment.id == item_id).first()
        if item:
            db.delete(item)
            db.commit()

        # 2. Fetch fresh records WITH Card and Payee data
        # This is the part that prevents the Error on line 41!
        records = (
            db.query(Installment)
            .options(joinedload(Installment.card), joinedload(Installment.payee))
            .order_by(Installment.start_date.desc())
            .all()
        )

        # 3. Recalculate stats for the OOB summary update
        stats = calculate_monthly_totals(db)

        # 4. Prepare the OOB summary
        summary_html = templates.get_template("partials/summary.html").render(
            {"request": request, **stats}
        )
        summary_oob = (
            f'<div id="summary-container" hx-swap-oob="true">{summary_html}</div>'
        )

        # 5. Return the list (HTMX will swap this into the list container)
        return templates.TemplateResponse(
            "partials/list.html",
            {"request": request, "records": records, "total_burn": stats["total_burn"]},
            headers={"Content-Type": "text/html"},  # Ensure browser treats it as HTML
        )
    finally:
        db.close()  # Safely close after all data is fetched


@app.get("/get-summary")
async def get_summary(request: Request):
    db = SessionLocal()
    try:
        # Use your existing logic function to get totals
        stats = calculate_monthly_totals(db)

        return templates.TemplateResponse(
            "partials/summary.html",
            {
                "request": request,
                "total_burn": stats["total_burn"],
                "card_totals": stats["card_totals"],
                "total_remaining": stats.get("total_remaining", 0),
            },
        )
    finally:
        db.close()


# Payee
@app.post("/add-payee")
async def add_payee(response: Response, name: str = Form(...)):
    db = SessionLocal()
    existing = db.query(Payee).filter(Payee.name == name).first()
    if not existing:
        db.add(Payee(name=name))
        db.commit()
    db.close()
    # Trigger refresh for the Payee dropdown in the main form
    response.headers["HX-Trigger"] = "payeeAdded"
    return '<div class="text-green-600 text-xs font-bold">✓ Payee Added</div>'


@app.get("/get-payees")
async def get_payees(request: Request):
    db = SessionLocal()
    payees = db.query(Payee).all()
    db.close()
    # Returns the <option> list for the select element
    options = "".join([f'<option value="{p.id}">{p.name}</option>' for p in payees])
    return HTMLResponse(
        content=f'<option value="" disabled selected>Select Payee</option>{options}'
    )


# Forecast
# @app.get("/get-forecast")
# async def get_forecast(request: Request, forecast_period: str = None):
#     # Fallback: If for some reason forecast_period is missing, use current month
#     if not forecast_period:
#         forecast_period = datetime.now().strftime("%Y-%m")

#     try:
#         yr, mo = map(int, forecast_period.split("-"))

#         db = SessionLocal()
#         # Using our logic from Step 2 with eager loading
#         data = get_monthly_forecast(db, yr, mo)
#         db.close()

#         return templates.TemplateResponse(
#             "partials/forecast.html", {"request": request, **data}
#         )
#     except Exception as e:
#         print(f"Forecast Error: {e}")
#         return HTMLResponse(f"Error: {str(e)}", status_code=500)


@app.get("/get-forecast")
async def get_forecast(
    request: Request,
    forecast_period: str = None,
    card_id: Optional[str] = Query(None),
    payee_id: Optional[str] = Query(None),
):
    # 1. Standardize Date Handling (using full path to avoid AttributeError)
    now_obj = datetime.datetime.now()

    if not forecast_period or not forecast_period.strip():
        yr, mo = now_obj.year, now_obj.month
    else:
        try:
            yr, mo = map(int, forecast_period.split("-"))
        except (ValueError, AttributeError):
            yr, mo = now_obj.year, now_obj.month

    # 2. Critical: Convert Query Strings to Integers for the DB logic
    c_id = int(card_id) if card_id and card_id.strip() and card_id != "None" else None
    p_id = (
        int(payee_id) if payee_id and payee_id.strip() and payee_id != "None" else None
    )

    db = SessionLocal()
    try:
        data = get_monthly_forecast(db, yr, mo, card_id=c_id, payee_id=p_id)

        return templates.TemplateResponse(
            "partials/forecast.html",
            {
                "request": request,
                "now": now_obj,
                "items": data.get("items", []),
                "total_due": data.get("total_due", 0.0),
                "card_data": data.get("card_data", {}),  # The new name
                "card_split": data.get(
                    "card_data", {}
                ),  # ALIAS to stop the UndefinedError
                "month_name": data.get("month_name", "Unknown"),
                "year": yr,
                "month": mo,
            },
        )
    finally:
        db.close()


@app.get("/records")
async def records_page(request: Request):
    db = SessionLocal()
    try:
        stats = calculate_monthly_totals(db)
        # ... your other logic (fetching cards, installments, etc.) ...

        return templates.TemplateResponse(
            "records_page.html",
            {
                "request": request,
                "now": datetime.datetime.now(),  # <--- FIX: Change this line
                "total_burn": stats["total_burn"],
            },
        )
    finally:
        db.close()


@app.get("/add")
async def add_page(request: Request):
    db = SessionLocal()
    try:
        # We need the stats for the Navbar ticker
        stats = calculate_monthly_totals(db)

        return templates.TemplateResponse(
            "add_page.html",
            {
                "request": request,
                "now": datetime.datetime.now(),
                "total_burn": stats["total_burn"],
            },
        )
    finally:
        db.close()


@app.get("/add-form")
async def get_add_form(request: Request):
    # We pass 'now' so the 'Starting Month' input can default to the current month
    return templates.TemplateResponse(
        "partials/form.html", {"request": request, "now": datetime.datetime.now()}
    )


@app.post("/toggle-card-status/{card_id}/{year}/{month}")
async def toggle_card_status(card_id: int, year: int, month: int):
    db = SessionLocal()
    period = f"{year}-{month:02d}"

    status_record = (
        db.query(CardMonthlyStatus)
        .filter(
            CardMonthlyStatus.card_id == card_id, CardMonthlyStatus.month_year == period
        )
        .first()
    )

    if not status_record:
        # If no record exists, they clicked it, so we mark it as PAID
        status_record = CardMonthlyStatus(
            card_id=card_id,
            month_year=period,
            is_paid=True,
            paid_at=datetime.datetime.now(),
        )
        db.add(status_record)
    else:
        # Toggle the existing state
        status_record.is_paid = not status_record.is_paid
        status_record.paid_at = (
            datetime.datetime.now() if status_record.is_paid else None
        )

    db.commit()

    # 1. Get the fresh status string ("PAID", "PENDING", or "OVERDUE")
    # This calls your smart logic to see if it should be yellow or red if unpaid
    new_status = get_card_status(db, card_id, year, month)
    db.close()

    # 2. Return the HTML Badge fragment
    # We MUST pass card_id, year, and month so the new button is also clickable
    return HTMLResponse(content=render_status_badge(new_status, card_id, year, month))

    # Get new status to return the correct badge
    new_status = get_card_status(db, card_id, year, month)
    db.close()

    # Return just the badge HTML (You can extract this to a small partial)
    # For now, we return a simple string or the partial
    return HTMLResponse(content=render_status_badge(new_status))  # Create this helper!


def render_status_badge(status, card_id, year, month):
    # CSS logic based on status
    if status == "PAID":
        styles = "bg-emerald-100 text-emerald-700 border-emerald-200"
    elif status == "OVERDUE":
        styles = "bg-rose-100 text-rose-700 border-rose-200 animate-pulse"
    else:
        styles = "bg-amber-100 text-amber-700 border-amber-200"

    # We rebuild the <div> so HTMX can swap it perfectly
    return f"""
    <div id="status-badge-{card_id}" 
         hx-post="/toggle-card-status/{card_id}/{year}/{month}"
         hx-swap="outerHTML"
         class="cursor-pointer px-3 py-1 rounded-full text-[10px] font-black border transition-all {styles}">
        {status}
    </div>
    """
