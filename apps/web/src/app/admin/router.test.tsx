// @vitest-environment jsdom
// 어드민 경로·가드 시험(밴드 AD1). createAppRouter 에 메모리 기록과 가짜 로그인 서버(entities/session/api/testing.ts)를 넣어 본다.
//   ① 가드는 /admin 레이아웃 경로 하나: service·안 로그인·admin 이 /admin/** 를 열 때, 자식 경로에는 beforeLoad 가 없다(경로 트리를 읽는다)
//   ② 어드민 틀(LNB·머리 줄) ③ 머리 [로그아웃] → revoke → /login(화면은 navigate 하지 않는다 — 세션만 바뀐다). 그린워싱 틀의 [로그아웃]도.
//   ④ 메뉴 데이터화와 목 화면 경로 셋(밴드 AD2 — AD-03 은 OPW1 ② 에서 뺌): 위치 → 지금 항목, 누름 → 그 항목의 to, 두 빌드 다 열림(sid:MARC-ENT-285), 가드는 /admin 하나 그대로
//   ⑤ AD-05 감사 기록 경로(밴드 AD5R — 실서버): 세션 api 로 GET /audit-logs·/actors 를 Bearer 와 함께 부르고, 줄은 서버 값, 띠 없음, 「계정」 → AD-01
//   ⑨ AD-04 실행 기록 경로(밴드 AD4R — 실서버): 세션 api 로 GET /run-logs·/metrics 를 Bearer 와 함께 부르고, 줄은 서버 값, 띠 없음, 모의 공급사 안내 띠는 서버 지표 aiProviderMock(MP1W)
//   ⑥ AD-02 AI 설정 경로(밴드 AD2R — 실서버, AD2W — 모듈 슬롯): 세션 api 로 목록 GET /ai-settings/greenwash 와 고른 판의 prompt-model 을 Bearer 와 함께 부르고,
//      판은 서버 값, 띠 없음, 두 빌드 같음
//   ⑧ 운영 관리자의 그린워싱(밴드 SV1 ①): 「서비스 화면」 → 목록, 머리 인사말·[관리자 화면] → AD-01, 고객사 사용자에겐 없음, 그린워싱 머리 로그아웃 → /login
import { StrictMode } from 'react';

import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  afterEach,
  beforeAll,
  describe,
  expect,
  expectTypeOf,
  it,
  vi,
} from 'vitest';

import { ACCOUNT_TEXT } from '../../entities/account/config/text.ts';
import { fakePromptModelServer } from '../../entities/ai-setting/api/testing.ts';
import { AI_SETTING_TEXT } from '../../entities/ai-setting/config/text.ts';
import {
  fakeActor,
  fakeAuditRow,
  json,
} from '../../entities/audit-log/api/testing.ts';
import { AUDIT_TEXT } from '../../entities/audit-log/config/text.ts';
import { fakeDataverifySettingServer } from '../../entities/dataverify-setting/api/testing.ts';
import { fakeDraftingSettingServer } from '../../entities/drafting-setting/api/testing.ts';
import { DRAFTING_SETTING_TEXT } from '../../entities/drafting-setting/config/text.ts';
import { fakeGhgServer } from '../../entities/ghg/api/testing.ts';
import { fakeGreenwashSettingServer } from '../../entities/greenwash-setting/api/testing.ts';
import { fakeGreenwashServer } from '../../entities/greenwash/api/testing.ts';
import { fakeMaterialitySettingServer } from '../../entities/materiality-setting/api/testing.ts';
import { MATERIALITY_SETTING_TEXT } from '../../entities/materiality-setting/config/text.ts';
import {
  fakeRunMetrics,
  fakeRunRow,
} from '../../entities/run-log/api/testing.ts';
import { RUN_LOG_TEXT } from '../../entities/run-log/config/text.ts';
import {
  fakeAuthServer,
  memoryStorage,
} from '../../entities/session/api/testing.ts';
import type { FakeUser } from '../../entities/session/api/testing.ts';
import {
  REFRESH_STORAGE_KEY,
  SESSION_PATHS,
} from '../../entities/session/model/index.ts';
import { fakeTranslationSettingServer } from '../../entities/translation-setting/api/testing.ts';
import {
  ADMIN_HOME,
  ADMIN_MOVED,
  AI_SETTINGS_HOME_MODULE,
  GHG_SETTINGS_HOME,
  createAppRouter,
  validateAiSettingsSearch,
} from '../router.tsx';
import {
  AI_SETTINGS_HOME,
  GHG_SETTINGS_TABS,
  MENU,
  adminLocation,
  auditTarget,
  currentMenuId,
  menuTarget,
  onMenuSelect,
} from './AdminRoutes.tsx';
import type { AdminRuntime } from './runtime.ts';

afterEach(cleanup);
vi.setConfig({ testTimeout: 20_000 });
const WAIT = { timeout: 8_000 };

beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

const BASE = 'http://test.local/api';
const shell = ACCOUNT_TEXT.shell;

const accounts = (): Record<string, FakeUser> => ({
  'ops.admin': { password: 'admin-pass-1', kind: 'admin' },
  user01: { password: 'service-pass-1', kind: 'service' },
  user03: { password: 'temp-pass-1', kind: 'service', isInitial: true },
});

/** 감사 기록 두 경로의 지어낸 답(밴드 AD5R — 세션 가짜 서버는 모르는 경로에서 던지므로 늘 단다). */
const AUDIT_ROWS = [
  fakeAuditRow(2, {
    at: '2026-10-15T16:02:00+09:00',
    actorKind: 'admin',
    actorUserId: 1,
    actorName: '지어낸 관리자',
    actorUsername: 'ops.admin',
    companyId: null,
    action: 'setting_change',
    event: 'password_reset',
    targetKind: 'user',
    targetId: 12,
    targetLabel: 'user12',
  }),
  fakeAuditRow(1, {
    at: '2026-10-15T09:00:00+09:00',
    actorUserId: 11,
    actorName: '지어낸 담당자',
    actorUsername: 'user11',
  }),
];
const AUDIT_ACTORS = [fakeActor(11, { actorName: '지어낸 담당자' })];

/** 실행 기록 두 경로의 지어낸 답(밴드 AD4R — 같은 까닭으로 늘 단다). 테스트 실행 하나, 이름이 풀리지 않은 줄 하나. */
const RUN_ROWS = [
  fakeRunRow(32, {
    documentName: '지어낸 보고서.pdf',
    isTest: true,
  }),
  fakeRunRow(31, {
    module: 'dataverify',
    status: 'failed',
    createdByName: null,
    createdByUsername: null,
  }),
];
const RUN_METRICS = fakeRunMetrics({ runs: 7 });

// 지연 로드 화면(lazyRouteComponent)을 미리 불러 둔다 — 부하 아래 첫 waitFor 가 모듈 로드를 기다리지 않게(예열, sid:MARC-ISSUE-318).
// 경로 파일을 직접 가져오지 않고(칸 규칙) 버리는 라우터 하나의 경로 조각을 모두 싣는다. 모듈은 한 번 실리면 다음 라우터도 바로 쓴다.
beforeAll(async () => {
  const router = createAppRouter({
    history: createMemoryHistory(),
    openPdf: () => new Promise(() => {}),
    session: {
      send: fakeAuthServer(accounts(), { baseUrl: BASE }).send,
      storage: memoryStorage(),
      baseUrl: BASE,
    },
  });
  await Promise.all(
    Object.values(router.routesById).map((route) =>
      router.loadRouteChunk(route),
    ),
  );
}, 60_000);

/** 라우터 하나. signedIn 이면 그 계정의 refresh 를 보관소에 심는다(새로고침 뒤의 꼴). */
function setup(
  path: string,
  {
    signedIn,
    demos,
    runMetrics = RUN_METRICS,
  }: {
    signedIn?: string;
    demos?: boolean;
    runMetrics?: ReturnType<typeof fakeRunMetrics>;
  } = {},
) {
  const server = fakeAuthServer(accounts(), { baseUrl: BASE });
  server.override['GET /audit-logs'] = () =>
    json(200, { count: 2, isNext: false, results: AUDIT_ROWS });
  server.override['GET /audit-logs/actors'] = () =>
    json(200, { results: AUDIT_ACTORS });
  server.override['GET /run-logs'] = () =>
    json(200, { count: 2, isNext: false, results: RUN_ROWS });
  server.override['GET /run-logs/metrics'] = () => json(200, runMetrics);
  const greenwash = fakeGreenwashServer({ baseUrl: BASE });
  // AD-02 는 실서버(밴드 AD2R): 세션 가짜 서버는 모르는 경로에서 던지므로 MOCK_SCREENS 를 도는 시험도 이 가짜로 잇는다.
  const settings = fakeGreenwashSettingServer({ baseUrl: BASE });
  // AD-02 가 판마다 prompt-model 을 읽는다(밴드 AD2W ②) — /ai-settings/greenwash/{id|default}/prompt-model 은 이 가짜로.
  const promptModels = fakePromptModelServer({ baseUrl: BASE });
  // 밴드 TRA1: 영문번역 AD-02 — /ai-settings/translation(목록·적용·저장)과 그 prompt-model.
  const trSettings = fakeTranslationSettingServer({ baseUrl: BASE });
  const trPromptModels = fakePromptModelServer({
    baseUrl: BASE,
    module: 'translation',
  });
  // 밴드 DVA2: 데이터 검증 AD-02 — /ai-settings/dataverify(목록·적용·저장)과 그 prompt-model.
  const dvSettings = fakeDataverifySettingServer({ baseUrl: BASE });
  const dvPromptModels = fakePromptModelServer({
    baseUrl: BASE,
    module: 'dataverify',
  });
  // 밴드 IRA2: 중대성평가 IRO AD-02 — /ai-settings/materiality(목록·적용·저장)과 그 prompt-model.
  const msSettings = fakeMaterialitySettingServer({ baseUrl: BASE });
  const msPromptModels = fakePromptModelServer({
    baseUrl: BASE,
    module: 'materiality',
  });
  // 밴드 RPA3: 보고서 작성 AD-02 — /ai-settings/drafting(목록·적용·저장)과 그 prompt-model.
  const rpSettings = fakeDraftingSettingServer({ baseUrl: BASE });
  const rpPromptModels = fakePromptModelServer({
    baseUrl: BASE,
    module: 'drafting',
  });
  // 밴드 W12-0a ③·AD7: 「선택항목」 탭(/admin/ai-settings/ghg/options) — /admin/facility-codes 는 가짜 온실가스 서버로.
  const ghgCodes = fakeGhgServer({ baseUrl: BASE });
  /** AI 설정 경로로 나간 요청의 Authorization 글(세션 api 를 넘겼는지). */
  const settingAuth: (string | null)[] = [];
  const storage = memoryStorage();
  if (signedIn)
    storage.setItem(REFRESH_STORAGE_KEY, server.issue(signedIn).refresh);
  const history = createMemoryHistory({ initialEntries: [path] });
  const urls: URL[] = [];
  const router = createAppRouter({
    history,
    openPdf: () => new Promise(() => {}),
    // 보낸 주소를 적는다(세션 가짜는 쿼리를 적지 않는다 — UA1W 의 목록·전체 수 가름).
    session: {
      send: (request: Request) => {
        urls.push(new URL(request.url));
        // 고객사 사용자의 /greenwash 는 기본 저장소가 실어댑터다(밴드 GW1R 함정 ①) — 그린워싱 경로는 가짜 그린워싱 서버로.
        if (settings.handles(request)) {
          settingAuth.push(request.headers.get('Authorization'));
          return settings.send(request);
        }
        if (promptModels.handles(request)) {
          settingAuth.push(request.headers.get('Authorization'));
          return promptModels.send(request);
        }
        if (trSettings.handles(request)) return trSettings.send(request);
        if (trPromptModels.handles(request))
          return trPromptModels.send(request);
        if (dvSettings.handles(request)) return dvSettings.send(request);
        if (dvPromptModels.handles(request))
          return dvPromptModels.send(request);
        if (msSettings.handles(request)) return msSettings.send(request);
        if (msPromptModels.handles(request))
          return msPromptModels.send(request);
        if (rpSettings.handles(request)) return rpSettings.send(request);
        if (rpPromptModels.handles(request))
          return rpPromptModels.send(request);
        if (ghgCodes.handles(request)) return ghgCodes.send(request);
        return greenwash.handles(request) ?
            greenwash.send(request)
          : server.send(request);
      },
      storage,
      baseUrl: BASE,
    },
    demos,
  });
  render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  return {
    server,
    storage,
    history,
    router,
    urls,
    greenwash,
    settings,
    promptModels,
    settingAuth,
    trSettings,
    trPromptModels,
    dvSettings,
    dvPromptModels,
    msSettings,
    msPromptModels,
    rpSettings,
    rpPromptModels,
    ghgCodes,
  };
}

