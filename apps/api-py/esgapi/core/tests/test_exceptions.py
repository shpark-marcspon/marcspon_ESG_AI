"""오류 본문 한 꼴(밴드 E2 ①): code 는 대문자, 옛 소문자는 legacyCode, fields 는 늘 키가 있다."""

import json

import pytest

from esgapi.core.exceptions import ErrorBody, ErrorDetail, edk_code, error_response


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("no_session", "NO_SESSION"),
        ("review_locked", "REVIEW_LOCKED"),
        ("token_not_valid", "TOKEN_NOT_VALID"),
        ("forbidden", "FORBIDDEN"),
        ("not_found", "NOT_FOUND"),
        ("invalid_input", "BAD_REQUEST"),  # 세부 이름 없는 400 은 EDK 의 일반 이름
        ("unauthenticated", "UNAUTHORIZED"),
        ("VALIDATION_ERROR", "VALIDATION_ERROR"),  # 이미 대문자면 그대로
    ],
)
def test_edk_code(old: str, new: str) -> None:
    assert edk_code(old) == new


def test_error_response_carries_all_four_keys() -> None:
    response = error_response(409, "review_locked", "확정된 실행이다")
    assert response.status_code == 409
    assert json.loads(response.content) == {
        "error": {"code": "REVIEW_LOCKED", "message": "확정된 실행이다", "fields": None, "legacyCode": "review_locked"}
    }


def test_a_detail_built_in_lowercase_goes_out_in_uppercase_once() -> None:
    detail = ErrorDetail(code="too_many_rows", message="m")
    assert (detail.code, detail.legacyCode) == ("TOO_MANY_ROWS", "too_many_rows")
    again = ErrorDetail.model_validate(detail.model_dump())  # 두 번 지나도 같다
    assert again.model_dump() == detail.model_dump()


def test_an_uppercase_code_has_no_legacy_unless_given() -> None:
    assert ErrorDetail(code="INTERNAL_SERVER_ERROR", message="m").legacyCode is None
    given = ErrorDetail(code="VALIDATION_ERROR", message="m", legacyCode="invalid_input")
    assert given.legacyCode == "invalid_input"


def test_the_schema_says_every_key_is_always_there_and_legacy_is_deprecated() -> None:
    schema = ErrorBody.model_json_schema()["$defs"]["ErrorDetail"]
    assert set(schema["required"]) == {"code", "message", "fields", "legacyCode"}
    assert schema["properties"]["legacyCode"]["deprecated"] is True
