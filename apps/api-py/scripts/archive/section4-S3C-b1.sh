#!/usr/bin/env bash
# 밴드 S3C-b1(MARC-TICK-208: Scope 3 코랩 흐름 b 몫 ① — 지출·폐기물 시트 넷 C4-2·C9-2·C6-2·C5)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-S3C-b1.sh --commit <1|2> [--step <n>] [--after-commit]
#         apps/api-py/scripts/section4-S3C-b1.sh --measure-base   (BASE 의 수집 목록·시간을 $OUT 에 한 번 잰다)
#   --commit 1 은 단계 1~11, 2 는 1~12. 13 은 --after-commit 일 때만(커밋 ①·② 둘 다).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 하나라도 0 이 아니면 1 로 끝난다.
# BASE 잼(단계 1·2·7·11 의 비교 값): $OUT/base-times.txt·base-collect.txt. 작업 트리가 이미 바뀌어 있으므로 --measure-base 는
#   $OUT/base-tree 에 BASE 를 따로 세운 임시 워크트리(git worktree add --detach)에서 재고 끝나면 지운다 — 이 워크트리는 건드리지 않는다.
#   verify.sh --fast 의 BASE 시간은 그 임시 트리에 node_modules 가 없어 재지 않는다. 참고 값: S3C-b0.out/verify-fast.log 「전체 37초」
#   (S3C-b0 머리 = 병합 뒤 BASE 와 같은 코드).
# 기대값(발주서 §4): lint-imports Contracts: 17 kept · scripts/planted-breaks.sh PLANTED=47/47 — 둘 다 BASE 그대로.
# 경로 맞춤(발주서 글 → 실제 자리): generated/ = apps/api-py/generated(esgapi/generated 는 없다) · tests/security = apps/api-py/tests/security
#   (esgapi/tests/security 는 없다) · core/flows·core/calc·core/llm·core/permissions.py 는 $E/core 가 덮는다.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독 몫). 업무·보안·통합 층, 컨테이너도 안 돌린다. AI 공급사 호출 0.
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. 변수 바로 뒤에 한글이 오면 ${var}.
#   git grep 의 종료 ≥2 와 양성 대조 0 은 실패로 센다. \s 대신 [[:space:]].
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=78d779ec7f96a9f584f620d10f3da0d66110df46   # 워크트리를 세운 main(merge band/S3C-b0, 2026-10-20)
OUT="$ROOT/../S3C-b1.out"                         # 워크트리 밖. base-collect.txt·base-times.txt 가 여기 있다
A=apps/api-py
E="$A/esgapi"
I="$E/inventory"
C="$I/engines/scope3/colab_157"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; AFTER=0; MEASURE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --after-commit) AFTER=1; shift ;;
    --measure-base) MEASURE=1; shift ;;
    *) echo "사용: $0 --commit <1|2> [--step <n>] [--after-commit] | --measure-base" >&2; exit 2 ;;
  esac
done

# ── BASE 잼(한 번) ──
if [ "$MEASURE" = 1 ]; then
  mkdir -p "$OUT"
  BT="$OUT/base-tree"
  [ -e "$BT" ] && { echo "$BT 가 이미 있다 — 지우고 다시" >&2; exit 2; }
  git worktree add --detach "$BT" "$BASE" > "$OUT/base-tree-add.txt" 2>&1
  code=$?
  [ "$code" = 0 ] || { cat "$OUT/base-tree-add.txt"; exit 1; }
  (
    cd "$BT/apps/api-py" || exit 1
    echo "HEAD=$(git rev-parse HEAD) load=$(sysctl -n vm.loadavg)" > "$OUT/base-times.txt"
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider esgapi tests > "$OUT/base-collect.txt" 2>&1
    echo "collect rc=$?" >> "$OUT/base-times.txt"
    s=$(date +%s); env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$OUT/base-pure.txt" 2>&1
    rc=$?; e=$(date +%s); echo "pure rc=$rc $((e - s))s" >> "$OUT/base-times.txt"
    s=$(date +%s); uv run --frozen pyright > "$OUT/base-pyright.txt" 2>&1
    rc=$?; e=$(date +%s); echo "pyright rc=$rc $((e - s))s" >> "$OUT/base-times.txt"
    echo "verify-fast (안 잼 — 참고 S3C-b0 37s)" >> "$OUT/base-times.txt"
    echo "load-end=$(sysctl -n vm.loadavg)" >> "$OUT/base-times.txt"
  )
  code=$?
  git worktree remove --force "$BT"
  rm_code=$?
  cat "$OUT/base-times.txt"
  echo "임시 워크트리 지움 EXIT=$rm_code"
  [ "$code" = 0 ] && [ "$rm_code" = 0 ]
  exit $?
