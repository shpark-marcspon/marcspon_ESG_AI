# 잠금과 문 — scripts/verify.sh · scripts/with-build-lock.sh · scripts/weekly.sh 가 source 해서 쓴다(혼자 돌지 않는다).
# macOS 의 /bin/bash 3.2 에서 돈다. 이 파일은 cd 하지 않고, 전역 이름은 LOCK_ 으로 시작하는 둘만 쓴다.
#
# 잠금은 폴더 하나다(mkdir 가 원자다). 안에 pid(잡은 셸의 $$)·worktree(pwd)·started, 그리고 있으면 what(무엇을 하는가).
#   lock_acquire <자리> <상한 초> <간격 초> <기다림 글의 머리> [<what> [<되들어감 pid>]]
#     0  잡았다(LOCK_ACQUIRED=new) 또는 이미 쥐었다(LOCK_ACQUIRED=held — 잠금의 pid 가 <되들어감 pid> 이고 살아 있다.
#        이때는 아무것도 쓰지 않고, 놓는 것도 잡은 바깥의 몫이다). LOCK_WAITED 는 기다린 초.
#     75 상한을 넘겼다(쥔 pid·자리·시작 시각을 한 줄 찍었다). 무엇을 찍고 몇으로 끝낼지는 부른 쪽이 정한다.
#     2  잠금 자리를 만들 수 없다(부모 폴더가 없거나 쓸 수 없다) — 기다리지 않는다(빈 pid 를 「남이 쥠」으로 읽어
#        상한까지 기다리는 꼴을 막는다).
#   잡혀 있으면 「<머리>: pid … · <자리> · <시각> 시작. 기다린다(n/상한초)」 를 찍고 <간격> 초마다 다시 본다.
#   쥔 pid 가 죽어 있으면 치우고 가져간다. 치우는 것은 한 번에 하나만(<자리>.reap), 그 안에서 pid 를 다시 읽고 옮긴다:
#   기다리던 둘이 같이 치우면 한쪽이 방금 새로 잡힌 잠금을 옮겨 버려 둘 다 쥐게 된다.
#   lock_release <자리>   내 pid($$)의 잠금일 때만 지운다. 아무것도 찍지 않는다.
# 못 막는 것: pid 재사용(살아 있는 잠금으로 보인다), SIGKILL(놓지 못한다 — 다음이 「죽은 잠금」으로 치운다),
#   mkdir 과 pid 적기 사이나 치우는 중(<자리>.reap)에 죽는 것(사람이 그 폴더를 지워야 한다).

LOCK_ACQUIRED=""
LOCK_WAITED=0

lock_acquire() {
  local dir="$1" limit="$2" poll="$3" head="$4" what="${5:-}" reenter="${6:-}" waited=0 holder nap
  LOCK_ACQUIRED=""
  LOCK_WAITED=0
  while :; do
    if mkdir "$dir" 2>/dev/null; then
      echo "$$" > "$dir/pid"
      pwd > "$dir/worktree"
      date '+%Y-%m-%d %H:%M:%S' > "$dir/started"
      [ -n "$what" ] && printf '%s\n' "$what" > "$dir/what"
      LOCK_ACQUIRED=new
      LOCK_WAITED=$waited
      return 0
    fi
    if [ ! -e "$dir" ]; then
      # mkdir 이 실패했는데 잠금이 없다: 부모를 못 쓰면 닫힌 쪽으로, 아니면 그 사이 놓인 것이니 다시 잡아 본다
      if [ ! -d "$(dirname "$dir")" ] || [ ! -w "$(dirname "$dir")" ]; then
        echo "잠금 자리를 만들 수 없다(부모 폴더가 없거나 쓸 수 없다): $dir"
        return 2
      fi
      continue
    fi
    holder="$(cat "$dir/pid" 2>/dev/null)"
    if [ -n "$reenter" ] && [ "$holder" = "$reenter" ] && kill -0 "$holder" 2>/dev/null; then
      LOCK_ACQUIRED=held
      LOCK_WAITED=$waited
      return 0
    fi
    if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
      # 죽은 잠금. 치우는 것은 한 번에 하나만(<자리>.reap), 그 안에서 pid 를 다시 읽고 옮긴다.
      if mkdir "$dir.reap" 2>/dev/null; then
        holder="$(cat "$dir/pid" 2>/dev/null)"
        if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null && mv "$dir" "$dir.stale.$$" 2>/dev/null; then
          echo "죽은 잠금을 치운다(pid $holder 는 살아 있지 않다): $dir"
          rm -rf "$dir.stale.$$"
        fi
        rmdir "$dir.reap"
        continue   # 치웠다(또는 그 사이 남이 치웠다). 다시 잡아 본다
      fi
      # 다른 실행이 치우는 중이다. 아래에서 기다린다.
    fi
    if [ "$waited" -ge "$limit" ]; then
      echo "$head(${waited}초 기다림): pid ${holder:-?} · $(cat "$dir/worktree" 2>/dev/null) · $(cat "$dir/started" 2>/dev/null) 시작$(lock_what_of "$dir")"
      LOCK_WAITED=$waited
      return 75
    fi
    echo "$head: pid ${holder:-?} · $(cat "$dir/worktree" 2>/dev/null) · $(cat "$dir/started" 2>/dev/null) 시작$(lock_what_of "$dir"). 기다린다(${waited}/${limit}초)"
    nap=$((limit - waited))
    [ "$nap" -gt "$poll" ] && nap="$poll"
    sleep "$nap"
    waited=$((waited + nap))
  done
}

