"""inventory 의 흐름 둘(flows/): 등록, 지금 경로·파이프라인과의 등가, 선언의 글자, 흐름이 Service 를 모르는 것.

순수 층: DB 0, 소켓 문지기 아래(Scope 3 는 모의 공급사, 막힌 시도 0). 있던 도우미는 import 만 한다.
"""

import ast
import json
from pathlib import Path
from typing import cast

import pytest
from django.apps.registry import Apps
from django.conf import settings
from django.test.utils import isolate_apps

from esgapi.core.flows.registry import REGISTRY, FlowRegistry
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowRegistryError
from esgapi.inventory.engines.scope3.llm_first_1.calc import CurrencyAdjustment
from esgapi.inventory.engines.scope3.llm_first_1.pipeline import PipelineOptions, PipelineResult, run_pipeline
from esgapi.inventory.engines.scope3.llm_first_1.serialize import (
    calc_to_dict,
    decision_to_dict,
    trace_to_dict,
    usage_to_dict,
)
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import Shortlister
from esgapi.inventory.engines.scope3.llm_first_1.types import InputRow, LicenseStatus
from esgapi.inventory.engines.scope12.engine_1.aggregate import GroupKey
from esgapi.inventory.flows import registration
from esgapi.inventory.flows import scope3_colab_157 as scope3_colab
from esgapi.inventory.flows import scope3_llm_first_1 as scope3
from esgapi.inventory.flows import scope12_engine_1 as scope12
from esgapi.inventory.service.services.inventory import CalcDone, calc_rows
from esgapi.inventory.tests.scope3_catalog_support import G1, G1_EXAMPLES, load_catalog, load_examples
from esgapi.inventory.tests.scope3_llm_support import Harness, harness, load_adjustments, load_memory
from esgapi.inventory.tests.support import TEST_DATA, validated
from esgapi.inventory.tests.test_golden import PURE_GOLDENS, raw_tables_for
from esgapi.inventory.tests.test_scope3_golden_full import CONFIGS

FLOWS_DIR = Path(__file__).resolve().parents[1] / "flows"
FLOWS_PACKAGE = "esgapi.inventory.flows"  # 상대 import 를 풀 기준(ISSUE-207)


def test_ready_registered_both_flows() -> None:
    assert {k: v for k, v in REGISTRY.defaults().items() if k in registration.DEFAULTS} == registration.DEFAULTS
    assert REGISTRY.flows_of("inventory.scope12") == (scope12.FLOW,)
    assert REGISTRY.flows_of("inventory.scope3") == (scope3.FLOW, scope3_colab.FLOW)
    assert REGISTRY.default_of("inventory.scope3") is scope3_colab.FLOW
    assert REGISTRY.modules_without_default() == ()


def test_registration_into_a_fresh_registry() -> None:
    registry = FlowRegistry()
    registration.register(registry)
    assert registry.defaults() == registration.DEFAULTS
    with pytest.raises(FlowRegistryError, match=r"scope12\.engine@1 이 이미 있다"):
        registration.register(registry)


# ── Scope 1·2: 지금 경로(calc_rows)와 같다 ──


def scope12_run(activity_file: str, which: str, by: tuple[GroupKey, ...]) -> tuple[dict[str, object], CalcDone]:
    activity = json.loads((TEST_DATA / activity_file).read_text(encoding="utf-8"))
    tables = raw_tables_for(which)
    inputs = scope12.Scope12Inputs(rows=activity["activities"], gwp_set_id=activity["gwpSetId"], group_by=by)
    run = run_flow(scope12.FLOW, inputs, scope12.Scope12Adapters(tables=validated(tables)))
    assert run.output.files == ()
    assert list(run.steps) == ["calculate"]
    (result,) = run.output.results
    path = calc_rows(rows=activity["activities"], tables=tables, gwp_set_id=activity["gwpSetId"], group_by=by)
    assert isinstance(path, CalcDone)
    return result, path