fi

case "$COMMIT" in 1 | 2) ;; *) echo "--commit <1|2> 이 필요하다" >&2; exit 2 ;; esac

T="$(mktemp -d /private/tmp/s3cb1.XXXXXX)"
case "$T" in /private/tmp/s3cb1.*) ;; *) exit 99 ;; esac
FAILS=0

wanted() { # <단계> — 이 커밋에서 도는 단계인가
  [ -z "$ONLY" ] || [ "$ONLY" = "$1" ] || return 1
  case "$COMMIT:$1" in
    *:1 | *:2 | *:3 | *:4 | *:5 | *:6 | *:7 | *:8 | *:9 | *:10 | *:11) return 0 ;;
    2:12) return 0 ;;
    *:13) [ "$AFTER" = 1 ] ;;
    *) return 1 ;;
  esac
}
step() { # <n> <설명> <셸 글>
  local n="$1" desc="$2" code
  shift 2
  echo
  echo "[$n] $desc"
  (eval "$*")
  code=$?
  echo "[$n] $desc EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
changed() { { git diff --no-renames --name-only "$BASE"; git ls-files --others --exclude-standard; } | sort -u; }
added_lines() { # 이 밴드의 스크립트 둘을 뺀 diff 의 더한 줄(추적 안 된 새 파일 포함)
  git diff "$BASE" -- . ":(exclude)$A/scripts/section4-S3C-b1.sh" ":(exclude)$A/scripts/planted-breaks-S3C-b1.sh" | grep "^+" | grep -v "^+++"
  git ls-files --others --exclude-standard -- . ":(exclude)$A/scripts/section4-S3C-b1.sh" ":(exclude)$A/scripts/planted-breaks-S3C-b1.sh" \
    | while IFS= read -r f; do sed "s/^/+/" "$f"; done
}
export -f changed added_lines
export ROOT BASE OUT A E I C T COMMIT

echo "── 밴드 S3C-b1 §4 · 커밋 $COMMIT · BASE ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 기록 $T · $(uptime | sed 's/.*load/load/')"
if [ -s "$OUT/base-times.txt" ]; then
  echo "── BASE 시간(base-times.txt): $(tr "\n" " " < "$OUT/base-times.txt")"
else
  echo "── BASE 시간 없음: 먼저 $0 --measure-base (단계 2·7 은 base-collect.txt 가 없으면 실패)"
fi

# ── 1. 순수 층 ──
if wanted 1; then
  step 1 "순수 층 초록(시간 BASE 와 함께 — base-times.txt 의 pure 줄)" '(cd "$A" && s=$(date +%s); env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$T/pure.txt" 2>&1; code=$?; e=$(date +%s); tail -1 "$T/pure.txt"; echo "  걸린 시간 $((e - s))초 · BASE $(grep "^pure " "$OUT/base-times.txt" 2> /dev/null)"; exit $code)'
fi

# ── 2. inventory 수집 수 ──
if wanted 2; then
  step 2 "inventory 수집 수 BASE → HEAD(HEAD ≥ BASE)" '
    test -s "$OUT/base-collect.txt" || { echo "  base-collect.txt 가 없다(--measure-base)"; exit 1; }
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider esgapi/inventory > "$T/inv-collect.txt" 2>&1); code=$?
    b="$(grep -c "^esgapi/inventory/.*::" "$OUT/base-collect.txt")"
    h="$(grep -c "^esgapi/inventory/.*::" "$T/inv-collect.txt")"
    echo "  inventory 노드 BASE ${b} → HEAD ${h}"
    [ "$code" = 0 ] && [ "$b" -gt 0 ] && [ "$h" -ge "$b" ]'
fi

