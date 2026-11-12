// Scope 1·2 입력 실어댑터(밴드 W12-1a ② — 발주서 §3 3·5). 진짜 createApi + 가짜 온실가스 서버(testing.ts — fakeEntryOptions).
//   경로 열의 메서드·경로·쿼리·본문 열쇠 · 요청 id 정수(아니면 요청 0 · failed) · 금액 글자 · 갈래(ok·notFound·locked·rejected·forbidden·refused·failed) ·
//   거울 ⊆ openapi(칸 더한 흉내에 초록) · 요청 칸 = openapi · 히스토리 모르는 kind 도 ok · 가짜 그 자체(칸 단위 덮음 · 히스토리 · 삭제 하나라도 404).
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { ENTRY_UPLOAD_MAX_BYTES, saveBody } from '../model/index.ts';
import { ENTRY_MIRRORED, ENTRY_REQUEST_FIELDS } from './contract/index.ts';
import {
  ENTRY_XLSX_TYPE,
  FAKE_EXPORT_NAME,
  FAKE_TEMPLATE_NAME,
  FAKE_UNIT_PAIRS,
  FAKE_UPLOAD_MAX,
  fakeCustomUnitProblem,
  fakeEntryOptions,
  fakeFactorBody,
  fakeGhgServer,
  json,
  mirrorGaps,
  portsOf,
  refusal,
  unreachable,
} from './testing.ts';
import type { FakeGhgServerOptions } from './testing.ts';

const X = (year: number, node: string) =>
  `/inventory/scope12/years/${year}/indexes/${node}`;

function setup(options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer({ ...fakeEntryOptions(), ...options });
  return { server, port: portsOf(server).entry };
}

/** 사업장 블록 가운데 제1공장(사업장 2 — 본사 1 도 같은 코드 줄이 있어 블록이 둘). */
function plantOf<T extends { siteId: string }>(sites: readonly T[]): T {
  return sites.find((site) => site.siteId === '2')!;
}

/** 2025 잎 20(지어낸 보일러) · 제1공장(사업장 2) 의 자산/시설 줄 4(1호기) 에 새 행 하나를 심는다. */
async function seeded(options: FakeGhgServerOptions = {}) {
  const { server, port } = setup(options);
  const out = await port.saveRows(2025, '20', '2', [
    {
      siteFacilityId: 4,
      unit: 'kL',
      na: false,
      values: [{ slot: '2025-01', amount: '12.5', estimated: false }],
    },
  ]);
  if (out.kind !== 'ok') throw new Error(`심기 실패 ${out.kind}`);
  const rowId = plantOf(out.value.sites).rows[0]!.rowId;
  return { server, port, rowId };
}

describe('입력 어댑터 — 읽기', () => {
  it('years: GET /inventory/scope12/years → 새 해 먼저 · configured', async () => {
    const { server, port } = setup();
    const out = await port.years();
    expect(out).toStrictEqual({
      kind: 'ok',
      value: [
        { year: 2025, configured: true },
        { year: 2024, configured: false },
      ],
    });
    expect(server.count('GET /inventory/scope12/years')).toBe(1);
  });

  it('rows: year 정수 · q 는 걷어 빈 글이면 싣지 않음 · 세 해 머리·자릿수·단위 · 금액 글자 · 설정 안 된 해 configured 거짓', async () => {
    const { server, port } = setup();
    const out = await port.rows(2025, '  ');
    expect(out.kind).toBe('ok');
    if (out.kind !== 'ok') return;
    expect(out.value.years).toEqual([2023, 2024, 2025]);
    expect([out.value.decimals, out.value.unit, out.value.configured]).toEqual([
      2,
      'tCO2-eq',
      true,
    ]);
    expect(out.value.scopes[0]!.rows[0]!.values).toStrictEqual({
      '2023': null,
      '2024': '7.25',
      '2025': '12.125',
    });
    const call = server.calls.at(-1)!;
    expect([call.path, call.query.get('year'), call.query.has('q')]).toEqual([
      '/inventory/scope12/rows',
      '2025',
      false,
    ]);
    await port.rows(2025, ' 보일러 ');
    expect(server.calls.at(-1)!.query.get('q')).toBe('보일러');
    const empty = await port.rows(2024);
    expect(empty).toMatchObject({
      kind: 'ok',
      value: { configured: false, scopes: [] },
    });
  });

  it('rows: 검색 q 422 → rejected(fields 그대로 — 검색 줄 아래 몫) · 그 밖 거절은 읽기 갈래(검증 A4)', async () => {
    const { port } = setup();
    expect(await port.rows(2025, 'ㄱ'.repeat(101))).toStrictEqual({
      kind: 'rejected',
      fields: { q: ['지어낸 100자 넘음'] },
    });
    const { server, port: other } = setup();
    server.override['GET /inventory/scope12/rows'] = () =>
      refusal(400, 'SOMETHING_ELSE');
    expect(await other.rows(2025, '보일러')).toStrictEqual({ kind: 'failed' });
  });

  it('detail: GET X(경로 id 정수) · 404 → notFound · 정수 아닌 id → 요청 0 · failed', async () => {
    const { server, port } = setup();
    const out = await port.detail(2025, '20');
    expect(out.kind).toBe('ok');
    if (out.kind === 'ok') {
      expect(out.value.nodeId).toBe('20');
      expect(out.value.unit).toBe('tCO2-eq');
      expect(out.value.sites.map((s) => s.siteName)).toEqual([
        '본사',
        '제1공장',
      ]);
    }
    expect(server.calls.at(-1)!.path).toBe(X(2025, '20'));
    expect(await port.detail(2025, '22')).toStrictEqual({ kind: 'notFound' });
    const before = server.calls.length;
    expect(await port.detail(2025, 'abc')).toStrictEqual({ kind: 'failed' });
    expect(await port.detail(2025.5, '20')).toStrictEqual({ kind: 'failed' });
    expect(server.calls.length).toBe(before);
  });

  it('history: page·pageSize · 새 것 먼저 · 심은 kind(unit) 도 ok · 없는 행 404', async () => {
    const { port, rowId } = await seeded({ entryHistoryKind: 'unit' });
    const out = await port.history(2025, '20', rowId, 1);
    expect(out.kind).toBe('ok');
    if (out.kind === 'ok') {
      expect(out.value.results[0]!.kind).toBe('unit');
      expect(out.value.results[0]!.after).toBe('12.5');
      expect([out.value.page, out.value.pageSize]).toEqual([1, 20]);
    }
    expect(await port.history(2025, '20', '999', 1)).toStrictEqual({
      kind: 'notFound',
    });
  });

  it('꼴 틀린 답 → failed · 끊김 → failed · 회사 거절 셋 → refused', async () => {
    const { server, port } = setup();
    server.override['GET /inventory/scope12/rows'] = [
      () => json(200, { year: 2025, years: [2025], scopes: 'x' }),
      unreachable,
    ];
    expect(await port.rows(2025)).toStrictEqual({ kind: 'failed' });
    expect(await port.rows(2025)).toStrictEqual({ kind: 'failed' });
    // 쓰기도 끊김 → failed(검증 A3)
    server.override[`PUT ${X(2025, '20')}/memo`] = [unreachable];
    expect(await port.memo(2025, '20', '지어낸 메모')).toStrictEqual({
      kind: 'failed',
    });
    for (const [code, company] of [
      ['COMPANY_AMBIGUOUS', 'ambiguous'],
      ['COMPANY_INACTIVE', 'inactive'],
      ['COMPANY_NOT_FOUND', 'not_found'],
    ] as const) {
      const refused = setup({ company: code }).port;
      expect(await refused.rows(2025)).toStrictEqual({
        kind: 'refused',
        company,
      });
      expect(await refused.memo(2025, '20', '가')).toStrictEqual({
        kind: 'refused',
        company,
      });
    }
  });
});

