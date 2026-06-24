"""
Opal Assemble Final Reel 벤치마킹 HTML 쇼케이스 생성기.

작업 디렉터리의 final_shorts.mp4, dubbing.mp3, script.txt를
다크모드 9:16 플레이어 + 대본 + 오디오 UI로 묶은 showcase.html을 생성한다.

주요 기능:
- #121212 다크모드 + Pretendard CDN + 글래스모피즘 카드
- 9:16 비디오 플레이어, 대본 카드, 나레이션 오디오 플레이어
- AI Generated / Ready to Post 상태 뱃지
- Download Video / Copy Script / Share Link 툴바
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
    # script.txt가 없으면 빈 문자열로 대본 섹션만 렌더링
    script_path = job_dir / "script.txt"
    script = script_path.read_text(encoding="utf-8") if script_path.exists() else ""

    # nginx 정적 경로 기준 미디어·다운로드 URL
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
    """HTML 특수문자 이스케이프 — 대본 XSS·깨짐 방지."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
