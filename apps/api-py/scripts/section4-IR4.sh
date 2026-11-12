#!/usr/bin/env bash
# 밴드 IR4(MARC-TICK-344: 중대성평가 IRO AI 설정 — 엔진이 템플릿 글·칸 모델 값을 받음 · 판 표·경로 일곱·
# ai.prompt-model@3 · 실행이 적용 판으로 부름)의 §4 자기검증(발주서 band-handoffs/IR4-order.md §4·부록 §4).
# 틀은 section4-DVA1.sh.
#   사용: apps/api-py/scripts/section4-IR4.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --with-containers 면 단계 11(업무·보안)을 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 IR4.out), IR4_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
MA="$E/materiality"
EN="$MA/engines/colab_155"
FL="$MA/flows"
OUT="${S4_OUT:-$ROOT/../IR4.out}"
FORBIDDEN="${IR4_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
PURE_PATHS="esgapi/materiality esgapi/core esgapi/dataverify esgapi/translation"
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
# 계약 수도 <기준> 에서 읽는다 — IR4 는 계약을 더하지 않는다(54a38aaa 17 → main 병합 뒤 e8e73e17 18)
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 IR4 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# 기준 트리(git archive) — 단계 5·6 이 쓴다
BASE_TREE="$OUT/base-tree"
base_tree() {
  [ -f "$BASE_TREE/.ref" ] && [ "$(cat "$BASE_TREE/.ref")" = "$BASE" ] && return 0
  rm -rf "$BASE_TREE" && mkdir -p "$BASE_TREE"
  git archive "$BASE" "$A" | tar -x -C "$BASE_TREE" || return 1
  echo "$BASE" > "$BASE_TREE/.ref"
}

# §1-2(중대성평가 닫힌 목록, 누적) + 허락 청(부록 §1-6 — e5·61). 경계 ① 은 엔진·흐름·README·시험·스크립트만 쓴다.
ALLOWED_1="^$EN/(prompts|part2_prompts|texts)\.py\$
^$FL/(colab_155|part2_155|iro_155|binding_155)\.py\$
^$MA/prompts/README\.md\$
^$MA/tests/.*
^$A/scripts/(section4|planted-breaks)-IR4\.sh\$
^$A/scripts/materiality_compare_ir(1b|2a|2b)\.py\$"
ALLOWED_2="^$FL/prompt_model_155\.py\$
^$MA/contracts/ai_setting_shapes\.py\$
^$MA/models\.py\$
^$MA/migrations/(__init__|0001_ai_settings)\.py\$
^$MA/service/(selectors|services)/(__init__|ai_settings)\.py\$
^$MA/service/(actions|apis)/ai_settings\.py\$
^$MA/api\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^docs/development\.md\$
^$E/core/permissions\.py\$
^$E/core/tests/(test_permissions|test_permissions_wiring|test_transaction_rules|test_selector_scope)\.py\$
^$E/core/tests/isolation/(test_static_rules|test_managers)\.py\$
^$E/runs/tests/test_extras\.py\$
^$E/config/api\.py\$
^$E/config/tests/(test_api_contract|test_api_errors|test_request_schemas_reject_bool)\.py\$
^$A/tests/security/(test_tenant_paths|test_login|test_owner|test_materiality_ai_settings|test_operator_company)\.py\$
^$A/tests/security/(test_migrations|test_same_company_foreign_keys|test_request_transactions)\.py\$"
ALLOWED_3="^$MA/service/selectors/run_extras\.py\$
^$MA/apps\.py\$"
ALLOWED="$ALLOWED_1"
[ "$COMMIT" -ge 2 ] && ALLOWED="$ALLOWED
$ALLOWED_2"
[ "$COMMIT" -ge 3 ] && ALLOWED="$ALLOWED
$ALLOWED_3"

s1() {
  local all outside pattern
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ]
}

