"""가져오기(`manage.py import_factors`)를 진짜 DB 로 잰다. 업무 층: 주인 역할, 테스트마다 되돌린다.

행 수는 ORM 으로 센다. 이 층의 연결은 주인 역할이라 그것이 실제 행 수(분모)다.
★ 「앱 역할로 부르면 not_owner」 는 여기서 잴 수 없다(이 층은 주인이다). tests/security/test_reference.py 가 잰다.
"""

import json
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from esgapi.reference.models import FactorRecordRow, FactorScope3CategoryRow, MappingRow, SourceRow
from esgapi.reference.service.selectors import reference as selectors
from esgapi.reference.tests.helpers import ALL_RECORDS, DATA, MAPPING

pytestmark = pytest.mark.django_db

# esg-lab `data/factors/SUMMARY.md` 의 출처별 건수 가운데 사본에 든 여섯(지침 560 + GIR 40 = 600).
SUMMARY = {
    "kr-ets-byl12": 108,
    "kr-ets-byl11": 55,
    "kr-ets-byl10": 385,
    "kr-ets-byl06": 12,
    "gir-2025": 32,
    "gir-2024": 8,
}


def counts() -> tuple[int, int, int, int]:
    """(출처, 낱줄, 범주 연결, 대응표)"""
    return (
        SourceRow.objects.count(),
        FactorRecordRow.objects.count(),
        FactorScope3CategoryRow.objects.count(),
        MappingRow.objects.count(),
    )


def run(*args: str) -> str:
    out = StringIO()
    call_command("import_factors", *args, stdout=out)
    return out.getvalue()


def packaged_lines() -> list[str]:
    return DATA.joinpath("factors.kr.jsonl").read_text(encoding="utf-8").splitlines()


def variant(index: int, **patch: Any) -> dict[str, Any]:
    """사본의 한 줄을 베껴 칸을 바꾼 가상 낱줄(synthetic). 실제 값이 아니다."""
    record: dict[str, Any] = json.loads(packaged_lines()[index])
    return {**record, **patch, "synthetic": True}


def of_source(source_id: str, key: str, license_status: str, **patch: Any) -> dict[str, Any]:
    """가짜 출처의 가상 낱줄. 이용 조건 상태를 고를 수 있다(사본에는 disputed 가 없다)."""
    base = variant(0)
    return {
        **base,
        "id": f"{source_id}:{key}",
        "source": {**base["source"], "id": source_id, "name": f"synthetic 출처 {source_id}"},
        "license": {"name": "synthetic 조건", "url": "https://example.invalid/license", "note": "synthetic: 테스트용"},
        "license_status": license_status,
        **patch,
    }


