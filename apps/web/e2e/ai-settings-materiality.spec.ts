// AD-02 중대성평가 IRO 탭(밴드 IRA2 — 발주서 §3-3): LNB 「중대성평가」 → /admin/ai-settings/materiality(그린워싱으로 넘기지 않음) → 흐름 띠 마디 다섯 + 신뢰 출처·칸 고름 →
// 자리 안내(K1)·출력 안내 모듈 글(K2) · 분석 모델 temperature 줄 0(K3) · 실행 규칙 카드 하나(Q1) → 자리를 지운 글 저장은 서버 400 이 그 칸 오류로 →
// 되살려 POST 한 번({title, memo, modelSettings, prompts} — 분석 temperature null · 바탕 판 GET 0).
// 빌드 결과를 실 모듈 줄(aiSettingModules(api))로 연다. 서버는 흉내(e2e/session.ts·e2e/accounts.ts·e2e/ai-settings-materiality.ts).
// 글자는 문구 표(AI_SETTING_TEXT·MATERIALITY_SETTING_TEXT) 값으로 단언한다. 글은 지어낸 것이다.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { ACCOUNT_TEXT } from '../src/entities/account/config/text.ts';
import { AI_SETTING_TEXT } from '../src/entities/ai-setting/config/text.ts';
import { MATERIALITY_SETTING_TEXT } from '../src/entities/materiality-setting/config/text.ts';
import { accountRow, fakeAccountsApi } from './accounts.ts';
import {
  IR_GROUPS,
  IR_REQUIRED,
  fakeMaterialitySettingApi,
  irText,
} from './ai-settings-materiality.ts';
import { signIn } from './session.ts';

const t = AI_SETTING_TEXT;
const own = MATERIALITY_SETTING_TEXT;
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

