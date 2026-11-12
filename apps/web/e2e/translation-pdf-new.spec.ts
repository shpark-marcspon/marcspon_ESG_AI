// 영문번역 PDF 새 번역의 쪽 칸 썸네일을 빌드 결과에서(밴드 TRW9). 서버는 e2e/translation-pdf-server.ts 의 흉내(import 만), 합성 PDF 45쪽은 메모리에서 짓는다.
//   PDF 올림 → 칸 40·그림 40 그려짐 → [더 보기] → 45 · 그림 위 끌기 3→7 → CEO 3~7 · 칠한 칸 틀 색. 워드(txt)는 칸 그대로(캔버스 0).
// TRW9_SHOTS 가 있으면 그 폴더에 1440·1280 칠하기 전·뒤 그림.
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { writePdf } from '../tools/pdf-writer.ts';
import { signIn } from './session.ts';
import { fakeTranslationPdfApi } from './translation-pdf-server.ts';
import { fakeTranslationApi } from './translation-server.ts';

const PDF = Buffer.from(
  writePdf(
    Array.from({ length: 45 }, (_, n) => ({
      width: 595,
      height: 842,
      rotate: 0 as const,
      marks: [],
      texts: [{ x: 72, top: 72, size: 18, str: `Made-up page ${n + 1}` }],
      tables: [],
    })),
  ),
);
const TXT = Buffer.from(
  ['[PAGE 1]', 'made up', '[PAGE 2]', 'made up', '[PAGE 3]', 'made up'].join(
    '\n',
  ),
);

const shots = process.env.TRW9_SHOTS;
async function shot(page: Page, name: string) {
  if (shots)
    await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
const center = async (target: Locator) => {
  const box = (await target.boundingBox())!;
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
};
const borderColor = (target: Locator) =>
  target.evaluate((node) => getComputedStyle(node).borderTopColor);

async function openPdfForm(page: Page) {
  await fakeTranslationPdfApi(page);
  await signIn(page);
  await page.goto('/translation/pdf/new');
  await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
    name: 'made_up_report.pdf',
    mimeType: 'application/pdf',
    buffer: PDF,
  });
  await expect(page.getByTestId('file-meta')).toContainText('총 45페이지');
  const grid = page.getByTestId('page-grid');
  await expect(page.locator('[data-page]')).toHaveCount(40);
  await expect(grid).toHaveAttribute('data-pdf-state', 'ready');
  await expect(page.locator('canvas[data-render-state="done"]')).toHaveCount(
    40,
  );
}

test('PDF 45쪽: 보이는 칸만 그린다 → [더 보기] → 45 그려짐', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openPdfForm(page);
  const width = await page
    .locator('[data-page="1"] canvas')
    .evaluate((node: HTMLCanvasElement) => node.width);
  expect(width).toBeGreaterThan(0);
  await page.getByRole('button', { name: /^더 보기/ }).click();
  await expect(page.locator('[data-page]')).toHaveCount(45);
  await expect(page.locator('canvas[data-render-state="done"]')).toHaveCount(
    45,
  );
});

for (const width of [1440, 1280]) {
  test(`${width}: 그림 위 끌기 3→7 → CEO 3~7 · 칠한 칸 틀 색이 다르다`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await openPdfForm(page);
    await page.locator('[data-page="1"]').scrollIntoViewIfNeeded();
    await shot(page, `${width}-before`);

    const frameOf = (n: number) =>
      page.locator(`[data-page="${n}"] [data-thumb-frame]`);
    const plain = await borderColor(frameOf(3));
    const from = await center(page.locator('[data-page="3"] canvas'));
    const to = await center(page.locator('[data-page="7"] canvas'));
    await page.mouse.move(from.x, from.y);
    await page.mouse.down();
    await page.mouse.move(to.x, to.y, { steps: 6 });
    await page.mouse.up();

    await expect(page.locator('[data-parts~="ceo"]')).toHaveCount(5);
    await expect(page.locator('[data-part-field="ceo"]')).toHaveValue('3~7');
    expect(await borderColor(frameOf(5))).not.toBe(plain);
    expect(await borderColor(frameOf(8))).toBe(plain);
    await shot(page, `${width}-painted`);
  });
}

test('워드(txt): 칸은 그대로 — data-pdf-state 없음 · 캔버스 0', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await fakeTranslationApi(page);
  await signIn(page);
  await page.goto('/translation/new');
  await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
    name: 'sample_extract.txt',
    mimeType: 'text/plain',
    buffer: TXT,
  });
  const grid = page.getByTestId('page-grid');
  await expect(grid).toBeVisible();
  await expect(page.locator('[data-page]')).toHaveCount(3);
  await expect(grid).not.toHaveAttribute('data-pdf-state', /.*/);
  await expect(page.locator('canvas')).toHaveCount(0);
});

// 썸네일 상자 비율(밴드 TRW10, 이슈 494-3): 2쪽만 가로로. TRW10_SHOTS 가 있으면 그 폴더에 1440·1280 그림.
const LANDSCAPE_PDF = Buffer.from(
  writePdf(
    Array.from({ length: 45 }, (_, n) => ({
      width: n === 1 ? 842 : 595,
      height: n === 1 ? 595 : 842,
      rotate: 0 as const,
      marks: [],
      texts: [{ x: 72, top: 72, size: 18, str: `Made-up page ${n + 1}` }],
      tables: [],
    })),
  ),
);
const frameBoxes = (page: Page, selector = '[data-thumb-frame]') =>
  page
    .locator(selector)
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().toJSON() as DOMRect),
    );
