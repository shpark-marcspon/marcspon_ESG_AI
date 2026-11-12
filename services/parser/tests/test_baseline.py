"""파서 기준선 대조(밴드 PB1, MARC-TICK-122): 합성 PDF 의 분해 산출이 얼린 해시와 같은가.

── 뜻 ──
기준선은 esg-lab 커밋 2e2c2c4 의 `py/docparse` 를 pdfium 엔진으로 돌린 산출이다(MARC-RPT-4·PD1 MARC-TICK-46 의 측정이
그 판으로 잰 것이다). PB1 은 그 산출과 esg-app `docparse/` 의 산출이 같음을 보이고, 합성 PDF 의 산출을 해시로 얼렸다
(`tests/baseline/synthetic.sha256.json`). `tests/test_baseline.py` 가 그 고정값과 견주며, `scripts/verify.sh` 의
`lane_parser`(pytest)에 저절로 든다. 공개 보고서 A·B 의 대조는 저장소 밖(검증 감독이 가진 스크립트와 고정값)이다.

── 쓰는 법(백엔드 PX 와 그 뒤) ──
- 커밋마다 `scripts/verify.sh --fast`(또는 `uv run --project services/parser --frozen pytest -q services/parser`)를 돌린다.
- 병합 전에 검증 감독에게 공개 보고서 A·B 대조(b)를 다시 돌려 달라고 요청한다.
- 빨개지면 실패 글이 다른 부분의 이름을 찍는다: document.pages·sections·blocks·tables·rest(나열한 칸 밖 전부),
  char-places.containers·unlinked·rest. `pdf` 가 다르면 짓개(`tests/baseline_doc.py`)나 `tests/pdfbuild.py` 가 바뀐
  것이고 분해기 탓이 아니다.

── 고정값을 바꾸는 규칙 ──
- 분해기의 산출을 **일부러** 바꾸는 커밋만 고정값을 바꾼다. 같은 커밋에서 고친다.
- 커밋 메시지에 다른 부분의 이름과 까닭을 적는다. 고정값의 `_comment` 에 적힌 기준 커밋도 같이 고친다.
- 공개 보고서 고정값(저장소 밖)은 검증 감독에게 다시 돌려 달라고 요청한다.
- D4 의 쪽 수·시간 상한에 걸리게 일부러 지은 큰 문서는 대조 밖이다.

── 정규화 ──
`source.file_name` 하나만 상수 "<pdf>" 로 바꾼다(document 와 char-places 둘 다). 파일 이름은 짓는 자리에 따라 달라지고
쪽 내용과 무관하다. 그 밖의 칸은 전부 해시에 든다. 직렬화는
`json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))` 의 UTF-8 바이트이고 sha256 이다.

── 이 파일의 테스트 ──
(a1) 짓개의 PDF 바이트 해시, (a2) `parse_pdf_places` 산출의 해시(전체·부분), (a3) 다른 이름으로 써도 같은 해시,
(a4) `parse_pdf`(places 없음)의 document 해시, (a5) 고정 JSON 의 꼴, (a6) 합성이 갈래를 실제로 건드리는지,
(a7) HTTP 입구 `POST /parse`(application/pdf), (a8) 명령줄 `python -m docparse parse --places`.
HTTP 입구가 바뀌면(PX) (a7) 의 부르는 줄만 맞춘다. 해시는 그대로여야 한다.
"""

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as parser_app
from docparse.document import parse_pdf, parse_pdf_places

from . import baseline_doc

PARSER_ROOT = Path(__file__).resolve().parents[1]
FIXED_PATH = Path(__file__).resolve().parent / "baseline" / "synthetic.sha256.json"


