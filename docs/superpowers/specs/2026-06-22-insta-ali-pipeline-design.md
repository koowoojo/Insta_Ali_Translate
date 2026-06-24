# Insta_Ali — AliExpress 숏폼 영상 자동 생성 파이프라인 설계서

> 작성일: 2026-06-22  
> 상태: 승인됨 (브레인스토밍 완료)

---

## 1. 개요

### 1.1 목표

AliExpress 상품 URL에서 영상을 스크래핑하고, AI로 대본을 번역·윤문한 뒤 고품질 TTS와 자막이 입혀진 9:16 세로형 숏폼 영상을 자동 생성하는 파이프라인을 구축한다.

### 1.2 확정된 요구사항

| 항목 | 선택 |
|------|------|
| 실행 방식 | 배치 처리 + 웹 UI |
| UI/워커 | 통합 대시보드 + 백그라운드 워커 (페이지 닫아도 작업 지속) |
| 아키텍처 | **FastAPI + RQ + Redis + SQLite** |
| 배포 | Windows 로컬 우선 개발 → Docker Compose 이전 용이 |
| 스크래핑 | 로그인 세션 재사용 + 프록시 옵션, 차단 시 재시도 |
| 영상 동기화 | 오디오 기준; 영상이 짧으면 **루프**, 길면 컷 |
| 동시 처리 | `MAX_CONCURRENT_JOBS` 환경변수 (기본값 2) |
| 알림 | 웹 대시보드 + 텔레그램 실패 알림 |
| 이력 저장 | SQLite (`jobs.db`) |

### 1.3 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| 스크래핑 | Playwright |
| STT | OpenAI `whisper-1` |
| LLM | Anthropic Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`) |
| TTS | ElevenLabs (`eleven_multilingual_v2`) |
| 영상 편집 | MoviePy ≥1.0.3, OpenCV |
| 웹 | FastAPI + Jinja2 + HTMX |
| 큐 | RQ + Redis |
| DB | SQLite + SQLAlchemy 2.x |
| 설정 | python-dotenv |

---

## 2. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  Web Dashboard (FastAPI + Jinja2/HTMX)                    │
│  - 단건 URL 제출 / CSV 업로드                            │
│  - 작업 목록·진행률·다운로드                             │
└──────────────────────┬──────────────────────────────────┘
                       │ enqueue job
                       ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│  Redis       │◄──│  RQ Worker   │──►│  SQLite jobs.db  │
│  (job queue) │   │  (N workers) │   │  (영구 이력)      │
└──────────────┘   └──────┬───────┘   └──────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    scraper.py    audio_processor.py  script_writer.py
          │               │               │
          └───────────────┼───────────────┘
                          ▼
              tts_generator.py → video_editor.py
                          │
                          ▼
              assets/jobs/{job_id}/final_shorts.mp4
```

### 2.1 디렉터리 구조

```
/project_root
  ├── .env
  ├── .env.example
  ├── main.py                  # CLI 진입점 (단건/배치/로그인)
  ├── docker-compose.yml       # Phase 2: web + worker + redis
  ├── requirements.txt
  ├── walkthrough.md
  ├── web/
  │   ├── app.py               # FastAPI 앱
  │   ├── routes/
  │   │   ├── jobs.py          # API + 페이지 라우트
  │   │   └── pages.py
  │   ├── templates/
  │   │   ├── base.html
  │   │   ├── index.html
  │   │   ├── jobs.html
  │   │   └── job_detail.html
  │   └── static/
  ├── worker/
  │   ├── tasks.py             # RQ 작업 정의
  │   ├── pipeline.py          # 파이프라인 오케스트레이션
  │   └── run_worker.py        # 워커 실행 스크립트
  ├── db/
  │   ├── models.py            # SQLAlchemy 모델
  │   ├── session.py           # DB 세션 팩토리
  │   └── jobs.db              # (런타임 생성)
  ├── modules/
  │   ├── scraper.py
  │   ├── audio_processor.py
  │   ├── script_writer.py
  │   ├── tts_generator.py
  │   └── video_editor.py
  ├── utils/
  │   ├── notifier.py          # 텔레그램 알림
  │   ├── config.py            # 환경변수 로드 (pydantic-settings)
  │   └── exceptions.py        # PipelineError 등
  ├── tests/
  │   └── test_pipeline.py
  ├── logs/                    # (런타임 생성)
  └── assets/
      ├── sessions/            # Playwright storage_state
      └── jobs/{job_id}/       # 작업별 산출물 격리
          ├── raw_video.mp4
          ├── extracted_audio.wav
          ├── script_step1.json
          ├── dubbing.mp3
          └── final_shorts.mp4
```

