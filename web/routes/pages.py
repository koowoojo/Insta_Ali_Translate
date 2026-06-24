"""
HTML 대시보드 페이지 라우트.

Jinja2 템플릿으로 홈·작업 목록·작업 상세를 렌더링한다.
작업 목록은 HTMX 5초 폴링으로 테이블 본문을 자동 갱신한다.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db.models import Job
from web.deps import get_db

# web/templates 디렉터리 (모듈 기준 절대 경로)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["pages"])


def _fetch_jobs(db: Session) -> list[Job]:
    """최신순 작업 목록을 조회한다."""
    return db.query(Job).order_by(Job.created_at.desc()).all()


@router.get("/", response_class=HTMLResponse)
def index_page(request: Request) -> HTMLResponse:
    """홈 — 단건 URL 입력 폼 + CSV 업로드."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "새 작업"},
    )


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """작업 목록 페이지 (HTMX 폴링 대상 tbody 포함)."""
    jobs = _fetch_jobs(db)
    return templates.TemplateResponse(
        "jobs.html",
        {"request": request, "title": "작업 목록", "jobs": jobs},
    )


@router.get("/jobs/table-body", response_class=HTMLResponse)
def jobs_table_body(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """HTMX 5초 폴링용 작업 테이블 tbody 프래그먼트."""
    jobs = _fetch_jobs(db)
    return templates.TemplateResponse(
        "_jobs_table_body.html",
        {"request": request, "jobs": jobs},
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """작업 상세 — 단계 로그·에러·재시도·다운로드."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    logs = sorted(job.logs, key=lambda log: log.created_at or "")
    return templates.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "title": f"작업 {job_id[:8]}…",
            "job": job,
            "logs": logs,
        },
    )
