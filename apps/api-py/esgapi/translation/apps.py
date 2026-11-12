from django.apps import AppConfig


def _spent_usd(company_id: int, run_id: int) -> float:
    """그 실행의 호출 기록 cost_usd 합(USD). 있는 selector 를 바로 부른다(새 selector 0 — 선례 user/service/apis/
    run_logs.py). 부를 때 import 한다(ready 앞에 모델을 끌지 않게)."""
    from esgapi.core.service.selectors import llm_usage

    found = llm_usage.usage_by_run(company_id=company_id, run_ids=frozenset({run_id})).get(run_id)
    return 0.0 if found is None else float(found.cost_usd)


class TranslationConfig(AppConfig):
    name = "esgapi.translation"
    label = "translation"

    def ready(self) -> None:
        # 흐름을 코어의 레지스트리에 단다. 코어는 translation 을 모른다(.importlinter 계약 가) — 등록은 여기서만.
        # 전역 앱의 ready 에서만 단다: isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리도 ready 를 부른다(Django 5.2).
        from django.apps import apps as global_apps

        if self.apps is not global_apps:
            return
        from esgapi.core.conf import app_config
        from esgapi.core.flows.binding import BINDINGS, DOCUMENTLESS_OPTIONS_MAX_OCTETS
        from esgapi.core.flows.registry import REGISTRY
        from esgapi.translation.flows import colab_158 as colab
        from esgapi.translation.flows import registration
        from esgapi.translation.flows.binding_158 import TranslationBinding
        from esgapi.translation.service.actions.retry_source import RunRetrySource
        from esgapi.translation.service.selectors.ai_settings import RunModelSource, RunSettingStore

        registration.register(REGISTRY)
        # 금액 상한은 읽는 함수로 꽂는다 — 값은 끼움이 실행이 돌 때 읽는다(ready 에서 읽지 않는다).
        # 옵션 상한 256KiB(밴드 TR3a): 용어집 500 + 500짝(지어낸 국 10·영 30자)과 peer 글 8,000자가 약 166KB
        # 판 읽기·모델 원천(TR4 ③)은 기본값 없이 꽂는다(빠지면 조용히 기본 판이 되는 길 0)
        BINDINGS.register(
            colab.FLOW_ID,
            TranslationBinding(
                store=RunRetrySource(),
                settings=RunSettingStore(),
                models=RunModelSource(),
                max_usd=lambda: app_config().llm.translation_run_max_usd,
                # 실행기와 같은 원천(runs/context.py 의 llm_settings 가 읽는 run_mode) — live 가 아니면 모의 경로(331)
                mock=lambda: app_config().llm.run_mode != "live",
                spent_usd=_spent_usd,  # 시도를 넘는 금액 상한(MARC-ISSUE-268) — 흐름은 selector 를 모른다
            ),
            max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS,
        )
        from esgapi.core.resources import parser as parsers
        from esgapi.translation.flows import pdf_158 as pdf
        from esgapi.translation.flows.binding_pdf_158 import TranslationPdfBinding

        # PDF 입력(밴드 TRD2): 같은 꽂음 + 파서를 만드는 함수(돌 때 지음 — 주소가 없으면 ParserSetupError 로 단계 실패).
        # 옵션 상한도 같게 둔다(빠지면 기본 16KiB — 용어집 옵션이 막힌다)
        BINDINGS.register(
            pdf.FLOW_ID,
            TranslationPdfBinding(
                store=RunRetrySource(flow_id=pdf.FLOW_ID, adapter=pdf.pdf_tags.ADAPTER_VERSION),
                settings=RunSettingStore(),
                models=RunModelSource(),
                max_usd=lambda: app_config().llm.translation_run_max_usd,
                mock=lambda: app_config().llm.run_mode != "live",
                spent_usd=_spent_usd,
                parser=lambda: parsers.make(
                    "http", base_url=app_config().parser_url, timeout_s=app_config().parser_timeout_ms / 1000
                ),
            ),
            max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS,
        )
        from esgapi.runs.extras import EXTRAS
        from esgapi.translation.service.selectors.run_extras import RunSettingExtras

        EXTRAS.register("translation", RunSettingExtras())  # 운영 관리자 실행 기록의 AI 설정 칸(Q7)
        from esgapi.core.flows.carriers import CARRIERS
        from esgapi.translation.service.actions.bundle import TranslationCarrier

        CARRIERS.register("translation", TranslationCarrier())  # 실행 묶음의 판·재번역 앞 실행(RX1b)
