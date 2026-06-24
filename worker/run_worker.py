"""
RQ 워커 실행 진입점.

`python worker/run_worker.py`로 insta_ali 큐를 구독하는 워커 프로세스를 시작한다.
Redis 연결 URL은 `utils.config.get_settings().redis_url`을 사용한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 — `python worker/run_worker.py` 직접 실행 지원
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from redis import Redis
from rq import Queue, Worker

from utils.config import get_settings
from utils.logging_setup import setup_logging

# FastAPI·워커가 공유하는 RQ 큐 이름
QUEUE_NAME = "insta_ali"


def main() -> None:
    """REDIS_URL에 연결된 RQ Worker를 insta_ali 큐에서 시작한다."""
    setup_logging()
    settings = get_settings()
    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue(QUEUE_NAME, connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    main()
