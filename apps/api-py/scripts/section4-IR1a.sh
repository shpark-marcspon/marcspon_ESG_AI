#!/usr/bin/env bash
# 밴드 IR1a(MARC-TICK-274) §4 의 자기검증. 중대성평가 IRO 코랩 1부의 도구 없는 바닥(esgapi/materiality)을 잰다.
#   사용: apps/api-py/scripts/section4-IR1a.sh [--step <n>[,<n>…]] [--planted] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0.
#   아무것도 없으면 1~7·9·10. 8(심은 파손)은 --planted 일 때만 돈다 — 작업 트리의 파일을 하나씩 고쳐 쓰고 되돌리므로
#   같은 워크트리에서 다른 실행과 겹치지 않게 한 번에 하나만.
#   그 커밋에 닿지 않는 단계는 「해당 없음」을 찍고 EXIT=0 이다(무엇이 없어서인지 한 줄).
#   --msg 는 6·9단계가 함께 볼 커밋 메시지 초안(기본 $S4_OUT/commit-msg.txt — 있으면).
# 출력 자리는 S4_OUT(기본 esg-app.worktrees/IR1a.out). 검증자는 S4_OUT=…/IR1a.verify 로 돌려 러너 기록을 덮지 않는다.
# 읽기판(받은 코랩의 뽑은 판)은 워크트리 밖이다 — MARCSPON_ROOT(기본 워크트리의 ../..) 아래에서 읽고, 못 읽으면 FAIL.
#   읽기판의 글은 이 스크립트에도 출력에도 싣지 않는다(줄 범위·sha·수·EXIT 만). 7단계가 읽기판에서 뗀 셀 조각은
#   S4_OUT 아래(git 밖)에만 둔다(MARC-ENT-310).
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 -I. LLM·네트워크·키 파일·컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=926e7f98
OUT="${S4_OUT:-$ROOT/../IR1a.out}"
MARCSPON_ROOT="${MARCSPON_ROOT:-$ROOT/../..}"
READING_DIR="$MARCSPON_ROOT/received-derived/2026-10-15/중대성평가 IRO 코랩"
FORBIDDEN="$MARCSPON_ROOT/esg-app.worktrees/G1a.out/forbidden-words.txt"
API="$ROOT/apps/api-py"
M=esgapi/materiality
mkdir -p "$OUT"

ONLY=1,2,3,4,5,6,7,9,10
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) ONLY="$ONLY,8"; shift ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--planted] [--msg <파일>]" >&2; exit 2 ;;
  esac
