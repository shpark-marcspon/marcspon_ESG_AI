// 온실가스 인덱스 풀 실어댑터(밴드 W12-0b1 ② — 발주서 §3 5): 진짜 createApi 에 가짜 서버(api/testing.ts)를 물려 경로 열둘의
//   메서드·경로·쿼리·본문 열쇠·id 정수를 단언한다. companyId 0. 갈래: 읽기 ok·failed(403·꼴 틀림·끊김·모르는 단 글자),
//   쓰기 rejected 의 code 넷(VALIDATION_ERROR·NOT_FOUND·HAS_CHILDREN·IN_USE)·그 밖 null·fields · 서버 message 0. 거울 칸 = openapi(★E).
//   가짜 그 자체(발주서 §3 7): 409 둘 · 기본 승계 · 새 판.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import { POOL_MIRRORED } from './contract/index.ts';
import { POOL_WRITE_CODES, createGhgPoolAdminPort } from './index.ts';
import {
  fakeFactorBody,
  fakeGhgServer,
  json,
  refusal,
  unreachable,
} from './testing.ts';
import type { FakeGhgServerOptions } from './testing.ts';

const BASE = 'http://test.local/api';
const P = '/inventory/admin';

function setup(options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer({ baseUrl: BASE, ...options });
  const port = createGhgPoolAdminPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  return { server, port };
}

const keys = (server: ReturnType<typeof setup>['server']) =>
  server.calls.map((call) => `${call.method} ${call.path}`);
const lastQuery = (server: ReturnType<typeof setup>['server']) =>
  Object.fromEntries(server.calls.at(-1)!.query);
const lastBody = (server: ReturnType<typeof setup>['server']) =>
  server.calls.at(-1)!.body;
const noCompany = (server: ReturnType<typeof setup>['server']) => {
  for (const call of server.calls) {
    expect(JSON.stringify(call.body ?? {})).not.toContain('companyId');
    expect(call.query.has('companyId')).toBe(false);
  }
};

describe('노드 넷', () => {
  it('listNodes: 쿼리 없음 → 범위 · parentId 정수 글자 · q 면 parentId 를 싣지 않음 · 단 글자 넷', async () => {
    const { server, port } = setup();
    const scopes = await port.listNodes({});
    expect(
      scopes.kind === 'ok' && scopes.value.map((n) => [n.id, n.level]),
    ).toEqual([
      ['1', 'scope'],
      ['2', 'scope'],
    ]);
    expect(lastQuery(server)).toEqual({});
    const types = await port.listNodes({ parentId: '1' });
    expect(types.kind === 'ok' && types.value.map((n) => n.level)).toEqual([
      'source_type',
      'source_type',
    ]);
    expect(lastQuery(server)).toEqual({ parentId: '1' });
    const leaves = await port.listNodes({ parentId: '5' });
    expect(leaves.kind === 'ok' && leaves.value[0]).toEqual({
      id: '20',
      level: 'facility',
      name: '지어낸 보일러',
      parentId: '5',
      sortOrder: 20,
      childCount: 0,
      facilityCode: 'F0001',
      facilityCodeId: '1',
    });
    const found = await port.listNodes({ parentId: '1', q: ' 도로 ' });
    expect(lastQuery(server)).toEqual({ q: '도로' });
    expect(found.kind === 'ok' && found.value.map((n) => n.id)).toEqual([
      '1',
      '4',
      '6',
    ]);
    expect(keys(server).every((k) => k === `GET ${P}/ghg-index/nodes`)).toBe(
      true,
    );
    noCompany(server);
  });

  it('모르는 단 글자(sourceType)·꼴 틀림·403·끊김 → failed · 글자 id 는 요청 없이 failed', async () => {
    const { server, port } = setup();
    const k = `GET ${P}/ghg-index/nodes`;
    server.override[k] = [
      () =>
        json(200, {
          items: [
            {
              id: '1',
              level: 'sourceType',
              name: 'x',
              parentId: null,
              sortOrder: 1,
              childCount: 0,
            },
          ],
        }),
      () => json(200, { items: [{ id: 1 }] }),
      () => refusal(403, 'FORBIDDEN'),
      unreachable,
    ];
    for (let i = 0; i < 4; i += 1)
      expect(await port.listNodes({})).toEqual({ kind: 'failed' });
    expect(await port.listNodes({ parentId: 'abc' })).toEqual({
      kind: 'failed',
    });
    expect(server.calls).toHaveLength(4);
  });

  it('createNode: 범위는 {level, name} · 그 밖은 {level, parentId 정수, name}(trim) → 201 · 겹침 422 fields.name', async () => {
    const { server, port } = setup();
    const scope = await port.createNode({
      level: 'scope',
      name: ' 지어낸 기타배출 ',
    });
    expect(lastBody(server)).toEqual({
      level: 'scope',
      name: '지어낸 기타배출',
    });
    expect(scope.kind === 'ok' && scope.value).toMatchObject({
      level: 'scope',
      parentId: null,
    });
    await port.createNode({
      level: 'source_type',
      parentId: '2',
      name: '지어낸 전력',
    });
    expect(lastBody(server)).toEqual({
      level: 'source_type',
      parentId: 2,
      name: '지어낸 전력',
    });
    expect(
      await port.createNode({
        level: 'source_type',
        parentId: '2',
        name: '지어낸 전력',
      }),
    ).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { name: expect.any(Array) },
    });
    expect(keys(server)).toEqual(Array(3).fill(`POST ${P}/ghg-index/nodes`));
  });

  it('renameNode: PATCH 경로 node_id 정수 · {name} · 404', async () => {
    const { server, port } = setup();
    const renamed = await port.renameNode('3', '지어낸 고정연소2');
    expect(keys(server)).toEqual([`PATCH ${P}/ghg-index/nodes/3`]);
    expect(lastBody(server)).toEqual({ name: '지어낸 고정연소2' });
    expect(renamed.kind === 'ok' && renamed.value.name).toBe(
      '지어낸 고정연소2',
    );
    expect(await port.renameNode('99', 'x')).toMatchObject({
      code: 'NOT_FOUND',
    });
    expect(await port.renameNode('x', 'x')).toEqual({ kind: 'failed' });
  });

  it('deleteNodes: {ids 정수} → 지운 수 · 409 HAS_CHILDREN · 409 IN_USE(쓰이는 잎·잎의 쓰이는 계수) · 404', async () => {
    const { server, port } = setup();
    expect(await port.deleteNodes(['5'])).toEqual({
      kind: 'rejected',
      code: 'HAS_CHILDREN',
      fields: {},
    });
    expect(lastBody(server)).toEqual({ ids: [5] });
    server.poolInUse.factors.add('23');
    expect(await port.deleteNodes(['20'])).toMatchObject({ code: 'IN_USE' });
    server.poolInUse.factors.clear();
    server.poolInUse.nodes.add('22');
    expect(await port.deleteNodes(['22'])).toMatchObject({ code: 'IN_USE' });
    expect(await port.deleteNodes(['20'])).toEqual({ kind: 'ok', value: 1 });
    expect(await port.deleteNodes(['20'])).toMatchObject({ code: 'NOT_FOUND' });
    // 자식까지 한 요청이면 지운다.
    expect(await port.deleteNodes(['6', '24'])).toEqual({
      kind: 'ok',
      value: 2,
    });
  });
});

