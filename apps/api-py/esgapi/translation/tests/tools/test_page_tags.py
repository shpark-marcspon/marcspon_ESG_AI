"""문서 쪽 수 셈(밴드 TRP6 §3-1, 결정 MARC-ENT-452): 시험이 지은 txt·docx → `page_count` 가 [PAGE n] 최댓값이고,
표본 셋에서 엔진의 셈(read_document → source_and_pages)과 같으며, 못 읽는 바이트는 예외 없이 None, 공격 셋은 각각
2초 안이다(`read_docx` 를 부르지 않는다). 글·문서는 지어낸 것이다.
"""

import io
import os
import struct
import time
import tracemalloc
import zipfile

import pytest

from esgapi.translation.engines.colab_158.pipeline import source_and_pages
from esgapi.translation.flows.colab_158 import MAX_SOURCE_CHARS, UnsupportedDocument, read_document
from esgapi.translation.tests.docx_support import (
    built,
    document_xml,
    p,
    parts_of,
    tbl,
    tc,
    tr,
    with_body,
    zip_bytes,
)
from esgapi.translation.tests.engines.colab_158.support import make_input
from esgapi.translation.tools import docx_reader, page_tags
from esgapi.translation.tools.page_tags import PageTags, page_count

SECONDS = 2.0
MEMORY = 50 * 1024 * 1024
V = 'xmlns:v="urn:schemas-microsoft-com:vml"'


def text(*lines: str, end: str = "\n") -> bytes:
    return end.join(lines).encode()


def engine_max(data: bytes) -> int | None:
    """엔진이 셀 쪽: read_document → source_and_pages 의 쪽 조각 번호 최댓값."""
    read = read_document(data)
    assert not isinstance(read, UnsupportedDocument), read
    _, pages, _ = source_and_pages(make_input(read.text))
    return max((chunk.page_num for chunk in pages), default=None)


def timed(data: bytes) -> tuple[PageTags, float]:
    start = time.perf_counter()
    found = page_count(data)
    return found, time.perf_counter() - start


def measured(data: bytes) -> tuple[PageTags, float, int]:
    """값 · 걸린 초 · 파이썬 쪽 메모리 꼭대기(tracemalloc — 받은 바이트는 재기 전에 지어 두므로 빠진다)."""
    tracemalloc.start()
    try:
        found, took = timed(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return found, took, peak


def run(*inner: str) -> str:
    return f"<w:r>{''.join(inner)}</w:r>"


def para(*inner: str) -> str:
    return f"<w:p>{''.join(inner)}</w:p>"


def wt(value: str) -> str:
    return f'<w:t xml:space="preserve">{value}</w:t>'


# ── 3-1-1 txt ──


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (text("[PAGE 1]", "가", "[PAGE 2]", "나", "[PAGE 3]", "[PAGE 4]", "[PAGE 5]", "마"), 5),
        (text("[PAGE 2]", "가", "[PAGE 7]", "나"), 7),  # 번호 뜀 — 태그 수(2)가 아니라 최댓값
        (text("[PAGE 3]", "가", "[PAGE 3]", "나", "[PAGE 1]"), 3),  # 겹침
        (text("**[PAGE 4]**", "가"), 4),
        (text("\\[PAGE 4\\]", "가"), 4),
        (text("[page 4]", "가"), 4),
        (text("  ## [PAGE 6]  ", "가"), 6),  # 머리 표시(정규화가 벗김)
        (text("[PAGE 1]", "가", "[PAGE 5]", "나", end="\r"), 5),  # `\r` 만 쓴 줄바꿈
        (text("[PAGE 1]", "가", "[PAGE 5]", "나", end="\r\n"), 5),
    ],
)
def test_txt_counts_the_largest_page_tag(data: bytes, expected: int) -> None:
    assert page_count(data) == PageTags(expected, None)


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (text("가", "나"), "no_pages"),
        (text("[PAGE 0]", "가"), "no_pages"),
        (text("본문 [PAGE 3] 가운데", "가"), "no_pages"),  # 줄 전체가 태그일 때만
        ("[PAGE 2]\n가나".encode("cp949"), "not_utf8"),
        (b"%PDF-1.7\n[PAGE 3]\n", "pdf"),
        (b"\xff" * (page_tags.MAX_TEXT_BYTES + 1), "too_large"),  # 디코드 전에 바이트로 거름(not_utf8 이 아니다)
        (b"", "no_pages"),
        (text("[PAGE 1]", "[PAGE 10001]"), "too_many_pages"),  # 그리드 칸 수 상한(MAX_PAGES)
    ],
)
def test_txt_that_cannot_be_counted_is_none(data: bytes, reason: str) -> None:
    assert page_count(data) == PageTags(None, reason)  # pyright: ignore[reportArgumentType]


