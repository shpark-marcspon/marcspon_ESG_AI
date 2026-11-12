#!/usr/bin/env bash
# 밴드 S12S1(MARC-TICK-611 — S12-06 샘플 교체: 씨앗 나무 + 옛 씨앗 셈·지우기 명령)의 §4 자기검증
# (발주서 band-handoffs/S12S1-order.md §4 · 덧 4).
#   사용: apps/api-py/scripts/section4-S12S1.sh [--only <이름>] [--with-containers]
#   --with-containers 면 test-business(compose postgres)·verify --fast 도 돈다. 안 주면 그 둘은 「안 돌림」(실패로 셈).
#   --only units|retired|ids 는 그 대조 하나만(심은 파손 X1 이 부른다 — DB·네트워크 0).
# 단계마다 「[이름] EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. 기준 B = 발주서 BASE f5bf4597(S4_BASE 로 바꿈) — ① 이 먼저
#   main 에 병합(8754cba8)돼 merge-base 는 ① 커밋이라 쓰지 않는다(옛 씨앗과 견줄 수 없음).
# .git/verify.lock(디렉터리)이 있으면 시험을 하나도 돌리지 않고 종료 2(러너 공통 §5).
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I(표준 라이브러리만). LLM·네트워크 0(gen-ts-types 의 pnpm dlx 만 네트워크).
set -u
cd "$(dirname "$0")/.."
API="$(pwd)"
MAIN="$(git rev-parse --path-format=absolute --git-common-dir)"
B="${S4_BASE:-f5bf4597}"
I=esgapi/inventory
D=$I/data/ghg-pool-seed.json
ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
FAIL=0
locked() { [ -e "$MAIN/verify.lock" ]; }
step() {  # step <이름> <명령…>
  local name="$1"; shift
  if locked; then echo "[$name] lock 있음 — 멈춤"; exit 2; fi
  local start=$SECONDS
  "$@"
  local code=$?
  echo "[$name] EXIT=$code $((SECONDS - start))s"
  [ "$code" -eq 0 ] || FAIL=$((FAIL + 1))
}

compare() {  # compare units|retired|ids — BASE 씨앗(git show B:)과 지금 씨앗의 대조
  git show "$B:apps/api-py/$D" > "${TMPDIR:-/private/tmp}/s12s1-base-seed.$$.json" || return 1
  python3 -I - "$1" "${TMPDIR:-/private/tmp}/s12s1-base-seed.$$.json" "$D" <<'PYEOF'
import json, sys
what, base_path, new_path = sys.argv[1:4]
base, new = (json.load(open(path, encoding="utf-8")) for path in (base_path, new_path))

def walk(plan):
    for scope in plan["tree"]:
        for kind in scope["children"]:
            for act in kind["children"]:
                for leaf in act["facilities"]:
                    yield scope, kind, act, leaf

def ids(plan):
    found = set()
    for *_, leaf in walk(plan):
        for spec in leaf["factors"]:
            found |= set(spec["gases"].values()) | ({spec["ncv"]} if "ncv" in spec else set())
    return found

if what == "ids":  # 낱줄 id 집합 BASE == 새(수치 지음 0)
    same = ids(base) == ids(new) and len(ids(new)) > 0
    print(f"IDS={'same' if same else 'differs'} {len(ids(new))}")
elif what == "retired":  # 새 retired == BASE 의 옛 활동 3·잎 23 열쇠
    old = [f"{s['key']}/{k['key']}/{a['key']}" for s in base["tree"] if s["key"] == "scope1" for k in s["children"] for a in k["children"]]
    old += [f"{s['key']}/{k['key']}/{a['key']}/{leaf['code']}" for s, k, a, leaf in walk(base)]
    same = sorted(old) == sorted(new.get("retired", [])) and len(old) == 26
    print(f"RETIRED={'same' if same else 'differs'} {len(new.get('retired', []))}")
elif what == "units":  # 덧 4: 연료(BASE 잎 code = 새 활동 이름) → 잎 단위가 같음 · 전력 잎 단위도
    def by_fuel(plan, fuel_of):
        return {fuel_of(s, a, leaf): (leaf["unit"]["kind"], leaf["unit"]["unit"]) for s, _, a, leaf in walk(plan)}
    old = by_fuel(base, lambda s, a, leaf: leaf["code"] if s["key"] == "scope1" else s["key"])
    now = by_fuel(new, lambda s, a, leaf: a["name"] if s["key"] == "scope1" else s["key"])
    same = old == now and len(now) == 23
    print(f"UNITS={'same' if same else 'differs'} {len(now)}")
    for key in sorted(set(old) | set(now)):
        if old.get(key) != now.get(key):
            print(f"  다름 {key}: {old.get(key)} → {now.get(key)}")
sys.exit(0 if same else 1)
PYEOF
  local code=$?
  rm -f "${TMPDIR:-/private/tmp}/s12s1-base-seed.$$.json"
  return $code
}

if [ -n "$ONLY" ]; then
  case "$ONLY" in units|retired|ids) compare "$ONLY"; exit $? ;; *) echo "--only units|retired|ids" >&2; exit 2 ;; esac
fi

echo "BASE $B · HEAD $(git rev-parse --short HEAD)"
if locked; then echo "lock 있음 — 시험 0"; exit 2; fi
echo "lock 없음 확인 $(date +%H:%M:%S)"

