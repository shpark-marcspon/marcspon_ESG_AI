#!/usr/bin/env bash
# 밴드 G2c2(MARC-TICK-198: 그린워싱 AI 설정 판 — 회사별 저장·적용·실행 판 고정)의 심은 파손(발주서
# band-handoffs/G2c2-order.md §3-5). 틀은 planted-breaks-G1b.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로
# 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-G2c2.sh [--commit 1|2|3] [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 커밋 n 에는 커밋 n 까지의 파손만 심는다. 업무·보안 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로
# 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: G2C2_OUT(기본: 워크트리 곁의 G2c2.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G2C2_OUT:-$(cd "$ROOT/.." && pwd)/G2c2.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
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
ONLY: set[str] | None = None
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


G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
SVC = G / "service/services/ai_settings.py"
SEL = G / "service/selectors/ai_settings.py"
SHAPES = G / "contracts/criteria_shapes.py"
TS = f"{T}/service/services/test_ai_settings.py"
TQ = f"{T}/contracts/test_ai_setting_shapes.py"
TSTATIC = "esgapi/core/tests/isolation/test_static_rules.py"
ACT = G / "service/actions/ai_settings.py"
PERM = Path("esgapi/core/permissions.py")
TA = f"{T}/service/apis/test_ai_settings.py"
TPERM = "esgapi/core/tests/test_permissions.py"
SEC = "tests/security/test_ai_settings.py"
BIND = G / "flows/binding_e0.py"
FLOWF = G / "flows/colab_e0.py"
TASKS = Path("esgapi/runs/tasks.py")
TB = f"{T}/flows/test_binding_e0_settings.py"
TBR = f"{T}/flows/test_binding_e0_settings_runs.py"
TD = f"{T}/flows/test_colab_e0_dryrun_settings.py"
TC = f"{T}/flows/test_criteria_flow.py"
TX = "esgapi/runs/tests/test_executor.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(검사 커밋, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", 1, "저장이 accept_criteria 를 건너뜀",
     [(SVC, swap("        accepted = accept_criteria(criteria)\n", "        accepted = cast(\"GreenwashCriteria\", criteria)\n"))],
     [(1, BUSINESS, [TS], {TS + "::test_a_refused_criteria_writes_nothing["})]),
    ("2", 1, "criteria.version 을 이름으로 안 덮음",
     [(SVC, swap('    return cast("GreenwashCriteria", {**accepted, "version": name})', '    return accepted'))],
     [(1, BUSINESS, [TS], {TS + "::test_the_saved_criteria_carry_the_server_name_and_their_sha"})]),
    ("3", 1, "이름 매김이 회사 조건 없이 셈",
     [(SEL, swap('    return tuple(GreenwashAiSettingRow.for_company(company_id).values_list("name", flat=True))',
                 '    return tuple(GreenwashAiSettingRow.unscoped.values_list("name", flat=True))'))],
     [(1, BUSINESS, [TS], {TS + "::test_the_name_counts_only_this_companys_versions",
                           TS + "::test_saving_names_the_versions_per_company"})]),
    ("4", 1, "이름 다시 시도가 모든 IntegrityError 를 삼킴",
     [(SVC, swap("            if _constraint(error) != NAME_UNIQUE:\n                raise\n", ""))],
     [(1, BUSINESS, [TS], {TS + "::test_another_constraint_breach_is_not_retried"})]),
    ("5", 1, "적용이 옛 판을 false 로 안 내림",
     [(SVC, swap("        GreenwashAiSettingRow.for_company(company_id).filter(id=before).update(applied=False)\n", "        pass\n"))],
     [(1, BUSINESS, [TS], {TS + "::test_apply_moves_the_one_applied_version"})]),
    ("6", 1, "적용 id 찾기(잠금)의 회사 조건 지움",
     [(SEL, swap('    rows = GreenwashAiSettingRow.for_company(company_id).select_for_update().order_by("id")',
                 '    rows = GreenwashAiSettingRow.unscoped.select_for_update().order_by("id")'))],
     [(1, PURE, [TSTATIC], {TSTATIC + "::test_product_code_does_not_use_unscoped"}),
      (1, BUSINESS, [TS], {TS + "::test_applying_a_missing_or_foreign_version_is_missing"})]),
    ("7", 1, "목록 selector 의 회사 조건 지움",
     [(SEL, swap('    rows = GreenwashAiSettingRow.for_company(company_id).order_by("-id")',
                 '    rows = GreenwashAiSettingRow.unscoped.order_by("-id")'))],
     [(1, PURE, [TSTATIC], {TSTATIC + "::test_product_code_does_not_use_unscoped"}),
      (1, BUSINESS, [TS], {TS + "::test_the_page_shows_only_this_companys_versions"})]),
    ("8", 2, "저장 감사 지움",
     [(ACT, swap('    record_event(\n        at=now,\n        company_id=company_id,\n        actor_kind=actor_kind,\n        actor_user_id=actor_user_id,\n        action="setting_change",\n        event="ai_setting_created",',
                 '    (lambda **_: None)(\n        at=now,\n        company_id=company_id,\n        actor_kind=actor_kind,\n        actor_user_id=actor_user_id,\n        action="setting_change",\n        event="ai_setting_created",'))],
     [(2, BUSINESS, [TA], {TA + "::test_the_save_and_apply_audit_lines"})]),
    ("9", 2, "같은 판 다시 적용에도 감사(Unchanged 대신 Applied)",
     [(SVC, swap("    if before == setting_id:\n        return Unchanged()\n",
                 "    if before == setting_id:\n        return Applied(before_id=before, after_id=setting_id, after_name=None)\n"))],
     [(2, BUSINESS, [TA], {TA + "::test_the_save_and_apply_audit_lines"}),
      (2, SECURITY, [SEC], {SEC + "::test_the_app_role_saves_applies_and_goes_back"})]),
    ("10", 2, "권한 다섯을 CUSTOMER 로",
     [(PERM, swap(f'    "greenwash_ai_setting_{op}": OPERATOR,', f'    "greenwash_ai_setting_{op}": CUSTOMER,'))
      for op in ("list", "default", "get", "create", "apply")],
     [(2, PURE, [TPERM], {TPERM + "::test_the_table_is_these_needs", TPERM + "::test_the_cells_are_partitioned"}),
      (2, BUSINESS, [TA], {TA + "::test_a_customer_is_403_before_any_read"}),
      (2, SECURITY, [SEC], {SEC + "::test_a_customer_bearer_is_refused_on_all_five"})]),
    ("11", 3, "versions_with 가 늘 기본 판",
     [(BIND, swap("        applied = self.store.applied(company_id)\n", "        applied = DefaultSetting()\n"))],
     [(3, PURE, [TB], {TB + "::test_versions_with_a_saved_setting_rebuilds_its_sha"}),
      (3, BUSINESS, [TBR], {TBR + "::test_a_run_keeps_the_version_applied_when_it_was_made"})]),
    ("12", 3, "inputs_with 가 versions 의 id 대신 지금 적용 판을 읽음",
     [(BIND, swap("        found = self.store.get(company_id, setting_id)\n", "        found = self.store.applied(company_id)\n"))],
     [(3, PURE, [TB], {TB + "::test_inputs_with_a_setting_reads_that_version"}),
      (3, BUSINESS, [TBR], {TBR + "::test_a_run_keeps_the_version_applied_when_it_was_made"})]),
    ("13", 3, "sha 대조 지움",
     [(BIND, swap('        if colab.run_versions(found.criteria)["evalPromptSha256"] != versions.get("evalPromptSha256"):\n'
                  '            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 판정 프롬프트가 실행을 만들 때와 다르다")\n', ""))],
     [(3, PURE, [TB], {TB + "::test_inputs_with_a_wrong_setting_fails[sha-differs]"}),
      (3, BUSINESS, [TBR], {TBR + "::test_a_run_whose_version_cannot_be_rebuilt_fails[sha]"})]),
    ("14", 3, "tasks.py 가 versions 를 {} 로 넘김",
     [(TASKS, swap("versions=claimed.run.versions", "versions={}"))],
     [(3, BUSINESS, [TBR, TX], {TBR + "::test_a_run_keeps_the_version_applied_when_it_was_made",
                                TX + "::test_a_binding_with_the_second_shape_gets_the_company_and_the_run_versions"})]),
    ("16", 3, "dry-run 보정 지움",
     [(FLOWF, swap("        if inputs.criteria is None:\n            return StepOutput(data={\"dry_run\": dry})\n",
                   "        if True:\n            return StepOutput(data={\"dry_run\": dry})\n"))],
     [(3, PURE, [TD, TC], {TD + "::test_the_edited_eval_is_added_per_eval_request",
                           TC + "::test_dry_run_with_criteria_calls_nothing_and_counts_the_edited_eval"})]),
    ("15", 1, "Q7 표기 하나 지움(기준 글의 maxLength)",
     [(SHAPES, swap('"maxLength": 300, ', ''))],
     [(1, PURE, [TQ], {TQ + "::test_the_marked_counts_are_the_acceptance_constants"})]),
]
if ONLY is not None:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]
PLANTS = [p for p in PLANTS if p[1] <= COMMIT]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def checks_of(plant):
    return [c for c in plant[4] if c[0] <= COMMIT]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    _, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


def hit(want: str, failed: set[str]) -> bool:
    return any(f.startswith(want) for f in failed) if want.endswith("[") else want in failed


files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for _, layer, targets, _ in checks_of(p):
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"[0] {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, _commit, what, edits, _ in PLANTS:
    plant = next(p for p in PLANTS if p[0] == number)
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        ok_plant = True
        for f, edit in edits:
            text = f.read_text(encoding="utf-8")
            new = edit(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        if not ok_plant:
            print(f"[{number}] 심기 실패(파일이 바뀌지 않음) — 못 잡은 것으로 센다 — {what}")
            planted += 1
            continue
        ran = 0
        all_hit = True
        for _, layer, targets, expected in checks_of(plant):
            label = f"[{number}/{layer[0]}]"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            ran += 1
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            missing = sorted(w for w in expected if not hit(w, failed))
            ok = code != 0 and not missing
            all_hit = all_hit and ok
            print(f"{label} {'잡음' if ok else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        if ran:
            planted += 1
            caught += 1 if all_hit else 0
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
for f in files:
    print(f"  {f} {hashlib.sha256(f.read_bytes()).hexdigest()}")
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