def test_a_txt_longer_than_the_engine_takes_still_shows_its_pages() -> None:
    """글자 상한은 실행이 쪽 범위 안 글자로 잰다(MARC-ISSUE-393) — 범위를 고르게 그리드는 뜬다."""
    long = ("[PAGE 1]\n" + "가" * MAX_SOURCE_CHARS + "\n[PAGE 7]\n나").encode()
    assert page_count(long) == PageTags(7, None)


def test_the_txt_byte_limit_itself_still_counts_and_one_byte_more_hides_the_grid() -> None:
    # 값을 못 박는다: 요청 길 공격 꼴이 이 값에서 1.39초, 8MiB 에서 5.66초(band-reports/TRS4.md 「MAX_TEXT_BYTES」)
    assert page_tags.MAX_TEXT_BYTES == 2 * 1024 * 1024
    head = b"[PAGE 3]\n"
    fits = head + b"a" * (page_tags.MAX_TEXT_BYTES - len(head))
    assert len(fits) == page_tags.MAX_TEXT_BYTES and page_count(fits) == PageTags(3, None)
    assert page_count(fits + b"a") == PageTags(None, "too_large")


def test_the_page_limit_itself_still_counts() -> None:
    assert page_count(text("[PAGE 1]", f"[PAGE {page_tags.MAX_PAGES}]")) == PageTags(page_tags.MAX_PAGES, None)


def test_a_tag_with_too_many_digits_is_unreadable_not_an_exception() -> None:
    assert page_count(text("[PAGE " + "9" * 5000 + "]")) == PageTags(None, "unreadable")


# ── 3-1-2 docx ──


def test_body_paragraphs_count() -> None:
    assert page_count(with_body(p("[PAGE 1]") + p("가") + p("[PAGE 2]") + p("[PAGE 3]"))) == PageTags(3, None)


def test_a_tag_in_a_table_cell_is_not_counted() -> None:
    assert page_count(with_body(tbl(tr(tc("[PAGE 99]"))) + p("[PAGE 2]"))) == PageTags(2, None)


def test_a_line_break_splits_one_paragraph_into_two_lines() -> None:
    body = para(run(wt("가"), "<w:br/>", wt("[PAGE 6]")))
    assert page_count(with_body(body + p("[PAGE 1]"))) == PageTags(6, None)


def test_a_tag_in_a_content_control_is_not_counted() -> None:
    body = f"<w:sdt><w:sdtContent>{p('[PAGE 30]')}</w:sdtContent></w:sdt>" + p("[PAGE 2]")
    assert page_count(with_body(body)) == PageTags(2, None)


def test_a_page_break_joins_the_tag_to_the_text_before_it() -> None:
    """`w:br w:type="page"` 는 글이 아니다(python-docx `""`) — 「본문 끝[PAGE 9]」 한 줄이라 태그가 아니다(엔진 값)."""
    body = para(run(wt("본문 끝"), '<w:br w:type="page"/>', wt("[PAGE 9]"))) + p("[PAGE 2]")
    data = with_body(body)
    assert page_count(data) == PageTags(2, None) and engine_max(data) == 2


def test_a_docx_without_tags_is_none() -> None:
    assert page_count(built(lambda d: d.add_paragraph("가상 본문"))) == PageTags(None, "no_pages")


def test_a_doctype_stops_the_reading() -> None:
    head = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    xml = document_xml(p("&a;")).replace(head, head + b'<!DOCTYPE w:document [<!ENTITY a "[PAGE 5]">]>')
    assert page_count(with_body("", replace={"word/document.xml": xml})) == PageTags(None, "unsafe")


