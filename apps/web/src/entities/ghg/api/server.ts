// 온실가스 조직구조 실어댑터(밴드 W12-0a ① — 서버 K1b-1 sid:MARC-TICK-358). 데이터 검증 AI 설정 실어댑터
// (entities/dataverify-setting/api/server.ts) 꼴을 따라 지음(가져오지 않는다). 경로 열하나:
//   createGhgOrganizationPort(S15 — 고객사 사용자·운영 관리자, 서버가 작업 회사를 정한다):
//     listBranches      GET  /branches?q=&page=&pageSize=      → BranchPageOut(q 는 빈 글이면 싣지 않는다)
//     getBranch         GET  /branches/{branch_id}             → BranchDetailOut(404 NOT_FOUND → missing)
//     createBranch      POST /branches {name, inventoryEnabled, facilities}          → 201 BranchDetailOut
//     saveBranch        PUT  /branches/{branch_id} {name, inventoryEnabled, facilities, updatedAt} → 200 BranchDetailOut(빠진 줄 = 삭제 표시 ·
//                       updatedAt 은 상세에서 받은 글자 그대로 — 다르면 409 STALE, 밴드 K1b-3)
//     setInventory      POST /branches/inventory {ids, enabled} → CountOut
//     deleteBranches    POST /branches/delete {ids}            → CountOut
//     listFacilityCodes GET  /facility-codes                   → FacilityCodesOut 의 items
//   createFacilityCodeAdminPort(S18 — 운영 관리자만, 고객사는 403):
//     list   GET   /admin/facility-codes?page=&pageSize=  → AdminFacilityCodePageOut(만든 차례)
//     create POST  /admin/facility-codes {name}           → FacilityCodeOut
//     rename PATCH /admin/facility-codes/{code_id} {name} → FacilityCodeOut(code 는 그대로)
//     remove POST  /admin/facility-codes/delete {ids}     → CountOut
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. companyId 는 어느 요청에도 싣지 않는다.
// 요청 id 는 정수(model 의 toRequestId — 정수 글자가 아니면 요청 없이 failed), 응답 id 는 글자(sid:MARC-ISSUE-92).
// 갈래: 읽기 ok | refused(회사 거절 셋 — companyRefusalOf) | failed(꼴 틀림·그 밖 거절·끊김). 쓰기는 거기에 rejected{code, fields} —
//   code 는 다섯(VALIDATION_ERROR·HEADQUARTERS_LOCKED·IN_USE·NOT_FOUND·STALE)만, 그 밖 거절은 null. 서버 message 는 싣지 않는다(화면 0).
import { asFailure, companyRefusalOf } from '../../../shared/api/index.ts';
import type {
  Api,
  ApiFailure,
  CompanyRefusal,
  FailureFields,
} from '../../../shared/api/index.ts';
import { toRequestId } from '../model/index.ts';
import type {
  AdminFacilityCodePage,
  BranchDetail,
  BranchPage,
  BranchPutBody,
  BranchSaveBody,
  FacilityCode,
} from '../model/index.ts';
import {
  parseAdminFacilityCodePage,
  parseBranchDetail,
  parseBranchPage,
  parseCount,
  parseFacilityCode,
  parseFacilityCodes,
} from './contract/index.ts';

/** S15 목록 한 쪽의 크기(서버 기본값과 같다 — 서버 상한 100). */
export const BRANCH_PAGE_SIZE = 20;
/** S18 목록 한 쪽의 크기(AD-01 계정 목록 LIST_PAGE_SIZE 와 같다 — 서버 상한 100). */
export const FACILITY_CODE_PAGE_SIZE = 100;

/** 쓰기 거절 중 화면이 가르는 code 다섯(STALE = 낡은 판 — 밴드 K1b-3). */
export const WRITE_CODES = [
  'VALIDATION_ERROR',
  'HEADQUARTERS_LOCKED',
  'IN_USE',
  'NOT_FOUND',
  'STALE',
] as const;
export type WriteCode = (typeof WRITE_CODES)[number];

export type { CompanyRefusal };

export type ReadOutcome<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

export type DetailOutcome =
  | ReadOutcome<BranchDetail>
  /** 404 NOT_FOUND(없는 id·지운 사업장). */
  | { kind: 'missing' };

export type WriteOutcome<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'rejected'; code: WriteCode | null; fields: FailureFields }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

export interface BranchListQuery {
  q: string;
  page: number;
}

export interface GhgOrganizationPort {
  listBranches(query: BranchListQuery): Promise<ReadOutcome<BranchPage>>;
  getBranch(id: string): Promise<DetailOutcome>;
  createBranch(body: BranchSaveBody): Promise<WriteOutcome<BranchDetail>>;
  saveBranch(
    id: string,
    body: BranchPutBody,
  ): Promise<WriteOutcome<BranchDetail>>;
  /** 바뀐 행 수. */
  setInventory(
    ids: readonly string[],
    enabled: boolean,
  ): Promise<WriteOutcome<number>>;
  deleteBranches(ids: readonly string[]): Promise<WriteOutcome<number>>;
  listFacilityCodes(): Promise<ReadOutcome<FacilityCode[]>>;
}

export interface FacilityCodeAdminPort {
  list(page: number): Promise<ReadOutcome<AdminFacilityCodePage>>;
  create(name: string): Promise<WriteOutcome<FacilityCode>>;
  rename(id: string, name: string): Promise<WriteOutcome<FacilityCode>>;
  remove(ids: readonly string[]): Promise<WriteOutcome<number>>;
}

