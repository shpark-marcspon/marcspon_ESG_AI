// Scope 1·2 입력 실어댑터(밴드 W12-1a ② — 서버 S12a, sid:MARC-ENT-469 2·4). selection.ts 꼴. 경로 열(/inventory 뒤, X = /scope12/years/{year}/indexes/{node_id}):
//     years      GET    /scope12/years                          → EntryYearsOut 의 years(새 해 먼저)
//     rows       GET    /scope12/rows?year=&q=                  → EntryRowsOut(q 는 빈 글이면 싣지 않는다 · 설정 안 된 해 = configured 거짓)
//     detail     GET    X                                       → EntryIndexOut
//     saveRows   PUT    X/sites/{site_id}/rows {rows}           → EntryIndexOut(본문은 model 의 rowBody·saveBody — 보내는 칸 규칙)
//     deleteRows POST   X/rows/delete {ids: 정수[]}             → 지운 수(하나라도 없으면 404)
//     memo       PUT    X/memo {memo}                           → 저장된 메모
//     lock       POST   X/lock                                  → EntryIndexOut
//     unlock     DELETE X/lock                                  → EntryIndexOut(운영 관리자만 — 고객사 403 forbidden · 회사 둘 400 → refused)
//     decimals   PUT    /scope12/years/{year}/decimals {decimals} → 저장된 자릿수
//     history    GET    X/rows/{row_id}/history?page=&pageSize= → EntryHistoryPageOut(새 것 먼저)
//     period     PUT    X/sites/{site_id}/period {period}       → EntryIndexOut(S7 — 같은 주기면 0 바뀜 · 옛 칸 값은 숨김, W12-2 ①)
//     restore    POST   X/rows/{row_id}/history/{history_id}/restore {}|{reason} → EntryIndexOut(S12 — 사유를 주면 {reason}(계수 줄 · W12-3 S11), 아니면 {})
//     setRowFactor PUT  X/rows/{row_id}/factor {factorId|custom, reason} → EntryIndexOut(S9·S11 — 운영 관리자만 · 직접입력 단위 거절은
//                                                              422 fields.custom.<칸>, sid:MARC-ISSUE-548 · W12-3 ②)
//     template   GET    /scope12/years/{year}/template?scope=&siteId= → xlsx(S4 양식 · scope 1·2 는 풀 트리 n번째 뿌리 · W12-5 ①)
//     exportFile GET    /scope12/years/{year}/export?scope=     → xlsx(S5 · scope all·1·2 · 이름은 서버의 Content-Disposition)
//     upload     POST   /scope12/years/{year}/uploads           → EntryUploadOut(본문 = xlsx 맨 바이트, 쿼리 0 — multipart 아님)
// 넣어 준 Api(세션 api)만 쓴다. companyId 0(서버가 작업 회사를 정한다). 경로 id·본문 ids 는 정수(model 의 toRequestId — 아니면 요청 없이 failed),
// 응답 id 글자(sid:MARC-ISSUE-92). 금액·배출량은 글자 그대로 들고 보낸다.
// 갈래: 읽기 ok | notFound(404) | refused(회사 거절 셋 — companyRefusalOf) | failed · 쓰기는 거기에 rejected{code, fields}(code 는
//   VALIDATION_ERROR·RESTORE_STALE(409 — 복구할 줄이 낡음), 그 밖 거절은 null) · locked(409 LOCKED) · forbidden(403 FORBIDDEN — 고객사 풀기). 서버 message 는 싣지 않는다.
//   올리기는 자기 갈래(EntryUploadSent): rejected 는 INVALID_UPLOAD 만이고 fields 글이 곧 화면 글이다. 그 밖 422·꼴 틀림·끊김은 failed —
//   ★ failed 는 서버가 안 했다는 뜻이 아니다(커밋 뒤 답만 끊길 수 있다). 화면은 표를 다시 읽고 결과를 모른다고 말한다.
import { asFailure, companyRefusalOf } from '../../../shared/api/index.ts';
import type {
  Api,
  ApiFailure,
  CompanyRefusal,
  FailureFields,
} from '../../../shared/api/index.ts';
import { toRequestId } from '../model/index.ts';
import type {
  EntryHistoryPage,
  EntryIndex,
  EntryPeriod,
  EntryRowBody,
  EntryRows,
  EntryUploadResult,
  EntryYear,
  FactorBody,
} from '../model/index.ts';
import {
  parseEntryCount,
  parseEntryDecimals,
  parseEntryHistoryPage,
  parseEntryIndex,
  parseEntryMemo,
  parseEntryRows,
  parseEntryUpload,
  parseEntryYears,
} from './contract/index.ts';

