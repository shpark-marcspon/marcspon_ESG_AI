"""결과 docx 짓기(밴드 RP2d — 순수: django·DB 0, greenwash/outputs/xlsx 꼴). drafting.bullets@3 → docx 바이트.
python-docx 의 기본 서식(Title·Heading 1~4·List Bullet)만 쓴다. 몸은 service/actions/download.py 가 부른다.

    첫 줄      제목 「원고 초안 — 실행 <id>」
    잎마다     titlePath 를 깊이별 머리(Heading 1~4, 깊이 4 넘으면 4). 앞 잎과 같은 조상 머리는 다시 쓰지 않는다
    done       bullet 마다 글머리 문단 + 끝에 출처 「(p.3, 7)」(bullet 의 출처 문서가 하나면 쪽만, 여럿이면
               「(12:3, 15:7)」 = 문서 id:쪽. 같은 (문서, 쪽) 은 한 번, 쪽 오름 — 블록·문장 상자는 싣지 않는다).
               unsupported 는 앞에 「[근거 없음] 」. 출처가 없으면 꼬리 없음
    그 밖      한 줄 — no_material 「자료에 해당 내용 없음」 · failed 「생성 실패: <message>」 ·
               not_run 「생성 안 함: <reason>」

★ 결정적: 같은 결과 → 같은 문단 차례·글자(바이트는 python-docx 의 저장에 맡긴다 — 시험은 문단 글자로 잰다).
★ 쓰기 전용이다 — 빈 Document() 로 새 문서를 지을 뿐, 올린 Word 를 열지 않는다(읽기는 영문번역 tools/docx_reader 몫).
★ XML 에 실을 수 없는 제어 글자(탭·줄바꿈 밖의 C0)는 뺀다 — python-docx 가 ValueError 로 던지는 자리다.
"""

import io
import re
from collections.abc import Sequence
from typing import Any, Final

import docx

MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TITLE: Final = "원고 초안"
HEADING_MAX: Final = 4
UNSUPPORTED: Final = "[근거 없음] "
NO_MATERIAL: Final = "자료에 해당 내용 없음"
BULLET_STYLE: Final = "List Bullet"
_NOT_XML: Final = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def file_name(run_id: int) -> str:
    return f"drafting-{run_id}.docx"


def _clean(text: str) -> str:
    return _NOT_XML.sub("", text)


def sources_tail(sources: Sequence[dict[str, Any]]) -> str:
    """bullet 끝의 출처 꼬리. 출처가 없으면 빈 글."""
    if not sources:
        return ""
    pairs = sorted({(source["documentId"], source["page"]) for source in sources}, key=lambda pair: (pair[1], pair[0]))
    if len({document for document, _ in pairs}) == 1:
        return " (p." + ", ".join(str(page) for _, page in pairs) + ")"
    return " (" + ", ".join(f"{document}:{page}" for document, page in pairs) + ")"


def outcome_line(outcome: dict[str, Any]) -> str | None:
    """done 이 아닌 잎의 한 줄(done 이면 None)."""
    match outcome["status"]:
        case "done":
            return None
        case "no_material":
            return NO_MATERIAL
        case "failed":
            return f"생성 실패: {outcome['failure']['message']}"
        case "not_run":
            return f"생성 안 함: {outcome['reason']}"
        case other:
            raise ValueError(f"모르는 잎 갈래: {other}")


def build(result: dict[str, Any], *, run_id: int) -> bytes:
    """drafting.bullets@3 → docx 바이트."""
    document = docx.Document()
    document.add_heading(f"{TITLE} — 실행 {run_id}", level=0)
    previous: list[str] = []
    for leaf in result["leaves"]:
        path = [_clean(title) for title in leaf["titlePath"]]
        same = 0
        while same < min(len(path), len(previous)) and path[same] == previous[same]:
            same += 1
        if same == len(path):  # 앞 잎과 경로가 통째로 같다 — 잎 머리는 다시 단다
            same -= 1
        for depth in range(max(same, 0), len(path)):
            document.add_heading(path[depth], level=min(depth + 1, HEADING_MAX))
        previous = path
        outcome = leaf["outcome"]
        line = outcome_line(outcome)
        if line is not None:
            document.add_paragraph(_clean(line))
            continue
        for bullet in outcome["bullets"]:
            head = UNSUPPORTED if bullet["unsupported"] else ""
            document.add_paragraph(_clean(head + bullet["text"] + sources_tail(bullet["sources"])), style=BULLET_STYLE)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()
