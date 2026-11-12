#!/usr/bin/env bash
# 밴드 AP1b 의 §4 자기검증(발주서 band-handoffs/AP1b-order.md §4). 줄마다 [n] … EXIT=<n> <초>s, 끝 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-AP1b.sh [--commit n] [--with-containers] [--step 1,2,3]
#   --commit n         경계(1|2, 기본 2). 1 의 허용 목록·8 의 generated·10~11 이 필요한지를 정한다
#   --with-containers  10: 업무 층 그린워싱·core + 보안 층 tests/security/test_ai_settings.py(postgres 하나 — 문을 보고
#                      띄우고 끝에 down -v) + 12 의 업무 갈래(같은 창). 경계 2 에 안 주면 EXIT=1
#
# 단계(§4): 1 바뀐 경로 ⊆ 1-1(그 경계까지) · 2 1-2 경로 diff 0·g2d-baseline 0바이트·보안 파일은 두 줄만 · 3 기존 시험 `-` 줄
#   ↔ 표·지운 def test_/it( 수 · 4 core 셈 몸 = <기준>(ast — ai_versions 는 꼴 주석을 걷고)·core diff 가 e5 조건 ③ 안·
#   terms_sha256 몸 = <기준> · 5 lint-imports · 6 ap1b_baseline --check·g2d_baseline --check · 7 순수 core·greenwash 초록·수 늘기만
#   · 8 generated(① = <기준>, ② = 다시 뽑아 cmp·jq Ai* 차이 = ★D)·openapi 에 AiVersionsCommon 0 · 9 check_test_layout·
#   verify.sh --fast · 10 업무·보안 층(--with-containers) · 11 웹 verify(② — WEB_TEST_PORT=5411) · 12 심은 파손 ·
#   13 추적 diff 에 키 꼴·실재 기업명·.xlsx 류 0.
# <기준> = git merge-base main HEAD. 기준 트리는 git archive 로 AP1b.out/base-<기준>/ 에 푼다. 공급사를 부르지 않는다.
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
OUT="${AP1B_OUT:-$SIDE/AP1b.out}"
NODE_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
FORBIDDEN="$SIDE/G1a.out/forbidden-words.txt"
WEB_TEST_PORT="${WEB_TEST_PORT:-5411}"
api() { (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen "$@"); }
env_value() { sed -n "s/^$1=//p" "$ROOT/.env" | tail -1; }

COMMIT=2
WITH_CONTAINERS=""
STEPS="all"
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:?--commit 뒤에 경계}"; shift 2 ;;
    --with-containers) WITH_CONTAINERS=1; shift ;;
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

BASE="$(git -C "$ROOT" merge-base main HEAD)"
S4="$OUT/section4-$COMMIT"
BT="$OUT/base-$BASE"
mkdir -p "$S4"
FAIL=0
T0=0
start() { T0=$(date +%s); }
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3 $(( $(date +%s) - T0 ))s"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}
echo "COMMIT=$COMMIT BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD)"
if [ ! -d "$BT/apps/api-py" ]; then mkdir -p "$BT" && git -C "$ROOT" archive "$BASE" apps | tar -x -C "$BT"; fi

HELPER="$S4/ap1b_helper.py"
cat > "$HELPER" <<'PY'
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
BASE = sys.argv[2]
COMMIT = int(sys.argv[3])
CMD = sys.argv[4]
ARGS = sys.argv[5:]
A = "apps/api-py/"
G = A + "esgapi/greenwash/"
E = "apps/web/src/entities/ai-setting/"
SEC = A + "tests/security/test_ai_settings.py"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def changed() -> set[str]:
    return set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())


def in_base() -> set[str]:
    return set(git("ls-tree", "-r", "--name-only", BASE).split())


