// 결과 greenwash.result@1 과 검토 greenwash.review@3 의 꼴(밴드 FW2 ①, @2 고침 칸 G1b-3 ①). TypeScript 꼴만 있다 — 값 검사는 api/contract 의 zod 거울이 한다.
// 정본은 서버의 고정 파일이다(main ee18aaa, 읽기만):
//   apps/api-py/esgapi/greenwash/tests/data/flow-shapes/greenwash.result@1.schema.json (contracts/shapes.py)
//   apps/api-py/esgapi/greenwash/tests/data/flow-shapes/review/greenwash.review@3.schema.json (contracts/review_shapes.py)
//   PUT 본문 GreenwashReviewUpdate (service/apis/greenwash.py)
// 칸 이름은 계약 그대로(camelCase — 밴드 GC3·WC2. 값이 키인 사전의 열쇠(LevelCounts 의 High·Mid·Low, byPart 의 파트 이름)는 데이터 그대로)다. 거울(api/contract)은 이 꼴을 `z.ZodType<…>` 로 맞춘다.
// 계약은 초안 판이다(README): 칸이 바뀌면 이 파일과 거울을 같이 고친다.

export const LEVELS = ['High', 'Mid', 'Low'] as const;
/** 판정 등급. */
export type Level = (typeof LEVELS)[number];

export const RESULT_SHAPE = 'greenwash.result@1';
export const REVIEW_SHAPE = 'greenwash.review@3';

/** [left, top, right, bottom], 포인트, 원점은 쪽의 왼쪽 위. */
export type Box = readonly [number, number, number, number];

export interface ResultPosition {
  page: number;
  boxes: readonly Box[];
}

export interface ResultSource {
  fileName: string;
  sha256: string;
  pageCount: number;
}

export interface CheckerConfig {
  maxCandidatesPerPage: number;
  maxCharsPageText: number;
  evidenceK: number;
  maxCharsPerChunk: number;
  useEvidenceFailopen: boolean;
  maxCharsEvidenceTotal: number;
  reportLevels: readonly string[];
  debug: boolean;
  debugPages: number;
  batchEval: boolean;
  promptVersion: string;
}

export interface ChunkingConfig {
  chunkSize: number;
  chunkOverlap: number;
  separators: readonly string[];
  normalize: boolean;
  embeddingBatchSize: number;
}

export interface ResultConfig {
  checker: CheckerConfig;
  chunking: ChunkingConfig;
  chat: { temperature: number; maxTokens: number };
}

export interface ResultModels {
  chat: string;
  embedding: string;
}

export interface ResultPart {
  /** 파트 이름(서버 글자 그대로: 「CEO 메시지」·「회사소개」·「기후/환경 토픽」). */
  name: string;
  pages: readonly number[];
}

export interface ResultItem {
  page: number;
  parts: readonly string[];
  sentence: string;
  level: Level;
  riskTags: readonly string[];
  confirmedInEvidence: readonly string[];
  missingFields: readonly string[];
  reasonBullets: readonly string[];
  fixParagraph: string;
  evidencePages: readonly number[];
  evidenceInternal: string;
  position: ResultPosition | null;
  exampleSentence: string | null;
}

export interface FailedPage {
  page: number;
  error: string;
}

export interface CandidateStats {
  raw: number;
  hardDropped: number;
  nonEnvDropped: number;
  promoDropped: number;
  tableDropped: number;
  kept: number;
  failedPages: readonly FailedPage[];
}

export interface LevelCounts {
  High: number;
  Mid: number;
  Low: number;
}

export interface ResultCounts {
  total: number;
  byLevel: LevelCounts;
  byPart: Readonly<Record<string, LevelCounts>>;
}

export interface TermCount {
  term: string;
  count: number;
}

export interface PageTermCounts {
  page: number;
  counts: readonly TermCount[];
}

export interface WordCounts {
  total: readonly TermCount[];
  pages: readonly PageTermCounts[];
}

export type TokenCount =
  | { status: 'measured'; encoding: string; value: number }
  | { status: 'unmeasured'; encoding: string; reason: string };

export interface Tally {
  requests: number;
  inputChars: number;
  inputTokens: TokenCount;
}

export interface TallyByKind {
  detect: Tally;
  eval: Tally;
  lowOnly: Tally;
  repair: Tally;
}

