from sqlalchemy.orm import Session
from app.models import Category


def get_all_categories(db: Session):
    """Fetch all categories sorted alphabetically."""
    return db.query(Category).order_by(Category.name).all()


def get_category_by_id(db: Session, category_id: int):
    """Retrieve a specific category."""
    return db.query(Category).filter(Category.id == category_id).first()


def create_category(db: Session, name: str, color: str = "#94a3b8"):
    """Create a new category with a custom hex color."""
    new_cat = Category(name=name.strip(), color=color)
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat


def delete_category(db: Session, category_id: int):
    category = db.query(Category).filter(Category.id == category_id).first()
    if category:
        db.delete(category)
        db.commit()
    return True
