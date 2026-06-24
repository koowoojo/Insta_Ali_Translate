"""FastAPI web API — POST /api/jobs 단위 테스트 (RQ enqueue mock)."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Job

# db.session 모듈 로드 전 Settings 스텁
_settings_mock = MagicMock(
    database_url="sqlite:///:memory:",
    redis_url="redis://localhost:6379/0",
)
_patch_settings = patch("utils.config.get_settings", return_value=_settings_mock)
_patch_settings.start()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """인메모리 SQLite 세션과 jobs 테이블."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """get_db·enqueue_video_job을 mock한 TestClient."""
    from web.app import app
    from web.deps import get_db

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with patch("web.routes.jobs.enqueue_video_job") as mock_enqueue:
        with TestClient(app) as test_client:
            test_client.mock_enqueue = mock_enqueue  # type: ignore[attr-defined]
            yield test_client

    app.dependency_overrides.clear()


def test_create_job_returns_id(client: TestClient, db_session: Session):
    """POST /api/jobs 가 id·status를 반환하고 RQ enqueue를 호출하는지 확인."""
    resp = client.post("/api/jobs", json={"url": "https://aliexpress.com/item/1"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["status"] == "pending"

    assert client.mock_enqueue.called  # type: ignore[attr-defined]
    call_args = client.mock_enqueue.call_args[0]  # type: ignore[attr-defined]
    assert call_args[0] == data["id"]
    assert call_args[1] == "https://aliexpress.com/item/1"

    assert db_session.query(Job).count() == 1
    job = db_session.query(Job).first()
    assert job is not None
    assert job.url == "https://aliexpress.com/item/1"
    assert job.status == "pending"
