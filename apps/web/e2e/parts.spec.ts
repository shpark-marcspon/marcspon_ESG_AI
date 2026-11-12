// 다시 만든 부품의 시험 화면(/dev/parts)을 빌드 결과에서 연다. 밴드 FK2.
// jsdom 에는 CSS 가 없어서, 실제 높이·둥글기·색·초점 바깥선은 여기서 잰다.
import { expect, test } from '@playwright/test';
import type { FileChooser, Page } from '@playwright/test';

import { GW_TEXT } from '../src/entities/greenwash/config/text.ts';

/** 시험 화면을 열고, 콘솔 오류를 모은다. */
async function openParts(page: Page) {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/dev/parts');
  await expect(page.locator('[data-part="button"]')).toBeVisible();
  return errors;
}

const computed = (page: Page, testId: string, property: string) =>
  page
    .getByTestId(testId)
    .evaluate(
      (element, name) => getComputedStyle(element).getPropertyValue(name),
      property,
    );

test('시험 화면이 열리고 부품이 모두 보인다. 콘솔 오류가 없다', async ({
  page,
}) => {
  const errors = await openParts(page);
  for (const part of [
    'button',
    'empty',
    'dialog',
    'data-table',
    'form-rows',
    'file-dropzone',
  ])
    await expect(page.locator(`[data-part="${part}"]`)).toBeVisible();
  expect(errors).toEqual([]);
});

test('버튼: md 높이 36, lg 40. 둥글기는 square md 8px, square xs 4px, round 는 아주 큰 값', async ({
  page,
}) => {
  await openParts(page);
  const height = async (testId: string) =>
    (await page.getByTestId(testId).boundingBox())!.height;
  expect(await height('button-solidGrey-square-md')).toBe(36);
  expect(await height('button-solidGrey-square-lg')).toBe(40);
  expect(await height('button-solidGrey-round-md')).toBe(36);
  expect(await height('button-solidGrey-square-sm')).toBe(28);
  expect(await height('button-solidGrey-square-xs')).toBe(22);
  expect(
    await computed(page, 'button-solidBlack-square-md', 'border-radius'),
  ).toBe('8px');
  expect(
    await computed(page, 'button-solidBlack-square-xs', 'border-radius'),
  ).toBe('4px');
  const round = await computed(
    page,
    'button-solidBlack-round-md',
    'border-radius',
  );
  expect(parseFloat(round)).toBeGreaterThanOrEqual(9999);
  // 회색 버튼 글자 #383C40(디자이너 값)
  expect(await computed(page, 'button-solidGrey-square-md', 'color')).toBe(
    'rgb(56, 60, 64)',
  );
  // md 최소 너비 80, round md 좌우 안쪽 16
  expect(
    (await page.getByTestId('button-solidGrey-square-md').boundingBox())!.width,
  ).toBeGreaterThanOrEqual(80);
  expect(
    await computed(page, 'button-solidGrey-round-md', 'padding-left'),
  ).toBe('16px');
  expect(
    await computed(page, 'button-solidGrey-square-md', 'padding-left'),
  ).toBe('12px');
});

test('버튼: 아이콘 16, 아이콘–글자 사이 2', async ({ page }) => {
  await openParts(page);
  const icon = page.getByTestId('button-icon').locator('svg');
  const box = (await icon.boundingBox())!;
  expect(box.width).toBe(16);
  expect(box.height).toBe(16);
  expect(await computed(page, 'button-icon', 'column-gap')).toBe('2px');
});

test('버튼: Tab 으로 초점을 주면 2px 바깥선이 #8B95A1 로 2px 떨어져 그려진다', async ({
  page,
}) => {
  await openParts(page);
  const first = page.getByTestId('button-solidBlack-square-xs');
  // 바로 앞의 초점 받을 수 있는 요소가 없으니, 버튼 앞 칸에서 Tab 한 번으로 간다.
  await first.evaluate((element) => {
    const before = document.createElement('a');
    before.href = '#before';
    before.id = 'before-first-button';
    before.textContent = '앞';
    element.parentElement!.prepend(before);
  });
  await page.locator('#before-first-button').focus();
  await page.keyboard.press('Tab');
  await expect(first).toBeFocused();
  expect(
    await computed(page, 'button-solidBlack-square-xs', 'outline-color'),
  ).toBe('rgb(139, 149, 161)');
  expect(
    await computed(page, 'button-solidBlack-square-xs', 'outline-width'),
  ).toBe('2px');
  expect(
    await computed(page, 'button-solidBlack-square-xs', 'outline-offset'),
  ).toBe('2px');
});

test('빈 목록: 높이 200, 버튼 있는 것과 없는 것', async ({ page }) => {
  await openParts(page);
  for (const testId of ['empty-with-action', 'empty-plain'])
    expect((await page.getByTestId(testId).boundingBox())!.height).toBe(200);
  await expect(
    page.getByTestId('empty-with-action').getByRole('button', {
      name: '자료 올리기',
    }),
  ).toBeVisible();
  await expect(page.getByTestId('empty-plain').getByRole('button')).toHaveCount(
    0,
  );
});

test('버튼: loading 이면 키트 Spinner 가 이름과 함께 돌고 버튼은 꺼진다', async ({
  page,
}) => {
  await openParts(page);
  const button = page.getByTestId('button-loading');
  await expect(button).toBeDisabled();
  await expect(button).toHaveAttribute('aria-busy', 'true');
  await expect(
    button.getByRole('status', { name: '불러오는 중' }),
  ).toBeVisible();
});

