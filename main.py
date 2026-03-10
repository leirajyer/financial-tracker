# main.py
from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime as dt

# 1. Standardize your Base import (Use the one from your models package)
from app.database import engine, get_db
from app.models.base import Base

# 2. IMPORT THE MODELS EXPLICITLY
# This fixes the NameError for CashFlow and Installment in your index function
from app.models import CashFlow, Installment

from app.services.debt import calculate_monthly_totals
from app.seed import seed_db


# 3. Debug Print
print("--- DATABASE SCHEMA CHECK ---")
print(f"Registered Tables: {list(Base.metadata.tables.keys())}")
print("-----------------------------")

# 4. Create the tables in Postgres (Only need this once)
Base.metadata.create_all(bind=engine)

from app.routes import (
    installments_router,
    forecast_router,
    settings_router,
    cashflow_router,
)

app = FastAPI(title="PesoPulse Financial Tracker")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_event():
    # This runs every time the container starts
    seed_db()


# ... router includes ...
app.include_router(installments_router)
app.include_router(forecast_router)
app.include_router(settings_router)
app.include_router(cashflow_router)


@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    stats = calculate_monthly_totals(db)
    # These now work because of the explicit import at the top
    recent_cashflow = db.query(CashFlow).order_by(CashFlow.id.desc()).limit(5).all()
    active_installments = (
        db.query(Installment).filter(Installment.status == "active").all()
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "recent_cashflow": recent_cashflow,
            "installments": active_installments,
            "now": dt.now(),
            **stats,
        },
    )
