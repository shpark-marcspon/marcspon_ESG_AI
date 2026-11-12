#!/usr/bin/env bash
# 밴드 G1b-2b(MARC-TICK-205: 그린워싱 좌표 엔진 꽂기·목록 줄 묶음 읽기·truncated·failedPageCount·보고서 GET 손질)의
# 심은 파손(발주서 band-handoffs/G1b-2b-order.md §3 — ①~③ = 커밋 ①, ④~⑨ = ②, ⑩·⑪ = ③).
# 틀은 planted-breaks-G1b-2a.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로 되쓴다(git checkout·restore·stash 를
# 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-G1b-2b.sh [--commit 1|2|3] [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 커밋 n 에는 커밋 n 까지의 파손만 심는다. 업무·보안 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로
# 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: G1B2B_OUT(기본: 워크트리 곁의 G1b-2b.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G1B2B_OUT:-$(cd "$ROOT/.." && pwd)/G1b-2b.out}"
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
COLAB = G / "flows/colab_e0.py"
BINDING = G / "flows/binding_e0.py"
TL = f"{T}/flows/test_locate_closing.py"
TB = f"{T}/flows/test_binding_e0.py"
TC = f"{T}/flows/test_binding_e0_coordinates_runs.py"
CHECKS = G / "service/actions/checks.py"
RUNS_SEL = Path("esgapi/runs/service/selectors/runs.py")
DOCS_SEL = Path("esgapi/core/service/selectors/documents.py")
TK = f"{T}/service/apis/test_greenwash_checks.py"
TKB = f"{T}/service/apis/test_greenwash_checks_batch.py"
TR = f"{T}/service/apis/test_greenwash_report.py"
TT = "esgapi/core/tests/test_selectors_tenant.py"
TRS = "esgapi/runs/tests/service/selectors/test_runs.py"
TS = "tests/security/test_greenwash.py"
REPORT = G / "service/actions/report.py"
REPORT_API = G / "service/apis/greenwash.py"
TH = f"{T}/service/apis/test_greenwash_report_headers.py"
QUERY = {TK + "::test_the_query_count_is_a_constant_k_whatever_the_run_count",
         TKB + "::test_the_query_count_is_the_same_for_one_run_and_five"}

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(검사 커밋, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", 1, "locate 의 close 지움",
     [(COLAB, swap("    finally:\n        coordinates.close()\n", "    finally:\n        pass\n"))],
     [(1, PURE, [TL], {TL + "::test_a_closing_port_is_closed_after_the_stats_are_put_in_the_step_data",
                       TL + "::test_a_closing_port_is_closed_when_locate_raises",
                       TL + "::test_pdfium_coordinates_in_the_flow_are_closed_with_stats_in_the_locate_data"})]),
    ("2", 1, "stats 안 실음",
     [(COLAB, swap('data={"positions": positions, "stats": stats}', 'data={"positions": positions}'))],
     [(1, PURE, [TL], {TL + "::test_a_closing_port_is_closed_after_the_stats_are_put_in_the_step_data",
                       TL + "::test_pdfium_coordinates_in_the_flow_are_closed_with_stats_in_the_locate_data"}),
      (1, BUSINESS, [TC], {TC + "::test_a_bound_run_on_a_built_pdf_fills_positions_and_puts_the_stats_in_the_locate_step",
                           TC + "::test_resuming_a_run_failed_in_report_carries_the_locate_data_and_does_not_locate_again"})]),
    ("3", 1, "adapters 가 좌표 인스턴스를 모듈 전역 하나로",
     [(BINDING, swap("            coordinates=PdfiumCoordinates(),\n",
                     '            coordinates=globals().setdefault("_PLANTED_SHARED", PdfiumCoordinates()),\n'))],
     [(1, PURE, [TB], {TB + "::test_adapters_are_a_bridge_with_the_tenant_tags_and_a_new_pdfium_coordinates_per_call"})]),
    ("4", 2, "단계 묶음 읽기를 실행마다 step_rows 로 되돌림",
     [(CHECKS, swap("            for s in step_rows.get(run.id, ())\n",
                    "            for s in run_selectors.step_rows(company_id=company_id, run_id=run.id)\n"))],
     [(2, BUSINESS, [TK, TKB], QUERY)]),
    ("5", 2, "truncated 를 늘 false",
     [(CHECKS, swap('"truncated": page.count > RUNS_MAX,', '"truncated": False,'))],
     [(2, BUSINESS, [TKB], {TKB + "::test_truncated_is_true_only_past_runs_max"})]),
    ("6", 2, "묶음 selector 셋의 회사 조건 지움(unscoped)",
     [(RUNS_SEL, swap("_steps(company_id).filter(run_id__in=run_ids)", "RunStepRow.unscoped.filter(run_id__in=run_ids)")),
      (RUNS_SEL, swap("RunResultRow.for_company(company_id).filter(run_id__in=run_ids)",
                      "RunResultRow.unscoped.filter(run_id__in=run_ids)")),
      (DOCS_SEL, swap("_documents(company_id).filter(pk__in=document_ids)", "DocumentRow.unscoped.filter(pk__in=document_ids)"))],
     [(2, BUSINESS, [TT, TRS], {TT + "::test_documents_of_leaves_out_another_tenants_documents",
                                TRS + "::test_step_rows_of_leaves_out_another_tenants_runs",
                                TRS + "::test_results_of_leaves_out_another_tenants_runs"}),
      (2, SECURITY, [TS], {TS + "::test_the_batch_reads_return_no_rows_of_another_company"})]),
    ("7", 2, "문서 칸(reportYear)이 묶음 뒤 None",
     [(CHECKS, swap('            "reportYear": d.report_year,\n', '            "reportYear": None,\n'))],
     [(2, BUSINESS, [TR, TKB], {TR + "::test_the_checks_row_reads_the_document_cells",
                                TKB + "::test_the_document_cells_keep_their_values_after_the_batch_read"})]),
    ("8", 2, "failedPageCount 를 실행마다 run_results 로 읽음",
     [(CHECKS, swap('"failedPageCount": _failed_page_count(result),',
                    '"failedPageCount": _failed_page_count(_result_of(run, {run.id: run_selectors.run_results('
                    'company_id=company_id, run_id=run.id)})),'))],
     [(2, BUSINESS, [TK, TKB], QUERY)]),
    ("9", 2, "failedPageCount 를 늘 null",
     [(CHECKS, swap('"failedPageCount": _failed_page_count(result),', '"failedPageCount": None,'))],
     [(2, BUSINESS, [TK, TKB], {TK + "::test_the_rows_carry_the_greenwash_runs_and_their_documents",
                                TKB + "::test_the_failed_page_count_comes_from_the_done_result"}),
      (2, SECURITY, [TS], {TS + "::test_the_checks_list_after_the_batch_read_shows_only_my_company"})]),
    ("10", 3, "보고서 응답의 nosniff 줄 지움",
     [(REPORT_API, swap('    response["X-Content-Type-Options"] = "nosniff"\n', ""))],
     [(3, BUSINESS, [TH], {TH + "::test_the_report_response_says_nosniff"}),
      (3, SECURITY, [TS], {TS + "::test_the_report_download_says_nosniff_with_the_xlsx_type"})]),
    ("11", 3, "extraTerms 기본값 지움(옛 꼴 결과 500)",
     [(REPORT, swap('filled: dict[str, Any] = {**result, "extraTerms": result.get("extraTerms") or []}',
                    "filled: dict[str, Any] = result"))],
     [(3, BUSINESS, [TH], {TH + "::test_an_old_result_without_extra_terms_is_a_report_without_added_terms"})]),
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
