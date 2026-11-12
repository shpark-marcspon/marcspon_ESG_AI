// 어드민 틀(밴드 AD1 ①)과 AD-01 계정 관리(②)·AD-05 감사 기록(밴드 AD5R)·AD-04 실행 기록(밴드 AD4R)·AD-02 AI 설정(밴드 AD2R)을 빌드 결과에서 연다.
// 서버는 흉내(e2e/session.ts·e2e/accounts.ts·e2e/audit.ts·e2e/run-logs.ts·e2e/ai-settings.ts·e2e/ai-prompt-model.ts).
// 글자는 문구 표(ACCOUNT_TEXT·SESSION_TEXT·AUDIT_TEXT·RUN_LOG_TEXT·AI_SETTING_TEXT) 값으로 단언한다(e2e → 슬라이스의 config/text.ts 는 층 시험이 허락한 문).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { ACCOUNT_TEXT } from '../src/entities/account/config/text.ts';
import { AI_SETTING_TEXT } from '../src/entities/ai-setting/config/text.ts';
import { AUDIT_TEXT } from '../src/entities/audit-log/config/text.ts';
import { GREENWASH_SETTING_TEXT } from '../src/entities/greenwash-setting/config/text.ts';
import { RUN_LOG_TEXT } from '../src/entities/run-log/config/text.ts';
import { SESSION_TEXT } from '../src/entities/session/config/text.ts';
import { accountRow, fakeAccountsApi } from './accounts.ts';
import { PROMPT_SLOTS, fakePromptModelApi } from './ai-prompt-model.ts';
import { fakeAiSettingApi } from './ai-settings.ts';
import { auditRow, fakeAuditApi } from './audit.ts';
import {
  EXPORT_NAME,
  EXPORT_TEXT,
  FILE_TEXT,
  RUN_METRICS,
  fakeRunLogApi,
  fileUrlsOf,
  runDetail,
  runRow,
  runRowNoDocument,
} from './run-logs.ts';
import { fakeAuthApi, signIn } from './session.ts';

const words = SESSION_TEXT.login;
const shell = ACCOUNT_TEXT.shell;

const accounts = () => ({
  'ops.admin': { password: 'admin-pass-1', kind: 'admin' as const },
  user01: { password: 'service-pass-1', kind: 'service' as const },
});

async function logIn(page: Page, username: string, password: string) {
  await page.goto('/login');
  await page.getByLabel(words.username, { exact: true }).fill(username);
  await page.getByLabel(words.password, { exact: true }).fill(password);
  await page.getByRole('button', { name: words.submit, exact: true }).click();
}

const pathOf = (page: Page) => new URL(page.url()).pathname;
/** 요청 목록이 poll 로 같아진 뒤 기다리는 고요(ms) — 그 뒤 수를 다시 대 「같아진 뒤 더 오는 요청 0」(sid:MARC-ISSUE-330). */
const QUIET_MS = 500;

test('운영 관리자: 어드민 틀(관리자 메뉴·「관리자 STAFF」·인사말) → 머리 [로그아웃] → revoke → /login', async ({
  page,
}) => {
  const api = await fakeAuthApi(page, accounts());
  await logIn(page, 'ops.admin', 'admin-pass-1');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  expect(pathOf(page)).toBe('/admin/accounts');
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await expect(
    nav.getByRole('button', { name: shell.menu.accounts }),
  ).toHaveAttribute('aria-current', 'page');
  // 밴드 LN1·RPA3: 「AI 설정」 하위 줄 여섯(시안 차례 — 끝 보고서 작성), 시안 .a-subnav 값(AD-02_r3).
  const modules = nav.getByRole('list', { name: shell.aiSettingsModulesLabel });
  await expect(modules.getByRole('button')).toHaveText([
    shell.menu.aiSettingsGreenwash,
    shell.menu.aiSettingsGhg,
    shell.menu.aiSettingsMateriality,
    shell.menu.aiSettingsDataverify,
    shell.menu.aiSettingsTranslation,
    shell.menu.aiSettingsDrafting,
  ]);
  // 밴드 TRA1·DVA2·IRA2·RPA3·AD7: 영문번역·데이터 검증·중대성평가·보고서 작성·온실가스(탭 껍데기) 켬 — 꺼진 줄 0.
  await expect(modules.locator('[aria-disabled="true"]')).toHaveCount(0);
  await expect(modules).toHaveCSS('background-color', 'rgb(17, 19, 21)');
  const sub = modules.getByRole('button', {
    name: shell.menu.aiSettingsGreenwash,
  });
  await expect(sub).toHaveCSS('min-height', '32px');
  await expect(sub).toHaveCSS('padding-left', '12px');
  await expect(sub).toHaveCSS('font-size', '12px');
  await expect(sub).toHaveCSS('font-weight', '400');
  await expect(sub).toHaveCSS('color', 'rgb(176, 183, 191)');
  await expect(
    modules.getByRole('button', { name: shell.menu.aiSettingsGhg }),
  ).toHaveCSS('opacity', '1');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    `${shell.title}${shell.staff}`,
  );
  await expect(page.getByText(shell.greeting)).toBeVisible();
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await expect(page.locator('[data-screen="login"]')).toBeVisible();
  expect(pathOf(page)).toBe('/login');
  expect(api.calls).toContain('POST /auth/revoke');
});

// 밴드 WS2(sid:MARC-ISSUE-371 L18 · 시안 admin-r1.css margin-top:auto): 「서비스 화면」 줄은 LNB 맨 아래 — 줄 아래 끝 = nav 아래 끝(1px 안).
test('운영 관리자 1280×900: LNB 「서비스 화면」 줄이 메뉴 맨 아래(줄 아래 끝 = nav 아래 끝)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await fakeAuthApi(page, accounts());
  await logIn(page, 'ops.admin', 'admin-pass-1');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  const service = nav.getByRole('button', { name: shell.menu.service });
  const audit = nav.getByRole('button', { name: shell.menu.audit });
  const navBox = (await nav.boundingBox())!;
  const serviceBox = (await service.boundingBox())!;
  const auditBox = (await audit.boundingBox())!;
  expect(navBox.height).toBeGreaterThanOrEqual(900 - 1);
  expect(
    Math.abs(serviceBox.y + serviceBox.height - (navBox.y + navBox.height)),
  ).toBeLessThanOrEqual(1);
  // 위 「감사 기록」 줄과 붙어 있지 않다(그 사이가 「온실가스 인덱스」·「선택항목」 줄과 빈 자리 — W12-0a ③·W12-0b1 ③, 1280×900 실측 374).
  expect(serviceBox.y - (auditBox.y + auditBox.height)).toBeGreaterThan(100);
});

// 밴드 WS3(sid:MARC-TICK-335): LNB 는 화면 높이에 고정(sticky) — 문서를 끝까지 스크롤해도 「서비스 화면」 줄이 왼쪽 아래에 보인다.
// 본문이 화면보다 긴 상태는 시험 안에서 main 높이를 늘려 만든다(화면마다 자료 길이가 달라서).
test('운영 관리자 1280×900: 문서를 끝까지 스크롤해도 LNB 는 위 끝 0 · 아래 끝 900, 「서비스 화면」 줄이 화면 안', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await fakeAuthApi(page, accounts());
  await logIn(page, 'ops.admin', 'admin-pass-1');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  await page
    .locator('[data-app-shell] > main')
    .evaluate((main) => (main.style.minHeight = '3000px'));
  await page.evaluate(() =>
    window.scrollTo(0, document.documentElement.scrollHeight),
  );
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(1000);
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  const service = nav.getByRole('button', { name: shell.menu.service });
  const navBox = (await nav.boundingBox())!;
  const serviceBox = (await service.boundingBox())!;
  expect(Math.abs(navBox.y)).toBeLessThanOrEqual(1);
  expect(Math.abs(navBox.y + navBox.height - 900)).toBeLessThanOrEqual(1);
  expect(serviceBox.y).toBeGreaterThanOrEqual(0);
  expect(serviceBox.y + serviceBox.height).toBeLessThanOrEqual(900 + 1);
  expect(
    Math.abs(serviceBox.y + serviceBox.height - (navBox.y + navBox.height)),
  ).toBeLessThanOrEqual(1);
});

test('운영 관리자 1280×500: 메뉴가 화면보다 길면 nav 안에서 스크롤해 「서비스 화면」 줄에 닿는다', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 500 });
  await fakeAuthApi(page, accounts());
  await logIn(page, 'ops.admin', 'admin-pass-1');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  const service = nav.getByRole('button', { name: shell.menu.service });
  const navBox = (await nav.boundingBox())!;
  expect(Math.abs(navBox.height - 500)).toBeLessThanOrEqual(1);
  // 메뉴가 화면보다 길다 — 그래서 nav 안 스크롤이 생긴다.
  const sizes = await nav.evaluate((element) => ({
    scroll: element.scrollHeight,
    client: element.clientHeight,
  }));
  expect(sizes.scroll).toBeGreaterThan(sizes.client);
  await service.scrollIntoViewIfNeeded();
  expect(await nav.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  const serviceBox = (await service.boundingBox())!;
  expect(serviceBox.y).toBeGreaterThanOrEqual(0);
  expect(serviceBox.y + serviceBox.height).toBeLessThanOrEqual(500 + 1);
});

test('고객사 사용자: 그린워싱 틀 머리 [로그아웃] → revoke → /login', async ({
  page,
}) => {
  const api = await fakeAuthApi(page, accounts());
  await logIn(page, 'user01', 'service-pass-1');
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await expect(page.locator('[data-screen="login"]')).toBeVisible();
  expect(api.calls).toContain('POST /auth/revoke');
});

/** 임시 비밀번호가 쪽 어디에도 남지 않았는가(DOM·sessionStorage·localStorage·URL). */
async function leftovers(page: Page, secret: string) {
  return page.evaluate(
    (value) => ({
      dom: document.documentElement.outerHTML.includes(value),
      inputs: [...document.querySelectorAll('input')].some(
        (input) => input.value === value,
      ),
      session: Object.values({ ...sessionStorage }).some((item) =>
        item.includes(value),
      ),
      local: Object.values({ ...localStorage }).some((item) =>
        item.includes(value),
      ),
      url: location.href.includes(value),
    }),
    secret,
  );
}
const none = {
  dom: false,
  inputs: false,
  session: false,
  local: false,
  url: false,
};