export interface CreateGhgPortOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
}

type Sent = { data: unknown } | { failure: ApiFailure };

/** 한 번 보낸다. 실패는 갈래로(던지지 않는다). */
async function attempt<T>(send: () => Promise<{ data?: T }>): Promise<Sent> {
  try {
    const { data } = await send();
    if (data === undefined) return { failure: { kind: 'network' } };
    return { data };
  } catch (error) {
    return { failure: asFailure(error) };
  }
}

function readFailure(failure: ApiFailure): ReadOutcome<never> {
  const company = companyRefusalOf(failure);
  return company ? { kind: 'refused', company } : { kind: 'failed' };
}

function writeFailure(failure: ApiFailure): WriteOutcome<never> {
  if (failure.kind !== 'api') return { kind: 'failed' };
  const company = companyRefusalOf(failure);
  if (company) return { kind: 'refused', company };
  const known = (WRITE_CODES as readonly string[]).includes(failure.code);
  return {
    kind: 'rejected',
    code: known ? (failure.code as WriteCode) : null,
    fields: known ? failure.fields : {},
  };
}

/** 받은 답을 거울로 읽어 쓰기 결과로. 꼴이 틀리면 failed. */
function written<T>(
  sent: Sent,
  parse: (value: unknown) => T | null,
): WriteOutcome<T> {
  if ('failure' in sent) return writeFailure(sent.failure);
  const value = parse(sent.data);
  return value === null ? { kind: 'failed' } : { kind: 'ok', value };
}

function read<T>(
  sent: Sent,
  parse: (value: unknown) => T | null,
): ReadOutcome<T> {
  if ('failure' in sent) return readFailure(sent.failure);
  const value = parse(sent.data);
  return value === null ? { kind: 'failed' } : { kind: 'ok', value };
}

/** 요청 id 들. 정수 글자가 아닌 것이 있으면 null(요청하지 않는다). */
function requestIds(ids: readonly string[]): number[] | null {
  try {
    return ids.map(toRequestId);
  } catch {
    return null;
  }
}

const requestId = (id: string): number | null => requestIds([id])?.[0] ?? null;

const countOf = (value: unknown) => parseCount(value)?.count ?? null;

export function createGhgOrganizationPort({
  api,
}: CreateGhgPortOptions): GhgOrganizationPort {
  const { client } = api;
  return {
    async listBranches({ q, page }) {
      const text = q.trim();
      const sent = await attempt(() =>
        client.GET('/branches', {
          params: {
            query: {
              ...(text === '' ? {} : { q: text }),
              page,
              pageSize: BRANCH_PAGE_SIZE,
            },
          },
        }),
      );
      return read(sent, parseBranchPage);
    },

    async getBranch(id) {
      const branchId = requestId(id);
      if (branchId === null) return { kind: 'missing' };
      const sent = await attempt(() =>
        client.GET('/branches/{branch_id}', {
          params: { path: { branch_id: branchId } },
        }),
      );
      if (
        'failure' in sent &&
        sent.failure.kind === 'api' &&
        sent.failure.code === 'NOT_FOUND'
      )
        return { kind: 'missing' };
      return read(sent, parseBranchDetail);
    },

    async createBranch({ name, inventoryEnabled, facilities }) {
      const sent = await attempt(() =>
        client.POST('/branches', {
          body: { name, inventoryEnabled, facilities },
        }),
      );
      return written(sent, parseBranchDetail);
    },

    async saveBranch(id, { name, inventoryEnabled, facilities, updatedAt }) {
      const branchId = requestId(id);
      if (branchId === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.PUT('/branches/{branch_id}', {
          params: { path: { branch_id: branchId } },
          body: { name, inventoryEnabled, facilities, updatedAt },
        }),
      );
      return written(sent, parseBranchDetail);
    },

    async setInventory(ids, enabled) {
      const body = requestIds(ids);
      if (body === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST('/branches/inventory', { body: { ids: body, enabled } }),
      );
      return written(sent, countOf);
    },

    async deleteBranches(ids) {
      const body = requestIds(ids);
      if (body === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST('/branches/delete', { body: { ids: body } }),
      );
      return written(sent, countOf);
    },

    async listFacilityCodes() {
      const sent = await attempt(() => client.GET('/facility-codes'));
      return read(sent, (value) => parseFacilityCodes(value)?.items ?? null);
    },
  };
}

export function createFacilityCodeAdminPort({
  api,
}: CreateGhgPortOptions): FacilityCodeAdminPort {
  const { client } = api;
  return {
    async list(page) {
      const sent = await attempt(() =>
        client.GET('/admin/facility-codes', {
          params: { query: { page, pageSize: FACILITY_CODE_PAGE_SIZE } },
        }),
      );
      return read(sent, parseAdminFacilityCodePage);
    },

    async create(name) {
      const sent = await attempt(() =>
        client.POST('/admin/facility-codes', { body: { name: name.trim() } }),
      );
      return written(sent, parseFacilityCode);
    },

    async rename(id, name) {
      const codeId = requestId(id);
      if (codeId === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.PATCH('/admin/facility-codes/{code_id}', {
          params: { path: { code_id: codeId } },
          body: { name: name.trim() },
        }),
      );
      return written(sent, parseFacilityCode);
    },

    async remove(ids) {
      const body = requestIds(ids);
      if (body === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST('/admin/facility-codes/delete', { body: { ids: body } }),
      );
      return written(sent, countOf);
    },
  };
}