export interface DryRun {
  pagesChecked: number;
  pagesWithText: number;
  pagesTruncated: number;
  chunks: number;
  embeddingIndex: Tally;
  ruleCandidates: number;
  lower: {
    chat: Tally;
    chatByKind: TallyByKind;
    embeddingQueries: Tally;
    judged: number;
  };
  upper: {
    chat: Tally;
    chatByKind: TallyByKind;
    embeddingQueries: Tally;
    outputTokensMax: number;
    evidenceChars: number;
    evidenceCapReached: boolean;
  };
  perPage: readonly {
    page: number;
    textChars: number;
    truncated: boolean;
    ruleCandidates: number;
    lowerJudged: number;
  }[];
}

interface ResultCommon {
  schemaVersion: typeof RESULT_SHAPE;
  source: ResultSource;
  config: ResultConfig;
  models: ResultModels;
  promptVersion: string;
  parts: readonly ResultPart[];
  pages: readonly number[];
  extraTerms: readonly string[];
  /** 빈도에 센 낱말 전체 — AI 설정 판의 대상 단어로 센 실행에만 있다(밴드 G2d ③). */
  terms?: readonly string[];
  wordCounts: WordCounts;
}

/** 점검한 실행(dryRun 이 null). */
export interface ScanResult extends ResultCommon {
  items: readonly ResultItem[];
  candidateStats: CandidateStats;
  counts: ResultCounts;
  dryRun: null;
  report: { file: 'greenwash-report.xlsx' };
}

/** dry-run(판정하지 않음): items 는 빈 목록, candidateStats·counts·report 는 null. */
export interface DryRunResult extends ResultCommon {
  items: readonly [];
  candidateStats: null;
  counts: null;
  dryRun: DryRun;
  report: null;
}

/** greenwash.result@1. 갈래는 dryRun 이 null 이냐로 가른다. */
export type GreenwashResult = ScanResult | DryRunResult;

export function isScanResult(result: GreenwashResult): result is ScanResult {
  return result.dryRun === null;
}

/**
 * 인식 실패 페이지(쪽 번호 오름차순, 겹침 없음) — 결과 candidateStats.failedPages 에서만(실행 상태에는 쪽 번호가 없다).
 * 없거나 dry-run 이면 빈 목록. GW-03 끝남(밴드 GW2R ② Q4)과 GW-04 인식 실패 페이지 줄(Q7)이 같이 쓴다.
 */
export function failedPagesOf(result: GreenwashResult): number[] {
  if (result.candidateStats === null) return [];
  return [
    ...new Set(result.candidateStats.failedPages.map((f) => f.page)),
  ].sort((a, b) => a - b);
}

// ── 검토 greenwash.review@3(@2 + 근거 고침 evidence·재판단 rejudges — GRJ1) ──

export const REVIEW_STATES = ['pending', 'in_review', 'confirmed'] as const;
/** 검토 대기 · 검토 중 · 확정. */
export type ReviewState = (typeof REVIEW_STATES)[number];
export type ReviewDecision = 'adopted' | 'excluded';

export interface ReviewMark {
  /** 결과 items 의 차례(0부터). */
  itemIndex: number;
  decision: ReviewDecision;
  /** excluded 일 때만 글, 그 밖에는 null. */
  excludeReason: string | null;
}

/** 확정한 사람(GreenwashReviewer). 이름은 빈 글자가 아니다. */
export interface ReviewReviewer {
  id: number;
  name: string;
}

export interface GreenwashReview {
  schemaVersion: typeof REVIEW_SHAPE;
  runId: number;
  state: ReviewState;
  /** confirmed 일 때만 +09:00 ISO 8601. */
  confirmedAt: string | null;
  /** 확정한 사람(GC2). confirmed 일 때만 값, 그 밖에는 null(confirmedAt 과 같은 규칙). */
  confirmedBy: ReviewReviewer | null;
  /** itemIndex 오름차순, 겹치지 않음. 없는 문장은 미검토. */
  marks: readonly ReviewMark[];
  /** 고친 문장(G1b-3). itemIndex 오름차순, 겹치지 않음. 고친 칸이 하나 이상인 문장만, 없으면 []. */
  edits: readonly ReviewEdit[];
  /** 근거를 고친 문장(GRJ1). itemIndex 오름차순, 겹치지 않음. 없으면 []. */
  evidence: readonly ReviewEvidence[];
  /** 재판단 실행이 있는 문장(GRJ1). itemIndex 오름차순, 겹치지 않음. 없으면 []. */
  rejudges: readonly ReviewRejudge[];
}

