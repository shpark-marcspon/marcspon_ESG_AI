"""문장 위치: pdfium 글자 상자로 문장의 쪽 위 자리를 찾는 CoordinatesPort 의 구현(밴드 G1d).

찾기 규칙의 상수(HEAD_KEEP_MIN 등)는 pypdf 글을 전제로 잰 값이다 — PDF 읽개를 바꾸는 판은 다시 잰다(MARC-ENT-267).
"""

import hashlib
from collections import Counter
from collections.abc import Sequence
from itertools import pairwise
from typing import Final, Literal

from esgapi.core.llm.errors import soft_deadline_in
from esgapi.greenwash.tools import pdfium_locate as pl
from esgapi.greenwash.tools.ports import PositionValue

HEAD_KEEP_MIN: Final = 0.4
"""개선 ① 쪽머리 앞머리 버리기: 앞 조각을 버린 나머지가 원 문장의 정규화 글자 수로 이만큼 이상일 때만 받는다.
출처: MARC-TICK-74 노트 「측정 결과 — pdfium 문장 위치」(2026-10-16)의 쪽머리 21건. 값은 G1d 의 공개 보고서 실측
(보고 band-reports/G1d-sentence-locate.md): 출발값 0.6 에서 가드 안 463/482, 0.4 에서 471/482 — 더 찾은 8건은 모두
버린 앞머리가 쪽 글 맨 앞의 쪽머리(정규화 71자, 쪽마다 같음)였다. 0.4 아래에서 더 붙는 것은 쪽머리보다 긴 앞머리
(108·112자)가 섞이기 시작해(0.35 에서 4건 중 3건) 쪽머리 2건(남은 비율 0.38·0.29)을 놓치는 대신 여기서 멈춘다."""

READBACK_EXTRA_MAX: Final = 0.3
"""개선 ② 되읽기: 상자 안 글(2단)에 문장(2단)이 차례대로 들고, 덧붙은 글자가 문장 길이의 이만큼 이하면 통과.
출처: 같은 측정 노트의 「되읽기 다름 18 — 확인이 엄격해서」. G1d 실측에서 0.0~0.5 는 가드 안 결과가 같아(덧붙음 0)
출발값을 둔다."""

MAX_SENTENCE_CHARS: Final = 250
"""덩어리 가드: 정규화 전 이 글자 수를 넘는 문장은 찾지 않는다(None). 출처: 같은 측정 노트 「250자 이하만 95.0%」."""

MAX_LINES: Final = 10
"""덩어리 가드: 상자가 이 줄 수를 넘으면 None. 출처: 같은 측정 노트 「11줄 이상 22개는 표·도표 덩어리」."""

TAIL_KEEP_MIN: Final = 0.4
"""대체 갈래(found_tail): 앞 조각을 버린 나머지가 원 문장의 정규화 글자 수로 이만큼 이상일 때만 다시 찾는다.
출처: MARC-ISSUE-313 원인 조사(esg-app.worktrees/HL313.out/report.md)·밴드 HL1 실측(band-reports/HL1.md): 공개 보고서
둘(G1d 표본)에서 0.4 는 가드 안 찾은 수 그대로(471/482)·가드 밖 3건을 더 찾고, 0.35·0.3 은 가드 안에서도 3·4건을 더
찾지만 HEAD_KEEP_MIN 이 0.4 에서 멈춘 까닭(쪽머리보다 긴 앞머리가 섞임)이 같아 HEAD_KEEP_MIN 과 같은 값에 둔다."""

TAIL_GAP_MAX: Final = 1.2
"""대체 갈래의 촘촘함: 이웃 줄의 세로 틈(윗줄 바닥 − 아랫줄 꼭대기)이 줄 높이의 이만큼 이하. 출처: HL1 실측 —
공개 보고서 둘에서 지금 찾는 여러 줄 상자의 틈은 중앙값 0.79·95% 0.99 줄 높이."""

TAIL_LEFT_MAX: Final = 1.0
"""대체 갈래의 촘촘함: 둘째 줄부터 왼쪽 끝이 윗줄과 줄 높이의 이만큼 안이고, 첫 줄은 둘째 줄보다 이만큼 넘게 왼쪽으로
나가지 않는다(문장은 줄 가운데서 시작할 수 있다). 출처: HL1 실측 — 같은 상자들의 둘째 줄부터 차이 중앙값 0.03·95%
0.09 줄 높이."""

LocateOutcome = Literal[
    "found_tier1", "found_tier2", "found_head", "found_tail",
    "none_multiple", "none_chunk", "none_not_found", "none_readback", "none_rotated", "none_error",
]  # fmt: skip


