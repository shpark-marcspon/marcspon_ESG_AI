#!/usr/bin/env bash
# LB1 의 심은 파손(발주서 band-handoffs/LB1-order.md §3 표 P1~P14 + 감독 답 2 B2 + Q6 + 검증 ① X1 + 검증 ② V3·V7): 파손 하나를 심고,
# 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-LB1.sh [--only P<n>|B2|Q6|X1|V3|V7]
# 틀은 planted-breaks-S12S1.sh: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 —
#   checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다(§ 로 여러 자리). 아니면 「못 심음」이고 실패로 센다.
# 빨강 = 그 명령의 종료 1(pytest 수집 실패 2·4 는 「죽음」 — 빨강이 아니다). 시험은 전부 순수 층(DB·네트워크·LLM 0).
# .git/verify.lock(디렉터리)이 있으면 심기 전마다 멈춘다(종료 2). 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>
#   FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다. macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I.
set -u
cd "$(dirname "$0")/.."
MAIN="$(git rev-parse --path-format=absolute --git-common-dir)"
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done

L=esgapi/core/llm
AN=$L/providers/anthropic.py
OA=$L/providers/openai.py
CL=$L/client.py
RT=$L/retry.py
EM=$L/embedding.py
TY=$L/types.py
TK=esgapi/core/tests/llm/test_error_kinds.py
TW=esgapi/core/tests/llm/test_retry_wait.py

backup="$(mktemp -d /private/tmp/lb1-planted.XXXXXX)"
case "$backup" in /private/tmp/lb1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈, § 로 여러 자리)
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
path, olds, news = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
for old, new in zip(olds.split("§"), news.split("§"), strict=True):
    if text.count(old) != 1:
        print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
        sys.exit(1)
    text = text.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(text)
PYEOF
}

check() {  # check <시험 노드…> — 0 초록 · 1 빨강 · 그 밖 죽음
  # shellcheck disable=SC2086
  uv run --frozen pytest -q -p no:randomly -p no:cacheprovider $1 > "$backup/log" 2>&1
}

planted=0; red=0
row() {  # row <번호> <설명> <파일> <옛> <새> <시험 노드(빈칸으로 여럿)>
  local id="$1" what="$2" file="$3" old="$4" new="$5" test="$6"
  if [ -n "$ONLY" ] && [ "$ONLY" != "$id" ]; then return; fi
  if [ -e "$MAIN/verify.lock" ]; then echo "lock 있음 — 멈춤"; exit 2; fi
  planted=$((planted + 1))
  cp "$file" "$backup/keep"; current="$file"
  if ! plant "$file" "$old" "$new"; then
    echo "$id 못 심음 — $what"; restore; return
  fi
  check "$test"; local code=$?
  restore
  cmp -s "$file" "$backup/keep" || { echo "$id 되돌림 실패: $file"; exit 1; }
  local failed
  failed=$(grep -E "^(FAILED|ERROR) " "$backup/log" | sed 's/ - .*//' | tr '\n' ' ' | cut -c1-220)
  if [ "$code" -eq 1 ]; then
    red=$((red + 1)); echo "$id 빨강 — $what · ${failed:-$(tail -1 "$backup/log" | cut -c1-120)}"
  elif [ "$code" -eq 0 ]; then
    echo "$id 초록(놓침) — $what · $test"
  else
    echo "$id 죽음(종료 $code) — $what · $(tail -1 "$backup/log" | cut -c1-120)"
  fi
}

row P1 "anthropic 529 를 server_error 로" "$AN" \
  '    if status == 529 or error_type == "overloaded_error":\n        return "overloaded"' \
  '    if status == 529 or error_type == "overloaded_error":\n        return "server_error"' \
  "$TK::test_s1_anthropic_names"
row P2 "스트림 overloaded_error(200) 가름 지움(옛 200·불가로)" "$AN" \
  '(status == 429 or status >= 500 or kind == "overloaded")' '(status == 429 or status >= 500)' \
  "$TK::test_s6_an_overloaded_event_in_a_200_stream_is_named_and_retryable"
row P3 "openai 크레딧 소진 가름 지움(→ rate_limited)" "$OA" \
  '        quota = code in QUOTA_ERROR_CODES or error_type == QUOTA_ERROR_TYPE' '        quota = False' \
  "$TK::test_s2_credit_exhausted_is_not_retryable_and_keeps_no_wait $TW::test_s12_quota_exhausted_is_called_once_then_the_next_model"
row P4 "call 의 ProviderFailed 에 retry_after_ms 안 실음" "$CL" \
  '                            meta=meta(),\n                            error_kind=response.error_kind,\n                            retry_after_ms=response.retry_after_ms,' \
  '                            meta=meta(),\n                            error_kind=response.error_kind,' \
  "$TK::test_s3_provider_failed_carries_the_name_and_the_wait $TW::test_s9_a_wait_longer_than_the_budget_is_not_slept_and_rides_on_the_result"
row P5 "기록 줄 error_kind 안 실음" "$CL" \
  'error_kind=response.error_kind if isinstance(response, ProviderError) else None,' 'error_kind=None,' \
  "$TK::test_s4_error_kind_sits_right_after_error_status_only_when_present"
