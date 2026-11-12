"""큐에 넣는 갈고리(esgapi/core/resources/queue.py). 순수 층: 가짜 앱을 끼워 잰다. 브로커도 DB 도 없다.

★ 진짜 celery_app() 으로 send_task 를 부르지 않는다(이 층은 소켓이 막혀 있고, 업무·보안 층은 막기 밖이다).
"""

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from esgapi.config.env import BrokerSettings
from esgapi.core.calc.documents import COMPANY_ID_TEXT
from esgapi.core.resources import queue as hooks

BROKER = BrokerSettings(
    url="sqs://queue:9324",
    region="ap-northeast-2",
    queue_name="esg-jobs",
    queue_url="http://queue:9324/000000000000/esg-jobs",
    secure=False,
)
ESGAPI = Path(__file__).resolve().parents[2]
COMPANY = 9876543  # 순수 층의 회사 id(DB 가 없다). 기록에 안 실리는 것을 글자로 보려고 흔치 않은 수로 둔다


class FakeApp:
    """send_task 가 받은 것을 적어 두는 가짜 Celery 앱."""

    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.error = error

    def send_task(self, *args: Any, **kwargs: Any) -> None:
        self.sent.append((args, kwargs))
        if self.error is not None:
            raise self.error


@pytest.fixture
def fake_app(monkeypatch: pytest.MonkeyPatch) -> FakeApp:
    app = FakeApp()
    monkeypatch.setattr(hooks, "celery_app", lambda: app)
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    return app


def test_the_note_carries_the_task_name_two_ids_the_queue_and_no_retry(fake_app: FakeApp) -> None:
    hooks.enqueue_job(company_id=COMPANY, job_id=42, kind="parse")
    assert fake_app.sent == [
        (("jobs.parse",), {"kwargs": {"company_id": "9876543", "job_id": "42"}, "queue": "esg-jobs", "retry": False})
    ]
    kwargs = fake_app.sent[0][1]["kwargs"]
    # 쪽지에는 id 둘뿐이다(바이트·주소·저장소 키·파일 이름이 없다). 값은 글자다(옛 이름의 칸은 없다).
    assert set(kwargs) == {"company_id", "job_id"}
    assert all(type(value) is str for value in kwargs.values())
    assert fake_app.sent[0][1]["retry"] is False


@pytest.mark.parametrize(("company_id", "job_id"), [(1, 1), (COMPANY, 42), (2**63 - 1, 2**63 - 1)])
def test_the_two_ids_are_sent_as_decimal_text(fake_app: FakeApp, company_id: int, job_id: int) -> None:
    """정수 id 둘은 십진 숫자 글자로 실린다: 워커 입구(reconcile/tasks.py)가 받는 꼴(COMPANY_ID_TEXT)이고,
    config/celery.py 의 on_task_prerun 이 job_id 를 글자일 때만 로그에 싣는다(reconcile/tests/test_task_note.py)."""
    hooks.enqueue_job(company_id=company_id, job_id=job_id, kind="parse")
    kwargs = fake_app.sent[0][1]["kwargs"]
    assert kwargs == {"company_id": str(company_id), "job_id": str(job_id)}
    assert all(type(value) is str and COMPANY_ID_TEXT.match(value) for value in kwargs.values())
    assert (int(kwargs["company_id"]), int(kwargs["job_id"])) == (company_id, job_id)  # 되읽으면 같은 수


