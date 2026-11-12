#!/usr/bin/env bash
# 밴드 TL1(MARC-TICK-180) §4 의 자기검증. core.llm 의 도구 호출(낱말·어댑터·모의·고리·dry-run)을 잰다.
#   사용: apps/api-py/scripts/section4-TL1.sh [--boundary 1|2] [--step <n>[,<n>…]]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0.
#   아무것도 안 주면 1~11 전부(9 = scripts/verify.sh --fast, 10 = 심은 파손 --boundary <경계>, 기본 경계 2).
# 출력 자리는 S4_OUT(기본 TL1.out). 검증자는 S4_OUT=…/TL1.verify 로 돌려 러너 기록을 덮지 않는다.
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 python3 -I. LLM·네트워크·키 파일·컨테이너 0.
# git grep·git diff 의 실패(종료 ≥2)와 양성 대조 0 은 실패로 센다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=ccd3194187fc314a3dce31a892343c66289547b6
OUT="${S4_OUT:-$ROOT/../TL1.out}"
API="$ROOT/apps/api-py"
LLM=apps/api-py/esgapi/core/llm
NODE_BIN="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$OUT"

ONLY=1,2,3,4,5,6,7,8,9,10,11
BOUNDARY=2
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --boundary) BOUNDARY="$2"; shift 2 ;;
    *) echo "사용: $0 [--boundary 1|2] [--step <n>[,<n>…]]" >&2; exit 2 ;;
  esac
done
case "$BOUNDARY" in 1 | 2) ;; *) echo "경계는 1 또는 2" >&2; exit 2 ;; esac

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }
api() { (cd "$API" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY "$@"); }

# BASE 이후 바뀐 파일(추적 diff + 새 파일)
changed_files() {
  { git diff --name-only "$BASE" && git ls-files --others --exclude-standard; } | sort -u
}

# 1. ruff (바뀐 .py 파일)
if want 1; then
  files=$(changed_files | grep '^apps/api-py/.*\.py$' | sed 's#^apps/api-py/##')
  n=$(printf '%s\n' "$files" | grep -c .)
  echo "  바뀐 .py ${n}개"
  code=0
  if [ "$n" = 0 ]; then
    code=1
    echo "  ★ 양성 대조: 바뀐 .py 가 0"
  else
    # shellcheck disable=SC2086
    api uv run --frozen ruff check $files > "$OUT/s1-ruff.log" 2>&1 || code=1
    # shellcheck disable=SC2086
    api uv run --frozen ruff format --check $files >> "$OUT/s1-ruff.log" 2>&1 || code=1
  fi
  tail -2 "$OUT/s1-ruff.log" | sed 's/^/  /'
  report 1 "ruff check·format --check" "$code"
fi

# 2. lint-imports(계약 수 그대로)와 core/llm 의 순수 계약
if want 2; then
  code=0
  api uv run --frozen lint-imports > "$OUT/s2-lint-imports.log" 2>&1 || code=1
  api uv run --frozen lint-imports --config esgapi/core/llm/purity.importlinter >> "$OUT/s2-lint-imports.log" 2>&1 || code=1
  n=$(grep -c '^\[importlinter:contract' "$API/.importlinter")
  base_n=$(git show "$BASE:apps/api-py/.importlinter" | grep -c '^\[importlinter:contract')
  echo "  계약 수 ${n} (BASE ${base_n}) · $(grep 'Contracts:' "$OUT/s2-lint-imports.log" | tr '\n' ' ')"
  if [ "$n" != "$base_n" ] || [ "$n" != 16 ]; then code=1; fi
  report 2 "lint-imports(계약 16)·purity" "$code"
fi