def _load_cli():
    spec = importlib.util.spec_from_file_location("parser_baseline", PARSER_ROOT / "scripts" / "parser_baseline.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pb = _load_cli()
FIXED = json.loads(FIXED_PATH.read_text(encoding="utf-8"))
VARIANTS = sorted(baseline_doc.VARIANTS)


def _assert_same(variant, got, where):
    diff = pb.differing(got, FIXED["variants"][variant])
    assert not diff, f"{variant} ({where}): 기준선과 다른 부분 = {', '.join(diff)}"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """판 이름 → (PDF 경로, PDF 바이트, 문서 모델, 글자 자리). 판마다 한 번만 분해한다."""
    folder = tmp_path_factory.mktemp("baseline")
    out = {}
    for variant in VARIANTS:
        data = baseline_doc.build(**baseline_doc.VARIANTS[variant])
        path = folder / f"{variant}.pdf"
        path.write_bytes(data)
        document, places = parse_pdf_places(path)
        out[variant] = (path, data, document, places)
    return out


def test_variants_match_the_fixed_file():
    assert sorted(FIXED["variants"]) == VARIANTS


@pytest.mark.parametrize("variant", VARIANTS)
def test_a1_builder_pdf_bytes(variant):
    data = baseline_doc.build(**baseline_doc.VARIANTS[variant])
    assert hashlib.sha256(data).hexdigest() == FIXED["variants"][variant]["pdf_sha256"], (
        f"{variant}: 합성 PDF 의 바이트가 바뀌었다 — 짓개(tests/baseline_doc.py)나 tests/pdfbuild.py 탓이다(분해기 탓이 아니다)"
    )
    assert data == baseline_doc.build(**baseline_doc.VARIANTS[variant]), "두 번 지은 바이트가 다르다"


@pytest.mark.parametrize("variant", VARIANTS)
def test_a2_parse_places_matches_baseline(built, variant):
    _path, _data, document, places = built[variant]
    _assert_same(variant, pb.hashes(document, places), "parse_pdf_places")


@pytest.mark.parametrize("variant", VARIANTS)
def test_a3_other_file_name_gives_same_hashes(built, tmp_path, variant):
    _path, data, document, places = built[variant]
    other = tmp_path / "other-folder" / "a different name.pdf"
    other.parent.mkdir()
    other.write_bytes(data)
    doc2, places2 = parse_pdf_places(other)
    assert doc2["source"]["file_name"] != document["source"]["file_name"]  # 이름이 실제로 다르다
    assert pb.hashes(doc2, places2) == pb.hashes(document, places)


@pytest.mark.parametrize("variant", VARIANTS)
def test_a4_parse_without_places_gives_same_document(built, variant):
    path = built[variant][0]
    got = pb.hashes(parse_pdf(path), {})["document"]
    assert got == FIXED["variants"][variant]["document"], f"{variant}: parse_pdf 의 document 가 places 판과 다르다"


def test_a5_fixed_file_shape():
    hex64 = re.compile(r"^[0-9a-f]{64}$")
    assert FIXED["_comment"] and isinstance(FIXED["_comment"], list)
    assert re.fullmatch(r"[0-9a-f]{40}", FIXED["base_commit"])
    for variant, entry in FIXED["variants"].items():
        flat = {k: entry[k] for k in ("pdf_sha256", "all", "document", "char-places")}
        flat.update(entry["parts"])
        assert sorted(entry["parts"]) == sorted(pb.PART_NAMES), variant
        bad = {k: v for k, v in flat.items() if not hex64.match(v)}
        assert not bad, f"{variant}: 64자 16진이 아닌 칸 {bad}"


def test_a6_synthetic_touches_the_branches(built):
    _path, _data, doc, places = built["synthetic"]
    pages = {p["page"]: p for p in doc["pages"]}
    assert pages[1]["columns"] == 2
    tables = {t["method"]: t for t in doc["tables"]}
    assert sorted(tables) == ["lines", "text"]
    ruled = tables["lines"]
    assert ruled["footnote_marks"] == [{"row": 1, "col": 3, "mark": "1)"}]
    # 세로 병합: 아래 띠에 놓인 글이 병합 칸의 첫 행으로. 가로 병합: 1열 자리의 글이 병합 칸의 첫 열로.
    assert [row[:2] for row in ruled["cells"][1:4]] == [["Energy", "MWh"], ["", "GJ"], ["Water total", ""]]
    blank = [p for p in doc["pages"] if p["text_layer"] == "none"]
    assert [p["page"] for p in blank] == [4] and blank[0]["image_coverage"] > 0
    assert not [b for b in doc["blocks"] if b["page"] == 4]
    sizes = {b["font_size"] for b in doc["blocks"] if b["kind"] == "paragraph"}
    assert 9.4 in sizes  # 9.37pt 를 소수 한 자리로 반올림한 값
    page1 = [b for b in doc["blocks"] if b["page"] == 1]
    # 꼬리 띠 블록 둘이 읽는 순서의 맨 뒤이고, 그 앞은 오른쪽 단의 마지막 문단이다(꼬리 판정이 꺼지면 왼쪽 단 끝에 끼어든다)
    assert all(b["bbox"][1] >= 0.92 * pages[1]["height"] for b in page1[-2:])
    assert page1[-3]["bbox"][0] >= 300 and page1[-3]["text"].startswith("8. ")
    assert "wrapped_line_merged" in tables["text"]["notes"]
    assert tables["text"]["cells"][3][0] == "Recycled share of waste"
    assert {s["basis"] for s in doc["sections"]} == {"page_top_largest_font"}
    toc_sections = built["synthetic_toc"][2]["sections"]
    assert {s["basis"] for s in toc_sections} == {"pdf_outline"} and len(toc_sections) == 3
    assert any(re.search("[가-힣]", b.get("text", "")) for b in doc["blocks"])
    assert places["containers"] and not places["unlinked"]


@pytest.mark.parametrize("variant", VARIANTS)
def test_a7_http_entry_matches_baseline(built, variant):
    data = built[variant][1]
    client = TestClient(parser_app.app)
    response = client.post("/parse?file_name=baseline.pdf", content=data, headers={"content-type": "application/pdf"})
    assert response.status_code == 200, response.text
    body = response.json()
    _assert_same(variant, pb.hashes(body["document"], body["charPlaces"]), "POST /parse")


def test_a8_cli_matches_baseline(built, tmp_path):
    path = built["synthetic"][0]
    out = tmp_path / "cli-out"
    done = subprocess.run(
        [sys.executable, "-m", "docparse", "parse", str(path), "--out", str(out), "--places"],
        cwd=PARSER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    _assert_same("synthetic", pb.hash_dir(out), "python -m docparse parse --places")