done
[ -n "$MSG" ] || MSG="$OUT/commit-msg.txt"

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }
api() { (cd "$API" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$@"); }
echo "BASE=$BASE HEAD=$(git rev-parse HEAD)"

# 지금 커밋 경계: BASE 이후 IR1a 커밋 수 + 스테이징이 있으면 1. 「해당 없음」 판정은 파일 유무가 아니라 이것으로.
done_commits=$(git log --format=%s "$BASE..HEAD" | grep -c '^feat(materiality): IR1a ')
staged_n=$(git diff --cached --name-only | grep -c .)
CB=$((done_commits + (staged_n > 0 ? 1 : 0)))
[ "$CB" -ge 1 ] || CB=1
[ "$CB" -le 4 ] || CB=4
echo "커밋 경계 ${CB}(커밋 ${done_commits} + 스테이징 ${staged_n} 경로)"

READING=""
for f in "$READING_DIR"/*.md; do [ -r "$f" ] && READING="$f"; done
PY_COLAB="$(mktemp -t s4ir1a-colab.XXXXXX)"
cat > "$PY_COLAB" <<'PYEOF'
"""§4-7 코랩 대조: 읽기판에서 셀 코드를 뽑아 빈 이름공간에서 실행한 값 == 엔진 값(발주서 §4-7, 처분 ⑤ 가).

실행하는 것은 ⑴ 함수 정의와 dedent(…) 대입(if __name__ 블록 안 포함) ⑵ 답 처리 조각(줄 범위)을 AST 로 뗀 것뿐이다.
셀 코드를 글로 고치지 않고 AST 노드를 그대로 컴파일한다(문자열 안 들여쓰기가 바뀌지 않게). 뗀 조각은 out 자리에만
ast.unparse 로 남긴다(git 밖). 읽기판의 글은 출력하지 않는다(이름·수·sha·EXIT 만).
"""

import ast
import hashlib
import json
import os
import re
import sys
from textwrap import dedent

READING, OUT, CB = sys.argv[1], sys.argv[2], int(sys.argv[3])
os.makedirs(OUT, exist_ok=True)
TEXT = open(READING, encoding="utf-8").read()
LINES = TEXT.split("\n")


def cell(n):
    m = re.search(rf"^### 셀 {n} · code\n\n(`{{3,4}})python\n(.*?)\n\1$", TEXT, re.S | re.M)
    if not m:
        raise SystemExit(f"  ★ 읽기판에서 셀 {n} 의 코드를 못 찾았다")
    return m.group(2), TEXT[: m.start(2)].count("\n") + 1


def fp(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def base_ns():
    return {"dedent": dedent, "json": json, "re": re, "hashlib": hashlib, "fp": fp, "print": lambda *a, **k: None}


def statements(tree):
    """모든 문(stmt) — 몸 목록 안의 것."""
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody", "handlers"):
            children = getattr(node, field, None)
            for child in children if isinstance(children, list) else []:
                if isinstance(child, ast.stmt):
                    yield child


def pieces(code, start, ranges):
    """읽기판 줄 범위들 안에 통째로 든 가장 바깥 문들(차례대로)."""
    tree = ast.parse(code)
    spans = [(a - start + 1, b - start + 1) for a, b in ranges]
    inside = [s for s in statements(tree) if any(a <= s.lineno and s.end_lineno <= b for a, b in spans)]
    inside.sort(key=lambda s: (s.lineno, -s.end_lineno))
    out, last = [], 0
    for s in inside:
        if s.lineno > last:
            out.append(s)
            last = s.end_lineno
    return out


def run(stmts, ns, label):
    open(os.path.join(OUT, f"piece-{label}.py"), "w", encoding="utf-8").write(
        ast.unparse(ast.Module(body=stmts, type_ignores=[])) + "\n"
    )
    exec(compile(ast.Module(body=stmts, type_ignores=[]), label, "exec"), ns)
    return ns


def definitions(code, label):
    """함수 정의와 dedent(…) 대입(if __name__ 블록 안 포함)만 실행한 이름공간."""
    tree = ast.parse(code)
    body = []
    for node in tree.body:
        body += node.body if isinstance(node, ast.If) else [node]
    keep = [
        n
        for n in body
        if isinstance(n, ast.FunctionDef)
        or (
            isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Name)
            and n.value.func.id == "dedent"
        )
    ]
    return run(keep, base_ns(), label)


def swapped(code, start, a, b, block):
    """셀 코드의 읽기판 R/a-b 줄을 block(다른 셀의 줄 목록)으로 바꾼 글."""
    lines = code.split("\n")
    return "\n".join(lines[: a - start] + block + lines[b - start + 1 :])


def reading_lines(a, b):
    return LINES[a - 1 : b]


diffs = {}


def check(category, label, theirs, ours):
    same = theirs == ours
    if not same:
        print(f"  ★ {category} {label}")
    diffs[category] = diffs.get(category, 0) + (0 if same else 1)
    counts[category] = counts.get(category, 0) + 1


counts = {}

# 지어낸 입력(실재 0)
INDUSTRY = {
    1: [{"standard": "SASB", "industry_name": "가상 산업 하나", "description": "가상 설명 하나 — {괄호} 포함"}],
    3: [
        {"standard": "SASB", "industry_name": "가상 산업 하나", "description": "가상 설명 하나"},
        {"standard": "GICS", "industry_name": "가상 산업 둘(Virtual)", "description": "가상 설명 둘 'quote'"},
        {"standard": "KSIC", "industry_name": "가상 산업 셋", "description": "가상 설명 셋\t탭"},
    ],
}
TOPICS = [
    {"topic": "가상토픽 하나", "description": "가상토픽 하나의 설명"},
    {"topic": "가상토픽 둘", "description": "가상토픽 둘의 설명 {x}"},
]
LOCATION, LANG, DATES = "가상 범위(대한민국/EU)", "한국어", "2025-01-01~오늘까지"

sys.path.insert(0, os.getcwd())
from esgapi.materiality.engines.colab_155 import prompts, whitelists  # noqa: E402

c11, s11 = cell(11)
c17, s17 = cell(17)
c20, s20 = cell(20)
c22, s22 = cell(22)


def colab_industry_text(industry):
    return run(pieces(c11, s11, [(369, 371)]), {**base_ns(), "industry": industry}, "c11-industry_text")["industry_text"]


# ① 프롬프트 바이트
SYSTEMS = {
    "colab17": (None, whitelists.WHITELIST_COLAB17),
    "cell71": ((3677, 3752), whitelists.WHITELIST_CELL71),
    "cell73": ((3764, 3843), whitelists.WHITELIST_CELL73),
}
for name, (block, raw) in SYSTEMS.items():
    code = c17 if block is None else swapped(c17, s17, 573, 652, reading_lines(*block))
    ns17 = definitions(code, f"c17-{name}")
    check("①프롬프트", f"셀17 system[{name}]", ns17["system_prompt"], prompts.regulation_system(raw))
ns17 = definitions(c17, "c17")
ns20 = definitions(c20, "c20")
ns22 = definitions(c22, "c22")
check("①프롬프트", "셀17 접두", ns17["SPECIFIC_USER_PREFIX"], prompts.REGULATION_USER_PREFIX)
check("①프롬프트", "셀20 system", ns20["system_prompt"], prompts.KEYWORDS_SYSTEM)
check("①프롬프트", "셀20 접두", ns20["USER_PREFIX"], prompts.KEYWORDS_USER_PREFIX)
check("①프롬프트", "셀22 system", ns22["system_prompt"], prompts.CONTROVERSY_SYSTEM)
check("①프롬프트", "셀22 접두", ns22["SPECIFIC_USER_PREFIX"], prompts.CONTROVERSY_USER_PREFIX)
for n, industry in INDUSTRY.items():
    text = colab_industry_text(industry)
    for t in TOPICS:
        check(
            "①프롬프트",
            f"셀17 가변(산업 {n})",
            ns17["build_specific_user_prompt"](t["topic"], t["description"], text, LOCATION, LANG),
            prompts.regulation_user(t["topic"], t["description"], text, LOCATION, LANG),
        )
        for kw in ("가상 키워드 1, 가상 키워드 2", "(키워드 없음)"):
            check(
                "①프롬프트",
                f"셀22 가변(산업 {n})",
                ns22["build_specific_user_prompt"](t["topic"], t["description"], industry, LOCATION, LANG, kw),
                prompts.controversy_user(t["topic"], t["description"], industry, LOCATION, LANG, kw),
            )
    ns20["topics"] = TOPICS  # 코랩은 전역 topics 를 읽는다
    check(
        "①프롬프트",
        f"셀20 가변(산업 {n})",
        ns20["build_user_prompt"](industry, DATES, LANG),
        prompts.keywords_user(industry, DATES, LANG, TOPICS),
    )

# ⑥ README 블록 sha256 == 읽기판
readme = os.path.join("esgapi", "materiality", "prompts", "README.md")
rows = re.findall(r"R/(\d+)-(\d+) \| `([0-9a-f]{64})`", open(readme, encoding="utf-8").read())
for a, b, sha in rows:
    block = "\n".join(reading_lines(int(a), int(b)))
    check("⑥README", f"R/{a}-{b}", hashlib.sha256(block.encode("utf-8")).hexdigest(), sha)
if len(rows) < 12:
    print(f"  ★ README 의 블록 줄이 {len(rows)} — 12 를 기대")
    diffs["⑥README"] = diffs.get("⑥README", 0) + 1

if CB >= 3:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    from esgapi.materiality.engines.colab_155 import inputs, outcomes, parsing

    c8, s8 = cell(8)
    ns8 = run(pieces(c8, s8, [(216, 258)]), base_ns(), "c8-extract_json_obj")
    theirs_extract = ns8["extract_json_obj"]

    def outcome(fn, text):
        try:
            return ("value", fn(text))
        except Exception as e:  # noqa: BLE001 — 값·예외 타입·문구를 견준다
            return ("raise", type(e).__name__, str(e))

    # ② extract_json_obj 예시 + hypothesis(시드 고정)
    EXAMPLES = [
        "",
        "   \n ",
        "설명만 있다",
        '{"a": 1}',
        '앞 글 {"a": {"b": [1, 2]}} 뒤 글',
        '```json\n{"a": "x"}\n```',
        '{"a": "괄호 } 안"}',
        '{"a": "따옴표 \\" 와 } 괄호"}',
        '{"a": "역빗금 \\\\"}',
        '{"a": 1} {"b": 2}',
        '{"a": 1',
        '{"a": 1,}',
        "{'a': 1}",
        '"{"a": 1}',
        '{"a": "\\u00e9"}',
    ]
    for i, text in enumerate(EXAMPLES):
        check("②extract_json_obj", f"예시 {i}", outcome(theirs_extract, text), outcome(parsing.extract_json_obj, text))

    texts = st.one_of(
        st.text(alphabet='{}[]":,\\ ab1\n', max_size=40),
        st.builds(
            lambda pre, obj, post: pre + json.dumps(obj, ensure_ascii=False) + post,
            st.text(alphabet='ab {"\\\n', max_size=8),
            st.dictionaries(
                st.text(max_size=5),
                st.recursive(
                    st.none() | st.booleans() | st.integers() | st.text(max_size=6),
                    lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=3), inner, max_size=3),
                    max_leaves=6,
                ),
                max_size=4,
            ),
            st.text(alphabet='ab }"\\\n', max_size=8),
        ),
    )
    seen = {"n": 0, "bad": 0}

    @settings(max_examples=600, derandomize=True, database=None, suppress_health_check=list(HealthCheck), deadline=None)
    @given(texts)
    def hyp(text):
        seen["n"] += 1
        if outcome(theirs_extract, text) != outcome(parsing.extract_json_obj, text):
            seen["bad"] += 1

    hyp()
    print(f"  hypothesis(derandomize) {seen['n']} 예 · 다름 {seen['bad']}")
    diffs["②extract_json_obj"] = diffs.get("②extract_json_obj", 0) + seen["bad"]
    counts["②extract_json_obj"] = counts.get("②extract_json_obj", 0) + seen["n"]

    # ③ industry_text
    for n, industry in INDUSTRY.items():
        check("③industry_text", f"산업 {n}", colab_industry_text(industry), inputs.industry_text(industry))

    # ④ 셀 17·22 답 처리 → 묶음(키 차례까지)
    ANSWERS = [
        None,
        "",
        "  ",
        "객체가 없다",
        '{"topic_name": "가상토픽 하나", "results": {"KR": [], "EU": [], "US": []}}',
        '{"topic_name": "다른 이름", "results": {"items": []}}',
        '{"topic_name": "가상토픽 하나", "u": "https://example.go.kr/a?utm_source=openai", '
        '"v": "https://example.go.kr/b?x=1&utm_source=openai"}',
        '{"u": "https://example.go.kr/c?utm_source=openai&x=1"}',
        "```json\n{\"topic_name\": \"가상토픽 하나\"}\n```",
        '{"a": 1',
        '{"a": 1,}',
        '{"a": "}"} 뒤 {"b": 2}',
    ]
    reg_piece = pieces(c17, s17, [(789, 789), (793, 809)])
    con_piece = pieces(c22, s22, [(1093, 1131)])
    for i, text in enumerate(ANSWERS):
        result = None if text is None else {"output_text": text}
        topic = "가상토픽 하나"
        ns = run(reg_piece, {**base_ns(), "extract_json_obj": theirs_extract, "specific_result": result,
                             "topic_name": topic, "regulation_updates_by_topic": {}}, "c17-answer")
        theirs = ns["regulation_updates_by_topic"][topic]
        ours = outcomes.regulation_bundle(text)
        check("④묶음", f"셀17 답 {i}", list(theirs.items()), list(ours.items()))
        ns = run(con_piece, {**base_ns(), "extract_json_obj": theirs_extract, "result": result,
                             "topic_name": topic, "controversies_by_topic": {}}, "c22-answer")
        theirs = ns["controversies_by_topic"][topic]
        ours = outcomes.controversy_bundle(text, topic)
        same_json = json.dumps(theirs, ensure_ascii=False) == json.dumps(ours, ensure_ascii=False)
        check("④묶음", f"셀22 답 {i}", (list(theirs.items()), same_json), (list(ours.items()), True))

    # ⑤ 셀 20 파싱 — ⑩ 은 허용 목록(코랩이 멈추거나 list[str] 아닌 값을 남기면 우리는 failed)
    KEYWORD_ANSWERS = [
        '{"topics": [{"topic": "가상토픽 하나", "keywords": ["가", "나"]}, {"topic": "가상토픽 둘", "keywords": []}]}',
        '앞 글 ```json\n{"topics": [{"topic": "가상토픽 하나", "keywords": ["가"]}]}\n``` 뒤 글',
        '{"topics": [{"topic": "가상토픽 하나", "keywords": ["가"]}, {"topic": "가상토픽 하나", "keywords": ["나"]}]}',
        '{"topics": []}',
        '{"other": 1}',
        '{"topics": [{"topic": "가상토픽 하나", "keywords": ["가"]}]} 설명 {"x": 1}',
        "객체 없음",
        '{"topics": [',
        '{"topics": {"topic": "가상토픽 하나"}}',
        '{"topics": [{"topic": "가상토픽 하나"}]}',
        '{"topics": [{"keywords": ["가"]}]}',
        '{"topics": [{"topic": "가상토픽 하나", "keywords": "가, 나"}]}',
        '{"topics": [{"topic": "가상토픽 하나", "keywords": [1, 2]}]}',
        '{"topics": ["가상토픽 하나"]}',
        '{"topics": "가상"}',
        '{"topics": [{"topic": 1, "keywords": ["가"]}]}',
    ]
    kw_piece = pieces(c20, s20, [(918, 954)])
    ks_piece = pieces(c22, s22, [(1083, 1084)])
    allowed = 0
    for i, text in enumerate(KEYWORD_ANSWERS):
        try:
            ns = run(kw_piece, {**base_ns(), "keyword_result": {"output_text": text}, "topics": TOPICS}, "c20-parse")
            theirs = ("value", ns["topic_to_keywords"])
        except Exception as e:  # noqa: BLE001
            theirs = ("raise", type(e).__name__)
        ours = parsing.parse_keywords(text)
        mapping = dict(ours.by_topic) if isinstance(ours, parsing.KeywordsParsed) else None
        if theirs[0] == "raise" or (
            theirs[0] == "value"
            and not all(
                isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v)
                for k, v in theirs[1].items()
            )
        ):
            same = mapping is None  # ⑩: 코랩이 멈추거나 list[str] 아닌 값 → 우리는 failed
            allowed += 1
        elif theirs[1] == {} and mapping is None:
            same = True  # 코랩의 JSONDecodeError·{ 없음 → {} 와 우리 failed
        else:
            same = mapping == theirs[1] and list((mapping or {}).items()) == list(theirs[1].items())
        check("⑤키워드", f"답 {i}", True, same)
        if mapping is not None:
            for t in TOPICS:
                ns = run(ks_piece, {**base_ns(), "topic_to_keywords": mapping, "topic_name": t["topic"]}, "c22-kw")
                check("⑤키워드", f"keyword_str {i}", ns["keyword_str"], parsing.keyword_str(mapping, t["topic"]))
    print(f"  ⑩ 허용 목록에 든 답 {allowed}")
    ns = run(ks_piece, {**base_ns(), "topic_to_keywords": {}, "topic_name": "가상"}, "c22-kw")
    check("⑤키워드", "keyword_str 빈", ns["keyword_str"], parsing.keyword_str({}, "가상"))
else:
    for name in ("②extract_json_obj", "③industry_text", "④묶음", "⑤키워드"):
        print(f"  {name}: 해당 없음 — 커밋 경계 {CB}(도우미는 커밋 ③ 부터)")

for k in sorted(counts):
    print(f"  {k}: 견줌 {counts[k]} · 다름 {diffs.get(k, 0)}")
total = sum(diffs.values())
print(f"COLAB_DIFF={total}")
sys.exit(int(total != 0))
PYEOF

reading_ok() {
  if [ -z "$READING" ]; then echo "  ★ 읽기판을 못 읽는다(MARCSPON_ROOT=$MARCSPON_ROOT)"; return 1; fi
  return 0
}

PY_HELPER="$(mktemp -t s4ir1a.XXXXXX)"
trap 'rm -f "$PY_HELPER" "$PY_COLAB"' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import hashlib, json, os, re, subprocess, sys

MODE, BASE, CB = sys.argv[1], sys.argv[2], int(sys.argv[3])
API = "apps/api-py/"
M = API + "esgapi/materiality/"


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def untracked():
    return git("ls-files", "--others", "--exclude-standard").splitlines()


def changed():
    return sorted(set(git("diff", "--name-only", BASE).splitlines()) | set(untracked()))


def added_lines():
    """BASE 이후 더한 줄(추적 파일의 diff ^+ 와 새 파일 전부)."""
    lines = [l[1:] for l in git("diff", "-U0", BASE).splitlines() if l.startswith("+") and not l.startswith("+++")]
    for f in untracked():
        try:
            lines += open(f, encoding="utf-8").read().splitlines()
        except UnicodeDecodeError:
            lines.append(f"<바이너리 {f}>")
    return lines


ALLOWED = re.compile(r"^(apps/api-py/esgapi/materiality/.*|apps/api-py/\.importlinter|apps/api-py/scripts/section4-IR1a\.sh)$")
# 처분 ③ 표(BASE 926e7f9 의 줄): (앞 줄, 더한 줄, 들어가는 커밋 경계)
LINT_ROWS = [
    ("    esgapi.translation", "    esgapi.materiality", 1),  # 가 forbidden :25
    ("    esgapi.translation", "    esgapi.materiality", 1),  # 나 source :52
    ("    esgapi.translation.models", "    esgapi.materiality.models", 1),  # 나 forbidden :62
    ("    esgapi.translation.** -> esgapi.translation.models", "    esgapi.materiality.** -> esgapi.materiality.models", 1),
    ("    esgapi.translation.outputs", "    esgapi.materiality.contracts", 1),  # 다 source :115
    ("    esgapi.materiality.contracts", "    esgapi.materiality.engines", 2),  # 다 ②
    ("    esgapi.materiality.engines", "    esgapi.materiality.outputs", 4),  # 다 ④
    ("    esgapi.translation", "    esgapi.materiality", 1),  # 바 forbidden :193
    ("    esgapi.translation.** -> esgapi.translation.**", "    esgapi.materiality.** -> esgapi.materiality.**", 1),
    ("    esgapi.translation", "    esgapi.materiality", 1),  # 차 forbidden :350(끝)
]


def step4():
    """완화(# pyright:·type: ignore)는 tests/ 만."""
    strict = re.compile("# py" + "right:|py" + "right: ignore|type" + ": ignore")
    bad = 0
    for f in changed():
        if f.endswith(".py") and os.path.isfile(f) and "/tests/" not in f:
            for i, line in enumerate(open(f, encoding="utf-8"), 1):
                if strict.search(line):
                    bad += 1
                    print(f"  ★ 제품 코드의 완화 줄: {f}:{i}")
    print(f"  제품 코드의 완화 줄 {bad}")
    return bad


def step5():
    bad = 0
    for f in changed():
        ok = ALLOWED.match(f) and "__pycache__" not in f
        if not ok:
            print(f"  ★ 허용 밖 {f}")
        bad += 0 if ok else 1
    print(f"  바뀐 경로 {len(changed())} · 허용 밖 {bad}")
    diff = git("diff", "-U0", BASE, "--", API + ".importlinter").splitlines()
    minus = [l for l in diff if re.match(r"^-[^-]", l)]
    plus = [l[1:] for l in diff if re.match(r"^\+[^+]", l)]
    rows = [(a, t) for a, t, cb in LINT_ROWS if cb <= CB]
    print(f"  .importlinter: 지운 줄 {len(minus)} · 더한 줄 {len(plus)} · 표의 줄(경계 {CB} 까지) {len(rows)}")
    if minus or sorted(plus) != sorted(t for _, t in rows):
        bad += 1
        print("  ★ 더한 줄이 처분 ③ 표와 다르다")
    lines = open(API + ".importlinter", encoding="utf-8").read().split("\n")
    at = 0
    for anchor, text in rows:
        hit = next((i for i in range(at, len(lines) - 1) if lines[i] == anchor and lines[i + 1] == text), None)
        if hit is None:
            bad += 1
            print(f"  ★ 자리가 표와 다르다: {anchor.strip()} 뒤의 {text.strip()}")
        else:
            at = hit + 1
    return bad


def cell_code(reading, cell):
    """읽기판에서 셀 하나의 코드 블록(```python … ```)과 그 첫 줄의 읽기판 줄 번호."""
    text = open(reading, encoding="utf-8").read()
    m = re.search(rf"^### 셀 {cell} · code\n\n(`{{3,4}})python\n(.*?)\n\1$", text, re.S | re.M)
    if not m:
        raise SystemExit(f"  ★ 읽기판에서 셀 {cell} 의 코드를 못 찾았다")
    return m.group(2), text[: m.start(2)].count("\n") + 1


def reading_texts(reading):
    """셀 11 의 industry_name·description 글과 셀 44 의 description 글(20자 이상) — 견줄 실제 예시 값."""
    out = set()
    for cell, minimum in ((11, 1), (44, 20)):
        code, _ = cell_code(reading, cell)
        for key, value in re.findall(r'"(industry_name|description)":\s*"([^"]*)"', code):
            if cell == 11 or len(value) >= minimum:
                out.add(value)
    return sorted(out)


def step6(reading, msg, report, forbidden):
    bad = 0
    words = [w for w in open(forbidden, encoding="utf-8").read().splitlines() if w.strip()]
    planted = [f"가상 줄 {words[0]} 가상"] if words else []
    if sum(1 for l in planted if any(x in l for x in words)) != 1:
        print("  ★ 금지 글 양성 대조 실패(목록이 비었거나 무늬가 안 문다)")
        bad += 1
    texts = {"diff ^+": added_lines(), "커밋 메시지": git("log", "--format=%B", f"{BASE}..HEAD").splitlines()}
    for name, path in (("메시지 초안", msg), ("보고", report)):
        if os.path.isfile(path):
            texts[name] = open(path, encoding="utf-8").read().splitlines()
    key = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
    fake = "sk" + "-" + "A" * 20
    if not key.search(fake):
        print("  ★ 키 꼴 양성 대조 실패")
        bad += 1
    samples = reading_texts(reading)
    for name, lines in texts.items():
        w = sum(1 for l in lines if any(x in l for x in words))
        k = sum(1 for l in lines if key.search(l))
        s = sum(1 for l in lines if any(x in l for x in samples)) if name == "diff ^+" else 0
        print(f"  {name}: 줄 {len(lines)} · 금지 글 {w} · 키 꼴 {k} · 코랩 예시 값 {s}")
        bad += w + k + s
    print(f"  금지 글 {len(words)}개 · 코랩 예시 값 {len(samples)}개(셀 11·44 에서 뽑음 — 0 이면 대조가 안 문다)")
    if len(samples) < 10:
        bad += 1
    exts = [f for f in changed() if re.search(r"\.(xlsx|csv|ipynb)$", f)]
    binary = [f for f in changed() if os.path.isfile(f) and b"\0" in open(f, "rb").read()]
    print(f"  xlsx·csv·ipynb 경로 {len(exts)} · 바이너리 {len(binary)}")
    bad += len(exts) + len(binary)
    jsons = [f for f in changed() if f.endswith(".json")]
    allowed_json = {
        M + "tests/data/flow-shapes/materiality.input@1.schema.json",
        M + "tests/data/flow-shapes/materiality.result@1.schema.json",
        M + "tests/data/examples/input-sample.json",
        M + "tests/data/examples/result-sample.json",
    }
    odd_json = [f for f in jsons if f not in allowed_json]
    print(f"  JSON 파일 {len(jsons)} · 고정 스키마 둘·합성 예시 둘 밖 {len(odd_json)}")
    bad += len(odd_json)
    company = []
    for f in changed():
        if f.startswith(M + "tests/") and os.path.isfile(f) and (f.endswith(".py") or f.endswith(".json")):
            company += re.findall(r'"name":[ ]*"([^"]*)"', open(f, encoding="utf-8").read())
    odd = [c for c in company if not c.startswith("가상")]
    print(f"  시험 자료의 이름 칸 {len(company)} · 가상 밖 {len(odd)}")
    return bad + len(odd)


TRAILERS = [
    "Ticket: MARC-TICK-274",
    "Derives-from: MARC-ENT-155",
    "Derives-from: MARC-ENT-425",
    "Constraint: 코랩 1부대로(약점 포함), 사본 0 — MARC-ENT-425, MARC-ENT-310",
    "Directive: engines/colab_155 의 1부 글은 고치지 않는다 — 고침은 engines/<다음 판>/ 새로",
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
]


def step9(msg):
    lines = open(msg, encoding="utf-8").read().rstrip("\n").split("\n")
    bad = 0
    if not re.match(r"^feat\(materiality\): IR1a [①②③④⑤] ", lines[0]):
        bad += 1
        print("  ★ 제목이 feat(materiality): IR1a ①… 꼴이 아니다")
    block = []
    for line in reversed(lines):
        if not line.strip():
            break
        block.insert(0, line)
    missing = [t for t in TRAILERS if t not in block]
    for t in missing:
        print(f"  ★ 트레일러 없음: {t.split(':')[0]}")
    loose = [l for l in block if not re.match(r"^[A-Z][A-Za-z-]+: ", l)]
    print(f"  제목 줄 {len(lines[0])}자 · 끝 문단 {len(block)}줄 · 빠진 트레일러 {len(missing)} · 트레일러 꼴 아닌 줄 {len(loose)}")
    return bad + len(missing) + len(loose)


E = M + "engines/colab_155/"
T = "esgapi/materiality/tests/engines/colab_155/"
# P3: regulation_user 를 미리 푼(6칸 벗긴) 글로 — dedent 를 걷어 낸 f-문자열
REG_USER = (
    '    return dedent(f"""\\\n      [가변 입력]\n      industry_definition:\n      {industry_text}\n\n'
    '      geo_scope: {location}\n      preferred_language: {main_language}\n\n'
    '      topic_name: {topic_name}\n      topic_desc: {topic_desc}""")\n'
)
REG_USER_FLAT = (
    '    return f"""[가변 입력]\nindustry_definition:\n{industry_text}\n\n'
    'geo_scope: {location}\npreferred_language: {main_language}\n\n'
    'topic_name: {topic_name}\ntopic_desc: {topic_desc}"""\n'
)

# 심은 파손: (번호, 들어가는 커밋 경계, 파일, 옛 글, 새 글, 빨개져야 할 것들). 빨개질 것: ("pytest", 경로) · ("lint",) · ("s7",)
PLANTS = [
    ("P7", 1, M + "contracts/shapes.py", "    topicCount: Count\n", "    topicCount: Count\n    planted: str\n",
     [("pytest", "esgapi/materiality/tests/contracts/test_shapes.py")]),
    ("P9", 1, M + "contracts/__init__.py", None, "import django  # noqa: F401\n", [("lint",)]),
    ("P9", 2, M + "engines/__init__.py", None, "import django  # noqa: F401\n", [("lint",)]),
    ("P9", 4, M + "outputs/__init__.py", None, "import django  # noqa: F401\n", [("lint",)]),
    ("P2", 2, E + "prompts.py", "\n  {{\n", "\n  {\n", [("pytest", T + "test_prompts.py"), ("s7",)]),
    ("P3", 2, E + "prompts.py", REG_USER, REG_USER_FLAT, [("pytest", T + "test_prompts.py"), ("s7",)]),
    ("P6", 2, E + "whitelists.py", "              12. 법제처 https://www.law.go.kr/main.html\n", "",
     [("pytest", T + "test_whitelists.py"), ("s7",)]),
    ("P10", 2, E + "constants.py", None, "from esgapi.materiality.contracts import shapes  # noqa: F401\n",
     [("pytest", T + "test_purity.py")]),
    ("P1", 3, E + "parsing.py",
     "            if escape:\n                escape = False\n            elif ch == \"\\\\\":\n                escape = True\n            elif ch == '\"':",
     "            if ch == '\"':", [("pytest", T + "test_parsing.py"), ("s7",)]),
    ("P4", 3, E + "constants.py", 'UTM_SUFFIXES: Final = ("?utm_source=openai", "&utm_source=openai")',
     'UTM_SUFFIXES: Final = ("?utm_source=openai",)', [("pytest", T + "test_parsing.py")]),
    ("P5", 3, E + "inputs.py", "    resolved = dict(subtopics_by_topic)\n", "    resolved = subtopics_by_topic\n",
     [("pytest", T + "test_inputs.py")]),
    ("P8", 3, E + "outcomes.py", "        parse_error = repr(e)\n", "        parse_error = str(e)\n",
     [("pytest", T + "test_outcomes.py"), ("s7",)]),
    ("P11", 4, M + "outputs/xlsx.py", '"F": "규제 및 정책"', '"F": "규제·정책"',
     [("pytest", "esgapi/materiality/tests/outputs/test_xlsx.py")]),
]


def red(check, out):
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
    if check[0] == "pytest":
        cmd, cwd = ["uv", "run", "--frozen", "pytest", "-q", "-x", "-p", "no:cacheprovider", check[1]], API
    elif check[0] == "lint":
        cmd, cwd = ["uv", "run", "--frozen", "lint-imports"], API
    else:
        cmd, cwd = ["bash", API + "scripts/section4-IR1a.sh", "--step", "7"], "."
        env["S4_OUT"] = os.path.join(out, "planted-s7")
    done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    lines = [l for l in (done.stdout + done.stderr).splitlines() if l.strip()]
    tail = [l for l in lines if l.startswith("COLAB_DIFF=")][-1:] or lines[-1:] or [""]
    if check[0] == "s7" and not re.match(r"^COLAB_DIFF=[1-9][0-9]*$", tail[0]):
        return False, "★ 대조가 다름 수를 내지 못했다(멈춤이나 0) · " + tail[0][:80]
    return done.returncode != 0, tail[0][:100]


def step8(out):
    rows = [p for p in PLANTS if p[1] <= CB]
    names = sorted({p[0] for p in rows}, key=lambda n: int(n[1:]))
    caught = 0
    for name in names:
        ok = True
        for _, _, path, old, new, checks in [p for p in rows if p[0] == name]:
            original = open(path, "rb").read()
            text = original.decode("utf-8")
            if old is None:
                planted = new + text
            elif text.count(old) != 1:
                print(f"  ★ {name}: {path} 에 심을 자리가 하나가 아니다({text.count(old)})")
                ok = False
                continue
            else:
                planted = text.replace(old, new)
            try:
                open(path, "w", encoding="utf-8").write(planted)
                for check in checks:
                    is_red, tail = red(check, out)
                    print(f"  {name} {path.removeprefix(M)} → {check[0]} {'빨강' if is_red else '★ 초록'} · {tail}")
                    ok = ok and is_red
            finally:
                open(path, "wb").write(original)
            if open(path, "rb").read() != original:
                print(f"  ★ {name}: 되돌리기 실패 {path}")
                ok = False
        caught += ok
    print(f"PLANTED={caught}/{len(names)}(경계 {CB} 까지 · 발주서 전체 11)")
    return int(caught != len(names))


if MODE == "4":
    sys.exit(min(step4(), 1))
elif MODE == "5":
    sys.exit(min(step5(), 1))
elif MODE == "6":
    sys.exit(min(step6(sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]), 1))
elif MODE == "8":
    sys.exit(step8(sys.argv[4]))
elif MODE == "9":
    sys.exit(min(step9(sys.argv[4]), 1))
PYEOF

# 1. materiality 표적(수집 수)
if want 1; then
  api uv run --frozen pytest -q $M -p no:cacheprovider > "$OUT/s1-pytest.log" 2>&1
  code=$?
  tries=$(grep -c -E '소켓 연결을 시도했다|이름 풀이를 시도했다' "$OUT/s1-pytest.log")
  passed=$(tail -1 "$OUT/s1-pytest.log" | sed -n -E 's/^([0-9]+) passed.*/\1/p')
  case "$CB" in 1) floor=14 ;; 2) floor=38 ;; 3) floor=101 ;; *) floor=117 ;; esac
  echo "  $(tail -1 "$OUT/s1-pytest.log") · 막힌 소켓 시도 $tries · 경계 ${CB} 의 바닥 ${floor}"
  if [ "$tries" != 0 ] || [ -z "$passed" ] || [ "$passed" -lt "$floor" ]; then code=1; fi
  report 1 "pytest $M" "$code"
