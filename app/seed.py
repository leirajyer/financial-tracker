from app.database import SessionLocal
from app.models import Card, Category, Payee


def seed_db():
    db = SessionLocal()
    try:
        # 1. Add Owner as a Special Payee
        owner = db.query(Payee).filter(Payee.name == "Rey (Owner)").first()
        if not owner:
            owner = Payee(name="Rey (Owner)")
            db.add(owner)
            db.commit()

        # 2. Add PH Credit Cards with Branding Colors
        ph_cards = [
            {
                "name": "BPI Blue Mastercard",
                "card_limit": 50000.0,
                "due_day": 10,  # Added this
                "color": "#0038A8",
            },
            {
                "name": "BDO ShopMore V2",
                "card_limit": 30000.0,
                "due_day": 15,  # Added this
                "color": "#FFD700",
            },
            {
                "name": "UnionBank Miles+",
                "card_limit": 100000.0,
                "due_day": 5,  # Added this
                "color": "#EE7624",
            },
            {
                "name": "Metrobank Titanium",
                "card_limit": 75000.0,
                "due_day": 12,  # Added this
                "color": "#004AAD",
            },
            {
                "name": "GCash GCredit",
                "card_limit": 10000.0,
                "due_day": 1,  # Added this
                "color": "#1E90FF",
            },
        ]

        for card_data in ph_cards:
            if not db.query(Card).filter(Card.name == card_data["name"]).first():
                db.add(Card(**card_data))

        # 3. Add Categories with Living Colors
        categories = [
            {"name": "Food & Dining", "color": "#FF6384"},  # Red/Pink
            {"name": "Housing & Utilities", "color": "#36A2EB"},  # Blue
            {"name": "Transportation", "color": "#FFCE56"},  # Yellow
            {"name": "Health & Wellness", "color": "#4BC0C0"},  # Teal
            {"name": "Shopping", "color": "#9966FF"},  # Purple
            {"name": "Entertainment", "color": "#FF9F40"},  # Orange
            {"name": "Internet & Mobile", "color": "#C9CBCF"},  # Grey
        ]

        for cat_data in categories:
            if not db.query(Category).filter(Category.name == cat_data["name"]).first():
                db.add(Category(**cat_data))

        db.commit()
        print("✅ Seeding with colors and owner successful!")
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_db()
