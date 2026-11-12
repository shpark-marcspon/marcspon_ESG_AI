#!/usr/bin/env bash
# 밴드 S3C-a(MARC-TICK-176: Scope 3 코랩 흐름 scope3.colab@157 의 바닥 — 실호출 0)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-S3C-a.sh --commit <1|2|3> [--step <n>] [--after-commit]
#   --commit 1 은 단계 1·4·5·10·12·13·15, 2 는 1·2·3·6·7·8·9·10·12·13·15, 3 은 전부(14 는 --after-commit 일 때만).
#   컨테이너(커밋 ① 의 ★b 이미지 확인)는 이 스크립트 밖에서 한 번 손으로 돌리고 보고에 적는다(발주서 §1-9).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 하나라도 0 이 아니면 1 로 끝난다.
# 커밋별 기대값(발주서 §2-4·§4, 러너 프롬프트):
#   단계 6 — ①② 는 BASE 그대로(Contracts: 16 kept · PLANTED=46/46), ③ 은 +1(17 · 47/47). 처분 ⑪ 은 커밋 ③.
#   단계 7 — ② 는 그 커밋 몫 P(P3·P4·P7·P8·P10·P14·P15 가운데 닿는 것) PLANTED=k/k, ③ 은 PLANTED=16/16·GUARDED_P6B=green
#            (P16 = 경계 ② 검증 N1 — pipeline.run 의 legacy_strings 감쌈을 지움. 감독 marcspon-93 이 ③ 몫으로 줌).
#   단계 4 — 감독 처분(2026-10-19, marcspon-93): uv 0.7.13 이 낸 잠금을 그대로 받는다. 지운 줄은 httpcore2 의 h11·truststore
#            의존 두 줄뿐(표지만 바뀜 — pandas 의 tzdata 플랫폼 표지로 풀이가 갈라짐), 판 줄 바뀜 0, resolution-markers +5줄,
#            새 패키지 셋(pandas·pandas-stubs·rapidfuzz). 그 밖의 - 줄이면 실패.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독 몫). AI 공급사 호출 0, 시험은 env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY.
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. 변수 바로 뒤에 한글이 오면 ${var}.
#   git grep 의 종료 ≥2 와 양성 대조 0 은 실패로 센다. \s 대신 [[:space:]].
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=90c2f6df372c3a3823c6511892850fd11dd2ccd0   # 워크트리를 세운 main(merge band/UA1, 그 앞 2f999c6 merge band/X1a)
OUT="$ROOT/../S3C-a.out"                         # 워크트리 밖. base-collect.txt·base-times.txt 가 여기 있다
A=apps/api-py
E="$A/esgapi"
I="$E/inventory"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; AFTER=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --after-commit) AFTER=1; shift ;;
    *) echo "사용: $0 --commit <1|2|3> [--step <n>] [--after-commit]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "--commit <1|2|3> 이 필요하다" >&2; exit 2 ;; esac

T="$(mktemp -d /private/tmp/s3ca.XXXXXX)"
case "$T" in /private/tmp/s3ca.*) ;; *) exit 99 ;; esac
FAILS=0

wanted() { # <단계> — 이 커밋에서 도는 단계인가
  [ -z "$ONLY" ] || [ "$ONLY" = "$1" ] || return 1
  case "$COMMIT:$1" in
    *:1 | *:10 | *:12 | *:13 | *:15) return 0 ;;
    1:4 | 1:5 | 3:4 | 3:5) return 0 ;;
    2:2 | 2:3 | 2:6 | 2:7 | 2:8 | 2:9) return 0 ;;
    3:2 | 3:3 | 3:6 | 3:7 | 3:8 | 3:9 | 3:11) return 0 ;;
    3:14) [ "$AFTER" = 1 ] ;;
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
  git diff "$BASE" -- . ":(exclude)$A/scripts/section4-S3C-a.sh" ":(exclude)$A/scripts/planted-breaks-S3C-a.sh" | grep "^+" | grep -v "^+++"
  git ls-files --others --exclude-standard -- . ":(exclude)$A/scripts/section4-S3C-a.sh" ":(exclude)$A/scripts/planted-breaks-S3C-a.sh" \
    | while IFS= read -r f; do sed "s/^/+/" "$f"; done
}
export -f changed added_lines
export ROOT BASE OUT A E I T COMMIT

