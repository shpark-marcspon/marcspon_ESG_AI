// (밴드 FS1 ③: results.test.ts 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 결과·검토 domain(밴드 FW2 ① §3): 요약 셈, 「추가」, 검토 잇기·거르기, PUT 본문, 확정 본문, 제외 사유 글, 서버 단계 맞춤,
// 바깥 상자, 목록 줄, 시각 꾸미기. 표 꼴. 심은 파손 (나)는 confirmUpdate 의 시험이 잡는다(위험 유형 셈 riskTagCounts 와 그 시험은 밴드 GW2R ① 에서 지웠다 — v115 GW-04_r2).
import { describe, expect, it } from 'vitest';

import type {
  Level,
  ResultItem,
  ScanResult,
} from '../../../entities/greenwash/model/index.ts';
import {
  countsAgree,
  failedPagesOf,
  isExtraTermRow,
  levelCountsOf,
  partSummaries,
  termFrequency,
} from './summary.ts';

const item = (
  page: number,
  parts: string[],
  level: Level,
  tags: string[] = [],
): ResultItem => ({
  page,
  parts,
  sentence: `문장 ${page}`,
  level,
  riskTags: level === 'Low' ? ['선언적 문장'] : tags,
  confirmedInEvidence: [],
  missingFields: [],
  reasonBullets: [],
  fixParagraph: '고칠 방향',
  evidencePages: [],
  evidenceInternal: '',
  position: null,
  exampleSentence: null,
});

function result(overrides: Partial<ScanResult> = {}): ScanResult {
  const items = overrides.items ?? [
    item(2, ['CEO'], 'High', ['미래 약속', '목표 근거 부족']),
    item(4, ['회사', '기후'], 'Mid', ['미래 약속']),
    item(5, ['기후'], 'Low'),
  ];
  return {
    schemaVersion: 'greenwash.result@1',
    source: { fileName: 'a.pdf', sha256: 'a'.repeat(64), pageCount: 10 },
    config: {
      checker: {
        maxCandidatesPerPage: 3,
        maxCharsPageText: 1,
        evidenceK: 1,
        maxCharsPerChunk: 1,
        useEvidenceFailopen: false,
        maxCharsEvidenceTotal: 1,
        reportLevels: [],
        debug: false,
        debugPages: 0,
        batchEval: false,
        promptVersion: 'v',
      },
      chunking: {
        chunkSize: 1,
        chunkOverlap: 0,
        separators: [],
        normalize: true,
        embeddingBatchSize: 1,
      },
      chat: { temperature: 0, maxTokens: 1 },
    },
    models: { chat: 'c', embedding: 'e' },
    promptVersion: 'v',
    parts: [
      { name: 'CEO', pages: [2] },
      { name: '회사', pages: [3, 4] },
      { name: '기후', pages: [4, 5] },
    ],
    pages: [2, 3, 4, 5],
    extraTerms: [],
    items,
    candidateStats: {
      raw: 3,
      hardDropped: 0,
      nonEnvDropped: 0,
      promoDropped: 0,
      tableDropped: 0,
      kept: 3,
      failedPages: [],
    },
    counts: {
      total: items.length,
      byLevel: levelCountsOf(items),
      byPart: {},
    },
    wordCounts: {
      total: [
        { term: '친환경', count: 4 },
        { term: '탄소중립', count: 2 },
      ],
      pages: [
        { page: 2, counts: [{ term: '탄소중립', count: 1 }] },
        {
          page: 4,
          counts: [
            { term: '친환경', count: 3 },
            { term: '탄소중립', count: 1 },
          ],
        },
        { page: 9, counts: [{ term: '친환경', count: 1 }] },
      ],
    },
    dryRun: null,
    report: { file: 'greenwash-report.xlsx' },
    ...overrides,
  };
}

describe('결과 요약 셈', () => {
  it('등급별 수는 items 로 세고, counts 와 맞는지 낸다', () => {
    const r = result();
    expect(levelCountsOf(r.items)).toEqual({ High: 1, Mid: 1, Low: 1 });
    expect(countsAgree(r)).toBe(true);
    expect(
      countsAgree(
        result({
          counts: {
            total: 3,
            byLevel: { High: 2, Mid: 0, Low: 1 },
            byPart: {},
          },
        }),
      ),
    ).toBe(false);
  });

  it('파트별 수: 두 파트에 든 문장은 두 파트에 다 센다(합이 전체보다 클 수 있다)', () => {
    const parts = partSummaries(result());
    expect(parts.map((p) => [p.name, p.counts, p.total])).toEqual([
      ['CEO', { High: 1, Mid: 0, Low: 0 }, 1],
      ['회사', { High: 0, Mid: 1, Low: 0 }, 1],
      ['기후', { High: 0, Mid: 1, Low: 1 }, 2],
    ]);
    expect(parts.reduce((sum, p) => sum + p.total, 0)).toBe(4);
  });

  it('단어 빈도: 전체는 total 그대로, 파트는 그 파트의 쪽을 묶어 더한다', () => {
    const r = result();
    expect(termFrequency(r, { kind: 'total' })).toEqual(r.wordCounts.total);
    expect(termFrequency(r, { kind: 'part', name: 'CEO' })).toEqual([
      { term: '탄소중립', count: 1 },
    ]);
    // 기후(4·5쪽): 4쪽만 낱말이 있다. 9쪽은 어느 파트에도 없다
    expect(termFrequency(r, { kind: 'part', name: '기후' })).toEqual([
      { term: '친환경', count: 3 },
      { term: '탄소중립', count: 1 },
    ]);
    expect(termFrequency(r, { kind: 'part', name: '없음' })).toEqual([]);
  });

  it('「추가」 표시 [R1]: 추가 단어이고 기본 목록에 없을 때만. 키는 띄어쓰기·대소문자를 무시', () => {
    const defaults = ['친환경', '탄소중립'];
    const cases: [string, string[], boolean][] = [
      ['초록 물결', ['초록 물결'], true],
      ['초록물결', ['초록 물결'], true],
      ['GreenWave', ['green-wave'], true],
      // 기본 목록과 키가 겹친 추가 단어: 그 줄은 기본 단어 줄이다
      ['탄소중립', ['탄소 중립'], false],
      ['탄소 중립', ['탄소 중립'], false],
      ['친환경', [], false],
      ['초록 물결', [], false],
    ];
    for (const [term, extras, expected] of cases)
      expect(isExtraTermRow(term, extras, defaults), term).toBe(expected);
  });

  it('분석하지 못한 쪽: 오름차순·겹침 없음, 없으면 빈 목록', () => {
    const stats = result().candidateStats;
    expect(failedPagesOf(result())).toEqual([]);
    expect(
      failedPagesOf(
        result({
          candidateStats: {
            ...stats,
            failedPages: [
              { page: 9, error: 'x' },
              { page: 3, error: 'y' },
              { page: 9, error: 'z' },
            ],
          },
        }),
      ),
    ).toEqual([3, 9]);
  });
});