@pytest.mark.parametrize(("golden", "activity", "which", "by"), PURE_GOLDENS, ids=[g[0] for g in PURE_GOLDENS])
def test_scope12_flow_equals_the_calc_path(golden: str, activity: str, which: str, by: tuple[GroupKey, ...]) -> None:
    result, path = scope12_run(activity, which, by)
    assert next(iter(result)) == "schemaVersion"
    assert result["schemaVersion"] == "scope12.result@2"
    rest = {k: v for k, v in result.items() if k != "schemaVersion"}
    assert rest == path.output
    assert json.dumps(rest, ensure_ascii=False) == json.dumps(path.output, ensure_ascii=False)


# ── Scope 3: run_pipeline 을 직접 부른 것과 같다 ──


def scope3_harness(shortlister: Shortlister, size: int, exclude: tuple[LicenseStatus, ...], adjusted: bool) -> Harness:
    return harness(
        load_catalog(),
        memory=load_memory(G1_EXAMPLES / "memory.synthetic.json"),
        heuristic=True,
        exclude=exclude,
        shortlist_size=size,
        shortlister=shortlister,
        adjustments=load_adjustments(G1 / "adjustments.synthetic.json") if adjusted else (),
    )


def scope3_flow_result(options: PipelineOptions, rows: list[InputRow]) -> dict[str, object]:
    inputs = scope3.Scope3Inputs(
        rows=rows,
        route=options.route,
        tags=options.tags,
        exclude_license_statuses=options.exclude_license_statuses,
        shortlist_size=options.shortlist_size,
        adjustments=options.adjustments,
    )
    adapters = scope3.Scope3Adapters(
        llm=options.client, catalog=options.store, memory=options.memory, shortlister=options.shortlister
    )
    run = run_flow(scope3.FLOW, inputs, adapters)
    assert run.output.files == ()
    assert list(run.steps) == ["pipeline"]
    (result,) = run.output.results
    assert next(iter(result)) == "schemaVersion"
    return result


@pytest.mark.parametrize(
    ("name", "shortlister", "size", "exclude", "adjusted"), CONFIGS, ids=[config[0] for config in CONFIGS]
)
def test_scope3_flow_equals_the_pipeline(
    name: str,
    shortlister: Shortlister,
    size: int,
    exclude: tuple[LicenseStatus, ...],
    adjusted: bool,
    blocked_network: list[object],
) -> None:
    rows = [example.row for example in load_examples()]
    through_flow = scope3_harness(shortlister, size, exclude, adjusted)
    result = scope3_flow_result(through_flow.options, rows)

    direct_harness = scope3_harness(shortlister, size, exclude, adjusted)
    direct = run_pipeline(rows, direct_harness.options)
    assert isinstance(direct, PipelineResult)
    assert result["schemaVersion"] == "scope3.llm-first.result@2"
    assert result["status"] == "done"
    assert result["rows"] == [
        {"rowId": r.row.row_id, "groupKey": r.group_key, "calc": calc_to_dict(r.calc)} for r in direct.rows
    ]
    flow_rows = cast("list[dict[str, object]]", result["rows"])
    assert [r["rowId"] for r in flow_rows] == [row.row_id for row in rows]  # 입력 차례
    assert result["groups"] == [
        {
            "key": g.key,
            "rowIds": list(g.row_ids),
            "decision": decision_to_dict(g.decision),
            "shortlists": [trace_to_dict(t) for t in g.shortlists],
        }
        for g in direct.groups
    ]
    assert result["usage"] == usage_to_dict(direct.usage)
    assert result["shortlist"] == {"method": direct.shortlist.method, "description": direct.shortlist.description}
    assert len(through_flow.mock.calls) == len(direct_harness.mock.calls) > 0
    assert blocked_network == []


def test_scope3_flow_rejects_like_the_pipeline(blocked_network: list[object]) -> None:
    first = load_examples()[0].row
    h = scope3_harness(*CONFIGS[0][1:])
    duplicated = scope3_flow_result(h.options, [first, first])
    assert duplicated == {
        "schemaVersion": "scope3.llm-first.result@2",
        "status": "rejected",
        "rejected": {"kind": "duplicate_row_id", "rowId": first.row_id, "problems": []},
    }
    assert h.mock.calls == []

    bad = CurrencyAdjustment("KRW", "USD", 2022, "1e-3", synthetic=True, source=None)
    h = harness(load_catalog(), heuristic=True, adjustments=(bad,))
    rejected = scope3_flow_result(h.options, [first])
    assert rejected["status"] == "rejected"
    detail = cast("dict[str, object]", rejected["rejected"])
    assert detail["kind"] == "invalid_adjustments"
    assert detail["rowId"] is None
    problems = cast("list[dict[str, object]]", detail["problems"])
    assert [p["kind"] for p in problems] == ["invalid_multiplier"]
    assert all(list(p) == ["index", "kind", "message"] for p in problems)
    assert h.mock.calls == []
    assert blocked_network == []


