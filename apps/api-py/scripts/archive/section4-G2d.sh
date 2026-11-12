#!/usr/bin/env bash
# 밴드 G2d(MARC-TICK-240: 판별 대상 단어를 AI 설정 판에 — 0006·POST terms·판 꼴 @3·웹 따라잡기 + 실행이 판의 켠 단어로
# 빈도를 셈)의 §4 자기검증(발주서 band-handoffs/G2d-order.md §4 + 처분 G2d-order-review-1·2). 틀은 section4-AS3a-2.sh 그대로다.
#   사용: apps/api-py/scripts/section4-G2d.sh --commit <2|3> [--with-containers] [--step <n>]
#   --with-containers 면 단계 9(업무·보안·③ 통합)와 10 의 컨테이너 층을 돈다 — 아니면 「안 돌림」(EXIT=1 로 센다).
#   단계 5 는 골든(바닥)과 함께 ②-0 기준물(g2d-baseline — ②-0 커밋 값)의 sha 와 g2d_baseline.py --check 를 본다(처분 2 B1·N7).
#   단계 12 는 makemigrations --check(검증 1 권고 r1 — 발주서 §4-7)와 <기준> 뒤 새 마이그레이션이 0006 하나인지 본다.
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 와 apps/web/scripts/verify.sh — 전량은 감독 몫). AI 공급사 호출 0.
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)만. 문(현황판 MARC-TICK-76 2절, MARC-ENT-241·292):
#   띄우기 전 기존 esg-app* 벌 < 3(자기 밖 ≤ 2), build 중 0, free ≥ 20%, 1분 부하 < 24 — 60초 간격 최대 30분. build 는
#   scripts/with-build-lock.sh 로만. 띄운 벌은 내리지 않는다(러너가 끝에 down -v).
# 환경 변수: G2D_OUT(로그 자리, 기본 워크트리 곁의 G2d.out — 심은 파손에도 넘긴다), G2D_FORBIDDEN(실재 기업명 낱말
#   파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
G="$E/greenwash"
C="$E/core"
OUT="${G2D_OUT:-$ROOT/../G2d.out}"
FORBIDDEN="${G2D_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(1a45b1b)에서 잰 수 — 그 트리를 git archive 로 풀어 --collect-only. 순수 = pytest esgapi/greenwash esgapi/core
# -m "not django_db", 업무 = test-business.sh esgapi/{greenwash,core,config}(③ 은 runs 더함 — 늘기만 본다).
# 기대 ②: 순수 +29(test_terms_e0) · 업무 +33(test_ai_settings_terms 31·test_migrations_0006 2).
# 기대 ③: 순수 +30(test_binding_e0_terms) · 업무(runs 더한 기준 720) +33(②) +4(test_binding_e0_terms_runs).
BASE_PURE=2353 BASE_BUSINESS=521
WANT_PURE_2=2382 WANT_BUSINESS_2=554
BASE_BUSINESS_3=720 WANT_PURE_3=2412 WANT_BUSINESS_3=757
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <2|3> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 2) WANT_PURE=$WANT_PURE_2 WANT_BUSINESS=$WANT_BUSINESS_2 ;;
  3) WANT_PURE=$WANT_PURE_3 WANT_BUSINESS=$WANT_BUSINESS_3 BASE_BUSINESS=$BASE_BUSINESS_3 ;;
  *) echo "--commit 2 또는 3" >&2; exit 2 ;; esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 G2d §4 커밋 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…> — EXIT 줄에 걸린 초
  local n="$1" what="$2" start; shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  echo "── [$n] $what"
  start=$(date +%s)
  "$@"
  local code=$?
  echo "[$n] $what EXIT=$code $(( $(date +%s) - start ))s"
  [ "$code" -eq 0 ] || FAILS=$((FAILS + 1))
}

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

env_value() { sed -n "s/^$1=//p" .env | tail -1; }

