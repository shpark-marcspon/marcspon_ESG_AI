# pyright: basic
# ruff: noqa: UP006, UP035, UP045
# ↑ GW1 사본이라 본문을 고치지 않는다(AST 대조). 끈 규칙은 이 파일이 실제로 어기는 것만:
#   typing.List 꼴; typing 의 옛 이름; Optional 꼴
"""검색용 정규화와 조각내기.

노트북(AI그린워싱 점검_E0의 사본.ipynb)의 셀 11 소스에서 기계로 뽑아 글자 그대로 옮겼다.
흠을 고치지 않는다(py/greenwash/README.md 의 「일부러 남긴 흠」). 원본 대조(tests/notebook_probe.py)가 같음을 잰다.
"""

import copy
import re
from typing import Any, Dict, List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter


def _normalize_for_retrieval(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    # 단일 개행은 공백으로, 문단 구분(연속 개행)은 유지
    t = re.sub(r"(?<!\n)\n(?!\n)", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _ensure_page_metadata(docs: List[Any]) -> List[Any]:
    """
    docs 각 원소(Document)에 metadata['page']가 없으면 0-based로 보정합니다.
    5단계 build_evidence()가 `int(d.metadata.get("page", 0)) + 1` 를 쓰므로,
    여기서 'page'는 0-based가 되도록 맞춥니다.
    """
    out = []
    for i, d in enumerate(docs):
        dd = copy.deepcopy(d)
        if not hasattr(dd, "metadata") or dd.metadata is None:
            dd.metadata = {}
        if "page" not in dd.metadata:
            dd.metadata["page"] = i  # ✅ 0-based
        out.append(dd)
    return out


def build_chunks_from_docs(
    docs: List[Any],
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
    embedding_model: str = "text-embedding-3-small",
    embedding_batch_size: int = 50,
    separators: Optional[List[str]] = None,
    normalize: bool = True,
) -> Dict[str, Any]:
    """
    반환:
      {
        "chunks": List[Document],
        "config": {...},
      }
    """
    if not docs:
        raise ValueError("docs가 비어 있습니다. PDF 로드(1~3단계) 결과를 확인하세요.")

    # 1) 페이지 메타데이터 보정(5단계와 호환 핵심)
    docs2 = _ensure_page_metadata(docs)

    # 2) (선택) 텍스트 정규화
    if normalize:
        for d in docs2:
            d.page_content = _normalize_for_retrieval(getattr(d, "page_content", "") or "")

    # 3) 청킹
    if separators is None:
        separators = ["\n\n", "\n", " "]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        add_start_index=True,
    )

    chunks = splitter.split_documents(docs2)

    # 4) chunk 메타데이터 강화(추적/디버그)
    for idx, ch in enumerate(chunks):
        if not hasattr(ch, "metadata") or ch.metadata is None:
            ch.metadata = {}
        src_page_0 = int(ch.metadata.get("page", 0))  # 0-based
        ch.metadata["source_page"] = src_page_0 + 1  # 1-based(사람용)
        ch.metadata["chunk_index"] = idx
        ch.metadata["chunk_id"] = f"p{src_page_0 + 1}-c{idx}"

    return {
        "chunks": chunks,
        "config": {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "embedding_model": embedding_model,
            "embedding_batch_size": embedding_batch_size,
            "separators": separators,
            "normalize": normalize,
        },
    }