const expectSameHeights = (boxes: readonly DOMRect[]) => {
  const heights = boxes.map((box) => box.height);
  expect(Math.max(...heights) - Math.min(...heights)).toBeLessThanOrEqual(1);
};

for (const width of [1440, 1280]) {
  test(`TRW10 ${width}: 썸네일 상자 높이 — ready 직후·done·가로 쪽·칠한 뒤 모두 같다`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await fakeTranslationPdfApi(page);
    await signIn(page);
    await page.goto('/translation/pdf/new');
    await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
      name: 'made_up_report.pdf',
      mimeType: 'application/pdf',
      buffer: LANDSCAPE_PDF,
    });
    await expect(page.getByTestId('page-grid')).toHaveAttribute(
      'data-pdf-state',
      'ready',
    );
    await expect(page.locator('[data-thumb-frame]')).toHaveCount(40);
    expectSameHeights(await frameBoxes(page));
    await expect(page.locator('canvas[data-render-state="done"]')).toHaveCount(
      40,
    );

    const boxes = await frameBoxes(page);
    expect(boxes).toHaveLength(40);
    expectSameHeights(boxes);
    expect(
      Math.abs(boxes[0]!.height - boxes[0]!.width * 1.414),
    ).toBeLessThanOrEqual(1);
    const landscape = page.locator('[data-page="2"] canvas');
    const canvasRatio = await landscape.evaluate(
      (node: HTMLCanvasElement) => node.height / node.width,
    );
    expect(canvasRatio).toBeLessThan(1);
    expect(boxes[1]!.height).toBeCloseTo(boxes[0]!.height, 0);

    await page.locator('[data-page="1"]').scrollIntoViewIfNeeded();
    const firstRow = '[data-page]:nth-child(-n+10) [data-thumb-frame]';
    const before = (await frameBoxes(page, firstRow))[0]!.height;
    const from = await center(page.locator('[data-page="3"] canvas'));
    const to = await center(page.locator('[data-page="7"] canvas'));
    await page.mouse.move(from.x, from.y);
    await page.mouse.down();
    await page.mouse.move(to.x, to.y, { steps: 6 });
    await page.mouse.up();
    await expect(page.locator('[data-parts~="ceo"]')).toHaveCount(5);
    const painted = await frameBoxes(page, firstRow);
    expect(painted).toHaveLength(10);
    for (const box of painted)
      expect(Math.abs(box.height - before)).toBeLessThanOrEqual(1);
    if (process.env.TRW10_SHOTS)
      await page.screenshot({
        path: `${process.env.TRW10_SHOTS}/trw10-thumbs-${width}.png`,
      });
  });

  // 실패 꼴 흉내: 크기를 정하기 전에 실패한 캔버스(기본 속성 300×150) — 틀이 캔버스를 따르지 않는다.
  test(`TRW10 ${width}: 캔버스가 기본 크기 300×150 이어도 상자 높이 그대로`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await openPdfForm(page);
    const frame = page.locator('[data-page="1"] [data-thumb-frame]');
    const before = (await frame.boundingBox())!.height;
    await page
      .locator('[data-page="1"] canvas')
      .evaluate((node: HTMLCanvasElement) => {
        node.width = 300;
        node.height = 150;
      });
    const after = (await frame.boundingBox())!.height;
    expect(Math.abs(after - before)).toBeLessThanOrEqual(1);
  });
  test(`TRW10 ${width}: 한 쪽 그리기 실패 → 회색 상자가 틀 안을 덮는다 · 틀 높이 그대로`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (
        this: HTMLCanvasElement,
        ...args: Parameters<typeof original>
      ) {
        if (this.closest('[data-page="3"]') !== null)
          throw new Error('지어낸 그리기 실패');
        return original.apply(this, args);
      } as typeof original;
    });
    await fakeTranslationPdfApi(page);
    await signIn(page);
    await page.goto('/translation/pdf/new');
    await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
      name: 'made_up_report.pdf',
      mimeType: 'application/pdf',
      buffer: PDF,
    });
    await expect(
      page.locator('[data-page="3"] canvas[data-render-state="error"]'),
    ).toHaveCount(1);
    await expect(page.locator('canvas[data-render-state="done"]')).toHaveCount(
      39,
    );

    const frame = (await page
      .locator('[data-page="3"] [data-thumb-frame]')
      .boundingBox())!;
    const failed = page.locator('[data-page="3"] [data-thumb-failed]');
    const grey = (await failed.boundingBox())!;
    expect(grey.x).toBeGreaterThanOrEqual(frame.x);
    expect(grey.y).toBeGreaterThanOrEqual(frame.y);
    expect(grey.x + grey.width).toBeLessThanOrEqual(frame.x + frame.width);
    expect(grey.y + grey.height).toBeLessThanOrEqual(frame.y + frame.height);
    expect(Math.abs(grey.width - (frame.width - 2))).toBeLessThanOrEqual(1);
    expect(Math.abs(grey.height - (frame.height - 2))).toBeLessThanOrEqual(1);
    const color = await failed.evaluate(
      (node) => getComputedStyle(node).backgroundColor,
    );
    expect(color).not.toBe('rgba(0, 0, 0, 0)');
    expect(color).not.toBe('transparent');
    expectSameHeights(await frameBoxes(page));
  });
}
