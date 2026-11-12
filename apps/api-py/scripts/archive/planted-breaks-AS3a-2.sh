#!/usr/bin/env bash
# 밴드 AS3a-2(MARC-TICK-229: AI 설정 판에 프롬프트 글·칸 메모·판 이름 저장 + 실행이 판의 글로 부름)의 심은 파손
# (발주서 band-handoffs/AS3a-2-order.md §3-5). 틀은 planted-breaks-AS3a-1.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본
# 바이트로 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 경계 ② = P1~P10, ③ = P11~P16. 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AS3a-2.sh --commit <2|3> [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 업무 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은
# 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: AS3A2_OUT(기본: 워크트리 곁의 AS3a-2.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AS3A2_OUT:-$(cd "$ROOT/.." && pwd)/AS3a-2.out}"
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
API = G / "service/apis/ai_settings.py"
PM = G / "flows/prompt_model_e0.py"
MIG = G / "migrations/0005_ai_settings_prompts.py"
TPR = f"{T}/service/apis/test_ai_settings_prompts.py"
TP = f"{T}/flows/test_prompt_model_e0.py"
TM = f"{T}/test_migrations_0005.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)

STORED = "    stored_prompts = None if texts is None else prompts_input(texts)\n"
CODE_PACK = "colab_e0.default_prompts(colab_e0.judged_prompt_version(dict(colab_e0.SCAN_CONFIG)))"
PROMPTS_BLOCK = "    texts = None if prompts is None else prompt_model_e0.accept_prompts(prompts)\n"

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS_2 = [
    ("1", "create 가 프롬프트 거절 무시",
     [(SVC, swap("    if isinstance(texts, PromptRefused):\n        return PromptsRefused(",
                 "    if False:\n        return PromptsRefused("))],
     [(BUSINESS, [TPR], {TPR + "::test_one_refusal_writes_nothing[prompts]",
                         TPR + "::test_a_refused_prompt_is_400_with_the_field_path["})]),
    ("2", "받기 차례: 프롬프트를 모델 앞으로",
     [(SVC, move_after(PROMPTS_BLOCK, "    stored = to_input(model)\n", "    config = models.config()\n"))],
     [(BUSINESS, [TPR], {TPR + "::test_one_refusal_writes_nothing[model-before]"})]),
    ("3", "저장 칸에 메모 strip 빠짐(받은 글 그대로 저장)",
     [(SVC, swap(STORED, "    stored_prompts = None if texts is None else prompts\n"))],
     [(BUSINESS, [TPR], {TPR + "::test_saved_text_is_kept_byte_for_byte_and_the_memo_is_stripped"})]),
    ("4", "eval_prompt_sha256 을 기준표로 셈",
     [(SVC, swap("            if texts is None\n            else sha256_text(", "            if True\n            else sha256_text("))],
     [(BUSINESS, [TPR], {TPR + "::test_saved_text_is_kept_byte_for_byte_and_the_memo_is_stripped"})]),
    ("5", "apply 의 프롬프트 다시 받기 지움",
     [(SVC, swap("        if isinstance(texts, PromptRefused):\n            return SettingUnusable(texts.code, found.name)\n",
                 "        pass\n"))],
     [(BUSINESS, [TPR], {TPR + "::test_a_saved_text_the_rules_no_longer_take_is_unusable"})]),
    ("6", "EDITABLE_PROMPTS = False",
     [(PM, swap("EDITABLE_PROMPTS: Final = True\n", "EDITABLE_PROMPTS: Final = False\n"))],
     [(PURE, [TP], {TP + "::test_the_default_board_shows_the_new_cells"}),
      (BUSINESS, [TPR], {TPR + "::test_saved_text_is_kept_byte_for_byte_and_the_memo_is_stripped"})]),
    ("7", "코드 글과 같으면 NULL 로 접음",
     [(SVC, swap(STORED, f"    stored_prompts = None if texts is None or colab_e0.pack_from(texts) == {CODE_PACK} "
                 "else prompts_input(texts)\n"))],
     [(BUSINESS, [TPR], {TPR + "::test_an_edited_output_section_warns_and_a_code_text_is_not_folded"})]),
    ("8", "400 의 fields 빠짐",
     [(API, swap("fields={saved.field: [saved.message]}", "fields=None"))],
     [(BUSINESS, [TPR], {TPR + "::test_a_refused_prompt_is_400_with_the_field_path[",
                         TPR + "::test_the_total_size_is_refused_by_the_rule_not_the_database"})]),
    ("9", "0005 크기 CHECK 상수 +1",
     [(MIG, swap('_octets_at_most("prompts", 131072)', '_octets_at_most("prompts", 131073)'))],
     [(BUSINESS, [TM], {TM + "::test_the_size_checks_refuse_one_byte_over"})]),
    ("10", "title strip 빠짐",
     [(API, swap("StringConstraints(strip_whitespace=True, min_length=1", "StringConstraints(strip_whitespace=False, min_length=1"))],
     [(BUSINESS, [TPR], {TPR + "::test_a_bad_title_is_422[blank]"})]),
]
BIND = G / "flows/binding_e0.py"
COLAB = G / "flows/colab_e0.py"
TBP = f"{T}/flows/test_binding_e0_prompts.py"
TBS = f"{T}/flows/test_binding_e0_settings.py"
TRUNS = f"{T}/flows/test_binding_e0_settings_runs.py"
EVAL_SHA = '        if sha256_text(pack.eval_system_prompt) != versions.get("evalPromptSha256"):\n'
TEXT_SHA = '        if prompts_sha256(texts) != versions.get("promptsSha256"):\n'

