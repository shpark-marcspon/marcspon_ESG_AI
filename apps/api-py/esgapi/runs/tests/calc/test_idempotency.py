"""Idempotency-Key 의 순수 규칙(runs/calc/idempotency.py — 밴드 IK1 §2-2): 열쇠 꼴과 본문 sha256. DB 없음."""

import hashlib
import re

from esgapi.runs.calc.idempotency import KEY_PATTERN, body_sha256


def sha(**overrides: object) -> str:
    fields: dict[str, object] = {
        "module": "probe",
        "flow_id": None,
        "document_id": 7,
        "options": {"pages": "1-3", "lang": "ko"},
        "resume_from": None,
    }
    fields.update(overrides)
    return body_sha256(**fields)  # pyright: ignore[reportArgumentType]


# 손으로 적은 기대 바이트와 그 sha256(고정 값 — 바이트 규칙이 바뀌면 빨개진다)
EXPECTED = (
    '{"module":"probe","flowId":null,"documentId":7,"options":{"제목":"지은 보고서","n":1},"resumeFromRunId":null}'
)
FIXED = "4508d63166987624e473fb32b0474291f2e8ecdde354937a02380ef678866177"


def test_the_bytes_are_fixed_compact_utf8_in_the_declared_order() -> None:
    """최상위 다섯 열쇠의 차례, 공백 없음, 한글은 \\u 이스케이프 없이 UTF-8."""
    got = body_sha256(
        module="probe", flow_id=None, document_id=7, options={"제목": "지은 보고서", "n": 1}, resume_from=None
    )
    assert got == hashlib.sha256(EXPECTED.encode("utf-8")).hexdigest() == FIXED


def test_the_options_order_matters_and_every_field_counts() -> None:
    base = sha()
    assert sha(options={"lang": "ko", "pages": "1-3"}) != base  # 같은 값·다른 차례 = 다른 요청(sort_keys 아님)
    assert sha(options={"pages": "1-4", "lang": "ko"}) != base
    assert sha(options={}) != base
    assert sha(module="other") != base
    assert sha(flow_id="probe.two@1") != base
    assert sha(document_id=8) != base
    assert sha(document_id=None) != base
    assert sha(resume_from=3) != base
    assert sha() == base  # 분모: 같은 값은 같다
    assert re.fullmatch(r"[0-9a-f]{64}", base)


def test_a_mapping_of_the_same_items_in_the_same_order_is_the_same() -> None:
    """options 는 Mapping 이면 된다(dict 로 적는다) — 차례가 같으면 같다."""
    from collections import OrderedDict

    assert sha(options=OrderedDict([("pages", "1-3"), ("lang", "ko")])) == sha()


def test_nan_is_hashed_not_refused() -> None:
    """IK1 처분 m3: allow_nan=True — NaN 이 든 옵션도 sha 를 낸다(열쇠 유무로 갈래가 달라지지 않게)."""
    assert re.fullmatch(r"[0-9a-f]{64}", sha(options={"x": float("nan")}))


def test_the_key_pattern_is_a_lowercase_uuid() -> None:
    pattern = re.compile(KEY_PATTERN)
    assert pattern.fullmatch("0b0e6c1e-1111-4222-8333-444455556666")
    for bad in (
        "0B0E6C1E-1111-4222-8333-444455556666",
        "1",
        "",
        "0b0e6c1e-1111-4222-8333-4444556666777",
        "0b0e6c1e111142228333444455556666",
        "0b0e6c1e-1111-4222-8333-44445555666g",
    ):
        assert pattern.fullmatch(bad) is None, bad


def test_bodies_differing_only_in_resume_from_have_different_shas() -> None:
    """IK1 검증 R1: resumeFromRunId 만 다른 두 본문은 다른 요청이다(없음 · 3 · 4 셋 다 다름)."""
    assert len({sha(resume_from=None), sha(resume_from=3), sha(resume_from=4)}) == 3


# ── LK1: launchKey 는 값이 있을 때만 여섯째 칸(발주서 §2-2 — Q5) ─────────────────────

