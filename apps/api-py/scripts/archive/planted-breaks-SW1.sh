#!/usr/bin/env bash
# 밴드 SW1 의 심은 파손(발주서 band-handoffs/SW1-order.md §3 P1~P11). 파손마다 바이트를 떠 두고 한 줄을 바꿔
# 표적 시험을 돌린 뒤 떠 둔 바이트로 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 컨테이너 없음(순수 층만).
#
#   apps/api-py/scripts/planted-breaks-SW1.sh        끝 줄 PLANTED=<잡은 수>/<전체>, 그 앞 줄 FINGERPRINT=same|DIFF
#
# 환경 변수: SW1_OUT 산출물 자리(기본: 워크트리 곁의 SW1.out). 파손마다의 pytest 출력은 $SW1_OUT/planted/ 아래.
# 「잡음」= 적힌 표적 시험이 전부 실패(pytest 의 「<표적 수> failed」). P4·P6 은 받은 머리 값 원문을 같이 찍는다.
# P8 의 컨테이너 몫(compose 를 옛 /readyz 로 되돌리면 통합의 「/readyz 200 아님」이 빨강인가)은 여기서 재지 않는다.
# macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
SIDE="$(cd "$API_PY/../../.." && pwd)"
OUT="${SW1_OUT:-$SIDE/SW1.out}/planted"
mkdir -p "$OUT"

cd "$API_PY" && uv run --frozen python - "$OUT" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

out = Path(sys.argv[1])
WEB = Path("esgapi/config/web.py")
BASE = Path("esgapi/config/settings/base.py")
API = Path("esgapi/config/api.py")
T = "esgapi/config/tests/test_web.py::"
C = "esgapi/config/tests/test_api_contract.py::"

# (이름, 파일, 옛 글자, 새 글자, 표적 시험들)
BREAKS = [
    (
        "P1 fallback 이 /api 를 빼지 않음",
        WEB,
        '    if head == "api":\n        return "api"\n',
        "",
        [T + "test_api_assets_and_reserved_paths_are_json_404[/api/no/such]"],
    ),
    (
        "P2 fallback 이 /assets/ 를 빼지 않음",
        WEB,
        '    if head == "assets":\n        return "asset"\n',
        "",
        [T + "test_api_assets_and_reserved_paths_are_json_404[/assets/none.js]"],
    ),
    (
        "P3 접두를 startswith(\"/api\") 로",
        WEB,
        '    if head == "api":\n',
        '    if path.startswith("/api"):\n',
        [T + "test_the_first_segment_decides_the_place[/apiary-screen]"],
    ),
    (
        "P4 WHITENOISE_IMMUTABLE_FILE_TEST 뺌",
        BASE,
        "WHITENOISE_IMMUTABLE_FILE_TEST = IMMUTABLE_FILE_TEST\n",
        "",
        [T + "test_a_hashed_asset_is_immutable_without_acao"],
    ),
    (
        "P5a fallback 의 no-cache 뺌",
        WEB,
        '    response["Cache-Control"] = "no-cache"\n',
        "",
        [T + "test_a_screen_path_gets_index_html_no_cache[/greenwash]"],
    ),
    (
        "P5b 머리 함수(/index.html)의 no-cache 뺌",
        WEB,
        '        headers["Cache-Control"] = "no-cache"\n',
        "        pass\n",
        [T + "test_index_html_by_name_is_no_cache_too"],
    ),
    (
        "P6 WHITENOISE_ALLOW_ALL_ORIGINS = False 뺌",
        BASE,
        "WHITENOISE_ALLOW_ALL_ORIGINS = False\n",
        "",
        [T + "test_a_hashed_asset_is_immutable_without_acao", T + "test_other_files_are_served_for_a_minute"],
    ),
    (
        "P7 docs_url 을 /api/docs 로 되돌림",
        API,
        '    docs_url="/docs",\n',
        '    docs_url="/api/docs",\n',
        [C + "test_openapi_and_docs_are_served"],
    ),
    (
        "P8 예약어 /healthz·/readyz 뺌",
        WEB,
        '    if head in RESERVED:\n        return "reserved"\n',
        "",
        [
            T + "test_api_assets_and_reserved_paths_are_json_404[/healthz]",
            T + "test_api_assets_and_reserved_paths_are_json_404[/readyz]",
        ],
    ),
    (
        "P9 fallback 이 POST 도 받음",
        WEB,
        'request.method not in ("GET", "HEAD")',
        'request.method not in ("GET", "HEAD", "POST")',
        [T + "test_other_methods_on_a_screen_path_are_json_404[post]"],
    ),
    (
        "P10 servers 뺌",
        API,
        '    servers=[{"url": "/api"}],\n',
        "",
        [C + "test_committed_openapi_matches_the_code"],
    ),
    (
        "P11 B2a 의 path_prefix 기본 \"\" 줄을 뺌",
        API,
        'path_prefix="" if path_prefix is None else path_prefix',
        "path_prefix=path_prefix",
        [C + "test_the_served_openapi_is_the_committed_one", C + "test_openapi_and_docs_are_served"],
    ),
]


def fingerprint() -> str:
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True)
    diff = subprocess.run(["git", "diff", "HEAD", "--", "."], capture_output=True)
    return status.stdout + hashlib.sha256(diff.stdout).hexdigest()


def plant(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def why(log: str) -> str:
    """빨강 까닭 한 줄: pytest 의 첫 assert 줄(받은 값 원문)."""
    lines = [line.strip() for line in log.splitlines() if line.startswith("E ")]
    return lines[0][:200] if lines else "-"


before = fingerprint()
caught = 0
env = {**os.environ, "PYTHONPYCACHEPREFIX": str(out / "pycache")}
for i, (name, path, old, new, tests) in enumerate(BREAKS, 1):
    held = path.read_bytes()
    try:
        plant(path, old, new)
        done = subprocess.run(
            ["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider", *tests],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        path.write_bytes(held)
    log = done.stdout + done.stderr
    (out / f"P{i}.log").write_text(log, encoding="utf-8")
    red = done.returncode != 0 and re.search(rf"\b{len(tests)} failed\b", done.stdout) is not None
    caught += red
    print(f"    {name} → {'빨강' if red else '★ 안 걸림'} ({len(tests)} 표적) · {why(log)}")
same = fingerprint() == before
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{len(BREAKS)}")
sys.exit(0 if caught == len(BREAKS) and same else 1)
PY
