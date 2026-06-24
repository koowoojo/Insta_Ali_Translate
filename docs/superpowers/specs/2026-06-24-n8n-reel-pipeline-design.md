# Insta_Ali_Translate — n8n + Docker 릴스 자동화 파이프라인 설계서

> 작성일: 2026-06-24  
> 상태: 승인됨 (브레인스토밍 완료)

---

## 1. 개요

### 1.1 목표

Google Opal에서 구성했던 AliExpress → 한국어 인스타 릴스 워크플로를 **n8n + Docker**로 재현한다.  
n8n이 핵심 오케스트레이터이며, 영상 처리·스크래핑은 **Insta_Ali 워커 코드를 복제**한 독립 서비스가 담당한다.

### 1.2 확정된 요구사항

| 항목 | 선택 |
|------|------|
| 오케스트레이션 | **n8n** (Form Trigger → 폴링 → 텔레그램 알림) |
| 입력 | AliExpress Product URL (n8n Form) |
| 콘텐츠 수집 | 상품 텍스트 + 페이지 설명 영상 다운로드 |
| 릴 플랜 | 다운로드 영상 **길이에 맞춘** 한국어 대본 생성 |
| 영상 가공 | 한국어 TTS 나레이션 + 자막 + **9:16 리포맷** |
| 워커 | Insta_Ali 코드 **복제·독립 배포** (런타임 분리) |
| 산출물 | **MP4** + Opal 스타일 **HTML 쇼케이스** |
| 트리거 | n8n Form Trigger (URL 붙여넣기) |
| 알림 | 텔레그램 완료/실패 + MP4·HTML 링크 |
| 배포 | Docker Compose 올인원 (로컬) |
| 아키텍처 접근법 | **접근법 1 — n8n 폴링형** |

### 1.3 Opal 워크플로 매핑

| Opal 단계 | 구현 |
|-----------|------|
| Product Url | n8n Form Trigger |
| Fetch Product Content | 워커: `scraper.scrape_video` + 텍스트 추출 |
| Generate Reel Plan | 워커: `script_writer.generate_script` (영상 길이 기준) |
| Generate Narration | 워커: `tts_generator.generate_speech` |
| Apply to Video | 워커: `video_editor.compose_shorts` (9:16 + 자막) |
| Assemble Final Reel | 워커: `showcase_generator.generate_showcase` (HTML) |
| 알림 | n8n Telegram 노드 |

### 1.4 기술 스택

| 영역 | 기술 |
|------|------|
| 오케스트레이션 | n8n (Docker) |
| 워커 | Python 3.11+ (Insta_Ali 복제) |
| 스크래핑 | Playwright |
| STT | OpenAI Whisper |
| LLM | Anthropic Claude |
| TTS | OpenAI TTS |
| 영상 편집 | MoviePy, FFmpeg |
| 큐 | RQ + Redis |
| DB | SQLite |
| 정적 서빙 | nginx |
| 알림 | Telegram Bot API |

---

## 2. 전체 아키텍처

### 2.1 시스템 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│  n8n (port 5678)                                             │
│  Form Trigger → POST /api/jobs → Poll GET /api/jobs/{id}      │
│              → Telegram (완료/실패 + 링크)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (docker network)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  web (FastAPI :8000)  ←→  redis  ←→  worker (RQ)            │
│       ↓                                                      │
│  SQLite jobs.db                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │ 볼륨: ./assets
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  nginx (port 8080)                                           │
│  /showcase/{id}  → HTML 쇼케이스                              │
│  /assets/jobs/   → MP4, MP3 정적 파일                         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Docker Compose 서비스

| 서비스 | 이미지/빌드 | 포트 | 역할 |
|--------|------------|------|------|
| `n8n` | `n8nio/n8n` | 5678 | 워크플로 오케스트레이션 |
| `redis` | `redis:7-alpine` | 6379 | RQ 작업 큐 |
| `web` | Dockerfile | 8000 | FastAPI API |
| `worker` | 동일 Dockerfile | — | RQ Worker 파이프라인 |
| `nginx` | `nginx:alpine` | 8080 | MP4·HTML 외부 서빙 |

### 2.3 공유 볼륨

| 호스트 경로 | 마운트 대상 | 용도 |
|-------------|------------|------|
| `./assets` | web, worker, nginx | MP4·HTML·세션 |
| `./db` | web, worker | SQLite |
| `./n8n_data` | n8n | 워크플로·실행 기록 |
| `./.env` | web, worker | API 키 |

### 2.4 디렉터리 구조

