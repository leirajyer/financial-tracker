from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    ForeignKey,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import relationship
from .database import Base
from datetime import date
from dateutil.relativedelta import relativedelta


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, default="#94a3b8")  # Default Slate color

    # Unified links for both CC Debt and CashFlow
    installments = relationship("Installment", back_populates="category")
    cash_flows = relationship("CashFlow", back_populates="category")


class Payee(Base):
    __tablename__ = "payees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    installments = relationship("Installment", back_populates="payee")


class Installment(Base):
    __tablename__ = "installments"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    total_amount = Column(Float)
    monthly_payment = Column(Float)
    start_date = Column(Date)
    end_date = Column(Date)

    card_id = Column(Integer, ForeignKey("cards.id"))
    payee_id = Column(Integer, ForeignKey("payees.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    category = relationship("Category", back_populates="installments")
    card = relationship("Card", back_populates="installments")
    payee = relationship("Payee", back_populates="installments")

    @property
    def total_months_count(self):
        if not self.start_date or not self.end_date:
            return 1
        diff = relativedelta(self.end_date, self.start_date)
        total = (diff.years * 12) + diff.months + 1
        return max(total, 1)

    def get_progress(self):
        today = date.today()
        total = self.total_months_count
        if today < self.start_date:
            return {"percent": 0, "current": 0, "total": total}
        diff = relativedelta(today, self.start_date)
        current = (diff.years * 12) + diff.months + 1
        current_capped = min(current, total)
        percent = (current_capped / total) * 100
        return {"percent": round(percent, 1), "current": current_capped, "total": total}

    def get_remaining_balance(self):
        prog = self.get_progress()
        months_left = prog["total"] - prog["current"]
        return float(months_left * self.monthly_payment) if months_left > 0 else 0.0


class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    due_day = Column(Integer, default=15)
    color = Column(String, default="#6366f1")  # Default Indigo

    installments = relationship("Installment", back_populates="card")
    monthly_statuses = relationship("CardMonthlyStatus", back_populates="card")


class CardMonthlyStatus(Base):
    __tablename__ = "card_monthly_statuses"
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("cards.id"))
    month_year = Column(String)
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime, nullable=True)

    card = relationship("Card", back_populates="monthly_statuses")


class CashFlow(Base):
    __tablename__ = "cash_flows"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)  # e.g., "Salary", "Rent"
    amount = Column(Float)  # Positive = Income, Negative = Expense
    is_recurring = Column(Boolean, default=True)
    month_year = Column(String, nullable=True)  # "2026-02"

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="cash_flows")
