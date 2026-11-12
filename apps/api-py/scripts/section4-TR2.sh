#!/usr/bin/env bash
# 밴드 TR2(MARC-TICK-214: 영문번역을 runs 에 잇기)의 §4 자기검증(발주서 band-handoffs/TR2-order.md §4).
#   사용: apps/api-py/scripts/section4-TR2.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --commit n 은 경계 n(그 경계까지의 시험·심은 파손). --with-containers 면 단계 9(업무·보안)를 돈다 — 경계 ②③ 에서
#   안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0). 경계 ① 은 컨테이너 몫이 없다.
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 TR2.out), TR2_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
TR="$E/translation"
OUT="${S4_OUT:-$ROOT/../TR2.out}"
FORBIDDEN="${TR2_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(4f15ca8)에서 잰 수: 그 트리를 git archive 로 풀어 --collect-only.
#   순수 = pytest esgapi/translation -m "not django_db" 405 · esgapi/runs/tests/calc 24 · lint-imports 계약 17.
# 경계마다 기대 수(늘기만): ① 순수 +50(plan_bounds 11 · remaining_and_shape 7 · retry 4 · run_digest 2 · 다리 캐시 25 ·
#   prompts +1). ② +39(흐름 test_colab_158 21 · 끼움 test_binding_158 18) · env 시험은 config 쪽.
expect_pure() { case "$COMMIT" in 1) echo 455 ;; *) echo 494 ;; esac; }
BASE_PURE=405 BASE_CALC=24 BASE_CONTRACTS=17
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
echo "── 밴드 TR2 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §1-2(영문번역) + §1-3(공유 파일) + §1-4(청한 줄) — 닫힌 목록
ALLOWED="^$TR/engines/colab_158/(plan|pipeline|translate|records|glossary|review|__init__)\.py\$
^$TR/tools/llm_bridge\.py\$
^$TR/prompts/(cell|table-batch|section|polish|editorial-qa|glossary-repair|korean-repair)/2\.md\$
^$TR/prompts/README\.md\$
^$TR/contracts/(__init__|shapes|wire|options_shapes)\.py\$
^$TR/flows/(__init__|colab_158|binding_158|registration)\.py\$
^$TR/apps\.py\$
^$TR/api\.py\$
^$TR/service/.*\.py\$
^README\.md\$
^docs/development\.md\$
^$E/core/tests/test_flows_core_names\.py\$
^$TR/tests/.*
^$A/scripts/(section4|planted-breaks)-TR2\.sh\$
^$E/config/apps_list\.py\$
^$E/config/tests/test_settings\.py\$
^$E/config/api\.py\$
^$E/runs/calc/errors\.py\$
^$E/config/env\.py\$
^$E/config/tests/test_env\.py\$
^$E/core/permissions\.py\$
^$E/core/tests/test_permissions\.py\$
^$E/core/tests/test_permissions_wiring\.py\$
^$E/config/tests/test_api_contract\.py\$
^$E/config/tests/test_api_errors\.py\$
^$E/core/tests/isolation/.*\.py\$
^$E/core/tests/test_selector_scope\.py\$
^$E/core/tests/test_transaction_rules\.py\$
^$A/\.importlinter\$
^$A/tests/security/test_login\.py\$
^$A/tests/security/test_tenant_paths\.py\$
^$A/tests/security/test_translation\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$"

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

# 0줄 자리(§1-3 끝·§1-4 의 0줄·§4-2)
ZERO="$E/core/flows/binding.py $E/runs/tasks.py $E/runs/service/actions/runs.py $E/runs/service $E/runs/models.py
$E/runs/context.py $E/greenwash $A/tests_integration $A/conftest.py $A/tests/support $A/scripts/planted-breaks.sh
$TR/tools/compare_dump.py $TR/tests/engines/colab_158/test_pipeline.py
$TR/tests/data/flow-shapes/translation.input@1.schema.json apps/web $A/uv.lock"

s2() {
  local missing=0 p n bad one
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO;
    git diff --name-only "$BASE" -- "$TR/prompts/*/1.md"; } | sort -u)"
  # core·runs 는 §1-3 표의 파일만(그 밖 0줄)
  one="$(git diff --name-only "$BASE" -- "$E/core" "$E/runs" | grep -v -E \
    "^$E/(core/permissions|core/tests/test_permissions|core/tests/test_permissions_wiring|core/tests/test_selector_scope|core/tests/test_transaction_rules|core/tests/test_flows_core_names|runs/calc/errors)\.py\$|^$E/core/tests/isolation/")"
  bad="$(printf '%s\n%s\n' "$bad" "$one" | grep . | sort -u)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') + prompts/*/1.md + core·runs 표 밖 · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

