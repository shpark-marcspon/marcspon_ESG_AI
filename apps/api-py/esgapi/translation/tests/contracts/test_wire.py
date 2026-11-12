"""결과 조립(contracts/wire.py — 발주서 §3 S3): 실제 흐름의 결과(`dataclasses.asdict(TranslationRun)`)를 `to_result` 로
옮긴 dict 가 결과 꼴 translation.result@1 을 strict 로 지난다.
흐름은 support.run_flow(실제 설정 + 모의 공급사 둘, 실호출 0).
고정 스키마와의 글자 대조는 test_shapes.py.
"""

import dataclasses
import hashlib
from collections.abc import Sequence
from typing import Any

import pytest

from esgapi.core.llm.types import ProviderResponse
from esgapi.translation.contracts import shapes
from esgapi.translation.contracts.wire import to_result
from esgapi.translation.engines.colab_158 import gates, prompts, review_rules
from esgapi.translation.engines.colab_158.pipeline import EngineInput
from esgapi.translation.tests.engines.colab_158.support import fail, make_input, ok, refuse, run_flow
from esgapi.translation.tools.llm_bridge import PROMPT_VERSIONS, prompt_id, route_for

SIMPLE = "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다."
SIMPLE_EN = "[BLOCK 1]\nVirtual Title\nVirtual body."
TWO = SIMPLE + "\n[PAGE 2]\n[BLOCK 1]\n가상 둘째"
NO_ISSUES = ok("[]")
GRAMMAR = ok(
    '[{"issue_type": "GRAMMAR", "severity": "HIGH", "original_span": "Virtual body.", '
    '"suggestion": "Virtual text.", "reason": "문법"}]'
)
SOURCE_SHA = hashlib.sha256("가상 원문".encode()).hexdigest()
"""흐름이 셈하는 원문 sha256 의 자리(값은 지어낸 글의 것 — wire 는 옮기기만)."""
CONSTANTS = {
    "editorialQaMinScore": gates.GENERIC_EDITORIAL_QA_MIN_SCORE,
    "tableBatchSize": gates.TABLE_BATCH_SIZE,
    "polishMinChars": gates.EDITORIAL_POLISH_MIN_CHARS,
    "polishMaxChars": gates.EDITORIAL_POLISH_MAX_CHARS,
    "koreanRepairRounds": gates.MAX_UNTRANSLATED_REPAIR_ROUNDS,
    "autofixKoreanRepairRounds": review_rules.PART_QA_AUTOFIX_MAX_KOREAN_REPAIR_ROUNDS,
}

CASES: dict[str, tuple[EngineInput, Sequence[ProviderResponse]]] = {
    "short_general": (make_input(SIMPLE), [ok(SIMPLE_EN), NO_ISSUES]),
    "a_b": (
        make_input(SIMPLE, compare_ab=True),
        [ok(SIMPLE_EN), ok(SIMPLE_EN), NO_ISSUES, NO_ISSUES],
    ),
    "w7_page_error": (
        make_input(SIMPLE + "\n[PAGE 2]\n[BLOCK 1]\n남는 국문"),
        [
            ok(SIMPLE_EN),
            ok("[BLOCK 1]\nleft 국문"),
            ok("[BLOCK 1]\nstill 국문"),
            ok("[BLOCK 1]\nagain 국문"),
            NO_ISSUES,
            NO_ISSUES,
            ok("[PAGE 2]\n[BLOCK 1]\nRemaining text"),
        ],
    ),
    "autofix_applied": (
        make_input(SIMPLE),
        [ok(SIMPLE_EN), GRAMMAR, ok("[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual text, fixed.")],
    ),
    "autofix_stopped": (
        make_input(SIMPLE),
        [ok(SIMPLE_EN), GRAMMAR, ok("[PAGE 1]\n[BLOCK 1]\n남은 국문"), ok("[PAGE 1]\n[BLOCK 1]\n아직 국문")],
    ),
    "a_b_autofix_call_failed": (
        make_input("[PAGE 1]\n[BLOCK 1]\n가", compare_ab=True),
        [
            ok("[BLOCK 1]\nA"),
            ok("[BLOCK 1]\nB"),
            ok(
                '[{"issue_type": "OMISSION", "severity": "HIGH", "original_span": "", '
                '"suggestion": "add", "reason": "빠짐"}]'
            ),
            NO_ISSUES,
            fail(),
        ],
    ),
    "review_stopped": (make_input(TWO), [ok(SIMPLE_EN), ok("[BLOCK 1]\nSecond"), fail()]),
    "review_unreadable": (make_input(SIMPLE, autofix=False), [ok(SIMPLE_EN), ok("not json")]),
    "refusal": (make_input(SIMPLE, autofix=False), [refuse("I can't help with that."), NO_ISSUES]),
    "rejected_no_pages": (make_input(TWO, start=3), []),
    "rejected_ceo_limit": (
        make_input("".join(f"[PAGE {n}]\n[BLOCK 1]\n가상 {n}\n" for n in range(1, 8)), part="ceo_message"),
        [],
    ),
}


