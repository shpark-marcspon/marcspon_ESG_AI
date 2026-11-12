"""결과 materiality.result@2 → 둘째 결과 materiality.digest@1(밴드 IR3c — 꼴은 contracts/digest_shapes.py). 순수다.

    digest(result)   결과 한 건의 요약(새 판정 없음 — 결과에서만 센다)

셈(칸 뜻은 꼴의 docstring): 최종 엑셀(outputs/final_xlsx.py)의 2-1·2-2 시트와 같은 갈래 — part2 가 done 이면 토픽·
서브토픽마다 impact(2-1)·pathway(2-2)가 done 인 것의 rows 수를 더한다(failed·not_run 은 0줄). part2 가 not_run 이면
둘 다 null(영향 정의까지 가지 않음 — 0 과 가른다).
"""

from collections.abc import Mapping
from typing import Any

from esgapi.materiality.contracts.digest_shapes import DIGEST_SHAPE, MaterialityDigest


def _rows(result: Mapping[str, Any], side: str) -> int:
    return sum(
        len(sub[side]["rows"])
        for topic in result["part2"]["topics"]
        for sub in topic["subtopics"]
        if sub[side]["status"] == "done"
    )


def digest(result: Mapping[str, Any]) -> MaterialityDigest:
    """결과(꼴을 지난 result@2) 한 건의 요약."""
    if result["part2"]["status"] != "done":
        return MaterialityDigest(schemaVersion=DIGEST_SHAPE, impactRows=None, pathwayRows=None)
    return MaterialityDigest(
        schemaVersion=DIGEST_SHAPE, impactRows=_rows(result, "impact"), pathwayRows=_rows(result, "pathway")
    )
