# Python 파서의 이미지. 원칙은 server.Dockerfile 과 같다: 두 단계, 잠금 파일대로 설치, 루트가 아닌 사용자.
# 빌드:  docker build -f docker/parser.Dockerfile .

# ── 1단계: 의존성 설치 ───────────────────────────────────────────────
FROM python:3.13.9-slim-bookworm@sha256:b685a4fa58bb19d1814d78a1ec0f0208f351452724f78b20212c984d6e124a34 AS build
# uv: 파이썬 패키지 설치 도구. 공식 이미지에서 실행 파일만 가져온다.
COPY --from=ghcr.io/astral-sh/uv:0.7.13@sha256:6c1e19020ec221986a210027040044a5df8de762eb36d5240e382bc41d7a9043 /uv /usr/local/bin/uv
WORKDIR /app
COPY services/parser/pyproject.toml services/parser/uv.lock ./
# --frozen: uv.lock 대로만. --no-dev: 테스트 도구(pytest)는 빼고. 결과는 /app/.venv 에 생긴다.
RUN uv sync --frozen --no-dev

# ── 2단계: 실행 ──────────────────────────────────────────────────────
FROM python:3.13.9-slim-bookworm@sha256:b685a4fa58bb19d1814d78a1ec0f0208f351452724f78b20212c984d6e124a34
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY services/parser/app.py ./
# 분해기(docparse/)와 산출의 스키마(schemas/). 테스트(services/parser/tests/, test_app.py)와 scripts/ 는 싣지 않는다.
COPY services/parser/docparse ./docparse
COPY services/parser/schemas ./schemas
# PATH: .venv 안의 uvicorn 을 찾게. PYTHONUNBUFFERED: 기록이 버퍼에 머물지 않고 바로 나가게.
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
# uvicorn 은 SIGTERM 을 받으면 받던 요청을 마치고 내려간다.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
