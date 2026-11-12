// 새 평가 폼의 처음 꼴과 [평가 시작] 검사(밴드 IRW2 ② — 부록 A4·A6-⑪). 화면은 넣은 값을 그대로 쥐고, 누르면 이 검사를 받아
//   칸마다 알리고 첫 오류 칸으로 옮긴다(차례 = 화면 차례: 기업명 → 산업 → 가치사슬 → 토픽 → 검색 지역 → 시작일 → 전체 크기).
// 「오늘」은 서울 날짜(shared/lib/time.ts toKstIso). 서버는 시작일 = 오늘도 받지만(★A — start == end) 판은 「앞선 날」만 받는다.
import { toKstIso } from '../../../shared/lib/time.ts';
import {
  STANDARDS,
  buildInput,
  buildOptions,
  filledSubtopics,
  optionsTooLarge,
} from './input.ts';
import type { RunDraft, Standard, TopicDraft } from './input.ts';
import { stagelessRows } from './valueChain.ts';
import { MAIN_LANGUAGE, USER_LOCATION } from './wire.ts';

/** 처음 시작일(코랩 셀 11 — 부록 A6-⑪). */
export const DEFAULT_START_DATE = '2024-01-01';

/** 빈 토픽 카드 하나(서브토픽 줄 하나). key 둘은 화면이 준다. */
export const blankTopic = (key: number, subKey: number): TopicDraft => ({
  key,
  topic: '',
  description: '',
  subtopics: [{ key: subKey, name: '', description: '' }],
});

/** 처음 꼴(A6-⑪): 칸 빔 · 토픽 카드 하나 · 검색 지역(화면 글 — 부르는 쪽이 준다) · KR · 한국어 · 2024-01-01 · 비금융.
 *  「최신 이슈 반영」 토글은 IRW15 ③ 에서 화면에서 뺐다 — 폼이 쥐지 않고 buildInput 이 늘 false 를 싣는다. */
export function initialDraft(geoScope: string, topic: TopicDraft): RunDraft {
  return {
    company: '',
    industries: {
      SASB: { name: '', description: '' },
      GICS: { name: '', description: '' },
      KSIC: { name: '', description: '' },
    },
    valueChain: [],
    topics: [topic],
    geoScope,
    userLocation: USER_LOCATION,
    mainLanguage: MAIN_LANGUAGE,
    startDate: DEFAULT_START_DATE,
    sector: 'non_financial',
  };
}

export type DraftProblem =
  | { field: 'company' }
  /** required = SASB 이름 빔 · description_only = GICS·KSIC 설명만 있음(A6-⑩). */
  | {
      field: 'industry';
      standard: Standard;
      code: 'required' | 'description_only';
    }
  /** 밸류체인이 빈 행(1부터). */
  | { field: 'stage'; rows: number[] }
  | { field: 'topics' }
  /** index = 토픽 카드 차례. */
  | { field: 'topic'; index: number; code: 'required' | 'duplicate' }
  /** 토픽에 서브토픽 0개(두 칸 다 빈 줄은 뺀 뒤). */
  | { field: 'subtopics'; index: number }
  /** 설명만 찬 서브토픽 줄(sub = 그 토픽의 줄 차례). */
  | { field: 'subtopic'; index: number; sub: number }
  | { field: 'geoScope' }
  | { field: 'startDate'; code: 'required' | 'not_before_today' }
  /** options 바이트가 서버 상한을 넘음(A6-⑦). */
  | { field: 'size' };

const blank = (text: string) => text.trim() === '';
const DAY = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/;

/** 달력에 있는 날인가(YYYY-MM-DD). */
export function isCalendarDay(text: string): boolean {
  const match = DAY.exec(text);
  if (match === null) return false;
  const [, y, m, d] = match.map(Number) as [number, number, number, number];
  const at = new Date(Date.UTC(y, m - 1, d));
  return (
    at.getUTCFullYear() === y &&
    at.getUTCMonth() === m - 1 &&
    at.getUTCDate() === d
  );
}

/** 서울 날짜 「YYYY-MM-DD」. */
export const seoulDay = (now: Date) => toKstIso(now).slice(0, 10);

/** [평가 시작] 검사 — 화면 차례로. 빈 목록이면 보낼 수 있다. */
export function draftProblems(draft: RunDraft, now: Date): DraftProblem[] {
  const problems: DraftProblem[] = [];
  if (blank(draft.company)) problems.push({ field: 'company' });
  for (const standard of STANDARDS) {
    const { name, description } = draft.industries[standard];
    if (!blank(name)) continue;
    if (standard === 'SASB')
      problems.push({ field: 'industry', standard, code: 'required' });
    else if (!blank(description))
      problems.push({ field: 'industry', standard, code: 'description_only' });
  }
  const stageless = stagelessRows(draft.valueChain);
  if (stageless.length > 0) problems.push({ field: 'stage', rows: stageless });
  if (draft.topics.length === 0) problems.push({ field: 'topics' });
  const seen = new Set<string>();
  draft.topics.forEach((topic, index) => {
    const name = topic.topic.trim();
    if (name === '') problems.push({ field: 'topic', index, code: 'required' });
    else if (seen.has(name))
      problems.push({ field: 'topic', index, code: 'duplicate' });
    seen.add(name);
    if (filledSubtopics(topic).length === 0)
      problems.push({ field: 'subtopics', index });
    topic.subtopics.forEach((sub, subIndex) => {
      if (blank(sub.name) && !blank(sub.description))
        problems.push({ field: 'subtopic', index, sub: subIndex });
    });
  });
  if (blank(draft.geoScope)) problems.push({ field: 'geoScope' });
  const start = draft.startDate.trim();
  if (!isCalendarDay(start))
    problems.push({ field: 'startDate', code: 'required' });
  else if (start >= seoulDay(now))
    problems.push({ field: 'startDate', code: 'not_before_today' });
  if (optionsTooLarge(buildOptions(buildInput(draft))))
    problems.push({ field: 'size' });
  return problems;
}
