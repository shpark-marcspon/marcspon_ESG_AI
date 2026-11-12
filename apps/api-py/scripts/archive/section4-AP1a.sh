#!/usr/bin/env bash
# 밴드 AP1a 의 §4 자기검증(발주서 band-handoffs/AP1a-order.md §4). 줄마다 [n] … EXIT=<n> <초>s, 끝 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-AP1a.sh [--commit n] [--with-containers] [--preview] [--step 1,2,3]
#   --commit n         경계(1|2, 기본 2). 9 의 심은 파손 몫과 10·11 이 필요한지를 정한다
#   --with-containers  10: 업무 층 그린워싱·core 시험(scripts/test-business.sh — Postgres 컨테이너). 경계 2 에 안 주면 EXIT=1
#   --preview          11: 웹 미리 보기(시험 설정으로 지은 NinjaAPI 의 GET /preview → AiPromptModel3)를 밖 출력
#                      AP1a.out/preview/{openapi.json,api.d.ts,README} 에 짓는다(커밋 0). 경계 2 에 안 주면 EXIT=1
#
# 단계(§4): 1 바뀐 경로 ⊆ 허용(§1-2·§1-3) · 2 0줄 경로(§1-4)·G/** 는 새 파일 하나 · 3 기존 고침 표 밖 `-` 0·core 셈의 기존
#   함수·클래스 몸 = <기준>(ast, 이름별 — AiStepSpec 은 AiModelSlotSpec 으로 견줌)·contracts 기존 클래스 = <기준> ·
#   4 lint-imports 전부 KEPT·계약 수 = <기준> · 5 순수 시험 core·greenwash 초록·수 <기준> → 뒤(늘기만) · 6 고정 스키마 다시
#   뽑아 cmp(@3 새, 옛 셋 = <기준>)·generated 다시 뽑아 cmp = <기준> · 7 check_test_layout · 8 verify.sh --fast ·
#   9 심은 파손 · 10 업무 층(--with-containers) · 11 미리 보기(--preview) · 12 추적 diff 에 키 꼴·실재 기업명·.xlsx 류 0.
# <기준> = git merge-base main HEAD. 기준 트리는 git archive 로 AP1a.out/base-<기준>/ 에 푼다(5 의 수를 셈). 공급사를 부르지
# 않는다. 컨테이너는 10 에서만(scripts/test-business.sh 가 띄운다 — 끝에 docker compose down -v 는 부르는 쪽 몫).
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
OUT="${AP1a_OUT:-$SIDE/AP1a.out}"
NODE_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
FORBIDDEN="$SIDE/G1a.out/forbidden-words.txt"
api() { (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen "$@"); }

COMMIT=2
WITH_CONTAINERS=""
PREVIEW=""
STEPS="all"
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:?--commit 뒤에 경계}"; shift 2 ;;
    --with-containers) WITH_CONTAINERS=1; shift ;;
    --preview) PREVIEW=1; shift ;;
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

BASE="$(git -C "$ROOT" merge-base main HEAD)"
S4="$OUT/section4-$COMMIT"
mkdir -p "$S4"
FAIL=0
T0=0
start() { T0=$(date +%s); }
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3 $(( $(date +%s) - T0 ))s"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}
echo "COMMIT=$COMMIT BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD)"

HELPER="$S4/ap1a_helper.py"
cat > "$HELPER" <<'PY'
import ast
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
BASE = sys.argv[2]
CMD = sys.argv[3]
ARGS = sys.argv[4:]
A = "apps/api-py/"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def changed() -> set[str]:
    return set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())


