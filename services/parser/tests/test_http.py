"""`POST /parse`(본문이 PDF 바이트)의 갈래와, 분해가 도는 동안에도 `/healthz` 가 막히지 않는다는 것.

옛 약속(`application/json` 의 `{sourceUrl}`)이 걷혔다는 것은 `services/parser/test_app.py` 가 본다.
여기의 PDF 는 `pdfbuild` 로 짓는다.
"""

import asyncio
import contextlib
import hashlib
import json
import os
import signal
import threading
import time
from functools import partial
from itertools import pairwise
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

import app as parser
from docparse.config import PLACES_SCHEMA_PATH, SCHEMA_PATH

from . import pdfbuild

client = TestClient(parser.app)
PDF = {"content-type": "application/pdf"}


def two_page_pdf():
    doc = pdfbuild.Doc()
    doc.new_page().insert_text((40, 60), "First page 12.5")
    doc.new_page().insert_text((40, 60), "Second page")
    return doc.tobytes()


def detail(response):
    body = response.json()
    assert set(body) == {"detail"} and set(body["detail"]) == {"code", "message"}, body
    return body["detail"]["code"]


# ── 200 ──────────────────────────────────────────────────────────────


def test_pdf_body_returns_document_and_char_places_that_pass_their_schemas():
    data = two_page_pdf()
    response = client.post("/parse", content=data, headers=PDF)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"document", "charPlaces"}
    document, places = body["document"], body["charPlaces"]
    assert [
        e.message
        for e in Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))).iter_errors(document)
    ] == []
    assert [
        e.message
        for e in Draft202012Validator(json.loads(PLACES_SCHEMA_PATH.read_text(encoding="utf-8"))).iter_errors(places)
    ] == []
    assert len(document["pages"]) == 2 and document["source"]["page_count"] == 2
    assert "First page 12.5" in " ".join(b.get("text", "") for b in document["blocks"])
    assert places is not None and places["unit"] == "utf16" and places["containers"]
    # 이름은 기본값, 해시는 받은 바이트의 것. 표 전략은 auto 고정.
    for output in (document, places):
        assert output["source"] == {
            "file_name": "upload.pdf",
            "sha256": hashlib.sha256(data).hexdigest(),
            "page_count": 2,
        }
        assert output["parser"]["table_strategy"] == "auto"
    assert document["parser"]["name"] == "docparse"


def test_the_http_answer_is_what_the_cli_writes(tmp_path):
    """HTTP 의 답은 CLI `parse --places` 가 쓰는 두 파일과 JSON 값으로 같다 (네 문서 골든이 CLI 산출과 견주는 근거)."""
    from docparse.cli import main

    pdf = tmp_path / "same.pdf"
    pdf.write_bytes(two_page_pdf())
    assert main(["parse", str(pdf), "--out", str(tmp_path / "out"), "--places"]) == 0
    body = client.post("/parse?file_name=same.pdf", content=pdf.read_bytes(), headers=PDF).json()
    assert body["document"] == json.loads((tmp_path / "out" / "document.json").read_text(encoding="utf-8"))
    assert body["charPlaces"] == json.loads((tmp_path / "out" / "char-places.json").read_text(encoding="utf-8"))


def test_page_without_text_layer_is_200_not_a_refusal():
    doc = pdfbuild.Doc()
    doc.new_page().draw_rect((40, 40, 90, 70), fill=(1, 0, 0), color=None)
    response = client.post("/parse", content=doc.tobytes(), headers=PDF)
    assert response.status_code == 200
    assert [p["text_layer"] for p in response.json()["document"]["pages"]] == ["none"]


