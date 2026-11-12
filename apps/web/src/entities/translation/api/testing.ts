// 시험용 가짜 영문번역 서버(밴드 TRW1a ①). 어댑터·훅·화면·경로 시험이 같이 쓴다(공개 표면이 아니다 — 시험만 직접 가져온다).
// 답의 꼴은 api-py 의 경로(generated/api.d.ts)와 계약(translation.batch@1·digest@1·result@1)을 따른다. 값은 전부 지어낸 것이다(실재 기업명 0).
//   - 거르지 않는다: 받은 요청을 calls 에 적고(method·path·query·body·headers·바이트 수), 서버 규칙대로 답한다.
//   - 경로: POST /documents · POST /documents/{id}/confirm · POST /runs · GET /translation/batches · GET /translation/documents/{d}/batches/{k}
//     (·/archive) · GET /translation/runs/{id}/result · GET /runs/{id} · GET /runs/{id}/files/{name} · POST /translation/glossary/read ·
//     GET /translation/glossary/template. GET /runs/{id} 의 options 는 저장한 그대로(밴드 TRW1b — [이 파트만 다시]가 읽는다).
//   - 서명 PUT 은 `/fake-upload/<문서 id>` 를 내주고, sendUpload 가 그 올림을 uploads 에 적는다. confirm 은 올림이 없으면 409 NOT_UPLOADED.
//     새 문서의 쪽 수는 serverPageCount(기본 null — docx·txt 꼴).
//   - GET /translation/documents/{id}/pages(밴드 TRP6): 없는 문서 404, 있으면 {documentId, pageCount} — pageCount 는
//     translationPageCount(주지 않으면 그 문서의 confirm 값 그대로). 끊김·500·늦춤은 override 로.
//   - POST /runs: module translation · options 의 모르는 열쇠 → 400 INVALID_OPTIONS · Idempotency-Key 가 소문자 UUID 가 아니면 422,
//     본 열쇠·같은 본문이면 앞 실행 201, 본 열쇠·다른 본문 409 IDEMPOTENCY_KEY_REUSED. 올림 전 문서 409 DOCUMENT_NOT_UPLOADED.
//   - 묶음은 실행에서 셈한다(서버 service/actions/batches.py 의 규칙 — 열쇠 batchId 또는 run-<id>, 파트마다 최신·앞 회차, state·doneParts).
//   - archive: 끝난(done·결과 거절 아님) 파트의 자동 수정 Word 가 없으면 409 NO_FINISHED_PARTS, archiveTooLarge 면 409 ARCHIVE_TOO_LARGE,
//     아니면 지어낸 바이트 + X-Archive-Missing(archiveMissing, 기본 0 — null 이면 머리 없음).
// override 에 「메서드 경로」 → 답(차례 목록도 된다. 끊김은 던지는 함수로)을 주면 그 경로는 그 답을 낸다.
// loseAnswer(「메서드 경로」) 는 다음 그 요청을 서버 규칙대로 처리한 뒤 답만 잃는다(끊김 — 서버가 만들고 답을 못 받은 꼴, TRW1b).
// PDF(밴드 TRW6 ① — TRS3 §1 꼴): 실행은 flowId 를 든다(기본 colab, POST /runs 본문의 flowId 를 저장). GET /runs/{id} 는 그 flowId·steps·
//   resultShapes(done 이면 result@1·digest@1, layout 을 지었으면 layout@1 도). GET /documents/{id}(문서 꼴 + hasText) · GET /documents/{id}/file
//   (문서의 pdf 바이트, 없으면 409 OBJECT_MISSING) · GET /translation/runs/{id}/layout(done 이고 layout 있음 200, 없는 실행·layout 없는 끝난 실행 404,
//   끝나지 않음 409 RUN_NOT_DONE). layout 은 advance 의 layout 으로 싣는다. 묶음 조립의 두 칸(TRS3)은 실행 flowId 로 잇는다(밴드 TRW6 ④):
//   parts[].latest.flowId = 그 실행 flowId · inputKind = 묶음 차례를 정한 가장 새 실행의 flowId 가 translation.pdf@ 로 시작하면 pdf(서버 batches.py 와 같음).
// advance(runId, {status, …}) 로 실행 상태를 바꾼다. done 이 되면 결과·요약을 짓는다(outcome·rejectionKind·failedPages·files 로 고름).
import { createApi } from '../../../shared/api/index.ts';
import type { ServerPart, ServerRejectionKind } from '../model/index.ts';
import { UUID_PATTERN } from './ids.ts';
import { createTranslationServerStore } from './server.ts';
import type { TranslationServerDeps } from './server.ts';

export interface FakeTranslationCall {
  method: string;
  path: string;
  query: URLSearchParams;
  /** JSON 본문(JSON 이 아니면 undefined). */
  body: unknown;
  /** 본문 바이트 수. */
  octets: number;
  headers: Headers;
}

