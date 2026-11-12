"""판 저장 본문의 나쁜 글자 거절(MARC-ISSUE-289 의 2): 판 이름·메모는 core 공개 판정식 has_bad_chars 하나로
거른다. DB 없이 본문 꼴만.

경로를 지나는 422 fields.memo·title 은 test_ai_settings.py(진짜 DB)가 잰다.
"""

import pytest
from pydantic import ValidationError

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.greenwash.service.apis import ai_settings as apis


# 짝 없는 서로게이트는 파이썬 dict 로 넣으면 pydantic 의 str 꼴이 먼저 거절해 판정식까지 오지 않는다 —
# 여기서는 NUL 만(서로게이트는 core 시험).
@pytest.mark.parametrize(("field", "noun"), [("title", "판 이름"), ("memo", "메모")])
def test_a_nul_is_refused_on_its_field(field: str, noun: str) -> None:
    body = {"title": "지어낸 판", "memo": "", field: "지어\x00낸"}
    with pytest.raises(ValidationError) as refused:
        apis.GreenwashAiSettingCreate.model_validate(body)
    errors = refused.value.errors()
    assert [error["loc"] for error in errors] == [(field,)]
    assert f"{noun}에 쓸 수 없는 글자가 있다" in errors[0]["msg"]


def test_a_plain_body_passes() -> None:
    plain = apis.GreenwashAiSettingCreate.model_validate({"title": "지어낸 판 😀", "memo": "지어낸 메모"})
    assert plain.memo == "지어낸 메모"


def test_the_check_is_the_core_one() -> None:
    assert apis.has_bad_chars is core_ai_settings.has_bad_chars
