// 온실가스 조직구조 실어댑터(밴드 W12-0a ① — 발주서 §3 1): 진짜 createApi 에 가짜 서버(api/testing.ts)를 물려
//   경로 열하나의 메서드·경로·쿼리·본문 열쇠·id 정수를 단언한다. 어느 요청에도 companyId 가 없다.
//   갈래: 읽기 ok·refused(회사 셋)·failed(꼴 틀림·5xx·끊김), 상세 missing(404). 쓰기 rejected 의 code 는 다섯만(그 밖 null)·fields·서버 message 0.
//   밴드 K1b-3: 상세 거울에 updatedAt(없으면 failed) · PUT 본문 updatedAt 은 받은 글자 그대로, POST 본문에는 없음 · 409 STALE → rejected.
//   거울 칸 이름이 openapi.json 의 스키마 칸과 같다(★E).
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import {
  branchPutBody,
  branchSaveBody,
  draftOf,
  emptyDraft,
} from '../model/index.ts';
import { MIRRORED } from './contract/index.ts';
import {
  BRANCH_PAGE_SIZE,
  FACILITY_CODE_PAGE_SIZE,
  createFacilityCodeAdminPort,
  createGhgOrganizationPort,
} from './index.ts';
import {
  codesByName,
  fakeBranch,
  fakeCodes,
  fakeGhgServer,
  fakeHeadquarters,
  json,
  refusal,
  unreachable,
} from './testing.ts';
import type { FakeGhgServerOptions } from './testing.ts';

const BASE = 'http://test.local/api';

function setup(options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer({
    baseUrl: BASE,
    branches: [
      fakeHeadquarters(),
      fakeBranch(7, '제1공장'),
      fakeBranch(8, '제2공장', { inventoryEnabled: false }),
    ],
    ...options,
  });
  const api = createApi({ baseUrl: BASE, fetch: server.send });
  return {
    server,
    port: createGhgOrganizationPort({ api }),
    admin: createFacilityCodeAdminPort({ api }),
  };
}

const keys = (server: ReturnType<typeof setup>['server']) =>
  server.calls.map((call) => `${call.method} ${call.path}`);
const lastQuery = (server: ReturnType<typeof setup>['server']) =>
  Object.fromEntries(server.calls.at(-1)!.query);
/** 본문 어디에도 companyId 가 없다. */
const noCompany = (server: ReturnType<typeof setup>['server']) => {
  for (const call of server.calls) {
    expect(JSON.stringify(call.body ?? {})).not.toContain('companyId');
    expect(call.query.has('companyId')).toBe(false);
  }
};

describe('GET /branches', () => {
  it('쿼리 page·pageSize(빈 q 는 싣지 않음) · 답은 본사 먼저 쪽 그대로(id 글자)', async () => {
    const { server, port } = setup();
    const outcome = await port.listBranches({ q: '', page: 1 });
    expect(keys(server)).toEqual(['GET /branches']);
    expect(lastQuery(server)).toEqual({
      page: '1',
      pageSize: String(BRANCH_PAGE_SIZE),
    });
    expect(BRANCH_PAGE_SIZE).toBe(20);
    expect(outcome.kind).toBe('ok');
    if (outcome.kind !== 'ok') return;
    expect(outcome.value.results.map((b) => b.id)).toEqual(['1', '7', '8']);
    expect(outcome.value.results[0]).toEqual({
      id: '1',
      name: '본사',
      isHeadquarters: true,
      inventoryEnabled: true,
      externalId: null,
      createdAt: '2026-10-28T09:00:00+09:00',
    });
    expect(outcome.value).toMatchObject({
      count: 3,
      totalPages: 1,
      page: 1,
      hasNext: false,
      hasPrevious: false,
    });
    noCompany(server);
  });

  it('q 는 앞뒤 공백을 걷어 싣는다 · 쪽 번호 그대로', async () => {
    const { server, port } = setup();
    await port.listBranches({ q: ' 제1 ', page: 3 });
    expect(lastQuery(server)).toEqual({
      q: '제1',
      page: '3',
      pageSize: '20',
    });
  });

  it.each([
    ['COMPANY_AMBIGUOUS', 'ambiguous'],
    ['COMPANY_INACTIVE', 'inactive'],
    ['COMPANY_NOT_FOUND', 'not_found'],
  ] as const)('회사 거절 %s → refused %s', async (code, company) => {
    const { port } = setup({ company: code });
    expect(await port.listBranches({ q: '', page: 1 })).toEqual({
      kind: 'refused',
      company,
    });
    expect(await port.listFacilityCodes()).toEqual({
      kind: 'refused',
      company,
    });
  });

  it('꼴 틀림·5xx·끊김·그 밖 거절 → failed', async () => {
    const { server, port } = setup();
    server.override['GET /branches'] = [
      () => json(200, { count: 1, results: [] }),
      () => json(200, { ...emptyPage(), results: [{ id: 1, name: 'x' }] }),
      () => refusal(500, 'SERVER_ERROR'),
      () => refusal(403, 'FORBIDDEN'),
      unreachable,
    ];
    for (let i = 0; i < 5; i++)
      expect(await port.listBranches({ q: '', page: 1 })).toEqual({
        kind: 'failed',
      });
  });

  it('모르는 칸은 버리고 지난다', async () => {
    const { server, port } = setup();
    server.override['GET /branches'] = () =>
      json(200, { ...emptyPage(), extra: 1 });
    const outcome = await port.listBranches({ q: '', page: 1 });
    expect(outcome).toEqual({ kind: 'ok', value: emptyPage() });
  });
});