# 0줄 자리(§1-2 끝 「0줄로 초록」 · §1-4 0바이트 중 파일·폴더 통째인 것). core·runs·config 는 허락 청 밖 0줄(아래 s2).
ZERO="$MA/contracts/shapes.py $MA/contracts/wire.py $MA/contracts/options_shapes.py $MA/contracts/digest_shapes.py
$MA/contracts/run_list_shapes.py $MA/tests/data/flow-shapes/options $MA/tests/data/examples
$EN/constants.py $EN/inputs.py $EN/outcomes.py $EN/parsing.py $EN/part2_parsing.py $EN/part2_render.py $EN/whitelists.py
$MA/outputs $MA/service/actions/runs.py $MA/service/actions/result.py $MA/service/apis/materiality.py
$MA/prompts/regulation/1.md $MA/prompts/keywords/1.md $MA/prompts/controversy/1.md $MA/prompts/impact/1.md
$MA/prompts/financial/1.md $MA/prompts/pathway/1.md $FL/registration.py
$MA/tests/engines/colab_155/test_prompts.py $MA/tests/engines/colab_155/test_part2_prompts.py
$MA/tests/engines/colab_155/test_whitelists.py $MA/tests/test_part1.py $MA/tests/outputs
$E/user $E/greenwash $E/translation $E/dataverify apps/web $A/.importlinter $A/conftest.py $A/tests/support $A/tests_integration
$A/uv.lock"
# 허락 청 밖 0줄: core·runs·config(허락 파일 밖) · tests/data/flow-shapes 맨 폴더의 *.schema.json.
PERMITTED_FILES="$E/core/permissions.py
$E/core/tests/test_permissions.py
$E/core/tests/test_permissions_wiring.py
$E/core/tests/test_transaction_rules.py
$E/core/tests/test_selector_scope.py
$E/core/tests/isolation/test_static_rules.py
$E/core/tests/isolation/test_managers.py
$E/runs/tests/test_extras.py
$E/config/api.py
$E/config/tests/test_api_contract.py
$E/config/tests/test_api_errors.py
$E/config/tests/test_request_schemas_reject_bool.py"
s2() {
  local missing=0 p n bad fenced
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  fenced="$( { git diff --name-only "$BASE" -- "$E/core" "$E/runs" "$E/config"; \
    git ls-files -o --exclude-standard --full-name -- "$E/core" "$E/runs" "$E/config"; } | sort -u)"
  if [ "$COMMIT" -ge 2 ]; then
    fenced="$(echo "$fenced" | grep -v -x -F -f <(echo "$PERMITTED_FILES"))"
  fi
  top="$( { git diff --name-only "$BASE" -- "$MA/tests/data/flow-shapes"; \
    git ls-files -o --exclude-standard --full-name -- "$MA/tests/data/flow-shapes"; } | grep -E "^$MA/tests/data/flow-shapes/[^/]+\$")"
  bad="$(printf '%s\n%s\n%s\n' "$bad" "$fenced" "$top" | grep . | sort -u)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  # 「기존 고침」(§1-2): test_binding_155(versions_with 단언·생성자)·test_apps 는 경계 ③ 에서만 바뀐다.
  if [ "$COMMIT" -lt 3 ]; then
    for p in "$MA/tests/flows/test_binding_155.py" "$MA/tests/test_apps.py"; do
      git diff --quiet "$BASE" -- "$p" || { echo "  ★ 경계 $COMMIT 에서 바뀜: $p"; bad="$bad x"; }
    done
  fi
  [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

# 공유·청한 줄: numstat 과 「-」 줄 원문. 셈 파일(COUNTS)의 「-」 줄은 숫자·같은 줄 주석만 다른 「+」 줄이 있어야 한다.
COUNTS="$E/core/tests/test_permissions.py $E/core/tests/test_permissions_wiring.py $E/core/tests/test_transaction_rules.py
$E/core/tests/test_selector_scope.py $E/core/tests/isolation/test_static_rules.py $E/core/tests/isolation/test_managers.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py $E/config/tests/test_request_schemas_reject_bool.py
$A/tests/security/test_login.py $A/tests/security/test_tenant_paths.py $A/tests/security/test_owner.py
$A/tests/security/test_operator_company.py $A/tests/security/test_migrations.py
$A/tests/security/test_same_company_foreign_keys.py $A/tests/security/test_request_transactions.py"
PERMITTED="$E/core/permissions.py $E/config/api.py $E/runs/tests/test_extras.py docs/development.md"
# 우리 땅의 기존 파일 중 「-」 줄을 보고에 찍는 것(발주서 §1-2 「기존 고침」·흐름·엔진의 바뀐 줄)
OWN_EXISTING="$MA/tests/flows/test_binding_155.py $MA/tests/flows/test_runs_materiality.py $MA/tests/flows/support.py
$MA/tests/flows/test_colab_155.py $MA/tests/flows/test_part2_155.py $MA/tests/flows/test_iro_155.py
$MA/tests/engines/colab_155/test_purity.py $MA/tests/test_apps.py
$A/scripts/materiality_compare_ir1b.py $A/scripts/materiality_compare_ir2a.py $A/scripts/materiality_compare_ir2b.py
$MA/prompts/README.md $MA/api.py $MA/apps.py"

s3() {
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $COUNTS $PERMITTED $OWN_EXISTING | sed 's/^/  numstat /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $PERMITTED $OWN_EXISTING > "$OUT/s3-permitted.diff"
  grep -E '^(\+\+\+ |-[^-])' "$OUT/s3-permitted.diff" | sed 's/^/  허락·기존 고침 /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $COUNTS > "$OUT/s3.diff"
  python3 -I - "$OUT/s3.diff" <<'PYEOF'
import re, sys
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
print(f"  셈 파일 「-」 줄 중 허용 밖 {bad} — bad_minus={bad}")
sys.exit(1 if bad else 0)
PYEOF
}

s4() {
  local log kept broken
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen lint-imports 2>&1)"
  echo "$log" | tail -3 | sed 's/^/  /'
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\2/p')"
  echo "  계약 KEPT ${kept:-?} (기준 $BASE_CONTRACTS) · broken ${broken:-?}"
  [ "${kept:-0}" = "$BASE_CONTRACTS" ] && [ "${broken:-1}" = 0 ]
}

s5() {
  local log n base code
  base_tree || return 1
  # shellcheck disable=SC2086
  base="$(cd "$BASE_TREE/$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$ROOT/$A/.venv/bin/python" -m pytest $PURE_PATHS \
    -m "not django_db" -q -p no:cacheprovider --collect-only 2>&1 | tail -1 | sed -n 's/^\([0-9]*\)\/*[0-9]* *tests* .*/\1/p')"
  # shellcheck disable=SC2086
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest $PURE_PATHS -m "not django_db" -q -p no:cacheprovider 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  순수($PURE_PATHS) ${n:-?} 통과 · 기준 트리 ${base:-?} 개 EXIT=$code"
  [ "$code" = 0 ] && [ -n "$base" ] && [ "${n:-0}" -gt "$base" ]
}

# 6: IR4 지문(texts_digest — 기본 글·코드 모델 값의 공급사 요청 몸·결과·엑셀 둘 칸 값·어림)을 <기준> 트리로도 내서
#   견준다. 통째로 같아야 한다. ③ 부터 실행 길(binding 의 inputs ↔ inputs_with) 지문도 같은 파일이 낸다.
s6() {
  base_tree || return 1
  cp "$MA/tests/flows/texts_digest.py" "$BASE_TREE/$MA/tests/flows/texts_digest.py"
  (cd "$BASE_TREE/$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH=. "$ROOT/$A/.venv/bin/python" \
    -m esgapi.materiality.tests.flows.texts_digest) > "$OUT/s6-texts_digest-base.txt" || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m esgapi.materiality.tests.flows.texts_digest) \
    > "$OUT/s6-texts_digest-new.txt" || return 1
  echo "  지문 줄 $(grep -c . "$OUT/s6-texts_digest-new.txt") · 호출 $(grep ' calls ' "$OUT/s6-texts_digest-new.txt" | awk '{print $1"="$3}' | paste -sd' ' -)"
  if diff "$OUT/s6-texts_digest-base.txt" "$OUT/s6-texts_digest-new.txt" | sed 's/^/  ★ /'; then
    echo "  texts_digest = 기준"
  else
    return 1
  fi
}

s7() {
  local code=0
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/materiality/tests/contracts 2>&1 | tail -1 | sed 's/^/  계약 시험 /') || code=1
  if [ "$COMMIT" -lt 2 ]; then
    git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ 경계 $COMMIT 에서 generated/ 가 바뀜"; code=1; }
    echo "  generated/ 0바이트(경계 $COMMIT)"
  else
    s7_pinned || code=1
    s7_generated || code=1
  fi
  return $code
}

# ②③: 판 꼴 고정 스키마 셋(tests/data/flow-shapes/ai-setting) — 있고 꼴 시험이 글자째 견준다.
PINNED_AI="$MA/tests/data/flow-shapes/ai-setting"
s7_pinned() {
  local f code=0
  for f in materiality.ai-settings@1 materiality.ai-setting@1 materiality.ai-setting-default@1; do
    [ -f "$PINNED_AI/$f.schema.json" ] || { echo "  ★ $f 고정 스키마가 없다"; code=1; }
  done
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/materiality/tests/contracts/test_ai_setting_shapes.py 2>&1 | tail -1 | sed 's/^/  판 꼴 고정 스키마 /'; \
    exit "${PIPESTATUS[0]}") || code=1
  return $code
}

