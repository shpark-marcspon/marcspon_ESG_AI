// 원고작성 실어댑터(밴드 RPW1 ① — 발주서 §2-1). 온실가스 api/server.ts 꼴(갈래를 값으로 — 던지지 않는다)을 따라 지음(가져오지 않는다).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh)와 서명 PUT 함수 sendUpload(틀이 준다 — Authorization 0)만 쓴다.
// companyId 는 어느 요청에도 싣지 않는다(sid:MARC-ENT-374 — 서버가 작업 회사를 정한다). 경로:
//   ① listProjects   GET  /drafting/projects?limit=100&offset=0            → DraftingProjectPage
//      getProject     GET  /drafting/projects/{project_id}                 → DraftingProject(404 → not_found)
//      createProject  POST /drafting/projects {year, name}                 → 201 DraftingProject
//      uploadPdf      POST /documents {fileName, sizeBytes} → 서명 PUT(sendUpload) → POST /documents/{id}/confirm → {documentId, pageCount, hasText}
//                     (영문번역 api/server.ts:400 uploadAndConfirm 을 옮겨 적음)
//      attachDocument PUT  /drafting/projects/{project_id}/document {documentId} → DraftingProject(422 DOCUMENT_NO_TEXT_LAYER)
//   ② saveOutline    PUT  /drafting/projects/{project_id}/outline {nodes} → DraftingOutlinePut
//      startRun       POST /runs {module:'drafting', launchKey, options:{projectId, base?}} + Idempotency-Key → 201 RunCreatedOut{id, status}(영문번역 createRun 꼴)
//                     — 같은 프로젝트·목차 판·본문으로 다시 누르면 같은 열쇠. 표는 저장소 밖 모듈 수준(화면을 떠났다 와도 산다 — 페이지 수명만).
//                       ok·rejected 에서 버리고 failed·refused 는 남긴다(RPW2 M5 — 시간 초과로 앞 요청이 섰어도 실행 하나). 5xx 도 failed(RPW3 — 서버가 세운 뒤 5xx 를 냈을 수 있다).
//      getDocument    GET  /documents/{document_id} → {fileName, pageCount}(목차 설정 부제 — RPW3)
//      getRun         GET  /runs/{run_id} → RunState(module 이 drafting 이 아니면 not_found)
//   ③ getResult      GET  /drafting/runs/{run_id}/result → drafting.bullets@3(409 RUN_NOT_DONE → not_done)
//      getChanges     GET  /drafting/projects/{project_id}/outline/changes?baseRunId= → DraftingOutlineChanges
//      openPdf        GET  /documents/{document_id}/file(blob — 영문번역 fetchPdf 꼴) · 문서 id 마다 한 벌(실패는 쥐지 않는다)
//      downloadDocx   GET  /drafting/runs/{run_id}/result.docx(blob — 이름은 Content-Disposition)
//      listRuns       GET  /drafting/projects/{project_id}/runs?limit=50&offset=0 → DraftingRunPage(RPS1)
// 갈래: 읽기 ok | refused(회사 거절 셋) | not_found | failed · 쓰기 ok | rejected{code, fields} | refused | failed.
//   rejected 는 4xx 뿐(5xx·연결 실패는 failed). code 는 WRITE_CODES 만, 그 밖 거절은 null. 서버 message 는 싣지 않는다(화면 0 — 이 파일에 서버 글이 지나가는 칸이 없다).
import { asFailure, companyRefusalOf } from '../../../shared/api/index.ts';
import type {
  Api,
  ApiFailure,
  CompanyRefusal,
  FailureFields,
} from '../../../shared/api/index.ts';
import type {
  DraftingResult,
  OutlineChanges,
  OutlineNode,
  Project,
  ProjectPage,
  RunOptions,
  RunPage,
  RunState,
} from '../model/index.ts';
import {
  parseChanges,
  parseDocumentCreated,
  parseDocumentStatus,
  parseOutlinePut,
  parseProject,
  parseProjectPage,
  parseResult,
  parseRunCreated,
  parseRunOptions,
  parseRunOut,
  parseRunPage,
} from './contract/index.ts';

/** 목록 한 번에 읽는 줄 수(서버 상한 100 — 거르기는 화면이 이 안에서). */
export const PROJECT_LIST_LIMIT = 100;
/** 프로젝트 실행 목록 한 번에 읽는 줄 수(서버 상한 50). */
export const RUN_LIST_LIMIT = 50;
/** 모듈 id. */
export const MODULE = 'drafting';

