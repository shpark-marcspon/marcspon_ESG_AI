#!/usr/bin/env bash
# 밴드 RX1b 의 심은 파손(발주서 band-handoffs/RX1b-order.md §3 표 Q1~Q17 + 검증 B1 의 Q18 + 영문번역 a1 의 Q19 + 감독
# 권고 R1~R3 — planted-breaks-RX1a.sh 꼴). 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트를 되쓴다(git checkout·restore·
# stash 를 쓰지 않는다 — 끝에 sha·status 대조). SIGINT·SIGTERM 이 와도 되쓴다.
# 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-RX1b.sh [--with-containers] [--only Q1,Q4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 Q 의 「잡음」= 그 Q 가 겨눈 층마다 0 아닌 종료이고 빨개져야 할
# 노드가 전부 FAILED 로 찍힘. 분모 22(Q1~Q19 · R1~R3). 업무·보안 층은 --with-containers 일 때만(아니면 「안 돌림」).
# 끝 줄 PLANTED=<잡음>/<심음>, 앞 줄 P0=·FINGERPRINT=. 산출물: RX1B_OUT(기본 워크트리 곁의 RX1b.out)/planted/.
# 공급사를 부르지 않는다(OPENAI·ANTHROPIC 키를 지운 환경). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${RX1B_OUT:-$(cd "$ROOT/.." && pwd)/RX1b.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import signal
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


def _term(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, _term)


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def append(extra: str) -> Callable[[str], str | None]:
    return lambda text: text + extra


E = Path("esgapi")
CARRIERS_PY = E / "core/flows/carriers.py"
IMPORT = E / "runbundle/service/actions/import_.py"
EXPORT = E / "runbundle/service/actions/export.py"
G_ACT = E / "greenwash/service/actions/bundle.py"
G_REVIEW = E / "greenwash/service/services/review.py"
G_SETTING = E / "greenwash/service/services/ai_settings.py"
T_ACT = E / "translation/service/actions/bundle.py"
M_APPS = E / "materiality/apps.py"

GT = "esgapi/greenwash/tests/service/actions/test_bundle_carrier.py"
TT = "esgapi/translation/tests/service/actions/test_bundle_carrier.py"
DT = "esgapi/dataverify/tests/service/test_bundle_carrier.py"
MT = "esgapi/materiality/tests/service/test_bundle_carrier.py"
TC = "esgapi/runbundle/tests/service/actions/test_carrier_contract.py"
SEC = "tests/security/test_run_bundles.py"
T1 = GT + "::test_reviews_marks_and_edits_come_back_with_the_importer_as_the_person"
T2G = GT + "::test_a_saved_setting_comes_back_once_as_a_new_unapplied_setting"
T2D = DT + "::test_saved_and_default_setting_runs_come_back"
T2M = MT + "::test_saved_and_default_setting_runs_come_back"
T3 = TT + "::test_a_retry_brings_its_source_and_every_retry_id_is_rewritten"
T6T = TT + "::test_the_id_fields_are_the_fixed_table_and_cover_every_flow"
T6M = MT + "::test_the_id_fields_are_the_fixed_table_and_cover_every_flow"
T7 = GT + "::test_every_module_with_a_binding_has_a_carrier"
T8 = SEC + "::test_module_rows_stay_in_their_company"
T8F = SEC + "::test_a_forged_bundle_with_a_person_column_is_refused_as_the_app_role"

PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)
LINT = ("lint", ["uv", "run", "--frozen", "lint-imports"], False)

