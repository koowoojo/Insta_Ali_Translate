# Insta_Ali_Translate 프로젝트 Walkthrough

> 모든 대화·작업 내용을 시계열로 누적 기록합니다.

---

## 2026-06-24 — n8n Docker 자동화 브레인스토밍 시작

### 사용자 요청
- Docker에 n8n을 세팅해서 자동화 프로세스를 만들고 싶음
- brainstorming 스킬 적용 (구현 전 설계 승인 필수)

### 프로젝트 컨텍스트 탐색 결과
- **현재 워크스페이스 `E:\Vibe\Insta_Ali_Translate`:** 빈 폴더 (코드·git 없음)
- **관련 프로젝트 `E:\Vibe\Insta_Ali`:**
  - AliExpress 상품 URL → 스크래핑 → AI 대본 번역/윤문 → TTS + 자막 → 9:16 숏폼 영상 파이프라인
  - Docker Compose: `redis` + `web`(FastAPI:8000) + `worker`(RQ)
  - 알림: 웹 대시보드 + 텔레그램
  - 설계 문서: `docs/superpowers/specs/2026-06-22-insta-ali-pipeline-design.md`
- **관련 프로젝트 `E:\Vibe\Insta_cupa`:** `.agent/skills/` 등 에이전트 스킬 보유, Docker 설정 없음

### Q2 (수정): 자동화 파이프라인 — Opal 벤치마킹 + 사용자 수정
- **사용자 수정 (2026-06-24):** AI 신규 영상 생성 방식 **폐기**
- **확정된 플로우:**
  1. **Product URL 입력**
  2. **상품 콘텐츠 수집** — 텍스트(기능·마케팅 포인트) **+** 페이지에 업로드된 **상품 설명 영상 다운로드**
  3. **릴 플랜 생성** — 다운로드한 영상 **길이에 맞춘** 한국어 인스타 릴스 대본·구성
  4. **영상에 입히기** — 릴 플랜을 다운로드한 원본 영상에 적용 (더빙·자막·편집 등)
- **Insta_Ali와의 유사점:** 기존 상품 영상 활용 + AI 대본·후처리
- **차이점:** n8n이 핵심 오케스트레이터, Insta_Ali Python/RQ 파이프라인 대신 n8n 워크플로 중심

### Q8: 배포 환경
- **사용자 선택:** A — **Docker Compose 올인원**
  - n8n + Redis + 복제 워커 + (선택) nginx를 한 `docker-compose.yml`로 로컬 실행

### 확정 요구사항 요약
| 항목 | 선택 |
|------|------|
| 목적 | Insta_Ali_Translate, n8n 핵심 오케스트레이터 |
| 입력 | AliExpress Product URL (n8n Form Trigger) |
| 처리 | 텍스트 수집 + 설명 영상 다운로드 → 영상 길이 맞춘 릴 플랜 → 나레이션+자막+9:16 |
| 워커 | Insta_Ali 코드 복제, 독립 배포 |
| 산출물 | MP4 + Opal 스타일 HTML 쇼케이스 |
| 알림 | 텔레그램 (완료/실패 + 링크) |
| 배포 | Docker Compose 올인원 (로컬) |

### 아키텍처 접근법
- **사용자 선택:** 접근법 1 — **n8n 폴링형**
- **섹션 1(아키텍처 & Docker Compose):** 접근법 1 기준으로 확정

### 설계 문서
- 경로: `docs/superpowers/specs/2026-06-24-n8n-reel-pipeline-design.md`
- 섹션 1~3 사용자 전체 승인 완료
- 스펙 자체 리뷰 완료
- git 커밋 완료

### 구현 계획 작성
- 경로: `docs/superpowers/plans/2026-06-24-n8n-reel-pipeline.md`
- Phase 1~6, Task 1~11 (복제 → showcase → API → Docker → n8n → E2E)
- writing-plans 스킬 적용 완료

### 진행 상태
- 구현 실행 방식 선택 대기 (Subagent-Driven vs Inline)

---

## 2026-06-24 — Task 1: Insta_Ali 워커 코드 복제 (Insta_Ali_Translate)

### 사용자 요청
- 소스 `E:\Vibe\Insta_Ali` 워커 코드베이스를 `E:\Vibe\Insta_Ali_Translate`에 독립 베이스로 복제
- 제외: `.venv`, `.git`, `__pycache__`, `.pytest_cache`, `logs`, `.env`, `assets/jobs/*` 런타임 출력, `db/jobs.db`
- 기존 `docs/`, `walkthrough.md`(Translate 버전) 유지 — 복제 후 walkthrough는 HEAD에서 복구 후 본 항목 추가

