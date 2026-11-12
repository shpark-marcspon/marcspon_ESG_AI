// 데이터 검증 시험 도우미(밴드 DV2a ①). 어댑터·훅·화면·경로·e2e 시험이 같이 쓴다(공개 표면이 아니다 — 시험만 직접 가져온다).
// 값은 전부 지어낸 것이다(「가상건설」 꼴 — 실재 기업명·실제 보고서 문장 0). 입력 JSON 은 여기서 짓는다(저장소에 .json 0).
// 결과는 dataverify.result@2 의 서버 꼴(JSON) 그대로다 — 백엔드 예시(tests/data/examples/result-sample.json)와 같은 갈래·수
//   (검사 줄 5 · 검사 5 · 어긋남 1 · 계산 못 함 4 · 리스크 2)로 지어냈다. 예시 파일은 계약 시험이 읽기만 한다.

type Json = Record<string, unknown>;

/** EDK 한 항목(지어낸 값). */
export function edkItem(extra: Json = {}): Json {
  return {
    ID: 'E-001',
    테마: '환경',
    항목: '기후변화',
    대분류: '온실가스 배출량',
    중분류: '직접 배출량',
    소분류: 'Scope 1',
    '입력 방식': '직접 입력',
    단위: 'tCO2eq',
    values: { '2022': '1,200', '2023': 1300, '2024': null },
    핵심데이터: 'Y',
    메모: '',
    ...extra,
  };
}

/** data(테마 셋 · 항목 넷 — 환경 둘(핵심 하나), 사회 하나, 지배구조 하나). */
export function edkData(): Json {
  return {
    환경: [
      edkItem(),
      edkItem({
        ID: 2,
        소분류: 'Scope 2',
        values: { '2023': 300, '2024': 310.5 },
        핵심데이터: 'N',
        담당자: '가상 담당',
      }),
    ],
    사회: [edkItem({ ID: 'S-1', 테마: '사회' })],
    지배구조: [edkItem({ ID: 'G-1', 테마: '지배구조' })],
  };
}

/** 지어낸 기업 정보. */
export const FAKE_COMPANY = {
  name: '가상건설',
  sasbIndustry: 'Engineering & Construction Services',
  materialTopics: ['기후변화 대응', '안전보건'],
  reportingYear: '2025',
} as const;

/** 지어낸 입력(dataverify.input@1). */
export function fakeInput(data: Json = edkData()): Json {
  return {
    schemaVersion: 'dataverify.input@1',
    company: {
      ...FAKE_COMPANY,
      materialTopics: [...FAKE_COMPANY.materialTopics],
    },
    data,
  };
}

const quad = (...names: string[]) => names;
const S1 = quad('온실가스 배출량', '직접 배출량', 'Scope 1', 'tCO2eq');
const S2 = quad('온실가스 배출량', '간접 배출량', 'Scope 2', 'tCO2eq');
const S12 = quad('온실가스 배출량', '총 배출량', 'Scope 1+2', 'tCO2eq');
const RE = quad('에너지', '재생에너지', '재생에너지 사용량', 'TJ');
const TE = quad('에너지', '총 에너지', '총 에너지 사용량', 'TJ');
const RR = quad('에너지', '재생에너지', '재생에너지 비율', '%');

/** 검사 기록 여덟(value·search 둘씩 섞임 — 표 줄은 check 셋·error 둘 = 다섯). */
export function fakeChecks(): Json[] {
  return [
    {
      seq: 1,
      tool: 'search_items',
      kind: 'search',
      filter: { 대분류: '온실가스 배출량' },
      total: 6,
      limit: 200,
      offset: 0,
      returned: 6,
    },
    {
      seq: 2,
      tool: 'value_of_by_name',
      kind: 'value',
      item: S1,
      year: '2024',
      value: '1300.0',
      na: false,
    },
    {
      seq: 3,
      tool: 'sum_check_by_name',
      kind: 'check',
      rule: 'sum',
      items: { byName: { total: S12, a: S1, b: S2 }, raw: null },
      tolerance: '0.0',
      years: [
        {
          year: '2023',
          ok: true,
          status: 'OK',
          diff: '0.0',
          note: null,
          explanation:
            'Sum(1200.0 + 300.0) - Target(1500.0) = 0.000000 → within tolerance (0.0).',
        },
        {
          year: '2024',
          ok: false,
          status: 'FAIL',
          diff: '5.0',
          note: null,
          explanation:
            'Sum(1300.0 + 310.0) - Target(1605.0) = 5.000000 → exceeds tolerance (0.0).',
        },
      ],
    },
    {
      seq: 4,
      tool: 'sum_n_check',
      kind: 'check',
      rule: 'sum_n',
      items: { byName: null, raw: { addends: [1200.5, 'N/A'], target: 1500 } },
      tolerance: '0.0',
      years: [
        {
          year: null,
          ok: false,
          status: 'FAIL',
          diff: null,
          note: 'non-numeric',
          explanation: 'Input values are not numeric.',
        },
      ],
    },
    {
      seq: 5,
      tool: 'value_of_by_name',
      kind: 'value',
      item: S2,
      year: '2022',
      value: null,
      na: true,
    },
    {
      seq: 6,
      tool: 'ratio_check_by_name',
      kind: 'check',
      rule: 'ratio',
      items: {
        byName: { numerator: RE, denominator: TE, expected: RR },
        raw: null,
      },
      tolerance: '0.0',
      years: [
        {
          year: '2024',
          ok: false,
          status: 'FAIL',
          diff: null,
          note: 'division by zero',
          explanation: 'Cannot divide by zero.',
        },
      ],
    },
    {
      seq: 7,
      tool: 'sum_check_by_name',
      kind: 'error',
      message: '지어낸 도구 오류',
      args: { total: S12, a: S1, b: S2 },
    },
    {
      seq: 8,
      tool: 'value_of',
      kind: 'error',
      message: '지어낸 모르는 도구',
      args: { name: '총 배출량' },
    },
  ];
}

