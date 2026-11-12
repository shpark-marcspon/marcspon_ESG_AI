#!/usr/bin/env bash
# 밴드 G2c-1(MARC-TICK-187, 판정 기준표)의 심은 파손(발주서 band-handoffs/G2c-order.md §3-4). 하나씩 심고 돌린 뒤 원본
# 바이트로 되쓴다(git checkout·restore·stash 를 쓰지 않는다).
#   사용(apps/api-py 에서): scripts/planted-breaks-G2c.sh --commit <2|3>
#   --commit 2 는 커밋 ①② 몫(6·7·8 빼고 열둘), 3 은 열여섯 전부(16 은 가지 리뷰 3).
#
# 판정: 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이 전부 출력의
# FAILED 줄에 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>. 끝에 심은 파일들의 sha256 이 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 산출물: G2C_OUT(기본: 워크트리 곁의 G2c.out)/planted/. AI 호출 0(env -u 키).
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G2C_OUT:-$(cd "$ROOT/.." && pwd)/G2c.out}"
COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --commit <2|3>" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 2 | 3) ;; *) echo "--commit <2|3> 이 필요하다" >&2; exit 2 ;; esac
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python - "$OUT/planted" "$COMMIT" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
COMMIT = int(sys.argv[2])
G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
CRIT = G / "flows/criteria_e0.py"
FLOW = G / "flows/colab_e0.py"
PYTEST = ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider"]
E0 = PYTEST + [f"{T}/flows/test_criteria_e0.py", f"{T}/contracts/test_criteria_shapes.py"]
FL = PYTEST + [f"{T}/flows/test_criteria_flow.py"]
E0_TEST = "test_criteria_e0.py::"
SHAPES_TEST = "test_criteria_shapes.py::"
FLOW_TEST = "test_criteria_flow.py::"

