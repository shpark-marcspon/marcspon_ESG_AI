// 실제 브라우저에서: 코드로 만든 PDF 를 열어, 강조 상자가 놓인 자리에 정말 그 표시가 그려져 있는지 본다.
//
// 확인하는 방법이 둘이다.
//   (가) 상자의 화면 자리 = 입력의 좌표 × 배율 인가(여기서 따로 셈한다. 뷰어의 geometry.ts 를 쓰지 않는다)
//   (나) 그 자리의 캔버스 픽셀이 PDF 에 칠해 둔 색인가(pdf.js 가 그린 것과 뷰어가 놓은 상자가 서로 맞는가)
// (나)는 뷰어 코드도 테스트의 셈도 믿지 않고 그려진 결과만 본다.
//
// 기다릴 때는 시간을 재지 않고 상태를 묻는다: 캔버스의 data-render-state, 칸의 data-current-page.
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
  kind: 'match' | 'mismatch' | 'unverified';
}
const sample = JSON.parse(
  readFileSync(
    new URL('../public/sample/compare.json', import.meta.url),
    'utf8',
  ),
) as {
  highlights: SampleHighlight[];
};
const COLOR_OF_KIND: Record<SampleHighlight['kind'], Rgb> = {
  match: MARK_GREEN,
  mismatch: MARK_RED,
  unverified: MARK_GRAY,
};

const pane = (page: Page, documentId: string) =>
  page.locator(`.dv-pane[data-document-id="${documentId}"]`);
const pageBox = (paneLocator: Locator, pageNumber: number) =>
  paneLocator.locator(`.dv-page[data-page="${pageNumber}"]`);
const item = (page: Page, itemId: string) =>
  page.locator(`.dv-item[data-item-id="${itemId}"]`);

async function openSample(page: Page) {
  await page.goto('/dev/viewer?data=sample/compare.json');
  await expect(pageBox(pane(page, 'a'), 1).locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
  );
  await expect(pageBox(pane(page, 'b'), 1).locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
  );
}

/** 쪽 하나에 놓인 상자들의 자리(캔버스 왼쪽 위에서 잰 CSS 픽셀)와, 상자 안팎 몇 점의 캔버스 색. */
async function readPage(pageLocator: Locator) {
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
    return [...pageElement.querySelectorAll<HTMLElement>('.dv-highlight')].map(
      (element) => {
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
          // 네 귀퉁이의 바로 안쪽(글자가 없는 곳).
          inside: [
            colorAt(left + inset, top + inset),
            colorAt(left + rect.width - inset, top + inset),
            colorAt(left + inset, top + rect.height - inset),
            colorAt(left + rect.width - inset, top + rect.height - inset),
          ],
          // 네 변의 바로 바깥쪽.
          outside: [
            colorAt(left - inset, top + rect.height / 2),
            colorAt(left + rect.width / 2, top - inset),
          ],
        };
      },
    );
  });
}

const near = (actual: number[], expected: Rgb, tolerance = 6) =>
  actual.every((value, i) => Math.abs(value - expected[i]!) <= tolerance);

/** 그 쪽의 상자마다: 안쪽은 칠해 둔 색이고, 바깥쪽은 그 색이 아니다. */
async function expectBoxesOnMarks(pageLocator: Locator, expectedCount: number) {
  const boxes = await readPage(pageLocator);
  expect(boxes).toHaveLength(expectedCount);
  for (const box of boxes) {
    const kind = sample.highlights.find((h) => h.id === box.ids[0])!.kind;
    const color = COLOR_OF_KIND[kind];
    for (const pixel of box.inside)
      expect(
        near(pixel, color),
        `${box.ids} 안쪽 ${pixel} 이 ${color} 여야 한다`,
      ).toBe(true);
    for (const pixel of box.outside)
      expect(
        near(pixel, color),
        `${box.ids} 바깥쪽 ${pixel} 이 ${color} 가 아니어야 한다`,
      ).toBe(false);
  }
  return boxes;
}

async function setZoom(page: Page, documentId: string, scale: number) {
  const target = pane(page, documentId);
  for (let guard = 0; guard < 10; guard++) {
    const current = Number(await target.getAttribute('data-scale'));
    if (current === scale) return;
    await target
      .getByRole('button', { name: current < scale ? '확대' : '축소' })
      .click();
  }
  throw new Error(`배율 ${scale} 에 닿지 못했다`);
}

for (const scale of [1, 1.5, 0.75]) {
  test(`강조 상자가 표시 위에 놓인다 (배율 ${scale})`, async ({ page }) => {
    await openSample(page);
    for (const documentId of ['a', 'b']) {
      await setZoom(page, documentId, scale);
      const boxes = await expectBoxesOnMarks(
        pageBox(pane(page, documentId), 1),
        documentId === 'a' ? 4 : 3,
      );

      // (가) 화면 자리 = 좌표 × 배율
      for (const box of boxes) {
        const h = sample.highlights.find(
          (candidate) => candidate.id === box.ids[0],
        )!;
        const [x0, y0, x1, y1] = h.innerBox ?? h.box;
        expect(box.left).toBeCloseTo(x0 * scale, 0);
        expect(box.top).toBeCloseTo(y0 * scale, 0);
        expect(box.width).toBeCloseTo((x1 - x0) * scale, 0);
        expect(box.height).toBeCloseTo((y1 - y0) * scale, 0);
      }
    }
  });
}

