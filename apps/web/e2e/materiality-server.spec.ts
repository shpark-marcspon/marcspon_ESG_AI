// 중대성평가 시연 길을 빌드 결과에서(밴드 IRW1 ③ — 발주서 §3-③ 12). 서버는 e2e/materiality-server.ts 의 흉내(page.route), 컨테이너 0.
//   메뉴 → IR-01 → [진행 보기] → IR-03 진행 → 끝남 → [결과 보기] → IR-04 탭 셋 → [내려받기] 모달의 결과 엑셀·리서치 엑셀(밴드 IRW16) ·
//   failed 줄 [다시 실행] → POST /runs 의 options 가 그 실행 그대로·Idempotency-Key·launchKey → 새 IR-03 · failed 줄 누름은 그 실행의 IR-03(POST 0) ·
//   운영 관리자(인사말 · 「내가 돌린 것만」 0 · 꺼진 메뉴 하나) · 빈 목록 → /materiality 그대로 IR-00 몸(밴드 IRW2 ③ Q9).
// IRW2 ③(발주서 §2-4 e2e): 메뉴 → 빈 목록 IR-00 → [시작하기] → IR-02 입력 → 붙여 넣기(TSV) → 표 → 밸류체인 빔 오류 → 고름 → [평가 시작]
//   → POST /runs 의 options.input 깊은 같음·Idempotency-Key → IR-03 · 올리기(버퍼) ok·bad_header · 운영 관리자 · 목록 [평가 안내]·[새 평가] · N1 굵기 ·
//   N2 1440 폭 카드 안 가로 스크롤 0.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { IR_TEXT } from '../src/entities/materiality/config/text.ts';
import {
  REPORT,
  RESEARCH,
  VALUE_CHAIN_OK,
  fakeMaterialityApi,
  inputOf,
} from './materiality-server.ts';
import { signIn } from './session.ts';

const list = IR_TEXT.list;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

test('메뉴 → IR-01 → [진행 보기] → IR-03 끝남 → [결과 보기] → IR-04 탭 셋 → 엑셀 둘', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.seed(5, 'processing');
  await signIn(page);
  await page.goto('/dataverify');
  const nav = page.getByRole('navigation', { name: IR_TEXT.shell.menuLabel });
  await nav
    .getByRole('button', { name: IR_TEXT.shell.menu.materiality })
    .click();
  await expect(page).toHaveURL(/\/materiality$/);
  await expect(page.getByRole('heading', { name: list.title })).toBeVisible();
  await expect(nav.locator('[aria-current="page"]')).toHaveText(
    IR_TEXT.shell.menu.materiality,
  );
  await expect(nav.locator('[aria-disabled="true"]')).toHaveCount(1);
  await expect(
    page.getByText(list.processing('컨트로버시 리서치')),
  ).toBeVisible();

  await page.getByRole('button', { name: list.next.progress }).click();
  await expect(page).toHaveURL(/\/materiality\/runs\/5$/);
  await expect(
    page.getByText(IR_TEXT.status.doneTitle, { exact: true }),
  ).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: IR_TEXT.common.viewResult }).click();
  await expect(page).toHaveURL(/\/materiality\/runs\/5\/result$/);
  await expect(
    page.getByRole('heading', { name: IR_TEXT.titleOf('가상건설') }),
  ).toBeVisible();
  for (const tab of [
    IR_TEXT.result.tabs.shortlist,
    IR_TEXT.result.tabs.pathway,
    IR_TEXT.result.tabs.impact,
  ]) {
    await page.getByRole('tab', { name: tab }).click();
    await expect(page.getByRole('tab', { name: tab })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  }
  await expect(page.locator('tr[data-row="impact"]')).toHaveCount(2);

  // 받기는 머리 [내려받기] 하나 → 공용 받기 모달 줄 둘(밴드 IRW16 — 화면 안 결과 엑셀 카드·1-1 리서치 단추 0).
  await expect(page.locator('[data-card="report"]')).toHaveCount(0);
  await page.getByTestId('downloads').click();
  const dialog = page.getByTestId('download-dialog');
  await expect(dialog).toBeVisible();
  const download = page.waitForEvent('download');
  await dialog.getByTestId('download-dialog-file-report').click();
  expect((await download).suggestedFilename()).toBe(REPORT);
  const research = page.waitForEvent('download');
  await dialog.getByTestId('download-dialog-file-research').click();
  expect((await research).suggestedFilename()).toBe(RESEARCH);
  await dialog
    .getByRole('button', { name: IR_TEXT.result.downloads.close })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('downloads')).toBeFocused();
  expect(api.posts()).toHaveLength(0);
});

test('꼴(밴드 IRW1b): 목록 머리 한 줄·산업만 줄바꿈 · 결과 표 머리 500 바탕·몸 400 · 숫자 display-03 · 1-1 칩 툴팁 주소 풀림(href 원래)', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.seed(3, 'done');
  await signIn(page);
  await page.goto('/materiality');
  await expect(page.getByRole('heading', { name: list.title })).toBeVisible();
  const style = (selector: string, prop: string) =>
    page
      .locator(selector)
      .first()
      .evaluate(
        (node, name) => getComputedStyle(node).getPropertyValue(name),
        prop,
      );
  expect(await style('thead th', 'white-space')).toBe('nowrap');
  expect(await style('tbody td', 'white-space')).toBe('nowrap');
  expect(await style('[data-testid="industry"]', 'white-space')).toBe('normal');

  await page.goto('/materiality/runs/3/result');
  await expect(page.locator('tr[data-row="impact"]').first()).toBeVisible();
  expect(await style('[data-card="impact"] thead th', 'font-weight')).toBe(
    '500',
  );
  expect(
    await style('[data-card="impact"] thead th', 'background-color'),
  ).not.toBe('rgba(0, 0, 0, 0)');
  expect(await style('tr[data-row="impact"] td', 'font-weight')).toBe('400');
  expect(await style('tr[data-row="impact"] td', 'padding-left')).toBe('16px');
  // 수는 display-03(1440 넘어 32 · 이 창 1400 은 28 — 토큰 단계, 데이터 검증 DV3 와 같음). 전 꼴 display-04 는 24
  expect(['28px', '32px']).toContain(
    await style('[data-testid="stat-impact"]', 'font-size'),
  );

  await page.getByRole('tab', { name: IR_TEXT.result.tabs.shortlist }).click();
  const link = page.locator('[data-card="shortlist"] a').first();
  await expect(link).toBeVisible();
  expect(await link.getAttribute('href')).toContain('%');
  // 밴드 IRW12: 공통 링크 칩 — 풀린 주소는 툴팁, 보이는 글은 도메인·제목(주소 0)
  expect(await link.textContent()).not.toContain('%');
  expect(await link.textContent()).not.toContain('https://');
  expect(decodeURI((await link.getAttribute('href'))!)).toBe(
    await link.getAttribute('title'),
  );
  expect(await link.getAttribute('aria-label')).toMatch(
    / 규제 · example\.com · 새 탭에서 열려요$/,
  );
});