test('모달: 덮개는 #1C1E21 50%, 그림자 shadow/strong, 너비 sm 420·md 640·lg 800. Esc 로 닫히고 여는 버튼으로 초점이 돌아온다', async ({
  page,
}) => {
  await openParts(page);
  for (const [size, width] of [
    ['sm', 420],
    ['md', 640],
    ['lg', 800],
  ] as const) {
    const opener = page.getByTestId(`dialog-open-${size}`);
    await opener.click();
    const dialog = page.getByTestId(`dialog-${size}`);
    await expect(dialog).toBeVisible();
    await expect(
      page.getByRole('dialog', { name: `모달 ${size}` }),
    ).toBeVisible();
    // 열리는 움직임(zoom-in-95)이 끝난 뒤에 잰다.
    await expect
      .poll(async () => (await dialog.boundingBox())!.width)
      .toBe(width);
    const overlay = page.locator('.twp.fixed.inset-0.z-modal').first();
    expect(
      await overlay.evaluate(
        (element) => getComputedStyle(element).backgroundColor,
      ),
    ).toBe('rgba(28, 30, 33, 0.5)');
    // Tailwind 는 그림자 앞에 링 자리 둘(투명, 0px)을 늘 붙인다. 보이는 층은 shadow/strong 하나뿐이어야 한다.
    const layers = (
      await dialog.evaluate((element) => getComputedStyle(element).boxShadow)
    ).split(/,\s*(?=rgba?\()/);
    expect(layers.at(-1)).toBe('rgba(0, 0, 0, 0.2) 3px 3px 10px 0px');
    for (const layer of layers.slice(0, -1))
      expect(layer).toBe('rgba(0, 0, 0, 0) 0px 0px 0px 0px');
    expect(
      await dialog.evaluate(
        (element) => getComputedStyle(element).borderRadius,
      ),
    ).toBe('16px');
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(opener).toBeFocused();
  }
});

test('모달: 루트에 variant 를 주지 않아도 키트 Header 가 default 꼴(굵은 제목)로 그려지고, lg 의 긴 본문은 모달 안에서 스크롤된다', async ({
  page,
}) => {
  await openParts(page);
  await page.getByTestId('dialog-open-lg').click();
  const dialog = page.getByTestId('dialog-lg');
  await expect(dialog).toBeVisible();
  const header = dialog.getByRole('heading', { name: '모달 lg' }).locator('..');
  expect(
    await header.evaluate((element) => getComputedStyle(element).fontWeight),
  ).toBe('700');
  const sizes = await dialog.evaluate((element) => ({
    scroll: element.scrollHeight,
    client: element.clientHeight,
    viewport: window.innerHeight,
  }));
  expect(sizes.scroll).toBeGreaterThan(sizes.client);
  expect(sizes.client).toBeLessThanOrEqual(sizes.viewport - 32);
});

test('표: 몸 칸의 아래 선은 1px #D1D5D9(칸에 건다), 머리 줄은 위아래 선과 높이 40 이상, 몸 줄은 56 이상', async ({
  page,
}) => {
  await openParts(page);
  const table = page.getByRole('table', { name: 'table-main' });
  // 진짜 표 의미: display 를 바꾸지 않는다(키트는 block·flex 로 바꿨다)
  expect(
    await table.evaluate((element) => getComputedStyle(element).display),
  ).toBe('table');
  const cell = table.getByRole('row').nth(1).getByRole('cell').first();
  const style = await cell.evaluate((element) => {
    const computed = getComputedStyle(element);
    return {
      color: computed.borderBottomColor,
      width: computed.borderBottomWidth,
      style: computed.borderBottomStyle,
    };
  });
  expect(style).toEqual({
    color: 'rgb(209, 213, 217)',
    width: '1px',
    style: 'solid',
  });
  const header = table.getByRole('columnheader').first();
  const head = await header.evaluate((element) => {
    const computed = getComputedStyle(element);
    return {
      top: `${computed.borderTopWidth} ${computed.borderTopColor}`,
      bottom: `${computed.borderBottomWidth} ${computed.borderBottomColor}`,
      background: computed.backgroundColor,
      transform: computed.textTransform,
    };
  });
  expect(head).toEqual({
    top: '1px rgb(209, 213, 217)',
    bottom: '1px rgb(209, 213, 217)',
    background: 'rgb(250, 251, 251)',
    transform: 'none',
  });
  expect((await header.boundingBox())!.height).toBeGreaterThanOrEqual(40);
  expect(
    (await table.getByRole('row').nth(1).boundingBox())!.height,
  ).toBeGreaterThanOrEqual(56);
  // 숫자 열은 오른쪽, 글 열은 왼쪽
  const align = (index: number) =>
    table
      .getByRole('row')
      .nth(1)
      .getByRole('cell')
      .nth(index)
      .evaluate((element) => getComputedStyle(element).textAlign);
  expect(await align(0)).toBe('left');
  expect(await align(1)).toBe('right');
  expect(await align(3)).toBe('center');
});

test('표: 정렬 머리 칸을 누르면 aria-sort 가 바뀐다. 클릭 줄을 Tab 으로 가서 Enter 를 누르면 눌린다', async ({
  page,
}) => {
  await openParts(page);
  const table = page.getByRole('table', { name: 'table-main' });
  const header = table.getByRole('columnheader', { name: '페이지' });
  await expect(header).toHaveAttribute('aria-sort', 'none');
  await header.getByRole('button').click();
  await expect(header).toHaveAttribute('aria-sort', 'ascending');
  await header.getByRole('button').click();
  await expect(header).toHaveAttribute('aria-sort', 'descending');
  // 정렬할 수 없는 열에는 aria-sort 가 없다
  await expect(
    table.getByRole('columnheader', { name: '보기' }),
  ).not.toHaveAttribute('aria-sort');

  // 내림차순(쪽 27, 12, 3)의 첫 줄: 마지막 머리 버튼 → Tab → 첫 줄
  const lastHeaderButton = table
    .getByRole('columnheader', { name: '점수' })
    .getByRole('button');
  await lastHeaderButton.focus();
  await page.keyboard.press('Tab');
  const firstRow = table.getByRole('row').nth(1);
  await expect(firstRow).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('table-main-clicked')).toHaveText(
    '누른 줄: c3',
  );
  // 칸 안 버튼은 줄 클릭으로 번지지 않는다
  await table
    .getByRole('row')
    .nth(2)
    .getByRole('button', { name: '열기' })
    .click();
  await expect(page.getByTestId('table-main-clicked')).toHaveText(
    '누른 줄: c3',
  );
});