@pytest.mark.parametrize(
    "query, expected",
    [
        ("file_name=report.pdf", "report.pdf"),
        (
            "file_name=%EC%A7%80%EC%86%8D%EA%B0%80%EB%8A%A5%20%EB%B3%B4%EA%B3%A0%EC%84%9C.pdf",
            "지속가능 보고서.pdf",
        ),  # UTF-8 percent-encoding
        ("file_name=a+b%2Bc.pdf", "a b+c.pdf"),  # 쿼리의 + 는 공백, 더하기 글자는 %2B
        ("other=1&file_name=x.pdf", "x.pdf"),
        ("other=1", "upload.pdf"),
        ("file_name=" + "%EA%B0%80" * 255, "가" * 255),  # 255자는 푼 뒤의 글자 수다 (바이트로는 765)
    ],
)
def test_file_name_goes_to_source_file_name(query, expected):
    response = client.post(f"/parse?{query}", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 200
    assert response.json()["document"]["source"]["file_name"] == expected
    assert response.json()["charPlaces"]["source"]["file_name"] == expected


# ── 거절의 갈래 ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "query",
    [
        "file_name=..%2Fx.pdf",
        "file_name=../x.pdf",
        "file_name=a%2Fb.pdf",
        "file_name=a%5Cb.pdf",
        "file_name=..",
        "file_name=a..b.pdf",
        "file_name=a%00b.pdf",
        "file_name=a%0Ab.pdf",
        "file_name=a%7Fb.pdf",  # 제어 글자
        "file_name=",
        "file_name=" + "a" * 256,
        "file_name=" + "%EA%B0%80" * 256,  # 빈 이름, 256자
        "file_name=%FF%FE.pdf",
        "file_name=%EC%A7.pdf",  # UTF-8 로 풀 수 없는 바이트
    ],
)
def test_bad_file_name_is_422(query):
    response = client.post(f"/parse?{query}", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 422 and detail(response) == "bad_file_name"


def test_empty_body_is_422():
    response = client.post("/parse", content=b"", headers=PDF)
    assert response.status_code == 422 and detail(response) == "empty_body"


def test_not_a_pdf_is_422():
    response = client.post("/parse", content=b"not a pdf at all", headers=PDF)
    assert response.status_code == 422 and detail(response) == "not_a_pdf"


def test_password_protected_is_422():
    doc = pdfbuild.Doc()
    doc.new_page().insert_text((40, 60), "Secret")
    response = client.post("/parse", content=doc.tobytes(user_pw="user", owner_pw="owner"), headers=PDF)
    assert response.status_code == 422 and detail(response) == "password_protected"


@pytest.mark.parametrize(
    "headers",
    [
        {"content-type": "text/plain"},
        {"content-type": "application/octet-stream"},
        {"content-type": "multipart/form-data; boundary=x"},
    ],
)
def test_other_content_types_are_415(headers):
    response = client.post("/parse", content=two_page_pdf(), headers=headers)
    assert response.status_code == 415 and detail(response) == "unsupported_media_type"


def test_content_type_parameters_and_case_are_ignored():
    response = client.post("/parse", content=two_page_pdf(), headers={"content-type": "Application/PDF; qs=1"})
    assert response.status_code == 200


def test_too_large_is_413_by_declared_length(monkeypatch):
    monkeypatch.setattr(parser, "MAX_SOURCE_BYTES", 100)
    response = client.post("/parse", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 413 and detail(response) == "too_large"


def test_too_large_is_cut_while_reading_when_no_length_is_declared(monkeypatch, tmp_path):
    """길이를 미리 말하지 않고 흘려보내는 본문: 상한을 넘는 순간 끊는다. 뒤의 조각은 읽지 않는다."""
    monkeypatch.setattr(parser, "MAX_SOURCE_BYTES", 100)
    marker = tmp_path / "decomposed"
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(mark_then_decompose, str(marker))}))
    sent = []

    def chunks():
        for i in range(50):
            sent.append(i)
            yield b"x" * 40

    response = client.post("/parse", content=chunks(), headers=PDF)
    assert response.status_code == 413 and detail(response) == "too_large"
    assert "content-length" not in {k.lower() for k in response.request.headers}
    assert not marker.exists()  # 상한을 넘은 본문이 분해기까지 가지 않았다


