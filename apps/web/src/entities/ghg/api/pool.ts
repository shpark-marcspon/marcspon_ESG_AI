// 온실가스 인덱스 풀 실어댑터(밴드 W12-0b1 ② — 서버 K1b-2a, sid:MARC-ENT-469 3 공통 풀·운영 관리자만). server.ts 꼴. 경로 열둘(/inventory 뒤):
//     listNodes      GET   /admin/ghg-index/nodes?parentId=&q=           → GhgNodesOut 의 items(q 가 있으면 parentId 를 싣지 않는다)
//     createNode     POST  /admin/ghg-index/nodes {level, parentId?, name} → 201 GhgNodeOut(열 1~3)
//     renameNode     PATCH /admin/ghg-index/nodes/{node_id} {name}         → GhgNodeOut
//     deleteNodes    POST  /admin/ghg-index/nodes/delete {ids}             → GhgCountOut(잎이면 그 계수도)
//     getFacility    GET   /admin/ghg-index/facilities/{node_id}           → GhgFacilityOut
//     createFacility POST  /admin/ghg-index/facilities {parentId, facilityCodeId, unit, tooltip} → 201 GhgFacilityOut
//     saveFacility   PUT   /admin/ghg-index/facilities/{node_id} {facilityCodeId, unit, tooltip, defaultFactorId?} → GhgFacilityOut
//     createFactor   POST  /admin/ghg-index/facilities/{node_id}/factors GhgFactorIn → 201 GhgFactorOut(판 1)
//     getFactor      GET   /admin/ghg-factors/{factor_id}?version=         → GhgFactorOut
//     saveFactor     PUT   /admin/ghg-factors/{factor_id} GhgFactorIn       → GhgFactorOut(늘 새 판)
//     deleteFactors  POST  /admin/ghg-factors/delete {ids}                 → GhgCountOut(기본을 지우면 남은 첫 행이 기본)
//     options        GET   /admin/ghg-options                              → GhgOptionsOut
// 넣어 준 Api(세션 api)만 쓴다. companyId 0(공통 풀 — 회사를 고르지 않는다). 요청 id 정수(model 의 toRequestId — 아니면 요청 없이 failed).
// 갈래: 읽기 ok | failed(403 도 — 가드가 먼저 막는다) · 쓰기 ok | rejected{code, fields} | failed — code 는 넷
//   (VALIDATION_ERROR·NOT_FOUND·HAS_CHILDREN·IN_USE)만, 그 밖 null. 서버 message 는 싣지 않는다.
import { asFailure } from '../../../shared/api/index.ts';
import type {
  Api,
  ApiFailure,
  FailureFields,
} from '../../../shared/api/index.ts';
import { isPoolLevel, toRequestId } from '../model/index.ts';
import type {
  FacilityCreateDraft,
  FacilitySaveDraft,
  FactorBody,
  PoolFacility,
  PoolFactor,
  PoolLevel,
  PoolNode,
  PoolOptions,
} from '../model/index.ts';
import {
  parsePoolCount,
  parsePoolFacility,
  parsePoolFactor,
  parsePoolNode,
  parsePoolNodes,
  parsePoolOptions,
} from './contract/index.ts';

/** 풀 쓰기 거절 중 화면이 가르는 code 넷. */
export const POOL_WRITE_CODES = [
  'VALIDATION_ERROR',
  'NOT_FOUND',
  'HAS_CHILDREN',
  'IN_USE',
] as const;
export type PoolWriteCode = (typeof POOL_WRITE_CODES)[number];

export type PoolRead<T> = { kind: 'ok'; value: T } | { kind: 'failed' };

export type PoolWrite<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'rejected'; code: PoolWriteCode | null; fields: FailureFields }
  | { kind: 'failed' };

export interface PoolNodeQuery {
  parentId?: string | null;
  q?: string;
}

export interface PoolNodeCreate {
  level: Exclude<PoolLevel, 'facility'>;
  parentId?: string | null;
  name: string;
}

