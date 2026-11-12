"""프롬프트 저장소. 순수 층. esg-lab 의 test/prompts.test.ts(6건)를 옮긴 것이다."""

from dataclasses import replace
from pathlib import Path

import pytest

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.errors import PromptError
from esgapi.core.llm.prompts import (
    FilePromptStore,
    PackagePromptStore,
    PromptRef,
    format_prompt_id,
    parse_prompt_id,
    parse_template,
    render_prompt,
)
from esgapi.core.llm.types import SystemSegment
from esgapi.core.tests.llm_support import TAGS, harness


def test_version_pinning_uses_only_the_requested_version(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("a").enqueue_text("b")
    request = CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS)

    h.client.call(request)
    h.client.call(replace(request, prompt="t/plain@2"))

    assert h.mock.calls[0].system[0].text == "짧게 답한다."
    assert h.mock.calls[1].system[0].text == "길게 답한다."
    assert [record.prompt_version for record in h.log.records] == [1, 2]
    assert h.log.records[0].template_hash != h.log.records[1].template_hash


@pytest.mark.parametrize(
    "bad", ["t/plain", "t/plain@latest", "t/plain@0", "t/plain@01", "T/plain@1", "t/pl ain@1", "t/plain@1\n", "../x@1"]
)
def test_id_without_a_version_or_with_a_wrong_shape_is_rejected(bad: str) -> None:
    """판을 빼면 거부한다(「최신」으로 흘러가지 않는다). id 의 꼴이 틀려도 거부한다."""
    with pytest.raises(PromptError, match="버전 필수"):
        parse_prompt_id(bad)


def test_good_id_parses_and_a_missing_version_file_is_rejected(prompt_root: Path) -> None:
    assert parse_prompt_id("scope3/classify@12") == PromptRef(module="scope3", name="classify", version=12)
    assert format_prompt_id(parse_prompt_id("scope3/classify@12")) == "scope3/classify@12"
    with pytest.raises(PromptError, match="프롬프트가 없다"):
        FilePromptStore(prompt_root).get(parse_prompt_id("t/plain@3"))


def test_missing_variable_is_an_error(prompt_root: Path) -> None:
    template = FilePromptStore(prompt_root).get(parse_prompt_id("t/plain@1"))
    assert render_prompt(template, {"question": "배출량은?"}).user == "배출량은?"
    with pytest.raises(PromptError, match="변수 question 의 값이 없다"):
        render_prompt(template, {})


def test_extra_variable_is_an_error(prompt_root: Path) -> None:
    template = FilePromptStore(prompt_root).get(parse_prompt_id("t/plain@1"))
    with pytest.raises(PromptError, match="템플릿에 없는 변수를 넘겼다: extra"):
        render_prompt(template, {"question": "q", "extra": "x"})


def test_substituted_value_is_not_substituted_again(prompt_root: Path) -> None:
    template = FilePromptStore(prompt_root).get(parse_prompt_id("t/plain@1"))
    assert render_prompt(template, {"question": "{{question}}"}).user == "{{question}}"


REF = PromptRef(module="t", name="x", version=1)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("=== system ===\n지침\n", "user 구획이 없다"),
        ("본문\n=== user ===\nq\n", "앞에 본문이 있다"),
        ("=== user ===\n\n", "구획이 비었다"),
        ("=== system ===\n   \n=== user ===\nq\n", "system 구획이 비었다"),
        ("=== system ===\na\n=== system cache ===\nb\n=== user ===\nq\n", "앞에 와야 한다"),
        ("=== user ===\nq\n=== system ===\na\n", "user 구획 앞에"),
        ("=== user ===\nq\n=== user ===\nr\n", "user 구획이 둘 이상"),
    ],
)
def test_malformed_templates_are_rejected(source: str, message: str) -> None:
    with pytest.raises(PromptError, match=message):
        parse_template(REF, source)


def test_well_formed_template_parses_sections_in_order() -> None:
    source = "\n=== system cache ===\r\n용어집\r\n\n=== system ===\n메모\n=== user ===\n{{q}} 는?\n"
    template = parse_template(REF, source)
    assert template.id == "t/x@1"
    assert template.system == (SystemSegment(text="용어집", cache=True), SystemSegment(text="메모", cache=False))
    assert template.user == "{{q}} 는?"
    assert len(template.hash) == 64
    # 해시는 원문의 것이다: 빈칸 하나만 달라도 달라진다.
    assert parse_template(REF, source + " ").hash != template.hash


def test_packaged_example_prompt_is_read_from_the_module_folder() -> None:
    """core/hello@1 = esgapi/core/prompts/hello/1.md. 패키지 자료로 읽는다."""
    template = PackagePromptStore().get(parse_prompt_id("core/hello@1"))
    assert template.system[0].cache is True
    assert "{{name}}" in template.user


@pytest.mark.parametrize("missing", ["core/hello@2", "core/nope@1", "no-such-module/hello@1", "nosuchmodule/hello@1"])
def test_package_store_names_the_missing_prompt(missing: str) -> None:
    with pytest.raises(PromptError, match="프롬프트가 없다"):
        PackagePromptStore().get(parse_prompt_id(missing))