ALLOWED = [
    r"apps/api-py/esgapi/core/contracts/ai_setting_shapes\.py",
    r"apps/api-py/esgapi/core/calc/ai_settings\.py",
    r"apps/api-py/esgapi/core/calc/__init__\.py",
    r"apps/api-py/esgapi/core/__init__\.py",
    r"apps/api-py/esgapi/core/tests/contracts/test_ai_setting_shapes\.py",
    r"apps/api-py/esgapi/core/tests/contracts/test_ai_setting_shapes_v3\.py",
    r"apps/api-py/esgapi/core/tests/calc/test_ai_settings_parts\.py",
    r"apps/api-py/esgapi/core/tests/calc/test_ai_settings_fake_module\.py",
    r"apps/api-py/esgapi/core/tests/data/ai-setting/ai\.prompt-model@3\.schema\.json",
    r"apps/api-py/esgapi/core/tests/data/ai-setting-examples/prompt-model3-(default|saved|fake-module)\.json",
    r"apps/api-py/scripts/(section4|planted-breaks)-AP1a\.sh",
    r"apps/api-py/esgapi/greenwash/tests/flows/test_prompt_model_e0_v3\.py",
]
ZERO = [
    "apps/api-py/esgapi/translation", "apps/api-py/esgapi/dataverify", "apps/api-py/esgapi/runs",
    "apps/api-py/esgapi/config", "apps/api-py/generated", "apps/api-py/.importlinter", "apps/api-py/conftest.py",
    "apps/api-py/tests_integration", "apps/api-py/tests/support", "apps/api-py/tests/security",
    "apps/api-py/scripts/planted-breaks.sh", "apps/web", "README.md", "docs",
]
# 기존 고침 표(§1-2)의 `-` 원문: 이 밖의 `-` 는 0.
MINUS_OK = {
    "apps/api-py/esgapi/core/tests/contracts/test_ai_setting_shapes.py": {
        "def test_the_examples_are_the_four() -> None:",
        '    assert sorted(ai_setting_shapes.SHAPES) == ["ai.model-settings@1", "ai.prompt-model@2", "ai.prompts@1"]',
    },
    "apps/api-py/esgapi/core/calc/ai_settings.py": {"from collections.abc import Sequence", "class AiStepSpec:"},
    "apps/api-py/esgapi/core/calc/__init__.py": {
        "ai_settings.py  모듈 공통 AI 설정의 받기·경로 능력·모델 설정 sha(꼴은 contracts/ai_setting_shapes.py)",
    },
    "apps/api-py/esgapi/core/__init__.py": {
        "    contracts/     모듈 공통 AI 설정 꼴(ai_setting_shapes.py — 프롬프트·모델 설정). 받기 규칙은 calc/ai_settings.py",
    },
}


def minus_lines(path: str) -> list[str]:
    diff = git("diff", "-U0", BASE, "--", path)
    return [line[1:] for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]


def top_nodes(source: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef | ast.ClassDef):
            found[node.name] = ast.dump(node, include_attributes=False).replace(f"name='{node.name}'", "name='_'", 1)
    return found


if CMD == "paths":
    files = sorted(changed())
    outside = [f for f in files if not any(re.fullmatch(p, f) for p in ALLOWED)]
    print(f"changed={len(files)} outside={len(outside)}", *outside, sep="\n  ")
    sys.exit(1 if outside else 0)
if CMD == "zero":
    files = changed()
    bad = sorted(f for f in files for z in ZERO if f == z or f.startswith(z + "/"))
    green = sorted(f for f in files if f.startswith(A + "esgapi/greenwash/"))
    ok_green = green in ([], [A + "esgapi/greenwash/tests/flows/test_prompt_model_e0_v3.py"])
    new_green = all(f not in git("ls-tree", "-r", "--name-only", BASE).split() for f in green)
    print(f"zero_paths_touched={len(bad)} greenwash={green}", *bad, sep="\n  ")
    sys.exit(0 if not bad and ok_green and new_green else 1)