describe('입력 어댑터 — 쓰기', () => {
  it('saveRows: PUT X/sites/{site}/rows · 본문 rows 그대로(id 정수·금액 글자·칸 amount·estimated) → 상세', async () => {
    const { server, rowId } = await seeded();
    const sent = server.bodies(`PUT ${X(2025, '20')}/sites/2/rows`);
    expect(sent).toStrictEqual([
      {
        rows: [
          {
            siteFacilityId: 4,
            unit: 'kL',
            na: false,
            values: [{ slot: '2025-01', amount: '12.5', estimated: false }],
          },
        ],
      },
    ]);
    expect(rowId).toMatch(/^[0-9]+$/);
  });

  it('saveRows + model saveBody: 추정만 바뀐 칸도 금액이 실려 가짜(서버)의 값이 그대로', async () => {
    const { port, server } = await seeded();
    const detail = await port.detail(2025, '20');
    if (detail.kind !== 'ok') throw new Error('상세');
    const before = plantOf(detail.value.sites).rows[0]!;
    const body = saveBody([
      {
        before,
        edited: {
          ...before,
          values: before.values.map((v) => ({ ...v, estimated: true })),
        },
      },
    ]);
    const out = await port.saveRows(2025, '20', '2', body.rows);
    expect(out.kind).toBe('ok');
    if (out.kind === 'ok')
      expect(plantOf(out.value.sites).rows[0]!.values).toStrictEqual([
        { slot: '2025-01', amount: '12.5', estimated: true },
      ]);
    expect(
      server.bodies(`PUT ${X(2025, '20')}/sites/2/rows`).at(-1),
    ).toStrictEqual({
      rows: [
        {
          rowId: Number(before.rowId),
          siteFacilityId: 4,
          unit: 'kL',
          na: false,
          values: [{ slot: '2025-01', amount: '12.5', estimated: true }],
        },
      ],
    });
  });

  it('422 → rejected VALIDATION_ERROR + fields(칸 열쇠 그대로) · 409 → locked · 404 → notFound · 그 밖 code → rejected null', async () => {
    const { port, server } = await seeded();
    const bad = await port.saveRows(2025, '20', '2', [
      {
        siteFacilityId: 4,
        unit: '톤',
        na: false,
        values: [{ slot: '2024-01', amount: '1e3', estimated: false }],
      },
    ]);
    expect(bad.kind).toBe('rejected');
    if (bad.kind === 'rejected') {
      expect(bad.code).toBe('VALIDATION_ERROR');
      expect(Object.keys(bad.fields).sort()).toEqual([
        'rows.0.siteFacilityId',
        'rows.0.unit',
        'rows.0.values.0.amount',
        'rows.0.values.0.slot',
      ]);
    }
    expect(await port.saveRows(2025, '20', '9', [])).toStrictEqual({
      kind: 'notFound',
    });
    expect((await port.lock(2025, '20')).kind).toBe('ok');
    expect(await port.saveRows(2025, '20', '2', [])).toStrictEqual({
      kind: 'locked',
    });
    expect(await port.memo(2025, '20', '가')).toStrictEqual({ kind: 'locked' });
    server.override[`PUT ${X(2025, '20')}/memo`] = () =>
      refusal(409, 'SOMETHING_ELSE');
    expect(await port.memo(2025, '20', '가')).toStrictEqual({
      kind: 'rejected',
      code: null,
      fields: {},
    });
  });

  it('심은 422 칸 셋(entryReject) → fields 열쇠 그대로', async () => {
    const keys = ['rows.0.values.0.amount', 'rows.0.unit', 'rows.0.rowId'];
    const { port } = setup({ entryReject: keys });
    const out = await port.saveRows(2025, '20', '2', []);
    expect(out.kind === 'rejected' && Object.keys(out.fields).sort()).toEqual(
      [...keys].sort(),
    );
  });

  it('deleteRows: POST X/rows/delete {ids: 정수[]} → 수 · 하나라도 없으면 404(지우지 않음) · 글자 id → 요청 0', async () => {
    const { port, server, rowId } = await seeded();
    expect(await port.deleteRows(2025, '20', [rowId, '999'])).toStrictEqual({
      kind: 'notFound',
    });
    expect(server.bodies(`POST ${X(2025, '20')}/rows/delete`)).toStrictEqual([
      { ids: [Number(rowId), 999] },
    ]);
    const before = server.calls.length;
    expect(await port.deleteRows(2025, '20', ['x'])).toStrictEqual({
      kind: 'failed',
    });
    expect(server.calls.length).toBe(before);
    expect(await port.deleteRows(2025, '20', [rowId])).toStrictEqual({
      kind: 'ok',
      value: 1,
    });
  });

  it('memo·decimals: 본문 열쇠 하나 · 422 memo·decimals · 저장 값', async () => {
    const { port, server } = setup();
    expect(await port.memo(2025, '20', '지어낸 메모')).toStrictEqual({
      kind: 'ok',
      value: '지어낸 메모',
    });
    expect(server.bodies(`PUT ${X(2025, '20')}/memo`)).toStrictEqual([
      { memo: '지어낸 메모' },
    ]);
    const long = await port.memo(2025, '20', '가'.repeat(2001));
    expect(long.kind === 'rejected' && Object.keys(long.fields)).toEqual([
      'memo',
    ]);
    expect(await port.decimals(2025, 3)).toStrictEqual({
      kind: 'ok',
      value: 3,
    });
    expect(server.bodies('PUT /inventory/scope12/years/2025/decimals')).toEqual(
      [{ decimals: 3 }],
    );
    const wide = await port.decimals(2025, 4);
    expect(wide.kind === 'rejected' && Object.keys(wide.fields)).toEqual([
      'decimals',
    ]);
    expect(await port.decimals(2019, 2)).toStrictEqual({ kind: 'notFound' });
  });

  it('lock·unlock: POST·DELETE X/lock → 상세 · 고객사 풀기 403 → forbidden(잠금 그대로) · 운영 관리자 회사 둘 → refused', async () => {
    const customer = setup({ admin: false }).port;
    const locked = await customer.lock(2025, '20');
    expect(locked.kind === 'ok' && locked.value.locked).toBe(true);
    expect(await customer.unlock(2025, '20')).toStrictEqual({
      kind: 'forbidden',
    });
    const still = await customer.detail(2025, '20');
    expect(still.kind === 'ok' && still.value.locked).toBe(true);
    const { port, server } = setup();
    await port.lock(2025, '20');
    const open = await port.unlock(2025, '20');
    expect(open.kind === 'ok' && open.value.locked).toBe(false);
    expect(server.count(`DELETE ${X(2025, '20')}/lock`)).toBe(1);
    expect(
      await setup({ company: 'COMPANY_AMBIGUOUS' }).port.unlock(2025, '20'),
    ).toStrictEqual({ kind: 'refused', company: 'ambiguous' });
  });
});

describe('거울 — 응답 ⊆ openapi · 요청 = openapi', () => {
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
  const schemas = openapi.components.schemas;

  it('응답 거울 스물세 꼴의 칸은 다 openapi 에 있다(⊆)', () => {
    expect(Object.keys(ENTRY_MIRRORED)).toHaveLength(23);
    expect(mirrorGaps(ENTRY_MIRRORED, schemas)).toEqual([]);
  });

  it('⊆ 판정: openapi 가 칸을 더해도 초록 · 거울에만 있는 칸·없는 꼴은 빨강', () => {
    const grown = structuredClone(schemas);
    grown.EntryRowsOut!.properties.basis = { type: 'string' };
    grown.EntryHistoryOut!.properties.note = { type: 'string' };
    expect(mirrorGaps(ENTRY_MIRRORED, grown)).toEqual([]);
    expect(
      mirrorGaps(
        { EntryRowsOut: ['year', 'summary'], NoSuchOut: ['a'] },
        grown,
      ),
    ).toEqual(['EntryRowsOut.summary', 'NoSuchOut']);
  });

  it('요청 본문 아홉은 칸 이름이 openapi 와 같다(칸이 늘면 빨강)', () => {
    expect(Object.keys(ENTRY_REQUEST_FIELDS)).toHaveLength(9);
    for (const [name, fields] of Object.entries(ENTRY_REQUEST_FIELDS))
      expect([...fields].sort(), name).toEqual(
        Object.keys(schemas[name]!.properties).sort(),
      );
  });
});