fi

# 2. import 계약 17
if want 2; then
  api uv run --frozen lint-imports > "$OUT/s2-lint.log" 2>&1
  code=$?
  got=$(grep 'Contracts:' "$OUT/s2-lint.log")
  echo "  $got"
  if [ "$got" != "Contracts: 17 kept, 0 broken." ]; then code=1; fi
  report 2 "lint-imports(계약 17)" "$code"
fi

# 3. 시험 자리
if want 3; then
  api uv run --frozen python scripts/check_test_layout.py > "$OUT/s3-layout.log" 2>&1
  code=$?
  echo "  $(head -1 "$OUT/s3-layout.log")"
  report 3 "check_test_layout" "$code"
fi

# 4. 타입·꼴(완화는 tests/ 만, ruff format 이 프롬프트 글을 안 바꿈)
if want 4; then
  api uv run --frozen pyright $M > "$OUT/s4-pyright.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s4-pyright.log")"
  api uv run --frozen ruff check $M > "$OUT/s4-ruff.log" 2>&1 || code=1
  api uv run --frozen ruff format --check $M >> "$OUT/s4-ruff.log" 2>&1 || code=1
  echo "  $(tail -1 "$OUT/s4-ruff.log")"
  python3 -I "$PY_HELPER" 4 "$BASE" "$CB" || code=1
  report 4 "pyright·ruff·완화 줄" "$code"
