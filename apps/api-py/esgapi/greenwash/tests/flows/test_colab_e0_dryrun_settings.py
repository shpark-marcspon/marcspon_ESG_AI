"""dry-run 의 판정 몫 보정(밴드 G2c2 Q8 — flows/colab_e0.adjusted_dry_run). 순수 층. 기준 글은 지어낸 것이다.

§3-1-6  기본 판(기준표 없음·기본 판과 같은 기준표) 결과 바이트 그대로 · 고친 판(지어낸 긴 글) eval 몫 = 기본 + 차이 ×
        요청 수(아래끝·위끝, eval 칸과 합) · 다른 칸 그대로 · 표지는 judge 산출에만(결과에 없음) · 토큰을 못 세면
        「못 쟀다」
G2c3 §3-3-2·3  토큰 ≠ 글자인 세기에서 글자 칸은 글자 차이로, 토큰 칸은 토큰 차이로 보정한다(MARC-ISSUE-231 — 기대값은
        수로 박는다·흐름 층은 UTF-8 바이트 세기로 따로 셈)
"""

import copy
import json
from typing import Any

from esgapi.greenwash.engines.e0.ports import CHAT_ENCODING, EMBEDDING_ENCODING, TokenCounter
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.criteria_e0 import default_criteria, eval_pack
from esgapi.greenwash.tests.flows import support as s

LONG = "지어낸 긴 기준 글: " + "근거 없는 환경 주장의 범위와 기준연도를 함께 본다 " * 5


def dry_inputs(criteria: Any) -> colab.GreenwashInputs:
    return colab.GreenwashInputs(
        document=s.SAMPLE_BYTES,
        media_type="application/pdf",
        file_name=s.SAMPLE_NAME,
        ceo="1",
        company="2",
        climate="3~4",
        dry_run=True,
        criteria=criteria,
    )


def long_criteria() -> Any:
    criteria = copy.deepcopy(default_criteria())
    criteria["version"] = "v2"
    criteria["rows"][9]["text"] = LONG.strip()[:300]
    return criteria


def run_dry(criteria: Any, tokens: TokenCounter | None = None) -> Any:
    return s.run(dry_inputs(criteria), s.adapters(tokens=tokens or s.char_counter()))


def snake_dry() -> dict[str, Any]:
    """엔진 dry-run 셈(snake)의 지어낸 꼴: 끝마다 판정 요청 둘, 합 글 10·eval 글 4(토큰도 같은 수)."""
    return {
        end: {
            "chat": {
                "requests": 2,
                "input_chars": 10,
                "input_tokens": {"status": "measured", "encoding": CHAT_ENCODING, "value": 10},
            },
            "chat_by_kind": {
                "eval": {
                    "requests": 2,
                    "input_chars": 4,
                    "input_tokens": {"status": "measured", "encoding": CHAT_ENCODING, "value": 4},
                }
            },
        }
        for end in ("lower", "upper")
    }


def test_the_default_dry_run_is_byte_for_byte_unchanged() -> None:
    plain = run_dry(None)
    same = run_dry(default_criteria())
    assert json.dumps(s.result_of(same), ensure_ascii=False) == json.dumps(s.result_of(plain), ensure_ascii=False)
    assert colab.DRY_EVAL_ADJUSTMENT not in plain.steps["judge"].data  # 기준표 없음 = 지금 갈래
    assert same.steps["judge"].data[colab.DRY_EVAL_ADJUSTMENT] == {"per_request_chars": 0, "per_request_tokens": 0}


def test_the_edited_eval_is_added_per_eval_request() -> None:
    plain, edited = run_dry(None), run_dry(long_criteria())
    diff = len(eval_pack(long_criteria(), PROMPT_VERSION).eval_system_prompt) - len(
        default_prompts(PROMPT_VERSION).eval_system_prompt
    )
    assert diff > 100  # 분모: 지어낸 긴 글
    assert edited.steps["judge"].data[colab.DRY_EVAL_ADJUSTMENT] == {
        "per_request_chars": diff,
        "per_request_tokens": diff,
    }
    base, got = s.result_of(plain)["dryRun"], s.result_of(edited)["dryRun"]
    expected = json.loads(json.dumps(base))
    seen = 0
    for end in ("lower", "upper"):
        requests = expected[end]["chatByKind"]["eval"]["requests"]
        seen += requests
        for tally in (expected[end]["chatByKind"]["eval"], expected[end]["chat"]):
            tally["inputChars"] += requests * diff
            tally["inputTokens"]["value"] += requests * diff
    assert seen > 0
    assert got == expected  # eval 칸과 합 밖(탐지·Low·다시 묻기·임베딩·쪽마다)은 그대로
    assert colab.DRY_EVAL_ADJUSTMENT not in json.dumps(s.result_of(edited))  # 결과 꼴에 표지 없음


