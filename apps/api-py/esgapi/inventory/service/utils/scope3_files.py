"""패키지에 실린 Scope 3 xlsx 둘(esgapi/inventory/data/scope3/)의 바이트 포트. 밴드 S3K1.

  TEMPLATE      빈 입력 양식 v2.2(MARC-ENT-641) — 양식 내려받기 경로가 그대로 낸다
  FACTOR_BOOK   배출계수 책(MARC-ENT-518) — 끼움(flows/binding_157.py)이 실행마다 읽는다(apps.py 가 꽂음)

두 파일은 받은 원본에서 zip 부품만 손질해 지은 바이트다(사람 칸 빔 MARC-ENT-521 — 짓는 법과 sha 는 data/README.md).
여기서 고치지 않는다.
없으면(배포 누락) 예외가 아니라 FileMissing 값이다.
"""

from dataclasses import dataclass
from importlib import resources
from typing import Final

from esgapi.inventory.flows.binding_157 import FileMissing


@dataclass(frozen=True, slots=True)
class PackagedXlsx:
    """data/scope3/<name> 의 바이트. 읽을 때마다 연다(파일은 작고 — 약 100KB — 실행·내려받기마다 한 번)."""

    name: str

    def read(self) -> bytes | FileMissing:
        try:
            return resources.files("esgapi.inventory").joinpath("data", "scope3", self.name).read_bytes()
        except FileNotFoundError:
            return FileMissing(self.name)


TEMPLATE: Final = PackagedXlsx("scope3-template-v2.2.xlsx")
FACTOR_BOOK: Final = PackagedXlsx("scope3-factor-book.xlsx")