# 3. pyright strict(core 전부)와 새 완화 줄 0
if want 3; then
  code=0
  api uv run --frozen pyright esgapi/core > "$OUT/s3-pyright.log" 2>&1 || code=1
  echo "  $(tail -1 "$OUT/s3-pyright.log")"
  diff_out=$(git diff "$BASE" -- apps/api-py/esgapi) || code=1
  relax=$(printf '%s\n' "$diff_out" | grep -cE '^\+.*(# pyright:|pyright: ignore|type: ignore)')
  new_relax=0
  for f in $(git ls-files --others --exclude-standard -- apps/api-py/esgapi); do
    c=$(grep -cE '(# pyright:|pyright: ignore|type: ignore)' "$f")
    new_relax=$((new_relax + c))
  done
  echo "  새 완화 줄: diff ${relax} · 새 파일 ${new_relax}"
  if [ "$relax" != 0 ] || [ "$new_relax" != 0 ]; then code=1; fi
  report 3 "pyright esgapi/core(strict)·완화 0" "$code"
fi

# 4. 순수 층 시험(llm·transaction). DB 층(django_db)은 11단계
if want 4; then
  code=0
  api uv run --frozen pytest -q esgapi/core/tests -k "llm or transaction" -m "not django_db and not security" \
    -p no:cacheprovider > "$OUT/s4-pytest.log" 2>&1 || code=1
  echo "  $(tail -1 "$OUT/s4-pytest.log")"
  if ! tail -1 "$OUT/s4-pytest.log" | grep -q ' passed'; then code=1; fi
  report 4 "pytest core -k 'llm or transaction' (순수 층)" "$code"
fi

# 5. 허용 경로 밖 0줄, 0줄 파일, core/llm 새 모듈 0
if want 5; then
  code=0
  files=$(changed_files)
  if [ -z "$files" ]; then code=1; echo "  ★ 양성 대조: 바뀐 파일 0"; fi
  allowed='^apps/api-py/(esgapi/core/llm/.*|esgapi/core/resources/ports/llm\.py|esgapi/core/tests/llm/.*|esgapi/core/tests/test_llm_[^/]*\.py|esgapi/core/tests/test_transaction_rules\.py|scripts/section4-TL1\.sh|scripts/planted-breaks-TL1\.sh)$'
  zero='^apps/api-py/(esgapi/core/llm/purity\.importlinter|esgapi/core/llm/data/models\.synthetic\.json|\.importlinter|pyproject\.toml|uv\.lock|esgapi/core/models\.py|esgapi/core/migrations/.*)$'
  for f in $files; do
    mark=""
    if ! printf '%s\n' "$f" | grep -qE "$allowed"; then mark="★ 허용 밖 "; code=1; fi
    if printf '%s\n' "$f" | grep -qE "$zero"; then mark="★ 0줄이어야 함 "; code=1; fi
    echo "  ${mark}${f}"
  done
  for f in $(git ls-files --others --exclude-standard -- "$LLM"); do
    echo "  ★ core/llm 의 새 파일(새 모듈 0): $f"
    code=1
  done
  report 5 "허용 경로·0줄 파일·새 모듈 0" "$code"
fi

# 6. 기존 시험은 더하기만: ^-[^-] 가 정확히 1줄이고 그것이 test_llm_cost.py 의 == 27
if want 6; then
  code=0
  d=$(git diff "$BASE" -- 'apps/api-py/esgapi/core/tests/test_llm_*.py' 'apps/api-py/esgapi/core/tests/llm/' \
    apps/api-py/esgapi/core/tests/test_transaction_rules.py) || code=1
  minus=$(printf '%s\n' "$d" | grep -E '^-[^-]')
  n=$(printf '%s\n' "$minus" | grep -c .)
  echo "  ^- ${n}줄: ${minus}"
  if [ "$n" != 1 ] || [ "$minus" != '-    assert len(body["sources"]) == 27' ]; then code=1; fi
  plus=$(printf '%s\n' "$d" | grep -cE '^\+[^+]')
  echo "  양성 대조 ^+ ${plus}줄"
  if [ "$plus" = 0 ]; then code=1; fi
  report 6 "기존 시험 더하기만(예외 :120 한 줄)" "$code"