test('AD-01: 목록 → [계정 만들기] → 409 글 → 다른 아이디로 만들기 → AD-01b(12자, 요청 본문과 같음) → [확인] 뒤 어디에도 없음', async ({
  page,
}) => {
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const api = await fakeAccountsApi(page, [
    accountRow(1),
    accountRow(2, { isLocked: true }),
  ]);
  await page.goto('/admin/accounts');
  await expect(
    page.getByRole('cell', { name: 'user01', exact: true }),
  ).toBeVisible();
  await expect(page.getByText(ACCOUNT_TEXT.list.description(2))).toBeVisible();
  await expect(
    page.locator('[data-status]', { hasText: ACCOUNT_TEXT.status.locked }),
  ).toBeVisible();

  await page.getByRole('button', { name: ACCOUNT_TEXT.list.create }).click();
  const dialog = page.getByRole('dialog');
  const words = ACCOUNT_TEXT.create;
  await dialog.getByRole('textbox', { name: words.username }).fill('user01');
  await dialog.getByRole('textbox', { name: words.name }).fill('담당자 G');
  await dialog.getByRole('button', { name: words.submit }).click();
  await expect(dialog.getByText(words.taken)).toBeVisible();
  await dialog.getByRole('textbox', { name: words.username }).fill('user07');
  await dialog.getByRole('button', { name: words.submit }).click();

  const field = dialog.getByRole('textbox', {
    name: ACCOUNT_TEXT.password.label,
  });
  await expect(field).toBeVisible();
  const secret = await field.inputValue();
  expect(secret).toHaveLength(12);
  expect(api.writes.at(-1)).toMatchObject({
    username: 'user07',
    name: '담당자 G',
    password: secret,
  });
  await expect(
    dialog.getByRole('button', { name: ACCOUNT_TEXT.password.copy }),
  ).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(field).toBeVisible();
  await dialog
    .getByRole('button', { name: ACCOUNT_TEXT.password.confirm })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(
    page.getByRole('cell', { name: 'user07', exact: true }),
  ).toBeVisible();
  expect(await leftovers(page, secret)).toEqual(none);
});

test('AD-01: 줄의 [초기화] → 확인 → AD-01b → [확인] 뒤 어디에도 없음', async ({
  page,
}) => {
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const api = await fakeAccountsApi(page, [accountRow(1), accountRow(2)]);
  await page.goto('/admin/accounts');
  await page
    .getByRole('button', { name: ACCOUNT_TEXT.list.resetLabel('user02') })
    .click();
  const dialog = page.getByRole('dialog');
  await expect(
    dialog.getByText(ACCOUNT_TEXT.reset.title('user02')),
  ).toBeVisible();
  await dialog.getByRole('button', { name: ACCOUNT_TEXT.reset.submit }).click();
  const field = dialog.getByRole('textbox', {
    name: ACCOUNT_TEXT.password.label,
  });
  await expect(field).toBeVisible();
  const secret = await field.inputValue();
  expect(api.calls).toContain('POST /users/2/password-reset');
  expect(api.writes.at(-1)).toEqual({ password: secret });
  await dialog
    .getByRole('button', { name: ACCOUNT_TEXT.password.confirm })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(await leftovers(page, secret)).toEqual(none);
});

test('AD-01c 실서버(UA1W): 고르고 [사용 중지] → 확인 → PATCH /api/users/2 {isActive:false} → 배지 「사용 중지」. 이름 고침 Enter → PATCH {name}. 공백만 검색 → 「상태: 잠김」 요청에 status=locked·q 없음', async ({
  page,
}) => {
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const api = await fakeAccountsApi(page, [accountRow(1), accountRow(2)]);
  await page.goto('/admin/accounts');
  const list = ACCOUNT_TEXT.list;
  await expect(page.getByText('준비 중')).toHaveCount(0);
  await page.getByRole('checkbox', { name: list.select('user02') }).click();
  await page
    .getByRole('button', { name: list.deactivate, exact: true })
    .click();
  const dialog = page.getByRole('dialog');
  await expect(
    dialog.getByText(ACCOUNT_TEXT.active.deactivateTitle(1)),
  ).toBeVisible();
  await dialog
    .getByRole('button', { name: ACCOUNT_TEXT.active.deactivate })
    .click();
  const row = page.locator('tr', {
    has: page.getByRole('cell', { name: 'user02', exact: true }),
  });
  await expect(row.locator('[data-status]')).toHaveText(
    ACCOUNT_TEXT.status.inactive,
  );
  expect(api.patches).toEqual([{ id: 2, body: '{"isActive":false}' }]);

  await page.getByRole('button', { name: list.editName('user01') }).click();
  const input = page.getByRole('textbox', {
    name: list.nameLabel,
    exact: true,
  });
  await input.fill('재무팀');
  await input.press('Enter');
  await expect(
    page.getByRole('button', { name: list.editName('user01') }),
  ).toHaveText('재무팀');
  expect(api.patches.at(-1)).toEqual({ id: 1, body: '{"name":"재무팀"}' });
  expect(api.writes).toEqual([]);

  await page.getByLabel(list.searchLabel).fill('   ');
  const before = api.queries.length;
  await page
    .getByRole('combobox', { name: list.statusLabel })
    .selectOption('locked');
  await expect
    .poll(() =>
      api.queries
        .slice(before)
        .some((query) => query.get('status') === 'locked'),
    )
    .toBe(true);
  for (const query of api.queries.slice(before))
    expect(query.has('q')).toBe(false);
});

/** 고르기 칸(키트 dropdown-menu)을 열고 값 하나를 고른 뒤 메뉴가 닫히기를 기다린다(admin-mock.spec.ts 와 같은 꼴 — 닫히는 메뉴가 남은 채 다시 열지 않게). */
async function choose(page: Page, name: string, option: string) {
  await page.getByRole('button', { name }).click();
  await page.getByRole('menuitemradio', { name: option, exact: true }).click();
  await expect(page.getByRole('menu')).toHaveCount(0);
}

