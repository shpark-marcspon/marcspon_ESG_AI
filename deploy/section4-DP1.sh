#!/usr/bin/env bash
# 밴드 DP1(시연 배포)의 §4 자기검증(발주서 band-handoffs/DP1-order.md §3·§4). 도는 자리: 운영 기계(워크트리).
#   사용: deploy/section4-DP1.sh [static|rehearsal|planted]      기본 static
#     static     S1~S8 + 빠른 게이트(scripts/verify.sh --fast). 컨테이너는 caddy 한 번짜리(validate·fmt)뿐.
#     rehearsal  R — 로컬 리허설: make-env.sh 가 mktemp ROOT 에 만든 env 로 compose.yaml + deploy/compose.prod.yaml 을
#                워크트리의 프로젝트 이름·포트로 띄우고(mock, LLM 키 0) 겉·로그인·서명 PUT·idle·백업을 본 뒤 그 프로젝트만 down -v.
#     planted    심은 파손 P1~P18 을 하나씩 넣고 빨강을 본 뒤 되돌린다. P3·P5·P7·P8 은 리허설 한 벌 안에서. 끝 줄 PLANTED=n/n · FINGERPRINT=same
#     demo2      밴드 DM1 — 두 벌 리허설: 첫 벌(proxy) + 둘째 벌(PROXY_ROLE=none, relay)을 워크트리 포트 안에서 하나씩 올려
#                두 이름 쌍의 겉·회사 하나씩·로그인·서명 PUT 이 자기 저장소로·둘째 벌 내리기/첫 벌 다시 올리기를 본 뒤 두 프로젝트만 down -v.
#     planted-dm1  밴드 DM1 의 심은 파손 P19~P26(정적 — 컨테이너는 caddy 한 번짜리뿐).
# 줄마다 「EXIT=<n>  # <이름>」, 끝 줄 SECTION4_FAIL=<n>. git 저장소 안(main 이 있는 워크트리)에서만 뜻이 있다 —
#   BASE(git merge-base main HEAD)를 못 구하면 종료 2(S4·S8 이 빈 측정으로 통과하지 않게). 로그는 S4_OUT(기본 워크트리 곁 DP1.out/s4).
# 리허설 포트는 워크트리 .env 의 칸(API_PORT 부터 10개)만: +1·+2·+3 은 base 와 같고, proxy 는 +5(http)·+6(https), 127.0.0.1 에만.
# 비밀: 리허설의 비밀은 make-env.sh 가 mktemp 에 만든 값(이 기계 밖 0, 끝에 지움). 찍지 않는다. AI 공급사 호출 0(LLM 변수 비움).
# 셸 규칙(bash 3.2): 연관 배열·mapfile 0.
set -u
cd "$(dirname "$0")/.."
WT="$(pwd)"
OUT="${S4_OUT:-$WT/../DP1.out/s4}"
mkdir -p "$OUT"
BASE="$(git merge-base main HEAD 2>/dev/null)"
# git 밖·main 없음이면 S4·S8 이 빈 측정으로 통과한다 — 여기서 멈춘다(검증 B1)
[ -n "$BASE" ] || { echo "BASE 를 구하지 못했다(git merge-base main HEAD) — git 저장소 안에서, main 이 있는 곳에서 돈다" >&2; exit 2; }
MODE="${1:-static}"
CADDY_IMG="$(sed -n 's/^ *image: \(caddy:[^ ]*\)$/\1/p' deploy/compose.prod.yaml)"
FAILS=0
export LC_ALL=C

# 1-1 의 닫힌 목록(S8)
ALLOWED="deploy/compose.prod.yaml deploy/Caddyfile deploy/env.prod.example deploy/bootstrap-host.sh deploy/make-env.sh
deploy/put-llm-key.sh deploy/ship.sh deploy/up.sh deploy/check-idle-runs.sh deploy/backup-db.sh deploy/smoke.sh
deploy/iam-policy.json deploy/section4-DP1.sh docs/deploy-demo.md
deploy/compose.edge-proxy.yaml deploy/compose.edge-relay.yaml deploy/Caddyfile.demo2 deploy/Caddyfile.relay"
# env.prod.example 에서 값이 비어 있어야 하는 비밀 이름(S5)
SECRET_NAMES="POSTGRES_OWNER_PASSWORD APP_DB_PASSWORD STORAGE_ACCESS_KEY STORAGE_SECRET_KEY SESSION_SECRET EDK_JWT_PUBLIC_KEY
LLM_OPENAI_API_KEY LLM_ANTHROPIC_API_KEY LLM_GEMINI_API_KEY"

step() {  # step <이름> <함수>
  local name="$1" fn="$2" t0 code
  t0=$(date +%s)
  "$fn" > "$OUT/$fn.log" 2>&1
  code=$?
  sed 's/^/  /' "$OUT/$fn.log" | tail -n 40
  echo "EXIT=$code  # $name ($(( $(date +%s) - t0 ))s)"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
  return "$code"
}

# 셸 환경이 섞이지 않게 docker 는 깨끗한 환경으로 부른다.
dk() { env -i HOME="$HOME" PATH="$PATH" ${DOCKER_HOST:+DOCKER_HOST="$DOCKER_HOST"} docker "$@"; }

# 가짜 값 env(S1·S2): 틀(env.prod.example)에서 비밀·주소만 가짜로 채운다. 나머지 이름은 틀 그대로.
fake_env() {  # fake_env <파일> [KEY=VALUE 덮기…]
  local file="$1"; shift
  awk -v over="$*" '
    BEGIN {
      fill["SITE_DOMAIN"] = "demo.example.test"; fill["FILES_DOMAIN"] = "files.demo.example.test"
      fill["STORAGE_CORS_ORIGINS"] = "https://demo.example.test"; fill["LLM_RUN_MODE"] = "live"
      fill["POSTGRES_OWNER_PASSWORD"] = "fake-owner-pw"; fill["APP_DB_PASSWORD"] = "fake-app-pw"
      fill["STORAGE_ACCESS_KEY"] = "fake-access"; fill["STORAGE_SECRET_KEY"] = "fake-secret"
      fill["SESSION_SECRET"] = "fake-session-secret-0123456789abcdef0123"; fill["EDK_JWT_PUBLIC_KEY"] = "fake-pem"
      fill["LLM_OPENAI_API_KEY"] = "fake-llm-key"
      n = split(over, pairs, " ")
      for (i = 1; i <= n; i++) { eq = index(pairs[i], "="); force[substr(pairs[i], 1, eq - 1)] = substr(pairs[i], eq + 1) }
    }
    /^[A-Z_][A-Z0-9_]*=/ {
      eq = index($0, "="); key = substr($0, 1, eq - 1)
      if (key in force) { print key "=" force[key]; next }
      if (substr($0, eq + 1) == "" && (key in fill)) { print key "=" fill[key]; next }
    }
    { print }
  ' deploy/env.prod.example > "$file"
}
render() {  # render <env 파일> <compose 인자…>
  local env_file="$1"; shift
  dk compose --project-directory "$WT" --env-file "$env_file" -f compose.yaml -f deploy/compose.prod.yaml "$@"
}
switch_case() {  # switch_case <이름> <env 파일> <바라는 값> — Scope 3 스위치(MARC-ENT-535)의 렌더 값만 찍고 단언한다
  local j; j="$(mktemp)"
  render "$2" config --format json > "$j" 2>/dev/null
  python3 -I -c 'import json, sys
s = json.load(open(sys.argv[1]))["services"]; label, want = sys.argv[2], sys.argv[3]
got = [s[n]["environment"].get("INVENTORY_SCOPE3_RUNS_ENABLED") for n in ("api-py", "worker-py")]
print(f"스위치 {label}: api-py={got[0]} worker-py={got[1]} (바람 {want})")
if got != [want, want]: print("  ✗ 스위치", label); sys.exit(1)' "$j" "$1" "$3"
  local code=$?
  rm -f "$j"
  return "$code"
}

# ── S1 ── 렌더가 되고, SITE_DOMAIN 이 비면 멈춘다
s1() {
  local e; e="$(mktemp)"
  fake_env "$e"; render "$e" config --quiet; local ok=$?
  fake_env "$e" "SITE_DOMAIN="; render "$e" config --quiet 2>/dev/null; local neg=$?
  rm -f "$e"
  echo "가짜 env 렌더 EXIT=$ok · SITE_DOMAIN 빈 값 EXIT=$neg(≠0 이어야)"
  [ "$ok" = 0 ] && [ "$neg" != 0 ]
}

# ── S2 ── 렌더한 설정을 파이썬(표준 라이브러리)으로 단언
s2() {
  local e j code neg
  e="$(mktemp)"; j="$(mktemp)"
  fake_env "$e"; render "$e" config --format json > "$j" 2>/dev/null
  python3 -I - "$j" "$WT" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); wt = sys.argv[2]
s = d["services"]; bad = []
want = {"parser", "api-py", "migrate-py", "worker-py", "postgres", "storage", "storage-cors", "queue", "proxy"}
if set(s) != want: bad.append(f"서비스 {sorted(s)}")
public = []
for name, svc in s.items():
    for p in svc.get("ports", []):
        if p.get("host_ip") in (None, "", "0.0.0.0", "::"):
            public.append((name, str(p.get("published")), p.get("target")))
if sorted(public) != [("proxy", "443", 443), ("proxy", "80", 80)]: bad.append(f"공개 포트 {public}")
api, wrk = s["api-py"]["environment"], s["worker-py"]["environment"]
same = ["S3_PUBLIC_ENDPOINT", "TRANSLATION_RUN_MAX_USD", "INVENTORY_SCOPE3_RUNS_ENABLED"] + sorted(k for k in api if k.startswith("LLM_"))
for k in same:
    if api.get(k) != wrk.get(k): bad.append(f"api-py·worker-py 다름 {k}")
for name, svc in s.items():
    for k in (svc.get("environment") or {}):
        if k.startswith("OPENAI_"): bad.append(f"{name} 에 {k}")
need = ("DATABASE_URL_PY SESSION_SECRET SESSION_TTL_SECONDS EDK_JWT_PUBLIC_KEY EDK_JWT_AUDIENCE EDK_JWT_ISSUER "
        "LLM_OPENAI_API_KEY LLM_MODELS_FILE LLM_LOG_SINK LLM_RUN_MODE LLM_RUN_MAX_USD S3_BUCKET S3_REGION "
        "AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY UPLOAD_URL_TTL_SECONDS MAX_UPLOAD_BYTES S3_PUBLIC_ENDPOINT "
        "TRANSLATION_RUN_MAX_USD INVENTORY_SCOPE3_RUNS_ENABLED").split()
for k in need:
    if k not in api: bad.append(f"api-py 에 {k} 없음")
expect = {"LLM_RUN_MODE": "live", "LLM_LOG_SINK": "db", "LLM_RUN_MAX_USD": "5.00", "TRANSLATION_RUN_MAX_USD": "10.00",
          "INVENTORY_SCOPE3_RUNS_ENABLED": "true",
          "S3_PUBLIC_ENDPOINT": "https://files.demo.example.test", "LLM_MODELS_FILE": "", "LLM_OPENAI_API_KEY": "fake-llm-key",
          "S3_BUCKET": "esg-documents", "S3_REGION": "ap-northeast-2", "AWS_ACCESS_KEY_ID": "fake-access"}
for k, v in expect.items():
    if api.get(k) != v: bad.append(f"api-py {k}={api.get(k)!r}")
if "fake-app-pw@" not in api.get("DATABASE_URL_PY", ""): bad.append("DATABASE_URL_PY 에 APP_DB_PASSWORD 가 안 닿음")
if s["storage-cors"]["environment"].get("STORAGE_CORS_ORIGINS") != "https://demo.example.test": bad.append("STORAGE_CORS_ORIGINS")
if s["postgres"]["environment"].get("POSTGRES_PASSWORD") != "fake-owner-pw": bad.append("POSTGRES_OWNER_PASSWORD")
px = s["proxy"]
if px["environment"].get("SITE_DOMAIN") != "demo.example.test" or px["environment"].get("FILES_DOMAIN") != "files.demo.example.test":
    bad.append("proxy 도메인")
if not any(v.get("source") == f"{wt}/deploy/Caddyfile" and v.get("read_only") for v in px.get("volumes", [])):
    bad.append("proxy 의 Caddyfile 묶음(경로 기준)")
for name in ("proxy", "parser", "worker-py", "postgres", "api-py", "storage", "queue"):
    if s[name].get("restart") != "unless-stopped": bad.append(f"{name} restart={s[name].get('restart')}")
