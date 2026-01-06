# Database Imports
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# --- DATABASE SETUP ---
DATABASE_URL = "sqlite:///./installments.db"

# 1. Create the engine with standard SQLite arguments ONLY
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# 2. Disable RETURNING globally using execution_options
# This prevents the 'RETURNING' error on older Macs without crashing the engine
engine = engine.execution_options(insert_returning=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
