"""engines/colab_156/prompts.py 의 템플릿 글 여섯(`PromptTexts`·`DEFAULT_TEXTS`)과 `render`(밴드 DVA1 §3-1).

1. 기본 글로 지은 글이 BASE(0a41a1c7)의 f-문자열 글과 바이트 같다 — 아래 지문은 BASE 엔진으로 잰 값이다(같은 입력을
   BASE 함수에 넣어 sha256(system + "\\0" + user)). 걸음 3·산식 0 개는 「− 4」 자리가 음수다.
2. 자리 표(PLACEHOLDERS·REQUIRED)가 기본 글에서 센 자리와 같다.
3. 끼우기는 한 번이다: 값 안의 자리 글자는 그대로 남는다.
4. 칸 양성: 칸마다 표지를 넣으면 그 단계의 system 또는 user 에만 나온다.
5. 지시 글의 걸음 자리를 지워도 렌더된다(처분 Q3). 6. ASCII `-` 변형은 U+2212 자리와 같은 값을 받는다(처분 Q2).
"""

import dataclasses
import hashlib
import re
from typing import Any

import pytest

from esgapi.dataverify.engines.colab_156 import prompts
from esgapi.dataverify.tests.engines.colab_156.support import environment

PLAIN: dict[str, Any] = {
    "company_name": "가상건설",
    "sasb_industry": "Engineering & Construction Services",
    "material_topics": ["기후변화 대응", "안전보건", "가상 토픽 {괄호}"],
    "reporting_year": "2025",
}
TRICKY: dict[str, Any] = {
    "company_name": "{입력 데이터 JSON}",
    "sasb_industry": "가상 {SASB 산업분류} 산업",
    "material_topics": ["{최대 걸음}", "{최대 걸음 - 4}"],
    "reporting_year": "{보고연도}",
}
COMPANIES = {"plain": PLAIN, "tricky": TRICKY}


def data(name: str) -> dict[str, Any]:
    if name == "plain":
        return {"환경": environment()}
    return {"환경": [{"소분류": "{기업명}", "메모": "{계산 계획의 산식 목록}", "values": {"2024": "{최대 걸음 − 2}"}}]}


def hints(name: str, count: int) -> list[str]:
    if name == "plain":
        return [f"가상 산식 {i} = A{i} + B{i} {{x}}" for i in range(count)]
    return [f"{{입력 데이터 JSON}} {i}" for i in range(count)]


def digest(pair: tuple[str, str]) -> str:
    return hashlib.sha256("\x00".join(pair).encode()).hexdigest()


# BASE 0a41a1c7 의 plan_prompt·insight_prompt(max_steps)·review_prompt(hints) 지문.
BASE_SHA256 = {
    "plan/plain/12": "50a71b160a6fb1620ffc08a3f8a02a5b68322ef360267f871f22d74a3e9f9eb0",
    "insight/plain/12": "e810a327aa4903bdc1159a249e0db056bb8ca38cfe4e3fd1cbe6c6e3ce9be91d",
    "plan/plain/20": "27b2f5d5121282d7018c5294252768319a7af72ab8674768240c01e4e4003bd5",
    "insight/plain/20": "5cd6e691034b96c0a5a225e2eae8e36253ba8c62a48614d7d8e573a9f40e7860",
    "plan/plain/3": "57a5282925c0abeda4256d80d1148b0000fcaaf11ea950ee70b37af10dcff851",
    "insight/plain/3": "4522d43996aacbd783092ff26c2bbc3a9930c02a905153c26a9cb5c2c22e9c03",
    "review/plain/0": "c40b2061aac484afae5947100954707677c531042eeac8301b842eec3e559cc7",
    "review/plain/1": "eb76627c9a8d4ff8d99aa777e699115c06d568d178827e231fded80ebc1f4f7f",
    "review/plain/5": "857b06e6195deb6e615e170dcf29b33d40b74ba76d66acbfc154066ea8808440",
    "review/plain/13": "639e538716bca00ddac5d8518544511e52a13042148aabd3218eff192d96eb8b",
    "plan/tricky/12": "36581dac5b00dba6577ea42d30501371ddf6898133b47bfd9d83e9a529947a69",
    "insight/tricky/12": "ac130febccbd8aac8e11382f0039eea070d228a5e631bbb06d0eb948f145301f",
    "plan/tricky/20": "cf8309215f74dad6798b63c7bdc006af0f7ac69e1c856815c75211d381185c67",
    "insight/tricky/20": "c0a338ddeaef1885759cca98adb3842012946a81c8a25b61036175413b2ea125",
    "plan/tricky/3": "29800817c3b06e54bc1f52430fe4afab5d6b14a37673fcb40b010b5d92683943",
    "insight/tricky/3": "c8e22be01623eaf95411ae47a41b766a3b2dcd8d43b805affb361aa5a1ed7547",
    "review/tricky/0": "1f90663617aa3079b73f5de245d0ce22b8461a76edd30755ab0d9e5c990fd826",
    "review/tricky/1": "cea28a901b6a76ebbf32668de3eee128c391fb2347d98988b8060d299ebe5eb8",
    "review/tricky/5": "f612c943d88fb2ebf6c3852c394bf482d8aaaf2d21f10a5d40443742a8f53a3e",
    "review/tricky/13": "157199535dca807a4b9d3bdf8a4c294e4b7848a16727cfa9a03b186ce60f1c2e",
}


