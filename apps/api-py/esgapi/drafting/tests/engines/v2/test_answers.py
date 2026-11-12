"""S3 답 다듬기(engines/v2/answers.py — RP2b B5 의 「꼴 어긋난 답 버림」). 순수 층."""

from typing import Any

from esgapi.drafting.engines.v2 import answers


def test_bad_sources_are_dropped_and_null_s_is_kept() -> None:
    answer = {
        "bullets": [
            {
                "text": "  가상 bullet  ",
                "sources": [
                    {"block": "p1-b1", "s": 0},
                    {"block": "p1-b2", "s": None},
                    {"block": 3, "s": 0},
                    {"block": "", "s": 0},
                    {"block": "p1-b1", "s": True},
                    {"block": "p1-b1", "s": -1},
                    {"block": "p1-b1", "s": "1"},
                    {"block": "p1-b1", "s": 1.0},
                    "p1-b1",
                ],
            },
            {"text": "   ", "sources": [{"block": "p1-b1", "s": 0}]},
        ]
    }
    kept, warnings = answers.trim(answer, "k")
    assert kept == [{"text": "가상 bullet", "sources": [{"block": "p1-b1", "s": 0}, {"block": "p1-b2", "s": None}]}]
    assert warnings == []


def test_text_is_cut_at_200_and_bullets_capped_at_15() -> None:
    answer: dict[str, Any] = {"bullets": [{"text": "가" * 250, "sources": []}] * 16}
    kept, warnings = answers.trim(answer, "k")
    assert len(kept) == 15 and len(kept[0]["text"]) == 200
    assert [w["code"] for w in warnings] == ["bullets_capped"]
