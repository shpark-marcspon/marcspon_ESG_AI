"""옛 id → 새 id 지도의 순수 몫(django 0): 넣는 차례, 받는 쪽의 열쇠 짓기, versions 의 aiSettingId 다시 쓰기.

    document_order(rows)            문서 넣는 차례: 앞 판 먼저, 그다음 옛 id 오름(묶음 밖 앞 판은 None 이라 묶지 않음)
    run_order(rows)                 실행 넣는 차례: 옛 id 오름(이어 간 사슬은 id 가 줄어드는 차례로만 — F2)
    idempotency_key(bundle, old)    uuid5(RX1_NS, "<bundleId>:<옛 id>") — 같은 묶음 두 번 넣기를 가르는 열쇠(Q4)
    launch_key(bundle, old)         uuid5(UUID(bundleId), 옛 열쇠) — 묶음 안 무리는 남고 두 넣기끼리는 섞이지 않는다
    rewrite_versions(versions, ids) 공통 열쇠 aiSettingId 를 **그 실행 모듈의** 판 지도로(None 은 그대로 — 웹 「기본
                                    설정」). 모듈 열쇠 aiSetting(판 이름)은 carrier rewrite 몫이다(RX1b)

지도 자체(IdMap)와 지도 밖의 UnknownId 는 core/flows/carriers.py 에 있다(carrier 가 같이 쓴다).
"""

import uuid
from collections.abc import Mapping, Sequence
from typing import Final

from esgapi.core.flows.carriers import IdMap
from esgapi.runbundle.calc.bundle import Refused

RX1_NS: Final = uuid.uuid5(uuid.NAMESPACE_URL, "esg.run-bundle@1")
AI_SETTING_ID: Final = "aiSettingId"


def idempotency_key(bundle_id: str, old_id: int) -> str:
    return str(uuid.uuid5(RX1_NS, f"{bundle_id}:{old_id}"))


def launch_key(bundle_id: str, old_key: str | None) -> str | None:
    return None if old_key is None else str(uuid.uuid5(uuid.UUID(bundle_id), old_key))


def run_order(rows: Sequence[Mapping[str, object]]) -> list[int]:
    return sorted(int(str(row["oldId"])) for row in rows)


def document_order(rows: Sequence[Mapping[str, object]]) -> list[int]:
    """앞 판이 먼저 오도록(같은 회사 외래 키 — 넣는 때 앞 판의 새 id 가 있어야 한다). 순환이면 Refused."""
    previous = {int(str(row["oldId"])): row["previousOldId"] for row in rows}
    order: list[int] = []
    placed: set[int] = set()
    for start in sorted(previous):
        path: list[int] = []
        current: int | None = start
        while current is not None and current not in placed:
            if current in path:
                raise Refused("문서 판 사슬에 순환이 있다")
            path.append(current)
            before = previous.get(current)
            current = before if isinstance(before, int) and before in previous else None
        for old in reversed(path):
            order.append(old)
            placed.add(old)
    return order


def rewrite_versions(versions: Mapping[str, object], ids: IdMap) -> dict[str, object]:
    """aiSettingId 가 정수면 판 지도의 새 id(지도 밖이면 UnknownId — ids 는 그 실행 모듈의 지도만 담는다, 다른 모듈의
    옛 판 id 도 UnknownId), None·없음이면 그대로."""
    rewritten = dict(versions)
    old = rewritten.get(AI_SETTING_ID)
    if isinstance(old, int) and not isinstance(old, bool):
        rewritten[AI_SETTING_ID] = ids.ai_setting_id(old)
    elif old is not None and AI_SETTING_ID in rewritten:
        raise Refused("versions 의 aiSettingId 꼴이 틀렸다")
    return rewritten
