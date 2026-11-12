// 목 결과·검토 짓기(밴드 FW2 ①). 값은 모두 지어낸 것이다 — 계약 예시 파일을 가져오지 않는다(mock 은 자기 domain·headless 만).
// 예외 하나: 실호출 씨앗(run-106)의 결과는 짓지 않고 fixtures/report-b.result.json(실호출 1회를 가린 판, sid:MARC-ENT-190, sid:MARC-ISSUE-129)을 mockSeeds.ts 가 읽는다.
// 꼴이 계약과 맞는지는 api/mock/mockResults.test.ts 가 거울(api/index.ts)로 지킨다.
// 서버 셈을 흉내 낸다: counts 는 items 를 다시 센 것, pages 는 파트의 합집합, wordCounts.total 은 쪽마다의 수를 더한 것
// (많은 차례, 같으면 처음 나온 차례), 추가 단어는 기본 목록과 키가 겹치지 않는 것만 빈도에 더한다(서버 frequency_extras).
import {
  LEVELS,
  RESULT_SHAPE,
  SERVER_PART_NAMES,
  termKey,
} from '../../model/index.ts';
import type {
  Level,
  LevelCounts,
  PageTermCounts,
  ResultItem,
  ResultPosition,
  ScanResult,
  TermCount,
} from '../../model/index.ts';

/** 서버 E0 의 파트 이름(결과의 parts[].name — 짝은 model/parts.ts 한 곳). 이 차례다. */
export const MOCK_PART_NAMES = SERVER_PART_NAMES;

export interface MockItemInput {
  page: number;
  level: Level;
  sentence: string;
  /** High·Mid 의 위험 유형(Low 는 늘 「선언적 문장」). */
  riskTags?: readonly string[];
  confirmed?: readonly string[];
  missing?: readonly string[];
  evidencePages?: readonly number[];
  position?: ResultPosition | null;
  example?: string | null;
}

export interface MockResultInput {
  fileName: string;
  pageCount: number;
  /** 파트 이름 → 쪽(서버 차례: CEO 메시지 · 회사소개 · 기후/환경 토픽). */
  parts: readonly { name: string; pages: readonly number[] }[];
  items: readonly MockItemInput[];
  extraTerms?: readonly string[];
  defaultTerms: readonly string[];
  /** 쪽 → 낱말 → 수. 기본 목록 밖·추가 단어 밖 낱말과, 기본 목록과 키가 겹친 추가 단어는 버린다. */
  wordPages: Readonly<Record<number, Readonly<Record<string, number>>>>;
  failedPages?: readonly number[];
}

const zero = (): LevelCounts => ({ High: 0, Mid: 0, Low: 0 });

/** 지어낸 sha256(소문자 16진 64자): 이름 글자로 정해진다. */
export function fakeSha(name: string): string {
  let hex = '';
  for (let i = 0; hex.length < 64; i++) {
    const code = name.charCodeAt(i % Math.max(name.length, 1)) || 0;
    hex += ((code * 31 + i * 7) % 256).toString(16).padStart(2, '0');
  }
  return hex.slice(0, 64);
}

function toItem(
  input: MockItemInput,
  parts: MockResultInput['parts'],
): ResultItem {
  const partNames = parts
    .filter((part) => part.pages.includes(input.page))
    .map((part) => part.name);
  const low = input.level === 'Low';
  return {
    page: input.page,
    parts: partNames,
    sentence: input.sentence,
    level: input.level,
    riskTags: low ? ['선언적 문장'] : (input.riskTags ?? ['근거 부족']),
    confirmedInEvidence: low ? [] : (input.confirmed ?? []),
    missingFields: low ? [] : (input.missing ?? ['기준연도']),
    reasonBullets:
      low ?
        ['지어낸 사유: 수치 없이 다짐만 하는 문장이에요.']
      : ['지어낸 사유: 근거 조각에 수치가 보이지 않아요.'],
    fixParagraph:
      low ?
        '다짐 대신 지금까지의 실적 수치와 기준을 함께 적어 주세요(지어낸 수정 방향).'
      : '주장에 기준연도와 수치, 측정 방법을 함께 밝혀 읽는 사람이 확인할 수 있게 보완해 주세요(지어낸 수정 방향).',
    evidencePages: input.evidencePages ?? [],
    evidenceInternal: low ? '' : '지어낸 판단 근거',
    position: input.position ?? null,
    exampleSentence: input.example ?? null,
  };
}

/** 낱말 수 표를 많은 차례(같으면 처음 나온 차례)로. */
function ranked(counted: Map<string, number>): TermCount[] {
  return [...counted]
    .map(([term, count]) => ({ term, count }))
    .sort((a, b) => b.count - a.count);
}

