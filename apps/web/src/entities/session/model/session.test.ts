// 첫 화면·가드의 순수 함수(밴드 LG1, 발주서 §4 단위 ②·가드 표).
import { describe, expect, it } from 'vitest';

import { SESSION_PATHS, areaOf, guardOf, landingOf } from './session.ts';
import type { SessionState, SessionUser } from './session.ts';

const user = (overrides: Partial<SessionUser>): SessionUser => ({
  id: 1,
  username: 'u',
  name: '지어낸-사람',
  kind: 'service',
  companyId: 1,
  isInitial: false,
  ...overrides,
});
const signedIn = (overrides: Partial<SessionUser>): SessionState => ({
  status: 'signedIn',
  user: user(overrides),
});
const signedOut: SessionState = { status: 'signedOut', notice: null };
const restoring: SessionState = { status: 'restoring' };
const admin = signedIn({ kind: 'admin', companyId: null });
const service = signedIn({});
const initial = signedIn({ isInitial: true });
const withTemp = { temporaryPassword: true };
const noTemp = { temporaryPassword: false };
const to = (path: string) => ({ kind: 'redirect', to: path });
const stay = { kind: 'stay' };

describe('areaOf', () => {
  it.each([
    ['/login', 'login'],
    ['/password', 'password'],
    ['/admin/accounts', 'admin'],
    ['/admin', 'admin'],
    ['/greenwash', 'greenwash'],
    ['/greenwash/runs/run-1/review', 'greenwash'],
    ['/', 'other'],
    ['/zzz', 'other'],
    ['/greenwashx', 'other'],
    ['/login/x', 'other'],
    ['/administrator', 'other'],
  ])('%s → %s', (path, area) => expect(areaOf(path)).toBe(area));
});

describe('landingOf — 역할·isInitial → 첫 화면', () => {
  it('복원 중 null · 안 로그인 /login · isInitial /password · admin /admin/accounts · service /greenwash', () => {
    expect(landingOf(restoring)).toBeNull();
    expect(landingOf(signedOut)).toBe('/login');
    expect(landingOf(initial)).toBe('/password');
    expect(landingOf(signedIn({ kind: 'admin', isInitial: true }))).toBe(
      '/password',
    );
    expect(landingOf(admin)).toBe(SESSION_PATHS.adminHome);
    expect(landingOf(service)).toBe(SESSION_PATHS.serviceHome);
  });
});

