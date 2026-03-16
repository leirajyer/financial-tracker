import httpx
from app.database import SessionLocal
from app.models import Category, Payee, Card, User
import sys

import time

BASE_URL = "http://127.0.0.1:8000"
TS = int(time.time())

def run_qa():
    print("🧪 Starting Backend QA Test Suite...")
    
    with httpx.Client(base_url=BASE_URL, follow_redirects=False) as client:
        # 1. Registration
        print(f"\n[1] testing Registration for qa_tester_{TS}...")
        reg_data = {
            "username": f"qa_tester_{TS}", 
            "email": f"qa_{TS}@test.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        resp = client.post("/register", data=reg_data)
        if resp.status_code == 303:
            print("✅ Registration successful")
        else:
            print(f"❌ Registration failed: {resp.status_code}")

        # 2. Login
        print("\n[2] testing Login...")
        login_data = {"username": f"qa_tester_{TS}", "password": "password123"}
        resp = client.post("/login", data=login_data)
        if resp.status_code == 303:
            print("✅ Login successful")
            print(f"DEBUG: Session Cookies: {client.cookies}")
        else:
            print(f"❌ Login failed: {resp.status_code}")
            return

        # 3. Settings - Protected Category Check
        print("\n[3] testing 'Credit Card' Protection...")
        db = SessionLocal()
        cc_cat = db.query(Category).filter(Category.name == "Credit Card").first()
        db.close()
        
        if cc_cat:
            print(f"DEBUG: Testing Category ID {cc_cat.id} (owner_id={cc_cat.owner_id})")
            # Try to delete it
            resp = client.post(f"/settings/delete-category/{cc_cat.id}")
            print(f"DEBUG: Delete Status: {resp.status_code}, Location: {resp.headers.get('location')}")
            toast = resp.cookies.get("toast_msg", "")
            print(f"Debug: Deletion toast cookie: {toast}")
            if "Error: 'Credit Card' category is system-protected" in toast:
                 print("✅ Deletion protection works")
            else:
                 print(f"❌ Deletion protection FAILED.")

            # Try to edit it
            resp = client.post(f"/settings/edit-category/{cc_cat.id}", data={"name": "Modified CC", "color": "#000000"})
            print(f"DEBUG: Edit Status: {resp.status_code}, Location: {resp.headers.get('location')}")
            toast = resp.cookies.get("toast_msg", "")
            print(f"Debug: Editing toast cookie: {toast}")
            if "Error: 'Credit Card' category is system-protected" in toast:
                 print("✅ Editing protection works")
            else:
                 print(f"❌ Editing protection FAILED.")
        else:
            print("⚠️ 'Credit Card' category not found in DB - seeding might have failed")

        # 4. Settings - Duplicate Check
        print("\n[4] testing Duplicate Category Validation...")
        resp = client.post("/settings/add-category", data={"name": "Utilities", "color": "#000000"})
        if "Error: Category 'Utilities' already exists" in resp.cookies.get("toast_msg", ""):
            print("✅ Duplicate category check works")
        else:
            print("❌ Duplicate category check FAILED")

        # 5. Settings - Card Validation
        print("\n[5] testing Card Validation (Due Day)...")
        resp = client.post("/settings/add-card", data={"name": "Bad Card", "due_day": 40, "card_limit": 1000})
        if "Error: Due day must be between 1 and 31" in resp.cookies.get("toast_msg", ""):
            print("✅ Card day validation works")
        else:
            print("❌ Card day validation FAILED")

        # 6. Success Case - Adding Card
        print("\n[6] testing Valid Card Addition...")
        resp = client.post("/settings/add-card", data={"name": f"QA Visa {TS}", "due_day":10, "card_limit":50000})
        toast = resp.cookies.get("toast_msg", "")
        if "Credit Card added successfully" in toast:
            print("✅ Card added successfully")
        else:
            print(f"❌ Card addition FAILED. Cookie: {toast}")

    print("\n🏁 QA Backend Tests Complete.")

if __name__ == "__main__":
    run_qa()
