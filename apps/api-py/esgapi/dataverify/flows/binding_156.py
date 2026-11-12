"""흐름 dataverify.colab@156 의 끼움(core/flows/binding.py 의 DocumentlessBinding + DocumentlessFactsBinding — 밴드
DV1d, 문서 없는 흐름 ND1 · AI 설정 판 DVA1 ③). apps.py 의 ready() 가 REGISTRY 곁에 `BINDINGS.register_documentless(
FLOW_ID, DataverifyBinding(settings=…, models=…), max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS)` 로 단다(옵션
상한은 등록 인자 — 256KiB).

    check_options(options)          옵션 꼴 dataverify.options@1 을 strict 로 받는다. 어기면 RunOptionsRejected(<해요체
                                    한 문장 — 열쇠 길만, 값은 싣지 않는다>)
    versions(options)               {"engine": "colab_156", "flow": FLOW_ID, "promptIds": {단계: id}, "route": ROUTE}
    versions_with(options, *, company_id)
                                    만들 때: versions + 판 열쇠(아래 「회사별 AI 설정 판」)
    inputs_with(options, *, company_id, versions)
                                    흐름의 입력. 글·모델 칸은 versions 의 판(아래)
    inputs(options, *, company_id)  inputs_with 의 판 없는 꼴 — DataverifyInputs(received=options["input"] 그대로,
                                    tags=(회사 id 글자, dataverify), max_cost_usd=STAGE_COSTS, web_search=True) 에
                                    코드 값(DEFAULT_TEXTS·CODE_MODEL — 흐름 상수의 route·temperature·위끝)
    adapters(ctx)                   DataverifyAdapters(llm=ctx.llm()) — 호출 기록에 이 실행의 id 가 실린다

받기 차례와 문장(어기는 첫 갈래 하나):
    모르는 열쇠(맨 위·input·company — 항목은 받는다)   「알 수 없는 옵션이에요: <열쇠 길, 쉼표로>」
    빠진 칸                                            「옵션 <열쇠 길>이(가) 없어요」
    그 밖(타입·무늬·schemaVersion 값)                   「옵션 <열쇠 길>의 값이 맞지 않아요」
  input 의 판정은 shapes.check_input 과 같다(strict — options 꼴이 shapes.DataverifyInput 을 그대로 싣는다).
  source(DV1f)는 kind 로 가르는 갈래라 pydantic 의 loc 에 갈래 꼬리표(file·paste)가 끼는데, 열쇠 길에서는 뺀다
  (source.file.name → source.name). 모르는 kind·kind 없음·글자는 「옵션 source의 값이 맞지 않아요」다.

받은 input 은 고치지 않고 넘긴다(DV1a §1-9 — 프롬프트가 글자째 싣는다). 실행 행의 options 는 열쇠 차례를 지키는 칸이라
(runs OrderedJSONField — ND1) 실행기를 거쳐도 프롬프트 글이 run_flow 에 바로 넣은 것과 같다.

회사별 AI 설정 판(밴드 DVA1 ③ — 결정 MARC-ENT-399·381·387·352, 영문번역 binding_158 의 꼴):
    versions_with  settings.applied(company_id) — 기본 판이면 {**versions, aiSetting: DEFAULT_TITLE, **ai_versions(None,
        명세 기본값, None)}. 저장 판이면 저장 모델 설정·글을 지금 받기(prompt_model_156.accept_model·accept_prompts)로
        **다시 받아** {**versions, aiSetting: 판 이름, **ai_versions(판 id, 받은 모델, 받은 글|None)}. 다시 받기
        거절이면 RunVersionsRejected(판 이름만 실은 한 문장 — 실행 만들기 409 AI_SETTING_UNUSABLE). versions() 열쇠는
        그대로다.
    inputs_with  열쇠 aiSettingId 가 없으면 옛 실행(DVA1 앞) — 코드 값. None 이면 기본 판: promptsSha256 이 있으면 예외,
        modelSettingsSha256 이 지금 명세 기본값의 sha 와 다르면 예외, 같으면 코드 값. 값이면 settings.get(company_id,
        id) 로 **만들 때의 판**을 읽고(그 뒤 적용을 바꿔도 이 판) 「저장 글 있음 ⇔ 열쇠 promptsSha256 있음」을 다른
        대조보다 먼저 본다. 모델·글을 지금 받기로 다시 받아 거절이거나 sha 가 다르면 예외, 같으면 texts_from·
        models_from 값. 예외는 core RunVersionsMismatch(실행 error_code versions_mismatch — MARC-ENT-352) — 조용히
        기본 판으로 가지 않는다(없는 판·남의 회사의 판·int 아닌 id 도).
    web_search 는 판과 무관하게 True 다(결정 372·303 — 칸의 webSearch 는 5a 로 고정, 실행이 칸 값으로 켜고 끄지 않음).
settings(AiSettingStore)·models(ModelSettingsSource)는 기본값 없이 받는다(빠지면 조용히 기본 판이 되는 길 0).
구현은 service/selectors/ai_settings.py(RunSettingStore — 권한 없는 입구, RunModelSource), apps.py 가 꽂는다.

이 파일은 순수다(django 0). 설정·환경 변수·키를 읽지 않는다 — 비용 상한은 코드 상수 STAGE_COSTS 다. 모델 설정은 꽂은
원천(models)으로만 본다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Protocol, cast

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
from esgapi.dataverify.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.dataverify.contracts.options_shapes import OPTIONS_SHAPES, SHAPE, DataverifyOptions
from esgapi.dataverify.engines.colab_156 import prompts
from esgapi.dataverify.engines.colab_156.prompts import PromptTexts
from esgapi.dataverify.flows import colab_156
from esgapi.dataverify.flows import prompt_model_156 as pm
from esgapi.dataverify.flows.colab_156 import DataverifyAdapters, DataverifyInputs, StageCosts
from esgapi.dataverify.flows.prompt_model_156 import ModelSettingsSource, StageModel

ENGINE: Final = "colab_156"
MODULE: Final = "dataverify"
STAGE_COSTS: Final = StageCosts(plan=1.0, review=3.0, insight=1.0)
"""단계마다 고리 한 번의 비용 상한(USD). 합 5 USD 로 MARC-ENT-262 의 한 번 5 USD 선 안(DV1b 처분 ② 예시, DV1d Q4).
무효 조건: 실호출을 켜는 밴드(runs/context.py 가 키를 싣는 때)가 오면 그 발주서에서 다시 정한다(MARC-ISSUE-206 4번)."""


CODE_MODEL: Final = StageModel(
    route=colab_156.ROUTE, temperature=colab_156.TEMPERATURE, max_output_tokens=colab_156.MAX_OUTPUT_TOKENS
)
"""코드 값의 모델(흐름 상수 그대로 — 기본 판·옛 실행의 요청은 DVA1 앞과 바이트 같다)."""


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


_SOURCE_TAGS: Final = frozenset({"file", "paste"})
"""source 갈래의 꼬리표(options_shapes.DataverifySource 의 kind 값)."""


def _path(loc: tuple[int | str, ...]) -> str:
    if loc[:1] == ("source",) and len(loc) > 1 and loc[1] in _SOURCE_TAGS:
        loc = loc[:1] + loc[2:]
    return ".".join(str(part) for part in loc if isinstance(part, str))


def accept_options(options: Mapping[str, object]) -> DataverifyOptions:
    """options@1 을 strict 로 받는다. 어기면 RunOptionsRejected(머리말의 차례·문장)."""
    try:
        return OPTIONS_SHAPES[SHAPE].validate_python(options, strict=True)
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


class DataverifyBinding:
    """dataverify.colab@156 의 끼움(머리말)."""

    def __init__(self, *, settings: AiSettingStore, models: ModelSettingsSource) -> None:
        self.settings = settings
        self.models = models

    def check_options(self, options: Mapping[str, object]) -> None:
        accept_options(options)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {
            "engine": ENGINE,
            "flow": colab_156.FLOW_ID,
            "promptIds": dict(prompts.PROMPT_IDS),
            "route": colab_156.ROUTE,
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
        texts = None if applied.prompts is None else pm.accept_prompts(applied.prompts)
        if isinstance(texts, PromptRefused):
            raise unusable
        # 코드 글 판(texts None)은 열쇠 promptsSha256 을 싣지 않는다(core ai_versions)
        common = ai_versions(setting_id=applied.id, model=model, prompts=texts)
        return {**self.versions(options), "aiSetting": applied.name, **common}

    def inputs(self, options: Mapping[str, object], *, company_id: int) -> DataverifyInputs:
        accept_options(options)
        return self._inputs(options, company_id, prompts.DEFAULT_TEXTS, CODE_MODEL)

    def inputs_with(
        self, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> DataverifyInputs:
        accept_options(options)
        texts, model = self._setting(company_id, versions)
        return self._inputs(options, company_id, texts, model)

    def _setting(self, company_id: int, versions: Mapping[str, object]) -> tuple[PromptTexts, StageModel]:
        """만들 때 박은 판의 (글, 모델). 다시 지을 수 없으면 AiSettingMismatch(머리말)."""
        if "aiSettingId" not in versions:
            return prompts.DEFAULT_TEXTS, CODE_MODEL  # 열쇠 없는 옛 실행(DVA1 앞) — 코드 값
        setting_id = versions["aiSettingId"]
        checks_prompts = "promptsSha256" in versions  # 저장 글 판으로 만든 실행만 열쇠가 있다
        if setting_id is None:
            if checks_prompts:
                raise AiSettingMismatch("기본 판으로 만든 실행에 저장 프롬프트 글의 sha 가 있다")
            if model_settings_sha256(self._defaults()) != versions.get("modelSettingsSha256"):
                raise AiSettingMismatch("기본 판의 모델 설정이 실행을 만들 때와 다르다")
            return prompts.DEFAULT_TEXTS, CODE_MODEL
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
        """저장 글을 지금 받기로 다시 받아 만들 때의 sha 와 견준 값. 어긋나면 AiSettingMismatch."""
        texts = pm.accept_prompts(saved)
        if isinstance(texts, PromptRefused):
            raise AiSettingMismatch(
                f"AI 설정 판 {setting_id} 의 프롬프트 글을 지금 받기로 다시 받을 수 없다: {texts.code}"
            )
        if prompts_sha256(texts) != versions.get("promptsSha256"):
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 프롬프트 글이 실행을 만들 때와 다르다")
        return texts

    def _inputs(
        self, options: Mapping[str, object], company_id: int, texts: PromptTexts, model: StageModel
    ) -> DataverifyInputs:
        # 검사 결과(복사본 — 열쇠 차례가 꼴의 차례로 바뀐다)가 아니라 받은 것을 넘긴다
        received = cast("Mapping[str, Any]", options["input"])
        return DataverifyInputs(
            received=received,
            tags=Tags(tenant=str(company_id), module=MODULE),
            max_cost_usd=STAGE_COSTS,
            texts=texts,
            temperature=model.temperature,
            route=model.route,
            max_output_tokens=model.max_output_tokens,
            web_search=True,
        )

    def adapters(self, ctx: RunContext) -> DataverifyAdapters:
        return DataverifyAdapters(llm=ctx.llm())