ALLOWED = {
    1: [
        G + r"flows/(prompt_model_e0|binding_e0)\.py",
        G + r"service/(services|selectors|actions)/ai_settings\.py",
        G + r"tests/flows/ap1b_baseline\.py",
        G + r"tests/data/ap1b-baseline/[^/]+",
        G + r"tests/flows/test_binding_e0_versions_ap1b\.py",
        G + r"tests/flows/test_prompt_model_e0(_v3)?\.py",
        A + r"esgapi/core/calc/ai_settings\.py",
        A + r"esgapi/core/contracts/ai_setting_shapes\.py",
        A + r"esgapi/core/tests/calc/test_ai_settings_parts\.py",
        A + r"scripts/(section4|planted-breaks)-AP1b\.sh",
        A + r"scripts/ap1b_baseline\.py",
    ],
    2: [
        G + r"service/apis/ai_settings\.py",
        G + r"README\.md",
        G + r"tests/service/apis/(test_ai_settings_prompt_model|test_ai_settings_model|test_ai_settings_prompts)\.py",
        SEC.replace(".", r"\."),
        A + r"generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)",
        E + r"model/slot\.ts",
        E + r"api/server(\.test)?\.ts",
    ],
}
ZERO = [
    *(A + f"esgapi/{m}" for m in ("config", "runs", "translation", "dataverify", "inventory", "accounts", "user",
                                  "organization")),
    A + ".importlinter", A + "conftest.py", A + "tests", A + "tests_integration", G + "tests/data/g2d-baseline",
    G + "models.py", G + "migrations", G + "contracts", A + "esgapi/core", "apps/web", "README.md", "docs",
]
ZERO_EXCEPT = [
    SEC, A + "esgapi/core/calc/ai_settings.py", A + "esgapi/core/contracts/ai_setting_shapes.py",
    A + "esgapi/core/tests/calc/test_ai_settings_parts.py", E + "model/slot.ts", E + "api/server.ts", E + "api/server.test.ts",
]
# 기존 시험의 `-` 원문(§3-2·3-3 표 — 경계 ② 의 「바뀐 단언 줄」). 이 밖의 `-` 는 0. ① 은 비었다(Q3 가 — 기존 시험 0줄).
# 줄 = <경로>\t<원문>(GT/ = 그린워싱 시험, AT/ = apps/api-py/tests, E/ = 웹 entities/ai-setting).
MINUS_2 = """
GT/flows/test_prompt_model_e0.py	    PROMPT_MODEL_SHAPE,
GT/flows/test_prompt_model_e0.py	    SHAPES,
GT/flows/test_prompt_model_e0.py	    AiPromptModel,
GT/flows/test_prompt_model_e0.py	def build(criteria: GreenwashCriteria | None = None, name: str = criteria_e0.DEFAULT_VERSION) -> AiPromptModel:
GT/flows/test_prompt_model_e0.py	def prompts_of(found: AiPromptModel) -> dict[str, Any]:
GT/flows/test_prompt_model_e0.py	    return {entry["key"]: entry for entry in found["steps"][0]["prompts"]}
GT/flows/test_prompt_model_e0.py	    SHAPES[PROMPT_MODEL_SHAPE].validate_python(found, strict=True)
GT/flows/test_prompt_model_e0.py	    assert found["schemaVersion"] == "ai.prompt-model@2"
GT/flows/test_prompt_model_e0.py	    assert [step["key"] for step in found["steps"]] == ["judge"]
GT/flows/test_prompt_model_e0.py	    assert found["steps"][0]["label"] == "판정"
GT/flows/test_prompt_model_e0.py	    entries = found["steps"][0]["prompts"]
GT/flows/test_prompt_model_e0.py	    step = found["steps"][0]
GT/flows/test_prompt_model_e0.py	    SHAPES[PROMPT_MODEL_SHAPE].validate_python(found, strict=True)
GT/flows/test_prompt_model_e0.py	    SHAPES[PROMPT_MODEL_SHAPE].validate_python(found, strict=True)
GT/flows/test_prompt_model_e0_v3.py	    3-4-1  시험 안의 선언 AiModuleSpec("greenwash", STEPS, 묶음 judge 하나)이 check_module 을 지나고 layout_of 가 LAYOUT
GT/flows/test_prompt_model_e0_v3.py	    3-4-2  기본 판·저장 판(모델 바꿈·글 바꿈)의 compose(@3) 가 prompt_model(@2)과 뜻이 같다(schemaVersion 만 바뀌고 칸은
GT/flows/test_prompt_model_e0_v3.py	compose 에 넘기는 칸 글은 @2 가 지은 칸 그대로다(칸 짓기는 모듈 몫 — 그린워싱 쪽 전환은 AP1b). 설정은 패키지의 실제
GT/flows/test_prompt_model_e0_v3.py	    AiModuleSpec,
GT/flows/test_prompt_model_e0_v3.py	    AiPromptGroupSpec,
GT/flows/test_prompt_model_e0_v3.py	    compose,
GT/flows/test_prompt_model_e0_v3.py	from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3, AiModelSettingsIn, AiPromptModel
GT/flows/test_prompt_model_e0_v3.py	SPEC = AiModuleSpec(
GT/flows/test_prompt_model_e0_v3.py	    module=pm.MODULE,
GT/flows/test_prompt_model_e0_v3.py	    models=pm.STEPS,
GT/flows/test_prompt_model_e0_v3.py	    groups=tuple(AiPromptGroupSpec(key, pm.JUDGE.label, tuple(keys), (pm.JUDGE.key,)) for key, keys in pm.LAYOUT),
GT/flows/test_prompt_model_e0_v3.py	)
GT/flows/test_prompt_model_e0_v3.py	    "default": (None, None, "colab-default"),
GT/flows/test_prompt_model_e0_v3.py	    "saved-model": (CHANGED_MODEL, None, "v2"),
GT/flows/test_prompt_model_e0_v3.py	    "saved-text": (CHANGED_MODEL, "saved", "v3"),
GT/flows/test_prompt_model_e0_v3.py	def pair(case: str) -> tuple[AiPromptModel, Any]:
GT/flows/test_prompt_model_e0_v3.py	    given, texts, name = CASES[case]
GT/flows/test_prompt_model_e0_v3.py	    old = pm.prompt_model(
GT/flows/test_prompt_model_e0_v3.py	    new = compose(
GT/flows/test_prompt_model_e0_v3.py	        CONFIG,
GT/flows/test_prompt_model_e0_v3.py	        SPEC,
GT/flows/test_prompt_model_e0_v3.py	        setting_name=name,
GT/flows/test_prompt_model_e0_v3.py	        editable=old["editable"],
GT/flows/test_prompt_model_e0_v3.py	        model=model,
GT/flows/test_prompt_model_e0_v3.py	        prompts={step["key"]: step["prompts"] for step in old["steps"]},
GT/flows/test_prompt_model_e0_v3.py	        fixed=pm.fixed_groups(),
GT/flows/test_prompt_model_e0_v3.py	    )
GT/service/apis/test_ai_settings_model.py	from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_SHAPE, SHAPES
GT/service/apis/test_ai_settings_model.py	    SHAPES[PROMPT_MODEL_SHAPE].validate_python(body, strict=True)
GT/service/apis/test_ai_settings_model.py	    model = body["steps"][0]["model"]
GT/service/apis/test_ai_settings_prompt_model.py	from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_SHAPE, SHAPES
GT/service/apis/test_ai_settings_prompt_model.py	from esgapi.core.llm.config import default_config_sources, load_config
GT/service/apis/test_ai_settings_prompt_model.py	    entries = {entry["key"]: entry for entry in body["steps"][0]["prompts"]}
GT/service/apis/test_ai_settings_prompt_model.py	    SHAPES[PROMPT_MODEL_SHAPE].validate_python(default.json(), strict=True)
GT/service/apis/test_ai_settings_prompt_model.py	    SHAPES[PROMPT_MODEL_SHAPE].validate_python(body, strict=True)
GT/service/apis/test_ai_settings_prompts.py	prompts, GET …/{id}/prompt-model 의 저장 글, PUT …/applied 의 프롬프트 다시 받기, 판 꼴 @2). 업무 층: 진짜 DB(주인
GT/service/apis/test_ai_settings_prompts.py	    return {entry["key"]: entry for entry in response.json()["steps"][0]["prompts"]}
AT/security/test_ai_settings.py	        assert {"steps", "settingName"} & set(response.json()) == set(), name
AT/security/test_ai_settings.py	    assert marker in of_b["one"].json()["steps"][0]["prompts"][1]["text"]
E/api/server.test.ts	import { createPromptModelReader, isPromptModel } from './server.ts';
"""
SHORT = {"GT/": G + "tests/", "AT/": A + "tests/", "E/": E}
MINUS_OK: dict[str, set[str]] = {}
if COMMIT >= 2:
    for row in MINUS_2.strip("\n").splitlines():
        short, _, text = row.partition("\t")
        head = next(k for k in SHORT if short.startswith(k))
        MINUS_OK.setdefault(SHORT[head] + short[len(head):], set()).add(text)


