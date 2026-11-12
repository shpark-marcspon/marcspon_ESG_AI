#!/usr/bin/env bash
# TRD2 의 심은 파손(발주서 §3 「심은 파손」 Q1~Q13 + ② 검증 꼴 Q14~Q18 — 파서 K1~K4 는 services/parser/scripts/planted.py 36~39): 파손 하나를
# 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-TRD2.sh --commit <2|3>
#   경계별 배치: ② Q1~Q7·Q10·Q13~Q18(14 — 클라이언트·어댑터. Q14~Q18 은 ② 검증 W6·W9·B1·B2 꼴) · ③ + Q8·Q9·Q11·Q12·Q19·Q20(20 — 흐름. Q19·Q20 은 ③ 검증 Y1·Y7 꼴).
# 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 — checkout·restore·stash 0).
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 옛 글·새 글에 「§」가 있으면 그것으로 나눈 짝마다 바꾼다. 글 안의 「\n」 두 글자는 줄바꿈이다.
# 시험 칸은 빈칸으로 나눈 「<층>:<경로>」 목록이다 — pure(uv pytest)·biz(scripts/test-business.sh — 이 워크트리의
#   compose postgres 가 떠 있어야 한다). 층마다 한 번 돌리고 **층마다 빨개야**(종료 1) 그 줄이 빨강이다.
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0(키가 있어도 env -u 로 뺀다).
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 2|3) ;; *) echo "--commit 2·3" >&2; exit 2 ;; esac

TR=esgapi/translation

backup="$(mktemp -d /private/tmp/trd2-planted.XXXXXX)"
case "$backup" in /private/tmp/trd2-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- .. | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>
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

run_layer() {  # run_layer <층> <경로…> → 종료 코드
  local layer="$1"; shift
  case "$layer" in
    pure) env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider "$@" ;;
    biz) env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider "$@" ;;
    *) echo "모르는 층: $layer"; return 2 ;;
  esac
}

# 줄: <id>|<경계>|<파일>|<옛 글>|<새 글>|<빨개질 시험>
PT=$TR/tools/pdf_tags.py
CP=esgapi/core/resources/parser.py
TT=$TR/tests/tools/test_pdf_tags.py
TC=esgapi/core/tests/test_parser_port.py
FL=$TR/flows/pdf_158.py
AP=$TR/apps.py
TF=$TR/tests/flows/test_pdf_158.py
TR_RUNS=$TR/tests/flows/test_runs_translation_pdf.py
RG=$TR/flows/registration.py
ROWS=""
read -r -d '' ROWS <<'ROWEOF' || true
Q1|2|CP|        if layout != 1:  # 기본 판|        if False:  # 기본 판|pure:TC
Q2|2|CP|        if layout != 1:  # 기본 판|        if True:  # 기본 판|pure:TC
Q3|2|PT|        members = [_member(b, str(b["text"])) for b in blocks]|        members = [_member(b, str(b["text"])) for b in blocks[: max(1, len(blocks) - 1)]]|pure:TT
Q4|2|PT|                if not any(cell.strip() for row in rows for cell in row):\n                    skipped["emptyTables"].append(table["id"])\n                    continue\n||pure:TT
Q5|2|PT|    if len(parts) == len(unit["members"]):|    if True:|pure:TT
Q6|2|PT|        if k not in shifted:\n            warnings.append({"code": "tag_missing", "page": page, "tag": unit["tag"]})|        if k not in shifted:\n            pass|pure:TT
Q7|2|PT|        if label not in position or label in seen:\n            unplaced.append({"page": page, "text": whole})|        if label not in position or label in seen:\n            pass|pure:TT
Q10|2|PT|"cells": cells, "rows": kept}|"cells": cells, "rows": list(range(len(kept)))}|pure:TT
Q13|2|PT|        if got and position[label] < got[-1][0]:|        if False:|pure:TT
Q14|2|PT|        if not mine or min(lost) < max(g[0] for g in mine):|        if True:|pure:TT
Q15|2|PT|            block["kind"] == "heading" or _overlap_ratio|            False or _overlap_ratio|pure:TT
Q16|2|PT| and _pipe_only(body):|:|pure:TT
Q17|2|PT|        return all(\n            _numbers(a)|        return True or all(\n            _numbers(a)|pure:TT
Q18|2|PT| and _numbers(body) == _numbers(source)||pure:TT
Q8|3|FL|    if not pdf.startswith(b"%PDF-"):|    if False:|pure:TF
Q9|3|RG|DEFAULTS: Final[dict[str, str]] = {"translation": colab.FLOW_ID}|DEFAULTS: Final[dict[str, str]] = {"translation": pdf.FLOW_ID}|pure:TF
Q11|3|AP|                ),\n            ),\n            max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS,|                ),\n            ),|biz:TR
Q12|3|FL|            raise RunRetryLater(|            raise PdfFlowError(|pure:TF biz:TR
Q19|3|FL|    if autofix["status"] == "done":|    if False:|pure:TF
Q20|3|FL|        warnings.extend({**w, "variant": variant["label"]} for w in placed.warnings)|        pass|pure:TF
ROWEOF

planted=0
caught=0
bad=0
while IFS='|' read -r id at file old new tests; do
  [ -n "$id" ] || continue
  [ "$at" -le "$COMMIT" ] || continue
  case "$file" in PT) file=$PT ;; CP) file=$CP ;; FL) file=$FL ;; AP) file=$AP ;; RG) file=$RG ;; esac
  tests="$(echo "$tests" | sed "s|:TT|:$TT|g; s|:TC|:$TC|g; s|:TF|:$TF|g; s|:TR|:$TR_RUNS|g")"
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  red=1
  codes=""
  failed=""
  for layer in pure biz; do
    paths="$(echo "$tests" | tr ' ' '\n' | sed -n "s|^$layer:||p" | paste -sd' ' -)"
    [ -n "$paths" ] || continue
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    run_layer "$layer" $paths > "$backup/log" 2>&1
    code=$?
    codes="$codes $layer=$code"
    [ "$code" = 1 ] || red=0
    failed="$failed $(grep -o -E '^FAILED [^ ]*|FAIL +[^ ]*' "$backup/log" 2>/dev/null | sed -E 's/^FAIL(ED)? +//' | head -4 | paste -sd' ' -)"
  done
  [ -n "$codes" ] || { red=0; echo "$id ★ 돌린 시험이 없다"; bad=$((bad + 1)); }
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT$codes)$failed"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 2) want=14 ;; 3) want=20 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
