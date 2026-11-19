import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from settings import settings

TEST_URL = settings.make_url("banana_test")


@pytest.fixture(scope="session")
def alembic_cfg():
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    return cfg


@pytest.fixture(scope="session")
def engine(alembic_cfg):
    command.upgrade(alembic_cfg, "head")
    eng = create_engine(TEST_URL)
    yield eng
    eng.dispose()
    command.downgrade(alembic_cfg, "base")


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()  # tests flush but never commit, so each test starts clean