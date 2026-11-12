#!/usr/bin/env bash
# 밴드 T2(MARC-TICK-98)의 심은 파손: 하나씩 심고, 그것을 잡아야 하는 자리가 잡는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-T2.sh --pure         P1~P6(컨테이너 없음)                마지막 줄 PLANTED=<잡음>/<전체>
#         apps/api-py/scripts/planted-breaks-T2.sh --containers   P7(떠 있는 이 워크트리의 compose 프로젝트에서. 짧은 값으로 띄운 것)
# 0번은 심지 않고 돌린다(그 모드의 시험이 초록이어야 한다 — 처음부터 빨간 것을 「잡았다」고 세지 않게. 0번이 빨가면
#   PLANTED 를 내지 않고 종료 1).
# 심는 것은 전부 있는 파일의 글자 바꿈이다. 되돌리기는 저장소 밖 임시 폴더의 사본을 cp 한다(git stash·checkout·restore 를
# 쓰지 않는다. 죽어도 trap 이 되돌린다). 끝에서 `git status --porcelain` 과 `git diff` 의 sha256 이 처음과 같은지 잰다.
# 다르면 PLANTED 를 내지 않고 종료 1.
# P7 의 대조(바닥 판)는 워크트리 안에서 test_worker_flow.py 를 `git show <바닥>:…` 의 판으로 잠깐 바꿔 끼워 돌린다(같은
# .env·.dev-keys·프로젝트를 쓴다). 띄우기·내리기는 부르는 쪽(section4-T2.sh --containers)이 한다.
# macOS /bin/bash 3.2 에서 돈다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-}"
case "$MODE" in --pure | --containers) ;; *) echo "사용: $0 --pure | --containers" >&2; exit 2 ;; esac

B=24ab83c   # 바닥(section4-T2.sh 의 B 와 같다)
A=apps/api-py
LOCKSH=scripts/lib/lock.sh
VERIFY=scripts/verify.sh
CMP=scripts/weekly_compare.py
WF="$A/tests_integration/test_worker_flow.py"
FILES="$LOCKSH $VERIFY $CMP $WF"
SIGTERM_TEST="tests_integration/test_worker_flow.py::test_a_worker_given_sigterm_finishes_the_job_in_hand_and_exits_0"

