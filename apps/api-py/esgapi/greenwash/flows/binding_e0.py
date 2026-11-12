"""흐름 greenwash.colab@E0 의 끼움(core/flows/binding.py 의 RunBinding) — 실행 행의 문서·옵션에서 흐름의 입력과 어댑터를
짓는다(밴드 G1b). apps.py 의 ready() 가 REGISTRY 곁에 `BINDINGS.register(FLOW_ID, GreenwashBinding(store=…))` 로 단다.

    check_options(options)     옵션 꼴 greenwash.options@1(contracts/options_shapes.py)을 받는다. 어기면
                               RunOptionsRejected(<해요체 한 문장> — 400 INVALID_OPTIONS 의 message 로 그대로 간다)
    inputs(document, options)  GreenwashInputs. 쪽 배열은 노트북 셀 16 의 쪽 글자로 바꾼다(pages_to_notebook)
    adapters(ctx)              GreenwashAdapters. 대화는 LlmChatBridge(ctx.llm()), 임베딩은 ClientEmbeddingPort
                               (ctx.embedding()), 좌표는 부를 때마다 새 PdfiumCoordinates(locate 단계가 닫는다 — G1b-2b)
    versions(options)          판 묶음의 흐름 몫 colab_e0.run_versions(None) — {"aiSetting", "evalPromptSha256"}
                               (옛 꼴 RunBinding 을 채우는 것 — 실행기는 아래 versions_with 를 부른다)

회사별 AI 설정 판(밴드 G2c2 — core/flows/binding.py 의 둘째 꼴 RunFactsBinding). 실행기는 이 끼움에 아래 둘을 부른다
(위의 versions·inputs 는 기본 판 그대로 남는다 — RunBinding 을 채우는 꼴이고 기존 시험이 부른다):
    versions_with(options, *, company_id)
        만들 때: store.applied(company_id) — 저장 판이면 {aiSetting: 판 이름, evalPromptSha256: 그 기준표로 **다시
        지은** sha, aiSettingId: 판 id, modelSettingsSha256: 저장 모델 설정을 지금 설정으로 **다시 받은** 값의 sha},
        기본 판이면 지금 값 + aiSettingId: None + modelSettingsSha256: 명세 기본값의 sha. 저장 판의 기준표나 모델 설정이
        지금 받기 규칙에 안 맞으면 RunVersionsRejected(판 이름만 실은 한 문장 — 실행 만들기 409 AI_SETTING_UNUSABLE,
        밴드 G2c3·AS2b)
    inputs_with(document, options, *, company_id, versions)
        돌 때: 열쇠가 없으면(G1b 때 만든 실행) criteria=None(지금 길), None 이면 지금 기본 판의 sha 와 대조한 뒤
        지금 길. 값이면 store.get(company_id, id) 로 **만들 때의 판**을 읽고(그 뒤 적용을 바꿔도 이 판), 다시 지은 sha
        가 versions 의 sha 와 다르면 예외. 없는 판·int 아닌 값도 예외 — 조용히 기본 판으로 가지 않는다(실행은 실패).
        예외는 core 의 RunVersionsMismatch(실행 error_code versions_mismatch — MARC-ENT-352). 저장 판이 지금 받기
        규칙에 안 맞아 다시 지을 수 없을 때도 같다.
        모델 설정(밴드 AS2b, MARC-ENT-353): 열쇠 modelSettingsSha256 가 있는 실행은 모델 설정도 대조한다 — 저장 판은
        저장 값을 지금 설정(models 원천)으로 다시 받아, 거절(code 무엇이든 — 상한이 내려감·경로가 명세에서 빠짐
        등)이거나 sha 가 다르면 예외(versions_mismatch — 글은 로그에만, code 를 싣는다). 기본 판은 명세 기본값의 sha 와
        대조.
        같으면 inputs.model = 받은 judge 단계 — **단 그 단계가 명세 기본값의 judge 단계와 같으면 None**(다리를 지은
        그대로 — 이행된 옛 행·기본값으로 저장한 판의 요청은 AS2b 앞과 바이트 같다). 열쇠가 없는 실행(AS2b 앞에 만든
        것)은 모델 대조를 건너뛰고 model=None(지금 길 — 처분 B2).
        sha 는 경로 이름과 풀린 api_model_id 를 품는다 — 배포로 models.json 의 경로→모델 짝이 바뀌면 그 전에 만든 실행은
        versions_mismatch 로 끝난다(짝을 바꾸는 배포도 진행 중 실행 0 을 보고 한다 — README 「배포 때 진행 중 실행」).
        프롬프트 글(밴드 AS3a-2, MARC-ENT-384): 저장 글이 있는 판(SavedSetting.prompts)은 만들 때 그 글을 지금 받기
        (core check_prompts, layout=colab_e0.LAYOUT)로 다시 받아 — 거절이면 RunVersionsRejected — evalPromptSha256 을
        받은 EVAL 글의 sha 로, 열쇠 promptsSha256 을 prompts_sha256(받은 값)으로 싣는다. 저장 글이 없는 판(코드 글)·기본
        판은 열쇠를 싣지 않는다(versions 바이트 그대로). 돌 때는 「저장 글 있음 ⇔ 열쇠 있음」을 모델 대조보다 먼저 보고
        (기본 판에 열쇠가 있어도) 어긋나면 예외, 다시 받기 거절·두 sha 가운데 하나라도 다르면 예외, 같으면
        inputs.prompts = colab_e0.pack_from(받은 값)(그 실행은 저장 글 넷으로 공급사를 부른다).
        대상 단어(밴드 G2d, MARC-ENT-394): 단어 칸이 있는 판(SavedSetting.terms)은 만들 때 그 칸을 지금 받기
        (terms_e0.accept_terms)로 다시 받아 — 거절이면 RunVersionsRejected(차례는 기준표 → 모델 → 프롬프트 → 단어) —
        열쇠 termsSha256 = terms_sha256(켠 낱말)을 싣는다. 칸 없는 판(NULL)·기본 판은 열쇠를 싣지 않는다(versions 바이트
        그대로). 돌 때는 「칸 있음 ⇔ 열쇠 있음」을 프롬프트 유무 곁(모델 대조보다 먼저)에서 보고 기본 판에 열쇠가 있어도
        예외, 다시 받기 거절·sha 다름도 예외, 같으면 inputs.terms = 켠 낱말 — 단 켠 낱말이 GREEN_TERMS 와 차례까지
        같으면 None(접기 — 판 없음과 같은 길이라 결과·메시지가 판 없는 실행과 바이트 같다). 모델 열쇠 없는 옛 실행
        갈래도 같다.
versions 의 공통 열쇠(aiSettingId·modelSettingsSha256·promptsSha256)는 core ai_versions 가 짓고, 모듈 열쇠 셋(aiSetting·
evalPromptSha256·termsSha256)은 이 파일이 더한다(밴드 AP1b).
store(AiSettingStore)·models(ModelSettingsSource)는 기본값 없이 받는다(빠지면 조용히 기본 판이 되는 길 0). 구현은
service/selectors/ai_settings.py(RunSettingStore — 권한 없는 입구, RunModelSource — 판 저장과 같은 원천), apps.py 가
꽂는다.

받기 차례와 문장(어기는 첫 것 하나 — 값은 글에 싣지 않는다. 열쇠 이름만):
    모르는 열쇠                       「알 수 없는 옵션이에요: <열쇠, 쉼표로>」(criteria·reportYear 등)
    parts 가 없거나 객체가 아님         「파트별 점검 페이지(parts)를 넣어 주세요」
    parts 의 모르는 열쇠               「알 수 없는 파트예요: <열쇠, 쉼표로>」
    parts 의 열쇠 셋 가운데 빠진 것      「파트 셋(ceo·company·climate)의 페이지를 모두 넣어 주세요」
    쪽이 정수의 목록이 아님(bool·실수·글자) 「페이지 번호는 정수의 목록으로 넣어 주세요」
    쪽이 1~300 밖                      「페이지 번호는 1~300 사이여야 해요」
    셋의 합집합이 비었음                「점검할 페이지를 하나 이상 골라 주세요」
    extraTerms 가 101개 이상(거르기 전)  「추가 단어는 100개까지만 보낼 수 있어요」
    그 밖의 추가 단어 규칙              colab_e0.accept_extra_terms 의 ValueError 문장 그대로

★ 경로 둘(chat_route·embedding_route)의 기본값은 실제 경로 이름이다. 실행기는 모의 공급사만 싣고 키를 비우므로
  (runs/context.py) 지금 서버의 실행은 임베딩에서 실패한다 — 실호출을 켜는 밴드(MARC-ENT-262) 전까지. 모의 경로
  (mock·mock-gw1)는 시험이 새 BindingRegistry 에 단 인스턴스에서만 쓴다.
★ 대화 포트는 반드시 LlmChatBridge 다 — 기준표가 기본 판과 다른 실행의 judge 가 with_pack 으로 갈아 끼울 수 있는
  꼴이 그것뿐이다(아니면 그 실행은 judge 에서 TypeError — MARC-ISSUE-208).
★ 꼬리표(Tags)는 tenant = 회사 id 글자, module = 실행의 모듈이다. 실행 id 는 칸이 없다 — 실행기의 싱크(RunCallSink)가
  기록마다 덮어 적는다.
이 파일은 순수다(django 0 — .importlinter 계약 다). 옵션 꼴(contracts/options_shapes.py)은 들이지 않는다(상한은 같은
값을 시험이 견준다).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final, Protocol, cast

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedStep,
    AiStepSpec,
    ModelSettingRefused,
    PromptRefused,
    ai_versions,
    check_model_settings,
    check_prompts,
    defaults,
    model_settings_sha256,
    prompts_sha256,
)
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.flows.binding import (
    DocumentInput,
    RunContext,
    RunOptionsRejected,
    RunVersionsMismatch,
    RunVersionsRejected,
)
from esgapi.core.llm.config import LlmConfig
from esgapi.core.llm.embedding import ClientEmbeddingPort
from esgapi.core.llm.log import sha256_text
from esgapi.core.llm.types import Tags
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.contracts.terms_shapes import GreenwashTerm
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.criteria_e0 import CriteriaRejected
from esgapi.greenwash.flows.terms_e0 import TermsRefused, accept_terms, terms_sha256, used_terms

PARTS: Final = ("ceo", "company", "climate")
OPTION_KEYS: Final = frozenset({"parts", "extraTerms"})
PAGE_MAX: Final = 300
EXTRA_TERMS_SENT_MAX: Final = 100
EMBEDDING_ROUTE: Final = "light-openai"
"""임베딩의 기본 경로 — core/llm/data/models.json 의 embeddingRoutes 이름(text-embedding-3-small)."""
EMBEDDING_BATCH: Final = colab.CHUNK_ARGS["embedding_batch_size"]


@dataclass(frozen=True, slots=True)
class SavedSetting:
    """회사의 저장된 판 하나(기준표·모델 설정·프롬프트 글째)."""

    id: int
    name: str
    criteria: GreenwashCriteria
    model_settings: AiModelSettingsIn
    prompts: AiPromptsIn | None
    """저장 글 정규형(ai.prompts@1). None = 코드 글(AS3a-2 — 기본값 없음: 빠지면 조용히 코드 글이 되는 길 0)."""
    terms: Sequence[GreenwashTerm] | None
    """대상 단어 저장 칸(받기 정규형 — G2d). None = 코드 기본 목록(GREEN_TERMS). 기본값 없음(위와 같은 까닭)."""


@dataclass(frozen=True, slots=True)
class DefaultSetting:
    """적용 판 없음 = 기본 판(코랩 원본 — 코드에 고정)."""


@dataclass(frozen=True, slots=True)
class SettingNotFound:
    """그 회사에 그 id 의 판이 없다."""

    id: int


class AiSettingStore(Protocol):
    """판 읽기 포트(순수). 구현은 service/selectors/ai_settings.py."""

    def applied(self, company_id: int) -> SavedSetting | DefaultSetting: ...

    def get(self, company_id: int, setting_id: int) -> SavedSetting | SettingNotFound: ...


class ModelSettingsSource(Protocol):
    """판 모델 설정의 받기·sha 원천(순수 포트 — AS2b ★E). 구현은 service/selectors/ai_settings.RunModelSource: 실제
    설정(LlmConfig)과 그린워싱 단계 명세(prompt_model_e0.STEPS). 판 저장·적용과 실행기가 같은 원천을 본다."""

    def config(self) -> LlmConfig: ...

    def steps(self) -> Sequence[AiStepSpec]: ...


AiSettingMismatch: Final = RunVersionsMismatch
"""실행에 박힌 판을 그대로 다시 지을 수 없다(없는 판·int 아닌 id·sha 다름·지금 받기에 안 맞음 — 기준표·모델 설정).
실행은 실패한다(글은 로그에만). 실행기의 error_code 표는 `<모듈>.<qualname>` 으로 고르므로(RE1) core 의 예외 그대로다
(G2c2 의 이름은 별칭)."""


def _keys(keys: Sequence[object]) -> str:
    return ", ".join(sorted(str(k) for k in keys))


def _pages(given: object) -> list[int]:
    """쪽 배열 하나를 받는다(정수만 — bool 은 int 의 하위라 따로 막는다)."""
    if not isinstance(given, list):
        raise RunOptionsRejected("페이지 번호는 정수의 목록으로 넣어 주세요")
    pages = cast("list[object]", given)
    if not all(isinstance(p, int) and not isinstance(p, bool) for p in pages):
        raise RunOptionsRejected("페이지 번호는 정수의 목록으로 넣어 주세요")
    ints = cast("list[int]", pages)
    if not all(1 <= p <= PAGE_MAX for p in ints):
        raise RunOptionsRejected(f"페이지 번호는 1~{PAGE_MAX} 사이여야 해요")
    return ints


def _too_many(terms: object) -> bool:
    """거르기 전 추가 단어 수가 상한을 넘는가(목록이 아니면 accept_extra_terms 가 거절한다)."""
    return isinstance(terms, list) and len(cast("list[object]", terms)) > EXTRA_TERMS_SENT_MAX


def accept_options(options: Mapping[str, object]) -> tuple[dict[str, list[int]], tuple[str, ...]]:
    """옵션을 받아 (파트별 쪽, 추가 단어)를 돌려준다. 어기면 RunOptionsRejected(머리말의 차례·문장)."""
    unknown = [k for k in options if k not in OPTION_KEYS]
    if unknown:
        raise RunOptionsRejected(f"알 수 없는 옵션이에요: {_keys(unknown)}")
    parts = options.get("parts")
    if not isinstance(parts, Mapping):
        raise RunOptionsRejected("파트별 점검 페이지(parts)를 넣어 주세요")
    given = cast("Mapping[object, object]", parts)
    stray = [k for k in given if k not in PARTS]
    if stray:
        raise RunOptionsRejected(f"알 수 없는 파트예요: {_keys(stray)}")
    if any(part not in given for part in PARTS):
        raise RunOptionsRejected("파트 셋(ceo·company·climate)의 페이지를 모두 넣어 주세요")
    pages = {part: _pages(given[part]) for part in PARTS}
    if not any(pages.values()):
        raise RunOptionsRejected("점검할 페이지를 하나 이상 골라 주세요")
    terms = options.get("extraTerms", [])
    if _too_many(terms):
        raise RunOptionsRejected(f"추가 단어는 {EXTRA_TERMS_SENT_MAX}개까지만 보낼 수 있어요")
    try:
        accepted = colab.accept_extra_terms(terms)
    except ValueError as refused:
        raise RunOptionsRejected(str(refused)) from refused
    return pages, accepted


def pages_to_notebook(pages: Sequence[int]) -> str:
    """쪽 배열 → 노트북 셀 16 의 쪽 글자(engines/e0/parts.parse_pages 가 읽는 꼴). 겹침을 접고 오름차순으로, 이어진
    쪽은 "a~b" 로 줄인다: [] → "", [5] → "5", [6..14] → "6~14", [25..37, 55..74] → "25~37,55~74"."""
    ordered = sorted(set(pages))
    runs: list[str] = []
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        runs.append(str(ordered[i]) if i == j else f"{ordered[i]}~{ordered[j]}")
        i = j + 1
    return ",".join(runs)


@dataclass(frozen=True, slots=True, kw_only=True)
class RunSetting:
    """실행에 박힌 판을 다시 지은 판 칸 넷(GreenwashInputs 의 같은 이름 칸). 다 None 이면 판 없음(지금 길)."""

    criteria: GreenwashCriteria | None
    prompts: colab.PromptPack | None
    model: AcceptedStep | None
    terms: tuple[str, ...] | None


NO_SETTING: Final = RunSetting(criteria=None, prompts=None, model=None, terms=None)


class GreenwashBinding:
    """greenwash.colab@E0 의 끼움(머리말)."""

    def __init__(
        self,
        *,
        store: AiSettingStore,
        models: ModelSettingsSource,
        chat_route: str = colab.CHAT_ROUTE,
        embedding_route: str = EMBEDDING_ROUTE,
    ) -> None:
        self.store = store
        self.models = models
        self.chat_route = chat_route
        self.embedding_route = embedding_route

    def check_options(self, options: Mapping[str, object]) -> None:
        accept_options(options)

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> colab.GreenwashInputs:
        pages, terms = accept_options(options)
        return colab.GreenwashInputs(
            document=document.content,
            media_type=document.media_type,
            file_name=document.file_name,
            ceo=pages_to_notebook(pages["ceo"]),
            company=pages_to_notebook(pages["company"]),
            climate=pages_to_notebook(pages["climate"]),
            extra_terms=terms,
            criteria=None,
            dry_run=False,
        )

    def adapters(self, ctx: RunContext) -> colab.GreenwashAdapters:
        # 늦은 import — API 프로세스에 pypdfium2 를 올리지 않는다(실행기 워커만 이 줄에 닿는다)
        from esgapi.greenwash.tools.coordinates import PdfiumCoordinates

        tags = Tags(tenant=str(ctx.company_id), module=ctx.module)
        return colab.GreenwashAdapters(
            pdf_text=colab.PDF_TEXT(),
            llm=colab.LlmChatBridge(ctx.llm(), route=self.chat_route, tags=tags),
            embedding=ClientEmbeddingPort(
                ctx.embedding(), route=self.embedding_route, tags=tags, batch_size=EMBEDDING_BATCH
            ),
            coordinates=PdfiumCoordinates(),
            tokens=None,
        )

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return colab.run_versions(None)

    def _defaults(self) -> AcceptedModelSettings:
        return defaults(self.models.config(), self.models.steps())

    def _accepted(self, saved: SavedSetting) -> AcceptedModelSettings | ModelSettingRefused:
        return check_model_settings(self.models.config(), saved.model_settings, steps=self.models.steps())

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        applied = self.store.applied(company_id)
        if isinstance(applied, DefaultSetting):
            return {**colab.run_versions(None), **ai_versions(setting_id=None, model=self._defaults(), prompts=None)}
        unusable = RunVersionsRejected(
            f"적용한 AI 설정 판({applied.name})이 지금 규칙에 맞지 않아요. "
            "운영 관리자가 판을 다시 저장해 적용하거나 기본 판으로 되돌려야 해요"
        )
        try:
            built = colab.run_versions(applied.criteria)
        except CriteriaRejected as refused:
            raise unusable from refused
        model = self._accepted(applied)
        if isinstance(model, ModelSettingRefused):
            raise unusable
        texts = None if applied.prompts is None else check_prompts(applied.prompts, layout=colab.LAYOUT)
        if isinstance(texts, PromptRefused):
            raise unusable
        # 코드 글 판(texts None)은 열쇠 promptsSha256 을 싣지 않는다(versions 바이트 그대로 — core ai_versions)
        versions = {**built, **ai_versions(setting_id=applied.id, model=model, prompts=texts)}
        if texts is not None:  # 저장 글 판의 판정 글 sha — built 의 자리 그대로 덮는다(열쇠 차례 = 바닥)
            versions["evalPromptSha256"] = sha256_text(colab.pack_from(texts).eval_system_prompt)
        if applied.terms is None:
            return versions  # 단어 칸 없는 판 — 열쇠 termsSha256 을 싣지 않는다(versions 바이트 그대로)
        accepted = accept_terms(applied.terms)
        if isinstance(accepted, TermsRefused):
            raise unusable
        return {**versions, "termsSha256": terms_sha256(used_terms(accepted))}

    def _judge_model(self, accepted: AcceptedModelSettings) -> AcceptedStep | None:
        """받은 judge 단계. 명세 기본값의 judge 단계와 같으면 None(다리를 지은 그대로 — 머리말)."""
        (judge,) = (step for step in accepted.steps if step.key == "judge")
        (default,) = (step for step in self._defaults().steps if step.key == "judge")
        return None if judge == default else judge

    def inputs_with(
        self, document: DocumentInput, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> colab.GreenwashInputs:
        base = self.inputs(document, options)
        setting = self.run_setting(company_id=company_id, versions=versions)
        if setting == NO_SETTING:
            return base  # 열쇠 없는 옛 실행(G1b)·기본 판 — 지금 길
        return replace(
            base, criteria=setting.criteria, prompts=setting.prompts, model=setting.model, terms=setting.terms
        )

    def run_setting(self, *, company_id: int, versions: Mapping[str, object]) -> "RunSetting":
        """실행에 박힌 판 묶음을 지금 다시 지어 견준 판 칸 넷(inputs_with 의 몸 — 재판단 끼움 flows/rejudge_e0.py 도
        같은 이것으로 원 실행의 판을 다시 짓는다, 밴드 GRJ1). 어긋나면 AiSettingMismatch. 판 없음은 NO_SETTING."""
        if "aiSettingId" not in versions:
            return NO_SETTING  # 열쇠 없는 옛 실행(G1b) — 지금 길
        setting_id = versions["aiSettingId"]
        checks_model = "modelSettingsSha256" in versions  # AS2b 앞에 만든 실행은 열쇠가 없다(처분 B2)
        checks_prompts = "promptsSha256" in versions  # 저장 글 판으로 만든 실행만 열쇠가 있다(AS3a-2)
        checks_terms = "termsSha256" in versions  # 단어 칸 있는 판으로 만든 실행만 열쇠가 있다(G2d)
        if setting_id is None:
            if checks_prompts:
                raise AiSettingMismatch("기본 판으로 만든 실행에 저장 프롬프트 글의 sha 가 있다")
            if checks_terms:
                raise AiSettingMismatch("기본 판으로 만든 실행에 대상 단어의 sha 가 있다")
            # 기본 판으로 만든 실행 — 지금 기본 판의 sha 와 대조한다(엔진 글이 바뀌었으면 조용히 다른 글로 돌지 않는다)
            if colab.run_versions(None)["evalPromptSha256"] != versions.get("evalPromptSha256"):
                raise AiSettingMismatch("기본 판의 판정 프롬프트가 실행을 만들 때와 다르다")
            if checks_model and model_settings_sha256(self._defaults()) != versions["modelSettingsSha256"]:
                raise AiSettingMismatch("기본 판의 모델 설정이 실행을 만들 때와 다르다")
            return NO_SETTING
        if not isinstance(setting_id, int) or isinstance(setting_id, bool):
            raise AiSettingMismatch(f"versions.aiSettingId 가 int 가 아니다: {type(setting_id).__name__}")
        found = self.store.get(company_id, setting_id)
        if isinstance(found, SettingNotFound):
            raise AiSettingMismatch(f"실행의 AI 설정 판 {setting_id} 이 그 회사에 없다")
        if (found.prompts is not None) != checks_prompts:  # 모델 대조(checks_model)보다 먼저 — AS2b 앞 실행도 본다
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다")
        if (found.terms is not None) != checks_terms:  # 같은 까닭으로 모델 대조보다 먼저
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 대상 단어 유무가 실행을 만들 때와 다르다")
        try:
            rebuilt = colab.run_versions(found.criteria)
        except CriteriaRejected as refused:
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 을 지금 받기 규칙으로 다시 지을 수 없다") from refused
        pack = None if found.prompts is None else self._saved_pack(setting_id, found.prompts, versions)
        if pack is None and rebuilt["evalPromptSha256"] != versions.get("evalPromptSha256"):
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 판정 프롬프트가 실행을 만들 때와 다르다")
        terms = None if found.terms is None else self._saved_terms(setting_id, found.terms, versions)
        if not checks_model:
            return RunSetting(criteria=found.criteria, prompts=pack, model=None, terms=terms)
        model = self._accepted(found)
        if isinstance(model, ModelSettingRefused):
            raise AiSettingMismatch(
                f"AI 설정 판 {setting_id} 의 모델 설정을 지금 받기로 다시 받을 수 없다: {model.code}"
            )
        if model_settings_sha256(model) != versions["modelSettingsSha256"]:
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 모델 설정이 실행을 만들 때와 다르다")
        return RunSetting(criteria=found.criteria, prompts=pack, model=self._judge_model(model), terms=terms)

    def _saved_terms(
        self, setting_id: int, saved: Sequence[GreenwashTerm], versions: Mapping[str, object]
    ) -> tuple[str, ...] | None:
        """저장 단어를 지금 받기로 다시 받아 만들 때의 sha 와 견준 켠 낱말. 어긋나면 AiSettingMismatch. 켠 낱말이
        GREEN_TERMS 와 차례까지 같으면 None(접기 — 판 없음과 같은 길, 발주서 ★G)."""
        accepted = accept_terms(saved)
        if isinstance(accepted, TermsRefused):
            raise AiSettingMismatch(
                f"AI 설정 판 {setting_id} 의 대상 단어를 지금 받기로 다시 받을 수 없다: {accepted.code}"
            )
        used = used_terms(accepted)
        if terms_sha256(used) != versions.get("termsSha256"):
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 대상 단어가 실행을 만들 때와 다르다")
        return None if used == tuple(colab.DEFAULT_TERMS) else used

    def _saved_pack(self, setting_id: int, saved: AiPromptsIn, versions: Mapping[str, object]) -> colab.PromptPack:
        """저장 글을 지금 받기로 다시 받아 만들 때의 두 sha(EVAL 글·글 넷)와 견준 묶음. 어긋나면 AiSettingMismatch."""
        texts = check_prompts(saved, layout=colab.LAYOUT)
        if isinstance(texts, PromptRefused):
            raise AiSettingMismatch(
                f"AI 설정 판 {setting_id} 의 프롬프트 글을 지금 받기로 다시 받을 수 없다: {texts.code}"
            )
        pack = colab.pack_from(texts)
        if sha256_text(pack.eval_system_prompt) != versions.get("evalPromptSha256"):
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 판정 프롬프트가 실행을 만들 때와 다르다")
        if prompts_sha256(texts) != versions.get("promptsSha256"):
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 프롬프트 글이 실행을 만들 때와 다르다")
        return pack
