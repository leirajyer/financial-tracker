from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date
from dateutil.relativedelta import relativedelta
import bcrypt

# Modular Imports from your app folder
from app.database import engine, SessionLocal, Base
from app.models import User, Card, Owner, Installment
from app.seed import seed_db
from app.logic import calculate_monthly_totals  # Add this import

# Initialize Database - Create tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_event():
    seed_db()


# --- AUTH ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not request.cookies.get("is_logged_in"):
        return RedirectResponse(url="/login")

    db = SessionLocal()
    # Get the calculated numbers
    stats = calculate_monthly_totals(db)
    db.close()

    return templates.TemplateResponse(
        "base.html",
        {
            "request": request,
            "total_burn": stats["total_burn"],
            "card_totals": stats["card_totals"],
        },
    )


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


@app.get("/get-list", response_class=HTMLResponse)
async def get_list(request: Request):
    db = SessionLocal()
    try:
        # 1. Fetch the raw installments
        records = db.query(Installment).all()

        # 2. Run the logic to get total_burn and card_totals
        stats = calculate_monthly_totals(db)

        # 3. Return the response with EVERY variable the template needs
        return templates.TemplateResponse(
            "partials/list.html",
            {
                "request": request,
                "records": records,
                "total_burn": stats["total_burn"],
                "card_totals": stats["card_totals"],
                "total_remaining": stats.get("total_remaining", 0),
            },
        )
    finally:
        db.close()


# --- HTMX SELECT LOADERS ---


@app.get("/get-owners")
async def get_owners():
    db = SessionLocal()
    owners = db.query(Owner).all()
    db.close()
    # Ensure value="{o.id}" has no extra escaped quotes
    options = '<option value="" disabled selected>Select Owner</option>'
    for o in owners:
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


@app.post("/add-owner")
async def add_owner(response: Response, name: str = Form(...)):
    db = SessionLocal()
    db.add(Owner(name=name))
    db.commit()
    db.close()
    response.headers["HX-Trigger"] = "ownerListChanged"
    return ""


@app.post("/add-installment")
async def add_installment(
    response: Response,
    description: str = Form(...),
    card_id: int = Form(...),
    total_amount: float = Form(...),
    total_months: int = Form(...),
    owner_id: int = Form(...),
    start_date: date = Form(...),
):
    # If user enters 0 or 1, it's a straight payment (1 month total)
    actual_months = total_months if total_months > 1 else 1
    monthly = total_amount / actual_months

    # Logic: Jan 1 to Feb 1 is 2 months.
    # So for a 12-month plan starting Jan 1, it should end Dec 1.
    if actual_months == 1:
        end_date = start_date
    else:
        end_date = start_date + relativedelta(months=actual_months - 1)

    db = SessionLocal()
    db.add(
        Installment(
            description=description,
            card_id=card_id,
            total_amount=total_amount,
            monthly_payment=monthly,
            owner_id=owner_id,
            start_date=start_date,
            end_date=end_date,
        )
    )
    db.commit()
    db.close()

    response.headers["HX-Trigger"] = "listChanged"
    return f'<div class="p-2 bg-green-100 text-green-700 rounded text-sm">✅ Added Successfully</div>'


@app.delete("/delete-installment/{item_id}")
async def delete_installment(item_id: int):
    db = SessionLocal()
    item = db.query(Installment).filter(Installment.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
    db.close()
    return ""
