"""숫자 표기 규칙. 「이 글자가 값 후보인가, 값이면 얼마인가」를 정하는 유일한 자리다.

esg-lab `ts/reconcile/src/domain/notation.ts`(261줄)를 옮겼다. 값은 십진 문자열로만 낸다. 글자를 고치거나 추측하지
않는다.

표 칸은 칸 전체를 한 덩어리로 읽는다(`classify_cell`).
문장과 글 칸은 그 안의 숫자 덩어리를 하나씩 읽는다(`scan_numbers`).

★ 정규식은 JS 의 뜻 그대로 옮겼다(까닭은 `jstext.py` 머리말):
  `\\d` → `[0-9]` / `\\s` → `[{WS}]` / `$` → `\\Z`·`fullmatch` / `.` → 줄 끝 글자 넷을 뺀 글자 /
  `\\b`(JS 는 ASCII 낱말 기준이라 한글은 낱말 글자가 아니다) → `(?=[A-Za-z0-9_])` / `\\p{L}` → `str.isalpha()`.
  `scan_numbers` 는 글을 UTF-16 자리의 문자열로 바꿔 그 위에서 일한다: 자리(`start`·`end`)와 앞뒤 글의 창(12·14자)이 JS
  와 같다.
"""

import re
import unicodedata
from typing import Final

from esgapi.reconcile.calc.jstext import NOT_LINE_END, WS, from_units, js_trim, to_units
from esgapi.reconcile.calc.types import CellNotation, NotationFlag, NumberToken, ParsedNumber, SignRule, TokenKind

_S: Final = f"[{WS}]"  # JS 의 \s
_NS: Final = f"[^{WS}]"  # JS 의 \S

_DASHES: Final = re.compile(r"[-–—−‐‑ㅡ]+")
_NO_VALUE_WORDS: Final = frozenset({"n/a", "na", "해당없음", "해당사항없음", "미해당", "미집계", "미산정"})
_YEAR: Final = re.compile(r"(FY)?['’]?(19|20)[0-9]{2}(년|년도)?")
# notation.ts:49
NUMBER_BODY: Final = r"[0-9]{1,3}(?:,[0-9]{3})+(?![0-9])(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?"
_SINGLE: Final = re.compile(
    rf"(?P<lead>[-−–+△▲▼]?){_S}?(?P<open>\(?)(?P<num>{NUMBER_BODY})(?P<close>\)?){_S}?(?P<suffix>{NOT_LINE_END}*)"
)
_DATE: Final = re.compile(rf"(19|20)[0-9]{{2}}[.\-/]{_S}?[0-9]{{1,2}}([.\-/]{_S}?[0-9]{{1,2}})?\.?")
_RANGE: Final = re.compile(rf"[-−+]?(?:{NUMBER_BODY}){_S}?%?{_S}?[~∼〜\-–]{_S}?[-−+]?(?:{NUMBER_BODY}){_S}?(%|%p)?")
_DIGIT: Final = re.compile(r"[0-9]")
_FOUR_DIGITS: Final = re.compile(r"[0-9]{4}")
_VERSION: Final = re.compile(r"[0-9]+(\.[0-9]+){2,}")
_CLAUSE: Final = re.compile(r"[0-9]+(\([0-9]+\))+(\([가-힣]\))?[0-9]{0,2}")
_LEADING_ZERO: Final = re.compile(r"0[0-9]")
_WS_ANY: Final = re.compile(_S)
_WS_RUN: Final = re.compile(f"{_S}+")
_CONTROL: Final = re.compile("[\x00-\x1f]")

# 숫자 뒤에 와도 「숫자 하나짜리 칸」으로 보는 단위 접미. 낱말 목록이 아니라 꼴이다: 짧고, 숫자가 없거나 단위 기호 안의
# 숫자뿐이다.
# notation.ts:57
_UNIT_SUFFIX: Final = re.compile(
    r"(%p|%|배|[가-힣]{1,3}(?: [가-힣]{1,2})?|[A-Za-zµ㎡㎥℃°][A-Za-z0-9₂²³/·]{0,9}"
    r"|[가-힣]{1,2} ?[A-Za-z][A-Za-z0-9₂/]{0,9})"
)
# 단위 접미 꼴이어도 값이 아닌 것 (notation.ts:96)
_NOT_UNIT_SUFFIXES: Final = frozenset(
    {"년", "년도", "월", "일", "분기", "차", "호", "조", "항", "기", "회차", "위", "등급", "단계", "번", "쪽", "페이지"}
)


