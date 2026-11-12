// AD-02 그린워싱 탭(밴드 AS3b — 발주서 §3-6): 대상 단어 카드 → 판 초안 하나 → POST 한 번의 terms. 빌드 결과를 실 모듈 줄(aiSettingModules(api))로 연다.
// 서버는 흉내(e2e/session.ts·e2e/ai-settings.ts·e2e/ai-prompt-model.ts). 글자는 문구 표(AI_SETTING_TEXT·GREENWASH_SETTING_TEXT) 값으로 단언한다.
// 낱말은 지어낸 것이다(흉내의 기본 단어 목록 DEFAULT_TERMS).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { AI_SETTING_TEXT } from '../src/entities/ai-setting/config/text.ts';
import { GREENWASH_SETTING_TEXT } from '../src/entities/greenwash-setting/config/text.ts';
import { fakePromptModelApi, promptModel } from './ai-prompt-model.ts';
import { DEFAULT_TERMS, fakeAiSettingApi } from './ai-settings.ts';
import { signIn } from './session.ts';

const t = AI_SETTING_TEXT;
const g = GREENWASH_SETTING_TEXT;
const w = g.terms;

/** 흉내 밖 /api/ 요청을 적고 503 으로 끊는다(흉내보다 먼저 건다 — admin.spec 의 덫과 같은 꼴). */
async function trapUnrouted(page: Page) {
  const unrouted: string[] = [];
  await page.route(/\/api\//, (route) => {
    const url = new URL(route.request().url());
    unrouted.push(`${route.request().method()} ${url.pathname}`);
    return route.fulfill({ status: 503, body: '' });
  });
  return unrouted;
}

async function open(page: Page) {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const settings = await fakeAiSettingApi(page);
  await fakePromptModelApi(page);
  await page.goto('/admin/ai-settings');
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v3') }),
  ).toBeVisible();
  return { unrouted, settings };
}

const components = (page: Page) =>
  page.getByRole('region', { name: t.columns.component });
const openTerms = (page: Page) =>
  components(page)
    .getByRole('button', { name: new RegExp(`^${w.title}`) })
    .click();
const termSwitch = (page: Page, word: string) =>
  page.getByRole('switch', { name: w.switchLabel(word) });
const bar = (page: Page) => page.getByTestId('save-bar');

async function saveAs(page: Page, title: string) {
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: t.save.name }).fill(title);
  await dialog
    .getByRole('button', { name: t.save.confirm, exact: true })
    .click();
  return dialog;
}

type Body = { terms: unknown; modelSettings: unknown };
const posted = (settings: Awaited<ReturnType<typeof open>>['settings']) =>
  settings.sent('POST', '').map((call) => call.body as Body);

test('AS3b ① 대상 단어: 기본 판에서 끄고 더함 → 「고친 것 2개」 → 판정 칸 → 「3개」·셈 줄은 그린워싱 글 → 다 끄면 저장 꺼짐·POST 0 → 하나 켜고 저장 → POST 하나, terms = 기본 n + 1(차례·사용 그대로) · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  await page.locator('[data-version="default"]').click();
  await expect(
    page.getByRole('heading', { name: t.prompt.title('기본 설정') }),
  ).toBeVisible();
  await expect(
    components(page).getByRole('button', { name: new RegExp(`^${w.title}`) }),
  ).toContainText(w.sum(DEFAULT_TERMS.length));
  await openTerms(page);
  await expect(page.getByTestId('terms-card')).toBeVisible();
  await expect(page.locator('tbody tr')).toHaveCount(DEFAULT_TERMS.length);
  // 기본 판은 terms null → 기본 단어 목록을 다 켬(GET /api/greenwash/terms/default 한 번)
  expect(settings.termCalls).toHaveLength(1);
  await termSwitch(page, DEFAULT_TERMS[0]!).click();
  await page.getByRole('textbox', { name: w.input }).fill('지어낸 더한 단어');
  await page.getByRole('textbox', { name: w.input }).press('Enter');
  await expect(page.locator('tr[data-added]')).toHaveText(
    new RegExp('지어낸 더한 단어'),
  );
  await expect(bar(page)).toContainText(t.saveBar.count(2));
  // 판정 칸 글 고침 → 3개
  await components(page)
    .getByRole('button', { name: /^프롬프트/ })
    .click();
  await page
    .getByRole('region', { name: g.flow.title })
    .getByRole('button', { name: g.flow.nodeLabel(2, '지어낸 판정', false) })
    .click();
  await page
    .getByRole('textbox', { name: `지어낸 판정 ${t.prompt.text}` })
    .fill('지어낸 고친 판정 글');
  await expect(bar(page)).toContainText(t.saveBar.count(3));
  // 켠 단어를 다 끄면 [새 버전으로 저장] 꺼짐(눌러도 창 0·POST 0) + 카드 아래 글
  await openTerms(page);
  for (const word of [...DEFAULT_TERMS.slice(1), '지어낸 더한 단어'])
    await termSwitch(page, word).click();
  await expect(page.getByTestId('terms-none-enabled')).toHaveText(
    w.noneEnabled,
  );
  const save = bar(page).getByRole('button', { name: t.saveBar.save });
  await expect(save).toHaveAttribute('aria-disabled', 'true');
  await save.click({ force: true });
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(settings.sent('POST', '')).toHaveLength(0);
  // 하나 켜고 저장 → POST 하나
  await termSwitch(page, DEFAULT_TERMS[1]!).click();
  await expect(page.getByTestId('terms-none-enabled')).toHaveCount(0);
  await save.click();
  const dialog = await saveAs(page, '지어낸 단어 판');
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('notice')).toHaveText(t.save.done('v4'));
  const bodies = posted(settings);
  expect(bodies).toHaveLength(1);
  expect(bodies[0]!.terms).toEqual([
    { text: DEFAULT_TERMS[0], enabled: false },
    { text: DEFAULT_TERMS[1], enabled: true },
    { text: DEFAULT_TERMS[2], enabled: false },
    { text: '지어낸 더한 단어', enabled: false },
  ]);
  expect(unrouted).toEqual([]);
});

