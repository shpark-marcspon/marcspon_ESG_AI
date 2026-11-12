"""심은 파손 (밴드 PD2 §3, PX 가 16~22 를, PX2 가 23~27 을, TRD1 이 28~35(발주서의 P1~P8)를, TRD2 가 36~39(발주서의 K1~K4)를 더함). `scripts/section4-PD2.sh planted`·`apps/api-py/scripts/section4-PX.sh` 가
부른다. 저장소 뿌리에서 돈다. 인자로 번호를 주면 그 파손만 심는다.

파손 하나마다: 파일을 고친다 → 테스트를 돌린다 → 빨개진 테스트를 적는다 → 파일을 처음 바이트로 되돌린다.
git 으로 되돌리지 않는다(읽어 둔 바이트를 도로 쓴다). 끝나면 작업 트리의 해시가 처음과 같은지 본다.

환경 변수: G(골든이 든 폴더. `section4-PD2.sh` 가 만든 것), REPORTS(공개 보고서 PDF). 둘이 없으면 네 문서·정답이 필요한
파손(5, 6)은 「못 쟀다」로 적고 실패로 센다.
종료 코드: 기대와 다른 파손이 있거나 작업 트리가 처음과 다르면 1.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "services" / "parser"
G = os.environ.get("G")
REPORTS = os.environ.get("REPORTS")
ENGINE, APP = P / "docparse/engine/pdfium_engine.py", P / "app.py"
TABLES, READING, LAYOUT = P / "docparse/tables_lines.py", P / "docparse/reading_order.py", P / "docparse/layout.py"
DOCUMENT, ANNOTATE = P / "docparse/document.py", P / "docparse/annotate.py"
BLOCKS = P / "docparse/blocks.py"
TABLES_ALL = P / "docparse/tables.py"


def tree_hash():
    h = hashlib.sha256()
    for base in (P, ROOT / "docker", ROOT / "scripts", ROOT / "tests" / "integration"):
        for path in sorted(base.rglob("*")):
            if path.is_file() and not ({".venv", "__pycache__", ".pytest_cache", "node_modules"} & set(path.parts)):
                h.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes())
    h.update((ROOT / "compose.yaml").read_bytes())
    return h.hexdigest()


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("PARSER_REPORTS_DIR", "PARSER_GOLD_DIR")}
    env.update(extra)
    return env


def pytest(*args, **env):
    """(빨간가, 빨개진 테스트 이름들, 마지막 줄)"""
    done = subprocess.run(
        ["uv", "run", "--project", str(P), "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", str(P), *args],
        cwd=ROOT,
        env=clean_env(**env),
        capture_output=True,
        text=True,
    )
    names = [
        m.group(2).split("::", 1)[-1] if "::" in m.group(2) else m.group(2)
        for m in re.finditer(r"^(FAILED|ERROR) (\S+)", done.stdout, re.M)
    ]
    files = sorted(
        {m.group(2).split("::")[0].split("/")[-1] for m in re.finditer(r"^(FAILED|ERROR) (\S+)", done.stdout, re.M)}
    )
    last = (done.stdout.strip().splitlines() or [""])[-1]
    return done.returncode != 0, names, files, last


def unit():
    return pytest()


def gold_reports():
    if not G or not REPORTS:
        return None
    return pytest("-m", "reports", PARSER_REPORTS_DIR=REPORTS, PARSER_GOLD_DIR=f"{G}/lab/data/gold")


def one_document_against_gold(doc="kb_2025_databook_kor"):
    """문서 하나를 분해해 골든과 견준다. (다른가, 설명)"""
    if not G or not REPORTS:
        return None
    with tempfile.TemporaryDirectory() as out:
        done = subprocess.run(
            [
                "uv",
                "run",
                "--frozen",
                "python",
                "-m",
                "docparse",
                "parse",
                f"{REPORTS}/{doc}.pdf",
                "--out",
                out,
                "--places",
            ],
            cwd=P,
            env=clean_env(),
            capture_output=True,
            text=True,
        )
        if done.returncode != 0:
            return True, f"{doc}: 분해가 실패했다 (EXIT={done.returncode})"
        notes, differs = [], False
        for name in ("document.json", "char-places.json"):
            mine = json.loads((Path(out) / name).read_text(encoding="utf-8"))
            gold = json.loads((Path(G) / "gold" / doc / name).read_text(encoding="utf-8"))
            bell = json.dumps(mine, ensure_ascii=False).count("\u0007") + json.dumps(mine).count("\\u0007")
            differs |= mine != gold
            notes.append(f"{name} {'다름' if mine != gold else '같음'}, U+0007 {bell}자")
        return differs, f"{doc}: " + " / ".join(notes)


def lock_grep():
    """pymupdf 를 더한 pyproject 로 잠그고 §4 의 잠금 grep 을 돌린다. (빨간가, 설명)"""
    locked = subprocess.run(["uv", "lock", "--project", str(P)], cwd=ROOT, capture_output=True, text=True)
    if locked.returncode != 0:
        return None, f"uv lock 실패: {locked.stderr.strip().splitlines()[-1:]}"
    hit = subprocess.run(
        ["grep", "-ciE", "pymupdf|fitz", str(P / "pyproject.toml"), str(P / "uv.lock")], capture_output=True, text=True
    ).stdout.split()
    red = any(int(line.rsplit(":", 1)[1]) for line in hit)
    return red, f"잠금 grep 이 잡은 줄 수 {hit} (이미지는 짓지 않았다: 빌드가 무겁다)"


# (번호, 이름, [(파일, 옛 글, 새 글)], 기대)
PLANTS = [
    (
        1,
        "pdfium_engine 의 y 뒤집기를 뺀다",
        [(ENGINE, "base = {0: (1, 0, 0, -1),", "base = {0: (1, 0, 0, 1),")],
        "unit",
    ),
    (
        2,
        "폼의 행렬을 곱하지 않는다",
        [
            (
                ENGINE,
                "walk(C.FPDFFormObj_CountObjects, C.FPDFFormObj_GetObject, obj, _concat(matrix_of(obj), parent))",
                "walk(C.FPDFFormObj_CountObjects, C.FPDFFormObj_GetObject, obj, parent)",
            )
        ],
        "unit",
    ),
    (3, "줄 끊는 틈 0.8 → 0.7", [(ENGINE, "LINE_BREAK_GAP = 0.8 ", "LINE_BREAK_GAP = 0.7 ")], "unit"),
    (
        4,
        "docparse/layout.py 에 import pymupdf",
        [(P / "docparse/layout.py", "from .engine import Rect\n", "import pymupdf\nfrom .engine import Rect\n")],
        "unit",
    ),
    (
        5,
        "글자 목록에 U+0007 을 도로 넣는다 (가운뎃점 뒤에)",
        [
            (
                ENGINE,
                "                found.append(\n"
                "                    (style[0], i, code, rect.left, rect.bottom, rect.right, rect.top, ox.value, oy.value, style)\n"
                "                )\n",
                "                found.append(\n"
                "                    (style[0], i, code, rect.left, rect.bottom, rect.right, rect.top, ox.value, oy.value, style)\n"
                "                )\n"
                "                if code == 0xB7:\n"
                "                    found.append((style[0], i, 7, rect.right, rect.bottom, rect.right, rect.top, ox.value, oy.value, style))\n",
            )
        ],
        "gold_only",
    ),
    (
        6,
        "괘선 전략을 끈다",
        [(P / "docparse/tables.py", 'if strategy in ("auto", METHOD_LINES):', "if strategy in (METHOD_LINES,):")],
        "reports",
    ),
    (
        7,
        "새 계약에서 스키마 검사를 건너뛴다",
        [
            (
                APP,
                "errors = schema_errors(_DOCUMENT_VALIDATOR, document) + schema_errors(_PLACES_VALIDATOR, places)",
                "errors = []",
            )
        ],
        "unit",
    ),
    (
        8,
        "크기 상한을 뺀다",
        [
            (APP, "if declared.isdigit() and int(declared) > MAX_SOURCE_BYTES:", "if False:"),
            (APP, "        if total > MAX_SOURCE_BYTES:", "        if False:"),
        ],
        "unit",
    ),
    (9, "자물쇠를 뺀다 (분해 일꾼을 여덟으로)", [(APP, "_PARSE_WORKERS = 1", "_PARSE_WORKERS = 8")], "unit"),
    (
        10,
        "분해(자식을 띄우고 기다림)를 이벤트 루프에서 돌린다",
        [
            (
                APP,
                "job = _PARSE_EXECUTOR.submit(run_isolated, data, file_name, *extra)",
                "job = _ran_on_the_loop(data, file_name, *extra)",
            ),
            (
                APP,
                "\nasync def parse_pdf_body(request: Request) -> Response:",
                "\ndef _ran_on_the_loop(data, file_name, *extra):\n    import concurrent.futures\n\n"
                "    done = concurrent.futures.Future()\n    try:\n        done.set_result(run_isolated(data, file_name, *extra))\n"
                "    except BaseException as err:\n        done.set_exception(err)\n    return done\n\n\n"
                "async def parse_pdf_body(request: Request) -> Response:",
            ),
        ],
        "unit",
    ),
    (
        11,
        "file_name=../x.pdf 를 받는다",
        [
            (
                APP,
                'if "/" in text or "\\\\" in text or ".." in text or any(unicodedata.category(c) == "Cc" for c in text):',
                "if False:",
            )
        ],
        "unit",
    ),
    # 12(옛 계약의 응답 꼴)는 옛 약속을 걷으며 걷었다(밴드 PX). 번호는 다시 쓰지 않는다.
    (
        13,
        "pyproject.toml 에 pymupdf 를 더해 잠근다",
        [(P / "pyproject.toml", '    "jsonschema==4.26.0",\n', '    "jsonschema==4.26.0",\n    "pymupdf>=1.26",\n')],
        "lock",
    ),
    (
        14,
        "healthz 를 def 로 되돌리고 스레드 자물쇠로 기다린다",
        [
            (APP, "async def healthz() -> dict[str, str]:", "def healthz() -> dict[str, str]:"),
            (
                APP,
                "        job = _PARSE_EXECUTOR.submit(run_isolated, data, file_name, *extra)\n        job.add_done_callback(_give_slot)\n",
                "",
            ),
            (
                APP,
                "body = await asyncio.wrap_future(job)",
                "body = await run_in_threadpool(_with_thread_lock, data, file_name, *extra)",
            ),
            (
                APP,
                "\ndef decompose(path: Path, opened",
                "\nfrom fastapi.concurrency import run_in_threadpool\n_THREAD_LOCK = threading.Lock()\n\n\n"
                "def _with_thread_lock(data, file_name, *extra):\n"
                "    with _THREAD_LOCK:\n        return run_isolated(data, file_name, *extra)\n\n\ndef decompose(path: Path, opened",
            ),
        ],
        "unit",
    ),
    (
        16,
        "쪽 수 상한을 끈다",
        [(APP, "            if pages > max_pages:", "            if False:")],
        "unit",
    ),
    (
        17,
        "줄 상한을 끈다",
        [(APP, "        if _slots_taken >= _PARSE_WORKERS + MAX_QUEUE:", "        if False:")],
        "unit",
    ),
    (
        18,
        "parse_failed 를 500 으로 되돌린다",
        [(APP, 'raise Rejected(422, "parse_failed",', 'raise Rejected(500, "parse_failed",')],
        "unit",
    ),
    (
        19,
        "옛 갈래를 되살린다 (application/json 의 sourceUrl 을 내려받는다)",
        [
            (
                APP,
                '    if kind == "application/pdf":\n        return await parse_pdf_body(request)\n',
                '    if kind == "application/pdf":\n        return await parse_pdf_body(request)\n'
                '    if kind == "application/json":\n        import urllib.request\n\n'
                '        source = json.loads(await request.body())["sourceUrl"]\n'
                "        with urllib.request.urlopen(source, timeout=1) as fetched:  # noqa: S310\n"
                '            return Response(content=fetched.read(), media_type="application/pdf")\n',
            )
        ],
        "unit",
    ),
    (
        21,
        "산출 검사기를 분해마다 다시 짓는다 (docparse 의 validate 로 되돌린다)",
        [
            (
                APP,
                "errors = schema_errors(_DOCUMENT_VALIDATOR, document) + schema_errors(_PLACES_VALIDATOR, places)",
                "from docparse.document import validate, validate_places\n\n"
                "        errors = validate(document) + validate_places(places)",
            )
        ],
        "unit",
    ),
    (
        22,
        "끊긴 요청의 자리를 요청 끝에서 돌려준다 (도는 자식이 끝나기 전에 — 검증 B8)",
        [
            (APP, "        job.add_done_callback(_give_slot)\n        handed = True\n", ""),
        ],
        "unit",
    ),
    (
        20,
        "시간 상한을 끈다 (자식을 끝까지 기다린다)",
        [(APP, "if not receive.poll(PARSE_TIMEOUT_SECONDS):", "if not receive.poll(None):")],
        "unit",
    ),
    (
        15,
        "charPlaces 를 null 로 낸다",
        [
            (APP, "document, places = decompose(path, opened)", "document, places = decompose(path, opened)[0], None"),
            (APP, "        if places is None:", "        if False:"),
            (APP, "for output in (document, places):", "for output in (document,):"),
            (APP, " + schema_errors(_PLACES_VALIDATOR, places)", ""),
        ],
        "unit",
    ),
    (
        23,
        "PDF 를 두 번 연다 (분해가 경로로 다시 연다 — PX2 ⑦ 앞으로)",
        [
            (
                APP,
                "from docparse.document import parse_opened_places\n",
                "from docparse.document import parse_opened_places, parse_pdf_places\n",
            ),
            (
                APP,
                'return parse_opened_places(opened, path, strategy="auto", dedupe_overdrawn=False)',
                'return parse_pdf_places(path, strategy="auto", dedupe_overdrawn=False)',
            ),
        ],
        "unit",
    ),
    (
        24,
        "표 칸 상한을 끈다 (PX2 ⑧)",
        [(TABLES, "    if cells > MAX_TABLE_CELLS:", "    if False:")],
        "unit",
    ),
    (
        25,
        "표 괘선 상한을 끈다 (PX2 ⑧)",
        [(TABLES, "if len(ghs) + len(gvs) > MAX_TABLE_RULES:", "if False:")],
        "unit",
    ),
    (
        26,
        "읽는 차례를 재귀로 되돌린다 (PX2 ⑧)",
        [
            (
                READING,
                "                todo.extend(reversed(groups))",
                "                out.extend(i for g in groups for i in walk(g))",
            )
        ],
        "unit",
    ),
    (
        27,
        "위첨자 붙이기가 조각 전부를 훑는다 (PX2 ⑧)",
        [
            (
                LAYOUT,
                "        for j in near:\n            base = chunks[j]\n",
                "        for j, base in enumerate(chunks):\n",
            )
        ],
        "unit",
    ),
    # 밴드 TRD1(번역 판 layout 2). 발주서의 P1~P8 = 28~35.
    (
        28,
        "번역 판 분기를 기본 판 길에도 켠다 (TRD1 P1)",
        [
            (
                DOCUMENT,
                '    if doc.needs_pass:\n        raise ParseError(f"암호가 걸린 PDF 다: {path}")\n',
                '    layout = 2\n    if doc.needs_pass:\n        raise ParseError(f"암호가 걸린 PDF 다: {path}")\n',
            )
        ],
        "unit",
    ),
    (
        29,
        "HTTP 의 layout 을 안쪽으로 넘기지 않는다 (TRD1 P2)",
        [
            (
                APP,
                "    extra = () if layout == DEFAULT_LAYOUT else (layout,)\n    _take_slot()",
                "    extra = ()\n    _take_slot()",
            )
        ],
        "unit",
    ),
    (
        30,
        "칸 밖 조각을 글로 돌리지 않는다 — 표 상자 안 조각을 다 뺀다 (TRD1 P3)",
        [
            (
                DOCUMENT,
                "            rest = [c for c in chunks if id(c) not in placed]\n",
                "            rest = [c for c in chunks if not any(_inside(c, t.bbox) for t in page_tables)]\n",
            )
        ],
        "unit",
    ),
    (
        31,
        "줄 끝 위첨자 판정을 되돌린다 — (y0, x0) 차례·조각 머리 x0 로 줄 잇기 (TRD1 P4)",
        [
            (
                P / "docparse/blocks.py",
                "    ordered = _line_order(chunks) if layout >= 2 else sorted(chunks, key=lambda c: (c.y0, c.x0))\n",
                "    ordered = sorted(chunks, key=lambda c: (c.y0, c.x0))\n",
            ),
            (
                P / "docparse/blocks.py",
                "        cx0 = c.body_x0 if layout >= 2 and c.body_x0 is not None else c.x0\n",
                "        cx0 = c.x0\n",
            ),
            (
                P / "docparse/blocks.py",
                "        keep_y1 = layout >= 2 and c.body_x0 is not None and home is not None and same_line\n",
                "        keep_y1 = False\n",
            ),
        ],
        "unit",
    ),
    (
        32,
        "세로 병합 띠의 약한 경계를 무리 통째로 잇는다 (TRD1 P5)",
        [
            (
                TABLES,
                "                    if layout >= 2 and not any(c.x0 < xs[j + 1] - 2 and c.x1 > xs[j + 1] + 2 for c in members):\n"
                "                        continue\n",
                "",
            )
        ],
        "unit",
    ),
    (
        33,
        "글자 정렬 표를 단 틈에서 자르지 않는다 (TRD1 P6)",
        [
            (
                P / "docparse/tables.py",
                "            text_tables = _cut_text_tables(text_tables, chunks, page.rect.height)\n",
                "            pass\n",
            )
        ],
        "unit",
    ),
    (
        34,
        "내용 키에 상자를 넣는다 (TRD1 P7)",
        [
            (
                ANNOTATE,
                'key = content_key(pno, "text", _squeeze(block["text"]))',
                'key = content_key(pno, "text", [_squeeze(block["text"]), block["bbox"]])',
            )
        ],
        "unit",
    ),
    (
        35,
        "bad_layout 검사를 뺀다 — 모르는 값은 1 (TRD1 P8)",
        [
            (
                APP,
                "    if len(found) > 1 or found[0] not in LAYOUT_VALUES:\n"
                '        raise reject(422, "bad_layout", "layout 은 한 번, 1 또는 2 여야 한다")\n'
                "    return LAYOUT_VALUES[found[0]]\n",
                "    return LAYOUT_VALUES.get(found[-1], DEFAULT_LAYOUT)\n",
            )
        ],
        "unit",
    ),
    (
        36,
        "내용 키 해시에 블록 갈래(heading·paragraph)를 넣는다 (TRD2 K1)",
        [
            (
                ANNOTATE,
                'content_key(pno, "text", _squeeze(block["text"]))',
                'content_key(pno, block["kind"], _squeeze(block["text"]))',
            )
        ],
        "unit",
    ),
    (
        37,
        "표 밖 숫자 조각의 각주 위첨자를 블록 글에 붙이지 않는다 (TRD2 K2)",
        [(BLOCKS, "        chunks = [_with_marks(c) for c in chunks]\n", "        chunks = list(chunks)\n")],
        "unit",
    ),
    (
        38,
        "단 틈 자르기에서 걷히는 칸의 거름을 지운다 (TRD2 K3)",
        [
            (
                P / "docparse/tables_text.py",
                "    kept = {(i, j): cs for (i, j), cs in kept.items() if i in rmap and j in cmap}\n",
                "",
            )
        ],
        "unit",
    ),
    (
        39,
        "위첨자 붙이기(layout 2 갈래)를 기본 판에도 (TRD2 K4)",
        [
            (
                BLOCKS,
                "    if layout >= 2:\n        chunks = [_with_marks(c)",
                "    if True:\n        chunks = [_with_marks(c)",
            )
        ],
        "unit",
    ),
    (
        40,
        "도표 표 거름 부르기를 지운다 (TRD3)",
        [
            (
                TABLES_ALL,
                "        tables = _drop_figure_tables(page, tables, chunks, notes)\n",
                "        pass\n",
            )
        ],
        "unit",
    ),
    (
        41,
        "도표 표 거름을 기본 판에도 켠다 (TRD3)",
        [
            (
                TABLES_ALL,
                "    if layout >= 2:\n        tables = _drop_figure_tables(",
                "    if True:\n        tables = _drop_figure_tables(",
            )
        ],
        "unit",
    ),
    (
        42,
        "막대 줄 문턱을 0 으로 (모든 표가 걸림, TRD3)",
        [(TABLES_ALL, "FIGURE_BAR_RUN_MIN = 3\n", "FIGURE_BAR_RUN_MIN = 0\n")],
        "unit",
    ),
    (
        43,
        "곡선 갈래에서 그리기 신호를 지운다 — 빈 칸 비율만 (TRD3)",
        [
            (
                TABLES_ALL,
                "    return curves >= 1 and empty >= FIGURE_EMPTY_RATIO_MIN and curve_rows >= FIGURE_CURVE_ROWS_MIN\n",
                "    return empty >= FIGURE_EMPTY_RATIO_MIN\n",
            )
        ],
        "unit",
    ),
    (
        44,
        "도표 상자 안 실패 항목 거름을 지운다 (TRD3)",
        [
            (
                TABLES_ALL,
                "    gone = {id(t) for t in dropped + failed}\n",
                "    gone = {id(t) for t in dropped}\n",
            )
        ],
        "unit",
    ),
]


def main():
    """인자로 번호를 주면 그 파손만 심는다(예: `planted.py 7 8 9`). 없으면 전부."""
    chosen = {int(arg) for arg in sys.argv[1:]}
    plants = [plant for plant in PLANTS if not chosen or plant[0] in chosen]
    before = tree_hash()
    lock_bytes = (P / "uv.lock").read_bytes()
    wrong = 0
    for number, name, edits, expect in plants:
        saved = {}
        try:
            for path, old, new in edits:
                text = path.read_text(encoding="utf-8")
                saved.setdefault(path, text)
                if text.count(old) != 1:
                    raise RuntimeError(f"고칠 자리가 {text.count(old)}곳이다: {path.name}: {old[:60]!r}")
                path.write_text(text.replace(old, new), encoding="utf-8")
            lines = []
            if expect == "lock":
                red, note = lock_grep()
                ok = red is True
                lines.append(f"잠금 grep: {'빨강' if red else '초록' if red is False else '못 쟀다'}. {note}")
            else:
                red, names, files, last = unit()
                lines.append(f"단위(원본 없이): {'빨강' if red else '초록'} — {last}")
                if names:
                    lines.append(
                        f"  빨개진 것 {len(names)}건, 파일 {files}: "
                        + ", ".join(names[:8])
                        + (" …" if len(names) > 8 else "")
                    )
                ok = red
                if expect == "gold_only":
                    result = one_document_against_gold()
                    if result is None:
                        ok = False
                        lines.append("네 문서 골든: 못 쟀다 (G 가 없다)")
                    else:
                        ok = (not red) and result[0]
                        lines.append(f"네 문서 골든: {'빨강' if result[0] else '초록'} — {result[1]}")
                        lines.append("  (기대: 단위는 초록으로 남고 골든만 빨개진다. 단위로는 못 잡는다)")
                if expect == "reports":
                    result = gold_reports()
                    if result is None:
                        ok = False
                        lines.append("정답 회귀(reports): 못 쟀다 (G 가 없다)")
                    else:
                        ok = result[0]
                        lines.append(f"정답 회귀(reports): {'빨강' if result[0] else '초록'} — {result[3]}")
                        if result[1]:
                            lines.append(
                                f"  빨개진 것 {len(result[1])}건: "
                                + ", ".join(result[1][:6])
                                + (" …" if len(result[1]) > 6 else "")
                            )
        finally:
            for path, text in saved.items():
                path.write_text(text, encoding="utf-8")
            if (P / "uv.lock").read_bytes() != lock_bytes:
                (P / "uv.lock").write_bytes(lock_bytes)
        wrong += not ok
        print(f"── 심은 파손 {number}: {name}")
        for line in lines:
            print("   " + line)
        print(f"EXIT={0 if ok else 1}  # 파손 {number} 이 기대대로 잡혔는가")
        sys.stdout.flush()
    after = tree_hash()
    print(f"── 작업 트리 해시: 처음 {before[:16]} / 끝 {after[:16]}")
    print(f"EXIT={0 if before == after else 1}  # 끝난 뒤 작업 트리가 처음과 같다")
    print(f"══ 기대와 다른 파손: {wrong}/{len(plants)}")
    return 1 if wrong or before != after else 0


if __name__ == "__main__":
    sys.exit(main())
