// RP-03a 목차 붙여넣기를 빌드 결과에서(밴드 RPW9 §2 S10). 서버는 e2e/drafting-server.ts 의 흉내(응답 꼴 바꿈 0), 지어낸 값만.
// 흉내 밖 /api/ 요청은 덫(503)으로 적고 시험마다 끝에 0 인지 본다(drafting-outline.spec.ts 꼴).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

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
const paste = outline.paste;
const PUT = 'PUT /drafting/projects/1/outline';

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

/** 1 a · 1.1 b · 1.1.1 c · 2 d · 2.1 e — 대제목 둘, 잎 둘. */
const BASIC = () => [
  node('a', null, 1),
  node('b', 'a', 2),
  node('c', 'b', 3, '가상 요구 c'),
  node('d', null, 1),
  node('e', 'd', 2),
];

/** 대 하나 + 중 n−1(잎 n−1). */
const MANY = (count: number) =>
  Array.from({ length: count }, (_, at) =>
    node(`m${at}`, at === 0 ? null : 'm0', at === 0 ? 1 : 2),
  );

/** 흉내 밖 /api/ 요청을 적고 503 으로 끊는다(drafting-outline.spec.ts 에서 옮겨 적음). */
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
  return { api, unrouted };
}

const dialog = (page: Page) => page.getByTestId('paste-dialog');
const textBox = (page: Page) => page.getByLabel(paste.inputLabel);
const insert = (page: Page) => page.getByTestId('paste-insert');
const numbers = (page: Page) =>
  page.getByTestId('paste-number').allTextContents();
const order = (page: Page) =>
  page
    .locator('[data-testid="outline-tree"] [data-key]')
    .evaluateAll((rows) =>
      rows.map(
        (one) =>
          `${one.getAttribute('data-depth')}:${one.querySelector('[data-testid="tree-number"]')!.textContent}:${one.querySelector('[data-testid="tree-title-text"]')!.textContent}`,
      ),
    );
const selected = (page: Page) =>
  page.locator('[data-testid="outline-tree"] [aria-selected="true"]');

/** 지어낸 붙여넣기 글 — 들여쓰기 0 번호 · 탭 요구 · 「요구:」 · 다음 줄 요구 · 다섯째 단계 · 201자 이름 · 들여쓰기만 줄. */
const MIXED = [
  '1. 가상 경영',
  '1.1 가상 재무\t지어낸 요구 가',
  '1.1.1 가상 매출 요구: 지어낸 요구 나',
  '1.1.1.1 가상 지역',
  '1.1.1.1.1 가상 너무 깊음',
  '',
  '2. 가상 부록',
  '    요구: 지어낸 요구 다',
  `2.1 ${'가'.repeat(201)}`,
  '가상 색인',
  '    가상 색인 아래',
].join('\n');

