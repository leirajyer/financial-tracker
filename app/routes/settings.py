from fastapi import APIRouter, Depends, Form, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi.responses import RedirectResponse, Response
from app.database import get_db
from app.models import Card, Category, Payee, Installment, CashFlow

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    user = request.state.user
    cards = db.query(Card).filter(Card.owner_id == user.id).order_by(Card.name).all()
    payees = db.query(Payee).filter(or_(Payee.owner_id == user.id, Payee.owner_id == None)).order_by(Payee.name).all()
    
    # Deduplicate categories by name, prioritizing user-owned ones
    all_cats = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id == None)).order_by(Category.name).all()
    cat_dict = {}
    for cat in all_cats:
        if cat.name not in cat_dict or cat.owner_id is not None:
            cat_dict[cat.name] = cat
    categories = sorted(cat_dict.values(), key=lambda x: x.name)

    from app.core.ui import render_template
    return render_template(
        "settings.html",
        request,
        {
            "cards": cards,
            "payees": payees,
            "categories": categories,
        },
    )


@router.post("/add-card")
async def add_card(
    request: Request,
    name: str = Form(...),
    due_day: int = Form(15),
    card_limit: float = Form(0.0),
    color: str = Form("#6366f1"),
    db: Session = Depends(get_db),
):
    user = request.state.user
    name = name.strip()
    
    # Validation & Duplicate Check
    if not name:
        return _error_response(request, "Card name cannot be empty")
    
    existing = db.query(Card).filter(Card.name == name, Card.owner_id == user.id).first()
    if existing:
        return _error_response(request, f"Card '{name}' already exists")
    
    if not (1 <= due_day <= 31):
        return _error_response(request, "Due day must be between 1 and 31")

    db.add(Card(name=name, due_day=due_day, card_limit=card_limit, color=color, owner_id=user.id))
    db.commit()
    
    redirect_url = request.headers.get("referer", "/settings/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Credit Card added successfully!")
    return response


@router.post("/add-category")
async def add_category(
    request: Request, name: str = Form(...), color: str = Form(...), db: Session = Depends(get_db)
):
    user = request.state.user
    name = name.strip()

    if not name:
        return _error_response(request, "Category name cannot be empty")

    existing = db.query(Category).filter(
        Category.name == name, 
        or_(Category.owner_id == user.id, Category.owner_id == None)
    ).first()
    
    if existing:
        return _error_response(request, f"Category '{name}' already exists")

    new_cat = Category(name=name, color=color, owner_id=user.id)
    db.add(new_cat)
    db.commit()
    
    redirect_url = request.headers.get("referer", "/settings/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Category created successfully!")
    return response