print(f"서비스 {len(s)} · 공개 포트 {public} · 같은 값 {len(same)}개 · 필요한 키 {len(need)}개")
for b in bad: print("  ✗", b)
sys.exit(1 if bad else 0)
PY
  code=$?
  fake_env "$e" "TRANSLATION_RUN_MAX_USD="; render "$e" config --quiet 2>/dev/null; neg=$?
  echo "TRANSLATION_RUN_MAX_USD 빈 값 렌더 EXIT=$neg(≠0 이어야)"
  # Scope 3 스위치 렌더 세 경우(MARC-ENT-535): 값 true · 빈 값 · 줄 없음
  local sw1 sw2 sw3
  fake_env "$e"; switch_case "값 true" "$e" true; sw1=$?
  fake_env "$e" "INVENTORY_SCOPE3_RUNS_ENABLED="; switch_case "빈 값" "$e" false; sw2=$?
  fake_env "$e"; grep -v '^INVENTORY_SCOPE3_RUNS_ENABLED=' "$e" > "$j"; cat "$j" > "$e"; switch_case "줄 없음" "$e" false; sw3=$?
  rm -f "$e" "$j"
  [ "$code" = 0 ] && [ "$neg" != 0 ] && [ "$sw1" = 0 ] && [ "$sw2" = 0 ] && [ "$sw3" = 0 ]
}

# ── S3 ── Caddy 이미지로 validate · fmt 차이 0
s3() {
  local v f
  dk run --rm -e SITE_DOMAIN=demo.example.test -e FILES_DOMAIN=files.demo.example.test \
    -v "$WT/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" "$CADDY_IMG" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile \
    > "$OUT/s3-validate.log" 2>&1
  v=$?
  dk run --rm -v "$WT/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" "$CADDY_IMG" caddy fmt /etc/caddy/Caddyfile | diff -q - deploy/Caddyfile >/dev/null
  f=$?
  echo "$CADDY_IMG · validate EXIT=$v · fmt 차이 EXIT=$f"
  [ "$v" = 0 ] && [ "$f" = 0 ]
}

# ── S4 ── 더한 줄에 키 꼴 0(양성 대조 포함)
KEY_RE='sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|aws_secret_access_[k]ey'  # [k] = 이 줄 자신을 세지 않게
added_lines() {  # added_lines <파일> — BASE 에서 지금 작업 트리까지(커밋·스테이징·추적 안 한 새 파일)의 + 줄. git 이 실패하면 1
  local diff new f
  diff="$(git diff "$BASE")" || return 1
  new="$(git ls-files -o --exclude-standard)" || return 1
  { printf '%s\n' "$diff"
    for f in $new; do git diff --no-index /dev/null "$f"; [ $? -le 1 ] || return 1; done
  } | grep -E '^\+' | grep -v -E '^\+\+\+ ' > "$1"
  return 0
}
s4() {
  local n pos lines
  lines="$(mktemp)"
  added_lines "$lines" || { echo "git diff 가 실패했다 — 빈 측정으로 통과하지 않는다"; rm -f "$lines"; return 1; }
  [ -s "$lines" ] || { echo "더한 줄이 0 — 잴 것이 없다"; rm -f "$lines"; return 1; }
  n="$(grep -c -E "$KEY_RE" "$lines")"
  echo "더한 줄 $(wc -l < "$lines" | tr -d ' ')개"
  rm -f "$lines"
  pos="$(printf '+K=sk-%s\n' "$(printf 'A%.0s' $(seq 1 20))" | grep -c -E "$KEY_RE")"
  echo "더한 줄의 키 꼴 $n(0 이어야) · 양성 대조 $pos(1 이어야)"
  [ "$n" = 0 ] && [ "$pos" = 1 ]
}

# ── S5 ── 틀의 비밀 이름은 전부 「이름=」 빈 값, 한 번씩
s5() {
  local bad=0 name lines
  for name in $SECRET_NAMES; do
    lines="$(grep -c -E "^$name=" deploy/env.prod.example)"
    if [ "$lines" != 1 ] || ! grep -q -x "$name=" deploy/env.prod.example; then echo "  ✗ $name (줄 $lines)"; bad=1; fi
  done
  echo "비밀 이름 $(echo $SECRET_NAMES | wc -w | tr -d ' ')개 빈 값 확인"
  [ "$bad" = 0 ]
}

