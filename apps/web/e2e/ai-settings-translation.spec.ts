// AD-02 영문번역 탭(밴드 TRA1 — 발주서 §3-3): LNB 「영문번역」 → /admin/ai-settings/translation(그린워싱으로 넘기지 않음) → 흐름 띠 마디 다섯·칸 고름 →
// 칸 글·모델 칸 하나 고침 → POST 한 번({title, memo, modelSettings, prompts} — 바탕 판 GET 0). 빌드 결과를 실 모듈 줄(aiSettingModules(api))로 연다.
// 서버는 흉내(e2e/session.ts·e2e/accounts.ts·e2e/ai-settings-translation.ts). 글자는 문구 표(AI_SETTING_TEXT·TRANSLATION_SETTING_TEXT) 값으로 단언한다. 글은 지어낸 것이다.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { ACCOUNT_TEXT } from '../src/entities/account/config/text.ts';
import { AI_SETTING_TEXT } from '../src/entities/ai-setting/config/text.ts';
import { TRANSLATION_SETTING_TEXT } from '../src/entities/translation-setting/config/text.ts';
import { accountRow, fakeAccountsApi } from './accounts.ts';
import {
  TR_GROUPS,
  fakeTranslationSettingApi,
  trLabel,
} from './ai-settings-translation.ts';
import { signIn } from './session.ts';

const t = AI_SETTING_TEXT;
const f = TRANSLATION_SETTING_TEXT.flow;
const shell = ACCOUNT_TEXT.shell;

/** 흉내 밖 /api/ 요청을 적고 503 으로 끊는다(흉내보다 먼저 건다 — 그린워싱 spec 의 덫과 같은 꼴). */
async function trapUnrouted(page: Page) {
  const unrouted: string[] = [];
  await page.route(/\/api\//, (route) => {
    const url = new URL(route.request().url());
    unrouted.push(`${route.request().method()} ${url.pathname}`);
    return route.fulfill({ status: 503, body: '' });
  });
  return unrouted;
}

const pathOf = (page: Page) => new URL(page.url()).pathname;

/** 계정 관리에서 LNB 「영문번역」 줄을 눌러 연다. */
async function open(page: Page) {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAccountsApi(page, [accountRow(1)]);
  const settings = await fakeTranslationSettingApi(page);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  await page
    .getByRole('navigation', { name: shell.menuLabel })
    .getByRole('button', { name: shell.menu.aiSettingsTranslation })
    .click();
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v2') }),
  ).toBeVisible();
  return { unrouted, settings };
}

const band = (page: Page) => page.getByRole('region', { name: f.title });
const picker = (page: Page) => page.getByRole('group', { name: f.picker });

test('TRA1 열기: LNB 「영문번역」 → /admin/ai-settings/translation 그대로 · data-module · 제목 · 판 열(기본 판 + 지어낸 둘) · 요청은 목록 → v2 prompt-model 뿐 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  expect(pathOf(page)).toBe('/admin/ai-settings/translation');
  await expect(
    page.locator('[data-screen="admin-ai-settings"]'),
  ).toHaveAttribute('data-module', 'translation');
  await expect(
    page.getByRole('heading', {
      name: t.title(TRANSLATION_SETTING_TEXT.module.name),
    }),
  ).toBeVisible();
  await expect(page.locator('[data-version]')).toHaveCount(3);
  await expect(page.locator('[data-version="default"]')).toBeVisible();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await expect(
    nav.getByRole('button', { name: shell.menu.aiSettingsTranslation }),
  ).toHaveAttribute('aria-current', 'page');
  await expect
    .poll(() => [...new Set(settings.keys())])
    .toEqual([
      'GET /ai-settings/translation',
      'GET /ai-settings/translation/12/prompt-model',
    ]);
  expect(unrouted.filter((one) => one.includes('/ai-settings/'))).toEqual([]);
  expect(unrouted).toEqual([]);
});

