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
    # - pool_pre_ping: test connection health before each checkout → fixes "Connection reset by peer"
    # - pool_recycle: replace connections older than 4.5 min before the cloud DB kills them (~5 min idle timeout)
    # - pool_size / max_overflow: conservative limits for free-tier (max 5 + 5 = 10 concurrent connections)
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=270,
        pool_size=5,
        max_overflow=5,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
