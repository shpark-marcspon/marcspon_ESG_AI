"""시험용 AI 설정 판 포트(flows/binding_v2.AiSettingStore) 둘과 모델 원천 — 순수(DB 0). 판·글은 지어낸 것이다.

DefaultOnlyStore()           어느 회사든 적용 판 없음(기본 판), get 은 늘 없음 — RPA1 앞 시험이 그대로 돈다
FakeStore(saved, applied)    회사 → 판 목록·적용 판 id 를 손으로 든 것. 부른 것을 calls 에 적는다
FileModels(config)           모델 원천 — 저장소 정본 models.json(실제 파일, 모의 경로 0)과 prompt_model_v2.MODELS
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from esgapi.core.calc.ai_settings import AiModelSlotSpec
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.drafting.flows import prompt_model_v2
from esgapi.drafting.flows.binding_v2 import DefaultSetting, SavedSetting, SettingNotFound


class DefaultOnlyStore:
    def applied(self, company_id: int) -> SavedSetting | DefaultSetting:
        return DefaultSetting()

    def get(self, company_id: int, setting_id: int) -> SavedSetting | SettingNotFound:
        return SettingNotFound(setting_id)


@dataclass
class FakeStore:
    saved: dict[int, list[SavedSetting]] = field(default_factory=dict[int, list[SavedSetting]])
    applied_id: dict[int, int] = field(default_factory=dict[int, int])
    calls: list[tuple[str, int, int | None]] = field(default_factory=list[tuple[str, int, int | None]])

    def applied(self, company_id: int) -> SavedSetting | DefaultSetting:
        self.calls.append(("applied", company_id, None))
        wanted = self.applied_id.get(company_id)
        found = next((s for s in self.saved.get(company_id, []) if s.id == wanted), None)
        return DefaultSetting() if found is None else found

    def get(self, company_id: int, setting_id: int) -> SavedSetting | SettingNotFound:
        self.calls.append(("get", company_id, setting_id))
        found = next((s for s in self.saved.get(company_id, []) if s.id == setting_id), None)
        return SettingNotFound(setting_id) if found is None else found


def file_config() -> LlmConfig:
    return load_config(default_config_sources(synthetic=False))


@dataclass
class FileModels:
    loaded: LlmConfig = field(default_factory=file_config)

    def config(self) -> LlmConfig:
        return self.loaded

    def steps(self) -> Sequence[AiModelSlotSpec]:
        return prompt_model_v2.MODELS
