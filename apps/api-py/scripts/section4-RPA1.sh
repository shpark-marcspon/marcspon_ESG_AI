#!/usr/bin/env bash
# 밴드 RPA1(MARC-TICK-433: 원고작성 AI 설정 서버 — ai.prompt-model@3 판 표·경로 일곱·실행이 적용 판으로)의 §4
# 자기검증(발주서 band-handoffs/RPA1-order.md §4). 틀은 section4-IR4.sh(경계·기준 트리 지문·generated 기대)와
# section4-RP2c.sh(WEAKEN·--msg·pyright·ruff).
#   사용: apps/api-py/scripts/section4-RPA1.sh --commit <1|2> [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --with-containers 면 단계 10(업무·보안)을 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 끝 경계 전량은 따로). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 RPA1.out — 검증자는 RPA1.verify), RPA1_FORBIDDEN(실재 기업명 낱말
#   파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만), MARCSPON_ROOT(보고 파일을 찾는 뿌리).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
C="$E/core"
P="$E/drafting"
R="$E/runs"
OUT="${S4_OUT:-$ROOT/../RPA1.out}"
FORBIDDEN="${RPA1_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
MROOT="${MARCSPON_ROOT:-$HERE/../../../../..}"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0; PLANTED=0; MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --commit <1|2> [--with-containers] [--planted] [--msg <파일>] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2) ;; *) echo "--commit <1|2> 이 필요하다" >&2; exit 2 ;; esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 RPA1 §4 · 경계 $COMMIT · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# 기준 트리(git archive) — 단계 1·6 이 쓴다
BASE_TREE="$OUT/base-tree"
base_tree() {
  [ -f "$BASE_TREE/.ref" ] && [ "$(cat "$BASE_TREE/.ref")" = "$BASE" ] && return 0
  rm -rf "$BASE_TREE" && mkdir -p "$BASE_TREE"
  git archive "$BASE" "$A" | tar -x -C "$BASE_TREE" || return 1
  echo "$BASE" > "$BASE_TREE/.ref"
}

# 1: 순수 층(drafting·core — not django_db). N0 = 기준 트리에서 모은 수 → N1 통과(늘기만).
PURE_PATHS="esgapi/drafting esgapi/core"
s1() {
  local log n n0 code
  base_tree || return 1
  # shellcheck disable=SC2086
  n0="$(cd "$BASE_TREE/$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$ROOT/$A/.venv/bin/python" -m pytest $PURE_PATHS \
    -m "not django_db" -q -p no:cacheprovider --collect-only 2>&1 | tail -1 | sed -n 's/^\([0-9]*\)\/*[0-9]* *tests* .*/\1/p')"
  # shellcheck disable=SC2086
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q $PURE_PATHS -m "not django_db" \
    -p no:cacheprovider 2>&1)"
  code=$?
  echo "$log" > "$OUT/s1-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  N0(기준 트리 — $PURE_PATHS) ${n0:-?} → N1 ${n:-?} 통과 · $(echo "$log" | tail -1)"
  [ "$code" = 0 ] && [ -n "$n0" ] && [ "${n:-0}" -gt "$n0" ]
}

# 2: lint-imports — 계약 수 = 기준, .importlinter 0줄(0줄 목록이 따로 본다).
s2() {
  local log kept broken
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen lint-imports 2>&1)"
  echo "$log" | tail -2 | sed 's/^/  /'
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\2/p')"
  echo "  계약 KEPT ${kept:-?} (기준 $BASE_CONTRACTS) · broken ${broken:-?}"
  [ "${kept:-0}" = "$BASE_CONTRACTS" ] && [ "${broken:-1}" = 0 ]
}

s3() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s4() {
  local code=0
  (cd "$A" && uv run --frozen pyright esgapi/drafting 2>&1 | tail -1 | sed 's/^/  pyright /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff check . 2>&1 | tail -1 | sed 's/^/  ruff check /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff format --check . 2>&1 | tail -1 | sed 's/^/  ruff format /'; exit "${PIPESTATUS[0]}") \
    || code=1
  return $code
}

