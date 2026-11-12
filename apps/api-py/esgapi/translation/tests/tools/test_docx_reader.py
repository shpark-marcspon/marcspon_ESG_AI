"""docx 읽개(발주서 §3 S1·S4·S5 의 W11·W12·S9): 시험이 코드로 지은 docx → `read_docx` 의 글이 손으로 적은 기대 글과
같고(셀 7 규칙 — 근거 R/ 는 읽기판 보고서_AI번역_v3_1 의 줄), 공격 파일은 갈래로 거절되고 예외가 밖으로 안 나온다.
"""

import inspect
import io
import struct
import sys
import time
import zipfile
from collections.abc import Callable, Iterator

import pytest

from esgapi.translation.engines.colab_158.pipeline import source_and_pages
from esgapi.translation.tests.docx_support import (
    R_NS,
    built,
    document_xml,
    p,
    parts_of,
    tbl,
    tc,
    tr,
    vmerge_chain,
    with_body,
    zip_bytes,
)
from esgapi.translation.tests.engines.colab_158.support import make_input
from esgapi.translation.tools import docx_reader
from esgapi.translation.tools.docx_reader import DocxRejected, DocxText, read_docx

R = f'xmlns:r="{R_NS}"'
CT_MAIN = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_RT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def read(data: bytes) -> DocxText:
    result = read_docx(data)
    assert isinstance(result, DocxText), result
    return result


def refused(data: bytes) -> DocxRejected:
    result = read_docx(data)
    assert isinstance(result, DocxRejected), result
    return result


def cell(*paragraph_texts: str) -> str:
    """문단 여럿인 칸(칸 안 줄바꿈 — cell.text 가 문단을 `\\n` 으로 잇는다)."""
    inner = "".join(p(text) if text else "<w:p/>" for text in paragraph_texts)
    return f"<w:tc>{inner}</w:tc>"


# ── S1 읽기: 몸 → 글 (손으로 적은 기대 글) ──

S1_CASES: list[tuple[str, str, str]] = [
    (
        "문단·빈 문단·끝 공백·태그는 정규화 전 그대로",  # R/263-267 `.text.rstrip()`, 빈 문단 → 빈 줄. 정규화는 엔진(③)
        p("가상 회사 보고서") + "<w:p/>" + p("끝 공백   ") + p("**[PAGE 1]**"),
        "가상 회사 보고서\n\n끝 공백\n**[PAGE 1]**",
    ),
    (
        "표 앞에 태그가 없으면 끼움, 표 뒤 빈 줄",  # R/259-262
        p("앞") + tbl(tr(tc("가"), tc("나")), tr(tc("1"), tc("2"))),
        "앞\n[MARKDOWN_TABLE]\n| 가 | 나 |\n| --- | --- |\n| 1 | 2 |\n",
    ),
    (
        "표 앞 줄이 이미 태그면 안 끼움",  # R/259 `lines[-1].strip() != "[MARKDOWN_TABLE]"`
        p("[MARKDOWN_TABLE]") + tbl(tr(tc("가"))),
        "[MARKDOWN_TABLE]\n| 가 |\n| --- |\n",
    ),
    (
        "태그 앞뒤 빈칸도 strip 으로 같은 태그",  # R/259 의 .strip(), 문단은 rstrip 이라 앞 빈칸은 남는다
        p("  [MARKDOWN_TABLE]") + tbl(tr(tc("가"))),
        "  [MARKDOWN_TABLE]\n| 가 |\n| --- |\n",
    ),
    (
        "몸 첫 자식이 표",  # R/259 `not lines`
        tbl(tr(tc("가"))),
        "[MARKDOWN_TABLE]\n| 가 |\n| --- |\n",
    ),
    (
        "표 둘이 잇달면 둘째에도 태그(앞 줄이 빈 줄)",  # R/261-262
        tbl(tr(tc("가"))) + tbl(tr(tc("나"))),
        "[MARKDOWN_TABLE]\n| 가 |\n| --- |\n\n[MARKDOWN_TABLE]\n| 나 |\n| --- |\n",
    ),
    (
        "칸 안 줄바꿈 → <br>(잇단 것은 하나)",  # R/194 `re.sub(r'\n+', '<br>', t)`
        tbl(tr(cell("가", "", "나"))),
        "[MARKDOWN_TABLE]\n| 가<br>나 |\n| --- |\n",
    ),
    (
        "칸 안 | 는 &#124;, 빈칸·탭은 하나로",  # R/195-196
        tbl(tr(tc("가 | 나"), tc("다\t\t라   마"))),
        "[MARKDOWN_TABLE]\n| 가 &#124; 나 | 다 라 마 |\n| --- | --- |\n",
    ),
    (
        # R/204-205 `if any(cells)`, R/207-208 `if not rows: return []`, R/254-255
        "칸이 다 빈 행은 버림, 다 빈 표는 줄 0",
        p("앞") + tbl(tr(tc("가")), tr(tc(""))) + tbl(tr(tc(""), tc(""))) + p("뒤"),
        "앞\n[MARKDOWN_TABLE]\n| 가 |\n| --- |\n\n뒤",
    ),
    (
        "짧은 행은 빈 칸으로 채움",  # R/210-217
        tbl(tr(tc("가"), tc("나")), tr(tc("다"))),
        "[MARKDOWN_TABLE]\n| 가 | 나 |\n| --- | --- |\n| 다 |  |\n",
    ),
    (
        "가로 병합은 같은 글이 칸 수만큼(W12)",  # python-docx 1.2.0 `_Row.cells` — `range(tc.grid_span)`
        tbl(tr(tc("가", '<w:gridSpan w:val="2"/>')), tr(tc("1"), tc("2"))),
        "[MARKDOWN_TABLE]\n| 가 | 가 |\n| --- | --- |\n| 1 | 2 |\n",
    ),
    (
        "세로 병합의 이어진 칸은 위 칸 글(W12)",  # `_Row.cells` — vMerge continue 는 `_tc_above`
        tbl(tr(tc("가", '<w:vMerge w:val="restart"/>'), tc("나")), tr(tc("", "<w:vMerge/>"), tc("다"))),
        "[MARKDOWN_TABLE]\n| 가 | 나 |\n| --- | --- |\n| 가 | 다 |\n",
    ),
    (
        "탭은 글자 그대로, 끝 탭은 rstrip",  # R/264 `.rstrip()`
        "<w:p><w:r><w:t>가</w:t><w:tab/><w:t>나</w:t><w:tab/></w:r></w:p>",
        "가\t나",
    ),
    (
        "문단 안 줄바꿈(w:br)은 글의 \\n",  # python-docx Run.text 가 w:br 을 \n 으로
        "<w:p><w:r><w:t>가</w:t><w:br/><w:t>나</w:t></w:r></w:p>",
        "가\n나",
    ),
]


