"""떠 있는 파서(services/parser)에 http 어댑터가 실제로 닿아 값 후보와 상자까지 이어지는가. 테스트 하나.

호스트의 이 테스트가 떠 있는 api-py 컨테이너 **안에서** 파이썬을 돌린다(`docker compose exec -T api-py python -c …`,
PDF 는 표준 입력으로). 그 코드는 컨테이너의 환경 변수로 설정을 읽어(PARSER_URL …) 제품 코드의 길 그대로
`default_parser(config)` → `parse_and_extract(…)` 를 부르고 결과를 JSON 한 줄로 찍는다. 호스트가 그 줄을 단언한다.

이렇게 재는 까닭: 파서는 호스트에 포트가 없고(compose 안에서만 부른다), 이것을 부르는 경로가 아직 없고, 이미지에는
테스트가 실리지 않는다. 포트도 경로도 새로 열지 않는다.

★ 무효 조건: 경로(HTTP 요청)를 거친 것이 아니다. 컨테이너 안에서 어댑터를 직접 불렀다. 저장소(S3)·큐·세션은 안 거친다.
  고정물은 지은 표 하나(4×4)다. 실제 보고서로는 재지 않았다.

고정물: data/ruled-table.pdf 는 data/ruled-table.cells.json 에서 지은 것이다(짓는 명령과 sha256 은 data/README.md.
scripts/section4-PY8c.sh 가 다시 지어 sha256 이 같은지 잰다). 기대값은 그 JSON 의 칸에서 온다. 숫자는 지어낸 것이다.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from tests_integration.conftest import ENV, REPO_ROOT

DATA = Path(__file__).resolve().parent / "data"
PDF = DATA / "ruled-table.pdf"
CELLS = DATA / "ruled-table.cells.json"
FILE_NAME = "ruled-table.pdf"
DOC_ID = "it-ruled-table"
# 한 쪽에 표가 하나뿐이라 격자의 ID 는 `p1-t1` 이다.
# 표 칸의 값 후보 ID 는 `<격자 ID>:r<행>c<열>` 이다(reconcile/calc 의 약속).
GRID_ID = "p1-t1"
NUMBER = re.compile(r"[0-9]{1,3}(,[0-9]{3})*(\.[0-9]+)?|[0-9]+(\.[0-9]+)?")

# 컨테이너 안에서 도는 코드. 제품 코드만 import 한다(이미지에 테스트는 없다).
INSIDE = """
import hashlib, json, os, sys
from esgapi.config.env import load_config
from esgapi.reconcile.calc.places import locate_place
from esgapi.reconcile.service.services.parse import default_parser, parse_and_extract

pdf = sys.stdin.buffer.read()
config = load_config(os.environ)
out = {"bytes": len(pdf), "sha256": hashlib.sha256(pdf).hexdigest(), "parserUrl": config.parser_url}
result = parse_and_extract(pdf, file_name=sys.argv[1], parser=default_parser(config), doc_id=sys.argv[2])
out["ok"] = result.ok
if result.ok:
    extraction = result.extraction
    out["source"] = {
        "fileName": result.document.source.file_name,
        "sha256": result.document.source.sha256,
        "pageCount": result.document.source.page_count,
    }
    out["grids"] = [{"id": g.id, "status": g.status} for g in extraction.grids]
    out["failedTables"] = len(extraction.failed_tables)
    out["facts"] = [
        {"id": f.id, "docId": f.doc_id, "bucket": f.bucket, "raw": f.raw, "value": f.value,
         "row": f.where.row, "col": f.where.col}
        for f in extraction.facts
    ]
    out["nonValues"] = [{"raw": n.raw, "cls": n.cls, "row": n.where.row, "col": n.where.col}
                        for n in extraction.non_values]
    out["hasPlaceIndex"] = result.place_index is not None
    places = {}
    for f in extraction.facts:
        place = locate_place(f.id, extraction, result.place_index)
        places[f.id] = (
            {"found": True, "page": place.page, "boxes": [list(b) for b in place.boxes]}
            if place.found else {"found": False, "reason": place.reason}
        )
    out["places"] = places
    out["warnings"] = list(result.warnings)
else:
    out["problem"] = {"kind": result.kind, "detail": result.detail, "code": result.code, "status": result.status}
