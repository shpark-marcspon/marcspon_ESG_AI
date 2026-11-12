#!/usr/bin/env bash
# 밴드 IRS3 의 심은 파손(발주서 band-handoffs/IRS3-order.md §3 표 — planted-breaks-IR3c.sh 꼴). 하나씩 심고 겨눈 시험만
# 돌린 뒤 원본 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — try/finally, SIGTERM·SIGINT 도 finally 를
# 지난다). 사용:
#   apps/api-py/scripts/planted-breaks-IRS3.sh [--commit <n>] [--with-containers] [--only P1,P4]
#   --commit n 은 경계 n 까지의 몫만(① P1~P7·P7b, ② +P8~P10, ③ +P11~P13). 기본 3.
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 업무·보안 층(Postgres)은 --with-containers 일 때만 —
# 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다. 끝에 심은 파일의 sha256 과 git status 가 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: IRS3_OUT(기본: 워크트리 곁의 IRS3.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${IRS3_OUT:-$(cd "$ROOT/.." && pwd)/IRS3.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
  uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
CONTAINERS = False
ONLY = None
COMMIT = 3
while args:
    if args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    elif args[0] == "--commit" and len(args) > 1:
        COMMIT, args = int(args[1]), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def _stop(signum, _frame):  # SIGTERM·SIGINT 도 되쓰기(finally)를 지나게
    raise SystemExit(128 + signum)


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


EDITS = Path("esgapi/materiality/outputs/edits.py")
SELECTORS = Path("esgapi/materiality/service/selectors/edits.py")
TE = "esgapi/materiality/tests/outputs/test_edits.py"
TS = "esgapi/materiality/tests/service/services/test_edits.py"
SERVICES = Path("esgapi/materiality/service/services/edits.py")
RESULT = Path("esgapi/materiality/service/actions/result.py")
EDIT_ACTION = Path("esgapi/materiality/service/actions/edits.py")
TA = "esgapi/materiality/tests/service/apis/test_materiality_edits.py"
UNSCOPED = (
    "    company_id = getattr(__import__('esgapi.runs.models', fromlist=['RunRow']).RunRow.unscoped"
    ".filter(pk=run_id).first(), 'company_id', company_id)\n"
)
REPORT = Path("esgapi/materiality/service/actions/report.py")
TR = "esgapi/materiality/tests/service/apis/test_materiality_report.py"
IMPORT_RESULT = "from esgapi.materiality.service.actions.result import NotFound, RunNotDone, run_result\n"
IMPORT_BOTH = "from esgapi.materiality.service.actions.result import NotFound, RunNotDone, original_result, run_result\n"
BUILD = "    content, _cuts = final_xlsx.build_final(in_shape_order(result))\n"
RAW_FROM_ORIGINAL = BUILD + """    import io as _io  # 심은 파손 P13: RAW_JSON 만 원본 본문으로 다시 씀
    from openpyxl import load_workbook as _lw
    from esgapi.materiality.outputs.xlsx import raw_json_chunks as _chunks
    _book = _lw(_io.BytesIO(content))
    _orig = original_result(company_id=company_id, run_id=run_id)
    for _n, _c in enumerate(_chunks(in_shape_order(_orig)), 1):
        _book["RAW_JSON"].cell(row=_n, column=1).value = _c
    _out = _io.BytesIO()
    _book.save(_out)
    content = _out.getvalue()
"""
SAVE_HEAD = "    body = original_result(company_id=company_id, run_id=run_id)\n    if isinstance(body, NotFound | RunNotDone):\n        return body\n    checked"
P3_HELPER = """

def _p3(body, current):  # 심은 파손 P3: 지금 고친 url 을 그 자리(첫 자리)에만 넣은 본문으로 묶음을 정한다
    out = copy.deepcopy(body)
    for target, value in current.items():
        address = parse(target)
        if address is not None and address.side is not None and address.field == "url":
            _item(out, tuple(address[:6]))["url"] = value
    return out
"""
P1_TAIL = """    import json as _json  # 심은 파손 P1: 원문 글을 본문 어디서나(parsed 포함) 고친 글로 바꿈

    text = _json.dumps(out, ensure_ascii=False)
    for target, value in current.items():
        old = original_value(body, target)
        if isinstance(old, str) and isinstance(value, str):
            text = text.replace(_json.dumps(old, ensure_ascii=False), _json.dumps(value, ensure_ascii=False))
    return _json.loads(text)


def original_value("""
APPLY_LOOP = "    for target, value in current.items():\n        address = parse(target)\n        if address is None:\n            raise LookupError(target)  # 저장한"