// 옛 늦춘 값 prop 의 견본(table-loading)과 그 단언은 걷었다(밴드 DT1, sid:MARC-ISSUE-373). 로딩 줄은 아래 「표 loading」 시험이 잰다.
test('표: 줄 0 이면 Empty 가 tbody 안 한 칸에 그려진다', async ({ page }) => {
  await openParts(page);
  const empty = page.getByRole('table', { name: 'table-empty' });
  await expect(empty.locator('tbody td')).toHaveCount(1);
  await expect(empty.getByText('검색된 문장이 없어요')).toBeVisible();
});

test('드롭존: 바로 앞 요소에서 Tab 한 번으로 칸에 가서 Enter 를 누르면 파일 창이 열린다', async ({
  page,
}) => {
  // 파일 창 가로채기는 듣는 쪽을 붙일 때 비동기로 켜진다. Enter 바로 앞에 waitForEvent 를 걸면 켜지기 전에 창이 열려
  // 사건을 놓칠 수 있다(전체 실행에서 두 번 재현, 따로 돌리면 초록). 그래서 맨 앞에서 듣기 시작한다.
  const choosers: FileChooser[] = [];
  page.on('filechooser', (chooser) => choosers.push(chooser));
  await openParts(page);
  const section = page.getByTestId('dropzone-empty');
  const zone = section.getByRole('button', {
    name: /파일을 끌어다 놓거나 눌러서 고르세요/,
  });
  // 바로 앞의 초점 받을 수 있는 요소를 만들어 둔다(시험 화면에서 칸 앞은 표의 마지막 줄이라 차례가 바뀔 수 있다)
  await zone.evaluate((element) => {
    const before = document.createElement('a');
    before.href = '#before';
    before.id = 'before-dropzone';
    before.textContent = '앞';
    element.parentElement!.parentElement!.prepend(before);
  });
  await page.locator('#before-dropzone').focus();
  await page.keyboard.press('Tab');
  await expect(zone).toBeFocused();
  expect(choosers).toHaveLength(0);
  await page.keyboard.press('Enter');
  await expect.poll(() => choosers.length).toBe(1);
  expect(choosers[0]!.isMultiple()).toBe(true);
  // 계산된 모양: 점선 1px, 최소 높이 200, 모서리 8
  const look = await zone.evaluate((element) => {
    const computed = getComputedStyle(element);
    return {
      style: computed.borderTopStyle,
      width: computed.borderTopWidth,
      radius: computed.borderTopLeftRadius,
    };
  });
  expect(look).toEqual({ style: 'dashed', width: '1px', radius: '8px' });
  expect((await zone.boundingBox())!.height).toBeGreaterThanOrEqual(200);
});

test('드롭존: 허용 밖 파일을 넣으면 거부 사유가 보이고, 허용된 것은 목록에 들어간다', async ({
  page,
}) => {
  await openParts(page);
  const section = page.getByTestId('dropzone-empty');
  await section.locator('input[type="file"]').setInputFiles([
    {
      name: '표.xls',
      mimeType: 'application/vnd.ms-excel',
      buffer: Buffer.from('x'),
    },
    { name: '표.xlsx', mimeType: '', buffer: Buffer.from('x') },
    {
      name: '큰.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.alloc(1024 * 1024 + 1),
    },
  ]);
  await expect(
    section.getByText('표.xls · XLSX·PDF 파일만 올려 주세요'),
  ).toBeVisible();
  await expect(
    section.getByText('큰.pdf · 1MB 이하 파일을 올려 주세요'),
  ).toBeVisible();
  await expect(section.getByText('표.xlsx', { exact: true })).toBeVisible();
  await section.getByRole('button', { name: '표.xlsx 지우기' }).click();
  await expect(section.getByText('표.xlsx', { exact: true })).toHaveCount(0);
});