describe('잎 셋', () => {
  it('getFacility: 경로 정수 · 계수 요약(기본·판)', async () => {
    const { server, port } = setup();
    const leaf = await port.getFacility('20');
    expect(keys(server)).toEqual([`GET ${P}/ghg-index/facilities/20`]);
    expect(leaf.kind === 'ok' && leaf.value).toMatchObject({
      id: '20',
      parentId: '5',
      facilityCodeId: '1',
      facilityName: '지어낸 보일러',
      unit: { kind: 'volume', unit: 'kL' },
      factors: [
        { id: '21', isDefault: true, version: 1 },
        { id: '23', isDefault: false, version: 1 },
      ],
    });
    expect(await port.getFacility('5')).toEqual({ kind: 'failed' });
  });

  it('createFacility: 본문 {parentId 정수, facilityCodeId 정수, unit, tooltip} → 201 · 같은 활동 같은 코드 422 fields.facilityCodeId', async () => {
    const { server, port } = setup();
    const made = await port.createFacility({
      parentId: '6',
      facilityCodeId: '2',
      unit: { kind: 'energy', unit: 'GJ' },
      tooltip: '지어낸',
    });
    expect(lastBody(server)).toEqual({
      parentId: 6,
      facilityCodeId: 2,
      unit: { kind: 'energy', unit: 'GJ' },
      tooltip: '지어낸',
    });
    expect(made.kind === 'ok' && made.value).toMatchObject({
      parentId: '6',
      factors: [],
    });
    expect(
      await port.createFacility({
        parentId: '6',
        facilityCodeId: '2',
        unit: { kind: 'energy', unit: 'GJ' },
        tooltip: '',
      }),
    ).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { facilityCodeId: expect.any(Array) },
    });
    expect(
      await port.createFacility({
        parentId: 'x',
        facilityCodeId: '2',
        unit: { kind: 'energy', unit: 'GJ' },
        tooltip: '',
      }),
    ).toEqual({ kind: 'failed' });
  });

  it('saveFacility: PUT 본문 {facilityCodeId 정수, unit, tooltip} · 기본 바꿈만 defaultFactorId 정수 · 쓰이는 잎의 코드·단위 바꿈 409 IN_USE(툴팁·기본은 지남)', async () => {
    const { server, port } = setup();
    server.poolInUse.nodes.add('20');
    const base = {
      facilityCodeId: '1',
      unit: { kind: 'volume', unit: 'kL' },
      tooltip: '고침',
    };
    expect(
      (await port.saveFacility('20', { ...base, defaultFactorId: null })).kind,
    ).toBe('ok');
    expect(lastBody(server)).toEqual({
      facilityCodeId: 1,
      unit: { kind: 'volume', unit: 'kL' },
      tooltip: '고침',
    });
    const switched = await port.saveFacility('20', {
      ...base,
      defaultFactorId: '23',
    });
    expect(lastBody(server)).toEqual({
      facilityCodeId: 1,
      unit: { kind: 'volume', unit: 'kL' },
      tooltip: '고침',
      defaultFactorId: 23,
    });
    expect(
      switched.kind === 'ok' && switched.value.factors.map((f) => f.isDefault),
    ).toEqual([false, true]);
    expect(
      await port.saveFacility('20', {
        ...base,
        unit: { kind: 'volume', unit: 'L' },
        defaultFactorId: null,
      }),
    ).toEqual({
      kind: 'rejected',
      code: 'IN_USE',
      fields: {},
    });
    expect(
      await port.saveFacility('20', {
        ...base,
        facilityCodeId: '3',
        defaultFactorId: null,
      }),
    ).toMatchObject({ code: 'IN_USE' });
    expect(
      await port.saveFacility('22', {
        ...base,
        facilityCodeId: '2',
        defaultFactorId: '21',
      }),
    ).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { defaultFactorId: expect.any(Array) },
    });
  });
});