def test_body_at_the_limit_is_accepted(monkeypatch):
    data = two_page_pdf()
    monkeypatch.setattr(parser, "MAX_SOURCE_BYTES", len(data))
    assert client.post("/parse", content=data, headers=PDF).status_code == 200
    monkeypatch.setattr(parser, "MAX_SOURCE_BYTES", len(data) - 1)
    assert client.post("/parse", content=data, headers=PDF).status_code == 413


def test_output_that_fails_the_schema_is_422_and_not_sent(monkeypatch, capfd):
    """같은 입력이면 늘 같은 산출이라 다시 해도 같다: 4xx. 코드 결함이라 기록(stderr)에 줄을 남긴다."""
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": text_layer_maybe}))
    response = client.post("/parse", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 422 and detail(response) == "output_schema_invalid"
    assert "스키마에 맞지 않는 산출" in capfd.readouterr().err
    assert "First page" not in response.text


def test_char_places_schema_is_checked_too(monkeypatch):
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": unit_bytes}))
    response = client.post("/parse", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 422 and detail(response) == "output_schema_invalid"


def test_missing_char_places_is_422(monkeypatch):
    """`charPlaces` 는 늘 있다. 분해 함수가 자리를 내지 않으면 `null` 을 내보내지 않고 422 다."""
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": no_places}))
    response = client.post("/parse", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 422 and detail(response) == "output_schema_invalid"


def test_exception_inside_the_rules_is_422_without_text_or_traceback(monkeypatch, capfd):
    """분해 규칙 안의 예외는 같은 바이트면 늘 같다: 422(부르는 쪽이 다시 하지 않는다)."""
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": boom}))
    response = client.post("/parse", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 422 and detail(response) == "parse_failed"
    assert (
        "First page" not in response.text and "Traceback" not in response.text and "RuntimeError" not in response.text
    )
    logged = capfd.readouterr().err
    assert "RuntimeError" in logged and "First page" not in logged  # 기록에는 종류와 자리만 (자식의 기록은 부모가 낸다)


def test_no_temporary_file_is_left(monkeypatch, tmp_path):
    temp, log = tmp_path / "temp", tmp_path / "seen.log"
    temp.mkdir()
    watching = in_child({"tempfile.tempdir": str(temp), "decompose": partial(record_path, str(log))})
    monkeypatch.setattr(parser, "CHILD_TARGET", watching)
    assert client.post("/parse?file_name=..%2Fx.pdf", content=two_page_pdf(), headers=PDF).status_code == 422
    assert client.post("/parse?file_name=mine.pdf", content=two_page_pdf(), headers=PDF).status_code == 200
    assert client.post("/parse", content=b"not a pdf", headers=PDF).status_code == 422
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"tempfile.tempdir": str(temp), "decompose": divide_by_zero}))
    assert client.post("/parse", content=two_page_pdf(), headers=PDF).status_code == 422
    seen = [tuple(line.split("\t")) for line in log.read_text(encoding="utf-8").splitlines()]
    assert seen == [("upload.pdf", "True", str(temp))]  # 임시 파일의 이름은 부르는 쪽이 준 이름이 아니다
    assert os.listdir(temp) == []


def test_fixed_options_are_not_open_over_http(monkeypatch, tmp_path):
    """표 전략과 겹쳐 그린 글 거르기는 쿼리로 바뀌지 않는다."""
    log = tmp_path / "options.log"
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"parse_opened_places": partial(record_options, str(log))}))
    assert (
        client.post("/parse?strategy=text&dedupe_overdrawn=1", content=two_page_pdf(), headers=PDF).status_code == 200
    )
    assert [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] == [
        {"strategy": "auto", "dedupe_overdrawn": False}
    ]


def test_the_schemas_are_read_once_not_per_parse(monkeypatch):
    """산출 검사기는 모듈을 읽을 때 한 번 짓는다. 분해마다 스키마 파일을 읽거나 검사기를 다시 짓지 않는다.

    자식 안의 일이라 같은 함수를 이 프로세스에서 직접 두 번 부르고, 그동안의 파일 읽기를 센다.
    """
    import docparse.document

    read = []
    real_read_text = Path.read_text

    def counting(self, *args, **kwargs):
        read.append(Path(self).name)
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting)
    for name in ("validate", "validate_places", "load_schema"):
        monkeypatch.setattr(docparse.document, name, lambda *a, **k: pytest.fail("분해마다 스키마를 다시 읽었다"))
    for _ in range(2):
        body = json.loads(parser.decompose_to_json(two_page_pdf(), "x.pdf", 10))
        assert set(body) == {"document", "charPlaces"}
    assert SCHEMA_PATH.name not in read and PLACES_SCHEMA_PATH.name not in read, read


