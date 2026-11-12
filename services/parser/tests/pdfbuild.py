"""테스트용 PDF 를 표준 라이브러리만으로 짓는다 (PDF 연산자를 직접 쓴다. PDF 라이브러리를 쓰지 않는다).

원본(esg-lab `py/docparse/tests/`)은 PDF 라이브러리로 PDF 를 지었다. 여기서는 그 라이브러리를 들이지 않으려고 필요한 만큼만 직접 쓴다.

좌표: 이 도구가 받는 좌표는 전부 **쪽의 왼쪽 위가 원점, y 는 아래로, 단위 pt** 다 (분해기가 내는 좌표와 같다).
PDF 파일에는 왼쪽 아래 원점으로 뒤집어 적는다. `add_content` 로 넣는 날 연산자만 PDF 의 좌표(왼쪽 아래 원점) 그대로다.

글꼴은 **파일을 심지 않는다**:
- `LATIN`("helv"): 표준 14 글꼴 Helvetica 를 이름으로만 가리킨다. 글자 너비는 Adobe 의 Helvetica AFM 값(`HELV_WIDTHS`)이고
  pdfium 은 제가 품은 대체 글꼴의 같은 너비로 읽는다 (`test_pdfbuild.py` 가 글자마다 견준다).
- `KOREAN`("kor"): 글꼴 파일 없는 Type0(CIDFontType2, Identity-H) + ToUnicode. 너비는 글꼴 사전의 /W 가 정한다
  (U+0020~U+007E 는 0.5em, 그 밖은 1em). 글리프가 없으므로 그림은 비지만 글자와 자리는 읽힌다.

암호: 표준 보안 처리기 V1/R2 (RC4 40비트). 표준 라이브러리의 MD5 와 여기 적은 RC4 로 쓴다.
"""

import hashlib
import math
import struct
import zlib

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
    """PDF 문자열. 암호를 걸면 이것과 스트림만 암호화된다."""

    def __init__(self, data):
        self.data = data


def _utf16(text):
    return _S(b"\xfe\xff" + text.encode("utf-16-be"))


