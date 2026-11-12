#!/usr/bin/env bash
# 밴드 S3K3(MARC-TICK-456: Scope 3 실행 — 설정 결함·공급사 거절·비용 상한을 실행 failed 로)의 심은 파손. 밴드 몫·verify 밖.
#   사용: apps/api-py/scripts/planted-breaks-S3K3.sh [--only P<n>] [--keep-db]
#   심기마다 원본을 <워크트리>.out/planted/ 에 떠 두고 → 한 줄 바꿈 → 그 시험을 돌려 빨강을 본다 → 떠 둔 원본으로 되돌린다.
#   줄마다 「P<n> RED|GREEN <걸린 시험 수> <시험 파일>」, 끝 줄 「PLANTED <빨강>/<전체>」. 다 빨강이면 0, 아니면 1.
# T3(test_binding_157_end_to_end.py)는 업무 층이라 이 워크트리 compose 의 postgres 가 떠 있어야 한다
#   (docker compose up -d --wait postgres — .env 의 COMPOSE_PROJECT_NAME 것만). 공급사 호출 0(모의), 키 0.
# 뿌리 .git/verify.lock 이 있으면 돌지 않는다(부분 실행 포함 — runner-common §5).
set -u
cd "$(dirname "$0")/.."
API="$(pwd)"
WT="$(cd ../.. && pwd)"
OUT="$WT.out/planted"
COMMON="$(git rev-parse --git-common-dir)"
case "$COMMON" in /*) ;; *) COMMON="$(cd "$COMMON" && pwd)" ;; esac
if [ -e "$COMMON/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다(돌리지 않음)" >&2; exit 3; fi
mkdir -p "$OUT"
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="${2:-}"; shift 2 ;;
    *) echo "사용: $0 [--only P<n>]" >&2; exit 2 ;;
  esac
done

J=esgapi/inventory/flows/scope3_journal_157.py
F=esgapi/inventory/flows/scope3_colab_157.py
T1=esgapi/inventory/tests/flows/test_scope3_journal_157.py
T2=esgapi/inventory/tests/flows/test_scope3_colab_157_surfacing.py
T3=esgapi/inventory/tests/flows/test_binding_157_end_to_end.py

plant() { # <파일> <옛 글> <새 글> — 꼭 한 곳
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳: {old[:60]!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}

run_tests() { # <시험 파일…> → 실패 수(표준 출력 한 줄)
  local pure=() db=() f out
  for f in "$@"; do
    if [ "$f" = "$T3" ]; then db+=("$f"); else pure+=("$f"); fi
  done
  out="$OUT/run.txt"; : > "$out"
  if [ ${#pure[@]} -gt 0 ]; then
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY uv run --frozen pytest -q -p no:cacheprovider "${pure[@]}" >> "$out" 2>&1
  fi
  if [ ${#db[@]} -gt 0 ]; then
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY scripts/test-business.sh -p no:cacheprovider "${db[@]}" >> "$out" 2>&1
  fi
  grep -c "^FAILED" "$out"
}

RED=0; ALL=0; BAD=0
CUR=""  # 지금 심은 파일 — 끊겨도(EXIT·INT·TERM) 떠 둔 원본으로 되돌린다(가지 리뷰 LOW 8)
restore() { if [ -n "$CUR" ]; then cp "$OUT/$(basename "$CUR").orig" "$CUR"; CUR=""; fi; }
trap restore EXIT
trap 'restore; exit 130' INT TERM
case_() { # <번호> <파일> <옛 글> <새 글> <시험 파일…>
  local n="$1" file="$2" old="$3" new="$4"; shift 4
  [ -z "$ONLY" ] || [ "$ONLY" = "$n" ] || return 0
  ALL=$((ALL + 1))
  cp "$file" "$OUT/$(basename "$file").orig"
  CUR="$file"
  if ! plant "$file" "$old" "$new"; then
    echo "$n ★ 심기 실패"; BAD=1; restore; return
  fi
  local failed; failed="$(run_tests "$@")"
  restore
  if ! cmp -s "$file" "$OUT/$(basename "$file").orig"; then echo "$n ★ 되돌림 실패"; BAD=1; fi
  if [ "$failed" -gt 0 ]; then
    RED=$((RED + 1)); echo "$n RED $failed $* · $(grep "^FAILED" "$OUT/run.txt" | head -3 | sed 's/^FAILED [^:]*:://' | tr '\n' ' ')"
  else
    echo "$n GREEN 0 $*"
  fi
}

START_SHA="$(shasum -a 256 "$J" "$F")"  # 끝에 견줄 시작 때 지문(커밋 전 고침도 그대로 견준다)
echo "── S3K3 심은 파손 · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"
# ① 설정 결함·공급사 거절
case_ P1 "$J" "= (LiveSetupError, LlmConfigError, PromptError)" "= (LlmConfigError, PromptError)" "$T1" "$T2" "$T3"
case_ P2 "$J" "= (LiveSetupError, LlmConfigError, PromptError)" "= (LiveSetupError, LlmConfigError)" "$T1" "$T2"
case_ P3 "$J" "            if type(err) in SETUP_ERRORS:" "            if True:" "$T1" "$T3"
case_ P5 "$J" "REJECTED_STATUSES: Final = frozenset({401, 403, 404})" "REJECTED_STATUSES: Final = frozenset({404})" "$T1" "$T2" "$T3"
case_ P6 "$J" "    if not isinstance(result, ProviderFailed):
        return None
" "    if not isinstance(result, ProviderFailed):
        return None
    return Scope3ProviderRejected(\"가상\")
" "$T1" "$T2"
case_ P11 "$J" "    if result.status == 404:
        return Scope3ProviderRejected(\"공급사가 모델·경로를 찾지 못했다(status 404)\")
    if result.status in REJECTED_STATUSES:" "    if result.status in REJECTED_STATUSES - {404}:" "$T1" "$T2"
case_ P12 "$J" "QUOTA_MARK in result.message" "False" "$T1" "$T2"
case_ X1 "$J" "            if type(err) in SETUP_ERRORS:" "            if isinstance(err, SETUP_ERRORS):" "$T1"
# ② 비용 상한·로그
case_ P4 "$J" "        if isinstance(got, BudgetExceeded):  # (f)" "        if False:  # (f)" "$T1" "$T2" "$T3"
case_ P7 "$J" "        while queue and queue[0].kind == \"budget_exceeded\":" "        while False:" "$T1"
case_ P8 "$J" "        if isinstance(got, BudgetExceeded):  # (f) — 칸·체크포인트 0, 뒤 부름 0
" "        if isinstance(got, BudgetExceeded):  # (f) — 칸·체크포인트 0, 뒤 부름 0
            self.entries.append(entry_of(key, got))
" "$T1"
case_ P9 "$F" "failed_sheets=%s llm_failed=%s\", failed_sheets, llm_failed)" \
  "failed_sheets=%s llm_failed=%s %s\", failed_sheets, llm_failed, [o.sheet for o in result.sheets])" "$T2"
case_ P10 "$F" "    return StepOutput(data={\"results\": [result_to_dict(result, RESULT_SHAPE)]})" \
  "    return StepOutput(data={\"results\": [{**result_to_dict(result, RESULT_SHAPE), \"problems\": 0}]})" "$T2" "$T3"
# P13(검증 V5 — 권고 R4): 상한 빼냄을 적는 게이트웨이(카테고리 단계)에만 — assemble 이 상한을 삼킴
case_ P13 "$J" "        if isinstance(got, BudgetExceeded):  # (f)" "        if isinstance(got, BudgetExceeded) and self._record_entries:  # (f)" "$T2"
case_ X2 "$F" "    if failed_sheets or llm_failed:" "    if True:" "$T2"
echo "PLANTED $RED/$ALL"
[ "$(shasum -a 256 "$J" "$F")" = "$START_SHA" ] || { echo "★ 되돌린 뒤 파일이 시작 때와 다르다"; BAD=1; }
[ "$RED" = "$ALL" ] && [ "$BAD" = 0 ]