type Answer = () => Response | Promise<Response>;

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
export const refusal = (status: number, code: string) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });
/** 답을 받지 못함(끊김). */
export const unreachable = (): Response => {
  throw new TypeError('network down');
};

export interface FakeUser {
  id: number;
  name: string;
}
export interface FakeDocument {
  id: number;
  fileName: string;
  sizeBytes: number;
  status: 'awaiting_upload' | 'uploaded';
  pageCount: number | null;
  createdAt: string;
  uploadedAt: string | null;
  uploadedBy: FakeUser;
  /** 글자 층(PDF probe — 밴드 TRW6). 기본 null. */
  hasText?: boolean | null;
  /** 원본 PDF 바이트(GET /documents/{id}/file — 없으면 409 OBJECT_MISSING). */
  pdf?: Uint8Array;
}
export type FakeStepStatus = 'pending' | 'running' | 'done' | 'failed';
export interface FakeStep {
  step: string;
  status: FakeStepStatus;
  done: number | null;
  total: number | null;
}
export interface FakeRun {
  id: number;
  /** 흐름(밴드 TRW6 — 기본 translation.colab@158). */
  flowId: string;
  documentId: number;
  options: Record<string, unknown>;
  launchKey: string | null;
  status: 'queued' | 'processing' | 'done' | 'failed';
  steps: FakeStep[];
  errorCode: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  createdBy: FakeUser;
  /** 끝난 실행의 요약·결과(advance 가 짓는다). */
  digest: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  /** layout@1(PDF 실행이 끝났을 때 — advance 의 layout). */
  layout: Record<string, unknown> | null;
}

/** 워드 흐름 id(가짜 실행의 기본). */
export const FAKE_COLAB_FLOW = 'translation.colab@158';
/** 이 앞머리의 흐름으로 돈 실행은 PDF 입력(서버 PDF_FLOW_PREFIX — 묶음 inputKind). */
const FAKE_PDF_FLOW_PREFIX = 'translation.pdf@';

/** 흐름 translation.colab@158 의 단계 셋. */
export const FAKE_STEP_NAMES = ['prepare', 'translate', 'report'] as const;

/** 단계 셋: 앞의 doneUntil 개는 done, 그다음 하나는 at, 나머지 pending. */
export function fakeSteps(
  doneUntil: number,
  at: Partial<FakeStep> & { status?: FakeStepStatus } = {},
): FakeStep[] {
  return FAKE_STEP_NAMES.map((step, index) => {
    if (index < doneUntil)
      return { step, status: 'done', done: null, total: null };
    if (index === doneUntil && at.status)
      return {
        step,
        status: at.status,
        done: at.done ?? null,
        total: at.total ?? null,
      };
    return { step, status: 'pending', done: null, total: null };
  });
}

const NOW = '2026-10-19T11:48:00+09:00';
/** 가짜가 끝낸 실행의 끝난 때. */
export const FAKE_FINISHED_AT = '2026-10-19T12:05:00+09:00';
/** 지어낸 Word·zip 바이트(실제 파일이 아니다 — 「PK」 머리만). */
export const FAKE_FILE_BYTES = new Uint8Array([80, 75, 3, 4, 9, 9]);
/** 지어낸 용어집 짝. */
export const FAKE_PAIRS = [
  { ko: '지어낸용어', en: 'Made-up Term' },
  { ko: '가상지표', en: 'Virtual Metric' },
] as const;

const KNOWN_OPTION_KEYS = new Set([
  'batchId',
  'company',
  'part',
  'style',
  'pages',
  'ceoPageLimit',
  'glossary',
  'peerGroupStyle',
  'autofix',
  'retry',
]);

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/** translation.options@1 의 꼴 부분(필수 칸·모르는 열쇠). 틀리면 까닭 글. */
function optionsProblem(options: unknown): string | null {
  if (!isObject(options)) return 'not object';
  const unknownKey = Object.keys(options).find(
    (key) => !KNOWN_OPTION_KEYS.has(key),
  );
  if (unknownKey) return `unknown ${unknownKey}`;
  for (const key of ['company', 'part', 'style', 'pages'])
    if (!(key in options)) return `missing ${key}`;
  if (!('ceoPageLimit' in options)) return 'missing ceoPageLimit';
  if (
    options.batchId !== undefined &&
    !(typeof options.batchId === 'string' && UUID_PATTERN.test(options.batchId))
  )
    return 'batchId';
  return null;
}