test('쪽 자체가 돌아간 PDF(/Rotate 90)와, 보는 사람이 돌린 화면에서도 상자가 표시 위에 놓인다', async ({
  page,
}) => {
  await openSample(page);
  const a = pane(page, 'a');

  // 항목 6 은 A 의 3쪽(돌아간 쪽)을 가리킨다.
  await item(page, '6').getByRole('button').first().click();
  await expect(a).toHaveAttribute('data-current-page', '3');
  await expectBoxesOnMarks(pageBox(a, 3), 1);

  // 화면을 시계 방향으로 90도씩 돌려 가며 3쪽과 1쪽을 다시 본다.
  for (const rotation of [90, 180, 270]) {
    await a.getByRole('button', { name: '시계 방향으로 돌리기' }).click();
    await expect(a).toHaveAttribute('data-rotation', String(rotation));
    await item(page, '6').getByRole('button').first().click();
    await expectBoxesOnMarks(pageBox(a, 3), 1);
    await item(page, '1').getByRole('button').first().click();
    await expect(a).toHaveAttribute('data-current-page', '1');
    await expectBoxesOnMarks(pageBox(a, 1), 4);
  }
});

test('좁힌 자리를 끄면 표·문단 전체 상자로 그린다', async ({ page }) => {
  await openSample(page);
  await page.getByLabel(/좁힌 자리로 보기/).uncheck();
  // A 의 1쪽: 표 상자 하나(강조 셋이 겹침)와 문단 상자 하나.
  const boxes = await readPage(pageBox(pane(page, 'a'), 1));
  expect(boxes.map((box) => box.ids.length).sort()).toEqual([1, 3]);
  const table = boxes.find((box) => box.ids.length === 3)!;
  expect(
    [table.left, table.top, table.width, table.height].map(Math.round),
  ).toEqual([72, 200, 450, 120]);
});

test('항목과 상자가 서로 이어지고, 키보드로 다음·이전 항목에 간다', async ({
  page,
}) => {
  await openSample(page);
  const a = pane(page, 'a');
  const b = pane(page, 'b');
  const selectedIds = (target: Locator) =>
    target
      .locator('.dv-highlight[data-selected="true"]')
      .evaluateAll((elements) =>
        elements.map(
          (element) => (element as HTMLElement).dataset.highlightIds,
        ),
      );

  // 항목 → 상자: 항목 5 를 누르면 두 문서가 모두 2쪽으로 가고 그 강조가 골라진다.
  await item(page, '5').getByRole('button').first().click();
  await expect(a).toHaveAttribute('data-current-page', '2');
  await expect(b).toHaveAttribute('data-current-page', '2');
  expect(await selectedIds(a)).toEqual(['5-a']);
  expect(await selectedIds(b)).toEqual(['5-b']);
  await expect(
    a.locator('.dv-highlight[data-selected="true"]'),
  ).toBeInViewport();
  await expect(
    b.locator('.dv-highlight[data-selected="true"]'),
  ).toBeInViewport();

  // 상자 → 항목: A 의 1쪽으로 돌아가 「2-a」 상자를 누르면 항목 2 가 골라지고 B 도 따라온다.
  await a.getByRole('button', { name: '이전 페이지' }).click();
  await expect(a).toHaveAttribute('data-current-page', '1');
  await a.locator('.dv-highlight[data-highlight-ids="2-a"]').click();
  await expect(item(page, '2')).toHaveAttribute('data-selected', 'true');
  await expect(b).toHaveAttribute('data-current-page', '1');
  expect(await selectedIds(b)).toEqual(['2-b']);

  // 겹친 상자: B 의 같은 칸을 항목 1 과 4 가 가리킨다. 누를 때마다 다음 항목으로 돈다.
  const shared = b.locator('.dv-highlight[data-highlight-ids="1-b 4-b"]');
  await shared.click();
  await expect(item(page, '1')).toHaveAttribute('data-selected', 'true');
  await shared.click();
  await expect(item(page, '4')).toHaveAttribute('data-selected', 'true');

  // 키보드: j 는 다음, k 는 이전.
  await page.keyboard.press('j');
  await expect(item(page, '5')).toHaveAttribute('data-selected', 'true');
  await expect(a).toHaveAttribute('data-current-page', '2');
  await page.keyboard.press('k');
  await page.keyboard.press('k');
  await expect(item(page, '3')).toHaveAttribute('data-selected', 'true');
  await expect(a).toHaveAttribute('data-current-page', '1');
  expect(await selectedIds(a)).toEqual(['3-a']);
});

test('크게 확대해 쪽이 칸보다 넓어도, 골라진 상자가 통째로 화면에 들어온다', async ({
  page,
}) => {
  await openSample(page);
  for (const documentId of ['a', 'b']) await setZoom(page, documentId, 2);
  for (const itemId of ['2', '5', '1']) {
    await item(page, itemId).getByRole('button').first().click();
    for (const documentId of ['a', 'b']) {
      await expect(
        pane(page, documentId).locator('.dv-highlight[data-selected="true"]'),
      ).toBeInViewport({ ratio: 1 });
    }
  }
});

test('검토 상태: 사유 없이는 반려되지 않고, 사유를 적으면 반려되고, 되돌릴 수 있다', async ({
  page,
}) => {
  await openSample(page);
  const target = item(page, '2');
  await target.getByRole('button').first().click();

  await target.getByRole('button', { name: '반려' }).click();
  await expect(target.getByRole('alert')).toContainText('사유');
  await expect(target.locator('.dv-status')).toHaveText('검토대기');

  await target.getByLabel('반려 사유').fill('단위가 다르다');
  await target.getByRole('button', { name: '반려' }).click();
  await expect(target.locator('.dv-status')).toHaveText('반려');
  await expect(target).toContainText('단위가 다르다');

  await target.getByRole('button', { name: '검토대기로 되돌리기' }).click();
  await expect(target.locator('.dv-status')).toHaveText('검토대기');
  await target.getByRole('button', { name: '확정' }).click();
  await expect(target.locator('.dv-status')).toHaveText('확정');
});