/** 쓰기 거절 중 화면이 가르는 code. */
export const WRITE_CODES = [
  'VALIDATION_ERROR',
  'DOCUMENT_NO_TEXT_LAYER',
  'RUN_NOT_DONE',
  'NOT_FOUND',
  'AI_SETTING_UNUSABLE',
  'INVALID_OPTIONS',
  'IDEMPOTENCY_KEY_REUSED',
] as const;
export type WriteCode = (typeof WRITE_CODES)[number];

export type { CompanyRefusal };

export type ReadOutcome<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'not_found' }
  | { kind: 'failed' };

/** 결과 읽기 — 끝나기 전(409 RUN_NOT_DONE)은 not_done. */
export type ResultOutcome = ReadOutcome<DraftingResult> | { kind: 'not_done' };

export type WriteOutcome<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'rejected'; code: WriteCode | null; fields: FailureFields }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

/** 올린 PDF(confirm 답). hasText null = 서버가 아직 모른다(PUT 에 맡김). */
export interface UploadedPdf {
  documentId: number;
  pageCount: number | null;
  hasText: boolean | null;
}

/** 달린 문서의 이름·쪽 수(목차 설정 부제). */
export interface DocumentInfo {
  fileName: string;
  pageCount: number | null;
}

export type PdfOutcome =
  { kind: 'ready'; file: File } | { kind: 'missing' } | { kind: 'failed' };

export type DownloadOutcome =
  { kind: 'ok'; blob: Blob; fileName: string } | { kind: 'failed' };

export interface DraftingStore {
  listProjects(): Promise<ReadOutcome<ProjectPage>>;
  getProject(projectId: number): Promise<ReadOutcome<Project>>;
  createProject(body: {
    year: number;
    name: string;
  }): Promise<WriteOutcome<Project>>;
  /** signal 이 끊기면 서명 PUT 을 끊고 confirm 을 보내지 않는다. */
  uploadPdf(
    file: File,
    signal?: AbortSignal,
  ): Promise<WriteOutcome<UploadedPdf>>;
  attachDocument(
    projectId: number,
    documentId: number,
  ): Promise<WriteOutcome<Project>>;
  saveOutline(
    projectId: number,
    nodes: readonly OutlineNode[],
  ): Promise<WriteOutcome<{ outlineId: number }>>;
  getDocument(documentId: number): Promise<ReadOutcome<DocumentInfo>>;
  /** outlineRef = 저장한 목차 판 id(모르면 null) — 열쇠를 가르는 값(서버로 가지 않는다). */
  startRun(
    options: RunOptions,
    outlineRef: number | null,
  ): Promise<WriteOutcome<{ runId: number }>>;
  getRun(runId: number): Promise<ReadOutcome<RunState>>;
  getResult(runId: number): Promise<ResultOutcome>;
  getChanges(
    projectId: number,
    baseRunId: number,
  ): Promise<ReadOutcome<OutlineChanges>>;
  openPdf(documentId: number): Promise<PdfOutcome>;
  downloadDocx(runId: number): Promise<DownloadOutcome>;
  listRuns(projectId: number): Promise<ReadOutcome<RunPage>>;
}

/** 서명 주소로 파일 본문을 올리는 함수(틀이 준다 — Authorization 을 싣지 않는다). 실패는 던진다. */
export type SendUpload = (
  url: string,
  method: string,
  file: File,
  signal?: AbortSignal,
) => Promise<void>;

/** 열쇠를 짓는 함수(시험이 고정한다). */
export type NewKey = () => string;

export const newKey: NewKey = () => crypto.randomUUID().toLowerCase();

/** 아직 만들어지지 않은 실행의 열쇠들 — `${projectId}|${outlineRef}|${본문}` → 열쇠·launchKey. */
export type PendingRuns = Map<string, { key: string; launchKey: string }>;

/** 경로 컴포넌트가 다시 마운트돼 저장소가 새로 나도 살아야 한다(RPW2 M5). 탭·새로 고침을 넘지는 않는다. */
const PENDING_RUNS: PendingRuns = new Map();

export interface DraftingStoreDeps {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
  sendUpload: SendUpload;
  /** 새 Idempotency-Key. 기본 newKey. */
  newKey?: NewKey;
  /** 새 launchKey. 기본 newKey. */
  newLaunchKey?: NewKey;
  /** 아직 만들어지지 않은 실행의 표. 기본은 모듈 표(시험은 새 Map 을 넣을 수 있다). */
  pendingRuns?: PendingRuns;
}

type Sent = { data: unknown; response?: Response } | { failure: ApiFailure };

/** 한 번 보낸다. 실패는 갈래로(던지지 않는다). */
async function attempt<T>(
  send: () => Promise<{ data?: T; response?: Response }>,
): Promise<Sent> {
  try {
    const { data, response } = await send();
    if (data === undefined) return { failure: { kind: 'network' } };
    return { data, response };
  } catch (error) {
    return { failure: asFailure(error) };
  }
}