@router.post("/add-payee")
async def add_payee(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    user = request.state.user
    name = name.strip()

    if not name:
        return _error_response(request, "Payee name cannot be empty")

    existing = db.query(Payee).filter(
        Payee.name == name,
        or_(Payee.owner_id == user.id, Payee.owner_id == None)
    ).first()
    
    if existing:
        return _error_response(request, f"Payee '{name}' already exists")

    db.add(Payee(name=name, owner_id=user.id))
    db.commit()
    
    redirect_url = request.headers.get("referer", "/settings/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Payee added successfully!")
    return response


# DELETE ROUTES
@router.delete("/delete-card/{id}")
@router.post("/delete-card/{id}")
async def delete_card(request: Request, id: int, db: Session = Depends(get_db)):
    user = request.state.user
    card = db.query(Card).filter(Card.id == id, Card.owner_id == user.id).first()
    if not card:
        return RedirectResponse(url="/settings/", status_code=303)

    if db.query(Installment).filter(Installment.card_id == id).first():
        if "hx-request" in request.headers:
            response = Response(status_code=200)
            response.headers["HX-Reswap"] = "none"
            response.set_cookie(key="toast_msg", value="Error: Card is linked to an installment!")
            return response
        raise HTTPException(status_code=400, detail="Cannot delete Card; it is linked to an existing installment.")
        
    db.delete(card)
    db.commit()
    
    if "hx-request" in request.headers:
        response = Response(status_code=200)
        response.set_cookie(key="toast_msg", value="Credit Card removed.")
        return response
    
    redirect_url = request.headers.get("referer", "/installments/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Credit Card removed.")
    return response


@router.post("/delete-category/{id}")
async def delete_category(request: Request, id: int, db: Session = Depends(get_db)):
    user = request.state.user
    
    cat = db.query(Category).filter(
        Category.id == id, 
        or_(Category.owner_id == user.id, Category.owner_id.is_(None))
    ).first()

    if not cat:
        return _error_response(request, "Category not found")
    
    
    # Check if category is protected name
    if cat.name == "Credit Card":
        return _error_response(request, "Error: 'Credit Card' category is system-protected!")
    
    # Block deleting system-wide categories
    if cat.owner_id is None:
        return _error_response(request, "Error: System categories cannot be deleted.")

    # Explicit ownership check
    if cat.owner_id != user.id:
        return _error_response(request, "Error: You do not have permission to delete this category.")

    if db.query(Installment).filter(Installment.category_id == id).first() or \
       db.query(CashFlow).filter(CashFlow.category_id == id).first():
        if "hx-request" in request.headers:
            response = Response(status_code=200)
            response.headers["HX-Reswap"] = "none"
            response.set_cookie(key="toast_msg", value="Error: Category is currently in use!")
            return response
        raise HTTPException(status_code=400, detail="Cannot delete Category; it is linked to a transaction or installment.")
        
    db.delete(cat)
    db.commit()
    
    if "hx-request" in request.headers:
        response = Response(status_code=200)
        response.set_cookie(key="toast_msg", value="Category removed.")
        return response
        
    redirect_url = request.headers.get("referer", "/installments/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Category removed.")
    return response

@router.delete("/delete-payee/{id}")
@router.post("/delete-payee/{id}")
async def delete_payee(request: Request, id: int, db: Session = Depends(get_db)):
    user = request.state.user
    payee = db.query(Payee).filter(Payee.id == id, Payee.owner_id == user.id).first()
    if not payee:
        return RedirectResponse(url="/settings/", status_code=303)

    if db.query(Installment).filter(Installment.payee_id == id).first():
        if "hx-request" in request.headers:
            response = Response(status_code=200)
            response.headers["HX-Reswap"] = "none"
            response.set_cookie(key="toast_msg", value="Error: Payee is linked to an installment!")
            return response
        raise HTTPException(status_code=400, detail="Cannot delete Payee; it is linked to an existing installment.")
        
    db.delete(payee)
    db.commit()
    
    if "hx-request" in request.headers:
        response = Response(status_code=200)
        response.set_cookie(key="toast_msg", value="Payee removed.")
        return response
        
    redirect_url = request.headers.get("referer", "/installments/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Payee removed.")
    return response


# EDIT ROUTES
@router.post("/edit-card/{id}")
async def edit_card(
    request: Request,
    id: int,
    name: str = Form(...),
    due_day: int = Form(15),
    card_limit: float = Form(0.0),
    color: str = Form("#6366f1"),
    db: Session = Depends(get_db),
):
    user = request.state.user
    card = db.query(Card).filter(Card.id == id, Card.owner_id == user.id).first()
    if not card:
        return _error_response(request, "Card not found")

    new_name = name.strip()
    if not new_name:
        return _error_response(request, "Card name cannot be empty")

    # If the name is changing, check for duplicates
    if new_name != card.name:
        existing = db.query(Card).filter(Card.name == new_name, Card.owner_id == user.id).first()
        if existing:
            return _error_response(request, f"Card '{new_name}' already exists")

    if not (1 <= due_day <= 31):
        return _error_response(request, "Due day must be between 1 and 31")

    card.name = new_name
    card.due_day = due_day
    card.card_limit = card_limit
    card.color = color
    db.commit()
    redirect_url = request.headers.get("referer", "/installments/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Card updated successfully!")
    return response

@router.post("/edit-category/{id}")
async def edit_category(
    request: Request,
    id: int,
    name: str = Form(...),
    color: str = Form("#8b5cf6"),
    db: Session = Depends(get_db),
):
    user = request.state.user
    
    cat = db.query(Category).filter(
        Category.id == id,
        or_(Category.owner_id == user.id, Category.owner_id.is_(None))
    ).first()
    
    if not cat:
        return _error_response(request, "Category not found")
    
    
    if cat.name == "Credit Card":
        return _error_response(request, "Error: 'Credit Card' category is system-protected and cannot be edited.")

    if cat.owner_id is None:
        return _error_response(request, "Error: System categories cannot be edited.")

    new_name = name.strip()
    if not new_name:
        return _error_response(request, "Category name cannot be empty")

    if new_name != cat.name:
        existing = db.query(Category).filter(
            Category.name == new_name, 
            or_(Category.owner_id == user.id, Category.owner_id == None)
        ).first()
        if existing:
            return _error_response(request, f"Category '{new_name}' already exists")

    cat.name = new_name
    cat.color = color
    db.commit()
    
    redirect_url = request.headers.get("referer", "/settings/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Category updated successfully!")
    return response

@router.post("/edit-payee/{id}")
async def edit_payee(
    request: Request,
    id: int,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    user = request.state.user
    payee = db.query(Payee).filter(Payee.id == id, Payee.owner_id == user.id).first()
    if not payee:
        return _error_response(request, "Payee not found")

    new_name = name.strip()
    if not new_name:
        return _error_response(request, "Payee name cannot be empty")

    if new_name != payee.name:
        existing = db.query(Payee).filter(
            Payee.name == new_name,
            or_(Payee.owner_id == user.id, Payee.owner_id == None)
        ).first()
        if existing:
            return _error_response(request, f"Payee '{new_name}' already exists")

    payee.name = new_name
    db.commit()
    redirect_url = request.headers.get("referer", "/settings/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Payee updated successfully!")
    return response

def _error_response(request: Request, message: str):
    """Helper to return errors via toast without breaking HTMX if used."""
    redirect_url = request.headers.get("referer", "/settings/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    # Prefix with Error: to help UI distinguish
    msg = message if message.startswith("Error:") else f"Error: {message}"
    response.set_cookie(key="toast_msg", value=msg)
    return response
