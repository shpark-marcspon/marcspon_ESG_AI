#!/usr/bin/env bash
# RP2c 의 심은 파손(발주서 band-handoffs/RP2c-order.md §3 「심은 파손」): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RP2c.sh   (커밋 하나 — R1~R16)
# 틀은 planted-breaks-RP2b.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
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

backup="$(mktemp -d /private/tmp/rp2c-planted.XXXXXX)"
case "$backup" in /private/tmp/rp2c-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
F=$PT/flows
# 줄: <id>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
# R1 잎 sha 에서 조상 제목 뺌 · R2 S2 목차 줄에 잎 전부 · R3 pagesSha256 대조 지움 · R4 versions 대조 지움 · R5 settings
# 대조 지움 · R6 rebuild 무시 · R7 앞 outcome failed 도 옮김(no_material 만 거름) · R8 origin 사슬 대신 늘 앞 실행
# · R9 documentId 그대로 · R10 base 의 프로젝트 대조 지움 · R11 482-1 블록 못 찾으면 FlowOutputError(옛 꼴) · R12
# GivenConflict 지움 · R13 482-3 경고 지움 · R14 DraftingBase 를 엶 — FORBID 를 지우기만 하면 바깥 DraftingResult 의
# forbid 를 물려받아 관측되는 것이 없다(RP2b R11) → extra="allow" 로 심음 · R15 위끝 ⓐ 에 옮긴 잎도 셈 · R16 차이
# 응답 Schema 의 model_config = OUT 뺌(ninja 기본 — 열림)
ROWS="R1|$P/contracts/wire.py|json.dumps([list(paths[key]), requirement[key]]|json.dumps([list(paths[key])[-1:], requirement[key]]|$PT/contracts/test_wire.py $F/test_draft_v2.py
R2|$P/flows/draft_v2.py|    requests = [map_request(inputs, adapters, batch, keys) for batch in groups]|    requests = [map_request(inputs, adapters, batch, [k for k, _, _ in _leaves(inputs)]) for batch in groups]|$F/test_draft_v2.py
R3|$P/flows/reuse.py|        or basis[\"pagesSha256\"] != extract[\"pagesSha256\"]\n||$F/test_reuse.py $F/test_draft_v2.py
R4|$P/flows/reuse.py|    if not base.versions_same:\n        return \"versions\"\n||$F/test_reuse.py $F/test_draft_v2.py
R5|$P/flows/reuse.py|    if base.result[\"settings\"] != settings:\n        return \"settings\"\n||$F/test_reuse.py $F/test_draft_v2.py
R6|$P/flows/reuse.py|    return changes.get(key) == \"same\" and key not in rebuild|    return changes.get(key) == \"same\"|$F/test_reuse.py $F/test_draft_v2.py
R7|$P/flows/reuse.py|or leaf[\"outcome\"][\"status\"] != \"done\":|or leaf[\"outcome\"][\"status\"] == \"no_material\":|$F/test_reuse.py
R8|$P/flows/reuse.py|    origin = leaf[\"reusedFrom\"] or {|    origin = None or {|$F/test_reuse.py $F/test_draft_v2.py
R9|$P/flows/reuse.py|            source[\"documentId\"] = document_id|            source[\"documentId\"] = source[\"documentId\"]|$F/test_reuse.py $F/test_draft_v2.py
R10|$P/flows/binding_v2.py| or found.project_id != project_id or found.result is None:| or found.result is None:|$F/test_binding_v2.py
R11|$P/flows/draft_v2.py|            if found is None:\n                placed.append(|            if found is None:\n                raise FlowOutputError(BLOCK_MISSING)\n                placed.append(|$F/test_draft_v2.py
R12|$P/engines/v2/material.py|        raise GivenConflict(f\"재료의 블록 id {block.id} 가 겹친다\")|        pass|$PT/engines/v2/test_material.py $F/test_draft_v2.py
R13|$P/flows/draft_v2.py|            answer[\"warnings\"] = [mapping.warning(\"material_truncated\", CUT_ALL, key=key)]|            answer[\"warnings\"] = []|$F/test_draft_v2.py
R14|$P/contracts/shapes.py|@with_config(FORBID)\nclass DraftingBase(TypedDict):|@with_config(ConfigDict(extra=\"allow\", use_attribute_docstrings=True))\nclass DraftingBase(TypedDict):|$PT/contracts/test_shapes.py $PT/service/schemas/test_projects.py
R15|$P/flows/draft_v2.py|        if not (key in kept and _reusable(inputs, plan, key, kept[key]))\n|        if key\n|$F/test_draft_v2.py
R16|$P/service/schemas/projects.py|    model_config = OUT\n\n    baseRunId: int|    baseRunId: int|$PT/service/schemas/test_projects.py"

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

want=16
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