test('문서 하나만 놓는 배치로도 뜬다(문장 강조 예시)', async ({ page }) => {
  await page.goto('/dev/viewer?data=sample/sentences.json');
  await expect(page.locator('.dv-root')).toHaveAttribute(
    'data-layout',
    'single',
  );
  await expect(page.locator('.dv-pane')).toHaveCount(1);
  await expect(page.locator('.dv-notice')).toContainText('가짜 자료');
  await item(page, 's3').getByRole('button').first().click();
  await expect(pane(page, 'a')).toHaveAttribute('data-current-page', '2');
  await expect(
    pane(page, 'a').locator('.dv-highlight[data-selected="true"]'),
  ).toBeInViewport();
});

// ── 강조의 보기 방식 ──
// 「채움이 없다」를 DOM 의 값이 아니라 화면의 픽셀로 본다:
//   상자의 한가운데에서, 화면에 실제로 보이는 색(화면 캡처)과 쪽의 원래 그림(캔버스에서 읽은 색)을 견준다.
//   채움이 없으면 둘이 같고, 채움이 있으면(종류 색을 14~18% 섞는다) 다르다.
// 화면 조건(픽셀 밀도 1, 배율 1)에서 캔버스의 한 픽셀이 화면의 한 픽셀이라 수치가 흔들리지 않는다.

interface CenterColors {
  ids: string;
  selected: boolean;
  pointed: boolean;
  /** 화면에 보이는 색과 쪽 그림의 색이 가장 많이 다른 채널의 차이(0~255). */
  difference: number;
}

/** 그 문서 칸에서 한가운데가 화면에 보이는 상자마다, 한가운데(에서 가장 가까운 평평한 자리)의 「화면 색 − 쪽 그림 색」. 스크롤 밖의 상자(앞뒤 쪽의 것)는 캡처에 없어 뺀다. */
async function centerColors(
  page: Page,
  documentId: string,
): Promise<CenterColors[]> {
  const target = pane(page, documentId);
  await expect(
    target.locator('canvas[data-render-state="done"]').first(),
  ).toBeVisible();
  const shot = (await page.screenshot()).toString('base64');
  return target.evaluate(async (paneElement, png) => {
    const bitmap = await createImageBitmap(
      await (await fetch(`data:image/png;base64,${png}`)).blob(),
    );
    const screenCanvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    const screenContext = screenCanvas.getContext('2d')!;
    screenContext.drawImage(bitmap, 0, 0);
    const view = paneElement
      .querySelector('.dv-scroller')!
      .getBoundingClientRect();
    const centerOf = (element: HTMLElement) => {
      const rect = element.getBoundingClientRect();
      return {
        x: Math.round(rect.left + rect.width / 2),
        y: Math.round(rect.top + rect.height / 2),
      };
    };
    const onScreen = (element: HTMLElement) => {
      const { x, y } = centerOf(element);
      return (
        x > view.left &&
        x < view.right &&
        y > view.top &&
        y < Math.min(view.bottom, bitmap.height)
      );
    };
    return [...paneElement.querySelectorAll<HTMLElement>('.dv-highlight')]
      .filter(onScreen)
      .map((element) => {
        const center = centerOf(element);
        const rect = element.getBoundingClientRect();
        const canvas = element.closest('.dv-page')!.querySelector('canvas')!;
        const canvasRect = canvas.getBoundingClientRect();
        const context = canvas.getContext('2d')!;
        // 쪽이 반 픽셀 자리에 놓이면(가운데 맞춤) 글자의 가장자리 픽셀은 화면에서 옆 픽셀과 섞인다. 채움과 무관하게 색이 달라지므로,
        // 한가운데에서 가장 가까운 「쪽 그림이 평평한 자리」(둘레 5×5 픽셀이 한 색)를 찾아 거기서 견준다.
        const flatAt = (x: number, y: number) => {
          const data = context.getImageData(
            Math.round(x - canvasRect.left) - 2,
            Math.round(y - canvasRect.top) - 2,
            5,
            5,
          ).data;
          for (let at = 4; at < data.length; at += 4)
            if (
              data[at] !== data[0] ||
              data[at + 1] !== data[1] ||
              data[at + 2] !== data[2]
            )
              return null;
          return [data[0]!, data[1]!, data[2]!];
        };
        let point = center;
        let original: number[] | null = null;
        search: for (
          let reach = 0;
          reach < Math.max(rect.width, rect.height) / 2 - 4;
          reach++
        ) {
          for (const [dx, dy] of [
            [0, 0],
            [reach, 0],
            [-reach, 0],
            [0, reach],
            [0, -reach],
          ] as const) {
            const x = center.x + dx;
            const y = center.y + dy;
            if (
              Math.abs(dx) > rect.width / 2 - 4 ||
              Math.abs(dy) > rect.height / 2 - 4
            )
              continue;
            original = flatAt(x, y);
            if (original) {
              point = { x, y };
              break search;
            }
          }
        }
        if (!original)
          throw new Error(
            `${element.dataset.highlightIds}: 상자 안에 평평한 자리가 없다`,
          );
        const seen = screenContext.getImageData(point.x, point.y, 1, 1).data;
        return {
          ids: element.dataset.highlightIds!,
          selected: element.dataset.selected === 'true',
          pointed: element.dataset.pointed === 'true',
          difference: Math.max(
            Math.abs(seen[0]! - original[0]!),
            Math.abs(seen[1]! - original[1]!),
            Math.abs(seen[2]! - original[2]!),
          ),
        };
      });
  }, shot);
}

/** 채움이 없다고 치는 한계(캡처의 색 반올림 여유)와, 채움이 있다고 치는 한계. 14% 섞으면 가장 덜 변하는 종류도 채널 하나가 15 넘게 움직인다. */
const NO_FILL = 2;
const FILLED = 8;