test('failed 줄: 누름은 그 실행의 IR-03(POST 0) · [다시 실행]은 그 options 그대로 새 실행 → 새 IR-03', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  const options = { input: inputOf('가상중공업') };
  api.seed(7, 'failed', options);
  await signIn(page);
  await page.goto('/materiality');
  await expect(
    page.getByTestId('row-status').getByText(IR_TEXT.badge.failed),
  ).toBeVisible();

  await page.getByRole('cell', { name: '가상중공업' }).click();
  await expect(page).toHaveURL(/\/materiality\/runs\/7$/);
  await expect(page.getByText(IR_TEXT.common.rerunAgain)).toBeVisible();
  expect(api.posts()).toHaveLength(0);

  await page
    .getByRole('button', { name: IR_TEXT.common.toList })
    .first()
    .click();
  await expect(page).toHaveURL(/\/materiality$/);
  await page.getByRole('button', { name: list.next.rerun }).click();
  await expect(page).toHaveURL(/\/materiality\/runs\/30$/);
  const [post] = api.posts();
  const body = post!.body as Record<string, unknown>;
  expect(Object.keys(body).sort()).toEqual(['launchKey', 'module', 'options']);
  expect(body.module).toBe('materiality');
  expect(body.options).toEqual(options);
  expect(body).not.toHaveProperty('resumeFromRunId');
  expect(post!.idempotencyKey).toMatch(UUID);
  expect(body.launchKey).toMatch(UUID);
  expect(api.posts()).toHaveLength(1);
});

test('운영 관리자: 인사말 · meta · 「내가 돌린 것만」 0 · 꺼진 메뉴 하나', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.seed(3, 'done');
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await page.goto('/materiality');
  await expect(page.getByText(IR_TEXT.shell.adminGreeting)).toBeVisible();
  await expect(page.locator('tbody [data-run-id]')).toHaveCount(1);
  // 머리 셈·안내 줄은 없다(sid:MARC-ENT-625)
  await expect(page.getByText('계정이 돌린 평가')).toHaveCount(0);
  await expect(page.getByText('내가 돌린', { exact: false })).toHaveCount(0);
  const nav = page.getByRole('navigation', { name: IR_TEXT.shell.menuLabel });
  await expect(nav.locator('[aria-disabled="true"]')).toHaveCount(1);
  await page.getByRole('button', { name: list.next.result }).click();
  await expect(page).toHaveURL(/\/materiality\/runs\/3\/result$/);
});

test('빈 목록: /materiality 그대로 IR-00 몸(IRW2 Q9 — IR-01 빈 꼴 아님)', async ({
  page,
}) => {
  await fakeMaterialityApi(page);
  await signIn(page);
  await page.goto('/materiality');
  await expect(page.locator('[data-screen="materiality-intro"]')).toBeVisible();
  await expect(page).toHaveURL(/\/materiality$/);
  await expect(page.getByText(list.empty)).toHaveCount(0);
  await expect(page.getByRole('heading', { name: list.title })).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: IR_TEXT.intro.start }),
  ).toBeVisible();
});

const vc = IR_TEXT.newRun.valueChain;
const topics = IR_TEXT.newRun.topics;
const TSV = [
  vc.columns.join('\t'),
  '가상 부문\t가상 시공\t자체운영\t근로자\t안전 관리',
  '\t\t중류\t협력회사\t자재 구매',
].join('\n');

/** IR-02 꼭 칸 넷. */
async function fillRequired(page: Page) {
  const box = (name: string) =>
    page.getByRole('textbox', { name, exact: true });
  await box(IR_TEXT.newRun.company.name).fill('가상물산');
  await box(IR_TEXT.newRun.company.industryName('SASB')).fill('가상 산업');
  await box(topics.nameLabel(1)).fill('가상토픽 A');
  await box(topics.subName('가상토픽 A')).fill('가상 서브');
}

test('메뉴 → 빈 목록 IR-00 → [시작하기] → IR-02 붙여 넣기 → 밸류체인 고름 → [평가 시작] → input@1 그대로 → IR-03', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  await signIn(page);
  await page.goto('/dataverify');
  await page
    .getByRole('navigation', { name: IR_TEXT.shell.menuLabel })
    .getByRole('button', { name: IR_TEXT.shell.menu.materiality })
    .click();
  await expect(page).toHaveURL(/\/materiality$/);
  await page.getByRole('button', { name: IR_TEXT.intro.start }).click();
  await expect(page).toHaveURL(/\/materiality\/new$/);
  await expect(page.locator('[data-screen="materiality-new"]')).toBeVisible();

  await fillRequired(page);
  await page.getByRole('tab', { name: vc.tabPaste }).click();
  await page.getByRole('textbox', { name: vc.pasteLabel }).fill(TSV);
  await expect(page.getByTestId('stage-error')).toHaveText(
    vc.errors.stage([2]),
  );
  await expect(
    page.getByRole('textbox', { name: vc.cell(2, vc.columns[0]!) }),
  ).toHaveValue('가상 부문');
  await page.getByTestId('start').click();
  expect(api.posts()).toHaveLength(0);
  await page
    .getByRole('combobox', { name: vc.cell(2, vc.columns[2]!) })
    .selectOption('upstream');
  await expect(page.getByTestId('stage-error')).toHaveCount(0);
  await page.getByTestId('start').click();

  await expect(page).toHaveURL(/\/materiality\/runs\/30$/);
  await expect(
    page.locator('[data-screen="materiality-status"]'),
  ).toBeVisible();
  const [post] = api.posts();
  const body = post!.body as Record<string, unknown>;
  expect(Object.keys(body).sort()).toEqual(['launchKey', 'module', 'options']);
  expect(body.module).toBe('materiality');
  expect(post!.idempotencyKey).toMatch(UUID);
  expect(body.launchKey).toMatch(UUID);
  expect(body.options).toEqual({
    input: {
      schemaVersion: 'materiality.input@1',
      company: { name: '가상물산' },
      industries: [
        { standard: 'SASB', industryName: '가상 산업', description: '' },
      ],
      topics: [{ topic: '가상토픽 A', description: '' }],
      geoScope: '글로벌(대한민국 · 북미 · EU 우선)',
      userLocation: 'KR',
      mainLanguage: '한국어',
      dateRange: '2024-01-01~오늘까지',
      sector: 'non_financial',
      latestEventMode: false,
      subtopicsByTopic: {
        '가상토픽 A': [{ name: '가상 서브', description: '' }],
      },
      valueChain: [
        {
          business_unit: '가상 부문',
          business_unit_description: '가상 시공',
          value_chain_stage: 'own operations',
          stakeholder: '근로자',
          business_activity: '안전 관리',
        },
        {
          business_unit: '가상 부문',
          business_unit_description: '가상 시공',
          value_chain_stage: 'upstream',
          stakeholder: '협력회사',
          business_activity: '자재 구매',
        },
      ],
    },
  });
  expect(api.reads()).toHaveLength(0);
  expect(api.posts()).toHaveLength(1);
});