const isNotFound = (failure: ApiFailure) =>
  failure.kind === 'api' &&
  (failure.code === 'NOT_FOUND' || failure.status === 404);

function readFailure(failure: ApiFailure): ReadOutcome<never> {
  const company = companyRefusalOf(failure);
  if (company) return { kind: 'refused', company };
  if (isNotFound(failure)) return { kind: 'not_found' };
  return { kind: 'failed' };
}

function writeFailure(failure: ApiFailure): WriteOutcome<never> {
  if (failure.kind !== 'api') return { kind: 'failed' };
  const company = companyRefusalOf(failure);
  if (company) return { kind: 'refused', company };
  if (failure.status >= 500) return { kind: 'failed' };
  const known = (WRITE_CODES as readonly string[]).includes(failure.code);
  return {
    kind: 'rejected',
    code: known ? (failure.code as WriteCode) : null,
    fields: known ? failure.fields : {},
  };
}

function read<T>(
  sent: Sent,
  parse: (value: unknown) => T | null,
): ReadOutcome<T> {
  if ('failure' in sent) return readFailure(sent.failure);
  const value = parse(sent.data);
  return value === null ? { kind: 'failed' } : { kind: 'ok', value };
}

function written<T>(
  sent: Sent,
  parse: (value: unknown) => T | null,
): WriteOutcome<T> {
  if ('failure' in sent) return writeFailure(sent.failure);
  const value = parse(sent.data);
  return value === null ? { kind: 'failed' } : { kind: 'ok', value };
}

/** Blob 꼴인가(전역 Blob 이 실행 환경마다 다를 수 있어 모양으로 본다). */
const isBlob = (value: unknown): value is Blob =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as Blob).size === 'number' &&
  typeof (value as Blob).arrayBuffer === 'function';

/** Content-Disposition 의 파일 이름(영문번역 api/server.ts:119 fileNameFromDisposition 을 옮겨 적음). */
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

/** RunOut → RunState(module 이 drafting 이 아니면 null — not_found). */
function runStateOf(value: unknown): RunState | null | 'other' {
  const run = parseRunOut(value);
  if (run === null) return null;
  if (run.module !== MODULE) return 'other';
  const options = parseRunOptions(run.options);
  return {
    id: run.id,
    status: run.status,
    steps: run.steps.map(({ step, status, done, total }) => ({
      step,
      status,
      done,
      total,
    })),
    projectId: options?.projectId ?? null,
    base: options?.base ?? null,
  };
}

