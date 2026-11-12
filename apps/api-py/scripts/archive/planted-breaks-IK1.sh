#!/usr/bin/env bash
# 밴드 IK1 의 심은 파손(발주서 band-handoffs/IK1-order.md §3 + MARC-TICK-253 노트의 73 조건 (다)). RF1 의 꼴 그대로:
# 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지
# 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-IK1.sh [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). PLANTED 는 P 단위로 센다 — 16(§3 의
# P1~P15 + 73 조건 (다)의 「유니크에서 company 빼기」 P16). 경계는 하나다.
# 범위 심음(P7·P8 — 보안 ⓗ 와 묶음)은 예외 없이 터지지 않는 꼴이다 — 업무·보안 층의 잡음은 **단언**으로 빨개진 것만
# 센다. 빨간 노드의 로그에 예외(UnscopedQueryError·Traceback 의 500)가 있으면 「예외로 빨강」을 찍고 못 잡음으로 센다.
# 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 시험 DB 는 돌 때마다 마이그레이션으로 새로 짓는다(--reuse-db 없음) — P15·P16 은 모델과 0003 을 같이 고친다.
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: IK1_OUT(기본: 워크트리 곁의 IK1.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${IK1_OUT:-$(cd "$ROOT/.." && pwd)/IK1.out}"
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
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


ACTIONS = Path("esgapi/runs/service/actions/runs.py")
API = Path("esgapi/runs/service/apis/runs.py")
CALC = Path("esgapi/runs/calc/idempotency.py")
SELECTORS = Path("esgapi/runs/service/selectors/runs.py")
MODELS = Path("esgapi/runs/models.py")
MIGRATION = Path("esgapi/runs/migrations/0003_run_idempotency_key.py")
TI = "esgapi/runs/tests/service/apis/test_runs_idempotency.py"
TRACE = "esgapi/runs/tests/service/actions/test_create_run_race.py"
TCALC = "esgapi/runs/tests/calc/test_idempotency.py"
TOP = "esgapi/runs/tests/service/apis/test_runs_operator.py"
TVAL = "esgapi/runs/tests/test_models_values.py"
SRUN = "tests/security/test_runs.py"

T1 = TI + "::test_the_same_key_and_body_twice_is_one_run_one_message_one_audit_line"
T1B = TI + "::test_a_replay_is_found_before_the_checks_so_a_changed_binding_does_not_refuse_it"
T2 = TI + "::test_the_same_key_with_another_body_is_409_and_writes_nothing"
T3 = TI + "::test_without_a_key_two_posts_are_two_runs_byte_for_byte_like_base"
T4 = TI + "::test_a_malformed_key_is_422_validation_error_and_writes_nothing"
T8 = TI + "::test_another_person_or_company_with_the_same_key_gets_their_own_run"
T9 = TI + "::test_a_replay_reads_the_session_and_the_key_only"
R10 = TRACE + "::test_two_overlapping_posts_with_the_same_key_and_body_make_one_run"
R11 = TRACE + "::test_two_overlapping_posts_with_the_same_key_and_another_body_make_one_run_and_one_refusal"
R12 = TRACE + "::test_another_constraint_breach_is_raised_not_swallowed"
OP_SCOPE = TOP + "::test_an_operator_key_is_scoped_to_the_work_company"
S_H = SRUN + "::test_the_same_key_in_two_companies_or_two_people_makes_separate_runs"
S_I = SRUN + "::test_the_app_role_cannot_write_a_second_row_for_the_same_key_or_a_key_without_its_sha"
V_CONS = TVAL + "::test_the_idempotency_columns_and_constraints_are_the_0003_ones"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

FIRST = (
    "        replayed = _replayed(company_id=company_id, actor_user_id=actor_user_id, idempotency=idempotency)\n"
    "        if replayed is not None:\n"
    "            return replayed\n"
    "    document = None\n"
)
FIRST_BLOCK = "    if idempotency is not None:\n" + FIRST
ENQUEUE = (
    "            if isinstance(replayed, RunReplayed):\n"
    "                transaction.on_commit(\n"
    "                    _sending(hooks.enqueue_run, company_id=company_id, run_id=replayed.run.id), robust=True\n"
    "                )\n"
)
AUDIT = (
    "            if isinstance(replayed, RunReplayed):\n"
    "                record_event(\n"
    "                    at=now, company_id=company_id, actor_kind=actor_kind, actor_user_id=actor_user_id,\n"
    "                    action=\"run\", event=\"run_created\", result=\"success\", target_kind=\"run\",\n"
    "                    target_id=replayed.run.id, target_label=None,\n"
    "                )\n"
)
SAVEPOINT = "        with transaction.atomic() if idempotency is not None else contextlib.nullcontext():\n"
CATCH = "        if idempotency is None or _broken(err) != IDEMPOTENCY_UNIQUE:\n            raise\n"
KEYLESS = "    key, sha = (None, None) if idempotency is None else idempotency\n"
LOOKUP = "    row = _runs(company_id).filter(created_by_user_id=created_by_user_id, idempotency_key=key).first()\n"
REPLAY = "        return Status(201, RunCreatedOut(id=result.run.id, status=result.run.status))  # pyright: ignore[reportArgumentType]\n    if isinstance(result, actions.KeyReused):\n"
PAIR_MODEL = (
    "            models.CheckConstraint(\n"
    "                condition=models.Q(idempotency_key__isnull=True, idempotency_sha256__isnull=True)\n"
    "                | models.Q(idempotency_key__isnull=False, idempotency_sha256__isnull=False),\n"
    "                name=\"run_runs_idempotency_pair_check\",\n"
    "            ),\n"
)
PAIR_MIGRATION = (
    "        migrations.AddConstraint(\n"
    "            model_name=\"runrow\",\n"
    "            constraint=models.CheckConstraint(\n"
    "                condition=models.Q(\n"
    "                    models.Q((\"idempotency_key__isnull\", True), (\"idempotency_sha256__isnull\", True)),\n"
    "                    models.Q((\"idempotency_key__isnull\", False), (\"idempotency_sha256__isnull\", False)),\n"
    "                    _connector=\"OR\",\n"
    "                ),\n"
    "                name=\"run_runs_idempotency_pair_check\",\n"
    "            ),\n"
    "        ),\n"
)
UNIQUE_MODEL = '                fields=["company", "created_by_user_id", "idempotency_key"],\n'
UNIQUE_MIGRATION = '                fields=("company", "created_by_user_id", "idempotency_key"),\n'

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", "첫 문장의 열쇠 찾기를 지움(INSERT 의 IntegrityError·ResumeAlready 다시 판정만 남김)",
     [(ACTIONS, swap(FIRST_BLOCK, "    document = None\n"))],
     [(BUSINESS, [TI], {T1B, T9})]),
    ("P2", "세이브포인트를 걷고 바깥 트랜잭션에서 IntegrityError 를 받음",
     [(ACTIONS, swap(SAVEPOINT, "        with contextlib.nullcontext():\n"))],
     [(BUSINESS, [TRACE], {R10, R11})]),
    ("P3", "sha 에서 options 를 뺌",
     [(CALC, swap('        "options": dict(options),\n', '        "options": {},\n'))],
     [(PURE, [TCALC], {TCALC + "::test_the_options_order_matters_and_every_field_counts"}),
      (BUSINESS, [TI], {T2 + "[option_value]", T2 + "[option_order]"})]),
    ("P4", "sha 를 sort_keys=True 로",
     [(CALC, swap('separators=(",", ":"))', 'separators=(",", ":"), sort_keys=True)'))],
     [(PURE, [TCALC], {TCALC + "::test_the_options_order_matters_and_every_field_counts"}),
      (BUSINESS, [TI], {T2 + "[option_order]"})]),
    ("P5", "다시 보냄에도 on_commit(enqueue)",
     [(ACTIONS, swap(FIRST, FIRST.replace("        if replayed is not None:\n", "        if replayed is not None:\n" + ENQUEUE)))],
     [(BUSINESS, [TI], {T1})]),
    ("P6", "다시 보냄에도 감사 run_created",
     [(ACTIONS, swap(FIRST, FIRST.replace("        if replayed is not None:\n", "        if replayed is not None:\n" + AUDIT)))],
     [(BUSINESS, [TI], {T1})]),
    ("P7", "찾기 범위에서 created_by_user_id 를 뺌",
     [(SELECTORS, swap(LOOKUP, LOOKUP.replace("created_by_user_id=created_by_user_id, ", "")))],
     [(BUSINESS, [TI], {T8}),
      (SECURITY, [SRUN], {S_H})]),
    ("P8", "찾기를 회사 무관으로(RunRow.unscoped)",
     [(SELECTORS, swap(LOOKUP, LOOKUP.replace("_runs(company_id)", "RunRow.unscoped")))],
     [(BUSINESS, [TOP], {OP_SCOPE})]),  # test_selector_scope 는 RunRow.unscoped 를 못 잡는다(실측 — 보고 물을 거리)
    ("P9", "KeyReused 를 conflict 일반 code 로",
     [(API, swap('raise ApplicationError("conflict", "idempotency_key_reused",', 'raise ApplicationError("conflict", "conflict",'))],
     [(BUSINESS, [TI], {T2 + "[option_value]", T2 + "[document]"})]),
    ("P10", "IntegrityError 를 제약 이름 없이 모두 받음",
     [(ACTIONS, swap(CATCH, "        if idempotency is None:\n            raise\n"))],
     [(BUSINESS, [TRACE], {R12})]),
    ("P11", "머리를 읽지 않음(늘 None)",
     [(API, swap("    if idempotency_key is not None:\n        sha = body_sha256(", "    if idempotency_key is not None and False:\n        sha = body_sha256("))],
     [(BUSINESS, [TI], {T1})]),
    ("P12", "Header 무늬(pattern)를 지움",
     [(API, swap("            pattern=KEY_PATTERN,\n", ""))],
     [(BUSINESS, [TI], {T4 + "[1]", T4 + "[0B0E6C1E-1111-4222-8333-444455556666]"})]),
    ("P13", "다시 보냄의 status 를 \"queued\" 고정",
     [(API, swap(REPLAY, REPLAY.replace("status=result.run.status", 'status="queued"')))],
     [(BUSINESS, [TI], {T1})]),
    ("P14", "열쇠 없는 요청에 빈 글자 열쇠를 적음",
     [(ACTIONS, swap(KEYLESS, KEYLESS.replace("(None, None)", '("", None)')))],
     [(BUSINESS, [TI], {T3})]),
    ("P15", "짝 CHECK 를 모델·0003 에서 지움",
     [(MODELS, swap(PAIR_MODEL, "")), (MIGRATION, swap(PAIR_MIGRATION, ""))],
     [(PURE, [TVAL], {V_CONS}),
      (SECURITY, [SRUN], {S_I})]),
    ("P16", "유일 제약에서 company 를 뺌(모델·0003 — 73 조건 (다))",
     [(MODELS, swap(UNIQUE_MODEL, UNIQUE_MODEL.replace('"company", ', ""))),
      (MIGRATION, swap(UNIQUE_MIGRATION, UNIQUE_MIGRATION.replace('"company", ', "")))],
     [(PURE, [TVAL], {V_CONS}),
      (SECURITY, [SRUN], {S_I})]),
]
PLANTS = [p for p in PLANTS if ONLY is None or p[0] in ONLY]
BOUNDARY_GUARDED = {"P7", "P8"}  # 범위 심음 — 예외로 빨개지면 무효
EXCEPTION = re.compile(r"UnscopedQueryError|Internal Server Error|Traceback")


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str, str]:
    _name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last, text


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[3]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, failed, last, _ = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, checks) -> bool | None:
    """잡았으면 True, 못 잡았으면 False, 컨테이너가 없어 다 돌리지 못했으면 None."""
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                return False
            f.write_text(new, encoding="utf-8")
        hit_all, skipped = True, False
        for layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                skipped = True
                continue
            code, failed, last, text = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            raised = number in BOUNDARY_GUARDED and layer[0] != "순수" and bool(EXCEPTION.search(text))
            if raised:
                print(f"{label} 예외로 빨강(무효 — 단언으로 빨개져야 한다)")
                hit = False
            hit_all = hit_all and hit
            missing = sorted(expected - failed)
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        return None if skipped and hit_all else hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
for number, what, edits, checks in PLANTS:
    planted += 1
    result = plant_and_check(number, what, edits, checks)
    caught += 1 if result is True else 0
    print(f"{number} => {'잡음' if result else '안 돌림' if result is None else '못 잡음'}")

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