def is_test(path: str) -> bool:
    return "/tests/" in path or path.endswith(".test.ts") or path.startswith(A + "tests/")


def minus_lines(path: str) -> list[str]:
    diff = git("diff", "-U0", BASE, "--", path)
    return [line[1:] for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]


def plus_lines(path: str) -> list[str]:
    diff = git("diff", "-U0", BASE, "--", path)
    return [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]


class _StripAnnotations(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.returns = None
        for arg in [*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs]:
            arg.annotation = None
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
        if node.value is None:  # 클래스 칸 — 걷지 않는다
            return node
        return ast.Assign(targets=[node.target], value=node.value, lineno=0)


def top_nodes(source: str, strip: bool = False) -> dict[str, str]:
    found: dict[str, str] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef | ast.ClassDef):
            if strip:
                node = _StripAnnotations().visit(node)
            found[node.name] = ast.dump(node, include_attributes=False)
    return found


if CMD == "paths":
    patterns = [p for c in range(1, COMMIT + 1) for p in ALLOWED[c]]
    files = sorted(changed())
    outside = [f for f in files if not any(re.fullmatch(p, f) for p in patterns)]
    print(f"changed={len(files)} outside={len(outside)}", *outside, sep="\n  ")
    sys.exit(1 if outside else 0)