_TAIL_AFTER: Final = frozenset({"none_chunk", "none_not_found", "none_readback"})
"""대체 갈래를 타는 None 의 갈래. 여러 곳(none_multiple)·돌린 쪽·예외는 타지 않는다. none_not_found 는 TAIL_KEEP_MIN 이
HEAD_KEEP_MIN 과 갈라질 때를 위한 길이다(같은 값이면 _find 가 같은 나머지를 이미 0건으로 봤다)."""


def is_compact(lines: Sequence[pl.Box]) -> bool:
    """줄 상자(차례대로)가 촘촘한 한 덩어리인가: 이웃 줄이 아래로 이어지고(세로 틈 −0.5×높이 ~ TAIL_GAP_MAX×높이),
    왼쪽 끝이 TAIL_LEFT_MAX×높이 넘게 튀지 않는다. 줄 하나는 촘촘하다."""
    for i, (upper, lower) in enumerate(pairwise(lines)):
        h = max(upper[3] - upper[1], lower[3] - lower[1], 1.0)
        gap = upper[1] - lower[3]
        if not -0.5 * h <= gap <= TAIL_GAP_MAX * h:
            return False
        shift = upper[0] - lower[0]
        if shift < -TAIL_LEFT_MAX * h or (i > 0 and shift > TAIL_LEFT_MAX * h):
            return False
    return True


