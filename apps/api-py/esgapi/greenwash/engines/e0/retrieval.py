# pyright: basic
# ruff: noqa: UP006, UP035
# ↑ GW1 사본이라 본문을 고치지 않는다(AST 대조). 끈 규칙은 이 파일이 실제로 어기는 것만:
#   typing.List 꼴; typing 의 옛 이름
"""정확 L2 검색(float32). 노트북의 `FAISS.from_documents` + `similarity_search` 자리다.

`FAISS.from_documents` 의 기본 색인은 평평한 L2 색인(`IndexFlatL2`)이라 어림 검색이 아니다(README 의 ★3).
거리는 제곱 L2 이고 가까운 차례로 k 개를 낸다. 거리가 같으면 조각 번호가 작은 것이 앞이다.
"""

from typing import Any, List, Sequence

import numpy as np

from esgapi.greenwash.engines.e0.ports import EMBEDDING_BATCH_SIZE, EmbeddingPort


def l2_order(matrix: np.ndarray, query: np.ndarray, k: int) -> List[int]:
    """`matrix`(n × d, float32)에서 `query`(d)와 제곱 L2 거리가 가까운 차례로 k 개의 줄 번호."""
    m = np.asarray(matrix, dtype=np.float32)
    q = np.asarray(query, dtype=np.float32)
    if m.ndim != 2 or m.shape[0] == 0:
        return []
    diff = m - q[None, :]
    dist = np.einsum("ij,ij->i", diff, diff, dtype=np.float32)
    order = np.argsort(dist, kind="stable")
    return [int(i) for i in order[: max(0, int(k))]]


class VectorIndex:
    """조각과 그 벡터. `similarity_search(query, k)` 는 물음을 한 번 임베딩해 가까운 조각 k 개를 돌려준다."""

    def __init__(self, chunks: Sequence[Any], vectors: Sequence[Sequence[float]], embeddings: EmbeddingPort):
        self.chunks = list(chunks)
        self.matrix = np.asarray(vectors, dtype=np.float32).reshape(len(self.chunks), -1)
        self.embeddings = embeddings

    @classmethod
    def from_documents(cls, chunks: Sequence[Any], embeddings: EmbeddingPort) -> "VectorIndex":
        texts = [c.page_content for c in chunks]
        return cls(chunks, embeddings.embed_documents(texts), embeddings)

    def similarity_search(self, query: str, k: int = 4) -> List[Any]:
        q = np.asarray(self.embeddings.embed_query(query), dtype=np.float32)
        return [self.chunks[i] for i in l2_order(self.matrix, q, k)]


def embedding_request_count(n_texts: int, batch_size: int = EMBEDDING_BATCH_SIZE) -> int:
    """조각 n 개를 묶음 크기로 나눠 보낼 때의 요청 수."""
    return (n_texts + batch_size - 1) // batch_size