# ── 상한: 쪽 수, 줄, 분해 시간 (결함 D4) ─────────────────────────────


def test_too_many_pages_is_413_before_decomposing(monkeypatch, tmp_path):
    """쪽 수는 이미 여는 자리(암호 확인)에서 센다. 넘으면 분해를 부르지 않고 413 이다. 같은 수는 받는다."""
    marker = tmp_path / "decomposed"
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(mark_then_decompose, str(marker))}))
    monkeypatch.setattr(parser, "MAX_PAGES", 1)
    response = client.post("/parse", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 413 and detail(response) == "too_many_pages"
    assert not marker.exists()
    monkeypatch.setattr(parser, "MAX_PAGES", 2)
    assert client.post("/parse", content=two_page_pdf(), headers=PDF).status_code == 200
    assert marker.exists()


def test_a_full_queue_is_503_busy_and_healthz_still_answers(monkeypatch, tmp_path):
    """도는 것 하나 + 기다리는 것 `MAX_QUEUE` 개까지 받는다. 그 위는 줄을 서지 않고 바로 503 `busy` 다(다시 해 볼 만함)."""
    monkeypatch.setattr(parser, "MAX_QUEUE", 1)
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(sleeping, 0.8, str(tmp_path / "t"))}))

    async def scenario():
        async with asgi() as http:
            first = asyncio.create_task(http.post("/parse", content=two_page_pdf(), headers=PDF))
            await asyncio.sleep(0.2)  # 첫째가 돌고 있을 때
            second = asyncio.create_task(http.post("/parse", content=two_page_pdf(), headers=PDF))
            await asyncio.sleep(0.1)  # 둘째가 줄에 서 있을 때
            started = time.monotonic()
            third = await asyncio.wait_for(http.post("/parse", content=two_page_pdf(), headers=PDF), timeout=2)
            third_took = time.monotonic() - started
            started = time.monotonic()
            health = await asyncio.wait_for(http.get("/healthz"), timeout=2)
            health_took = time.monotonic() - started
            done = [await first, await second]
            after = await http.post("/parse", content=two_page_pdf(), headers=PDF)  # 자리를 돌려받았다
            return third, third_took, health, health_took, done, after

    third, third_took, health, health_took, done, after = run(scenario())
    assert third.status_code == 503 and detail(third) == "busy" and third_took < 0.5, third_took
    assert health.status_code == 200 and health_took < 0.5, health_took
    assert [r.status_code for r in done] == [200, 200]
    assert after.status_code == 200
    assert parser._slots_taken == 0


def test_a_caller_that_hangs_up_keeps_its_slot_until_the_running_child_ends(monkeypatch, tmp_path):
    """부르는 쪽이 끊어 요청이 거둬져도, 이미 도는 자식은 끝까지 돌므로 그동안 줄 자리를 쥔다(검증 B8).

    자리가 하나뿐일 때(기다림 0): 끊은 뒤 곧바로 온 요청은 503 `busy` 이고, 자식이 끝나면 자리를 돌려받아 200 이다.
    """
    monkeypatch.setattr(parser, "MAX_QUEUE", 0)
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(sleeping, 1.0, str(tmp_path / "t"))}))

    async def scenario():
        async with asgi() as http:
            hung_up = asyncio.create_task(http.post("/parse", content=two_page_pdf(), headers=PDF))
            await asyncio.sleep(0.3)  # 자식이 돌고 있을 때 끊는다
            hung_up.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hung_up
            held = parser._slots_taken
            right_after = await http.post("/parse", content=two_page_pdf(), headers=PDF)
            deadline = time.monotonic() + 5
            while parser._slots_taken and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
            later = await http.post("/parse", content=two_page_pdf(), headers=PDF)
            return held, right_after, later

    held, right_after, later = run(scenario())
    assert held == 1  # 끊긴 요청의 자리를 도는 자식이 쥐고 있다
    assert right_after.status_code == 503 and detail(right_after) == "busy"
    assert later.status_code == 200
    assert parser._slots_taken == 0


