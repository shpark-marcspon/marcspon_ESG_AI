// 그린워싱 실어댑터(밴드 GW1R ①). GreenwashStore 꼴을 서버 경로로 맞춘다 — 짝짓기 표는 band-handoffs/archive/G1b-order.md §2-0.
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. 전역 통신·창·보관소는 모른다:
//   서명 주소로 올리는 PUT(sendUpload)과 PDF 쪽 세기(countPages)는 app/ 이 넣는다. 서명 PUT 에는 Authorization 을 싣지 않는다(app 의 몫).
// 경로:
//   createDocument  countPages(file) → POST /documents {fileName, sizeBytes} → sendUpload(upload.url, upload.method, file) → POST /documents/{id}/confirm.
//                   쪽 수·글자 층은 서버 값(X1b-2a 뒤)이 null 이 아니면 그것, null 이면 이 탭에서 센 쪽 수·true(Q2·Q3). 못 세면 올리지 않고 거절.
//   createRun       보고연도가 있으면 먼저 PATCH /documents/{id} 본문 정확히 {reportYear} → 답(DocumentOut)의 id·reportYear 가 보낸 값과 같은지 본다
//                   (밴드 GW2R ③ Q8). PATCH 가 거절·끊김·꼴 틀림이면 실행을 만들지 않고 거절. null 이면 PATCH 하지 않는다.
//                   그 뒤 POST /runs {module:'greenwash', documentId, options:{parts:{ceo,company,climate}, extraTerms?}}(실행 옵션에 연도를 싣지 않는다).
//                   수정본 대상이 있으면 거절(v115 — 화면에 칸이 없다). flowId·resumeFromRunId·companyId 는 싣지 않는다.
//   getRun          GET /runs/{id} → RunSnapshot(checkedPages = parts 합집합 수, progress = progressFromServer, pageCount·rerunOf null, errorCode·finishedAt 그대로).
//   subscribeRun    GET /runs/{id} 폴링: 곧바로 한 번, 응답을 받은 뒤 pollMs 뒤 다음(겹침 없음), done·failed 에서 멈춤, 404 → onMissing 한 번.
//                   실패는 처음 읽기면 곧바로, 값을 받은 뒤면 연속 3번째에 onFailed 한 번 부르고 멈춘다(성공하면 셈 0). 해제 뒤 온 응답은 버린다.
//   rerun           GET /runs/{id}(failed 가 아니면 거절) → POST /runs 같은 documentId·options(처음부터 — resumeFromRunId 를 쓰지 않는다, store.ts).
//   POST /runs 는 열쇠를 받으면 머리 Idempotency-Key(그대로, 밴드 GR2)를 싣는다(안 받으면 머리 없음). 409 IDEMPOTENCY_KEY_REUSED(같은 열쇠·다른 본문)는
//                   createRun 에서만 key_reused(sid:MARC-ISSUE-312 — 화면이 목록 확인으로 이끈다), rerun 은 rejected 그대로.
//   본문 launchKey(서버 LK1, 밴드 GP6)는 그 열쇠와 같은 값, 열쇠가 없으면 새로 짓는다(다시 하기는 누름마다 새 열쇠라 새 값).
//   listCheckRows   GET /greenwash/checks(greenwash.checks@1) → CheckRowsSource. 꼴은 손으로 검사한다(틀리면 거절 — 목으로 메우지 않는다).
//   listDocuments   같은 checks 의 documents(수정본 대상 — 화면이 X1b-2 잇기 전까지 그 칸을 숨겨 실제로는 부르지 않는다).
//   getDocument     GET /documents/{id}. getResult·getReview·putReview 는 GET/PUT /greenwash/runs/{id}/result·review 의 JSON 그대로(거울은 훅).
//   openDocumentPdf 이 탭에서 올린 File, 없으면 GET /documents/{id}/file(parseAs 'blob' — 운영 관리자·다른 사용자·새로 고침의 미리보기, 밴드 GR3·
//                   리허설 sid:MARC-TICK-257). 받은 File 은 이 탭에 둔다(다시 열어도 내려받기 감사 줄을 늘리지 않는다 — forget 이 비움).
//                   거절·끊김·꼴 틀림은 null(화면의 「미리보기를 열 수 없어요」 갈래 그대로).
//   getReport       GET /greenwash/runs/{id}/report(확정본이면 ?confirmed=true, 아니면 쿼리 없음 — 서버 기본 false), parseAs 'blob'(밴드 GW2R ③ Q9).
//                   답이 Blob 꼴이 아니면 거절. 파일 이름은 Content-Disposition(없으면 greenwash-<runId>.xlsx). 파일 저장(DOM)은 ui 층이 한다.
// id 는 글자다: 나갈 때 `^[1-9][0-9]*$` 만 숫자로, 아니면 요청 없이 not_found(구독이면 onMissing). 들어올 때 String(id).
// 거절은 StoreError: 서버 code 는 serverCodes 표(409 RUN_NOT_DONE 은 결과·검토 읽기에서 not_found), 연결 끊김·꼴 틀림은 rejected.
//   다만 POST /runs 의 끊김(ApiFailure.kind 가 api 가 아님)은 unreachable — 실행이 만들어졌는지 모른다(밴드 GR1, sid:MARC-ISSUE-225).
// 서버 message 는 화면에 보이지 않는다. 어느 요청에도 companyId 를 싣지 않는다(MARC-ENT-251).
import { asFailure } from '../../../shared/api/index.ts';
import type { Api, ApiFailure } from '../../../shared/api/index.ts';
import {
  PART_KEYS,
  fallbackReportName,
  fileNameFromDisposition,
  progressFromServer,
  totalPages,
} from '../model/index.ts';
import type {
  CheckRowsSource,
  LevelCounts,
  ListedDocument,
  ListedRun,
  PartPages,
  ServerRunStatus,
  ServerStep,
} from '../model/index.ts';
import { newIdempotencyKey } from './idempotency.ts';
import { storeErrorKindOf } from './serverCodes.ts';
import { StoreError } from './store.ts';
import type {
  DocumentInfo,
  ExistingDocument,
  GreenwashStore,
  ReportFile,
  RunSnapshot,
  StoreErrorKind,
} from './store.ts';