# ── 3. 0줄 경로 ──
if wanted 3; then
  P0="$C/purchase.py $I/engines/scope3/llm_first_1 $I/engines/scope12 $I/tools $I/flows/registration.py $I/flows/__init__.py $I/service $I/api.py $A/generated apps/web $E/core"
  P4="$E/config/api.py $E/config/apps_list.py $E/runs $A/.importlinter $A/pyproject.toml $A/uv.lock $E/organization $A/scripts/planted-breaks.sh $E/reconcile/tests/test_tasks_registered.py $A/tests/security $E/config/tests"
  [ "$COMMIT" = 1 ] && P4="$P4 $C/pipeline.py $C/serialize.py $I/contracts"
  export P0 P4
  step 3 "1-2·1-3 0줄 경로(커밋 ① 은 pipeline.py·serialize.py·contracts 도)" '
    for p in $P0 $P4; do n="$(git ls-files -- "$p" | wc -l | tr -d " ")"; [ "$n" -gt 0 ] || { echo "  ★ 추적 파일 0 인 경로(양성 대조 실패): $p"; exit 1; }; done
    git diff --quiet "$BASE" -- $P0 $P4; code=$?
    new="$(git ls-files --others --exclude-standard -- $P0 $P4 | wc -l | tr -d " ")"
    git diff --stat "$BASE" -- $P0 $P4 | tail -5 | sed "s/^/  /"
    echo "  경로 $(echo $P0 $P4 | wc -w | tr -d " ")개 · git diff EXIT=$code · 추적 안 된 새 파일 $new"
    [ "$code" = 0 ] && [ "$new" = 0 ]'
  step 3 "config/tests/test_api_contract.py 초록" '(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py > "$T/contract.txt" 2>&1; code=$?; tail -1 "$T/contract.txt"; exit $code)'
fi

# ── 4. import 계약 ──
if wanted 4; then
  KEPT=17; PB=47   # BASE 78d779e 의 값(발주서 §4-4)
  export KEPT PB
  step 4 "lint-imports: Contracts: ${KEPT} kept, 0 broken." '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; [ "$(tail -1 "$T/lint.txt")" = "Contracts: $KEPT kept, 0 broken." ] && exit $code; exit 1)'
  step 4 "scripts/planted-breaks.sh: PLANTED=${PB}/${PB}, FINGERPRINT=same" '("$A/scripts/planted-breaks.sh" > "$T/planted.txt" 2>&1; code=$?; grep -v "맞음" "$T/planted.txt"; fp=same; grep -q "작업 트리가 처음과 다르다" "$T/planted.txt" && fp=differs; echo "FINGERPRINT=$fp"; [ "$(tail -1 "$T/planted.txt")" = "PLANTED=$PB/$PB" ] && [ "$fp" = same ] && exit $code; exit 1)'
fi

# ── 5. 이 밴드의 심은 파손 ──
if wanted 5; then
  step 5 "scripts/planted-breaks-S3C-b1.sh --commit $COMMIT" '("$A/scripts/planted-breaks-S3C-b1.sh" --commit "$COMMIT" > "$T/planted-s3cb1.txt" 2>&1; code=$?; tail -24 "$T/planted-s3cb1.txt"; exit $code)'
fi

# ── 6. 시험 자리 ──
if wanted 6; then
  step 6 "check_test_layout.py EXIT=0, test-layout-allow.txt diff 0줄" '(cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$T/layout.txt" 2>&1; code=$?; tail -2 "$T/layout.txt"; n="$(git diff "$BASE" -- scripts/test-layout-allow.txt | wc -l | tr -d " ")"; echo "  allow diff ${n}줄"; [ "$code" = 0 ] && [ "$n" = 0 ])'
fi

