// AD-02 보고서 작성 탭(밴드 RPA3 — 발주서 §3-3): LNB 「보고서 작성」 → /admin/ai-settings/drafting(그린워싱으로 넘기지 않음) → 흐름 띠 마디 둘·칸 고름 →
// 입력 글 자리 안내 · 출력 안내 0 · 모델 카드 곁 글 0(모의 안내 뺌 — RPA4, 이슈 490) · 근거 표지 규칙은 이름만 → 자리를 지운 글 저장은 서버 400 이 그 칸 오류로 →
// 되살려 POST 한 번({title, memo, modelSettings, prompts} — 바탕 판 GET 0).
// 빌드 결과를 실 모듈 줄(aiSettingModules(api))로 연다. 서버는 흉내(e2e/session.ts·e2e/accounts.ts·e2e/ai-settings-drafting.ts).
// 글자는 문구 표(AI_SETTING_TEXT·DRAFTING_SETTING_TEXT) 값으로 단언한다. 글은 지어낸 것이다.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { ACCOUNT_TEXT } from '../src/entities/account/config/text.ts';
import { AI_SETTING_TEXT } from '../src/entities/ai-setting/config/text.ts';
import { DRAFTING_SETTING_TEXT } from '../src/entities/drafting-setting/config/text.ts';
import { accountRow, fakeAccountsApi } from './accounts.ts';
import {
  RP_FIXED,
  RP_GROUPS,
  RP_MAX_OUTPUT,
  RP_MODELS,
  RP_REQUIRED,
  fakeDraftingSettingApi,
  rpText,
} from './ai-settings-drafting.ts';
import { signIn } from './session.ts';

const t = AI_SETTING_TEXT;
const own = DRAFTING_SETTING_TEXT;
const f = own.flow;
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

/** 계정 관리에서 LNB 「보고서 작성」 줄을 눌러 연다. */
async function open(page: Page) {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAccountsApi(page, [accountRow(1)]);
  const settings = await fakeDraftingSettingApi(page);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  await page
    .getByRole('navigation', { name: shell.menuLabel })
    .getByRole('button', { name: shell.menu.aiSettingsDrafting })
    .click();
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v2') }),
  ).toBeVisible();
  return { unrouted, settings };
}

const band = (page: Page) => page.getByRole('region', { name: f.title });
const picker = (page: Page) => page.getByRole('group', { name: f.picker });
const slot = (page: Page) => page.locator('[data-card="prompt-slot"]');
/** 고른 칸의 글 칸(칸 이름 + 「프롬프트」). */
const textOf = (page: Page, label: string) =>
  slot(page).getByRole('textbox', {
    name: `${label} ${t.prompt.text}`,
    exact: true,
  });
const node = (page: Page, key: string) =>
  band(page).locator(`[data-flow-key="${key}"]`);
/** 자리 안내 글(모듈 줄과 같은 꼴). */
const placeholderNote = (key: string) =>
  `${own.placeholders.lead(RP_REQUIRED[key]!)} · ${own.placeholders.tail}`;

test('RPA3 열기: LNB 「보고서 작성」 → /admin/ai-settings/drafting 그대로 · data-module · 제목 · 판 열(기본 판 + 지어낸 둘) · 요청은 목록 → v2 prompt-model 뿐 · 흉내 밖 /api/ 0 · 마디 이름 넘침 0', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  expect(pathOf(page)).toBe('/admin/ai-settings/drafting');
  await expect(
    page.locator('[data-screen="admin-ai-settings"]'),
  ).toHaveAttribute('data-module', 'drafting');
  await expect(
    page.getByRole('heading', { name: t.title(own.module.name) }),
  ).toBeVisible();
  await expect(page.locator('[data-version]')).toHaveCount(3);
  await expect(page.locator('[data-version="default"]')).toBeVisible();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await expect(
    nav.getByRole('button', { name: shell.menu.aiSettingsDrafting }),
  ).toHaveAttribute('aria-current', 'page');
  await expect
    .poll(() => [...new Set(settings.keys())])
    .toEqual([
      'GET /ai-settings/drafting',
      'GET /ai-settings/drafting/12/prompt-model',
    ]);
  // 마디는 서버 label — 마디 상자 안에 들고(세로 넘침 0) 이름이 잘리지 않는다(가로 넘침 0)
  await expect(band(page).getByTestId('flow-node-label')).toHaveText(
    RP_GROUPS.map(([, label]) => label),
  );
  const overflow = await band(page)
    .locator('[data-flow-key]')
    .evaluateAll((nodes) =>
      nodes.flatMap((one) => {
        const label = one.querySelector('[data-testid="flow-node-label"]')!;
        return (
            one.scrollHeight > one.clientHeight ||
              label.scrollWidth > label.clientWidth
          ) ?
            [one.getAttribute('data-flow-key')]
          : [];
      }),
    );
  expect(overflow).toEqual([]);
  expect(unrouted).toEqual([]);
});

