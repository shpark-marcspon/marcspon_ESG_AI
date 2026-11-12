"""개발 compose 의 저장소 CORS(한 번짜리 storage-cors)를 글로 읽는다. 순수 층(컨테이너 0).

재는 것: storage-cors 덩어리의 꼴과 기본 허락 출처(웹 출처 넷), api-py 가 그 뒤에 뜸, 전역 대체(VGW_CORS_ALLOW_ORIGIN)를
쓰지 않음, 규칙 모양이 운영 terraform 과 같음, 출처 목록의 거절, 덩어리의 자리. 떠 있는 저장소의 판정은
tests_integration/test_storage_cors.py 가 잰다.

★ 무효 조건: 운영 규칙이 terraform 글(infra/terraform/modules/storage/main.tf 의 cors_rule)에서 다른 곳으로 가면
  4 의 대조를 그 자리로 옮긴다.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[5]
COMPOSE = ROOT / "compose.yaml"
SCRIPT = ROOT / "docker" / "storage_cors.py"
TERRAFORM = ROOT / "infra" / "terraform" / "modules" / "storage" / "main.tf"


def _service_block(compose: str, name: str) -> str:
    """compose.yaml 에서 서비스 하나의 덩어리(`  <이름>:` 다음 줄부터 다음 서비스나 `volumes:` 앞까지)."""
    found = re.search(rf"\n  {re.escape(name)}:\n(.*?)(?=\n  [a-z-]+:\n|\nvolumes:)", compose, re.S)
    assert found is not None, name
    return found.group(1)


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("storage_cors", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _compose() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def test_the_storage_cors_block_writes_the_web_origins_once() -> None:
    block = _service_block(_compose(), "storage-cors")
    assert "\n    image: ${COMPOSE_PROJECT_NAME:-esg-app}/api-py:local\n" in block
    assert "\n    pull_policy: never\n" in block
    assert "\n      - ./docker/storage_cors.py:/opt/storage_cors.py:ro\n" in block
    assert '\n    command: ["python", "/opt/storage_cors.py"]\n' in block
    assert "\n      storage: { condition: service_healthy }" in block
    found = re.search(r"\n      STORAGE_CORS_ORIGINS: \$\{STORAGE_CORS_ORIGINS:-(.+)\}\n", block)
    assert found is not None
    assert found.group(1).split(",") == [
        "http://localhost:${WEB_PORT:-15173}",
        "http://127.0.0.1:${WEB_PORT:-15173}",
        "http://localhost:${API_PY_PORT:-18081}",
        "http://127.0.0.1:${API_PY_PORT:-18081}",
    ]
    assert "*" not in found.group(1)
    assert "*api-py-env" not in block
    assert "restart:" not in block  # 한 번 돌고 끝나는 일


def test_api_py_starts_after_the_rule_is_written() -> None:
    block = _service_block(_compose(), "api-py")
    assert "\n      storage-cors: { condition: service_completed_successfully }" in block


def test_the_storage_has_no_global_cors_fallback() -> None:
    """전역 대체는 출처 하나뿐이고, 버킷 규칙이 없으면 어떤 Origin 에도 ACAO 를 붙인다(Versity v1.8.0)."""
    block = _service_block(_compose(), "storage")
    assert "VGW_CORS_ALLOW_ORIGIN" not in block
    assert "cors-allow-origin" not in block


def _terraform_cors_rule() -> dict[str, object]:
    text = TERRAFORM.read_text(encoding="utf-8")
    body = text.split("cors_rule {", 1)[1].split("\n  }", 1)[0]

    def strings(name: str) -> list[str]:
        found = re.search(rf"^\s*{name}\s*=\s*\[(.*?)\]", body, re.M)
        assert found is not None, name
        return re.findall(r'"([^"]*)"', found.group(1))

    max_age = re.search(r"^\s*max_age_seconds\s*=\s*(\d+)", body, re.M)
    assert max_age is not None
    return {
        "AllowedMethods": strings("allowed_methods"),
        "AllowedHeaders": strings("allowed_headers"),
        "ExposeHeaders": strings("expose_headers"),
        "MaxAgeSeconds": int(max_age.group(1)),
    }


def test_the_rule_has_the_same_shape_as_the_terraform_one() -> None:
    rule = _script().rule_for(("http://a.test",))
    assert rule["AllowedOrigins"] == ["http://a.test"]
    expected = _terraform_cors_rule()
    assert {key: rule[key] for key in expected} == expected
    assert set(rule) == {"AllowedOrigins", *expected}


def test_parse_origins_keeps_the_order_and_refuses_the_rest() -> None:
    parse = _script().parse_origins
    assert parse(" http://localhost:15173,http://127.0.0.1:15173 , https://a.test,http://localhost:18081") == (
        "http://localhost:15173",
        "http://127.0.0.1:15173",
        "https://a.test",
        "http://localhost:18081",
    )
    for bad in (
        "",
        " , ",
        "*",
        "http://localhost:*",
        "http://localhost:15173/",
        "http://localhost:15173/x",
        "http://a.test,http://a.test",
        "ftp://a.test",
        "null",
    ):
        with pytest.raises(ValueError):
            parse(bad)


def test_the_storage_cors_block_sits_between_storage_and_queue() -> None:
    """api-py 와 migrate-py 사이에 들면 test_env.py 의 _api_py_block 이 그 키들을 api-py 의 것으로 세어 가린다."""
    names = re.findall(r"^  ([a-z-]+):\n", _compose().split("\nservices:\n", 1)[1].split("\nvolumes:\n", 1)[0], re.M)
    at = names.index("storage-cors")
    assert names[at - 1 : at + 2] == ["storage", "storage-cors", "queue"]
