// 떠 있는 api-py 에 닿는 한 흐름: 교환 전 → 교환(쿠키) → 내 세션 → 사업장 → 계산 → 기준정보 → Scope 3 후보 추리기.
// 진짜 Vite 프록시와 진짜 api-py 를 거친다. 값을 기대값으로 박지 않는다(꼴과 갈래만 본다).
// 토큰은 환경 변수로만 받는다. 테스트 이름, 단언의 말, 로그에 싣지 않는다.
import { expect, test } from '@playwright/test';
import type { BrowserContext, Page } from '@playwright/test';

const token = process.env.F9_TOKEN ?? '';
const secondToken = process.env.F9_TOKEN_2 ?? token;
const tenant = process.env.F9_TENANT ?? '';

/** 입력칸에 토큰을 넣는다. fill 을 쓰지 않는다: 실패하면 그 호출의 기록에 값이 찍힌다. */
async function putToken(page: Page, value: string) {
  await page.getByLabel('토큰').evaluate((element, text) => {
    const setValue = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      'value',
    )!.set!;
    setValue.call(element, text);
    element.dispatchEvent(new Event('input', { bubbles: true }));
  }, value);
}

async function sessionCookie(context: BrowserContext) {
  const cookie = (await context.cookies()).find(
    (each) => each.name === 'esg_session',
  );
  // 쿠키의 값은 단언에 싣지 않는다. 속성만 본다.
  return cookie ?
      {
        httpOnly: cookie.httpOnly,
        secure: cookie.secure,
        sameSite: cookie.sameSite,
        path: cookie.path,
      }
    : null;
}

test('교환부터 Scope 3 후보 추리기까지, 프록시를 거쳐 세션 쿠키로', async ({
  page,
  browser,
  baseURL,
}) => {
  expect(
    token !== '' && tenant !== '',
    'F9_TOKEN 과 F9_TENANT 를 환경 변수로 준다',
  ).toBe(true);

  // 교환 전: 세션이 없다.
  await page.goto('/dev/api');
  await expect(page.getByTestId('no-session')).toContainText('NO_SESSION');
  await expect(page.getByTestId('no-session')).toContainText('401');

  // 교환. 쿠키가 담기는가(Secure 쿠키인데 주소는 http://127.0.0.1 이다).
  await putToken(page, token);
  await page.getByRole('button', { name: '교환' }).click();
  await expect(page.getByTestId('exchanged')).toBeVisible();
  expect(await sessionCookie(page.context())).toEqual({
    httpOnly: true,
    secure: true,
    sameSite: 'Lax',
    path: '/',
  });
  // HttpOnly 라 쪽의 스크립트는 읽지 못한다.
  expect(await page.evaluate(() => document.cookie)).toBe('');
  await expect(page.getByLabel('토큰')).toHaveValue('');

  // 내 세션: 쿠키가 되보내졌다.
  await expect(page.getByTestId('me-tenant')).toHaveText(tenant);

  // 사업장을 만들면 다시 받은 목록에 뜬다.
  const siteName = `지어낸-사업장-${Date.now()}`;
  await page.getByLabel('사업장 이름').fill(siteName);
  await page.getByRole('button', { name: '만들기' }).click();
  await expect(page.getByTestId('sites')).toContainText(siteName);

  // 계산: 첫 행이 ok 이고 값이 십진 글자다.
  await page.getByRole('region', { name: '계산' }).getByRole('button').click();
  const firstRow = page
    .getByTestId('calc-rows')
    .locator('[data-row-status]')
    .first();
  await expect(firstRow).toHaveAttribute('data-row-status', 'ok');
  await expect(firstRow.getByTestId('co2e')).toHaveText(/^\d+(\.\d+)?$/);

  // 기준정보: 들인 낱줄이 있다.
  await expect(page.getByTestId('factors-count')).toHaveText(/^[1-9]\d*$/);

  // 후보 추리기: 둘 가운데 하나(패키지 사본만 들인 DB 에서는 no_candidates 다).
  await page
    .getByRole('region', { name: 'Scope 3 후보 추리기' })
    .getByRole('button')
    .click();
  await expect(page.getByTestId('shortlist')).toHaveAttribute(
    'data-status',
    /^(shortlisted|no_candidates)$/,
  );
  await expect(page.getByRole('alert')).toHaveCount(0);

  // 같은 서버를 localhost 라는 이름으로: 쿠키가 담기는지만 본다(새 문맥이라 앞의 쿠키가 없다).
  const other = await browser.newContext();
  try {
    const second = await other.newPage();
    await second.goto(`${baseURL!.replace('127.0.0.1', 'localhost')}dev/api`);
    await expect(second.getByTestId('no-session')).toBeVisible();
    await putToken(second, secondToken);
    await second.getByRole('button', { name: '교환' }).click();
    await expect(second.getByTestId('me-tenant')).toHaveText(tenant);
    expect(await sessionCookie(other)).toEqual({
      httpOnly: true,
      secure: true,
      sameSite: 'Lax',
      path: '/',
    });
  } finally {
    await other.close();
  }
});
