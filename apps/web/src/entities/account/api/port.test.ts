// 계정 어댑터: 목록 이어 받기(isNext·상한·꼴 틀림), 만들기·초기화의 code → 갈래(409·400 한 번 다시·422 fields·404),
// 임시 비밀번호는 요청 본문과 결과에만(실패 결과에는 없다), companyId 를 보내지 않는다.
// UA1W ①: 거르기 쿼리(q·status)를 쪽마다, 전체 수(limit=1), PATCH /users/{id} 의 본문 한 칸·갈래, 여럿은 id 차례로·일부 실패, 꼴 11칸.
// 시험 이름·단언 글에 생성된 비밀번호 값을 싣지 않는다.
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import { PASSWORD_GROUPS, TEMPORARY_PASSWORD_LENGTH } from '../model/index.ts';
import type { RandomFill } from '../model/index.ts';
import {
  LIST_PAGE_LIMIT,
  LIST_PAGE_SIZE,
  createAccountsPort,
} from './index.ts';
import { fakeAccount, fakeAccountsServer, json, refusal } from './testing.ts';

const BASE = 'http://test.local/api';

/** 고정 씨앗의 32비트 선형 합동. */
const seeded = (seed: number): RandomFill => {
  let state = seed >>> 0;
  return (array) => {
    for (let i = 0; i < array.length; i++) {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
      array[i] = state;
    }
    return array;
  };
};

function setup(accounts = [fakeAccount(1), fakeAccount(2)]) {
  const server = fakeAccountsServer(accounts, { baseUrl: BASE });
  const port = createAccountsPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
    random: seeded(42),
  });
  return { server, port };
}

const looksTemporary = (password: unknown) =>
  typeof password === 'string' &&
  password.length === TEMPORARY_PASSWORD_LENGTH &&
  PASSWORD_GROUPS.every((group) =>
    [...password].some((char) => group.includes(char)),
  );

describe('list — limit=100 으로 isNext 가 거짓일 때까지', () => {
  it('한 쪽이면 한 번, count 는 서버 값', async () => {
    const { server, port } = setup();
    const outcome = await port.list();
    expect(outcome).toEqual({
      kind: 'ok',
      count: 2,
      accounts: [fakeAccount(1), fakeAccount(2)],
    });
    expect(server.calls.map((call) => call.query)).toEqual([
      `?limit=${LIST_PAGE_SIZE}&offset=0`,
    ]);
  });

  it('두 쪽이면 offset 을 받은 수만큼 밀어 이어 받는다', async () => {
    const many = Array.from({ length: LIST_PAGE_SIZE + 3 }, (_, i) =>
      fakeAccount(i + 1),
    );
    const { server, port } = setup(many);
    const outcome = await port.list();
    expect(outcome.kind === 'ok' && outcome.accounts.length).toBe(
      LIST_PAGE_SIZE + 3,
    );
    expect(server.calls.map((call) => call.query)).toEqual([
      `?limit=${LIST_PAGE_SIZE}&offset=0`,
      `?limit=${LIST_PAGE_SIZE}&offset=${LIST_PAGE_SIZE}`,
    ]);
  });

  it(`상한 ${LIST_PAGE_LIMIT}쪽을 넘으면 failed(더 부르지 않는다)`, async () => {
    const { server, port } = setup();
    server.override['GET /users'] = () =>
      json(200, { count: 5000, isNext: true, results: [fakeAccount(1)] });
    expect(await port.list()).toEqual({ kind: 'failed' });
    expect(server.count('GET /users')).toBe(LIST_PAGE_LIMIT);
  });

  it.each([
    ['404 COMPANY_NOT_FOUND', () => refusal(404, 'COMPANY_NOT_FOUND')],
    ['400 COMPANY_AMBIGUOUS', () => refusal(400, 'COMPANY_AMBIGUOUS')],
    ['403 FORBIDDEN', () => refusal(403, 'FORBIDDEN')],
    ['502 빈 본문', () => new Response(null, { status: 502 })],
    ['연결 끊김', () => Promise.reject(new TypeError('끊김'))],
    ['꼴 틀림 {users: []}', () => json(200, { users: [] })],
    [
      '줄 꼴 틀림',
      () => json(200, { count: 1, isNext: false, results: [{ id: '1' }] }),
    ],
    [
      'isNext 인데 빈 쪽',
      () => json(200, { count: 3, isNext: true, results: [] }),
    ],
  ])('%s → failed 하나', async (_, answer) => {
    const { server, port } = setup();
    server.override['GET /users'] = answer;
    expect(await port.list()).toEqual({ kind: 'failed' });
  });
});

