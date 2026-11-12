#!/usr/bin/env bash
# 밴드 GM1 의 §4 자기검증(발주서 band-handoffs/GM1-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-GM1.sh                 전부
#   apps/api-py/scripts/section4-GM1.sh --step 3,4,5    일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   GM1_BASE   기준 커밋(기본: 기동 노트의 52ab882…)
#   GM1_OUT    산출물 자리(기본: 워크트리 곁의 GM1.out). 산출물은 $GM1_OUT/section4/ 아래
#   GM1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(있으면 9 가 $BASE..HEAD 의 메시지와 함께 본다)
#   GM1_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${GM1_BASE:-52ab8823a97916cd00907564ff592e2b429d747a}"
OUT="${GM1_OUT:-$SIDE/GM1.out}"
WORDS="${GM1_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
S4="$OUT/section4"
D="apps/api-py/esgapi/core/llm/data"
MODELS="$D/models.json"
README="$D/README.md"
TEST="apps/api-py/esgapi/core/tests/test_llm_cost.py"
NEW_TEST="test_gpt41_mini_prices_match_the_official_table_and_has_its_own_route"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$S4"
# 키를 환경에 두고 돌리지 않는다(발주서 §2)
api() { (cd "$API_PY" && env -u OPENAI_API_KEY uv run --frozen "$@"); }

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

changed_files() {
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1 의 닫힌 목록. __init__.py·config.py 는 기동 노트의 백엔드 허락(2026-10-16, marcspon-36)이 있어 docstring 만 든다.
ALLOWED='^(apps/api-py/esgapi/core/llm/data/(models\.json|README\.md)|apps/api-py/esgapi/core/tests/test_llm_cost\.py|apps/api-py/esgapi/core/llm/(__init__|config)\.py|apps/api-py/scripts/(section4|planted-breaks)-GM1\.sh)$'

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse HEAD), 산출물 $S4"

if want 1; then
  changed_files > "$S4/changed-files.txt"
  outside=$(grep -Ev "$ALLOWED" "$S4/changed-files.txt")
  n=$(grep -c . "$S4/changed-files.txt")
  echo "    바뀐 파일 $n, 허용 밖 $( [ -n "$outside" ] && echo "$outside" | grep -c . || echo 0)"
  [ -n "$outside" ] && echo "$outside" | sed 's/^/    밖: /'
  # __init__.py·config.py 는 docstring 뺀 AST 가 기준과 같아야 한다(동작 0줄)
  bad=0
  for f in apps/api-py/esgapi/core/llm/__init__.py apps/api-py/esgapi/core/llm/config.py; do
    git -C "$ROOT" show "$BASE:$f" > "$S4/ast-base.py"
    r=$(api python - "$S4/ast-base.py" "$ROOT/$f" <<'PY'
import ast
import sys


def strip(path: str) -> str:
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:]
    return ast.dump(tree, include_attributes=False)


print("same" if strip(sys.argv[1]) == strip(sys.argv[2]) else "DIFF")
PY
)
    ns=$(git -C "$ROOT" diff --numstat "$BASE" -- "$f" | awk '{print $1 "+" $2 "-"}')
    echo "    ${f##*/}: ${ns:-0+0-}, docstring 뺀 AST $r"
    [ "$r" = "same" ] || bad=$((bad + 1))
  done
  rm -f "$S4/ast-base.py"
  report 1 "허용 경로·코드 0줄" "$([ -z "$outside" ] && [ "$bad" = 0 ] && echo 0 || echo 1)"
fi

if want 2; then
  api pytest -q -p no:cacheprovider esgapi/core/tests/test_llm_cost.py esgapi/core/tests/llm > "$S4/pytest.log" 2>&1
  e=$?
  api pytest -q --collect-only -p no:cacheprovider "${TEST#apps/api-py/}" 2>&1 | grep '::' > "$S4/nodeids.txt"
  has=$(grep -c "::$NEW_TEST\$" "$S4/nodeids.txt")
  tail -1 "$S4/pytest.log" | sed 's/^/    /'
  echo "    새 시험 $NEW_TEST: $has"
  report 2 "pytest test_llm_cost·core/tests/llm" "$([ "$e" = 0 ] && [ "$has" = 1 ] && echo 0 || echo 1)"
fi

