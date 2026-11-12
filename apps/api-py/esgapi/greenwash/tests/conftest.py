# pyright: basic
# ↑ GW1 테스트의 사본(import 경로만 바꿈). 타입 표기 없는 GW1 의 꼴 그대로라 strict 를 끈다.
"""테스트 공용 도구. 글은 전부 지은 것(synthetic)이다. 네트워크와 키 없이 돈다."""

import pytest
from langchain_core.documents import Document

from esgapi.greenwash.tests.sample_text import page_texts

# 지은 문장. NONLOW 는 숫자가 있어 Low 가 아니고, LOW 는 환경 낱말 + 의지 표현이라 Low 다.
NONLOW = [
    "가상상사는 2030년까지 온실가스 배출량을 40% 줄였습니다.",
    "가상상사는 2024년에 폐기물 재활용률 85%를 달성했습니다.",
    "가상상사는 2025년에 재생에너지 비율을 30%로 높였습니다.",
    "가상상사는 2023년에 용수 사용량을 12% 줄였다고 밝혔습니다.",
]
LOW = ["재생에너지 사용을 확대해 나가겠습니다.", "온실가스 감축을 지속적으로 추진하겠습니다."]

LONG_FIX = (
    "기준연도 2020년과 목표연도 2030년을 밝혀야 합니다. 범위를 Scope 1과 Scope 2로 나누어 적어야 합니다. "
    "감축량은 tCO2eq 단위의 수치와 산정 방법을 함께 제시해야 합니다. 제3자 검증 여부를 밝히는 것이 바람직합니다."
)


def make_docs(texts):
    return [Document(page_content=t, metadata={"page": i}) for i, t in enumerate(texts)]


def chunk(page_1based, text):
    return Document(page_content=text, metadata={"page": page_1based - 1})


class StubIndex:
    """정해 둔 조각을 차례대로 돌려주는 검색. 받은 물음과 k 를 적어 둔다."""

    def __init__(self, chunks=()):
        self.chunks = list(chunks)
        self.calls = []

    def similarity_search(self, query, k=4):
        self.calls.append((query, k))
        return self.chunks[:k]


def eval_json(decision="High", **kw):
    d = {
        "decision": decision,
        "risk_tags": ["꼬리표"],
        "confirmed_in_evidence": ["사실 하나", "사실 둘"],
        "missing_fields": [],
        "reason_bullets": ["까닭"],
        "fix_paragraph": LONG_FIX,
        "evidence_internal": "근거 한 줄(p.1)",
    }
    d.update(kw)
    return {"json": d}


@pytest.fixture
def sample_docs():
    return make_docs(page_texts())
