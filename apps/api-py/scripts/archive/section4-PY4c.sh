#!/usr/bin/env bash
# 밴드 PY4c(MARC-TICK-63: invalid_tables 응답이 받은 값을 싣는다)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-PY4c.sh           전체. 줄마다 EXIT=<종료 코드>. 전부 0 이어야 한다(하나라도 아니면 스크립트가 1 로 끝난다)
#         apps/api-py/scripts/section4-PY4c.sh --pure    컨테이너 없이 도는 것만
# 컨테이너는 postgres 하나만 띄우고(이미지를 짓지 않는다) 끝나면 내린다(down -v).
# 다루는 컨테이너·볼륨은 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독이 병합 뒤 main 에서). AI 공급사 호출 0. bash 전용.
set -u
cd "$(dirname "$0")/../../.."
B=269ce6b   # 기준 커밋(발주서 §1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 가 Node 22 를 쓴다
MODE="${1:-all}"
case "$MODE" in all | --pure) ;; *) echo "사용: $0 [--pure]" >&2; exit 2 ;; esac
API=apps/api-py/esgapi/inventory/api.py
F=esgapi/inventory/tests/test_api.py
TEST="$F::test_the_invalid_tables_message_carries_the_received_value"
OLD="$F::test_tables_that_fail_the_check_are_400_invalid_tables"
CUT="$F::test_a_long_problem_sentence_is_cut_at_the_limit"

run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
FAILS=0

# 허용 경로(발주서 §1) 밖에서 바뀐 파일이 0 인가. 추적 안 된 새 파일도 센다.
outside() {
  { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u | grep -v -x \
    -e 'apps/api-py/esgapi/inventory/api.py' \
    -e 'apps/api-py/esgapi/inventory/calc/tables.py' \
    -e 'apps/api-py/esgapi/inventory/tests/.*' \
    -e 'README.md' \
    -e 'apps/api-py/scripts/section4-PY4c.sh'
}

run 'scripts/verify.sh --fast > "${TMPDIR:-/tmp}/py4c-fast.log" 2>&1; code=$?; tail -5 "${TMPDIR:-/tmp}/py4c-fast.log"; grep -q "^VERIFY_FAST=PASS" "${TMPDIR:-/tmp}/py4c-fast.log" && exit $code; exit 1'
run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
run 'git diff "$B" -- apps/api-py/esgapi/inventory/calc/tables.py | grep "^[+-][^+-]" | grep -v "^[+-] *#"; n=$?; echo "tables.py 의 주석 아닌 변경 줄이 없다(grep 종료 1 이어야 한다): $n"; [ "$n" = 1 ]'
run 'grep -n "summary: str" apps/api-py/esgapi/inventory/calc/tables.py'
[ "$MODE" = "--pure" ] && { echo; echo "0 이 아닌 EXIT: $FAILS"; [ "$FAILS" = 0 ]; exit $?; }

# ── 업무 층: postgres 하나 ──
free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
echo
echo "── 메모리 free ${free:-?}%   $(uptime | sed 's/.*load/load/')"
run '[ "${free:-0}" -ge 20 ]'
run 'docker compose up -d --wait postgres 2>&1 | tail -3; exit ${PIPESTATUS[0]}'
run 'apps/api-py/scripts/test-business.sh esgapi/inventory 2>&1 | tail -4; exit ${PIPESTATUS[0]}'

# 심은 파손 둘. 저장소 밖 사본으로 되돌린다.
keep="$(mktemp)"
cp "$API" "$keep"
# ① api.py 를 p.summary 로 되돌리면 이름 붙은 테스트 둘이 빨개져야 한다.
run 'grep -c "_shown(p.where, p.problem)" "$API"'
sed -i '' 's/_shown(p\.where, p\.problem)/_shown(p.where, p.summary)/' "$API"
run 'grep -c "_shown(p.where, p.summary)" "$API"'
run 'apps/api-py/scripts/test-business.sh "$TEST" 2>&1 | tail -3; code=${PIPESTATUS[0]}; echo "심은 파손 ①(summary 로 되돌림) · 새 테스트: pytest 종료 $code (1 이어야 한다)"; [ "$code" = 1 ]'
run 'apps/api-py/scripts/test-business.sh "$OLD" 2>&1 | tail -3; code=${PIPESTATUS[0]}; echo "심은 파손 ①(summary 로 되돌림) · 있던 테스트: pytest 종료 $code (1 이어야 한다)"; [ "$code" = 1 ]'
cp "$keep" "$API"
# ② 자르기를 빼면 (b) 의 여섯 갈래가 전부 빨개져야 한다.
run 'grep -c "return line if len(line) <= _PROBLEM_CHARS else" "$API"'
sed -i '' 's/return line if len(line) <= _PROBLEM_CHARS else .*/return line/' "$API"
run 'grep -c "^    return line$" "$API"'
run 'apps/api-py/scripts/test-business.sh "$CUT" 2>&1 | tail -8; code=${PIPESTATUS[0]}; echo "심은 파손 ②(자르기를 뺌): pytest 종료 $code (1 이어야 한다)"; [ "$code" = 1 ]'
cp "$keep" "$API"
run 'git diff --quiet -- "$API"; [ $? = 1 ] && cmp -s "$keep" "$API"'
run 'apps/api-py/scripts/test-business.sh "$TEST" "$OLD" "$CUT" 2>&1 | tail -2; exit ${PIPESTATUS[0]}'

run 'docker compose down -v 2>&1 | tail -2; exit ${PIPESTATUS[0]}'
PROJECT="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env | tail -1)"
run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; i="$(docker images -q --filter "reference=$PROJECT-*" | wc -l | tr -d " ")"; echo "남은 컨테이너 $n · 볼륨 $v · 이미지 $i"; [ "$n$v$i" = 000 ]'

echo
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
