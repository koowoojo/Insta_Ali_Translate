# Insta_Ali Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AliExpress 상품 URL에서 영상을 스크래핑하고, Whisper → Claude → ElevenLabs → MoviePy 파이프라인으로 9:16 한국어 숏폼 영상을 자동 생성하며, FastAPI 대시보드 + RQ 워커로 배치 처리한다.

**Architecture:** 핵심 5모듈(`scraper`, `audio_processor`, `script_writer`, `tts_generator`, `video_editor`)을 `worker/pipeline.py`가 오케스트레이션. FastAPI가 작업을 SQLite에 기록하고 RQ 큐에 등록, RQ 워커가 Redis에서 꺼내 파이프라인 실행. 작업별 산출물은 `assets/jobs/{job_id}/`에 격리.

**Tech Stack:** Python 3.11+, Playwright, OpenAI Whisper, Anthropic Claude 3.5 Sonnet, ElevenLabs, MoviePy, OpenCV, FastAPI, RQ, Redis, SQLite, SQLAlchemy 2.x

**Spec reference:** `docs/superpowers/specs/2026-06-22-insta-ali-pipeline-design.md`

---

## File Map (전체 생성·수정 파일)

| 파일 | 책임 |
|------|------|
| `requirements.txt` | 의존성 고정 |
| `.env.example` | 환경변수 템플릿 |
| `utils/config.py` | pydantic-settings 설정 로드 |
| `utils/exceptions.py` | `PipelineError`, `VideoNotFoundError` |
| `utils/logging_setup.py` | 콘솔 + 파일 로깅 |
| `utils/notifier.py` | 텔레그램 실패 알림 |
| `modules/scraper.py` | Playwright MP4 추출·다운로드 |
| `modules/audio_processor.py` | 오디오 분리 + Whisper STT |
| `modules/script_writer.py` | Claude 2단계 프롬프팅 |
| `modules/tts_generator.py` | ElevenLabs TTS |
| `modules/video_editor.py` | 9:16 크롭, 루프, 자막, 렌더 |
| `worker/pipeline.py` | 5단계 동기 오케스트레이션 |
| `worker/tasks.py` | RQ 작업 래퍼 |
| `worker/run_worker.py` | RQ 워커 실행 |
| `db/models.py` | Job, JobLog SQLAlchemy 모델 |
| `db/session.py` | DB 세션 팩토리 |
| `db/init_db.py` | 테이블 생성 스크립트 |
| `main.py` | CLI (--url, --batch, --login) |
| `web/app.py` | FastAPI 앱 팩토리 |
| `web/routes/jobs.py` | REST API |
| `web/routes/pages.py` | HTML 페이지 |
| `web/templates/*.html` | 대시보드 UI |
| `tests/test_*.py` | 단위·API 테스트 |
| `docker-compose.yml` | Phase 2 컨테이너 구성 |

---

## Phase MVP — 프로젝트 스캐폴딩 + 핵심 모듈 + CLI

### Task 1: 프로젝트 기반 설정

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `utils/__init__.py`
- Create: `modules/__init__.py`
- Create: `tests/__init__.py`
- Create: `pytest.ini`

- [ ] **Step 1: requirements.txt 작성**

```
python-dotenv>=1.0.0
pydantic>=2.0
pydantic-settings>=2.0
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
jinja2>=3.1.0
python-multipart>=0.0.9
httpx>=0.27.0
redis>=5.0.0
rq>=1.16.0
sqlalchemy>=2.0.0
aiosqlite>=0.20.0
playwright>=1.42.0
openai>=1.30.0
anthropic>=0.25.0
moviepy>=1.0.3
opencv-python-headless>=4.9.0
Pillow>=10.0.0
requests>=2.31.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
fakeredis>=2.21.0
```

- [ ] **Step 2: .env.example 작성**