test('드롭존: 올리는 중이면 칸이 흐려지고 주황 Spinner 가 돈다. 줄 상태 글은 업로드 중·업로드 실패', async ({
  page,
}) => {
  await openParts(page);
  const uploading = page.getByTestId('dropzone-uploading');
  const zone = uploading.getByRole('button', {
    name: /파일을 끌어다 놓거나/,
  });
  await expect(zone).toHaveAttribute('aria-disabled', 'true');
  expect(
    await zone.evaluate((element) => getComputedStyle(element).opacity),
  ).toBe('0.4');
  const spinner = zone.getByRole('status', { name: '업로드 중' });
  await expect(spinner).toBeVisible();
  expect(
    await spinner.evaluate((element) => getComputedStyle(element).color),
  ).toBe('rgb(242, 92, 44)');
  await expect(uploading.getByText('업로드 중', { exact: true })).toBeVisible();
  const failed = page.getByTestId('dropzone-failed').getByText('업로드 실패');
  await expect(failed).toBeVisible();
  expect(
    await failed.evaluate((element) => getComputedStyle(element).color),
  ).toBe('rgb(234, 40, 49)');
  // 줄 높이 28(지우기 단추 28 상자를 담는다 — 344 SC8, AV2 Q5)
  const row = page.getByTestId('dropzone-files').getByRole('listitem').first();
  expect((await row.boundingBox())!.height).toBe(28);
});

test('드롭존 오류 aria(밴드 FZ1): 칸이 aria-invalid 이고, 칸 아래 오류 글이 칸의 설명으로 읽힌다', async ({
  page,
}) => {
  const errors = await openParts(page);
  const zone = page.getByTestId('dropzone-invalid').getByRole('button', {
    name: /파일을 끌어다 놓거나/,
  });
  await expect(zone).toHaveAttribute('aria-invalid', 'true');
  await expect(zone).toHaveAccessibleDescription('파일을 하나 올려 주세요');
  // 오류가 없는 칸에는 둘 다 없다
  const plain = page.getByTestId('dropzone-empty').getByRole('button', {
    name: /파일을 끌어다 놓거나/,
  });
  await expect(plain).not.toHaveAttribute('aria-invalid');
  await expect(plain).not.toHaveAttribute('aria-describedby');
  expect(errors).toEqual([]);
});

// ── 밴드 FW1 ⓪: FK2 생김새 고침(band-reports/FK2-design-review.md) ──

test('버튼 글자 크기: xs·sm 12, md 14, lg 16(Bold). sm 최소 너비 56, round sm 좌우 10', async ({
  page,
}) => {
  await openParts(page);
  for (const [size, fontSize] of [
    ['xs', '12px'],
    ['sm', '12px'],
    ['md', '14px'],
    ['lg', '16px'],
  ] as const)
    expect(
      await computed(page, `button-solidGrey-square-${size}`, 'font-size'),
    ).toBe(fontSize);
  expect(
    await computed(page, 'button-solidGrey-square-lg', 'font-weight'),
  ).toBe('700');
  expect(
    await computed(page, 'button-solidGrey-square-md', 'font-weight'),
  ).toBe('500');
  expect(
    (await page.getByTestId('button-solidGrey-square-sm').boundingBox())!.width,
  ).toBeGreaterThanOrEqual(56);
  expect(
    await computed(page, 'button-solidGrey-round-sm', 'padding-left'),
  ).toBe('10px');
  expect(
    await computed(page, 'button-solidGrey-square-sm', 'padding-left'),
  ).toBe('8px');
});

test('outlineOrange: 바탕은 흰색, hover 하면 #F3F4F5', async ({ page }) => {
  await openParts(page);
  const button = page.getByTestId('button-outlineOrange-round-md');
  await expect(button).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  // 글자는 text-brand #F25C2C 그대로
  await expect(button).toHaveCSS('color', 'rgb(242, 92, 44)');
  await button.hover();
  // 전이(200ms)가 끝날 때까지 다시 잰다.
  await expect(button).toHaveCSS('background-color', 'rgb(243, 244, 245)');
});

test('모달 제목은 Bold 24(pre-display-04)', async ({ page }) => {
  await openParts(page);
  await page.getByTestId('dialog-open-md').click();
  const title = page.getByTestId('dialog-title-md');
  await expect(title).toBeVisible();
  await expect(title).toHaveCSS('font-size', '24px');
  await expect(title).toHaveCSS('font-weight', '700');
  await expect(
    page.getByTestId('dialog-md').getByRole('button', { name: '닫기' }),
  ).toBeVisible();
});

// ── 밴드 FW1 ①: 화면 뼈대와 기본 표시 부품 ──

test('화면 뼈대·기본 표시 부품 절이 보이고 콘솔 오류가 없다', async ({
  page,
}) => {
  const errors = await openParts(page);
  for (const part of ['app-shell', 'page-info', 'greenwash-badges'])
    await expect(page.locator(`[data-part="${part}"]`)).toBeVisible();
  expect(errors).toEqual([]);
});

test('화면 뼈대: 메뉴 폭 120, 머리 줄 64, 고른 항목 aria-current="page", 쓰지 않는 항목 aria-disabled', async ({
  page,
}) => {
  await openParts(page);
  const shell = page.getByTestId('app-shell-demo');
  const nav = shell.getByRole('navigation', { name: '모듈 메뉴' });
  expect((await nav.boundingBox())!.width).toBe(120);
  const header = shell.locator('header');
  expect((await header.boundingBox())!.height).toBe(64);
  await expect(header).toHaveCSS('padding-left', '32px');
  await expect(header.getByRole('heading', { level: 1 })).toHaveText(
    '그린워싱 점검',
  );
  const current = nav.locator('[aria-current="page"]');
  await expect(current).toHaveCount(1);
  await expect(current).toHaveText('그린워싱 점검');
  // 고른 항목: 주황 글자(orange-400 #F68F6E) + 오른쪽 3px 주황 막대(#F25C2C)
  await expect(current).toHaveCSS('color', 'rgb(246, 143, 110)');
  await expect(current).toHaveCSS('border-right-color', 'rgb(242, 92, 44)');
  await expect(current).toHaveCSS('border-right-width', '3px');
  await expect(nav).toHaveCSS('background-color', 'rgb(28, 30, 33)');
  // 쓰지 않는 항목은 눌러도 고른 항목이 바뀌지 않는다
  const disabled = nav.getByRole('button', { name: '온실가스' });
  await expect(disabled).toHaveAttribute('aria-disabled', 'true');
  // Playwright 는 aria-disabled 요소를 누를 수 없다고 보고 기다린다. 클릭 사건을 직접 보낸다.
  await disabled.dispatchEvent('click');
  await expect(current).toHaveText('그린워싱 점검');
  // 다른 항목을 누르면 고른 항목이 옮겨 간다
  await nav.getByRole('button', { name: '대시보드' }).click();
  await expect(nav.locator('[aria-current="page"]')).toHaveText('대시보드');
  // 흰 카드: 모서리 16, 안쪽 32
  const card = page.getByTestId('card-demo');
  await expect(card).toHaveCSS('border-radius', '16px');
  await expect(card).toHaveCSS('padding-top', '32px');
  await expect(card).toHaveCSS('background-color', 'rgb(255, 255, 255)');
});