# ── S6 ── 문법 · make-env 두 번 · put-llm-key(가짜 키·가짜 ssh) · ship(가짜 ssh)
s6() {
  local bad=0 f t sum1 sum2 fake_ssh key_file out fake_key short
  for f in deploy/*.sh; do bash -n "$f" || { echo "  ✗ bash -n $f"; bad=1; }; done
  t="$(mktemp -d)"; mkdir -p "$t/shared"
  deploy/make-env.sh demo.example.test files.demo.example.test "$t" > "$t/m1.log" 2>&1 || { echo "  ✗ make-env 첫 번"; bad=1; }
  [ "$(stat -f %Lp "$t/shared/.env" 2>/dev/null || stat -c %a "$t/shared/.env")" = 600 ] || { echo "  ✗ .env 권한"; bad=1; }
  for f in POSTGRES_OWNER_PASSWORD APP_DB_PASSWORD STORAGE_ACCESS_KEY STORAGE_SECRET_KEY SESSION_SECRET; do
    grep -q -E "^$f=[0-9a-f]{64}$" "$t/shared/.env" || { echo "  ✗ $f 가 hex 64 가 아님"; bad=1; }
  done
  grep -q -E '^EDK_JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\\n[A-Za-z0-9+/=\\n]+-----END PUBLIC KEY-----\\n$' "$t/shared/.env" \
    || { echo "  ✗ EDK 공개키 꼴"; bad=1; }
  grep -q -x 'STORAGE_CORS_ORIGINS=https://demo.example.test' "$t/shared/.env" || { echo "  ✗ STORAGE_CORS_ORIGINS"; bad=1; }
  grep -q -E 'PRIVATE KEY' "$t/shared/.env" && { echo "  ✗ 개인키가 남음"; bad=1; }
  # make-env 의 출력에 만든 비밀 값 0(이름만 찍는다 — 검증 R2)
  local leaked=0 v
  for f in POSTGRES_OWNER_PASSWORD APP_DB_PASSWORD STORAGE_ACCESS_KEY STORAGE_SECRET_KEY SESSION_SECRET; do
    v="$(sed -n "s/^$f=//p" "$t/shared/.env")"
    [ -n "$v" ] && leaked=$((leaked + $(grep -F -c -- "$v" "$t/m1.log")))
  done
  [ "$leaked" = 0 ] || { echo "  ✗ make-env 출력에 비밀 값 $leaked 줄"; bad=1; }
  sum1="$(shasum "$t/shared/.env")"
  deploy/make-env.sh demo.example.test files.demo.example.test "$t" > "$t/m2.log" 2>&1 && { echo "  ✗ make-env 두 번째가 거절하지 않음"; bad=1; }
  sum2="$(shasum "$t/shared/.env")"
  [ "$sum1" = "$sum2" ] || { echo "  ✗ 두 번째가 파일을 바꿈"; bad=1; }
  ls "$t/shared" | grep -q '\.env\.new' && { echo "  ✗ 임시 파일이 남음"; bad=1; }
  # put-llm-key: 가짜 키 파일 · 가짜 ssh(대상을 버리고 원격 글을 이 기계의 sh 로)
  fake_ssh="$t/fake-ssh"; printf '#!/bin/sh\nshift\nexec sh -c "$1"\n' > "$fake_ssh"; chmod 700 "$fake_ssh"
  fake_key="sk-fake$(openssl rand -hex 12)"
  key_file="$t/key.env"; (umask 077; printf 'export OPENAI_API_KEY="%s"\n' "$fake_key" > "$key_file")
  out="$(KEY_FILE="$key_file" SSH_CMD="$fake_ssh" ENV_PATH="$t/shared/.env" deploy/put-llm-key.sh fake-host 2>&1)" || { echo "  ✗ put-llm-key 실패"; bad=1; }
  printf '%s\n' "$out" | grep -q -F "$fake_key" && { echo "  ✗ 출력에 키 글자"; bad=1; }
  grep -q -x "LLM_OPENAI_API_KEY=$fake_key" "$t/shared/.env" || { echo "  ✗ 키 줄이 안 바뀜"; bad=1; }
  grep -q -x "LLM_RUN_MODE=live" "$t/shared/.env" || { echo "  ✗ live 로 안 바뀜"; bad=1; }
  [ "$(stat -f %Lp "$t/shared/.env" 2>/dev/null || stat -c %a "$t/shared/.env")" = 600 ] || { echo "  ✗ 바꾼 뒤 권한"; bad=1; }
  out="$(SSH_CMD="$fake_ssh" ENV_PATH="$t/shared/.env" deploy/put-llm-key.sh fake-host --mock 2>&1)" || { echo "  ✗ --mock 실패"; bad=1; }
  grep -q -x "LLM_RUN_MODE=" "$t/shared/.env" || { echo "  ✗ --mock 이 모드를 안 비움"; bad=1; }
  grep -q -x "LLM_OPENAI_API_KEY=$fake_key" "$t/shared/.env" || { echo "  ✗ --mock 이 키를 건드림"; bad=1; }
  echo "put-llm-key 출력(키 0): $(printf '%s' "$out" | tr '\n' ' ')"
  # ship: BASE(main 의 조상)를 가짜 서버 뿌리에 · HEAD(병합 안 됨)는 거절
  mkdir -p "$t/srv/releases" "$t/srv/shared"
  SSH_CMD="$fake_ssh" SHIP_ROOT="$t/srv" deploy/ship.sh fake-host "$BASE" > "$t/ship.log" 2>&1 || { echo "  ✗ ship 실패"; cat "$t/ship.log"; bad=1; }
  short="$(git rev-parse --short=12 "$BASE")"
  [ "$(readlink "$t/srv/current")" = "$t/srv/releases/$short" ] || { echo "  ✗ current 가 안 바뀜"; bad=1; }
  [ -f "$t/srv/current/compose.yaml" ] && [ ! -e "$t/srv/current/.env" ] || { echo "  ✗ 푼 내용"; bad=1; }
  [ "$(wc -l < "$t/srv/shared/DEPLOYED" | tr -d ' ')" = 1 ] || { echo "  ✗ DEPLOYED"; bad=1; }
  # 같은 해시를 다시 보냄(지금 current) — current 가 늘 살아 있는 폴더를 가리키고 .part 가 안 남아야(리뷰 L2)
  SSH_CMD="$fake_ssh" SHIP_ROOT="$t/srv" deploy/ship.sh fake-host "$BASE" > "$t/ship2.log" 2>&1 || { echo "  ✗ 같은 해시 다시 보내기 실패"; cat "$t/ship2.log"; bad=1; }
  [ "$(readlink "$t/srv/current")" = "$t/srv/releases/$short" ] && [ -f "$t/srv/current/compose.yaml" ] || { echo "  ✗ 다시 보낸 뒤 current"; bad=1; }
  ls "$t/srv/releases" | grep -q '\.part$' && { echo "  ✗ .part 가 남음"; bad=1; }
  [ "$(wc -l < "$t/srv/shared/DEPLOYED" | tr -d ' ')" = 2 ] || { echo "  ✗ DEPLOYED 둘째 줄"; bad=1; }
  if [ "$(git rev-parse HEAD)" != "$BASE" ]; then
    SSH_CMD="$fake_ssh" SHIP_ROOT="$t/srv" deploy/ship.sh fake-host HEAD > /dev/null 2>&1 && { echo "  ✗ 병합 안 된 HEAD 를 받음"; bad=1; }
  fi
  rm -rf "$t"
  echo "make-env 두 번(둘째 거절) · put-llm-key live/mock · ship BASE·HEAD 거절 확인"
  [ "$bad" = 0 ]
}

# ── S7 ── IAM 정책이 DP1-user-asks.md 의 문 목록 꼴
s7() {
  python3 -I - deploy/iam-policy.json <<'PY'
import json, sys
p = json.load(open(sys.argv[1])); bad = []
st = {s["Sid"]: s for s in p["Statement"]}
want = ["Read", "Identity", "RunTagged", "RunOther", "Create", "CreateSg", "CreateSgVpc", "TagOnCreate", "SgRules", "Eip",
        "Power", "Dlm", "PassDlm", "R53", "R53Rec", "Snap", "R53Health", "Alerts"]
if list(st) != want: bad.append(f"Sid {list(st)}")
def acts(s): return s["Action"] if isinstance(s["Action"], list) else [s["Action"]]
def res(s): return s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]
def cond(s): return s.get("Condition", {}).get("StringEquals", {})
for s in p["Statement"]:
    if s.get("Effect") != "Allow": bad.append(f"{s['Sid']} Effect")
run = [s for s in p["Statement"] if "ec2:RunInstances" in acts(s)]
if len(run) != 2: bad.append("RunInstances 문이 둘이 아님")
rt, ro = st.get("RunTagged", {}), st.get("RunOther", {})
if sorted(r.split(":")[-1].split("/")[0] for r in res(rt)) != ["instance", "volume"]: bad.append("RunTagged 자원")
if cond(rt).get("aws:RequestTag/Project") != "marcspon-demo": bad.append("RunTagged 요청 태그")
if sorted(r.split(":")[-1].split("/")[0] for r in res(ro)) != ["image", "key-pair", "network-interface", "security-group", "subnet"]:
    bad.append("RunOther 자원")
if "aws:RequestTag/Project" in cond(ro): bad.append("RunOther 에 요청 태그")
sg = [s for s in p["Statement"] if "ec2:CreateSecurityGroup" in acts(s)]
if len(sg) != 2: bad.append("CreateSecurityGroup 문이 둘이 아님")
if cond(st["CreateSg"]).get("aws:RequestTag/Project") != "marcspon-demo" or not res(st["CreateSg"])[0].endswith(":security-group/*"):
    bad.append("CreateSg")
if "aws:RequestTag/Project" in cond(st["CreateSgVpc"]) or not res(st["CreateSgVpc"])[0].endswith(":vpc/*"): bad.append("CreateSgVpc")
if res(st["PassDlm"]) != ["arn:aws:iam::ACCOUNT_ID:role/*AWSDataLifecycleManagerDefaultRole"]: bad.append("PassDlm 자원")
if cond(st["PassDlm"]).get("iam:PassedToService") != "dlm.amazonaws.com": bad.append("PassDlm 조건")
if sorted(cond(st["TagOnCreate"]).get("ec2:CreateAction", [])) != ["AllocateAddress", "CreateSecurityGroup", "CreateSnapshot", "ImportKeyPair", "RunInstances"]:
    bad.append("TagOnCreate 의 ec2:CreateAction")
for s in p["Statement"]:
    a = acts(s); region = cond(s).get("aws:RequestedRegion")
    if any(x.startswith(("ec2:", "dlm:")) for x in a) and region != "ap-northeast-2": bad.append(f"{s['Sid']} 리전 조건 없음")
    if any(x.startswith("route53") for x in a) and "Condition" in s: bad.append(f"{s['Sid']} Route53 에 조건")
    # 다운 알림(⑤-d): Route53 지표가 us-east-1 에만 있어 SNS·CloudWatch 는 그 리전으로만
    if any(x.startswith(("sns:", "cloudwatch:")) for x in a) and region != "us-east-1": bad.append(f"{s['Sid']} 알림 리전 조건")
    for x in a:
        if (x.startswith(("ec2:Terminate", "ec2:Delete", "dlm:Delete")) or x in ("ec2:ReleaseAddress", "ec2:ModifyInstanceAttribute")
                or x.startswith("s3:") or (x.startswith("iam:") and x != "iam:PassRole") or x in ("*", "ec2:*", "iam:*")
                or x.startswith(("sns:Delete", "sns:Unsubscribe", "cloudwatch:Delete", "route53:DeleteHealthCheck"))):
            bad.append(f"금지 동작 {x}")
print(f"문 {len(st)}개 · RunInstances {len(run)}문 · CreateSecurityGroup {len(sg)}문")
for b in bad: print("  ✗", b)
sys.exit(1 if bad else 0)
PY
}

# ── S8 ── 바뀐 파일 ⊂ 1-1 목록
s8() {
  local changed names new bad=0 f
  names="$(git diff --name-only "$BASE")" || { echo "git diff 가 실패했다"; return 1; }
  new="$(git ls-files -o --exclude-standard)" || { echo "git ls-files 가 실패했다"; return 1; }
  changed="$(printf '%s\n%s\n' "$names" "$new" | grep . | sort -u)"
  [ -n "$changed" ] || { echo "바뀐 파일이 0 — 잴 것이 없다"; return 1; }
  for f in $changed; do
    echo "$ALLOWED" | tr ' ' '\n' | grep -q -x "$f" || { echo "  ✗ 목록 밖: $f"; bad=1; }
  done
  echo "바뀐 파일 $(echo "$changed" | grep -c .)개(목록 18 안)"
  [ "$bad" = 0 ]
}

# ── S9 ── (DM1) 둘째 이름이 빌 때 Caddy adapt 가 BASE 와 같다 · 둘째 블록을 묶으면 파일 거르기가 두 FILES 이름에 다 걸린다
#   · Caddyfile.demo2·Caddyfile.relay 의 validate·fmt
caddy_adapt() {  # caddy_adapt <Caddyfile 경로> [sites.d 에 묶을 파일] — 정렬한 JSON 을 표준 출력으로
  local extra=()
  [ -z "${2:-}" ] || extra=(-v "$2:/etc/caddy/sites.d/demo2.caddy:ro")
  dk run --rm -e SITE_DOMAIN=demo.example.test -e FILES_DOMAIN=files.demo.example.test \
    -e DEMO2_SITE_DOMAIN=demo2.example.test -e DEMO2_FILES_DOMAIN=files-demo2.example.test \
    -v "$1:/etc/caddy/Caddyfile:ro" ${extra[@]+"${extra[@]}"} "$CADDY_IMG" caddy adapt --config /etc/caddy/Caddyfile 2>/dev/null \
    | python3 -I -c 'import json, sys; print(json.dumps(json.load(sys.stdin), sort_keys=True, indent=1))'
}
s9() {
  local t bad=0 f
  t="$(mktemp -d)"
  git show "$BASE:deploy/Caddyfile" > "$t/base.caddy" || { echo "BASE Caddyfile 을 못 읽음"; rm -rf "$t"; return 1; }
  caddy_adapt "$t/base.caddy" > "$t/base.json" && caddy_adapt "$WT/deploy/Caddyfile" > "$t/solo.json" \
    && caddy_adapt "$WT/deploy/Caddyfile" "$WT/deploy/Caddyfile.demo2" > "$t/two.json" || { echo "  ✗ adapt 실패"; bad=1; }
  [ -s "$t/base.json" ] || { echo "  ✗ BASE adapt 가 비었다 — 빈 측정"; bad=1; }
  if diff -q "$t/base.json" "$t/solo.json" >/dev/null; then echo "둘째 이름 없음: adapt JSON = BASE (diff 0)"
  else echo "  ✗ 둘째 이름 없는 adapt 가 BASE 와 다름"; diff "$t/base.json" "$t/solo.json" | head -n 20; bad=1; fi
  python3 -I - "$t/two.json" <<'PYS9' || bad=1
import json, sys
d = json.load(open(sys.argv[1])); bad = []
routes = d["apps"]["http"]["servers"]["srv0"]["routes"]
def by_host(h):
    r = [x for x in routes if any(h in m.get("host", []) for m in x.get("match", []))]
    return json.dumps(r[0]) if len(r) == 1 else None
for h, up in (("files.demo.example.test", "storage:7070"), ("files-demo2.example.test", "demo2-edge:7070")):
    j = by_host(h)
    if j is None: bad.append(f"{h} 블록 없음"); continue
    for need in ('"X-Amz-Signature"', '"X-Amz-Copy-Source"', '"max_size": 60000000', '"PUT"', '"OPTIONS"', f'"dial": "{up}"'):
        if need not in j: bad.append(f"{h} 에 {need} 없음")
    n403 = j.count('"status_code": 403')
    if n403 < 3: bad.append(f"{h} 403 거르기 {n403}개(3 이어야)")
for h, up in (("demo.example.test", "api-py:8000"), ("demo2.example.test", "demo2-edge:8000")):
    j = by_host(h)
    if j is None: bad.append(f"{h} 블록 없음"); continue
    for need in ('"Strict-Transport-Security"', '"Server"', '"request_buffers": 22020096', f'"dial": "{up}"'):
        if need not in j: bad.append(f"{h} 에 {need} 없음")
print(f"두 벌 adapt: 라우트 {len(routes)}개 · FILES 두 이름 거르기 · SITE 두 이름 HSTS·버퍼")
for b in bad: print("  ✗", b)
sys.exit(1 if bad else 0)
PYS9
  for f in Caddyfile.demo2 Caddyfile.relay; do
    dk run --rm -v "$WT/deploy/$f:/c:ro" "$CADDY_IMG" caddy fmt /c | diff -q - "deploy/$f" >/dev/null || { echo "  ✗ fmt 차이 $f"; bad=1; }
  done
  dk run --rm -v "$WT/deploy/Caddyfile.relay:/etc/caddy/Caddyfile:ro" "$CADDY_IMG" caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1 \
    || { echo "  ✗ relay validate"; bad=1; }
  # 둘째 블록을 묶은 채 validate(demo2-edge 가 안 풀려도 설정은 선다 — 요청 때 푼다)
  dk run --rm -e SITE_DOMAIN=demo.example.test -e FILES_DOMAIN=files.demo.example.test -e DEMO2_SITE_DOMAIN=demo2.example.test \
    -e DEMO2_FILES_DOMAIN=files-demo2.example.test -v "$WT/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" \
    -v "$WT/deploy/Caddyfile.demo2:/etc/caddy/sites.d/demo2.caddy:ro" "$CADDY_IMG" caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1 \
    || { echo "  ✗ 두 벌 validate"; bad=1; }
  rm -rf "$t"
  echo "Caddyfile.demo2·relay fmt · validate(relay · 두 벌)"
  [ "$bad" = 0 ]
}

# ── S10 ── (DM1) 가드 · 기본 뿌리 유도 · 덧붙임 렌더 · make-env 둘째 벌 · cron
up_guard() {  # up_guard <뿌리> <바라는 글> [KEY=VALUE…] — 가짜 env 로 up.sh 가 멈추고(종료 1) 그 글을 내는지. /srv 는 만들지 않는다
  local root="$1" want="$2" e out code; shift 2
  e="$(mktemp)"; fake_env "$e" "$@"
  out="$(env -i HOME="$HOME" PATH="$PATH" DEPLOY_ROOT="$root" ENV_FILE="$e" APP_DIR="$WT" deploy/up.sh --no-build 2>&1)"; code=$?
  rm -f "$e"
  if [ "$code" = 1 ] && printf '%s' "$out" | grep -q -F "$want"; then echo "가드 $root $* → 멈춤"; return 0; fi
  echo "  ✗ 가드 $root $* → EXIT=$code: $(printf '%s' "$out" | tail -n 1)"; return 1
}
s10() {
  local bad=0 e j t f line pair got nr="$WT/../DM1.out/no-root"
  up_guard /srv/esg-demo2 "esg-demo2 여야" || bad=1   # 둘째 뿌리 + esg-demo(틀 값)
  up_guard /srv/esg-demo2 "esg-demo2 여야" COMPOSE_PROJECT_NAME=esg-app-dm1 PROXY_ROLE=none || bad=1
  up_guard /srv/esg-demo "esg-demo 여야" COMPOSE_PROJECT_NAME=esg-demo2 PROXY_ROLE=none || bad=1
  up_guard /srv/esg-demo2 "PROXY_ROLE 이 뿌리와" COMPOSE_PROJECT_NAME=esg-demo2 || bad=1   # 둘째 뿌리인데 edge
  up_guard /srv/esg-demo "PROXY_ROLE 이 뿌리와" PROXY_ROLE=none || bad=1
  up_guard "$nr" "PROXY_ROLE 은 edge·none" COMPOSE_PROJECT_NAME=dm1-guard PROXY_ROLE=both || bad=1
  up_guard "$nr" "둘 다 있거나" COMPOSE_PROJECT_NAME=dm1-guard DEMO2_SITE_DOMAIN=demo2.example.test || bad=1
  up_guard "$nr" ".env 의 칸이다" COMPOSE_PROJECT_NAME=dm1-guard PROXY_ROLE=none \
    DEMO2_SITE_DOMAIN=a.example.test DEMO2_FILES_DOMAIN=b.example.test || bad=1
  up_guard "$nr" "첫 벌 proxy 가 없다" COMPOSE_PROJECT_NAME=dm1-guard PROXY_ROLE=none EDGE_NETWORK=dm1-no-such-net || bad=1
  # 기본 뿌리 = 스크립트가 놓인 벌(critic 블로커 ②): 세 스크립트의 유도 줄을 꺼내 here 값마다 돌린다
  for f in deploy/up.sh deploy/backup-db.sh deploy/check-idle-runs.sh; do
    line="$(grep -F 'case "$here" in /srv/esg-demo2/*)' "$f")"
    [ -n "$line" ] || { echo "  ✗ $f 에 기본 뿌리 유도 줄 없음"; bad=1; continue; }
    grep -q -x -F 'root="${DEPLOY_ROOT:-$default_root}"' "$f" || { echo "  ✗ $f 의 root 가 유도 값을 안 씀"; bad=1; }
    for pair in /srv/esg-demo2/current/deploy=/srv/esg-demo2 /srv/esg-demo2/releases/0123abcd/deploy=/srv/esg-demo2 \
        /srv/esg-demo/current/deploy=/srv/esg-demo /srv/esg-demo/releases/0123abcd/deploy=/srv/esg-demo "$WT/deploy=/srv/esg-demo"; do
      got="$(here="${pair%%=*}" bash -c "$line"' ; echo "$default_root"')"
      [ "$got" = "${pair#*=}" ] || { echo "  ✗ $f: here=${pair%%=*} → $got"; bad=1; }
    done
  done
  grep -q -F '/srv/esg-demo/*:/srv/esg-demo2|/srv/esg-demo2/*:/srv/esg-demo)' deploy/up.sh || { echo "  ✗ up.sh 벌 섞임 가드 없음"; bad=1; }
  echo "기본 뿌리 유도 3파일 × 5경우"
  # 렌더: 첫 벌 + edge-proxy · 둘째 벌 + edge-relay
  e="$(mktemp)"; j="$(mktemp)"
  fake_env "$e" DEMO2_SITE_DOMAIN=demo2.example.test DEMO2_FILES_DOMAIN=files-demo2.example.test
  render "$e" -f deploy/compose.edge-proxy.yaml config --format json > "$j" 2>/dev/null || { echo "  ✗ edge-proxy 렌더"; bad=1; }
  python3 -I - "$j" <<'PYS10A' || bad=1
import json, sys
d = json.load(open(sys.argv[1])); s = d["services"]; bad = []
px = s["proxy"]
if sorted(px.get("networks", {})) != ["default", "edge"]: bad.append(f"proxy 네트워크 {sorted(px.get('networks', {}))}")
if d["networks"]["edge"].get("name") != "esg-edge" or not d["networks"]["edge"].get("external"): bad.append("edge 가 바깥 esg-edge 가 아님")
if px["environment"].get("DEMO2_SITE_DOMAIN") != "demo2.example.test": bad.append("DEMO2_SITE_DOMAIN")
if not any(v.get("target") == "/etc/caddy/sites.d/demo2.caddy" and v.get("read_only") for v in px.get("volumes", [])): bad.append("demo2 묶음")
for n, v in s.items():
    if n != "proxy" and "edge" in (v.get("networks") or {}): bad.append(f"{n} 이 edge 에")
print("첫 벌 + edge-proxy: proxy 만 default·edge, DEMO2 이름·묶음")
for b in bad: print("  ✗", b)
sys.exit(1 if bad else 0)
PYS10A
  fake_env "$e" COMPOSE_PROJECT_NAME=esg-demo2 PROXY_ROLE=none POSTGRES_PORT=25432 STORAGE_PORT=29000 API_PY_PORT=28081 \
    SITE_DOMAIN=demo2.example.test FILES_DOMAIN=files-demo2.example.test STORAGE_CORS_ORIGINS=https://demo2.example.test
  render "$e" -f deploy/compose.edge-relay.yaml config --format json > "$j" 2>/dev/null || { echo "  ✗ edge-relay 렌더"; bad=1; }
  python3 -I - "$j" <<'PYS10B' || bad=1
import json, sys
d = json.load(open(sys.argv[1])); s = d["services"]; bad = []
r = s.get("relay") or {}
if sorted(r.get("networks", {})) != ["default", "edge"]: bad.append(f"relay 네트워크 {sorted(r.get('networks', {}))}")
if (r.get("networks", {}).get("edge") or {}).get("aliases") != ["demo2-edge"]: bad.append("relay 별칭")
if r.get("ports"): bad.append("relay 에 호스트 포트")
# 서비스 이름(api-py·storage)이 공유 네트워크에 나가지 않는다 — 첫 벌 proxy 의 조회가 새지 않게
for n, v in s.items():
    if n != "relay" and "edge" in (v.get("networks") or {}): bad.append(f"{n} 이 edge 에")
pub = sorted((n, str(p.get("published")), p.get("host_ip")) for n, v in s.items() if n != "proxy" for p in v.get("ports", []))
if pub != [("api-py", "28081", "127.0.0.1"), ("postgres", "25432", "127.0.0.1"), ("storage", "29000", "127.0.0.1")]: bad.append(f"둘째 벌 포트 {pub}")
if s["api-py"]["environment"].get("S3_PUBLIC_ENDPOINT") != "https://files-demo2.example.test": bad.append("S3_PUBLIC_ENDPOINT 가 둘째 이름이 아님")
if s["storage-cors"]["environment"].get("STORAGE_CORS_ORIGINS") != "https://demo2.example.test": bad.append("STORAGE_CORS_ORIGINS")
if d.get("name") != "esg-demo2": bad.append(f"이름 {d.get('name')}")
if not str(s["api-py"].get("image", "")).startswith("esg-demo2/"): bad.append(f"이미지 이름 {s['api-py'].get('image')}")
print(f"둘째 벌 + edge-relay: relay 만 edge(demo2-edge) · 호스트 포트 {pub} · 자기 이름·이미지")
for b in bad: print("  ✗", b)
sys.exit(1 if bad else 0)
PYS10B
  rm -f "$e" "$j"
  # make-env: 둘째 뿌리 짝 거절 · demo2 칸(포트 셋 — critic 블로커 ①)
  t="$(mktemp -d)"; mkdir -p "$t/shared"
  deploy/make-env.sh a.example.test b.example.test /srv/esg-demo2 >/dev/null 2>&1 && { echo "  ✗ make-env /srv/esg-demo2 가 지나감"; bad=1; }
  MAKE_ENV_SET=first deploy/make-env.sh a.example.test b.example.test /srv/esg-demo2 2>&1 | grep -q "맞지 않는다" || { echo "  ✗ make-env 둘째 뿌리에 first"; bad=1; }
  MAKE_ENV_SET=demo2 deploy/make-env.sh a.example.test b.example.test /srv/esg-demo 2>&1 | grep -q "맞지 않는다" || { echo "  ✗ make-env 첫 뿌리에 demo2"; bad=1; }
  MAKE_ENV_SET=demo2 deploy/make-env.sh demo2.example.test files-demo2.example.test "$t" >/dev/null 2>&1 || { echo "  ✗ make-env demo2"; bad=1; }
  for f in COMPOSE_PROJECT_NAME=esg-demo2 PROXY_ROLE=none POSTGRES_PORT=25432 STORAGE_PORT=29000 API_PY_PORT=28081 \
      STORAGE_CORS_ORIGINS=https://demo2.example.test DEMO2_SITE_DOMAIN= EDGE_NETWORK=; do
    [ "$(grep -c -x -F "$f" "$t/shared/.env")" = 1 ] || { echo "  ✗ demo2 .env 에 $f 한 줄이 아님"; bad=1; }
  done
  rm -rf "$t"
  # cron 줄 찾기가 두 뿌리를 섞지 않는다(앞머리 /srv/esg-demo ⊂ /srv/esg-demo2)
  line='45 18 * * * DEPLOY_ROOT=/srv/esg-demo2 /srv/esg-demo2/current/deploy/backup-db.sh >> /srv/esg-demo2/backup/backup.log 2>&1'
  printf '%s\n' "$line" | grep -qF "/srv/esg-demo/current/deploy/backup-db.sh " && { echo "  ✗ 둘째 cron 줄을 첫 벌 줄로 읽음"; bad=1; }
  grep -qF 'grep -qF "$ROOT/current/deploy/backup-db.sh "' deploy/bootstrap-host.sh || { echo "  ✗ bootstrap 의 cron 찾기 꼴"; bad=1; }
  grep -qF '/srv/esg-demo2) cron_min=45 ;;' deploy/bootstrap-host.sh || { echo "  ✗ bootstrap 둘째 뿌리·시각"; bad=1; }
  echo "가드 9 · 렌더 둘 · make-env 둘째 벌 · cron 찾기"
  [ "$bad" = 0 ]
}

fast_gate() {
  local log
  export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
  log="$(scripts/verify.sh --fast 2>&1)"; echo "$log" > "$OUT/verify-fast.full.log"
  echo "$log" | tail -n 3
  echo "$log" | tail -n 1 | grep -q '^VERIFY_FAST=PASS'
}

# ══ R — 로컬 리허설 ══════════════════════════════════════════════════
R_PROJECT="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env 2>/dev/null)"
PBASE="$(sed -n 's/^API_PORT=//p' .env 2>/dev/null)"
R_ROOT=""; R_ENV=""
# 배포 스크립트는 셸에 가짜 COMPOSE_PROJECT_NAME 이 내보내진 채로 부른다 — -p 가 그것을 이기는지 잰다(리뷰 M3)
DECOY_PROJECT=dp1-decoy-not-this
R_SITE=localhost R_FILES=files.localhost
r_http() { echo $((PBASE + 5)); }
r_https() { echo $((PBASE + 6)); }
rc() { curl -sS -k --max-time 20 --resolve "$R_SITE:$(r_https):127.0.0.1" --resolve "$R_FILES:$(r_https):127.0.0.1" "$@"; }
rdc() { env -i HOME="$HOME" PATH="$PATH" docker compose --project-directory "$WT" --env-file "$R_ENV" -f compose.yaml -f deploy/compose.prod.yaml "$@"; }
set_env() {  # set_env KEY VALUE — 리허설 env 의 그 줄을 바꾼다(없으면 더한다)
  local t; t="$(mktemp "$R_ROOT/shared/.e.XXXXXX")"
  awk -v k="$1" -v v="$2" 'BEGIN{d=0} index($0, k "=") == 1 { print k "=" v; d=1; next } { print } END { if (!d) print k "=" v }' "$R_ENV" > "$t"
  mv "$t" "$R_ENV"
}

r_prepare() {  # mktemp ROOT 에 make-env.sh 로 env 를 만들고 워크트리 이름·포트를 덧씀
  [ -n "$R_PROJECT" ] && [ -n "$PBASE" ] || { echo "워크트리 .env 에 COMPOSE_PROJECT_NAME·API_PORT 가 없다"; return 1; }
  case "$R_PROJECT" in esg-demo) echo "리허설 프로젝트가 esg-demo 다 — 거절(서버 이름)"; return 1 ;; esac
  R_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/dp1-r.XXXXXX")"; mkdir -p "$R_ROOT/shared"; chmod 700 "$R_ROOT/shared"
  R_ENV="$R_ROOT/shared/.env"
  deploy/make-env.sh "$R_SITE" "$R_FILES" "$R_ROOT" || return 1
  set_env COMPOSE_PROJECT_NAME "$R_PROJECT"
  set_env POSTGRES_PORT "$((PBASE + 1))"; set_env STORAGE_PORT "$((PBASE + 2))"; set_env API_PY_PORT "$((PBASE + 3))"
  set_env PROXY_HTTP_PORT "127.0.0.1:$(r_http)"; set_env PROXY_HTTPS_PORT "127.0.0.1:$(r_https)"
  set_env PROXY_PUBLIC_PORT_SUFFIX ":$(r_https)"
  set_env STORAGE_CORS_ORIGINS "https://$R_SITE:$(r_https)"
  set_env LLM_RUN_MODE ""   # mock — 리허설은 AI 공급사 0
  echo "리허설 env: $R_ROOT/shared/.env · 프로젝트 $R_PROJECT · proxy 127.0.0.1:$(r_http)/$(r_https)"
}
r_build() {
  scripts/with-build-lock.sh env -i HOME="$HOME" PATH="$PATH" docker compose --project-directory "$WT" --env-file "$R_ENV" \
    -f compose.yaml -f deploy/compose.prod.yaml build
}
r_up() {
  # 올리기 직전마다 컨테이너 문(scripts/lib/lock.sh — verify.lock 없음·free ≥ 20%·1분 부하·떠 있는 esg-app* 벌)을 지난다
  ( . scripts/lib/lock.sh && container_door "$R_PROJECT" ) || { echo "컨테이너 문을 못 지남"; return 1; }
  COMPOSE_PROJECT_NAME="$DECOY_PROJECT" DEPLOY_ROOT="$R_ROOT" APP_DIR="$WT" ENV_FILE="$R_ENV" UP_CURL_OPTS=-k deploy/up.sh --no-build
}
r_down() {  # 이 로컬 프로젝트만(서버 이름이면 거절)
  local p; p="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$R_ENV" | tail -n 1)"
  case "$p" in esg-demo|"") echo "down -v 거절: 프로젝트 ${p:-없음}"; return 1 ;; esac
  rdc down -v --remove-orphans
}
r_cleanup() { [ -n "$R_ENV" ] && [ -f "$R_ENV" ] && r_down >/dev/null 2>&1; [ -n "$R_ROOT" ] && rm -rf "$R_ROOT"; R_ROOT=""; R_ENV=""; }

r_second_make_env() {
  deploy/make-env.sh "$R_SITE" "$R_FILES" "$R_ROOT" >/dev/null 2>&1 && { echo "두 번째 make-env 가 거절하지 않음"; return 1; }
  echo "두 번째 make-env 거절"
}
r_smoke() {
  SMOKE_HTTP_PORT="$(r_http)" SMOKE_HTTPS_PORT="$(r_https)" SMOKE_RESOLVE_IP=127.0.0.1 SMOKE_CURL_OPTS=-k \
    SMOKE_ISSUER="Caddy Local Authority" deploy/smoke.sh "$R_SITE" "$R_FILES"
}
r_headers() {  # HSTS 있음 · Server 없음
  local h; h="$(rc -o /dev/null -D - "https://$R_SITE:$(r_https)/api/readyz" | tr -d '\r')"
  echo "$h" | grep -qi '^strict-transport-security: max-age=31536000' || { echo "HSTS 없음"; return 1; }
  echo "$h" | grep -qi '^server:' && { echo "Server 머리가 있음"; return 1; }
  echo "HSTS 있음 · Server 없음"
}
r_pem() {  # api-py 가 떴다 = EDK 공개키(\n 꼴)를 읽었다(user/apps.py 가 기동 때 읽고 틀리면 멈춘다)
  rdc exec -T api-py python manage.py shell -c "from esgapi.user.service.services.user import edk_public_key; edk_public_key(); print('EDK 공개키 읽힘')"
}

R_PASS=""; R_TOKEN=""; R_COMPANY=""
r_accounts() {  # 가짜 회사·계정, 로그인, /users/me
  R_PASS="$(openssl rand -hex 16)"
  rdc run --rm -T migrate-py python manage.py seed_company --name "DP1 Rehearsal Co" --business-licence-number 9990000001 --subdomain dp1r \
    || return 1
  printf '%s\n' "$R_PASS" | rdc exec -T api-py python manage.py create_user --company dp1r --username dp1-r --name "DP1 R" --password-stdin \
    || return 1
  local body code
  # 비밀번호는 표준 입력으로(--data @-) — 명령줄 인자·ps 에 0(리뷰 L4)
  body="$(printf '{"companySubdomain":"dp1r","username":"dp1-r","password":"%s"}' "$R_PASS" \
    | rc -X POST -H 'Content-Type: application/json' --data @- "https://$R_SITE:$(r_https)/api/auth/login")"
  R_TOKEN="$(printf '%s' "$body" | python3 -I -c 'import json,sys; print(json.load(sys.stdin).get("access",""))' 2>/dev/null)"
  [ -n "$R_TOKEN" ] || { echo "로그인 실패"; return 1; }
  # 첫 로그인은 비밀번호를 바꿔야 업무 경로가 열린다(is_initial) — 바꾼 뒤 받은 새 토큰을 쓴다
  local new_pass; new_pass="$(openssl rand -hex 16)"
  body="$(printf '{"currentPassword":"%s","newPassword":"%s"}' "$R_PASS" "$new_pass" \
    | rc -X POST -H "Authorization: Bearer $R_TOKEN" -H 'Content-Type: application/json' --data @- "https://$R_SITE:$(r_https)/api/users/me/password")"
  R_TOKEN="$(printf '%s' "$body" | python3 -I -c 'import json,sys; print(json.load(sys.stdin).get("access",""))' 2>/dev/null)"
  R_PASS="$new_pass"
  [ -n "$R_TOKEN" ] || { echo "첫 로그인 비밀번호 바꾸기 실패"; return 1; }
  echo "첫 로그인 비밀번호 바꿈 200"
  code="$(rc -o "$OUT/me.json" -w '%{http_code}' -H "Authorization: Bearer $R_TOKEN" "https://$R_SITE:$(r_https)/api/users/me")"
  R_COMPANY="$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["companyId"])' "$OUT/me.json" 2>/dev/null)"
  echo "로그인 200 · /api/users/me $code · 회사 id ${R_COMPANY:-?}"
  [ "$code" = 200 ]
}
R_DOC=""
r_upload() {  # 지어낸 6 MB 짜리 PDF 꼴 파일을 서명 PUT 으로 https://FILES:<포트> 에 → confirm
  local f size created url code
  f="$OUT/r-upload.pdf"
  { printf '%%PDF-1.4\n%% DP1 rehearsal filler\n'; head -c 6291456 /dev/zero | tr '\0' 'x'; printf '\n%%%%EOF\n'; } > "$f"
  size="$(wc -c < "$f" | tr -d ' ')"
  created="$(rc -X POST -H "Authorization: Bearer $R_TOKEN" -H 'Content-Type: application/json' \
    --data "{\"fileName\":\"dp1-rehearsal.pdf\",\"sizeBytes\":$size}" "https://$R_SITE:$(r_https)/api/documents")"
  printf '%s' "$created" | python3 -I -c 'import json,sys; d=json.load(sys.stdin); print("문서 만들기 →", d.get("error", {}).get("code") or "id " + str(d.get("document", {}).get("id")))' 
  url="$(printf '%s' "$created" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["upload"]["url"])' 2>/dev/null)"
  R_DOC="$(printf '%s' "$created" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["document"]["id"])' 2>/dev/null)"
  case "$url" in "https://$R_FILES:$(r_https)/"*) ;; *) echo "서명 주소의 호스트가 FILES 가 아님: ${url%%\?*}"; return 1 ;; esac
  code="$(rc -o /dev/null -w '%{http_code}' -X PUT -H "Origin: https://$R_SITE:$(r_https)" --data-binary "@$f" "$url")"
  echo "서명 PUT($size 바이트, Caddy max_size 60MB 를 지나) → $code"
  [ "$code" = 200 ] || return 1
  code="$(rc -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $R_TOKEN" "https://$R_SITE:$(r_https)/api/documents/$R_DOC/confirm")"
  echo "confirm → $code"
  [ "$code" = 200 ]
}
r_idle_db() {  # owner 로 psql 한 줄(로컬 리허설 DB 만)
  rdc exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "${POSTGRES_DB}_py" -At -c "$1"' sh "$1"
}
r_idle() {  # 일감이 끝나길 기다려 0 · processing 한 줄을 심으면 1(회사 id 찍음) · 되돌리면 0
  local i n code job
  for i in $(seq 1 60); do
    n="$(r_idle_db "SELECT count(*) FROM run_jobs WHERE status IN ('queued','processing')")"
    [ "$n" = 0 ] && break; sleep 3
  done
  COMPOSE_PROJECT_NAME="$DECOY_PROJECT" DEPLOY_ROOT="$R_ROOT" APP_DIR="$WT" ENV_FILE="$R_ENV" deploy/check-idle-runs.sh; code=$?
  [ "$code" = 0 ] || { echo "일감이 끝난 뒤 check-idle EXIT=$code"; return 1; }
  job="$(r_idle_db "SELECT max(id) FROM run_jobs")"
  r_idle_db "UPDATE run_jobs SET status = 'processing' WHERE id = $job" >/dev/null
  COMPOSE_PROJECT_NAME="$DECOY_PROJECT" DEPLOY_ROOT="$R_ROOT" APP_DIR="$WT" ENV_FILE="$R_ENV" deploy/check-idle-runs.sh > "$OUT/r-idle-planted.log"; code=$?
  r_idle_db "UPDATE run_jobs SET status = 'done' WHERE id = $job" >/dev/null
  cat "$OUT/r-idle-planted.log"
  [ "$code" = 1 ] || { echo "processing 한 줄을 세지 않음(EXIT=$code)"; return 1; }
  grep -q "run_jobs ${R_COMPANY:-x} 1" "$OUT/r-idle-planted.log" || { echo "회사별 줄이 아님"; return 1; }
  COMPOSE_PROJECT_NAME="$DECOY_PROJECT" DEPLOY_ROOT="$R_ROOT" APP_DIR="$WT" ENV_FILE="$R_ENV" deploy/check-idle-runs.sh >/dev/null || return 1
  echo "idle 0 → processing 심음 1 → 되돌림 0"
}
r_backup() {
  COMPOSE_PROJECT_NAME="$DECOY_PROJECT" DEPLOY_ROOT="$R_ROOT" APP_DIR="$WT" ENV_FILE="$R_ENV" deploy/backup-db.sh || return 1
  ls "$R_ROOT"/backup/db-*.dump >/dev/null
}
r_dumps() { ls -1 "$R_ROOT"/backup/db-*.dump 2>/dev/null | wc -l | tr -d ' '; }
r_relog() {  # 두 번째 up.sh: 계획 0 → 덤프 안 늘고, 교체 전 로그 폴더(700, 파일 600) · 최근 10개만(⑤-a·⑤-c)
  local before out d i seen
  mkdir -p "$R_ROOT/logs"
  for i in 01 02 03 04 05 06 07 08 09 10; do mkdir -p "$R_ROOT/logs/20000101T0000${i}Z"; done   # 옛 폴더 열 개를 심는다
  before="$(r_dumps)"; seen="$(ls -1d "$R_ROOT"/logs/2*/ | sort | tail -n 1)"
  out="$(r_up 2>&1)" || { printf '%s\n' "$out" | tail -n 20; return 1; }
  printf '%s\n' "$out" | grep -E "교체 전 로그|적용할 마이그레이션"
  printf '%s\n' "$out" | grep -q "적용할 마이그레이션 0" || { echo "계획 0 줄이 없음"; return 1; }
  [ "$(r_dumps)" = "$before" ] || { echo "계획 0 인데 덤프가 늘었다"; return 1; }
  d="$(ls -1d "$R_ROOT"/logs/2*/ | sort | tail -n 1)"
  [ "$d" != "$seen" ] || { echo "이번 up 의 로그 폴더가 새로 생기지 않음"; return 1; }
  d="${d%/}"
  [ -s "$d/compose.log.gz" ] && [ -s "$d/ps.txt" ] || { echo "로그 파일이 비었거나 없음: $d"; return 1; }
  gzip -t "$d/compose.log.gz" && [ "$(gzip -dc "$d/compose.log.gz" | wc -l | tr -d ' ')" -gt 0 ] || { echo "로그 gzip 이 깨졌거나 비었음"; return 1; }
  [ "$(stat -f '%Lp' "$d" 2>/dev/null || stat -c '%a' "$d")" = 700 ] || { echo "폴더 권한이 700 아님"; return 1; }
  for f in "$d"/*; do [ "$(stat -f '%Lp' "$f" 2>/dev/null || stat -c '%a' "$f")" = 600 ] || { echo "파일 권한이 600 아님: $f"; return 1; }; done
  [ "$(ls -1d "$R_ROOT"/logs/*/ | wc -l | tr -d ' ')" = 10 ] || { echo "로그 폴더가 10개가 아님"; return 1; }
  [ ! -e "$R_ROOT/logs/20000101T000001Z" ] || { echo "가장 옛 폴더가 남음"; return 1; }
  echo "로그 $(basename "$d") · 폴더 10개 · 덤프 그대로 $before"
}
r_migrate_backup() {  # runs 0004 를 되감은 뒤 up.sh → 「적용할 마이그레이션 1개」 · 덤프 +1 · 다시 [X](⑤-a·⑤-b 의 되감기 명령)
  local before out
  rdc run --rm -T migrate-py python manage.py migrate runs 0003 > "$OUT/r-unmigrate.log" 2>&1 || { tail -n 5 "$OUT/r-unmigrate.log"; return 1; }
  # 되감은 뒤 남은 수(0003 뒤의 runs 마이그레이션 — 0004 하나였다가 main 에서 0005·0006 이 더해짐, DM1 실측). 1 이상이어야
  local want
  want="$(rdc run --rm -T migrate-py python manage.py showmigrations runs 2>/dev/null | grep -c '\[ \]')"
  [ "${want:-0}" -ge 1 ] || { echo "되감은 뒤 남은 마이그레이션 0 — 빈 측정"; return 1; }
  before="$(r_dumps)"
  out="$(r_up 2>&1)" || { printf '%s\n' "$out" | tail -n 20; return 1; }
  printf '%s\n' "$out" | grep -E "적용할 마이그레이션|runs\.0004|덤프:"
  printf '%s\n' "$out" | grep -q "적용할 마이그레이션 ${want}개" || { echo "계획 ${want} 줄이 없음"; return 1; }
  [ "$(r_dumps)" = "$((before + 1))" ] || { echo "덤프가 늘지 않음($before → $(r_dumps))"; return 1; }
  # 덤프가 마이그레이션 앞이다 = 새 덤프의 django_migrations 에 0004 가 없다(검증 ⑤ 블로커)
  local newest n
  newest="$(ls -1t "$R_ROOT"/backup/db-*.dump | head -n 1)"
  rdc exec -T postgres pg_restore -a -t django_migrations -f - < "$newest" > "$OUT/r-dump-migrations.txt" 2>&1
  # 양성 대조: 같은 덤프에 0003 은 있다(덤프를 읽었다 — 0004 의 0 이 빈 측정이 아님)
  n="$(grep -c 0003_run_idempotency_key "$OUT/r-dump-migrations.txt" || true)"
  [ "${n:-0}" -ge 1 ] || { echo "새 덤프에서 0003 을 못 읽음 — 0004 셈이 빈 측정"; return 1; }
  n="$(grep -c 0004_run_launch_key "$OUT/r-dump-migrations.txt" || true)"
  [ "${n:-1}" = 0 ] || { echo "새 덤프에 0004 가 이미 있다 — 덤프가 마이그레이션 뒤"; return 1; }
  rdc run --rm -T migrate-py python manage.py showmigrations runs > "$OUT/r-showmigrations.log" 2>&1
  grep -q '\[X\] 0004_run_launch_key' "$OUT/r-showmigrations.log" || { echo "0004 가 다시 적용되지 않음"; grep 0004 "$OUT/r-showmigrations.log"; return 1; }
  echo "되감기 → up.sh 덤프 먼저($before → $(r_dumps)) → 0004 다시 [X]"
}

