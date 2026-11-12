#!/usr/bin/env bash
# 밴드 K2b 의 심은 파손 넷(정본 표 band-handoffs/K2-order.md 의 b-3-4 — CA 에서 뺀 것을 밴드 PB 가 되살림, 발주서
# band-handoffs/PB-order.md). 하나씩 심고 돌린 뒤 손으로 되돌린다: 심기 전에 원본을 저장소 밖(산출물 폴더의 orig/)에
# 떠 두고 그 바이트를 되쓴다 — git checkout·restore·stash 를 쓰지 않는다. 사용(apps/api-py 에서): scripts/planted-breaks-K2b.sh
#
# 판정(E2 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」(글 묶음 —
# 묶음의 글이 모두 한 줄에) 하나라도 출력의 FAILED·ERROR 줄에 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 두 층을 돈다: 순수 층(DB 없음)과 보안 층(tests/security/test_tenant_paths.py — scripts/test-security.sh 로. compose 의
# Postgres 가 떠 있어야 한다). 끝에 심은 파일의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF).
# 중간에 멈추면: Ctrl-C·SIGTERM·SIGHUP 은 되돌림(finally)을 타고 끝난다(130·143·129). kill -9 는 못 막는다 — 그때는
# 산출물 폴더의 orig/<파일 이름> 이 마지막으로 심기 전의 원본이다(거기서 되쓴다).
# 산출물: K2B_OUT(기본: 워크트리 곁의 K2b.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${K2B_OUT:-$(cd "$ROOT/.." && pwd)/K2b.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import signal
import subprocess
import sys
from pathlib import Path

# SIGTERM·SIGHUP 을 SystemExit 로 바꾼다: 기본 처리는 finally 없이 죽어 심은 글이 남는다. subprocess.run 안에서 나면
# 자식을 죽이고 다시 던지므로 아래의 되돌림(finally)이 돈다.
signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
signal.signal(signal.SIGHUP, lambda *_: sys.exit(129))

LOGS = Path(sys.argv[1])
ORIG = LOGS / "orig"
B = Path("esgapi/core/auth/bearer.py")
M = Path("esgapi/core/observability/middleware.py")
# 회사 경로의 auth= 목록이 적힌 자리(라우터 셋 + 경로 아홉 — 회사 동작 24)
COMPANY_AUTH_FILES = [
    Path("esgapi/config/api.py"),
    Path("esgapi/inventory/service/apis/inventory.py"),
    Path("esgapi/organization/service/apis/organization.py"),
    Path("esgapi/reference/service/apis/reference.py"),
]
PURE = [
    "esgapi/core/tests/auth/test_bearer.py",
    "esgapi/core/tests/test_observability_middleware.py",
]
SECURITY = ["tests/security/test_tenant_paths.py"]
PURE_CMD = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", "-m", "not django_db and not security", *PURE]
SECURITY_CMD = ["scripts/test-security.sh", "-rfE", "-p", "no:cacheprovider", *SECURITY]

BEARER_FIRST = "auth=[company_scoped_auth_or_next, session_cookie]"
COOKIE_FIRST = "auth=[session_cookie, company_scoped_auth_or_next]"

