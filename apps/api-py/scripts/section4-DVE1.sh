#!/usr/bin/env bash
# 밴드 DVE1(MARC-TICK-390: 데이터 검증 엔진이 soft limit 을 다시 던짐 414 · reconcile job_summary 축 N1 436)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-DVE1.sh --part <1|2>   그 커밋 경계(스테이징을 그 커밋의 허용 목록에 견준다)
# 컨테이너 0 — -m "not django_db" 순수 시험만. AI 공급사 호출 0. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 1 로 끝난다.
set -u
cd "$(dirname "$0")/../../.."
B=568fb2cb
PART="${2:-}"
case "${1:-}:$PART" in --part:1 | --part:2) ;; *) echo "사용: $0 --part <1|2>" >&2; exit 2 ;; esac
A=apps/api-py
E="$A/esgapi"
DV="$E/dataverify"

FAILS=0
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}

ALLOWED_1='^apps/api-py/esgapi/dataverify/engines/colab_156/(dispatch|loop)\.py$|^apps/api-py/esgapi/dataverify/flows/colab_156\.py$|^apps/api-py/esgapi/dataverify/tests/engines/colab_156/test_(dispatch|loop)\.py$|^apps/api-py/esgapi/dataverify/tests/flows/test_colab_156_soft_deadline\.py$|^apps/api-py/scripts/(section4|planted-breaks)-DVE1\.sh$'
ALLOWED_2='^apps/api-py/esgapi/reconcile/tests/test_job_summary\.py$|^apps/api-py/scripts/(section4|planted-breaks)-DVE1\.sh$'
ALLOWED_ANY="$ALLOWED_1|$ALLOWED_2"
[ "$PART" = 1 ] && ALLOWED="$ALLOWED_1" || ALLOWED="$ALLOWED_2"
export ALLOWED ALLOWED_ANY B

# ① 스테이징이 그 커밋의 허용 목록 안이고 비지 않았다
run '[ -n "$(git diff --cached --name-only)" ] && ! git diff --cached --name-only | grep -v -E "$ALLOWED"'
# ② BASE 에서 바뀐 것(작업 트리 + 추적 안 된 새 파일)이 §1 허용 전체 안
run '! { git diff --no-renames --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u | grep -v -E "$ALLOWED_ANY"'
# ③ §1 0줄 자리: BASE 와 diff 0
run 'git diff --quiet "$B" -- '"$DV"'/contracts '"$DV"'/engines/colab_156/prompts.py '"$DV"'/engines/colab_156/schemas.py '"$DV"'/engines/colab_156/tools.py '"$DV"'/engines/colab_156/inputs.py '"$E"'/core '"$E"'/runs '"$E"'/reconcile ":(exclude)'"$E"'/reconcile/tests" '"$A"'/scripts/dataverify_compare_dump.py '"$A"'/.importlinter '"$A"'/pyproject.toml '"$DV"'/tests/engines/colab_156/test_purity.py '"$(git ls-files "$A" | grep conftest.py | tr "\n" " ")"
# ④ 기존 시험 파일(BASE 에 있던 dataverify 시험)의 diff 에 지운 줄 0
run '[ "$(git diff "$B" -- '"$DV"'/tests | grep -c "^-[^-]")" = 0 ]'
# ⑤ engines/colab_156 에 esgapi.core 문자열 0
run '! grep -rn "esgapi.core" '"$DV"'/engines/colab_156 --include=*.py'
# ⑥ 게이트
run 'cd '"$A"' && uv run --frozen pytest -q -p no:cacheprovider esgapi/dataverify/tests/engines/colab_156/test_purity.py'
run 'cd '"$A"' && uv run --frozen pytest -q -p no:cacheprovider esgapi/dataverify esgapi/reconcile -m "not django_db"'
CHANGED_PY="$(git diff --no-renames --name-only "$B" -- '*.py'; git ls-files --others --exclude-standard -- '*.py')"
CHANGED_PY="$(echo "$CHANGED_PY" | sed "s#^$A/##" | sort -u | tr '\n' ' ')"
export CHANGED_PY
run 'cd '"$A"' && uv run --frozen ruff check $CHANGED_PY'
run 'cd '"$A"' && uv run --frozen ruff format --check $CHANGED_PY'
run 'cd '"$A"' && uv run --frozen pyright $CHANGED_PY'
run 'cd '"$A"' && uv run --frozen lint-imports'

echo
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
