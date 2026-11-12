"""문서 파서 서비스. 내부 HTTP 로만 불린다. DB 에 닿지 않고, 저장소의 접근 키도 갖지 않는다.

`POST /parse` 는 본문이 PDF 바이트(`Content-Type: application/pdf`)인 약속 하나뿐이다. `docparse/`(pdfium 엔진)로
분해해 `{"document": <document.json>, "charPlaces": <char-places.json>}` 를 돌려준다. 둘 다 스키마로 검사한 뒤에만
내보낸다. 그 밖의 Content-Type 은 415 다. 원본의 주소를 받아 파서가 내려받던 옛 약속(`application/json`)은 걷었다
(밴드 PX, 2026-10-16. 아무 http(s) 를 내려받는 길이라 SSRF 였고, 부르는 쪽이 0 이었다).

상태 코드의 약속: 4xx = 이 입력은 다시 해도 안 된다, 5xx = 다시 해 볼 만하다(밴드 PX 에서 결함 D4 로 맞춤).

| 상태 | code | 갈래 |
|---:|---|---|
| 413 | `too_large`·`too_many_pages` | 본문 크기·쪽 수 상한 |
| 415 | `unsupported_media_type` | `application/pdf` 가 아님 |
| 422 | `empty_body`·`bad_file_name`·`bad_layout`·`bad_charts`·`not_a_pdf`·`password_protected` | 입력이 틀림 |
| 422 | `parse_timeout`·`parse_failed`·`output_schema_invalid` | 같은 바이트면 늘 같은 실패(결정적) |
| 500 | `worker_died` | 자식이 답 없이 죽음(메모리 따위, 잠깐의 문제일 수 있음) |
| 503 | `busy` | 줄이 참 |

쿼리 `layout`(분해 판, `1`·`2`, 없으면 1)만 분해 갈래를 고른다(밴드 TRD1). 그 밖의 값이나 두 번 오면
422 `bad_layout` 이다. 다른 모르는 쿼리는 지금처럼 무시한다. 판 1 의 산출은 쿼리가 없을 때와 바이트까지 같다.

쿼리 `charts=1`(밴드 CHL1)은 판 2 에서만 도표 라벨을 셋째 키 `chartLabels`(`schemas/chart-labels.schema.json`)로
더 싣는다. 같은 자식이 같은 열린 PDF 로 낸다. `1` 밖의 값·두 번·판 2 가 아닌 요청(layout 쿼리가 없으면 판 1)은 422
`bad_charts` 다. 쿼리가 없으면 봉투는 키 둘 그대로이고 바이트도 같다.

분해 한 건은 **자식 프로세스 하나**에서 돈다(밴드 PX). 서비스 프로세스는 pdfium 을 열지 않는다. 자식을 띄우고
기다리는 것은 일꾼이 하나뿐인 실행기(`_PARSE_EXECUTOR`)라 한 번에 한 건이다. 차례는 이벤트 루프에서 기다리므로 분해가
돌거나 요청이 쌓여 있어도 `/healthz` 는 바로 답한다.

상한(결함 D4. 넷 다 환경 변수, 기본값과 근거는 README 「상한」):
- `MAX_SOURCE_BYTES` 본문 크기 → 413 `too_large`
- `MAX_PAGES` 쪽 수 → 413 `too_many_pages`(여는 자리에서 세고 분해 전에 거절)
- `MAX_QUEUE` 기다리는 요청 수(도는 하나 밖) → 503 `busy`(줄을 서지 않고 바로)
- `PARSE_TIMEOUT_SECONDS` 자식 한 건의 시간 → 자식을 죽이고 422 `parse_timeout`
자식이 답 없이 죽으면(메모리로 죽임을 당함 따위) 500 `worker_died` 다.
"""

import asyncio
import contextlib
import io
import json
import multiprocessing
import os
import sys
import tempfile
import threading
import traceback
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from jsonschema import Draft202012Validator

from docparse.config import CHARTS_SCHEMA_PATH, PLACES_SCHEMA_PATH, SCHEMA_PATH
from docparse.document import label_charts, parse_opened_places
from docparse.engine import PdfOpenError, open_pdf


def _positive(name: str, default: str, kind: type[int] | type[float] = int):
    """설정은 환경 변수로만. 0 이하나 숫자가 아닌 값이면 뜨지 않는다(조용히 상한 없음이 되지 않게)."""
    value = kind(os.environ.get(name, default))
    if not value > 0:
        raise ValueError(f"{name} 은 0보다 커야 한다: {value}")
    return value


