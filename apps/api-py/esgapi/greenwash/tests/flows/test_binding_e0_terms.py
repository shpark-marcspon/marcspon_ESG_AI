"""판의 대상 단어로 세는 실행 — 끼움의 versions_with·inputs_with 와 흐름의 wordcount·결과·엑셀(밴드 G2d ③ §3-3, 순수 층
— 가짜 판 포트 tests/flows/settings_store.py, 바닥 기준물 tests/data/g2d-baseline). 업무 끝까지(3-3-6)는
test_binding_e0_terms_runs.py.

    3-3-1  기본 판·칸 NULL 판의 실행 = g2d-baseline(결과 JSON·versions·메시지 해시 바이트, 엑셀 셀) — 다섯 갈래
    3-3-2  판 켠 목록 = GREEN_TERMS(차례 같음) → 결과·메시지·엑셀 셀 == 기준물 ⓒ, terms 칸 없음,
           versions = ⓒ + termsSha256
    3-3-3  판에 더한 단어(환경 신호 없는 문장에만 있음) → 빈도에 셈 · 판정 대상 아님(candidateStats·메시지 그대로) ·
           judge 가 환경 낱말 전역을 건드리지 않음 · 결과 terms · 엑셀 「대상 단어」
    3-3-4  기본 단어 하나 끔·하나 지움 → 그 낱말 빈도 줄 없음 · candidateStats·메시지 그대로
    3-3-5  칸만·열쇠만·기본 판에 열쇠·받기 좁힘·sha 한 글자 → mismatch(저장 글 없는 판·모델 열쇠 없는 옛 실행 갈래 다)
    3-3-7  판 + extraTerms → 빈도 목록 차례 = 판 켠 단어 → 판 키에 없는 extra · extra 는 환경 낱말에도 ·
           엑셀 「추가」 는 GREEN_TERMS 기준 · 끝에 되돌린 전역은 re 캐시와 무관하게 기본과 같음(582)

단어는 지어낸 것이다(「미래 가치」 는 표본 1쪽의 환경 신호 없는 문장에만 있다). 실제 AI 호출 0.
"""

import copy
import json
import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Any, cast

import pytest

from esgapi.core.flows.binding import DocumentInput, RunVersionsRejected
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.greenwash.contracts import shapes
from esgapi.greenwash.contracts.terms_shapes import GreenwashTerm
from esgapi.greenwash.engines.e0 import heuristics
from esgapi.greenwash.engines.e0.gw1 import GREEN_TERMS, frequency_extras
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import terms_e0
from esgapi.greenwash.flows.binding_e0 import AiSettingMismatch, GreenwashBinding, SavedSetting
from esgapi.greenwash.flows.terms_e0 import extras_beyond, terms_sha256
from esgapi.greenwash.tests.flows import g2d_baseline as baseline
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows import test_criteria_flow as flow_cases
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore, FakeStore

COMPANY = cast("int", baseline.fixtures()["companyId"])
OPTIONS = cast("dict[str, object]", baseline.fixtures()["options"])
ADDED = "미래 가치"
"""판에 더하는 지어낸 낱말 — 표본 1쪽 「혁신과 도전으로 미래 가치를 창출하겠습니다.」(환경 신호 없음)에만 있다."""


def board(*extra: str, off: Sequence[str] = (), drop: Sequence[str] = ()) -> list[GreenwashTerm]:
    """GREEN_TERMS 차례 그대로에서 drop 을 빼고 off 를 끄고 extra 를 끝에 켜서 더한 판 단어."""
    kept: list[GreenwashTerm] = [{"text": t, "enabled": t not in off} for t in GREEN_TERMS if t not in drop]
    return [*kept, *({"text": t, "enabled": True} for t in extra)]


def saved(terms: Sequence[GreenwashTerm] | None, *, prompts: bool = False) -> SavedSetting:
    return replace(baseline.saved_setting(prompts=prompts), terms=terms)


def binding_with(setting: SavedSetting) -> GreenwashBinding:
    return GreenwashBinding(
        models=s.REAL_MODELS, store=FakeStore(saved={COMPANY: [setting]}, applied_id={COMPANY: setting.id})
    )


