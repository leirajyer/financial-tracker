# app/models/base.py
from sqlalchemy.ext.declarative import declarative_base

# Every model in your app MUST inherit from THIS specific Base.
Base = declarative_base()