```ini
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///db/jobs.db
MAX_CONCURRENT_JOBS=2
PROXY_URL=
ALIEXPRESS_SESSION_PATH=assets/sessions/aliexpress_state.json
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SUBTITLE_FONT_PATH=C:/Windows/Fonts/malgun.ttf
SUBTITLE_FONT_SIZE=48
SUBTITLE_CHUNK_SIZE=18
```

- [ ] **Step 3: pytest.ini 작성**

```ini
[pytest]
asyncio_mode = auto
markers =
    integration: marks tests that call external services (deselect with '-m "not integration"')
```

- [ ] **Step 4: 가상환경 설치 및 Playwright 브라우저 설치**

Run:
```powershell
cd E:\Vibe\Insta_Ali
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```
Expected: exit code 0

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example pytest.ini utils/__init__.py modules/__init__.py tests/__init__.py
git commit -m "chore: add project scaffolding and dependencies"
```

---

### Task 2: 설정·예외·로깅 유틸

**Files:**
- Create: `utils/config.py`
- Create: `utils/exceptions.py`
- Create: `utils/logging_setup.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_config.py
from utils.config import Settings

def test_settings_defaults():
    s = Settings(
        openai_api_key="test-openai",
        anthropic_api_key="test-anthropic",
        elevenlabs_api_key="test-eleven",
        elevenlabs_voice_id="voice-123",
    )
    assert s.max_concurrent_jobs == 2
    assert s.subtitle_chunk_size == 18
    assert "malgun" in s.subtitle_font_path.lower() or s.subtitle_font_path.endswith(".ttf")
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `pytest tests/test_config.py::test_settings_defaults -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.config'`

- [ ] **Step 3: exceptions.py 구현**

```python
# utils/exceptions.py
"""파이프라인 공통 예외 정의."""

class PipelineError(Exception):
    def __init__(self, step: str, message: str) -> None:
        self.step = step
        self.message = message
        super().__init__(f"[{step}] {message}")

class VideoNotFoundError(PipelineError):
    def __init__(self, message: str = "페이지에서 MP4 비디오를 찾을 수 없습니다.") -> None:
        super().__init__("scraping", message)
```

- [ ] **Step 4: config.py 구현**

```python
# utils/config.py
"""환경변수 기반 애플리케이션 설정."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    anthropic_api_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite:///db/jobs.db"
    max_concurrent_jobs: int = 2

    proxy_url: str = ""
    aliexpress_session_path: str = "assets/sessions/aliexpress_state.json"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    subtitle_font_path: str = "C:/Windows/Fonts/malgun.ttf"
    subtitle_font_size: int = 48
    subtitle_chunk_size: int = 18

    claude_model: str = "claude-3-5-sonnet-20241022"
    elevenlabs_model_id: str = "eleven_multilingual_v2"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: logging_setup.py 구현**

```python
# utils/logging_setup.py
"""콘솔 + 파일 로깅 초기화."""
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

