# Insta_Ali Docker image
#
# AliExpress 숏폼 파이프라인용 공통 이미지.
# FastAPI web, RQ worker, CLI(main.py)가 동일 이미지를 사용한다.
# 포함: Python 3.11, ffmpeg, requirements.txt 의존성, Playwright Chromium.

FROM python:3.11-slim-bookworm

# ffmpeg — MoviePy 영상 편집·인코딩에 필요
# fonts-nanum — Docker 자막 렌더링용 한글 폰트 (SUBTITLE_FONT_PATH)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 패키지 설치 (web / worker / CLI 공통)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium 브라우저 및 OS 의존성 (--with-deps: libglib, fonts 등)
RUN playwright install --with-deps chromium

# 애플리케이션 소스 복사 (.dockerignore로 불필요 파일 제외)
COPY . .

# docker-compose web 서비스가 8000 포트를 노출
EXPOSE 8000

# compose에서 web/worker별 command로 override; 기본값은 web
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
