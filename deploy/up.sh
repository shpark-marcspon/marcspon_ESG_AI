#!/usr/bin/env bash
# 서버에서 시연 구성을 (다시) 띄운다(밴드 DP1). 도는 자리: 서버(deploy 사용자).   사용: /srv/esg-demo/current/deploy/up.sh [--no-build]
# 차례: 진행 중 실행 0 확인(check-idle-runs.sh — 0 이 아니면 멈춤) → 이미지 빌드 → 교체 전 로그 떠 두기(<ROOT>/logs/<UTC>/,
#   600, 서비스마다 끝 2만 줄·gzip, 최근 10개 — 떠 있는 컨테이너가 있을 때) → migrate --plan 에 적용할 것이 있으면 backup-db.sh 먼저(실패면 멈춤)
#   → compose up -d --wait → proxy 다시 만들기 → 상태 요약 → proxy 너머 https://<SITE_DOMAIN>/api/readyz 200
#   → docker image prune -f(볼륨 0). 되돌리기는 docs/deploy-demo.md 「되돌리기」.
# down·--volumes·볼륨 지우기를 부르지 않는다. 서버의 COMPOSE_PROJECT_NAME 은 esg-demo 가 아니면 멈춘다(바꾸면 새 빈 DB).
# 둘째 벌(데모 고정판, 밴드 DM1 — docs/deploy-demo.md 11절): 뿌리 /srv/esg-demo2 ↔ 프로젝트 esg-demo2 · PROXY_ROLE=none.
#   PROXY_ROLE(.env, 빈 값 = edge) — edge: proxy 를 띄운다(첫 벌). DEMO2_SITE_DOMAIN·DEMO2_FILES_DOMAIN 이 있으면
#     deploy/compose.edge-proxy.yaml 을 얹고 공유 네트워크 EDGE_NETWORK(기본 esg-edge)를 없으면 만든다. 둘 다 비면 BASE 그대로.
#   none: proxy 를 빼고 띄우고(다시 만들기도 건너뜀) deploy/compose.edge-relay.yaml 의 relay 를 얹는다. readyz 는 첫 벌 proxy
#     너머로 본다 — 공유 네트워크에 첫 벌 proxy 가 없으면 처음에 멈춘다.
# 환경 변수(로컬 리허설용): DEPLOY_ROOT · APP_DIR · ENV_FILE(check-idle-runs.sh 와 같음) · UP_CURL_OPTS(리허설만 -k).
#   --no-build 는 리허설용(이미지를 빌드 잠금 안에서 미리 지은 뒤).
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
# 기본 뿌리는 이 스크립트가 놓인 벌을 따른다(밴드 DM1): /srv/esg-demo2/… 아래면 둘째 벌, 그 밖은 첫 벌.
case "$here" in /srv/esg-demo2/*) default_root=/srv/esg-demo2 ;; *) default_root=/srv/esg-demo ;; esac
root="${DEPLOY_ROOT:-$default_root}"
app="${APP_DIR:-$root/current}"
env_file="${ENV_FILE:-$root/shared/.env}"
build=--build
case "${1:-}" in "") ;; --no-build) build= ;; *) echo "사용: deploy/up.sh [--no-build]" >&2; exit 2 ;; esac
# 한 벌의 코드로 다른 벌을 올리지 않는다(둘째 벌은 사용자가 정한 판에 고정 — docs/deploy-demo.md 11절)
case "$here:$root" in
  /srv/esg-demo/*:/srv/esg-demo2|/srv/esg-demo2/*:/srv/esg-demo)
    echo "멈춤: $here 의 up.sh 로 $root 를 올리지 않는다 — 그 벌의 current/deploy/up.sh 를 부른다" >&2; exit 1 ;;
esac

[ -r "$env_file" ] || { echo "env 파일을 읽을 수 없다: $env_file (처음이면 deploy/make-env.sh)" >&2; exit 1; }
value_of() { sed -n "s/^$1=//p" "$env_file" | tail -n 1; }   # 비밀이 아닌 이름에만 쓴다
project="$(value_of COMPOSE_PROJECT_NAME)"
site="$(value_of SITE_DOMAIN)"
https_port="$(value_of PROXY_HTTPS_PORT)"
role="$(value_of PROXY_ROLE)"; role="${role:-edge}"
demo2_site="$(value_of DEMO2_SITE_DOMAIN)"
demo2_files="$(value_of DEMO2_FILES_DOMAIN)"
edge_net="$(value_of EDGE_NETWORK)"; edge_net="${edge_net:-esg-edge}"
[ -n "$project" ] || { echo "COMPOSE_PROJECT_NAME 이 없다: $env_file" >&2; exit 1; }
if [ "$root" = /srv/esg-demo ] && [ "$project" != esg-demo ]; then
  echo "서버의 COMPOSE_PROJECT_NAME 은 esg-demo 여야 한다(지금: ${project:-없음}) — 바꾸면 새 빈 볼륨이 생긴다" >&2
  exit 1
fi
if [ "$root" = /srv/esg-demo2 ] && [ "$project" != esg-demo2 ]; then
  echo "둘째 벌의 COMPOSE_PROJECT_NAME 은 esg-demo2 여야 한다(지금: ${project:-없음}) — 다르면 다른 벌의 볼륨을 잡거나 새 빈 볼륨이 생긴다" >&2
  exit 1
fi
case "$role" in edge|none) ;; *) echo "PROXY_ROLE 은 edge·none(빈 값 = edge)뿐이다(지금: $role)" >&2; exit 1 ;; esac
if { [ "$root" = /srv/esg-demo ] && [ "$role" != edge ]; } || { [ "$root" = /srv/esg-demo2 ] && [ "$role" != none ]; }; then
  echo "PROXY_ROLE 이 뿌리와 맞지 않는다: $root 는 $([ "$root" = /srv/esg-demo ] && echo edge || echo none) 여야(지금: $role) — 443 은 첫 벌 하나" >&2
  exit 1
fi
case "$edge_net" in *[!A-Za-z0-9_.-]*) echo "EDGE_NETWORK 에 쓸 수 없는 글자: $edge_net" >&2; exit 1 ;; esac
extra=()
if [ "$role" = edge ]; then
  if [ -n "$demo2_site$demo2_files" ]; then
    [ -n "$demo2_site" ] && [ -n "$demo2_files" ] || { echo "DEMO2_SITE_DOMAIN·DEMO2_FILES_DOMAIN 은 둘 다 있거나 둘 다 비어야 한다" >&2; exit 1; }
    extra=(-f deploy/compose.edge-proxy.yaml)
    docker network inspect "$edge_net" >/dev/null 2>&1 || docker network create "$edge_net" >/dev/null \
      || { echo "공유 네트워크를 만들지 못했다: $edge_net" >&2; exit 1; }
  fi
else
  [ -z "$demo2_site$demo2_files" ] || { echo "DEMO2_* 는 첫 벌(PROXY_ROLE=edge) .env 의 칸이다 — 둘째 벌 .env 에서 뺀다" >&2; exit 1; }
  extra=(-f deploy/compose.edge-relay.yaml)
  # 첫 벌 proxy 가 공유 네트워크에 떠 있어야 이 벌의 이름이 밖에서 닿는다(readyz 도 그 너머로 본다)
  if [ -z "$(docker ps -q --filter "network=$edge_net" --filter label=com.docker.compose.service=proxy 2>/dev/null)" ]; then
    echo "첫 벌 proxy 가 없다: 공유 네트워크 $edge_net 에 떠 있는 proxy 0 — 첫 벌 .env 에 DEMO2_* 두 칸을 넣고 첫 벌 up.sh 먼저(docs/deploy-demo.md 11절)" >&2
    exit 1
  fi
fi

"$here/check-idle-runs.sh" || { echo "멈춤: 진행 중인 실행이 있거나 읽지 못했다 — docs/deploy-demo.md 「다시 올리기」·「멈춘 실행」" >&2; exit 1; }

cd "$app"
# -p 를 밝힌다: 셸에 내보낸 COMPOSE_PROJECT_NAME 이 --env-file 을 이겨 새 빈 볼륨으로 뜨지 않게(리뷰 M3)
compose=(docker compose -p "$project" --env-file "$env_file" -f compose.yaml -f deploy/compose.prod.yaml ${extra[@]+"${extra[@]}"})
started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# 새 코드의 이미지를 먼저 짓는다 — 마이그레이션 계획은 새 이미지(migrate-py = api-py 이미지)로 세야 한다
[ -z "$build" ] || "${compose[@]}" build

# 교체 전 로그: 바꾸면 컨테이너와 함께 로그가 사라진다(json-file 로그는 컨테이너에 묶임)
if [ -n "$("${compose[@]}" ps -a -q 2>/dev/null)" ]; then
  logdir="$root/logs/$(date -u +%Y%m%dT%H%M%SZ)"
  (
    umask 077
    mkdir -p "$logdir"
    "${compose[@]}" ps -a > "$logdir/ps.txt" 2>&1 || true
    # 서비스마다 끝 2만 줄 · gzip(크기 상한 — json-file 은 컨테이너당 100MB 까지 쌓인다)
    { "${compose[@]}" logs --no-color --timestamps --tail 20000 2>&1 || true; } | gzip -6 > "$logdir/compose.log.gz"
  )
  chmod 700 "$root/logs" "$logdir"; chmod 600 "$logdir"/*
  # 최근 10개만(이름이 UTC 시각이라 글자 차례 = 시간 차례)
  ls -1d "$root"/logs/*/ | sort -r | tail -n +11 | while read -r old; do rm -rf -- "$old"; done
  echo "교체 전 로그: $logdir ($(gzip -dc "$logdir/compose.log.gz" | wc -l | tr -d ' ')줄, gzip $(wc -c < "$logdir/compose.log.gz" | tr -d ' ') 바이트)"
