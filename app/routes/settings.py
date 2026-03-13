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
    categories = db.query(Category).filter(or_(Category.owner_id == user.id, Category.owner_id == None)).order_by(Category.name).all()

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
    db.add(Card(name=name, due_day=due_day, card_limit=card_limit, color=color, owner_id=user.id))
    db.commit()
    redirect_url = request.headers.get("referer", "/installments/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Credit Card added successfully!")
    return response


@router.post("/add-category")
async def add_category(
    request: Request, name: str = Form(...), color: str = Form(...), db: Session = Depends(get_db)
):
    user = request.state.user
    new_cat = Category(name=name, color=color, owner_id=user.id)
    db.add(new_cat)
    db.commit()
    redirect_url = request.headers.get("referer", "/installments/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Category created successfully!")
    return response


@router.post("/add-payee")
async def add_payee(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    user = request.state.user
    db.add(Payee(name=name, owner_id=user.id))
    db.commit()
    redirect_url = request.headers.get("referer", "/installments/")
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


@router.delete("/delete-category/{id}")
@router.post("/delete-category/{id}")
async def delete_category(request: Request, id: int, db: Session = Depends(get_db)):
    user = request.state.user
    cat = db.query(Category).filter(Category.id == id, Category.owner_id == user.id).first()
    if not cat:
        return RedirectResponse(url="/settings/", status_code=303)

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
    if card:
        card.name = name
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
    cat = db.query(Category).filter(Category.id == id, Category.owner_id == user.id).first()
    if cat:
        cat.name = name
        cat.color = color
        db.commit()
    redirect_url = request.headers.get("referer", "/installments/")
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
    if payee:
        payee.name = name
        db.commit()
    redirect_url = request.headers.get("referer", "/installments/")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="toast_msg", value="Payee updated successfully!")
    return response
