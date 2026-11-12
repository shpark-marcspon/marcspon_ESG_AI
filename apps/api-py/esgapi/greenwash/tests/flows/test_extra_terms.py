"""추가 단어(입력 extra_terms, 밴드 G1c — 발주서 band-handoffs/G1c-order.md §3 의 (a)~(g)).

노트북의 스위치 env_keywords_extra(판정 대상 키워드 = 환경 낱말)를 켜고 빈도 목록에도 더한다. 빈 목록이면 전역을
건드리지 않아 G1a 와 같고, 단어가 있으면 escape 뒤 정규식으로 가며, judge 가 끝나면 전역(흠 18)이 기본으로 돌아온다.
글은 전부 지어낸 것(「초록마루」는 기본 목록에 없는 지어낸 낱말). 실제 공급사 0 — 가짜 어댑터만 쓴다.
"""

import dataclasses
import io
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, cast

import pytest
from openpyxl import load_workbook

from esgapi.core.flows.types import FlowStepFailed
from esgapi.greenwash.contracts import shapes
from esgapi.greenwash.engines.e0 import checker as checker_mod
from esgapi.greenwash.engines.e0 import heuristics
from esgapi.greenwash.engines.e0.gw1 import GREEN_TERMS, frequency_extras, term_key
from esgapi.greenwash.engines.e0.ports import (
    CHAT_ENCODING,
    DEFAULT_SCRIPT,
    EMBEDDING_ENCODING,
    Message,
    ScriptedChat,
    TokenCounter,
    prompt_kind,
)
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.engines.e0.wordcount import normalize_text
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.sample_text import page_texts

WORD = "초록마루"
"""기본 목록에 없는 지어낸 환경 낱말."""
SENTENCE = f"우리는 {WORD} 실천을 꾸준히 확대해 나가겠습니다."
"""WORD 말고는 환경 낱말이 없는 다짐 문장(어미 규칙의 후보가 된다)."""
SYMBOLS = ("가.*", "a\\b", "x+", "y?", "a|b")
"""글자가 섞인 특수문자 단어(글자·숫자가 없는 `.*` 는 입력에서 거절된다 — 아래 _refused 테스트)."""
SYMBOL_LINE = "기호 시험 줄 가.* 와 a\\b 와 x+ 와 y? 와 a|b 끝"
ONE_PAGE = {"ceo": "1", "company": "", "climate": ""}


def default_pattern() -> str:
    built = heuristics.build_env_keywords_re()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("re.Pattern[str]", built).pattern


def global_pattern() -> str:
    found = heuristics._ENV_KEYWORDS_RE  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType, reportUnknownVariableType]
    return cast("re.Pattern[str]", found).pattern


@pytest.fixture(autouse=True)
def the_global_starts_and_ends_at_the_default() -> Iterator[None]:
    assert global_pattern() == default_pattern()
    yield
    assert global_pattern() == default_pattern()


def texts(*lines: str) -> list[str]:
    """표본 네 쪽에서 쪽 1 만 머리말 + lines 로 바꾼다(표본 쪽 1 은 어미 규칙의 후보가 이미 상한 셋이다)."""
    pages = page_texts()
    pages[0] = "\n".join(["가상 머리말", *lines])
    return pages


def given(
    extra: Sequence[str] = (), *, dry_run: bool = False, pages: Mapping[str, str] = ONE_PAGE
) -> colab.GreenwashInputs:
    return dataclasses.replace(s.inputs(dry_run=dry_run, **pages), extra_terms=tuple(extra))


def detect_script(*sentences: str) -> dict[str, list[Any]]:
    """탐지가 늘 sentences 를 후보로 돌려주는 대본(이 테스트가 직접 쓴다 — 표본 대본에 기대지 않음)."""
    return {**DEFAULT_SCRIPT, "detect": [{"json": [{"sentence": x} for x in sentences]}]}


def scan(extra: Sequence[str], *lines: str, candidates: Sequence[str] = (SENTENCE,)) -> dict[str, Any]:
    chat = ScriptedChat(detect_script(*candidates))
    run = s.run(given(extra), s.adapters(llm=chat, pdf=s.SamplePdf(texts(*lines))))
    assert global_pattern() == default_pattern()
    return s.result_of(run)