def normalize_text(text: str) -> str:
    """NFKC → 제어 글자(U+0000~001F)를 빈칸으로 → 빈칸 줄을 하나로 → 앞뒤 빈칸 떼기. (notation.ts:59-61)"""
    out = unicodedata.normalize("NFKC", text)
    out = _CONTROL.sub(" ", out)
    out = _WS_RUN.sub(" ", out)
    return js_trim(out)


def _digits_to_decimal(num: str) -> tuple[str, int]:
    plain = num.replace(",", "")
    int_part, _, frac = plain.partition(".")
    # 앞자리 0 은 값에서 지운다 (`0.5` 는 그대로, `007` 은 여기 오지 않는다).
    whole = re.sub(r"^0+(?=[0-9])", "", int_part)
    return (whole if frac == "" else f"{whole}.{frac}", len(frac))


_ZERO: Final = re.compile(r"0(\.0+)?")


def _apply_sign(value: str, negative: bool) -> str:
    if not negative or _ZERO.fullmatch(value):
        return value
    return f"-{value}"


_YEAR_INTEGER: Final = re.compile(r"(19|20)[0-9]{2}")


def _is_year_integer(num: str) -> bool:
    return _YEAR_INTEGER.fullmatch(num) is not None or num == "2100"


def _has_letter(text: str) -> bool:
    """JS 의 `/\\p{L}/u.test(text)`. `str.isalpha()` 는 일반 범주 L* 와 같다."""
    return any(ch.isalpha() for ch in text)


def classify_cell(raw: str) -> CellNotation:
    """표 칸 하나를 읽는다. (notation.ts:81-134)"""
    text = normalize_text(raw)
    if text == "":
        return CellNotation("blank", None)
    if _DASHES.fullmatch(text) or _WS_ANY.sub("", text).lower() in _NO_VALUE_WORDS:
        return CellNotation("no_value_marker", None)
    if not _DIGIT.search(text):
        return CellNotation("text", None)
    compact = _WS_ANY.sub("", text)
    if _YEAR.fullmatch(compact) and not _FOUR_DIGITS.fullmatch(compact):
        return CellNotation("year", None)
    if _DATE.fullmatch(text):
        return CellNotation("date", None)
    if _VERSION.fullmatch(text):
        return CellNotation("code", None)

    single = _SINGLE.fullmatch(text)
    if single:
        lead, opening, num, closing = single["lead"], single["open"], single["num"], single["close"]
        paren_ok = (opening == "(") == (closing == ")")
        suffix = js_trim(single["suffix"])
        suffix_ok = suffix == "" or (_UNIT_SUFFIX.fullmatch(suffix) is not None and suffix not in _NOT_UNIT_SUFFIXES)
        if paren_ok and suffix_ok and not (opening == "(" and lead != ""):
            # 앞자리 0 인 정수 (`04`, `007`) 는 번호다.
            if _LEADING_ZERO.match(num):
                return CellNotation("code", None)
            flags: list[NotationFlag] = []
            sign: SignRule = "none"
            negative = False
            if opening == "(":
                sign = "paren_negative"
                negative = True
                flags.append("paren_negative_assumed")
            elif lead in ("-", "−", "–"):
                sign = "minus"
                negative = True
            elif lead == "+":
                sign = "plus"
            elif lead == "△":
                sign = "triangle_negative"
                negative = True
                flags.append("triangle_negative")
            elif lead in ("▲", "▼"):
                sign = "triangle_ambiguous"
                flags.append("sign_ambiguous")
            value, decimals = _digits_to_decimal(num)
            percent = suffix in ("%", "%p")
            if suffix == "" and sign == "none" and _is_year_integer(num):
                flags.append("year_like")
            return CellNotation(
                "value",
                ParsedNumber(
                    value=_apply_sign(value, negative),
                    decimals=decimals,
                    sign=sign,
                    percent=percent,
                    unit_suffix=None if suffix == "" else suffix,
                    flags=tuple(flags),
                ),
            )
    if _YEAR.fullmatch(compact):
        return CellNotation("year", None)
    if _RANGE.fullmatch(text):
        return CellNotation("range", None)
    if _CLAUSE.fullmatch(compact):
        return CellNotation("code", None)
    if not _has_letter(text.replace("%p", "")):
        return CellNotation("multi_number", None)
    return CellNotation("text_with_digits", None)


