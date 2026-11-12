// 세션 저장소 시험(밴드 LG1 ①, 발주서 §4 단위 ①·critic 1 반영 B2·B3·N3·N5). 가짜 서버(testing.ts)로 본다.
import { afterEach, describe, expect, it, vi } from 'vitest';

import { asFailure, companyRefusalOf } from '../../../shared/api/index.ts';
import { REFRESH_STORAGE_KEY } from '../model/index.ts';
import {
  RESTORE_TIMEOUT_MS,
  REVOKE_TIMEOUT_MS,
  createSessionStore,
} from './store.ts';
import { fakeAuthServer, memoryStorage } from './testing.ts';
import type { FakeUser } from './testing.ts';

const BASE = 'http://test.local/api';

const accounts = (): Record<string, FakeUser> => ({
  'ops.admin': { password: 'admin-pass-1', kind: 'admin' },
  user01: { password: 'service-pass-1', kind: 'service' },
  user03: { password: 'temp-pass-1', kind: 'service', isInitial: true },
});

/** 가짜 서버 + 보관소 + 저장소. signedIn 이면 그 계정의 refresh 를 보관소에 심고 복원까지 한다. */
async function setup(signedIn?: string) {
  const server = fakeAuthServer(accounts(), { baseUrl: BASE });
  const storage = memoryStorage();
  if (signedIn)
    storage.setItem(REFRESH_STORAGE_KEY, server.issue(signedIn).refresh);
  const store = createSessionStore({
    send: server.send,
    storage,
    baseUrl: BASE,
  });
  if (signedIn) await store.ready();
  return { server, storage, store };
}

const meCall = (store: Awaited<ReturnType<typeof setup>>['store']) =>
  store.api.client.GET('/users/me');

describe('부팅 복원', () => {
  it('보관소에 refresh 가 없으면 서버를 부르지 않고 안 로그인', async () => {
    const { server, store } = await setup();
    expect(store.getSnapshot()).toEqual({ status: 'restoring' });
    await store.ready();
    expect(store.getSnapshot()).toEqual({ status: 'signedOut', notice: null });
    expect(server.calls).toEqual([]);
  });

  it('저장된 refresh 로 복원: refresh 한 번 → /users/me, rotate 된 refresh 를 보관소에 쓴다', async () => {
    const { server, storage, store } = await setup('user01');
    expect(server.count('POST /auth/refresh')).toBe(1);
    expect(server.count('GET /users/me')).toBe(1);
    const snapshot = store.getSnapshot();
    expect(snapshot.status).toBe('signedIn');
    if (snapshot.status === 'signedIn')
      expect(snapshot.user).toMatchObject({
        username: 'user01',
        kind: 'service',
        isInitial: false,
      });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(
      server.liveRefreshOf('user01'),
    );
    // /users/me 에 새 access 가 실렸다
    expect(server.calls.at(-1)!.authorization).toMatch(/^Bearer access-\d+$/);
  });

  it('부팅 복원을 두 번(동시에·뒤에) 불러도 refresh 는 한 번', async () => {
    const server = fakeAuthServer(accounts(), { baseUrl: BASE });
    const storage = memoryStorage({
      [REFRESH_STORAGE_KEY]: server.issue('user01').refresh,
    });
    const store = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
    });
    await Promise.all([store.ready(), store.ready()]);
    await store.ready();
    expect(server.count('POST /auth/refresh')).toBe(1);
    expect(store.getSnapshot().status).toBe('signedIn');
  });

  it('refresh 가 444(죽은 refresh)면 세션 비움 + 만료 안내', async () => {
    const server = fakeAuthServer(accounts(), { baseUrl: BASE });
    const storage = memoryStorage({ [REFRESH_STORAGE_KEY]: 'refresh-dead' });
    const store = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
    });
    await store.ready();
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'expired',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
    expect(server.count('GET /users/me')).toBe(0);
  });

  it('[N5] 복원 중 /users/me 401 USER_UNAVAILABLE → 세션 비움, 로그인 화면으로', async () => {
    const server = fakeAuthServer(
      {
        ...accounts(),
        gone: { password: 'x', kind: 'service', unavailable: true },
      },
      { baseUrl: BASE },
    );
    const storage = memoryStorage({
      [REFRESH_STORAGE_KEY]: server.issue('gone').refresh,
    });
    const store = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
    });
    await store.ready();
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'expired',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });
});

