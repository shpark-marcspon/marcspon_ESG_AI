// 데이터 검증 시연 길을 빌드 결과에서(밴드 DV2a ③ — 발주서 §3-3 12). 서버는 e2e/dataverify-server.ts 의 흉내(page.route).
// 입력 JSON 은 메모리에서 짓는다(디스크에 .json 0 — 「가상건설」 꼴, 실재 기업명 0).
//   메뉴 → DV-00 → [시작하기] → JSON 파일 + 기업 칸 → [검증 시작] → POST /runs 본문 열쇠(launchKey·module·options{input})·Idempotency-Key →
//   진행 → 끝남 → [결과 보기] → 결과 표 → 머리 [내려받기] → 받기 모달 결과 엑셀 줄(DV15) · 붙여 넣기로 두 번(성공 뒤 새 검증은 새 열쇠 — P16) ·
//   운영 관리자 한 번(인사말 · 꺼진 메뉴 하나).
//   DV2b: 본문 options.source(파일 = 고른 이름 · 붙여 넣기 = {kind:'paste'}) · 목록(파일명 줄 · 「붙여 넣은 데이터 · 시각」 줄) → [결과 보기] ·
//   빈 목록 → DV-00 · 운영 관리자 목록에 「내가 올린 것만」 0.
//   DVX1 ②: .xlsx(버퍼 — 내용은 흉내가 무시) → 서버 읽기 → 미리 읽기·마지막 연도 → [검증 시작] 본문 data = 흉내 답 · bad_header 글 한 번 ·
//   [엑셀 양식 내려받기] 이름.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DV_TEXT } from '../src/entities/dataverify/config/text.ts';
import { EDK_OK, edkRejected, fakeDataverifyApi } from './dataverify-server.ts';
import { signIn } from './session.ts';

const words = DV_TEXT.newCheck;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const item = (extra: Record<string, unknown>) => ({
  ID: 'E-001',
  테마: '환경',
  항목: '기후변화',
  대분류: '온실가스 배출량',
  중분류: '직접 배출량',
  소분류: 'Scope 1',
  '입력 방식': '직접 입력',
  단위: 'tCO2eq',
  values: { '2023': 1200, '2024': 1300 },
  핵심데이터: 'Y',
  메모: '',
  ...extra,
});
const DATA = {
  환경: [item({}), item({ ID: 'E-002', 소분류: 'Scope 2', 핵심데이터: 'N' })],
  사회: [item({ ID: 'S-001', 테마: '사회' })],
};
const JSON_TEXT = JSON.stringify(DATA);

async function fillCompany(page: Page) {
  await page.getByLabel(words.name).fill('가상건설');
  await page.getByLabel(words.sasb).fill('Engineering & Construction Services');
  const topic = page.getByRole('textbox', { name: words.topicAdd });
  await topic.fill('기후변화 대응');
  await topic.press('Enter');
}

async function paste(page: Page) {
  await page.getByRole('tab', { name: words.tabPaste }).click();
  await page.getByRole('textbox', { name: words.pasteLabel }).fill(JSON_TEXT);
  await expect(page.getByTestId('preview')).toBeVisible();
}

