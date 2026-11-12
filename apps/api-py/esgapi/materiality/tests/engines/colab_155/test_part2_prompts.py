"""engines/colab_155/part2_prompts.py(밴드 IR2a): system 셋의 지문과 바꾼 자리, user 셋의 바이트(산업 하나·셋,
valueChain 있음·없음, 묶음 글 있음·없음), 2부 글에 기간이 없음(발주서 §3 S3).

코랩 글과 바이트 같음(바꾸는 자리 밖)은 scripts/section4-IR2a.sh 7단계(COLAB_DIFF=0)가 읽기판에서 다시 보인다 — 여기서는
그 판의 지문을 못박고, 기대 글 하나씩은 손으로 적는다(dedent 가 셀 46 의 5칸 줄 때문에 1칸을 남기는 것까지).
"""

import hashlib
import json
import re
from pathlib import Path

from esgapi.materiality.contracts import wire
from esgapi.materiality.engines.colab_155 import part2_prompts as p

INDUSTRY = [{"standard": "SASB", "industry_name": "가상 산업", "description": "가상 설명"}]
NO_CON = "제공된 컨트로버시 정보 없음"
NO_REG = "제공된 정책/규정/가이드라인 정보 없음"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_system_fingerprints() -> None:
    """이 판의 글 지문(prompts/README.md 의 표와 같다). 바뀌면 README·section4 대조를 다시 잰다."""
    assert sha(p.IMPACT_SYSTEM) == "3f32db36d5b7f336ffc5c9b7c8de5516024cffd357fecec4891b26c52852a53c"
    assert sha(p.FINANCIAL_SYSTEM) == "a1cccc7a73bc9c45628987e3c8a31d38dc94a64fdc0dc8a997ed9eef1408c09c"
    assert sha(p.PATHWAY_SYSTEM) == "6807a731a4c61f945b08c464c6237c5a6714d97d6bdd131a519c3e185d118eea"


def test_readme_part2_fingerprints_match() -> None:
    """prompts/README.md 의 2부 「낸 글 지문」 표(칸 셋)가 이 판의 글과 같다."""
    readme = Path(p.__file__).resolve().parents[2] / "prompts" / "README.md"
    rows = re.findall(
        r"^\| `([A-Z_]+)` \| (46|50|55) \| `([0-9a-f]{64})` \|$", readme.read_text(encoding="utf-8"), re.M
    )
    assert {name: digest for name, _, digest in rows} == {
        name: sha(getattr(p, name)) for name in ("IMPACT_SYSTEM", "FINANCIAL_SYSTEM", "PATHWAY_SYSTEM")
    }


def test_impact_system_output_section_is_json() -> None:
    text = p.IMPACT_SYSTEM
    assert text.startswith("\nYou are an ESG & Double Materiality expert specializing in ESRS impact materiality")
    assert text.endswith("- JSON 외의 부가 설명은 절대 출력하지 않는다.\n")
    for gone in (
        "[최종 Output Format]",
        "Markdown 테이블",
        "[Length Constraint]",
        "[컬럼별 작성 규칙]",
        "[HTML 사용 규칙]",
    ):
        assert gone not in text
    assert text.count("- 각 항목은 아래 형식을 따른다.") == 0  # Step E 형식 두 줄(R/2214-2215) 지움
    assert "[FINAL OUTPUT — JSON ONLY]" in text
    assert '"impact_type": "긍정" | "부정",' in text
    assert text.count("- 답변은 반드시 **한국어**로 작성한다.\n") == 1  # 셀 46 R/2227(감독 처분 ⑤)
    assert "테이블" not in text  # R/2153 도 「하나의 결과로」(셀 50 R/2425 선례, 감독 Q3)
    assert "컨트로버시/정책을 연결해 하나의 결과로 정리하는 것이다.\n" in text
    assert '"value_chain_activities": ["<business_activity 글 그대로>"],' in text
    assert "[Step E] 컨트로버시/규제 연결" in text and "[Step D]" in text  # 그대로 구간
    assert text.count("=" * 71) == 12  # 머리 다섯 쌍(A~E) + JSON 절의 한 쌍


def test_financial_system_adds_one_line() -> None:
    text = p.FINANCIAL_SYSTEM
    risk = '      "risk_type": "리스크-규제 및 법률" | "리스크-평판" | "리스크-기술" | "리스크-시장" | null,\n'
    chain = '      "value_chain_activities": ["<business_activity 글 그대로>"],\n'
    assert text.count(chain) == 1
    assert risk + chain + '      "context": {\n' in text
    without = text.replace(chain, "")
    assert sha(without) != sha(text)
    assert "[FINAL OUTPUT — JSON ONLY]" in text and "- 중요(보완 규칙):" in text.replace("**", "")
    assert "-context.controversies는 <Controversies for this topic> 블록에서만 추출" in text  # 추출 세 줄


def test_pathway_system_output_section() -> None:
    text = p.PATHWAY_SYSTEM
    assert text.startswith("\nYou are a senior ESG & financial materiality analyst")
    assert "[형식 규칙]" not in text and "Header는" not in text
    assert "[Impact Pathway 예시]" in text
    assert '"pathways": [' in text and '"i": <입력 표의 행 번호(1부터)>,' in text
    assert "- 여러 항목을 도출한 경우, “A, B, C” 형식으로 한 줄에 연결한다.\n" in text
    assert text.endswith("  ]\n}\n")


