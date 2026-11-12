from django.apps import AppConfig

from esgapi.core.conf import app_config


def g1_runs_enabled() -> bool:
    """그린워싱 2차 엔진 실행을 받는가(환경 변수 GREENWASH_G1_RUNS_ENABLED — Config 로만 읽는다, 기본 꺼짐 GE1b D4)."""
    return app_config().greenwash_g1_runs_enabled


class GreenwashConfig(AppConfig):
    name = "esgapi.greenwash"
    label = "greenwash"

    def ready(self) -> None:
        # 흐름을 코어의 레지스트리에 단다. 코어는 greenwash 를 모른다(.importlinter 계약 가) — 등록은 여기서만.
        # 전역 앱의 ready 에서만 단다: isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리도 ready 를 부른다(Django 5.2).
        from django.apps import apps as global_apps

        if self.apps is not global_apps:
            return
        from esgapi.core.flows.binding import BINDINGS
        from esgapi.core.flows.registry import REGISTRY
        from esgapi.greenwash.flows import colab_e0 as colab
        from esgapi.greenwash.flows import registration
        from esgapi.greenwash.flows.binding_e0 import GreenwashBinding

        registration.register(REGISTRY)
        from esgapi.greenwash.service.selectors.ai_settings import RunModelSource, RunSettingStore

        # 끼움(G1b) — 실제 경로 이름. 판 읽기(G2c2)는 기본값 없이 꽂는다(빠지면 조용히 기본 판이 되는 길 0)
        setting = GreenwashBinding(store=RunSettingStore(), models=RunModelSource())
        BINDINGS.register(colab.FLOW_ID, setting)
        from esgapi.greenwash.flows import rejudge_e0 as rejudge

        # 재판단(GRJ1) — 문서 없는 갈래. 원 실행의 판을 E0 끼움(setting)과 같은 대조로 다시 짓는다
        BINDINGS.register_documentless(
            rejudge.FLOW_ID, rejudge.RejudgeBinding(setting=setting), max_options_bytes=rejudge.OPTIONS_MAX_OCTETS
        )
        from esgapi.core.llm.prompts import PackagePromptStore
        from esgapi.core.resources import parser as parsers
        from esgapi.greenwash.flows import engine_g1
        from esgapi.greenwash.flows.binding_g1 import G1Binding
        from esgapi.greenwash.service.actions.engine_g1 import RunG1Documents

        # 2차 엔진(GE1b ③) — 실행 시작은 환경 스위치(기본 꺼짐, 읽는 함수 — 시작마다 읽는다). 문서는 core 문서 산출물
        # (파서는 만드는 함수 — drafting/apps.py 와 같은 꼴). 모델 원천은 E0 와 같은 RunModelSource
        BINDINGS.register(
            engine_g1.FLOW_ID,
            G1Binding(
                runs_enabled=g1_runs_enabled,
                documents=RunG1Documents(
                    parser=lambda: parsers.make(
                        "http", base_url=app_config().parser_url, timeout_s=app_config().parser_timeout_ms / 1000
                    )
                ),
                models=RunModelSource(),
                prompts=PackagePromptStore(),
            ),
        )
        from esgapi.greenwash.service.selectors.run_extras import RunReviewSource
        from esgapi.runs.extras import EXTRAS

        EXTRAS.register("greenwash", RunReviewSource())  # 운영 관리자 실행 기록의 검토·AI 설정 칸(AD4S)
        from esgapi.core.flows.carriers import CARRIERS
        from esgapi.greenwash.service.actions.bundle import GreenwashCarrier

        CARRIERS.register("greenwash", GreenwashCarrier())  # 실행 묶음의 판·검토·표시(RX1b)
