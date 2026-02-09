from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime as dt

from app.database import engine, Base, get_db
from app.services.debt import calculate_monthly_totals
from app.models import Card, Payee
from app.seed import seed_db
from app.routes import dashboard_router, installments_router
from app.routes.forecast import router as forecast_router
from app.routes.settings import router as settings_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="PesoPulse Financial Tracker")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_event():
    seed_db()


# ==========================================
# 🚀 REGISTER ROUTERS
# ==========================================
app.include_router(dashboard_router)
app.include_router(installments_router)
app.include_router(forecast_router)
app.include_router(settings_router)


@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
        },
    )


@app.get("/installments")
async def index(request: Request, db: Session = Depends(get_db)):
    now = dt.now()
    stats = calculate_monthly_totals(db, year=now.year, month=now.month)
    return templates.TemplateResponse(
        "installments.html",
        {
            "request": request,
            "now": dt.now(),
            "total_burn": stats["total_burn"],
            "total_due": stats["total_due"],
            "cards": db.query(Card).all(),
            "payees": db.query(Payee).all(),
        },
    )


@app.get("/records")
async def records_page(request: Request, db: Session = Depends(get_db)):
    stats = calculate_monthly_totals(db)
    return templates.TemplateResponse(
        "records_page.html",
        {
            "request": request,
            "now": dt.now(),
            "total_burn": stats["total_burn"],
        },
    )
