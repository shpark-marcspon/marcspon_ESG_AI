"""이용 조건의 상태(license_status)로 낱줄을 거르는 규칙. 순수하다(표준 라이브러리만).

  ok          조건을 확인했고 쓸 수 있다(DEFRA: 출처 표시, EPA: 공공 저작물)
  unverified  확인하지 못했다(GIR 공표, 고시 별표). 쓰되 상태를 늘 같이 보인다
  disputed    공식 문면끼리 충돌한다(KEITI 환경성적표지 평가계수). 서면 확인 전에는 쓰지 않는다

★ 기본은 `ok,unverified` 다. **disputed 는 명시해야만 들어온다** — 가져오기(`import_factors --include-license`)에서도,
  읽기 API(`GET /reference/factors?license=`)에서도. 두 자리가 따로 거른다: disputed 를 명시해 들인 DB 에서도
  기본 조회는 그것을 내지 않는다.
"""

from typing import Final, cast

from esgapi.reference.jsonl import LICENSE_STATUSES, LicenseStatus

DEFAULT_LICENSES: Final[frozenset[LicenseStatus]] = frozenset({"ok", "unverified"})
DEFAULT_LICENSES_TEXT: Final = "ok,unverified"


class LicenseListInvalid(ValueError):
    """`ok,unverified` 꼴이 아니다. 모르는 상태가 있거나 비었다."""


def parse_license_list(text: str) -> frozenset[LicenseStatus]:
    """쉼표로 나눈 상태 목록을 읽는다. 모르는 이름이 하나라도 있으면 거절한다(조용히 빼지 않는다)."""
    names = [part.strip() for part in text.split(",")]
    if not names or any(name not in LICENSE_STATUSES for name in names):
        raise LicenseListInvalid(f"license 는 {', '.join(LICENSE_STATUSES)} 를 쉼표로 이은 것이다")
    return frozenset(cast(LicenseStatus, name) for name in names)
