# Insta_Ali_Translate

Google Opal 스타일 **AliExpress → 한국어 9:16 인스타 릴스** 자동 생성 파이프라인입니다.

**n8n**이 Form Trigger로 URL을 받고, **Python RQ 워커**가 스크래핑·STT·대본·TTS·영상 합성·HTML 쇼케이스를 실행합니다. 완료/실패 시 **Telegram**으로 MP4·쇼케이스 링크를 알립니다.

| 문서 | 설명 |
|------|------|
| [설계 스펙](docs/superpowers/specs/2026-06-24-n8n-reel-pipeline-design.md) | 아키텍처·API·n8n 폴링 정책 |
| [구현 계획](docs/superpowers/plans/2026-06-24-n8n-reel-pipeline.md) | Task 1–11 체크리스트 |
| [n8n 워크플로 가이드](n8n/workflows/README.md) | Import·수동 설정·Telegram 템플릿 |

---

## 사전 요구사항

| 항목 | 설명 |
|------|------|
| **Docker Desktop** | Compose v2 (Windows / macOS / Linux) |
| **OpenAI API Key** | Whisper STT + TTS |
| **Anthropic API Key** | Claude 대본 생성 |
| **Telegram Bot** | Bot Token + Chat ID (n8n·워커 알림) |
| **AliExpress 세션** | Playwright 로그인 상태 (`python main.py --login`) |

---

## 빠른 시작 (Docker Compose)

### 1. 환경 변수

```powershell
copy .env.example .env
```

`.env`에 필수 값을 채웁니다.

| 변수 | 설명 |
|------|------|
| `OPENAI_API_KEY` | OpenAI (Whisper + TTS) |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 |
| `TELEGRAM_CHAT_ID` | 알림 수신 채팅 ID |
| `N8N_ENCRYPTION_KEY` | n8n 크리덴셜 암호화 (32자 이상 랜덤) |
| `SHOWCASE_BASE_URL` | `http://localhost:8080` (기본값) |

Docker/Linux 자막 폰트 (compose가 web/worker에 주입하지만 `.env`에도 명시 권장):

```env
SUBTITLE_FONT_PATH=/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf
```

### 2. AliExpress 세션 준비

**로그인이 필수는 아닙니다.** 공개 상품 페이지는 세션 없이도 스크래핑될 수 있습니다.  
로그인·캡차 때문에 `python main.py --login`이 안 될 때는 아래 대안을 사용하세요.

#### 방법 A — 세션 없이 바로 테스트 (가장 간단)

세션 파일이 없으면 스크래퍼가 로그인 없이 페이지를 엽니다. n8n Form에 URL을 넣고 먼저 시도해 보세요.

#### 방법 B — Chrome 쿠키 가져오기 (권장 대안)

1. **일반 Chrome**에서 https://ko.aliexpress.com 로그인
2. Chrome 확장 **Cookie-Editor** 설치 → aliexpress.com → **Export** → JSON 저장
3. 프로젝트에서 변환:

```powershell
.\.venv\Scripts\Activate.ps1
python main.py --import-cookies C:\Users\YOU\Downloads\cookies.json
```

세션 파일: `assets/sessions/aliexpress_state.json` (Docker `./assets` 볼륨과 공유)

#### 방법 C — Playwright 로그인 (개선됨)

`AliExpress_로그인.bat` 또는:

```powershell
python main.py --login
```

- 설치된 **Chrome → Edge → Chromium** 순으로 브라우저 시도
- `https://ko.aliexpress.com` 한국 사이트로 접속

#### 방법 D — 프록시 (지역 차단 시)

`.env`에 `PROXY_URL=http://user:pass@host:port` 설정

Compose 기동 **전** 또는 **후** 호스트에서 세션을 준비합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

### 3. 기동

```powershell
docker compose up --build -d
docker compose ps
```

5개 서비스(`redis`, `web`, `worker`, `n8n`, `nginx`)가 `running`이어야 합니다.

---

## 포트 및 URL

| 포트 | 서비스 | 용도 |
|------|--------|------|
| **5678** | n8n | 워크플로 UI + Form Trigger |
| **8080** | nginx | MP4·HTML 쇼케이스 (외부 접근) |
| **8000** | web (FastAPI) | API·디버깅 |

