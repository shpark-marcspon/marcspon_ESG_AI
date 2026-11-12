#!/usr/bin/env bash
# 밴드 IRW2 의 심은 파손 — 서버 몫(발주서 band-handoffs/IRW2-order.md §3 P1~P5·P2b~P2g, + 러너 몫 PR1·PR2). 웹 몫
# (P6~P16)은 apps/web/scripts/planted-breaks-IRW2.sh. 틀은 planted-breaks-IR3c.sh 그대로: 하나씩 심고 겨눈 시험만 돌린
# 뒤 원본 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — try/finally, SIGTERM·SIGINT 도 finally 를 지난다).
#   apps/api-py/scripts/planted-breaks-IRW2.sh [--commit <n>] [--with-containers] [--only P1,P4]
#   --commit 은 받기만 한다(서버 몫은 전부 경계 ①).
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 업무·보안 층(Postgres)은 --with-containers 일 때만 —
# 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다. 끝에 심은 파일의 sha256 과 git status 가 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: IRW2_OUT(기본: 워크트리 곁의 IRW2.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${IRW2_OUT:-$(cd "$ROOT/.." && pwd)/IRW2.out}"
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


READER = Path("esgapi/materiality/tools/value_chain_xlsx.py")
ACTION = Path("esgapi/materiality/service/actions/value_chain.py")
PERM = Path("esgapi/core/permissions.py")
TX = "esgapi/materiality/tests/tools/test_value_chain_xlsx.py"
TW = "esgapi/materiality/tests/tools/test_value_chain_xlsx_twin.py"
TA = "esgapi/materiality/tests/service/apis/test_value_chain.py"
TP = "esgapi/core/tests/test_permissions.py"
SM = "tests/security/test_materiality.py"
REJ = TX + "::test_each_rejection_has_its_kind_row_column_and_sentence"
DOCTYPE = TX + "::test_a_doctype_in_any_part_openpyxl_opens_is_unsafe"
ANY_PART = TX + "::test_any_part_whose_bytes_look_like_xml_is_scanned_whatever_its_name"
NODES = TX + "::test_comments_and_processing_instructions_count_in_the_element_budget"
CT_ROOT = TX + "::test_a_content_types_part_whose_root_is_not_the_opc_types_is_not_xlsx"
EMPTY_ROW = '("", "", "", "", "")'


# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (경계, 번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    (1, "P1", "머리 대조의 차례 무시(다섯 이름이 섞여도 머리)",
     [(READER, swap("        if stripped[start : start + len(HEADER)] == HEADER:\n",
                    "        if sorted(map(str, stripped[start : start + len(HEADER)])) == sorted(HEADER):\n"))],
     [(PURE, [TX], {f"{REJ}[header_order]"})]),
    (1, "P2", "XML 훑기를 워크시트만",
     [(READER, swap("        if _looks_like_xml(entry):\n",
                    '        if name.startswith("xl/worksheets/") and _looks_like_xml(entry):\n'))],
     [(PURE, [TX], {f"{DOCTYPE}[xl/styles.xml]", f"{ANY_PART}[plain]"})]),
    (1, "P2b", "같은 이름 항목 거절 뺌",
     [(READER, swap("        if entry.filename in sizes:  # 같은 이름이 둘이면", "        if False:  # 같은 이름이 둘이면"))],
     [(PURE, [TX], {TX + "::test_a_zip_with_two_entries_of_the_same_name_is_unsafe"})]),
    (1, "P2c", "주석·처리 지시를 요소 수에서 뺌",
     [(READER, swap("    def on_node(*_: object) -> None:  # 주석·처리 지시\n        last[0] = parser.CurrentByteIndex\n"
                    "        count(1)\n",
                    "    def on_node(*_: object) -> None:  # 주석·처리 지시\n        last[0] = parser.CurrentByteIndex\n"))],
     [(PURE, [TX], {f"{NODES}[comment]", f"{NODES}[pi]"})]),
    (1, "P2d", "[Content_Types].xml 뿌리 검사 뺌",
     [(READER, swap('        if name != f"{_CT_NS} Types":\n', "        if False:\n"))],
     [(PURE, [TX], {f"{CT_ROOT}[no_namespace]", f"{CT_ROOT}[other_name]"})]),
    (1, "P2e", "옮긴 상수 하나를 glossary 와 다르게(MAX_XML_DEPTH 65)",
     [(READER, swap("MAX_XML_DEPTH: Final = 64\n", "MAX_XML_DEPTH: Final = 65\n"))],
     [(PURE, [TW], {TW + "::test_the_copied_limits_and_tables_have_the_same_value[MAX_XML_DEPTH]"})]),
    (1, "P2f", "병합 채움 뺌",
     [(READER, swap("                if _blank(cells[column]):\n", "                if False:\n"))],
     [(PURE, [TX], {TX + "::test_a_merge_fills_its_blank_cells_from_the_top_left"})]),
    (1, "P2g", "숨은 시트를 고름",
     [(READER, swap('            visible = [s for s in sheets if s.sheet_state == "visible"]\n',
                    "            visible = list(sheets)\n"))],
     [(PURE, [TX], {TX + "::test_a_hidden_value_chain_sheet_is_skipped_for_the_first_visible_sheet",
                    TX + "::test_without_a_value_chain_name_the_first_visible_sheet_is_read"})]),
    (1, "P3", "거절 message 에 칸 값",
     [(READER, swap('            "too_long", f"{row}행의 {HEADER[column]} 칸이 너무 길어요',
                    '            "too_long", f"{row}행의 {HEADER[column]} 칸({text})이 너무 길어요'))],
     [(PURE, [TX], {TX + "::test_rejection_messages_never_carry_cell_values", f"{REJ}[unit_long]"})]),
    (1, "P4", "응답 ok:true 의 행에 6번째 칸",
     [(ACTION, swap('                        "business_activity": activity,\n',
                    '                        "business_activity": activity,\n                        "extra": "",\n'))],
     [(BUSINESS, [TA], {TA + "::test_a_table_is_read_into_rows"})]),
    (1, "P5", "권한 칸 뺌",
     [(PERM, swap('    "materiality_value_chain_read": COMPANY,\n', ""))],
     [(PURE, [TP], {TP + "::test_the_table_is_these_needs"}),
      (SECURITY, [SM], {SM + "::test_an_operator_bearer_with_two_companies_reads_the_value_chain_without_touching_runs"})]),
    (1, "PR1", "러너 몫: 사업 부문이 있어도 빈 사업 내용을 위에서 물려받음(감독 10-28 (나) 어김)",
     [(READER, swap("            if found and not unit:",
                    "            if found:\n                description = description or found[-1][1]\n"
                    "            if found and not unit:"))],
     [(PURE, [TX], {TX + "::test_a_new_unit_with_an_empty_description_keeps_it_empty"})]),
    (1, "PR2", "러너 몫: 건너뛴 행도 데이터 행 번호에 셈",
     [(READER, swap("            if all(_blank(c) for c in five[2:]):\n                continue\n",
                    "            if all(_blank(c) for c in five[2:]):\n"
                    f"                found.append(found[-1] if found else {EMPTY_ROW})\n                continue\n"))],
     [(PURE, [TX], {TX + "::test_skipped_rows_are_not_counted_in_the_row_number"})]),
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
