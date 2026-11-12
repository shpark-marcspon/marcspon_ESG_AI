#!/usr/bin/env bash
# 밴드 DV1g(MARC-TICK-275: 데이터 검증 실행 목록 GET /dataverify/runs · 요약 dataverify.digest@1 · 거름)의 §4 자기검증
# (발주서 band-handoffs/DV1g-order.md §4).
#   사용: apps/api-py/scripts/section4-DV1g.sh [--commit <1|2|3>] [--with-containers] [--step <n>]
#   --commit 은 경계(기본 3 — 끝판). 경계마다 기대 수·허락 줄·generated 의 판정이 다르다.
#   --with-containers 면 단계 10(업무·보안 층)을 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 DV1g.out), DV1g_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
DV="$E/dataverify"
FS="$DV/tests/data/flow-shapes"
S="$A/tests/security"
OUT="${S4_OUT:-$ROOT/../DV1g.out}"
FORBIDDEN="${DV1g_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; COMMIT=3
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 [--commit <1|2|3>] [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
# <기준>(4182f848)에서 잰 수: 순수 = pytest esgapi/dataverify -m "not django_db" 449(+ core 권한·config 계약의 순수 몫은
# 단계 5 가 따로 찍는다). 기대(늘기만): ① +33(test_digest_shapes 22 · test_digest 11) · ② +11(test_run_list_shapes).
case "$COMMIT" in
  1) EXPECT_PURE=482 EXPECT_PLANTED=4 ;;
  2) EXPECT_PURE=493 EXPECT_PLANTED=15 ;;
  3) EXPECT_PURE=493 EXPECT_PLANTED=17 ;;
  *) echo "--commit 은 1·2·3" >&2; exit 2 ;;
esac
BASE_PURE=449
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 DV1g §4 · 경계 $COMMIT · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

