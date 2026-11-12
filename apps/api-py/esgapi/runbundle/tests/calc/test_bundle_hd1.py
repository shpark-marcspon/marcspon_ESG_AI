"""묶음 꼴 HD1 몫(runbundle/calc/bundle.py) — 순수 층.

    R4  loads: 자릿수 상한을 넘는 정수 · 재귀 상한을 넘는 중첩 → 제 글의 Refused(날 ValueError·RecursionError 0).
        시험 입력 크기는 sys.get_int_max_str_digits()·sys.getrecursionlimit() 에서 짓는다(상한 숫자를 지어내지 않음)
    R6  role shared: 같은 blob 을 문서와 실행 파일이 같이 가리키면 통과 · document·run_file 은 그대로 한 쪽만
★ 값은 전부 지어낸 것이다(synthetic).
"""

import copy
import json
import sys
from typing import Any, cast

import pytest

from esgapi.runbundle.calc.bundle import ROLES, SHARED, Blob, Refused, check_bundle, loads
from esgapi.runbundle.tests.calc.test_bundle import DOC, good


def test_an_integer_past_the_digit_limit_is_refused() -> None:
    text = b'{"a": ' + b"7" * (sys.get_int_max_str_digits() + 1) + b"}"
    with pytest.raises(Refused, match="자릿수 상한을 넘는 정수"):
        loads(text)


def nested(depth: int) -> bytes:
    return b"[" * depth + b"]" * depth


def test_nesting_past_the_recursion_limit_is_refused() -> None:
    """json 의 C 스캐너는 파이썬 재귀 상한과 다른 상한을 쓴다 — getrecursionlimit() 에서 두 배씩 늘려 날 json.loads 가
    RecursionError 를 내는 깊이를 재고(상한 숫자를 지어내지 않음), 그 깊이에서 loads 가 Refused 인지 본다."""
    depth = sys.getrecursionlimit()
    while True:
        try:
            json.loads(nested(depth))
        except RecursionError:
            break
        depth *= 2
    with pytest.raises(Refused, match="중첩이 너무 깊다"):
        loads(nested(depth))


def test_an_integer_at_the_digit_limit_still_reads() -> None:
    assert loads(b"[" + b"7" * sys.get_int_max_str_digits() + b"]") == [int("7" * sys.get_int_max_str_digits())]


def shared() -> dict[str, Any]:
    """문서 blob(DOC)을 실행 파일도 가리키는 머리(role shared)."""
    header = cast("dict[str, Any]", copy.deepcopy(good()))
    header["blobs"] = [{"sha256": DOC, "size": 3, "role": SHARED}]
    header["rows"]["run_files"][0] |= {"blob": DOC, "size_bytes": 3, "sha256": DOC}
    return header


def test_shared_is_one_more_role() -> None:
    assert frozenset({"document", "run_file", SHARED}) == ROLES


def test_a_shared_blob_passes_both_sides() -> None:
    bundle = check_bundle(shared())
    assert bundle.blobs == (Blob(DOC, 3, SHARED),)


@pytest.mark.parametrize("role", ["document", "run_file"])
def test_one_blob_under_both_rows_without_shared_is_refused(role: str) -> None:
    header = shared()
    header["blobs"][0]["role"] = role
    with pytest.raises(Refused, match="blob 이 목록에 없다"):
        check_bundle(header)
