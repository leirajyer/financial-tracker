from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime as dt, date
from dateutil.relativedelta import relativedelta
from .base import Base

class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    description = Column(String)
    amount = Column(Float)
    interest_rate = Column(Float)  # Fixed annual rate
    terms_years = Column(Integer)  # Term in years
    start_date = Column(Date, default=date.today)
    
    # Calculated Fields
    monthly_payment = Column(Float)
    total_to_pay = Column(Float)  # Total including interest
    
    # Audit
    status = Column(String, default="active") # active, closed
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)

    # Relationships
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("app.models.category.Category", backref="loans")
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("app.models.user.User", backref="loans")

    def calculate_payment(self):
        """Calculates monthly payment using standard loan amortization formula."""
        if not self.amount or not self.terms_years:
            return 
            
        r = (self.interest_rate / 100) / 12  # Monthly rate
        n = self.terms_years * 12  # Number of payments
        
        if r == 0:
            self.monthly_payment = self.amount / n
        else:
            self.monthly_payment = (self.amount * r * (1 + r)**n) / ((1 + r)**n - 1)
            
        self.total_to_pay = self.monthly_payment * n

    @property
    def end_date(self):
        if not self.start_date or not self.terms_years:
            return None
        return self.start_date + relativedelta(years=self.terms_years)

    def get_progress(self):
        """Calculates current payment progress."""
        today = date.today()
        total_months = self.terms_years * 12

        if today < self.start_date:
            return {"percent": 0, "current": 0, "total": total_months}

        diff = relativedelta(today, self.start_date)
        current = min((diff.years * 12) + diff.months + 1, total_months)

        return {
            "percent": round((current / total_months) * 100, 1) if total_months > 0 else 0,
            "current": current,
            "total": total_months,
        }

    def get_remaining_balance(self):
        progress = self.get_progress()
        remaining = self.total_to_pay - (self.monthly_payment * progress["current"])
        return max(round(remaining, 2), 0)