test('RPA3 칸·안내·모델·구성: 처음 칸 = map_system(KEY 소문자·라벨 「칸」·안내 0) → 마디 2 「초안 짓기」 입력 글(자리 안내 한 줄 — 세 자리) · 네 칸 출력 안내 0 · 모델 칸 둘(서버 label) · 곁 글 0(모의 안내 뺌) · webSearch 글 0 · 근거 표지 규칙 이름만 · 실행 규칙 넷', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  // D1·D9·D10: 처음 칸 {0,0} = map_system · 첫 줄 라벨 「칸」 · KEY 소문자
  await expect(
    picker(page).locator('[aria-pressed="true"][data-prompt-key]'),
  ).toHaveAttribute('data-prompt-key', 'map_system');
  await expect(band(page).locator('[data-flow-key]')).toHaveCount(2);
  await expect(slot(page).locator('span.w-40').first()).toHaveText(
    own.module.slotLabel,
  );
  const key = slot(page).getByTestId('slot-key');
  await expect(key).toHaveText('map_system');
  await expect(key).toHaveCSS('text-transform', 'none');
  const output = slot(page).getByTestId('output-note');
  const note = slot(page).getByTestId('prompt-note');
  await expect(output).toHaveCount(0);
  await expect(note).toHaveCount(0);
  // 칸 고름 「입력 글」(목차 달기) → 자리 안내 한 줄(두 자리)
  await picker(page).locator('[data-prompt-key="map_user"]').click();
  await expect(key).toHaveText('map_user');
  await expect(output).toHaveCount(0);
  await expect(note).toHaveText(placeholderNote('map_user'));
  // 마디 2 → 「초안 짓기」 · 머리 빈도 글 · 지시 글 안내 0 · 입력 글 자리 안내(세 자리)
  await node(page, 'draft').click();
  await expect(picker(page).locator('p').first()).toContainText('초안 짓기');
  await expect(picker(page).getByTestId('flow-step-head')).toHaveText(
    f.steps.draft.head,
  );
  await expect(picker(page).locator('[data-prompt-key]')).toHaveText([
    /^지시 글draft_system/,
    /^입력 글draft_user/,
  ]);
  await expect(key).toHaveText('draft_system');
  await expect(note).toHaveCount(0);
  await expect(output).toHaveCount(0);
  await picker(page).locator('[data-prompt-key="draft_user"]').click();
  await expect(note).toHaveText(placeholderNote('draft_user'));
  await expect(output).toHaveCount(0);
  // 흐름 띠 상자·갈래 글 = config
  await expect(band(page).locator('[data-flow-fixed="check"]')).toHaveText(
    f.check,
  );
  await expect(band(page).locator('[data-flow-branch]')).toHaveText(f.branch);
  // 모델 카드: 칸 둘(서버 label) · 곁 글 0(모의 위끝 안내 뺌 — RPA4) · 출력 상한 = 읽은 값 · webSearch 글 0
  const components = page.getByRole('region', { name: t.columns.component });
  await components.getByRole('button', { name: /^모델 설정/ }).click();
  const model = page.locator('[data-card="model-detail"]');
  await expect(model.locator('[data-step]')).toHaveCount(2); // 분모: 카드가 그려졌다
  await expect(model).not.toContainText('모의');
  await expect(model).not.toContainText('4,000');
  for (const [step, label] of RP_MODELS) {
    await expect(model.locator(`[data-step="${step}"] dt`).first()).toHaveText(
      `${label} ${t.model.route}`,
    );
    await expect(
      model.getByRole('textbox', {
        name: `${label} ${t.model.maxOutputTokens}`,
      }),
    ).toHaveValue(String(RP_MAX_OUTPUT));
  }
  await expect(model.getByTestId('model-uses')).toHaveText([
    t.model.uses([RP_GROUPS[0][1]]),
    t.model.uses([RP_GROUPS[1][1]]),
  ]);
  await expect(model).not.toContainText(/webSearch|웹 검색/);
  // 구성 열(Q5 — 모듈 줄 0): 모델 설정 · 프롬프트 · fixed 둘. 근거 표지 규칙은 이름만(값 0, Q2) · 실행 규칙 넷은 값 그대로
  const rows = components.getByRole('button');
  await expect(rows).toHaveCount(4);
  await expect(
    components.getByRole('button', { name: /^고정 규칙/ }),
  ).toHaveCount(0);
  await components
    .getByRole('button', {
      name: new RegExp(`^${RP_FIXED[0]!.label.replace(/[()]/g, '\\$&')}`),
    })
    .click();
  // 항목 모두 이름만(값 0 — 항목 수는 흉내 그대로, RPQ1 꼴 markers·writing)
  const rules = page.locator('[data-card="fixed"] [data-fixed]');
  await expect(rules).toHaveCount(RP_FIXED[0]!.items.length);
  for (const item of RP_FIXED[0]!.items) {
    await expect(
      page.locator(`[data-card="fixed"] [data-fixed="${item.key}"]`),
    ).toHaveText(item.label);
    await expect(page.locator('[data-card="fixed"]')).not.toContainText(
      String(item.value),
    );
  }
  await components.getByRole('button', { name: /^실행 규칙/ }).click();
  const fixed = page.locator('[data-card="fixed"] [data-fixed]');
  await expect(fixed).toHaveCount(4);
  await expect(fixed.first()).toHaveText(/페이지 글 상한\(자\)\s*1,?111/);
  expect(unrouted).toEqual([]);
});