keep="$(mktemp -d)"   # 저장소 밖
log="$(mktemp -d)"
for f in $FILES; do mkdir -p "$keep/$(dirname "$f")"; cp "$f" "$keep/$f"; done
fingerprint() { git status --porcelain; git diff | shasum -a 256; }
fingerprint > "$keep/.before"
restore() {
  local f
  for f in $FILES; do cmp -s "$keep/$f" "$f" || cp "$keep/$f" "$f"; done
}
trap 'restore' EXIT
trap 'restore; exit 130' INT
trap 'restore; exit 143' TERM

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
load1() { uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p'; }

# ── 순수: check-gates 의 검사 이름별 EXIT ────────────────────────────
gates() { scripts/check-gates.sh > "$1" 2>&1; }
# <로그> <검사 이름의 앞 글자> → 그 검사의 EXIT 값
exit_of() { awk -v want="▶ $2" 'index($0, want) == 1 { on = 1; next } on && /^EXIT=/ { print substr($0, 6); exit }' "$1"; }
red_in_gates() { # <번호와 설명> <빨개야 할 검사 이름의 앞 글자>...
  local what="$1" f="$log/$total.gates" name all=1 got=""
  shift
  gates "$f"
  for name in "$@"; do
    got="${got}「${name}」 EXIT=$(exit_of "$f" "$name") "
    [ "$(exit_of "$f" "$name")" != 0 ] && [ -n "$(exit_of "$f" "$name")" ] || all=0
  done
  verdict "$what" "$all" "${got}· $(tail -1 "$f")"
  restore
}
selftest_red() { # <번호와 설명> <빨개야 할 자기 시험 줄의 앞 글자>
  local f="$log/$total.self"
  python3 -I "$CMP" --self-test > "$f" 2>&1
  local code=$?
  if [ "$code" -ne 0 ] && grep -q "★ 실패 $2" "$f"; then
    verdict "$1" 1 "$(grep '★ 실패' "$f" | tr '\n' ';') $(tail -1 "$f")"
  else
    verdict "$1" 0 "종료 코드 $code · $(tail -1 "$f")"
  fi
  restore
}

pure_mode() {
  echo "# 0번(심지 않음): check-gates · 견주기 자기 시험 · 1분 부하 $(load1)"
  gates "$log/0.gates"
  python3 -I "$CMP" --self-test > "$log/0.self" 2>&1
  local self=$?
  echo "#   $(tail -1 "$log/0.gates") · $(tail -1 "$log/0.self")"
  if [ "$(tail -1 "$log/0.gates" | cut -d' ' -f1)" != "GATES=PASS" ] || [ "$self" -ne 0 ]; then
    echo "★ 0번이 빨갛다 — PLANTED 를 내지 않는다"; return 1
  fi

  plant "$LOCKSH" '    if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
      # 죽은 잠금.' '    if false; then
      # 죽은 잠금.'
  red_in_gates "P1 lock.sh 의 죽은 pid 검사를 뺀다(늘 「살아 있다」)" "B5 " "W5 "

  plant "$VERIFY" 'then release_build_lock; release_lock; fi' 'then release_lock; fi'
  red_in_gates "P2 verify.sh 의 on_exit 에서 빌드 잠금 놓기를 뺀다" "B3 build 중 SIGINT" "B3 build 중 SIGTERM"

  plant "$VERIFY" '  [ "$PLAN" -eq 0 ] && acquire_build_lock
fi
container_step docker compose build
' '  :
fi
container_step docker compose build
[ "$FAST" -eq 0 ] && [ "$PLAN" -eq 0 ] && acquire_build_lock
'
  red_in_gates "P3 빌드 잠금 잡기를 build 단계 뒤로 옮긴다" "B1 "

  plant "$LOCKSH" '  if [ "$(cat "$1/pid" 2>/dev/null)" = "$$" ]; then rm -rf "$1"; fi' '  rm -rf "$1"'
  red_in_gates "P4 lock_release 의 pid 비교를 뺀다(남의 잠금도 지움)" "B4 " "W3 "

  plant "$CMP" '    key = (func, diff_lines(body))' '    key = ("", diff_lines(body))'
  selftest_red "P5 견주기 열쇠에서 함수 이름을 뺀다" "⑥"

  plant "$CMP" '    func = strip_number(head[0])' '    func = head[0]'
  selftest_red "P6 견주기가 변이 번호를 열쇠에 남긴다" "④"
}

# ── 컨테이너: P7 ─────────────────────────────────────────────────────
WARM="worker: Warm shutdown (MainProcess)"
warm_count() { docker compose logs --no-color worker-py 2>/dev/null | grep -c -F "$WARM"; }
ready_count() { docker compose logs --no-color worker-py 2>/dev/null | grep -c ' ready\.'; }
# 같은 컨테이너에 낡은 Warm shutdown 줄을 남긴다: stop(따뜻한 종료가 그 줄을 찍는다) → start → ready 가 하나 더
leave_an_old_line() {
  local ready_before tries=0
  ready_before="$(ready_count)"
  docker compose stop worker-py > /dev/null 2>&1 || return 1
  docker compose start worker-py > /dev/null 2>&1 || return 1
  while [ "$(ready_count)" -le "$ready_before" ] && [ "$tries" -lt 60 ]; do sleep 1; tries=$((tries + 1)); done
  [ "$(ready_count)" -gt "$ready_before" ] || return 1
  # 앞 워커의 긴 폴링이 끝나기를(시험의 recreate_worker 와 같은 쉼 — 짧은 값 2초 + 1)
  sleep 3
  echo "  (stop·start 뒤 같은 컨테이너의 기록: Warm shutdown $(warm_count)줄 · ready $(ready_count)줄)"
}
sigterm_run() { (cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -c tests_integration/pytest.ini "$SIGTERM_TEST") > "$1" 2>&1; }

containers_mode() {
  local f code
  echo "# 0번(심지 않음): SIGTERM 시험 · 1분 부하 $(load1)"
  sigterm_run "$log/0.sig"; code=$?
  echo "#   $(grep -E '[0-9]+ (passed|failed|error)' "$log/0.sig" | tail -1) · 종료 $code"
  [ "$code" -eq 0 ] || { echo "★ 0번이 빨갛다 — PLANTED 를 내지 않는다"; tail -20 "$log/0.sig"; return 1; }

  # 고친 판: 신호를 SIGCONT 로(워커는 아무 일 없음), 같은 컨테이너에 낡은 줄을 남긴 뒤
  plant "$WF" 'compose("kill", "-s", "SIGTERM", "worker-py")' 'compose("kill", "-s", "SIGCONT", "worker-py")'
  leave_an_old_line || { echo "★ 낡은 줄을 남기지 못했다(stop·start·ready)"; return 1; }
  f="$log/p7.fixed"; sigterm_run "$f"; code=$?
  local fixed_where; fixed_where="$(grep -o '기다렸지만 되지 않았다([0-9.]*초): [^/]*' "$f" | head -1)"
  restore
  case "$fixed_where" in *"워커가 신호를 받았다고 적기"*) verdict "P7 고친 판: SIGTERM 을 SIGCONT 로 + 낡은 Warm shutdown 줄" 1 "종료 $code · $fixed_where" ;;
    *) verdict "P7 고친 판: SIGTERM 을 SIGCONT 로 + 낡은 Warm shutdown 줄" 0 "종료 $code · ${fixed_where:-기다림 실패 줄 없음} · $(grep -E '[0-9]+ (passed|failed)' "$f" | tail -1)" ;;
  esac

  # 대조(바닥 판): 워크트리 안에서 바닥의 시험 파일로 바꿔 끼우고 같은 것을 심는다(되돌림은 cp)
  git show "$B:$WF" > "$WF" || { echo "★ 바닥 판을 꺼내지 못했다"; return 1; }
  plant "$WF" 'compose("kill", "-s", "SIGTERM", "worker-py")' 'compose("kill", "-s", "SIGCONT", "worker-py")'
  leave_an_old_line || { echo "★ 낡은 줄을 남기지 못했다(바닥 판 앞)"; restore; return 1; }
  f="$log/p7.base"; sigterm_run "$f"; code=$?
  local base_where; base_where="$(grep -o '기다렸지만 되지 않았다([0-9.]*초): [^/]*' "$f" | head -1)"
  restore
  echo "# P7 대조(바닥 $B 의 판, 셈에 넣지 않음) → 종료 $code · ${base_where:-기다림 실패 줄 없음} — 신호 기다림은 낡은 줄로 지나고 다른 자리에서 빨강이어야 한다"
  case "$base_where" in *"워커가 신호를 받았다고 적기"*) echo "#   ★ 바닥 판도 신호 기다림에서 빨갛다(대조가 갈리지 않음)" ;; esac
}

if [ "$MODE" = --pure ]; then pure_mode; else containers_mode; fi
mode_code=$?
restore
fingerprint > "$keep/.after"
if ! cmp -s "$keep/.before" "$keep/.after"; then
  echo "★ 작업 트리가 처음과 다르다(지문)"; diff "$keep/.before" "$keep/.after"; exit 1
fi
echo "# 지문(git status --porcelain + git diff 의 sha256): 처음과 같음"
[ "$mode_code" -eq 0 ] || exit 1
echo "PLANTED=$ok/$total"
[ "$ok" -eq "$total" ]
