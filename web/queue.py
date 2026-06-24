"""
RQ 큐 등록 헬퍼.

FastAPI 라우트에서 `process_video_job`을 `insta_ali` 큐에 enqueue한다.
단위 테스트에서는 이 모듈 함수를 mock한다.
"""

from __future__ import annotations

from redis import Redis
from rq import Queue

from utils.config import get_settings
from worker.tasks import process_video_job

# worker/run_worker.py와 동일한 큐 이름
QUEUE_NAME = "insta_ali"


def get_redis_connection() -> Redis:
    """settings.redis_url 기반 Redis 연결을 반환한다."""
    return Redis.from_url(get_settings().redis_url)


def get_queue() -> Queue:
    """insta_ali RQ 큐 인스턴스를 반환한다."""
    return Queue(QUEUE_NAME, connection=get_redis_connection())


def enqueue_video_job(job_id: str, url: str) -> None:
    """
    단일 비디오 처리 작업을 RQ 큐에 등록한다.

    Args:
        job_id: SQLite Job UUID
        url: AliExpress 상품 URL
    """
    queue = get_queue()
    queue.enqueue(process_video_job, job_id, url)