```
Insta_Ali_Translate/
├── docker-compose.yml
├── Dockerfile
├── .env / .env.example
├── nginx/
│   └── nginx.conf
├── n8n/
│   └── workflows/
│       └── reel-pipeline.json
├── web/                         # Insta_Ali 복제
├── worker/
├── modules/
├── db/
├── utils/
│   ├── notifier.py              # 실패 + 성공 알림 확장
│   └── showcase_generator.py    # 신규
├── assets/
│   ├── jobs/{job_id}/
│   │   ├── raw_video.mp4
│   │   ├── dubbing.mp3
│   │   ├── script.txt
│   │   ├── final_shorts.mp4
│   │   └── showcase.html
│   └── sessions/
├── docs/superpowers/specs/
└── walkthrough.md
```

---

## 3. n8n 워크플로 (접근법 1 — 폴링형)

### 3.1 노드 흐름

```
[1] Form Trigger
      ↓
[2] Set — product_url 정규화
      ↓
[3] HTTP Request — POST http://web:8000/api/jobs
      body: { "url": "{{ $json.product_url }}" }
      ↓
[4] Set — job_id 저장
      ↓
[5] Loop (최대 60회)
      ├─ Wait 30s
      ├─ HTTP Request — GET http://web:8000/api/jobs/{{ job_id }}
      └─ IF status == "completed" → 탈출
         IF status == "failed"    → 실패 분기
      ↓
[6] IF completed
      ├─ [성공] Telegram — MP4 + 쇼케이스 링크
      └─ [실패] Telegram — 에러 메시지
```

### 3.2 Form Trigger 필드

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `product_url` | text | Y | AliExpress 상품 URL |

### 3.3 폴링 정책

| 조건 | 동작 |
|------|------|
| `status` = `pending` / `running` | 30초 후 재폴링 |
| `status` = `completed` | 성공 분기 |
| `status` = `failed` | 실패 분기 |
| 60회 초과 (30분) | n8n 타임아웃 텔레그램 |

### 3.4 텔레그램 메시지 형식

**완료:**
```
[Insta_Ali_Translate] 릴스 생성 완료 ✅
URL: {product_url}
MP4: {SHOWCASE_BASE_URL}/assets/jobs/{job_id}/final_shorts.mp4
쇼케이스: {SHOWCASE_BASE_URL}/showcase/{job_id}
```

**실패:**
```
[Insta_Ali_Translate] 작업 실패 ❌
Job: {job_id}
URL: {product_url}
단계: {current_step}
에러: {error_message}
```

---

## 4. Worker API 계약

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `POST` | `/api/jobs` | 작업 생성·RQ 큐 등록 |
| `GET` | `/api/jobs/{id}` | 상태 폴링 (n8n) |
| `GET` | `/api/jobs/{id}/download` | MP4 다운로드 |
| `GET` | `/showcase/{id}` | HTML 쇼케이스 페이지 |

### 4.1 `GET /api/jobs/{id}` 응답

```json
{
  "id": "uuid",
  "url": "https://www.aliexpress.com/item/...",
  "status": "running",
  "current_step": "tts",
  "script_text": "한국어 대본...",
  "output_path": "assets/jobs/{id}/final_shorts.mp4",
  "showcase_url": "/showcase/{id}",
  "error_message": null
}
```

### 4.2 `current_step` 값

`scraping` → `transcribing` → `scripting` → `tts` → `editing` → `showcase` → `completed`

---

## 5. 파이프라인 (Insta_Ali 복제 + 확장)

### 5.1 처리 단계

| 단계 | 모듈 | 산출물 |
|------|------|--------|
| 1. scrape | `scraper.py` | `raw_video.mp4`, 상품 텍스트 |
| 2. transcribe | `audio_processor.py` | `extracted_audio.wav`, 전사 텍스트 |
| 3. script | `script_writer.py` | `script.txt` (영상 길이 기준) |
| 4. tts | `tts_generator.py` | `dubbing.mp3` |
| 5. compose | `video_editor.py` | `final_shorts.mp4` (9:16 + 자막) |
| 6. showcase | `showcase_generator.py` | `showcase.html` |

### 5.2 Insta_Ali 대비 변경 사항

| 파일 | 변경 |
|------|------|
| `utils/showcase_generator.py` | **신규** — Opal 스타일 HTML 생성 |
| `worker/pipeline.py` | 6단계 showcase 추가 |
| `utils/notifier.py` | `send_telegram_success()` 추가 |
| `web/routes/` | `/showcase/{id}` 라우트 추가 |
| `db/models.py` | `showcase_path` 필드 추가 (선택) |

