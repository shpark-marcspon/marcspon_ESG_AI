#!/usr/bin/env bash
# 서버의 비밀 파일 <ROOT>/shared/.env 를 처음 한 번 만든다(밴드 DP1). 도는 자리: 서버(deploy 사용자).
#   사용: deploy/make-env.sh <SITE_DOMAIN> <FILES_DOMAIN> [ROOT]      ROOT 기본 /srv/esg-demo(로컬 리허설만 mktemp 폴더)
#   둘째 벌(데모 고정판, 밴드 DM1): ROOT=/srv/esg-demo2 면 둘째 벌 고정 칸(COMPOSE_PROJECT_NAME=esg-demo2 · PROXY_ROLE=none ·
#     POSTGRES_PORT=25432 · STORAGE_PORT=29000 · API_PY_PORT=28081)을 채운다. 리허설은 MAKE_ENV_SET=demo2 로 같은 칸을 고른다.
#     /srv/esg-demo 에 demo2, /srv/esg-demo2 에 first 는 거절한다. 비밀은 벌마다 새로 만든다(첫 벌 .env 와 나누지 않는다).
# 틀은 이 스크립트 곁의 env.prod.example. ★ 표시 비밀은 전부 openssl rand -hex 32(64 글자 16진 — DB 비밀번호가
#   postgres://u:PASS@ 주소에 인코딩 없이 들어가 base64 의 / + = 가 주소를 깬다). EDK 공개키는 새 RSA 키 쌍의 공개 쪽만
#   (개인키는 파이프 안에서만 있고 버린다), PEM 줄바꿈은 글자 \n.
# 이미 있으면 거절한다(종료 1) — 덮으면 DB 의 역할 비밀번호와 어긋나 시연 DB 에 못 닿는다. 찍는 것은 채운 이름뿐.
set -euo pipefail
umask 077

here="$(cd "$(dirname "$0")" && pwd)"
[ "$#" -ge 2 ] && [ "$#" -le 3 ] || { echo "사용: deploy/make-env.sh <SITE_DOMAIN> <FILES_DOMAIN> [ROOT]" >&2; exit 2; }
site="$1" files="$2" root="${3:-/srv/esg-demo}"
host_re='^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$'
for name in "$site" "$files"; do
  [[ "$name" =~ $host_re ]] || { echo "호스트 이름의 꼴이 틀렸다(소문자·숫자·- · . 만, 스킴·포트·경로 없이): $name" >&2; exit 2; }
done
[ "$site" != "$files" ] || { echo "SITE_DOMAIN 과 FILES_DOMAIN 은 달라야 한다" >&2; exit 2; }
set_name="${MAKE_ENV_SET:-}"
[ -n "$set_name" ] || { [ "$root" = /srv/esg-demo2 ] && set_name=demo2 || set_name=first; }
case "$set_name" in first|demo2) ;; *) echo "MAKE_ENV_SET 은 first·demo2 뿐이다: $set_name" >&2; exit 2 ;; esac
if { [ "$root" = /srv/esg-demo ] && [ "$set_name" != first ]; } || { [ "$root" = /srv/esg-demo2 ] && [ "$set_name" != demo2 ]; }; then
  echo "벌이 뿌리와 맞지 않는다: $root 에 $set_name" >&2; exit 2
fi

target="$root/shared/.env"
if [ -e "$target" ]; then
  echo "이미 있다 — 덮지 않는다: $target (비밀을 바꾸려면 docs/deploy-demo.md 「키 바꾸기」)" >&2
  exit 1
fi
[ -d "$root/shared" ] || { echo "폴더가 없다: $root/shared (서버는 deploy/bootstrap-host.sh 가 만든다)" >&2; exit 1; }
command -v openssl >/dev/null || { echo "openssl 이 없다" >&2; exit 1; }

secret() { openssl rand -hex 32; }
edk_public_key() {
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 2>/dev/null | openssl pkey -pubout | awk 'BEGIN { ORS = "\\n" } { print }'
}

tmp="$(mktemp "$root/shared/.env.new.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

# 값은 awk 의 환경으로만 넘긴다(명령줄 인자·ps 에 0).
V_POSTGRES_OWNER_PASSWORD="$(secret)" \
V_APP_DB_PASSWORD="$(secret)" \
V_STORAGE_ACCESS_KEY="$(secret)" \
V_STORAGE_SECRET_KEY="$(secret)" \
V_SESSION_SECRET="$(secret)" \
V_EDK_JWT_PUBLIC_KEY="$(edk_public_key)" \
V_SITE_DOMAIN="$site" \
V_FILES_DOMAIN="$files" \
V_STORAGE_CORS_ORIGINS="https://$site" \
V_SET="$set_name" \
awk '
  BEGIN {
    n = split("POSTGRES_OWNER_PASSWORD APP_DB_PASSWORD STORAGE_ACCESS_KEY STORAGE_SECRET_KEY SESSION_SECRET EDK_JWT_PUBLIC_KEY SITE_DOMAIN FILES_DOMAIN STORAGE_CORS_ORIGINS", names, " ")
    for (i = 1; i <= n; i++) fill[names[i]] = ENVIRON["V_" names[i]]
    # 둘째 벌 고정 칸: 틀의 값을 덮는다(COMPOSE_PROJECT_NAME 은 틀에 esg-demo 가 적혀 있다)
    if (ENVIRON["V_SET"] == "demo2") {
      m = split("COMPOSE_PROJECT_NAME=esg-demo2 PROXY_ROLE=none POSTGRES_PORT=25432 STORAGE_PORT=29000 API_PY_PORT=28081", pairs, " ")
      for (i = 1; i <= m; i++) { e = index(pairs[i], "="); force[substr(pairs[i], 1, e - 1)] = substr(pairs[i], e + 1) }
    }
  }
  {
    eq = index($0, "=")
    if ($0 !~ /^#/ && eq > 0) {
      key = substr($0, 1, eq - 1)
      if (key in force) { print key "=" force[key]; forced[key] = 1; next }
      if ((key in fill) && substr($0, eq + 1) == "") {
        if (fill[key] == "") { print "빈 값: " key > "/dev/stderr"; exit 1 }
        print key "=" fill[key]; done[key] = 1; next
      }
    }
    print
  }
  END {
    for (i = 1; i <= n; i++) if (!(names[i] in done)) { print "틀에 빈 줄이 없다: " names[i] > "/dev/stderr"; exit 1 }
    for (k in force) if (!(k in forced)) { print "틀에 줄이 없다: " k > "/dev/stderr"; exit 1 }
  }
' "$here/env.prod.example" > "$tmp"

# 그 사이에 누가 만들었으면 덮지 않는다(ln 은 대상이 있으면 실패한다).
ln "$tmp" "$target" || { echo "이미 있다 — 덮지 않는다: $target" >&2; exit 1; }
chmod 600 "$target"
echo "만듦: $target (600) · 벌 $set_name"
echo "채운 이름: POSTGRES_OWNER_PASSWORD APP_DB_PASSWORD STORAGE_ACCESS_KEY STORAGE_SECRET_KEY SESSION_SECRET EDK_JWT_PUBLIC_KEY(공개키 — 개인키 버림) SITE_DOMAIN FILES_DOMAIN STORAGE_CORS_ORIGINS"
echo "남은 것: LLM_OPENAI_API_KEY 는 운영 기계에서 deploy/put-llm-key.sh"
