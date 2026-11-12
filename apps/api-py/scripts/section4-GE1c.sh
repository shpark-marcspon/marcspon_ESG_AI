#!/usr/bin/env bash
# 밴드 GE1c(MARC-TICK-591)의 §4 자기검증(발주서 band-handoffs/GE1c-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-GE1c.sh                전부(5 의 DB·전량은 빼고 — 그것은 verify.sh·test-business.sh 로)
#   apps/api-py/scripts/section4-GE1c.sh --step 1,2,7   일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   GE1C_BASE   기준 커밋(기본: 9ad1e020 — GE1b 병합)
#   GE1C_OUT    산출물 자리(기본: 워크트리 곁의 GE1c.out). 로그는 $GE1C_OUT/section4/ 아래
#   GE1C_WORDS  금지어 목록(줄마다 하나, 추적 밖 — 기본: 곁의 G1a.out·GE1.out 의 forbidden-words.txt)
#   GE1C_OVERLAP 정답 문장 20자 겹침 셈 스크립트(추적 밖 — 기본: esg-lab/out/GE1/drivers/overlap20.py)
# 5 의 순수 층은 main 저장소 .git/verify.lock 이 있으면 돌리지 않고 EXIT=2 로 적는다(runner-common §5).
# 금지어·겹침은 수만 찍는다(맞은 글자를 찍지 않는다). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${GE1C_BASE:-9ad1e020}"
OUT="${GE1C_OUT:-$SIDE/GE1c.out}"
S4="$OUT/section4"
mkdir -p "$S4"
WORDS="${GE1C_WORDS:-$SIDE/G1a.out/forbidden-words.txt $SIDE/GE1.out/forbidden-words.txt}"
OVERLAP="${GE1C_OVERLAP:-$SIDE/../esg-lab/out/GE1/drivers/overlap20.py}"
MAIN_GIT="$(git -C "$ROOT" rev-parse --git-common-dir)"
case "$MAIN_GIT" in /*) ;; *) MAIN_GIT="$ROOT/$MAIN_GIT" ;; esac
api() { (cd "$API_PY" && uv run --frozen "$@"); }

STEPS="all"
if [ "${1:-}" = "--step" ]; then
  STEPS=",${2:?--step 뒤에 번호},"
fi
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

# 1. 수정 허용 경로(발주서 §4-1 의 정규식 그대로 — 작업 트리 기준)
if want 1; then
  git -C "$ROOT" status --porcelain -uall > "$S4/status.txt"
  git -C "$ROOT" diff --name-only "$BASE" > "$S4/committed.txt"
  out="$(grep -v -E '^.. apps/api-py/(esgapi/greenwash/(engines/g1/[a-z_0-9]+\.py|flows/(engine_g1|binding_g1)\.py|service/actions/engine_g1\.py|tests/(engines/g1/.*|flows/test_(engine|binding)_g1[a-z_0-9]*\.py|service/[a-z_/]*test_engine_g1[a-z_0-9]*\.py))|scripts/(section4|planted-breaks)-GE1c\.sh)$' "$S4/status.txt")"
  out2="$(grep -v -E '^apps/api-py/(esgapi/greenwash/(engines/g1/[a-z_0-9]+\.py|flows/(engine_g1|binding_g1)\.py|service/actions/engine_g1\.py|tests/(engines/g1/.*|flows/test_(engine|binding)_g1[a-z_0-9]*\.py|service/[a-z_/]*test_engine_g1[a-z_0-9]*\.py))|scripts/(section4|planted-breaks)-GE1c\.sh)$' "$S4/committed.txt")"
  echo "    작업 트리 $(wc -l < "$S4/status.txt" | tr -d ' ')줄 · 커밋된 바뀜 $(wc -l < "$S4/committed.txt" | tr -d ' ')파일"
  [ -n "$out$out2" ] && printf '%s\n%s\n' "$out" "$out2" | sed '/^$/d; s/^/    밖: /'
  report 1 "수정 허용 경로" "$([ -z "$out$out2" ] && echo 0 || echo 1)"
fi

# 2. 0줄 자리 · 71 땅 sha16(빈 diff = e3b0c44298fc1c14) · generated
if want 2; then
  n=$(git -C "$ROOT" diff "$BASE" --numstat -- apps/api-py/.importlinter apps/api-py/esgapi/greenwash/prompts apps/api-py/esgapi/greenwash/contracts apps/api-py/esgapi/greenwash/apps.py apps/api-py/esgapi/greenwash/flows/registration.py apps/api-py/esgapi/greenwash/tests/data apps/web deploy docs | wc -l | tr -d ' ')
  sha=$(git -C "$ROOT" diff "$BASE" -- apps/api-py/esgapi/core apps/api-py/esgapi/config apps/api-py/esgapi/runs apps/api-py/esgapi/runbundle apps/api-py/generated apps/api-py/tests/security | shasum -a 256 | cut -c1-16)
  echo "    0줄 자리 numstat ${n}줄 · 71 땅 sha16 $sha"
  report 2 "0줄 자리·71 땅" "$([ "$n" = 0 ] && [ "$sha" = e3b0c44298fc1c14 ] && echo 0 || echo 1)"
fi

# 3. 셈 줄(BASE..작업 트리) — 이 밴드는 0 기대. 병합 전 main 쪽 대조는 감독이 한다
if want 3; then
  git -C "$ROOT" diff "$BASE" -U0 -- apps/api-py/esgapi/core/tests apps/api-py/esgapi/config/tests apps/api-py/tests/security apps/api-py/esgapi/greenwash/tests apps/api-py/esgapi/runs/tests \
    | grep -E '^[-+][^-+]' | grep -E '== [0-9]+|69 \+ [0-9]+|# 분모|len\((REGISTRY\.flows_of|everything|NEEDS|COMPANY_WORK_OPERATIONS|found|operations|company|with_444|takers|names|work|targets|closed|authenticated|flows)' > "$S4/count-lines.txt"
  n=$(wc -l < "$S4/count-lines.txt" | tr -d ' ')
  echo "    움직인 셈 줄 $n (목록 $S4/count-lines.txt — 새 시험 파일의 == 는 셈 줄이 아니면 보고에 까닭)"
  report 3 "셈 줄" 0
fi

# 4. 옛 글 grep — 남은 곳을 찍는다(판단은 보고 표)
if want 4; then
  git -C "$ROOT" grep -n -E '8,000자|8천 자|도표 라벨 안 읽음|GE1c 전|a 도표 라벨은 옮기지 않음|charts=False' -- apps/api-py/esgapi/greenwash > "$S4/old-words.txt"
  echo "    옛 글 $(wc -l < "$S4/old-words.txt" | tr -d ' ')곳 (목록 $S4/old-words.txt)"
  report 4 "옛 글 grep(찍기만)" 0
fi

# 5. 정적 검사 + 순수 층(그린워싱). lock 이 있으면 돌리지 않는다
if want 5; then
  if [ -e "$MAIN_GIT/verify.lock" ]; then
    echo "    verify.lock 있음 — 돌리지 않음"
    report 5 "정적·순수" 2
  else
    e=0
    api ruff check esgapi/greenwash > "$S4/ruff.log" 2>&1 || e=1
    api ruff format --check esgapi/greenwash scripts > "$S4/format.log" 2>&1 || e=1
    api lint-imports > "$S4/lint-imports.log" 2>&1 || e=1
    api python scripts/check_test_layout.py > "$S4/layout.log" 2>&1 || e=1
    api pyright esgapi/greenwash > "$S4/pyright.log" 2>&1 || e=1
    api pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi/greenwash > "$S4/pure.log" 2>&1 || e=1
    tail -1 "$S4/pure.log" | sed 's/^/    순수 /'
    tail -1 "$S4/pyright.log" | sed 's/^/    pyright /'
    report 5 "정적·순수" "$e"
  fi
fi

# 6. 시험 약화 검사(BASE..HEAD)
if want 6; then
  (cd "$ROOT" && python3 scripts/check_test_weakening.py "$BASE" HEAD) > "$S4/weakening.log" 2>&1
  e=$?
  tail -2 "$S4/weakening.log" | sed 's/^/    /'
  report 6 "시험 약화" "$e"
fi

# 7. 금지어 ^+ 0 · 정답 문장 20자 겹침 0 (작업 트리 기준, 새 파일 포함)
if want 7; then
  # 새 파일도 diff 에 들게 임시 색인에만 add -N 한다(진짜 색인 0 바뀜)
  idx="$(mktemp)"; cp "$(git -C "$ROOT" rev-parse --git-path index)" "$idx"
  export GIT_INDEX_FILE="$idx"
  git -C "$ROOT" add -N -- apps/api-py/esgapi/greenwash apps/api-py/scripts 2>/dev/null
  git -C "$ROOT" diff "$BASE" -- . | grep -E '^\+[^+]' > "$S4/added.txt"
  hits=0
  for w in $WORDS; do
    [ -f "$w" ] || { echo "    !! 금지어 목록 없음: $w"; hits=$((hits + 1)); continue; }
    grep -v -E '^[[:space:]]*(#|$)' "$w" > "$S4/.words"
    k=$(grep -c -i -F -f "$S4/.words" "$S4/added.txt" || true)
    rm -f "$S4/.words"
    hits=$((hits + ${k:-0}))
  done
  ov=$(api python "$OVERLAP" "$ROOT" "$BASE" 2>&1 | tail -1)
  unset GIT_INDEX_FILE; rm -f "$idx"
  echo "    금지어 맞은 줄 $hits · $ov"
  case "$ov" in *"겹친 줄 0") o=0 ;; *) o=1 ;; esac
  report 7 "금지어·20자 겹침" "$([ "$hits" = 0 ] && [ "$o" = 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
