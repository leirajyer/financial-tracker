from app.database import SessionLocal
from app.models import Category, Payee


def seed_db():
    db = SessionLocal()
    try:
        # 1. Basic Categories (owner_id is None)
        basic_categories = [
            {"name": "Income", "color": "#10b981"},
            {"name": "Utilities", "color": "#3b82f6"},
            {"name": "Subscriptions", "color": "#8b5cf6"},
            {"name": "Food & Dining", "color": "#f59e0b"},
            {"name": "Transportation", "color": "#6366f1"},
            {"name": "Personal", "color": "#ec4899"},
            {"name": "Health", "color": "#ef4444"},
            {"name": "Savings", "color": "#06b6d4"},
            {"name": "Debt", "color": "#64748b"},
        ]

        for cat_data in basic_categories:
            existing = db.query(Category).filter(
                Category.name == cat_data["name"], 
                Category.owner_id == None
            ).first()
            if not existing:
                db.add(Category(**cat_data, owner_id=None))

        # 2. Default Payees (owner_id is None)
        default_payees = [
            "Owner",
        ]

        # Migration: Rename "Rey (Owner)" to "Owner" if found
        rey_owner = db.query(Payee).filter(Payee.name == "Rey (Owner)", Payee.owner_id == None).first()
        if rey_owner:
            rey_owner.name = "Owner"
            db.commit()

        for payee_name in default_payees:
            existing_payee = db.query(Payee).filter(
                Payee.name == payee_name,
                Payee.owner_id == None
            ).first()
            if not existing_payee:
                db.add(Payee(name=payee_name, owner_id=None))

        db.commit()
        print("✅ Basic categories and payees seeded successfully!")
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_db()