describe('create — POST /users', () => {
  it('201 → created(만든 계정과 보낸 임시 비밀번호). 본문은 username·name·password 셋, companyId 없음', async () => {
    const { server, port } = setup();
    const outcome = await port.create({ username: 'user07', name: '담당자 G' });
    expect(outcome.kind).toBe('created');
    const [body] = server.writes();
    expect(Object.keys(body!).sort()).toEqual(['name', 'password', 'username']);
    expect(body).toMatchObject({ username: 'user07', name: '담당자 G' });
    expect(looksTemporary(body!.password)).toBe(true);
    if (outcome.kind === 'created') {
      expect(outcome.password).toBe(body!.password);
      expect(outcome.account.username).toBe('user07');
      expect(outcome.account.isInitial).toBe(true);
    }
  });

  it('409 USERNAME_TAKEN → taken(한 번만 보냄, 결과에 비밀번호 없음)', async () => {
    const { server, port } = setup();
    const outcome = await port.create({ username: 'user01', name: '새 사람' });
    expect(outcome).toEqual({ kind: 'taken' });
    expect(server.count('POST /users')).toBe(1);
  });

  it('400 PASSWORD_REJECTED → 새 임시 비밀번호로 한 번만 다시(두 번째 값이 다르다) → created', async () => {
    const { server, port } = setup();
    server.override['POST /users'] = [() => refusal(400, 'PASSWORD_REJECTED')];
    const outcome = await port.create({ username: 'user07', name: '담당자 G' });
    expect(outcome.kind).toBe('created');
    const [first, second] = server.writes();
    expect(server.count('POST /users')).toBe(2);
    expect(first!.password).not.toBe(second!.password);
    expect(outcome.kind === 'created' && outcome.password).toBe(
      second!.password,
    );
  });

  it('400 PASSWORD_REJECTED 가 두 번이면 failed(세 번째는 보내지 않는다)', async () => {
    const { server, port } = setup();
    server.override['POST /users'] = () => refusal(400, 'PASSWORD_REJECTED');
    expect(await port.create({ username: 'u', name: 'n' })).toEqual({
      kind: 'failed',
    });
    expect(server.count('POST /users')).toBe(2);
  });

  it('422 VALIDATION_ERROR → invalid(fields 의 아는 칸만), 아는 칸이 없으면 failed', async () => {
    const { server, port } = setup();
    server.override['POST /users'] = () =>
      refusal(422, 'VALIDATION_ERROR', {
        username: ['꼴'],
        'body.name': ['길이'],
      });
    expect(await port.create({ username: 'u', name: 'n' })).toEqual({
      kind: 'invalid',
      fields: ['username', 'name'],
    });
    server.override['POST /users'] = () =>
      refusal(422, 'VALIDATION_ERROR', { companyId: ['?'] });
    expect(await port.create({ username: 'u', name: 'n' })).toEqual({
      kind: 'failed',
    });
  });

  it.each([
    ['500', () => refusal(500, 'INTERNAL_ERROR')],
    ['연결 끊김', () => Promise.reject(new TypeError('끊김'))],
    ['201 꼴 틀림', () => json(201, { id: 'x' })],
  ])('%s → failed', async (_, answer) => {
    const { server, port } = setup();
    server.override['POST /users'] = answer;
    expect(await port.create({ username: 'u', name: 'n' })).toEqual({
      kind: 'failed',
    });
  });
});

describe('resetPassword — POST /users/{id}/password-reset', () => {
  it('200 → reset(계정과 보낸 임시 비밀번호). 본문은 password 하나', async () => {
    const { server, port } = setup();
    const outcome = await port.resetPassword({ id: 2 });
    expect(outcome.kind).toBe('reset');
    expect(server.calls[0]!.path).toBe('/users/2/password-reset');
    const [body] = server.writes();
    expect(Object.keys(body!)).toEqual(['password']);
    expect(looksTemporary(body!.password)).toBe(true);
    expect(outcome.kind === 'reset' && outcome.password).toBe(body!.password);
  });

  it('404 USER_NOT_FOUND → missing', async () => {
    const { port } = setup();
    expect(await port.resetPassword({ id: 99 })).toEqual({ kind: 'missing' });
  });

  it('400 PASSWORD_REJECTED → 한 번만 다시, 또 거절이면 failed', async () => {
    const { server, port } = setup();
    server.override['POST /users/2/password-reset'] = [
      () => refusal(400, 'PASSWORD_REJECTED'),
    ];
    expect((await port.resetPassword({ id: 2 })).kind).toBe('reset');
    expect(server.count('POST /users/2/password-reset')).toBe(2);
    server.override['POST /users/2/password-reset'] = () =>
      refusal(400, 'PASSWORD_REJECTED');
    expect(await port.resetPassword({ id: 2 })).toEqual({ kind: 'failed' });
    expect(server.count('POST /users/2/password-reset')).toBe(4);
  });

  it('403 FORBIDDEN → failed', async () => {
    const { server, port } = setup();
    server.override['POST /users/2/password-reset'] = () =>
      refusal(403, 'FORBIDDEN');
    expect(await port.resetPassword({ id: 2 })).toEqual({ kind: 'failed' });
  });
});

