#!/usr/bin/env bash
# 밴드 T1c(MARC-TICK-89)의 심은 파손: 하나씩 심고, 그것을 잡아야 하는 자리가 잡는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-T1c.sh --pure          P1~P5(컨테이너 없음)          마지막 줄 PLANTED=<잡음>/<전체>
#         apps/api-py/scripts/planted-breaks-T1c.sh --containers    떠 있는 compose 프로젝트에서. worker-py 가 받은 긴 폴링을
#                                                                   먼저 읽어(C5) 판을 가른다:
#             짧은 값 판(10 아님): C1s(보고만) · C2 · C3 · C4
#             기본값 판(10)      : C1(바꿔치기·SIGKILL 각 세 번, 한 번 이상 빨강) · C6(어긋남 세 번 + 대조 한 번)
#   C5(워커가 받은 값)는 대조라 셈에 넣지 않는다. C1s 도 셈에 넣지 않는다(보고만 — 발주서 3-2).
# 0번은 심지 않고 돌린다(그 모드·판의 시험이 초록이어야 한다. 처음부터 빨간 것을 「잡았다」고 세지 않게.
#   0번이 빨가면 PLANTED 를 내지 않고 종료 1).
# 심는 것은 전부 있는 파일의 글자 바꿈이다. 되돌리기는 저장소 밖 임시 폴더의 사본을 cp 한다(git 을 쓰지 않는다.
# 죽어도 trap 이 되돌린다). 끝에서 `git status --porcelain` 과 `git diff` 의 sha256 이 처음과 같은지 잰다. 다르면
# PLANTED 를 내지 않고 종료 1. C2(parser 를 루트로)는 되돌린 뒤 parser 를 다시 만든다.
# C6 의 「세션 시작 단언을 끈다」도 심은 파손으로만 한다(autouse 를 끈 사본). 끄는 환경 변수·스위치는 없다.
# 컨테이너 쪽은 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)만 다룬다. 띄우기·내리기는 부르는 쪽(section4)이 한다.
# macOS /bin/bash 3.2 에서 돈다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-}"
case "$MODE" in --pure | --containers) ;; *) echo "사용: $0 --pure | --containers" >&2; exit 2 ;; esac

A=apps/api-py
ENVPY="$A/esgapi/config/env.py"
CELERYPY="$A/esgapi/config/celery.py"
WF="$A/tests_integration/test_worker_flow.py"
FILES="$ENVPY $CELERYPY $WF compose.yaml"
SWAP="tests_integration/test_worker_flow.py::test_an_object_swapped_after_the_confirm_is_not_parsed"
KILL="tests_integration/test_worker_flow.py::test_a_killed_workers_job_is_taken_over_after_the_lease_and_ends_once"
PARSER_DOWN="tests_integration/test_worker_flow.py::test_when_the_parser_is_down_the_job_fails_at_the_attempt_limit_with_a_reason"
SIGTERM="tests_integration/test_worker_flow.py::test_a_worker_given_sigterm_finishes_the_job_in_hand_and_exits_0"
NONROOT_PARSER="tests_integration/test_flow.py::test_the_worker_and_the_parser_run_as_non_root[parser]"

keep="$(mktemp -d)"   # 저장소 밖
log="$(mktemp -d)"
for f in $FILES; do mkdir -p "$keep/$(dirname "$f")"; cp "$f" "$keep/$f"; done
fingerprint() { git status --porcelain; git diff | shasum -a 256; }
fingerprint > "$keep/.before"
parser_dirty=0
restore() {
  local f
  for f in $FILES; do cmp -s "$keep/$f" "$f" || cp "$keep/$f" "$f"; done
  if [ "$parser_dirty" = 1 ]; then
    docker compose up -d --no-deps --force-recreate --wait parser > /dev/null 2>&1
    parser_dirty=0
  fi
}
trap 'restore' EXIT INT TERM

plant() { # <파일> <있는 글자> <바꿀 글자>   그 글자가 꼭 한 번 있어야 한다(아니면 종료 3)
  python3 - "$1" "$2" "$3" <<'EOF' || { echo "★ 심을 글자가 꼭 한 번 있지 않다: $1" >&2; exit 3; }
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(1)
open(path, "w", encoding="utf-8").write(text.replace(old, new))
EOF
}