def test_an_unmeasured_counter_marks_the_eval_tokens_unmeasured() -> None:
    measured = TokenCounter({CHAT_ENCODING: len, EMBEDDING_ENCODING: len})
    snake = snake_dry()
    adjusted, mark = colab.adjusted_dry_run(snake, measured, default_eval="ab", edited_eval="abcde")
    assert mark == {"per_request_chars": 3, "per_request_tokens": 3}
    assert adjusted["upper"]["chat"]["input_chars"] == 16 and adjusted["upper"]["chat"]["input_tokens"]["value"] == 16
    assert snake["upper"]["chat"]["input_chars"] == 10  # 받은 값은 그대로(새 값)
    blind = TokenCounter({EMBEDDING_ENCODING: len})
    adjusted, mark = colab.adjusted_dry_run(snake, blind, default_eval="ab", edited_eval="abcde")
    assert mark == {"per_request_chars": 3, "per_request_tokens": None}
    assert adjusted["lower"]["chat_by_kind"]["eval"]["input_tokens"]["status"] == "unmeasured"
    assert adjusted["lower"]["chat_by_kind"]["eval"]["input_chars"] == 10


def test_chars_and_tokens_are_adjusted_each_by_its_own_difference() -> None:
    # 토큰 = 2 × 글자 + 1: "ab" → 5, "abcde" → 11. 요청 하나의 차이 글자 3·토큰 6, 끝마다 판정 요청 둘
    doubled = TokenCounter({CHAT_ENCODING: lambda t: 2 * len(t) + 1, EMBEDDING_ENCODING: len})
    adjusted, mark = colab.adjusted_dry_run(snake_dry(), doubled, default_eval="ab", edited_eval="abcde")
    assert mark == {"per_request_chars": 3, "per_request_tokens": 6}
    upper = adjusted["upper"]
    assert (upper["chat"]["input_chars"], upper["chat"]["input_tokens"]["value"]) == (16, 22)
    assert (upper["chat_by_kind"]["eval"]["input_chars"], upper["chat_by_kind"]["eval"]["input_tokens"]["value"]) == (
        10,
        16,
    )


def test_the_flow_adjusts_bytes_as_tokens_and_chars_as_chars() -> None:
    utf8 = TokenCounter({CHAT_ENCODING: lambda t: len(t.encode("utf-8")), EMBEDDING_ENCODING: len})
    plain, edited = run_dry(None, utf8), run_dry(long_criteria(), utf8)
    default_eval = default_prompts(PROMPT_VERSION).eval_system_prompt
    edited_eval = eval_pack(long_criteria(), PROMPT_VERSION).eval_system_prompt
    chars = len(edited_eval) - len(default_eval)
    tokens = len(edited_eval.encode("utf-8")) - len(default_eval.encode("utf-8"))
    mark = edited.steps["judge"].data[colab.DRY_EVAL_ADJUSTMENT]
    assert mark == {"per_request_chars": chars, "per_request_tokens": tokens}
    assert mark["per_request_tokens"] != mark["per_request_chars"]  # 분모: 한글이라 바이트 ≠ 글자
    base, got = s.result_of(plain)["dryRun"], s.result_of(edited)["dryRun"]
    seen = 0
    for end in ("lower", "upper"):
        requests = base[end]["chatByKind"]["eval"]["requests"]
        seen += requests
        for before, after in (
            (base[end]["chatByKind"]["eval"], got[end]["chatByKind"]["eval"]),
            (base[end]["chat"], got[end]["chat"]),
        ):
            assert after["inputChars"] == before["inputChars"] + requests * chars, end
            assert after["inputTokens"]["value"] == before["inputTokens"]["value"] + requests * tokens, end
    assert seen > 0
