"""밴드 IR3a §4-10 의 대조: 업무 시험 3-2-7(★B)·3-2-8(이어 돌기)을 IR3A_DUMP 를 켜고 돌려 견준 두 쪽을 받아, 다시
견줘 다름 수를 센다. 사용(apps/api-py 에서, 컨테이너가 떠 있을 때):

    uv run --frozen python -I scripts/materiality_compare_ir3a.py <출력 폴더>

끝 줄 `EXEC_SAME=<다른 요청 수> RESUME_SAME=<다른 칸 수>`(둘 다 0 이어야 한다). 덤프·로그는 <출력 폴더> 아래만 쓴다.
wheel 밖 개발 도구다. 공급사는 모의뿐이라 네트워크·키는 0 이다(`env -u OPENAI_API_KEY …` 아래에서 돌린다).
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

TESTS = "esgapi/materiality/tests/flows/test_runs_materiality.py"
PICK = "same_request_bodies or resuming_after_report_iro"


def load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        print(f"★ 덤프 없음: {path.name}")
        return None
    found: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return found


def exec_diff(pair: dict[str, Any] | None) -> int:
    if pair is None:
        return 1
    ours, theirs = pair["executor"], pair["run_flow"]
    diff = sum(1 for a, b in zip(ours, theirs, strict=False) if a != b) + abs(len(ours) - len(theirs))
    print(f"요청 몸: 실행기 {len(ours)} · run_flow {len(theirs)} · 다름 {diff}")
    if len(ours) != 14:
        print("★ 요청이 14 가 아니다")
        diff += 1
    return diff


def resume_diff(pair: dict[str, Any] | None) -> int:
    if pair is None:
        return 1
    resumed, straight = pair["resumed"], pair["report_iro"]
    keys = sorted(set(resumed) | set(straight))
    diff = sum(1 for k in keys if resumed.get(k) != straight.get(k))
    first, final = pair["part1_sha256"]
    same_book = first == final
    print(f"결과 @2 칸 {len(keys)} · 다름 {diff} · 1부 엑셀 sha256 같음 {same_book} ({final[:12]})")
    return diff + (0 if same_book else 1)


def main() -> int:
    out = Path(sys.argv[1]).resolve()
    dumps = out / "ir3a-dump"
    for old in dumps.glob("*.json"):
        old.unlink()
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")}
    env["IR3A_DUMP"] = str(dumps)
    done = subprocess.run(
        ["scripts/test-business.sh", TESTS, "-p", "no:cacheprovider", "-k", PICK],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "ir3a-compare-pytest.log").write_text(done.stdout + done.stderr, encoding="utf-8")
    tail = (done.stdout.strip().splitlines() or [""])[-1]
    print(f"업무 시험 둘: {tail} (종료 {done.returncode})")
    exec_same = exec_diff(load(dumps / "exec.json"))
    resume_same = resume_diff(load(dumps / "resume.json"))
    print(f"EXEC_SAME={exec_same} RESUME_SAME={resume_same}")
    return int(done.returncode != 0 or exec_same != 0 or resume_same != 0)


if __name__ == "__main__":
    sys.exit(main())
