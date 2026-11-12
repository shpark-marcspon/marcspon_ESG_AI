"""프롬프트 끼우기·글(engines/v1/prompts.py·texts.py — RP1 §3 S7). 순수 층."""

import hashlib
import re
from pathlib import Path

from esgapi.drafting.engines.v1 import prompts
from esgapi.drafting.engines.v1.texts import DEFAULT_TEXTS


def test_render_is_one_pass() -> None:
    assert prompts.render("{a} {b}", {"{a}": "{b}", "{b}": "x"}) == "{b} x"
    assert prompts.render("{없는 자리}", {"{a}": "1"}) == "{없는 자리}"


def test_map_and_draft_texts() -> None:
    outline = prompts.outline_lines([("k", ("환경", "기후"), "  요구\n" + "가" * 400)])
    assert outline == "k | 환경 > 기후 | 요구 " + "가" * 297
    system, user = prompts.map_texts(DEFAULT_TEXTS, outline, "[PAGE 1]\n글")
    assert system == DEFAULT_TEXTS.map_system
    assert user == f"[목차 잎 — key | 제목 경로 | 요구 내용]\n{outline}\n\n[쪽 글]\n[PAGE 1]\n글"
    _, user = prompts.draft_texts(DEFAULT_TEXTS, ("환경", "기후"), "배출량", "[PAGE 2]\n{쪽 글}")
    assert user == "[목차 잎] 환경 > 기후\n[요구 내용] 배출량\n\n[쪽 글]\n[PAGE 2]\n{쪽 글}"


def test_readme_fingerprints_match() -> None:
    """prompts/README.md 「기본 글 지문」 표(칸 넷)가 DEFAULT_TEXTS 와 같다. 바뀌면 README 를 다시 잰다."""
    readme = Path(prompts.__file__).resolve().parents[2] / "prompts" / "README.md"
    rows = re.findall(r"^\| `([a-z_]+)` \| `([0-9a-f]{64})` \|$", readme.read_text(encoding="utf-8"), re.M)
    fields = ("map_system", "map_user", "draft_system", "draft_user")
    assert dict(rows) == {name: hashlib.sha256(getattr(DEFAULT_TEXTS, name).encode()).hexdigest() for name in fields}
