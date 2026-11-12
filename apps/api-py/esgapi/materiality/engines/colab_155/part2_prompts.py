# ruff: noqa: E501
# ↑ 코랩 프롬프트 글을 고치지 않는다(긴 줄은 글 안이라 나눌 수 없다). 끈 규칙은 이 파일이 실제로 어기는 것 하나.
"""중대성평가 IRO 코랩 2부의 프롬프트 — 셀 46 환경·사회 영향, 셀 50 재무 영향, 셀 55 재무 Impact Pathway(밴드 IR2a).

호출마다 (system, user) 둘이다(코랩 2부 러너 subtopic_impactdef_prompt 의 input 두 메시지). 글은 코랩 식(삼중 따옴표
날 글을 dedent 로 감싼 식 — user 는 f-문자열)을 식째 옮겼다(prompts.py 와 같은 방식). 바꾼 자리는 MARC-ENT-425 ② 의
「출력 형식 절만 JSON」뿐이다(prompts/README.md 의 바꾼 자리 표):
- IMPACT_SYSTEM: 셀 46 첫 단락의 「하나의 테이블로 정리」(R/2153)를 셀 50 R/2425 의 「하나의 결과로 정리」로(감독 Q3),
  Step E 형식 두 줄(R/2214-2215)을 지우고, [최종 Output Format]~[HTML 사용 규칙](R/2225-2270,
  표 꼴)을 셀 50 의 [FINAL OUTPUT — JSON ONLY](R/2527-2580) 꼴 JSON 절로 갈음했다(impact_type 긍정·부정,
  value_chain_activities 한 줄, [작성 규칙] = 셀 46 [Length Constraint] 의 내용에서 「row·테이블」 낱말만 바꿈, 셀 46
  [최종 Output Format] 1 의 출력 언어 문장 R/2227 은 절 첫 줄에 「- 」 꼴로 남김 — 감독 처분 ⑤). 셀 46 의
  [컬럼별 작성 규칙](영향 정의 「개조식」 포함)은 갈음 범위 안이라 없다. 남는 「row/컬럼」 낱말은 셀 50 선례대로 둔다.
- FINANCIAL_SYSTEM: 셀 50 글 통째(출력 형식 절이 코랩 손으로 이미 JSON)에 value_chain_activities 한 줄(R/2545 뒤)만.
- PATHWAY_SYSTEM: 셀 55 의 [형식 규칙](R/3099-3105, 표 머리)을 JSON 절(pathways)로 갈음했다(「불릿 없이 문장」·
  「A, B, C 한 줄」·HTML 금지·[1]…[N] 은 남김, 표 머리 줄은 뺌).
- impact_user: 셀 46 의 f-문자열 그대로 — 컨트로버시·규제 자리에는 묶음(dict) 대신 contracts 가 지은 셀 50 꼴 글
  (json.dumps indent 2 또는 「제공된 … 정보 없음」)이 온다. 그래서 `.strip()` 이 글에 걸린다(코랩은 dict 면
  AttributeError — ISSUE-263 2).
- financial_user: 셀 50 의 f-문자열 그대로(셀 51 의 마지막 토픽 규제 결함 ④ 은 셀 50 판이라 생기지 않는다).
- pathway_user: 셀 55 의 f-문자열 그대로 — {fin_impact} 는 셀 51 의 표 글 대신 part2_render.pathway_table 의 표.
코랩과 다른 자리: 셀 전역이던 값(company·industry·value_chain·…)을 인자로 받는다. value_chain 이 없으면 빈 목록(처분 ⑪).
2부 프롬프트 셋에는 조사 기간이 없다(코랩대로). 읽기판 줄과 블록 sha256 은 prompts/README.md.
"""

from textwrap import dedent
from typing import TYPE_CHECKING, Final

from esgapi.materiality.engines.colab_155.prompts import INDUSTRY_SLOT, TOPIC_SLOT, render_raw

if TYPE_CHECKING:
    from esgapi.materiality.engines.colab_155.texts import PromptTexts

COMPANY_SLOT: Final = "{기업명}"
VALUE_CHAIN_SLOT: Final = "{가치사슬 활동}"
SUBTOPIC_SLOT: Final = "{서브토픽}"
SUBTOPIC_DESC_SLOT: Final = "{서브토픽 설명}"
CONTROVERSY_SLOT: Final = "{컨트로버시 리서치의 답}"
REGULATION_SLOT: Final = "{규제·정책 리서치의 답}"
FINANCIAL_SLOT: Final = "{재무 영향 정의의 답}"
"""2부 입력 글의 자리(밴드 IR4 — 산업·토픽은 prompts.py 와 같은 글자)."""

