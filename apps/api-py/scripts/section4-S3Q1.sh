#!/usr/bin/env bash
# 밴드 S3Q1 §4 손 검사: (가) BASE ↔ 지금 트리의 엔진 결과 글자 같음 (나) 0줄 자리·셈 줄 grep.
#   사용: apps/api-py/scripts/section4-S3Q1.sh [BASE]   (기본 BASE 7f374bde)
# (가) `git archive BASE apps/api-py` 를 임시 폴더에 풀어 BASE 의 esgapi 로, 지금 트리의 esgapi 로 같은 지어낸 템플릿
#     (C12 갈래 넷·흠 두 줄·차례가 갈리는 비중 + C3·C8 에너지 줄 — 짓개, 실제 책·기업 0)을 같은 지어낸 계수 책으로 돌려
#     result_to_dict 를 견준다. 지금 쪽에서 줄의 `treatments` 키만 빼면 BASE 와 JSON 글자째 같아야 한다(MARC-ENT-442).
#     LLM 은 모의(test 지원의 ColabReplies) — 공급사 호출 0. 저장소·DB 0.
# (나) 발주서 §4 의 0줄 grep. 끝 줄 SECTION4=PASS|FAIL.
set -u
cd "$(dirname "$0")/../../.."
BASE="${1:-7f374bde}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fail=0

git archive "$BASE" apps/api-py | tar -x -C "$tmp"
cat > "$tmp/dump.py" <<'PY'
import json
import sys

import django

django.setup()  # 시험 지원 모듈이 ninja 꼴을 들인다(DJANGO_SETTINGS_MODULE — 시험 설정, DB 0)

from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.tests.engines.scope3.colab_157.support import c12_sheet
import esgapi
from esgapi.inventory.tests.engines.scope3.colab_157 import test_energy_sheet as energy
from esgapi.inventory.tests.engines.scope3.colab_157.test_product_eol_sheet import PAPER, ROWS, row, run_on

print(f"esgapi = {esgapi.__file__}", file=sys.stderr)

c12 = (
    *ROWS,
    row("99 | 가상 없음", "선택안함", "선택안함", "가상물건", 900, 1, "kg", (90, 9, 9)),
    row(*PAPER, "가상종이판", 900, 1, "kg", (0, 0, 0)),
    row(*PAPER, "가상종이컵", 960, 0.9, "kg", (90, 9, None)),
    row(*PAPER, "가상종이봉투", 950, 0.99, "g", (None, None, None)),
    row("92 | 가상 사업장", "92-01 | 가상 수지", "92-01-01 | 가상 폐수지 묶음", "가상수지병", 900, 1, "kg", (95, 3, 2)),
)
schema = "scope3.colab.result@1"
results = [
    result_to_dict(run_on([c12_sheet("c12_판매제품폐기", *c12)]), schema),
    result_to_dict(energy.run_on([energy.c3_sheet("c3_연료에너지", *energy.C3_ROWS)]), schema),
]
if sys.argv[1] == "head":
    for result in results:
        for sheet in result["sheets"]:
            for one in sheet.get("rows", []):
                one.pop("treatments", None)
print(json.dumps(results, ensure_ascii=False, sort_keys=False))
PY
dump() { # <esgapi 뿌리> <base|head> <출력>
  (cd apps/api-py && PYTHONPATH="$1" PYTHONDONTWRITEBYTECODE=1 DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python "$tmp/dump.py" "$2" > "$3" 2> "$3.err") \
    || { echo "dump 실패($2):"; tail -5 "$3.err"; fail=1; }
}
dump "$tmp/apps/api-py" base "$tmp/base.json"
dump "$PWD/apps/api-py" head "$tmp/head.json"
if [ "$fail" -eq 0 ] && cmp -s "$tmp/base.json" "$tmp/head.json"; then
  grep -h '^esgapi = ' "$tmp/base.json.err" "$tmp/head.json.err" | sed 's/^/    /'
  echo "(가) 엔진 결과 BASE ↔ 지금(treatments 뺌) 글자 같음 · sha16 $(shasum -a 256 "$tmp/base.json" | cut -c1-16) · $(wc -c < "$tmp/base.json") 바이트"
else
  echo "(가) ★ 엔진 결과가 다르다"; diff <(tr ',' '\n' < "$tmp/base.json") <(tr ',' '\n' < "$tmp/head.json") | head -20; fail=1
fi

zero() { # <이름> <명령 출력의 수> <기대>
  if [ "$2" = "$3" ]; then echo "(나) $1 = $2"; else echo "(나) ★ $1 = $2 (기대 $3)"; fail=1; fi
}
P=apps/api-py/esgapi
zero "same-factor 시험 diff 줄" "$(git diff "$BASE" -- $P/inventory/tests/service/utils/test_scope3_factors_same.py | wc -l | tr -d ' ')" 0
zero "product.py 셈 줄(+/-)" "$(git diff "$BASE" -- $P/inventory/engines/scope3/colab_157/product.py | grep -E '^[-+]' | grep -E 'weighted_ef \+=|emission =|_pct\(|WASTE_AVG_EF\[' | wc -l | tr -d ' ')" 0
zero "엔진 셈 파일·data·runs·config/api·importlinter·의존·scope3_factors" "$(git diff "$BASE" -- $P/inventory/engines/scope3/colab_157/{waste,energy,factor_book}.py $P/inventory/data $P/runs $P/config/api.py apps/api-py/.importlinter apps/api-py/pyproject.toml apps/api-py/uv.lock $P/inventory/service/utils/scope3_factors.py | wc -l | tr -d ' ')" 0
zero "core 제품 코드(permissions.py 밖)" "$(git diff --name-only "$BASE" -- $P/core | grep -v '/tests/' | grep -v '^apps/api-py/esgapi/core/permissions.py$' | wc -l | tr -d ' ')" 0
zero "core/permissions.py 바뀐 줄" "$(git diff "$BASE" -- $P/core/permissions.py | grep -E '^[-+][^-+]' | wc -l | tr -d ' ')" 1
zero "웹 shared·app·widgets·packages·의존·visual" "$(git diff "$BASE" -- apps/web/src/shared apps/web/src/app apps/web/src/widgets packages apps/web/package.json pnpm-lock.yaml apps/web/e2e/visual.spec.ts apps/web/e2e/visual-baseline.ts | wc -l | tr -d ' ')" 0
zero "경로 밖(permits 의 core/config/security 시험 포함)" "$(git diff --name-only "$BASE" | grep -vE '^apps/(api-py/(esgapi/(inventory/|core/permissions\.py$|core/tests/test_permissions(_wiring)?\.py$|config/tests/test_api_(contract|errors)\.py$)|tests/security/test_(tenant_paths|login|operator_company)\.py$|generated/|scripts/(planted-breaks|section4)-S3Q1\.sh$)|web/(src/(entities|pages)/ghg-scope3/|e2e/ghg-scope3-server(\.spec)?\.ts$))' | wc -l | tr -d ' ')" 0

echo "SECTION4=$([ "$fail" -eq 0 ] && echo PASS || echo FAIL)"
[ "$fail" -eq 0 ]