# 5: 경로(§1-2·§1-3, 누적) · 0줄 목록 · 기존 고침은 ② 에서만 · 공유 numstat·「-」 원문(bad_minus=0) · 7a sha16
ALLOWED_1="^$P/contracts/ai_setting_shapes\.py\$
^$P/flows/prompt_model_v2\.py\$
^$P/models\.py\$
^$P/migrations/0002_ai_settings\.py\$
^$P/service/(selectors|services|actions|apis)/ai_settings\.py\$
^$P/api\.py\$
^$P/tests/.*
^$A/scripts/(section4|planted-breaks)-RPA1\.sh\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$C/permissions\.py\$
^$C/tests/(test_permissions|test_permissions_wiring|test_transaction_rules|test_selector_scope)\.py\$
^$C/tests/isolation/(test_static_rules|test_managers)\.py\$
^$E/config/api\.py\$
^$E/config/tests/(test_api_contract|test_api_errors|test_request_schemas_reject_bool)\.py\$
^$A/tests/security/(test_tenant_paths|test_login|test_owner|test_operator_company|test_drafting_ai_settings)\.py\$
^$A/tests/security/(test_migrations|test_same_company_foreign_keys|test_request_transactions|test_api_times)\.py\$"
ALLOWED_2="^$P/flows/(binding_v2|draft_v2)\.py\$
^$P/service/selectors/run_extras\.py\$
^$P/apps\.py\$
^$P/prompts/README\.md\$
^$R/tests/test_extras\.py\$"
ALLOWED="$ALLOWED_1"
[ "$COMMIT" -ge 2 ] && ALLOWED="$ALLOWED
$ALLOWED_2"
# §1-2 「0줄」(정규식, 뿌리 기준). core·config·runs 는 허락 파일 밖 전부 0(ALLOWED 가 가른다 — 여기는 이름 박은 것만).
ZERO="^$P/contracts/(shapes|options_shapes|wire|api_shapes)\.py\$
^$P/engines/
^$P/flows/(reuse|registration)\.py\$
^$P/service/apis/drafting\.py\$
^$P/service/actions/(projects|changes|result|download|run_sources)\.py\$
^$P/service/schemas/
^$P/outputs/
^$P/tools/
^$P/prompts/[^/]+/[^/]+\.md\$
^$P/migrations/0001_initial\.py\$
^$P/tests/data/flow-shapes/[^/]+\$
^$P/tests/data/flow-shapes/options/
^$P/tests/data/examples/
^$A/esgapi/runbundle/
^apps/web/
^$A/\.importlinter\$
^compose\.yaml\$
^$A/(pyproject\.toml|uv\.lock)\$"
# 기존 시험 고침(§1-2 끝): ② 에서만 바뀐다.
OWN_FIXES_2="$P/tests/flows/test_binding_v2.py $P/tests/flows/support.py $P/tests/flows/test_draft_v2.py
$P/tests/flows/test_runs_drafting.py $P/tests/test_apps.py"
# 셈 파일(§1-3 — 「-」 줄은 숫자·같은 줄 주석만 다른 「+」 줄이 있어야 한다)
COUNTS="$C/tests/test_permissions.py $C/tests/test_permissions_wiring.py $C/tests/test_transaction_rules.py
$C/tests/test_selector_scope.py $C/tests/isolation/test_static_rules.py $C/tests/isolation/test_managers.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py $E/config/tests/test_request_schemas_reject_bool.py
$A/tests/security/test_login.py $A/tests/security/test_tenant_paths.py $A/tests/security/test_owner.py
$A/tests/security/test_operator_company.py $A/tests/security/test_migrations.py
$A/tests/security/test_same_company_foreign_keys.py $A/tests/security/test_request_transactions.py
$A/tests/security/test_api_times.py $R/tests/test_extras.py"
# 허락 파일(셈 아님 — 「-」 0 이어야 한다)과 우리 땅 기존 파일(「-」 원문을 보고에)
PERMITTED="$C/permissions.py $E/config/api.py"
OWN_EXISTING="$P/models.py $P/api.py $P/apps.py $P/flows/binding_v2.py $P/flows/draft_v2.py $P/prompts/README.md
$P/tests/test_axes.py $OWN_FIXES_2"
# 「바꿈」 표시 줄(§1-3 허락 — 숫자 정규화로 같은 줄이 안 되는 것): ② test_extras 튜플 끝 "drafting"
REPLACED='"greenwash", "translation", "dataverify", "materiality")'