const pathOf = (history: { location: { pathname: string } }) =>
  history.location.pathname;
const atPath = (history: { location: { pathname: string } }, path: string) =>
  waitFor(() => expect(pathOf(history)).toBe(path), WAIT);
const screenShown = (name: string) =>
  waitFor(
    () =>
      expect(document.querySelector(`[data-screen="${name}"]`)).not.toBeNull(),
    WAIT,
  );

describe('어드민 ① 가드는 /admin 레이아웃 경로 하나', () => {
  it('첫 화면 글자(ADMIN_HOME)는 세션의 adminHome 과 같다', () => {
    expect(ADMIN_HOME).toBe(SESSION_PATHS.adminHome);
  });

  it.each(['/admin/accounts', '/admin', '/admin/zzz'])(
    '고객사 사용자가 %s 를 열면 /greenwash(replace)',
    async (path) => {
      const { history } = setup(path, { signedIn: 'user01' });
      await atPath(history, '/greenwash');
      await screenShown('list');
      expect(history.length).toBe(1);
    },
  );

  it.each([
    ['/admin', '/admin/accounts'],
    ['/admin/', '/admin/accounts'],
    ['/admin/zzz', '/admin/accounts'],
    ['/admin/accounts', '/admin/accounts'],
  ])('운영 관리자가 %s 를 열면 %s(replace)', async (path, landing) => {
    const { history } = setup(path, { signedIn: 'ops.admin' });
    await atPath(history, landing);
    await screenShown('admin-accounts');
    expect(history.length).toBe(1);
  });

  it.each(['/admin/accounts', '/admin'])(
    '안 로그인이 %s 를 열면 /login, 서버는 부르지 않는다',
    async (path) => {
      const { history, server } = setup(path);
      await atPath(history, '/login');
      await screenShown('login');
      expect(server.calls).toEqual([]);
    },
  );

  it.each(['/admin', '/admin/accounts'])(
    'isInitial(임시 비밀번호로 막 로그인)이 %s 를 열면 /password',
    async (path) => {
      const { history, router } = setup('/login');
      await screenShown('login');
      await router.options.context.session.login('user03', 'temp-pass-1');
      await atPath(history, '/password');
      void router.navigate({ to: path });
      await atPath(history, '/password');
      await screenShown('password');
    },
  );

  it('경로 트리: /admin 은 beforeLoad 를 갖고, 그 아래 자식 경로는 하나도 갖지 않는다(AD2 가 자식마다 가드를 달지 않게)', () => {
    const { router } = setup('/login');
    const routes = Object.values(router.routesById) as {
      id: string;
      options: { beforeLoad?: unknown };
    }[];
    const admin = routes.find((route) => route.id === '/admin');
    expect(admin?.options.beforeLoad).toBeTypeOf('function');
    const children = routes.filter((route) => route.id.startsWith('/admin/'));
    expect(children.map((route) => route.id)).toContain('/admin/accounts');
    for (const child of children)
      expect(child.options.beforeLoad, child.id).toBeUndefined();
  });
});

describe('어드민 ② 틀', () => {
  // AD2 ①: AD-02~05 는 목 화면이라도 모든 빌드에서 켬(sid:MARC-ENT-285). 앞 단언 「AD-02~05 꺼짐」을 두 빌드로 갈랐다(발주서 감독 판단 1 허락).
  it.each([
    ['데모(기본)', undefined],
    ['demos:false', false],
  ] as const)(
    'LNB 「관리자 메뉴」(%s): 계정 관리가 지금 화면, AD-02~05·서비스 화면 켜짐. 머리 줄 「관리자 STAFF」와 인사말',
    async (_, demos) => {
      setup('/admin/accounts', { signedIn: 'ops.admin', demos });
      await screenShown('admin-accounts');
      const nav = screen.getByRole('navigation', { name: shell.menuLabel });
      const item = (label: string) =>
        [...nav.querySelectorAll('button, a')].find(
          (node) => node.textContent === label,
        )!;
      expect(item(shell.menu.accounts).getAttribute('aria-current')).toBe(
        'page',
      );
      expect(
        item(shell.menu.accounts).getAttribute('aria-disabled'),
      ).toBeNull();
      for (const label of [
        shell.menu.aiSettings,
        shell.menu.runs,
        shell.menu.audit,
      ])
        expect(item(label).getAttribute('aria-disabled'), label).toBeNull();
      // 밴드 SV1(sid:MARC-ENT-286): 서비스 화면 켬(발주서 §2 바뀌는 단언 3).
      expect(item(shell.menu.service).getAttribute('aria-disabled')).toBeNull();
      expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(
        `${shell.title}${shell.staff}`,
      );
      expect(screen.getByText(shell.greeting)).toBeTruthy();
    },
  );
});

