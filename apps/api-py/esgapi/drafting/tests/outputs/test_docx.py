"""결과 docx 짓기(outputs/docx.build — 밴드 RP2d, 순수 층: DB 0). 지은 바이트를 python-docx 로 다시 읽어
문단의 (서식, 글자) 목록으로 잰다(바이트 대조가 아니다 — 결정적은 같은 결과 → 같은 문단 목록).

    D1  계약 예시 result-sample: 제목 → 머리(같은 조상은 한 번) → bullet·출처 꼬리·[근거 없음] →
        failed·no_material 한 줄
    D2  not_run 한 줄 · 깊이 5 의 경로는 Heading 4 까지 · 출처 문서가 둘이면 「문서 id:쪽」 ·
        출처 쪽이 여럿이면 「p.3, 7」
    D3  같은 결과를 두 번 지으면 문단 목록이 같다 · 제어 글자는 빠진다(python-docx 가 던지는 자리)
    B10 (RP2b) 출처 꼬리는 (문서, 쪽) 마다 한 번·쪽 오름 — @2 는 한 쪽의 블록·문장 출처가 여럿일 수 있다(상자는 안 실음)
결과는 지어낸 것이다(계약 예시와 손으로 쓴 잎).
"""

import io
import json
from pathlib import Path
from typing import Any, Final

import docx

from esgapi.drafting.outputs import docx as docx_output

EXAMPLE: Final = Path(__file__).resolve().parents[1] / "data/examples/result-sample.json"


def paragraphs(data: bytes) -> list[tuple[str, str]]:
    document = docx.Document(io.BytesIO(data))
    return [((p.style.name or "") if p.style is not None else "", p.text) for p in document.paragraphs]


def sample() -> dict[str, Any]:
    body: dict[str, Any] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    return body


def leaf(path: list[str], outcome: dict[str, Any]) -> dict[str, Any]:
    return {"key": "k", "titlePath": path, "pages": [], "outcome": outcome}


def bullet(text: str, *sources: tuple[int, int], unsupported: bool = False) -> dict[str, Any]:
    return {
        "text": text,
        "sources": [{"documentId": d, "page": p} for d, p in sources],
        "unsupported": unsupported,
    }


def test_d1_the_contract_sample_becomes_headings_bullets_and_one_liners() -> None:
    assert paragraphs(docx_output.build(sample(), run_id=41)) == [
        ("Title", "원고 초안 — 실행 41"),
        ("Heading 1", "환경"),
        ("Heading 2", "기후변화 대응"),
        ("Heading 3", "온실가스 배출 관리"),
        ("List Bullet", "2025년 Scope 1·2 배출량 1,200 tCO2eq, 전년 대비 3.5% 감축 (p.2, 3)"),  # @2 예시: 쪽 2 둘·쪽 3
        ("List Bullet", "[근거 없음] 사업장 전체 고효율 설비 교체 추진"),
        ("Heading 3", "에너지 사용"),  # 환경 › 기후변화 대응 은 다시 쓰지 않는다
        ("Normal", "생성 실패: 모델 호출이 시간 안에 끝나지 않았다."),
        ("Heading 1", "사회"),
        ("Heading 2", "안전보건"),
        ("Normal", "자료에 해당 내용 없음"),
    ]


def test_d2_not_run_deep_paths_and_source_tails() -> None:
    result = {
        "leaves": [
            leaf(
                ["가", "나", "다", "라", "마"],
                {
                    "status": "done",
                    "bullets": [
                        bullet("가상 사실 하나", (31, 3), (31, 7)),
                        bullet("가상 사실 둘", (31, 3), (32, 5), unsupported=True),
                        bullet("가상 사실 셋", unsupported=False),
                    ],
                },
            ),
            leaf(["가", "바"], {"status": "not_run", "reason": "비용 상한을 넘어 돌리지 않았다."}),
        ]
    }
    assert paragraphs(docx_output.build(result, run_id=7)) == [
        ("Title", "원고 초안 — 실행 7"),
        ("Heading 1", "가"),
        ("Heading 2", "나"),
        ("Heading 3", "다"),
        ("Heading 4", "라"),
        ("Heading 4", "마"),  # 깊이 5 도 Heading 4
        ("List Bullet", "가상 사실 하나 (p.3, 7)"),
        ("List Bullet", "[근거 없음] 가상 사실 둘 (31:3, 32:5)"),
        ("List Bullet", "가상 사실 셋"),
        ("Heading 2", "바"),
        ("Normal", "생성 안 함: 비용 상한을 넘어 돌리지 않았다."),
    ]


def test_d3_the_same_result_gives_the_same_paragraphs_and_control_characters_drop() -> None:
    assert paragraphs(docx_output.build(sample(), run_id=41)) == paragraphs(docx_output.build(sample(), run_id=41))
    result = {"leaves": [leaf(["가\x00상"], {"status": "done", "bullets": [bullet("글\x0b자", (1, 2))]})]}
    assert paragraphs(docx_output.build(result, run_id=1))[1:] == [("Heading 1", "가상"), ("List Bullet", "글자 (p.2)")]


def test_d4_the_file_name_is_ascii() -> None:
    assert docx_output.file_name(123) == "drafting-123.docx"
    assert docx_output.file_name(123).isascii()


def test_b10_the_same_page_is_one_tail_entry_in_page_order() -> None:
    """RP2b B10: 같은 (문서, 쪽) 의 블록·문장 출처 여럿은 꼬리에 한 번, 쪽 오름(문서가 여럿이면 쪽 → 문서 차례)."""
    same = [
        {"documentId": 31, "blockId": "p7-b2", "page": 7},
        {"documentId": 31, "blockId": "p3-b1", "page": 3},
        {"documentId": 31, "blockId": "p7-b1", "page": 7},
    ]
    assert docx_output.sources_tail(same) == " (p.3, 7)"
    two = [*same, {"documentId": 30, "blockId": "p7-b1", "page": 7}]
    assert docx_output.sources_tail(two) == " (31:3, 30:7, 31:7)"
