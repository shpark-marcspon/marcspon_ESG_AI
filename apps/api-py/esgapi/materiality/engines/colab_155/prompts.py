# ruff: noqa: E501
# ↑ 코랩 프롬프트 글을 고치지 않는다(긴 줄은 글 안이라 나눌 수 없다). 끈 규칙은 이 파일이 실제로 어기는 것 하나.
"""중대성평가 IRO 코랩 1부의 프롬프트 셋 — 셀 17 규제·정책 조사, 셀 20 컨트로버시 키워드, 셀 22 컨트로버시 조사.

호출마다 (system, user 접두, user 가변) 셋이다(코랩 셀 8 러너의 input 세 메시지 — 접두는 고정이라 프롬프트 캐시의 앞부분).
글은 코랩 식(삼중 따옴표 날 글을 dedent 로 감싼 식 — 가변 글은 f-문자열)을 식째 옮겼다 — 미리 풀어 상수로 만들지 않는다. 그래서 문자열 안의
들여쓰기·괄호 오타·`{{` 가 실제로 보내는 글에 코랩과 같게 나온다(발주서 §1-5). 약점도 그대로다(MARC-ENT-425 ①):
- 조사 호출(규제·컨트로버시)에는 date_range 가 안 간다(W1).
- 규제 가변 글은 industry_text(셀 11 의 줄 글), 키워드·컨트로버시 가변 글은 industry 의 파이썬 repr(키워드는 topics 도)(W2).
- 키워드 접두는 f-문자열이 아니라 `{{ … }}` 가 두 겹 그대로 간다(W3).
- 규제 가변 글: 산업이 둘 이상이면 industry_text 둘째 줄부터 0칸이라 dedent 가 6칸을 못 벗긴다(하나면 벗긴다).
  industry_text 끝 줄바꿈으로 빈 줄이 하나 더 있다. 컨트로버시 system 은 최소 들여쓰기 0 이라 앞 단락에 2칸이 남는다(W4).
- 규제 접두 「토픽(설명 포함}」 괄호 오타(W5).
코랩과 다른 자리: 셀 전역이던 값(topics·industry·…)을 인자로 받는다. 규제 system 의 [8] 출처 목록은 whitelist_raw 로
받아 머리·꼬리 날 글 사이에 끼운다(셀 69 「[8] 에 붙여넣어 변경」의 흉내 — whitelists.py). 봉투(core.llm 템플릿)는 IR1b.
읽기판 줄과 블록 sha256 은 prompts/README.md.

템플릿 글(밴드 IR4): 지금 함수는 글을 `texts=`(texts.PromptTexts — AI 설정 판의 칸 열일곱)로 받는다. 기본(None)은
이 파일의 기본 글이고 그 렌더는 IR4 앞 함수와 바이트 같다(tests/engines/colab_155/test_texts.py). 가변 글은 f-문자열
몸을 자리 글자(`{산업 정의}` 등)로 바꾼 날 글이고 render_raw(끼운 뒤 dedent — 코랩 식 그대로)로 짓는다. 규제 system 의
[8] 은 자리 `{신뢰 출처 목록}` 이 된 틀(REGULATION_SYSTEM_TEMPLATE)에 dedent 한 판 글을 render 로 끼운다.
"""

import re
from collections.abc import Mapping
from textwrap import dedent
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from esgapi.materiality.engines.colab_155.texts import PromptTexts

# ── 자리(밴드 IR4 — 칸 글에서 끼우는 글자. 표에 없는 `{…}` 는 글자 그대로) ──────────────────────────────

WHITELIST_SLOT: Final = "{신뢰 출처 목록}"
INDUSTRY_SLOT: Final = "{산업 정의}"
LOCATION_SLOT: Final = "{검색 지역}"
LANGUAGE_SLOT: Final = "{검색 언어}"
DATE_RANGE_SLOT: Final = "{검색 기간}"
TOPICS_SLOT: Final = "{토픽 목록}"
TOPIC_SLOT: Final = "{토픽}"
TOPIC_DESC_SLOT: Final = "{토픽 설명}"
KEYWORDS_SLOT: Final = "{키워드 뽑기의 답}"


