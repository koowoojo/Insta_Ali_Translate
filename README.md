# Insta_Ali

AliExpress 상품 URL을 입력하면 스크래핑 → 스크립트 생성 → TTS → 9:16 숏폼 영상까지 자동 처리하는 파이프라인입니다.  
FastAPI 웹 대시보드, RQ 백그라운드 워커, CLI를 모두 지원합니다.

## 사전 요구사항

| 환경 | 필요 항목 |
|------|-----------|
| 로컬 (Windows) | Python 3.11+, Redis, ffmpeg, Playwright Chromium |
| Docker | Docker Desktop (또는 Docker Engine + Compose v2) |

## 환경 변수 설정

1. 저장소 루트에서 `.env.example`을 복사합니다.

```powershell
copy .env.example .env
```

2. `.env`에 필수 API 키를 채웁니다.

| 변수 | 설명 |
|------|------|
| `OPENAI_API_KEY` | OpenAI (Whisper STT + TTS 더빙) |
| `ANTHROPIC_API_KEY` | Anthropic (Claude 스크립트) |
| `OPENAI_TTS_MODEL` | `tts-1-hd` (선택, OpenAI TTS 모델) |
| `OPENAI_TTS_VOICE` | `nova` (선택, OpenAI TTS 보이스) |

3. 선택·인프라 변수 (기본값은 `.env.example` 참고)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `REDIS_URL` | `redis://localhost:6379/0` | RQ 큐 Redis URL |
| `DATABASE_URL` | `sqlite:///db/jobs.db` | SQLite DB 경로 |
| `MAX_CONCURRENT_JOBS` | `2` | 동시 처리 워커 수 |
| `ALIEXPRESS_SESSION_PATH` | `assets/sessions/aliexpress_state.json` | Playwright 세션 파일 |
| `SUBTITLE_FONT_PATH` | `C:/Windows/Fonts/malgun.ttf` | 자막 폰트 (Docker/Linux에서는 Linux 경로로 변경) |

4. 데이터 디렉터리를 준비합니다 (없으면 자동 생성되지만, 세션·DB 경로를 위해 권장).

```powershell
mkdir assets\sessions, db -Force
```

## 로컬 실행 (Windows)

### 1. Python 의존성

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

### 2. Redis 기동

Docker로 Redis만 실행하는 경우:

```powershell
docker run -d -p 6379:6379 --name insta-redis redis:7-alpine
```

또는 WSL/별도 Redis 서버를 사용합니다. `.env`의 `REDIS_URL`이 실제 Redis 주소와 일치해야 합니다.

### 3. 워커 + 웹 서버 (터미널 2개)

```powershell
# 터미널 1 — RQ 워커
python worker/run_worker.py

# 터미널 2 — FastAPI 대시보드
uvicorn web.app:app --reload --port 8000
```

브라우저에서 [http://localhost:8000](http://localhost:8000) 으로 접속합니다.

## Docker Compose

`.env` 파일이 **반드시** 존재해야 합니다 (compose가 `./.env`를 볼륨으로 마운트).

```powershell
copy .env.example .env
# .env 편집 후
docker compose up --build -d
```

| 서비스 | 역할 | 포트 |
|--------|------|------|
| `redis` | RQ 큐 | `6379` |
| `web` | FastAPI (`uvicorn`) | `8000` |
| `worker` | RQ 워커 (`worker/run_worker.py`) | (내부) |

볼륨 마운트:

- `./assets` → 스크래핑 세션·중간·출력 파일
- `./db` → SQLite `jobs.db`
- `./.env` → 환경 변수

`docker-compose.yml`은 `REDIS_URL=redis://redis:6379/0` 을 web/worker에 주입하므로, `.env`에 `localhost`가 있어도 Compose 환경에서는 Redis 서비스 이름으로 연결됩니다.

### Docker에서 자막 폰트

Windows 기본값(`malgun.ttf`)은 Linux 컨테이너에서 사용할 수 없습니다. `.env`에 예를 들어 다음을 설정하세요.

```env
SUBTITLE_FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
```

(이미지에 DejaVu 폰트가 Playwright `--with-deps` 설치 시 포함됩니다. 한글 자막이 필요하면 Dockerfile에 `fonts-noto-cjk` 추가를 검토하세요.)

### Compose 명령어

```powershell
docker compose ps          # 상태 확인
docker compose logs -f web # web 로그
docker compose down        # 중지·컨테이너 제거
```

## CLI 사용법

CLI는 Redis/RQ 없이 **동기**로 파이프라인을 실행합니다 (로컬 Python 환경).

```powershell
# AliExpress 로그인 세션 저장 (Headful 브라우저)
python main.py --login

# 단건 URL 처리
python main.py --url "https://www.aliexpress.com/item/....html"

# CSV 배치 (url 또는 URL 컬럼)
python main.py --batch urls.csv
```

## 웹 API 요약

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/jobs` | 단건 URL 작업 등록 |
| `POST` | `/api/jobs/batch` | CSV 배치 등록 |
| `GET` | `/api/jobs` | 작업 목록 |
| `GET` | `/api/jobs/{id}` | 작업 상세 |
| `GET` | `/api/jobs/{id}/download` | 완료 영상 다운로드 |
| `POST` | `/api/jobs/{id}/retry` | 실패 작업 재시도 |

## 테스트

```powershell
pytest -v
```