const emptyPage = () => ({
  count: 0,
  totalPages: 1,
  page: 1,
  pageSize: 20,
  hasNext: false,
  hasPrevious: false,
  results: [],
});

describe('GET /branches/{branch_id}', () => {
  it('경로 id 정수 · 답은 facilities 까지(id 글자)', async () => {
    const { server, port } = setup();
    const outcome = await port.getBranch('1');
    expect(keys(server)).toEqual(['GET /branches/1']);
    expect(outcome).toEqual({ kind: 'ok', value: fakeHeadquarters() });
  });

  it('updatedAt 이 없거나 글자가 아닌 상세 → failed(거울 — 판 버전 없이 저장하지 않는다)', async () => {
    const { server, port } = setup();
    const withoutVersion: Record<string, unknown> = { ...fakeHeadquarters() };
    delete withoutVersion.updatedAt;
    server.override['GET /branches/1'] = [
      () => json(200, withoutVersion),
      () => json(200, { ...fakeHeadquarters(), updatedAt: null }),
    ];
    expect(await port.getBranch('1')).toEqual({ kind: 'failed' });
    expect(await port.getBranch('1')).toEqual({ kind: 'failed' });
  });

  it('404 NOT_FOUND → missing · 정수 글자가 아닌 id 는 요청 없이 missing', async () => {
    const { server, port } = setup();
    expect(await port.getBranch('99')).toEqual({ kind: 'missing' });
    expect(await port.getBranch('new')).toEqual({ kind: 'missing' });
    expect(keys(server)).toEqual(['GET /branches/99']);
  });

  it('회사 거절 → refused · 끊김 → failed', async () => {
    const { server, port } = setup({ company: 'COMPANY_INACTIVE' });
    expect(await port.getBranch('1')).toEqual({
      kind: 'refused',
      company: 'inactive',
    });
    server.override['GET /branches/1'] = unreachable;
    expect(await port.getBranch('1')).toEqual({ kind: 'failed' });
  });
});