test('AD-05 감사 기록: 메뉴로 열기 → /api/audit-logs?·/actors 요청 → 띠 없음·줄 → 공백만 검색 → 「행동: 로그인」 요청에 action=login·q 없음 → 줄 셈 → 「계정」 → AD-01', async ({
  page,
}) => {
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const audit = await fakeAuditApi(
    page,
    [
      auditRow(3, {
        at: '2026-10-15T16:02:00+09:00',
        actorKind: 'admin',
        actorUserId: 1,
        actorName: '지어낸 관리자',
        actorUsername: 'ops.admin',
        companyId: null,
        action: 'setting_change',
        event: 'user_created',
        targetKind: 'user',
        targetId: 12,
        targetLabel: 'user12',
      }),
      auditRow(2, { at: '2026-10-15T15:00:00+09:00' }),
      auditRow(1, {
        at: '2026-10-15T14:00:00+09:00',
        result: 'failure',
        reason: 'wrong_password',
        event: 'login_failed',
      }),
    ],
    [
      {
        actorKind: 'service',
        actorUserId: 11,
        actorName: '지어낸 담당자',
        actorUsername: 'user11',
      },
    ],
  );
  await fakeAccountsApi(page, [accountRow(1)]);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  expect(audit.urls).toEqual([]);
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await nav.getByRole('button', { name: shell.menu.audit }).click();
  await expect(page.locator('[data-screen="admin-audit"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/audit');
  await expect(page.locator('tr[data-audit-id]')).toHaveCount(3);
  await expect(page.getByTestId('count')).toHaveText(AUDIT_TEXT.count(3));
  expect(audit.listUrls().length).toBeGreaterThanOrEqual(1);
  expect(audit.listUrls()[0]!.search).toMatch(/^\?/);
  expect(audit.listUrls()[0]!.searchParams.get('dateTo')).toMatch(
    /^\d{4}-\d{2}-\d{2}$/,
  );
  expect(audit.listUrls()[0]!.searchParams.has('companyId')).toBe(false);
  expect(
    audit.urls.some((url) => url.pathname === '/api/audit-logs/actors'),
  ).toBe(true);
  await expect(page.getByTestId('mock-band')).toHaveCount(0);

  // 공백만 든 검색 → 그 뒤 나간 요청에 q 가 없다(행동을 바꿔 요청을 낸다 — 요청이 안 나가는 빈 통과를 막는다).
  // 거르기를 바꾸면 화면이 칸의 글(공백)을 기다리지 않고 바로 쿼리에 싣는다 — 정해진 시간 대기 없이 그 요청을 본다.
  await page.getByLabel(AUDIT_TEXT.searchLabel).fill('   ');
  const before = audit.listUrls().length;
  await choose(page, AUDIT_TEXT.action.name, AUDIT_TEXT.actions.login);
  await expect(page.locator('tr[data-audit-id]')).toHaveCount(2);
  const after = audit.listUrls().slice(before);
  expect(after.length).toBeGreaterThanOrEqual(1);
  for (const url of after) {
    expect(url.searchParams.get('action')).toBe('login');
    expect(url.searchParams.has('q')).toBe(false);
  }
  await expect(page.getByTestId('count')).toHaveText(AUDIT_TEXT.count(2));

  await choose(page, AUDIT_TEXT.action.name, AUDIT_TEXT.action.all);
  await expect(page.locator('tr[data-audit-id]')).toHaveCount(3);
  await page.getByRole('link', { name: '계정' }).click();
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/accounts');
});

test('AD-04 실행 기록: 메뉴로 열기 → /api/run-logs?·/metrics 요청 → 띠 없음·안내 띠·지표·줄 → 공백만 검색 → 「상태: 실패」 요청에 status=failed·q 없음 → 줄 셈', async ({
  page,
}) => {
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const runs = await fakeRunLogApi(page, [
    runRow(3, { createdAt: '2026-10-15T16:02:00+09:00', isTest: true }),
    runRow(2, {
      createdAt: '2026-10-15T15:00:00+09:00',
      module: 'dataverify',
      status: 'failed',
    }),
    runRow(1, {
      createdAt: '2026-10-15T14:00:00+09:00',
      status: 'queued',
      startedAt: null,
      finishedAt: null,
      durationSec: null,
      createdByName: null,
      createdByUsername: null,
    }),
  ]);
  await fakeAccountsApi(page, [accountRow(1)]);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  expect(runs.urls).toEqual([]);
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await nav.getByRole('button', { name: shell.menu.runs }).click();
  await expect(page.locator('[data-screen="admin-runs"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/runs');
  await expect(page.locator('tr[data-run-id]')).toHaveCount(3);
  await expect(page.getByTestId('count')).toHaveText(RUN_LOG_TEXT.count(3));
  expect(runs.listUrls().length).toBeGreaterThanOrEqual(1);
  const first = runs.listUrls()[0]!;
  expect(first.searchParams.get('dateFrom')).toMatch(/^\d{4}-\d{2}-01$/);
  expect(first.searchParams.get('dateTo')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(first.searchParams.get('limit')).toBe('50');
  expect(first.searchParams.get('offset')).toBe('0');
  expect(first.searchParams.has('companyId')).toBe(false);
  expect(
    runs.urls.some((url) => url.pathname === '/api/run-logs/metrics'),
  ).toBe(true);
  await expect(page.getByTestId('mock-band')).toHaveCount(0);
  // 흉내 지표 aiProviderMock 참 → 안내 띠(MP1W — 빌드 값이 아니라 서버 지표).
  await expect(page.getByTestId('ai-mock-notice')).toHaveText(
    RUN_LOG_TEXT.aiMockNotice,
  );
  await expect(page.getByTestId('metrics')).toContainText('3.1M');
  await expect(page.getByText(RUN_LOG_TEXT.foot)).toBeVisible();

  // 공백만 든 검색 → 그 뒤 나간 요청에 q 가 없다(상태를 바꿔 요청을 낸다 — 요청이 안 나가는 빈 통과를 막는다).
  await page.getByLabel(RUN_LOG_TEXT.searchLabel).fill('   ');
  const before = runs.listUrls().length;
  await choose(
    page,
    RUN_LOG_TEXT.status.name,
    RUN_LOG_TEXT.status.options.failed,
  );
  await expect(page.locator('tr[data-run-id]')).toHaveCount(1);
  const after = runs.listUrls().slice(before);
  expect(after.length).toBeGreaterThanOrEqual(1);
  for (const url of after) {
    expect(url.searchParams.get('status')).toBe('failed');
    expect(url.searchParams.has('q')).toBe(false);
  }
  await expect(page.getByTestId('count')).toHaveText(RUN_LOG_TEXT.count(1));

  await choose(page, RUN_LOG_TEXT.status.name, RUN_LOG_TEXT.status.options.all);
  await expect(page.locator('tr[data-run-id]')).toHaveCount(3);
});

test('AD-02 모듈 주소(밴드 AM1): 하위 줄 「그린워싱」 누름 → /admin/ai-settings/greenwash · 옛 /admin/ai-settings?version=v1 → 그린워싱 주소(판 실림) · 뒤로 가기에 옛 주소 없음 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAiSettingApi(page);
  await fakePromptModelApi(page);
  await fakeAccountsApi(page, [accountRow(1)]);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await nav
    .getByRole('button', { name: shell.menu.aiSettingsGreenwash })
    .click();
  await expect(page.locator('[data-screen="admin-ai-settings"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/ai-settings/greenwash');
  await page.goto('/admin/ai-settings?version=v1');
  await expect(
    page.getByRole('heading', { name: AI_SETTING_TEXT.prompt.title('v1') }),
  ).toBeVisible();
  expect(pathOf(page)).toBe('/admin/ai-settings/greenwash');
  expect(new URL(page.url()).search).toBe('?version=v1');
  await page.goBack();
  await expect(page.locator('[data-screen="admin-ai-settings"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/ai-settings/greenwash');
  expect(new URL(page.url()).search).toBe('');
  expect(unrouted).toEqual([]);
});

test('AD-02 AI 설정(실서버 AD2R · 모듈 슬롯·prompt-model AD2W ②): 메뉴로 열기 → 목록 GET 하나 + 고른 판 prompt-model GET(/13·/12·/default — 판마다 한 번) → 띠·기준표·[테스트 비교로] 없음 → 모델·칸 넷·고정 값 → 「고정 규칙」 카드 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const p = AI_SETTING_TEXT.prompt;
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const settings = await fakeAiSettingApi(page);
  const models = await fakePromptModelApi(page);
  await fakeAccountsApi(page, [accountRow(1)]);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  expect(settings.calls).toEqual([]);
  expect(models.calls).toEqual([]);
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await nav.getByRole('button', { name: shell.menu.aiSettings }).click();
  await expect(page.locator('[data-screen="admin-ai-settings"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/ai-settings/greenwash');
  await expect(
    page.getByRole('heading', { name: p.title('v3') }),
  ).toBeVisible();
  const [list] = settings.sent('GET', '');
  expect(Object.fromEntries(list!.url.searchParams)).toEqual({
    limit: '100',
    offset: '0',
  });
  await expect(page.getByTestId('mock-band')).toHaveCount(0);
  // 기준표 카드·표·스위치가 없고, [테스트 비교로] 링크도 없다
  await expect(
    page.locator('[data-card="criteria"], table, [role="switch"]'),
  ).toHaveCount(0);
  await expect(page.getByRole('link', { name: /테스트 비교/ })).toHaveCount(0);
  // 판 줄 「v3 · 이름」, 흐름 띠 마디 넷(흉내 label — AS3b ② 셋째 열을 갈음), 모델 「지어낸 미니」
  await expect(page.locator('[data-version="13"]')).toHaveText(
    'v3 · 지어낸 판 셋',
  );
  const steps = page.getByRole('region', {
    name: GREENWASH_SETTING_TEXT.flow.title,
  }); // AS3b ②: 셋째 열 대신 처리 흐름 띠 마디
  await expect
    .poll(() =>
      steps
        .locator('[data-flow-key]')
        .evaluateAll((nodes) =>
          nodes.map((node) => node.getAttribute('aria-label')),
        ),
    )
    .toEqual(
      PROMPT_SLOTS.map(([, label], index) =>
        GREENWASH_SETTING_TEXT.flow.nodeLabel(index + 1, label, false),
      ),
    );
  const components = page.getByRole('region', {
    name: AI_SETTING_TEXT.columns.component,
  });
  await components.getByRole('button', { name: /^모델 설정/ }).click();
  await expect(page.locator('[data-card="model"]')).toContainText(
    '지어낸 미니',
  );
  await page.locator('[data-version="12"]').click();
  await expect(page.locator('[data-card="model"]')).toBeVisible();
  await components.getByRole('button', { name: /^프롬프트/ }).click();
  await expect(
    page.getByRole('heading', { name: p.title('v2') }),
  ).toBeVisible();
  await page.locator('[data-version="default"]').click();
  await expect(
    page.getByRole('heading', { name: p.title('기본 설정') }),
  ).toBeVisible();
  await expect(
    page.locator('[data-version="default"]').locator('xpath=..'),
  ).toContainText(AI_SETTING_TEXT.status.default);
  await page.locator('[data-version="13"]').click();
  await expect(
    page.getByRole('heading', { name: p.title('v3') }),
  ).toBeVisible();
  await components.getByRole('button', { name: /^처리 값/ }).click();
  await expect(page.locator('[data-card="fixed"]')).toContainText(
    AI_SETTING_TEXT.fixedNote,
  );
  await components.getByRole('button', { name: /^고정 규칙/ }).click();
  await expect(page.getByTestId('fixed-rules')).toContainText(
    GREENWASH_SETTING_TEXT.module.codeRules.foot,
  );
  // 요청: 목록 GET 하나 + 판마다 prompt-model 하나(v3 를 다시 골라도 0) + 대상 단어 바탕 몫 판마다 하나(/13·/12·/default — AS3b ①)·POST 0
  await expect
    .poll(() =>
      settings.calls.map((call) => `${call.method} ${call.url.pathname}`),
    )
    .toEqual([
      'GET /api/ai-settings/greenwash',
      'GET /api/ai-settings/greenwash/13',
      'GET /api/ai-settings/greenwash/12',
      'GET /api/ai-settings/greenwash/default',
    ]);
  expect(models.paths()).toEqual([
    '/13/prompt-model',
    '/12/prompt-model',
    '/default/prompt-model',
  ]);
  // 같아진 뒤 더 오는 요청 0: 고요 뒤 수를 다시 댄다(sid:MARC-ISSUE-330)
  await page.waitForTimeout(QUIET_MS);
  expect(settings.calls).toHaveLength(4);
  expect(models.paths()).toHaveLength(3);
  for (const call of [...settings.calls, ...models.calls])
    expect(call.url.searchParams.has('companyId')).toBe(false);
  expect(unrouted).toEqual([]);
});

test('AD-02 적용(실서버 AD2R): v3 [이 버전 적용] → 확인 → PUT /applied {id:13} → v3 「적용 중」, POST 0(밴드 GW2R ④ — 옛 「쓰기: 저장 → 새 판」 시험을 갈음)', async ({
  page,
}) => {
  const p = AI_SETTING_TEXT.prompt;
  const apply = AI_SETTING_TEXT.applyDialog;
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const settings = await fakeAiSettingApi(page);
  await fakePromptModelApi(page);
  await page.goto('/admin/ai-settings');
  await expect(
    page.getByRole('heading', { name: p.title('v3') }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: AI_SETTING_TEXT.apply, exact: true })
    .click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading')).toHaveText(apply.title('v3'));
  expect(settings.sent('PUT', '/applied')).toHaveLength(0);
  const put = page.waitForRequest(
    (request) =>
      request.method() === 'PUT' &&
      new URL(request.url()).pathname === '/api/ai-settings/greenwash/applied',
  );
  await dialog
    .getByRole('button', { name: apply.confirm, exact: true })
    .click();
  expect((await put).postDataJSON()).toEqual({ id: 13 });
  await expect(dialog).toHaveCount(0);
  await expect(
    page.locator('[data-version="13"]').locator('xpath=..'),
  ).toContainText(AI_SETTING_TEXT.status.applied);
  await expect(page.getByTestId('notice')).toHaveText(apply.done('v3'));
  expect(settings.sent('POST', '')).toHaveLength(0);
  expect(settings.sent('PUT', '/applied')).toHaveLength(1);
});

test('AD-02 한 번 저장(AD2W ③④): 모델 출력 상한 고침 → 「고친 것 1개」 → 판정 칸 글·메모 → 「2개」 → [이 버전 적용] 눌러도 PUT 0·창 0 → 다른 판·메뉴 「실행 기록」 → 나가기 창 [취소] → 이름 빔 [저장]·Enter POST 0 → [저장] 빠르게 두 번 → GET /13 + POST 정확히 하나(본문 다섯 칸, 칸 넷 중 판정만 고친 글) → 목록 → v4 고름·/14/prompt-model · 알림 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const t = AI_SETTING_TEXT;
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const settings = await fakeAiSettingApi(page);
  const models = await fakePromptModelApi(page);
  await page.goto('/admin/ai-settings');
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v3') }),
  ).toBeVisible();
  const components = page.getByRole('region', {
    name: t.columns.component,
  });
  await components.getByRole('button', { name: /^모델 설정/ }).click();
  await page
    .getByRole('textbox', { name: t.model.maxOutputTokens })
    .fill('3000');
  const bar = page.getByTestId('save-bar');
  await expect(bar).toContainText(t.saveBar.count(1));
  // ④: 판정 칸(둘째) 글·메모 고침 → 고친 것 2개(모델 1 · 칸 1)
  await components.getByRole('button', { name: /^프롬프트/ }).click();
  await page
    .getByRole('region', { name: GREENWASH_SETTING_TEXT.flow.title })
    .getByRole('button', {
      name: GREENWASH_SETTING_TEXT.flow.nodeLabel(2, '지어낸 판정', false),
    })
    .click();
  await page
    .getByRole('textbox', { name: `지어낸 판정 ${t.prompt.text}` })
    .fill('지어낸 고친 판정 글');
  await page
    .getByRole('textbox', { name: `지어낸 판정 ${t.prompt.memo}` })
    .fill('지어낸 고친 이유');
  await expect(bar).toContainText(t.saveBar.count(2));
  await expect(
    page.locator('[data-version="13"]').locator('xpath=../..'),
  ).toContainText(t.editingSum('v3'));
  // 끈 [이 버전 적용]: 눌러도 창 0·PUT 0
  const applyButton = page.getByRole('button', { name: t.apply, exact: true });
  await expect(applyButton).toHaveAttribute('aria-disabled', 'true');
  await applyButton.click({ force: true });
  await expect(page.getByRole('dialog')).toHaveCount(0);
  // 고친 채 다른 판 → 나가기 창 [취소] 그대로
  await page.locator('[data-version="12"]').click();
  const leave = page.getByTestId('leave-confirm');
  await expect(leave.getByRole('heading')).toHaveText(t.leave.title);
  await leave
    .getByRole('button', { name: t.leave.cancel, exact: true })
    .click();
  await expect(leave).toHaveCount(0);
  await expect(bar).toBeVisible();
  // 메뉴 이동(라우터 useBlocker) → 같은 나가기 창 [취소] — 경로 그대로
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await nav.getByRole('button', { name: shell.menu.runs }).click();
  await expect(leave.getByRole('heading')).toHaveText(t.leave.title);
  await leave
    .getByRole('button', { name: t.leave.cancel, exact: true })
    .click();
  await expect(leave).toHaveCount(0);
  expect(pathOf(page)).toBe('/admin/ai-settings/greenwash');
  await expect(bar).toBeVisible();
  // 이름 빔 → [저장] 끔: 누름·Enter 모두 POST 0
  await bar.getByRole('button', { name: t.saveBar.save }).click();
  const dialog = page.getByTestId('save-dialog');
  await expect(dialog.getByTestId('save-changes')).toHaveText(
    [t.changed.model, t.prompt.slot(2, '지어낸 판정')].join(t.changed.join),
  );
  await expect(dialog.getByTestId('save-number')).toHaveText('v4');
  const confirm = dialog.getByRole('button', {
    name: t.save.confirm,
    exact: true,
  });
  await expect(confirm).toHaveAttribute('aria-disabled', 'true');
  await confirm.click({ force: true });
  const name = dialog.getByRole('textbox', { name: t.save.name });
  await name.press('Enter');
  await expect(dialog.getByTestId('name-error')).toHaveText(t.save.nameEmpty);
  expect(settings.sent('POST', '')).toHaveLength(0);
  // 이름 → [저장] 빠르게 두 번 → POST 정확히 하나
  await name.fill('지어낸 새 판');
  await dialog
    .getByRole('textbox', { name: t.save.memo })
    .fill('지어낸 판 메모');
  await confirm.dblclick();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('notice')).toHaveText(t.save.done('v4'));
  const posts = settings.sent('POST', '');
  expect(posts).toHaveLength(1);
  const body = posts[0]!.body as {
    title: string;
    memo: string;
    criteria: { version: string; rows: unknown[] };
    modelSettings: unknown;
    prompts: {
      steps: {
        key: string;
        prompts: { key: string; text: string; memo: string }[];
      }[];
    };
  };
  expect(Object.keys(body).sort()).toEqual([
    'criteria',
    'memo',
    'modelSettings',
    'prompts',
    'terms',
    'title',
  ]);
  expect(Reflect.get(body, 'terms')).toEqual([
    { text: '지어낸 초록낱말', enabled: true },
    { text: '친환경', enabled: false },
  ]); // G2d: 바탕 판 13 의 대상 단어 그대로
  expect(body.title).toBe('지어낸 새 판');
  expect(body.memo).toBe('지어낸 판 메모');
  expect(body.criteria.version).toBe('v3');
  expect(body.criteria.rows).toHaveLength(15);
  expect(body.modelSettings).toEqual({
    steps: [
      {
        key: 'judge',
        route: 'fake-mini',
        temperature: 0.2,
        maxOutputTokens: 3000,
        webSearch: false,
      },
    ],
  });
  expect(body.prompts.steps.map((step) => step.key)).toEqual(['judge']);
  expect(body.prompts.steps[0]!.prompts).toEqual(
    PROMPT_SLOTS.map(([key]) =>
      key === 'eval' ?
        { key, text: '지어낸 고친 판정 글', memo: '지어낸 고친 이유' }
      : {
          key,
          text: `지어낸 ${key} 기본 글\n[출력(JSON)]\n{"지어낸칸": "값"}`,
          memo: `지어낸 ${key} 메모`,
        },
    ),
  );
  // 새 판 v4 가 골라지고 그 판의 prompt-model 을 받는다(outputKept 는 저장 답에 없다)
  await expect(page.locator('[data-version="14"]')).toHaveText(
    'v4 · 지어낸 새 판',
  );
  await expect(bar).toHaveCount(0);
  await expect
    .poll(() => models.paths())
    .toEqual(['/13/prompt-model', '/14/prompt-model']);
  // 요청 차례: 목록 → 대상 단어 바탕 몫 GET /13(AS3b ①) → (저장) 바탕 판 GET /13 → POST → 목록 → 새 판 바탕 몫 GET /14
  await expect
    .poll(() =>
      settings.calls.map((call) => `${call.method} ${call.url.pathname}`),
    )
    .toEqual([
      'GET /api/ai-settings/greenwash',
      'GET /api/ai-settings/greenwash/13',
      'GET /api/ai-settings/greenwash/13',
      'POST /api/ai-settings/greenwash',
      'GET /api/ai-settings/greenwash',
      'GET /api/ai-settings/greenwash/14',
    ]);
  // 같아진 뒤 더 오는 요청 0: 고요 뒤 수를 다시 댄다(sid:MARC-ISSUE-330)
  await page.waitForTimeout(QUIET_MS);
  expect(settings.calls).toHaveLength(6);
  expect(models.paths()).toHaveLength(2);
  expect(settings.sent('PUT', '/applied')).toHaveLength(0);
  expect(unrouted).toEqual([]);
});

test('AD-02 나가기(AD2W ③): 고친 채 [나가기] 는 그 판으로 · 메뉴 이동 [나가기] 는 그 화면으로 · 창 닫기·새로고침은 막지 않음(beforeunload 대화창 0)', async ({
  page,
}) => {
  const t = AI_SETTING_TEXT;
  const dialogs: string[] = [];
  page.on('dialog', (dialog) => {
    dialogs.push(dialog.type());
    void dialog.dismiss();
  });
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAiSettingApi(page);
  await fakePromptModelApi(page);
  await fakeRunLogApi(page, [runRow(1)]);
  await page.goto('/admin/ai-settings');
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v3') }),
  ).toBeVisible();
  const components = page.getByRole('region', { name: t.columns.component });
  const editTokens = async () => {
    await components.getByRole('button', { name: /^모델 설정/ }).click();
    await page
      .getByRole('textbox', { name: t.model.maxOutputTokens })
      .fill('3000');
    await expect(page.getByTestId('save-bar')).toBeVisible();
  };
  await editTokens();
  await page.locator('[data-version="12"]').click();
  const leave = page.getByTestId('leave-confirm');
  await leave
    .getByRole('button', { name: t.leave.confirm, exact: true })
    .click();
  await expect(page.getByTestId('save-bar')).toHaveCount(0);
  await expect(
    page.locator('[data-version="12"]').locator('xpath=../..'),
  ).toHaveAttribute('aria-pressed', 'true');
  await editTokens();
  await page.reload();
  await expect(page.locator('[data-screen="admin-ai-settings"]')).toBeVisible();
  expect(dialogs).toEqual([]);
  await editTokens();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await nav.getByRole('button', { name: shell.menu.runs }).click();
  await leave
    .getByRole('button', { name: t.leave.confirm, exact: true })
    .click();
  await expect(page.locator('[data-screen="admin-runs"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/runs');
  expect(dialogs).toEqual([]);
});

test('AD-02 저장 중 뒤로가기(AD2S ①): POST 가 도는 동안 뒤로가기 → 나가기 창 0 · 저장되면 그대로 떠남, 실패하면 그때 나가기 창 → [나가기] 떠남 · POST 둘 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const t = AI_SETTING_TEXT;
  const unrouted = await trapUnrouted(page);
  const dialogs: string[] = [];
  page.on('dialog', (dialog) => {
    dialogs.push(dialog.type());
    void dialog.dismiss();
  });
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const settings = await fakeAiSettingApi(page, { gatePost: true });
  await fakePromptModelApi(page);
  await fakeRunLogApi(page, [runRow(1)]);
  // 실행 기록에서 메뉴로 들어온다(뒤로 갈 기록을 만든다)
  await page.goto('/admin/runs');
  await expect(page.locator('[data-screen="admin-runs"]')).toBeVisible();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  const components = page.getByRole('region', { name: t.columns.component });
  const dialog = page.getByTestId('save-dialog');
  const leave = page.getByTestId('leave-confirm');
  /** 메뉴 「AI 설정」 → 모델 출력 상한 고침 → 저장 창 → [저장] → POST 가 붙잡힐 때까지. */
  const saveHeld = async (tokens: string) => {
    await nav.getByRole('button', { name: shell.menu.aiSettings }).click();
    await expect(
      page.locator('[data-screen="admin-ai-settings"]'),
    ).toBeVisible();
    await components.getByRole('button', { name: /^모델 설정/ }).click();
    await page
      .getByRole('textbox', { name: t.model.maxOutputTokens })
      .fill(tokens);
    await page
      .getByTestId('save-bar')
      .getByRole('button', { name: t.saveBar.save })
      .click();
    await dialog
      .getByRole('textbox', { name: t.save.name })
      .fill('지어낸 새 판');
    await dialog
      .getByRole('button', { name: t.save.confirm, exact: true })
      .click();
    await settings.postArrived();
  };
  // 저장 중 뒤로가기 → 창 0 · 그 자리 → 저장됨 → 막은 이동대로 실행 기록
  await saveHeld('3000');
  await page.goBack();
  await page.waitForTimeout(300);
  await expect(leave).toHaveCount(0);
  // 막힌 뒤로가기(pop)는 주소가 먼저 바뀌어 있다 — 화면이 그대로인지를 본다
  await expect(page.locator('[data-screen="admin-ai-settings"]')).toBeVisible();
  await expect(dialog).toBeVisible();
  settings.releasePost('ok');
  await expect(page.locator('[data-screen="admin-runs"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/runs');
  await expect(leave).toHaveCount(0);
  expect(settings.sent('POST', '')).toHaveLength(1);
  // 다시: 저장 중 뒤로가기 → 실패(500) → 그때 나가기 창 → [나가기] → 실행 기록
  await saveHeld('3100');
  await page.goBack();
  await page.waitForTimeout(300);
  await expect(leave).toHaveCount(0);
  settings.releasePost('fail');
  await expect(dialog.getByTestId('save-failure')).toBeVisible();
  await leave
    .getByRole('button', { name: t.leave.confirm, exact: true })
    .click();
  await expect(page.locator('[data-screen="admin-runs"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/runs');
  expect(settings.sent('POST', '')).toHaveLength(2);
  expect(unrouted).toEqual([]);
  expect(dialogs).toEqual([]);
});

/**
 * 흉내 밖 /api/ 요청을 잡는 덫(밴드 AD4X). 흉내들보다 먼저 건다 — 나중에 건 route 가 먼저 받으므로 흉내가 받은 요청은 여기 오지 않는다.
 * 여기 온 요청은 적고 503 으로 끊는다(preview 프록시로 새지 않게). 시험 끝에 unrouted 가 비었는지 본다.
 */
async function trapUnrouted(page: Page) {
  const unrouted: string[] = [];
  await page.route(/\/api\//, (route) => {
    const url = new URL(route.request().url());
    unrouted.push(`${route.request().method()} ${url.pathname}`);
    return route.fulfill({ status: 503, body: '' });
  });
  return unrouted;
}

test('AD-04 「AI 설정」·「검토」 열(밴드 AD4X ①): AI 설정 칸 v3·「기본 설정」 → 「검토: 검토 중」 요청에 review=in_review·줄 셈 → 1280 폭 실측(단언 없음) · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const runs = await fakeRunLogApi(page, [
    runRow(3, {
      createdAt: '2026-10-15T16:02:00+09:00',
      isTest: true,
      review: 'in_review',
      aiSetting: { id: 3, name: 'v3' },
      documentName:
        '지어낸 아주 긴 이름의 지속가능경영 보고서 초안 최종본 둘째 판.pdf',
    }),
    runRow(2, {
      createdAt: '2026-10-15T15:00:00+09:00',
      module: 'dataverify',
      aiSetting: { id: null, name: 'colab-2026-01-15-v1' },
    }),
    runRow(1, { createdAt: '2026-10-15T14:00:00+09:00', review: 'pending' }),
  ]);
  await page.goto('/admin/runs');
  await expect(page.locator('[data-screen="admin-runs"]')).toBeVisible();
  await expect(page.locator('tr[data-run-id]')).toHaveCount(3);

  // AI 설정 칸: 판 이름·기본 판 「기본 설정」·없음 「–」. 열 차례는 머리 글로 찾는다.
  const heads = await page.locator('thead th').allTextContents();
  const aiColumn = heads.indexOf(RUN_LOG_TEXT.columns.aiSetting);
  expect(aiColumn).toBeGreaterThan(0);
  expect(heads.at(-1)).toBe(RUN_LOG_TEXT.columns.review);
  const cell = (id: number) =>
    page.locator(`tr[data-run-id="${id}"] td`).nth(aiColumn);
  await expect(cell(3)).toHaveText('v3');
  await expect(cell(2)).toHaveText(RUN_LOG_TEXT.defaultSetting);
  await expect(cell(1)).toHaveText(RUN_LOG_TEXT.empty);
  await expect(page.locator('tr[data-run-id="3"] [data-test-run]')).toHaveText(
    RUN_LOG_TEXT.test,
  );
  await expect(page.getByText(RUN_LOG_TEXT.foot)).toBeVisible();

  // 「검토: 검토 중」 → 그 뒤 요청에 review=in_review, 흉내가 거른 줄 하나.
  const before = runs.listUrls().length;
  await choose(
    page,
    RUN_LOG_TEXT.review.name,
    RUN_LOG_TEXT.review.options.in_review,
  );
  await expect(page.locator('tr[data-run-id]')).toHaveCount(1);
  const after = runs.listUrls().slice(before);
  expect(after.length).toBeGreaterThanOrEqual(1);
  for (const url of after)
    expect(url.searchParams.get('review')).toBe('in_review');
  await expect(page.locator('tr[data-run-id="3"] [data-review]')).toHaveText(
    RUN_LOG_TEXT.review.options.in_review,
  );
  await expect(page.getByTestId('count')).toHaveText(RUN_LOG_TEXT.count(1));
  await choose(page, RUN_LOG_TEXT.review.name, RUN_LOG_TEXT.review.options.all);
  await expect(page.locator('tr[data-run-id]')).toHaveCount(3);

  // 1280 폭(판 S9 — sid:MARC-ISSUE-201): 긴 문서 이름 줄이 있을 때 표 상자의 넘침과 「검토」 머리 오른쪽 끝을 재서 남긴다(단언 없음 — 보고에 옮긴다).
  await page.setViewportSize({ width: 1280, height: 900 });
  const measured = await page
    .locator('table')
    .locator('xpath=..')
    .evaluate((box) => {
      const head = [...box.querySelectorAll('thead th')].at(-1)!;
      return {
        scrollWidth: box.scrollWidth,
        clientWidth: box.clientWidth,
        reviewHeadRight: Math.round(head.getBoundingClientRect().right),
        boxRight: Math.round(box.getBoundingClientRect().right),
      };
    });
  test.info().annotations.push({
    type: 'AD4X-1280',
    description: JSON.stringify(measured),
  });
  expect(unrouted).toEqual([]);
});

