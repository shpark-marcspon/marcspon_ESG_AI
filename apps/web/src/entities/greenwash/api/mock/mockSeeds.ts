// 목록(GW-01) 씨앗(밴드 FW2 ①). 시안 GW-01 의 상태 다섯(검토 중 · 검토 대기 · AI 점검 중 · 멈춤 · 검토 완료)을 지어낸 이름으로.
//   - 「목-환경경영보고서-2026.pdf」는 수정본이다: 앞 판 「…-초안.pdf」 가 더 있지만 목록에는 마지막 판만(「이전 버전 1개」).
//   - 검토 중 결과(run-101)는 failedPages 가 있고, position 있는 문장 셋과 null 인 문장 둘이 섞인다(발주서 덧붙임 1 — 위치는 pdfium, 못 찾으면 null). 검토 대기 결과(run-102)는 추가 단어 둘이고
//     그 하나(「탄소 중립」)는 기본 목록의 「탄소중립」과 키가 겹친다. 확정 결과(run-105)는 검토의 confirmedBy 에 확정한 사람이 있다(그 밖의 검토는 null).
//   - 실패 씨앗(run-104)은 실행 전체 실패다. 「목-지속가능경영보고서-2026.pdf」는 실행이 둘이다(run-100 실패 → run-101, 2회차).
//   - 실호출 씨앗(run-106, 밴드 FX1)은 예외다: 결과는 공개 보고서 B 를 실제로 1회 돌린 결과를 가린 판(fixtures/report-b.result.json,
//     가림 sid:MARC-ENT-190, sid:MARC-ISSUE-129)이고 거울(parseResult)을 지나 들어간다. 파싱이 안 되면 목을 지을 때 던진다.
//     문서 이름 B.pdf·쪽 수 89 는 결과의 source 그대로, 파트 쪽은 결과의 parts 그대로다. High 0 이다.
// 그 밖의 이름·문장·수는 지어낸 것이다. 시각은 +09:00 ISO 8601.
import type {
  GreenwashReview,
  RunProgress,
  ScanResult,
} from '../../model/index.ts';
import { isScanResult } from '../../model/index.ts';
import { parseResult } from '../contract/index.ts';
import type { RunRequest } from '../store.ts';
import reportBRaw from './fixtures/report-b.result.json?raw';
import { MOCK_PART_NAMES, buildMockResult } from './mockResults.ts';

export const MOCK_CURRENT_USER = { userId: 'user-1', name: '김하나' } as const;
export const MOCK_OTHER_USER = { userId: 'user-2', name: '이두리' } as const;

/** 목 사용자 → 검토의 confirmedBy(GreenwashReviewer: id 는 int). id 는 userId 의 숫자(user-2 → 2) — 목 사용자의 「user-N」 꼴만 맞다. */
export const mockReviewer = (user: { userId: string; name: string }) => ({
  id: Number(user.userId.replace(/\D/g, '')),
  name: user.name,
});
export const MOCK_COMPANY_NAME = '고객사 A';

export interface SeedDoc {
  documentId: string;
  fileName: string;
  pageCount: number;
  reportYear: number | null;
  previousDocumentId: string | null;
  uploadedAt: string;
  uploadedBy: { userId: string; name: string };
}

export interface SeedRun {
  runId: string;
  documentId: string;
  createdAt: string;
  startedAt: string | null;
  progress: RunProgress;
  request: RunRequest;
  result: ScanResult | null;
  review: GreenwashReview | null;
}

const parts = (
  ceo: number[],
  company: number[],
  climate: number[],
): RunRequest['parts'] => ({ ceo, company, climate });

const request = (p: RunRequest['parts'], extraTerms: string[] = []) => ({
  parts: p,
  extraTerms,
  reportYear: 2026,
  previousDocumentId: null,
});

const named = (p: RunRequest['parts']) => [
  { name: MOCK_PART_NAMES.ceo, pages: p.ceo },
  { name: MOCK_PART_NAMES.company, pages: p.company },
  { name: MOCK_PART_NAMES.climate, pages: p.climate },
];

