"""쪽 수 경로의 로그 단계(밴드 TRS2, MARC-ISSUE-385-2): 사용자 파일 탓·올림 전은 INFO, 저장소·설정 탓만 WARNING,
`no_pages` 는 로그 0. DB 없이 `_unknown` 만 부른다(갈래별 길은 test_pages.py — 업무 층)."""

import logging
from typing import get_args

import pytest

from esgapi.translation.service.actions import pages
from esgapi.translation.tools import page_tags

LOGGER = "esgapi.translation.service.actions.pages"
USER_FILE = [*sorted(set(get_args(page_tags.Reason)) - {"no_pages"}), "not_uploaded"]
STORAGE = [
    "object_missing",
    "object_too_large",
    "storage_denied",
    "storage_unavailable",
    "storage_unconfigured",
    "etag_mismatch",
]


def logged(reason: str, caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert pages._unknown(7, reason) == pages.Pages(7, None, reason)  # pyright: ignore[reportPrivateUsage]
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == LOGGER]


def test_the_user_file_reasons_cover_every_page_tags_reason() -> None:
    assert {"pdf", "not_utf8", "too_large", "unsafe", "unreadable", "too_many_entries"} <= set(USER_FILE)


@pytest.mark.parametrize("reason", USER_FILE)
def test_a_user_file_reason_is_info(reason: str, caplog: pytest.LogCaptureFixture) -> None:
    assert logged(reason, caplog) == [(logging.INFO, f"translation_pages_unreadable reason={reason}")]


@pytest.mark.parametrize("reason", STORAGE)
def test_a_storage_reason_is_a_warning(reason: str, caplog: pytest.LogCaptureFixture) -> None:
    assert logged(reason, caplog) == [(logging.WARNING, f"translation_pages_unreadable reason={reason}")]


def test_no_pages_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    assert logged("no_pages", caplog) == []
