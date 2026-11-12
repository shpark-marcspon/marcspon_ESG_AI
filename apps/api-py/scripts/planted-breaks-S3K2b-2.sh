#!/usr/bin/env bash
# S3K2b-2 의 심은 고장(발주서 band-handoffs/S3K2b-2-order.md §3): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S3K2b-2.sh --commit <1|2>
#   경계별 배치(누적): ① P3~P10·P13·P14(10 — P14 는 러너가 더한 표 밖 하나) · ② +P1·P2·P11·P12·P15(15 — P15 는 검증 B1 의 넘침). ①·② 는 한 경계로 합쳤다 — --commit 2.
# 틀은 planted-breaks-S3K2a.sh: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 —
#   checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(둘 다 이 워크트리의 compose postgres 가 떠 있어야 한다), 그 밖은 순수 층.
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# verify.lock 이 있으면 exit 3(부분 실행도 안 돌린다 — runner-common §5). macOS /bin/bash 3.2. LLM·네트워크 0.
set -euo pipefail
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1|2) ;; *) echo "--commit 1·2" >&2; exit 2 ;; esac

LOCK="/Users/leedongeon/Desktop/marcspon/esg-app/.git/verify.lock"
I=esgapi/inventory
IT=$I/tests
UE=$I/service/utils/scope3_edits.py
US=$I/service/utils/scope3_state.py
AE=$I/service/actions/scope3_edits.py
SE=$I/service/selectors/scope3_edits.py
SS=$I/service/selectors/scope3_state.py
MG=$I/migrations/0007_scope3_row_factors.py
UF=$I/service/utils/scope3_factors.py
TF=$IT/service/actions/test_scope3_factors.py
TR=$IT/service/actions/test_scope3_edits_race.py
TM=$IT/test_migrations_0007.py
TU=$IT/service/actions/test_scope3_factors_sums.py

backup="$(mktemp -d /private/tmp/s3k2b2-planted.XXXXXX)"
case "$backup" in /private/tmp/s3k2b2-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
  git ls-files -o --exclude-standard -z | xargs -0 shasum -a 256 2>/dev/null | shasum -a 256
}
before="$(fingerprint)"
plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈, § 로 여러 자리)
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
path, olds, news = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
pairs = list(zip(olds.split("§"), news.split("§"), strict=True))
for old, new in pairs:
    if text.count(old) != 1:
        print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
        sys.exit(1)
    text = text.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(text)
PYEOF
}

# 줄: <id>|<경계>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
# ① P3 fold 축 하나 · P4 왕복계수 뺌 · P5 applied 를 고침으로 셈 · P6 C15 받음 · P7 거절 때 set_rollback 뺌 · P8 순위 0부터 ·
#   P9 모양 CHECK 의 NULL 틈 · P10 소수 자리 검사 뺌 · P13 FOR UPDATE 뺌(경합) · P14(표 밖) 줄별 자기 대조 뺌
# ② P1 합에서 고친 co2e 무시 · P2 계수 사건을 rowId 로만 찾음(실행 무시) · P11 L4 되돌림 · P12 L5 되돌림
ROWS="P3|1|$UE|key = (event.run_id, event.row_id, axis_of(event.kind))|key = (event.run_id, event.row_id, ROW_AXIS)|$IT/service/utils/test_scope3_edits.py
P4|1|$UF|return km * trip * people * trips * value / 1000.0|return km * people * trips * value / 1000.0|$IT/service/utils/test_scope3_factors_same.py
P5|1|$UE|        and event.factor.choice != \"applied\"\n||biz:$TF
P6|1|$UF|    factor = _mapping(row.get(\"factor\"))\n    if schema != RESULT_SHAPE|    factor = _mapping(row.get(\"factor\"))\n    if row.get(\"kind\") == \"investment\":\n        return True\n    if schema != RESULT_SHAPE|$IT/service/utils/test_scope3_factors.py
P7|1|$AE|    transaction.set_rollback(True)  # ④|    pass  # ④|biz:$TF
P8|1|$UF|items[rank - 1] if rank <= len(items)|items[rank] if rank < len(items)|$IT/service/utils/test_scope3_factors.py
P9|1|$MG|(\"factor_choice__isnull\", False),||biz:$TM
P10|1|$UF|if match is None or len(match.group(2) or \"\") > VALUE_DECIMALS:|if match is None:|$IT/service/utils/test_scope3_factors.py
P13|1|$SS|for_company(company_id).select_for_update().filter(year=year, category=category)|for_company(company_id).filter(year=year, category=category)|biz:$TR
P14|1|$UF|    return (None if again is None else again.co2e) == row.get(\"co2e\")|    return again is not None or True|$IT/service/utils/test_scope3_factors_same.py
P1|2|$US|    return co2e_of[row_id] if row_id in co2e_of else row.get(\"co2e\")|    return row.get(\"co2e\")|biz:$TU
P2|2|$UE|        if event_run == run_id\n        and event.category == category\n        and event.factor is not None|        if event.category == category\n        and event.factor is not None|biz:$TU
P11|2|$AE|        events = [*events, *services.add_events(company_id, run_id, category, kind, stripped, actor, changed, uuid4())]|        services.add_events(company_id, run_id, category, kind, stripped, actor, changed, uuid4())\n        events = selectors.events_of(company_id, [run_id])|biz:$IT/service/actions/test_scope3_edits_sums.py
P15|2|$UF|    if not math.isfinite(emission):\n        return None\n||$IT/service/utils/test_scope3_factors.py
P12|2|$US|    if not isinstance(row_id, str):\n        return row.get(\"co2e\")\n||$IT/service/utils/test_scope3_state.py"

planted=0
caught=0
bad=0
while IFS='|' read -r id at file old new tests; do
  [ -n "$id" ] || continue
  [ "$at" -le "$COMMIT" ] || continue
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  [ ! -e "$LOCK" ] || { echo "verify.lock 있음 — 멈춤"; exit 3; }
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  code=0
  if [ "${tests#biz:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1 || code=$?
  elif [ "${tests#sec:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1 || code=$?
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests > "$backup/log" 2>&1 || code=$?
  fi
  if [ "$code" = 1 ]; then red=1; else red=0; fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' - || true)"
  nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null || true)"
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, $tests) 빨강 ${nfail:-0}개: ${failed:-}"
done <<ROWS_END
$ROWS
ROWS_END

case "$COMMIT" in 1) want=10 ;; 2) want=15 ;; esac  # 경계마다 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
same=same
if [ "$before" != "$after" ]; then
  same=differs
  diff <(echo "$before") <(echo "$after") || true
fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$same"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$same" = same ]