echo "── 밴드 S3C-a §4 · 커밋 $COMMIT · BASE ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 기록 $T · $(uptime | sed 's/.*load/load/')"
echo "── BASE 시간(base-times.txt): $(tr "\n" " " < "$OUT/base-times.txt" 2> /dev/null)"

# ── 1. 순수 층 ──
if wanted 1; then
  step 1 "순수 층 초록(BASE 29초 — 같은 트리에서 HEAD=BASE 일 때 잼)" '(cd "$A" && s=$(date +%s); env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$T/pure.txt" 2>&1; code=$?; e=$(date +%s); tail -1 "$T/pure.txt"; echo "  걸린 시간 $((e - s))초"; exit $code)'
fi

# ── 2. inventory 표적 ──
if wanted 2; then
  step 2 "inventory 표적(수집 수 BASE → HEAD)" '(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/inventory -m "not django_db and not security" > "$T/inv.txt" 2>&1; code=$?; tail -1 "$T/inv.txt"; b="$(grep -c "^apps/api-py/esgapi/inventory/\|^esgapi/inventory/" "$OUT/base-collect.txt")"; echo "  BASE 수집(inventory 노드, 업무 층 포함) ${b}"; exit $code)'
fi

# ── 3. 계약 바이트 0 ──
if wanted 3; then
  step 3 "0줄 경로(generated·web·core·greenwash·기존 엔진 둘·기존 흐름 둘·tools·service·api.py·기존 고정 스키마 둘)" '
    P="$A/generated apps/web $E/core $E/greenwash $I/engines/scope3/llm_first_1 $I/engines/scope12 $I/flows/scope3_llm_first_1.py $I/flows/scope12_engine_1.py $I/tools $I/service $I/api.py $I/tests/data/flow-shapes/scope12.result@2.schema.json $I/tests/data/flow-shapes/scope3.llm-first.result@2.schema.json $I/tests/test_scope3_is_pure.py $A/scripts/test-layout-allow.txt"
    git diff --quiet "$BASE" -- $P; code=$?
    new="$(git ls-files --others --exclude-standard -- $P | wc -l | tr -d " ")"
    echo "  git diff EXIT=$code · 추적 안 된 새 파일 $new"
    [ "$code" = 0 ] && [ "$new" = 0 ]'
  step 3 "config/tests/test_api_contract.py 초록" '(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py > "$T/contract.txt" 2>&1; code=$?; tail -1 "$T/contract.txt"; exit $code)'
fi

# ── 4. 잠금 ──
if wanted 4; then
  step 4 "uv lock --check(uv 0.7.13)" '(cd "$A" && uvx --from "uv==0.7.13" uv lock --check > "$T/lockcheck.txt" 2>&1; code=$?; tail -2 "$T/lockcheck.txt"; exit $code)'
  step 4 "잠금 diff: 지운 줄 = httpcore2 의 h11·truststore 두 줄뿐, 더한 패키지 = pandas·pandas-stubs·rapidfuzz, 판 줄 바뀜 0(감독 처분 2026-10-19)" '
    git diff "$BASE" -- "$A/uv.lock" > "$T/lock.diff"
    grep "^-" "$T/lock.diff" | grep -v "^---" > "$T/lock-minus.txt"
    printf "%s\n" "-    { name = \"h11\" }," "-    { name = \"truststore\" }," > "$T/lock-minus-want.txt"
    diff "$T/lock-minus.txt" "$T/lock-minus-want.txt" > /dev/null; m=$?
    sed -n "s/^+name = \"\(.*\)\"$/\1/p" "$T/lock.diff" | sort > "$T/lock-added.txt"
    printf "%s\n" pandas pandas-stubs rapidfuzz > "$T/lock-added-want.txt"
    diff "$T/lock-added.txt" "$T/lock-added-want.txt" > /dev/null; n=$?
    # 판 줄: 이미 있는 패키지의 version = 줄은 하나도 지워지지 않는다(위 - 줄 목록이 정확히 둘이면 판 줄 - 는 0)
    v="$(grep -c "^-version = " "$T/lock.diff")"
    rm_blk="$(grep -c "^+resolution-markers = \[" "$T/lock.diff")"
    plus_h="$(grep -c -E "^\+    \{ name = \"(h11|truststore)\", marker = \"sys_platform != .emscripten.\" \}," "$T/lock.diff")"
    echo "  지운 줄 $(wc -l < "$T/lock-minus.txt" | tr -d " ") (기대 2 일치 $([ $m = 0 ] && echo 예 || echo 아니오)) · 더한 패키지 $(tr "\n" " " < "$T/lock-added.txt")(일치 $([ $n = 0 ] && echo 예 || echo 아니오)) · 지운 판 줄 ${v} · resolution-markers 블록 ${rm_blk} · 표지 붙은 h11·truststore ${plus_h}"
    for p in pytz types-pytz; do c="$(grep -c "^name = \"$p\"$" "$A/uv.lock")"; echo "  $p ${c}줄"; [ "$c" = 0 ] || exit 1; done
    [ "$m" = 0 ] && [ "$n" = 0 ] && [ "$v" = 0 ] && [ "$rm_blk" = 1 ] && [ "$plus_h" = 2 ]'