@pytest.mark.parametrize(("body", "expected"), [(b, e) for _, b, e in S1_CASES], ids=[c[0] for c in S1_CASES])
def test_the_structured_text_is_what_cell_7_writes_before_normalizing(body: str, expected: str) -> None:
    result = read(with_body(body))
    assert result.text == expected
    assert dict(result.skipped) == {}


def test_there_are_enough_reading_cases() -> None:
    assert len(S1_CASES) >= 12


def test_a_hyperlink_paragraph_reads_its_text_and_external_relationships_are_not_opened(
    blocked_network: list[object],
) -> None:
    """외부 관계(하이퍼링크·연결 그림·attachedTemplate — TargetMode External)는 거절이 아니라 읽힘. 소켓 시도 0."""
    parts = parts_of(built())
    rels = parts["word/_rels/document.xml.rels"].decode()
    extra = (
        f'<Relationship Id="rLink" Type="{OFFICE_RT}/hyperlink" Target="http://127.0.0.1:9/가상" '
        'TargetMode="External"/>'
        f'<Relationship Id="rImg" Type="{OFFICE_RT}/image" Target="http://127.0.0.1:9/a.png" TargetMode="External"/>'
    )
    parts["word/_rels/document.xml.rels"] = rels.replace("</Relationships>", extra + "</Relationships>").encode()
    parts["word/_rels/settings.xml.rels"] = (
        f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{REL_NS}">'
        f'<Relationship Id="rT" Type="{OFFICE_RT}/attachedTemplate" Target="http://127.0.0.1:9/t.dotx" '
        'TargetMode="External"/></Relationships>'
    ).encode()
    body = (
        '<w:p><w:r><w:t xml:space="preserve">가상 누리집 </w:t></w:r>'
        '<w:hyperlink r:id="rLink"><w:r><w:t>바로가기</w:t></w:r></w:hyperlink></w:p>'
    )
    parts["word/document.xml"] = document_xml(body, R)
    assert read(zip_bytes(parts)).text == "가상 누리집 바로가기"
    assert blocked_network == []


# ── ★f: 읽개 → 엔진 source_and_pages 의 글 = 코랩 셀 7 의 파일을 셀 17 이 읽은 글(정규화 한 번) ──

NORMALIZE_ONCE: list[tuple[str, str, str]] = [
    # 정규화가 바꾸는 꼴 둘(두 번 하면 또 바뀐다 — 멱등 아님), 그대로인 꼴 하나
    ("태그 강조 넷", p("****[PAGE 1]****") + p("본문"), "**[PAGE 1]**\n본문"),
    ("중괄호 줄", p("[PAGE 1]") + p("가") + p("{{{}{{{}나"), "[PAGE 1]\n가\n\n{{{}나"),
    ("그대로", p("[PAGE 1]") + p("가상 본문"), "[PAGE 1]\n가상 본문"),
]


@pytest.mark.parametrize(
    ("body", "expected"), [(b, e) for _, b, e in NORMALIZE_ONCE], ids=[c[0] for c in NORMALIZE_ONCE]
)
def test_the_engine_normalizes_the_read_text_exactly_once(body: str, expected: str) -> None:
    source_text, _, _ = source_and_pages(make_input(read(with_body(body)).text))
    assert source_text == expected