# ── 7. 노드 id ──
if wanted 7; then
  step 7 "BASE 의 수집 노드 id ⊆ HEAD 의 것(기존 노드 id 가 하나도 안 바뀜)" '
    test -s "$OUT/base-collect.txt" || { echo "  base-collect.txt 가 없다(--measure-base)"; exit 1; }
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider esgapi tests > "$T/collect-now.txt" 2>&1); code=$?
    grep "::" "$OUT/base-collect.txt" | sort > "$T/ids-base.txt"; grep "::" "$T/collect-now.txt" | sort > "$T/ids-now.txt"
    gone="$(comm -23 "$T/ids-base.txt" "$T/ids-now.txt" | wc -l | tr -d " ")"
    new="$(comm -13 "$T/ids-base.txt" "$T/ids-now.txt" | wc -l | tr -d " ")"
    comm -23 "$T/ids-base.txt" "$T/ids-now.txt" | head -10 | sed "s/^/  ★ 빠짐 /"
    echo "  BASE $(wc -l < "$T/ids-base.txt" | tr -d " ") · HEAD $(wc -l < "$T/ids-now.txt" | tr -d " ") · 빠진 것 ${gone} · 새 것 ${new}"
    [ "$code" = 0 ] && [ "$gone" = 0 ] && [ -s "$T/ids-base.txt" ]'
fi

# ── 8. 빠른 게이트 ──
if wanted 8; then
  step 8 "scripts/verify.sh --fast 끝 줄 VERIFY_FAST=PASS(BASE 참고 37초 — S3C-b0.out/verify-fast.log)" '(s=$(date +%s); scripts/verify.sh --fast > "$T/verify-fast.txt" 2>&1; code=$?; e=$(date +%s); tail -2 "$T/verify-fast.txt"; echo "  걸린 시간 $((e - s))초"; [ "$(tail -1 "$T/verify-fast.txt")" = "VERIFY_FAST=PASS" ] && exit $code; exit 1)'
fi

# ── 9. 허용 경로 ──
if wanted 9; then
  step 9 "바뀐 경로가 §1-1 허용 목록 안" '
    changed > "$T/changed.txt"
    grep -v -E \
      -e "^$C/(spend|waste|units|travel_mode|company_mapping|activity|__init__|pipeline|serialize|template|llm|factor_book|constants)\.py$" \
      -e "^$I/prompts/scope3-colab-[a-z0-9-]+/1\.md$" \
      -e "^$I/prompts/README\.md$" \
      -e "^$I/contracts/shapes\.py$" \
      -e "^$I/tests/data/flow-shapes/scope3\.colab\.result@1\.schema\.json$" \
      -e "^$I/tests/engines/scope3/colab_157/" \
      -e "^$I/tests/flows/test_vocab\.py$" \
      -e "^$I/tests/contracts/test_shapes\.py$" \
      -e "^$I/tests/test_flow_shapes\.py$" \
      -e "^$I/tests/flows/test_scope3_colab_157\.py$" \
      -e "^$I/tests/(test_)?scope3colab_dump\.py$" \
      -e "^$I/flows/scope3_colab_157\.py$" \
      -e "^$I/README\.md$" \
      -e "^$A/scripts/(section4|planted-breaks)-S3C-b1\.sh$" \
      "$T/changed.txt" > "$T/outside.txt"
    echo "  바뀐 파일 $(wc -l < "$T/changed.txt" | tr -d " ")개 · 허용 밖 $(wc -l < "$T/outside.txt" | tr -d " ")개"
    sed "s/^/  ★ /" "$T/outside.txt"
    if [ "$COMMIT" = 1 ]; then
      early="$(grep -c -E "^($C/(pipeline|serialize)\.py|$I/contracts/.*)$" "$T/changed.txt")"
      echo "  커밋 ② 몫(pipeline·serialize·contracts) ${early}개"; [ "$early" = 0 ] || exit 1
    fi
    [ -s "$T/changed.txt" ] && [ ! -s "$T/outside.txt" ]'
fi

