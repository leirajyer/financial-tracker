# main.py
from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime as dt

from app.database import engine, get_db
from app.models import Base, CashFlow, Installment
from app.services.debt import calculate_monthly_totals
from app.seed import seed_db

# Import all routers
# from app.routes.dashboard import router as dashboard_router
from app.routes import (
    installments_router,
    forecast_router,
    settings_router,
    cashflow_router,
)

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="PesoPulse Financial Tracker")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_event():
    seed_db()


# ==========================================
# 🚀 REGISTER ROUTERS
# ==========================================
# app.include_router(dashboard_router)
app.include_router(installments_router)
app.include_router(forecast_router)
app.include_router(settings_router)
app.include_router(cashflow_router) 


@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    stats = calculate_monthly_totals(db)
    recent_cashflow = db.query(CashFlow).order_by(CashFlow.date.desc()).limit(5).all()
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