test('한 줄 안내: 기본 #F3F4F5 · 중요 #FEEEE9 · 오류 #FCE4E6 바탕', async ({
  page,
}) => {
  await openParts(page);
  for (const [tone, background, color] of [
    ['default', 'rgb(243, 244, 245)', 'rgb(111, 119, 129)'],
    ['important', 'rgb(254, 238, 233)', 'rgb(194, 73, 34)'],
    ['error', 'rgb(252, 228, 230)', 'rgb(167, 32, 39)'],
  ] as const) {
    const info = page.getByTestId(`page-info-${tone}`);
    await expect(info).toHaveCSS('background-color', background);
    await expect(info).toHaveCSS('color', color);
    await expect(info).toHaveCSS('padding-top', '12px');
    await expect(info).toHaveCSS('padding-left', '16px');
    await expect(info).toHaveCSS('border-radius', '8px');
  }
});

test('단계 띠: 지금 단계만 주황 바탕이고 aria-current="step"', async ({
  page,
}) => {
  await openParts(page);
  const flow = page.getByRole('list', { name: '점검 단계 2' });
  const current = flow.locator('[aria-current="step"]');
  await expect(current).toHaveCount(1);
  await expect(current).toContainText('문장 찾기·판정');
  await expect(current).toHaveCSS('background-color', 'rgb(242, 92, 44)');
  expect((await current.boundingBox())!.height).toBe(36);
});

test('머리 줄 제목은 NanumSquare Neo(nanum-display-01, 24), PageTitle 제목은 24px Bold', async ({
  page,
}) => {
  await openParts(page);
  const shell = page.getByTestId('app-shell-demo');
  const h1 = shell.locator('header').getByRole('heading', { level: 1 });
  await expect(h1).toHaveCSS('font-size', '24px');
  await expect(h1).toHaveCSS('font-weight', '900'); // 시안 「관리자」 900(GW3R A1)
  expect(
    await h1.evaluate((element) => getComputedStyle(element).fontFamily),
  ).toMatch(/NanumSquare ?Neo/);
  const h2 = shell.getByRole('heading', { level: 2, name: '새 점검' });
  await expect(h2).toHaveCSS('font-size', '24px');
  await expect(h2).toHaveCSS('font-weight', '700');
});

// ── 밴드 FW1 ②: 검토·확정·비교 표시 부품 ──

test('검토·확정·비교 표시 부품 절이 보이고 콘솔 오류가 없다', async ({
  page,
}) => {
  const errors = await openParts(page);
  for (const part of ['greenwash-review', 'greenwash-compare'])
    await expect(page.locator(`[data-part="${part}"]`)).toBeVisible();
  expect(errors).toEqual([]);
});

test('제외 사유 모달: 열리고, 사유 없이 [제외] 면 오류, 고르면 값이 나가고, Esc 로 닫힌다', async ({
  page,
}) => {
  const errors = await openParts(page);
  const opener = page.getByTestId('exclude-open');
  await opener.click();
  const dialog = page.getByRole('dialog', { name: '이 문장을 제외할까요?' });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole('heading', { name: '이 문장을 제외할까요?' }),
  ).toHaveCSS('font-size', '24px');
  await dialog.getByRole('button', { name: '제외' }).click();
  await expect(dialog.getByRole('alert')).toHaveText('필수 선택 항목이에요');
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  // 다시 열면 비어 있다. 사유를 고르고 내면 값이 나간다
  await opener.click();
  await expect(dialog.getByRole('alert')).toHaveCount(0);
  await dialog.getByRole('radio', { name: '근거가 문서에 있음' }).click();
  await dialog.getByRole('textbox', { name: '설명' }).fill('표에 근거 있음');
  await dialog.getByRole('button', { name: '제외' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('review-result')).toContainText(
    '제외: evidence_in_doc / 표에 근거 있음',
  );
  expect(errors).toEqual([]);
});

