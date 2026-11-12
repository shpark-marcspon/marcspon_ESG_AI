#!/usr/bin/env bash
# S12S1 의 심은 파손(발주서 band-handoffs/S12S1-order.md §4): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S12S1.sh [--only P<n>]
# 틀은 planted-breaks-K1b-2b.sh: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 —
#   checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다(§ 로 여러 자리). 아니면 「못 심음」이고 실패로 센다.
# 빨강 = 그 명령의 종료 1(pytest 수집 실패 2·4 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」면 업무 층(이 워크트리의
#   compose postgres), 「pure:」면 순수 층, 「s4:」면 section4-S12S1.sh --only <이름>.
# .git/verify.lock(디렉터리)이 있으면 심기 전마다 멈춘다(종료 2). 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>
#   FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다. macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I.
set -u
cd "$(dirname "$0")/.."
MAIN="$(git rev-parse --path-format=absolute --git-common-dir)"
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done

I=esgapi/inventory
D=$I/data/ghg-pool-seed.json
GA=$I/service/actions/ghg_pool.py
CMD=$I/management/commands/retire_ghg_seed.py
TU=$I/tests/service/utils/test_ghg_pool_seed.py
TI=$I/tests/service/utils/test_ghg_pool_seed_ids.py
TR=$I/tests/service/actions/test_ghg_pool_retire.py
ST=esgapi/core/tests/isolation/test_static_rules.py

backup="$(mktemp -d /private/tmp/s12s1-planted.XXXXXX)"
case "$backup" in /private/tmp/s12s1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈, § 로 여러 자리)
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
path, olds, news = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
for old, new in zip(olds.split("§"), news.split("§"), strict=True):
    if text.count(old) != 1:
        print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
        sys.exit(1)
    text = text.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(text)
PYEOF
}

check() {  # check <시험 칸> — 0 초록 · 1 빨강 · 그 밖 죽음
  local spec="$1" kind="${1%%:*}" target="${1#*:}"
  case "$kind" in
    pure) uv run --frozen pytest -q -x -p no:randomly "$target" > "$backup/log" 2>&1 ;;
    biz) ./scripts/test-business.sh -q -x -p no:randomly "$target" > "$backup/log" 2>&1 ;;
    s4) bash scripts/section4-S12S1.sh --only "$target" > "$backup/log" 2>&1 ;;
    *) echo "모르는 시험 칸: $spec" >&2; return 9 ;;
  esac
}

planted=0; red=0
row() {  # row <번호> <설명> <파일> <옛> <새> <시험 칸>
  local id="$1" what="$2" file="$3" old="$4" new="$5" test="$6"
  if [ -n "$ONLY" ] && [ "$ONLY" != "$id" ]; then return; fi
  if [ -e "$MAIN/verify.lock" ]; then echo "lock 있음 — 멈춤"; exit 2; fi
  planted=$((planted + 1))
  cp "$file" "$backup/keep"; current="$file"
  if ! plant "$file" "$old" "$new"; then
    echo "$id 못 심음 — $what"; restore; return
  fi
  check "$test"; local code=$?
  restore
  cmp -s "$file" "$backup/keep" || { echo "$id 되돌림 실패: $file"; exit 1; }
  local failed
  failed=$(grep -E "^(FAILED|ERROR) " "$backup/log" | head -1 | cut -c1-150)
  if [ "$code" -eq 1 ]; then
    red=$((red + 1)); echo "$id 빨강 — $what · ${failed:-$(tail -1 "$backup/log" | cut -c1-120)}"
  elif [ "$code" -eq 0 ]; then
    echo "$id 초록(놓침) — $what · $test"
  else
    echo "$id 죽음(종료 $code) — $what · $(tail -1 "$backup/log" | cut -c1-120)"
  fi
}

row P1 "잎 하나의 낱줄 id 한 글자 바꿈(대조 시험)" "$D" '"gir-2024:main:r3"' '"gir-2024:main:r9"' "pure:$TI"
row P2 "잎 코드를 연료 이름으로 되돌림" "$D" '"name": "경유",\n       "facilities": [\n        {\n         "code": "비상발전기"' \
  '"name": "경유",\n       "facilities": [\n        {\n         "code": "경유"' "pure:$TU"
row P3 "새 활동 열쇠를 옛 열쇠 liquid 로(R9 겹침)" "$D" '"key": "diesel"' '"key": "liquid"' "pure:$TU"
row P4 "기본(셈만)이 지움" "$GA" 'if not apply or report.state != "ready":' 'if report.state != "ready":' "biz:$TR"
row P5 "쓰임 셈 뺌(nodes_in_use 안 부름)" "$GA" 'leaves_in_use=len(nodes_in_use(leaves)),' 'leaves_in_use=0,' "biz:$TR"
row P6 "factors_in_use 뺌" "$GA" 'factors_in_use=len(factors_in_use([mark.id for mark in marks])),' 'factors_in_use=0,' "biz:$TR"
row P7 "고친 씨앗 계수 셈 뺌" "$GA" 'edited_factors=sum(mark.seeded and mark.current_version >= 2 for mark in marks),' \
  'edited_factors=0,' "biz:$TR"
