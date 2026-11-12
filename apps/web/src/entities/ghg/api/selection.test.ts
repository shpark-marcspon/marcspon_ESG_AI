// 고객사 인덱스 선택 실어댑터(밴드 W12-0b2 ① — 발주서 §3 1·3): 진짜 createApi 에 가짜 서버(api/testing.ts)를 물려 경로 둘의
//   메서드·경로·쿼리·본문 열쇠·id 정수를 단언한다. companyId 0. 갈래: 읽기 ok·refused(회사 셋)·failed(꼴 틀림·모르는 단 글자·끊김),
//   쓰기 rejected 의 code(VALIDATION_ERROR 만 — fields.year·fields.facilityNodeIds)·그 밖 null · 서버 message 0. 거울 칸 = openapi(★E).
//   가짜 그 자체(§3 3): 해마다 따로(Q8) · 빈 선택이 해를 만듦 · J1(이미 고른 못 고를 잎은 지남) · 422 · 「쓰이는 표」(S19 409 와 한 가짜).
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import { SELECTION_MIRRORED } from './contract/index.ts';
import { createGhgSelectionPort } from './index.ts';
import {
  fakeGhgServer,
  fakeHeadquarters,
  fakeSelectionOptions,
  json,
  portsOf,
  refusal,
  unreachable,
} from './testing.ts';
import type { FakeGhgServerOptions } from './testing.ts';

const BASE = 'http://test.local/api';
const TREE = 'GET /inventory/scope12/index-tree';
const SAVE = (year: number) =>
  `PUT /inventory/scope12/index-selections/${year}`;

function setup(options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer({ baseUrl: BASE, thisYear: 2026, ...options });
  const port = createGhgSelectionPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  return { server, port };
}

type Server = ReturnType<typeof setup>['server'];
const keys = (server: Server) =>
  server.calls.map((call) => `${call.method} ${call.path}`);
const noCompany = (server: Server) => {
  for (const call of server.calls) {
    expect(JSON.stringify(call.body ?? {})).not.toContain('companyId');
    expect(call.query.has('companyId')).toBe(false);
  }
};
const leafOf = (
  out: Awaited<ReturnType<ReturnType<typeof setup>['port']['tree']>>,
  id: string,
) => (out.kind === 'ok' ? out.value.nodes.find((n) => n.id === id) : null);

