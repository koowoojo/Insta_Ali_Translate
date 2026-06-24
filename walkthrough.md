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