test('AD-04 [엑셀 내보내기](밴드 AD4X ②): 거르기 다섯 → 누름 → 내려받기(서버 이름·흉내 바이트)·export 질의 = 마지막 목록 질의 − 쪽 → 409 → alert 글 → 0건은 Enter 눌러도 요청 0 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  // 흉내는 status·review 로 거른다 — 건 값과 맞는 줄(완료·확정)을 둔다(0건이면 단추가 꺼진다).
  const runs = await fakeRunLogApi(page, [
    runRow(2, {
      createdAt: '2026-09-15T15:00:00+09:00',
      status: 'done',
      review: 'confirmed',
    }),
    runRow(1, { createdAt: '2026-09-14T15:00:00+09:00', status: 'failed' }),
  ]);
  await page.goto('/admin/runs');
  await expect(page.locator('[data-screen="admin-runs"]')).toBeVisible();
  await expect(page.locator('tr[data-run-id]')).toHaveCount(2);

  await page.getByLabel(RUN_LOG_TEXT.searchLabel).fill('지어낸');
  await choose(page, RUN_LOG_TEXT.module.name, RUN_LOG_TEXT.modules.greenwash!);
  await choose(
    page,
    RUN_LOG_TEXT.status.name,
    RUN_LOG_TEXT.status.options.done,
  );
  await choose(
    page,
    RUN_LOG_TEXT.review.name,
    RUN_LOG_TEXT.review.options.confirmed,
  );
  await choose(
    page,
    RUN_LOG_TEXT.period.name,
    RUN_LOG_TEXT.period.options.lastMonth,
  );
  await expect(page.locator('tr[data-run-id]')).toHaveCount(1);
  await expect(page.getByTestId('export-count')).toHaveText(
    RUN_LOG_TEXT.exportCount('1'),
  );

  const button = page.getByTestId('export');
  const downloading = page.waitForEvent('download');
  await button.click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe(EXPORT_NAME);
  const saved = await download.path();
  const { readFileSync } = await import('node:fs');
  expect(readFileSync(saved, 'utf8')).toBe(EXPORT_TEXT);
  expect(runs.exportUrls()).toHaveLength(1);
  const last = new URLSearchParams(runs.listUrls().at(-1)!.searchParams);
  last.delete('limit');
  last.delete('offset');
  expect(Object.fromEntries(runs.exportUrls()[0]!.searchParams)).toEqual(
    Object.fromEntries(last),
  );
  expect([...last.keys()].sort()).toEqual(
    ['dateFrom', 'dateTo', 'module', 'q', 'review', 'status'].sort(),
  );

  // 409 상한 넘음 → 단추 옆 alert 글, 단추는 다시 켬.
  runs.setExport('tooLarge');
  await button.click();
  await expect(page.getByTestId('export-error')).toHaveText(
    RUN_LOG_TEXT.exportTooLarge,
  );
  await expect(button).not.toHaveAttribute('aria-disabled');
  expect(runs.exportUrls()).toHaveLength(2);

  // 0건: 끔 — 눌러도·Enter 를 쳐도 export 요청 0.
  await choose(
    page,
    RUN_LOG_TEXT.status.name,
    RUN_LOG_TEXT.status.options.queued,
  );
  await expect(page.getByText(RUN_LOG_TEXT.noMatch)).toBeVisible();
  await expect(button).toHaveAttribute('aria-disabled', 'true');
  // aria-disabled 단추는 Playwright 가 「enabled 아님」으로 기다리므로 force 로 누른다(누름 자체는 실제로 간다).
  await button.click({ force: true });
  await button.focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(200);
  expect(runs.exportUrls()).toHaveLength(2);
  expect(unrouted).toEqual([]);
});