fi

# ── 5. 판 줄 ──
if wanted 5; then
  step 5 "pyproject 의 판 줄 셋, pytz·types-pytz 0, 설치된 판 = 그 줄, uv.lock 양성 대조" '
    for want in "\"pandas==3.0.6\"," "\"rapidfuzz==3.14.6\"," "\"pandas-stubs==3.0.5.260914\","; do
      c="$(grep -c -F "$want" "$A/pyproject.toml")"; echo "  $want ${c}줄"; [ "$c" = 1 ] || exit 1
    done
    c="$(grep -c -E "pytz" "$A/pyproject.toml")"; echo "  pyproject 의 pytz ${c}줄"; [ "$c" = 0 ] || exit 1
    got="$(cd "$A" && uv run --frozen python -c "import pandas, rapidfuzz; print(pandas.__version__, rapidfuzz.__version__)")"; rc=$?
    echo "  설치된 판: $got"; [ "$rc" = 0 ] && [ "$got" = "3.0.6 3.14.6" ] || exit 1
    pos="$(grep -c "^name = \"pandas\"$" "$A/uv.lock")"; echo "  양성 대조 ^name = \"pandas\" ${pos}줄"; [ "$pos" = 1 ]'
fi

# ── 6. import 계약 ──
if wanted 6; then
  if [ "$COMMIT" = 3 ]; then KEPT=17; PB=47; else KEPT=16; PB=46; fi
  export KEPT PB
  step 6 "lint-imports: Contracts: ${KEPT} kept, 0 broken." '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; [ "$(tail -1 "$T/lint.txt")" = "Contracts: $KEPT kept, 0 broken." ] && exit $code; exit 1)'
  step 6 "scripts/planted-breaks.sh: PLANTED=${PB}/${PB}, 지문 같음" '("$A/scripts/planted-breaks.sh" > "$T/planted.txt" 2>&1; code=$?; grep -v "맞음" "$T/planted.txt"; [ "$(tail -1 "$T/planted.txt")" = "PLANTED=$PB/$PB" ] && ! grep -q "작업 트리가 처음과 다르다" "$T/planted.txt" && exit $code; exit 1)'
  if [ "$COMMIT" = 3 ]; then
    step 6 "planted-breaks.sh: BASE 의 경우·기대·심는 줄이 하나도 안 바뀜(- 줄은 머리 글의 수만), 새 경우 하나" '
      git diff "$BASE" -- "$A/scripts/planted-breaks.sh" > "$T/pb.diff"
      minus="$(grep "^-" "$T/pb.diff" | grep -v "^---")"
      echo "$minus" | sed "s/^/  - /"
      bad="$(printf "%s\n" "$minus" | grep -v "^$" | grep -v -c "^-# 심은 파손: 계약(.importlinter) 열여섯")"
      added="$(grep -c "^+check \"" "$T/pb.diff")"
      echo "  머리 글 밖 - 줄 ${bad} · 더한 check ${added}"
      [ "$bad" = 0 ] && [ "$added" = 1 ]'
  fi
fi

# ── 7. 심은 파손 ──
if wanted 7; then
  step 7 "scripts/planted-breaks-S3C-a.sh --commit $COMMIT" '("$A/scripts/planted-breaks-S3C-a.sh" --commit "$COMMIT" > "$T/planted-s3ca.txt" 2>&1; code=$?; cat "$T/planted-s3ca.txt" | tail -22; exit $code)'