test('확정 모달: 제목 18px 가운데(1400 폭), 미검토 n 경고는 n>0 일 때만, Esc 로 닫힌다', async ({
  page,
}) => {
  const errors = await openParts(page);
  const opener = page.getByTestId('confirm-open-8');
  await opener.click();
  const dialog = page.getByRole('dialog', { name: '검토를 확정할까요?' });
  await expect(dialog).toBeVisible();
  const title = dialog.getByRole('heading', { name: '검토를 확정할까요?' });
  await expect(title).toHaveCSS('font-size', '18px');
  await expect(title).toHaveCSS('text-align', 'center');
  await expect(dialog).toContainText('미검토 문장 8개');
  // 잠금 안내는 한 줄 안내의 중요 꼴(#FEEEE9)
  await expect(dialog.locator('[data-tone="important"]')).toHaveCSS(
    'background-color',
    'rgb(254, 238, 233)',
  );
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  await page.getByTestId('confirm-open-0').click();
  await expect(dialog).toBeVisible();
  await expect(dialog).not.toContainText('미검토');
  await dialog.getByRole('button', { name: '확정' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('review-result')).toContainText(
    '확정 누름 1번',
  );
  expect(errors).toEqual([]);
});

test('채택·제외 토글: aria-pressed 가 값을 따른다', async ({ page }) => {
  await openParts(page);
  const group = page
    .locator('[data-part="greenwash-review"]')
    .getByRole('group', { name: '검토' });
  const adopt = group.getByRole('button', { name: '채택' });
  await expect(adopt).toHaveAttribute('aria-pressed', 'false');
  await adopt.click();
  await expect(adopt).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('review-choice-value')).toHaveText(
    '지금 값: adopted',
  );
});

// ── 밴드 FW1b ⓪: FW1 디자인 대조 고침(band-reports/FW1-design-review.md) ──

test('버튼 lg 는 md 보다 좁지 않다(최소 너비 80)', async ({ page }) => {
  await openParts(page);
  const width = async (id: string) =>
    (await page.getByTestId(id).boundingBox())!.width;
  for (const shape of ['square', 'round'])
    expect(
      await width(`button-solidGrey-${shape}-lg`),
      shape,
    ).toBeGreaterThanOrEqual(await width(`button-solidGrey-${shape}-md`));
  expect(await width('button-solidGrey-square-lg')).toBeGreaterThanOrEqual(80);
});

test('비교 배지: 해소는 배지 「해소」 + 아래 갈래 글, 검토 토글은 [제외][채택], 등급 배지 좌우 6', async ({
  page,
}) => {
  const errors = await openParts(page);
  const compare = page.locator('[data-part="greenwash-compare"]');
  const badge = compare.locator('[data-compare="resolved_deleted"]');
  const note = compare.locator('[data-compare-note="resolved_deleted"]');
  await expect(badge).toHaveText(
    await compare.locator('[data-compare="resolved_undetermined"]').innerText(),
  );
  await expect(note).toBeVisible();
  await expect(note).toHaveCSS('font-size', '12px');
  // 갈래 글은 배지 아래에 있다
  expect((await note.boundingBox())!.y).toBeGreaterThanOrEqual(
    (await badge.boundingBox())!.y + (await badge.boundingBox())!.height,
  );
  // 해소 배지 셋의 폭이 같다
  const widths = await Promise.all(
    ['resolved_deleted', 'resolved_not_flagged', 'resolved_undetermined'].map(
      async (kind) =>
        (await compare.locator(`[data-compare="${kind}"]`).boundingBox())!
          .width,
    ),
  );
  expect(new Set(widths).size).toBe(1);
  await expect(
    compare.locator('[data-compare-note="resolved_undetermined"]'),
  ).toHaveCount(0);

  const group = page
    .locator('[data-part="greenwash-review"]')
    .getByRole('group', { name: GW_TEXT.review.groupLabel });
  const boxes = await Promise.all(
    [GW_TEXT.review.excluded, GW_TEXT.review.adopted].map(
      async (name) =>
        (await group.getByRole('button', { name }).boundingBox())!.x,
    ),
  );
  expect(boxes[0]).toBeLessThan(boxes[1]!);

  await expect(page.getByTestId('risk-high')).toHaveCSS('padding-left', '6px');
  await expect(page.getByTestId('risk-high')).toHaveCSS('height', '20px');
  expect(errors).toEqual([]);
});

// ── 밴드 AV2(sid:MARC-ISSUE-344): 공용 부품 꼴을 시안 v149 값으로 ──