def swap_all(old: str, new: str, times: int) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new) if text.count(old) == times else None

    return plant


def chain(*plants: Callable[[str], str | None]) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        for one in plants:
            got = one(text)
            if got is None:
                return None
            text = got
        return text

    return plant


# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (경계, 번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    (1, "P1", "apply 가 parsed 안 같은 글도 바꿈",
     [(EDITS, swap("    return out\n\n\ndef original_value(", P1_TAIL))],
     [(PURE, [TE], {TE + "::test_apply_leaves_parsed_raw_and_the_original_alone"})]),
    (1, "P2", "퍼짐에서 pathway 사본을 뺌",
     [(EDITS, swap("                            of[key] = first\n                            members[first].append(key)\n",
                   "                            of[key] = first\n"))],
     [(PURE, [TE], {TE + "::test_the_pathway_copy_follows_and_the_2_2_summary_shows_it"})]),
    (1, "P3", "묶음을 고친 url 로 정함",
     [(EDITS, chain(swap("    found = groups(body)\n    out: list[tuple[str, str | None]] = []\n",
                         "    found = groups(_p3(body, current))\n    out: list[tuple[str, str | None]] = []\n"),
                    lambda t: t + P3_HELPER))],
     [(PURE, [TE], {TE + "::test_the_group_is_fixed_by_the_original_url"})]),
    (1, "P4", "허용 꼴에 impactType 더함",
     [(EDITS, swap("_POINTER: Final = re.compile(POINTER_PATTERN)",
                   '_POINTER: Final = re.compile(POINTER_PATTERN.replace("impactDefinition", "(impactDefinition|impactType)"))'))],
     [(PURE, [TE], {TE + "::test_a_classification_pointer_is_400"})]),
    (1, "P5", "상한 비교 > → > +1(한 자 더 받음)",
     [(EDITS, swap("    if len(value) > LIMITS[field]:\n", "    if len(value) > LIMITS[field] + 1:\n"))],
     [(PURE, [TE], {f"{TE}::test_limits_at_n_and_n_plus_one[/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition-4000]"})]),
    (1, "P6", "지금 값을 가장 작은 revision 으로",
     [(SELECTORS, swap('.order_by("pointer", "-revision")', '.order_by("pointer", "revision")'))],
     [(BUSINESS, [TS], {TS + "::test_the_current_value_is_the_largest_revision"})]),
    (1, "P7", "url 겹침 검사 지움",
     [(EDITS, swap("    clash = _url_clash(body, found, {**current, **dict(out)})\n", "    clash = None\n"))],
     [(PURE, [TE], {TE + "::test_a_url_that_matches_another_group_is_400"})]),
    (1, "P7b", "덮기가 「원문과 같음」인 바른 주소를 건너뜀",
     [(EDITS, swap(APPLY_LOOP, "    for target, value in current.items():\n        if value == original_value(body, target):\n"
                               "            continue\n        address = parse(target)\n        if address is None:\n"
                               "            raise LookupError(target)  # 저장한"))],
     [(PURE, [TE], {TE + "::test_apply_is_deterministic_and_writes_values_equal_to_the_original"})]),
    (2, "P8", "조건부 UPDATE 의 revision = base 조건 지움",
     [(SERVICES, swap(".filter(run_id=run_id, revision=base_revision)", ".filter(run_id=run_id)"))],
     [(BUSINESS, [TA], {TA + "::test_two_saves_from_the_same_revision_one_wins"})]),
    (2, "P9", "run_result 가 덮기 전 본문을 냄",
     [(RESULT, swap("    return edits.apply(body, {row.pointer: row.value for row in rows})\n", "    return body\n"))],
     [(BUSINESS, [TA], {TA + "::test_a_shortlist_item_edit_shows_in_the_2_1_summary_and_the_1_1_title"})]),
    (2, "P10", "고침 저장의 회사를 unscoped 로(경로 id 의 실행 회사로 갈아 씀 — 시험 안 가짜)",
     [(EDIT_ACTION, swap(SAVE_HEAD, UNSCOPED + SAVE_HEAD))],
     [(BUSINESS, [TA], {TA + "::test_another_company_cannot_edit_or_read"})]),
    (2, "P10b", "검증 ② 블로커: 머리 없음 선검사와 409 되돌림(set_rollback) 둘 다 지움(고아 머리)",
     [(EDIT_ACTION, chain(swap("    if head is None and base_revision != 0:\n", "    if False:\n"),
                          swap("        transaction.set_rollback(True)", "        pass")))],
     [(BUSINESS, [TA], {TA + "::test_a_first_save_with_a_nonzero_base_makes_no_head",
                        TA + "::test_a_refused_first_save_leaves_no_head"})]),
    (3, "P11", "report 가 원본 본문으로 지음",
     [(REPORT, chain(swap(IMPORT_RESULT, IMPORT_BOTH),
                     swap("    result = run_result(company_id=company_id, run_id=run_id)\n",
                          "    result = original_result(company_id=company_id, run_id=run_id)\n")))],
     [(BUSINESS, [TR], {TR + "::test_edited_cells_land_in_2_1_q_2_2_s_and_1_1_f"})]),
    (3, "P12", "감사 줄 지움",
     [(REPORT, swap("    record_event(\n        at=now,", "    (lambda **_: None)(\n        at=now,"))],
     [(BUSINESS, [TR], {TR + "::test_one_download_audit_row_per_report"})]),
    (3, "P13", "RAW_JSON 을 원본 본문으로",
     [(REPORT, chain(swap(IMPORT_RESULT, IMPORT_BOTH), swap(BUILD, RAW_FROM_ORIGINAL)))],
     [(BUSINESS, [TR], {TR + "::test_raw_json_is_the_edited_result"})]),
    (3, "P14", "검증 ③ B2: 검사한 값 말고 받은 dict 를 덤프(jsonb 차례가 RAW_JSON 에)",
     [(REPORT, swap("adapter.dump_json(adapter.validate_python(result, strict=True))",
                    "adapter.dump_json(result) if adapter.validate_python(result, strict=True) is not None else b''"))],
     [(BUSINESS, [TR], {TR + "::test_raw_json_keeps_the_shape_key_order_of_a_stored_run"})]),
]
PLANTS = [p[1:] for p in PLANTS if p[0] <= COMMIT and (ONLY is None or p[1] in ONLY)]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    done = subprocess.run([*layer[1], *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (.+?)(?: - .*)?$", text, flags=re.M))  # 매개 id 에 빈칸이 있다(GET /…)
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[3]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _failed, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, checks) -> bool | None:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                return False
            f.write_text(new, encoding="utf-8")
        hit_all, skipped = True, False
        for layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                skipped = True
                continue
            code, failed, _last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            hit_all = hit_all and hit
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - failed)} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        return None if skipped and hit_all else hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
for number, what, edits, checks in PLANTS:
    planted += 1
    result = plant_and_check(number, what, edits, checks)
    caught += 1 if result is True else 0
    print(f"{number} => {'잡음' if result else '안 돌림' if result is None else '못 잡음'}")

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
