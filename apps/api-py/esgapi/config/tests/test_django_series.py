"""Django 의 계열이 5.2(LTS)에 머무는가. 순수 층(DB 없음, 네트워크 없음).

마크스폰의 백엔드 가이드가 Django 5.2 LTS 를 기본으로 요청한다(MARC-ISSUE-62 의 1번, MARC-TICK-64).
누가 `django==` 줄이나 잠금을 6.x 로 올리면 여기서 빨개진다. 올리기로 정했으면 이 파일의 계열을 같이 고친다.

    (가) 설치된 Django 의 계열이 5.2 다.
    (나) pyproject.toml 의 `django==` 줄과 uv.lock 의 django 꾸러미의 판이 같고 5.2. 로 시작한다.
    (다) django-ninja 도 pyproject 와 잠금이 같다(판 값은 못 박지 않는다. 올리는 밴드가 이 파일을 고치지 않게).

읽는 것은 글자뿐이다: 잠금에 적힌 판과 설치된 판이 같은지는 (가)·(나)를 같이 봐야 안다.
무효 조건: (가)·(나)는 계열만 본다. 5.2 안에서 낮은 판으로 내려가는 것(보안 고침이 빠지는 것)은 잡지 않는다.
"""

import re
import tomllib
from pathlib import Path
from typing import Any, cast

import django

ROOT = Path(__file__).resolve().parents[3]  # apps/api-py
SERIES = (5, 2)


def _pinned(name: str) -> str:
    """pyproject.toml 의 dependencies 에서 `<name>==<판>` 의 판. 그 줄이 하나가 아니면 실패한다."""
    project = cast("dict[str, Any]", tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"])
    lines = cast("list[str]", project["dependencies"])
    found = [
        m.group(1) for m in (re.fullmatch(re.escape(name) + r"==([0-9][0-9A-Za-z.]*)", line) for line in lines) if m
    ]
    assert len(found) == 1, f"pyproject.toml 에 {name}== 줄이 하나가 아니다: {found}"
    return found[0]


def _locked(name: str) -> str:
    """uv.lock 의 `name = "<name>"` 꾸러미의 판. 그 꾸러미가 하나가 아니면 실패한다."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = cast("list[dict[str, Any]]", lock["package"])
    found = [cast("str", p["version"]) for p in packages if p["name"] == name]
    assert len(found) == 1, f"uv.lock 에 {name} 꾸러미가 하나가 아니다: {found}"
    return found[0]


def test_the_installed_django_is_in_the_5_2_series() -> None:
    assert django.VERSION[:2] == SERIES, django.get_version()


def test_django_is_pinned_and_locked_to_the_same_5_2_version() -> None:
    pinned, locked = _pinned("django"), _locked("django")
    assert pinned == locked, f"pyproject {pinned} · 잠금 {locked}"
    assert pinned.startswith("5.2."), pinned
    assert locked.startswith("5.2."), locked


def test_django_ninja_is_pinned_and_locked_to_the_same_version() -> None:
    pinned, locked = _pinned("django-ninja"), _locked("django-ninja")
    assert pinned == locked, f"pyproject {pinned} · 잠금 {locked}"