# 공유·청한 줄: numstat 과 「-」 줄 원문. 「-」 줄은 숫자와 같은 줄 주석만 다른 「+」 줄이 있어야 한다.
SHARED="$E/config/apps_list.py $E/config/tests/test_settings.py $E/config/api.py $E/runs/calc/errors.py $E/config/env.py
$E/config/tests/test_env.py $E/core/permissions.py $E/core/tests/test_permissions.py $E/core/tests/test_permissions_wiring.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py $E/core/tests/isolation $E/core/tests/test_selector_scope.py
$E/core/tests/test_transaction_rules.py $E/core/tests/test_flows_core_names.py $A/.importlinter $A/tests/security/test_login.py
$A/tests/security/test_tenant_paths.py README.md docs/development.md"

s3() {
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $SHARED | sed 's/^/  numstat /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $SHARED > "$OUT/s3.diff"
  python3 -I - "$OUT/s3.diff" <<'PYEOF'
import re, sys
def norm(line):
    line = re.sub(r"#.*$", "", line)
    return re.sub(r"\d+", "N", line).rstrip()
bad = 0
minus, plus = [], []
HEADER = {
    "★ 라우터는 경로가 있는 모듈 다섯(user · organization · inventory · reference · greenwash)과 core(문서)·runs(실행)의": [
        "★ 라우터는 경로가 있는 모듈 여섯(user·organization·inventory·reference·greenwash·translation)과 core(문서)·runs(실행)의"
    ],
    "  core 의 문서 경로는 /documents 에, runs 의 실행 경로는 /runs 에, greenwash 는 /greenwash 에 걸려 있고 이 셋에는": [
        "  core 의 문서 경로는 /documents 에, runs 의 실행 경로는 /runs 에, greenwash 는 /greenwash 에,",
        "  translation 은 /translation 에 걸려 있고 이 넷에는",
    ],
}
def flush():
    global bad, minus, plus
    pool = [norm(p) for p in plus]
    for m in minus:
        print(f"  - {m}")
        # 감독 8a 허락(10-21): 업무 모듈 목록에 이름 하나 더하기(core/tests/test_flows_core_names.py)
        widened = m.replace('"greenwash", "runs"', '"greenwash", "translation", "runs"')
        if m.startswith("BUSINESS = (") and widened != m and widened in plus:
            print("    (감독 8a 허락 — 이름 하나 더함)")
            plus.remove(widened)
            continue
        header = HEADER.get(m)  # §1-3: config/api.py 머리말 :3(다섯 → 여섯)·:8(/translation) — 글 그대로 대조
        if header is not None and all(h in plus for h in header):
            print("    (§1-3 머리말 :3·:8)")
            for h in header:
                plus.remove(h)
            continue
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
print(f"  「-」 줄 중 허용 밖 {bad}")
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
  local log n calc code1 code2
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest esgapi/translation -m "not django_db" -q -p no:cacheprovider 2>&1)"
  code1=$?
  echo "$log" > "$OUT/s5-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest esgapi/runs/tests/calc -q -p no:cacheprovider 2>&1)"
  code2=$?
  calc="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  순수 translation ${n:-?} 통과(기준 $BASE_PURE → 기대 $(expect_pure)) EXIT=$code1 · runs/tests/calc ${calc:-?}(기준 $BASE_CALC) EXIT=$code2"
  [ "$code1" = 0 ] && [ "$code2" = 0 ] && [ "${n:-0}" = "$(expect_pure)" ] && [ "${calc:-0}" -ge "$BASE_CALC" ]
}

