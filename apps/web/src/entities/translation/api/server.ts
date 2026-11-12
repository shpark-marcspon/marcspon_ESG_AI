// 영문번역 실어댑터(밴드 TRW1a ①). TranslationStore 꼴을 서버 경로로 맞춘다 — 그린워싱 api/server.ts(GW1R) 꼴을 따라 지음(가져오지 않는다).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. 전역 통신·창·보관소는 모른다:
//   서명 주소로 올리는 PUT(sendUpload)은 app/ 이 넣는다(Authorization 을 싣지 않는다 — app 의 몫).
// 경로:
//   uploadDocument   POST /documents {fileName, sizeBytes} → sendUpload(upload.url, upload.method, file) → POST /documents/{id}/confirm
//                    → GET /translation/documents/{id}/pages(밴드 TRP6 — 서버가 [PAGE n] 최댓값을 셈, 그리드 표시용, 결정 sid:MARC-ENT-452).
//                    쪽 수는 pages 답(null 이어도 그 값). 끊김·PAGES_TIMEOUT_MS 넘김·4xx·5xx·꼴 어긋남이면 confirm 의 쪽 수 —
//                    올림을 거절하지 않고 다시 보내지 않는다. 웹은 쪽을 세지 않는다.
//   readGlossary     POST /translation/glossary/read — 본문은 xlsx 바이트 그대로, Content-Type 은 서버 MEDIA_TYPE. 답 둘 다 200(ok 판별).
//   glossaryTemplate GET /translation/glossary/template(blob) — 이름은 Content-Disposition(없으면 서버 FILE_NAME).
//   startBatch       파트마다 POST /runs {module:'translation', documentId, launchKey, options} + 머리 Idempotency-Key(파트마다 새 열쇠).
//                    options = translation.options@1(apps/api-py/esgapi/translation/contracts/options_shapes.py): batchId · company · part ·
//                    style · pages · ceoPageLimit(CEO 파트 6, 그 밖 null — 감독 판단 4) · glossary{base?, final} · peerGroupStyle?(켰을 때만).
//                    batchId·launchKey 는 [번역 시작] 한 번에 하나씩(서로 다른 값)을 모든 파트에. autofix·retry·flowId·resumeFromRunId·companyId 0.
//                    파트 하나의 options 를 서버 꼴(json.dumps 기본 구분자)로 적은 UTF-8 바이트가 OPTIONS_MAX_OCTETS(256KiB — 서버 DOCUMENTLESS_OPTIONS_MAX_OCTETS,
//                    esgapi/core/flows/binding.py:50) 를 넘으면 아무것도 보내지 않고 too_long. 일부 파트만 거절되면 만든 것만 started(failed 에 나머지),
//                    하나도 못 만들면 거절(끊김이면 unreachable).
//   retryPart        GET /runs/{id} → 화면이 읽는 칸만 대 봄(module translation · documentId · options 객체 · options.batchId = 묶음 열쇠 ·
//                    options.part = 그 파트) — 어긋나면 rejected(POST 0) · `run-<id>` 열쇠(batchId 없는 옛 실행)는 요청 없이 rejected →
//                    POST /runs {module, documentId, launchKey: 새 열쇠, options: 받은 그대로}(결정 sid:MARC-ENT-393·405 — 옵션을 고치지 않는다).
//                    앞 실행 flowId 가 translation.pdf@ 로 시작하면 그 flowId 도 그대로(밴드 TRW6 ④ W5), 워드는 flowId 키 0.
//   POST /runs 는 열쇠(Idempotency-Key)를 한 번 지어 보내고, 끊기면(unreachable) 같은 열쇠·같은 본문으로 한 번 더(서버가 만들었으면 앞 실행 201).
//                    그 밖 거절(4xx·꼴)은 다시 보내지 않는다(startBatch·retryPart 같이).
//   listBatches      GET /translation/batches?state=&mine=true&limit=20&offset= (state 는 있을 때만, mine 은 참일 때만) → translation.batch@1 쪽.
//   getBatch         GET /translation/documents/{d}/batches/{k}. subscribeBatch 는 같은 경로의 폴링(store.ts 의 규칙, 멈춤은 state !== 'active').
//   getResult        GET /translation/runs/{id}/result → translation.result@1(거울). 409 RUN_NOT_DONE 은 not_done.
//   runFile          GET /runs/{id}/files/{name}(blob) → 받은 이름 그대로.
//   archive          GET /translation/documents/{d}/batches/{k}/archive(blob) → zip + 머리 X-Archive-Missing(정수 글자 — 없거나 아니면 거절).
//                    409 ARCHIVE_TOO_LARGE → too_large · 409 NO_FINISHED_PARTS → nothing · 404 → not_found.
// id 는 글자다: 나갈 때 `^[1-9][0-9]*$` 만 수로, 묶음 열쇠는 BATCH_KEY_PATTERN 만 — 아니면 요청 없이 not_found(구독이면 onMissing).
// PDF(밴드 TRW6 ①, TRS3 §1-1·§1-2):
//   uploadPdf        uploadDocument 와 같은 셋(POST /documents → PUT → confirm)에서 멈춘다 — pages 경로 0. 쪽 수·hasText 는 confirm 답(W4).
//   getDocument      GET /documents/{id} → {document} 의 쪽 수·hasText(목록에서 다시 들어올 때).
//   getRunInfo       GET /runs/{id} → flowId·resultShapes·documentId·options.part(retryPart 와 같은 읽기 readRun).
//   startBatch       입력에 flowId 가 있을 때만 POST /runs 본문에 flowId(W5 — 워드 본문은 BASE 그대로, 키 없음).
//   getLayout        GET /translation/runs/{id}/layout → layout@1 거울. 404 → not_found, 409 RUN_NOT_DONE → not_done.
//   openRunPdf       GET /documents/{id}/file(blob) → File. 404·409 → missing, 그 밖 → failed. 받은 것(ready·missing)은 문서 id 마다 한 벌
//                    들고 있다가 다음 부름에 그대로(그린워싱 fetched 꼴 — 감사 줄 중복 0). failed 는 들지 않는다([다시 시도]가 새로 보냄).
// 거절의 서버 message 는 화면에 보이지 않는다(이 파일의 거절 글은 개발자용 영문). 어느 요청에도 companyId 를 싣지 않는다.
import { asFailure } from '../../../shared/api/index.ts';
import type { Api, ApiFailure } from '../../../shared/api/index.ts';
import {
  CEO_PAGE_LIMIT,
  SERVER_PARTS,
  isPdfFlow,
  partKeyOf,
  pyJsonOctets,
  serverPartOf,
} from '../model/index.ts';
import type {
  PartKey,
  ServerPart,
  TranslationBatchDetail,
} from '../model/index.ts';
import {
  parseBatchDetail,
  parseBatchPage,
  parseGlossaryRead,
  parseLayout,
  parseResult,
} from './contract/index.ts';
import { isBatchKey, newKey, serverId } from './ids.ts';
import type { NewKey } from './ids.ts';
import { TranslationStoreError } from './store.ts';
import type {
  FileDownload,
  RunPdf,
  StartInput,
  StoreErrorKind,
  TranslationStore,
} from './store.ts';

