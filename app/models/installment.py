from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import date, datetime as dt
from dateutil.relativedelta import relativedelta
from .base import Base


class Installment(Base):
    __tablename__ = "installments"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    description = Column(String)
    total_amount = Column(Float)
    interest_rate = Column(Float)
    monthly_payment = Column(Float)
    payment_terms = Column(Integer)
    start_date = Column(Date)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)

    # Foreign Keys
    card_id = Column(Integer, ForeignKey("cards.id"))
    payee_id = Column(Integer, ForeignKey("payees.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # FIXED RELATIONSHIPS: Use strings here
    category = relationship(
        "app.models.category.Category", back_populates="installments"
    )
    card = relationship("app.models.card.Card", back_populates="installments")
    payee = relationship("app.models.payee.Payee", back_populates="installments")

    @property
    def total_to_pay(self):
        """Principal + Total Interest."""
        return (self.total_amount or 0.0) + (self.interest_rate or 0.0)

    @property
    def end_date(self):
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