test('AD-04a 실행 상세(밴드 AD4W): 문서 단추 → /api/run-logs/<id> 하나(companyId 없음) → 단계·0 토큰 「–」·파일 이름 → [닫기] 초점 되돌림 → 둘째 줄 시각 칸(기록 없음·실패) → Escape → 상세 없는 id 404 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const d = RUN_LOG_TEXT.detail;
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const first = runRow(3, { createdAt: '2026-10-15T16:02:00+09:00' });
  const second = runRow(2, {
    createdAt: '2026-10-15T15:00:00+09:00',
    status: 'failed',
  });
  const third = runRow(1, { createdAt: '2026-10-15T14:00:00+09:00' });
  const runs = await fakeRunLogApi(page, [first, second, third], undefined, {
    3: runDetail(first),
    2: runDetail(second, {
      stepUsageRecorded: false,
      failedStep: 'judge',
      errorCode: 'step_error',
      steps: runDetail(second).steps.map((step) => ({
        ...step,
        tokens: null,
        costUsd: null,
      })),
    }),
  });
  await page.goto('/admin/runs');
  await expect(page.locator('tr[data-run-id]')).toHaveCount(3);
  const dialog = page.getByTestId('run-detail');

  const button = page.getByRole('button', {
    name: d.openLabel(first.documentName),
  });
  await button.focus();
  await page.keyboard.press('Enter');
  await expect(dialog.getByRole('heading', { name: d.title })).toBeVisible();
  await expect(page.locator('[data-step]')).toHaveCount(6);
  expect(runs.detailUrls()).toHaveLength(1);
  expect(runs.detailUrls()[0]!.pathname).toBe('/api/run-logs/3');
  expect(runs.detailUrls()[0]!.searchParams.has('companyId')).toBe(false);
  await expect(page.locator('[data-step] td:first-child')).toHaveText([
    '글 뽑기',
    '색인',
    '판정',
    '낱말 세기',
    '위치 찾기',
    '결과 만들기',
  ]);
  await expect(page.locator('[data-step="index"] td').nth(3)).toHaveText(
    '21,300',
  );
  await expect(page.locator('[data-step="extract"] td').nth(3)).toHaveText(
    RUN_LOG_TEXT.empty,
  );
  await expect(page.getByTestId('run-files')).toContainText(
    '지어낸 결과 3.xlsx',
  );
  await dialog.getByRole('button', { name: d.close }).click();
  await expect(dialog).toHaveCount(0);
  await expect(button).toBeFocused();

  await page.locator('tr[data-run-id="2"] td').first().click();
  await expect(page.getByTestId('no-step-usage')).toHaveText(d.noStepUsage);
  await expect(page.locator('[data-step="judge"] td').nth(3)).toHaveText(
    RUN_LOG_TEXT.empty,
  );
  await expect(page.locator('[data-step="judge"] td').nth(2)).toHaveText(
    '5분 31초',
  );
  await expect(page.getByTestId('run-failure')).toHaveText(
    `${d.failedAt('판정')} · ${d.errorCode('step_error')}`,
  );
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);

  await page.locator('tr[data-run-id="1"] td').first().click();
  await expect(page.getByTestId('run-not-found')).toHaveText(d.notFound);
  expect(runs.detailUrls().map((url) => url.pathname)).toEqual([
    '/api/run-logs/3',
    '/api/run-logs/2',
    '/api/run-logs/1',
  ]);
  expect(unrouted).toEqual([]);
});