if CMD == "zero":
    files = changed()
    bad = sorted(f for f in files for z in ZERO if (f == z or f.startswith(z + "/")) and f not in ZERO_EXCEPT)
    sec_minus, sec_plus = (len(minus_lines(SEC)), len(plus_lines(SEC))) if SEC in files else (0, 0)
    sec_ok = (sec_minus, sec_plus) in ((0, 0), (2, 2)) and (COMMIT >= 2 or SEC not in files)
    print(f"zero_paths_touched={len(bad)} security_minus={sec_minus} security_plus={sec_plus}", *bad, sep="\n  ")
    sys.exit(0 if not bad and sec_ok else 1)
if CMD == "minus":
    bad = []
    deleted = 0
    base_files = in_base()
    for f in sorted(changed()):
        if f not in base_files or not is_test(f):
            continue
        for line in minus_lines(f):
            if re.match(r"\s*(def test_|it\()", line):
                deleted += 1
            if line not in MINUS_OK.get(f, set()):
                bad.append(f"{f}: {line[:110]}")
    plus_tests = sum(
        bool(re.match(r"\s*(def test_|it\()", line)) for f in changed() if is_test(f) for line in
        (plus_lines(f) if f in base_files else (ROOT / f).read_text(encoding="utf-8").splitlines())
    )
    print(f"bad_minus={len(bad)} deleted_tests={deleted} added_tests={plus_tests}")
    for b in bad:
        print("  " + b)
    sys.exit(0 if not bad and deleted == 0 else 1)