async function openMode(page: Page, mode: string) {
  await page.goto(
    `/dev/viewer?data=sample/compare.json${mode ? `&mode=${mode}` : ''}`,
  );
  await expect(pageBox(pane(page, 'a'), 1).locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
  );
  await expect(pageBox(pane(page, 'b'), 1).locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
  );
  // 마우스가 상자 위에 놓여 있지 않게 한다(올리면 채워진다).
  await page.mouse.move(2, 2);
}

test('옅게(기본값): 고르지 않은 상자의 한가운데 픽셀은 쪽의 원래 그림 그대로다(채움이 없다). 전체 채움에서는 다르다', async ({
  page,
}) => {
  // 보기 방식을 주소에 적지 않았다. 기본값이 옅게다.
  await openMode(page, '');
  await expect(page.locator('.dv-highlights').first()).toHaveAttribute(
    'data-mode',
    'outline',
  );
  // 문서 칸이 쪽보다 좁아(화면 1400 에 칸 둘) 오른쪽 열의 상자는 가로 스크롤 밖에 있다. 처음 화면에 보이는 것은 넷이다.
  const SHOWN = ['3-a', '3-b', '4-a', '5-b'];
  const outline = [
    ...(await centerColors(page, 'a')),
    ...(await centerColors(page, 'b')),
  ];
  expect(outline.map((box) => box.ids).sort()).toEqual(SHOWN);
  for (const box of outline)
    expect(
      box.difference,
      `옅게: ${box.ids} 의 한가운데가 쪽 그림과 달라졌다(차이 ${box.difference})`,
    ).toBeLessThanOrEqual(NO_FILL);

  // 같은 재는 법이 채움을 볼 수 있는지: 전체 채움에서는 모든 상자의 한가운데가 달라져야 한다.
  await openMode(page, 'fill');
  const fill = [
    ...(await centerColors(page, 'a')),
    ...(await centerColors(page, 'b')),
  ];
  expect(fill.map((box) => box.ids).sort()).toEqual(SHOWN);
  for (const box of fill)
    expect(
      box.difference,
      `전체 채움: ${box.ids} 의 한가운데가 쪽 그림 그대로다(차이 ${box.difference})`,
    ).toBeGreaterThanOrEqual(FILLED);

  // 가로로 밀어 나머지 상자도 본다(A 의 표 오른쪽 열, B 의 겹친 칸): 옅게에서는 역시 채움이 없다.
  await openMode(page, 'outline');
  for (const documentId of ['a', 'b'])
    await pane(page, documentId)
      .locator('.dv-scroller')
      .evaluate((element) => (element.scrollLeft = element.scrollWidth));
  const right = [
    ...(await centerColors(page, 'a')),
    ...(await centerColors(page, 'b')),
  ];
  expect(right.map((box) => box.ids).sort()).toEqual(
    expect.arrayContaining(['1-a', '1-b 4-b', '2-a', '2-b']),
  );
  for (const box of right)
    expect(
      box.difference,
      `옅게(오른쪽): ${box.ids} (차이 ${box.difference})`,
    ).toBeLessThanOrEqual(NO_FILL);
});

test('옅게: 고르지 않은 상자에도 선이 있고(상자의 바깥에), 그 선은 상자 안으로 들어오지 않는다', async ({
  page,
}) => {
  // 화면 대 화면으로 견준다: 상자가 하나도 없는 화면(「고른 것만」, 아무것도 고르지 않음)과 옅게의 화면.
  // (쪽 그림과 견주면 안 된다. 상자의 변이 곧 색이 바뀌는 자리라, 쪽이 반 픽셀 자리에 놓이면 선이 없어도 색이 다르게 읽힌다.)
  await openMode(page, 'selected');
  await expect(page.locator('.dv-highlight')).toHaveCount(0);
  const bare = (await page.screenshot()).toString('base64');
  await openMode(page, 'outline');
  const withBoxes = (await page.screenshot()).toString('base64');

  // 상자 3-a 의 왼쪽 변 둘레를 가로로 훑는다: 변의 바깥 3픽셀과, 안쪽 2~4픽셀째에서 두 화면의 색 차이.
  const edge = await pane(page, 'a')
    .locator('.dv-highlight[data-highlight-ids="3-a"]')
    .evaluate(
      async (element, [first, second]) => {
        const read = async (png: string) => {
          const bitmap = await createImageBitmap(
            await (await fetch(`data:image/png;base64,${png}`)).blob(),
          );
          const context = new OffscreenCanvas(
            bitmap.width,
            bitmap.height,
          ).getContext('2d')!;
          context.drawImage(bitmap, 0, 0);
          return context;
        };
        const [before, after] = [await read(first!), await read(second!)];
        const rect = element.getBoundingClientRect();
        const y = Math.round(rect.top + rect.height / 2);
        const differenceAt = (x: number) => {
          const one = before.getImageData(x, y, 1, 1).data;
          const other = after.getImageData(x, y, 1, 1).data;
          return Math.max(
            Math.abs(one[0]! - other[0]!),
            Math.abs(one[1]! - other[1]!),
            Math.abs(one[2]! - other[2]!),
          );
        };
        const left = Math.round(rect.left);
        return {
          outside: [left - 3, left - 2, left - 1].map(differenceAt),
          inside: [left + 1, left + 2, left + 3].map(differenceAt),
        };
      },
      [bare, withBoxes],
    );
  // 바깥 3픽셀 어딘가에 선이 있다(반 픽셀 자리에 걸쳐도 한 픽셀은 뚜렷이 달라진다). 안쪽은 상자가 없을 때와 같다.
  expect(
    Math.max(...edge.outside),
    `바깥쪽 차이 ${edge.outside}`,
  ).toBeGreaterThanOrEqual(FILLED * 2);
  expect(
    Math.max(...edge.inside),
    `안쪽 차이 ${edge.inside}`,
  ).toBeLessThanOrEqual(NO_FILL);
});

