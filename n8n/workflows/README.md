# n8n Reel Pipeline 워크플로

`reel-pipeline.json`은 Insta_Ali_Translate의 Form → API 폴링 → Telegram 알림 워크플로 export입니다.

설계 참고: [`docs/superpowers/specs/2026-06-24-n8n-reel-pipeline-design.md`](../../docs/superpowers/specs/2026-06-24-n8n-reel-pipeline-design.md) §3

---

## Import 방법

1. Docker Compose 기동 후 n8n UI 접속: [http://localhost:5678](http://localhost:5678)
2. 우측 상단 **⋯** → **Import from File**
3. `n8n/workflows/reel-pipeline.json` 선택
4. Import 후 아래 **수동 설정** 항목을 반드시 확인

> **참고:** JSON import 시 Telegram 크리덴셜 ID·Chat ID는 placeholder입니다. Import 후 노드 3곳(Telegram Success / Failure / Timeout)에서 크리덴셜과 Chat ID를 다시 연결해야 합니다.

---

## Import 후 수동 설정 (필수)

### 1. Telegram 크리덴셜

1. n8n → **Credentials** → **Add Credential** → **Telegram**
2. `.env`의 `TELEGRAM_BOT_TOKEN` 입력
3. 워크플로의 Telegram 노드 3개 모두에 해당 크리덴셜 연결

### 2. Telegram Chat ID

각 Telegram 노드의 **Chat ID** 필드를 `.env`의 `TELEGRAM_CHAT_ID` 값으로 변경합니다.

placeholder `REPLACE_WITH_TELEGRAM_CHAT_ID`를 실제 숫자 Chat ID로 교체하세요.

### 3. 워크플로 활성화

1. 에디터 우측 상단 **Inactive** → **Active** 토글
2. Form Trigger 노드에서 **Production URL** 복사 (예: `http://localhost:5678/form/xxxx`)

---

## 노드 구성 (수동 재구성 시)

Import가 실패하거나 노드가 깨진 경우, 아래 순서로 수동 구성하세요.

| # | 노드 | 설정 |
|---|------|------|
| 1 | **Form Trigger** | 필드 `product_url` (text, required) |
| 2 | **Set** (Normalize URL) | `product_url` = `{{ $json.product_url.trim() }}` |
| 3 | **HTTP Request** (Create Job) | POST `http://web:8000/api/jobs`, JSON body `{"url": "{{ $json.product_url }}"}` |
| 4 | **Set** (Set Job ID) | `job_id` = `{{ $json.id }}`, `product_url` = `{{ $('Normalize URL').item.json.product_url }}` |
| 5 | **Code** (Init Poll Slots) | 60개 폴링 슬롯 배열 생성 (아래 코드 참고) |
| 6 | **Split In Batches** (Poll Loop) | Batch Size = 1 |
| 7 | **Wait** | 30 seconds |
| 8 | **HTTP Request** (Get Job Status) | GET `http://web:8000/api/jobs/{{ $json.job_id }}` |
| 9 | **IF** (Completed) | `{{ $json.status }}` equals `completed` |
| 10 | **IF** (Failed) | `{{ $json.status }}` equals `failed` |
| 11 | **Telegram** (Success) | 완료 메시지 (아래 템플릿) |
| 12 | **Telegram** (Failure) | 실패 메시지 (아래 템플릿) |
| 13 | **Telegram** (Timeout) | Split In Batches **Done** 출력(2번째)에 연결 |

### 연결 흐름

```
Form Trigger → Normalize URL → Create Job → Set Job ID → Init Poll Slots → Poll Loop
Poll Loop [loop] → Wait 30s → Get Job Status → IF Completed
  ├─ true  → Telegram Success (종료)
  └─ false → IF Failed
       ├─ true  → Telegram Failure (종료)
       └─ false → Poll Loop (다음 배치)
Poll Loop [done] → Telegram Timeout
```

### Init Poll Slots 코드

```javascript
const job_id = $input.first().json.job_id;
const product_url = $input.first().json.product_url;

return Array.from({ length: 60 }, (_, i) => ({
  json: { job_id, product_url, poll_index: i + 1 },
}));
```

### Telegram 메시지 템플릿

**완료:**

```
[Insta_Ali_Translate] 릴스 생성 완료 ✅
URL: {{ $('Set Job ID').item.json.product_url }}
MP4: http://localhost:8080/assets/jobs/{{ $('Set Job ID').item.json.job_id }}/final_shorts.mp4
쇼케이스: http://localhost:8080/showcase/{{ $('Set Job ID').item.json.job_id }}
```

**실패:**

```
[Insta_Ali_Translate] 작업 실패 ❌
Job: {{ $('Set Job ID').item.json.job_id }}
URL: {{ $('Set Job ID').item.json.product_url }}
단계: {{ $json.current_step }}
에러: {{ $json.error_message }}
```

**타임아웃 (60회 ≈ 30분):**

```
[Insta_Ali_Translate] 작업 타임아웃 ⏱️
Job: {{ $('Set Job ID').item.json.job_id }}
URL: {{ $('Set Job ID').item.json.product_url }}
60회 폴링(약 30분) 후에도 완료되지 않았습니다.
```

---

## Docker 네트워크

n8n 컨테이너 내부에서 API 호출 URL은 **호스트가 아닌 Compose 서비스명**을 사용합니다.

| 호출 | URL |
|------|-----|
| 작업 생성 | `http://web:8000/api/jobs` |
| 상태 폴링 | `http://web:8000/api/jobs/{job_id}` |

텔레그램·브라우저 링크는 **호스트 기준** `http://localhost:8080` (`SHOWCASE_BASE_URL`)을 사용합니다.

---

## 알려진 Import 이슈

| 이슈 | 해결 |
|------|------|
| Telegram credential ID 불일치 | Credentials에서 새 Telegram 크리덴셜 생성 후 3개 노드에 재연결 |
| Form Trigger webhookId 충돌 | Import 후 Form Trigger 노드를 삭제·재생성하거나 Production URL 재확인 |
| Wait 노드 webhook | n8n 버전에 따라 Wait 노드 import 경고 — 노드 삭제 후 30s Wait 재추가 |
| Split In Batches 루프 미연결 | IF Failed **false** 출력 → Poll Loop 입력 재연결 |
