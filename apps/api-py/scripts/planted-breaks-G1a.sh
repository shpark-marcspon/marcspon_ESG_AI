#!/usr/bin/env bash
# 밴드 G1a 의 심은 파손(발주서 §4 마-18). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 —
# git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-G1a.sh
#
# 판정(X2 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이
# 출력의 FAILED 줄(또는 lint-imports 의 BROKEN 줄)에 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 끝에 심은 파일들의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF).
# 산출물: G1A_OUT(기본: 워크트리 곁의 G1a.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G1A_OUT:-$(cd "$ROOT/.." && pwd)/G1a.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
PYTEST = ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider"]
LINT = ["uv", "run", "--frozen", "lint-imports"]

# (번호, 심는 것, 파일, 옛 글, 새 글, 돌릴 명령, 빨개져야 하는 것(FAILED/BROKEN 줄에 들어야 하는 글 — 하나라도))
PLANTS = [
    (1, "calc/wordcount.py 의 빠진 쉼표 하나를 넣음", G / "calc/wordcount.py", '    "eco프리",\n', '    "eco",\n    "프리",\n',
     PYTEST + [f"{T}/test_copy_ast.py", f"{T}/flows/test_colab.py"], ["test_a_copy_has_the_gw1_ast[wordcount.py]", "test_contrast_a_matches_gw1"]),
    (2, "calc/heuristics.py 의 의지 표현 정규식 한 글자", G / "calc/heuristics.py", '\n        r"확대해\\s*나가겠습니다|', '\n        r"확대해\\s*나가겠읍니다|',
     PYTEST + [f"{T}/test_copy_ast.py", f"{T}/flows/test_colab.py"], ["test_a_copy_has_the_gw1_ast[heuristics.py]", "test_contrast_a_matches_gw1"]),
    (3, "2,500 → 2,501 (자리는 calc/checker.py 의 GWConfig — 발주서는 heuristics 라 했다)", G / "calc/checker.py",
     "    max_chars_page_text: int = 2500\n", "    max_chars_page_text: int = 2501\n",
     PYTEST + [f"{T}/calc/test_checker.py"], ["test_config_defaults_and_sanitize"]),
    (4, "prompts/detect/1.md 의 구획 안에 비공백 글자 하나", G / "prompts/detect/1.md", "{{system}}\n", "{{system}}X\n",
     PYTEST + [f"{T}/flows/test_adapters.py"], ["test_contrast_b_through_core_llm_is_the_same"]),
    (5, "judge 가 resume 의 done_pages 를 건너뛰지 않음", G / "calc/checker.py",
     "        if page_no in done_pages:\n            continue", "        if page_no in done_pages:\n            pass",
     PYTEST + [f"{T}/flows/test_colab.py"], ["test_contrast_d_resume_after_the_second_page"]),
    (6, "judge 가 checkpoint 를 부르지 않음", G / "flows/colab.py",
     "        checkpoint=checkpoint,\n", "",
     PYTEST + [f"{T}/flows/test_colab.py"], ["test_the_judge_reports_progress_page_by_page"]),
    (7, "벡터 파일의 줄 차례를 뒤집어 씀", G / "flows/colab.py",
     '    blob = matrix.astype("<f4").tobytes()', '    blob = matrix[::-1].astype("<f4").tobytes()',
     PYTEST + [f"{T}/flows/test_colab.py"], ["test_contrast_a_matches_gw1"]),
    (8, "결과의 schemaVersion 을 둘째 키로", G / "flows/colab.py",
     '        "schemaVersion": RESULT_SHAPE,\n        "source": {"file_name": inputs.file_name, "sha256": ext["sha256"], "page_count": ext["page_count"]},\n',
     '        "source": {"file_name": inputs.file_name, "sha256": ext["sha256"], "page_count": ext["page_count"]},\n        "schemaVersion": RESULT_SHAPE,\n',
     PYTEST + [f"{T}/flows/test_colab.py"], ["test_contrast_a_matches_gw1"]),
    (9, "결과 꼴에서 position 칸을 뺌", G / "flows/shapes.py",
     "    position: Position | None\n", "",
     PYTEST + [f"{T}/flows/test_shapes.py"], ["test_the_json_schema_is_pinned"]),
    (10, "counts.by_part 에서 두 파트 쪽을 한 번만 셈", G / "flows/colab.py",
     '        part: {level: sum(1 for r in rows if r["level"] == level) for level in LEVELS}',
     '        part: {level: sum(1 for r in rows if r["level"] == level and r["parts"][0] == part) for level in LEVELS}',
     PYTEST + [f"{T}/flows/test_colab.py"], ["test_counts_by_part_count_a_page_in_two_parts_twice"]),
    (11, "flows/registration.py 의 DEFAULTS 에서 greenwash 줄을 뺌", G / "flows/registration.py",
     'DEFAULTS: Final[dict[str, str]] = {"greenwash": "greenwash.colab@E0"}', "DEFAULTS: Final[dict[str, str]] = {}",
     PYTEST + [f"{T}/flows/test_registration.py"], ["test_registration_into_a_fresh_registry", "test_ready_registered_the_flow_as_the_default"]),
    (12, "apps.py 의 지킴(self.apps is not global_apps)을 뺌", G / "apps.py",
     "        if self.apps is not global_apps:\n            return\n", "",
     PYTEST + [f"{T}/test_apps.py"], ["test_another_app_registry_does_not_register_again"]),
    (13, "flows/colab.py 에 import django", G / "flows/colab.py",
     "import hashlib\n", "import hashlib\n\nimport django  # noqa: F401\n",
     LINT, ["다. 순수 모듈"]),
    (14, "flows/adapters.py 에서 openai.OpenAI() 를 짓는 줄", G / "flows/adapters.py",
     "class PdfTextPort(Protocol):", "def _client() -> object:\n    import openai  # type: ignore\n\n    return openai.OpenAI()\n\n\nclass PdfTextPort(Protocol):",
     PYTEST + [f"{T}/flows/test_boundary.py"], ["test_flow_modules_touch_nothing_outside_their_adapters"]),
    (15, "dry-run 인데 judge 가 llm.invoke 를 한 번 부름", G / "flows/colab.py",
     '        counter = cast("TokenCounter", adapters.tokens)\n',
     '        counter = cast("TokenCounter", adapters.tokens)\n        adapters.llm.invoke([])\n',
     PYTEST + [f"{T}/flows/test_colab.py"], ["test_dry_run_counts_without_calling_llm_or_embedding"]),
    (16, "엑셀 문장 시트에서 마지막 줄을 빠뜨림", G / "flows/xlsx.py",
     "    for row in sentence_rows(result):\n", "    for row in sentence_rows(result)[:-1]:\n",
     PYTEST + [f"{T}/flows/test_xlsx.py"], ["test_the_workbook_holds_the_result"]),
    (17, "점검 쪽이 없는데 index 가 임베딩을 부름", G / "flows/colab.py",
     "        # GW1 cli.run_scan: 점검 쪽이 없으면 조각내기·임베딩을 하지 않는다.\n",
     "        # GW1 cli.run_scan: 점검 쪽이 없으면 조각내기·임베딩을 하지 않는다.\n        adapters.embedding.embed_documents([\"x\"])\n",
     PYTEST + [f"{T}/flows/test_colab.py"], ["test_no_pages_skips_the_index_and_calls_nothing"]),
]

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def red_lines(text: str) -> list[str]:
    """pytest 의 FAILED 줄, lint-imports 의 BROKEN 줄(계약 이름이 여러 줄로 꺾이므로 앞의 세 줄과 이어 붙인다)."""
    lines = text.splitlines()
    out = [line for line in lines if line.startswith("FAILED")]
    out += [" ".join(lines[max(0, i - 3) : i + 1]) for i, line in enumerate(lines) if line.endswith("BROKEN")]
    return out


# 0번: 아무것도 안 심고 쓰는 명령 전부
cmds = {tuple(p[5]) for p in PLANTS}
zero_ok = True
for i, cmd in enumerate(sorted(cmds)):
    code, _ = run(list(cmd), LOGS / f"00-{i}.log")
    zero_ok = zero_ok and code == 0
print(f"[0] 아무것도 안 심음: {'전부 초록' if zero_ok else '빨강이 있다'} ({len(cmds)} 명령)")

caught = 0
for num, what, path, old, new, cmd, want in PLANTS:
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
    ok = code != 0 and bool(hit)
    caught += ok
    print(f"[{num}] {what}: {'잡음' if ok else '못 잡음'} (종료 {code}, 빨간 줄 {len(reds)}, 기대한 것 {hit or want})")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
