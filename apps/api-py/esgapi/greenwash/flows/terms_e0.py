"""AI 설정 판의 대상 단어(밴드 G2d, 결정 MARC-ENT-394) — 받기·켠 낱말·빈도 목록 합·sha. 순수(DB·I/O 0).

판의 「대상 단어」는 의심 낱말 빈도 목록(engines/e0/wordcount.GREEN_TERMS 자리) **하나만** 바꾼다. 판정할 문장을 고르는
환경 신호(heuristics.DEFAULT_ENV_KEYWORDS)에는 넣지 않는다 — 그쪽은 코드 고정이고 실행 옵션 extraTerms 만 닿는다(G1c).

    accept_terms(given)          {text, enabled} 목록 → AcceptedTerms | TermsRefused(code·문장·칸 경로)
    terms_input(accepted)        저장 칸의 정규형(받은 차례, text strip)
    used_terms(accepted)         켠 낱말(판 차례) — 빈도에 셀 기준 목록
    extras_beyond(base, extra)   extra 가운데 비교 키(gw1.term_key)가 base 의 키에 없는 것(받은 차례).
                                 base = GREEN_TERMS 면 gw1.frequency_extras 와 같다
    terms_sha256(used)           versions.termsSha256

받기 차례(발주서 K6 — 만들 때 services 와 워커의 끼움이 같은 함수를 부른다): 글(앞 칸부터) → 비교 키 겹침 → 개수 →
켠 것. 글 = strip 뒤 1~30자 · 괄호·따옴표 0 · NUL·짝 없는 서로게이트·제어·서식(보이지 않는) 글자 0
(criteria_e0.INVISIBLE) · 비교 키에 글자·숫자 ≥ 1. 겹침은 뒤 것의 칸 경로. 개수 = 켠 것·끈 것 다 센 수 ≤ 100.
켠 것 0 이면 거절.
규칙은 colab_e0.accept_extra_terms(G1c)를 따르되 부르지 않는다(그쪽은 겹침을 버리고 이쪽은 거절한다 — 처분 W2).
거절은 값이다(TermsRefused). code 는 대문자 TERMS_*(나갈 때 그대로), field 는 422 의 fields 와 같은 점 경로.
"""

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from esgapi.greenwash.contracts.terms_shapes import GreenwashTerm
from esgapi.greenwash.engines.e0.gw1 import term_key
from esgapi.greenwash.flows.criteria_e0 import INVISIBLE

TERMS_MAX: Final = 100
TERM_CHARS: Final = 30
TERM_REFUSED: Final = re.compile(r"[(){}\[\]\"'“”‘’]")
"""괄호·따옴표(colab_e0.EXTRA_TERM_REFUSED 와 같은 글자 — 시험이 견준다)."""

MESSAGES: Final = {
    "TERMS_SHAPE": "대상 단어 목록의 꼴이 맞지 않아요",
    "TERMS_TEXT_LENGTH": f"대상 단어는 1~{TERM_CHARS}자로 써 주세요",
    "TERMS_TEXT_INVISIBLE": "대상 단어에는 줄바꿈이나 보이지 않는 글자를 쓸 수 없어요",
    "TERMS_TEXT_BRACKET": "대상 단어에는 괄호나 따옴표를 쓸 수 없어요",
    "TERMS_TEXT_NO_LETTER": "대상 단어에는 글자나 숫자가 하나 이상 있어야 해요",
    "TERMS_DUPLICATE": "같은 대상 단어를 두 번 넣을 수 없어요(띄어쓰기·대소문자만 다른 것도 같아요)",
    "TERMS_COUNT": f"대상 단어는 {TERMS_MAX}개까지 넣을 수 있어요",
    "TERMS_NONE_ENABLED": "사용하는 대상 단어를 하나 이상 남겨 주세요",
}
"""문장(화면에 그대로 보일 꼴). 글 규칙 넷은 code 가 TERMS_TEXT 하나다."""


@dataclass(frozen=True, slots=True)
class AcceptedTerms:
    """받은 대상 단어(정규형 — text strip, 받은 차례)."""

    terms: tuple[GreenwashTerm, ...]