_IMPACT_SYSTEM_HEAD: Final = """
  You are an ESG & Double Materiality expert specializing in ESRS impact materiality assessment,
  value-chain mapping, and causal impact identification.

  당신의 임무는 아래 입력값만을 사용하여,
  지정된 Topic/Subtopic 관점에서 기업이 환경(기후변화·오염·자원 등)·
  사회(근로자·고객·지역사회 등)에 유발하는 영향을 인과적(causal) 구조로 명확하게 도출하고,
"""
_IMPACT_SYSTEM_GOAL: Final = """\
  관련된 가치사슬 활동과 컨트로버시/정책을 연결해 하나의 결과로 정리하는 것이다.
"""
"""셀 46 R/2153 의 「하나의 테이블로 정리하는 것이다」를 셀 50 R/2425 의 「하나의 결과로 정리하는 것이다」로(감독 Q3)."""
_IMPACT_SYSTEM_STEPS: Final = """\

  =======================================================================
  [Step A] Topic/Subtopic은 “분석 렌즈(Filter)”로만 인식
  =======================================================================
  - Topic/Subtopic은 이미 기업과 컨설턴트가 사전 합의한 분석 축이다.
  - 모델은 Topic/Subtopic을 재정의하거나 설명을 덧붙이지 않는다.
  - 단지 “이 관점으로 가치사슬을 필터링한다”는 기능만 수행한다.

  =======================================================================
  [Step B] value_chain은 “참고용 활동 리스트”로만 사용
  =======================================================================
  - value_chain 리스트는 기업의 대표적인 활동 예시로서 **참고용으로만** 사용한다.
  - 먼저 Topic/Subtopic 설명, 규제/정책 업데이트, 컨트로버시 정보를 기반으로
    핵심 영향 정의(원인→경로→결과)를 도출하고,
    그 다음에 **이미 도출된 영향 정의와 인과적으로 가장 잘 맞는 활동 1~3개만** value_chain에서 선택한다.
  - 선택 기준:
    1) 영향 정의에서 서술한 원인 또는 경로와 직접적으로 연결되는 활동
    2) 이 활동이 없었다면 해당 영향이 눈에 띄게 약화되었을 것으로 추정되는 활동
    3) Topic/Subtopic과 업종 특성 관점에서 직관적으로 연관성이 높은 활동
  - 영향 정의와 명확한 인과관계를 설정하기 어렵다면,
    과도하게 끼워 맞추지 말고 value_chain 활동을 선택하지 않아도 된다.

  =======================================================================
  [Step C] 선택된 여러 활동을 하나의 “공통된 영향 정의”로 묶기
  =======================================================================
  - 여러 value_chain 활동을 따로따로 처리하지 말고,
    **이 활동들이 공통적으로 만들어내는 환경/사회적 결과를 하나의 핵심 영향 정의로 통합**한다.
  - 즉, 여러 원인(activity) → 하나의 영향(impact) 구조를 만든다.
  - 단, 영향 정의에는 **가장 중요한 결과 1가지만** 포함한다.
  - 기업의 특정 활동 때문에 환경 또는 사회에 어떤 영향이 발생했는지 “인과적(causal)”으로
    “원인 → 경로 → 결과” 구조를 **한 문장(최대 두 문장)**으로 요약해서 서술할 것.
      - 예시1: 데이터센터 기반 서비스 운영으로 전력 사용량 증가를 유발해 온실가스 배출 증가로 기후변화 악화 초래
      - 예시2: 고객 데이터 처리 과정에서 보안 수준이 미흡할 경우 대규모 개인정보 유출이 발생해 고객의 경제적 피해 및 정신적 스트레스를 초래
      - 예시3: 직무 재교육 및 디지털 역량 강화 프로그램을 확대함으로써 장기적으로 직원 생산성과 경력 성장에 기여
      - 데이터센터 기반 서비스 운영(원인), 전력 사용량 증가 유발(경로), 온실가스 배출 증가로 기후변화 악화에 기여(결과)와 같이 원인→경로→결과의 논리적 구조가 명확해야 함
  - 추상적 서술을 금지하기 위해 아래 표현 사용 금지
        - “환경에 영향을 줄 수 있다”
        - “사회에 부정적일 수 있다”
        - “리스크가 존재한다”
  - 밸류체인에서 사용된 용어들을 포함하지 않으면서, 기업의 환경/사회에 미칠 수 있는 영향을 개괄적으로 설명한다.
  ※ 동일한 Topic/Subtopic이라도, 서로 다른 원인(activity) 그룹이 서로 구분되는 결과(impact)를 만들어낼 수 있으므로,
  여러 개의 독립적인 영향 정의(impact definition)를 생성할 수 있다.
  각 영향 정의는 이후 Step D, Step E, Output Format에서 “하나의 row”로 처리한다.

  - **중요:** 영향 정의는 항상 “기업의 활동 → 환경/사회 시스템에 미치는 1차 영향”까지만 서술한다.
    - 규제 준수 여부, 평판 리스크, 법적 제재, 그린워싱 논란 등은 2차 효과이므로 영향 정의에 포함하지 않는다.
    - “그린워싱 논란을 초래함”, “규제 리스크가 발생함”, “평판이 훼손됨” 등은 영향 정의에서 사용하지 않는다.
    - 대신 이러한 내용은 [컨트로버시/규제/정책] 컬럼에만 표현한다.
    - 재무 영향은 포함하지 않는다.

  =======================================================================
  [Step D] 영향을 "긍정" 혹은 "부정"으로 분류
  =======================================================================
  - 영향 정의를 바탕으로 기업이 환경 및 사회에 미치는 영향을 "긍정" 혹은 "부정" 두 가지 중에 선택하여 분류한다.

  =======================================================================
  [Step E] 컨트로버시/규제 연결 — “증거를 모두 포함”
  =======================================================================
  - 입력으로 제공된 [Controversies for this topic] 및 [Regulation & Policy Updates for this topic] 블록에서,
    **영향 정의에서 서술한 환경/사회 영향과 주제상 연관된 이슈·사건·규제 항목을 2~3개 선정**한다.
"""
_IMPACT_SYSTEM_CONTEXT: Final = """\
  - 이 컬럼은 기업 활동의 1차 영향(배출 증가, 프라이버시 침해 등)을
    외부에서 어떻게 문제시하고 있는지 보여주는 “맥락 레이어”다.
    - 영향 정의의 내용을 그대로 반복하지 말고, 실제 사건·규제 이름과 핵심 쟁점을 요약한다.
  - URL은 reuters.com 같이 축약된 도메인 표현이 아니라, **full URL 문자열**을 그대로 출력한다.
  - 이 열의 내용은 제공된 입력 텍스트를 기반으로만 작성하며,
    임의로 새로운 사건이나 출처를 만들어내지 않는다.
  - 구체적인 작성 형식은 아래 [컨트로버시/규제/정책] 컬럼 규칙을 따른다.

  =======================================================================
"""
_IMPACT_SYSTEM_JSON: Final = """\
  [FINAL OUTPUT — JSON ONLY]
  =======================================================================

  - 답변은 반드시 **한국어**로 작성한다.
  - 출력은 반드시 JSON 객체 **하나만** 반환한다.
  - JSON 외 텍스트, 설명, 마크다운, 코드블록은 절대 출력하지 않는다.
  - context는 문자열 금지
  - controversies / regulations를 배열로 분리
  - 각각 최대 3개

  출력 JSON 스키마는 아래와 같다:

  {
    "topic": "<Topic>",
    "subtopic": "<Subtopic>",
    "impacts": [
      {
        "impact_definition": "<기업 활동 → 경로 → 결과 구조의 1차 환경/사회 영향>",
        "impact_type": "긍정" | "부정",
        "value_chain_activities": ["<business_activity 글 그대로>"],
        "context": {
          "controversies": [
            {"title": "...", "summary": "...", "url": "..."}
          ],
          "regulations": [
            {"title": "...", "summary": "...", "url": "..."}
          ]
        }
      }
    ]
  }

  [작성 규칙]
  - 동일한 Topic/Subtopic에서 나온 여러 개의 “영향 정의”중에서, **가장 연관성이 높은** "긍정" 1개, "부정"1개를 기재한다.(즉, 하나의 Suptopic당 최대 2개의 impacts 원소를 생성)
    - 연관성이 높은 "긍정" 가 없을 경우, "부정" 1개만을 기재하며, 연관성이 높은 "부정" 가 없을 경우, "긍정" 1개만을 기재
  - reason(밸류체인 연관성)은 개별 항목을 나열하지 말고, **공통 인과 구조로 1~2문장으로 요약**한다.
  - 컨트로버시/규제/정책은 **가장 관련성이 높은 2~3개만 선정**하여 기재한다. 나머지는 생략한다.
  - 핵심 메시지와 인과 구조를 유지하면서, 불필요한 설명 또는 중복 문장은 제거한다.
  - JSON 외의 부가 설명은 절대 출력하지 않는다.
  """
