#!/usr/bin/env bash
# 밴드 RX1a 의 심은 파손(발주서 band-handoffs/RX1a-order.md §3 표 — RF1 의 planted-breaks-RF1.sh 꼴). 하나씩 심고 겨눈
# 시험만 돌린 뒤 원본 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — cp 와 같은 꼴, 끝에 sha·status 대조).
# SIGINT·SIGTERM 이 와도 되쓴다(파이썬 finally — TERM 은 KeyboardInterrupt 로 바꾼다).
# 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-RX1a.sh [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 0 아닌 종료이고 빨개져야 할
# 노드가 전부 FAILED 로 찍힘(lint 층은 BROKEN 과 계약 이름). 분모 27(P1~P28, P6·P10 비움, P15 는 a·b 둘 — P26 은
# ② 검증 B1 의 쓰기 앞 상태 문, P27 은 ③ S3 의 외톨이 failed 문, P28 은 ③ 검증 B2 의 커밋 확인 불가 갈래).
# 업무·보안 층(Postgres·versitygw 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 잡음으로 세지 않는다.
# 보안 층의 S16(실제 저장소)은 RUNBUNDLE_S3_* 가 있을 때만 돈다(section4-RX1a.sh 가 .env 에서 넘긴다).
# 끝 줄 PLANTED=<잡음>/<심음>, 앞 줄 P0=·FINGERPRINT=. 산출물: RX1A_OUT(기본 워크트리 곁의 RX1a.out)/planted/.
# 공급사를 부르지 않는다(OPENAI·ANTHROPIC 키를 지운 환경). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${RX1A_OUT:-$(cd "$ROOT/.." && pwd)/RX1a.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def _term(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, _term)


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def append(extra: str) -> Callable[[str], str | None]:
    return lambda text: text + extra


R = Path("esgapi/runbundle")
IMPORT = R / "service/actions/import_.py"
EXPORT = R / "service/actions/export.py"
BUNDLE = R / "calc/bundle.py"
IDMAP = R / "calc/idmap.py"
GATE = R / "calc/gate.py"
INIT = R / "__init__.py"
RUNSEL = Path("esgapi/runs/service/selectors/bundle.py")
LLMSEL = Path("esgapi/core/service/selectors/llm_logs.py")

T = "esgapi/runbundle/tests/"
TIMP = T + "service/actions/test_import_.py"
TEXP = T + "service/actions/test_export.py"
TZIP = T + "service/actions/test_import_zip.py"
TBUN = T + "calc/test_bundle.py"
TMAP = T + "calc/test_idmap.py"
TGATE = T + "calc/test_gate.py"
TRSEL = "esgapi/runs/tests/service/selectors/test_bundle.py"
TSTAT = "esgapi/core/tests/isolation/test_static_rules.py"
SEC = "tests/security/test_run_bundles.py"
S7 = TIMP + "::test_a_round_trip_reads_the_same"
S9 = TIMP + "::test_a_bundle_goes_in_once_per_company"
S9T = TIMP + "::test_two_imports_at_once_let_one_in"
S10 = TIMP + "::test_times_of_table_t_come_back_and_the_rest_are_now"
S11 = TIMP + "::test_a_failure_before_the_puts_leaves_no_rows_and_no_objects"
S13 = TIMP + "::test_the_executor_sees_the_same_object"
S18 = TIMP + "::test_resuming_an_imported_failed_run_is_already_resumed"
S15X = SEC + "::test_export_carries_only_that_companys_rows"
S15I = SEC + "::test_import_commits_as_the_app_role_without_delete"
S16 = SEC + "::test_a_round_trip_through_the_real_storage"
S16_ON = all(os.environ.get(f"RUNBUNDLE_S3_{name}") for name in ("ENDPOINT", "BUCKET", "REGION", "ACCESS_KEY", "SECRET_KEY"))

PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)
LINT = ("lint", ["uv", "run", "--frozen", "lint-imports"], False)

