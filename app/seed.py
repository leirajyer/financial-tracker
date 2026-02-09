import bcrypt
from .database import SessionLocal
from .models import User, Card, Payee, Category
from .services import category as category_service


def seed_db():
    db = SessionLocal()
    print("🌱 Starting database seed...")

    try:
        # 1. Seed Users
        accounts = [{"u": "admin", "p": "admin4321"}, {"u": "admin2", "p": "admin4321"}]
        for acc in accounts:
            exists = db.query(User).filter(User.username == acc["u"]).first()
            if not exists:
                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(acc["p"].encode("utf-8"), salt)
                new_user = User(
                    username=acc["u"], hashed_password=hashed.decode("utf-8")
                )
                db.add(new_user)
                print(f"✅ User Created: {acc['u']}")

        # 2. Seed Payees
        if db.query(Payee).count() == 0:
            for name in ["Owner"]:
                db.add(Payee(name=name))
            print("✅ Payees seeded.")

        # 3. Seed Cards with specific colors
        if db.query(Card).count() == 0:
            card_list = [
                {"name": "BDO", "color": "#0033a0"},
            ]
            for c in card_list:
                db.add(Card(name=c["name"], color=c["color"]))
            print("✅ Cards seeded with colors.")

        # 4. Seed Basic Categories (Electrical, Water, Subscription)
        # We manually define these here to ensure the colors match your preference
        category_list = [
            {"name": "Electrical", "color": "#fbbf24"},  # Amber
            {"name": "Water", "color": "#3b82f6"},  # Blue
            {"name": "Subscription", "color": "#a855f7"},  # Purple
            {"name": "Salary", "color": "#10b981"},  # Emerald
            {"name": "Dining", "color": "#f43f5e"},  # Rose
        ]

        for cat in category_list:
            exists = db.query(Category).filter(Category.name == cat["name"]).first()
            if not exists:
                db.add(Category(name=cat["name"], color=cat["color"]))
                print(f"✅ Category Created: {cat['name']}")

        db.commit()
        print("🚀 Seeding completed successfully!")

    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_db()
