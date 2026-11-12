"""원본 대조(게이트 밖, 손으로 한 번). pytest 가 모으지 않는다(파일 이름이 test_ 로 시작하지 않는다).

    cd apps/api-py && uv run --frozen python -m esgapi.inventory.tests.s3sheets_probe "<계수 책 xlsx>" "<템플릿 xlsx>" \
        [--scan <더 훑을 파일> ...]

받은 두 xlsx(저장소 밖, 읽기 전용)를 읽개·적재기·드롭다운·검사에 넣어 **건수와 `시트!칸` 자리만** 찍는다.
계수의 값·항목 이름·표준코드·사전의 낱말은 찍지 않는다(옵션으로도 없다). 찍힌 것을 파일로 떠 두지 않는다.

하는 일 셋:
  ① 대조표: 발주서(밴드 S3a) §3 의 표와 줄마다 같은가(아래 EXPECTED. 2026-10-13 에 두 파일에서 센 수).
  ② 칸 회계: 계수 책의 칸이 갈래별로 몇이고 어디에도 안 든 칸이 0 인가.
  ③ 옮김 훑기: 원본의 값(수 칸의 글자, 5자 이상)과 이름(글자 칸, 4자 이상. 시트 이름·머리글·정의된 이름·유효성 식·
     단위 표기·매핑검토의 묶음 이름은 꼴이라 뺀다)이 이 밴드가 만든 파일에 글자 그대로 있는가. 0 이어야 한다.
     꼴의 글자(시트 이름·머리글)의 부분 글자인 것은 옮김으로 세지 않고 따로 센다. README 는 이 밴드의 소절만 본다.
     수와 영문 낱말은 낱말로서 있을 때만 센다(`_appears`).
     칸의 글을 쉼표·줄바꿈·`|`·`/`·가운뎃점으로 나눈 조각도 찾는다.
     영어 낱말만으로 된 글자는 수만 세고 옮김으로 치지 않는다(코드의 낱말과 우연히 같기 쉽다 — 이 훑기의 구멍이다).
마지막 줄 `PROBE=PASS|FAIL`. 종료 코드는 PASS 면 0.

무효 조건: 원본이 새 판으로 바뀌면 EXPECTED 와 꼴 자료를 다시 센다.
"""

import re
import sys
from pathlib import Path

from esgapi.inventory.tools.scope3_sheets import dropdowns as dd
from esgapi.inventory.tools.scope3_sheets.crosscheck import (
    AbsentCategoryNumbers,
    CheckSkipped,
    DuplicateKey,
    ListComparison,
    Located,
    MappingComparison,
    SheetIndexProblem,
    UnitTextPairs,
    crosscheck,
)
from esgapi.inventory.tools.scope3_sheets.factor_layout import FACTOR_SHEETS, INDEX_SHEET
from esgapi.inventory.tools.scope3_sheets.factors import FactorBook, Placeholder, Unaccounted, load_factor_book
from esgapi.inventory.tools.scope3_sheets.grid import FormulaCell, NumberCell, TextCell, Workbook
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