row P6 "예산 무시(한도 갈래도 max_retries 2)" "$RT" \
  '    if in_wait_budget(error, maybe_billed=maybe_billed):' '    if False:' \
  "$TW::test_s7_k_rate_limits_with_a_wait_are_waited_out_beyond_max_retries $TW::test_s8_overloaded_without_a_wait_backs_off_until_the_budget_then_falls_back"
row P7 "천장 지움" "$RT" \
  '        if budget_done >= policy.max_budget_retries:\n            return None\n' '' \
  "$TW::test_s10_tiny_waits_stop_at_the_ceiling"
row P8 "지터 상수(흩뜨림 없음)" "$RT" \
  '    spread = min(1.0, max(0.0, jitter()))' '    spread = 0.0' \
  "$TW::test_s13_jitter_never_goes_below_the_provider_wait_and_halves_backoff_at_most"
row P9 "HTTP 날짜 꼴 읽기 지움" "$RT" \
  '            if name == "retry-after" and (waited := _http_date_ms(value, now_ms)) is not None:\n                return waited\n' '' \
  "$TW::test_s11_http_date_retry_after_is_read_against_the_given_clock"
row P10 "과금됐을 수 있는 overloaded 를 예산 갈래로(§1-3)" "$RT" \
  '    return error.error_kind in WAIT_BUDGET_KINDS and not maybe_billed' '    return error.error_kind in WAIT_BUDGET_KINDS' \
  "$TW::test_s14_a_maybe_billed_overload_uses_the_count_branch"
row P11 "시간 초과를 재시도" "$CL" \
  '            if not isinstance(response, ProviderError):\n                return _Answered(response=response, validated=validated)' \
  '            if isinstance(response, ProviderTimeout):\n                continue\n            if not isinstance(response, ProviderError):\n                return _Answered(response=response, validated=validated)' \
  "$TW::test_s14_a_timeout_is_not_retried_and_falls_back"
row P12 "임베딩 재시도 지움" "$EM" \
  '                    if decision is None:' '                    if True:' \
  "$TW::test_s15_embedding_retries_two_rate_limits_then_succeeds"
row P13 "624 마지막 답(잘림) 몫 빼기" "$CL" \
  '                    failure = CutOff(partial_text=response.text, meta=state.meta())\n                    hosted_calls += response.hosted_calls\n' \
  '                    failure = CutOff(partial_text=response.text, meta=state.meta())\n' \
  "$TW::test_s16_a_cut_or_refused_last_answer_adds_its_searches"
row P14 "새 칸을 meta 앞에(위치 인자 깨짐)" "$TY" \
  '    message: str\n    meta: CallMeta\n    kind: Literal["provider_error"] = "provider_error"\n    error_kind: ErrorKind | None = None\n' \
  '    message: str\n    error_kind: ErrorKind | None\n    meta: CallMeta\n    kind: Literal["provider_error"] = "provider_error"\n' \
  "$TK::test_s5_positional_provider_failed_still_builds"
row B2 "provider_retry 에 없는 공급사에 기본 예산(전역 상수로)" "$RT" \
  'NO_RETRY = RetryPolicy(max_retries=0, base_delay_ms=0, max_delay_ms=0, wait_budget_ms=0, max_budget_retries=0)' \
  'NO_RETRY = RetryPolicy(max_retries=0, base_delay_ms=0, max_delay_ms=0)' \
  "$TW::test_b2_an_empty_provider_retry_turns_the_budget_branch_off_too $TW::test_s15_an_empty_provider_retry_turns_embedding_retry_off"
row Q6 "크레딧 소진이 다음 모델로 안 감" "$CL" \
  ' or failure.error_kind == "quota_exhausted"' '' \
  "$TW::test_s12_quota_exhausted_is_called_once_then_the_next_model"
row X1 "call_tools 의 ProviderFailed 에 retry_after_ms 안 실음(검증 ① B1)" "$CL" \
  '                        meta=state.meta(),\n                        error_kind=response.error_kind,\n                        retry_after_ms=response.retry_after_ms,' \
  '                        meta=state.meta(),\n                        error_kind=response.error_kind,' \
  "$TK::test_s3_a_failed_tool_loop_carries_the_name_and_the_wait"
row V3 "임베딩이 예산 갈래를 안 씀(BASE 횟수 정책처럼 — 검증 ② B1)" "$EM" \
  '                        maybe_billed=billed,' '                        maybe_billed=True,' \
  "$TW::test_s15_embedding_rate_limits_use_the_wait_budget_beyond_max_retries_with_jitter"
row V7 "임베딩 지터를 0 으로 고정(검증 ② B1)" "$EM" \
  '                        jitter=self._jitter,' '                        jitter=lambda: 0.0,' \
  "$TW::test_s15_embedding_rate_limits_use_the_wait_budget_beyond_max_retries_with_jitter"

after="$(fingerprint)"
same=same
if [ "$before" != "$after" ]; then same=differs; diff <(printf '%s\n' "$before") <(printf '%s\n' "$after"); fi
echo "PLANTED=$red/$planted FINGERPRINT=$same"
[ "$red" -eq "$planted" ] && [ "$same" = same ]