def built(case: str, texts: prompts.PromptTexts = prompts.DEFAULT_TEXTS) -> tuple[str, str]:
    stage, name, number = case.split("/")
    n = int(number)
    if stage == "plan":
        return prompts.plan_prompt(**COMPANIES[name], data_split=data(name), max_steps=n, texts=texts)
    if stage == "insight":
        return prompts.insight_prompt(**COMPANIES[name], data_split=data(name), max_steps=n, texts=texts)
    return prompts.review_prompt(hints=hints(name, n), data_split=data(name), texts=texts)


@pytest.mark.parametrize("case", sorted(BASE_SHA256))
def test_the_default_texts_render_the_base_bytes(case: str) -> None:
    assert digest(built(case)) == BASE_SHA256[case]
    assert built(case) == built(case, dataclasses.replace(prompts.DEFAULT_TEXTS))  # 기본 인자 = DEFAULT_TEXTS


SLOT_RE = re.compile(
    r"\{(?:최대 걸음[^{}]*|기업명|SASB 산업분류|중대토픽|보고연도|입력 데이터 JSON|계산 계획의 산식 목록)\}"
)
STAGE_FIELDS = {stage: (f"{stage}_system", f"{stage}_user") for stage in ("plan", "review", "insight")}


@pytest.mark.parametrize("stage", ["plan", "review", "insight"])
def test_the_slot_table_is_what_the_default_texts_hold(stage: str) -> None:
    system, user = (getattr(prompts.DEFAULT_TEXTS, field) for field in STAGE_FIELDS[stage])
    assert set(SLOT_RE.findall(system + user)) == set(prompts.PLACEHOLDERS[stage])
    assert set(SLOT_RE.findall(user)) == set(prompts.REQUIRED[f"{stage}_user"])
    # 걸음 자리는 지시 글에만, 입력 글 자리는 입력 글에만
    assert set(SLOT_RE.findall(system)) == {prompts.STEPS, prompts.STEPS_MINUS_4, prompts.STEPS_MINUS_2}
    # 자리 밖에 「{최대」·「{기업」 같은 반쪽 글자가 없다
    rest = SLOT_RE.sub("", system + user)
    assert "{최대" not in rest and "{기업" not in rest
    # 렌더한 글에 자리 글자가 남지 않는다(값이 자리 글자가 아닐 때)
    rendered = built(f"{stage}/plain/{12 if stage != 'review' else 5}")
    assert SLOT_RE.findall("".join(rendered)) == []


def test_the_default_texts_are_the_order_lengths() -> None:
    lengths = {
        field.name: len(getattr(prompts.DEFAULT_TEXTS, field.name)) for field in dataclasses.fields(prompts.PromptTexts)
    }
    assert (lengths["plan_system"], lengths["review_system"], lengths["insight_system"]) == (1734, 3636, 4438)
    assert all(0 < length <= 8000 for length in lengths.values())
    assert [field.name for field in dataclasses.fields(prompts.PromptTexts)] == [
        "plan_system",
        "plan_user",
        "review_system",
        "review_user",
        "insight_system",
        "insight_user",
    ]


