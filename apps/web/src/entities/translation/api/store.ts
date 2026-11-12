// 영문번역 저장소 꼴(밴드 TRW1a ①). 화면·훅은 이 꼴만 안다 — 기본 저장소는 실어댑터(server.ts), 시험은 가짜 서버(testing.ts)를 그 앞에 둔다.
// 목 저장소는 없다(발주서 §1-3 — CreateTranslationStore 는 시험 주입 자리로만).
// 거절은 TranslationStoreError(kind): not_found(없음·꼴 밖 id) · not_done(결과 409 RUN_NOT_DONE) · rejected(서버 거절·꼴 틀림) ·
//   unreachable(답을 받지 못함 — 실행을 만들었는지 모른다, 그린워싱 GR1 꼴). 서버 message 는 싣지 않는다.
import type {
  BatchState,
  PartKey,
  Range,
  TranslationBatchDetail,
  TranslationBatchPage,
  TranslationLayout,
  TranslationResult,
} from '../model/index.ts';
import type { GlossaryPair, GlossaryRead } from './contract/index.ts';

export type StoreErrorKind =
  'not_found' | 'not_done' | 'rejected' | 'unreachable';

export class TranslationStoreError extends Error {
  readonly kind: StoreErrorKind;
  constructor(kind: StoreErrorKind, message: string) {
    super(message);
    this.name = 'TranslationStoreError';
    this.kind = kind;
  }
}

/** 거절의 갈래(저장소 거절이 아닌 것은 rejected). */
export function storeErrorKind(error: unknown): StoreErrorKind {
  return error instanceof TranslationStoreError ? error.kind : 'rejected';
}

/** 올린 문서(confirm 답 + 쪽 수는 GET …/pages 의 [PAGE n] 최댓값 — 못 세거나 못 받으면 null·confirm 값, 밴드 TRP6). */
export interface UploadedDocument {
  documentId: string;
  fileName: string;
  sizeBytes: number;
  uploadedAt: string | null;
  pageCount: number | null;
}

/**
 * 올린 PDF(밴드 TRW6 ① W4): confirm 답 그대로 — 쪽 수·글자 층은 core 의 pdf probe(GET …/pages 는 부르지 않는다).
 * hasText: 앞 몇 쪽에 글자 층이 있는가(모르면 null).
 */
export interface UploadedPdf extends UploadedDocument {
  hasText: boolean | null;
}

/** 이미 올린 문서(GET /documents/{id} — 목록에서 다시 들어올 때의 쪽 수 원천). */
export interface DocumentInfo {
  documentId: string;
  fileName: string;
  pageCount: number | null;
  hasText: boolean | null;
}

/** 실행 하나의 정보(GET /runs/{id}): 흐름 · 결과 꼴 · 문서 · 파트(options.part — [← 결과 요약] 이 고를 탭). */
export interface RunInfo {
  runId: string;
  flowId: string;
  resultShapes: readonly string[];
  documentId: string;
  part: PartKey | null;
}

/** 원본 PDF 바이트(GET /documents/{id}/file): 받음 · 없음(404·409) · 그 밖 실패. */
export type RunPdf =
  { kind: 'ready'; file: File } | { kind: 'missing' } | { kind: 'failed' };

/** [번역 시작] 한 번의 입력. 파트는 쪽을 넣은 것만(빈 파트는 싣지 않는다). */
export interface StartInput {
  documentId: string;
  parts: readonly { part: PartKey; range: Range }[];
  company: {
    name: string;
    preferredSubject: string;
    industryStandards: string;
  };
  style: { compareAb: boolean; single: 'A' | 'B' };
  /** base 는 평가용어집(없으면 싣지 않음), final 은 고객사 용어집(읽은 짝 그대로). */
  glossary: { base?: readonly GlossaryPair[]; final: readonly GlossaryPair[] };
  /** 참고 문체 글(켰을 때만 — 끄면 null). */
  peerGroupStyle: string | null;
  /** 흐름(PDF 만 — 밴드 TRW6 W5). 없으면 POST /runs 본문에 flowId 키가 없다(워드 BASE 그대로). */
  flowId?: 'translation.pdf@158';
}

