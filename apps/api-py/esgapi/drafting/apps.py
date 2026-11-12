from django.apps import AppConfig


class DraftingConfig(AppConfig):
    name = "esgapi.drafting"
    label = "drafting"

    def ready(self) -> None:
        # 흐름을 코어의 레지스트리에 단다. 코어는 drafting 을 모른다(.importlinter 계약 가) — 등록은 여기서만.
        # 전역 앱의 ready 에서만 단다: isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리도 ready 를 부른다(Django 5.2).
        from django.apps import apps as global_apps

        if self.apps is not global_apps:
            return
        from esgapi.core.conf import app_config
        from esgapi.core.flows.binding import BINDINGS
        from esgapi.core.flows.registry import REGISTRY
        from esgapi.core.resources import parser as parsers
        from esgapi.drafting.flows import draft_v2, registration
        from esgapi.drafting.flows.binding_v2 import DraftingBinding
        from esgapi.drafting.service.actions.run_sources import (
            RunArtifacts,
            RunBaseSource,
            RunProjectSource,
            spent_usd,
        )
        from esgapi.drafting.service.selectors.ai_settings import RunModelSource, RunSettingStore

        registration.register(REGISTRY)
        # 문서 없는 흐름(처분 ① 가). 포트는 기본값 없이 꽂는다. 금액 상한·mock 은 읽는 함수 — 실행이 돌 때 읽는다
        # (mock: 실행기와 같은 원천 run_mode — live 가 아니면 모의 경로, 331). 옵션 상한은 기본 16KiB.
        # 쪽 글은 core 문서 산출물(RP2a ②) — 파서는 만드는 함수(돌 때 지음 — 주소가 없으면 ParserSetupError 로
        # 단계 실패, translation/apps.py 의 PDF 입력과 같은 꼴). 앞 실행 이어 받기는 runs 의 selector 로 읽는다(RP2c).
        # AI 설정 판 읽기·모델 원천(RPA1 ②)도 기본값 없이 꽂는다(빠지면 조용히 기본 판이 되는 길 0)
        BINDINGS.register_documentless(
            draft_v2.FLOW_ID,
            DraftingBinding(
                projects=RunProjectSource(),
                max_usd=lambda: app_config().llm.drafting_run_max_usd,
                mock=lambda: app_config().llm.run_mode != "live",
                spent_usd=spent_usd,
                artifacts=RunArtifacts(
                    parser=lambda: parsers.make(
                        "http", base_url=app_config().parser_url, timeout_s=app_config().parser_timeout_ms / 1000
                    )
                ),
                bases=RunBaseSource(),
                settings=RunSettingStore(),
                models=RunModelSource(),
            ),
        )
        from esgapi.drafting.service.selectors.run_extras import RunSettingExtras
        from esgapi.runs.extras import EXTRAS

        EXTRAS.register("drafting", RunSettingExtras())  # 운영 관리자 실행 기록의 AI 설정 칸(RPA1 ②)