# ── 10. 원본·비밀 ──
if wanted 10; then
  step 10 "더한 줄·커밋 메시지에 키 꼴 0, 새 바이너리 자료 0, 바꿈 표지 0, 표본 이름 지킴이(test_samples.py) 초록" '
    added_lines > "$T/added.txt"
    a="$(grep -c -E "sk-[A-Za-z0-9_-]{20,}|sk-ant-" "$T/added.txt")"
    b="$(git log --format=%B "$BASE"..HEAD | grep -c -E "sk-[A-Za-z0-9_-]{20,}|sk-ant-")"
    c=0; [ -n "${S3CB1_MSG:-}" ] && c="$(grep -c -E "sk-[A-Za-z0-9_-]{20,}|sk-ant-" "$S3CB1_MSG")"
    bin="$(changed | grep -c -E "\.(xlsx|xls|csv|ipynb)$")"
    mark="$(grep -c -E "\[고객사\]|\[Client\]|\[Peer|\[자회사\]" "$T/added.txt")"
    pos="$(printf "%s\n" "+x sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA" | grep -c -E "sk-[A-Za-z0-9_-]{20,}|sk-ant-")"
    pos2="$(printf "%s\n" "+x [고객사] y" | grep -c -E "\[고객사\]|\[Client\]|\[Peer|\[자회사\]")"
    echo "  키 꼴: diff ${a} · 커밋 메시지 ${b} · 쓸 메시지(S3CB1_MSG=${S3CB1_MSG:-없음}) ${c} · 양성 대조 ${pos}/${pos2} · 새 바이너리 ${bin} · 바꿈 표지 ${mark}"
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/inventory/tests/engines/scope3/colab_157/test_samples.py > "$T/samples.txt" 2>&1); g=$?
    echo "  표본 이름 지킴이(test_samples.py): $(tail -1 "$T/samples.txt")"
    [ "$a$b$c$bin$mark" = 00000 ] && [ "$pos$pos2" = 11 ] && [ "$g" = 0 ]'
fi

# ── 11. 타입 검사 ──
if wanted 11; then
  step 11 "pyright 0 errors(BASE 는 base-times.txt), 더한 완화 줄 0, cast( 셈" '
    (cd "$A" && s=$(date +%s); uv run --frozen pyright > "$T/pyright.txt" 2>&1; code=$?; e=$(date +%s); tail -1 "$T/pyright.txt"; echo "  걸린 시간 $((e - s))초 · BASE $(grep "^pyright " "$OUT/base-times.txt" 2> /dev/null)"; exit $code); code=$?
    added_lines > "$T/added11.txt"
    h="$(grep -c -E "^\+[[:space:]]*# pyright:" "$T/added11.txt")"
    i="$(grep -c "pyright: ignore" "$T/added11.txt")"
    t="$(grep -c "type: ignore" "$T/added11.txt")"
    k="$(grep -c "cast(" "$T/added11.txt")"
    echo "  더한 줄: # pyright: 머리 ${h} · pyright: ignore ${i} · type: ignore ${t} · cast( ${k}"
    grep -n "cast(" "$T/added11.txt" | sed "s/^/  cast /" | head -40
    [ "$code" = 0 ] && [ "$(tail -1 "$T/pyright.txt" | cut -d" " -f1)" = 0 ] && [ "$h$i$t" = 000 ]'
fi

# ── 12. 고정 스키마·generated (커밋 ②) ──
if wanted 12; then
  step 12 "고정 스키마 scope3.colab.result@1 다시 뽑아 cmp(test_flow_shapes.pinned_text 꼴), generated/ 0바이트" '
    (cd "$A" && uv run --frozen python -c "import json, sys; from esgapi.inventory.contracts import shapes; sys.stdout.write(json.dumps(shapes.RESULT_SHAPES[\"scope3.colab.result@1\"].json_schema(), ensure_ascii=False, indent=2) + \"\n\")" > "$T/regen.schema.json" 2> "$T/regen.err"); r=$?
    [ "$r" = 0 ] || { tail -5 "$T/regen.err"; exit 1; }
    cmp "$T/regen.schema.json" "$I/tests/data/flow-shapes/scope3.colab.result@1.schema.json"; m=$?
    git diff --quiet "$BASE" -- "$A/generated"; g=$?
    gn="$(git ls-files --others --exclude-standard -- "$A/generated" | wc -l | tr -d " ")"
    echo "  다시 뽑은 $(wc -c < "$T/regen.schema.json" | tr -d " ")바이트 · cmp EXIT=$m · generated diff EXIT=$g · 새 파일 $gn"
    [ -s "$T/regen.schema.json" ] && [ "$m" = 0 ] && [ "$g" = 0 ] && [ "$gn" = 0 ]'
fi

# ── 13. 작업 트리 ──
if wanted 13; then
  step 13 "git status --porcelain 0줄" 'n="$(git status --porcelain | wc -l | tr -d " ")"; echo "  ${n}줄"; [ "$n" = 0 ]'
fi

echo
echo "── 기록: $T"
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