test('옅게: 고른 항목의 상자와 목록에서 마우스를 올린 항목의 상자만 채워진다. 떼면 돌아온다', async ({
  page,
}) => {
  await openMode(page, 'outline');
  const a = pane(page, 'a');

  // 항목 2 를 고른다 → A 의 1쪽에서 2-a 만 채워진다.
  await item(page, '2').locator('.dv-item-head').click();
  await expect(
    a.locator('.dv-highlight[data-highlight-ids="2-a"]'),
  ).toHaveAttribute('data-selected', 'true');
  await page.mouse.move(2, 2);
  // 방금 누른 단추에 초점이 남아 있다. 초점을 떼어 「가리킨」 표시를 지운다.
  await page.evaluate(() =>
    (document.activeElement as HTMLElement | null)?.blur(),
  );
  let boxes = await centerColors(page, 'a');
  expect(
    boxes.filter((box) => box.difference >= FILLED).map((box) => box.ids),
  ).toEqual(['2-a']);
  expect(
    boxes.filter((box) => box.difference > NO_FILL && box.difference < FILLED),
  ).toEqual([]);

  // 항목 3 에 마우스를 올린다 → 3-a 도 채워진다. 고르지도 스크롤하지도 않는다.
  const scrollBefore = await a
    .locator('.dv-scroller')
    .evaluate((element) => element.scrollTop);
  await item(page, '3').locator('.dv-item-head').hover();
  await expect(
    a.locator('.dv-highlight[data-highlight-ids="3-a"]'),
  ).toHaveAttribute('data-pointed', 'true');
  boxes = await centerColors(page, 'a');
  expect(
    boxes
      .filter((box) => box.difference >= FILLED)
      .map((box) => box.ids)
      .sort(),
  ).toEqual(['2-a', '3-a']);
  await expect(item(page, '3')).toHaveAttribute('data-selected', 'false');
  expect(
    await a.locator('.dv-scroller').evaluate((element) => element.scrollTop),
  ).toBe(scrollBefore);

  // 마우스를 떼면 3-a 는 다시 채움이 없다.
  await page.mouse.move(2, 2);
  await expect(
    a.locator('.dv-highlight[data-highlight-ids="3-a"]'),
  ).toHaveAttribute('data-pointed', 'false');
  boxes = await centerColors(page, 'a');
  expect(
    boxes.filter((box) => box.difference >= FILLED).map((box) => box.ids),
  ).toEqual(['2-a']);

  // 문서의 상자 위에 직접 마우스를 올려도 그 상자가 채워진다.
  await a.locator('.dv-highlight[data-highlight-ids="1-a"]').hover();
  boxes = await centerColors(page, 'a');
  expect(
    boxes
      .filter((box) => box.difference >= FILLED)
      .map((box) => box.ids)
      .sort(),
  ).toEqual(['1-a', '2-a']);
});

test('고른 것만: 고르기 전에는 상자가 없고, 고른 항목의 상자만 그린다. 안내 글이 보인다', async ({
  page,
}) => {
  await openMode(page, 'selected');
  await expect(page.locator('.dv-highlight')).toHaveCount(0);
  await expect(page.getByTestId('dv-mode-note')).toBeVisible();
  await expect(page.getByTestId('dv-mode-note')).toContainText(
    '눌러 고를 수 없',
  );

  await item(page, '2').locator('.dv-item-head').click();
  await expect(page.locator('.dv-highlight')).toHaveCount(2);
  await expect(pane(page, 'a').locator('.dv-highlight')).toHaveAttribute(
    'data-highlight-ids',
    '2-a',
  );
  await expect(pane(page, 'b').locator('.dv-highlight')).toHaveAttribute(
    'data-highlight-ids',
    '2-b',
  );
  // 다른 항목의 상자가 있던 자리(1-a 의 한가운데)를 눌러도 아무것도 골라지지 않는다.
  const [x0, y0, x1, y1] = sample.highlights.find(
    (h) => h.id === '1-a',
  )!.innerBox!;
  await pageBox(pane(page, 'a'), 1).click({
    position: { x: (x0 + x1) / 2, y: (y0 + y1) / 2 },
  });
  await expect(item(page, '2')).toHaveAttribute('data-selected', 'true');
  await expect(item(page, '1')).toHaveAttribute('data-selected', 'false');

  // 띠의 조작으로 방식을 바꾸면 주소에도 적히고 상자가 다시 나온다.
  await page.getByRole('radio', { name: '옅게' }).check();
  await expect(
    pageBox(pane(page, 'a'), 1).locator('.dv-highlight'),
  ).toHaveCount(4);
  expect(new URL(page.url()).searchParams.get('mode')).toBeNull();
  await page.getByRole('radio', { name: '전체 채움' }).check();
  expect(new URL(page.url()).searchParams.get('mode')).toBe('fill');
  await expect(page.getByTestId('dv-mode-note')).toHaveCount(0);
});

