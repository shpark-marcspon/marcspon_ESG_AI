#!/usr/bin/env bash
# 밴드 X1b-2b 의 심은 파손(발주서 band-handoffs/X1b-2b-order.md §3-2, 개정 1 — P1~P14). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로
# 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-X1b-2b.sh [--commit 1|2|3] [--with-containers] [--only P1,P4]
#
# (-q 를 품은 층 명령에 -vv 를 더해 PASSED 줄이 찍히게 한다 — -v 하나면 -q 와 맞비겨 초록 노드를 못 본다.)
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 「잡음」= 심은 뒤 그 층의 pytest 가 0 아닌 종료이고, 빨개져야 할
# 시험 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 「초록이어야 함」 노드가 있으면 그것이 통과로
# 찍혀야 한다.
# 커밋 n 에는 커밋 n 까지의 P 만 심는다. 업무·보안·통합 층(컨테이너가 필요)은 --with-containers 일 때만 — 아니면
# 「안 돌림」으로 찍고 잡은 수·심은 수에 넣지 않는다(조용한 초록 0).
# 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다. 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지
# 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 보안 층은 부를 때마다 테스트 DB 를 새로 만들어 마이그레이션한다(심은 마이그레이션이 그대로 들어간다).
# 산출물: X1B2B_OUT(기본: 워크트리 곁의 X1b-2b.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${X1B2B_OUT:-$(cd "$ROOT/.." && pwd)/X1b-2b.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
COMMIT = 3
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--commit" and len(args) > 1 and args[1] in ("1", "2", "3"):
        COMMIT, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def cut(pattern: str) -> Callable[[str], str | None]:
    """정규식(DOTALL)에 정확히 한 번 맞는 자리를 지운다."""

    def plant(text: str) -> str | None:
        found = list(re.finditer(pattern, text, flags=re.S))
        return text[: found[0].start()] + text[found[0].end() :] if len(found) == 1 else None

    return plant


def swap_all(old: str, new: str, count: int) -> Callable[[str], str | None]:
    """old 가 정확히 count 번 있을 때 전부 바꾼다."""

    def plant(text: str) -> str | None:
        return text.replace(old, new) if text.count(old) == count else None

    return plant


MODELS = Path("esgapi/runs/models.py")
T_MODELS = "esgapi/runs/tests/test_models.py"
T_EXEC = "esgapi/runs/tests/test_executor.py"
ACTION = Path("esgapi/runs/service/actions/runs.py")
T_API = "esgapi/runs/tests/service/apis/test_runs.py"
T_SEC = "tests/security/test_runs.py"
STATIC = "esgapi/core/tests/isolation/test_static_rules.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)
# import 계약: 「빨간 노드」는 lint-imports 의 「<계약 이름> BROKEN」 줄의 계약 머리(가. 등)
LINT = ("계약", ["uv", "run", "--frozen", "lint-imports", "--no-cache"], False)
CORE_TEST = Path("esgapi/core/tests/test_selectors_tenant.py")
RUNS_PRODUCT = Path("esgapi/runs/calc/keys.py")
T_NAMES = "esgapi/runs/tests/test_names.py"

