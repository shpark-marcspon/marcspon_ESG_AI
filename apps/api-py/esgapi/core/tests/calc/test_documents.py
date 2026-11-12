"""문서의 순수 규칙 가운데 쪽 재기의 몫(core/calc/documents.py 의 has_text·한도 — X1b-2a). 순수 층.

나머지(상태·전이·키·파일 이름)는 옛 평평한 파일 core/tests/test_documents_calc.py 에 있다.
"""

import pytest

from esgapi.core.calc import documents


def test_the_probe_limits_are_the_written_guesses() -> None:
    assert (documents.TEXT_PROBE_PAGES, documents.PDF_PROBE_TIMEOUT_S) == (3, 5)
    assert documents.PDF_PROBE_MEMORY_BYTES == 512 * 1024 * 1024


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        ([], False),  # 쪽이 없다
        ([""], False),  # 빈 쪽
        (["   ", "\n\t", " 　"], False),  # 공백만(빈칸·줄바꿈·탭·NBSP·전각 빈칸)
        (["", "  a  "], True),  # 한 쪽이라도 글자가 있으면
        (["보고서"], True),
    ],
)
def test_has_text_counts_only_non_space_characters(pages: list[str], expected: bool) -> None:
    assert documents.has_text(pages) is expected