/** 폴링 간격 기본(ms). */
export const RUN_POLL_MS = 2000;
/** 값을 받은 뒤 이만큼 잇달아 실패하면 onFailed. */
export const RUN_POLL_FAILURES = 3;

export interface GreenwashServerDeps {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
  /** 서명 주소로 파일 본문을 올린다(app 이 넣는다 — Authorization 을 싣지 않는다). 2xx 가 아니거나 끊기면 거절(413 은 StoreError too_large). */
  sendUpload(url: string, method: string, file: File): Promise<void>;
  /** PDF 의 쪽 수를 센다(app 이 넣는다 — pdf.js). 못 세면 거절. */
  countPages(file: File): Promise<number>;
  /** 폴링 간격(ms). 기본 RUN_POLL_MS. */
  pollMs?: number;
}

export interface GreenwashServerControl {
  store: GreenwashStore;
  /** 이 탭의 기억(올린 File·센 쪽 수)을 비운다(로그아웃 때 — Q11). */
  forget(): void;
}

const RUN_STATUSES: readonly string[] = [
  'queued',
  'processing',
  'done',
  'failed',
];
const STEP_STATUSES: readonly string[] = [
  'pending',
  'running',
  'done',
  'failed',
];
const REVIEW_STATES: readonly string[] = ['pending', 'in_review', 'confirmed'];

type Json = Record<string, unknown>;

const isObject = (value: unknown): value is Json =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const isInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value);
const nullable = (value: unknown, type: 'string' | 'number') =>
  value === null || typeof value === type;
const nullableInt = (value: unknown) => value === null || isInt(value);

/** 나가는 id: 양의 정수 글자만 숫자로. 아니면 null(요청하지 않는다). */
export function serverId(id: string): number | null {
  if (!/^[1-9][0-9]*$/.test(id)) return null;
  const value = Number(id);
  return Number.isSafeInteger(value) ? value : null;
}

function isStep(value: unknown): value is ServerStep {
  return (
    isObject(value) &&
    typeof value.step === 'string' &&
    typeof value.status === 'string' &&
    STEP_STATUSES.includes(value.status) &&
    nullableInt(value.done) &&
    nullableInt(value.total)
  );
}
const isSteps = (value: unknown): value is ServerStep[] =>
  Array.isArray(value) && value.every(isStep);
const isStatus = (value: unknown): value is ServerRunStatus =>
  typeof value === 'string' && RUN_STATUSES.includes(value);