describe('POST /branches · PUT /branches/{branch_id}', () => {
  it('POST 본문 {name, inventoryEnabled, facilities[{facilityCodeId 정수, detailName}]} → 201 상세', async () => {
    const { server, port } = setup();
    const draft = { ...emptyDraft(), name: ' 제3공장 ' };
    draft.facilities.push({
      key: 'n1',
      id: null,
      facilityCodeId: '2',
      facilityName: '지어낸 발전기',
      detailName: '1호기',
    });
    const outcome = await port.createBranch(branchSaveBody(draft));
    expect(keys(server)).toEqual(['POST /branches']);
    expect(server.bodies('POST /branches')[0]).toStrictEqual({
      name: '제3공장',
      inventoryEnabled: true,
      facilities: [{ facilityCodeId: 2, detailName: '1호기' }],
    });
    expect(outcome.kind).toBe('ok');
    if (outcome.kind !== 'ok') return;
    expect(outcome.value).toMatchObject({ id: '9', name: '제3공장' });
    expect(outcome.value.facilities[0]).toMatchObject({
      facilityCodeId: '2',
      facilityCode: 'F0002',
    });
    noCompany(server);
  });

  it('PUT 경로 id 정수 · 남은 줄 id 정수 · 빠진 줄은 본문에 없다 → 200 상세', async () => {
    const { server, port } = setup();
    const draft = draftOf(fakeHeadquarters());
    draft.facilities.push({
      key: 'n1',
      id: null,
      facilityCodeId: '3',
      facilityName: '지어낸 사업장 차량',
      detailName: '지게차',
    });
    const first = await port.saveBranch(
      '1',
      branchPutBody(draft, fakeHeadquarters().updatedAt),
    );
    expect(server.bodies('PUT /branches/1')[0]).toStrictEqual({
      name: '본사',
      inventoryEnabled: true,
      facilities: [
        { id: 1, facilityCodeId: 1, detailName: '1호기' },
        { facilityCodeId: 3, detailName: '지게차' },
      ],
      updatedAt: '2026-10-28T09:00:00.000001+09:00',
    });
    const saved = server.branches()[0]!;
    // 200 의 판은 새 글자 — 다음 저장은 그 글자를 그대로 싣는다.
    expect(first.kind === 'ok' && first.value.updatedAt).toBe(saved.updatedAt);
    expect(saved.updatedAt).not.toBe(fakeHeadquarters().updatedAt);
    const next = draftOf(saved);
    next.facilities = next.facilities.slice(1);
    const outcome = await port.saveBranch(
      '1',
      branchPutBody(next, saved.updatedAt),
    );
    expect(server.bodies('PUT /branches/1')[1]).toStrictEqual({
      name: '본사',
      inventoryEnabled: true,
      facilities: [{ id: 2, facilityCodeId: 3, detailName: '지게차' }],
      updatedAt: saved.updatedAt,
    });
    expect(outcome.kind === 'ok' && outcome.value.facilities).toEqual([
      {
        id: '2',
        facilityCodeId: '3',
        facilityCode: 'F0003',
        facilityName: '지어낸 사업장 차량',
        detailName: '지게차',
      },
    ]);
  });

  it('422 VALIDATION_ERROR → rejected code·fields(서버 message 없음)', async () => {
    const { port } = setup();
    const outcome = await port.createBranch({
      name: '',
      inventoryEnabled: true,
      facilities: [],
    });
    expect(outcome).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { name: ['지어낸 빈 이름'] },
    });
    expect(JSON.stringify(outcome)).not.toContain('지어낸-');
  });

  it('409 STALE(낡은 판) → rejected STALE · 아무것도 쓰이지 않음 · 판 없는 본문은 422 fields.updatedAt(가짜도 서버처럼)', async () => {
    const { server, port } = setup();
    const before = await port.getBranch('7');
    if (before.kind !== 'ok') throw new Error('읽기 실패');
    server.bumpBranch('7', { facilityCodeId: '2', detailName: '다른 탭 줄' });
    const after = server.branches().find((b) => b.id === '7')!;
    const draft = { ...draftOf(before.value), name: '제1공장 고침' };
    expect(
      await port.saveBranch('7', branchPutBody(draft, before.value.updatedAt)),
    ).toEqual({ kind: 'rejected', code: 'STALE', fields: {} });
    expect(server.branches().find((b) => b.id === '7')).toEqual(after);
    expect(
      await port.saveBranch('7', {
        ...branchSaveBody(draft),
        updatedAt: '',
      }),
    ).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { updatedAt: expect.any(Array) },
    });
    // 다시 읽은 판 위에서 고쳐 보내면 200 — 다른 탭의 줄이 남는다.
    const fresh = await port.saveBranch(
      '7',
      branchPutBody(
        { ...draftOf(after), name: '제1공장 고침' },
        after.updatedAt,
      ),
    );
    expect(fresh.kind === 'ok' && fresh.value.name).toBe('제1공장 고침');
    expect(fresh.kind === 'ok' && fresh.value.facilities).toHaveLength(1);
  });

  it('409 HEADQUARTERS_LOCKED·IN_USE·404 NOT_FOUND → rejected 그 code · 모르는 code → null', async () => {
    const { server, port } = setup();
    const body = {
      name: '본사',
      inventoryEnabled: false,
      facilities: [],
      updatedAt: fakeHeadquarters().updatedAt,
    };
    expect(await port.saveBranch('1', body)).toEqual({
      kind: 'rejected',
      code: 'HEADQUARTERS_LOCKED',
      fields: {},
    });
    expect(await port.saveBranch('99', body)).toEqual({
      kind: 'rejected',
      code: 'NOT_FOUND',
      fields: {},
    });
    server.override['PUT /branches/7'] = [
      () => refusal(409, 'IN_USE'),
      () => refusal(409, 'SOMETHING_ELSE', { name: ['x'] }),
    ];
    expect(await port.saveBranch('7', body)).toEqual({
      kind: 'rejected',
      code: 'IN_USE',
      fields: {},
    });
    expect(await port.saveBranch('7', body)).toEqual({
      kind: 'rejected',
      code: null,
      fields: {},
    });
  });

  it('회사 거절 → refused · 끊김·5xx 글자 본문·꼴 틀린 답 → failed · 글자 id 는 요청 없이 failed', async () => {
    const { server, port } = setup();
    const body = { name: '제9공장', inventoryEnabled: true, facilities: [] };
    server.override['POST /branches'] = [
      () => refusal(400, 'COMPANY_AMBIGUOUS'),
      unreachable,
      () => new Response('boom', { status: 502 }),
      () => json(201, { id: 9 }),
    ];
    expect(await port.createBranch(body)).toEqual({
      kind: 'refused',
      company: 'ambiguous',
    });
    for (let i = 0; i < 3; i++)
      expect(await port.createBranch(body)).toEqual({ kind: 'failed' });
    const before = server.calls.length;
    expect(await port.saveBranch('abc', { ...body, updatedAt: 'x' })).toEqual({
      kind: 'failed',
    });
    expect(server.calls.length).toBe(before);
  });
});

