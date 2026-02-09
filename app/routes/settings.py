from app.services.debt import get_global_updates_fragment
from app.routes.dashboard import templates
from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Card, Payee, Category, Installment, CashFlow
from app.services import category as category_service
from datetime import datetime

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    cards = db.query(Card).order_by(Card.name).all()
    payees = db.query(Payee).order_by(Payee.name).all()
    # Fetch categories for the third column
    categories = category_service.get_all_categories(db)

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "cards": cards,
            "payees": payees,
            "categories": categories,
            "active_page": "settings",
        },
    )


@router.post("/add-card")
async def add_card(
    request: Request,
    name: str = Form(...),
    color: str = Form("#6366f1"),
    db: Session = Depends(get_db),
):
    # 1. Logic: Create the new card
    new_card = Card(name=name.strip(), color=color)
    db.add(new_card)
    db.commit()

    # 2. Data: Get updated card list
    cards = db.query(Card).order_by(Card.name).all()

    # 3. Render: The updated list wrapped in the OOB shell
    # This matches the <div id="card-list"> on your settings page
    list_html = f"""
    <div id="card-list" hx-swap-oob="true" class="grid grid-cols-2 gap-2">
        {templates.get_template("partials/settings_card_list.html").render({"cards": cards})}
    </div>
    """

    # 4. Global: Get the Toast and Navbar updates
    now = datetime.now()
    global_html = get_global_updates_fragment(
        db, now.year, now.month, toast_msg=f"Card '{name}' Added!"
    )

    # 5. Response: Return combined HTML fragments
    return HTMLResponse(content=list_html + global_html)


@router.post("/add-category")
async def add_category(
    request: Request,
    name: str = Form(...),
    color: str = Form("#94a3b8"),
    db: Session = Depends(get_db),
):
    # 1. Save
    category_service.create_category(db, name=name.strip(), color=color)

    # 2. Get fresh data
    categories = category_service.get_all_categories(db)

    # 3. Render the partial wrapped in the OOB shell
    # This ensures HTMX knows exactly which div to replace on the settings page
    list_html = f"""
    <div id="category-list" hx-swap-oob="true" class="grid grid-cols-2 gap-2">
        {templates.get_template("partials/settings_category_list.html").render({"categories": categories})}
    </div>
    """

    # 4. Add the Toast/Global sync
    global_html = get_global_updates_fragment(
        db, datetime.now().year, datetime.now().month, toast_msg=f"Added {name}"
    )

    return HTMLResponse(content=list_html + global_html)


@router.post("/categories/seed")
async def seed_categories_route(request: Request, db: Session = Depends(get_db)):
    category_service.seed_default_categories(db)
    categories = category_service.get_all_categories(db)

    list_html = templates.TemplateResponse(
        "partials/settings_category_list.html",
        {"request": request, "categories": categories},
    ).body.decode()

    return HTMLResponse(content=list_html)


# Add Payee remains the same as your snippet...
@router.post("/add-payee")
async def add_payee(
    request: Request, name: str = Form(...), db: Session = Depends(get_db)
):
    new_payee = Payee(name=name.strip())
    db.add(new_payee)
    db.commit()
    payees = db.query(Payee).order_by(Payee.name).all()
    list_html = templates.TemplateResponse(
        "partials/settings_payee_list.html", {"request": request, "payees": payees}
    ).body.decode()
    now = datetime.now()
    global_html = get_global_updates_fragment(
        db, now.year, now.month, toast_msg=f"Payee '{name}' Added!"
    )
    return HTMLResponse(content=list_html + global_html)


from fastapi import Response


