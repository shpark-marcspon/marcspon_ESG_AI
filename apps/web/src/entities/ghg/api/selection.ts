// 고객사 인덱스 선택 실어댑터(밴드 W12-0b2 ① — 서버 K1b-2b, sid:MARC-ENT-469 3·4). server.ts 꼴. 경로 둘(/inventory 뒤):
//     tree  GET /scope12/index-tree?year=                                → IndexTreeOut(평평한 nodes, 페이지 없음)
//     save  PUT /scope12/index-selections/{year} {facilityNodeIds: 정수[]} → IndexSelectionSaveOut(빠진 잎은 뺌 — 빈 목록도 그 해를 만든다)
// 넣어 준 Api(세션 api)만 쓴다. companyId 0(서버가 작업 회사를 정한다 — 고객사 사용자·운영 관리자). 요청 id 정수(model 의 toRequestId —
// 아니면 요청 없이 failed), 응답 id 글자(sid:MARC-ISSUE-92). 연도는 정수가 아니면 요청 없이 failed.
// 갈래: 읽기 ok | refused(회사 거절 셋 — companyRefusalOf) | failed · 쓰기는 거기에 rejected{code, fields} — code 는
//   VALIDATION_ERROR 만(fields.year·fields.facilityNodeIds 를 화면이 가른다), 그 밖 거절은 null. 서버 message 는 싣지 않는다.
import { asFailure, companyRefusalOf } from '../../../shared/api/index.ts';
import type {
  Api,
  ApiFailure,
  CompanyRefusal,
  FailureFields,
} from '../../../shared/api/index.ts';
import { toRequestId } from '../model/index.ts';
import type {
  SelectionNode,
  SelectionSaved,
  SelectionTree,
} from '../model/index.ts';
import { parseIndexTree, parseSelectionSaved } from './contract/index.ts';
import type { IndexTreeOut } from './contract/index.ts';

/** 선택 쓰기 거절 중 화면이 가르는 code. */
export const SELECTION_WRITE_CODES = ['VALIDATION_ERROR'] as const;
export type SelectionWriteCode = (typeof SELECTION_WRITE_CODES)[number];

export type SelectionRead<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

export type SelectionWrite<T> =
  | { kind: 'ok'; value: T }
  | {
      kind: 'rejected';
      code: SelectionWriteCode | null;
      fields: FailureFields;
    }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

export interface GhgSelectionPort {
  tree(year: number): Promise<SelectionRead<SelectionTree>>;
  /** 그 해에 고를 잎 전부(서버 차례 — model 의 selectionBody). */
  save(
    year: number,
    facilityNodeIds: readonly string[],
  ): Promise<SelectionWrite<SelectionSaved>>;
}

export interface CreateGhgSelectionPortOptions {
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

/** 잎 칸 셋을 null 로 고른 꼴로. */
const treeOf = (out: IndexTreeOut): SelectionTree => ({
  year: out.year,
  nodes: out.nodes.map((node): SelectionNode => ({
    id: node.id,
    level: node.level as SelectionNode['level'],
    name: node.name,
    parentId: node.parentId,
    facilityCodeId: node.facilityCodeId ?? null,
    availableCount: node.availableCount,
    selected: node.selected,
    hasFactor: node.hasFactor ?? null,
    hasData: node.hasData ?? null,
  })),
});

function requestIds(ids: readonly string[]): number[] | null {
  try {
    return ids.map(toRequestId);
  } catch {
    return null;
  }
}

export function createGhgSelectionPort({
  api,
}: CreateGhgSelectionPortOptions): GhgSelectionPort {
  const { client } = api;
  return {
    async tree(year) {
      if (!Number.isInteger(year)) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.GET('/inventory/scope12/index-tree', {
          params: { query: { year } },
        }),
      );
      if ('failure' in sent) {
        const company = companyRefusalOf(sent.failure);
        return company ? { kind: 'refused', company } : { kind: 'failed' };
      }
      const value = parseIndexTree(sent.data);
      return value === null ?
          { kind: 'failed' }
        : { kind: 'ok', value: treeOf(value) };
    },

    async save(year, facilityNodeIds) {
      const body = requestIds(facilityNodeIds);
      if (body === null || !Number.isInteger(year)) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.PUT('/inventory/scope12/index-selections/{year}', {
          params: { path: { year } },
          body: { facilityNodeIds: body },
        }),
      );
      if ('failure' in sent) {
        const { failure } = sent;
        if (failure.kind !== 'api') return { kind: 'failed' };
        const company = companyRefusalOf(failure);
        if (company) return { kind: 'refused', company };
        const known = (SELECTION_WRITE_CODES as readonly string[]).includes(
          failure.code,
        );
        return {
          kind: 'rejected',
          code: known ? (failure.code as SelectionWriteCode) : null,
          fields: known ? failure.fields : {},
        };
      }
      const value = parseSelectionSaved(sent.data);
      return value === null ? { kind: 'failed' } : { kind: 'ok', value };
    },
  };
}