describe('POST /branches/inventory · /branches/delete', () => {
  it('inventory 본문 {ids 정수, enabled} → 바뀐 수', async () => {
    const { server, port } = setup();
    expect(await port.setInventory(['7', '8'], false)).toEqual({
      kind: 'ok',
      value: 2,
    });
    expect(server.bodies('POST /branches/inventory')[0]).toStrictEqual({
      ids: [7, 8],
      enabled: false,
    });
    expect(server.branches().map((b) => b.inventoryEnabled)).toEqual([
      true,
      false,
      false,
    ]);
  });

  it('끄기에 본사 → 409 HEADQUARTERS_LOCKED rejected', async () => {
    const { port } = setup();
    expect(await port.setInventory(['1', '7'], false)).toEqual({
      kind: 'rejected',
      code: 'HEADQUARTERS_LOCKED',
      fields: {},
    });
  });

  it('delete 본문 {ids 정수} → 바뀐 수, 목록에서 빠진다 · 본사 409 · IN_USE 409', async () => {
    const { server, port } = setup();
    expect(await port.deleteBranches(['8'])).toEqual({ kind: 'ok', value: 1 });
    expect(server.bodies('POST /branches/delete')[0]).toStrictEqual({
      ids: [8],
    });
    expect(server.branches().map((b) => b.id)).toEqual(['1', '7']);
    expect(await port.deleteBranches(['1'])).toEqual({
      kind: 'rejected',
      code: 'HEADQUARTERS_LOCKED',
      fields: {},
    });
    server.override['POST /branches/delete'] = () => refusal(409, 'IN_USE');
    expect(await port.deleteBranches(['7'])).toEqual({
      kind: 'rejected',
      code: 'IN_USE',
      fields: {},
    });
  });

  it('글자 id 가 섞이면 요청 없이 failed', async () => {
    const { server, port } = setup();
    expect(await port.setInventory(['7', 'x'], true)).toEqual({
      kind: 'failed',
    });
    expect(await port.deleteBranches(['']).then((o) => o.kind)).toBe('failed');
    expect(server.calls).toHaveLength(0);
  });
});

describe('GET /facility-codes', () => {
  it('items 를 서버 차례 그대로', async () => {
    const { server, port } = setup();
    expect(await port.listFacilityCodes()).toEqual({
      kind: 'ok',
      // 서버 차례 = 이름 가나다 → id(W12-0b1 ① L3 — 가짜가 만든 차례로 내던 것을 고침).
      value: codesByName(fakeCodes()),
    });
    expect(keys(server)).toEqual(['GET /facility-codes']);
    expect(lastQuery(server)).toEqual({});
  });

  it('꼴 틀림 → failed', async () => {
    const { server, port } = setup();
    server.override['GET /facility-codes'] = () => json(200, { items: [{}] });
    expect(await port.listFacilityCodes()).toEqual({ kind: 'failed' });
  });
});