fi

# 7. 공급사 보관 0: 코드 열쇠만
if want 7; then
  code=0
  d=$(git diff "$BASE" -- apps/api-py/esgapi) || code=1
  for f in $(git ls-files --others --exclude-standard -- apps/api-py/esgapi); do d="$d
$(sed 's/^/+/' "$f")"; done
  n=$(printf '%s\n' "$d" | grep -cE '^\+.*("previous_response_id"|previous_response_id=|"store": *True|store=True)')
  ctl=$(printf '%s\n' "$d" | grep -cE '^\+.*"store"')
  echo "  보관 열쇠 ${n}줄 · 양성 대조(\"store\" 를 단언하는 더한 줄) ${ctl}줄"
  if [ "$n" != 0 ] || [ "$ctl" = 0 ]; then code=1; fi
  report 7 "store:true·previous_response_id 열쇠 0" "$code"
fi

# 8. core 는 업무를 모른다(더한 import 0)
if want 8; then
  code=0
  d=$(git diff "$BASE" -- "$LLM") || code=1
  n=$(printf '%s\n' "$d" | grep -cE '^\+.*(from|import) +esgapi\.(dataverify|greenwash|inventory)')
  ctl=$(printf '%s\n' "$d" | grep -cE '^\+.*(from|import) +esgapi\.')
  echo "  업무 import ${n}줄 · 양성 대조(더한 esgapi import) ${ctl}줄"
  if [ "$n" != 0 ] || [ "$ctl" = 0 ]; then code=1; fi
  report 8 "core/llm 업무 import 0" "$code"
fi

# 9. scripts/verify.sh --fast
if want 9; then
  PATH="$NODE_BIN:$PATH" scripts/verify.sh --fast > "$OUT/s9-verify-fast.log" 2>&1
  code=$?
  last=$(tail -1 "$OUT/s9-verify-fast.log")
  echo "  $last"
  if [ "$last" != "VERIFY_FAST=PASS" ]; then code=1; fi
  report 9 "scripts/verify.sh --fast" "$code"
fi

# 10. 심은 파손(이 경계까지의 P)
if want 10; then
  S4_OUT="$OUT" apps/api-py/scripts/planted-breaks-TL1.sh --boundary "$BOUNDARY" > "$OUT/s10-planted-b${BOUNDARY}.log" 2>&1
  code=$?
  grep -E '^(PLANTED|FINGERPRINT)=' "$OUT/s10-planted-b${BOUNDARY}.log" | sed 's/^/  /'
  p=$(grep '^PLANTED=' "$OUT/s10-planted-b${BOUNDARY}.log" | sed 's/^PLANTED=//')
  if [ -z "$p" ] || [ "${p%/*}" != "${p#*/}" ]; then code=1; fi
  if ! grep -qx 'FINGERPRINT=same' "$OUT/s10-planted-b${BOUNDARY}.log"; then code=1; fi
  report 10 "planted-breaks-TL1 --boundary ${BOUNDARY}" "$code"
fi

# 11. DB 층: 워크트리의 compose DB 가 이미 떠 있을 때만(러너는 띄우지 않는다)
if want 11; then
  port=""
  if [ -f "$ROOT/.env" ]; then port=$(grep -E '^POSTGRES_PORT=' "$ROOT/.env" | cut -d= -f2); fi
  if [ -n "$port" ] && lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then
    (cd "$API" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY \
      scripts/test-business.sh -k 'llm or scope3' -p no:cacheprovider) > "$OUT/s11-business.log" 2>&1
    code=$?
    echo "  $(tail -1 "$OUT/s11-business.log")"
    report 11 "test-business.sh -k 'llm or scope3'" "$code"
  else
    echo "[11] DB 층 안 돌림 — 워크트리의 compose DB 가 떠 있지 않음(.env ${port:-없음}). 병합 뒤 전량 scripts/verify.sh 가 첫 확인"
  fi
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
