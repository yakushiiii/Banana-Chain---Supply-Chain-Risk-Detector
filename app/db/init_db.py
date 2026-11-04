from sqlalchemy import inspect

from app.db.database import Base, get_engine
from app.db import models


def init_db():
    """Initialize the Banana Chain database tables."""

    engine = get_engine()

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    print("Database tables initialized.")
    print("Tables:", sorted(inspector.get_table_names()))


if __name__ == "__main__":
    init_db()