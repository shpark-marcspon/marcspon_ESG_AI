// RP-03 끌어 옮기기·긴 목차·요구 칸을 빌드 결과에서(밴드 RPW7 §2 S8). 서버는 e2e/drafting-server.ts 의 흉내, 지어낸 값만.
// 흉내 밖 /api/ 요청은 덫(503)으로 적고 시험마다 끝에 0 인지 본다(drafting.spec.ts 꼴).
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DR_TEXT } from '../src/entities/drafting/config/text.ts';
import { writePdf } from '../tools/pdf-writer.ts';
import { fakeDraftingApi } from './drafting-server.ts';
import { signIn } from './session.ts';

const PDF = Buffer.from(
  writePdf([
    {
      width: 595,
      height: 842,
      rotate: 0 as const,
      marks: [],
      texts: [{ x: 72, top: 72, size: 18, str: 'Made-up page' }],
      tables: [],
    },
  ]),
);
const outline = DR_TEXT.outline;

interface Node {
  key: string;
  parentKey: string | null;
  depth: number;
  title: string;
  requirement: string;
}
const node = (
  key: string,
  parentKey: string | null,
  depth: number,
  requirement = '',
): Node => ({ key, parentKey, depth, title: `가상 ${key}`, requirement });

/** 1 a · 1.1 b · 1.1.1 c · 1.1.2 d · 1.1.2.1 e · 1.2 f · 2 g · 2.1 h · 2.2 i. */
const BASIC = () => [
  node('a', null, 1),
  node('b', 'a', 2),
  node('c', 'b', 3, '가상 요구 c'),
  node('d', 'b', 3),
  node('e', 'd', 4, '가상 요구 e'),
  node('f', 'a', 2, '가상 요구 f'),
  node('g', null, 1),
  node('h', 'g', 2, '가상 요구 h'),
  node('i', 'g', 2, '가상 요구 i'),
];

/** 대제목 여섯 · 그 아래 넷 — 30줄. */
const LONG = () =>
  Array.from({ length: 6 }, (_, top) => [
    node(`t${top}`, null, 1),
    ...Array.from({ length: 4 }, (_, sub) =>
      node(`t${top}-${sub}`, `t${top}`, 2, `가상 요구 ${top}-${sub}`),
    ),
  ]).flat();

/** 흉내 밖 /api/ 요청을 적고 503 으로 끊는다(흉내보다 먼저 건다 — drafting.spec.ts 에서 옮겨 적음). */
async function trapUnrouted(page: Page) {
  const unrouted: string[] = [];
  await page.route(/\/api\//, (route) => {
    const url = new URL(route.request().url());
    unrouted.push(`${route.request().method()} ${url.pathname}`);
    return route.fulfill({ status: 503, body: '' });
  });
  return unrouted;
}

async function open(page: Page, nodes: Node[]) {
  const unrouted = await trapUnrouted(page);
  const api = await fakeDraftingApi(page);
  await signIn(page);
  const [projectId] = api.seed(PDF, nodes);
  await page.goto(`/drafting/projects/${projectId}/outline`);
  await expect(page.getByTestId('outline-tree')).toBeVisible();
  return { api, projectId, unrouted };
}

const row = (page: Page, key: string) => page.locator(`[data-key="${key}"]`);
const order = async (page: Page) =>
  page
    .locator('[data-testid="outline-tree"] [data-key]')
    .evaluateAll((rows) =>
      rows.map(
        (one) =>
          `${one.getAttribute('data-key')}:${one.getAttribute('data-depth')}:${one.querySelector('[data-testid="tree-number"]')!.textContent}`,
      ),
    );
const line = (page: Page) => page.getByTestId('drop-line');

