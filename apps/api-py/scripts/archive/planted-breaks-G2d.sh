#!/usr/bin/env bash
# 밴드 G2d(MARC-TICK-240: 판별 대상 단어를 AI 설정 판에 + 실행이 판의 켠 단어로 빈도를 셈)의 심은 파손(발주서
# band-handoffs/G2d-order.md §3-4). 틀은 planted-breaks-AS3a-2.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로
# 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 경계 ② = P1~P7, ③ = P8~P14. 웹 층(vitest — apps/web 에서)은 컨테이너가
# 필요 없다(처분 G2d-order-review-2 N8 — P7). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-G2d.sh --commit <2|3> [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도 — 웹 층은 vitest 의 빨간 시험
# 이름에 그 글이 듦). 파손 하나 = 하나로 센다.
# 업무 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은
# 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: G2D_OUT(기본: 워크트리 곁의 G2d.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G2D_OUT:-$(cd "$ROOT/.." && pwd)/G2d.out}"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
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
COMMIT = ""
while args:
    if args[0] == "--commit" and len(args) > 1:
        COMMIT, args = args[1], args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")
if COMMIT not in ("2", "3"):
    sys.exit("--commit 2 또는 3")


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
SVC = G / "service/services/ai_settings.py"
TERMS = G / "flows/terms_e0.py"
MIG = G / "migrations/0006_ai_settings_terms.py"
MODULES = Path("../web/src/app/admin/ai-setting-modules.ts")
TT = f"{T}/service/apis/test_ai_settings_terms.py"
TE = f"{T}/flows/test_terms_e0.py"
TM = f"{T}/test_migrations_0006.py"
TW = "src/app/admin/ai-setting-modules.test.ts"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가, 도는 자리)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False, ".")
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True, ".")
WEB = ("웹", ["pnpm", "exec", "vitest", "run"], False, "../web")