# ②③: generated/ 셋을 다시 뽑아 cmp(gen-ts-types.sh 와 같은 명령 — 커밋된 것을 덮지 않고 $OUT 에) + <기준> 과의 차이가
#   /ai-settings/materiality 경로(동작 일곱)와 MaterialityAiSetting* 뿐(바뀐·지운 0 — 기존 Ai*·다른 모듈 값 그대로).
s7_generated() {
  local g="$OUT/s7-generated" code=0 f
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
  done
  git show "$BASE:$A/generated/openapi.json" > "$g/openapi.base.json"
  python3 -I - "$g/openapi.base.json" "$A/generated/openapi.json" <<'PYEOF' || code=1
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
print(f"  path 더함 {added} {ids} · 지움 {lost} · 바뀜 {moved}")
print(f"  schema 더함 {len(new)}({', '.join(new)}) · 바뀜·지움 {changed} · 그 밖 {rest}")
ok = all(p.startswith("/ai-settings/materiality") for p in added) and len(added) == 6
ok = ok and ids == sorted(f"materiality_ai_setting_{n}" for n in (
    "list", "default", "get", "create", "apply", "prompt_model", "default_prompt_model"))
ok = ok and not lost and not moved and not changed and not rest
ok = ok and all(k.startswith("MaterialityAiSetting") for k in new)
sys.exit(0 if ok else 1)
PYEOF
  return $code
}

