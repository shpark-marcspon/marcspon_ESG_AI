"""흐름을 실행기에 끼우는 포트(끼움)와 그 등록부. 순수(django·ninja·psycopg 0 — .importlinter 계약 다).

흐름(types.py·registry.py)은 「입력·어댑터 → 산출물」만 안다. 실행기(esgapi/runs/tasks.py)는 실행 행의 문서·옵션에서
그 입력과 어댑터를 지어야 하는데, runs 는 업무 모듈을 import 하지 못한다(계약 차). 그래서 모듈이 흐름 곁에 끼움을
단다:

    BINDINGS.register("greenwash.colab@E0", GreenwashBinding())    # 모듈의 AppConfig.ready() — REGISTRY.register 곁

    check_options(options)          실행 만들기 때: 옵션이 이 흐름에 맞는가. 아니면 RunOptionsRejected
                                    (사람에게 보일 한 문장)
    inputs(document, options)       흐름의 입력 dataclass 를 짓는다
    adapters(ctx)                   흐름의 어댑터 dataclass 를 짓는다. LLM 은 ctx.llm()·ctx.embedding() 으로만
    versions(options)               판 묶음의 흐름 몫(실행 행 versions 에 실린다 — MARC-ENT-210 (2))

  실행의 회사·만들 때의 판이 필요한 끼움은 둘째 꼴 RunFactsBinding 을 더 갖춘다(밴드 G2c2 — 그린워싱 AI 설정 판):
    versions_with(options, *, company_id)                     만들 때: 그 회사의 지금 판으로 판 묶음
    inputs_with(document, options, *, company_id, versions)   돌 때: 실행 행에 박힌 versions 로 입력
  실행기는 isinstance(binding, RunFactsBinding) 일 때만 이 둘을 부르고, 아니면 versions·inputs 그대로다(다른 끼움 0줄).
  지을 수 없으면 versions_with 는 RunVersionsRejected(만들기 409 — 행 0), inputs_with 는 RunVersionsMismatch(실패).

★ 끼움이 없는 흐름은 실행하지 못한다(실행 만들기 422 FLOW_NOT_RUNNABLE, 실행기 failed·flow_not_runnable).

문서 없는 흐름(ND1 — 입력이 옵션뿐인 흐름, 데이터 검증)은 다른 갈래로 단다:

    BINDINGS.register_documentless("dataverify.colab@156", DataverifyBinding(), max_options_bytes=256 * 1024)

  꼴은 DocumentlessBinding(inputs 가 문서를 받지 않고 회사를 받는다 — 옵션 속 id 를 그 회사로 거르라고)이고, 회사·판이
  필요하면 DocumentlessFactsBinding 을 더 갖춘다. 실행 만들기는 이 흐름에 documentId 를 받지 않고(422
  DOCUMENT_NOT_ACCEPTED), 실행기는 문서를 읽지 않는다. 옵션의 앱 상한은 흐름마다(options_limit — 두 갈래 다
  등록값(기본 DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS), 많아야 DOCUMENTLESS_OPTIONS_MAX_OCTETS).
  ★ 어느 갈래인지는 어느 사전에 달렸는가로 가른다(documentless 가 None 이 아니면 문서 없는 흐름). RunFactsBinding 은
    runtime_checkable 이라 이름만 본다 — 문서 없는 끼움에 그 isinstance 를 쓰면 문서 꼴로 불러 TypeError 다.
★ 실행기는 시도마다 끼움의 adapters 를 새로 부른다. 어댑터에 상태가 있으면(모의 대본) 이어 도는 시도가 다른 상태를
  본다 — ctx.attempt 가 그 시도의 번호다.
★ 단계나 어댑터가 「잠깐의 실패」(저장소에 닿지 못함, LLM 시간 초과)를 실행기에 알리려면 RunRetryLater 를 던진다.
  실행기는 그 시도를 접고 같은 실행을 다시 넣는다(시도 상한은 진행 없이 끝난 시도만 센다). 그 밖의 예외는 실패다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from esgapi.core.flows.types import FlowRegistryError
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.embedding import EmbeddingClient

# 실행 옵션의 앱 상한(바이트 — raw JSON). runs 를 import 하지 못해(계약 차) 여기 둔다. 등록값이고 기본은 DEFAULT 다
# (runs/models.py 의 RUN_OPTIONS_MAX_OCTETS 와 같은 값). DB 의 CHECK 는 MAX 의 두 배 + 64(runs 0002).
DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS: Final = 16 * 1024
DOCUMENTLESS_OPTIONS_MAX_OCTETS: Final = 256 * 1024  # 데이터 검증 입력의 어림(MARC-TICK-236 — 78 측정 ≈14KB~50KB+)


class RunOptionsRejected(Exception):
    """실행의 옵션이 이 흐름에 맞지 않는다. 글은 사람에게 그대로 보인다(한국어 한 문장)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RunVersionsRejected(Exception):
    """끼움이 이 실행의 판 묶음을 지금 지을 수 없다(versions_with). 글은 사람에게 그대로 보인다(한국어 한 문장)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RunVersionsMismatch(Exception):
    """실행에 박힌 판 묶음을 돌 때 그대로 다시 지을 수 없다(inputs_with). 실행은 실패한다(글은 로그에만)."""


class RunRetryLater(Exception):
    """잠깐의 실패다(다시 해 볼 수 있다). 실행기는 이 시도를 접고 실행을 다시 넣는다. 글은 로그에만 간다."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentInput:
    """실행의 문서(바이트째). 실행기가 저장소에서 읽어 넘긴다."""

    content: bytes
    media_type: str
    file_name: str


