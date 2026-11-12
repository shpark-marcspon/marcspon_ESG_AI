#!/usr/bin/env bash
# 밴드 G1b-2b(MARC-TICK-205: 그린워싱 좌표 엔진 꽂기·목록 줄 묶음 읽기·truncated·failedPageCount·보고서 GET 손질)의
# §4 자기검증(발주서 band-handoffs/G1b-2b-order.md §4). 틀은 section4-G1b-2a.sh 그대로다.
#   사용: apps/api-py/scripts/section4-G1b-2b.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --commit n 은 커밋 n 경계(그 커밋까지의 시험·심은 파손). --with-containers 면 단계 11(업무·보안)과 12 의 컨테이너
#   층을 돈다 — 아니면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)만. 문(MARC-ENT-241·292): 자기 밖 esg-app*
#   프로젝트 ≤ 2, build 중 0, free ≥ 20%, 1분 부하 < 24 — 60초 간격 최대 30분. postgres 만 띄운다(build 없음).
#   띄운 벌은 내리지 않는다(러너가 끝에 down -v).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 G1b-2b.out — 심은 파손에도 G1B2B_OUT 으로 넘긴다), G1B2B_FORBIDDEN(실재
#   기업명 낱말 파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
G="$E/greenwash"
OUT="${S4_OUT:-$ROOT/../G1b-2b.out}"
FORBIDDEN="${G1B2B_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(5c4ef9b — ba37610 뒤 S3C-b1 병합)에서 잰 수: 그 트리를 git archive 로 풀어 --collect-only 로 잼.
#   순수 = pytest esgapi/greenwash -m "not django_db" 787 · 정적 규칙 = esgapi/core/tests/isolation 의 test_static_rules 21 ·
#   업무 = -m django_db esgapi/greenwash esgapi/config esgapi/core/tests/test_permissions_wiring.py
#   esgapi/runs/tests/service/selectors/test_runs.py esgapi/core/tests/test_selectors_tenant.py 210 · 보안 = tests/security 273.
# 커밋마다 기대 수. ① 순수 +7(test_locate_closing) · 업무 +2(test_binding_e0_coordinates_runs) · 보안 +0.
# ② = ① + 순수 +6(늦은 import R1 둘 · test_checks_shapes 거절 넷) · 업무 +8(checks_batch 넷 · test_runs 하나 · tenant 셋 —
#   test_greenwash_checks 는 이름 바꿈 하나라 0) · 보안 +2(ⓘ 둘).
# ③ = ② + 업무 +2(test_greenwash_report_headers 둘) · 보안 +1(ⓙ) · 순수 +0.
expect_pure() { case "$COMMIT" in 1) echo 794 ;; *) echo 800 ;; esac; }
expect_business() { case "$COMMIT" in 1) echo 212 ;; 2) echo 220 ;; *) echo 222 ;; esac; }
expect_security() { case "$COMMIT" in 1) echo 273 ;; 2) echo 275 ;; *) echo 276 ;; esac; }
BASE_PURE=787 BASE_BUSINESS=210 BASE_SECURITY=273 BASE_RULES=21
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2|3> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "--commit <1|2|3> 이 필요하다" >&2; exit 2 ;; esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 G1b-2b §4 · 커밋 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
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

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-2(그린워싱) + §1-3(공유 파일) — 닫힌 목록
ALLOWED="^$G/flows/(binding_e0|colab_e0)\.py\$
^$G/tools/ports\.py\$
^$G/service/actions/(checks|report)\.py\$
^$G/contracts/checks_shapes\.py\$
^$G/service/apis/greenwash\.py\$
^$G/README\.md\$
^$G/tests/.*
^$A/scripts/(section4|planted-breaks)-G1b-2b\.sh\$
^$E/runs/service/selectors/runs\.py\$
^$E/core/service/selectors/documents\.py\$
^$E/runs/tests/service/selectors/test_runs\.py\$
^$E/core/tests/test_selectors_tenant\.py\$
^$E/core/tests/isolation/test_static_rules\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$A/tests/security/test_greenwash\.py\$"

# §1-2 의 기존 시험 고침 허용(그 밖의 $G/tests 기존 파일은 0줄 — 새 파일은 됨)
TESTS_EDIT="^$G/tests/flows/test_binding_e0\.py\$
^$G/tests/service/apis/test_greenwash_checks\.py\$
^$G/tests/data/flow-shapes/checks/.*\.schema\.json\$
^$G/tests/data/contract-examples/checks/.*\.json\$
^$G/tests/contracts/test_checks_shapes\.py\$"