IDMAP_OLD = (
    "                    ids_of[module] = IdMap(\n"
    "                        run=run_map,\n"
    "                        document=document_map,\n"
    "                        ai_setting={old: new for old, (new, _name) in made.items()},\n"
    "                        ai_setting_name={old: name for old, (_new, name) in made.items()},\n"
    "                    )\n"
)
IDMAP_MERGED = (
    "                    merged |= made\n"
    "                for module in _modules(bundle):\n"
    + IDMAP_OLD.replace("made.items()", "merged.items()")
)

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("Q1", "표시 *_edited_by_user_id 를 묶음의 값(지어낸 5)으로",
     [(G_REVIEW, swap("        people = {by: None if row[at] is None else user_id for at, by in EDITS}\n",
                      "        people = {by: 5 if row[at] is not None else None for at, by in EDITS}\n"))],
     [(BUSINESS, [GT], {T1})]),
    ("Q2", "검토·표시 run_id 를 옛 id 로",
     [(G_ACT, swap('{"run_id": ids.run_id(int(str(row["runOldId"]))),', '{"run_id": int(str(row["runOldId"])),'))],
     [(BUSINESS, [GT], {T1}), (SECURITY, [SEC], {T8})]),
    ("Q3", "판을 applied=True 로 넣음",
     [(G_SETTING, swap('                    memo=row["memo"],\n                    created_by_user_id=user_id,\n',
                       '                    memo=row["memo"],\n                    created_by_user_id=user_id,\n'
                       '                    applied=True,\n                    applied_at=datetime.now().astimezone(),\n'))],
     [(BUSINESS, [GT], {T2G})]),
    ("Q4", "판을 실행마다 넣음(같은 판을 두 번 실음)",
     [(CARRIERS_PY, swap("        olds = sorted({old for v in versions.values() if (old := _setting_id(v.get(AI_SETTING_ID))) is not None})\n",
                         "        olds = [old for v in versions.values() if (old := _setting_id(v.get(AI_SETTING_ID))) is not None]\n"))],
     [(BUSINESS, [GT, TT, DT, MT], {T2G, T3, T2D, T2M})]),
    ("Q5", "versions aiSetting 다시 쓰기 지움",
     [(CARRIERS_PY, swap("            if old is None or AI_SETTING not in versions\n", "            if True\n"))],
     [(BUSINESS, [GT, TT, DT, MT], {T2G, T3, T2D, T2M})]),
    ("Q6", "result@1 retry.fromRunId 다시 쓰기 지움",
     [(T_ACT, swap('            results=tuple((shape, _rewritten(shape, body, ids)) for shape, body in results),\n',
                   '            results=tuple(results),\n'))],
     [(BUSINESS, [TT], {T3})]),
    ("Q7", "options retry.fromRunId 다시 쓰기 지움",
     [(T_ACT, swap('            options=cast("Mapping[str, object]", _rewritten("options", dict(options), ids)),\n',
                   "            options=options,\n"))],
     [(BUSINESS, [TT], {T3})]),
    ("Q8", "referenced_runs 가 빈 것을 돌려줌",
     [(T_ACT, swap("        return (found,) if isinstance(found, int) and not isinstance(found, bool) else ()\n",
                   "        return ()\n"))],
     [(BUSINESS, [TT], {T3, TT + "::test_a_rejected_retry_is_refused_or_skipped[failed]"})]),
    ("Q9", "id_fields() 에서 한 칸(step:report) 뺌",
     [(T_ACT, swap('    "step:report": (f"results[].settings.{RETRY}",),\n', ""))],
     [(BUSINESS, [TT], {T6T})]),
    ("Q10", "materiality 등록 지움",
     [(M_APPS, swap("        CARRIERS.register(  # 실행 묶음의 AI 설정 판", "        (lambda *_a: None)(  # 실행 묶음의 AI 설정 판"))],
     [(BUSINESS, [MT, GT], {T2M, T6M, T7})]),
    ("Q11", "그린워싱 carrier 가 자기 models 를 직접 import",
     [(G_ACT, swap("from esgapi.greenwash.service.services import review as review_services\n",
                   "from esgapi.greenwash.service.services import review as review_services\n"
                   "from esgapi.greenwash.models import GreenwashReviewRow  # noqa: F401\n"))],
     [(BUSINESS, [GT], {GT + "::test_a_module_carrier_does_not_import_its_own_models[greenwash]"})]),
    ("Q12", "검토 confirmed_at 을 넣은 때로",
     [(G_REVIEW, swap('            confirmed_at=row["confirmed_at"],\n',
                      '            confirmed_at=None if row["confirmed_at"] is None else datetime.now().astimezone(),\n'))],
     [(BUSINESS, [GT], {T1})]),
    ("Q13", "import_setting 이 받기를 다시 거쳐 모델 설정을 고쳐 씀",
     [(G_SETTING, swap('                    model_settings=row["model_settings"],\n',
                       '                    model_settings=to_input(prompt_model_e0.accept_model(RUN_MODELS.config(), '
                       'row["model_settings"], steps=RUN_MODELS.steps())),  # type: ignore\n'))],
     [(BUSINESS, [GT], {T2G})]),
    ("Q14", "runbundle 이 partial 을 carrier 에 안 넘김",
     [(IMPORT, swap('            partials=[(str(row["name"]), row["partial"]) for row in mine_steps],\n', "            partials=[],\n"))],
     [(BUSINESS, [TC], {TC + "::test_versions_and_partials_go_through_the_carrier"})]),
    ("Q15", "넣는 쪽 모듈 행 검사(check_gates 의 check_module_rows) 지움",
     [(IMPORT, swap("    modules = check_module_rows(bundle.modules, declared)\n",
                    "    modules = {m: {t: [dict(r) for r in rows] for t, rows in ts.items()} for m, ts in bundle.modules.items()}\n"))],
     [(BUSINESS, [TC], {TC + "::test_forged_module_rows_are_refused_before_writing[person]"}), (SECURITY, [SEC], {T8F})]),
    ("Q16", "참조 닫힘이 failed 를 받음",
     [(EXPORT, swap('target.module != run.module or target.status != "done"):',
                    'target.module != run.module or target.status not in CLOSURE_STATUSES):'))],
     [(BUSINESS, [TC], {TC + "::test_a_carrier_reference_outside_is_refused_or_skipped[failed]"})]),
    ("Q17", "판 지도를 모듈 넷 |= 합침으로",
     [(IMPORT, swap("                ids_of: dict[str, IdMap] = {}\n",
                    "                ids_of: dict[str, IdMap] = {}\n                merged: dict[int, tuple[int, str]] = {}\n")),
      (IMPORT, swap(IDMAP_OLD, IDMAP_MERGED))],
     [(BUSINESS, [TC], {TC + "::test_setting_maps_stay_per_module", TC + "::test_another_modules_setting_id_is_refused"})]),
    ("Q18", "_rewrite 가 versions aiSettingId 도 가림(검증 B1)",
     [(IMPORT, swap('        paths = [path for path in fields.get(place, ()) if not (place == "versions" and path == AI_SETTING_ID)]\n',
                    "        paths = list(fields.get(place, ()))\n"))],
     [(BUSINESS, [TC], {TC + "::test_a_carrier_that_swaps_the_setting_id_is_refused"})]),
    ("Q19", "영문번역 단계 data 다시 쓰기 지움(a1)",
     [(T_ACT, swap('            steps=tuple((name, _rewritten(f"step:{name}", data, ids)) for name, data in steps),\n',
                   "            steps=tuple(steps),\n"))],
     [(BUSINESS, [TT], {T3})]),
    ("R1", "같은 실행의 검토가 있어도 넣음(있음 확인 지움)",
     [(G_REVIEW, swap("    if GreenwashReviewRow.for_company(company_id).filter(run_id__in=runs).exists():\n        return False\n", ""))],
     [(BUSINESS, [GT], {GT + "::test_an_existing_review_of_the_same_run_is_not_overwritten"})]),
    ("R2", "★l 지킴(criteria.version ≠ 이름 거절) 지움",
     [(G_ACT, swap('            if not isinstance(criteria, dict) or criteria.get("version") != row["name"]:',
                   "            if False:"))],
     [(BUSINESS, [GT], {GT + "::test_a_setting_whose_criteria_version_is_not_its_name_is_not_exported"})]),
    ("R3", "판 이름 다시 시도가 다해도 지나감",
     [(CARRIERS_PY, swap("            if not _is_made(made):\n", "            if False:\n"))],
     [(BUSINESS, [TC], {TC + "::test_an_exhausted_setting_name_is_a_refusal"})]),
]
PLANTS = [p for p in PLANTS if ONLY is None or p[0] in ONLY]
EXCEPTION = re.compile(r"NameError")  # 심은 글이 이름 오류로 빨개지면 무효
GUARDED = {p[0] for p in PLANTS}


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str, str]:
    _name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        env.pop(name, None)
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last, text


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[3]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _failed, last, _ = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, checks) -> bool | None:
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
            if number in GUARDED and EXCEPTION.search(text):
                print(f"{label} 이름 오류로 빨강(무효 — 심은 글이 틀렸다)")
                hit = False
            hit_all = hit_all and hit
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - failed)} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        return None if skipped and hit_all else hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
try:
    for number, what, edits, checks in PLANTS:
        planted += 1
        result = plant_and_check(number, what, edits, checks)
        caught += 1 if result is True else 0
        print(f"{number} => {'잡음' if result else '안 돌림' if result is None else '못 잡음'}")
except KeyboardInterrupt:
    print("멈춤(INT·TERM) — 심은 파일은 되썼다")
same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