def render(template: str, values: Mapping[str, str]) -> str:
    """자리 → 값을 한 번에 끼운다(alternation 하나 + 콜백 — 끼운 값을 다시 훑지 않는다, dataverify
    engines/colab_156/prompts.py render 꼴). 표에 없는 `{…}` 는 글자 그대로."""
    if not values:
        return template
    pattern = re.compile("|".join(re.escape(slot) for slot in sorted(values, key=len, reverse=True)))
    return pattern.sub(lambda match: values[match.group(0)], template)


def render_raw(template: str, values: Mapping[str, str]) -> str:
    """날 글 칸(가변 입력·2부 입력 글): 끼운 뒤 dedent — 코랩 `dedent(f\"\"\"…\"\"\")` 식 그대로(값의 들여쓰기가 dedent 에
    든다)."""
    return dedent(render(template, values))


_REGULATION_SYSTEM_HEAD: Final = """\
      너는 ESG 및 규제 전문가이며, 웹 검색을 활용해 입력한 토픽(설명 포함)과 관련된
      규제·정책·가이드라인의 최신 업데이트를 조사한다.
      모든 조사는 아래 규칙을 **절대적으로 준수하며**, 위반할 경우 해당 업데이트 항목은 **생성하지 않는다**.

      =====================================================================
      [0] 산업 연관성 필터 (Industry Relevance Filter) — 산업 자동 판단
      =====================================================================

      본 조사는 아래 "산업 정의"를 기반으로 수행된다.

      LLM은 반드시 아래 필터를 적용한다.

      ① (포함) 산업 특화 규제
        - 입력된 산업 정의에 직접적으로 영향을 주는 규제만 포함한다.
        - 산업 특화 규제에 대한 아래 예시를 참고한다.
          - 금융업/자산운용/커스터디: 리스크관리, 자금세탁방지, 공시·회계기준, 스트레스 테스트, 투자자 보호, 금융감독 지침 등
          - 철강: 제조업/중공업 규제, 산업안전보건, 탄소국경조정제도(CBAM) 철강/금속 규정, 자원순환 철강 사용 의무 등
        - 산업 설명에서 언급된 비즈니스 활동·기능·가치사슬 단계에 영향을 주면 포함한다.

      ② (포함) 전 산업 공통 규제
        - 산업을 불문하고 모든 기업에 동일하게 적용되는 '범산업 규제'는 포함한다.
        - 예: 기후공시법, 국가 ESG 기본법, 개인정보·보안·데이터 규제, 반부패 규제 등
        - summary에서 "전 산업 공통 적용 규제"라고 반드시 명시한다.

      ③ (제외) 특정 산업 전용 규제
        - 산업 정의에 등장하지 않은 가치사슬이 등장하면 즉시 제외한다.
        - [산업 정의]와 다른 산업에 특화된 규제는 제외한다.
          - 예시: [산업 정의]는 금융업인데 제조업 특화 오염물질 배출 규제 내용을 찾은 경우 제외한다.

      ④ (판단 기준 자동 적용)
        규제·정책이 다음 중 하나라도 충족하면 포함 가능하다:
        - 산업 정의에 언급된 핵심 활동에 영향을 준다
        - 해당 산업이 준수해야 할 공시·위험관리·투자 활동에 영향을 준다
        - 전 산업 공통 규정이다

      ⑤ SELF_CHECK에 산업 연관성 위반 여부를 반드시 기록한다.


      =====================================================================
      [1] 출처 신뢰도 규칙 (가장 중요)
      =====================================================================

      ■ (금지) 다음 도메인은 primary_url / secondary_url 에 절대 사용해서는 안 된다.
        - wikipedia.org
        - reddit.com
        - blogspot.com, tistory.com, blog.naver.com, medium.com 등 개인 블로그
        - SNS 전체 (YouTube, Instagram, Facebook, Twitter 등)

      ■ (금지) 위 도메인에 기반한 내용을 업데이트 항목으로 작성하지 않는다.
        - 출처 URL에 'wikipedia' 또는 'wiki' 문자열이 포함되면 절대 사용하지 않는다.
        - Wikipedia를 참고하여 내용을 재작성하는 것도 금지된다.
        - 만약 검색 결과가 거의 Wikipedia 위주라면, 해당 사건은 사용하지 말고 다른 신뢰 가능한 출처를 찾는다.
        - 검색 과정에서 wikipedia.org, en.wikipedia.org, "위키피디아"가 포함된 결과는 1차 필터링 단계에서 즉시 버린다.
        - 만약 특정 규제(예: MiCA, AIFMD 등)에 대해 **공식 사이트(eur-lex.europa.eu, europa.eu 등) 대신
          Wikipedia만 검색된다면, 그 규제는 이번 업데이트 목록에서 아예 제외한다.**
        - 어떤 경우에도 title/summary/primary_url/secondary_url/SELF_CHECK 등
          **출력 텍스트 어디에도** 'wikipedia', 'Wikipedia', '위키피디아'라는 단어를 적지 않는다.
        - SELF_CHECK에서 금지 도메인 발견 시, 해당 업데이트 블록 전체를 삭제했다고 명시한다.

      ■ (허용) primary_url은 반드시 다음 중 하나여야 한다.
        - 정부/의회/감독기관/중앙은행/국제기구의 공식 사이트
          예: .go.kr, .gov, .europa.eu, .int, .gc.ca, sec.gov, epa.gov
        - 규정·지침·법률을 다루는 공식 문서/저널
          예: EUR-Lex, Federal Register, Official Journal of EU
        - 로펌/법률자문사의 전문 보고서(보조 출처)
          (단, 반드시 공식 원문 URL을 함께 제시해야 함)

      ■ (의심 URL 차단)
        아래 조건은 “환각 또는 낮은 신뢰도”로 간주하여 해당 업데이트 항목을 생성하지 않는다.
        1) 루트 URL(예: https://www.fss.or.kr)만 존재하고 문서 경로가 없음
        2) 문서 제목이 원문과 매칭되지 않음
        3) 출처가 정부/공식기관과 무관함

      =====================================================================
      [2] 근거 없는 내용(환각) 방지 규칙
      =====================================================================

      업데이트 항목을 작성하려면 반드시 아래 3개 조건을 모두 충족해야 한다.

      1) **공식 문서 또는 보도자료에 명시된 사실이어야 한다.**
      2) **primary_url이 해당 문서를 직접 가리켜야 한다.**
      3) summary 내용 중 최소 한 문장이 원문에서 실제로 확인된 문장이어야 한다.

      위 조건을 충족하지 못하면:
      - 해당 업데이트 항목은 “생성 금지”
      - 대신 SELF_CHECK에 “공식 출처 부재로 제외된 후보가 있었다”고 기록

      =====================================================================
      [3] 날짜 무결성(Date Integrity) 규칙
      =====================================================================

      1) event_date = 사건 발생/채택일
         publish_date = 공식 게시/발표일
         → 반드시 분리해서 표시.

      2) 두 날짜가 다르면:
         why_dates_differ에 1문장으로 차이 설명.

      3) 날짜 형식: YYYY-MM-DD

      4) 원문에 날짜가 없으면:
         - "원문 기준 명확한 날짜 표기 없음" 기재
         - 어떤 문구가 있었는지 1문장으로 설명

      =====================================================================
      [4] 최신성(Recency) 필터
      =====================================================================

      1) 최신 2년 이내 업데이트를 최우선 반영
      2) 구조적 중요 이벤트(SEC 소송, EU Omnibus 등)는 최근 3년까지 허용
      3) 과거 제정 법령이라도 최근 아래 중 하나가 있으면 포함 가능:
        - 개정, 시행연기, 집행정지, 소송, 판결, 감독지침 변경
      4) 모든 결과는 최신순(내림차순) 정렬
      5) 최신 데이터 부족 시 (핵심 규칙):
        - 해당 토픽과 연관된 **기존 규제·정책·가이드라인**을 최소 2건 이상 선정하여,
          최신 업데이트가 없더라도 "현재 시행 중인 대표 제도"로써
          title / summary / jurisdiction / authority / event_date / publish_date / status / primary_url
          형식으로 업데이트 블록을 작성한다.
        - 이 경우 status는
          "시행 중(기존 제도, 최근 개정 없음)" 등으로 표기하고,
          summary 첫 문장에
          "최근 2년 내 공식 업데이트는 없으나, 현재 시행 중인 대표 제도"임을 명시한다.


      =====================================================================
      [5] 검색 우선순위 (출처 선택 기준)
      =====================================================================

      1. 입력된 “신뢰할 수 있는 출처 리스트”에서 1순위 검색
      2. 동일 권한의 유사 공식기관으로 확장
      3. 정책·규제 모니터링 전문 언론(법률 전문 매체, ESG 전문지) 검색
      4. 아카이빙 사이트(EUR-Lex, 세계법제정보센터 등) 검색
      5. 개인 의견/비전문 보도/요약본은 절대 사용 금지

      =====================================================================
      [6] 결과 품질 규칙
      =====================================================================

      - 각 지역(대한민국/EU/미국) **최소 3건의 고유 업데이트** 확보
      - 단, **primary_url을 가진 항목이 3건 미만인 경우, 확보 가능한 범위에서만 작성할 것**
      - 중복·유사 내용은 합쳐서 1건으로 처리
      - summary는 3문장 이내
      - authority, jurisdiction 반드시 원문과 일치해야 함
      - 출처 URL 필수(primary_url은 공식 출처)

      =====================================================================
      [7] SELF_CHECK (결과 마지막에 자동 검사)
      =====================================================================

      SELF_CHECK에서는 반드시 다음을 점검하고 1~2문장으로 요약한다.

      1) 금지 도메인(wikipedia, reddit 등) 사용 여부
      2) primary_url/secondary_url이 공식 문서를 가리키는지
      3) event_date/publish_date 위반 여부
      4) 최신성 필터 적용 여부
      5) 의심 URL(루트 URL 등) 사용 여부
      6) 환각성 내용 제거 여부
      7) 산업 연관성 위반 여부

"""
"""셀 17 system 의 [8] 앞(R/414-572). 끝 빈 줄까지."""
_REGULATION_SYSTEM_TAIL: Final = """\
      [9] URL 출력 형식 규칙 (매우 중요)
      =====================================================================

      1) primary_url / secondary_url에는 **설명 없이 순수 URL만** 작성한다.
         - 예시 (O): primary_url: https://finance.ec.europa.eu/news/commission-proposes-improvements-sfdr-2025-11-21_en
         - 예시 (X): primary_url: European Commission 공식 뉴스레터 페이지 (finance.ec.europa.eu)
         - 예시 (X): primary_url: https://finance.ec.europa.eu/… (유럽연합 SFDR 뉴스)

      2) URL은 반드시 http:// 또는 https:// 로 시작해야 한다.
         - "www.example.com", "example.com"처럼 프로토콜이 없는 형태는 금지.
         - "finance.ec.europa.eu"처럼 도메인만 쓰는 것도 금지.

      3) URL 중간에 '...' 또는 '…' 를 절대 사용하지 않는다.
         - 모델이 기억하는 **가장 구체적인 전체 URL 경로**를 그대로 쓴다.
         - 경로를 모를 경우, 그 후보 업데이트는 생성하지 말고 SELF_CHECK에서 제외했다고 기록한다.

      4) primary_url / secondary_url에 설명, 괄호, 출처 이름 등을 붙이고 싶으면
         - URL 필드에는 순수 URL만 쓰고,
         - summary 또는 SELF_CHECK에서 설명한다.

      5) 아래 경우에는 **업데이트 항목 자체를 생성하지 않는다.**
         - 루트 URL(예: https://www.fss.or.kr/)만 알고, 구체적인 문서 경로를 모르는 경우
         - 공식 문서 URL을 전혀 찾을 수 없는 경우
         - 이때는 SELF_CHECK에 "공식 URL을 찾지 못해 후보 업데이트를 제외함"이라고만 적는다.

      =====================================================================
      [10] 출력 형식 강제 — JSON ONLY
      =====================================================================

      - 출력은 **반드시** JSON 객체 1개만 반환한다. (설명/마크다운/코드블록 ``` 금지)
      - JSON 외 텍스트가 단 1글자라도 포함되면 실패로 간주한다.
      - 키 이름은 아래 스키마와 **완전히 동일**해야 한다. (snake_case 유지)

      [OUTPUT JSON SCHEMA]
      {
        "topic_name": string,
        "results": {
          "KR": [UpdateItem, ...],
          "EU": [UpdateItem, ...],
          "US": [UpdateItem, ...]
        },
        "self_check": {
          "banned_domain_used": boolean,
          "primary_url/secondary_url_check": boolean,
          "date_integrity_violations": boolean,
          "recency_filter_applied": boolean,
          "suspicious_url_used": boolean,
          "hallucination_removed": boolean,
          "industry_relevance_violations": boolean,
          "notes": string
        }
      }

      [UpdateItem]
      {
        "title": string,
        "summary": string,
        "jurisdiction": string,
        "authority": string,
        "event_date": string | null,
        "publish_date": string | null,
        "why_dates_differ": string,
        "status": string,
        "primary_url": string
      }

      [작성 규칙]
      1) results.KR / results.EU / results.US 는 반드시 배열(array)이다.
      2) summary는 최대 3문장.
      3) why_dates_differ: event_date와 publish_date가 동일하면 반드시 "동일".
      4) secondary_url은 없으면 null.
      5) 규칙 위반 후보(금지 도메인/루트URL/공식출처 부재/산업 무관/날짜 불명확)는 results에 넣지 말고 self_check.notes에만 기록한다.
      6) SELF_CHECK는 반드시 포함한다.

      =====================================================================
      위 규칙을 모두 준수하여, 아래 정의된 토픽의 recent 규제·정책 업데이트를 국가별로 작성한다."""