# 발주서 §3 의 대조표(건수뿐이다).
EXPECTED: dict[str, object] = {
    "읽개·책": (11, 3829, 654, 24, 630),  # 시트 · 칸 · 수식 · 으뜸 · 딸린
    "읽개·템플릿": (23, 1937, 11, 1, 10, 11, 39),  # … · 정의된 이름 · 유효성
    "책·행": 403,
    "책·숫자 값 칸": 591,
    "책·`-`": 8,
    "책·수식 칸": 654,
    "책·안 든 칸": 0,
    "드롭다운·이름의 길이": {
        "DD_PURCHASE_GROUP": 17,
        "DD_ENERGY": 14,
        "DD_ENERGY_UNIT": 5,
        "DD_TRANSPORT_DISTANCE": 7,
        "DD_TRANSPORT_SPEND": 27,
        "DD_TRAVEL_DISTANCE": 33,
        "DD_TRAVEL_SPEND": 14,
        "DD_WASTE_C5_TYPE": 16,
        "DD_WASTE_METHOD": 4,
        "DD_WASTE_UNIT": 2,
        "DD_TRANSPORT_WEIGHT_UNIT": 2,
    },
    "드롭다운·표준코드": 33,
    "드롭다운·C12 AG 칸(머리글 포함)": 72,
    "드롭다운·사전 줄": 120,
    "드롭다운·유효성의 꼴": {"defined_name": 32, "range": 1, "offset": 2, "quoted_list": 1, "number_range": 3},
    "드롭다운·문제": 0,
    # (목록 쪽 수, 같음, 목록에만, 책에만, near)
    "K1": (17, 14, 3, 3, 0),
    "K2": (14, 13, 1, 1, 0),
    "K3": (14, 6, 8, 6, 0),
    "K4a": (5, 4, 1, 1, 0),
    "K4b": (5, 4, 1, 0, 0),
    "K5": (7, 6, 1, 0, 0),
    "K6": (27, 17, 10, 0, 0),
    "K7": (33, 11, 22, 0, 0),
    "K8": (14, 11, 3, 0, 0),
    "K9": (64, 63, 1, 0, 0),
    "K9·겹친 짝": 2,
    "K10a": (71, 70, 1, 0, 0),
    "K10b": (71, 70, 1, 0, 0),
    "K11·unit 을 뺀 줄 · 그 가운데 없는 것": (104, 10),
    "K11·없는 것(묶음별)": {"transport_spend": 9, "energy": 1},
    "K11·unit(목록별 없는 것)": {"DD_ENERGY_UNIT": 3, "DD_WASTE_UNIT": 12, "DD_TRANSPORT_WEIGHT_UNIT": 12},
    "K11·(묶음, 기존값) 겹침": 0,
    "K13": (21, True, 1),  # 템플릿 탭 · 차례까지 같음 · 책 쪽 탭이 시트가 아닌 줄
    "K14": (10,),
    "K15": (6, 2),  # 짝 · 단위의 글자가 다른 짝
    "재지 못한 검사": 0,
}


def _places(items: tuple[Located, ...]) -> str:
    return " ".join("·".join(item.where) for item in items) if items else "—"


def _formulas(workbook: Workbook) -> tuple[int, int, int]:
    cells = [cell for sheet in workbook.sheets for cell in sheet.cells.values() if isinstance(cell, FormulaCell)]
    masters = sum(1 for cell in cells if cell.formula is not None)
    return len(cells), masters, len(cells) - masters