s5() {
  local all outside pattern zero code=0 p
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  zero="$(echo "$all" | grep -E -e "$(echo "$ZERO" | paste -sd'|' -)" | grep -c .)"
  [ "$zero" -eq 0 ] || echo "$all" | grep -E -e "$(echo "$ZERO" | paste -sd'|' -)" | sed 's/^/  ★ 0줄 목록: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside · 0줄 목록 $zero"
  [ "$outside" -eq 0 ] && [ "$zero" -eq 0 ] || code=1
  if [ "$COMMIT" -lt 2 ]; then
    for p in $OWN_FIXES_2; do
      git diff --quiet "$BASE" -- "$p" || { echo "  ★ 경계 $COMMIT 에서 바뀜(② 몫): $p"; code=1; }
    done
  fi
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $COUNTS $PERMITTED $OWN_EXISTING | sed 's/^/  numstat /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $PERMITTED $OWN_EXISTING > "$OUT/s5-permitted.diff"
  grep -E '^(\+\+\+ |-[^-])' "$OUT/s5-permitted.diff" | sed 's/^/  허락·기존 고침 /'
  # shellcheck disable=SC2086
  if [ "$(git diff "$BASE" -- $PERMITTED | grep -c '^-[^-]')" != 0 ]; then
    echo "  ★ 허락 파일(permissions·config/api)에 「-」 줄"; code=1
  fi
  echo "  7a sha16 $(git diff "$BASE" HEAD -- $A/esgapi/core $A/esgapi/config $A/generated $A/tests/security $A/esgapi/runs \
    | shasum -a 256 | cut -c1-16) (BASE..HEAD — 커밋 뒤 값이 7a 에 가는 값)"
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $COUNTS > "$OUT/s5-counts.diff"
  python3 -I - "$OUT/s5-counts.diff" "$REPLACED" <<'PYEOF' || code=1
import re, sys
replaced = [r for r in sys.argv[2].split("\n") if r]
def norm(line):
    line = re.sub(r"#.*$", "", line)
    return re.sub(r"\d+", "N", line).rstrip()
bad = 0
minus, plus = [], []
def flush():
    global bad, minus, plus
    pool = [norm(p) for p in plus]
    for m in minus:
        print(f"  - {m}")
        if norm(m) in pool:
            pool.remove(norm(m))
        elif any(r in m for r in replaced):
            print("    (「바꿈」 표시 줄 — §1-3 허락)")
        else:
            print("    ★ 숫자·같은 줄 주석 밖이 바뀐 「-」 줄")
            bad += 1
    minus, plus = [], []
for raw in open(sys.argv[1], encoding="utf-8"):
    if raw.startswith("@@") or raw.startswith("diff "):
        flush()
    elif raw.startswith("-") and not raw.startswith("---"):
        minus.append(raw[1:].rstrip("\n"))
    elif raw.startswith("+") and not raw.startswith("+++"):
        plus.append(raw[1:].rstrip("\n"))
flush()
print(f"  bad_minus={bad}")
sys.exit(1 if bad else 0)
PYEOF
  return $code
}