test('공용 부품 꼴(344): 배지 700 12/1.4 · 창 간격 16·글 14 · 탭 · 검색 칸 · 올리기 칸 글. 콘솔 오류가 없다', async ({
  page,
}) => {
  const errors = await openParts(page);

  // SB1 위험 배지: Bold, 줄 높이 12 × 1.4
  await expect(page.getByTestId('risk-high')).toHaveCSS('font-weight', '700');
  await expect(page.getByTestId('risk-high')).toHaveCSS(
    'line-height',
    '16.8px',
  );

  // SB9 창: 겹침 16 · 바탕 글 14
  await page.getByTestId('dialog-open-md').click();
  const dialog = page.getByTestId('dialog-md');
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveCSS('row-gap', '16px');
  await expect(dialog).toHaveCSS('font-size', '14px');
  await dialog.getByRole('button', { name: '닫기' }).click();
  await expect(dialog).toBeHidden();

  // SB2 상자 탭: 안 고른 칸 글자 #6F7781(tertiary)
  const box = page.getByTestId('tabs-box');
  await expect(box.getByRole('tab', { name: '검토' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(box.getByRole('tab', { name: '전체' })).toHaveCSS(
    'color',
    'rgb(111, 119, 129)',
  );

  // SB3 줄 탭: 목록 밑줄 1px, 칸 최소 96
  const line = page.getByTestId('tabs-line');
  await expect(line).toHaveCSS('border-bottom-width', '1px');
  await expect(line.getByRole('tab', { name: '전체' })).toHaveCSS(
    'min-width',
    '96px',
  );
  expect(
    (await line.getByRole('tab', { name: '전체' }).boundingBox())!.width,
  ).toBeGreaterThanOrEqual(96);

  // SB4 검색 칸: 돋보기 왼쪽, 글은 40 에서 시작, 오른 12
  const search = page.getByTestId('search-field');
  await expect(search).toHaveCSS('padding-left', '40px');
  await expect(search).toHaveCSS('padding-right', '12px');
  const icon = page.locator('[data-part="tabs-search"] svg');
  await expect(icon).toHaveCount(1);
  const inputBox = (await search.boundingBox())!;
  const iconBox = (await icon.boundingBox())!;
  expect(iconBox.x + iconBox.width).toBeLessThanOrEqual(inputBox.x + 40);
  expect(iconBox.x).toBeGreaterThan(inputBox.x);

  // SB6 올리기 칸: 큰 글 #383C40(grey.800)
  await expect(
    page
      .getByTestId('dropzone-empty')
      .getByText('파일을 끌어다 놓거나 눌러서 고르세요'),
  ).toHaveCSS('color', 'rgb(56, 60, 64)');

  expect(errors).toEqual([]);
});

// 첫 불러오기 자리(밴드 LD1, sid:MARC-ENT-443, 6c 표·결과 카드·제목 자리). jsdom 에 없는 높이·계산값을 잰다.
test('표 loading: 줄 5 · 줄 높이 = 진짜 줄 56 · 막대 바탕 background-tertiary · 움직임 없음 · 머리줄 그대로 · empty 0', async ({
  page,
}) => {
  await openParts(page);
  const table = page.getByRole('table', { name: 'table-loading-rows' });
  await expect(table).toHaveAttribute('aria-busy', 'true');
  await expect(table.locator('thead th')).toHaveCount(4);
  await expect(table.locator('tbody tr')).toHaveCount(5);
  await expect(table.getByText('검색된 문장이 없어요')).toHaveCount(0);
  await expect(table.locator('tbody [data-skeleton-bar]')).toHaveCount(20);
  const real = await page
    .getByRole('table', { name: 'table-main' })
    .locator('tbody tr')
    .first()
    .boundingBox();
  const heights = await table
    .locator('tbody tr')
    .evaluateAll((rows) =>
      rows.map((row) => row.getBoundingClientRect().height),
    );
  expect(real!.height).toBe(56);
  expect(heights).toEqual(Array(5).fill(56));
  const bar = await table
    .locator('tbody [data-skeleton-bar]')
    .first()
    .evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        background: style.backgroundColor,
        animation: style.animationName,
        height: style.height,
        radius: style.borderTopLeftRadius,
      };
    });
  const tertiary = await page.evaluate(() => {
    const probe = document.createElement('span');
    probe.className = 'bg-background-tertiary';
    document.body.append(probe);
    const color = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return color;
  });
  expect(bar).toEqual({
    background: tertiary,
    animation: 'none',
    height: '12px',
    radius: '6px',
  });
  expect(tertiary).not.toBe('rgba(0, 0, 0, 0)');
  // 쪽 수 칸은 오른쪽(ml-auto), 버튼 칸은 가운데 — 막대가 칸 맞춤을 따른다
  const cells = table.locator('tbody tr').first().locator('td');
  const placement = async (index: number) =>
    cells.nth(index).evaluate((cell) => {
      const box = cell.getBoundingClientRect();
      const bar = cell.firstElementChild!.getBoundingClientRect();
      return {
        left: Math.round(bar.left - box.left),
        right: Math.round(box.right - bar.right),
      };
    });
  expect((await placement(1)).right).toBe(16);
  const center = await placement(3);
  expect(Math.abs(center.left - center.right)).toBeLessThanOrEqual(1);
});

test('결과 카드 스켈레톤: 수 칸 900 이상 4열 · 900 아래 2열, 칸 높이 96 · 모서리 8, 카드 이름', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openParts(page);
  const card = page
    .getByTestId('load-skeleton-card')
    .getByRole('status', { name: '결과를 불러오는 중' });
  await expect(card).toBeVisible();
  const columns = () =>
    card.locator('.grid').evaluate((grid) => {
      const tops = [...grid.children].map((child) =>
        Math.round(child.getBoundingClientRect().top),
      );
      const first = grid.children[0]!;
      const style = getComputedStyle(first);
      return {
        perRow: tops.filter((top) => top === tops[0]).length,
        height: style.height,
        radius: style.borderTopLeftRadius,
        animation: style.animationName,
      };
    });
  expect(await columns()).toEqual({
    perRow: 4,
    height: '96px',
    radius: '8px',
    animation: 'none',
  });
  await page.setViewportSize({ width: 899, height: 900 });
  await expect.poll(async () => (await columns()).perRow).toBe(2);
});

test('제목 자리: titlePending·descriptionPending 의 높이 = 진짜 제목 줄 높이, 설명 막대 360×12 · 제목 막대 22', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openParts(page);
  const pending = page.getByTestId('page-title-pending');
  const ready = page.getByTestId('page-title-ready');
  const sizes = (box: typeof pending) =>
    box.evaluate((element) => {
      const heading = element.querySelector('h2')!;
      const lines = element.querySelectorAll('h2, p');
      return {
        whole: element.getBoundingClientRect().height,
        heading: heading.getBoundingClientRect().height,
        description: lines[1]!.getBoundingClientRect().height,
      };
    });
  expect(await sizes(pending)).toEqual(await sizes(ready));
  const bars = await pending
    .locator('[data-skeleton-bar]')
    .evaluateAll((elements) =>
      elements.map((element) => {
        const box = element.getBoundingClientRect();
        return { width: Math.round(box.width), height: box.height };
      }),
    );
  expect(bars[0]!.height).toBe(22);
  expect(bars[1]).toEqual({ width: 360, height: 12 });
});