test('AS3b ① 단어를 안 고친 저장: 모델만 고친 v2(terms null) → terms: null · v3(목록) 복제 → 바탕 terms 그대로', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  await page.locator('[data-version="12"]').click();
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v2') }),
  ).toBeVisible();
  await components(page)
    .getByRole('button', { name: /^모델 설정/ })
    .click();
  await page
    .getByRole('textbox', { name: t.model.maxOutputTokens })
    .fill('3000');
  await bar(page).getByRole('button', { name: t.saveBar.save }).click();
  await expect(await saveAs(page, '지어낸 모델 판')).toHaveCount(0);
  await expect(page.getByTestId('notice')).toHaveText(t.save.done('v4'));
  // v3(목록) 를 고쳐 쓰지 않고 복제(구성은 모델 설정에 남아 있다 — 프롬프트로 옮겨 판 제목을 본다)
  await page.locator('[data-version="13"]').click();
  await components(page)
    .getByRole('button', { name: /^프롬프트/ })
    .click();
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v3') }),
  ).toBeVisible();
  await page.getByRole('button', { name: t.newVersion }).click();
  await expect(await saveAs(page, '지어낸 복제 판')).toHaveCount(0);
  await expect(page.getByTestId('notice')).toHaveText(t.save.done('v5'));
  const bodies = posted(settings);
  expect(bodies.map((body) => body.terms)).toEqual([
    null,
    [
      { text: '지어낸 초록낱말', enabled: true },
      { text: '친환경', enabled: false },
    ],
  ]);
  expect(unrouted).toEqual([]);
});

test('AS3b ① 400 TERMS_DUPLICATE: 저장 창 「대상 단어 — <웹 글>」·그 줄 빨강, 서버 문장은 안 보임', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  await openTerms(page);
  await page.getByRole('textbox', { name: w.input }).fill('지어낸 새 단어');
  await page.getByRole('textbox', { name: w.input }).press('Enter');
  await page.route(/\/api\/ai-settings\/greenwash(\?.*)?$/, (route) =>
    route.request().method() === 'POST' ?
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'TERMS_DUPLICATE',
            message: '지어낸 서버 겹침 문장',
            fields: { 'terms.2.text': ['지어낸 서버 겹침 문장'] },
            legacyCode: 'terms_duplicate',
          },
        }),
      })
    : route.fallback(),
  );
  await bar(page).getByRole('button', { name: t.saveBar.save }).click();
  const dialog = await saveAs(page, '지어낸 거절 판');
  await expect(dialog).toContainText(
    `${w.title} — ${w.refused.TERMS_DUPLICATE}`,
  );
  await expect(dialog).not.toContainText('지어낸 서버 겹침 문장');
  await expect(page.locator('tr[data-refused]')).toHaveCount(1);
  await expect(page.locator('tr[data-refused]')).toHaveAttribute(
    'data-term',
    '지어낸 새 단어',
  );
  expect(unrouted).toEqual([]);
});