---

## 6. HTML 쇼케이스 스펙

Opal **Assemble Final Reel** 벤치마킹.

### 6.1 레이아웃

| 영역 | 내용 |
|------|------|
| Hero | 9:16 커스텀 비디오 플레이어 (`final_shorts.mp4`) |
| Script Card | 씬별 한국어 대본 (`script.txt`) |
| Audio Module | 나레이션 플레이어 (`dubbing.mp3`) |
| Action Toolbar | Download Video / Copy Script / Share Link |

### 6.2 디자인

- 배경: `#121212` 다크모드
- 카드: 글래스모피즘 (frosted glass)
- 강조색: 보라→핑크 그라데이션 (Cyber-Instagram)
- 폰트: Pretendard (CDN)
- 모바일: 단일 컬럼 (영상 → 대본 → 오디오)
- 데스크톱: 좌측 9:16 플레이어 / 우측 스크롤 패널
- 상태 뱃지: `AI Generated`, `Ready to Post`
- 모서리: 16px+ 라운드

### 6.3 nginx 라우팅

```
/showcase/{job_id}     → web:8000/showcase/{job_id}
/assets/jobs/{path}    → /var/www/assets/jobs/{path} (정적)
```

---

## 7. 에러 처리

| 실패 지점 | 처리 | 알림 |
|-----------|------|------|
| URL 형식 오류 | n8n Form 검증, 워커 미호출 | 없음 |
| 스크래핑 실패 | `status=failed`, `step=scraping` | 텔레그램 |
| 설명 영상 없음 | scraping 단계 실패 | 텔레그램 |
| STT/TTS/편집 실패 | 해당 step 기록 후 failed | 텔레그램 |
| 세션 만료 | scraping 실패, "세션 갱신 필요" | 텔레그램 |
| n8n 30분 타임아웃 | n8n 타임아웃 메시지 | 텔레그램 |
| 텔레그램 미설정 | n8n 실행 로그만 | n8n UI |

**재시도:** 사용자가 Form을 다시 제출. 워커 `retry_count` 로직 유지.

---

## 8. 환경변수

| 변수 | 서비스 | 설명 |
|------|--------|------|
| `OPENAI_API_KEY` | worker | Whisper + TTS |
| `ANTHROPIC_API_KEY` | worker | Claude 대본 |
| `TELEGRAM_BOT_TOKEN` | n8n, worker | 텔레그램 |
| `TELEGRAM_CHAT_ID` | n8n, worker | 수신 채팅 |
| `REDIS_URL` | web, worker | `redis://redis:6379/0` |
| `DATABASE_URL` | web, worker | `sqlite:///db/jobs.db` |
| `MAX_CONCURRENT_JOBS` | worker | 기본 `2` |
| `ALIEXPRESS_SESSION_PATH` | worker | Playwright 세션 |
| `SUBTITLE_FONT_PATH` | worker | Docker: NanumGothic 경로 |
| `SHOWCASE_BASE_URL` | worker, n8n | `http://localhost:8080` |
| `N8N_ENCRYPTION_KEY` | n8n | 크리덴셜 암호화 |
| `N8N_BASIC_AUTH_USER` | n8n | UI 보호 (선택) |
| `N8N_BASIC_AUTH_PASSWORD` | n8n | UI 보호 (선택) |

---

## 9. 접근 URL

| URL | 용도 |
|-----|------|
| `http://localhost:5678` | n8n UI + Form |
| `http://localhost:8080` | MP4·HTML 쇼케이스 |
| `http://localhost:8000` | FastAPI (디버깅) |

---

## 10. 테스트 계획

| # | 테스트 | 성공 기준 |
|---|--------|----------|
| 1 | `docker compose up -d` | 5 서비스 healthy |
| 2 | `POST /api/jobs` curl | `status=completed`, MP4 생성 |
| 3 | n8n Form URL 제출 | 폴링 → completed |
| 4 | 텔레그램 완료/실패 | 링크 수신 |
| 5 | `/showcase/{id}` | 9:16 플레이어·대본·오디오 |
| 6 | E2E 실제 AliExpress URL | 전체 파이프라인 완료 |

---

## 11. 구현 범위 외 (YAGNI)

- CSV 배치 처리 (n8n Form 단건만)
- n8n Webhook 트리거 (추후 확장)
- AI 신규 영상 생성 (Opal 원본 방식 폐기)
- Insta_Ali 프로젝트 직접 의존 (코드 복제만)
- 프로덕션 HTTPS·도메인 (로컬 개발 우선)