describe('계수 넷 · 선택 목록', () => {
  it('createFactor: POST 경로 node_id 정수 · 본문 GhgFactorIn 깊은 같음(Decimal 글자) → 201 판 1 · 첫 계수면 기본', async () => {
    const { server, port } = setup();
    const draft = fakeFactorBody('지어낸 새 계수');
    const made = await port.createFactor('24', draft);
    expect(keys(server)).toEqual([`POST ${P}/ghg-index/facilities/24/factors`]);
    expect(lastBody(server)).toEqual(draft);
    expect(made.kind === 'ok' && made.value).toMatchObject({
      version: 1,
      versions: [1],
      isDefault: true,
      facilityNodeId: '24',
    });
    const bad = {
      ...draft,
      gases: draft.gases.map((g) => ({ ...g, enabled: false })),
    };
    expect(await port.createFactor('24', bad)).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { gases: expect.any(Array) },
    });
  });

  it('createFactor 422 점 열쇠: 켠 가스의 0·글자 아님 → fields 의 gases.<가스>.factor·gwp 그대로(R6)', async () => {
    const { port } = setup();
    const draft = fakeFactorBody('지어낸 점 열쇠');
    const out = await port.createFactor('24', {
      ...draft,
      gases: draft.gases.map((g) =>
        g.gas === 'CH4' ? { ...g, factor: '0', gwp: '1e3' } : g,
      ),
    });
    expect(out.kind === 'rejected' && out.code).toBe('VALIDATION_ERROR');
    expect(out.kind === 'rejected' && Object.keys(out.fields).sort()).toEqual([
      'gases.CH4.factor',
      'gases.CH4.gwp',
    ]);
  });

  it('가짜 계수 검사가 서버 단위 규칙을 따른다(R5): 배출 단위 목록 · 순발열량 단위 energy · factorUnit 꼴·분모 종류', async () => {
    const { port } = setup();
    const base = fakeFactorBody('지어낸 단위 검사');
    const fieldsOf = async (body: typeof base) => {
      const out = await port.createFactor('24', body);
      return out.kind === 'rejected' ?
          Object.keys(out.fields).sort()
        : out.kind;
    };
    expect(
      await fieldsOf({ ...base, emissionUnit: { kind: 'mass', unit: 'kg' } }),
    ).toEqual(['emissionUnit']);
    expect(
      await fieldsOf({ ...base, ncvUnit: { kind: 'volume', unit: 'kL' } }),
    ).toEqual(['ncvUnit']);
    expect(await fieldsOf({ ...base, factorUnit: 'kgTJ' })).toEqual([
      'factorUnit',
    ]);
    // 순발열량 켬인데 분모가 부피 · 끔인데 분모가 에너지(투입은 부피) → factorUnit.
    expect(await fieldsOf({ ...base, factorUnit: 'kg/kL' })).toEqual([
      'factorUnit',
    ]);
    const off = { ...base, ncvEnabled: false, ncv: null, ncvUnit: null };
    expect(await fieldsOf({ ...off, factorUnit: 'kg/TJ' })).toEqual([
      'factorUnit',
    ]);
    // 비우면 서버 기본(늘 지남) · 같은 종류 안 접두 차이는 지남.
    expect(await fieldsOf({ ...off, factorUnit: null })).toBe('ok');
    expect(await fieldsOf({ ...off, factorUnit: 't/L' })).toBe('ok');
  });

  it('getFactor: 경로 factor_id 정수 · version 쿼리(있을 때만) · saveFactor: PUT 늘 새 판(옛 판은 ?version=)', async () => {
    const { server, port } = setup();
    await port.getFactor('21');
    expect(lastQuery(server)).toEqual({});
    const draft = { ...fakeFactorBody('지어낸 경유 계수 고침') };
    const saved = await port.saveFactor('21', draft);
    expect(keys(server).at(-1)).toBe(`PUT ${P}/ghg-factors/21`);
    expect(lastBody(server)).toEqual(draft);
    expect(saved.kind === 'ok' && saved.value).toMatchObject({
      version: 2,
      versions: [1, 2],
      name: '지어낸 경유 계수 고침',
    });
    const old = await port.getFactor('21', 1);
    expect(lastQuery(server)).toEqual({ version: '1' });
    expect(old.kind === 'ok' && old.value).toMatchObject({
      version: 1,
      name: '지어낸 경유 계수',
    });
    expect(await port.getFactor('21', 9)).toEqual({ kind: 'failed' });
  });

  it('deleteFactors: {ids 정수} · 기본을 지우면 남은 첫 행이 기본 · 쓰이는 계수 409 IN_USE', async () => {
    const { server, port } = setup();
    server.poolInUse.factors.add('23');
    expect(await port.deleteFactors(['23'])).toEqual({
      kind: 'rejected',
      code: 'IN_USE',
      fields: {},
    });
    server.poolInUse.factors.clear();
    expect(await port.deleteFactors(['21'])).toEqual({ kind: 'ok', value: 1 });
    expect(lastBody(server)).toEqual({ ids: [21] });
    const leaf = await port.getFacility('20');
    expect(leaf.kind === 'ok' && leaf.value.factors).toEqual([
      expect.objectContaining({ id: '23', isDefault: true }),
    ]);
    expect(await port.deleteFactors(['21'])).toMatchObject({
      code: 'NOT_FOUND',
    });
  });

  it('options: 가스 일곱·단위·국가·산업·기본값', async () => {
    const { server, port } = setup();
    const out = await port.options();
    expect(keys(server)).toEqual([`GET ${P}/ghg-options`]);
    expect(out.kind === 'ok' && out.value.gases).toEqual([
      'CO2',
      'CH4',
      'N2O',
      'HFCs',
      'PFCs',
      'SF6',
      'NF3',
    ]);
    expect(out.kind === 'ok' && out.value.defaults.emissionUnit).toEqual({
      kind: 'mass',
      unit: 'tCO2-eq',
    });
  });

  it('쓰기 갈래: code 넷만 · 모르는 code → null(fields 비움) · 끊김·5xx·꼴 틀림 → failed · 서버 message 0', async () => {
    const { server, port } = setup();
    expect(POOL_WRITE_CODES).toEqual([
      'VALIDATION_ERROR',
      'NOT_FOUND',
      'HAS_CHILDREN',
      'IN_USE',
    ]);
    const k = `POST ${P}/ghg-factors/delete`;
    server.override[k] = [
      () => refusal(409, 'SOMETHING_ELSE', { x: ['y'] }),
      unreachable,
      () => refusal(500, 'SERVER_ERROR'),
      () => json(200, { count: 'x' }),
    ];
    expect(await port.deleteFactors(['21'])).toEqual({
      kind: 'rejected',
      code: null,
      fields: {},
    });
    for (let i = 0; i < 3; i += 1) {
      const out = await port.deleteFactors(['21']);
      expect(
        out.kind === 'failed' || (out.kind === 'rejected' && out.code === null),
      ).toBe(true);
      expect(JSON.stringify(out)).not.toContain('지어낸-');
    }
  });
});

describe('풀 거울(★E)', () => {
  it('거울 칸 이름이 openapi.json 의 스키마 칸과 같다(열두 꼴)', () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const openapi = JSON.parse(
      readFileSync(
        resolve(here, '../../../../../api-py/generated/openapi.json'),
        'utf8',
      ),
    ) as {
      components: {
        schemas: Record<string, { properties: Record<string, unknown> }>;
      };
    };
    for (const [name, fields] of Object.entries(POOL_MIRRORED))
      expect([...fields].sort(), name).toEqual(
        Object.keys(openapi.components.schemas[name]!.properties).sort(),
      );
  });
});