changed() {  # <기준> 이후 바뀐 파일(작업 트리 — 스테이징·커밋 포함) + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-2(그린워싱 서버 — 처분 2 B1·N6 의 더한 경로 포함) + §1-3(그린워싱 웹) + §1-4(남의 경로 — 22·d9 허락, MARC-ISSUE-246
# 노트) — 닫힌 목록
W=apps/web
ALLOWED="^$G/contracts/(ai_setting_shapes|terms_shapes|shapes|__init__)\.py\$
^$G/models\.py\$
^$G/migrations/0006_ai_settings_terms\.py\$
^$G/flows/(terms_e0|colab_e0|binding_e0)\.py\$
^$G/outputs/xlsx\.py\$
^$G/service/(selectors|services|actions|apis)/ai_settings\.py\$
^$G/README\.md\$
^$G/tests/
^$A/scripts/(section4|planted-breaks)-G2d\.sh\$
^$A/scripts/g2d_baseline\.py\$
^$W/src/entities/greenwash-setting/model/(setting|setting\.test|index)\.ts\$
^$W/src/entities/greenwash-setting/api/(server|server\.test|testing)\.ts\$
^$W/src/app/admin/ai-setting-modules(\.test)?\.ts\$
^$W/e2e/(ai-settings|greenwash-server)\.ts\$
^$W/e2e/admin\.spec\.ts\$
^$W/src/entities/greenwash/model/result\.ts\$
^$W/src/entities/greenwash/api/contract/(result|contract\.test)\.ts\$
^$E/config/tests/test_request_schemas_reject_bool\.py\$
^$A/tests/security/test_ai_settings\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$"

# §1-4 「0줄」 + §1-5 0바이트(골든·기준물은 단계 5). 표 밖 config/** 는 단계 1 의 닫힌 목록이 막는다.
ZERO="$E/runs $E/core $A/.importlinter $E/config/api.py $W/src/shared $W/src/widgets $W/src/pages $A/uv.lock
$W/src/entities/ai-setting $W/src/entities/greenwash $A/tests_integration $G/engines $G/prompts $G/tests/data/golden
$G/tests/data/gw1-ast-sha256.txt $G/migrations/0001_initial.py $G/migrations/0002_ai_settings.py
$G/migrations/0003_ai_settings_model_settings.py $G/migrations/0004_review_mark_edits.py $G/migrations/0005_ai_settings_prompts.py
$G/flows/criteria_e0.py $G/flows/rewrite_r1.py $G/flows/registration.py $G/tests/flows/support.py"

s1() {
  local all outside pattern missing=0 p n bad
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  # ③ 결과 꼴 terms? 의 웹 거울 셋(그린워싱 감독 a2 허락 — 손 꼴·zod 거울·거울 시험)은 0줄 자리 entities/greenwash 의 예외
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u \
    | grep -v -E "^$W/src/entities/greenwash/(model/result|api/contract/(result|contract\.test))\.ts\$")"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ "$outside" -eq 0 ] && [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

SHARED="$E/config/tests/test_request_schemas_reject_bool.py $A/tests/security/test_ai_settings.py"
WEB_SHARED="$W/src/app/admin/ai-setting-modules.ts $W/src/app/admin/ai-setting-modules.test.ts $W/e2e/admin.spec.ts"

s2() {  # 22 허락 줄(§1-4, <기준> 줄 번호) 밖의 - 줄 = bad_minus. 웹 셋(d9 허락 — 복제 줄·그 시험, 8e 허락 — admin.spec 키 한 줄·단언 한 문장)은 numstat·- 원문만. generated 는 단계 6.
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $SHARED $WEB_SHARED | sed 's/^/  /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $WEB_SHARED | grep -E '^-[^-]' | sed 's/^/    웹 - /'
  # shellcheck disable=SC2086
  echo "  공통 경로 diff sha256(22·d9 에) $(git diff "$BASE" -- $SHARED | shasum -a 256 | cut -c1-12) · 웹 $(git diff "$BASE" -- $WEB_SHARED | shasum -a 256 | cut -c1-12)"
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $SHARED | python3 -c '
import re, sys
GRANTED = {
    "test_request_schemas_reject_bool.py": [(34, 34)],
    "security/test_ai_settings.py": [],
}
bad = total = 0
file = None
line = 0
for raw in sys.stdin:
    text = raw.rstrip("\n")
    if text.startswith("diff --git"):
        file = text.split(" b/", 1)[1]
    elif text.startswith("@@"):
        line = int(re.match(r"@@ -(\d+)", text).group(1))
    elif text.startswith("-") and not text.startswith("---"):
        total += 1
        ranges = next(v for k, v in GRANTED.items() if file.endswith(k))
        print(f"    - {file}:{line}: {text[1:]}")
        if not any(a <= line <= b for a, b in ranges):
            bad += 1
            print("      ★ 허락 줄 밖")
        line += 1
print(f"  - 줄 {total} · bad_minus={bad}")
sys.exit(1 if bad else 0)
'
}

s3() { (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}"); }

s4() {
  local log="$OUT/s4-pytest.log" code total
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/greenwash \
    esgapi/core -m "not django_db") > "$log" 2>&1
  code=$?
  total="$(grep -E '^[0-9]+ passed' "$log" | sed -E 's/^([0-9]+) passed.*/\1/')"
  tail -1 "$log" | sed 's/^/  /'
  echo "  순수 기준 $BASE_PURE → 지금 ${total:-?}(기대 ${WANT_PURE:-늘기만})"
  [ "$code" -eq 0 ] && [ "${total:-0}" -ge "${WANT_PURE:-$BASE_PURE}" ]
}

s5() {
  local p bad=0 n=0 a b
  for p in $(git ls-tree -r --name-only "$BASE" -- "$G/tests/data/golden"); do
    a="$(git show "$BASE:$p" | shasum -a 256 | cut -d' ' -f1)"
    b="$(shasum -a 256 "$p" | cut -d' ' -f1)"
    n=$((n + 1))
    [ "$a" = "$b" ] || { echo "  ★ $p"; bad=$((bad + 1)); }
  done
  echo "  골든 $n 파일 · 다름 $bad"
  [ "$n" -gt 0 ] && [ "$bad" = 0 ] || return 1
  local made m=0 nb=0 check
  made="$(git log --format=%H --diff-filter=A "$BASE..HEAD" -- "$G/tests/data/g2d-baseline/fixtures.json" | tail -1)"
  [ -n "$made" ] || { echo "  ★ ②-0 커밋을 못 찾음"; return 1; }
  for p in $(git ls-tree -r --name-only "$made" -- "$G/tests/data/g2d-baseline"); do
    a="$(git show "$made:$p" | shasum -a 256 | cut -d' ' -f1)"
    b="$(shasum -a 256 "$p" | cut -d' ' -f1)"
    nb=$((nb + 1))
    [ "$a" = "$b" ] || { echo "  ★ $p"; m=$((m + 1)); }
  done
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python scripts/g2d_baseline.py --check) > "$OUT/s5-baseline.log" 2>&1
  check=$?
  echo "  기준물(②-0 ${made:0:7}) $nb 파일 · 다름 $m · 다시 지어 대조 $(tail -1 "$OUT/s5-baseline.log") EXIT=$check"
  [ "$nb" -gt 0 ] && [ "$m" = 0 ] && [ "$check" = 0 ]
}

