#!/usr/bin/env bash
# 밴드 D0(MARC-TICK-88: 그린워싱 의존성 일곱을 api-py 에 더한다. 코드는 0줄)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-D0.sh                  커밋 ① 뒤(이 스크립트는 아직 커밋 전)
#         apps/api-py/scripts/section4-D0.sh --after-commit   같은 것 + 커밋된 모습(작업 트리 0줄, 커밋, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 컨테이너 층은 돌리지 않는다(감독이 병합 뒤 main 전량). AI 공급사 호출 0. 네트워크는 uv·pnpm 의 설치뿐.
# bash 전용이다(${PIPESTATUS[0]}).
#
# ★ (나) 의 머리 검사는 감독 지시(2026-10-15)로 더한 것이다.
# ★ (아) 는 발주서 §4 의 여덟 밖에 더한 것이다: ★2(원격 전송이 기본 꺼짐)를 실행으로 잰다. LANGSMITH_·LANGCHAIN_
#   환경 변수를 지우고 소켓 연결을 막은 채 text-splitters 로 나누고 Runnable 을 한 번 부른다 — 연결 시도 0.
set -u
cd "$(dirname "$0")/../../.."
B=b78a477   # 기준 커밋(발주서: 워크트리를 만들 때의 main)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-}"
case "$MODE" in "" | --after-commit) ;; *) echo "사용: $0 [--after-commit]" >&2; exit 2 ;; esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
A=apps/api-py
PY="$A/pyproject.toml"
LOCK="$A/uv.lock"
export A PY LOCK T B

FAILS=0
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 §1) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -x \
    -e 'apps/api-py/pyproject.toml' \
    -e 'apps/api-py/uv.lock' \
    -e 'apps/api-py/scripts/section4-D0.sh'
}

echo "── 밴드 D0 §4 · ${MODE:-커밋 ① 뒤} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

echo; echo "── 가. 잠금이 pyproject 와 맞음"
run '(cd "$A" && uv lock --check 2>&1 | tail -1; exit ${PIPESTATUS[0]})'

echo; echo "── 나. 잠금은 더하기만: 기준 대비 지운 version·name 줄 0, 더한 꾸러미 23"
run 'v="$(git diff -U0 "$B" -- "$LOCK" | grep -c -E "^-version")"; n="$(git diff -U0 "$B" -- "$LOCK" | grep -c -E "^-name")"; a="$(git diff -U0 "$B" -- "$LOCK" | grep -c -E "^\+name")"; echo "  -version $v · -name $n · +name $a"; [ "$v" = 0 ] && [ "$n" = 0 ] && [ "$a" = 23 ]'
run 'git diff -U0 "$B" -- "$LOCK" | grep -E "^-[^-]" > "$T/lock-minus.txt"; cat "$T/lock-minus.txt"; echo "  지운 줄: $(wc -l < "$T/lock-minus.txt" | tr -d " ")"; test ! -s "$T/lock-minus.txt"'
# 잠금 머리(version·revision)가 기준과 같다: 이미지의 uv(docker/api-py.Dockerfile 의 0.7.13)가 쓰는 꼴. 호스트 uv 가 새 꼴로 다시 쓰면 빨강.
run 'git show "$B:$LOCK" | head -2 > "$T/head-base.txt"; head -2 "$LOCK" > "$T/head-now.txt"; cat "$T/head-now.txt" | sed "s/^/  /"; cmp "$T/head-base.txt" "$T/head-now.txt"'

echo; echo "── 다. pyproject 의 일곱 줄이 정확한 판, 그 밖에 지운 줄 0"
run 'bad=0; for d in pypdf==6.20.1 langchain-text-splitters==1.1.3 langchain-core==1.6.10 numpy==2.5.4 tiktoken==0.14.0 jsonschema==4.26.0 openpyxl==3.1.5; do grep -q -E "^[[:space:]]+\"$d\",([[:space:]]|$)" "$PY" && echo "  $d" || { echo "★ 없다: $d"; bad=1; }; done; [ "$bad" = 0 ]'
run 'n="$(git diff -U0 "$B" -- "$PY" | grep -c -E "^-[^-]")"; echo "  pyproject 에서 지운 줄: $n"; [ "$n" = 0 ]'

echo; echo "── 라. 설치된 판이 발주서 §1 과 같음"
run '(cd "$A" && uv run --frozen python -I -c "
import importlib.metadata as m
import pypdf, langchain_text_splitters, langchain_core, numpy, tiktoken, jsonschema, openpyxl
want = {\"pypdf\": \"6.20.1\", \"langchain-text-splitters\": \"1.1.3\", \"langchain-core\": \"1.6.10\", \"numpy\": \"2.5.4\", \"tiktoken\": \"0.14.0\", \"jsonschema\": \"4.26.0\", \"openpyxl\": \"3.1.5\"}
got = {n: m.version(n) for n in want}
print(\" \", got)
assert got == want
")'

echo; echo "── 마. 빠른 게이트(뿌리에서)"
run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -6; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'

echo; echo "── 바. 휠"
run '"$A/scripts/check-wheel.sh" 2>&1 | tail -3; exit ${PIPESTATUS[0]}'

echo; echo "── 사. 경계: 허용 경로 밖 0, generated/ 가 기준과 같고 다시 뽑아도 같음"
run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
run 'git diff --quiet "$B" -- "$A/generated"'
run '(cd "$A" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

echo; echo "── 아. 원격 전송이 기본 꺼짐(실행으로): 환경 변수 없이 연결 시도 0"
run '(cd "$A" && uv run --frozen python -I -c "
import os, socket
for k in [k for k in os.environ if k.startswith((\"LANGSMITH_\", \"LANGCHAIN_\"))]:
    del os.environ[k]
calls = []
def deny(self, *a, **k):
    calls.append(a)
    raise OSError(\"network denied\")
socket.socket.connect = deny
socket.socket.connect_ex = deny
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnableLambda
from langsmith import utils
chunks = RecursiveCharacterTextSplitter(chunk_size=20, chunk_overlap=0).split_text(\"가나다라 마바사 아자차카 타파하 \" * 5)
out = RunnableLambda(lambda x: x + 1).invoke(1)
print(\"  tracing_is_enabled:\", utils.tracing_is_enabled(), \"· 조각\", len(chunks), \"· 연결 시도\", len(calls))
assert utils.tracing_is_enabled() is False and not calls and out == 2
")'
run 'n="$(git grep -n -i -E "LANGSMITH|LANGCHAIN" -- .env.example "$A/esgapi/config" compose.yaml docker | wc -l | tr -d " ")"; echo "  우리 설정에서 그 변수를 적은 줄: $n"; [ "$n" = 0 ]'

if [ "$MODE" = --after-commit ]; then
  echo; echo "── 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 2'
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do for t in "Ticket: MARC-TICK-88" "Derives-from: MARC-TICK-74"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
fi

echo
echo "── 바뀐 파일 수 (기준 $B 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
