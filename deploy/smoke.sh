#!/usr/bin/env bash
# 배포 주소의 겉 확인(밴드 DP1). 도는 자리: 운영 기계. 비밀 0(로그인하지 않는다). 끝 줄 SMOKE=<통과>/<전체>, 종료 0 = 전부.
#   사용: deploy/smoke.sh <SITE_DOMAIN> <FILES_DOMAIN>
# 환경 변수(로컬 리허설용 — 서버 확인은 전부 빈 값):
#   SMOKE_HTTP_PORT·SMOKE_HTTPS_PORT(기본 80·443) · SMOKE_RESOLVE_IP(주면 DNS 대신 그 IP — curl --resolve)
#   · SMOKE_CURL_OPTS(리허설만 -k) · SMOKE_ISSUER(발급자 기대 글자, 기본 Let's Encrypt)
set -uo pipefail

[ "$#" -eq 2 ] || { echo "사용: deploy/smoke.sh <SITE_DOMAIN> <FILES_DOMAIN>" >&2; exit 2; }
site="$1" files="$2"
hp="${SMOKE_HTTP_PORT:-80}" sp="${SMOKE_HTTPS_PORT:-443}"
issuer_want="${SMOKE_ISSUER:-}"
[ -n "$issuer_want" ] || issuer_want="Let's Encrypt"   # 기본값을 \${:-} 안에 두지 않는다(bash 3.2 가 그 안의 ' 를 따옴표로 읽는다)
suffix=""; [ "$sp" = 443 ] || suffix=":$sp"
hsuffix=""; [ "$hp" = 80 ] || hsuffix=":$hp"
origin="https://$site$suffix"
bucket_key="/esg-documents/smoke-probe"

c() {  # curl 공통: 시간 제한, 리허설의 --resolve·-k
  local args=(-sS --max-time 10)
  if [ -n "${SMOKE_RESOLVE_IP:-}" ]; then
    args+=(--resolve "$site:$sp:$SMOKE_RESOLVE_IP" --resolve "$files:$sp:$SMOKE_RESOLVE_IP" --resolve "$site:$hp:$SMOKE_RESOLVE_IP")
  fi
  # shellcheck disable=SC2086
  curl "${args[@]}" ${SMOKE_CURL_OPTS:-} "$@"
}

pass=0 total=0
check() {  # check <이름> <참이면 0 인 명령…>
  local name="$1"; shift
  total=$((total + 1))
  if "$@"; then pass=$((pass + 1)); echo "ok    $name"; else echo "FAIL  $name"; fi
}

body="$(mktemp)"; trap 'rm -f "$body"' EXIT
site_index() {
  local code
  code="$(c -o "$body" -w '%{http_code}' "https://$site$suffix/")"
  [ "$code" = 200 ] && grep -qi '<!doctype html' "$body"
}
readyz() {
  local code
  code="$(c -o /dev/null -w '%{http_code}' "https://$site$suffix/api/readyz")"
  [ "$code" = 200 ]
}
http_redirect() {
  local out; out="$(c -o /dev/null -w '%{http_code} %{redirect_url}' "http://$site$hsuffix/")"
  case "$out" in 30[1278]" https://$site"*) return 0 ;; *) echo "      받음: $out"; return 1 ;; esac
}
proxy_403() {  # proxy_403 <메서드> — proxy 가 막은 403 이어야(저장소의 403 은 XML <Error> 본문이 있다 — 저장소에 닿았다는 뜻)
  local code
  code="$(c -o "$body" -w '%{http_code}' -X "$1" "https://$files$suffix$bucket_key")"
  [ "$code" = 403 ] && ! grep -q '<Error' "$body"
}
files_get_403() { proxy_403 GET; }
files_unsigned_put_403() {  # 질의 서명 없는 PUT 은 proxy 가 막음
  local code
  code="$(c -o "$body" -w '%{http_code}' -X PUT --data-binary 'x' "https://$files$suffix$bucket_key")"
  [ "$code" = 403 ] && ! grep -q '<Error' "$body"
}
files_copy_403() {  # 복사 머리가 있으면(질의 서명 꼴이 있어도) proxy 가 막음
  local code
  code="$(c -o "$body" -w '%{http_code}' -X PUT -H "X-Amz-Copy-Source: /esg-documents/other" --data-binary 'x' \
    "https://$files$suffix$bucket_key?X-Amz-Signature=0000")"
  [ "$code" = 403 ] && ! grep -q '<Error' "$body"
}
files_delete_403() { proxy_403 DELETE; }
acao_for() {  # 미리 묻기(OPTIONS)의 Access-Control-Allow-Origin 값
  c -o /dev/null -D - -X OPTIONS -H "Origin: $1" -H "Access-Control-Request-Method: PUT" \
    "https://$files$suffix$bucket_key" | tr -d '\r' | sed -n 's/^[Aa]ccess-[Cc]ontrol-[Aa]llow-[Oo]rigin: //p'
}
cors_allowed() {
  local got
  got="$(acao_for "$origin")"
  [ "$got" = "$origin" ]
}
cors_other() {
  local got
  got="$(acao_for "https://example.invalid")"
  [ -z "$got" ]
}
other_host_cut() {  # 인증서는 SITE 로 맞추고 Host 만 다르게 — 앱에 닿지 않아야(응답 0)
  local code; code="$(c -o /dev/null -w '%{http_code}' -H "Host: other.invalid" "https://$site$suffix/" 2>/dev/null)"
  [ "$code" = 000 ]
}
http_other_cut() {  # http 로 다른 Host·IP 꼴 Host·FILES → 앱·저장소 본문 0(돌려보냄 308 이거나 끊김)
  local host code
  for host in other.invalid 203.0.113.10 "$files"; do
    code="$(c -o "$body" -w '%{http_code}' -H "Host: $host" "http://$site$hsuffix/esg-documents/x" 2>/dev/null)"
    case "$code" in 000|301|302|307|308) ;; *) echo "      Host $host → $code"; return 1 ;; esac
    if grep -q -i -e '<Error' -e '<!doctype' "$body" 2>/dev/null; then echo "      Host $host → 본문이 앱·저장소의 것"; return 1; fi
  done
}
issuer() {
  local line
  line="$(c -o /dev/null -v "https://$site$suffix/api/readyz" 2>&1 | sed -n 's/^\*  *issuer: //p' | head -n 1)"
  echo "      발급자: ${line:-없음}"
  case "$line" in *"$issuer_want"*) return 0 ;; *) return 1 ;; esac
}

check "https://SITE/ 200 · index.html" site_index
check "https://SITE/api/readyz 200" readyz
check "http://SITE/ → https" http_redirect
check "https://FILES/ GET 403(proxy 가 막음)" files_get_403
check "https://FILES/ DELETE 403(proxy 가 막음)" files_delete_403
check "https://FILES/ 서명 없는 PUT 403(proxy 가 막음)" files_unsigned_put_403
check "https://FILES/ X-Amz-Copy-Source PUT 403(proxy 가 막음)" files_copy_403
check "OPTIONS 허락 출처 → ACAO $origin" cors_allowed
check "OPTIONS 목록 밖 출처 → ACAO 없음" cors_other
check "다른 Host → 응답 0" other_host_cut
check "http 로 다른 Host·IP·FILES → 앱·저장소 본문 0" http_other_cut
check "인증서 발급자 ~ $issuer_want" issuer
echo "SMOKE=$pass/$total"
[ "$pass" = "$total" ]
