"""결과 translation.result@1 → 둘째 결과 translation.digest@1(밴드 TR3a — 꼴은 contracts/digest_shapes.py). 순수다.

    digest(result, built, *, name)   built = 그 실행이 **실제로 지은** 출력 파일 이름(계획이 아니다 — Word 짓기가
                                     실패한 파일은 없다), name(kind, label) = 흐름의 출력 파일 이름 규칙(flows/colab_158
                                     word_name — 이름 규칙은 흐름 한 벌이고 outputs 는 flows 를 import 하지 않는다)

셈(칸 뜻은 꼴의 docstring):
- failedPages: 어느 문체든 fragments status error 의 쪽(오름차순·겹침 없음)
- reviewStatus: 쪽 차례로 처음 call_failed·not_run 인 쪽의 status(그 쪽 번호가 reviewStoppedAt), 없으면 reviewed
- glossaryMisses: glossaryCheck 가운데 pageNum 이 document.pageNumbers 안인 줄(엔진은 원문 조각 전부를 본다 —
  engines/colab_158/pipeline.py — 화면은 그 파트의 쪽만 보인다)
- outcome: rejected > partial(failedPages 가 있거나 어느 문체의 검수가 멈춤) > done
"""

from collections.abc import Callable, Collection, Mapping
from typing import Any, cast

from esgapi.translation.contracts.digest_shapes import (
    DIGEST_SHAPE,
    DigestFiles,
    DigestVariant,
    TranslationDigest,
)
from esgapi.translation.contracts.shapes import SeverityCounts

WORD_KINDS = ("bilingual", "qa", "autofix")


def _variant(
    variant: Mapping[str, Any], targets: set[int], built: Collection[str], name: Callable[[str, str], str]
) -> DigestVariant:
    pages = cast("list[Mapping[str, Any]]", variant["pages"])
    stopped = next((p for p in pages if p["review"]["status"] in ("call_failed", "not_run")), None)
    counts = SeverityCounts(high=0, medium=0, low=0)
    for page in pages:
        for level in ("high", "medium", "low"):
            counts[level] += page["review"]["counts"][level]
    autofix = variant["autofix"]
    found = {kind: name(kind, variant["label"]) for kind in WORD_KINDS}
    files = DigestFiles(
        bilingual=found["bilingual"] if found["bilingual"] in built else None,
        qa=found["qa"] if found["qa"] in built else None,
        autofix=found["autofix"] if found["autofix"] in built else None,
    )
    return DigestVariant(
        label=variant["label"],
        reviewStatus="reviewed" if stopped is None else stopped["review"]["status"],
        reviewStoppedAt=None if stopped is None else stopped["pageNum"],
        parseFailedPages=sum(1 for p in pages if p["review"]["status"] == "parse_failed"),
        issueCount=sum(len(p["review"]["issues"]) for p in pages),
        issueCounts=counts,
        glossaryMisses=sum(1 for miss in variant["glossaryCheck"] if miss["pageNum"] in targets),
        autofixStatus=autofix["status"],
        autofixChangedPages=sum(1 for p in autofix["pages"] if p["changed"]),
        files=files,
    )


def digest(result: Mapping[str, Any], built: Collection[str], *, name: Callable[[str, str], str]) -> TranslationDigest:
    """결과(꼴을 지난 translation.result@1)의 요약. 머리말의 셈."""
    targets = set(cast("list[int]", result["document"]["pageNumbers"]))
    variants = cast("list[Mapping[str, Any]]", result["variants"])
    failed = sorted({f["pageNum"] for v in variants for f in v["fragments"] if f["status"] == "error"})
    summaries = [_variant(v, targets, built, name) for v in variants]
    rejection = result["rejection"]
    if result["status"] == "rejected":
        outcome = "rejected"
    elif failed or any(v["reviewStatus"] != "reviewed" for v in summaries):
        outcome = "partial"
    else:
        outcome = "done"
    return TranslationDigest(
        schemaVersion=DIGEST_SHAPE,
        status=result["status"],
        rejectionKind=None if rejection is None else rejection["kind"],
        outcome=outcome,
        pageCount=len(targets),
        failedPages=failed,
        variants=summaries,
        warningCount=len(result["warnings"]),
    )