# (번호, 커밋, 심는 것, 파일, 옛 글, 새 글, 돌릴 명령, 빨개져야 하는 것(전부 FAILED 줄에 있어야 함))
PLANTS = [
    (1, 2, "틀의 [등급] 앞 빈 줄 하나 지움", CRIT,
     '_HIGH_HEAD: Final = (\n    "",\n    "[등급]",', '_HIGH_HEAD: Final = (\n    "[등급]",',
     E0, [E0_TEST + "test_the_default_criteria_build_the_engine_text_byte_for_byte"]),
    (2, 2, '예외 앞머리 "-" → "- "', CRIT,
     '    "exception": "-",  # 노트북의 흠', '    "exception": "- ",  # 노트북의 흠',
     E0, [E0_TEST + "test_the_default_criteria_build_the_engine_text_byte_for_byte",
          E0_TEST + "test_editing_one_row_changes_that_line_only"]),
    (3, 2, "default_criteria() 의 high-1 글 한 글자", CRIT,
     '"절대적·단언적 표현(100%, 완전', '"절대적·단언적 표현(101%, 완전',
     E0, [E0_TEST + "test_the_default_criteria_build_the_engine_text_byte_for_byte",
          SHAPES_TEST + "test_the_default_example_is_the_default_criteria"]),
    (4, 2, "끈 줄을 빼지 않음", CRIT,
     '        if row["enabled"]:\n            lines[', '        if True:\n            lines[',
     E0, [E0_TEST + "test_turning_one_row_off_drops_that_line_only"]),
    (5, 2, "이어 붙인 글 전체에 .format(prompt_version=…)", CRIT,
     "            *_OUTPUT,\n        ]\n    )\n", "            *_OUTPUT,\n        ]\n    ).format(prompt_version=prompt_version)\n",
     E0, [E0_TEST + "test_braces_and_heads_in_a_row_stay_as_they_are"]),
    (6, 3, "judge 가 prompts=pack 을 넘기지 않음", FLOW,
     '    given: dict[str, Any] = {} if pack is None else {"prompts": pack}\n',
     "    given: dict[str, Any] = {}\n",
     FL, [FLOW_TEST + "test_the_edited_criteria_reach_the_provider_as_the_edited_eval"]),
    (7, 3, "judge 가 with_pack 을 부르지 않음", FLOW,
     "            llm = llm.with_pack(pack)\n", "            llm = llm\n",
     FL, [FLOW_TEST + "test_the_edited_criteria_reach_the_provider_as_the_edited_eval"]),
    (8, 3, 'criteria=None 에서도 eval_pack 을 지어 넘기되 판 글자 "X"', FLOW,
     "    pack = None if inputs.criteria is None else eval_pack(inputs.criteria, version)\n",
     "    from esgapi.greenwash.flows.criteria_e0 import default_criteria\n\n"
     '    pack = eval_pack(inputs.criteria or default_criteria(), "X" if inputs.criteria is None else version)\n',
     FL, [FLOW_TEST + "test_the_default_criteria_send_the_golden_messages"]),
    (9, 2, "받기에서 verdict 짝 검사를 지움", CRIT,
     '        if row["verdict"] != VERDICT[category]:\n            _reject("CRITERIA_ROW_KIND")\n', "",
     E0, [E0_TEST + "test_accept_refuses_with_its_sentence[verdict-pair]"]),
    (10, 2, "빈 구분이면 그 절 머리(▶ Mid 등)까지 지움", CRIT,
     "            *_MID_HEAD,\n", '            *(_MID_HEAD if lines["mid"] else ()),\n',
     E0, [E0_TEST + "test_an_empty_category_keeps_its_head_and_adds_nothing[mid]"]),
    (11, 2, "받기에서 줄바꿈 검사를 지움", CRIT,
     '    if not _one_line(text):\n        _reject("CRITERIA_TEXT_MULTILINE")\n    if row["terms"] is not None:',
     '    if row["terms"] is not None:',
     E0, [E0_TEST + "test_accept_refuses_with_its_sentence[text-lf]"]),
    (12, 2, "꼴에 칸 하나 더하고 고정 스키마를 다시 뽑지 않음", G / "contracts/criteria_shapes.py",
     "    guideline: GreenwashCriterionGuideline | None\n",
     "    guideline: GreenwashCriterionGuideline | None\n    note: str | None\n",
     E0, [SHAPES_TEST + "test_the_json_schema_is_pinned_byte_for_byte"]),
    (13, 2, "run_versions 의 열쇠 aiSetting → ai_setting", CRIT,
     '    return {"aiSetting": used["version"],', '    return {"ai_setting": used["version"],',
     E0, [E0_TEST + "test_the_run_versions_are_the_setting_name_and_the_eval_hash"]),
    (14, 2, "id 차례 표에서 두 줄 바꿈", CRIT,
     '    ("high-1", "high"),\n    ("high-2", "high"),\n', '    ("high-2", "high"),\n    ("high-1", "high"),\n',
     E0, [E0_TEST + "test_the_row_table_is_the_contract_order",
          SHAPES_TEST + "test_the_default_example_is_the_default_criteria"]),
    (15, 2, "빈 구분에 자리 표시 줄 「- (없음)」", CRIT,
     '            *lines["mid"],\n', '            *(lines["mid"] or ["- (없음)"]),\n',
     E0, [E0_TEST + "test_an_empty_category_keeps_its_head_and_adds_nothing[mid]"]),
    (16, 3, "다리 아닌 포트 + 고친 기준표에서 TypeError 를 내지 않음(가지 리뷰 3)", FLOW,
     "        elif pack.eval_system_prompt != default_prompts(version).eval_system_prompt:\n",
     "        elif False:\n",
     FL, [FLOW_TEST + "test_a_port_without_with_pack_fails_outside_the_page_loop"]),
]
PLANTS = [p for p in PLANTS if p[1] <= COMMIT]

files = sorted({p[3] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def red_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("FAILED")]


cmds = {tuple(p[6]) for p in PLANTS}
zero_ok = True
for i, cmd in enumerate(sorted(cmds)):
    code, _ = run(list(cmd), LOGS / f"00-{i}.log")
    zero_ok = zero_ok and code == 0
print(f"[0] 아무것도 안 심음: {'전부 초록' if zero_ok else '빨강이 있다'} ({len(cmds)} 명령)")

caught = 0
for num, _, what, path, old, new, cmd, want in PLANTS:
    original = path.read_bytes()
    text = original.decode("utf-8")
    if text.count(old) != 1:
        print(f"[{num}] {what}: 심을 자리를 못 찾음(옛 글이 {text.count(old)} 번) — 못 잡은 것으로 센다")
        continue
    try:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        code, out = run(cmd, LOGS / f"{num:02d}.log")
    finally:
        path.write_bytes(original)  # 손으로 되돌림
    reds = red_lines(out)
    hit = [w for w in want if any(w in line for line in reds)]
    ok = code != 0 and len(hit) == len(want)
    caught += ok
    print(f"[{num}] {what}: {'잡음' if ok else '못 잡음'} (종료 {code}, 빨간 줄 {len(reds)}, 기대 {len(hit)}/{len(want)})")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
for f in files:
    print(f"  {f} {end[f]}")
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
