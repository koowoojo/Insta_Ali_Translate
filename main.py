"""
CLI 진입점: 단건 URL, CSV 배치, AliExpress 로그인 세션 저장.

사용 예:
    python main.py --url "https://..."
    python main.py --batch urls.csv
    python main.py --login
"""

from __future__ import annotations

import argparse
import csv
import json
import logging

from pathlib import Path

from modules.scraper import save_login_session
from utils.config import get_settings
from utils.logging_setup import setup_logging
from utils.session_import import import_cookies_file
from worker.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def main() -> None:
    """argparse CLI를 파싱하고 요청된 모드(로그인/단건/배치)를 실행한다."""
    setup_logging()
    parser = argparse.ArgumentParser(description="Insta_Ali 숏폼 파이프라인")
    parser.add_argument("--url", help="처리할 AliExpress 상품 URL")
    parser.add_argument("--batch", help="url 컬럼이 있는 CSV 파일 경로")
    parser.add_argument("--login", action="store_true", help="Headful 로그인 후 세션 저장")
    parser.add_argument(
        "--import-cookies",
        metavar="JSON",
        help="Chrome Cookie-Editor 등에서보낸 쿠키 JSON → storage_state 변환",
    )
    args = parser.parse_args()

    if args.import_cookies:
        settings = get_settings()
        dest = Path(settings.aliexpress_session_path)
        try:
            out = import_cookies_file(Path(args.import_cookies), dest)
        except Exception as exc:
            logger.error("%s", exc)
            raise SystemExit(1) from exc
        logger.info("쿠키 세션 저장 완료: %s (%d cookies)", out, len(json.loads(out.read_text(encoding="utf-8"))["cookies"]))
        return

    if args.login:
        save_login_session()
        return

    if args.url:
        result = run_pipeline(args.url)
        logger.info("완료: %s", result["output_path"])
        return

    if args.batch:
        with open(args.batch, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                url = row.get("url") or row.get("URL")
                if url:
                    run_pipeline(url.strip())
        return

    parser.print_help()


if __name__ == "__main__":
    main()