zero_land() {  # 2-2 의 0줄 땅
  local n
  n=$(git diff "$B" --name-only -- $I/models.py $I/migrations $I/engines $I/contracts $I/tools $I/flows $I/calc $I/api.py \
      $I/service/utils $I/service/services $I/service/apis esgapi/reference esgapi/config esgapi/runs esgapi/tests/security \
      .importlinter pyproject.toml uv.lock generated ../web ../../packages ../../deploy ../../infra | wc -l | tr -d ' ')
  echo "0줄 땅 바뀐 파일 $n"; [ "$n" -eq 0 ]
}
others_land() {  # OR·core 는 허락한 자리만(7a — Q9 (가))
  local bad
  bad=$(git diff "$B" --name-only -- esgapi/organization esgapi/core | grep -vE '^apps/api-py/esgapi/(organization/models\.py|organization/service/selectors/facility_codes\.py|organization/tests/.*|core/tests/isolation/test_static_rules\.py)$')
  echo "허락 밖 OR·core: ${bad:-0}"; [ -z "$bad" ]
}
placeholder_kept() {  # facility_codes_in_use 몸 0줄
  local n
  n=$(git diff "$B" -- esgapi/organization/service/selectors/facility_codes.py | grep -A3 "def facility_codes_in_use" | grep -c '^[-+]')
  echo "facility_codes_in_use 바뀐 줄 $n"; [ "$n" -eq 0 ]
}
st_lines() {  # ST 는 허락 여섯 자리(각 줄 「S12S1 Q9 +1」) — 바뀐 줄의 S12S1 표지를 센다
  local n
  n=$(git diff "$B" -- esgapi/core/tests/isolation/test_static_rules.py | grep '^+[^+]' | grep -c 'S12S1 Q9 +1')
  echo "ST 표지 줄 $n(기대 6)"; [ "$n" -eq 6 ]
}
generated_zero() {
  ./scripts/gen-ts-types.sh > /dev/null 2>&1 || return 1
  local n
  n=$(git diff --stat -- generated | wc -l | tr -d ' ')
  echo "generated 바뀐 줄 $n"; [ "$n" -eq 0 ]
}
r7_once() {
  local n
  n=$(grep -c '"gir-2025:main:r7"' "$D")
  echo "gir-2025:main:r7 $n"; [ "$n" -eq 1 ]
}
old_words() {  # 옛 글 grep — 서버 글이 바뀜(남의 시험·문서가 옛 것을 단언하는지)
  local hits
  hits=$(grep -rnE "시설 코드 이름 = 연료 이름|22 연료 × 부문|구매 전력 열하나|고체연료 연소|액체연료 연소|기체연료 연소" \
    esgapi ../../docs ../web/src ../web/e2e 2>/dev/null | grep -v "/tests/.*지어낸")
  echo "옛 글 남은 자리 $(printf '%s' "$hits" | grep -c .)"; [ -n "$hits" ] && printf '%s\n' "$hits"
  [ -z "$hits" ]
}
count_asserts() {  # 바뀐 단언 자리만(보고에) — 종료는 늘 0
  grep -rnE "== *(31|50|99)\b|\(31, *99\)|\(50, *99\)|\(23, *99\)" esgapi | grep "\.py:" ; return 0
}
test_counts() {  # 2-3 셈 줄 — 줄지 않음(BASE 8·2·8·13·6·OR 6)
  local ok=0 path base now
  for pair in "$I/tests/service/utils/test_ghg_pool_seed.py:8" "$I/tests/service/utils/test_ghg_pool_seed_ids.py:2" \
              "$I/tests/service/actions/test_ghg_pool_seed.py:8" "$I/tests/service/actions/test_ghg_pool.py:13" \
              "$I/tests/service/actions/test_ghg_pool_in_use.py:6" \
              "esgapi/organization/tests/service/services/test_facility_codes.py:6"; do
    path="${pair%:*}"; base="${pair##*:}"; now=$(grep -cE "^def test_" "$path")
    echo "  $path $base → $now"; [ "$now" -ge "$base" ] || ok=1
  done
  return $ok
}

step pytest-band uv run --frozen pytest -m "not django_db" esgapi/inventory esgapi/organization esgapi/core/tests/isolation -q -n 2
step importlinter uv run --frozen lint-imports
step test-layout uv run --frozen python scripts/check_test_layout.py
step pyright uv run --frozen pyright esgapi/inventory esgapi/organization esgapi/core/tests/isolation
step generated generated_zero
step zero-land zero_land
step others-land others_land
step placeholder placeholder_kept
step st-six st_lines
step retired compare retired
step ids compare ids
step units compare units
step r7 r7_once
step old-words old_words
step count-asserts count_asserts
step test-counts test_counts
if [ "$CONTAINERS" -eq 1 ]; then
  step test-business ./scripts/test-business.sh -n 2 -q
  step verify-fast bash -c 'cd ../.. && scripts/verify.sh --fast'
else
  echo "[test-business] 안 돌림(--with-containers 없음)"; FAIL=$((FAIL + 1))
  echo "[verify-fast] 안 돌림(--with-containers 없음)"; FAIL=$((FAIL + 1))
fi
echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