/** 폴링 간격 기본(ms). */
export const BATCH_POLL_MS = 2000;
/** 값을 받은 뒤 이만큼 잇달아 실패하면 onFailed. */
export const BATCH_POLL_FAILURES = 3;
/** 한 실행 옵션의 UTF-8 바이트 상한(서버 DOCUMENTLESS_OPTIONS_MAX_OCTETS). */
export const OPTIONS_MAX_OCTETS = 256 * 1024;
/** 묶음 목록 한 쪽의 줄 수(쪽 넘김은 TRW1b). */
export const BATCH_PAGE_LIMIT = 20;
/** GET …/pages 를 기다리는 상한(ms). 넘으면 confirm 의 쪽 수로(밴드 TRP6). */
export const PAGES_TIMEOUT_MS = 5000;
/** 용어집 엑셀의 꼴(서버 glossary MEDIA_TYPE). */
export const XLSX_MEDIA_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
/** 양식 이름을 모를 때(서버 glossary FILE_NAME). */
export const TEMPLATE_FILE_NAME = 'translation-glossary-template.xlsx';

export interface TranslationServerDeps {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
  /** 서명 주소로 파일 본문을 올린다(app 이 넣는다 — Authorization 을 싣지 않는다). 2xx 가 아니거나 끊기면 거절. */
  sendUpload(url: string, method: string, file: File): Promise<void>;
  /** 폴링 간격(ms). 기본 BATCH_POLL_MS. */
  pollMs?: number;
  /** 새 열쇠(batchId·launchKey·Idempotency-Key). 기본 newKey(시험이 고정한다). */
  newKey?: NewKey;
}