describe('guardOf — 가드 표', () => {
  it('복원 중: 어디든 기다림', () => {
    for (const path of [
      '/greenwash',
      '/admin/accounts',
      '/login',
      '/password',
      '/',
    ])
      expect(guardOf(restoring, path, noTemp)).toEqual({ kind: 'wait' });
  });

  it('안 로그인: 업무 주소·/password·/ → /login, /login 은 그대로', () => {
    expect(guardOf(signedOut, '/greenwash/new', noTemp)).toEqual(to('/login'));
    expect(guardOf(signedOut, '/admin/accounts', noTemp)).toEqual(to('/login'));
    expect(guardOf(signedOut, '/password', noTemp)).toEqual(to('/login'));
    expect(guardOf(signedOut, '/', noTemp)).toEqual(to('/login'));
    expect(guardOf(signedOut, '/login', noTemp)).toEqual(stay);
  });

  it('isInitial(임시 비밀번호 있음): 업무 주소·/login → /password, /password 는 그대로', () => {
    expect(guardOf(initial, '/greenwash', withTemp)).toEqual(to('/password'));
    expect(guardOf(initial, '/admin/accounts', withTemp)).toEqual(
      to('/password'),
    );
    expect(guardOf(initial, '/login', withTemp)).toEqual(to('/password'));
    expect(guardOf(initial, '/zzz', withTemp)).toEqual(to('/password'));
    expect(guardOf(initial, '/password', withTemp)).toEqual(stay);
  });

  it('[B2] isInitial 인데 임시 비밀번호가 메모리에 없음: 어디서든 relogin', () => {
    for (const path of ['/password', '/greenwash', '/login'])
      expect(guardOf(initial, path, noTemp)).toEqual({ kind: 'relogin' });
  });

  // 밴드 SV1(sid:MARC-ENT-286): 운영 관리자도 /greenwash/** 를 연다 — 앞 단언 「/greenwash/** → /admin/accounts」를 stay 로(발주서 §2 바뀌는 단언 1).
  it('admin: /greenwash/**·/admin/** 그대로, /login·/password·/ → 첫 화면', () => {
    expect(guardOf(admin, '/greenwash/runs/run-1', noTemp)).toEqual(stay);
    expect(guardOf(admin, '/admin/accounts', noTemp)).toEqual(stay);
    expect(guardOf(admin, '/login', noTemp)).toEqual(to('/admin/accounts'));
    expect(guardOf(admin, '/password', noTemp)).toEqual(to('/admin/accounts'));
    expect(guardOf(admin, '/', noTemp)).toEqual(to('/admin/accounts'));
  });

  it('admin(밴드 SV1): /greenwash·/greenwash/new·/admin/accounts 는 stay, /·/login·/password·/zzz 는 /admin/accounts, 첫 화면은 그대로 /admin/accounts', () => {
    for (const path of ['/greenwash', '/greenwash/new', '/admin/accounts'])
      expect(guardOf(admin, path, noTemp), path).toEqual(stay);
    for (const path of ['/', '/login', '/password', '/zzz'])
      expect(guardOf(admin, path, noTemp), path).toEqual(to('/admin/accounts'));
    expect(landingOf(admin)).toBe('/admin/accounts');
    // 고객사 사용자는 그대로: /admin/** 는 막히고 첫 화면은 /greenwash.
    for (const path of ['/admin', '/admin/accounts', '/admin/audit'])
      expect(guardOf(service, path, noTemp), path).toEqual(to('/greenwash'));
    expect(landingOf(service)).toBe('/greenwash');
  });

  it('service: /admin/** → /greenwash, /greenwash/** 그대로, /login·/password·/ → 첫 화면', () => {
    expect(guardOf(service, '/admin/accounts', noTemp)).toEqual(
      to('/greenwash'),
    );
    expect(guardOf(service, '/greenwash/new', noTemp)).toEqual(stay);
    expect(guardOf(service, '/login', noTemp)).toEqual(to('/greenwash'));
    expect(guardOf(service, '/password', noTemp)).toEqual(to('/greenwash'));
    expect(guardOf(service, '/zzz', noTemp)).toEqual(to('/greenwash'));
  });
});

// 밴드 TRW1a(H2): 영문번역 /translation/** — 고객사 사용자·운영 관리자 둘 다 머문다(sid:MARC-ENT-380). 안 로그인·isInitial 은 그대로 첫 화면.
describe('translation 갈래', () => {
  it.each([
    ['/translation', 'translation'],
    ['/translation/new', 'translation'],
    ['/translation/documents/12/batches/run-3', 'translation'],
    ['/translationx', 'other'],
  ])('areaOf %s → %s', (path, area) => expect(areaOf(path)).toBe(area));

  it('service·admin: /translation/** stay, 안 로그인·isInitial 은 첫 화면', () => {
    for (const path of [
      '/translation',
      '/translation/new',
      '/translation/documents/12/batches/run-3',
    ]) {
      expect(guardOf(service, path, noTemp), path).toEqual(stay);
      expect(guardOf(admin, path, noTemp), path).toEqual(stay);
      expect(guardOf(signedOut, path, noTemp), path).toEqual(to('/login'));
      expect(guardOf(initial, path, withTemp), path).toEqual(to('/password'));
    }
  });
});