/** greenwash.options@1 의 parts(셋 다 있고 쪽은 정수). */
function partsOf(options: unknown): PartPages | null {
  if (!isObject(options) || !isObject(options.parts)) return null;
  const parts = options.parts;
  const ok = PART_KEYS.every(
    (key) =>
      Array.isArray(parts[key]) && (parts[key] as unknown[]).every(isInt),
  );
  if (!ok) return null;
  return {
    ceo: parts.ceo as number[],
    company: parts.company as number[],
    climate: parts.climate as number[],
  };
}

/** RunOut 가운데 쓰는 칸. */
interface ServerRun {
  id: number;
  documentId: number;
  module: string;
  status: ServerRunStatus;
  steps: ServerStep[];
  options: Json;
  parts: PartPages;
  startedAt: string | null;
  finishedAt: string | null;
  errorCode: string | null;
}

function serverRunOf(value: unknown): ServerRun | null {
  if (!isObject(value)) return null;
  const parts = partsOf(value.options);
  if (
    !isInt(value.id) ||
    !isInt(value.documentId) ||
    typeof value.module !== 'string' ||
    !isStatus(value.status) ||
    !isSteps(value.steps) ||
    !isObject(value.options) ||
    parts === null ||
    !nullable(value.startedAt, 'string') ||
    !nullable(value.finishedAt, 'string') ||
    !nullable(value.errorCode, 'string')
  )
    return null;
  return {
    id: value.id,
    documentId: value.documentId,
    module: value.module,
    status: value.status,
    steps: value.steps,
    options: value.options,
    parts,
    startedAt: value.startedAt as string | null,
    finishedAt: value.finishedAt as string | null,
    errorCode: value.errorCode as string | null,
  };
}

/** RunOut → 화면 스냅샷. */
export function snapshotOf(run: ServerRun): RunSnapshot {
  const checkedPages = totalPages(run.parts);
  return {
    runId: String(run.id),
    documentId: String(run.documentId),
    startedAt: run.startedAt,
    finishedAt: run.finishedAt,
    pageCount: null,
    checkedPages,
    progress: progressFromServer(run.status, run.steps, checkedPages),
    rerunOf: null,
    errorCode: run.errorCode,
  };
}

const isLevelCounts = (value: unknown): value is LevelCounts =>
  isObject(value) && isInt(value.High) && isInt(value.Mid) && isInt(value.Low);

function reviewOf(value: unknown): ListedRun['review'] | undefined {
  if (value === null) return null;
  if (!isObject(value)) return undefined;
  const by = value.confirmedBy;
  if (
    typeof value.state !== 'string' ||
    !REVIEW_STATES.includes(value.state) ||
    !isInt(value.reviewed) ||
    !isInt(value.total) ||
    !nullable(value.confirmedAt, 'string') ||
    !(by === null || (isObject(by) && typeof by.name === 'string'))
  )
    return undefined;
  return {
    state: value.state as NonNullable<ListedRun['review']>['state'],
    reviewed: value.reviewed,
    total: value.total,
    confirmedAt: value.confirmedAt as string | null,
    // 목록은 이름만 쓴다(id 는 싣지 않는다 — 옛 111 (3)).
    confirmedBy: by === null ? null : (by as { name: string }).name,
  };
}

function listedRunOf(value: unknown): ListedRun | null {
  if (!isObject(value)) return null;
  const review = reviewOf(value.review);
  if (
    !isInt(value.runId) ||
    !isInt(value.documentId) ||
    typeof value.createdAt !== 'string' ||
    !isStatus(value.status) ||
    !isSteps(value.steps) ||
    !isInt(value.checkedPages) ||
    !(value.levelCounts === null || isLevelCounts(value.levelCounts)) ||
    review === undefined ||
    // G1e 가 더하는 칸(Q8): 없어도 되고, 있으면 글자나 null.
    !(value.errorCode === undefined || nullable(value.errorCode, 'string')) ||
    // GCB1 이 더하는 칸: 없어도 되고(옛 서버), 있으면 글자나 null.
    !(value.finishedAt === undefined || nullable(value.finishedAt, 'string'))
  )
    return null;
  return {
    runId: String(value.runId),
    documentId: String(value.documentId),
    createdAt: value.createdAt,
    finishedAt: (value.finishedAt as string | null | undefined) ?? null,
    progress: progressFromServer(value.status, value.steps, value.checkedPages),
    levelCounts: value.levelCounts === null ? null : { ...value.levelCounts },
    review,
    errorCode: (value.errorCode as string | null | undefined) ?? null,
  };
}