export function buildMockResult(input: MockResultInput): ScanResult {
  const extraTerms = input.extraTerms ?? [];
  const baseKeys = new Set(input.defaultTerms.map(termKey));
  // 빈도에 드는 낱말: 기본 목록 단어, 그리고 기본 목록과 키가 겹치지 않는 추가 단어(서버 frequency_extras).
  // 기본 목록과 겹친 추가 단어는 빈도에 줄이 없다(그 낱말은 기본 단어 줄로 센다).
  const inFrequency = (term: string) =>
    input.defaultTerms.includes(term) ||
    (extraTerms.includes(term) && !baseKeys.has(termKey(term)));
  const pagesOut: PageTermCounts[] = [];
  const total = new Map<string, number>();
  for (const page of Object.keys(input.wordPages)
    .map(Number)
    .sort((a, b) => a - b)) {
    const counted = new Map<string, number>();
    for (const [term, count] of Object.entries(input.wordPages[page]!))
      if (count >= 1 && inFrequency(term))
        counted.set(term, (counted.get(term) ?? 0) + count);
    if (counted.size === 0) continue;
    pagesOut.push({ page, counts: ranked(counted) });
    for (const [term, count] of counted)
      total.set(term, (total.get(term) ?? 0) + count);
  }

  const items = input.items.map((item) => toItem(item, input.parts));
  const byLevel = zero();
  for (const item of items) byLevel[item.level] += 1;
  const byPart: Record<string, LevelCounts> = {};
  for (const part of input.parts) {
    const counts = zero();
    for (const item of items)
      if (item.parts.includes(part.name)) counts[item.level] += 1;
    byPart[part.name] = counts;
  }
  const pages = [...new Set(input.parts.flatMap((part) => part.pages))].sort(
    (a, b) => a - b,
  );
  const failed = input.failedPages ?? [];
  const kept = items.length + failed.length;
  return {
    schemaVersion: RESULT_SHAPE,
    source: {
      fileName: input.fileName,
      sha256: fakeSha(input.fileName),
      pageCount: input.pageCount,
    },
    config: MOCK_CONFIG,
    models: { chat: 'mock-chat', embedding: 'mock-embedding' },
    promptVersion: 'mock-v1',
    parts: input.parts.map((part) => ({
      name: part.name,
      pages: [...part.pages],
    })),
    pages,
    extraTerms: [...extraTerms],
    items,
    candidateStats: {
      raw: kept + 4,
      hardDropped: 1,
      nonEnvDropped: 1,
      promoDropped: 0,
      tableDropped: 2,
      kept,
      failedPages: failed.map((page) => ({
        page,
        error: '지어낸 오류: 응답을 읽지 못했어요',
      })),
    },
    counts: { total: items.length, byLevel, byPart },
    wordCounts: { total: ranked(total), pages: pagesOut },
    dryRun: null,
    report: { file: 'greenwash-report.xlsx' },
  };
}

/** 점검 설정(지어낸 값. 화면에 보이지 않는 기록 칸). */
const MOCK_CONFIG: ScanResult['config'] = {
  checker: {
    maxCandidatesPerPage: 3,
    maxCharsPageText: 2500,
    evidenceK: 4,
    maxCharsPerChunk: 800,
    useEvidenceFailopen: false,
    maxCharsEvidenceTotal: 6000,
    reportLevels: [...LEVELS],
    debug: false,
    debugPages: 0,
    batchEval: false,
    promptVersion: 'mock-v1',
  },
  chunking: {
    chunkSize: 800,
    chunkOverlap: 150,
    separators: ['\n\n', '\n', ' '],
    normalize: true,
    embeddingBatchSize: 50,
  },
  chat: { temperature: 0.2, maxTokens: 1200 },
};

/**
 * 새로 만든 실행의 결과 [R7]: 지정한 쪽에서 결정적으로 문장 n개(3~6, 등급 셋이 다 나오게 High → Mid → Low 차례).
 * page 는 지정한 쪽 안이다. 낱말 수도 쪽 번호로 정해진다. position 은 High·Low 에만 있고 Mid 는 null(섞임, 덧붙임 1).
 */
export function generatedItems(
  checked: readonly number[],
  nameOf: (page: number) => string,
): MockItemInput[] {
  if (checked.length === 0) return [];
  const n = Math.max(3, Math.min(6, checked.length));
  return Array.from({ length: n }, (_, i) => {
    const page = checked[i % checked.length]!;
    const level = LEVELS[i % 3]!;
    return {
      page,
      level,
      sentence: `[목 ${i + 1}] ${nameOf(page)} ${page}쪽의 지어낸 환경 주장 문장이에요.`,
      riskTags:
        level === 'High' ? ['미래 약속', '목표 근거 부족'] : ['근거 부족'],
      evidencePages: level === 'Mid' ? [] : [page],
      // 위치는 High·Low 만 찾았다고 둔다: 한 결과 안에 상자 있음·없음이 섞인다(발주서 덧붙임 1)
      position:
        level === 'Mid' ? null : (
          { page, boxes: [[72, 120 + i * 40, 500, 134 + i * 40]] }
        ),
    };
  });
}

/** 새 실행의 낱말 수: 점검 쪽마다 기본 단어 하나(쪽 번호로 고름), 첫 쪽에 추가 단어 하나씩. */
export function generatedWordPages(
  checked: readonly number[],
  defaultTerms: readonly string[],
  extraTerms: readonly string[],
): Record<number, Record<string, number>> {
  const out: Record<number, Record<string, number>> = {};
  checked.forEach((page, index) => {
    const row: Record<string, number> = {};
    if (defaultTerms.length > 0)
      row[defaultTerms[page % defaultTerms.length]!] = 1 + (page % 3);
    if (index === 0) for (const term of extraTerms) row[term] = 1;
    out[page] = row;
  });
  return out;
}