# (번호, 심는 것, [(파일, 옛 글, 새 글, 옛 글의 수), …], 빨개져야 하는 것 — 글 묶음들(묶음 하나가 한 줄에 다 있으면 맞음))
PLANTS = [
    ("P11", "회사 경로 auth= 목록의 차례를 뒤집음(쿠키 먼저 — 머리 없는 쿠키 인증이 401 no_session 을 먼저 던진다)",
     [(A, BEARER_FIRST, COOKIE_FIRST, n) for A, n in zip(COMPANY_AUTH_FILES, [3, 3, 2, 4], strict=True)],
     [["test_tenant_paths.py::", "bearer"],
      ["test_an_operator_bearer_is_401_company_required_on_every_company_operation"]]),
    ("P16", "접근 줄에서 user_id 를 뺌",
     [(M, '            user_id = authenticated_user_id(request)\n'
          '            if user_id is not None:\n'
          '                extra["user_id"] = user_id\n', "", 1)],
     [["test_the_access_line_carries_the_user_id_of_an_authenticated_request"],
      ["test_the_access_line_user_id_is_the_same_for_both_ways"]]),
    ("P30", "CompanyScopedAuth 가 회사 없는 토큰을 받음",
     [(B, "        principal = super().authenticate(request, token)\n"
          "        if principal.company_id is None:\n"
          "            raise company_required()\n",
          "        principal = super().authenticate(request, token)\n", 1)],
     [["test_bearer.py::test_the_company_auth_refuses_an_operator_token_as_company_required"],
      ["test_an_operator_bearer_is_401_company_required_on_every_company_operation"]]),
    ("P31", "틀린 Bearer 가 None(쿠키로 넘어감)",
     [(B, "        principal = super().authenticate(request, token)\n        if principal.company_id is None:",
          "        try:\n"
          "            principal = super().authenticate(request, token)\n"
          "        except ApplicationError:\n"
          "            return None  # type: ignore[return-value]\n"
          "        if principal.company_id is None:", 1)],
     [["test_a_bad_bearer_does_not_fall_back_to_the_cookie"]]),
]

files = sorted({edit[0] for plant in PLANTS for edit in plant[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
ORIG.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다.
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def run_both(name: str) -> tuple[int, str]:
    pure_code, pure_out = run(PURE_CMD, LOGS / f"{name}-pure.log")
    security_code, security_out = run(SECURITY_CMD, LOGS / f"{name}-security.log")
    print(f"    순수 종료 {pure_code} · 보안 종료 {security_code}")
    return pure_code or security_code, pure_out + "\n" + security_out


def red_lines(text: str) -> list[str]:
    # 시험의 줄만(「FAILED <경로>::<이름>」·「ERROR <경로>::<이름>」). caplog 가 찍는 「ERROR    django.request:…」 는 뺀다.
    return [line for line in text.splitlines() if line.startswith(("FAILED ", "ERROR ")) and "::" in line]


print("[0] 아무것도 안 심음")
code, out = run_both("00")
zero_ok = code == 0
print(f"[0] {'전부 초록' if zero_ok else '빨강이 있다'}")
for line in red_lines(out):
    print(f"    {line}")

caught = 0
for num, what, edits, want in PLANTS:
    touched = sorted({edit[0] for edit in edits})
    originals = {}
    for path in touched:
        originals[path] = path.read_bytes()
        (ORIG / path.name).write_bytes(originals[path])  # 저장소 밖 사본
    texts = {path: originals[path].decode("utf-8") for path in touched}
    counts = [texts[path].count(old) for path, old, _, _ in edits]
    expected = [n for _, _, _, n in edits]
    if counts != expected:
        print(f"[{num}] {what}: 심을 자리를 못 찾음(옛 글이 {counts} 번, 기대 {expected}) — 못 잡은 것으로 센다")
        continue
    for path, old, new, _ in edits:
        texts[path] = texts[path].replace(old, new)
    print(f"[{num}] {what}")
    try:
        for path in touched:
            path.write_text(texts[path], encoding="utf-8")
        code, out = run_both(num)
    finally:
        for path in touched:
            path.write_bytes((ORIG / path.name).read_bytes())  # 손으로 되돌림(저장소 밖 사본에서)
    reds = red_lines(out)
    hit = [" + ".join(group) for group in want if any(all(w in line for w in group) for line in reds)]
    ok = code != 0 and bool(hit)
    caught += ok
    print(f"[{num}] {'잡음' if ok else '못 잡음'} (종료 {code}, 빨간 줄 {len(reds)}, 기대한 것 중 맞은 것 {hit or '없음'})")
    for line in reds:
        print(f"    {line}")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