test('범례에서 종류를 끄면 그 종류의 상자가 사라지고, 고른 항목의 상자는 남는다. 겹친 상자는 남은 것만 돈다', async ({
  page,
}) => {
  await openMode(page, 'outline');
  const a = pane(page, 'a');
  const b = pane(page, 'b');
  // 1쪽의 상자만 센다(아래 2쪽도 미리 그려져 있다).
  const idsIn = (target: Locator) =>
    pageBox(target, 1)
      .locator('.dv-highlight')
      .evaluateAll((elements) =>
        elements
          .map((element) => (element as HTMLElement).dataset.highlightIds)
          .sort(),
      );
  expect(await idsIn(a)).toEqual(['1-a', '2-a', '3-a', '4-a']);

  // 「불일치」를 끈다(뷰어에게는 그저 종류 하나다).
  const mismatch = page.locator('.dv-kind[data-kind="mismatch"]');
  await mismatch.click();
  await expect(mismatch).toHaveAttribute('aria-pressed', 'false');
  expect(await idsIn(a)).toEqual(['1-a', '3-a', '4-a']);
  expect(await idsIn(b)).toEqual(['1-b 4-b', '3-b']);
  await expect(item(page, '2')).toHaveAttribute('data-kind-hidden', 'true');
  await expect(item(page, '1')).toHaveAttribute('data-kind-hidden', 'false');

  // 꺼진 종류의 항목을 고르면 그 상자는 보인다.
  await item(page, '2').locator('.dv-item-head').click();
  expect(await idsIn(a)).toEqual(['1-a', '2-a', '3-a', '4-a']);
  await expect(
    a.locator('.dv-highlight[data-highlight-ids="2-a"]'),
  ).toHaveAttribute('data-selected', 'true');

  // 「일치」를 끄면 B 의 겹친 상자(항목 1 과 4, 둘 다 일치)가 사라진다. 다시 켜면 돌아와 누를 때마다 돈다.
  const match = page.locator('.dv-kind[data-kind="match"]');
  await match.click();
  expect(await idsIn(b)).toEqual(['2-b']);
  await match.click();
  const shared = b.locator('.dv-highlight[data-highlight-ids="1-b 4-b"]');
  await shared.click();
  await expect(item(page, '1')).toHaveAttribute('data-selected', 'true');
  await shared.click();
  await expect(item(page, '4')).toHaveAttribute('data-selected', 'true');

  await mismatch.click();
  await expect(mismatch).toHaveAttribute('aria-pressed', 'true');
  expect(await idsIn(a)).toEqual(['1-a', '2-a', '3-a', '4-a']);
});

// ── 강조 하나에 상자 여럿: 두 줄에 걸친 문장 ──
// 예시 PDF 의 2쪽에 두 줄짜리 문단이 있고, 문장 강조 예시의 s4 가 그 둘째 문장을 줄마다 상자 하나로 가리킨다
// (상자는 글자 폭 표로 셈한 것이다. tools/sample-places.ts). 여기서는 그 상자가 「그려진 글자」 위에 놓였는지를 캔버스의 픽셀로 잰다:
// 상자 안에서 글자의 잉크(어두운 픽셀)가 차지한 범위를 찾아 상자의 네 변과의 틈을 CSS 픽셀로 낸다. 뷰어의 셈도 테스트의 셈도 쓰지 않는다.
const sentences = JSON.parse(
  readFileSync(
    new URL('../public/sample/sentences.json', import.meta.url),
    'utf8',
  ),
) as {
  highlights: {
    id: string;
    page: number;
    box: number[];
    innerBoxes?: number[][];
  }[];
};
const S4 = sentences.highlights.find((h) => h.id === 's4')!;

interface InkGaps {
  /** 조각의 화면 자리(캔버스 왼쪽 위에서 잰 CSS 픽셀). */
  rect: { left: number; top: number; width: number; height: number };
  /** 상자의 변에서 안쪽으로 잉크가 처음 나오는 데까지의 틈(CSS 픽셀). 잉크가 없으면 null. */
  gaps: { left: number; right: number; top: number; bottom: number } | null;
  /** 상자 바로 바깥의 띠에 있는 잉크 픽셀 수: 왼쪽·오른쪽은 폭 2px, 위·아래는 높이 2px. 상자가 글자를 딱 덮으면 0 이다. */
  outside: { left: number; right: number; top: number; bottom: number };
}

/** 그 강조의 조각마다, 캔버스에서 잉크의 범위를 읽는다. */
async function inkOfPieces(
  pageLocator: Locator,
  highlightId: string,
): Promise<InkGaps[]> {
  await expect(pageLocator.locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
  );
  return pageLocator.evaluate((pageElement, id) => {
    const canvas = pageElement.querySelector('canvas')!;
    const context = canvas.getContext('2d')!;
    const canvasRect = canvas.getBoundingClientRect();
    const density = canvas.width / canvasRect.width;
    const image = context.getImageData(0, 0, canvas.width, canvas.height);
    // 잉크 = 어두운 픽셀(검은 글자). 글자 가장자리의 옅은 회색(계단 지우기)은 세지 않는다.
    const isInk = (x: number, y: number) => {
      if (x < 0 || y < 0 || x >= image.width || y >= image.height) return false;
      const at = (y * image.width + x) * 4;
      return (
        image.data[at]! + image.data[at + 1]! + image.data[at + 2]! < 3 * 110
      );
    };
    const count = (x0: number, y0: number, x1: number, y1: number) => {
      let n = 0;
      for (let y = Math.round(y0 * density); y < Math.round(y1 * density); y++)
        for (
          let x = Math.round(x0 * density);
          x < Math.round(x1 * density);
          x++
        )
          if (isInk(x, y)) n += 1;
      return n;
    };
    return [
      ...pageElement.querySelectorAll<HTMLElement>(
        `.dv-highlight[data-highlight-ids="${id}"]`,
      ),
    ].map((element) => {
      const box = element.getBoundingClientRect();
      const rect = {
        left: box.left - canvasRect.left,
        top: box.top - canvasRect.top,
        width: box.width,
        height: box.height,
      };
      const right = rect.left + rect.width;
      const bottom = rect.top + rect.height;
      let minX = Infinity,
        maxX = -Infinity,
        minY = Infinity,
        maxY = -Infinity;
      for (
        let y = Math.round(rect.top * density);
        y < Math.round(bottom * density);
        y++
      ) {
        for (
          let x = Math.round(rect.left * density);
          x < Math.round(right * density);
          x++
        ) {
          if (!isInk(x, y)) continue;
          minX = Math.min(minX, x);
          maxX = Math.max(maxX, x);
          minY = Math.min(minY, y);
          maxY = Math.max(maxY, y);
        }
      }
      const gaps =
        Number.isFinite(minX) ?
          {
            left: minX / density - rect.left,
            right: right - (maxX + 1) / density,
            top: minY / density - rect.top,
            bottom: bottom - (maxY + 1) / density,
          }
        : null;
      const outside = {
        left: count(rect.left - 2, rect.top, rect.left, bottom),
        right: count(right, rect.top, right + 2, bottom),
        top: count(rect.left, rect.top - 2, right, rect.top),
        bottom: count(rect.left, bottom, right, bottom + 2),
      };
      return { rect, gaps, outside };
    });
  }, highlightId);
}

