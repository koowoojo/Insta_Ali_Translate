"""
HTML 쇼케이스 페이지 서빙.

완료된 Job의 Opal 스타일 showcase.html을 GET /showcase/{job_id} 로 제공한다.
DB의 showcase_path가 있으면 우선 사용하고, 없으면 표준 assets 경로를 조회한다.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db.models import Job
from web.deps import get_db

router = APIRouter(tags=["showcase"])


@router.get("/showcase/{job_id}")
def get_showcase(job_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """
    Job의 HTML 쇼케이스 파일을 반환한다.

    Args:
        job_id: Job UUID
        db: SQLAlchemy 세션 (FastAPI DI)

    Returns:
        showcase.html FileResponse

    Raises:
        HTTPException: Job 미존재(404) 또는 쇼케이스 파일 미생성(404)
    """
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # DB 저장 경로 우선, 없으면 파이프라인 표준 산출물 경로
    path = (
        Path(job.showcase_path)
        if job.showcase_path
        else Path(f"assets/jobs/{job_id}/showcase.html")
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="Showcase not ready")

    return FileResponse(path, media_type="text/html")