/**
 * [번역 시작]의 끝: started = 하나 이상 만들어짐(못 만든 파트는 failed — 감독 판단 4 ⓐ) ·
 * too_long = 옵션 바이트가 상한을 넘어 아무것도 보내지 않음(TR-02a). 하나도 못 만들면 TranslationStoreError.
 */
export type StartResult =
  | {
      kind: 'started';
      documentId: string;
      batchKey: string;
      runs: readonly { part: PartKey; runId: string }[];
      failed: readonly PartKey[];
    }
  | { kind: 'too_long' };

/** [이 파트만 다시](결정 sid:MARC-ENT-393) 한 번의 입력: 묶음(문서·열쇠)의 그 파트 최신 실행 runId 의 옵션을 그대로 다시 보낸다. */
export interface RetryPartInput {
  documentId: string;
  batchKey: string;
  part: PartKey;
  runId: string;
}

export interface BatchQuery {
  state?: BatchState;
  mine: boolean;
  offset: number;
}

export interface FileDownload {
  blob: Blob;
  fileName: string;
}

/** [모두 받기]의 끝: zip(빠진 항목 수) · 409 ARCHIVE_TOO_LARGE · 409 NO_FINISHED_PARTS. */
export type ArchiveResult =
  | { kind: 'file'; blob: Blob; fileName: string; missing: number }
  | { kind: 'too_large' }
  | { kind: 'nothing' };

export interface TranslationStore {
  uploadDocument(file: File): Promise<UploadedDocument>;
  /** PDF 올림(밴드 TRW6 W4 — pages 경로를 부르지 않는다). */
  uploadPdf(file: File): Promise<UploadedPdf>;
  getDocument(documentId: string): Promise<DocumentInfo>;
  getRunInfo(runId: string): Promise<RunInfo>;
  /** layout@1. 404 → not_found, 409 RUN_NOT_DONE → not_done. */
  getLayout(runId: string): Promise<TranslationLayout>;
  /** 원본 PDF(문서 id 마다 한 번 받고 다음부터 같은 답 — 감사 줄 중복 0). */
  openRunPdf(documentId: string): Promise<RunPdf>;
  readGlossary(file: File): Promise<GlossaryRead>;
  glossaryTemplate(): Promise<FileDownload>;
  startBatch(input: StartInput): Promise<StartResult>;
  /** 같은 옵션·같은 batchId 로 새 실행 하나(launchKey·Idempotency-Key 만 새로). 거절은 TranslationStoreError. */
  retryPart(input: RetryPartInput): Promise<{ runId: string }>;
  listBatches(query: BatchQuery): Promise<TranslationBatchPage>;
  getBatch(
    documentId: string,
    batchKey: string,
  ): Promise<TranslationBatchDetail>;
  /**
   * 묶음 폴링: 곧바로 한 번, 답을 받은 뒤 pollMs 뒤 다음(겹침 없음), state 가 active 가 아니면 멈춤, 404 → onMissing 한 번.
   * 실패는 처음 읽기면 곧바로, 값을 받은 뒤면 연속 3번째에 onFailed 한 번(그린워싱 subscribeRun 규칙). 해제 뒤 온 답은 버린다.
   */
  subscribeBatch(
    documentId: string,
    batchKey: string,
    listener: (batch: TranslationBatchDetail) => void,
    onMissing?: () => void,
    onFailed?: () => void,
  ): () => void;
  getResult(runId: string): Promise<TranslationResult>;
  runFile(runId: string, name: string): Promise<FileDownload>;
  archive(documentId: string, batchKey: string): Promise<ArchiveResult>;
}