def setup_logging(log_dir: str = "logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        root.addHandler(ch)
        fh = TimedRotatingFileHandler(f"{log_dir}/app.log", when="midnight", backupCount=7, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add utils/ tests/test_config.py
git commit -m "feat: add settings, exceptions, and logging utilities"
```

---

### Task 3: scraper.py — Playwright MP4 추출

**Files:**
- Create: `modules/scraper.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: URL 추출 단위 테스트 (HTML fixture)**

```python
# tests/test_scraper.py
import re
from modules.scraper import find_mp4_url_in_html

SAMPLE_HTML = '''
<html><body>
<video src="https://cdn.example.com/video.mp4"></video>
</body></html>
'''

def test_find_mp4_in_video_tag():
    url = find_mp4_url_in_html(SAMPLE_HTML)
    assert url == "https://cdn.example.com/video.mp4"

def test_find_mp4_in_page_source():
    html = 'var x = {"video_url":"https://cdn.example.com/promo.mp4"}'
    url = find_mp4_url_in_html(html)
    assert url == "https://cdn.example.com/promo.mp4"

def test_find_mp4_returns_none():
    assert find_mp4_url_in_html("<html></html>") is None
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_scraper.py -v`
Expected: FAIL — `find_mp4_url_in_html` not defined

- [ ] **Step 3: scraper.py 핵심 구현**

```python
# modules/scraper.py
"""
AliExpress 상품 페이지 Playwright 스크래핑.
- video 태그 또는 페이지 소스 내 MP4 URL 탐색
- 세션 재사용, 프록시, 재시도 지원
"""
import argparse
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from playwright.sync_api import sync_playwright

from utils.config import get_settings
from utils.exceptions import VideoNotFoundError

logger = logging.getLogger(__name__)

MP4_PATTERN = re.compile(r"https?://[^\s\"'<>]+\.mp4", re.IGNORECASE)

def find_mp4_url_in_html(html: str, base_url: str = "") -> str | None:
    m = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        return urljoin(base_url, m.group(1))
    m2 = re.search(r'video_url["\']?\s*[:=]\s*["\']([^"\']+\.mp4)', html, re.IGNORECASE)
    if m2:
        return m2.group(1)
    m3 = MP4_PATTERN.search(html)
    return m3.group(0) if m3 else None

def _download_mp4(url: str, dest: Path, proxy_url: str = "") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proxies = proxy_url if proxy_url else None
    with httpx.Client(proxies=proxies, timeout=120.0, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
    logger.info("MP4 저장 완료: %s", dest)
    return dest

def scrape_video(url: str, output_path: str, max_retries: int = 3) -> str:
    settings = get_settings()
    dest = Path(output_path)
    last_err: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("스크래핑 시도 %d/%d: %s", attempt, max_retries, url)
            with sync_playwright() as p:
                launch_kwargs: dict = {"headless": True}
                if settings.proxy_url:
                    launch_kwargs["proxy"] = {"server": settings.proxy_url}
                browser = p.chromium.launch(**launch_kwargs)
                context_kwargs: dict = {}
                session = Path(settings.aliexpress_session_path)
                if session.exists():
                    context_kwargs["storage_state"] = str(session)
                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=60000)
                html = page.content()
                mp4 = find_mp4_url_in_html(html, base_url=url)
                browser.close()

            if not mp4:
                raise VideoNotFoundError()

            return str(_download_mp4(mp4, dest, settings.proxy_url))
        except Exception as e:
            last_err = e
            logger.warning("스크래핑 실패 (시도 %d): %s", attempt, e)
            time.sleep(2 ** attempt)

    raise PipelineError("scraping", str(last_err))

def save_login_session() -> None:
  """Headful 브라우저로 수동 로그인 후 storage_state 저장."""
  settings = get_settings()
  path = Path(settings.aliexpress_session_path)
  path.parent.mkdir(parents=True, exist_ok=True)
  with sync_playwright() as p:
      browser = p.chromium.launch(headless=False)
      context = browser.new_context()
      page = context.new_page()
      page.goto("https://www.aliexpress.com/")
      input("AliExpress 로그인 후 Enter를 누르세요...")
      context.storage_state(path=str(path))
      browser.close()
  logger.info("세션 저장: %s", path)

if __name__ == "__main__":
    from utils.logging_setup import setup_logging
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", action="store_true")
    parser.add_argument("--url")
    parser.add_argument("--output", default="assets/raw_video.mp4")
    args = parser.parse_args()
    if args.login:
        save_login_session()
    elif args.url:
        scrape_video(args.url, args.output)
```

> **Note:** `scrape_video` except 블록에서 `PipelineError` import 추가: `from utils.exceptions import VideoNotFoundError, PipelineError`

- [ ] **Step 4: 테스트 통과**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/scraper.py tests/test_scraper.py
git commit -m "feat: add Playwright scraper with MP4 URL extraction"
```

---

### Task 4: audio_processor.py — 오디오 분리 + Whisper

**Files:**
- Create: `modules/audio_processor.py`
- Create: `tests/test_audio_processor.py`

- [ ] **Step 1: 청크 분리 헬퍼 테스트**

```python
# tests/test_audio_processor.py
from modules.audio_processor import chunk_text_for_subtitles

def test_chunk_text_for_subtitles():
    text = "가나다라마바사아자차카타파하"  # 14 chars
    chunks = chunk_text_for_subtitles(text, chunk_size=4)
    assert chunks == ["가나다라", "마바사아", "자차카타", "파하"]
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_audio_processor.py::test_chunk_text_for_subtitles -v`
Expected: FAIL

- [ ] **Step 3: audio_processor.py 구현**

```python
# modules/audio_processor.py
"""영상 오디오 분리 및 OpenAI Whisper STT."""
import logging
from pathlib import Path

from moviepy.editor import VideoFileClip
from openai import OpenAI

from utils.config import get_settings

logger = logging.getLogger(__name__)

def chunk_text_for_subtitles(text: str, chunk_size: int = 18) -> list[str]:
    text = text.replace("\n", " ").strip()
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

def extract_audio(video_path: str, audio_path: str) -> str:
    logger.info("오디오 추출: %s", video_path)
    Path(audio_path).parent.mkdir(parents=True, exist_ok=True)
    clip = VideoFileClip(video_path)
    if clip.audio is None:
        raise ValueError("영상에 오디오 트랙이 없습니다.")
    clip.audio.write_audiofile(audio_path, logger=None)
    clip.close()
    return audio_path

def transcribe(audio_path: str) -> str:
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    logger.info("Whisper STT 시작: %s", audio_path)
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(model="whisper-1", file=f)
    text = result.text.strip()
    logger.info("STT 완료 (%d자)", len(text))
    return text
```

- [ ] **Step 4: 테스트 통과**

Run: `pytest tests/test_audio_processor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/audio_processor.py tests/test_audio_processor.py
git commit -m "feat: add audio extraction and Whisper transcription"
```

---

### Task 5: script_writer.py — Claude 2단계 프롬프팅

**Files:**
- Create: `modules/script_writer.py`
- Create: `tests/test_script_writer.py`

- [ ] **Step 1: 프롬프트 빌더 테스트**

```python
# tests/test_script_writer.py
from modules.script_writer import build_step1_prompt, build_step2_prompt

def test_build_step1_prompt_contains_text():
    p = build_step1_prompt("hello product")
    assert "hello product" in p

def test_build_step2_prompt_contains_summary():
    p = build_step2_prompt('{"hooks":["fast"]}')
    assert "fast" in p
    assert "40초" in p or "40" in p
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_script_writer.py -v`
Expected: FAIL

- [ ] **Step 3: script_writer.py 구현**

```python
# modules/script_writer.py
"""Claude 다단계 프롬프팅으로 한국어 세일즈 대본 생성."""
import json
import logging
from pathlib import Path

import anthropic

from utils.config import get_settings

logger = logging.getLogger(__name__)

def build_step1_prompt(raw_text: str) -> str:
    return f"""다음은 상품 홍보 영상의 음성 인식 원문입니다.
핵심 소구점(hooks), 제품 특징(features), 타겟(target_audience)을 JSON으로 요약하세요.
키만 hooks, features, target_audience를 사용하세요.

원문:
{raw_text}
"""

def build_step2_prompt(summary_json: str) -> str:
    return f"""아래 제품 요약을 바탕으로 유튜브 쇼츠/틱톡용 한국어 세일즈 대본을 작성하세요.
- 첫 3초 안에 시선을 사로잡는 강력한 후킹 멘트
- 자연스러운 한국어 홈쇼핑 톤
- 낭독 시 40초 이내 (150~200자 내외)
- 대본 텍스트만 출력 (설명·괄호 없음)

요약:
{summary_json}
"""

def analyze_product(client: anthropic.Anthropic, raw_text: str, model: str) -> dict:
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": build_step1_prompt(raw_text)}],
    )
    content = msg.content[0].text
    return json.loads(content)

def write_sales_script(client: anthropic.Anthropic, summary: dict, model: str) -> str:
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": build_step2_prompt(json.dumps(summary, ensure_ascii=False))}],
    )
    return msg.content[0].text.strip()