type Json = Record<string, unknown>;

const isObject = (value: unknown): value is Json =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const isInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value);

/** Blob 꼴인가(전역 Blob 이 실행 환경마다 다를 수 있어 모양으로 본다). */
const isBlob = (value: unknown): value is Blob =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as Blob).size === 'number' &&
  typeof (value as Blob).type === 'string' &&
  typeof (value as Blob).arrayBuffer === 'function';

/**
 * Content-Disposition → 파일 이름(그린워싱 model/report.ts fileNameFromDisposition 과 같은 셈 — 옮겨 적음):
 * filename*=UTF-8''… 가 있으면 그것, 없으면 filename="…"·filename=…. 경로 글자는 지운다. 못 읽으면 null.
 */
export function fileNameFromDisposition(header: string | null): string | null {
  if (header === null) return null;
  const clean = (name: string) => {
    const trimmed = name.replace(/[/\\]/g, '').trim();
    return trimmed === '' ? null : trimmed;
  };
  const star = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (star) {
    try {
      return clean(decodeURIComponent(star[1]!.trim()));
    } catch {
      // 퍼센트 꼴이 깨졌으면 아래 filename= 으로
    }
  }
  const quoted = /filename\s*=\s*"((?:[^"\\]|\\.)*)"/.exec(header);
  if (quoted) return clean(quoted[1]!.replace(/\\(.)/g, '$1'));
  const bare = /filename\s*=\s*([^;\s]+)/.exec(header);
  if (bare) return clean(bare[1]!);
  return null;
}

/** 실패 → 거절 갈래: 404 류·NOT_FOUND → not_found, RUN_NOT_DONE → not_done, 그 밖 서버 거절 → rejected, 답 없음 → lost. */
function kindOf(failure: ApiFailure, lost: StoreErrorKind): StoreErrorKind {
  if (failure.kind !== 'api') return lost;
  if (failure.code === 'RUN_NOT_DONE') return 'not_done';
  if (failure.code === 'NOT_FOUND' || failure.status === 404)
    return 'not_found';
  return 'rejected';
}

const refuse = (kind: StoreErrorKind, message: string) =>
  new TranslationStoreError(kind, message);

/** 파트 하나의 실행 옵션(translation.options@1). 키 차례: batchId 먼저(서버는 차례를 보지 않는다). */
export function optionsOf(
  input: StartInput,
  part: PartKey,
  range: { from: number; to: number },
  batchId: string,
): Json {
  return {
    batchId,
    company: { ...input.company },
    part: serverPartOf(part),
    style: { ...input.style },
    pages: { start: range.from, end: range.to },
    ceoPageLimit: part === 'ceo' ? CEO_PAGE_LIMIT : null,
    glossary: {
      ...(input.glossary.base === undefined ?
        {}
      : { base: input.glossary.base.map((pair) => ({ ...pair })) }),
      final: input.glossary.final.map((pair) => ({ ...pair })),
    },
    ...(input.peerGroupStyle === null ?
      {}
    : { peerGroupStyle: { prompt: input.peerGroupStyle } }),
  };
}

/** 옵션의 UTF-8 바이트 수 — 서버와 같은 셈(파이썬 json.dumps 기본 구분자, model/options.ts). */
export const optionsOctets = (options: Json) => pyJsonOctets(options);