LAUNCH = "0b0e6c1e-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID
EXPECTED_WITH_LAUNCH = (
    '{"module":"probe","flowId":null,"documentId":7,"options":{"제목":"지은 보고서","n":1},"resumeFromRunId":null,'
    '"launchKey":"0b0e6c1e-1111-4222-8333-444455556666"}'
)


def test_without_a_launch_key_the_bytes_are_the_ik1_ones() -> None:
    """launch_key=None 과 인자 생략은 IK1 의 FIXED 그대로(배포 전 열쇠의 다시 보냄이 같은 sha)."""
    fields: dict[str, object] = {
        "module": "probe", "flow_id": None, "document_id": 7, "options": {"제목": "지은 보고서", "n": 1},
        "resume_from": None,
    }  # fmt: skip
    assert body_sha256(**fields) == body_sha256(**fields, launch_key=None) == FIXED  # pyright: ignore[reportArgumentType]


def test_a_launch_key_is_appended_sixth_and_counts() -> None:
    got = body_sha256(
        module="probe", flow_id=None, document_id=7, options={"제목": "지은 보고서", "n": 1}, resume_from=None,
        launch_key=LAUNCH,
    )  # fmt: skip
    assert got == hashlib.sha256(EXPECTED_WITH_LAUNCH.encode("utf-8")).hexdigest()
    assert got != FIXED  # 값 있음 ≠ 없음
    other = "9f8e7d6c-5b4a-4321-8fed-cba987654321"
    assert len({sha(), sha(launch_key=LAUNCH), sha(launch_key=other)}) == 3  # 값이 다르면 다르다
    assert sha(launch_key=LAUNCH) == sha(launch_key=LAUNCH)  # 분모


# ── RM1c ③: retrySegments(T14 — 바이트 R9) ──

RETRY_KEYS = ("b" * 64, "a" * 64)


def test_without_retry_segments_the_bytes_are_the_ik1_bytes() -> None:
    """칸이 없으면(None) 바이트가 RM1c 앞과 같다 — 배포 전 열쇠의 다시 보냄이 같은 sha(고정 값 FIXED)."""
    got = body_sha256(
        module="probe",
        flow_id=None,
        document_id=7,
        options={"제목": "지은 보고서", "n": 1},
        resume_from=None,
        retry=None,
    )
    assert got == FIXED


def test_retry_segments_come_after_the_launch_key_in_the_declared_order() -> None:
    """launchKey 다음에 {"fromRunId","step","keys"} 이 차례 — keys 는 보낸 차례 그대로(정렬 아님)."""
    launch = "0b0e6c1e-1111-4222-8333-444455556666"
    expected = (
        '{"module":"probe","flowId":null,"documentId":7,"options":{},"resumeFromRunId":null,'
        f'"launchKey":"{launch}","retrySegments":{{"fromRunId":3,"step":"spread","keys":["{"b" * 64}","{"a" * 64}"]}}}}'
    )
    got = sha(options={}, launch_key=launch, retry=(3, "spread", list(RETRY_KEYS)))
    assert got == hashlib.sha256(expected.encode("utf-8")).hexdigest()
    without_launch = expected.replace(f'"launchKey":"{launch}",', "")
    assert sha(options={}, retry=(3, "spread", RETRY_KEYS)) == hashlib.sha256(without_launch.encode()).hexdigest()


def test_every_retry_field_and_the_key_order_count() -> None:
    base = sha(retry=(3, "spread", RETRY_KEYS))
    assert base != sha()  # 칸 있음 ≠ 칸 없음
    assert sha(retry=(4, "spread", RETRY_KEYS)) != base
    assert sha(retry=(3, "other", RETRY_KEYS)) != base
    assert sha(retry=(3, "spread", tuple(reversed(RETRY_KEYS)))) != base  # 차례만 바꿈 = 다른 요청(409)
    assert sha(retry=(3, "spread", RETRY_KEYS[:1])) != base
    assert sha(retry=(3, "spread", list(RETRY_KEYS))) == base  # 분모: 튜플·목록 같은 값은 같다
