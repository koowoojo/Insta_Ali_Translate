"""
Job REST API 라우트.

단건·배치 작업 생성, 목록·상세 조회, MP4 다운로드, 실패 작업 재시도를 제공한다.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.models import Job
from web.deps import get_db
from web.queue import enqueue_video_job
from worker.pipeline import job_asset_dir

router = APIRouter(prefix="/jobs", tags=["jobs"])


class CreateJobRequest(BaseModel):
    """POST /api/jobs 요청 본문."""

    url: str = Field(..., min_length=1, description="AliExpress 상품 URL")


class JobSummaryResponse(BaseModel):
    """작업 목록·생성 응답용 요약 필드."""

    id: str
    url: str
    status: str
    current_step: Optional[str] = None
    retry_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobLogResponse(BaseModel):
    """작업 상세의 단계별 로그 1건."""

    id: int
    step: str
    message: Optional[str] = None
    created_at: Optional[datetime] = None


class JobDetailResponse(JobSummaryResponse):
    """GET /api/jobs/{id} 상세 응답."""

    error_message: Optional[str] = None
    script_text: Optional[str] = None
    output_path: Optional[str] = None
    logs: list[JobLogResponse] = Field(default_factory=list)


class BatchCreateResponse(BaseModel):
    """CSV 배치 등록 결과."""

    created: list[JobSummaryResponse]
    count: int


def _job_summary(job: Job) -> JobSummaryResponse:
    """Job ORM → API 요약 dict 변환."""
    return JobSummaryResponse(
        id=job.id,
        url=job.url,
        status=job.status,
        current_step=job.current_step,
        retry_count=job.retry_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


def _job_detail(job: Job) -> JobDetailResponse:
    """Job ORM → 상세 응답(로그 포함) 변환."""
    logs = sorted(job.logs, key=lambda log: log.created_at or datetime.min)
    return JobDetailResponse(
        id=job.id,
        url=job.url,
        status=job.status,
        current_step=job.current_step,
        retry_count=job.retry_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        script_text=job.script_text,
        output_path=job.output_path,
        logs=[
            JobLogResponse(
                id=log.id,
                step=log.step,
                message=log.message,
                created_at=log.created_at,
            )
            for log in logs
        ],
    )


def _resolve_output_path(job: Job) -> Path:
    """
    Job의 final_shorts.mp4 경로를 반환한다.

    output_path가 저장되어 있으면 우선 사용하고, 없으면 표준 assets 경로를 쓴다.
    """
    if job.output_path:
        return Path(job.output_path)
    return job_asset_dir(job.id) / "final_shorts.mp4"


def _create_and_enqueue(db: Session, url: str) -> Job:
    """
    Job 1건을 SQLite에 저장하고 RQ 큐에 등록한다.

    Args:
        db: SQLAlchemy 세션
        url: AliExpress URL

    Returns:
        생성된 Job ORM 인스턴스
    """
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, url=url.strip(), status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_video_job(job_id, url.strip())
    return job


@router.post("", response_model=JobSummaryResponse)
def create_job(body: CreateJobRequest, db: Session = Depends(get_db)) -> JobSummaryResponse:
    """단건 URL을 제출해 Job을 생성하고 RQ 큐에 등록한다."""
    job = _create_and_enqueue(db, body.url)
    return _job_summary(job)


@router.post("/batch", response_model=BatchCreateResponse)
async def create_jobs_batch(
    file: UploadFile = File(..., description="url 컬럼이 포함된 CSV"),
    db: Session = Depends(get_db),
) -> BatchCreateResponse:
    """CSV 파일(url 컬럼)로 여러 Job을 일괄 생성·enqueue한다."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "url" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must contain a 'url' column")

    created: list[JobSummaryResponse] = []
    for row in reader:
        url = (row.get("url") or "").strip()
        if not url:
            continue
        job = _create_and_enqueue(db, url)
        created.append(_job_summary(job))

    if not created:
        raise HTTPException(status_code=400, detail="No valid URLs found in CSV")

    return BatchCreateResponse(created=created, count=len(created))


@router.get("", response_model=list[JobSummaryResponse])
def list_jobs(
    status: Optional[str] = Query(None, description="상태 필터 (pending, completed, failed 등)"),
    db: Session = Depends(get_db),
) -> list[JobSummaryResponse]:
    """작업 목록을 최신순으로 반환한다. ?status= 로 필터 가능."""
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    jobs = query.order_by(Job.created_at.desc()).all()
    return [_job_summary(job) for job in jobs]


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobDetailResponse:
    """작업 상세와 단계별 로그를 반환한다."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_detail(job)


@router.get("/{job_id}/download")
def download_job(job_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """완료된 작업의 final_shorts.mp4를 다운로드한다."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    output_path = _resolve_output_path(job)
    if not output_path.is_file():
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(
        path=output_path,
        filename="final_shorts.mp4",
        media_type="video/mp4",
    )


@router.post("/{job_id}/retry", response_model=JobSummaryResponse)
def retry_job(job_id: str, db: Session = Depends(get_db)) -> JobSummaryResponse:
    """failed 상태 작업을 pending으로 되돌리고 RQ 큐에 재등록한다."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    job.status = "pending"
    job.current_step = None
    job.error_message = None
    job.retry_count += 1
    db.commit()
    db.refresh(job)
    enqueue_video_job(job.id, job.url)
    return _job_summary(job)
