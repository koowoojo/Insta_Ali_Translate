# Insta_Ali_Translate n8n Reel Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Google Opal 벤치마킹 AliExpress URL → 한국어 9:16 릴스(MP4) + HTML 쇼케이스 자동 생성 파이프라인을 n8n(Form Trigger·폴링·텔레그램) + Docker Compose(5서비스)로 구축한다.

**Architecture:** Insta_Ali Python 워커 코드를 `E:\Vibe\Insta_Ali_Translate`로 복제해 독립 배포한다. n8n이 `POST/GET /api/jobs`로 작업을 등록·폴링하고, RQ 워커가 스크래핑→STT→대본→TTS→9:16 합성→HTML 쇼케이스를 실행한다. nginx가 MP4·쇼케이스를 `:8080`에서 서빙한다.

**Tech Stack:** n8n, Docker Compose, nginx, Python 3.11, FastAPI, RQ, Redis, SQLite, Playwright, OpenAI Whisper/TTS, Anthropic Claude, MoviePy, FFmpeg

**Spec reference:** `docs/superpowers/specs/2026-06-24-n8n-reel-pipeline-design.md`

---

## File Map

| 파일 | 책임 |
|------|------|
| `docker-compose.yml` | n8n + redis + web + worker + nginx 5서비스 |
| `Dockerfile` | Python 워커 이미지 (ffmpeg, Playwright, Nanum 폰트) |
| `nginx/nginx.conf` | `/showcase`, `/assets` 역프록시·정적 서빙 |
| `n8n/workflows/reel-pipeline.json` | Form→Poll→Telegram 워크플로 export |
| `.env.example` | SHOWCASE_BASE_URL, N8N_* 포함 환경변수 |
| `utils/showcase_generator.py` | Opal 스타일 HTML 쇼케이스 생성 |
| `utils/config.py` | `showcase_base_url` 설정 추가 |
| `utils/notifier.py` | `send_telegram_success()` 추가 |
| `worker/pipeline.py` | 6단계 showcase 추가 |
| `worker/tasks.py` | `showcase` step, showcase_path 저장 |
| `db/models.py` | `showcase_path` 컬럼 |
| `web/routes/showcase.py` | `GET /showcase/{id}` |
| `web/routes/jobs.py` | `showcase_url` API 응답 필드 |
| `web/app.py` | showcase 라우터 등록, 앱 타이틀 변경 |
| `tests/test_showcase_generator.py` | HTML 생성 단위 테스트 |
| `tests/test_showcase_route.py` | 쇼케이스 라우트 테스트 |
| `README.md` | Docker 기동·n8n Form·환경변수 안내 |

**복제 원본:** `E:\Vibe\Insta_Ali` (`.venv`, `.git`, `assets/jobs`, `db/jobs.db`, `logs` 제외)

---

## Spec Coverage Checklist

| 스펙 섹션 | Task |
|-----------|------|
| §2 Docker 5서비스 | Task 8 |
| §3 n8n 폴링 워크플로 | Task 10 |
| §4 Worker API | Task 6, 7 |
| §5 파이프라인 6단계 | Task 4, 5 |
| §6 HTML 쇼케이스 | Task 3, 6 |
| §7 에러 처리 | Task 5 (기존 notifier + n8n 분기) |
| §8 환경변수 | Task 2, 8 |
| §10 테스트 | Task 3, 6, 11 |

---

## Phase 1 — Insta_Ali 코드 복제 및 프로젝트 초기화

### Task 1: Insta_Ali 워커 코드 복제

**Files:**
- Create: `Insta_Ali_Translate/` 전체 (Insta_Ali에서 복사)
- Exclude: `.venv`, `.git`, `assets/jobs/*`, `db/jobs.db`, `logs`, `__pycache__`, `.pytest_cache`

- [ ] **Step 1: PowerShell로 복제**

```powershell
$src = "E:\Vibe\Insta_Ali"
$dst = "E:\Vibe\Insta_Ali_Translate"
$exclude = @('.venv', '.git', '__pycache__', '.pytest_cache', 'logs')
Get-ChildItem $src -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
    Copy-Item $_.FullName -Destination $dst -Recurse -Force
}
# 빈 jobs 디렉터리·sessions 보장
New-Item -ItemType Directory -Force -Path "$dst\assets\jobs", "$dst\assets\sessions", "$dst\db" | Out-Null
```

