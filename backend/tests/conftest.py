import os
import tempfile
from pathlib import Path


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"careershield-pytest-{os.getpid()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"

from app.db import Base, engine
import app.models  # noqa: F401

Base.metadata.create_all(bind=engine)


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{TEST_DATABASE_PATH}{suffix}")
        if path.exists():
            path.unlink()