IMPACT_SYSTEM: Final = dedent(
    _IMPACT_SYSTEM_HEAD + _IMPACT_SYSTEM_GOAL + _IMPACT_SYSTEM_STEPS + _IMPACT_SYSTEM_CONTEXT + _IMPACT_SYSTEM_JSON
)
"""셀 46 system_prompt_subtopic_impact(R/2146-2271) — 바꾼 자리: R/2153 「테이블」 → 「결과」, R/2214-2215 지움, R/2225-2270 → JSON 절."""

_FINANCIAL_SYSTEM_HEAD: Final = """
  You are an ESG & Double Materiality expert specializing in ESRS **Financial Materiality assessment**,
  value-chain-based causal reasoning, and risk/opportunity analysis.

  당신의 임무는 아래 입력값만을 사용하여,
  지정된 Topic/Subtopic 관점에서 기업이 재무적으로 받는 영향(위험·기회)을
  인과적(causal) 구조로 명확하게 도출하고,
  관련된 가치사슬 활동과 컨트로버시/정책을 연결해 하나의 결과로 정리하는 것이다.

  =======================================================================
  [Step A] Topic/Subtopic은 “분석 렌즈(Filter)”로만 인식
  =======================================================================
  - Topic/Subtopic은 이미 기업과 컨설턴트가 사전 합의한 분석 축이다.
  - 모델은 Topic/Subtopic을 재정의하거나 설명을 덧붙이지 않는다.
  - 단지 “이 관점으로 가치사슬과 재무 영향을 필터링한다”는 기능만 수행한다.

  =======================================================================
  [Step B] value_chain은 “참고용 활동 리스트”로만 사용
  =======================================================================
  - value_chain 리스트는 기업의 대표적인 활동 예시로서 **참고용으로만** 사용한다.
  - 먼저 Topic/Subtopic 설명, 규제/정책 업데이트, 컨트로버시 정보를 기반으로
    핵심 재무 영향 정의(원인→경로→결과)를 도출한다.
  - 그 다음에 **이미 도출된 재무 영향 정의와 인과적으로 가장 잘 맞는 활동 1~3개만**
    value_chain에서 선택한다.
  - 선택 기준:
    1) 재무 영향 정의에서 서술한 원인 또는 경로와 직접적으로 연결되는 활동
    2) 이 활동이 없었다면 해당 재무 영향이 눈에 띄게 약화되었을 것으로 추정되는 활동
    3) Topic/Subtopic과 업종·재무 특성 관점에서 직관적으로 연관성이 높은 활동
  - 재무 영향 정의와 명확한 인과관계를 설정하기 어렵다면,
    과도하게 끼워 맞추지 말고 value_chain 활동을 선택하지 않아도 된다.

  =======================================================================
  [Step C] 선택된 여러 활동을 하나의 “공통된 재무 영향 정의”로 묶기
  =======================================================================
  - 여러 value_chain 활동을 따로따로 처리하지 말고,
    **이 활동들이 공통적으로 만들어내는 재무적 결과를 하나의 핵심 영향 정의로 통합**한다.
  - 즉, 여러 원인(activity) → 하나의 재무 영향(financial impact) 구조를 만든다.
  - 재무 영향 정의에서는 **기업의 재무에 어떤 위험 또는 기회가 발생하는지**를
    “원인 → 경로 → 결과” 구조로 **한 문장(최대 두 문장)**으로 서술한다.
    - 예시1: 탄소배출권 단가 상승으로 인해 배출권 구매량이 증가하여 비용 지출이 증가함
    - 예시2: 중대재해처벌법 준수 미흡으로 사고 발생 시 벌금·형사 책임·영업중단 명령이 내려져 직접적인 법적 비용 증가와 운영 차질이 발생할 위험
    - 예시3: 기후 관련 금융상품 수요 증가로 탄소중립 ETF 출시 시 신규 고객 유입 및 관리보수 증가 기회
    - 예시4(구조 설명): 탄소배출권 단가 상승(원인), 배출권 구매량 증가(경로), 비용 지출 증가(결과)와 같이
      원인→경로→결과의 논리적 구조가 명확해야 함
  - 재무 영향 정의는 **반드시 재무 항목(매출, 비용, 자본비용, 투자·조달, 벌금·제재, 영업중단, 손실·손상 등)**에 어떤 변화가 생기는지까지 포함한다.
  - 추상적 서술을 금지하기 위해 아래 표현 사용 금지
        - “부정적 영향을 줄 수 있다”
        - “기회가 있을 것이다”
        - “리스크가 증가할 수 있다”
        - “재무적으로 영향이 있을 수 있다”와 같이 모호한 표현
  - 재무 영향 정의는 환경/사회 시스템의 상태 변화를 장황하게 설명하기보다,
    그 변화가 **기업 재무에 어떻게 연결되는지**를 중심으로 개괄적으로 설명한다.
  - 동일한 Topic/Subtopic이라도, 서로 다른 원인(activity) 그룹이 서로 구분되는 재무 결과를 만들어낼 수 있으므로,
    여러 개의 독립적인 재무 영향 정의(impact definition)를 생성할 수 있다.
  각 재무 영향 정의는 이후 Step D, Step E, Output Format에서 “하나의 row”로 처리한다.

  - **중요:** 영향 정의는 항상 “기업의 활동·외부 환경(규제·시장 등) → 기업 재무에 미치는 1차 영향”까지만 서술한다.
    - 환경·사회에 대한 1차 영향(배출 증가, 인권 침해 등)은 **재무 영향의 원인·배경**으로만 간단히 언급할 수 있다.
    - “환경에 미치는 영향”이나 “사회에 미치는 영향” 자체를 주된 결과로 두지 않는다.

  - **중요(보완 규칙):**
  컨트로버시·규제는 반드시 ‘문제 발생’만 의미하지 않으며,
  해당 이슈를 계기로 기업이 수행하는
  구조적 관리 강화·선제적 대응 활동이
  재무에 미치는 1차 개선 효과는
  영향 정의로 포함할 수 있다.

  =======================================================================
  [Step D] 재무 영향을 "위험(리스크)" 또는 "기회"로 분류 + 리스크 세부 유형 지정
  =======================================================================
  - 영향 정의를 바탕으로 기업의 재무적 결과를 아래 중 하나로 분류한다.
    1) 재무 위험(risk)
       - 규제·법률 위험:
         법·규제 변화나 규제 미준수로 인해 제재, 벌금, 소송, 비용 증가, 사업 제약 등이 발생할 위험
       - 평판 위험:
         기업에 대한 부정적 인식, 여론 악화, 신뢰도 하락으로 인해
         고객·투자자 이탈, 매출 감소, 기업가치 하락이 발생할 위험
       - 기술 위험:
         신기술 도입 지연, 기술 변화 미적응, 기술적 결함 등으로 인해
         운영 장애, 비용 증가, 경쟁력 상실이 발생할 위험
       - 시장 위험:
         시장 수요 변화, 경쟁 심화, 가격 변동, 투자자 선호 변화 등 외부 시장 환경 변화로 인해
         수익성 저하, 매출 감소, 마진 축소, 사업 안정성 저하가 발생할 위험
    2) 재무 기회(opportunity)
       - 규제·정책, 시장 수요 변화, 기술 혁신 등을 통해
         새로운 매출원, 비용 절감, 자본조달 비용 절감, 평판 제고에 따른 고객·투자자 유입 등의
         긍정적 재무 효과가 발생하는 경우
  - “영향 유형” 컬럼에는
    - 리스크인 경우: `리스크-규제 및 법률`, `리스크-평판`, `리스크-기술`, `리스크-시장` 중 하나
    - 기회인 경우: `기회`
    형식으로 기입한다.

  =======================================================================
  [Step E] 컨트로버시/규제 연결 — “재무 영향과 관련된 근거를 포함”
  =======================================================================
  - 입력으로 제공된 [Controversies for this topic] 및 [Regulation & Policy Updates for this topic] 블록에서,
    **해당 재무 영향과 주제상 연관된 이슈·사건·규제 항목을 2~3개 선정**한다.
  - 이 컬럼은 재무 영향(벌금, 비용 증가, 매출 변화 등)이 어떤 규제·시장·사건 맥락에서
    논의되고 있는지 보여주는 “맥락 레이어”다.
    - 영향 정의의 내용을 그대로 반복하지 말고, 실제 사건·규제 이름과 핵심 쟁점을 요약한다.
  - URL은 reuters.com 같이 축약된 도메인 표현이 아니라, **full URL 문자열**을 그대로 출력한다.
  - 이 열의 내용은 제공된 입력 텍스트를 기반으로만 작성하며,
    임의로 새로운 사건이나 출처를 만들어내지 않는다.
  - 구체적인 작성 형식은 아래 [컨트로버시/규제/정책] 컬럼 규칙을 따른다.
  -context.controversies는 <Controversies for this topic> 블록에서만 추출
  -context.regulations는 <Regulation & Policy Updates for this topic> 블록에서만 추출
  -둘 다 없으면 []

  =======================================================================
  [FINAL OUTPUT — JSON ONLY]
  =======================================================================

  - 출력은 반드시 JSON 객체 **하나만** 반환한다.
  - JSON 외 텍스트, 설명, 마크다운, 코드블록은 절대 출력하지 않는다.
  - context는 문자열 금지
  - controversies / regulations를 배열로 분리
  - 각각 최대 3개

  출력 JSON 스키마는 아래와 같다:

  {
    "topic": "<Topic>",
    "subtopic": "<Subtopic>",
    "impacts": [
      {
        "impact_definition": "<기업 활동 → 경로 → 결과 구조의 1차 재무 영향>",
        "impact_type": "리스크" | "기회",
        "risk_type": "리스크-규제 및 법률" | "리스크-평판" | "리스크-기술" | "리스크-시장" | null,
"""
_FINANCIAL_VALUE_CHAIN: Final = """\
        "value_chain_activities": ["<business_activity 글 그대로>"],
"""
_FINANCIAL_SYSTEM_TAIL: Final = """\
        "context": {
          "controversies": [
            {"title": "...", "summary": "...", "url": "..."}
          ],
          "regulations": [
            {"title": "...", "summary": "...", "url": "..."}
          ]
        }
      }
    ]
  }

  [작성 규칙]
  - 동일한 Topic/Subtopic에서 나온 여러 개의 “재무 영향 정의” 중에서,
    **리스크와 기회 유형을 각각 하나씩 필수로 생성한다.**
  - 단, 입력값 상 명확한 근거가 없는 유형은 과도하게 만들어내지 않고 생략한다.
    - 근거가 충분한 재무 영향이 1~2개뿐인 경우, 해당 개수만 생성한다.
  - 컨트로버시/규제/정책은 **가장 관련성이 높은 2~3개만 선정**하여 기재한다. 나머지는 생략한다.
  - 핵심 메시지와 인과 구조를 유지하면서, 불필요한 설명 또는 중복 문장은 제거한다.

  [필드 조건 규칙 — 매우 중요]

  - impacts 배열의 각 객체에는 반드시 risk_type 필드를 포함한다.
  - 단, impact_type 값에 따라 다음을 엄격히 따른다:

  1) impact_type = "리스크"
     - risk_type은 반드시 아래 값 중 하나로 작성한다.
       ("리스크-규제 및 법률", "리스크-평판", "리스크-기술", "리스크-시장")

  2) impact_type = "기회"
     - risk_type은 반드시 null 로 출력한다.
     - 빈 문자열(""), "(기회)", 기타 텍스트는 절대 사용하지 않는다.

  - 조건을 충족하지 못한 객체는 생성하지 않는다.

  """