test('AD-05 AI 설정 줄(밴드 AD4X ③·AM1): 대상 「AI 설정 · 그린워싱 · v3 만듦」·「… · 기본 설정 적용」 → 「AI 설정」 누름 → 그 줄 모듈 주소 /admin/ai-settings/greenwash?version=v3 에 AD-02 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAuditApi(
    page,
    [
      auditRow(2, {
        at: '2026-10-15T16:02:00+09:00',
        actorKind: 'admin',
        actorUserId: 1,
        actorName: '지어낸 관리자',
        actorUsername: 'ops.admin',
        companyId: null,
        action: 'setting_change',
        event: 'ai_setting_created',
        targetKind: 'ai_setting',
        targetId: 3,
        targetLabel: 'v3',
        module: 'greenwash',
      }),
      auditRow(1, {
        at: '2026-10-15T15:00:00+09:00',
        actorKind: 'admin',
        actorUserId: 1,
        actorName: '지어낸 관리자',
        actorUsername: 'ops.admin',
        companyId: null,
        action: 'setting_change',
        event: 'ai_setting_applied',
        targetKind: 'ai_setting',
        targetId: null,
        targetLabel: 'colab-2026-01-15-v1',
        module: 'greenwash',
      }),
    ],
    [],
  );
  // AD-02 로 넘어가면 그 화면의 요청을 받는 흉내(안 걸면 preview 프록시로 샌다 — critic R3).
  await fakeAiSettingApi(page);
  // AD-02 가 고른 판의 prompt-model 을 읽는다(밴드 AD2W ② — 감독 허락 예외: 흉내 거는 줄만 더함).
  await fakePromptModelApi(page);
  await page.goto('/admin/audit');
  await expect(page.locator('[data-screen="admin-audit"]')).toBeVisible();
  await expect(page.locator('tr[data-audit-id]')).toHaveCount(2);
  const target = (id: number) =>
    page.locator(`tr[data-audit-id="${id}"] td`).nth(3);
  await expect(target(2)).toHaveText('AI 설정 · 그린워싱 · v3 만듦');
  await expect(target(1)).toHaveText('AI 설정 · 그린워싱 · 기본 설정 적용');
  const links = page.getByRole('link', { name: 'AI 설정', exact: true });
  await expect(links).toHaveCount(2);
  await expect(links.nth(0)).toHaveAttribute(
    'href',
    '/admin/ai-settings/greenwash?version=v3',
  );
  await expect(links.nth(1)).toHaveAttribute(
    'href',
    '/admin/ai-settings/greenwash',
  );
  await links.nth(0).click();
  await expect(page.locator('[data-screen="admin-ai-settings"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/ai-settings/greenwash');
  expect(new URL(page.url()).search).toBe('?version=v3');
  await expect(
    page.getByRole('heading', { name: AI_SETTING_TEXT.prompt.title('v3') }),
  ).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('AD-04 안내 띠(밴드 MP1W): 흉내 지표 aiProviderMock 거짓 → 지표는 보이고 「시험용 AI 연결」 띠 0 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeRunLogApi(
    page,
    [runRow(3, { createdAt: '2026-10-15T16:02:00+09:00' })],
    { ...RUN_METRICS, aiProviderMock: false },
  );
  await page.goto('/admin/runs');
  await expect(page.locator('tr[data-run-id]')).toHaveCount(1);
  await expect(page.getByTestId('metrics')).toContainText('3.1M');
  await expect(page.getByTestId('ai-mock-notice')).toHaveCount(0);
  await expect(page.getByText(RUN_LOG_TEXT.aiMockNotice)).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('AD-04 문서 없는 줄(밴드 ND1W): 목록 문서 칸 회색 「–」(title 없음)·단추 이름 「<시각> 실행 결과 보기」 → 줄 누름 → /api/run-logs/<id> 하나 → 상세 문서 칸 「–」 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const d = RUN_LOG_TEXT.detail;
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const named = runRow(3, { createdAt: '2026-10-15T16:02:00+09:00' });
  const bare = runRowNoDocument(2, { createdAt: '2026-10-15T15:00:00+09:00' });
  const runs = await fakeRunLogApi(page, [named, bare], undefined, {
    2: runDetail(bare, { documentId: null, documentName: null }),
  });
  await page.goto('/admin/runs');
  await expect(page.locator('tr[data-run-id]')).toHaveCount(2);
  await expect(page.getByText(RUN_LOG_TEXT.failed)).toHaveCount(0);

  const opener = page.locator('tr[data-run-id="2"] [data-run-open]');
  await expect(opener).toHaveText(RUN_LOG_TEXT.empty);
  await expect(opener.locator('[title]')).toHaveCount(0);
  await expect(opener).toHaveAccessibleName(
    d.openLabelNoDocument('2026-10-15 15:00'),
  );
  await expect(
    page.locator('tr[data-run-id="3"] [data-run-open] [title]'),
  ).toHaveAttribute('title', named.documentName);

  await page.locator('tr[data-run-id="2"] td').first().click();
  const dialog = page.getByTestId('run-detail');
  await expect(dialog.getByRole('heading', { name: d.title })).toBeVisible();
  await expect(dialog.locator('[data-document-missing]')).toHaveText(
    RUN_LOG_TEXT.empty,
  );
  expect(runs.detailUrls().map((url) => url.pathname)).toEqual([
    '/api/run-logs/2',
  ]);
  expect(unrouted).toEqual([]);
});

