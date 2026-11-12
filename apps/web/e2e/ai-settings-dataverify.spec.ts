// AD-02 데이터 검증 탭(밴드 DVA2 — 발주서 §3-3): LNB 「데이터 검증」 → /admin/ai-settings/dataverify(그린워싱으로 넘기지 않음) → 흐름 띠 마디 셋·칸 고름 →
// 입력 글 자리 안내(K1)·출력 안내 모듈 글(K2) → 자리를 지운 입력 글 저장은 서버 400 이 그 칸 오류로 → 되살려 POST 한 번({title, memo, modelSettings, prompts} — 바탕 판 GET 0).
// 빌드 결과를 실 모듈 줄(aiSettingModules(api))로 연다. 서버는 흉내(e2e/session.ts·e2e/accounts.ts·e2e/ai-settings-dataverify.ts).
// 글자는 문구 표(AI_SETTING_TEXT·DATAVERIFY_SETTING_TEXT) 값으로 단언한다. 글은 지어낸 것이다.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { ACCOUNT_TEXT } from '../src/entities/account/config/text.ts';
import { AI_SETTING_TEXT } from '../src/entities/ai-setting/config/text.ts';
import { DATAVERIFY_SETTING_TEXT } from '../src/entities/dataverify-setting/config/text.ts';
import { accountRow, fakeAccountsApi } from './accounts.ts';
import {
  DV_GROUPS,
  DV_REQUIRED,
  dvText,
  fakeDataverifySettingApi,
} from './ai-settings-dataverify.ts';
import { signIn } from './session.ts';

const t = AI_SETTING_TEXT;
const own = DATAVERIFY_SETTING_TEXT;
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

/** 계정 관리에서 LNB 「데이터 검증」 줄을 눌러 연다. */
async function open(page: Page) {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAccountsApi(page, [accountRow(1)]);
  const settings = await fakeDataverifySettingApi(page);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  await page
    .getByRole('navigation', { name: shell.menuLabel })
    .getByRole('button', { name: shell.menu.aiSettingsDataverify })
    .click();
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v2') }),
  ).toBeVisible();
  return { unrouted, settings };
}

const band = (page: Page) => page.getByRole('region', { name: f.title });
const picker = (page: Page) => page.getByRole('group', { name: f.picker });
const slot = (page: Page) => page.locator('[data-card="prompt-slot"]');
/** 고른 칸의 글 칸(칸 이름 「지시 글」·「입력 글」 + 「프롬프트」). */
const textOf = (page: Page, label: string) =>
  slot(page).getByRole('textbox', { name: `${label} ${t.prompt.text}` });
/** 입력 글 자리 안내 글(모듈 줄과 같은 꼴). */
const placeholderNote = (key: string) =>
  `${own.placeholders.lead(DV_REQUIRED[key]!)} — ${
    key === 'review_user' ? own.placeholders.review : own.placeholders.company
  } · ${own.placeholders.tail}`;

test('DVA2 열기: LNB 「데이터 검증」 → /admin/ai-settings/dataverify 그대로 · data-module · 제목 · 판 열(기본 판 + 지어낸 둘) · 요청은 목록 → v2 prompt-model 뿐(그린워싱·영문번역 0) · 흉내 밖 /api/ 0', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  expect(pathOf(page)).toBe('/admin/ai-settings/dataverify');
  await expect(
    page.locator('[data-screen="admin-ai-settings"]'),
  ).toHaveAttribute('data-module', 'dataverify');
  await expect(
    page.getByRole('heading', { name: t.title(own.module.name) }),
  ).toBeVisible();
  await expect(page.locator('[data-version]')).toHaveCount(3);
  await expect(page.locator('[data-version="default"]')).toBeVisible();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await expect(
    nav.getByRole('button', { name: shell.menu.aiSettingsDataverify }),
  ).toHaveAttribute('aria-current', 'page');
  await expect
    .poll(() => [...new Set(settings.keys())])
    .toEqual([
      'GET /ai-settings/dataverify',
      'GET /ai-settings/dataverify/12/prompt-model',
    ]);
  expect(unrouted).toEqual([]);
});

