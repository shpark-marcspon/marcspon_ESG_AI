"""흐름 translation.colab@158 의 끼움(core/flows/binding.py 의 RunBinding + RunFactsBinding — 밴드 TR2).
apps.py 의 ready() 가 REGISTRY 곁에 `BINDINGS.register(FLOW_ID, TranslationBinding(store=…, settings=…, models=…,
max_usd=…, mock=…, spent_usd=…))` 로 단다.

    check_options(options)     옵션 꼴 translation.options@1 을 strict 로 받는다. 어기면 RunOptionsRejected(<해요체 한
                               문장 — 열쇠 이름만, 값은 싣지 않는다>)
    versions(options)          {"engine": "colab_158", "flow": FLOW_ID, "promptIds": [...]}
                               (판은 versions — MARC-ENT-210 (2))
    versions_with(options, *, company_id)
                               만들 때: versions + 판 열쇠(밴드 TR4 ③ — 아래 「회사별 AI 설정 판」)
    inputs_with(document, options, *, company_id, versions)
                               흐름의 입력. retry 가 있으면 store.base(company_id, fromRunId) 의 갈래와 이번 versions 의
                               판 열쇠(colab.ai_key — MARC-ISSUE-326)를 싣는다(남의 회사 실행은 store 가 없는 실행으로
                               돌려준다). 금액 상한은 max_usd() 를 **돌 때** 부른다.
                               글·모델 칸은 versions 의 판(아래).
    inputs(document, options)  inputs_with 의 회사 없는 꼴 — retry 가 있으면 앞 실행을 못 읽어 not_found 갈래. 글·모델은
                               코드 값(DEFAULT_TEXTS·DEFAULT_MODELS).
    adapters(ctx)              TranslationAdapters(llm=ctx.llm(), tenant=str(ctx.company_id), mock=mock())
                               mock = 실행기가 모의 공급사만 싣는가(apps.py 가 꽂은 함수 — runs/context.py 와 같은 원천
                               run_mode). 참이면 흐름이 모델 칸 대신 MOCK_MODELS 로 부른다(MARC-ISSUE-331)
                               spent_usd = 그 실행의 지출을 읽는 함수(회사·실행 id 를 묶음 — apps.py 가 꽂은
                               spent_usd(company_id, run_id), MARC-ISSUE-268 의 시도를 넘는 금액 상한)

받기 차례와 문장(어기는 첫 것 하나):
    모르는 열쇠(어느 깊이든)            「알 수 없는 옵션이에요: <열쇠 길, 쉼표로>」
    그 밖의 꼴(빠진 칸·타입·범위)        「옵션 <열쇠 길>의 값이 맞지 않아요」
    retry.pages 의 겹침                  「다시 번역할 쪽 번호가 겹쳐요」

회사별 AI 설정 판(밴드 TR4 ③ — 결정 MARC-ENT-399·381·387, 그린워싱 binding_e0 의 꼴):
    versions_with  settings.applied(company_id) — 기본 판이면 {**versions, aiSetting: DEFAULT_TITLE, **ai_versions(None,
        명세 기본값, None)}. 저장 판이면 저장 모델 설정·글을 지금 받기(prompt_model_158.accept_model·accept_prompts)로
        **다시 받아** {**versions, aiSetting: 판 이름, **ai_versions(판 id, 받은 모델, 받은 글|None)}. 다시 받기
        거절이면 RunVersionsRejected(판 이름만 실은 한 문장 — 실행 만들기 409 AI_SETTING_UNUSABLE). 공통 열쇠
        (aiSettingId·modelSettingsSha256·promptsSha256)는 core ai_versions 가, aiSetting 은 이 파일이 짓는다.
    inputs_with  열쇠 aiSettingId 가 없으면 옛 실행(TR4 앞) — 코드 값. None 이면 기본 판: promptsSha256 이 있으면 예외,
        modelSettingsSha256 이 지금 명세 기본값의 sha 와 다르면 예외, 같으면 코드 값. 값이면 settings.get(company_id,
        id) 로 **만들 때의 판**을 읽고(그 뒤 적용을 바꿔도 이 판) 「저장 글 있음 ⇔ 열쇠 promptsSha256 있음」을 다른
        대조보다 먼저 본다. 모델·글을 지금 받기로 다시 받아 거절이거나 sha 가 다르면 예외, 같으면 texts_from·
        models_from 값. 예외는 core RunVersionsMismatch(실행 error_code versions_mismatch — MARC-ENT-352) — 조용히
        기본 판으로 가지 않는다(없는 판·남의 회사의 판·int 아닌 id 도).
    코드 값 = DEFAULT_TEXTS·DEFAULT_MODELS(다리를 지은 그대로 — 기본 판·옛 실행의 요청은 TR4 앞과 바이트 같다).
    sha 는 경로 이름과 풀린 api_model_id 를 품는다 — 배포로 models.json 의 짝이 바뀌면 그 전에 만든 실행은
    versions_mismatch 로 끝난다(그린워싱과 같음).
store·settings(AiSettingStore)·models(ModelSettingsSource)는 기본값 없이 받는다(빠지면 조용히 기본 판이 되는 길 0).
구현은 service/selectors/ai_settings.py(RunSettingStore — 권한 없는 입구, RunModelSource), apps.py 가 꽂는다.

이 파일은 순수다(django 0). 설정·키를 읽지 않는다 — 금액 상한·mock 여부는 apps.py 가 꽂은 함수(max_usd·mock)로만,
모델 설정은 꽂은 원천(models)으로만.
"""