export function createDraftingStore({
  api,
  sendUpload,
  newKey: makeKey = newKey,
  newLaunchKey: makeLaunchKey = newKey,
  pendingRuns = PENDING_RUNS,
}: DraftingStoreDeps): DraftingStore {
  const { client } = api;
  /** 문서 id → 여는 중이거나 연 PDF(한 벌 — 실패는 지운다). */
  const pdfs = new Map<number, Promise<PdfOutcome>>();

  async function fetchPdf(documentId: number): Promise<PdfOutcome> {
    let answer: { data?: unknown; response: Response };
    try {
      answer = await client.GET('/documents/{document_id}/file', {
        params: { path: { document_id: documentId } },
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
      ) ?? `document-${documentId}.pdf`;
    return {
      kind: 'ready',
      file: new File([answer.data], name, { type: 'application/pdf' }),
    };
  }

  return {
    async listProjects() {
      const sent = await attempt(() =>
        client.GET('/drafting/projects', {
          params: { query: { limit: PROJECT_LIST_LIMIT, offset: 0 } },
        }),
      );
      return read(sent, parseProjectPage);
    },

    async getProject(projectId) {
      const sent = await attempt(() =>
        client.GET('/drafting/projects/{project_id}', {
          params: { path: { project_id: projectId } },
        }),
      );
      return read(sent, parseProject);
    },

    async createProject({ year, name }) {
      const sent = await attempt(() =>
        client.POST('/drafting/projects', {
          body: { year, name: name.trim() },
        }),
      );
      return written(sent, parseProject);
    },

    async uploadPdf(file, signal) {
      const created = await attempt(() =>
        client.POST('/documents', {
          body: { fileName: file.name, sizeBytes: file.size },
        }),
      );
      if ('failure' in created) return writeFailure(created.failure);
      const made = parseDocumentCreated(created.data);
      if (made === null) return { kind: 'failed' };
      try {
        await sendUpload(made.upload.url, made.upload.method, file, signal);
      } catch {
        return { kind: 'failed' };
      }
      if (signal?.aborted) return { kind: 'failed' };
      const documentId = made.document.id;
      const confirmed = await attempt(() =>
        client.POST('/documents/{document_id}/confirm', {
          params: { path: { document_id: documentId } },
        }),
      );
      return written(confirmed, (value) => {
        const status = parseDocumentStatus(value);
        if (status === null || status.document.id !== documentId) return null;
        return {
          documentId,
          pageCount: status.document.pageCount,
          hasText: status.document.hasText,
        };
      });
    },

    async attachDocument(projectId, documentId) {
      const sent = await attempt(() =>
        client.PUT('/drafting/projects/{project_id}/document', {
          params: { path: { project_id: projectId } },
          body: { documentId },
        }),
      );
      return written(sent, parseProject);
    },

    async saveOutline(projectId, nodes) {
      const sent = await attempt(() =>
        client.PUT('/drafting/projects/{project_id}/outline', {
          params: { path: { project_id: projectId } },
          body: {
            nodes: nodes.map(
              ({ key, parentKey, depth, title, requirement }) => ({
                key,
                parentKey,
                depth,
                title,
                requirement,
              }),
            ),
          },
        }),
      );
      return written(sent, (value) => {
        const put = parseOutlinePut(value);
        return put && { outlineId: put.outlineId };
      });
    },

    async getDocument(documentId) {
      const sent = await attempt(() =>
        client.GET('/documents/{document_id}', {
          params: { path: { document_id: documentId } },
        }),
      );
      return read(sent, (value) => {
        const status = parseDocumentStatus(value);
        return (
          status && {
            fileName: status.document.fileName,
            pageCount: status.document.pageCount,
          }
        );
      });
    },

    async startRun(options, outlineRef) {
      const checked = parseRunOptions(options);
      if (checked === null) return { kind: 'failed' };
      const slot = `${checked.projectId}|${outlineRef}|${JSON.stringify(checked)}`;
      const held = pendingRuns.get(slot) ?? {
        key: makeKey(),
        launchKey: makeLaunchKey(),
      };
      pendingRuns.set(slot, held);
      const { key, launchKey } = held;
      const sent = await attempt(() =>
        client.POST('/runs', {
          params: { header: { 'Idempotency-Key': key } },
          body: { module: MODULE, launchKey, options: { ...checked } },
        }),
      );
      const out = written(sent, (value) => {
        const run = parseRunCreated(value);
        return run && { runId: run.id };
      });
      if (out.kind === 'ok' || out.kind === 'rejected')
        pendingRuns.delete(slot);
      return out;
    },

    async getRun(runId) {
      const sent = await attempt(() =>
        client.GET('/runs/{run_id}', { params: { path: { run_id: runId } } }),
      );
      if ('failure' in sent) return readFailure(sent.failure);
      const run = runStateOf(sent.data);
      if (run === 'other') return { kind: 'not_found' };
      return run === null ? { kind: 'failed' } : { kind: 'ok', value: run };
    },

    async getResult(runId) {
      const sent = await attempt(() =>
        client.GET('/drafting/runs/{run_id}/result', {
          params: { path: { run_id: runId } },
        }),
      );
      if (
        'failure' in sent &&
        sent.failure.kind === 'api' &&
        sent.failure.code === 'RUN_NOT_DONE'
      )
        return { kind: 'not_done' };
      return read(sent, parseResult);
    },

    async getChanges(projectId, baseRunId) {
      const sent = await attempt(() =>
        client.GET('/drafting/projects/{project_id}/outline/changes', {
          params: { path: { project_id: projectId }, query: { baseRunId } },
        }),
      );
      return read(sent, parseChanges);
    },

    openPdf(documentId) {
      const held = pdfs.get(documentId);
      if (held) return held;
      const got = fetchPdf(documentId).then((pdf) => {
        if (pdf.kind !== 'ready') pdfs.delete(documentId);
        return pdf;
      });
      pdfs.set(documentId, got);
      return got;
    },

    async downloadDocx(runId) {
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET('/drafting/runs/{run_id}/result.docx', {
          params: { path: { run_id: runId } },
          parseAs: 'blob',
        });
      } catch {
        return { kind: 'failed' };
      }
      if (!isBlob(answer.data)) return { kind: 'failed' };
      const fileName =
        fileNameFromDisposition(
          answer.response.headers.get('Content-Disposition'),
        ) ?? `draft-${runId}.docx`;
      return { kind: 'ok', blob: answer.data, fileName };
    },

    async listRuns(projectId) {
      const sent = await attempt(() =>
        client.GET('/drafting/projects/{project_id}/runs', {
          params: {
            path: { project_id: projectId },
            query: { limit: RUN_LIST_LIMIT, offset: 0 },
          },
        }),
      );
      return read(sent, parseRunPage);
    },
  };
}
