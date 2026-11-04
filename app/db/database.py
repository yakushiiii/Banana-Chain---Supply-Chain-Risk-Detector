import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


load_dotenv()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy database models."""
    pass


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create a database engine using DATABASE_URL."""

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Check your .env file."
        )

    # Use psycopg 3 with the existing PostgreSQL connection string.
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 5,
    },
)

def get_session_factory():
    """Create a factory for database sessions."""

    return sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
    )