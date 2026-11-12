"""Word 쓰기 덤프 명령(발주서 §3 S8, 처분 ⑬): 작은 지은 입력으로 돌아 Word·읽기 JSON·종료 0, 짓다 실패해도 종료 0 +
`status: "failed"`(Word 파일 없음).
"""

import json
from pathlib import Path

from esgapi.translation.outputs.word_dump import main


def test_bilingual_writes_the_word_and_its_readback(tmp_path: Path) -> None:
    text = tmp_path / "in.txt"
    text.write_text("[PAGE 1]\n[BLOCK 1]\n가상 제목\n", encoding="utf-8")
    out = tmp_path / "out.docx"
    assert main(["bilingual", "--text", str(text), "--out", str(out)]) == 0
    assert out.read_bytes()[:4] == b"PK\x03\x04"
    read = json.loads((tmp_path / "out.docx.read.json").read_text(encoding="utf-8"))
    assert read["status"] == "built"
    texts = ["".join(r["text"] for r in b["runs"]) for b in read["blocks"] if b["type"] == "paragraph"]
    assert texts == ["[PAGE 1]", "[BLOCK 1]", "가상 제목"]
    first = read["blocks"][0]["runs"][0]
    assert first == {
        "text": "[PAGE 1]",
        "font": "Malgun Gothic",
        "eastAsiaFont": "Malgun Gothic",
        "sizePt": 8.5,
        "color": "808080",
        "bold": True,
        "italic": False,
        "highlight": None,
        "pageBreak": False,
    }


def test_qa_reads_colab_all_sections_json(tmp_path: Path) -> None:
    sections = tmp_path / "sections.json"
    sections.write_text(
        json.dumps(
            [
                {
                    "page_num": 2,
                    "content": "[PAGE 2]\nABC Corp grew.",
                    "issues": [
                        {
                            "issue_type": "TERMINOLOGY",
                            "severity": "LOW",
                            "original_span": "ABC Corp grew",
                            "suggestion": "가상",
                            "reason": "가상",
                        }
                    ],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "qa.docx"
    assert main(["qa", "--sections", str(sections), "--variant", "B", "--out", str(out)]) == 0
    read = json.loads((tmp_path / "qa.docx.read.json").read_text(encoding="utf-8"))
    assert read["status"] == "built"
    tables = [b for b in read["blocks"] if b["type"] == "table"]
    assert [c["text"] for c in tables[0]["rows"][1]] == ["B", "2", "", "", "1"]
    highlighted = [r["text"] for b in read["blocks"] if b["type"] == "paragraph" for r in b["runs"] if r["highlight"]]
    assert highlighted == ["ABC Corp grew"]


def test_a_failed_word_writes_only_the_failure_and_exits_zero(tmp_path: Path) -> None:
    text = tmp_path / "in.txt"
    text.write_text("가상\x01글\n", encoding="utf-8")
    out = tmp_path / "out.docx"
    assert main(["bilingual", "--text", str(text), "--out", str(out)]) == 0
    assert not out.exists()
    read = json.loads((tmp_path / "out.docx.read.json").read_text(encoding="utf-8"))
    assert read["status"] == "failed"
    assert read["message"].startswith("XML 에 못 담는 글자 U+0001")
