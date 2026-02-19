from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import date
from .base import Base


class CashFlow(Base):
    __tablename__ = "cashflows"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, default=date.today)

    # Values should be 'income' or 'expense'
    type = Column(String, nullable=False)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Relationship points to the Category model by string name
    category = relationship("Category", back_populates="cash_flows")