describe('list(query) — q·status 를 쪽마다 싣는다', () => {
  it('한 쪽: /users?limit=100&offset=0&q=…&status=locked 정확히', async () => {
    const { server, port } = setup();
    await port.list({ q: '담당', status: 'locked' });
    expect(server.calls.map((call) => call.query)).toEqual([
      `?limit=${LIST_PAGE_SIZE}&offset=0&q=${encodeURIComponent('담당')}&status=locked`,
    ]);
  });

  it('두 쪽이면 둘째 쪽에도 같은 쿼리', async () => {
    const many = Array.from({ length: LIST_PAGE_SIZE + 3 }, (_, i) =>
      fakeAccount(i + 1),
    );
    const { server, port } = setup(many);
    await port.list({ q: 'kim', status: 'inactive' });
    expect(server.calls.map((call) => call.query)).toEqual([
      `?limit=${LIST_PAGE_SIZE}&offset=0&q=kim&status=inactive`,
      `?limit=${LIST_PAGE_SIZE}&offset=${LIST_PAGE_SIZE}&q=kim&status=inactive`,
    ]);
  });

  it('count 는 서버의 거른 수 그대로(실린 줄 수가 아니다)', async () => {
    const { server, port } = setup();
    server.setCount({ list: 7 });
    expect(await port.list({ status: 'active' })).toMatchObject({
      kind: 'ok',
      count: 7,
    });
  });
});

describe('total — GET /users?limit=1&offset=0 의 count', () => {
  it('쿼리는 limit·offset 둘뿐, 답은 거르지 않은 수', async () => {
    const { server, port } = setup();
    server.setCount({ total: 42, list: 3 });
    expect(await port.total()).toEqual({ kind: 'ok', total: 42 });
    expect(server.calls.map((call) => call.query)).toEqual([
      '?limit=1&offset=0',
    ]);
  });

  it.each([
    ['500', () => refusal(500, 'INTERNAL_ERROR')],
    ['연결 끊김', () => Promise.reject(new TypeError('끊김'))],
    ['count 없음', () => json(200, { isNext: false, results: [] })],
    ['count 글자', () => json(200, { count: '3', isNext: false, results: [] })],
  ])('%s → failed', async (_, answer) => {
    const { server, port } = setup();
    server.override['GET /users'] = answer;
    expect(await port.total()).toEqual({ kind: 'failed' });
  });
});

describe('rename — PATCH /users/{id} 본문 {name} 하나', () => {
  it('200 → renamed(서버가 돌려준 계정), 본문 글자 정확히 {"name":"재무팀"}', async () => {
    const { server, port } = setup();
    const outcome = await port.rename({ id: 2 }, '재무팀');
    expect(server.calls).toHaveLength(1);
    expect(server.calls[0]).toMatchObject({
      method: 'PATCH',
      path: '/users/2',
      query: '',
      body: '{"name":"재무팀"}',
    });
    expect(outcome).toEqual({
      kind: 'renamed',
      account: fakeAccount(2, { name: '재무팀' }),
    });
  });

  it('404 USER_NOT_FOUND → missing', async () => {
    const { port } = setup();
    expect(await port.rename({ id: 99 }, '재무팀')).toEqual({
      kind: 'missing',
    });
  });

  it('422 VALIDATION_ERROR → invalid', async () => {
    const { server, port } = setup();
    server.override['PATCH /users/2'] = () =>
      refusal(422, 'VALIDATION_ERROR', { name: ['길이'] });
    expect(await port.rename({ id: 2 }, '재무팀')).toEqual({
      kind: 'invalid',
    });
  });

  it.each([
    ['500', () => refusal(500, 'INTERNAL_ERROR')],
    ['403', () => refusal(403, 'FORBIDDEN')],
    ['연결 끊김', () => Promise.reject(new TypeError('끊김'))],
    ['200 꼴 틀림', () => json(200, { id: 2 })],
    // JSON 은 undefined 칸을 싣지 않는다 — createdAt 이 빠진 답.
    [
      '200 createdAt 빠짐',
      () => json(200, { ...fakeAccount(2), createdAt: undefined }),
    ],
  ])('%s → failed', async (_, answer) => {
    const { server, port } = setup();
    server.override['PATCH /users/2'] = answer;
    expect(await port.rename({ id: 2 }, '재무팀')).toEqual({
      kind: 'failed',
    });
  });
});