def test_without_a_broker_nothing_is_sent_and_nothing_is_raised(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def no_app() -> Any:
        raise AssertionError("브로커 설정이 없는데 앱을 얻으려 했다")

    monkeypatch.setattr(hooks, "celery_app", no_app)
    monkeypatch.setattr(hooks, "broker_settings", lambda: None)
    with caplog.at_level("WARNING", logger=hooks.logger.name):
        hooks.enqueue_job(company_id=COMPANY, job_id=1, kind="parse")
    assert [record.getMessage().split(" (")[0] for record in caplog.records] == [
        "queue_unconfigured job_id=1 kind=parse"
    ]
    assert str(COMPANY) not in caplog.text


def test_an_error_from_the_broker_is_raised_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """못 닿으면 그대로 던진다(삼키는 것은 올림 확인의 on_commit(robust=True) 다. 다시 넣기 명령은 세어 적는다)."""

    class Unreachable(Exception):
        pass

    app = FakeApp(error=Unreachable("닿지 않는다"))
    monkeypatch.setattr(hooks, "celery_app", lambda: app)
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    with pytest.raises(Unreachable):
        hooks.enqueue_job(company_id=COMPANY, job_id=1, kind="parse")
    assert len(app.sent) == 1  # 한 번 불렀고 다시 부르지 않았다


def test_an_unknown_kind_is_not_sent(fake_app: FakeApp) -> None:
    with pytest.raises(ValueError, match="모르는 일감의 종류"):
        hooks.enqueue_job(company_id=COMPANY, job_id=1, kind="translate")
    assert fake_app.sent == []


def test_the_hook_takes_keywords_only() -> None:
    signature = inspect.signature(hooks.enqueue_job)
    assert [parameter.kind for parameter in signature.parameters.values()] == [inspect.Parameter.KEYWORD_ONLY] * 3
    assert list(signature.parameters) == ["company_id", "job_id", "kind"]


def _module_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _all_imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_hook_sends_by_name_and_imports_the_app_only_when_called() -> None:
    """core 는 업무 모듈을 import 하지 않는다(태스크를 이름으로 보낸다). celery 앱은 함수 안에서 들인다."""
    path = ESGAPI / "core" / "resources" / "queue.py"
    everything = _all_imports(path)
    assert not [name for name in everything if name.startswith("esgapi.reconcile")]
    assert "esgapi.config.celery" in everything
    top = _module_level_imports(path)
    assert "esgapi.config.celery" not in top
    assert not [name for name in top if name.split(".")[0] in ("celery", "kombu")]


def test_celery_is_imported_in_exactly_these_product_files() -> None:
    """celery 를 들이는 제품 코드는 넷이다: 앱 정의, 태스크 둘(분해 · X1b-1 의 실행), 그리고 (앱을 거쳐, 함수 안에서)
    갈고리."""
    direct: set[str] = set()
    through_app: set[str] = set()
    for path in sorted(ESGAPI.rglob("*.py")):
        if "tests" in path.parts:
            continue
        imports = _all_imports(path)
        relative = path.relative_to(ESGAPI).as_posix()
        if any(name.split(".")[0] in ("celery", "kombu") for name in imports):
            direct.add(relative)
        if "esgapi.config.celery" in imports:
            through_app.add(relative)
    assert direct == {"config/celery.py", "reconcile/tasks.py", "runs/tasks.py"}
    assert through_app == {"core/resources/queue.py", "reconcile/tasks.py", "runs/tasks.py"}


def test_a_failed_send_is_logged_with_the_job_id_and_still_raised(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """던지기 앞에 일감 id 를 실은 한 줄을 남긴다. 같은 예외를 그대로 던진다(삼키지도 바꾸지도 않는다)."""

    class Unreachable(Exception):
        pass

    error = Unreachable("닿지 않는다 sqs://queue:9324")
    app = FakeApp(error=error)
    monkeypatch.setattr(hooks, "celery_app", lambda: app)
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    with caplog.at_level("ERROR", logger=hooks.logger.name), pytest.raises(Unreachable) as raised:
        hooks.enqueue_job(company_id=COMPANY, job_id=1, kind="parse")
    assert raised.value is error
    assert len(app.sent) == 1  # 한 번 불렀고 다시 부르지 않았다
    records = [record for record in caplog.records if record.name == hooks.logger.name]
    assert [(record.levelname, record.getMessage()) for record in records] == [
        ("ERROR", "queue_send_failed job_id=1 kind=parse error=Unreachable")
    ]
    # 예외의 글에는 브로커 주소가 들 수 있다. 클래스 이름만 싣고, 스택(글이 든다)도 싣지 않는다.
    assert records[0].exc_info is None
    for absent in (str(COMPANY), "닿지 않는다", "sqs://"):
        assert absent not in caplog.text


def test_a_sent_note_logs_nothing(fake_app: FakeApp, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("DEBUG", logger=hooks.logger.name):
        hooks.enqueue_job(company_id=COMPANY, job_id=1, kind="parse")
    assert len(fake_app.sent) == 1
    assert [record for record in caplog.records if record.name == hooks.logger.name] == []


def test_an_unknown_kind_is_raised_without_a_record(fake_app: FakeApp, caplog: pytest.LogCaptureFixture) -> None:
    """모르는 종류는 브로커의 실패가 아니다. `queue_send_failed` 를 남기지 않고 던진다."""
    with caplog.at_level("DEBUG", logger=hooks.logger.name), pytest.raises(ValueError, match="모르는 일감의 종류"):
        hooks.enqueue_job(company_id=COMPANY, job_id=1, kind="translate")
    assert fake_app.sent == []
    assert [record for record in caplog.records if record.name == hooks.logger.name] == []
