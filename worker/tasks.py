"""
RQ 백그라운드 작업 — DB 상태 갱신 + 파이프라인 실행.

`process_video_job`은 FastAPI가 큐에 등록한 작업을 워커가 수신할 때 호출된다.
Job·JobLog를 SQLite에 갱신하고 `run_pipeline`을 실행한다. 실패 시 텔레그램 알림 후
예외를 재발생시켜 RQ 재시도·실패 기록이 정상 동작하게 한다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from db.models import Job, JobLog
from db.session import get_sync_session
from utils.exceptions import PipelineError
from utils.notifier import send_telegram_failure
from worker.pipeline import run_pipeline

# 파이프라인 단계 식별자 (로깅·상태 전이 참조용)
STEPS = ["scraping", "transcribing", "scripting", "tts", "editing"]


def _update(
    db,
    job_id: str,
    status: str,
    step: str | None = None,
    error: str | None = None,
    output: str | None = None,
    script: str | None = None,
) -> None:
    """
    Job 상태·산출물 필드를 갱신하고 JobLog 1건을 추가한다.

    Args:
        db: SQLAlchemy 동기 세션
        job_id: 대상 Job UUID
        status: pending|running|scraping|completed|failed 등 상태 문자열
        step: current_step 및 JobLog.step에 기록할 단계명
        error: 실패 시 error_message·JobLog.message에 저장
        output: 성공 시 output_path
        script: 성공 시 script_text
    """
    job = db.get(Job, job_id)
    if not job:
        return
    job.status = status
    job.current_step = step
    job.error_message = error
    job.output_path = output or job.output_path
    job.script_text = script or job.script_text
    job.updated_at = datetime.now(timezone.utc)
    if status == "completed":
        job.completed_at = datetime.now(timezone.utc)
    db.add(JobLog(job_id=job_id, step=step or status, message=error or status))
    db.commit()


def process_video_job(job_id: str, url: str) -> None:
    """
    RQ 워커가 실행하는 단일 비디오 처리 작업.

    1. Job을 scraping 단계로 갱신
    2. `run_pipeline(url, job_id)` 실행
    3. 성공 시 completed·산출물 경로·대본 저장
    4. 실패 시 failed·텔레그램 알림·예외 재발생

    Args:
        job_id: DB Job 식별자 (UUID 문자열)
        url: AliExpress 상품 페이지 URL
    """
    db = get_sync_session()
    try:
        _update(db, job_id, "scraping", "scraping")
        result = run_pipeline(url, job_id=job_id)
        _update(
            db,
            job_id,
            "completed",
            "editing",
            output=result["output_path"],
            script=result["script"],
        )
    except Exception as e:
        step = e.step if isinstance(e, PipelineError) else "unknown"
        _update(db, job_id, "failed", step, error=str(e))
        send_telegram_failure(job_id, url, step, str(e))
        raise
    finally:
        db.close()