/** 그 줄 손잡이를 잡는다. [잡은 x, 잡은 y]. */
async function grab(page: Page, target: Locator): Promise<[number, number]> {
  await target.hover();
  const box = (await target.getByTestId('tree-grip').boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  return [x, y];
}

/** y 가 그 줄과 다음 줄의 경계가 되게 — 그 줄 아래쪽. */
const below = async (target: Locator) => {
  const box = (await target.boundingBox())!;
  return box.y + box.height - 1;
};

test('S8a: 같은 단계 끌기 — 선 → 놓음 → 차례·번호 → 저장 본문 → 새로고침 왕복', async ({
  page,
}) => {
  const { api, unrouted } = await open(page, BASIC());
  const [x] = await grab(page, row(page, 'i'));
  // 2.1 h 앞으로 — g 와 h 사이.
  await page.mouse.move(x, await below(row(page, 'g')), { steps: 8 });
  await expect(line(page)).toHaveAttribute('data-depth', '2');
  await expect(row(page, 'i')).toHaveAttribute('data-ghost', 'true');
  await expect(page.getByTestId('drag-chip')).toHaveText('가상 i');
  await expect(row(page, 'i')).toHaveAttribute('aria-selected', 'true');
  await page.mouse.up();
  await expect(line(page)).toHaveCount(0);
  await expect(page.getByTestId('drag-chip')).toHaveCount(0);
  const expected = [
    'a:1:1',
    'b:2:1.1',
    'c:3:1.1.1',
    'd:3:1.1.2',
    'e:4:1.1.2.1',
    'f:2:1.2',
    'g:1:2',
    'i:2:2.1',
    'h:2:2.2',
  ];
  expect(await order(page)).toEqual(expected);
  await expect(page.getByTestId('outline-dirty')).toBeVisible();
  await expect(row(page, 'i')).toBeFocused();
  await page.getByRole('button', { name: outline.save }).click();
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  const puts = api.of('PUT /drafting/projects/1/outline');
  expect(puts).toHaveLength(1);
  const body = puts[0]!.body as { nodes: Node[] };
  expect(body.nodes.map((one) => [one.key, one.parentKey, one.depth])).toEqual([
    ['a', null, 1],
    ['b', 'a', 2],
    ['c', 'b', 3],
    ['d', 'b', 3],
    ['e', 'd', 4],
    ['f', 'a', 2],
    ['g', null, 1],
    ['i', 'g', 2],
    ['h', 'g', 2],
  ]);
  await page.reload();
  await expect(page.getByTestId('outline-tree')).toBeVisible();
  expect(await order(page)).toEqual(expected);
  expect(unrouted).toEqual([]);
});

test('S8b: 오른쪽 16px — 선 단계 +1 · 저장 본문 parentKey · 아래 단계 같이', async ({
  page,
}) => {
  const { api, unrouted } = await open(page, BASIC());
  // d(1.1.2, 아래 e)를 f 뒤(g 앞) 틈으로. 왼쪽 16px = 단계 2, 거기서 오른쪽 16px = 단계 3, 더 오른쪽은 틈 범위(앞 줄 f + 1)에 묶인다.
  const [x] = await grab(page, row(page, 'd'));
  const y = await below(row(page, 'f'));
  await page.mouse.move(x - 16, y, { steps: 8 });
  await expect(line(page)).toHaveAttribute('data-depth', '2');
  await page.mouse.move(x, y, { steps: 4 });
  await expect(line(page)).toHaveAttribute('data-depth', '3');
  await page.mouse.move(x + 32, y, { steps: 4 });
  await expect(line(page)).toHaveAttribute('data-depth', '3');
  await expect(line(page)).not.toHaveAttribute('data-bad', 'true');
  await page.mouse.up();
  expect(await order(page)).toEqual([
    'a:1:1',
    'b:2:1.1',
    'c:3:1.1.1',
    'f:2:1.2',
    'd:3:1.2.1',
    'e:4:1.2.1.1',
    'g:1:2',
    'h:2:2.1',
    'i:2:2.2',
  ]);
  await page.getByRole('button', { name: outline.save }).click();
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  const body = api.of('PUT /drafting/projects/1/outline')[0]!.body as {
    nodes: Node[];
  };
  const of = (key: string) => body.nodes.find((one) => one.key === key)!;
  expect(of('d')).toMatchObject({ parentKey: 'f', depth: 3 });
  expect(of('e')).toMatchObject({ parentKey: 'd', depth: 4 });
  expect(unrouted).toEqual([]);
});

test('S8c: 네 단계 넘는 자리 — 빨간 선·툴팁 → 놓아도 그대로·dirty 없음', async ({
  page,
}) => {
  const { unrouted } = await open(page, BASIC());
  const before = await order(page);
  const [x, y] = await grab(page, row(page, 'd'));
  await page.mouse.move(x + 16, y, { steps: 6 });
  await expect(line(page)).toHaveAttribute('data-bad', 'true');
  await expect(line(page)).toHaveAttribute('data-depth', '4');
  await expect(page.getByTestId('drop-tip')).toHaveText(outline.tooDeep);
  await expect(page.getByTestId('drag-chip')).toHaveText(
    `가상 d · ${outline.dragChildren(1)}`,
  );
  await page.mouse.up();
  expect(await order(page)).toEqual(before);
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  await expect(page.getByTestId('drop-tip')).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('S8c2: 4px 안에 놓으면 클릭 = 고르기 · 목록 그대로', async ({ page }) => {
  const { unrouted } = await open(page, BASIC());
  const before = await order(page);
  const [x, y] = await grab(page, row(page, 'h'));
  await page.mouse.move(x + 2, y);
  await expect(line(page)).toHaveCount(0);
  await page.mouse.up();
  await expect(row(page, 'h')).toHaveAttribute('aria-selected', 'true');
  await expect(row(page, 'h')).toBeFocused();
  expect(await order(page)).toEqual(before);
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  // 앞 줄에 초점을 둔 뒤 손잡이 클릭 → 키는 새로 고른 줄에 먹는다.
  await row(page, 'a').click();
  await grab(page, row(page, 'i'));
  await page.mouse.up();
  await page.keyboard.press('Delete');
  await expect(page.getByTestId('remove-dialog')).toContainText(
    outline.removeConfirm('가상 i'),
  );
  await page.getByRole('button', { name: outline.cancel }).click();
  await grab(page, row(page, 'c'));
  await page.mouse.up();
  await page.keyboard.press('ArrowDown');
  await expect(row(page, 'd')).toHaveAttribute('aria-selected', 'true');
  expect(unrouted).toEqual([]);
});

test('S8c6: [삭제] 초점 + 끌며 Enter — 창이 뜨면 끌기 취소 · 놓아도 창 이름·차례 그대로 · 초점은 창', async ({
  page,
}) => {
  const { unrouted } = await open(page, BASIC());
  await row(page, 'c').click();
  await page.getByRole('button', { name: outline.removeShort }).focus();
  const before = await order(page);
  const [x] = await grab(page, row(page, 'c'));
  await page.mouse.move(x, await below(row(page, 'e')), { steps: 6 });
  await expect(line(page)).toHaveCount(1);
  await page.keyboard.press('Enter');
  const dialog = page.getByTestId('remove-dialog');
  await expect(dialog).toContainText(outline.removeConfirm('가상 c'));
  await expect(line(page)).toHaveCount(0);
  await page.mouse.up();
  await expect(dialog).toContainText(outline.removeConfirm('가상 c'));
  expect(await order(page)).toEqual(before);
  expect(
    await dialog.evaluate((box) => box.contains(document.activeElement)),
  ).toBe(true);
  expect(unrouted).toEqual([]);
});

test('S8c7: 끊김 없는 긴 이름 — 경로·이름이 칸 안에서 꺾여 쪽이 옆으로 넘치지 않는다', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { unrouted } = await open(page, [
    node('p', null, 1),
    node('q', 'p', 2, '가상 요구'),
    node('r', 'q', 3, '가상 요구'),
  ]);
  const long = 'x'.repeat(190);
  // 조상 긴 이름 + 자기 긴 이름 둘 다.
  await row(page, 'q').click();
  await page.getByLabel(outline.nameLabel).fill(long);
  await row(page, 'r').click();
  await page.getByLabel(outline.nameLabel).fill(long);
  const wide = await page.evaluate(() => ({
    doc: document.documentElement.scrollWidth,
    win: window.innerWidth,
  }));
  expect(wide.doc).toBeLessThanOrEqual(wide.win);
  const path = (await page.getByTestId('node-path').boundingBox())!;
  const name = (await page
    .getByTestId('node-path')
    .locator('b')
    .boundingBox())!;
  expect(name.x + name.width).toBeLessThanOrEqual(path.x + path.width + 1);
  expect(unrouted).toEqual([]);
});

test('S8c3: 끄는 중 줄 키 막힘 — Tab·Shift+Tab 은 그대로·초점 안 튐, Delete 는 창 없음, 놓으면 끌던 줄이 옮겨짐', async ({
  page,
}) => {
  const { unrouted } = await open(page, BASIC());
  await row(page, 'h').click();
  const [x] = await grab(page, row(page, 'h'));
  await page.mouse.move(x, await below(row(page, 'f')), { steps: 6 });
  await expect(line(page)).toHaveCount(1);
  await expect(row(page, 'h')).toBeFocused();
  const before = await order(page);
  await page.keyboard.press('Shift+Tab');
  expect(await order(page)).toEqual(before);
  await expect(row(page, 'h')).toBeFocused();
  await page.keyboard.press('Tab');
  expect(await order(page)).toEqual(before);
  await expect(row(page, 'h')).toBeFocused();
  await page.keyboard.press('Delete');
  await expect(page.getByTestId('remove-dialog')).toHaveCount(0);
  await page.mouse.up();
  expect((await order(page)).map((one) => one.split(':')[0])).toEqual([
    'a',
    'b',
    'c',
    'd',
    'e',
    'f',
    'h',
    'g',
    'i',
  ]);
  expect(unrouted).toEqual([]);
});

test('S8c4: 4px 안에서 잡은 채로도 줄 키 막힘 · 잡은 동안 목록이 바뀌면 끌기 취소', async ({
  page,
}) => {
  const { unrouted } = await open(page, BASIC());
  await row(page, 'h').click();
  const before = await order(page);
  await grab(page, row(page, 'h'));
  await page.keyboard.press('Shift+Tab');
  expect(await order(page)).toEqual(before);
  // Alt+↑↓ 옮기기(RPW12)도 잡은 동안 막힌다.
  await page.keyboard.press('Alt+ArrowUp');
  expect(await order(page)).toEqual(before);
  await page.mouse.up();
  // 편집 칸 이름 칸에 초점을 두고 끄는 중 Enter(같은 단계 새 줄) — 목록이 바뀌어 끌기 취소.
  // (RPW12: 편집 칸 「순서 · 단계」 단추 넷을 걷어 [아래로] 대신 이름 칸 Enter 로 같은 막힘을 잰다.)
  await row(page, 'h').click();
  await page.getByLabel(outline.nameLabel).focus();
  const [x, y] = await grab(page, row(page, 'h'));
  await page.mouse.move(x, y + 60, { steps: 4 });
  await expect(line(page)).toHaveCount(1);
  await page.keyboard.press('Enter');
  await expect(line(page)).toHaveCount(0);
  await page.mouse.up();
  const after = (await order(page)).map((one) => one.split(':')[0]);
  expect(after).toHaveLength(before.length + 1);
  expect(after.slice(0, 8)).toEqual(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']);
  expect(after.at(-1)).toBe('i');
  expect(['h', 'i']).not.toContain(after.at(-2));
  expect(unrouted).toEqual([]);
});

test('S8c5: 끄는 중 pointercancel = 취소 · 단추 없는 pointermove(창 밖에서 놓음) = 취소', async ({
  page,
}) => {
  const { unrouted } = await open(page, BASIC());
  const before = await order(page);
  for (const send of [
    () => window.dispatchEvent(new PointerEvent('pointercancel')),
    () => window.dispatchEvent(new PointerEvent('pointermove', { buttons: 0 })),
  ]) {
    const [x] = await grab(page, row(page, 'i'));
    await page.mouse.move(x, await below(row(page, 'a')), { steps: 6 });
    await expect(line(page)).toHaveCount(1);
    await page.evaluate(send);
    await expect(line(page)).toHaveCount(0);
    await expect(page.getByTestId('drag-chip')).toHaveCount(0);
    expect(await page.evaluate(() => document.body.style.cursor)).toBe('');
    await page.mouse.up();
    expect(await order(page)).toEqual(before);
    await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  }
  expect(unrouted).toEqual([]);
});

test('S8d: 긴 목차 — 목록 504 · 안쪽 스크롤 · 창 그대로 · 자동 스크롤', async ({
  page,
}) => {
  // 창 1000: 목록 전체가 창 안이고 쪽은 조금 구를 수 있다 — 고른 줄 보이기가 창을 건드리면 scrollY 로 잡힌다.
  await page.setViewportSize({ width: 1280, height: 1000 });
  const { unrouted } = await open(page, LONG());
  const list = page.getByTestId('outline-tree');
  const box = (await list.boundingBox())!;
  expect(box.height).toBe(504);
  expect(box.y + box.height).toBeLessThan(1000);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollHeight > window.innerHeight,
    ),
  ).toBe(true);
  await expect(page.getByTestId('tree-total')).toHaveText(
    outline.treeTotal(30),
  );

  await row(page, 't0').click();
  // 넘친 만큼만: 14줄째까지 ↓ 면 목록은 한 줄 안쪽만 구른다(맨 위로 맞추는 스크롤이 아니다).
  for (let at = 0; at < 14; at += 1) await page.keyboard.press('ArrowDown');
  expect(await list.evaluate((one) => one.scrollTop)).toBeLessThanOrEqual(40);
  for (let at = 14; at < 29; at += 1) await page.keyboard.press('ArrowDown');
  const last = row(page, 't5-3');
  await expect(last).toHaveAttribute('aria-selected', 'true');
  await expect(last).toBeFocused();
  await expect(last).toBeInViewport({ ratio: 1 });
  const fitted = (await last.boundingBox())!;
  expect(fitted.y + fitted.height).toBeLessThanOrEqual(box.y + box.height + 1);
  expect(await list.evaluate((one) => one.scrollTop)).toBeGreaterThan(0);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);

  // 끌기로 목록 가장자리 자동 스크롤 → 먼 자리에 놓임: 맨 아래 t5-3 을 잡고 위 가장자리에 머무르면 맨 위 근처까지 구른다.
  const [x] = await grab(page, last);
  const top = (await list.boundingBox())!;
  await page.mouse.move(x, top.y + 6, { steps: 6 });
  await expect
    .poll(() => list.evaluate((one) => one.scrollTop), { timeout: 15_000 })
    .toBe(0);
  // 맨 위 줄(t0) 아래 틈으로 — 자식 t0-0 이 뒤따르는 틈이라 단계 2 고정.
  const first = (await row(page, 't0').boundingBox())!;
  await page.mouse.move(x, first.y + first.height - 1, { steps: 4 });
  await expect(line(page)).toHaveAttribute('data-depth', '2');
  await page.mouse.up();
  const after = await order(page);
  expect(after[1]).toBe('t5-3:2:1.1');
  expect(after).toHaveLength(30);
  expect(unrouted).toEqual([]);
});

