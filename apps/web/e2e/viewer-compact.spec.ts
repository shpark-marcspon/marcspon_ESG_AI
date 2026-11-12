// 둘째 화면(src/pages/demo-viewer/CompactViewer.tsx)을 실제 브라우저에서 본다. 주소에 ?screen=compact 를 붙이면 뜬다.
//
// 보려는 것은 하나다: 화면을 갈아 끼워도(목록의 생김, 강조의 생김이 다르다) 강조가 PDF 의 그 자리에 놓인다.
// 자리는 화면이 아니라 헤드리스 컴포넌트(PageStack, HighlightOverlay)가 잡기 때문이다.
// 재는 법은 viewer.spec.ts 와 같다: 예시 PDF 는 강조할 자리에 색을 칠해 두었고, 조각 안쪽의 캔버스 픽셀이 그 색인지 본다.
// 본 화면의 클래스 이름(.dv-*)을 쓰지 않고 이름표(data-*)로만 찾는다.
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { readFileSync } from 'node:fs';

import { MARK_GRAY, MARK_GREEN, MARK_RED } from '../tools/sample-layout.ts';
import type { Rgb } from '../tools/sample-layout.ts';

interface SampleHighlight {
  id: string;
  documentId: string;
  page: number;
  box: [number, number, number, number];
  innerBox?: [number, number, number, number];
  innerBoxes?: [number, number, number, number][];
  kind: string;
}
const read = (name: string) =>
  JSON.parse(
    readFileSync(new URL(`../public/sample/${name}`, import.meta.url), 'utf8'),
  ) as { highlights: SampleHighlight[] };
const compare = read('compare.json');
const sentences = read('sentences.json');
const COLOR_OF_KIND: Record<string, Rgb> = {
  match: MARK_GREEN,
  mismatch: MARK_RED,
  unverified: MARK_GRAY,
};

const pane = (page: Page, documentId: string) =>
  page.locator(`[data-document-id="${documentId}"]`);
const pageBox = (paneLocator: Locator, pageNumber: number) =>
  paneLocator.locator(`[data-page="${pageNumber}"]`);
const item = (page: Page, itemId: string) =>
  page.locator(`[data-item-id="${itemId}"]`);
const near = (actual: number[], expected: Rgb, tolerance = 6) =>
  actual.every((value, i) => Math.abs(value - expected[i]!) <= tolerance);

async function open(page: Page, data: string, documentIds: string[]) {
  await page.goto(`/dev/viewer?data=sample/${data}&screen=compact`);
  for (const id of documentIds)
    await expect(pageBox(pane(page, id), 1).locator('canvas')).toHaveAttribute(
      'data-render-state',
      'done',
    );
  // 정말 둘째 화면이다: 본 화면의 클래스가 하나도 없다.
  await expect(page.locator('[class^="dv-"], [class*=" dv-"]')).toHaveCount(0);
}

/** 쪽 하나에 놓인 조각들의 자리(캔버스 왼쪽 위에서 잰 CSS 픽셀)와 조각 안팎의 캔버스 색. */
async function readMarks(pageLocator: Locator) {
  await expect(pageLocator.locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
  );
  return pageLocator.evaluate((pageElement) => {
    const canvas = pageElement.querySelector('canvas')!;
    const context = canvas.getContext('2d')!;
    const canvasRect = canvas.getBoundingClientRect();
    const density = canvas.width / canvasRect.width;
    const colorAt = (x: number, y: number) =>
      Array.from(
        context
          .getImageData(Math.round(x * density), Math.round(y * density), 1, 1)
          .data.slice(0, 3),
      );
    return [
      ...pageElement.querySelectorAll<HTMLElement>('[data-highlight-ids]'),
    ].map((element) => {
      const rect = element.getBoundingClientRect();
      const left = rect.left - canvasRect.left;
      const top = rect.top - canvasRect.top;
      const inset = 3;
      return {
        ids: element.dataset.highlightIds!.split(' '),
        left,
        top,
        width: rect.width,
        height: rect.height,
        inside: [
          colorAt(left + inset, top + inset),
          colorAt(left + rect.width - inset, top + rect.height - inset),
        ],
        outside: [
          colorAt(left - inset, top + rect.height / 2),
          colorAt(left + rect.width / 2, top - inset),
        ],
      };
    });
  });
}