from collections.abc import Callable, Mapping
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
from esgapi.core.flows.binding import (
    DocumentInput,
    RunContext,
    RunOptionsRejected,
    RunVersionsMismatch,
    RunVersionsRejected,
)
from esgapi.translation.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.translation.contracts.options_shapes import OPTIONS_SHAPES, SHAPE, TranslationOptions
from esgapi.translation.engines.colab_158.texts import DEFAULT_TEXTS, PromptTexts
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows import prompt_model_158 as pm
from esgapi.translation.flows.colab_158 import RetryNotFound, RetryRequest, RetrySource
from esgapi.translation.flows.prompt_model_158 import ModelSettingsSource
from esgapi.translation.tools.llm_bridge import DEFAULT_MODELS, TranslationModels, prompt_ids

ENGINE: Final = "colab_158"


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


class RetrySourceStore(Protocol):
    """앞 실행 읽기 포트(순수). 구현은 service/actions/retry_source.py — 회사 조건·module translation·done·결과
    translation.result@1 의 status done 만 RetryFound."""

    def base(self, company_id: int, run_id: int) -> RetrySource: ...


def _path(loc: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in loc if isinstance(part, str))


def accept_options(options: Mapping[str, object]) -> TranslationOptions:
    """options@1 을 strict 로 받는다. 어기면 RunOptionsRejected(머리말의 차례·문장)."""
    try:
        accepted = OPTIONS_SHAPES[SHAPE].validate_python(options, strict=True)
    except ValidationError as error:
        errors = error.errors(include_input=False, include_url=False, include_context=False)
        extra = sorted({_path(e["loc"]) for e in errors if e["type"] == "extra_forbidden"})
        if extra:
            raise RunOptionsRejected(f"알 수 없는 옵션이에요: {', '.join(extra)}") from None
        raise RunOptionsRejected(f"옵션 {_path(errors[0]['loc']) or '전체'}의 값이 맞지 않아요") from None
    retry = accepted.get("retry")
    if retry is not None and len(set(retry["pages"])) != len(retry["pages"]):
        raise RunOptionsRejected("다시 번역할 쪽 번호가 겹쳐요")
    return accepted