test('TRA1 흐름 띠: 마디 다섯(서버 묶음 이름) → 「검수」 → 프롬프트 칸이 검수 칸 · 번역 → 「파트마다 하나」 펼침 → 칸 셋', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  const nodes = band(page).locator('[data-flow-key]');
  await expect(nodes).toHaveCount(5);
  await expect(band(page).getByTestId('flow-node-label')).toHaveText(
    TR_GROUPS.map(([, label]) => label),
  );
  await band(page)
    .getByRole('button', { name: f.nodeLabel(4, '지어낸 검수', false) })
    .click();
  await expect(
    page.getByRole('textbox', {
      name: `${trLabel('review')} ${t.prompt.text}`,
    }),
  ).toBeVisible();
  await expect(picker(page).locator('[data-prompt-key]')).toHaveCount(1);
  await band(page)
    .getByRole('button', { name: f.nodeLabel(1, '지어낸 번역', false) })
    .click();
  // 마디 누름은 묶음의 보이는 차례 첫 칸(공통 style_rules — 밴드 TRA2 D1)을 고르므로 「파트마다 하나」·「고른 문체 하나」는 접힘
  await expect(
    picker(page).locator('[data-prompt-key="style_rules"]'),
  ).toHaveAttribute('aria-pressed', 'true');
  const part = picker(page).getByRole('button', {
    name: new RegExp(`^${f.sections.part.title}`),
  });
  await expect(part).toHaveAttribute('aria-expanded', 'false');
  await part.click();
  await expect(part).toHaveAttribute('aria-expanded', 'true');
  const style = picker(page).getByRole('button', {
    name: new RegExp(`^${f.sections.style.title}`),
  });
  await expect(style).toHaveAttribute('aria-expanded', 'false');
  await style.click();
  await expect(style).toHaveAttribute('aria-expanded', 'true');
  await expect(
    picker(page).locator('[data-section="style"] [data-prompt-key]'),
  ).toHaveCount(2);
  await expect(
    picker(page).locator('[data-section="part"] [data-prompt-key]'),
  ).toHaveText([
    new RegExp(trLabel('tone_ceo_message')),
    new RegExp(trLabel('tone_story')),
    new RegExp(trLabel('tone_general')),
  ]);
  await picker(page).locator('[data-prompt-key="tone_story"]').click();
  await expect(
    page.getByRole('textbox', {
      name: `${trLabel('tone_story')} ${t.prompt.text}`,
    }),
  ).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('TRA2 시안 대조: 처음 칸 = 보이는 차례 첫 칸 style_rules · 이어 붙임 안내 한 줄 · 상세 라벨 「칸」· KEY 소문자 · 출력절 없는 칸 노란 안내 0 · 「고정 글」 카드는 이름만', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  // D1: 처음 열 때 고른 칸 = 공통 첫 칸(서버 차례 0번 tone_ceo_message 아님)
  await expect(
    picker(page).locator('[aria-pressed="true"][data-prompt-key]'),
  ).toHaveAttribute('data-prompt-key', 'style_rules');
  const slot = page.locator('[data-card="prompt-slot"]');
  await expect(slot).toHaveAttribute('aria-label', trLabel('style_rules'));
  // D8: 칸 고름 머리 아래 이어 붙임 안내(시안 .tr-lead 글)
  await expect(picker(page).getByTestId('flow-lead')).toHaveText(f.lead);
  // D9·D10: 첫 줄 라벨 「칸」 · KEY 소문자 그대로
  await expect(slot.locator('span.w-40').first()).toHaveText(
    TRANSLATION_SETTING_TEXT.module.slotLabel,
  );
  const key = slot.getByTestId('slot-key');
  await expect(key).toHaveText('style_rules');
  await expect(key).toHaveCSS('text-transform', 'none');
  // D4: 흉내 칸은 outputSection null — 노란 안내 0
  await expect(slot.getByTestId('output-note')).toHaveCount(0);
  // D2: 「고정 글」 카드는 이름만(글 몸 0) · 처리 값은 값 그대로
  await page
    .getByRole('region', { name: t.columns.component })
    .getByRole('button', { name: /^고정 글/ })
    .click();
  const fixed = page.locator('[data-card="fixed"] [data-fixed="base"]');
  await expect(fixed).toHaveText('지어낸 바탕 지시');
  await page
    .getByRole('region', { name: t.columns.component })
    .getByRole('button', { name: /^처리 값/ })
    .click();
  await expect(
    page.locator('[data-card="fixed"] [data-fixed="gate"]'),
  ).toHaveText(/지어낸 관문 점수\s*90/);
  expect(unrouted).toEqual([]);
});