if CMD == "core":
    calc = A + "esgapi/core/calc/ai_settings.py"
    shapes = A + "esgapi/core/contracts/ai_setting_shapes.py"
    old = top_nodes(git("show", f"{BASE}:{calc}"))
    new = top_nodes((ROOT / calc).read_text(encoding="utf-8"))
    body_changed = sorted(n for n in old if n != "ai_versions" and new.get(n) != old[n])
    named = {n: new.get(n) == old[n] for n in ("model_settings_sha256", "prompts_sha256", "compose")}
    ai_same = (top_nodes(git("show", f"{BASE}:{calc}"), strip=True)["ai_versions"]
               == top_nodes((ROOT / calc).read_text(encoding="utf-8"), strip=True)["ai_versions"])
    old_s = top_nodes(git("show", f"{BASE}:{shapes}"))
    new_s = top_nodes((ROOT / shapes).read_text(encoding="utf-8"))
    shapes_changed = sorted(n for n in old_s if new_s.get(n) != old_s[n])
    new_names = sorted((set(new) - set(old)) | (set(new_s) - set(old_s)))
    core_files = sorted(f for f in changed() if f.startswith(A + "esgapi/core/"))
    allowed_core = {calc, shapes, A + "esgapi/core/tests/calc/test_ai_settings_parts.py"}
    core_minus = {f: minus_lines(f) for f in core_files if f in in_base() and not is_test(f)}
    minus_ok = {
        calc: {") -> dict[str, object]:",
               '    versions: dict[str, object] = {"aiSettingId": setting_id, "modelSettingsSha256": model_settings_sha256(model)}'},
        shapes: {"from typing import Annotated, Any, Final, Literal, TypedDict",
                 "    판            (꼴 없음 — 모듈마다)  next_version_name · version_status · ai_versions · 상수 VERSION_* 넷(이 파일)"},
    }
    core_bad = [f"{f}: {l[:100]}" for f, ls in core_minus.items() for l in ls if l not in minus_ok.get(f, set())]
    parts = A + "esgapi/core/tests/calc/test_ai_settings_parts.py"
    parts_plus = len(plus_lines(parts)) if parts in core_files else 0
    terms = G + "flows/terms_e0.py"
    terms_same = (top_nodes(git("show", f"{BASE}:{terms}"))["terms_sha256"]
                  == top_nodes((ROOT / terms).read_text(encoding="utf-8"))["terms_sha256"])
    print(f"calc_bodies_changed={body_changed} named_same={named} ai_versions_ast_without_annotations_same={ai_same}")
    print(f"shapes_classes_changed={shapes_changed} new_names={new_names} core_files={len(core_files)} "
          f"core_minus_outside={len(core_bad)} parts_plus={parts_plus} terms_sha256_same={terms_same}")
    for b in core_bad:
        print("  " + b)
    ok = (not body_changed and all(named.values()) and ai_same and not shapes_changed
          and new_names in ([], ["AiVersionsCommon"]) and set(core_files) <= allowed_core and not core_bad
          and parts_plus <= 2 and terms_same)
    sys.exit(0 if ok else 1)
if CMD == "secrets":
    words = [w.strip() for w in Path(ARGS[0]).read_text(encoding="utf-8").splitlines() if w.strip()] if ARGS else []
    added: list[str] = []
    for f in sorted(changed()):
        if re.search(r"\.(xlsx|csv|ipynb)$", f):
            added.append(f"\x00file {f}")
        p = ROOT / f
        if not p.is_file():
            continue
        if f in in_base():
            added += plus_lines(f)
        else:
            added += p.read_text(encoding="utf-8").splitlines()
    keys = sum(bool(re.search(r"sk-[A-Za-z0-9_-]{20,}|sk-an[t]-|AKIA[0-9A-Z]{16}", l)) for l in added)
    names = sum(any(w in l for w in words) for l in added)
    files = sum(l.startswith("\x00file") for l in added)
    print(f"key_like={keys} forbidden_word_lines={names} words={len(words)} data_files={files} added_lines={len(added)}")
    sys.exit(0 if keys == 0 and names == 0 and files == 0 and words else 1)
