from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.models.base import Base


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    due_day = Column(Integer, default=15)  # Keep this
    card_limit = Column(Float, default=0.0)  # ADD THIS LINE
    color = Column(String, default="#6366f1")

    installments = relationship(
        "app.models.installment.Installment", back_populates="card"
    )
    monthly_statuses = relationship("CardMonthlyStatus", back_populates="card")

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("app.models.user.User", back_populates="cards")


class CardMonthlyStatus(Base):
    __tablename__ = "card_monthly_statuses"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("cards.id"))
    month_year = Column(String)
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime, nullable=True)

    card = relationship("Card", back_populates="monthly_statuses")
