#!/usr/bin/env bash
# TRS3 의 심은 파손(발주서 §3 「심은 파손」 P1~P11 — planted-breaks-TRD2.sh 꼴): 파손 하나를 심고, 그것을 물어야 할 시험이
# 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-TRS3.sh --commit 3
#   경계 ③ 에서 한 번에 열하나(① 의 P1·P2 · ② 의 P3~P8·P11 · ③ 의 P9·P10 — 셋째 커밋 뒤의 파일에 심는다).
# 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 — checkout·restore·stash 0).
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 옛 글·새 글에 「§」가 있으면 그것으로 나눈 짝마다 바꾼다. 글 안의 「\n」 두 글자는 줄바꿈이다.
# 시험 칸은 빈칸으로 나눈 「<층>:<경로>」 목록이다 — pure(uv pytest)·biz(scripts/test-business.sh)·sec
#   (scripts/test-security.sh — 직렬. biz·sec 는 이 워크트리의 compose postgres 가 떠 있어야 한다). 층마다 한 번 돌리고
#   **층마다 빨개야**(종료 1) 그 줄이 빨강이다.
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
case "$COMMIT" in 3) ;; *) echo "--commit 3" >&2; exit 2 ;; esac

TR=esgapi/translation

backup="$(mktemp -d /private/tmp/trs3-planted.XXXXXX)"
case "$backup" in /private/tmp/trs3-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
    sec) env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider "$@" ;;
    *) echo "모르는 층: $layer"; return 2 ;;
  esac
}

# 줄: <id>|<경계>|<파일>|<옛 글>|<새 글>|<빨개질 시험>
BA=$TR/service/actions/batches.py
LA=$TR/service/actions/layout.py
LS=$TR/contracts/layout_shapes.py
AP=$TR/apps.py
PM=esgapi/core/permissions.py
GO=generated/openapi.json
TBI=$TR/tests/service/actions/test_batches_input_kind.py
TL=$TR/tests/service/actions/test_layout.py
TLS=$TR/tests/contracts/test_layout_shapes.py
TRP=$TR/tests/flows/test_runs_translation_pdf.py
TP=esgapi/core/tests/test_permissions.py
TW=esgapi/core/tests/test_permissions_wiring.py
TAC=esgapi/config/tests/test_api_contract.py
SD4=tests/security/test_translation.py
ROWS=""
read -r -d '' ROWS <<'ROWEOF' || true
P1|3|BA|"inputKind": "pdf" if lines[g.newest.id]["flowId"].startswith(PDF_FLOW_PREFIX) else "word",|"inputKind": "word",|biz:TBI
P2|3|BA|        "flowId": run.flow_id,|        "flowId": "translation.colab@158",|biz:TBI
P3|3|LA|r.schema_version == LAYOUT_SHAPE), None)|r.schema_version == "translation.result@1"), None)|biz:TL
P4|3|LA|        return NotFound()\n    return cast(|        return None  # type: ignore[return-value]\n    return cast(|biz:TL
P5|3|LA|        return RunNotDone(run.status)|        return NotFound()|biz:TL
P6|3|LA|    run = run_selectors.find_run(company_id=company_id, run_id=run_id)|    from esgapi.runs.models import RunRow\n\n    company_id = RunRow.unscoped.get(pk=run_id).company_id\n    run = run_selectors.find_run(company_id=company_id, run_id=run_id)|sec:SD4
P7|3|PM|    "translation_layout_get": COMPANY,\n||pure:TP biz:TW
P8|3|GO|"/translation/runs/{run_id}/layout": {|"/translation/runs/{run_id}/layout-old": {|pure:TAC
P9|3|AP|store=RunRetrySource(flow_id=pdf.FLOW_ID, adapter=pdf.pdf_tags.ADAPTER_VERSION),|store=RunRetrySource(),|biz:TRP
P10|3|AP|                store=RunRetrySource(),|                store=RunRetrySource(flow_id="translation.pdf@158", adapter="pdf_tags@1"),|biz:TRP
P11|3|LS|class TranslationLayoutSkipped(TypedDict):§    skipped: TranslationLayoutSkipped|class Skipped(TypedDict):§    skipped: Skipped|pure:TLS biz:TL
ROWEOF

planted=0
caught=0
bad=0
while IFS='|' read -r id at file old new tests; do
  [ -n "$id" ] || continue
  [ "$at" -le "$COMMIT" ] || continue
  case "$file" in BA) file=$BA ;; LA) file=$LA ;; LS) file=$LS ;; AP) file=$AP ;; PM) file=$PM ;; GO) file=$GO ;; esac
  tests="$(echo "$tests" | sed "s|:TBI|:$TBI|g; s|:TLS|:$TLS|g; s|:TL|:$TL|g; s|:TRP|:$TRP|g; s|:TP|:$TP|g; s|:TW|:$TW|g; \
    s|:TAC|:$TAC|g; s|:SD4|:$SD4|g")"
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  red=1
  codes=""
  failed=""
  for layer in pure biz sec; do
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

want=11
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
