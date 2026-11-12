#!/usr/bin/env bash
# 심은 파손: 계약(.importlinter) 열일곱 전부(가~사 일곱, 아(그린워싱 축) 넷, 자(인벤토리 축) 다섯, 차(실행 층) 하나)마다 어기는 import 를 심고,
#   기대한 계약만 빨개지는지 계약 id 로 본다.
#   사용: apps/api-py/scripts/planted-breaks.sh
# 심기 전의 파일을 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다). 끝나면 작업 트리가 처음과 같아야 한다.
# 같은지는 스크립트가 스스로 잰다: 시작과 끝의 작업 트리 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
#   앞뒤를 견주는 것이라 커밋하지 않은 변경이 있는 트리에서도 돈다. 건드릴 파일의 목록에 기대지 않는다.
# 줄마다  <심은 것> → 깨진 계약의 id(정렬해 , 로 잇는다. 하나도 없으면 「없음」)  를 낸다(도구가 죽었으면 「죽음」). 마지막 줄 PLANTED= 이 기대와 같은 수/전체.
#   계약 이름 → id 의 정본은 .importlinter 다 — 돌 때마다 [importlinter:contract:<id>] 와 그 name = 을 읽는다(여기에 표를 두지 않는다).
#   이름에 맞춰지지 않는 BROKEN 줄은 ?<줄 앞 40자> 로 내어 「다름」이 된다.
# 종료 0 은 「PLANTED 가 다 맞음 ∧ 지문이 같음」일 때뿐이다.
# core 가 업무 모듈을 import 하면 runs → core → 업무 모듈 의 간접 사슬로 차(runs-knows-no-module)도 깨진다(차는 간접도 문다 — 1·26). core → runs 는 44 가 따로 잰다.
set -u
cd "$(dirname "$0")/.."

backup="$(mktemp -d)"
touched=()   # 고친 파일(되돌릴 것)
created=()   # 새로 만든 파일·폴더(지울 것)

restore() {
  for f in "${touched[@]:-}"; do [ -n "$f" ] && cp "$backup/$(echo "$f" | tr / _)" "$f"; done
  for f in "${created[@]:-}"; do [ -n "$f" ] && rm -rf "$f"; done
  touched=(); created=()
}
trap 'restore; rm -rf "$backup"' EXIT

append() { # <파일> <한 줄>
  cp "$1" "$backup/$(echo "$1" | tr / _)"; touched+=("$1")
  printf '\n%s\n' "$2" >> "$1"
}
create() { # <파일> <내용>   (없던 폴더는 __init__.py 와 함께 만든다)
  local dir; dir="$(dirname "$1")"
  local top="$dir"
  while [ ! -d "$(dirname "$top")" ]; do top="$(dirname "$top")"; done
  local fresh=0
  if [ ! -d "$dir" ]; then fresh=1; created+=("$top"); mkdir -p "$dir"; fi
  local d="$dir"
  while [ "$d" != "$(dirname "$top")" ]; do
    if [ ! -f "$d/__init__.py" ]; then
      : > "$d/__init__.py"
      [ "$fresh" -eq 1 ] || created+=("$d/__init__.py")   # 있던 폴더에 만든 것은 따로 지운다
    fi
    d="$(dirname "$d")"
  done
  # 이미 있는 파일이면(뒤 밴드가 그 자리에 파일을 만들었다) 지우지 않고 되돌린다: append 처럼 베껴 둔다.
  if [ -e "$1" ]; then cp "$1" "$backup/$(echo "$1" | tr / _)"; touched+=("$1"); else created+=("$1"); fi
  printf '%s\n' "$2" > "$1"
}

