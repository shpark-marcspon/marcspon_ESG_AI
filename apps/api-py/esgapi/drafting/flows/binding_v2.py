"""drafting.draft@v2 의 끼움(밴드 RP2b 가 v1 을 갈음. 문서 없는 흐름 — 처분 ① 가, DocumentlessFactsBinding). 실행
행의 documentId 는 null 이고
문서는 프로젝트에 달린 것을 끼움이 만들 때 versions 에 박는다.

    check_options(options)          options@2 strict(base.rebuild 겹침도). 어기면 RunOptionsRejected(해요체 한 문장 —
                                    값 0)
    versions(options)               {engine, flow, promptIds, adapter, parserLayout, epoch, segmenter, reuse, texts} —
                                    쪽 글
                                    어댑터 drafting-blocks@1 · 분해 판 2 · core 산출물 EPOCH(밴드 RP2a ②) · 문장
                                    나누기 판
                                    (engines/v2/sentences — 바뀌면 문장 번호가 갈린다, §2-0 ⑩) · 이어 받기 규칙 판
                                    (flows/reuse — 밴드 RP2c). 옵션의 base 는 싣지 않는다(옵션에 있다)
    versions_with(options, company) + 지금 목차 판 {outlineId, outlineSha256} · 지금 문서 {documentId, documentEtag}
                                    · AI 설정 판 열쇠(아래 「회사별 AI 설정 판」).
                                    프로젝트 없음(남의 회사도)·목차 없음·문서 없음·문서 올림 미완·etag 없음(474) →
                                    RunVersionsRejected(만들기 409 — 프로젝트 없음과 남의 회사는 같은 글). 옵션 base 가
                                    있으면 앞 실행이 없음·남의 회사·원고작성 아님·끝나지 않음·다른 프로젝트·결과 @3
                                    없음 → 한 글(BASE_MISSING), rebuild 가 지금 목차 잎 밖 → REBUILD_OUTSIDE
    inputs_with(options, company, versions)  글·모델 칸은 versions 의 AI 설정 판(아래). 판 id 로 목차를 읽어 판의
                                    프로젝트·회사 대조 + sha 다시 셈. 다르거나 열쇠
                                    빠짐·etag 가 글이 아님 → RunVersionsMismatch(실행 실패). 큐 중에 목차를 고쳐도
                                    만들 때의 판을 읽는다. base 가 있으면 앞 실행을 다시 읽어(사라졌으면 Mismatch) 앞
                                    목차
                                    판·versions 같음(FACT_KEYS 뺌)·결과를 DraftInputs.base 에
    inputs(options, company)        versions_with → inputs_with 를 이음(판 묶음 없이 부르는 길)
    adapters(ctx)                   DraftAdapters(llm·mock·spent_usd·artifacts — 회사·실행은 ctx 에서)

글 판(RPQ1): versions 열쇠 texts = engines/v2/texts.TEXTS_VERSION. same_versions 가 저절로 견주어 옛 글로 지은 앞
    실행은 이어 받지 않는다(reason versions). inputs_with 는 열쇠가 있고 지금 글 판과 다르면 다른 대조보다 먼저
    RunVersionsMismatch, 열쇠가 없으면(RPQ1 앞 실행) 지금 코드 글 — 옛 실행 규칙(아래 aiSettingId 없음)과 같은 꼴.

회사별 AI 설정 판(밴드 RPA1 ② — 결정 MARC-ENT-399·381·387·352, 데이터 검증 binding_156 의 꼴):
    versions_with  위 판정 뒤 settings.applied(company_id) — 기본 판이면 {…, aiSetting: DEFAULT_TITLE,
        **ai_versions(None, 명세 기본값, None)}. 저장 판이면 저장 모델 설정·글을 지금 받기
        (prompt_model_v2.accept_model·accept_prompts)로 **다시 받아** {…, aiSetting: 판 이름,
        **ai_versions(판 id, 받은 모델, 받은 글|None)}. 다시 받기 거절이면 RunVersionsRejected(판 이름만 실은 한
        문장 — 실행 만들기 409 AI_SETTING_UNUSABLE).
    inputs_with  열쇠 aiSettingId 가 없으면 옛 실행(RPA1 앞) — 코드 값(DEFAULT_TEXTS·CODE_MODELS). None 이면 기본 판:
        promptsSha256 이 있으면 예외, modelSettingsSha256 이 지금 명세 기본값의 sha 와 다르면 예외, 같으면 코드 값.
        값이면 settings.get(company_id, id) 로 **만들 때의 판**을 읽고(그 뒤 적용을 바꿔도 이 판) 「저장 글 있음 ⇔ 열쇠
        promptsSha256 있음」을 다른 대조보다 먼저 본다. 모델·글을 지금 받기로 다시 받아 거절이거나 sha 가 다르면 예외,
        같으면 texts_from·models_from 값. 예외는 core RunVersionsMismatch(실행 error_code versions_mismatch) — 조용히
        기본 판으로 가지 않는다(없는 판·남의 회사의 판·int 아닌 id 도).
    AI 열쇠는 versions 에 들어 same_versions 가 견준다 — 판이 다른 앞 실행은 이어 받지 않는다(reason versions, 처분 ⑤).
    고정 꼬리(MARKER_RULES·WRITING_RULES)는 칸 밖이라 저장 draft_system 뒤에도 흐름이 붙인다(처분 ⑦ · RPQ1).

포트는 기본값 없이 꽂는다(빠지면 조용히 다른 원천이 되는 길 0): projects(판·문서 읽기)·max_usd·mock·spent_usd·artifacts
(core 문서 산출물 — 회사를 받는 꼴)·bases(앞 실행 읽기 — runs 의 회사 조건 selector 로만)·settings(AI 설정 판 읽기 —
service/selectors/ai_settings.RunSettingStore)·models(모델 설정 원천 — RunModelSource). 몸은
service/actions/run_sources.py·service/selectors/ai_settings.py, 꽂는 자리는 apps.py.
RPA1 은 엔진 0줄, 흐름은 입력 칸(models)만 바꿨다.
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
from esgapi.core.documents.contract import EPOCH, ArtifactRef, ArtifactRefused, ArtifactUnreadable
from esgapi.core.documents.view import DocArtifactView
from esgapi.core.flows.binding import RunContext, RunOptionsRejected, RunVersionsMismatch, RunVersionsRejected
from esgapi.core.llm.types import Tags
from esgapi.drafting.contracts import wire
from esgapi.drafting.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.drafting.contracts.options_shapes import OPTIONS_SHAPES, SHAPE, DraftingOptions
from esgapi.drafting.engines.v2 import sentences
from esgapi.drafting.engines.v2 import texts as v2_texts
from esgapi.drafting.flows import draft_v2, reuse
from esgapi.drafting.flows import prompt_model_v2 as pm
from esgapi.drafting.flows.draft_v2 import (
    CODE_MODELS,
    DEFAULT_TEXTS,
    DraftAdapters,
    DraftInputs,
    PromptTexts,
    StageModels,
)
from esgapi.drafting.flows.prompt_model_v2 import ModelSettingsSource
from esgapi.drafting.tools import blocks_text

ENGINE: Final = "v2"
PARSER_LAYOUT: Final = 2
FACT_KEYS: Final = ("outlineId", "outlineSha256", "documentId", "documentEtag")
NO_PROJECT: Final = "원고작성 프로젝트를 찾을 수 없어요"
NO_OUTLINE: Final = "프로젝트에 목차가 없어요. 목차를 먼저 넣어 주세요"
NO_DOCUMENT: Final = "프로젝트에 전년도 보고서가 없어요. 문서를 먼저 달아 주세요"
NOT_UPLOADED: Final = "프로젝트의 전년도 보고서 올림이 끝나지 않았어요"
BASE_MISSING: Final = "이어 받을 앞 실행을 찾을 수 없어요"
REBUILD_OUTSIDE: Final = "다시 만들 목차가 지금 목차에 없어요"
REBUILD_TWICE: Final = "다시 만들 목차가 겹쳐요"


@dataclass(frozen=True, slots=True)
class ProjectFacts:
    """프로젝트의 지금 판(만들 때 읽음). outline_id·document_id 는 없으면 None."""

    project_id: int
    outline_id: int | None
    outline_sha256: str | None
    document_id: int | None


@dataclass(frozen=True, slots=True)
class OutlineFacts:
    project_id: int
    sha256: str
    outline: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class DocumentFacts:
    uploaded: bool
    etag: str | None


@dataclass(frozen=True, slots=True)
class BaseFacts:
    """앞 실행(회사 조건으로 읽은 원고작성 실행). project_id 는 그 옵션의 projectId(int 가 아니면 None), result 는 결과
    drafting.bullets@3 본문(없으면 None)."""

    run_id: int
    project_id: int | None
    status: str
    versions: Mapping[str, object]
    result: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class SavedSetting:
    """회사의 저장된 AI 설정 판 하나(모델 설정·프롬프트 글째)."""

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
"""실행에 박힌 판을 그대로 다시 지을 수 없다(없는 판·int 아닌 id·sha 다름·지금 받기에 안 맞음). 실행은 실패한다.
실행기의 error_code 표가 `<모듈>.<qualname>` 으로 고르므로 core 의 예외 그대로다(이 이름은 별칭)."""


class BaseSource(Protocol):
    def base(self, company_id: int, run_id: int) -> BaseFacts | None:
        """그 회사의 그 원고작성 실행(없음·남의 회사·다른 모듈은 None)."""
        ...


class ProjectSource(Protocol):
    def project(self, company_id: int, project_id: int) -> ProjectFacts | None: ...

    def outline(self, company_id: int, outline_id: int) -> OutlineFacts | None: ...

    def document(self, company_id: int, document_id: int) -> DocumentFacts | None: ...


class CompanyArtifacts(Protocol):
    def ensure(
        self, company_id: int, document_id: int, etag: str
    ) -> ArtifactRef | ArtifactRefused | ArtifactUnreadable: ...

    def view(self, company_id: int, document_id: int, artifact_id: int, *, places: bool = False) -> DocArtifactView: ...

    def file_name(self, company_id: int, document_id: int) -> str | None: ...


@dataclass(frozen=True, slots=True)
class _Scoped:
    """실행의 회사를 묶은 산출물 읽기(흐름의 ArtifactSource). 뷰는 그 문서에 이어진 산출물만 연다."""

    artifacts: CompanyArtifacts
    company_id: int

    def ensure(self, document_id: int, etag: str) -> ArtifactRef | ArtifactRefused | ArtifactUnreadable:
        return self.artifacts.ensure(self.company_id, document_id, etag)

    def view(self, document_id: int, artifact_id: int, *, places: bool = False) -> DocArtifactView:
        return self.artifacts.view(self.company_id, document_id, artifact_id, places=places)

    def file_name(self, document_id: int) -> str | None:
        return self.artifacts.file_name(self.company_id, document_id)


def _accepted(options: Mapping[str, object]) -> DraftingOptions:
    """options@2 strict + rebuild 겹침."""
    try:
        OPTIONS_SHAPES[SHAPE].validate_python(options, strict=True)
    except ValidationError as error:
        errors = error.errors()
        if any(e["type"] == "extra_forbidden" for e in errors):
            raise RunOptionsRejected("알 수 없는 옵션이에요") from None
        if any(e["loc"][:1] == ("base",) for e in errors):
            raise RunOptionsRejected("옵션 base의 값이 맞지 않아요") from None
        if any(e["type"] == "missing" for e in errors):
            raise RunOptionsRejected("옵션 projectId가 없어요") from None
        raise RunOptionsRejected("옵션 projectId의 값이 맞지 않아요") from None
    accepted = cast("DraftingOptions", options)  # 꼴 검사를 지난 값
    if "base" in accepted and len(set(accepted["base"]["rebuild"])) != len(accepted["base"]["rebuild"]):
        raise RunOptionsRejected(REBUILD_TWICE)
    return accepted


def accept_options(options: Mapping[str, object]) -> int:
    """options@2 를 strict 로 받아 projectId 를 돌려준다."""
    return _accepted(options)["projectId"]


def same_versions(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    """두 versions 가 FACT_KEYS(목차·문서 판)를 빼고 같은가."""
    return {k: v for k, v in left.items() if k not in FACT_KEYS} == {
        k: v for k, v in right.items() if k not in FACT_KEYS
    }


class DraftingBinding:
    """drafting.draft@v2 의 끼움(머리말)."""

    def __init__(
        self,
        *,
        projects: ProjectSource,
        max_usd: Callable[[], float],
        mock: Callable[[], bool],
        spent_usd: Callable[[int, int], float],
        artifacts: CompanyArtifacts,
        bases: BaseSource,
        settings: AiSettingStore,
        models: ModelSettingsSource,
    ) -> None:
        self.projects = projects
        self.max_usd = max_usd
        self.mock = mock
        self.spent_usd = spent_usd
        self.artifacts = artifacts
        self.bases = bases
        self.settings = settings
        self.models = models

    def check_options(self, options: Mapping[str, object]) -> None:
        accept_options(options)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {
            "engine": ENGINE,
            "flow": draft_v2.FLOW_ID,
            "promptIds": dict(draft_v2.PROMPT_IDS),
            "adapter": blocks_text.ADAPTER,
            "parserLayout": PARSER_LAYOUT,
            "epoch": EPOCH,
            "segmenter": sentences.SEGMENTER,
            "reuse": reuse.REUSE_VERSION,
            "texts": v2_texts.TEXTS_VERSION,
        }

    def _base(self, company_id: int, project_id: int, run_id: int) -> BaseFacts | None:
        """이어 받을 수 있는 앞 실행(같은 프로젝트·done·결과 @3), 아니면 None."""
        found = self.bases.base(company_id, run_id)
        if found is None or found.status != "done" or found.project_id != project_id or found.result is None:
            return None
        return found

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        accepted = _accepted(options)
        project = self.projects.project(company_id, accepted["projectId"])
        if project is None:
            raise RunVersionsRejected(NO_PROJECT)
        if project.outline_id is None or project.outline_sha256 is None:
            raise RunVersionsRejected(NO_OUTLINE)
        if project.document_id is None:
            raise RunVersionsRejected(NO_DOCUMENT)
        document = self.projects.document(company_id, project.document_id)
        if document is None or not document.uploaded or document.etag is None:
            raise RunVersionsRejected(NOT_UPLOADED)
        if "base" in accepted:
            if self._base(company_id, project.project_id, accepted["base"]["runId"]) is None:
                raise RunVersionsRejected(BASE_MISSING)
            current = self.projects.outline(company_id, project.outline_id)
            leaves: set[str] = set() if current is None else set(wire.leaf_keys(current.outline["nodes"]))
            if not set(accepted["base"]["rebuild"]) <= leaves:
                raise RunVersionsRejected(REBUILD_OUTSIDE)
        return {
            **self.versions(options),
            "outlineId": project.outline_id,
            "outlineSha256": project.outline_sha256,
            "documentId": project.document_id,
            "documentEtag": document.etag,
            **self._ai_versions(company_id),
        }

    def _defaults(self) -> AcceptedModelSettings:
        return defaults(self.models.config(), self.models.steps())

    def _model(self, saved: SavedSetting) -> AcceptedModelSettings | ModelSettingRefused:
        return pm.accept_model(self.models.config(), saved.model_settings, steps=self.models.steps())

    def _ai_versions(self, company_id: int) -> dict[str, object]:
        """적용 판의 열쇠(머리말 「회사별 AI 설정 판」 versions_with)."""
        applied = self.settings.applied(company_id)
        if isinstance(applied, DefaultSetting):
            return {"aiSetting": DEFAULT_TITLE, **ai_versions(setting_id=None, model=self._defaults(), prompts=None)}
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
        return {"aiSetting": applied.name, **ai_versions(setting_id=applied.id, model=model, prompts=texts)}

    def _setting(self, company_id: int, versions: Mapping[str, object]) -> tuple[PromptTexts, StageModels]:
        """만들 때 박은 판의 (글, 모델). 다시 지을 수 없으면 AiSettingMismatch(머리말)."""
        if "texts" in versions and versions["texts"] != v2_texts.TEXTS_VERSION:  # 모든 갈래 전(옛 실행 갈래 포함)
            raise AiSettingMismatch("versions.texts 가 지금 글 판과 다르다")
        if "aiSettingId" not in versions:
            return DEFAULT_TEXTS, CODE_MODELS  # 열쇠 없는 옛 실행(RPA1 앞) — 코드 값
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
        """저장 글을 지금 받기로 다시 받아 만들 때의 sha 와 견준 값. 어긋나면 AiSettingMismatch."""
        texts = pm.accept_prompts(saved)
        if isinstance(texts, PromptRefused):
            raise AiSettingMismatch(
                f"AI 설정 판 {setting_id} 의 프롬프트 글을 지금 받기로 다시 받을 수 없다: {texts.code}"
            )
        if prompts_sha256(texts) != versions.get("promptsSha256"):
            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 프롬프트 글이 실행을 만들 때와 다르다")
        return texts

    def inputs_with(
        self, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> DraftInputs:
        accepted = _accepted(options)
        project_id = accepted["projectId"]
        if any(key not in versions for key in FACT_KEYS):
            raise RunVersionsMismatch("실행의 판 묶음에 목차·문서 열쇠가 없다")
        outline_id, sha, document_id, etag = (versions[key] for key in FACT_KEYS)
        if not isinstance(outline_id, int) or not isinstance(document_id, int) or not isinstance(sha, str):
            raise RunVersionsMismatch("실행의 판 묶음의 목차·문서 값 꼴이 다르다")
        if not isinstance(etag, str):
            raise RunVersionsMismatch("실행의 판 묶음의 문서 etag 꼴이 다르다")
        found = self.projects.outline(company_id, outline_id)
        if found is None or found.project_id != project_id:
            raise RunVersionsMismatch(f"목차 판 {outline_id} 이 이 회사·프로젝트의 것이 아니다")
        if wire.outline_sha256(found.outline) != sha or found.sha256 != sha:
            raise RunVersionsMismatch(f"목차 판 {outline_id} 의 sha256 이 실행을 만들 때와 다르다")
        texts, models = self._setting(company_id, versions)
        base: reuse.Base | None = None
        rebuild: frozenset[str] = frozenset()
        if "base" in accepted:
            base = self._read_base(company_id, project_id, accepted["base"]["runId"], versions)
            rebuild = frozenset(accepted["base"]["rebuild"])
        return DraftInputs(
            project_id=project_id,
            outline_id=outline_id,
            outline_sha256=sha,
            outline=found.outline,
            document_id=document_id,
            document_etag=etag,
            texts=texts,
            models=models,
            tags=Tags(tenant=str(company_id), module=draft_v2.MODULE),
            max_usd=self.max_usd(),
            base=base,
            rebuild=rebuild,
        )

    def _read_base(self, company_id: int, project_id: int, run_id: int, versions: Mapping[str, object]) -> reuse.Base:
        found = self._base(company_id, project_id, run_id)
        if found is None or found.result is None:
            raise RunVersionsMismatch(f"이어 받을 앞 실행 {run_id} 을 다시 읽지 못했다")
        outline_id = found.result["outlineId"]
        outline = self.projects.outline(company_id, outline_id)
        if outline is None or outline.project_id != project_id:
            raise RunVersionsMismatch(f"앞 실행 {run_id} 의 목차 판을 다시 읽지 못했다")
        return reuse.Base(
            run_id=run_id,
            outline_id=outline_id,
            nodes=list(outline.outline["nodes"]),
            versions_same=same_versions(found.versions, versions),
            result=found.result,
        )

    def inputs(self, options: Mapping[str, object], *, company_id: int) -> DraftInputs:
        versions = self.versions_with(options, company_id=company_id)
        return self.inputs_with(options, company_id=company_id, versions=versions)

    def adapters(self, ctx: RunContext) -> DraftAdapters:
        company_id, run_id = ctx.company_id, ctx.run_id
        return DraftAdapters(
            llm=ctx.llm(),
            mock=self.mock(),
            spent_usd=lambda: self.spent_usd(company_id, run_id),
            artifacts=_Scoped(self.artifacts, company_id),
        )
