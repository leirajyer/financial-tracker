from sqlalchemy import Column, Integer, ForeignKey, String, Float, Date
from sqlalchemy.orm import relationship
from datetime import date
from .base import Base


class CashFlow(Base):
    __tablename__ = "cash_flows"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    description = Column(String)
    amount = Column(Float, nullable=False)
    # ADD THIS: "type" (Income or Expense)
    type = Column(String)
    # ADD THIS: "date"
    date = Column(Date, default=date.today)

    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("app.models.category.Category", back_populates="cash_flows")

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("app.models.user.User", back_populates="cash_flows")
