from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from .base import Base


class Payee(Base):
    __tablename__ = "payees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    # Relationship points to the Installment model by string name
    installments = relationship("Installment", back_populates="payee")
