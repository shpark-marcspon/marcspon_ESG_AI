"""결과 dataverify.result@2 → 둘째 결과 dataverify.digest@1(밴드 DV1g — 꼴은 contracts/digest_shapes.py). 순수다.

    digest(result)   결과 한 건의 요약(새 판정 없음 — 결과에서만 센다)

셈(칸 뜻은 꼴의 docstring):
- stages: plan·review·insight 마다 결과의 status·partial 그대로
- checks: review.checks 를 엑셀 verify_rows(outputs/xlsx.py)와 같은 갈래로 센다 — check 는 해마다 note 가 있으면
  notComputed(엑셀 「계산 불가」), 없으면 status 로 ok·fail · value 는 na 인 것만 naValues · error 는 toolErrors ·
  search·값 있는 value 는 셈 밖
"""

from collections.abc import Mapping
from typing import Any, cast

from esgapi.dataverify.contracts.digest_shapes import (
    DIGEST_SHAPE,
    DataverifyCheckCounts,
    DataverifyDigest,
    DataverifyStageHead,
    DataverifyStageHeads,
)


def _head(stage: Mapping[str, Any]) -> DataverifyStageHead:
    return DataverifyStageHead(status=stage["status"], partial=stage["partial"])


def _counts(checks: list[Mapping[str, Any]]) -> DataverifyCheckCounts:
    counts = DataverifyCheckCounts(ok=0, fail=0, notComputed=0, naValues=0, toolErrors=0)
    for check in checks:
        kind = check["kind"]
        if kind == "value":
            counts["naValues"] += 1 if check["na"] else 0
        elif kind == "error":
            counts["toolErrors"] += 1
        elif kind == "check":
            for year in check["years"]:
                if year["note"] is not None:
                    counts["notComputed"] += 1
                elif year["status"] == "OK":
                    counts["ok"] += 1
                else:
                    counts["fail"] += 1
    return counts


def digest(result: Mapping[str, Any]) -> DataverifyDigest:
    """결과(꼴을 지난 result@2) 한 건의 요약."""
    return DataverifyDigest(
        schemaVersion=DIGEST_SHAPE,
        stages=DataverifyStageHeads(
            plan=_head(result["plan"]), review=_head(result["review"]), insight=_head(result["insight"])
        ),
        checks=_counts(cast("list[Mapping[str, Any]]", result["review"]["checks"])),
    )
