#!/usr/bin/env bash
# TR1a 의 심은 파손(발주서 §3 P1~P15): 파손 하나를 심고, 그것을 물어야 할 시험(P13 은 lint-imports)이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-TR1a.sh --commit <1|2|3|4>
#   커밋별 배치(§3 끝 줄): ① P11 · ② + P3·P5·P6·P9·P13·P16(상대 import — 검증 ② B1) · ③ + P1·P4·P7·P8·P10·P12·P15 · ④ 전부(+ P2·P14).
# 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 — checkout·restore·stash 0).
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다(조용히 넘어가지 않는다).
# 빨강 = 그 시험 파일의 pytest 종료 1(실패. 수집 실패 2 는 「죽음」 — 빨강이 아니다). P13 의 빨강 = lint-imports 가
#   「다」(pure-modules)에서 esgapi.translation.engines → django 를 막았다고 말함.
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
E=$TR/engines/colab_158
T=$TR/tests

backup="$(mktemp -d /private/tmp/tr1a-planted.XXXXXX)"
case "$backup" in /private/tmp/tr1a-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈. 새 글이 「@json-drop:<경로>」면 JSON 의 그 칸을 지운다)
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import json, sys
path, old, new = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
if new.startswith("@json-drop:"):
    data = json.loads(text)
    *parents, last = new.removeprefix("@json-drop:").split("/")
    node = data
    for key in parents:
        node = node[key]
    if last not in node:
        print(f"  ★ 지울 칸이 없다: {new}")
        sys.exit(1)
    del node[last]
    open(path, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    sys.exit(0)
if text.count(old) != 1:
    print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
    sys.exit(1)
open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
PYEOF
}

# 줄: <id>|<커밋>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔) 또는 lint>
ET=$T/engines/colab_158
ROWS="P11|1|$T/data/flow-shapes/translation.result@1.schema.json|-|@json-drop:\$defs/Fragment/properties/error|$T/contracts/test_shapes.py
P3|2|$E/structured.py|{{3,}}\"|{3,}\"|$ET/test_structured.py
P5|2|$E/glossary.py|    items.sort(key=lambda x: len(x[0]), reverse=True)|    items.sort(key=lambda x: len(x[0]))|$ET/test_glossary.py
P6|2|$E/glossary.py|    expected_norm = normalize_space(expected_en).lower()|    expected_norm = normalize_space(expected_en)|$ET/test_glossary.py
P9|2|$E/review_rules.py|        if is_source_absent_only_false_positive(item):\\n            continue\\n||$ET/test_review_rules.py
P13|2|$E/structured.py|import re\\n|import re\\n\\nimport django  # noqa: F401\\n|lint
P16|2|$E/glossary.py|import re\\n|import re\\n\\nfrom ...contracts import shapes  # noqa: F401\\n|$ET/test_purity.py
P1|3|$E/translate.py|import re\\n|import re\\n\\nfrom esgapi.core.llm import client  # noqa: F401\\n|$ET/test_purity.py
P4|3|$E/gates.py|GENERIC_EDITORIAL_QA_MIN_SCORE = 96\\n|GENERIC_EDITORIAL_QA_MIN_SCORE = 95\\n|$ET/test_pipeline.py
P7|3|$E/gates.py|TABLE_BATCH_SIZE = 24\\n|TABLE_BATCH_SIZE = 25\\n|$ET/test_pipeline.py
P8|3|$E/review.py|gateway.complete(\"review\", \"review\",|gateway.complete(\"review\", \"translate\",|$ET/test_pipeline.py
P10|3|$E/pipeline.py|\"[TRANSLATION_ERROR page={page.page_num}]|\"|$ET/test_pipeline.py
P12|3|$TR/prompts/review/1.md|{{user}}\\n|{{user}}\\n\\n|$ET/test_prompts.py
P15|3|$E/glossary.py|    for ko, en in base:\\n        folded[ko] = en\\n    for ko, en in final:\\n        folded[ko] = en\\n|    for ko, en in final:\\n        folded[ko] = en\\n    for ko, en in base:\\n        folded.setdefault(ko, en)\\n|$ET/test_glossary.py
P2|4|$TR/contracts/wire.py|from typing import Any, Final\\n|from typing import Any, Final\\n\\nfrom esgapi.translation.engines.colab_158 import pipeline  # noqa: F401\\n|$T/test_axes.py
P14|4|$TR/tools/llm_bridge.py|            report = self.client.dry_run(|            report = self.client.call(|$T/tools/test_llm_bridge.py"

planted=0
caught=0
bad=0
while IFS='|' read -r id at file old new tests; do
  [ -n "$id" ] || continue
  [ "$at" -le "$COMMIT" ] || continue
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  if [ "$tests" = lint ]; then
    log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen lint-imports 2>&1)"
    code=$?
    if [ "$code" != 0 ] && printf '%s\n' "$log" | grep -q "^esgapi.translation.engines is not allowed to import django"; then red=1; else red=0; fi
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -x -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  fi
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, $tests)"
done <<EOF
$ROWS
EOF

# 커밋별로 심어야 하는 수(§3 끝 줄의 배치 + 검증 ② B1 의 P16 상대 import): ① 1 · ② 7 · ③ 14 · ④ 16
case "$COMMIT" in 1) want=1 ;; 2) want=7 ;; 3) want=14 ;; 4) want=16 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 커밋 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

# P13 의 대조(셈 밖): 「다」의 engines 줄을 지우면 같은 django import 를 lint-imports 가 더는 engines 에서 말하지 않는다
#   — 빨강이 그 목록 줄 때문이라는 물증.
if [ "$COMMIT" -ge 2 ]; then
  cp .importlinter "$backup/keep-lint"
  cp "$E/structured.py" "$backup/keep-eng"
  current=""
  plant .importlinter "    esgapi.translation.engines\\n" "" > /dev/null
  plant "$E/structured.py" "import re\\n" "import re\\n\\nimport django  # noqa: F401\\n" > /dev/null
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen lint-imports 2>&1)"
  cp "$backup/keep-lint" .importlinter
  cp "$backup/keep-eng" "$E/structured.py"
  if printf '%s\n' "$log" | grep -q "^esgapi.translation.engines is not allowed to import django"; then
    echo "P13-대조 ★ 줄을 지워도 engines 의 django 를 말한다"; bad=$((bad + 1))
  else
    echo "P13-대조 줄을 지우면 engines 의 django 를 말하지 않음(맞음)"
  fi
fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