ORDER = T_MODELS + "::test_step_data_and_partial_come_back_in_the_written_key_order"
CARRIED = T_EXEC + "::test_a_resumed_attempt_gets_the_carried_data_in_the_written_key_order"
MAIN = T_API + "::test_resume_copies_the_finished_steps_and_files_and_keeps_the_previous_versions_and_options"
REFUSALS = T_API + "::test_resume_refusals_write_nothing_and_leave_the_previous_run"
ECROSS = T_SEC + "::test_resuming_another_companys_failed_run_is_not_found"
NOT_AGAIN = T_EXEC + "::test_a_resumed_run_does_not_run_the_carried_steps_again"
HANDS = T_EXEC + "::test_a_resumed_run_hands_the_previous_versions_to_the_binding"

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음, 초록이어야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "data 를 맨 models.JSONField 로",
     [(MODELS, swap('    data: "models.JSONField[dict[str, object] | None]" = OrderedJSONField(null=True)\n',
                    '    data: "models.JSONField[dict[str, object] | None]" = models.JSONField(null=True)\n'))],
     [(BUSINESS, [T_MODELS, T_EXEC], {ORDER + "[data]", CARRIED}, {ORDER + "[partial]"})]),
    ("P2", 1, "from_db_value 가 감싼 글자를 안 풂",
     [(MODELS, swap("        return json.loads(wrapped) if isinstance(wrapped, str) else items\n", "        return items\n"))],
     [(BUSINESS, [T_MODELS, T_EXEC], {
         ORDER + "[data]",
         ORDER + "[partial]",
         CARRIED,
         T_EXEC + "::test_a_run_goes_to_done_with_steps_results_and_files",
     }, {T_MODELS + "::test_an_unwrapped_old_value_reads_as_it_is"})]),
    ("P3", 2, "앞 실행을 RunRow.unscoped 로 찾음",
     [(ACTION, swap("        previous = selectors.lock_run(company_id=company_id, run_id=resume_from)\n",
                    "        previous = RunRow.unscoped.select_for_update().filter(pk=resume_from).first()\n"))],
     [(SECURITY, [T_SEC], {ECROSS + "[session]", ECROSS + "[bearer]"}, set()),
      (PURE, [STATIC], {STATIC + "::test_product_code_does_not_use_unscoped"}, set())]),
    ("P4", 2, "failed 아닌 앞 실행도 받음",
     [(ACTION, swap('        if previous.status != "failed":\n',
                    '        if previous.status not in ("failed", "queued", "processing", "done"):\n'))],
     [(BUSINESS, [T_API], {REFUSALS + "[queued-expected6]", REFUSALS + "[processing-expected7]",
                           REFUSALS + "[done-expected8]"}, {MAIN})]),
    ("P5", 2, "옮긴 단계를 pending 으로",
     [(ACTION, swap('            status="pending" if step is None else "done",\n', '            status="pending",\n'))],
     [(BUSINESS, [T_EXEC, T_API], {NOT_AGAIN, MAIN}, set())]),
    ("P6", 2, "새 파일 행이 앞 키 그대로",
     [(ACTION, swap("        key = file_key(company_id=company_id, run_id=row.pk, step=file.step, name=file.name)\n",
                    "        key = file.storage_key\n"))],
     [(BUSINESS, [T_API], {MAIN}, set())]),
    ("P7", 2, "versions 를 다시 지음",
     [(ACTION, swap("        previous_versions = dict(previous.versions)\n", "        previous_versions = None\n"))],
     [(BUSINESS, [T_API, T_EXEC], {MAIN, HANDS}, set())]),
    ("P8", 2, "앞 실행 finished_at 을 고침",
     [(ACTION, swap("        previous_files = selectors.run_files(company_id=company_id, run_id=previous.pk)\n",
                    "        previous_files = selectors.run_files(company_id=company_id, run_id=previous.pk)\n"
                    "        RunRow.for_company(company_id).filter(pk=previous.pk).update(finished_at=now)\n"))],
     [(BUSINESS, [T_API], {MAIN}, set())]),
    ("P9", 2, "이어 돌기 검사를 옵션 뒤로(요청 옵션으로 먼저 검사)",
     [(ACTION, swap("    carried: tuple[RunStep, ...] = ()\n",
                    "    try:\n        binding.check_options(options)\n    except RunOptionsRejected as rejected:\n"
                    "        return OptionsRejected(rejected.message)\n    carried: tuple[RunStep, ...] = ()\n"))],
     [(BUSINESS, [T_API], {MAIN}, set())]),
    ("P10", 2, "묶음이 보내기를 복사 앞에",
     [(ACTION, swap("        if copies:\n"
                    "            _copy_files(company_id=company_id, run_id=run_id, resumed_from=resumed_from, copies=copies)\n"
                    "        send(company_id=company_id, run_id=run_id)\n",
                    "        send(company_id=company_id, run_id=run_id)\n"
                    "        if copies:\n"
                    "            _copy_files(company_id=company_id, run_id=run_id, resumed_from=resumed_from, copies=copies)\n"))],
     [(BUSINESS, [T_API], {T_API + "::test_resume_sends_after_the_bytes_are_in_the_new_key"}, {MAIN})]),
    ("P11", 2, "RESUME_ALREADY 검사 지움",
     [(ACTION, swap("        if selectors.resumed_alive(company_id=company_id, run_id=previous.pk):\n"
                    "            return ResumeAlready()\n", ""))],
     [(BUSINESS, [T_API], {REFUSALS + "[child_queued-expected9]", REFUSALS + "[child_processing-expected10]",
                           REFUSALS + "[child_done-expected11]",
                           T_API + "::test_a_failed_child_does_not_block_and_a_second_resume_is_refused"}, set())]),
    ("P12", 3, "걷은 import(runs 일감 selector)를 core 시험에 심음",
     [(CORE_TEST, swap("from esgapi.runs.models import JobRow\n",
                       "from esgapi.runs.models import JobRow\nfrom esgapi.runs.service.selectors import jobs  # noqa: F401\n"))],
     [(LINT, [], {"가."}, set())]),
    ("P13", 3, "runs 제품 글자 상수에 \"esgapi.greenwash\"",
     [(RUNS_PRODUCT, swap('FILE_NAME: Final = re.compile(r"^[A-Za-z0-9._-]{1,100}$")\n',
                          'FILE_NAME: Final = re.compile(r"^[A-Za-z0-9._-]{1,100}$")\nPLANTED: Final = "esgapi.greenwash"\n'))],
     [(PURE, [T_NAMES], {T_NAMES + "::test_runs_spells_no_business_module"}, set())]),
    ("P14", 2, "복사를 create_run 블록 안에서 바로 부름",
     [(ACTION, swap("    created = selectors.find_run(company_id=company_id, run_id=row.pk)\n",
                    "    if copies:\n        resume.copy_files(documents.default_storage(), copies)  # type: ignore[arg-type]\n"
                    "    created = selectors.find_run(company_id=company_id, run_id=row.pk)\n"))],
     [(BUSINESS, [T_API], {T_API + "::test_a_rolled_back_block_copies_nothing"}, set())]),

]