sys.exit(f"모르는 CMD {CMD}")
PY
helper() { (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python "$HELPER" "$ROOT" "$BASE" "$COMMIT" "$@"); }

if want 1; then start; helper paths > "$S4/1.log" 2>&1; e=$?; head -4 "$S4/1.log"; report 1 "바뀐 경로 ⊆ 1-1" $e; fi
if want 2; then start; helper zero > "$S4/2.log" 2>&1; e=$?; head -4 "$S4/2.log"; report 2 "1-2 경로 0·g2d-baseline 0·보안 두 줄" $e; fi
if want 3; then start; helper minus > "$S4/3.log" 2>&1; e=$?; cat "$S4/3.log"; report 3 "기존 시험 - ↔ 표·지운 시험 0" $e; fi
if want 4; then start; helper core > "$S4/4.log" 2>&1; e=$?; cat "$S4/4.log"; report 4 "core 셈 몸 = 기준(ast)·e5 조건 ③" $e; fi

if want 5; then
  start
  api lint-imports > "$S4/5.log" 2>&1; e=$?
  total="$(grep -E '^Contracts:' "$S4/5.log")"
  base_n="$(git -C "$ROOT" show "$BASE:apps/api-py/.importlinter" | grep -c '^\[importlinter:contract:')"
  echo "    $total base_contracts=$base_n"
  case "$total" in "Contracts: $base_n kept, 0 broken.") ;; *) e=1 ;; esac
  report 5 "lint-imports 전부 KEPT·수 = 기준" $e
fi

if want 6; then
  start
  api python scripts/ap1b_baseline.py --check > "$S4/6.log" 2>&1; e=$?
  api python scripts/g2d_baseline.py --check >> "$S4/6.log" 2>&1 || e=1
  grep -E '^(AP1B|G2D)_BASELINE|기준물과 다름' "$S4/6.log"
  report 6 "ap1b_baseline·g2d_baseline --check" $e
fi

if want 7; then
  start
  if [ ! -f "$BT/collect.txt" ]; then
    (cd "$BT/apps/api-py" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONDONTWRITEBYTECODE=1 \
      "$API_PY/.venv/bin/python" -I -c "import sys; sys.path.insert(0, '.'); import pytest; sys.exit(pytest.main(['-q', '--co', '-p', 'no:cacheprovider', '-m', 'not django_db', 'esgapi/core', 'esgapi/greenwash']))" \
      > "$BT/collect-raw.txt" 2>&1)
    grep -c '::' "$BT/collect-raw.txt" > "$BT/collect.txt"
  fi
  base_n="$(tail -1 "$BT/collect.txt")"
  api pytest -q -p no:cacheprovider -m "not django_db" esgapi/core esgapi/greenwash > "$S4/7.log" 2>&1; e=$?
  passed="$(tail -1 "$S4/7.log")"
  now_n="$(echo "$passed" | sed -nE 's/^([0-9]+) passed.*/\1/p')"
  echo "    base=$base_n now=$passed"
  [ -n "$now_n" ] && [ "$now_n" -gt "$base_n" ] || e=1
  report 7 "순수 core·greenwash 초록·수 기준 → 뒤" $e
fi