test('IR-02 직접 입력(IRW3): 붙여 넣기 가운데 빈 줄은 뗌 → [모두 지우기] → [직접 입력] 두 행 → [평가 시작] → input@1 valueChain 그대로', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  await signIn(page);
  await page.goto('/materiality');
  await page.getByRole('button', { name: IR_TEXT.intro.start }).click();
  await expect(page).toHaveURL(/\/materiality\/new$/);
  await fillRequired(page);

  await page.getByRole('tab', { name: vc.tabPaste }).click();
  await page
    .getByRole('textbox', { name: vc.pasteLabel })
    .fill('가\t나\t업스트림\t라\t마\r\n\r\n가\t나\t자체 운영\t라\t마');
  await expect(page.getByTestId('value-chain-error')).toHaveCount(0);
  await expect(
    page.getByRole('combobox', { name: vc.cell(2, vc.columns[2]!) }),
  ).toHaveValue('own operations');
  await page.getByRole('button', { name: vc.clear }).click();
  await expect(
    page.getByRole('textbox', { name: vc.pasteLabel }),
  ).toBeVisible();

  await page.getByRole('tab', { name: vc.tabManual }).click();
  const cell = (row: number, column: number) =>
    page.getByRole('textbox', {
      name: vc.cell(row, vc.columns[column]!),
      exact: true,
    });
  const rows = [
    ['가상 부문', '가상 시공', 'upstream', '가상 협력사', '가상 구매'],
    ['', '', 'downstream', '가상 고객', '가상 유지보수'],
  ] as const;
  for (const [index, values] of rows.entries()) {
    if (index > 0) await page.getByRole('button', { name: vc.addRow }).click();
    for (const [column, value] of values.entries()) {
      if (column === 2)
        await page
          .getByRole('combobox', { name: vc.cell(index + 1, vc.columns[2]!) })
          .selectOption(value);
      else await cell(index + 1, column).fill(value);
    }
  }
  await page.getByRole('button', { name: vc.addRow }).click();
  await page.getByTestId('start').click();
  await expect(page).toHaveURL(/\/materiality\/runs\/30$/);
  expect(api.posts()).toHaveLength(1);
  const options = api.posts()[0]!.body as {
    options: { input: { valueChain: unknown } };
  };
  expect(options.options.input.valueChain).toEqual([
    {
      business_unit: '가상 부문',
      business_unit_description: '가상 시공',
      value_chain_stage: 'upstream',
      stakeholder: '가상 협력사',
      business_activity: '가상 구매',
    },
    {
      business_unit: '',
      business_unit_description: '',
      value_chain_stage: 'downstream',
      stakeholder: '가상 고객',
      business_activity: '가상 유지보수',
    },
  ]);
  expect(api.reads()).toHaveLength(0);
});

test('IR-02 엑셀 올리기: 맨 바이트 한 번 → 표(못 맞춘 밸류체인 빔) · bad_header → 판 글(서버 message 0)', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.readAs({
    ok: false,
    kind: 'bad_header',
    row: null,
    column: null,
    message: '지어낸-서버-글',
  });
  await signIn(page);
  await page.goto('/materiality/new');
  const file = page.locator('[data-testid="value-chain"] input[type="file"]');
  const buffer = Buffer.from([80, 75, 3, 4, 1, 2, 3]);
  await file.setInputFiles({
    name: '가치사슬.xlsx',
    mimeType:
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer,
  });
  await expect(page.getByText(vc.errors.badHeader)).toBeVisible();
  await expect(page.getByText('지어낸-서버-글')).toHaveCount(0);
  const [first] = api.reads();
  expect(first!.bytes).toBe(buffer.length);
  expect(first!.contentType).toBe(
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  );

  api.readAs(VALUE_CHAIN_OK);
  await file.setInputFiles({
    name: '가치사슬.xlsx',
    mimeType:
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer,
  });
  await expect(page.getByTestId('file-line')).toContainText(vc.fileLine(3, 2));
  const stage = (row: number) =>
    page.getByRole('combobox', { name: vc.cell(row, vc.columns[2]!) });
  await expect(stage(1)).toHaveValue('own operations');
  await expect(stage(2)).toHaveValue('upstream');
  await expect(stage(3)).toHaveValue('');
  await expect(stage(3)).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByTestId('stage-error')).toHaveText(
    vc.errors.stage([3]),
  );
  expect(api.reads()).toHaveLength(2);
  expect(api.posts()).toHaveLength(0);
});

test('운영 관리자: 빈 목록 IR-00 → IR-02 → [평가 시작] → IR-03(replace)', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await page.goto('/materiality');
  await expect(page.getByText(IR_TEXT.shell.adminGreeting)).toBeVisible();
  await page.getByRole('button', { name: IR_TEXT.intro.start }).click();
  await expect(page).toHaveURL(/\/materiality\/new$/);
  await fillRequired(page);
  await page.getByTestId('start').click();
  await expect(page).toHaveURL(/\/materiality\/runs\/30$/);
  expect(api.posts()).toHaveLength(1);
  await page.goBack();
  await expect(page).toHaveURL(/\/materiality$/);
});

test('N2(Q10) 1440 폭: 목록 카드 안 가로 스크롤 0 · 리서치 기간은 두 덩이로 줄바꿈', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  const ranged = {
    input: { ...inputOf('가상중공업'), dateRange: '2024-01-01~2024-12-31' },
  };
  api.seed(3, 'done', ranged);
  api.seed(4, 'processing', ranged);
  api.seed(5, 'failed');
  api.seed(6, 'queued');
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  await page.goto('/materiality');
  await expect(page.getByTestId('row-status')).toHaveCount(4);
  const wrap = page.locator('table').locator('..');
  const [scroll, client] = await wrap.evaluate((node) => [
    node.scrollWidth,
    node.clientWidth,
  ]);
  expect(scroll).toBeLessThanOrEqual(client);
  const period = page
    .getByTestId('period')
    .filter({ hasText: '2024-12-31' })
    .first();
  await expect(period).toHaveText('2024-01-01 ~ 2024-12-31');
  const lines = await period.evaluate(
    (node) =>
      node.getBoundingClientRect().height /
      parseFloat(getComputedStyle(node).lineHeight),
  );
  expect(Math.round(lines)).toBe(2);
});

test('목록 [평가 안내] → IR-00 · [새 평가] → IR-02 · 결과 정의 덧말 없음(IRW11 B2)', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.seed(3, 'done');
  await signIn(page);
  await page.goto('/materiality');
  await page.getByRole('link', { name: list.introLink }).click();
  await expect(page).toHaveURL(/\/materiality\/intro$/);
  await page.goBack();
  await page.getByRole('button', { name: list.newRun }).click();
  await expect(page).toHaveURL(/\/materiality\/new$/);

  await page.goto('/materiality/runs/3/result');
  // 판 r3: 영향 정의 머리의 「AI 가 쓴 글 그대로」 덧말은 지웠다(밴드 IRW11 B2).
  await expect(page.locator('[data-card="impact"] table')).toBeVisible();
  await expect(page.getByText('AI 가 쓴 글 그대로')).toHaveCount(0);
});