fi

# 5. 경로·.importlinter 더하기만(처분 ③ 표, 그 커밋까지)
if want 5; then
  python3 -I "$PY_HELPER" 5 "$BASE" "$CB"
  report 5 "허용 경로·.importlinter" $?
fi

# 6. 금지 글·키·바이너리·코랩 예시 값
if want 6; then
  if reading_ok && [ -r "$FORBIDDEN" ]; then
    python3 -I "$PY_HELPER" 6 "$BASE" "$CB" "$READING" "$MSG" "$MARCSPON_ROOT/band-reports/IR1a.md" "$FORBIDDEN"
    code=$?
  else
    echo "  ★ 읽기판이나 금지 글 목록을 못 읽는다"
    code=1
  fi
  report 6 "금지 글·키·바이너리·예시 값" "$code"
fi

# 7. 코랩 대조(커밋 ② 부터)
if want 7; then
  if [ "$CB" -lt 2 ]; then
    echo "  해당 없음 — 커밋 경계 ${CB}(엔진은 커밋 ② 부터)"
    echo "COLAB_DIFF=해당 없음"
    report 7 "코랩 대조" 0
  elif reading_ok; then
    rm -rf "$OUT/s7-pieces"
    api uv run --frozen python -I "$PY_COLAB" "$READING" "$OUT/s7-pieces" "$CB" > "$OUT/s7-colab.log" 2>&1
    code=$?
    grep -v '^COLAB_DIFF=' "$OUT/s7-colab.log" | sed 's/^/  /' | tail -30
    grep '^COLAB_DIFF=' "$OUT/s7-colab.log" || { echo "COLAB_DIFF=없음(대조가 끝나지 않았다)"; code=1; }
    report 7 "코랩 대조" "$code"
  else
    report 7 "코랩 대조" 1
  fi