s1() {
  local all outside pattern tpat edited
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  tpat="$(echo "$TESTS_EDIT" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  # $G/tests 안의 「기존」 파일 고침은 TESTS_EDIT 만
  edited="$(git diff --no-renames --name-only --diff-filter=MD "$BASE" -- "$G/tests" | grep -v -E -e "$tpat" | grep -c .)"
  [ "$edited" -eq 0 ] || git diff --no-renames --name-only --diff-filter=MD "$BASE" -- "$G/tests" | grep -v -E -e "$tpat" | sed 's/^/  ★ 허용 밖 기존 시험 고침: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside · 허용 밖 기존 시험 고침 $edited"
  [ "$outside" -eq 0 ] && [ "$edited" -eq 0 ]
}

# §1-3 「0줄」 자리(실행기·core 흐름·끼움 밖 흐름·좌표 도구·출력·웹·마이그레이션 등)
ZERO="$E/runs/tasks.py $E/runs/context.py $E/runs/service/actions $E/runs/service/apis/runs.py $E/core/flows
$E/core/tests/test_selector_scope.py $A/.importlinter $E/config/api.py $E/core/permissions.py $E/config/tests/test_api_contract.py
$G/apps.py $G/engines $G/prompts $G/flows/rewrite_r1.py $G/flows/criteria_e0.py $G/flows/prompt_model_e0.py
$G/flows/registration.py $G/tools/coordinates.py $G/tools/pdfium_locate.py $G/tools/llm_bridge.py $G/outputs
$G/tests/data/golden $G/migrations $E/runs/migrations $E/core/migrations $A/uv.lock apps/web"
CONTRACTS_OTHER=":(exclude)$G/contracts/checks_shapes.py"

s2() {
  local missing=0 p n bad
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO;
    git diff --name-only "$BASE" -- "$G/contracts" "$CONTRACTS_OTHER"; } | sort -u)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') + contracts 의 checks 밖 · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

