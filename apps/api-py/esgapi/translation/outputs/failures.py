"""Word 를 짓다 실패한 갈래(발주서 처분 ⑧). docx 를 직접 import 하지 않는다 — 결과에서 고르는 쪽(files)도 같이 쓴다."""

import re
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class WordFailed:
    """코랩의 `except Exception` → 출력 후 `False` 자리(R/4915-4917). 코랩은 모든 예외를 잡지만 우리는 미리 알아본
    실패(`WordUnwritable` — 못 담는 글자·없는 스타일)와 python-docx 자신의 오류만 이 갈래로 낸다. 그 밖의 예외와
    `MemoryError` 는 밖으로 나간다(우리 버그를 숨기지 않는다 — 감독 처분, 가지 리뷰 M2)."""

    message: str
    """까닭 글(「XML 에 못 담는 글자 U+0001 …」·「틀에 스타일 Table Grid 가 없다」·`PythonDocxError: …`)."""


class WordUnwritable(Exception):
    """python-docx 에 넘기기 전에 알아본 실패. 쓰개가 `WordFailed` 로 바꾼다 — 밖으로 새지 않는다."""


XML_INCOMPATIBLE: Final = re.compile("[^\t\n\r\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")
"""XML 1.0 `Char` 밖의 글자(서로게이트 포함). lxml 이 글(`w:t`)로 받지 않는 집합과 같다 — 0..0x10FFFF 전부를 견주는
차등 시험(tests/outputs/test_failures.py)이 잰다. python-docx 는 run 글의 `\\t`·`\\n`·`\\r` 를 `w:tab`·`w:br` 로
바꾸지만 셋 다 XML 글자라 이 집합 밖이다. 약점 W10(코랩대로): 이 글자 하나면 그 Word 가 통째로 안 생긴다."""


def writable(text: str) -> str:
    """run 에 넣을 글 그대로 — XML 에 못 담는 글자가 있으면 `WordUnwritable`(python-docx 라면 ValueError 를 낼 자리)."""
    bad = XML_INCOMPATIBLE.search(text)
    if bad is not None:
        raise WordUnwritable(f"XML 에 못 담는 글자 U+{ord(bad.group()):04X} — Word 하나가 통째로 안 생긴다(W10)")
    return text