# ── S5 약점 W11(몸의 그 밖 자식은 빠지고 셈만) ──


def test_body_children_other_than_paragraphs_and_tables_are_skipped_and_counted() -> None:
    sdt = f"<w:sdt><w:sdtContent>{p('가상 목차')}</w:sdtContent></w:sdt>"
    result = read(with_body(p("앞") + sdt + p("뒤") + "<w:sectPr/>"))
    assert result.text == "앞\n뒤"  # 코랩도 sdt 안 글을 빼먹는다(R/233-238 — CT_P·CT_Tbl 만)
    assert dict(result.skipped) == {"sdt": 1}  # sectPr 은 세지 않는다


# ── S4 거절·안전 ──


def honest() -> dict[str, bytes]:
    return parts_of(built(lambda d: d.add_paragraph("가상 본문")))


def test_empty_and_too_many_bytes_and_not_a_zip() -> None:
    assert refused(b"").kind == "empty"
    assert refused(b"\0" * (docx_reader.MAX_BYTES + 1)).kind == "too_many_bytes"
    assert refused(b"not a zip").kind == "not_a_zip"
    assert refused(b"PK\x03\x04" + b"\0" * 40).kind == "not_a_zip"


def test_too_many_entries() -> None:
    parts = honest()
    for index in range(docx_reader.MAX_ENTRIES + 1 - len(parts)):
        parts[f"word/media/x{index}.bin"] = b"0"
    assert refused(zip_bytes(parts)).kind == "too_many_entries"
    parts.pop("word/media/x0.bin")
    assert isinstance(read_docx(zip_bytes(parts)), DocxText)  # 1,000 은 지난다


def _central_directory_bomb(entries: int) -> bytes:
    """지역 머리 하나 + 1바이트 이름의 가운데 항목 `entries` 개(모두 그 머리를 가리킴) + EOCD(zip64 표시 없음)."""
    local = struct.pack("<4s5H3L2H", b"PK\x03\x04", 20, 0, 0, 0, 0, 0, 0, 0, 1, 0) + b"a"
    central = struct.pack("<4s6H3L5H2L", b"PK\x01\x02", 20, 20, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0) + b"a"
    directory = central * entries
    end = struct.pack(
        "<4s4H2LH", b"PK\x05\x06", 0, 0, entries & 0xFFFF, entries & 0xFFFF, len(directory), len(local), 0
    )
    return local + directory + end


def _zip64_end_record(data: bytes) -> bytes:
    """끝 EOCD(주석 없음)의 항목 수를 0xFFFF(zip64 표시)로 바꾼 바이트."""
    head, end = data[:-22], list(struct.unpack("<4s4H2LH", data[-22:]))
    end[4] = 0xFFFF
    return head + struct.pack("<4s4H2LH", *end)


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: _central_directory_bomb(1_000_000), id="가운데 목록 47MB(1바이트 이름 100만 개)"),
        pytest.param(lambda: _central_directory_bomb(23_000), id="가운데 목록 1MiB 바로 위"),
        pytest.param(lambda: _zip64_end_record(zip_bytes(honest())), id="zip64 표시 EOCD"),
    ],
)
def test_a_central_directory_bomb_is_refused_before_zipfile_opens_it(
    build: Callable[[], bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """가운데 목록이 1MiB 넘거나 zip64 면 `zipfile.ZipFile` 을 짓기 전에 too_many_entries(밴드 TRS2, MARC-ISSUE-385 —
    ZipFile 은 여는 자리에서 목록 전체를 ZipInfo 로 풀어 44MB 파일 하나로 worker 메모리 +350MB 였다)."""
    data = build()
    assert len(data) <= docx_reader.MAX_BYTES

    def no_zipfile(*args: object, **kwargs: object) -> None:
        raise AssertionError("zipfile.ZipFile 을 지었다")

    monkeypatch.setattr(docx_reader.zipfile, "ZipFile", no_zipfile)
    assert refused(data).kind == "too_many_entries"


def test_a_central_directory_just_inside_the_limit_still_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    """앞 검사는 1MiB 안의 목록을 막지 않는다 — 항목 수 상한(_declared_sizes)이 그다음에 거른다."""
    data = _central_directory_bomb(22_000)  # 22,000 × 47 바이트 ≈ 0.99MiB
    opened: list[object] = []
    real = zipfile.ZipFile

    def counting(*args: object, **kwargs: object) -> zipfile.ZipFile:
        opened.append(args)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(docx_reader.zipfile, "ZipFile", counting)
    assert refused(data).kind == "too_many_entries"
    assert len(opened) == 1


def test_duplicate_entries_are_refused() -> None:
    buffer = io.BytesIO()
    with pytest.warns(UserWarning, match="Duplicate name"), zipfile.ZipFile(buffer, "w") as archive:
        for name, data in honest().items():
            archive.writestr(name, data)
        archive.writestr("word/document.xml", document_xml(p("가상 둘째")))
    assert refused(buffer.getvalue()).kind == "duplicate_entry"


def central_directory_patched(data: bytes, name: bytes, offset: int, value: bytes) -> bytes:
    """가운데 목록에서 이름이 `name` 인 항목 머리의 `offset` 바이트를 `value` 로 바꾼다."""
    out = bytearray(data)
    position = out.find(b"PK\x01\x02")
    patched = 0
    while position != -1:
        name_length = int.from_bytes(out[position + 28 : position + 30], "little")
        if bytes(out[position + 46 : position + 46 + name_length]) == name:
            out[position + offset : position + offset + len(value)] = value
            patched += 1
        position = out.find(b"PK\x01\x02", position + 4)
    assert patched == 1
    return bytes(out)


def test_an_entry_flagged_as_encrypted_is_refused() -> None:
    data = central_directory_patched(zip_bytes(honest()), b"word/document.xml", 8, b"\x01\x00")
    assert refused(data).kind == "encrypted_entry"


@pytest.mark.parametrize("method", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA], ids=["bzip2", "lzma"])
def test_compression_other_than_stored_or_deflated_is_refused(method: int) -> None:
    assert refused(zip_bytes(honest(), method)).kind == "unsupported_compression"
    assert isinstance(read_docx(zip_bytes(honest(), zipfile.ZIP_STORED)), DocxText)


def test_an_entry_or_the_declared_sum_over_the_limit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    data = zip_bytes(honest())
    largest = max(len(v) for v in honest().values())
    monkeypatch.setattr(docx_reader, "MAX_ENTRY_BYTES", largest - 1)
    assert refused(data).kind == "entry_too_large"
    monkeypatch.setattr(docx_reader, "MAX_ENTRY_BYTES", largest)
    total = sum(len(v) for v in honest().values())
    monkeypatch.setattr(docx_reader, "MAX_DECLARED_BYTES", total - 1)
    assert refused(data).kind == "declared_entries_too_large"
    monkeypatch.setattr(docx_reader, "MAX_DECLARED_BYTES", total)
    assert isinstance(read_docx(data), DocxText)


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int | None]]:
    """`ZipExtFile.read` 가 청받은 길이(선례 inventory/tests/test_s3sheets_reader_limits.py 의 엿보기)."""
    lengths: list[int | None] = []
    real_read = zipfile.ZipExtFile.read

    def recording_read(self: zipfile.ZipExtFile, n: int | None = -1) -> bytes:
        lengths.append(n)
        return real_read(self, n)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", recording_read)
    yield lengths


