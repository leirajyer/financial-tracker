import traceback
from fastapi.testclient import TestClient
from main import app
from app.models.user import User
from app.database import SessionLocal

try:
    from app.core.auth import get_password_hash
except ImportError:
    pass

def run():
    db = SessionLocal()
    user = db.query(User).first()
    if not user:
        user = User(email="test2@test.com", name="Test User", hashed_password=get_password_hash("pw"))
        db.add(user)
        db.commit()
    
    client = TestClient(app)
    # the normal login path expects application/x-www-form-urlencoded
    # Let's just spoof the token or do a real login
    resp = client.post("/auth/token", data={"username": user.email, "password": "pw"})
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        client.cookies.set("access_token", f"Bearer {token}")
    
    try:
        r2 = client.get("/")
        print("Status Code:", r2.status_code)
        if r2.status_code == 500:
            print("Server returned 500!")
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    run()