test('TRA1 저장: 칸 글 + 모델 칸 하나(출력 상한·경로) 고침 → 고친 것 숫자 → [새 버전으로 저장] → POST 하나(본문 넷 — 모델 칸 셋·묶음 다섯·칸 열넷, temperature null) · 바탕 판 GET 0 · 새 판 고름 · 알림', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  // 칸 글 하나(번역 묶음 공통 「style_rules」 — 처음 고른 칸은 묶음 첫 칸)
  await picker(page).locator('[data-prompt-key="style_rules"]').click();
  await page
    .getByRole('textbox', {
      name: `${trLabel('style_rules')} ${t.prompt.text}`,
    })
    .fill('지어낸 고친 규칙 글');
  const bar = page.getByTestId('save-bar');
  await expect(bar).toContainText(t.saveBar.count(1));
  // 모델 칸 하나: 출력 상한 + 경로(temperature 칸은 꺼짐 그대로 — acceptsTemperature false)
  const components = page.getByRole('region', { name: t.columns.component });
  await components.getByRole('button', { name: /^모델 설정/ }).click();
  const ceo = '지어낸 번역 · 대표 글';
  await page
    .getByRole('textbox', { name: `${ceo} ${t.model.maxOutputTokens}` })
    .fill('3000');
  await page
    .getByRole('combobox', { name: `${ceo} ${t.model.route}` })
    .selectOption('fake-tr-b');
  await expect(
    page.getByRole('textbox', { name: `${ceo} ${t.model.temperature}` }),
  ).toHaveCount(0);
  // 모델 칸 하나(출력 상한·경로 둘을 고쳐도 칸 하나) 1 + 프롬프트 칸 1
  await expect(bar).toContainText(t.saveBar.count(2));
  await bar.getByRole('button', { name: t.saveBar.save }).click();
  const dialog = page.getByTestId('save-dialog');
  await dialog.getByRole('textbox', { name: t.save.name }).fill('지어낸 새 판');
  await dialog
    .getByRole('button', { name: t.save.confirm, exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('notice')).toHaveText(t.save.done('v3'));
  // 새 판(v3 — id 13)을 고른다: 그 판의 prompt-model 을 읽는다
  await expect
    .poll(() => settings.keys())
    .toContain('GET /ai-settings/translation/13/prompt-model');
  await expect(page.locator('[data-version="13"]')).toBeVisible();
  const posts = settings.posted();
  expect(posts).toHaveLength(1);
  const body = posts[0] as {
    title: string;
    memo: string;
    modelSettings: {
      steps: {
        key: string;
        route: string;
        temperature: number | null;
        maxOutputTokens: number;
      }[];
    };
    prompts: {
      steps: { key: string; prompts: { key: string; text: string }[] }[];
    };
  };
  expect(Object.keys(body).sort()).toEqual([
    'memo',
    'modelSettings',
    'prompts',
    'title',
  ]);
  expect(body.title).toBe('지어낸 새 판');
  expect(body.modelSettings.steps.map((step) => step.key)).toEqual([
    'translate_ceo',
    'translate_other',
    'review',
  ]);
  expect(body.modelSettings.steps[0]).toMatchObject({
    route: 'fake-tr-b',
    temperature: null,
    maxOutputTokens: 3000,
  });
  for (const step of body.modelSettings.steps)
    expect(step.temperature).toBeNull();
  expect(body.prompts.steps.map((step) => step.key)).toEqual(
    TR_GROUPS.map(([key]) => key),
  );
  expect(
    body.prompts.steps.flatMap((step) => step.prompts).map((one) => one.key),
  ).toHaveLength(14);
  expect(
    body.prompts.steps[0]!.prompts.find((one) => one.key === 'style_rules')!
      .text,
  ).toBe('지어낸 고친 규칙 글');
  // 요청 순서(처음 나온 차례 — 다시 읽는 목록은 겹쳐 하나로): 목록 → v2 prompt-model → POST → 새 판 prompt-model. 바탕 판 GET 0
  const order = settings
    .keys()
    .filter((key, index, all) => all.indexOf(key) === index);
  expect(order).toEqual([
    'GET /ai-settings/translation',
    'GET /ai-settings/translation/12/prompt-model',
    'POST /ai-settings/translation',
    'GET /ai-settings/translation/13/prompt-model',
  ]);
  expect(settings.keys().some((key) => /translation\/\d+$/.test(key))).toBe(
    false,
  );
  expect(unrouted).toEqual([]);
});