fi

# ── 8. 시험 자리 ──
if wanted 8; then
  step 8 "check_test_layout.py EXIT=0, test-layout-allow.txt diff 0줄" '(cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$T/layout.txt" 2>&1; code=$?; tail -2 "$T/layout.txt"; n="$(git diff "$BASE" -- scripts/test-layout-allow.txt | wc -l | tr -d " ")"; echo "  allow diff ${n}줄"; [ "$code" = 0 ] && [ "$n" = 0 ])'
fi

# ── 9. 노드 id ──
if wanted 9; then
  step 9 "BASE 의 수집 노드 id ⊆ HEAD 의 것(기존 노드 id 가 하나도 안 바뀜)" '
    test -s "$OUT/base-collect.txt" || { echo "  base-collect.txt 가 없다"; exit 1; }
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider esgapi tests > "$T/collect-now.txt" 2>&1); code=$?
    grep "::" "$OUT/base-collect.txt" | sort > "$T/ids-base.txt"; grep "::" "$T/collect-now.txt" | sort > "$T/ids-now.txt"
    gone="$(comm -23 "$T/ids-base.txt" "$T/ids-now.txt" | wc -l | tr -d " ")"
    new="$(comm -13 "$T/ids-base.txt" "$T/ids-now.txt" | wc -l | tr -d " ")"
    comm -23 "$T/ids-base.txt" "$T/ids-now.txt" | head -10 | sed "s/^/  ★ 빠짐 /"
    echo "  BASE $(wc -l < "$T/ids-base.txt" | tr -d " ") · HEAD $(wc -l < "$T/ids-now.txt" | tr -d " ") · 빠진 것 ${gone} · 새 것 ${new}"
    [ "$code" = 0 ] && [ "$gone" = 0 ] && [ -s "$T/ids-base.txt" ]'
fi

# ── 10. 빠른 게이트 ──
if wanted 10; then
  step 10 "scripts/verify.sh --fast 끝 줄 VERIFY_FAST=PASS(BASE 26초, 30초를 넘으면 보고)" '(s=$(date +%s); scripts/verify.sh --fast > "$T/verify-fast.txt" 2>&1; code=$?; e=$(date +%s); tail -2 "$T/verify-fast.txt"; echo "  걸린 시간 $((e - s))초"; [ "$(tail -1 "$T/verify-fast.txt")" = "VERIFY_FAST=PASS" ] && exit $code; exit 1)'
fi

# ── 11. 시간 ──
if wanted 11; then
  step 11 "import pandas 누적(호스트, 세 번 중앙값)" '(cd "$A" && for i in 1 2 3; do uv run --frozen python -X importtime -c "import pandas" 2>&1 | tail -1 | awk -F"|" "{gsub(/ /,\"\",\$2); print \$2}"; done | sort -n | sed -n 2p | sed "s/^/  중앙값 µs /")'
fi

# ── 12. 허용 경로 ──
if wanted 12; then
  step 12 "바뀐 경로가 §4-12 허용 목록 안" '
    changed > "$T/changed.txt"
    grep -v -E \
      -e "^$I/engines/scope3/colab_157/" \
      -e "^$I/flows/scope3_colab_157\.py$" \
      -e "^$I/prompts/scope3-colab-[a-z0-9-]+/1\.md$" \
      -e "^$I/tests/engines/scope3/colab_157/" \
      -e "^$I/tests/flows/test_scope3_colab_157\.py$" \
      -e "^$I/tests/data/flow-shapes/scope3\.colab\.result@1\.schema\.json$" \
      -e "^$I/flows/(registration|__init__)\.py$" \
      -e "^$I/contracts/shapes\.py$" \
      -e "^$I/README\.md$" \
      -e "^$I/prompts/README\.md$" \
      -e "^$I/__init__\.py$" \
      -e "^$I/engines/scope3/__init__\.py$" \
      -e "^$I/tests/(test_flows|test_flow_shapes|flows/test_vocab|contracts/test_shapes)\.py$" \
      -e "^$A/(pyproject\.toml|uv\.lock|\.importlinter)$" \
      -e "^$E/reconcile/tests/test_tasks_registered\.py$" \
      -e "^$A/scripts/planted-breaks\.sh$" \
      -e "^README\.md$" \
      -e "^$A/scripts/(section4|planted-breaks)-S3C-a\.sh$" \
      "$T/changed.txt" > "$T/outside.txt"
    echo "  바뀐 파일 $(wc -l < "$T/changed.txt" | tr -d " ")개 · 허용 밖 $(wc -l < "$T/outside.txt" | tr -d " ")개"
    sed "s/^/  ★ /" "$T/outside.txt"
    if [ "$COMMIT" != 3 ]; then
      early="$(grep -c -E "^($A/\.importlinter|$E/reconcile/tests/test_tasks_registered\.py|$A/scripts/planted-breaks\.sh)$" "$T/changed.txt")"
      echo "  테스트 트랙·계약 경로(커밋 ③ 몫) ${early}개"; [ "$early" = 0 ] || exit 1
    fi
    [ -s "$T/changed.txt" ] && [ ! -s "$T/outside.txt" ]'
