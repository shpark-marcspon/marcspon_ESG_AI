# pyright: basic
# ↑ 타입 표기가 없는 GW1 사본(engines/e0 의 사본 열)의 함수 넷에 꼴을 입히는 얇은 겉. 부르기만 한다 — flows 는 strict.
"""engines/e0 사본 열의 타입 표기 없는 함수 넷을 꼴 있는 이름으로 내보낸다(flows/colab_e0.py 가 strict 로 부르게).
추가 단어(G1c)의 비교 키와 빈도 목록에 더할 것도 여기서 engines/e0/wordcount 의 정규화로 정한다."""

from collections import Counter
from collections.abc import Sequence
from typing import Any, Final

from langchain_core.documents import Document

from esgapi.greenwash.engines.e0 import dryrun, heuristics, parts, wordcount
from esgapi.greenwash.engines.e0.ports import TokenCounter


def set_env_keywords(extra_keywords: Sequence[str] | None, include_general_env: bool) -> None:
    heuristics.set_env_keywords(extra_keywords=extra_keywords, include_general_env=include_general_env)


def dry_run(
    docs: list[Document], pages: list[int], allowed_pages: list[int], config: dict[str, Any], counter: TokenCounter
) -> dict[str, Any]:
    return dryrun.dry_run(docs, pages, allowed_pages, config, counter)


def build_results_by_part(
    results: list[dict[str, Any]], section_pages: dict[str, list[int]]
) -> dict[str, list[dict[str, Any]]]:
    return parts.build_results_by_part(results, section_pages)


GREEN_TERMS: Final[tuple[str, ...]] = tuple(wordcount.GREEN_TERMS)
"""노트북의 의심 낱말 목록(빠진 쉼표로 붙은 낱말까지 그대로)."""


def count_green_terms(
    docs: list[Document], terms: Sequence[str] = GREEN_TERMS
) -> tuple[Counter[str], list[tuple[int, Counter[str]]]]:
    return wordcount.count_green_terms_in_docs(docs, list(terms))


def term_key(term: str) -> str:
    """추가 단어의 비교 키: wordcount.normalize_term(소문자, `-_/·•∙` 를 공백으로, 공백 정리)에서 공백까지 지운 것.
    빈도 패턴이 띄어쓰기 변형을 허용하므로(build_flexible_pattern) 「탄소 중립」과 「탄소중립」은 같은 키다."""
    return wordcount.normalize_term(term).replace(" ", "")


def frequency_extras(extra_terms: Sequence[str]) -> list[str]:
    """추가 단어 가운데 빈도 목록에 더할 것: 비교 키가 GREEN_TERMS 의 어느 낱말의 키와도 같지 않은 것(두 번 세지
    않게). 글자 그대로의 비교라 노트북 목록에서 붙어 버린 낱말의 조각(「eco」 ≠ 「eco프리」)은 더해진다."""
    base = {term_key(t) for t in GREEN_TERMS}
    return [t for t in extra_terms if term_key(t) not in base]