changed() {  # <기준> 뒤 바뀐 경로(추적 diff + 추적 안 된 새 파일)
  { git diff --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-2 수정 허용(닫힌 목록) + §1-3 허락 줄의 파일(줄 단위 판정은 단계 3)
DV_ALLOWED='apps/api-py/esgapi/dataverify/(contracts/(digest_shapes|run_list_shapes)\.py|outputs/digest\.py|flows/colab_156\.py|service/actions/runs\.py|service/apis/dataverify\.py|tests/.*)|apps/api-py/scripts/(section4|planted-breaks)-DV1g\.sh|README\.md|docs/development\.md'
SHARED=("$E/core/permissions.py" "$E/core/tests/test_permissions.py" "$E/core/tests/test_permissions_wiring.py"
  "$E/core/tests/test_transaction_rules.py" "$E/config/tests/test_api_contract.py" "$E/config/tests/test_api_errors.py"
  "$E/runs/service/selectors/runs.py" "$E/runs/tests/service/selectors/test_runs.py"
  "$S/test_tenant_paths.py" "$S/test_login.py" "$S/test_operator_company.py" "$S/test_dataverify.py")
SHARED_RE="$(printf '%s|' "${SHARED[@]}" | sed 's/\./\\./g; s/|$//')"
ALLOWED="^(${DV_ALLOWED}|${SHARED_RE}|apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256))$"

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · outside=$outside"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

# §1-2 「0바이트」·§1-3 의 0줄 목록 + greenwash·translation·apps/web · §1-4 의 테스트 감독 몫
ZERO=("$DV/engines" "$DV/prompts" "$DV/contracts/shapes.py" "$DV/contracts/wire.py" "$DV/contracts/options_shapes.py"
  "$DV/flows/binding_156.py" "$DV/flows/registration.py" "$DV/outputs/xlsx.py" "$DV/service/actions/result.py"
  "$DV/apps.py" "$DV/api.py" "$FS/dataverify.input@1.schema.json" "$FS/dataverify.result@2.schema.json" "$FS/options"
  "$DV/tests/data/examples" "$E/user" "$E/config/api.py" "$A/.importlinter" "$E/core/tests/test_flows_core_names.py"
  "$E/runs/models.py" "$E/runs/service/apis" "$E/runs/service/schemas" "$E/runs/service/actions"
  "$E/greenwash" "$E/translation" apps/web "$A/tests_integration" "$A/conftest.py" "$A/tests/support"
  "$S/conftest.py" "$S/seed.py")

s2() {
  local n
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  echo "  0줄 목록 바뀐 파일 $n"
  git diff --name-only "$BASE" -- "${ZERO[@]}" | sed 's/^/  ★ /'
  [ "$n" = 0 ]
}

# §1-3 허락 줄: 경계 ① 은 그 파일 전부 0줄. ②③ 은 numstat 을 찍고, `-` 줄은 짝 `+` 줄과 숫자·같은 줄 주석만 다르거나
# DATAVERIFY_OPERATIONS 줄·runs 머리말 서명 줄(:6)이어야 한다. 흐름 colab_156.py 는 report 의 결과 목록·result_shapes·
# import·머리말 줄만(`-` 둘).
s3() {
  local code=0 n
  if [ "$COMMIT" = 1 ]; then
    n="$(git diff --name-only "$BASE" -- "${SHARED[@]}" "$A/generated" | grep -c .)"
    echo "  경계 ① — 허락 줄 파일 바뀜 $n(0 이어야)"
    [ "$n" = 0 ] || code=1
  else
    git diff --numstat "$BASE" -- "${SHARED[@]}" | sed 's/^/  numstat /'
    git diff -U0 "$BASE" -- "${SHARED[@]}" > "$OUT/s3-shared.diff"
    (cd "$A" && uv run --frozen python - "$OUT/s3-shared.diff") <<'PYEOF' || code=1
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
bad = 0
for hunk in re.split(r"^@@.*$", text, flags=re.M)[1:]:
    minus = [l[1:] for l in hunk.splitlines() if l.startswith("-") and not l.startswith("---")]
    plus = [l[1:] for l in hunk.splitlines() if l.startswith("+") and not l.startswith("+++")]
    def norm(line: str) -> str:
        return re.sub(r"[0-9]+", "#", line.split("  #")[0]).rstrip()
    for line in minus:
        ok = "DATAVERIFY_OPERATIONS" in line or line.startswith("    run_page(company_id, module, status, document_id")
        ok = ok or line.startswith("    company    둘 다 — 회사 업무(")  # core/permissions.py:7 머리말(e5 표)
        ok = ok or any(norm(line) == norm(p) for p in plus)
        if not ok:
            bad += 1
            print(f"  ★ 허락 밖 - 줄: {line.strip()[:100]}")
print(f"  허락 밖 - 줄 {bad}")
sys.exit(1 if bad else 0)
PYEOF
  fi
  local flow_minus
  flow_minus="$(git diff -U0 "$BASE" -- "$DV/flows/colab_156.py" | grep -v '^---' | grep -c '^-')"
  echo "  colab_156.py - 줄 $flow_minus(report 결과 목록·result_shapes·머리말 = 3)"
  [ "$flow_minus" -le 3 ] || code=1
  git diff -U0 "$BASE" -- "$DV/flows/colab_156.py" | grep -v '^---' | grep '^-' | sed 's/^/    /'
  return $code
}

s4() {
  local log kept broken base
  base="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
  log="$(cd "$A" && uv run --frozen lint-imports 2>&1)"
  echo "$log" > "$OUT/s4-lint-imports.log"
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\2/p')"
  echo "  kept=$kept broken=$broken (기준 계약 $base)"
  [ "$kept" = "$base" ] && [ "$broken" = 0 ]
}

s5() {
  local log n code clog ccode
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/dataverify \
    -m "not django_db" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  dataverify 순수 $(echo "$log" | tail -1) · 기준 $BASE_PURE → 기대 $EXPECT_PURE"
  clog="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db" \
    esgapi/core/tests/test_permissions.py esgapi/config/tests/test_api_contract.py 2>&1)"
  ccode=$?
  echo "$clog" > "$OUT/s5-core-config.log"
  echo "  core 권한·config 계약(순수 몫) $(echo "$clog" | tail -1) EXIT=$ccode"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ] && [ "$ccode" = 0 ]
}