test('IRW4 열 폭(공용 DataTable fixed): 1280·1440 짧은 칸 th = meta.width · 1-1 반반 · 2-1 데이터 줄 칸만 위아래 12·위 붙임 · 머리 40 · 1440 목록 스크롤 0 · 흐린 줄 색', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  const ranged = {
    input: { ...inputOf('가상중공업'), dateRange: '2024-01-01~2024-12-31' },
  };
  api.seed(3, 'done', ranged);
  api.seed(4, 'processing', ranged);
  api.seed(5, 'failed');
  api.seed(6, 'queued');
  // 흉내 결과에 「정하지 못함」 서브토픽 하나(2-1 impact not_run)를 브라우저 쪽에서 더한다 — 흉내 서버 0줄.
  await page.addInitScript(() => {
    const original = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const response = await original(input, init);
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (!/\/materiality\/runs\/3\/result$/.test(url)) return response;
      const body = await response.clone().json();
      const sub = structuredClone(body.part2.topics[0].subtopics[0]);
      sub.name = '가상 서브토픽 9';
      sub.impact = { status: 'not_run', message: '지어낸 글' };
      body.part2.topics[1].subtopics.push(sub);
      return new Response(JSON.stringify(body), {
        status: response.status,
        headers: response.headers,
      });
    };
  });
  await signIn(page);
  const ths = (table: string) =>
    page
      .locator(table)
      .first()
      .evaluate((node) =>
        [...node.querySelectorAll('thead th')].map(
          (th) => th.getBoundingClientRect().width,
        ),
      );
  const near = (got: number[], want: (number | null)[]) =>
    want.forEach((width, index) => {
      if (width !== null)
        expect(Math.abs(got[index]! - width)).toBeLessThanOrEqual(1);
    });
  const style = (selector: string, prop: string) =>
    page
      .locator(selector)
      .first()
      .evaluate(
        (node, name) => getComputedStyle(node).getPropertyValue(name),
        prop,
      );
  for (const width of [1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/materiality');
    await expect(page.getByTestId('row-status')).toHaveCount(4);
    near(await ths('table'), [136, 168, 56, 124, 96, 153, 111, 111, 136, 98]);
    if (width === 1440) {
      const [scroll, client] = await page
        .locator('table')
        .locator('..')
        .evaluate((node) => [node.scrollWidth, node.clientWidth]);
      expect(scroll).toBeLessThanOrEqual(client);
    }

    await page.goto('/materiality/runs/3/result');
    await expect(page.locator('tr[data-row="impact"]').first()).toBeVisible();
    near(await ths('[data-card="impact"] table'), [
      56,
      120,
      176,
      240,
      null,
      72,
      null,
    ]);
    expect(
      await page
        .locator('[data-card="impact"] thead tr')
        .evaluate((node) => node.getBoundingClientRect().height),
    ).toBeCloseTo(40, 0);
    expect(await style('tr[data-row="impact"] td', 'padding-top')).toBe('12px');
    expect(await style('tr[data-row="impact"] td', 'vertical-align')).toBe(
      'top',
    );
    expect(
      await page
        .locator('tr[data-row="undecided"] td')
        .evaluateAll((tds) =>
          tds
            .slice(0, 7)
            .map((td) => getComputedStyle(td.firstElementChild ?? td).color),
        ),
    ).toEqual(Array.from({ length: 7 }, () => 'rgb(176, 183, 191)'));
    await page
      .getByRole('tab', { name: IR_TEXT.result.impact.positive(0) })
      .click();
    await expect(page.getByTestId('filtered-empty')).toBeVisible();
    expect(
      await style('[data-card="impact"] tbody td', 'padding-top'),
    ).not.toBe('12px');

    await page
      .getByRole('tab', { name: IR_TEXT.result.tabs.shortlist })
      .click();
    await expect(
      page.locator('tr[data-row="shortlist"]').first(),
    ).toBeVisible();
    const shortlist = await ths('[data-card="shortlist"] table');
    near(shortlist, [50, 108, null, null]);
    expect(Math.abs(shortlist[2]! - shortlist[3]!)).toBeLessThanOrEqual(1);
  }
});