fingerprint() { # 작업 트리의 지문: 무엇이 바뀌었나(추적 안 되는 파일까지) + 추적 파일의 내용이 HEAD 와 어떻게 다른가
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
fingerprint > "$backup/.fingerprint-before"

ids=(); names=()   # 계약 id 와 그 이름(같은 차례)
cid=""
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    '[importlinter:contract:'*']') cid="${line#'[importlinter:contract:'}"; cid="${cid%']'}" ;;
    '['*) cid="" ;;
    'name ='*)
      if [ -n "$cid" ]; then
        line="${line#name =}"; line="${line#"${line%%[! ]*}"}"; line="${line%"${line##*[! ]}"}"
        ids+=("$cid"); names+=("$line"); cid=""
      fi ;;
  esac
done < .importlinter
if [ "${#ids[@]}" -eq 0 ]; then echo "★ .importlinter 에서 계약을 하나도 읽지 못했다"; exit 1; fi

broken() { # 깨진 계약의 id 를 정렬해 , 로 잇는다. 하나도 없으면 「없음」, 도구가 죽었으면 「죽음」
  # COLUMNS: lint-imports 가 긴 계약 이름을 두 줄로 접지 않게(접히면 KEPT/BROKEN 이 다음 줄로 간다).
  # 「죽음」: 출력에 `Contracts: ` 줄이 없다(예: `Module '…' does not exist.`). 계약을 재지 못한 것을 「없음」으로 세지 않는다.
  # 줄 꼴은 「<이름> BROKEN」(뒤에 「 (n ignored imports)」가 붙기도 한다) — 이름으로 시작하고 남은 것이 (공백을 걷고)
  # BROKEN 으로 시작하는 줄을 그 id 로 센다. `Contracts: ` 줄 뒤(깨진 계약의 풀이)는 보지 않는다.
  local out line rest i hit got=""
  out="$(COLUMNS=400 uv run --frozen lint-imports --no-cache 2>&1)"
  if ! printf '%s\n' "$out" | grep -q '^Contracts: '; then printf '죽음'; return; fi
  while IFS= read -r line; do
    case "$line" in 'Contracts: '*) break ;; *BROKEN*) ;; *) continue ;; esac
    hit=""
    for i in "${!ids[@]}"; do
      case "$line" in
        "${names[$i]}"*)
          rest="${line#"${names[$i]}"}"; rest="${rest#"${rest%%[! ]*}"}"
          case "$rest" in BROKEN*) hit="${ids[$i]}"; break ;; esac ;;
      esac
    done
    got="$got${hit:-?${line:0:40}}
"
  done <<EOF
$out
EOF
  got="$(printf '%s' "$got" | LC_ALL=C sort -u | paste -sd, -)"
  printf '%s' "${got:-없음}"
}

total=0; ok=0
check() { # <설명> <기대>
  local got; got="$(broken)"
  total=$((total + 1))
  if [ "$got" = "$2" ]; then ok=$((ok + 1)); mark="맞음"; else mark="★ 다름(기대 $2)"; fi
  printf '%-96s → %s  %s\n' "$1" "$got" "$mark"
  restore
}

check "0. 심지 않음" "없음"

# ── 계약 넷을 새 자리에서 어긴다 ──
append esgapi/core/conf.py "import esgapi.organization.service.services.organization"
check "1. core/conf.py 가 organization 의 service 를 import" "core-knows-no-module,runs-knows-no-module"

create esgapi/inventory/models.py "from esgapi.organization.models import Company"
check "2. inventory/models.py(새 파일)가 organization.models 를 import" "no-foreign-models"

append esgapi/user/service/utils/tokens.py "import django"
check "3. user/service/utils/tokens.py 에 import django (와일드카드 *.service.utils)" "pure-modules"

append esgapi/user/service/apis/user.py "from esgapi.user.models import User"
check "4. user/service/apis/user.py 가 자기 models 를 import (새 무늬 *.service.apis)" "api-knows-no-models"

append esgapi/user/api.py "from esgapi.user.models import User"
check "5. user/api.py(뿌리)가 자기 models 를 import (옛 무늬 *.api 가 뿌리에서 아직 문다)" "api-knows-no-models"

# ── 뒤 밴드가 만들 자리에도 걸리는가 (와일드카드와 「아직 없는 이름」) ──
create esgapi/inventory/calc/scope12.py "import django"
check "6. inventory/calc/scope12.py(새 파일)에 import django" "pure-modules"

create esgapi/reconcile/calc/rules/mask.py "import psycopg"
check "7. reconcile/calc/rules/mask.py(두 단계 아래)에 import psycopg" "pure-modules"

create esgapi/inventory/models.py "X = 1"
append esgapi/user/service/services/user.py "from esgapi.inventory.models import X"
check "8. user 의 service 가 inventory.models(새 파일)를 import (남의 도메인이기도 하다)" "no-foreign-models,services-stay-home"

create esgapi/inventory/models.py "X = 1"
append esgapi/inventory/service/apis/inventory.py "from esgapi.inventory.models import X"
check "9. inventory/service/apis/inventory.py 가 자기 모듈의 models(새 파일)를 import" "api-knows-no-models"

create esgapi/inventory/models.py "X = 1"
create esgapi/inventory/service/services/zz_planted.py "from esgapi.inventory.models import X"
create esgapi/organization/service/actions/zz_planted.py "from esgapi.inventory.service.services.zz_planted import X"
check "10. (어기지 않는 것) organization 의 Action(새 폴더)이 inventory 의 service 를 거쳐 models 에 닿는다" "없음"

create esgapi/inventory/service/utils/zz_planted.py "import django"
check "11. inventory/service/utils/zz_planted.py(새 폴더)에 import django (둘째 도메인에서도 와일드카드가 문다)" "pure-modules"