describe('/admin/facility-codes', () => {
  it('list: 쿼리 page·pageSize 100 · 만든 차례·inUse', async () => {
    const { server, admin } = setup();
    const outcome = await admin.list(1);
    expect(FACILITY_CODE_PAGE_SIZE).toBe(100);
    expect(keys(server)).toEqual(['GET /admin/facility-codes']);
    expect(lastQuery(server)).toEqual({ page: '1', pageSize: '100' });
    expect(outcome.kind === 'ok' && outcome.value.results).toEqual(
      fakeCodes().map((code) => ({ ...code, inUse: false })),
    );
  });

  it('고객사 403 → failed(회사 거절 아님)', async () => {
    const { admin } = setup({ admin: false });
    expect(await admin.list(1)).toEqual({ kind: 'failed' });
    expect(await admin.create('x')).toEqual({
      kind: 'rejected',
      code: null,
      fields: {},
    });
  });

  it('create: 본문 {name}(trim) → FacilityCodeOut · 겹침 422 fields.name', async () => {
    const { server, admin } = setup();
    expect(await admin.create(' 지어낸 냉동기 ')).toEqual({
      kind: 'ok',
      value: { id: '4', code: 'F0004', name: '지어낸 냉동기' },
    });
    expect(server.bodies('POST /admin/facility-codes')[0]).toStrictEqual({
      name: '지어낸 냉동기',
    });
    expect(await admin.create('지어낸 보일러')).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { name: ['지어낸 겹침'] },
    });
  });

  it('rename: PATCH 경로 code_id 정수 · 본문 {name} · code 그대로 · 404', async () => {
    const { server, admin } = setup();
    expect(await admin.rename('2', '지어낸 비상발전기')).toEqual({
      kind: 'ok',
      value: { id: '2', code: 'F0002', name: '지어낸 비상발전기' },
    });
    expect(keys(server)).toEqual(['PATCH /admin/facility-codes/2']);
    expect(server.bodies('PATCH /admin/facility-codes/2')[0]).toStrictEqual({
      name: '지어낸 비상발전기',
    });
    expect(await admin.rename('99', 'x')).toEqual({
      kind: 'rejected',
      code: 'NOT_FOUND',
      fields: {},
    });
    expect(await admin.rename('F0002', 'x')).toEqual({ kind: 'failed' });
    expect(server.calls).toHaveLength(2);
  });

  it('remove: 본문 {ids 정수} → 바뀐 수 · 409 IN_USE(S12a 가 더함) rejected', async () => {
    const { server, admin } = setup();
    expect(await admin.remove(['1', '3'])).toEqual({ kind: 'ok', value: 2 });
    expect(server.bodies('POST /admin/facility-codes/delete')[0]).toStrictEqual(
      { ids: [1, 3] },
    );
    expect(server.codes().map((c) => c.id)).toEqual(['2']);
    server.override['POST /admin/facility-codes/delete'] = () =>
      refusal(409, 'IN_USE');
    expect(await admin.remove(['2'])).toEqual({
      kind: 'rejected',
      code: 'IN_USE',
      fields: {},
    });
  });
});

describe('계약 거울(★E)', () => {
  it('거울 칸 이름이 openapi.json 의 스키마 칸과 같다(일곱 꼴 + 줄 꼴 둘)', () => {
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
    expect(Object.keys(MIRRORED).sort()).toEqual(
      [
        'AdminFacilityCodeOut',
        'AdminFacilityCodePageOut',
        'BranchDetailOut',
        'BranchFacilityOut',
        'BranchOut',
        'BranchPageOut',
        'CountOut',
        'FacilityCodeOut',
        'FacilityCodesOut',
      ].sort(),
    );
    for (const [name, fields] of Object.entries(MIRRORED))
      expect([...fields].sort(), name).toEqual(
        Object.keys(openapi.components.schemas[name]!.properties).sort(),
      );
  });
});

