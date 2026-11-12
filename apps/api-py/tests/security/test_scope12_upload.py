"""Scope 1·2 일괄 올리기(S12b-2 ③ — 결정 MARC-ENT-472)의 보안 층. 앱 역할, 진짜 커밋. 6d 조건 (마)(바)(자).

  ⓐ A 의 파일에 B 의 사업장 이름 → 422, 없는 이름과 같은 바이트 · B 의 행·값·히스토리·사건 0 바뀜 · 글에 B 글자 0
  ⓑ A 가 고르지 않은 풀 잎·없는 잎 → 같은 422 바이트(숨긴 잎의 같은 글은 업무 층 시험이 잰다)
  ⓒ 운영 관리자: 회사 둘 400 · 쓰기 0 / 회사 하나 → 그 회사에만 씀
  ⓓ 같은 바이트 두 번 → 두 번째는 표마다 쓰기 0
메서드마다 양성 대조(A 의 유효 파일이 2xx 이고 실제로 쓴다)를 둔다. 오류 글에는 어느 회사의 이름도 싣지 않으므로,
「A 이름은 보임」의 양성 대조는 A 가 내려받은 양식(그 파일을 고쳐 올린다)에 A 사업장이 있음으로 잰다.
이름·값은 지어낸 것이다.
"""

import io
from collections.abc import Iterator
from typing import Any, Final

import psycopg
import pytest
from django.test import Client
from openpyxl import load_workbook

from tests.security.seed import add_company
from tests.security.test_entries import entries_of, place
from tests.security.test_ghg_pool import CODES, POOL, one, seed
from tests.security.test_operator_company import customer_client, operator_client

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
YEAR: Final = 2025
ROOT: Final = f"/api/inventory/scope12/years/{YEAR}"
MEDIA: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
A_SITE: Final = "가 회사의 올리기 공장"
B_SITE: Final = "나 회사의 올리기 공장"
NOWHERE: Final = "어디에도 없는 올리기 공장"
FEB_COLUMN: Final = 10  # 월 시트 J = 2월
SITE_COLUMN: Final = 6
ID_COLUMN: Final = 1


@pytest.fixture(autouse=True)
def empty_pool(owner: Owner) -> Iterator[None]:
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")
    yield
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")


@pytest.fixture
def both(owner: Owner, companies: tuple[int, int]) -> dict[str, Any]:
    """같은 풀 잎·같은 코드 — A·B 에 사업장 하나씩(1월 1000 kg)."""
    a, b = companies
    ids = seed(owner)
    mine = place(owner, customer_client(a, "tenant-a"), a, ids["code"], ids["leaf"], A_SITE, "가 1호기")
    theirs = place(owner, customer_client(b, "tenant-b"), b, ids["code"], ids["leaf"], B_SITE, "나 7호기")
    return {**ids, "a": mine, "b": theirs}


def template(client: Client) -> bytes:
    response = client.get(f"{ROOT}/template")
    assert response.status_code == 200, response.content.decode(errors="replace")[:300]
    return response.content


def changed(data: bytes, *, value: object = 5, site: str | None = None, node: int | None = None) -> bytes:
    """A 양식 첫 줄(월 시트 2행)의 2월 칸에 값을 넣고, 사업장·ID 를 바꾼 바이트."""
    book = load_workbook(io.BytesIO(data))
    sheet = book["월"]
    assert sheet.cell(row=2, column=SITE_COLUMN).value == A_SITE  # 양성 대조: A 양식에 A 이름이 있다
    sheet.cell(row=2, column=FEB_COLUMN).value = value  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
    if site is not None:
        sheet.cell(row=2, column=SITE_COLUMN).value = site  # pyright: ignore[reportAttributeAccessIssue]
    if node is not None:
        sheet.cell(row=2, column=ID_COLUMN).value = node  # pyright: ignore[reportAttributeAccessIssue]
    saved = io.BytesIO()
    book.save(saved)
    return saved.getvalue()


def upload(client: Client, data: bytes) -> Any:
    return client.post(f"{ROOT}/uploads", data=data, content_type=MEDIA)


def traces(owner: Owner, company_id: int) -> list[list[tuple[Any, ...]]]:
    """그 회사의 입력 행·값·히스토리와 사건 기록(감사) 전부 — 0 씀 단언의 전·후."""
    events = owner.execute(
        "SELECT id, action, event, result FROM core_audit_events WHERE company_id = %s ORDER BY id", [company_id]
    ).fetchall()
    return [*entries_of(owner, company_id), events]


def sizes(owner: Owner, company_id: int) -> list[int]:
    return [len(part) for part in entries_of(owner, company_id)]


