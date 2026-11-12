#!/usr/bin/env bash
# TR2 의 심은 파손(발주서 §3-5, 1~18 + 5a·5b = 19): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-TR2.sh --commit <1|2|3>
#   경계별 배치: ① 1·2·6·7·8·12·13·16·18 · ② + 3·4·5a·5b·9·10·14·15 · ③ + 11·17.
# 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 — checkout·restore·stash 0).
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다. 새 글이 「@rm」이면 파일을
#   지운다(되쓰기로 돌아온다).
# 옛 글·새 글에 「§」가 있으면 그것으로 나눈 짝마다 바꾼다(한 파손이 여러 자리를 지우는 것 — 5a).
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층
#   (scripts/test-business.sh — 이 워크트리의 compose postgres 가 떠 있어야 한다), 「sec:」로 시작하면 보안 층
#   (scripts/test-security.sh — 같은 postgres). 시험 칸이 「digest」면 run 지문
#   (tests/engines/colab_158/run_digest.py)을 BASE 트리(`git archive <기준>`)의 지문과 견줘 다르면 빨강.
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0(② 의 django_db 줄은 compose 의 DB 를 쓴다).
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1|2|3) ;; *) echo "--commit 1·2·3" >&2; exit 2 ;; esac

TR=esgapi/translation
E=$TR/engines/colab_158
T=$TR/tests
ET=$T/engines/colab_158
FT=$T/flows
E0=esgapi
DIGEST=esgapi.translation.tests.engines.colab_158.run_digest

backup="$(mktemp -d /private/tmp/tr2-planted.XXXXXX)"
case "$backup" in /private/tmp/tr2-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

# BASE 지문: 기준 트리를 풀어 이 지문 파일만 넣고 그쪽 엔진으로 돌린다(상수 박기 0).
base_ref="$(git merge-base main HEAD)"
mkdir -p "$backup/base"
git archive "$base_ref" -- . | tar -x -C "$backup/base"
cp "$ET/run_digest.py" "$backup/base/$ET/run_digest.py"
(cd "$backup/base" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH=. "$OLDPWD/.venv/bin/python" -m "$DIGEST") \
  > "$backup/digest-base.json" || { echo "★ BASE 지문을 못 냈다"; exit 2; }

digest_differs() {  # 0 = 이쪽 지문(열쇠 목록 밖)이 BASE 와 다름
  env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m "$DIGEST" > "$backup/digest-new.json" 2> "$backup/log" || return 0
  python3 -I - "$backup/digest-base.json" "$backup/digest-new.json" <<'PYEOF'
import json, sys
base, new = (json.load(open(p)) for p in sys.argv[1:3])
same = all(base[k] == new.get(k) for k in base if k != "keys")
sys.exit(1 if same else 0)
PYEOF
}

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈. 새 글이 「@rm」이면 파일을 지운다)
  if [ "$3" = "@rm" ]; then rm "$1"; return 0; fi
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

# 줄: <id>|<경계>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔) 또는 digest>
ROWS="1|1|$E/plan.py|, len(items) * prompts.MAX_TOKENS[\"cell\"]||$ET/test_plan_bounds.py
2|1|$E/plan.py|stand_in(max(page_tokens, prompts.MAX_TOKENS['autofix']))|stand_in(prompts.MAX_TOKENS['autofix'])|$ET/test_plan_bounds.py
6|1|$E/translate.py|raise KoreanRemaining(msg, remaining)|raise ValueError(msg)|$ET/test_remaining_and_shape.py
7|1|$E/pipeline.py|    source_map = last_wins_map(parse_pages(source_text))\\n|    source_map = {p.page_num: p.content for p in reversed(parse_pages(source_text))}\\n|$ET/test_retry.py
8|1|$E/pipeline.py|[translated_maps[label][k] for k in sorted(translated_maps[label])]|[translated_maps[label][k] for k in sorted(translated_maps[label]) if k in pages]|$ET/test_retry.py
12|1|$TR/tools/llm_bridge.py|        \"section\": 2,|        \"section\": 1,|$T/tools/test_llm_bridge_cache.py
13|1|$TR/tools/llm_bridge.py|        \"review\": 1,|        \"review\": 2,|$T/tools/test_llm_bridge_cache.py
16|1|$E/pipeline.py|    source_map = filter_range(\\n        _merge(parse_pages(source_text), \"원문\", result, None)|    source_map = filter_range(\\n        pages_to_map_merge(parse_pages(source_text))[0]|digest
18|1|$TR/prompts/section/2.md|-|@rm|$ET/test_prompts.py
3|2|$TR/flows/colab_158.py|    estimate = LlmBridge(adapters.llm, part=inputs.part, tenant=adapters.tenant).dry_run(planned)|    estimate = {\"totalEstimateUsd\": 0.0, \"perSite\": {}, \"warnings\": []}|$FT/test_colab_158.py
4|2|$E0/runs/calc/errors.py|    \"esgapi.core.llm.errors.LlmConfigError\": \"setup_error\",  # 영문번역 prepare 의 dry-run(TR2)\n||biz:$FT/test_runs_translation.py
5a|2|$TR/flows/colab_158.py|    if len(text) > MAX_SOURCE_CHARS:§    if len(chunks) > MAX_PAGE_CHUNKS:§    if calls > MAX_PLANNED_CALLS:|    if False:§    if False:§    if False:|$FT/test_colab_158.py
5b|2|$TR/flows/colab_158.py|    if total > inputs.max_usd:|    if False:|$FT/test_colab_158.py
9|2|$TR/flows/colab_158.py|    if source.source_sha256 != source_sha256 or source.labels != _labels(inputs):|    if source.labels != _labels(inputs):|$FT/test_colab_158.py
10|2|$TR/service/actions/retry_source.py|        run = run_selectors.find_run(company_id=company_id, run_id=run_id)|        run = next((r for c in range(1, 1000) if (r := run_selectors.find_run(company_id=c, run_id=run_id))), None)\n        company_id = company_id if run is None else run.company_id|biz:$FT/test_runs_translation.py
14|2|$TR/contracts/options_shapes.py|@with_config(FORBID)\nclass TranslationOptions(TypedDict):|@with_config({\"extra\": \"ignore\"})\nclass TranslationOptions(TypedDict):|$FT/test_binding_158.py
15|2|$TR/flows/colab_158.py|    if data.startswith(b\"PK\\x03\\x04\"):|    if data.startswith(b\"PK\\x03\\x04-never\"):|$FT/test_colab_158.py
11|3|$TR/service/actions/result.py|    if run is None or run.module != MODULE:|    if run is None:|biz:$FT/test_runs_translation.py
17|3|$TR/service/actions/result.py|    run = run_selectors.find_run(company_id=company_id, run_id=run_id)|    run = next((r for c in range(1, 1000) if (r := run_selectors.find_run(company_id=c, run_id=run_id))), None)\n    company_id = company_id if run is None else run.company_id|sec:tests/security/test_translation.py tests/security/test_tenant_paths.py"

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
  if [ "$tests" = digest ]; then
    if digest_differs; then red=1; code=differs; else red=0; code=same; fi
  elif [ "${tests#biz:}" != "$tests" ]; then
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -x -p no:cacheprovider "${tests#biz:}" > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  elif [ "${tests#sec:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록. -x 없이 — 어느 파일이 빨개졌는지 줄마다 본다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -x -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | head -6 | paste -sd' ' -)"
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, $tests) ${failed:-}"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=9 ;; 2) want=17 ;; 3) want=19 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
