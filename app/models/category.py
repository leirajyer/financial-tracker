from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    name = Column(String) # Removed unique=True to allow different users to have same category name
    color = Column(String, default="#10b981")  # Added for your color feature

    # Use strings here so SQLAlchemy waits for all files to load
    installments = relationship(
        "app.models.installment.Installment", back_populates="category"
    )
    cash_flows = relationship("app.models.cashflow.CashFlow", back_populates="category")

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("app.models.user.User", back_populates="categories")