test('IRW5 한국어 칸 낱말 사이에서만 꺾임 · 2-2 공용 표(칸 위아래 12·펼친 줄 선 0·요약 칸 위 0·누름 줄 hover 바탕(IRW13)·꺾쇠 첫 열·처음 화면에 보임·한 번 토글·Enter·Space) · 경고 줄 사이 8 · 목록 1281~1436 카드 안 스크롤', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  const ranged = {
    input: {
      ...inputOf('가상 미래 에너지 솔루션 홀딩스 주식회사'),
      dateRange: '2024-01-01~2024-12-31',
    },
  };
  api.seed(3, 'done', ranged);
  api.seed(4, 'processing', ranged);
  api.seed(5, 'failed');
  api.seed(6, 'queued');
  // 흉내 결과의 2-1·2-2 긴 칸에 지어낸 긴 한국어 글(띄어쓰기 있음) · 2-2 정하지 못함 서브토픽 하나 · 경고 둘 — 흉내 서버 0줄(IRW4 꼴).
  await page.addInitScript(() => {
    const long = [
      '가상 기업의 탄소 배출 감축 목표 달성이 늦어지면 규제 당국의 추가 공시 요구와 과징금 부과 가능성이 커지고 협력사 공급망 전반에서 친환경 원자재 조달 비용이 늘어나 중장기 영업이익률이 낮아질 수 있음',
      '국내외 배출권 거래 제도의 할당 기준이 강화되면서 유상 할당 비율이 높아지고 설비 교체 투자와 에너지 효율 개선 사업의 집행 시점이 앞당겨져 단기 현금 흐름 부담이 커질 수 있음',
      '주요 고객사가 공급망 실사 결과를 거래 조건으로 요구하기 시작하여 인증 취득 비용과 내부 관리 체계 정비에 드는 인력과 시간이 늘어나고 수주 경쟁력에도 영향을 줄 수 있음',
      '기후 관련 재무 정보 공시 의무화로 시나리오 분석과 내부 탄소 가격 도입이 필요해지고 이를 반영한 자산 손상 검토 결과가 재무제표 수치와 투자자 평가에 직접 반영될 수 있음',
    ];
    const original = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const response = await original(input, init);
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (!/\/materiality\/runs\/3\/result$/.test(url)) return response;
      const body = await response.clone().json();
      for (const topic of body.part2.topics)
        for (const sub of topic.subtopics) {
          sub.impact.rows[0].impactDefinition = long[0];
          const row = sub.pathway.rows[0];
          row.impactDefinition = long[0];
          row.impactDriver = long[1];
          row.businessImpact = long[2];
          row.financialImpact = long[3];
        }
      const sub = structuredClone(body.part2.topics[0].subtopics[0]);
      sub.name = '가상 서브토픽 9';
      sub.pathway = {
        status: 'failed',
        raw: null,
        parseError: null,
        failure: { kind: 'provider_error', message: '지어낸 글' },
      };
      body.part2.topics[1].subtopics.push(sub);
      body.warnings = [
        {
          code: 'item_date_unreadable',
          message: '지어낸 글',
          topic: body.part2.topics[0].topic,
          phase: 'regulation',
          subtopic: null,
        },
        {
          code: 'items_out_of_range',
          message: '지어낸 글',
          topic: body.part2.topics[1].topic,
          phase: 'controversy',
          subtopic: null,
        },
      ];
      return new Response(JSON.stringify(body), {
        status: response.status,
        headers: response.headers,
      });
    };
  });
  await signIn(page);
  /** 낱말 중간 줄바꿈 수: 글 마디를 띄어쓰기로 나눠 낱말 Range 의 줄(top)이 둘 이상이면 하나로 센다. 칸 word-break 도 함께. */
  const breaks = (selector: string) =>
    page.locator(selector).evaluateAll((nodes) => {
      const words: string[] = [];
      const wordBreak = new Set<string>();
      for (const node of nodes) {
        wordBreak.add(getComputedStyle(node).wordBreak);
        const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
        for (let text = walker.nextNode(); text; text = walker.nextNode()) {
          const value = text.textContent ?? '';
          const word = /\S+/g;
          for (let at = word.exec(value); at; at = word.exec(value)) {
            const range = document.createRange();
            range.setStart(text, at.index);
            range.setEnd(text, at.index + at[0].length);
            const tops = new Set(
              [...range.getClientRects()]
                .filter((rect) => rect.width > 0)
                .map((rect) => Math.round(rect.top)),
            );
            if (tops.size > 1) words.push(at[0]);
          }
        }
      }
      return { words, wordBreak: [...wordBreak] };
    });
  const style = (selector: string, prop: string) =>
    page
      .locator(selector)
      .first()
      .evaluate(
        (node, name) => getComputedStyle(node).getPropertyValue(name),
        prop,
      );
  const keepAll = { words: [], wordBreak: ['keep-all'] };
  const company = 'tbody td [data-run-id] > span';

  for (const width of [1400, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/materiality/runs/3/result');
    await expect(page.locator('tr[data-row="impact"]').first()).toBeVisible();
    // ④ 경고 둘은 한 묶음, 사이 8
    const warnings = page.getByTestId('warning');
    await expect(warnings).toHaveCount(2);
    const gap = await warnings.evaluateAll(
      (nodes) =>
        nodes[1]!.getBoundingClientRect().top -
        nodes[0]!.getBoundingClientRect().bottom,
    );
    expect(Math.abs(gap - 8)).toBeLessThanOrEqual(1);
    // ① 2-1
    expect(await breaks('[data-card="impact"] tbody td')).toEqual(keepAll);

    await page.getByRole('tab', { name: IR_TEXT.result.tabs.pathway }).click();
    const card = '[data-card="pathway"]';
    const lines = page.locator(`${card} tr[data-row="pathway"]`);
    await expect(lines.first()).toBeVisible();
    // ① 2-2
    expect(await breaks(`${card} tbody td`)).toEqual(keepAll);
    // ② 데이터 줄 칸
    expect(
      await style(`${card} tr[data-row="pathway"] td`, 'padding-top'),
    ).toBe('12px');
    expect(
      await style(`${card} tr[data-row="pathway"] td`, 'vertical-align'),
    ).toBe('top');
    // ③ hover 바탕(IRW13 규칙 2): 누름 줄은 hover 전 투명 → hover 때 바탕(붙은 고치기 칸도 같은 바탕 — 끊김 0) · 정하지 못함 줄은 hover 해도 투명
    const paint = (tr: HTMLElement | SVGElement) => [
      getComputedStyle(tr).backgroundColor,
      getComputedStyle(tr.querySelector('td:last-child')!).backgroundColor,
    ];
    await page.mouse.move(0, 0);
    expect((await lines.nth(1).evaluate(paint))[0]).toBe('rgba(0, 0, 0, 0)');
    await lines.nth(1).hover();
    const [hoverRow, hoverEdit] = await lines.nth(1).evaluate(paint);
    expect(hoverRow).not.toBe('rgba(0, 0, 0, 0)');
    expect(hoverEdit).toBe(hoverRow);
    const undecided = page.locator(`${card} tr[data-row="undecided"]`);
    await undecided.hover();
    expect(
      await undecided.evaluate((tr) => getComputedStyle(tr).backgroundColor),
    ).toBe('rgba(0, 0, 0, 0)');
    // ⑥ 꺾쇠(IRW13 규칙 5): 누르면 한 번만 열림(장식 — 줄 누름 하나) · 열림 180° 돌림 · 다시 누르면 닫힘. 정하지 못함 줄 꺾쇠 0.
    await expect(undecided.locator('[data-expand-mark]')).toHaveCount(0);
    const chevron = lines.nth(1).locator('[data-expand-mark] svg');
    // 개정 2: 꺾쇠는 첫 열(No 앞) — 가로 스크롤 0 인 처음 화면에서 보이고, 꺾쇠 칸이 줄의 첫 칸
    expect(
      await lines
        .nth(1)
        .evaluate((tr) => [
          tr.querySelector('td')!.querySelector('[data-expand-mark]') !== null,
          tr.closest('table')!.parentElement!.scrollLeft,
        ]),
    ).toEqual([true, 0]);
    await expect(chevron).toBeInViewport({ ratio: 1 });
    expect(
      await chevron.evaluate((svg) => {
        const box = svg.getBoundingClientRect();
        const wrap = svg
          .closest('table')!
          .parentElement!.getBoundingClientRect();
        return box.left >= wrap.left && box.right <= wrap.right;
      }),
    ).toBe(true);
    const turn = () =>
      chevron.evaluate((svg) => getComputedStyle(svg).transform);
    expect(await turn()).toBe('none');
    await chevron.click();
    await expect(lines.nth(1)).toHaveAttribute('aria-expanded', 'true');
    await expect(
      page.locator(`${card} tr[data-row="pathway-summary"][data-no="2"]`),
    ).toHaveCount(1);
    await expect.poll(turn).toBe('matrix(-1, 0, 0, -1, 0, 0)');
    // 펼친 줄 hover 바탕이 요약 줄까지 한 덩이(마우스는 꺾쇠 위 = 그 줄 위)
    expect(
      await page
        .locator(`${card} tr[data-row="pathway-summary"][data-no="2"] td`)
        .evaluate((td) => getComputedStyle(td).backgroundColor),
    ).toBe(hoverRow);
    // 꺾쇠 칸 폭 40
    expect(
      await lines
        .nth(1)
        .locator('td:has(> [data-expand-mark])')
        .evaluate((td) => td.getBoundingClientRect().width),
    ).toBe(40);
    await chevron.click();
    await expect(lines.nth(1)).toHaveAttribute('aria-expanded', 'false');
    await expect(
      page.locator(`${card} tr[data-row="pathway-summary"]`),
    ).toHaveCount(0);
    // ② 누름 → 펼침: 펼친 줄 아래 선 0 · 요약 칸 위 0·아래 12 · Enter 닫힘 · Space 열림
    await lines.first().click();
    await expect(lines.first()).toHaveAttribute('aria-expanded', 'true');
    expect(
      await style(`${card} tr[data-row="pathway"] td`, 'border-bottom-width'),
    ).toBe('0px');
    const summary = `${card} tr[data-row="pathway-summary"] td`;
    expect(await style(summary, 'padding-top')).toBe('0px');
    expect(await style(summary, 'padding-bottom')).toBe('12px');
    expect(await breaks(summary)).toEqual(keepAll);
    await lines.first().press('Enter');
    await expect(lines.first()).toHaveAttribute('aria-expanded', 'false');
    await expect(page.locator(summary)).toHaveCount(0);
    expect(
      await style(`${card} tr[data-row="pathway"] td`, 'border-bottom-width'),
    ).toBe('1px');
    await lines.nth(1).press('Space');
    await expect(lines.nth(1)).toHaveAttribute('aria-expanded', 'true');
    await expect(
      page.locator(`${card} tr[data-row="pathway-summary"][data-no="2"]`),
    ).toHaveCount(1);
  }

  // ⑤ 목록: 1281~1436 은 표 합 1189 > 카드 안 — 감싸개(카드 안) 가로 스크롤, 쪽은 넘치지 않음, 끝까지 밀면 끝 열이 감싸개 안. 1440 은 IRW4 N5(스크롤 0).
  for (const width of [1281, 1366, 1400, 1436, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/materiality');
    await expect(page.getByTestId('row-status')).toHaveCount(4);
    // ① 목록 회사
    expect(await breaks(company)).toEqual(keepAll);
    if (width === 1440) continue;
    const wrap = page.locator('table').first().locator('..');
    const before = await wrap.evaluate((node) => ({
      overflowX: getComputedStyle(node).overflowX,
      scroll: node.scrollWidth,
      client: node.clientWidth,
      page: document.documentElement.scrollWidth,
      inner: window.innerWidth,
    }));
    expect(before.overflowX).toBe('auto');
    expect(before.scroll).toBeGreaterThan(before.client);
    expect(before.page).toBeLessThanOrEqual(before.inner);
    const ends = await wrap.evaluate((node) => {
      node.scrollLeft = node.scrollWidth;
      const ths = node.querySelectorAll('thead th');
      return {
        wrap: node.getBoundingClientRect().right,
        th: ths[ths.length - 1]!.getBoundingClientRect().right,
        next: [...node.querySelectorAll('[data-next]')].map(
          (button) => button.getBoundingClientRect().right,
        ),
      };
    });
    expect(ends.next.length).toBeGreaterThan(0);
    for (const right of [ends.th, ...ends.next])
      expect(right).toBeLessThanOrEqual(ends.wrap + 1);
  }
});