# 6: 기본 바이트 지문(tests/flows/texts_digest.py)을 기준 트리로도 내서 견준다 — 통째로 같아야 한다.
s6() {
  local digest="$P/tests/flows/texts_digest.py"
  base_tree || return 1
  cp "$digest" "$BASE_TREE/$digest"
  (cd "$BASE_TREE/$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH=. "$ROOT/$A/.venv/bin/python" \
    -m esgapi.drafting.tests.flows.texts_digest) > "$OUT/s6-texts_digest-base.txt" || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m esgapi.drafting.tests.flows.texts_digest) \
    > "$OUT/s6-texts_digest-new.txt" || return 1
  echo "  지문 줄 $(grep -c . "$OUT/s6-texts_digest-new.txt") · 호출 $(grep ' calls ' "$OUT/s6-texts_digest-new.txt" | awk '{print $1"="$3}' | paste -sd' ' -)"
  if diff "$OUT/s6-texts_digest-base.txt" "$OUT/s6-texts_digest-new.txt" | sed 's/^/  ★ /'; then
    if [ "$(awk '{print $2, $3}' "$OUT/s6-texts_digest-new.txt" | sort -u | grep -c '^requests ')" -le 2 ]; then
      echo "  FINGERPRINT=same (기준 = 작업본 · 실행 길 셋이 손 입력과 같은 요청)"
    else
      echo "  ★ 경우끼리 요청 지문이 갈림(손·모의 둘보다 많음)"; return 1
    fi
  else
    echo "  FINGERPRINT=differs"; return 1
  fi
}

# 7: 금지 글 — 더한 줄(추적 diff + 새 파일)·메시지·보고.
s7() {
  local d="$OUT/s7.diff" n_key n_bin n_lab n_name=0 report="$MROOT/band-reports/RPA1.md"
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } \
    > "$d" 2>/dev/null
  [ -n "$MSG" ] && [ -f "$MSG" ] && sed 's/^/+/' "$MSG" >> "$d"
  [ -f "$report" ] && sed 's/^/+/' "$report" >> "$d"
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY|marcspon-openai[.]env|spike/[.]env')"
  n_bin="$(changed | grep -c -E '\.(pdf|xlsx|docx|ipynb)$')"
  n_lab="$(grep -E '^\+' "$d" | grep -c -E 'from esg[l]ab|import esg[l]ab')"  # [ ] = 이 줄 자신을 세지 않게
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴 $n_key · .pdf/.xlsx/.docx/.ipynb $n_bin · esg-lab import $n_lab · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_lab" = 0 ] && [ "$n_name" = 0 ]
}

s8() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

