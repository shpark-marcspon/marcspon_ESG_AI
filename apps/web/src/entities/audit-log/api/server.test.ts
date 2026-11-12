// 감사 기록 실어댑터(밴드 AD5R ①): 진짜 createApi 에 가짜 서버를 물려 부른 경로·쿼리를 단언한다.
//   list → GET /audit-logs(쿼리 = 넣은 칸 + limit 50·offset, companyId 없음), actors → GET /audit-logs/actors(쿼리 없음, 서버 차례 그대로).
//   실패(400·403·404·422·5xx·던짐·꼴 틀림)는 모두 failed 하나.
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import { AUDIT_NO_FILTER, auditQuery } from '../model/index.ts';
import { AUDIT_PAGE_SIZE, createAuditServerPort } from './index.ts';
import {
  fakeActor,
  fakeAuditRow,
  fakeAuditServer,
  json,
  refusal,
} from './testing.ts';

const BASE = 'http://test.local/api';

function setup(
  rows = [fakeAuditRow(2), fakeAuditRow(1)],
  actors = [fakeActor(11)],
) {
  const server = fakeAuditServer(rows, actors, { baseUrl: BASE });
  const port = createAuditServerPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  return { server, port };
}

/** 처음 거르기(이번 주 — 2026-10-15 목 기준). */
const firstQuery = auditQuery(
  AUDIT_NO_FILTER,
  new Date('2026-10-15T03:00:00Z'),
);

describe('list — GET /audit-logs 한 쪽', () => {
  it('부른 경로가 정확히 /audit-logs, 쿼리가 정확히 날짜 둘 + limit 50·offset 0, count 는 서버 값', async () => {
    const { server, port } = setup();
    const outcome = await port.list(firstQuery, 0);
    expect(outcome).toEqual({
      kind: 'ok',
      count: 2,
      isNext: false,
      rows: [fakeAuditRow(2), fakeAuditRow(1)],
    });
    expect(server.calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      'GET /audit-logs',
    ]);
    expect(server.listQueries()).toEqual([
      {
        dateFrom: '2026-10-12',
        dateTo: '2026-10-15',
        limit: String(AUDIT_PAGE_SIZE),
        offset: '0',
      },
    ]);
    expect(AUDIT_PAGE_SIZE).toBe(50);
  });

  it('q·사람·행동이 그 값으로 실리고, offset 50 이 실린다. companyId 는 없다', async () => {
    const { server, port } = setup();
    await port.list(
      auditQuery(
        {
          query: ' kim ',
          period: 'all',
          actorUserId: 7,
          action: 'setting_change',
        },
        new Date('2026-10-15T03:00:00Z'),
      ),
      50,
    );
    expect(server.listQueries()).toEqual([
      {
        q: 'kim',
        actorUserId: '7',
        action: 'setting_change',
        limit: '50',
        offset: '50',
      },
    ]);
    expect(server.calls[0]!.query.has('companyId')).toBe(false);
  });

  it('공백만 든 검색은 q 키째 나가지 않는다', async () => {
    const { server, port } = setup();
    await port.list(
      auditQuery(
        { ...AUDIT_NO_FILTER, query: '   ' },
        new Date('2026-10-15T03:00:00Z'),
      ),
      0,
    );
    expect(server.calls[0]!.query.has('q')).toBe(false);
  });

  it('다음 쪽이 있으면 isNext 참, count 는 실린 수가 아니라 전부의 수', async () => {
    const many = Array.from({ length: 53 }, (_, i) => fakeAuditRow(53 - i));
    const { port } = setup(many);
    const first = await port.list({}, 0);
    expect(
      first.kind === 'ok' && [first.count, first.isNext, first.rows.length],
    ).toEqual([53, true, 50]);
    const second = await port.list({}, 50);
    expect(second.kind === 'ok' && [second.isNext, second.rows.length]).toEqual(
      [false, 3],
    );
  });
});

describe('actors — GET /audit-logs/actors', () => {
  it('경로 정확히, 쿼리 없음, 서버 차례 그대로', async () => {
    const actors = [
      fakeActor(1, { actorName: 'Zed' }),
      fakeActor(2, { actorName: 'alpha' }),
      fakeActor(3, { actorName: null, actorUsername: null }),
      fakeActor(4, { actorKind: 'admin' }),
    ];
    const { server, port } = setup([], actors);
    expect(await port.actors()).toEqual({ kind: 'ok', actors });
    expect(server.calls).toHaveLength(1);
    expect(server.calls[0]!.path).toBe('/audit-logs/actors');
    expect([...server.calls[0]!.query.keys()]).toEqual([]);
  });
});

describe('실패는 모두 failed 하나', () => {
  const answers = {
    '422': () => refusal(422, 'VALIDATION_ERROR'),
    '403 FORBIDDEN': () => refusal(403, 'FORBIDDEN'),
    '403 PASSWORD_CHANGE_REQUIRED': () =>
      refusal(403, 'PASSWORD_CHANGE_REQUIRED'),
    '404': () => refusal(404, 'COMPANY_NOT_FOUND'),
    '400': () => refusal(400, 'COMPANY_AMBIGUOUS'),
    '500': () => json(500, undefined),
    '502 빈 본문': () => new Response('', { status: 502 }),
    던짐: () => {
      throw new TypeError('연결 끊김');
    },
  };

  it.each(Object.entries(answers))('list: %s', async (_, answer) => {
    const { server, port } = setup();
    server.override['GET /audit-logs'] = answer;
    expect(await port.list({}, 0)).toEqual({ kind: 'failed' });
  });

  it.each(Object.entries(answers))('actors: %s', async (_, answer) => {
    const { server, port } = setup();
    server.override['GET /audit-logs/actors'] = answer;
    expect(await port.actors()).toEqual({ kind: 'failed' });
  });

  it.each([
    ['results 가 배열이 아님', { count: 1, isNext: false, results: {} }],
    ['count 없음', { isNext: false, results: [] }],
    ['isNext 가 글자', { count: 0, isNext: 'no', results: [] }],
    [
      '줄의 칸 빠짐',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeAuditRow(1), event: undefined }],
      },
    ],
    [
      'action 모르는 값',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeAuditRow(1), action: 'delete' }],
      },
    ],
    [
      'actorKind 모르는 값',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeAuditRow(1), actorKind: 'robot' }],
      },
    ],
    [
      'id 가 글자',
      { count: 1, isNext: false, results: [{ ...fakeAuditRow(1), id: '1' }] },
    ],
    [
      'module 이 수',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeAuditRow(1), module: 3 }],
      },
    ],
    [
      'module 키 없음',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeAuditRow(1), module: undefined }],
      },
    ],
    ['null', null],
  ])('list 꼴 틀림: %s', async (_, body) => {
    const { server, port } = setup();
    server.override['GET /audit-logs'] = () => json(200, body);
    expect(await port.list({}, 0)).toEqual({ kind: 'failed' });
  });

  it.each([
    ['results 없음', {}],
    [
      'actorKind command(목록에 없는 갈래)',
      { results: [fakeActor(1, { actorKind: 'command' as 'admin' })] },
    ],
    ['actorUserId 없음', { results: [{ ...fakeActor(1), actorUserId: null }] }],
  ])('actors 꼴 틀림: %s', async (_, body) => {
    const { server, port } = setup();
    server.override['GET /audit-logs/actors'] = () => json(200, body);
    expect(await port.actors()).toEqual({ kind: 'failed' });
  });
});