/** 실호출 씨앗의 실행 id(밴드 FX1). */
export const REPORT_B_RUN_ID = 'run-106';

/** 실호출 결과(가린 판)를 거울로 읽는다. 꼴이 어긋나면 던진다(조용히 빼지 않는다). */
export function reportBResult(): ScanResult {
  const parsed = parseResult(JSON.parse(reportBRaw));
  if (!parsed.ok)
    throw new Error(
      `fixtures/report-b.result.json 이 거울을 지나지 않는다: ${parsed.issues}`,
    );
  if (!isScanResult(parsed.value))
    throw new Error('fixtures/report-b.result.json 이 dry-run 결과다');
  return parsed.value;
}

export function seedDocs(): SeedDoc[] {
  return [
    {
      documentId: 'doc-s1',
      fileName: '목-지속가능경영보고서-2026.pdf',
      pageCount: 60,
      reportYear: 2026,
      previousDocumentId: null,
      uploadedAt: '2026-10-13T09:10:00+09:00',
      uploadedBy: MOCK_CURRENT_USER,
    },
    {
      documentId: 'doc-s0',
      fileName: '목-환경경영보고서-2026-초안.pdf',
      pageCount: 48,
      reportYear: 2026,
      previousDocumentId: null,
      uploadedAt: '2026-09-30T14:00:00+09:00',
      uploadedBy: MOCK_OTHER_USER,
    },
    {
      documentId: 'doc-s2',
      fileName: '목-환경경영보고서-2026.pdf',
      pageCount: 52,
      reportYear: 2026,
      previousDocumentId: 'doc-s0',
      uploadedAt: '2026-10-12T16:30:00+09:00',
      uploadedBy: MOCK_OTHER_USER,
    },
    {
      documentId: 'doc-s3',
      fileName: '목-통합보고서-2026.pdf',
      pageCount: 139,
      reportYear: 2026,
      previousDocumentId: null,
      uploadedAt: '2026-10-15T08:50:00+09:00',
      uploadedBy: MOCK_CURRENT_USER,
    },
    {
      documentId: 'doc-s4',
      fileName: '목-기후공시-2025.pdf',
      pageCount: 36,
      reportYear: 2025,
      previousDocumentId: null,
      uploadedAt: '2026-10-14T11:00:00+09:00',
      uploadedBy: MOCK_OTHER_USER,
    },
    {
      documentId: 'doc-s5',
      fileName: '목-ESG하이라이트-2025.pdf',
      pageCount: 24,
      reportYear: 2025,
      previousDocumentId: null,
      uploadedAt: '2026-10-02T10:00:00+09:00',
      uploadedBy: MOCK_CURRENT_USER,
    },
    {
      // 실호출 씨앗(밴드 FX1): 이름·쪽 수는 결과의 source 그대로. 보고연도는 결과에 없어 비운다.
      documentId: 'doc-s6',
      fileName: 'B.pdf',
      pageCount: 89,
      reportYear: null,
      previousDocumentId: null,
      uploadedAt: '2026-10-16T21:10:00+09:00',
      uploadedBy: MOCK_CURRENT_USER,
    },
  ];
}

