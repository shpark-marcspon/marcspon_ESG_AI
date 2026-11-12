"""호출 계획(처분 ⑬): 입력 → 부를 수 있는 LLM 호출의 위끝 목록. 공급사를 부르지 않는다 — 다리의 `dry_run` 이 이 목록을
core.llm `LlmClient.dry_run` 으로 어림한다.

위끝의 정직성(발주서 §2-4, critic N2):
- (a) 표 묶음 JSON 을 못 읽으면 칸마다 한 번 더 부른다(R/2324-2333) — 칸 대체 호출을 위끝에 넣는다. 그 구획 번역 글의
  위끝도 묶음 출력(묶음 수 × 8192)과 칸 대체 출력(칸 수 × 1024) 중 큰 쪽이다(MARC-ISSUE-196 의 1).
- (b) 앞 호출의 출력이 들어가는 자리(윤문·QA·보정·검수·자동수정의 번역 글)는 그 글을 모른다 — 앞 호출의 max_tokens
  토큰만큼의 자리 글(`stand_in`)로 채운다. 자리 글은 영문 4자 = 1토큰(models.json tokenEstimate latinCharsPerToken 4)에
  맞춘 「x」 줄이다.
- (d) 횟수: A/B 면 문체마다, 구획 윤문·용어집 보정 ≤ 1, 한국어 보정 ≤ 2(R/3051), 쪽 윤문·QA ≤ 1(쪽 원문에 표 꼴이
  없을 때 — R/2554-2575, 번역 글이 표를 지니면 둘 다 안 돈다), 검수 쪽마다 1, 자동수정 쪽마다 ≤ 1 + 한국어 ≤ 1(R/6368).
  돌지 않을 것이 글로 정해진 자리(국문 없는 구획의 번역, 쪽에 key 가 없는 용어집 보정, 국문 없는 표 칸)는 넣지 않는다.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.gates import (
    EDITORIAL_POLISH_MAX_CHARS,
    EDITORIAL_POLISH_MIN_CHARS,
    MAX_UNTRANSLATED_REPAIR_ROUNDS,
    TABLE_BATCH_SIZE,
    contains_table_like_text,
    has_ko,
    split_page_sections,
)
from esgapi.translation.engines.colab_158.glossary import build_glossary_text, build_relevant_glossary, fold_glossary
from esgapi.translation.engines.colab_158.pages import (
    filter_range,
    last_wins_map,
    pages_to_map_merge,
    parse_pages,
    remove_page_tag_lines,
)
from esgapi.translation.engines.colab_158.pipeline import EngineInput, source_and_pages, style_prompts
from esgapi.translation.engines.colab_158.ports import Role
from esgapi.translation.engines.colab_158.records import Rejection, VariantLabel
from esgapi.translation.engines.colab_158.review_rules import PART_QA_AUTOFIX_MAX_KOREAN_REPAIR_ROUNDS
from esgapi.translation.engines.colab_158.tables import collect_table_fragments

STAND_IN_CHARS_PER_TOKEN = 4
"""자리 글의 글자 수 = 토큰 × 4(영문). core 의 어림(latinCharsPerToken 4)이 바뀌면 자리 글의 어림 토큰도 바뀐다."""


def stand_in(tokens: int) -> str:
    return "x" * (tokens * STAND_IN_CHARS_PER_TOKEN)


@dataclass(frozen=True)
class PlannedCall:
    site: prompts.Site
    role: Role
    system: str
    user: str
    max_tokens: int
    count: int
    """이 요청을 최대 몇 번 부르는가."""
    page_num: int
    variant: VariantLabel


@dataclass
class CallPlan:
    part: str
    """계획을 지은 입력의 파트 — 다리의 `dry_run` 이 제 파트와 다르면 거절한다(경로가 파트에 달림,
    MARC-ISSUE-196 N8)."""
    calls: list[PlannedCall] = field(default_factory=list[PlannedCall])
    rejection: Rejection | None = None
    assumptions: list[str] = field(default_factory=list[str])
    unestimated: list[str] = field(default_factory=list[str])


ASSUMPTIONS = (
    "앞 호출의 출력이 들어가는 자리는 그 호출의 max_tokens 만큼의 자리 글로 셌다(영문 4자 = 1토큰)",
    "표 묶음 JSON 실패 때의 칸 대체 호출(칸마다 1024)을 위끝에 넣었다 — 표 구획 번역 글의 위끝은 묶음 수 × 8192 와 "
    "칸 수 × 1024 중 큰 쪽",
    "구획 윤문은 번역 글 길이를 모르므로 국문 구획마다 1 로 셌다(general·story 는 120자 미만이면 실제로는 0)",
    "쪽 윤문·범용 QA 는 쪽 원문에 표 꼴이 없으면 1, 있으면 0 으로 셌다(번역 쪽이 120자 미만이면 실제로는 0, "
    "번역 쪽이 원문의 표 꼴을 잃으면 실제로는 1)",
    "검수의 병기 힌트는 쪽 원문 글로 셌다(실제는 병기된 국문 첫 줄들 — 그보다 짧다)",
    "자동수정 한국어 보정의 입력은 쪽 번역 글 위끝과 자동수정 max_tokens 중 큰 쪽으로 셌다(자동수정이 쪽을 그대로 두면 "
    "쪽 번역 글이 들어간다)",
)


def plan(inputs: EngineInput) -> CallPlan:
    """`pipeline.run` 이 부를 수 있는 호출의 위끝. 거절이면 호출 0."""
    out = CallPlan(part=inputs.part, assumptions=list(ASSUMPTIONS))
    source_text, pages, rejection = source_and_pages(inputs)
    if rejection is not None:
        out.rejection = rejection
        return out
    glossary = fold_glossary(inputs.glossary_base, inputs.glossary_final)
    company = inputs.texts.company_style(
        inputs.part,
        inputs.company_name,
        inputs.preferred_subject,
        inputs.industry_standards,
        inputs.peer_group_style_prompt,
    )
    styles = style_prompts(inputs)
    page_out_tokens: dict[tuple[VariantLabel, int], int] = {}
    for page in pages:
        for label, style_prompt in styles:
            tokens = _translate_page(out, inputs, company, glossary, page.content, page.page_num, label, style_prompt)
            key = (label, page.page_num)
            page_out_tokens[key] = page_out_tokens.get(key, 0) + tokens
    source_map = filter_range(pages_to_map_merge(parse_pages(source_text))[0], inputs.page_start, inputs.page_end)
    for label, _ in styles:
        for pnum in sorted(source_map):
            if (label, pnum) not in page_out_tokens:
                continue
            _review_and_fix(out, inputs, glossary, source_map[pnum], pnum, label, page_out_tokens[(label, pnum)])
    return out


RETRY_ASSUMPTION = (
    "실패 쪽만 다시(셀 50): 고른 쪽 중 원문에 있는 쪽만 번역을 셌고, 검수·자동수정은 전 쪽을 셌다 — 다시 번역하지 않는 "
    "쪽의 번역 글은 앞 결과의 글 길이(한 글자 = 1토큰)로 셌다"
)


def retry_plan(inputs: EngineInput, base: Mapping[VariantLabel, str], pages: Sequence[int]) -> CallPlan:
    """`pipeline.retry` 가 부를 수 있는 호출의 위끝. `plan` 과 같은 꼴 — 쪽 번역은 고른 쪽만(원문 지도는 뒤 조각이
    이김, 범위 거름 없음 — R/3568-3569), 셀 52~67 은 전 쪽. 거절이면 호출 0."""
    out = CallPlan(part=inputs.part, assumptions=[*ASSUMPTIONS, RETRY_ASSUMPTION])
    source_text, _, rejection = source_and_pages(inputs)
    if rejection is not None:
        out.rejection = rejection
        return out
    glossary = fold_glossary(inputs.glossary_base, inputs.glossary_final)
    company = inputs.texts.company_style(
        inputs.part,
        inputs.company_name,
        inputs.preferred_subject,
        inputs.industry_standards,
        inputs.peer_group_style_prompt,
    )
    styles = style_prompts(inputs)
    source_pages = last_wins_map(parse_pages(source_text))
    page_out_tokens: dict[tuple[VariantLabel, int], int] = {}
    for pnum in pages:
        if pnum not in source_pages:
            continue
        for label, style_prompt in styles:
            page_out_tokens[(label, pnum)] = _translate_page(
                out, inputs, company, glossary, source_pages[pnum], pnum, label, style_prompt
            )
    source_map = filter_range(pages_to_map_merge(parse_pages(source_text))[0], inputs.page_start, inputs.page_end)
    for label, _ in styles:
        base_map = pages_to_map_merge(parse_pages(base.get(label, "")))[0]
        for pnum in sorted(source_map):
            if (label, pnum) in page_out_tokens:
                tokens = page_out_tokens[(label, pnum)]
            elif pnum in base_map:
                tokens = _tokens(base_map[pnum])
            else:
                continue
            _review_and_fix(out, inputs, glossary, source_map[pnum], pnum, label, tokens)
    return out


def _translate_page(
    out: CallPlan,
    inputs: EngineInput,
    company: str,
    glossary: dict[str, str],
    page_content: str,
    page_num: int,
    label: VariantLabel,
    style_prompt: str,
) -> int:
    """쪽 조각 하나·문체 하나(R/3279-3360). 돌려주는 값 = 그 쪽 번역 글의 위끝 토큰."""
    active = build_relevant_glossary(glossary, page_content)
    glossary_text = build_glossary_text(active)
    texts = inputs.texts
    sp = texts.page_system(company, style_prompt, inputs.industry_standards)
    ceo = inputs.part == "ceo_message"

    def add(site: prompts.Site, system: str, user: str, count: int = 1) -> None:
        out.calls.append(PlannedCall(site, "translate", system, user, prompts.MAX_TOKENS[site], count, page_num, label))

    total = 0
    for sec in split_page_sections(page_content):
        sec_text = "\n".join(sec.lines).strip()
        if not sec_text:
            continue
        is_table = sec.kind == "TABLE"
        korean = has_ko(sec_text)
        # 그 구획 번역 글의 위끝 토큰: 부른 자리의 max_tokens(표 묶음이면 묶음 수 × 8192), 안 부르면 원문 그대로(R/2341)
        out_tokens = _tokens(sec_text)
        table = collect_table_fragments(sec_text) if is_table else None
        if table is not None:
            items = table.fragments
            for start in range(0, len(items), TABLE_BATCH_SIZE):
                payload = json.dumps({"items": items[start : start + TABLE_BATCH_SIZE]}, ensure_ascii=False, indent=2)
                add("table-batch", texts.table_batch_system(sp), prompts.table_batch_user(glossary_text, payload))
            for item in items:  # (a) 칸 대체
                add("cell", sp, prompts.cell_user(glossary_text, item["text"]))
            batches = -(-len(items) // TABLE_BATCH_SIZE)
            out_tokens = max(
                out_tokens, batches * prompts.MAX_TOKENS["table-batch"], len(items) * prompts.MAX_TOKENS["cell"]
            )
        elif korean:  # 표 구획인데 pipe 표가 없으면 쪽 번호 없이 일반 구획처럼(R/2822-2824)
            add("section", sp, prompts.section_user(glossary_text, sec_text, None if is_table else page_num))
            out_tokens = max(out_tokens, prompts.MAX_TOKENS["section"])
        if not is_table:  # 구획 윤문(R/2482-2549) — 국문 없는 구획은 번역 글 = 원문이라 조건이 글로 정해진다
            draft = stand_in(out_tokens) if korean else sec_text
            long_enough = ceo or korean or _plain_len(sec_text) >= EDITORIAL_POLISH_MIN_CHARS
            if long_enough and (korean or len(sec_text) <= EDITORIAL_POLISH_MAX_CHARS):
                add("polish", texts.polish_system(sp), prompts.polish_user(glossary_text, sec_text, draft, page_num))
                out_tokens = max(out_tokens, prompts.MAX_TOKENS["polish"])
        draft = stand_in(out_tokens)
        relevant = build_relevant_glossary(active, sec_text)
        if relevant:  # 용어집 보정 ≤ 1(R/2980-3041) — 쪽에 key 가 없으면 위반이 날 수 없다
            rule = prompts.GLOSSARY_REPAIR_TABLE_RULE if is_table else prompts.GLOSSARY_REPAIR_STRUCTURE_RULE
            violations = "\n".join(f"- {k} -> {v}" for k, v in relevant.items())
            user = prompts.glossary_repair_user(build_glossary_text(relevant), violations, rule, sec_text, draft)
            add("glossary-repair", sp, user)
        if korean:  # 한국어 보정 ≤ 2(R/3051) — 국문 없는 구획의 번역 글(= 원문)에는 국문이 없다
            rule = prompts.KOREAN_REPAIR_TABLE_RULE if is_table else prompts.KOREAN_REPAIR_STRUCTURE_RULE
            user = prompts.korean_repair_user(glossary_text, draft, rule, sec_text, draft)
            add("korean-repair", prompts.korean_repair_system(sp), user, MAX_UNTRANSLATED_REPAIR_ROUNDS)
        total += out_tokens
    page_draft = stand_in(total)
    if not contains_table_like_text(page_content):
        add("polish", texts.polish_system(sp), prompts.polish_user(glossary_text, page_content, page_draft, page_num))
        add(
            "editorial-qa",
            texts.editorial_qa_system(sp),
            prompts.editorial_qa_user(glossary_text, page_content, page_draft, page_num),
        )
        total = max(total, prompts.MAX_TOKENS["editorial-qa"])
    return total


def _review_and_fix(
    out: CallPlan,
    inputs: EngineInput,
    glossary: dict[str, str],
    source_page: str,
    pnum: int,
    label: VariantLabel,
    page_tokens: int,
) -> None:
    """검수 1(R/5262-5369) + 자동수정 ≤ 1 + 한국어 ≤ 1(R/6647-6797)."""
    relevant = build_relevant_glossary(glossary, source_page)
    glossary_text = build_glossary_text(relevant)
    source_for_review = f"[PAGE {pnum}]\n{remove_page_tag_lines(source_page)}"
    translated = f"[PAGE {pnum}]\n{stand_in(page_tokens)}"
    user = prompts.review_user(label, glossary_text, pnum, source_for_review, source_page, translated)
    out.calls.append(
        PlannedCall("review", "review", inputs.texts.review, user, prompts.MAX_TOKENS["review"], 1, pnum, label)
    )
    if not inputs.autofix:
        return
    issues = stand_in(prompts.MAX_TOKENS["review"])
    fix_user = prompts.autofix_user(label, glossary_text, issues, pnum, source_page, translated)
    out.calls.append(
        PlannedCall(
            "autofix",
            "translate",
            inputs.texts.autofix_system(pnum),
            fix_user,
            prompts.MAX_TOKENS["autofix"],
            1,
            pnum,
            label,
        )
    )
    fixed = f"[PAGE {pnum}]\n{stand_in(max(page_tokens, prompts.MAX_TOKENS['autofix']))}"
    ko_user = prompts.autofix_korean_user(glossary_text, fixed, pnum, source_page, fixed)
    out.calls.append(
        PlannedCall(
            "autofix-korean",
            "translate",
            inputs.texts.autofix_korean_system(pnum),
            ko_user,
            prompts.MAX_TOKENS["autofix-korean"],
            PART_QA_AUTOFIX_MAX_KOREAN_REPAIR_ROUNDS,
            pnum,
            label,
        )
    )


def _plain_len(text: str) -> int:
    return len("".join(text.split()))


def _tokens(text: str) -> int:
    """원문 그대로 나가는 글의 위끝 토큰(한 글자 = 1토큰 — 국문·영문 어느 쪽 어림보다 크다)."""
    return len(text)