MAX_SOURCE_BYTES = _positive("MAX_SOURCE_BYTES", str(50 * 1024 * 1024))
MAX_PAGES = _positive("MAX_PAGES", "1000")
MAX_QUEUE = _positive("MAX_QUEUE", "8")
PARSE_TIMEOUT_SECONDS = _positive("PARSE_TIMEOUT_SECONDS", "180", float)

app = FastAPI(title="esg-parser")

# 산출 스키마의 검사기는 모듈을 읽을 때 한 번 짓는다(밴드 PX). forkserver 가 이 모듈을 미리 읽어 두므로 자식마다 다시
# 짓지 않는다. docparse 의 validate·validate_places 는 부를 때마다 파일을 읽고 검사기를 지어서 쓰지 않는다(CLI 가 쓴다).
_DOCUMENT_VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
_PLACES_VALIDATOR = Draft202012Validator(json.loads(PLACES_SCHEMA_PATH.read_text(encoding="utf-8")))
_CHARTS_VALIDATOR = Draft202012Validator(json.loads(CHARTS_SCHEMA_PATH.read_text(encoding="utf-8")))


def schema_errors(validator: Draft202012Validator, value: dict) -> list[str]:
    """스키마 위반 메시지 목록(없으면 빈 목록). 글의 꼴은 docparse 의 validate 와 같다."""
    return [f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in validator.iter_errors(value)]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    # async 다: 스레드 풀을 거치지 않으므로 풀이 차 있어도 답한다.
    return {"status": "ok"}


@app.post("/parse")
async def parse(request: Request) -> Response:
    # 상태 코드의 약속: 4xx = 이 입력은 다시 해도 안 된다(부르는 쪽이 재시도하지 않는다),
    #                  5xx = 잠깐의 문제일 수 있다(부르는 쪽이 다시 시도한다).
    kind = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if kind == "application/pdf":
        return await parse_pdf_body(request)
    raise reject(415, "unsupported_media_type", "Content-Type 은 application/pdf 여야 한다")


# ── PDF 바이트 → {document, charPlaces} (docparse, pdfium) ─────────────────────

DEFAULT_FILE_NAME = "upload.pdf"
MAX_FILE_NAME_CHARS = 255
DEFAULT_LAYOUT = 1
LAYOUT_VALUES = {b"1": 1, b"2": 2}  # docparse.document.LAYOUTS 와 같다
CHARTS_LAYOUT = 2  # 도표 라벨을 붙이는 판(밴드 CHL1)

# 일꾼이 하나다: 분해는 한 번에 한 건이다. 일꾼 스레드는 자식 프로세스를 띄우고 끝나기를 기다리기만 한다
# (pdfium 을 여는 것도 닫는 것도 자식 안이다). 차례를 기다리는 요청은 이 실행기의 줄에 서고, 기다리는 동안 스레드를
# 쥐지 않는다. 줄의 길이는 `_take_slot` 이 센다.
_PARSE_WORKERS = 1
_PARSE_EXECUTOR = ThreadPoolExecutor(max_workers=_PARSE_WORKERS, thread_name_prefix="pdfium")
_SLOTS_LOCK = threading.Lock()
_slots_taken = 0  # 도는 것 + 줄에 선 것

# 자식은 forkserver 로 띄운다: 이 모듈을 미리 읽어 둔 서버 프로세스(스레드 없음)를 갈라 쓰므로 건마다 import 를 다시
# 하지 않는다(spawn 은 건마다 ~250ms, forkserver 는 ~4ms. 2026-10-16 호스트에서 잼). 스레드가 도는 서비스 프로세스를
# 그대로 가르는 fork 는 쓰지 않는다.
_CHILDREN = multiprocessing.get_context("forkserver")
_CHILDREN.set_forkserver_preload(["app"])


