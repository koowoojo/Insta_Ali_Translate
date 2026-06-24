"""
SQLite 테이블 초기화 스크립트.

`python db/init_db.py` 실행 시 settings.database_url에 연결된 DB에
jobs·job_logs 테이블을 생성한다. 기존 테이블이 있으면 create_all은 건너뛴다.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 — `python db/init_db.py` 직접 실행 지원
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from db.models import Base
from db.session import _ensure_sqlite_directory, engine
from utils.config import get_settings
from utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def init_db() -> None:
    """설정된 DATABASE_URL에 모든 ORM 테이블을 생성한다."""
    database_url = get_settings().database_url
    _ensure_sqlite_directory(database_url)
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized: %s", database_url)


if __name__ == "__main__":
    setup_logging()
    init_db()
    print(f"Database tables created at {get_settings().database_url}")