if want 8; then
  start
  e=0
  GEN="$API_PY/generated"
  BGEN="$BT/apps/api-py/generated"
  if [ "$COMMIT" -ge 2 ]; then
    R="$S4/regen"; mkdir -p "$R"
    (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
      uv run --frozen python manage.py export_openapi > "$R/openapi.json" 2> "$S4/8.log") || e=1
    (cd "$R" && PATH="$NODE_DIR:$PATH" pnpm dlx openapi-typescript@7.13.0 openapi.json -o api.d.ts >> "$S4/8.log" 2>&1) || e=1
    cmp "$R/openapi.json" "$GEN/openapi.json" >> "$S4/8.log" 2>&1 || e=1
    cmp "$R/api.d.ts" "$GEN/api.d.ts" >> "$S4/8.log" 2>&1 || e=1
    [ "$(shasum -a 256 "$GEN/openapi.json" | cut -d' ' -f1)" = "$(cat "$GEN/api.d.ts.source-sha256")" ] || e=1
    echo "    다시 뽑음 cmp(openapi·api.d.ts·source-sha256): $([ $e = 0 ] && echo same || echo DIFF)"
    jq -n --slurpfile b "$BGEN/openapi.json" --slurpfile n "$GEN/openapi.json" '
      ($b[0].components.schemas) as $bs | ($n[0].components.schemas) as $ns |
      {removed: [$bs | keys[] | select(. as $k | $ns | has($k) | not)],
       added: [$ns | keys[] | select(. as $k | $bs | has($k) | not)],
       changed: [$bs | keys[] | select(. as $k | ($ns | has($k)) and $ns[$k] != $bs[$k])],
       paths_same_after_ref_rename: (($b[0].paths | tojson | gsub("#/components/schemas/AiPromptModel\""; "#/components/schemas/AiPromptModel3\""))
                                     == ($n[0].paths | tojson)),
       other_top_same: (($b[0] | del(.paths, .components)) == ($n[0] | del(.paths, .components)))}' > "$S4/8-jq.json" || e=1
    cat "$S4/8-jq.json" | jq -c .
    jq -e '.removed == ["AiPromptModel","AiPromptStep"] and (.added | sort) == ["AiModelSlot","AiPromptGroup","AiPromptModel3"]
           and .changed == [] and .paths_same_after_ref_rename and .other_top_same' "$S4/8-jq.json" > /dev/null || e=1
  else
    [ -z "$(git -C "$ROOT" diff --name-only "$BASE" -- apps/api-py/generated)" ] || e=1
    echo "    ① generated = 기준: $([ $e = 0 ] && echo same || echo DIFF)"
  fi
  n="$(grep -c AiVersionsCommon "$GEN/openapi.json" "$GEN/api.d.ts" | awk -F: '{s += $2} END {print s}')"
  echo "    AiVersionsCommon in generated = $n"
  [ "$n" = "0" ] || e=1
  report 8 "generated·AiVersionsCommon 0" $e
fi

if want 9; then
  start
  api python scripts/check_test_layout.py > "$S4/9.log" 2>&1; e=$?; tail -1 "$S4/9.log"
  while [ -e "$(git -C "$ROOT" rev-parse --git-common-dir)/verify.lock" ]; do echo "    verify.lock 있음 — 기다림"; sleep 20; done
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast > "$S4/9-fast.log" 2>&1) || e=1
  tail -1 "$S4/9-fast.log"; grep -q '^VERIFY_FAST=PASS' "$S4/9-fast.log" || e=1
  report 9 "check_test_layout·verify.sh --fast" $e
fi

gate() {  # 기계 문(MARC-ENT-241): 자기 밖 esg-app* 벌 둘까지·build 0·free ≥ 20%·1분 부하 < 24
  local tries=0 free load others building me
  me="$(env_value COMPOSE_PROJECT_NAME)"
  while :; do
    others="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep '^esg-app' | grep -v -x -F "$me" | sort -u | wc -l | tr -d ' ')"
    building="$(ps -axo command | grep -E "^[^ ]*/?(docker|docker-compose)( .*)? (build|buildx)( |$)" | grep -v -c grep)"
    free="$(memory_pressure 2> /dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(sysctl -n vm.loadavg | awk '{print $2}')"
    if [ "$others" -le 2 ] && [ "$building" = 0 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 24 ]; then
      echo "    (문: 자기 밖 esg-app* $others · build 중 $building · free ${free:-?}% · 1분 부하 ${load:-?} · 기다림 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "    (문이 안 열림: 자기 밖 $others · build 중 $building · free ${free:-?}% · 부하 ${load:-?})"; return 1; }
    tries=$((tries + 1))
    sleep 60
  done
}

