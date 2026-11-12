"""목록 줄 levelCounts 의 효력 등급 셈(actions/checks.effective_level_counts — 밴드 G1b-3 §2-4). 순수 층(DB 없음).

잰다: 고침 없음 = 결과 counts.byLevel 그대로 · 고친 문장마다 AI 등급 −1·고친 등급 +1 · 합은 그대로 · 결과 밖
itemIndex 는 세지 않음 · dry-run(counts null)은 None. 결과는 계약 예시(지어낸 것)다.
"""

import json
from pathlib import Path
from typing import Any

from esgapi.greenwash.service.actions.checks import effective_level_counts

EXAMPLES = Path(__file__).resolve().parents[2] / "data" / "contract-examples"


def example(name: str) -> dict[str, Any]:
    body: dict[str, Any] = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return body


def test_no_edits_is_the_result_count() -> None:
    result = example("result-normal")
    assert effective_level_counts(result, {}) == result["counts"]["byLevel"]


def test_each_edited_sentence_moves_one_from_its_ai_level_to_its_edited_level() -> None:
    """result-normal: 0 High · 1 Mid · 2 Mid · 3 Low → 0 을 Low, 3 을 High."""
    result = example("result-normal")
    assert effective_level_counts(result, {0: "Low", 3: "High"}) == {"High": 1, "Mid": 2, "Low": 1}
    assert effective_level_counts(result, {0: "Low", 1: "Low"}) == {"High": 0, "Mid": 1, "Low": 3}
    assert effective_level_counts(result, {1: "High", 2: "High"}) == {"High": 3, "Mid": 0, "Low": 1}


def test_an_index_outside_the_result_is_not_counted() -> None:
    result = example("result-normal")
    assert effective_level_counts(result, {4: "High", -1: "High"}) == result["counts"]["byLevel"]


def test_a_dry_run_result_has_no_counts() -> None:
    result = example("result-dry-run")
    assert result["counts"] is None
    assert effective_level_counts(result, {0: "High"}) is None


def test_a_rejudge_basis_counts_unless_the_level_was_edited() -> None:
    """GRJ1(감독 R5): 효력 등급 = 고친 등급 ?? 기준 판단 ?? 첫 판단. 기준이 리스크 아님(None)이면 세 칸 밖(합이
    준다)."""
    result = example("result-normal")
    assert effective_level_counts(result, {}, {0: "Low"}) == {"High": 0, "Mid": 2, "Low": 2}
    assert effective_level_counts(result, {0: "Mid"}, {0: "Low"}) == {"High": 0, "Mid": 3, "Low": 1}
    assert effective_level_counts(result, {}, {1: None}) == {"High": 1, "Mid": 1, "Low": 1}
    assert effective_level_counts(result, {1: "High"}, {1: None}) == {"High": 2, "Mid": 1, "Low": 1}
    assert effective_level_counts(result, {}, {9: "High"}) == result["counts"]["byLevel"]