class Rejected(Exception):
    """분해 스레드에서 갈래 있는 거절을 이벤트 루프 쪽으로 넘긴다."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status, self.code, self.message = status, code, message


def reject(status: int, code: str, message: str) -> HTTPException:
    """거절의 본문은 늘 {"detail": {"code", "message"}} 다. 문서의 글과 트레이스백은 싣지 않는다."""
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def file_name_from(raw_query: bytes) -> str:
    """쿼리의 `file_name` 을 **날 쿼리 문자열에서** 꺼내 UTF-8 로 푼다. 없으면 기본 이름.

    프레임워크가 미리 푼 값을 쓰지 않는다: 그것은 깨진 바이트를 U+FFFD 로 바꿔 버려서 거절할 수 없다.
    `+` 는 공백으로 읽는다(쿼리의 관례. 더하기 글자는 `%2B` 로 온다).
    """
    name = None
    for pair in raw_query.split(b"&"):
        key, _, value = pair.partition(b"=")
        if urllib.parse.unquote_to_bytes(key.replace(b"+", b" ")) == b"file_name":
            name = value
    if name is None:
        return DEFAULT_FILE_NAME
    try:
        text = urllib.parse.unquote_to_bytes(name.replace(b"+", b" ")).decode("utf-8")
    except UnicodeDecodeError as err:
        raise reject(422, "bad_file_name", "file_name 을 UTF-8 로 풀 수 없다") from err
    if not text or len(text) > MAX_FILE_NAME_CHARS:
        raise reject(422, "bad_file_name", f"file_name 은 1~{MAX_FILE_NAME_CHARS}자여야 한다")
    if "/" in text or "\\" in text or ".." in text or any(unicodedata.category(c) == "Cc" for c in text):
        raise reject(422, "bad_file_name", "file_name 에 경로 구분자, `..`, 제어 글자를 쓸 수 없다")
    return text


def layout_from(raw_query: bytes) -> int:
    """쿼리의 `layout`(분해 판)을 **날 쿼리 문자열에서** 꺼낸다(`file_name_from` 과 같은 읽기). 없으면 1.

    `1`·`2` 밖이거나 두 번 오면 422 `bad_layout`.
    """
    found = []
    for pair in raw_query.split(b"&"):
        key, _, value = pair.partition(b"=")
        if urllib.parse.unquote_to_bytes(key.replace(b"+", b" ")) == b"layout":
            found.append(urllib.parse.unquote_to_bytes(value.replace(b"+", b" ")))
    if not found:
        return DEFAULT_LAYOUT
    if len(found) > 1 or found[0] not in LAYOUT_VALUES:
        raise reject(422, "bad_layout", "layout 은 한 번, 1 또는 2 여야 한다")
    return LAYOUT_VALUES[found[0]]


def charts_from(raw_query: bytes, layout: int) -> bool:
    """쿼리의 `charts`(도표 라벨)를 날 쿼리 문자열에서 꺼낸다(`layout_from` 과 같은 읽기). 없으면 거짓.

    `1` 밖이거나 두 번 오거나 판이 2 가 아니면 422 `bad_charts`.
    """
    found = []
    for pair in raw_query.split(b"&"):
        key, _, value = pair.partition(b"=")
        if urllib.parse.unquote_to_bytes(key.replace(b"+", b" ")) == b"charts":
            found.append(urllib.parse.unquote_to_bytes(value.replace(b"+", b" ")))
    if not found:
        return False
    if len(found) > 1 or found[0] != b"1":
        raise reject(422, "bad_charts", "charts 는 한 번, 1 이어야 한다")
    if layout != CHARTS_LAYOUT:
        raise reject(422, "bad_charts", f"charts 는 layout={CHARTS_LAYOUT} 에만 쓴다")
    return True


async def read_limited(request: Request) -> bytes:
    """본문을 읽으면서 크기 상한을 넘는 순간 끊는다(다 받은 뒤에 재지 않는다)."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_SOURCE_BYTES:
        raise reject(413, "too_large", f"본문이 {MAX_SOURCE_BYTES} 바이트를 넘는다")
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_SOURCE_BYTES:
            raise reject(413, "too_large", f"본문이 {MAX_SOURCE_BYTES} 바이트를 넘는다")
        chunks.append(chunk)
    return b"".join(chunks)


def _take_slot() -> None:
    """도는 것 하나와 기다리는 것 `MAX_QUEUE` 개까지 받는다. 그 위는 줄을 세우지 않고 503 `busy` 다."""
    global _slots_taken
    with _SLOTS_LOCK:
        if _slots_taken >= _PARSE_WORKERS + MAX_QUEUE:
            raise reject(503, "busy", f"분해를 기다리는 요청이 {MAX_QUEUE}건을 넘는다. 잠시 뒤 다시 한다")
        _slots_taken += 1


def _give_slot(_job: object = None) -> None:
    global _slots_taken
    with _SLOTS_LOCK:
        _slots_taken -= 1