if want 3; then
  r=$(api python -c '
from esgapi.core.llm.config import default_config_sources, load_config
c = load_config(default_config_sources(synthetic=False))
m = c.models["gpt-4.1-mini"]
print(m.entry.api_model_id, c.routes["light-openai-41"], m.entry.source_refs)
' 2>&1)
  e=$?
  echo "$r" | tail -3 | sed 's/^/    /'
  report 3 "load_config 가 새 모델·경로를 받음" "$e"
fi

if want 4; then
  git -C "$ROOT" show "$BASE:$MODELS" > "$S4/models-base.json"
  r=$(python3 - "$S4/models-base.json" "$ROOT/$MODELS" <<'PY'
import json
import sys

base = json.load(open(sys.argv[1], encoding="utf-8"))
now = json.load(open(sys.argv[2], encoding="utf-8"))
missing = [k for k, part in (("openai_model_gpt41mini", "sources"), ("gpt-4.1-mini", "models"), ("light-openai-41", "routes"))
           if k not in now.get(part, {})]
for key, part in (("openai_model_gpt41mini", "sources"), ("gpt-4.1-mini", "models"), ("light-openai-41", "routes")):
    now.get(part, {}).pop(key, None)
# 키 순서까지 견준다(json.dumps 는 순서를 지킨다)
same = json.dumps(base, ensure_ascii=False) == json.dumps(now, ensure_ascii=False)
print(("same" if same else "DIFF") + (f" (새 키 없음: {missing})" if missing else ""))
PY
)
  echo "    기준 ↔ 지금에서 새 셋을 뺀 것: $r"
  report 4 "기존 값 그대로" "$([ "$r" = "same" ] && echo 0 || echo 1)"
fi

if want 5; then
  ns=$(git -C "$ROOT" diff --numstat "$BASE" -- "$MODELS")
  echo "    numstat: ${ns:-(바뀜 없음)}"
  r=$(git -C "$ROOT" diff -U0 "$BASE" -- "$MODELS" | python3 -c '
import sys
minus, plus = [], set()
for line in sys.stdin.read().splitlines():
    if line.startswith(("---", "+++")):
        continue
    if line.startswith("-"):
        minus.append(line[1:])
    elif line.startswith("+"):
        plus.add(line[1:])
bad = [m for m in minus if m + "," not in plus]
print(f"{len(minus)} {len(bad)}")
for b in bad:
    print("    쉼표만 단 줄이 아니다: " + b, file=sys.stderr)
')
  dels="${r%% *}"; notcomma="${r##* }"
  echo "    지운 줄 $dels(셋까지), 그중 쉼표만 단 것이 아닌 줄 $notcomma"
  report 5 "models.json 삭제 0(쉼표 줄 예외)" "$([ "$dels" -le 3 ] && [ "$notcomma" = 0 ] && echo 0 || echo 1)"
fi

if want 6; then
  r=$(python3 - "$ROOT/$MODELS" <<'PY'
import json
import sys

body = json.load(open(sys.argv[1], encoding="utf-8"))
m = body["models"]["gpt-4.1-mini"]
url = body["sources"]["openai_model_gpt41mini"]
problems = []
if not url.startswith("https://"):
    problems.append(f"출처 URL 이 https 가 아니다: {url}")
for ref in m["sourceRefs"]:
    if not body["sources"].get(ref, "").startswith("https://"):
        problems.append(f"sourceRefs {ref} 의 URL")
texts = list(m["notes"]) + [m["lifecycle"]["note"]]
for t in texts:
    if "2026-10-16 확인" not in t:
        problems.append("확인일 없음: " + t[:40])
    if not any(ref in t for ref in m["sourceRefs"]):
        problems.append("출처 키 없음: " + t[:40])
# 쓴 출처 키는 notes 어딘가에 나온다
for ref in m["sourceRefs"]:
    if not any(ref in t for t in texts):
        problems.append(f"notes 에 안 나오는 sourceRef {ref}")
# 수치마다 notes 에 그 값이 인용돼 있다
p = m["pricing"]
quotes = {"input": "$0.40", "cacheRead": "$0.10", "output": "$1.60", "cacheWrite": "No additional cache-write charge",
          "contextWindowTokens": "1,047,576", "maxOutputTokens": "32,768", "minCacheTokens": "Varies by request settings",
          "pdf.maxRequestMb": "50 MB", "structuredOutput": "Structured outputs Supported"}
joined = "\n".join(texts)
for k, q in quotes.items():
    if q not in joined:
        problems.append(f"{k} 의 인용 「{q}」 없음")
print(f"notes {len(m['notes'])} · lifecycle 1 · sourceRefs {len(m['sourceRefs'])} · 문제 {len(problems)}")
for x in problems:
    print("    " + x)
PY
)
  echo "$r" | sed 's/^/    /'
  report 6 "새 항목 수치마다 출처 키·확인일" "$(echo "$r" | head -1 | grep -q '문제 0$' && echo 0 || echo 1)"
fi

if want 7; then
  f="$ROOT/$README"
  head_ok=$(grep -cxF '`models.json` 은 이 저장소가 정본이다(2026-10-16 `sid:MARC-ENT-249`, 밴드 GM1). 수치는 공식 문서를 열어 확인한 것만, 출처 키와 확인일과 함께 고친다. `models.synthetic.json` 은 여전히 esg-lab 의 사본이고, `models.embedding.synthetic.json` 은 이 저장소의 가상 파일이다.' "$f")
  title=$(head -1 "$f")
  title_ok=$([ "$title" = "# 모델 설정 자료" ] && echo 1 || echo 0)
  row_ok=$(grep -cF '| `models.json` | 없음(정본. 2026-10-16 까지는 `esg-lab/data/llm/models.json` 의 사본) |' "$f")
  n27=$(grep -cF '`sources`(27개)' "$f")
  tail_ok=$(grep -cxF -e '- 단가가 바뀌면 공식 문서를 열어 확인하고, 이 파일의 그 항목 notes 에 확인일과 출처를 같이 적는다.' "$f")
  # 「사본」은 models.synthetic.json 줄과 「사본을 뜬 날」 줄에만(정한 것 4 가 정한 models.json 줄의 「…까지는 … 사본」은 역사라 든다)
  stray=$(grep -n '사본' "$f" | grep -v 'models\.synthetic\.json' | grep -v '사본을 뜬 날' | grep -vF '2026-10-16 까지는')
  echo "    제목 「${title}」 · 머리 ${head_ok} · 표 원본 칸 ${row_ok} · sources 27 ${n27} · 끝 줄 ${tail_ok}"
  [ -n "$stray" ] && echo "$stray" | sed 's/^/    남은 사본: /'
  report 7 "README 정본 문구" "$([ "$head_ok$title_ok$row_ok$n27$tail_ok" = 11111 ] && [ -z "$stray" ] && echo 0 || echo 1)"
fi

if want 8; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" env -u OPENAI_API_KEY scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" env -u OPENAI_API_KEY scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  gates=$(grep '^GATES=' "$S4/check-gates.log" | tail -1)
  echo "    $last / $gates (종료 $e)"
  report 8 "verify.sh --fast · check-gates" "$([ "$last" = "VERIFY_FAST=PASS" ] && [ "$e" = 0 ] && echo 0 || echo 1)"
fi

# 이 밴드가 들인 글: 추적 파일은 기준 대비 더한 줄, 새 파일은 전부. 줄마다 「경로<TAB>글」.
added_lines() {
  git -C "$ROOT" diff -U0 "$BASE" | awk '
    /^\+\+\+ / { f = substr($0, 7); next }
    /^\+/ { print f "\t" substr($0, 2) }'
  git -C "$ROOT" ls-files -o --exclude-standard --full-name | while IFS= read -r f; do
    [ -f "$ROOT/$f" ] && awk -v f="$f" '{ print f "\t" $0 }' "$ROOT/$f"
  done
}

if want 9; then
  added_lines > "$S4/added-lines.txt"
  nl=$(grep -c . "$S4/added-lines.txt")
  hits=0
  : > "$S4/forbidden-hits.txt"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다: $WORDS"; hits=1
  else
    hits=$(cut -f2- "$S4/added-lines.txt" | grep -F -i -c -f "$WORDS")
    [ "$hits" = 0 ] || awk -F'\t' '{print $1}' "$S4/added-lines.txt" | sort -u | while IFS= read -r f; do
      grep -F "$f	" "$S4/added-lines.txt" | cut -f2- | grep -F -i -q -f "$WORDS" && echo "$f" >> "$S4/forbidden-hits.txt"
    done
  fi
  mhits=0
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  draft="${GM1_COMMIT_MSG_FILE:-}"
  if [ -n "$draft" ]; then
    if [ -f "$draft" ]; then msgs="$msgs
$(cat "$draft")"; else echo "    커밋 메시지 초안이 없다: $draft"; mhits=1; fi
  fi
  if [ -n "$msgs" ] && [ -f "$WORDS" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
  keys=$( { cut -f2- "$S4/added-lines.txt"; printf '%s\n' "$msgs"; } | grep -E -c 'sk-[A-Za-z0-9_-]{20,}')
  # 찾는 글 자체가 든 이 밴드의 두 스크립트는 키 파일 경로 검사에서 뺀다
  opens=$( { grep -vE '^apps/api-py/scripts/(section4|planted-breaks)-GM1\.sh	' "$S4/added-lines.txt" | cut -f2-; printf '%s\n' "$msgs"; } \
    | grep -E -c 'manufac-erp|spike/\.env|marcspon-openai\.env')
  nmsg=$(git -C "$ROOT" rev-list --count "$BASE..HEAD")
  echo "    낱말 $( [ -f "$WORDS" ] && grep -c . "$WORDS" || echo 0)개로 본 더한 줄 $nl: 걸린 줄 $hits, 커밋 메시지($nmsg 개, $BASE..HEAD${draft:+ + 초안 ${draft##*/}}) $mhits"
  echo "    키 꼴 $keys, 키 파일 경로 $opens"
  sed 's/^/    걸린 파일: /' "$S4/forbidden-hits.txt"
  report 9 "기업명·키" "$([ "$hits$mhits$keys$opens" = 0000 ] && echo 0 || echo 1)"
fi

if want 10; then
  (cd "$API_PY" && GM1_OUT="$OUT" GM1_BASE="$BASE" scripts/planted-breaks-GM1.sh) > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  report 10 "GM1 심은 파손" "$([ "$e" = 0 ] && grep -q '^PLANTED=3/3$' "$S4/planted.log" && grep -q '^FINGERPRINT=same' "$S4/planted.log" && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