RESUMED = '            "resumed_from_run_id": None if resumed_old is None else ids.run_id(resumed_old),\n'
PUTS = "            putting = True\n            _put_all(store, company_id, puts, blobs, uploaded)\n"
DOCS = "                document_times = _insert_documents(bundle, company_id, user_id, document_map, puts)\n"

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", "넣기가 sourceCompanyId 로 씀",
     [(IMPORT, swap("    bundle, blobs = read_bundle(path, max_bytes)\n",
                    "    bundle, blobs = read_bundle(path, max_bytes)\n    company_id = bundle.source_company_id\n"))],
     [(BUSINESS, [TIMP], {S7}), (SECURITY, [SEC], {S15I})]),
    ("P2", "created_by_user_id 를 싣고 그대로(싣지 않는 칸·사람 칸에서 빼고 넣기의 덮어쓰기를 지움)",
     [(BUNDLE, swap('            "created_by_user_id",\n', "")),
      (BUNDLE, swap('frozenset({"company_id", "created_by_user_id", "uploaded_by",', 'frozenset({"company_id", "uploaded_by",')),
      (IMPORT, swap('            "created_by_user_id": user_id,\n', ""))],
     [(PURE, [TBUN], {TBUN + "::test_a_wrong_header_is_refused[person_carried]"}), (BUSINESS, [TIMP], {S7})]),
    ("P3", "파일 키를 옛 키(보낸 회사·옛 실행)로",
     [(IMPORT, swap("key = file_key(company_id=company_id, run_id=new,", "key = file_key(company_id=bundle.source_company_id, run_id=old,"))],
     [(BUSINESS, [TIMP], {S7, S13})] + ([(SECURITY, [SEC], {S16})] if S16_ON else [])),
    ("P4", "실행을 옛 id 내림으로 넣음",
     [(IDMAP, swap('    return sorted(int(str(row["oldId"])) for row in rows)\n',
                   '    return sorted((int(str(row["oldId"])) for row in rows), reverse=True)\n'))],
     [(PURE, [TMAP], {TMAP + "::test_runs_go_in_old_id_ascending"}), (BUSINESS, [TIMP], {S7})]),
    ("P5", "resumed_from_run_id 다시 쓰기 지움",
     [(IMPORT, swap(RESUMED, '            "resumed_from_run_id": resumed_old,\n'))],
     [(BUSINESS, [TIMP], {S7, S18})]),
    ("P7", "versions aiSettingId 그대로",
     [(IMPORT, swap('rewrite_versions(rewritten.versions, ids)', 'rewritten.versions'))],
     [(BUSINESS, [TIMP], {S7})]),
    ("P8", "blob 묶기 끔(같은 바이트를 항목마다 다시 씀)",
     [(EXPORT, swap("            for sha in sorted(blobs):\n", "            for sha in [*sorted(blobs), *sorted(blobs)]:\n"))],
     [(BUSINESS, [TIMP], {S7})]),
    ("P9", "blob sha 대조 지움",
     [(IMPORT, swap("if len(data) != blob.size or hashlib.sha256(data).hexdigest() != blob.sha256:", "if len(data) != blob.size:"))],
     [(PURE, [TZIP], {TZIP + "::test_bytes_that_differ_from_the_header_are_refused"})]),
    ("P11", "문 ⓑ 지움(모르는 흐름을 지나감)",
     [(GATE, swap('            raise Refused(f"실행 {old} 의 흐름을 받는 쪽이 모른다") from None\n', "            continue\n"))],
     [(PURE, [TGATE], {TGATE + "::test_unknown_flows_shapes_and_steps_are_refused[flow]"})]),
    ("P12", "문 ⓒ 지움(받는 쪽이 모르는 칸)",
     [(GATE, swap("        if not carried <= set(columns):\n", "        if False:\n"))],
     [(PURE, [TGATE], {TGATE + "::test_columns"})]),
    ("P13", "Q4 앞 조회 지움",
     [(IMPORT, swap("            if bundle_selectors.taken_keys(company_id=company_id, keys=keys):\n", "            if False:\n"))],
     [(BUSINESS, [TIMP], {S9})]),
    ("P14", "LLM 기록 읽기에서 회사 거름 뺌",
     [(LLMSEL, swap("LlmCallLogRow.for_company(company_id).filter(run_id__in=run_ids)", "LlmCallLogRow.unscoped.filter(run_id__in=run_ids)"))],
     [(SECURITY, [SEC], {S15X})]),
    ("P15a", "문서 etag 를 묶음 값으로",
     [(IMPORT, swap("            etag=None,\n", '            etag=str(row["etag"]),\n'))],
     [(BUSINESS, [TIMP], {S13})]),
    ("P15b", "set_imported_etag 지움",
     [(IMPORT, swap("            document_services.set_imported_etag(company_id=company_id, document_id=item.document_id, etag=result.etag)\n",
                    "            pass\n"))],
     [(BUSINESS, [TIMP], {S13})]),
    ("P16", "zip 목록 밖 항목 허용",
     [(BUNDLE, swap("    if set(names) != expected:\n", "    if not expected <= set(names):\n"))],
     [(PURE, [TBUN, TZIP], {TBUN + "::test_zip_members_outside_the_list_are_refused[outside]",
                            TZIP + "::test_members_outside_the_list_are_refused[outside]"})]),
    ("P17", "NaN 받음",
     [(BUNDLE, swap("json.loads(data.decode(), parse_constant=_refuse_constant)", "json.loads(data.decode())"))],
     [(PURE, [TZIP], {TZIP + "::test_json_constants_are_refused[NaN]"})]),
    ("P18", "표 T 되돌리기 끔(실행)",
     [(IMPORT, swap('            bundle_services.restore_times(company_id=company_id, table="run_runs", times=run_times)\n', ""))],
     [(BUSINESS, [TIMP], {S10})]),
    ("P19", "runbundle 에 import esgapi.greenwash",
     [(INIT, append("\nimport esgapi.greenwash  # noqa: E402,F401  심은 파손\n"))],
     [(LINT, [], {"LINT:runbundle-knows-no-module"})]),
    ("P20", "직접 고른 failed 실행 허용",
     [(EXPORT, swap('        if known[run_id].status != "done":\n', "        if known[run_id].status not in CLOSURE_STATUSES:\n"))],
     [(BUSINESS, [TEXP], {TEXP + "::test_a_directly_picked_run_must_be_done[failed]"})]),
    ("P21", "people_of 확인 지움",
     [(IMPORT, swap("    if user_id not in people_of(company_id, {user_id}):\n", "    if False:\n"))],
     [(BUSINESS, [TIMP], {TIMP + "::test_people_and_companies_are_checked[other_user]",
                          TIMP + "::test_people_and_companies_are_checked[missing_user]"})]),
    ("P22", "bundle_rows 의 실행 문을 RunRow.unscoped 로",
     [(RUNSEL, swap("    return RunRow.for_company(company_id)\n", "    return RunRow.unscoped.all()\n"))],
     [(PURE, [TSTAT], {TSTAT + "::test_product_code_does_not_use_unscoped"}),
      (BUSINESS, [TRSEL], {TRSEL + "::test_the_rows_of_that_companys_runs"}),
      (SECURITY, [SEC], {S15X})]),
    ("P23", "advisory 잠금 지움",
     [(IMPORT, swap("            _pg.lock_bundle(company_id, bundle.bundle_id)\n", ""))],
     [(BUSINESS, [TIMP], {S9T})]),
    ("P24", "put 을 ④ 앞으로 옮김(문서 행 바로 뒤)",
     [(IMPORT, swap(PUTS, "")), (IMPORT, swap(DOCS, DOCS + PUTS.replace("            ", "                ")))],
     [(BUSINESS, [TIMP], {S11})]),
    ("P26", "넣기 문에서 실행 상태 검사를 지나감(queued·processing 도 넣음)",
     [(GATE, swap("        if row.get(\"status\") not in FINISHED:\n", "        if False:\n"))],
     [(PURE, [TGATE], {TGATE + "::test_unfinished_runs_are_refused[queued]"}),
      (BUSINESS, [TIMP], {TIMP + "::test_an_unfinished_run_in_the_bundle_is_refused[queued]"})]),
    ("P27", "넣기 문에서 외톨이 failed(묶음 안 done 후손 없음) 검사를 지나감",
     [(GATE, swap('        if row["status"] == "failed" and not _has_done_descendant(old, runs, children):\n', "        if False:\n"))],
     [(PURE, [TGATE], {TGATE + "::test_a_lonely_failed_run_is_refused[failed_alone]"})]),
    ("P28", "커밋 단계 다시 보기 실패를 False(행 되돌림·지워도 됨)로",
     [(IMPORT, swap("    except Exception:  # 다시 보기 실패 = 모름(아래에서 「확인 불가 키(지우지 말 것)」)\n        return None\n",
                    "    except Exception:  # 다시 보기 실패 = 모름(아래에서 「확인 불가 키(지우지 말 것)」)\n        return False\n"))],
     [(BUSINESS, [TIMP], {TIMP + "::test_an_ambiguous_commit_that_cannot_be_rechecked_is_marked_do_not_delete"})]),
    ("P25", "failed 앞 실행에서만 resumed_from 다시 쓰기 지움",
     [(IMPORT, swap(RESUMED, '            "resumed_from_run_id": None if resumed_old is None else '
                             '(resumed_old if runs[resumed_old]["status"] == "failed" else ids.run_id(resumed_old)),\n'))],
     [(BUSINESS, [TIMP], {S18})]),
]
PLANTS = [p for p in PLANTS if ONLY is None or p[0] in ONLY]
EXCEPTION = re.compile(r"UnscopedQueryError")  # 회사 경계 심음(P14·P22)은 단언으로 빨개져야 한다
GUARDED = {"P14", "P22"}


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str, str]:
    _name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        env.pop(name, None)
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    if layer is LINT and "BROKEN" in text and "runbundle" in text:
        failed.add("LINT:runbundle-knows-no-module")
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last, text


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[3]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _failed, last, _ = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, checks) -> bool | None:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                return False
            f.write_text(new, encoding="utf-8")
        hit_all, skipped = True, False
        for layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                skipped = True
                continue
            code, failed, last, text = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            if number in GUARDED and layer[0] != "순수" and EXCEPTION.search(text):
                print(f"{label} 예외로 빨강(무효 — 단언으로 빨개져야 한다)")
                hit = False
            hit_all = hit_all and hit
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - failed)} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        return None if skipped and hit_all else hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
try:
    for number, what, edits, checks in PLANTS:
        planted += 1
        result = plant_and_check(number, what, edits, checks)
        caught += 1 if result is True else 0
        print(f"{number} => {'잡음' if result else '안 돌림' if result is None else '못 잡음'}")
except KeyboardInterrupt:
    print("멈춤(INT·TERM) — 심은 파일은 되썼다")
same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