def run_board(
    setting: SavedSetting, options: dict[str, object] = OPTIONS, *, drop_keys: Sequence[str] = ()
) -> dict[str, Any]:
    """g2d_baseline.build 와 같은 길(versions_with → inputs_with → run_flow, 모의 공급사)을 판 하나로."""
    binding = binding_with(setting)
    versions = binding.versions_with(options, company_id=COMPANY)
    versions = {k: v for k, v in versions.items() if k not in drop_keys}
    inputs = binding.inputs_with(baseline.DOCUMENT, options, company_id=COMPANY, versions=versions)
    mock = flow_cases.scripted_provider(baseline.PROVIDER_QUEUE, baseline.pack_of(inputs))
    run = s.run(inputs, s.adapters(llm=flow_cases.bridge(mock, MemorySink())))
    (book,) = run.output.files
    return {
        "versions": versions,
        "inputs": inputs,
        "result": s.result_of(run),
        "messages": flow_cases.provider_hashes(mock.calls),
        "workbook": baseline.cells(book.content),
    }


def _json(branch: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(baseline.stored(branch)))


def env_pattern() -> object:
    """엔진의 환경 낱말 전역(heuristics._ENV_KEYWORDS_RE — 노트북이 바꾸는 모듈 전역, 흠 18) 객체."""
    return cast("object", getattr(heuristics, "_ENV_KEYWORDS_RE"))  # noqa: B009 — 밑줄 이름을 그대로 읽는다


def same_pattern(left: object, right: object) -> bool:
    """두 환경 낱말 전역의 패턴 글자·flags 가 같은가 — 객체가 같은지는 re 캐시에 달려 있어 묻지 않는다(582)."""
    one, other = cast("re.Pattern[str]", left), cast("re.Pattern[str]", right)
    return (one.pattern, one.flags) == (other.pattern, other.flags)