for (const scale of [1, 1.5]) {
  test(`둘째 화면: 강조가 표시 위에 놓인다 (배율 ${scale})`, async ({
    page,
  }) => {
    await open(page, 'compare.json', ['a', 'b']);
    for (const documentId of ['a', 'b']) {
      const target = pane(page, documentId);
      for (
        let guard = 0;
        guard < 10 && Number(await target.getAttribute('data-scale')) < scale;
        guard++
      )
        await target.getByRole('button', { name: '확대' }).click();
      await expect(target).toHaveAttribute('data-scale', String(scale));

      const marks = await readMarks(pageBox(target, 1));
      expect(marks).toHaveLength(documentId === 'a' ? 4 : 3);
      for (const mark of marks) {
        const h = compare.highlights.find(
          (candidate) => candidate.id === mark.ids[0],
        )!;
        // 화면 자리 = 좌표 × 배율
        const [x0, y0, x1, y1] = h.innerBox ?? h.box;
        expect(mark.left).toBeCloseTo(x0 * scale, 0);
        expect(mark.top).toBeCloseTo(y0 * scale, 0);
        expect(mark.width).toBeCloseTo((x1 - x0) * scale, 0);
        expect(mark.height).toBeCloseTo((y1 - y0) * scale, 0);
        // 그 자리가 PDF 에 칠해 둔 자리다.
        const color = COLOR_OF_KIND[h.kind]!;
        for (const pixel of mark.inside)
          expect(
            near(pixel, color),
            `${mark.ids} 안쪽 ${pixel} 이 ${color} 여야 한다`,
          ).toBe(true);
        for (const pixel of mark.outside)
          expect(
            near(pixel, color),
            `${mark.ids} 바깥쪽 ${pixel} 이 ${color} 가 아니어야 한다`,
          ).toBe(false);
      }
    }
  });
}

test('둘째 화면: 생김은 다르고(상자가 아니라 밑줄) 동작은 같다(항목 ↔ 강조, 키보드)', async ({
  page,
}) => {
  await open(page, 'compare.json', ['a', 'b']);
  const first = pageBox(pane(page, 'a'), 1)
    .locator('[data-highlight-ids]')
    .first();
  // 본 화면의 조각은 바깥 선(outline)이 있고 아래 테두리가 없다. 여기는 그 반대다.
  expect(
    await first.evaluate((element) => [
      getComputedStyle(element).outlineStyle,
      getComputedStyle(element).borderBottomStyle,
      getComputedStyle(element).borderBottomWidth,
    ]),
  ).toEqual(['none', 'solid', '2px']);

  // 문서의 조각을 누르면 그 항목이 골라진다.
  const ids = (await first.getAttribute('data-highlight-ids'))!.split(' ');
  await first.click();
  const chosen = page.locator('[data-item-id][data-selected="true"]');
  await expect(chosen).toHaveCount(1);
  await expect(first).toHaveAttribute('data-selected', 'true');
  expect(
    await first.evaluate(
      (element) => getComputedStyle(element).borderBottomWidth,
    ),
  ).toBe('4px');
  const chosenId = (await chosen.getAttribute('data-item-id'))!;

  // j 로 다음 항목에 가면 앞의 조각은 골라진 표시를 잃는다.
  await page.keyboard.press('j');
  await expect(item(page, chosenId)).toHaveAttribute('data-selected', 'false');
  await expect(
    page.locator('[data-item-id][data-selected="true"]'),
  ).toHaveCount(1);
  await expect(
    pageBox(pane(page, 'a'), 1).locator(
      `[data-highlight-ids="${ids.join(' ')}"][data-selected="true"]`,
    ),
  ).toHaveCount(0);

  // 목록의 항목을 누르면 그 항목의 조각이 골라진 채 화면 안에 있다.
  await item(page, chosenId).locator('button').first().click();
  const again = pane(page, 'a')
    .locator('[data-highlight-ids][data-selected="true"]')
    .first();
  await expect(again).toBeInViewport();
});

test('둘째 화면: 두 줄에 걸친 문장 강조도 줄마다 조각 하나가 입력의 자리에 놓인다', async ({
  page,
}) => {
  await open(page, 'sentences.json', ['a']);
  const s4 = sentences.highlights.find((h) => h.id === 's4')!;
  expect(s4.innerBoxes!.length).toBe(2);
  // s4 를 가리키는 항목을 눌러 그 쪽으로 간다.
  const target = pane(page, 'a');
  await item(page, 's4').locator('button').first().click();
  const pieces = pageBox(target, s4.page).locator('[data-highlight-ids="s4"]');
  await expect(pieces).toHaveCount(2);
  await expect(pieces.first()).toHaveAttribute('data-selected', 'true');
  const canvas = (await pageBox(target, s4.page)
    .locator('canvas')
    .boundingBox())!;
  for (const [index, [x0, y0, x1, y1]] of s4.innerBoxes!.entries()) {
    const box = (await pieces.nth(index).boundingBox())!;
    expect(box.x - canvas.x).toBeCloseTo(x0, 0);
    expect(box.y - canvas.y).toBeCloseTo(y0, 0);
    expect(box.width).toBeCloseTo(x1 - x0, 0);
    expect(box.height).toBeCloseTo(y1 - y0, 0);
  }
});