test('S8d2: 창 600 — 줄이 창 밖이면 넘친 만큼만 굴러 다 보임 · 굴린 뒤 편집 칸 top 24', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1400, height: 600 });
  const { unrouted } = await open(page, LONG());
  const list = page.getByTestId('outline-tree');
  await row(page, 't0').click();
  // 맨 아래 줄까지 ↓ — 목록 아래 끝이 창 밖이면 창도 그만큼만 구른다.
  for (let at = 0; at < 29; at += 1) await page.keyboard.press('ArrowDown');
  const last = row(page, 't5-3');
  await expect(last).toBeFocused();
  await expect(last).toBeInViewport({ ratio: 1 });
  const lastBox = (await last.boundingBox())!;
  expect(lastBox.y + lastBox.height).toBeLessThanOrEqual(601);
  expect(lastBox.y + lastBox.height).toBeGreaterThan(560);
  expect(await list.evaluate((one) => one.scrollTop)).toBeGreaterThan(0);

  // 창을 더 굴려 sticky 를 잰다 — 쪽이 안 구르면 재지 못하니 먼저 굴렸는지 본다.
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const scrolled = await page.evaluate(() => window.scrollY);
  expect(scrolled).toBeGreaterThan(0);
  const editor = page.getByTestId('outline-editor');
  const tree = page.getByTestId('outline-tree-box');
  expect((await tree.boundingBox())!.y).toBeLessThan(24);
  expect((await editor.boundingBox())!.y).toBe(24);
  expect(unrouted).toEqual([]);
});