def test_a_foreign_site_name_is_refused_like_a_missing_one(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    theirs, mine = traces(owner, b), entries_of(owner, a)
    assert [len(part) for part in theirs[:3]] == [1, 1, 1]  # 분모: B 의 행·값·히스토리가 있다
    client = customer_client(a, "tenant-a")
    data = template(client)
    foreign = upload(client, changed(data, site=B_SITE))
    missing = upload(client, changed(data, site=NOWHERE))
    assert foreign.status_code == 422, foreign.content.decode()
    assert foreign.content == missing.content  # 남의 것과 없는 것이 같은 바이트
    assert B_SITE not in foreign.content.decode()
    assert (entries_of(owner, a), traces(owner, b)) == (mine, theirs)  # 양쪽 다 0 씀
    positive = upload(client, changed(data))
    assert positive.status_code == 200, positive.content.decode()  # 양성 대조: A 의 유효 파일은 쓴다
    assert sizes(owner, a) == [1, 2, 2]
    assert traces(owner, b) == theirs


def test_a_leaf_a_did_not_choose_is_refused_like_a_missing_one(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    parent = owner.execute("SELECT parent_id FROM ghg_index_nodes WHERE id = %s", [both["leaf"]]).fetchone()
    assert parent is not None
    code = one(
        owner,
        f"INSERT INTO {CODES} (code, name, sort_order, created_at, updated_at) VALUES (NULL, %s, 0, now(), now()) "
        "RETURNING id",
        ["가상 다른 시설"],
    )
    other = one(
        owner,
        "INSERT INTO ghg_index_nodes (level, parent_id, name, sort_order, facility_code_id, unit_kind, unit, tooltip, "
        "seed_key, deleted_at, created_at, updated_at) "
        "VALUES ('facility', %s, '', 1, %s, 'mass', 'kg', '', NULL, NULL, now(), now()) RETURNING id",
        [parent[0], code],
    )
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모
    client = customer_client(a, "tenant-a")
    data = template(client)
    not_mine = upload(client, changed(data, node=other))
    missing = upload(client, changed(data, node=other + 100000))
    assert not_mine.status_code == 422, not_mine.content.decode()
    assert not_mine.content == missing.content
    assert entries_of(owner, b) == theirs
    positive = upload(client, changed(data))
    assert positive.status_code == 200, positive.content.decode()
    assert sizes(owner, a) == [1, 2, 2]


def test_a_foreign_or_missing_year_answers_like_a_year_with_no_selection(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    """A 에게 B 만의 해 · 없는 해 · 선택 0 인 해는 같은 404 바이트다(해가 남의 것인지 드러나지 않는다)."""
    a, b = companies
    theirs_only, nobody, empty = YEAR - 1, YEAR + 7, YEAR - 2
    theirs_client = customer_client(b, "tenant-b")
    client = customer_client(a, "tenant-a")
    for owner_client, year, nodes in ((theirs_client, theirs_only, [both["leaf"]]), (client, empty, [])):
        chose = owner_client.put(
            f"/api/inventory/scope12/index-selections/{year}",
            data={"facilityNodeIds": nodes},
            content_type="application/json",
        )
        assert chose.status_code == 200, chose.content.decode()
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모: B 의 행이 있다
    data = changed(template(client))

    def answer(year: int) -> Any:
        return client.post(f"/api/inventory/scope12/years/{year}/uploads", data=data, content_type=MEDIA)

    foreign, missing, none_chosen = answer(theirs_only), answer(nobody), answer(empty)
    assert foreign.status_code == 404, foreign.content.decode()
    assert foreign.content == missing.content == none_chosen.content
    assert entries_of(owner, b) == theirs
    assert upload(client, data).status_code == 200  # 양성 대조: 제 해에는 쓴다


def test_an_operator_with_two_companies_writes_nothing(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    data = changed(template(customer_client(a, "tenant-a")))
    before = (entries_of(owner, a), entries_of(owner, b))
    operator, _ = operator_client(owner)
    refused = upload(operator, data)
    assert (refused.status_code, refused.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")
    assert B_SITE not in refused.content.decode()
    assert (entries_of(owner, a), entries_of(owner, b)) == before
    positive = upload(customer_client(a, "tenant-a"), data)  # 양성 대조: 같은 바이트가 A 고객사로는 든다
    assert positive.status_code == 200, positive.content.decode()
    assert sizes(owner, a) == [1, 2, 2]


def test_an_operator_writes_only_to_the_sole_company(owner: Owner) -> None:
    solo = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    ids = seed(owner)
    client = customer_client(solo, "tenant-a")
    place(owner, client, solo, ids["code"], ids["leaf"], A_SITE, "가 1호기")
    assert sizes(owner, solo) == [1, 1, 1]  # 분모
    operator, _ = operator_client(owner)
    done = upload(operator, changed(template(client)))
    assert done.status_code == 200, done.content.decode()
    assert done.json()["filled"] == 1
    assert sizes(owner, solo) == [1, 2, 2]  # 양성 대조: 그 회사에 들었다


def test_the_same_bytes_twice_write_nothing_the_second_time(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    client = customer_client(a, "tenant-a")
    data = changed(template(client))
    first = upload(client, data)
    assert (first.status_code, first.json()["filled"]) == (200, 1)
    assert sizes(owner, a) == [1, 2, 2]
    after = (entries_of(owner, a), entries_of(owner, b))
    second = upload(client, data)
    assert second.status_code == 200, second.content.decode()
    assert second.json() == {"added": 0, "filled": 0, "unchanged": 1, "unresolved": 0}
    assert (entries_of(owner, a), entries_of(owner, b)) == after  # 표마다 0 씀