/** 입력 쓰기 거절 중 화면이 가르는 code. */
export const ENTRY_WRITE_CODES = ['VALIDATION_ERROR', 'RESTORE_STALE'] as const;
export type EntryWriteCode = (typeof ENTRY_WRITE_CODES)[number];

/** 히스토리 한 쪽의 크기(서버 상한 100). */
export const ENTRY_HISTORY_PAGE_SIZE = 20;

export type EntryRead<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'notFound' }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

export type EntryWrite<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'rejected'; code: EntryWriteCode | null; fields: FailureFields }
  | { kind: 'locked' }
  | { kind: 'notFound' }
  | { kind: 'forbidden' }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

/** 내려받은 파일 하나(이름은 서버가 정한다). */
export interface EntryFile {
  blob: Blob;
  fileName: string;
}

/** 일괄 올리기의 답. ★ failed = 결과를 모름(안 됐다는 뜻이 아니다). */
export type EntryUploadSent =
  | { kind: 'ok'; value: EntryUploadResult }
  | { kind: 'rejected'; fields: FailureFields }
  | { kind: 'tooLarge' }
  | { kind: 'locked' }
  | { kind: 'notFound' }
  | { kind: 'refused'; company: CompanyRefusal }
  /** 파일을 못 읽어 요청을 보내지 않음(고른 뒤 디스크에서 바뀜) — 결과를 모르는 failed 와 다르다. */
  | { kind: 'unreadable' }
  | { kind: 'failed' };

/** 리스트 읽기 — 검색 q 의 422(VALIDATION_ERROR)만 rejected(fields 그대로 — 화면은 fields.q 를 검색 줄 아래에). */
export type EntryRowsRead =
  EntryRead<EntryRows> | { kind: 'rejected'; fields: FailureFields };

export interface GhgEntryPort {
  years(): Promise<EntryRead<EntryYear[]>>;
  /** q 는 앞뒤 공백을 걷어 빈 글이면 싣지 않는다. */
  rows(year: number, q?: string): Promise<EntryRowsRead>;
  detail(year: number, nodeId: string): Promise<EntryRead<EntryIndex>>;
  /** rows 는 model 의 saveBody(…).rows — 이 어댑터는 본문을 고치지 않는다. */
  saveRows(
    year: number,
    nodeId: string,
    siteId: string,
    rows: readonly EntryRowBody[],
  ): Promise<EntryWrite<EntryIndex>>;
  /** 지운 행 수. */
  deleteRows(
    year: number,
    nodeId: string,
    ids: readonly string[],
  ): Promise<EntryWrite<number>>;
  /** 저장된 메모(빈 글 = 비움). */
  memo(year: number, nodeId: string, text: string): Promise<EntryWrite<string>>;
  lock(year: number, nodeId: string): Promise<EntryWrite<EntryIndex>>;
  unlock(year: number, nodeId: string): Promise<EntryWrite<EntryIndex>>;
  /** 저장된 자릿수. */
  decimals(year: number, n: number): Promise<EntryWrite<number>>;
  history(
    year: number,
    nodeId: string,
    rowId: string,
    page: number,
  ): Promise<EntryRead<EntryHistoryPage>>;
  /** 사업장 블록의 입력주기(S7). 응답은 상세 — 그 블록의 slots·values 가 새 주기 꼴. */
  period(
    year: number,
    nodeId: string,
    siteId: string,
    period: EntryPeriod,
  ): Promise<EntryWrite<EntryIndex>>;
  /** 히스토리 줄의 뒤 상태로 되돌리는 새 줄(S12). 사유를 주면 본문 {reason}(계수 줄 — S11), 안 주면 {}. 응답은 상세. */
  restore(
    year: number,
    nodeId: string,
    rowId: string,
    historyId: string,
    reason?: string,
  ): Promise<EntryWrite<EntryIndex>>;
  /** 행 하나의 계수 바꿈(S9·S11 — 운영 관리자만): 같은 잎의 풀 계수(factorId) 또는 직접입력(custom) 하나 + 사유. 응답은 상세. */
  setRowFactor(
    year: number,
    nodeId: string,
    rowId: string,
    target: EntryFactorTarget,
    reason: string,
  ): Promise<EntryWrite<EntryIndex>>;
  /** 일괄 올리기 양식(S4). siteId 는 정수 글자(아니면 요청 없이 failed). */
  template(
    year: number,
    scope: 1 | 2,
    siteId: string,
  ): Promise<EntryRead<EntryFile>>;
  /** 데이터 엑셀(S5). */
  exportFile(year: number, scope: 'all' | 1 | 2): Promise<EntryRead<EntryFile>>;
  /** 양식을 맨 바이트로 올린다(S4). 연도·사업장은 양식이 말한다. */
  upload(year: number, file: File): Promise<EntryUploadSent>;
}

