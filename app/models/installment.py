from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import date
from dateutil.relativedelta import relativedelta
from .base import Base

from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import date
from dateutil.relativedelta import relativedelta
from .base import Base


class Installment(Base):
    __tablename__ = "installments"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)

    # Financials
    total_amount = Column(Float)  # The Principal (e.g., 50,000)
    interest_rate = Column(Float, default=0.0)
    monthly_payment = Column(Float)  # (Principal + Total Interest) / Terms
    payment_terms = Column(Integer, default=1)  # Total months (e.g., 12)

    start_date = Column(Date)
    status = Column(String, default="active")

    # Foreign Keys
    card_id = Column(Integer, ForeignKey("cards.id"))
    payee_id = Column(Integer, ForeignKey("payees.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Relationships
    category = relationship("Category", back_populates="installments")
    card = relationship("Card", back_populates="installments")
    payee = relationship("Payee", back_populates="installments")

    @property
    def total_to_pay(self):
        """Principal + Total Interest."""
        return (self.total_amount or 0.0) + (self.interest_rate or 0.0)

    @property
    def end_date(self):
        """
        Calculates the completion date.
        For Straight Payment (terms=1): Returns start_date + 1 month.
        For Installments (terms > 1): Returns start_date + (terms - 1) months.
        """
        if not self.start_date or not self.payment_terms:
            return None

        if self.payment_terms == 1:
            # Straight payment is due the very next month
            return self.start_date + relativedelta(months=1)

        # Standard installment logic
        return self.start_date + relativedelta(months=self.payment_terms - 1)

    @property
    def total_months_count(self):
        """Uses payment_terms as the primary source of truth."""
        return self.payment_terms if self.payment_terms else 1

    def get_progress(self):
        """Calculates current payment progress."""
        today = date.today()
        total = self.total_months_count

        if today < self.start_date:
            return {"percent": 0, "current": 0, "total": total}

        diff = relativedelta(today, self.start_date)
        # +1 because the first payment is usually billed in the start month
        current = min((diff.years * 12) + diff.months + 1, total)

        return {
            "percent": round((current / total) * 100, 1) if total > 0 else 0,
            "current": current,
            "total": total,
        }

    def get_remaining_balance(self):
        """
        Calculates remaining debt based on the Total Amount to Pay (including interest).
        """
        progress = self.get_progress()
        # Remaining = (Principal + Total Interest) - (Monthly Payment * Months Paid)
        remaining = self.total_to_pay - (self.monthly_payment * progress["current"])
        return max(round(remaining, 2), 0)