# 허용 파일 안의 허용 자리: AST 의 맨 위 문(클래스는 메서드마다)을 <기준> 과 견줘 허용 이름 밖이 같은지
s2b() {
  local d="$OUT/s2b" f
  mkdir -p "$d"
  for f in flows/binding_e0.py flows/colab_e0.py tools/ports.py service/actions/checks.py service/actions/report.py \
    service/apis/greenwash.py contracts/checks_shapes.py; do
    git show "$BASE:$G/$f" > "$d/$(echo "$f" | tr / _).base"
  done
  (cd "$A" && uv run --frozen python - "$d" "$COMMIT" <<'PY'
import ast
import sys
from pathlib import Path

d, commit = Path(sys.argv[1]), int(sys.argv[2])
G = Path("esgapi/greenwash")
# 파일 → 바뀌어도 되는 자리(<모듈 머리말> · 함수·클래스 이름 · 클래스.메서드 · import:<모듈>). 더한 이름은 「+이름」.
ALLOW = {
    "flows/binding_e0.py": {"<doc>", "GreenwashBinding.adapters"},
    "flows/colab_e0.py": {"<doc>", "locate", "import:esgapi.greenwash.tools.ports"},
    "tools/ports.py": {"<doc>", "import:typing", "+ClosingCoordinatesPort"},
    "service/actions/checks.py": set(),
    "service/actions/report.py": set(),
    "service/apis/greenwash.py": set(),
    "contracts/checks_shapes.py": set(),
}
if commit >= 2:  # ② 목록 줄 묶음 읽기·두 칸
    ALLOW["service/actions/checks.py"] = {
        "<doc>", "_result_of", "+_failed_page_count", "checks", "import:esgapi.runs.service.selectors.runs"
    }
    ALLOW["contracts/checks_shapes.py"] = {
        "<doc>",
        "GreenwashCheckDocument.reportYear.__doc__",
        "GreenwashCheckDocument.previousDocumentId.__doc__",
        "+GreenwashCheckRun.failedPageCount",
        "+GreenwashCheckRun.failedPageCount.__doc__",
        "+GreenwashChecks.truncated",
        "+GreenwashChecks.truncated.__doc__",
    }
if commit >= 3:  # ③ 보고서 GET 손질
    ALLOW["service/actions/report.py"] = {"<doc>", "report"}
    ALLOW["service/apis/greenwash.py"] = {"report_get"}


def units(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    body = ast.parse(text).body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        out["<doc>"] = ast.dump(body[0])
        body = body[1:]
    for i, node in enumerate(body):
        if isinstance(node, ast.ImportFrom):
            out[f"import:{node.module}"] = ast.dump(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = ast.dump(node)
        elif isinstance(node, ast.ClassDef):
            head = ast.ClassDef(name=node.name, bases=node.bases, keywords=node.keywords, body=[],
                                decorator_list=node.decorator_list, type_params=getattr(node, "type_params", []))
            out[node.name] = ast.dump(head)
            last = "<classdoc>"  # 칸 뒤의 글(docstring)은 그 칸의 이름.__doc__ 로 센다(칸을 더해도 차례가 밀리지 않게)
            for j, item in enumerate(node.body):
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    name = last = item.target.id
                elif isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
                    name = last if last == "<classdoc>" else f"{last}.__doc__"
                else:
                    name = getattr(item, "name", None) or f"#{j}:{type(item).__name__}:{ast.dump(item)[:80]}"
                    last = name
                out[f"{node.name}.{name}"] = ast.dump(item)
        else:
            out[f"#{ast.dump(node)}"] = ast.dump(node)
    return out


bad = 0
for f, allowed in ALLOW.items():
    base = units((d / (f.replace("/", "_") + ".base")).read_text(encoding="utf-8"))
    head = units((G / f).read_text(encoding="utf-8"))
    changed = sorted(k for k in base.keys() & head.keys() if base[k] != head[k])
    removed = sorted(base.keys() - head.keys())
    added = sorted(head.keys() - base.keys())
    outside = [k for k in changed if k not in allowed] + [f"-{k}" for k in removed if k not in allowed]
    # 더한 클래스(「+이름」 허용)의 몸은 그 클래스와 같이 더해진 것이다
    added = [k for k in added if f"+{k.split('.', 1)[0]}" not in allowed or "." not in k]
    outside += [f"+{k}" for k in added if f"+{k}" not in allowed and not k.startswith("#")]
    outside += [f"+?{k[:60]}" for k in added if k.startswith("#")]
    print(f"  {f}: 바뀐 자리 {changed + ['+' + a[:40] for a in added] + ['-' + r[:40] for r in removed] or '없음'}"
          f" · 허용 밖 {len(outside)}")
    for k in outside:
        print(f"    ★ {k[:120]}")
    bad += len(outside)
sys.exit(0 if bad == 0 else 1)
PY
  )
}

numstat() {  # <파일> → "더함 지움"(바뀌지 않았으면 0 0)
  local got
  got="$(git diff --numstat "$BASE" -- "$1" | awk '{print $1, $2}')"
  echo "${got:-0 0}"
}

s3() {
  local bad=0 add del want
  # 파일 · 지움 한도(§1-3 — 더하기·숫자 줄만): test_static_rules 1(분모 60→61) · 나머지 0. ports.py 는 §1-2 「더하기만」
  # 에 import 한 줄(runtime_checkable)과 머리말 한 줄(셋 → 넷)을 고친다 — 2(감독 허락). test_checks_shapes 는 required
  # 한 줄 1(감독 허락 10-20 저녁). generated 는 [8] 이 잰다.
  for want in "$E/runs/service/selectors/runs.py 0" "$E/core/service/selectors/documents.py 0" \
    "$E/runs/tests/service/selectors/test_runs.py 0" "$E/core/tests/test_selectors_tenant.py 0" \
    "$E/core/tests/isolation/test_static_rules.py 1" "$A/tests/security/test_greenwash.py 0" "$G/tools/ports.py 2" \
    "$G/tests/contracts/test_checks_shapes.py 1" \
    "$A/generated/openapi.json -" "$A/generated/api.d.ts -" "$A/generated/api.d.ts.source-sha256 -"; do
    set -- $want
    read -r add del <<< "$(numstat "$1")"
    echo "  $1 더함 $add 지움 $del(지움 한도 $2)"
    [ "$2" = "-" ] && continue
    [ "$del" -le "$2" ] || bad=$((bad + 1))
    [ "$del" = 0 ] || git diff -U0 "$BASE" -- "$1" | grep -E '^-' | grep -v -E '^--- ' | sed 's/^/      /'
  done
  [ "$bad" = 0 ]
}

s4() { (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}"); }

s5() {
  local log="$OUT/s5-pytest.log" code total want rules rcode
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/greenwash \
    -m "not django_db") > "$log" 2>&1
  code=$?
  total="$(grep -E '^[0-9]+ passed' "$log" | sed -E 's/^([0-9]+) passed.*/\1/')"
  want="$(expect_pure)"
  tail -1 "$log" | sed 's/^/  /'
  echo "  기준 $BASE_PURE → 지금 ${total:-?}(커밋 $COMMIT 기대 $want)"
  (cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/core/tests/isolation/test_static_rules.py) > "$OUT/s5-rules.log" 2>&1
  rcode=$?
  rules="$(grep -E '^[0-9]+ passed' "$OUT/s5-rules.log" | sed -E 's/^([0-9]+) passed.*/\1/')"
  echo "  정적 규칙(test_static_rules) EXIT=$rcode ${rules:-?}(기준 $BASE_RULES)"
  [ "$code" -eq 0 ] && [ "${total:-0}" -eq "$want" ] && [ "$rcode" -eq 0 ] && [ "${rules:-0}" -eq "$BASE_RULES" ]
}

s6() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/greenwash/tests/test_copy_ast.py 2>&1 | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s7() {
  local p bad=0 n=0 a b
  for p in $(git ls-tree -r --name-only "$BASE" -- "$G/tests/data/golden"); do
    a="$(git show "$BASE:$p" | shasum -a 256 | cut -d' ' -f1)"
    b="$(shasum -a 256 "$p" | cut -d' ' -f1)"
    n=$((n + 1))
    [ "$a" = "$b" ] || { echo "  ★ $p"; bad=$((bad + 1)); }
  done
  echo "  골든 $n 파일 · 다름 $bad"
  [ "$n" -gt 0 ] && [ "$bad" = 0 ]
}

s8() {  # generated: 다시 뽑아 cmp + <기준> 과의 차이(커밋 ① 은 0 · ②·③ 은 §1-3 의 칸 둘과 설명 글만)
  local d="$OUT/s8-generated" code
  mkdir -p "$d"
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json" || return 1
  echo "  openapi 다시 뽑음 cmp 같음"
  [ "$(shasum -a 256 "$A/generated/openapi.json" | cut -d' ' -f1)" = "$(cat "$A/generated/api.d.ts.source-sha256")" ] \
    || { echo "  ★ api.d.ts.source-sha256 ≠ openapi.json"; return 1; }
  if [ "$COMMIT" = 1 ]; then
    local n
    n="$(git diff --name-only "$BASE" -- "$A/generated" | grep -c .)"
    echo "  커밋 ①: generated 의 <기준> 차이 파일 $n(기대 0)"
    [ "$n" = 0 ]
    return
  fi
  git show "$BASE:$A/generated/openapi.json" > "$d/openapi-base.json"
  git diff -U0 "$BASE" -- "$A/generated/api.d.ts" > "$d/api.d.ts.diff"
  (cd "$A" && uv run --frozen python - "$d/openapi-base.json" generated/openapi.json "$d/api.d.ts.diff" <<'PY'
import copy
import json
import re
import sys

base, head = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
want = copy.deepcopy(head)
schemas = want["components"]["schemas"]
bad = []
# 칸 둘을 걷고 required 에서도 뺀다
for comp, field in (("GreenwashCheckRun", "failedPageCount"), ("GreenwashChecks", "truncated")):
    s = schemas[comp]
    if field not in s["properties"] or field not in s.get("required", []):
        bad.append(f"{comp}.{field} 가 없거나 필수가 아님")
        continue
    del s["properties"][field]
    s["required"].remove(field)
# 고친 칸 설명 둘(reportYear·previousDocumentId)은 <기준> 의 설명으로 돌려 견준다
for field in ("reportYear", "previousDocumentId"):
    b = base["components"]["schemas"]["GreenwashCheckDocument"]["properties"][field]
    schemas["GreenwashCheckDocument"]["properties"][field]["description"] = b["description"]
if want != base:
    bad.append("openapi 의 차이가 칸 둘·설명 둘 밖")
allowed = re.compile(r"^-\s*\* @description (보고 연도|수정본이면 앞 판 문서 id)\..*$")
removed = [l for l in open(sys.argv[3], encoding="utf-8").read().splitlines() if l.startswith("-") and not l.startswith("---")]
outside = [l for l in removed if not allowed.match(l)]
print(f"  openapi: 칸 둘·설명 둘 밖 같음 {'예' if not bad else '★ 아니오'} · api.d.ts 지운 줄 {len(removed)} · 허용 밖 {len(outside)}")
for line in outside:
    print(f"  ★ {line}")
for b in bad:
    print(f"  ★ {b}")
sys.exit(0 if not bad and not outside else 1)
PY
  )
}

s9() {
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py makemigrations --check --dry-run 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s9b() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s10() {
  local log="$OUT/s10-verify-fast.log"
  scripts/verify.sh --fast > "$log" 2>&1
  local code=$?
  tail -1 "$log" | sed 's/^/  /'
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "VERIFY_FAST=PASS" ]
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

s11_business() {
  local log="$OUT/s11-business.log" code n want
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s11-up-postgres.log" 2>&1 || { tail -3 "$OUT/s11-up-postgres.log"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/greenwash \
    esgapi/config esgapi/core/tests/test_permissions_wiring.py esgapi/runs/tests/service/selectors/test_runs.py \
    esgapi/core/tests/test_selectors_tenant.py) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  want="$(expect_business)"
  echo "  업무 층 수 ${n:-?}(기준 $BASE_BUSINESS — 늘기만 · 커밋 $COMMIT 기대 $want)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -gt "$BASE_BUSINESS" ] && [ "${n:-0}" -eq "$want" ]
}

s11_security() {
  local log="$OUT/s11-security.log" code n want
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s11-up-postgres.log" 2>&1 || { tail -3 "$OUT/s11-up-postgres.log"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  want="$(expect_security)"
  echo "  보안 층 수 ${n:-?}(기준 $BASE_SECURITY — 줄지 않음 · 커밋 $COMMIT 기대 $want)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -ge "$BASE_SECURITY" ] && [ "${n:-0}" -eq "$want" ]
}

s12() {
  local log="$OUT/s12-planted.log" flag="" want
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  case "$COMMIT" in 1) want=3 ;; 2) want=9 ;; *) want=11 ;; esac
  # shellcheck disable=SC2086
  G1B2B_OUT="$OUT" "$A/scripts/planted-breaks-G1b-2b.sh" --commit "$COMMIT" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^    FAILED|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$CONTAINERS" = 1 ] || echo "  (컨테이너 층 없이 — 업무 층만 걸린 파손은 셈 밖)"
  [ "$code" -eq 0 ] && { [ "$CONTAINERS" = 0 ] || [ "$(tail -1 "$log")" = "PLANTED=$want/$want" ]; }
}