test('AD-04a 결과 파일 [내려받기](밴드 RF1W): 상세 → step null 줄만 단추 → 누름 → 내려받기(서버 이름·흉내 바이트)·/api/run-logs/<id>/files/<이름> 하나(companyId 없음) → 흉내에 없는 파일은 실패 글 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const d = RUN_LOG_TEXT.detail;
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const row = runRow(5, { createdAt: '2026-10-15T16:02:00+09:00' });
  const out = '지어낸 결과 #5.xlsx';
  const gone = '지어낸 표시 5.pdf';
  const served = '받은_지어낸 결과 5.xlsx';
  const runs = await fakeRunLogApi(
    page,
    [row],
    undefined,
    {
      5: runDetail(row, {
        files: [
          { name: out, step: null, mediaType: 'application/pdf', sizeBytes: 1 },
          {
            name: '지어낸 중간 5.json',
            step: 'judge',
            mediaType: 'application/json',
            sizeBytes: 1,
          },
          {
            name: gone,
            step: null,
            mediaType: 'application/pdf',
            sizeBytes: 1,
          },
        ],
      }),
    },
    { [`5/${out}`]: served },
  );
  await page.goto('/admin/runs');
  await expect(page.locator('tr[data-run-id]')).toHaveCount(1);
  await page.locator('tr[data-run-id="5"] td').first().click();
  const dialog = page.getByTestId('run-detail');
  await expect(dialog.getByRole('heading', { name: d.title })).toBeVisible();
  await expect(dialog.locator('[data-file-download]')).toHaveCount(2);

  const downloading = page.waitForEvent('download');
  await dialog.getByRole('button', { name: d.downloadLabel(out) }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe(served);
  const { readFileSync } = await import('node:fs');
  expect(readFileSync(await download.path(), 'utf8')).toBe(FILE_TEXT);
  expect(fileUrlsOf(runs.urls)).toHaveLength(1);
  expect(fileUrlsOf(runs.urls)[0]!.pathname).toBe(
    `/api/run-logs/5/files/${encodeURIComponent(out)}`,
  );
  expect(fileUrlsOf(runs.urls)[0]!.searchParams.has('companyId')).toBe(false);
  await expect(page.getByTestId('file-error')).toHaveText('');

  await dialog.getByRole('button', { name: d.downloadLabel(gone) }).click();
  await expect(page.getByTestId('file-error')).toHaveText(d.fileNotFound);
  expect(fileUrlsOf(runs.urls)).toHaveLength(2);
  expect(unrouted).toEqual([]);
});

test('AD-04 같이 시작·이어서(밴드 AD4P): 표에 「같이 시작 #101 · k/3」 셋·「이어서 #88」 하나 → 상세 엶 → 같이 시작 칸 · 같은 이름 두 파일이 한 줄 · 흉내에 없는 파일 → 「파일을 찾을 수 없어요」 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const d = RUN_LOG_TEXT.detail;
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const launch = {
    launchKey: '지어낸-묶음-열쇠',
    launchFirstRunId: 101,
    launchSize: 3,
  };
  const rows = [
    runRow(103, { ...launch, launchIndex: 3 }),
    runRow(102, { ...launch, launchIndex: 2 }),
    runRow(101, { ...launch, launchIndex: 1 }),
    runRow(52, { resumedFromRunId: 88 }),
  ];
  const out = '지어낸 결과 102.xlsx';
  const gone = '지어낸 표시 102.pdf';
  const runs = await fakeRunLogApi(
    page,
    rows,
    undefined,
    {
      102: runDetail(rows[1]!, {
        files: [
          {
            name: out,
            step: 'report',
            mediaType: 'application/pdf',
            sizeBytes: 1,
          },
          { name: out, step: null, mediaType: 'application/pdf', sizeBytes: 1 },
          {
            name: gone,
            step: null,
            mediaType: 'application/pdf',
            sizeBytes: 1,
          },
        ],
      }),
    },
    { [`102/${out}`]: `받은_${out}` },
  );
  await page.goto('/admin/runs');
  await expect(page.locator('tr[data-run-id]')).toHaveCount(4);
  await expect(page.locator('tr[data-run-id] [data-launch]')).toHaveText([
    '같이 시작 #101 · 3/3',
    '같이 시작 #101 · 2/3',
    '같이 시작 #101 · 1/3',
  ]);
  await expect(page.locator('tr[data-run-id] [data-resumed]')).toHaveText([
    '이어서 #88',
  ]);
  await expect(
    page.locator('tr[data-run-id="52"] [data-resumed]'),
  ).toBeVisible();

  await page.locator('tr[data-run-id="102"] td').first().click();
  const dialog = page.getByTestId('run-detail');
  await expect(dialog.getByRole('heading', { name: d.title })).toBeVisible();
  await expect(dialog.getByTestId('run-launch')).toHaveText('#101 · 2/3');
  await expect(dialog.getByTestId('run-launch-siblings')).toHaveText(
    '같이 시작한 실행 2개',
  );
  await expect(dialog.locator('[data-testid="run-files"] li')).toHaveCount(2);
  await expect(dialog.locator('[data-file-download]')).toHaveCount(2);

  await dialog.getByRole('button', { name: d.downloadLabel(gone) }).click();
  await expect(page.getByTestId('file-error')).toHaveText(d.fileNotFound);
  expect(fileUrlsOf(runs.urls)).toHaveLength(1);
  expect(unrouted).toEqual([]);
});

// 1280 문서 칸 한 줄(밴드 RL1, sid:MARC-ISSUE-403 N1·N2 — 디자인 6c DT1 대조): 첫 줄 배지·이름이 한 줄, 둘째 줄 알약 안 꺾임 0.
test('AD-04 1280×900 문서 칸(밴드 RL1): 「시험용」 배지와 이름 단추 세로 가운데 같음 · 긴 이름 말줄임 · 같이 시작·이어서 알약 글 한 줄 높이 · title = 전체 글 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const unrouted = await trapUnrouted(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const launch = {
    launchKey: '지어낸-묶음-열쇠',
    launchFirstRunId: 101,
    launchSize: 3,
  };
  await fakeRunLogApi(page, [
    runRow(101, {
      ...launch,
      launchIndex: 1,
      isTest: true,
      resumedFromRunId: 88,
      documentName:
        '지어낸 아주 긴 이름의 지속가능경영 보고서 초안 최종본 둘째 판.pdf',
    }),
  ]);
  await page.goto('/admin/runs');
  await expect(page.locator('tr[data-run-id]')).toHaveCount(1);
  const row = page.locator('tr[data-run-id="101"]');
  const pills = { launch: '같이 시작 #101 · 1/3', resumed: '이어서 #88' };
  await expect(row.locator('[data-launch]')).toHaveText(pills.launch);
  await expect(row.locator('[data-resumed]')).toHaveText(pills.resumed);

  const measured = await row.evaluate((tr) => {
    const box = (selector: string) =>
      tr.querySelector(selector)!.getBoundingClientRect();
    /** 배지 안 글이 차지한 높이(글 줄 수를 잰다 — 알약 높이는 h-5 로 고정이라 꺾여도 같다). */
    const textHeight = (selector: string) => {
      const text = document
        .createTreeWalker(tr.querySelector(selector)!, NodeFilter.SHOW_TEXT)
        .nextNode()!;
      const range = document.createRange();
      range.selectNodeContents(text);
      return range.getBoundingClientRect().height;
    };
    const name = tr.querySelector<HTMLElement>('[data-run-open] [title]')!;
    return {
      // 세로 가운데(items-center — 배지 h-5 와 이름 단추 줄 높이가 달라 top 은 1px 넘게 어긋난다). 꺾이면 한 줄 높이만큼 벌어진다.
      testMid: (box('[data-test-run]').top + box('[data-test-run]').bottom) / 2,
      openMid: (box('[data-run-open]').top + box('[data-run-open]').bottom) / 2,
      nameScroll: name.scrollWidth,
      nameClient: name.clientWidth,
      oneLine: textHeight('[data-test-run]'),
      oneLineBadge: box('[data-test-run]').height,
      launchText: textHeight('[data-launch]'),
      launchBadge: box('[data-launch]').height,
      resumedText: textHeight('[data-resumed]'),
      launchTitle: tr.querySelector('[data-launch]')!.getAttribute('title'),
      resumedTitle: tr.querySelector('[data-resumed]')!.getAttribute('title'),
    };
  });
  expect(Math.abs(measured.testMid - measured.openMid)).toBeLessThanOrEqual(1);
  expect(measured.nameScroll).toBeGreaterThan(measured.nameClient);
  expect(
    Math.abs(measured.launchBadge - measured.oneLineBadge),
  ).toBeLessThanOrEqual(1);
  expect(Math.abs(measured.launchText - measured.oneLine)).toBeLessThanOrEqual(
    1,
  );
  expect(Math.abs(measured.resumedText - measured.oneLine)).toBeLessThanOrEqual(
    1,
  );
  expect(measured.launchTitle).toBe(pills.launch);
  expect(measured.resumedTitle).toBe(pills.resumed);
  test.info().annotations.push({
    type: 'RL1-1280',
    description: JSON.stringify(measured),
  });
  expect(unrouted).toEqual([]);
});

// 첫 불러오기 자리(밴드 LD1, sid:MARC-ENT-443 ①②③): 목록 답을 800ms 늦춰 받기 전을 잰다.
test('AD-01 첫 불러오기: 받기 전 100ms·500ms 에 빈 목록 글 0 · 몸 줄 5 · tbody 높이 같음 → 받으면 진짜 줄 · 설명 줄 자리 높이 받기 전후 같음', async ({
  page,
}) => {
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAccountsApi(page, [accountRow(1), accountRow(2)]);
  // 뒤에 건 route 가 먼저 받는다 — 늦춘 뒤 흉내 서버로 넘긴다.
  await page.route(/\/api\/users(\?.*)?$/, async (route) => {
    await new Promise((done) => setTimeout(done, 800));
    await route.fallback();
  });
  await page.goto('/admin/accounts');
  const table = page.getByRole('table', { name: ACCOUNT_TEXT.list.tableLabel });
  const body = table.locator('tbody');
  const slot = page.getByTestId('description-pending');
  await expect(slot).toBeVisible();
  const started = Date.now();
  const at = async (ms: number) => {
    const wait = started + ms - Date.now();
    if (wait > 0) await page.waitForTimeout(wait);
    return {
      empty: await page.getByText(ACCOUNT_TEXT.list.empty).count(),
      rows: await body.locator('tr').count(),
      height: (await body.boundingBox())!.height,
    };
  };
  const early = await at(100);
  const later = await at(500);
  expect(early).toMatchObject({ empty: 0, rows: 5 });
  expect(later).toMatchObject({ empty: 0, rows: 5 });
  expect(later.height).toBe(early.height);
  expect(early.height).toBe(5 * 56);
  const pendingHeight = (await slot.boundingBox())!.height;
  const pendingTop = (await slot.boundingBox())!.y;
  await expect(
    page.getByRole('cell', { name: 'user01', exact: true }),
  ).toBeVisible();
  const description = page.getByText(ACCOUNT_TEXT.list.description(2));
  await expect(description).toBeVisible();
  await expect(slot).toHaveCount(0);
  const box = (await description.boundingBox())!;
  expect(box.height).toBe(pendingHeight);
  expect(box.y).toBe(pendingTop);
});