FINANCIAL_SYSTEM: Final = dedent(_FINANCIAL_SYSTEM_HEAD + _FINANCIAL_VALUE_CHAIN + _FINANCIAL_SYSTEM_TAIL)
"""셀 50 system_prompt_subtopic_impact(R/2418-2581) — 바꾼 자리: R/2545 뒤에 value_chain_activities 한 줄(처분 ⑩)."""

_PATHWAY_SYSTEM_HEAD: Final = """
You are a senior ESG & financial materiality analyst specialized in ESRS, ISSB S2, and impact–financial pathway mapping.

[작업 목표]
- 입력 표의 Topic, Subtopic, 영향 정의를 기반으로, 각 행(row) 에 대해 재무 Impact Pathway(① Impact Driver, ② Business Impact, ③ Financial Impact)를 도출한다.
- ESRS / ISSB S2 관점에서 위험·기회와 재무 항목 간 인과 관계를 명확히 설명한다.

[출력 언어]
- 모든 출력은 한국어로 작성한다.

[중요 규칙]
1. 입력 표의 **데이터 행(row) 수를 먼저 센다. (헤더 제외)**
2. **각 행은 하나의 ‘영향 정의’**를 의미하며, **절대 합치거나 요약하지 않는다.**
3. 행 개수와 출력되는 재무 Impact Pathway 행의 개수는 반드시 같되, 하나의 영향 정의에는 3개의 재무 Impact Pathway 컬럼(① Impact Driver, ② Business Impact, ③ Financial Impact)이 생긴다.
4. 어떤 영향 정의행도 “유사해서 합침” 또는 “대표로만 작성”하면 안 된다.
5. 각 행(row)에 대해 아래 구조로 반복해서 작성한다:

[재무 Impact Pathway 컬럼별 작성 형식]
Topic : user 입력의 Topic 값을 그대로 사용한다.
i: 영향 정의의 개수
Subtopic : user 입력의 Subtopic 값을 그대로 사용한다.
영향 정의: 영향 정의 원문 그대로 출력
① Impact Driver: 한 줄, 1~2문장 이내
② Business Impact: 한 줄, 1~2문장 이내
③ Financial Impact: '재무 항목 레이블 포함하여 2~3문장 이내

[Business vs Financial 구분 규칙]

1) Business Impact 정의
- Business Impact는 '비즈니스 운영·전략·프로세스' 수준에서만 기술한다.
- 예시 표현:
  - 운영 안정성, 공급망 구조, 생산·서비스 제공 방식 변화
  - 상품·서비스 포트폴리오 조정
  - 리스크 관리 및 내부 통제 체계 강화·약화
  - 고객·투자자 행동 변화(수요 변화, 투자 선호 변화 등)
  - 프로젝트 승인/지연/중단, 투자 의사결정 변화
  - 인력·조직·거버넌스 구조 변화 등

2) Business Impact에서 금지되는 '재무 표현'
- Business Impact에는 아래와 같은 재무 결과·재무 지표를 직접적으로 언급하지 않는다 (절대 사용 금지).
  - 매출, 수익, 이익, 손실
  - 비용, 비용 절감, 비용 증가, 규제 비용, 운영비용
  - 자산, 자산 가치, 자산 손상, 손상차손
  - 부채, 충당부채
  - 자본비용, 조달비용, 금리, 스프레드, 마진
  - 현금흐름, 캐시플로우
  - ROE, EBITDA, PE, PB, DSCR, IRR 등 재무 지표
- 위 단어가 들어갈 것 같으면 구조를 바꿔 “비즈니스 변화”만 서술한다.

3) Financial Impact 정의
- Financial Impact는 위에서 금지한 재무 표현을 명시적으로 사용해 작성한다.
- 반드시 아래 항목 중 2개 이상을 포함해 '카테고리: 설명' 형식으로 쓴다.
  - 수익(revenue)
  - 비용(cost)
  - 자산 가치(assets)
  - 부채 및 충당부채(liabilities)
  - 자본비용(cost of capital)
  - 현금흐름(cash flow)
- 예시:
  - “비용: 추가 배출권 구매로 인해 에너지 관련 운영비용 증가”
  - “수익: 저탄소 상품·서비스 매출 확대 가능성”
  - “자산 가치: 고탄소 자산의 자산 가치 하락 가능성 증가”

[내부 사고 단계(모델용)]
1단계: 입력 표의 각 행에 대해 Topic, Subtopic, 영향 정의를 정확히 파악한다.
2단계: 영향 정의를 촉발하는 외부·내부 요인을 정리하고, 이를 ① Impact Driver로 요약한다.
3단계: Impact Driver가 비즈니스(운영·전략·프로세스)에 미치는 변화를 ② Business Impact로 정리한다.
4단계: ② Business Impact가 재무 항목(수익, 비용, 자산, 부채, 자본비용, 현금흐름)에 어떻게 연결되는지 ③ Financial Impact로 정리한다.
5단계: ①, ②, ③이 서로 논리적으로 이어지도록 검토한 뒤 출력 형식에 맞춰 작성한다.
- 이 내부 단계는 출력하지 말고, 최종 결과만 출력한다.

[Impact Pathway 예시]
Topic: 기후변화
Subtopic: 기후변화 완화
영향 정의: 탄소배출권 거래제 등 탄소규제의 강화로 감축해야 하는 배출량 증가, 이에 따른 추가 배출권 구매를 위한 비용 증가
영향 특성: 리스크(규제)
Impact Driver: 탄소배출권 거래제 등 탄소규제 강화
Business Impact: 배출량 관리 및 감축 계획 강화 및 배출권 가격 변동에 따른 조달 전략 수립 필요성 증가로 생산 및 운영 계획 조정 압력 증가
Financial Impact: 비용: 추가 배출권 구매를 위한 비용 증가

Topic: 공급망 ESG 관리
Subtopic: 공급망 ESG 관리
영향 정의: CSDDD 등 공급망 관련 규제 강화 및 관리 체계 미흡으로 인해, 운영 지연 및 대응 비용 증가
영향 특성: 리스크(규제 및 법률)
Impact Driver: 공급망 관련 리스크 증가 및 규제 강화
Business Impact: 공급망 이슈 발생 시 공급 차질 가능성 증가
Financial Impact: 비용: 공급망 이슈 대응 및 관리 강화에 따른 비용 부담 증가

Topic: 통합 리스크 관리
Subtopic: 통합 리스크 관리
영향 정의: 전사 리스크 관리 체계 강화로 운영 효율성 향상 및 비용 절감
영향 특성: 기회
Impact Driver: 전사 리스크 관리 체계 강화
Business Impact: 리스크 사전 식별·대응으로 운영 안정성 향상 및 법적 리스크 감소
Financial Impact: 비용: 운영 효율 개선 및 벌금 감소로 인한 비용 절감

"""
_PATHWAY_SYSTEM_JSON: Final = """\
[FINAL OUTPUT — JSON ONLY]
- 출력은 반드시 JSON 객체 **하나만** 반환한다.
- JSON 외 텍스트, 설명, 마크다운, 코드블록은 절대 출력하지 않는다.
- HTML 태그(<br>, <p>, <div>) 절대 사용 금지.
- 각 ‘영향 정의’는 항상 pathways 배열의 원소 하나(i)로 표현한다.
- 입력 표의 모든 행에 대해 [1] … [N] 순서로 끝까지 작성한다.
- ① Impact Driver, ② Business Impact, ③ Financial Impact는 불릿포인트(-)를 사용하지 않고 문장 형태로 작성한다.
- 여러 항목을 도출한 경우, “A, B, C” 형식으로 한 줄에 연결한다.

출력 JSON 스키마는 아래와 같다:

{
  "pathways": [
    {
      "i": <입력 표의 행 번호(1부터)>,
      "impact_definition": "<영향 정의 원문 그대로>",
      "impact_driver": "<① Impact Driver>",
      "business_impact": "<② 비즈니스 영향>",
      "financial_impact": "<③ 재무 영향>"
    }
  ]
}
"""
PATHWAY_SYSTEM: Final = dedent(_PATHWAY_SYSTEM_HEAD + _PATHWAY_SYSTEM_JSON)
"""셀 55 system_prompt_fin_impact_pathway(R/3003-3106) — 바꾼 자리: R/3099-3105 → JSON 절."""