def result_of(inputs: EngineInput, replies: Sequence[ProviderResponse]) -> dict[str, Any]:
    flow = run_flow(inputs, replies)
    return to_result(
        dataclasses.asdict(flow.run),
        routes={"translate": route_for("translate", inputs.part), "review": route_for("review", inputs.part)},
        prompt_ids=[prompt_id(site) for site in prompts.SITES],
        constants=CONSTANTS,
        source_sha256=SOURCE_SHA,
        retry=None,
    )


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_assembled_result_fits_the_result_shape(case: str) -> None:
    result = result_of(*CASES[case])
    assert next(iter(result)) == "schemaVersion"
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)


def test_the_cases_cover_every_branch_of_the_result() -> None:
    """갈래마다 경우 하나 이상: 결과 done·rejected 둘, 조각 translated·error,
    검수 reviewed·parse_failed·call_failed·not_run,
    자동수정 done·stopped·not_run(disabled·review_stopped·earlier_variant_stopped), 경고 있음."""
    results = {case: result_of(*CASES[case]) for case in CASES}
    seen: set[str] = set()
    for result in results.values():
        seen.add(f"status:{result['status']}")
        for v in result["variants"]:
            seen.update(f"fragment:{f['status']}" for f in v["fragments"])
            seen.update(f"review:{p['review']['status']}" for p in v["pages"])
            seen.add(f"autofix:{v['autofix']['status']}:{v['autofix']['notRunReason']}")
        if result["warnings"]:
            seen.add("warnings")
    assert seen >= {
        "status:done",
        "status:rejected",
        "fragment:translated",
        "fragment:error",
        "review:reviewed",
        "review:parse_failed",
        "review:call_failed",
        "review:not_run",
        "autofix:done:None",
        "autofix:stopped:None",
        "autofix:not_run:disabled",
        "autofix:not_run:review_stopped",
        "autofix:not_run:earlier_variant_stopped",
        "warnings",
    }
    assert len(CASES) == 11


def test_the_wire_moves_values_without_new_arithmetic() -> None:
    """칸 이름만 바꾼다: 쪽 번호 열쇠는 글자로, 튜플은 목록으로, 엄중도 셈은 엔진의 것 그대로."""
    inputs, replies = CASES["autofix_applied"]
    flow = run_flow(inputs, replies)
    result = result_of(inputs, replies)
    (variant,) = result["variants"]
    (page,) = variant["pages"]
    assert page["review"]["counts"] == {"high": 1, "medium": 0, "low": 0}
    assert flow.run.variants[0].pages[0].counts == (1, 0, 0)
    assert page["review"]["issues"][0]["originalSpan"] == "Virtual body."
    assert variant["autofix"]["pages"][0]["spanReplacements"] == [
        {"issueType": "GRAMMAR", "originalSpan": "Virtual body.", "suggestion": "Virtual text."}
    ]
    assert result["settings"] == {
        "part": "general",
        "variants": ["single"],
        "routes": {"translate": "light-openai-41", "review": "light-openai-41"},
        "promptIds": [f"translation/{site}@{PROMPT_VERSIONS[site]}" for site in prompts.SITES],
        "engine": "colab_158",
        "retry": None,
        "constants": {
            "editorialQaMinScore": 96,
            "tableBatchSize": 24,
            "polishMinChars": 120,
            "polishMaxChars": 6000,
            "koreanRepairRounds": 2,
            "autofixKoreanRepairRounds": 1,
        },
    }
    duplicated = result_of(
        make_input(SIMPLE + "\n[PAGE 1]\n[BLOCK 2]\n가상 더", autofix=False),
        [ok(SIMPLE_EN), ok("[BLOCK 2]\nMore"), NO_ISSUES],
    )
    assert duplicated["document"] == {"pageNumbers": [1, 1], "duplicatePages": {"1": 2}, "sourceSha256": SOURCE_SHA}


def test_a_rejection_has_no_variants() -> None:
    result = result_of(*CASES["rejected_ceo_limit"])
    assert (result["status"], result["variants"]) == ("rejected", [])
    assert result["rejection"] == {
        "kind": "ceo_page_limit",
        "message": "CEO 페이지 수 초과로 실행 중단",
        "pageCount": 7,
        "limit": 6,
    }
    assert result["settings"]["routes"] == {"translate": "standard-openai-41", "review": "light-openai-41"}
