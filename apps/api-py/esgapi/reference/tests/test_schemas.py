"""응답의 꼴(service/schemas/reference.py)이 조립의 실패 갈래를 빠짐없이 싣는가. 순수 층.

경로는 `exclude_unset` 으로 답한다: 응답 스키마가 모르는 칸은 오류 없이 조용히 빠진다. 그래서 갈래마다의 곁칸을
스키마(FailureOut)가 다 아는지를 여기서 본다. 갈래나 곁칸을 더하고 스키마를 잊으면 빨개진다.
"""

from esgapi.reference.calc import FAILURE_KINDS
from esgapi.reference.service.schemas.reference import FailureOut
from esgapi.reference.tests.test_failures import one_failure_of_every_kind


def test_the_failure_schema_knows_every_field_of_every_kind() -> None:
    failures = one_failure_of_every_kind()
    assert {failure["kind"] for failure in failures} == set(FAILURE_KINDS)
    for failure in failures:
        assert set(failure) <= set(FailureOut.model_fields), failure["kind"]
        assert FailureOut.model_validate(failure).model_dump(exclude_unset=True) == failure