// 열 폭 고정(밴드 DT1 ②, J3·sid:MARC-ISSUE-374): 견본 표 셋이 layout="fixed" — 로딩 줄 표와 진짜 줄 표의 머리 칸이 같은 자리·같은 폭.
test('표 layout fixed: table-loading-rows·table-empty 와 table-main 의 머리 칸 x·width 가 열마다 1px 안(1280×900)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openParts(page);
  const heads = (name: string) =>
    page
      .getByRole('table', { name, exact: true })
      .locator('thead th')
      .evaluateAll((cells) =>
        cells.map((cell) => {
          const box = cell.getBoundingClientRect();
          return [box.x, box.width];
        }),
      );
  // 계산값 table-layout fixed(셋 다). 이 견본은 문장 말고 모두 폭이 있어 auto 로 그려도 칸 자리가 같다 — 짜임은 계산값으로 본다.
  for (const name of ['table-main', 'table-loading-rows', 'table-empty'])
    expect(
      await page
        .getByRole('table', { name, exact: true })
        .evaluate((table) => getComputedStyle(table).tableLayout),
    ).toBe('fixed');
  const main = await heads('table-main');
  expect(main).toHaveLength(4);
  for (const name of ['table-loading-rows', 'table-empty']) {
    const other = await heads(name);
    expect(other).toHaveLength(main.length);
    other.forEach(([x, width], index) => {
      expect(
        Math.abs(x! - main[index]![0]!),
        `${name} ${index} x`,
      ).toBeLessThanOrEqual(1);
      expect(
        Math.abs(width! - main[index]![1]!),
        `${name} ${index} width`,
      ).toBeLessThanOrEqual(1);
    });
  }
  // 폭을 준 열(페이지 86 · 점수 74 · 보기 88)은 그 폭, 문장은 남은 폭
  expect(main.slice(1).map(([, width]) => Math.round(width!))).toEqual([
    86, 74, 88,
  ]);
});

// 묶음 줄(밴드 DT1 ③, sid:MARC-ISSUE-384): rowSpan 칸 높이 = 덮은 줄 높이 합 — 펼치면 펼침 줄까지 덮는다.
test('표 table-span: rowSpan 칸이 묶음 줄 셋을 덮고, [식 보기] 로 펼치면 펼침 줄까지 덮는다(높이 1px 안)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openParts(page);
  const table = page.getByRole('table', { name: 'table-span', exact: true });
  await expect(table.getByTestId('span-row')).toHaveCount(5);
  await expect(table.locator('tbody tr[data-group="1"]')).toHaveCount(3);
  await expect(table.locator('thead th button')).toHaveCount(0);
  /** 묶음 1 의 rowSpan 칸 높이와, 그 칸이 덮는 줄(데이터 셋 + 그 사이 펼침 줄) 높이 합. */
  const measure = () =>
    table.evaluate((element) => {
      const rows = [...element.querySelectorAll('tbody tr')];
      const first = rows[0]!.querySelector('td')!;
      const span = Number(first.getAttribute('rowspan'));
      const covered = rows.slice(0, span);
      return {
        span,
        cell: first.getBoundingClientRect().height,
        rows: covered.reduce(
          (sum, row) => sum + row.getBoundingClientRect().height,
          0,
        ),
        expanded: covered.filter((row) => row.hasAttribute('data-expanded-row'))
          .length,
      };
    });
  const closed = await measure();
  expect(closed.span).toBe(3);
  expect(closed.expanded).toBe(0);
  expect(Math.abs(closed.cell - closed.rows)).toBeLessThanOrEqual(1);

  await table
    .locator('tbody tr[data-group="1"]')
    .nth(1)
    .getByRole('button', { name: '식 보기' })
    .click();
  await expect(table.getByTestId('span-formula')).toHaveText('118 + 35 ≠ 150');
  const opened = await measure();
  expect(opened.span).toBe(4);
  expect(opened.expanded).toBe(1);
  expect(Math.abs(opened.cell - opened.rows)).toBeLessThanOrEqual(1);
  expect(opened.cell).toBeGreaterThan(closed.cell);
  // 펼침 칸은 덮이지 않은 열 셋(해·판정·계산 식)을 한 칸이
  await expect(table.locator('tr[data-expanded-row] td')).toHaveAttribute(
    'colspan',
    '3',
  );
});

test('양식 줄 form-rows: 라벨 칸 폭 160 · 줄 높이 64 이상 · 묶음 위 선 1px', async ({
  page,
}) => {
  await openParts(page);
  const rows = page.getByTestId('form-rows');
  const sizes = await rows.evaluate((element) => {
    const lines = [...element.children];
    return {
      lines: lines.length,
      labels: lines.map(
        (line) => line.firstElementChild!.getBoundingClientRect().width,
      ),
      heights: lines.map((line) => line.getBoundingClientRect().height),
      top: getComputedStyle(element).borderTopWidth,
      margin: getComputedStyle(element).marginTop,
    };
  });
  expect(sizes.lines).toBe(2);
  expect(sizes.labels).toEqual([160, 160]);
  for (const height of sizes.heights) expect(height).toBeGreaterThanOrEqual(64);
  expect(sizes.top).toBe('1px');
  expect(sizes.margin).toBe('0px');
});