const FORMULAS = [
  '총 배출량(Scope 1+2) = 직접 배출량(Scope 1) + 간접 배출량(Scope 2)',
  '재생에너지 비율 = 재생에너지 사용량 / 총 에너지 사용량',
];

/** 검토 글(마크다운 원문 — 화면은 원문 그대로). */
export const FAKE_REVIEW_REPORT =
  '## 1. 총 배출량 합계 검증\n\n연도 | 합계(입력) | 계산값 | 차이\n2024 | 1605.0 | 1610.0 | 5.0';
/** 인사이트 원문(표로 못 나눴을 때 그대로 보인다). */
export const FAKE_INSIGHT_REPORT =
  '| 영역 | 지표 | 관찰 | 리스크 | 해석 |\n|---|---|---|---|---|\n| 환경 | Scope 2 | 지어낸 관찰 | 지어낸 리스크 | 지어낸 해석 |';

const failure = (kind: string) => ({
  kind,
  budgetSource: kind === 'budget_exceeded' ? 'loop' : null,
  message: `지어낸-${kind}`,
});

export const planDone = (partial = false): Json => ({
  status: 'done',
  partial,
  formulas: [...FORMULAS],
  raw: JSON.stringify(FORMULAS),
  failure: null,
});
export const planFailed = (kind = 'unparsable'): Json => ({
  status: 'failed',
  partial: null,
  formulas: [],
  raw: kind === 'unparsable' ? '지어낸 원문' : null,
  failure: failure(kind),
});
export const NOT_RUN_PLAN: Json = {
  status: 'not_run',
  partial: null,
  formulas: [],
  raw: null,
  failure: null,
};
export const reviewDone = (partial = false, checks = fakeChecks()): Json => ({
  status: 'done',
  partial,
  report: FAKE_REVIEW_REPORT,
  checks,
  failure: null,
});
export const reviewFailed = (
  kind = 'provider_error',
  checks = fakeChecks().slice(0, 3),
): Json => ({
  status: 'failed',
  partial: null,
  report: null,
  checks,
  failure: failure(kind),
});
export const NOT_RUN_REVIEW: Json = {
  status: 'not_run',
  partial: null,
  report: null,
  checks: [],
  failure: null,
};
export const insightDone = (extra: Json = {}): Json => ({
  status: 'done',
  partial: false,
  report: FAKE_INSIGHT_REPORT,
  rows: [
    {
      area: '환경',
      indicator: 'Scope 2',
      observation: '지어낸 관찰 하나',
      risk: '지어낸 리스크 하나',
      interpretation: '지어낸 해석 하나',
    },
    {
      area: '환경',
      indicator: 'Scope 1',
      observation: '지어낸 관찰 둘',
      risk: '지어낸 리스크 둘',
      interpretation: '지어낸 해석 둘',
    },
  ],
  rowsParsed: 'parsed',
  sources: [{ title: '가상 기준서', url: 'https://example.org/standard' }],
  failure: null,
  ...extra,
});
export const insightFailed = (
  kind = 'provider_error',
  partialText: string | null = null,
): Json => ({
  status: 'failed',
  partial: null,
  report: null,
  rows: [],
  rowsParsed: 'none',
  sources: [],
  failure: failure(kind),
  partialText,
});
export const NOT_RUN_INSIGHT: Json = {
  status: 'not_run',
  partial: null,
  report: null,
  rows: [],
  rowsParsed: 'none',
  sources: [],
  failure: null,
};

/** 결과(dataverify.result@2 서버 꼴). 기본은 세 단계 완료(검토 partial — 판 DV-04). */
export function fakeResult(extra: Json = {}): Json {
  return {
    schemaVersion: 'dataverify.result@2',
    company: {
      ...FAKE_COMPANY,
      materialTopics: [...FAKE_COMPANY.materialTopics],
    },
    scope: {
      themes: ['환경'],
      itemCount: 12,
      keyItemCount: 4,
      years: ['2022', '2023', '2024'],
    },
    settings: {
      model: 'made-up-model',
      tolerance: '0.0',
      temperature: '0.1',
      maxSteps: { plan: 12, review: 6, insight: 12 },
      promptIds: {
        plan: 'dataverify/plan@1',
        review: 'dataverify/review@1',
        insight: 'dataverify/insight@1',
      },
    },
    plan: planDone(),
    review: reviewDone(true),
    insight: insightDone(),
    warnings: [],
    ...extra,
  };
}

/** 「환경」이 없는 입력의 결과(경고 no_target_theme · 세 단계 돌지 않음). */
export function noTargetResult(): Json {
  return fakeResult({
    scope: { themes: [], itemCount: 0, keyItemCount: 0, years: [] },
    settings: {
      model: null,
      tolerance: '0.0',
      temperature: null,
      maxSteps: { plan: null, review: null, insight: null },
      promptIds: { plan: null, review: null, insight: null },
    },
    plan: NOT_RUN_PLAN,
    review: NOT_RUN_REVIEW,
    insight: NOT_RUN_INSIGHT,
    warnings: [{ code: 'no_target_theme', message: '지어낸 경고' }],
  });
}
