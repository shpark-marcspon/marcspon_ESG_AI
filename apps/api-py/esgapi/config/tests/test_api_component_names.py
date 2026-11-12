# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
"""계약 문서(OpenAPI)의 컴포넌트 이름 하나에는 정의가 하나다(MARC-ISSUE-301, 밴드 DV1i).

ninja 는 모델의 `$defs` 를 이름으로 components 에 합친다 — 같은 이름에 다른 정의가 오면 나중 것이 앞 것을 조용히 덮는다
(ninja 1.7.1 openapi/schema.py:336-342 `add_schema_definitions` 의 `self.schemas.update` — 그 자리의 TODO 도
그것을 말한다).
그래서 다 지은 문서만 봐서는 못 잡는다. 이 시험은 그 자리를 `monkeypatch` 로 감싸(이 시험 안에서만 — 다른 시험에 남김 0)
들어오는 (이름, 정의)를 전부 모은 뒤 진짜 `api` 의 문서를 짓고, 한 이름에 서로 다른 정의가 둘 이상인지 본다.
같은 정의가 두 자리에서 오는 것(예 `JsonValue`, 여러 경로가 같이 쓰는 모델)은 겹침이 아니다.

`dataverify/tests/contracts/test_shapes.py` 의 교집합 시험(결과 꼴 셋끼리)과 겹쳐도 된다 — 이쪽은 경로에 걸린
전부를 본다.
순수 층: DB 에 닿지 않는다.
"""

from typing import Any

import pytest
from ninja import NinjaAPI, Router, Schema
from ninja.openapi.schema import OpenAPISchema

from esgapi.config.api import api


def definitions_by_name(
    monkeypatch: pytest.MonkeyPatch, target: NinjaAPI
) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    """`target` 의 계약 문서를 지으며 components 로 들어간 정의를 이름별로(들어온 차례대로, 같은 것은 한 번) 모은다.
    지은 문서의 components 이름도 같이 낸다 — 분모(감싸기가 빗나가 못 모으면 겹침 0 이 거짓 초록이 된다)."""
    seen: dict[str, list[dict[str, Any]]] = {}
    original = OpenAPISchema.add_schema_definitions

    def recording(self: OpenAPISchema, definitions: dict[str, Any]) -> None:
        for name, definition in definitions.items():
            known = seen.setdefault(name, [])
            if definition not in known:
                known.append(definition)
        original(self, definitions)

    monkeypatch.setattr(OpenAPISchema, "add_schema_definitions", recording)
    # 가짜 api 는 urls 에 걸리지 않았다 — 접두를 reverse 로 찾지 않게 준다(진짜 api 의 기본값도 "")
    document = target.get_openapi_schema(path_prefix="")
    return seen, set(document["components"]["schemas"])


def collisions(seen: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted(name for name, found in seen.items() if len(found) > 1)


def test_no_component_name_has_two_definitions(monkeypatch: pytest.MonkeyPatch) -> None:
    seen, components = definitions_by_name(monkeypatch, api)
    assert collisions(seen) == []
    assert set(seen) == components
    assert {"DataverifySettings", "GreenwashAiSettingApply", "JsonValue"} <= set(seen)


# ── 재는 법이 문다는 것: 가짜 api 둘(진짜 api 는 건드리지 않는다) ──


def twin_api(namespace: str, same: bool) -> NinjaAPI:
    """라우터 둘이 이름이 `Twin` 인 모델을 하나씩 받는다. same 이면 두 정의가 글자까지 같다."""

    def first() -> type[Schema]:
        class Twin(Schema):
            """쌍둥이."""

            value: int

        return Twin

    def second() -> type[Schema]:
        class Twin(Schema):
            """쌍둥이."""

            value: int if same else str  # pyright: ignore[reportInvalidTypeForm]

        return Twin

    fake = NinjaAPI(urls_namespace=namespace)
    for prefix, model in (("/a", first()), ("/b", second())):
        router = Router()

        def view(request: Any, body: model) -> int:  # pyright: ignore[reportInvalidTypeForm]
            del request, body
            return 0

        router.post("/", response=int)(view)
        fake.add_router(prefix, router)
    return fake


def test_two_definitions_under_one_name_are_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    seen, _ = definitions_by_name(monkeypatch, twin_api("dv1i-twin-differ", same=False))
    assert collisions(seen) == ["Twin"]


def test_one_definition_from_two_places_is_not_a_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    seen, _ = definitions_by_name(monkeypatch, twin_api("dv1i-twin-same", same=True))
    assert collisions(seen) == []
    assert "Twin" in seen
