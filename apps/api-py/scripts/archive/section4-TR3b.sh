#!/usr/bin/env bash
# 밴드 TR3b(MARC-TICK-251: 영문번역 묶음 목록·문서 하나 보기·[모두 받기] zip — runs selector run_keys·runs_of·
# step_lines_of·results_of 키워드)의 §4 자기검증(발주서 band-handoffs/TR3b-order.md §4).
#   사용: apps/api-py/scripts/section4-TR3b.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --commit n 은 경계 n(그 경계까지의 시험·심은 파손). --with-containers 면 단계 9(업무·보안·문턱)를 돈다 — 안 주면
#   「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0). 심은 파손의 biz:·sec: 줄도 compose postgres 가 떠 있어야 한다.
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 TR3b.out), TR3B_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
TR="$E/translation"
PINNED="$TR/tests/data/flow-shapes"
API_PINNED="$TR/tests/data/api-shapes"
OUT="${S4_OUT:-$ROOT/../TR3b.out}"
FORBIDDEN="${TR3B_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
BASE_CONTRACTS=17
PURE_PATHS="esgapi/translation"
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
echo "── 밴드 TR3b §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

BASE_TREE="$OUT/base-tree"
base_tree() {
  [ -f "$BASE_TREE/.ref" ] && [ "$(cat "$BASE_TREE/.ref")" = "$BASE" ] && return 0
  rm -rf "$BASE_TREE" && mkdir -p "$BASE_TREE"
  git archive "$BASE" "$A" | tar -x -C "$BASE_TREE" || return 1
  echo "$BASE" > "$BASE_TREE/.ref"
}

# §1-2(우리 땅) + §1-3(알리고 하는 공통 줄) + §1-4(청한 줄 — 22·73) — 닫힌 목록
ALLOWED="^$TR/contracts/(batch_shapes|__init__)\.py\$
^$TR/service/(apis/translation|actions/(batches|archive))\.py\$
^$TR/tests/.*
^$A/scripts/(section4|planted-breaks)-TR3b\.sh\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^docs/development\.md\$
^$E/runs/service/selectors/runs\.py\$
^$E/runs/models\.py\$
^$E/runs/tests/service/selectors/test_runs\.py\$
^$E/core/permissions\.py\$
^$E/core/tests/(test_permissions|test_permissions_wiring|test_transaction_rules)\.py\$
^$E/core/tests/isolation/test_static_rules\.py\$
^$E/inventory/tests/test_s3sheets_is_pure\.py\$
^$E/config/tests/(test_api_contract|test_api_errors)\.py\$
^$A/tests/security/(test_tenant_paths|test_login|test_translation|test_operator_company)\.py\$"

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

# 0줄 자리(§1-2 끝·§1-4·§4-2). runs/models.py 는 :62 뒤 한 줄 더함만, selectors/runs.py 는 기존 함수 몸이 기준과 같음
#   (results_of 의 키워드 밖) — 아래 s2 가 따로 잰다.
ZERO="$TR/contracts/options_shapes.py $TR/contracts/digest_shapes.py $TR/contracts/shapes.py $TR/contracts/glossary_shapes.py
$TR/contracts/wire.py $TR/outputs $TR/tools $TR/engines $TR/flows $TR/prompts $TR/apps.py $TR/service/actions/glossary.py
$TR/service/actions/result.py $TR/service/actions/retry_source.py
$PINNED/translation.input@1.schema.json $PINNED/translation.result@1.schema.json $PINNED/translation.digest@1.schema.json
$PINNED/options $E/config/api.py $E/runs/tasks.py $E/runs/migrations $E/runs/service/actions $E/runs/service/apis
$E/runs/service/services apps/web $A/pyproject.toml $A/uv.lock $A/tests_integration $A/conftest.py $A/tests/support
$A/tests/security/conftest.py $A/.importlinter"

s2() {
  local missing=0 p n bad models bodies
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  models="$(git diff --numstat "$BASE" -- "$E/runs/models.py" | cut -f1,2 | tr '\t' ' ')"
  echo "  runs/models.py numstat ${models:-0 0}(허락: 1 0 — :62 뒤 예외 한 줄)"
  case "$models" in "" | "1 0") ;; *) echo "  ★ runs/models.py 가 한 줄 더함 밖으로 바뀜"; bad="$bad models" ;; esac
  # 73 허락(②): test_operator_company.py 는 :147 셈 한 줄(숫자·같은 줄 주석)만
  local toc
  toc="$(git diff --numstat "$BASE" -- "$A/tests/security/test_operator_company.py" | cut -f1,2 | tr '\t' ' ')"
  echo "  test_operator_company.py numstat ${toc:-0 0}(허락: 1 1 — 셈 한 줄, 경계 2 부터)"
  case "$toc" in "" | "1 1") ;; *) echo "  ★ test_operator_company.py 가 셈 한 줄 밖으로 바뀜"; bad="$bad operator_company" ;; esac
  # 67 허락(③): test_s3sheets_is_pure.py 는 순수성 목록 한 줄 더함만
  local pure
  pure="$(git diff --numstat "$BASE" -- "$E/inventory/tests/test_s3sheets_is_pure.py" | cut -f1,2 | tr '\t' ' ')"
  echo "  test_s3sheets_is_pure.py numstat ${pure:-0 0}(허락: 1 0 — 목록 한 줄, 경계 3)"
  case "$pure" in "" | "1 0") ;; *) echo "  ★ test_s3sheets_is_pure.py 가 한 줄 밖으로 바뀜"; bad="$bad s3sheets" ;; esac
  # selectors/runs.py: 기준의 함수·클래스 몸이 그대로(results_of 는 머리와 거름 두 줄 밖 그대로) + 공통 helper 둘
  bodies="$(python3 -I - "$BASE" <<'PYEOF'
