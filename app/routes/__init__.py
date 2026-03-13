# from .dashboard import router as dashboard_router
from .cashflow import router as cashflow_router
from .installments import router as installments_router
from .forecast import router as forecast_router
from .settings import router as settings_router
from .auth import router as auth_router
from .reports import router as reports_router

__all__ = [
    "cashflow_router",
    "installments_router",
    "forecast_router",
    "settings_router",
    "auth_router",
    "reports_router",
]