WORDS = "    words = None if terms is None else terms_e0.accept_terms(terms)\n"

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS_2 = [
    ("1", "create 가 단어 거절 무시",
     [(SVC, swap("    if isinstance(words, terms_e0.TermsRefused):\n        return TermsRefused(",
                 "    if False:\n        return TermsRefused("))],
     [(BUSINESS, [TT], {TT + "::test_one_refusal_writes_nothing[terms]",
                        TT + "::test_a_refused_term_is_400_with_the_field_path["})]),
    ("2", "받기 차례: 단어를 프롬프트 앞으로",
     [(SVC, move_after(WORDS, "    stored = to_input(model)\n",
                       "    texts = None if prompts is None else prompt_model_e0.accept_prompts(prompts)\n"))],
     [(BUSINESS, [TT], {TT + "::test_one_refusal_writes_nothing[prompts-before-terms]"})]),
    ("3", "키 겹침 검사 지움",
     [(TERMS, swap("        if key in seen:\n", "        if False:\n"))],
     [(PURE, [TE], {TE + "::test_a_key_duplicate_points_at_the_later_one"}),
      (BUSINESS, [TT], {TT + "::test_a_refused_term_is_400_with_the_field_path[duplicate]"})]),
    ("4", "보이지 않는 글자 검사 지움",
     [(TERMS, swap('    if any(unicodedata.category(char) in INVISIBLE for char in text):\n'
                   '        return "TERMS_TEXT_INVISIBLE"\n', ""))],
     [(PURE, [TE], {TE + "::test_a_bad_text_is_terms_text_at_its_index[bell]",
                    TE + "::test_a_bad_text_is_terms_text_at_its_index[zero-width]"}),
      (BUSINESS, [TT], {TT + "::test_a_refused_term_is_400_with_the_field_path[zero-width]"})]),
    ("5", "기본 목록과 같은 목록을 NULL 로 접음",
     [(SVC, swap("terms=None if words is None else terms_e0.terms_input(words),",
                 "terms=None if words is None or list(terms_e0.used_terms(words)) == list(colab_e0.DEFAULT_TERMS) "
                 "else terms_e0.terms_input(words),"))],
     [(BUSINESS, [TT], {TT + "::test_the_default_list_is_kept_as_a_value_and_a_terms_only_change_is_a_new_version"})]),
    ("6", "0006 크기 CHECK 상수 +1",
     [(MIG, swap("                        16384,\n", "                        16385,\n"))],
     [(BUSINESS, [TM], {TM + "::test_the_size_check_refuses_one_byte_over"})]),
    ("7", "복제 줄 terms 빠뜨림(AD-02 저장이 바탕 판 단어를 잃음)",
     [(MODULES, swap("          terms: loaded.setting.terms,\n", ""))],
     [(WEB, [TW], {"저장 판 바탕"})]),
]
BIND = G / "flows/binding_e0.py"
COLAB = G / "flows/colab_e0.py"
XLSX = G / "outputs/xlsx.py"
TB = f"{T}/flows/test_binding_e0_terms.py"
TBR = f"{T}/flows/test_binding_e0_terms_runs.py"
PLANTS_3 = [
    ("8", "접기(★G) 지움 — 켠 목록 = GREEN_TERMS 여도 판 단어로 셈",
     [(BIND, swap("        return None if used == tuple(colab.DEFAULT_TERMS) else used\n", "        return used\n"))],
     [(PURE, [TB], {TB + "::test_a_board_equal_to_green_terms_folds_to_the_code_list"})]),
    ("9", "칸 NULL 판에도 termsSha256",
     [(BIND, swap("            return versions  # 단어 칸 없는 판",
                  "            return {**versions, \"termsSha256\": terms_sha256(())}  # 단어 칸 없는 판"))],
     [(PURE, [TB], {TB + "::test_runs_without_board_terms_are_the_baseline_to_the_byte[b-saved-code-text]",
                    TB + "::test_runs_without_board_terms_are_the_baseline_to_the_byte[c-saved-text]",
                    TB + "::test_versions_carry_the_terms_sha_on_both_branches["})]),
    ("10", "inputs_with 의 sha 대조 지움",
     [(BIND, swap("        if terms_sha256(used) != versions.get(\"termsSha256\"):\n", "        if False:\n"))],
     [(PURE, [TB], {TB + "::test_one_changed_letter_of_the_sha_is_a_mismatch[model-key]",
                    TB + "::test_one_changed_letter_of_the_sha_is_a_mismatch[old-run-no-model-key]"})]),
    ("11", "칸⇔열쇠 검사를 checks_model 일찍 돌아가기 뒤로",
     [(BIND, move_after("        if (found.terms is not None) != checks_terms:",
                        "        try:\n            rebuilt = colab.run_versions(found.criteria)",
                        "        model = self._accepted(found)\n"))],
     [(PURE, [TB], {TB + "::test_field_and_key_must_go_together[code-text-old-run-no-model-key]",
                    TB + "::test_field_and_key_must_go_together[saved-text-old-run-no-model-key]"})]),
    ("12", "판 단어를 환경 낱말(②)로 샘",
     [(COLAB, swap("    if inputs.extra_terms:\n        config[\"env_keywords_extra\"] = [re.escape(term) for term in inputs.extra_terms]",
                   "    if inputs.extra_terms or inputs.terms:\n        config[\"env_keywords_extra\"] = "
                   "[re.escape(term) for term in (*inputs.extra_terms, *(inputs.terms or ()))]"))],
     [(PURE, [TB], {TB + "::test_an_added_word_is_counted_but_not_judged"})]),
    ("13", "합 목록에서 판 키 거르기 지움(extra 를 두 번 셈)",
     [(COLAB, swap("*(t for t in inputs.extra_terms if term_key(t) not in keys)]", "*inputs.extra_terms]"))],
     [(PURE, [TB], {TB + "::test_board_and_extra_terms_together",
                    TB + "::test_frequency_terms_matches_extras_beyond[board]"})]),
    ("14", "terms 없을 때도 엑셀에 「대상 단어」 줄",
     [(XLSX, swap('*([("대상 단어", _join(result["terms"], "\\n"))] if "terms" in result else [])',
                  '*[("대상 단어", _join(result.get("terms", []), "\\n"))]'))],
     [(PURE, [TB], {TB + "::test_runs_without_board_terms_are_the_baseline_to_the_byte[a-default]"})]),
]
PLANTS = PLANTS_2 if COMMIT == "2" else PLANTS_3
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
    name, cmd, _, cwd = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env, cwd=cwd)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    if name == "웹":  # vitest 의 빨간 줄(× …) — 기대는 그 줄에 든 글
        failed = set(re.findall(r"^ *(?:×|✗|FAIL) (.+)$", text, flags=re.M))
    else:
        failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


def hit(want: str, failed: set[str]) -> bool:
    if "::" not in want:  # 웹 층 — 빨간 시험 이름에 든 글
        return any(want in f for f in failed)
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
