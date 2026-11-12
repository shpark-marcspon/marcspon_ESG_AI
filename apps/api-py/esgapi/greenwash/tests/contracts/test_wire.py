"""밴드 GC3: 흐름 꼴 넷의 키는 camelCase(pydantic to_camel 규칙), 엔진의 snake 를 옮기는 경계는
wire.result_to_wire 하나.

(a) 이름 규칙 — 네 꼴 모듈의 TypedDict 필드 키 전부. 예외는 값이 키인 꼴 둘(LevelCounts·GreenwashCompareCounts)뿐.
(b) result_to_wire — 흐름이 지은 snake 결과(정상·dry-run)를 옮기면 result@1 strict 를 지나고, 값이 키인 자리는 그대로,
    입력은 바뀌지 않고, 키가 겹치면 ValueError. snake 결과는 assemble 이 wire 에 넘기는 값을 붙잡아 얻는다.
"""

import copy
import typing
from types import ModuleType
from typing import Any, get_args

import pytest
from pydantic.alias_generators import to_camel

from esgapi.greenwash.contracts import compare_shapes, rejudge_shapes, review_shapes, shapes, terms_shapes, wire
from esgapi.greenwash.tests.flows import support as s

MODULES: tuple[ModuleType, ...] = (shapes, review_shapes, compare_shapes, terms_shapes, rejudge_shapes)
VALUE_KEYED = {"LevelCounts", "GreenwashCompareCounts"}
"""값이 키인 꼴 — 키가 값(level·outcome)과 같아야 해서 이름 규칙 밖이다."""

RENAMED: dict[str, list[tuple[str, str]]] = {
    "Source": [("file_name", "fileName"), ("page_count", "pageCount")],
    "CheckerConfig": [
        ("max_candidates_per_page", "maxCandidatesPerPage"),
        ("max_chars_page_text", "maxCharsPageText"),
        ("evidence_k", "evidenceK"),
        ("max_chars_per_chunk", "maxCharsPerChunk"),
        ("use_evidence_failopen", "useEvidenceFailopen"),
        ("max_chars_evidence_total", "maxCharsEvidenceTotal"),
        ("report_levels", "reportLevels"),
        ("debug_pages", "debugPages"),
        ("batch_eval", "batchEval"),
        ("prompt_version", "promptVersion"),
    ],
    "ChunkingConfig": [
        ("chunk_size", "chunkSize"),
        ("chunk_overlap", "chunkOverlap"),
        ("embedding_batch_size", "embeddingBatchSize"),
    ],
    "ChatParams": [("max_tokens", "maxTokens")],
    "Item": [
        ("risk_tags", "riskTags"),
        ("confirmed_in_evidence", "confirmedInEvidence"),
        ("missing_fields", "missingFields"),
        ("reason_bullets", "reasonBullets"),
        ("fix_paragraph", "fixParagraph"),
        ("evidence_pages", "evidencePages"),
        ("evidence_internal", "evidenceInternal"),
        ("example_sentence", "exampleSentence"),
    ],
    "CandidateStats": [
        ("hard_dropped", "hardDropped"),
        ("non_env_dropped", "nonEnvDropped"),
        ("promo_dropped", "promoDropped"),
        ("table_dropped", "tableDropped"),
        ("failed_pages", "failedPages"),
    ],
    "Counts": [("by_level", "byLevel"), ("by_part", "byPart")],
    "Tally": [("input_chars", "inputChars"), ("input_tokens", "inputTokens")],
    "ByKind": [("low_only", "lowOnly")],
    "DryRunLower": [("chat_by_kind", "chatByKind"), ("embedding_queries", "embeddingQueries")],
    "DryRunUpper": [
        ("chat_by_kind", "chatByKind"),
        ("embedding_queries", "embeddingQueries"),
        ("output_tokens_max", "outputTokensMax"),
        ("evidence_chars", "evidenceChars"),
        ("evidence_cap_reached", "evidenceCapReached"),
    ],
    "DryRunPage": [("text_chars", "textChars"), ("rule_candidates", "ruleCandidates"), ("lower_judged", "lowerJudged")],
    "DryRun": [
        ("pages_checked", "pagesChecked"),
        ("pages_with_text", "pagesWithText"),
        ("pages_truncated", "pagesTruncated"),
        ("embedding_index", "embeddingIndex"),
        ("rule_candidates", "ruleCandidates"),
        ("per_page", "perPage"),
    ],
    "ScanResult": [
        ("prompt_version", "promptVersion"),
        ("extra_terms", "extraTerms"),
        ("candidate_stats", "candidateStats"),
        ("word_counts", "wordCounts"),
        ("dry_run", "dryRun"),
    ],
    "DryRunResult": [
        ("prompt_version", "promptVersion"),
        ("extra_terms", "extraTerms"),
        ("candidate_stats", "candidateStats"),
        ("word_counts", "wordCounts"),
        ("dry_run", "dryRun"),
    ],
    "GreenwashReviewMark": [("item_index", "itemIndex"), ("exclude_reason", "excludeReason")],
    "GreenwashReviewState": [("run_id", "runId"), ("confirmed_at", "confirmedAt"), ("confirmed_by", "confirmedBy")],
    "GreenwashCompareSide": [("document_id", "documentId"), ("run_id", "runId"), ("version_label", "versionLabel")],
    "GreenwashItemRef": [("item_index", "itemIndex")],
}
"""GC3 가 바꾼 키 69쌍(옛 → 새), 꼴별."""


