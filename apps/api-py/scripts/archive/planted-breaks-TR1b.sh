#!/usr/bin/env bash
# TR1b 의 심은 파손(발주서 §3 P1~P17 + 감독 처분 ★d 의 P18 + 검증 ① B1 의 P19): 파손 하나를 심고, 그것을 물어야 할 시험(P10 은
#   lint-imports)이 빨개지는지 본다. planted-breaks-TR1a.sh 판별 복사(import 하지 않는다).
#   사용: apps/api-py/scripts/planted-breaks-TR1b.sh --commit <1|2|3|4>
#   커밋별 배치: ① P1~P6·P16~P19(10) · ② + P7~P10(14) · ③ + P11~P15(19) · ④ + P20~P22(22 — 병합 전 가지 리뷰 B1·M2).
# 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 — checkout·restore·stash 0).
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다(조용히 넘어가지 않는다).
# 빨강 = 그 시험의 pytest 종료 1(실패. 수집 실패 2 는 「죽음」 — 빨강이 아니다). 시간 상한 칸이 있는 줄(P16·P18 — 검사가
#   없으면 python-docx 가 칸·사슬을 끝까지 되풀이한다)은 `perl -e 'alarm …; exec …'` 로 감싸고 시간 넘김(종료 142)도
#   빨강으로 센다(개정 2 M2′). 그 줄은 uv 를 거치지 않고 .venv 의 python 을 바로 부른다(alarm 이 pytest 를 죽이게).
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크·컨테이너 0.
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1|2|3|4) ;; *) echo "--commit 1·2·3·4" >&2; exit 2 ;; esac

TR=esgapi/translation
T=$TR/tests
RD=$TR/tools/docx_reader.py
TRD=$T/tools/test_docx_reader.py
BI=$TR/outputs/docx_bilingual.py
TBI=$T/outputs/test_docx_bilingual.py
QA=$TR/outputs/docx_qa.py
TQA=$T/outputs/test_docx_qa.py
FI=$TR/outputs/files.py
FA=$TR/outputs/failures.py

backup="$(mktemp -d /private/tmp/tr1b-planted.XXXXXX)"
case "$backup" in /private/tmp/tr1b-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
path, old, new = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
    sys.exit(1)
open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
PYEOF
}