test('RPA3 저장: 초안 짓기 입력 글에서 {페이지 글} 지움 + 초안 짓기 모델 temperature 0.3 → 「고친 것 2개」 → 저장 → 400 → 창 줄 · 칸 「고칠 곳 있음」 · 칸 오류(서버 문장) → 되살림 → POST 본문(모델 칸 둘 — draft 0.3 · webSearch false · 위끝 읽은 값 · 묶음 둘 칸 2·2) · 바탕 판 GET 0 · 새 판 고름 · 알림', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  await node(page, 'draft').click();
  await picker(page).locator('[data-prompt-key="draft_user"]').click();
  const original = rpText('draft_user');
  const cut = original.replace('\n{페이지 글}', '');
  expect(cut).not.toContain('{페이지 글}');
  await textOf(page, '입력 글').fill(cut);
  const components = page.getByRole('region', { name: t.columns.component });
  await components.getByRole('button', { name: /^모델 설정/ }).click();
  await page
    .getByRole('textbox', {
      name: `${RP_MODELS[1][1]} ${t.model.temperature}`,
    })
    .fill('0.3');
  const bar = page.getByTestId('save-bar');
  await expect(bar).toContainText(t.saveBar.count(2));
  await bar.getByRole('button', { name: t.saveBar.save }).click();
  const dialog = page.getByTestId('save-dialog');
  await dialog.getByRole('textbox', { name: t.save.name }).fill('지어낸 새 판');
  await dialog
    .getByRole('button', { name: t.save.confirm, exact: true })
    .click();
  const message = '지어낸 자리 거절 {페이지 글}';
  await expect(dialog).toContainText(t.save.fieldRefused('입력 글', message));
  await dialog.getByRole('button', { name: t.save.cancel }).click();
  await expect(dialog).toHaveCount(0);
  // 칸 고름 그 칸 「고칠 곳 있음」 · 칸 오류는 서버 문장
  await components
    .getByRole('button', { name: new RegExp(`^${t.components.prompt}`) })
    .click();
  await node(page, 'draft').click();
  await expect(
    picker(page).locator('[data-prompt-key="draft_user"]'),
  ).toContainText(f.refused);
  await expect(node(page, 'draft')).toContainText(f.refused);
  await picker(page).locator('[data-prompt-key="draft_user"]').click();
  await expect(slot(page).getByTestId('text-error')).toHaveText(message);
  // 되살림 → 칸 오류 걷힘 → 다시 저장(남은 고침은 temperature 하나)
  await textOf(page, '입력 글').fill(original);
  await expect(slot(page).getByTestId('text-error')).toHaveCount(0);
  await expect(bar).toContainText(t.saveBar.count(1));
  await bar.getByRole('button', { name: t.saveBar.save }).click();
  await dialog.getByRole('textbox', { name: t.save.name }).fill('지어낸 새 판');
  await dialog
    .getByRole('button', { name: t.save.confirm, exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('notice')).toHaveText(t.save.done('v3'));
  await expect
    .poll(() => settings.keys())
    .toContain('GET /ai-settings/drafting/13/prompt-model');
  await expect(page.locator('[data-version="13"]')).toBeVisible();
  const posts = settings.posted();
  expect(posts).toHaveLength(2);
  const body = posts[1] as {
    title: string;
    modelSettings: {
      steps: {
        key: string;
        temperature: number | null;
        webSearch: boolean;
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
  expect(body.modelSettings.steps).toHaveLength(2);
  expect(body.modelSettings.steps[0]).toMatchObject({
    key: 'map',
    temperature: 0,
    webSearch: false,
    maxOutputTokens: RP_MAX_OUTPUT,
  });
  expect(body.modelSettings.steps[1]).toMatchObject({
    key: 'draft',
    temperature: 0.3,
    webSearch: false,
    maxOutputTokens: RP_MAX_OUTPUT,
  });
  expect(body.prompts.steps.map((step) => step.key)).toEqual(
    RP_GROUPS.map(([key]) => key),
  );
  for (const [index, step] of body.prompts.steps.entries())
    expect(step.prompts.map((one) => one.key)).toEqual([
      ...RP_GROUPS[index]![2],
    ]);
  expect(body.prompts.steps[1]!.prompts[1]!.text).toBe(original);
  // 요청 순서(처음 나온 차례): 목록 → v2 prompt-model → POST → 새 판 prompt-model. 바탕 판 GET 0
  const order = settings
    .keys()
    .filter((one, index, all) => all.indexOf(one) === index);
  expect(order).toEqual([
    'GET /ai-settings/drafting',
    'GET /ai-settings/drafting/12/prompt-model',
    'POST /ai-settings/drafting',
    'GET /ai-settings/drafting/13/prompt-model',
  ]);
  expect(settings.keys().some((one) => /drafting\/\d+$/.test(one))).toBe(false);
  expect(unrouted).toEqual([]);
});

test('RPW12 적용 안내: 제목 바로 아래 왼쪽 한 줄(문구 표 글 · 12px · 회색) — 제목 묶음과 12 · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  const note = page.getByTestId('module-apply-note');
  await expect(note).toHaveCount(1);
  await expect(note).toHaveText(own.applyNote);
  const look = await note.evaluate((element) => {
    const style = getComputedStyle(element);
    const title = element.previousElementSibling!.getBoundingClientRect();
    const box = element.getBoundingClientRect();
    const main = element.parentElement!.getBoundingClientRect();
    return {
      size: style.fontSize,
      gap: Math.round(box.top - title.bottom),
      left: Math.round(box.left - main.left),
    };
  });
  expect(look).toEqual({ size: '12px', gap: 12, left: 0 });
  expect(unrouted).toEqual([]);
});
