# pyright: basic, reportArgumentType=false
# ruff: noqa: E501, RUF005, RUF059  (긴 줄, 목록 잇기, 안 쓰는 풀기 이름 — GW1 그대로)
# ↑ GW1 테스트의 사본(import 경로만 바꿈). 타입 표기 없는 GW1 의 꼴 그대로라 strict 를 끈다.
#   일부러 틀린 꼴을 넣는 테스트가 있어 인자 꼴 검사도 끈다.
"""셀 14 의 1·6·7절: 설정 다듬기, 후보 탐지, 추리기, 근거, 판정, 쪽 분석, 스캔. 답은 대본대로 답하는 모의 대화가 낸다."""

import json

import pytest

from esgapi.greenwash.engines.e0 import heuristics
from esgapi.greenwash.engines.e0.checker import (
    GreenwashingChecker,
    GWConfig,
    sanitize_config_dict,
    scan_report_greenwashing_pages,
)
from esgapi.greenwash.engines.e0.ports import ScriptedChat
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.tests.conftest import LONG_FIX, LOW, NONLOW, StubIndex, chunk, eval_json, make_docs

PACK = default_prompts(PROMPT_VERSION)
LOW_REPLY = {
    "json": {
        "low_reason_bullets": ["하나", "둘", "셋"],
        "fix_paragraph": "의지를 밝힌 글만으로는 성과를 가늠하기 어렵습니다. 수치와 기한이 있는 목표를 앞에 두는 편이 좋겠습니다.",
    }
}


def checker(script, texts=("가",), index=None, **cfg):
    chat = ScriptedChat(script)
    return GreenwashingChecker(make_docs(list(texts)), index or StubIndex(), chat, cfg=GWConfig(**cfg)), chat


def detect_reply(sentences):
    return {"json": [{"sentence": s} for s in sentences]}


# ---------------- 설정 ----------------
def test_config_defaults_and_sanitize():
    cfg = GWConfig()
    assert (
        cfg.max_candidates_per_page,
        cfg.max_chars_page_text,
        cfg.evidence_k,
        cfg.max_chars_per_chunk,
        cfg.max_chars_evidence_total,
        cfg.use_evidence_failopen,
        cfg.report_levels,
        cfg.prompt_version,
    ) == (3, 2500, 2, 450, 1600, False, ("High", "Mid", "Low"), "2026-01-15-v1")
    out = sanitize_config_dict(
        {
            "max_candidates_per_page": 99,
            "evidence_k": 0,
            "max_chars_page_text": "x",
            "debug": 1,
            "report_levels": "High, Mid",
            "prompt_version": "  ",
        }
    )
    assert out == {
        "max_candidates_per_page": 5,
        "evidence_k": 1,
        "max_chars_page_text": 800,
        "debug": True,
        "report_levels": ("High", "Mid"),
        "prompt_version": "2026-01-15-v1",
    }


# ---------------- 후보 탐지 ----------------
def test_detect_sends_system_and_user_and_keeps_at_most_three():
    c, chat = checker({"detect": [detect_reply(NONLOW + ["  "])]})
    got = c.detect_candidates("쪽 글", 7)
    assert [x["sentence"] for x in got] == NONLOW[:3]
    system, user = chat.sent[0]
    assert (system.role, user.role) == ("system", "user")
    assert system.content == PACK.detect_system_prompt
    assert (
        user.content
        == "아래 텍스트는 ESG 보고서의 7페이지 일부입니다.\n이 텍스트 안에서 그린워싱 의심 후보 문장을 찾아주세요.\n\n[텍스트]\n쪽 글"
    )


def test_detect_does_not_check_sentence_is_on_the_page():
    # 흠 6: 쪽 글에 없는 문장도 그대로 후보가 된다.
    c, _ = checker({"detect": [detect_reply(["쪽 글에 없는 온실가스 문장입니다."])]})
    assert c.detect_candidates("전혀 다른 글", 1) == [{"sentence": "쪽 글에 없는 온실가스 문장입니다."}]


@pytest.mark.parametrize("reply", ['{"sentence": "배열이 아님"}', "JSON 이 아님", '[1, "글"]', ""])
def test_detect_returns_nothing_for_non_list_or_broken(reply):
    c, _ = checker({"detect": [reply]})
    assert c.detect_candidates("쪽 글", 1) == []