/** 계수 바꿈의 대상 — 풀 계수 id(글자, 보낼 때 정수) 또는 직접입력 본문(GhgFactorIn 꼴). */
export type EntryFactorTarget = { factorId: string } | { custom: FactorBody };

export interface CreateGhgEntryPortOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
}

type Sent = { data: unknown } | { failure: ApiFailure };

async function attempt<T>(send: () => Promise<{ data?: T }>): Promise<Sent> {
  try {
    const { data } = await send();
    if (data === undefined) return { failure: { kind: 'network' } };
    return { data };
  } catch (error) {
    return { failure: asFailure(error) };
  }
}

/** 경로·본문 id 를 정수로(하나라도 아니면 null — 요청 없이 failed). */
function requestIds(ids: readonly string[]): number[] | null {
  try {
    return ids.map(toRequestId);
  } catch {
    return null;
  }
}

const isNotFound = (failure: ApiFailure) =>
  failure.kind === 'api' && failure.code === 'NOT_FOUND';

function readFailure(failure: ApiFailure): EntryRead<never> {
  const company = companyRefusalOf(failure);
  if (company) return { kind: 'refused', company };
  return isNotFound(failure) ? { kind: 'notFound' } : { kind: 'failed' };
}

function writeFailure(failure: ApiFailure): EntryWrite<never> {
  if (failure.kind !== 'api') return { kind: 'failed' };
  const company = companyRefusalOf(failure);
  if (company) return { kind: 'refused', company };
  if (failure.code === 'LOCKED') return { kind: 'locked' };
  if (failure.code === 'NOT_FOUND') return { kind: 'notFound' };
  if (failure.code === 'FORBIDDEN') return { kind: 'forbidden' };
  const known = (ENTRY_WRITE_CODES as readonly string[]).includes(failure.code);
  return {
    kind: 'rejected',
    code: known ? (failure.code as EntryWriteCode) : null,
    fields: known ? failure.fields : {},
  };
}

function uploadFailure(failure: ApiFailure): EntryUploadSent {
  if (failure.kind !== 'api') return { kind: 'failed' };
  const company = companyRefusalOf(failure);
  if (company) return { kind: 'refused', company };
  switch (failure.code) {
    case 'INVALID_UPLOAD':
      return { kind: 'rejected', fields: failure.fields };
    case 'BODY_TOO_LARGE':
      return { kind: 'tooLarge' };
    case 'LOCKED':
      return { kind: 'locked' };
    case 'NOT_FOUND':
      return { kind: 'notFound' };
    default:
      return { kind: 'failed' };
  }
}

const isBlob = (value: unknown): value is Blob =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as Blob).arrayBuffer === 'function';

/**
 * Content-Disposition → 파일 이름(Scope 3 api/server.ts fileNameFromDisposition 을 옮겨 적음 — 남의 칸이라 import 0):
 * filename*=UTF-8''… 가 있으면 그것, 없으면 filename="…"·filename=…. 경로 글자는 지운다. 못 읽으면 null.
 */
