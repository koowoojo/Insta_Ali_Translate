"""GET /showcase/{job_id} 라우트 단위 테스트."""

from __future__ import annotations

import sys
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base

# web import 체인에서 worker.pipeline(moviepy 등) 로드를 막기 위한 스텁
_worker_pipeline_stub = MagicMock()
_worker_pipeline_stub.job_asset_dir = MagicMock()
sys.modules["worker.pipeline"] = _worker_pipeline_stub

_worker_tasks_stub = MagicMock()
_worker_tasks_stub.process_video_job = MagicMock()
sys.modules["worker.tasks"] = _worker_tasks_stub

# db.session 모듈 로드 전 Settings 스텁
_settings_mock = MagicMock(
    database_url="sqlite:///:memory:",
    redis_url="redis://localhost:6379/0",
)
_patch_settings = patch("utils.config.get_settings", return_value=_settings_mock)
_patch_settings.start()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """StaticPool 인메모리 DB와 get_db override가 적용된 TestClient."""
    from web.app import app
    from web.deps import get_db

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    db.close()


def test_showcase_404_when_missing(client: TestClient):
    """존재하지 않는 job_id 요청 시 404를 반환하는지 확인."""
    r = client.get("/showcase/nonexistent-id")
    assert r.status_code == 404
