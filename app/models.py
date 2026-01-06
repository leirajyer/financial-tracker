from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)


class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    installments = relationship("Installment", back_populates="card")


class Owner(Base):
    __tablename__ = "owners"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    installments = relationship("Installment", back_populates="owner")


class Installment(Base):
    __tablename__ = "installments"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    total_amount = Column(Float)
    monthly_payment = Column(Float)
    start_date = Column(Date)
    end_date = Column(Date)

    card_id = Column(Integer, ForeignKey("cards.id"))
    owner_id = Column(Integer, ForeignKey("owners.id"))

    card = relationship("Card", back_populates="installments")
    owner = relationship("Owner", back_populates="installments")
