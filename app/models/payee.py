from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base


class Payee(Base):
    __tablename__ = "payees"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    name = Column(String) # Removed unique=True

    # Update this to use the full module path
    installments = relationship(
        "app.models.installment.Installment", back_populates="payee"
    )

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("app.models.user.User", back_populates="payees")
