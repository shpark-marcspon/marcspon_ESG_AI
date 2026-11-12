#!/usr/bin/env bash
# 시연 DB 를 덤프한다(밴드 DP1). 도는 자리: 서버(cron 매일 03:30 KST — bootstrap-host.sh 가 단다, 손으로도).
#   사용: deploy/backup-db.sh      → <ROOT>/backup/db-<UTC>.dump (600, pg_dump -Fc, DB ${POSTGRES_DB}_py)
# 옛 덤프는 최근 7개만 남긴다(지우는 것은 backup/db-*.dump 뿐). 끝에 pg_restore --list 의 줄 수 > 0 을 본다.
# 올린 문서(storage-data 볼륨)와 덤프 파일은 EBS 스냅숏(DLM)이 같이 담는다 — 역할이 있을 때(docs/deploy-demo.md 「백업」).
# 환경 변수(로컬 리허설용): DEPLOY_ROOT · APP_DIR · ENV_FILE(check-idle-runs.sh 와 같음). 기본 뿌리는 스크립트가 놓인 벌(/srv/esg-demo2/… 면 둘째 벌).
set -euo pipefail
umask 077

# 기본 뿌리는 이 스크립트가 놓인 벌을 따른다(밴드 DM1): /srv/esg-demo2/… 아래면 둘째 벌, 그 밖은 첫 벌.
here="$(cd "$(dirname "$0")" && pwd)"
case "$here" in /srv/esg-demo2/*) default_root=/srv/esg-demo2 ;; *) default_root=/srv/esg-demo ;; esac
root="${DEPLOY_ROOT:-$default_root}"
app="${APP_DIR:-$root/current}"
env_file="${ENV_FILE:-$root/shared/.env}"
dir="$root/backup"
mkdir -p "$dir"
cd "$app"
project="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$env_file" | tail -n 1)"
[ -n "$project" ] || { echo "COMPOSE_PROJECT_NAME 이 없다: $env_file" >&2; exit 1; }
# -p 를 밝힌다(셸에 내보낸 COMPOSE_PROJECT_NAME 이 --env-file 을 이기지 않게 — 리뷰 M3)
compose=(docker compose -p "$project" --env-file "$env_file" -f compose.yaml -f deploy/compose.prod.yaml)

out="$dir/db-$(date -u +%Y%m%dT%H%M%SZ).dump"
tmp="$out.part"
trap 'rm -f "$tmp"' EXIT
"${compose[@]}" exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "${POSTGRES_DB}_py"' > "$tmp"
lines="$("${compose[@]}" exec -T postgres pg_restore --list < "$tmp" | grep -c -v '^;' || true)"
[ "${lines:-0}" -gt 0 ] || { echo "덤프가 비었거나 읽히지 않는다: $tmp" >&2; exit 1; }
mv "$tmp" "$out"
trap - EXIT
chmod 600 "$out"

ls -1t "$dir"/db-*.dump | tail -n +8 | while read -r old; do rm -f -- "$old"; done
echo "덤프: $out ($(wc -c < "$out" | tr -d ' ') 바이트, 목록 $lines 줄) · 남은 덤프 $(ls -1 "$dir"/db-*.dump | wc -l | tr -d ' ')개"