describe('어드민 ② AD-01 경로', () => {
  it('운영 관리자의 /admin/accounts: 세션의 api 로 GET /users(Bearer, limit=100) → 목록 줄이 뜬다', async () => {
    const { server } = setup('/admin/accounts', { signedIn: 'ops.admin' });
    server.override['GET /users'] = () =>
      new Response(
        JSON.stringify({
          count: 1,
          isNext: false,
          results: [
            {
              id: 7,
              companyId: 1,
              username: 'user07',
              name: '담당자 G',
              isActive: true,
              isInitial: true,
              isLocked: false,
              branchId: null,
              lastLoginAt: null,
              createdAt: '2026-10-01T09:00:00+09:00',
              companyName: '고객사 A',
            },
          ],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    await screen.findByText('user07', { selector: 'td' });
    const call = server.calls.find((row) => row.path === '/users')!;
    expect(call.authorization).toMatch(/^Bearer /);
    expect(
      document.querySelector('[data-screen="admin-accounts"]'),
    ).not.toBeNull();
    expect(document.querySelector('[data-status]')?.textContent).toBe(
      ACCOUNT_TEXT.status.initial,
    );
  });
});

describe('어드민 ② AD-01 실서버 쓰기 — 모든 빌드(UA1W ②, MARC-ENT-285)', () => {
  const row = (id: number, username: string) => ({
    id,
    companyId: 1,
    username,
    name: `담당자 ${id}`,
    isActive: true,
    isInitial: false,
    isLocked: false,
    branchId: null,
    lastLoginAt: null,
    createdAt: '2026-10-01T09:00:00+09:00',
    companyName: '고객사 A',
  });
  /** 세션 가짜에 계정 줄 하나를 단다: GET /users 는 지금 줄, PATCH /users/1 은 받은 본문(세션 가짜가 먼저 적은 calls 의 끝)을 입힌다. */
  function withAccount(server: ReturnType<typeof setup>['server']) {
    const account = row(1, 'user01');
    server.override['GET /users'] = () =>
      json(200, { count: 1, isNext: false, results: [account] });
    server.override['PATCH /users/1'] = () => {
      Object.assign(
        account,
        JSON.parse(server.calls.at(-1)!.body) as Partial<typeof account>,
      );
      return json(200, account);
    };
    return account;
  }
  const patchCalls = (server: ReturnType<typeof setup>['server']) =>
    server.calls.filter((call) => call.method === 'PATCH');

  it('router context 의 어드민 칸에 계정 덧칠 칸이 없다(타입·값)', () => {
    expectTypeOf<keyof AdminRuntime>().toEqualTypeOf<'demos'>();
    const { router } = setup('/login');
    expect('overlay' in router.options.context.admin).toBe(false);
  });

  it('/admin/accounts: GET /users 둘(목록·전체 수) 다 Bearer', async () => {
    const { server, urls } = setup('/admin/accounts', {
      signedIn: 'ops.admin',
      demos: false,
    });
    withAccount(server);
    await screen.findByText('user01', { selector: 'td' });
    // StrictMode 는 효과를 두 번 돌린다 — 짝 수는 보지 않고 둘 다 나갔는지만 본다.
    const limits = urls
      .filter((url) => url.pathname === '/api/users')
      .map((url) => url.searchParams.get('limit'));
    expect(limits).toContain('100');
    expect(limits).toContain('1');
    for (const call of server.calls.filter((row) => row.path === '/users'))
      expect(call.authorization).toMatch(/^Bearer /);
  });

  it('createAppRouter({ demos: false }): 「준비 중」 없음, [사용 중지] → 확인 → PATCH /users/1 한 번(Bearer, 본문 {isActive:false}) → 배지 「사용 중지」', async () => {
    const { server, router } = setup('/admin/accounts', {
      signedIn: 'ops.admin',
      demos: false,
    });
    withAccount(server);
    await screen.findByText('user01', { selector: 'td' });
    expect(router.options.context.admin.demos).toBe(false);
    expect(document.body.textContent).not.toContain('준비 중');
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: ACCOUNT_TEXT.list.select('user01'),
      }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: ACCOUNT_TEXT.list.deactivate }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: ACCOUNT_TEXT.active.deactivate }),
    );
    await waitFor(() =>
      expect(document.querySelector('[data-status]')?.textContent).toBe(
        ACCOUNT_TEXT.status.inactive,
      ),
    );
    const patches = patchCalls(server);
    expect(patches).toHaveLength(1);
    expect(patches[0]).toMatchObject({
      path: '/users/1',
      body: '{"isActive":false}',
    });
    expect(patches[0]!.authorization).toMatch(/^Bearer /);
  });

  it('createAppRouter({ demos: false }): 이름 칸은 단추 → 「재무팀」 Enter → PATCH /users/1 한 번(Bearer, 본문 {name}) → 서버 이름', async () => {
    const { server } = setup('/admin/accounts', {
      signedIn: 'ops.admin',
      demos: false,
    });
    withAccount(server);
    await screen.findByText('user01', { selector: 'td' });
    fireEvent.click(
      screen.getByRole('button', {
        name: ACCOUNT_TEXT.list.editName('user01'),
      }),
    );
    const input = screen.getByRole('textbox', {
      name: ACCOUNT_TEXT.list.nameLabel,
    });
    fireEvent.change(input, { target: { value: '재무팀' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await screen.findByText('재무팀', { selector: 'button' });
    const patches = patchCalls(server);
    expect(patches).toHaveLength(1);
    expect(patches[0]).toMatchObject({
      path: '/users/1',
      body: '{"name":"재무팀"}',
    });
    expect(patches[0]!.authorization).toMatch(/^Bearer /);
  });
});

describe('어드민 ③ 머리 [로그아웃]', () => {
  it('운영 관리자: [로그아웃] → revoke 한 번 → /login(보관소 refresh 지움). 두 번 눌러도 revoke 는 한 번', async () => {
    const { history, server, storage } = setup('/admin/accounts', {
      signedIn: 'ops.admin',
    });
    await screenShown('admin-accounts');
    const button = screen.getByRole('button', { name: '로그아웃' });
    fireEvent.click(button);
    fireEvent.click(button);
    await atPath(history, '/login');
    await screenShown('login');
    expect(server.count('POST /auth/revoke')).toBe(1);
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('고객사 사용자: 그린워싱 틀의 [로그아웃] → revoke → /login', async () => {
    const { history, server, greenwash } = setup('/greenwash', {
      signedIn: 'user01',
    });
    await screenShown('list');
    await waitFor(() =>
      expect(greenwash.count('GET /greenwash/checks')).toBeGreaterThan(0),
    );
    fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));
    await atPath(history, '/login');
    expect(server.count('POST /auth/revoke')).toBe(1);
  });
});

/**
 * 어드민 화면 셋(밴드 AD2 의 목 화면 — AD-05 는 AD5R, AD-04 는 AD4R, AD-02 는 AD2R 부터 실서버, AD-03 은 OPW1 ② 에서 뺌. 이름은 그대로):
 * 경로 · data-screen · 메뉴 글 · 그 화면에서 aria-current 인 메뉴 글(밴드 LN1: AI 설정은 부모와 하위 줄 「그린워싱」 둘).
 */
const MOCK_SCREENS = [
  // 밴드 AM1: AD-02 주소는 모듈 칸까지(/admin/ai-settings/greenwash). 경로 트리의 /admin 자식은 그대로 /admin/ai-settings(다섯째 칸).
  [
    '/admin/ai-settings/greenwash',
    'admin-ai-settings',
    shell.menu.aiSettings,
    [shell.menu.aiSettings, shell.menu.aiSettingsGreenwash],
    '/admin/ai-settings',
  ],
  [
    '/admin/runs',
    'admin-runs',
    shell.menu.runs,
    [shell.menu.runs],
    '/admin/runs',
  ],
  [
    '/admin/audit',
    'admin-audit',
    shell.menu.audit,
    [shell.menu.audit],
    '/admin/audit',
  ],
  // 밴드 AD7(sid:MARC-ENT-575): 「AI 설정 › 온실가스」 탭 껍데기의 첫 탭 S19 온실가스 인덱스(공통 풀) — 하위 줄 누름은 껍데기 주소, /admin 이 첫 탭으로.
  //   S18 선택항목은 둘째 탭이라 메뉴 줄이 없다 — 아래 「온실가스 탭 껍데기」 시험이 본다. 경로 트리의 /admin 자식은 /admin/ai-settings.
  [
    '/admin/ai-settings/ghg/index',
    'admin-ghg-index',
    shell.menu.aiSettingsGhg,
    [shell.menu.aiSettings, shell.menu.aiSettingsGhg],
    '/admin/ai-settings',
  ],
] as const;

/**
 * 가드 시험이 도는 주소(밴드 AD7 검증 B1): 목 화면 주소 + 메뉴 줄이 없는 「선택항목」 탭 + 옛 두 주소(넘김 전에 /admin 가드가 먼저 돈다).
 */
const GUARDED = [
  ...MOCK_SCREENS.map(([path]) => path),
  '/admin/ai-settings/ghg/options',
  '/admin/options',
  '/admin/ghg-index',
] as const;

const menuItem = (label: string) =>
  [
    ...screen
      .getByRole('navigation', { name: shell.menuLabel })
      .querySelectorAll('button, a'),
  ].find((node) => node.textContent === label)! as HTMLElement;
const currentItems = () =>
  [
    ...screen
      .getByRole('navigation', { name: shell.menuLabel })
      .querySelectorAll('[aria-current="page"]'),
  ].map((node) => node.textContent);

describe('어드민 ④ 메뉴 데이터화(밴드 AD2 ① — AD1 가지 리뷰 4)', () => {
  it.each([
    ['/admin/accounts', 'accounts'],
    // 밴드 LN1: AI 설정 경로는 하위 줄 「그린워싱」(부모 「AI 설정」도 같이 고른 꼴 — AppShell 이 그린다).
    // 밴드 AM1: 하위 줄마다 제 주소 — 가장 긴 to 앞머리 맞춤(꺼진 줄이어도 제 주소면 그 줄. 옛 /admin/ai-settings 는 넘김 전 잠깐이라 없음).
    ['/admin/ai-settings/greenwash', 'ai-settings-greenwash'],
    ['/admin/ai-settings/greenwash/x', 'ai-settings-greenwash'],
    ['/admin/ai-settings/translation', 'ai-settings-translation'],
    ['/admin/ai-settings/dataverify', 'ai-settings-dataverify'],
    ['/admin/ai-settings/materiality', 'ai-settings-materiality'],
    ['/admin/ai-settings/drafting', 'ai-settings-drafting'],
    ['/admin/ai-settings/greenwashx', undefined],
    ['/admin/ai-settings', undefined],
    ['/admin/runs', 'runs'],
    ['/admin/audit', 'audit'],
    ['/admin/audit/x', 'audit'],
    // 밴드 AD7: 온실가스 탭 껍데기 — 두 탭 어디서든 하위 줄 「온실가스」. 옛 두 주소는 메뉴 항목이 없다(넘김 전 잠깐).
    ['/admin/ai-settings/ghg', 'ai-settings-ghg'],
    ['/admin/ai-settings/ghg/index', 'ai-settings-ghg'],
    ['/admin/ai-settings/ghg/options', 'ai-settings-ghg'],
    ['/admin/ai-settings/ghgx', undefined],
    ['/admin/ghg-index', undefined],
    ['/admin/options', undefined],
    ['/admin/zzz', undefined],
    ['/admin/runsx', undefined],
    ['/admin', undefined],
    ['/greenwash', 'service'],
  ])('위치 %s → 지금 항목 %s', (pathname, id) => {
    expect(currentMenuId(pathname)).toBe(id);
  });

  it('지금 항목은 가장 긴 to 앞머리 맞춤(밴드 AM1, sid:MARC-ENT-444): 짧은 to 가 앞에 있어도 더 긴 제 줄 — 앞머리가 겹치는 표로 본다', () => {
    // 지금 MENU 에는 앞머리가 겹치는 to 쌍이 없다 — 겹침(옛 부모 /admin/ai-settings 꼴)은 이 표로만 만든다.
    const menu = [
      { id: 'wide', label: 'wide', to: '/admin/ai-settings' },
      {
        id: 'parent',
        label: 'parent',
        to: '/admin/runs',
        children: [
          { id: 'deep', label: 'deep', to: '/admin/ai-settings/translation' },
        ],
      },
      { id: 'after', label: 'after', to: '/admin/ai-settings/translation/x' },
    ] as unknown as Parameters<typeof currentMenuId>[1];
    expect(currentMenuId('/admin/ai-settings/translation', menu)).toBe('deep');
    expect(currentMenuId('/admin/ai-settings/translation/x/y', menu)).toBe(
      'after',
    );
    expect(currentMenuId('/admin/ai-settings/greenwash', menu)).toBe('wide');
    expect(currentMenuId('/admin/runs', menu)).toBe('parent');
  });

  it('이동은 항목의 to 를 따른다(id 로 경로를 짓지 않는다 — id≠경로 표로 본다)', () => {
    const menu = [
      { id: 'x', label: 'x', to: '/admin/runs' },
      { id: 'audit', label: 'audit', to: '/admin/accounts' },
      { id: 'off', label: 'off', disabled: true },
    ] as const;
    expect(menuTarget(menu, 'x')).toBe('/admin/runs');
    expect(menuTarget(menu, 'audit')).toBe('/admin/accounts');
    expect(menuTarget(menu, 'off')).toBeUndefined();
    expect(menuTarget(menu, 'zzz')).toBeUndefined();
    expect(menuTarget(MENU, 'service')).toBe('/greenwash');
  });

  it('메뉴 누름 처리기(AdminLayout 의 onSelect)는 그 항목의 to 로만 go 를 부른다 — id≠경로 표와 가짜 go', () => {
    const menu = [
      { id: 'x', label: 'x', to: '/admin/runs' },
      { id: 'audit', label: 'audit', to: '/admin/accounts' },
      { id: 'off', label: 'off', disabled: true },
    ] as const;
    const go = vi.fn();
    const select = onMenuSelect(menu, go);
    select('x');
    expect(go).toHaveBeenLastCalledWith('/admin/runs');
    select('audit');
    expect(go).toHaveBeenLastCalledWith('/admin/accounts');
    select('off');
    select('zzz');
    expect(go).toHaveBeenCalledTimes(2);
  });

  it('AdminLayout 의 메뉴 onSelect 는 onMenuSelect(MENU, …) 하나다(처리기를 건너뛰어 경로를 짓지 않게 — 글자로 본다)', () => {
    const source = readFileSync(
      // jsdom 환경이라 import.meta.url 이 file: 이 아니다 — vitest 의 cwd(apps/web) 기준.
      resolve(process.cwd(), 'src/app/admin/AdminRoutes.tsx'),
      'utf8',
    );
    expect(source.match(/\bonSelect=\{/g)).toHaveLength(1);
    expect(source).toMatch(/onSelect=\{onMenuSelect\(\s*MENU,/);
  });

  it('메뉴 항목의 to 는 그 항목의 경로, 서비스 화면은 /greenwash(켬)', () => {
    expect(MENU.map(({ id, to, disabled }) => [id, to, disabled])).toEqual([
      ['accounts', '/admin/accounts', undefined],
      ['ai-settings', '/admin/ai-settings/greenwash', undefined],
      ['runs', '/admin/runs', undefined],
      ['audit', '/admin/audit', undefined],
      ['service', '/greenwash', undefined],
    ]);
  });

  it('「AI 설정」 하위 줄 여섯(밴드 LN1·RPA3): 시안 차례, 줄마다 제 주소 /admin/ai-settings/<id>(밴드 AM1), 그린워싱·영문번역 켬(밴드 TRA1), 보고서 작성은 끝에 새로 켬(밴드 RPA3), 온실가스도 켬 — 탭 껍데기 주소(밴드 AD7), 꺼진 줄 0', () => {
    const ai = MENU.find(({ id }) => id === 'ai-settings');
    expect(ai?.childrenLabel).toBe(shell.aiSettingsModulesLabel);
    expect(
      ai?.children?.map(({ id, label, to, disabled }) => [
        id,
        label,
        to,
        disabled,
      ]),
    ).toEqual([
      [
        'ai-settings-greenwash',
        shell.menu.aiSettingsGreenwash,
        '/admin/ai-settings/greenwash',
        undefined,
      ],
      [
        'ai-settings-ghg',
        shell.menu.aiSettingsGhg,
        '/admin/ai-settings/ghg',
        undefined,
      ],
      [
        'ai-settings-materiality',
        shell.menu.aiSettingsMateriality,
        '/admin/ai-settings/materiality',
        undefined,
      ],
      [
        'ai-settings-dataverify',
        shell.menu.aiSettingsDataverify,
        '/admin/ai-settings/dataverify',
        undefined,
      ],
      [
        'ai-settings-translation',
        shell.menu.aiSettingsTranslation,
        '/admin/ai-settings/translation',
        undefined,
      ],
      [
        'ai-settings-drafting',
        shell.menu.aiSettingsDrafting,
        '/admin/ai-settings/drafting',
        undefined,
      ],
    ]);
  });

  it('하위 줄 누름(밴드 LN1·AM1·TRA1·DVA2·IRA2·RPA3·AD7): 온실가스 → /admin/ai-settings/ghg(탭 껍데기), 그린워싱 → /admin/ai-settings/greenwash, 영문번역 → /admin/ai-settings/translation, 데이터 검증 → /admin/ai-settings/dataverify, 중대성평가 → /admin/ai-settings/materiality, 보고서 작성 → /admin/ai-settings/drafting, 부모 「AI 설정」 → /admin/ai-settings/greenwash', () => {
    const go = vi.fn();
    const select = onMenuSelect(MENU, go);
    select('ai-settings-ghg');
    expect(go).toHaveBeenLastCalledWith('/admin/ai-settings/ghg');
    select('ai-settings-translation');
    expect(go).toHaveBeenLastCalledWith('/admin/ai-settings/translation');
    select('ai-settings-dataverify');
    expect(go).toHaveBeenLastCalledWith('/admin/ai-settings/dataverify');
    select('ai-settings-materiality');
    expect(go).toHaveBeenLastCalledWith('/admin/ai-settings/materiality');
    select('ai-settings-drafting');
    expect(go).toHaveBeenLastCalledWith('/admin/ai-settings/drafting');
    select('ai-settings-greenwash');
    expect(go).toHaveBeenLastCalledWith('/admin/ai-settings/greenwash');
    select('ai-settings');
    expect(go).toHaveBeenLastCalledWith('/admin/ai-settings/greenwash');
    expect(go).toHaveBeenCalledTimes(7);
  });

  it('하위 줄 그림(밴드 LN1·TRA1·DVA2·IRA2·RPA3·AD7): 꺼진 줄 0 — 온실가스·영문번역·데이터 검증·중대성평가·보고서 작성도 켬, 그린워싱 누름 → AD-02', async () => {
    const { history } = setup('/admin/accounts', { signedIn: 'ops.admin' });
    await screenShown('admin-accounts');
    const group = screen.getByRole('list', {
      name: shell.aiSettingsModulesLabel,
    });
    expect(group.closest('li')).toBe(
      menuItem(shell.menu.aiSettings).closest('li'),
    );
    expect(group.querySelectorAll('[aria-disabled]')).toHaveLength(0);
    expect(
      menuItem(shell.menu.aiSettingsGhg).hasAttribute('aria-disabled'),
    ).toBe(false);
    expect(
      menuItem(shell.menu.aiSettingsTranslation).hasAttribute('aria-disabled'),
    ).toBe(false);
    expect(
      menuItem(shell.menu.aiSettingsDataverify).hasAttribute('aria-disabled'),
    ).toBe(false);
    expect(
      menuItem(shell.menu.aiSettingsMateriality).hasAttribute('aria-disabled'),
    ).toBe(false);
    expect(
      menuItem(shell.menu.aiSettingsDrafting).hasAttribute('aria-disabled'),
    ).toBe(false);
    expect(pathOf(history)).toBe('/admin/accounts');
    expect(currentItems()).toEqual([shell.menu.accounts]);
    fireEvent.click(menuItem(shell.menu.aiSettingsGreenwash));
    await atPath(history, '/admin/ai-settings/greenwash');
    await screenShown('admin-ai-settings');
    expect(currentItems()).toEqual([
      shell.menu.aiSettings,
      shell.menu.aiSettingsGreenwash,
    ]);
  });

  it('「실행 기록」 메뉴 아이콘은 24×24 막대그래프(ChartSquareIcon) — LNB 선택 막대 BarIcon(0 0 4 48) 아님(밴드 DT1 C7)', async () => {
    setup('/admin/accounts', { signedIn: 'ops.admin' });
    await screenShown('admin-accounts');
    const icons = [...menuItem(shell.menu.runs).querySelectorAll('svg')];
    expect(icons.length).toBeGreaterThan(0);
    for (const icon of icons) {
      expect(icon.getAttribute('viewBox')).toBe('0 0 24 24');
      expect(icon.getAttribute('viewBox')).not.toBe('0 0 4 48');
    }
  });

  it.each([
    ['데모(기본)', undefined],
    ['demos:false', false],
  ] as const)(
    '%s: 운영 관리자가 목 화면 셋을 열면 그 화면, 메뉴 지금 항목은 그 화면의 것만(AI 설정은 부모+하위 줄)',
    async (_, demos) => {
      for (const [path, name, , current] of MOCK_SCREENS) {
        const { history } = setup(path, { signedIn: 'ops.admin', demos });
        await screenShown(name);
        expect(pathOf(history)).toBe(path);
        expect(currentItems()).toEqual(current);
        cleanup();
      }
    },
  );

  it('「선택항목」 탭(밴드 W12-0a ③ · AD7): 세션 api 로 코드 목록을 읽어 이름을 그린다 · 위층 메뉴 항목 없음', async () => {
    const { ghgCodes } = setup('/admin/ai-settings/ghg/options', {
      signedIn: 'ops.admin',
    });
    await screenShown('admin-options');
    await waitFor(
      () => expect(screen.getByText('지어낸 보일러')).not.toBeNull(),
      WAIT,
    );
    // StrictMode 는 첫 읽기를 두 번 할 수 있다.
    expect(ghgCodes.count('GET /admin/facility-codes')).toBeGreaterThan(0);
    expect(MENU.find(({ id }) => id === 'options')).toBeUndefined();
  });

  it('「온실가스 인덱스」 탭(밴드 W12-0b1 ③ · AD7): 하위 줄 「온실가스」 누름 → /admin/ai-settings/ghg/index(replace 넘김) · 표식 · 세션 api 로 풀 범위 단·코드 목록을 읽음 · 지금 항목 · 위층 메뉴 항목 없음', async () => {
    const { history, ghgCodes } = setup('/admin/accounts', {
      signedIn: 'ops.admin',
    });
    await screenShown('admin-accounts');
    fireEvent.click(menuItem(shell.menu.aiSettingsGhg));
    await atPath(history, '/admin/ai-settings/ghg/index');
    await screenShown('admin-ghg-index');
    // 껍데기 주소는 넘김(replace)이라 기록은 계정 관리 + 첫 탭 둘.
    expect(history.length).toBe(2);
    await waitFor(
      () => expect(screen.getByText('지어낸 직접배출')).not.toBeNull(),
      WAIT,
    );
    expect(currentItems()).toEqual([
      shell.menu.aiSettings,
      shell.menu.aiSettingsGhg,
    ]);
    expect(
      ghgCodes.count('GET /inventory/admin/ghg-index/nodes'),
    ).toBeGreaterThan(0);
    expect(ghgCodes.count('GET /admin/facility-codes')).toBeGreaterThan(0);
    expect(MENU.find(({ id }) => id === 'ghg-index')).toBeUndefined();
  });

  it('온실가스 탭 껍데기(밴드 AD7, sid:MARC-ENT-575): 탭 둘(온실가스 인덱스·선택항목, 차례·이름은 옛 메뉴 글) · 첫 탭 고름 · 「선택항목」 누름 → …/ghg/options(push) · 고른 탭 바뀜 · 메뉴 지금 항목 그대로 · 다시 첫 탭', async () => {
    const { history } = setup('/admin/ai-settings/ghg/index', {
      signedIn: 'ops.admin',
    });
    await screenShown('admin-ghg-index');
    // 밴드 AD8(sid:MARC-ISSUE-575): 머리는 껍데기의 「AI 설정 — 온실가스」 하나, 탭 줄 위, 탭 안 제목 되풀이 0.
    const head = AI_SETTING_TEXT.title(shell.menu.aiSettingsGhg);
    const titles = () =>
      screen
        .getAllByRole('heading', { level: 2 })
        .filter((one) => one.closest('[data-screen]') === null)
        .map((one) => one.textContent);
    expect(titles()).toEqual([head]);
    const tabs = screen.getByRole('tablist', {
      name: shell.menu.aiSettingsGhg,
    });
    expect(
      screen
        .getByRole('heading', { name: head })
        .compareDocumentPosition(tabs) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      screen.queryByRole('heading', { name: shell.menu.ghgIndex }),
    ).toBeNull();
    const tabNames = () =>
      [...tabs.querySelectorAll('[role="tab"]')].map((tab) => [
        tab.textContent,
        tab.getAttribute('aria-selected'),
      ]);
    expect(tabNames()).toEqual([
      [shell.menu.ghgIndex, 'true'],
      [shell.menu.options, 'false'],
    ]);
    expect(GHG_SETTINGS_TABS.map(({ to }) => to)).toEqual([
      GHG_SETTINGS_HOME,
      '/admin/ai-settings/ghg/options',
    ]);
    // Radix 탭은 mousedown 으로 고른다.
    fireEvent.mouseDown(screen.getByRole('tab', { name: shell.menu.options }));
    await atPath(history, '/admin/ai-settings/ghg/options');
    await screenShown('admin-options');
    expect(titles()).toEqual([head]);
    expect(
      screen.queryByRole('heading', { name: shell.menu.options }),
    ).toBeNull();
    expect(history.length).toBe(2);
    expect(tabNames()).toEqual([
      [shell.menu.ghgIndex, 'false'],
      [shell.menu.options, 'true'],
    ]);
    expect(currentItems()).toEqual([
      shell.menu.aiSettings,
      shell.menu.aiSettingsGhg,
    ]);
    fireEvent.mouseDown(screen.getByRole('tab', { name: shell.menu.ghgIndex }));
    await atPath(history, '/admin/ai-settings/ghg/index');
    await screenShown('admin-ghg-index');
  });

  it.each([
    ['/admin/ai-settings/ghg', GHG_SETTINGS_HOME, 'admin-ghg-index'],
    ['/admin/ai-settings/ghg/', GHG_SETTINGS_HOME, 'admin-ghg-index'],
    ['/admin/ghg-index', GHG_SETTINGS_HOME, 'admin-ghg-index'],
    ['/admin/ghg-index/', GHG_SETTINGS_HOME, 'admin-ghg-index'],
    ['/admin/options', '/admin/ai-settings/ghg/options', 'admin-options'],
    ['/admin/options/', '/admin/ai-settings/ghg/options', 'admin-options'],
  ] as const)(
    '넘김(밴드 AD7): %s → %s(replace — 기록 하나) · 메뉴 지금 항목 「AI 설정 › 온실가스」',
    async (from, to, name) => {
      const { history } = setup(from, { signedIn: 'ops.admin' });
      await atPath(history, to);
      await screenShown(name);
      expect(history.length).toBe(1);
      expect(currentItems()).toEqual([
        shell.menu.aiSettings,
        shell.menu.aiSettingsGhg,
      ]);
    },
  );

  it('모듈 칸이 ghg 를 삼키지 않는다(밴드 AD7): ghg 는 고정 경로 껍데기, 없는 모듈(ghgx)은 그대로 그린워싱으로 넘김', async () => {
    const { history } = setup('/admin/ai-settings/ghgx', {
      signedIn: 'ops.admin',
    });
    await atPath(history, AI_SETTINGS_HOME);
    await screenShown('admin-ai-settings');
    cleanup();
    const again = setup('/admin/ai-settings/ghg/zzz', {
      signedIn: 'ops.admin',
    });
    // 껍데기 아래 모르는 탭은 루트 splat — 첫 화면(그 밖 주소와 같은 길).
    await atPath(again.history, '/admin/accounts');
    expect(ADMIN_MOVED).toEqual({
      '/admin/ai-settings/ghg': GHG_SETTINGS_HOME,
      '/admin/ghg-index': GHG_SETTINGS_HOME,
      '/admin/options': '/admin/ai-settings/ghg/options',
    });
  });

  it('메뉴 누름 → 그 항목의 to 로 이동(계정 관리 → 셋 → 계정 관리 → 서비스 화면 → 그린워싱 목록)', async () => {
    const { history } = setup('/admin/accounts', { signedIn: 'ops.admin' });
    await screenShown('admin-accounts');
    for (const [path, name, label, current] of MOCK_SCREENS) {
      fireEvent.click(menuItem(label));
      await atPath(history, path);
      await screenShown(name);
      expect(currentItems()).toEqual(current);
    }
    fireEvent.click(menuItem(shell.menu.accounts));
    await atPath(history, '/admin/accounts');
    await screenShown('admin-accounts');
    // 밴드 SV1: 서비스 화면 → 그린워싱 목록(발주서 §2 바뀌는 단언 7).
    fireEvent.click(menuItem(shell.menu.service));
    await atPath(history, '/greenwash');
    await screenShown('list');
  });

  it.each(GUARDED)(
    '고객사 사용자가 %s 를 열면 /greenwash(replace)',
    async (path) => {
      const { history } = setup(path, { signedIn: 'user01' });
      await atPath(history, '/greenwash');
      await screenShown('list');
      expect(history.length).toBe(1);
    },
  );

  it.each(GUARDED)(
    '안 로그인이 %s 를 열면 /login, 서버는 부르지 않는다',
    async (path) => {
      const { history, server } = setup(path);
      await atPath(history, '/login');
      expect(server.calls).toEqual([]);
    },
  );

  it('경로 트리: 목 화면 셋은 /admin 의 자식이고 beforeLoad 가 없다(두 빌드 다)', () => {
    for (const demos of [undefined, false]) {
      const { router } = setup('/login', { demos });
      const routes = Object.values(router.routesById) as {
        id: string;
        parentRoute?: { id: string };
        options: { beforeLoad?: unknown };
      }[];
      for (const [, , , , path] of MOCK_SCREENS) {
        const route = routes.find((row) => row.id === path);
        expect(route?.parentRoute?.id, path).toBe('/admin');
        expect(route?.options.beforeLoad, path).toBeUndefined();
      }
      cleanup();
    }
  });

  it('감사 링크 주소(auditTarget — 밴드 AM1, sid:MARC-ISSUE-291): module 있으면 그 모듈 주소, null 이면 그린워싱. 판은 search', () => {
    expect(
      auditTarget({
        kind: 'ai-settings',
        module: 'translation',
        version: 'v2',
      }),
    ).toEqual({
      to: '/admin/ai-settings/$module',
      params: { module: 'translation' },
      search: { version: 'v2' },
    });
    expect(
      auditTarget({ kind: 'ai-settings', module: null, version: null }),
    ).toEqual({
      to: '/admin/ai-settings/$module',
      params: { module: 'greenwash' },
      search: {},
    });
    expect(auditTarget({ kind: 'accounts' })).toEqual({
      to: '/admin/accounts',
    });
  });

  it('AD-02 모듈 주소 → 경로 틀 + 경로 칸(adminLocation — 밴드 AM1). 처음 주소는 router 의 처음 모듈과 같다', () => {
    expect(adminLocation('/admin/ai-settings/translation')).toEqual({
      to: '/admin/ai-settings/$module',
      params: { module: 'translation' },
    });
    expect(adminLocation('/admin/runs')).toEqual({ to: '/admin/runs' });
    // 밴드 AD7: 온실가스 탭 껍데기는 모듈 칸으로 펴지 않는다(고정 경로).
    expect(adminLocation('/admin/ai-settings/ghg')).toEqual({
      to: '/admin/ai-settings/ghg',
    });
    expect(adminLocation('/admin/ai-settings/ghg/options')).toEqual({
      to: '/admin/ai-settings/ghg/options',
    });
    expect(AI_SETTINGS_HOME).toBe(
      `/admin/ai-settings/${AI_SETTINGS_HOME_MODULE}`,
    );
  });

  it('AD-02 의 search: version 은 「v숫자」만 남긴다', () => {
    expect(validateAiSettingsSearch({ version: 'v3' })).toEqual({
      version: 'v3',
    });
    for (const version of ['3', 'v', 'v3x', '', undefined, 3])
      expect(validateAiSettingsSearch({ version }), String(version)).toEqual(
        {},
      );
  });
});

describe('어드민 ⑦ AD-03 테스트 비교는 없다(밴드 OPW1 ② — sid:MARC-ENT-362, sid:MARC-ISSUE-244)', () => {
  it.each([
    ['ops.admin', '/admin/accounts', 'admin-accounts'],
    ['user01', '/greenwash', 'list'],
  ] as const)(
    '%s 가 /admin/test-compare 를 열면 첫 화면 %s(replace — 그 밖 주소와 같은 길)',
    async (user, landing, name) => {
      const { history } = setup('/admin/test-compare', { signedIn: user });
      await atPath(history, landing);
      await screenShown(name);
      expect(history.length).toBe(1);
      expect(
        document.querySelector('[data-screen="admin-test-compare"]'),
      ).toBeNull();
    },
  );

  it('경로 트리에 /admin/test-compare 가 없다. /admin 의 자식은 accounts·ai-settings·runs·audit·옛 주소 둘(ghg-index·options — 화면 없음, 밴드 AD7). ai-settings 의 자식은 $module·ghg, ghg 의 자식은 index·options(셋째 탭 없음) — 모두 beforeLoad 없음', () => {
    const { router } = setup('/login');
    const routes = Object.values(router.routesById) as {
      id: string;
      parentRoute?: { id: string };
    }[];
    expect(routes.some((row) => row.id === '/admin/test-compare')).toBe(false);
    expect(
      routes
        .filter((row) => row.parentRoute?.id === '/admin')
        .map((row) => row.id),
    ).toEqual([
      '/admin/accounts',
      '/admin/ai-settings',
      '/admin/runs',
      '/admin/audit',
      '/admin/ghg-index',
      '/admin/options',
    ]);
    const childrenOf = (id: string) =>
      routes.filter((row) => row.parentRoute?.id === id);
    expect(childrenOf('/admin/ai-settings').map((row) => row.id)).toEqual([
      '/admin/ai-settings/$module',
      '/admin/ai-settings/ghg',
    ]);
    expect(childrenOf('/admin/ai-settings/ghg').map((row) => row.id)).toEqual([
      '/admin/ai-settings/ghg/index',
      '/admin/ai-settings/ghg/options',
    ]);
    const options = (id: string) =>
      (
        routes.find((row) => row.id === id) as unknown as {
          options: { beforeLoad?: unknown; component?: unknown };
        }
      ).options;
    for (const id of [
      '/admin/ai-settings/ghg',
      '/admin/ai-settings/ghg/index',
      '/admin/ai-settings/ghg/options',
      '/admin/ghg-index',
      '/admin/options',
    ])
      expect(options(id).beforeLoad, id).toBeUndefined();
    expect(options('/admin/ghg-index').component).toBeUndefined();
    expect(options('/admin/options').component).toBeUndefined();
  });

  it('어드민 메뉴에 「테스트 비교」가 없다. 항목 id 차례는 accounts·ai-settings·runs·audit·service(온실가스 인덱스·선택항목은 AI 설정 › 온실가스 탭으로 — 밴드 AD7)', async () => {
    expect(MENU.map(({ id }) => id)).toEqual([
      'accounts',
      'ai-settings',
      'runs',
      'audit',
      'service',
    ]);
    setup('/admin/accounts', { signedIn: 'ops.admin' });
    await screenShown('admin-accounts');
    const labels = [
      ...screen
        .getByRole('navigation', { name: shell.menuLabel })
        .querySelectorAll('button, a'),
    ].map((node) => node.textContent);
    expect(labels).toEqual([
      shell.menu.accounts,
      shell.menu.aiSettings,
      // 밴드 LN1·RPA3: 「AI 설정」 하위 줄 여섯(시안 차례 — 끝 보고서 작성).
      shell.menu.aiSettingsGreenwash,
      shell.menu.aiSettingsGhg,
      shell.menu.aiSettingsMateriality,
      shell.menu.aiSettingsDataverify,
      shell.menu.aiSettingsTranslation,
      shell.menu.aiSettingsDrafting,
      shell.menu.runs,
      shell.menu.audit,
      shell.menu.service,
    ]);
    expect(screen.queryByText('테스트 비교')).toBeNull();
  });
});

describe('어드민 ⑤ AD-05 감사 기록 경로(밴드 AD2 ①, 실서버 AD5R ②)', () => {
  it.each([
    ['데모(기본)', undefined],
    ['demos:false', false],
  ] as const)(
    '%s: 세션 api 로 GET /audit-logs·/audit-logs/actors 를 Bearer 와 함께 부르고, 줄은 서버 값, 띠 없음, 「계정」 → /admin/accounts',
    async (_, demos) => {
      const { history, server } = setup('/admin/audit', {
        signedIn: 'ops.admin',
        demos,
      });
      await screenShown('admin-audit');
      await screen.findByText('지어낸 담당자');
      // 서버 경로를 불렀다(StrictMode 라 효과가 두 번 돌 수 있어 1 이상)
      expect(server.count('GET /audit-logs')).toBeGreaterThanOrEqual(1);
      expect(server.count('GET /audit-logs/actors')).toBeGreaterThanOrEqual(1);
      const auditCalls = server.calls.filter((call) =>
        call.path.startsWith('/audit-logs'),
      );
      expect(auditCalls.length).toBeGreaterThanOrEqual(2);
      for (const call of auditCalls)
        expect(call.authorization, call.path).toMatch(/^Bearer \S+$/);
      // 줄은 override 의 지어낸 값
      expect(
        [...document.querySelectorAll('tbody tr[data-audit-id]')].map((row) =>
          row.getAttribute('data-audit-id'),
        ),
      ).toEqual(['2', '1']);
      expect(
        document.querySelectorAll('tr[data-audit-id="2"] td')[3]!.textContent,
      ).toBe('계정 · user12 비밀번호 초기화');
      expect(screen.getByTestId('count').textContent).toBe(AUDIT_TEXT.count(2));
      // 예시 데이터 띠는 AD-05 에서만 걷혔다
      expect(screen.queryByTestId('mock-band')).toBeNull();
      const link = screen.getByRole('link', { name: '계정' });
      expect(link.getAttribute('href')).toBe('/admin/accounts');
      fireEvent.click(link);
      await atPath(history, '/admin/accounts');
      await screenShown('admin-accounts');
      expect(
        server.calls.every((call) =>
          /^\/(auth|users|audit-logs)(\/|$)/.test(call.path),
        ),
      ).toBe(true);
    },
  );

  it('AI 설정 줄(밴드 AD4X ③·AM1): 「AI 설정」 href = /admin/ai-settings/greenwash?version=v3, 누름 → AD-02 화면(v3). 기본 판 적용 줄은 /admin/ai-settings/greenwash', async () => {
    const { history, server } = setup('/admin/audit', {
      signedIn: 'ops.admin',
    });
    // 화면이 불러오기 전에 이 시험의 줄로 덮는다(모듈 맨 위 AUDIT_ROWS 는 그대로).
    server.override['GET /audit-logs'] = () =>
      json(200, {
        count: 2,
        isNext: false,
        results: [
          fakeAuditRow(4, {
            action: 'setting_change',
            event: 'ai_setting_created',
            targetKind: 'ai_setting',
            targetId: 3,
            targetLabel: 'v3',
            module: 'greenwash',
          }),
          fakeAuditRow(3, {
            action: 'setting_change',
            event: 'ai_setting_applied',
            targetKind: 'ai_setting',
            targetId: null,
            targetLabel: 'colab-2026-01-15-v1',
            module: 'greenwash',
          }),
        ],
      });
    await screenShown('admin-audit');
    const links = await screen.findAllByRole('link', { name: 'AI 설정' });
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/admin/ai-settings/greenwash?version=v3',
      '/admin/ai-settings/greenwash',
    ]);
    fireEvent.click(links[0]!);
    await atPath(history, '/admin/ai-settings/greenwash');
    await screenShown('admin-ai-settings');
    expect(
      await screen.findByRole('heading', {
        name: AI_SETTING_TEXT.prompt.title('v3'),
      }),
    ).toBeTruthy();
    expect(history.location.search).toBe('?version=v3');
  });

  it('AD-02 에도 예시 데이터 띠가 없다(밴드 AD2R — 서버가 와서 걷힘). 띠는 어느 어드민 화면에도 없다', async () => {
    setup('/admin/ai-settings', { signedIn: 'ops.admin' });
    // 기준표 카드는 걷었다(밴드 GW2R ④) — 처음 구성 프롬프트 카드로 그림을 기다린다
    await screen.findByRole('heading', {
      name: AI_SETTING_TEXT.prompt.title('v3'),
    });
    expect(screen.queryByTestId('mock-band')).toBeNull();
  });
});

describe('어드민 ⑥ AD-02 AI 설정 경로(밴드 AD2R — 실서버, 두 빌드 같음 · 밴드 GW2R ④ — 기준표 없음)', () => {
  const titled = (name: string) =>
    screen.findByRole('heading', { name: AI_SETTING_TEXT.prompt.title(name) });

  it.each([
    ['데모(기본)', undefined],
    ['demos:false', false],
  ] as const)(
    '%s: /admin/ai-settings → 세션 api 로 목록 GET /ai-settings/greenwash 와 고른 판(v3) prompt-model GET 하나·대상 단어 바탕 몫 GET /13 하나(Bearer) — POST 0, 판은 서버 값, 띠 없음',
    async (_, demos) => {
      const { settings, promptModels, settingAuth } = setup(
        '/admin/ai-settings',
        {
          signedIn: 'ops.admin',
          demos,
        },
      );
      await titled('v3');
      await new Promise((done) => setTimeout(done, 20));
      expect(
        settings.count('GET /ai-settings/greenwash'),
      ).toBeGreaterThanOrEqual(1);
      expect(
        settings.calls
          .filter(
            (call) =>
              call.path !== '/ai-settings/greenwash' || call.method !== 'GET',
          )
          .map((call) => `${call.method} ${call.path}`),
      ).toEqual(['GET /ai-settings/greenwash/13']); // AS3b ①: 대상 단어 바탕 몫(판 열쇠마다 한 번)
      expect(promptModels.calls.map((call) => call.path)).toEqual([
        '/ai-settings/greenwash/13/prompt-model',
      ]);
      expect(settingAuth.length).toBeGreaterThanOrEqual(2);
      for (const auth of settingAuth) expect(auth).toMatch(/^Bearer \S+$/);
      for (const call of [...settings.calls, ...promptModels.calls])
        expect(call.query.has('companyId')).toBe(false);
      expect(screen.queryByTestId('mock-band')).toBeNull();
      expect(
        document
          .querySelector('[data-screen="admin-ai-settings"]')!
          .hasAttribute('data-can-write'),
      ).toBe(false);
    },
  );

  it('?version=v1 이면 v1 을 고른 채(바탕 몫 GET /11 하나 · v1 prompt-model 하나)', async () => {
    const { settings, promptModels } = setup('/admin/ai-settings?version=v1', {
      signedIn: 'ops.admin',
    });
    expect(await titled('v1')).toBeTruthy();
    expect(settings.count('GET /ai-settings/greenwash/11')).toBe(1);
    expect(settings.count('GET /ai-settings/greenwash/13')).toBe(0);
    expect(promptModels.calls.map((call) => call.path)).toEqual([
      '/ai-settings/greenwash/11/prompt-model',
    ]);
  });

  it.each([
    ['/admin/ai-settings', ''],
    ['/admin/ai-settings?version=v1', '?version=v1'],
    ['/admin/ai-settings?version=zz', ''],
  ])(
    '옛 주소 %s → /admin/ai-settings/greenwash(밴드 AM1 — search version 은 실어 감, replace 라 뒤로 가기에 옛 주소 없음)',
    async (path, search) => {
      const { history } = setup(path, { signedIn: 'ops.admin' });
      await atPath(history, '/admin/ai-settings/greenwash');
      expect(await titled(search ? 'v1' : 'v3')).toBeTruthy();
      expect(history.location.search).toBe(search);
      expect(history.length).toBe(1);
    },
  );

  it('옛 주소로 이동(메뉴 밖 navigate)해도 그린워싱 주소로 넘기고 그 판을 고른다(밴드 AM1)', async () => {
    const { history, router } = setup('/admin/accounts', {
      signedIn: 'ops.admin',
    });
    await screenShown('admin-accounts');
    void router.navigate({
      to: '/admin/ai-settings',
      search: { version: 'v1' },
    });
    await atPath(history, '/admin/ai-settings/greenwash');
    expect(await titled('v1')).toBeTruthy();
    expect(history.location.search).toBe('?version=v1');
  });

  it.each(['zzz'])(
    '슬롯 없는 모듈 /admin/ai-settings/%s?version=v1 → /admin/ai-settings/greenwash(replace, version 버림 — 밴드 AM1)',
    async (module) => {
      const { history } = setup(`/admin/ai-settings/${module}?version=v1`, {
        signedIn: 'ops.admin',
      });
      await atPath(history, '/admin/ai-settings/greenwash');
      expect(await titled('v3')).toBeTruthy();
      expect(history.location.search).toBe('');
      expect(history.length).toBe(1);
    },
  );

  // 밴드 TRA1: 영문번역 슬롯이 생겨 'translation' 은 넘김 목록(위 it.each)에서 켜진 쪽으로 옮겼다 — 주소 그대로·version 그대로.
  it('영문번역 /admin/ai-settings/translation?version=v1 → 넘기지 않고 영문번역 AD-02(data-module·제목·하위 줄 aria-current) · 그 판(v1) · 그린워싱 요청 0', async () => {
    const { history, settings, promptModels, trSettings, trPromptModels } =
      setup('/admin/ai-settings/translation?version=v1', {
        signedIn: 'ops.admin',
      });
    expect(await titled('v1')).toBeTruthy();
    expect(pathOf(history)).toBe('/admin/ai-settings/translation');
    expect(history.location.search).toBe('?version=v1');
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('translation');
    expect(
      screen.getByRole('heading', {
        name: AI_SETTING_TEXT.title(shell.menu.aiSettingsTranslation),
      }),
    ).toBeTruthy();
    expect(currentItems()).toEqual([
      shell.menu.aiSettings,
      shell.menu.aiSettingsTranslation,
    ]);
    // StrictMode 라 목록 읽기가 두 번일 수 있다 — 경로만 본다.
    expect(
      new Set(trSettings.calls.map((call) => `${call.method} ${call.path}`)),
    ).toEqual(new Set(['GET /ai-settings/translation']));
    expect(new Set(trPromptModels.calls.map((call) => call.path))).toEqual(
      new Set(['/ai-settings/translation/11/prompt-model']),
    );
    expect(settings.calls).toEqual([]);
    expect(promptModels.calls).toEqual([]);
  });

  it('LNB 영문번역 줄 누름 → /admin/ai-settings/translation(aria-disabled 0) · 영문번역 화면', async () => {
    const { history } = setup('/admin/accounts', { signedIn: 'ops.admin' });
    await screenShown('admin-accounts');
    const item = menuItem(shell.menu.aiSettingsTranslation);
    expect(item.hasAttribute('aria-disabled')).toBe(false);
    fireEvent.click(item);
    await atPath(history, '/admin/ai-settings/translation');
    expect(await titled('v2')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('translation');
  });

  it('감사 영문번역 링크(module translation · 판 v1) → /admin/ai-settings/translation?version=v1 · 영문번역 화면의 그 판', async () => {
    const { history, server } = setup('/admin/audit', {
      signedIn: 'ops.admin',
    });
    server.override['GET /audit-logs'] = () =>
      json(200, {
        count: 1,
        isNext: false,
        results: [
          fakeAuditRow(5, {
            action: 'setting_change',
            event: 'ai_setting_created',
            targetKind: 'ai_setting',
            targetId: 11,
            targetLabel: 'v1',
            module: 'translation',
          }),
        ],
      });
    await screenShown('admin-audit');
    const [link] = await screen.findAllByRole('link', { name: 'AI 설정' });
    expect(link!.getAttribute('href')).toBe(
      '/admin/ai-settings/translation?version=v1',
    );
    fireEvent.click(link!);
    await atPath(history, '/admin/ai-settings/translation');
    expect(await titled('v1')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('translation');
  });

  // 밴드 DVA2: 데이터 검증 슬롯이 생겨 'dataverify' 는 넘김 목록(위 it.each)에서 켜진 쪽으로 옮겼다 — 주소 그대로·version 그대로.
  it('데이터 검증 /admin/ai-settings/dataverify?version=v1 → 넘기지 않고 데이터 검증 AD-02(data-module·제목·하위 줄 aria-current) · 그 판(v1) · 그린워싱·영문번역 요청 0', async () => {
    const {
      history,
      settings,
      promptModels,
      trSettings,
      trPromptModels,
      dvSettings,
      dvPromptModels,
    } = setup('/admin/ai-settings/dataverify?version=v1', {
      signedIn: 'ops.admin',
    });
    expect(await titled('v1')).toBeTruthy();
    expect(pathOf(history)).toBe('/admin/ai-settings/dataverify');
    expect(history.location.search).toBe('?version=v1');
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('dataverify');
    expect(
      screen.getByRole('heading', {
        name: AI_SETTING_TEXT.title(shell.menu.aiSettingsDataverify),
      }),
    ).toBeTruthy();
    expect(currentItems()).toEqual([
      shell.menu.aiSettings,
      shell.menu.aiSettingsDataverify,
    ]);
    // StrictMode 라 목록 읽기가 두 번일 수 있다 — 경로만 본다.
    expect(
      new Set(dvSettings.calls.map((call) => `${call.method} ${call.path}`)),
    ).toEqual(new Set(['GET /ai-settings/dataverify']));
    expect(new Set(dvPromptModels.calls.map((call) => call.path))).toEqual(
      new Set(['/ai-settings/dataverify/11/prompt-model']),
    );
    expect(settings.calls).toEqual([]);
    expect(promptModels.calls).toEqual([]);
    expect(trSettings.calls).toEqual([]);
    expect(trPromptModels.calls).toEqual([]);
  });

  it('LNB 데이터 검증 줄 누름 → /admin/ai-settings/dataverify(aria-disabled 0) · 데이터 검증 화면', async () => {
    const { history } = setup('/admin/accounts', { signedIn: 'ops.admin' });
    await screenShown('admin-accounts');
    const item = menuItem(shell.menu.aiSettingsDataverify);
    expect(item.hasAttribute('aria-disabled')).toBe(false);
    fireEvent.click(item);
    await atPath(history, '/admin/ai-settings/dataverify');
    expect(await titled('v2')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('dataverify');
  });

  it('감사 데이터 검증 링크(module dataverify · 판 v1) → /admin/ai-settings/dataverify?version=v1 · 데이터 검증 화면의 그 판', async () => {
    const { history, server } = setup('/admin/audit', {
      signedIn: 'ops.admin',
    });
    server.override['GET /audit-logs'] = () =>
      json(200, {
        count: 1,
        isNext: false,
        results: [
          fakeAuditRow(5, {
            action: 'setting_change',
            event: 'ai_setting_created',
            targetKind: 'ai_setting',
            targetId: 11,
            targetLabel: 'v1',
            module: 'dataverify',
          }),
        ],
      });
    await screenShown('admin-audit');
    const [link] = await screen.findAllByRole('link', { name: 'AI 설정' });
    expect(link!.getAttribute('href')).toBe(
      '/admin/ai-settings/dataverify?version=v1',
    );
    fireEvent.click(link!);
    await atPath(history, '/admin/ai-settings/dataverify');
    expect(await titled('v1')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('dataverify');
  });

  it('그린워싱에서 고친 채 LNB 데이터 검증 줄 → 나가기 창 [취소] 경로 그대로 · [나가기] → 데이터 검증 화면(밴드 DVA2 — TRA1 P3 꼴)', async () => {
    const { history } = setup('/admin/ai-settings/greenwash', {
      signedIn: 'ops.admin',
    });
    expect(await titled('v3')).toBeTruthy();
    const text = within(
      document.querySelector('[data-card="prompt-slot"]') as HTMLElement,
    ).getAllByRole('textbox')[0]!;
    fireEvent.change(text, { target: { value: '지어낸 고친 글' } });
    fireEvent.click(menuItem(shell.menu.aiSettingsDataverify));
    fireEvent.click(
      within(await screen.findByTestId('leave-confirm')).getByRole('button', {
        name: AI_SETTING_TEXT.leave.cancel,
      }),
    );
    await waitFor(
      () => expect(screen.queryByTestId('leave-confirm')).toBeNull(),
      WAIT,
    );
    expect(pathOf(history)).toBe('/admin/ai-settings/greenwash');
    fireEvent.click(menuItem(shell.menu.aiSettingsDataverify));
    fireEvent.click(
      within(await screen.findByTestId('leave-confirm')).getByRole('button', {
        name: AI_SETTING_TEXT.leave.confirm,
      }),
    );
    await atPath(history, '/admin/ai-settings/dataverify');
    expect(await titled('v2')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('dataverify');
  });

  // 밴드 IRA2: 중대성평가 슬롯이 생겨 주소 그대로·version 그대로(옛 넘김 — 그린워싱).
  it('중대성평가 /admin/ai-settings/materiality?version=v1 → 넘기지 않고 중대성평가 AD-02(data-module·제목 「중대성평가 IRO」·하위 줄 aria-current) · 그 판(v1) · 다른 모듈 요청 0', async () => {
    const {
      history,
      settings,
      promptModels,
      trSettings,
      trPromptModels,
      dvSettings,
      dvPromptModels,
      msSettings,
      msPromptModels,
    } = setup('/admin/ai-settings/materiality?version=v1', {
      signedIn: 'ops.admin',
    });
    expect(await titled('v1')).toBeTruthy();
    expect(pathOf(history)).toBe('/admin/ai-settings/materiality');
    expect(history.location.search).toBe('?version=v1');
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('materiality');
    expect(
      screen.getByRole('heading', {
        name: AI_SETTING_TEXT.title(MATERIALITY_SETTING_TEXT.module.name),
      }),
    ).toBeTruthy();
    expect(currentItems()).toEqual([
      shell.menu.aiSettings,
      shell.menu.aiSettingsMateriality,
    ]);
    // StrictMode 라 목록 읽기가 두 번일 수 있다 — 경로만 본다.
    expect(
      new Set(msSettings.calls.map((call) => `${call.method} ${call.path}`)),
    ).toEqual(new Set(['GET /ai-settings/materiality']));
    expect(new Set(msPromptModels.calls.map((call) => call.path))).toEqual(
      new Set(['/ai-settings/materiality/11/prompt-model']),
    );
    for (const fake of [
      settings,
      promptModels,
      trSettings,
      trPromptModels,
      dvSettings,
      dvPromptModels,
    ])
      expect(fake.calls).toEqual([]);
  });

  it('LNB 중대성평가 줄 누름 → /admin/ai-settings/materiality(aria-disabled 0) · 중대성평가 화면', async () => {
    const { history } = setup('/admin/accounts', { signedIn: 'ops.admin' });
    await screenShown('admin-accounts');
    const item = menuItem(shell.menu.aiSettingsMateriality);
    expect(item.hasAttribute('aria-disabled')).toBe(false);
    fireEvent.click(item);
    await atPath(history, '/admin/ai-settings/materiality');
    expect(await titled('v2')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('materiality');
  });

  it('감사 중대성평가 링크(module materiality · 판 v1) → /admin/ai-settings/materiality?version=v1 · 중대성평가 화면의 그 판', async () => {
    const { history, server } = setup('/admin/audit', {
      signedIn: 'ops.admin',
    });
    server.override['GET /audit-logs'] = () =>
      json(200, {
        count: 1,
        isNext: false,
        results: [
          fakeAuditRow(5, {
            action: 'setting_change',
            event: 'ai_setting_created',
            targetKind: 'ai_setting',
            targetId: 11,
            targetLabel: 'v1',
            module: 'materiality',
          }),
        ],
      });
    await screenShown('admin-audit');
    const [link] = await screen.findAllByRole('link', { name: 'AI 설정' });
    expect(link!.getAttribute('href')).toBe(
      '/admin/ai-settings/materiality?version=v1',
    );
    fireEvent.click(link!);
    await atPath(history, '/admin/ai-settings/materiality');
    expect(await titled('v1')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('materiality');
  });

  it('데이터 검증에서 고친 채 LNB 중대성평가 줄 → 나가기 창 [취소] 경로 그대로 · [나가기] → 중대성평가 화면(밴드 IRA2 — TRA1 P3 꼴)', async () => {
    const { history } = setup('/admin/ai-settings/dataverify', {
      signedIn: 'ops.admin',
    });
    expect(await titled('v2')).toBeTruthy();
    const text = within(
      document.querySelector('[data-card="prompt-slot"]') as HTMLElement,
    ).getAllByRole('textbox')[0]!;
    fireEvent.change(text, { target: { value: '지어낸 고친 글' } });
    fireEvent.click(menuItem(shell.menu.aiSettingsMateriality));
    fireEvent.click(
      within(await screen.findByTestId('leave-confirm')).getByRole('button', {
        name: AI_SETTING_TEXT.leave.cancel,
      }),
    );
    await waitFor(
      () => expect(screen.queryByTestId('leave-confirm')).toBeNull(),
      WAIT,
    );
    expect(pathOf(history)).toBe('/admin/ai-settings/dataverify');
    fireEvent.click(menuItem(shell.menu.aiSettingsMateriality));
    fireEvent.click(
      within(await screen.findByTestId('leave-confirm')).getByRole('button', {
        name: AI_SETTING_TEXT.leave.confirm,
      }),
    );
    await atPath(history, '/admin/ai-settings/materiality');
    expect(await titled('v2')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('materiality');
  });

  // 밴드 RPA3: 보고서 작성 슬롯이 생겨 주소 그대로·version 그대로(옛 넘김 — 그린워싱).
  it('보고서 작성 /admin/ai-settings/drafting?version=v1 → 넘기지 않고 보고서 작성 AD-02(data-module·제목 「보고서 작성」·하위 줄 aria-current) · 그 판(v1) · 다른 모듈 요청 0', async () => {
    const {
      history,
      settings,
      promptModels,
      trSettings,
      trPromptModels,
      dvSettings,
      dvPromptModels,
      msSettings,
      msPromptModels,
      rpSettings,
      rpPromptModels,
    } = setup('/admin/ai-settings/drafting?version=v1', {
      signedIn: 'ops.admin',
    });
    expect(await titled('v1')).toBeTruthy();
    expect(pathOf(history)).toBe('/admin/ai-settings/drafting');
    expect(history.location.search).toBe('?version=v1');
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('drafting');
    expect(
      screen.getByRole('heading', {
        name: AI_SETTING_TEXT.title(DRAFTING_SETTING_TEXT.module.name),
      }),
    ).toBeTruthy();
    expect(currentItems()).toEqual([
      shell.menu.aiSettings,
      shell.menu.aiSettingsDrafting,
    ]);
    // StrictMode 라 목록 읽기가 두 번일 수 있다 — 경로만 본다.
    expect(
      new Set(rpSettings.calls.map((call) => `${call.method} ${call.path}`)),
    ).toEqual(new Set(['GET /ai-settings/drafting']));
    expect(new Set(rpPromptModels.calls.map((call) => call.path))).toEqual(
      new Set(['/ai-settings/drafting/11/prompt-model']),
    );
    for (const fake of [
      settings,
      promptModels,
      trSettings,
      trPromptModels,
      dvSettings,
      dvPromptModels,
      msSettings,
      msPromptModels,
    ])
      expect(fake.calls).toEqual([]);
  });

  it('LNB 보고서 작성 줄 누름 → /admin/ai-settings/drafting(aria-disabled 0) · 보고서 작성 화면', async () => {
    const { history } = setup('/admin/accounts', { signedIn: 'ops.admin' });
    await screenShown('admin-accounts');
    const item = menuItem(shell.menu.aiSettingsDrafting);
    expect(item.hasAttribute('aria-disabled')).toBe(false);
    fireEvent.click(item);
    await atPath(history, '/admin/ai-settings/drafting');
    expect(await titled('v2')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('drafting');
  });

  it('감사 보고서 작성 링크(module drafting · 판 v1 — 줄 글은 낱말 표의 「보고서 작성」, AD6) → /admin/ai-settings/drafting?version=v1 · 보고서 작성 화면의 그 판', async () => {
    const { history, server } = setup('/admin/audit', {
      signedIn: 'ops.admin',
    });
    server.override['GET /audit-logs'] = () =>
      json(200, {
        count: 1,
        isNext: false,
        results: [
          fakeAuditRow(5, {
            action: 'setting_change',
            event: 'ai_setting_created',
            targetKind: 'ai_setting',
            targetId: 11,
            targetLabel: 'v1',
            module: 'drafting',
          }),
        ],
      });
    await screenShown('admin-audit');
    const [link] = await screen.findAllByRole('link', { name: 'AI 설정' });
    expect(link!.getAttribute('href')).toBe(
      '/admin/ai-settings/drafting?version=v1',
    );
    expect(link!.closest('tr')!.textContent).toContain(
      'AI 설정 · 보고서 작성 · v1 만듦',
    );
    expect(link!.closest('tr')!.textContent).not.toContain('drafting');
    fireEvent.click(link!);
    await atPath(history, '/admin/ai-settings/drafting');
    expect(await titled('v1')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('drafting');
  });

  it('중대성평가에서 고친 채 LNB 보고서 작성 줄 → 나가기 창 [취소] 경로 그대로 · [나가기] → 보고서 작성 화면(밴드 RPA3 — TRA1 P3 꼴)', async () => {
    const { history } = setup('/admin/ai-settings/materiality', {
      signedIn: 'ops.admin',
    });
    expect(await titled('v2')).toBeTruthy();
    const text = within(
      document.querySelector('[data-card="prompt-slot"]') as HTMLElement,
    ).getAllByRole('textbox')[0]!;
    fireEvent.change(text, { target: { value: '지어낸 고친 글' } });
    fireEvent.click(menuItem(shell.menu.aiSettingsDrafting));
    fireEvent.click(
      within(await screen.findByTestId('leave-confirm')).getByRole('button', {
        name: AI_SETTING_TEXT.leave.cancel,
      }),
    );
    await waitFor(
      () => expect(screen.queryByTestId('leave-confirm')).toBeNull(),
      WAIT,
    );
    expect(pathOf(history)).toBe('/admin/ai-settings/materiality');
    fireEvent.click(menuItem(shell.menu.aiSettingsDrafting));
    fireEvent.click(
      within(await screen.findByTestId('leave-confirm')).getByRole('button', {
        name: AI_SETTING_TEXT.leave.confirm,
      }),
    );
    await atPath(history, '/admin/ai-settings/drafting');
    expect(await titled('v2')).toBeTruthy();
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('drafting');
  });

  // 발주서 0-2 P3: 경로 칸(module)만 바뀌는 이동도 useBlocker 가 막는다 — 고친 채 영문번역 줄 → 나가기 창.
  it('그린워싱에서 고친 채 LNB 영문번역 줄 → 나가기 창 [취소] 경로 그대로 · [나가기] → 영문번역 화면(고친 것 없이 새로)', async () => {
    const { history } = setup('/admin/ai-settings/greenwash', {
      signedIn: 'ops.admin',
    });
    expect(await titled('v3')).toBeTruthy();
    const text = within(
      document.querySelector('[data-card="prompt-slot"]') as HTMLElement,
    ).getAllByRole('textbox')[0]!;
    fireEvent.change(text, { target: { value: '지어낸 고친 글' } });
    fireEvent.click(menuItem(shell.menu.aiSettingsTranslation));
    const leave = await screen.findByTestId('leave-confirm');
    expect(
      within(leave).getByRole('heading', {
        name: AI_SETTING_TEXT.leave.title,
      }),
    ).toBeTruthy();
    fireEvent.click(
      within(leave).getByRole('button', { name: AI_SETTING_TEXT.leave.cancel }),
    );
    await waitFor(
      () => expect(screen.queryByTestId('leave-confirm')).toBeNull(),
      WAIT,
    );
    expect(pathOf(history)).toBe('/admin/ai-settings/greenwash');
    fireEvent.click(menuItem(shell.menu.aiSettingsTranslation));
    fireEvent.click(
      within(await screen.findByTestId('leave-confirm')).getByRole('button', {
        name: AI_SETTING_TEXT.leave.confirm,
      }),
    );
    await atPath(history, '/admin/ai-settings/translation');
    expect(await titled('v2')).toBeTruthy();
    expect(screen.queryByTestId('leave-confirm')).toBeNull();
  });

  it('/admin/ai-settings/greenwash?version=v3 → 그 판(v3), 모듈 칸 그대로', async () => {
    const { history } = setup('/admin/ai-settings/greenwash?version=v1', {
      signedIn: 'ops.admin',
    });
    expect(await titled('v1')).toBeTruthy();
    expect(pathOf(history)).toBe('/admin/ai-settings/greenwash');
    expect(history.location.search).toBe('?version=v1');
  });

  it('[테스트 비교로] 링크가 없다(sid:MARC-ISSUE-244 — 옛 「[테스트 비교로] → /admin/test-compare」 시험을 갈음)', async () => {
    setup('/admin/ai-settings', { signedIn: 'ops.admin' });
    await titled('v3');
    expect(screen.queryByRole('link', { name: /테스트 비교/ })).toBeNull();
  });
});

describe('어드민 ⑨ AD-04 실행 기록 경로(밴드 AD2 ③, 실서버 AD4R ②)', () => {
  it.each([
    ['데모(기본)', undefined],
    ['demos:false', false],
  ] as const)(
    '%s: 세션 api 로 GET /run-logs·/run-logs/metrics 를 Bearer 와 함께 부르고, 줄·지표는 서버 값, 예시 데이터 띠 없음, [엑셀 내보내기] 켬',
    async (_, demos) => {
      const { server } = setup('/admin/runs', { signedIn: 'ops.admin', demos });
      await screenShown('admin-runs');
      await screen.findByText('지어낸 보고서.pdf');
      // 서버 경로를 불렀다(StrictMode 라 효과가 두 번 돌 수 있어 1 이상)
      expect(server.count('GET /run-logs')).toBeGreaterThanOrEqual(1);
      expect(server.count('GET /run-logs/metrics')).toBeGreaterThanOrEqual(1);
      const runCalls = server.calls.filter((call) =>
        call.path.startsWith('/run-logs'),
      );
      expect(runCalls.length).toBeGreaterThanOrEqual(2);
      for (const call of runCalls)
        expect(call.authorization, call.path).toMatch(/^Bearer \S+$/);
      // 줄은 override 의 지어낸 값
      expect(
        [...document.querySelectorAll('tbody tr[data-run-id]')].map((row) =>
          row.getAttribute('data-run-id'),
        ),
      ).toEqual(['32', '31']);
      expect(document.querySelectorAll('[data-test-run]')).toHaveLength(1);
      expect(
        document.querySelectorAll('tr[data-run-id="31"] td')[5]!.textContent,
      ).toBe(RUN_LOG_TEXT.unknownUploader);
      expect(screen.getByTestId('count').textContent).toBe(
        RUN_LOG_TEXT.count(2),
      );
      expect(screen.getByTestId('metrics').textContent).toContain(
        `${RUN_LOG_TEXT.metrics.runsThisMonth}7${RUN_LOG_TEXT.metrics.times}`,
      );
      // 예시 데이터 띠는 AD-04 에서도 걷혔다
      expect(screen.queryByTestId('mock-band')).toBeNull();
      expect(
        screen
          .getByRole('button', { name: RUN_LOG_TEXT.export })
          .getAttribute('aria-disabled'),
      ).toBeNull();
      expect(
        server.calls.every((call) =>
          /^\/(auth|users|run-logs)(\/|$)/.test(call.path),
        ),
      ).toBe(true);
    },
  );

  // MP1W: 띠의 근거는 서버 지표 aiProviderMock 하나(빌드 값 배관은 걷었다 — sid:MARC-ISSUE-211).
  it.each([true, false])(
    '모의 공급사 안내 띠: 서버 지표 aiProviderMock %s → 참이면 띠, 거짓이면 0',
    async (mock) => {
      setup('/admin/runs', {
        signedIn: 'ops.admin',
        runMetrics: fakeRunMetrics({ runs: 7, aiProviderMock: mock }),
      });
      await screen.findByText('지어낸 보고서.pdf');
      await screen.findByTestId('metrics');
      if (mock)
        expect(screen.getByTestId('ai-mock-notice').textContent).toBe(
          RUN_LOG_TEXT.aiMockNotice,
        );
      else expect(screen.queryByTestId('ai-mock-notice')).toBeNull();
    },
  );
});

describe('어드민 ⑧ 운영 관리자의 그린워싱(밴드 SV1 ①, sid:MARC-ENT-286)', () => {
  // 그린워싱 머리 단추 글(GW_TEXT.shell.toAdmin). 이 시험은 그린워싱 문구 표를 가져오지 않는다(층 규칙) — 글을 그대로 적는다.
  const TO_ADMIN = '관리자 화면';
  const toAdmin = () => screen.queryByRole('button', { name: TO_ADMIN });

  it('운영 관리자 /greenwash → 목록, 머리 「운영 관리자님 안녕하세요」·[관리자 화면], 누르면 /admin/accounts(AD-01)', async () => {
    const { history } = setup('/greenwash', { signedIn: 'ops.admin' });
    await screenShown('list');
    expect(pathOf(history)).toBe('/greenwash');
    // 인사말은 어드민 머리와 같은 글(ACCOUNT_TEXT.shell.greeting).
    expect(screen.getByText(shell.greeting)).toBeTruthy();
    const button = toAdmin()!;
    expect(button).not.toBeNull();
    // 차례: 인사말 → [관리자 화면] → [로그아웃](디자인 원문 3), 단추는 md(높이 36).
    const row = screen.getByText(shell.greeting).parentElement!;
    expect([...row.children].map((node) => node.textContent)).toEqual([
      shell.greeting,
      TO_ADMIN,
      '로그아웃',
    ]);
    expect(button.className.split(/\s+/)).toContain('h-9');
    expect(button.tagName).toBe('BUTTON');
    expect(button.getAttribute('href')).toBeNull();
    fireEvent.click(button);
    await atPath(history, '/admin/accounts');
    await screenShown('admin-accounts');
  });

  it('고객사 사용자 /greenwash → [관리자 화면] 없음, 인사말은 「담당자님 안녕하세요」(운영 관리자 인사말 없음)', async () => {
    const { history } = setup('/greenwash', { signedIn: 'user01' });
    await screenShown('list');
    expect(pathOf(history)).toBe('/greenwash');
    expect(toAdmin()).toBeNull();
    expect(screen.queryByText(shell.greeting)).toBeNull();
    expect(screen.getByText('담당자님 안녕하세요')).toBeTruthy();
  });

  it('운영 관리자: AD-01 → 「서비스 화면」 → 목록 → [관리자 화면] → AD-01(어드민 칸은 화면 이동에 그대로 — 같은 객체)', async () => {
    const { history, router } = setup('/admin/accounts', {
      signedIn: 'ops.admin',
    });
    await screenShown('admin-accounts');
    const admin = router.options.context.admin;
    fireEvent.click(menuItem(shell.menu.service));
    await atPath(history, '/greenwash');
    await screenShown('list');
    fireEvent.click(toAdmin()!);
    await atPath(history, '/admin/accounts');
    await screenShown('admin-accounts');
    expect(router.options.context.admin).toBe(admin);
  });

  it('운영 관리자가 그린워싱 머리에서 [로그아웃] → revoke 한 번 → /login', async () => {
    const { history, server } = setup('/admin/accounts', {
      signedIn: 'ops.admin',
    });
    await screenShown('admin-accounts');
    fireEvent.click(menuItem(shell.menu.service));
    await screenShown('list');
    fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));
    await atPath(history, '/login');
    await screenShown('login');
    expect(server.count('POST /auth/revoke')).toBe(1);
  });

  it('운영 관리자의 첫 화면은 그대로 /admin/accounts(/ 와 /login 은 AD-01 로)', async () => {
    for (const path of ['/', '/login']) {
      const { history } = setup(path, { signedIn: 'ops.admin' });
      await atPath(history, '/admin/accounts');
      await screenShown('admin-accounts');
      cleanup();
    }
  });

  it('운영 관리자의 모르는 그린워싱 주소 /greenwash/xyz 는 첫 화면 /admin/accounts(splat 그대로)', async () => {
    const { history } = setup('/greenwash/xyz', { signedIn: 'ops.admin' });
    await atPath(history, '/admin/accounts');
    await screenShown('admin-accounts');
  });
});