total=0; ok=0
verdict() { # <번호와 설명> <잡았나 0|1> <나온 것>
  total=$((total + 1))
  if [ "$2" -eq 1 ]; then ok=$((ok + 1)); echo "# $1 → 잡음 · $3"; else echo "# $1 → ★ 못 잡음 · $3"; fi
}
report() { echo "# $1 → (보고만) $2"; }
load1() { uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p'; }
summary_of() { grep -E '[0-9]+ (passed|failed|error)' "$1" | tail -1; }

# ── 순수 층 ───────────────────────────────────────────────────────────
PURE_TESTS="esgapi/config/tests/test_env.py esgapi/core/tests/test_celery_conf.py"
pure_run() { (cd "$A" && uv run --frozen pytest -q -p no:cacheprovider $PURE_TESTS) > "$1" 2>&1; }
pure_catches() { # <번호와 설명> <빨개야 할 시험 이름의 무늬>
  local f="$log/$total.pure" code
  pure_run "$f"; code=$?
  local failed; failed="$(grep -E '^FAILED ' "$f" | sed 's/ - .*//' | tr '\n' ';')"
  local caught=0
  [ "$code" -eq 1 ] && printf '%s\n' "$failed" | grep -q -E "$2" && caught=1
  verdict "$1" "$caught" "종료 $code · $(summary_of "$f") · 빨강: ${failed:-없음}"
}
gates_catches() { # <번호와 설명> <빨개야 할 검사 이름의 글자>
  local f="$log/$total.gates" code
  scripts/check-gates.sh > "$f" 2>&1; code=$?
  local red; red="$(grep -E '^(▶|EXIT=)' "$f" | paste - - | grep -v 'EXIT=0$' | sed 's/^▶ //; s/\tEXIT=.*//')"
  local caught=0
  [ "$code" -eq 1 ] && [ "$red" = "$2" ] && caught=1
  verdict "$1" "$caught" "종료 $code · $(tail -1 "$f") · 빨간 검사: ${red:-없음}"
}

pure_mode() {
  local f="$log/0.pure"
  pure_run "$f" || { echo "★ 0번(심지 않음)이 빨갛다: $(summary_of "$f") · $f"; exit 1; }
  echo "# 0 심지 않음 → 초록 · $(summary_of "$f")"
  scripts/check-gates.sh > "$log/0.gates" 2>&1 || { echo "★ 0번 check-gates 가 빨갛다: $log/0.gates"; exit 1; }
  echo "# 0 심지 않음 → check-gates $(tail -1 "$log/0.gates")"

  plant "$ENVPY" '    wait_s = _positive(env, problems, "CELERY_WAIT_TIME_SECONDS", BrokerSettings.wait_time_seconds)
    if wait_s > 20:
        problems.append("CELERY_WAIT_TIME_SECONDS 는 20 이하여야 한다(SQS 의 WaitTimeSeconds 는 0~20)")' \
    '    wait_s = int(env.get("CELERY_WAIT_TIME_SECONDS", "").strip() or BrokerSettings.wait_time_seconds)'
  pure_catches "P1 env.py 의 긴 폴링 읽기에서 범위 검사(1~20)를 뺀다" 'test_bad_broker_values_stop_startup'
  restore

  plant "$CELERYPY" '"wait_time_seconds": broker.wait_time_seconds,' '"wait_time_seconds": 10,'
  pure_catches "P2 celery.py 가 설정을 무시하고 10 을 글자로" 'test_the_long_poll_comes_from_the_settings'
  restore

  plant "$ENVPY" '    wait_time_seconds: int = 10' '    wait_time_seconds: int = 2'
  pure_catches "P3 기본값 10 → 2" 'test_the_conf_is_exactly_these_names_and_values'
  restore

  plant compose.yaml '      CELERY_WAIT_TIME_SECONDS: ${CELERY_WAIT_TIME_SECONDS:-}
' ''
  pure_catches "P4 compose.yaml 의 api-py 에서 CELERY_WAIT_TIME_SECONDS 줄을 지운다" 'test_compose_api_py_and_env_carry_the_same_broker_keys'
  restore

  plant compose.yaml '  redis:
    profiles: ["ts"]
' '  redis:
'
  gates_catches "P5 compose.yaml 의 redis 에서 profiles 를 지운다" 'compose.yaml: TS 넷(api·worker·migrate·redis)은 프로필 ts 뒤, 프로필 없는 서비스의 depends_on 에 TS 넷 없음'
  restore
}

# ── 컨테이너 ──────────────────────────────────────────────────────────
it() { # <기록 파일> <노드…>   통합 시험 몇 개(이 프로세스의 환경 그대로)
  local out="$1"; shift
  (cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -c tests_integration/pytest.ini "$@") > "$out" 2>&1
}
worker_wait_time() {
  docker compose exec -T worker-py python -c "from esgapi.config.celery import app; print(app.conf.broker_transport_options['wait_time_seconds'])" 2> /dev/null | tail -1 | tr -d '\r'
}
settle() { sleep $((WT + 1)); }   # 앞 판의 죽은 긴 폴링이 끝나기를(판마다 독립이게)
# 같은 시험을 세 번: 한 번 이상 빨가면 「잡음」. 빨강 수/3 을 적는다.
thrice() { # <번호와 설명> <노드> [보고만=1]
  local i red=0 codes="" f
  for i in 1 2 3; do
    settle
    f="$log/$total.$i.c"
    it "$f" "$2"; local c=$?
    codes="$codes$c "
    [ "$c" -ne 0 ] && red=$((red + 1))
  done
  if [ "${3:-0}" = 1 ]; then
    report "$1" "빨강 $red/3 · 종료 코드 ${codes}· 1분 부하 $(load1) · 기록 $log/$total.*.c"
  else
    verdict "$1" "$([ "$red" -ge 1 ] && echo 1 || echo 0)" "빨강 $red/3 · 종료 코드 ${codes}· 1분 부하 $(load1) · 기록 $log/$total.*.c"
  fi
}
one() { # <번호와 설명> <노드> <빨강의 글자(무늬)>
  local f="$log/$total.one"
  settle
  it "$f" "$2"; local c=$?
  local caught=0
  [ "$c" -ne 0 ] && grep -q -E "$3" "$f" && caught=1
  verdict "$1" "$caught" "종료 $c · $(summary_of "$f") · 기록 $f"
}

containers_mode() {
  WT="$(worker_wait_time)"
  case "$WT" in '' | *[!0-9]*) echo "★ worker-py 의 긴 폴링을 못 읽었다(떠 있나?): '$WT'"; exit 1 ;; esac
  echo "# C5 worker-py 가 받은 긴 폴링 = ${WT}초 · 이 프로세스의 CELERY_WAIT_TIME_SECONDS='${CELERY_WAIT_TIME_SECONDS:-}' (대조, 셈 밖)"
  if [ "$WT" = 10 ]; then
    [ -z "${CELERY_WAIT_TIME_SECONDS:-}" ] || { echo "★ 기본값 판인데 시험 쪽에 CELERY_WAIT_TIME_SECONDS 가 있다"; exit 1; }
    echo "# (기본값 판: C1 · C6)"
    settle; it "$log/0.c" "$SWAP" "$KILL" || { echo "★ 0번(심지 않음)이 빨갛다: $(summary_of "$log/0.c") · $log/0.c"; exit 1; }
    echo "# 0 심지 않음(바꿔치기·SIGKILL) → 초록 · $(summary_of "$log/0.c")"

    plant "$WF" 'POLL_SETTLE_S = WAIT_TIME_S + 1' 'POLL_SETTLE_S = 0'
    thrice "C1 (기본값 판) POLL_SETTLE_S = 0 → 바꿔치기" "$SWAP"
    thrice "C1 (기본값 판) POLL_SETTLE_S = 0 → SIGKILL 임대 인수" "$KILL"
    restore

    plant "$WF" '@pytest.fixture(scope="session", autouse=True)
def the_worker_has_the_long_poll_the_tests_assume()' '@pytest.fixture(scope="session", autouse=False)
def the_worker_has_the_long_poll_the_tests_assume()'
    export CELERY_WAIT_TIME_SECONDS=2
    thrice "C6 어긋남: 워커 10 · 시험만 2(쉼 3), 세션 시작 단언을 끈 사본 → 바꿔치기" "$SWAP"
    restore
    one "C6 대조: 같은 어긋남, 단언을 켠 채 → 첫 단언에서 빨강" "$SWAP" "worker-py 의 긴 폴링은 10초인데 시험은 2초"
    unset CELERY_WAIT_TIME_SECONDS
  else
    [ "${CELERY_WAIT_TIME_SECONDS:-}" = "$WT" ] || { echo "★ 짧은 값 판인데 시험 쪽의 값이 워커와 다르다: '${CELERY_WAIT_TIME_SECONDS:-}' ≠ $WT"; exit 1; }
    echo "# (짧은 값 판: C1s · C2 · C3 · C4)"
    settle; it "$log/0.c" "$SWAP" "$KILL" "$NONROOT_PARSER" "$PARSER_DOWN" "$SIGTERM" || { echo "★ 0번(심지 않음)이 빨갛다: $(summary_of "$log/0.c") · $log/0.c"; exit 1; }
    echo "# 0 심지 않음(바꿔치기·SIGKILL·parser 비루트·파서 멈춤·SIGTERM) → 초록 · $(summary_of "$log/0.c")"

    plant "$WF" 'POLL_SETTLE_S = WAIT_TIME_S + 1' 'POLL_SETTLE_S = 0'
    thrice "C1s (짧은 값 판) POLL_SETTLE_S = 0 → 바꿔치기" "$SWAP" 1
    thrice "C1s (짧은 값 판) POLL_SETTLE_S = 0 → SIGKILL 임대 인수" "$KILL" 1
    restore

    plant compose.yaml '  parser:
    build: { context: ., dockerfile: docker/parser.Dockerfile }' '  parser:
    user: "0:0"
    build: { context: ., dockerfile: docker/parser.Dockerfile }'
    parser_dirty=1
    docker compose up -d --no-deps --force-recreate --wait parser > "$log/c2.up" 2>&1 || { echo "★ C2 의 parser 를 못 띄웠다: $log/c2.up"; exit 1; }
    one "C2 compose.yaml 의 parser 에 user: \"0:0\" → parser 비루트" "$NONROOT_PARSER" "assert '0' == '10001'|AssertionError"
    restore   # parser 를 원래 꼴로 다시 만든다

    plant "$WF" '    compose("stop", "parser")
    try:
        document_id, _ = create_and_put(http, headers, pdf)
        confirm(http, headers, document_id)
        job = wait_finished(http, headers, document_id, timeout=60 + MAX_ATTEMPTS * RETRY_DELAY_S)' '    try:
        document_id, _ = create_and_put(http, headers, pdf)
        confirm(http, headers, document_id)
        job = wait_finished(http, headers, document_id, timeout=60 + MAX_ATTEMPTS * RETRY_DELAY_S)'
    one "C3 파서 멈춤 시험에서 compose stop parser 를 뺀다" "$PARSER_DOWN" "'done'"
    restore

    plant "$WF" '        compose("kill", "-s", "SIGTERM", "worker-py")' '        compose("kill", "-s", "SIGKILL", "worker-py")'
    one "C4 SIGTERM 시험에서 SIGTERM → SIGKILL" "$SIGTERM" "AssertionError"
    restore
  fi
}

case "$MODE" in
  --pure) pure_mode ;;
  --containers) containers_mode ;;
esac

restore
trap - EXIT INT TERM
fingerprint > "$keep/.after"
if ! cmp -s "$keep/.before" "$keep/.after"; then
  echo "★ 지문이 처음과 다르다:"; diff "$keep/.before" "$keep/.after"
  exit 1
fi
echo "지문: 처음과 같다(git status --porcelain $(sed '$d' "$keep/.after" | grep -c . || true)줄 · git diff sha256 $(tail -1 "$keep/.after" | cut -c1-16))"
echo "기록: $log"
echo "PLANTED=$ok/$total"
[ "$ok" -eq "$total" ]