### 수행 작업
1. PowerShell `Get-ChildItem` + `Copy-Item`으로 소스 루트 항목만 대상에 복사
2. `assets/jobs`, `assets/sessions`, `db` 디렉터리 생성; `assets/jobs` 내용 비움; `db/jobs.db`·`.env` 삭제
3. 검증: `worker/pipeline.py`, `modules/scraper.py`, `web/app.py` → 모두 `True`
4. `.gitignore`에 `.env` 포함 확인

### 복제된 주요 항목
- `worker/`, `modules/`, `utils/`, `web/`, `tests/`
- `main.py`, `requirements.txt`, `pytest.ini`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `README.md`
- `docs/superpowers` 내 Insta_Ali 쪽 2026-06-22 설계·계획 문서 추가(기존 2026-06-24 n8n 문서 유지)

### Git
- 커밋 메시지: `chore: copy Insta_Ali worker codebase as independent base`

---

## 2026-06-24 — Task 2: 프로젝트 설정·브랜딩 변경

### 사용자 요청
- `utils/config.py`에 `showcase_base_url` 설정 추가 (nginx 경유 쇼케이스·외부 URL)
- `.env.example`에 `SHOWCASE_BASE_URL`, n8n 관련 환경변수, Docker/Linux 자막 폰트 주석 추가
- `web/app.py` FastAPI title/description을 Insta Ali Translate API로 리브랜딩
- 커밋 후 walkthrough 갱신

### 수행 작업
1. **utils/config.py** — Telegram 필드 아래에 `showcase_base_url: str = "http://localhost:8080"` 추가
2. **.env.example** — 하단에 `SHOWCASE_BASE_URL`, `N8N_ENCRYPTION_KEY`, `N8N_BASIC_AUTH_USER`, `N8N_BASIC_AUTH_PASSWORD`, Docker/Linux `SUBTITLE_FONT_PATH` 주석 추가
3. **web/app.py** — FastAPI `title="Insta Ali Translate API"`, `description="n8n 연동 AliExpress 릴스 파이프라인 API"`로 변경

### Git
- 커밋 SHA: `f22de09`
- 커밋 메시지: `feat: add showcase_base_url and rebrand API for Insta_Ali_Translate`
- 변경 파일: `utils/config.py`, `.env.example`, `web/app.py` (3 files, +11 / -2)

---

## 2026-06-24 — Task 3: showcase_generator 모듈

### 사용자 요청
- `utils/showcase_generator.py` 및 `tests/test_showcase_generator.py` 구현 (구현 계획 Task 3)
- Opal 스타일 HTML 쇼케이스: 다크모드 #121212, Pretendard CDN, 글래스모피즘, 9:16 플레이어, 대본·오디오, 툴바·뱃지
- pytest 통과 후 커밋

### 수행 작업
1. **utils/showcase_generator.py** — `generate_showcase(job_id, job_dir, product_url, base_url) -> Path` 구현
   - `script.txt` 읽기, `final_shorts.mp4`·`dubbing.mp3` nginx URL 조립
   - `_escape_html`로 대본 HTML 이스케이프
   - `showcase.html`을 job_dir에 생성
2. **tests/test_showcase_generator.py** — `test_generate_showcase_creates_html(tmp_path)` 추가
   - 대본 텍스트, 미디어 경로, 뱃지, `#121212` 포함 여부 검증

### 테스트 결과
```
python -m pytest tests/test_showcase_generator.py -v
tests/test_showcase_generator.py::test_generate_showcase_creates_html PASSED [100%]
1 passed in 0.06s
```

### Git
- 커밋 SHA: `445810d`
- 커밋 메시지: `feat: add Opal-style HTML showcase generator`
- 변경 파일: `utils/showcase_generator.py`, `tests/test_showcase_generator.py`

---

## 2026-06-24 — Task 4: 파이프라인 6단계 showcase 추가

### 사용자 요청
- `worker/pipeline.py`에 showcase 생성 단계(6단계) 추가
- `compose_shorts` 이후 `generate_showcase` 호출, 반환 dict에 `showcase_path` 포함
- 커밋: `feat: add showcase generation as pipeline step 6`

### 수행 작업
1. **worker/pipeline.py**
   - `utils.showcase_generator.generate_showcase` import
   - 모듈·함수 docstring을 6단계 파이프라인으로 갱신
   - `compose_shorts` 직후 showcase 단계 로그 및 `generate_showcase(job_id, job_dir=base, product_url=url, base_url=settings.showcase_base_url)` 호출
   - 반환값에 `"showcase_path": str(showcase_path)` 추가

