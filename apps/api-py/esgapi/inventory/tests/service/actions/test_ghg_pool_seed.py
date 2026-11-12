"""씨앗 action ⓕ seed_pool 과 명령 seed_ghg_pool(밴드 K1b-2a ④ — 발주서 §3-5). 업무 층, 주인 역할 연결.

지어낸 낱줄(actions.load_seed_records 를 바꿔 끼움)로: 값 = value_raw · GWP = 고른 세트(gwp-sets.json 에서 읽어 견줌) ·
seedRecordIds · 두 번 → 0 더함 · 고친 씨앗 계수 그대로 · 없는 id 건너뜀 · --dry-run 0. 그리고 **실제 씨앗 파일**을
패키지 적재본(import_factors)에 돌려 낱줄이 전부 있고 99 묶음이 다 들어가는지. 계수·GWP 숫자를 시험에 적지 않는다.
"""

import copy
import io
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command

from esgapi.inventory.models import GhgFactor, GhgFactorGas, GhgFactorVersion, GhgIndexNode
from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.utils.ghg_pool import FactorView, SeedRecord
from esgapi.inventory.tests.ghg_pool_support import ADMIN, CUSTOMER, counts, draft
from esgapi.organization.service.selectors.facility_codes import selectable_codes

pytestmark = pytest.mark.django_db

DATA = Path(__file__).resolve().parents[3] / "data"
GWP_SETS = {row["id"]: row["values"] for row in json.loads((DATA / "gwp-sets.json").read_text())["gwpSets"]}
SET = "kr-ets-decree-annex2"

RECORDS = {
    "s:co2": SeedRecord("s:co2", "1,234.5", "kgCO2", "TJ", "CO2"),
    "s:ch4": SeedRecord("s:ch4", "2.5", "kgCH4", "TJ", "CH4"),
    "s:n2o": SeedRecord("s:n2o", "0.25", "kgN2O", "TJ", "N2O"),
    "s:ncv": SeedRecord("s:ncv", "12.34", "MJ", "L", "none"),
    "s:co2-kl": SeedRecord("s:co2-kl", "1", "kgCO2", "kL", "CO2"),
    "s:co2-l": SeedRecord("s:co2-l", "1,234.5", "kgCO2", "L", "CO2"),
    "s:ch4-l": SeedRecord("s:ch4-l", "2.5", "kgCH4", "L", "CH4"),
    "s:n2o-l": SeedRecord("s:n2o-l", "0.25", "kgN2O", "L", "N2O"),
}


def factor_spec(key: str, gases: dict[str, str], **fields: Any) -> dict[str, Any]:
    return {
        "key": key,
        "name": f"계수 {key}",
        "source": "지어낸 출처",
        "baseYear": 2024,
        "baseYearBasis": "지어냄",
        "tier": 2,
        "countryCode": "KR",
        "industryCode": "other",
        "gases": gases,
        **fields,
    }