def test_broken_zip_and_missing_part_are_none() -> None:
    assert page_count(b"PK\x03\x04" + b"\x00" * 64) == PageTags(None, "unreadable")
    parts = parts_of(with_body(p("[PAGE 2]")))
    del parts["word/document.xml"]
    assert page_count(zip_bytes(parts)) == PageTags(None, "no_document_xml")


@pytest.mark.parametrize("encoding", ["x-nope", "utf-32"])
def test_an_encoding_expat_cannot_read_is_unreadable(encoding: str) -> None:
    xml = document_xml(p("[PAGE 2]")).replace(b'encoding="UTF-8"', f'encoding="{encoding}"'.encode())
    assert page_count(with_body("", replace={"word/document.xml": xml})) == PageTags(None, "unreadable")


def test_a_broken_deflate_stream_is_unreadable() -> None:
    data = bytearray(with_body(p("[PAGE 2]") * 2000))
    with zipfile.ZipFile(io.BytesIO(bytes(data))) as archive:
        entry = archive.getinfo("word/document.xml")
    start = entry.header_offset + 30 + len(entry.filename.encode()) + len(entry.extra)
    middle = start + entry.compress_size // 2
    data[middle : start + entry.compress_size] = b"\xff" * (start + entry.compress_size - middle)
    assert page_count(bytes(data)) == PageTags(None, "unreadable")


def test_encrypted_and_unknown_compression_are_none() -> None:
    data = bytearray(with_body(p("[PAGE 2]")))
    with zipfile.ZipFile(io.BytesIO(bytes(data))) as archive:
        entry = archive.getinfo("word/document.xml")
    data[entry.header_offset + 6] |= 0x1  # 지역 머리의 암호 비트
    for found in _central_entries(bytes(data), b"word/document.xml"):
        data[found + 8] |= 0x1  # 가운데 목록의 암호 비트(zipfile 은 이것을 읽는다)
    assert page_count(bytes(data)) == PageTags(None, "encrypted")
    data = bytearray(with_body(p("[PAGE 2]")))
    for found in _central_entries(bytes(data), b"word/document.xml"):
        data[found + 10 : found + 12] = (14).to_bytes(2, "little")  # LZMA
    assert page_count(bytes(data)) == PageTags(None, "unsupported_compression")


def _central_entries(data: bytes, name: bytes) -> list[int]:
    found: list[int] = []
    at = data.find(b"PK\x01\x02")
    while at >= 0:
        size = int.from_bytes(data[at + 28 : at + 30], "little")
        if data[at + 46 : at + 46 + size] == name:
            found.append(at)
        at = data.find(b"PK\x01\x02", at + 4)
    return found


