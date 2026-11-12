"""파서의 단위 테스트. 컨테이너도 저장소도 없이 돈다. `POST /parse` 의 갈래는 `tests/test_http.py` 가 본다."""

import pytest
from fastapi.testclient import TestClient

import app as parser

client = TestClient(parser.app)


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "body",
    [
        {"sourceUrl": "http://storage/x"},
        {"sourceUrl": "http://169.254.169.254/latest/meta-data/"},
        {"sourceUrl": "file:///etc/passwd"},
        {},
    ],
)
def test_the_old_json_contract_is_gone_and_nothing_is_fetched(body, monkeypatch):
    """옛 약속(`application/json` 의 `{sourceUrl}` → 아무 http(s) 를 내려받음)은 걷혔다.

    이제 415 이고 아무것도 내려받지 않는다.
    """
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("파서가 주소를 내려받으려 했다"))
    response = client.post("/parse", json=body)
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_media_type"