rehearsal_core() {  # 띄운 뒤의 단계들
  step "R1 make-env 두 번째 거절" r_second_make_env
  step "R2 smoke.sh 전부(자체 CA)" r_smoke
  step "R3 HSTS·Server 머리" r_headers
  step "R4 EDK 공개키(\\n 꼴) 읽힘" r_pem
  step "R5 seed_company·create_user·로그인·/users/me" r_accounts
  step "R6 서명 PUT(6 MB, https://FILES:포트) · confirm" r_upload
  step "R7 check-idle-runs 0 · processing 셈" r_idle
  step "R8 backup-db.sh 한 번" r_backup
  step "R10 두 번째 up.sh: 교체 전 로그 · 10개 · 계획 0 덤프 0" r_relog
  step "R11 마이그레이션 되감기 → up.sh 덤프 먼저" r_migrate_backup
}
rehearsal() {
  trap r_cleanup EXIT
  step "R0 make-env → 리허설 env" r_prepare || return
  step "R0 build(빌드 잠금)" r_build || return
  step "R0 up.sh --no-build(첫 배포 · readyz)" r_up || { rdc ps > "$OUT/r-ps.log" 2>&1; rdc logs --tail 80 > "$OUT/r-logs.log" 2>&1; return; }
  rehearsal_core
  rdc logs --no-color > "$OUT/r-compose.log" 2>&1
  step "R9 그 로컬 프로젝트만 down -v" r_down
  r_cleanup; trap - EXIT
}