- [ ] **Step 2: 복제 확인**

```powershell
Test-Path "E:\Vibe\Insta_Ali_Translate\worker\pipeline.py"
Test-Path "E:\Vibe\Insta_Ali_Translate\modules\scraper.py"
Test-Path "E:\Vibe\Insta_Ali_Translate\web\app.py"
```
Expected: 모두 `True`

- [ ] **Step 3: Commit**

```bash
cd E:/Vibe/Insta_Ali_Translate
git add -A
git commit -m "chore: copy Insta_Ali worker codebase as independent base"
```

---

### Task 2: 프로젝트 설정·브랜딩 변경

**Files:**
- Modify: `utils/config.py`
- Modify: `.env.example`
- Modify: `web/app.py`

- [ ] **Step 1: config에 showcase_base_url 추가**

`utils/config.py`의 `Settings` 클래스에 추가:

```python
    # --- 쇼케이스·외부 URL (nginx 경유) ---
    showcase_base_url: str = "http://localhost:8080"
```

- [ ] **Step 2: .env.example 확장**

`.env.example` 하단에 추가:

```ini
SHOWCASE_BASE_URL=http://localhost:8080
N8N_ENCRYPTION_KEY=change-me-to-random-32-chars-min
N8N_BASIC_AUTH_USER=
N8N_BASIC_AUTH_PASSWORD=
```

Docker용 자막 폰트 주석 추가:

```ini
# Docker/Linux: SUBTITLE_FONT_PATH=/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf
```

- [ ] **Step 3: FastAPI 앱 타이틀 변경**

`web/app.py`:

```python
app = FastAPI(
    title="Insta Ali Translate API",
    description="n8n 연동 AliExpress 릴스 파이프라인 API",
    lifespan=lifespan,
)
```

- [ ] **Step 4: Commit**

```bash
git add utils/config.py .env.example web/app.py
git commit -m "feat: add showcase_base_url and rebrand API for Insta_Ali_Translate"
```

---

## Phase 2 — HTML 쇼케이스 생성기

### Task 3: showcase_generator 모듈

**Files:**
- Create: `utils/showcase_generator.py`
- Create: `tests/test_showcase_generator.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_showcase_generator.py
from pathlib import Path

from utils.showcase_generator import generate_showcase


def test_generate_showcase_creates_html(tmp_path):
    job_dir = tmp_path / "job-1"
    job_dir.mkdir()
    (job_dir / "script.txt").write_text("한국어 대본 테스트", encoding="utf-8")
    (job_dir / "final_shorts.mp4").write_bytes(b"fake-mp4")
    (job_dir / "dubbing.mp3").write_bytes(b"fake-mp3")

    out = generate_showcase(
        job_id="job-1",
        job_dir=job_dir,
        product_url="https://www.aliexpress.com/item/123.html",
        base_url="http://localhost:8080",
    )

    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "한국어 대본 테스트" in html
    assert "final_shorts.mp4" in html
    assert "dubbing.mp3" in html
    assert "AI Generated" in html
    assert "Ready to Post" in html
    assert "#121212" in html
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```powershell
cd E:\Vibe\Insta_Ali_Translate
python -m pytest tests/test_showcase_generator.py -v
```
Expected: FAIL — `ModuleNotFoundError: utils.showcase_generator`

- [ ] **Step 3: showcase_generator 구현**

```python
# utils/showcase_generator.py
"""
Opal Assemble Final Reel 벤치마킹 HTML 쇼케이스 생성기.

작업 디렉터리의 final_shorts.mp4, dubbing.mp3, script.txt를
다크모드 9:16 플레이어 + 대본 + 오디오 UI로 묶은 showcase.html을 생성한다.
"""

from __future__ import annotations

from pathlib import Path