PLANTS = [p for p in PLANTS if p[1] <= COMMIT and (ONLY is None or p[0] in ONLY)]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], set[str], str]:
    name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    env.pop("OPENAI_API_KEY", None)
    if layer is LINT:
        done = subprocess.run(cmd, capture_output=True, text=True, check=False, env={**env, "COLUMNS": "400"})
        text = done.stdout + done.stderr
        log.write_text(text, encoding="utf-8")
        failed = set(re.findall(r"^(\S+) .*? BROKEN\b", text, flags=re.M))
        last = next((x for x in text.splitlines() if x.startswith("Contracts:")), "")
        return done.returncode, failed, set(), last
    done = subprocess.run([*cmd, "-vv", *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    passed = set(re.findall(r"^(\S+::\S+(?:\[[^\]]*\])?) PASSED", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, passed, last


files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _, _ in p[4]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, failed, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, _commit, what, edits, checks in PLANTS:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        ok_plant = True
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        if not ok_plant:
            print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
            planted += 1
            continue
        for layer, targets, expected, green in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            planted += 1
            code, failed, passed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed and green <= passed
            caught += 1 if hit else 0
            missing = sorted(expected - failed)
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
            for node in sorted(green):
                print(f"    {'PASSED' if node in passed else '★ 초록 아님'} {node}  (초록이어야 함)")
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
