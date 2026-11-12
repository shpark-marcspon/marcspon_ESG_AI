#!/usr/bin/env bash
# 밴드 DV1g 의 심은 파손(발주서 band-handoffs/DV1g-order.md §3-5, + 러너 몫 R1). 하나씩 심고 겨눈 시험만 돌린 뒤 원본
# 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-DV1g.sh [--commit <1|2|3>] [--with-containers] [--only P1,P4]
#   --commit n 이면 경계 n 까지의 파손만(기본 3 — 전부).
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 업무·보안 층(Postgres)은 --with-containers 일 때만 —
# 아니면 「안 돌림」으로 찍고 그 층은 건너뛴다(순수 층이 잡으면 잡음). 끝에 심은 파일의 sha256 과 git status 가 시작과
# 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: DV1g_OUT(기본: 워크트리 곁의 DV1g.out)/planted/.
# 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${DV1g_OUT:-$(cd "$ROOT/.." && pwd)/DV1g.out}"
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
COMMIT = 3
while args:
    if args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    elif args[0] == "--commit" and len(args) > 1:
        COMMIT, args = int(args[1]), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


DIGEST = Path("esgapi/dataverify/outputs/digest.py")
FLOW = Path("esgapi/dataverify/flows/colab_156.py")
TD = "esgapi/dataverify/tests/outputs/test_digest.py"
TF = "esgapi/dataverify/tests/flows/test_colab_156.py"
TREG = "esgapi/dataverify/tests/flows/test_registration.py"
BY_HAND = TD + "::test_the_digest_by_hand"
ACT = Path("esgapi/dataverify/service/actions/runs.py")
API = Path("esgapi/dataverify/service/apis/dataverify.py")
LIST = Path("esgapi/dataverify/contracts/run_list_shapes.py")
PERM = Path("esgapi/core/permissions.py")
SEL = Path("esgapi/runs/service/selectors/runs.py")
TL = "esgapi/dataverify/tests/service/apis/test_dataverify_runs.py"
TOP = "esgapi/dataverify/tests/service/apis/test_dataverify_operator.py"
TLS = "esgapi/dataverify/tests/contracts/test_run_list_shapes.py"
TP = "esgapi/core/tests/test_permissions.py"
TW = "esgapi/core/tests/test_permissions_wiring.py"
TRS = "esgapi/runs/tests/service/selectors/test_runs.py"
ROWS_FIRST = TL + "::test_the_rows_are_my_company_dataverify_runs_newest_first"
OUT_OF_SHAPE = TL + "::test_a_value_out_of_shape_is_null_and_the_row_stays"
SD = "tests/security/test_dataverify.py"
STP = "tests/security/test_tenant_paths.py"
TPATHS = Path("tests/security/test_tenant_paths.py")
S_LIST = SD + "::test_another_companys_list_carries_none_of_its_runs"
S_KIND = STP + "::test_the_dataverify_list_shows_only_my_company"
ROWS = TD + "::test_the_counts_match_the_workbook_rows"

PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (경계, 번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    (1, "P1", "notComputed 를 fail 로 셈",
     [(DIGEST, swap('                    counts["notComputed"] += 1\n', '                    counts["fail"] += 1\n'))],
     [(PURE, [TD], {f"{BY_HAND}[verdicts_only]", f"{ROWS}[verdicts_only]", f"{ROWS}[example]",
                    TD + "::test_the_example_counts_every_branch"})]),
    (1, "P2", "요약이 결과에 칸을 더함",
     [(FLOW, swap('data={"results": [result, dict(digest(result))]}',
                  'data={"results": [{**result, "digest": dict(digest(result))}, dict(digest(result))]}'))],
     [(PURE, [TF], {TF + "::test_s3_end_to_end_requests_outputs_and_result",
                    TF + "::test_s10_no_target_theme_runs_nothing"})]),
    (1, "P3", "result_shapes 에 digest 빠뜨림",
     [(FLOW, swap("result_shapes=(shapes.RESULT_SHAPE, DIGEST_SHAPE),", "result_shapes=(shapes.RESULT_SHAPE,),"))],
     [(PURE, [TF, TREG], {TF + "::test_s3_end_to_end_requests_outputs_and_result",
                          TREG + "::test_the_flow_declaration"})]),
    (1, "R1", "러너 몫: 값 있는 조회도 naValues 로 셈",
     [(DIGEST, swap('counts["naValues"] += 1 if check["na"] else 0', 'counts["naValues"] += 1'))],
     [(PURE, [TD], {f"{BY_HAND}[lookups_and_errors]", f"{ROWS}[lookups_and_errors]", f"{ROWS}[example]"})]),
    (2, "P4", "module 거름 뺌",
     [(ACT, swap("        module=MODULE,\n", "        module=None,\n"))],
     [(BUSINESS, [TL], {ROWS_FIRST})]),
    (2, "P5", "source 검사를 「dict·kind 만」으로(꼴 밖 행이 응답 검사에서 500)",
     [(ACT, swap('        return SOURCE.validate_python(options["source"], strict=True)\n',
                 '        found = options["source"]\n'
                 '        return found if isinstance(found, dict) and "kind" in found else None\n'))],
     [(BUSINESS, [TL], {f"{OUT_OF_SHAPE}[change0-nulls0]", f"{OUT_OF_SHAPE}[change1-nulls1]",
                        f"{OUT_OF_SHAPE}[change3-nulls3]", f"{OUT_OF_SHAPE}[change4-nulls4]"})]),
    (2, "P6", "줄에 options 째",
     [(ACT, swap('        "source": _source(run.options),\n', '        "source": _source(run.options),\n        "options": run.options,\n'))],
     [(BUSINESS, [TL], {ROWS_FIRST, TL + "::test_the_rows_carry_no_input_data_or_material_topics"})]),
    (2, "P7", "limit 의 le=20 뺌",
     [(API, swap("    limit: int = Field(default=20, ge=1, le=20)\n", "    limit: int = Field(default=20, ge=1)\n"))],
     [(BUSINESS, [TL], {TL + "::test_a_bad_query_is_422[?limit=21]"})]),
    (2, "P8", "컴포넌트 이름 Source(남의 컴포넌트와 겹침)",
     [(LIST, swap("class DataverifyPerson(TypedDict):", "class Source(TypedDict):")),
      (LIST, swap("    createdBy: DataverifyPerson\n", "    createdBy: Source\n")),
      (LIST, lambda text: text + "\nDataverifyPerson = Source\n")],
     [(PURE, [TLS], {TLS + "::test_every_component_name_has_the_dataverify_head"})]),
    (2, "P9", "권한 칸 CUSTOMER(운영 관리자 막힘)",
     [(PERM, swap('    "dataverify_runs_list": COMPANY,\n', '    "dataverify_runs_list": CUSTOMER,\n'))],
     [(PURE, [TP], {TP + "::test_both_kinds_do_the_company_work"}),
      (BUSINESS, [TOP], {TOP + "::test_the_operator_lists_the_work_company_runs_like_the_customer"})]),
    (2, "P10", "runs statuses 거름 무시",
     [(SEL, swap("        rows = rows.filter(status__in=statuses)\n", "        rows = rows\n"))],
     [(BUSINESS, [TRS, TL], {TRS + "::test_run_page_filters_by_a_status_set",
                             TL + "::test_the_status_filter_takes_several_values"})]),
    (2, "P11", "mine 이 created_by_user_id 를 안 넘김",
     [(ACT, swap("        created_by_user_id=user_id if mine else None,\n", "        created_by_user_id=None,\n"))],
     [(BUSINESS, [TL, TOP], {TL + "::test_mine_shows_only_the_runs_i_made",
                             TOP + "::test_the_operator_lists_the_work_company_runs_like_the_customer"})]),
    (2, "P12", "currentStep 을 processing 밖 실행에도",
     [(ACT, swap('current = _current(company_id, [r.id for r in found if r.status == "processing"])',
                 "current = _current(company_id, [r.id for r in found])")),
      (ACT, swap('        "currentStep": current.get(run.id) if run.status == "processing" else None,\n',
                 '        "currentStep": current.get(run.id),\n'))],
     [(BUSINESS, [TL], {TL + "::test_a_failed_step_on_a_done_run_and_a_running_step_on_a_failed_run_are_not_shown"})]),
    (2, "P13", "people_of 빼고 id 글자",
     [(ACT, swap("    names = people_of(company_id, wanted)\n", "    names = {u: (str(u), str(u)) for u in wanted}\n"))],
     [(BUSINESS, [TL], {ROWS_FIRST})]),
    (2, "R2", "러너 몫: 보고연도를 꼴(YYYY) 없이 글자면 그대로",
     [(ACT, swap("        return YEAR.validate_python(year, strict=True)\n",
                 "        return year if isinstance(year, str) else None\n"))],
     [(BUSINESS, [TL], {f"{OUT_OF_SHAPE}[change5-nulls5]"})]),
    (3, "P14", "회사 조건 없는 읽기(회사 id 를 훑어 남의 회사 실행까지 줄로)",
     [(ACT, swap("    found = [run for run, _name in page.runs]\n",
                 "    found = [run for c in range(1, 300) for run, _name in run_selectors.run_page(company_id=c, "
                 "module=MODULE, status=None, document_id=None, limit=limit, offset=0).runs]\n"))],
     [(SECURITY, [SD], {f"{S_LIST}[session]", f"{S_LIST}[bearer]"})]),
    (3, "P15", "dataverify_list 를 contract_only 로",
     [(TPATHS, swap('    ("GET", "/dataverify/runs"): "dataverify_list",\n', '    ("GET", "/dataverify/runs"): "contract_only",\n'))],
     [(SECURITY, [STP], {f"{S_KIND}[session]", f"{S_KIND}[bearer]"})]),
]
PLANTS = [p[1:] for p in PLANTS if p[0] <= COMMIT and (ONLY is None or p[1] in ONLY)]


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
    failed = set(re.findall(r"^FAILED (.+?)(?: - .*)?$", text, flags=re.M))
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


def plant_and_check(number: str, what: str, edits, checks) -> bool:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                return False
            f.write_text(new, encoding="utf-8")
        hit_all = True
        for layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            code, failed, _last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            hit_all = hit_all and hit
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - failed)} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        return hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
for number, what, edits, checks in PLANTS:
    planted += 1
    result = plant_and_check(number, what, edits, checks)
    caught += 1 if result else 0
    print(f"{number} => {'잡음' if result else '못 잡음'}")

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
