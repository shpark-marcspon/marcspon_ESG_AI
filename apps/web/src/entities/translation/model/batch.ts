// 영문번역 서버 꼴의 타입(밴드 TRW1a ①). 묶음 translation.batch@1 · 요약 translation.digest@1 · 결과 translation.result@1 의 칸.
// 정본: apps/api-py/esgapi/translation/contracts/{batch_shapes,digest_shapes,shapes}.py(고정 파일 tests/data/…/*.schema.json).
// 값 검사는 api/contract/(zod 거울)가 하고, 이 파일은 타입만 — model·api·hooks·화면이 같이 쓴다. id 는 서버 꼴 그대로 수다.
// 부재는 null 그대로 둔다(digest null = 「모름」 — 0 으로 삼키지 않는다).

/** 서버 파트 이름(화면 파트 PartKey 와 잇는 것은 adapt.ts). */
export const SERVER_PARTS = ['ceo_message', 'story', 'general'] as const;
export type ServerPart = (typeof SERVER_PARTS)[number];

export type RunStatus = 'queued' | 'processing' | 'done' | 'failed';
export type StepStatus = 'pending' | 'running' | 'done' | 'failed';
export type BatchState = 'active' | 'done' | 'failed';
export type VariantLabel = 'single' | 'A' | 'B';
export type Outcome = 'done' | 'partial' | 'rejected';

/** 결과 rejection.kind(= 요약 rejectionKind) 일곱. */
export const SERVER_REJECTION_KINDS = [
  'no_pages',
  'ceo_page_limit',
  'unsupported_input',
  'too_large',
  'over_budget',
  'retry_source_not_found',
  'retry_source_mismatch',
] as const;
export type ServerRejectionKind = (typeof SERVER_REJECTION_KINDS)[number];

export interface BatchPerson {
  userId: number;
  name: string;
}
export interface BatchStep {
  step: string;
  status: StepStatus;
  done: number | null;
  total: number | null;
}
export interface PageBounds {
  start: number | null;
  end: number | null;
}
export interface StyleChoice {
  compareAb: boolean;
  single: 'A' | 'B';
}
export interface SeverityCounts {
  high: number;
  medium: number;
  low: number;
}

/** 요약 문체 하나의 Word 세 갈래(짓지 않았으면 null). */
export interface DigestFiles {
  bilingual: string | null;
  qa: string | null;
  autofix: string | null;
}
export interface DigestVariant {
  label: VariantLabel;
  reviewStatus: 'reviewed' | 'call_failed' | 'not_run';
  reviewStoppedAt: number | null;
  parseFailedPages: number;
  issueCount: number;
  issueCounts: SeverityCounts;
  glossaryMisses: number;
  autofixStatus: 'done' | 'stopped' | 'not_run';
  autofixChangedPages: number;
  files: DigestFiles;
}
/** translation.digest@1. */
export interface TranslationDigest {
  schemaVersion: 'translation.digest@1';
  status: 'done' | 'rejected';
  rejectionKind: ServerRejectionKind | null;
  outcome: Outcome;
  pageCount: number;
  failedPages: number[];
  variants: DigestVariant[];
  warningCount: number;
}

/** 파트의 최신 실행. */
export interface BatchRun {
  runId: number;
  /** 그 실행의 흐름 id 그대로(translation.colab@158 · translation.pdf@158 — TRS3). */
  flowId: string;
  status: RunStatus;
  pages: PageBounds | null;
  style: StyleChoice | null;
  glossaryCounts: { base: number; final: number };
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  failedStep: string | null;
  errorCode: string | null;
  steps: BatchStep[];
  digest: TranslationDigest | null;
}
export interface BatchEarlier {
  runId: number;
  status: RunStatus;
  createdAt: string;
  finishedAt: string | null;
  outcome: Outcome | null;
}
export interface ServerBatchPart {
  part: ServerPart;
  latest: BatchRun;
  earlier: BatchEarlier[];
  round: number;
}
/**
 * translation.batch@1. 서버 칸 `document` 는 거울(api/contract)이 `file` 로 옮겨 싣는다 — model 칸은 DOM 낱말 「document」를 쓰지 않는다
 * (app/guards/layers.test.ts DOM_WORD, 그린워싱 ListedDocument 의 이름 바꿈과 같은 까닭).
 */
export interface TranslationBatch {
  batchKey: string;
  /** 묶음 차례를 정한 가장 새 실행의 흐름이 PDF 면 pdf, 아니면 word(TRS3). */
  inputKind: 'word' | 'pdf';
  file: {
    id: number;
    fileName: string;
    uploadedAt: string | null;
    uploadedBy: BatchPerson;
  };
  createdBy: BatchPerson;
  parts: ServerBatchPart[];
  state: BatchState;
  doneParts: number;
  partCount: number;
}
export interface TranslationBatchDetail extends TranslationBatch {
  truncated: boolean;
}
export interface TranslationBatchPage {
  /** 요청의 회사 이름(운영 관리자 = 작업 회사 — sid:MARC-ENT-374). 회사 행이 없으면 ''. */
  companyName: string;
  count: number;
  isNext: boolean;
  truncated: boolean;
  results: TranslationBatch[];
}

// ── 결과 translation.result@1(화면이 읽는 갈래 — 거울은 칸 전부를 본다) ──

export interface ReviewIssue {
  issueType: string;
  severity: string;
  originalSpan: string;
  suggestion: string;
  reason: string;
  source: 'model' | 'glossary_rule';
}
export interface ResultPage {
  pageNum: number;
  translated: string;
  bilingual: string;
  review: {
    status: 'reviewed' | 'parse_failed' | 'call_failed' | 'not_run';
    issues: ReviewIssue[];
    counts: SeverityCounts;
    message: string | null;
  };
}
export interface ResultFragment {
  pageNum: number;
  status: 'translated' | 'error';
  error: string | null;
  remainingKorean: string[];
}
export interface GlossaryMiss {
  pageNum: number;
  termKo: string;
  termEn: string;
  sourceCount: number;
}
export interface ResultVariant {
  label: VariantLabel;
  fragments: ResultFragment[];
  pages: ResultPage[];
  glossaryCheck: GlossaryMiss[];
  autofix: {
    status: 'done' | 'stopped' | 'not_run';
    pages: { pageNum: number; changed: boolean }[];
    notRunReason:
      'disabled' | 'review_stopped' | 'earlier_variant_stopped' | null;
  };
}
export interface ResultWarning {
  code: string;
  pageNum: number | null;
  variant: VariantLabel | null;
}
/** translation.result@1 — done·rejected 판별 유니온(화면이 읽는 칸). */
export type TranslationResult =
  | {
      status: 'done';
      part: ServerPart;
      pageNumbers: number[];
      variants: ResultVariant[];
      warnings: ResultWarning[];
    }
  | {
      status: 'rejected';
      part: ServerPart;
      rejection: {
        kind: ServerRejectionKind;
        pageCount: number | null;
        limit: number | null;
      };
      warnings: ResultWarning[];
    };