export interface AdvanceInput {
  status: FakeRun['status'];
  steps?: FakeStep[];
  errorCode?: string | null;
  /** done 의 요약 outcome(기본 done). rejected 면 rejectionKind 로 거절 결과. */
  outcome?: 'done' | 'partial' | 'rejected';
  rejectionKind?: ServerRejectionKind;
  /** partial 의 못 옮긴 쪽(기본 범위의 첫 쪽). */
  failedPages?: number[];
  /** 지은 Word(기본 셋 다). */
  files?: { bilingual: boolean; qa: boolean; autofix: boolean };
  /** 요약을 남기지 않은 옛 실행(digest null). */
  noDigest?: boolean;
  /** done 이면 실을 layout@1(밴드 TRW6). */
  layout?: Record<string, unknown>;
}

export interface FakeTranslationServerOptions {
  baseUrl?: string;
  currentUser?: FakeUser;
  /** 목록 답의 companyName(기본 '지어낸 회사' — 밴드 TRC1). */
  companyName?: string;
  documents?: FakeDocument[];
  runs?: FakeRun[];
  nextDocumentId?: number;
  nextRunId?: number;
  serverPageCount?: number | null;
  /** 새 문서 confirm 의 hasText(밴드 TRW6 — PDF probe, 기본 null). */
  serverHasText?: boolean | null;
  /** GET …/pages 의 pageCount(밴드 TRP6). 안 주면 그 문서의 confirm 값(serverPageCount)을 그대로. */
  translationPageCount?: number | null;
  /** 용어집 읽기의 답(기본 지어낸 짝 둘). */
  glossaryAnswer?: Json;
  archiveTooLarge?: boolean;
  /** X-Archive-Missing 값(null 이면 머리 없음). */
  archiveMissing?: string | null;
}

export function fakeDocument(
  id: number,
  extra: Partial<FakeDocument> = {},
): FakeDocument {
  return {
    id,
    fileName: `sample_extract_${id}.txt`,
    sizeBytes: 120,
    status: 'uploaded',
    pageCount: null,
    createdAt: NOW,
    uploadedAt: NOW,
    uploadedBy: { id: 7, name: '담당자 가' },
    ...extra,
  };
}

/** 지어낸 옵션(파트·쪽·묶음). */
export function fakeOptions(
  part: ServerPart,
  start: number,
  end: number,
  batchId: string | null,
  extra: Json = {},
): Json {
  return {
    ...(batchId === null ? {} : { batchId }),
    company: {
      name: 'Sample Corp',
      preferredSubject: 'virtual services',
      industryStandards: 'GRI',
    },
    part,
    style: { compareAb: false, single: 'B' },
    pages: { start, end },
    ceoPageLimit: part === 'ceo_message' ? 6 : null,
    glossary: { final: FAKE_PAIRS.map((pair) => ({ ...pair })) },
    ...extra,
  };
}

export function fakeRun(
  id: number,
  documentId: number,
  options: Json,
  extra: Partial<FakeRun> = {},
): FakeRun {
  return {
    id,
    flowId: FAKE_COLAB_FLOW,
    documentId,
    options,
    launchKey: null,
    status: 'queued',
    steps: fakeSteps(0),
    errorCode: null,
    createdAt: NOW,
    startedAt: null,
    finishedAt: null,
    createdBy: { id: 7, name: '담당자 가' },
    digest: null,
    result: null,
    layout: null,
    ...extra,
  };
}

const ZERO = { high: 0, medium: 0, low: 0 };