| URL | 설명 |
|-----|------|
| [http://localhost:5678](http://localhost:5678) | n8n 에디터 |
| [http://localhost:8080/showcase/{job_id}](http://localhost:8080/showcase/) | Opal 스타일 HTML 쇼케이스 |
| [http://localhost:8080/assets/jobs/{job_id}/final_shorts.mp4](http://localhost:8080/assets/jobs/) | 완성 MP4 |
| [http://localhost:8000/docs](http://localhost:8000/docs) | FastAPI Swagger |

---

## n8n Form 사용법

1. [n8n 워크플로 Import](n8n/workflows/README.md) — `n8n/workflows/reel-pipeline.json`
2. Telegram 크리덴셜·Chat ID 설정 (Import 후 필수)
3. 워크플로 **Active** 토글
4. **Form Trigger** 노드 → **Production URL** 복사  
   예: `http://localhost:5678/form/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
5. 브라우저에서 Form URL 접속 → AliExpress 상품 URL 입력 → 제출
6. 워커 처리 중 n8n이 30초 간격으로 최대 60회 폴링 → 완료 시 Telegram 알림

---

## Telegram 설정

### Bot 생성

1. Telegram에서 [@BotFather](https://t.me/BotFather) → `/newbot`
2. 발급된 **Bot Token** → `.env`의 `TELEGRAM_BOT_TOKEN`

### Chat ID 확인

1. Bot과 대화 시작 후 아무 메시지 전송
2. `https://api.telegram.org/bot<TOKEN>/getUpdates` 에서 `chat.id` 확인
3. `.env`의 `TELEGRAM_CHAT_ID`에 입력

### n8n 연동

n8n UI → Credentials → Telegram → Bot Token 등록 후, 워크플로 Telegram 노드 3개에 연결합니다.  
자세한 내용: [n8n/workflows/README.md](n8n/workflows/README.md)

워커(`utils/notifier.py`)도 동일 `.env` 토큰으로 백업 알림을 보냅니다.

---

## 쇼케이스 URL 패턴

작업 완료 후 nginx(:8080)에서 제공됩니다.

| 리소스 | URL 패턴 |
|--------|----------|
| HTML 쇼케이스 | `http://localhost:8080/showcase/{job_id}` |
| MP4 | `http://localhost:8080/assets/jobs/{job_id}/final_shorts.mp4` |
| 나레이션 MP3 | `http://localhost:8080/assets/jobs/{job_id}/dubbing.mp3` |

`{job_id}`는 `POST /api/jobs` 응답의 `id` (UUID)입니다.

---

## E2E 검증

### 1. API 단건 테스트

```powershell
curl -X POST http://localhost:8000/api/jobs `
  -H "Content-Type: application/json" `
  -d "{\"url\": \"https://www.aliexpress.com/item/XXXX.html\"}"

curl http://localhost:8000/api/jobs/{job_id}
```

성공 기준: `status: "completed"`, `showcase_url: "/showcase/{id}"`

### 2. 쇼케이스 브라우저 확인

`http://localhost:8080/showcase/{job_id}` — 9:16 플레이어, 한국어 대본, 나레이션 오디오

### 3. n8n Form E2E

1. Form Production URL에 실제 AliExpress URL 제출
2. 약 30분 이내 Telegram 완료 메시지 수신
3. MP4·쇼케이스 링크 클릭 확인

### 4. Compose 상태·로그

```powershell
docker compose ps
docker compose logs -f worker
docker compose logs -f n8n
```

---

## 아키텍처 요약

```
n8n (5678)  Form → POST /api/jobs → Poll GET /api/jobs/{id} → Telegram
                    ↓ Docker network
web (8000) ←→ redis ←→ worker (RQ 파이프라인 6단계)
                    ↓ ./assets
nginx (8080)  /showcase/{id}, /assets/jobs/
```

파이프라인 단계: `scraping` → `transcribing` → `scripting` → `tts` → `editing` → `showcase`

---

## 로컬 개발 (Docker 없이)

Redis + Python venv로 web/worker를 직접 실행할 수 있습니다. 자세한 CLI·로컬 설정은 Insta_Ali 베이스 README 패턴을 따릅니다.

```powershell
python worker/run_worker.py          # 터미널 1
uvicorn web.app:app --reload --port 8000   # 터미널 2
```

---

## 테스트

```powershell
pytest -v
```

---

## API 요약

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/jobs` | 단건 URL 작업 등록 (n8n) |
| `GET` | `/api/jobs/{id}` | 상태 폴링 (n8n) |
| `GET` | `/api/jobs/{id}/download` | MP4 다운로드 |
| `GET` | `/showcase/{id}` | HTML 쇼케이스 |