GOOD = {"CO2": "s:co2", "CH4": "s:ch4", "N2O": "s:n2o"}
PLAN: dict[str, Any] = {
    "sources": ["s"],
    "tree": [
        {
            "key": "scope1",
            "name": "범위 가",
            "children": [
                {
                    "key": "kind",
                    "name": "유형 가",
                    "children": [
                        {
                            "key": "act",
                            "name": "활동 가",
                            "facilities": [
                                {
                                    "code": "지어낸 연료",
                                    "unit": {"kind": "volume", "unit": "L"},
                                    "factors": [
                                        factor_spec("first", GOOD, ncv="s:ncv"),
                                        factor_spec("second", {"CO2": "s:co2-l", "CH4": "s:ch4-l", "N2O": "s:n2o-l"}),
                                        factor_spec("mixed", {**GOOD, "CO2": "s:co2-kl"}),  # 분모 다름 → 건너뜀
                                        factor_spec("gone", {**GOOD, "N2O": "s:none"}),  # 없는 낱줄 → 건너뜀
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture
def fake_records(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(source_ids: list[str]) -> dict[str, SeedRecord]:
        return dict(RECORDS)

    monkeypatch.setattr(actions, "load_seed_records", fake)


def seed(**fields: Any) -> actions.SeedReport:
    report = actions.seed_pool(actor_kind=ADMIN, plan=PLAN, gwp_set_id=fields.pop("gwp_set_id", SET), **fields)
    assert isinstance(report, actions.SeedReport), report
    return report


@pytest.mark.usefixtures("fake_records")
def test_the_seed_takes_value_raw_and_the_chosen_gwp_set() -> None:
    report = seed()
    assert (report.made, report.existing) == (
        {"node": 3, "facility": 1, "factor": 2, "code": 1},
        {"node": 0, "facility": 0, "factor": 0},
    )
    assert sorted(key for key, _ in report.skipped) == [
        "scope1/kind/act/지어낸 연료#gone",
        "scope1/kind/act/지어낸 연료#mixed",
    ]
    first = GhgFactor.objects.get(seed_key="scope1/kind/act/지어낸 연료#first")
    assert first.is_default  # 파일의 첫 줄이 기본
    version = GhgFactorVersion.objects.get(factor=first)
    assert (version.seed_record_ids, version.seed_gwp_set_id, version.factor_unit) == (
        ["s:co2", "s:ch4", "s:n2o", "s:ncv"],
        SET,
        "kg/TJ",
    )
    assert version.ncv == Decimal("12.34")
    gases = {row.gas: row for row in GhgFactorGas.objects.filter(factor_version=version)}
    assert gases["CO2"].factor == Decimal("1234.5")  # value_raw 의 쉼표를 걷은 값
    assert {gas: gases[gas].gwp for gas in ("CO2", "CH4", "N2O")} == {
        gas: Decimal(GWP_SETS[SET][gas]) for gas in ("CO2", "CH4", "N2O")
    }  # GWP = 고른 세트(파일에서 읽어 견줌)
    assert [gas for gas, row in gases.items() if not row.enabled] == ["HFCs", "PFCs", "SF6", "NF3"]
    assert [code.name for code in selectable_codes()] == ["지어낸 연료"]  # 시설 코드는 이름으로 만든다


@pytest.mark.usefixtures("fake_records")
def test_the_other_gwp_set_is_taken_when_asked() -> None:
    other = "ipcc-ar5-100y-kr-nid-2025"
    seed(gwp_set_id=other)
    gas = GhgFactorGas.objects.get(factor_version__factor__seed_key="scope1/kind/act/지어낸 연료#second", gas="CH4")
    assert gas.gwp == Decimal(GWP_SETS[other]["CH4"])
    assert actions.seed_pool(actor_kind=ADMIN, plan=PLAN, gwp_set_id="no-such-set") == actions.Invalid(
        {"gwpSet": "gwp-sets.json 에 no-such-set 가 없다"}
    )


@pytest.mark.usefixtures("fake_records")
def test_seeding_twice_adds_nothing_and_keeps_what_the_operator_changed() -> None:
    seed()
    second = GhgFactor.objects.get(seed_key="scope1/kind/act/지어낸 연료#second")
    saved = actions.save_factor(actor_kind=ADMIN, factor_id=second.pk, draft=draft(name="관리자가 고침"))
    assert isinstance(saved, FactorView) and saved.version == 2
    before = counts()
    report = seed()
    assert (report.made, report.existing) == (
        {"node": 0, "facility": 0, "factor": 0, "code": 0},
        {"node": 3, "facility": 1, "factor": 2},
    )
    assert len(report.skipped) == 2  # 늘 건너뛰는 둘(분모 다름·없는 낱줄)만
    assert counts() == before
    second.refresh_from_db()
    assert second.current_version == 2  # 고친 씨앗 계수 그대로
    assert GhgFactorVersion.objects.get(factor=second, version=2).name == "관리자가 고침"


@pytest.mark.usefixtures("fake_records")
def test_a_dry_run_leaves_nothing() -> None:
    report = seed(dry_run=True)
    assert report.made["factor"] == 2
    assert counts() == (0, 0, 0, 0)
    assert selectable_codes() == []


def test_a_customer_kind_cannot_seed() -> None:
    assert actions.seed_pool(actor_kind=CUSTOMER, plan=PLAN, gwp_set_id=SET) == actions.Forbidden(
        "inventory_admin_ghg_nodes_create"
    )
    assert counts() == (0, 0, 0, 0)


def test_the_real_seed_file_finds_every_record_in_the_packaged_load_and_seeds_all() -> None:
    """실제 씨앗 파일 × 패키지 적재본(import_factors 인자 없이): 낱줄 id 가 전부 있고, 99 묶음이 다 들어간다."""
    call_command("import_factors", stdout=io.StringIO())
    plan = json.loads((DATA / "ghg-pool-seed.json").read_text())
    loaded = actions.load_seed_records(plan["sources"])
    wanted = {
        record_id
        for scope in plan["tree"]
        for kind in scope["children"]
        for act in kind["children"]
        for leaf in act["facilities"]
        for spec in leaf["factors"]
        for record_id in [*spec["gases"].values(), *([spec["ncv"]] if "ncv" in spec else [])]
    }
    assert wanted - set(loaded) == set()  # 적재본에 전부 있다
    out = io.StringIO()
    call_command("seed_ghg_pool", stdout=out)
    assert "건너뜀 0" in out.getvalue(), out.getvalue()
    # S12S1(MARC-ENT-676): 범위 2 + 유형 2 + 연료 활동 22 + 전력 활동 1 + 설비 잎 23 = 50
    # (앞 31 — 활동 셋이 연료 잎 22 를 품음)
    assert (GhgIndexNode.objects.count(), GhgFactor.objects.count()) == (50, 99)
    assert GhgFactorGas.objects.filter(enabled=True).count() == 99 * 3
    again = io.StringIO()
    call_command("seed_ghg_pool", "--dry-run", stdout=again)
    assert "계수 만듦 0·있음 99" in again.getvalue(), again.getvalue()


@pytest.mark.usefixtures("fake_records")
def test_a_deleted_seed_node_skips_everything_below_with_one_line() -> None:
    """R9(K1b-2b ⑤ — MARC-ISSUE-430): 관리자가 지운 씨앗 활동 아래에 씨앗이 새 잎을 들고 와도 만들지 않는다.
    보고는 「지운 씨앗 노드 — 아래 건너뜀」 한 줄(아래 하나하나의 「만들지 못했다: NotFound()」 줄 0)."""
    seed()
    act = GhgIndexNode.objects.get(seed_key="scope1/kind/act")
    leaf = GhgIndexNode.objects.get(seed_key="scope1/kind/act/지어낸 연료")
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[act.pk, leaf.pk]) == 2  # 잎·활동을 아래부터
    more = copy.deepcopy(PLAN)
    facilities = more["tree"][0]["children"][0]["children"][0]["facilities"]
    facilities.append(
        {"code": "새 연료", "unit": {"kind": "volume", "unit": "L"}, "factors": [factor_spec("new", GOOD)]}
    )
    before = counts()
    report = actions.seed_pool(actor_kind=ADMIN, plan=more, gwp_set_id=SET)
    assert isinstance(report, actions.SeedReport), report
    assert report.skipped == [("scope1/kind/act", actions.DELETED_SEED_NODE)]
    assert not [why for _, why in report.skipped if "NotFound" in why]
    assert (report.made, report.existing) == (
        {"node": 0, "facility": 0, "factor": 0, "code": 0},
        {"node": 2, "facility": 0, "factor": 0},  # 범위·유형만 「이미 있음」
    )
    assert counts() == before  # 새 잎·계수 0
    assert not GhgIndexNode.objects.filter(seed_key="scope1/kind/act/새 연료").exists()


@pytest.mark.usefixtures("fake_records")
def test_a_deleted_seed_leaf_skips_its_factors_with_one_line() -> None:
    seed()
    leaf = GhgIndexNode.objects.get(seed_key="scope1/kind/act/지어낸 연료")
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[leaf.pk]) == 1
    before = counts()
    report = seed()
    assert report.skipped == [("scope1/kind/act/지어낸 연료", actions.DELETED_SEED_NODE)]  # 그 아래 계수 줄 0
    assert counts() == before
