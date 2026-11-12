// 로그인 화면(CM-01·01a·01b)과 가드를 빌드 결과에서 연다(밴드 LG1 ②). 서버는 흉내(e2e/session.ts 의 fakeAuthApi).
// 글자는 문구 표(SESSION_TEXT) 값으로 단언한다(e2e → entities/session/config/text.ts 는 층 시험이 허락한 문 — N10).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { SESSION_TEXT } from '../src/entities/session/config/text.ts';
import { fakeAuthApi } from './session.ts';

const words = SESSION_TEXT.login;

const accounts = () => ({
  'ops.admin': { password: 'admin-pass-1', kind: 'admin' as const },
  user01: { password: 'service-pass-1', kind: 'service' as const },
});

async function logIn(page: Page, username: string, password: string) {
  await page.getByLabel(words.username, { exact: true }).fill(username);
  await page.getByLabel(words.password, { exact: true }).fill(password);
  await page.getByRole('button', { name: words.submit, exact: true }).click();
}

const pathOf = (page: Page) => new URL(page.url()).pathname;

test('안 로그인으로 /greenwash 를 열면 /login(CM-01), 콘솔 오류 0', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  const api = await fakeAuthApi(page, accounts());
  await page.goto('/greenwash');
  await expect(page.locator('[data-screen="login"]')).toBeVisible();
  expect(pathOf(page)).toBe('/login');
  await expect(
    page.getByRole('heading', { name: SESSION_TEXT.brand.service }),
  ).toBeVisible();
  await expect(page.getByText(words.foot)).toBeVisible();
  await expect(
    page.getByRole('button', { name: words.submit, exact: true }),
  ).toBeDisabled();
  expect(api.calls).toEqual([]);
  expect(errors).toEqual([]);
});

test('고객사 사용자 로그인 → /greenwash 목록, 운영 관리자 로그인 → /admin/accounts', async ({
  page,
}) => {
  const api = await fakeAuthApi(page, accounts());
  await page.goto('/login');
  await logIn(page, 'user01', 'service-pass-1');
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash');
  expect(api.calls.slice(0, 2)).toEqual(['POST /auth/login', 'GET /users/me']);
  expect(api.bodies[0]).toEqual({
    username: 'user01',
    password: 'service-pass-1',
  });

  // 새 탭 꼴(보관소 비움)으로 운영 관리자
  await page.evaluate(() => sessionStorage.clear());
  await page.goto('/login');
  await logIn(page, 'ops.admin', 'admin-pass-1');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  expect(pathOf(page)).toBe('/admin/accounts');
});

test('로그인 뒤 새로고침하면 보관소의 refresh 로 복원해 그 자리 그대로(refresh 한 번)', async ({
  page,
}) => {
  const api = await fakeAuthApi(page, accounts());
  await page.goto('/login');
  await logIn(page, 'user01', 'service-pass-1');
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  await page.goto('/greenwash/new');
  await expect(page.locator('[data-screen="new"]')).toBeVisible();
  expect(
    api.calls.filter((call) => call === 'POST /auth/refresh'),
  ).toHaveLength(1);
});

test('새로고침 때 refresh 가 503 이면 /login 에 「연결하지 못했어요」 띠, 닿은 뒤 [다시 시도] → 첫 화면(밴드 SN1)', async ({
  page,
}) => {
  const api = await fakeAuthApi(page, accounts());
  await page.goto('/login');
  await logIn(page, 'user01', 'service-pass-1');
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  api.failRefresh(Infinity);
  await page.reload();
  await expect(page.locator('[data-screen="login"]')).toBeVisible();
  expect(pathOf(page)).toBe('/login');
  const notice = page.locator('[data-reason="unreachable"]');
  await expect(notice).toContainText(SESSION_TEXT.notice.unreachable);
  api.failRefresh(0);
  await notice.getByRole('button', { name: words.retry }).click();
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash');
  expect(
    api.calls.filter((call) => call === 'POST /auth/refresh'),
  ).toHaveLength(2);
});

test('틀린 비밀번호 → 01a 글(role=alert), 주소 그대로. 잠김은 따로 잠김 글', async ({
  page,
}) => {
  const list = accounts();
  await fakeAuthApi(page, {
    ...list,
    locked: { password: 'x', kind: 'service', locked: true },
  });
  await page.goto('/login');
  await logIn(page, 'user01', 'nope');
  await expect(page.getByRole('alert')).toHaveText(words.invalid);
  expect(pathOf(page)).toBe('/login');
  await expect(page.getByLabel(words.password, { exact: true })).toHaveValue(
    '',
  );
  await logIn(page, 'locked', 'x');
  await expect(page.getByRole('alert')).toHaveText(words.locked);
});

