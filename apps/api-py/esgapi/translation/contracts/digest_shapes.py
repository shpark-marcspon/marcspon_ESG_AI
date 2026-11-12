"""둘째 결과 꼴 translation.digest@1 — 영문번역 실행 하나의 작은 요약(밴드 TR3a, MARC-ENT-392).

흐름(flows/colab_158.py report)이 결과 translation.result@1 곁에 둘째 결과로 남긴다. 결과 본문(원문 글자당 약 24.6바이트
— flows/colab_158.py MAX_SOURCE_CHARS)을 목록·묶음 화면이 읽지 않게 하려는 것이다. 값은 결과에서 셈한 것과 그 실행이
**실제로 지은** Word 이름뿐이다(셈은 outputs/digest.py — 이 파일에 로직은 없다). 결과 본문은 바이트 그대로다.

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다. 고정 파일은
tests/data/flow-shapes/translation.digest@1.schema.json.
칸을 더하는 것은 @1 안, 빼거나 바꾸면 @2 다.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal, TypedDict

from pydantic import Field, TypeAdapter, with_config

from esgapi.translation.contracts.shapes import FORBID, Count, PageNum, SeverityCounts, VariantLabel

DIGEST_SHAPE: Final = "translation.digest@1"

FileName = Annotated[str, Field(min_length=1)]


@with_config(FORBID)
class DigestFiles(TypedDict):
    """그 문체의 Word 세 갈래 — 실행이 실제로 지은 출력 파일 이름, 짓지 않았으면(검수 멈춤·자동수정 안 돎·Word 짓기
    실패) null. 이름은 그 실행의 출력 파일 이름 그대로다(`translation-<갈래>-<문체 소문자>.docx`)."""

    bilingual: FileName | None
    qa: FileName | None
    autofix: FileName | None


@with_config(FORBID)
class DigestVariant(TypedDict):
    """문체 하나의 요약."""

    label: VariantLabel
    reviewStatus: Literal["reviewed", "call_failed", "not_run"]
    """reviewed = 모든 쪽의 검수가 돌았다(parse_failed 쪽 포함), call_failed·not_run = 쪽 차례로 처음 멈춘 쪽의 검수
    status."""
    reviewStoppedAt: PageNum | None
    """검수가 처음 멈춘 쪽 번호. reviewed 면 null."""
    parseFailedPages: Count
    """검수 답을 JSON 으로 못 읽은 쪽 수(결과 review.status parse_failed — 모델 이슈 0 으로 친 쪽)."""
    issueCount: Count
    """그 문체의 검수 이슈 수(쪽마다 review.issues 길이의 합 — 심각도 글자와 무관)."""
    issueCounts: SeverityCounts
    """심각도별 이슈 수(쪽마다 review.counts 의 합 — 글자가 정확히 HIGH·MEDIUM·LOW 인 것만이라 합은 issueCount 이하)."""
    glossaryMisses: Count
    """용어집 미반영 줄 수 — 결과 glossaryCheck 가운데 번역 대상 쪽(document.pageNumbers)의 줄만."""
    autofixStatus: Literal["done", "stopped", "not_run"]
    autofixChangedPages: Count
    """자동수정이 글을 바꾼 쪽 수(autofix.pages 의 changed). 끝까지 안 돌았으면 0."""
    files: DigestFiles


@with_config(FORBID)
class TranslationDigest(TypedDict):
    """translation.digest@1 — 영문번역 실행 하나의 요약."""

    schemaVersion: Literal["translation.digest@1"]
    status: Literal["done", "rejected"]
    """결과 translation.result@1 의 status."""
    rejectionKind: (
        Literal[
            "no_pages",
            "ceo_page_limit",
            "unsupported_input",
            "too_large",
            "over_budget",
            "retry_source_not_found",
            "retry_source_mismatch",
        ]
        | None
    )
    """rejected 면 결과 rejection.kind, 아니면 null. 거절 글은 결과 경로의 rejection.message 에 있다."""
    outcome: Literal["done", "partial", "rejected"]
    """rejected = 번역을 시작하지 않음, partial = 번역 못 한 쪽이 하나라도 있거나(failedPages) 어느 문체의 검수가
    멈춤(call_failed·not_run), done = 그 밖. 자동수정 멈춤·검수 parse_failed 는 partial 로 치지 않는다."""
    pageCount: Count
    """번역 대상 쪽 수(document.pageNumbers 의 서로 다른 번호)."""
    failedPages: list[PageNum]
    """어느 문체에서든 번역이 실패한 쪽 번호(fragments status error — 오름차순, 겹침 없음)."""
    variants: list[DigestVariant]
    """결과의 문체 차례 그대로. rejected 면 빈 목록."""
    warningCount: Count
    """결과 warnings 의 줄 수."""


DIGEST_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    DIGEST_SHAPE: TypeAdapter[TranslationDigest](
        Annotated[TranslationDigest, Field(title=DIGEST_SHAPE, description="영문번역 한 건의 요약.")]
    )
}
"""꼴 id → 검사기. validate_python(요약, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
