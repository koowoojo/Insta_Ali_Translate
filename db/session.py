"""
SQLAlchemy 동기 엔진·세션 팩토리.

`utils.config.get_settings()`의 `database_url`로 엔진을 구성하고,
RQ 워커·FastAPI 라우트에서 `get_sync_session()`으로 세션을 얻는다.
호출 측은 `finally: db.close()`로 세션을 반드시 닫아야 한다.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from utils.config import get_settings

# --- 모듈 수준 엔진·세션 팩토리 (앱/워커 프로세스당 1회 구성) ---


def _ensure_sqlite_directory(database_url: str) -> None:
    """
    파일 기반 SQLite URL이면 DB 파일 부모 디렉터리를 생성한다.

    `sqlite:///:memory:` 또는 상대·절대 경로 `sqlite:///db/jobs.db` 모두 처리한다.
    """
    if not database_url.startswith("sqlite:///"):
        return
    # sqlite:/// 접두사 제거 후 실제 파일 경로 추출
    db_file = database_url.removeprefix("sqlite:///")
    if db_file == ":memory:":
        return
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)


# settings.database_url 기반 동기 엔진 (SQLite check_same_thread=False)
_settings = get_settings()
_ensure_sqlite_directory(_settings.database_url)

engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)

# autocommit/autoflush 비활성 — 명시적 commit 패턴 사용
_SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_sync_session() -> Session:
    """
    새 SQLAlchemy 동기 세션을 반환한다.

    사용 예::
        db = get_sync_session()
        try:
            ...
            db.commit()
        finally:
            db.close()
    """
    return _SessionLocal()
