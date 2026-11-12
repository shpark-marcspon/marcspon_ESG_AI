"""engines/colab_156/prompts.py 의 글 셋(코랩 셀 10·14·18 의 SYSTEM·USER — 변수화·예시 수 바꿈 뒤)이 고정한 지문과 같고,
core.llm 봉투(prompts/<이름>/1.md)로 렌더해도 한 바이트도 바뀌지 않는가(발주서 DV1a §3 S9·★b, DV1c 감독 결정 ⑥).

글자 하나가 바뀌어도 「렌더 결과 sha256」이 빨개진다. 코랩 글과의 바이트 견줌은 esg-lab `py/dvcolab`(MARC-ENT-310).
core.llm 은 prompts(parse_template·render_prompt·PackagePromptStore — 순수, 호출 0)만 쓴다(발주서 §1-1 의 예외).
"""

import hashlib
import json
from typing import Any

import pytest

from esgapi.core.llm.prompts import PackagePromptStore, parse_prompt_id, render_prompt
from esgapi.dataverify.engines.colab_156 import prompts
from esgapi.dataverify.tests.engines.colab_156.support import environment

COMPANY: dict[str, Any] = {
    "company_name": "가상건설",
    "sasb_industry": "Engineering & Construction Services",
    "material_topics": ["기후변화 대응", "안전보건", "가상 토픽 {괄호}"],
    "reporting_year": "2025",
}
HINTS = [
    "총 배출량(Scope 1+2) = 직접 배출량(Scope 1) + 간접 배출량(Scope 2)",
    "재생에너지 비율 = 재생에너지 / 총 에너지 {x}",
]


def data_split() -> dict[str, Any]:
    return {"환경": environment()}


def ours(kind: str) -> tuple[str, str]:
    if kind == "plan":
        return prompts.plan_prompt(**COMPANY, data_split=data_split())
    if kind == "review":
        return prompts.review_prompt(hints=HINTS, data_split=data_split())
    return prompts.insight_prompt(**COMPANY, data_split=data_split())


def rendered(kind: str, system: str, user: str) -> tuple[str, str]:
    template = PackagePromptStore().get(parse_prompt_id(prompts.PROMPT_IDS[kind]))
    out = render_prompt(template, {"system": system, "user": user})
    assert len(out.system) == 1
    assert not out.system[0].cache
    return out.system[0].text, out.user


# 렌더 결과 sha256(system, user) — 위 COMPANY·HINTS·data_split 로 렌더한 글의 지문.
# BASE ccd3194 엔진 렌더에서 잰 값이다. DV1a 가 그 글이 코랩 사본과 바이트 같음을 보였다
# (손셈 원칙의 예외 — 발주서 §7-5).
# 읽기판 블록 sha256(prompts/README.md)과는 다른 값이다.
RENDERED_SHA256 = {
    "plan": (
        "9b5ac7cae1e4ed81fa77542599ff9536c9713231bb5c9a4982a75e7a14c8ca9f",
        "d3856884b39547f08937bb0580a1592e0062aa0d68d361878927004c722b7be3",
    ),
    "review": (
        "a32137fe1f1277e021eb7b08c729dc02894af41af2a64ed78793167651227503",
        "829a75c8543ef6266a574b938a81febd18463d45b614824977788cfef8bfbbd8",
    ),
    "insight": (
        "33815a99993f73cb9c8f0385ca09a69c9319779baddebeb93d99ed60551be6a4",
        "d9d02e7253663a2264c18a89f711a63160a53813b1f3b2601c1a4d8aef6c045c",
    ),
}


@pytest.mark.parametrize("kind", ["plan", "review", "insight"])
def test_the_rendered_prompt_keeps_its_sha256(kind: str) -> None:
    system, user = rendered(kind, *ours(kind))
    digest = tuple(hashlib.sha256(text.encode()).hexdigest() for text in (system, user))
    assert digest == RENDERED_SHA256[kind]


@pytest.mark.parametrize("kind", ["plan", "review", "insight"])
def test_the_envelope_changes_no_byte(kind: str) -> None:
    """★b — 봉투가 구획을 strip 해도 변수로 넘긴 글은 앞뒤 빈 줄·괄호까지 그대로다."""
    system, user = ours(kind)
    assert system.startswith("\n")
    assert user.endswith("\n    ")
    assert rendered(kind, system, user) == (system, user)


def test_the_data_json_is_the_received_dict_as_is() -> None:
    _, user = ours("plan")
    assert json.dumps(data_split(), ensure_ascii=False, separators=(",", ":")) in user
    assert '"2023":"1,250"' in user  # 받은 글자 그대로


def test_cell_14_sends_single_braces_and_the_made_up_example_numbers() -> None:
    system, _ = ours("review")
    assert '{ "value": "N/A" }' in system
    assert "{{" not in system
    assert '"values": {"2022": 1200, "2023": 1300, "2024": 1400}' in system


def test_the_variables_land_where_the_colab_had_them() -> None:
    _, user = ours("plan")
    assert "    [기업명]: 가상건설\n" in user
    assert "    [주요 중대토픽(Material Topics)]: 기후변화 대응, 안전보건, 가상 토픽 {괄호}\n" in user
    assert "    [Reporting year]: 2025\n" in user
    system, user = ours("review")
    assert "최대 6 스텝" in system  # len(HINTS)*3
    assert "    - " + "\n- ".join(HINTS) + "</힌트>" in user
    system, _ = prompts.plan_prompt(**COMPANY, data_split=data_split(), max_steps=20)
    assert "최대 20 스텝" in system
    assert "툴 호출은 16 ~ 18 사이에서만 허용하며" in system


def test_the_settings() -> None:
    assert (prompts.MODEL_RESP, prompts.TOLERANCE, prompts.PLAN_MAX_STEPS, prompts.INSIGHT_MAX_STEPS) == (
        "gpt-4.1",
        0.0,  # 판정 허용 오차 0(밴드 DV16, MARC-ENT-685 — 코랩은 1.1)
        12,
        12,
    )
    assert prompts.review_max_steps(HINTS) == 6