# 잠금에 what 이 있으면 「 · <what>」 (없으면 빈 글 — verify.lock 은 what 을 쓰지 않아 기다림 글이 예전 그대로다)
lock_what_of() {
  local w
  w="$(cat "$1/what" 2>/dev/null)"
  [ -n "$w" ] && printf ' · %s' "$w"
  return 0
}

lock_release() {
  if [ "$(cat "$1/pid" 2>/dev/null)" = "$$" ]; then rm -rf "$1"; fi
}

# 기계 메모리의 남은 몫(%, 정수)을 찍는다. memory_pressure(macOS)가 있으면 그 「free percentage」, 없으면
# ${FREE_MEMINFO:-/proc/meminfo}(리눅스)의 MemAvailable/MemTotal. 둘 다 없으면 아무것도 찍지 않고 1(「free 모름」).
# memory_pressure 가 있는데 그 글을 못 읽으면 빈 값에 0 — 부른 쪽은 지금처럼 닫힘으로 읽는다.
# FREE_MEMINFO 는 scripts/check-gates.sh 의 자기 검사 전용이다(손으로 쓰지 않는다).
free_percent() {
  local meminfo="${FREE_MEMINFO:-/proc/meminfo}"
  if command -v memory_pressure > /dev/null 2>&1; then
    memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p'
    return 0
  fi
  [ -r "$meminfo" ] || return 1
  awk '/^MemTotal:/ { t = $2 } /^MemAvailable:/ { a = $2 } END { if (t > 0 && a != "") printf "%d\n", a * 100 / t }' "$meminfo"
}

# ── 문 ────────────────────────────────────────────────────────────────
# 컨테이너나 무거운 일을 시작하기 전에 기계가 한가해지기를 기다린다. 아무 잠금도 쥐지 않고 기다린다(잠금은 문을
# 지난 뒤에 잡는다 — build.lock 을 쥔 채 verify.lock 을 기다리는 곳 0). 60초마다, 30분까지. 숫자는 글자로 박는다.
#   container_door <자기 compose 프로젝트>   (사용자 결정 2026-10-15 「컨테이너 새 규칙」)
#     · 자기 밖의 esg-app* compose 프로젝트(docker compose ls -q — main 의 esg-app 도 센다) 둘 이하
#       (들어가면 셋까지 — 「띄운 esg-app* 벌은 셋까지」)
#     · verify.lock 없음(감독의 전량은 혼자 돈다) · build.lock 없음 · free ≥ 20%(free_percent. 「free 모름」이면 이 조건만
#       건너뛴다) · 1분 부하 < 24
#   host_door   위에서 compose 프로젝트 셈과 build.lock 을 뺀 것(컨테이너를 띄우지 않는 무거운 일 — mutmut)
#   0 열렸다 · 75 30분 안에 안 열렸다 · 2 잠금 자리를 계산하지 못했다(git 저장소 밖)
# 잠금 자리는 VERIFY_LOCK_DIR·BUILD_LOCK_DIR 가 있으면 그것, 없으면 지금 자리의 <git 공통 폴더>/verify.lock·build.lock.
container_door() { lock_door compose "$1"; }
host_door() { lock_door host ""; }

lock_door() {
  local kind="$1" self="$2" common="" vlock block tries=0 free free_known load others names ok why
  if [ -z "${VERIFY_LOCK_DIR:-}" ] || [ -z "${BUILD_LOCK_DIR:-}" ]; then
    common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
    [ -n "$common" ] || { echo "  (문: 잠금 자리를 계산하지 못했다 — git 저장소 밖: $(pwd))"; return 2; }
  fi
  vlock="${VERIFY_LOCK_DIR:-$common/verify.lock}"
  block="${BUILD_LOCK_DIR:-$common/build.lock}"
  while :; do
    free_known=1
    free="$(free_percent)" || free_known=0
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    ok=1
    why="verify.lock $([ -e "$vlock" ] && echo 있음 || echo 없음)"
    [ -e "$vlock" ] && ok=0
    if [ "$kind" = compose ]; then
      names="$(docker compose ls -q 2>/dev/null | grep '^esg-app' | grep -v -x -F "$self" | tr '\n' ' ')"
      others="$(printf '%s' "$names" | wc -w | tr -d ' ')"
      why="자기 밖 esg-app* 프로젝트 $others(${names:-없음}) · $why · build.lock $([ -e "$block" ] && echo 있음 || echo 없음)"
      [ "$others" -le 2 ] || ok=0
      [ -e "$block" ] && ok=0
    fi
    if [ "$free_known" -eq 1 ]; then
      why="$why · free ${free:-?}% · 1분 부하 ${load:-?}"
      [ "${free:-0}" -ge 20 ] || ok=0
    else
      why="$why · free 모름 · 1분 부하 ${load:-?}"
    fi
    # 「< 24」 는 정수 부분으로 본다(23.9 는 열림, 24.0 은 닫힘). 못 읽으면 닫힘
    load="${load:-99}"
    [ "${load%%.*}" -lt 24 ] 2>/dev/null || ok=0
    if [ "$ok" -eq 1 ]; then
      echo "  (문 열림: $why · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    if [ "$tries" -ge 30 ]; then
      echo "  (문이 안 열렸다 — 30분: $why)"
      return 75
    fi
    echo "  (문 닫힘 — 60초 뒤 다시: $why)"
    tries=$((tries + 1))
    sleep 60
  done
}
