from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.models.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    cash_flows = relationship("app.models.cashflow.CashFlow", back_populates="owner")
    installments = relationship("app.models.installment.Installment", back_populates="owner")
    cards = relationship("app.models.card.Card", back_populates="owner")
    categories = relationship("app.models.category.Category", back_populates="owner")
    payees = relationship("app.models.payee.Payee", back_populates="owner")