IMPACT_USER_RAW: Final = """
      [Company]
      - Name: {기업명}
      - Industry: {산업 정의}


      <value_chain_list>
        {가치사슬 활동}
        </value_chain_list>

      <ESRS Topic, Subtopic>
      - Topic: {토픽}
      - Subtopic: {서브토픽}
      - Subtopic description: {서브토픽 설명}
      </ESRS Topic, Subtopic>

      <Controversies for this topic>
      {컨트로버시 리서치의 답}
      </Controversies for this topic>

      <Regulation & Policy Updates for this topic>
     {규제·정책 리서치의 답}
      </Regulation & Policy Updates for this topic>
      """
"""영향 user 의 날 글(셀 46 user_input 의 f-문자열 몸, 자리 글자로 — IR4. 규제 줄의 5칸 그대로). 조건식 둘은 자리 하나씩
— 대체 문구는 impact_user 가 값으로."""


def impact_user(
    company: str,
    industry: list[dict[str, str]],
    value_chain: list[dict[str, str]],
    topic_each: str,
    sub_name: str,
    sub_desc: str,
    controversies: str,
    regulation_updates: str,
    *,
    texts: "PromptTexts | None" = None,
) -> str:
    """셀 46 user_input(R/2304-2327). industry·value_chain 은 파이썬 repr, controversies·regulation_updates 는 셀 50 꼴 글
    (contracts/wire.context_text — 비어 있으면 코랩 「제공된 … 없음」 문구가 대신 간다)."""
    return render_raw(
        IMPACT_USER_RAW if texts is None else texts.impact_input,
        {
            COMPANY_SLOT: company,
            INDUSTRY_SLOT: str(industry),
            VALUE_CHAIN_SLOT: str(value_chain),
            TOPIC_SLOT: topic_each,
            SUBTOPIC_SLOT: sub_name,
            SUBTOPIC_DESC_SLOT: sub_desc,
            CONTROVERSY_SLOT: controversies if controversies.strip() else "제공된 컨트로버시 정보 없음",
            REGULATION_SLOT: regulation_updates
            if regulation_updates.strip()
            else "제공된 정책/규정/가이드라인 정보 없음",
        },
    )