describe('444 → refresh 한 번', () => {
  it('access 가 만료(444)면 refresh 한 번, 원 요청을 새 access 로 한 번 다시 보낸다(B3: 머리를 바꿔 단다)', async () => {
    const { server, store } = await setup('user01');
    const before = server.calls.length;
    const oldBearer = server.calls.at(-1)!.authorization;
    server.expireAccess();
    const { data } = await meCall(store);
    expect(data?.username).toBe('user01');
    const after = server.calls.slice(before);
    expect(after.map((call) => `${call.method} ${call.path}`)).toEqual([
      'GET /users/me',
      'POST /auth/refresh',
      'GET /users/me',
    ]);
    expect(after[0]!.authorization).toBe(oldBearer);
    // 다시 보낸 요청의 Bearer 는 refresh 가 낸 새 access 다(옛 머리 그대로가 아니다).
    expect(after[2]!.authorization).not.toBe(oldBearer);
    expect(after[2]!.authorization).toBe(
      `Bearer ${server.lastIssued()!.access}`,
    );
  });

  it('동시 요청 셋이 다 444 여도 refresh 는 한 번, 원 요청은 저마다 한 번씩 다시', async () => {
    const { server, store } = await setup('user01');
    server.expireAccess();
    const before = server.calls.length;
    const release = server.holdRefresh();
    const three = Promise.all([meCall(store), meCall(store), meCall(store)]);
    // 셋 다 첫 답(444)을 받고 refresh 를 기다리는 사이에 refresh 를 푼다.
    await new Promise((resolve) => setTimeout(resolve, 20));
    release();
    const answers = await three;
    expect(answers.every(({ data }) => data?.username === 'user01')).toBe(true);
    const after = server.calls.slice(before);
    expect(after.filter((call) => call.path === '/auth/refresh')).toHaveLength(
      1,
    );
    expect(after.filter((call) => call.path === '/users/me')).toHaveLength(6);
    expect(store.getSnapshot().status).toBe('signedIn');
  });

  it('refresh 가 끝난 뒤 늦게 온 444 는 refresh 하지 않고 이미 받은 새 access 로 다시 보낸다', async () => {
    const { server, store } = await setup('user01');
    server.expireAccess();
    // 첫 요청의 답(444)만 붙든다: 그 사이 둘째 요청이 444 → refresh → 다시 보내기를 끝낸다.
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.override['GET /users/me'] = async () => {
      delete server.override['GET /users/me'];
      await gate;
      return new Response(
        JSON.stringify({
          error: {
            code: 'TOKEN_NOT_VALID',
            message: 'x',
            fields: null,
            legacyCode: 'token_not_valid',
          },
        }),
        { status: 444, headers: { 'Content-Type': 'application/json' } },
      );
    };
    const late = meCall(store);
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect((await meCall(store)).data?.username).toBe('user01');
    expect(server.count('POST /auth/refresh')).toBe(2); // 복원 한 번 + 둘째 요청의 한 번
    release();
    expect((await late).data?.username).toBe('user01');
    expect(server.count('POST /auth/refresh')).toBe(2);
    expect(server.calls.at(-1)!.authorization).toBe(
      `Bearer ${server.lastIssued()!.access}`,
    );
  });

  it('세션을 비운 뒤 늦게 온 444 는 refresh 하지 않고 안내(잠김)를 「만료」로 덮지 않는다', async () => {
    const { server, store } = await setup('user01');
    server.expireAccess();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.override['GET /users/me'] = async () => {
      await gate;
      return new Response(
        JSON.stringify({
          error: {
            code: 'TOKEN_NOT_VALID',
            message: 'x',
            fields: null,
            legacyCode: 'token_not_valid',
          },
        }),
        { status: 444, headers: { 'Content-Type': 'application/json' } },
      );
    };
    const late = meCall(store);
    await new Promise((resolve) => setTimeout(resolve, 10));
    await store.end('locked');
    release();
    await expect(late).rejects.toMatchObject({ status: 444 });
    expect(server.count('POST /auth/refresh')).toBe(1); // 복원 때 한 번뿐
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'locked',
    });
  });

  it('[N3] rotate 된 refresh 는 약속이 풀리기 전에 보관소에 든다 — 풀린 뒤 첫 요청이 나갈 때 이미 새 refresh', async () => {
    // 같은 보관소를 쓰는 새 저장소(새로고침 꼴)로 복원한다.
    const { server, storage } = await setup('user01');
    const old = storage.getItem(REFRESH_STORAGE_KEY);
    const seen: (string | null)[] = [];
    const send = server.send;
    let refreshed = false;
    const spy = createSessionStore({
      send: async (request) => {
        if (refreshed && new URL(request.url).pathname.endsWith('/users/me'))
          seen.push(storage.getItem(REFRESH_STORAGE_KEY));
        const response = await send(request);
        if (new URL(request.url).pathname.endsWith('/auth/refresh'))
          refreshed = true;
        return response;
      },
      storage,
      baseUrl: BASE,
    });
    await spy.ready();
    expect(seen).toHaveLength(1);
    expect(seen[0]).not.toBe(old);
    expect(seen[0]).toBe(server.liveRefreshOf('user01'));
  });

  it('[N3] 부팅 복원과 444 의 refresh 는 약속 하나를 같이 쓴다(동시에 와도 refresh 한 번)', async () => {
    const { server, storage, store } = await setup();
    // 로그인으로 access·refresh 를 받은 뒤(복원은 아직 안 불렀다), access 를 죽이고 복원과 444 를 같이 낸다.
    await store.login('user01', 'service-pass-1');
    expect(storage.getItem(REFRESH_STORAGE_KEY)).not.toBeNull();
    server.expireAccess();
    const before = server.count('POST /auth/refresh');
    const release = server.holdRefresh();
    const both = Promise.all([store.ready(), meCall(store)]);
    await new Promise((resolve) => setTimeout(resolve, 20));
    release();
    const [, me] = await both;
    expect(me.data?.username).toBe('user01');
    expect(server.count('POST /auth/refresh') - before).toBe(1);
    expect(store.getSnapshot().status).toBe('signedIn');
  });

  it('refresh 도 444 면 세션 비움 + 만료 안내, 원 요청은 실패(444)', async () => {
    const { server, storage, store } = await setup('user01');
    server.expireAccess();
    server.override['POST /auth/refresh'] = () =>
      new Response(
        JSON.stringify({
          error: {
            code: 'TOKEN_NOT_VALID',
            message: 'x',
            fields: null,
            legacyCode: 'token_not_valid',
          },
        }),
        { status: 444, headers: { 'Content-Type': 'application/json' } },
      );
    await expect(meCall(store)).rejects.toMatchObject({
      kind: 'api',
      status: 444,
    });
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'expired',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('401·403 은 refresh 하지 않는다', async () => {
    const { server, store } = await setup('user01');
    server.override['GET /users/me'] = () =>
      new Response(
        JSON.stringify({
          error: {
            code: 'USER_UNAVAILABLE',
            message: 'x',
            fields: null,
            legacyCode: 'user_unavailable',
          },
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      );
    await expect(meCall(store)).rejects.toMatchObject({ status: 401 });
    server.override['GET /users/me'] = () =>
      new Response(
        JSON.stringify({
          error: {
            code: 'FORBIDDEN',
            message: 'x',
            fields: null,
            legacyCode: 'forbidden',
          },
        }),
        { status: 403, headers: { 'Content-Type': 'application/json' } },
      );
    await expect(meCall(store)).rejects.toMatchObject({ status: 403 });
    expect(server.count('POST /auth/refresh')).toBe(1); // 복원 때 한 번뿐
    expect(store.getSnapshot().status).toBe('signedIn');
  });

  it('[B3] /auth/* 는 가로채지 않는다: 로그인 실패 401·refresh 444 에 refresh 를 다시 내지 않는다', async () => {
    const { server, store } = await setup();
    await store.ready();
    expect(await store.login('user01', 'wrong-pass')).toEqual({
      ok: false,
      reason: 'invalid',
    });
    expect(server.count('POST /auth/refresh')).toBe(0);
    expect(server.calls[0]!.authorization).toBeNull();
  });

  it('[N5] 다른 요청의 403 PASSWORD_CHANGE_REQUIRED → 사용자를 isInitial 로 표시', async () => {
    const { server, store } = await setup('user01');
    server.users.user01!.isInitial = true;
    await expect(store.api.client.GET('/users')).rejects.toMatchObject({
      status: 403,
      code: 'PASSWORD_CHANGE_REQUIRED',
    });
    const snapshot = store.getSnapshot();
    expect(snapshot.status === 'signedIn' && snapshot.user.isInitial).toBe(
      true,
    );
  });

  it('회사 거절 셋(COMPANY_AMBIGUOUS·COMPANY_INACTIVE·COMPANY_NOT_FOUND)에 세션을 비우지도, refresh 하지도, isInitial 로 바꾸지도 않는다(sid:MARC-ENT-374)', async () => {
    const { server, storage, store } = await setup('ops.admin');
    const refresh = storage.getItem(REFRESH_STORAGE_KEY);
    for (const [status, code, refusal] of [
      [400, 'COMPANY_AMBIGUOUS', 'ambiguous'],
      [403, 'COMPANY_INACTIVE', 'inactive'],
      [400, 'COMPANY_NOT_FOUND', 'not_found'],
    ] as const) {
      server.override['GET /greenwash/checks'] = () =>
        new Response(
          JSON.stringify({
            error: {
              code,
              message: 'x',
              fields: null,
              legacyCode: code.toLowerCase(),
            },
          }),
          { status, headers: { 'Content-Type': 'application/json' } },
        );
      const error: unknown = await store.api.client
        .GET('/greenwash/checks')
        .then(
          () => null,
          (thrown: unknown) => thrown,
        );
      expect(error, code).toMatchObject({ kind: 'api', status, code });
      expect(companyRefusalOf(asFailure(error)), code).toBe(refusal);
      const snapshot = store.getSnapshot();
      expect(snapshot.status, code).toBe('signedIn');
      expect(snapshot.status === 'signedIn' && snapshot.user.kind, code).toBe(
        'admin',
      );
      expect(
        snapshot.status === 'signedIn' && snapshot.user.isInitial,
        code,
      ).toBe(false);
    }
    expect(server.count('POST /auth/refresh')).toBe(1); // 복원 때 한 번뿐
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(refresh);
  });
});

describe('로그인', () => {
  it('운영 관리자: 토큰 짝 저장(access 메모리·refresh 보관소) → /users/me → signedIn, companySubdomain 은 보내지 않는다', async () => {
    const { server, storage, store } = await setup();
    await store.ready();
    expect(await store.login('ops.admin', 'admin-pass-1')).toEqual({
      ok: true,
    });
    expect(JSON.parse(server.calls[0]!.body)).toEqual({
      username: 'ops.admin',
      password: 'admin-pass-1',
    });
    const snapshot = store.getSnapshot();
    expect(snapshot.status === 'signedIn' && snapshot.user.kind).toBe('admin');
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(
      server.liveRefreshOf('ops.admin'),
    );
    // access 는 보관소에 없다(키는 refresh 하나)
    expect([...storage.items.keys()]).toEqual([REFRESH_STORAGE_KEY]);
    expect(store.hasTemporaryPassword()).toBe(false);
  });

  it('틀린 비번·꼴 틀림(422) → invalid, 잠김 → locked, 5xx·연결 끊김 → failed', async () => {
    const { server, store } = await setup();
    await store.ready();
    expect(await store.login('user01', 'nope')).toEqual({
      ok: false,
      reason: 'invalid',
    });
    expect(await store.login('no such user!', 'x')).toEqual({
      ok: false,
      reason: 'invalid',
    });
    server.users.user01!.locked = true;
    expect(await store.login('user01', 'service-pass-1')).toEqual({
      ok: false,
      reason: 'locked',
    });
    server.override['POST /auth/login'] = () =>
      new Response('Internal Server Error', { status: 500 });
    expect(await store.login('user01', 'service-pass-1')).toEqual({
      ok: false,
      reason: 'failed',
    });
    server.override['POST /auth/login'] = () => {
      throw new TypeError('fetch failed');
    };
    expect(await store.login('user01', 'service-pass-1')).toEqual({
      ok: false,
      reason: 'failed',
    });
    expect(store.getSnapshot()).toEqual({ status: 'signedOut', notice: null });
  });

  it('[N4] 임시 비밀번호는 isInitial 일 때만 메모리에, 스냅샷에는 싣지 않는다', async () => {
    const { store } = await setup();
    await store.ready();
    await store.login('user03', 'temp-pass-1');
    expect(store.hasTemporaryPassword()).toBe(true);
    expect(JSON.stringify(store.getSnapshot())).not.toContain('temp-pass-1');
  });
});

describe('비밀번호 바꾸기', () => {
  async function initial() {
    const context = await setup();
    await context.store.ready();
    await context.store.login('user03', 'temp-pass-1');
    return context;
  }

  it('성공: 임시 비밀번호를 currentPassword 로 보내고, 새 짝 저장 → isInitial 거짓, 임시 비밀번호를 지운다', async () => {
    const { server, storage, store } = await initial();
    expect(await store.changePassword('green-paper-1')).toEqual({ ok: true });
    const call = server.calls.find((row) => row.path === '/users/me/password')!;
    expect(JSON.parse(call.body)).toEqual({
      currentPassword: 'temp-pass-1',
      newPassword: 'green-paper-1',
    });
    expect(store.hasTemporaryPassword()).toBe(false);
    const snapshot = store.getSnapshot();
    expect(snapshot.status === 'signedIn' && snapshot.user.isInitial).toBe(
      false,
    );
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(
      server.liveRefreshOf('user03'),
    );
  });

  it('400 PASSWORD_REJECTED → rejected, 세션은 그대로', async () => {
    const { store } = await initial();
    expect(await store.changePassword('short')).toEqual({
      ok: false,
      reason: 'rejected',
    });
    expect(store.getSnapshot().status).toBe('signedIn');
    expect(store.hasTemporaryPassword()).toBe(true);
  });

  it('[B2] 400 CURRENT_PASSWORD_MISMATCH → revoke 결과와 무관하게 메모리·보관소 비움 + 처음부터 다시 로그인 안내', async () => {
    const { server, storage, store } = await initial();
    server.users.user03!.password = 'reset-again';
    server.override['POST /auth/revoke'] = () => {
      throw new TypeError('fetch failed');
    };
    expect(await store.changePassword('green-paper-1')).toEqual({
      ok: false,
      reason: 'ended',
    });
    expect(server.count('POST /auth/revoke')).toBe(1);
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'relogin',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
    expect(store.hasTemporaryPassword()).toBe(false);
  });

  it('[N5] 401 ACCOUNT_LOCKED → 세션 비움 + 잠김 안내', async () => {
    const { server, store } = await initial();
    server.users.user03!.locked = true;
    expect(await store.changePassword('green-paper-1')).toEqual({
      ok: false,
      reason: 'ended',
    });
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'locked',
    });
  });

  it('[B2] 임시 비밀번호가 메모리에 없으면(새로고침) revoke → 세션 비움 + 처음부터 다시 로그인 안내', async () => {
    const { server, storage, store } = await setup('user03');
    expect(store.hasTemporaryPassword()).toBe(false);
    expect(await store.changePassword('green-paper-1')).toEqual({
      ok: false,
      reason: 'ended',
    });
    expect(server.count('POST /users/me/password')).toBe(0);
    expect(server.count('POST /auth/revoke')).toBe(1);
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'relogin',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('연결 끊김 → failed, 세션·임시 비밀번호는 그대로', async () => {
    const { server, store } = await initial();
    server.override['POST /users/me/password'] = () => {
      throw new TypeError('fetch failed');
    };
    expect(await store.changePassword('green-paper-1')).toEqual({
      ok: false,
      reason: 'failed',
    });
    expect(store.hasTemporaryPassword()).toBe(true);
  });
});

describe('로그아웃', () => {
  it('revoke(보관소의 refresh) → 메모리·보관소 비움, 그 뒤 요청에는 Bearer 가 없다', async () => {
    const { server, storage, store } = await setup('user01');
    const refresh = storage.getItem(REFRESH_STORAGE_KEY);
    await store.logout();
    const revoke = server.calls.find((row) => row.path === '/auth/revoke')!;
    expect(JSON.parse(revoke.body)).toEqual({ refresh });
    expect(store.getSnapshot()).toEqual({ status: 'signedOut', notice: null });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
    expect(storage.items.size).toBe(0);
    await expect(meCall(store)).rejects.toMatchObject({ status: 401 });
    expect(server.calls.at(-1)!.authorization).toBeNull();
  });

  it('[B2] revoke 가 실패(연결 끊김·444)해도 비운다', async () => {
    const { server, storage, store } = await setup('user01');
    server.override['POST /auth/revoke'] = () => {
      throw new TypeError('fetch failed');
    };
    await store.logout();
    expect(store.getSnapshot()).toEqual({ status: 'signedOut', notice: null });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('revoke 가 답하지 않으면 상한(revokeTimeoutMs)이 지나 결과를 기다리지 않고 비운다', async () => {
    const server = fakeAuthServer(accounts(), { baseUrl: BASE });
    const storage = memoryStorage({
      [REFRESH_STORAGE_KEY]: server.issue('user01').refresh,
    });
    const store = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
      revokeTimeoutMs: 30,
    });
    await store.ready();
    server.override['POST /auth/revoke'] = () => new Promise(() => {});
    const started = Date.now();
    await store.logout();
    expect(Date.now() - started).toBeLessThan(2_000);
    expect(server.count('POST /auth/revoke')).toBe(1);
    expect(store.getSnapshot()).toEqual({ status: 'signedOut', notice: null });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('revoke 상한의 기본은 5초', () => {
    expect(REVOKE_TIMEOUT_MS).toBe(5_000);
  });

  it('안내는 dismissNotice 로 내린다', async () => {
    const { store } = await setup('user03');
    await store.end('relogin');
    store.dismissNotice();
    expect(store.getSnapshot()).toEqual({ status: 'signedOut', notice: null });
  });

  it('보관소가 던져도(사생활 창) 저장소는 죽지 않는다 — 안 로그인으로 시작', async () => {
    const server = fakeAuthServer(accounts(), { baseUrl: BASE });
    const broken = {
      getItem: () => {
        throw new Error('막힘');
      },
      setItem: () => {
        throw new Error('막힘');
      },
      removeItem: () => {
        throw new Error('막힘');
      },
    };
    const store = createSessionStore({
      send: server.send,
      storage: broken,
      baseUrl: BASE,
    });
    await store.ready();
    expect(store.getSnapshot()).toEqual({ status: 'signedOut', notice: null });
    expect(await store.login('user01', 'service-pass-1')).toEqual({ ok: true });
  });
});

const tokenRefusal = (status: number, code: string) => () =>
  new Response(
    JSON.stringify({
      error: {
        code,
        message: 'x',
        fields: null,
        legacyCode: code.toLowerCase(),
      },
    }),
    { status, headers: { 'Content-Type': 'application/json' } },
  );
const unreachable = () => {
  throw new TypeError('fetch failed');
};

describe('가지 리뷰 지적(경계 ④)', () => {
  afterEach(() => void vi.useRealTimers());

  it('[1] refresh 가 연결 끊김이면 세션을 비우지 않고 보관소의 refresh 를 둔 채 원 444 를 돌려준다 — 다음 요청이 다시 refresh', async () => {
    const { server, storage, store } = await setup('user01');
    const kept = storage.getItem(REFRESH_STORAGE_KEY);
    server.expireAccess();
    server.override['POST /auth/refresh'] = unreachable;
    await expect(meCall(store)).rejects.toMatchObject({ status: 444 });
    expect(store.getSnapshot().status).toBe('signedIn');
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(kept);
    // 다시 닿으면 다음 요청이 refresh 해 산다
    delete server.override['POST /auth/refresh'];
    const { data } = await meCall(store);
    expect(data?.username).toBe('user01');
    expect(server.count('POST /auth/refresh')).toBe(3); // 복원 + 끊김 + 다시
  });

  it('[1] refresh 가 5xx·꼴 밖의 답이어도 비우지 않는다, 444 만 비운다', async () => {
    const { server, storage, store } = await setup('user01');
    server.expireAccess();
    server.override['POST /auth/refresh'] = () =>
      new Response('Bad Gateway', { status: 502 });
    await expect(meCall(store)).rejects.toMatchObject({ status: 444 });
    server.override['POST /auth/refresh'] = tokenRefusal(500, 'INTERNAL');
    await expect(meCall(store)).rejects.toMatchObject({ status: 444 });
    expect(store.getSnapshot().status).toBe('signedIn');
    expect(storage.getItem(REFRESH_STORAGE_KEY)).not.toBeNull();
    server.override['POST /auth/refresh'] = tokenRefusal(
      444,
      'TOKEN_NOT_VALID',
    );
    await expect(meCall(store)).rejects.toMatchObject({ status: 444 });
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'expired',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('[1] 부팅 복원의 refresh·/users/me 가 닿지 못하면 안 로그인이되 보관소의 refresh 는 남긴다', async () => {
    const server = fakeAuthServer(accounts(), { baseUrl: BASE });
    const refresh = server.issue('user01').refresh;
    const storage = memoryStorage({ [REFRESH_STORAGE_KEY]: refresh });
    server.override['POST /auth/refresh'] = unreachable;
    const first = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
    });
    await first.ready();
    expect(first.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'unreachable',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(refresh);
    // refresh 는 되고 /users/me 가 끊김
    delete server.override['POST /auth/refresh'];
    server.override['GET /users/me'] = unreachable;
    const second = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
    });
    await second.ready();
    expect(second.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'unreachable',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(
      server.liveRefreshOf('user01'),
    );
    // 다시 닿으면 다음 복원이 산다
    delete server.override['GET /users/me'];
    const third = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
    });
    await third.ready();
    expect(third.getSnapshot().status).toBe('signedIn');
  });

  it('[2] 부팅 복원은 상한(10초)이 지나면 안 로그인으로, 보관소의 refresh 는 남긴다(가짜 시계)', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    expect(RESTORE_TIMEOUT_MS).toBe(10_000);
    const server = fakeAuthServer(accounts(), { baseUrl: BASE });
    const refresh = server.issue('user01').refresh;
    const storage = memoryStorage({ [REFRESH_STORAGE_KEY]: refresh });
    server.override['POST /auth/refresh'] = () => new Promise(() => {});
    const store = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
    });
    let done = false;
    void store.ready().then(() => (done = true));
    await vi.advanceTimersByTimeAsync(RESTORE_TIMEOUT_MS - 1);
    expect(done).toBe(false);
    expect(store.getSnapshot()).toEqual({ status: 'restoring' });
    await vi.advanceTimersByTimeAsync(1);
    expect(done).toBe(true);
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'unreachable',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(refresh);
  });

  it('[2] 상한 뒤 늦게 온 복원 결과는 세션을 되살리지 않는다', async () => {
    const server = fakeAuthServer(accounts(), { baseUrl: BASE });
    const storage = memoryStorage({
      [REFRESH_STORAGE_KEY]: server.issue('user01').refresh,
    });
    const release = server.holdRefresh();
    const store = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
      restoreTimeoutMs: 20,
    });
    await store.ready();
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'unreachable',
    });
    release();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'unreachable',
    });
    expect(server.count('GET /users/me')).toBe(0);
  });

  it('[4] 로그아웃·다시 로그인 뒤에는 옛 refresh 약속의 결과를 받지 않고 새로 refresh 한다', async () => {
    const { server, store } = await setup();
    await store.ready();
    await store.login('user01', 'service-pass-1');
    server.expireAccess();
    const release = server.holdRefresh();
    const old = meCall(store).catch((error: unknown) => error);
    await new Promise((resolve) => setTimeout(resolve, 10));
    await store.logout();
    await store.login('user01', 'service-pass-1');
    server.expireAccess();
    const fresh = meCall(store);
    await new Promise((resolve) => setTimeout(resolve, 10));
    release();
    expect((await fresh).data?.username).toBe('user01');
    expect(await old).toMatchObject({ status: 444 });
    expect(store.getSnapshot().status).toBe('signedIn');
    expect(server.count('POST /auth/refresh')).toBe(2);
  });

  it('[6] 다시 보낸 응답의 403 PASSWORD_CHANGE_REQUIRED 도 isInitial 로 표시', async () => {
    const { server, store } = await setup('user01');
    server.users.user01!.isInitial = true;
    server.expireAccess();
    await expect(store.api.client.GET('/users')).rejects.toMatchObject({
      status: 403,
      code: 'PASSWORD_CHANGE_REQUIRED',
    });
    expect(server.count('POST /auth/refresh')).toBe(2);
    const snapshot = store.getSnapshot();
    expect(snapshot.status === 'signedIn' && snapshot.user.isInitial).toBe(
      true,
    );
  });

  it('[7] 비밀번호 바꾸기의 422 VALIDATION_ERROR → rejected', async () => {
    const { server, store } = await setup();
    await store.ready();
    await store.login('user03', 'temp-pass-1');
    server.override['POST /users/me/password'] = tokenRefusal(
      422,
      'VALIDATION_ERROR',
    );
    expect(await store.changePassword('green-paper-1')).toEqual({
      ok: false,
      reason: 'rejected',
    });
    expect(store.getSnapshot().status).toBe('signedIn');
  });
});

