// 주소의 인자: 화면의 띠에서 자료·보기 방식·화면을 바꿔도, 바꾼 것 말고는 주소에 그대로 남는다.
// 데모 주소는 /dev/viewer·/dev/table(밴드 RT1). 검토 표의 띠 링크는 지금도 view=table 을 싣는다(데모 안은 고치지 않았다 — 해 없음).
// 전에는 뷰어가 주소를 data·mode 만으로 다시 써서 ?screen=compact 가 빠졌고, 검토 표의 띠는 링크를 view·data 만으로 만들어
// 자료를 바꾸면 &screen=cards 와 &calcFail 같은 것이 빠졌다(새로 고치면 다른 화면이 떴다).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

/** 주소의 인자를 이름 → 값으로. */
const params = (page: Page) =>
  Object.fromEntries(new URL(page.url()).searchParams);

test.describe('문서 뷰어', () => {
  // 둘째 화면은 본 화면의 클래스(.dv-*)를 하나도 쓰지 않는다. 그것으로 어느 화면인지 가른다.
  const mainScreenParts = (page: Page) =>
    page.locator('[class^="dv-"], [class*=" dv-"]');
  const firstPageDrawn = (page: Page) =>
    expect(
      page.locator('[data-document-id="a"] [data-page="1"] canvas'),
    ).toHaveAttribute('data-render-state', 'done');

  test('둘째 화면에서 보기 방식과 자료를 바꿔도 screen 이 주소에 남고, 새로 고쳐도 둘째 화면이다', async ({
    page,
  }) => {
    await page.goto('/dev/viewer?data=sample/compare.json&screen=compact');
    await firstPageDrawn(page);
    await expect(mainScreenParts(page)).toHaveCount(0);

    await page.getByRole('radio', { name: '전체 채움' }).check();
    expect(params(page)).toEqual({
      data: 'sample/compare.json',
      screen: 'compact',
      mode: 'fill',
    });

    await page.locator('header select').selectOption('sample/sentences.json');
    expect(params(page)).toEqual({
      data: 'sample/sentences.json',
      screen: 'compact',
      mode: 'fill',
    });

    await page.reload();
    await firstPageDrawn(page);
    await expect(mainScreenParts(page)).toHaveCount(0);
    await expect(page.getByRole('radio', { name: '전체 채움' })).toBeChecked();
    await expect(page.locator('header select')).toHaveValue(
      'sample/sentences.json',
    );

    // 기본 보기 방식으로 돌아가면 mode 만 빠진다.
    await page.getByRole('radio', { name: '옅게' }).check();
    expect(params(page)).toEqual({
      data: 'sample/sentences.json',
      screen: 'compact',
    });
  });

  test('이 앱이 모르는 인자도 지우지 않는다. 본 화면은 그대로 data 와 mode 만 쓴다', async ({
    page,
  }) => {
    await page.goto('/dev/viewer?data=sample/compare.json');
    await firstPageDrawn(page);
    await page.getByRole('radio', { name: '고른 것만' }).check();
    expect(params(page)).toEqual({
      data: 'sample/compare.json',
      mode: 'selected',
    });

    await page.goto('/dev/viewer?data=sample/compare.json&from=mail');
    await firstPageDrawn(page);
    await page.getByRole('radio', { name: '전체 채움' }).check();
    expect(params(page)).toEqual({
      data: 'sample/compare.json',
      from: 'mail',
      mode: 'fill',
    });
  });
});

test.describe('검토 표', () => {
  const rowsShown = (page: Page) =>
    expect(page.locator('[data-row-id]').first()).toBeVisible();
  const bar = (page: Page) => page.locator('header.app-bar');

  test('자료를 바꿔도 screen 과 그 밖의 인자가 남고, 화면을 바꿔도 자료와 그 밖의 인자가 남는다', async ({
    page,
  }) => {
    await page.goto('/dev/table?data=sample&screen=cards&calcFail=1');
    await rowsShown(page);
    await expect(page.locator('.rc')).toBeVisible();

    await bar(page).getByRole('link', { name: '가짜 5,000행' }).click();
    await rowsShown(page);
    expect(params(page)).toEqual({
      view: 'table',
      data: 'fake',
      rows: '5000',
      screen: 'cards',
      calcFail: '1',
    });
    await expect(page.locator('.rc')).toBeVisible();
    await expect(page.getByTestId('rt-summary')).toHaveAttribute(
      'data-total',
      '5000',
    );

    await bar(page).getByRole('link', { name: '표', exact: true }).click();
    await rowsShown(page);
    expect(params(page)).toEqual({
      view: 'table',
      data: 'fake',
      rows: '5000',
      calcFail: '1',
    });
    await expect(page.locator('.rt')).toBeVisible();
    await expect(page.locator('.rc')).toHaveCount(0);

    await bar(page).getByRole('link', { name: '카드(둘째 화면)' }).click();
    await rowsShown(page);
    expect(params(page)).toEqual({
      view: 'table',
      data: 'fake',
      rows: '5000',
      calcFail: '1',
      screen: 'cards',
    });

    // 가짜가 아닌 자료로 가면 가짜 행의 수(rows)는 뜻이 없어 빠진다. 나머지는 남는다.
    await bar(page).getByRole('link', { name: '예시' }).click();
    await rowsShown(page);
    expect(params(page)).toEqual({
      view: 'table',
      data: 'sample',
      calcFail: '1',
      screen: 'cards',
    });
    await expect(page.getByTestId('rt-summary')).toHaveAttribute(
      'data-total',
      '8',
    );
  });

  test('실제 자료로 가는 링크도 가짜 행의 수(rows)는 싣지 않고 나머지 인자는 싣는다', async ({
    page,
  }) => {
    await page.goto('/dev/table?data=fake&rows=300&screen=cards&calcFail=1');
    await rowsShown(page);
    // 누르지 않고 링크의 주소만 읽는다(테스트에는 실제 자료가 없어, 누르면 「자료를 쓸 수 없다」가 뜬다).
    const href = await bar(page)
      .getByRole('link', { name: '실제 자료(붙였으면)' })
      .getAttribute('href');
    expect(Object.fromEntries(new URLSearchParams(href!))).toEqual({
      view: 'table',
      data: 'local',
      screen: 'cards',
      calcFail: '1',
    });
  });
});
