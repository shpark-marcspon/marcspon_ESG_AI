"""§4 의 재생 G2 (커밋 경계 ③): 실제 계수 표 + 예제 148행으로 TS CLI `eval --provider mock` 을 그 자리에서 돌린
rows.json 과 파이썬의 순수 파이프라인이 전체 일치하는가. scope3_replay 가 `--only g2` 일 때 부른다.

파이썬 쪽: 파일 순 후보(TS 의 표 순서), 예제 폴더의 가상 기억, 모의 공급사 + 규칙 응답기. AI 공급사 호출 0.
"""

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from esgapi.inventory.engines.scope3.llm_first_1.catalog import RawRecord
from esgapi.inventory.engines.scope3.llm_first_1.pipeline import PipelineResult, run_pipeline
from esgapi.inventory.tests.scope3_catalog_support import (
    Example,
    FloatTally,
    catalog_from,
    compare_with_ts,
    load_json_keeping_floats,
)
from esgapi.inventory.tests.scope3_llm_support import harness, load_memory, row_dump
from esgapi.inventory.tests.scope3_replay import ReplayFailed, run_ts_cli, say


def g2(lab: Path, examples: Sequence[Example], records: Sequence[RawRecord]) -> None:
    say("== G2: TS `eval --provider mock` 의 rows.json 과 전체 일치 (실제 표, 파일 순, 예제 148행) ==")
    examples_dir = lab / "data/scope3-examples"
    with tempfile.TemporaryDirectory(prefix="scope3-g2-") as out:
        arguments = [
            "eval",
            str(examples_dir),
            "--provider",
            "mock",
            "--factors",
            str(lab / "data/factors/factors.jsonl"),
        ]
        run_ts_cli(lab, [*arguments, "--out", out, "--log", str(Path(out) / "calls.jsonl")])
        theirs: list[dict[str, Any]] = load_json_keeping_floats(Path(out) / "rows.json")

    setup = harness(
        catalog_from(records, "file"), memory=load_memory(examples_dir / "memory.synthetic.json"), heuristic=True
    )
    result = run_pipeline([example.row for example in examples], setup.options)
    if not isinstance(result, PipelineResult):
        raise ReplayFailed(f"G2: 파이프라인이 입력을 거절했다: {result}")
    mine = row_dump(examples, result)

    recommend_calls = sum(len(group.shortlists) for group in result.groups)
    scored = sum(
        1 for group in result.groups for trace in group.shortlists for entry in trace.evidence if entry.lexical
    )
    shown = sum(len(trace.shown_ids) for group in result.groups for trace in group.shortlists)
    say(f"분모: 행 {len(mine)} (TS {len(theirs)}), 묶음 {len(result.groups)}, 추천 호출 {recommend_calls}")
    say(f"  생성 모델 호출 {result.usage.calls} (모의 공급사가 받은 요청 {len(setup.mock.calls)}), 실호출 0")
    say(f"  추린 후보 {shown} 건, 그 가운데 낱말이 겹쳐 점수가 붙은 것 {scored}")
    statuses: dict[str, int] = {}
    for row in mine:
        statuses[str(row["status"])] = statuses.get(str(row["status"]), 0) + 1
    say(f"  판단의 갈래: {dict(sorted(statuses.items()))}")

    tally = FloatTally()
    differences = compare_with_ts(mine, theirs, tally, "rows")
    say(f"  다른 자리 {len(differences)} (id·순위·겹친 낱말·갈래·계산 상태는 글자까지, 점수는 상대 오차 1e-12 안에서)")
    say(f"  {tally.line()}")
    if differences:
        for line in differences[:20]:
            say(f"    {line}")
        raise ReplayFailed(f"G2: TS 와 다른 자리 {len(differences)}")
    if len(mine) != 148:
        raise ReplayFailed(f"G2: 행이 148 이 아니다 ({len(mine)})")
    say("G2 일치")