function fileNameFromDisposition(header: string | null): string | null {
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

/** 서버 이름을 못 읽었을 때의 이름. */
const TEMPLATE_FILE_NAME = 'scope12-template.xlsx';
const EXPORT_FILE_NAME = 'scope12-data.xlsx';
const XLSX_MEDIA_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

/** 파일 읽기 한 번(parseAs blob). 이름은 응답 머리에서. */
async function fileOf(
  send: () => Promise<{ data?: unknown; response: Response }>,
  fallbackName: string,
): Promise<EntryRead<EntryFile>> {
  let answer: { data?: unknown; response: Response };
  try {
    answer = await send();
  } catch (error) {
    return readFailure(asFailure(error));
  }
  if (!isBlob(answer.data)) return { kind: 'failed' };
  return {
    kind: 'ok',
    value: {
      blob: answer.data,
      fileName:
        fileNameFromDisposition(
          answer.response.headers.get('Content-Disposition'),
        ) ?? fallbackName,
    },
  };
}

/** 받은 값을 거울로 읽는다 — 꼴이 틀리면 failed. */
function readWith<T, U>(
  sent: Sent,
  parse: (value: unknown) => T | null,
  pick: (value: T) => U,
): EntryRead<U> {
  if ('failure' in sent) return readFailure(sent.failure);
  const value = parse(sent.data);
  return value === null ?
      { kind: 'failed' }
    : { kind: 'ok', value: pick(value) };
}

function writeWith<T, U>(
  sent: Sent,
  parse: (value: unknown) => T | null,
  pick: (value: T) => U,
): EntryWrite<U> {
  if ('failure' in sent) return writeFailure(sent.failure);
  const value = parse(sent.data);
  return value === null ?
      { kind: 'failed' }
    : { kind: 'ok', value: pick(value) };
}

const same = <T>(value: T) => value;

export function createGhgEntryPort({
  api,
}: CreateGhgEntryPortOptions): GhgEntryPort {
  const { client } = api;
  /** 해·잎 경로 인자(정수가 아니면 null). */
  const indexPath = (year: number, nodeId: string) => {
    const [node] = requestIds([nodeId]) ?? [];
    return Number.isInteger(year) && node !== undefined ?
        { year, node_id: node }
      : null;
  };
  return {
    async years() {
      const sent = await attempt(() => client.GET('/inventory/scope12/years'));
      return readWith(sent, parseEntryYears, (value) => value.years);
    },

    async rows(year, q) {
      if (!Number.isInteger(year)) return { kind: 'failed' };
      const search = q?.trim() ?? '';
      const sent = await attempt(() =>
        client.GET('/inventory/scope12/rows', {
          params: { query: search === '' ? { year } : { year, q: search } },
        }),
      );
      if (
        'failure' in sent &&
        sent.failure.kind === 'api' &&
        sent.failure.code === 'VALIDATION_ERROR'
      )
        return { kind: 'rejected', fields: sent.failure.fields };
      return readWith(sent, parseEntryRows, same);
    },

    async detail(year, nodeId) {
      const path = indexPath(year, nodeId);
      if (path === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.GET('/inventory/scope12/years/{year}/indexes/{node_id}', {
          params: { path },
        }),
      );
      return readWith(sent, parseEntryIndex, same);
    },

    async saveRows(year, nodeId, siteId, rows) {
      const path = indexPath(year, nodeId);
      const [site] = requestIds([siteId]) ?? [];
      if (path === null || site === undefined) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.PUT(
          '/inventory/scope12/years/{year}/indexes/{node_id}/sites/{site_id}/rows',
          {
            params: { path: { ...path, site_id: site } },
            body: { rows: [...rows] },
          },
        ),
      );
      return writeWith(sent, parseEntryIndex, same);
    },

    async deleteRows(year, nodeId, ids) {
      const path = indexPath(year, nodeId);
      const body = requestIds(ids);
      if (path === null || body === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST(
          '/inventory/scope12/years/{year}/indexes/{node_id}/rows/delete',
          { params: { path }, body: { ids: body } },
        ),
      );
      return writeWith(sent, parseEntryCount, (value) => value.count);
    },

    async memo(year, nodeId, text) {
      const path = indexPath(year, nodeId);
      if (path === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.PUT('/inventory/scope12/years/{year}/indexes/{node_id}/memo', {
          params: { path },
          body: { memo: text },
        }),
      );
      return writeWith(sent, parseEntryMemo, (value) => value.memo);
    },

    async lock(year, nodeId) {
      const path = indexPath(year, nodeId);
      if (path === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST('/inventory/scope12/years/{year}/indexes/{node_id}/lock', {
          params: { path },
        }),
      );
      return writeWith(sent, parseEntryIndex, same);
    },

    async unlock(year, nodeId) {
      const path = indexPath(year, nodeId);
      if (path === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.DELETE(
          '/inventory/scope12/years/{year}/indexes/{node_id}/lock',
          { params: { path } },
        ),
      );
      return writeWith(sent, parseEntryIndex, same);
    },

    async decimals(year, n) {
      if (!Number.isInteger(year) || !Number.isInteger(n))
        return { kind: 'failed' };
      const sent = await attempt(() =>
        client.PUT('/inventory/scope12/years/{year}/decimals', {
          params: { path: { year } },
          body: { decimals: n },
        }),
      );
      return writeWith(sent, parseEntryDecimals, (value) => value.decimals);
    },

    async history(year, nodeId, rowId, page) {
      const path = indexPath(year, nodeId);
      const [row] = requestIds([rowId]) ?? [];
      if (path === null || row === undefined || !Number.isInteger(page))
        return { kind: 'failed' };
      const sent = await attempt(() =>
        client.GET(
          '/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/history',
          {
            params: {
              path: { ...path, row_id: row },
              query: { page, pageSize: ENTRY_HISTORY_PAGE_SIZE },
            },
          },
        ),
      );
      return readWith(sent, parseEntryHistoryPage, same);
    },

    async period(year, nodeId, siteId, period) {
      const path = indexPath(year, nodeId);
      const [site] = requestIds([siteId]) ?? [];
      if (path === null || site === undefined) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.PUT(
          '/inventory/scope12/years/{year}/indexes/{node_id}/sites/{site_id}/period',
          { params: { path: { ...path, site_id: site } }, body: { period } },
        ),
      );
      return writeWith(sent, parseEntryIndex, same);
    },

    async restore(year, nodeId, rowId, historyId, reason) {
      const path = indexPath(year, nodeId);
      const [row, history] = requestIds([rowId, historyId]) ?? [];
      if (path === null || row === undefined || history === undefined)
        return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST(
          '/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/history/{history_id}/restore',
          {
            params: { path: { ...path, row_id: row, history_id: history } },
            body: reason === undefined ? {} : { reason },
          },
        ),
      );
      return writeWith(sent, parseEntryIndex, same);
    },

    async setRowFactor(year, nodeId, rowId, target, reason) {
      const path = indexPath(year, nodeId);
      const [row] = requestIds([rowId]) ?? [];
      if (path === null || row === undefined) return { kind: 'failed' };
      let body:
        | { factorId: number; reason: string }
        | { custom: FactorBody; reason: string };
      if ('factorId' in target) {
        const [factorId] = requestIds([target.factorId]) ?? [];
        if (factorId === undefined) return { kind: 'failed' };
        body = { factorId, reason };
      } else body = { custom: target.custom, reason };
      const sent = await attempt(() =>
        client.PUT(
          '/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/factor',
          { params: { path: { ...path, row_id: row } }, body },
        ),
      );
      return writeWith(sent, parseEntryIndex, same);
    },

    async template(year, scope, siteId) {
      const [site] = requestIds([siteId]) ?? [];
      if (!Number.isInteger(year) || site === undefined)
        return { kind: 'failed' };
      return fileOf(
        () =>
          client.GET('/inventory/scope12/years/{year}/template', {
            params: {
              path: { year },
              query: { scope: `${scope}`, siteId: site },
            },
            parseAs: 'blob',
          }),
        TEMPLATE_FILE_NAME,
      );
    },

    async exportFile(year, scope) {
      if (!Number.isInteger(year)) return { kind: 'failed' };
      return fileOf(
        () =>
          client.GET('/inventory/scope12/years/{year}/export', {
            params: { path: { year }, query: { scope: `${scope}` } },
            parseAs: 'blob',
          }),
        EXPORT_FILE_NAME,
      );
    },

    async upload(year, file) {
      if (!Number.isInteger(year)) return { kind: 'failed' };
      let bytes: Uint8Array;
      try {
        bytes = new Uint8Array(await file.arrayBuffer());
      } catch {
        return { kind: 'unreadable' };
      }
      const sent = await attempt(() =>
        client.POST('/inventory/scope12/years/{year}/uploads', {
          params: { path: { year } },
          // 본문은 맨 바이트(multipart 아님 — 서버 경로의 선언). openapi 의 본문 타입은 글자라 바꿔 싣는다(데이터 검증 readEdkXlsx 꼴).
          body: bytes as unknown as string,
          bodySerializer: (value: unknown) => value as BodyInit,
          headers: { 'Content-Type': XLSX_MEDIA_TYPE },
        }),
      );
      if ('failure' in sent) return uploadFailure(sent.failure);
      const value = parseEntryUpload(sent.data);
      return value === null ? { kind: 'failed' } : { kind: 'ok', value };
    },
  };
}