### Git
- 커밋 SHA: `6e919fc`
- 커밋 메시지: `feat: add showcase generation as pipeline step 6`
- 변경 파일: `worker/pipeline.py` (1 file, +20 / -5)

---

## 2026-06-24 — Task 5: DB·워커 tasks·notifier 확장

### 사용자 요청
- `db/models.py` Job 모델에 `showcase_path` 필드 추가
- `worker/tasks.py`: STEPS에 `"showcase"` 추가, `_update`에 showcase 파라미터, 성공 시 showcase_path 저장 및 텔레그램 성공 알림
- `utils/notifier.py`: `format_success_message`, `send_telegram_success` 추가, 실패 메시지 prefix를 `[Insta_Ali_Translate]`로 변경
- `python -m pytest tests/test_config.py tests/test_notifier.py -v` 실행
- 커밋: `feat: persist showcase_path and add telegram success notification`

### 수행 작업
1. **db/models.py** — `showcase_path: Mapped[Optional[str]]` (Text, nullable) 추가
2. **worker/tasks.py**
   - `STEPS` 끝에 `"showcase"` 추가
   - `_update(..., showcase: str | None = None)` 및 `job.showcase_path` 갱신
   - 성공 `_update` step을 `"showcase"`로, `showcase=result.get("showcase_path")` 전달
   - `get_settings`, `send_telegram_success` import
   - 성공 후 MP4·쇼케이스 URL 조립하여 `send_telegram_success` 호출
3. **utils/notifier.py**
   - `format_success_message` — `[Insta_Ali_Translate] 릴스 생성 완료 ✅` + URL/MP4/쇼케이스 링크
   - `send_telegram_success` — Telegram Bot API 전송 (자격 증명 미설정 시 스킵)
   - `format_failure_message` prefix → `[Insta_Ali_Translate] 작업 실패`

### 테스트 결과
```
python -m pytest tests/test_config.py tests/test_notifier.py -v
tests/test_config.py::test_settings_defaults PASSED
tests/test_notifier.py::test_format_failure_message PASSED
2 passed in 0.30s
```

### Git
- 커밋 SHA: `0f3d7ec`
- 커밋 메시지: `feat: persist showcase_path and add telegram success notification`
- 변경 파일: `db/models.py`, `worker/tasks.py`, `utils/notifier.py` (3 files, +90 / -7)

---

## 2026-06-24 — Task 6: Showcase 라우트 및 Jobs API 확장

### 사용자 요청 (ultrawork)
- `web/routes/showcase.py` 생성 — `GET /showcase/{job_id}` → `showcase.html` FileResponse
- `web/routes/jobs.py` — `JobSummaryResponse`·`JobDetailResponse`에 `showcase_url: Optional[str]` 추가
- `_job_summary`·`_job_detail`에서 `showcase_path` 존재 또는 `status == "completed"`일 때 `showcase_url=f"/showcase/{job.id}"` 설정
- `web/app.py` — showcase 라우터 등록
- `tests/test_showcase_route.py` — 존재하지 않는 job_id 404 테스트
- 커밋: `feat: add showcase route and showcase_url in jobs API`

### 수행 작업
1. **web/routes/showcase.py** (신규)
   - Job 조회 후 `showcase_path` 우선, 없으면 `assets/jobs/{id}/showcase.html` fallback
   - 파일 미존재 시 404 `"Showcase not ready"`
2. **web/routes/jobs.py**
   - `_showcase_url(job)` 헬퍼 추가
   - `JobSummaryResponse.showcase_url` 필드 및 `_job_summary`·`_job_detail` 반영
3. **web/app.py**
   - `showcase.router` import 및 pages 라우터 앞에 등록
4. **tests/test_showcase_route.py** (신규)
   - worker.pipeline/tasks 스텁 + StaticPool 인메모리 DB fixture
   - `test_showcase_404_when_missing` — `GET /showcase/nonexistent-id` → 404

### 테스트 결과
```
python -m pytest tests/test_showcase_route.py -v
tests/test_showcase_route.py::test_showcase_404_when_missing PASSED [100%]
1 passed in 0.47s
```

### Git
- 커밋 SHA: `092589e`
- 커밋 메시지: `feat: add showcase route and showcase_url in jobs API`
- 변경 파일: `web/routes/showcase.py`, `web/routes/jobs.py`, `web/app.py`, `tests/test_showcase_route.py`, `walkthrough.md`

---

## 2026-06-24 — Task 7: Dockerfile Nanum 폰트 추가

### 사용자 요청
- Docker 이미지에 `fonts-nanum` 패키지 추가 (자막 렌더링용)
- `ffmpeg`와 동일한 `apt-get install` 라인에 포함