### 2.2 작업 흐름

1. 사용자가 웹 UI 또는 CLI로 URL 제출
2. SQLite에 `pending` 작업 생성
3. RQ 큐에 `process_video_job(job_id, url)` 등록
4. 워커가 5단계 파이프라인 순차 실행, 단계마다 DB 상태 갱신
5. 완료 시 `completed` + 다운로드 가능
6. 실패 시 `failed` + 대시보드 표시 + 텔레그램 알림

---

## 3. 핵심 파이프라인 모듈

### 3.1 `scraper.py` — Playwright 스크래핑

| 항목 | 내용 |
|------|------|
| 입력 | AliExpress 상품 URL, `job_id` |
| 출력 | `assets/jobs/{job_id}/raw_video.mp4` |
| 핵심 함수 | `scrape_video(url: str, output_path: str) -> str` |

**동작 순서:**

1. Playwright Chromium Headless 기동 (`PROXY_URL` 환경변수 적용)
2. `assets/sessions/aliexpress_state.json` 존재 시 `storage_state` 로드
3. 페이지 로드 후 `<video>` 태그 `src` 또는 페이지 소스 내 MP4 URL 탐색
4. HTTP로 MP4 다운로드 → `raw_video.mp4` 저장
5. 비디오 없음 → `VideoNotFoundError` 발생 + 로그

**세션 초기화:** `python main.py --login` 또는 `python -m modules.scraper --login` — Headful 브라우저로 수동 로그인 후 세션 저장.

**재시도:** CAPTCHA/차단 감지 시 최대 3회 재시도 (지수 백오프). 실패 시 작업 `failed` + 텔레그램 알림.

### 3.2 `audio_processor.py` — Whisper STT

| 항목 | 내용 |
|------|------|
| 입력 | `raw_video.mp4` |
| 출력 | 원본 텍스트 문자열, `extracted_audio.wav` |
| 핵심 함수 | `extract_audio(video_path) -> str`, `transcribe(audio_path) -> str` |

MoviePy/ffmpeg로 오디오 분리 → OpenAI `whisper-1` API 호출 → 언어 자동 감지, 원문 텍스트 반환.

### 3.3 `script_writer.py` — Claude 다단계 프롬프팅

| 항목 | 내용 |
|------|------|
| 입력 | STT 원문 텍스트 |
| 출력 | 최종 한국어 세일즈 대본 문자열 |
| 핵심 함수 | `generate_script(raw_text: str) -> str` |

**Step 1 — `analyze_product(raw_text)`**

- 핵심 소구점·제품 특징 요약
- 반환: JSON (`hooks`, `features`, `target_audience`)
- 저장: `assets/jobs/{job_id}/script_step1.json`

**Step 2 — `write_sales_script(summary)`**

- 3초 후킹 멘트 + 홈쇼핑 톤 한국어 대본
- 40초 이내 (약 150~200자) 제한을 프롬프트에 명시

모델: `claude-3-5-sonnet-20241022` (Anthropic SDK).

### 3.4 `tts_generator.py` — ElevenLabs TTS