test('S10a 붙이기: 미리보기 번호·못 읽은 줄 → 넣기 → 첫 새 줄 고름·초점 → 저장 본문 → 새로고침 왕복', async ({
  page,
}) => {
  const { api, unrouted } = await open(page, BASIC());
  await page.getByRole('button', { name: paste.open }).click();
  await expect(dialog(page)).toBeVisible();
  await expect(textBox(page)).toBeFocused();
  await textBox(page).fill(MIXED);
  // 지금 대제목 둘 → 3 부터. 들여쓰기 0 번호 글이 1/2/3/4 단계로 읽힌다.
  await expect(page.getByTestId('paste-number')).toHaveCount(7);
  expect(await numbers(page)).toEqual([
    '3',
    '3.1',
    '3.1.1',
    '3.1.1.1',
    '4',
    '5',
    '5.1',
  ]);
  await expect(page.getByTestId('paste-counts')).toHaveText(
    paste.previewCounts(7, 3),
  );
  await expect(page.getByTestId('paste-bad')).toContainText(
    paste.badSummary(2),
  );
  const list = page.getByTestId('paste-bad-list');
  await expect(list).toBeHidden();
  await page.getByTestId('paste-bad-toggle').click();
  await expect(list).toBeVisible();
  await expect(list.getByRole('listitem')).toHaveText([
    `${paste.badLine(5)} · ${paste.reasons.tooDeep}`,
    `${paste.badLine(9)} · ${paste.reasons.titleLong(200)}`,
  ]);
  await expect(insert(page)).toHaveText(paste.insert(7));
  await insert(page).click();
  await expect(dialog(page)).toHaveCount(0);
  const expected = [
    '1:1:가상 a',
    '2:1.1:가상 b',
    '3:1.1.1:가상 c',
    '1:2:가상 d',
    '2:2.1:가상 e',
    '1:3:가상 경영',
    '2:3.1:가상 재무',
    '3:3.1.1:가상 매출',
    '4:3.1.1.1:가상 지역',
    '1:4:가상 부록',
    '1:5:가상 색인',
    '2:5.1:가상 색인 아래',
  ];
  expect(await order(page)).toEqual(expected);
  await expect(selected(page)).toHaveCount(1);
  await expect(selected(page)).toContainText('가상 경영');
  await expect(selected(page)).toBeFocused();
  await expect(page.getByTestId('outline-dirty')).toBeVisible();
  await page.getByRole('button', { name: outline.save }).click();
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  const puts = api.of(PUT);
  expect(puts).toHaveLength(1);
  const body = (puts[0]!.body as { nodes: Node[] }).nodes;
  expect(body.slice(0, 5)).toEqual(BASIC());
  const fresh = body.slice(5);
  const keyOf = (title: string) =>
    fresh.find((one) => one.title === title)!.key;
  expect(
    fresh.map((one) => [one.parentKey, one.depth, one.title, one.requirement]),
  ).toEqual([
    [null, 1, '가상 경영', ''],
    [keyOf('가상 경영'), 2, '가상 재무', '지어낸 요구 가'],
    [keyOf('가상 재무'), 3, '가상 매출', '지어낸 요구 나'],
    [keyOf('가상 매출'), 4, '가상 지역', ''],
    [null, 1, '가상 부록', '지어낸 요구 다'],
    [null, 1, '가상 색인', ''],
    [keyOf('가상 색인'), 2, '가상 색인 아래', ''],
  ]);
  await page.reload();
  await expect(page.getByTestId('outline-tree')).toBeVisible();
  expect(await order(page)).toEqual(expected);
  expect(unrouted).toEqual([]);
});

test('S10b 바꾸기: 확인 창 글 → Esc 는 확인 창만 → 다시 → [바꾸기] → 새 줄만 · 첫 새 줄 초점 · 옛 key 0', async ({
  page,
}) => {
  const { api, unrouted } = await open(page, BASIC());
  await page.getByRole('button', { name: paste.open }).click();
  await textBox(page).fill('가상 하나\n  가상 둘\n가상 셋');
  await page.getByRole('radio', { name: paste.replace }).click();
  await expect(page.getByTestId('paste-number')).toHaveText(['1', '1.1', '2']);
  await insert(page).click();
  const confirm = page.getByTestId('paste-confirm');
  await expect(confirm).toBeVisible();
  await expect(confirm).toHaveAttribute('role', 'alertdialog');
  await expect(confirm).toContainText(paste.confirmTitle);
  await expect(confirm).toContainText(paste.confirmBody(5, 3));
  await page.keyboard.press('Escape');
  await expect(confirm).toHaveCount(0);
  await expect(dialog(page)).toBeVisible();
  await expect(textBox(page)).toHaveValue('가상 하나\n  가상 둘\n가상 셋');
  await expect(page.getByRole('radio', { name: paste.replace })).toBeChecked();
  await expect(insert(page)).toBeFocused();
  await insert(page).click();
  await page
    .getByTestId('paste-confirm')
    .getByRole('button', { name: paste.confirmYes })
    .click();
  await expect(dialog(page)).toHaveCount(0);
  expect(await order(page)).toEqual([
    '1:1:가상 하나',
    '2:1.1:가상 둘',
    '1:2:가상 셋',
  ]);
  await expect(selected(page)).toContainText('가상 하나');
  await expect(selected(page)).toBeFocused();
  await page.getByRole('button', { name: outline.save }).click();
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  const body = (api.of(PUT)[0]!.body as { nodes: Node[] }).nodes;
  expect(body.map((one) => one.title)).toEqual([
    '가상 하나',
    '가상 둘',
    '가상 셋',
  ]);
  const old = new Set(BASIC().map((one) => one.key));
  expect(body.filter((one) => old.has(one.key))).toEqual([]);
  expect(unrouted).toEqual([]);
});

