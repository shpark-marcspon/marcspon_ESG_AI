#!/usr/bin/env bash
# 밴드 GO1(MARC-TICK-70)의 심은 파손 열다섯: 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-GO1.sh        마지막 줄 PLANTED=<잡은 수>/15
# 0번은 심지 않고 돌린다: 아래 테스트 파일이 전부 초록이어야 한다(처음부터 빨간 것을 「잡았다」고 세지 않게).
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준: 테스트가 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다
#   (다른 까닭으로 빨개진 것을 잡았다고 세지 않는다).
# 컨테이너 0, 네트워크 0. 순수 층만 돈다(업무 층의 test_observability_api.py 는 여기서 돌지 않는다). bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."

A=apps/api-py
BASE="$A/esgapi/config/settings/base.py"
CONTEXT="$A/esgapi/core/observability/context.py"
JSONLOG="$A/esgapi/core/observability/jsonlog.py"
MIDDLEWARE="$A/esgapi/core/observability/middleware.py"
GUNICORN="$A/gunicorn.conf.py"
CELERY="$A/esgapi/config/celery.py"
QUEUE="$A/esgapi/core/resources/queue.py"
T=esgapi/core/tests
T_SETTINGS=esgapi/config/tests/test_settings.py
T_CHECK=esgapi/config/tests/test_system_check.py
T_CONTEXT="$T/test_observability_context.py"
T_JSONLOG="$T/test_observability_jsonlog.py"
T_LAYERS="$T/test_observability_layers.py"
T_MIDDLEWARE="$T/test_observability_middleware.py"
T_WORKER="$T/test_observability_worker.py"
T_HOOK="$T/test_jobs_hook.py"

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$BASE" "$CONTEXT" "$JSONLOG" "$MIDDLEWARE" "$GUNICORN" "$CELERY" "$QUEUE")
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}" 2>&1; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() { for f in "${FILES[@]}"; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done; }
trap 'restore_files' EXIT INT TERM