describe('가짜 그 자체(서버 규칙)', () => {
  it('칸 단위 덮음: 실린 칸의 빠진 amount 는 null 로 덮임 · 안 실린 칸은 그대로', async () => {
    const { server, rowId } = await seeded();
    const port = portsOf(server).entry;
    await port.saveRows(2025, '20', '2', [
      {
        rowId: Number(rowId),
        siteFacilityId: 4,
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-02', amount: '3', estimated: false }],
      },
    ]);
    const send = await server.send(
      new Request(`http://test.local/api${X(2025, '20')}/sites/2/rows`, {
        method: 'PUT',
        body: JSON.stringify({
          rows: [
            {
              rowId: Number(rowId),
              siteFacilityId: 4,
              unit: 'kL',
              na: false,
              values: [{ slot: '2025-01', estimated: true }],
            },
          ],
        }),
      }),
    );
    expect(send.status).toBe(200);
    const detail = await port.detail(2025, '20');
    expect(
      detail.kind === 'ok' && plantOf(detail.value.sites).rows[0]!.values,
    ).toStrictEqual([
      { slot: '2025-01', amount: null, estimated: true },
      { slot: '2025-02', amount: '3', estimated: false },
    ]);
  });

  it('칸 단위 덮음: 빠진 estimated 는 거짓 · 행의 빠진 na 는 N/A 꺼짐(na_off) — 422 아님', async () => {
    const { server, rowId } = await seeded();
    const port = portsOf(server).entry;
    const put = (row: Record<string, unknown>) =>
      server.send(
        new Request(`http://test.local/api${X(2025, '20')}/sites/2/rows`, {
          method: 'PUT',
          body: JSON.stringify({ rows: [row] }),
        }),
      );
    const base = { rowId: Number(rowId), siteFacilityId: 4, unit: 'kL' };
    expect(
      (
        await put({
          ...base,
          na: false,
          values: [{ slot: '2025-01', amount: '2', estimated: true }],
        })
      ).status,
    ).toBe(200);
    expect((await put({ ...base, na: true, values: [] })).status).toBe(200);
    expect(
      (
        await put({
          ...base,
          values: [{ slot: '2025-01', amount: '2' }],
        })
      ).status,
    ).toBe(200);
    const detail = await port.detail(2025, '20');
    const row =
      detail.kind === 'ok' ? plantOf(detail.value.sites).rows[0]! : null;
    expect([row?.na, row?.values]).toStrictEqual([
      false,
      [{ slot: '2025-01', amount: '2', estimated: false }],
    ]);
    const history = await port.history(2025, '20', rowId, 1);
    expect(history.kind === 'ok' && history.value.results[0]!.kind).toBe(
      'na_off',
    );
  });

  it('히스토리: 값 바뀜·N/A 켬·끔이 새 것 먼저 쌓임 · 추정만은 0', async () => {
    const { server, rowId } = await seeded();
    const port = portsOf(server).entry;
    const line = (over: object) => ({
      rowId: Number(rowId),
      siteFacilityId: 4,
      unit: 'kL',
      na: false,
      values: [],
      ...over,
    });
    await port.saveRows(2025, '20', '2', [line({ na: true })]);
    await port.saveRows(2025, '20', '2', [line({ na: false })]);
    await port.saveRows(2025, '20', '2', [
      line({ values: [{ slot: '2025-01', amount: '12.5', estimated: true }] }),
    ]);
    const out = await port.history(2025, '20', rowId, 1);
    expect(out.kind === 'ok' && out.value.results.map((h) => h.kind)).toEqual([
      'na_off',
      'na_on',
      'value',
    ]);
  });

  it('입력이 생긴 잎은 S17 hasData 참(서버 with_data)', async () => {
    const { server } = await seeded();
    expect(server.selectionData.has('20')).toBe(true);
  });
});

describe('밴드 W12-1b ① — 거울 넓힘(D1)·가짜 맞춤(D2)', () => {
  const mirror = (name: string) => ENTRY_MIRRORED[name] ?? [];

  it('거울 ⊇ S12a-2 칸: EntrySiteOut period·slots · EntryRowOut factor · EntryHistoryOut reason·beforeFactor·afterFactor', () => {
    expect(mirror('EntrySiteOut')).toEqual(
      expect.arrayContaining(['period', 'slots']),
    );
    expect(mirror('EntryRowOut')).toEqual(expect.arrayContaining(['factor']));
    expect(mirror('EntryHistoryOut')).toEqual(
      expect.arrayContaining(['reason', 'beforeFactor', 'afterFactor']),
    );
  });

  it('응답의 slots·행 factor·히스토리 새 칸이 파싱을 지나 남는다(직접입력 계수 version 없음)', async () => {
    const custom = {
      customId: '5',
      name: '지어낸 직접입력',
      source: '지어낸 출처',
      baseYear: 2024,
      tier: 1,
      countryCode: 'KR',
      industryCode: '',
      inputUnit: { kind: '부피', unit: 'kL' },
      ncvEnabled: false,
      ncv: null,
      ncvUnit: null,
      factorUnit: 'kgGHG/kL',
      gases: [],
      note: '지어낸 비고',
      isCustom: true,
    };
    const { server, port } = await seeded({
      entryPeriod: { '1': 'year' },
      entryRowFactor: { '4': custom },
    });
    const out = await port.detail(2025, '20');
    if (out.kind !== 'ok') throw new Error(out.kind);
    const site = plantOf(out.value.sites);
    expect(site.period).toBe('month');
    expect(site.slots).toHaveLength(12);
    expect(site.rows[0]!.factor).toStrictEqual(custom);
    const head = out.value.sites.find((s) => s.siteId === '1')!;
    expect([head.period, head.slots]).toEqual(['year', ['2025']]);
    server.override[`GET ${X(2025, '20')}/rows/1/history`] = () =>
      json(200, {
        count: 1,
        totalPages: 1,
        page: 1,
        pageSize: 20,
        hasNext: false,
        hasPrevious: false,
        results: [
          {
            historyId: '1',
            at: '2026-01-02T03:04:05Z',
            kind: 'factor',
            slot: null,
            unit: 'kL',
            before: null,
            after: null,
            actor: { kind: 'service', id: '1', name: '지어낸-사람' },
            reason: '지어낸 사유',
            restorable: true,
            beforeFactor: {
              versionId: '1',
              customId: null,
              name: '지어낸 앞',
              isCustom: false,
            },
            afterFactor: {
              versionId: null,
              customId: '5',
              name: '지어낸 뒤',
              isCustom: true,
            },
          },
        ],
      });
    const page = await port.history(2025, '20', '1', 1);
    if (page.kind !== 'ok') throw new Error(page.kind);
    const [line] = page.value.results;
    expect(line!.reason).toBe('지어낸 사유');
    expect(line!.beforeFactor?.name).toBe('지어낸 앞');
    expect(line!.afterFactor?.customId).toBe('5');
    expect(line!.restorable).toBe(true); // W12-2 ①: 거울이 restorable 을 싣는다(앞: 걷음)
  });

  it('가짜: 단위 바뀜 → unit 줄(값 줄보다 먼저 쌓임) · 추정만은 0', async () => {
    const { port, rowId } = await seeded({ entryUnits: ['L'] });
    const before = await port.history(2025, '20', rowId, 1);
    const count = before.kind === 'ok' ? before.value.count : -1;
    const out = await port.saveRows(2025, '20', '2', [
      {
        rowId: Number(rowId),
        siteFacilityId: 4,
        unit: 'L',
        na: false,
        values: [{ slot: '2025-01', amount: '13', estimated: false }],
      },
    ]);
    expect(out.kind).toBe('ok');
    const page = await port.history(2025, '20', rowId, 1);
    if (page.kind !== 'ok') throw new Error(page.kind);
    expect(page.value.count).toBe(count + 2);
    const [value, unit] = page.value.results;
    expect(value!.kind).toBe('value');
    expect(value!.unit).toBe('L');
    expect(unit).toMatchObject({ kind: 'unit', before: 'kL', after: 'L' });
    await port.saveRows(2025, '20', '2', [
      {
        rowId: Number(rowId),
        siteFacilityId: 4,
        unit: 'L',
        na: false,
        values: [{ slot: '2025-01', amount: '13', estimated: true }],
      },
    ]);
    const again = await port.history(2025, '20', rowId, 1);
    expect(again.kind === 'ok' && again.value.count).toBe(count + 2);
  });

  it('가짜: 모르는 본문 칸 422(행·칸·꼭대기·메모·지우기·자릿수 — 서버 StrictIn)', async () => {
    const { port } = setup();
    const row = { siteFacilityId: 4, unit: 'kL', values: [] };
    const fieldsOf = async (rows: object[]) => {
      const out = await port.saveRows(2025, '20', '2', rows as never);
      return out.kind === 'rejected' ? Object.keys(out.fields) : out.kind;
    };
    expect(await fieldsOf([{ ...row, extra: 1 }])).toEqual(['rows.0.extra']);
    expect(
      await fieldsOf([
        {
          ...row,
          values: [{ slot: '2025-01', amount: '1', note: 'x' }],
        },
      ]),
    ).toEqual(['rows.0.values.0.note']);
    const { server } = setup();
    const api = portsOf(server);
    expect(
      (
        await server.send(
          new Request(`http://test.local/api${X(2025, '20')}/memo`, {
            method: 'PUT',
            body: JSON.stringify({ memo: 'x', extra: 1 }),
          }),
        )
      ).status,
    ).toBe(422);
    expect(api.entry).toBeTruthy();
  });

  it('가짜: 그 블록 주기 밖 칸 422 rows.<i>.values.<j>.slot · 칸 겹침 422', async () => {
    const { port } = setup({ entryPeriod: { '2': 'quarter' } });
    const save = (values: object[]) =>
      port.saveRows(2025, '20', '2', [
        { siteFacilityId: 4, unit: 'kL', na: false, values },
      ] as never);
    const month = await save([
      { slot: '2025-01', amount: '1', estimated: false },
    ]);
    expect(month.kind === 'rejected' && Object.keys(month.fields)).toEqual([
      'rows.0.values.0.slot',
    ]);
    const twice = await save([
      { slot: '2025-Q1', amount: '1', estimated: false },
      { slot: '2025-Q1', amount: '2', estimated: false },
    ]);
    expect(twice.kind === 'rejected' && Object.keys(twice.fields)).toEqual([
      'rows.0.values.1.slot',
    ]);
    const ok = await save([{ slot: '2025-Q2', amount: '1', estimated: false }]);
    expect(ok.kind).toBe('ok');
  });

  it('가짜: 없는 칸을 빈 칸으로 보내면 칸이 생기지 않는다(서버 _changes)', async () => {
    const { port } = setup();
    const out = await port.saveRows(2025, '20', '2', [
      {
        siteFacilityId: 4,
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-01', amount: null, estimated: false }],
      },
    ]);
    if (out.kind !== 'ok') throw new Error(out.kind);
    expect(plantOf(out.value.sites).rows[0]!.values).toEqual([]);
  });
});