def test_parse_over_the_time_limit_is_422_and_its_child_is_killed(monkeypatch, tmp_path):
    """분해는 자식 프로세스에서 돌고, `PARSE_TIMEOUT_SECONDS` 를 넘으면 그 자식을 죽이고 422 `parse_timeout` 이다.

    같은 PDF 는 다시 해도 같으므로 4xx 다. 그 뒤에도 서비스는 다음 요청을 받는다.
    """
    pid_file = tmp_path / "pid"
    monkeypatch.setattr(parser, "PARSE_TIMEOUT_SECONDS", 0.5)
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(hang, str(pid_file))}))
    started = time.monotonic()
    response = client.post("/parse", content=two_page_pdf(), headers=PDF)
    took = time.monotonic() - started
    assert response.status_code == 422 and detail(response) == "parse_timeout"
    assert 0.5 <= took < 3.0, took
    pid = int(pid_file.read_text())
    assert pid != os.getpid()
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)  # 죽였고 거두었다
    monkeypatch.setattr(parser, "CHILD_TARGET", parser.decompose_to_json)
    assert client.post("/parse", content=two_page_pdf(), headers=PDF).status_code == 200


def test_a_child_that_dies_is_500_worker_died_and_the_service_lives_on(monkeypatch):
    """자식이 답 없이 죽으면(메모리로 죽임을 당함 따위) 500 `worker_died` 다(잠깐의 문제일 수 있다). 서비스는 그대로다."""
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": die}))
    response = client.post("/parse", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 500 and detail(response) == "worker_died"
    monkeypatch.setattr(parser, "CHILD_TARGET", parser.decompose_to_json)
    assert client.post("/parse", content=two_page_pdf(), headers=PDF).status_code == 200


def test_memory_error_is_500_worker_died_not_a_deterministic_failure(monkeypatch):
    """메모리 부족은 잠깐의 문제일 수 있다: `parse_failed`(422) 로 삼키지 않고 자식이 죽은 것으로 낸다(500 `worker_died`)."""
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": out_of_memory}))
    response = client.post("/parse", content=two_page_pdf(), headers=PDF)
    assert response.status_code == 500 and detail(response) == "worker_died"


def test_the_server_process_never_touches_pdfium(monkeypatch):
    """pdfium 을 여는 것도 분해하는 것도 자식에서만 한다. 부모의 이 함수들이 불리면 실패한다."""
    for name in ("open_pdf", "parse_opened_places", "decompose"):
        monkeypatch.setattr(parser, name, lambda *a, **k: pytest.fail("서비스 프로세스가 pdfium 을 만졌다"))
    assert client.post("/parse", content=two_page_pdf(), headers=PDF).status_code == 200


# ── 한 번에 한 건, 그리고 그동안에도 답하는 것들 ─────────────────────


def run(coroutine):
    return asyncio.run(coroutine)


def asgi():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=parser.app), base_url="http://parser")


def spans(log):
    """`sleeping` 이 적은 (들어감, 나옴, pid) 들. 들어간 차례로."""
    rows = [line.split() for line in log.read_text(encoding="utf-8").splitlines()]
    return sorted((float(a), float(b), int(p)) for a, b, p in rows)


def test_two_requests_never_overlap_inside_the_parser(monkeypatch, tmp_path):
    log = tmp_path / "spans"
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(sleeping, 0.2, str(log))}))

    async def scenario():
        async with asgi() as http:
            return await asyncio.gather(*(http.post("/parse", content=two_page_pdf(), headers=PDF) for _ in range(4)))

    responses = run(scenario())
    assert [r.status_code for r in responses] == [200] * 4
    seen = spans(log)
    assert len(seen) == 4
    # 넷이 들어왔지만 분해 함수 안에는 늘 하나뿐이었다: 다음 것은 앞의 것이 나온 뒤에 들어갔다
    assert all(later[0] >= earlier[1] for earlier, later in pairwise(seen)), seen


