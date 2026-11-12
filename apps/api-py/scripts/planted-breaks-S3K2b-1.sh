#!/usr/bin/env bash
# S3K2b-1 의 심은 고장(발주서 band-handoffs/S3K2b-1-order.md §3): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S3K2b-1.sh --commit <1|2>
#   경계별 배치(누적): ① P3·P4·P5·P7·P8·P9·P9b·P10·P13·P14(10 — P14 는 러너가 더한 표 밖 하나) · ② +P1·P2·P6·P11·P12(15).
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
AS=$I/service/actions/scope3_state.py
AD=$I/service/actions/dashboard.py
SE=$I/service/selectors/scope3_edits.py
SS=$I/service/selectors/scope3_state.py
MG=$I/migrations/0006_scope3_row_edits.py
TA=$IT/service/actions/test_scope3_edits.py
TR=$IT/service/actions/test_scope3_edits_race.py
TM=$IT/test_migrations_0006.py
TU=$IT/service/actions/test_scope3_edits_sums.py
SEC=tests/security/test_scope3_edits.py

backup="$(mktemp -d /private/tmp/s3k2b1-planted.XXXXXX)"
case "$backup" in /private/tmp/s3k2b1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P3 잠김 판정 뺌 · P4 current.runId 대조 뺌 · P5 지금 상태를 가장 작은 id 로 · P7 거절 때 set_rollback 뺌 ·
#   P8 events_of 의 for_company 대신 unscoped · P9·P9b 사유·row_id CHECK 무력화(>= 0 — 한도+1 은 varchar 가 막아 근거 아님) ·
#   P10 히스토리에 다른 실행 사건 섞음 · P13 FOR UPDATE 뺌(경합) · P14(러너 표 밖) 다른 모듈 실행 거름 뺌
# ② P1 합에서 제외 무시 · P2 편집을 rowId 로만 찾음(실행 무시) · P6 editedRowsUnlocked 에 잠긴 카테고리 더함 ·
#   P11 549 ① _base 두 번 되돌림 · P12 대시보드 이름 조회 되돌림
ROWS="P3|1|$AE|    if row.lock is not None:\n        return _refused(Locked())\n||biz:$TA
P4|1|$AE|    if base.run_id != run_id:\n        return _refused(StaleRun())\n||biz:$TA
P5|1|$UE|event.id > last.id|event.id < last.id|$IT/service/utils/test_scope3_edits.py
P7|1|$AE|    transaction.set_rollback(True)  # ④|    pass  # ④|biz:$TA
P8|1|$SE|    rows = Scope3RowEdit.for_company(company_id).filter(run_id__in=run_ids).order_by(\"id\")|    rows = Scope3RowEdit.unscoped.filter(run_id__in=run_ids).order_by(\"id\")|sec:$SEC
P9|1|$MG|Trim(\"reason\")),\n                                1,|Trim(\"reason\")),\n                                0,|biz:$TM
P9b|1|$MG|Length(\"row_id\"), 1|Length(\"row_id\"), 0|biz:$TM
P10|1|$SE|    rows = Scope3RowEdit.for_company(company_id).filter(run_id=run_id)\n|    rows = Scope3RowEdit.for_company(company_id).filter(run_id__gte=0)\n|biz:$TA
P13|1|$SS|for_company(company_id).select_for_update().filter(year=year, category=category)|for_company(company_id).filter(year=year, category=category)|biz:$TR
P14|1|$AE|    return run if run is not None and run.module == MODULE else None|    return run|biz:$TA
P1|2|$US|                if row is not None and row.get(\"rowId\") not in excluded:|                if row is not None:|biz:$TU
P2|2|$SE|filter(run_id__in=run_ids).order_by(\"id\")§    return [_event(line) for line in rows.values_list(*_FIELDS)]\n\n\ndef history_page|filter(run_id__gte=0).order_by(\"id\")§    return [__import__(\"dataclasses\").replace(_event(line), run_id=max(run_ids)) for line in rows.values_list(*_FIELDS)]\n\n\ndef history_page|biz:$TU
P6|2|$AS|sum(line.edited_rows for line in categories if line.locked_at is None)|sum(line.edited_rows for line in categories)|biz:$TU
P11|2|$AS|    return category_state(company_id, year, category, base, pinned)|    return category_state(company_id, year, category, base_of(company_id, year))|biz:$TU
P12|2|$AD|    found = scope3_state.year_values(company_id, year)\n    return {} if isinstance(found, Invalid) else found|    found = scope3_state.year_state(company_id, year)\n    if isinstance(found, Invalid):\n        return {}\n    return {line.category: None if line.current is None else line.current.value.total for line in found.categories}|biz:$TU"

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
