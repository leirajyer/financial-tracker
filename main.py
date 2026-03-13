from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime as dt

# 1. Standardize your Base import (Use the one from your models package)
from app.database import engine, get_db
from app.models.base import Base

# 2. IMPORT THE MODELS EXPLICITLY
# This fixes the NameError for CashFlow and Installment in your index function
from app.models import CashFlow, Installment

from app.services.debt import calculate_monthly_totals

# 3. Create the tables in Postgres (Only need this once)
Base.metadata.create_all(bind=engine)

from app.routes import (
    installments_router,
    forecast_router,
    settings_router,
    cashflow_router,
    auth_router,
)

from starlette.middleware.sessions import SessionMiddleware
from app.core.auth import get_current_user, SECRET_KEY

from app.core.ui import templates
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

app = FastAPI(title="PesoPulse Financial Tracker")

# Handle proxy headers for HTTPS redirection (critical for Railway/Render)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Required for Google OAuth state tracking
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Middleware to add current_user to all template contexts
@app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    db: Session = next(get_db())
    user = await get_current_user(request, db)
    request.state.user = user

    # Public paths that don't require login
    public_paths = ["/login", "/register", "/auth", "/static", "/favicon.ico"]
    
    is_public = any(request.url.path.startswith(path) for path in public_paths)
    
    if not user and not is_public:
        return RedirectResponse(url="/login", status_code=303)
        
    response = await call_next(request)
    return response

# Standardize templates to always include current_user
templates.env.globals["current_user"] = None # Placeholder


from app.seed import seed_db

@app.on_event("startup")
async def startup_event():
    seed_db()


# ... router includes ...
app.include_router(installments_router)
app.include_router(forecast_router)
app.include_router(settings_router)
app.include_router(cashflow_router)
app.include_router(auth_router)


@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    user = request.state.user
    stats = calculate_monthly_totals(db, user_id=user.id)
    
    recent_cashflow = (
        db.query(CashFlow)
        .filter(CashFlow.owner_id == user.id)
        .order_by(CashFlow.id.desc())
        .limit(5)
        .all()
    )
    active_installments = (
        db.query(Installment)
        .filter(Installment.owner_id == user.id, Installment.status == "active")
        .all()
    )

    from app.core.ui import render_template
    return render_template(
        "index.html",
        request,
        {
            "recent_cashflow": recent_cashflow,
            "installments": active_installments,
            "now": dt.now(),
            **stats,
        },
    )