print(json.dumps(out, ensure_ascii=False))
"""


def run_inside(pdf: bytes) -> dict[str, Any]:
    """api-py 컨테이너 안에서 INSIDE 를 돌리고 그것이 찍은 JSON 한 줄을 읽는다. PDF 는 표준 입력으로 간다."""
    done = subprocess.run(
        ["docker", "compose", "exec", "-T", "api-py", "python", "-c", INSIDE, FILE_NAME, DOC_ID],
        cwd=REPO_ROOT,
        input=pdf,
        capture_output=True,
        check=False,
    )
    stdout = done.stdout.decode("utf-8")
    assert done.returncode == 0, f"컨테이너 안의 코드가 {done.returncode} 로 끝났다:\n{done.stderr.decode('utf-8')}"
    lines = stdout.splitlines()
    assert len(lines) == 1, stdout
    out: dict[str, Any] = json.loads(lines[0])
    return out


def expected_cells() -> tuple[dict[str, Any], list[tuple[int, int, str]], list[tuple[int, int, str]]]:
    """cells.json → (지은 조건, 숫자 칸, 숫자 열의 숫자 아닌 칸). 칸은 (행, 열, 글자)이고 머리글 행(0)은 뺀다."""
    spec: dict[str, Any] = json.loads(CELLS.read_text(encoding="utf-8"))
    numbers: list[tuple[int, int, str]] = []
    others: list[tuple[int, int, str]] = []
    for r, row in enumerate(spec["rows"]):
        if r == 0:
            continue
        for c in spec["numericColumns"]:
            text: str = row[c]
            (numbers if NUMBER.fullmatch(text) else others).append((r, c, text))
    return spec, numbers, others


def test_adapter_reaches_the_running_parser_and_yields_fact_candidates() -> None:
    pdf = PDF.read_bytes()
    spec, numbers, others = expected_cells()
    # 기대의 분모를 못 박는다: 숫자 칸 다섯, 값 없음 표시 하나(고정물이 바뀌면 여기가 먼저 알린다).
    assert (len(numbers), [text for _, _, text in others]) == (5, ["-"])

    out = run_inside(pdf)

    # 1. 표준 입력의 바이트가 그대로 갔고, 컨테이너가 자기 환경의 주소로 파서를 불렀다.
    assert (out["bytes"], out["sha256"]) == (len(pdf), hashlib.sha256(pdf).hexdigest())
    assert out["parserUrl"] == (ENV.get("PARSER_URL") or "http://parser:8000")

    # 2. 처음 맞물린 길이 ok 다. 아니면 어느 갈래에서 멈췄는지가 그대로 보인다.
    assert out["ok"] is True, out.get("problem")
    # 파서가 받은 것이 그 PDF 다(파서가 자기가 읽은 바이트의 sha256 과 받은 파일 이름을 문서 모델에 싣는다).
    assert out["source"] == {"fileName": FILE_NAME, "sha256": hashlib.sha256(pdf).hexdigest(), "pageCount": 1}
    assert out["grids"] == [{"id": GRID_ID, "status": "ok"}]
    assert out["failedTables"] == 0

    # 3. 값 후보의 (ID, 값) 목록이 cells.json 의 숫자 칸과 같다. 쉼표는 자릿수 구분이라 값에서 빠진다.
    wanted = [
        {
            "id": f"{GRID_ID}:r{r}c{c}",
            "docId": DOC_ID,
            "bucket": "table_cell",
            "raw": text,
            "value": text.replace(",", ""),
            "row": r,
            "col": c,
        }
        for r, c, text in numbers
    ]
    assert out["facts"] == wanted
    # 값이 아닌 것: 머리글 행의 숫자 열 칸(연도)과 값 없음 표시.
    header = [{"raw": spec["rows"][0][c], "cls": "header", "row": 0, "col": c} for c in spec["numericColumns"]]
    markers = [{"raw": text, "cls": "no_value_marker", "row": r, "col": c} for r, c, text in others]
    assert out["nonValues"] == [*header, *markers]

    # 4. 상자 색인이 있고, 값 후보마다 상자가 그 칸의 자리 안에 있다(쪽 1, 열의 가로 범위, 행의 세로 범위).
    assert out["hasPlaceIndex"] is True
    edges: list[float] = spec["columnEdges"]
    for r, c, text in numbers:
        place = out["places"][f"{GRID_ID}:r{r}c{c}"]
        assert place["found"] is True, (text, place)
        assert place["page"] == 1
        assert len(place["boxes"]) == 1, (text, place)
        x0, y0, x1, y1 = place["boxes"][0]
        row_top = spec["top"] + r * spec["rowHeight"]
        assert edges[c] <= x0 < x1 <= edges[c + 1], (text, place)
        assert row_top <= y0 < y1 <= row_top + spec["rowHeight"], (text, place)
    assert sorted(out["places"]) == sorted(item["id"] for item in wanted)