def test_an_entry_lying_about_its_size_is_refused_without_inflating_it_all(asked: list[int | None]) -> None:
    """선언 10 바이트·실제 1 MiB: 읽개는 선언 + 1 바이트까지만 청한다(끝까지 -1·None 을 청하지 않는다)."""
    parts = honest()
    parts["word/media/lie.bin"] = b"\0" * (1024 * 1024)
    data = zip_bytes(parts)
    data = central_directory_patched(data, b"word/media/lie.bin", 24, (10).to_bytes(4, "little"))
    asked.clear()  # 짓느라 청한 것은 뺀다
    rejection = refused(data)
    assert (rejection.kind, rejection.where) == ("unreadable_entry", "word/media/lie.bin")
    assert asked and all(n is not None and 0 <= n <= 1024 * 1024 + 1 for n in asked)
    assert 11 in asked


def test_an_honest_docx_asks_for_each_declared_size_plus_one_before_python_docx(
    asked: list[int | None], monkeypatch: pytest.MonkeyPatch
) -> None:
    parts = honest()
    seen: list[list[int | None]] = []
    real_open = docx_reader.Package.open

    def recording_open(stream: io.BytesIO) -> object:
        seen.append(list(asked))
        return real_open(stream)

    monkeypatch.setattr(docx_reader.Package, "open", recording_open)
    data = zip_bytes(parts)
    asked.clear()
    assert isinstance(read_docx(data), DocxText)
    assert sorted(n for n in seen[0] if n is not None) == sorted(len(v) + 1 for v in parts.values())


BILLION_LAUGHS = (
    '<?xml version="1.0"?><!DOCTYPE w:document [<!ENTITY a "가상가상가상"><!ENTITY b "&a;&a;&a;&a;&a;&a;">'
    '<!ENTITY c "&b;&b;&b;&b;&b;&b;">]>'
)


def test_a_doctype_in_the_main_document_is_refused() -> None:
    xml = (BILLION_LAUGHS + document_xml(p("&c;")).decode().split("?>", 1)[1]).encode()
    rejection = refused(with_body("", replace={"word/document.xml": xml}))
    assert (rejection.kind, rejection.where) == ("doctype", "word/document.xml")
    utf16 = xml.decode().replace('<?xml version="1.0"?>', '<?xml version="1.0" encoding="UTF-16"?>').encode("utf-16")
    assert refused(with_body("", replace={"word/document.xml": utf16})).kind == "doctype"  # 바이트 검색이 아니다


