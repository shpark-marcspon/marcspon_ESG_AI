#!/usr/bin/env bash
# 밴드 G1b-1(MARC-TICK-191: 그린워싱 끼움·결과·검토·목록 줄)의 심은 파손(발주서 band-handoffs/G1b-order.md §3-6).
# 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를
# 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-G1b.sh [--commit 1|2|3] [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 커밋 n 에는 커밋 n 까지의 파손만 심는다(검사마다 커밋도 따로 — 그 커밋에 생긴 시험만). 업무·보안 층(컨테이너)은
# --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: G1B_OUT(기본: 워크트리 곁의 G1b.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G1B_OUT:-$(cd "$ROOT/.." && pwd)/G1b.out}"
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
BINDING = G / "flows/binding_e0.py"
FLOW = G / "flows/colab_e0.py"
APPS = G / "apps.py"
T = "esgapi/greenwash/tests"
TB = f"{T}/flows/test_binding_e0.py"
TO = f"{T}/contracts/test_options_shapes.py"
TA = f"{T}/test_apps_binding.py"
TN = f"{T}/flows/test_colab_e0_no_text_layer.py"
TR = f"{T}/flows/test_binding_e0_runs.py"
ACT = G / "service/actions/review.py"
SEL = G / "service/selectors/review.py"
TV = f"{T}/service/apis/test_greenwash_review.py"
TC = f"{T}/service/apis/test_greenwash_checks.py"
CHECKS = G / "service/actions/checks.py"
SEC = "tests/security/test_greenwash.py"
TSTATIC = "esgapi/core/tests/isolation/test_static_rules.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(검사 커밋, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", 1, "check_options 의 모르는 열쇠 검사 지움",
     [(BINDING, swap('    if unknown:\n        raise RunOptionsRejected(f"알 수 없는 옵션이에요: {_keys(unknown)}")\n', ""))],
     [(1, PURE, [TB, TO], {TB + "::test_bad_options_are_refused_with_the_sentence[criteria]",
                           TB + "::test_bad_options_are_refused_with_the_sentence[report-year]",
                           TO + "::test_the_shape_refuses_what_the_binding_refuses[unknown-key]"})]),
    ("2", 1, "pages_to_notebook 이 구간 끝을 하나 빼먹음",
     [(BINDING, swap('f"{ordered[i]}~{ordered[j]}"', 'f"{ordered[i]}~{ordered[j] - 1}"'))],
     [(1, PURE, [TB], {TB + "::test_pages_to_notebook[", TB + "::test_the_notebook_reader_gives_the_set_back[",
                       TB + "::test_the_bound_inputs_are_the_golden_inputs",
                       TB + "::test_the_bound_flow_matches_the_golden_through_core_llm"})]),
    ("3", 1, "adapters 가 LlmChatBridge 대신 감싼 다리를 냄",
     [(BINDING, swap("            llm=colab.LlmChatBridge(ctx.llm(), route=self.chat_route, tags=tags),\n",
                     '            llm=type("Wrapped", (), {"invoke": lambda _, m, b=colab.LlmChatBridge(ctx.llm(), '
                     'route=self.chat_route, tags=tags): b.invoke(m)})(),\n'))],
     [(1, PURE, [TB], {TB + "::test_adapters_are_a_bridge_with_the_tenant_tags_and_no_coordinates",
                       TB + "::test_the_default_binding_uses_the_real_route_names"})]),
    ("4", 1, "apps.py 의 BINDINGS.register 지움",
     [(APPS, swap('        BINDINGS.register(colab.FLOW_ID, GreenwashBinding())  # 끼움(G1b) — 실제 경로 이름\n', ""))],
     [(1, PURE, [TA], {TA + "::test_ready_registered_the_binding_with_the_real_routes"}),
      (1, BUSINESS, [TR], {TR + "::test_the_process_binding_is_the_greenwash_binding_with_real_routes",
                           TR + "::test_post_runs_greenwash_is_201_with_the_versions"})]),
    ("5", 1, "NoTextLayer 갈래 지움",
     [(FLOW, swap('    if not any(page.strip() for page in pages):\n        raise NoTextLayer("글자 층이 없는 문서예요")\n', ""))],
     [(1, PURE, [TN], {TN + "::test_a_pdf_without_any_text_fails_in_extract_with_no_text_layer",
                       TN + "::test_whitespace_only_pages_are_no_text["}),
      (1, BUSINESS, [TR], {TR + "::test_a_pdf_without_a_text_layer_fails_in_extract"})]),
    ("13", 1, "versions 가 run_versions 대신 {}",
     [(BINDING, swap("        return colab.run_versions(None)\n", "        return {}\n"))],
     [(1, PURE, [TB], {TB + "::test_versions_are_run_versions_without_flow"}),
      (1, BUSINESS, [TR], {TR + "::test_post_runs_greenwash_is_201_with_the_versions"})]),
    # ── 커밋 ② ──
    ("6", 2, "검토 PUT 의 잠금 검사 지움",
     [(ACT, swap('    if review is not None and review.state == "confirmed":\n        return ReviewLocked()\n', ""))],
     [(2, BUSINESS, [TV], {TV + "::test_the_review_state_machine"}),
      (3, SECURITY, [SEC], {SEC + "::test_a_put_that_overlaps_a_confirm_is_locked"})]),
    ("7", 2, "확정 때 미검토 채우기 지움",
     [(ACT, swap('            wanted.setdefault(index, ("adopted", None))\n', "            pass\n"))],
     [(2, BUSINESS, [TV], {TV + "::test_the_review_state_machine"})]),
    ("8", 2, "검토 selector 의 회사 조건 지움(for_company → unscoped)",
     [(SEL, swap("    row = GreenwashReviewRow.for_company(company_id).filter(run_id=run_id).first()\n",
                 "    row = GreenwashReviewRow.unscoped.filter(run_id=run_id).first()\n"))],
     [(2, PURE, [TSTATIC], {TSTATIC + "::test_product_code_opens_company_tables_only_through_for_company",
                            TSTATIC + "::test_product_code_does_not_use_unscoped"}),
      (2, BUSINESS, [TV], {TV + "::test_another_companys_review_rows_on_the_same_run_id_do_not_leak"})]),
    ("9", 2, "감사 adopt 를 바뀐 것만이 아니라 표시 전부에 씀",
     [(ACT, swap("        if new == old:\n            continue\n", ""))],
     [(2, BUSINESS, [TV], {TV + "::test_the_audit_lines_follow_what_changed"})]),
    ("10", 2, "itemIndex 범위 검사 지움",
     [(ACT, swap("        if not 0 <= index < items:\n", "        if False:\n"))],
     [(2, BUSINESS, [TV], {TV + "::test_bad_marks_are_400_and_write_nothing[range]"})]),
    ("11", 2, "결과 GET 이 done 검사 없이 냄",
     [(ACT, swap('    if run.status != "done":\n        return RunNotDone(run.status)\n', ""))],
     [(2, BUSINESS, [TV], {TV + "::test_a_run_that_is_not_done_is_409_everywhere["})]),
    ("14", 2, "갈아 넣기에서 보내지 않은 itemIndex 를 NULL 로 UPDATE 하지 않음(B2)",
     [(ACT, swap("            updates[index] = (None, None)  # 보내지 않은 표시 = 미검토(DELETE 없음)\n",
                 "            pass\n"))],
     [(2, BUSINESS, [TV], {TV + "::test_the_review_state_machine", TV + "::test_the_audit_lines_follow_what_changed"})]),
    ("16", 2, "표시 UPDATE 가 run_id 조건 없이 itemIndex 로만 고름(검증 2 B2)",
     [(G / "service/services/review.py",
       swap(".filter(run_id=run_id, item_index=index).update(", ".filter(item_index=index).update("))],
     [(2, BUSINESS, [TV], {TV + "::test_a_put_leaves_the_marks_of_another_run_alone"})]),
    ("17", 2, "표시 CHECK 의 decision IS NOT NULL 지움 — NULL decision + 사유가 지남(검증 2 B1)",
     [(G / "migrations/0001_initial.py",
       swap('("decision", "excluded"), ("decision__isnull", False), ("exclude_reason__isnull", False)',
            '("decision", "excluded"), ("exclude_reason__isnull", False)')),
      (G / "models.py",
       swap('models.Q(decision__isnull=False, decision="excluded", exclude_reason__isnull=False)',
            'models.Q(decision="excluded", exclude_reason__isnull=False)'))],
     [(2, SECURITY, [SEC], {SEC + "::test_the_decision_check_holds_for_the_app_role["})]),
    ("15", 2, "확정 PUT 의 없음→채택에도 adopt 줄을 씀(B5)",
     [(ACT, swap('        if new == "adopted" and not (confirm and old is None):\n', '        if new == "adopted":\n'))],
     [(2, BUSINESS, [TV], {TV + "::test_the_audit_lines_follow_what_changed"})]),
]
PLANTS += [
    # ── 커밋 ③ ──
    ("12", 3, "목록 줄이 다른 모듈의 실행도 실음",
     [(CHECKS, swap("company_id=company_id, module=MODULE, status=None", "company_id=company_id, module=None, status=None"))],
     [(3, BUSINESS, [TC], {TC + "::test_the_rows_carry_the_greenwash_runs_and_their_documents"})]),
]
PLANTS = [p for p in PLANTS if p[1] <= COMMIT and (ONLY is None or p[0] in ONLY)]


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
