#!/usr/bin/env bash
# 밴드 DV1d 의 심은 파손(발주서 band-handoffs/DV1d-order.md §3-3 — Q2 (나)라 P13 없음, + 러너 몫 P14). 하나씩 심고 겨눈
# 시험만 돌린 뒤 원본 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-DV1d.sh [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 업무 층(Postgres)은 --with-containers 일 때만 — 아니면
# 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다. 끝에 심은 파일의 sha256 과 git status 가 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: DV1d_OUT(기본: 워크트리 곁의 DV1d.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${DV1d_OUT:-$(cd "$ROOT/.." && pwd)/DV1d.out}"
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


OPT = Path("esgapi/dataverify/contracts/options_shapes.py")
BIND = Path("esgapi/dataverify/flows/binding_156.py")
APPS = Path("esgapi/dataverify/apps.py")
TB = "esgapi/dataverify/tests/flows/test_binding_156.py"
TA = "esgapi/dataverify/tests/test_apps.py"
TR = "esgapi/dataverify/tests/flows/test_runs_dataverify.py"

REFUSED = TB + "::test_refused_options_say_one_sentence_with_key_paths_only"
SAME = TB + "::test_the_input_verdict_is_the_same_as_check_input"
INPUTS = TB + "::test_inputs_pass_the_received_input_as_is_with_the_company_tags"
ORDER = TB + "::test_inputs_keep_the_item_key_order_of_the_received_input"
COSTS = TB + "::test_the_stage_costs_are_one_three_one_usd"
VERSIONS = TB + "::test_versions_are_engine_flow_prompt_ids_and_route"
VALUE = TB + "::test_a_value_planted_in_a_wrong_field_does_not_reach_the_sentence"
ADAPTERS = TB + "::test_adapters_use_the_run_client"
A_BOUND = TA + "::test_ready_registered_a_documentless_binding_with_the_256kib_limit"
A_AGAIN = TA + "::test_another_app_registry_does_not_register_again"
R_MADE = TR + "::test_post_runs_dataverify_without_a_document_is_201_with_the_versions"
R_DONE = TR + "::test_the_executor_runs_dataverify_to_done_with_a_result_and_the_workbook"
R_SENT = TR + "::test_the_requests_carry_the_stage_costs_web_search_and_the_run_and_company_tags"
R_REFUSED = TR + "::test_options_that_do_not_fit_are_400_with_the_binding_sentence_and_no_row"
R_20K = TR + "::test_options_of_20kib_are_over_the_default_16kib_and_still_accepted"
R_UNDER = TR + "::test_options_just_under_256kib_run_to_done"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)

REGISTER = (
    "        BINDINGS.register_documentless(\n"
    "            colab_156.FLOW_ID, DataverifyBinding(), max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS\n"
    "        )\n"
)
SEPARATE = (
    "DataverifyAdapters(llm=__import__('esgapi.dataverify.tests.flows.support', fromlist=['x']).real_client("
    "__import__('esgapi.core.llm.providers.mock', fromlist=['x']).MockProvider('openai')))"
)

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", "맨 위 모르는 열쇠 받음(FORBID 뺌)",
     [(OPT, swap("@with_config(FORBID)\nclass DataverifyOptions", "class DataverifyOptions"))],
     [(PURE, [TB], {f"{REFUSED}[webSearch]", f"{REFUSED}[maxCostUsd]", f"{REFUSED}[both]"}),
      (BUSINESS, [TR], {f"{R_REFUSED}[webSearch]"})]),
    ("P2", "input 검사 건너뜀",
     [(BIND, swap("        return OPTIONS_SHAPES[SHAPE].validate_python(options, strict=True)",
                  "        return options  # type: ignore[return-value]"))],
     [(PURE, [TB], {f"{REFUSED}[empty]", f"{REFUSED}[schemaVersion]", f"{SAME}[2]", f"{SAME}[3]"})]),
    ("P3", "web_search=False",
     [(BIND, swap("            web_search=True,", "            web_search=False,"))],
     [(PURE, [TB], {INPUTS}), (BUSINESS, [TR], {R_SENT})]),
    ("P4", "STAGE_COSTS.review 3.0→30.0",
     [(BIND, swap("StageCosts(plan=1.0, review=3.0, insight=1.0)", "StageCosts(plan=1.0, review=30.0, insight=1.0)"))],
     [(PURE, [TB], {COSTS}), (BUSINESS, [TR], {R_SENT})]),
    ("P5", "Tags module greenwash",
     [(BIND, swap('MODULE: Final = "dataverify"', 'MODULE: Final = "greenwash"'))],
     [(PURE, [TB], {INPUTS})]),
    ("P6", "Tags tenant 빈 글",
     [(BIND, swap("tags=Tags(tenant=str(company_id), module=MODULE)", 'tags=Tags(tenant="", module=MODULE)'))],
     [(PURE, [TB], {INPUTS}), (BUSINESS, [TR], {R_SENT})]),
    ("P7", "apps.py 가 register_documentless 빠뜨림",
     [(APPS, swap(REGISTER, ""))],
     [(PURE, [TA], {A_BOUND}), (BUSINESS, [TR], {R_MADE, R_DONE})]),
    ("P8", "전역 앱 가드 지움",
     [(APPS, swap("        if self.apps is not global_apps:\n            return\n", ""))],
     [(PURE, [TA], {A_AGAIN})]),
    ("P9", "versions 에서 promptIds 뺌",
     [(BIND, swap('            "promptIds": dict(prompts.PROMPT_IDS),\n', ""))],
     [(PURE, [TB], {VERSIONS}), (BUSINESS, [TR], {R_MADE})]),
    ("P10", "거절 문장에 값 글자",
     [(BIND, swap('raise RunOptionsRejected(f"옵션 {where}의 값이 맞지 않아요") from None',
                  'raise RunOptionsRejected(f"옵션 {where}의 값이 맞지 않아요 {error}") from None'))],
     [(PURE, [TB], {VALUE})]),
    ("P11", "adapters 가 따로 지은 클라이언트",
     [(BIND, swap("return DataverifyAdapters(llm=ctx.llm())", "return " + SEPARATE))],
     [(PURE, [TB], {ADAPTERS}), (BUSINESS, [TR], {R_SENT})]),
    ("P12", "max_options_bytes 지움(기본 16KiB)",
     [(APPS, swap(", max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS", ""))],
     [(PURE, [TA], {A_BOUND}), (BUSINESS, [TR], {R_20K, R_UNDER})]),
    ("P12b", "register_documentless 대신 register",
     [(APPS, swap(REGISTER, "        BINDINGS.register(colab_156.FLOW_ID, DataverifyBinding())\n"))],
     [(PURE, [TA], {A_BOUND}), (BUSINESS, [TR], {R_MADE, R_DONE})]),
    ("P14", "러너 몫: 받은 input 대신 검사 결과(복사본)를 넘김",
     [(BIND, swap('received = cast("Mapping[str, Any]", options["input"])',
                  'received = cast("Mapping[str, Any]", accept_options(options)["input"])'))],
     [(PURE, [TB], {INPUTS, ORDER})]),
]
PLANTS = [p for p in PLANTS if ONLY is None or p[0] in ONLY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    done = subprocess.run([*layer[1], *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


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
        code, _failed, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
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
            code, failed, _last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            hit_all = hit_all and hit
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - failed)} — {what}")
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
