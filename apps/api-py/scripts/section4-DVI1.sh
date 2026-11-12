#!/usr/bin/env bash
# 밴드 DVI1(MARC-TICK-424 · MARC-ISSUE-442 — 실행 목록 jsonb 투영의 \u0000·외톨이 서로게이트)의 §4 자기검증(정적 몫).
#   사용(어디서든): apps/api-py/scripts/section4-DVI1.sh [--cached]
#     --cached  스테이징 판(커밋 전)을 본다. 없으면 BASE..작업 트리(커밋 뒤에도 같은 답) + 추적 안 된 새 파일.
# 확인: ① 바뀐 경로 = apps/api-py/esgapi/runs/** + apps/api-py/scripts/*DVI1* + 허락받은 쿼리 수 시험 넷만
#   ② 기존 시험 파일의 BASE 줄 삭제·바뀜은 허락받은 파일에서 아래 표의 수만큼만(e7·0f·IRO 27 — 세이브포인트 +2, 감독 전달
#      10-29·30, MARC-TICK-424 노트. runs 의 import 셋은 ruff isort 가 합친 넓힘), 그 밖 시험 파일은 0
#   ③ RAW_SQL_ALLOWED(test_static_rules.py)·selector 문 표(test_selector_scope.py) diff 0 ④ generated diff 0
#   ⑤ e7 sha16(발주서 §4 셈법)을 찍는다. 컨테이너·시험은 돌리지 않는다(업무 층은 test-business.sh, 파손은 planted-breaks-DVI1.sh).
# 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 1 로 끝난다.
set -u
cd "$(dirname "$0")/../../.."
B=298f13ce
CACHED=""
[ "${1:-}" = "--cached" ] && CACHED="--cached"
FAILS=0
check() { # <이름> <명령>
  local out code
  out="$(eval "$2")"; code=$?
  echo "▶ $1"; [ -n "$out" ] && printf '%s\n' "$out" | sed 's/^/    /'
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
changed() {
  if [ -n "$CACHED" ]; then git diff --cached --no-renames --name-only "$B"
  else { git diff --no-renames --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; fi
}
A=apps/api-py
# 허락받은 기존 시험 파일 → 바뀌어도 되는 BASE 줄 수
ALLOWED="$A/esgapi/runs/tests/service/selectors/test_runs.py=6
$A/esgapi/dataverify/tests/service/apis/test_dataverify_runs.py=4
$A/esgapi/materiality/tests/service/apis/test_materiality_runs.py=5
$A/esgapi/translation/tests/service/actions/test_batches.py=3
$A/esgapi/translation/tests/service/actions/test_batches_input_kind.py=2"
check "① 허용 경로 밖 0" "! changed | grep -v -E -e '^$A/esgapi/runs/' -e '^$A/scripts/[^/]*DVI1[^/]*\$' \
  -e '^$A/esgapi/(dataverify/tests/service/apis/test_dataverify_runs|materiality/tests/service/apis/test_materiality_runs)\.py\$' \
  -e '^$A/esgapi/translation/tests/service/actions/test_batches(_input_kind)?\.py\$'"
check "② 기존 시험 파일의 BASE 줄 삭제·바뀜 = 허락 수(그 밖 0)" \
  "for f in \$(changed | grep -E '/tests/.*\.py\$'); do git cat-file -e $B:\$f 2>/dev/null || continue; \
   n=\$(git diff $CACHED --no-renames -U0 $B -- \$f | grep -cE '^-[^-]'); \
   want=\$(printf '%s\n' \"\$ALLOWED\" | sed -n \"s#^\$f=##p\"); echo \"\$f −\$n (허락 \${want:-0})\"; \
   [ \"\$n\" = \"\${want:-0}\" ] || exit 1; done; exit 0"
check "③ 날 SQL 허용 표·selector 문 표 diff 0" \
  "git diff $CACHED --exit-code --stat $B -- $A/esgapi/core/tests/isolation/test_static_rules.py $A/esgapi/core/tests/test_selector_scope.py"
check "④ generated diff 0" "git diff $CACHED --exit-code --stat $B -- $A/generated packages"
E7="$(git diff $CACHED $B -- $A/esgapi/core $A/esgapi/config $A/generated $A/tests/security $A/esgapi/runs | shasum -a 256 | cut -c1-16)"
echo "▶ ⑤ e7 sha16${CACHED:+ (스테이징 판)} = $E7"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