s6() {  # 그린워싱 고정 스키마 셋 + 다시 뽑은 openapi 가 generated/ 와 바이트 같고, sha 파일이 맞고, <기준> 견줌이 허용 차이 안
  local d="$OUT/s6-generated" code sha
  mkdir -p "$d"
  (cd "$A" && uv run --frozen python -c '
import json, sys
from pathlib import Path
from esgapi.greenwash.contracts import ai_setting_shapes as s
pinned = Path("esgapi/greenwash/tests/data/flow-shapes/ai-setting")
shapes = {**s.LIST_SHAPES, **s.SETTING_SHAPES, **s.DEFAULT_SHAPES}
names = sorted(p.name for p in pinned.iterdir())
bad = [k for k, a in shapes.items()
       if (pinned / f"{k}.schema.json").read_bytes()
       != (json.dumps(a.json_schema(), ensure_ascii=False, indent=2) + "\n").encode()]
print(f"  고정 스키마 {names} · 다름 {bad}")
sys.exit(0 if names == sorted(f"{k}.schema.json" for k in shapes) and not bad else 1)
') || return 1
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json" || return 1
  sha="$(shasum -a 256 "$A/generated/openapi.json" | cut -d' ' -f1)"
  [ "$sha" = "$(cat "$A/generated/api.d.ts.source-sha256")" ] || { echo "  ★ api.d.ts.source-sha256 다름"; return 1; }
  git show "$BASE:$A/generated/openapi.json" > "$d/openapi.base.json"
  python3 - "$d/openapi.base.json" "$A/generated/openapi.json" "$COMMIT" <<'PY'
import json, sys
a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
changed_paths = sorted(k for k in set(a["paths"]) | set(b["paths"]) if a["paths"].get(k) != b["paths"].get(k))
sa, sb = a["components"]["schemas"], b["components"]["schemas"]
changed = sorted(k for k in sa if k in sb and sa[k] != sb[k])
gone = sorted(k for k in sa if k not in sb)
new = sorted(k for k in sb if k not in sa)
rest = [k for k in set(a) | set(b) if k not in ("paths", "components") and a.get(k) != b.get(k)]
rest += [k for k in set(a["components"]) | set(b["components"])
         if k != "schemas" and a["components"].get(k) != b["components"].get(k)]


def props(name):
    x, y = sa[name].get("properties", {}), sb[name].get("properties", {})
    return sorted(q for q in set(x) | set(y) if x.get(q) != y.get(q))


ALLOWED = {
    "GreenwashAiSettingCreate": {"terms"},
    "GreenwashAiSetting": {"schemaVersion", "terms"},
    "GreenwashAiSettingDefault": {"schemaVersion", "terms"},
}
if sys.argv[3] == "3":  # ③ 결과 result@1 두 갈래의 terms?(NotRequired — required 목록은 그대로)
    ALLOWED |= {"ScanResult": {"terms"}, "DryRunResult": {"terms"}}
    assert all("terms" not in sb[k].get("required", []) for k in ("ScanResult", "DryRunResult"))
seen = {k: props(k) for k in changed if k in ALLOWED}
print(f"  paths 바뀜 {changed_paths} · 구성요소 바뀜 {changed} · 새 {new} · 빠짐 {gone} · 그 밖 {rest}")
print(f"  칸 {seen}")
path = "/ai-settings/greenwash"
post_only = (changed_paths == [path] and {m for m in a["paths"][path] if a["paths"][path][m] != b["paths"][path][m]}
             == {"post"})
ok = (post_only and set(changed) <= set(ALLOWED) and not gone and not rest
      and new == ["GreenwashTerm", "GreenwashTermIn"]
      and all(set(v) <= ALLOWED[k] for k, v in seen.items()))
sys.exit(0 if ok else 1)
PY
}

s12() {  # 발주서 §4-7(검증 1 권고 r1): 모델과 마이그레이션이 맞음 · <기준> 뒤 새 마이그레이션은 0006 하나
  local n
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py makemigrations --check --dry-run) > "$OUT/s12-makemigrations.log" 2>&1
  local code=$?
  grep -v -i "warning" "$OUT/s12-makemigrations.log" | tail -1 | sed 's/^/  /'
  n="$(changed | grep -E "^$E/[a-z_]+/migrations/" | grep -v -c -x -F "$G/migrations/0006_ai_settings_terms.py")"
  echo "  <기준> 뒤 마이그레이션 파일(0006 밖) $n"
  [ "$code" -eq 0 ] && [ "$n" -eq 0 ] && grep -q "No changes detected" "$OUT/s12-makemigrations.log"
}