// 밴드 W12-0b1 ① L3(sid:MARC-ISSUE-426): 가짜(api/testing.ts) 그 자체를 잰다 — 코드 지우기는 삭제 표시 · 차례·검색은 서버대로.
//   e2e 흉내(e2e/ghg-server.ts)도 같은 규칙이다(그쪽은 e2e/ghg-server.spec.ts 의 W12-0b1 ① 시험).
describe('가짜 서버 규칙(W12-0b1 ① L3)', () => {
  const plant = (): ReturnType<typeof fakeBranch> => ({
    ...fakeBranch(7, '제1공장'),
    facilities: [
      {
        id: '5',
        facilityCodeId: '2',
        facilityCode: 'F0002',
        facilityName: '지어낸 발전기',
        detailName: '2호기',
      },
    ],
  });

  it('지운 코드: 두 목록에서 빠짐 · 그 코드를 그대로 두는 기존 줄은 이름 그대로 저장 통과 · 새 줄·코드 바꿈으로 고르면 422 fields.facilityCodeId', async () => {
    const { port, admin } = setup({ branches: [fakeHeadquarters(), plant()] });
    expect(await admin.remove(['2'])).toEqual({ kind: 'ok', value: 1 });
    const codes = await port.listFacilityCodes();
    expect(codes.kind === 'ok' && codes.value.map((c) => c.id)).toEqual([
      '1',
      '3',
    ]);
    const page = await admin.list(1);
    expect(page.kind === 'ok' && page.value.results.map((c) => c.id)).toEqual([
      '1',
      '3',
    ]);
    const before = await port.getBranch('7');
    if (before.kind !== 'ok') throw new Error('읽기 실패');
    const kept = await port.saveBranch(
      '7',
      branchPutBody(draftOf(before.value), before.value.updatedAt),
    );
    if (kept.kind !== 'ok') throw new Error('저장 실패');
    expect(kept.value.facilities).toEqual([
      expect.objectContaining({
        id: '5',
        facilityCodeId: '2',
        facilityName: '지어낸 발전기',
      }),
    ]);
    const added = await port.saveBranch('7', {
      name: '제1공장',
      inventoryEnabled: true,
      facilities: [
        { id: 5, facilityCodeId: 2, detailName: '2호기' },
        { facilityCodeId: 2, detailName: '3호기' },
      ],
      updatedAt: kept.value.updatedAt,
    });
    expect(added).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { facilityCodeId: expect.any(Array) },
    });
    const switched = await port.saveBranch('7', {
      name: '제1공장',
      inventoryEnabled: true,
      facilities: [{ id: 5, facilityCodeId: 1, detailName: '2호기' }],
      updatedAt: kept.value.updatedAt,
    });
    if (switched.kind !== 'ok') throw new Error('저장 실패');
    const back = await port.saveBranch('7', {
      name: '제1공장',
      inventoryEnabled: true,
      facilities: [{ id: 5, facilityCodeId: 2, detailName: '2호기' }],
      updatedAt: switched.value.updatedAt,
    });
    expect(back).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { facilityCodeId: expect.any(Array) },
    });
    // 지운 코드는 다시 지울 수 없고(404) 이름 겹침에도 세지 않는다.
    expect(await admin.remove(['2'])).toMatchObject({ code: 'NOT_FOUND' });
    expect((await admin.create('지어낸 발전기')).kind).toBe('ok');
  });

  it('차례: /facility-codes = 이름 가나다 → id · /admin/facility-codes = 만든 차례', async () => {
    const { port, admin } = setup({
      codes: [
        { id: '1', code: 'F0001', name: '지어낸 하' },
        { id: '2', code: 'F0002', name: '지어낸 가' },
        { id: '3', code: 'F0003', name: '지어낸 나' },
      ],
    });
    const codes = await port.listFacilityCodes();
    expect(codes.kind === 'ok' && codes.value.map((c) => c.id)).toEqual([
      '2',
      '3',
      '1',
    ]);
    const page = await admin.list(1);
    expect(page.kind === 'ok' && page.value.results.map((c) => c.id)).toEqual([
      '1',
      '2',
      '3',
    ]);
  });

  it('/branches q 는 대소문자 무시 부분 일치', async () => {
    const { port } = setup({
      branches: [fakeHeadquarters(), fakeBranch(7, 'Plant North')],
    });
    const found = await port.listBranches({ q: 'plant', page: 1 });
    expect(found.kind === 'ok' && found.value.results.map((b) => b.id)).toEqual(
      ['7'],
    );
  });
});