def test_a_docx_with_more_body_text_than_the_engine_takes_still_shows_its_pages() -> None:
    """글자 상한은 실행이 쪽 범위 안 글자로 잰다(MARC-ISSUE-393). 셈은 끝까지 간다 — 상한 뒤의 쪽 태그도 센다."""
    chunk = "가" * 1000
    data = with_body(p("[PAGE 1]") + p(chunk) * (MAX_SOURCE_CHARS // 1000 + 1) + p("[PAGE 9]") + p("나"))
    assert page_count(data) == PageTags(9, None)


def test_a_docx_over_the_xml_byte_limit_stays_too_large() -> None:
    xml = document_xml(p("[PAGE 1]") + p("가" * 1000) * (page_tags.MAX_XML_BYTES // 3000 + 1))
    assert len(xml) > page_tags.MAX_XML_BYTES
    assert page_count(with_body("", replace={"word/document.xml": xml})) == PageTags(None, "too_large")


# ── 가지 리뷰 ③ — 깊이·가운데 목록·이어진 바이트 상한 ──


NESTED = {
    "이름 공간 없는 요소가 끝없이 열림": lambda: "<x>" * 2_000_000,
    "w:p 겹침": lambda: "<w:p>" * 600_000 + p("[PAGE 2]") + "</w:p>" * 600_000,
}


@pytest.mark.parametrize("name", sorted(NESTED))
def test_deep_nesting_stops_as_unsafe_quickly_and_small(name: str) -> None:
    data = with_body(NESTED[name]())
    found, took, peak = measured(data)
    assert found == PageTags(None, "unsafe"), name
    assert took < SECONDS and peak < MEMORY, f"{name}: {took:.2f}s {peak / 2**20:.1f}MiB"


def _central_directory_bomb(entries: int) -> bytes:
    """지역 머리 하나 + 1바이트 이름의 가운데 항목 `entries` 개(모두 그 머리를 가리킴) + EOCD(zip64 표시 없음)."""
    local = struct.pack("<4s5H3L2H", b"PK\x03\x04", 20, 0, 0, 0, 0, 0, 0, 0, 1, 0) + b"a"
    central = struct.pack("<4s6H3L5H2L", b"PK\x01\x02", 20, 20, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0) + b"a"
    directory = central * entries
    end = struct.pack(
        "<4s4H2LH", b"PK\x05\x06", 0, 0, entries & 0xFFFF, entries & 0xFFFF, len(directory), len(local), 0
    )
    return local + directory + end


def test_a_central_directory_bomb_is_refused_before_zipfile_reads_it() -> None:
    """1바이트 이름 가운데 항목 100만 개(47MB < MAX_BYTES) — zipfile 이 ZipInfo 100만 개를 짓기 전에 EOCD 로 거른다."""
    data = _central_directory_bomb(1_000_000)
    assert len(data) <= page_tags.MAX_BYTES
    found, took, peak = measured(data)
    assert found == PageTags(None, "too_many_entries")
    assert took < 0.3 and peak < MEMORY, f"{took:.2f}s {peak / 2**20:.1f}MiB"


def _with_end_record(data: bytes, **fields: int) -> bytes:
    """끝 EOCD(주석 없음)의 칸을 바꾼 바이트."""
    names = ("disk", "start_disk", "disk_entries", "entries", "size", "offset")
    head, end = data[:-22], list(struct.unpack("<4s4H2LH", data[-22:]))
    for name, value in fields.items():
        end[1 + names.index(name)] = value
    return head + struct.pack("<4s4H2LH", *end)


@pytest.mark.parametrize(
    "fields",
    [{"entries": 0xFFFF}, {"disk_entries": 0xFFFF}, {"size": 0xFFFFFFFF}, {"offset": 0xFFFFFFFF}],
)
def test_a_zip64_end_record_is_refused(fields: dict[str, int]) -> None:
    assert page_count(_with_end_record(with_body(p("[PAGE 2]")), **fields)) == PageTags(None, "too_many_entries")


def test_a_zip64_locator_before_the_end_record_is_refused() -> None:
    data = with_body(p("[PAGE 2]"))
    head, end = data[:-22], data[-22:]
    locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, 0, 1)
    assert page_count(head + locator + end) == PageTags(None, "too_many_entries")


def test_an_archive_comment_still_finds_the_end_record() -> None:
    """주석이 있으면 EOCD 는 끝 22바이트가 아니다 — zipfile 처럼 끝 64KiB 에서 찾는다."""
    data = with_body(p("[PAGE 1]") + p("[PAGE 3]"))
    comment = "가상 주석 ".encode() * 100
    data = data[:-2] + len(comment).to_bytes(2, "little") + comment
    assert page_count(data) == PageTags(3, None)


def _many_attributes(count: int) -> str:
    return "".join(f' a{i:x}=""' for i in range(count))


def test_a_start_tag_without_end_is_refused_across_chunks() -> None:
    """속성 20만 개 1.7MB 짜리 태그 하나 — `>` 없이 이어진 바이트가 MAX_TAG_RUN 을 넘으면(청크를 넘어 셈) unsafe."""
    body = f"<w:p{_many_attributes(200_000)}>" + run(wt("[PAGE 2]")) + "</w:p>"
    assert len(body) > 1_600_000
    found, took, peak = measured(with_body(body))
    assert found == PageTags(None, "unsafe")
    assert took < SECONDS and peak < MEMORY, f"{took:.2f}s {peak / 2**20:.1f}MiB"


def test_long_text_without_a_tag_end_is_unsafe_but_shorter_text_spanning_chunks_counts() -> None:
    long = "가" * (page_tags.MAX_TAG_RUN // 3 + 1)  # 바이트로는 상한을 넘고 글자로는 MAX_SOURCE_CHARS 안
    assert len(long) < MAX_SOURCE_CHARS
    assert page_count(with_body(p("[PAGE 1]") + p(long))) == PageTags(None, "unsafe")
    assert page_count(with_body(p("a" * 150_000) + p("[PAGE 3]"))) == PageTags(3, None)  # 64KiB 청크 셋을 건넘


# ── 3-1-3 엔진과 같음 — 표본 셋 ──

SAMPLES = {
    "ㄱ 몸 문단": (with_body(p("[PAGE 1]") + p("가") + p("[PAGE 3]") + p("나") + p("[PAGE 8]") + p("다")), 8),
    "ㄴ 표 칸 + 몸": (with_body(tbl(tr(tc("[PAGE 99]"), tc("가"))) + p("[PAGE 2]") + p("나")), 2),
    "ㄷ `\\r` 줄바꿈 txt": (text("[PAGE 1]", "가", "[PAGE 4]", "나", end="\r"), 4),
    "ㄹ 쪽 나눔·글상자·고친 자취·링크": (
        with_body(
            para(run(wt("본문 끝"), '<w:br w:type="page"/>', wt("[PAGE 9]")))
            + para(
                run(
                    "<w:pict><v:shape><v:textbox><w:txbxContent>"
                    + p("[PAGE 50]")
                    + "</w:txbxContent></v:textbox></v:shape></w:pict>"
                )
            )
            + para('<w:ins w:id="1" w:author="가상">', run(wt("[PAGE 40]")), "</w:ins>")
            + para("<w:hyperlink>", run(wt("[PAGE 7]")), "</w:hyperlink>")
            + p("가"),
            extra_ns=V,
        ),
        7,
    ),
}


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_the_samples_count_what_the_engine_counts(name: str) -> None:
    """기대값은 python-docx 1.2.0 의 엔진 셈(손으로 박음) — 그리고 지금 엔진과도 다시 견준다."""
    data, expected = SAMPLES[name]
    assert page_count(data) == PageTags(expected, None)
    assert engine_max(data) == expected


# ── 3-1-4 시간(각각 2초 안 + 값) — `read_docx` 는 부르지 않는다 ──


def vmerge_table(rows: int, cols: int) -> str:
    first = tr(*(tc("가", '<w:vMerge w:val="restart"/>') for _ in range(cols)))
    rest = tr(*(tc("", "<w:vMerge/>") for _ in range(cols)))
    return tbl(first + rest * (rows - 1))


def test_the_attack_set_is_inside_the_docx_reader_limits() -> None:
    """공격 셋이 docx_reader 의 상한 안이다 — 거기서 거절되는 꼴이 아니라 python-docx 가 느린 꼴(critic 탐침)."""
    rows, cols = 700, 2
    assert rows * cols <= docx_reader.MAX_TABLE_CELLS
    assert cols * (rows - 1) * rows // 2 <= docx_reader.MAX_VMERGE_STEPS  # 이어진 칸마다 사슬 깊이
    assert docx_reader.MAX_GRID_COLS >= 64 and docx_reader.MAX_TABLE_CELLS >= 64 * 3_100
    assert len(_big_markup_xml()) <= page_tags.MAX_XML_BYTES


def _big_markup_xml() -> bytes:
    """7.8MB document.xml — 문단마다 꾸밈이 무겁고 글은 적다(글 합 < MAX_SOURCE_CHARS), 20 문단마다 [PAGE i]."""
    filler = para('<w:pPr><w:jc w:val="both"/><w:spacing w:after="0"/></w:pPr>', run("<w:rPr><w:b/></w:rPr>", wt("가")))
    body: list[str] = []
    page = 0
    size = 0
    while size < 7_800_000 - 2_000:
        if len(body) % 20 == 0:
            page += 1
            body.append(p(f"[PAGE {page}]"))
        body.append(filler)
        size += len(body[-1].encode())
    return document_xml("".join(body))


def _big_markup_pages() -> int:
    return _big_markup_xml().count(b"[PAGE ")


def _full_txt() -> bytes:
    return "".join(f"[PAGE {i}]\n" for i in range(1, _full_txt_pages() + 1)).encode()


def _full_txt_pages() -> int:
    """글자 상한 안에 [PAGE n] 줄을 가득."""
    total, n = 0, 0
    while total + len(f"[PAGE {n + 1}]\n") <= MAX_SOURCE_CHARS:
        n += 1
        total += len(f"[PAGE {n}]\n")
    return n


@pytest.mark.parametrize(
    ("name", "build", "expected"),
    [
        ("vMerge 700행×2열", lambda: with_body(vmerge_table(700, 2) + p("[PAGE 4]")), PageTags(4, None)),
        (
            "gridSpan 64칸×3,100행",
            lambda: with_body(tbl(tr(tc("가", '<w:gridSpan w:val="64"/>')) * 3_100) + p("[PAGE 5]")),
            PageTags(5, None),
        ),
        (
            "document.xml 7.8MB",
            lambda: with_body("", replace={"word/document.xml": _big_markup_xml()}),
            None,  # 값은 아래에서 짓는 쪽 수
        ),
        (
            "정상 1MB(그림 하나 + 문단 150)",
            lambda: with_body(
                "".join(p(f"[PAGE {i}]") + p("가상 본문 " * 20) for i in range(1, 151)),
                replace={"word/media/image1.png": os.urandom(900_000)},
            ),
            PageTags(150, None),
        ),
        (
            "「a ↵」 41만 줄 한 문단(XML 바이트 상한 넘음)",
            lambda: with_body(para(run((wt("a") + "<w:br/>") * 410_000)) + p("[PAGE 1]")),
            PageTags(None, "too_large"),
        ),
        (
            "「a ↵」 9만 줄 한 문단 + 끝 [PAGE 3]",
            lambda: with_body(para(run((wt("a") + "<w:br/>") * 90_000 + wt("[PAGE 3]")))),
            PageTags(3, None),
        ),
        ("[PAGE n] 줄로 꽉 찬 txt(MAX_PAGES 넘음)", lambda: _full_txt(), PageTags(None, "too_many_pages")),
        (
            "page 와 빈칸 19만 칸 한 줄 txt",
            lambda: ("page" + " " * 190_000 + "x\n[PAGE 2]").encode(),
            PageTags(2, None),
        ),
        (
            "page 와 빈칸 19만 칸 한 문단 docx",
            lambda: with_body(p("page" + " " * 190_000 + "x") + p("[PAGE 2]")),
            PageTags(2, None),
        ),
    ],
)
def test_the_attack_set_counts_within_two_seconds(name: str, build: object, expected: PageTags | None) -> None:
    data = build()  # pyright: ignore[reportUnknownVariableType, reportCallIssue]
    assert isinstance(data, bytes)
    if expected is None:
        expected = PageTags(_big_markup_pages(), None)
    found, took = timed(data)
    assert found == expected, name
    assert took < SECONDS, f"{name}: {took:.2f}s"


def test_the_count_never_calls_the_docx_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(data: bytes) -> object:
        raise AssertionError("read_docx 를 불렀다")

    monkeypatch.setattr(docx_reader, "read_docx", boom)
    assert page_count(with_body(vmerge_table(700, 2) + p("[PAGE 4]"))) == PageTags(4, None)


# ── 밴드 TRS2(MARC-ISSUE-385-3) — 우리 실수는 unreadable 로 묻히지 않는다 ──


def test_no_honest_sample_is_unreadable() -> None:
    """정상 docx 표본 전부와 txt 하나가 unreadable 이 아니다(갈고리 실수를 잡아 삼키면 여기서 먼저 드러난다)."""
    honest = [data for data, _ in SAMPLES.values()] + [text("[PAGE 1]", "가", "[PAGE 2]")]
    assert [page_count(data).reason for data in honest] == [None] * len(honest)


@pytest.mark.parametrize("mistake", [KeyError, IndexError, RuntimeError])
def test_a_mistake_in_the_hook_escapes_instead_of_unreadable(
    mistake: type[Exception], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: object, name: str, attributes: dict[str, str]) -> None:
        raise mistake("갈고리 실수")

    monkeypatch.setattr(page_tags._BodyText, "on_start", broken)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(mistake, match="갈고리 실수"):
        page_count(with_body(p("[PAGE 2]")))


def test_a_mistake_in_the_line_count_escapes_for_txt_too(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(text: str) -> list[int]:
        raise IndexError("셈 실수")

    monkeypatch.setattr(page_tags, "_tags_of", broken)
    with pytest.raises(IndexError, match="셈 실수"):
        page_count(text("[PAGE 2]"))