export function seedRuns(defaultTerms: readonly string[]): SeedRun[] {
  const p1 = parts([2, 3], [4, 5], [5, 6, 7, 8]);
  const p2 = parts([2], [3, 4], [6, 7, 8, 9, 10]);
  const p3 = parts([3, 4], [5, 6], [20, 21, 22, 23, 24, 25, 26]);
  const p4 = parts([], [2, 3], [10, 11, 12, 13, 14]);
  const p5 = parts([2], [], [4, 5, 6]);
  const done = (total: number): RunProgress => ({
    state: 'done',
    stage: 'summarize',
    judge: { done: total, total },
  });
  return [
    {
      runId: 'run-100',
      documentId: 'doc-s1',
      createdAt: '2026-10-13T09:20:00+09:00',
      startedAt: '2026-10-13T09:20:05+09:00',
      progress: {
        state: 'failed',
        stage: 'judge',
        judge: { done: 3, total: 7 },
      },
      request: request(p1),
      result: null,
      review: null,
    },
    {
      runId: 'run-101',
      documentId: 'doc-s1',
      createdAt: '2026-10-14T10:00:00+09:00',
      startedAt: '2026-10-14T10:00:04+09:00',
      progress: done(7),
      request: request(p1),
      result: buildMockResult({
        fileName: '목-지속가능경영보고서-2026.pdf',
        pageCount: 60,
        parts: named(p1),
        defaultTerms,
        failedPages: [7],
        items: [
          {
            page: 2,
            level: 'High',
            sentence:
              '목회사는 2030년까지 모든 사업장에서 탄소중립을 반드시 이루겠습니다.',
            riskTags: ['미래 약속', '목표 근거 부족'],
            missing: ['기준연도', '감축 경로'],
            evidencePages: [6, 8],
            position: {
              page: 2,
              boxes: [
                [72, 140.5, 523.2, 154],
                [72, 156, 301.8, 169.5],
              ],
            },
          },
          {
            page: 3,
            level: 'Mid',
            sentence: '우리의 모든 제품은 친환경 소재로 만들어집니다.',
            riskTags: ['포괄적 표현'],
            confirmed: ['재생 소재 비율 표가 있음'],
            missing: ['제품별 비율'],
            evidencePages: [5],
            position: { page: 3, boxes: [[90, 320, 480, 334]] },
          },
          {
            page: 5,
            level: 'Mid',
            sentence: '물류 차량을 녹색 차량으로 바꾸고 있습니다.',
            riskTags: ['근거 부족'],
            evidencePages: [],
          },
          {
            page: 6,
            level: 'Low',
            sentence: '우리는 지구를 위한 길을 계속 걷겠습니다.',
          },
          {
            page: 8,
            level: 'High',
            sentence: '공장 배출을 지난해보다 크게 줄였습니다.',
            riskTags: ['수치 없음', '근거 부족'],
            evidencePages: [8],
            position: {
              page: 8,
              boxes: [
                [72, 410, 530, 424],
                [72, 426, 210, 440],
              ],
            },
            example:
              '공장 배출량을 지난해 대비 12% 줄였어요(지어낸 예시 문장).',
          },
        ],
        wordPages: {
          2: { 탄소중립: 1, 친환경: 1 },
          3: { 친환경: 2 },
          5: { 녹색: 1 },
          11: { 지속가능: 1 },
        },
      }),
      review: {
        schemaVersion: 'greenwash.review@3',
        evidence: [],
        rejudges: [],
        runId: 101,
        state: 'in_review',
        confirmedAt: null,
        confirmedBy: null,
        marks: [
          { itemIndex: 0, decision: 'adopted', excludeReason: null },
          {
            itemIndex: 2,
            decision: 'excluded',
            excludeReason: '근거가 문서에 있음(AI 가 놓침): 부록 표에 있어요',
          },
        ],
        edits: [],
      },
    },
    {
      runId: 'run-102',
      documentId: 'doc-s2',
      createdAt: '2026-10-12T16:40:00+09:00',
      startedAt: '2026-10-12T16:40:03+09:00',
      progress: done(8),
      request: request(p2, ['초록 물결', '탄소 중립']),
      result: buildMockResult({
        fileName: '목-환경경영보고서-2026.pdf',
        pageCount: 52,
        parts: named(p2),
        defaultTerms,
        extraTerms: ['초록 물결', '탄소 중립'],
        items: [
          {
            page: 2,
            level: 'Mid',
            sentence: '초록 물결 캠페인으로 지역의 환경을 지킵니다.',
            riskTags: ['포괄적 표현'],
            evidencePages: [7],
          },
          {
            page: 4,
            level: 'High',
            sentence: '넷제로를 이미 이뤘습니다.',
            riskTags: ['사실 과장'],
            evidencePages: [],
          },
          {
            page: 7,
            level: 'Low',
            sentence: '앞으로도 환경을 생각하는 회사가 되겠습니다.',
          },
        ],
        wordPages: {
          2: { '초록 물결': 3, 친환경: 1 },
          4: { 넷제로: 2, '탄소 중립': 1 },
          7: { 탄소중립: 2, 녹색: 1 },
        },
      }),
      review: {
        schemaVersion: 'greenwash.review@3',
        evidence: [],
        rejudges: [],
        runId: 102,
        state: 'pending',
        confirmedAt: null,
        confirmedBy: null,
        marks: [],
        edits: [],
      },
    },
    {
      runId: 'run-103',
      documentId: 'doc-s3',
      createdAt: '2026-10-15T09:00:00+09:00',
      startedAt: '2026-10-15T09:00:06+09:00',
      progress: {
        state: 'running',
        stage: 'judge',
        judge: { done: 6, total: 11 },
      },
      request: request(p3),
      result: null,
      review: null,
    },
    {
      runId: 'run-104',
      documentId: 'doc-s4',
      createdAt: '2026-10-14T11:10:00+09:00',
      startedAt: '2026-10-14T11:10:02+09:00',
      progress: {
        state: 'failed',
        stage: 'judge',
        judge: { done: 2, total: 7 },
      },
      request: { ...request(p4), reportYear: 2025 },
      result: null,
      review: null,
    },
    {
      runId: 'run-105',
      documentId: 'doc-s5',
      createdAt: '2026-10-02T10:10:00+09:00',
      startedAt: '2026-10-02T10:10:05+09:00',
      progress: done(4),
      request: { ...request(p5), reportYear: 2025 },
      result: buildMockResult({
        fileName: '목-ESG하이라이트-2025.pdf',
        pageCount: 24,
        parts: named(p5),
        defaultTerms,
        items: [
          {
            page: 2,
            level: 'High',
            sentence: '목회사는 업계에서 가장 친환경적인 기업입니다.',
            riskTags: ['비교 근거 없음'],
            evidencePages: [5],
          },
          {
            page: 5,
            level: 'Low',
            sentence: '지속가능한 내일을 약속합니다.',
          },
        ],
        wordPages: { 2: { 친환경: 2 }, 5: { 지속가능: 1 } },
      }),
      review: {
        schemaVersion: 'greenwash.review@3',
        evidence: [],
        rejudges: [],
        runId: 105,
        state: 'confirmed',
        confirmedAt: '2026-10-03T15:30:00+09:00',
        confirmedBy: mockReviewer(MOCK_OTHER_USER),
        marks: [
          { itemIndex: 0, decision: 'adopted', excludeReason: null },
          {
            itemIndex: 1,
            decision: 'excluded',
            excludeReason: '환경 주장 문장이 아님',
          },
        ],
        edits: [],
      },
    },
    reportBRun(),
  ];
}