export function createTranslationServerStore({
  api,
  sendUpload,
  pollMs = BATCH_POLL_MS,
  newKey: makeKey = newKey,
}: TranslationServerDeps): TranslationStore {
  const { client } = api;

  /** 보낸다. 실패는 TranslationStoreError 로 던진다. lost 는 답을 받지 못했을 때의 갈래(기본 rejected). */
  async function send<T>(
    what: string,
    request: () => Promise<{ data?: T }>,
    lost: StoreErrorKind = 'rejected',
  ): Promise<unknown> {
    let data: T | undefined;
    try {
      ({ data } = await request());
    } catch (error) {
      throw refuse(kindOf(asFailure(error), lost), `${what} failed`);
    }
    if (data === undefined) throw refuse('rejected', `${what}: empty answer`);
    return data;
  }

  /** 문서 쪽 수(GET …/pages). 못 받으면 fallback(confirm 의 값). 시간 상한은 setTimeout 하나가 요청을 끊고(signal)
   *  기다림도 끝낸다(race) — 시험 가짜 서버는 signal 을 보지 않아서다. 늦게 온 답·거절은 버린다. */
  async function pagesOf(
    id: number,
    fallback: number | null,
  ): Promise<number | null> {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const late = new Promise<undefined>((resolve) => {
      timer = setTimeout(() => {
        controller.abort();
        resolve(undefined);
      }, PAGES_TIMEOUT_MS);
    });
    const answered = client
      .GET('/translation/documents/{document_id}/pages', {
        params: { path: { document_id: id } },
        signal: controller.signal,
      })
      .then(
        ({ data }): unknown => data,
        () => undefined,
      );
    try {
      const body = await Promise.race([answered, late]);
      if (
        isObject(body) &&
        body.documentId === id &&
        (body.pageCount === null ||
          (isInt(body.pageCount) && body.pageCount >= 1))
      )
        return body.pageCount as number | null;
      return fallback;
    } finally {
      clearTimeout(timer);
    }
  }

  const idOrMissing = (id: string, what: string) => {
    const value = serverId(id);
    if (value === null) throw refuse('not_found', `${what}: not a server id`);
    return value;
  };
  const keyOrMissing = (key: string) => {
    if (!isBatchKey(key)) throw refuse('not_found', 'batch key: bad shape');
    return key;
  };

  async function readBatch(
    documentId: number,
    batchKey: string,
  ): Promise<TranslationBatchDetail> {
    const body = await send('batch', () =>
      client.GET('/translation/documents/{document_id}/batches/{batch_key}', {
        params: { path: { document_id: documentId, batch_key: batchKey } },
      }),
    );
    const parsed = parseBatchDetail(body);
    if (!parsed.ok) throw refuse('rejected', `batch shape: ${parsed.issues}`);
    return parsed.value;
  }

  /** POST /runs 하나 → 실행 id. 열쇠는 한 번 짓고, 끊기면 같은 열쇠·같은 본문으로 한 번 더(둘째도 끊기면 unreachable). */
  async function createRun(
    documentId: number,
    launchKey: string,
    options: Json,
    flowId?: string,
  ): Promise<string> {
    const idempotencyKey = makeKey();
    const post = () =>
      send(
        'run create',
        () =>
          client.POST('/runs', {
            params: { header: { 'Idempotency-Key': idempotencyKey } },
            body: {
              module: 'translation',
              // 흐름은 있을 때만(PDF — 워드 본문은 BASE 그대로).
              ...(flowId === undefined ? {} : { flowId }),
              documentId,
              launchKey,
              options,
            },
          }),
        'unreachable',
      );
    let body: unknown;
    try {
      body = await post();
    } catch (error) {
      if (
        !(error instanceof TranslationStoreError) ||
        error.kind !== 'unreachable'
      )
        throw error;
      body = await post();
    }
    if (!isObject(body) || !isInt(body.id))
      throw refuse('rejected', 'run create: bad shape');
    return String(body.id);
  }

  /** blob 답(파일 이름은 Content-Disposition). */
  async function readBlob(
    what: string,
    request: () => Promise<{ data?: unknown; response: Response }>,
  ): Promise<{ blob: Blob; response: Response }> {
    let answer: { data?: unknown; response: Response };
    try {
      answer = await request();
    } catch (error) {
      throw refuse(kindOf(asFailure(error), 'rejected'), `${what} failed`);
    }
    if (!isBlob(answer.data)) throw refuse('rejected', `${what}: not a file`);
    return { blob: answer.data, response: answer.response };
  }

  /**
   * GET /runs/{id} 를 읽어 영문번역 실행의 바탕 칸(module translation · 문서 id 수 · options 객체)을 대 본다 — retryPart·getRunInfo 한 벌.
   * flowId·resultShapes 는 getRunInfo 만 본다(retryPart 는 BASE 처럼 그 칸을 요구하지 않는다 — 워드 동작 0 바뀜).
   * 꼴이 틀리면 null(부르는 쪽이 제 거절 글을 단다), 보내기 실패는 send 의 거절 그대로(retryPart 의 「run failed」 — BASE, 검증 권고 R3).
   */
  async function readRun(id: number) {
    const body = await send('run', () =>
      client.GET('/runs/{run_id}', { params: { path: { run_id: id } } }),
    );
    const options = isObject(body) ? body.options : null;
    if (
      !isObject(body) ||
      body.module !== 'translation' ||
      !isInt(body.documentId) ||
      !isObject(options)
    )
      return null;
    return { body, documentId: body.documentId, options };
  }

  /** 문서 꼴(confirm·GET /documents/{id} 의 document) — 칸이 틀리면 거절. */
  function documentOf(answer: unknown, id: number, what: string) {
    const doc = isObject(answer) ? answer.document : null;
    if (
      !isObject(doc) ||
      doc.id !== id ||
      typeof doc.fileName !== 'string' ||
      !isInt(doc.sizeBytes) ||
      !(doc.uploadedAt === null || typeof doc.uploadedAt === 'string') ||
      !(doc.pageCount === null || isInt(doc.pageCount)) ||
      !(
        doc.hasText === undefined ||
        doc.hasText === null ||
        typeof doc.hasText === 'boolean'
      )
    )
      throw refuse('rejected', `${what}: bad shape`);
    return {
      fileName: doc.fileName,
      sizeBytes: doc.sizeBytes,
      uploadedAt: doc.uploadedAt as string | null,
      pageCount: doc.pageCount as number | null,
      hasText: (doc.hasText ?? null) as boolean | null,
    };
  }

  /** 받은 원본 PDF(문서 id → 답). failed 는 들지 않는다. */
  const pdfs = new Map<number, Promise<RunPdf>>();

  async function fetchPdf(id: number): Promise<RunPdf> {
    let answer: { data?: unknown; response: Response };
    try {
      answer = await client.GET('/documents/{document_id}/file', {
        params: { path: { document_id: id } },
        parseAs: 'blob',
      });
    } catch (error) {
      const failure = asFailure(error);
      if (
        failure.kind === 'api' &&
        (failure.status === 404 || failure.status === 409)
      )
        return { kind: 'missing' };
      return { kind: 'failed' };
    }
    if (!isBlob(answer.data)) return { kind: 'failed' };
    const name =
      fileNameFromDisposition(
        answer.response.headers.get('Content-Disposition'),
      ) ?? `document-${id}.pdf`;
    return {
      kind: 'ready',
      file: new File([answer.data], name, { type: 'application/pdf' }),
    };
  }

  /** POST /documents → PUT → confirm(uploadDocument·uploadPdf 같이). confirm 답의 문서 꼴을 돌려준다. */
  async function uploadAndConfirm(file: File) {
    const created = await send('document create', () =>
      client.POST('/documents', {
        body: { fileName: file.name, sizeBytes: file.size },
      }),
    );
    const made = isObject(created) ? created.document : null;
    const upload = isObject(created) ? created.upload : null;
    if (
      !isObject(made) ||
      !isInt(made.id) ||
      !isObject(upload) ||
      typeof upload.url !== 'string' ||
      typeof upload.method !== 'string'
    )
      throw refuse('rejected', 'document create: bad shape');
    try {
      await sendUpload(upload.url, upload.method, file);
    } catch {
      throw refuse('rejected', 'upload failed');
    }
    const id = made.id;
    const confirmed = await send('document confirm', () =>
      client.POST('/documents/{document_id}/confirm', {
        params: { path: { document_id: id } },
      }),
    );
    return { id, ...documentOf(confirmed, id, 'document confirm') };
  }

  const store: TranslationStore = {
    async uploadDocument(file) {
      const doc = await uploadAndConfirm(file);
      const pageCount = await pagesOf(doc.id, doc.pageCount);
      return {
        documentId: String(doc.id),
        fileName: doc.fileName,
        sizeBytes: doc.sizeBytes,
        uploadedAt: doc.uploadedAt,
        pageCount,
      };
    },

    async uploadPdf(file) {
      const doc = await uploadAndConfirm(file);
      return {
        documentId: String(doc.id),
        fileName: doc.fileName,
        sizeBytes: doc.sizeBytes,
        uploadedAt: doc.uploadedAt,
        pageCount: doc.pageCount,
        hasText: doc.hasText,
      };
    },

    async getDocument(documentId) {
      const id = idOrMissing(documentId, 'document');
      const body = await send('document', () =>
        client.GET('/documents/{document_id}', {
          params: { path: { document_id: id } },
        }),
      );
      const doc = documentOf(body, id, 'document');
      return {
        documentId: String(id),
        fileName: doc.fileName,
        pageCount: doc.pageCount,
        hasText: doc.hasText,
      };
    },

    async getRunInfo(runId) {
      const id = idOrMissing(runId, 'run');
      const run = await readRun(id);
      if (run === null) throw refuse('rejected', 'run: bad shape');
      const { flowId, resultShapes } = run.body;
      if (
        typeof flowId !== 'string' ||
        !Array.isArray(resultShapes) ||
        !resultShapes.every((shape) => typeof shape === 'string')
      )
        throw refuse('rejected', 'run: bad shape');
      const part = run.options.part;
      return {
        runId: String(id),
        flowId,
        resultShapes: resultShapes as string[],
        documentId: String(run.documentId),
        part:
          (SERVER_PARTS as readonly unknown[]).includes(part) ?
            partKeyOf(part as ServerPart)
          : null,
      };
    },

    async getLayout(runId) {
      const id = idOrMissing(runId, 'run');
      const body = await send('layout', () =>
        client.GET('/translation/runs/{run_id}/layout', {
          params: { path: { run_id: id } },
        }),
      );
      const parsed = parseLayout(body);
      if (!parsed.ok)
        throw refuse('rejected', `layout shape: ${parsed.issues}`);
      return parsed.value;
    },

    openRunPdf(documentId) {
      const id = serverId(documentId);
      if (id === null) return Promise.resolve({ kind: 'missing' });
      const kept = pdfs.get(id);
      if (kept) return kept;
      const got = fetchPdf(id).then((pdf) => {
        if (pdf.kind === 'failed') pdfs.delete(id);
        return pdf;
      });
      pdfs.set(id, got);
      return got;
    },

    async readGlossary(file) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const body = await send('glossary read', () =>
        client.POST('/translation/glossary/read', {
          // 본문은 맨 바이트(multipart 아님 — 서버 경로의 선언). openapi 의 본문 타입은 글자라 바꿔 싣는다.
          body: bytes as unknown as string,
          bodySerializer: (value: unknown) => value as BodyInit,
          headers: { 'Content-Type': XLSX_MEDIA_TYPE },
        }),
      );
      const parsed = parseGlossaryRead(body);
      if (!parsed.ok)
        throw refuse('rejected', `glossary read shape: ${parsed.issues}`);
      return parsed.value;
    },

    async glossaryTemplate(): Promise<FileDownload> {
      const { blob, response } = await readBlob('glossary template', () =>
        client.GET('/translation/glossary/template', { parseAs: 'blob' }),
      );
      return {
        blob,
        fileName:
          fileNameFromDisposition(
            response.headers.get('Content-Disposition'),
          ) ?? TEMPLATE_FILE_NAME,
      };
    },

    async startBatch(input) {
      const documentId = idOrMissing(input.documentId, 'document');
      const batchId = makeKey();
      const launchKey = makeKey();
      const planned = input.parts.map(({ part, range }) => ({
        part,
        options: optionsOf(input, part, range, batchId),
      }));
      // 하나라도 상한을 넘으면 아무것도 보내지 않는다(일부만 만들어지지 않게).
      if (
        planned.some(
          ({ options }) => optionsOctets(options) > OPTIONS_MAX_OCTETS,
        )
      )
        return { kind: 'too_long' };
      const runs: { part: PartKey; runId: string }[] = [];
      const failed: PartKey[] = [];
      let lastError: unknown = refuse('rejected', 'no parts');
      for (const { part, options } of planned) {
        try {
          runs.push({
            part,
            runId: await createRun(
              documentId,
              launchKey,
              options,
              input.flowId,
            ),
          });
        } catch (error) {
          lastError = error;
          failed.push(part);
        }
      }
      if (runs.length === 0) throw lastError;
      return {
        kind: 'started',
        documentId: String(documentId),
        batchKey: batchId,
        runs,
        failed,
      };
    },

    async retryPart({ documentId, batchKey, part, runId }) {
      const docId = idOrMissing(documentId, 'document');
      const key = keyOrMissing(batchKey);
      const id = idOrMissing(runId, 'run');
      // batchId 없는 옛 실행의 묶음: 같은 옵션을 다시 보내면 새 줄(run-<새 id>)이 생긴다 — 묶음 회차가 아니다(감독 판단 c).
      if (key.startsWith('run-'))
        throw refuse('rejected', 'retry: batch has no batchId');
      const run = await readRun(id);
      if (
        run === null ||
        run.documentId !== docId ||
        run.options.batchId !== key ||
        run.options.part !== serverPartOf(part)
      )
        throw refuse('rejected', 'retry: run does not match the batch part');
      // PDF 실행이면 같은 flowId 를 싣는다(W5 — 빼면 워드 흐름이 PDF 를 거절). 워드 본문은 BASE 그대로(키 없음).
      const flowId = run.body.flowId;
      return {
        runId: await createRun(
          docId,
          makeKey(),
          run.options,
          typeof flowId === 'string' && isPdfFlow(flowId) ? flowId : undefined,
        ),
      };
    },

    async listBatches({ state, mine, offset }) {
      const body = await send('batch list', () =>
        client.GET('/translation/batches', {
          params: {
            query: {
              ...(state === undefined ? {} : { state }),
              ...(mine ? { mine: true } : {}),
              limit: BATCH_PAGE_LIMIT,
              offset,
            },
          },
        }),
      );
      const parsed = parseBatchPage(body);
      if (!parsed.ok)
        throw refuse('rejected', `batch list shape: ${parsed.issues}`);
      return parsed.value;
    },

    async getBatch(documentId, batchKey) {
      return readBatch(
        idOrMissing(documentId, 'document'),
        keyOrMissing(batchKey),
      );
    },

    subscribeBatch(documentId, batchKey, listener, onMissing, onFailed) {
      let stopped = false;
      let timer: ReturnType<typeof setTimeout> | undefined;
      const id = serverId(documentId);
      if (id === null || !isBatchKey(batchKey)) {
        // 요청 없이 없는 묶음(해제했으면 부르지 않는다).
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
        let batch: TranslationBatchDetail;
        try {
          batch = await readBatch(id, batchKey);
        } catch (error) {
          if (stopped) return;
          if (
            error instanceof TranslationStoreError &&
            error.kind === 'not_found'
          ) {
            stopped = true;
            onMissing?.();
            return;
          }
          failures += 1;
          if (!received || failures >= BATCH_POLL_FAILURES) {
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
        listener(batch);
        if (batch.state === 'active')
          timer = setTimeout(() => void tick(), pollMs);
      };
      void tick();
      return () => {
        stopped = true;
        if (timer !== undefined) clearTimeout(timer);
      };
    },

    async getResult(runId) {
      const id = idOrMissing(runId, 'run');
      const body = await send('result', () =>
        client.GET('/translation/runs/{run_id}/result', {
          params: { path: { run_id: id } },
        }),
      );
      const parsed = parseResult(body);
      if (!parsed.ok)
        throw refuse('rejected', `result shape: ${parsed.issues}`);
      return parsed.value;
    },

    async runFile(runId, name) {
      const id = idOrMissing(runId, 'run');
      const { blob } = await readBlob('run file', () =>
        client.GET('/runs/{run_id}/files/{name}', {
          params: { path: { run_id: id, name } },
          parseAs: 'blob',
        }),
      );
      return { blob, fileName: name };
    },

    async archive(documentId, batchKey) {
      const id = idOrMissing(documentId, 'document');
      const key = keyOrMissing(batchKey);
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET(
          '/translation/documents/{document_id}/batches/{batch_key}/archive',
          {
            params: { path: { document_id: id, batch_key: key } },
            parseAs: 'blob',
          },
        );
      } catch (error) {
        const failure = asFailure(error);
        if (failure.kind === 'api' && failure.code === 'ARCHIVE_TOO_LARGE')
          return { kind: 'too_large' };
        if (failure.kind === 'api' && failure.code === 'NO_FINISHED_PARTS')
          return { kind: 'nothing' };
        throw refuse(kindOf(failure, 'rejected'), 'archive failed');
      }
      if (!isBlob(answer.data)) throw refuse('rejected', 'archive: not a file');
      const missing = answer.response.headers.get('X-Archive-Missing');
      if (missing === null || !/^(0|[1-9][0-9]*)$/.test(missing))
        throw refuse('rejected', 'archive: bad X-Archive-Missing');
      return {
        kind: 'file',
        blob: answer.data,
        fileName:
          fileNameFromDisposition(
            answer.response.headers.get('Content-Disposition'),
          ) ?? `translation-${id}-${key.slice(0, 8)}.zip`,
        missing: Number(missing),
      };
    },
  };

  return store;
}