test('메뉴 → DV-00 → DV-02 파일 → [검증 시작] → DV-03 진행·끝남 → DV-04 결과 표 → 엑셀', async ({
  page,
}) => {
  const api = await fakeDataverifyApi(page);
  await signIn(page);
  await page.goto('/translation');
  const nav = page.getByRole('navigation', { name: DV_TEXT.shell.menuLabel });
  await nav
    .getByRole('button', { name: DV_TEXT.shell.menu.validation })
    .click();
  await expect(page).toHaveURL(/\/dataverify$/);
  await page.getByRole('button', { name: DV_TEXT.intro.start }).click();
  await expect(page).toHaveURL(/\/dataverify\/new$/);

  await page.locator('[data-card="data"] input[type="file"]').setInputFiles({
    name: 'edk.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON_TEXT, 'utf8'),
  });
  await expect(page.getByTestId('preview')).toBeVisible();
  await fillCompany(page);
  await page.getByTestId('start').click();

  await expect(page).toHaveURL(/\/dataverify\/runs\/30$/);
  const [post] = api.posts();
  const body = post!.body as {
    module: string;
    options: { input: unknown; source: unknown };
  };
  expect(Object.keys(body).sort()).toEqual(['launchKey', 'module', 'options']);
  expect(body.module).toBe('dataverify');
  expect(Object.keys(body.options)).toEqual(['input', 'source']);
  expect(body.options.source).toEqual({ kind: 'file', name: 'edk.json' });
  expect(body.options.input).toMatchObject({
    schemaVersion: 'dataverify.input@1',
    company: { name: '가상건설', materialTopics: ['기후변화 대응'] },
    data: DATA,
  });
  expect(post!.idempotencyKey).toMatch(UUID);
  // launchKey(DV2d): 소문자 UUID · Idempotency-Key 와 다른 값.
  const { launchKey } = post!.body as { launchKey: unknown };
  expect(launchKey).toMatch(UUID);
  expect(launchKey).not.toBe(post!.idempotencyKey);

  // 폴링이 진행 → 끝남으로(읽기마다 한 걸음).
  await expect(
    page.getByRole('heading', { name: DV_TEXT.status.doneTitle }),
  ).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: DV_TEXT.common.viewResult }).click();
  await expect(page).toHaveURL(/\/dataverify\/runs\/30\/result$/);
  const checks = page.locator('[data-card="checks"]');
  await expect(checks.locator('tr[data-line="1"]')).toHaveCount(2);
  await expect(checks.locator('tr[data-line="2"]')).toContainText(
    DV_TEXT.result.notes.tool,
  );
  await expect(page.getByTestId('stat-checks')).toHaveText(
    DV_TEXT.result.cards.checksValue(3),
  );
  await expect(page.getByText('지어낸 도구 오류')).toHaveCount(0);

  await expect(page.locator('[data-card="file"]')).toHaveCount(0);
  await page.getByTestId('download-head').click();
  await expect(page.getByTestId('download-dialog')).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByTestId('download-dialog-file-report').click();
  expect((await download).suggestedFilename()).toBe('dataverify-report.xlsx');
});

test('붙여 넣기 두 번: 성공 뒤 새 검증의 누름은 새 Idempotency-Key(같은 본문이어도)', async ({
  page,
}) => {
  const api = await fakeDataverifyApi(page);
  await signIn(page);
  await page.goto('/dataverify/new');
  await paste(page);
  await fillCompany(page);
  await page.getByTestId('start').click();
  await expect(page).toHaveURL(/\/dataverify\/runs\/30$/);

  // 같은 틀 안에서(저장소가 살아 있다) [목록으로] → 목록(실행이 하나 있다 — DV2b) [새 검증] → 같은 본문으로 다시.
  await page.getByRole('button', { name: DV_TEXT.common.toList }).click();
  await expect(page).toHaveURL(/\/dataverify$/);
  await page
    .getByRole('button', { name: DV_TEXT.list.newCheck })
    .first()
    .click();
  await paste(page);
  await fillCompany(page);
  await page.getByTestId('start').click();
  await expect(page).toHaveURL(/\/dataverify\/runs\/31$/);

  const keys = api.posts().map((call) => call.idempotencyKey);
  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe(keys[1]);
  // 새 누름 = 새 launchKey(DV2d) — 그 밖 본문은 같다.
  const [first, second] = api.posts().map((call) => {
    const { launchKey, ...rest } = call.body as { launchKey: unknown };
    return { launchKey, rest };
  });
  expect(first!.rest).toEqual(second!.rest);
  expect(first!.launchKey).toMatch(UUID);
  expect(first!.launchKey).not.toBe(second!.launchKey);
  // 붙여 넣은 본문의 출처는 {kind:'paste'} 하나(이름 0 — 주면 서버가 모르는 열쇠로 거절).
  expect(
    (api.posts()[0]!.body as { options: { source: unknown } }).options.source,
  ).toEqual({ kind: 'paste' });
});

