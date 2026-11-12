#!/usr/bin/env bash
# 밴드 DVR1(MARC-TICK-379) §4 의 자기검증. reconcile 평평한 시험 셋을 calc/ 로(ISSUE-173) · AST 순수 시험의 상대 import
# 풀기(ISSUE-207 의 reconcile 몫).
#   사용: apps/api-py/scripts/section4-DVR1.sh
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>. 심은 파손은 planted-breaks-DVR1.sh 따로.
# 커밋 전에는 스테이징된 트리를 잰다(git diff --cached). 시험을 돌리는 단계는 작업 트리에서 도니 4단계가
# 「작업 트리 = 스테이징」을 함께 본다. 컨테이너 0 — django_db 시험은 수집만 대조한다(돌리지 않음).
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."
BASE=aff154be
OUT="$(cd ../../.. && pwd)/DVR1.out"
mkdir -p "$OUT"

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}

R=esgapi/reconcile/tests
MOVED="test_notation test_kinds test_document"
# 커밋이 고칠 수 있는 자리(발주서 §1 + 감독 처분 10-28: 허용 목록 세 줄 지우기 · document.py:6 주석 한 줄)
ALLOWED_RE='^apps/api-py/(esgapi/reconcile/tests/.*|scripts/section4-DVR1\.sh|scripts/planted-breaks-DVR1\.sh|scripts/test-layout-allow\.txt|esgapi/reconcile/calc/document\.py)$'

# [1] 순수 시험
uv run --frozen pytest esgapi/reconcile -m "not django_db" -q -p no:cacheprovider >"$OUT/pytest.txt" 2>&1
code=$?
tail -1 "$OUT/pytest.txt"
report 1 "pytest esgapi/reconcile -m 'not django_db'" $code

# [2] ruff(바뀐 .py)
py="$(git diff --cached --name-only --diff-filter=AMR "$BASE" -- '*.py' | sed 's#^apps/api-py/##')"
# shellcheck disable=SC2086
{ uv run --frozen ruff check $py && uv run --frozen ruff format --check $py; } >"$OUT/ruff.txt" 2>&1
code=$?  # 아래 $(…) 가 $? 를 덮기 전에 든다
report 2 "ruff check · format --check ($(echo "$py" | wc -l | tr -d ' ') 파일)" $code

# [3] import 계약
uv run --frozen lint-imports >"$OUT/lint-imports.txt" 2>&1
report 3 "lint-imports" $?

# [4] 스테이징 경계
code=0
outside="$(git diff --cached --name-only "$BASE" | grep -v -E "$ALLOWED_RE")"
[ -z "$outside" ] || { echo "  ★ 허용 밖: $outside"; code=1; }
[ -z "$(git diff --name-only)" ] || { echo "  ★ 작업 트리 ≠ 스테이징: $(git diff --name-only)"; code=1; }
untracked="$(git ls-files --others --exclude-standard -- . | grep -v -E '^scripts/(section4|planted-breaks)-DVR1\.sh$')"
[ -z "$untracked" ] || { echo "  ★ 스테이징 안 된 새 파일: $untracked"; code=1; }
# 허용 목록: 옮긴 셋의 줄 지우기만
allow="$(git diff --cached -U0 "$BASE" -- scripts/test-layout-allow.txt | grep -E '^[-+][^-+]')"
want="$(for n in $MOVED; do echo "-$R/$n.py"; done | sort)"
[ "$(echo "$allow" | sort)" = "$want" ] || { echo "  ★ 허용 목록 diff 가 세 줄 지우기가 아니다: $allow"; code=1; }
# 제품 코드: document.py 의 주석 한 줄(+1 −1, 시험 경로만 바뀜)
prod="$(git diff --cached -U0 "$BASE" -- esgapi/reconcile/calc/document.py | grep -E '^[-+][^-+]')"
[ "$(echo "$prod" | wc -l | tr -d ' ')" = 2 ] && [ "$(echo "$prod" | sed -E 's/^[-+]//; s#`tests/(calc/)?test_document(_ts)?\.py`#X#' | sort -u | wc -l | tr -d ' ')" = 1 ] \
  || { echo "  ★ document.py diff 가 주석 한 줄 경로 바꿈이 아니다: $prod"; code=1; }
