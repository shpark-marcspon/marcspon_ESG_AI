"""Scope 1·2 엑셀 내려받기 둘(S12b-1 ③ — 결정 MARC-ENT-472, 발주서 §3-4)의 보안 층. 앱 역할, 진짜 커밋.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 회사 둘이 같은 풀 잎을 고르고 같은 코드 자산/시설에 값을 넣어도 A 의 두 파일(xlsx 를 풀어 낸 XML 전부)에 B 의
     회사 이름·서브도메인·사업장 이름·상세 시설명·메모 0 — A 의 사업장 이름은 있다(양성 대조)
  ⓑ A 의 Bearer 로 B 의 siteId → 404(없는 사업장과 같은 갈래 — 있나 없나를 가르지 않음) · B 의 행 0 바뀜
  ⓒ 운영 관리자: 회사 둘 → 400 company_ambiguous(코드·글 그대로 — 파일 0 · B 글자 0), 같은 시험에서 B 를 지워 A
     하나만 남기면 A 의 파일(A 줄 있음 · B 줄 0 — 6d (라) 양성 대조) · 회사 하나 → 그 회사의 파일(고객사 사용자가 받는
     것과 XML 이 같음 · 그 회사 줄 있음)
시험마다 B 의 행이 실제로 있음을 첫 단언으로 둔다(분모). 이름·값은 지어낸 것이다.
★ 공통 표(풀 넷·코드 목록)는 tenant_tables 밖이라 owner 고정물이 비우지 않는다 — 앞뒤로 비운다(test_entries 와 같음).
"""

import html
import io
import zipfile
from collections.abc import Iterator
from typing import Any, Final

import psycopg
import pytest
from psycopg import sql

from tests.security.conftest import tenant_tables
from tests.security.seed import add_company
from tests.security.test_entries import entries_of, place
from tests.security.test_ghg_pool import CODES, POOL, seed
from tests.security.test_operator_company import customer_client, operator_client

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
YEAR: Final = 2025
ROOT: Final = f"/api/inventory/scope12/years/{YEAR}"
A_SITE: Final = "가 회사의 엑셀 공장"
B_SITE: Final = "나 회사의 엑셀 공장"
B_DETAIL: Final = "나 회사 엑셀 7호기"
B_MEMO: Final = "나 회사만의 엑셀 메모"
AMBIGUOUS: Final = "회사가 둘 이상이라 companyId 를 골라야 한다"  # 응답 글 그대로(users.COMPANY_AMBIGUOUS)


@pytest.fixture(autouse=True)
def empty_pool(owner: Owner) -> Iterator[None]:
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")
    yield
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")


def unpacked(response: Any) -> str:
    """xlsx 응답을 풀어 낸 XML 전부(글자 — 공유 문자열·인라인 글·문서 속성 포함). openpyxl 은 한글을 문자 참조
    (`&#44032;`)로 적으므로 참조를 풀어 견준다 — 풀지 않으면 한글 이름의 「0」 단언이 늘 참이 된다(양성 대조가 잡음)."""
    assert response.status_code == 200, response.content.decode(errors="replace")[:300]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return html.unescape("".join(archive.read(name).decode() for name in archive.namelist()))


def b_words(owner: Owner, b: int) -> tuple[str, ...]:
    names = owner.execute("SELECT name, subdomain FROM company WHERE id = %s", [b]).fetchone()
    assert names is not None
    return (*names, B_SITE, B_DETAIL, B_MEMO)


@pytest.fixture
def both(owner: Owner, companies: tuple[int, int]) -> dict[str, Any]:
    """같은 풀 잎·같은 코드 — A·B 에 사업장 하나씩(1월 1000 kg), B 에만 메모."""
    a, b = companies
    ids = seed(owner)
    mine = place(owner, customer_client(a, "tenant-a"), a, ids["code"], ids["leaf"], A_SITE, "가 엑셀 1호기")
    theirs_client = customer_client(b, "tenant-b")
    theirs = place(owner, theirs_client, b, ids["code"], ids["leaf"], B_SITE, B_DETAIL)
    memo = theirs_client.put(
        f"{ROOT}/indexes/{ids['leaf']}/memo", data={"memo": B_MEMO}, content_type="application/json"
    )
    assert memo.status_code == 200, memo.content.decode()
    return {**ids, "a": mine, "b": theirs}