test('IRW6 IR-03 진행 수: 진행 중 줄 끝·머리에 「1 / 2토픽」 · 끝난 줄 수 0', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.seed(4, 'processing');
  // 흉내 서버는 읽기마다 상태가 넘어가므로 GET /runs/4 를 브라우저 쪽에서 늘 같은 진행으로 덧씌운다 — 흉내 서버 0줄.
  await page.addInitScript(() => {
    const original = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const response = await original(input, init);
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (!/\/runs\/4$/.test(url)) return response;
      const body = await response.clone().json();
      const at: Record<string, [string, number | null, number | null]> = {
        load: ['done', null, null],
        regulation: ['done', 2, 2],
        keywords: ['done', null, null],
        controversy: ['running', 1, 2],
      };
      body.status = 'processing';
      body.finishedAt = null;
      body.steps = body.steps.map((step: { step: string }) => {
        const [status, done, total] = at[step.step] ?? ['pending', null, null];
        return { ...step, status, done, total };
      });
      return new Response(JSON.stringify(body), {
        status: response.status,
        headers: response.headers,
      });
    };
  });
  await signIn(page);
  await page.goto('/materiality/runs/4');
  const words = IR_TEXT.status;
  const controversy = page.locator('[data-line="controversy"]');
  await expect(controversy).toHaveAttribute('data-state', 'running');
  await expect(controversy.getByTestId('line-count')).toHaveText('1 / 2토픽');
  await expect(controversy).toContainText(
    `${words.lines.controversy.text} · 1 / 2토픽`,
  );
  await expect(page.getByTestId('progress-now')).toHaveText(
    `${words.lines.controversy.name} 1 / 2토픽`,
  );
  await expect(
    page.locator('[data-line="regulation"] [data-testid="line-count"]'),
  ).toHaveCount(0);
  await expect(page.getByTestId('line-count')).toHaveCount(1);
});

test('IRW6 꼴: IR-02 파일 줄(공용 목록 28·테두리 0·이름 16) · 가치사슬 th 바탕·위아래 1px = 결과 표 th · 2-2 토픽·서브토픽 th 100', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.seed(3, 'done');
  api.readAs(VALUE_CHAIN_OK);
  await signIn(page);
  const look = (selector: string) =>
    page
      .locator(selector)
      .first()
      .evaluate((node) => {
        const s = getComputedStyle(node);
        return {
          background: s.backgroundColor,
          top: `${s.borderTopWidth} ${s.borderTopStyle} ${s.borderTopColor}`,
          bottom: `${s.borderBottomWidth} ${s.borderBottomStyle} ${s.borderBottomColor}`,
        };
      });
  for (const width of [1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/materiality/runs/3/result');
    await expect(page.locator('tr[data-row="impact"]').first()).toBeVisible();
    const resultHead = await look('[data-card="impact"] thead th');
    await page.getByRole('tab', { name: IR_TEXT.result.tabs.pathway }).click();
    await expect(page.locator('tr[data-row="pathway"]').first()).toBeVisible();
    const [topic, subtopic] = await page
      .locator('[data-card="pathway"] table')
      .first()
      .evaluate((node) =>
        // 첫 머리는 꺾쇠 열(IRW13 개정 2) — 토픽·서브토픽은 셋째·넷째
        [...node.querySelectorAll('thead th')]
          .slice(2, 4)
          .map((th) => th.getBoundingClientRect().width),
      );
    for (const got of [topic!, subtopic!]) {
      expect(got).toBeGreaterThanOrEqual(99);
      expect(Math.abs(got - 100)).toBeLessThanOrEqual(1);
    }

    await page.goto('/materiality/new');
    await page
      .locator('[data-testid="value-chain"] input[type="file"]')
      .setInputFiles({
        name: '가치사슬.xlsx',
        mimeType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        buffer: Buffer.from([80, 75, 3, 4, 1, 2, 3]),
      });
    const line = page.getByTestId('file-line').locator('li');
    await expect(line).toHaveCount(1);
    const row = await line.evaluate((li) => ({
      height: li.getBoundingClientRect().height,
      border: getComputedStyle(li).borderTopWidth,
      name: getComputedStyle(li.querySelector('span')!).fontSize,
    }));
    expect(Math.abs(row.height - 28)).toBeLessThanOrEqual(1);
    expect(row.border).toBe('0px');
    expect(row.name).toBe('16px');
    const vcHead = await look('[data-testid="value-chain-table"] thead th');
    expect(vcHead.background).toBe('rgb(250, 251, 251)');
    expect(vcHead.top).toMatch(/^1px solid /);
    expect(vcHead.bottom).toMatch(/^1px solid /);
    expect(vcHead).toEqual(resultHead);
  }
});