test('S10c 한도: 290 + 11 → 빨간 띠(합친 수)·꺼짐 → 바꾸기면 켜짐 · 끝 목차 150 도', async ({
  page,
}) => {
  const { unrouted } = await open(page, MANY(290));
  await page.getByRole('button', { name: paste.open }).click();
  await textBox(page).fill(
    Array.from({ length: 11 }, (_, at) => `가상 대 ${at}`).join('\n'),
  );
  const band = page.getByTestId('paste-over');
  await expect(band).toHaveAttribute('role', 'alert');
  await expect(band).toHaveText(paste.tooManyNodes(300, 301));
  await expect(insert(page)).toBeDisabled();
  await expect(insert(page)).toHaveText(paste.insert(11));
  await page.getByRole('radio', { name: paste.replace }).click();
  await expect(band).toHaveCount(0);
  await expect(insert(page)).toBeEnabled();
  // 끝 목차: 바꾸기 그대로 새 대제목 151 개 — 괄호 없는 끝 목차 띠
  await textBox(page).fill(
    Array.from({ length: 151 }, (_, at) => `가상 대 ${at}`).join('\n'),
  );
  await expect(band).toHaveText(paste.tooManyLeaves(150, null));
  await expect(insert(page)).toBeDisabled();
  expect(unrouted).toEqual([]);
});

test('S10d 키보드: Tab 으로 [붙여넣기] → Enter → 글 칸 → Esc → 초점 [붙여넣기] · insertText 도 같게 읽힘', async ({
  page,
}) => {
  const { unrouted } = await open(page, BASIC());
  await page.getByRole('button', { name: outline.addChild }).focus();
  await page.keyboard.press('Tab');
  const opener = page.getByRole('button', { name: paste.open });
  await expect(opener).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(textBox(page)).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog(page)).toHaveCount(0);
  await expect(opener).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(textBox(page)).toBeFocused();
  await page.keyboard.insertText('1. 가상 가\t지어낸 요구\n1.1 가상 나');
  await expect(page.getByTestId('paste-title')).toHaveText([
    '가상 가',
    '가상 나',
  ]);
  await expect(page.getByTestId('paste-requirement')).toHaveCount(1);
  expect(await numbers(page)).toEqual(['3', '3.1']);
  expect(unrouted).toEqual([]);
});

test('S10e 감독 골자 예(다음 줄 요구) → 저장 본문의 잎 requirement', async ({
  page,
}) => {
  const { api, unrouted } = await open(page, BASIC());
  await page.getByRole('button', { name: paste.open }).click();
  await textBox(page).fill(
    [
      '1. 환경',
      '  1.1 기후변화 대응',
      '    1.1.1 온실가스 배출 현황',
      '        요구: Scope 1·2 배출량을 연도별로',
    ].join('\n'),
  );
  await expect(page.getByTestId('paste-counts')).toHaveText(
    paste.previewCounts(3, 1),
  );
  await expect(page.getByTestId('paste-bad')).toHaveCount(0);
  await insert(page).click();
  await page.getByRole('button', { name: outline.save }).click();
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  const body = (api.of(PUT)[0]!.body as { nodes: Node[] }).nodes;
  expect(
    body.slice(5).map((one) => [one.depth, one.title, one.requirement]),
  ).toEqual([
    [1, '환경', ''],
    [2, '기후변화 대응', ''],
    [3, '온실가스 배출 현황', 'Scope 1·2 배출량을 연도별로'],
  ]);
  expect(unrouted).toEqual([]);
});