def test_a_doctype_with_an_external_entity_in_a_rels_part_is_refused() -> None:
    parts = honest()
    rels = parts["word/_rels/document.xml.rels"].decode()
    head, rest = rels.split("?>", 1)
    parts["word/_rels/document.xml.rels"] = (
        head
        + '?><!DOCTYPE Relationships [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        + rest.replace("</Relationships>", "<!-- &x; --></Relationships>")
    ).encode()
    rejection = refused(zip_bytes(parts))
    assert (rejection.kind, rejection.where) == ("doctype", "word/_rels/document.xml.rels")
    assert "root:" not in rejection.detail


def test_a_doctype_in_a_part_named_bin_but_typed_as_the_main_document_is_refused() -> None:
    """python-docx 는 이름이 아니라 내용 꼴로 파싱한다 — DOCTYPE 훑기 대상은 이름 ∪ [Content_Types].xml 꼴
    (개정 1 M2)."""
    parts = honest()
    document = parts.pop("word/document.xml")
    parts["word/document.bin"] = (BILLION_LAUGHS + document.decode().split("?>", 1)[1]).encode()
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(b"/word/document.xml", b"/word/document.bin")
    parts["_rels/.rels"] = parts["_rels/.rels"].replace(b"word/document.xml", b"word/document.bin")
    rejection = refused(zip_bytes(parts))
    assert (rejection.kind, rejection.where) == ("doctype", "word/document.bin")


def hidden_override_parts(doctype: bool) -> dict[str, bytes]:
    """본 문서를 `word/document.bin` 으로 옮기고 뿌리 직속 Override 는 WML main, 더 깊이 숨긴 Override 는
    바이트 꼴로."""
    parts = honest()
    document = parts.pop("word/document.xml")
    parts["word/document.bin"] = (
        (BILLION_LAUGHS + document.decode().split("?>", 1)[1]).encode() if doctype else document
    )
    hidden = '<Nest><Override PartName="/word/document.bin" ContentType="application/octet-stream"/></Nest>'
    types = parts["[Content_Types].xml"].replace(b"/word/document.xml", b"/word/document.bin")
    parts["[Content_Types].xml"] = types.replace(b"</Types>", hidden.encode() + b"</Types>")
    parts["_rels/.rels"] = parts["_rels/.rels"].replace(b"word/document.xml", b"word/document.bin")
    return parts


def test_a_hidden_deeper_override_does_not_split_the_content_type_map(monkeypatch: pytest.MonkeyPatch) -> None:
    """검증 B1: 뿌리 직속 자식만 꼴 지도에 든다(python-docx 와 같은 지도) — 더 깊이 숨긴 Override 로 XML 셈·DOCTYPE
    훑기 대상을 빗나가게 하지 못한다."""
    from docx.opc.packuri import PackURI
    from docx.opc.pkgreader import _ContentTypeMap  # pyright: ignore[reportPrivateUsage]

    types = hidden_override_parts(doctype=False)["[Content_Types].xml"]
    theirs = _ContentTypeMap.from_xml(types)[PackURI("/word/document.bin")]  # pyright: ignore[reportUnknownMemberType]
    _, overrides = docx_reader._content_types(types)  # pyright: ignore[reportPrivateUsage]
    assert overrides["/word/document.bin"] == theirs == CT_MAIN
    rejection = refused(zip_bytes(hidden_override_parts(doctype=True)))
    assert (rejection.kind, rejection.where) == ("doctype", "word/document.bin")
    parts = hidden_override_parts(doctype=False)
    counted = len(parts["word/document.bin"]) + sum(
        len(data)
        for name, data in parts.items()
        if name == "[Content_Types].xml" or name.endswith(".rels") or name in PARSED_NAMES
    )
    monkeypatch.setattr(docx_reader, "MAX_XML_BYTES", counted - 1)  # document.bin 이 파싱될 XML 로 세인다
    assert refused(zip_bytes(parts)).kind == "xml_too_large"


def test_content_types_whose_root_is_not_types_or_missing_attributes_are_unreadable() -> None:
    parts = honest()
    parts["[Content_Types].xml"] = (
        parts["[Content_Types].xml"].replace(b"<Types ", b"<Typez ").replace(b"</Types>", b"</Typez>")
    )
    rejection = refused(zip_bytes(parts))
    assert (rejection.kind, rejection.where) == ("unreadable_document", "[Content_Types].xml")
    parts = honest()
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
        b"</Types>", b'<Default Extension="x"/></Types>'
    )
    assert refused(zip_bytes(parts)) == DocxRejected(
        "unreadable_document", "[Content_Types].xml", "Default 에 필수 속성이 없다"
    )


def test_a_doctype_in_the_content_types_is_refused_first() -> None:
    parts = honest()
    head, rest = parts["[Content_Types].xml"].decode().split("?>", 1)
    parts["[Content_Types].xml"] = (head + "?><!DOCTYPE Types>" + rest).encode()
    assert refused(zip_bytes(parts)) == DocxRejected("doctype", "[Content_Types].xml", "DOCTYPE 선언(Types)이 있다")