# 옮긴 셋: 이름 바꿈으로 잡히고, 바뀐 줄은 HERE(폴더 한 칸 깊어짐) 하나뿐
for n in $MOVED; do
  status="$(git diff --cached -M --name-status "$BASE" -- "$R/$n.py" "$R/calc/${n}_ts.py" | cut -f1)"
  case "$status" in R*) ;; *) echo "  ★ $n 이 이름 바꿈으로 잡히지 않는다: $status"; code=1 ;; esac
  body="$(git diff --cached -M -U0 "$BASE" -- "$R/$n.py" "$R/calc/${n}_ts.py" | grep -E '^[-+][^-+]')"
  case "$n" in
    test_document)
      [ "$body" = "$(printf '%s\n%s' '-HERE = Path(__file__).resolve().parent' '+HERE = Path(__file__).resolve().parents[1]')" ] \
        || { echo "  ★ $n 의 본문이 바뀌었다: $body"; code=1; } ;;
    *) [ -z "$body" ] || { echo "  ★ $n 의 본문이 바뀌었다: $body"; code=1; } ;;
  esac
done
report 4 "스테이징 = 허용 안 · 옮긴 셋 본문 같음 · 허용 목록 −3 · document.py 주석 1" $code

# [5] 수집 id 대조: BASE 와 가지가 옮긴 셋의 경로만 다르고 이름·수가 같다
base_tree="$(mktemp -d /private/tmp/dvr1-base.XXXXXX)"
git -C "$(git rev-parse --show-toplevel)" archive "$BASE:apps/api-py" | tar -x -C "$base_tree"
# 가지의 .venv 를 빌리되 PYTHONPATH 를 앞에 둬 BASE 소스를 import 한다(편집 설치 .pth 보다 앞)
venv="$(pwd)/.venv"
(cd "$base_tree" && PYTHONPATH="$base_tree" "$venv/bin/python" -m pytest esgapi/reconcile --collect-only -q -p no:cacheprovider 2>&1) \
  | grep '::' >"$OUT/collect-base.txt"
rm -rf "$base_tree"
uv run --frozen pytest esgapi/reconcile --collect-only -q -p no:cacheprovider 2>&1 | grep '::' >"$OUT/collect-branch.txt"
mapped="$OUT/collect-base-mapped.txt"
cp "$OUT/collect-base.txt" "$mapped"
for n in $MOVED; do sed -i '' "s#^$R/$n\.py::#$R/calc/${n}_ts.py::#" "$mapped"; done
code=0
diff <(sort "$mapped") <(sort "$OUT/collect-branch.txt") >"$OUT/collect-diff.txt" || code=1
echo "  수집 BASE $(wc -l <"$OUT/collect-base.txt" | tr -d ' ') · 가지 $(wc -l <"$OUT/collect-branch.txt" | tr -d ' ') · 경로 바꿔 대 본 차이 $(wc -l <"$OUT/collect-diff.txt" | tr -d ' ')줄"
[ "$(wc -l <"$OUT/collect-base.txt")" -gt 300 ] || { echo "  ★ BASE 수집이 너무 적다"; code=1; }
report 5 "수집 id 대조" $code

# [6] 시험 자리 규칙
uv run --frozen python scripts/check_test_layout.py >"$OUT/layout.txt" 2>&1
code=$?
tail -1 "$OUT/layout.txt"
grep -q '허용인데 없음 0 · 어김 0' "$OUT/layout.txt" || code=1
report 6 "check_test_layout(허용인데 없음 0 · 어김 0)" $code

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
