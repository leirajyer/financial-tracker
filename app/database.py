import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Docker injects DATABASE_URL. Local dev defaults to SQLite.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db")

# Railway/Render often use 'postgres://' which SQLAlchemy 1.4+ rejects.
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

IS_SQLITE = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    # SQLite: allow multi-threaded access (needed for FastAPI async)
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL (Railway / Render):
    # - pool_pre_ping: reconnects automatically if server closed the connection
    # - pool_recycle=270: rotate before Railway's ~5min idle timeout kills them
    # - pool_size=2, max_overflow=2: with 2 gunicorn workers this = 8 max connections
    #   safely under the Railway free-tier limit of 25
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=270,
        pool_size=2,
        max_overflow=2,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