def test_each_parse_is_its_own_child_waited_for_on_one_named_thread(monkeypatch, tmp_path):
    """분해 한 건 = 자식 프로세스 하나. 그 자식을 띄우고 기다리는 것은 늘 같은 한 스레드다(이벤트 루프의 스레드도, 공용 스레드 풀도 아니다)."""
    log = tmp_path / "spans"
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(sleeping, 0, str(log))}))
    names = []
    real = parser.run_isolated

    def spy(data, file_name):
        names.append((threading.current_thread().name, threading.current_thread() is threading.main_thread()))
        return real(data, file_name)

    monkeypatch.setattr(parser, "run_isolated", spy)
    for _ in range(3):
        assert client.post("/parse", content=two_page_pdf(), headers=PDF).status_code == 200
    assert len(set(names)) == 1 and names[0][0].startswith("pdfium") and names[0][1] is False
    pids = [pid for _, _, pid in spans(log)]
    assert len(set(pids)) == 3 and os.getpid() not in pids


def test_healthz_answers_while_a_parse_is_running(monkeypatch, tmp_path):
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(sleeping, 1.0, str(tmp_path / "t"))}))

    async def scenario():
        async with asgi() as http:
            parsing = asyncio.create_task(http.post("/parse", content=two_page_pdf(), headers=PDF))
            await asyncio.sleep(0.2)  # 분해가 자식에서 돌고 있을 때
            started = time.monotonic()
            health = await asyncio.wait_for(http.get("/healthz"), timeout=2)
            took = time.monotonic() - started
            return health, took, parsing.done(), await parsing

    health, took, parse_done_first, parsed = run(scenario())
    assert health.status_code == 200 and health.json() == {"status": "ok"}
    assert took < 0.5 and not parse_done_first, took  # 분해가 끝나기를 기다리지 않았다
    assert parsed.status_code == 200


def test_healthz_answers_within_two_seconds_while_fifty_requests_wait(monkeypatch, tmp_path):
    """대기 50건이 쌓인 동안에도 답한다. 기다리는 요청이 공용 스레드 풀(기본 40)을 쥐고 있으면 여기서 줄을 선다.

    가짜 분해는 건마다 0.25초다: 스레드 풀을 쥐고 기다리는 꼴이면 풀 밖에 선 열한 건 뒤에서 2초를 넘긴다.
    줄 상한은 이 시험에서만 넉넉히 연다(기본값이면 50건이 줄에 서지 못하고 503 이다).
    물은 뒤에는 남은 요청을 거둔다(아직 차례가 오지 않은 것은 실행기의 줄에서 빠지고 자리를 돌려준다).
    """
    monkeypatch.setattr(parser, "MAX_QUEUE", 100)
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(sleeping, 0.25, str(tmp_path / "t"))}))

    async def scenario():
        async with asgi() as http:
            waiting = [asyncio.create_task(http.post("/parse", content=two_page_pdf(), headers=PDF)) for _ in range(51)]
            await asyncio.sleep(0.3)
            pending = sum(1 for t in waiting if not t.done())
            started = time.monotonic()
            health = await asyncio.wait_for(http.get("/healthz"), timeout=2)
            took = time.monotonic() - started
            refused_started = time.monotonic()
            refused = await asyncio.wait_for(
                http.post("/parse", json={}), timeout=2
            )  # 분해 앞의 거절(415)도 줄을 서지 않는다
            refused_took = time.monotonic() - refused_started
            still = sum(1 for t in waiting if not t.done())
            for task in waiting:
                task.cancel()
            done = await asyncio.gather(*waiting, return_exceptions=True)
            return pending, still, health, took, refused, refused_took, done

    pending, still, health, took, refused, refused_took, done = run(scenario())
    assert pending >= 49 and still >= 45, (pending, still)  # 물을 때 정말로 쌓여 있었다
    assert health.status_code == 200 and took < 2.0, took
    assert refused.status_code == 415 and refused_took < 2.0, refused_took
    assert all(isinstance(r, asyncio.CancelledError) or r.status_code == 200 for r in done)
    deadline = time.monotonic() + 5
    while parser._slots_taken and time.monotonic() < deadline:
        time.sleep(0.05)
    assert parser._slots_taken == 0  # 거둔 요청과 돌던 것이 자리를 모두 돌려주었다