test('운영 관리자: 인사말 · DV-00 · 꺼진 메뉴 하나', async ({ page }) => {
  await fakeDataverifyApi(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await page.goto('/dataverify');
  await expect(page.getByText(DV_TEXT.shell.adminGreeting)).toBeVisible();
  await expect(
    page.getByRole('button', { name: DV_TEXT.intro.start }),
  ).toBeVisible();
  const nav = page.getByRole('navigation', { name: DV_TEXT.shell.menuLabel });
  await expect(nav.locator('[aria-current="page"]')).toHaveText(
    DV_TEXT.shell.menu.validation,
  );
  await expect(nav.locator('[aria-disabled="true"]')).toHaveCount(1);
});

const company = {
  name: '가상건설',
  sasbIndustry: 'Engineering & Construction Services',
  materialTopics: ['기후변화 대응'],
  reportingYear: '2025',
};
const inputOf = () => ({
  schemaVersion: 'dataverify.input@1',
  company,
  data: DATA,
});

test('목록: 파일명 줄 · 붙여 넣은 줄 → [결과 보기] → DV-04 머리 = 파일 이름', async ({
  page,
}) => {
  const api = await fakeDataverifyApi(page);
  api.seed(11, {
    input: inputOf(),
    source: { kind: 'file', name: 'EDK_가상데이터_2025.json' },
  });
  api.seed(12, { input: inputOf(), source: { kind: 'paste' } });
  api.seed(13, { input: inputOf() }, 'queued');
  await signIn(page);
  await page.goto('/dataverify');
  const list = DV_TEXT.list;
  await expect(page.getByRole('heading', { name: list.title })).toBeVisible();
  const rows = page.locator('tbody tr');
  await expect(rows).toHaveCount(3);
  // 머리 셈·안내 줄은 없다(sid:MARC-ENT-625)
  await expect(page.getByText('계정이 올린 파일')).toHaveCount(0);
  await expect(page.getByTestId('file-name')).toHaveText([
    DV_TEXT.source.pastedAt('2026-10-19 10:40'),
    'EDK_가상데이터_2025.json',
  ]);
  await expect(rows.nth(0)).toContainText(list.badge.queued);
  await expect(rows.nth(0)).toContainText(list.next.progress);
  await expect(page.getByText('1회차')).toHaveCount(0);
  await rows
    .filter({ hasText: 'EDK_가상데이터_2025.json' })
    .getByRole('button', { name: list.next.result })
    .click();
  await expect(page).toHaveURL(/\/dataverify\/runs\/11\/result$/);
  await expect(
    page.locator('[data-screen="dataverify-result"] h2'),
  ).toContainText('EDK_가상데이터_2025.json');
});

test('빈 목록 → DV-00(주소 그대로) · 운영 관리자 목록은 「내가 올린 것만」 0', async ({
  page,
}) => {
  const api = await fakeDataverifyApi(page);
  await signIn(page);
  await page.goto('/dataverify');
  await expect(
    page.getByRole('button', { name: DV_TEXT.intro.start }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/dataverify$/);
  await expect(
    page.getByRole('heading', { name: DV_TEXT.list.title }),
  ).toHaveCount(0);

  api.seed(11, { input: inputOf(), source: { kind: 'paste' } });
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await page.goto('/dataverify');
  await expect(
    page.getByRole('heading', { name: DV_TEXT.list.title }),
  ).toBeVisible();
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await expect(page.getByTestId('file-name')).toHaveCount(1);
  await expect(page.getByText('계정이 올린 파일')).toHaveCount(0);
  await expect(page.getByText(DV_TEXT.list.mineOnly)).toHaveCount(0);
  await expect(page.getByRole('checkbox')).toHaveCount(0);
});

test('시안 대조 손질(밴드 DV3 ①): DV-04 표·수·단추 · DV-02 보고연도·탭의 계산된 값', async ({
  page,
}) => {
  // 끝난 실행을 심어 DV-04 로 바로 간다(첫 시험 길은 이미 그 흐름을 잰다).
  const api = await fakeDataverifyApi(page);
  api.seed(11, {
    input: inputOf(),
    source: { kind: 'file', name: 'EDK_가상데이터_2025.json' },
  });
  await signIn(page);
  await page.goto('/dataverify/runs/11/result');
  const css = (selector: string, name: string) =>
    page
      .locator(selector)
      .first()
      .evaluate(
        (el, prop) => getComputedStyle(el).getPropertyValue(prop),
        name,
      );

  await expect(
    page.locator('[data-card="plan"] table td').first(),
  ).toBeVisible();
  expect(await css('[data-card="plan"] th', 'font-weight')).toBe('500');
  expect(await css('[data-card="plan"] th', 'background-color')).toBe(
    'rgb(250, 251, 251)',
  );
  expect(await css('[data-card="plan"] td', 'font-weight')).toBe('400');
  expect(await css('[data-card="checks"] td', 'font-weight')).toBe('400');
  // 수 크기: 32 를 주는 토큰이 없어 pre-display-03(28) — 영문번역과 같다(감독 처분 4).
  expect(await css('[data-testid="stat-checks"]', 'font-size')).toBe('28px');
  expect(await css('[data-testid="stat-checks"] small', 'font-size')).toBe(
    '14px',
  );
  // 머리 [내려받기] = outlineGrey(디자인 c3 11-11, 밴드 DV15) — 흰 바탕.
  expect(await css('[data-testid="download-head"]', 'background-color')).toBe(
    'rgb(255, 255, 255)',
  );

  await page.goto('/dataverify/new');
  const year = page.getByLabel(words.year);
  await expect(year).toBeVisible();
  expect((await year.boundingBox())!.height).toBe(36);
  const selected = page.getByRole('tab', { name: words.tabFile });
  await expect(selected).toHaveAttribute('aria-selected', 'true');
  expect(
    await selected.evaluate((el) => getComputedStyle(el).borderBottomWidth),
  ).toBe('2px');
});

test('DV-04 움직임(밴드 DV3 ②): 수 칸 Card animation-name gw-m-rise → 줄임 움직임이면 none', async ({
  page,
}) => {
  const api = await fakeDataverifyApi(page);
  api.seed(11, {
    input: inputOf(),
    source: { kind: 'file', name: 'EDK_가상데이터_2025.json' },
  });
  await signIn(page);
  await page.goto('/dataverify/runs/11/result');
  const card = page.locator('[data-stat="checks"]');
  await expect(card).toHaveClass(/gw-m-rise/);
  await expect(card).toHaveCSS('animation-name', 'gw-m-rise');
  // 움직임이 끝나면 끝 값(「n곳」 — 맞음 1 + 어긋남 1 + 도구 오류 1, 밴드 DV7)
  await expect(page.getByTestId('stat-checks')).toHaveText(
    DV_TEXT.result.cards.checksValue(3),
  );
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(card).toHaveCSS('animation-name', 'none');
  await page.reload();
  await expect(page.getByTestId('stat-checks')).toHaveText(
    DV_TEXT.result.cards.checksValue(3),
  );
  await expect(page.locator('[data-stat="checks"]')).toHaveCSS(
    'animation-name',
    'none',
  );
});

// BASE(cb08265f) 같은 자료 잼: 항목 글 위 12.5 · 오류 줄 56 · 리스크 관찰 글 위 19.8(한 줄 — 56 안 가운데). 뒤: 항목 13.5(td 기본 1px) · 나머지 같음.
test('공용 DataTable(밴드 DVW1 ①): DV-04 검증 결과 rowSpan·펼침 colSpan · 긴 칸 감싸개 위 12 · 줄 높이 56 · 리스크 감싸개 위 12', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const api = await fakeDataverifyApi(page);
  api.seed(11, {
    input: inputOf(),
    source: { kind: 'file', name: 'EDK_가상데이터_2025.json' },
  });
  await signIn(page);
  await page.goto('/dataverify/runs/11/result');
  const checks = page.locator('[data-card="checks"]');
  const line = checks.locator('tr[data-line="1"]');
  await expect(line).toHaveCount(2);
  const firstTd = line.first().locator('td').first();
  await expect(firstTd).toHaveAttribute('rowspan', '2');

  // 항목 칸(묶음): 감싸개 위 0·아래 12 · td 위 여백 = 공용 묶음 칸 (h-14 − 1lh) / 2 · 첫 줄 글 가운데 = 옆 한 줄 칸(해) 글 가운데 1px 안(밴드 TA1)
  const items = checks.getByTestId('items').first();
  const gap = await items.evaluate((el) => {
    const td = el.closest('td')!;
    const tr = td.closest('tr')!;
    const middle = (node: Node) => {
      const range = document.createRange();
      range.selectNodeContents(node);
      const rect = range.getClientRects()[0]!;
      return rect.top + rect.height / 2 - tr.getBoundingClientRect().top;
    };
    return {
      wrap: getComputedStyle(el).paddingTop,
      wrapBottom: getComputedStyle(el).paddingBottom,
      td: getComputedStyle(td).paddingTop,
      text: middle(el.firstElementChild!),
      // 열 차례 규칙·항목·연도(순번 열 없음 — 밴드 DV17)
      year: middle(tr.querySelectorAll('td')[2]!),
      firstRow: el
        .closest('table')!
        .querySelector('tbody tr')!
        .getBoundingClientRect().height,
    };
  });
  expect(gap.wrap).toBe('0px');
  expect(gap.wrapBottom).toBe('12px');
  expect(parseFloat(gap.td)).toBeCloseTo((56 - 14 * 1.6) / 2, 1);
  expect(Math.abs(gap.text - gap.year)).toBeLessThanOrEqual(1);
  expect(gap.firstRow).toBe(56);
  // 한 줄 칸 줄(오류 줄 2) 높이 56(h-14)
  const errorRow = await checks
    .locator('tr[data-line="2"]')
    .evaluate((el) => el.getBoundingClientRect().height);
  expect(Math.abs(errorRow - 56)).toBeLessThanOrEqual(1);

  // 리스크 첫 줄: 관찰 칸 감싸개 위 12 · 글 위 끝 − td 위 끝 ≥ 12(한 줄이면 56 안 가운데 — BASE 19.8)
  const risk = await page
    .getByTestId('risk-row')
    .first()
    .evaluate((tr) => {
      const td = tr.querySelectorAll('td')[2]!;
      const wrap = td.firstElementChild!;
      const range = document.createRange();
      range.selectNodeContents(wrap);
      return {
        wrap: getComputedStyle(wrap).paddingTop,
        top: range.getClientRects()[0]!.top - td.getBoundingClientRect().top,
        row: tr.getBoundingClientRect().height,
      };
    });
  expect(risk.wrap).toBe('12px');
  expect(risk.top).toBeGreaterThanOrEqual(12);
  expect(risk.row).toBe(56);

  // [보기] → rowSpan 3 · 펼침 칸 colSpan 5
  await line.last().getByRole('button').click();
  await expect(firstTd).toHaveAttribute('rowspan', '3');
  await expect(checks.locator('tr[data-expanded-row] td')).toHaveAttribute(
    'colspan',
    '5',
  );
  // 펼침 = 이름 단 줄 다섯(밴드 DV6 ①) · 값 칸(dd)은 줄마다 같은 x(1px 안 — 머리 칸 고정 폭) · 펼침 칸 잘림 0(넘침 숨김 없음)
  const detail = await checks
    .locator('tr[data-expanded-row] td')
    .evaluate((td) => ({
      keys: [...td.querySelectorAll('[data-detail]')].map((el) =>
        el.getAttribute('data-detail'),
      ),
      xs: [...td.querySelectorAll('dd')].map(
        (dd) => dd.getBoundingClientRect().left,
      ),
      clipped: td.scrollHeight > td.clientHeight + 1,
      overflow: getComputedStyle(td).overflowY,
    }));
  expect(detail.keys).toEqual([
    'formula',
    'input',
    'actual',
    'verdict',
    'diff',
  ]);
  expect(detail.xs).toHaveLength(5);
  for (const x of detail.xs)
    expect(Math.abs(x - detail.xs[0]!)).toBeLessThanOrEqual(1);
  expect(detail.clipped).toBe(false);
  expect(detail.overflow).not.toBe('hidden');
});

test('열 폭 고정(밴드 DVW1 ②): 계획·목록·DV-02 검사 내용·DV-00 구분 표 table-layout fixed · 잰 폭 · 1280 넘침 0 · 목록 탭 바꿈 머리 칸 1px 안', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const api = await fakeDataverifyApi(page);
  api.seed(11, {
    input: inputOf(),
    source: { kind: 'file', name: 'EDK_가상데이터_2025.json' },
  });
  api.seed(12, { input: inputOf(), source: { kind: 'paste' } });
  await signIn(page);
  /** 표의 짜임 · 머리 칸 폭 · 넘친 칸 수. */
  const look = (selector: string) =>
    page.locator(selector).evaluate((table) => ({
      layout: getComputedStyle(table).tableLayout,
      widths: [...table.querySelectorAll('thead th')].map((th) =>
        Math.round(th.getBoundingClientRect().width),
      ),
      overflow: [...table.querySelectorAll('th, td')].filter(
        (cell) => cell.scrollWidth > cell.clientWidth + 1,
      ).length,
    }));

  await page.goto('/dataverify/runs/11/result');
  await expect(
    page.locator('[data-card="plan"] table td').first(),
  ).toBeVisible();
  const plan = await look('[data-card="plan"] table');
  expect(plan.layout).toBe('fixed');
  // 산식 한 열(번호 열 없음 — 밴드 DV17)
  expect(plan.widths).toHaveLength(1);
  expect(plan.overflow).toBe(0);

  // 목록: 탭을 바꾸면 다시 읽는다 — 그 응답을 늦춰 스켈레톤 동안과 받은 뒤의 머리 칸 x·폭을 견준다.
  let slow = false;
  await page.route(
    (url) => url.pathname === '/api/dataverify/runs',
    async (route) => {
      if (slow) await new Promise((resolve) => setTimeout(resolve, 600));
      await route.fallback();
    },
  );
  await page.goto('/dataverify');
  const table = '[data-screen="dataverify-list"] table';
  await expect(page.getByTestId('row-status').first()).toBeVisible();
  const list = await look(table);
  expect(list.layout).toBe('fixed');
  expect(list.widths.slice(1)).toEqual([80, 120, 84, 153, 68, 87, 160, 98]);
  expect(list.overflow).toBe(0);
  const heads = () =>
    page
      .locator(`${table} thead th`)
      .evaluateAll((ths) =>
        ths.map((th) => [
          th.getBoundingClientRect().x,
          th.getBoundingClientRect().width,
        ]),
      );
  slow = true;
  await page
    .getByRole('tab', { name: DV_TEXT.list.tabs.done })
    .dispatchEvent('mousedown');
  await expect(page.locator(table)).toHaveAttribute('aria-busy', 'true');
  await page.waitForTimeout(100);
  const loading = await heads();
  await expect(page.locator(table)).not.toHaveAttribute('aria-busy', 'true');
  const after = await heads();
  loading.forEach(([x, width], index) => {
    expect(Math.abs(x! - after[index]![0]!)).toBeLessThanOrEqual(1);
    expect(Math.abs(width! - after[index]![1]!)).toBeLessThanOrEqual(1);
  });

  await page.goto('/dataverify/new');
  await expect(
    page.locator('[data-card="checks"] table td').first(),
  ).toBeVisible();
  const checks = await look('[data-card="checks"] table');
  expect(checks.layout).toBe('fixed');
  expect(checks.widths[0]).toBe(84);
  expect(checks.overflow).toBe(0);

  await page.goto('/dataverify/intro');
  const introTable = page.getByRole('table', { name: DV_TEXT.intro.heading });
  await expect(introTable.locator('td').first()).toBeVisible();
  const intro = await introTable.evaluate((el) => ({
    layout: getComputedStyle(el).tableLayout,
    widths: [...el.querySelectorAll('thead th')].map((th) =>
      Math.round(th.getBoundingClientRect().width),
    ),
  }));
  expect(intro.layout).toBe('fixed');
  expect([intro.widths[0], intro.widths[2]]).toEqual([120, 420]);
});

