"""RQ worker/tasks.py — process_video_job DB 상태 갱신 단위 테스트."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Job, JobLog
from utils.exceptions import PipelineError

# db.session이 모듈 로드 시 get_settings()를 호출하므로 import 전에 스텁
_settings_mock = MagicMock(database_url="sqlite:///:memory:")
_patch_settings = patch("utils.config.get_settings", return_value=_settings_mock)
_patch_settings.start()

from worker.tasks import process_video_job


def _make_db_session():
    """인메모리 SQLite 세션과 Job 1건을 준비한다."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    job_id = str(uuid.uuid4())
    db.add(Job(id=job_id, url="https://aliexpress.com/item/1", status="pending"))
    db.commit()
    return db, job_id


def test_process_video_job_marks_completed():
    """run_pipeline 성공 시 Job이 completed로 갱신되고 산출물·대본이 저장되는지 확인."""
    db, job_id = _make_db_session()
    pipeline_result = {
        "job_id": job_id,
        "script": "테스트 대본",
        "output_path": "assets/jobs/final_shorts.mp4",
    }

    with patch("worker.tasks.get_sync_session", return_value=db):
        with patch("worker.tasks.run_pipeline", return_value=pipeline_result):
            process_video_job(job_id, "https://aliexpress.com/item/1")

    job = db.get(Job, job_id)
    assert job is not None
    assert job.status == "completed"
    assert job.current_step == "editing"
    assert job.script_text == "테스트 대본"
    assert job.output_path == "assets/jobs/final_shorts.mp4"
    assert job.completed_at is not None
    assert db.query(JobLog).filter_by(job_id=job_id).count() >= 2


def test_process_video_job_marks_failed_and_notifies():
    """PipelineError 발생 시 failed 갱신·텔레그램 알림·예외 재발생을 확인."""
    db, job_id = _make_db_session()
    pipeline_error = PipelineError("tts", "voice synthesis failed")

    with patch("worker.tasks.get_sync_session", return_value=db):
        with patch("worker.tasks.run_pipeline", side_effect=pipeline_error):
            with patch("worker.tasks.send_telegram_failure") as notify:
                with pytest.raises(PipelineError):
                    process_video_job(job_id, "https://aliexpress.com/item/1")

                notify.assert_called_once_with(
                    job_id,
                    "https://aliexpress.com/item/1",
                    "tts",
                    str(pipeline_error),
                )

    job = db.get(Job, job_id)
    assert job is not None
    assert job.status == "failed"
    assert job.current_step == "tts"
    assert "voice synthesis failed" in job.error_message