def typed_dicts() -> dict[str, type]:
    found: dict[str, type] = {}
    for module in MODULES:
        for name, value in vars(module).items():
            if typing.is_typeddict(value) and value.__module__ == module.__name__:
                found[name] = value
    return found


def keys(cls: type) -> list[str]:
    return list(cls.__annotations__)


# ── (a) 이름 규칙 ──


def test_every_shape_key_is_camel_case_except_the_value_keyed_two() -> None:
    shapes_found = typed_dicts()
    assert set(shapes_found) >= VALUE_KEYED
    bad = [
        (name, key)
        for name, cls in shapes_found.items()
        if name not in VALUE_KEYED
        for key in keys(cls)
        if "_" in key or to_camel(key) != key
    ]
    assert bad == []
    # 166 + review@2 의 edits 칸 1 과 새 꼴 다섯의 키 17(G1b-3) + 판 단어 꼴 둘의 키 4(G2d — terms_shapes)
    # + 결과 두 갈래의 terms 2(G2d ③) + review@3 의 evidence·rejudges 2 와 새 꼴 넷의 키 24(GRJ1)
    # + 재판단 꼴 다섯의 키 27(GRJ1 — rejudge_shapes) + 재판단 옵션의 promptVersion 1(GRS1)
    assert sum(len(keys(cls)) for cls in shapes_found.values()) == 244


def test_the_69_renamed_keys_are_all_new_and_none_old() -> None:
    shapes_found = typed_dicts()
    assert sum(len(pairs) for pairs in RENAMED.values()) == 69
    for name, pairs in RENAMED.items():
        present = set(keys(shapes_found[name]))
        assert [old for old, _ in pairs if old in present] == [], name
        assert [new for _, new in pairs if new not in present] == [], name
        assert all(to_camel(old) == new for old, new in pairs), name
    old_everywhere = {old for pairs in RENAMED.values() for old, _ in pairs}
    assert {key for cls in shapes_found.values() for key in keys(cls)} & old_everywhere == set()


def test_the_value_keyed_shapes_use_the_values_as_keys() -> None:
    assert keys(shapes.LevelCounts) == list(get_args(shapes.Level))
    assert keys(compare_shapes.GreenwashCompareCounts) == list(get_args(compare_shapes.GreenwashCompareOutcome))


def test_terms_default_has_nothing_to_rename() -> None:
    assert keys(terms_shapes.GreenwashDefaultTerms) == ["terms"]


# ── (b) result_to_wire ──


def snake_of(monkeypatch: pytest.MonkeyPatch, *, dry_run: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """흐름을 돌려 assemble 이 wire 에 넘긴 snake 결과와 흐름의 결과를 함께 돌려준다."""
    seen: list[dict[str, Any]] = []
    original = wire.result_to_wire

    def spy(result: dict[str, Any]) -> dict[str, Any]:
        seen.append(copy.deepcopy(result))
        return original(result)

    monkeypatch.setattr(wire, "result_to_wire", spy)
    used = s.adapters(tokens=s.char_counter()) if dry_run else s.adapters()
    result = s.result_of(s.run(s.inputs(dry_run=dry_run), used))
    monkeypatch.setattr(wire, "result_to_wire", original)
    (snake,) = seen
    return snake, result


@pytest.mark.parametrize("dry_run", [False, True])
def test_the_flows_snake_result_becomes_result_at_1(monkeypatch: pytest.MonkeyPatch, dry_run: bool) -> None:
    snake, result = snake_of(monkeypatch, dry_run=dry_run)
    assert "dry_run" in snake and "dryRun" not in snake
    before = copy.deepcopy(snake)
    wired = wire.result_to_wire(snake)
    assert snake == before  # 입력은 그대로
    assert wired == result
    shapes.RESULT_SHAPES[shapes.SHAPE].validate_python(wired, strict=True)
    assert next(iter(wired)) == "schemaVersion"


def test_value_keyed_places_keep_their_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    snake, _ = snake_of(monkeypatch, dry_run=False)
    levels = {"High": 1, "Mid": 0, "Low": 2}
    snake["counts"]["by_level"] = dict(levels)
    snake["counts"]["by_part"] = {"CEO 메시지": dict(levels), "Part_a": {"High": 0, "Mid": 1, "Low": 0}}
    before = copy.deepcopy(snake)
    wired = wire.result_to_wire(snake)
    assert snake == before
    assert wired["counts"]["byLevel"] == levels
    assert wired["counts"]["byPart"] == {"CEO 메시지": levels, "Part_a": {"High": 0, "Mid": 1, "Low": 0}}
    assert "partA" not in wired["counts"]["byPart"]
    shapes.RESULT_SHAPES[shapes.SHAPE].validate_python(wired, strict=True)


def test_lists_of_dicts_are_walked_and_a_new_value_is_returned() -> None:
    snake: dict[str, Any] = {
        "per_page": [{"text_chars": 1, "lower_judged": [{"rule_candidates": 2}]}],
        "by_level": {"High": 0},
    }
    wired = wire.result_to_wire(snake)
    assert wired == {"perPage": [{"textChars": 1, "lowerJudged": [{"ruleCandidates": 2}]}], "byLevel": {"High": 0}}
    wired["perPage"][0]["textChars"] = 9
    assert snake["per_page"][0]["text_chars"] == 1


def test_a_key_collision_after_renaming_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="겹친다"):
        wire.result_to_wire({"item_index": 1, "itemIndex": 2})
    with pytest.raises(ValueError, match="겹친다"):
        wire.result_to_wire({"items": [{"risk_tags": [], "riskTags": []}]})