def watch_judge(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """judge 안(_judge 가 끝난 직후, 되돌리기 전)의 환경 낱말 전역 객체를 적는다."""
    seen: list[object] = []
    real = colab._judge  # pyright: ignore[reportPrivateUsage]

    def wrapped(*args: Any) -> Any:
        try:
            return real(*args)
        finally:
            seen.append(env_pattern())

    monkeypatch.setattr(colab, "_judge", wrapped)
    return seen


def counted(result: dict[str, Any]) -> dict[str, int]:
    return {row["term"]: row["count"] for row in result["wordCounts"]["total"]}


def setting_rows(workbook: dict[str, Any]) -> dict[str, Any]:
    return {row[0]: row[1] for row in workbook["설정"]}


# ── 3-3-1 재현(사용자 조건) ──


@pytest.mark.parametrize("branch", baseline.BRANCHES)
def test_runs_without_board_terms_are_the_baseline_to_the_byte(branch: str) -> None:
    assert baseline.dump(baseline.build(branch)) == baseline.stored(branch)


def test_the_baseline_has_no_terms_anywhere() -> None:
    """분모: 기준물에는 terms 칸·termsSha256·「대상 단어」 줄이 없다(그래서 위 대조가 그 셋을 문다)."""
    for branch in baseline.BRANCHES:
        found = _json(branch)
        assert "terms" not in found["result"] and "termsSha256" not in found["versions"]
        if found["workbook"] is not None:
            assert "대상 단어" not in setting_rows(found["workbook"])


# ── 3-3-2 접기(★G) ──


def test_a_board_equal_to_green_terms_folds_to_the_code_list() -> None:
    made = run_board(saved(board(), prompts=True))
    base = _json("c-saved-text")
    assert made["inputs"].terms is None
    assert "terms" not in made["result"]
    assert baseline.dump({**base, "result": made["result"]}) == baseline.stored("c-saved-text")
    assert made["messages"] == base["messages"]
    assert made["workbook"] == base["workbook"]
    assert made["versions"] == {**base["versions"], "termsSha256": terms_sha256(GREEN_TERMS)}


def test_a_board_with_the_same_words_in_another_order_does_not_fold() -> None:
    """분모: 차례가 다르면 접지 않는다(결과에 terms — 판 차례)."""
    turned = list(reversed(board()))
    made = run_board(saved(turned))
    assert made["inputs"].terms == tuple(reversed(GREEN_TERMS))
    assert made["result"]["terms"] == list(reversed(GREEN_TERMS))
    assert counted(made["result"]) == counted(_json("b-saved-code-text")["result"])


# ── 3-3-3 판 단어는 빈도에만(394) ──


def test_an_added_word_is_counted_but_not_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    pattern = env_pattern()
    during = watch_judge(monkeypatch)
    made = run_board(saved(board(ADDED)))
    base = _json("b-saved-code-text")
    assert counted(made["result"]) == {**counted(base["result"]), ADDED: 1}
    assert made["result"]["candidateStats"] == base["result"]["candidateStats"]
    assert made["result"]["items"] == base["result"]["items"]
    assert made["messages"] == base["messages"]
    assert len(during) == 1 and during[0] is pattern  # judge 동안 바닥 객체 그대로
    assert env_pattern() is pattern
    assert made["result"]["terms"] == [*GREEN_TERMS, ADDED]
    assert list(made["result"]) == [*list(base["result"])[:8], "terms", *list(base["result"])[8:]]  # extraTerms 뒤
    assert setting_rows(made["workbook"])["대상 단어"] == "\n".join([*GREEN_TERMS, ADDED])
    assert {row[2] for row in made["workbook"]["단어 빈도"][1:]} <= {
        None,
        "",
    }  # 「추가」 는 GREEN_TERMS 기준 — 판 단어에 안 붙음(W4)
    assert made["versions"] == {**base["versions"], "termsSha256": terms_sha256([*GREEN_TERMS, ADDED])}
    shapes.RESULT_SHAPES[shapes.SHAPE].validate_python(made["result"])


def test_the_added_word_is_in_a_sentence_without_an_environment_signal() -> None:
    """분모: 「미래 가치」 가 든 문장은 환경 신호가 없다(그래서 위 시험의 「판정 대상 아님」 이 헛돌지 않는다)."""
    (sentence,) = [line for line in s.page_texts()[0].splitlines() if ADDED in line]
    assert not heuristics.has_env_signal(sentence)
    assert ADDED not in counted(_json("b-saved-code-text")["result"])


# ── 3-3-4 끔·지움 ──


def test_a_word_turned_off_or_dropped_is_not_counted() -> None:
    made = run_board(saved(board(off=["친환경"], drop=["저탄소"])))
    base = _json("b-saved-code-text")
    left = {k: v for k, v in counted(base["result"]).items() if k not in ("친환경", "저탄소")}
    assert counted(made["result"]) == left
    assert "친환경" in counted(base["result"]) and "저탄소" in counted(base["result"])  # 분모
    assert made["result"]["candidateStats"] == base["result"]["candidateStats"]
    assert made["messages"] == base["messages"]
    assert "친환경" not in made["result"]["terms"] and "저탄소" not in made["result"]["terms"]


# ── 3-3-5 만들 때와 돌 때의 대조 ──


def versions_and_binding(setting: SavedSetting) -> tuple[dict[str, object], GreenwashBinding]:
    binding = binding_with(setting)
    return binding.versions_with(OPTIONS, company_id=COMPANY), binding


@pytest.mark.parametrize("prompts", [False, True], ids=["code-text", "saved-text"])
def test_versions_carry_the_terms_sha_on_both_branches(prompts: bool) -> None:
    with_terms, _ = versions_and_binding(saved(board(ADDED), prompts=prompts))
    without, _ = versions_and_binding(saved(None, prompts=prompts))
    assert with_terms == {**without, "termsSha256": terms_sha256([*GREEN_TERMS, ADDED])}
    assert "termsSha256" not in without


def test_a_default_board_carries_no_terms_sha() -> None:
    made = GreenwashBinding(models=s.REAL_MODELS, store=DefaultOnlyStore()).versions_with(OPTIONS, company_id=COMPANY)
    assert made == _json("a-default")["versions"]


def mismatch(binding: GreenwashBinding, versions: dict[str, object]) -> None:
    with pytest.raises(AiSettingMismatch):
        binding.inputs_with(baseline.DOCUMENT, OPTIONS, company_id=COMPANY, versions=versions)


OLD = cast("list[str]", baseline.fixtures()["dropKeys"])


@pytest.mark.parametrize("old_run", [False, True], ids=["model-key", "old-run-no-model-key"])
@pytest.mark.parametrize("prompts", [False, True], ids=["code-text", "saved-text"])
def test_field_and_key_must_go_together(old_run: bool, prompts: bool) -> None:
    drop = OLD if old_run else []
    with_terms = saved(board(ADDED), prompts=prompts)
    versions, binding = versions_and_binding(with_terms)
    versions = {k: v for k, v in versions.items() if k not in drop}
    taken = binding.inputs_with(baseline.DOCUMENT, OPTIONS, company_id=COMPANY, versions=versions)
    assert taken.terms == (*GREEN_TERMS, ADDED)  # 분모: 맞으면 받는다
    mismatch(binding, {k: v for k, v in versions.items() if k != "termsSha256"})  # 칸만
    plain = saved(None, prompts=prompts)
    plain_versions, plain_binding = versions_and_binding(plain)
    plain_versions = {k: v for k, v in plain_versions.items() if k not in drop}
    assert (
        plain_binding.inputs_with(baseline.DOCUMENT, OPTIONS, company_id=COMPANY, versions=plain_versions).terms is None
    )
    mismatch(plain_binding, {**plain_versions, "termsSha256": versions["termsSha256"]})  # 열쇠만


def test_a_default_run_with_a_terms_key_is_a_mismatch() -> None:
    binding = GreenwashBinding(models=s.REAL_MODELS, store=DefaultOnlyStore())
    versions = binding.versions_with(OPTIONS, company_id=COMPANY)
    binding.inputs_with(baseline.DOCUMENT, OPTIONS, company_id=COMPANY, versions=versions)  # 분모
    mismatch(binding, {**versions, "termsSha256": terms_sha256(GREEN_TERMS)})


@pytest.mark.parametrize("old_run", [False, True], ids=["model-key", "old-run-no-model-key"])
def test_one_changed_letter_of_the_sha_is_a_mismatch(old_run: bool) -> None:
    versions, binding = versions_and_binding(saved(board(ADDED)))
    versions = {k: v for k, v in versions.items() if not (old_run and k in OLD)}
    sha = cast("str", versions["termsSha256"])
    flipped = ("0" if sha[0] != "0" else "1") + sha[1:]
    mismatch(binding, {**versions, "termsSha256": flipped})


def test_a_board_the_rules_no_longer_take_is_refused_and_mismatched(monkeypatch: pytest.MonkeyPatch) -> None:
    setting = saved(board(ADDED))
    versions, binding = versions_and_binding(setting)
    monkeypatch.setattr(terms_e0, "TERMS_MAX", 2)
    with pytest.raises(RunVersionsRejected):
        binding.versions_with(OPTIONS, company_id=COMPANY)
    mismatch(binding, versions)


def test_the_terms_check_is_not_skipped_by_the_old_run_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """옛 실행 갈래(모델 열쇠 없음)도 받기 좁힘·sha 대조를 지난다(:345 replace 앞)."""
    versions, binding = versions_and_binding(saved(board(ADDED)))
    old = {k: v for k, v in versions.items() if k not in OLD}
    monkeypatch.setattr(terms_e0, "TERMS_MAX", 2)
    mismatch(binding, old)


# ── 3-3-7 판 + extraTerms ──


def test_board_and_extra_terms_together(monkeypatch: pytest.MonkeyPatch) -> None:
    pattern = env_pattern()
    during = watch_judge(monkeypatch)
    extra = ["고객과 임직원", "탄소 중립", "친환경", ADDED]
    options = {**OPTIONS, "extraTerms": extra}
    made = run_board(saved(board(ADDED, off=["친환경"])), options)
    used = [t for t in [*GREEN_TERMS, ADDED] if t != "친환경"]
    assert made["result"]["terms"] == [
        *used,
        "고객과 임직원",
        "친환경",
    ]  # 「탄소 중립」=「탄소중립」·판 단어와 같은 extra 는 두 번 안 셈
    assert made["result"]["terms"] == [*used, *extras_beyond(used, extra)]
    assert made["result"]["extraTerms"] == extra
    assert counted(made["result"])["친환경"] == 2  # 판에서 끈 기본 단어를 extra 로 → 빈도에 든다
    assert counted(made["result"])["고객과 임직원"] == 1
    assert len(during) == 1 and not same_pattern(during[0], pattern)  # extra 는 환경 낱말에도(G1c 그대로)
    assert same_pattern(env_pattern(), pattern)  # 끝에 되돌림 — 새로 컴파일하므로 객체는 re 캐시 따라 다르다(582)
    marked = {row[0] for row in made["workbook"]["단어 빈도"][1:] if row[2] == "추가"}
    assert marked == set(frequency_extras(extra)) & set(counted(made["result"]))  # GREEN_TERMS 기준(W4)
    assert "친환경" not in marked and "고객과 임직원" in marked


def test_the_default_comes_back_with_the_re_cache_emptied(monkeypatch: pytest.MonkeyPatch) -> None:
    """되돌리기 직전에 re 캐시를 비워도 끝의 전역은 기본과 같다 — 다른 시험의 컴파일이 캐시를 민 때와 같은 자리(582).
    기준은 시작 때 전역이 아니라 새로 지은 기본이다 — 앞 시험이 전역을 더럽혀도 눈감지 않는다."""
    pattern = cast("object", heuristics.build_env_keywords_re())  # pyright: ignore[reportUnknownMemberType]
    real = colab.set_env_keywords

    def purged(extra: Sequence[str] | None, general: bool) -> None:
        re.purge()
        real(extra, general)

    monkeypatch.setattr(colab, "set_env_keywords", purged)
    during = watch_judge(monkeypatch)
    run_board(saved(board(ADDED)), {**OPTIONS, "extraTerms": ["고객과 임직원"]})
    assert len(during) == 1 and not same_pattern(during[0], pattern)
    assert env_pattern() is not pattern  # 캐시가 정말 비어 새 객체다 — 이 시험이 헛돌지 않는다
    assert same_pattern(env_pattern(), pattern)


@pytest.mark.parametrize(
    "terms", [None, (*GREEN_TERMS, ADDED), ("친환경", "미래 가치"), ()], ids=["none", "board", "short", "empty"]
)
def test_frequency_terms_matches_extras_beyond(terms: tuple[str, ...] | None) -> None:
    """colab_e0.frequency_terms 의 판 쪽 셈 = terms_e0.extras_beyond(colab_e0 는 terms_e0 를 들이지 않는다)."""
    extra = ("고객과 임직원", "탄소 중립", "친환경", "eco")
    given = replace(s.inputs(), extra_terms=extra, terms=terms)
    base = GREEN_TERMS if terms is None else terms
    assert colab.frequency_terms(given) == [*base, *extras_beyond(base, extra)]


def test_a_dry_run_on_a_board_carries_terms() -> None:
    binding = binding_with(saved(board(ADDED)))
    versions = binding.versions_with(OPTIONS, company_id=COMPANY)
    inputs = binding.inputs_with(baseline.DOCUMENT, OPTIONS, company_id=COMPANY, versions=versions)
    forbidden = s.Forbidden()
    run = s.run(replace(inputs, dry_run=True), s.adapters(llm=forbidden, embedding=forbidden, tokens=s.char_counter()))
    result = s.result_of(run)
    assert result["terms"] == [*GREEN_TERMS, ADDED] and counted(result)[ADDED] == 1
    shapes.RESULT_SHAPES[shapes.SHAPE].validate_python(result)
    assert forbidden.calls == 0


def test_the_default_document_input_is_the_baseline_one() -> None:
    """분모: 이 파일의 문서·옵션은 기준물의 것과 같다."""
    assert (
        DocumentInput(content=s.SAMPLE_BYTES, media_type="application/pdf", file_name=s.SAMPLE_NAME)
        == baseline.DOCUMENT
    )
    assert copy.deepcopy(OPTIONS) == baseline.fixtures()["options"]
