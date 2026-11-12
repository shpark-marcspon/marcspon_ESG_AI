"""pdfium 없는 정규화 textnorm(밴드 GR1, 발주서 §3 (k)). pdfium_locate 는 옮긴 이름을 그대로 들여 다시 내보낸다."""

from esgapi.greenwash.tools import pdfium_locate as pl
from esgapi.greenwash.tools import textnorm


def test_pdfium_locate_reexports_the_moved_names() -> None:
    assert pl.norm_str is textnorm.norm_str
    assert pl.norm_chars is textnorm.norm_chars
    assert pl.strip_tail is textnorm.strip_tail
    assert pl.TRUNC_TAIL is textnorm.TRUNC_TAIL


def test_the_two_tiers() -> None:
    assert textnorm.norm_str("Ａ “b”–c​ d.", 1) == 'a"b"-cd.'
    assert textnorm.norm_str("Ａ “b”–c​ d.", 2) == "abcd"
    assert textnorm.strip_tail("문장 ...") == "문장"
    assert textnorm.strip_tail("문장...") == "문장..."