describe('밴드 W12-2 ① — 입력주기(S7)·복구(S12)·restorable·총합', () => {
  const H = (row: string) => `${X(2025, '20')}/rows/${row}/history`;
  /** 행의 히스토리 1쪽(새 것 먼저). */
  async function lines(port: ReturnType<typeof setup>['port'], rowId: string) {
    const page = await port.history(2025, '20', rowId, 1);
    if (page.kind !== 'ok') throw new Error(page.kind);
    return page.value.results;
  }

  it('period: PUT X/sites/{site}/period {period} → 상세 · 새 주기 칸만(옛 값 숨김) · 월로 돌리면 옛 값 다시 · period 줄', async () => {
    const { server, port, rowId } = await seeded();
    const out = await port.period(2025, '20', '2', 'quarter');
    expect(server.bodies(`PUT ${X(2025, '20')}/sites/2/period`)).toStrictEqual([
      { period: 'quarter' },
    ]);
    if (out.kind !== 'ok') throw new Error(out.kind);
    const quarter = plantOf(out.value.sites);
    expect(quarter.period).toBe('quarter');
    expect(quarter.slots).toEqual(['2025-Q1', '2025-Q2', '2025-Q3', '2025-Q4']);
    expect(quarter.rows[0]!.values).toEqual([]);
    expect(quarter.rows[0]!.emission).toBeNull();
    const [top] = await lines(port, rowId);
    expect([top!.kind, top!.before, top!.after, top!.slot]).toEqual([
      'period',
      'month',
      'quarter',
      null,
    ]);
    const back = await port.period(2025, '20', '2', 'month');
    if (back.kind !== 'ok') throw new Error(back.kind);
    expect(plantOf(back.value.sites).slots).toHaveLength(12);
    expect(plantOf(back.value.sites).rows[0]!.values).toEqual([
      { slot: '2025-01', amount: '12.5', estimated: false },
    ]);
    // 다른 블록(본사 1)은 그대로 · 같은 주기면 0 바뀜(줄 안 쌓임)
    expect(back.value.sites.find((s) => s.siteId === '1')!.period).toBe(
      'month',
    );
    const count = (await lines(port, rowId)).length;
    expect((await port.period(2025, '20', '2', 'month')).kind).toBe('ok');
    expect(await lines(port, rowId)).toHaveLength(count);
  });

  it('period 갈래: 주기 밖 422 fields.period · 잠김 409 locked · 없는 사업장 404 · 글자 id → 요청 0 failed', async () => {
    const { server, port } = await seeded();
    const bad = await port.period(2025, '20', '2', 'weekly' as 'month');
    expect(
      bad.kind === 'rejected' && [bad.code, Object.keys(bad.fields)],
    ).toEqual(['VALIDATION_ERROR', ['period']]);
    expect(await port.period(2025, '20', '9', 'year')).toStrictEqual({
      kind: 'notFound',
    });
    expect(await port.period(2025, '20', 'x', 'year')).toStrictEqual({
      kind: 'failed',
    });
    expect(server.count(`PUT ${X(2025, '20')}/sites/x/period`)).toBe(0);
    expect((await port.lock(2025, '20')).kind).toBe('ok');
    expect(await port.period(2025, '20', '2', 'year')).toStrictEqual({
      kind: 'locked',
    });
  });

  it('restore: POST …/history/{h}/restore 본문 {} → 상세 · value 줄의 뒤 값으로 새 줄 · restorable(맨 위 거짓·나머지 참)', async () => {
    const { server, port, rowId } = await seeded();
    await port.saveRows(2025, '20', '2', [
      {
        rowId: Number(rowId),
        siteFacilityId: 4,
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-01', amount: '20', estimated: false }],
      },
    ]);
    const before = await lines(port, rowId);
    expect(before.map((l) => [l.after, l.restorable])).toEqual([
      ['20', false],
      ['12.5', true],
    ]);
    const out = await port.restore(2025, '20', rowId, before[1]!.historyId);
    expect(
      server.bodies(`POST ${H(rowId)}/${before[1]!.historyId}/restore`),
    ).toStrictEqual([{}]);
    if (out.kind !== 'ok') throw new Error(out.kind);
    expect(plantOf(out.value.sites).rows[0]!.values[0]!.amount).toBe('12.5');
    const after = await lines(port, rowId);
    expect(after.map((l) => [l.before, l.after, l.restorable])).toEqual([
      ['20', '12.5', false],
      ['12.5', '20', true],
      [null, '12.5', true],
    ]);
  });

  it('restore 갈래(서버 차례): 404 · 422 historyId(종류·맨 위) · 409 RESTORE_STALE · 409 locked · 글자 id → 요청 0', async () => {
    const { server, port, rowId } = await seeded({ entryUnits: ['L'] });
    await port.saveRows(2025, '20', '2', [
      {
        rowId: Number(rowId),
        siteFacilityId: 4,
        unit: 'L',
        na: false,
        values: [{ slot: '2025-01', amount: '3', estimated: false }],
      },
    ]);
    const [top, unit, first] = await lines(port, rowId);
    expect([top!.kind, unit!.kind, first!.kind]).toEqual([
      'value',
      'unit',
      'value',
    ]);
    expect([top!.restorable, unit!.restorable, first!.restorable]).toEqual([
      false,
      false,
      false, // 단위 바뀜 → 낡음
    ]);
    expect(await port.restore(2025, '20', rowId, '999')).toStrictEqual({
      kind: 'notFound',
    });
    const kind = await port.restore(2025, '20', rowId, unit!.historyId);
    expect(kind.kind === 'rejected' && Object.keys(kind.fields)).toEqual([
      'historyId',
    ]);
    const isTop = await port.restore(2025, '20', rowId, top!.historyId);
    expect(isTop.kind === 'rejected' && Object.keys(isTop.fields)).toEqual([
      'historyId',
    ]);
    expect(
      await port.restore(2025, '20', rowId, first!.historyId),
    ).toStrictEqual({ kind: 'rejected', code: 'RESTORE_STALE', fields: {} });
    expect(await port.restore(2025, '20', rowId, 'x')).toStrictEqual({
      kind: 'failed',
    });
    expect(server.count(`POST ${H(rowId)}/x/restore`)).toBe(0);
    expect((await port.lock(2025, '20')).kind).toBe('ok');
    expect(
      await port.restore(2025, '20', rowId, first!.historyId),
    ).toStrictEqual({ kind: 'locked' });
    expect((await lines(port, rowId)).every((l) => !l.restorable)).toBe(true);
  });

  it('restore factor 줄: 고객사 403 forbidden · 운영 관리자 + 사유 없음({}) 422 reason', async () => {
    for (const [admin, want] of [
      [false, { kind: 'forbidden' }],
      [
        true,
        {
          kind: 'rejected',
          code: 'VALIDATION_ERROR',
          fields: { reason: ['지어낸 사유 필수'] },
        },
      ],
    ] as const) {
      const { port, rowId } = await seeded({
        admin,
        entryHistoryKind: 'factor',
      });
      await port.saveRows(2025, '20', '2', [
        {
          rowId: Number(rowId),
          siteFacilityId: 4,
          unit: 'kL',
          na: false,
          values: [{ slot: '2025-01', amount: '4', estimated: false }],
        },
      ]);
      const [, older] = await lines(port, rowId);
      expect([older!.kind, older!.restorable]).toEqual(['factor', true]);
      expect(
        await port.restore(2025, '20', rowId, older!.historyId),
      ).toStrictEqual(want);
    }
  });

  it('period 줄 복구 = 그 줄의 after 로: 월→분기→월→분기 뒤 after=월 줄 → 월 12·옛 값 다시', async () => {
    const { port, rowId } = await seeded();
    for (const p of ['quarter', 'month', 'quarter'] as const)
      expect((await port.period(2025, '20', '2', p)).kind).toBe('ok');
    const all = await lines(port, rowId);
    const toMonth = all.find(
      (l) => l.kind === 'period' && l.after === 'month',
    )!;
    expect(toMonth.restorable).toBe(true);
    expect(all[0]!.restorable).toBe(false);
    const out = await port.restore(2025, '20', rowId, toMonth.historyId);
    if (out.kind !== 'ok') throw new Error(out.kind);
    const site = plantOf(out.value.sites);
    expect([site.period, site.slots.length]).toEqual(['month', 12]);
    expect(site.rows[0]!.values[0]!.amount).toBe('12.5');
    const [top] = await lines(port, rowId);
    expect([top!.kind, top!.before, top!.after]).toEqual([
      'period',
      'quarter',
      'month',
    ]);
  });

  it('가짜 총합 = sum_or_none: 사업장별 고른 해 · all 은 사업장 합 · N/A·빈 행 빠짐 · 값 없는 사업장·지난 해 null', async () => {
    const { port } = await seeded();
    const one = await port.detail(2025, '20');
    if (one.kind !== 'ok') throw new Error(one.kind);
    expect(one.value.totals.all).toStrictEqual({
      '2023': null,
      '2024': null,
      '2025': '1.5',
    });
    expect(
      one.value.totals.bySite.map((s) => [s.siteId, s.values['2025']]),
    ).toEqual([
      ['1', null],
      ['2', '1.5'],
    ]);
    // 본사 1 에 N/A 행 → 빠짐
    await port.saveRows(2025, '20', '1', [
      {
        siteFacilityId: 1,
        unit: 'kL',
        na: true,
        values: [{ slot: '2025-02', amount: '9', estimated: false }],
      },
    ]);
    const na = await port.detail(2025, '20');
    if (na.kind !== 'ok') throw new Error(na.kind);
    expect(na.value.totals.all['2025']).toBe('1.5');
    expect(na.value.totals.bySite[0]!.values['2025']).toBeNull();
    // N/A 끄면 두 사업장 합
    const rowId = na.value.sites.find((s) => s.siteId === '1')!.rows[0]!.rowId;
    const two = await port.saveRows(2025, '20', '1', [
      {
        rowId: Number(rowId),
        siteFacilityId: 1,
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-02', amount: '9', estimated: false }],
      },
    ]);
    if (two.kind !== 'ok') throw new Error(two.kind);
    expect(two.value.totals.all['2025']).toBe('3'); // addAmounts 글자 합(뒤 0 걷음)
    // 주기를 바꿔 칸이 다 숨으면 그 사업장은 null
    const hidden = await port.period(2025, '20', '2', 'year');
    if (hidden.kind !== 'ok') throw new Error(hidden.kind);
    expect(hidden.value.totals.bySite[1]!.values['2025']).toBeNull();
    expect(hidden.value.totals.all['2025']).toBe('1.5');
  });
});