def _measure(book: Workbook, template: Workbook) -> tuple[dict[str, object], FactorBook]:
    got: dict[str, object] = {}
    got["읽개·책"] = (len(book.sheets), sum(len(sheet.cells) for sheet in book.sheets), *_formulas(book))
    got["읽개·템플릿"] = (
        len(template.sheets),
        sum(len(sheet.cells) for sheet in template.sheets),
        *_formulas(template),
        len(template.defined_names),
        sum(len(sheet.validations) for sheet in template.sheets),
    )
    factors = load_factor_book(book)
    contents = [entry.content for row in factors.rows for entry in row.values]
    got["책·행"] = len(factors.rows)
    got["책·숫자 값 칸"] = sum(1 for content in contents if isinstance(content, NumberCell))
    got["책·`-`"] = sum(1 for content in contents if isinstance(content, Placeholder) and content.text == "-")
    got["책·수식 칸"] = sum(len(row.derived) for row in factors.rows)
    got["책·안 든 칸"] = sum(1 for problem in factors.problems if isinstance(problem, Unaccounted))
    print(
        "── 칸 회계(계수 책) ──  시트: 칸 = 제목·머리글 + 이름표 + 값 + 파생 + 덧붙은 칸 + 주석 + 탭 안내 (+ 안 든 칸)"
    )
    for account in factors.accounts:
        rows = sum(1 for row in factors.rows if row.sheet == account.sheet)
        print(
            f"  {account.sheet}: {account.total} = {account.title_header} + {account.label} + {account.value} + "
            f"{account.derived} + {account.extra} + {account.note} + {account.link} (+ {account.unaccounted})"
            f"   행 {rows}"
        )
    total = sum(account.total for account in factors.accounts)
    print(f"  합: 칸 {total} · 적재된 시트 {len(factors.accounts)}/{len(FACTOR_SHEETS) + 1}")
    extras = [f"{row.sheet}!{entry.column}{row.row}" for row in factors.rows for entry in row.extras]
    print(f"  덧붙은 칸의 자리: {' '.join(extras) if extras else '—'}")
    print(f"  주석 칸의 자리: {' '.join(f'{note.sheet}!{note.cell}' for note in factors.notes) or '—'}")
    print(f"  적재기의 문제: {len(factors.problems)}건 {[type(problem).__name__ for problem in factors.problems]}")
    for problem in factors.problems:
        print(f"    {type(problem).__name__} {problem.sheet} {getattr(problem, 'cell', '')}")

    drops = dd.read_dropdowns(template)
    got["드롭다운·이름의 길이"] = {named.name: len(named.items) for named in drops.named_lists}
    got["드롭다운·표준코드"] = len(drops.travel_codes)
    got["드롭다운·C12 AG 칸(머리글 포함)"] = sum(1 for item in drops.c12.minor if item.item is not None) + 1
    got["드롭다운·사전 줄"] = len(drops.mapping_review.entries)
    shapes: dict[str, int] = {}
    for validation in drops.validations:
        shapes[validation.shape] = shapes.get(validation.shape, 0) + 1
    got["드롭다운·유효성의 꼴"] = shapes
    got["드롭다운·문제"] = len(drops.problems)
    for problem in drops.problems:
        print(f"  드롭다운의 문제: {problem.kind} {problem.where}")
    groups: dict[str, int] = {}
    for entry in drops.mapping_review.entries:
        groups[str(entry.group)] = groups.get(str(entry.group), 0) + 1
    print(
        f"── 드롭다운 ──  C12 목록 AA {len(drops.c12.major)} · AC·AD {len(drops.c12.middle)}"
        f" · AF·AG {len(drops.c12.minor)}"
    )
    print(f"  사전의 묶음별 줄 수: {groups} · 요약 줄 {len(drops.mapping_review.summary)}")

    print("── 어긋남(자리만) ──")
    absent_by_group: dict[str, int] = {}
    unit_absent: dict[str, int] = {}
    non_unit_total = 0
    duplicates = {"K9": 0, "K11": 0}
    skipped = 0
    for finding in crosscheck(factors, drops, drops.sheet_names):
        if isinstance(finding, ListComparison):
            got[finding.check] = (
                finding.list_total,
                len(finding.matched),
                len(finding.template_only),
                len(finding.db_only),
                len(finding.near),
            )
            print(f"  {finding.check} 목록에만: {_places(finding.template_only)}")
            print(f"  {finding.check} 책에만: {_places(finding.db_only)}")
        elif isinstance(finding, DuplicateKey):
            duplicates[finding.check] = duplicates.get(finding.check, 0) + 1
            print(f"  {finding.check} 같은 열쇠의 줄들: {' '.join(finding.where)}")
        elif isinstance(finding, MappingComparison):
            if finding.group == "unit":
                unit_absent[finding.target_list] = len(finding.absent)
            else:
                non_unit_total += finding.total
                if finding.absent:
                    absent_by_group[finding.group] = len(finding.absent)
            print(
                f"  K11 {finding.group} ↔ {finding.target_list}: {finding.total}줄 가운데 없는 것"
                f" {_places(finding.absent)}"
            )
        elif isinstance(finding, SheetIndexProblem):
            got["K13"] = (finding.template_tabs, finding.same_order, len(finding.book_tabs_not_sheets))
            print(
                f"  K13 다른 줄: {_places(finding.mismatched)}"
                f" · 시트가 아닌 책 쪽 탭: {_places(finding.book_tabs_not_sheets)}"
            )
        elif isinstance(finding, AbsentCategoryNumbers):
            got["K14"] = finding.absent
        elif isinstance(finding, UnitTextPairs):
            got["K15"] = (len(finding.pairs), finding.differing)
            differing = [f"{p.left_where}↔{p.right_where}" for p in finding.pairs if p.left_unit != p.right_unit]
            print(f"  K15 단위의 글자가 다른 짝: {' '.join(differing) or '—'}")
        else:
            assert isinstance(finding, CheckSkipped)
            skipped += 1
            print(f"  ★ 재지 못함 {finding.check}: {finding.reason}")
    got["K9·겹친 짝"] = duplicates["K9"]
    got["K11·unit 을 뺀 줄 · 그 가운데 없는 것"] = (non_unit_total, sum(absent_by_group.values()))
    got["K11·없는 것(묶음별)"] = absent_by_group
    got["K11·unit(목록별 없는 것)"] = unit_absent
    got["K11·(묶음, 기존값) 겹침"] = duplicates["K11"]
    got["재지 못한 검사"] = skipped
    return got, factors


