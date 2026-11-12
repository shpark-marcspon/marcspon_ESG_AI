#!/usr/bin/env bash
# 밴드 DVX1 의 심은 파손 — 서버 몫(발주서 band-handoffs/DVX1-order.md §3 P1~P9·P14~P16, + 러너 몫 PR1, ② 의 R1·R2 몫 PR2·PR3, 가지 리뷰 B1 몫 PR4·PR5). 웹 몫
# (P10~P13)은 apps/web/scripts/planted-breaks-DVX1.sh. 틀은 planted-breaks-IRW2.sh 그대로: 하나씩 심고 겨눈 시험만 돌린
# 뒤 원본 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — try/finally, SIGTERM·SIGINT 도 finally 를 지난다).
#   apps/api-py/scripts/planted-breaks-DVX1.sh [--commit <n>] [--with-containers] [--only P1,P4]
#   --commit 은 받기만 한다(서버 몫은 전부 경계 ①).
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 업무·보안 층(Postgres)은 --with-containers 일 때만 —
# 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다. 끝에 심은 파일의 sha256 과 git status 가 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: DVX1_OUT(기본: 워크트리 곁의 DVX1.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${DVX1_OUT:-$(cd "$ROOT/.." && pwd)/DVX1.out}"
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


READER = Path("esgapi/dataverify/tools/edk_xlsx.py")
API = Path("esgapi/dataverify/service/apis/dataverify.py")
PERM = Path("esgapi/core/permissions.py")
TX = "esgapi/dataverify/tests/tools/test_edk_xlsx.py"
TW = "esgapi/dataverify/tests/tools/test_edk_xlsx_twin.py"
TU = "esgapi/dataverify/tests/tools/test_edk_xlsx_purity.py"
TA = "esgapi/dataverify/tests/service/apis/test_dataverify_edk.py"
TP = "esgapi/core/tests/test_permissions.py"
SD = "tests/security/test_dataverify.py"
REJ = TX + "::test_each_rejection_has_its_kind_row_column_and_sentence"
DOCTYPE = TX + "::test_a_doctype_in_any_part_openpyxl_opens_is_unsafe"
ANY_PART = TX + "::test_any_part_whose_bytes_look_like_xml_is_scanned_whatever_its_name"
YEARS = TX + "::test_year_columns_are_keyed_by_the_header_without_the_suffix"
COMPANY = TX + "::test_the_company_book_keeps_only_the_target_theme_and_counts_the_rest"
ITEM = TX + "::test_an_item_has_the_eleven_keys_in_order_and_normalised_values"
YEAR_422 = TA + "::test_a_year_off_the_shape_is_422"


# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (경계, 번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    (1, "P1", "정수 float → int 바꿈 뺌",
     [(READER, swap("        if cell.is_integer() and abs(cell) < _EXACT_FLOAT_LIMIT:\n            return int(cell)\n", ""))],
     [(PURE, [TX], {TX + "::test_an_integral_float_written_in_the_file_is_read_as_int"})]),
    (1, "P2", "「공시」를 실음",
     [(READER, swap('REQUIRED: Final = ("ID", "테마", "항목", "대분류", "중분류", "소분류", "입력 방식", "단위", "메모", "핵심데이터")',
                    'REQUIRED: Final = ("ID", "테마", "항목", "대분류", "중분류", "소분류", "입력 방식", "단위", "메모", "핵심데이터", "공시")')),
      (READER, swap('    "핵심데이터",\n    "메모",\n)\n', '    "핵심데이터",\n    "메모",\n    "공시",\n)\n'))],
     [(PURE, [TX], {COMPANY, ITEM})]),
    (1, "P3", "빈 행 건너뜀 뺌",
     [(READER, swap("                empty += 1\n                continue\n", "                pass\n"))],
     [(PURE, [TX], {COMPANY, f"{REJ}[no_rows]"})]),
    (1, "P4", "연도 열쇠에 「년」 남김",
     [(READER, swap("            year = name[:-1]\n", "            year = name\n"))],
     [(PURE, [TX], {f"{YEARS}[years0]", f"{YEARS}[years1]", f"{YEARS}[years2]", COMPANY})]),
    (1, "P5", "XML 훑기를 워크시트만",
     [(READER, swap("        if _looks_like_xml(entry):\n",
                    '        if name.startswith("xl/worksheets/") and _looks_like_xml(entry):\n'))],
     [(PURE, [TX], {f"{DOCTYPE}[xl/styles.xml]", f"{ANY_PART}[plain]"})]),
    (1, "P6", "옮긴 상수 하나를 glossary 와 다르게(MAX_XML_DEPTH 65)",
     [(READER, swap("MAX_XML_DEPTH: Final = 64\n", "MAX_XML_DEPTH: Final = 65\n"))],
     [(PURE, [TW], {TW + "::test_the_copied_limits_and_tables_have_the_same_value[MAX_XML_DEPTH]"})]),
    (1, "P7", "거절 message 에 칸 값(항목 이름)",
     [(READER, swap('"no_theme", f"{row}행의 테마 칸이 비어 있어요."', '"no_theme", f"{row}행({found[\'항목\']})의 테마 칸이 비어 있어요."'))],
     [(PURE, [TX], {TX + "::test_rejection_messages_never_carry_cell_values", f"{REJ}[theme_empty]"})]),
    (1, "P8", "읽기 권한 칸 뺌",
     [(PERM, swap('    "dataverify_edk_read": COMPANY,\n', ""))],
     [(PURE, [TP], {TP + "::test_the_table_is_these_needs"}),
      (SECURITY, [SD], {SD + "::test_the_edk_read_is_401_without_a_session_and_an_operator_reads_without_touching_runs"})]),
    (1, "P9", "read_only=False",
     [(READER, swap("load_workbook(io.BytesIO(data), read_only=True, data_only=True)",
                    "load_workbook(io.BytesIO(data), read_only=False, data_only=True)"))],
     [(PURE, [TU], {TU + "::test_the_reader_opens_the_workbook_read_only_with_values"})]),
    (1, "P14", "다른 테마도 실음",
     [(READER, swap("            if theme not in THEMES:\n", "            if False:\n")),
      (READER, swap("        data={theme: target[theme] for theme in THEMES if theme in target},\n", "        data=dict(target),\n"))],
     [(PURE, [TX], {COMPANY}),
      (BUSINESS, [TA], {TA + "::test_a_book_is_read_into_the_target_theme_data"})]),
    (1, "P15", "양식 권한 칸 뺌",
     [(PERM, swap('    "dataverify_edk_template": COMPANY,\n', ""))],
     [(PURE, [TP], {TP + "::test_the_table_is_these_needs"}),
      (SECURITY, [SD], {SD + "::test_the_edk_template_is_401_without_a_session_and_an_operator_downloads_without_touching_runs"})]),
    (1, "P16", "year 검사 뺌",
     [(API, swap("default=None, ge=1002, le=9999, description=", "default=None, description="))],
     [(BUSINESS, [TA], {f"{YEAR_422}[1001]", f"{YEAR_422}[10000]", f"{YEAR_422}[-1]"})]),
    (1, "PR1", "러너 몫: 항목 상한을 거른 뒤 셈(대상 테마만 셈)",
     [(READER, swap("            total += 1\n", "            total += item[THEME_COLUMN] in THEMES\n"))],
     [(PURE, [TX], {TX + "::test_the_limits_count_items_before_the_theme_filter", f"{REJ}[no_target_theme]"})]),
    (1, "PR2", "러너 몫(② R1): 정수 float → int 를 2**53 밖에도",
     [(READER, swap("        if cell.is_integer() and abs(cell) < _EXACT_FLOAT_LIMIT:\n", "        if cell.is_integer():\n"))],
     [(PURE, [TX], {TX + "::test_an_integral_float_beyond_two_to_the_53_stays_a_float"})]),
    (1, "PR3", "러너 몫(② R2): 수로 적은 연도 머리를 읽지 않는 열로",
     [(READER, swap("        elif isinstance(name, int) and not isinstance(name, bool) and YEAR_NUMBER_MIN <= name <= YEAR_NUMBER_MAX:\n",
                    "        elif False:\n"))],
     [(PURE, [TX], {TX + "::test_a_year_header_written_as_a_number_is_a_year_column",
                    TX + "::test_a_number_year_header_and_the_same_year_as_text_overlap"})]),
    (1, "PR4", "가지 리뷰 B1a: 칸 글자 수 상한 뺌",
     [(READER, swap("        if len(cell) > MAX_CELL_CHARS:\n", "        if False:\n"))],
     [(PURE, [TX], {TX + "::test_one_long_shared_string_behind_many_cells_is_a_long_cell_fast",
                    TX + "::test_the_cell_length_limit_is_inclusive"})]),
    (1, "PR5", "가지 리뷰 B1b: 실을 글자·수 합 상한 뺌",
     [(READER, swap("            if octets > OPTIONS_MAX_OCTETS:\n", "            if False:\n"))],
     [(PURE, [TX], {TX + "::test_short_strings_reused_over_the_options_limit_stop_as_converted_too_large_fast"})]),
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