# ══ D — 두 벌 리허설(밴드 DM1) ═══════════════════════════════════════
# 첫 벌 A = 워크트리 프로젝트(포트 +1·+2·+3, proxy +5·+6) · 둘째 벌 B = <프로젝트>-b(포트 +7·+8·+9, proxy 없음 — relay)
# 공유 네트워크는 <프로젝트>-edge(서버 이름 esg-edge 를 쓰지 않는다). B 의 PROXY_HTTPS_PORT 는 A 의 것(readyz 를 A 너머로).
D_B="${R_PROJECT}-b"; D_EDGE="${R_PROJECT}-edge"
D_SITE2=demo2.localhost D_FILES2=files-demo2.localhost
D_ROOT_B=""; D_ENV_B=""
adc() { rdc -f deploy/compose.edge-proxy.yaml "$@"; }
bdc() { env -i HOME="$HOME" PATH="$PATH" docker compose --project-directory "$WT" --env-file "$D_ENV_B" -f compose.yaml -f deploy/compose.prod.yaml -f deploy/compose.edge-relay.yaml "$@"; }
rc2() { curl -sS -k --max-time 20 --resolve "$D_SITE2:$(r_https):127.0.0.1" --resolve "$D_FILES2:$(r_https):127.0.0.1" "$@"; }
set_env_b() {
  local t; t="$(mktemp "$D_ROOT_B/shared/.e.XXXXXX")"
  awk -v k="$1" -v v="$2" 'BEGIN{d=0} index($0, k "=") == 1 { print k "=" v; d=1; next } { print } END { if (!d) print k "=" v }' "$D_ENV_B" > "$t"
  mv "$t" "$D_ENV_B"
}
readyz_code() {  # readyz_code <이름> — A proxy 너머
  curl -sS -k --max-time 10 -o /dev/null -w '%{http_code}' --resolve "$1:$(r_https):127.0.0.1" "https://$1:$(r_https)/api/readyz" 2>/dev/null
}
d_prepare() {
  r_prepare || return 1
  set_env EDGE_NETWORK "$D_EDGE"
  D_ROOT_B="$(mktemp -d "${TMPDIR:-/tmp}/dm1-b.XXXXXX")"; mkdir -p "$D_ROOT_B/shared"; chmod 700 "$D_ROOT_B/shared"
  D_ENV_B="$D_ROOT_B/shared/.env"
  MAKE_ENV_SET=demo2 deploy/make-env.sh "$D_SITE2" "$D_FILES2" "$D_ROOT_B" || return 1
  grep -q -x PROXY_ROLE=none "$D_ENV_B" || { echo "make-env demo2 가 PROXY_ROLE=none 을 안 채움"; return 1; }
  set_env_b COMPOSE_PROJECT_NAME "$D_B"
  set_env_b POSTGRES_PORT "$((PBASE + 7))"; set_env_b STORAGE_PORT "$((PBASE + 8))"; set_env_b API_PY_PORT "$((PBASE + 9))"
  set_env_b PROXY_HTTP_PORT "127.0.0.1:$(r_http)"; set_env_b PROXY_HTTPS_PORT "127.0.0.1:$(r_https)"
  set_env_b PROXY_PUBLIC_PORT_SUFFIX ":$(r_https)"
  set_env_b STORAGE_CORS_ORIGINS "https://$D_SITE2:$(r_https)"
  set_env_b LLM_RUN_MODE ""
  set_env_b EDGE_NETWORK "$D_EDGE"
  echo "A $R_PROJECT · B $D_B · 공유 네트워크 $D_EDGE · B 포트 $((PBASE + 7))~$((PBASE + 9))"
}
d_build() {
  r_build || return 1
  scripts/with-build-lock.sh env -i HOME="$HOME" PATH="$PATH" docker compose --project-directory "$WT" --env-file "$D_ENV_B" \
    -f compose.yaml -f deploy/compose.prod.yaml build
}
d_up_b() {
  ( . scripts/lib/lock.sh && container_door "$D_B" ) || { echo "컨테이너 문을 못 지남"; return 1; }
  COMPOSE_PROJECT_NAME="$DECOY_PROJECT" DEPLOY_ROOT="$D_ROOT_B" APP_DIR="$WT" ENV_FILE="$D_ENV_B" UP_CURL_OPTS=-k deploy/up.sh --no-build
}
norm_json() { python3 -I -c 'import json,sys; print(json.dumps(json.load(sys.stdin), sort_keys=True, indent=1))'; }
d_solo_same() {  # A 단독(DEMO2 빈 값): proxy 의 adapt JSON = BASE · 컨테이너 네트워크 = <A>_default 하나 · 공유 네트워크 없음
  local t bad=0 c nets
  t="$(mktemp -d)"
  git show "$BASE:deploy/Caddyfile" > "$t/base.caddy"
  dk run --rm -e "SITE_DOMAIN=$R_SITE" -e "FILES_DOMAIN=$R_FILES" -v "$t/base.caddy:/etc/caddy/Caddyfile:ro" "$CADDY_IMG" \
    caddy adapt --config /etc/caddy/Caddyfile 2>/dev/null | norm_json > "$t/base.json"
  rdc exec -T proxy caddy adapt --config /etc/caddy/Caddyfile 2>/dev/null | norm_json > "$t/live.json"
  if [ -s "$t/base.json" ] && diff -q "$t/base.json" "$t/live.json" >/dev/null; then echo "떠 있는 proxy adapt = BASE(diff 0)"
  else echo "  ✗ adapt 다름"; diff "$t/base.json" "$t/live.json" | head; bad=1; fi
  for c in $(rdc ps -q); do
    nets="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$c")"
    [ "$nets" = "${R_PROJECT}_default " ] || { echo "  ✗ $(docker inspect -f '{{.Name}}' "$c") 네트워크 $nets"; bad=1; }
  done
  echo "A 컨테이너 $(rdc ps -q | wc -l | tr -d ' ')개 전부 ${R_PROJECT}_default 하나"
  docker network inspect "$D_EDGE" >/dev/null 2>&1 && { echo "  ✗ 둘째 이름 없이 공유 네트워크가 생김"; bad=1; }
  rm -rf "$t"
  [ "$bad" = 0 ]
}
d_b_needs_proxy() {  # A 에 DEMO2 가 없을 때 B 를 올리면 「첫 벌 proxy 가 없다」로 멈춘다(B 컨테이너 0)
  local out code
  out="$(COMPOSE_PROJECT_NAME="$DECOY_PROJECT" DEPLOY_ROOT="$D_ROOT_B" APP_DIR="$WT" ENV_FILE="$D_ENV_B" deploy/up.sh --no-build 2>&1)"; code=$?
  printf '%s\n' "$out" | tail -n 1
  [ "$code" = 1 ] && printf '%s' "$out" | grep -q "첫 벌 proxy 가 없다" && [ -z "$(bdc ps -a -q 2>/dev/null)" ]
}
d_a_edge() {  # A 에 둘째 이름 두 칸 → up.sh(공유 네트워크 만들기 · proxy 다시 만들기)
  set_env DEMO2_SITE_DOMAIN "$D_SITE2"; set_env DEMO2_FILES_DOMAIN "$D_FILES2"
  r_up || return 1
  docker network inspect "$D_EDGE" >/dev/null 2>&1 || { echo "공유 네트워크가 없다"; return 1; }
  echo "A proxy 네트워크: $(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$(adc ps -q proxy)")"
  echo "B 이름(B 없음) readyz: $(readyz_code "$D_SITE2")(502 이어야 — Caddy 는 떠 있다)"
  [ "$(readyz_code "$D_SITE2")" = 502 ]
}
d_relay_only() {  # 공유 네트워크에 붙은 것 = A proxy · B relay 둘뿐(api-py·storage 이름이 새지 않음)
  local got want
  got="$(docker network inspect -f '{{range .Containers}}{{.Name}} {{end}}' "$D_EDGE" | tr ' ' '\n' | grep . | sort | tr '\n' ' ')"
  want="$(printf '%s\n%s\n' "${R_PROJECT}-proxy-1" "${D_B}-relay-1" | sort | tr '\n' ' ')"
  echo "공유 네트워크: $got"
  [ "$got" = "$want" ]
}
d_smoke2() {
  SMOKE_HTTP_PORT="$(r_http)" SMOKE_HTTPS_PORT="$(r_https)" SMOKE_RESOLVE_IP=127.0.0.1 SMOKE_CURL_OPTS=-k \
    SMOKE_ISSUER="Caddy Local Authority" deploy/smoke.sh "$D_SITE2" "$D_FILES2"
}
D_TOKEN=""; D_OBJ=""
d_account() {  # d_account <a|b> — 그 벌에 회사 하나 · 계정 · 서브도메인 없는 로그인 200 · 첫 비밀번호 바꿈 · 회사 수 1
  local which="$1" dcf curlf site sub pass body code n np lic
  if [ "$which" = a ]; then dcf=rdc; curlf=rc; site="$R_SITE"; sub=dm1a; lic=9990000021
  else dcf=bdc; curlf=rc2; site="$D_SITE2"; sub=dm1b; lic=9990000022; fi
  pass="$(openssl rand -hex 16)"
  $dcf run --rm -T migrate-py python manage.py seed_company --name "DM1 $which Co" --business-licence-number "$lic" --subdomain "$sub" >/dev/null || return 1
  printf '%s\n' "$pass" | $dcf exec -T api-py python manage.py create_user --company "$sub" --username "dm1-$which" --name "DM1 $which" --password-stdin >/dev/null || return 1
  n="$($dcf exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "${POSTGRES_DB}_py" -Atc "SELECT count(*) FROM company"')"
  # 웹은 서브도메인을 보내지 않는다(MARC-ENT-283) — 회사가 하나일 때만 찾는다. 그 꼴 그대로 로그인한다
  code="$(printf '{"username":"dm1-%s","password":"%s"}' "$which" "$pass" \
    | $curlf -o "$OUT/d-login-$which.json" -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data @- "https://$site:$(r_https)/api/auth/login")"
  D_TOKEN="$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1])).get("access",""))' "$OUT/d-login-$which.json" 2>/dev/null)"
  rm -f "$OUT/d-login-$which.json"
  np="$(openssl rand -hex 16)"
  body="$(printf '{"currentPassword":"%s","newPassword":"%s"}' "$pass" "$np" \
    | $curlf -X POST -H "Authorization: Bearer $D_TOKEN" -H 'Content-Type: application/json' --data @- "https://$site:$(r_https)/api/users/me/password")"
  D_TOKEN="$(printf '%s' "$body" | python3 -I -c 'import json,sys; print(json.load(sys.stdin).get("access",""))' 2>/dev/null)"
  echo "벌 $which: 회사 수 $n · 서브도메인 없는 로그인 $code · 비밀번호 바꿈 $([ -n "$D_TOKEN" ] && echo 200 || echo 실패)"
  [ "$n" = 1 ] && [ "$code" = 200 ] && [ -n "$D_TOKEN" ]
}
d_upload() {  # d_upload <a|b> — 서명 PUT 이 그 벌의 FILES 이름으로 가고 confirm 200. 올린 버킷/키는 D_OBJ
  local which="$1" curlf site files f url doc code cc size created
  if [ "$which" = a ]; then curlf=rc; site="$R_SITE"; files="$R_FILES"; else curlf=rc2; site="$D_SITE2"; files="$D_FILES2"; fi
  f="$OUT/d-upload-$which.pdf"
  { printf '%%PDF-1.4\n%% DM1 rehearsal filler %s\n' "$which"; head -c 1048576 /dev/zero | tr '\0' 'y'; printf '\n%%%%EOF\n'; } > "$f"
  size="$(wc -c < "$f" | tr -d ' ')"
  created="$($curlf -X POST -H "Authorization: Bearer $D_TOKEN" -H 'Content-Type: application/json' \
    --data "{\"fileName\":\"dm1-$which.pdf\",\"sizeBytes\":$size}" "https://$site:$(r_https)/api/documents")"
  url="$(printf '%s' "$created" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["upload"]["url"])' 2>/dev/null)"
  doc="$(printf '%s' "$created" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["document"]["id"])' 2>/dev/null)"
  case "$url" in "https://$files:$(r_https)/"*) ;; *) echo "서명 주소의 호스트가 $files 가 아님: ${url%%\?*}"; return 1 ;; esac
  code="$($curlf -o /dev/null -w '%{http_code}' -X PUT -H "Origin: https://$site:$(r_https)" --data-binary "@$f" "$url")"
  D_OBJ="${url#https://$files:$(r_https)/}"; D_OBJ="${D_OBJ%%\?*}"
  cc="$($curlf -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $D_TOKEN" "https://$site:$(r_https)/api/documents/$doc/confirm")"
  echo "벌 $which: 서명 PUT https://$files → $code · confirm $cc"
  [ "$code" = 200 ] && [ "$cc" = 200 ]
}
d_obj_in() { "$1" exec -T storage test -f "/data/$2"; }   # d_obj_in <rdc|bdc> <버킷/키>
d_isolation() {  # 둘째 이름으로 올린 것은 B 저장소에만 · 첫 이름으로 올린 것은 A 저장소에만
  local ka kb
  d_account a && d_upload a || return 1; ka="$D_OBJ"
  d_account b && d_upload b || return 1; kb="$D_OBJ"
  [ -n "$ka" ] && [ -n "$kb" ] || { echo "키가 비었다 — 빈 측정"; return 1; }
  if d_obj_in rdc "$ka" && ! d_obj_in bdc "$ka" && d_obj_in bdc "$kb" && ! d_obj_in rdc "$kb"; then
    echo "A 키는 A 저장소에만 · B 키는 B 저장소에만"
  else echo "저장소가 섞였거나 못 찾음"; return 1; fi
}
d_b_ops() {  # B 뿌리로 check-idle-runs · backup-db(덤프가 B 뿌리에만). D9 의 confirm 이 띄운 일감이 끝나길 먼저 기다린다(R7 과 같음)
  local i n
  for i in $(seq 1 60); do
    n="$(bdc exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "${POSTGRES_DB}_py" -Atc "SELECT count(*) FROM run_jobs WHERE status IN ('"'"'queued'"'"','"'"'processing'"'"')"')"
    [ "$n" = 0 ] && break; sleep 3
  done
  echo "B 일감 남음 ${n:-?}(기다린 뒤)"
  COMPOSE_PROJECT_NAME="$DECOY_PROJECT" DEPLOY_ROOT="$D_ROOT_B" APP_DIR="$WT" ENV_FILE="$D_ENV_B" deploy/check-idle-runs.sh || return 1
  COMPOSE_PROJECT_NAME="$DECOY_PROJECT" DEPLOY_ROOT="$D_ROOT_B" APP_DIR="$WT" ENV_FILE="$D_ENV_B" deploy/backup-db.sh || return 1
  ls "$D_ROOT_B"/backup/db-*.dump >/dev/null 2>&1 || { echo "B 뿌리에 덤프 없음"; return 1; }
  ls "$R_ROOT"/backup/db-*.dump >/dev/null 2>&1 && { echo "A 뿌리에 덤프가 생김"; return 1; }
  echo "덤프는 B 뿌리에만"
}
d_stats() {  # 쉰 상태 메모리(서버 어림의 근거)
  sleep 20
  # shellcheck disable=SC2046
  docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' $(rdc ps -q) $(bdc ps -q) > "$OUT/d-stats.txt" || return 1
  python3 -I - "$OUT/d-stats.txt" "$R_PROJECT" "$D_B" <<'PYD'
import re, sys
u = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "kB": 1000, "MB": 1000**2, "GB": 1000**3}
tot = {}
for line in open(sys.argv[1]):
    name, use = line.split()[0], line.split()[1]
    m = re.match(r"([0-9.]+)([A-Za-z]+)", use); v = float(m.group(1)) * u.get(m.group(2), 1)
    k = sys.argv[3] if name.startswith(sys.argv[3] + "-") else sys.argv[2]
    tot[k] = tot.get(k, 0) + v
    print(f"  {name} {use}")
