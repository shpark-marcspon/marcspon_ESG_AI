"""흐름 translation.pdf@158 의 끼움(밴드 TRD2). 워드 흐름의 끼움(binding_158.TranslationBinding)을 그대로 쓰고 둘만
다르다.

    versions(options)  {"engine", "flow": pdf.FLOW_ID, "promptIds", "input": "pdf", "adapter": pdf_tags 판,
                       "parserLayout": 2} — 판 열쇠(versions_with)·옵션 받기·inputs 는 워드 흐름 그대로(options@1)
    adapters(ctx)      PdfAdapters(워드 흐름의 칸 + parser) — parser 는 apps.py 가 설정으로 꽂은 「만드는 함수」

이 파일은 순수다(django 0). 파서 주소·시간 제한을 읽지 않는다 — apps.py 가 꽂은 함수로만.
"""

from collections.abc import Callable, Mapping

from esgapi.core.flows.binding import RunContext
from esgapi.core.resources.ports.parser import DocumentParser
from esgapi.translation.flows import pdf_158 as pdf
from esgapi.translation.flows.binding_158 import ENGINE, AiSettingStore, RetrySourceStore, TranslationBinding
from esgapi.translation.flows.prompt_model_158 import ModelSettingsSource
from esgapi.translation.tools.llm_bridge import prompt_ids
from esgapi.translation.tools.pdf_tags import ADAPTER_VERSION


class TranslationPdfBinding(TranslationBinding):
    """translation.pdf@158 의 끼움(머리말)."""

    def __init__(
        self,
        *,
        store: RetrySourceStore,
        settings: AiSettingStore,
        models: ModelSettingsSource,
        max_usd: Callable[[], float],
        mock: Callable[[], bool],
        spent_usd: Callable[[int, int], float],
        parser: Callable[[], DocumentParser],
    ) -> None:
        super().__init__(store=store, settings=settings, models=models, max_usd=max_usd, mock=mock, spent_usd=spent_usd)
        self.parser = parser

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {
            "engine": ENGINE,
            "flow": pdf.FLOW_ID,
            "promptIds": prompt_ids(),
            "input": "pdf",
            "adapter": ADAPTER_VERSION,
            "parserLayout": pdf.PARSER_LAYOUT,
        }

    def adapters(self, ctx: RunContext) -> pdf.PdfAdapters:
        base = super().adapters(ctx)
        return pdf.PdfAdapters(
            llm=base.llm, tenant=base.tenant, mock=base.mock, spent_usd=base.spent_usd, parser=self.parser
        )