test('S8f: 초점 복구 — 뒤 형제가 있는 줄을 Shift+Tab(DOM 이 옮겨짐) → 그 줄에 초점 → 이어 Tab 은 단계 내림', async ({
  page,
}) => {
  const { unrouted } = await open(page, BASIC());
  await row(page, 'c').click();
  await page.keyboard.press('Shift+Tab');
  expect(await order(page)).toEqual([
    'a:1:1',
    'b:2:1.1',
    'd:3:1.1.1',
    'e:4:1.1.1.1',
    'c:2:1.2',
    'f:2:1.3',
    'g:1:2',
    'h:2:2.1',
    'i:2:2.2',
  ]);
  await expect(row(page, 'c')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(row(page, 'c')).toHaveAttribute('data-depth', '3');
  await expect(row(page, 'c')).toBeFocused();
  // 줄 아이콘을 눌러도 초점은 줄로.
  await row(page, 'c').getByRole('button', { name: outline.up }).click();
  await expect(row(page, 'c')).toBeFocused();
  expect(unrouted).toEqual([]);
});

test('S8e: 요구 칸 — 빈 칸 108 · 30줄이면 높이 상한 + 칸 안 스크롤', async ({
  page,
}) => {
  const { unrouted } = await open(page, BASIC());
  await row(page, 'c').click();
  const area = page.getByLabel(outline.requirementLabel);
  await area.fill('');
  expect((await area.boundingBox())!.height).toBe(108);
  await area.fill(
    Array.from({ length: 30 }, (_, at) => `가상 줄 ${at}`).join('\n'),
  );
  const limit = await area.evaluate((one) => {
    const style = getComputedStyle(one);
    return {
      max: parseFloat(style.maxHeight),
      height: one.getBoundingClientRect().height,
      scroll: one.scrollHeight > one.clientHeight,
      font: parseFloat(style.fontSize),
    };
  });
  expect(limit.max).toBeCloseTo(1.6 * limit.font * 12 + 24, 0);
  expect(limit.height).toBeCloseTo(limit.max, 0);
  expect(limit.scroll).toBe(true);
  expect(unrouted).toEqual([]);
});

/** 사진(밴드 RPW8 §2) — RPW8_SHOTS 가 있을 때만, 그 폴더에. */
const shot = async (page: Page, name: string) => {
  const dir = process.env.RPW8_SHOTS;
  if (dir) await page.screenshot({ path: `${dir}/${name}.png` });
};

/** 낱말마다 줄 상자가 하나의 줄에만 있는가(낱말 중간에서 안 꺾임). 꺾인 낱말 목록. */
const brokenWords = (target: Locator) =>
  target.evaluate((b) => {
    const text = b.firstChild as Text;
    const broken: string[] = [];
    const re = /\S+/g;
    let hit: RegExpExecArray | null;
    while ((hit = re.exec(text.data))) {
      const range = document.createRange();
      range.setStart(text, hit.index);
      range.setEnd(text, hit.index + hit[0].length);
      const tops = new Set(
        [...range.getClientRects()].map((rect) => Math.round(rect.top)),
      );
      if (tops.size > 1) broken.push(hit[0]);
    }
    return broken;
  });

test('S9a(RPW8 ③): 띄어쓴 긴 영문 이름 — 낱말 경계에서만 꺾임 · 쪽 폭 = 창', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { unrouted } = await open(page, BASIC());
  await row(page, 'e').click();
  const long = Array.from(
    { length: 4 },
    () => 'Imaginary Climate Targets Disclosure Overview',
  ).join(' ');
  await page.getByLabel(outline.nameLabel).fill(long);
  const name = page.getByTestId('node-path').locator('b');
  await expect(name).toHaveText(long);
  const box = (await name.boundingBox())!;
  expect(box.height).toBeGreaterThan(30); // 두 줄 넘게 감김 — 시험이 뜻이 있게
  expect(await brokenWords(name)).toEqual([]);
  const wide = await page.evaluate(() => ({
    doc: document.documentElement.scrollWidth,
    win: window.innerWidth,
  }));
  expect(wide.doc).toBe(wide.win);
  expect(unrouted).toEqual([]);
});