append esgapi/user/service/permissions/user.py "import django"
check "12. user/service/permissions/user.py 에 import django" "pure-modules"

append esgapi/core/resources/llm.py "import django"
check "13. core/resources/llm.py 에 import django" "pure-modules"

append esgapi/core/resources/ports/llm.py "import psycopg"
check "14. core/resources/ports/llm.py 에 import psycopg" "pure-modules"

append esgapi/core/service/apis/documents.py "from esgapi.core.models import DocumentRow"
check "15. core/service/apis/documents.py 가 core.models 를 import" "api-knows-no-models"

append esgapi/reconcile/tasks.py "from esgapi.runs.models import JobRow"
check "16. reconcile/tasks.py 가 runs.models 를 import (*.tasks 그대로. 남의 models 이기도 하다 — 나)" "api-knows-no-models,no-foreign-models"

# ── 새 계약 마: 두 표면은 서로를 모른다 ──
append esgapi/reference/admin/services/importer.py "import esgapi.reference.service.selectors.reference"
check "17. reference 의 admin 이 service 를 import" "surfaces-apart"

append esgapi/reference/service/services/reference.py "import esgapi.reference.admin.services.importer"
check "18. reference 의 service 가 admin 을 import" "surfaces-apart"

# ── 새 계약 바: Service·Selector 는 남의 도메인을 모른다. 권한 표는 순수하고 업무 모듈을 모른다 ──
append esgapi/user/service/selectors/user.py "import esgapi.reference.service.selectors.reference"
check "19. user 의 Selector 가 reference 의 Selector 를 import" "services-stay-home"

append esgapi/reference/service/services/reference.py "from esgapi.inventory.engines.scope12.engine_1 import types"
check "20. reference 의 Service 가 inventory 의 calc 를 import (남의 calc 도 문다)" "services-stay-home"

append esgapi/reference/admin/services/importer.py "import esgapi.user.service.services.user"
check "21. reference 의 admin Service 가 user 의 Service 를 import (admin 무늬)" "services-stay-home"

append esgapi/inventory/service/services/inventory.py "from esgapi.reference.service.selectors import reference"
check "22. inventory 의 Service 가 reference 의 Selector 를 import (걷은 그 줄을 되심는다)" "services-stay-home"

append esgapi/inventory/service/actions/scope3_shortlist.py "import esgapi.user.service.selectors.user"
check "23. (어기지 않는 것) inventory 의 Action 이 user 의 Selector 를 import" "없음"

create esgapi/reconcile/service/selectors/zz_planted.py "import esgapi.user.service.selectors.user"
check "24. reconcile/service/selectors/zz_planted.py(새 폴더)가 user 의 Selector 를 import (없던 폴더에도 와일드카드가 문다)" "services-stay-home"

append esgapi/core/permissions.py "import django"
check "25. core/permissions.py 에 import django (다의 새 줄 esgapi.core.permissions)" "pure-modules"

append esgapi/core/permissions.py "import esgapi.user.service.permissions.user"
check "26. core/permissions.py 가 user 의 permissions 를 import" "core-knows-no-module,runs-knows-no-module"

# ── 새 계약 사: 시험 밖 코드는 시험을 모른다(wheel 에 tests 가 없다) ──
#   심는 것은 있는 모듈이어야 한다 — 없는 모듈을 import 하면 grimp 가 그 줄을 세지 않아 「없음」이 된다(IL1 실측).
append esgapi/organization/service/services/organization.py "import esgapi.core.tests.resource_fakes"
check "27. organization 의 Service 가 core.tests.resource_fakes 를 import (남의 도메인의 시험)" "product-knows-no-tests"

append esgapi/user/api.py "import esgapi.user.tests"
check "28. user/api.py 가 자기 tests 패키지(뿌리 __init__)를 import" "product-knows-no-tests"

append esgapi/inventory/tests/conftest.py "import esgapi.core.tests.resource_fakes"
check "29. (어기지 않는 것) inventory 의 시험이 core 의 시험 도구를 import (ignore 한 줄)" "없음"

# ── 새 계약 자 넷(인벤토리 축, 밴드 EN1): 머리글자가 넷 다 「자」라 계약 id 로 가른다 ──
append esgapi/inventory/contracts/shapes.py "from esgapi.inventory.engines.scope12.engine_1 import types"
check "30. 인벤토리 계약(contracts/shapes.py)이 엔진 Scope 1·2 의 types 를 import" "inventory-contracts-not-engines"

append esgapi/inventory/engines/scope3/llm_first_1/memory.py "from esgapi.inventory.contracts import shapes"
check "31. 인벤토리 엔진(scope3 memory.py)이 계약 shapes 를 import" "inventory-engine-not-contracts"