# ── 자식 프로세스 안에서만 바꿔 끼우는 도우미 ─────────────────────────
# 분해는 자식 프로세스(forkserver)에서 돈다. 부모에서 monkeypatch 한 것은 자식에 닿지 않는다.
# 그래서 시험은 `parser.CHILD_TARGET` 을 `in_child(...)` 로 바꾼다: 자식이 이 모듈을 import 해 `patched_in_child` 를
# 부르고, 자식 안에서만 바꿔 끼운 뒤 진짜 `decompose_to_json` 을 돈다. 바꿔 끼우는 값은 이 모듈의 맨 위 함수
# (또는 그 partial)여야 한다(자식으로 pickle 해 보낸다). 자식이 남기는 것은 파일로 받는다.

REAL_DECOMPOSE = parser.decompose
REAL_PARSE_OPENED_PLACES = parser.parse_opened_places


def patched_in_child(patches, data, file_name, max_pages):
    for dotted, value in patches:
        *path, name = dotted.split(".")
        owner = parser
        for part in path:
            owner = getattr(owner, part)
        setattr(owner, name, value)
    return parser.decompose_to_json(data, file_name, max_pages)


def in_child(patches):
    return partial(patched_in_child, tuple(patches.items()))


def text_layer_maybe(path, opened):
    document, places = REAL_DECOMPOSE(path, opened)
    document["pages"][0]["text_layer"] = "maybe"  # 스키마에 없는 값
    return document, places


def unit_bytes(path, opened):
    document, places = REAL_DECOMPOSE(path, opened)
    places["unit"] = "bytes"
    return document, places


def no_places(path, opened):
    return REAL_DECOMPOSE(path, opened)[0], None


def boom(path, opened):
    raise RuntimeError("First page 12.5 가 든 글")  # 예외의 글에 문서의 글이 섞였다


def divide_by_zero(path, opened):
    return 1 / 0


def mark_then_decompose(marker, path, opened):
    Path(marker).write_text("called", encoding="utf-8")
    return REAL_DECOMPOSE(path, opened)


def record_path(log, path, opened):
    with open(log, "a", encoding="utf-8") as out:
        out.write(f"{Path(path).name}\t{Path(path).is_file()}\t{Path(path).parent.parent}\n")
    return REAL_DECOMPOSE(path, opened)


def record_options(log, doc, path, **options):
    with open(log, "a", encoding="utf-8") as out:
        out.write(json.dumps(options) + "\n")
    return REAL_PARSE_OPENED_PLACES(doc, path, **options)


def sleeping(seconds, log, path, opened):
    """seconds 동안 붙든 뒤 진짜로 분해한다. 들어간 때·나온 때·pid 를 log 에 적는다."""
    entered = time.monotonic()
    time.sleep(seconds)
    result = REAL_DECOMPOSE(path, opened)
    with open(log, "a", encoding="utf-8") as out:
        out.write(f"{entered} {time.monotonic()} {os.getpid()}\n")
    return result


def hang(pid_file, path, opened):
    Path(pid_file).write_text(str(os.getpid()), encoding="utf-8")
    time.sleep(10)  # 시간 상한(시험에서 0.5초)보다 한참 길다. 상한을 끈 심은 파손이 10초 뒤에 200 으로 빨개진다
    return REAL_DECOMPOSE(path, opened)


def out_of_memory(path, opened):
    raise MemoryError


def die(path, opened):
    os.kill(os.getpid(), signal.SIGKILL)
