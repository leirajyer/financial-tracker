import bcrypt
from .database import SessionLocal
from .models import User, Card, Payee


def seed_db():
    db = SessionLocal()

    # 1. Seed Users (Direct Bcrypt Method)
    accounts = [{"u": "admin", "p": "admin4321"}, {"u": "admin2", "p": "admin4321"}]
    for acc in accounts:
        exists = db.query(User).filter(User.username == acc["u"]).first()
        if not exists:
            # Hashing the password correctly
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(acc["p"].encode("utf-8"), salt)
            new_user = User(username=acc["u"], hashed_password=hashed.decode("utf-8"))
            db.add(new_user)
            print(f"✅ User Created: {acc['u']}")

    # 2. Seed Owners
    if db.query(Payee).count() == 0:
        for name in ["Owner"]:
            db.add(Payee(name=name))
        print("✅ Owners seeded.")

    # 3. Seed Cards
    if db.query(Card).count() == 0:
        card_list = [
            "Citi Simplicity",
            "Citi Cashback",
            "BDO",
            "Unionbank Gold",
            "HSBC Platinum",
            "RCBC",
            "JCB",
        ]
        for name in card_list:
            db.add(Card(name=name))
        print("✅ Cards seeded.")

    db.commit()
    db.close()