def test_broken_xml_is_refused() -> None:
    assert refused(with_body("", replace={"word/document.xml": b"<w:document"})).kind == "broken_xml"


def test_a_macro_enabled_main_document_is_not_a_word_document() -> None:
    parts = honest()
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
        b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
        b"application/vnd.ms-word.document.macroEnabled.main+xml",
    )
    rejection = refused(zip_bytes(parts))
    assert rejection.kind == "not_a_word_document"
    assert "macroEnabled" in rejection.detail


def test_a_missing_content_types_entry_is_refused() -> None:
    parts = honest()
    del parts["[Content_Types].xml"]
    assert refused(zip_bytes(parts)) == DocxRejected("missing_entry", "[Content_Types].xml", "zip 에 그 항목이 없다")


def test_strict_ooxml_is_unreadable_with_a_detail() -> None:
    strict = "http://purl.oclc.org/ooxml/wordprocessingml/main"
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{strict}"><w:body>{p("가상")}</w:body></w:document>'
    rejection = refused(with_body("", replace={"word/document.xml": xml.encode()}))
    assert rejection.kind == "unreadable_document"
    assert "Strict OOXML" in rejection.detail


@pytest.mark.parametrize(("span", "measured"), [(2147483647, "2,147,483,647"), (0, "gridSpan 0"), (-1, "gridSpan -1")])
def test_a_grid_span_out_of_range_is_refused_before_reading(span: int, measured: str) -> None:
    """검사가 있을 때의 갈래 단언만(검사가 없으면 수백 GB — 개정 2 M2′)."""
    rejection = refused(with_body(tbl(tr(tc("가상", f'<w:gridSpan w:val="{span}"/>')))))
    assert (rejection.kind, rejection.where) == ("table_too_large", "표 1")
    assert measured in rejection.detail
    if span > 0:
        assert "상한 64" in rejection.detail  # 잰 값과 상한 둘 다(개정 2 N1)


def test_a_grid_span_of_a_million_is_refused() -> None:
    """심은 파손 P16 이 무는 경우: 검사가 없으면 칸 1,000,000 을 되풀이한다(수 초 — 스스로 끝난다). 5초 상한(개정 1
    B1)은 표 검사를 글 뽑기 뒤로 옮기는 파손도 잡는다(검증 B2)."""
    data = with_body(tbl(tr(tc("가상", '<w:gridSpan w:val="1000000"/>'))))
    start = time.perf_counter()
    rejection = refused(data)
    took = time.perf_counter() - start
    assert rejection == DocxRejected("table_too_large", "표 1", "행 폭 1,000,000 > 상한 64")
    assert took < 5.0, took


def test_negative_grid_before_is_refused_and_the_row_width_counts_before_and_after() -> None:
    assert refused(with_body(tbl(tr(tc("가"), props='<w:gridBefore w:val="-1"/>')))).kind == "table_too_large"
    edge = tr(tc("가", '<w:gridSpan w:val="62"/>'), props='<w:gridBefore w:val="1"/><w:gridAfter w:val="1"/>')
    assert isinstance(read_docx(with_body(tbl(edge))), DocxText)  # 1 + 62 + 1 = 64
    over = tr(tc("가", '<w:gridSpan w:val="62"/>'), props='<w:gridBefore w:val="1"/><w:gridAfter w:val="2"/>')
    assert refused(with_body(tbl(over))) == DocxRejected("table_too_large", "표 1", "행 폭 65 > 상한 64")


def test_the_table_cell_sum_counts_the_whole_document(monkeypatch: pytest.MonkeyPatch) -> None:
    data = with_body(tbl(tr(tc("가"), tc("나"))) + tbl(tr(tc("다"), tc("라"))))
    monkeypatch.setattr(docx_reader, "MAX_TABLE_CELLS", 4)
    assert isinstance(read_docx(data), DocxText)
    monkeypatch.setattr(docx_reader, "MAX_TABLE_CELLS", 3)
    assert refused(data) == DocxRejected("table_too_large", "표 2", "표 칸 합 4 > 상한 3")


def test_vertical_merge_chains_over_the_step_limit_are_refused() -> None:
    """심은 파손 P18 이 무는 경우(감독 처분 ★d): 600행 사슬 셋 = 되짚기 3 × 179,700 = 539,100 > 500,000. 셈은 넘는
    행에서 멈춘다(셋째 표 — 앞 둘 359,400 + 셋째의 140,715)."""
    rejection = refused(with_body(vmerge_chain(600) * 3))
    assert rejection == DocxRejected("vertical_merge_too_deep", "표 3", "세로 병합 되짚기 500,115 > 상한 500,000")