describe('선택 경로 둘', () => {
  it('tree: GET 쿼리 year 하나 · 평평한 nodes(서버 차례 — 단 → sortOrder → id) · 잎 칸 셋 · 위 단 null', async () => {
    const { server, port } = setup();
    const out = await port.tree(2025);
    expect(keys(server)).toEqual([TREE]);
    expect(Object.fromEntries(server.calls[0]!.query)).toEqual({
      year: '2025',
    });
    expect(out.kind === 'ok' && out.value.year).toBe(2025);
    expect(out.kind === 'ok' && out.value.nodes.map((n) => n.id)).toEqual([
      '1',
      '2',
      '3',
      '4',
      '5',
      '6',
      '20',
      '22',
      '24',
    ]);
    expect(leafOf(out, '20')).toEqual({
      id: '20',
      level: 'facility',
      name: '지어낸 보일러',
      parentId: '5',
      facilityCodeId: '1',
      availableCount: 1,
      selected: false,
      hasFactor: true,
      hasData: false,
    });
    expect(leafOf(out, '1')).toEqual({
      id: '1',
      level: 'scope',
      name: '지어낸 직접배출',
      parentId: null,
      facilityCodeId: null,
      availableCount: 1,
      selected: false,
      hasFactor: null,
      hasData: null,
    });
    noCompany(server);
  });

  it('tree: 잎 칸 셋이 빠진 답도 null 로 · 모르는 단 글자(sourceType)·꼴 틀림·끊김 → failed · 정수 아닌 해는 요청 없이 failed', async () => {
    const { server, port } = setup();
    server.override[TREE] = () =>
      json(200, {
        year: 2026,
        nodes: [
          {
            id: '7',
            level: 'scope',
            name: '지어낸',
            parentId: null,
            availableCount: 0,
            selected: false,
          },
        ],
      });
    const bare = await port.tree(2026);
    expect(bare.kind === 'ok' && bare.value.nodes[0]).toMatchObject({
      facilityCodeId: null,
      hasFactor: null,
      hasData: null,
    });
    server.override[TREE] = () =>
      json(200, {
        year: 2026,
        nodes: [
          {
            id: '7',
            level: 'sourceType',
            name: '지어낸',
            parentId: null,
            availableCount: 0,
            selected: false,
          },
        ],
      });
    expect(await port.tree(2026)).toEqual({ kind: 'failed' });
    server.override[TREE] = () => json(200, { year: '2026', nodes: [] });
    expect(await port.tree(2026)).toEqual({ kind: 'failed' });
    server.override[TREE] = unreachable;
    expect(await port.tree(2026)).toEqual({ kind: 'failed' });
    const before = server.calls.length;
    expect(await port.tree(2026.5)).toEqual({ kind: 'failed' });
    expect(server.calls.length).toBe(before);
  });

  it('save: PUT 경로 year · 본문 {facilityNodeIds 정수[]} 깊은 같음(열쇠 하나) · 답 {selected, hiddenWithData} · 글자 id 는 요청 없이 failed', async () => {
    const { server, port } = setup(fakeSelectionOptions());
    const out = await port.save(2026, ['20', '22']);
    expect(out).toEqual({
      kind: 'ok',
      value: { selected: 2, hiddenWithData: 0 },
    });
    expect(keys(server)).toEqual([SAVE(2026)]);
    expect(server.calls[0]!.body).toStrictEqual({ facilityNodeIds: [20, 22] });
    expect(await port.save(2026, ['20', 'x9'])).toEqual({ kind: 'failed' });
    expect(server.calls.length).toBe(1);
    noCompany(server);
  });

  it('save 422 두 칸: fields.year(올해 뒤·1990 앞) · fields.facilityNodeIds(잎 아님·기본 계수 없음 — S12-05 시설 0 은 200) — 서버 message 0', async () => {
    const { port } = setup(fakeSelectionOptions());
    const year = await port.save(2027, ['20']);
    expect(year).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { year: ['지어낸 연도'] },
    });
    expect(JSON.stringify(year)).not.toContain('지어낸-VALIDATION_ERROR');
    expect((await port.save(1989, [])).kind).toBe('rejected');
    for (const ids of [['5'], ['24'], ['999']]) {
      const out = await port.save(2026, ids);
      expect(out.kind === 'rejected' && Object.keys(out.fields)).toEqual([
        'facilityNodeIds',
      ]);
    }
    // S12-05: 이 회사에 자산/시설이 없는 잎(22 — 기본 계수 있음, 본사만이라 줄 0)도 고른다 — 서버와 같이 거절 아님.
    const bare = setup({
      ...fakeSelectionOptions(),
      branches: [fakeHeadquarters()],
    });
    const facilityless = await bare.port.save(2026, ['22']);
    expect(facilityless).toEqual({
      kind: 'ok',
      value: { selected: 1, hiddenWithData: 0 },
    });
    // 트리: 잎 22 = 시설 0 · 골라짐 · 위 단(5)은 시설 0 잎도 셈 안(서버 「위 단: 시설 0 잎도 셈 안」과 같은 꼴).
    const lineOf = async (id: string) => {
      const out = await bare.port.tree(2026);
      if (out.kind !== 'ok') throw new Error(`트리 실패 ${out.kind}`);
      return out.value.nodes.find((node) => node.id === id)!;
    };
    expect(await lineOf('22')).toMatchObject({
      availableCount: 0,
      selected: true,
      hasFactor: true,
    });
    expect((await lineOf('5')).selected).toBe(false); // 20 이 안 골라짐
    expect((await bare.port.save(2026, ['20'])).kind).toBe('ok');
    expect((await lineOf('5')).selected).toBe(false); // 22(시설 0)가 빠짐 — 셈 안
    expect((await bare.port.save(2026, ['20', '22'])).kind).toBe('ok');
    expect((await lineOf('5')).selected).toBe(true);
  });

  it('갈래: 회사 거절 셋 → refused(읽기·쓰기) · 모르는 code·5xx → rejected null(fields 비움) · 끊김·꼴 틀림 → failed', async () => {
    for (const company of [
      'COMPANY_AMBIGUOUS',
      'COMPANY_INACTIVE',
      'COMPANY_NOT_FOUND',
    ] as const) {
      const { port } = setup({ company });
      expect((await port.tree(2026)).kind).toBe('refused');
      expect((await port.save(2026, ['20'])).kind).toBe('refused');
    }
    const { server, port } = setup();
    server.override[SAVE(2026)] = () =>
      refusal(409, 'SOMETHING_ELSE', { x: ['y'] });
    expect(await port.save(2026, ['20'])).toEqual({
      kind: 'rejected',
      code: null,
      fields: {},
    });
    server.override[SAVE(2026)] = unreachable;
    expect(await port.save(2026, ['20'])).toEqual({ kind: 'failed' });
    server.override[SAVE(2026)] = () => refusal(500, 'INTERNAL');
    expect((await port.save(2026, ['20'])).kind).toBe('rejected');
    server.override[SAVE(2026)] = () => json(200, { selected: '2' });
    expect(await port.save(2026, ['20'])).toEqual({ kind: 'failed' });
    server.override[TREE] = () => refusal(403, 'FORBIDDEN');
    expect(await port.tree(2026)).toEqual({ kind: 'failed' });
  });
});