for (const scale of [1, 1.5]) {
  test(`두 줄에 걸친 문장 강조: 줄마다 상자 하나가 글자 위에 놓인다 (배율 ${scale})`, async ({
    page,
  }) => {
    await page.goto('/dev/viewer?data=sample/sentences.json');
    const a = pane(page, 'a');
    await setZoom(page, 'a', scale);
    await item(page, 's4').getByRole('button').first().click();
    await expect(a).toHaveAttribute('data-current-page', '2');

    const pieces = await inkOfPieces(pageBox(a, 2), 's4');
    // 조각은 둘이다. 첫 것만 그리거나, 둘을 감싼 큰 상자 하나로 그리면 여기서 걸린다.
    expect(pieces).toHaveLength(2);
    S4.innerBoxes!.forEach(([x0, y0, x1, y1], index) => {
      const { rect, gaps, outside } = pieces[index]!;
      // (가) 화면 자리 = 입력의 좌표 × 배율
      expect(rect.left).toBeCloseTo(x0! * scale, 0);
      expect(rect.top).toBeCloseTo(y0! * scale, 0);
      expect(rect.width).toBeCloseTo((x1! - x0!) * scale, 0);
      expect(rect.height).toBeCloseTo((y1! - y0!) * scale, 0);
      // 잉크는 픽셀 단위로 읽고 상자의 변은 소수 자리에 놓인다(배율 1.5). 그래서 반 픽셀까지는 재는 쪽의 격자 탓이다.
      const HALF_PIXEL = 0.5;
      // (나) 그 안의 잉크: 왼쪽·오른쪽 변에서 글자까지의 틈이 글자 옆 여백(1pt 안팎)만큼이고, 위·아래는 글꼴의 줄 높이만큼 넉넉하다.
      expect(gaps, `조각 ${index} 안에 잉크가 있어야 한다`).not.toBeNull();
      expect(gaps!.left).toBeGreaterThanOrEqual(-HALF_PIXEL);
      expect(gaps!.left).toBeLessThanOrEqual(2 * scale);
      expect(gaps!.right).toBeGreaterThanOrEqual(-HALF_PIXEL);
      expect(gaps!.right).toBeLessThanOrEqual(2 * scale);
      expect(gaps!.top).toBeGreaterThanOrEqual(-HALF_PIXEL);
      expect(gaps!.top).toBeLessThanOrEqual(4 * scale);
      expect(gaps!.bottom).toBeGreaterThanOrEqual(-HALF_PIXEL);
      expect(gaps!.bottom).toBeLessThanOrEqual(3 * scale);
      // (다) 상자 바로 바깥 2px 띠에는 잉크가 없다(앞뒤 문장의 글자를 물지 않고, 글자가 위아래로 삐져나오지 않는다).
      expect(outside, `조각 ${index} 바깥`).toEqual({
        left: 0,
        right: 0,
        top: 0,
        bottom: 0,
      });
    });
    // 두 조각은 서로 다른 줄이다(위아래로 겹치지 않는다).
    expect(pieces[1]!.rect.top).toBeGreaterThanOrEqual(
      pieces[0]!.rect.top + pieces[0]!.rect.height,
    );
    // 문단 전체(box)는 점선 하나로.
    await expect(pageBox(a, 2).locator('.dv-context')).toHaveCount(1);
  });
}

test('상자가 여럿인 강조: 한 조각에 마우스를 올리면 다른 줄의 조각도 같이 채워지고, 어느 조각을 눌러도 그 항목이 골라진다', async ({
  page,
}) => {
  await page.goto('/dev/viewer?data=sample/sentences.json');
  const a = pane(page, 'a');
  // s3 을 골라 2쪽으로 간다. s4 는 고르지 않은 채다(옅게: 채움 없음).
  await item(page, 's3').getByRole('button').first().click();
  await expect(a).toHaveAttribute('data-current-page', '2');
  const pieces = pageBox(a, 2).locator(
    '.dv-highlight[data-highlight-ids="s4"]',
  );
  await expect(pieces).toHaveCount(2);
  const fills = () =>
    pieces.evaluateAll((elements) =>
      elements.map(
        (element) =>
          getComputedStyle(element).backgroundColor !== 'rgba(0, 0, 0, 0)',
      ),
    );
  expect(await fills()).toEqual([false, false]);

  await pieces.nth(0).hover();
  await expect.poll(fills).toEqual([true, true]);
  await a.locator('.dv-toolbar').hover();
  await expect.poll(fills).toEqual([false, false]);

  // 둘째 줄의 조각을 누른다.
  await pieces.nth(1).click();
  await expect(item(page, 's4')).toHaveAttribute('data-selected', 'true');
  await expect(pieces.nth(0)).toHaveAttribute('data-selected', 'true');
  await expect(pieces.nth(1)).toHaveAttribute('data-selected', 'true');
});