def dry(extra: Sequence[str], *lines: str) -> dict[str, Any]:
    forbidden = s.Forbidden()
    run = s.run(
        given(extra, dry_run=True),
        s.adapters(llm=forbidden, embedding=forbidden, pdf=s.SamplePdf(texts(*lines)), tokens=s.char_counter()),
    )
    assert forbidden.calls == 0
    assert global_pattern() == default_pattern()
    return s.result_of(run)


def totals(result: Mapping[str, Any]) -> dict[str, int]:
    return {row["term"]: row["count"] for row in result["wordCounts"]["total"]}


class Spy:
    """set_env_keywords 를 부른 인자를 적고 그대로 넘긴다(흐름 쪽 이름과 엔진 쪽 이름 둘 다에 건다)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls: list[tuple[list[str] | None, bool]] = []
        real = cast("Callable[..., None]", heuristics.set_env_keywords)  # pyright: ignore[reportUnknownMemberType]

        def spy(extra_keywords: Sequence[str] | None = None, include_general_env: bool = False) -> None:
            self.calls.append((None if extra_keywords is None else list(extra_keywords), include_general_env))
            real(extra_keywords=extra_keywords, include_general_env=include_general_env)

        monkeypatch.setattr(colab, "set_env_keywords", spy)
        monkeypatch.setattr(checker_mod, "set_env_keywords", spy)


# ── (a) 빈 목록 = G1a ──


def test_empty_extra_terms_give_the_g1a_results_and_never_touch_the_global(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = Spy(monkeypatch)
    chat = ScriptedChat()
    mock = s.result_of(s.run(given((), pages=s.SAMPLE_PAGES), s.adapters(llm=chat)))
    assert mock["extraTerms"] == []
    assert s.as_gw1(mock) == s.gw1_view(s.golden("sample-mock.json"))
    assert s.message_hashes(chat.sent) == s.golden("sample-mock.json")["messages"]
    dry_run = s.result_of(s.run(given((), dry_run=True, pages=s.SAMPLE_PAGES), s.adapters(tokens=s.char_counter())))
    assert dry_run["extraTerms"] == []
    assert dry_run["dryRun"] == s.golden_wire("sample-dryrun.json")["dryRun"]
    none = s.result_of(s.run(given((), pages={"ceo": "", "company": "", "climate": ""}), s.adapters()))
    assert s.as_gw1(none) == s.gw1_view(s.golden("sample-none.json"))
    assert spy.calls == []  # 빈 목록이면 설정도 되돌림도 부르지 않는다


def test_whitespace_only_terms_are_the_empty_list() -> None:
    assert given([" ", "", "\t"]).extra_terms == ()
    assert colab.scan_config(given([" "])) == colab.SCAN_CONFIG


# ── (b) 단어가 들어간다 ──


def test_an_extra_word_keeps_its_sentence_and_is_counted() -> None:
    without = scan((), SENTENCE)
    with_word = scan((WORD,), SENTENCE)
    assert without["candidateStats"]["nonEnvDropped"] == 1  # 환경 낱말이 없어 빠진다
    assert without["candidateStats"]["kept"] == 0 and without["items"] == []
    assert with_word["candidateStats"]["nonEnvDropped"] == 0  # 추가 단어로 후보에 남는다
    assert with_word["candidateStats"]["kept"] >= 1
    assert [SENTENCE in item["sentence"] for item in with_word["items"]] == [True]  # 쪽 글의 머리말과 붙어 나온다
    assert WORD not in totals(without)
    assert totals(with_word)[WORD] == 1
    assert with_word["extraTerms"] == [WORD]
    page_1 = next(p for p in with_word["wordCounts"]["pages"] if p["page"] == 1)
    assert {"term": WORD, "count": 1} in page_1["counts"]


def test_extra_words_come_after_the_default_list() -> None:
    """빈도 목록은 GREEN_TERMS 뒤에 추가 단어 — 수가 같으면 기본 낱말이 앞(Counter.most_common 은 넣은 차례)."""
    terms = [row["term"] for row in scan((WORD,), f"{WORD} 와 생분해 끝")["wordCounts"]["total"]]
    assert terms.index("생분해") < terms.index(WORD)


def test_a_word_that_never_appears_has_no_row() -> None:
    result = scan(("없는낱말",), SENTENCE)
    assert result["extraTerms"] == ["없는낱말"]
    assert "없는낱말" not in totals(result)


# ── (c) 특수문자 ──


def test_symbols_are_escaped_before_the_env_regex(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = Spy(monkeypatch)
    escaped = scan(SYMBOLS, SENTENCE, SYMBOL_LINE)
    assert escaped["candidateStats"]["failedPages"] == []  # 정규식이 깨지지 않는다
    assert escaped["candidateStats"]["nonEnvDropped"] == 1  # `가.*` 가 「가」 든 문장을 환경 문장으로 만들지 않는다
    assert spy.calls[0] == ([r"가\.\*", r"a\\b", r"x\+", r"y\?", r"a\|b"], False)
    assert spy.calls[-1] == (None, False)  # judge 의 되돌림

    def unescaped(inputs: colab.GreenwashInputs) -> dict[str, Any]:
        return {**colab.SCAN_CONFIG, "env_keywords_extra": list(inputs.extra_terms)}

    monkeypatch.setattr(colab, "scan_config", unescaped)
    raw = scan(("가.*",), SENTENCE)
    assert raw["candidateStats"]["nonEnvDropped"] == 0  # escape 하지 않으면 `가.*` 가 「가」 든 문장(SENTENCE)에 맞는다


def test_symbols_are_counted_letter_for_letter() -> None:
    counted = totals(scan(SYMBOLS, SYMBOL_LINE))
    assert {term: counted.get(term) for term in SYMBOLS} == dict.fromkeys(SYMBOLS, 1)


def test_korean_terms_are_unchanged_by_escape() -> None:
    assert colab.scan_config(given([WORD, "탄소 감축"]))["env_keywords_extra"] == [WORD, "탄소\\ 감축"]


# ── (d) 되돌림 ──


def test_two_runs_in_a_row_the_second_is_e0() -> None:
    first_chat = ScriptedChat()
    first = s.result_of(
        s.run(given((WORD,), pages=s.SAMPLE_PAGES), s.adapters(llm=first_chat, pdf=s.SamplePdf(texts(SENTENCE))))
    )
    assert first["extraTerms"] == [WORD] and global_pattern() == default_pattern()
    chat = ScriptedChat()
    second = s.result_of(s.run(given((), pages=s.SAMPLE_PAGES), s.adapters(llm=chat)))
    assert global_pattern() == default_pattern()
    assert s.as_gw1(second) == s.gw1_view(s.golden("sample-mock.json"))
    assert s.message_hashes(chat.sent) == s.golden("sample-mock.json")["messages"]
    assert {k: v for k, v in second.items() if k != "extraTerms"} == {
        k: v for k, v in s.result_of(s.run(s.inputs(), s.adapters())).items() if k != "extraTerms"
    }


def test_the_global_is_restored_when_judge_is_interrupted() -> None:
    seen: list[str] = []

    class Watching(s.Recorder):
        def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
            seen.append(global_pattern())
            super().step_progress(flow_id, step, done, total, partial)

    with pytest.raises(s.Interrupted):
        s.run(given((WORD,), pages=s.SAMPLE_PAGES), s.adapters(), events=Watching(stop_after=1))
    assert seen and WORD in seen[0] and seen[0] != default_pattern()  # 판정 중에는 추가 단어가 들어 있었다
    assert global_pattern() == default_pattern()


def test_the_global_is_restored_when_the_dry_run_fails() -> None:
    seen: list[str] = []

    def failing(text: str) -> int:
        seen.append(global_pattern())
        raise RuntimeError("가상의 토큰 세기 실패")

    counter = TokenCounter({CHAT_ENCODING: failing, EMBEDDING_ENCODING: len})
    with pytest.raises(FlowStepFailed) as failed:
        s.run(given((WORD,), dry_run=True), s.adapters(pdf=s.SamplePdf(texts(SENTENCE)), tokens=counter))
    assert failed.value.step == "judge"
    assert seen and WORD in seen[0]  # 노트북 스캔(아래끝)이 전역을 바꾼 뒤에 끊겼다
    assert global_pattern() == default_pattern()


def test_a_resumed_judge_sets_the_same_words_again() -> None:
    def used() -> Any:
        return s.adapters(llm=ScriptedChat(detect_script(SENTENCE)), pdf=s.SamplePdf(texts(SENTENCE)))

    inputs = given((WORD,), pages=s.SAMPLE_PAGES)
    whole_run = s.run(inputs, used())
    adapters = used()
    recorder = s.Recorder(stop_after=1)
    with pytest.raises(s.Interrupted):
        s.run(inputs, adapters, events=recorder)
    assert global_pattern() == default_pattern()
    carried = {name: recorder.finished[name] for name in ("extract", "index")}
    resumed_run = s.run(inputs, adapters, start_at="judge", carried=carried, resume=recorder.saved)
    assert s.result_of(resumed_run) == s.result_of(whole_run)
    assert resumed_run.steps["judge"].data == whole_run.steps["judge"].data
    assert s.result_of(whole_run)["candidateStats"]["nonEnvDropped"] == 0  # 쪽 1 뒤의 쪽도 추가 단어로 걸렀다


def test_dry_run_rule_candidates_grow_with_the_extra_word() -> None:
    without, with_word = dry((), SENTENCE), dry((WORD,), SENTENCE)
    assert with_word["dryRun"]["ruleCandidates"] > without["dryRun"]["ruleCandidates"]
    assert with_word["extraTerms"] == [WORD] and without["extraTerms"] == []
    assert totals(with_word)[WORD] == 1


# ── (e) 상한 그대로 ──


def eval_calls_by_page(sent: Sequence[Sequence[Message]]) -> list[int]:
    """탐지 프롬프트 하나 뒤에 이어지는 평가(eval·low_only) 호출 수, 쪽마다."""
    pack = default_prompts(PROMPT_VERSION)
    out: list[int] = []
    for msgs in sent:
        kind = prompt_kind(msgs[0].content, pack)
        if kind == "detect":
            out.append(0)
        elif kind in ("eval", "low_only"):
            out[-1] += 1
    return out


def test_the_per_page_limit_holds_with_extra_words() -> None:
    many = [f"{WORD} {n}호 설비를 모든 사업장에 확대해 나가겠습니다." for n in range(6)]
    chat = ScriptedChat(detect_script(*many))
    s.run(given((WORD,), pages=s.SAMPLE_PAGES), s.adapters(llm=chat, pdf=s.SamplePdf(texts(*many))))
    per_page = eval_calls_by_page(chat.sent)
    assert len(per_page) == 4 and per_page[0] >= 3
    assert all(n <= 4 for n in per_page)  # max_candidates_per_page(3) + Low 하나


# ── (f) 입력 검사 ──


def test_terms_are_trimmed_and_deduplicated_by_the_key() -> None:
    accepted = given(["  Green ", "green", "탄소 중립", "탄소-중립", "탄소중립", "", " 초록 "]).extra_terms
    assert accepted == ("Green", "탄소 중립", "초록")
    assert given(["탄소중립", "탄소 중립"]).extra_terms == ("탄소중립",)


@pytest.mark.parametrize("term", ["(괄호", "끝)", "a{b", "[x]", '"따옴"', "'홑'", "“둥근”", "‘둥근’"])
def test_brackets_and_quotes_are_refused(term: str) -> None:
    with pytest.raises(ValueError, match="괄호나 따옴표"):
        given([term])
    assert normalize_text(term) != term.lower()  # 노트북이 본문에서 지우는 글자다


@pytest.mark.parametrize("term", [".", "-", "·", "-_", ".*", " - "])
def test_terms_without_a_letter_or_digit_are_refused(term: str) -> None:
    with pytest.raises(ValueError, match="글자나 숫자가 하나 이상"):
        given([WORD, term])


def test_terms_with_a_letter_among_symbols_pass() -> None:
    assert given(["a.b", "x+", "가.*", "a,b", "2030"]).extra_terms == ("a.b", "x+", "가.*", "a,b", "2030")  # 숫자만도


def test_the_length_and_count_limits() -> None:
    assert given(["가" * 30]).extra_terms == ("가" * 30,)
    with pytest.raises(ValueError, match="1~30자"):
        given(["가" * 31])
    thirty = [f"낱말{n}" for n in range(30)]
    assert len(given(thirty).extra_terms) == 30
    assert len(given([*thirty, "낱말0", "낱말 0"]).extra_terms) == 30  # 중복 제거 뒤에 센다
    with pytest.raises(ValueError, match="30개까지"):
        given([*thirty, "낱말30"])


@pytest.mark.parametrize("bad", ["초록마루", ["초록", 1], None])
def test_the_type_is_checked(bad: Any) -> None:
    with pytest.raises(ValueError, match="추가 단어는"):
        dataclasses.replace(s.inputs(), extra_terms=bad)


def test_error_messages_are_korean_sentences() -> None:
    messages: list[str] = []
    for bad in (["(x"], ["가" * 31], [f"w{n}" for n in range(31)]):
        with pytest.raises(ValueError) as raised:
            given(bad)
        messages.append(str(raised.value))
    assert all(m.startswith("추가 단어") and m.endswith("요") for m in messages)


def test_a_default_word_is_accepted_but_counted_once(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = Spy(monkeypatch)
    base = scan((), SENTENCE)
    for term in ("친환경", "Green", "탄소 중립"):
        result = scan((term,), SENTENCE)
        assert result["extraTerms"] == [term]
        assert result["wordCounts"] == base["wordCounts"]  # 두 번 세지 않는다
    assert [c[0] for c in spy.calls if c[0] is not None] == [
        ["친환경"],
        ["Green"],
        ["탄소\\ 중립"],
    ]  # env 에는 들어간다
    assert frequency_extras(["친환경", "Green", "탄소 중립", "eco", WORD]) == ["eco", WORD]
    assert term_key("탄소 중립") == term_key("탄소-중립") == term_key("탄소중립") == "탄소중립"
    assert "탄소중립" in GREEN_TERMS


def test_eco_is_not_the_default_eco_free_and_is_counted() -> None:
    line = "eco 라인을 넓힙니다"
    assert "eco" not in totals(scan((), line))
    assert totals(scan(("eco",), line))["eco"] == 1


# ── (g) 꼴 ──


def test_results_with_extra_words_fit_the_shape_and_the_workbook() -> None:
    extra = (WORD, "친환경", "없는낱말")
    run = s.run(given(extra, pages=s.SAMPLE_PAGES), s.adapters(pdf=s.SamplePdf(texts(SENTENCE))))
    result = s.result_of(run)
    shapes.RESULT_SHAPES[shapes.SHAPE].validate_python(result, strict=True)
    assert list(result)[list(result).index("pages") + 1] == "extraTerms"
    shapes.RESULT_SHAPES[shapes.SHAPE].validate_python(dry(extra, SENTENCE), strict=True)

    (book,) = run.output.files
    sheets = load_workbook(io.BytesIO(book.content), read_only=True)
    words = [tuple(row) for row in sheets["단어 빈도"].iter_rows(values_only=True)]
    settings: dict[Any, Any] = {row[0]: row[1] for row in sheets["설정"].iter_rows(min_row=2, values_only=True)}
    assert words[0] == ("낱말", "수", "추가")
    assert words[1:] == [
        (row["term"], row["count"], "추가" if row["term"] == WORD else None) for row in result["wordCounts"]["total"]
    ]
    assert ("친환경", totals(result)["친환경"], None) in words  # 기본 목록과 겹친 단어는 기본 낱말 줄 그대로
    assert settings["추가 단어"] == "\n".join(extra)  # 쉼표가 든 단어와 구별되게 줄바꿈으로