# ---------------- 추리기 ----------------
def test_filter_and_rank_counts_drops_and_keeps_top_three_by_score():
    c, _ = checker({})
    cands = [
        {"sentence": s}
        for s in [
            "짧다.",  # 제목 꼴(15자 미만)
            "고객과 함께 성장하는 회사가 되겠습니다.",  # 환경 낱말 없음
            "구분 | 온실가스 배출량 | 2023 | 2024 | 증감",  # 표 꼴
            "온실가스 emissions were reduced across every site",  # 점수 0.2
            *NONLOW,
        ]
    ]
    kept, stats = c.filter_and_rank(cands)
    assert stats == {
        "raw": 8,
        "hard_dropped": 1,
        "non_env_dropped": 1,
        "promo_dropped": 0,
        "table_dropped": 1,
        "kept": 3,
    }
    assert [k["sentence"] for k in kept] == NONLOW[:3]
    assert all("_score" not in k for k in kept)


def test_table_like_survives_when_it_has_a_high_risk_word():
    c, _ = checker({})
    kept, stats = c.filter_and_rank([{"sentence": "구분 | 탄소 중립 달성 | 100% | 온실가스"}])
    assert stats["table_dropped"] == 0 and len(kept) == 1


# ---------------- 근거 ----------------
def test_evidence_asks_for_twelve_keeps_allowed_pages_first_two_and_cuts_chunks():
    index = StubIndex(
        [
            chunk(5, "다섯째 쪽"),
            chunk(1, "가" * 500),
            chunk(5, "또 다섯째"),
            chunk(2, "둘째\n쪽  글"),
            chunk(1, "셋째로 온 것"),
        ]
    )
    c, _ = checker({}, index=index)
    text, pages = c.build_evidence("물음 문장", allowed_pages=[1, 2])
    assert index.calls == [("물음 문장", 12)]
    assert text == "[p.1]\n" + "가" * 450 + " ...\n\n[p.2]\n둘째 쪽 글"
    assert pages == [1, 2]


def test_evidence_is_empty_when_nothing_is_on_allowed_pages():
    c, _ = checker({}, index=StubIndex([chunk(5, "다섯째 쪽")]))
    assert c.build_evidence("물음", allowed_pages=[1]) == ("", [])


def test_evidence_failopen_and_no_filter_without_allowed_pages():
    idx = StubIndex([chunk(5, "다섯째"), chunk(6, "여섯째"), chunk(7, "일곱째")])
    c, _ = checker({}, index=idx, use_evidence_failopen=True)
    assert c.build_evidence("물음", allowed_pages=[1])[1] == [5, 6]
    c, _ = checker({}, index=idx)
    assert c.build_evidence("물음", allowed_pages=None)[1] == [5, 6]


def test_evidence_fetch_grows_with_k_and_total_cap_cuts():
    # 합 1,600자 상한은 기본 설정(조각 2 × 450자)으로는 닿지 않는다. evidence_k 를 올려 잰다.
    idx = StubIndex([chunk(1, "나" * 500)] * 30)
    c, _ = checker({}, index=idx, evidence_k=5)
    text, pages = c.build_evidence("물음", allowed_pages=[1])
    assert idx.calls == [("물음", 25)]
    assert len(text) == 1600 + len("\n...(truncated)") and text.endswith("\n...(truncated)")
    assert pages == [1]
    c, _ = checker({}, index=StubIndex([chunk(1, "나" * 500)] * 30))
    assert len(c.build_evidence("물음", allowed_pages=[1])[0]) == 2 * (len("[p.1]\n") + 450 + len(" ...")) + 2


# ---------------- 판정 ----------------
def judge(reply, evidence="[p.1]\n근거", repair=None):
    script = {"eval": [reply], "repair": [repair if repair is not None else {"json": {"fix_paragraph": LONG_FIX}}]}
    c, chat = checker(script)
    return c.eval_high_mid_or_nonrisk("문장", evidence), chat


def test_eval_message_and_plain_high():
    out, chat = judge(eval_json("High"))
    assert chat.sent[0][0].content == PACK.eval_system_prompt
    assert chat.sent[0][1].content == "[문장]\n문장\n\n[근거 컨텍스트]\n[p.1]\n근거\n"
    assert len(chat.sent) == 1  # 수정 방향이 길고 구체적이면 다시 묻지 않는다
    assert out == {
        "decision": "High",
        "risk_tags": ["꼬리표"],
        "confirmed_in_evidence": ["사실 하나", "사실 둘"],
        "missing_fields": [],
        "reason_bullets": ["까닭"],
        "fix_paragraph": LONG_FIX,
        "evidence_internal": "근거 한 줄(p.1)",
    }