test('EDK 인벤토리 엑셀(DVX1 ②): .xlsx → 서버 읽기 → 미리 읽기 · 보고연도 2024 → [검증 시작] 본문 data = 읽기 답 · bad_header 글 · 양식 이름', async ({
  page,
}) => {
  const api = await fakeDataverifyApi(page);
  await signIn(page);
  await page.goto('/dataverify/new');
  const xlsx = Buffer.from([80, 75, 3, 4, 1, 2, 3, 4]);
  const input = page.locator('[data-card="data"] input[type="file"]');

  api.edk.answer = edkRejected('bad_header', 1);
  await input.setInputFiles({
    name: 'edk.xlsx',
    mimeType:
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: xlsx,
  });
  await expect(page.getByTestId('data-error')).toHaveText(
    words.errors.xlsx.bad_header,
  );
  await expect(page.getByText('지어낸-')).toHaveCount(0);
  await page.getByRole('button', { name: /edk\.xlsx/ }).click();

  api.edk.answer = EDK_OK;
  await input.setInputFiles({
    name: 'edk.xlsx',
    mimeType:
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: xlsx,
  });
  await expect(page.getByTestId('preview')).toBeVisible();
  await expect(page.getByTestId('skipped-themes')).toHaveText(
    words.skippedThemes(2, 5),
  );
  await expect(page.getByLabel(words.year)).toHaveValue('2024');
  await expect(page.getByTestId('company-filled')).toHaveText(
    words.yearFilled('2024'),
  );
  const reads = api.calls.filter(
    (call) => call.method === 'POST' && call.path === '/dataverify/edk/read',
  );
  expect(reads.map((call) => call.octets)).toEqual([xlsx.length, xlsx.length]);

  await fillCompany(page);
  await page.getByTestId('start').click();
  await expect(page).toHaveURL(/\/dataverify\/runs\/30$/);
  const [post] = api.posts();
  const options = (post!.body as { options: Record<string, unknown> }).options;
  expect(options.source).toEqual({ kind: 'file', name: 'edk.xlsx' });
  expect(options.input).toMatchObject({
    schemaVersion: 'dataverify.input@1',
    company: { name: '가상건설', reportingYear: '2024' },
  });
  expect((options.input as { data: unknown }).data).toEqual(EDK_OK.data);

  await page.goto('/dataverify/new');
  const download = page.waitForEvent('download');
  await page.getByTestId('template').click();
  expect((await download).suggestedFilename()).toBe('EDK-인벤토리-양식.xlsx');
});
