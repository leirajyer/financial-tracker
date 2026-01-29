from app.routes.dashboard import templates
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Card, Payee
from app.logic import get_global_updates_fragment
from datetime import datetime

router = APIRouter()

# app/routes/settings.py


@router.post("/add-card")
async def add_card(
    request: Request, name: str = Form(...), db: Session = Depends(get_db)
):
    # 1. Save the new card
    new_card = Card(name=name.strip())
    db.add(new_card)
    db.commit()

    # 2. Fetch the UPDATED list of cards
    cards = db.query(Card).order_by(Card.name).all()

    # 3. Render the partial (This contains hx-swap-oob="true")
    list_html = templates.TemplateResponse(
        "partials/settings_card_list.html", {"request": request, "cards": cards}
    ).body.decode()

    # 4. Add the Toast notification (Global Sync)
    now = datetime.now()
    global_html = get_global_updates_fragment(
        db, now.year, now.month, toast_msg=f"Card '{name}' Added!"
    )

    # Combine both. HTMX handles the rest!
    return HTMLResponse(content=list_html + global_html)


@router.post("/add-payee")
async def add_payee(
    request: Request, name: str = Form(...), db: Session = Depends(get_db)
):
    # 1. Save the new payee
    new_payee = Payee(name=name.strip())
    db.add(new_payee)
    db.commit()

    # 2. Fetch the UPDATED list
    payees = db.query(Payee).order_by(Payee.name).all()

    # 3. Render the partial (This contains hx-swap-oob="true")
    list_html = templates.TemplateResponse(
        "partials/settings_payee_list.html", {"request": request, "payees": payees}
    ).body.decode()

    # 4. Add Toast
    now = datetime.now()
    global_html = get_global_updates_fragment(
        db, now.year, now.month, toast_msg=f"Payee '{name}' Added!"
    )

    return HTMLResponse(content=list_html + global_html)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    cards = db.query(Card).order_by(Card.name).all()
    payees = db.query(Payee).order_by(Payee.name).all()

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "cards": cards,
            "payees": payees,
            "active_page": "settings",  # Useful if you want to highlight the nav link
        },
    )


@router.post("/add-card")
async def add_card(
    request: Request, name: str = Form(...), db: Session = Depends(get_db)
):
    # ... (save logic from before) ...

    # 1. Fetch updated list
    cards = db.query(Card).order_by(Card.name).all()

    # 2. Render the partial OOB
    list_html = templates.TemplateResponse(
        "partials/settings_card_list.html", {"request": request, "cards": cards}
    ).body.decode()

    # 3. Add global toast
    global_html = get_global_updates_fragment(db, 2026, 1, toast_msg="Card Added!")

    return HTMLResponse(content=list_html + global_html)