def test_my_two_files_carry_nothing_of_the_other_company(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모: B 의 행·값·히스토리가 있다
    client = customer_client(a, "tenant-a")
    for url in (f"{ROOT}/template", f"{ROOT}/export"):
        text = unpacked(client.get(url))
        assert A_SITE in text, url  # 양성 대조: A 의 줄은 실렸다
        for word in b_words(owner, b):
            assert word not in text, (url, word)
    assert entries_of(owner, b) == theirs


def test_the_other_companys_site_id_is_not_found(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모
    client = customer_client(a, "tenant-a")
    mine = client.get(f"{ROOT}/template?siteId={both['a']['site']}")
    assert mine.status_code == 200  # 짝: 제 사업장은 받는다
    refused = client.get(f"{ROOT}/template?siteId={both['b']['site']}")
    missing = client.get(f"{ROOT}/template?siteId={both['b']['site'] + 100000}")
    for response in (refused, missing):
        assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert refused.json() == missing.json()  # 남의 것과 없는 것이 같은 답
    for word in b_words(owner, b):
        assert word not in refused.content.decode()
    assert entries_of(owner, b) == theirs


def drop_company(owner: Owner, company_id: int) -> None:
    """그 회사와 그 회사의 테넌트 행 전부를 지운다(한 트랜잭션). 표 이름은 카탈로그에서 — 외래 키 차례를 박지 않고,
    남이 아직 가리키는 표는 세이브포인트로 되돌려 다음 바퀴에 다시 지운다(바퀴마다 하나 이상 지워지지 않으면 실패)."""
    left = tenant_tables(owner)
    with owner.transaction():
        owner.execute("SET CONSTRAINTS ALL IMMEDIATE")  # 미룬 외래 키도 문장마다 잰다(세이브포인트로 잡게)
        owner.execute(  # 회사 칸이 없는 자식 — 그 회사 사용자의 갱신 토큰
            "DELETE FROM user_refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE company_id = %s)",
            [company_id],
        )
        while left:
            stuck: list[str] = []
            for table in left:
                column = "id" if table == "company" else "company_id"
                query = sql.SQL("DELETE FROM {} WHERE {} = %s").format(sql.Identifier(table), sql.Identifier(column))
                try:
                    with owner.transaction():
                        owner.execute(query, [company_id])
                except psycopg.errors.ForeignKeyViolation:
                    stuck.append(table)
            assert len(stuck) < len(left), stuck
            left = stuck


def test_an_operator_with_two_companies_gets_no_file(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    assert [len(part) for part in entries_of(owner, b)] == [1, 1, 1]  # 분모
    operator, _ = operator_client(owner)
    for url in (f"{ROOT}/template", f"{ROOT}/export"):
        response = operator.get(url)
        assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS"), url
        assert response.json()["error"]["message"] == AMBIGUOUS, url  # 글 그대로(파일 0)
        for word in b_words(owner, b):
            assert word not in response.content.decode(), (url, word)
    # 양성 대조(같은 시험 — 6d (라)): 회사를 A 하나만 남기면 같은 운영 관리자가 A 의 파일을 받는다 — A 줄 있음·B 줄 0
    words = b_words(owner, b)
    drop_company(owner, b)
    assert owner.execute("SELECT id FROM company").fetchall() == [(a,)]  # 분모: 남은 회사가 A 하나
    for url in (f"{ROOT}/template", f"{ROOT}/export"):
        text = unpacked(operator.get(url))
        assert A_SITE in text, url
        for word in words:
            assert word not in text, (url, word)


@pytest.fixture
def solo(owner: Owner) -> int:
    """회사 하나(활성, subdomain tenant-a). 운영 관리자의 작업 회사가 그것 하나로 정해진다."""
    return add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")


def test_an_operator_downloads_only_the_sole_company(owner: Owner, solo: int) -> None:
    ids = seed(owner)
    place(owner, customer_client(solo, "tenant-a"), solo, ids["code"], ids["leaf"], A_SITE, "가 엑셀 1호기")
    assert [len(part) for part in entries_of(owner, solo)] == [1, 1, 1]  # 분모: 그 회사의 행이 있다
    customer = customer_client(solo, "tenant-a")
    operator, _ = operator_client(owner)
    for url in (f"{ROOT}/template", f"{ROOT}/export"):
        mine, theirs = customer.get(url), operator.get(url)
        assert unpacked(theirs) == unpacked(mine), url  # 운영 관리자 = 작업 회사의 같은 파일
        assert A_SITE in unpacked(theirs)  # 양성 대조: 그 회사 줄이 실렸다
