from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from app.database import get_db
from app.models import Card, Category, Payee  # Ensure these are imported

router = APIRouter(prefix="/settings", tags=["settings"])


@router.post("/add-card")
async def add_card(
    name: str = Form(...), color: str = Form("#6366f1"), db: Session = Depends(get_db)
):
    db.add(Card(name=name, color=color))
    db.commit()
    return RedirectResponse(url="/installments/", status_code=303)


@router.post("/add-category")
async def add_category(
    name: str = Form(...), color: str = Form(...), db: Session = Depends(get_db)
):
    new_cat = Category(name=name, color=color)
    db.add(new_cat)
    db.commit()
    return RedirectResponse(url="/installments/", status_code=303)


@router.post("/add-payee")
async def add_payee(name: str = Form(...), db: Session = Depends(get_db)):
    db.add(Payee(name=name))
    db.commit()
    return RedirectResponse(url="/installments/", status_code=303)


# DELETE ROUTES
@router.post("/delete-card/{id}")
async def delete_card(id: int, db: Session = Depends(get_db)):
    db.query(Card).filter(Card.id == id).delete()
    db.commit()
    return RedirectResponse(url="/installments/", status_code=303)


@router.post("/delete-category/{id}")
async def delete_category(id: int, db: Session = Depends(get_db)):
    db.query(Category).filter(Category.id == id).delete()
    db.commit()
    return RedirectResponse(url="/installments/", status_code=303)


# EDIT ROUTES
@router.post("/edit-card/{id}")
async def edit_card(id: int, name: str = Form(...), db: Session = Depends(get_db)):
    card = db.query(Card).filter(Card.id == id).first()
    if card:
        card.name = name
        db.commit()
    return RedirectResponse(url="/installments/", status_code=303)
