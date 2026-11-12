"""코드 검사 넷과 안정 열쇠(순수 함수, AI 0). 결과는 이름 있는 dataclass 이고 result@2 의 errorCode 로 옮기는 것은
흐름의 모음이 한다(엔진은 계약을 모른다).

  quote_in_block    정규화(NFC + 공백 전부 지움) 뒤 대상 문장 ⊂ 대상 블록 글을 읽는 차례로 이은 글
  evidence_in_pool  판정이 인용한 근거 단락 id ⊂ 그 항목의 근거 풀(판정에 보여 준 단락)
  category_in_list  카테고리가 판 목록 안. 목록이 비면 null 만
  level_rule        Low 는 E0 선언문 규칙(heuristics.is_low_declarative)이 참인 문장에만
  stable_key        sha256(문서 sha · NFC+공백 접기 문장 · 쪽) 앞 32자

정규화가 둘인 까닭: 블록 경계·줄 바꿈은 PDF 가 낱말 안에도 넣어(띄어쓰기 없는 한국어 줄 끊김) 포함 검사는 공백을 다
지운 글로 본다. 열쇠는 사람이 읽는 문장의 같음이라 공백을 한 칸으로 접기만 한다.
"""

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from esgapi.greenwash.engines.e0.heuristics import is_low_declarative

STABLE_KEY_CHARS: Final = 32

CheckName = Literal["quote_in_block", "evidence_in_pool", "category_in_list", "level_rule"]
Failure = Literal["quote_not_found", "evidence_outside_pool", "category_unknown", "level_rule_broken"]
JudgeLevel = Literal["High", "Mid", "Low", "None"]

_SPACE: Final = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class CheckResult:
    """검사 하나의 결과. ok 가 거짓이면 failure 가 그 이름이고 offending 이 걸린 값(근거 id 등)."""

    name: CheckName
    ok: bool
    failure: Failure | None
    offending: tuple[str, ...] = ()


def fold(text: str) -> str:
    """NFC + 공백 한 칸으로 접기 + 앞뒤 공백 지움(열쇠·짝의 같음)."""
    return _SPACE.sub(" ", unicodedata.normalize("NFC", text or "")).strip()


def squash(text: str) -> str:
    """NFC + 공백 전부 지움(포함 검사)."""
    return _SPACE.sub("", unicodedata.normalize("NFC", text or ""))


def stable_key(document_sha256: str, sentence: str, page: int) -> str:
    """실행을 넘어 같은 문장을 가리키는 열쇠. 공백·NFC 만 다른 문장은 같고, 쪽·문서가 다르면 다르다."""
    raw = f"{document_sha256}\n{fold(sentence)}\n{page}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:STABLE_KEY_CHARS]


def _result(name: CheckName, failure: Failure, bad: Sequence[str]) -> CheckResult:
    return CheckResult(name=name, ok=not bad, failure=failure if bad else None, offending=tuple(bad))


def quote_in_block(sentence: str, block_texts: Sequence[str]) -> CheckResult:
    """block_texts = 대상 블록 글(읽는 차례). 빈 문장·빈 블록 목록은 실패다."""
    needle = squash(sentence)
    hay = squash("".join(block_texts))
    ok = bool(needle) and bool(block_texts) and needle in hay
    return _result("quote_in_block", "quote_not_found", () if ok else (fold(sentence)[:40],))


def evidence_in_pool(cited: Iterable[str], pool: Iterable[str]) -> CheckResult:
    allowed = set(pool)
    bad = [c for c in dict.fromkeys(cited) if c not in allowed]
    return _result("evidence_in_pool", "evidence_outside_pool", bad)


def category_in_list(category: str | None, allowed: Sequence[str]) -> CheckResult:
    ok = category is None or (bool(allowed) and category in allowed)
    return _result("category_in_list", "category_unknown", () if ok else (category or "",))


def level_rule(level: JudgeLevel, sentence: str) -> CheckResult:
    """Low 는 E0 선언문 규칙이 참일 때만. 그 반대(규칙이 참인데 High·Mid·None)는 막지 않는다 — 판정이 근거를 보고
    다르게 볼 수 있다(E0 는 규칙이 참이면 판정 없이 Low 로 정했다. 이 판은 판정에 맡긴다)."""
    ok = level != "Low" or is_low_declarative(sentence)
    return _result("level_rule", "level_rule_broken", () if ok else (level,))


def first_failure(results: Sequence[CheckResult]) -> Failure | None:
    """검사 차례(문장 → 근거 → 카테고리 → 등급)에서 처음 걸린 것."""
    return next((r.failure for r in results if not r.ok), None)