s7() {
  local n
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || return 1
  n="$(git diff --name-only "$BASE" -- "$A/scripts/test-layout-allow.txt" | grep -c .)"
  echo "  허용 목록 diff $n"
  [ "$n" = 0 ]
}

s8() {
  local log="$OUT/s8-verify-fast.log" code web
  scripts/verify.sh --fast > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  local port
  port="$(env_value WEB_PORT)"
  WEB_PORT="$port" WEB_TEST_PORT="$((port + 1))" apps/web/scripts/verify.sh > "$OUT/s8-web-verify.log" 2>&1
  web=$?
  echo "  apps/web verify $(tail -1 "$OUT/s8-web-verify.log") EXIT=$web(WEB_PORT $port)"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "VERIFY_FAST=PASS" ] && [ "$web" -eq 0 ]
}

gate() {  # 기계 문(머리말)
  local tries=0 free load others building me
  me="$(env_value COMPOSE_PROJECT_NAME)"
  while :; do
    others="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep '^esg-app' | grep -v -x -F "$me" | sort -u | wc -l | tr -d ' ')"
    building="$(ps -axo command | grep -E "^[^ ]*/?(docker|docker-compose)( .*)? (build|buildx)( |$)" | grep -v -c grep)"
    free="$(memory_pressure 2> /dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(sysctl -n vm.loadavg | awk '{print $2}')"
    if [ "$others" -le 2 ] && [ "$building" = 0 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 24 ]; then
      echo "  (문: 자기 밖 esg-app* $others · build 중 $building · free ${free:-?}% · 1분 부하 ${load:-?} · 기다림 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열림: 자기 밖 $others · build 중 $building · free ${free:-?}% · 부하 ${load:-?})"; return 1; }
    tries=$((tries + 1))
    sleep 60
  done
}