class Page:
    def __init__(self, width, height, parent=None, number=0):
        self.width, self.height = width, height
        self.parent, self.number = parent, number  # 든 문서와 그 안의 차례(0부터)
        self.ops = []
        self.fonts = set()
        self.xobjects = {}  # 이름 → ("image", w, h, bytes) | ("form", Page)
        self.shadings = {}  # 이름 → 사전 글
        self.gstates = {}  # 이름 → 사전 글
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

    # ── 벡터 그림 ───────────────────────────────────────────────────────

    def _paint(self, path, fill, color, width, fill_opacity=None):
        """경로 하나를 칠한다. fill·color 가 다 있으면 한 번에 채우고 긋는다(`B`)."""
        head = []
        if fill_opacity is not None:
            name = f"GS{len(self.gstates)}"
            self.gstates[name] = f"<< /Type /ExtGState /ca {_n(fill_opacity)} >>"
            head.append(f"/{name} gs")
        if fill is not None:
            head.append(_rgb(fill, "rg"))
        if color is not None:
            head.append(_rgb(color, "RG"))
            head.append(f"{_n(width)} w")
        op = (
            "B"
            if fill is not None and color is not None
            else "f"
            if fill is not None
            else "S"
            if color is not None
            else "n"
        )
        self.ops.append(("q " + " ".join([*head, path, op]) + " Q").encode("ascii"))

    def _pt(self, p):
        return f"{_n(p[0])} {_n(self.height - p[1])}"

    def draw_rect(self, rect, fill=None, color=(0, 0, 0), width=1, fill_opacity=None):
        """네모 연산자 `re` 하나."""
        x0, y0, x1, y1 = rect
        self._paint(f"{_n(x0)} {_n(self.height - y1)} {_n(x1 - x0)} {_n(y1 - y0)} re", fill, color, width, fill_opacity)

    def draw_line(self, a, b, color=(0, 0, 0), width=1):
        self._paint(f"{self._pt(a)} m {self._pt(b)} l", None, color, width)

    def draw_polyline(self, points, color=(0, 0, 0), width=1, fill=None, close=False):
        """`m l l …` 그리고 close 면 `h`."""
        path = f"{self._pt(points[0])} m " + " ".join(f"{self._pt(p)} l" for p in points[1:]) + (" h" if close else "")
        self._paint(path, fill, color, width)

    def draw_bezier(self, p1, p2, p3, p4, color=(0, 0, 0), width=1):
        self._paint(f"{self._pt(p1)} m {self._pt(p2)} {self._pt(p3)} {self._pt(p4)} c", None, color, width)

    def draw_circle(self, center, radius, fill=None, color=(0, 0, 0), width=1):
        """곡선 넷으로 그린 원."""
        cx, cy = center
        k = 0.5522847498 * radius
        r = radius
        pts = [
            ((cx + r, cy + k), (cx + k, cy + r), (cx, cy + r)),
            ((cx - k, cy + r), (cx - r, cy + k), (cx - r, cy)),
            ((cx - r, cy - k), (cx - k, cy - r), (cx, cy - r)),
            ((cx + k, cy - r), (cx + r, cy - k), (cx + r, cy)),
        ]
        path = (
            f"{self._pt((cx + r, cy))} m "
            + " ".join(f"{self._pt(a)} {self._pt(b)} {self._pt(c)} c" for a, b, c in pts)
            + " h"
        )
        self._paint(path, fill, color, width)

    # ── 그림, 폼, 음영, 날 연산자 ───────────────────────────────────────

    def insert_image(self, rect, gray=180, pixels=(30, 20)):
        """한 가지 회색으로 찬 RGB 그림을 rect 에 늘여 놓는다 (그림 XObject)."""
        w, h = pixels
        name = f"Im{len(self.xobjects)}"
        self.xobjects[name] = ("image", w, h, bytes([gray]) * (w * h * 3))
        x0, y0, x1, y1 = rect
        self.ops.append(
            f"q {_n(x1 - x0)} 0 0 {_n(y1 - y0)} {_n(x0)} {_n(self.height - y1)} cm /{name} Do Q".encode("ascii")
        )

    def show_form(self, rect, src):
        """다른 쪽(`src`)을 폼 XObject 로 rect 에 줄여(늘여) 붙인다. 폼의 행렬은 배율과 옮김이다."""
        name = f"Fm{len(self.xobjects)}"
        self.xobjects[name] = ("form", src)
        x0, y0, x1, y1 = rect
        sx, sy = (x1 - x0) / src.width, (y1 - y0) / src.height
        self.ops.append(f"q {_n(sx)} 0 0 {_n(sy)} {_n(x0)} {_n(self.height - y1)} cm /{name} Do Q".encode("ascii"))

    def add_shading(self, name, dictionary):
        """자원 사전의 /Shading 에 음영 하나를 더한다 (`/name sh` 로 쓴다)."""
        self.shadings[name] = dictionary

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
        self.toc = []

    def new_page(self, width=400, height=300):
        page = Page(width, height, self, len(self.pages))
        self.pages.append(page)
        return page

    def set_toc(self, entries):
        """[[수준(1부터), 제목, 쪽(1부터. -1 이면 가리키는 쪽 없음)]] 또는 넷째 자리에 {"uri": 주소}."""
        self.toc = [list(e) for e in entries]

    def save(self, path, user_pw=None, owner_pw=None):
        with open(path, "wb") as f:
            f.write(self.tobytes(user_pw=user_pw, owner_pw=owner_pw))
        return path

    def tobytes(self, user_pw=None, owner_pw=None):
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
        outlines = self._outlines(out, numbers)
        out.set(
            catalog,
            [f"<< /Type /Catalog /Pages {pages} 0 R" + (f" /Outlines {outlines} 0 R" if outlines else "") + " >>"],
        )
        return out.serialize(catalog, user_pw, owner_pw)

    def _outlines(self, out, page_numbers):
        if not self.toc:
            return None
        root = out.alloc()
        nodes = [{"n": out.alloc(), "entry": e, "kids": [], "parent": None} for e in self.toc]
        tops, stack = [], []
        for node in nodes:
            level = node["entry"][0]
            del stack[level - 1 :]
            (stack[-1]["kids"] if stack else tops).append(node)
            node["parent"] = stack[-1]["n"] if stack else root
            stack.append(node)

        def link(siblings):
            for i, node in enumerate(siblings):
                _level, title, target = node["entry"][:3]
                body = ["<< /Title ", _utf16(title), f" /Parent {node['parent']} 0 R"]
                if i:
                    body.append(f" /Prev {siblings[i - 1]['n']} 0 R")
                if i + 1 < len(siblings):
                    body.append(f" /Next {siblings[i + 1]['n']} 0 R")
                if node["kids"]:
                    body.append(
                        f" /First {node['kids'][0]['n']} 0 R /Last {node['kids'][-1]['n']} 0 R /Count {len(node['kids'])}"
                    )
                extra = node["entry"][3] if len(node["entry"]) > 3 else None
                if extra and "uri" in extra:
                    body += [" /A << /S /URI /URI ", _S(extra["uri"].encode("ascii")), " >>"]
                elif target >= 1:
                    body.append(f" /Dest [{page_numbers[target - 1]} 0 R /XYZ 0 {_n(self.pages[target - 1].height)} 0]")
                out.set(node["n"], [*body, " >>"])
                link(node["kids"])

        link(tops)
        out.set(root, [f"<< /Type /Outlines /First {tops[0]['n']} 0 R /Last {tops[-1]['n']} 0 R /Count {len(tops)} >>"])
        return root


