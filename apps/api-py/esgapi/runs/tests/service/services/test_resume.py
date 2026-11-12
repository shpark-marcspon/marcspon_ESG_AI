"""이어 돌기의 파일 옮김(runs/service/services/resume.py — X1b-2b ⑬b · RC1)을 가짜 저장소로 잰다. 순수 층(DB 0).

재는 것: carry(RC1) — 후보를 가까운 것부터 게으르게, 없음·큼·읽기 거절은 다음, 닿지 못함은 멈춤, 남의 접두는 get 0,
put 의 닿지 못함·거절, 앞 키는 읽기만.
★ 바이트는 전부 지어낸 것이다(synthetic).
"""

from collections.abc import Iterator

import pytest

from esgapi.core.resources.ports.storage import GetResult, StorageDenied, StorageUnavailable
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.service.services.resume import (
    Carried,
    CarryMissing,
    CarryRefused,
    CarryUnavailable,
    carry,
)

# ── carry(RC1): 실행기 _plan 이 새 키 하나를 채운다 ──────────────────────────

TARGET = "runs/1/9/steps/s/a.json"
FIRST = (8, "runs/1/8/steps/s/a.json")
SECOND = (7, "runs/1/7/steps/s/a.json")


def carried(storage: FakeStorage, sources: list[tuple[int, str]] | Iterator[tuple[int, str]], size: int = 3) -> object:
    return carry(
        storage, company_id=1, target_key=TARGET, sources=sources, size_bytes=size, media_type="application/json"
    )


def failing(storage: FakeStorage, monkeypatch: pytest.MonkeyPatch, key: str, result: GetResult) -> None:
    """그 키의 get 만 result 를 돌려준다(fail_with 는 모든 키 — 앞 키 하나만 실패하는 저장소를 흉내 낸다)."""
    real = storage.get

    def get(asked: str, *, max_bytes: int) -> GetResult:
        if asked == key:
            storage.get_calls.append(asked)
            return result
        return real(asked, max_bytes=max_bytes)

    monkeypatch.setattr(storage, "get", get)


def test_carry_takes_the_first_source_and_writes_the_target() -> None:
    storage = FakeStorage()
    storage.put(FIRST[1], b"AAA")
    storage.put(SECOND[1], b"BBB")
    assert carried(storage, [FIRST, SECOND]) == Carried(data=b"AAA", from_run=8)
    assert storage.objects[TARGET][0] == b"AAA"
    assert storage.media_types[TARGET] == "application/json"
    assert (storage.get_calls, storage.put_calls) == ([FIRST[1]], [TARGET])
    assert storage.objects[FIRST[1]][0] == b"AAA"  # 앞 키 그대로


def test_carry_goes_on_to_the_next_source_when_one_is_missing_too_large_or_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = FakeStorage()
    storage.put(FIRST[1], b"TOO-BIG")
    storage.put(SECOND[1], b"BBB")
    assert carried(storage, [(9, "runs/1/x/none.json"), FIRST, SECOND]) == Carried(data=b"BBB", from_run=7)
    assert storage.get_calls == ["runs/1/x/none.json", FIRST[1], SECOND[1]]
    refusing = FakeStorage()
    refusing.put(SECOND[1], b"BBB")
    failing(refusing, monkeypatch, FIRST[1], StorageDenied("지어낸 읽기 거절"))
    assert carried(refusing, [FIRST, SECOND]) == Carried(data=b"BBB", from_run=7)


def test_carry_stops_at_an_unreachable_store_without_reading_further(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = FakeStorage()
    storage.put(SECOND[1], b"BBB")
    failing(storage, monkeypatch, FIRST[1], StorageUnavailable("지어낸 끊김"))
    assert carried(storage, [FIRST, SECOND]) == CarryUnavailable("지어낸 끊김")
    assert (storage.get_calls, storage.put_calls) == ([FIRST[1]], [])


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (StorageUnavailable("쓰기 끊김"), CarryUnavailable("쓰기 끊김")),
        (StorageDenied("쓰기 거절"), CarryRefused("쓰기 거절")),
    ],
    ids=["unavailable", "denied"],
)
def test_carry_reports_a_failed_put(failure: StorageUnavailable | StorageDenied, expected: object) -> None:
    storage = FakeStorage()
    storage.put(FIRST[1], b"AAA")
    storage.put(SECOND[1], b"BBB")
    storage.put_fail_with = failure
    assert carried(storage, [FIRST, SECOND]) == expected
    assert (storage.get_calls, storage.put_calls) == ([FIRST[1]], [TARGET])  # 다음 후보로 가지 않는다
    assert TARGET not in storage.objects


def test_carry_never_reads_a_key_outside_the_company() -> None:
    """회사 접두 방어(BASE 의 갈고리 방어 — test_runs 의 남의 접두 거절을 잇는다): 같은 바이트가 있어도 get 0."""
    storage = FakeStorage()
    foreign = (8, "runs/2/8/steps/s/a.json")
    storage.put(foreign[1], b"AAA")
    assert carried(storage, [foreign, (8, "runs/10/8/steps/s/a.json")]) == CarryMissing()
    assert (storage.get_calls, storage.put_calls) == ([], [])
    storage.put(FIRST[1], b"AAA")
    assert carried(storage, [foreign, FIRST]) == Carried(data=b"AAA", from_run=8)  # 분모: 제 접두는 읽는다


def test_carry_without_sources_is_missing() -> None:
    storage = FakeStorage()
    assert carried(storage, []) == CarryMissing()
    assert (storage.get_calls, storage.put_calls) == ([], [])


def test_carry_draws_the_sources_lazily() -> None:
    storage = FakeStorage()
    storage.put(FIRST[1], b"AAA")
    drawn: list[int] = []

    def sources() -> Iterator[tuple[int, str]]:
        for source in (FIRST, SECOND):
            drawn.append(source[0])
            yield source

    assert carried(storage, sources()) == Carried(data=b"AAA", from_run=8)
    assert drawn == [8]  # 첫에서 옮겼으니 둘째를 지어 내지 않는다
