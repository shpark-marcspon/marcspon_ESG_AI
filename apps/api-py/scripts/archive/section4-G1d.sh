#!/usr/bin/env bash
# 밴드 G1d 의 §4 자기검증(발주서 band-handoffs/G1d-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-G1d.sh                 전부
#   apps/api-py/scripts/section4-G1d.sh --step 1,2,8    일부(번호는 아래의 번호. 1~7 은 발주서 §4 의 번호, 8 은 §3 (a) 의 바이트 대조)
#
# 환경 변수:
#   G1D_BASE   기준 커밋(기본: 착수 때 적은 6d93b84…)
#   G1D_OUT    산출물 자리(기본: 워크트리 곁의 G1d.out). 산출물은 $G1D_OUT/section4/ 아래
#   G1D_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt)
#   G1D_PRIVATE_ENV  공개 보고서 자리를 적은 파일(기본: 워크트리 곁의 G1a.out/private.env — 7번이 그 자리 글이 추적 파일에
#              없는지 보려고 G1A_REPORTS_DIR 한 줄만 읽는다)
# 공개 보고서 실측(§3 (h))은 여기에 없다($G1D_OUT/locate-public.py, 추적 밖).
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${G1D_BASE:-6d93b84ad6456030c85a4c4e1507724cf0c34621}"
OUT="${G1D_OUT:-$SIDE/G1d.out}"
WORDS="${G1D_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
PRIVATE="${G1D_PRIVATE_ENV:-$SIDE/G1a.out/private.env}"
S4="$OUT/section4"
mkdir -p "$S4"
api() { (cd "$API_PY" && uv run --frozen "$@"); }
pyt() { # pyt <로그 이름> <pytest 인자…>
  local log="$S4/$1.log"; shift
  api pytest -q -rfE -p no:cacheprovider "$@" > "$log" 2>&1
  local e=$?
  grep -E '^FAILED|^ERROR|passed|failed|error' "$log" | tail -5 | sed 's/^/    /'
  return $e
}

STEPS="all"
if [ "${1:-}" = "--step" ]; then
  STEPS=",${2:?--step 뒤에 번호},"
fi
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

# 바뀐 파일(커밋된 것 + 작업 트리 + 새 파일), 저장소 뿌리 기준 경로. 지워진 파일도 든다.
changed_files() {
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u
}

ALLOWED='^(apps/api-py/esgapi/greenwash/flows/(adapters|pdfium_locate|colab)\.py|apps/api-py/esgapi/greenwash/tests/.*|apps/api-py/scripts/(section4|planted-breaks)-G1d\.sh)$'

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse HEAD), 산출물 $S4"

if want 1; then
  changed_files > "$S4/changed-files.txt"
  outside=$(grep -Ev "$ALLOWED" "$S4/changed-files.txt")
  n=$(grep -c . "$S4/changed-files.txt")
  echo "    바뀐 파일 $n, 허용 밖 $( [ -n "$outside" ] && echo "$outside" | grep -c . || echo 0)"
  [ -n "$outside" ] && echo "$outside" | sed 's/^/    밖: /'
  report 1 "허용 경로" "$([ -z "$outside" ] && echo 0 || echo 1)"
fi

ZERO="apps/api-py/esgapi/greenwash/calc apps/api-py/esgapi/greenwash/flows/shapes.py apps/api-py/esgapi/greenwash/tests/data/flow-shapes
  apps/api-py/esgapi/greenwash/tests/data/contract-examples apps/api-py/esgapi/greenwash/tests/data/golden apps/api-py/generated
  apps/api-py/esgapi/core apps/api-py/esgapi/config apps/api-py/.importlinter apps/api-py/pyproject.toml apps/api-py/uv.lock
  apps/web services apps/api-py/tests/security"

if want 2; then
  # shellcheck disable=SC2086
  zero=$(git -C "$ROOT" diff "$BASE" --stat -- $ZERO | tail -1)
  # shellcheck disable=SC2086
  untracked=$(git -C "$ROOT" ls-files -o --exclude-standard -- $ZERO | grep -c .)
  colab=$(git -C "$ROOT" diff "$BASE" --stat -- apps/api-py/esgapi/greenwash/flows/colab.py | tail -1)
  echo "    diff: ${zero:-(없음)} / 새 파일 $untracked / 흐름 colab.py: ${colab:-(0줄)}"
  report 2 "calc·shapes·고정 스키마·예시·골든·generated·core·config·.importlinter·pyproject·uv.lock·apps/web·services·tests/security 0줄" "$([ -z "$zero" ] && [ "$untracked" = 0 ] && echo 0 || echo 1)"
