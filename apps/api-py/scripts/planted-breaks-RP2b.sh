#!/usr/bin/env bash
# RP2b 의 심은 파손(발주서 band-handoffs/RP2b-order.md §3 「심은 파손」): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RP2b.sh   (커밋 하나 — R1~R12)
# 틀은 planted-breaks-RP1.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
#   않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(이 워크트리의 compose postgres 가 떠 있어야 한다).
#   「lint+」로 시작하면 lint-imports 도 돌리고 둘 다 빨개야(lint 종료 ≠ 0) 빨강으로 센다.
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

[ $# -eq 0 ] || { echo "인자 없음: $0" >&2; exit 2; }

backup="$(mktemp -d /private/tmp/rp2b-planted.XXXXXX)"
case "$backup" in /private/tmp/rp2b-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈)
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
path, olds, news = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
pairs = list(zip(olds.split("§"), news.split("§"), strict=True))
for old, new in pairs:
    if text.count(old) != 1:
        print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
        sys.exit(1)
    text = text.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(text)
PYEOF
}

P=esgapi/drafting
PT=$P/tests
V=$P/engines/v2
VT=$PT/engines/v2
# 줄: <id>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
# R1 문장 번호 1부터 · R2 상한 셈에서 표지 뺌 · R3 준 블록 검사 지움(모르는 블록을 첫 블록으로) · R4 숫자 대조를 쪽 글로
# · R5 범위 밖 s 를 그대로 · R6 [B·[T 이스케이프 지움 · R7 범위를 code point 로 · R8 runs 없을 때 boxes [](null 대신)
# · R9 result.py 가 @1 도 찾음 · R10 basis 를 뺌 · R11 새 꼴 하나를 엶(extra allow — FORBID 를 지우기만 하면 바깥
#   DraftingResult 의 forbid 를 물려받아 관측되는 것이 없다: 1차 실측 초록) · R12 places 뷰를 출처마다 엶
ROWS="R1|$V/material.py|    units = dict(enumerate(pieces(escape_heads(block.text), spans)))§dict(enumerate(spans))|    units = dict(enumerate(pieces(escape_heads(block.text), spans), start=1))§dict(enumerate(spans, start=1))|$VT/test_material.py $PT/flows/test_draft_v2.py
R2|$V/material.py|            line = _line(whole, list(whole.units))\n            cost = len(LINE) + len(line)|            line = _line(whole, list(whole.units))\n            cost = len(LINE) + len(whole.text)|$VT/test_material.py
R3|$V/checks.py|            block = given.get(source[\"block\"])|            block = given.get(source[\"block\"]) or next(iter(given.values()))|$VT/test_checks.py
R4|$V/checks.py|numbers(block.text)|numbers(\" \".join(b.text for b in given.values() if b.page == block.page))|$VT/test_checks.py
R5|$V/checks.py|                index = None|                pass|$VT/test_checks.py
R6|$P/engines/v1/pages.py|    heads = MARKER_LOOKALIKE.sub(|    heads = (lambda _repl, text: text)(|$PT/engines/v1/test_pages.py $VT/test_material.py
R7|$V/sentences.py|    units = _utf16(text)|    units = list(range(len(text) + 1))|$VT/test_sentences.py
R8|$V/places.py|        \"sentence\": {\"index\": index, \"boxes\": boxes} if boxes else None,|        \"sentence\": {\"index\": index, \"boxes\": boxes} if index is not None else None,|$VT/test_places.py $PT/flows/test_draft_v2.py
R9|$P/service/actions/result.py|if r.schema_version == RESULT_SHAPE|if r.schema_version in (RESULT_SHAPE, \"drafting.bullets@1\")|biz:$PT/service/apis/test_drafting.py
R10|$P/flows/draft_v2.py|        \"basis\": _basis(extract),\n||$PT/flows/test_draft_v2.py
R11|$P/contracts/shapes.py|@with_config(FORBID)\nclass DraftingBasis(TypedDict):|@with_config(ConfigDict(extra=\"allow\", use_attribute_docstrings=True))\nclass DraftingBasis(TypedDict):|$PT/service/schemas/test_projects.py $PT/contracts/test_shapes.py
R12|$P/flows/draft_v2.py|            placed.append(places.source(blocks[block_id], source[\"index\"], view, source[\"documentId\"]))|            again = _view(inputs, adapters, carried, places=True)\n            placed.append(places.source(blocks[block_id], source[\"index\"], again, source[\"documentId\"]))|$PT/flows/test_draft_v2.py"

planted=0
caught=0
bad=0
while IFS='|' read -r id file old new tests; do
  [ -n "$id" ] || continue
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  lint_red=1
  lint_note=""
  if [ "${tests#lint+}" != "$tests" ]; then
    tests="${tests#lint+}"
    if uv run --frozen lint-imports > "$backup/lint" 2>&1; then lint_red=0; fi
    lint_note="lint-imports $([ "$lint_red" = 1 ] && echo 빨강 || echo ★초록), "
  fi
  if [ "${tests#biz:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1
    code=$?
  elif [ "${tests#sec:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
  fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' -)"
  nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
  # 빨강 = 종료 1 이고 FAILED 줄이 있음(ERROR 뿐인 종료 1 — DB 끊김 등 — 은 「죽음」이다)
  if [ "$code" = 1 ] && [ "${nfail:-0}" -gt 0 ] && [ "$lint_red" = 1 ]; then red=1; else red=0; fi
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, ${lint_note}$tests) 빨강 ${nfail:-0}개: ${failed:-}"
done <<EOF
$ROWS
EOF

want=12
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