class TranslationBinding:
    """translation.colab@158 의 끼움(머리말)."""

    def __init__(
        self,
        *,
        store: RetrySourceStore,
        settings: AiSettingStore,
        models: ModelSettingsSource,
        max_usd: Callable[[], float],
        mock: Callable[[], bool],
        spent_usd: Callable[[int, int], float],
    ) -> None:
        self.store = store
        self.settings = settings
        self.models = models
        self.max_usd = max_usd
        self.mock = mock
        self.spent_usd = spent_usd

    def check_options(self, options: Mapping[str, object]) -> None:
        accept_options(options)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {"engine": ENGINE, "flow": colab.FLOW_ID, "promptIds": prompt_ids()}

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

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> colab.TranslationRunInputs:
        return self._inputs(
            document, accept_options(options), lambda _run_id: RetryNotFound(), None, DEFAULT_TEXTS, DEFAULT_MODELS
        )

    def inputs_with(
        self, document: DocumentInput, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> colab.TranslationRunInputs:
        accepted = accept_options(options)
        texts, models = self._setting(company_id, versions)
        key = colab.ai_key(versions)
        return self._inputs(document, accepted, lambda run_id: self.store.base(company_id, run_id), key, texts, models)

    def _setting(self, company_id: int, versions: Mapping[str, object]) -> tuple[PromptTexts, TranslationModels]:
        """만들 때 박은 판의 (글, 모델 칸). 다시 지을 수 없으면 AiSettingMismatch(머리말)."""
        if "aiSettingId" not in versions:
            return DEFAULT_TEXTS, DEFAULT_MODELS  # 열쇠 없는 옛 실행(TR4 앞) — 코드 값
        setting_id = versions["aiSettingId"]
        checks_prompts = "promptsSha256" in versions  # 저장 글 판으로 만든 실행만 열쇠가 있다
        if setting_id is None:
            if checks_prompts:
                raise AiSettingMismatch("기본 판으로 만든 실행에 저장 프롬프트 글의 sha 가 있다")
            if model_settings_sha256(self._defaults()) != versions.get("modelSettingsSha256"):
                raise AiSettingMismatch("기본 판의 모델 설정이 실행을 만들 때와 다르다")
            return DEFAULT_TEXTS, DEFAULT_MODELS
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
        self,
        document: DocumentInput,
        options: TranslationOptions,
        read: Callable[[int], RetrySource],
        key: colab.AiKey | None,
        texts: PromptTexts,
        models: TranslationModels,
    ) -> colab.TranslationRunInputs:
        glossary = cast("Mapping[str, Any]", options.get("glossary", {}))
        peer = options.get("peerGroupStyle")
        pages = options["pages"]
        retry_option = options.get("retry")
        retry = None
        if retry_option is not None:
            from_run_id = retry_option["fromRunId"]
            retry = RetryRequest(
                from_run_id=from_run_id, pages=tuple(retry_option["pages"]), source=read(from_run_id), ai_key=key
            )
        company = options["company"]
        style = options["style"]
        return colab.TranslationRunInputs(
            document=document.content,
            company_name=company["name"],
            preferred_subject=company["preferredSubject"],
            industry_standards=company["industryStandards"],
            glossary_base=tuple((p["ko"], p["en"]) for p in glossary.get("base", [])),
            glossary_final=tuple((p["ko"], p["en"]) for p in glossary.get("final", [])),
            part=options["part"],
            compare_ab=style["compareAb"],
            single_style=style["single"],
            peer_group_style_prompt=None if peer is None else peer["prompt"],
            page_start=pages["start"],
            page_end=pages["end"],
            ceo_page_limit=options["ceoPageLimit"],
            autofix=options.get("autofix", True),
            retry=retry,
            max_usd=self.max_usd(),
            texts=texts,
            models=models,
        )

    def adapters(self, ctx: RunContext) -> colab.TranslationAdapters:
        company_id, run_id = ctx.company_id, ctx.run_id
        return colab.TranslationAdapters(
            llm=ctx.llm(),
            tenant=str(ctx.company_id),
            mock=self.mock(),
            spent_usd=lambda: self.spent_usd(company_id, run_id),
        )