# ── 문장 속 숫자 ────────────────────────────────────────────────────────────

# 숫자 바로 뒤가 아니면 어디서든 덩어리를 시작한다 (`10,20,30%` 의 20 과 30 도 남긴다). notation.ts:161
_TOKEN: Final = re.compile(rf"(?<![0-9])({NUMBER_BODY})(%p|%)?")
# 숫자에 붙은 로마자 단위 꼴 (`28MW`, `34.4ton`). 한 글자(`3R`)나 글자 뒤에 숫자가 오는 꼴(`24X365`)은 식별자다.
# notation.ts:163
_LATIN_UNIT_AFTER: Final = re.compile(r"([A-Za-zµ][A-Za-z₂]{1,9}(?:/[A-Za-z]{1,6})?)(?![A-Za-z0-9])")
# notation.ts:164
_LABEL_BEFORE: Final = re.compile(
    r"(Scope|Category|CAT|Cat|GRI|ISO|IFRS|SASB|TCFD|KSSB|ESRS|SDGs?|Tier|Level|Phase|No\.?|Step|Type|Class|Annex"
    rf"|스코프|카테고리)[{WS}.\-]?\Z"
)
# notation.ts:165 의 `위\b`·`기\b`·`종\b`: JS 의 `\b` 는 `u` 플래그여도 ASCII 낱말 글자([A-Za-z0-9_]) 기준이다.
# 한글은 낱말 글자가 아니므로 「위 뒤의 경계」는 「바로 뒤가 ASCII 낱말 글자」와 같다. 파이썬의 `\b` 는 한글을 낱말로
# 보아 정반대다.
_JS_WORD_NEXT: Final = "(?=[A-Za-z0-9_])"
_ORDINAL_AFTER: Final = re.compile(
    rf"(차|단계|위{_JS_WORD_NEXT}|등급|호|번|조|항|기{_JS_WORD_NEXT}|회차|순위|세대|종{_JS_WORD_NEXT})"
)
# notation.ts:166-169
_UNIT_AFTER: Final = re.compile(
    r" ?((?:십|백|천|만|억|조){0,3} ?"
    r"(?:원|톤|명|건|개월|개사|개소|개|시간|배|회|년|일|주|kWh|MWh|GWh|TJ|GJ|MJ|tCO2eq|tCO2e|tCO₂eq|tCO₂e|kg|㎡|㎥|m3|m2|km|L|ℓ)"
    r"(?=\Z|[^A-Za-z0-9가-힣]"
    r"|(?:이다|이며|이고|입니다|으로|에서|까지|부터|이|가|은|는|을|를|의|과|와|로|에|씩|도)(?![가-힣])"
    r"|(?:이다|이며|이고|입니다)))"
)
_URL_SPAN: Final = re.compile(rf"{_NS}*(?:https?:|www\.|@){_NS}*")
_DATE_SPAN: Final = re.compile(r"(?<![0-9])(?:19|20)[0-9]{2}[.\-/] ?[0-9]{1,2}(?:[.\-/] ?[0-9]{1,2})?(?![0-9,])")