function listedDocumentOf(
  value: unknown,
  runs: readonly ListedRun[],
): ListedDocument | null {
  if (!isObject(value)) return null;
  const by = value.uploadedBy;
  if (
    !isInt(value.documentId) ||
    typeof value.fileName !== 'string' ||
    !nullableInt(value.reportYear) ||
    !nullableInt(value.previousDocumentId) ||
    !nullableInt(value.pageCount) ||
    !nullable(value.uploadedAt, 'string') ||
    !isObject(by) ||
    !isInt(by.userId) ||
    typeof by.name !== 'string'
  )
    return null;
  const documentId = String(value.documentId);
  return {
    documentId,
    fileName: value.fileName,
    reportYear: value.reportYear as number | null,
    previousDocumentId:
      value.previousDocumentId === null ?
        null
      : String(value.previousDocumentId),
    pageCount: value.pageCount as number | null,
    // 올림 확인 전이면 null — 실서버의 checks 에는 생기지 않지만(실행은 올라온 문서에만) 막아 둔다: 그 문서 실행 가운데 이른 만든 때.
    uploadedAt:
      (value.uploadedAt as string | null) ?? earliestRun(runs, documentId),
    uploadedBy: { userId: String(by.userId), name: by.name },
  };
}

const earliestRun = (runs: readonly ListedRun[], documentId: string) =>
  runs
    .filter((run) => run.documentId === documentId)
    .map((run) => run.createdAt)
    .sort((a, b) => Date.parse(a) - Date.parse(b))[0] ?? '';

/** greenwash.checks@1 → 목록 원재료. 꼴이 틀리면 null. */
export function checkRowsOf(body: unknown): CheckRowsSource | null {
  if (
    !isObject(body) ||
    body.schemaVersion !== 'greenwash.checks@1' ||
    !isInt(body.currentUserId) ||
    typeof body.companyName !== 'string' ||
    !Array.isArray(body.documents) ||
    !Array.isArray(body.runs)
  )
    return null;
  const runs = body.runs.map(listedRunOf);
  if (runs.some((run) => run === null)) return null;
  const listed = runs as ListedRun[];
  const documents = body.documents.map((doc) => listedDocumentOf(doc, listed));
  if (documents.some((doc) => doc === null)) return null;
  return {
    currentUserId: String(body.currentUserId),
    companyName: body.companyName,
    documents: documents as ListedDocument[],
    runs: listed,
  };
}

/** 서버 문서(DocumentOut) 가운데 쓰는 칸. */
function serverDocumentOf(value: unknown) {
  if (
    !isObject(value) ||
    !isInt(value.id) ||
    typeof value.fileName !== 'string' ||
    !nullableInt(value.pageCount) ||
    !(
      value.hasText === undefined ||
      value.hasText === null ||
      typeof value.hasText === 'boolean'
    )
  )
    return null;
  return {
    id: value.id,
    fileName: value.fileName,
    pageCount: value.pageCount as number | null,
    hasText: (value.hasText as boolean | null | undefined) ?? null,
  };
}

/** Blob 꼴인가(전역 Blob 이 실행 환경마다 다를 수 있어 모양으로 본다 — 크기·종류·바이트 읽기). */
const isBlob = (value: unknown): value is Blob =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as Blob).size === 'number' &&
  typeof (value as Blob).type === 'string' &&
  typeof (value as Blob).arrayBuffer === 'function';

/** 실패 → 거절 갈래. 서버가 정한 꼴이면 code 표, 그 밖(끊김·꼴 밖)은 rejected. */
function kindOf(failure: ApiFailure): StoreErrorKind {
  return failure.kind === 'api' ?
      storeErrorKindOf(failure.status, failure.code)
    : 'rejected';
}

const refuse = (kind: StoreErrorKind, message: string) =>
  new StoreError(kind, message);