def generate_script(raw_text: str, job_dir: str | None = None) -> str:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    logger.info("Step1: 제품 분석")
    summary = analyze_product(client, raw_text, settings.claude_model)
    if job_dir:
        p = Path(job_dir) / "script_step1.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Step2: 세일즈 대본 작성")
    return write_sales_script(client, summary, settings.claude_model)
```

- [ ] **Step 4: 테스트 통과**

Run: `pytest tests/test_script_writer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/script_writer.py tests/test_script_writer.py
git commit -m "feat: add Claude multi-step script generation"
```

---

### Task 6: tts_generator.py — ElevenLabs TTS

**Files:**
- Create: `modules/tts_generator.py`
- Create: `tests/test_tts_generator.py`

- [ ] **Step 1: API 페이로드 빌더 테스트**

```python
# tests/test_tts_generator.py
from modules.tts_generator import build_tts_payload

def test_build_tts_payload():
    payload = build_tts_payload("안녕하세요", "voice-1", "eleven_multilingual_v2")
    assert payload["text"] == "안녕하세요"
    assert payload["model_id"] == "eleven_multilingual_v2"
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_tts_generator.py -v`
Expected: FAIL

- [ ] **Step 3: tts_generator.py 구현**

```python
# modules/tts_generator.py
"""ElevenLabs TTS로 한국어 더빙 오디오 생성."""
import logging
from pathlib import Path