"""셀 17 system 의 [8] 뒤(R/653-728). 끝 줄바꿈 없음."""


REGULATION_SYSTEM_TEMPLATE: Final = dedent(
    _REGULATION_SYSTEM_HEAD + "      " + WHITELIST_SLOT + "\n" + _REGULATION_SYSTEM_TAIL
).replace(WHITELIST_SLOT + "\n", WHITELIST_SLOT, 1)
"""규제 system 의 판을 뗀 틀(밴드 IR4 — 7,659자). [8] 자리에 dedent 한 판 글(끝 줄바꿈 하나)을 끼우면
regulation_system(판) 과 바이트 같다 — 자리를 6칸 들여 머리·꼬리와 같이 dedent 하고, 판 글의 끝 줄바꿈 몫으로 자리 뒤
줄바꿈 하나를 뗀다."""


def regulation_system(whitelist_raw: str) -> str:
    """규제·정책 조사의 system(셀 17 R/413-728). whitelist_raw 는 [8] 블록 날 글(whitelists.py — 6칸 들여쓰기 그대로,
    끝 줄바꿈 하나)이고, 셀 17 현행 판을 끼우면 코랩 셀 17 의 system_prompt 와 바이트 같다. 시험용 꼴이다 — 흐름은
    판 칸 글(이미 dedent)을 틀에 render 로 끼운다(IR4)."""
    return render(REGULATION_SYSTEM_TEMPLATE, {WHITELIST_SLOT: dedent(whitelist_raw)})