# 고정 스키마 다시 뽑아 cmp + 흐름의 result@2 가 <기준> 흐름과 바이트 같음(§3-1-2 — 흐름 시험의 모의 실행마다 첫 결과를
# JSON 으로 떠서 <기준> 나무(git archive)와 견준다)
s6() {
  local code=0 g="$OUT/s6-shapes" bt="$OUT/s6-base-tree"
  rm -rf "$g" "$bt" && mkdir -p "$g/head" "$g/base" "$bt"
  (cd "$A" && uv run --frozen python - "$g" <<'PYEOF') || return 1
import json, sys
from pathlib import Path
from esgapi.dataverify.contracts import digest_shapes, options_shapes, shapes
out = Path(sys.argv[1])
every = {**shapes.INPUT_SHAPES, **shapes.RESULT_SHAPES, **digest_shapes.DIGEST_SHAPES, **options_shapes.OPTIONS_SHAPES}
for name, adapter in every.items():
    (out / f"{name}.schema.json").write_text(json.dumps(adapter.json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PYEOF
  for pair in "dataverify.options@1 options/" "dataverify.input@1 " "dataverify.result@2 " "dataverify.digest@1 "; do
    set -- $pair
    if cmp -s "$g/$1.schema.json" "$FS/${2:-}$1.schema.json"; then echo "  cmp $1 = 고정 파일"; else echo "  ★ cmp $1 ≠ 고정 파일"; code=1; fi
  done
  git diff --quiet "$BASE" -- "$FS/dataverify.input@1.schema.json" "$FS/dataverify.result@2.schema.json" "$FS/options" \
    && echo "  input@1·result@2·options@1 = 기준" || { echo "  ★ input@1·result@2·options@1 이 기준과 다름"; code=1; }
  git archive "$BASE" "$A" | tar -x -C "$bt" || { echo "  ★ git archive 실패"; return 1; }
  cat > "$g/dump_plugin.py" <<'PYEOF'
"""흐름 시험이 run_flow 를 부를 때마다 첫 결과(result@2)를 JSON 글자로 뜬다(시험 이름·차례가 열쇠)."""
import json, os
from pathlib import Path

OUT = Path(os.environ["DV1G_DUMP"])


def pytest_configure(config):
    import esgapi
    from esgapi.dataverify.tests.flows import support
    (OUT / "esgapi-path.txt").write_text(esgapi.__file__, encoding="utf-8")
    real = support.run
    seen = {}

    def run(given, llm):
        done = real(given, llm)
        name = os.environ.get("PYTEST_CURRENT_TEST", "?").split(" ")[0].replace("/", "_").replace("::", "__")
        seen[name] = seen.get(name, 0) + 1
        first = done.output.results[0]
        (OUT / f"{name}-{seen[name]}.json").write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
        return done

    support.run = run
PYEOF
  local t
  for t in head base; do
    local dir="$ROOT/$A"
    [ "$t" = base ] && dir="$bt/$A"
    (cd "$dir" && PYTHONPATH="$g" DV1G_DUMP="$g/$t" env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY \
      "$ROOT/$A/.venv/bin/python" -m pytest -q -p no:cacheprovider -p dump_plugin -m "not django_db" \
      esgapi/dataverify/tests/flows/test_colab_156.py esgapi/dataverify/tests/flows/test_colab_156_failures.py) \
      > "$g/$t.log" 2>&1 || { echo "  ★ $t 흐름 시험 실패($(tail -1 "$g/$t.log"))"; code=1; }
  done
  echo "  esgapi 자리 head=$(sed "s|$ROOT/||" "$g/head/esgapi-path.txt") base=$(sed "s|$OUT/||" "$g/base/esgapi-path.txt" | sed 's|.*/DV1g.out/||')"
  grep -q "s6-base-tree" "$g/base/esgapi-path.txt" || { echo "  ★ 기준 나무가 기준 코드를 읽지 않음"; code=1; }
  local nh nb
  nh="$(ls "$g/head" | grep -c '\.json$')"; nb="$(ls "$g/base" | grep -c '\.json$')"
  if [ "$nh" -gt 0 ] && [ "$nh" = "$nb" ] && diff -r -q -x esgapi-path.txt "$g/head" "$g/base" > /dev/null; then
    echo "  흐름 결과 result@2 $nh 건 = 기준 흐름(바이트)"
  else
    echo "  ★ 흐름 결과가 기준과 다름(head $nh · base $nb)"; diff -r -q -x esgapi-path.txt "$g/head" "$g/base" | head -5 | sed 's/^/    /'
    code=1
  fi
  return $code
}

s7() {
  local g="$OUT/s7-generated" code=0
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi) \
    > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋한 generated/"; else echo "  ★ cmp $f ≠ 커밋한 generated/"; code=1; fi
    git show "$BASE:$A/generated/$f" > "$g/base-$f"
  done
  if [ "$COMMIT" = 1 ]; then
    cmp -s "$g/openapi.json" "$g/base-openapi.json" && echo "  경계 ① — openapi.json = 기준" || { echo "  ★ 경계 ① 인데 openapi 가 바뀜"; code=1; }
  else
    (cd "$A" && uv run --frozen python - "$g/base-openapi.json" "$g/openapi.json") <<'PYEOF' || code=1
import json, sys
base, head = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:])
bc, hc = base["components"]["schemas"], head["components"]["schemas"]
changed = [k for k in bc if hc.get(k) != bc[k]]
new = sorted(set(hc) - set(bc))
paths = sorted(set(head["paths"]) - set(base["paths"]))
same_paths = all(head["paths"][p] == base["paths"][p] for p in base["paths"])
print(f"  기준 컴포넌트 {len(bc)} · 값 바뀜 {len(changed)} {changed} · 새 {len(new)} {new}")
print(f"  새 path {paths} · 기준 path 값 같음 {same_paths}")
ok = not changed and new and all(n.startswith("Dataverify") for n in new) and paths == ["/dataverify/runs"] and same_paths
sys.exit(0 if ok else 1)
PYEOF
  fi
  return $code
}