def test_eval_without_evidence_says_no_evidence_and_nonrisk_becomes_mid():
    out, chat = judge(eval_json("NonRisk"), evidence="")
    assert chat.sent[0][1].content == "[문장]\n문장\n\n[근거 컨텍스트]\n[근거 없음]\n"
    assert out["decision"] == "Mid"


def test_nonrisk_passes_only_with_no_missing_fields_and_two_confirmed():
    assert judge(eval_json("NonRisk"))[0] == {
        "decision": "NonRisk",
        "risk_tags": ["꼬리표"],
        "confirmed_in_evidence": ["사실 하나", "사실 둘"],
        "missing_fields": [],
        "reason_bullets": [],
        "fix_paragraph": "",
        "evidence_internal": "근거 한 줄(p.1)",
    }
    assert judge(eval_json("NonRisk", missing_fields=["범위/경계"]))[0]["decision"] == "Mid"
    assert judge(eval_json("NonRisk", confirmed_in_evidence=["사실 하나"]))[0]["decision"] == "Mid"


@pytest.mark.parametrize(
    "reply",
    [
        eval_json("Low"),
        eval_json("높음"),
        eval_json(""),
        "JSON 이 아님",
        "[]",
        "```json\n" + json.dumps(eval_json("High")["json"], ensure_ascii=False) + "\n```",
    ],
)
def test_odd_decisions_and_broken_or_fenced_replies_become_mid(reply):
    assert judge(reply)[0]["decision"] == "Mid"


def test_short_or_generic_fix_asks_once_more():
    out, chat = judge(eval_json("Mid", fix_paragraph="범위를 명확히 제시해야 합니다."))
    assert len(chat.sent) == 2
    assert chat.sent[1][0].content == PACK.repair_fix_prompt
    assert chat.sent[1][1].content == "[문장]\n문장\n\n[근거 컨텍스트]\n[p.1]\n근거\n\n[리스크 등급]\nMid\n"
    assert out["fix_paragraph"] == LONG_FIX
    generic = "용어와 대상과 기간에 대한 설명을 문장 안에 명확히 추가 하는 것이 좋겠다는 의견이며 " * 4
    assert len(generic) >= 120 and len(judge(eval_json("High", fix_paragraph=generic))[1].sent) == 2
    assert (
        len(judge(eval_json("High", fix_paragraph=generic + " 2030년"))[1].sent) == 1
    )  # 구체 단서가 있으면 일반론이 아니다


def test_fallback_when_fix_stays_short_and_default_reason():
    out, chat = judge(
        eval_json("High", fix_paragraph="", reason_bullets=[], missing_fields=["범위"]), repair="고칠 수 없음"
    )
    assert len(chat.sent) == 2
    assert out["fix_paragraph"] == heuristics._fallback_fix_paragraph(["범위"])
    assert out["reason_bullets"] == ["근거 컨텍스트 대비 표현의 범위·기준·방법 또는 수치 정보가 충분히 확인되지 않음."]


def test_fix_gets_a_polite_tail():
    fix = LONG_FIX[: -len("바람직합니다.")] + "좋음"
    assert judge(eval_json("High", fix_paragraph=fix))[0]["fix_paragraph"] == fix + ". 추가 보완이 필요합니다."


def test_non_string_decision_raises():
    c, _ = checker({"eval": [eval_json(3)]})
    with pytest.raises(AttributeError):
        c.eval_high_mid_or_nonrisk("문장", "근거")


def test_low_only_reply_defaults():
    c, chat = checker(
        {"low_only": [LOW_REPLY, {"json": {"low_reason_bullets": [], "fix_paragraph": "짧음"}}, "JSON 이 아님"]}
    )
    out = c.eval_low_only("문장", "")
    assert chat.sent[0][0].content == PACK.low_only_prompt and "[근거 없음]" in chat.sent[0][1].content
    assert out == {"reason_bullets": ["하나", "둘"], "fix_paragraph": LOW_REPLY["json"]["fix_paragraph"]}
    fixed = "선언적·리드성 문장은 최소화하고, 핵심 환경 성과·구체 목표·이행 현황 중심으로 공시의 중심을 재배치하는 것이 바람직합니다."
    for _ in range(2):  # 40자 미만이면 고정 문구
        assert c.eval_low_only("문장", "") == {
            "reason_bullets": ["선언적·포괄적 표현이 구체 성과/목표와 분리되어 공시 실질성을 약화시킬 수 있음."],
            "fix_paragraph": fixed,
        }