import ast, subprocess, sys
base = sys.argv[1]
def show(path):
    return subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True, check=True).stdout
def tops(text):
    tree = ast.parse(text)
    return {n.name: ast.get_source_segment(text, n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
bad = 0
path = "apps/api-py/esgapi/runs/service/selectors/runs.py"
old, new = tops(show(path)), tops(open(path, encoding="utf-8").read())
same = [k for k in old if old[k] == new.get(k)]
moved = [k for k in old if old[k] != new.get(k)]
print(f"  selectors/runs.py 기준 정의 {len(old)} · 그대로 {len(same)} · 바뀜 {moved} · 더함 {sorted(set(new) - set(old))}")
if moved != ["results_of"]:
    bad += 1
else:
    o, n = old["results_of"].splitlines(), new["results_of"].splitlines()
    body_o = o[o.index(next(l for l in o if l.strip().startswith("rows = "))):]
    body_n = [l for l in n[n.index(next(l for l in n if l.strip().startswith("rows = "))):]
              if l.strip() not in ("if schema_versions is not None:", "rows = rows.filter(schema_version__in=schema_versions)")]
    ok = body_o == body_n
    print(f"  results_of 몸(거름 두 줄 밖) {'= 기준' if ok else '★ ≠ 기준'}")
    bad += not ok
for path, name in (("apps/api-py/esgapi/core/tests/test_permissions_wiring.py", "send"),
                   ("apps/api-py/tests/security/test_tenant_paths.py", "send_passing")):
    o, n = tops(show(path)).get(name), tops(open(path, encoding="utf-8").read()).get(name)
    ok = o is not None and o == n
    bad += not ok
    print(f"  {path.rsplit('/', 1)[-1]}::{name} {'= 기준' if ok else '★ ≠ 기준'}")
sys.exit(bad)
PYEOF
)"
  local bcode=$?
  echo "$bodies"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ] && [ "$bcode" -eq 0 ]
}

# 공유·청한 줄: numstat 과 「-」 줄 원문. 셈 파일(COUNTS)의 「-」 줄은 숫자·같은 줄 주석만 다른 「+」 줄이 있어야 한다.
COUNTS="$E/core/tests/test_permissions.py $E/core/tests/test_permissions_wiring.py $E/core/tests/test_transaction_rules.py
$E/core/tests/isolation/test_static_rules.py $E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py
$A/tests/security/test_login.py $A/tests/security/test_tenant_paths.py $A/tests/security/test_translation.py
$A/tests/security/test_operator_company.py $E/runs/tests/service/selectors/test_runs.py"
PERMITTED="$E/runs/service/selectors/runs.py $E/runs/models.py $E/core/permissions.py docs/development.md
$E/inventory/tests/test_s3sheets_is_pure.py"

s3() {
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $COUNTS $PERMITTED | sed 's/^/  numstat /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $PERMITTED > "$OUT/s3-permitted.diff"
  grep -E '^-[^-]' "$OUT/s3-permitted.diff" | sed 's/^/  허락 줄 /'
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
print(f"  셈 파일 「-」 줄 중 허용 밖 {bad}")
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
  [ "$code" = 0 ] && [ -n "$base" ] && [ "${n:-0}" -ge "$base" ]
}

