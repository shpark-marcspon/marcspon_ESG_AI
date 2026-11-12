// 대시보드(S1) 실어댑터(밴드 DB1 ②). 진짜 createApi + 가짜 온실가스 서버(testing.ts — dashboards 씨앗, openapi 꼴).
//   GET /inventory/scope12/dashboard?year= · 값 글자 그대로(새 칸 scope3FailedSheets 포함) · 갈래(ok·refused·failed — 꼴 틀림·끊김·422) ·
//   거울 ⊆ openapi(칸 더한 흉내에 초록) · 씨앗 꼴이 openapi 와 같음.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { DASHBOARD_MIRRORED } from './contract/index.ts';
import {
  dashboardOut,
  fakeDashboard,
  fakeGhgServer,
  json,
  mirrorGaps,
  portsOf,
  refusal,
  unreachable,
} from './testing.ts';
import type { FakeGhgServerOptions } from './testing.ts';

const KEY = 'GET /inventory/scope12/dashboard';

function setup(options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer(options);
  return { server, port: portsOf(server).dashboard };
}

describe('대시보드 어댑터', () => {
  it('board: GET ?year= 하나 · 값 글자·새 칸 그대로', async () => {
    const seeded = fakeDashboard(2025, { scope3FailedSheets: 2 });
    const { server, port } = setup({ dashboards: { 2025: seeded } });
    const out = await port.board(2025);
    expect(out).toStrictEqual({ kind: 'ok', value: seeded });
    expect(server.count(KEY)).toBe(1);
    expect(server.calls.at(-1)!.query.get('year')).toBe('2025');
  });

  it('심지 않은 해는 빈 판(configured 거짓 · Scope 3 없음 · 빠진 시트 0)', async () => {
    const out = await setup().port.board(2024);
    expect(out).toStrictEqual({ kind: 'ok', value: dashboardOut(2024) });
  });

  it('정수 아닌 해는 요청 없이 failed', async () => {
    const { server, port } = setup();
    expect(await port.board(2025.5)).toStrictEqual({ kind: 'failed' });
    expect(server.count(KEY)).toBe(0);
  });

  it('회사 거절 → refused · 꼴 틀림(새 칸 빠짐)·끊김·그 밖 거절 → failed', async () => {
    expect(
      await setup({ company: 'COMPANY_AMBIGUOUS' }).port.board(2025),
    ).toStrictEqual({ kind: 'refused', company: 'ambiguous' });
    const { server, port } = setup();
    const broken = fakeDashboard(2025) as unknown as {
      total: Record<string, unknown>;
    };
    delete broken.total.scope3FailedSheets;
    server.override[KEY] = [
      () => json(200, broken),
      unreachable,
      () => refusal(500, 'SOMETHING_ELSE'),
    ];
    expect(await port.board(2025)).toStrictEqual({ kind: 'failed' });
    expect(await port.board(2025)).toStrictEqual({ kind: 'failed' });
    expect(await port.board(2025)).toStrictEqual({ kind: 'failed' });
  });
});

describe('대시보드 거울 — 응답 ⊆ openapi', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const openapi = JSON.parse(
    readFileSync(
      resolve(here, '../../../../../api-py/generated/openapi.json'),
      'utf8',
    ),
  ) as {
    components: {
      schemas: Record<
        string,
        { properties: Record<string, unknown>; required?: string[] }
      >;
    };
  };
  const schemas = openapi.components.schemas;

  it('거울 일곱 꼴의 칸은 다 openapi 에 있다(⊆) · openapi 가 칸을 더해도 초록', () => {
    expect(Object.keys(DASHBOARD_MIRRORED)).toHaveLength(7);
    expect(mirrorGaps(DASHBOARD_MIRRORED, schemas)).toEqual([]);
    const grown = structuredClone(schemas);
    grown.Scope12DashboardTotalOut!.properties.later = { type: 'string' };
    expect(mirrorGaps(DASHBOARD_MIRRORED, grown)).toEqual([]);
  });

  it('씨앗(dashboardOut·fakeDashboard)의 칸 = openapi 꼴의 칸(흉내가 openapi 꼴)', () => {
    const seeded = fakeDashboard(2025);
    const keys = (name: string) =>
      Object.keys(schemas[name]!.properties).sort();
    expect(Object.keys(seeded).sort()).toEqual(keys('Scope12DashboardOut'));
    expect(Object.keys(seeded.total).sort()).toEqual(
      keys('Scope12DashboardTotalOut'),
    );
    expect(Object.keys(seeded.bySite[0]!).sort()).toEqual(
      keys('Scope12DashboardSiteOut'),
    );
    expect(Object.keys(seeded.scopes[0]!).sort()).toEqual(
      keys('Scope12DashboardScopeOut'),
    );
    expect(Object.keys(seeded.scopes[0]!.topSources[0]!).sort()).toEqual(
      keys('Scope12DashboardSourceOut'),
    );
    expect(Object.keys(seeded.scope3Categories[0]!).sort()).toEqual(
      keys('Scope12DashboardCategoryOut'),
    );
    expect(schemas.Scope12DashboardTotalOut!.required).toContain(
      'scope3FailedSheets',
    );
  });
});