| 항목 | 내용 |
|------|------|
| 입력 | 최종 한국어 대본 |
| 출력 | `assets/jobs/{job_id}/dubbing.mp3` |
| 핵심 함수 | `generate_speech(text: str, output_path: str) -> str` |

- `ELEVENLABS_VOICE_ID` 환경변수
- `model_id="eleven_multilingual_v2"`

### 3.5 `video_editor.py` — MoviePy 합성

| 항목 | 내용 |
|------|------|
| 입력 | `raw_video.mp4`, `dubbing.mp3`, 대본 텍스트 |
| 출력 | `assets/jobs/{job_id}/final_shorts.mp4` |
| 핵심 함수 | `compose_shorts(video, audio, script, output) -> str` |

**편집 순서:**

1. 원본 오디오 제거 (Mute)
2. 9:16 (1080×1920) 중앙 크롭 (OpenCV 비율 계산 + MoviePy `crop`)
3. 오디오 길이 기준 동기화:
   - 영상 > 오디오 → 오디오 끝에서 영상 컷
   - 영상 < 오디오 → 영상 루프 후 오디오 길이에 맞춤
4. 자막 합성:
   - 대본 15~20자 단위 청킹 (`SUBTITLE_CHUNK_SIZE`, 기본 18)
   - 오디오 길이에 균등 배분 타이밍
   - 하단 중앙, 노란색 글씨 + 검은색 Stroke
   - 폰트: `SUBTITLE_FONT_PATH` (기본 Windows `C:/Windows/Fonts/malgun.ttf`)
5. 렌더: `libx264` + `aac`

### 3.6 `worker/pipeline.py` — 오케스트레이션

```python
def run_pipeline(job_id: str, url: str) -> None:
    update_status(job_id, "scraping")
    scraper.scrape_video(url, ...)
    update_status(job_id, "transcribing")
    text = audio_processor.transcribe(...)
    update_status(job_id, "scripting")
    script = script_writer.generate_script(text)
    update_status(job_id, "tts")
    tts_generator.generate_speech(script, ...)
    update_status(job_id, "editing")
    video_editor.compose_shorts(...)
    update_status(job_id, "completed")
```

각 단계 실패 시 `failed` + `error_message` 저장 + `notifier.send_telegram(...)`.

---

## 4. 웹 대시보드 · RQ 워커 · DB

### 4.1 웹 대시보드

**화면:**

| 페이지 | 기능 |
|--------|------|
| 홈 / 새 작업 | 단건 URL 입력 + CSV 업로드 (컬럼: `url`) |
| 작업 목록 | ID, URL, 상태, 진행 단계, 생성 시각, 다운로드 |
| 작업 상세 | 단계별 타임라인, 에러, 중간 산출물, 재시도 |

**상태:** `pending` → `scraping` → `transcribing` → `scripting` → `tts` → `editing` → `completed` / `failed`

**기술:** FastAPI + Jinja2 + HTMX (5초 폴링 자동 갱신)

**API:**

```
POST /api/jobs              — 단건 URL 제출
POST /api/jobs/batch        — CSV 업로드 배치 등록
GET  /api/jobs              — 작업 목록 (status 필터)
GET  /api/jobs/{id}         — 작업 상세
GET  /api/jobs/{id}/download — final_shorts.mp4 다운로드
POST /api/jobs/{id}/retry   — 실패 작업 재시도
```

### 4.2 RQ 워커

- `worker/tasks.py`: `process_video_job(job_id, url)` RQ 등록
- `worker/run_worker.py`: `rq worker` 실행
- 동시 처리: `MAX_CONCURRENT_JOBS`(기본 2) 워커 프로세스

**Windows 로컬 개발:**

```powershell
# 터미널 1: Redis
docker run -p 6379:6379 redis:7-alpine

# 터미널 2: FastAPI
uvicorn web.app:app --reload --port 8000

# 터미널 3: RQ Worker
python worker/run_worker.py
```