describe('밴드 W12-3 ② — 계수 바꿈(S9·S11)·사유 실은 복구·548 흉내·R1·R3·R4', () => {
  const F = (row: string) => `${X(2025, '20')}/rows/${row}/factor`;
  const H = (row: string) => `${X(2025, '20')}/rows/${row}/history`;
  const WHY = '지어낸 사유';
  /** 어댑터를 거치지 않은 날 본문(스키마 갈래 — 모르는 칸·둘 다·없음). */
  const put = (
    server: ReturnType<typeof setup>['server'],
    path: string,
    body: unknown,
  ) =>
    server.send(
      new Request(`http://test.local/api${path}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    );
  /** 직접입력 본문(풀 꼴 — 투입 kL · 순발열량 켬 MJ · kg/TJ: 잎 kL 로 셈이 됨). */
  const custom = (fields: Partial<ReturnType<typeof fakeFactorBody>> = {}) => ({
    ...fakeFactorBody('지어낸 직접 계수'),
    ...fields,
  });
  /** 잎 kL 로 바꿀 쌍이 없는 투입 단위(GWh — 순발열량 끔 · 계수 단위 기본). */
  const gwh = () =>
    custom({
      inputUnit: { kind: 'electricity', unit: 'GWh' },
      ncvEnabled: false,
      ncv: null,
      ncvUnit: null,
      factorUnit: null,
    });
  async function lines(port: ReturnType<typeof setup>['port'], rowId: string) {
    const page = await port.history(2025, '20', rowId, 1);
    if (page.kind !== 'ok') throw new Error(page.kind);
    return page.value.results;
  }

  it('★M 직접입력 본문(FactorBody) 칸 = openapi GhgFactorIn · EntryRowFactorIn = factorId·custom·reason', () => {
    const schemas = (
      JSON.parse(
        readFileSync(
          resolve(
            dirname(fileURLToPath(import.meta.url)),
            '../../../../../api-py/generated/openapi.json',
          ),
          'utf8',
        ),
      ) as { components: { schemas: Record<string, { properties: object }> } }
    ).components.schemas;
    expect(Object.keys(fakeFactorBody('지어낸')).sort()).toEqual(
      Object.keys(schemas.GhgFactorIn!.properties).sort(),
    );
    expect([...ENTRY_REQUEST_FIELDS.EntryRowFactorIn!].sort()).toEqual(
      Object.keys(schemas.EntryRowFactorIn!.properties).sort(),
    );
  });

  it('setRowFactor 풀: PUT X/rows/{r}/factor {factorId 정수, reason} → 상세 · 행 factor = 그 계수 · 배출량 그 계수 글자 · factor 줄(before 선택 판 · after 그 계수 · 사유)', async () => {
    const { server, port, rowId } = await seeded();
    const out = await port.setRowFactor(
      2025,
      '20',
      rowId,
      { factorId: '23' },
      WHY,
    );
    expect(server.bodies(`PUT ${F(rowId)}`)).toStrictEqual([
      { factorId: 23, reason: WHY },
    ]);
    if (out.kind !== 'ok') throw new Error(out.kind);
    const row = plantOf(out.value.sites).rows[0]!;
    expect(row.factor && 'factorId' in row.factor && row.factor.factorId).toBe(
      '23',
    );
    expect(row.emission).toBe('2.23');
    expect(out.value.totals.bySite[1]!.values['2025']).toBe('2.23');
    const [top] = await lines(port, rowId);
    expect([top!.kind, top!.reason, top!.restorable]).toEqual([
      'factor',
      WHY,
      false,
    ]);
    expect(top!.beforeFactor).toStrictEqual({
      versionId: '2101',
      customId: null,
      name: '지어낸 경유 계수',
      isCustom: false,
    });
    expect(top!.afterFactor).toStrictEqual({
      versionId: '2301',
      customId: null,
      name: '지어낸 등유 계수',
      isCustom: false,
    });
  });

  it('setRowFactor 직접입력: 본문 {custom: 그대로, reason} · 행 factor 직접입력 꼴 · 선택 계수로 돌리면 factor null · 같은 계수는 0 바뀜', async () => {
    const { server, port, rowId } = await seeded();
    const body = custom();
    const out = await port.setRowFactor(
      2025,
      '20',
      rowId,
      { custom: body },
      WHY,
    );
    expect(server.bodies(`PUT ${F(rowId)}`)).toStrictEqual([
      { custom: body, reason: WHY },
    ]);
    if (out.kind !== 'ok') throw new Error(out.kind);
    const row = plantOf(out.value.sites).rows[0]!;
    expect(row.factor && 'customId' in row.factor && row.factor.name).toBe(
      '지어낸 직접 계수',
    );
    expect(row.emission).toBe('3.1');
    const back = await port.setRowFactor(
      2025,
      '20',
      rowId,
      { factorId: '21' },
      WHY,
    );
    if (back.kind !== 'ok') throw new Error(back.kind);
    expect(plantOf(back.value.sites).rows[0]!.factor).toBeNull();
    expect(plantOf(back.value.sites).rows[0]!.emission).toBe('1.5');
    const count = (await lines(port, rowId)).length;
    expect(
      (await port.setRowFactor(2025, '20', rowId, { factorId: '21' }, WHY))
        .kind,
    ).toBe('ok');
    expect(await lines(port, rowId)).toHaveLength(count);
  });

  it('548 흉내: 잎 단위로 셈할 수 없는 직접입력 → rejected VALIDATION_ERROR fields.custom.inputUnit · 0 씀', async () => {
    const { port, rowId } = await seeded();
    const count = (await lines(port, rowId)).length;
    expect(
      await port.setRowFactor(2025, '20', rowId, { custom: gwh() }, WHY),
    ).toStrictEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { 'custom.inputUnit': ['지어낸 단위 어긋남'] },
    });
    expect(await lines(port, rowId)).toHaveLength(count);
  });

  it('PUT factor 차례(서버 실측): 모르는 칸 422(고객사도) → 고객사 403 → 사유·둘 다·없음 422 → 404 → 단위 422 → 409 → 다른 잎 422', async () => {
    const customer = await seeded({ admin: false });
    expect(
      (
        await put(customer.server, F(customer.rowId), {
          factorId: 23,
          reason: WHY,
          x: 1,
        })
      ).status,
    ).toBe(422);
    expect(
      await customer.port.setRowFactor(
        2025,
        '20',
        customer.rowId,
        { factorId: '23' },
        WHY,
      ),
    ).toStrictEqual({ kind: 'forbidden' }); // R5 — 고객사 403
    const { port, rowId } = await seeded();
    const rejected = async (
      target: Parameters<typeof port.setRowFactor>[3],
      reason: string,
      row = rowId,
    ) => {
      const out = await port.setRowFactor(2025, '20', row, target, reason);
      return out.kind === 'rejected' ?
          Object.keys(out.fields).sort()
        : out.kind;
    };
    expect(await rejected({ factorId: '23' }, '   ')).toEqual(['reason']);
    expect(await rejected({ factorId: '23' }, '가'.repeat(501))).toEqual([
      'reason',
    ]);
    expect(await rejected({ factorId: '23' }, ` ${'가'.repeat(500)} `)).toBe(
      'ok',
    ); // trim 뒤 500
    expect(await rejected({ custom: gwh() }, '', '999')).toEqual(['reason']); // 본문 422 가 404 보다 먼저
    expect(await rejected({ custom: gwh() }, WHY, '999')).toBe('notFound'); // 404 가 단위 422 보다 먼저
    await port.lock(2025, '20');
    expect(await rejected({ custom: gwh() }, WHY)).toEqual([
      'custom.inputUnit',
    ]); // 단위 422 가 409 보다 먼저
    expect(await rejected({ custom: custom() }, WHY)).toBe('locked');
  });

  it('PUT factor 본문 둘 다·없음 422 factorId · 다른 잎 계수 422 factorId · 글자 factorId → 요청 0 failed', async () => {
    const { server, port, rowId } = await seeded();
    for (const raw of [
      { factorId: 23, custom: custom(), reason: WHY },
      { reason: WHY },
    ]) {
      const res = await put(server, F(rowId), raw);
      expect(res.status).toBe(422);
      expect(
        Object.keys(
          ((await res.json()) as { error: { fields: object } }).error.fields,
        ),
      ).toEqual(['factorId']);
    }
    const other = await port.setRowFactor(
      2025,
      '20',
      rowId,
      { factorId: '30' },
      WHY,
    );
    expect(other.kind === 'rejected' && Object.keys(other.fields)).toEqual([
      'factorId',
    ]);
    const before = server.bodies(`PUT ${F(rowId)}`).length;
    expect(
      await port.setRowFactor(2025, '20', rowId, { factorId: 'x' }, WHY),
    ).toStrictEqual({ kind: 'failed' });
    expect(server.bodies(`PUT ${F(rowId)}`)).toHaveLength(before);
  });

  it('restore: 사유를 주면 본문 {reason} · 안 주면 {} · factor 줄 복구 = 그 줄 afterFactor 로(행 factor·배출량) · 새 줄 before = 그 행 지금 계수(R3)', async () => {
    const { server, port, rowId } = await seeded();
    await port.setRowFactor(2025, '20', rowId, { factorId: '23' }, WHY);
    await port.setRowFactor(2025, '20', rowId, { custom: custom() }, WHY);
    const toPool = (await lines(port, rowId)).find(
      (l) => l.kind === 'factor' && l.afterFactor?.versionId === '2301',
    )!;
    expect(toPool.restorable).toBe(true);
    const out = await port.restore(
      2025,
      '20',
      rowId,
      toPool.historyId,
      '지어낸 복구 사유',
    );
    expect(
      server.bodies(`POST ${H(rowId)}/${toPool.historyId}/restore`),
    ).toStrictEqual([{ reason: '지어낸 복구 사유' }]);
    if (out.kind !== 'ok') throw new Error(out.kind);
    const row = plantOf(out.value.sites).rows[0]!;
    expect(row.factor && 'factorId' in row.factor && row.factor.factorId).toBe(
      '23',
    );
    expect(row.emission).toBe('2.23');
    const [top] = await lines(port, rowId);
    expect([
      top!.kind,
      top!.reason,
      top!.beforeFactor?.isCustom,
      top!.afterFactor?.versionId,
    ]).toEqual(['factor', '지어낸 복구 사유', true, '2301']); // R3: before 는 그 줄의 after 가 아니라 지금(직접입력)
    const value = (await lines(port, rowId)).find((l) => l.kind === 'value')!;
    await port.restore(2025, '20', rowId, value.historyId);
    expect(
      server.bodies(`POST ${H(rowId)}/${value.historyId}/restore`),
    ).toStrictEqual([{}]);
  });

  it('R4 restore 사유 > 500(앞뒤 빈칸 걷은 뒤) → 422 reason · 500 은 지남', async () => {
    const { port, rowId } = await seeded();
    await port.setRowFactor(2025, '20', rowId, { factorId: '23' }, WHY);
    await port.setRowFactor(2025, '20', rowId, { factorId: '21' }, WHY);
    const line = (await lines(port, rowId)).find(
      (l) => l.kind === 'factor' && l.afterFactor?.versionId === '2301',
    )!;
    const long = await port.restore(
      2025,
      '20',
      rowId,
      line.historyId,
      '가'.repeat(501),
    );
    expect(long.kind === 'rejected' && Object.keys(long.fields)).toEqual([
      'reason',
    ]);
    expect(
      (
        await port.restore(
          2025,
          '20',
          rowId,
          line.historyId,
          ` ${'가'.repeat(500)} `,
        )
      ).kind,
    ).toBe('ok');
  });

  it('가짜 548 흉내 그 자체: 진짜 표 쌍 · 행 단위 하나라도 못 바꾸면 inputUnit · 켬 ncvUnit · 끔 분모·분자 factorUnit(지어낸 표)', () => {
    expect(FAKE_UNIT_PAIRS).toHaveLength(25);
    expect(fakeCustomUnitProblem(['kL', 'L'], custom())).toStrictEqual({});
    expect(fakeCustomUnitProblem(['kL', 'Nm3'], custom())).toStrictEqual({
      'custom.inputUnit': '지어낸 단위 어긋남',
    });
    const noMjTj = FAKE_UNIT_PAIRS.filter((p) => p !== 'MJ>TJ');
    expect(fakeCustomUnitProblem(['kL'], custom(), noMjTj)).toStrictEqual({
      'custom.ncvUnit': '지어낸 단위 어긋남',
    });
    const noKgT = FAKE_UNIT_PAIRS.filter((p) => p !== 'kg>t');
    expect(fakeCustomUnitProblem(['GWh'], gwh(), noKgT)).toStrictEqual({
      'custom.factorUnit': '지어낸 단위 어긋남',
    });
    expect(
      fakeCustomUnitProblem(
        ['t'],
        custom({
          inputUnit: { kind: 'mass', unit: 't' },
          ncvEnabled: false,
          ncv: null,
          ncvUnit: null,
          factorUnit: 'kg/g',
        }),
      ),
    ).toStrictEqual({ 'custom.factorUnit': '지어낸 단위 어긋남' });
  });
});

// ── 밴드 W12-5 ①: 양식·데이터 엑셀·일괄 올리기 어댑터와 가짜 — 맨 바이트·이름·갈래·서버 판정 차례·흉내 ↔ openapi. ──
const fileOf = (bytes: number | Uint8Array, name = '지어낸.xlsx') =>
  new File(
    [typeof bytes === 'number' ? new Uint8Array(bytes) : (bytes as BlobPart)],
    name,
  );
const UPLOADS = 'POST /inventory/scope12/years/2025/uploads';
const invalid = (fields: Record<string, string[]>) => () =>
  refusal(422, 'INVALID_UPLOAD', fields);

describe('W12-5 ① 양식·데이터 엑셀', () => {
  it('template: 경로·쿼리(scope·siteId 정수) · 서버 이름 · blob', async () => {
    const { server, port } = setup();
    const out = await port.template(2025, 1, '2');
    expect(out.kind).toBe('ok');
    if (out.kind !== 'ok') return;
    expect(out.value.fileName).toBe(FAKE_TEMPLATE_NAME);
    expect(out.value.blob.size).toBe(4);
    const call = server.calls.at(-1)!;
    expect(call.path).toBe('/inventory/scope12/years/2025/template');
    expect(Object.fromEntries(call.query)).toEqual({ scope: '1', siteId: '2' });
  });

  it('template: 글자 siteId 는 요청 없이 failed', async () => {
    const { server, port } = setup();
    expect(await port.template(2025, 1, '둘')).toEqual({ kind: 'failed' });
    expect(server.calls).toHaveLength(0);
  });

  it('exportFile: scope 셋이 그대로 쿼리에 · basis 없음 · 서버 이름', async () => {
    const { server, port } = setup();
    for (const scope of ['all', 1, 2] as const) {
      const out = await port.exportFile(2025, scope);
      expect(out.kind).toBe('ok');
      if (out.kind === 'ok') expect(out.value.fileName).toBe(FAKE_EXPORT_NAME);
      expect(Object.fromEntries(server.calls.at(-1)!.query)).toEqual({
        scope: `${scope}`,
      });
    }
  });

  it('이름을 못 읽으면 고정 이름 · 깨진 퍼센트는 filename= 으로', async () => {
    const { server, port } = setup();
    const answer = (disposition: string | null) => () =>
      new Response(new Uint8Array([1]), {
        status: 200,
        headers: {
          'Content-Type': ENTRY_XLSX_TYPE,
          ...(disposition === null ?
            {}
          : { 'Content-Disposition': disposition }),
        },
      });
    const key = 'GET /inventory/scope12/years/2025/export';
    server.override[key] = [
      answer(null),
      answer(`attachment; filename="a.xlsx"; filename*=utf-8''%E0%A4%A`),
    ];
    const first = await port.exportFile(2025, 'all');
    const second = await port.exportFile(2025, 'all');
    expect(first.kind === 'ok' && first.value.fileName).toBe(
      'scope12-data.xlsx',
    );
    expect(second.kind === 'ok' && second.value.fileName).toBe('a.xlsx');
  });

  it('갈래: 404 notFound · 회사 거절 refused · 끊김 failed', async () => {
    const empty = setup();
    expect(await empty.port.exportFile(2024, 'all')).toEqual({
      kind: 'notFound',
    });
    const refused = setup({ company: 'COMPANY_AMBIGUOUS' });
    expect((await refused.port.template(2025, 1, '2')).kind).toBe('refused');
    const cut = setup();
    cut.server.override['GET /inventory/scope12/years/2025/export'] =
      unreachable;
    expect(await cut.port.exportFile(2025, 'all')).toEqual({ kind: 'failed' });
  });

  it('가짜: scope 밖 422 fields.scope(양식은 all 도) · 켠 사업장 아닌 siteId 404 · 뿌리 안 고른 잎 0 은 양식 404 · 데이터 200', async () => {
    const { server } = setup();
    const get = (query: string, what = 'template') =>
      server.send(
        new Request(
          `http://test.local/api/inventory/scope12/years/2025/${what}?${query}`,
        ),
      );
    const bad = await get('scope=all&siteId=2');
    expect(bad.status).toBe(422);
    expect((await bad.json()).error.fields.scope).toHaveLength(1);
    expect((await get('scope=3', 'export')).status).toBe(422);
    expect((await get('scope=1&siteId=999')).status).toBe(404);
    expect((await get('scope=2&siteId=2')).status).toBe(404);
    expect((await get('scope=2', 'export')).status).toBe(200);
  });
});