for k, v in tot.items(): print(f"합 {k}: {v / 1024**2:.0f} MiB")
print(f"두 벌 합: {sum(tot.values()) / 1024**2:.0f} MiB")
PYD
}
d_stop_b() {  # B stop → A readyz 200 그대로 · B 이름 502
  bdc stop >/dev/null 2>&1 || return 1
  local a b; a="$(readyz_code "$R_SITE")"; b="$(readyz_code "$D_SITE2")"
  echo "B stop 뒤: A readyz $a · B readyz $b"
  [ "$a" = 200 ] && [ "$b" = 502 ]
}
d_reup_a() {  # B start → A up.sh(proxy 다시 만들기) → 두 이름 다시 200
  local i b
  bdc start >/dev/null 2>&1 || return 1
  for i in $(seq 1 40); do b="$(readyz_code "$D_SITE2")"; [ "$b" = 200 ] && break; sleep 3; done
  echo "B start 뒤 B readyz $b"
  r_up > "$OUT/d-reup-a.log" 2>&1 || { tail -n 5 "$OUT/d-reup-a.log"; return 1; }
  grep -q "proxy 너머 /api/readyz: 200" "$OUT/d-reup-a.log" || return 1
  b="$(readyz_code "$D_SITE2")"
  echo "A up.sh 다시(proxy 다시 만들기) 뒤: A 200 · B readyz $b"
  [ "$b" = 200 ] && d_relay_only
}
d_down() {
  local p
  if [ -n "$D_ENV_B" ] && [ -f "$D_ENV_B" ]; then
    p="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$D_ENV_B" | tail -n 1)"
    case "$p" in esg-demo|esg-demo2|"") echo "down -v 거절: ${p:-없음}"; return 1 ;; esac
    bdc down -v --remove-orphans
  fi
  if [ -n "$R_ENV" ] && [ -f "$R_ENV" ]; then
    if grep -q '^DEMO2_SITE_DOMAIN=.' "$R_ENV"; then adc down -v --remove-orphans; else r_down; fi
  fi
  if docker network inspect "$D_EDGE" >/dev/null 2>&1; then docker network rm "$D_EDGE" >/dev/null; fi
  echo "A·B down -v · 네트워크 $D_EDGE 지움"
}
d_cleanup() {
  d_down >/dev/null 2>&1
  [ -n "$R_ROOT" ] && rm -rf "$R_ROOT"; [ -n "$D_ROOT_B" ] && rm -rf "$D_ROOT_B"
  R_ROOT=""; R_ENV=""; D_ROOT_B=""; D_ENV_B=""
}
demo2() {
  case "$D_EDGE" in esg-edge|-edge) echo "공유 네트워크 이름이 서버 이름이거나 비었다 — 거절"; return 1 ;; esac
  trap d_cleanup EXIT
  step "D0 make-env 두 벌(B 는 MAKE_ENV_SET=demo2)" d_prepare || return
  step "D0 build 두 벌(빌드 잠금)" d_build || return
  step "D1 A 단독 up.sh(둘째 이름 없음)" r_up || return
  step "D2 A 단독: adapt = BASE · 네트워크 default 하나 · 공유 네트워크 없음" d_solo_same
  step "D3 A 에 둘째 이름 없을 때 B up → 「첫 벌 proxy 가 없다」 멈춤" d_b_needs_proxy
  step "D4 A 에 둘째 이름 두 칸 → up.sh(공유 네트워크·proxy 다시) · B 없을 때 B 이름 502" d_a_edge || return
  step "D5 B up.sh(proxy 없음 · relay · readyz 는 A 너머)" d_up_b || { bdc ps > "$OUT/d-b-ps.log" 2>&1; bdc logs --tail 80 > "$OUT/d-b-logs.log" 2>&1; return; }
  step "D6 공유 네트워크 = A proxy · B relay 뿐" d_relay_only
  step "D7 smoke.sh A 이름 쌍" r_smoke
  step "D8 smoke.sh B 이름 쌍(거르기 403·CORS·다른 Host)" d_smoke2
  step "D9 두 벌 회사 하나씩 · 로그인 200 · 서명 PUT 이 자기 저장소로" d_isolation
  step "D10 B 뿌리로 check-idle · backup-db" d_b_ops
  step "D11 쉰 상태 메모리" d_stats
  step "D12 B stop → A 200 · B 502" d_stop_b
  step "D13 B start → A up.sh 다시 → B 200" d_reup_a
  rdc logs --no-color > "$OUT/d-a-compose.log" 2>&1; bdc logs --no-color > "$OUT/d-b-compose.log" 2>&1
  step "D14 두 프로젝트만 down -v · 네트워크 지움" d_down
  d_cleanup; trap - EXIT
}

