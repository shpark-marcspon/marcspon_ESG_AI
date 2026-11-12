// 운영 관리자의 그린워싱(밴드 SV1, sid:MARC-ENT-286 · 쓰기 열기 밴드 GR3, sid:MARC-ENT-374·409)을 빌드 결과에서 연다. 서버는 흉내(e2e/session.ts·e2e/accounts.ts).
//   AD-01 → LNB 「서비스 화면」 → 그린워싱 목록([새 점검]·[다시 실행] 있음 — 고객사 사용자와 같이 쓴다) → 머리 [관리자 화면] → AD-01. 고객사 사용자에겐 [관리자 화면]이 없다.
// 글자는 문구 표(ACCOUNT_TEXT·GW_TEXT) 값으로 단언한다.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { ACCOUNT_TEXT } from '../src/entities/account/config/text.ts';
import { GW_TEXT } from '../src/entities/greenwash/config/text.ts';
import { accountRow, fakeAccountsApi } from './accounts.ts';
import { useMockStore } from './greenwash-server.ts';
import { signIn } from './session.ts';

// 그린워싱 화면을 목 저장소로 연다(밴드 GW1R Q1 — 기본은 실어댑터, 목은 데모 빌드의 탭 표지 뒤로만). 단언은 그대로다.
test.beforeEach(({ page }) => useMockStore(page));

const shell = ACCOUNT_TEXT.shell;
const gw = GW_TEXT.shell;

/** 콘솔 오류·잡히지 않은 예외를 모은다. */
function consoleErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  return errors;
}

const pathOf = (page: Page) => new URL(page.url()).pathname;

test('운영 관리자: AD-01 → 「서비스 화면」 → 그린워싱 목록(인사말·[관리자 화면], [새 점검] 있음) → [관리자 화면] → AD-01. 콘솔 오류 0', async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await fakeAccountsApi(page, [accountRow(1)]);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeVisible();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await nav.getByRole('button', { name: shell.menu.service }).click();
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash');
  await expect(page.getByText(gw.adminGreeting)).toBeVisible();
  await expect(
    page.locator('[data-testid="row-status"]').first(),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: GW_TEXT.list.newCheck, exact: true }),
  ).toBeVisible();
  await expect(page.locator('[data-next="rerun"]').first()).toBeVisible();
  // GW-01b(sid:MARC-ENT-409): 「내가 올린 것만」 없음(남김), 목록 아래 안내는 고객사와 같은 글
  await expect(page.getByText(GW_TEXT.list.mineOnly)).toHaveCount(0);
  await expect(page.getByTestId('list-notice')).toHaveText(GW_TEXT.list.notice);
  const toAdmin = page.getByRole('button', { name: gw.toAdmin, exact: true });
  await expect(toAdmin).toBeVisible();
  await toAdmin.click();
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeVisible();
  expect(pathOf(page)).toBe('/admin/accounts');
  expect(errors).toEqual([]);
});

test('고객사 사용자: 그린워싱 목록에 [관리자 화면] 없음, 인사말 「담당자님 안녕하세요」. 콘솔 오류 0', async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await signIn(page);
  await page.goto('/greenwash');
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  await expect(page.getByText(gw.greeting)).toBeVisible();
  await expect(page.getByText(gw.adminGreeting)).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: GW_TEXT.list.newCheck, exact: true }),
  ).toBeVisible();
  await expect(page.getByText(GW_TEXT.list.mineOnly)).toBeVisible();
  await expect(page.getByTestId('list-notice')).toHaveText(GW_TEXT.list.notice);
  await expect(
    page.getByRole('button', { name: gw.toAdmin, exact: true }),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});
