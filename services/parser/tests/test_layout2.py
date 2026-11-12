"""번역 판 `layout=2`(밴드 TRD1, MARC-TICK-364)와 기본 판의 바이트.

── 뜻 ──
- 기본 판(1)은 BASE 와 바이트까지 같다(L1): 인자 없음·`layout=1` 명시·명령줄 `--layout 1`·HTTP 쿼리 없음과 `layout=1` 이
  PB1 고정값(`baseline/synthetic.sha256.json`, 바꾸지 않는다)과 같은 해시다. 기본 판 산출에는 새 단언을 걸지 않는다.
- 번역 판(2)의 산출은 새 고정값(`baseline/layout2.sha256.json`)에 얼린다(L2). Python·명령줄·HTTP 세 길이 같은 해시다.
  고정값을 바꾸는 규칙은 PB1 과 같다(산출을 일부러 바꾸는 커밋만, 같은 커밋에서).
- L7 머리글·꼬리말 띠와 내용 키, L8 HTTP 의 `bad_layout`.
합성 PDF 는 `layout2_doc`(쪽 넷)와 PB1 의 `baseline_doc`(판 둘)이다. 글은 전부 지어낸 것이다.
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as parser_app
from docparse.document import parse_pdf, parse_pdf_places, validate, validate_places

from . import baseline_doc, layout2_doc
from .test_baseline import FIXED as PB1_FIXED
from .test_baseline import pb

PARSER_ROOT = Path(__file__).resolve().parents[1]
FIXED_PATH = Path(__file__).resolve().parent / "baseline" / "layout2.sha256.json"
FIXED = json.loads(FIXED_PATH.read_text(encoding="utf-8"))
PDF = {"content-type": "application/pdf"}
client = TestClient(parser_app.app)

BUILDERS = {
    **{name: (lambda kw=kw: baseline_doc.build(**kw)) for name, kw in baseline_doc.VARIANTS.items()},
    **{name: (lambda kw=kw: layout2_doc.build(**kw)) for name, kw in layout2_doc.VARIANTS.items()},
}
# 고정값의 판 이름 = "<짓개 판>@<분해 판>"
CASES = sorted(FIXED["variants"])


def _split(case):
    name, layout = case.split("@")
    return name, int(layout)


def _assert_same(case, got, where):
    diff = pb.differing(got, FIXED["variants"][case])
    assert not diff, f"{case} ({where}): 고정값과 다른 부분 = {', '.join(diff)}"


@pytest.fixture(scope="module")
def pdfs(tmp_path_factory):
    folder = tmp_path_factory.mktemp("layout2")
    out = {}
    for name, build in BUILDERS.items():
        path = folder / f"{name}.pdf"
        path.write_bytes(build())
        out[name] = path
    return out


@pytest.fixture(scope="module")
def parsed(pdfs):
    """판 이름 → (문서 모델, 글자 자리). 번역 판으로 한 번씩."""
    return {name: parse_pdf_places(path, layout=2) for name, path in pdfs.items()}


def _cli(path, out, *args):
    done = subprocess.run(
        [sys.executable, "-m", "docparse", "parse", str(path), "--out", str(out), "--places", *args],
        cwd=PARSER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return pb.hash_dir(out)


# ── L1 기본 판의 바이트 ─────────────────────────────────────────────


@pytest.mark.parametrize("variant", sorted(baseline_doc.VARIANTS))
def test_l1_explicit_layout_1_is_the_pb1_baseline(pdfs, variant):
    document, places = parse_pdf_places(pdfs[variant], layout=1)
    assert not pb.differing(pb.hashes(document, places), PB1_FIXED["variants"][variant])
    assert pb.hashes(parse_pdf(pdfs[variant], layout=1), {})["document"] == PB1_FIXED["variants"][variant]["document"]
    assert "layout" not in document["parser"] and "layout" not in places["parser"]


def test_l1_cli_layout_1_is_the_pb1_baseline(pdfs, tmp_path):
    got = _cli(pdfs["synthetic"], tmp_path / "out", "--layout", "1")
    assert not pb.differing(got, PB1_FIXED["variants"]["synthetic"])


@pytest.mark.parametrize("query", ["", "?layout=1", "?file_name=a.pdf&layout=1", "?layout=%31"])
def test_l1_http_without_layout_or_layout_1_is_the_pb1_baseline(pdfs, query):
    response = client.post(f"/parse{query}", content=pdfs["synthetic"].read_bytes(), headers=PDF)
    assert response.status_code == 200, response.text
    body = response.json()
    assert not pb.differing(pb.hashes(body["document"], body["charPlaces"]), PB1_FIXED["variants"]["synthetic"])


def test_l1_layout2_builder_under_layout_1_is_frozen_too(pdfs):
    """번역 판 짓개를 기본 판으로 분해한 산출도 얼린다(기본 판의 바이트가 이 문서에서도 그대로인지)."""
    _assert_same("layout2@1", pb.hashes(*parse_pdf_places(pdfs["layout2"])), "parse_pdf_places 인자 없음")


def test_l1_unknown_layout_is_an_error_not_a_default(pdfs, tmp_path, capsys):
    from docparse.cli import main
    from docparse.document import ParseError

    with pytest.raises(ParseError):
        parse_pdf(pdfs["synthetic"], layout=3)
    with pytest.raises(SystemExit):
        main(["parse", str(pdfs["synthetic"]), "--out", str(tmp_path / "o"), "--layout", "3"])
    assert not (tmp_path / "o").exists()


# ── L2 번역 판의 새 기준선 ──────────────────────────────────────────


def test_l2_fixed_file_shape_and_builders():
    hex64 = re.compile(r"^[0-9a-f]{64}$")
    assert FIXED["_comment"] and re.fullmatch(r"[0-9a-f]{40}", FIXED["base_commit"])
    assert {_split(c)[0] for c in CASES} == set(BUILDERS)
    for case, entry in FIXED["variants"].items():
        name, _layout = _split(case)
        assert sorted(entry["parts"]) == sorted(pb.PART_NAMES), case
        assert all(
            hex64.match(v) for v in [entry["all"], entry["document"], entry["char-places"], *entry["parts"].values()]
        )
        data = BUILDERS[name]()
        assert hashlib.sha256(data).hexdigest() == entry["pdf_sha256"], f"{case}: 짓개의 PDF 바이트가 바뀌었다"
        assert data == BUILDERS[name](), "두 번 지은 바이트가 다르다"
    # 기존 합성 두 판의 PDF 는 PB1 고정값의 것과 같다(짓개를 바꾸지 않았다)
    for name in baseline_doc.VARIANTS:
        assert FIXED["variants"][f"{name}@2"]["pdf_sha256"] == PB1_FIXED["variants"][name]["pdf_sha256"]


@pytest.mark.parametrize("case", [c for c in CASES if c.endswith("@2")])
def test_l2_python_entry_matches_the_layout2_baseline(parsed, case):
    document, places = parsed[_split(case)[0]]
    _assert_same(case, pb.hashes(document, places), "parse_pdf_places(layout=2)")
    assert not validate(document) and not validate_places(places)
    assert document["parser"]["layout"] == 2 and places["parser"]["layout"] == 2
    # 판 표지 밖의 칸은 기본 판과 같다(판 번호·스키마 판은 올리지 않는다)
    assert document["parser"]["version"] == "0.1.0" and document["schema_version"] == "0.1"


@pytest.mark.parametrize("case", ["layout2@2", "synthetic@2"])
def test_l2_cli_matches_the_layout2_baseline(pdfs, tmp_path, case):
    _assert_same(case, _cli(pdfs[_split(case)[0]], tmp_path / "out", "--layout", "2"), "명령줄 --layout 2")


@pytest.mark.parametrize("case", [c for c in CASES if c.endswith("@2")])
def test_l2_http_matches_the_layout2_baseline(pdfs, case):
    response = client.post("/parse?layout=2&file_name=x.pdf", content=pdfs[_split(case)[0]].read_bytes(), headers=PDF)
    assert response.status_code == 200, response.text
    body = response.json()
    _assert_same(case, pb.hashes(body["document"], body["charPlaces"]), "POST /parse?layout=2")


# ── L7 머리글·꼬리말 띠와 내용 키 ───────────────────────────────────

KEY = re.compile(r"^k[0-9a-f]{16}(-[2-9]|-[1-9][0-9]+)?$")


def test_l7_regions(parsed):
    document, _ = parsed["layout2"]
    heights = {p["page"]: p["height"] for p in document["pages"]}
    for b in document["blocks"]:
        top, bottom = b["bbox"][3] <= 0.075 * heights[b["page"]], b["bbox"][1] >= 0.92 * heights[b["page"]]
        assert b["region"] == ("footer" if bottom else "header" if top else "body"), b["id"]
    by_page = {}
    for b in document["blocks"]:
        by_page.setdefault(b["page"], []).append(b)
    for page, blocks in by_page.items():
        assert [b["region"] for b in blocks if b["region"] != "body"] == ["header", "footer"], page
        assert blocks[0]["text"].endswith("header band") and blocks[-1]["text"] == str(page)
    tables = [b for b in document["blocks"] if b["kind"] == "table"]
    assert tables and {b["region"] for b in tables} == {"body"}


def test_l7_keys_are_content_hashes_with_page_suffixes(parsed):
    document, _ = parsed["layout2"]
    keys = [b["key"] for b in document["blocks"]]
    assert all(KEY.match(k) for k in keys) and len(set(keys)) == len(keys)
    page3 = [b for b in document["blocks"] if b["page"] == 3]
    same = [b["key"] for b in page3 if b["kind"] != "table" and b["text"].startswith("This column keeps")]
    assert len(same) >= 3 and same[0] + "-2" in same and same[0] + "-3" in same  # 같은 글은 읽는 차례대로 -2·-3
    # 다른 쪽의 같은 글(머리글 띠)은 쪽 번호가 달라 키가 다르다
    heads = [b["key"] for b in document["blocks"] if b["region"] == "header"]
    assert len(set(heads)) == len(heads) == 4
    # 위치 ID 는 그대로다
    assert all(re.fullmatch(rf"p{b['page']}-b{b['order']}", b["id"]) for b in document["blocks"])


def test_l7_keys_do_not_move_when_a_block_is_added_in_front(parsed):
    base = [b for b in parsed["layout2"][0]["blocks"] if b["page"] == 1]
    extra = [b for b in parsed["layout2_extra"][0]["blocks"] if b["page"] == 1]
    added = [b for b in extra if b.get("text", "").startswith("An unrelated note")]
    assert len(added) == 1 and len(extra) == len(base) + 1
    rest = [b for b in extra if b is not added[0]]
    assert [b["key"] for b in rest] == [b["key"] for b in base]
    assert [b["text"] for b in rest] == [b["text"] for b in base]
    assert [b["id"] for b in rest] != [b["id"] for b in base]  # 위치 ID 는 밀린다
    assert [b["bbox"] for b in rest] != [b["bbox"] for b in base]  # 자리도 다르다(키에 넣지 않았다)


def test_l7_table_key_is_the_cells(parsed):
    from docparse.annotate import content_key

    document, _ = parsed["layout2"]
    cells = {t["id"]: t["cells"] for t in document["tables"]}
    for b in document["blocks"]:
        if b["kind"] == "table":
            assert b["key"].split("-")[0] == content_key(b["page"], "table", cells[b["table_id"]])


# ── L8 HTTP 의 bad_layout ───────────────────────────────────────────


@pytest.mark.parametrize(
    "query",
    ["?layout=3", "?layout=x", "?layout=", "?layout=1&layout=2", "?layout=2&layout=2", "?layout=02", "?layout=+2"],
)
def test_l8_bad_layout_is_422(pdfs, query):
    response = client.post(f"/parse{query}", content=pdfs["synthetic"].read_bytes(), headers=PDF)
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"detail"} and set(body["detail"]) == {"code", "message"}
    assert body["detail"]["code"] == "bad_layout"


def test_l8_other_unknown_queries_are_still_ignored(pdfs):
    response = client.post("/parse?layouts=9&lay=3", content=pdfs["synthetic"].read_bytes(), headers=PDF)
    assert response.status_code == 200
    assert "layout" not in response.json()["document"]["parser"]


def test_l7_key_folds_full_width_and_spaces_with_nfkc():
    """글 블록의 키는 NFKC 뒤 공백을 지운 글에서 낸다: 전각·반각과 띄어쓰기만 다른 같은 글은 같은 키다."""
    from docparse.annotate import annotate

    pages = [{"page": 1, "height": 800.0}]

    def block(text):
        return {"page": 1, "kind": "paragraph", "bbox": [40.0, 100.0, 200.0, 110.0], "text": text}

    half, full = (
        annotate([block("Scope 1 2025 ABC")], [], pages),
        annotate([block("Ｓｃｏｐｅ　１ ２０２５ＡＢＣ")], [], pages),
    )
    assert half[0]["key"] == full[0]["key"]
    assert annotate([block("Scope 2 2025 ABC")], [], pages)[0]["key"] != half[0]["key"]