s8() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s8-layout.log" 2>&1
  local code=$?
  tail -1 "$OUT/s8-layout.log" | sed 's/^/  /'
  return $code
}

s9() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s9-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s10() {
  local blog="$OUT/s10-business.log" slog="$OUT/s10-security.log" bcode scode
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s10-up.log" 2>&1 || { tail -3 "$OUT/s10-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider \
    esgapi/dataverify esgapi/runs esgapi/config esgapi/core esgapi/translation) > "$blog" 2>&1
  bcode=$?
  echo "  업무(dataverify·runs·config·core·translation) $(tail -1 "$blog") EXIT=$bcode"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  echo "  보안 $(tail -1 "$slog") EXIT=$scode"
  [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s11() {
  local log flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-DV1g.sh" --commit "$COMMIT" $flag 2>&1)"
  echo "$log" > "$OUT/s11-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s12() {
  local d="$OUT/s12.diff" n_key n_bin n_json n_name=0
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY')"
  n_bin="$(changed | grep -c -E '\.(xlsx|csv|ipynb)$')"
  n_json="$(changed | grep -E '\.json$' | grep -v -x -c -e "$FS/dataverify.digest@1.schema.json" -e "$A/generated/openapi.json")"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴 $n_key · .xlsx/.csv/.ipynb $n_bin · 고정 스키마·generated 밖 .json $n_json · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_json" = 0 ] && [ "$n_name" = 0 ]
}

step 1 "바뀐 경로가 §1-2·§1-3 안(outside=0)" s1
step 2 "0바이트·0줄 목록 diff 0" s2
step 3 "§1-3 허락 줄 numstat·- 줄 원문" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "순수 시험 초록·수(늘기만)" s5
step 6 "고정 스키마 cmp · input@1·result@2·options@1 = 기준 · 흐름 result@2 = 기준 흐름" s6
step 7 "generated/ 다시 뽑아 cmp · 기준 컴포넌트 값 같음·새 이름 Dataverify·새 path 하나" s7
step 8 "check_test_layout" s8
step 9 "뿌리 verify.sh --fast" s9
if [ "$CONTAINERS" = 1 ]; then
  step 10 "업무·보안(컨테이너)" s10
else
  not_run 10 "업무·보안(컨테이너)" "--with-containers 없음"
fi
step 11 "심은 파손(경계 $COMMIT 까지 $EXPECT_PLANTED)" s11
step 12 "추적 diff 의 키 꼴·.xlsx/.csv/.ipynb·업로드 견본 .json·실재 기업명 0" s12
echo "SECTION4_FAIL=$FAILS"
