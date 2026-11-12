"""못 담는 글자 거르기(가지 리뷰 M2): `failures.XML_INCOMPATIBLE` 가 lxml 이 `w:t` 글로 받지 않는 집합과 0..0x10FFFF
전부에서 같다(서로게이트 포함). 같으면 `writable` 로 미리 알아본 실패가 코랩의 python-docx ValueError 자리와 꼭 같다.
"""

import docx
import pytest
from docx.oxml import OxmlElement  # pyright: ignore[reportUnknownVariableType]

from esgapi.translation.outputs.failures import XML_INCOMPATIBLE, WordUnwritable, writable


def lxml_refuses(text: str) -> bool:
    element = OxmlElement("w:t")  # pyright: ignore[reportUnknownVariableType]
    try:
        element.text = text
    except ValueError:  # UnicodeEncodeError(서로게이트)도 ValueError 아래
        return True
    return False


@pytest.mark.parametrize("start", range(0, 0x110000, 0x10000))
def test_the_filter_is_exactly_what_lxml_refuses(start: int) -> None:
    """한 판(0x10000 글자)씩 — 판마다 다른 수를 함께 적는다."""
    differing = [
        cp for cp in range(start, start + 0x10000) if lxml_refuses(chr(cp)) != bool(XML_INCOMPATIBLE.search(chr(cp)))
    ]
    assert differing == []


def test_the_refused_set_is_the_one_measured() -> None:
    """잰 값(python-docx 1.2.0·lxml 6.1.3): 2,079 글자 = C0 제어 29(탭·줄바꿈·CR 뺌) + 서로게이트 2,048 +
    U+FFFE·U+FFFF."""
    refused = [cp for cp in range(0x110000) if XML_INCOMPATIBLE.search(chr(cp))]
    assert len(refused) == 2079
    assert refused[:3] == [0x0, 0x1, 0x2] and 0x9 not in refused and 0xA not in refused and 0xD not in refused


@pytest.mark.parametrize("text", ["가상\t탭", "줄\n바꿈", "캐리지\r리턴", "", "가상 😀"])
def test_writable_passes_what_python_docx_writes(text: str) -> None:
    assert writable(text) == text
    docx.Document().add_paragraph().add_run(text)  # python-docx 도 받는다


@pytest.mark.parametrize("char", ["\x00", "\x0b", "\x0c", "￾", "\ud800"])
def test_writable_refuses_what_python_docx_refuses(char: str) -> None:
    with pytest.raises(WordUnwritable, match=f"U\\+{ord(char):04X}"):
        writable(f"가상{char}")
    with pytest.raises(ValueError):
        docx.Document().add_paragraph().add_run(f"가상{char}")