fi

# 마이그레이션 전 백업: 볼륨이 있을 때(첫 배포는 백업할 DB 가 없다) 새 이미지로 계획을 세고, 적용할 것이 있으면 덤프부터
if docker volume inspect "${project}_postgres-data" >/dev/null 2>&1; then
  "${compose[@]}" up -d --wait postgres
  plan="$("${compose[@]}" run --rm --no-deps -T migrate-py python manage.py migrate --plan 2>&1)" \
    || { echo "migrate --plan 실패 — 올리지 않는다:" >&2; printf '%s\n' "$plan" | tail -n 5 >&2; exit 1; }
  pending="$(printf '%s\n' "$plan" | grep -cE '^[a-z_][a-z0-9_]*\.[0-9]{4}_' || true)"
  if [ "${pending:-0}" -gt 0 ]; then
    echo "적용할 마이그레이션 $pending개 — 먼저 덤프:"
    printf '%s\n' "$plan" | grep -E '^[a-z_][a-z0-9_]*\.[0-9]{4}_' | sed 's/^/  /'
    "$here/backup-db.sh" || { echo "멈춤: 마이그레이션 전 덤프 실패 — 올리지 않는다" >&2; exit 1; }
    # 덤프 뒤 곧바로 적용한다 — 이미지가 같으면 up 이 끝난 migrate-py 를 다시 돌린다는 보장이 없다(R11 에서 안 돎)
    "${compose[@]}" run --rm --no-deps -T migrate-py || { echo "멈춤: 마이그레이션 실패 — 덤프는 위 파일, 되돌리기는 docs/deploy-demo.md" >&2; exit 1; }
  else
    echo "적용할 마이그레이션 0"
  fi
