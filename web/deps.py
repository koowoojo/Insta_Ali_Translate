"""
FastAPI 공통 의존성.

SQLAlchemy 동기 세션을 요청 단위로 주입·정리한다.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from db.session import get_sync_session


def get_db() -> Generator[Session, None, None]:
    """
    요청마다 SQLAlchemy 세션을 생성하고 응답 후 close한다.

    Yields:
        SQLAlchemy 동기 Session
    """
    db = get_sync_session()
    try:
        yield db
    finally:
        db.close()