def generate_showcase(
    job_id: str,
    job_dir: Path,
    product_url: str,
    base_url: str,
) -> Path:
    """
  job_dir 내 산출물을 참조하는 showcase.html을 생성한다.

  Args:
      job_id: 작업 UUID
      job_dir: assets/jobs/{job_id} 경로
      product_url: 원본 AliExpress URL
      base_url: nginx 외부 베이스 URL (예: http://localhost:8080)

  Returns:
      생성된 showcase.html Path
  """
    script_path = job_dir / "script.txt"
    script = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
    video_url = f"{base_url}/assets/jobs/{job_id}/final_shorts.mp4"
    audio_url = f"{base_url}/assets/jobs/{job_id}/dubbing.mp3"
    download_url = video_url

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Insta Ali Translate — Reel {job_id}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css" />
  <style>
    :root {{
      --bg: #121212;
      --card: rgba(255,255,255,0.06);
      --border: rgba(255,255,255,0.12);
      --text: #f5f5f5;
      --muted: #a0a0a0;
      --grad: linear-gradient(135deg, #7c3aed, #ec4899);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: Pretendard, system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}
    .wrap {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }}
    header {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .badge {{
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--card);
      border: 1px solid var(--border);
    }}
    .badge.accent {{
      background: var(--grad);
      border: none;
      color: white;
      font-weight: 600;
    }}
    h1 {{ font-size: 1.5rem; font-weight: 700; }}
    .layout {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 24px;
    }}
    @media (min-width: 900px) {{
      .layout {{ grid-template-columns: 380px 1fr; align-items: start; }}
    }}
    .player-card {{
      background: var(--card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 16px;
      box-shadow: 0 0 40px rgba(124, 58, 237, 0.25);
    }}
    video {{
      width: 100%;
      aspect-ratio: 9/16;
      border-radius: 16px;
      background: #000;
      display: block;
    }}
    .panel {{
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .card {{
      background: var(--card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px;
    }}
    .card h2 {{ font-size: 1rem; margin-bottom: 12px; color: var(--muted); }}
    .script {{
      white-space: pre-wrap;
      line-height: 1.7;
      font-size: 0.95rem;
    }}
    audio {{ width: 100%; margin-top: 8px; }}
    .toolbar {{
      position: sticky;
      bottom: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 16px;
      background: rgba(18,18,18,0.9);
      backdrop-filter: blur(8px);
      border-radius: 16px;
      border: 1px solid var(--border);
    }}
    .btn {{
      flex: 1;
      min-width: 120px;
      padding: 12px 16px;
      border: none;
      border-radius: 12px;
      font-weight: 600;
      cursor: pointer;
      background: var(--grad);
      color: white;
      text-decoration: none;
      text-align: center;
      transition: transform 0.15s;
    }}
    .btn:hover {{ transform: scale(1.03); }}
    .btn.secondary {{
      background: var(--card);
      border: 1px solid var(--border);
      color: var(--text);
    }}
    .url {{ font-size: 12px; color: var(--muted); word-break: break-all; margin-top: 8px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Instagram Reel Studio</h1>
      <span class="badge accent">AI Generated</span>
      <span class="badge">Ready to Post</span>
    </header>
    <div class="layout">
      <div class="player-card">
        <video id="reel" src="{video_url}" controls playsinline></video>
      </div>
      <div class="panel">
        <div class="card">
          <h2>한국어 대본</h2>
          <div class="script" id="script">{_escape_html(script)}</div>
          <p class="url">Source: {product_url}</p>
        </div>
        <div class="card">
          <h2>나레이션</h2>
          <audio controls src="{audio_url}"></audio>
        </div>
        <div class="toolbar">
          <a class="btn" href="{download_url}" download>Download Video</a>
          <button class="btn secondary" type="button" onclick="copyScript()">Copy Script</button>
          <button class="btn secondary" type="button" onclick="shareLink()">Share Link</button>
        </div>
      </div>
    </div>
  </div>
  <script>
    function copyScript() {{
      navigator.clipboard.writeText(document.getElementById('script').innerText);
      alert('대본이 복사되었습니다.');
    }}
    function shareLink() {{
      navigator.clipboard.writeText(window.location.href);
      alert('링크가 복사되었습니다.');
    }}
  </script>
</body>
</html>"""

    out = job_dir / "showcase.html"
    out.write_text(html, encoding="utf-8")
    return out


def _escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
python -m pytest tests/test_showcase_generator.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add utils/showcase_generator.py tests/test_showcase_generator.py
git commit -m "feat: add Opal-style HTML showcase generator"
```

---

## Phase 3 — 파이프라인·DB·API 확장

### Task 4: pipeline 6단계 showcase 추가

**Files:**
- Modify: `worker/pipeline.py`
- Modify: `tests/test_pipeline.py` (mock showcase 호출 검증 추가)

- [ ] **Step 1: pipeline.py import 및 6단계 추가**

`worker/pipeline.py` 상단 import 추가:

```python
from utils.config import get_settings
from utils.showcase_generator import generate_showcase
```

`run_pipeline` return 직전에 추가:

```python
    logger.info("[%s] showcase", job_id)
    settings = get_settings()
    showcase_path = generate_showcase(
        job_id=job_id,
        job_dir=base,
        product_url=url,
        base_url=settings.showcase_base_url,
    )

    return {
        "job_id": job_id,
        "script": script,
        "output_path": final,
        "showcase_path": str(showcase_path),
    }
```

- [ ] **Step 2: Commit**

```bash
git add worker/pipeline.py
git commit -m "feat: add showcase generation as pipeline step 6"
```

---

### Task 5: DB·워커 tasks 확장

**Files:**
- Modify: `db/models.py`
- Modify: `worker/tasks.py`
- Modify: `utils/notifier.py`

- [ ] **Step 1: Job 모델에 showcase_path 추가**

`db/models.py` `Job` 클래스:

```python
    showcase_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: tasks.py STEPS 및 _update 확장**

```python
STEPS = ["scraping", "transcribing", "scripting", "tts", "editing", "showcase"]
```

`_update` 시그니처에 `showcase: str | None = None` 추가, 본문:

```python
    job.showcase_path = showcase or job.showcase_path
```

성공 시 `_update` 호출:

```python
        _update(
            db,
            job_id,
            "completed",
            "showcase",
            output=result["output_path"],
            script=result["script"],
            showcase=result.get("showcase_path"),
        )
```

- [ ] **Step 3: notifier 성공 함수 추가**

`utils/notifier.py`:

```python
def format_success_message(
    job_id: str,
    url: str,
    mp4_url: str,
    showcase_url: str,
) -> str:
    return (
        "[Insta_Ali_Translate] 릴스 생성 완료 ✅\n"
        f"URL: {url}\n"
        f"MP4: {mp4_url}\n"
        f"쇼케이스: {showcase_url}"
    )


def send_telegram_success(
    job_id: str,
    url: str,
    mp4_url: str,
    showcase_url: str,
) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram credentials missing; skip success notification")
        return
    text = format_success_message(job_id, url, mp4_url, showcase_url)
    api_url = _TELEGRAM_API_BASE.format(token=settings.telegram_bot_token)
    requests.post(
        api_url,
        json={"chat_id": settings.telegram_chat_id, "text": text},
        timeout=30,
    )
```

`process_video_job` 성공 분기에서 (n8n이 주 알림이지만 워커 백업용):

```python
        settings = get_settings()
        mp4 = f"{settings.showcase_base_url}/assets/jobs/{job_id}/final_shorts.mp4"
        showcase = f"{settings.showcase_base_url}/showcase/{job_id}"
        send_telegram_success(job_id, url, mp4, showcase)
```

실패 메시지 prefix를 `[Insta_Ali_Translate]`로 변경.

- [ ] **Step 4: Commit**

```bash
git add db/models.py worker/tasks.py utils/notifier.py
git commit -m "feat: persist showcase_path and add telegram success notification"
```

---

### Task 6: Showcase 라우트 및 Jobs API 확장

**Files:**
- Create: `web/routes/showcase.py`
- Modify: `web/routes/jobs.py`
- Modify: `web/app.py`
- Create: `tests/test_showcase_route.py`

- [ ] **Step 1: showcase 라우트**

```python
# web/routes/showcase.py
"""HTML 쇼케이스 페이지 서빙."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db.models import Job
from web.deps import get_db

router = APIRouter(tags=["showcase"])


@router.get("/showcase/{job_id}")
def get_showcase(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    path = (
        Path(job.showcase_path)
        if job.showcase_path
        else Path(f"assets/jobs/{job_id}/showcase.html")
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="Showcase not ready")
    return FileResponse(path, media_type="text/html")
```

- [ ] **Step 2: jobs.py 응답에 showcase_url 추가**

`JobDetailResponse` 및 `_job_summary`에:

```python
    showcase_url: Optional[str] = None
```

`GET /api/jobs/{id}` 빌드 시:

```python
    showcase_url=f"/showcase/{job.id}" if job.showcase_path or job.status == "completed" else None,
```

- [ ] **Step 3: app.py 라우터 등록**

```python
from web.routes import jobs, pages, showcase

app.include_router(showcase.router)
```

- [ ] **Step 4: 라우트 테스트**

```python
# tests/test_showcase_route.py
from pathlib import Path

from fastapi.testclient import TestClient

from db.models import Job
from db.session import get_sync_session
from web.app import app

client = TestClient(app)


def test_showcase_404_when_missing():
    r = client.get("/showcase/nonexistent-id")
    assert r.status_code == 404
```

- [ ] **Step 5: Commit**

```bash
git add web/routes/showcase.py web/routes/jobs.py web/app.py tests/test_showcase_route.py
git commit -m "feat: add showcase route and showcase_url in jobs API"
```

---

## Phase 4 — Docker Compose 풀스택

### Task 7: Dockerfile Nanum 폰트 추가

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Dockerfile에 폰트 패키지 추가**

`apt-get install` 줄에 추가:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-nanum \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile
git commit -m "chore: add Nanum font for Docker subtitle rendering"
```

---

### Task 8: docker-compose.yml (5서비스)

**Files:**
- Create: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: docker-compose.yml 작성**

```yaml
# Insta_Ali_Translate — n8n + redis + web + worker + nginx
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped

  web:
    build: .
    command: uvicorn web.app:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    volumes:
      - ./assets:/app/assets
      - ./db:/app/db
      - ./.env:/app/.env
    environment:
      REDIS_URL: redis://redis:6379/0
      SUBTITLE_FONT_PATH: /usr/share/fonts/truetype/nanum/NanumGothicBold.ttf
      SHOWCASE_BASE_URL: http://localhost:8080
    depends_on:
      - redis
    restart: unless-stopped

  worker:
    build: .
    command: python worker/run_worker.py
    volumes:
      - ./assets:/app/assets
      - ./db:/app/db
      - ./.env:/app/.env
    environment:
      REDIS_URL: redis://redis:6379/0
      SUBTITLE_FONT_PATH: /usr/share/fonts/truetype/nanum/NanumGothicBold.ttf
      SHOWCASE_BASE_URL: http://localhost:8080
    depends_on:
      - redis
    restart: unless-stopped

  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=localhost
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - WEBHOOK_URL=http://localhost:5678/
      - GENERIC_TIMEZONE=Asia/Seoul
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
    volumes:
      - ./n8n_data:/home/node/.n8n
      - ./n8n/workflows:/import:ro
    depends_on:
      - web
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./assets:/var/www/assets:ro
    depends_on:
      - web
    restart: unless-stopped
```

- [ ] **Step 2: 빌드·기동 스모크 테스트**

```powershell
cd E:\Vibe\Insta_Ali_Translate
copy .env.example .env
# .env에 OPENAI_API_KEY, ANTHROPIC_API_KEY 채우기
docker compose build
docker compose up -d
docker compose ps
```
Expected: redis, web, worker, n8n, nginx 모두 `running`

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose with n8n, worker, and nginx"
```

---

### Task 9: nginx 설정

**Files:**
- Create: `nginx/nginx.conf`

- [ ] **Step 1: nginx.conf 작성**

```nginx
server {
    listen 80;
    server_name localhost;

    # MP4·MP3·HTML 정적 자산
    location /assets/ {
        alias /var/www/assets/;
        add_header Access-Control-Allow-Origin *;
    }

    # FastAPI 쇼케이스 HTML
    location /showcase/ {
        proxy_pass http://web:8000/showcase/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

- [ ] **Step 2: nginx 재기동 후 정적 파일 확인**

```powershell
docker compose restart nginx
curl -I http://localhost:8080/showcase/test
```
Expected: 404 (정상 — job 없음)

- [ ] **Step 3: Commit**

```bash
git add nginx/nginx.conf
git commit -m "feat: add nginx config for assets and showcase proxy"
```

---

## Phase 5 — n8n 워크플로

### Task 10: n8n reel-pipeline 워크플로 구성

**Files:**
- Create: `n8n/workflows/reel-pipeline.json`
- Create: `README.md` (n8n import·Form URL 안내)

- [ ] **Step 1: n8n UI에서 워크플로 수동 구성 (또는 JSON import)**

노드 구성 (설계 §3.1):

1. **Form Trigger** — 필드 `product_url` (required text)
2. **Set** — `product_url` = `{{ $json.product_url }}`
3. **HTTP Request** — POST `http://web:8000/api/jobs`, JSON body `{"url": "{{ $json.product_url }}"}`
4. **Set** — `job_id` = `{{ $json.id }}`
5. **Loop** (60 iterations):
   - **Wait** 30s
   - **HTTP Request** — GET `http://web:8000/api/jobs/{{ $json.job_id }}`
   - **IF** `{{ $json.status }}` equals `completed` → break
   - **IF** `{{ $json.status }}` equals `failed` → 실패 분기
6. **IF** completed:
   - **Telegram** — 성공 메시지:
     ```
     [Insta_Ali_Translate] 릴스 생성 완료 ✅
     URL: {{ $('Set').item.json.product_url }}
     MP4: http://localhost:8080/assets/jobs/{{ $json.id }}/final_shorts.mp4
     쇼케이스: http://localhost:8080/showcase/{{ $json.id }}
     ```
7. **IF** failed:
   - **Telegram** — 실패 메시지 (error_message, current_step)

- [ ] **Step 2: n8n에서 Telegram 크리덴셜 등록**

n8n UI → Credentials → Telegram → Bot Token 입력

- [ ] **Step 3: 워크플로 Export → `n8n/workflows/reel-pipeline.json` 저장**

- [ ] **Step 4: Form URL 확인**

n8n UI → Form Trigger 노드 → Production URL 복사  
예: `http://localhost:5678/form/xxxx`

- [ ] **Step 5: Commit**

```bash
git add n8n/workflows/reel-pipeline.json README.md
git commit -m "feat: add n8n reel pipeline workflow export"
```

---

## Phase 6 — 통합 테스트 및 문서

### Task 11: README 및 E2E 검증

**Files:**
- Create/Modify: `README.md`

- [ ] **Step 1: README 작성**

포함 섹션:
- 사전 요구사항 (Docker Desktop, API 키)
- `.env` 설정
- `docker compose up -d`
- n8n Form URL 접속 방법
- AliExpress 세션 준비 (`python main.py --login` 또는 세션 파일 복사)
- 포트 표 (5678, 8080, 8000)
- 텔레그램 설정

- [ ] **Step 2: API 단건 테스트**

```powershell
curl -X POST http://localhost:8000/api/jobs -H "Content-Type: application/json" -d "{\"url\": \"https://www.aliexpress.com/item/XXXX.html\"}"
# job_id로 폴링
curl http://localhost:8000/api/jobs/{job_id}
```
Expected: 최종 `status: completed`, `showcase_url: /showcase/{id}`

- [ ] **Step 3: 쇼케이스 브라우저 확인**

`http://localhost:8080/showcase/{job_id}` — 9:16 플레이어·대본·오디오

- [ ] **Step 4: n8n Form E2E**

Form에 실제 AliExpress URL 제출 → 30분 내 텔레그램 완료 메시지

- [ ] **Step 5: Commit**

```bash
git add README.md walkthrough.md
git commit -m "docs: add setup guide and E2E verification steps"
```

---

## Execution Notes

- **DB 마이그레이션:** SQLite `showcase_path` 컬럼은 기존 `jobs.db`가 있으면 삭제 후 재생성하거나 Alembic 없이 `db/jobs.db` 삭제 후 재기동.
- **n8n ↔ Docker 네트워크:** n8n 컨테이너에서 `http://web:8000`은 동일 compose 네트워크로 해석됨.
- **호스트 링크:** 텔레그램·쇼케이스 URL은 `SHOWCASE_BASE_URL=http://localhost:8080` (호스트 기준).
- **AliExpress 세션:** `assets/sessions/aliexpress_state.json` 볼륨 유지 필수.