# ── 선언 ──


def test_flow_declarations() -> None:
    one, three = scope12.FLOW, scope3.FLOW
    assert (one.module, one.id, one.input_shape, one.result_shapes) == (
        "inventory.scope12",
        "scope12.engine@1",
        "scope12.input@1",
        ("scope12.result@2",),
    )
    assert (three.module, three.id, three.input_shape, three.result_shapes) == (
        "inventory.scope3",
        "scope3.llm-first@1",
        "scope3.input@1",
        ("scope3.llm-first.result@2",),
    )
    assert one.adapter_names == ("tables",)
    assert three.adapter_names == ("llm", "catalog", "memory", "shortlister")
    assert one.optional_adapters == three.optional_adapters == ()
    assert (one.steps, three.steps) == (("calculate",), ("pipeline",))
    assert one.output_files == three.output_files == ()
    colab = scope3_colab.FLOW
    assert (colab.module, colab.id, colab.input_shape, colab.result_shapes) == (
        "inventory.scope3",
        "scope3.colab@157",
        "scope3.colab.input@1",
        ("scope3.colab.result@1",),
    )
    assert colab.adapter_names == ("llm", "factor_book", "geocoder")
    assert (colab.optional_adapters, colab.steps, colab.output_files) == (
        (),
        (*scope3_colab.CATEGORY_STEPS, "assemble"),
        (),
    )
    assert (one, three, colab) == registration.FLOWS


def test_flows_call_no_service() -> None:
    forbidden = (
        "esgapi.inventory.service",
        "esgapi.reference",
        "esgapi.organization",
        "esgapi.user",
        "esgapi.reconcile",
    )
    hits: list[str] = []
    files = sorted(FLOWS_DIR.glob("*.py"))
    assert {p.name for p in files} >= {"scope12_engine_1.py", "scope3_llm_first_1.py", "registration.py"}
    for path in files:
        names = sorted(modules_in(path.read_text(encoding="utf-8"), FLOWS_PACKAGE))
        hits += [f"{path.name}: {n}" for n in names if n.startswith(forbidden)]
    assert hits == []


def resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미, 둘 = 그 위(dataverify
    tests/engines/colab_156/test_purity.py 의 판별 복사 — ISSUE-207)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def modules_in(source: str, package: str) -> set[str]:
    """절대·상대 import 둘 다(상대는 flows 꾸러미 기준 — 폴더가 납작해 파일마다 같다). `from . import x` 는 그
    꾸러미와 `<꾸러미>.x` 둘 다."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = resolve(node, package)
            names.add(module)
            if node.module is None:
                names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def test_relative_imports_are_resolved() -> None:
    """상대 꼴도 잡는다(ISSUE-207 — 옛 걷기는 `ImportFrom.level` 을 버려 `from ..service import x` 를 지나쳤다)."""
    assert modules_in("from ..service import services\nfrom .. import reference\nimport json\n", FLOWS_PACKAGE) == {
        "esgapi.inventory.service",
        "esgapi.inventory",
        "esgapi.inventory.reference",
        "json",
    }
    assert modules_in("from . import registration\n", FLOWS_PACKAGE) == {
        "esgapi.inventory.flows",
        "esgapi.inventory.flows.registration",
    }
    assert modules_in("from ...reference import calc\n", FLOWS_PACKAGE) == {"esgapi.reference"}


def test_another_app_registry_does_not_register_again() -> None:
    before = (REGISTRY.defaults(), REGISTRY.flows_of("inventory.scope12"), REGISTRY.flows_of("inventory.scope3"))
    Apps(list(settings.INSTALLED_APPS))
    with isolate_apps("esgapi.inventory"):
        pass
    after = (REGISTRY.defaults(), REGISTRY.flows_of("inventory.scope12"), REGISTRY.flows_of("inventory.scope3"))
    assert after == before
