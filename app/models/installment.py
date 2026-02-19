from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import date
from dateutil.relativedelta import relativedelta
from .base import Base


class Installment(Base):
    __tablename__ = "installments"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    total_amount = Column(Float)
    monthly_payment = Column(Float)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String, default="active")

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
        return max((diff.years * 12) + diff.months + 1, 1)

    def get_progress(self):
        today = date.today()
        total = self.total_months_count
        if today < self.start_date:
            return {"percent": 0, "current": 0, "total": total}
        diff = relativedelta(today, self.start_date)
        current = min((diff.years * 12) + diff.months + 1, total)
        return {
            "percent": round((current / total) * 100, 1),
            "current": current,
            "total": total,
        }
