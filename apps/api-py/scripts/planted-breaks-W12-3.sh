#!/usr/bin/env bash
# W12-3 ① 의 심은 고장(발주서 band-handoffs/W12-3-order.md §2-1 — sid:MARC-ISSUE-548 직접입력 단위 검사): 고장 하나를
#   심고, 그것을 물어야 할 시험이 빨개지는지 본다. 사용: apps/api-py/scripts/planted-breaks-W12-3.sh --commit 1
#   표: S1 검사 뺌 · S2 첫 단위만 봄 · S3 잠김 409 를 단위 검사 앞으로(차례) · S4 열쇠를 custom.inputUnit 하나로 뭉침 ·
#   S5 거절이 직접입력 행을 남김. 표 밖: S6 행 하나의 단위만 봄(잎 선택지 대신) · S7 같은 단위도 쌍을 요구함.
# 틀은 planted-breaks-S12a-2.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을
#   쓰지 않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만. 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」).
#   시험은 업무 층(이 워크트리의 compose postgres). .git/verify.lock 이 있는 동안 기다린다.
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1) ;; *) echo "--commit 1" >&2; exit 2 ;; esac

I=esgapi/inventory
UE=$I/service/utils/entries.py
AE=$I/service/actions/entries.py
AT=$I/tests/service/actions/test_entries.py
APT=$I/tests/service/apis/test_entries.py

backup="$(mktemp -d /private/tmp/w123-planted.XXXXXX)"
case "$backup" in /private/tmp/w123-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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

# 줄: <id>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
ROWS="S1|$AE|    if values is not None:\n        leaf_unit = |    if False and values is not None:\n        leaf_unit = |$AT $APT
S2|$UE|for unit in row_units)|for unit in row_units[:1])|$AT
S3|$AE|    year_id, chosen, pinned, row = found\n    if values is not None:|    year_id, chosen, pinned, row = found\n    if chosen.locked_at is not None:\n        return Locked()\n    if values is not None:|$AT
S4|$UE|errors[\"custom.ncvUnit\"]§denominator, conversions):\n        errors[\"custom.factorUnit\"]§EMISSION_UNIT, conversions):\n        errors[\"custom.factorUnit\"]|errors[\"custom.inputUnit\"]§denominator, conversions):\n        errors[\"custom.inputUnit\"]§EMISSION_UNIT, conversions):\n        errors[\"custom.inputUnit\"]|$AT
S5|$AE|            return Invalid(mismatch)|            services.insert_custom(company_id, values, actor)\n            return Invalid(mismatch)|$AT
S6|$AE|        row_units = unit_options(leaf_unit[1], conversions())|        row_units = (row.unit,)|$AT
S7|$UE|    return source == target or (source, target) in conversions|    return (source, target) in conversions|$AT"

planted=0
caught=0
bad=0
while IFS='|' read -r id file old new tests; do
  [ -n "$id" ] || continue
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 20; done  # 전량 verify 와 겹치지 않는다
  # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
  env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider $tests > "$backup/log" 2>&1
  code=$?
  if [ "$code" = 1 ]; then red=1; else red=0; fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' -)"
  nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code) 빨강 ${nfail:-0}개: ${failed:-}"
done <<EOF
$ROWS
EOF

want=7
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
