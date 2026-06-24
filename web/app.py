"""
FastAPI 애플리케이션 진입점.

`uvicorn web.app:app --reload --port 8000` 으로 웹 대시보드를 기동한다.
/api/jobs REST API와 Jinja2 HTML 페이지, 정적 파일을 마운트한다.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db.models import Base
from db.session import engine
from web.routes import jobs, pages

# web/static — CSS·JS 등 정적 자산 (없어도 마운트 가능)
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 기동 시 SQLite 테이블을 보장한다."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Insta Ali Dashboard",
    description="AliExpress 숏폼 파이프라인 웹 대시보드",
    lifespan=lifespan,
)

# REST API — prefix /api → /api/jobs ...
app.include_router(jobs.router, prefix="/api")
# HTML 페이지 — /, /jobs, /jobs/{id}
app.include_router(pages.router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