s13() {
  local all keys bin words body msg
  all="$(changed)"
  body="$(for f in $all; do
    case "$f" in "$A"/generated/*) continue ;; esac
    if git cat-file -e "$BASE:$f" 2>/dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed "s|^|+$f:|" "$f"; fi; done)"
  msg="$(git log --format=%B "$BASE..HEAD")"
  keys="$(printf '%s\n%s\n' "$body" "$msg" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G1b-2b\.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$body" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  echo "  키 꼴 $keys · pdf/xlsx/ipynb 파일 더함 $bin · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$keys" -eq 0 ] && [ "$bin" -eq 0 ] && [ "$words" = 0 ]
}

step 1 "바뀐 파일이 §1-2 + §1-3 안 · 기존 시험 고침은 §1-2 목록만" s1
step 2 "0줄 목록 diff 0(§1-3)" s2
step 2 "허용 파일 안의 허용 자리(AST 맨 위 문)" s2b
step 3 "§1-3 공유 파일 numstat·- 줄 원문" s3
step 4 "lint-imports 전부 KEPT" s4
step 5 "pytest esgapi/greenwash(순수) 초록·수 · 정적 규칙" s5
step 6 "test_copy_ast(엔진 AST 그대로)" s6
step 7 "골든 sha256 = <기준>" s7
step 8 "generated/ 다시 뽑아 cmp + 차이가 §1-3 허용 안" s8
step 9 "makemigrations --check(모든 앱)" s9
step 9 "테스트 자리 검사" s9b
step 10 "verify.sh --fast" s10
if [ "$CONTAINERS" = 1 ]; then
  step 11 "업무 층 greenwash·config·wiring·runs/core selector 시험" s11_business
  step 11 "보안 층 tests/security" s11_security
else
  not_run 11 "컨테이너 층(업무·보안)" "--with-containers 없음"
fi
step 12 "심은 파손" s12
step 13 "키 꼴·xlsx/pdf 파일·실재 기업명 0" s13
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