def test_impact_user_by_hand() -> None:
    """셀 46 의 규제 줄은 5칸이라 dedent 가 5칸만 벗긴다(코랩대로 — 다른 줄에 1칸이 남는다)."""
    got = p.impact_user("가상물류", INDUSTRY, [], "가상토픽", "가상 서브", "가상 서브 설명", NO_CON, NO_REG)
    industry = "[{'standard': 'SASB', 'industry_name': '가상 산업', 'description': '가상 설명'}]"
    assert got == (
        "\n [Company]\n - Name: 가상물류\n - Industry: " + industry + "\n\n\n"
        " <value_chain_list>\n   []\n   </value_chain_list>\n\n"
        " <ESRS Topic, Subtopic>\n - Topic: 가상토픽\n - Subtopic: 가상 서브\n - Subtopic description: 가상 서브 설명\n"
        " </ESRS Topic, Subtopic>\n\n"
        " <Controversies for this topic>\n 제공된 컨트로버시 정보 없음\n </Controversies for this topic>\n\n"
        " <Regulation & Policy Updates for this topic>\n제공된 정책/규정/가이드라인 정보 없음\n"
        " </Regulation & Policy Updates for this topic>\n"
    )


def test_financial_user_by_hand() -> None:
    got = p.financial_user("가상물류", INDUSTRY, [], "가상토픽", "가상 서브", "가상 서브 설명", NO_CON, NO_REG)
    industry = "[{'standard': 'SASB', 'industry_name': '가상 산업', 'description': '가상 설명'}]"
    assert got == (
        "\n[Company]\n- Name: 가상물류\n- Industry: " + industry + "\n\n"
        "<value_chain_list>\n  []\n</value_chain_list>\n\n"
        "<ESRS Topic, Subtopic>\n- Topic: 가상토픽\n- Subtopic: 가상 서브\n- Subtopic description: 가상 서브 설명\n"
        "</ESRS Topic, Subtopic>\n\n"
        "<Controversies for this topic>\n제공된 컨트로버시 정보 없음\n</Controversies for this topic>\n\n"
        "<Regulation & Policy Updates for this topic>\n제공된 정책/규정/가이드라인 정보 없음\n"
        "</Regulation & Policy Updates for this topic>\n"
    )


def test_multiline_bundle_text_stops_the_dedent() -> None:
    """묶음 글(json.dumps indent 2)의 둘째 줄부터는 0칸이라 dedent 가 아무것도 벗기지 못한다(코랩 셀 50 그대로)."""
    bundle = wire.context_text({"json": {"items": []}, "raw_text": None, "parse_error": None}, "controversy")
    industry3 = INDUSTRY * 3
    chain = [{"business_activity": "가상 활동"}]
    got = p.financial_user("가상물류", industry3, chain, "가상토픽", "가상 서브", "설명", bundle, NO_REG)
    assert got.startswith("\n      [Company]\n      - Name: 가상물류\n")
    assert "      - Industry: " + repr(industry3) + "\n" in got
    assert "        [{'business_activity': '가상 활동'}]\n" in got
    assert "\n      {\n" + '  "json": {\n' in got
    impact = p.impact_user("가상물류", industry3, chain, "가상토픽", "가상 서브", "설명", bundle, NO_REG)
    assert "\n     제공된 정책/규정/가이드라인 정보 없음\n" in impact  # 5칸 줄 그대로


def test_pathway_user_by_hand() -> None:
    got = p.pathway_user("| Topic |\n|---|")
    assert got == (
        "아래는 Topic–Subtopic—영향 정의 표의 결과물이다.\n"
        "각 표의 “행(row)”마다 1개씩, 입력된 ‘Topic’,‘Subtopic’, ‘영향 정의’별로 “재무 Impact Pathway”를 생성해줘.\n\n"
        "요구사항:\n"
        "- 각 ‘Topic’,‘Subtopic’, ‘영향 정의’마다 ① Impact Driver → ② 비즈니스 영향 → ③ 재무 영향을 모두 출력할 것\n"
        "- ESRS/ISSB 기준에 따라 재무 영향 매핑은 정합성 있게 추론\n\n"
        "주의:\n"
        "- 헤더를 제외한 각 행 = 1개의 i 행(영향 정의의 행)으로 작성할 것.\n"
        "- 총 행 개수와 i 행(영향 정의의 행) 개수는 반드시 같아야 한다.\n"
        "- 영향 정의를 서로 합치거나 “대표 사례만” 다루지 말 것.\n\n"
        "[INPUT TABLE BELOW]\n| Topic |\n|---|"
    )


def test_no_date_range_in_part2_texts() -> None:
    """2부 프롬프트 셋에는 조사 기간이 없다(코랩대로) — 지은 예시의 기간 글이 어디에도 안 실린다."""
    date_range = "2025-01-01~오늘까지"
    texts = [
        p.IMPACT_SYSTEM,
        p.FINANCIAL_SYSTEM,
        p.PATHWAY_SYSTEM,
        p.impact_user("가상", INDUSTRY, [], "t", "s", "d", NO_CON, NO_REG),
        p.financial_user("가상", INDUSTRY, [], "t", "s", "d", NO_CON, NO_REG),
        p.pathway_user("| t |"),
    ]
    assert all(date_range not in t and "date_range" not in t and "기간" not in t for t in texts)
    assert json.dumps(texts, ensure_ascii=False).count("조사 기간") == 0