# ══ 심은 파손 ════════════════════════════════════════════════════════
fingerprint() { cat $ALLOWED 2>/dev/null | shasum | cut -c1-12; }
PLANT_OK=0 PLANT_ALL=0
plant() {  # plant <번호> <파일> <빨개질 함수>   — 바꿈은 표준 입력의 파이썬(s = 글 → s 를 바꿈)
  local id="$1" file="$2" fn="$3" saved code
  saved="$OUT/plant-$id.orig"; cp "$file" "$saved"
  python3 -I -c 'import sys
p = sys.argv[1]; s = open(p).read(); t = s
exec(sys.stdin.read())
assert s != t, "바꿈 0"
open(p, "w").write(s)' "$file" || { echo "  ✗ $id 심기 실패"; PLANT_ALL=$((PLANT_ALL + 1)); return; }
  "$fn" > "$OUT/plant-$id.log" 2>&1; code=$?
  cat "$saved" > "$file"   # 같은 inode 로 되돌린다(컨테이너가 묶은 파일)
  PLANT_ALL=$((PLANT_ALL + 1))
  if [ "$code" != 0 ]; then PLANT_OK=$((PLANT_OK + 1)); echo "  빨강 $id ← $fn"; else echo "  ✗ 초록 그대로 $id ← $fn"; fi
}
plant_fn() {  # 파일을 안 바꾸고 함수 안에서 리허설 env 를 바꾸는 파손(P5)
  local id="$1" fn="$2" code
  "$fn" > "$OUT/plant-$id.log" 2>&1; code=$?
  PLANT_ALL=$((PLANT_ALL + 1))
  if [ "$code" != 0 ]; then PLANT_OK=$((PLANT_OK + 1)); echo "  빨강 $id ← $fn"; else echo "  ✗ 초록 그대로 $id ← $fn"; fi
}
p3_get() {  # Caddyfile 바꿈을 proxy 에 다시 읽힌 뒤 GET 403 단언
  rdc exec -T proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
  local code; code="$(rc -o "$OUT/p3-body" -w '%{http_code}' "https://$R_FILES:$(r_https)/esg-documents/x")"
  echo "GET → $code · 저장소 본문(<Error) $(grep -c '<Error' "$OUT/p3-body")"
  [ "$code" = 403 ] && ! grep -q '<Error' "$OUT/p3-body"
}
p_reload_smoke() {  # Caddyfile 을 다시 읽힌 뒤 smoke 전부
  rdc exec -T proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
  r_smoke
}
p9_http_storage() {  # http 의 끝 블록이 저장소로 가면 smoke 가 빨개야
  rdc exec -T proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
  r_smoke
}
p5_cors_star() {  # STORAGE_CORS_ORIGINS=* 면 storage-cors 가 실패해 up 이 실패해야 — 성공하면 초록(파손 못 잡음)
  set_env STORAGE_CORS_ORIGINS '*'
  rdc up -d --wait > "$OUT/p5-up.log" 2>&1; local code=$?
  set_env STORAGE_CORS_ORIGINS "https://$R_SITE:$(r_https)"
  rdc up -d --wait > "$OUT/p5-restore.log" 2>&1 || echo "  되돌린 up 실패"
  echo "* 로 up EXIT=$code"; [ "$code" = 0 ]
}
p8_boot() {  # base64 꼴(/ + =) 비밀번호로 처음부터 띄우면 실패해야 — 성공하면 초록
  r_prepare || return 0
  r_up; local code=$?
  rdc ps -a --format '{{.Service}} {{.State}} {{.ExitCode}}' 2>/dev/null
  r_down > /dev/null 2>&1; rm -rf "$R_ROOT"; R_ROOT=""; R_ENV=""
  echo "base64 꼴 비밀번호로 up EXIT=$code"; [ "$code" = 0 ]
}
planted() {
  local before after
  before="$(fingerprint)"
  echo "── 정적(컨테이너는 caddy 한 번짜리뿐)"
  plant P1 deploy/compose.prod.yaml s2 <<'PY'
worker = s.index("  worker-py:")
line = "      S3_PUBLIC_ENDPOINT: https://${FILES_DOMAIN:?FILES_DOMAIN 이 없다}${PROXY_PUBLIC_PORT_SUFFIX:-}\n"
i = s.index(line, worker)
s = s[:i] + s[i + len(line):]
PY
  plant P2 deploy/compose.prod.yaml s2 <<'PY'
s = s.replace("  postgres:\n", '  postgres:\n    ports: ["5432:5432"]\n', 1)
PY
  plant P4 deploy/env.prod.example planted_s4_s5 <<'PY'
s = s.replace("\nLLM_OPENAI_API_KEY=\n", "\nLLM_OPENAI_API_KEY=sk-" + "Q" * 24 + "\n")
PY
  plant P6 deploy/make-env.sh s6 <<'PY'
s = s.replace('if [ -e "$target" ]; then', "if false; then").replace('ln "$tmp" "$target" ||', 'mv "$tmp" "$target" ||')
PY
  plant P10 deploy/make-env.sh s6 <<'PY'
s = s.replace('chmod 600 "$target"\n', 'chmod 600 "$target"\ngrep "^SESSION_SECRET=" "$target"\n', 1)
PY
  plant P17 deploy/compose.prod.yaml s2 <<'PY'
worker = s.index("  worker-py:")
line = "      INVENTORY_SCOPE3_RUNS_ENABLED: ${INVENTORY_SCOPE3_RUNS_ENABLED:-false}\n"
i = s.index(line, worker)
s = s[:i] + s[i + len(line):]
PY
  plant P18 deploy/compose.prod.yaml s2 <<'PY'
s = s.replace("${INVENTORY_SCOPE3_RUNS_ENABLED:-false}", "${INVENTORY_SCOPE3_RUNS_ENABLED:-true}", 1)
PY
  echo "── 리허설 안(컨테이너)"
  trap r_cleanup EXIT
  # 이미지는 한 번(빌드 잠금) — env 는 이름·포트만 쓰고 바로 버린다
  { r_prepare && r_build; } > "$OUT/planted-build.log" 2>&1 || { echo "  ✗ 빌드 실패"; r_cleanup; trap - EXIT; return 1; }
  rm -rf "$R_ROOT"; R_ROOT=""; R_ENV=""
  plant P8 deploy/make-env.sh p8_boot <<'PY'
s = s.replace('V_POSTGRES_OWNER_PASSWORD="$(secret)"', 'V_POSTGRES_OWNER_PASSWORD="a/b+c=$(openssl rand -base64 24)"')
s = s.replace('V_APP_DB_PASSWORD="$(secret)"', 'V_APP_DB_PASSWORD="a/b+c=$(openssl rand -base64 24)"')
PY
  { r_prepare && r_up && r_accounts && r_upload; } > "$OUT/planted-up.log" 2>&1 \
    || { echo "  ✗ 리허설이 뜨지 않아 P3·P5·P7 을 못 잼"; PLANT_ALL=$((PLANT_ALL + 3)); r_cleanup; trap - EXIT; return 1; }
  plant P3 deploy/Caddyfile p3_get <<'PY'
s = s.replace("\t@not_upload not method PUT OPTIONS\n\trespond @not_upload 403\n", "")
PY
  rdc exec -T proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile > /dev/null 2>&1
  plant P9 deploy/Caddyfile p9_http_storage <<'PY'
s = s + "\n:80 {\n\treverse_proxy storage:7070\n}\n"
PY
  rdc exec -T proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile > /dev/null 2>&1
  plant_fn P5 p5_cors_star
  plant P7 deploy/check-idle-runs.sh r_idle <<'PY'
s = s.replace("FROM run_jobs WHERE status IN ('queued','processing')", "FROM run_jobs WHERE status IN ('queued')")
PY
  plant P11 deploy/Caddyfile p_reload_smoke <<'PY'
s = s.replace("\t@copy header X-Amz-Copy-Source *\n\trespond @copy 403\n", "")
PY
  plant P12 deploy/Caddyfile p_reload_smoke <<'PY'
s = s.replace("\t@unsigned_put {\n\t\tmethod PUT\n\t\tnot query X-Amz-Signature=*\n\t}\n\trespond @unsigned_put 403\n", "")
PY
  rdc exec -T proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile > /dev/null 2>&1
  plant P13 deploy/check-idle-runs.sh r_idle <<'PY'
s = s.replace('docker compose -p "$project" --env-file', 'docker compose --env-file')
PY
  plant P14 deploy/up.sh r_migrate_backup <<'PY'
s = s.replace('"$here/backup-db.sh" || {', 'true || {')
PY
  plant P15 deploy/up.sh r_relog <<'PY'
s = s.replace('if [ -n "$("${compose[@]}" ps -a -q 2>/dev/null)" ]; then', 'if false; then')
PY
  plant P16 deploy/up.sh r_migrate_backup <<'PY'
b = '    "$here/backup-db.sh" || { echo "멈춤: 마이그레이션 전 덤프 실패 — 올리지 않는다" >&2; exit 1; }\n'
i = s.index(b); s = s[:i] + s[i + len(b):]
m = s.index("\n", s.index('run --rm --no-deps -T migrate-py ||')) + 1
s = s[:m] + b + s[m:]
PY
  r_cleanup; trap - EXIT
  after="$(fingerprint)"
  echo "PLANTED=$PLANT_OK/$PLANT_ALL"
  if [ "$before" = "$after" ]; then echo "FINGERPRINT=same"; else echo "FINGERPRINT=changed"; fi
  [ "$PLANT_OK" = "$PLANT_ALL" ] && [ "$before" = "$after" ]
}
planted_s4_s5() { s4 && s5; }
planted_dm1() {  # 밴드 DM1 — 정적(컨테이너는 caddy 한 번짜리뿐)
  local before after
  before="$(fingerprint)"
  plant P19 deploy/Caddyfile.demo2 s9 <<'PYP'
s = s.replace("\timport files demo2-edge:7070\n", "\treverse_proxy demo2-edge:7070\n")
PYP
  plant P20 deploy/Caddyfile s9 <<'PYP'
s = s.replace("\t@unsigned_put {\n\t\tmethod PUT\n\t\tnot query X-Amz-Signature=*\n\t}\n\trespond @unsigned_put 403\n", "")
PYP
  plant P21 deploy/up.sh s10 <<'PYP'
s = s.replace('if [ "$root" = /srv/esg-demo2 ] && [ "$project" != esg-demo2 ]; then', 'if false; then')
PYP
  plant P22 deploy/compose.edge-relay.yaml s10 <<'PYP'
s = s.replace("\nnetworks:\n  edge:", "\n  api-py:\n    networks: [default, edge]\n\nnetworks:\n  edge:")
PYP
  plant P23 deploy/up.sh s10 <<'PYP'
s = s.replace('if [ -z "$(docker ps -q --filter "network=$edge_net"', 'if [ -n "" ] && [ -z "$(docker ps -q --filter "network=$edge_net"')
PYP
  plant P24 deploy/make-env.sh s10 <<'PYP'
s = s.replace("COMPOSE_PROJECT_NAME=esg-demo2 PROXY_ROLE=none", "COMPOSE_PROJECT_NAME=esg-demo2", 1)
PYP
  plant P25 deploy/backup-db.sh s10 <<'PYP'
s = s.replace('root="${DEPLOY_ROOT:-$default_root}"', 'root="${DEPLOY_ROOT:-/srv/esg-demo}"')
PYP
  plant P26 deploy/make-env.sh s10 <<'PYP'
s = s.replace("POSTGRES_PORT=25432 STORAGE_PORT=29000 API_PY_PORT=28081", "", 1)
PYP
  after="$(fingerprint)"
  echo "PLANTED=$PLANT_OK/$PLANT_ALL"
  if [ "$before" = "$after" ]; then echo "FINGERPRINT=same"; else echo "FINGERPRINT=changed"; fi
  [ "$PLANT_OK" = "$PLANT_ALL" ] && [ "$before" = "$after" ]
}

