"""이어서 돌린 실행의 파일 바이트를 앞 실행의 키에서 새 키로 옮겨 적는다(X1b-2b ⑬b · RC1). DB 를 읽지도 쓰지도 않는다.

    carry(storage, …)   새 키 하나를 채운다: 후보 키(가까운 앞 실행부터)를 차례로 get → 처음 나온 바이트를 put

★ 부르는 자리는 실행기(runs/tasks.py 의 _plan)다: 옮긴 단계의 새 키가 비었고 그 실행이 이어 돈 것이면 앞 실행
  (사슬)의 같은 (단계, 이름) 키에서 옮겨 쓰고 그 바이트로 이어 돈다(RC1 — 요청 스레드 저장소 호출 0). 후보 키는 부르는
  쪽이 넘긴다(DB 0). 그 회사의 접두(runs/<회사 id>/)가 아닌 후보는 get 없이 건너뛴다(방어).
  닿지 못함은 더 거슬러 가지 않고 멈춘다(CarryUnavailable → 실행기의 RunDeferred). 없음·너무 큼·읽기 거절은 다음 후보로.
★ 던지지 않는다(저장소 포트도 갈래로 돌려준다).
★ 앞 실행의 객체는 읽기만 한다(앞 실행 불변). 크기는 파일 행의 size_bytes 가 상한이다.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from esgapi.core.resources.ports.storage import (
    ObjectBytes,
    ObjectPut,
    ObjectStorage,
    StorageDenied,
    StorageUnavailable,
)


@dataclass(frozen=True, slots=True)
class Carried:
    data: bytes
    from_run: int  # 바이트가 나온 앞 실행(로그용)


@dataclass(frozen=True, slots=True)
class CarryMissing:
    """어느 후보에도 쓸 바이트가 없다(없음·행의 크기보다 큼·읽기 거절·남의 접두)."""


@dataclass(frozen=True, slots=True)
class CarryUnavailable:
    detail: str


@dataclass(frozen=True, slots=True)
class CarryRefused:
    """새 키 쓰기가 거절됐다(403)."""

    detail: str


CarryResult = Carried | CarryMissing | CarryUnavailable | CarryRefused


def carry(
    storage: ObjectStorage,
    *,
    company_id: int,
    target_key: str,
    sources: Iterable[tuple[int, str]],
    size_bytes: int,
    media_type: str,
) -> CarryResult:
    """sources 는 (앞 run id, 키) 가까운 것부터 — 게으르게 하나씩 꺼낸다(앞에서 옮기면 뒤를 지어 내지 않는다)."""
    prefix = f"runs/{company_id}/"
    for run_id, key in sources:
        if not key.startswith(prefix):
            continue
        got = storage.get(key, max_bytes=size_bytes)
        if isinstance(got, StorageUnavailable):
            return CarryUnavailable(got.detail)
        if not isinstance(got, ObjectBytes):
            continue
        put = storage.put(target_key, content=got.data, media_type=media_type)
        if isinstance(put, ObjectPut):
            return Carried(data=got.data, from_run=run_id)
        if isinstance(put, StorageDenied):
            return CarryRefused(put.detail)
        return CarryUnavailable(put.detail)
    return CarryMissing()