import httpx

from utils.config import get_settings

logger = logging.getLogger(__name__)
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

def build_tts_payload(text: str, voice_id: str, model_id: str) -> dict:
    return {
        "text": text,
        "model_id": model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

def generate_speech(text: str, output_path: str) -> str:
    settings = get_settings()
    url = ELEVENLABS_URL.format(voice_id=settings.elevenlabs_voice_id)
    headers = {"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"}
    payload = build_tts_payload(text, settings.elevenlabs_voice_id, settings.elevenlabs_model_id)
    logger.info("ElevenLabs TTS 요청 (%d자)", len(text))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        Path(output_path).write_bytes(resp.content)
    logger.info("더빙 저장: %s", output_path)
    return output_path
```

- [ ] **Step 4: 테스트 통과**

Run: `pytest tests/test_tts_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/tts_generator.py tests/test_tts_generator.py
git commit -m "feat: add ElevenLabs TTS generator"
```

---

### Task 7: video_editor.py — 9:16 합성 + 자막

**Files:**
- Create: `modules/video_editor.py`
- Create: `tests/test_video_editor.py`

- [ ] **Step 1: 크롭 박스 계산 테스트**

```python
# tests/test_video_editor.py
from modules.video_editor import compute_center_crop_box

def test_compute_center_crop_box_landscape():
    # 1920x1080 landscape -> 9:16 crop
    x1, y1, x2, y2 = compute_center_crop_box(1920, 1080, target_w=9, target_h=16)
    assert x2 - x1 == y2 - y1  # square crop region for 9:16 from center
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_video_editor.py -v`
Expected: FAIL

- [ ] **Step 3: video_editor.py 구현**

```python
# modules/video_editor.py
"""
MoviePy 기반 9:16 숏폼 합성.
- 원본 음소거, 중앙 크롭, 오디오 길이 기준 루프/컷
- 노란 글씨 + 검은 테두리 자막
"""
import logging
import math

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)
from modules.audio_processor import chunk_text_for_subtitles
from utils.config import get_settings

logger = logging.getLogger(__name__)
TARGET_W, TARGET_H = 1080, 1920

