// 시험 도우미(밴드 TRW0b — 이 슬라이스 helperIsTest, 화면 시험만 쓴다). 지어낸 자료 하나: 서버 노트 「한 문서의 시각」.
//   64쪽 문서 하나를 파트 셋(CEO 1~3 · 스토리 4~41 · 일반 42~64)으로 [번역 시작] 한 번 — 11:50 셋째 대기, 11:55 하나 끝남,
//   스토리 회차 1 이 일부 쪽 실패(12:00) → [이 파트만 다시] 회차 2(14:10 시작 · 14:22 끝남).
// 실재 기업명·실제 보고서 문장 없음. 시각은 보이는 글(어댑터가 짓는 꼴)로 둔다.
import type { PartKey } from './parts.ts';
import type { RejectionKey, TabState } from './status.ts';

/** 파트 하나의 지은 자리(화면 꼴 — 부품 props 의 재료). */
export interface SamplePart {
  part: PartKey;
  range: { from: number; to: number };
  /** 「4~41」. */
  rangeText: string;
  round: number;
  started: string;
  finished?: string;
  state: TabState;
  reason?: RejectionKey;
  pages?: { done: number; total: number };
}

export const SAMPLE_FILE = 'sample_report_ko_extract.docx';
export const SAMPLE_PAGE_COUNT = 64;

const ceo = (state: TabState, extra: Partial<SamplePart> = {}): SamplePart => ({
  part: 'ceo',
  range: { from: 1, to: 3 },
  rangeText: '1~3',
  round: 1,
  started: '11:48',
  state,
  ...extra,
});
const story = (
  state: TabState,
  extra: Partial<SamplePart> = {},
): SamplePart => ({
  part: 'story',
  range: { from: 4, to: 41 },
  rangeText: '4~41',
  round: 1,
  started: '11:48',
  state,
  ...extra,
});
const general = (
  state: TabState,
  extra: Partial<SamplePart> = {},
): SamplePart => ({
  part: 'general',
  range: { from: 42, to: 64 },
  rangeText: '42~64',
  round: 1,
  started: '11:53',
  state,
  ...extra,
});

/** 11:50 — 둘이 돌고 셋째는 차례를 기다림. */
export const AT_1150: readonly SamplePart[] = [
  ceo('running', { pages: { done: 2, total: 3 } }),
  story('running', { pages: { done: 6, total: 38 } }),
  general('queued'),
];

/** 11:55 — CEO 끝남, 스토리 번역 20/38쪽, 일반 준비 중. */
export const AT_1155: readonly SamplePart[] = [
  ceo('done', { finished: '11:53' }),
  story('running', { pages: { done: 20, total: 38 } }),
  general('running'),
];

/** 12:05~14:10 — 스토리 회차 1 이 일부 쪽 실패, 나머지 끝남. */
export const AT_1205: readonly SamplePart[] = [
  ceo('done', { finished: '11:53' }),
  story('failed_partial', { finished: '12:00' }),
  general('done', { finished: '12:05' }),
];

/** 14:22 — 스토리 회차 2 까지 끝나 셋 다 완료. */
export const AT_1422: readonly SamplePart[] = [
  ceo('done', { finished: '11:53' }),
  story('done', { round: 2, started: '14:10', finished: '14:22' }),
  general('done', { finished: '12:05' }),
];

/** 지은 검수 이슈(스토리 회차 2 — High 1 · Mid 4 · Low 6, 11건). 영문은 지은 문장. */
export const SAMPLE_ISSUES = [
  {
    page: 12,
    type: 'number_unit',
    severity: 'high',
    span: 'a 12% cut',
    suggestion: 'a 21% cut',
    reason: '원문 숫자와 다릅니다.',
  },
  {
    page: 5,
    type: 'unnatural',
    severity: 'mid',
    span: 'metric managing',
    suggestion: 'tracking metrics',
    reason: '명사를 늘어놓았습니다.',
  },
  {
    page: 18,
    type: 'term_inconsistency',
    severity: 'mid',
    span: 'partner firms',
    suggestion: 'suppliers',
    reason: '같은 낱말을 두 가지로 옮겼습니다.',
  },
  {
    page: 27,
    type: 'omission',
    severity: 'mid',
    span: 'fell by 15%.',
    suggestion: 'fell by 15% year on year.',
    reason: '비교 기준이 빠졌습니다.',
  },
  {
    page: 30,
    type: 'glossary_violation',
    severity: 'mid',
    span: 'safety board',
    suggestion: 'Safety Committee',
    reason: '용어집 영문과 다릅니다.',
  },
  {
    page: 33,
    type: 'grammar',
    severity: 'low',
    span: 'staff participates',
    suggestion: 'staff participate',
    reason: '수가 맞지 않습니다.',
  },
  {
    page: 34,
    type: 'grammar',
    severity: 'low',
    span: 'a events',
    suggestion: 'an event',
    reason: '관사가 맞지 않습니다.',
  },
  {
    page: 35,
    type: 'unnatural',
    severity: 'low',
    span: 'very much large',
    suggestion: 'very large',
    reason: '어색합니다.',
  },
  {
    page: 38,
    type: 'table_content',
    severity: 'low',
    span: 'Waste (t)',
    suggestion: 'Waste (%)',
    reason: '표 단위가 다릅니다.',
  },
  {
    page: 39,
    type: 'figure_caption',
    severity: 'low',
    span: 'Figure 1 Trend',
    suggestion: 'Figure 1. Trend',
    reason: '그림 설명 꼴이 다릅니다.',
  },
  {
    page: 40,
    type: 'structure_changed',
    severity: 'low',
    span: '[PAGE 40] heading',
    suggestion: '[PAGE 40]',
    reason: '구조 표시가 바뀌었습니다.',
  },
] as const;

/** 지은 용어집 미반영(스토리). */
export const SAMPLE_MISSES = [
  {
    page: 9,
    ko: '안전보건 관리',
    en: 'Health and Safety Management',
    count: 2,
  },
  { page: 36, ko: '협력사', en: 'Suppliers', count: 1 },
] as const;

/** 지은 확인할 쪽(스토리 회차 1). */
export const SAMPLE_PAGES_TO_CHECK = [
  {
    pages: '27',
    translate: '실패',
    review: '검수함',
    reason: 'AI 호출이 실패했어요.',
  },
  {
    pages: '30',
    translate: '완료',
    review: '30페이지에서 멈춤',
    reason: '검수 AI 호출이 실패했어요',
  },
  {
    pages: '31~41',
    translate: '완료',
    review: '돌리지 않음',
    reason: '앞 페이지에서 검수가 멈췄어요',
  },
] as const;
