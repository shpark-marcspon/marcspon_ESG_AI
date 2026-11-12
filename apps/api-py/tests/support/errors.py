"""오류 본문을 읽는 도구(밴드 E2). 업무 층·보안 층·순수 시험이 같이 쓴다.

본문의 꼴은 하나다: {"error": {"code", "message", "fields", "legacyCode"}} (esgapi/core/exceptions.py).
읽기 전에 그 꼴인지부터 본다 — 키가 하나라도 빠지거나 더 있으면 AssertionError 다.
"""

from typing import Any, Protocol

ERROR_KEYS = frozenset({"code", "message", "fields", "legacyCode"})


class _Response(Protocol):
    status_code: int

    def json(self) -> Any: ...


def error_detail(response: _Response) -> dict[str, Any]:
    """본문의 error 칸. 꼴이 하나인지(키 넷, code·message 는 글자, fields 는 null 이거나 {칸: [글자]})를 함께 잰다."""
    body: Any = response.json()
    assert isinstance(body, dict), body
    top: dict[str, Any] = body  # pyright: ignore[reportUnknownVariableType]
    assert set(top) == {"error"}, top
    detail: dict[str, Any] = top["error"]
    assert set(detail) == ERROR_KEYS, detail
    assert isinstance(detail["code"], str) and isinstance(detail["message"], str), detail
    fields: Any = detail["fields"]
    if fields is not None:
        assert isinstance(fields, dict), detail
        for messages in fields.values():  # pyright: ignore[reportUnknownVariableType]
            assert isinstance(messages, list) and all(isinstance(m, str) for m in messages), detail  # pyright: ignore[reportUnknownVariableType]
    return detail


def error_of(response: _Response) -> tuple[int, str]:
    """(상태 코드, 대문자 code)."""
    return response.status_code, error_detail(response)["code"]


def fields_of(response: _Response) -> dict[str, list[str]] | None:
    return error_detail(response)["fields"]