// ── CSS 가 내는 모양과 브라우저만 아는 것들. jsdom 테스트로는 볼 수 없어 여기서 본다(모양은 계산된 스타일로, 값을 베껴 적지 않고 견주어서) ──

test('겹친 개수 딱지는 보통 숨어 있다가, 그 상자에 마우스를 올리면 보이고 떼면 다시 숨는다', async ({
  page,
}) => {
  await openSample(page);
  const b = pane(page, 'b');
  // B 의 한 칸을 항목 1 과 4 가 같이 가리킨다.
  const shared = b.locator('.dv-highlight[data-highlight-ids="1-b 4-b"]');
  const count = shared.locator('.dv-count');
  await expect(count).toHaveText('2');
  await expect(count).toBeHidden();

  await shared.hover();
  await expect(count).toBeVisible();
  await b.locator('.dv-toolbar').hover();
  await expect(count).toBeHidden();
});

test('키보드 초점이 간 강조는 다른 상자보다 선이 굵어지고 채워진다. 여러 줄 강조면 줄 조각이 전부 그렇다', async ({
  page,
}) => {
  await page.goto('/dev/viewer?data=sample/sentences.json');
  const a = pane(page, 'a');
  // s3 을 골라 2쪽으로 간다. 2쪽에는 한 줄짜리 s2·s3 과 두 줄짜리 s4 가 있다.
  await item(page, 's3').getByRole('button').first().click();
  await expect(a).toHaveAttribute('data-current-page', '2');
  await expect(
    pageBox(a, 2).locator('.dv-highlight[data-highlight-ids="s4"]'),
  ).toHaveCount(2);

  // Tab 으로 s4 까지 간다(조각이 둘이어도 Tab 은 첫 조각에만 선다).
  const focusedIds = () =>
    page.evaluate(
      () =>
        (document.activeElement as HTMLElement | null)?.dataset.highlightIds ??
        null,
    );
  for (let guard = 0; guard < 40 && (await focusedIds()) !== 's4'; guard++)
    await page.keyboard.press('Tab');
  expect(await focusedIds()).toBe('s4');

  const look = (ids: string) =>
    pageBox(a, 2)
      .locator(`.dv-highlight[data-highlight-ids="${ids}"]`)
      .evaluateAll((elements) =>
        elements.map((element) => ({
          line: Number.parseFloat(getComputedStyle(element).outlineWidth),
          filled:
            getComputedStyle(element).backgroundColor !== 'rgba(0, 0, 0, 0)',
        })),
      );
  // s2: 고르지도 가리키지도 않았고 초점도 없는 상자. 옅게(기본 방식)에서는 채움이 없다.
  const plain = await look('s2');
  expect(plain.map((piece) => piece.filled)).toEqual([false]);
  const focused = await look('s4');
  expect(focused).toHaveLength(2);
  for (const piece of focused) {
    expect(piece.filled).toBe(true);
    expect(piece.line).toBeGreaterThan(plain[0]!.line);
  }

  // 초점이 떠나면 돌아온다.
  await page.keyboard.press('Tab');
  expect(await focusedIds()).not.toBe('s4');
  await expect.poll(() => look('s4')).toEqual([plain[0], plain[0]]);
});

test('창이 커져 더 많은 쪽이 보이게 되면, 스크롤하지 않아도 그 쪽을 그린다. 다시 줄이면 걷어 낸다', async ({
  page,
}) => {
  await openSample(page);
  const a = pane(page, 'a');
  const drawn = () =>
    a
      .locator('.dv-page')
      .evaluateAll((elements) =>
        elements.map((element) =>
          Number((element as HTMLElement).dataset.page),
        ),
      );
  // 세 쪽짜리 문서. 처음 창(높이 900)에는 1쪽만 보여, 1쪽과 그 다음 쪽만 그려져 있다.
  expect(await drawn()).toEqual([1, 2]);

  await page.setViewportSize({ width: 1400, height: 2000 });
  await expect.poll(drawn).toEqual([1, 2, 3]);
  await expect(pageBox(a, 3).locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
  );
  expect(
    await a.locator('.dv-scroller').evaluate((element) => element.scrollTop),
  ).toBe(0);

  await page.setViewportSize({ width: 1400, height: 900 });
  await expect.poll(drawn).toEqual([1, 2]);
});

test('목록이 길어 고른 항목이 목록의 보이는 범위 밖에 있으면, 목록이 그 항목이 보이는 데로 따라간다', async ({
  page,
}) => {
  // 창을 낮춰 항목 여섯이 목록에 다 들어오지 않게 한다.
  await page.setViewportSize({ width: 1400, height: 360 });
  await openSample(page);
  const head = (itemId: string) => item(page, itemId).locator('.dv-item-head');
  await expect(head('1')).toBeInViewport();
  await expect(head('6')).not.toBeInViewport();

  // 키보드로 마지막 항목까지 간다. 목록을 손으로 굴리지 않는다.
  await head('1').click();
  for (let i = 0; i < 5; i++) await page.keyboard.press('j');
  await expect(item(page, '6')).toHaveAttribute('data-selected', 'true');
  await expect(head('6')).toBeInViewport({ ratio: 1 });
  await expect(head('1')).not.toBeInViewport();

  // 거꾸로 올라와도 따라온다.
  for (let i = 0; i < 5; i++) await page.keyboard.press('k');
  await expect(item(page, '1')).toHaveAttribute('data-selected', 'true');
  await expect(head('1')).toBeInViewport({ ratio: 1 });
});