class _Out:
    """객체 번호를 주고 파일로 적는다."""

    def __init__(self):
        self.objs = [None]
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
                    f"<< /Type /FontDescriptor /FontName /PdfbuildGothic /Flags 4 /FontBBox [0 {KOR_DESCENT} 1000 {KOR_ASCENT}] "
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
        """쪽(또는 폼이 된 쪽)의 자원 사전을 이루는 조각들."""
        parts = ["<<"]
        if page.fonts:
            parts.append(" /Font << " + " ".join(f"/{k} {self.font(k)} 0 R" for k in sorted(page.fonts)) + " >>")
        if page.xobjects:
            refs = []
            for name, x in page.xobjects.items():
                if x[0] == "image":
                    n = self.add_stream(
                        f"/Type /XObject /Subtype /Image /Width {x[1]} /Height {x[2]} /ColorSpace /DeviceRGB /BitsPerComponent 8",
                        x[3],
                    )
                else:
                    src = x[1]
                    data = src.content()
                    n = self.add(
                        [
                            f"<< /Type /XObject /Subtype /Form /BBox [0 0 {_n(src.width)} {_n(src.height)}] /Resources ",
                            *self.resources(src),
                            f" /Length {len(data)} >>",
                        ],
                        data,
                    )
                refs.append(f"/{name} {n} 0 R")
            parts.append(" /XObject << " + " ".join(refs) + " >>")
        if page.shadings:
            parts.append(" /Shading << " + " ".join(f"/{k} {v}" for k, v in page.shadings.items()) + " >>")
        if page.gstates:
            parts.append(" /ExtGState << " + " ".join(f"/{k} {v}" for k, v in page.gstates.items()) + " >>")
        parts.append(" >>")
        return parts

    def serialize(self, catalog, user_pw, owner_pw):
        file_id = hashlib.md5(repr([(b, s) for b, s in map(_plain, self.objs[1:])]).encode("utf-8")).digest()
        key, encrypt = None, None
        if user_pw is not None:
            user, owner = _pad(user_pw), _pad(owner_pw if owner_pw is not None else user_pw)
            permissions = struct.pack("<i", -4)
            o = _rc4(hashlib.md5(owner).digest()[:5], user)
            key = hashlib.md5(user + o + permissions + file_id).digest()[:5]
            u = _rc4(key, _PAD)
            encrypt = self.add([f"<< /Filter /Standard /V 1 /R 2 /O <{o.hex()}> /U <{u.hex()}> /P -4 >>"])
        buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for n in range(1, len(self.objs)):
            body, stream = self.objs[n]
            object_key = None
            if key is not None and n != encrypt:
                object_key = hashlib.md5(key + struct.pack("<I", n)[:3] + b"\x00\x00").digest()[:10]
            offsets.append(len(buf))
            buf += f"{n} 0 obj\n".encode("ascii")
            for part in body:
                if isinstance(part, _S):
                    data = _rc4(object_key, part.data) if object_key else part.data
                    buf += b"<" + data.hex().encode("ascii") + b">"
                else:
                    buf += part.encode("ascii") if isinstance(part, str) else part
            if stream is not None:
                buf += b"\nstream\n" + (_rc4(object_key, stream) if object_key else stream) + b"\nendstream"
            buf += b"\nendobj\n"
        xref = len(buf)
        buf += f"xref\n0 {len(self.objs)}\n".encode("ascii") + b"0000000000 65535 f \n"
        for off in offsets[1:]:
            buf += f"{off:010d} 00000 n \n".encode("ascii")
        trailer = f"<< /Size {len(self.objs)} /Root {catalog} 0 R /ID [<{file_id.hex()}> <{file_id.hex()}>]"
        if encrypt:
            trailer += f" /Encrypt {encrypt} 0 R"
        buf += f"trailer\n{trailer} >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
        return bytes(buf)


def _plain(obj):
    body, stream = obj
    return [p.data if isinstance(p, _S) else p for p in body], stream


_PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")


def _pad(password):
    return (password.encode("latin-1") + _PAD)[:32]


def _rc4(key, data):
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) & 0xFF
        s[i], s[j] = s[j], s[i]
    out = bytearray()
    i = j = 0
    for byte in data:
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        out.append(byte ^ s[(s[i] + s[j]) & 0xFF])
    return bytes(out)


# ── PNG 읽기 (렌더 테스트가 점의 색을 본다) ─────────────────────────────


def png_size(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def png_pixel(data, x, y):
    """PNG(8비트, 회색·RGB·RGBA, 엇갈림 없음)의 (x, y) 점. 채널 값의 튜플."""
    width, _height, depth, kind, _c, _f, interlace = struct.unpack(">IIBBBBB", data[16:29])
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[kind]
    assert depth == 8 and interlace == 0, (depth, interlace)
    idat, pos = b"", 8
    while pos < len(data):
        length, tag = struct.unpack(">I4s", data[pos : pos + 8])
        if tag == b"IDAT":
            idat += data[pos + 8 : pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * channels
    prev = bytearray(stride)
    for row in range(y + 1):
        start = row * (stride + 1)
        kind_of_filter, line = raw[start], bytearray(raw[start + 1 : start + 1 + stride])
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if kind_of_filter == 1:
                line[i] = (line[i] + a) & 0xFF
            elif kind_of_filter == 2:
                line[i] = (line[i] + b) & 0xFF
            elif kind_of_filter == 3:
                line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif kind_of_filter == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        prev = line
    return tuple(prev[x * channels : (x + 1) * channels])
