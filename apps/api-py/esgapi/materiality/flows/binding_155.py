"""흐름 materiality.iro@155 의 끼움(core/flows/binding.py 의 DocumentlessBinding + DocumentlessFactsBinding — 밴드
IR3a, 문서 없는 흐름 ND1 · AI 설정 판 IR4 ③). apps.py 의 ready() 가 REGISTRY 곁에 `BINDINGS.register_documentless(
iro_155.FLOW_ID, MaterialityBinding(settings=…, models=…), max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS)` 로
단다(옵션 상한은 등록 인자 — 256KiB). 1부 단독
materiality.colab@155 는 끼우지 않는다(REGISTRY 에만 — 실행 만들기 422 FLOW_NOT_RUNNABLE).

    check_options(options)          옵션 꼴 materiality.options@1 을 strict 로 받고 dateRange 를 「오늘」로 읽어 본다.
                                    어기면 RunOptionsRejected(<해요체 한 문장 — 열쇠 길만, 값은 싣지 않는다>)
    versions(options)               {"engine": "colab_155", "flow": FLOW_ID, "promptIds": {단계: id — 1부 셋·2부 셋}}
                                    경로는 싣지 않는다(경로 둘을 route 한 글로 못 싣는다 — 모델은 modelSettingsSha256)
    versions_with(options, *, company_id)
                                    만들 때: versions + 판 열쇠(아래 「회사별 AI 설정 판」)
    inputs_with(options, *, company_id, versions)
                                    흐름의 입력. 글·모델 칸은 versions 의 판(아래)
    inputs(options, *, company_id)  inputs_with 의 판 없는 꼴 — IroInputs(received=options["input"] 그대로, tags=(회사
                                    id 글자, materiality), max_cost_usd=RUN_MAX_COST_USD, today=today()) 에 코드 값
                                    (DEFAULT_TEXTS·research·analysis 코드 모델 값 — IR4 ① 앞과 같은 요청)
    adapters(ctx)                   IroAdapters(llm=ctx.llm()) — 호출 기록에 이 실행의 id 가 실린다

받기 차례와 문장(어기는 첫 갈래 하나):
    모르는 열쇠(맨 위·input·그 아래)   「알 수 없는 옵션이에요: <열쇠 길, 쉼표로>」
    빠진 칸                            「옵션 <열쇠 길>이(가) 없어요」
    그 밖(타입·무늬·schemaVersion 값·토픽 이름 겹침)   「옵션 <열쇠 길>의 값이 맞지 않아요」
    꼴은 맞는데 dateRange 를 「오늘」로 못 읽음(문법 밖·달력에 없는 날·시작 > 끝)
                                       「옵션 input.dateRange의 값이 맞지 않아요」
  열쇠 길에서 사용자가 지은 dict 열쇠(_DICT_KEY_FIELDS 칸 바로 아래 — 토픽 이름)는 `*` 다(MARC-ISSUE-367 — 글자 0).
  input 의 꼴 판정은 shapes.check_input 과 같다(strict — options 꼴이 shapes.MaterialityInput 을 그대로 싣는다).
  dateRange 는 흐름의 load 도 다시 본다(방어) — 사람이 고칠 잘못을 실행 행 없이 만들기에서 막으려고 여기서도 본다.

「오늘」은 이 파일의 clock() 하나에서만 읽는다(실행기 runs/tasks.py 의 clock 꼴 — 시험은 모듈 속성을 갈아 끼운다).
서버 시계는 UTC 라 Asia/Seoul 로 바꾼 날짜를 넣는다. 흐름(iro_155)은 시계를 읽지 않는다. 창은 load 단계 data 에 박혀
load 뒤에서 이어 돌면 「오늘」이 바뀌어도 앞 창 그대로다.

받은 input 은 고치지 않고 넘긴다(프롬프트가 글자째 싣는다). 실행 행의 options 는 열쇠 차례를 지키는 칸이라
(runs OrderedJSONField — ND1) 실행기를 거쳐도 요청이 run_flow 에 바로 넣은 것과 같다.

회사별 AI 설정 판(밴드 IR4 ③ — 결정 MARC-ENT-399·381·387·352, 데이터 검증 binding_156 의 꼴):
    versions_with  settings.applied(company_id) — 기본 판이면 {**versions, aiSetting: DEFAULT_TITLE, **ai_versions(None,
        명세 기본값, None)}. 저장 판이면 저장 모델 설정·글을 지금 받기(prompt_model_155.accept_model·accept_stored)로
        **다시 받아** {**versions, aiSetting: 판 이름, **ai_versions(판 id, 받은 모델, 받은 글|None)}. 다시 받기
        거절이면 RunVersionsRejected(판 이름만 실은 한 문장 — 실행 만들기 409 AI_SETTING_UNUSABLE). versions() 열쇠는
        그대로다.
    inputs_with  열쇠 aiSettingId 가 없으면 옛 실행(IR4 앞) — 코드 값. None 이면 기본 판: promptsSha256 이 있으면 예외,
        modelSettingsSha256 이 지금 명세 기본값의 sha 와 다르면 예외, 같으면 코드 값. 값이면 settings.get(company_id,
        id) 로 **만들 때의 판**을 읽고(그 뒤 적용을 바꿔도 이 판) 「저장 글 있음 ⇔ 열쇠 promptsSha256 있음」을 다른
        대조보다 먼저 본다. 모델·글을 지금 받기로 다시 받아 거절이거나 sha 가 다르면 예외, 같으면 texts_from·
        models_from 값(research·analysis 칸의 route·temperature·위끝). 예외는 core RunVersionsMismatch(실행 error_code
        versions_mismatch — MARC-ENT-352) — 조용히 기본 판으로 가지 않는다(없는 판·남의 회사의 판·int 아닌 id 도).
    옛 판(밴드 IRA3 — MARC-ENT-569): 판 칸이 열넷이 되기 전에 저장한 판(칸 열일곱)은 accept_stored 가 1부 가변 입력
        셋을 그 단계에서만 떼고 받는다(표는 불변 행 — 마이그레이션 0). 새 실행은 열넷 sha 를 싣는다. IRA3 앞에 만든
        실행(열일곱 sha)은 _saved_texts 가 legacy_sha256 과도 견주어 지난다. 어느 쪽이든 셋은 엔진 기본 글이다.
    web_search 는 판과 무관하다(1부 늘 · 2부 latestEventMode — 결정 372·425, 칸의 webSearch 는 받기 고정값).
settings(AiSettingStore)·models(ModelSettingsSource)는 기본값 없이 받는다(빠지면 조용히 기본 판이 되는 길 0).
구현은 service/selectors/ai_settings.py(RunSettingStore — 권한 없는 입구, RunModelSource), apps.py 가 꽂는다.
엔진(engines/*)은 import 하지 않는다 — 글은 colab_155 가 다시 내보낸 PromptTexts·DEFAULT_TEXTS.

이 파일은 순수다(django 0). 설정·환경 변수·키를 읽지 않는다 — 비용 상한은 코드 상수 RUN_MAX_COST_USD 다
(colab_155 에 정의, 여기는 다시 내보냄 — IRS1). 모델 설정은 꽂은 원천(models)으로만 본다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Final, Protocol, cast
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompts,
    ModelSettingRefused,
    PromptRefused,
    ai_versions,
    defaults,
    model_settings_sha256,
    prompts_sha256,
)
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.flows.binding import RunContext, RunOptionsRejected, RunVersionsMismatch, RunVersionsRejected
from esgapi.core.llm.types import Tags
from esgapi.materiality.contracts import wire
from esgapi.materiality.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.materiality.contracts.options_shapes import OPTIONS_SHAPES, SHAPE, MaterialityOptions
from esgapi.materiality.flows import colab_155, iro_155, part2_155
from esgapi.materiality.flows import prompt_model_155 as pm
from esgapi.materiality.flows.colab_155 import DEFAULT_TEXTS, PromptTexts, StageModel
from esgapi.materiality.flows.colab_155 import RUN_MAX_COST_USD as RUN_MAX_COST_USD
from esgapi.materiality.flows.iro_155 import IroAdapters, IroInputs
from esgapi.materiality.flows.prompt_model_155 import ModelSettingsSource

ENGINE: Final = "colab_155"
MODULE: Final = "materiality"
SEOUL: Final = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True, slots=True)
class SavedSetting:
    """회사의 저장된 판 하나(모델 설정·프롬프트 글째)."""

    id: int
    name: str
    model_settings: AiModelSettingsIn
    prompts: AiPromptsIn | None
    """저장 글 정규형(ai.prompts@1). None = 코드 글. 기본값 없음(빠지면 조용히 코드 글이 되는 길 0)."""


@dataclass(frozen=True, slots=True)
class DefaultSetting:
    """적용 판 없음 = 기본 판(코드 값)."""


@dataclass(frozen=True, slots=True)
class SettingNotFound:
    """그 회사에 그 id 의 판이 없다(남의 회사의 판도)."""

    id: int


class AiSettingStore(Protocol):
    """판 읽기 포트(순수). 구현은 service/selectors/ai_settings.RunSettingStore."""

    def applied(self, company_id: int) -> SavedSetting | DefaultSetting: ...

    def get(self, company_id: int, setting_id: int) -> SavedSetting | SettingNotFound: ...


AiSettingMismatch: Final = RunVersionsMismatch
"""실행에 박힌 판을 그대로 다시 지을 수 없다(없는 판·int 아닌 id·sha 다름·지금 받기에 안 맞음). 실행은 실패한다(글은
로그에만). 실행기의 error_code 표가 `<모듈>.<qualname>` 으로 고르므로 core 의 예외 그대로다(이 이름은 별칭)."""

CODE_MODELS: Final = (colab_155.CODE_RESEARCH, part2_155.CODE_ANALYSIS)
"""코드 값의 모델 둘(research·analysis — 흐름 상수 그대로, 기본 판·옛 실행의 요청은 IR4 앞과 바이트 같다)."""


def clock() -> datetime:
    """지금(UTC). 「오늘」의 원천 하나 — 시험은 이 모듈 속성을 갈아 끼운다."""
    return datetime.now(UTC)


def today() -> date:
    """실행 시각의 Asia/Seoul 날짜."""
    return clock().astimezone(SEOUL).date()


_DICT_KEY_FIELDS: Final = frozenset({"subtopicsByTopic"})
"""열쇠를 사용자가 짓는 dict 칸(input@1 에 하나). 거절 문장의 열쇠 길에서 그 바로 아래 마디를 `*` 로 가린다."""


def _path(loc: tuple[int | str, ...]) -> str:
    parts: list[str] = []
    masked = False
    for part in loc:
        if masked:  # dict 칸 바로 아래 = 사용자가 지은 열쇠(int·str 모두)
            parts.append("*")
            masked = False
        elif isinstance(part, str) and part != "[key]":  # 열쇠 꼴 틀림의 표지는 떨군다
            parts.append(part)
            masked = part in _DICT_KEY_FIELDS
    return ".".join(parts)


def _accept(options: Mapping[str, object], day: date) -> MaterialityOptions:
    try:
        accepted = OPTIONS_SHAPES[SHAPE].validate_python(options, strict=True)
    except ValidationError as error:
        errors = error.errors(include_input=False, include_url=False, include_context=False)
        extra = sorted({_path(e["loc"]) for e in errors if e["type"] == "extra_forbidden"})
        if extra:
            raise RunOptionsRejected(f"알 수 없는 옵션이에요: {', '.join(extra)}") from None
        first = errors[0]
        where = _path(first["loc"]) or "전체"
        if first["type"] == "missing":
            raise RunOptionsRejected(f"옵션 {where}이(가) 없어요") from None
        raise RunOptionsRejected(f"옵션 {where}의 값이 맞지 않아요") from None
    if wire.parse_date_range(accepted["input"]["dateRange"], day) is None:
        raise RunOptionsRejected("옵션 input.dateRange의 값이 맞지 않아요")
    return accepted


def accept_options(options: Mapping[str, object]) -> MaterialityOptions:
    """options@1 을 strict 로 받고 dateRange 를 today() 로 읽어 본다. 어기면 RunOptionsRejected(머리말의 차례·문장)."""
    return _accept(options, today())


class MaterialityBinding:
    """materiality.iro@155 의 끼움(머리말)."""

    def __init__(self, *, settings: AiSettingStore, models: ModelSettingsSource) -> None:
        self.settings = settings
        self.models = models

    def check_options(self, options: Mapping[str, object]) -> None:
        accept_options(options)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {
            "engine": ENGINE,
            "flow": iro_155.FLOW_ID,
            "promptIds": {**colab_155.PROMPT_IDS, **part2_155.PROMPT_IDS2},
        }

    def _defaults(self) -> AcceptedModelSettings:
        return defaults(self.models.config(), self.models.steps())

    def _model(self, saved: SavedSetting) -> AcceptedModelSettings | ModelSettingRefused:
        return pm.accept_model(self.models.config(), saved.model_settings, steps=self.models.steps())

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        applied = self.settings.applied(company_id)
        if isinstance(applied, DefaultSetting):
            common = ai_versions(setting_id=None, model=self._defaults(), prompts=None)
            return {**self.versions(options), "aiSetting": DEFAULT_TITLE, **common}
        unusable = RunVersionsRejected(
            f"적용한 AI 설정 판({applied.name})이 지금 규칙에 맞지 않아요. "
            "운영 관리자가 판을 다시 저장해 적용하거나 기본 판으로 되돌려야 해요"
        )
        model = self._model(applied)
        if isinstance(model, ModelSettingRefused):
            raise unusable
        # 옛 판(칸 열일곱)도 셋을 떼고 받는다(accept_stored — MARC-ENT-569)
        texts = None if applied.prompts is None else pm.accept_stored(applied.prompts)
        if isinstance(texts, PromptRefused):
            raise unusable
        # 코드 글 판(texts None)은 열쇠 promptsSha256 을 싣지 않는다(core ai_versions)
        common = ai_versions(setting_id=applied.id, model=model, prompts=texts)
        return {**self.versions(options), "aiSetting": applied.name, **common}

    def inputs(self, options: Mapping[str, object], *, company_id: int) -> IroInputs:
        day = today()  # 한 번 읽어 검사와 입력에 같이 쓴다(자정 경계에서 둘이 갈리지 않게)
        _accept(options, day)
        return self._inputs(options, company_id, day, DEFAULT_TEXTS, CODE_MODELS)

    def inputs_with(
        self, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> IroInputs:
        day = today()  # inputs 와 같다 — 한 번 읽는다
        _accept(options, day)
        texts, models = self._setting(company_id, versions)
        return self._inputs(options, company_id, day, texts, models)

    def _setting(
        self, company_id: int, versions: Mapping[str, object]
    ) -> tuple[PromptTexts, tuple[StageModel, StageModel]]:
        """만들 때 박은 판의 (글, (research, analysis)). 다시 지을 수 없으면 AiSettingMismatch(머리말)."""
        if "aiSettingId" not in versions:
            return DEFAULT_TEXTS, CODE_MODELS  # 열쇠 없는 옛 실행(IR4 앞) — 코드 값
        setting_id = versions["aiSettingId"]
        checks_prompts = "promptsSha256" in versions  # 저장 글 판으로 만든 실행만 열쇠가 있다
        if setting_id is None:
            if checks_prompts:
                raise AiSettingMismatch("기본 판으로 만든 실행에 저장 프롬프트 글의 sha 가 있다")
            if model_settings_sha256(self._defaults()) != versions.get("modelSettingsSha256"):
                raise AiSettingMismatch("기본 판의 모델 설정이 실행을 만들 때와 다르다")
            return DEFAULT_TEXTS, CODE_MODELS
        if not isinstance(setting_id, int) or isinstance(setting_id, bool):
            raise AiSettingMismatch(f"versions.aiSettingId 가 int 가 아니다: {type(setting_id).__name__}")
        found = self.settings.get(company_id, setting_id)
        if isinstance(found, SettingNotFound):
            raise AiSettingMismatch(f"실행의 AI 설정 판 {setting_id} 이 그 회사에 없다")
        if (found.prompts is not None) != checks_prompts:  # 다른 대조보다 먼저
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다")
        model = self._model(found)
        if isinstance(model, ModelSettingRefused):
            raise AiSettingMismatch(
                f"AI 설정 판 {setting_id} 의 모델 설정을 지금 받기로 다시 받을 수 없다: {model.code}"
            )
        if model_settings_sha256(model) != versions.get("modelSettingsSha256"):
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 모델 설정이 실행을 만들 때와 다르다")
        texts = None if found.prompts is None else self._saved_texts(setting_id, found.prompts, versions)
        return pm.texts_from(texts), pm.models_from(model)

    def _saved_texts(self, setting_id: int, saved: AiPromptsIn, versions: Mapping[str, object]) -> AcceptedPrompts:
        """저장 글을 지금 받기(accept_stored)로 다시 받아 만들 때의 sha 와 견준 값. 칸 열넷의 sha 가 다르면 옛 판의
        받은 그대로(열일곱) sha 와도 견준다(IRA3 앞에 만든 실행 — 글은 열넷, 셋은 기본). 어긋나면 AiSettingMismatch."""
        texts = pm.accept_stored(saved)
        if isinstance(texts, PromptRefused):
            raise AiSettingMismatch(
                f"AI 설정 판 {setting_id} 의 프롬프트 글을 지금 받기로 다시 받을 수 없다: {texts.code}"
            )
        made = versions.get("promptsSha256")
        legacy = pm.legacy_sha256(
            saved
        )  # 옛 칸이 없으면 None — None 은 무엇과도 맞지 않는다(null sha 를 지나게 하지 않음)
        if prompts_sha256(texts) != made and (legacy is None or legacy != made):
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 프롬프트 글이 실행을 만들 때와 다르다")
        return texts

    def _inputs(
        self,
        options: Mapping[str, object],
        company_id: int,
        day: date,
        texts: PromptTexts,
        models: tuple[StageModel, StageModel],
    ) -> IroInputs:
        # 검사 결과(복사본 — 열쇠 차례가 꼴의 차례로 바뀐다)가 아니라 받은 것을 넘긴다
        received = cast("Mapping[str, Any]", options["input"])
        research, analysis = models
        return IroInputs(
            received=received,
            tags=Tags(tenant=str(company_id), module=MODULE),
            max_cost_usd=RUN_MAX_COST_USD,
            today=day,
            texts=texts,
            research=research,
            analysis=analysis,
        )

    def adapters(self, ctx: RunContext) -> IroAdapters:
        return IroAdapters(llm=ctx.llm())