describe('가짜 선택(§3 3)', () => {
  it('해마다 따로(Q8): 2025 저장 뒤 2024 트리의 selected 0 · 빈 선택 저장도 해를 만듦', async () => {
    const { server, port } = setup(fakeSelectionOptions());
    await port.save(2025, ['20', '22']);
    const y2025 = await port.tree(2025);
    expect(leafOf(y2025, '20')?.selected).toBe(true);
    expect(leafOf(y2025, '5')?.selected).toBe(true);
    const y2024 = await port.tree(2024);
    expect(
      y2024.kind === 'ok' && y2024.value.nodes.filter((n) => n.selected),
    ).toEqual([]);
    expect(server.chosenIn(2024)).toBeNull();
    expect(await port.save(2024, [])).toEqual({
      kind: 'ok',
      value: { selected: 0, hiddenWithData: 0 },
    });
    expect(server.chosenIn(2024)).toEqual([]);
    expect(server.chosenIn(2025)).toEqual(['20', '22']);
  });

  it('J1: 이미 고른 잎은 시설 0·기본 계수 없음이어도 다시 보내면 지남 · 새로 고르면 422', async () => {
    const { server, port } = setup({ chosen: { 2026: ['22', '24'] } });
    const tree = await port.tree(2026);
    expect(leafOf(tree, '22')).toMatchObject({
      availableCount: 0,
      hasFactor: false,
      selected: true,
    });
    expect((await port.save(2026, ['22', '24', '20'])).kind).toBe('ok');
    expect(server.chosenIn(2026)).toEqual(['20', '22', '24']);
    expect((await port.save(2026, ['20'])).kind).toBe('ok');
    expect((await port.save(2026, ['20', '22'])).kind).toBe('rejected');
  });

  it('hasData: 해가 있고 심은 잎만 참 · 빼며 저장하면 숨김(hiddenWithData) · 다시 고르면 숨김 풂', async () => {
    const { server, port } = setup(fakeSelectionOptions());
    server.selectionData.add('20');
    expect(leafOf(await port.tree(2026), '20')?.hasData).toBe(false);
    await port.save(2026, ['20', '22']);
    expect(leafOf(await port.tree(2026), '20')?.hasData).toBe(true);
    expect(await port.save(2026, ['22'])).toEqual({
      kind: 'ok',
      value: { selected: 1, hiddenWithData: 1 },
    });
    expect(leafOf(await port.tree(2026), '20')?.selected).toBe(false);
    await port.save(2026, ['20', '22']);
    expect(server.chosenIn(2026)).toEqual(['20', '22']);
  });

  it('1,000 넘음·본문 열쇠 밖(companyId)·글자 id → 422 fields.facilityNodeIds', async () => {
    const { server } = setup(fakeSelectionOptions());
    const put = (body: unknown) =>
      server.send(
        new Request(`${BASE}/inventory/scope12/index-selections/2026`, {
          method: 'PUT',
          body: JSON.stringify(body),
        }),
      );
    for (const body of [
      { facilityNodeIds: Array.from({ length: 1001 }, (_, i) => i + 1) },
      { facilityNodeIds: [20], companyId: 1 },
      { facilityNodeIds: ['20'] },
      { facilityNodeIds: [true] },
    ]) {
      const answer = await put(body);
      expect(answer.status).toBe(422);
      expect(
        ((await answer.json()) as { error: { fields: object } }).error.fields,
      ).toHaveProperty('facilityNodeIds');
    }
  });

  it('저장한 잎·그 기본 계수는 「쓰이는 표」에 든다 → S19 잎 지우기 409 IN_USE · 빼면 풀림 · 숨긴 선택은 남음', async () => {
    const server = fakeGhgServer({ baseUrl: BASE, ...fakeSelectionOptions() });
    const ports = portsOf(server, BASE);
    expect((await ports.selection.save(2026, ['20'])).kind).toBe('ok');
    expect(server.poolInUse.nodes.has('20')).toBe(true);
    expect(server.poolInUse.factors.has('21')).toBe(true);
    expect(await ports.pool.deleteNodes(['20'])).toMatchObject({
      kind: 'rejected',
      code: 'IN_USE',
    });
    await ports.selection.save(2026, []);
    expect(server.poolInUse.nodes.has('20')).toBe(false);
    expect((await ports.pool.deleteNodes(['20'])).kind).toBe('ok');
    // 숨긴 선택(데이터가 있어 빼며 숨김)도 쓰이는 표에 남는다(서버 nodes_in_use — 숨김 포함·삭제 표시만 뺌).
    server.selectionData.add('22');
    await ports.selection.save(2026, ['22']);
    expect(await ports.selection.save(2026, [])).toEqual({
      kind: 'ok',
      value: { selected: 0, hiddenWithData: 1 },
    });
    expect(server.poolInUse.nodes.has('22')).toBe(true);
    expect(server.poolInUse.factors.has('30')).toBe(true);
    expect(await ports.pool.deleteNodes(['22'])).toMatchObject({
      kind: 'rejected',
      code: 'IN_USE',
    });
  });
});

describe('선택 거울(★E)', () => {
  it('거울 칸 이름이 openapi.json 의 스키마 칸과 같다(셋) · 요청 본문 IndexSelectionSaveIn 은 facilityNodeIds 하나', () => {
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
    for (const [name, fields] of Object.entries(SELECTION_MIRRORED))
      expect([...fields].sort(), name).toEqual(
        Object.keys(openapi.components.schemas[name]!.properties).sort(),
      );
    expect(
      Object.keys(openapi.components.schemas.IndexSelectionSaveIn!.properties),
    ).toEqual(['facilityNodeIds']);
  });
});