def test_slot_values_are_inserted_once() -> None:
    system, user = built("plan/tricky/12")
    assert "    [기업명]: {입력 데이터 JSON}\n" in user  # 기업명 값의 자리 글자를 다시 끼우지 않는다
    assert "[주요 중대토픽(Material Topics)]: {최대 걸음}, {최대 걸음 - 4}\n" in user
    assert "[Reporting year]: {보고연도}\n" in user
    assert '"소분류":"{기업명}"' in user
    assert "최대 12 스텝" in system
    _, user = built("review/tricky/1")
    assert "    - {입력 데이터 JSON} 0</힌트>" in user
    assert '"메모":"{계산 계획의 산식 목록}"' in user


def test_render_leaves_unknown_braces_and_takes_one_pass() -> None:
    values = {prompts.COMPANY_NAME: "{기업명}{기업명}", prompts.DATA_JSON: "x"}
    assert (
        prompts.render("{기업명}·{모름}·{입력 데이터 JSON}·{{기업명}}", values)
        == "{기업명}{기업명}·{모름}·x·{{기업명}{기업명}}"
    )
    assert prompts.render("글 {기업명}", {}) == "글 {기업명}"


@pytest.mark.parametrize("field", [field.name for field in dataclasses.fields(prompts.PromptTexts)])
def test_each_field_reaches_only_its_own_stage(field: str) -> None:
    marker = f"⟦DVA1-{field}⟧"
    texts = dataclasses.replace(prompts.DEFAULT_TEXTS, **{field: marker + getattr(prompts.DEFAULT_TEXTS, field)})
    stage, part = field.split("_")
    for other in ("plan", "review", "insight"):
        system, user = built(f"{other}/plain/{5 if other == 'review' else 12}", texts)
        assert (marker in system) == (other == stage and part == "system")
        assert (marker in user) == (other == stage and part == "user")


@pytest.mark.parametrize("stage", ["plan", "review", "insight"])
def test_a_system_text_without_step_slots_still_renders(stage: str) -> None:
    field = f"{stage}_system"
    text = getattr(prompts.DEFAULT_TEXTS, field)
    for slot in (prompts.STEPS, prompts.STEPS_MINUS_4, prompts.STEPS_MINUS_2):
        text = text.replace(slot, "")
    texts = dataclasses.replace(prompts.DEFAULT_TEXTS, **{field: text})
    system, _ = built(f"{stage}/plain/{5 if stage == 'review' else 12}", texts)
    assert system == text


@pytest.mark.parametrize(("stage", "steps"), [("plan", 12), ("review", 15), ("insight", 20)])
def test_the_ascii_minus_spelling_takes_the_same_value(stage: str, steps: int) -> None:
    template = "걸음 {최대 걸음} · {최대 걸음 - 4}={최대 걸음 − 4} · {최대 걸음 - 2}={최대 걸음 − 2} · {기업명}"
    texts = dataclasses.replace(prompts.DEFAULT_TEXTS, **{f"{stage}_system": template})
    case = f"{stage}/plain/{steps // 3 if stage == 'review' else steps}"
    system, _ = built(case, texts)
    company = "가상건설" if stage != "review" else "{기업명}"  # 검토 단계 자리 표에 기업명이 없다 — 글자 그대로
    assert system == f"걸음 {steps} · {steps - 4}={steps - 4} · {steps - 2}={steps - 2} · {company}"


def test_review_steps_per_formula_is_the_colab_three() -> None:
    assert prompts.REVIEW_STEPS_PER_FORMULA == 3
    assert prompts.review_max_steps(["a"] * 5) == 15
    assert prompts.missing_slots(
        "{최대 걸음 - 4} {기업명}", (prompts.STEPS_MINUS_4, prompts.COMPANY_NAME, prompts.DATA_JSON)
    ) == [prompts.DATA_JSON]
