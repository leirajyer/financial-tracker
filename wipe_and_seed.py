from app.database import SessionLocal
from app.models import CashFlow, Installment, CardMonthlyStatus, Card, Category, Payee, User, Loan
from app.seed import seed_db

def wipe_and_seed():
    db = SessionLocal()
    print("🧹 Starting full data wipe...")
    try:
        # Delete in order to respect potential foreign keys
        db.query(Installment).delete()
        db.query(CashFlow).delete()
        db.query(CardMonthlyStatus).delete()
        db.query(Loan).delete()
        db.query(Card).delete()
        db.query(Category).delete()
        db.query(Payee).delete()
        db.query(User).delete()
        db.commit()
        print("✅ All tables cleared.")
    except Exception as e:
        db.rollback()
        print(f"❌ Wipe failed: {e}")
        return
    finally:
        db.close()

    print("🌱 Re-seeding default data...")
    seed_db()
    print("✨ Process complete. your database is fresh.")

if __name__ == "__main__":
    wipe_and_seed()