test('AS3b ② 처리 흐름 띠: 셋째 열 0 · 마디 「3」 누름 → 단계 카드 머리 흉내 label(지어낸 고치기) · 고른 마디 aria-pressed · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  await expect(
    page.getByRole('region', { name: t.columns.category }),
  ).toHaveCount(0);
  // 적용 안내(RPW12)는 보고서 작성 탭에만 — 그린워싱 탭은 0.
  await expect(page.getByTestId('module-apply-note')).toHaveCount(0);
  const band = page.getByRole('region', { name: g.flow.title });
  const third = band.getByRole('button', {
    name: g.flow.nodeLabel(3, '지어낸 고치기', false),
  });
  await third.click();
  await expect(third).toHaveAttribute('aria-pressed', 'true');
  await expect(
    page.getByRole('textbox', { name: `지어낸 고치기 ${t.prompt.text}` }),
  ).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('GP2 AD-02 시안 값(GW3R-AD02 (c)): 마디 radius 8 · 고른 마디 2px 테두리 · 마디 이름 700 · 빈도 알약 · 끝 상자 grey-800 바탕 · 대상 단어 표 머리 support-grey-subtle 바탕', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  const band = page.getByRole('region', { name: g.flow.title });
  const node = band.getByRole('button', {
    name: g.flow.nodeLabel(3, '지어낸 고치기', false),
  });
  // C1 마디 radius · 높이 112, 고른 마디 2px grey-800
  await expect(node).toHaveCSS('border-top-left-radius', '8px');
  await expect(node).toHaveCSS('height', '112px');
  await expect(node).toHaveCSS('border-top-width', '1px');
  await node.click();
  await expect(node).toHaveAttribute('aria-pressed', 'true');
  await expect(node).toHaveCSS('border-top-width', '2px');
  await expect(node).toHaveCSS('border-top-color', 'rgb(56, 60, 64)');
  // C2 마디 이름 700 14
  const name = node.getByTestId('flow-node-name');
  await expect(name).toHaveCSS('font-weight', '700');
  await expect(name).toHaveCSS('font-size', '14px');
  // C4 빈도 알약: 바탕 #F3F4F5 · 모서리 full · 500 12 #383C40
  const runs = node.getByTestId('flow-runs');
  await expect(runs).toHaveCSS('background-color', 'rgb(243, 244, 245)');
  await expect(runs).toHaveCSS('border-top-left-radius', '9999px');
  await expect(runs).toHaveCSS('font-weight', '500');
  await expect(runs).toHaveCSS('color', 'rgb(56, 60, 64)');
  // C7 끝 상자 「결과 검토 화면」: grey-800 바탕
  await expect(band.locator('[data-flow-fixed="end"] rect')).toHaveCSS(
    'fill',
    'rgb(56, 60, 64)',
  );
  // C13 대상 단어 표 머리 칸: 바탕 #FAFBFB · 위 1px 선 · 500 14
  await openTerms(page);
  const head = page.getByTestId('terms-card').locator('thead th').nth(1);
  await expect(head).toHaveCSS('background-color', 'rgb(250, 251, 251)');
  await expect(head).toHaveCSS('border-top-width', '1px');
  await expect(head).toHaveCSS('font-size', '14px');
  await expect(head).toHaveCSS('height', '40px');
  expect(unrouted).toEqual([]);
});

test('GP4 AD-02 흐름 마디: 긴 이름의 칸을 고쳐 고른 마디가 「● 고침」을 달아도 이름 줄은 한 줄(다른 마디의 이름 줄 높이와 같다) · 전체 이름은 title 에', async ({
  page,
}) => {
  const long = '아주 긴 지어낸 단계 이름';
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAiSettingApi(page);
  await fakePromptModelApi(page);
  // 셋째 칸 label 만 긴 지어낸 이름으로(뒤에 건 길이 먼저 받는다)
  await page.route(
    /\/api\/ai-settings\/greenwash\/(\d+|default)\/prompt-model(\?.*)?$/,
    (route) => {
      const hit = /\/(\d+|default)\/prompt-model/.exec(
        new URL(route.request().url()).pathname,
      )!;
      const name =
        hit[1] === 'default' ? 'colab-2026-01-15-v1' : `setting-${hit[1]}`;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(promptModel(name)).replaceAll(
          '"지어낸 고치기"',
          JSON.stringify(long),
        ),
      });
    },
  );
  await page.goto('/admin/ai-settings');
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v3') }),
  ).toBeVisible();
  const band = page.getByRole('region', { name: g.flow.title });
  await band
    .getByRole('button', { name: g.flow.nodeLabel(3, long, false) })
    .click();
  await page
    .getByRole('textbox', { name: `${long} ${t.prompt.text}` })
    .fill('지어낸 고친 글');
  const node = band.getByRole('button', {
    name: g.flow.nodeLabel(3, long, true),
  });
  await expect(node).toHaveAttribute('aria-pressed', 'true');
  await expect(node.getByTestId('flow-edited')).toBeVisible();
  await expect(node.getByTestId('flow-node-label')).toHaveAttribute(
    'title',
    long,
  );
  const nameHeight = async (locator: typeof node) =>
    (await locator.getByTestId('flow-node-name').boundingBox())!.height;
  const other = band.getByRole('button', {
    name: g.flow.nodeLabel(1, '지어낸 찾기', false),
  });
  expect(await nameHeight(node)).toBe(await nameHeight(other));
  expect(await nameHeight(node)).toBe(24);
  if (process.env.GP4_SHOTS)
    await band.screenshot({
      path: `${process.env.GP4_SHOTS}/ad02-flow-edited.png`,
    });
  expect(unrouted).toEqual([]);
});