async def parse_pdf_body(request: Request) -> Response:
    file_name = file_name_from(request.scope.get("query_string", b""))
    layout = layout_from(request.scope.get("query_string", b""))
    charts = charts_from(request.scope.get("query_string", b""), layout)
    # 판은 기본이 아닐 때만, 도표 라벨은 참일 때만 안쪽으로 넘긴다: 기본 길의 부르는 꼴(자식의 target·decompose 의
    # 인자)은 그대로다.
    extra: tuple[Any, ...] = (layout, True) if charts else () if layout == DEFAULT_LAYOUT else (layout,)
    _take_slot()  # 본문을 다 받기 전에 거절한다
    handed = False
    try:
        data = await read_limited(request)
        if not data:
            raise reject(422, "empty_body", "본문이 비었다")
        # 자리는 실행기의 일이 끝날 때 돌려준다: 부르는 쪽이 끊어 이 요청이 거둬져도 이미 도는 자식은 끝까지
        # (또는 시간 상한까지) 돌므로 그동안 자리를 쥔다. 아직 줄에 선 일은 거둬질 때 줄에서 빠지고 자리를 돌려준다.
        job = _PARSE_EXECUTOR.submit(run_isolated, data, file_name, *extra)
        job.add_done_callback(_give_slot)
        handed = True
        try:
            body = await asyncio.wrap_future(job)
        except Rejected as err:
            raise reject(err.status, err.code, err.message) from None
    finally:
        if not handed:
            _give_slot()
    return Response(content=body, media_type="application/json")


def run_isolated(data: bytes, file_name: str, layout: int = DEFAULT_LAYOUT, charts: bool = False) -> bytes:
    """일꾼 스레드에서 돈다. 자식 하나를 띄워 분해를 맡기고, `PARSE_TIMEOUT_SECONDS` 안에 답이 없으면 죽인다."""
    receive, send = _CHILDREN.Pipe(duplex=False)
    more = (True,) if charts else ()  # 도표 라벨은 참일 때만 넘긴다(기본 길의 인자 꼴 그대로)
    child = _CHILDREN.Process(
        target=_child_main,
        args=(send, CHILD_TARGET, data, file_name, MAX_PAGES, layout, *more),
        name="parse",
        daemon=True,
    )
    try:
        child.start()
        send.close()
        if not receive.poll(PARSE_TIMEOUT_SECONDS):
            child.kill()
            print(f"parse: {PARSE_TIMEOUT_SECONDS:g}초 안에 끝나지 않아 자식을 죽였다", file=sys.stderr)
            raise Rejected(422, "parse_timeout", f"분해가 {PARSE_TIMEOUT_SECONDS:g}초 안에 끝나지 않았다")
        try:
            outcome, log = receive.recv()
        except (EOFError, OSError):
            outcome, log = None, ""
    finally:
        receive.close()
        child.join(5)
        if child.is_alive():
            child.kill()
            child.join()
    if log:
        sys.stderr.write(log)
    if outcome is None or outcome[0] == "died":
        why = f"exitcode {child.exitcode}" if outcome is None else outcome[1]
        print(f"parse: 자식이 끝내지 못했다 ({why})", file=sys.stderr)
        raise Rejected(500, "worker_died", "분해하던 프로세스가 죽었다")
    if outcome[0] == "rejected":
        raise Rejected(*outcome[1:])
    return outcome[1]


def _child_main(
    conn, target, data: bytes, file_name: str, max_pages: int, layout: int = DEFAULT_LAYOUT, charts: bool = False
) -> None:
    """자식 프로세스의 몸. 결과(또는 갈래 있는 거절)와 그동안 stderr 에 적은 기록을 부모에게 한 번 보낸다.

    판(`layout`)은 기본이 아닐 때만, 도표 라벨(`charts`)은 참일 때만 target 에 넘긴다(기본 판의 target 은 인자 셋
    그대로).

    기록은 부모가 자기 stderr 로 낸다(자식의 stderr 는 forkserver 를 띄운 때의 것이라 부모의 것과 다를 수 있다).
    """
    log = io.StringIO()
    with contextlib.redirect_stderr(log):
        try:
            extra = (layout, True) if charts else () if layout == DEFAULT_LAYOUT else (layout,)
            outcome = ("ok", target(data, file_name, max_pages, *extra))
        except Rejected as err:
            outcome = ("rejected", err.status, err.code, err.message)
        except BaseException as err:  # 메모리 부족 따위. 글은 싣지 않고 종류만
            outcome = ("died", type(err).__name__)
    conn.send((outcome, log.getvalue()))
    conn.close()