test('CM-01b: 「비밀번호를 잊으셨나요?」 모달, [확인] 으로 닫는다', async ({
  page,
}) => {
  await fakeAuthApi(page, accounts());
  await page.goto('/login');
  await page.getByRole('button', { name: words.forgot }).click();
  const dialog = page.getByRole('dialog', { name: SESSION_TEXT.forgot.title });
  await expect(dialog).toContainText(SESSION_TEXT.forgot.body);
  await dialog
    .getByRole('button', { name: SESSION_TEXT.forgot.confirm })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('button', { name: words.forgot })).toBeFocused();
});

const pw = SESSION_TEXT.password;
const initialAccounts = () => ({
  ...accounts(),
  user03: {
    password: 'temp-pass-1',
    kind: 'service' as const,
    isInitial: true,
  },
});
/** CM-02 의 두 칸. 라벨 이름이 서로를 품어(「새 비밀번호」⊂「새 비밀번호 확인」) 차례로 찾는다. */
const newField = (page: Page) => page.locator('form input').nth(0);
const confirmField = (page: Page) => page.locator('form input').nth(1);

test('첫 로그인(isInitial) → CM-02 → 새 비밀번호로 바꾸기 → 고객사 첫 화면(/greenwash)', async ({
  page,
}) => {
  const api = await fakeAuthApi(page, initialAccounts());
  await page.goto('/login');
  await logIn(page, 'user03', 'temp-pass-1');
  await expect(page.locator('[data-screen="password"]')).toBeVisible();
  expect(pathOf(page)).toBe('/password');
  await expect(page.getByTestId('who')).toHaveText(pw.who('user03'));
  const submit = page.getByRole('button', { name: pw.submit });
  await newField(page).fill('1234567');
  await confirmField(page).fill('1234567');
  await expect(submit).toBeDisabled();
  await newField(page).fill('green-paper-1');
  await confirmField(page).fill('green-paper-');
  await expect(page.getByText(pw.mismatch)).toBeVisible();
  await expect(confirmField(page)).toHaveAttribute('aria-invalid', 'true');
  await confirmField(page).fill('green-paper-1');
  await submit.click();
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash');
  const change = api.calls.indexOf('POST /users/me/password');
  expect(api.bodies[change]).toEqual({
    currentPassword: 'temp-pass-1',
    newPassword: 'green-paper-1',
  });
});

test('CM-02 에서 앱 안 이동으로 /greenwash 를 열면 /password, 새로고침하면 임시 비밀번호를 잃어 /login(「임시 비밀번호로 다시 로그인」 회색 안내)', async ({
  page,
}) => {
  const api = await fakeAuthApi(page, initialAccounts());
  await page.goto('/login');
  await logIn(page, 'user03', 'temp-pass-1');
  await expect(page.locator('[data-screen="password"]')).toBeVisible();
  // 앱 안 이동(새로고침 없이): 주소를 바꾸고 popstate 를 낸다 — 라우터가 가드를 돌린다.
  await page.evaluate(() => {
    window.history.pushState({}, '', '/greenwash');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await expect(page).toHaveURL(/\/password$/);
  await expect(page.locator('[data-screen="password"]')).toBeVisible();
  // 새로고침: 메모리의 임시 비밀번호가 없다 → revoke → /login 에 안내
  await page.reload();
  await expect(page.getByRole('status')).toHaveText(
    SESSION_TEXT.notice.relogin,
  );
  expect(pathOf(page)).toBe('/login');
  expect(api.calls).toContain('POST /auth/revoke');
});

test('CM-02 의 [로그아웃] → revoke 요청 → /login', async ({ page }) => {
  const api = await fakeAuthApi(page, initialAccounts());
  await page.goto('/login');
  await logIn(page, 'user03', 'temp-pass-1');
  await expect(page.locator('[data-screen="password"]')).toBeVisible();
  const before = api.calls.length;
  await page.getByRole('button', { name: pw.logout }).click();
  await expect(page.locator('[data-screen="login"]')).toBeVisible();
  expect(pathOf(page)).toBe('/login');
  expect(api.calls.slice(before)).toEqual(['POST /auth/revoke']);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
});