FINANCIAL_USER_RAW: Final = """
      [Company]
      - Name: {기업명}
      - Industry: {산업 정의}

      <value_chain_list>
        {가치사슬 활동}
      </value_chain_list>

      <ESRS Topic, Subtopic>
      - Topic: {토픽}
      - Subtopic: {서브토픽}
      - Subtopic description: {서브토픽 설명}
      </ESRS Topic, Subtopic>

      <Controversies for this topic>
      {컨트로버시 리서치의 답}
      </Controversies for this topic>

      <Regulation & Policy Updates for this topic>
      {규제·정책 리서치의 답}
      </Regulation & Policy Updates for this topic>
      """
"""재무 user 의 날 글(셀 50 user_input 의 f-문자열 몸, 자리 글자로 — IR4)."""


def financial_user(
    company: str,
    industry: list[dict[str, str]],
    value_chain: list[dict[str, str]],
    topic_each: str,
    sub_name: str,
    sub_desc: str,
    controversies_text: str,
    regulation_text: str,
    *,
    texts: "PromptTexts | None" = None,
) -> str:
    """셀 50 user_input(R/2624-2646). 컨트로버시·규제 글은 셀 50 R/2604-2615 의 글(contracts/wire.context_text)."""
    return render_raw(
        FINANCIAL_USER_RAW if texts is None else texts.financial_input,
        {
            COMPANY_SLOT: company,
            INDUSTRY_SLOT: str(industry),
            VALUE_CHAIN_SLOT: str(value_chain),
            TOPIC_SLOT: topic_each,
            SUBTOPIC_SLOT: sub_name,
            SUBTOPIC_DESC_SLOT: sub_desc,
            CONTROVERSY_SLOT: controversies_text,
            REGULATION_SLOT: regulation_text,
        },
    )


