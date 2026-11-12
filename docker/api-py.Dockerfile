# Python API(esgapi)의 이미지. 원칙은 parser.Dockerfile 과 같다: 잠금 파일대로 설치, 루트가 아닌 사용자.
# api-py 와 migrate-py·worker-py 가 이 이미지 하나를 같이 쓴다(명령만 다르다).
# 세 단계: 웹 빌드(node) → 파이썬 의존성 + 웹 빌드 압축판 → 실행. 실행 단계에는 .venv 와 웹 빌드(dist)만 들어간다
# (node·node_modules 0). api-py 가 그 dist 를 같은 출처에서 정적 서빙한다(sid:MARC-ENT-198, WEB_DIST_DIR).
# 빌드:  docker build -f docker/api-py.Dockerfile .

# ── 0단계: 웹 빌드 ───────────────────────────────────────────────────
# node 판은 apps/web 의 engines(>=22.22.2)와 호스트(v22.23.1)에 맞춘다. 다이제스트는 인덱스의 것
# (docker buildx imagetools inspect node:22.23.1-bookworm-slim 의 맨 위 Digest, 확인 2026-10-16, 올림 2026-07-14).
FROM node:22.23.1-bookworm-slim@sha256:6c74791e557ce11fc957704f6d4fe134a7bc8d6f5ca4403205b2966bd488f6b3 AS web
# pnpm 은 corepack 이 루트 package.json 의 packageManager(pnpm@10.28.1)대로 받는다.
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /src
# 먼저 의존성 목록만: 소스만 고쳤을 때 설치 층은 다시 만들지 않는다.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/common/package.json packages/common/
COPY packages/tailwind-config/package.json packages/tailwind-config/
COPY packages/typescript-config/package.json packages/typescript-config/
COPY packages/ui/package.json packages/ui/
RUN pnpm install --frozen-lockfile --filter "@esg/web..."
COPY tsconfig.base.json ./
COPY packages packages
COPY apps/web apps/web
# VITE_DEMOS 없이: 데모 화면(/dev/*)은 싣지 않는다.
RUN pnpm --filter @esg/web build

# ── 1단계: 의존성과 esgapi 패키지 설치 ───────────────────────────────
FROM python:3.13.9-slim-bookworm@sha256:b685a4fa58bb19d1814d78a1ec0f0208f351452724f78b20212c984d6e124a34 AS build
# uv: 파이썬 패키지 설치 도구. 공식 이미지에서 실행 파일만 가져온다.
COPY --from=ghcr.io/astral-sh/uv:0.7.13@sha256:6c1e19020ec221986a210027040044a5df8de762eb36d5240e382bc41d7a9043 /uv /usr/local/bin/uv
WORKDIR /app
COPY apps/api-py/pyproject.toml apps/api-py/uv.lock ./
# 먼저 바깥 의존성만(--no-install-project). 코드만 고쳤을 때 이 층은 다시 만들지 않는다.
# --frozen: uv.lock 대로만. --no-dev: 테스트·린트 도구는 빼고. 결과는 /app/.venv 에 생긴다.
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/api-py/esgapi ./esgapi
# esgapi 자신을 .venv 안에 설치한다(--no-editable: 소스 폴더를 가리키는 링크가 아니라 복사본으로).
RUN uv sync --frozen --no-dev --no-editable
# 웹 빌드에 gzip 판(.gz)을 곁에 만든다. whitenoise 가 Accept-Encoding 을 보고 골라 준다. brotli 는 설치하지 않아 만들지 않는다.
COPY --from=web /src/apps/web/dist /app/web
RUN /app/.venv/bin/python -m whitenoise.compress --no-brotli /app/web

# ── 2단계: 실행 ──────────────────────────────────────────────────────
FROM python:3.13.9-slim-bookworm@sha256:b685a4fa58bb19d1814d78a1ec0f0208f351452724f78b20212c984d6e124a34
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# 웹 빌드(압축판까지 끝난 dist) 하나만. 기동 때 index.html 이 없으면 설정이 기동을 거부한다(config/web.py).
COPY --from=build /app/web /app/web
COPY apps/api-py/manage.py apps/api-py/gunicorn.conf.py ./
# PATH: .venv 안의 gunicorn 을 찾게. PYTHONUNBUFFERED: 기록이 버퍼에 머물지 않고 바로 나가게.
# WEB_DIST_DIR: api-py 가 정적 서빙할 웹 빌드의 자리(절대 경로).
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=esgapi.config.settings.base \
    WEB_DIST_DIR=/app/web
USER app
EXPOSE 8000
# gunicorn 은 SIGTERM 을 받으면 새 요청을 받지 않고, 받던 요청을 마친 뒤 내려간다(gunicorn.conf.py 의 graceful_timeout).
# 대괄호 꼴(exec)이라 gunicorn 이 PID 1 이 되어 신호를 바로 받는다.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "esgapi.config.wsgi:application"]