total=0; ok=0
edit() { # <파일> <있던 글자> <바꿀 글자>   글자가 정확히 한 번 있어야 한다(없으면 심지 못한 것이다: 종료 3)
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
# 테스트 파일 여럿을 한 글자열로 받는다(빈칸으로 가른다).
pure_tests() { (cd "$A" && uv run --frozen pytest -q -rf -p no:cacheprovider -m "not django_db and not security" $1); }
# <번호와 설명> <로그 파일> <종료 코드> <FAILED 줄에 있어야 하는 테스트 이름…>
judge() {
  local name="$1" file="$2" code="$3" caught=0 wanted
  shift 3
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|^FAILED' "$file" | sed 's/^/    /' | cut -c1-200 | head -8
  [ "$code" -ne 0 ] || caught=1
  for wanted in "$@"; do
    grep -q "^FAILED .*$wanted" "$file" || { caught=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$caught" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}
# <번호> <설명> <파일> <있던 글자> <바꿀 글자> <테스트 파일들> <FAILED 줄에 있어야 하는 테스트 이름…>
plant() {
  local number="$1" what="$2" file="$3" old="$4" new="$5" tests="$6" code
  shift 6
  edit "$file" "$old" "$new" || exit 3
  pure_tests "$tests" > "$log/$number.txt" 2>&1; code=$?
  judge "$number. $what" "$log/$number.txt" "$code" "$@"
}

# ── 0. 심지 않고: 전부 초록 ──
pure_tests "$T_SETTINGS $T_CHECK $T_CONTEXT $T_JSONLOG $T_LAYERS $T_MIDDLEWARE $T_WORKER $T_HOOK" > "$log/0.txt" 2>&1; code=$?
tail -1 "$log/0.txt" | sed 's/^/    /'
if [ "$code" -ne 0 ] || tail -1 "$log/0.txt" | grep -q -E 'failed|error'; then
  echo "0. 심지 않았는데 빨갛다 → ★ 멈춘다" >&2; tail -20 "$log/0.txt" >&2; exit 1
fi
echo "0. 심지 않고 → 전부 초록"

# ── 요청 쪽 ──
plant 1 "MIDDLEWARE 에서 request ID 줄을 지운다" "$BASE" \
  $'    "esgapi.core.observability.middleware.RequestIdMiddleware",\n' '' \
  "$T_SETTINGS $T_MIDDLEWARE" \
  'test_the_request_id_middleware_is_first\[base\]' test_through_the_configured_chain_healthz_carries_the_header
plant 2 "두 미들웨어의 차례를 뒤집는다" "$BASE" \
  $'    "esgapi.core.observability.middleware.RequestIdMiddleware",\n    "esgapi.core.tenancy.middleware.TenantMiddleware",\n' \
  $'    "esgapi.core.tenancy.middleware.TenantMiddleware",\n    "esgapi.core.observability.middleware.RequestIdMiddleware",\n' \
  "$T_SETTINGS $T_MIDDLEWARE" \
  'test_the_request_id_middleware_is_first\[base\]' 'test_the_request_id_middleware_is_first\[test_business\]' \
  test_the_settings_put_the_middleware_first_and_use_the_json_config
plant 3 "accept_request_id 가 받은 값을 검사 없이 돌려준다" "$CONTEXT" \
  'if raw is not None and _ACCEPTED.fullmatch(raw) is not None:' 'if raw is not None:' \
  "$T_CONTEXT $T_MIDDLEWARE" \
  'test_anything_else_is_dropped_and_a_new_id_is_made\[has space\]' 'test_anything_else_is_dropped_and_a_new_id_is_made\[a,b\]' \
  'test_a_malformed_id_is_replaced_not_refused\[has space\]'
plant 4 "미들웨어가 응답 헤더를 싣지 않는다" "$MIDDLEWARE" \
  $'            response[REQUEST_ID_HEADER] = request_id\n' '' \
  "$T_MIDDLEWARE" \
  'test_every_response_carries_the_header_and_nothing_else_changes\[200\]' 'test_every_response_carries_the_header_and_nothing_else_changes\[503\]'
plant 5 "미들웨어의 finally: unbind 를 지운다" "$MIDDLEWARE" \
  $'        finally:\n            unbind_request_id(token)' $'        finally:\n            pass' \
  "$T_MIDDLEWARE" test_the_id_is_bound_inside_and_gone_after test_the_id_is_gone_even_when_the_inside_raises
plant 6 "포매터가 record.__dict__ 를 통째로 싣는다" "$JSONLOG" \
  '        if record.exc_info and record.exc_info[0] is not None:' \
  $'        line.update({key: str(value) for key, value in record.__dict__.items()})\n        if record.exc_info and record.exc_info[0] is not None:' \
  "$T_JSONLOG" test_extra_names_outside_the_list_are_not_carried test_a_plain_line_is_one_line_of_json_with_the_five_fixed_fields
plant 7 "접근 줄의 path 를 get_full_path() 로" "$MIDDLEWARE" \
  '"path": request.path,' '"path": request.get_full_path(),' \
  "$T_MIDDLEWARE" test_the_query_the_cookie_and_the_authorization_are_not_logged test_through_the_configured_chain_healthz_carries_the_header
plant 8 "gunicorn.conf.py 의 accesslog 를 켠다" "$GUNICORN" \
  'accesslog = None' 'accesslog = "-"' \
  "$T_JSONLOG" test_gunicorn_writes_no_access_log_of_its_own
plant 9 "gunicorn.access 로거에 처리기를 건다" "$JSONLOG" \
  '"gunicorn.access": {"level": "INFO", "handlers": [],' '"gunicorn.access": {"level": "INFO", "handlers": ["stdout"],' \
  "$T_JSONLOG" test_the_gunicorn_config_adds_only_the_two_gunicorn_loggers

# ── 워커 쪽 ──
plant 10 "task_prerun.connect 줄을 지운다" "$CELERY" \
  $'task_prerun.connect(on_task_prerun, weak=False)\n' '' \
  "$T_WORKER" test_our_receivers_are_connected_to_the_three_signals \
  test_while_a_task_runs_the_lines_carry_the_task_and_the_job_and_never_the_tenant
plant 11 "on_task_prerun 이 tenant_id 를 job_id 자리에 싣는다" "$CELERY" \
  'job_id = kwargs.get("job_id") if isinstance(kwargs, dict) else None' \
  'job_id = kwargs.get("tenant_id") if isinstance(kwargs, dict) else None' \
  "$T_WORKER" test_while_a_task_runs_the_lines_carry_the_task_and_the_job_and_never_the_tenant
plant 12 "enqueue_job 의 except 가 raise 없이 삼킨다" "$QUEUE" \
  $'type(err).__name__)\n        raise\n' $'type(err).__name__)\n' \
  "$T_HOOK" test_an_error_from_the_broker_is_raised_as_it_is test_a_failed_send_is_logged_with_the_job_id_and_still_raised
plant 13 "실패 기록에서 job_id 를 뺀다" "$QUEUE" \
  '"queue_send_failed job_id=%s kind=%s error=%s", job_id, kind,' '"queue_send_failed kind=%s error=%s", kind,' \
  "$T_HOOK" test_a_failed_send_is_logged_with_the_job_id_and_still_raised

# ── 층과 system check ──
plant 14 "jsonlog.py 가 django 를 import" "$JSONLOG" \
  $'\nimport json\nimport logging\n' $'\nimport django\nimport json\nimport logging\n' \
  "$T_LAYERS" test_jsonlog_imports_only_the_standard_library_and_context 'test_the_pure_two_know_no_framework\[jsonlog.py\]'
# ★ 발주서는 LANGUAGE_CODE = "not a code" 를 심으라 했다. 그 값은 pytest 가 뜨다가 죽는다(Django 가 번역 파일을 찾다
#   OSError. 종료 코드는 0 이 아니지만 FAILED 줄이 없어 「이름으로 잡았다」를 못 잰다). 그래서 뜨기는 하고 system check 만
#   틀리는 값을 심는다: LANGUAGES 의 틀린 언어 코드(translation.E002·E004).
plant 15 "설정에 틀린 LANGUAGES 를 심는다(system check 의 오류)" "$BASE" \
  $'USE_TZ = True\n' $'USE_TZ = True\nLANGUAGES = [("not a code", "x")]\n' \
  "$T_CHECK" test_the_system_check_is_clean 'test_every_settings_module_passes_the_check\[base\]' \
  'test_every_settings_module_passes_the_check\[test_business\]' 'test_every_settings_module_passes_the_check\[test_security\]'

restore_files
trap - EXIT INT TERM
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
if ! cmp -s "$keep/.sums-before" "$keep/.sums-after" || ! cmp -s "$keep/.status-before" "$keep/.status-after"; then
  echo "★ 되돌린 뒤의 파일이 처음과 다르다(sha256 이나 git status)" >&2
  diff "$keep/.sums-before" "$keep/.sums-after" >&2
  exit 1
fi
echo "되돌림 확인: sha256 $(wc -l < "$keep/.sums-after" | tr -d ' ')개 같음 · git status 같음"
echo "PLANTED=$ok/$total"
[ "$ok" -eq 15 ] && [ "$total" -eq 15 ]