if CMD == "minus":
    bad = []
    for f in sorted(changed()):
        for line in minus_lines(f) if f in git("ls-tree", "-r", "--name-only", BASE).split() else []:
            if line not in MINUS_OK.get(f, set()):
                bad.append(f"{f}: {line[:100]}")
    calc = A + "esgapi/core/calc/ai_settings.py"
    old = top_nodes(git("show", f"{BASE}:{calc}"))
    new = top_nodes((ROOT / calc).read_text(encoding="utf-8"))
    old["AiModelSlotSpec"] = old.pop("AiStepSpec")
    body_changed = sorted(n for n in old if new.get(n) != old[n])
    alias = "AiStepSpec = AiModelSlotSpec" in (ROOT / calc).read_text(encoding="utf-8")
    shapes = A + "esgapi/core/contracts/ai_setting_shapes.py"
    old_s = top_nodes(git("show", f"{BASE}:{shapes}"))
    new_s = top_nodes((ROOT / shapes).read_text(encoding="utf-8"))
    shapes_changed = sorted(n for n in old_s if new_s.get(n) != old_s[n])
    print(f"bad_minus={len(bad)} calc_bodies_changed={body_changed} alias={alias} shapes_classes_changed={shapes_changed}")
    print(f"calc_names_base={len(old)} calc_new_names={sorted(set(new) - set(old))}")
    for b in bad:
        print("  " + b)
    sys.exit(0 if not bad and not body_changed and alias and not shapes_changed else 1)
if CMD == "pinned":
    sys.path.insert(0, str(ROOT / "apps/api-py"))
    import json

    from esgapi.core.contracts import ai_setting_shapes as s

    pinned = ROOT / A / "esgapi/core/tests/data/ai-setting"
    bad = []
    for shape, adapter in s.SHAPES.items():
        text = json.dumps(adapter.json_schema(), ensure_ascii=False, indent=2) + "\n"
        path = pinned / f"{shape}.schema.json"
        if path.read_bytes() != text.encode("utf-8"):
            bad.append(f"{shape}: 다시 뽑은 것 ≠ 고정 파일")
        rel = f"{A}esgapi/core/tests/data/ai-setting/{shape}.schema.json"
        in_base = rel in git("ls-tree", "-r", "--name-only", BASE).split()
        if in_base and git("show", f"{BASE}:{rel}").encode("utf-8") != path.read_bytes():
            bad.append(f"{shape}: 고정 파일 ≠ <기준>")
        print(f"{shape} {'옛(= 기준)' if in_base else '새'} sha256={hashlib.sha256(path.read_bytes()).hexdigest()[:12]}")
    print(f"pinned_bad={len(bad)}", *bad, sep="\n  ")
    sys.exit(1 if bad else 0)
if CMD == "secrets":
    words = [w.strip() for w in Path(ARGS[0]).read_text(encoding="utf-8").splitlines() if w.strip()] if ARGS else []
    added: list[str] = []
    for f in sorted(changed()):
        if re.search(r"\.(xlsx|csv|ipynb)$", f):
            added.append(f"\x00file {f}")
        p = ROOT / f
        if not p.is_file():
            continue
        if f in git("ls-tree", "-r", "--name-only", BASE).split():
            added += [l[1:] for l in git("diff", "-U0", BASE, "--", f).splitlines() if l.startswith("+") and not l.startswith("+++")]
        else:
            added += p.read_text(encoding="utf-8").splitlines()
    keys = sum(bool(re.search(r"sk-[A-Za-z0-9_-]{20,}|sk-an[t]-|AKIA[0-9A-Z]{16}", l)) for l in added)
    names = sum(any(w in l for w in words) for l in added)
    files = sum(l.startswith("\x00file") for l in added)
    print(f"key_like={keys} forbidden_word_lines={names} words={len(words)} data_files={files} added_lines={len(added)}")
    sys.exit(0 if keys == 0 and names == 0 and files == 0 and words else 1)
sys.exit(f"모르는 CMD {CMD}")
PY
helper() { (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python "$HELPER" "$ROOT" "$BASE" "$@"); }

if want 1; then start; helper paths > "$S4/1.log" 2>&1; e=$?; head -3 "$S4/1.log"; report 1 "바뀐 경로 ⊆ 허용" $e; fi
if want 2; then start; helper zero > "$S4/2.log" 2>&1; e=$?; head -3 "$S4/2.log"; report 2 "0줄 경로·G/** 새 파일 하나" $e; fi
if want 3; then start; helper minus > "$S4/3.log" 2>&1; e=$?; cat "$S4/3.log"; report 3 "표 밖 - 0·기존 몸 = 기준(ast)" $e; fi