PLANTS_3 = [
    ("11", "코드 글 판에도 promptsSha256",
     [(BIND, swap("            return versions  # 코드 글 판", '            return {**versions, "promptsSha256": "0" * 64}  # 코드 글 판'))],
     [(PURE, [TBP, TBS], {TBP + "::test_versions_with_a_code_text_or_the_default_have_no_prompts_key",
                          TBS + "::test_versions_with_a_saved_setting_rebuilds_its_sha"})]),
    ("12", "inputs_with 의 두 sha 대조 지움",
     [(BIND, swap(EVAL_SHA, "        if False:\n")), (BIND, swap(TEXT_SHA, "        if False:\n"))],
     [(PURE, [TBP], {TBP + "::test_inputs_with_one_sha_changed_fails[prompts-sha]", TBP + "::test_inputs_with_one_sha_changed_fails[eval-sha]"})]),
    ("13", "열쇠⇔칸 검사를 checks_model 일찍 돌아가기 뒤로",
     [(BIND, move_after("        if (found.prompts is not None) != checks_prompts:",
                        "        try:\n            rebuilt = colab.run_versions(found.criteria)",
                        "        model = self._accepted(found)\n"))],
     [(PURE, [TBP], {TBP + "::test_inputs_with_a_key_and_field_that_disagree_fail[key-only-before-as2b]"})]),
    ("14", "기본 판 열쇠 검사 지움",
     [(BIND, swap("            if checks_prompts:\n                raise AiSettingMismatch(",
                  "            if False:\n                raise AiSettingMismatch("))],
     [(PURE, [TBP], {TBP + "::test_inputs_with_a_prompts_key_on_the_default_fails"})]),
    ("15", "_scan_pages 가 inputs.prompts 무시",
     [(COLAB, swap("    if inputs.prompts is not None:\n        pack: PromptPack | None = inputs.prompts",
                   "    if False:\n        pack: PromptPack | None = inputs.prompts"))],
     [(PURE, [TBP], {TBP + "::test_the_saved_texts_reach_the_provider_as_they_are"}),
      (BUSINESS, [TRUNS], {TRUNS + "::test_a_run_on_saved_texts_calls_the_provider_with_those_texts"})]),
    ("16", "dry-run 막음 지움",
     [(COLAB, swap("        if inputs.prompts is not None:\n            raise ValueError(",
                   "        if False:\n            raise ValueError("))],
     [(PURE, [TBP], {TBP + "::test_a_dry_run_with_saved_texts_is_refused"})]),
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