/** 사람이 더한 근거 조각(GreenwashEvidenceAdded). page 는 1부터, 고르지 않았으면 null. */
export interface EvidenceAdded {
  text: string;
  page: number | null;
}

/** 문장 하나의 근거 고침(GreenwashReviewEvidence). removed = 기준 판단 confirmedInEvidence 의 지운 차례. */
export interface ReviewEvidence {
  itemIndex: number;
  removed: readonly number[];
  added: readonly EvidenceAdded[];
  editedAt: string;
  editedBy: ReviewReviewer;
}

/** PUT 본문의 근거 고침(GreenwashReviewEvidenceIn). */
export interface ReviewEvidenceIn {
  itemIndex: number;
  removed: readonly number[];
  added: readonly EvidenceAdded[];
}

export type RejudgeStatus = 'running' | 'failed' | 'done';

/** 기준 판단(GreenwashRejudged) — 가장 늦게 끝난 재판단의 판단. nonrisk 면 level null. */
export interface Rejudged {
  runId: number;
  judgedAt: string;
  judgedBy: ReviewReviewer;
  outcome: 'judged' | 'nonrisk';
  level: Level | null;
  riskTags: readonly string[];
  confirmedInEvidence: readonly string[];
  missingFields: readonly string[];
  reasonBullets: readonly string[];
  fixParagraph: string;
  evidencePages: readonly number[];
  added: readonly EvidenceAdded[];
}

/** 문장 하나의 재판단 상태(GreenwashReviewRejudge). current null = 끝난 재판단 없음(첫 판단은 결과 items). */
export interface ReviewRejudge {
  itemIndex: number;
  status: RejudgeStatus;
  count: number;
  current: Rejudged | null;
}

/** 고친 칸 하나: 값과 그 칸 값이 바뀐 PUT 의 때(+09:00 ISO 8601)·사람. */
export interface ReviewEditedLevel {
  value: Level;
  editedAt: string;
  editedBy: ReviewReviewer;
}
export interface ReviewEditedReasons {
  value: readonly string[];
  editedAt: string;
  editedBy: ReviewReviewer;
}
export interface ReviewEditedFix {
  value: string;
  editedAt: string;
  editedBy: ReviewReviewer;
}

/** 문장 하나의 고침(GreenwashReviewEdit). 칸 null = AI 그대로(AI 원본은 결과 items[itemIndex]). 셋 중 하나 이상이 값. */
export interface ReviewEdit {
  itemIndex: number;
  level: ReviewEditedLevel | null;
  reasonBullets: ReviewEditedReasons | null;
  fixParagraph: ReviewEditedFix | null;
}

/** PUT 본문의 문장 하나의 고침(GreenwashReviewEditIn) — 평평한 값, null = 그 칸 고침 없음. 때·사람은 서버가 넣는다. */
export interface ReviewEditIn {
  itemIndex: number;
  level: Level | null;
  reasonBullets: readonly string[] | null;
  fixParagraph: string | null;
}

/**
 * PUT 본문(GreenwashReviewUpdate). marks 는 그 실행의 표시 전부를 갈아 넣는다. state 는 'confirmed' 나 없음(null)만 받는다(결함 D1):
 * 표시가 있으면 서버가 pending → in_review 로 옮기고, confirmed 면 미검토를 adopted 로 채워 확정한다.
 */
export interface ReviewUpdate {
  state?: 'confirmed' | null;
  marks: readonly ReviewMark[];
  /** 생략·null = 고침 그대로, 목록 = 그 실행의 고침 전부 갈아 넣기([] = 다 지움). 채택·제외·확정 PUT 은 싣지 않는다. */
  edits?: readonly ReviewEditIn[] | null;
  /** 생략·null = 근거 고침 그대로, 목록 = 그 실행의 근거 고침 전부 갈아 넣기([] = 다 지움). GRJ1. */
  evidence?: readonly ReviewEvidenceIn[] | null;
}
