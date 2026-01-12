from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import date
from dateutil.relativedelta import (
    relativedelta,
)  # You'll need to pip install python-dateutil


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)


class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    installments = relationship("Installment", back_populates="card")


class Payee(Base):
    __tablename__ = "payees"  # Renamed table
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    # Update the relationship back-reference
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

    card = relationship("Card", back_populates="installments")
    payee = relationship("Payee", back_populates="installments")

    @property
    def total_months_count(self):
        """Calculates total months including the first and last month."""
        if not self.start_date or not self.end_date:
            return 1
        diff = relativedelta(self.end_date, self.start_date)
        # We add 1 so Jan to Jan = 1 month, Jan to Feb = 2 months
        total = (diff.years * 12) + diff.months + 1
        return total if total > 0 else 1

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
        return months_left * self.monthly_payment if months_left > 0 else 0.0