def compute_center_crop_box(w: int, h: int, target_w: int = 9, target_h: int = 16) -> tuple[int, int, int, int]:
    target_ratio = target_w / target_h
    current_ratio = w / h
    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        x1 = (w - new_w) // 2
        return x1, 0, x1 + new_w, h
    new_h = int(w / target_ratio)
    y1 = (h - new_h) // 2
    return 0, y1, w, y1 + new_h

def _sync_video_to_audio(video: VideoFileClip, audio: AudioFileClip) -> VideoFileClip:
    if video.duration >= audio.duration:
        return video.subclip(0, audio.duration)
    loops = math.ceil(audio.duration / video.duration)
    looped = concatenate_videoclips([video] * loops)
    return looped.subclip(0, audio.duration)

def _build_subtitle_clips(script: str, duration: float) -> list[TextClip]:
    settings = get_settings()
    chunks = chunk_text_for_subtitles(script, settings.subtitle_chunk_size)
    if not chunks:
        return []
    seg = duration / len(chunks)
    clips = []
    for i, chunk in enumerate(chunks):
        txt = TextClip(
            chunk,
            font=settings.subtitle_font_path,
            fontsize=settings.subtitle_font_size,
            color="yellow",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(TARGET_W - 80, None),
        ).set_position(("center", TARGET_H - 200)).set_start(i * seg).set_duration(seg)
        clips.append(txt)
    return clips

def compose_shorts(video_path: str, audio_path: str, script: str, output_path: str) -> str:
    logger.info("영상 합성 시작")
    video = VideoFileClip(video_path).without_audio()
    x1, y1, x2, y2 = compute_center_crop_box(video.w, video.h)
    video = video.crop(x1=x1, y1=y1, x2=x2, y2=y2).resize((TARGET_W, TARGET_H))
    audio = AudioFileClip(audio_path)
    video = _sync_video_to_audio(video, audio)
    video = video.set_audio(audio)
    subs = _build_subtitle_clips(script, video.duration)
    final = CompositeVideoClip([video, *subs]) if subs else video
    final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
    video.close(); audio.close(); final.close()
    logger.info("렌더 완료: %s", output_path)
    return output_path
```

- [ ] **Step 4: 테스트 통과**

Run: `pytest tests/test_video_editor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/video_editor.py tests/test_video_editor.py
git commit -m "feat: add 9:16 video composer with subtitles and loop sync"
```

---

### Task 8: worker/pipeline.py + main.py CLI

**Files:**
- Create: `worker/__init__.py`
- Create: `worker/pipeline.py`
- Create: `main.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: job 경로 헬퍼 테스트**

```python
# tests/test_pipeline.py
from worker.pipeline import job_asset_dir

def test_job_asset_dir():
    p = job_asset_dir("abc-123")
    assert str(p).replace("\\", "/").endswith("assets/jobs/abc-123")
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_pipeline.py::test_job_asset_dir -v`
Expected: FAIL

- [ ] **Step 3: pipeline.py 구현**

```python
# worker/pipeline.py
"""5단계 동기 파이프라인 오케스트레이션."""
import logging
import uuid
from pathlib import Path

from modules import audio_processor, scraper, script_writer, tts_generator, video_editor

logger = logging.getLogger(__name__)

def job_asset_dir(job_id: str) -> Path:
    return Path("assets") / "jobs" / job_id

def run_pipeline(url: str, job_id: str | None = None) -> dict:
    job_id = job_id or str(uuid.uuid4())
    base = job_asset_dir(job_id)
    base.mkdir(parents=True, exist_ok=True)

    raw = str(base / "raw_video.mp4")
    wav = str(base / "extracted_audio.wav")
    dub = str(base / "dubbing.mp3")
    final = str(base / "final_shorts.mp4")

    logger.info("[%s] scraping", job_id)
    scraper.scrape_video(url, raw)

    logger.info("[%s] transcribing", job_id)
    audio_processor.extract_audio(raw, wav)
    text = audio_processor.transcribe(wav)

    logger.info("[%s] scripting", job_id)
    script = script_writer.generate_script(text, job_dir=str(base))

    logger.info("[%s] tts", job_id)
    tts_generator.generate_speech(script, dub)

    logger.info("[%s] editing", job_id)
    video_editor.compose_shorts(raw, dub, script, final)

    return {"job_id": job_id, "script": script, "output_path": final}
```