row P8 "씨앗 밖 자식 셈 뺌" "$GA" 'foreign_children=sum(len(found - set(alive)) for found in children.values()),' \
  'foreign_children=0,' "biz:$TR"
row P9 "blocked 인데 지움" "$GA" 'if not apply or report.state != "ready":' 'if not apply or report.state == "nothing":' "biz:$TR"
row P10 "이미 지운 것도 넘김(404)" "$GA" \
  'alive = sorted(node_id for node_id, deleted in found.values() if not deleted)§alive = sorted(selectors.lock_nodes(alive))' \
  'alive = sorted(node_id for node_id, _ in found.values())§selectors.lock_nodes(alive)' "biz:$TR"
row P11 "범위·유형 노드까지 지움" "$GA" 'actor_kind=actor_kind, ids=alive, nodes_in_use' \
  'actor_kind=actor_kind, ids=[*alive, *(n.parent_id for n in selectors.alive_nodes(alive).values() if n.parent_id and n.level == "activity")], nodes_in_use' \
  "biz:$TR"
row P12 "다른 잎이 쓰는 코드도 지움" "$GA" 'kept = selectors.codes_on_other_leaves(alive_old_codes, except_ids=alive)' \
  'kept: frozenset[int] = frozenset()' "biz:$TR"
row P13 "사업장이 쓰는 코드 지움(셈 뺌 + 판정 빈 집합)" "$GA" \
  'codes_on_sites=len(codes_on_sites(codes)) if codes else 0,§facility_codes_in_use=codes_on_sites)' \
  'codes_on_sites=0,§facility_codes_in_use=lambda ids: frozenset())' "biz:$TR"
row P14 "셈 줄에 회사 id" "$CMD" 'f"옛 씨앗 노드 살아 있음 {report.alive}' 'f"회사 id 7 · 옛 씨앗 노드 살아 있음 {report.alive}' "biz:$TR"
row P15 "명령이 입구를 바로 부름(7a ④ — ST :1037 이 잡아야)" "$CMD" \
  'codes_on_sites=codes_on_site_facilities§from esgapi.organization.service.selectors.facility_codes import codes_on_site_facilities' \
  'codes_on_sites=SiteFacility.used_code_ids§from esgapi.organization.models import SiteFacility' "pure:$ST"
row P16 "지울 옛 코드만 남은 때를 nothing 으로(러너 표 밖)" "$GA" '"ready" if alive or codes else "nothing"' '"ready" if alive else "nothing"' "biz:$TR"
row P17 "셈이 노드 잠금 앞(retire_seed 의 lock_nodes 뺌 — 덧 3, 검증 B1 L1)" "$GA" \
  '    if apply:  # 셈 전에 잠근다(덧 3) — 그 아래 만들기·고르기·지우기와 줄을 선다(기다린 사이 지운 것은 빠진다)\n        alive = sorted(selectors.lock_nodes(alive))\n' \
  '' "biz:$TR"
row P18 "계수 잠금 뺌(lock_factor 고리 — 검증 B1 L2)" "$GA" '        for mark in marks:\n            selectors.lock_factor(mark.id)\n' \
  '        pass\n' "biz:$TR"
row P19 "거절을 모두 blocked 로(가지 리뷰 MINOR1)" "$CMD" '"RETIRE=blocked" if used else f"RETIRE=refused {type(report).__name__}"' \
  '"RETIRE=blocked"' "biz:$TR"
row X1 "경유 잎 단위 L→kg(검증 권고 R1 — UNITS 대조)" "$D" \
  '"code": "비상발전기",\n         "unit": {\n          "kind": "volume",\n          "unit": "L"\n         },\n         "factors": [\n          {\n           "key": "manufacturing_construction",\n           "name": "경유' \
  '"code": "비상발전기",\n         "unit": {\n          "kind": "mass",\n          "unit": "kg"\n         },\n         "factors": [\n          {\n           "key": "manufacturing_construction",\n           "name": "경유' \
  "s4:units"

after="$(fingerprint)"
same=same
if [ "$before" != "$after" ]; then same=differs; diff <(printf '%s\n' "$before") <(printf '%s\n' "$after"); fi
echo "PLANTED=$red/$planted FINGERPRINT=$same"
[ "$red" -eq "$planted" ] && [ "$same" = same ]