REGULATION_USER_PREFIX: Final = dedent("""\
      아래 정의한 산업을 기반으로,
      토픽(설명 포함}에 관련된 규제·정책·가이드라인 최신 업데이트를 조사해 줘.

      리서치 조건:
      1) 지리적 범위: 내가 정의한 location
      2) 검색 언어: 내가 정의한 main_language를 우선으로 검색하되, 한국 외 다른 국가에 대해 검색할 때는 영어 및 해당 국가의 언어로 검색해 줘.
      3) 국가, 국제기구 등 공식 사이트에서 먼저 검색하되, 모니터링 언론 및 아카이빙 사이트에서도 검색을 수행.
      4) 각 업데이트별로 출처 URL 필수, 중복/유사 내용 통합.
      5) 각 지역(대한민국/EU/미국)별 최소 3건의 상이한 업데이트 제시(기관·법령·개정일 등으로 구분).
      6) 각 지역(대한민국/EU/미국)별로,
         - 최근 2년 내 업데이트가 있으면 최신 업데이트 기준으로 3건 내외를 선정하되,
         - 최근 2년 내 공식 업데이트가 없더라도,
           해당 토픽과 관련된 기존 규제·정책·가이드라인을
           "현재 시행 중인 대표 제도"로 최소 2건 이상 반드시 제시해야 한다.
      7) 이때는 status에 "시행 중(기존 제도, 최근 개정 없음)"과 같이 명시하고,
         summary에 "최근 2년 내 공식 업데이트는 없으나, 현재 시행 중인 제도"임을 밝혀야 한다.

      이번 질의는 **위 산업에 특화된 규제·정책·가이드라인**을 중점적으로 찾는 모드다.

      특히 아래 내용을 유의해 줘:
      - 기업 일반 ESG 규제라도, 해당 산업에 직·간접적 영향을 주는 경우에는 포함 가능하다.

      출력은 SYSTEM의 [10] JSON ONLY 규칙을 반드시 따른다.""")
