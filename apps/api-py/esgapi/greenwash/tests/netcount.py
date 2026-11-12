"""pytest 플러그인(`-p esgapi.greenwash.tests.netcount` 로만 켜진다): 테스트마다 소켓 문지기(뿌리 conftest 의
blocked_network)가 막은 시도의 수를 환경 변수 G1A_NET_LOG 의 파일에 한 줄씩 적는다. section4-G1a.sh 의 바-20 이 센다.

GW1 의 스캔 루프는 쪽 안의 예외를 삼키므로(흠 12), 막힌 시도가 테스트를 빨갛게 하지 않을 수 있다 — 그래서 따로 센다.
"""

import os
from collections.abc import Iterator
from typing import cast

import pytest


@pytest.fixture(autouse=True)
def _count_blocked(request: pytest.FixtureRequest, blocked_network: list[object]) -> Iterator[None]:
    yield
    path = os.environ.get("G1A_NET_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as log:
            node = cast("pytest.Item", getattr(request, "node"))  # noqa: B009  (request.node 의 타입이 알려져 있지 않다)
            log.write(f"{len(blocked_network)} {node.nodeid}\n")
