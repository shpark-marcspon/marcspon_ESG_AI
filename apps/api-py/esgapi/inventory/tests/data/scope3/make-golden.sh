#!/usr/bin/env bash
# G1 골든: esg-lab 의 Scope 3 CLI(`ts/scope3/src/cli.ts eval --provider mock`)를 가상 표·가상 예제로 설정 넷으로 돌려
# rows.json 넷과, 설정 a 에서 모의 공급사가 받은 사용자 글자를 golden/ 아래에 만든다.
# AI 공급사 호출 0(모의 응답기). esg-lab 의 파일은 고치지 않는다(--out·--log 는 임시 폴더로만 준다).
#
#   make-golden.sh            골든을 다시 만든다(golden/ 의 파일을 덮어쓴다)
#   make-golden.sh --check    임시 폴더에 다시 만들어 golden/ 과 diff 0 인지만 본다(0 이면 같다)
#
# 환경: ESG_LAB(esg-lab 저장소의 경로. 꼭 준다), Node 22(PATH 앞에 ~/.nvm/versions/node/v22.23.1/bin).
# 아무것도 지우지 않는다: CLI 의 산출물은 mktemp 의 임시 폴더에 두고(운영체제가 치운다) 골든이 되는 파일만 베껴 온다.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ESG_LAB="${ESG_LAB:?ESG_LAB=<esg-lab 저장소의 경로> 를 준다}"
NODE_BIN="$HOME/.nvm/versions/node/v22.23.1/bin"
[ -d "$NODE_BIN" ] && PATH="$NODE_BIN:$PATH"

[ -f "$ESG_LAB/ts/scope3/src/cli.ts" ] || { echo "esg-lab 의 Scope 3 CLI 가 없다: $ESG_LAB" >&2; exit 2; }

WORK="$(mktemp -d)"
if [ "${1:-}" = "--check" ]; then
  DEST="$WORK/golden"
else
  DEST="$HERE/golden"
fi

run() {  # run <이름> <cli 인자...>
  local name="$1"; shift
  mkdir -p "$WORK/raw/$name" "$DEST/$name"
  (cd "$ESG_LAB/ts" && pnpm -F scope3 exec tsx src/cli.ts eval "$HERE/examples" --provider mock \
      --factors "$HERE/factors.synthetic.jsonl" --out "$WORK/raw/$name" --log "$WORK/raw/$name/calls.jsonl" \
      --store-bodies "$@" >/dev/null)
  # 골든은 rows.json 뿐이다. report.json 은 평가 지표라(옮기지 않은 eval/ 의 것) 베끼지 않는다.
  cp "$WORK/raw/$name/rows.json" "$DEST/$name/rows.json"
}

run a-default
run b-no-bigrams --no-bigrams
run c-lexical-v1 --shortlist-method lexical-v1
run d-exclude-disputed --exclude-license disputed --shortlist 5 --adjustments "$HERE/adjustments.synthetic.json"

# 모의 공급사가 받은 사용자 글자(ITEM_JSON·CANDIDATES_JSON 줄)를 설정 a 의 호출 기록에서 뽑아 둔다(★ 라).
# 호출 기록의 줄마다 시도(attempt)의 요청 본문이 있다. 호출 id·시각 같은 실행마다 달라지는 칸은 싣지 않는다.
jq -c '[.. | objects | select(has("user") and has("apiModelId")) | [.user[] | select(.type == "text") | .text] | join("\n")] | .[0] // empty' \
  "$WORK/raw/a-default/calls.jsonl" > "$DEST/a-default/user-texts.jsonl"

# ★ 나: 유니코드 표본(BMP 밖 글자, İ, 전각, ㎥, 결합 문자)에 esg-lab 의 함수가 내는 글자.
(cd "$ESG_LAB/ts" && pnpm -F scope3 exec tsx "$HERE/unicode-samples.mts" "$ESG_LAB" "$HERE/unicode-samples.input.json") \
  > "$DEST/unicode-samples.json"

if [ "${1:-}" = "--check" ]; then
  diff -r "$DEST" "$HERE/golden"
  echo "G1 골든: 다시 만든 것과 같다 (설정 넷)"
fi