/** 실호출 씨앗의 끝난 실행(밴드 FX1). 입력 쪽은 결과의 parts 를 서버 차례(CEO 메시지 · 회사소개 · 기후/환경 토픽)로 읽은 것. 검토는 아직(pending). */
function reportBRun(): SeedRun {
  const result = reportBResult();
  const pagesOf = (name: string) => [
    ...(result.parts.find((part) => part.name === name)?.pages ?? []),
  ];
  const p = parts(
    pagesOf(MOCK_PART_NAMES.ceo),
    pagesOf(MOCK_PART_NAMES.company),
    pagesOf(MOCK_PART_NAMES.climate),
  );
  const total = result.pages.length;
  return {
    runId: REPORT_B_RUN_ID,
    documentId: 'doc-s6',
    createdAt: '2026-10-16T21:15:00+09:00',
    startedAt: '2026-10-16T21:15:05+09:00',
    progress: {
      state: 'done',
      stage: 'summarize',
      judge: { done: total, total },
    },
    request: { ...request(p), reportYear: null },
    result,
    review: {
      schemaVersion: 'greenwash.review@3',
      evidence: [],
      rejudges: [],
      runId: 106,
      state: 'pending',
      confirmedAt: null,
      confirmedBy: null,
      marks: [],
      edits: [],
    },
  };
}