export interface GhgPoolAdminPort {
  listNodes(query: PoolNodeQuery): Promise<PoolRead<PoolNode[]>>;
  createNode(body: PoolNodeCreate): Promise<PoolWrite<PoolNode>>;
  renameNode(id: string, name: string): Promise<PoolWrite<PoolNode>>;
  /** 지운 수. */
  deleteNodes(ids: readonly string[]): Promise<PoolWrite<number>>;
  getFacility(id: string): Promise<PoolRead<PoolFacility>>;
  createFacility(draft: FacilityCreateDraft): Promise<PoolWrite<PoolFacility>>;
  saveFacility(
    id: string,
    draft: FacilitySaveDraft,
  ): Promise<PoolWrite<PoolFacility>>;
  createFactor(
    facilityId: string,
    draft: FactorBody,
  ): Promise<PoolWrite<PoolFactor>>;
  getFactor(id: string, version?: number): Promise<PoolRead<PoolFactor>>;
  saveFactor(id: string, draft: FactorBody): Promise<PoolWrite<PoolFactor>>;
  deleteFactors(ids: readonly string[]): Promise<PoolWrite<number>>;
  options(): Promise<PoolRead<PoolOptions>>;
}

export interface CreateGhgPoolPortOptions {
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

function read<T>(sent: Sent, parse: (value: unknown) => T | null): PoolRead<T> {
  if ('failure' in sent) return { kind: 'failed' };
  const value = parse(sent.data);
  return value === null ? { kind: 'failed' } : { kind: 'ok', value };
}

function written<T>(
  sent: Sent,
  parse: (value: unknown) => T | null,
): PoolWrite<T> {
  if ('failure' in sent) {
    const { failure } = sent;
    if (failure.kind !== 'api') return { kind: 'failed' };
    const known = (POOL_WRITE_CODES as readonly string[]).includes(
      failure.code,
    );
    return {
      kind: 'rejected',
      code: known ? (failure.code as PoolWriteCode) : null,
      fields: known ? failure.fields : {},
    };
  }
  const value = parse(sent.data);
  return value === null ? { kind: 'failed' } : { kind: 'ok', value };
}

function requestIds(ids: readonly string[]): number[] | null {
  try {
    return ids.map(toRequestId);
  } catch {
    return null;
  }
}
const requestId = (id: string): number | null => requestIds([id])?.[0] ?? null;

/** 거울을 지난 노드 → model 꼴(단 글자는 거울이 넷만 받았다 — 다시 본다). */
function nodeOf(raw: {
  id: string;
  level: string;
  name: string;
  parentId: string | null;
  sortOrder: number;
  childCount: number;
  facilityCode?: string | null;
  facilityCodeId?: string | null;
}): PoolNode | null {
  if (!isPoolLevel(raw.level)) return null;
  return {
    id: raw.id,
    level: raw.level,
    name: raw.name,
    parentId: raw.parentId,
    sortOrder: raw.sortOrder,
    childCount: raw.childCount,
    facilityCode: raw.facilityCode ?? null,
    facilityCodeId: raw.facilityCodeId ?? null,
  };
}

const nodesOf = (value: unknown): PoolNode[] | null => {
  const parsed = parsePoolNodes(value);
  if (!parsed) return null;
  const out = parsed.items.map(nodeOf);
  return out.every((node) => node !== null) ? (out as PoolNode[]) : null;
};
const oneNodeOf = (value: unknown): PoolNode | null => {
  const parsed = parsePoolNode(value);
  return parsed ? nodeOf(parsed) : null;
};
const countOf = (value: unknown) => parsePoolCount(value)?.count ?? null;

export function createGhgPoolAdminPort({
  api,
}: CreateGhgPoolPortOptions): GhgPoolAdminPort {
  const { client } = api;
  return {
    async listNodes({ parentId = null, q = '' }) {
      const text = q.trim();
      let parent: number | null = null;
      if (text === '' && parentId !== null) {
        parent = requestId(parentId);
        if (parent === null) return { kind: 'failed' };
      }
      const sent = await attempt(() =>
        client.GET('/inventory/admin/ghg-index/nodes', {
          params: {
            query:
              text !== '' ? { q: text }
              : parent !== null ? { parentId: parent }
              : {},
          },
        }),
      );
      return read(sent, nodesOf);
    },

    async createNode({ level, parentId = null, name }) {
      let parent: number | null = null;
      if (parentId !== null) {
        parent = requestId(parentId);
        if (parent === null) return { kind: 'failed' };
      }
      const sent = await attempt(() =>
        client.POST('/inventory/admin/ghg-index/nodes', {
          body:
            parent === null ?
              { level, name: name.trim() }
            : { level, parentId: parent, name: name.trim() },
        }),
      );
      return written(sent, oneNodeOf);
    },

    async renameNode(id, name) {
      const nodeId = requestId(id);
      if (nodeId === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.PATCH('/inventory/admin/ghg-index/nodes/{node_id}', {
          params: { path: { node_id: nodeId } },
          body: { name: name.trim() },
        }),
      );
      return written(sent, oneNodeOf);
    },

    async deleteNodes(ids) {
      const body = requestIds(ids);
      if (body === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST('/inventory/admin/ghg-index/nodes/delete', {
          body: { ids: body },
        }),
      );
      return written(sent, countOf);
    },

    async getFacility(id) {
      const nodeId = requestId(id);
      if (nodeId === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.GET('/inventory/admin/ghg-index/facilities/{node_id}', {
          params: { path: { node_id: nodeId } },
        }),
      );
      return read(sent, parsePoolFacility);
    },

    async createFacility({ parentId, facilityCodeId, unit, tooltip }) {
      const ids = requestIds([parentId, facilityCodeId]);
      if (ids === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST('/inventory/admin/ghg-index/facilities', {
          body: { parentId: ids[0]!, facilityCodeId: ids[1]!, unit, tooltip },
        }),
      );
      return written(sent, parsePoolFacility);
    },

    async saveFacility(id, { facilityCodeId, unit, tooltip, defaultFactorId }) {
      const ids = requestIds(
        defaultFactorId === null ?
          [id, facilityCodeId]
        : [id, facilityCodeId, defaultFactorId],
      );
      if (ids === null) return { kind: 'failed' };
      const [nodeId, codeId, factorId] = ids as [number, number, number?];
      const sent = await attempt(() =>
        client.PUT('/inventory/admin/ghg-index/facilities/{node_id}', {
          params: { path: { node_id: nodeId } },
          body: {
            facilityCodeId: codeId,
            unit,
            tooltip,
            ...(factorId === undefined ? {} : { defaultFactorId: factorId }),
          },
        }),
      );
      return written(sent, parsePoolFacility);
    },

    async createFactor(facilityId, draft) {
      const nodeId = requestId(facilityId);
      if (nodeId === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST('/inventory/admin/ghg-index/facilities/{node_id}/factors', {
          params: { path: { node_id: nodeId } },
          body: draft,
        }),
      );
      return written(sent, parsePoolFactor);
    },

    async getFactor(id, version) {
      const factorId = requestId(id);
      if (factorId === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.GET('/inventory/admin/ghg-factors/{factor_id}', {
          params: {
            path: { factor_id: factorId },
            query: version === undefined ? {} : { version },
          },
        }),
      );
      return read(sent, parsePoolFactor);
    },

    async saveFactor(id, draft) {
      const factorId = requestId(id);
      if (factorId === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.PUT('/inventory/admin/ghg-factors/{factor_id}', {
          params: { path: { factor_id: factorId } },
          body: draft,
        }),
      );
      return written(sent, parsePoolFactor);
    },

    async deleteFactors(ids) {
      const body = requestIds(ids);
      if (body === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.POST('/inventory/admin/ghg-factors/delete', {
          body: { ids: body },
        }),
      );
      return written(sent, countOf);
    },

    async options() {
      const sent = await attempt(() =>
        client.GET('/inventory/admin/ghg-options'),
      );
      return read(sent, parsePoolOptions);
    },
  };
}