/** 끝난 실행의 결과·요약(지어낸 — 쪽마다 이슈 하나, 첫 쪽에 용어집 미반영 하나). */
function buildFinished(run: FakeRun, input: AdvanceInput) {
  const options = run.options;
  const part = options.part as ServerPart;
  const pages = options.pages as { start: number; end: number };
  const style = options.style as { compareAb: boolean; single: 'A' | 'B' };
  const settings = {
    part,
    variants: style.compareAb ? ['A', 'B'] : ['single'],
    routes: { translate: 'light-anthropic', review: 'light-anthropic' },
    promptIds: ['translation/section@2'],
    engine: 'colab_158',
    constants: {
      editorialQaMinScore: 96,
      tableBatchSize: 24,
      polishMinChars: 120,
      polishMaxChars: 6000,
      koreanRepairRounds: 2,
      autofixKoreanRepairRounds: 1,
    },
    retry: null,
  };
  const numbers: number[] = [];
  for (let n = pages.start; n <= pages.end; n++) numbers.push(n);
  const document = {
    pageNumbers: numbers,
    duplicatePages: {},
    sourceSha256: '0'.repeat(64),
  };
  const outcome = input.outcome ?? 'done';
  if (outcome === 'rejected') {
    const kind = input.rejectionKind ?? 'no_pages';
    return {
      result: {
        schemaVersion: 'translation.result@1',
        status: 'rejected',
        rejection: {
          kind,
          message: '지어낸 거절 글',
          pageCount: kind === 'ceo_page_limit' ? numbers.length : null,
          limit: kind === 'ceo_page_limit' ? 6 : null,
        },
        settings,
        document,
        variants: [],
        warnings: [],
      },
      digest: {
        schemaVersion: 'translation.digest@1',
        status: 'rejected',
        rejectionKind: kind,
        outcome: 'rejected',
        pageCount: numbers.length,
        failedPages: [],
        variants: [],
        warningCount: 0,
      },
    };
  }
  const failed =
    outcome === 'partial' ? (input.failedPages ?? [pages.start]) : [];
  const files = input.files ?? { bilingual: true, qa: true, autofix: true };
  const labels = settings.variants as ('single' | 'A' | 'B')[];
  const variants = labels.map((label) => ({
    label,
    translatedText: '[PAGE 1]\nMade-up text',
    bilingualText: '[PAGE 1]\nMade-up text',
    fragments: numbers.map((pageNum) => ({
      pageNum,
      status: failed.includes(pageNum) ? 'error' : 'translated',
      error: failed.includes(pageNum) ? 'made-up error' : null,
      editorialQa: null,
      remainingKorean: [],
    })),
    pages: numbers.map((pageNum) => ({
      pageNum,
      translated: `[PAGE ${pageNum}]\nMade-up text`,
      bilingual: `[PAGE ${pageNum}]\nMade-up text`,
      review: {
        status: 'reviewed',
        issues: [
          {
            issueType: 'UNNATURAL',
            severity: 'LOW',
            originalSpan: 'Made-up text',
            suggestion: 'Invented text',
            reason: '지어낸 까닭',
            source: 'model',
          },
        ],
        counts: { high: 0, medium: 0, low: 1 },
        message: null,
      },
    })),
    glossaryCheck: [
      {
        pageNum: pages.start,
        termKo: FAKE_PAIRS[0].ko,
        termEn: FAKE_PAIRS[0].en,
        sourceCount: 1,
      },
    ],
    autofix: {
      status: 'done',
      pages: [],
      translatedText: '[PAGE 1]\nFixed text',
      bilingualText: '[PAGE 1]\nFixed text',
      stop: null,
      notRunReason: null,
    },
  }));
  const fileName = (kind: string, label: string) =>
    `translation-${kind}-${label.toLowerCase()}.docx`;
  return {
    result: {
      schemaVersion: 'translation.result@1',
      status: 'done',
      rejection: null,
      settings,
      document,
      variants,
      warnings: [],
    },
    digest: {
      schemaVersion: 'translation.digest@1',
      status: 'done',
      rejectionKind: null,
      outcome,
      pageCount: numbers.length,
      failedPages: failed,
      variants: labels.map((label) => ({
        label,
        reviewStatus: 'reviewed',
        reviewStoppedAt: null,
        parseFailedPages: 0,
        issueCount: numbers.length,
        issueCounts: { ...ZERO, low: numbers.length },
        glossaryMisses: 1,
        autofixStatus: 'done',
        autofixChangedPages: 0,
        files: {
          bilingual: files.bilingual ? fileName('bilingual', label) : null,
          qa: files.qa ? fileName('qa', label) : null,
          autofix: files.autofix ? fileName('autofix', label) : null,
        },
      })),
      warningCount: 0,
    },
  };
}

