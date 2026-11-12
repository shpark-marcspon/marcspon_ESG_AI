# pyright: basic
# ↑ services/parser/tests/pdfbuild.py 의 사본(타입 표기 없는 꼴 그대로라 strict 를 끈다). 선례 tests/conftest.py.
"""테스트용 PDF 를 표준 라이브러리만으로 짓는다 (PDF 연산자를 직접 쓴다. PDF 라이브러리를 쓰지 않는다).

출처: esg-app `services/parser/tests/pdfbuild.py`(main `6d93b84` 시점, 마지막 변경 `3249180`)의 사본 —
밴드 G1d(MARC-TICK-103, 감독 결정 5).
services 는 고치지 않고 다른 패키지를 import 하지 않으려고 옮겨 적었다. 줄인 것: 그림(선·사각형·곡선·원·이미지·폼·
음영), 목차, 암호(RC4·MD5), PNG 읽기. 바꾼 것: 파일 id 를 MD5 대신 sha256 앞 16바이트로 짓는다(암호와 무관한 값).
남은 짓기 코드(글 놓기·글꼴·쪽 상자·직렬화)는 원본과 같다.

좌표: 이 도구가 받는 좌표는 전부 **쪽의 왼쪽 위가 원점, y 는 아래로, 단위 pt** 다.
PDF 파일에는 왼쪽 아래 원점으로 뒤집어 적는다. `add_content` 로 넣는 날 연산자만 PDF 의 좌표(왼쪽 아래 원점) 그대로다.

글꼴은 **파일을 심지 않는다**:
- `LATIN`("helv"): 표준 14 글꼴 Helvetica 를 이름으로만 가리킨다. 글자 너비는 Adobe 의 Helvetica AFM 값
  (`HELV_WIDTHS`)이고 pdfium 은 제가 품은 대체 글꼴의 같은 너비로 읽는다(원본 쪽 `test_pdfbuild.py` 가 견준다).
- `KOREAN`("kor"): 글꼴 파일 없는 Type0(CIDFontType2, Identity-H) + ToUnicode. 너비는 글꼴 사전의 /W 가 정한다
  (U+0020~U+007E 는 0.5em, 그 밖은 1em). 글리프가 없으므로 그림은 비지만 글자와 자리는 읽힌다.
"""

import hashlib
import math

LATIN, KOREAN = "helv", "kor"

# Adobe Core 14 Helvetica AFM 의 글자 너비 (1/1000 em). 출처: Adobe Font Metrics, Helvetica.afm (Core 14).
_HELV_RUN = [
    278,
    278,
    355,
    556,
    556,
    889,
    667,
    191,
    333,
    333,
    389,
    584,
    278,
    333,
    278,
    278,  # 0x20~0x2F
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    278,
    278,
    584,
    584,
    584,
    556,  # 0x30~0x3F
    1015,
    667,
    667,
    722,
    722,
    667,
    611,
    778,
    722,
    278,
    500,
    667,
    556,
    833,
    722,
    778,  # 0x40~0x4F
    667,
    778,
    722,
    667,
    611,
    722,
    667,
    944,
    667,
    667,
    611,
    278,
    278,
    278,
    469,
    556,  # 0x50~0x5F
    333,
    556,
    556,
    500,
    556,
    556,
    278,
    556,
    556,
    222,
    222,
    500,
    222,
    833,
    556,
    556,  # 0x60~0x6F
    556,
    556,
    333,
    500,
    278,
    556,
    500,
    722,
    500,
    500,
    500,
    334,
    260,
    334,
    584,
]  # 0x70~0x7E
HELV_WIDTHS = {chr(0x20 + i): w for i, w in enumerate(_HELV_RUN)}
HELV_WIDTHS.update({" ": 278, "•": 350, "·": 278, "–": 556, "—": 1000})
KOR_ASCII_WIDTH, KOR_WIDE_WIDTH = 500, 1000
KOR_ASCENT, KOR_DESCENT = 880, -120


