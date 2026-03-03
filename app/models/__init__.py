# app/models/__init__.py

# 1. Import the Base first
from .base import Base

# 2. Import models that are referenced by others (The "Leaves")
from .user import User
from .card import Card, CardMonthlyStatus
from .payee import Payee

# 3. Import models that reference the above (The "Branches")
# Moving Installment up can help Category find it during initialization
from .installment import Installment
from .cashflow import CashFlow

# 4. Finally, import Category
from .category import Category

__all__ = [
    "Base",
    "User",
    "Category",
    "Payee",
    "Card",
    "CardMonthlyStatus",
    "CashFlow",
    "Installment",
]
