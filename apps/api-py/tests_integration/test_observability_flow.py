"""떠 있는 api-py 컨테이너의 request ID 와 로그. 호스트에서 요청을 보내고, 컨테이너가 표준 출력에 낸 줄을 읽는다.

재는 것: gunicorn → Django 의 미들웨어 사슬을 다 지난 응답에 X-Request-ID 가 있다, 받은 값이 되돌아온다,
요청 하나에 접근 줄이 정확히 하나다(gunicorn 의 접근 로그와 두 벌이 아니다).
"""

import json
import re
import uuid
from typing import Any

import httpx

from tests_integration.conftest import API, compose, wait_for

HEX32 = re.compile(r"[0-9a-f]{32}")
FIELDS = {
    "ts",
    "level",
    "logger",
    "pid",
    "message",
    "request_id",
    "task_id",
    "task_name",
    "job_id",
    "method",
    "path",
    "status",
    "duration_ms",
    "exc",
}


def lines_with(request_id: str) -> list[dict[str, Any]]:
    """api-py 가 낸 줄 가운데 그 request_id 가 실린 것. JSON 으로 안 읽히는 줄은 여기서 세지 않는다."""
    found: list[dict[str, Any]] = []
    for line in compose("logs", "--no-color", "--no-log-prefix", "--tail", "300", "api-py").splitlines():
        if request_id not in line:
            continue
        parsed = json.loads(line)
        if parsed.get("request_id") == request_id:
            found.append(parsed)
    return found


def test_every_response_carries_a_request_id(http: httpx.Client) -> None:
    for path, status in (("/healthz", 200), ("/no/such/path", 404), ("/me", 401)):
        response = http.get(path)
        assert response.status_code == status, path
        assert HEX32.fullmatch(response.headers["x-request-id"]), path


def test_a_well_formed_id_comes_back_and_a_malformed_one_is_replaced(http: httpx.Client) -> None:
    sent = f"it-{uuid.uuid4().hex}"
    assert http.get("/healthz", headers={"X-Request-ID": sent}).headers["x-request-id"] == sent

    replaced = http.get("/healthz", headers={"X-Request-ID": "has space"})
    assert replaced.status_code == 200  # 거절하지 않는다
    assert HEX32.fullmatch(replaced.headers["x-request-id"])


def test_one_request_leaves_exactly_one_access_line() -> None:
    sent = f"it-{uuid.uuid4().hex}"
    with httpx.Client(base_url=API, timeout=10.0) as client:
        response = client.get("/healthz", params={"probe": "QUERY-SECRET"}, headers={"X-Request-ID": sent})
    assert (response.status_code, response.headers["x-request-id"]) == (200, sent)

    # 로그가 닿기까지 틈이 있을 수 있다. 「하나 이상」을 기다린 뒤 「정확히 하나」를 본다.
    wait_for("그 요청의 줄이 api-py 의 로그에 나오기", lambda: lines_with(sent) or None, timeout=20)
    lines = lines_with(sent)
    assert len(lines) == 1, lines
    line = lines[0]
    assert (line["logger"], line["method"], line["path"], line["status"]) == (
        "esgapi.access",
        "GET",
        "/api/healthz",
        200,
    )
    assert set(line) <= FIELDS
    assert "QUERY-SECRET" not in json.dumps(line)