test('DVA2 칸·안내: 처음 칸 = 계산 계획 지시 글(KEY 소문자·라벨 「칸」·출력 안내 = 모듈 글) → 마디 3 리스크 진단 지시 글(모듈 글) → 입력 글(출력 안내 0 · 자리 안내 한 줄) → 계산 검토(지시 글 출력 안내 0 · 입력 글 안내에 기업 낱말 0) · 모델 칸 하나 · 구성 열', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  // D1·D9·D10: 처음 칸 {0,0} = plan_system · 첫 줄 라벨 「칸」 · KEY 소문자
  await expect(
    picker(page).locator('[aria-pressed="true"][data-prompt-key]'),
  ).toHaveAttribute('data-prompt-key', 'plan_system');
  await expect(band(page).locator('[data-flow-key]')).toHaveCount(3);
  await expect(band(page).getByTestId('flow-node-label')).toHaveText(
    DV_GROUPS.map(([, label]) => label),
  );
  await expect(slot(page).locator('span.w-40').first()).toHaveText(
    own.module.slotLabel,
  );
  const key = slot(page).getByTestId('slot-key');
  await expect(key).toHaveText('plan_system');
  await expect(key).toHaveCSS('text-transform', 'none');
  // K2: 출력 안내 = 모듈 글(공통 글 0)
  await expect(slot(page).getByTestId('output-note')).toHaveText(
    own.outputNotes.plan_system!,
  );
  await expect(slot(page).getByTestId('prompt-note')).toHaveCount(0);
  // 마디 3 → 리스크 진단 지시 글 · 모듈 글
  await band(page)
    .getByRole('button', { name: f.nodeLabel(3, '리스크 진단', false) })
    .click();
  await expect(key).toHaveText('insight_system');
  await expect(slot(page).getByTestId('output-note')).toHaveText(
    own.outputNotes.insight_system!,
  );
  // 칸 고름 「입력 글」 → 출력 안내 0 · 자리 안내 한 줄(K1)
  await picker(page).locator('[data-prompt-key="insight_user"]').click();
  await expect(key).toHaveText('insight_user');
  await expect(slot(page).getByTestId('output-note')).toHaveCount(0);
  await expect(slot(page).getByTestId('prompt-note')).toHaveText(
    placeholderNote('insight_user'),
  );
  // 마디 2 → 계산 검토 지시 글: 출력절 없음 → 안내 0
  await band(page)
    .getByRole('button', { name: f.nodeLabel(2, '계산 검토', false) })
    .click();
  await expect(key).toHaveText('review_system');
  await expect(slot(page).getByTestId('output-note')).toHaveCount(0);
  await expect(slot(page).getByTestId('prompt-note')).toHaveCount(0);
  await picker(page).locator('[data-prompt-key="review_user"]').click();
  const reviewNote = slot(page).getByTestId('prompt-note');
  await expect(reviewNote).toHaveText(placeholderNote('review_user'));
  for (const word of ['기업명', 'SASB', '중대토픽', '보고연도'])
    await expect(reviewNote).not.toContainText(word);
  // 모델 칸 하나 · 곁 글 = modelNote · webSearch 글 0
  const components = page.getByRole('region', { name: t.columns.component });
  await components.getByRole('button', { name: /^모델 설정/ }).click();
  const model = page.locator('[data-card="model-detail"]');
  await expect(model).toContainText(own.module.modelNote);
  await expect(model.getByRole('combobox')).toHaveCount(1);
  await expect(
    model.getByRole('textbox', { name: t.model.temperature }),
  ).toHaveValue('0.1');
  await expect(model).not.toContainText(/webSearch|웹 검색/);
  // 구성 열: 계산 도구 다섯 · 처리 값 넷(서버 label 그대로) · 고정 규칙 줄 = config
  await components.getByRole('button', { name: /^계산 도구/ }).click();
  await expect(page.locator('[data-card="fixed"] [data-fixed]')).toHaveCount(5);
  await components.getByRole('button', { name: /^처리 값/ }).click();
  await expect(page.locator('[data-card="fixed"] [data-fixed]')).toHaveCount(4);
  await expect(
    page.locator('[data-card="fixed"] [data-fixed="tolerance"]'),
  ).toHaveText(/판정 허용 오차\s*0\.0/);
  await components.getByRole('button', { name: /^고정 규칙/ }).click();
  await expect(page.getByTestId('fixed-rules').locator('li')).toHaveText([
    ...own.fixedRules,
  ]);
  expect(unrouted).toEqual([]);
});