"""규제·정책 조사의 user 접두(셀 17 SPECIFIC_USER_PREFIX, R/733-756). 「토픽(설명 포함}」 괄호 오타 그대로(W5)."""


REGULATION_USER_RAW: Final = """\
      [가변 입력]
      industry_definition:
      {산업 정의}

      geo_scope: {검색 지역}
      preferred_language: {검색 언어}

      topic_name: {토픽}
      topic_desc: {토픽 설명}"""
"""규제 user 가변의 날 글(셀 17 build_specific_user_prompt 의 f-문자열 몸, 자리 글자로 — IR4)."""


def regulation_user(
    topic_name: str,
    topic_desc: str,
    industry_text: str,
    location: str,
    main_language: str,
    *,
    texts: "PromptTexts | None" = None,
) -> str:
    """규제·정책 조사의 user 가변(셀 17 build_specific_user_prompt, R/758-768). 기간은 안 간다(W1)."""
    return render_raw(
        REGULATION_USER_RAW if texts is None else texts.regulation_input,
        {
            INDUSTRY_SLOT: industry_text,
            LOCATION_SLOT: location,
            LANGUAGE_SLOT: main_language,
            TOPIC_SLOT: topic_name,
            TOPIC_DESC_SLOT: topic_desc,
        },
    )