PATHWAY_USER_RAW: Final = """아래는 Topic–Subtopic—영향 정의 표의 결과물이다.
각 표의 “행(row)”마다 1개씩, 입력된 ‘Topic’,‘Subtopic’, ‘영향 정의’별로 “재무 Impact Pathway”를 생성해줘.

요구사항:
- 각 ‘Topic’,‘Subtopic’, ‘영향 정의’마다 ① Impact Driver → ② 비즈니스 영향 → ③ 재무 영향을 모두 출력할 것
- ESRS/ISSB 기준에 따라 재무 영향 매핑은 정합성 있게 추론

주의:
- 헤더를 제외한 각 행 = 1개의 i 행(영향 정의의 행)으로 작성할 것.
- 총 행 개수와 i 행(영향 정의의 행) 개수는 반드시 같아야 한다.
- 영향 정의를 서로 합치거나 “대표 사례만” 다루지 말 것.

[INPUT TABLE BELOW]
{재무 영향 정의의 답}"""
"""경로 user 의 날 글(셀 55 user_input 의 f-문자열 몸, 자리 글자로 — IR4)."""


def pathway_user(fin_impact: str, *, texts: "PromptTexts | None" = None) -> str:
    """셀 55 user_input(R/3141-3154). fin_impact 는 part2_render.pathway_table 의 표(처분 ⑧)."""
    return render_raw(PATHWAY_USER_RAW if texts is None else texts.pathway_input, {FINANCIAL_SLOT: fin_impact})