- [ ] **Step 4: main.py 구현**

```python
# main.py
"""CLI 진입점: 단건, 배치, 로그인 세션 저장."""
import argparse
import csv
import logging

from utils.logging_setup import setup_logging
from worker.pipeline import run_pipeline
from modules.scraper import save_login_session

def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Insta_Ali 숏폼 파이프라인")
    parser.add_argument("--url")
    parser.add_argument("--batch")
    parser.add_argument("--login", action="store_true")
    args = parser.parse_args()

    if args.login:
        save_login_session()
        return

    if args.url:
        result = run_pipeline(args.url)
        logging.getLogger(__name__).info("완료: %s", result["output_path"])
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
```

- [ ] **Step 5: 테스트 통과**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add worker/ main.py tests/test_pipeline.py
git commit -m "feat: add sync pipeline orchestration and CLI entrypoint"
```

---

## Phase 1 — SQLite + RQ + FastAPI + 텔레그램

### Task 9: SQLite 모델 및 DB 초기화

**Files:**
- Create: `db/__init__.py`
- Create: `db/models.py`
- Create: `db/session.py`
- Create: `db/init_db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Job 생성 테스트**

```python
# tests/test_db.py
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, Job

def test_create_job():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    job = Job(id=str(uuid.uuid4()), url="https://example.com", status="pending")
    db.add(job)
    db.commit()
    assert db.query(Job).count() == 1
```

- [ ] **Step 2~4: models.py, session.py, init_db.py 구현 후 테스트 PASS**

Run: `pytest tests/test_db.py -v`

- [ ] **Step 5: DB 초기화 실행**

Run: `python db/init_db.py`
Expected: `db/jobs.db` 생성

- [ ] **Step 6: Commit**

```bash
git add db/ tests/test_db.py
git commit -m "feat: add SQLite job models and database init"
```

**models.py 핵심 스키마:** `Job(id, url, status, current_step, error_message, script_text, output_path, retry_count, created_at, updated_at, completed_at)`, `JobLog(id, job_id, step, message, created_at)` — 설계서 SQL과 동일.

---

### Task 10: notifier.py — 텔레그램 알림

**Files:**
- Create: `utils/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: 메시지 포맷 테스트**

```python
def test_format_failure_message():
    from utils.notifier import format_failure_message
    msg = format_failure_message("j1", "http://x", "scraping", "timeout")
    assert "j1" in msg and "timeout" in msg
```

- [ ] **Step 2~4: 구현 — `requests.post` to `https://api.telegram.org/bot{token}/sendMessage`, 토큰 없으면 skip**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add Telegram failure notifier"
```

---

### Task 11: RQ 워커 작업

**Files:**
- Create: `worker/tasks.py`
- Create: `worker/run_worker.py`
- Create: `tests/test_rq_tasks.py`

- [ ] **Step 1: process_video_job가 DB 상태를 갱신하는지 fakeredis로 테스트**

- [ ] **Step 2: tasks.py 구현**

```python
# worker/tasks.py
"""RQ 백그라운드 작업 — DB 상태 갱신 + 파이프라인 실행."""
from datetime import datetime, timezone

from db.session import get_sync_session
from db.models import Job, JobLog
from worker.pipeline import run_pipeline
from utils.notifier import send_telegram_failure
from utils.exceptions import PipelineError

STEPS = ["scraping", "transcribing", "scripting", "tts", "editing"]