if want 4; then
  start
  api lint-imports > "$S4/4.log" 2>&1; e=$?
  kept="$(grep -c ' KEPT$' "$S4/4.log")"; total="$(grep -E '^Contracts:' "$S4/4.log")"
  base_n="$(git -C "$ROOT" show "$BASE:apps/api-py/.importlinter" | grep -c '^\[importlinter:contract:')"
  echo "    $total base_contracts=$base_n"
  case "$total" in "Contracts: $base_n kept, 0 broken.") ;; *) e=1 ;; esac
  report 4 "lint-imports 전부 KEPT·수 = 기준" $e
fi

if want 5; then
  start
  BT="$OUT/base-$BASE"
  if [ ! -f "$BT/collect.txt" ]; then
    mkdir -p "$BT" && git -C "$ROOT" archive "$BASE" apps/api-py | tar -x -C "$BT"
    (cd "$BT/apps/api-py" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONDONTWRITEBYTECODE=1 \
      "$API_PY/.venv/bin/python" -I -c "import sys; sys.path.insert(0, '.'); import pytest; sys.exit(pytest.main(['-q', '--co', '-p', 'no:cacheprovider', '-m', 'not django_db', 'esgapi/core', 'esgapi/greenwash']))" \
      > "$BT/collect-raw.txt" 2>&1)
    grep -E '^[0-9]+(/[0-9]+)? tests? (collected|selected)' "$BT/collect-raw.txt" | tail -1 > "$BT/collect.txt"
    grep -c '::' "$BT/collect-raw.txt" >> "$BT/collect.txt"
  fi
  base_n="$(tail -1 "$BT/collect.txt")"
  api pytest -q -p no:cacheprovider -m "not django_db" esgapi/core esgapi/greenwash > "$S4/5.log" 2>&1; e=$?
  passed="$(tail -1 "$S4/5.log")"
  now_n="$(echo "$passed" | sed -nE 's/^([0-9]+) passed.*/\1/p')"
  echo "    base=$base_n now=$passed"
  [ -n "$now_n" ] && [ "$now_n" -gt "$base_n" ] || e=1
  report 5 "순수 core·greenwash 초록·수 기준 → 뒤" $e
fi

if want 6; then
  start
  helper pinned > "$S4/6.log" 2>&1; e=$?
  (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi > "$S4/openapi.json" 2>> "$S4/6.log")
  cmp "$S4/openapi.json" "$API_PY/generated/openapi.json" >> "$S4/6.log" 2>&1 || e=1
  [ -z "$(git -C "$ROOT" diff --name-only "$BASE" -- apps/api-py/generated)" ] || e=1
  cat "$S4/6.log"; echo "    generated/openapi.json 다시 뽑음 cmp: $([ $e = 0 ] && echo same || echo DIFF)"
  report 6 "고정 스키마 cmp·generated cmp = 기준" $e
fi

if want 7; then start; api python scripts/check_test_layout.py > "$S4/7.log" 2>&1; e=$?; tail -1 "$S4/7.log"; report 7 "check_test_layout" $e; fi

if want 8; then
  start
  while [ -e "$(git -C "$ROOT" rev-parse --git-common-dir)/verify.lock" ]; do echo "    verify.lock 있음 — 기다림"; sleep 20; done
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast > "$S4/8.log" 2>&1)
  e=$?; tail -1 "$S4/8.log"; grep -q '^VERIFY_FAST=PASS' "$S4/8.log" || e=1
  report 8 "verify.sh --fast" $e
fi

if want 9; then
  start
  AP1a_OUT="$OUT" "$API_PY/scripts/planted-breaks-AP1a.sh" --commit "$COMMIT" > "$S4/9.log" 2>&1; e=$?
  grep -E '^(P[0-9]+ |P0=|FINGERPRINT=|PLANTED=)' "$S4/9.log" | grep -v '^P0 '
  report 9 "심은 파손" $e
fi