# 3-1-5: run 지문(asdict·호출 열 sha256)을 <기준> 트리의 엔진으로도 내서 견준다(상수 박기 0)
s6() {
  local base="$OUT/s6-base" digest=esgapi.translation.tests.engines.colab_158.run_digest
  rm -rf "$base" && mkdir -p "$base"
  git archive "$BASE" "$A" | tar -x -C "$base" || return 1
  cp "$TR/tests/engines/colab_158/run_digest.py" "$base/$TR/tests/engines/colab_158/run_digest.py"
  (cd "$base/$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m "$digest") \
    > "$OUT/s6-digest-base.json" || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m "$digest") > "$OUT/s6-digest-new.json" || return 1
  python3 -I - "$OUT/s6-digest-base.json" "$OUT/s6-digest-new.json" <<'PYEOF'
import json, sys
base, new = (json.load(open(p)) for p in sys.argv[1:3])
bad = 0
for case in base:
    if case == "keys":
        continue
    for part in ("run", "calls"):
        same = base[case][part] == new[case][part]
        bad += not same
        print(f"  {case} {part} {new[case][part][:16]} {'= 기준' if same else '★ ≠ 기준 ' + base[case][part][:16]}")
added = sorted(set(new["keys"]) - set(base["keys"]))
lost = sorted(set(base["keys"]) - set(new["keys"]))
print(f"  열쇠 더함 {added} · 잃음 {lost}")
ok = added == ["run.variants[].fragments[].remaining_korean"] and not lost
sys.exit(0 if bad == 0 and ok else 1)
PYEOF
}

s7() {
  local code=0
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/translation/tests/contracts/test_shapes.py 2>&1 | tail -1 | sed 's/^/  고정 스키마 /') || code=1
  git diff --quiet "$BASE" -- "$TR/tests/data/flow-shapes/translation.input@1.schema.json" || { echo "  ★ input@1 고정 스키마가 바뀜"; code=1; }
  if [ "$COMMIT" -lt 3 ]; then
    git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ 경계 $COMMIT 에서 generated/ 가 바뀜"; code=1; }
    echo "  generated/ 0바이트(경계 $COMMIT)"
  else
    s7_generated || code=1
  fi
  return $code
}

# ③: generated/ 셋을 다시 뽑아 cmp(gen-ts-types.sh 와 같은 명령 — 커밋된 것을 덮지 않고 $OUT 에) + <기준> 과의 차이가
#   경로 하나(translation_result_get)와 새 schema 뿐(바뀐·지운 path·schema 0)인지.
s7_generated() {
  local g="$OUT/s7-generated" code=0
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi) \
    > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
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
ids = [op.get("operationId") for p in added for op in b["paths"][p].values()]
print(f"  path 더함 {added} {ids} · 지움 {lost} · 바뀜 {moved}")
print(f"  schema 더함 {len(new)}({', '.join(new)}) · 바뀜·지움 {changed} · 그 밖 {rest}")
ok = added == ["/translation/runs/{run_id}/result"] and ids == ["translation_result_get"] and not lost and not moved
sys.exit(0 if ok and not changed and not rest and "TranslationDone" in new and "TranslationRejected" in new else 1)
PYEOF
  return $code
}

s8() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s8-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s9() {
  local blog="$OUT/s9-business.log" slog="$OUT/s9-security.log" bcode scode
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s9-up.log" 2>&1 || { tail -3 "$OUT/s9-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/translation \
    esgapi/runs esgapi/config esgapi/core esgapi/greenwash/tests/test_apps.py esgapi/greenwash/tests/test_apps_binding.py) \
    > "$blog" 2>&1
  bcode=$?
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  echo "  업무 $(tail -1 "$blog") EXIT=$bcode · 보안 $(tail -1 "$slog") EXIT=$scode"
  [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s10() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-TR2.sh" --commit "$COMMIT" 2>&1)"
  echo "$log" > "$OUT/s10-planted.log"
  echo "$log" | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s11() {
  local d="$OUT/s11.diff" n_key n_bin n_lab n_name=0
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY')"
  n_bin="$(changed | grep -c -E '\.(pdf|docx|ipynb)$')"
  n_lab="$(grep -E '^\+' "$d" | grep -c -E 'esg[_]lab|esg[-]lab/|from esg[l]ab|import esg[l]ab')"  # [ ] = 이 줄 자신을 세지 않게
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴 $n_key · .pdf/.docx/.ipynb $n_bin · esg-lab import $n_lab · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_lab" = 0 ] && [ "$n_name" = 0 ]
}

step 1 "바뀐 경로가 §1-2~§1-4 안(outside=0)" s1
step 2 "0줄 목록 diff 0" s2
step 3 "공유·청한 줄 numstat·「-」 줄 원문" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "순수 시험(translation not django_db · runs calc) 초록·수" s5
step 6 "run 지문 sha256 = 기준 트리(git archive)" s6
step 7 "고정 스키마·generated/" s7
step 8 "뿌리 verify.sh --fast" s8
if [ "$COMMIT" = 1 ]; then
  if [ -z "$ONLY" ] || [ "$ONLY" = 9 ]; then echo "[9] 업무·보안(컨테이너) — 경계 ① 몫 없음 EXIT=0"; fi
elif [ "$CONTAINERS" = 1 ]; then
  step 9 "업무·보안(컨테이너 postgres)" s9
else
  not_run 9 "업무·보안(컨테이너)" "--with-containers 없음"
fi
step 10 "심은 파손(경계 $COMMIT 몫)" s10
step 11 "추적 diff 의 키 꼴·.pdf/.docx/.ipynb·esg-lab import·실재 기업명 0" s11
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