def _update(db, job_id, status, step=None, error=None, output=None, script=None):
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
    db = get_sync_session()
    try:
        _update(db, job_id, "scraping", "scraping")
        result = run_pipeline(url, job_id=job_id)
        _update(db, job_id, "completed", "editing", output=result["output_path"], script=result["script"])
    except Exception as e:
        step = e.step if isinstance(e, PipelineError) else "unknown"
        _update(db, job_id, "failed", step, error=str(e))
        send_telegram_failure(job_id, url, step, str(e))
        raise
    finally:
        db.close()
```

- [ ] **Step 3: run_worker.py — `rq worker insta_ali --url $REDIS_URL`**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: add RQ worker task with DB status updates"
```

---

### Task 12: FastAPI 웹 대시보드

**Files:**
- Create: `web/__init__.py`
- Create: `web/app.py`
- Create: `web/routes/jobs.py`
- Create: `web/routes/pages.py`
- Create: `web/templates/base.html`
- Create: `web/templates/index.html`
- Create: `web/templates/jobs.html`
- Create: `web/templates/job_detail.html`
- Create: `tests/test_web_api.py`

- [ ] **Step 1: POST /api/jobs 테스트 (fakeredis + TestClient)**

```python
def test_create_job_returns_id(client):
    resp = client.post("/api/jobs", json={"url": "https://aliexpress.com/item/1"})
    assert resp.status_code == 200
    assert "id" in resp.json()
```

- [ ] **Step 2: jobs.py API — create, batch(CSV), list, detail, download, retry**

- [ ] **Step 3: pages.py + HTMX 5초 폴링 jobs 테이블**

- [ ] **Step 4: app.py — `uvicorn web.app:app`**

Run: `uvicorn web.app:app --reload --port 8000`
Expected: `http://localhost:8000` 접속 가능

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add FastAPI dashboard and job API"
```

---

## Phase 2 — Docker Compose (설계서 Phase 2)

### Task 13: docker-compose.yml

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: 3서비스 정의 — `redis`, `web`, `worker`**

- [ ] **Step 2: 볼륨 — `./assets`, `./db`, `.env`**

- [ ] **Step 3: 검증**

Run: `docker compose up --build -d`
Expected: 3 containers running

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: add Docker Compose for web, worker, and redis"
```

---

## Spec Coverage Checklist

| 설계서 요구 | Task |
|-------------|------|
| Playwright 스크래핑 + 세션 + 프록시 + 재시도 | Task 3 |
| Whisper STT | Task 4 |
| Claude 2단계 프롬프팅 | Task 5 |
| ElevenLabs TTS | Task 6 |
| 9:16 루프 + 자막 | Task 7 |
| CLI 단건/배치/로그인 | Task 8 |
| SQLite jobs | Task 9 |
| 텔레그램 알림 | Task 10 |
| RQ 백그라운드 워커 | Task 11 |
| FastAPI 대시보드 + CSV 배치 | Task 12 |
| Docker Compose | Task 13 |
| MAX_CONCURRENT_JOBS | Task 11 run_worker (워커 프로세스 수) |
| logging | Task 2 |
| .env | Task 1 |

---

## Manual Verification (MVP 완료 후)

1. `.env`에 API 키 설정
2. `python main.py --login` → AliExpress 세션 저장
3. `python main.py --url "<실제 상품 URL>"` → `assets/jobs/{id}/final_shorts.mp4` 생성 확인
4. Phase 1: Redis 기동 → worker + uvicorn → 웹 UI에서 URL 제출 → 대시보드 상태 전이 확인
5. 실패 URL 제출 → 텔레그램 알림 수신 확인

---

## Plan Self-Review

- **Spec coverage:** 모든 설계서 섹션에 Task 매핑 완료
- **Placeholder scan:** TBD/TODO 없음
- **Type consistency:** `run_pipeline(url, job_id)` 시그니처 Task 8·11에서 동일