// RPW10 — 디자인 재대조(RPW9 디자인 검토 「고칠 것」 #2·#3). 창은 위에서 64 에 서고(시안 `.rp-pover` padding-top 64) 글·띠에 따라 움직이지 않는다.
// [붙여넣기] 단추는 시안 `.c-textbtn` 14px · 높이 36. PASTE_SHOTS=<폴더> 이면 사진을 남긴다(보고용, 단언 아님).
const SHOTS = process.env.PASTE_SHOTS;
const shot = async (page: Page, name: string) => {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png` });
};
const box = async (page: Page) => (await dialog(page).boundingBox())!;
/** 창 자신의 움직임(키트 Dialog 의 여는 zoom-in 200ms)이 끝나기를 기다린다. 도는 중의 위 끝은 64.59·64.25 처럼 소수가 남는다(RPW11 실측). */
const settled = (page: Page) =>
  dialog(page).evaluate(async (element) => {
    await Promise.all(element.getAnimations().map((one) => one.finished));
  });
/** 여는 움직임이 끝난 뒤 창 위 끝이 64±1 인지. 끝난 뒤라 다시 재지 않는다 — 이때 벗어나면 창이 정말 움직인 것이다. */
const expectTop64 = async (page: Page) => {
  await settled(page);
  expect(Math.abs((await box(page)).y - 64)).toBeLessThanOrEqual(1);
};
const OVER = [
  MIXED,
  ...Array.from({ length: 11 }, (_, at) => `가상 넘음 ${at}`),
].join('\n');

test.describe('RPW10 창 자리·단추 크기', () => {
  test.use({ viewport: { width: 1440, height: 1000 } });

  test('S10f 네 상태(빈 → 글 → 못 읽은 줄 펼침 → 한도)에서 창 위 끝 64 그대로', async ({
    page,
  }) => {
    const { unrouted } = await open(page, MANY(290));
    await page.getByRole('button', { name: paste.open }).click();
    await expect(dialog(page)).toBeVisible();
    await expectTop64(page);
    await shot(page, 'w1-empty');
    const tops = [(await box(page)).y];
    await textBox(page).fill('가상 하나\n  가상 둘\n가상 셋');
    await expect(page.getByTestId('paste-number')).toHaveCount(3);
    await expectTop64(page);
    await shot(page, 'w2-read');
    tops.push((await box(page)).y);
    await textBox(page).fill(MIXED);
    await page.getByTestId('paste-bad-toggle').click();
    await expect(page.getByTestId('paste-bad-list')).toBeVisible();
    await expectTop64(page);
    await shot(page, 'w3-bad-open');
    tops.push((await box(page)).y);
    await textBox(page).fill(OVER);
    await expect(page.getByTestId('paste-over')).toBeVisible();
    await expectTop64(page);
    await shot(page, 'w4-over');
    tops.push((await box(page)).y);
    expect(new Set(tops).size).toBe(1);
    expect(unrouted).toEqual([]);
  });

  test('S10j 한도 띠가 새로 나타나도(140 + 11 → 12) 창 위 끝 64 · 앞 상태 y 그대로(RPW12)', async ({
    page,
  }) => {
    // 대 하나 + 중 139(잎 139). 붙인 대제목은 잎 — 11 이면 잎 150(한도 안), 12 면 151(끝 목차 한도 넘음). 목차 수 152 는 300 안.
    const { unrouted } = await open(page, MANY(140));
    const rows = (count: number) =>
      Array.from({ length: count }, (_, at) => `가상 대 ${at}`).join('\n');
    await page.getByRole('button', { name: paste.open }).click();
    await expect(dialog(page)).toBeVisible();
    await expectTop64(page);
    await expect(page.getByTestId('paste-over')).toHaveCount(0);
    const tops = [(await box(page)).y];
    await textBox(page).fill(rows(11));
    await expect(page.getByTestId('paste-number')).toHaveCount(11);
    await expectTop64(page);
    await expect(page.getByTestId('paste-over')).toHaveCount(0);
    await expect(insert(page)).toBeEnabled();
    await shot(page, 'rpw12-paste-under');
    tops.push((await box(page)).y);
    await textBox(page).fill(rows(12));
    const band = page.getByTestId('paste-over');
    await expect(band).toBeVisible();
    await expect(band).toHaveText(paste.tooManyLeaves(150, 151));
    await expect(insert(page)).toBeDisabled();
    await expectTop64(page);
    await shot(page, 'rpw12-paste-band');
    tops.push((await box(page)).y);
    expect(new Set(tops).size).toBe(1);
    expect(unrouted).toEqual([]);
  });

  test('S10g 높이 700 화면: 창이 화면 밖으로 넘치지 않고 창 안에서 스크롤', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 700 });
    const { unrouted } = await open(page, MANY(290));
    await page.getByRole('button', { name: paste.open }).click();
    await textBox(page).fill(OVER);
    await page.getByTestId('paste-bad-toggle').click();
    await expect(page.getByTestId('paste-over')).toBeVisible();
    await expectTop64(page);
    const { y, height } = await box(page);
    expect(y + height).toBeLessThanOrEqual(700 - 64 + 1);
    const scrolled = await dialog(page).evaluate((element) => {
      const before = element.scrollHeight > element.clientHeight;
      element.scrollTop = element.scrollHeight;
      return { before, top: element.scrollTop };
    });
    expect(scrolled.before).toBe(true);
    expect(scrolled.top).toBeGreaterThan(0);
    await expect(insert(page)).toBeInViewport();
    await shot(page, 'w5-low-700');
    expect(unrouted).toEqual([]);
  });

  test('S10h 트리 머리 [붙여넣기] 14px · 높이 36 · 옆 칩은 12px · 28', async ({
    page,
  }) => {
    const look = (name: string) =>
      page.getByRole('button', { name }).evaluate((element) => ({
        font: getComputedStyle(element).fontSize,
        height: element.getBoundingClientRect().height,
        line: getComputedStyle(element).textDecorationLine,
      }));
    const { unrouted } = await open(page, BASIC());
    expect(await look(paste.open)).toEqual({
      font: '14px',
      height: 36,
      line: 'underline',
    });
    expect(await look(outline.addChild)).toMatchObject({
      font: '12px',
      height: 28,
    });
    await shot(page, 'w6-tree-head');
    expect(unrouted).toEqual([]);
  });

  test('S10i 빈 상태 [붙여넣기] 14px · 높이 36', async ({ page }) => {
    const unrouted = await trapUnrouted(page);
    const api = await fakeDraftingApi(page);
    await signIn(page);
    const [projectId] = api.seed(PDF, []);
    await page.goto(`/drafting/projects/${projectId}/outline`);
    await expect(page.getByTestId('outline-empty')).toBeVisible();
    const look = await page
      .getByRole('button', { name: paste.open })
      .evaluate((element) => ({
        font: getComputedStyle(element).fontSize,
        height: element.getBoundingClientRect().height,
        line: getComputedStyle(element).textDecorationLine,
      }));
    expect(look).toEqual({ font: '14px', height: 36, line: 'underline' });
    await shot(page, 'w7-empty-state');
    expect(unrouted).toEqual([]);
  });
});
