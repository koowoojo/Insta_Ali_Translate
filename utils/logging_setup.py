"""
콘솔 + 파일 로깅 초기화.

애플리케이션 진입점(main, worker)에서 setup_logging()을 한 번 호출하면
INFO 레벨 로그가 stderr와 logs/app.log(자정 로테이션)에 동시 기록된다.
"""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: str = "logs") -> None:
    """
    루트 로거에 콘솔·파일 핸들러를 등록한다.

    Args:
        log_dir: 로그 파일을 저장할 디렉터리 경로 (기본: "logs")
    """
    # 로그 디렉터리가 없으면 생성 (parents=True로 중간 경로도 함께 생성)
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 모든 핸들러에 공통 적용할 포맷
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 중복 호출 시 핸들러가 누적되지 않도록 기존 핸들러가 없을 때만 등록
    if not root.handlers:
        # 콘솔 출력 핸들러
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        root.addHandler(ch)

        # 자정마다 로테이션, 최대 7일치 백업 보관
        fh = TimedRotatingFileHandler(
            f"{log_dir}/app.log",
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