# §4-6: TR2 지문(run·호출 열)과 흐름 지문(주 결과·Word 바이트)을 <기준> 트리로도 내서 견준다 — 전부 같아야 한다.
s6() {
  local digest=esgapi.translation.tests.engines.colab_158.run_digest
  base_tree || return 1
  (cd "$BASE_TREE/$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m "$digest") \
    > "$OUT/s6-digest-base.json" || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m "$digest") > "$OUT/s6-digest-new.json" || return 1
  if cmp -s "$OUT/s6-digest-base.json" "$OUT/s6-digest-new.json"; then
    echo "  run·호출 열·열쇠 길·흐름(결과·Word) 지문 = 기준 ($(shasum -a 256 "$OUT/s6-digest-new.json" | cut -c1-16))"
  else
    echo "  ★ 지문 ≠ 기준"; return 1
  fi
}

s7() {
  local code=0
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/translation/tests/contracts -k "pinned" 2>&1 | tail -1 | sed 's/^/  고정 스키마 /') || code=1
  if [ "$COMMIT" -ge 2 ]; then
    [ -f "$API_PINNED/translation.batch@1.schema.json" ] || { echo "  ★ batch@1 고정 스키마가 없다"; code=1; }
  fi
  if [ "$COMMIT" -lt 2 ]; then
    git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ 경계 $COMMIT 에서 generated/ 가 바뀜"; code=1; }
    echo "  generated/ 0바이트(경계 $COMMIT)"
  else
    s7_generated || code=1
  fi
  return $code
}

# ②·③: generated/ 셋을 다시 뽑아 cmp + <기준> 과의 차이가 경로(②: 둘 · ③: 셋)와 TranslationBatch 로 시작하는 새 schema
#   + digest 세 schema 뿐(바뀐·지운 path·schema 0)인지.
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
  python3 -I - "$g/openapi.base.json" "$A/generated/openapi.json" "$COMMIT" <<'PYEOF' || code=1
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
commit = int(sys.argv[3])
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
want = ["translation_batch_get", "translation_batches_list"] + (["translation_batch_archive"] if commit >= 3 else [])
ok = ids == sorted(want) and not lost and not moved
# digest 세 schema 는 TR3a 의 digest@1 이 응답에 처음 오른 것(감독 65 받음)
digest = {"TranslationDigest", "DigestVariant", "DigestFiles"}
fits = digest <= set(new) and all(k.startswith("TranslationBatch") or k in digest for k in new)
sys.exit(0 if ok and not changed and not rest and fits else 1)
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
  local blog="$OUT/s9-business.log" slog="$OUT/s9-security.log" tlog="$OUT/s9-threshold.log" bcode scode tcode
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s9-up.log" 2>&1 || { tail -3 "$OUT/s9-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/translation \
    esgapi/runs esgapi/config esgapi/core) > "$blog" 2>&1
  bcode=$?
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  # 3-2-7 문턱: 병렬 업무 층에 두지 않고 따로 한 번(TR3B_THRESHOLD=1)
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY TR3B_THRESHOLD=1 scripts/test-business.sh -p no:cacheprovider -s \
    esgapi/translation/tests/service/actions/test_batches_threshold.py) > "$tlog" 2>&1
  tcode=$?
  echo "  업무 $(tail -1 "$blog") EXIT=$bcode · 보안 $(tail -1 "$slog") EXIT=$scode · 문턱 $(tail -1 "$tlog") EXIT=$tcode"
  grep -E "^TR3B_THRESHOLD" "$tlog" | sed 's/^/  /'
  [ "$bcode" = 0 ] && [ "$scode" = 0 ] && [ "$tcode" = 0 ]
}

s10() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-TR3b.sh" --commit "$COMMIT" 2>&1)"
  echo "$log" > "$OUT/s10-planted.log"
  echo "$log" | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s11() {
  local d="$OUT/s11.diff" n_key n_bin n_lab n_name=0
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY')"
  n_bin="$(changed | grep -c -E '\.(pdf|docx|xlsx|zip|ipynb)$')"
  n_lab="$(grep -E '^\+' "$d" | grep -c -E 'esg[_]lab|esg[-]lab/|from esg[l]ab|import esg[l]ab')"  # [ ] = 이 줄 자신을 세지 않게
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴 $n_key · .pdf/.docx/.xlsx/.zip/.ipynb $n_bin · esg-lab import $n_lab · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_lab" = 0 ] && [ "$n_name" = 0 ]
}

step 1 "바뀐 경로가 §1-2~§1-4 안(outside=0)" s1
step 2 "0줄 목록 diff 0 · runs/models.py 한 줄 · selectors 기존 정의 = 기준(results_of 키워드 밖) · 공통 helper 둘" s2
step 3 "공유·청한 줄 numstat·「-」 줄 원문" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "순수 시험(translation — not django_db) 초록·수" s5
step 6 "TR2 지문·흐름 지문(결과·Word 바이트) = 기준 트리(git archive)" s6
step 7 "고정 스키마·generated/" s7
step 8 "뿌리 verify.sh --fast" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "업무·보안·문턱(컨테이너 postgres)" s9
else
  not_run 9 "업무·보안·문턱(컨테이너)" "--with-containers 없음"
fi
step 10 "심은 파손(경계 $COMMIT 몫)" s10
step 11 "추적 diff 의 키 꼴·.pdf/.docx/.xlsx/.zip/.ipynb·esg-lab import·실재 기업명 0" s11
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