UP=""
if want 10; then
  start
  if [ -n "$WITH_CONTAINERS" ]; then
    e=0
    while [ -e "$(git -C "$ROOT" rev-parse --git-common-dir)/verify.lock" ]; do echo "    verify.lock 있음 — 기다림"; sleep 20; done
    gate || e=1
    if [ "$e" = 0 ]; then
      (cd "$ROOT" && docker compose up -d --wait postgres > "$S4/10-up.log" 2>&1) || { tail -3 "$S4/10-up.log"; e=1; }
      UP=1
    fi
    if [ "$e" = 0 ]; then
      (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -q -p no:cacheprovider esgapi/greenwash esgapi/core > "$S4/10.log" 2>&1) || e=1
      echo "    업무 $(tail -1 "$S4/10.log")"
      (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -q -p no:cacheprovider tests/security/test_ai_settings.py > "$S4/10-security.log" 2>&1) || e=1
      echo "    보안 $(tail -1 "$S4/10-security.log")"
    fi
  elif [ "$COMMIT" -ge 2 ]; then echo "    안 돌림(--with-containers 없음)"; e=1
  else echo "    경계 1 — 안 돌림(§4-10 은 ② 만)"; e=0; fi
  report 10 "업무 층 그린워싱·core + 보안 test_ai_settings" $e
fi

if want 11; then
  start
  if [ "$COMMIT" -ge 2 ]; then
    e=0
    if lsof -nP -iTCP:"$WEB_TEST_PORT" -sTCP:LISTEN > /dev/null 2>&1; then echo "    포트 $WEB_TEST_PORT 이 이미 쓰임"; e=1; fi
    if [ "$e" = 0 ]; then
      (cd "$ROOT" && PATH="$NODE_DIR:$PATH" WEB_PORT="$(env_value WEB_PORT)" WEB_TEST_PORT="$WEB_TEST_PORT" \
        apps/web/scripts/verify.sh > "$S4/11.log" 2>&1) || e=1
      tail -1 "$S4/11.log"; grep -q '^VERIFY=PASS' "$S4/11.log" || e=1
      grep -E '(Tests|passed|failed)' "$S4/11.log" | grep -vi "warn" | tail -4 | sed 's/^/    /'
    fi
  else echo "    경계 1 — 안 돌림(웹은 ②)"; e=0; fi
  report 11 "웹 verify(WEB_TEST_PORT=$WEB_TEST_PORT)" $e
fi

if want 12; then
  start
  AP1B_OUT="$OUT" "$API_PY/scripts/planted-breaks-AP1b.sh" --commit "$COMMIT" ${UP:+--with-containers} > "$S4/12.log" 2>&1; e=$?
  grep -E '^(P[0-9]+ |P0=|FINGERPRINT=|PLANTED=)' "$S4/12.log"
  report 12 "심은 파손" $e
fi

if [ -n "$UP" ]; then (cd "$ROOT" && docker compose down -v > "$S4/down.log" 2>&1); echo "    compose $(env_value COMPOSE_PROJECT_NAME) down -v EXIT=$?"; fi

if want 13; then
  start; helper secrets "$FORBIDDEN" > "$S4/13.log" 2>&1; e=$?; cat "$S4/13.log"
  report 13 "키 꼴·실재 기업명·자료 파일 0" $e
fi

echo "SECTION4_FAIL=$FAIL"
exit $(( FAIL > 0 ? 1 : 0 ))