/** 계정 관리에서 LNB 「중대성평가」 줄을 눌러 연다. */
async function open(page: Page) {
  const unrouted = await trapUnrouted(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAccountsApi(page, [accountRow(1)]);
  const settings = await fakeMaterialitySettingApi(page);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  await page
    .getByRole('navigation', { name: shell.menuLabel })
    .getByRole('button', { name: shell.menu.aiSettingsMateriality })
    .click();
  await expect(
    page.getByRole('heading', { name: t.prompt.title('v2') }),
  ).toBeVisible();
  return { unrouted, settings };
}

const band = (page: Page) => page.getByRole('region', { name: f.title });
const picker = (page: Page) => page.getByRole('group', { name: f.picker });
const slot = (page: Page) => page.locator('[data-card="prompt-slot"]');
/** 고른 칸의 글 칸(칸 이름 + 「프롬프트」 — 「금융」은 「비금융」과 갈라야 해 exact). */
const textOf = (page: Page, label: string) =>
  slot(page).getByRole('textbox', {
    name: `${label} ${t.prompt.text}`,
    exact: true,
  });
const node = (page: Page, key: string) =>
  band(page).locator(`[data-flow-key="${key}"]`);
/** 자리 안내 글(모듈 줄과 같은 꼴). */
const placeholderNote = (key: string) =>
  `${own.placeholders.lead(IR_REQUIRED[key]!)} — ${own.placeholders.from[key]} · ${own.placeholders.tail}`;

test('IRA2 열기: LNB 「중대성평가」 → /admin/ai-settings/materiality 그대로 · data-module · 제목 · 판 열(기본 판 + 지어낸 둘) · 요청은 목록 → v2 prompt-model 뿐 · 흉내 밖 /api/ 0 · 마디 이름 넘침 0', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  expect(pathOf(page)).toBe('/admin/ai-settings/materiality');
  await expect(
    page.locator('[data-screen="admin-ai-settings"]'),
  ).toHaveAttribute('data-module', 'materiality');
  await expect(
    page.getByRole('heading', { name: t.title(own.module.name) }),
  ).toBeVisible();
  await expect(page.locator('[data-version]')).toHaveCount(3);
  await expect(page.locator('[data-version="default"]')).toBeVisible();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await expect(
    nav.getByRole('button', { name: shell.menu.aiSettingsMateriality }),
  ).toHaveAttribute('aria-current', 'page');
  await expect
    .poll(() => [...new Set(settings.keys())])
    .toEqual([
      'GET /ai-settings/materiality',
      'GET /ai-settings/materiality/12/prompt-model',
    ]);
  // Q3: 마디는 서버 label — 마디 상자 안에 들고(세로 넘침 0) 이름이 잘리지 않는다(가로 넘침 0)
  await expect(band(page).getByTestId('flow-node-label')).toHaveText(
    IR_GROUPS.map(([, label]) => label),
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

test('IRA2·IRA3 칸·안내·모델·구성: 처음 칸 = 규제 지시 글(KEY 소문자·라벨 「칸」·출력 안내 = v211 모듈 글·자리 안내 = 신뢰 출처 글) · 규제 칸 둘 → 입력 글(출력 0·안내 = { } 글) → 마디 2 칸 넷 · 키워드 입력(출력 안내·{ } 글) · 이슈 입력({ } 글) → 마디 5 경로 입력 글 → 신뢰 출처 둘(안내 0) · 분석 temperature 줄 0 · 실행 규칙 하나 8개', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  // D1·D9·D10: 처음 칸 {0,0} = regulation_system · 첫 줄 라벨 「칸」 · KEY 소문자
  await expect(
    picker(page).locator('[aria-pressed="true"][data-prompt-key]'),
  ).toHaveAttribute('data-prompt-key', 'regulation_system');
  await expect(band(page).locator('[data-flow-key]')).toHaveCount(6);
  await expect(picker(page).locator('[data-prompt-key]')).toHaveCount(2);
  await expect(slot(page).locator('span.w-40').first()).toHaveText(
    own.module.slotLabel,
  );
  const key = slot(page).getByTestId('slot-key');
  await expect(key).toHaveText('regulation_system');
  await expect(key).toHaveCSS('text-transform', 'none');
  const output = slot(page).getByTestId('output-note');
  const note = slot(page).getByTestId('prompt-note');
  await expect(output).toHaveText(own.outputNotes.regulation_system!);
  await expect(note).toHaveText(
    `${own.placeholders.whitelist(['{신뢰 출처 목록}'])} · ${own.placeholders.tail}`,
  );
  // 칸 고름 「입력 글」 → 출력 안내 0 · 안내 = 「{ } 칸은…」(시안 v211)
  await picker(page).locator('[data-prompt-key="regulation_prefix"]').click();
  await expect(key).toHaveText('regulation_prefix');
  await expect(output).toHaveCount(0);
  await expect(note).toHaveText(own.inputNote);
  // 마디 2 → 칸 넷 · 머리 빈도 글 · 「키워드 입력」 출력 안내 = 모듈 글 · 안내 = 「{ } 칸은…」
  await node(page, 'controversy').click();
  await expect(picker(page).locator('[data-prompt-key]')).toHaveCount(4);
  await expect(picker(page).getByTestId('flow-step-head')).toHaveText(
    f.steps.controversy.head,
  );
  await picker(page).locator('[data-prompt-key="keywords_prefix"]').click();
  await expect(output).toHaveText(own.outputNotes.keywords_prefix!);
  await expect(note).toHaveText(own.inputNote);
  // 「이슈 입력」 → 출력 안내 0 · 안내 = 「{ } 칸은…」
  await picker(page).locator('[data-prompt-key="controversy_prefix"]').click();
  await expect(key).toHaveText('controversy_prefix');
  await expect(output).toHaveCount(0);
  await expect(note).toHaveText(own.inputNote);
  // 마디 5 → 경로 입력 글: 안내에 1부 자리 낱말 0
  await node(page, 'pathway').click();
  await picker(page).locator('[data-prompt-key="pathway_input"]').click();
  await expect(note).toHaveText(placeholderNote('pathway_input'));
  for (const word of ['검색', '토픽', '키워드', '산업', '신뢰 출처'])
    await expect(note).not.toContainText(word);
  // 신뢰 출처 마디 → 칸 「비금융」·「금융」 · 안내 0 둘 다
  await node(page, 'whitelist').click();
  await expect(picker(page).locator('[data-prompt-key]')).toHaveText([
    /^비금융whitelist_non_financial/,
    /^금융whitelist_financial/,
  ]);
  for (const one of ['whitelist_non_financial', 'whitelist_financial']) {
    await picker(page).locator(`[data-prompt-key="${one}"]`).click();
    await expect(key).toHaveText(one);
    await expect(note).toHaveCount(0);
    await expect(output).toHaveCount(0);
  }
  // 모델 카드: 줄 묶음 둘 · 리서치 temperature 0.1 · 분석 temperature 줄 0(K3) · 출력 상한 둘 · 쓰는 곳 둘 · webSearch 글 0
  const components = page.getByRole('region', { name: t.columns.component });
  await components.getByRole('button', { name: /^모델 설정/ }).click();
  const model = page.locator('[data-card="model-detail"]');
  await expect(model).toContainText(own.module.modelNote);
  await expect(model.locator('[data-step]')).toHaveCount(2);
  await expect(
    model.getByRole('textbox', { name: `리서치 모델 ${t.model.temperature}` }),
  ).toHaveValue('0.1');
  const analysis = model.locator('[data-step="analysis"]');
  // 줄은 모델 · 출력 상한 둘(temperature 줄 0) + 쓰는 곳(숨은 dt)
  await expect(analysis.locator('dt')).toHaveCount(3);
  await expect(analysis.locator('dt').nth(0)).toHaveText(
    `분석 모델 ${t.model.route}`,
  );
  await expect(analysis.locator('dt').nth(1)).toHaveText(
    `분석 모델 ${t.model.maxOutputTokens}`,
  );
  await expect(analysis).not.toContainText(t.model.temperature);
  await expect(analysis.locator('[data-value="temperature"]')).toHaveCount(0);
  await expect(
    model.getByRole('textbox', { name: new RegExp(t.model.maxOutputTokens) }),
  ).toHaveCount(2);
  await expect(model.getByTestId('model-uses')).toHaveText([
    t.model.uses(['규제·정책 리서치', '컨트로버시 리서치', '신뢰 출처 목록']),
    t.model.uses(['환경·사회 영향 정의', '재무 영향 정의', '재무 영향 경로']),
  ]);
  await expect(model).not.toContainText(/webSearch|웹 검색/);
  // 구성 열: 실행 규칙 하나(Q1 가 — 웹 검색 둘 + 실행 규칙 여섯) · 웹 검색 줄 0 · 고정 규칙 줄 = config
  await expect(
    components.getByRole('button', { name: /^웹 검색/ }),
  ).toHaveCount(0);
  await components.getByRole('button', { name: /^실행 규칙/ }).click();
  const fixed = page.locator('[data-card="fixed"] [data-fixed]');
  await expect(fixed).toHaveCount(8);
  await expect(fixed.first()).toHaveText(
    /웹 검색 · 리서치 모델\s*지어낸 늘 검색/,
  );
  await components.getByRole('button', { name: /^고정 규칙/ }).click();
  await expect(page.getByTestId('fixed-rules').locator('li')).toHaveText([
    ...own.fixedRules,
  ]);
  expect(unrouted).toEqual([]);
});

test('IRA2·IRA3 저장: 영향 입력 글에서 {토픽} 지움 + 리서치 temperature 0.3 → 「고친 것 2개」 → 저장 → 400 → 창 줄 · 칸 「고칠 곳 있음」 · 칸 오류(서버 문장) → 되살림 + 신뢰 출처 「금융」 고침 → POST 본문(모델 칸 둘 — 분석 temperature null · 묶음 여섯 칸 2·4·2·2·2·2) · 바탕 판 GET 0 · 새 판 고름 · 알림', async ({
  page,
}) => {
  const { unrouted, settings } = await open(page);
  await node(page, 'impact').click();
  await picker(page).locator('[data-prompt-key="impact_input"]').click();
  const original = irText('impact_input');
  const cut = original.replace('{토픽}\n', '');
  expect(cut).not.toContain('{토픽}');
  await textOf(page, '입력 글').fill(cut);
  const components = page.getByRole('region', { name: t.columns.component });
  await components.getByRole('button', { name: /^모델 설정/ }).click();
  await page
    .getByRole('textbox', { name: `리서치 모델 ${t.model.temperature}` })
    .fill('0.3');
  const bar = page.getByTestId('save-bar');
  await expect(bar).toContainText(t.saveBar.count(2));
  await bar.getByRole('button', { name: t.saveBar.save }).click();
  const dialog = page.getByTestId('save-dialog');
  await dialog.getByRole('textbox', { name: t.save.name }).fill('지어낸 새 판');
  await dialog
    .getByRole('button', { name: t.save.confirm, exact: true })
    .click();
  const message = '입력 글에서 {토픽} 자리를 지우면 안 돼요';
  await expect(dialog).toContainText(t.save.fieldRefused('입력 글', message));
  await dialog.getByRole('button', { name: t.save.cancel }).click();
  await expect(dialog).toHaveCount(0);
  // 칸 고름 그 칸 「고칠 곳 있음」 · 칸 오류는 서버 문장
  await components
    .getByRole('button', { name: new RegExp(`^${t.components.prompt}`) })
    .click();
  await node(page, 'impact').click();
  await expect(
    picker(page).locator('[data-prompt-key="impact_input"]'),
  ).toContainText(f.refused);
  await picker(page).locator('[data-prompt-key="impact_input"]').click();
  await expect(slot(page).getByTestId('text-error')).toHaveText(message);
  // 되살림 → 칸 오류 걷힘 → 신뢰 출처 「금융」 고침 → 다시 저장
  await textOf(page, '입력 글').fill(original);
  await expect(slot(page).getByTestId('text-error')).toHaveCount(0);
  await expect(bar).toContainText(t.saveBar.count(1));
  await node(page, 'whitelist').click();
  await picker(page).locator('[data-prompt-key="whitelist_financial"]').click();
  const financial = `${irText('whitelist_financial')}\n지어낸 출처 한 줄`;
  await textOf(page, '금융').fill(financial);
  await expect(bar).toContainText(t.saveBar.count(2));
  await expect(node(page, 'whitelist')).toContainText(f.edited);
  await bar.getByRole('button', { name: t.saveBar.save }).click();
  await dialog.getByRole('textbox', { name: t.save.name }).fill('지어낸 새 판');
  await dialog
    .getByRole('button', { name: t.save.confirm, exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('notice')).toHaveText(t.save.done('v3'));
  await expect
    .poll(() => settings.keys())
    .toContain('GET /ai-settings/materiality/13/prompt-model');
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
  expect(body.modelSettings.steps).toHaveLength(2);
  expect(body.modelSettings.steps[0]).toMatchObject({
    key: 'research',
    temperature: 0.3,
    webSearch: true,
  });
  expect(body.modelSettings.steps[1]).toMatchObject({
    key: 'analysis',
    temperature: null,
    webSearch: false,
  });
  expect(body.prompts.steps.map((step) => step.key)).toEqual(
    IR_GROUPS.map(([key]) => key),
  );
  expect(body.prompts.steps.map((step) => step.prompts.length)).toEqual([
    2, 4, 2, 2, 2, 2,
  ]);
  for (const [index, step] of body.prompts.steps.entries())
    expect(step.prompts.map((one) => one.key)).toEqual([
      ...IR_GROUPS[index]![2],
    ]);
  expect(body.prompts.steps[2]!.prompts[1]!.text).toBe(original);
  expect(body.prompts.steps[5]!.prompts[1]!.text).toBe(financial);
  // 요청 순서(처음 나온 차례): 목록 → v2 prompt-model → POST → 새 판 prompt-model. 바탕 판 GET 0
  const order = settings
    .keys()
    .filter((one, index, all) => all.indexOf(one) === index);
  expect(order).toEqual([
    'GET /ai-settings/materiality',
    'GET /ai-settings/materiality/12/prompt-model',
    'POST /ai-settings/materiality',
    'GET /ai-settings/materiality/13/prompt-model',
  ]);
  expect(settings.keys().some((one) => /materiality\/\d+$/.test(one))).toBe(
    false,
  );
  expect(unrouted).toEqual([]);
});
