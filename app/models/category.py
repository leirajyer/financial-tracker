from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from .base import Base


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, default="#94a3b8")

    # Use strings ONLY. SQLAlchemy will find them in the global registry
    # as long as they all share the same Base.
    installments = relationship("Installment", back_populates="category")
    cash_flows = relationship("CashFlow", back_populates="category")