# ---------------- 쪽 분석 ----------------
def test_page_takes_three_nonlow_plus_one_low_rule_candidates_first():
    page = " ".join(LOW + NONLOW)  # 규칙 후보는 LOW 둘
    script = {
        "detect": [detect_reply([NONLOW[3], NONLOW[2], NONLOW[1]])],
        "eval": [eval_json("High")],
        "low_only": [LOW_REPLY],
    }
    index = StubIndex([chunk(1, "근거 글")])
    c, chat = checker(script, texts=[page], index=index)
    results, stats = c.analyze_page(1, evidence_allowed_pages=[1])
    assert stats == {
        "raw": 5,
        "hard_dropped": 0,
        "non_env_dropped": 0,
        "promo_dropped": 0,
        "table_dropped": 0,
        "kept": 4,
    }
    assert [(r["sentence"], r["level"]) for r in results] == [
        (NONLOW[3], "High"),
        (NONLOW[2], "High"),
        (NONLOW[1], "High"),
        (LOW[0], "Low"),
    ]
    kinds = [m[0].content for m in chat.sent]
    assert kinds == [PACK.detect_system_prompt] + [PACK.eval_system_prompt] * 3 + [PACK.low_only_prompt]
    assert [q for q, _ in index.calls] == [NONLOW[3], NONLOW[2], NONLOW[1], LOW[0]]  # Low 문장도 근거를 찾는다
    low = results[-1]
    assert low["risk_tags"] == ["선언적 문장"] and low["evidence_internal"] == "" and low["evidence_pages"] == [1]
    assert low["fix"] == low["action"] == low["fix_paragraph"]  # 같은 글 세 벌


def test_rule_candidates_come_before_ai_candidates_and_duplicates_are_dropped():
    rule = "2030년까지 온실가스 배출량을 40% 줄이는 것을 목표로 합니다."  # 규칙 후보이되 숫자가 있어 Low 가 아니다
    page = rule + " " + NONLOW[0]
    script = {"detect": [detect_reply([NONLOW[0], rule.replace(" ", "  "), NONLOW[0]])], "eval": [eval_json("High")]}
    c, chat = checker(script, texts=[page], index=StubIndex())
    results, stats = c.analyze_page(1, evidence_allowed_pages=[1])
    assert stats["raw"] == 2
    assert [r["sentence"] for r in results] == [rule, NONLOW[0]]


def test_page_text_sent_to_detect_is_cut_at_2500_and_rule_candidates_come_from_cut_text():
    page = "가" * 2495 + " " + LOW[0] + " " + NONLOW[0]
    c, chat = checker({"detect": ["[]"]}, texts=[page])
    results, stats = c.analyze_page(1, evidence_allowed_pages=[1])
    sent = chat.sent[0][1].content
    assert sent.endswith("[텍스트]\n" + page[:2500] + "\n...\n(이 페이지 텍스트는 일부만 잘라서 제공되었습니다.)")
    assert (results, stats["raw"]) == ([], 0)  # 2,500자 뒤의 선언문은 규칙 후보가 되지 못한다


def test_empty_page_sends_nothing_and_nonrisk_is_left_out():
    c, chat = checker({}, texts=["   "])
    assert c.analyze_page(1, None) == (
        [],
        {"raw": 0, "hard_dropped": 0, "non_env_dropped": 0, "promo_dropped": 0, "table_dropped": 0, "kept": 0},
    )
    assert chat.sent == []
    c, _ = checker(
        {"detect": [detect_reply(NONLOW[:2])], "eval": [eval_json("NonRisk"), eval_json("Mid")]},
        texts=["쪽 글"],
        index=StubIndex([chunk(1, "근거")]),
    )
    results, stats = c.analyze_page(1, [1])
    assert [r["level"] for r in results] == ["Mid"] and stats["kept"] == 2