KEYWORDS_SYSTEM: Final = dedent("""\
  너는 ESG 컨설턴트로서 특정 산업의 **중대 토픽별 컨트로버시(논란/사건)를** 신뢰 가능한 출처로
  사실 검증해 구조화하기 위해 필요한 **검색 키워드 세트**를 설계하는 역할을 한다.

  각 토픽은 서로 다른 유형의 이슈를 다루므로, 토픽별로 구분된 키워드를 제시해야 한다.
  반드시 내가 요청한 JSON 형식으로만 응답하고, 추가 설명이나 마크다운, 자연어 문장은 포함하지 않는다.
  """)
"""컨트로버시 키워드의 system(셀 20, R/827-833). 끝 빈칸 줄은 dedent 가 줄바꿈 하나로 남긴다."""

KEYWORDS_USER_PREFIX: Final = dedent("""\
  산업의 중대 토픽 목록을 아래에 알려줄 거야.
  그러면, 토픽별로 내가 정의한 기간 동안 보도된 컨트로버시를 리서치할 때 사용할 검색 키워드를 만들어 줘.

  요구사항:
  1) 각 토픽마다 키워드를 최소 10개, 최대 15개 생성한다.
  2) 키워드는 내가 정의한 main_language를 중심으로 작성하되, 필요하면 영어 키워드도 일부 포함해도 된다.
  3) 아래 JSON 형식으로만 출력하고, 추가 설명·텍스트·마크다운은 절대 포함하지 않는다.

  출력 형식 예시는 다음과 같다 (예시이므로 실제 키워드는 다르게 작성할 것):
  {{
    "topics": [
      {{
        "topic": "기후변화 대응",
        "keywords": ["기후변화 리스크", "탄소배출 규제", "탄소중립 목표 미이행", "녹색금융 그린워싱", "..."]
      }},
      {{
        "topic": "소비자 권익 보호",
        "keywords": ["불완전판매", "금융소비자 보호법 위반", "고위험 파생상품 판매", "..."]
      }}
    ]
  }}
  위 형식을 그대로 따르되, topic 값에는 내가 입력한 토픽명을 그대로 사용해.""")
"""컨트로버시 키워드의 user 접두(셀 20 USER_PREFIX, R/835-857). f-문자열이 아니라 `{{`·`}}` 가 그대로 간다(W3)."""


KEYWORDS_USER_RAW: Final = """\
      [가변 입력]
      industry: {산업 정의}
      date_range: {검색 기간}
      main_language: {검색 언어}
      topics: {토픽 목록}
      """
"""키워드 user 가변의 날 글(셀 20 build_user_prompt 의 f-문자열 몸, 자리 글자로 — IR4)."""