def test_vertical_merge_steps_are_counted_per_grid_column(monkeypatch: pytest.MonkeyPatch) -> None:
    chain = vmerge_chain(4)  # 되짚기 1 + 2 + 3 = 6
    monkeypatch.setattr(docx_reader, "MAX_VMERGE_STEPS", 6)
    assert isinstance(read_docx(with_body(chain)), DocxText)
    monkeypatch.setattr(docx_reader, "MAX_VMERGE_STEPS", 5)
    assert refused(with_body(chain)).kind == "vertical_merge_too_deep"
    restart = tr(tc("나", '<w:vMerge w:val="restart"/>'))
    monkeypatch.setattr(docx_reader, "MAX_VMERGE_STEPS", 3)  # restart 가 사슬을 끊는다: 1 + 2 + 0 + 1 = 4 > 3
    rows = (
        tr(tc("가", '<w:vMerge w:val="restart"/>'))
        + tr(tc("", "<w:vMerge/>")) * 2
        + restart
        + tr(tc("", "<w:vMerge/>"))
    )
    assert refused(with_body(tbl(rows))).detail == "세로 병합 되짚기 4 > 상한 3"


@pytest.fixture
def shallow_recursion() -> Iterator[None]:
    """재귀 상한을 지금 깊이 + 120 으로 낮춘다 — 사슬 수백 행으로 RecursionError 를 1초 안에(★d: 기본 상한이면
    사슬 약 900 행·15초)."""
    before = sys.getrecursionlimit()
    sys.setrecursionlimit(len(inspect.stack(0)) + 120)
    try:
        yield
    finally:
        sys.setrecursionlimit(before)


def test_a_long_vertical_merge_chain_that_recurses_too_deep_is_unreadable(shallow_recursion: None) -> None:
    rejection = refused(with_body(vmerge_chain(400)))
    assert rejection == DocxRejected("unreadable_document", "", "RecursionError")


def test_a_relationship_chain_499_deep_is_read() -> None:
    """관계 사슬(_walk_phys_parts 의 재귀 생성기): 항목 1,000 안의 가장 깊은 사슬도 RecursionError 없이 읽힌다(★d)."""
    parts = honest()
    custom = f"{OFFICE_RT}/customXml"
    depth = (docx_reader.MAX_ENTRIES - len(parts)) // 2
    assert depth >= 490
    rels = parts["word/_rels/document.xml.rels"].decode()
    parts["word/_rels/document.xml.rels"] = rels.replace(
        "</Relationships>", f'<Relationship Id="rC" Type="{custom}" Target="c/p0.xml"/></Relationships>'
    ).encode()
    for k in range(depth):
        parts[f"word/c/p{k}.xml"] = b"<a/>"
        if k + 1 < depth:
            parts[f"word/c/_rels/p{k}.xml.rels"] = (
                f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}"><Relationship Id="r" Type="{custom}" '
                f'Target="p{k + 1}.xml"/></Relationships>'
            ).encode()
    assert len(parts) <= docx_reader.MAX_ENTRIES
    assert read(zip_bytes(parts)).text == "가상 본문"