test('S9b(RPW8 N1): 쪽 연 뒤 첫 조작이 끌기 — 놓은 줄에 초점 테두리 없음 · 이어 ↓ 는 새 줄에 테두리', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { unrouted } = await open(page, BASIC());
  const visible = (key: string) =>
    row(page, key).evaluate((one) => one.matches(':focus-visible'));
  const [x] = await grab(page, row(page, 'i'));
  await page.mouse.move(x, await below(row(page, 'g')), { steps: 8 });
  await expect(line(page)).toHaveCount(1);
  await page.mouse.up();
  await expect(row(page, 'i')).toBeFocused();
  expect(await visible('i')).toBe(false);
  await page.mouse.move(900, 860);
  await shot(page, 'N1-after-drag');
  await page.keyboard.press('ArrowDown');
  await expect(row(page, 'h')).toBeFocused();
  expect(await visible('h')).toBe(true);
  expect(unrouted).toEqual([]);
});

test('S9b3(RPW8 N1·검증 B1): 끌어 놓은 줄에서 Tab(줄 그대로 단계 내림) — 같은 줄에 테두리가 돌아옴', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { unrouted } = await open(page, BASIC());
  const visible = (key: string) =>
    row(page, key).evaluate((one) => one.matches(':focus-visible'));
  const [x] = await grab(page, row(page, 'c'));
  await page.mouse.move(x, await below(row(page, 'e')), { steps: 8 });
  await expect(line(page)).toHaveCount(1);
  await page.mouse.up();
  await expect(row(page, 'c')).toBeFocused();
  expect(await visible('c')).toBe(false);
  const depth = await row(page, 'c').getAttribute('data-depth');
  await page.keyboard.press('Tab');
  await expect(row(page, 'c')).not.toHaveAttribute('data-depth', depth!);
  await expect(row(page, 'c')).toBeFocused();
  expect(await visible('c')).toBe(true);
  // 손잡이 클릭 뒤 Tab(못 옮겨도) — 같은 줄 테두리.
  await row(page, 'a').hover();
  await row(page, 'a').getByTestId('tree-grip').click();
  expect(await visible('a')).toBe(false);
  await page.keyboard.press('Tab');
  await expect(row(page, 'a')).toBeFocused();
  expect(await visible('a')).toBe(true);
  expect(unrouted).toEqual([]);
});