# ---------------- 스캔 ----------------
def test_scan_counts_failed_pages_and_goes_on(sample_docs):
    # 흠 12·17: 글자열이 아닌 decision 은 그 쪽 전체를 실패로 넘긴다. 그 쪽의 후보는 집계에 들지 않는다.
    script = {"detect": [detect_reply(NONLOW[:1])], "eval": [eval_json(3), eval_json("High")], "low_only": [LOW_REPLY]}
    chat = ScriptedChat(script)
    out = scan_report_greenwashing_pages(
        sample_docs, [2, 1, 2, 0, 99, "x"], config={"debug": True, "debug_pages": 2}, vectorstore=StubIndex(), llm=chat
    )
    assert out.pages_norm == [1, 2] and out.allowed_norm == [1, 2]
    assert out.failed == 1 and [f["page"] for f in out.failed_pages] == [1]
    assert "strip" in out.failed_pages[0]["error"]
    assert [r["page"] for r in out.results] == [2]
    assert out.agg["raw"] == 1 and out.agg["kept"] == 1  # 쪽 2 의 것만(쪽 1 은 규칙 후보가 셋인데도 들지 않는다)


def test_scan_report_levels_filter_and_missing_ports(sample_docs):
    script = {"detect": [detect_reply(NONLOW[:1])], "eval": [eval_json("High")], "low_only": [LOW_REPLY]}
    out = scan_report_greenwashing_pages(
        sample_docs, [1], config={"report_levels": ["Low"]}, vectorstore=StubIndex(), llm=ScriptedChat(script)
    )
    assert [r["level"] for r in out.results] == ["Low"]
    assert (
        scan_report_greenwashing_pages(sample_docs, [], vectorstore=StubIndex(), llm=ScriptedChat(script)).results == []
    )
    with pytest.raises(ValueError):
        scan_report_greenwashing_pages(sample_docs, [1], vectorstore=None, llm=ScriptedChat(script))
    with pytest.raises(ValueError):
        scan_report_greenwashing_pages(sample_docs, [1], vectorstore=StubIndex(), llm=None)


# ---------------- 문턱값 ----------------
def test_fix_shorter_than_sixty_falls_back_and_sixty_stays():
    keep = "가" * 56 + "합니다."  # 60자
    short = "가" * 55 + "합니다."  # 59자
    assert len(keep) == 60 and len(short) == 59
    reply = {"json": {"fix_paragraph": keep}}
    assert judge(eval_json("High", fix_paragraph=""), repair=reply)[0]["fix_paragraph"] == keep
    reply = {"json": {"fix_paragraph": short}}
    assert judge(eval_json("High", fix_paragraph=""), repair=reply)[0][
        "fix_paragraph"
    ] == heuristics._fallback_fix_paragraph([])


def test_generic_fix_threshold_is_120_chars():
    specific = "2030년 " + "가" * 110 + "합니다."  # 120자, 구체 단서 있음
    assert len(specific) == 120
    assert len(judge(eval_json("High", fix_paragraph=specific))[1].sent) == 1
    assert len(judge(eval_json("High", fix_paragraph=specific[1:]))[1].sent) == 2  # 119자


def test_low_fix_shorter_than_forty_becomes_the_fixed_text_and_forty_stays():
    keep = "가" * 36 + "합니다."  # 40자
    short = "가" * 35 + "합니다."  # 39자
    c, _ = checker(
        {
            "low_only": [
                {"json": {"low_reason_bullets": ["하나"], "fix_paragraph": keep}},
                {"json": {"low_reason_bullets": ["하나"], "fix_paragraph": short}},
            ]
        }
    )
    assert c.eval_low_only("문장", "")["fix_paragraph"] == keep
    assert c.eval_low_only("문장", "")["fix_paragraph"].startswith("선언적·리드성 문장은 최소화하고")


def test_evidence_internal_is_stripped_and_non_string_sentence_fails_the_page(sample_docs):
    assert judge(eval_json("High", evidence_internal="  근거  "))[0]["evidence_internal"] == "근거"
    out = scan_report_greenwashing_pages(
        sample_docs, [2], vectorstore=StubIndex(), llm=ScriptedChat({"detect": [{"json": [{"sentence": 5}]}]})
    )
    assert out.failed == 1 and out.results == []
    c, _ = checker({"eval": [eval_json("Mid", fix_paragraph=7)]})
    with pytest.raises(AttributeError):
        c.eval_high_mid_or_nonrisk("문장", "근거")