export function createGreenwashServerStore({
  api,
  sendUpload,
  countPages,
  pollMs = RUN_POLL_MS,
}: GreenwashServerDeps): GreenwashServerControl {
  const { client } = api;
  /** 이 탭에서 올린 문서: documentId → File·센 쪽 수(Q11). */
  const uploads = new Map<string, { file: File; pageCount: number }>();
  /** 서버에서 받은 원본: documentId → File(이 탭에서 올리지 않은 문서의 미리보기 — 밴드 GR3). */
  const fetched = new Map<string, File>();

  /**
   * 보낸다. 실패는 StoreError 로 던진다(409 RUN_NOT_DONE 등을 바꿀 표를 받는다).
   * lost 는 서버 답이 없을 때(끊김·꼴 밖 — ApiFailure.kind 가 api 가 아님)의 갈래다(기본 rejected).
   */
  async function send<T>(
    what: string,
    request: () => Promise<{ data?: T }>,
    overrides: Readonly<Record<string, StoreErrorKind>> = {},
    lost: StoreErrorKind = 'rejected',
  ): Promise<unknown> {
    let data: T | undefined;
    try {
      ({ data } = await request());
    } catch (error) {
      const failure = asFailure(error);
      throw refuse(
        failure.kind !== 'api' ? lost
        : Object.hasOwn(overrides, failure.code) ? overrides[failure.code]!
        : kindOf(failure),
        `${what} 실패`,
      );
    }
    if (data === undefined) throw refuse('rejected', `${what}: 빈 답`);
    return data;
  }

  const idOrMissing = (id: string, what: string) => {
    const value = serverId(id);
    if (value === null) throw refuse('not_found', `${what}: 서버 id 가 아님`);
    return value;
  };

  async function readRun(runId: number): Promise<ServerRun> {
    const body = await send('실행 읽기', () =>
      client.GET('/runs/{run_id}', { params: { path: { run_id: runId } } }),
    );
    const run = serverRunOf(body);
    if (run === null) throw refuse('rejected', '실행 꼴이 틀림');
    // 그린워싱이 아닌 실행은 이 화면에 없는 것이다.
    if (run.module !== 'greenwash')
      throw refuse('not_found', '그린워싱 실행이 아님');
    return run;
  }

  // 답이 끊기면 unreachable: 서버가 실행을 만들었는지 모른다(sid:MARC-ISSUE-225). 같은 열쇠로 다시 보내면 서버가 앞 실행을 돌려준다(밴드 GR2).
  async function postRun(
    documentId: number,
    options: Json,
    key: string | undefined,
    overrides: Readonly<Record<string, StoreErrorKind>> = {},
  ) {
    // launchKey(LK1)는 그 누름의 열쇠 그대로: 같은 열쇠로 다시 보내면 본문도 같아야 한다(바뀌면 서버 409 IDEMPOTENCY_KEY_REUSED).
    const launchKey = key ?? newIdempotencyKey();
    const body = await send(
      '실행 만들기',
      () =>
        client.POST('/runs', {
          ...(key === undefined ?
            {}
          : { params: { header: { 'Idempotency-Key': key } } }),
          body: { module: 'greenwash', documentId, launchKey, options },
        }),
      overrides,
      'unreachable',
    );
    if (!isObject(body) || !isInt(body.id))
      throw refuse('rejected', '실행 만들기 답의 꼴이 틀림');
    return { runId: String(body.id) };
  }

  async function readChecks(): Promise<CheckRowsSource> {
    const body = await send('목록 읽기', () => client.GET('/greenwash/checks'));
    const source = checkRowsOf(body);
    if (source === null) throw refuse('rejected', '목록 꼴이 틀림');
    return source;
  }

  const store: GreenwashStore = {
    async createDocument(file) {
      let counted: number;
      try {
        counted = await countPages(file);
      } catch {
        throw refuse('rejected', '쪽 수를 셀 수 없는 파일');
      }
      if (!isInt(counted) || counted < 1)
        throw refuse('rejected', '쪽 수를 셀 수 없는 파일');
      const created = await send('문서 만들기', () =>
        client.POST('/documents', {
          body: { fileName: file.name, sizeBytes: file.size },
        }),
      );
      const made =
        isObject(created) ? serverDocumentOf(created.document) : null;
      const upload = isObject(created) ? created.upload : null;
      if (
        made === null ||
        !isObject(upload) ||
        typeof upload.url !== 'string' ||
        typeof upload.method !== 'string'
      )
        throw refuse('rejected', '문서 만들기 답의 꼴이 틀림');
      try {
        await sendUpload(upload.url, upload.method, file);
      } catch (error) {
        // 크기 거절(413 — sendUpload 가 too_large 로 던짐)만 갈래를 살리고 그 밖은 rejected
        throw error instanceof StoreError && error.kind === 'too_large' ?
            error
          : refuse('rejected', '올리기 실패');
      }
      const confirmed = await send('올림 확인', () =>
        client.POST('/documents/{document_id}/confirm', {
          params: { path: { document_id: made.id } },
        }),
      );
      const after =
        isObject(confirmed) ? serverDocumentOf(confirmed.document) : null;
      if (after === null) throw refuse('rejected', '올림 확인 답의 꼴이 틀림');
      const documentId = String(made.id);
      const pageCount = after.pageCount ?? counted;
      uploads.set(documentId, { file, pageCount });
      return { documentId, pageCount, hasText: after.hasText ?? true };
    },

    async createRun(documentId, request, idempotencyKey) {
      // 수정본 대상은 화면에 칸이 없다(v115 — 조용히 버리지 않는다).
      if (request.previousDocumentId !== null)
        throw refuse('rejected', '수정본 대상은 실을 수 없다');
      const id = idOrMissing(documentId, '문서');
      // 보고연도는 실행 옵션이 아니라 문서 칸이다: 실행을 만들기 전에 PATCH(Q8). 거절되면 실행을 만들지 않는다.
      if (request.reportYear !== null) {
        const year = request.reportYear;
        const patched = await send('보고연도 정하기', () =>
          client.PATCH('/documents/{document_id}', {
            params: { path: { document_id: id } },
            body: { reportYear: year },
          }),
        );
        if (
          !isObject(patched) ||
          patched.id !== id ||
          patched.reportYear !== year
        )
          throw refuse('rejected', '보고연도 정하기 답의 꼴이 틀림');
      }
      const parts = {
        ceo: [...request.parts.ceo],
        company: [...request.parts.company],
        climate: [...request.parts.climate],
      };
      return postRun(
        id,
        request.extraTerms.length > 0 ?
          { parts, extraTerms: [...request.extraTerms] }
        : { parts },
        idempotencyKey,
        { IDEMPOTENCY_KEY_REUSED: 'key_reused' },
      );
    },

    async getRun(runId) {
      return snapshotOf(await readRun(idOrMissing(runId, '실행')));
    },

    subscribeRun(runId, listener, onMissing, onFailed) {
      let stopped = false;
      let timer: ReturnType<typeof setTimeout> | undefined;
      const id = serverId(runId);
      if (id === null) {
        // 요청 없이 없는 실행(계약: 조금 뒤든 곧바로든 — 해제했으면 부르지 않는다).
        void Promise.resolve().then(() => {
          if (!stopped) onMissing?.();
        });
        return () => {
          stopped = true;
        };
      }
      let received = false;
      let failures = 0;
      const tick = async () => {
        let run: ServerRun;
        try {
          run = await readRun(id);
        } catch (error) {
          if (stopped) return;
          if (error instanceof StoreError && error.kind === 'not_found') {
            stopped = true;
            onMissing?.();
            return;
          }
          failures += 1;
          if (!received || failures >= RUN_POLL_FAILURES) {
            stopped = true;
            onFailed?.();
            return;
          }
          timer = setTimeout(() => void tick(), pollMs);
          return;
        }
        if (stopped) return;
        received = true;
        failures = 0;
        const snapshot = snapshotOf(run);
        listener(snapshot);
        if (snapshot.progress.state === 'running')
          timer = setTimeout(() => void tick(), pollMs);
      };
      void tick();
      return () => {
        stopped = true;
        if (timer !== undefined) clearTimeout(timer);
      };
    },

    async rerun(runId, idempotencyKey) {
      const run = await readRun(idOrMissing(runId, '실행'));
      if (run.status !== 'failed')
        throw refuse('rejected', '실패한 실행만 다시 돈다');
      return postRun(run.documentId, run.options, idempotencyKey);
    },

    async listDocuments() {
      const source = await readChecks();
      return source.documents
        .map((doc): ExistingDocument => ({
          documentId: doc.documentId,
          fileName: doc.fileName,
          uploadedAt: doc.uploadedAt,
        }))
        .sort((a, b) => Date.parse(b.uploadedAt) - Date.parse(a.uploadedAt));
    },

    async listDefaultTerms() {
      const body = await send('기본 단어 읽기', () =>
        client.GET('/greenwash/terms/default'),
      );
      if (
        !isObject(body) ||
        !Array.isArray(body.terms) ||
        !body.terms.every((term) => typeof term === 'string')
      )
        throw refuse('rejected', '기본 단어 꼴이 틀림');
      return body.terms as string[];
    },

    async getDocument(documentId): Promise<DocumentInfo> {
      const id = idOrMissing(documentId, '문서');
      const body = await send('문서 읽기', () =>
        client.GET('/documents/{document_id}', {
          params: { path: { document_id: id } },
        }),
      );
      const found = isObject(body) ? serverDocumentOf(body.document) : null;
      if (found === null) throw refuse('rejected', '문서 꼴이 틀림');
      return {
        documentId: String(found.id),
        fileName: found.fileName,
        pageCount:
          found.pageCount ?? uploads.get(documentId)?.pageCount ?? null,
      };
    },

    listCheckRows: readChecks,

    async getResult(runId) {
      const id = idOrMissing(runId, '실행');
      return send(
        '결과 읽기',
        () =>
          client.GET('/greenwash/runs/{run_id}/result', {
            params: { path: { run_id: id } },
          }),
        { RUN_NOT_DONE: 'not_found' },
      );
    },

    async getReview(runId) {
      const id = idOrMissing(runId, '실행');
      return send(
        '검토 읽기',
        () =>
          client.GET('/greenwash/runs/{run_id}/review', {
            params: { path: { run_id: id } },
          }),
        { RUN_NOT_DONE: 'not_found' },
      );
    },

    async putReview(runId, update) {
      const id = idOrMissing(runId, '실행');
      return send('검토 저장', () =>
        client.PUT('/greenwash/runs/{run_id}/review', {
          params: { path: { run_id: id } },
          // 받은 그대로(거울은 훅이 댄다 — store.ts 무효 조건). marks·edits 는 계약 타입이 고칠 수 있는 배열이라 옮겨 담기만 한다.
          body: {
            ...update,
            marks: [...update.marks],
            edits:
              update.edits == null ?
                update.edits
              : update.edits.map((e) => ({
                  ...e,
                  reasonBullets:
                    e.reasonBullets === null ? null : [...e.reasonBullets],
                })),
            evidence:
              update.evidence == null ?
                update.evidence
              : update.evidence.map((e) => ({
                  itemIndex: e.itemIndex,
                  removed: [...e.removed],
                  added: e.added.map((a) => ({ ...a })),
                })),
          },
        }),
      );
    },

    async rejudge(runId, itemIndex) {
      const id = idOrMissing(runId, '실행');
      const body = await send('재판단 만들기', () =>
        client.POST('/greenwash/runs/{run_id}/items/{item_index}/rejudge', {
          params: { path: { run_id: id, item_index: itemIndex } },
        }),
      );
      const made = (body as { rejudgeRunId?: unknown }).rejudgeRunId;
      if (typeof made !== 'number')
        throw refuse('rejected', '재판단 만들기: 답 꼴이 다름');
      return { rejudgeRunId: String(made) };
    },

    async openDocumentPdf(documentId) {
      const local = uploads.get(documentId)?.file ?? fetched.get(documentId);
      if (local) return local;
      const id = serverId(documentId);
      if (id === null) return null;
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET('/documents/{document_id}/file', {
          params: { path: { document_id: id } },
          parseAs: 'blob',
        });
      } catch {
        return null;
      }
      const blob = answer.data;
      if (!isBlob(blob)) return null;
      const file = new File(
        [blob],
        fileNameFromDisposition(
          answer.response.headers.get('Content-Disposition'),
        ) ?? `document-${id}.pdf`,
        { type: 'application/pdf' },
      );
      fetched.set(documentId, file);
      return file;
    },

    async getReport(runId, confirmed): Promise<ReportFile> {
      const id = idOrMissing(runId, '실행');
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET('/greenwash/runs/{run_id}/report', {
          params: {
            path: { run_id: id },
            // 확정 전 결과는 쿼리를 싣지 않는다(서버 기본 false)
            ...(confirmed ? { query: { confirmed: true } } : {}),
          },
          parseAs: 'blob',
        });
      } catch (error) {
        throw refuse(kindOf(asFailure(error)), '엑셀 내려받기 실패');
      }
      const blob = answer.data;
      if (!isBlob(blob)) throw refuse('rejected', '엑셀 답이 파일이 아님');
      return {
        blob,
        fileName:
          fileNameFromDisposition(
            answer.response.headers.get('Content-Disposition'),
          ) ?? fallbackReportName(String(id)),
      };
    },
  };

  return {
    store,
    forget: () => {
      uploads.clear();
      fetched.clear();
    },
  };
}
