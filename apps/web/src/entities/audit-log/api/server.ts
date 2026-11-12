// 감사 기록의 실어댑터(밴드 AD5R ①). 서버 경로 둘 — 줄(GET /audit-logs, 쪽)·행위자 목록(GET /audit-logs/actors).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. 전역 통신·창은 모른다(app/ 이 넣는다).
// 거르기는 서버가 한다: 화면이 만든 쿼리(model 의 auditQuery — 값 있는 칸만)에 쪽(limit·offset)만 더해 보낸다.
// companyId 는 보내지 않는다(MARC-ENT-251 — 회사가 하나면 생략. 회사가 둘이면 400 COMPANY_AMBIGUOUS → failed).
// 한 번 보내고, 꼴 틀림·400·403·404·422·5xx·연결 끊김은 모두 failed 하나(MARC-ENT-260 3 「둘로만」). 서버 message 는 화면에 보이지 않는다.
// 줄은 서버 꼴 그대로 돌려준다 — 화면 글로 바꾸는 것(toEntry)은 문구 표를 넣는 화면의 몫이다.
import { asFailure } from '../../../shared/api/index.ts';
import type { Api, ApiFailure } from '../../../shared/api/index.ts';
import { AUDIT_ACTIONS } from '../model/index.ts';
import type {
  AuditActorRow,
  AuditEventRow,
  AuditQuery,
} from '../model/index.ts';

/** 한 쪽의 크기(「더 보기」 한 번). */
export const AUDIT_PAGE_SIZE = 50;

export type AuditPageOutcome =
  | { kind: 'ok'; count: number; isNext: boolean; rows: AuditEventRow[] }
  | { kind: 'failed' };

export type AuditActorsOutcome =
  { kind: 'ok'; actors: AuditActorRow[] } | { kind: 'failed' };

export interface AuditServerPort {
  /** 거른 줄의 한 쪽(offset 부터 AUDIT_PAGE_SIZE 줄). count 는 조건에 맞는 전부의 수. */
  list(query: AuditQuery, offset: number): Promise<AuditPageOutcome>;
  /** 감사 기록에 나온 사람(서버 차례 그대로 — 화면 차례는 model 의 actorOptions). */
  actors(): Promise<AuditActorsOutcome>;
}

export interface CreateAuditServerPortOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
}

const ACTIONS: readonly string[] = AUDIT_ACTIONS;
const KINDS: readonly string[] = ['admin', 'service', 'command', 'anonymous'];
const nullable = (value: unknown, type: 'string' | 'number') =>
  value === null || typeof value === type;

/** 줄 하나가 계약 꼴인가(꼴 틀림은 실패로 — 틀린 정보를 그리지 않는다). */
function isRow(value: unknown): value is AuditEventRow {
  if (typeof value !== 'object' || value === null) return false;
  const row = value as Record<string, unknown>;
  return (
    typeof row.id === 'number' &&
    typeof row.at === 'string' &&
    nullable(row.companyId, 'number') &&
    typeof row.actorKind === 'string' &&
    KINDS.includes(row.actorKind) &&
    nullable(row.actorUserId, 'number') &&
    nullable(row.actorName, 'string') &&
    nullable(row.actorUsername, 'string') &&
    typeof row.action === 'string' &&
    ACTIONS.includes(row.action) &&
    typeof row.event === 'string' &&
    (row.result === 'success' || row.result === 'failure') &&
    nullable(row.reason, 'string') &&
    nullable(row.targetKind, 'string') &&
    nullable(row.targetId, 'number') &&
    nullable(row.targetLabel, 'string') &&
    (row.changedFields === null || Array.isArray(row.changedFields)) &&
    nullable(row.requestId, 'string') &&
    nullable(row.module, 'string')
  );
}

/** 행위자 하나가 계약 꼴인가. */
function isActor(value: unknown): value is AuditActorRow {
  if (typeof value !== 'object' || value === null) return false;
  const actor = value as Record<string, unknown>;
  return (
    (actor.actorKind === 'admin' || actor.actorKind === 'service') &&
    typeof actor.actorUserId === 'number' &&
    nullable(actor.actorName, 'string') &&
    nullable(actor.actorUsername, 'string')
  );
}

export function createAuditServerPort({
  api,
}: CreateAuditServerPortOptions): AuditServerPort {
  const { client } = api;

  /** 한 번 보낸다. 실패는 갈래로(던지지 않는다). */
  async function attempt<T>(
    send: () => Promise<{ data?: T }>,
  ): Promise<{ data: T } | { failure: ApiFailure }> {
    try {
      const { data } = await send();
      if (data === undefined) return { failure: { kind: 'network' } };
      return { data };
    } catch (error) {
      return { failure: asFailure(error) };
    }
  }

  return {
    async list(query, offset) {
      const result = await attempt(() =>
        client.GET('/audit-logs', {
          params: { query: { ...query, limit: AUDIT_PAGE_SIZE, offset } },
        }),
      );
      if ('failure' in result) return { kind: 'failed' };
      const body: unknown = result.data;
      if (typeof body !== 'object' || body === null) return { kind: 'failed' };
      const { count, isNext, results } = body as Record<string, unknown>;
      if (
        typeof count !== 'number' ||
        typeof isNext !== 'boolean' ||
        !Array.isArray(results) ||
        !results.every(isRow)
      )
        return { kind: 'failed' };
      return { kind: 'ok', count, isNext, rows: results };
    },

    async actors() {
      const result = await attempt(() => client.GET('/audit-logs/actors'));
      if ('failure' in result) return { kind: 'failed' };
      const body: unknown = result.data;
      if (typeof body !== 'object' || body === null) return { kind: 'failed' };
      const { results } = body as Record<string, unknown>;
      if (!Array.isArray(results) || !results.every(isActor))
        return { kind: 'failed' };
      return { kind: 'ok', actors: results };
    },
  };
}