test('S9b2(RPW8 N1): 쪽 연 뒤 첫 조작이 손잡이 클릭 — 테두리 없음 · 이어 ↑ 는 테두리', async ({
  page,
}) => {
  const { unrouted } = await open(page, BASIC());
  await row(page, 'c').hover();
  await row(page, 'c').getByTestId('tree-grip').click();
  await expect(row(page, 'c')).toBeFocused();
  expect(
    await row(page, 'c').evaluate((one) => one.matches(':focus-visible')),
  ).toBe(false);
  await page.keyboard.press('ArrowUp');
  await expect(row(page, 'b')).toBeFocused();
  expect(
    await row(page, 'b').evaluate((one) => one.matches(':focus-visible')),
  ).toBe(true);
  expect(unrouted).toEqual([]);
});

test('S9c(RPW8 N2): 긴 이름 — [삭제] 는 머리 첫 줄 높이에서 오른쪽 끝', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { unrouted } = await open(page, BASIC());
  await row(page, 'e').click();
  await page
    .getByLabel(outline.nameLabel)
    .fill(
      Array.from({ length: 5 }, () => '가상 아주 긴 목차 이름 조각').join(' '),
    );
  const head = page.getByTestId('node-path');
  const remove = page
    .getByTestId('outline-editor')
    .getByRole('button', { name: outline.removeShort });
  const headBox = (await head.boundingBox())!;
  const removeBox = (await remove.boundingBox())!;
  const outer = (await head.locator('..').boundingBox())!;
  expect(headBox.height).toBeGreaterThan(removeBox.height); // 머리가 감겼다
  expect(Math.abs(removeBox.y - headBox.y)).toBeLessThanOrEqual(1);
  expect(
    Math.abs(removeBox.x + removeBox.width - (outer.x + outer.width)),
  ).toBeLessThanOrEqual(1);
  expect(removeBox.x).toBeGreaterThanOrEqual(headBox.x + headBox.width);
  await shot(page, 'N2-long-head');
  expect(unrouted).toEqual([]);
});