describe('setActive — id 마다 차례로 PATCH {isActive}', () => {
  const three = () => setup([fakeAccount(1), fakeAccount(2), fakeAccount(3)]);

  it('셋 → PATCH 셋이 id 차례로, 본문 정확히 {"isActive":false}', async () => {
    const { server, port } = three();
    const outcome = await port.setActive(
      [{ id: 1 }, { id: 2 }, { id: 3 }],
      false,
    );
    expect(server.patches()).toEqual([
      { id: 1, body: '{"isActive":false}' },
      { id: 2, body: '{"isActive":false}' },
      { id: 3, body: '{"isActive":false}' },
    ]);
    expect(outcome).toEqual({ done: [1, 2, 3], failed: [] });
    expect(server.accounts.map((row) => row.isActive)).toEqual([
      false,
      false,
      false,
    ]);
  });

  it('차례로(병렬 아님): 앞 요청의 답이 오기 전에 다음을 보내지 않는다', async () => {
    const { server, port } = three();
    let release!: () => void;
    server.override['PATCH /users/1'] = () =>
      new Promise<Response>((resolve) => {
        release = () => resolve(json(200, fakeAccount(1, { isActive: false })));
      });
    const pending = port.setActive([{ id: 1 }, { id: 2 }], false);
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(server.patches().map((call) => call.id)).toEqual([1]);
    release();
    expect(await pending).toEqual({ done: [1, 2], failed: [] });
    expect(server.patches().map((call) => call.id)).toEqual([1, 2]);
  });

  it('둘째만 500 → {done:[1,3], failed:[2]}(셋째도 보낸다, 던지지 않는다)', async () => {
    const { server, port } = three();
    server.override['PATCH /users/2'] = () => refusal(500, 'INTERNAL_ERROR');
    expect(
      await port.setActive([{ id: 1 }, { id: 2 }, { id: 3 }], true),
    ).toEqual({ done: [1, 3], failed: [2] });
    expect(server.patches().map((call) => call.body)).toEqual([
      '{"isActive":true}',
      '{"isActive":true}',
      '{"isActive":true}',
    ]);
  });

  it.each([
    ['404', () => refusal(404, 'USER_NOT_FOUND')],
    ['연결 끊김', () => Promise.reject(new TypeError('끊김'))],
    [
      '200 companyName 숫자',
      () => json(200, { ...fakeAccount(1), companyName: 1 }),
    ],
  ])('%s → 그 id 는 failed', async (_, answer) => {
    const { server, port } = three();
    server.override['PATCH /users/1'] = answer;
    expect(await port.setActive([{ id: 1 }, { id: 2 }], false)).toEqual({
      done: [2],
      failed: [1],
    });
  });
});

describe('꼴 검사 — CustomerUserOut 11칸', () => {
  it.each([
    ['createdAt 빠짐', { createdAt: undefined }],
    ['companyName 숫자', { companyName: 3 }],
    ['companyId 글자', { companyId: '1' }],
    ['branchId 글자', { branchId: 'b' }],
  ])('목록 줄의 %s → failed', async (_, broken) => {
    const { server, port } = setup();
    server.override['GET /users'] = () =>
      json(200, {
        count: 1,
        isNext: false,
        results: [{ ...fakeAccount(1), ...broken }],
      });
    expect(await port.list()).toEqual({ kind: 'failed' });
  });

  it('branchId 숫자는 된다(1차엔 null 이지만 계약은 integer|null)', async () => {
    const { server, port } = setup([fakeAccount(1, { branchId: 4 })]);
    expect((await port.list()).kind).toBe('ok');
    expect(server.calls).toHaveLength(1);
  });
});

describe('companyId 를 보내지 않는다(MARC-ENT-251)', () => {
  it('목록·전체 수·이름 고침·사용 여부 어느 요청에도 companyId 가 없다', async () => {
    const { server, port } = setup();
    await port.list({ q: 'a', status: 'active' });
    await port.total();
    await port.rename({ id: 1 }, '재무팀');
    await port.setActive([{ id: 1 }, { id: 2 }], false);
    expect(server.calls).toHaveLength(5);
    for (const call of server.calls) {
      expect(call.query).not.toContain('companyId');
      expect(call.body).not.toContain('companyId');
    }
    expect(
      server.writes().every((body) => Object.keys(body).length === 1),
    ).toBe(true);
  });
});