fi

# 8. 심은 파손(--planted). 하나씩 심고 빨강을 보고 바이트째 되돌린다. 끝나고 git status 가 시작 때와 같아야 한다.
if want 8; then
  before=$(git status --porcelain)
  python3 -I "$PY_HELPER" 8 "$BASE" "$CB" "$OUT" > "$OUT/s8-planted.log" 2>&1
  code=$?
  sed 's/^/  /' "$OUT/s8-planted.log" | grep -v '^  PLANTED='
  grep '^PLANTED=' "$OUT/s8-planted.log"
  if [ "$(git status --porcelain)" != "$before" ]; then code=1; echo "  ★ 심은 파손 뒤 작업 트리가 달라졌다"; fi
  report 8 "심은 파손(커밋 ${CB} 까지)" "$code"
fi

# 9. 커밋 메시지 트레일러
if want 9; then
  if [ -f "$MSG" ]; then
    python3 -I "$PY_HELPER" 9 "$BASE" "$CB" "$MSG"
    report 9 "트레일러($MSG)" $?
  elif [ "$done_commits" -gt 0 ]; then
    git log -1 --format=%B HEAD > "$OUT/s9-head-msg.txt"
    echo "  메시지 초안이 없어 HEAD 커밋 메시지를 본다"
    python3 -I "$PY_HELPER" 9 "$BASE" "$CB" "$OUT/s9-head-msg.txt"
    report 9 "트레일러(HEAD)" $?
  else
    echo "  ★ 메시지 초안도 IR1a 커밋도 없다($MSG)"
    report 9 "트레일러" 1
  fi
fi

# 10. 빠른 게이트(뿌리에서)
if want 10; then
  start=$(date +%s)
  PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast > "$OUT/s10-verify-fast.log" 2>&1
  code=$?
  last=$(tail -1 "$OUT/s10-verify-fast.log")
  echo "  $last · $(( $(date +%s) - start ))초"
  if [ "$last" != "VERIFY_FAST=PASS" ]; then code=1; fi
  report 10 "scripts/verify.sh --fast" "$code"
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