test('DVA2 저장: 계산 검토 입력 글에서 {계산 계획의 산식 목록} 지움 + temperature 0.3 → 「고친 것 2개」 → 저장 → 400 → 창 줄 · 칸 「고칠 곳 있음」 · 칸 오류(서버 문장) → 되살려 저장 → POST 본문(모델 칸 하나 0.3 · 묶음 셋 칸 둘씩) · 바탕 판 GET 0 · 새 판 고름 · 알림', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  await band(page)
    .getByRole('button', { name: f.nodeLabel(2, '계산 검토', false) })
    .click();
  await picker(page).locator('[data-prompt-key="review_user"]').click();
  const original = dvText('review_user');
  const cut = original.replace('{계산 계획의 산식 목록}', '');
  await textOf(page, '입력 글').fill(cut);
  const components = page.getByRole('region', { name: t.columns.component });
  await components.getByRole('button', { name: /^모델 설정/ }).click();
  await page.getByRole('textbox', { name: t.model.temperature }).fill('0.3');
  const bar = page.getByTestId('save-bar');
  await expect(bar).toContainText(t.saveBar.count(2));
  await bar.getByRole('button', { name: t.saveBar.save }).click();
  const dialog = page.getByTestId('save-dialog');
  await dialog.getByRole('textbox', { name: t.save.name }).fill('지어낸 새 판');
  await dialog
    .getByRole('button', { name: t.save.confirm, exact: true })
    .click();
  const message = '입력 글에서 {계산 계획의 산식 목록} 자리를 지우면 안 돼요';
  await expect(dialog).toContainText(t.save.fieldRefused('입력 글', message));
  await dialog.getByRole('button', { name: t.save.cancel }).click();
  await expect(dialog).toHaveCount(0);
  // 칸 고름 그 칸 「고칠 곳 있음」 · 칸 오류는 서버 문장
  await components
    .getByRole('button', { name: new RegExp(`^${t.components.prompt}`) })
    .click();
  await expect(
    picker(page).locator('[data-prompt-key="review_user"]'),
  ).toContainText(f.refused);
  await expect(slot(page).getByTestId('text-error')).toHaveText(message);
  // 되살림 → 칸 오류 걷힘 → 다시 저장
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
    .toContain('GET /ai-settings/dataverify/13/prompt-model');
  await expect(page.locator('[data-version="13"]')).toBeVisible();
  const posts = settings.posted();
  expect(posts).toHaveLength(2);
  const body = posts[1] as {
    title: string;
    modelSettings: {
      steps: { key: string; temperature: number | null; webSearch: boolean }[];
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
  expect(body.modelSettings.steps).toHaveLength(1);
  expect(body.modelSettings.steps[0]).toMatchObject({
    key: 'shared',
    temperature: 0.3,
    webSearch: true,
  });
  expect(body.prompts.steps.map((step) => step.key)).toEqual(
    DV_GROUPS.map(([key]) => key),
  );
  for (const step of body.prompts.steps)
    expect(step.prompts.map((one) => one.key)).toEqual([
      `${step.key}_system`,
      `${step.key}_user`,
    ]);
  expect(body.prompts.steps[1]!.prompts[1]!.text).toBe(original);
  // 요청 순서(처음 나온 차례): 목록 → v2 prompt-model → POST → 새 판 prompt-model. 바탕 판 GET 0
  const order = settings
    .keys()
    .filter((key, index, all) => all.indexOf(key) === index);
  expect(order).toEqual([
    'GET /ai-settings/dataverify',
    'GET /ai-settings/dataverify/12/prompt-model',
    'POST /ai-settings/dataverify',
    'GET /ai-settings/dataverify/13/prompt-model',
  ]);
  expect(settings.keys().some((key) => /dataverify\/\d+$/.test(key))).toBe(
    false,
  );
  expect(unrouted).toEqual([]);
});
