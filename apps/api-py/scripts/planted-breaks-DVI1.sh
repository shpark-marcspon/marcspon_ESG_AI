#!/usr/bin/env bash
# 밴드 DVI1 의 심은 파손(발주서 band-handoffs/DVI1-order.md §3 P1~P3 + 러너가 더한 X1~X5 — X3 「대체 길 뺌」은 감독 요구). 하나씩 runs selector 에 심고
# 그 시험 파일(업무 층)을 돌린 뒤 원본 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — 끝에 sha 대조).
# SIGINT·SIGTERM 이 와도 되쓴다. compose 의 postgres 가 떠 있어야 한다(scripts/test-business.sh).
# 사용(어디서든): apps/api-py/scripts/planted-breaks-DVI1.sh
# 판정: P0(아무것도 안 심음)은 전부 초록. 한 P 의 「잡음」= 종료가 0 이 아니고 빨개져야 할 노드가 전부 FAILED.
# 끝 줄 PLANTED=<잡음>/<심음>. 로그: DVI1_OUT(기본 워크트리 곁의 DVI1.out)/planted/. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${DVI1_OUT:-$(cd "$ROOT/.." && pwd)/DVI1.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
  uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import re
import signal
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
SEL = Path("esgapi/runs/service/selectors/runs.py")
T = "esgapi/runs/tests/service/selectors/test_runs.py"


def _term(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, _term)

LONE = 'LONE_ESCAPE = rf"{_REAL}(?:\\\\u0000|{_HIGH}(?!{_LOW})|{_LOW}(?<!{_REAL}{_HIGH}{_LOW}))"\n'
KEYS = [f"{T}::test_run_keys_count_a_lone_escape_row_like_python[{p}]" for p in ("raw_pair", "escaped_pair")]
BRIEF = [f"{T}::test_run_page_brief_marks_only_a_lone_escape_row[{p}]" for p in ("raw_pair", "escaped_pair")]
BATCH = f"{T}::test_run_keys_read_the_batch_id_of_a_lone_escape_row"
HTTP = f"{T}::test_the_dataverify_run_list_is_200_with_a_lone_surrogate_row"
MIXED = f"{T}::test_a_mixed_page_takes_the_fallback_and_answers_like_python"
OUTER = f"{T}::test_the_outer_transaction_lives_after_the_fallback"
TAKES = f"{T}::test_the_fallback_takes_only_the_lone_escape_errors"
SAVE = "        with transaction.atomic():  # 세이브포인트 — 떨어져도 바깥 트랜잭션은 산다\n"
NARROW = '    return state == "22P02" and getattr(diag, "message_primary", None) == "invalid input syntax for type json"\n'
# (번호, 설명, 바꿀 글자, 바꾼 글자, 빨개져야 할 노드) — 바꿀 글자가 여러 번이면 전부 바꾼다(X4 의 세이브포인트 둘)
PLANTS = [
    ("P1", "표시를 \\u0000 만으로 되돌림", LONE, 'LONE_ESCAPE = rf"{_REAL}\\\\u0000"\n', [*KEYS, *BRIEF, BATCH, HTTP, MIXED]),
    ("P2", "run_keys 비킴 뺌(대체 길도 감싼 글자를 그대로 ::jsonb)",
     "    if lone_safe:\n        inner = Func(\n", "    if False:\n        inner = Func(\n", [*KEYS, BATCH, MIXED, OUTER]),
    ("P3", "정상 짝도 표시", LONE, 'LONE_ESCAPE = rf"{_REAL}(?:\\\\u0000|{_HIGH}|{_LOW})"\n', [BRIEF[1]]),
    ("X1", "run_keys 의 표시 줄 두 번째 쿼리(파이썬 셈) 뺌", "    if lone:  #", "    if False:  #", [*KEYS, BATCH, MIXED]),
    ("X2", "하위 갈래의 「앞이 진짜 상위」에서 역슬래시 홀짝을 뺌", LONE,
     LONE.replace("(?<!{_REAL}{_HIGH}{_LOW})", "(?<!{_HIGH}{_LOW})"), [*KEYS, *BRIEF]),
    ("X3", "대체 길 뺌(어떤 DataError 도 다시 던짐)", "    cause = error.__cause__\n",
     "    return False\n    cause = error.__cause__\n", [*KEYS, *BRIEF, BATCH, HTTP, MIXED, OUTER]),
    ("X4", "세이브포인트 뺌(보통 길을 바깥 트랜잭션에서 바로)", SAVE, SAVE.replace("with transaction.atomic():", "if True:"),
     [*KEYS, *BRIEF, BATCH, MIXED, OUTER]),
    ("X5", "22P02 를 json 메시지로 좁히지 않음", NARROW, '    return state == "22P02"\n',
     [f"{TAKES}[integer_text]"]),
]

original = SEL.read_bytes()
digest = hashlib.sha256(original).hexdigest()


def run(tag: str) -> tuple[int, set[str]]:
    done = subprocess.run(
        ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider", T], capture_output=True, text=True
    )
    log = done.stdout + done.stderr
    (LOGS / f"{tag}.log").write_text(log)
    return done.returncode, set(re.findall(r"^FAILED (\S+)", log, re.M))


caught = 0
try:
    code, failed = run("P0")
    print(f"P0= exit {code} · FAILED {len(failed)}")
    if code != 0:
        sys.exit("P0 가 초록이 아니다 — 심기 전에 멈춘다")
    for tag, what, old, new, want in PLANTS:
        text = original.decode()
        if text.count(old) < 1:
            print(f"{tag} 심을 자리 없음 — {what}")
            continue
        SEL.write_text(text.replace(old, new))
        try:
            code, failed = run(tag)
        finally:
            SEL.write_bytes(original)
        missing = [n for n in want if n not in failed]
        ok = code != 0 and not missing
        caught += ok
        print(f"{tag} {'잡음' if ok else '놓침'} — {what} · exit {code} · FAILED {len(failed)} · 빠짐 {missing}")
        for node in sorted(failed):
            print(f"    {node.split('::', 1)[1]}")
finally:
    SEL.write_bytes(original)
    assert hashlib.sha256(SEL.read_bytes()).hexdigest() == digest
print(f"FINGERPRINT={digest[:16]} (되씀 확인)")
print(f"PLANTED={caught}/{len(PLANTS)}")
PY
