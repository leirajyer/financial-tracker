from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base


class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    due_day = Column(Integer, default=15)
    color = Column(String, default="#6366f1")

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