s9() {
  local log="$OUT/s9-business.log" code n
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s9-up-postgres.log" 2>&1 || { tail -3 "$OUT/s9-up-postgres.log"; return 1; }
  if [ "$COMMIT" = 3 ]; then  # ③ 통합(test_run_flow)은 벌 전체(api-py·worker-py·queue)가 떠 있어야 한다 — verify.sh 전량과 같은 꼴
    EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)" || return 1
    export EDK_JWT_PUBLIC_KEY CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
    scripts/with-build-lock.sh docker compose build > "$OUT/s9-build.log" 2>&1 || { tail -5 "$OUT/s9-build.log"; return 1; }
    docker compose up -d --wait > "$OUT/s9-up.log" 2>&1 || { tail -5 "$OUT/s9-up.log"; return 1; }
    echo "  벌 전체 build(빌드 잠금)·up --wait 됨"
  fi
  local extra="" sec integ=0
  [ "$COMMIT" = 3 ] && extra="esgapi/runs"
  # shellcheck disable=SC2086
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db -n 4 \
    esgapi/greenwash esgapi/core esgapi/config $extra) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  echo "  업무 층 수 ${n:-?}(기준 $BASE_BUSINESS — 늘기만 · 기대 ${WANT_BUSINESS:-늘기만})"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) \
    > "$OUT/s9-security.log" 2>&1
  sec=$?
  echo "  보안 층 $(tail -1 "$OUT/s9-security.log") EXIT=$sec"
  if [ "$COMMIT" = 3 ]; then
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-integration.sh -p no:cacheprovider \
      tests_integration/test_run_flow.py) > "$OUT/s9-integration.log" 2>&1
    integ=$?
    echo "  통합 test_run_flow $(tail -1 "$OUT/s9-integration.log") EXIT=$integ"
  fi
  [ "$code" -eq 0 ] && [ "${n:-0}" -ge "${WANT_BUSINESS:-$BASE_BUSINESS}" ] && [ "$sec" -eq 0 ] && [ "$integ" -eq 0 ]
}

s10() {
  local log="$OUT/s10-planted.log" flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  # shellcheck disable=SC2086
  G2D_OUT="$OUT" "$A/scripts/planted-breaks-G2d.sh" --commit "$COMMIT" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^    FAILED|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$CONTAINERS" = 1 ] || echo "  (컨테이너 층 없이 — 업무 층만 걸린 파손은 셈 밖)"
  local want="PLANTED=7/7"
  [ "$code" -eq 0 ] && { [ "$CONTAINERS" = 0 ] || [ "$(tail -1 "$log")" = "$want" ]; }
}

s11() {
  local all keys bin lab words body msg
  all="$(changed)"
  body="$(for f in $all; do
    if git cat-file -e "$BASE:$f" 2>/dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed "s|^|+$f:|" "$f"; fi; done)"
  msg="$(git log --format=%B "$BASE..HEAD")"
  keys="$(printf '%s\n%s\n' "$body" "$msg" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G2d\.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  lab="$(echo "$body" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G2d\.sh:" | grep -c -E 'esg-lab|py/greenwash')"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$body" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  echo "  키 꼴 $keys · pdf/xlsx/ipynb $bin · esg-lab 언급(더한 줄) $lab · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$keys" -eq 0 ] && [ "$bin" -eq 0 ] && [ "$lab" -eq 0 ] && [ "$words" = 0 ]
}

step 1 "바뀐 파일이 §1-2~1-4 안 · 0줄·0바이트 diff 0" s1
step 2 "§1-4 공유 줄 numstat·- 줄 원문·허락 줄 밖 0 · 웹 복제 줄" s2
step 3 "lint-imports 전부 KEPT" s3
step 4 "pytest esgapi/greenwash esgapi/core(순수) 초록, 수" s4
step 5 "골든 sha256 = <기준> · g2d-baseline = ②-0 커밋 · 다시 지어 대조" s5
step 6 "그린워싱 고정 스키마·generated/ 다시 뽑아 cmp · 허용 차이 안" s6
step 7 "테스트 자리 검사·허용 목록 diff 0" s7
step 8 "verify.sh --fast · apps/web/scripts/verify.sh" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "업무 층 greenwash·core·config(③ runs) · 보안 층 · ③ 통합" s9
else
  not_run 9 "컨테이너 층(업무·보안·통합)" "--with-containers 없음"
fi
step 10 "심은 파손" s10
step 11 "키 꼴·바이너리·esg-lab·실재 기업명 0" s11
step 12 "makemigrations --check(No changes) · 새 마이그레이션 0006 하나" s12
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