describe('W12-5 ① 양식 scope 없음(서버 실측)', () => {
  it('서버처럼 scope 없음은 양식·데이터 다 200 · all 은 양식만 422', async () => {
    const { server } = setup();
    const get = (query: string) =>
      server.send(
        new Request(
          `http://test.local/api/inventory/scope12/years/2025/${query}`,
        ),
      );
    expect((await get('template')).status).toBe(200);
    expect((await get('template?siteId=2')).status).toBe(200);
    expect((await get('export')).status).toBe(200);
    expect((await get('template?scope=all&siteId=2')).status).toBe(422);
    expect((await get('export?scope=all')).status).toBe(200);
  });
});

describe('W12-5 ① 올리기', () => {
  it('맨 바이트 그대로 · Content-Type xlsx · 쿼리 0 · 답 넷', async () => {
    const bytes = new Uint8Array([9, 8, 7, 0, 255]);
    const result = { added: 1, filled: 3, unchanged: 2, unresolved: 0 };
    const { server, port } = setup({
      uploadAnswers: [() => json(200, result)],
    });
    expect(await port.upload(2025, fileOf(bytes))).toEqual({
      kind: 'ok',
      value: result,
    });
    const call = server.calls.at(-1)!;
    expect(`${call.method} ${call.path}`).toBe(UPLOADS);
    expect([...call.bytes!]).toEqual([...bytes]);
    expect(call.contentType).toBe(ENTRY_XLSX_TYPE);
    expect([...call.query.keys()]).toEqual([]);
  });

  it('갈래: INVALID_UPLOAD 만 rejected(fields 그대로·차례 그대로) · 413 · 409 · 404 · 회사 거절', async () => {
    const fields = { '월!C3': ['지어낸 값'], '년도!A2': ['지어낸 줄'] };
    const { port } = setup({
      uploadAnswers: [
        invalid(fields),
        () => refusal(409, 'LOCKED'),
        () => refusal(404, 'NOT_FOUND'),
      ],
    });
    const rejected = await port.upload(2025, fileOf(1));
    expect(rejected).toEqual({ kind: 'rejected', fields });
    if (rejected.kind === 'rejected')
      expect(Object.keys(rejected.fields)).toEqual(['월!C3', '년도!A2']);
    expect(await port.upload(2025, fileOf(1))).toEqual({ kind: 'locked' });
    expect(await port.upload(2025, fileOf(1))).toEqual({ kind: 'notFound' });
    expect(await port.upload(2025, fileOf(FAKE_UPLOAD_MAX + 1))).toEqual({
      kind: 'tooLarge',
    });
    // 흉내 상한 = 화면 거름 = 서버 경로 상한(20MB — MARC-ENT-593)
    expect(FAKE_UPLOAD_MAX).toBe(ENTRY_UPLOAD_MAX_BYTES);
    const refused = setup({ company: 'COMPANY_AMBIGUOUS' });
    expect((await refused.port.upload(2025, fileOf(1))).kind).toBe('refused');
  });

  it('★ 그 밖 422·5xx·끊김·꼴 틀림은 다 failed(rejected 아님)', async () => {
    const { port } = setup({
      uploadAnswers: [
        () => refusal(422, 'VALIDATION_ERROR', { year: ['지어낸'] }),
        () => refusal(503, 'SERVICE_UNAVAILABLE'),
        unreachable,
        () => json(200, { added: 1, filled: 1, unchanged: 0, skipped: 0 }),
        () => json(200, { added: -1, filled: 1, unchanged: 0, unresolved: 0 }),
      ],
    });
    for (let i = 0; i < 5; i += 1)
      expect(await port.upload(2025, fileOf(1))).toEqual({ kind: 'failed' });
  });

  it('파일을 못 읽으면 요청 없이 unreadable(보내지 않음이 확실 — failed 아님)', async () => {
    const { server, port } = setup();
    const broken = fileOf(1);
    broken.arrayBuffer = () => Promise.reject(new Error('지어낸 읽기 실패'));
    expect(await port.upload(2025, broken)).toEqual({ kind: 'unreadable' });
    expect(server.calls).toHaveLength(0);
  });

  it('가짜 차례: 회사 400 → 413 → 선택 0 404 → 빈 바이트 422 file → 심는 답', async () => {
    const planted = invalid({ file: ['지어낸 틀린 파일'] });
    const company = setup({
      company: 'COMPANY_AMBIGUOUS',
      uploadAnswers: [planted],
    });
    expect(
      (await company.port.upload(2025, fileOf(FAKE_UPLOAD_MAX + 1))).kind,
    ).toBe('refused');
    const size = setup({ uploadAnswers: [planted] });
    // 413 이 404 앞: 선택 0 인 해에도 큰 파일은 413.
    expect(await size.port.upload(2024, fileOf(FAKE_UPLOAD_MAX + 1))).toEqual({
      kind: 'tooLarge',
    });
    // 선택 0 이면 틀린 파일이어도 404(심는 답을 꺼내지 않는다).
    expect(await size.port.upload(2024, fileOf(1))).toEqual({
      kind: 'notFound',
    });
    expect(size.server.uploadAnswers).toHaveLength(1);
    const blank = await size.port.upload(2025, fileOf(0));
    expect(blank).toEqual({
      kind: 'rejected',
      fields: { file: ['지어낸 빈 파일'] },
    });
    expect(size.server.uploadAnswers).toHaveLength(1);
    expect((await size.port.upload(2025, fileOf(1))).kind).toBe('rejected');
    expect(size.server.uploadAnswers).toHaveLength(0);
    // 딱 상한은 413 이 아니다(심은 답이 비어 넷 다 0 인 200).
    expect(await size.port.upload(2025, fileOf(FAKE_UPLOAD_MAX))).toEqual({
      kind: 'ok',
      value: { added: 0, filled: 0, unchanged: 0, unresolved: 0 },
    });
  });

  it('「표를 바꾼 뒤 끊김」: 답은 failed 인데 표에는 새 값', async () => {
    const options = fakeEntryOptions();
    const { server, port } = setup({
      ...options,
      uploadAnswers: [
        () => {
          options.entryValues!['20']!['2025'] = '99.5';
          return unreachable();
        },
      ],
    });
    expect(await port.upload(2025, fileOf(1))).toEqual({ kind: 'failed' });
    expect(server.count(UPLOADS)).toBe(1);
    const rows = await port.rows(2025);
    expect(JSON.stringify(rows)).toContain('99.5');
  });
});