fi

if want 3; then
  (cd "$ROOT" && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  echo "    $last"
  report 3 "verify.sh --fast" "$([ "$last" = "VERIFY_FAST=PASS" ] && echo 0 || echo 1)"
fi

if want 4; then
  rm -f "$S4/netlog.txt"
  G1A_NET_LOG="$S4/netlog.txt" pyt pytest-greenwash -p esgapi.greenwash.tests.netcount esgapi/greenwash
  report 4 "pytest esgapi/greenwash" "$?"
fi

if want 5; then
  (cd "$API_PY" && G1A_OUT="$OUT/g1a" G1A_BASE="$BASE" scripts/section4-G1a.sh --step 9,10,11,13,15,17,18) > "$S4/g1a-section4.log" 2>&1
  e=$?
  grep -E '^\[|SECTION4_FAIL' "$S4/g1a-section4.log" | sed 's/^/    /'
  report 5 "G1a 자기검증(9,10,11,13,15,17,18) G1d 바닥에서" "$e"
fi

if want 6; then
  (cd "$API_PY" && G1D_OUT="$OUT" scripts/planted-breaks-G1d.sh) > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  report 6 "심은 파손" "$e"
fi

if want 7; then
  hits=0; keys=0; opens=0; reports=0
  rdir=$( [ -f "$PRIVATE" ] && sed -n 's/^G1A_REPORTS_DIR=//p' "$PRIVATE" | tr -d '"' | head -1 )
  : > "$S4/forbidden-hits.txt"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다: $WORDS"; hits=1
  else
    while IFS= read -r f; do
      [ -f "$ROOT/$f" ] || continue
      if grep -F -i -q -f "$WORDS" "$ROOT/$f"; then echo "$f" >> "$S4/forbidden-hits.txt"; hits=$((hits + 1)); fi
    done < <(changed_files)
  fi
  mhits=0
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  if [ -n "$msgs" ] && [ -f "$WORDS" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
  while IFS= read -r f; do
    [ -f "$ROOT/$f" ] || continue
    if grep -E -q 'sk-[A-Za-z0-9_-]{20,}' "$ROOT/$f"; then echo "    키 꼴: $f"; keys=$((keys + 1)); fi
    case "$f" in apps/api-py/scripts/section4-G1d.sh) continue ;; esac  # 찾는 글 자체가 든 이 스크립트
    if grep -E -q 'manufac-erp|spike/\.env' "$ROOT/$f"; then echo "    키 파일 경로: $f"; opens=$((opens + 1)); fi
    if grep -E -q 'prework/reports|_kor\.pdf|G1A_REPORTS_DIR' "$ROOT/$f"; then echo "    공개 보고서 자리: $f"; reports=$((reports + 1)); fi
    if [ -n "$rdir" ] && grep -F -q "$rdir" "$ROOT/$f"; then echo "    공개 보고서 자리(private.env 의 값): $f"; reports=$((reports + 1)); fi
  done < <(changed_files)
  if [ -n "$msgs" ] && printf '%s' "$msgs" | grep -E -q 'prework/reports|_kor\.pdf'; then reports=$((reports + 1)); echo "    공개 보고서 자리: 커밋 메시지"; fi
  if [ ! -f "$S4/netlog.txt" ]; then
    G1A_NET_LOG="$S4/netlog.txt" api pytest -q -p no:cacheprovider -p esgapi.greenwash.tests.netcount esgapi/greenwash > "$S4/pytest-net.log" 2>&1
  fi
  tests=$(wc -l < "$S4/netlog.txt" | tr -d ' ')
  blocked=$(awk '{s += $1} END {print s + 0}' "$S4/netlog.txt")
  echo "    낱말 $( [ -f "$WORDS" ] && grep -c . "$WORDS" || echo 0)개로 본 파일 $(changed_files | wc -l | tr -d ' '): 걸린 파일 $hits, 커밋 메시지($BASE..HEAD) $mhits"
  echo "    키 꼴 $keys, 키 파일 경로 $opens, 공개 보고서 자리 $reports(자리 값 $( [ -n "$rdir" ] && echo 읽음 || echo 못 읽음)), 소켓 문지기가 막은 시도 $blocked (테스트 $tests 개에서)"
  cat "$S4/forbidden-hits.txt"
  report 7 "기업명·키·공개 보고서 자리·소켓" "$([ "$hits$mhits$keys$opens$reports$blocked" = 000000 ] && [ -n "$rdir" ] && [ "$tests" -gt 0 ] && echo 0 || echo 1)"
fi

# (a) coordinates=None 이면 G1a 와 같다, 바이트로: 기준 커밋의 esgapi 를 git archive 로 꺼내(체크아웃 없이) 같은 도움 코드를
# 두 나무에서 돌리고 결과 JSON·대화 메시지 sha256 열·엑셀 칸 값을 견준다(가짜 좌표 BoxCoordinates 의 실행도 같이).
if want 8; then
  rm -rf "$S4/base-src" && mkdir -p "$S4/base-src"
  git -C "$ROOT" archive "$BASE" apps/api-py/esgapi | tar -x -C "$S4/base-src"
  cat > "$S4/a-driver.py" <<'PY'
"""(a) 의 도움 코드: argv[1] 의 나무(apps/api-py)의 esgapi 로 표본 실행 다섯을 돌려 argv[2] 에 JSON 으로 적는다."""
import hashlib, io, json, sys
sys.path.insert(0, sys.argv[1])
import esgapi
assert esgapi.__file__.startswith(sys.argv[1]), esgapi.__file__
from openpyxl import load_workbook
from esgapi.greenwash.calc.ports import MockEmbedding, ScriptedChat
from esgapi.greenwash.tests.flows import support as s

def one(flow_run, chat=None):
    files = {}
    for f in flow_run.output.files:  # 엑셀은 칸 값으로(zip 안의 시각이 실행마다 달라 바이트는 견주지 않는다)
        book = load_workbook(io.BytesIO(f.content), read_only=True)
        files[f.name] = {name: [[str(v) for v in r] for r in book[name].iter_rows(values_only=True)] for name in book.sheetnames}
    return {"result": s.result_of(flow_run), "messages": s.message_hashes(chat.sent) if chat else None, "files": files}

runs = {}
chat = ScriptedChat()
runs["A-none"] = one(s.run(s.inputs(), s.adapters(llm=chat, embedding=MockEmbedding())), chat)
chat = ScriptedChat()
runs["A-box"] = one(s.run(s.inputs(), s.adapters(llm=chat, embedding=MockEmbedding(), coordinates=s.BoxCoordinates())), chat)
runs["none"] = one(s.run(s.inputs(ceo="", company="", climate=""), s.adapters()))
runs["C-dry"] = one(s.run(s.inputs(dry_run=True), s.adapters(tokens=s.char_counter())))
chat = s.FailingChat([1])
runs["failing"] = one(s.run(s.inputs(), s.adapters(llm=chat)), chat)
text = json.dumps(runs, ensure_ascii=False, indent=1)
open(sys.argv[2], "w", encoding="utf-8").write(text)
print(sys.argv[2], hashlib.sha256(text.encode()).hexdigest(), {k: len(v["result"]["items"]) for k, v in runs.items()})
PY
  api python "$S4/a-driver.py" "$S4/base-src/apps/api-py" "$S4/a-base.json" > "$S4/a-base.log" 2>&1; e1=$?
  api python "$S4/a-driver.py" "$API_PY" "$S4/a-now.json" > "$S4/a-now.log" 2>&1; e2=$?
  sed 's/^/    /' "$S4/a-base.log" "$S4/a-now.log" | tail -4
  if [ "$e1$e2" = 00 ] && cmp -s "$S4/a-base.json" "$S4/a-now.json"; then same=0; echo "    바이트로 같다($(wc -c < "$S4/a-now.json" | tr -d ' ') 바이트)"; else same=1; echo "    다르다"; fi
  report 8 "(a) coordinates 없음 = 기준 커밋(결과 JSON·메시지 sha256·엑셀 칸 값)" "$same"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