if want 10; then
  start
  if [ -n "$WITH_CONTAINERS" ]; then
    (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -q -p no:cacheprovider esgapi/greenwash esgapi/core > "$S4/10.log" 2>&1)
    e=$?; tail -1 "$S4/10.log"
  elif [ "$COMMIT" -ge 2 ]; then echo "    안 돌림(--with-containers 없음)"; e=1
  else echo "    경계 1 — 안 돌림(§4-10 은 ② 만)"; e=0; fi
  report 10 "업무 층 그린워싱·core" $e
fi

if want 11; then
  start
  if [ -n "$PREVIEW" ]; then
    P="$OUT/preview"; mkdir -p "$P"
    (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
      uv run --frozen python - "$P/openapi.json" > "$S4/11.log" 2>&1 <<'PY'
import json
import sys

import django

django.setup()
from ninja import NinjaAPI  # noqa: E402

from esgapi.core.contracts.ai_setting_shapes import AiPromptModel3  # noqa: E402

api = NinjaAPI(title="AP1a preview", urls_namespace="ap1a-preview")


@api.get("/preview", response=AiPromptModel3, operation_id="ai_prompt_model3_preview")
def preview(request: object) -> AiPromptModel3:
    raise NotImplementedError


with open(sys.argv[1], "w", encoding="utf-8") as out:
    out.write(json.dumps(api.get_openapi_schema(path_prefix=""), ensure_ascii=False, indent=2, sort_keys=True))
PY
    )
    e=$?
    (cd "$P" && PATH="$NODE_DIR:$PATH" pnpm dlx openapi-typescript@7.13.0 openapi.json -o api.d.ts >> "$S4/11.log" 2>&1) || e=1
    changed="$(jq -n --slurpfile p "$P/openapi.json" --slurpfile m "$API_PY/generated/openapi.json" \
      '[$p[0].components.schemas | to_entries[] | select(.key | startswith("Ai")) | select($m[0].components.schemas[.key] != null) | select($m[0].components.schemas[.key] != .value) | .key] | length')"
    shared="$(jq -n --slurpfile p "$P/openapi.json" --slurpfile m "$API_PY/generated/openapi.json" \
      '[$p[0].components.schemas | keys[] | select(startswith("Ai")) | select(. as $k | $m[0].components.schemas | has($k))] | join(",")')"
    added="$(jq -n --slurpfile p "$P/openapi.json" --slurpfile m "$API_PY/generated/openapi.json" \
      '[$p[0].components.schemas | keys[] | select(. as $k | $m[0].components.schemas | has($k) | not)] | join(",")')"
    cat > "$P/README" <<EOF
AP1a 웹 미리 보기 — ai.prompt-model@3 (커밋 0, 밖 출력)
가지 band/AP1a HEAD $(git -C "$ROOT" rev-parse HEAD) · 기준 $BASE
openapi.json = 시험 설정으로 지은 NinjaAPI 의 GET /preview (응답 AiPromptModel3) · api.d.ts = pnpm dlx openapi-typescript@7.13.0 (gen-ts-types.sh 와 같은 판)
새 구성요소: $added
main 에 있는 구성요소(값 대조): $shared
jq 대조: jq -n --slurpfile p openapi.json --slurpfile m <esg-app>/apps/api-py/generated/openapi.json '[\$p[0].components.schemas | to_entries[] | select(.key|startswith("Ai")) | select(\$m[0].components.schemas[.key] != null and \$m[0].components.schemas[.key] != .value) | .key] | length'
ai_components_changed=$changed
EOF
    cat "$P/README" | tail -3
    [ "$changed" = "0" ] && [ -s "$P/api.d.ts" ] || e=1
  elif [ "$COMMIT" -ge 2 ]; then echo "    안 돌림(--preview 없음)"; e=1
  else echo "    경계 1 — 안 돌림(미리 보기는 ②)"; e=0; fi
  report 11 "웹 미리 보기" $e
fi

if want 12; then
  start; helper secrets "$FORBIDDEN" > "$S4/12.log" 2>&1; e=$?; cat "$S4/12.log"
  report 12 "키 꼴·실재 기업명·자료 파일 0" $e
fi

echo "SECTION4_FAIL=$FAIL"
exit $(( FAIL > 0 ? 1 : 0 ))