export function fakeTranslationServer({
  baseUrl = 'http://test.local/api',
  currentUser = { id: 7, name: '담당자 가' },
  companyName = '지어낸 회사',
  documents = [],
  runs = [],
  nextDocumentId = 12,
  nextRunId = 20,
  serverPageCount = null,
  serverHasText = null,
  translationPageCount,
  glossaryAnswer = {
    ok: true,
    pairs: FAKE_PAIRS.map((pair) => ({ ...pair })),
    rowCount: FAKE_PAIRS.length,
  },
  archiveTooLarge = false,
  archiveMissing = '0',
}: FakeTranslationServerOptions = {}) {
  const calls: FakeTranslationCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  const docs = new Map(documents.map((doc) => [doc.id, { ...doc }]));
  const runMap = new Map(runs.map((run) => [run.id, { ...run }]));
  const uploaded = new Map<number, number>();
  const uploads: { url: string; method: string; size: number }[] = [];
  let documentSeq = nextDocumentId;
  let runSeq = nextRunId;
  const runKeys = new Map<string, { id: number; body: string }>();
  const settings = { archiveTooLarge, archiveMissing, glossaryAnswer };
  /** 「메서드 경로」 → 처리한 뒤 답을 잃을 남은 수. */
  const lost: Record<string, number> = {};

  const basePath = new URL(baseUrl).pathname;
  const pathOf = (url: URL) => url.pathname.slice(basePath.length);

  const documentOut = (doc: FakeDocument) => ({
    id: doc.id,
    fileName: doc.fileName,
    sizeBytes: doc.sizeBytes,
    status: doc.status,
    pageCount: doc.pageCount,
    hasText: doc.hasText ?? null,
    reportYear: null,
    previousDocumentId: null,
    etag: doc.status === 'uploaded' ? '"made-up"' : null,
    createdAt: doc.createdAt,
    uploadedAt: doc.uploadedAt,
  });

  const keyOf = (run: FakeRun) =>
    typeof run.options.batchId === 'string' ?
      run.options.batchId
    : `run-${run.id}`;

  const person = (user: FakeUser) => ({ userId: user.id, name: user.name });

  const latestOf = (run: FakeRun) => {
    const pages = run.options.pages as { start: number; end: number };
    const style = run.options.style as Json;
    const glossary = (run.options.glossary ?? {}) as {
      base?: unknown[];
      final?: unknown[];
    };
    return {
      runId: run.id,
      flowId: run.flowId,
      status: run.status,
      pages: { start: pages.start, end: pages.end },
      style: { compareAb: style.compareAb, single: style.single },
      glossaryCounts: {
        base: glossary.base?.length ?? 0,
        final: glossary.final?.length ?? 0,
      },
      createdAt: run.createdAt,
      startedAt: run.startedAt,
      finishedAt: run.finishedAt,
      failedStep:
        run.status === 'failed' ?
          (run.steps.find((s) => s.status === 'failed')?.step ?? null)
        : null,
      errorCode: run.status === 'failed' ? run.errorCode : null,
      steps: run.steps.map((s) => ({ ...s })),
      digest: run.digest === null ? null : structuredClone(run.digest),
    };
  };

  /** (문서, 열쇠) 묶음들 — 묶음 안 가장 새 실행이 새 것 먼저. */
  const batches = () => {
    const groups = new Map<string, FakeRun[]>();
    for (const run of runMap.values()) {
      const key = `${run.documentId}/${keyOf(run)}`;
      groups.set(key, [...(groups.get(key) ?? []), run]);
    }
    const order: ServerPart[] = ['ceo_message', 'story', 'general'];
    return [...groups.values()]
      .map((group) => {
        const newest = [...group].sort((a, b) => b.id - a.id);
        const parts = order.flatMap((part) => {
          const list = newest.filter((run) => run.options.part === part);
          if (list.length === 0) return [];
          const [latest, ...earlier] = list as [FakeRun, ...FakeRun[]];
          return [
            {
              part,
              latest: latestOf(latest),
              earlier: earlier.map((run) => ({
                runId: run.id,
                status: run.status,
                createdAt: run.createdAt,
                finishedAt: run.finishedAt,
                outcome:
                  run.digest === null ? null : (run.digest.outcome as string),
              })),
              round: earlier.length + 1,
            },
          ];
        });
        const latestRuns = parts.map((p) => p.latest);
        const state =
          (
            latestRuns.some(
              (r) => r.status === 'queued' || r.status === 'processing',
            )
          ) ?
            'active'
          : (
            latestRuns.some(
              (r) =>
                r.status === 'failed' ||
                (r.digest !== null &&
                  (r.digest.outcome === 'rejected' ||
                    r.digest.outcome === 'partial')),
            )
          ) ?
            'failed'
          : 'done';
        const doc = docs.get(newest[0]!.documentId)!;
        return {
          top: newest[0]!.id,
          batch: {
            batchKey: keyOf(newest[0]!),
            inputKind:
              newest[0]!.flowId.startsWith(FAKE_PDF_FLOW_PREFIX) ?
                'pdf'
              : 'word',
            document: {
              id: doc.id,
              fileName: doc.fileName,
              uploadedAt: doc.uploadedAt,
              uploadedBy: person(doc.uploadedBy),
            },
            createdBy: person(newest[0]!.createdBy),
            parts,
            state,
            doneParts: latestRuns.filter((r) => r.status === 'done').length,
            partCount: parts.length,
          },
          uploaderId: doc.uploadedBy.id,
        };
      })
      .sort((a, b) => b.top - a.top);
  };

  const findBatch = (documentId: number, key: string) =>
    batches().find(
      (b) => b.batch.document.id === documentId && b.batch.batchKey === key,
    );

  function answer(
    method: string,
    path: string,
    body: unknown,
    query: URLSearchParams,
    headers: Headers,
  ): Response {
    if (method === 'POST' && path === '/documents') {
      const b = body as { fileName: string; sizeBytes: number };
      const id = documentSeq++;
      const doc: FakeDocument = {
        id,
        fileName: b.fileName,
        sizeBytes: b.sizeBytes,
        status: 'awaiting_upload',
        pageCount: null,
        createdAt: NOW,
        uploadedAt: null,
        uploadedBy: { ...currentUser },
      };
      docs.set(id, doc);
      return json(201, {
        document: documentOut(doc),
        upload: {
          url: `${baseUrl}/fake-upload/${id}`,
          method: 'PUT',
          headers: {},
          expiresAt: NOW,
        },
      });
    }
    let match = /^\/documents\/(\d+)\/confirm$/.exec(path);
    if (method === 'POST' && match) {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(404, 'NOT_FOUND');
      if (!uploaded.has(doc.id)) return refusal(409, 'NOT_UPLOADED');
      doc.status = 'uploaded';
      doc.uploadedAt = NOW;
      doc.pageCount = serverPageCount;
      doc.hasText = serverHasText;
      return json(200, { document: documentOut(doc) });
    }
    match = /^\/translation\/documents\/(\d+)\/pages$/.exec(path);
    if (method === 'GET' && match) {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(404, 'NOT_FOUND');
      return json(200, {
        documentId: doc.id,
        pageCount:
          translationPageCount === undefined ?
            doc.pageCount
          : translationPageCount,
      });
    }
    if (method === 'POST' && path === '/runs') {
      const b = body as Json;
      const key = headers.get('Idempotency-Key');
      if (key !== null && !UUID_PATTERN.test(key))
        return refusal(422, 'VALIDATION_ERROR');
      const text = JSON.stringify(body);
      if (key !== null) {
        const seen = runKeys.get(key);
        if (seen && seen.body === text)
          return json(201, { id: seen.id, status: 'queued' });
        if (seen) return refusal(409, 'IDEMPOTENCY_KEY_REUSED');
      }
      if (b.module !== 'translation') return refusal(400, 'INVALID_OPTIONS');
      if (optionsProblem(b.options) !== null)
        return refusal(400, 'INVALID_OPTIONS');
      const doc = docs.get(b.documentId as number);
      if (!doc) return refusal(404, 'NOT_FOUND');
      if (doc.status !== 'uploaded')
        return refusal(409, 'DOCUMENT_NOT_UPLOADED');
      const id = runSeq++;
      runMap.set(
        id,
        fakeRun(id, doc.id, b.options as Json, {
          flowId: typeof b.flowId === 'string' ? b.flowId : FAKE_COLAB_FLOW,
          launchKey: (b.launchKey as string | undefined) ?? null,
          createdBy: { ...currentUser },
        }),
      );
      if (key !== null) runKeys.set(key, { id, body: text });
      return json(201, { id, status: 'queued' });
    }
    if (method === 'GET' && path === '/translation/batches') {
      let list = batches();
      const state = query.get('state');
      if (state !== null) list = list.filter((b) => b.batch.state === state);
      if (query.get('mine') === 'true')
        list = list.filter((b) => b.uploaderId === currentUser.id);
      const limit = Number(query.get('limit') ?? '20');
      const offset = Number(query.get('offset') ?? '0');
      return json(200, {
        companyName,
        count: list.length,
        isNext: offset + limit < list.length,
        truncated: false,
        results: list.slice(offset, offset + limit).map((b) => b.batch),
      });
    }
    match =
      /^\/translation\/documents\/(\d+)\/batches\/([^/]+)(\/archive)?$/.exec(
        path,
      );
    if (method === 'GET' && match) {
      const found = findBatch(Number(match[1]), decodeURIComponent(match[2]!));
      if (!found) return refusal(404, 'NOT_FOUND');
      if (match[3] === undefined)
        return json(200, { ...found.batch, truncated: false });
      const withFiles = found.batch.parts.filter((part) => {
        const digest = part.latest.digest as {
          status: string;
          variants: { files: { autofix: string | null } }[];
        } | null;
        return (
          part.latest.status === 'done' &&
          digest !== null &&
          digest.status === 'done' &&
          digest.variants.some((v) => v.files.autofix !== null)
        );
      });
      if (withFiles.length === 0) return refusal(409, 'NO_FINISHED_PARTS');
      if (settings.archiveTooLarge) return refusal(409, 'ARCHIVE_TOO_LARGE');
      const name = `translation-${found.batch.document.id}-${found.batch.batchKey.slice(0, 8)}.zip`;
      return new Response(FAKE_FILE_BYTES, {
        status: 200,
        headers: {
          'Content-Type': 'application/zip',
          'Content-Disposition': `attachment; filename="${name}"`,
          ...(settings.archiveMissing === null ?
            {}
          : { 'X-Archive-Missing': settings.archiveMissing }),
        },
      });
    }
    match = /^\/translation\/runs\/(\d+)\/result$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      if (!run) return refusal(404, 'NOT_FOUND');
      if (run.status !== 'done' || run.result === null)
        return refusal(409, 'RUN_NOT_DONE');
      return json(200, run.result);
    }
    match = /^\/runs\/(\d+)$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      if (!run) return refusal(404, 'NOT_FOUND');
      // RunOut(generated/api.d.ts) 가운데 영문번역이 읽는 칸과 몇 칸. options 는 저장한 그대로.
      return json(200, {
        id: run.id,
        module: 'translation',
        flowId: run.flowId,
        documentId: run.documentId,
        options: structuredClone(run.options),
        status: run.status,
        errorCode: run.errorCode,
        errorMessage: null,
        failedStep:
          run.status === 'failed' ?
            (run.steps.find((s) => s.status === 'failed')?.step ?? null)
          : null,
        files: [],
        steps: run.steps.map((step) => ({ ...step })),
        resultShapes:
          run.status === 'done' && run.result !== null ?
            [
              'translation.result@1',
              'translation.digest@1',
              ...(run.layout === null ? [] : ['translation.layout@1']),
            ]
          : [],
        createdAt: run.createdAt,
        startedAt: run.startedAt,
        finishedAt: run.finishedAt,
      });
    }
    match = /^\/translation\/runs\/(\d+)\/layout$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      if (!run) return refusal(404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(409, 'RUN_NOT_DONE');
      if (run.layout === null) return refusal(404, 'NOT_FOUND');
      return json(200, run.layout);
    }
    match = /^\/documents\/(\d+)(\/file)?$/.exec(path);
    if (method === 'GET' && match) {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(404, 'NOT_FOUND');
      if (match[2] === undefined)
        return json(200, { document: documentOut(doc), jobs: [] });
      if (doc.status !== 'uploaded') return refusal(409, 'NOT_UPLOADED');
      if (doc.pdf === undefined) return refusal(409, 'OBJECT_MISSING');
      return new Response(doc.pdf, {
        status: 200,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `attachment; filename="${doc.fileName}"`,
        },
      });
    }
    match = /^\/runs\/(\d+)\/files\/([^/]+)$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      const name = decodeURIComponent(match[2]!);
      const names = (
        (run?.digest?.variants ?? []) as {
          files: Record<string, string | null>;
        }[]
      ).flatMap((v) => Object.values(v.files));
      if (!run || !names.includes(name)) return refusal(404, 'NOT_FOUND');
      return new Response(FAKE_FILE_BYTES, {
        status: 200,
        headers: {
          'Content-Type': 'application/octet-stream',
          'Content-Disposition': `attachment; filename="${name}"`,
        },
      });
    }
    if (method === 'POST' && path === '/translation/glossary/read')
      return json(200, settings.glossaryAnswer);
    if (method === 'GET' && path === '/translation/glossary/template')
      return new Response(FAKE_FILE_BYTES, {
        status: 200,
        headers: {
          'Content-Type':
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition':
            'attachment; filename="translation-glossary-template.xlsx"',
        },
      });
    throw new Error(`fake translation server: no route ${method} ${path}`);
  }

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(url);
    const bytes = new Uint8Array(await request.clone().arrayBuffer());
    let body: unknown;
    try {
      body =
        bytes.length === 0 ?
          undefined
        : JSON.parse(new TextDecoder().decode(bytes));
    } catch {
      body = undefined;
    }
    calls.push({
      method: request.method,
      path,
      query: url.searchParams,
      body,
      octets: bytes.length,
      headers: new Headers(request.headers),
    });
    const key = `${request.method} ${path}`;
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return next();
    } else if (replaced) return replaced();
    const answered = answer(
      request.method,
      path,
      body,
      url.searchParams,
      new Headers(request.headers),
    );
    if ((lost[key] ?? 0) > 0) {
      lost[key] = lost[key]! - 1;
      throw new TypeError('network down after the server acted');
    }
    return answered;
  };

  /** 서명 PUT(어댑터에 넣는 sendUpload). 주소가 가짜 것이 아니면 거절. */
  const sendUpload = async (url: string, method: string, file: File) => {
    const match = /\/fake-upload\/(\d+)$/.exec(url);
    if (!match) throw new Error('bad upload url');
    uploads.push({ url, method, size: file.size });
    uploaded.set(Number(match[1]), file.size);
  };

  const advance = (runId: number, input: AdvanceInput) => {
    const run = runMap.get(runId);
    if (!run) throw new Error(`no run ${runId}`);
    run.status = input.status;
    if (input.errorCode !== undefined) run.errorCode = input.errorCode;
    if (input.status !== 'queued' && run.startedAt === null)
      run.startedAt = NOW;
    if (input.steps) run.steps = input.steps;
    else if (input.status === 'done') run.steps = fakeSteps(3);
    else if (input.status === 'processing')
      run.steps = fakeSteps(1, { status: 'running', done: 0, total: 3 });
    else if (input.status === 'failed')
      run.steps = fakeSteps(1, { status: 'failed' });
    if (input.status === 'done' || input.status === 'failed')
      run.finishedAt ??= FAKE_FINISHED_AT;
    if (input.status === 'done' && !input.noDigest) {
      const { result, digest } = buildFinished(run, input);
      run.result = result;
      run.digest = digest;
      if (input.layout !== undefined)
        run.layout = structuredClone(input.layout);
    }
  };

  return {
    calls,
    override,
    uploads,
    documents: docs,
    runs: runMap,
    settings,
    send,
    sendUpload,
    advance,
    /** 다음 그 요청(「POST /runs」)을 처리한 뒤 답만 잃는다. */
    loseAnswer: (key: string, times = 1) => {
      lost[key] = (lost[key] ?? 0) + times;
    },
    /** 그 경로의 부른 수. */
    count: (key: string) =>
      calls.filter((call) => `${call.method} ${call.path}` === key).length,
    /** POST /runs 의 본문들. */
    runBodies: () =>
      calls
        .filter((call) => call.method === 'POST' && call.path === '/runs')
        .map((call) => call.body as Json),
  };
}

