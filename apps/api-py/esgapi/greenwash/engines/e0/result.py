"""GW1 의 결과 조립 함수 다섯 — esg-lab `py/greenwash/result.py`(main 2a237d2)의 item_json·counts_json·
word_counts_json·config_json·chunk_defaults 의 본문을 그대로 옮겼다(타입 표기만 이 저장소의 꼴로).

GW1 의 result.py 는 사본 열(test_copy_ast 고정)에 넣지 않는다: GW1 의 결과 꼴(schema_version 0.1)과 jsonschema 검증은
여기서 쓰지 않는다. greenwash.result@1 로 옮기는 것(span → position, example_sentence·counts·report)은
flows/colab_e0.py 의 report 단계가 한다.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from esgapi.greenwash.engines.e0 import checker as checker_mod
from esgapi.greenwash.engines.e0.checker import GWConfig
from esgapi.greenwash.engines.e0.ports import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL


def config_json(cfg: GWConfig, chunk_config: dict[str, Any]) -> dict[str, Any]:
    c = asdict(cfg)
    c["report_levels"] = list(c["report_levels"])
    return {
        "checker": c,
        "chunking": {
            "chunk_size": chunk_config["chunk_size"],
            "chunk_overlap": chunk_config["chunk_overlap"],
            "separators": list(chunk_config["separators"]),
            "normalize": chunk_config["normalize"],
            "embedding_batch_size": chunk_config["embedding_batch_size"],
        },
        "chat": {"temperature": checker_mod.TEMPERATURE, "max_tokens": checker_mod.MAX_TOKENS},
    }


def item_json(r: dict[str, Any], section_pages: dict[str, list[int]]) -> dict[str, Any]:
    """노트북의 결과 dict 한 건 → JSON 한 건.

    세 벌 칸(`fix`·`action`·`fix_paragraph`)은 `fix_paragraph` 한 칸으로 싣는다.
    """
    return {
        "page": r["page"],
        "parts": [name for name, pages in section_pages.items() if r["page"] in pages],
        "sentence": r["sentence"],
        "level": r["level"],
        "risk_tags": list(r.get("risk_tags", [])),
        "confirmed_in_evidence": list(r.get("confirmed_in_evidence", [])),
        "missing_fields": list(r.get("missing_fields", [])),
        "reason_bullets": list(r.get("reason_bullets", [])),
        "fix_paragraph": r.get("fix_paragraph", ""),
        "evidence_pages": list(r.get("evidence_pages", [])),
        "evidence_internal": r.get("evidence_internal", ""),
        # 문장이 쪽 글의 어디인지. 노트북은 AI 가 돌려준 문장이 쪽 글에 있는지 확인하지 않으므로
        # 이 밴드에서는 늘 null 이다.
        "span": None,
    }


def counts_json(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"term": term, "count": n} for term, n in counter.most_common()]


def word_counts_json(total: Counter[str], per_page: Sequence[tuple[int, Counter[str]]]) -> dict[str, Any]:
    return {"total": counts_json(total), "pages": [{"page": p, "counts": counts_json(c)} for p, c in per_page]}


def chunk_defaults() -> dict[str, Any]:
    """노트북의 셀 11 이 `build_vectorstore_from_docs` 에 주는 값."""
    return {
        "chunk_size": 800,
        "chunk_overlap": 150,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_batch_size": EMBEDDING_BATCH_SIZE,
        "separators": ["\n\n", "\n", " "],
        "normalize": True,
    }