# 줄: <id>|<커밋>|<파일>|<옛 글>|<새 글>|<빨개질 시험(pytest 인자, 빈칸으로 나눔) 또는 lint>|<시간 상한 초, 0 = 없음>
ROWS="P1|1|$RD|            data = stream.read(sizes[name] + 1)|            data = stream.read()|$TRD -k lying_about_its_size|0
P2|1|$RD|    parser.StartDoctypeDeclHandler = on_doctype\\n||$TRD -k doctype|0
P3|1|$RD|    return DocxText(text=|    lines = [__import__(\"esgapi.translation.engines.colab_158.structured\", fromlist=[\"_\"]).normalize_structured_tags(chr(10).join(lines))]\\n    return DocxText(text=|$TRD -k normalizes_the_read_text_exactly_once|0
P4|1|$RD|            if not lines or lines[-1].strip() != \"[MARKDOWN_TABLE]\":|            if True:|$TRD -k cell_7_writes|0
P5|1|$RD|    *_ZIP_ERRORS,\\n    RecursionError,\\n|    *(error for error in _ZIP_ERRORS if error is not RuntimeError),\\n|$TRD -k recurses_too_deep|0
P6|1|$TR/tools/compare_dump.py|import argparse\\n|import argparse\\n\\nimport docx  # noqa: F401\\n|$T/test_docx_imports.py|0
P16|1|$RD|                width = offset + after\\n|                width = 0\\n|$TRD -k grid_span_of_a_million|60
P17|1|$RD|        if lowered.endswith((\".xml\", \".rels\")) or any(c.endswith(\"xml\") for c in content_types):|        if lowered.endswith((\".xml\", \".rels\")):|$TRD -k named_bin|0
P18|1|$RD|                        steps += depth\\n|                        steps += 0\\n|$TRD -k chains_over_the_step_limit|60
P19|1|$RD|        if depth[0] != 2 or namespace != _CT_NS or local not in required:|        if namespace != _CT_NS or local not in required:|$TRD -k hidden_deeper_override|0
P7|2|$BI|        if len(s) <= 60 and not s.endswith(|        if len(s) <= 61 and not s.endswith(|$TBI -k merge_wrapped_lines|0
P8|2|$BI|                if page_num == current_page_num:\n                    continue\n||$TBI -k reads_back_as_cell_54|0
P9|2|$BI|        set_cell_shading(header_cells[i], \"DDEBF7\")|        set_cell_shading(header_cells[i], \"DDEBF8\")|$TBI -k markdown_table_becomes|0
P10|2|$BI|import io\n|import io\n\nimport django  # noqa: F401\n|lint|0
P11|3|$QA|        if len(span) < 4:|        if len(span) < 3:|$TQA -k highlight|0
P12|3|$QA|            if not overlaps:\n                intervals.append((idx, end))\n|            intervals.append((idx, end))\n|$TQA -k highlight|0
P13|3|$QA|    p = cell.paragraphs[0]\n    run = p.add_run(writable(str(text or \"\")))|    p = cell.paragraphs[0]\n    run = p.add_run(writable(str(text)))|$TQA -k w9|0
P14|3|$FI|REVIEWED: Final = frozenset({\"reviewed\", \"parse_failed\"})|REVIEWED: Final = frozenset({\"reviewed\", \"parse_failed\", \"call_failed\"})|$T/outputs/test_files.py -k stopped_review|0
P15|3|$FI|from esgapi.translation.outputs.failures import WordFailed\n|from esgapi.translation.outputs.failures import WordFailed\nfrom esgapi.translation.tools import docx_reader  # noqa: F401\n|$T/test_axes.py|0
P20|4|$RD|    return defaults.get(PackURI(partname).ext)\n|    base = partname.rsplit(\"/\", 1)[-1]\n    return defaults.get(base.rsplit(\".\", 1)[-1] if \".\" in base else \"\")\n|$TRD -k dotfile_main_part|0
P21|4|$FA|\x20-\ud7ff|\x01-\ud7ff|$T/outputs/test_failures.py -k exactly_what_lxml_refuses|0
P22|4|$BI|        run = p.add_run(writable(part))  # (TR1b) W10 을 넘기기 전에 — failures.writable\n        apply_run_style(run, size=size, color=color, bold=bold, italic=italic)|        run = p.add_run(part)\n        apply_run_style(run, size=size, color=color, bold=bold, italic=italic)|$TBI -k w10_a_control|0"

planted=0
caught=0
bad=0
while IFS='|' read -r id at file old new tests limit; do
  [ -n "$id" ] || continue
  [ "$at" -le "$COMMIT" ] || continue
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  start=$(date +%s)
  if [ "$tests" = lint ]; then
    log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen lint-imports 2>&1)"
    code=$?
    if [ "$code" != 0 ] && printf '%s\n' "$log" | grep -q "^esgapi.translation.outputs is not allowed to import django"; then red=1; else red=0; fi
  elif [ "$limit" != 0 ]; then
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 pytest 인자다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY perl -e 'alarm shift; exec @ARGV' "$limit" \
      .venv/bin/python -m pytest -q -x -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ] || [ "$code" = 142 ]; then red=1; else red=0; fi
  else
    # shellcheck disable=SC2086
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -x -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  fi
  took=$(( $(date +%s) - start ))
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  if [ "$code" = 5 ]; then echo "$id ★ 고른 시험이 하나도 없다(-k 가 빗나감)"; fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, ${took}초, $tests)"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=10 ;; 2) want=14 ;; 3) want=19 ;; 4) want=22 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 커밋 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

# P10 의 대조(셈 밖 — planted-breaks-TR1a.sh 의 P13-대조 판별 복사): 「다」의 outputs 줄을 지우면 같은 django import 를
#   lint-imports 가 더는 outputs 에서 말하지 않는다 — 빨강이 그 목록 줄 때문이라는 물증.
if [ "$COMMIT" -ge 2 ]; then
  cp .importlinter "$backup/keep-lint"
  cp "$BI" "$backup/keep-bi"
  current=""
  plant .importlinter "    esgapi.translation.outputs\\n" "" > /dev/null
  plant "$BI" "import io\\n" "import io\\n\\nimport django  # noqa: F401\\n" > /dev/null
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen lint-imports 2>&1)"
  cp "$backup/keep-lint" .importlinter
  cp "$backup/keep-bi" "$BI"
  if printf '%s\n' "$log" | grep -q "^esgapi.translation.outputs is not allowed to import django"; then
    echo "P10-대조 ★ 줄을 지워도 outputs 의 django 를 말한다"; bad=$((bad + 1))
  else
    echo "P10-대조 줄을 지우면 outputs 의 django 를 말하지 않음(맞음)"
  fi
fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
