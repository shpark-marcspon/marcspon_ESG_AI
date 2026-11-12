"""그림 첨부가 호출 층을 지나 공급사에 전달되고, 보고된 사용량이 비용에 세어지는가. 순수 층.

esg-lab 의 test/attachments.test.ts(4건)를 옮긴 것이다. 모의 공급사와 요청 조립만 본다.
"""

from dataclasses import replace
from pathlib import Path

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.types import ImagePart, PdfPart, ProviderRequest, TextPart, Usage
from esgapi.core.tests.llm_support import TAGS, harness

# 1×1 PNG (그림의 내용은 보지 않는다). 가상 자료다.
PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg=="
IMAGE = ImagePart(base64=PNG_BASE64, media_type="image/png")
BASE = CallRequest(prompt="t/plain@1", vars={"question": "번호마다 답해 줘"}, route="mock", tags=TAGS)


def test_image_goes_before_text_and_reported_input_tokens_are_billed(prompt_root: Path) -> None:
    h = harness(prompt_root, store_bodies=True)
    # 그림이 든 호출의 가상 사용량: 입력 2,060(글 60 + 그림 2,000 이라고 치자), 출력 20.
    # 모의 단가(입력 1, 출력 2 USD/100만 토큰)로 2,060 + 40 = 2,100 → 0.0021 USD.
    h.mock.enqueue_text("ok", Usage(input_tokens=2060, output_tokens=20, cache_read_tokens=0, cache_write_tokens=0))

    result = h.client.call(replace(BASE, attachments=[IMAGE]))

    assert result.kind == "success"
    assert [part.type for part in h.mock.calls[0].user] == ["image", "text"]
    assert h.mock.calls[0].user[0] == IMAGE
    assert result.meta.total_cost_usd == 0.0021
    assert (h.log.records[0].input_tokens, h.log.records[0].cost_usd) == (2060, 0.0021)


def test_attachments_keep_their_order_and_all_precede_the_text(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("ok")
    pdf = PdfPart(base64="UERG", filename="report.pdf")
    h.client.call(replace(BASE, attachments=[pdf, IMAGE]))
    assert h.mock.calls[0].user == (pdf, IMAGE, TextPart(text="번호마다 답해 줘"))


def test_without_attachments_only_text_is_sent(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("ok")
    h.client.call(BASE)
    assert [part.type for part in h.mock.calls[0].user] == ["text"]


def test_dry_run_does_not_estimate_images_and_says_so(prompt_root: Path) -> None:
    h = harness(prompt_root)
    with_image = h.client.dry_run(replace(BASE, attachments=[IMAGE]))
    plain = h.client.dry_run(BASE)
    assert with_image.estimate.unestimated_parts == ("image",)
    assert plain.estimate.unestimated_parts == ()
    assert with_image.estimate.input_tokens == plain.estimate.input_tokens


def test_openai_body_carries_the_image_as_a_data_url_before_the_text() -> None:
    request = ProviderRequest(
        api_model_id="model-synthetic", system=(), user=(IMAGE, TextPart(text="질문")), max_output_tokens=100
    )
    body = OpenAIProvider().build_request(request)
    assert body["input"] == [
        {
            "role": "user",
            "content": [
                {"type": "input_image", "detail": "auto", "image_url": f"data:image/png;base64,{PNG_BASE64}"},
                {"type": "input_text", "text": "질문"},
            ],
        }
    ]
