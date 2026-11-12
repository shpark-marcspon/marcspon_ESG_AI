# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""엑셀 보고서 GET 손질(밴드 G1b-2b ③ — MARC-ISSUE-255). 업무 층: 진짜 DB, 세션은 EDK 교환(login — 회사 A).

    nosniff   응답에 X-Content-Type-Options: nosniff — 같은 응답의 Content-Type 이 xlsx(분모)
    옛 꼴      extraTerms 칸이 없는 결과(G1c 앞) → 200, 엑셀이 추가 단어가 빈 같은 결과의 것과 같고(「설정」의
              추가 단어 빔), 감사 한 줄

★ 실행·결과 행은 seed(apps.get_model)로 심는다. 자료는 지어낸 것.
"""

import copy

import pytest
from django.test import Client

from esgapi.greenwash.outputs import xlsx
from esgapi.greenwash.tests.service import seed
from esgapi.greenwash.tests.service.apis.test_greenwash_report import (
    NORMAL,
    downloads,
    get,
    sheets,
    user_id,
)
from tests.support.http import login

pytestmark = pytest.mark.django_db


def test_the_report_response_says_nosniff(client: Client, companies: tuple[int, int]) -> None:
    login(client)
    run_id = seed.run(companies[0], result=NORMAL)
    for query in ("", "?confirmed=false"):
        response = get(client, run_id, query)
        assert response.status_code == 200
        assert response["Content-Type"] == xlsx.MEDIA_TYPE  # 분모: 같은 응답이 xlsx 다
        assert response["X-Content-Type-Options"] == "nosniff"


def test_an_old_result_without_extra_terms_is_a_report_without_added_terms(
    client: Client, companies: tuple[int, int]
) -> None:
    login(client)
    a = companies[0]
    old = copy.deepcopy(NORMAL)
    del old["extraTerms"]  # G1c 앞의 결과 꼴
    empty = {**copy.deepcopy(NORMAL), "extraTerms": []}  # 분모: 추가 단어가 빈 같은 결과
    assert NORMAL["extraTerms"]  # 예시에는 추가 단어가 있다(빈 것과 견주는 것이 헛돌지 않음)
    old_run, empty_run = seed.run(a, result=old), seed.run(a, result=empty)
    response = get(client, old_run)
    assert response.status_code == 200, response.content[:200]
    got = sheets(response)
    assert got == sheets(get(client, empty_run))
    settings = {row[0]: row[1] for row in got["설정"] if row and row[0] is not None}
    assert settings["추가 단어"] in ("", None)
    assert downloads(a)[0] == (
        "service", user_id(a), "download", "greenwash_report_downloaded", "success", "report", old_run,
        "greenwash-report.xlsx",
    )  # fmt: skip
