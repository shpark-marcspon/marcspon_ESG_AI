// 평가 목록 어댑터(밴드 IRW1 ③ — 덧붙임 A, IR3c 계약 소비). 진짜 실어댑터 + 가짜 서버.
//   GET /materiality/runs 쿼리(status 여러 번·mine 은 참일 때만·limit 20·offset) · 쪽 그대로 · 꼴 틀림 rejected · 끊김 unreachable ·
//   새 칸은 버리고 지난다 · 거울 칸 이름이 openapi.json 의 스키마 칸과 같다.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { MIRRORED_LIST } from './contract/runs.ts';
import {
  FAKE_OTHER,
  doneRun,
  fakeMaterialityServer,
  fakeRun,
  json,
  serverStoreOf,
  unreachable,
} from './testing.ts';

const LIST = 'GET /materiality/runs';

describe('listRuns', () => {
  it('쿼리: status 여러 번 · mine 은 참일 때만 · limit 20 · offset — 쪽은 새 것 먼저, 줄 칸은 서버 짓기 그대로', async () => {
    const server = fakeMaterialityServer({
      runs: [
        doneRun(1, { createdAt: '2026-10-19T10:00:00+09:00' }),
        fakeRun(2, {
          status: 'processing',
          createdAt: '2026-10-19T11:00:00+09:00',
          createdBy: FAKE_OTHER,
        }),
        fakeRun(3, { module: 'dataverify' }),
      ],
    });
    const store = serverStoreOf(server);
    const page = await store.listRuns({ offset: 0 });
    expect(page.count).toBe(2);
    expect(page.results.map((row) => row.id)).toEqual([2, 1]);
    expect(page.results[1]).toMatchObject({
      companyName: '가상물산',
      topicCount: 2,
      impactRows: 3,
      pathwayRows: 3,
      industries: [{ standard: 'SASB', industryName: '가상 산업' }],
    });
    const [first] = server.calls;
    expect(first!.query.getAll('status')).toEqual([]);
    expect(first!.query.has('mine')).toBe(false);
    expect(first!.query.get('limit')).toBe('20');
    expect(first!.query.get('offset')).toBe('0');

    const mine = await store.listRuns({
      status: ['queued', 'processing'],
      mine: true,
      offset: 0,
    });
    expect(mine.count).toBe(0);
    const last = server.calls.at(-1)!;
    expect(last.query.getAll('status')).toEqual(['queued', 'processing']);
    expect(last.query.get('mine')).toBe('true');
  });

  it('꼴 틀림 rejected · 끊김 unreachable · 새 칸은 버리고 지난다', async () => {
    const server = fakeMaterialityServer();
    server.override[LIST] = [
      () => json(200, { count: 1, isNext: false, results: [{ id: 1 }] }),
      unreachable,
      () => json(200, { count: 0, isNext: false, results: [], later: 'x' }),
    ];
    const store = serverStoreOf(server);
    await expect(store.listRuns({ offset: 0 })).rejects.toMatchObject({
      kind: 'rejected',
    });
    await expect(store.listRuns({ offset: 0 })).rejects.toMatchObject({
      kind: 'unreachable',
    });
    await expect(store.listRuns({ offset: 0 })).resolves.toEqual({
      count: 0,
      isNext: false,
      results: [],
    });
  });

  it('거울 칸 이름이 openapi.json 의 스키마 칸과 같다', () => {
    const openapi = JSON.parse(
      readFileSync(
        resolve(
          dirname(fileURLToPath(import.meta.url)),
          '../../../../../api-py/generated/openapi.json',
        ),
        'utf8',
      ),
    ) as {
      components: {
        schemas: Record<string, { properties: Record<string, unknown> }>;
      };
    };
    for (const [name, fields] of Object.entries(MIRRORED_LIST))
      expect([...fields].sort(), name).toEqual(
        Object.keys(openapi.components.schemas[name]!.properties).sort(),
      );
  });
});
