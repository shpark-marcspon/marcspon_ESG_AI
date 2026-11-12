"""BM25(표준 라이브러리만). 랩 `esg-lab/py/semgraph/lexical.py` 그대로 옮겼다.

낱말 = 영숫자 낱말(소문자, 쉼표 뺌) + 한글 두 글자 조각(한 글자 낱말은 그대로). k1 1.2 · b 0.75 ·
idf = log(1 + (n − df + 0.5) / (df + 0.5)).
"""

import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import Final

WORD: Final = re.compile(r"[A-Za-z][A-Za-z0-9\-]*|\d[\d,\.]*")
HANGUL: Final = re.compile(r"[가-힣]+")
K1: Final = 1.2
B: Final = 0.75


def tokens(text: str) -> list[str]:
    out = [w.lower().replace(",", "") for w in WORD.findall(text)]
    for run in HANGUL.findall(text):
        if len(run) == 1:
            out.append(run)
        out.extend(run[i : i + 2] for i in range(len(run) - 1))
    return out


class BM25:
    def __init__(self, docs: Sequence[str], k1: float = K1, b: float = B) -> None:
        self.tf = [Counter(tokens(d)) for d in docs]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 0.0
        df: Counter[str] = Counter(w for t in self.tf for w in t)
        n = len(docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query: str) -> list[float]:
        q = Counter(tokens(query))
        out: list[float] = []
        for tf, ln in zip(self.tf, self.len, strict=True):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if f:
                    norm = 1 - self.b + self.b * ln / self.avg if self.avg else 1.0
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * norm)
            out.append(s)
        return out