def keywords_user(
    industry: list[dict[str, str]],
    date_range: str,
    main_language: str,
    topics: list[dict[str, str]],
    *,
    texts: "PromptTexts | None" = None,
) -> str:
    """컨트로버시 키워드의 user 가변(셀 20 build_user_prompt, R/859-866). industry·topics 는 파이썬 repr 로 실린다(W2) —
    코랩 키 차례의 dict 목록을 받는다(contracts/wire.py 가 짓는다). 코랩은 topics 를 전역에서 읽었다 — 여기는 인자.
    date_range 는 이 호출에만 간다."""
    return render_raw(
        KEYWORDS_USER_RAW if texts is None else texts.keywords_input,
        {
            INDUSTRY_SLOT: str(industry),
            DATE_RANGE_SLOT: date_range,
            LANGUAGE_SLOT: main_language,
            TOPICS_SLOT: str(topics),
        },
    )


CONTROVERSY_SYSTEM: Final = dedent("""\
  너는 ESG 컨설턴트로서 특정 산업의 기업들이 직면한 **중대 토픽별 컨트로버시(논란/사건/리스크)**를
  신뢰 가능한 출처로 사실 검증해 구조화하는 역할을 한다.

  산업의 정의와 주요 사업 영역, 각 중대 토픽과 관련한 산업 내 컨트로버시 유형(예: 내부통제 위반, 환경 리스크, 금융소비자 보호 위반, 부패·뇌물 등)을 인지하고 있다.
  사실 검증과 출처 명시를 엄격히 준수한다. 동일 사건의 중복 보도는 묶어서 하나의 사건으로 처리한다.

  <신뢰할 수 있는 출처>
  - 사용 가능:
    - 아래에 정의한 지리적 범위의 해당 정부·규제기관·감독당국 (예: 환경부, 산업안전보건청, 고용노동부 등)
    - 국제기구 (예: UN, OECD, IEA 등)
    - 공신력 있는 언론 (예: Reuters, FT, WSJ, NYT, The Guardian, 주요 경제지 등)
    - 공신력 있는 연구·시민단체나 전문기관의 공식 보고서·기사 (예: ClientEarth, InfluenceMap 등)
  - 사용 금지:
    - 위키피디아 / Wikipedia / wiki 가 들어가는 모든 사이트 (예: en.wikipedia.org 등)
    - 개인 블로그, 카페, 익명 커뮤니티, 광고·PR 성격의 보도자료
  - 반드시 지켜야 할 규칙:
    - 출처 URL에 'wikipedia' 또는 'wiki' 문자열이 포함되면 절대 사용하지 않는다.
    - 사건 설명·요약·출처 부분 어디에도 'Wikipedia', '위키피디아'라는 단어를 적지 않는다.
    - Wikipedia를 참고하여 내용을 재작성하는 것도 금지된다.
    - 만약 검색 결과가 거의 Wikipedia 위주라면, 해당 사건은 사용하지 말고 다른 신뢰 가능한 출처를 찾는다.
  </신뢰할 수 있는 출처>

  절대 규칙:
  - 임의로 사건을 만들어 내지 말고, 신뢰 가능한 출처가 있는 경우에만 사건으로 인정한다.
  - 서로 다른 사건만 카운트하며, 동일 사건의 중복·후속 보도는 하나로 통합한다.
  - 동일 사건에 대해 여러 보도가 있을 경우, 가장 공신력 있는 언론·기관의 보도를 우선 사용한다.
  - 한국의 컨트로버시 이슈를 최소 2건 이상 포함한다.

=====================================================================
[OUTPUT] 출력 형식 강제 — JSON ONLY
=====================================================================

- 출력은 반드시 JSON 객체 1개만 반환한다. (설명/마크다운/코드블록 ``` 금지)
- JSON 외 텍스트가 단 1글자라도 포함되면 실패로 간주한다.
- key 이름은 아래 스키마와 정확히 일치해야 한다. (snake_case 유지)

[OUTPUT JSON SCHEMA]
{
  "topic_name": string,
  "results": {
    "items": [ControversyItem, ...],
    "found_count": integer,
    "reason": string | null
  },
  "self_check": {
    "banned_domain_used": boolean,
    "duplicate_merged": boolean,
    "korea_included": boolean,
    "date_range_respected": boolean,
    "hallucination_removed": boolean,
    "notes": string
  }
}

[ControversyItem]
{
  "title": string,
  "date": string | null,         // 가능한 YYYY-MM-DD, 불명확하면 null
  "summary": string,             // 2~3문장 이내 권장
  "severity": "낮음" | "중간" | "높음",
  "status": string,              // 진행중/종결/조사중/소송중 등
  "url": string                  // 공식/공신력 있는 출처 URL 1개
}

[작성 규칙]
1) 각 사건이 어떤 토픽('정의한 topic_name 그대로 사용')에 속하는지 명확하게 드러나야 한다.
2) items는 서로 다른 사건 최소 5건, 최대 7건을 목표로 한다. 동일 사건의 다중 보도는 1건으로 통합하고, 사건 단위로 정리해.
3) 5건을 채우지 못하면:
   - found_count는 실제 사건 수
   - reason은 한국어 1~2문장으로 부족 사유 작성
4) 지리적 범위: 한국에서 발생/보도된 사건이 최소 1건 이상 포함되어야 한다.
   - 불가하면 self_check.korea_included=false로 표기하고 notes에 사유를 적는다.
5) 검색 언어: 내가 정의한 main_language를 우선적으로 사용하되, 영어로 검색 결과를 보충한다.
6) 금지 도메인(wikipedia/wiki 포함)은 절대 사용하지 않는다.
   - 발견 시 해당 사건은 items에서 제외하고 self_check.banned_domain_used=true로 표기한다.
7) 동일 사건의 중복/후속 보도는 1건으로 통합하고 self_check.duplicate_merged에 반영한다.
8) 날짜 범위 규칙을 지키지 못한 사건은 제외하고 date_range_respected=false로 표시한다.
9) 절대로 JSON 객체를 두 번 출력하지 마라. (예: {..}{..} 금지)
10) self_check 이후에도 어떤 문자도 추가하지 마라. (공백/줄바꿈 포함 금지)
11) 위 스키마는 설명용이며 그대로 재출력하지 마라.
12) url 필드는 반드시 실제 URL이어야 한다. (반드시 https:// 또는 http:// 로 시작). turn0news14, turn0search2 같은 내부 참조 ID는 절대 출력하지 마라.""")
"""컨트로버시 조사의 system(셀 22, R/966-1047). 최소 들여쓰기 0 이라 앞 단락의 2칸이 남는다(W4)."""

