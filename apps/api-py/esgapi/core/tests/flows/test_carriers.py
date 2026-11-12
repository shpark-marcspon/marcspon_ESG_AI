"""carrier 등록부(core/flows/carriers.py — RX1a)를 순수 층에서 잰다: 두 번 달기 거절, 없는 모듈은 None, NO_ROWS 는
받은 값을 그대로 돌려주고 행 0, 지도(IdMap) 밖 id 는 UnknownId, 전역 CARRIERS 는 이 밴드 뒤 0.
RX1b: 판 이름 지도(ai_setting_name), 공통 판 carrier SettingCarrier(가짜 판 dataclass·가짜 읽기·넣기 함수 —
모듈 import 0).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from esgapi.core.flows.carriers import (
    CARRIERS,
    NO_ROWS,
    CarrierRefused,
    CarrierRegistry,
    CarrierRegistryError,
    IdMap,
    Rewritten,
    SettingCarrier,
    UnknownId,
)


def test_a_module_gets_one_carrier() -> None:
    registry = CarrierRegistry()
    registry.register("probe", NO_ROWS)
    assert registry.get("probe") is NO_ROWS
    assert registry.get("other") is None
    assert registry.modules() == ("probe",)
    with pytest.raises(CarrierRegistryError):
        registry.register("probe", NO_ROWS)  # 같은 객체여도


def test_no_rows_carries_nothing_and_rewrites_nothing() -> None:
    ids = IdMap(run={1: 10}, document={}, ai_setting={})
    assert NO_ROWS.export_rows(1, [1], {1: {}}) == {}
    assert NO_ROWS.referenced_runs({"retry": {"fromRunId": 1}}) == ()
    rewritten = NO_ROWS.rewrite(
        options={"a": 1},
        versions={"aiSettingId": 7},
        results=[("x.result@1", {"b": 2})],
        steps=[("s", {"c": 3})],
        partials=[("s", None)],
        ids=ids,
    )
    assert rewritten == Rewritten(
        options={"a": 1},
        versions={"aiSettingId": 7},
        results=(("x.result@1", {"b": 2}),),
        steps=(("s", {"c": 3}),),
        partials=(("s", None),),
    )
    assert NO_ROWS.columns() == {}
    assert NO_ROWS.import_settings(1, 2, {}) == {}
    assert NO_ROWS.import_rows(1, 2, {}, ids) is None
    assert NO_ROWS.id_fields() == {}


def test_the_map_refuses_ids_outside_the_bundle() -> None:
    ids = IdMap(run={1: 10, 2: 11}, document={5: 50}, ai_setting={7: 70})
    assert (ids.run_id(2), ids.document_id(5), ids.ai_setting_id(7)) == (11, 50, 70)
    for lookup in (lambda: ids.run_id(3), lambda: ids.document_id(1), lambda: ids.ai_setting_id(1)):
        with pytest.raises(UnknownId):
            lookup()


def test_no_module_carries_rows_yet() -> None:
    # 분모: 모듈 다섯(+ inventory.scope3 NO_ROWS — S3K1)의 carrier 는 AppConfig.ready() 가 단다(RX1b). 끼움 없는 모듈 0.
    assert sorted(CARRIERS.modules()) == ["dataverify", "greenwash", "inventory.scope3", "materiality", "translation"]


def test_the_name_map_refuses_settings_outside_the_bundle() -> None:
    ids = IdMap(run={}, document={}, ai_setting={7: 70}, ai_setting_name={7: "v3"})
    assert ids.ai_setting_name_of(7) == "v3"
    with pytest.raises(UnknownId):
        ids.ai_setting_name_of(8)
    assert IdMap(run={}, document={}, ai_setting={}).ai_setting_name == {}


# ── SettingCarrier(RX1b Qb5) ─────────────────────────────────────────

WHEN = datetime(2026, 9, 1, tzinfo=UTC)


@dataclass(frozen=True)
class FakeSetting:
    id: int
    name: str
    title: str
    memo: str
    model_settings: dict[str, object]
    created_by_user_id: int
    created_at: datetime
    applied: bool
    applied_at: datetime | None


class FakeSettings:
    """판 표 대신 메모리. read 는 그 회사의 판만, insert 는 다음 v<n> 으로 넣고 (id, 이름) — conflict 면 다시 시도
    다함."""

    def __init__(self, *, conflict: bool = False) -> None:
        self.rows = {
            (1, 7): FakeSetting(7, "v2", "가상 판", "메모", {"m": 1}, 5, WHEN, True, WHEN),
            (2, 9): FakeSetting(9, "v1", "남의 판", "", {}, 6, WHEN, False, None),
        }
        self.reads: list[int] = []
        self.inserted: list[tuple[int, dict[str, object], int]] = []
        self.conflict = conflict

    def read(self, *, company_id: int, setting_id: int) -> FakeSetting | None:
        self.reads.append(setting_id)
        return self.rows.get((company_id, setting_id))

    def insert(self, company_id: int, *, row: dict[str, object], user_id: int) -> tuple[int, str] | None:
        if self.conflict:
            return None
        self.inserted.append((company_id, row, user_id))
        return (100 + len(self.inserted), f"v{4 + len(self.inserted)}")


def a_carrier(fake: FakeSettings) -> SettingCarrier:
    return SettingCarrier(table="fake_settings", shape=FakeSetting, read_settings=fake.read, insert_setting=fake.insert)


def test_setting_rows_are_read_once_per_setting_and_default_runs_carry_none() -> None:
    fake = FakeSettings()
    rows = a_carrier(fake).export_rows(
        1, [1, 2, 3], {1: {"aiSettingId": 7}, 2: {"aiSettingId": 7}, 3: {"aiSettingId": None}}
    )
    assert rows == {
        "fake_settings": [
            {"oldId": 7, "name": "v2", "title": "가상 판", "memo": "메모", "model_settings": {"m": 1}},
        ]
    }  # 사람·때·적용 칸 0(SETTING_DROP), 같은 판은 한 번(Qb2)
    assert fake.reads == [7]
    assert a_carrier(fake).export_rows(1, [3], {3: {"aiSettingId": None}}) == {"fake_settings": []}


def test_a_setting_of_another_company_is_refused_on_export() -> None:
    with pytest.raises(CarrierRefused):
        a_carrier(FakeSettings()).export_rows(1, [1], {1: {"aiSettingId": 9}})


def test_setting_columns_are_the_shape_without_people_times_or_applied() -> None:
    assert a_carrier(FakeSettings()).columns() == {
        "fake_settings": {"oldId": "id", "name": "plain", "title": "plain", "memo": "plain", "model_settings": "plain"}
    }
    assert a_carrier(FakeSettings()).id_fields() == {
        "fake_settings": ("oldId",),
        "versions": ("aiSettingId", "aiSetting"),
    }


def test_settings_are_inserted_once_with_the_carried_columns() -> None:
    fake = FakeSettings()
    row: dict[str, object] = {"oldId": 7, "name": "v2", "title": "가상 판", "memo": "메모", "model_settings": {"m": 1}}
    made = a_carrier(fake).import_settings(3, 44, {"fake_settings": [row]})
    assert made == {7: (101, "v5")}
    assert fake.inserted == [(3, {"name": "v2", "title": "가상 판", "memo": "메모", "model_settings": {"m": 1}}, 44)]


@pytest.mark.parametrize("rows", [[{"oldId": 7}, {"oldId": 7}], [{"oldId": "7"}], [{"oldId": 0}]])
def test_a_bad_or_doubled_setting_id_is_refused(rows: list[dict[str, object]]) -> None:
    filled: list[dict[str, object]] = [
        {"name": "v", "title": "t", "memo": "", "model_settings": {}, **row} for row in rows
    ]
    with pytest.raises(CarrierRefused):
        a_carrier(FakeSettings()).import_settings(3, 44, {"fake_settings": filled})


def test_an_exhausted_name_retry_is_refused() -> None:
    row: dict[str, object] = {"oldId": 7, "name": "v2", "title": "t", "memo": "", "model_settings": {}}
    with pytest.raises(CarrierRefused):
        a_carrier(FakeSettings(conflict=True)).import_settings(3, 44, {"fake_settings": [row]})


def test_rewrite_renames_only_a_saved_setting() -> None:
    carrier = a_carrier(FakeSettings())
    ids = IdMap(run={}, document={}, ai_setting={7: 101}, ai_setting_name={7: "v5"})
    saved = {"aiSettingId": 7, "aiSetting": "v2", "promptsSha256": "s"}
    found = carrier.rewrite(
        options={"o": 1}, versions=saved, results=[], steps=[("a", {"x": 7})], partials=[("a", None)], ids=ids
    )
    assert found.versions == {"aiSettingId": 7, "aiSetting": "v5", "promptsSha256": "s"}  # aiSettingId 는 runbundle 몫
    assert (found.options, found.steps, found.partials) == ({"o": 1}, (("a", {"x": 7}),), (("a", None),))
    default = {"aiSettingId": None, "aiSetting": "기본 설정"}
    assert carrier.rewrite(options={}, versions=default, results=[], steps=[], partials=[], ids=ids).versions == default
    with pytest.raises(UnknownId):  # 다른 모듈의 판 id(이 모듈 지도 밖)
        carrier.rewrite(
            options={}, versions={"aiSettingId": 8, "aiSetting": "v1"}, results=[], steps=[], partials=[], ids=ids
        )