_LATIN_OR_SUB2: Final = re.compile(r"[A-Za-z₂]")
_LATIN: Final = re.compile(r"[A-Za-z]")
_DIGIT_HYPHEN_END: Final = re.compile(r"[0-9]-\Z")
_HYPHEN_DIGIT: Final = re.compile(r"-[0-9]")
_DIGIT_DOT_END: Final = re.compile(r"[0-9]\.\Z")
_DATE_DOT_END: Final = re.compile(r"(19|20)[0-9]{2}\.([0-9]{1,2}\.)?\Z")
_RANGE_AFTER: Final = re.compile(r" ?[~∼〜]")
_HANGUL_OR_LATIN: Final = re.compile(r"[가-힣A-Za-z]")
_MARKER_PREV: Final = re.compile(rf"[({WS}·,]")
_ONE_OR_TWO_DIGITS: Final = re.compile(r"[0-9]{1,2}")
_TWO_DIGITS: Final = re.compile(r"[0-9]{2}")
_DOT_SPACE_NONDIGIT: Final = re.compile(rf"\.{_S}+[^0-9]")
_LINE_HEAD: Final = re.compile(rf"(?:^|\n)[{WS}·•\-]*\Z")
_JO_DIGIT: Final = re.compile(r"조 ?[0-9]")
_YEAR_AFTER: Final = re.compile(r"(년|년도)(?!간|차| ?이상| ?이하| ?동안| ?연속| ?만에)")
_APOSTROPHE_END: Final = re.compile(r"['’]\Z")
_MONTH_DAY_AFTER: Final = re.compile(r"(월|일)(?!간| ?평균)")
_MONTH_END: Final = re.compile(r"월 ?\Z")
_SIGN_BEFORE: Final = re.compile(rf"(?:^|[{WS}(])([-−△▲▼+])\Z")

# 앞뒤 글을 보는 창 (notation.ts:191-192). UTF-16 자리로 센다.
_BEFORE_WINDOW: Final = 12
_AFTER_WINDOW: Final = 14


def _count_occurrences(text: str, needle: str, before: int) -> int:
    count = 0
    at = text.find(needle)
    while at != -1 and at <= before:
        count += 1
        at = text.find(needle, at + 1)
    return count


def _token_kind(
    text: str,
    start: int,
    end: int,
    num: str,
    pct: str,
    url_spans: list[tuple[int, int]],
    date_spans: list[tuple[int, int]],
) -> TokenKind:
    """덩어리 하나의 갈래. 가지의 **차례가 뜻이다** (notation.ts:196-214 의 차례 그대로)."""
    before = text[max(0, start - _BEFORE_WINDOW) : start]
    after = text[end : end + _AFTER_WINDOW]
    prev = before[-1:]
    following = after[:1]
    no_pct = pct == ""

    if any(start >= a and end <= b for a, b in url_spans):
        return "identifier"
    if any(a <= start < b for a, b in date_spans):
        return "date_part"
    if _LATIN_OR_SUB2.search(prev) or _LABEL_BEFORE.search(before):
        return "identifier"
    if (prev == "-" and _DIGIT_HYPHEN_END.search(before)) or (following == "-" and _HYPHEN_DIGIT.match(after)):
        return "identifier"
    if prev == "." and _DIGIT_DOT_END.search(before):
        return "date_part" if _DATE_DOT_END.search(before) else "identifier"
    if prev in ("~", "∼") or _RANGE_AFTER.match(after):
        return "range_part"
    if (
        no_pct
        and following == ")"
        and (_HANGUL_OR_LATIN.search(prev) or prev == "" or _MARKER_PREV.search(prev))
        and len(num) <= 2
        and "." not in num
    ):
        return "marker"
    if (
        no_pct
        and _ONE_OR_TWO_DIGITS.fullmatch(num)
        and _DOT_SPACE_NONDIGIT.match(after)
        and _LINE_HEAD.search(text[:start])
    ):
        return "marker"
    if no_pct and before.endswith("제"):
        return "ordinal"
    unit_after = _UNIT_AFTER.match(after) is not None
    # `333.6조 원`, `187조 9,673억 원` 의 조는 순번(제3조)이 아니라 수 단위다.
    if no_pct and _ORDINAL_AFTER.match(after) and not unit_after and not _JO_DIGIT.match(after) and "," not in num:
        return "ordinal"
    if no_pct and _YEAR_AFTER.match(after) and _is_year_integer(num):
        return "year"
    if no_pct and _APOSTROPHE_END.search(before) and _TWO_DIGITS.fullmatch(num):
        return "year"
    if (
        no_pct
        and _MONTH_DAY_AFTER.match(after)
        and _ONE_OR_TWO_DIGITS.fullmatch(num)
        and (after.startswith("월") or _MONTH_END.search(before))
    ):
        return "date_part"
    if no_pct and _is_year_integer(num) and not unit_after and not _LATIN.search(following):
        return "year"
    if no_pct and _LATIN.match(after) and not unit_after and not _LATIN_UNIT_AFTER.match(after):
        return "identifier"
    if _LEADING_ZERO.match(num):
        return "identifier"
    return "value"