@dataclass(frozen=True, slots=True)
class TermsRefused:
    """대상 단어 받기 거절. code 는 TERMS_*, message 는 화면에 보일 한 문장, field 는 어긴 칸의 점 경로."""

    code: str
    message: str
    field: str


def _text_refused(text: str) -> str | None:
    """글 규칙을 어긴 문장의 열쇠(MESSAGES). 맞으면 None. text 는 strip 한 값."""
    if any(unicodedata.category(char) in INVISIBLE for char in text):
        return "TERMS_TEXT_INVISIBLE"
    if not 1 <= len(text) <= TERM_CHARS:
        return "TERMS_TEXT_LENGTH"
    if TERM_REFUSED.search(text):
        return "TERMS_TEXT_BRACKET"
    if not any(char.isalnum() for char in term_key(text)):
        return "TERMS_TEXT_NO_LETTER"
    return None


def _shape(given: object) -> list[tuple[str, bool]] | None:
    """[{text: str, enabled: bool}, …] 이면 (text, enabled) 목록. 아니면 None(본문은 422 가 먼저 막는다 — 저장 칸을
    다시 받을 때의 그물)."""
    if not isinstance(given, list):
        return None
    pairs: list[tuple[str, bool]] = []
    for item in cast("list[object]", given):
        if not isinstance(item, dict):
            return None
        found = cast("dict[object, object]", item)
        text, enabled = found.get("text"), found.get("enabled")
        if set(found) != {"text", "enabled"} or not isinstance(text, str) or not isinstance(enabled, bool):
            return None
        pairs.append((text, enabled))
    return pairs


def accept_terms(given: object) -> AcceptedTerms | TermsRefused:
    """받기(머리말의 차례). given 은 본문 꼴을 지난 목록이거나 저장 칸 값이다."""
    pairs = _shape(given)
    if pairs is None:
        return TermsRefused("TERMS_SHAPE", MESSAGES["TERMS_SHAPE"], "terms")
    stripped = [(text.strip(), enabled) for text, enabled in pairs]
    for i, (text, _enabled) in enumerate(stripped):
        refused = _text_refused(text)
        if refused is not None:
            return TermsRefused("TERMS_TEXT", MESSAGES[refused], f"terms.{i}.text")
    seen: set[str] = set()
    for i, (text, _enabled) in enumerate(stripped):
        key = term_key(text)
        if key in seen:
            return TermsRefused("TERMS_DUPLICATE", MESSAGES["TERMS_DUPLICATE"], f"terms.{i}.text")
        seen.add(key)
    if len(stripped) > TERMS_MAX:
        return TermsRefused("TERMS_COUNT", MESSAGES["TERMS_COUNT"], "terms")
    if not any(enabled for _text, enabled in stripped):
        return TermsRefused("TERMS_NONE_ENABLED", MESSAGES["TERMS_NONE_ENABLED"], "terms")
    return AcceptedTerms(tuple({"text": text, "enabled": enabled} for text, enabled in stripped))


def terms_input(accepted: AcceptedTerms) -> list[GreenwashTerm]:
    """저장 칸의 값(받은 정규형 그대로 — 기본 목록과 같아도 접지 않는다)."""
    return [{"text": term["text"], "enabled": term["enabled"]} for term in accepted.terms]


def used_terms(accepted: AcceptedTerms) -> tuple[str, ...]:
    """켠 낱말(판 차례)."""
    return tuple(term["text"] for term in accepted.terms if term["enabled"])


def extras_beyond(base: Sequence[str], extra: Sequence[str]) -> list[str]:
    """extra 가운데 비교 키가 base 의 어느 낱말의 키와도 같지 않은 것(받은 차례 — 두 번 세지 않게)."""
    keys = {term_key(t) for t in base}
    return [t for t in extra if term_key(t) not in keys]


def terms_sha256(used: Sequence[str]) -> str:
    """versions.termsSha256 — 켠 낱말 목록(차례째)의 JSON(ensure_ascii=False, 빈칸 없는 구분)의 sha256."""
    text = json.dumps(list(used), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
