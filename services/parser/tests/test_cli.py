"""명령줄."""

import json

from docparse.cli import main, parse_pages

from . import pdfbuild


def test_parse_pages():
    assert parse_pages("3,10-12") == [3, 10, 11, 12]


def test_parse_writes_valid_document_and_renders(tmp_path, synthetic_ruled_page, capsys):
    pdf = tmp_path / "synthetic_ruled.pdf"
    synthetic_ruled_page.parent.save(pdf)
    out = tmp_path / "out"
    assert main(["parse", str(pdf), "--out", str(out), "--render", "--dpi", "72"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_valid"] is True and summary["tables"] == 1 and summary["rendered_pages"] == 1
    doc = json.loads((out / "document.json").read_text(encoding="utf-8"))
    assert doc["tables"][0]["cells"][1] == ["Alpha", "t", "1,200", "1,304"]
    png = (out / "pages" / "p0001.png").read_bytes()
    assert png[:4] == b"\x89PNG"
    assert tuple(pdfbuild.png_size(png)) == (400, 300)  # 72dpi 면 1pt 가 1px: 쪽은 400 × 300pt


def test_render_command(tmp_path, synthetic_ruled_page, capsys):
    pdf = tmp_path / "synthetic_ruled.pdf"
    synthetic_ruled_page.parent.save(pdf)
    assert main(["render", str(pdf), "--out", str(tmp_path / "png"), "--dpi", "100"]) == 0
    assert (tmp_path / "png" / "p0001.png").is_file()


def test_missing_pdf_is_an_error_not_an_empty_document(tmp_path, capsys):
    assert main(["parse", str(tmp_path / "nope.pdf"), "--out", str(tmp_path / "o")]) == 2
    assert not (tmp_path / "o" / "document.json").exists()


def test_score_with_missing_gold_dir_is_an_error(tmp_path, capsys):
    assert main(["score", "--gold", str(tmp_path / "nope")]) == 2
