"""outputs/digest.digest(밴드 DV1g §3-1-1): 지어낸 결과 dataverify.result@2 넷마다 요약의 다섯 칸·단계 머리가 손값과
같고, 엑셀 「검증 결과」 시트(xlsx.verify_rows)의 줄과 갈래별로 맞는다 — ok+fail+notComputed = 판정 OK·FAIL·「계산
불가」 줄, naValues = 「값 없음(N/A)」 줄, toolErrors = 판정 「오류」 줄(값 있는 조회·검색 줄은 셈 밖)."""

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.dataverify.contracts import shapes
from esgapi.dataverify.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES
from esgapi.dataverify.outputs import xlsx
from esgapi.dataverify.outputs.digest import digest

EXAMPLE = Path(__file__).resolve().parents[1] / "data" / "examples" / "result-sample.json"
FAILURE = {"kind": "provider_error", "budgetSource": None, "message": "가상 오류"}
INSIGHT_NOT_RUN: dict[str, Any] = {
    "status": "not_run",
    "partial": None,
    "report": None,
    "rows": [],
    "rowsParsed": "none",
    "sources": [],
    "failure": None,
}


def example() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLE.read_text(encoding="utf-8")))


def checks_of(*kinds: str) -> list[dict[str, Any]]:
    """견본의 검사 기록에서 그 갈래만(seq 는 1부터 다시)."""
    picked = [copy.deepcopy(c) for c in example()["review"]["checks"] if c["kind"] in kinds]
    for seq, check in enumerate(picked, start=1):
        check["seq"] = seq
    return picked


def no_checks() -> dict[str, Any]:
    result = example()
    result["review"]["checks"] = []
    return result


def verdicts_only() -> dict[str, Any]:
    """합계·부분합·비율만 — OK·FAIL·계산 불가 섞임."""
    result = example()
    result["review"]["checks"] = checks_of("check")
    return result


def lookups_and_errors() -> dict[str, Any]:
    """N/A 조회·값 있는 조회·검색·도구 오류(판정 칸 있는 검사 0)."""
    result = example()
    result["review"]["checks"] = checks_of("value", "search", "error")
    return result


def stages_mixed() -> dict[str, Any]:
    """Plan 은 부분, 검토는 실패(그때까지의 기록 — 오류 하나·N/A 하나), 인사이트는 돌리지 않음."""
    result = example()
    result["plan"]["partial"] = True
    checks = [c for c in checks_of("value", "error") if c["kind"] == "error" or c["na"]][:2]
    result["review"] = {"status": "failed", "partial": None, "report": None, "checks": checks, "failure": FAILURE}
    result["insight"] = copy.deepcopy(INSIGHT_NOT_RUN)
    return result


def stages(plan: tuple[str, bool | None], review: tuple[str, bool | None], insight: tuple[str, bool | None]) -> Any:
    return {k: {"status": s, "partial": p} for k, (s, p) in (("plan", plan), ("review", review), ("insight", insight))}


CASES = [
    (no_checks, stages(("done", False), ("done", True), ("done", False)), (0, 0, 0, 0, 0)),
    (verdicts_only, stages(("done", False), ("done", True), ("done", False)), (1, 1, 2, 0, 0)),
    (lookups_and_errors, stages(("done", False), ("done", True), ("done", False)), (0, 0, 0, 1, 2)),
    (stages_mixed, stages(("done", True), ("failed", None), ("not_run", None)), (0, 0, 0, 1, 1)),
]


@pytest.mark.parametrize(("build", "heads", "counts"), CASES, ids=[c[0].__name__ for c in CASES])
def test_the_digest_by_hand(build: Any, heads: Any, counts: tuple[int, ...]) -> None:
    result = build()
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)
    made = digest(result)
    DIGEST_SHAPES[DIGEST_SHAPE].validate_python(made, strict=True)
    assert made["schemaVersion"] == "dataverify.digest@1"
    assert made["stages"] == heads
    names = ("ok", "fail", "notComputed", "naValues", "toolErrors")
    assert made["checks"] == dict(zip(names, counts, strict=True))


@pytest.mark.parametrize("build", [c[0] for c in CASES] + [example], ids=[c[0].__name__ for c in CASES] + ["example"])
def test_the_counts_match_the_workbook_rows(build: Any) -> None:
    result = build()
    rows = xlsx.verify_rows(result)
    verdict = [row[5] for row in rows]  # 판정 열(VERIFY_HEADER 의 「판정」)
    told = [row[9] for row in rows]  # 설명 열 — 값 조회는 여기에 「값 없음(N/A)」·「값 = …」
    counts = digest(result)["checks"]
    judged = sum(v in ("OK", "FAIL", "계산 불가") for v in verdict)
    assert counts["ok"] + counts["fail"] + counts["notComputed"] == judged
    assert counts["ok"] == verdict.count("OK")
    assert counts["fail"] == verdict.count("FAIL")
    assert counts["notComputed"] == verdict.count("계산 불가")
    assert counts["naValues"] == told.count("값 없음(N/A)")
    assert counts["toolErrors"] == verdict.count("오류")
    outside = [r for r in rows if r[2] in ("값 조회", "검색") and r[9] != "값 없음(N/A)"]
    counted = counts["ok"] + counts["fail"] + counts["notComputed"] + counts["naValues"] + counts["toolErrors"]
    assert len(rows) == counted + len(outside)  # 값 있는 조회·검색 줄만 셈 밖


def test_the_example_counts_every_branch() -> None:
    assert digest(example())["checks"] == {"ok": 1, "fail": 1, "notComputed": 2, "naValues": 1, "toolErrors": 2}


def test_the_digest_does_not_touch_the_result() -> None:
    result = example()
    before = json.dumps(result, ensure_ascii=False)
    digest(result)
    assert json.dumps(result, ensure_ascii=False) == before