**Docker Compose (Phase 2):** `web`, `worker`, `redis` 3서비스 + `assets/`, `db/`, `.env` 볼륨 마운트.

### 4.3 SQLite 스키마

```sql
CREATE TABLE jobs (
    id            TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    current_step  TEXT,
    error_message TEXT,
    script_text   TEXT,
    output_path   TEXT,
    retry_count   INTEGER DEFAULT 0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at  DATETIME
);

CREATE TABLE job_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     TEXT NOT NULL REFERENCES jobs(id),
    step       TEXT NOT NULL,
    message    TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.4 CLI (`main.py`)

```powershell
python main.py --url "https://aliexpress.com/item/..."
python main.py --batch urls.csv
python main.py --login
```

CLI는 동기 실행 (개발·디버깅). 프로덕션은 웹 + RQ 워커 경로.

### 4.5 텔레그램 알림

- 실패 시에만 전송
- 형식: `[Insta_Ali] 작업 실패\nJob: {id}\nURL: {url}\n단계: {step}\n에러: {message}`
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 미설정 시 스킵 (경고 로그)

---

## 5. 환경변수

```ini
# API Keys
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=

# 인프라
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///db/jobs.db
MAX_CONCURRENT_JOBS=2

# 스크래핑
PROXY_URL=
ALIEXPRESS_SESSION_PATH=assets/sessions/aliexpress_state.json

# 알림
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# 영상 편집
SUBTITLE_FONT_PATH=C:/Windows/Fonts/malgun.ttf
SUBTITLE_FONT_SIZE=48
SUBTITLE_CHUNK_SIZE=18
```

---

## 6. 에러 처리

| 단계 | 실패 유형 | 처리 |
|------|-----------|------|
| 스크래핑 | 비디오 없음, CAPTCHA, 타임아웃 | 최대 3회 재시도 → failed + 텔레그램 |
| STT | 오디오 없음, API 오류 | 즉시 failed |
| LLM | Rate limit, 토큰 초과 | 2회 재시도 (exponential backoff) |
| TTS | API 오류, 빈 대본 | 즉시 failed |
| 영상 편집 | 코덱 오류, 메모리 부족 | 1회 재시도 → failed |

- 공통 예외: `PipelineError(step, message)`
- 모든 예외 `job_logs` 기록
- 로깅: 콘솔 + `logs/app.log` (일별 로테이션)
- MVP: 실패 시 처음부터 재실행; Phase 2에서 단계별 재개

---

## 7. 테스트 전략

| 대상 | 방식 |
|------|------|
| 모듈 단위 | `if __name__ == "__main__"` 독립 실행 |
| 스크래퍼 | Mock HTML fixture + `@pytest.mark.integration` |
| 파이프라인 | API mock (`unittest.mock`) |
| 웹 API | FastAPI `TestClient` / `httpx.AsyncClient` |
| RQ | `fakeredis` 큐·상태 전이 테스트 |

MVP: 모듈 독립 실행 + API 기본 테스트. Playwright E2E는 수동.

---

## 8. 의존성

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

시스템: FFmpeg, Playwright Chromium (`playwright install chromium`).

---

## 9. 구현 단계

| Phase | 범위 |
|-------|------|
| **MVP** | 5개 모듈 + CLI + 동기 파이프라인 검증 |
| **Phase 1** | FastAPI 대시보드 + RQ 워커 + SQLite + 텔레그램 |
| **Phase 2** | Docker Compose, 단계별 재개, 배치 통계 |

---

## 10. 접근법 비교 (기록)

| 접근법 | 요약 | 채택 |
|--------|------|------|
| FastAPI + Celery + Redis + SQLite | 대규모 분산, 설정 무거움 | ✗ |
| **FastAPI + RQ + Redis + SQLite** | 단순·충분한 확장성 | **✓** |
| FastAPI + SQLite 큐 (Redis 없음) | 의존성 최소, 동시성 직접 구현 | ✗ |