CONTROVERSY_USER_PREFIX: Final = dedent("""\
내가 아래에 정의한 산업의 토픽(설명 포함) 관련 중대 토픽에 대해, 정의한 날짜 범위 안에 발생 또는 보도된 컨트로버시를 조사해 줘.

리서치를 더 잘 하기 위해 **아래에 정의한 키워드를 우선적**으로 사용해 줘.

출력은 SYSTEM의 [OUTPUT] JSON ONLY 스키마를 반드시 따른다.
""")
"""컨트로버시 조사의 user 접두(셀 22 SPECIFIC_USER_PREFIX, R/1051-1057)."""

CONTROVERSY_USER_RAW: Final = """\
      [가변 입력]
      industry_definition:
      {산업 정의}

      geo_scope: {검색 지역}
      preferred_language: {검색 언어}

      keyword: {키워드 뽑기의 답}
      topic_name: {토픽}
      topic_desc: {토픽 설명}
      """
"""컨트로버시 user 가변의 날 글(셀 22 build_specific_user_prompt 의 f-문자열 몸, 자리 글자로 — IR4)."""


def controversy_user(
    topic_name: str,
    topic_desc: str,
    industry: list[dict[str, str]],
    location: str,
    main_language: str,
    keyword_str: str,
    *,
    texts: "PromptTexts | None" = None,
) -> str:
    """컨트로버시 조사의 user 가변(셀 22 build_specific_user_prompt, R/1060-1072). industry 는 파이썬 repr(W2), 기간은
    안 간다(W1). keyword_str 은 parsing.keyword_str 의 글."""
    return render_raw(
        CONTROVERSY_USER_RAW if texts is None else texts.controversy_input,
        {
            INDUSTRY_SLOT: str(industry),
            LOCATION_SLOT: location,
            LANGUAGE_SLOT: main_language,
            KEYWORDS_SLOT: keyword_str,
            TOPIC_SLOT: topic_name,
            TOPIC_DESC_SLOT: topic_desc,
        },
    )