test('IRW11 글 칸 고치기: 2-1 고침·저장 → 연필·배지 · 1-1 제목 고침 → 머리 엑셀은 고친 판 경로 · 2-2 [고치기] 뒤 첫 칸이 스크롤 칸 안 · 바꾼 채 탭 → 창', async ({
  page,
}) => {
  const edit = IR_TEXT.result.edit;
  const api = await fakeMaterialityApi(page);
  api.seed(3, 'done');
  await signIn(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/materiality/runs/3/result');

  await page.locator('[data-edit-button="impact-1"]').click();
  const definition = page.getByRole('textbox', { name: edit.definition });
  await expect(definition).toBeFocused();
  await expect(page.locator('[data-edit-button]')).toHaveCount(0);
  await definition.fill('e2e 가상 정의 고침');
  await page.getByRole('button', { name: edit.save }).click();
  await expect(page.getByRole('textbox')).toHaveCount(0);
  const row = page.locator('tr[data-row="impact"]').first();
  await expect(row).toContainText('e2e 가상 정의 고침');
  await expect(row.getByTestId('edited-mark')).toHaveAttribute(
    'aria-label',
    edit.editedLabel('담당자 A', '11-03 14:28'),
  );
  await expect(page.getByTestId('edited-badge')).toHaveText(
    edit.badge(1, '14:28'),
  );
  const saves = api.calls.filter(
    (call) =>
      call.method === 'POST' &&
      call.path === '/materiality/runs/3/result/edits',
  );
  expect(saves.map((call) => call.body)).toEqual([
    {
      baseRevision: 0,
      changes: [
        {
          pointer: '/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition',
          value: 'e2e 가상 정의 고침',
        },
      ],
    },
  ]);

  await page.getByRole('tab', { name: IR_TEXT.result.tabs.shortlist }).click();
  await page.locator('[data-edit-button="shortlist-1"]').click();
  await page
    .getByRole('textbox', { name: edit.title })
    .first()
    .fill('e2e 가상 제목 고침');
  await page.getByRole('button', { name: edit.save }).click();
  await expect(page.getByRole('textbox')).toHaveCount(0);
  await expect(page.locator('tr[data-row="shortlist"]').first()).toContainText(
    'e2e 가상 제목 고침',
  );
  await page.getByTestId('downloads').click();
  const download = page.waitForEvent('download');
  await page
    .getByTestId('download-dialog')
    .getByTestId('download-dialog-file-report')
    .click();
  expect((await download).suggestedFilename()).toBe(REPORT);
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('download-dialog')).toHaveCount(0);
  expect(
    api.calls.some(
      (call) =>
        call.method === 'GET' && call.path === '/materiality/runs/3/report',
    ),
  ).toBe(true);
  expect(
    api.calls.some((call) => call.path === `/runs/3/files/${REPORT}`),
  ).toBe(false);

  await page.getByRole('tab', { name: IR_TEXT.result.tabs.pathway }).click();
  await page.locator('[data-edit-button="pathway-1"]').click();
  const first = page.getByRole('textbox', { name: edit.definition });
  await expect(first).toBeFocused();
  const [box, wrap] = await Promise.all([
    first.boundingBox(),
    page.locator('[data-card="pathway"] table').locator('..').boundingBox(),
  ]);
  expect(box!.x).toBeGreaterThanOrEqual(wrap!.x - 1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(wrap!.x + wrap!.width + 1);
  await expect(page.locator('tr[data-row="pathway-edit"]')).toHaveCount(1);
  await first.fill('e2e 가상 경로 고침');
  await page.getByRole('tab', { name: IR_TEXT.result.tabs.impact }).click();
  await expect(page.getByTestId('leave-dialog')).toBeVisible();
  await expect(page.getByTestId('leave-dialog')).toContainText(edit.leaveTitle);
  await page.getByRole('button', { name: edit.leaveGo }).click();
  await expect(
    page.getByRole('tab', { name: IR_TEXT.result.tabs.impact }),
  ).toHaveAttribute('aria-selected', 'true');
});

test('IRW11b B1 나가기 창: 결과 탭·유형 탭에서 [계속 고치기]·Esc → 창 0 · 편집 줄·쓴 글·탭 그대로(창이 다시 뜨지 않음)', async ({
  page,
}) => {
  const edit = IR_TEXT.result.edit;
  const tabs = IR_TEXT.result.tabs;
  const api = await fakeMaterialityApi(page);
  api.seed(3, 'done');
  await signIn(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/materiality/runs/3/result');
  await page.locator('[data-edit-button="impact-1"]').click();
  const definition = page.getByRole('textbox', { name: edit.definition });
  await definition.fill('e2e 가상 정의 고침');
  const dialog = page.getByTestId('leave-dialog');
  const stays = async () => {
    // 창이 닫힌 뒤 다시 뜨지 않는지 잠깐 지켜본다(재현 때 remove→add 가 곧바로 일어남).
    await expect(dialog).toHaveCount(0);
    await page.waitForTimeout(300);
    await expect(dialog).toHaveCount(0);
    await expect(definition).toHaveValue('e2e 가상 정의 고침');
    await expect(page.locator('tr[data-editing]')).toHaveCount(1);
    await expect(page.getByRole('tab', { name: tabs.impact })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  };
  // 결과 탭 → [계속 고치기]
  await page.getByRole('tab', { name: tabs.shortlist }).click();
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: edit.leaveStay }).click();
  await stays();
  // 결과 탭 → Esc
  await page.getByRole('tab', { name: tabs.pathway }).click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Escape');
  await stays();
  // 유형 탭 → [계속 고치기]
  const kind = page.getByRole('tab', {
    name: IR_TEXT.result.impact.positive(0),
  });
  await kind.click();
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: edit.leaveStay }).click();
  await stays();
  await expect(
    page.getByRole('tab', { name: IR_TEXT.result.impact.all(2) }),
  ).toHaveAttribute('aria-selected', 'true');
  // 유형 탭 → Esc
  await kind.click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Escape');
  await stays();
  await expect(
    page.getByRole('tab', { name: IR_TEXT.result.impact.all(2) }),
  ).toHaveAttribute('aria-selected', 'true');
  // [나가기]는 그대로 편집 버리고 그 이동
  await page.getByRole('tab', { name: tabs.shortlist }).click();
  await dialog.getByRole('button', { name: edit.leaveGo }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('tab', { name: tabs.shortlist })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(page.getByRole('textbox')).toHaveCount(0);
});

test('IRW11b m1 편집 줄 아래 단추 줄: 2-1·1-1 위아래 12(판 .d-rowact) · 2-2 펼침 단추 아래 12', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.seed(3, 'done');
  await signIn(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/materiality/runs/3/result');
  /** 칸 위·아래와 마지막 단추 사이(아래는 접힌 칸 선 0.5~1px 이 칸 안에 들어 12~13). */
  const gaps = (selector: string) =>
    page.locator(selector).evaluate((td) => {
      const cell = td.getBoundingClientRect();
      const last = [...td.querySelectorAll('button')]
        .at(-1)!
        .getBoundingClientRect();
      const style = getComputedStyle(td);
      return {
        top: last.top - cell.top,
        bottom: cell.bottom - last.bottom,
        height: last.height,
        padding: `${style.paddingTop}/${style.paddingBottom}`,
      };
    });
  const rowGaps = async (selector: string) => {
    const found = await gaps(selector);
    expect(found.top).toBeCloseTo(12, 0);
    expect(found.bottom).toBeGreaterThanOrEqual(12);
    expect(found.bottom).toBeLessThanOrEqual(13);
    expect(found.height).toBe(28);
    expect(found.padding).toBe('12px/12px');
  };
  const tabs = IR_TEXT.result.tabs;
  await page.locator('[data-edit-button="impact-1"]').click();
  await rowGaps('tr[data-row="edit-actions"] td');
  await page.getByRole('button', { name: IR_TEXT.result.edit.cancel }).click();
  await page.getByRole('tab', { name: tabs.shortlist }).click();
  await page.locator('[data-edit-button="shortlist-1"]').click();
  await rowGaps('tr[data-row="edit-actions"] td');
  await page.getByRole('button', { name: IR_TEXT.result.edit.cancel }).click();
  await page.getByRole('tab', { name: tabs.pathway }).click();
  await page.locator('[data-edit-button="pathway-1"]').click();
  const pathway = await gaps('tr[data-row="pathway-edit"] td');
  expect(pathway.bottom).toBeGreaterThanOrEqual(12);
  expect(pathway.bottom).toBeLessThanOrEqual(13);
});