# 9: generated/ 셋을 다시 뽑아 cmp(gen-ts-types.sh 와 같은 명령 — 작업본을 덮지 않고 $OUT 에) · 기준과의 차이가
#   /ai-settings/drafting 경로 여섯(동작 일곱)과 DraftingAiSetting* 뿐 · $OUT/generated-diff.txt 에 jq 넷 · apps/web typecheck
s9() {
  local g="$OUT/s9-generated" code=0 f b n
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 작업본"; else echo "  ★ cmp $f ≠ 작업본"; code=1; fi
  done
  b="$g/openapi.base.json"; n="$A/generated/openapi.json"
  git show "$BASE:$A/generated/openapi.json" > "$b"
  {
    echo "ⓐ 새 꼴 이름:"
    jq -n --slurpfile a "$b" --slurpfile b "$n" -r \
      '($b[0].components.schemas | keys) - ($a[0].components.schemas | keys) | .[]' | sed 's/^/  /'
    echo "ⓑ 지운 꼴 이름:"
    jq -n --slurpfile a "$b" --slurpfile b "$n" -r \
      '($a[0].components.schemas | keys) - ($b[0].components.schemas | keys) | .[]' | sed 's/^/  /'
    echo "ⓒ 기존 꼴 바뀜(설명 글을 걷고도 다른 것):"
    jq -n --slurpfile a "$b" --slurpfile b "$n" -r \
      'def strip: walk(if type == "object" then del(.description) else . end);
       $a[0].components.schemas as $x | $b[0].components.schemas as $y
       | [$x | keys[] | select($y[.] != null and ($x[.] | strip) != ($y[.] | strip))] | .[]' | sed 's/^/  /'
    echo "ⓓ 설명 글만 바뀐 기존 꼴:"
    jq -n --slurpfile a "$b" --slurpfile b "$n" -r \
      'def strip: walk(if type == "object" then del(.description) else . end);
       $a[0].components.schemas as $x | $b[0].components.schemas as $y
       | [$x | keys[] | select($y[.] != null and $x[.] != $y[.] and ($x[.] | strip) == ($y[.] | strip))] | .[]' | sed 's/^/  /'
    echo "새 경로 · operationId:"
    jq -n --slurpfile a "$b" --slurpfile b "$n" -r \
      '$a[0].paths as $x | $b[0].paths | to_entries[] | select($x[.key] == null)
       | .key as $k | .value | to_entries[] | "  \(.key | ascii_upcase) \($k) \(.value.operationId)"'
  } > "$OUT/generated-diff.txt"
  sed 's/^/  /' "$OUT/generated-diff.txt"
  python3 -I - "$b" "$n" <<'PYEOF' || code=1
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
added = sorted(set(b["paths"]) - set(a["paths"]))
lost = sorted(set(a["paths"]) - set(b["paths"]))
moved = [p for p in a["paths"] if p in b["paths"] and a["paths"][p] != b["paths"][p]]
sa, sb = a["components"]["schemas"], b["components"]["schemas"]
new = sorted(set(sb) - set(sa))
changed = [k for k in sa if k not in sb or sa[k] != sb[k]]
rest = [k for k in set(a) | set(b) if k not in ("paths", "components") and a.get(k) != b.get(k)]
rest += [k for k in set(a["components"]) | set(b["components"]) if k != "schemas" and a["components"].get(k) != b["components"].get(k)]
ids = sorted(op.get("operationId") for p in added for op in b["paths"][p].values())
print(f"  path 더함 {len(added)} · 동작 {len(ids)} · 지움 {lost} · 바뀜 {moved}")
print(f"  schema 더함 {len(new)} · 바뀜·지움 {changed} · 그 밖 {rest}")
ok = all(p.startswith("/ai-settings/drafting") for p in added) and len(added) == 6
ok = ok and ids == sorted(f"drafting_ai_setting_{n}" for n in (
    "list", "default", "get", "create", "apply", "prompt_model", "default_prompt_model"))
ok = ok and not lost and not moved and not changed and not rest
ok = ok and bool(new) and all(k.startswith("DraftingAiSetting") for k in new)
print(f"  기대(경로 여섯·동작 일곱·새 꼴 전부 DraftingAiSetting*·지움 0·바뀜 0) {'맞음' if ok else '★ 어긋남'}")
sys.exit(0 if ok else 1)
PYEOF
  (cd apps/web && pnpm -s typecheck > "$OUT/s9-web-typecheck.log" 2>&1) || { echo "  ★ apps/web typecheck"; code=1; }
  echo "  apps/web typecheck EXIT=$([ $code = 0 ] && echo 0 || echo '?') $(tail -1 "$OUT/s9-web-typecheck.log")"
  return $code
}

# 10: 업무(drafting·config·core·runs·translation·R9 carrier)·보안(전부)·openapi
s10() {
  local blog="$OUT/s10-business.log" slog="$OUT/s10-security.log" olog="$OUT/s10-openapi.log" bcode scode ocode
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s10-up.log" 2>&1 || { tail -3 "$OUT/s10-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db \
    esgapi/drafting esgapi/config esgapi/core esgapi/runs esgapi/translation \
    esgapi/greenwash/tests/service/actions/test_bundle_carrier.py) > "$blog" 2>&1
  bcode=$?
  echo "  업무 $(tail -1 "$blog") EXIT=$bcode"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  echo "  보안 $(tail -1 "$slog") EXIT=$scode"
  # -k openapi 는 순수·업무 둘 다(test-business.sh 는 -m django_db 를 박으므로 db-env 만 빌려 직접)
  (cd "$A" && . scripts/db-env.sh && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY \
    TEST_DATABASE_URL_PY_OWNER="$OWNER_DATABASE_URL" uv run --frozen pytest -q -p no:cacheprovider -k openapi esgapi) \
    > "$olog" 2>&1
  ocode=$?
  echo "  -k openapi $(tail -1 "$olog") EXIT=$ocode"
  [ "$bcode" = 0 ] && [ "$scode" = 0 ] && [ "$ocode" = 0 ]
}

