#!/usr/bin/env bash
# 밴드 IRS2 의 심은 파손(발주서 band-handoffs/IRS2-order.md §3 P1~P5 — planted-breaks-HD1.sh 꼴). 하나씩 심고 겨눈 업무
# 시험만 돌린 뒤 원본 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — 끝에 sha·status 대조). SIGINT·SIGTERM
# 이 와도 되쓴다.
# 사용(어디서든): apps/api-py/scripts/planted-breaks-IRS2.sh [--only P1,P4]
# 판정: P0(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 0 아닌 종료이고 빨개져야 할 노드가 전부 FAILED.
# X 로 시작하는 것은 러너가 더한 하나(분모 밖 — EXTRA=; X1 은 dc 허락의 runs started_at 칸).
# 끝 줄 PLANTED=<잡음>/<심음>, 앞 줄 P0=·FINGERPRINT=·EXTRA=. 산출물: IRS2_OUT(기본 워크트리 곁의 IRS2.out)/planted/.
# compose esg-app-irs2 의 postgres 가 떠 있어야 한다. 공급사를 부르지 않는다(키를 지운 환경). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${IRS2_OUT:-$(cd "$ROOT/.." && pwd)/IRS2.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
  -u LLM_RUN_MODE uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
ONLY = None
while args:
    if args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def _term(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, _term)


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


ACT = Path("esgapi/materiality/service/actions/runs.py")
SEL = Path("esgapi/runs/service/selectors/runs.py")
T = "esgapi/materiality/tests/service/apis/test_materiality_runs.py"
T1 = f"{T}::test_the_list_never_selects_the_whole_options_outside_the_nul_branch"
T2 = f"{T}::test_the_option_fields_equal_the_base_count_for_every_shape"
GOOD = f"{T}::test_the_good_input_fills_every_option_field"

OLD_CALL = """    page = run_selectors.run_page_brief(
        company_id=company_id,
        module=MODULE,
        statuses=statuses,
        created_by_user_id=user_id if mine else None,
        limit=limit,
        offset=offset,
        values=BRIEF_VALUES,
        shapes=BRIEF_SHAPES,
    )
    found = list(page.runs)"""
BASE_CALL = """    page = run_selectors.run_page(
        company_id=company_id,
        module=MODULE,
        status=None,
        document_id=None,
        limit=limit,
        offset=offset,
        statuses=statuses,
        created_by_user_id=user_id if mine else None,
    )
    found = [
        BriefRun(
            id=r.id, status=r.status, created_at=r.created_at, started_at=r.started_at, finished_at=r.finished_at,
            created_by_user_id=r.created_by_user_id, failed_step=r.failed_step, values={}, shapes={},
            whole=dict(r.options),
        )
        for r, _name in page.runs
    ]"""

# (이름, 파일, 심기, 겨눈 시험, 빨개져야 할 노드)
PLANTS: list[tuple[str, Path, Callable[[str], str | None], list[str], list[str]]] = [
    ("P1 run_page 로 되돌림(본문 통째)", ACT, swap(OLD_CALL, BASE_CALL), [T1], [T1]),
    (
        "P2 whole 무시(늘 투영)",
        ACT,
        swap(
            "given = _input(run.whole) if run.whole is not None else _brief_input(run)",
            "given = _brief_input(run)",
        ),
        [T2],
        [f"{T2}[nul_in_topic]", f"{T2}[nul_in_name]"],
    ),
    (
        "P3 topicCount length or 0",
        ACT,
        swap('return length if kind == "array" else None', "return length or 0"),
        [T2],
        [f"{T2}[topics_text]"],
    ),
    (
        "P4 industries 경로 오타",
        ACT,
        swap('"industries": ("input", "industries"),', '"industries": ("input", "industry"),'),
        [T2, GOOD],
        [f"{T2}[good]", GOOD],
    ),
    (
        "P5 latest 경로 오타",
        ACT,
        swap('"latest": ("input", "latestEventMode"),', '"latest": ("input", "latestEventModes"),'),
        [T2, GOOD],
        [f"{T2}[good]", GOOD],
    ),
    (
        "X1 runs started_at 칸이 finished_at 을 실음",
        SEL,
        swap(
            '            started_at=row["started_at"],\n            finished_at=row["finished_at"],\n            created_by_user_id',
            '            started_at=row["finished_at"],\n            finished_at=row["finished_at"],\n            created_by_user_id',
        ),
        [T2, GOOD],
        [f"{T2}[good]"],
    ),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout


def run(targets: list[str], log: Path) -> tuple[int, str]:
    cmd = ["scripts/test-business.sh", "-p", "no:cacheprovider", "-rf", *targets]
    done = subprocess.run(cmd, capture_output=True, text=True)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


files = {ACT, SEL}
before = {p: sha(p) for p in files}
status_before = status()
code, _ = run(sorted({t for _, _, _, ts, _ in PLANTS for t in ts}), LOGS / "P0.log")
print(f"P0={'GREEN' if code == 0 else 'RED'}")
caught = planted = extra_caught = extra = 0
for name, path, plant, targets, reds in PLANTS:
    key = name.split()[0]
    if ONLY is not None and key not in ONLY:
        continue
    original = path.read_bytes()
    changed = plant(original.decode("utf-8"))
    if changed is None:
        print(f"{name} => 심을 자리 없음(MISS)")
        ok = False
    else:
        try:
            path.write_text(changed, encoding="utf-8")
            code, text = run(targets, LOGS / f"{key}.log")
        finally:
            path.write_bytes(original)
        missing = [r for r in reds if f"FAILED {r}" not in text]
        ok = code != 0 and not missing
        print(f"{name} => EXIT={code} {'잡음' if ok else '놓침'} 빠진 빨강 {missing}")
    if key.startswith("X"):
        extra, extra_caught = extra + 1, extra_caught + int(ok)
    else:
        planted, caught = planted + 1, caught + int(ok)
after = {p: sha(p) for p in files}
same = after == before and status() == status_before
print(f"FINGERPRINT={'SAME' if same else 'CHANGED'} {' '.join(f'{p.name}:{after[p]}' for p in sorted(files))}")
print(f"EXTRA={extra_caught}/{extra}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if same and caught == planted and extra_caught == extra and planted > 0 else 1)
PY