def _shape_texts(book: Workbook, template: Workbook, factors: FactorBook) -> set[str]:
    """꼴이라 훑지 않는 글자: 시트 이름, 머리글, 정의된 이름, 유효성 식, 단위 표기, 매핑검토의 묶음 이름."""
    shape: set[str] = {sheet.name for sheet in (*book.sheets, *template.sheets)}
    shape |= {INDEX_SHEET.template_header, INDEX_SHEET.book_header}
    unit_columns: dict[str, set[str]] = {}
    for layout in FACTOR_SHEETS:
        shape |= {column.header for column in layout.columns} | {header for _, header in layout.group_headers}
        unit_columns[layout.name] = {column.letter for column in layout.columns if column.role == "unit"}
    for row in factors.rows:
        for entry in row.labels:
            if entry.column in unit_columns.get(row.sheet, set()) and isinstance(entry.cell, TextCell):
                shape.add(entry.cell.text)
    for headers in (dd.TRAVEL_CODE_HEADERS, dd.C12_HEADERS, dd.MAPPING_SUMMARY_HEADERS, dd.MAPPING_HEADERS):
        shape |= {header for _, header in headers}
    drops = dd.read_dropdowns(template)
    shape |= {defined.name for defined in template.defined_names}
    shape |= {text for v in drops.validations for text in (v.formula1, v.formula2) if text is not None}
    shape |= {item.text for named in drops.named_lists if named.name.endswith("_UNIT") for item in named.items}
    shape |= {str(entry.group) for entry in drops.mapping_review.entries}
    shape |= {str(entry.new) for entry in drops.mapping_review.entries if entry.group == "unit"}
    shape |= {str(entry.old) for entry in drops.mapping_review.entries if entry.group == "unit"}
    return shape


def _needles(book: Workbook, template: Workbook, shape: set[str]) -> dict[str, str]:
    """찾을 글자 → 그 글자가 있던 자리 하나(`시트!칸`)."""
    needles: dict[str, str] = {}
    for workbook in (book, template):
        for sheet in workbook.sheets:
            for address, cell in sheet.cells.items():
                where = f"{sheet.name}!{address}"
                contents = [cell.cached] if isinstance(cell, FormulaCell) else [cell]
                for content in contents:
                    if isinstance(content, TextCell) and content.text not in shape:
                        # 칸 통째와, 그 글을 쉼표·줄바꿈·`|`·`/`·가운뎃점으로 나눈 조각을 찾는다.
                        for piece in (content.text, *re.split(r"[,\n|/·]", content.text)):
                            piece = piece.strip() if piece != content.text else piece
                            if len(piece) >= 4 and piece not in shape:
                                needles.setdefault(piece, where)
                    elif isinstance(content, NumberCell):
                        for digits in (content.xml_text, content.decimal):
                            if len(digits) >= 5:
                                needles.setdefault(digits, where)
    return needles


def _band_files(extra: list[Path]) -> list[Path]:
    """이 밴드가 만들거나 고친 파일(저장소 안의 것은 정해진 자리에서 모은다)."""
    api = Path(__file__).resolve().parents[3]
    inventory = api / "esgapi" / "inventory"
    files = [
        *sorted((inventory / "tools" / "scope3_sheets").glob("*.py")),
        inventory / "tools" / "xlsx_reader.py",
        inventory / "__init__.py",
        *sorted((inventory / "tests").glob("test_s3sheets_*.py")),
        *sorted((inventory / "tests").glob("s3sheets_*.py")),
        api / "scripts" / "section4-S3a.sh",
        api / "scripts" / "planted-breaks-S3a.sh",
        api.parents[1] / "README.md",
        *extra,
    ]
    return [path for path in files if path.is_file()]


README_HEADING = "### Scope 3 시트 읽기"