class PdfiumCoordinates:
    """CoordinatesPort 의 구현: 문장(pypdf 글에서 나온 것)을 pdfium 쪽 글에서 정규화로 찾아 줄마다 상자를 낸다.

    글은 바꾸지 않는다 — judge 가 보는 글은 PypdfText 그대로이고 이 어댑터는 위치만 찾는다(코랩 재현).
    문서는 하나만 든다: 같은 bytes 객체면 그대로, 아니면 sha256 으로 견줘 같으면 그대로, 다르면 앞 문서를 닫고 새로
    연다. 부르는 쪽(G1b 의 실행기)이 실행마다 짓고 끝에 close()·stats() 를 부른다. 버려지면 pypdfium2 의 finalizer 가
    닫는다. pdfium 은 스레드에 안전하지 않다 — 인스턴스를 스레드끼리 나누지 않는다.

    실패는 조용히 None 이다(위치는 보조 정보라 점검을 실패시키지 않는다). 찾은 단과 None 의 갈래는 stats() 가 센다.
    pdfium 을 부르는 부분과 정규화·줄 묶기는 tools/pdfium_locate.py 에 있다.
    """

    def __init__(self) -> None:
        self._doc: pl.PdfiumDocument | None = None
        self._bytes: bytes | None = None
        self._key = ""
        self._counts: Counter[str] = Counter()

    def __enter__(self) -> "PdfiumCoordinates":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
        self._doc, self._bytes, self._key = None, None, ""

    def stats(self) -> dict[str, int]:
        """찾은 단(found_*)·None 의 갈래(none_*)·예외 종류별(error:<이름>)·문서를 연 횟수(opened)."""
        return dict(self._counts)

    @property
    def document(self) -> pl.PdfiumDocument | None:
        """지금 든 문서(테스트가 닫힘을 본다)."""
        return self._doc

    def _document(self, pdf: bytes) -> pl.PdfiumDocument:
        if self._doc is not None and pdf is self._bytes:
            return self._doc
        key = hashlib.sha256(pdf).hexdigest()
        if self._doc is not None and key == self._key:
            self._bytes = pdf
            return self._doc
        self.close()
        self._doc = pl.PdfiumDocument(pdf)
        self._bytes, self._key = pdf, key
        self._counts["opened"] += 1
        return self._doc

    def locate(self, pdf: bytes, page: int, sentence: str) -> PositionValue | None:
        try:
            outcome, position = self._locate(pdf, page, sentence)
        except Exception as exc:  # 위치 때문에 점검이 실패하면 안 된다(발주서 「정한 것」 6)
            if soft_deadline_in(exc) is not None:  # Celery soft limit 은 None 으로 굳히지 않는다(MARC-ISSUE-414, GSL1)
                raise
            self._counts["none_error"] += 1
            self._counts[f"error:{type(exc).__name__}"] += 1
            return None
        self._counts[outcome] += 1
        return position

    def _locate(self, pdf: bytes, page: int, sentence: str) -> tuple[LocateOutcome, PositionValue | None]:
        text = self._document(pdf).page(page - 1)
        if text.rotation:
            return "none_rotated", None
        query = pl.strip_tail(sentence)
        outcome, position = self._locate_whole(text, page, sentence, query)
        # 대체는 지금 규칙이 None 을 낸 뒤에만, 온 문장이 쪽 글에서 이어진 채로 안 찾힐 때만 돈다(MARC-ISSUE-313 F1)
        if position is None and outcome in _TAIL_AFTER and not self._whole_on_page(text, query):
            tail = self._find_tail(text, page, query)
            if tail is not None:
                return "found_tail", tail
        return outcome, position

    def _locate_whole(
        self, text: pl.PageText, page: int, sentence: str, query: str
    ) -> tuple[LocateOutcome, PositionValue | None]:
        if len(sentence) > MAX_SENTENCE_CHARS:
            return "none_chunk", None
        found = self._find(text, query)
        if isinstance(found, str):
            return found, None
        stage, tier, start, part = found
        lines = self._lines(text, tier, start, part)
        if not lines or len(lines) > MAX_LINES:
            return "none_chunk", None
        if not self._reads_back(text, lines, part):
            return "none_readback", None
        return stage, self._position(text, page, lines)

    def _find_tail(self, text: pl.PageText, page: int, query: str) -> PositionValue | None:
        """대체 갈래: 앞 조각을 버린 나머지(TAIL_KEEP_MIN 까지, 긴 것부터, 1단 → 2단)를 다시 찾아, 한 군데이며 상자가
        촘촘한 한 덩어리이고 되읽기를 통과하는 첫 나머지의 상자. 찾힌 나머지가 여러 곳이거나 MAX_SENTENCE_CHARS 를
        넘으면(본문이 덩어리) 그 자리에서 None — 더 짧은 나머지로 문장 한 토막만 칠하지 않는다."""
        for tier in (1, 2):
            for part in pl.head_drops(query, tier, TAIL_KEEP_MIN):
                needle = pl.norm_str(part, tier)
                hits = pl.find_all(text.maps[tier][0], needle) if needle else []
                if len(hits) > 1 or (hits and len(part) > MAX_SENTENCE_CHARS):
                    return None
                if not hits:
                    continue
                lines = self._lines(text, tier, hits[0], part)
                if 0 < len(lines) <= MAX_LINES and is_compact(lines) and self._reads_back(text, lines, part):
                    return self._position(text, page, lines)
        return None

    @staticmethod
    def _whole_on_page(text: pl.PageText, query: str) -> bool:
        """온 문장이 1단이나 2단으로 쪽 글에 이어진 채 있는가."""
        for tier in (1, 2):
            needle = pl.norm_str(query, tier)
            if needle and pl.find_all(text.maps[tier][0], needle):
                return True
        return False

    @staticmethod
    def _lines(text: pl.PageText, tier: int, start: int, part: str) -> list[pl.Box]:
        needle = pl.norm_str(part, tier)
        positions = text.maps[tier][1]
        first, last = positions[start], positions[start + len(needle) - 1]
        boxes = pl.drop_unplaced([text.charbox(i) for i in range(first, last + 1)])  # 사이의 공백·생성 글자 포함
        return pl.group_lines(boxes)

    @staticmethod
    def _reads_back(text: pl.PageText, lines: list[pl.Box], part: str) -> bool:
        back = pl.readback_norm("".join(text.bounded(line) for line in lines))
        return pl.readback_ok(pl.norm_str(part, 2), back, READBACK_EXTRA_MAX)

    @staticmethod
    def _position(text: pl.PageText, page: int, lines: list[pl.Box]) -> PositionValue:
        return {"page": page, "boxes": [pl.to_top_left(line, text.crop) for line in lines]}

    @staticmethod
    def _find(text: pl.PageText, query: str) -> tuple[LocateOutcome, int, int, str] | LocateOutcome:
        """(단, 정규화 수준, 정규화 쪽 글에서의 시작, 찾은 부분) 또는 None 의 갈래. 차례: 1단 → 2단 → 개선 ①(1단, 2단).
        어느 차례에서든 두 군데 이상이면 그 자리에서 여러 곳."""
        tries: list[tuple[LocateOutcome, int, str]] = [("found_tier1", 1, query), ("found_tier2", 2, query)]
        for tier in (1, 2):
            tries.extend(("found_head", tier, rest) for rest in pl.head_drops(query, tier, HEAD_KEEP_MIN))
        for stage, tier, part in tries:
            needle = pl.norm_str(part, tier)
            hits = pl.find_all(text.maps[tier][0], needle) if needle else []
            if len(hits) > 1:
                return "none_multiple"
            if hits:
                return stage, tier, hits[0], part
        return "none_not_found"
