#!/usr/bin/env bash
# 밴드 AS2a(MARC-TICK-215: 그린워싱 AI 설정 판의 프롬프트·모델 읽기 경로 둘)의 심은 파손(발주서
# band-handoffs/AS2a-order.md §3-4). 틀은 planted-breaks-G2c3.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로
# 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AS2a.sh [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 업무 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은
# 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: AS2A_OUT(기본: 워크트리 곁의 AS2a.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AS2A_OUT:-$(cd "$ROOT/.." && pwd)/AS2a.out}"
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
CONTAINERS = False
ONLY: set[str] | None = None
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


def move_after(block_start: str, block_end: str, anchor: str) -> Callable[[str], str | None]:
    """block_start 에서 block_end 앞까지의 덩이를 떼어 anchor 앞에 다시 넣는다(경로 차례 바꾸기)."""

    def plant(text: str) -> str | None:
        if text.count(block_start) != 1 or text.count(anchor) != 1:
            return None
        i = text.index(block_start)
        j = text.index(block_end, i + 1)
        block, rest = text[i:j], text[:i] + text[j:]
        k = rest.index(anchor)
        return rest[:k] + block + rest[k:]

    return plant


G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
PM = G / "flows/prompt_model_e0.py"
ACT = G / "service/actions/ai_settings.py"
API = G / "service/apis/ai_settings.py"
SEL = G / "service/selectors/ai_settings.py"
TP = f"{T}/flows/test_prompt_model_e0.py"
TAP = f"{T}/service/apis/test_ai_settings_prompt_model.py"
TPERM = "esgapi/core/tests/test_permissions.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)

BOARD = TP + "::test_the_default_board_passes_the_as1_shape_strictly"
DEFAULT_ROUTE = (
    '@router.get(\n    "/default/prompt-model",'
)

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", "actions prompt_model 이 criteria=None 을 넘김",
     [(ACT, swap("            criteria=found.criteria,\n", "            criteria=None,\n"))],
     [(BUSINESS, [TAP], {TAP + "::test_the_default_and_a_saved_board"})]),
    ("2", "판 글자를 judged_prompt_version 대신 \"x\"",
     [(PM, swap("    version = colab.judged_prompt_version(dict(colab.SCAN_CONFIG))\n", '    version = "x"\n'))],
     [(PURE, [TP], {BOARD, TP + "::test_the_eval_sha_is_the_run_versions_sha"})]),
    ("3", "/default/prompt-model 을 /{setting_id}/prompt-model 뒤로 옮김",
     [(API, move_after(DEFAULT_ROUTE, "@router.put(\n", '@router.post("", operation_id="greenwash_ai_setting_create"'))],
     [(BUSINESS, [TAP], {TAP + "::test_the_default_route_is_not_taken_as_an_id"})]),
    ("4", "JUDGE.tool_loop = True",
     [(PM, swap("    tool_loop=False,\n", "    tool_loop=True,\n"))],
     [(PURE, [TP], {TP + "::test_the_model_cell_is_the_colab_defaults"})]),
    ("5", "JUDGE_ROUTES 에 \"mock\" 더함",
     [(PM, swap('JUDGE_ROUTES: Final = ("light-openai-41", "standard-openai-41")',
                'JUDGE_ROUTES: Final = ("light-openai-41", "standard-openai-41", "mock")'))],
     [(PURE, [TP], {TP + "::test_the_spec_points_at_real_routes_only"})]),
    ("6", "actions 첫 줄 is_allowed 지움",
     [(ACT, swap('    if not is_allowed("greenwash_ai_setting_prompt_model", kind=actor_kind):\n'
                 '        return Forbidden("greenwash_ai_setting_prompt_model")\n', ""))],
     [(PURE, [TPERM], {TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"})]),
    ("7", "actions 의 except CriteriaRejected 지움",
     [(ACT, swap("    except CriteriaRejected as refused:\n        return services.SettingUnusable(",
                 "    except ZeroDivisionError as refused:\n        return services.SettingUnusable("))],
     [(BUSINESS, [TAP], {TAP + "::test_a_board_the_rules_no_longer_take_is_409"})]),
    ("8", "한 판 읽기의 회사 조건 지움(unscoped)",
     [(SEL, swap("    row = GreenwashAiSettingRow.for_company(company_id).filter(id=setting_id).first()\n"
                 "    return SettingMissing() if row is None else setting_of(row)\n",
                 '    row = GreenwashAiSettingRow._meta.managers_map["unscoped"].filter(id=setting_id).first()\n'
                 "    return SettingMissing() if row is None else setting_of(row)\n"))],
     [(BUSINESS, [TAP], {TAP + "::test_another_companys_board_is_the_same_404"})]),
    ("9", "프롬프트 차례 맞바꿈(repair ↔ low_only)",
     [(PM, swap('    ("repair", "다시 묻기", "repair_fix_prompt"),\n    ("low_only", "Low 전용", "low_only_prompt"),\n',
                '    ("low_only", "Low 전용", "low_only_prompt"),\n    ("repair", "다시 묻기", "repair_fix_prompt"),\n'))],
     [(PURE, [TP], {BOARD})]),
    ("10", "editable 의 prompts 를 True 로",
     [(PM, swap('"editable": {"prompts": False, "model": editable_model}', '"editable": {"prompts": True, "model": editable_model}'))],
     [(PURE, [TP], {BOARD})]),
]
if ONLY is not None:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def checks_of(plant):
    return plant[3]


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


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in checks_of(p):
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"[0] {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, what, edits, _ in PLANTS:
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
        for layer, targets, expected in checks_of(plant):
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
