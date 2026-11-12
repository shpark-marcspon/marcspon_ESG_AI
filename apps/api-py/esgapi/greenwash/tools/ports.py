"""판 무관 포트(Protocol) 넷과 자리 꼴. 흐름의 어댑터 꼴(flows 의 GreenwashAdapters)이 이 이름으로 칸을 적는다."""

from typing import Protocol, TypedDict, runtime_checkable


class PositionValue(TypedDict):
    """좌표 어댑터가 돌려주는 자리 — 결과 꼴의 Position(contracts/shapes.py)과 같은 칸. page 는 1부터, boxes 는
    [[left, top, right, bottom], …](pt, 쪽의 왼쪽 위 원점, 줄마다 하나). shapes.py 를 등록 길에서 들이지 않으려고
    따로 적는다."""

    page: int
    boxes: list[list[float]]


class PdfTextPort(Protocol):
    def page_texts(self, pdf: bytes) -> list[str]:
        """쪽마다 글(쪽 차례, 0번 = 1쪽)."""
        ...


class CoordinatesPort(Protocol):
    def locate(self, pdf: bytes, page: int, sentence: str) -> PositionValue | None:
        """문장의 쪽 위 자리(page 는 1부터). 못 찾으면 None."""
        ...


@runtime_checkable
class ClosingCoordinatesPort(CoordinatesPort, Protocol):
    """닫는 좌표 포트(밴드 G1b-2b) — 실행(시도)마다 짓는 것. locate 단계가 끝에 stats() 를 단계 data 에 싣고 close()
    한다(실행기는 어댑터를 닫지 않는다). 닫기 없는 좌표(시험의 가짜)는 이 꼴이 아니라 닫지도 세지도 않는다."""

    def close(self) -> None: ...

    def stats(self) -> dict[str, int]: ...


class TokenCounterPort(Protocol):
    """GW1 TokenCounter 의 두 메서드. count 가 None 이면 「못 쟀다」."""

    def count(self, encoding: str, text: str) -> int | None: ...

    def reason(self, encoding: str) -> str: ...