def test_the_parsed_xml_sum_over_eight_mib_is_refused_with_both_numbers() -> None:
    body = "<w:p/>" * ((docx_reader.MAX_XML_BYTES // len("<w:p/>")) + 1)
    rejection = refused(with_body(body))
    assert rejection.kind == "xml_too_large"
    assert "바이트 > 상한 8,388,608" in rejection.detail


def test_the_parsed_xml_sum_counts_only_what_python_docx_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    """셈 대상 = [Content_Types].xml + .rels + 여덟 꼴(개정 2 M1′). 다른 꼴의 XML(여기서는 customXml)은 세지 않는다."""
    parts = honest()
    counted = sum(
        len(data)
        for name, data in parts.items()
        if name == "[Content_Types].xml" or name.endswith(".rels") or name in PARSED_NAMES
    )
    parts["customXml/item9.xml"] = b"<a>" + b" " * 100_000 + b"</a>"
    data = zip_bytes(parts)
    monkeypatch.setattr(docx_reader, "MAX_XML_BYTES", counted)
    assert isinstance(read_docx(data), DocxText)
    monkeypatch.setattr(docx_reader, "MAX_XML_BYTES", counted - 1)
    assert refused(data).detail == f"파싱될 XML 합 {counted:,} 바이트 > 상한 {counted - 1:,}"


PARSED_NAMES = {
    "docProps/core.xml",
    "word/document.xml",
    "word/numbering.xml",
    "word/settings.xml",
    "word/styles.xml",
}
"""python-docx 기본 틀에서 여덟 꼴인 파트(손으로 적음 — 기본 틀에 comments·header·footer 는 없다)."""


def test_the_parsed_content_types_are_python_docx_registry() -> None:
    from docx.opc.part import PartFactory

    assert set(PartFactory.part_type_for) == docx_reader.PARSED_CONTENT_TYPES  # 판을 올리면 여기서 안다


def test_a_memory_error_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def out_of_memory(stream: io.BytesIO) -> object:
        raise MemoryError

    monkeypatch.setattr(docx_reader.Package, "open", out_of_memory)
    with pytest.raises(MemoryError):
        read_docx(zip_bytes(honest()))


def test_no_corrupted_byte_raises(blocked_network: list[object]) -> None:
    """어떤 바이트를 받아도 예외가 아니라 갈래다(xlsx 읽개 꼴 — 자리마다 비트를 뒤집는다)."""
    data = zip_bytes(honest())
    for position in range(0, len(data), max(1, len(data) // 300)):
        broken = bytearray(data)
        broken[position] ^= 1 << (position % 8)
        assert isinstance(read_docx(bytes(broken)), DocxText | DocxRejected)
    assert isinstance(read_docx(data[: len(data) // 2]), DocxRejected)
    assert blocked_network == []


# ── 가지 리뷰 B1: 꼴(content type)을 python-docx 와 같은 함수로 ────────────────────────

CT_RELS = "application/vnd.openxmlformats-package.relationships+xml"
NAMES = ["word/document.xml", "word/a.xml", "word/..xml", "word/doc.", "a.b/c", "word/.foo", "word/.xml", "WORD/X.XML"]


def tricky_types(*, empty_default: str | None) -> bytes:
    extra = "" if empty_default is None else f'<Default Extension="" ContentType="{empty_default}"/>'
    return (
        '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        f'<Default Extension="rels" ContentType="{CT_RELS}"/><Default Extension="xml" ContentType="application/xml"/>'
        f'<Default Extension="foo" ContentType="application/octet-stream"/>{extra}</Types>'
    ).encode()


@pytest.mark.parametrize("empty_default", [None, CT_MAIN])
def test_the_reader_resolves_content_types_exactly_as_python_docx(empty_default: str | None) -> None:
    """차등: 이름마다 읽개의 꼴 == python-docx `_ContentTypeMap`(없으면 둘 다 None). 확장자는 `PackURI.ext`
    (`posixpath.splitext` — `word/.foo` 는 확장자 `""`)."""
    from docx.opc.packuri import PackURI
    from docx.opc.pkgreader import _ContentTypeMap  # pyright: ignore[reportPrivateUsage]

    types = tricky_types(empty_default=empty_default)
    defaults, overrides = docx_reader._content_types(types)  # pyright: ignore[reportPrivateUsage]
    theirs_map = _ContentTypeMap.from_xml(types)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    for name in NAMES:
        try:
            theirs: str | None = theirs_map[PackURI(f"/{name}")]  # pyright: ignore[reportUnknownVariableType]
        except KeyError:
            theirs = None
        ours = docx_reader._content_type_of(name, defaults, overrides)  # pyright: ignore[reportPrivateUsage]
        assert ours == theirs, name
    if empty_default is not None:
        assert docx_reader._content_type_of("word/.foo", defaults, overrides) == CT_MAIN  # pyright: ignore[reportPrivateUsage]


def dotfile_main(document: bytes) -> bytes:
    """본문을 `word/.foo` 에 두고 `Default Extension=""` 으로 WML main 꼴을 준 문서(가지 리뷰 poc1·poc2)."""
    rels = (
        f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}"><Relationship Id="rId1" '
        f'Type="{OFFICE_RT}/officeDocument" Target="word/.foo"/></Relationships>'
    ).encode()
    return zip_bytes(
        {
            "[Content_Types].xml": tricky_types(empty_default=CT_MAIN),
            "_rels/.rels": rels,
            "word/.foo": document,
        }
    )


def test_a_dotfile_main_part_is_counted_against_the_xml_limit() -> None:
    body = p("가상") * ((docx_reader.MAX_XML_BYTES // len(p("가상"))) + 1)
    refused = read_docx(dotfile_main(document_xml(body)))
    assert isinstance(refused, DocxRejected)
    assert refused.kind == "xml_too_large"


def test_a_dotfile_main_part_is_scanned_for_doctype() -> None:
    doc = (
        b'<?xml version="1.0"?><!DOCTYPE w:document [<!ENTITY a "aaaa">]>'
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b"<w:body><w:p><w:r><w:t>&a;</w:t></w:r></w:p></w:body></w:document>"
    )
    refused = read_docx(dotfile_main(doc))
    assert isinstance(refused, DocxRejected)
    assert (refused.kind, refused.where) == ("doctype", "word/.foo")


def test_a_dotfile_main_part_that_is_honest_is_read() -> None:
    """같은 꼴이라도 작고 정직하면 python-docx 처럼 읽는다(거절이 아니라 셈·훑기 대상이 된 것)."""
    result = read_docx(dotfile_main(document_xml(p("가상 본문"))))
    assert isinstance(result, DocxText)
    assert result.text == "가상 본문"


def test_an_unknown_xml_encoding_is_refused_not_raised() -> None:
    """가지 리뷰 poc3: expat 이 모르는 encoding 은 LookupError — 밖으로 새지 않고 broken_xml."""
    doc = b'<?xml version="1.0" encoding="x-bogus"?><w:document/>'
    for data in (dotfile_main(doc), with_body("", replace={"word/document.xml": doc})):
        refused = read_docx(data)
        assert isinstance(refused, DocxRejected)
        assert refused.kind == "broken_xml" and refused.detail.startswith("LookupError")