class RunContext(Protocol):
    """끼움의 adapters 가 받는 것. 실행 하나·시도 하나의 것이다(시도마다 새로 진다).

    llm()·embedding()  그 실행의 LLM 클라이언트. 호출 기록에는 늘 이 실행의 id 가 실린다(꼬리표와 무관)
    (`dry_run` 칸은 읽는 곳이 없어 지웠다 — LH1 Q4. 조립만 하는 실행은 흐름 입력의 dry_run 이 정한다)
    """

    @property
    def company_id(self) -> int: ...

    @property
    def run_id(self) -> int: ...

    @property
    def module(self) -> str: ...

    @property
    def flow_id(self) -> str: ...

    @property
    def attempt(self) -> int: ...

    def llm(self) -> LlmClient: ...

    def embedding(self) -> EmbeddingClient: ...


class RunBinding(Protocol):
    def check_options(self, options: Mapping[str, object]) -> None:
        """맞지 않으면 RunOptionsRejected."""
        ...

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> object: ...

    def adapters(self, ctx: RunContext) -> object: ...

    def versions(self, options: Mapping[str, object]) -> dict[str, object]: ...


@runtime_checkable
class RunFactsBinding(Protocol):
    """끼움의 둘째 꼴(G2c2). 실행의 회사와 만들 때 박은 판 묶음을 받는다. 갖춘 끼움만 실행기가 이 길로 부른다."""

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]: ...

    def inputs_with(
        self, document: DocumentInput, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> object: ...


class DocumentlessBinding(Protocol):
    """문서 없는 흐름의 끼움(ND1). RunBinding 과 같되 inputs 가 문서 대신 실행의 회사를 받는다."""

    def check_options(self, options: Mapping[str, object]) -> None:
        """맞지 않으면 RunOptionsRejected."""
        ...

    def inputs(self, options: Mapping[str, object], *, company_id: int) -> object: ...

    def adapters(self, ctx: RunContext) -> object: ...

    def versions(self, options: Mapping[str, object]) -> dict[str, object]: ...


@runtime_checkable
class DocumentlessFactsBinding(Protocol):
    """문서 없는 끼움의 둘째 꼴(RunFactsBinding 의 문서 없는 판). 갖춘 끼움만 만들기·실행기가 이 길로 부른다."""

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]: ...

    def inputs_with(
        self, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class NoBinding:
    """그 흐름에 끼움이 없다(흐름이 없어도 이 갈래다 — 흐름은 REGISTRY 가 따로 답한다)."""

    flow_id: str


class BindingRegistry:
    """흐름 id@판 → 끼움. 프로세스에 하나(BINDINGS). 순수 테스트는 새 것을 짓는다."""

    def __init__(self) -> None:
        self._bindings: dict[str, RunBinding] = {}
        self._documentless: dict[str, DocumentlessBinding] = {}
        self._options_limit: dict[str, int] = {}
        self._order: list[str] = []  # 단 차례(두 갈래 함께)

    def register(
        self, flow_id: str, binding: RunBinding, *, max_options_bytes: int = DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS
    ) -> None:
        """같은 흐름에 두 번 달면 FlowRegistryError(같은 객체여도 — REGISTRY.register 와 같은 규칙). 문서 없는
        갈래에 달린 흐름도 같다. 상한이 1 미만·MAX 초과여도 FlowRegistryError(register_documentless 와 같은 검사)."""
        self._check(flow_id, max_options_bytes)
        self._bindings[flow_id] = binding
        self._options_limit[flow_id] = max_options_bytes
        self._order.append(flow_id)

    def register_documentless(
        self,
        flow_id: str,
        binding: DocumentlessBinding,
        *,
        max_options_bytes: int = DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS,
    ) -> None:
        """문서 없는 흐름의 끼움(ND1). 어느 갈래에든 이미 달렸거나 상한이 1 미만·MAX 초과면 FlowRegistryError."""
        self._check(flow_id, max_options_bytes)
        self._documentless[flow_id] = binding
        self._options_limit[flow_id] = max_options_bytes
        self._order.append(flow_id)

    def _check(self, flow_id: str, max_options_bytes: int) -> None:
        """두 갈래 등록의 같은 검사: 어느 갈래에든 이미 달렸거나 상한이 1~MAX 밖이면 FlowRegistryError."""
        if flow_id in self._bindings or flow_id in self._documentless:
            raise FlowRegistryError(f"흐름 {flow_id} 의 끼움이 이미 있다")
        if not 1 <= max_options_bytes <= DOCUMENTLESS_OPTIONS_MAX_OCTETS:
            raise FlowRegistryError(
                f"흐름 {flow_id} 의 옵션 상한 {max_options_bytes} 은 1~{DOCUMENTLESS_OPTIONS_MAX_OCTETS} 밖이다"
            )

    def get(self, flow_id: str) -> RunBinding | NoBinding:
        """문서 흐름의 끼움. 문서 없는 흐름이면 NoBinding 이다(그 끼움은 documentless 로)."""
        found = self._bindings.get(flow_id)
        return NoBinding(flow_id) if found is None else found

    def documentless(self, flow_id: str) -> DocumentlessBinding | None:
        """문서 없는 흐름의 끼움. 아니면 None."""
        return self._documentless.get(flow_id)

    def options_limit(self, flow_id: str) -> int:
        """그 흐름의 옵션 앱 상한(바이트). 등록값(기본 DEFAULT), 끼움이 없는 흐름은 DEFAULT."""
        return self._options_limit.get(flow_id, DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS)

    def flow_ids(self) -> tuple[str, ...]:
        """끼움이 있는 흐름(단 차례 — 두 갈래 함께)."""
        return tuple(self._order)


BINDINGS: Final = BindingRegistry()
"""프로세스에 하나. 각 모듈의 AppConfig.ready() 가 흐름을 달 때 같이 단다."""