s8() {
  if [ "$COMMIT" -lt 2 ]; then
    echo "  경계 $COMMIT — 마이그레이션 없음(M/migrations 0 파일)"
    [ "$(git ls-files -o --exclude-standard --full-name -- "$MA/migrations" | grep -c .)" = 0 ] \
      && git diff --quiet "$BASE" -- "$MA/migrations"
    return $?
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s9() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s10() {
  local log code=0
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s10-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS" || code=1
  if [ "$COMMIT" -ge 2 ]; then
    (cd apps/web && pnpm -s typecheck > "$OUT/s10-web-typecheck.log" 2>&1) || { echo "  ★ apps/web typecheck"; code=1; }
    echo "  apps/web typecheck $(tail -1 "$OUT/s10-web-typecheck.log")"
  fi
  return $code
}

s11() {
  local blog="$OUT/s11-business.log" slog="$OUT/s11-security.log" bcode scode
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s11-up.log" 2>&1 || { tail -3 "$OUT/s11-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/materiality \
    esgapi/core esgapi/config esgapi/runs esgapi/user) > "$blog" 2>&1
  bcode=$?
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  echo "  업무 $(tail -1 "$blog") EXIT=$bcode · 보안 $(tail -1 "$slog") EXIT=$scode"
  [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s12() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-IR4.sh" --commit "$COMMIT" 2>&1)"
  echo "$log" > "$OUT/s12-planted.log"
  echo "$log" | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s13() {
  local d="$OUT/s13.diff" n_key n_bin n_lab n_name=0
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY')"
  n_bin="$(changed | grep -c -E '\.(pdf|docx|xlsx|ipynb)$')"
  n_lab="$(grep -E '^\+' "$d" | grep -c -E 'esg[_]lab|esg[-]lab/|from esg[l]ab|import esg[l]ab')"  # [ ] = 이 줄 자신을 세지 않게
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴 $n_key · .pdf/.docx/.xlsx/.ipynb $n_bin · esg-lab import $n_lab · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_lab" = 0 ] && [ "$n_name" = 0 ]
}

step 1 "바뀐 경로가 §1-2·허락 청 안(outside=0)" s1
step 2 "§1-4·0줄 diff 0 · core·runs·config 는 허락 파일만 · 기존 고침은 ③ 에서만" s2
step 3 "공유 줄 numstat·「-」 줄 원문(bad_minus=0)" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "순수 시험(materiality·core·dataverify·translation — not django_db) 초록·수 늘기만" s5
step 6 "IR4 지문(기본 글·코드 모델 값의 요청·결과·엑셀 둘·어림) = 기준 트리(git archive)" s6
step 7 "generated/·고정 스키마" s7
step 8 "makemigrations --check --dry-run" s8
step 9 "check_test_layout" s9
step 10 "뿌리 verify.sh --fast(②③ + apps/web typecheck)" s10
if [ "$CONTAINERS" = 1 ]; then
  step 11 "업무·보안(컨테이너 postgres)" s11
elif [ "$COMMIT" -lt 2 ]; then
  if [ -z "$ONLY" ] || [ "$ONLY" = 11 ]; then echo "[11] 업무·보안(컨테이너) — 경계 ① 은 발주서 §4-11 밖 EXIT=0 0s"; fi
else
  not_run 11 "업무·보안(컨테이너)" "--with-containers 없음"
fi
step 12 "심은 파손(경계 $COMMIT 몫)" s12
step 13 "추적 diff 의 키 꼴·.pdf/.docx/.xlsx/.ipynb·esg-lab import·실재 기업명 0" s13
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