def scan_numbers(text: str) -> list[NumberToken]:
    """글 한 덩어리에서 숫자 덩어리를 전부 찾아 갈래를 붙인다. 숫자 글자는 어느 덩어리엔가 들어간다(버리지 않는다).

    `start`·`end` 는 UTF-16 자리다 (notation.ts:182-247).
    """
    units = to_units(text)
    tokens: list[NumberToken] = []
    url_spans = [m.span() for m in _URL_SPAN.finditer(units)]
    date_spans = [m.span() for m in _DATE_SPAN.finditer(units)]
    for match in _TOKEN.finditer(units):
        num: str = match[1]
        pct: str = match[2] or ""
        start, end = match.span()
        kind = _token_kind(units, start, end, num, pct, url_spans, date_spans)

        number: ParsedNumber | None = None
        if kind == "value":
            before = units[max(0, start - _BEFORE_WINDOW) : start]
            after = units[end : end + _AFTER_WINDOW]
            flags: list[NotationFlag] = []
            sign: SignRule = "none"
            negative = False
            # 부호는 숫자 바로 앞에 붙어 있고 그 앞이 글자·숫자가 아닐 때만 숫자의 것으로 본다.
            sign_match = _SIGN_BEFORE.search(before)
            if sign_match:
                sign_char: str = sign_match[1]
                start -= len(sign_char)
                if sign_char in ("-", "−"):
                    sign = "minus"
                    negative = True
                elif sign_char == "+":
                    sign = "plus"
                elif sign_char == "△":
                    sign = "triangle_negative"
                    negative = True
                    flags.append("triangle_negative")
                else:
                    sign = "triangle_ambiguous"
                    flags.append("sign_ambiguous")
            value, decimals = _digits_to_decimal(num)
            unit: str | None
            if pct != "":
                unit = pct
            else:
                unit_match = _UNIT_AFTER.match(after)
                latin_match = _LATIN_UNIT_AFTER.match(after)
                unit = js_trim(unit_match[1]) if unit_match else latin_match[1] if latin_match else None
            number = ParsedNumber(
                value=_apply_sign(value, negative),
                decimals=decimals,
                sign=sign,
                percent=pct != "",
                unit_suffix=unit,
                flags=tuple(flags),
            )
        raw = units[start:end]
        tokens.append(
            NumberToken(
                raw=from_units(raw),
                start=start,
                end=end,
                occurrence=_count_occurrences(units, raw, start),
                kind=kind,
                number=number,
            )
        )
    return tokens


def locate_quote(text: str, quote: str, occurrence: int) -> tuple[int, int, int] | None:
    """원문 글자 `quote` 가 `text` 에서 `occurrence` 번째로 나오는 자리 `(start, end, total)`. 없으면 None. 자리는
    UTF-16.

    (notation.ts:250-261)
    """
    if quote == "" or type(occurrence) is not int or occurrence < 1:
        return None
    units = to_units(text)
    needle = to_units(quote)
    total = 0
    found: int | None = None
    at = units.find(needle)
    while at != -1:
        total += 1
        if total == occurrence:
            found = at
        at = units.find(needle, at + 1)
    return None if found is None else (found, found + len(needle), total)