case "$MODE" in
  static)
    step "S1 렌더 · SITE_DOMAIN 빈 값 멈춤" s1
    step "S2 렌더 단언(공개 포트·같은 값·키 목록·서비스)" s2
    step "S3 caddy validate · fmt" s3
    step "S4 더한 줄 키 꼴 0" s4
    step "S5 틀의 비밀 이름 빈 값" s5
    step "S6 문법 · make-env · put-llm-key · ship" s6
    step "S7 IAM 정책 꼴" s7
    step "S8 경계(1-1 목록)" s8
    step "S9 (DM1) 둘째 이름 없음 adapt = BASE · 두 FILES 거르기 · demo2·relay fmt" s9
    step "S10 (DM1) 가드 · 기본 뿌리 · 덧붙임 렌더 · make-env 둘째 벌 · cron" s10
    step "F  scripts/verify.sh --fast" fast_gate
    ;;
  rehearsal) rehearsal ;;
  demo2) demo2 ;;
  planted-dm1)
    planted_dm1; code=$?
    echo "EXIT=$code  # planted-dm1"
    [ "$code" = 0 ] || FAILS=$((FAILS + 1))
    ;;
  planted)
    planted; code=$?
    echo "EXIT=$code  # planted"
    [ "$code" = 0 ] || FAILS=$((FAILS + 1))
    ;;
  *) echo "사용: deploy/section4-DP1.sh [static|rehearsal|planted|demo2|planted-dm1]" >&2; exit 2 ;;
esac
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