describe('W12-5 ① 흉내 ↔ openapi', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  interface Operation {
    parameters?: { name: string }[];
    requestBody?: { content: Record<string, unknown> };
    responses: Record<string, { content?: Record<string, unknown> }>;
  }
  const openapi = JSON.parse(
    readFileSync(
      resolve(here, '../../../../../api-py/generated/openapi.json'),
      'utf8',
    ),
  ) as {
    paths: Record<string, Record<string, Operation>>;
    components: { schemas: Record<string, { required?: string[] }> };
  };
  const route = (name: string) =>
    openapi.paths[`/inventory/scope12/years/{year}/${name}`]!;
  const upload = route('uploads').post!;
  const template = route('template').get!;
  const exported = route('export').get!;
  const sorted = (keys: readonly string[]) => [...keys].sort();

  it('ⓐ 200 본문 열쇠 = EntryUploadOut.required', async () => {
    const { server } = setup();
    const answer = await server.send(
      new Request(
        'http://test.local/api/inventory/scope12/years/2025/uploads',
        {
          method: 'POST',
          body: new Uint8Array([1]),
        },
      ),
    );
    expect(sorted(Object.keys(await answer.json()))).toEqual(
      sorted(openapi.components.schemas.EntryUploadOut!.required!),
    );
  });

  it('ⓑ 보낸 Content-Type ∈ requestBody · ⓒ 보낸 쿼리 ⊆ parameters', async () => {
    const { server, port } = setup();
    await port.upload(2025, fileOf(1));
    const sent = server.calls.at(-1)!;
    expect(Object.keys(upload.requestBody!.content)).toContain(
      sent.contentType,
    );
    expect([...sent.query.keys()]).toEqual([]);
    const names = (operation: Operation) =>
      (operation.parameters ?? []).map((parameter) => parameter.name);
    await port.template(2025, 1, '2');
    for (const name of server.calls.at(-1)!.query.keys())
      expect(names(template)).toContain(name);
    await port.exportFile(2025, 'all');
    for (const name of server.calls.at(-1)!.query.keys())
      expect(names(exported)).toContain(name);
  });

  it('ⓓ 200 미디어 = 가짜가 낸 미디어', async () => {
    const { server } = setup();
    const get = (what: string) =>
      server.send(
        new Request(
          `http://test.local/api/inventory/scope12/years/2025/${what}`,
        ),
      );
    for (const [what, operation] of [
      ['template?scope=1', template],
      ['export?scope=all', exported],
    ] as const) {
      const answer = await get(what);
      expect(Object.keys(operation.responses['200']!.content!)).toEqual([
        answer.headers.get('Content-Type'),
      ]);
      expect(answer.headers.get('X-Content-Type-Options')).toBe('nosniff');
    }
  });

  it('ⓔ 오류 본문 열쇠 = ErrorDetail.required · ⓕ 쓰는 상태 번호가 responses 에 있음', async () => {
    const { server } = setup({
      uploadAnswers: [
        invalid({ file: ['지어낸'] }),
        () => refusal(409, 'LOCKED'),
      ],
    });
    const post = (size: number) =>
      server.send(
        new Request(
          'http://test.local/api/inventory/scope12/years/2025/uploads',
          { method: 'POST', body: new Uint8Array(size) },
        ),
      );
    const answers = [
      await post(1),
      await post(1),
      await post(FAKE_UPLOAD_MAX + 1),
    ];
    expect(answers.map((answer) => answer.status)).toEqual([422, 409, 413]);
    for (const answer of answers)
      expect(sorted(Object.keys((await answer.json()).error))).toEqual(
        sorted(openapi.components.schemas.ErrorDetail!.required!),
      );
    for (const status of ['200', '400', '404', '409', '413', '422'])
      expect(Object.keys(upload.responses)).toContain(status);
    for (const status of ['200', '400', '404', '422']) {
      expect(Object.keys(template.responses)).toContain(status);
      expect(Object.keys(exported.responses)).toContain(status);
    }
  });
});