// 표 칸 가로 튐 0(밴드 DT1 ②, J3·sid:MARC-ISSUE-374): 목록 답을 800ms 늦춰 100ms(빈 줄)·500ms(막대)·받은 뒤 세 때에
// 머리 칸과 첫 몸 줄 칸의 x·width 를 잰다 — 세 때 사이 차이 1px 안(table-fixed + colgroup).
type ColumnBoxes = { head: number[][]; body: number[][] };
async function columnBoxes(page: Page, name: string): Promise<ColumnBoxes> {
  return page.getByRole('table', { name, exact: true }).evaluate((table) => {
    const pick = (row: Element | null) =>
      row ?
        [...row.children].map((cell) => {
          const box = cell.getBoundingClientRect();
          return [box.x, box.width];
        })
      : [];
    return {
      head: pick(table.querySelector('thead tr')),
      body: pick(table.querySelector('tbody tr')),
    };
  });
}
function expectSameColumns(a: ColumnBoxes, b: ColumnBoxes) {
  expect(b.head).toHaveLength(a.head.length);
  expect(b.body).toHaveLength(a.body.length);
  expect(a.body).toHaveLength(a.head.length);
  for (const [part, boxes] of [
    ['head', a.head],
    ['body', a.body],
  ] as const) {
    boxes.forEach(([x, width], index) => {
      const [x2, width2] = b[part][index]!;
      expect(Math.abs(x2! - x!), `${part} ${index} x`).toBeLessThanOrEqual(1);
      expect(
        Math.abs(width2! - width!),
        `${part} ${index} width`,
      ).toBeLessThanOrEqual(1);
    });
  }
}
async function threeMoments(
  page: Page,
  name: string,
  ready: () => Promise<void>,
) {
  const started = Date.now();
  const at = async (ms: number) => {
    const wait = started + ms - Date.now();
    if (wait > 0) await page.waitForTimeout(wait);
    return columnBoxes(page, name);
  };
  await expect(page.getByRole('table', { name, exact: true })).toBeVisible();
  const early = await at(100);
  const later = await at(500);
  await ready();
  const received = await columnBoxes(page, name);
  expectSameColumns(early, later);
  expectSameColumns(early, received);
}
/** 받은 뒤 몸 칸마다 안의 요소가 칸 오른쪽 끝을 넘지 않고 글이 칸 밖으로 넘치지 않는다(table-fixed 에서 옆 칸을 덮지 않게 — 밴드 DT1 B 검증 권고). */
async function expectNoOverflow(page: Page, name: string) {
  const over = await page
    .getByRole('table', { name, exact: true })
    .evaluate((table) =>
      [...table.querySelectorAll('tbody td')].flatMap((cell) => {
        const right = cell.getBoundingClientRect().right;
        const inner = [...cell.querySelectorAll('*')].reduce(
          (most, element) =>
            Math.max(most, element.getBoundingClientRect().right),
          0,
        );
        return inner > right + 0.5 || cell.scrollWidth > cell.clientWidth + 1 ?
            [
              `${cell.textContent} 칸 ${right} 안 ${inner} scroll ${cell.scrollWidth}/${cell.clientWidth}`,
            ]
          : [];
      }),
    );
  expect(over).toEqual([]);
}
const slow = (page: Page, pattern: RegExp) =>
  page.route(pattern, async (route) => {
    await new Promise((done) => setTimeout(done, 800));
    await route.fallback();
  });

test.describe('표 칸 가로 튐 0(밴드 DT1, 1280×900)', () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test('AD-01 계정: 100ms·500ms·받은 뒤 머리 칸·첫 몸 줄 칸 x·width 1px 안', async ({
    page,
  }) => {
    await signIn(page, { kind: 'admin', username: 'ops.admin' });
    await fakeAccountsApi(page, [
      accountRow(1),
      accountRow(2, { isLocked: true }),
      // 지어낸 긴 아이디 22자 — 아이디 칸 안에서 줄을 바꾼다(break-all)
      accountRow(3, { username: 'longusername.example01' }),
    ]);
    await slow(page, /\/api\/users(\?.*)?$/);
    await page.goto('/admin/accounts');
    await threeMoments(page, ACCOUNT_TEXT.list.tableLabel, () =>
      expect(page.locator('tr[data-account-id]')).toHaveCount(3),
    );
    await expectNoOverflow(page, ACCOUNT_TEXT.list.tableLabel);
  });

  test('AD-05 감사: 100ms·500ms·받은 뒤 머리 칸·첫 몸 줄 칸 x·width 1px 안', async ({
    page,
  }) => {
    await signIn(page, { kind: 'admin', username: 'ops.admin' });
    await fakeAuditApi(page, [auditRow(2), auditRow(1)], []);
    await slow(page, /\/api\/audit-logs(\?.*)?$/);
    await page.goto('/admin/audit');
    await threeMoments(page, AUDIT_TEXT.tableLabel, () =>
      expect(page.locator('tr[data-audit-id]')).toHaveCount(2),
    );
  });

  test('AD-04 실행 기록(흉내 지표 aiProviderMock 참): 100ms·500ms·받은 뒤 머리 칸·첫 몸 줄 칸 x·width 1px 안', async ({
    page,
  }) => {
    await signIn(page, { kind: 'admin', username: 'ops.admin' });
    await fakeRunLogApi(page, [
      runRow(3, {
        createdAt: '2026-10-15T16:02:00+09:00',
        module: 'materiality',
        isTest: true,
        review: 'in_review',
        aiSetting: { id: 3, name: 'v3' },
      }),
      runRow(2, {
        createdAt: '2026-10-15T15:00:00+09:00',
        module: 'dataverify',
        status: 'failed',
      }),
      // 긴 모듈 이름·긴 문서 이름·긴 AI 설정 이름·같이 시작·이어서 배지 — 칸 안에서 줄바꿈·말줄임(지어낸 값)
      runRow(1, {
        createdAt: '2026-10-15T14:00:00+09:00',
        module: 'inventory.scope3',
        status: 'processing',
        documentName:
          '지어낸 아주 긴 이름의 지속가능경영 보고서 초안 최종본 둘째 판.pdf',
        aiSetting: { id: 9, name: '아주긴설정이름-그린워싱-실험판-셋째' },
        launchKey: 'k',
        launchFirstRunId: 101,
        launchIndex: 1,
        launchSize: 3,
        resumedFromRunId: 88,
      }),
    ]);
    await slow(page, /\/api\/run-logs(\?.*)?$/);
    await page.goto('/admin/runs');
    await threeMoments(page, RUN_LOG_TEXT.tableLabel, () =>
      expect(page.locator('tr[data-run-id]')).toHaveCount(3),
    );
    await expectNoOverflow(page, RUN_LOG_TEXT.tableLabel);
  });
});

test('AD6 모듈·단계 이름(전 모듈): AD-04 원고작성 줄 모듈 칸 「보고서 작성」·모듈 거르기 선택지 여섯(셸 차례) → 상세 단계 넷 한국어 → AD-05 원고작성 AI 설정 줄 「AI 설정 · 보고서 작성 · v2 만듦」 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const d = RUN_LOG_TEXT.detail;
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const drafting = runRowNoDocument(4, {
    createdAt: '2026-10-15T16:02:00+09:00',
    module: 'drafting',
    flowId: 'drafting.draft@v2',
  });
  await fakeRunLogApi(page, [drafting], undefined, {
    4: runDetail(drafting, {
      steps: runDetail(drafting)
        .steps.slice(0, 4)
        .map((step, position) => ({
          ...step,
          name: ['extract', 'map', 'draft', 'report'][position]!,
        })),
      files: [],
    }),
  });
  await page.goto('/admin/runs');
  await expect(page.locator('tr[data-run-id]')).toHaveCount(1);
  await expect(page.locator('tr[data-run-id="4"]')).toContainText(
    '보고서 작성',
  );
  await expect(page.locator('tr[data-run-id="4"]')).not.toContainText(
    'drafting',
  );
  await page.getByRole('button', { name: RUN_LOG_TEXT.module.name }).click();
  await expect(page.getByRole('menuitemradio')).toHaveText([
    RUN_LOG_TEXT.module.all,
    '온실가스 Scope 3',
    '그린워싱',
    '중대성평가 IRO',
    '데이터 검증',
    '영문번역',
    '보고서 작성',
  ]);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menu')).toHaveCount(0);

  await page.locator('tr[data-run-id="4"] td').first().click();
  const dialog = page.getByTestId('run-detail');
  await expect(dialog.getByRole('heading', { name: d.title })).toBeVisible();
  await expect(page.locator('[data-step] td:first-child')).toHaveText([
    '전년도 보고서 읽기',
    '목차에 맞는 페이지 찾기',
    '목차마다 초안 짓기',
    '결과 만들기',
  ]);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);

  await fakeAuditApi(
    page,
    [
      auditRow(1, {
        at: '2026-10-15T16:02:00+09:00',
        actorKind: 'admin',
        actorUserId: 1,
        actorName: '지어낸 관리자',
        actorUsername: 'ops.admin',
        companyId: null,
        action: 'setting_change',
        event: 'ai_setting_created',
        targetKind: 'ai_setting',
        targetId: 2,
        targetLabel: 'v2',
        module: 'drafting',
      }),
    ],
    [],
  );
  await page.goto('/admin/audit');
  await expect(page.locator('tr[data-audit-id]')).toHaveCount(1);
  await expect(page.locator('tr[data-audit-id="1"] td').nth(3)).toHaveText(
    'AI 설정 · 보고서 작성 · v2 만듦',
  );
  expect(unrouted).toEqual([]);
});