def _scanned_text(path: Path) -> str:
    """훑을 글. README 는 이 밴드가 더한 소절만 본다(그 밖의 줄은 이 밴드의 글이 아니다)."""
    content = path.read_text(encoding="utf-8")
    if path.name != "README.md":
        return content
    lines = content.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith(README_HEADING)]
    if not starts:
        return ""
    rest = lines[starts[0] + 1 :]
    end = next((index for index, line in enumerate(rest) if line.startswith(("## ", "### "))), len(rest))
    return "\n".join(rest[:end])


def _appears(needle: str, content: str) -> bool:
    """그 글자가 글 안에 **낱말로서** 있는가.

    한글이 든 글자는 부분 글자로 찾는다. 수는 앞뒤가 숫자·소수점이 아닐 때만(긴 수의 가운데 토막은 그 수가 아니다),
    영문·숫자만으로 된 낱말은 앞뒤가 영문·숫자·밑줄이 아닐 때만 센다(`trailing` 안의 네 글자는 그 낱말이 아니다).
    """
    if needle not in content:
        return False
    if re.fullmatch(r"-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?", needle) is not None:
        return re.search(rf"(?<![0-9.]){re.escape(needle)}(?![0-9]|\.[0-9])", content) is not None
    if re.fullmatch(r"[A-Za-z0-9_]+", needle) is not None:
        return re.search(rf"(?<![A-Za-z0-9_]){re.escape(needle)}(?![A-Za-z0-9_])", content) is not None
    return True


def _scan(needles: dict[str, str], shape: set[str], files: list[Path]) -> tuple[int, int, int]:
    """(옮김, 꼴의 글자 안에 든 것).

    원본의 글자가 꼴(시트 이름·머리글 등)의 부분 글자이면 옮김으로 세지 않고 따로 센다.
    """
    moved = 0
    inside_shape = 0
    english = 0
    for path in files:
        content = _scanned_text(path)
        for needle, where in sorted(needles.items(), key=lambda pair: pair[1]):
            if not _appears(needle, content):
                continue
            if any(needle in text for text in shape):
                inside_shape += 1
                print(f"  (꼴의 글자 안에 든 글자) {path.name}: 원본의 자리 {where}")
            elif re.fullmatch(r"[A-Za-z][A-Za-z ]*", needle) is not None:
                # 영어 낱말만으로 된 글자(키워드 칸의 조각 등)는 코드의 낱말과 우연히 같기 쉽다.
                # 세되 옮김으로 치지 않는다.
                english += 1
            else:
                moved += 1
                print(f"  ★ 옮김 {path.name}: 원본의 자리 {where}")
    return moved, inside_shape, english


def main(arguments: list[str]) -> int:
    if len(arguments) < 2 or (len(arguments) > 2 and arguments[2] != "--scan"):
        print(__doc__)
        return 2
    extra = [Path(argument) for argument in arguments[3:]]
    book = read_workbook(Path(arguments[0]).read_bytes())
    template = read_workbook(Path(arguments[1]).read_bytes())
    if isinstance(book, ReaderProblem) or isinstance(template, ReaderProblem):
        for name, result in (("계수 책", book), ("템플릿", template)):
            if isinstance(result, ReaderProblem):
                print(f"읽개가 거절했다 — {name}: {result.kind} {result.where} {result.detail}")
        print("PROBE=FAIL")
        return 1
    got, factors = _measure(book, template)
    print("── 대조표 ──")
    different = 0
    for key, expected in EXPECTED.items():
        same = got.get(key) == expected
        different += 0 if same else 1
        print(
            f"  {'같다 ' if same else '★ 다르다'} {key}: {got.get(key)}" + ("" if same else f"   (발주서: {expected})")
        )
    print("── 옮김 훑기 ──")
    shape = _shape_texts(book, template, factors)
    needles = _needles(book, template, shape)
    files = _band_files(extra)
    hits, inside_shape, english = _scan(needles, shape, files)
    print(f"  영어 낱말만으로 된 글자와 같은 낱말(옮김으로 치지 않는다. 자리를 찍지 않는다): {english}")
    print(
        f"  찾은 글자 {len(needles)}가지 · 훑은 파일 {len(files)} · 옮김 {hits} · 꼴의 글자 안에 든 것 {inside_shape}"
    )
    passed = different == 0 and hits == 0
    print(f"대조표에서 다른 줄 {different}/{len(EXPECTED)} · 안 든 칸 {got['책·안 든 칸']} · 옮김 {hits}")
    print(f"PROBE={'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