fi

if [ "$role" = edge ]; then
  "${compose[@]}" up -d --wait
else
  # proxy 만 뺀 서비스 목록(80·443 을 잡지 않는다). 한 번짜리(migrate-py·storage-cors)는 목록에 남아 지금처럼 돈다.
  services="$("${compose[@]}" config --services | grep -vx proxy)"
  # shellcheck disable=SC2086
  "${compose[@]}" up -d --wait $services
fi
# proxy 는 늘 다시 만든다(첫 벌만 — 둘째 벌은 proxy 가 없다): Caddyfile 묶음의 원본이 current 심볼릭 경로라 설정 글자가 안 바뀌어 compose 가 그대로 두고,
#   도커는 묶을 때 심볼릭을 풀어 옛 release 의 파일을 계속 본다(리뷰 M1). 인증서는 볼륨(caddy-data)에 있어 다시 안 받는다.
[ "$role" != edge ] || "${compose[@]}" up -d --no-deps --force-recreate --wait proxy
"${compose[@]}" ps --format 'table {{.Service}}\t{{.Status}}'

port="${https_port##*:}"; port="${port:-443}"
code=000
for _ in $(seq 1 30); do
  # shellcheck disable=SC2086
  code="$(curl -sS -o /dev/null -w '%{http_code}' ${UP_CURL_OPTS:-} --max-time 5 --resolve "$site:$port:127.0.0.1" "https://$site:$port/api/readyz" 2>/dev/null || true)"
  [ "$code" = 200 ] && break
  sleep 4
done
echo "proxy 너머 /api/readyz: $code"
[ "$code" = 200 ] || { echo "readyz 가 200 이 아니다 — 인증서·DNS 는 docs/deploy-demo.md 「인증서」, 로그는 logs --since $started proxy" >&2; exit 1; }

docker image prune -f >/dev/null
echo "올림 끝: $(readlink -f "$app" 2>/dev/null || echo "$app") · 시작 $started"