def text_length(text, fontsize=10, font=LATIN):
    """글의 너비(pt). 이 도구가 놓는 다음 글자의 자리와 같다."""
    if font == LATIN:
        return sum(HELV_WIDTHS[c] for c in text) * fontsize / 1000
    if font == KOREAN:
        return sum(KOR_ASCII_WIDTH if 0x20 <= ord(c) <= 0x7E else KOR_WIDE_WIDTH for c in text) * fontsize / 1000
    raise ValueError(f"모르는 글꼴: {font}")


def _n(v):
    """수를 PDF 에 적는 꼴로 (소수 여섯째 자리까지, 끝의 0 은 뗀다)."""
    s = f"{float(v):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _rgb(c, op):
    return f"{_n(c[0])} {_n(c[1])} {_n(c[2])} {op}"


class _S:
    """PDF 문자열."""

    def __init__(self, data):
        self.data = data


class Page:
    def __init__(self, width, height, parent=None, number=0):
        self.width, self.height = width, height
        self.parent, self.number = parent, number  # 든 문서와 그 안의 차례(0부터)
        self.ops = []
        self.fonts = set()
        self.cropbox = None
        self.rotation = 0

    # ── 글 ──────────────────────────────────────────────────────────────

    def insert_text(self, at, text, fontsize=10, font=LATIN, color=None, rotate=0):
        """(x, y) 를 바닥선의 왼쪽 끝으로 글을 놓는다. 글 객체 하나가 된다.

        rotate: 도. 양수면 글이 반시계로 돈다 (90 이면 아래에서 위로 읽는 글).
        """
        self.fonts.add(font)
        x, y = at
        data = text.encode("cp1252") if font == LATIN else text.encode("utf-16-be")
        c, s = math.cos(math.radians(rotate)), math.sin(math.radians(rotate))
        tm = f"{_n(c)} {_n(s)} {_n(-s)} {_n(c)} {_n(x)} {_n(self.height - y)} Tm"
        fill = _rgb(color, "rg") + " " if color is not None else ""
        self.ops.append(f"q {fill}BT {tm} /{font} {_n(fontsize)} Tf <{data.hex()}> Tj ET Q".encode("ascii"))

    # ── 날 연산자·쪽 상자 ──────────────────────────────────────────────

    def add_content(self, raw):
        """날 연산자를 내용 스트림 끝에 덧붙인다. 좌표는 PDF 의 것(왼쪽 아래 원점) 그대로다."""
        self.ops.append(raw if isinstance(raw, bytes) else raw.encode("ascii"))

    def set_cropbox(self, rect):
        self.cropbox = tuple(rect)

    def set_rotation(self, degrees):
        self.rotation = degrees

    def content(self):
        return b"\n".join(self.ops) + b"\n"


class Doc:
    def __init__(self):
        self.pages = []

    def new_page(self, width=400, height=300):
        page = Page(width, height, self, len(self.pages))
        self.pages.append(page)
        return page

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.tobytes())
        return path

    def tobytes(self):
        out = _Out()
        catalog, pages = out.alloc(), out.alloc()
        numbers = [out.alloc() for _ in self.pages]
        for page, n in zip(self.pages, numbers, strict=False):
            h = page.height
            body = f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {_n(page.width)} {_n(h)}]"
            if page.cropbox:
                x0, y0, x1, y1 = page.cropbox
                body += f" /CropBox [{_n(x0)} {_n(h - y1)} {_n(x1)} {_n(h - y0)}]"
            if page.rotation:
                body += f" /Rotate {page.rotation}"
            contents = out.add_stream("", page.content())
            out.set(n, [body + " /Resources ", *out.resources(page), f" /Contents {contents} 0 R >>"])
        out.set(pages, [f"<< /Type /Pages /Count {len(numbers)} /Kids [{' '.join(f'{n} 0 R' for n in numbers)}] >>"])
        out.set(catalog, [f"<< /Type /Catalog /Pages {pages} 0 R >>"])
        return out.serialize(catalog)