fi

# ── 13. 원본·비밀 ──
if wanted 13; then
  step 13 "더한 줄·커밋 메시지에 키 꼴 0, 새 바이너리 자료 0, 바꿈 표지 0, 표본 이름 지킴이" '
    added_lines > "$T/added.txt"
    a="$(grep -c -E "sk-[A-Za-z0-9_-]{20,}|sk-ant-" "$T/added.txt")"
    b="$(git log --format=%B "$BASE"..HEAD | grep -c -E "sk-[A-Za-z0-9_-]{20,}|sk-ant-")"
    c=0; [ -n "${S3CA_MSG:-}" ] && c="$(grep -c -E "sk-[A-Za-z0-9_-]{20,}|sk-ant-" "$S3CA_MSG")"
    bin="$(changed | grep -c -E "\.(xlsx|xls|csv|ipynb)$")"
    mark="$(grep -c -E "\[고객사\]|\[Client\]|\[Peer|\[자회사\]" "$T/added.txt")"
    pos="$(printf "%s\n" "+x sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA" | grep -c -E "sk-[A-Za-z0-9_-]{20,}|sk-ant-")"
    echo "  키 꼴: diff ${a} · 커밋 메시지 ${b} · 쓸 메시지(${S3CA_MSG:-없음}) ${c} · 양성 대조 ${pos} · 새 바이너리 ${bin} · 바꿈 표지 ${mark}"
    g=0
    if [ "$COMMIT" != 1 ]; then
      (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/inventory/tests/engines/scope3/colab_157/test_samples.py > "$T/samples.txt" 2>&1); g=$?
      echo "  표본 이름 지킴이(test_samples.py): $(tail -1 "$T/samples.txt")"
    fi
    [ "$a$b$c$bin$mark" = 00000 ] && [ "$pos" = 1 ] && [ "$g" = 0 ]'
fi

# ── 14. 작업 트리 ──
if wanted 14; then
  step 14 "git status --porcelain 0줄" 'n="$(git status --porcelain | wc -l | tr -d " ")"; echo "  ${n}줄"; [ "$n" = 0 ]'
fi

# ── 15. 타입 검사 ──
if wanted 15; then
  step 15 "pyright 0 errors(BASE 10초), 더한 완화 줄 0, cast( 셈" '
    (cd "$A" && s=$(date +%s); uv run --frozen pyright > "$T/pyright.txt" 2>&1; code=$?; e=$(date +%s); tail -1 "$T/pyright.txt"; echo "  걸린 시간 $((e - s))초"; exit $code); code=$?
    added_lines > "$T/added15.txt"
    h="$(grep -c -E "^\+[[:space:]]*# pyright:" "$T/added15.txt")"
    i="$(grep -c "pyright: ignore" "$T/added15.txt")"
    t="$(grep -c "type: ignore" "$T/added15.txt")"
    k="$(grep -c "cast(" "$T/added15.txt")"
    echo "  더한 줄: # pyright: 머리 ${h} · pyright: ignore ${i} · type: ignore ${t} · cast( ${k}"
    grep -n "cast(" "$T/added15.txt" | sed "s/^/  cast /" | head -40
    [ "$code" = 0 ] && [ "$(tail -1 "$T/pyright.txt" | cut -d" " -f1)" = 0 ] && [ "$h$i$t" = 000 ]'
fi

echo
echo "── 기록: $T"
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