test('S8g(RPW12): 편집 칸에 「순서 · 단계」 줄 0 · 줄 아이콘 [아래로] 로 옮김 그대로 · Alt+↑↓ 옮김 · 끝에서 0 · 초점은 옮긴 줄', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { unrouted } = await open(page, BASIC());
  await row(page, 'h').click();
  const editor = page.getByTestId('outline-editor');
  await expect(editor.getByText('순서 · 단계')).toHaveCount(0);
  for (const name of [
    outline.up,
    outline.down,
    outline.outdent,
    outline.indent,
  ])
    await expect(editor.getByRole('button', { name })).toHaveCount(0);
  const keys = async () => (await order(page)).map((one) => one.split(':')[0]);
  // 줄 아이콘(행 hover 다섯)으로 아래로.
  await row(page, 'h').getByRole('button', { name: outline.down }).click();
  expect((await keys()).slice(-3)).toEqual(['g', 'i', 'h']);
  // Alt+↑ — 줄 초점에서 한 칸 위로, 초점은 그 줄.
  await row(page, 'h').focus();
  await page.keyboard.press('Alt+ArrowUp');
  expect((await keys()).slice(-3)).toEqual(['g', 'h', 'i']);
  await expect(row(page, 'h')).toBeFocused();
  // 맨 위 형제에서 Alt+↑ 는 0.
  const top = await order(page);
  await page.keyboard.press('Alt+ArrowUp');
  expect(await order(page)).toEqual(top);
  await expect(row(page, 'h')).toBeFocused();
  // Alt+↓ — 하위(c·d·e)와 함께 b 가 f 아래로.
  await row(page, 'b').click();
  await row(page, 'b').focus();
  await page.keyboard.press('Alt+ArrowDown');
  expect((await keys()).slice(0, 6)).toEqual(['a', 'f', 'b', 'c', 'd', 'e']);
  await expect(row(page, 'b')).toBeFocused();
  await shot(page, 'outline-editor');
  expect(unrouted).toEqual([]);
});