### 수행 작업
1. **Dockerfile** — `apt-get install`에 `fonts-nanum` 추가
   - `SUBTITLE_FONT_PATH: /usr/share/fonts/truetype/nanum/NanumGothicBold.ttf`와 연동

### Git
- 커밋 SHA: `5241a6e`
- 커밋 메시지: `chore: add Nanum font for Docker subtitle rendering`

---

## 2026-06-24 — Task 8: docker-compose 5서비스 스택

### 사용자 요청
- 기존 3서비스(redis + web + worker) compose를 n8n + redis + web + worker + nginx 5서비스 스택으로 교체
- web/worker에 `SUBTITLE_FONT_PATH`, `SHOWCASE_BASE_URL` 환경변수 추가
- n8n 서비스: 포트 5678, Asia/Seoul, workflows import 볼륨
- nginx 서비스: 포트 8080→80

### 수행 작업
1. **docker-compose.yml** 전면 교체
   - `redis`: redis:7-alpine (호스트 포트 노출 제거)
   - `web`: FastAPI 8000, Redis·폰트·쇼케이스 URL env
   - `worker`: RQ worker, 동일 env
   - `n8n`: n8nio/n8n:latest, `./n8n_data`·`./n8n/workflows:/import:ro`
   - `nginx`: nginx:alpine, `./nginx/nginx.conf`·`./assets` 마운트

### Git
- 커밋 SHA: `7917e7e`
- 커밋 메시지: `feat: add docker-compose with n8n, worker, and nginx`

---

## 2026-06-24 — Task 9: nginx 설정 및 n8n workflows 디렉터리

### 사용자 요청
- `nginx/nginx.conf` — `/assets/` 정적 서빙(CORS), `/showcase/` web 프록시
- `n8n/workflows/` 디렉터리 생성 (`.gitkeep`)

### 수행 작업
1. **nginx/nginx.conf** (신규)
   - `location /assets/` — alias `/var/www/assets/`, CORS `*`
   - `location /showcase/` — `proxy_pass http://web:8000/showcase/`
2. **n8n/workflows/.gitkeep** (신규) — n8n 워크플로 import 마운트용 빈 디렉터리

### 검증
- `docker-compose.yml` YAML 구문 검증 통과 (Python yaml.safe_load)

### Git
- 커밋 SHA: `git log -1 --oneline` (nginx + walkthrough 커밋)
- 커밋 메시지: `feat: add nginx config for assets and showcase proxy`

---

## 2026-06-24 — Task 10: n8n reel-pipeline 워크플로 export

### 사용자 요청 (부모 에이전트 Task 10)
- `n8n/workflows/reel-pipeline.json` — n8n v1 호환 importable 워크플로 JSON
- Form Trigger → URL 정규화 → POST /api/jobs → job_id 저장 → 60회 SplitInBatches 폴링(Wait 30s + GET) → completed/failed/timeout Telegram

### 수행 작업
1. **n8n/workflows/reel-pipeline.json** (신규)
   - 노드 13개: Form Trigger, Normalize URL (Set), Create Job (HTTP POST), Set Job ID, Init Poll Slots (Code), Poll Loop (SplitInBatches), Wait 30s, Get Job Status, IF Completed, IF Failed, Telegram Success/Failure/Timeout
   - Docker 내부 API URL: `http://web:8000/api/jobs`
   - 텔레그램 링크: `http://localhost:8080` (SHOWCASE_BASE_URL 호스트 기준)
   - Telegram credential·Chat ID는 placeholder (import 후 수동 연결 필요)
2. **n8n/workflows/README.md** (신규)
   - Import 절차, 수동 노드 재구성 표, 연결 다이어그램, 메시지 템플릿, 알려진 import 이슈

### Import 시 수동 조정 필요
- Telegram 크리덴셜 3노드 재연결
- Chat ID placeholder → `.env` 값으로 교체
- Wait/SplitInBatches 노드가 n8n 버전에 따라 import 경고 가능

### Git
- 커밋 SHA: `c941cd5`
- 커밋 메시지: `feat: add n8n reel pipeline workflow export`

---

## 2026-06-24 — Task 11: README 및 E2E 검증 문서

### 사용자 요청 (부모 에이전트 Task 11)
- README.md: n8n + Opal-style 파이프라인 설명, Docker/API 키/.env, compose 기동, 포트, Form URL, AliExpress 세션, Telegram, 쇼케이스 URL, 설계·계획 문서 링크
- E2E 검증 단계 (API curl, 쇼케이스, n8n Form)