test('IRW12b m1 1-1 읽기 칸 줄 사이 6(시안 .l-items) — 고침 표시 없는 칸·있는 칸', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.seed(3, 'done');
  await signIn(page);
  await page.goto('/materiality/runs/3/result');
  await expect(page.locator('tr[data-row="impact"]').first()).toBeVisible();
  // 흉내 서버의 칸은 한 줄뿐이라, 결과 읽기를 덮어 토픽마다 재무 규제 주소를 갈라 1-1 칸을 두 줄로 만든다(지어낸 주소).
  const body = (await page.evaluate(async () =>
    (await fetch('/api/materiality/runs/3/result')).json(),
  )) as {
    part2: {
      topics: {
        subtopics: {
          financial: {
            rows: { context: { regulations: { url: string }[] } }[];
          };
        }[];
      }[];
    };
  };
  for (const topic of body.part2.topics) {
    const regulation =
      topic.subtopics[0]!.financial.rows[0]!.context.regulations[0]!;
    regulation.url = `${regulation.url}-b`;
  }
  await page.route('**/api/materiality/runs/3/result', (route) =>
    route.fulfill({ status: 200, json: body }),
  );
  // 흉내 서버의 고침 길로 토픽 1 규제 제목 하나를 고쳐 그 칸에만 연필을 단다
  const status = await page.evaluate(
    async () =>
      (
        await fetch('/api/materiality/runs/3/result/edits', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            baseRevision: 0,
            changes: [
              {
                pointer:
                  '/part2/topics/0/subtopics/0/impact/rows/0/context/regulations/0/title',
                value: 'e2e 가상 규제 고침',
              },
            ],
          }),
        })
      ).status,
  );
  expect(status).toBe(200);
  await page.reload();
  await page.getByRole('tab', { name: IR_TEXT.result.tabs.shortlist }).click();
  const between = (row: number) =>
    page
      .locator('[data-card="shortlist"] tbody tr')
      .nth(row)
      .locator('td')
      .nth(2)
      .evaluate((td) => {
        const lines = [...td.querySelectorAll('[data-item-label]')].map(
          (line) => line.getBoundingClientRect(),
        );
        return {
          count: lines.length,
          gaps: lines.slice(1).map((box, i) => box.top - lines[i]!.bottom),
          edited: td.querySelector('[data-testid="edited-mark"]') !== null,
          chips: td.querySelectorAll('a').length,
        };
      });
  const plain = await between(1);
  const edited = await between(0);
  console.log(
    `IRW12b m1 사이: 고침 0 ${JSON.stringify(plain)} · 고침 ${JSON.stringify(edited)}`,
  );
  for (const [found, mark] of [
    [plain, false],
    [edited, true],
  ] as const) {
    expect(found.edited).toBe(mark);
    expect(found.count).toBe(2);
    expect(found.chips).toBe(2);
    for (const gap of found.gaps) expect(gap).toBeCloseTo(6, 0);
  }
});

test('IRW15 ① [양식 받기]: 엑셀 올리기 탭 드롭 칸 안 · 누르면 빈 양식 내려받음(머리 다섯 xlsx) · 파일 고르기 창 0', async ({
  page,
}) => {
  await fakeMaterialityApi(page);
  await signIn(page);
  await page.goto('/materiality/new');
  const link = page.getByTestId('value-chain-template');
  await expect(link).toHaveText(vc.template);
  let chooser = 0;
  page.on('filechooser', () => (chooser += 1));
  const download = page.waitForEvent('download');
  await link.click();
  const file = await download;
  expect(file.suggestedFilename()).toBe(vc.templateFile);
  const path = await file.path();
  const { readFile } = await import('node:fs/promises');
  const bytes = await readFile(path);
  expect(bytes.subarray(0, 2).toString('latin1')).toBe('PK');
  await link.focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(200);
  expect(chooser).toBe(0);
  await page.getByRole('tab', { name: vc.tabPaste }).click();
  await expect(page.getByTestId('value-chain-template')).toHaveCount(0);
});

test('IRW15 ④ 떠나기 경고: 빈 폼은 창 0 · 넣으면 메뉴·뒤로·[취소] 때 창 · [계속 입력] 남음 · [나가기] 이동 · 시작 성공 뒤 이동은 창 0', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  await signIn(page);
  const leave = IR_TEXT.newRun.leave;
  const dialog = page.getByTestId('leave-dialog');
  const menu = page
    .getByRole('navigation', { name: IR_TEXT.shell.menuLabel })
    .getByRole('button', { name: IR_TEXT.shell.menu.materiality });

  // 빈 폼: [취소] → 목록, 창 0
  await page.goto('/materiality');
  await page.getByRole('button', { name: IR_TEXT.intro.start }).click();
  await expect(page).toHaveURL(/\/materiality\/new$/);
  await page.getByRole('button', { name: IR_TEXT.newRun.cancel }).click();
  await expect(page).toHaveURL(/\/materiality$/);
  await expect(dialog).toHaveCount(0);

  // 무엇이든 넣으면 [취소] → 창 · [계속 입력] → 남음(넣은 값 그대로)
  await page.getByRole('button', { name: IR_TEXT.intro.start }).click();
  await expect(page).toHaveURL(/\/materiality\/new$/);
  const company = page.getByRole('textbox', {
    name: IR_TEXT.newRun.company.name,
    exact: true,
  });
  await company.fill('가상물산');
  await page.getByRole('button', { name: IR_TEXT.newRun.cancel }).click();
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText(leave.title);
  await expect(dialog).toContainText(leave.body);
  await dialog.getByRole('button', { name: leave.stay }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page).toHaveURL(/\/materiality\/new$/);
  await expect(company).toHaveValue('가상물산');

  // 메뉴 → 창 → [계속 입력]
  await menu.click();
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: leave.stay }).click();
  await expect(page).toHaveURL(/\/materiality\/new$/);

  // 뒤로 → 창 → [나가기] → 목록
  await page.goBack();
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: leave.go }).click();
  await expect(page).toHaveURL(/\/materiality$/);
  await expect(dialog).toHaveCount(0);

  // 넣고 [평가 시작] 성공 → IR-03, 창 0
  await page.getByRole('button', { name: IR_TEXT.intro.start }).click();
  await fillRequired(page);
  await page.getByTestId('start').click();
  await expect(page).toHaveURL(/\/materiality\/runs\/30$/);
  await expect(dialog).toHaveCount(0);
  expect(api.posts()).toHaveLength(1);
});

test('IRW17 떠나기 경고 빈틈: 표로 안 읽히는 붙여 넣기 글만 → 창 · 실패 파일 줄만 → 창 · 아무것도 없음 → 창 0', async ({
  page,
}) => {
  const api = await fakeMaterialityApi(page);
  api.readAs({
    ok: false,
    kind: 'bad_header',
    row: null,
    column: null,
    message: '지어낸-서버-글',
  });
  await signIn(page);
  const leave = IR_TEXT.newRun.leave;
  const dialog = page.getByTestId('leave-dialog');
  const cancel = page.getByRole('button', { name: IR_TEXT.newRun.cancel });

  // 아무것도 없음 → 창 0
  await page.goto('/materiality/new');
  await cancel.click();
  await expect(page).toHaveURL(/\/materiality$/);
  await expect(dialog).toHaveCount(0);

  // 표로 안 읽히는 붙여 넣기 글만 → 창
  await page.goto('/materiality/new');
  await page.getByRole('tab', { name: vc.tabPaste }).click();
  const pasteBox = page.getByRole('textbox', { name: vc.pasteLabel });
  await pasteBox.fill('가상 글 한 줄');
  await expect(pasteBox).toHaveValue('가상 글 한 줄');
  await cancel.click();
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: leave.stay }).click();
  await expect(pasteBox).toHaveValue('가상 글 한 줄');
  await pasteBox.fill('');
  await cancel.click();
  await expect(page).toHaveURL(/\/materiality$/);
  await expect(dialog).toHaveCount(0);

  // 실패 파일 줄만 → 창
  await page.goto('/materiality/new');
  await page
    .locator('[data-testid="value-chain"] input[type="file"]')
    .setInputFiles({
      name: '가치사슬.xlsx',
      mimeType:
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      buffer: Buffer.from([80, 75, 3, 4, 1, 2, 3]),
    });
  await expect(page.getByTestId('file-line-failed')).toBeVisible();
  await cancel.click();
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: leave.go }).click();
  await expect(page).toHaveURL(/\/materiality$/);
  expect(api.posts()).toHaveLength(0);
});