def write(path: Path, records: list[dict[str, Any]], *, with_packaged: bool = False) -> str:
    lines = packaged_lines() if with_packaged else []
    lines += [json.dumps(record, ensure_ascii=False) for record in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


# ── 패키지 사본 ───────────────────────────────────────────────────────


def test_the_packaged_copy_imports_600_rows_matching_the_summary() -> None:
    assert counts() == (0, 0, 0, 0)
    out = run()
    assert dict(Counter(FactorRecordRow.objects.values_list("source_id", flat=True))) == SUMMARY
    # 출처 일곱 = 낱줄이 있는 여섯 + 대응표만 가리키는 kr-ets-byl05. 사본에는 Scope 3 낱줄이 없다(연결 0).
    assert counts() == (7, 600, 0, 1)
    assert "읽은 줄 600 = 쓴 줄 600 + 걸러 낸 줄 0" in out
    assert "license_status 별 쓴 줄: unverified 600" in out
    assert "걸린 시간" in out
    # 사본은 전부 unverified 다(GIR 공표, 고시 별표). 그 상태와 덧붙인 말이 jsonl 에서 그대로 왔다.
    assert set(SourceRow.objects.values_list("license_status", flat=True)) == {"unverified"}
    gir = SourceRow.objects.get(id="gir-2025")
    assert gir.license_url == "https://www.gir.go.kr/home/index.do?menuId=43"
    assert gir.license_note is not None and "담당자와 사전 협의 후 이용" in gir.license_note


def test_importing_twice_keeps_the_row_counts() -> None:
    run()
    first = counts()
    created = dict(FactorRecordRow.objects.values_list("id", "created_at"))
    run()
    assert counts() == first == (7, 600, 0, 1)
    # 새로 만든 것이 아니라 같은 행을 다시 쓴 것이다.
    assert dict(FactorRecordRow.objects.values_list("id", "created_at")) == created


def test_rows_read_back_equal_the_file() -> None:
    """DB 를 거친 낱줄과 대응표가 파일에서 바로 읽은 것과 같다(조립이 받는 꼴로 견준다)."""
    run()
    read_back = selectors.records_for_assembly(SUMMARY)
    assert read_back == sorted(ALL_RECORDS, key=lambda record: record.id)
    found = selectors.current_mapping()
    assert isinstance(found, selectors.MappingFound)
    assert found.mapping == MAPPING
    # 값 없는 낱줄(별표 11 의 1건)은 값 상태와 원문 표기가 남는다.
    empty = FactorRecordRow.objects.exclude(value_status="ok")
    assert [(row.value, row.value_raw, row.value_status) for row in empty] == [(None, "-", "not_available_in_source")]


def test_the_mapping_only_source_is_listed_as_unverified_with_no_records() -> None:
    run()
    by_id = {source.id: source for source in selectors.list_sources()}
    assert len(by_id) == 7
    byl05 = by_id["kr-ets-byl05"]
    assert (byl05.record_count, byl05.license_status, byl05.license_name, byl05.license_note) == (
        0,
        "unverified",
        "",
        None,
    )
    assert byl05.version == MAPPING.guideline.version
    assert {s.id: s.record_count for s in by_id.values() if s.record_count} == SUMMARY


# ── 이용 조건으로 거르기 ──────────────────────────────────────────────


def test_disputed_rows_are_left_out_by_default(tmp_path: Path) -> None:
    """★ 기본(--include-license 를 주지 않음)에서는 disputed 인 낱줄이 한 줄도 들어오지 않는다. 출처 행도 없다."""
    disputed = [of_source("synthetic-disputed", f"row{n}", "disputed") for n in range(3)]
    path = write(tmp_path / "factors.jsonl", disputed, with_packaged=True)
    out = run(path)
    assert FactorRecordRow.objects.count() == 600  # 분모: 파일에는 603줄이 있다
    assert FactorRecordRow.objects.filter(source__license_status="disputed").count() == 0
    assert not SourceRow.objects.filter(id="synthetic-disputed").exists()
    assert "읽은 줄 603 = 쓴 줄 600 + 걸러 낸 줄 3" in out
    assert "synthetic-disputed\t3" in out


def test_disputed_rows_come_in_only_when_named(tmp_path: Path) -> None:
    disputed = [of_source("synthetic-disputed", f"row{n}", "disputed") for n in range(3)]
    path = write(tmp_path / "factors.jsonl", disputed, with_packaged=True)
    run(path, "--include-license", "ok,unverified,disputed")
    assert FactorRecordRow.objects.count() == 603
    source = SourceRow.objects.get(id="synthetic-disputed")
    assert (source.license_status, source.license_note) == ("disputed", "synthetic: 테스트용")
    # 기본으로 다시 돌리면 이번 파일의 그 출처에서 쓰지 않은 행(include 밖)은 지운다(D7).
    out = run(path)
    assert FactorRecordRow.objects.filter(source_id="synthetic-disputed").count() == 0
    assert FactorRecordRow.objects.count() == 600
    assert "synthetic-disputed\t3" in out.split("출처별 지운 줄")[1]


def test_only_the_named_statuses_are_written(tmp_path: Path) -> None:
    rows = [of_source("synthetic-ok", "a", "ok"), of_source("synthetic-unverified", "a", "unverified")]
    path = write(tmp_path / "factors.jsonl", rows)
    run(path, "--include-license", "ok")
    assert list(FactorRecordRow.objects.values_list("id", flat=True)) == ["synthetic-ok:a"]
    assert list(SourceRow.objects.values_list("id", flat=True)) == ["synthetic-ok"]


def test_an_unknown_status_name_is_rejected() -> None:
    with pytest.raises(CommandError, match=r"^invalid_license_list: "):
        run("--include-license", "ok,public")
    assert counts() == (0, 0, 0, 0)


# ── 꼴이 틀리면 아무것도 쓰지 않는다 ──────────────────────────────────


def test_one_malformed_line_writes_nothing(tmp_path: Path) -> None:
    """맨 끝 줄 하나가 틀렸다. 앞의 600줄은 멀쩡하지만 한 줄도 남지 않는다(트랜잭션 하나)."""
    broken = variant(0, id="kr-ets-byl12:synthetic-broken")
    del broken["value_raw"]
    path = write(tmp_path / "factors.jsonl", [broken], with_packaged=True)
    with pytest.raises(CommandError, match=r"^invalid_shape: 601행: value_raw"):
        run(path)
    assert counts() == (0, 0, 0, 0)


def test_a_malformed_line_of_an_excluded_source_also_stops_everything(tmp_path: Path) -> None:
    """걸러 낼 출처(disputed)의 줄이어도 꼴은 본다."""
    broken = of_source("synthetic-disputed", "row", "disputed", schema_version="0.2")
    path = write(tmp_path / "factors.jsonl", [broken], with_packaged=True)
    with pytest.raises(CommandError, match=r"^invalid_shape: 601행: schema_version"):
        run(path)
    assert counts() == (0, 0, 0, 0)


def test_duplicate_ids_and_inconsistent_source_blocks_write_nothing(tmp_path: Path) -> None:
    twin = json.loads(packaged_lines()[0])
    with pytest.raises(CommandError, match=r"^duplicate_id: 601행"):
        run(write(tmp_path / "dup.jsonl", [twin], with_packaged=True))
    assert counts() == (0, 0, 0, 0)
    other = variant(0, id="gir-2025:synthetic-other-version")
    other["source"] = {**other["source"], "version": "synthetic 다른 공고"}
    with pytest.raises(CommandError, match=r"^inconsistent_source: 601행: 출처 gir-2025 .*\(version\)"):
        run(write(tmp_path / "other.jsonl", [other], with_packaged=True))
    assert counts() == (0, 0, 0, 0)


def test_empty_and_missing_files_and_a_bad_mapping_write_nothing(tmp_path: Path) -> None:
    (tmp_path / "empty.jsonl").write_text("\n", encoding="utf-8")
    with pytest.raises(CommandError, match=r"^empty: "):
        run(str(tmp_path / "empty.jsonl"))
    with pytest.raises(CommandError, match=r"^unreadable_file: FileNotFoundError"):
        run(str(tmp_path / "none.jsonl"))
    body: dict[str, Any] = json.loads(DATA.joinpath("mappings.kr-ets.json").read_text(encoding="utf-8"))
    del body["sectors"]
    (tmp_path / "mapping.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    path = write(tmp_path / "factors.jsonl", [], with_packaged=True)
    with pytest.raises(CommandError, match=r"^mapping_invalid: .*sectors"):
        run(path, "--mapping", str(tmp_path / "mapping.json"))
    # 낱줄 600 은 멀쩡했지만 대응표가 틀려 같이 되돌려졌다.
    assert counts() == (0, 0, 0, 0)


# ── upsert ────────────────────────────────────────────────────────────


def test_a_changed_line_overwrites_its_row(tmp_path: Path) -> None:
    """같은 id 의 줄은 덮어쓴다."""
    run()
    changed = variant(0, value=0.5, value_raw="0.5")
    lines = packaged_lines()
    lines[0] = json.dumps(changed, ensure_ascii=False)
    path = tmp_path / "all.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run(str(path))
    row = FactorRecordRow.objects.get(id=changed["id"])
    assert (row.value_raw, row.synthetic) == ("0.5", True)
    assert FactorRecordRow.objects.count() == 600
    # --mapping 없이 파일을 주면 대응표는 건드리지 않는다.
    assert MappingRow.objects.count() == 1


def test_scope3_rows_get_one_link_row_per_category(tmp_path: Path) -> None:
    scope3 = of_source(
        "synthetic-ok",
        "s3",
        "ok",
        scope="scope3",
        scope3_categories=[1, 2],
        scope3_mapping_basis="synthetic: 테스트용 후보",
    )
    path = write(tmp_path / "factors.jsonl", [scope3])
    out = run(path)
    assert "쓴 줄의 Scope 3 범주 연결: 2" in out
    run(path)
    assert list(FactorScope3CategoryRow.objects.values_list("record_id", "category").order_by("category")) == [
        ("synthetic-ok:s3", 1),
        ("synthetic-ok:s3", 2),
    ]


# ── 바뀐·빠진 행(D7) ──────────────────────────────────────────────────


def test_an_ok_row_turned_disputed_is_removed_by_the_next_import(tmp_path: Path) -> None:
    """★ ok 로 들어간 행이 다음 파일에서 disputed(include 밖)로 바뀌면 DB 에 ok 로 남지 않는다."""
    first = [of_source("synthetic-ok", "a", "ok"), of_source("synthetic-ok", "b", "ok")]
    run(write(tmp_path / "first.jsonl", first))
    assert FactorRecordRow.objects.filter(source_id="synthetic-ok").count() == 2
    # 같은 출처의 블록은 줄마다 같아야 하므로 다른 출처로 옮긴 것이 아니라 그 출처 전체의 상태가 바뀐다.
    second = [of_source("synthetic-ok", "a", "disputed"), of_source("synthetic-ok", "b", "disputed")]
    out = run(write(tmp_path / "second.jsonl", second))
    assert FactorRecordRow.objects.filter(source_id="synthetic-ok").count() == 0
    assert "출처별 지운 줄" in out
    assert "synthetic-ok\t2" in out.split("출처별 지운 줄")[1]


def test_a_row_missing_from_the_next_file_is_removed_with_its_links(tmp_path: Path) -> None:
    """★ 파일에서 빠진 행은 지운다(그 행의 Scope 3 범주 연결도). 남은 행은 그대로다."""
    keep = of_source("synthetic-ok", "keep", "ok")
    gone = of_source(
        "synthetic-ok", "gone", "ok", scope="scope3", scope3_categories=[1], scope3_mapping_basis="synthetic: 후보"
    )
    run(write(tmp_path / "first.jsonl", [keep, gone]))
    assert FactorScope3CategoryRow.objects.filter(record_id="synthetic-ok:gone").count() == 1
    out = run(write(tmp_path / "second.jsonl", [keep]))
    assert list(FactorRecordRow.objects.filter(source_id="synthetic-ok").values_list("id", flat=True)) == [
        "synthetic-ok:keep"
    ]
    assert FactorScope3CategoryRow.objects.filter(record_id="synthetic-ok:gone").count() == 0
    assert "synthetic-ok\t1" in out.split("출처별 지운 줄")[1]


def test_sources_not_in_the_file_are_left_alone(tmp_path: Path) -> None:
    """이번 파일에 나오지 않은 출처의 행은 건드리지 않는다(지운 줄 0)."""
    run()
    out = run(write(tmp_path / "other.jsonl", [of_source("synthetic-ok", "a", "ok")]))
    assert FactorRecordRow.objects.count() == 601
    for source_id, count in SUMMARY.items():
        assert FactorRecordRow.objects.filter(source_id=source_id).count() == count
    assert "출처별 지운 줄" in out
    assert out.split("출처별 지운 줄")[1].splitlines()[1] == "  (없음)"
