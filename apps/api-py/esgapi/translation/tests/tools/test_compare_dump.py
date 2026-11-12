"""엔진 JSON 덤프(tools/compare_dump.py — 개정 1 B1, TR1-o 가 부를 명령): 작은 대본으로 돌아 JSON 꼴이 맞고,
대본을 다 쓰며, 공급사는 모의 둘뿐이다(실호출 0). 입력은 지어낸 translation.input@1.
"""

import json
from pathlib import Path
from typing import Any

from esgapi.translation.contracts.shapes import check_input
from esgapi.translation.tools import compare_dump

INPUT: dict[str, Any] = {
    "schemaVersion": "translation.input@1",
    "document": {"kind": "structuredText", "text": "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다."},
    "company": {"name": "가상고객사", "preferredSubject": "가상 업종", "industryStandards": "GRI"},
    "glossary": {"base": [{"ko": "가상 제목", "en": "Virtual Title"}], "final": []},
    "part": "general",
    "style": {"compareAb": False, "single": "B"},
    "peerGroupStyle": None,
    "pages": {"start": None, "end": None},
    "ceoPageLimit": 6,
    "autofix": True,
}
SCRIPT = {
    "anthropic": [],
    "openai": [
        {"kind": "completed", "text": "[BLOCK 1]\nVirtual Title\nVirtual body."},
        {"kind": "completed", "text": "[]"},
    ],
}
"""경로가 셋 다 openai 라(MARC-ENT-402) 답은 openai 쪽에 심는다."""


def test_the_input_is_a_translation_input() -> None:
    check_input(INPUT)


def test_dump_records_the_calls_and_the_run() -> None:
    out = compare_dump.dump(INPUT, SCRIPT)
    assert set(out) == {"calls", "run", "unusedReplies"}
    calls = out["calls"]
    assert isinstance(calls, list)
    assert [(c["site"], c["role"], c["maxTokens"], c["model"], c["route"]) for c in calls] == [
        ("section", "translate", 4096, "gpt-4.1-mini", "light-openai-41"),
        ("review", "review", 4096, "gpt-4.1-mini", "light-openai-41"),
    ]
    assert all(set(c) == {"site", "role", "system", "user", "maxTokens", "model", "route"} for c in calls)
    assert "[Mandatory glossary for this source text]\n- 가상 제목 -> Virtual Title\n" in calls[0]["user"]
    run = out["run"]
    assert isinstance(run, dict)
    assert run["part"] == "general"
    assert run["variants"][0]["translated_text"] == "[PAGE 1]\n\n[BLOCK 1]\nVirtual Title\nVirtual body."
    assert out["unusedReplies"] == {"anthropic": 0, "openai": 0}


def test_main_writes_json_and_unused_replies_are_counted(tmp_path: Path) -> None:
    script = {"anthropic": [], "openai": [*SCRIPT["openai"], {"kind": "refusal", "text": "남는 답"}]}
    (tmp_path / "in.json").write_text(json.dumps(INPUT, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    argv = ["--input", str(tmp_path / "in.json"), "--script", str(tmp_path / "script.json")]
    assert compare_dump.main([*argv, "--out", str(tmp_path / "out.json")]) == 0
    written = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert written["unusedReplies"] == {"anthropic": 0, "openai": 1}
    assert [c["site"] for c in written["calls"]] == ["section", "review"]


def test_every_reply_kind_is_built_with_keywords() -> None:
    kinds = [compare_dump.reply({"kind": k, "text": "t"}).kind for k in ("completed", "truncated", "refusal", "error")]
    assert kinds == ["completed", "truncated", "refusal", "error"]