describe('부팅 복원이 서버에 닿지 못함 → unreachable 안내 · [다시 시도](밴드 SN1)', () => {
  afterEach(() => void vi.useRealTimers());

  /** user01 의 refresh 를 심은 보관소와 저장소(아직 ready 전). */
  const boot = (options: { restoreTimeoutMs?: number } = {}) => {
    const server = fakeAuthServer(accounts(), { baseUrl: BASE });
    const refresh = server.issue('user01').refresh;
    const storage = memoryStorage({ [REFRESH_STORAGE_KEY]: refresh });
    const store = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
      ...options,
    });
    return { server, storage, store, refresh };
  };
  const unreachableNotice = { status: 'signedOut', notice: 'unreachable' };

  it('[T1] 부팅 refresh 503 → signedOut + unreachable, 보관소의 refresh 는 남는다', async () => {
    const { server, storage, store, refresh } = boot();
    server.override['POST /auth/refresh'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    expect(store.getSnapshot()).toEqual(unreachableNotice);
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(refresh);
    expect(server.count('GET /users/me')).toBe(0);
  });

  it('[T2] 부팅 복원이 상한을 넘기면 unreachable(가짜 시계)', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const { server, storage, store, refresh } = boot();
    server.override['POST /auth/refresh'] = () => new Promise(() => {});
    let done = false;
    void store.ready().then(() => (done = true));
    await vi.advanceTimersByTimeAsync(RESTORE_TIMEOUT_MS - 1);
    expect(store.getSnapshot()).toEqual({ status: 'restoring' });
    await vi.advanceTimersByTimeAsync(1);
    expect(done).toBe(true);
    expect(store.getSnapshot()).toEqual(unreachableNotice);
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(refresh);
  });

  it('[T3] refresh 는 되고 /users/me 가 503 → unreachable, rotate 된 refresh 가 남는다', async () => {
    const { server, storage, store } = boot();
    server.override['GET /users/me'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    expect(store.getSnapshot()).toEqual(unreachableNotice);
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(
      server.liveRefreshOf('user01'),
    );
  });

  it('[T4] 거절(refresh 444 · /users/me 401 USER_UNAVAILABLE)은 지금 안내 그대로 — unreachable 아님', async () => {
    const dead = boot();
    dead.server.override['POST /auth/refresh'] = tokenRefusal(
      444,
      'TOKEN_NOT_VALID',
    );
    await dead.store.ready();
    expect(dead.store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'expired',
    });
    expect(dead.storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();

    const gone = boot();
    gone.server.override['GET /users/me'] = tokenRefusal(
      401,
      'USER_UNAVAILABLE',
    );
    await gone.store.ready();
    expect(gone.store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'expired',
    });
    expect(gone.storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('[T5] 다시 시도: 닿으면 signedIn, 그동안 상태는 restoring 으로 돌아가지 않는다', async () => {
    const { server, store } = boot();
    server.override['POST /auth/refresh'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    delete server.override['POST /auth/refresh'];
    const seen: string[] = [];
    store.subscribe(() => seen.push(store.getSnapshot().status));
    await store.retryRestore();
    expect(store.getSnapshot().status).toBe('signedIn');
    expect(seen).not.toContain('restoring');
    expect(server.count('POST /auth/refresh')).toBe(2);
  });

  it('[T5] 다시 시도가 또 503·상한이면 unreachable 그대로, refresh 남음', async () => {
    const { server, storage, store, refresh } = boot({ restoreTimeoutMs: 20 });
    server.override['POST /auth/refresh'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    await store.retryRestore();
    expect(store.getSnapshot()).toEqual(unreachableNotice);
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(refresh);
    // 상한을 넘겨도 같은 꼴
    server.override['POST /auth/refresh'] = () => new Promise(() => {});
    await store.retryRestore();
    expect(store.getSnapshot()).toEqual(unreachableNotice);
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(refresh);
  });

  it('[T5] 다시 시도에 444 → 만료 안내 + refresh 지움, /users/me 401 USER_UNAVAILABLE 도 같다', async () => {
    const { server, storage, store } = boot();
    server.override['POST /auth/refresh'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    server.override['POST /auth/refresh'] = tokenRefusal(
      444,
      'TOKEN_NOT_VALID',
    );
    await store.retryRestore();
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'expired',
    });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();

    const gone = boot();
    gone.server.override['GET /users/me'] = tokenRefusal(503, 'UNAVAILABLE');
    await gone.store.ready();
    gone.server.override['GET /users/me'] = tokenRefusal(
      401,
      'USER_UNAVAILABLE',
    );
    await gone.store.retryRestore();
    expect(gone.store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'expired',
    });
    expect(gone.storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('[T5] 보관소에 refresh 가 없으면 서버를 부르지 않고 안내를 내린다', async () => {
    const { server, storage, store } = boot();
    server.override['POST /auth/refresh'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    storage.removeItem(REFRESH_STORAGE_KEY);
    await store.retryRestore();
    expect(store.getSnapshot()).toEqual({ status: 'signedOut', notice: null });
    expect(server.count('POST /auth/refresh')).toBe(1);
  });

  it('[T5] 두 번 눌러도 refresh 는 한 번(진행 중인 약속을 같이 쓴다)', async () => {
    const { server, store } = boot();
    server.override['POST /auth/refresh'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    delete server.override['POST /auth/refresh'];
    await Promise.all([store.retryRestore(), store.retryRestore()]);
    expect(store.getSnapshot().status).toBe('signedIn');
    expect(server.count('POST /auth/refresh')).toBe(2);
    expect(server.count('GET /users/me')).toBe(1);
  });

  it('[T5] 늦게 온 다시 시도의 결과는 그사이 이긴 로그인을 덮지 않는다', async () => {
    const { server, storage, store } = boot();
    server.override['POST /auth/refresh'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    delete server.override['POST /auth/refresh'];
    const release = server.holdRefresh();
    const retried = store.retryRestore();
    expect(await store.login('ops.admin', 'admin-pass-1')).toEqual({
      ok: true,
    });
    const loggedIn = storage.getItem(REFRESH_STORAGE_KEY);
    release();
    await retried;
    const snapshot = store.getSnapshot();
    expect(snapshot.status === 'signedIn' && snapshot.user.username).toBe(
      'ops.admin',
    );
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBe(loggedIn);
    expect(server.count('GET /users/me')).toBe(1);
  });

  it('[T5] 다시 시도가 붙든 사이 로그인하면, 로그인 직후 요청은 새 access 로 바로 가고 옛 refresh 약속을 같이 쓰지 않는다', async () => {
    const { server, store } = boot();
    server.override['POST /auth/refresh'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    delete server.override['POST /auth/refresh'];
    const release = server.holdRefresh();
    const retried = store.retryRestore();
    await store.login('ops.admin', 'admin-pass-1');
    const loginAccess = server.lastIssued()!.access;
    // refresh 를 풀지 않은 채로: 첫 요청이 새 access 로 끝난다(옛 약속을 기다리지 않음)
    const { data } = await meCall(store);
    expect(data?.username).toBe('ops.admin');
    expect(server.calls.at(-1)?.authorization).toBe(`Bearer ${loginAccess}`);
    // 444 가 와도 옛 약속(user01 의 refresh)을 같이 쓰지 않고 새로 refresh 한다
    server.expireAccess();
    const again = meCall(store);
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(server.count('POST /auth/refresh')).toBe(3); // 부팅 503 + 다시 시도(붙듦) + 로그인 뒤 새 refresh
    release();
    expect((await again).data?.username).toBe('ops.admin');
    await retried;
    const snapshot = store.getSnapshot();
    expect(snapshot.status === 'signedIn' && snapshot.user.username).toBe(
      'ops.admin',
    );
  });

  it('[T5] 다시 시도가 붙든 사이 세대가 넘어가면(로그인 → 세션 끝냄) 옛 상한 타이머가 그 안내를 unreachable 로 덮지 않는다', async () => {
    const { server, store } = boot({ restoreTimeoutMs: 20 });
    server.override['POST /auth/refresh'] = tokenRefusal(503, 'UNAVAILABLE');
    await store.ready();
    delete server.override['POST /auth/refresh'];
    const release = server.holdRefresh();
    const retried = store.retryRestore();
    await store.login('ops.admin', 'admin-pass-1');
    await store.end('relogin');
    await new Promise((resolve) => setTimeout(resolve, 40));
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'relogin',
    });
    release();
    await retried;
    expect(store.getSnapshot()).toEqual({
      status: 'signedOut',
      notice: 'relogin',
    });
  });

  it('[T5] 로그인한 뒤에는 다시 시도가 아무것도 하지 않는다', async () => {
    const { server, store } = boot();
    await store.ready();
    await store.retryRestore();
    expect(store.getSnapshot().status).toBe('signedIn');
    expect(server.count('POST /auth/refresh')).toBe(1);
  });
});