# 11: 시험 약화 검사. HEAD 가 기준이면(커밋 전) --warn 으로 미리(작업 트리는 못 본다 — 짝 표는 보고에)
s11() {
  local log code
  if [ "$(git rev-parse HEAD)" = "$BASE" ]; then
    log="$(python3 -I scripts/check_test_weakening.py --warn main HEAD 2>&1)"
  else
    log="$(python3 -I scripts/check_test_weakening.py main HEAD 2>&1)"
  fi
  code=$?
  echo "$log" > "$OUT/s11-weaken.log"
  echo "$log" | tail -3 | sed 's/^/  /'
  return $code
}

s12() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-RPA1.sh" --commit "$COMMIT" 2>&1)"
  echo "$log" > "$OUT/s12-planted.log"
  echo "$log" | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" \
    && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s13() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-433" "Derives-from: MARC-ENT-399" "Derives-from: MARC-ENT-514" "Derives-from: MARC-ENT-381" \
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; do
    grep -q -x -F "$t" "$MSG" || { echo "  ★ 트레일러 없음: $t"; code=1; }
  done
  for t in Constraint Rejected Directive Not-tested; do
    grep -q -E "^$t: " "$MSG" || { echo "  ★ 트레일러 없음: $t:"; code=1; }
  done
  head -1 "$MSG" | grep -q -E "^feat\(drafting\): RPA1 (①|②) " || { echo "  ★ 제목 꼴"; code=1; }
  echo "  제목 $(head -1 "$MSG") · 트레일러 $(grep -c -E '^[A-Z][A-Za-z-]+: ' "$MSG") 줄"
  return $code
}

s14() {
  local log code start
  start=$(date +%s)
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  code=$?
  echo "$log" > "$OUT/s14-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  [ $(( $(date +%s) - start )) -gt 30 ] && echo "  30초 넘음 · $(uptime | sed 's/.*load/load/')"
  [ "$code" = 0 ] && echo "$log" | grep -q "VERIFY_FAST=PASS"
}

step 1 "순수 시험(drafting·core — not django_db) N0 → N1" s1
step 2 "lint-imports 전부 KEPT·수 = 기준" s2
step 3 "check_test_layout" s3
step 4 "pyright drafting 0 · ruff check · ruff format --check" s4
step 5 "경로 §1-2·§1-3 안 · 0줄 목록 · 기존 고침은 ② 에서만 · numstat · bad_minus=0 · 7a sha16" s5
step 6 "기본 바이트 지문 = 기준 트리(git archive)" s6
step 7 "금지 글·키 꼴·바이너리·esg-lab import·실재 기업명 0" s7
step 8 "makemigrations --check --dry-run" s8
step 9 "generated/ 다시 뽑아 cmp · jq 넷 · 기대(경로 여섯·동작 일곱·DraftingAiSetting*) · apps/web typecheck" s9
if [ "$CONTAINERS" = 1 ]; then
  step 10 "업무(drafting·config·core·runs·translation·R9 carrier) · 보안(전부) · -k openapi" s10
else
  not_run 10 "업무·보안(컨테이너)" "--with-containers 없음"
fi
step 11 "WEAKEN(check_test_weakening — 커밋 전엔 --warn)" s11
if [ "$PLANTED" = 1 ]; then step 12 "심은 파손(경계 $COMMIT 몫)" s12; fi
if [ -n "$MSG" ]; then step 13 "커밋 메시지 트레일러(§5)" s13; fi
step 14 "뿌리 verify.sh --fast" s14
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