append esgapi/inventory/tools/jsrepr.py "import esgapi.inventory.engines.scope12.engine_1.units"
check "32. 인벤토리 도구(tools/jsrepr.py)가 엔진을 import (scope3 엔진 → 도구 → scope12 엔진 의 간접 사슬도)" "inventory-engines-apart,inventory-tools-know-no-axis"

append esgapi/inventory/engines/scope3/llm_first_1/memory.py "from esgapi.inventory.engines.scope12.engine_1 import units"
check "33. 인벤토리 엔진 scope3 이 엔진 scope12 를 import (흐름끼리의 엔진)" "inventory-engines-apart"

# ── 아 넷(그린워싱 축, 밴드 GX1 의 P5~P8)과 그 엔진·도구의 순수(P9·P10) ──
append esgapi/greenwash/contracts/shapes.py "from esgapi.greenwash.engines.e0 import wordcount"
check "34. 그린워싱 계약(contracts/shapes.py)이 엔진 e0 의 wordcount 를 import" "greenwash-contracts-not-engine"

append esgapi/greenwash/engines/e0/parts.py "from esgapi.greenwash.contracts import shapes"
check "35. 그린워싱 엔진(e0/parts.py)이 계약 shapes 를 import" "greenwash-engine-not-contracts"

append esgapi/greenwash/outputs/xlsx.py "from esgapi.greenwash.engines.e0 import gw1"
check "36. 그린워싱 출력(outputs/xlsx.py)이 엔진 e0 의 gw1 을 import" "greenwash-outputs-not-engine"

append esgapi/greenwash/tools/textnorm.py "import esgapi.greenwash.engines.e0.heuristics"
check "37. 그린워싱 도구(tools/textnorm.py)가 엔진 e0 의 heuristics 를 import" "greenwash-tools-know-no-axis"

append esgapi/greenwash/engines/e0/retrieval.py "import django"
check "38. 그린워싱 엔진(e0/retrieval.py)에 import django" "pure-modules"

append esgapi/greenwash/tools/coordinates.py "import django"
check "39. 그린워싱 도구(tools/coordinates.py)에 import django" "pure-modules"

# ── 자 축의 나머지(밴드 EN1 의 P5~P7) ──
append esgapi/inventory/engines/scope12/engine_1/units.py "from esgapi.inventory.flows import registration"
check "40. 인벤토리 엔진 scope12(units.py)가 흐름 registration 을 import (흐름 → scope3 엔진 의 간접 사슬도)" "inventory-engine-not-contracts,inventory-engines-apart"

append esgapi/inventory/tools/scope3_sheets/grid.py "import django"
check "41. 인벤토리 도구(tools/scope3_sheets/grid.py)에 import django" "pure-modules"

append esgapi/inventory/engines/scope12/engine_1/units.py "import django"
check "42. 인벤토리 엔진 scope12(units.py)에 import django" "pure-modules"

# ── 새 계약 차(실행 층 runs, 밴드 X1a): runs 는 업무 모듈을 모른다 ──
append esgapi/runs/apps.py "import esgapi.greenwash"
check "43. runs/apps.py 가 greenwash 를 import" "runs-knows-no-module"

append esgapi/core/conf.py "import esgapi.runs.service.apis.runs"
check "44. core/conf.py 가 runs 의 경로를 import (가 의 금지 목록 runs)" "core-knows-no-module"

append esgapi/core/conf.py "from esgapi.runs.models import JobRow"
check "45. core/conf.py(시험 아닌 core 파일)가 runs.models 를 import (가 의 시험 ignore 가 제품을 풀지 않는다)" "core-knows-no-module"

# ── 자 다섯째(Scope 3 엔진의 판끼리, 밴드 S3C-a): 코랩 판이 LLM 먼저 판을 import ──
append esgapi/inventory/engines/scope3/colab_157/purchase.py "import esgapi.inventory.engines.scope3.llm_first_1.types"
check "46. 인벤토리 엔진 scope3 의 판 colab_157(purchase.py)이 판 llm_first_1 을 import" "inventory-scope3-versions-apart"

# ── 끝 검사: 되돌린 뒤의 작업 트리가 처음과 같은가 ──
restore
fingerprint > "$backup/.fingerprint-after"
same=1
if ! diff "$backup/.fingerprint-before" "$backup/.fingerprint-after" > "$backup/.fingerprint-diff"; then
  same=0
  echo "★ 작업 트리가 처음과 다르다(< 처음, > 지금):"
  cat "$backup/.fingerprint-diff"
fi

echo "PLANTED=$ok/$total"
[ "$ok" -eq "$total" ] && [ "$same" -eq 1 ]
