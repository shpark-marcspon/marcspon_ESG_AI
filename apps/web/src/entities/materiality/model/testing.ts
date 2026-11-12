// 시험 도우미(밴드 IRW1 ①): 지어낸 materiality.input@1·result@2 의 서버 꼴(JSON). 값은 전부 지어낸 것이다(실재 기업명 0).
// 어댑터·훅·화면·경로 시험이 같이 쓴다(공개 표면이 아니다 — 시험만 직접 가져온다). 화면 꼴은 계약 거울(api/contract)로 바꿔 쓴다.
import type { RunDraft } from './input.ts';

type Json = Record<string, unknown>;

export const FAKE_COMPANY = '가상물산';

export function fakeInput(extra: Json = {}): Json {
  return {
    schemaVersion: 'materiality.input@1',
    company: { name: FAKE_COMPANY },
    industries: [
      { standard: 'SASB', industryName: '가상 산업', description: '가상 설명' },
    ],
    topics: [
      { topic: '가상토픽 A', description: '가상토픽 A 설명' },
      { topic: '가상토픽 B', description: '가상토픽 B 설명' },
    ],
    geoScope: '가상 범위',
    userLocation: 'KR',
    mainLanguage: '한국어',
    dateRange: '2025-01-01~오늘까지',
    sector: 'non_financial',
    latestEventMode: false,
    subtopicsByTopic: null,
    valueChain: null,
    ...extra,
  };
}

export const item = (
  title: string,
  url: string | null = `https://example.com/${encodeURIComponent(title)}`,
  summary: string | null = `${title} 요약`,
) => ({ title, summary, url });

export const ctx = (regulations: Json[] = [], controversies: Json[] = []) => ({
  regulations,
  controversies,
});

export const impactRow = (
  definition: string,
  type: string | null = '부정',
  context: Json = ctx(),
) => ({
  impactDefinition: definition,
  impactType: type,
  valueChainActivities: [],
  context,
});

export const financialRow = (
  definition: string,
  type: string | null = '리스크',
  riskType: string | null = '리스크-규제 및 법률',
  context: Json = ctx(),
) => ({
  impactDefinition: definition,
  impactType: type,
  riskType,
  valueChainActivities: [],
  context,
});

export const pathwayRow = (
  definition: string,
  type: string | null = '리스크',
  riskType: string | null = '리스크-규제 및 법률',
  context: Json = ctx(),
) => ({
  i: 1,
  impactDefinition: definition,
  impactDriver: `${definition} 요인`,
  businessImpact: `${definition} 비즈니스`,
  financialImpact: `${definition} 재무`,
  impactType: type,
  riskType,
  context,
});

export const done = (rows: Json[]) => ({ status: 'done', parsed: {}, rows });
export const failed = () => ({
  status: 'failed',
  raw: null,
  parseError: null,
  failure: { kind: 'provider_error', message: '지어낸 서버 글-실패' },
});
export const notRun = () => ({
  status: 'not_run',
  message: '지어낸 서버 글-돌리지 않음',
});

export function subtopic(name: string, extra: Json = {}): Json {
  return {
    name,
    description: `${name} 설명`,
    autofilled: false,
    impact: done([impactRow(`${name} 영향`)]),
    financial: done([financialRow(`${name} 재무`)]),
    pathway: done([pathwayRow(`${name} 경로`)]),
    ...extra,
  };
}

const regulationDone = () => ({
  status: 'done',
  parsed: {},
  items: [],
  selfCheck: null,
  topicNameMismatch: false,
});
const controversyDone = () => ({
  status: 'done',
  parsed: {},
  items: [],
  selfCheck: null,
  topicNameMismatch: false,
});

/** 1부 토픽 하나(규제·컨트로버시 갈래만 고른다). */
export function part1Topic(
  topic: string,
  regulation: 'done' | 'failed' | 'not_run' = 'done',
  controversy: 'done' | 'failed' | 'not_run' = 'done',
): Json {
  const of = (status: string, made: () => Json) =>
    status === 'done' ? made()
    : status === 'failed' ?
      {
        status: 'failed',
        raw: null,
        parseError: null,
        failure: { kind: 'unparsable', message: '지어낸 서버 글-못 읽음' },
      }
    : notRun();
  return {
    topic,
    description: `${topic} 설명`,
    keywordStr: null,
    regulation: of(regulation, regulationDone),
    controversy: of(controversy, controversyDone),
  };
}

/**
 * 지어낸 결과(서버 꼴). 기본: 토픽 둘(A: 서브토픽 가·나 · B: 다), 줄은 서브토픽마다 2-1 하나·2-2 하나, 경고 0.
 * part2Topics 로 2부 토픽을 갈아 끼운다(part1 은 그 토픽 이름들로).
 */
export function fakeResult(
  extra: Json = {},
  part2Topics: Json[] = [
    {
      topic: '가상토픽 A',
      description: '가상토픽 A 설명',
      subtopics: [subtopic('서브 가'), subtopic('서브 나')],
    },
    {
      topic: '가상토픽 B',
      description: '가상토픽 B 설명',
      subtopics: [subtopic('서브 다')],
    },
  ],
): Json {
  return {
    schemaVersion: 'materiality.result@2',
    company: { name: FAKE_COMPANY },
    scope: {
      topicCount: part2Topics.length,
      sector: 'non_financial',
      whitelist: 'cell73',
      dateRange: '2025-01-01~오늘까지',
      geoScope: '가상 범위',
      userLocation: 'KR',
      mainLanguage: '한국어',
      latestEventMode: false,
    },
    settings: {
      model: 'model-x',
      temperature: '0.1',
      searchContextSize: 'low',
      promptIds: { regulation: null, keywords: null, controversy: null },
      part2: {
        model: 'model-y',
        maxOutputTokens: 100,
        latestEventMode: false,
        promptIds: { impact: null, financial: null, pathway: null },
      },
    },
    part1: {
      keywords: { status: 'not_run', message: '지어낸 서버 글-키워드' },
      topics: part2Topics.map((t) => part1Topic(t.topic as string)),
    },
    part2: { status: 'done', input: { source: 'result' }, topics: part2Topics },
    warnings: [],
    ...extra,
  };
}

/** 경고 한 줄(서버 꼴 — message 는 지어낸 서버 글). */
export const warning = (
  code: string,
  topic: string | null = null,
  phase: string | null = null,
) => ({
  code,
  message: `지어낸 서버 글-${code}`,
  topic,
  phase,
  subtopic: null,
});

/** 다 채운 새 평가 폼(밴드 IRW2 — model 시험 도우미, 값은 지어낸 것). */
export function fakeDraft(extra: Partial<RunDraft> = {}): RunDraft {
  return {
    company: ' 가상물산 ',
    industries: {
      SASB: { name: '가상 산업', description: '가상 산업 설명' },
      GICS: { name: '', description: '' },
      KSIC: { name: '가상 분류', description: '' },
    },
    valueChain: [],
    topics: [
      {
        key: 1,
        topic: '가상토픽 A',
        description: '가상토픽 A 설명',
        subtopics: [
          { key: 2, name: '가상 서브 1', description: '서브 1 설명' },
          { key: 3, name: '', description: '' },
        ],
      },
      {
        key: 4,
        topic: '가상토픽 B',
        description: '',
        subtopics: [{ key: 5, name: '가상 서브 2', description: '' }],
      },
    ],
    geoScope: '가상 범위',
    userLocation: 'KR',
    mainLanguage: '한국어',
    startDate: '2024-01-01',
    sector: 'non_financial',
    ...extra,
  };
}