// 밴드 DV2a(H2): 데이터 검증 /dataverify/** — 고객사 사용자·운영 관리자 둘 다 머문다(sid:MARC-ENT-388). 안 로그인·isInitial 은 그대로 첫 화면.
describe('dataverify 갈래', () => {
  it.each([
    ['/dataverify', 'dataverify'],
    ['/dataverify/new', 'dataverify'],
    ['/dataverify/runs/12/result', 'dataverify'],
    ['/dataverifyx', 'other'],
  ])('areaOf %s → %s', (path, area) => expect(areaOf(path)).toBe(area));

  it('service·admin: /dataverify/** stay, 안 로그인·isInitial 은 첫 화면', () => {
    for (const path of [
      '/dataverify',
      '/dataverify/new',
      '/dataverify/runs/12/result',
    ]) {
      expect(guardOf(service, path, noTemp), path).toEqual(stay);
      expect(guardOf(admin, path, noTemp), path).toEqual(stay);
      expect(guardOf(signedOut, path, noTemp), path).toEqual(to('/login'));
      expect(guardOf(initial, path, withTemp), path).toEqual(to('/password'));
    }
  });
});

// 밴드 IRW1(H2): 중대성평가 /materiality/** — 고객사 사용자·운영 관리자 둘 다 머문다(sid:MARC-ENT-419). 안 로그인·isInitial 은 그대로 첫 화면.
describe('materiality 갈래', () => {
  it.each([
    ['/materiality', 'materiality'],
    ['/materiality/runs/7', 'materiality'],
    ['/materiality/runs/7/result', 'materiality'],
    ['/materialityx', 'other'],
  ])('areaOf %s → %s', (path, area) => expect(areaOf(path)).toBe(area));

  it('service·admin: /materiality/** stay, 안 로그인·isInitial 은 첫 화면', () => {
    for (const path of [
      '/materiality',
      '/materiality/runs/7',
      '/materiality/runs/7/result',
    ]) {
      expect(guardOf(service, path, noTemp), path).toEqual(stay);
      expect(guardOf(admin, path, noTemp), path).toEqual(stay);
      expect(guardOf(signedOut, path, noTemp), path).toEqual(to('/login'));
      expect(guardOf(initial, path, withTemp), path).toEqual(to('/password'));
    }
  });
});

// 밴드 W12-0a(H2): 온실가스 /ghg/** — 고객사 사용자·운영 관리자 둘 다 머문다(sid:MARC-ENT-469 4). 안 로그인·isInitial 은 그대로 첫 화면.
describe('ghg 갈래', () => {
  it.each([
    ['/ghg', 'ghg'],
    ['/ghg/organization', 'ghg'],
    ['/ghg/organization/branches/7', 'ghg'],
    ['/ghgx', 'other'],
  ])('areaOf %s → %s', (path, area) => expect(areaOf(path)).toBe(area));

  it('service·admin: /ghg/** stay, 안 로그인·isInitial 은 첫 화면', () => {
    for (const path of [
      '/ghg',
      '/ghg/organization',
      '/ghg/organization/branches/new',
    ]) {
      expect(guardOf(service, path, noTemp), path).toEqual(stay);
      expect(guardOf(admin, path, noTemp), path).toEqual(stay);
      expect(guardOf(signedOut, path, noTemp), path).toEqual(to('/login'));
      expect(guardOf(initial, path, withTemp), path).toEqual(to('/password'));
    }
  });
});

// 밴드 RPW1(A2): 원고작성 /drafting/** — 사용자 물음 ⑪(sid:MARC-ENT-525) 답 전 (가) — 고객사 사용자·운영 관리자 두 갈래 다 머문다.
//   안 로그인·isInitial 은 그대로 첫 화면.
describe('drafting 갈래', () => {
  it.each([
    ['/drafting', 'drafting'],
    ['/drafting/new', 'drafting'],
    ['/drafting/projects/7/document', 'drafting'],
    ['/draftingx', 'other'],
  ])('areaOf %s → %s', (path, area) => expect(areaOf(path)).toBe(area));

  it('service·admin: /drafting/** stay, 안 로그인·isInitial 은 첫 화면', () => {
    for (const path of [
      '/drafting',
      '/drafting/new',
      '/drafting/projects/7/outline',
    ]) {
      expect(guardOf(service, path, noTemp), path).toEqual(stay);
      expect(guardOf(admin, path, noTemp), path).toEqual(stay);
      expect(guardOf(signedOut, path, noTemp), path).toEqual(to('/login'));
      expect(guardOf(initial, path, withTemp), path).toEqual(to('/password'));
    }
  });
});