### 수행 작업
1. **README.md** 전면 갱신
   - Insta_Ali_Translate 브랜딩·아키텍처 요약
   - Docker Compose 빠른 시작, `.env` 필수 변수 표
   - 포트 5678/8080/8000, n8n Form·Telegram 설정, 쇼케이스 URL 패턴
   - E2E 검증 4단계 (API, 브라우저, Form, 로그)
   - 설계 스펙·구현 계획·n8n README 링크

### Git
- 커밋 SHA: `d90a13d`
- 커밋 메시지: `docs: add setup guide and E2E verification steps`

---

## 2026-06-24 — Subagent-Driven 구현 전체 완료

### 사용자 선택
- 구현 실행 방식: **1) Subagent-Driven**

### 완료 Task (1~11)
| Task | 내용 | 커밋 |
|------|------|------|
| 1 | Insta_Ali 코드 복제 | `4b7ca20` |
| 2 | showcase_base_url·브랜딩 | `f22de09` |
| 3 | showcase_generator + 테스트 | `445810d` |
| 4 | pipeline 6단계 | `6e919fc` |
| 5 | DB·notifier 확장 | `0f3d7ec` |
| 6 | showcase 라우트·API | `1a3a282` |
| 7 | Dockerfile Nanum 폰트 | `5241a6e` |
| 8 | docker-compose 5서비스 | `7917e7e` |
| 9 | nginx 설정 | `6a1f5a8` |
| 10 | n8n workflow JSON | `c941cd5` |
| 11 | README·E2E 문서 | `f4d7268` |

### 검증
- `pytest` 핵심 4건 PASS (showcase_generator, showcase_route, config, notifier)

### 다음 단계 (사용자 로컬)
1. `.env.example` → `.env` 복사 후 API 키·Telegram·N8N_ENCRYPTION_KEY 설정
2. `docker compose up -d --build`
3. n8n (`:5678`)에서 `n8n/workflows/reel-pipeline.json` Import + Telegram 크리덴셜 연결
4. `python main.py --login` (AliExpress 세션)
5. n8n Form에 AliExpress URL 제출 → 텔레그램·쇼케이스 확인

---

## 2026-06-24 — .env API 키·설정 이전

### 사용자 요청
- Insta_Ali 및 다른 프로젝트에서 필요한 API 키·설정을 Insta_Ali_Translate `.env`로 가져오기

### 수행 작업
- `E:\Vibe\Insta_Ali_Translate\.env` 생성 (`.gitignore` 대상, 커밋 안 함)

| 변수 | 출처 |
|------|------|
| `OPENAI_API_KEY` | Insta_Ali `.env` |
| `ANTHROPIC_API_KEY` | Insta_Ali `.env` |
| `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE` | Insta_Ali `.env` |
| `PROXY_URL` | Insta_Ali `.env` |
| `TELEGRAM_BOT_TOKEN` | trader/trader `.env` |
| `TELEGRAM_CHAT_ID` | trader/trader `.env` (coin_bot 등과 동일 ID) |
| `N8N_ENCRYPTION_KEY` | 신규 랜덤 40자 생성 |
| 기타 인프라·자막·SHOWCASE_BASE_URL | `.env.example` 기본값 |

### 미이전·주의
- **AliExpress 세션** (`assets/sessions/aliexpress_state.json`): Vibe 내 프로젝트에 파일 없음 → `python main.py --login` 필요
- Insta_Ali `.env`의 TELEGRAM은 비어 있었음 → trader 프로젝트 값 사용
- Insta_cupa의 GOOGLE_API_KEY·쿠팡 키는 본 파이프라인에 불필요하여 제외

---

## 2026-06-24 — 로컬 환경 기동 자동 실행

### 수행 작업
1. Docker Desktop 기동
2. Python `.venv` 생성 + `pip install -r requirements.txt` + Playwright Chromium
3. `docker compose up --build -d` 실행 (이미지 빌드·5서비스 기동 완료)
4. `.env` UTF-8 BOM 제거 (web 컨테이너 `openai_api_key` 파싱 오류 수정)
5. `docker compose restart web worker` → 5서비스 모두 `Up`

### 현재 서비스 상태
| 서비스 | 포트 | 상태 |
|--------|------|------|
| n8n | 5678 | Up |
| nginx | 8080 | Up |
| redis | 6379 | Up |
| web (FastAPI) | 8000 | Up |
| worker (RQ) | — | Up |

### 사용자 수동 필요 (미완료)
- **AliExpress 로그인 세션**: `python main.py --login` (브라우저에서 직접 로그인 후 Enter)
- **n8n 워크플로 Import**: http://localhost:5678 → `n8n/workflows/reel-pipeline.json` Import + Telegram 크리덴셜 연결