export type FakeTranslationServer = ReturnType<typeof fakeTranslationServer>;

/** 진짜 실어댑터 + 이 가짜 서버. */
export function serverStoreOf(
  server: FakeTranslationServer,
  deps: Partial<Omit<TranslationServerDeps, 'api'>> = {},
  baseUrl = 'http://test.local/api',
) {
  return createTranslationServerStore({
    api: createApi({ baseUrl, fetch: server.send }),
    sendUpload: server.sendUpload,
    ...deps,
  });
}

/** TRS3 §1-2 예 꼴의 layout@1(done, 한 쪽 — 지어낸 글). 시험이 고쳐 쓰도록 새 객체를 돌려준다. */
export function fakeLayout(page = 12): Record<string, unknown> {
  return {
    schemaVersion: 'translation.layout@1',
    status: 'done',
    sourceSha256: '9'.repeat(64),
    source: {
      pdfSha256: 'a'.repeat(64),
      pageCount: 64,
      parser: { name: 'docparse', version: '0.4.0', layout: 2 },
      adapter: 'pdf_tags@1',
    },
    pages: [{ page, width: 595.28, height: 841.89, textLayer: 'present' }],
    units: [
      {
        tag: 'BLOCK 1',
        page,
        kind: 'block',
        members: [
          {
            id: `p${page}-b1`,
            key: 'k-3f9a',
            kind: 'heading',
            bbox: [56.7, 72.0, 320.4, 94.1],
            source: '기후 대응 전략',
          },
          {
            id: `p${page}-b2`,
            key: 'k-77c1',
            kind: 'paragraph',
            bbox: [56.7, 100.2, 538.6, 180.9],
            source: '지어낸 회사는 2030년까지 배출을 줄인다',
          },
        ],
      },
      {
        tag: 'TABLE 1',
        page,
        kind: 'table',
        members: [
          {
            id: `p${page}-t1`,
            key: 'k-0b21',
            kind: 'table',
            bbox: [56.7, 200.0, 538.6, 320.0],
            source: '| 구분 | 2025 |\n| --- | --- |\n| 배출량 | 1,200 |',
          },
        ],
        cells: [
          {
            row: 0,
            col: 0,
            id: `p${page}-t1:r0c0`,
            bbox: [60.0, 204.0, 120.0, 216.0],
            source: '구분',
          },
        ],
        rows: [0, 1],
      },
      {
        tag: null,
        page,
        kind: 'footer',
        members: [
          {
            id: `p${page}-b9`,
            key: 'k-9e00',
            kind: 'paragraph',
            bbox: [56.7, 800.0, 538.6, 812.0],
            source: '2026 지속가능경영보고서 12',
          },
        ],
      },
    ],
    variants: [
      {
        label: 'A',
        stage: 'autofix',
        units: [
          {
            tag: 'BLOCK 1',
            page,
            level: 'block',
            translations: ['Climate Strategy', 'By 2030, Made-up Co. cuts'],
          },
          {
            tag: 'TABLE 1',
            page,
            level: 'cell',
            translations: null,
            cells: [{ row: 0, col: 0, text: 'Category' }],
          },
          { tag: null, page, level: 'source_only', translations: null },
        ],
        unplaced: [],
      },
    ],
    skipped: { emptyTables: [], imageOnlyPages: [] },
    warnings: [],
  };
}

/** 거절된 layout@1(파서 앞 거절 — variants 빈 목록). */
export function fakeRejectedLayout(): Record<string, unknown> {
  return {
    ...fakeLayout(),
    status: 'rejected',
    source: {
      pdfSha256: 'a'.repeat(64),
      pageCount: null,
      parser: null,
      adapter: 'pdf_tags@1',
    },
    pages: [],
    units: [],
    variants: [],
  };
}