class _Out:
    """객체 번호를 주고 파일로 적는다."""

    def __init__(self):
        self.objs: list = [None]  # 0번은 비운다(사본에서 붙인 표기 — pyright 가 list[None] 으로 짐작하지 않게)
        self.font_numbers = {}

    def alloc(self):
        self.objs.append(None)
        return len(self.objs) - 1

    def set(self, n, body, stream=None):
        self.objs[n] = (body, stream)

    def add(self, body, stream=None):
        n = self.alloc()
        self.set(n, body, stream)
        return n

    def add_stream(self, inner, data):
        return self.add([f"<< {inner} /Length {len(data)} >>"], data)

    def font(self, name):
        if name in self.font_numbers:
            return self.font_numbers[name]
        if name == LATIN:
            n = self.add(["<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"])
        elif name == KOREAN:
            rows = "\n".join(f"<{hi:02X}00> <{hi:02X}FF> <{hi:02X}00>" for hi in range(256))
            cmap = (
                "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
                "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
                "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
                + "".join(
                    f"{len(chunk)} beginbfrange\n" + "\n".join(chunk) + "\nendbfrange\n"
                    for chunk in (rows.split("\n")[i : i + 100] for i in range(0, 256, 100))
                )
                + "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
            ).encode("ascii")
            to_unicode = self.add_stream("", cmap)
            descriptor = self.add(
                [
                    "<< /Type /FontDescriptor /FontName /PdfbuildGothic /Flags 4 "
                    f"/FontBBox [0 {KOR_DESCENT} 1000 {KOR_ASCENT}] "
                    f"/ItalicAngle 0 /Ascent {KOR_ASCENT} /Descent {KOR_DESCENT} /CapHeight 700 /StemV 80 >>"
                ]
            )
            descendant = self.add(
                [
                    "<< /Type /Font /Subtype /CIDFontType2 /BaseFont /PdfbuildGothic /CIDSystemInfo << /Registry ",
                    _S(b"Adobe"),
                    " /Ordering ",
                    _S(b"Identity"),
                    f" /Supplement 0 >> /FontDescriptor {descriptor} 0 R "
                    f"/DW {KOR_WIDE_WIDTH} /W [32 126 {KOR_ASCII_WIDTH}] /CIDToGIDMap /Identity >>",
                ]
            )
            n = self.add(
                [
                    f"<< /Type /Font /Subtype /Type0 /BaseFont /PdfbuildGothic /Encoding /Identity-H "
                    f"/DescendantFonts [{descendant} 0 R] /ToUnicode {to_unicode} 0 R >>"
                ]
            )
        else:
            raise ValueError(f"모르는 글꼴: {name}")
        self.font_numbers[name] = n
        return n

    def resources(self, page):
        """쪽의 자원 사전을 이루는 조각들(이 사본은 글꼴만)."""
        parts = ["<<"]
        if page.fonts:
            parts.append(" /Font << " + " ".join(f"/{k} {self.font(k)} 0 R" for k in sorted(page.fonts)) + " >>")
        parts.append(" >>")
        return parts

    def serialize(self, catalog):
        file_id = hashlib.sha256(repr([(b, s) for b, s in map(_plain, self.objs[1:])]).encode("utf-8")).digest()[:16]
        buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for n in range(1, len(self.objs)):
            body, stream = self.objs[n]
            offsets.append(len(buf))
            buf += f"{n} 0 obj\n".encode("ascii")
            for part in body:
                if isinstance(part, _S):
                    buf += b"<" + part.data.hex().encode("ascii") + b">"
                else:
                    buf += part.encode("ascii") if isinstance(part, str) else part
            if stream is not None:
                buf += b"\nstream\n" + stream + b"\nendstream"
            buf += b"\nendobj\n"
        xref = len(buf)
        buf += f"xref\n0 {len(self.objs)}\n".encode("ascii") + b"0000000000 65535 f \n"
        for off in offsets[1:]:
            buf += f"{off:010d} 00000 n \n".encode("ascii")
        trailer = f"<< /Size {len(self.objs)} /Root {catalog} 0 R /ID [<{file_id.hex()}> <{file_id.hex()}>]"
        buf += f"trailer\n{trailer} >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
        return bytes(buf)


def _plain(obj):
    body, stream = obj
    return [p.data if isinstance(p, _S) else p for p in body], stream