def decompose(path: Path, opened, layout: int = DEFAULT_LAYOUT):
    """이미 연 PDF(`opened`, 파일은 `path`) 하나를 (문서 모델, 글자 자리)로. 다시 열지 않는다.

    표 전략은 `auto`, 겹쳐 그린 글 거르기는 끔으로 고정이고 HTTP 로 열지 않는다. 판(`layout`)만 쿼리로 고른다.
    """
    if layout != DEFAULT_LAYOUT:
        return parse_opened_places(opened, path, strategy="auto", dedupe_overdrawn=False, layout=layout)
    return parse_opened_places(opened, path, strategy="auto", dedupe_overdrawn=False)


def decompose_to_json(
    data: bytes, file_name: str, max_pages: int, layout: int = DEFAULT_LAYOUT, charts: bool = False
) -> bytes:
    """자식 프로세스에서 돈다. 받은 바이트를 임시 파일로 써서 분해하고, 스키마로 검사한 JSON 바이트를 돌려준다.

    임시 파일의 이름은 고정이다(부르는 쪽이 준 이름을 파일 시스템에 쓰지 않는다).
    `source.file_name` 은 분해 뒤에 적는다. 쪽 수는 암호를 확인하며 여는 자리에서 세고, 넘으면 분해하지 않는다.
    PDF 는 한 번만 연다: 암호·쪽 수를 본 문서를 그대로 분해에 넘기고 끝나면 닫는다(밴드 PX2).
    `charts` 가 참이면 분해한 같은 열린 문서로 도표 라벨을 내 셋째 키 `chartLabels` 로 싣는다(밴드 CHL1).
    """
    try:
        with tempfile.TemporaryDirectory(prefix="parse-") as folder:
            path = Path(folder) / DEFAULT_FILE_NAME
            path.write_bytes(data)
            try:
                opened = open_pdf(path)
            except PdfOpenError:
                raise Rejected(422, "not_a_pdf", "PDF 로 열 수 없다") from None
            with opened:
                if opened.needs_pass:
                    raise Rejected(422, "password_protected", "암호가 걸린 PDF 다")
                pages = len(opened)
                if pages > max_pages:
                    raise Rejected(413, "too_many_pages", f"쪽 수({pages})가 상한 {max_pages} 를 넘는다")
                if layout == DEFAULT_LAYOUT:
                    document, places = decompose(path, opened)
                else:
                    document, places = decompose(path, opened, layout)
                labels = label_charts(opened, document) if charts else None
        if places is None:
            raise Rejected(422, "output_schema_invalid", "분해기가 글자 자리를 내지 않았다")
        # 두 산출은 같은 source 를 싣는다. 이름은 부르는 쪽이 준 것으로 적는다.
        # 해시는 분해기가 받은 바이트에서 이미 냈다.
        outputs = (document, places) if labels is None else (document, places, labels)
        for output in outputs:
            output["source"]["file_name"] = file_name
        errors = schema_errors(_DOCUMENT_VALIDATOR, document) + schema_errors(_PLACES_VALIDATOR, places)
        if labels is not None:
            errors += schema_errors(_CHARTS_VALIDATOR, labels)
        if errors:
            # 같은 입력이면 늘 같으므로 422 지만 코드의 결함이다: 기록에 줄을 남긴다.
            print(f"parse: 스키마에 맞지 않는 산출 {len(errors)}건 (내보내지 않는다)", file=sys.stderr)
            raise Rejected(422, "output_schema_invalid", f"분해 산출이 스키마에 맞지 않는다 ({len(errors)}건)")
        envelope = {"document": document, "charPlaces": places}
        if labels is not None:
            envelope["chartLabels"] = labels
        return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (Rejected, MemoryError):
        raise  # 메모리 부족은 잠깐의 문제일 수 있다: 자식이 죽은 것(500 worker_died)으로 간다
    except Exception as err:  # 규칙 안의 어떤 예외든 422 한 갈래로 낸다(같은 바이트면 늘 같다)
        # 기록에는 예외의 종류와 일어난 자리(파일·줄)만 남긴다. 예외의 글에는 문서의 글이 섞일 수 있어 적지 않는다.
        frames = " <- ".join(
            f"{Path(f.filename).name}:{f.lineno} {f.name}"
            for f in reversed(traceback.extract_tb(err.__traceback__)[-6:])
        )
        print(f"parse: 분해 실패 {type(err).__name__} at {frames}", file=sys.stderr)
        raise Rejected(422, "parse_failed", "분해하다 실패했다") from None


# 자식이 부르는 함수. 시험이 바꿔 끼운다(자식에 pickle 해 보내므로 모듈 맨 위의 함수나 그 partial 이어야 한다).
CHILD_TARGET = decompose_to_json