# --- DELETE CARD ---
@router.delete("/delete-card/{card_id}")
async def delete_card(request: Request, card_id: int, db: Session = Depends(get_db)):
    # 1. Fetch the card
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        return Response(status_code=404)

    # 2. SAFETY CHECK: Is this card tied to any installments?
    # If we delete a card with active debt, the dashboard won't be able
    # to calculate "Available Credit" or "Total Debt per Card."
    used_in_debt = db.query(Installment).filter(Installment.card_id == card_id).first()

    if used_in_debt:
        # Stop and send a warning Toast via OOB
        global_html = get_global_updates_fragment(
            db,
            datetime.now().year,
            datetime.now().month,
            toast_msg=f"❌ Cannot delete '{card.name}': It still has active installments!",
        )
        return HTMLResponse(content=global_html)

    # 3. If safe, proceed with deletion
    card_name = card.name
    db.delete(card)
    db.commit()

    # 4. Fetch updated list for the UI
    cards = db.query(Card).order_by(Card.name).all()

    # 5. Render the OOB Fragment for the grid list
    # Matching the grid-cols-2 layout from Category and Payee
    list_html = f"""
    <div id="card-list" hx-swap-oob="true" class="grid grid-cols-2 gap-2">
        {templates.get_template("partials/settings_card_list.html").render({"cards": cards, "request": request})}
    </div>
    """

    # 6. Success Toast
    global_html = get_global_updates_fragment(
        db,
        datetime.now().year,
        datetime.now().month,
        toast_msg=f"🗑️ Card '{card_name}' successfully removed.",
    )

    return HTMLResponse(content=list_html + global_html)


# --- DELETE PAYEE ---
@router.delete("/delete-payee/{payee_id}")
async def delete_payee(request: Request, payee_id: int, db: Session = Depends(get_db)):
    # 1. Fetch the payee
    payee = db.query(Payee).filter(Payee.id == payee_id).first()
    if not payee:
        return Response(status_code=404)

    # 2. SAFETY CHECK: Is this payee tied to any installments?
    # We check Installments because deleting a used Payee would leave
    # the debt list with "Unknown" or broken links.
    used_in_debt = (
        db.query(Installment).filter(Installment.payee_id == payee_id).first()
    )

    if used_in_debt:
        # Stop and send a warning Toast
        global_html = get_global_updates_fragment(
            db,
            datetime.now().year,
            datetime.now().month,
            toast_msg=f"❌ Cannot delete '{payee.name}': It is linked to active debt!",
        )
        return HTMLResponse(content=global_html)

    # 3. If safe, proceed with deletion
    payee_name = payee.name
    db.delete(payee)
    db.commit()

    # 4. Fetch updated list for the UI
    payees = db.query(Payee).order_by(Payee.name).all()

    # 5. Render the OOB Fragment for the grid list
    # Note: Using grid-cols-2 to match your Card and Category layouts
    list_html = f"""
    <div id="payee-list" hx-swap-oob="true" class="grid grid-cols-2 gap-2">
        {templates.get_template("partials/settings_payee_list.html").render({"payees": payees, "request": request})}
    </div>
    """

    # 6. Success Toast
    global_html = get_global_updates_fragment(
        db,
        datetime.now().year,
        datetime.now().month,
        toast_msg=f"🗑️ Payee '{payee_name}' removed.",
    )

    return HTMLResponse(content=list_html + global_html)


# --- DELETE CATEGORY ---
@router.delete("/delete-category/{cat_id}")
async def delete_category(request: Request, cat_id: int, db: Session = Depends(get_db)):
    # 1. Fetch the category
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        return Response(status_code=404)

    # 2. SAFETY CHECK: Is this category linked to any records?
    # Check Installments (Debt)
    used_in_debt = (
        db.query(Installment).filter(Installment.category_id == cat_id).first()
    )
    # Check CashFlow (Variable Expenses/Income)
    used_in_flow = db.query(CashFlow).filter(CashFlow.category_id == cat_id).first()

    if used_in_debt or used_in_flow:
        # Prevent deletion and send a warning Toast via OOB
        global_html = get_global_updates_fragment(
            db,
            datetime.now().year,
            datetime.now().month,
            toast_msg=f"❌ Cannot delete '{cat.name}': It is currently assigned to transactions!",
        )
        return HTMLResponse(content=global_html)

    # 3. If safe, proceed with deletion
    cat_name = cat.name
    db.delete(cat)
    db.commit()

    # 4. Fetch updated list for the UI
    categories = db.query(Category).order_by(Category.name).all()

    # 5. Render the OOB Fragment for the grid list
    list_html = f"""
    <div id="category-list" hx-swap-oob="true" class="grid grid-cols-2 gap-2">
        {templates.get_template("partials/settings_category_list.html").render({"categories": categories, "request": request})}
    </div>
    """

    # 6. Success Toast
    global_html = get_global_updates_fragment(
        db,
        datetime.now().year,
        datetime.now().month,
        toast_msg=f"🗑️ Category '{cat_name}' deleted.",
    )

    return HTMLResponse(content=list_html + global_html)
