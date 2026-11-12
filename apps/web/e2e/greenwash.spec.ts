// 그린워싱 화면(/greenwash/…, 목 저장소)을 빌드 결과에서 연다. 밴드 FW1b. 주소는 경로 표(src/app/router.tsx, 밴드 RT1)를 따른다.
// PDF 는 tools/pdf-writer.ts 로 메모리에서 만든다(디스크에 .pdf 를 두지 않는다: verify.sh 의 no_real_data 가 막는다).
// 글자는 문구 표(GW_TEXT) 값으로 단언한다(e2e → entities/greenwash/config/text.ts 는 층 시험이 허락한 입구 [B2]).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { GW_TEXT } from '../src/entities/greenwash/config/text.ts';
import { writePdf } from '../tools/pdf-writer.ts';
import type { SamplePage } from '../tools/sample-layout.ts';
import { useMockStore } from './greenwash-server.ts';
import { signIn } from './session.ts';

const words = GW_TEXT.newCheck;
const intro = GW_TEXT.intro;
const status = GW_TEXT.status;
const shell = GW_TEXT.shell;
const list = GW_TEXT.list;

// 그린워싱 경로는 가드 뒤에 있다(밴드 LG1): 고객사 사용자로 로그인한 채로 시작한다.
test.beforeEach(({ page }) => signIn(page));
// 그린워싱 화면을 목 저장소로 연다(밴드 GW1R Q1 — 기본은 실어댑터, 목은 데모 빌드의 탭 표지 뒤로만). 단언은 그대로다.
test.beforeEach(({ page }) => useMockStore(page));

/** 글자 한 줄씩 든 쪽 n 개짜리 PDF. */
function pdfOf(pageCount: number): Buffer {
  const pages: SamplePage[] = Array.from({ length: pageCount }, (_, i) => ({
    width: 595,
    height: 842,
    rotate: 0,
    marks: [],
    texts: [{ x: 72, top: 72, size: 18, str: `Page ${i + 1}` }],
    tables: [],
  }));
  return Buffer.from(writePdf(pages));
}

/** 자산 응답의 종류(요청 종류 또는 주소 끝). 이것들이 text/html 로 오면 깨진 경로다(SPA fallback 이 index.html 을 준다). */
const ASSET_TYPES = new Set(['script', 'stylesheet', 'font']);
const ASSET_PATH = /\.(m?js|css|woff2?|ttf|json|pdf|wasm|bcmap)(\?|$)/;

/** 주소(경로와 search)를 열고 콘솔 오류, 404 응답, HTML 로 온 자산 응답을 모은다. */
async function open(page: Page, path: string) {
  const errors: string[] = [];
  const missing: string[] = [];
  const htmlAssets: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('response', (response) => {
    if (response.status() === 404) missing.push(response.url());
    const asset =
      ASSET_TYPES.has(response.request().resourceType()) ||
      ASSET_PATH.test(new URL(response.url()).pathname);
    if (
      asset &&
      (response.headers()['content-type'] ?? '').includes('text/html')
    )
      htmlAssets.push(response.url());
  });
  await page.goto(path);
  return { errors, missing, htmlAssets };
}

async function upload(page: Page, name: string, pageCount: number) {
  await page.locator('input[type="file"]').setInputFiles({
    name,
    mimeType: 'application/pdf',
    buffer: pdfOf(pageCount),
  });
}

const thumbs = (page: Page) =>
  page.getByTestId('thumbnails').locator('button[data-page]');
const doneCanvases = (page: Page) =>
  page.getByTestId('thumbnails').locator('canvas[data-render-state="done"]');

test('GW-02: 60쪽 PDF 를 올리면 썸네일 40개가 그려지고, 「더 보기」로 41~60쪽. 콘솔 오류·404 0', async ({
  page,
}) => {
  const { errors, missing } = await open(page, '/greenwash/new');
  await expect(
    page.getByRole('heading', { name: words.title, level: 2 }),
  ).toBeVisible();
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(page.getByTestId('file-meta')).toContainText(
    words.upload.pageMeta(60),
  );
  await expect(thumbs(page)).toHaveCount(40);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await expect(page.getByTestId('thumbnails')).toContainText(
    words.parts.viewing(1, 40),
  );
  await page.getByRole('button', { name: words.parts.more(41, 60) }).click();
  await expect(thumbs(page)).toHaveCount(60);
  await expect(doneCanvases(page)).toHaveCount(60, { timeout: 20_000 });
  await expect(
    page.getByRole('button', { name: words.parts.more(41, 60) }),
  ).toHaveCount(0);
  await expect(page.getByTestId('checked-pages')).toHaveText(
    words.parts.checked(0, 60),
  );
  expect(errors).toEqual([]);
  expect(missing).toEqual([]);
});

test('GW-02: 파트를 고르고 썸네일 둘을 누르면 글자 칸이 「4~5」, 글자 칸에 150 이면 문구 표의 오류, 고치면 사라진다', async ({
  page,
}) => {
  // 끌기의 끝 쪽(14쪽, 둘째 줄)이 화면 안에 들도록 높이를 키운다(마우스는 화면 밖으로 가지 못한다).
  await page.setViewportSize({ width: 1400, height: 1600 });
  const { errors } = await open(page, '/greenwash/new');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  const ceo = page.getByLabel(words.parts.names.ceo, { exact: true });
  await page
    .getByRole('radiogroup', { name: words.parts.groupLabel })
    .getByRole('radio', { name: new RegExp(words.parts.names.ceo) })
    .click();
  await thumbs(page).nth(3).click();
  await thumbs(page).nth(4).click();
  await expect(ceo).toHaveValue('4~5');
  // 키보드: 초점을 두고 Enter 로 넣고 빼기(누르기 토글)
  await thumbs(page).nth(9).focus();
  await page.keyboard.press('Enter');
  await expect(ceo).toHaveValue('4~5, 10');
  await page.keyboard.press('Enter');
  await expect(ceo).toHaveValue('4~5');
  await expect(
    page.getByRole('button', {
      name: words.parts.thumbLabel(4, [words.parts.names.ceo]),
    }),
  ).toHaveAttribute('data-parts', 'ceo');
  // 끌기: 회사소개를 고르고 5쪽에서 14쪽까지 끈다 → 5쪽이 겹친 쪽
  await page
    .getByRole('radiogroup', { name: words.parts.groupLabel })
    .getByRole('radio', { name: new RegExp(words.parts.names.company) })
    .click();
  const from = (await thumbs(page).nth(4).boundingBox())!;
  const to = (await thumbs(page).nth(13).boundingBox())!;
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, {
    steps: 12,
  });
  await page.mouse.up();
  const company = page.getByLabel(words.parts.names.company, { exact: true });
  await expect(company).toHaveValue('5~14');
  await expect(thumbs(page).nth(4)).toHaveAttribute(
    'data-parts',
    'ceo company',
  );
  // 겹친 쪽은 중립 꼴: 틀 #383C40(border-primary), 바깥선 없음, 쪽 번호 옆 파트 점 둘(디자인 대조 물음 5)
  const overlapFrame = thumbs(page).nth(4).locator('[data-thumb-frame]');
  await expect(overlapFrame).toHaveCSS('border-top-color', 'rgb(56, 60, 64)');
  await expect(overlapFrame).toHaveCSS('outline-style', 'none');
  await expect(thumbs(page).nth(4).locator('[data-part-dot]')).toHaveCount(2);
  await expect(thumbs(page).nth(3).locator('[data-part-dot]')).toHaveCount(0);
  await expect(page.getByTestId('checked-pages')).toHaveText(
    words.parts.checked(11, 60),
  );

  const climate = page.getByLabel(words.parts.names.climate, { exact: true });
  await climate.fill('25~37, 150');
  const error = page.getByTestId('gw-part-climate-error');
  await expect(error).toHaveText(words.parts.rangeError.over(150, 60));
  await expect(climate).toHaveAttribute('aria-invalid', 'true');
  await climate.fill('25~37, 55');
  await expect(error).toHaveCount(0);
  await expect(page.getByTestId('checked-pages')).toHaveText(
    words.parts.checked(25, 60),
  );

  await page.getByRole('button', { name: words.start }).click();
  await expect(page.locator('[data-run-id]')).toHaveAttribute(
    'data-run-id',
    'run-1',
  );
  await expect(
    page.getByRole('progressbar', { name: status.progressLabel }),
  ).toBeVisible();
  expect(screenOf(page)).toBe('status');
  expect(errors).toEqual([]);
});

test('GW-02: 문서를 올리기 전에는 쪽 한도가 300(문구 표의 한도 문구), 시작하면 파일 없음 사유', async ({
  page,
}) => {
  await open(page, '/greenwash/new');
  const ceo = page.getByLabel(words.parts.names.ceo, { exact: true });
  await ceo.fill('4~400');
  await expect(page.getByTestId('gw-part-ceo-error')).toHaveText(
    words.parts.rangeError.overMax(300),
  );
  await ceo.fill('4~5');
  await page.getByRole('button', { name: words.start }).click();
  await expect(page.getByTestId('start-problems')).toHaveText(
    words.problems.no_file,
  );
});

test('GW-02: 「3. 점검 설정」 카드가 없다 — 대상 단어 칸·근거 범위 줄 없음(시안 댓글 — sid:MARC-ENT-603)', async ({
  page,
}) => {
  await open(page, '/greenwash/new');
  await expect(h2(page, words.title)).toBeVisible();
  await expect(page.locator('[data-card="settings"]')).toHaveCount(0);
  await expect(page.getByTestId('default-terms')).toHaveCount(0);
  await expect(page.getByText('3. 점검 설정')).toHaveCount(0);
  await expect(page.getByText('근거 검색 범위')).toHaveCount(0);
  await expect(page.getByRole('radio', { name: '문서 전체' })).toHaveCount(0);
});

test('GW-02a: 글자 없는 24쪽 PDF 는 오류 안내, 카드 1 만, [점검 시작] 꺼짐', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash/new');
  await upload(page, '목-스캔-24쪽.pdf', 24);
  await expect(page.getByTestId('no-text')).toHaveText(words.upload.noText);
  await expect(page.getByTestId('file-meta')).toContainText(
    /^총 24페이지 · \S+ · 텍스트 없음$/,
  );
  await expect(page.getByText(words.upload.noTextHow)).toBeVisible();
  await expect(page.getByRole('button', { name: words.start })).toBeDisabled();
  await expect(page.locator('[data-card="parts"]')).toHaveCount(0);
  await expect(page.locator('[data-card="settings"]')).toHaveCount(0);
  await expect(page.getByTestId('thumbnails')).toHaveCount(0);
  // 지우면 다시 켜진다
  await page.getByRole('button', { name: /목-스캔-24쪽\.pdf/ }).click();
  await expect(page.getByRole('button', { name: words.start })).toBeEnabled();
  expect(errors).toEqual([]);
});

test('GW-02: 표 밖 이름의 파일은 「올릴 수 없는 파일」', async ({ page }) => {
  await open(page, '/greenwash/new');
  await upload(page, '모르는-보고서.pdf', 2);
  await expect(page.getByText(words.upload.uploadFailed)).toBeVisible();
  await expect(page.getByTestId('file-meta')).toHaveCount(0);
});

/** 주소의 경로가 가리키는 화면(경로 표 src/app/router.tsx). 그린워싱 밖이면 null. */
function screenOf(page: Page): string | null {
  const path = new URL(page.url()).pathname;
  const match =
    /^\/greenwash(?:\/(intro|new)|\/runs\/[^/]+(?:\/(result|review))?)?$/.exec(
      path,
    );
  if (!match) return null;
  if (match[1]) return match[1];
  if (path.startsWith('/greenwash/runs/')) return match[2] ?? 'status';
  return 'list';
}
/** 주소의 경로에 든 실행 id. */
const runOf = (page: Page) =>
  /^\/greenwash\/runs\/([^/]+)/.exec(new URL(page.url()).pathname)?.[1] ?? null;
const h2 = (page: Page, name: string) =>
  page.getByRole('heading', { name, level: 2, exact: true });

test('GW-00 → [시작하기] → GW-01 문서 목록 → [새 점검] → GW-02 → 파일·쪽 → [점검 시작] → GW-03 진행 막대(셸 안)', async ({
  page,
}) => {
  const { errors, missing } = await open(page, '/greenwash/intro');
  await expect(h2(page, intro.title)).toBeVisible();
  // 등급 설명 표: 배지 셋과 예시 글
  const table = page.getByRole('table', { name: intro.tableLabel });
  await expect(table.getByRole('row')).toHaveCount(4);
  await expect(table).toContainText(intro.levels.high.example);
  await expect(page.getByTestId('pdf-info')).toHaveText(intro.pdfInfo);
  await expect(
    page
      .getByRole('list', { name: intro.processHeading })
      .getByRole('listitem'),
  ).toHaveCount(3);
  // 셸: 머리 줄 제목과 인사
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(shell.title);
  await expect(page.getByText(shell.greeting)).toBeVisible();

  // 시작 안내는 점검 과정 카드 안, 3단계 띠 아래(시안 댓글 — sid:MARC-ENT-603)
  await expect(page.getByTestId('start-hint')).toHaveText(intro.startHint);
  expect(
    await page
      .getByTestId('start-hint')
      .evaluate((hint) =>
        hint.previousElementSibling?.getAttribute('data-testid'),
      ),
  ).toBe('process-band');

  // [시작하기] → 문서 목록(새 점검이 아니다 — 시안 댓글, sid:MARC-ENT-603)
  await page.getByRole('button', { name: intro.start }).click();
  await expect(h2(page, list.title)).toBeVisible();
  expect(screenOf(page)).toBe('list');
  expect(pathOf(page)).toBe('/greenwash');
  await page.getByRole('button', { name: list.newCheck }).click();
  await expect(h2(page, words.title)).toBeVisible();
  expect(screenOf(page)).toBe('new');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await page
    .getByLabel(words.parts.names.climate, { exact: true })
    .fill('25~37');
  await page.getByRole('button', { name: words.start }).click();

  await expect(h2(page, status.title.running)).toBeVisible();
  const bar = page.getByRole('progressbar', { name: status.progressLabel });
  await expect(bar).toHaveAttribute('aria-valuenow', '0');
  await expect(page.locator('[data-run-id]')).toHaveAttribute(
    'data-run-id',
    'run-1',
  );
  expect(screenOf(page)).toBe('status');
  // 제목 아래 설명: 시작 시각 뒤(시각은 지금이라 뺀다) 「점검할 쪽 13쪽」(25~37)
  await expect(page.locator('[data-screen="status"]')).toContainText(
    status.meta('@', 13).split('@')[1]!,
  );
  // [목록으로] → 목록(GW-01, 밴드 FW2 ②. 앞에서는 목록이 없어 소개로 갔다)
  await page.getByRole('button', { name: status.back }).first().click();
  await expect(h2(page, list.title)).toBeVisible();
  expect(screenOf(page)).toBe('list');
  expect(errors).toEqual([]);
  expect(missing).toEqual([]);
});

test('운영 관리자(sid:MARC-ENT-374·409 — 밴드 GR3): 목록 [새 점검] → GW-02 → 파일·쪽 → [점검 시작] → GW-03(run-1). 콘솔 오류·404 0', async ({
  page,
}) => {
  // 뒤에 단 경로 처리기가 먼저 답한다 — 이 시험만 운영 관리자로 복원한다(흉내 서버).
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  const { errors, missing } = await open(page, '/greenwash');
  await expect(page.getByText(shell.adminGreeting)).toBeVisible();
  await expect(page.getByText(list.mineOnly)).toHaveCount(0);
  await page.getByRole('button', { name: list.newCheck, exact: true }).click();
  await expect(h2(page, words.title)).toBeVisible();
  expect(screenOf(page)).toBe('new');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await page
    .getByLabel(words.parts.names.climate, { exact: true })
    .fill('25~37');
  await page.getByRole('button', { name: words.start }).click();
  await expect(h2(page, status.title.running)).toBeVisible();
  expect(screenOf(page)).toBe('status');
  expect(runOf(page)).toBe('run-1');
  expect(errors).toEqual([]);
  expect(missing).toEqual([]);
});

test('GW-03 진행(&mock=running): 단계 셋, 둘째만 쪽 진행 28 / 44, 전체 60%(무게 10·80·10)', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash/runs/run-1?mock=running');
  await expect(h2(page, status.title.running)).toBeVisible();
  const bar = page.getByRole('progressbar', { name: status.progressLabel });
  await expect(bar).toHaveAttribute('aria-valuenow', '60');
  await expect(page.getByTestId('progress-percent')).toHaveText(
    status.percent(60),
  );
  const stages = page.locator('li[data-stage]');
  await expect(stages).toHaveCount(3);
  await expect(page.locator('li[data-stage="extract"]')).toHaveAttribute(
    'data-state',
    'done',
  );
  await expect(page.locator('li[data-stage="extract"]')).toContainText(
    status.stages.extract.body(139),
  );
  const judge = page.locator('li[data-stage="judge"]');
  await expect(judge).toHaveAttribute('data-state', 'now');
  await expect(judge).toHaveAttribute('aria-current', 'step');
  await expect(judge).toContainText(status.stages.judge.body(28, 44));
  await expect(page.locator('li[data-stage="summarize"]')).toHaveAttribute(
    'data-state',
    'todo',
  );
  await expect(page.getByTestId('failure')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('GW-03 실패(&mock=failed): 실행 전체 실패 안내, [다시 실행] 은 새 실행(run-1 → run-2)', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash/runs/run-1?mock=failed');
  const root = page.locator('[data-run-id]');
  await expect(root).toHaveAttribute('data-run-id', 'run-1');
  await expect(h2(page, status.title.failed)).toBeVisible();
  await expect(page.getByTestId('failure-info')).toHaveText(status.failure);
  // 멈춤에는 진행 카드(막대·단계 셋)가 없다(판 r3 — sid:MARC-ISSUE-265 (1), 밴드 GP1)
  await expect(page.getByRole('progressbar')).toHaveCount(0);
  await expect(page.locator('li[data-stage]')).toHaveCount(0);
  // 어디서 멈췄는지는 카드 없이도: 위 단계 띠의 지금 단계(판정에서 멈춤 → STEP 2)와 제목·안내 글
  await expect(
    page
      .getByRole('list', { name: GW_TEXT.stepFlow.label })
      .locator('[aria-current="step"]'),
  ).toContainText(GW_TEXT.stepFlow.steps[1]!);
  await page.getByRole('button', { name: status.rerun }).click();
  await expect(root).toHaveAttribute('data-run-id', 'run-2');
  await expect(page.locator('[data-screen="status"]')).toHaveAttribute(
    'data-run-state',
    'running',
  );
  await expect(page.getByTestId('failure')).toHaveCount(0);
  await expect(h2(page, status.title.running)).toBeVisible();
  expect(screenOf(page)).toBe('status');
  expect(errors).toEqual([]);
});

// 밴드 RT1: 「실행 없이 screen=status 면 목록으로」는 새 주소 체계에선 만들 수 없는 경우라 지웠다(옛 주소 넘기기는 단위 시험 app/greenwash/router.test.tsx ③).
test('GW-03 실패의 [목록으로] 는 목록으로', async ({ page }) => {
  await open(page, '/greenwash/runs/run-1?mock=failed');
  await page
    .getByTestId('failure')
    .getByRole('button', { name: status.back })
    .click();
  await expect(h2(page, list.title)).toBeVisible();
  expect(screenOf(page)).toBe('list');
});

test('셸: 고른 메뉴는 그린워싱 하나. 꺼진 항목은 Enter·클릭에도 화면·쿼리가 그대로, 대조로 [시작하기] Enter 는 화면을 바꾼다 [R5]', async ({
  page,
}) => {
  await open(page, '/greenwash/new');
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  const current = nav.locator('[aria-current="page"]');
  await expect(current).toHaveCount(1);
  await expect(current).toHaveText(shell.menu.greenwash);
  const disabled = nav.locator('[aria-disabled="true"]');
  // 영문번역 켬 — TRW1a H5 · 데이터 검증 켬 — DV2a H5 · 중대성평가 켬 — IRW1 H6 · 온실가스 켬 — W12-0a
  await expect(disabled).toHaveCount(1);

  const dashboard = nav.getByRole('button', { name: shell.menu.dashboard });
  await dashboard.focus();
  await expect(dashboard).toBeFocused();
  await page.keyboard.press('Enter');
  await dashboard.dispatchEvent('click');
  await expect(h2(page, words.title)).toBeVisible();
  expect(screenOf(page)).toBe('new');
  await expect(current).toHaveText(shell.menu.greenwash);

  // 대조: 소개의 [시작하기] 에 초점을 두고 Enter 면 문서 목록으로 간다(sid:MARC-ENT-603)
  await open(page, '/greenwash/intro');
  const start = page.getByRole('button', { name: intro.start });
  await start.focus();
  await page.keyboard.press('Enter');
  await expect(h2(page, list.title)).toBeVisible();
  expect(screenOf(page)).toBe('list');
});

test('GW-02: 끌어서 썸네일 칸·페이지 밖으로 나가면 자동 스크롤하며 칠한다(마우스)', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash/new');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await page
    .getByRole('radiogroup', { name: words.parts.groupLabel })
    .getByRole('radio', { name: new RegExp(words.parts.names.ceo) })
    .click();
  const box = page.getByTestId('thumbnails-scroll');
  const first = thumbs(page).nth(0);
  await first.scrollIntoViewIfNeeded();
  const startScroll = await page.evaluate(() => window.scrollY);
  const at = (await first.boundingBox())!;
  const height = page.viewportSize()!.height;
  await page.mouse.move(at.x + at.width / 2, at.y + at.height / 2);
  await page.mouse.down();
  // 화면 아래 끝으로 끌고 손을 떼지 않는다 → 썸네일 칸이 끝까지, 그다음 페이지가 스크롤된다
  await page.mouse.move(at.x + at.width / 2, height - 4, { steps: 10 });
  await expect
    .poll(() => box.evaluate((el) => el.scrollTop), { timeout: 10_000 })
    .toBeGreaterThan(0);
  await expect
    .poll(() => page.evaluate(() => window.scrollY), { timeout: 10_000 })
    .toBeGreaterThan(startScroll);
  // 칸의 넷째 줄(31쪽, 처음엔 칸 밖)까지 칠해졌다
  await expect(thumbs(page).nth(30)).toHaveAttribute('data-parts', 'ceo', {
    timeout: 10_000,
  });
  await page.mouse.up();
  await expect(
    page.getByLabel(words.parts.names.ceo, { exact: true }),
  ).toHaveValue(/^1~3\d$/);
  expect(errors).toEqual([]);
});

test.describe('터치', () => {
  test.use({ hasTouch: true });

  test('GW-02: 터치는 끌어 칠하지 않고, 톡 누르면 하나씩 넣고 뺀다(썸네일 칸은 터치 스크롤 그대로)', async ({
    page,
  }) => {
    const { errors } = await open(page, '/greenwash/new');
    await upload(page, '목-보고서-60쪽.pdf', 60);
    await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
    await page
      .getByRole('radiogroup', { name: words.parts.groupLabel })
      .getByRole('radio', { name: new RegExp(words.parts.names.ceo) })
      .tap();
    const ceo = page.getByLabel(words.parts.names.ceo, { exact: true });
    await thumbs(page).nth(3).tap();
    await thumbs(page).nth(6).tap();
    await expect(ceo).toHaveValue('4, 7');
    await thumbs(page).nth(3).tap();
    await expect(ceo).toHaveValue('7');
    // 손가락으로 1쪽에서 14쪽까지 쓸면 칠하지 않는다(스크롤 몫). CDP 로 터치를 흘린다.
    const a = (await thumbs(page).nth(0).boundingBox())!;
    const b = (await thumbs(page).nth(13).boundingBox())!;
    const cdp = await page.context().newCDPSession(page);
    const point = (box: typeof a, t: number) => ({
      x: box.x + box.width / 2 + (b.x - a.x) * t,
      y: box.y + box.height / 2 + (b.y - a.y) * t,
    });
    await cdp.send('Input.dispatchTouchEvent', {
      type: 'touchStart',
      touchPoints: [point(a, 0)],
    });
    for (let step = 1; step <= 10; step++)
      await cdp.send('Input.dispatchTouchEvent', {
        type: 'touchMove',
        touchPoints: [point(a, step / 10)],
      });
    await cdp.send('Input.dispatchTouchEvent', {
      type: 'touchEnd',
      touchPoints: [],
    });
    await expect(ceo).toHaveValue('7');
    await expect(thumbs(page).nth(0)).not.toHaveAttribute('data-parts', /./);
    await expect(page.getByTestId('thumbnails-scroll')).toHaveCSS(
      'touch-action',
      'auto',
    );
    expect(errors).toEqual([]);
  });
});

// ── 밴드 FW2 ⓪: FW1b 디자인 대조 고침 + sid:MARC-ISSUE-99 화면 고침 ──

const heightOf = async (locator: ReturnType<Page['locator']>) =>
  (await locator.boundingBox())!.height;

test('파트 고르기: radiogroup 의 radio, 방향키로 고르고 초점이 따라간다. 알약 36·고른 것 Bold. 필수 점 없음', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash/new');
  const group = page.getByRole('radiogroup', { name: words.parts.groupLabel });
  const radios = group.getByRole('radio');
  await expect(radios).toHaveCount(3);
  const ceo = group.getByRole('radio', {
    name: new RegExp(words.parts.names.ceo),
  });
  const company = group.getByRole('radio', {
    name: new RegExp(words.parts.names.company),
  });
  await expect(ceo).toHaveAttribute('aria-checked', 'true');
  expect(await heightOf(ceo)).toBe(36);
  await expect(ceo).toHaveCSS('font-weight', '700');
  await expect(company).toHaveCSS('font-weight', '500');
  await ceo.focus();
  await page.keyboard.press('ArrowRight');
  await expect(company).toBeFocused();
  await expect(company).toHaveAttribute('aria-checked', 'true');
  await expect(ceo).toHaveAttribute('aria-checked', 'false');
  await expect(ceo).toHaveAttribute('tabindex', '-1');
  // 필수 점과 aria-required 가 없다(파트는 하나 이상이면 된다)
  for (const key of ['ceo', 'company', 'climate'] as const) {
    const field = page.getByLabel(words.parts.names[key], { exact: true });
    await expect(field).not.toHaveAttribute('aria-required', /.*/);
  }
  await expect(page.locator('label .rounded-full')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('[점검 시작] 오류는 칸 아래: 파일 없음은 드롭존 아래 + 드롭존 초점, 파트 셋이 비면 묶음 아래 + 첫 파트 칸 초점', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash/new');
  await page.getByRole('button', { name: words.start }).click();
  const fileError = page.getByTestId('start-problems');
  await expect(fileError).toHaveText(words.problems.no_file);
  const zone = page.getByRole('button', {
    name: new RegExp(words.upload.guide),
  });
  await expect(zone).toBeFocused();
  // 드롭존 아래에 있다(버튼 위에 모은 줄이 아니다)
  const zoneBox = (await zone.boundingBox())!;
  const errorBox = (await fileError.boundingBox())!;
  expect(errorBox.y).toBeGreaterThanOrEqual(zoneBox.y + zoneBox.height);
  const startBox = (await page
    .getByRole('button', { name: words.start })
    .boundingBox())!;
  expect(errorBox.y).toBeLessThan(startBox.y - 200);

  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(fileError).toHaveCount(0);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await page.getByRole('button', { name: words.start }).click();
  await expect(page.getByTestId('no-parts')).toHaveText(
    words.problems.no_parts,
  );
  await expect(
    page.getByLabel(words.parts.names.ceo, { exact: true }),
  ).toBeFocused();
  // 한 파트만 넣으면 시작된다
  await page.getByLabel(words.parts.names.company, { exact: true }).fill('6~9');
  await expect(page.getByTestId('no-parts')).toHaveCount(0);
  await page.getByRole('button', { name: words.start }).click();
  await expect(h2(page, status.title.running)).toBeVisible();
  expect(errors).toEqual([]);
});

test('300쪽 초과는 파일 줄 아래 오류(「…300쪽까지만…」), 파일 줄 한 줄에 쪽 수·크기', async ({
  page,
}) => {
  await open(page, '/greenwash/new');
  await upload(page, '목-큰문서-320쪽.pdf', 2);
  const meta = page.getByTestId('file-meta');
  await expect(meta).toContainText(words.upload.pageMeta(320));
  // 파일 이름과 같은 줄(li) 안
  await expect(page.locator('li', { has: meta })).toContainText(
    '목-큰문서-320쪽.pdf',
  );
  await page.getByRole('button', { name: words.start }).click();
  await expect(page.getByTestId('start-problems')).toHaveText(
    words.problems.too_many_pages(320, 300),
  );
  await expect(
    page.getByRole('button', { name: /목-큰문서-320쪽\.pdf/ }),
  ).toBeFocused();
});

test('쪽 끝 버튼은 모두 md(36): GW-00 [시작하기], GW-02 [취소][점검 시작], 글자 없는 PDF 에서도 같다', async ({
  page,
}) => {
  await open(page, '/greenwash/intro');
  expect(await heightOf(page.getByRole('button', { name: intro.start }))).toBe(
    36,
  );
  await page.getByRole('button', { name: intro.start }).click();
  await expect(h2(page, list.title)).toBeVisible();
  await page.getByRole('button', { name: list.newCheck }).click();
  const start = page.getByRole('button', { name: words.start });
  const cancel = page.getByRole('button', { name: words.cancel, exact: true });
  expect(await heightOf(start)).toBe(36);
  expect(await heightOf(cancel)).toBe(36);
  await upload(page, '목-스캔-24쪽.pdf', 24);
  await expect(start).toBeDisabled();
  expect(await heightOf(start)).toBe(36);
});

test('GW-03: 실패 meta 에 「계속돼요」 없음·덧글 없음, [다시 실행]은 처음부터(추출 진행 중 「정리해요」). 막대 바탕 #E7E9EC', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash/runs/run-1?mock=failed');
  const root = page.locator('[data-screen="status"]');
  await expect(h2(page, status.title.failed)).toBeVisible();
  await expect(root).not.toContainText('이 창을 닫아도');
  await expect(root).toContainText(status.meta('@', 44, false).split('@')[1]!);
  // 덧글(failureNote)은 없다(디자인 답 D4 — 밴드 GW2R ②)
  await expect(page.getByTestId('failure-note')).toHaveCount(0);
  await expect(page.getByRole('button', { name: status.rerun })).toHaveCount(1);
  await page.getByRole('button', { name: status.rerun }).click();
  await expect(page.locator('[data-run-id]')).toHaveAttribute(
    'data-run-id',
    'run-2',
  );
  await expect(root).toContainText('이 창을 닫아도');
  const extract = page.locator('li[data-stage="extract"]');
  await expect(extract).toHaveAttribute('data-state', 'now');
  await expect(extract).toContainText(status.stages.extract.bodyPending(139));
  await expect(
    page.getByRole('progressbar', { name: status.progressLabel }),
  ).toHaveCSS('background-color', 'rgb(231, 233, 236)');
  await expect(
    page.locator('li[data-stage="summarize"] > span[aria-hidden]'),
  ).toHaveCSS('background-color', 'rgb(231, 233, 236)');
  await expect(page.locator('li[data-stage="summarize"]')).toContainText(
    status.stages.summarize.body,
  );
  expect(errors).toEqual([]);
});

test('GW-00 3단계 띠: 위 4px 주황 선·아래 1px 선, 칸 바탕 없음, 이름 16 Bold 주황, 「Step n」 14 Bold', async ({
  page,
}) => {
  await open(page, '/greenwash/intro');
  const band = page.getByRole('list', { name: intro.processHeading });
  await expect(band).toHaveCSS('border-top-width', '4px');
  await expect(band).toHaveCSS('border-top-color', 'rgb(242, 92, 44)');
  await expect(band).toHaveCSS('border-bottom-width', '1px');
  const first = band.getByRole('listitem').first();
  await expect(first).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
  const name = first.locator('strong');
  await expect(name).toHaveText(intro.process[0].name);
  await expect(name).toHaveCSS('font-size', '16px');
  await expect(name).toHaveCSS('font-weight', '700');
  await expect(name).toHaveCSS('color', 'rgb(242, 92, 44)');
  await expect(first.locator('b')).toHaveCSS('font-size', '14px');
  // 칸 사이 꺾쇠 동그라미 28
  const go = first.locator('span[aria-hidden]');
  expect((await go.boundingBox())!.width).toBe(28);
});

test('썸네일: 칠한 쪽의 틀은 그림에 붙는다(캔버스 폭 = 틀 안쪽 폭 ± 1px, 양옆 색 띠 없음)', async ({
  page,
}) => {
  // 1920 폭(디자인 기준): 칸(약 154)이 그림(595pt × 0.2 = 119)보다 넓다. 좁은 폭에서는 그림이 칸에 맞춰 줄어 차이가 안 보인다.
  await page.setViewportSize({ width: 1920, height: 1080 });
  const { errors } = await open(page, '/greenwash/new');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await thumbs(page).nth(3).click();
  await expect(thumbs(page).nth(3)).toHaveAttribute('data-parts', 'ceo');
  const sizes = await thumbs(page)
    .nth(3)
    .locator('[data-thumb-frame]')
    .evaluate((frame) => {
      const style = getComputedStyle(frame);
      const inner =
        frame.getBoundingClientRect().width -
        parseFloat(style.paddingLeft) -
        parseFloat(style.paddingRight) -
        parseFloat(style.borderLeftWidth) -
        parseFloat(style.borderRightWidth);
      const canvas = frame.querySelector('canvas')!.getBoundingClientRect();
      return { inner, canvas: canvas.width };
    });
  expect(Math.abs(sizes.canvas - sizes.inner)).toBeLessThanOrEqual(1);
  // 그림이 칸보다 좁은 자리에서 잰 것이다(빈 검사가 아니다)
  const cell = (await thumbs(page).nth(3).boundingBox())!.width;
  expect(cell - sizes.canvas).toBeGreaterThan(10);
  expect(errors).toEqual([]);
});

test('코드로 연 모달을 닫으면 연 자리로 초점이 돌아간다(공용 DialogContent, sid:MARC-ISSUE-97 1번)', async ({
  page,
}) => {
  await page.goto('/dev/parts');
  const opener = page.getByTestId('confirm-open-8');
  await opener.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(opener).toBeFocused();
  const exclude = page.getByTestId('exclude-open');
  await exclude.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: GW_TEXT.exclude.cancel }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(exclude).toBeFocused();
});

test('글꼴: 목록 화면을 열면 Pretendard 는 쓰인 글자의 dynamic-subset 조각만 받는다(합 < 1.5MB), 옛 JP 통파일은 받지 않는다', async ({
  page,
}) => {
  const fonts: { url: string; bytes: number }[] = [];
  page.on('response', async (response) => {
    if (response.request().resourceType() !== 'font') return;
    const body = await response.body().catch(() => Buffer.alloc(0));
    fonts.push({ url: response.url(), bytes: body.length });
  });
  await page.goto('/greenwash');
  await expect(h2(page, list.title)).toBeVisible();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  await page.waitForLoadState('networkidle');
  const subsets = fonts.filter((font) =>
    /PretendardVariable\.subset\.\d+-[^/]*\.woff2$/.test(
      new URL(font.url).pathname,
    ),
  );
  // 실측(2026-10-16, 밴드 CW1 ②): 글꼴 응답 10개(Pretendard 조각 9개), 합 596,640 바이트. 옛 JP 통파일 하나는 5.3MB 였다.
  const total = fonts.reduce((sum, font) => sum + font.bytes, 0);
  expect(subsets.length).toBeGreaterThan(0);
  expect(fonts.filter((font) => /PretendardJP/i.test(font.url))).toEqual([]);
  expect(total).toBeLessThan(1_500_000);
});

// ── 밴드 FW2 ②: GW-01 문서 목록과 목록으로 잇기 ──

const listTable = (page: Page) =>
  page.getByRole('table', { name: list.tableLabel });
const listRows = (page: Page) => listTable(page).locator('tbody tr');

test('GW-01: 루트(/)를 열면 목록(/greenwash), 씨앗 여섯 줄(상태 다섯, 실호출 씨앗 하나 포함), 수정본은 마지막 판만, 셸 메뉴 「그린워싱 점검」은 목록으로', async ({
  page,
}) => {
  const { errors, missing } = await open(page, '/');
  await expect(h2(page, list.title)).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/greenwash');
  // 지어낸 씨앗 다섯 + 실호출 씨앗(run-106 B.pdf, 밴드 FX1) 하나
  // 고객사 사용자의 설명 줄(회사 · 문서 n건 · 실행 n회 · …)은 없다(시안 댓글 — sid:MARC-ENT-603)
  await expect(page.getByText(/문서 \d+건 · 실행 \d+회/)).toHaveCount(0);
  await expect(listRows(page)).toHaveCount(6);
  const states = await listRows(page)
    .getByTestId('row-status')
    .evaluateAll((els) => els.map((el) => el.getAttribute('data-status')));
  expect(new Set(states)).toEqual(
    new Set(['running', 'in_review', 'failed', 'pending', 'confirmed']),
  );
  // 버전 칸은 없다(v115 GW-01_r2 — 밴드 GW2R ①). 사슬 묶음은 그대로: 앞 판(초안)은 줄이 없다
  await expect(
    listTable(page).getByRole('columnheader', { name: '버전' }),
  ).toHaveCount(0);
  await expect(listTable(page)).not.toContainText(/v\d 수정본|이전 버전/);
  await expect(listTable(page)).not.toContainText(
    '목-환경경영보고서-2026-초안.pdf',
  );
  // 확정 줄: 잠금 표시 「MM-DD 이름」
  await expect(
    listRows(page).filter({ hasText: '목-ESG하이라이트-2025.pdf' }),
  ).toContainText('10-03');
  await expect(page.getByTestId('list-notice')).toHaveText(list.notice);

  // 메뉴 「그린워싱 점검」 → 목록(새 점검에서)
  await page.getByRole('button', { name: list.newCheck }).click();
  await expect(h2(page, words.title)).toBeVisible();
  await page
    .getByRole('navigation')
    .getByRole('button', { name: shell.menu.greenwash })
    .click();
  await expect(h2(page, list.title)).toBeVisible();
  expect(screenOf(page)).toBe('list');
  expect(errors).toEqual([]);
  expect(missing).toEqual([]);
});

test('GW-01 거르기: 상태 탭 여섯, 문서명 검색, 보고연도, 내가 올린 것만, 0건이면 Empty', async ({
  page,
}) => {
  await open(page, '/greenwash');
  await expect(listRows(page)).toHaveCount(6);
  const tab = (name: string) =>
    page
      .getByRole('tablist', { name: list.tabsLabel })
      .getByRole('tab', { name, exact: true });
  await tab(list.tabs.running).click();
  await expect(tab(list.tabs.running)).toHaveAttribute('aria-selected', 'true');
  await expect(listRows(page)).toHaveCount(1);
  await tab(list.tabs.failed).click();
  await expect(listRows(page)).toHaveCount(1);
  await tab(list.tabs.confirmed).click();
  await expect(listRows(page)).toHaveCount(1);
  await tab(list.tabs.all).click();
  await page.getByRole('textbox', { name: list.searchLabel }).fill('기후');
  await expect(listRows(page)).toHaveCount(1);
  await expect(listRows(page)).toContainText('목-기후공시-2025.pdf');
  await page.getByRole('textbox', { name: list.searchLabel }).fill('');
  await page
    .getByRole('combobox', { name: list.yearLabel })
    .selectOption({ label: list.year(2025) });
  await expect(listRows(page)).toHaveCount(2);
  await page
    .getByRole('combobox', { name: list.yearLabel })
    .selectOption({ label: list.yearAll });
  await page.getByRole('checkbox', { name: list.mineOnly }).click();
  // 실호출 씨앗(doc-s6)도 지금 사용자가 올린 것
  await expect(listRows(page)).toHaveCount(4);
  await page.getByRole('textbox', { name: list.searchLabel }).fill('없는이름');
  await expect(listRows(page)).toHaveCount(1);
  await expect(listTable(page)).toContainText(list.emptyTitle);
  await expect(listTable(page)).toContainText(list.emptyFiltered);
});

test('GW-01 줄 누르기·다음 할 일: 줄 안 버튼은 줄 누르기를 일으키지 않는다, 줄 → GW-04·GW-03, 다음 할 일 → GW-05·GW-03, [새 점검] → GW-02', async ({
  page,
}) => {
  await open(page, '/greenwash');
  const row = (name: string) => listRows(page).filter({ hasText: name });
  // 검토 중 줄의 [검토 이어 하기] → GW-05(줄 누르기라면 GW-04 였다)
  await row('목-지속가능경영보고서-2026.pdf')
    .getByRole('button', { name: list.next.continue_review })
    .click();
  await expect(page.locator('[data-screen="review"]')).toBeVisible();
  expect(screenOf(page)).toBe('review');
  expect(runOf(page)).toBe('run-101');
  // GW-05 의 [요약으로]는 GW-04 로 간다(밴드 FW2 ④) — 메뉴로 목록에 돌아간다
  await page
    .getByRole('navigation')
    .getByRole('button', { name: shell.menu.greenwash })
    .click();
  // 줄 누르기(이름 단서가 있다) → GW-04
  const clickable = page.getByRole('row', {
    name: list.rowLabel('목-지속가능경영보고서-2026.pdf', list.rowOpen.result),
  });
  await clickable.getByRole('cell').first().click();
  await expect(page.locator('[data-screen="result"]')).toBeVisible();
  expect(screenOf(page)).toBe('result');
  // GW-04 에는 [목록으로]가 없다(시안 GW-04_r1) — 메뉴로 목록에 돌아간다
  await page
    .getByRole('navigation')
    .getByRole('button', { name: shell.menu.greenwash })
    .click();
  // AI 점검 중 줄 → GW-03(진행), [진행 보기]도 같다
  await row('목-통합보고서-2026.pdf').getByRole('cell').first().click();
  await expect(h2(page, status.title.running)).toBeVisible();
  expect(runOf(page)).toBe('run-103');
  await page.getByRole('button', { name: status.back }).first().click();
  // 실패 줄의 [다시 실행] → 새 실행(run-1)의 GW-03
  await row('목-기후공시-2025.pdf')
    .getByRole('button', { name: list.next.rerun })
    .click();
  await expect(h2(page, status.title.running)).toBeVisible();
  await expect(page.locator('[data-run-id]')).toHaveAttribute(
    'data-run-id',
    'run-1',
  );
  await page.getByRole('button', { name: status.back }).first().click();
  // [새 점검] → GW-02, [취소] → 목록
  await page.getByRole('button', { name: list.newCheck }).click();
  await expect(h2(page, words.title)).toBeVisible();
  await page.getByRole('button', { name: words.cancel, exact: true }).click();
  await expect(h2(page, list.title)).toBeVisible();
  expect(screenOf(page)).toBe('list');
});

// 밴드 RT1: 「실행 없는 screen=review·result 는 목록으로」 시험은 지웠다(새 주소에는 늘 실행 id 가 있다 — 옛 주소는 단위 ③).

test('GW-00 등급 설명 표의 열 너비 120 / 나머지 / 420(1920 폭)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await open(page, '/greenwash/intro');
  const headers = page
    .getByRole('table', { name: intro.tableLabel })
    .getByRole('columnheader');
  await expect(headers).toHaveCount(3);
  const widths = await headers.evaluateAll((els) =>
    els.map((el) => el.getBoundingClientRect().width),
  );
  expect(Math.round(widths[0]!)).toBe(120);
  expect(Math.round(widths[2]!)).toBe(420);
  expect(widths[1]!).toBeGreaterThan(420);
});

// ── 밴드 FW2 ③: GW-04 결과 요약 ──

const result = GW_TEXT.result;
const statValue = (page: Page, id: string) =>
  page.getByTestId(id).getByTestId('stat-value');

test('GW-04(검토 중, run-101): 통계 수 = 문장 수, 실패한 쪽 안내, 확정 전 안내, 2회차 meta, [내려받기] → 받기 모달 엑셀 줄은 목 파일 내려받기', async ({
  page,
}) => {
  const { errors, missing } = await open(
    page,
    '/greenwash/runs/run-101/result',
  );
  await expect(
    page.getByRole('heading', {
      level: 2,
      name: /^목-지속가능경영보고서-2026\.pdf/,
    }),
  ).toBeVisible();
  await expect(page.getByTestId('review-state')).toHaveAttribute(
    'data-state',
    'in_review',
  );
  await expect(
    page.getByText(
      result.meta({
        at: '2026-10-14 10:00',
        ordinal: 2,
        pageCount: 60,
        checked: 7,
        reviewed: 2,
        total: 5,
      }),
    ),
  ).toBeVisible();
  // 통계 넷: 지적된 문장 = 문장 수(5) = 등급 합
  await expect(statValue(page, 'stat-total')).toHaveText('5');
  const levels = await Promise.all(
    ['stat-high', 'stat-mid', 'stat-low'].map(async (id) =>
      Number(await statValue(page, id).textContent()),
    ),
  );
  expect(levels.reduce((a, b) => a + b, 0)).toBe(5);
  // 인식 실패 페이지 줄(v115 GW-04_r2 · Q7 — 밴드 GW2R ②)
  await expect(page.getByTestId('failed-pages')).toHaveText(
    `${result.missedPages(1)}${result.missedPage(7)}${result.missedNote}`,
  );
  await expect(page.getByTestId('unconfirmed-notice')).toBeVisible();
  await expect(page.getByTestId('image-notice')).toHaveText(result.imageNotice);
  // [내려받기](밴드 GDL1 — 옛 [엑셀 내보내기]를 갈음): 머리 단추는 켜져 있고 받기 모달의 「점검 결과 엑셀」 줄을 누르면
  // 목의 지어낸 파일을 내려받는다, 화면은 그대로. [닫기] 뒤 초점은 [내려받기]
  const opener = page.getByTestId('gw-downloads');
  await expect(opener).not.toHaveAttribute('aria-disabled', 'true');
  await expect(opener).toHaveText(GW_TEXT.downloads.title);
  await opener.click();
  const dialog = page.getByTestId('gw-download-dialog');
  await expect(dialog).toBeVisible();
  const excel = dialog.getByTestId('gw-download-dialog-file-excel');
  await expect(excel).toHaveText(GW_TEXT.downloads.excel);
  await expect(dialog).toContainText(GW_TEXT.downloads.excelNote);
  await expect(excel).not.toHaveAttribute('aria-disabled', 'true');
  await expect(excel).toHaveCSS('opacity', '1');
  const download = page.waitForEvent('download');
  await excel.click();
  expect((await download).suggestedFilename()).toBe('greenwash-run-101.xlsx');
  expect(screenOf(page)).toBe('result');
  await dialog.getByRole('button', { name: GW_TEXT.downloads.close }).click();
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  // 파트별 표: 결과의 파트 이름 그대로
  await expect(
    page
      .getByRole('table', { name: result.partsTableLabel })
      .locator('tbody tr'),
  ).toHaveCount(3);
  // [검토 이어 하기] → GW-05
  await page.getByRole('button', { name: result.continueReview }).click();
  await expect(page.locator('[data-screen="review"]')).toBeVisible();
  expect(screenOf(page)).toBe('review');
  expect(errors).toEqual([]);
  expect(missing).toEqual([]);
});

test('GW-04(검토 대기, run-102): 실패한 쪽 안내 없음, 「추가」 배지 줄(기본 목록과 겹친 탄소중립 줄에는 없음), 파트별 탭', async ({
  page,
}) => {
  await open(page, '/greenwash/runs/run-102/result');
  await expect(page.getByTestId('review-state')).toHaveAttribute(
    'data-state',
    'pending',
  );
  await expect(page.getByTestId('image-notice')).toBeVisible();
  await expect(page.getByTestId('failed-pages')).toHaveCount(0);
  const total = page.getByTestId('terms-total');
  await expect(total.locator('li[data-term="초록 물결"]')).toHaveAttribute(
    'data-extra',
    'true',
  );
  await expect(
    total.locator('li[data-term="초록 물결"]').getByTestId('extra-badge'),
  ).toHaveText(result.extraBadge);
  await expect(total.locator('li[data-term="탄소중립"]')).toBeVisible();
  await expect(
    total.locator('li[data-term="탄소중립"]').getByTestId('extra-badge'),
  ).toHaveCount(0);
  await expect(total.locator('li[data-term="탄소 중립"]')).toHaveCount(0);
  // 파트별: 파트마다 묶음
  await page
    .getByRole('tablist', { name: result.termsTabsLabel })
    .getByRole('tab', { name: result.termsTabs.parts })
    .click();
  await expect(
    page.getByTestId('terms').locator('section[data-part]'),
  ).toHaveCount(3);
});

test('GW-04(확정, run-105): [확정] 없음, [결과 보기], 확정 전 안내 없음', async ({
  page,
}) => {
  await open(page, '/greenwash/runs/run-105/result');
  await expect(
    page.getByRole('button', { name: result.viewResult }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: result.confirm })).toHaveCount(
    0,
  );
  await expect(page.getByTestId('unconfirmed-notice')).toHaveCount(0);
});

test('GW-02 → GW-03 → (&autofinish=1) → GW-04 → [검토 이어 하기] → GW-05: 새 실행의 지은 결과, 콘솔 오류 0', async ({
  page,
}) => {
  const { errors, missing } = await open(page, '/greenwash/new?autofinish=1');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await page.getByLabel(words.parts.names.ceo, { exact: true }).fill('3');
  await page
    .getByLabel(words.parts.names.climate, { exact: true })
    .fill('5, 9');
  await page.getByRole('button', { name: words.start }).click();
  await expect(page.locator('[data-screen="status"]')).toBeVisible();
  // 곧 끝나도 저절로 넘기지 않는다: 「분석이 끝났어요」 + [결과 보기] 를 누르면 GW-04(디자인 대조 C8)
  await expect(page.locator('[data-screen="status"]')).toHaveAttribute(
    'data-run-state',
    'done',
  );
  await expect(h2(page, status.title.done)).toBeVisible();
  expect(screenOf(page)).toBe('status');
  await page.getByRole('button', { name: status.viewResult }).click();
  await expect(page.locator('[data-screen="result"]')).toHaveAttribute(
    'data-result-state',
    'ready',
  );
  expect(screenOf(page)).toBe('result');
  expect(runOf(page)).toBe('run-1');
  await expect(
    page.getByRole('heading', { level: 2, name: /^목-보고서-60쪽\.pdf/ }),
  ).toBeVisible();
  // 지은 문장 셋(쪽 셋) — 통계 수 = 문장 수
  await expect(statValue(page, 'stat-total')).toHaveText('3');
  await page.getByRole('button', { name: result.continueReview }).click();
  await expect(page.locator('[data-screen="review"]')).toBeVisible();
  // 밴드 FW2 ④: GW-05 가운데 칸 — 올린 PDF 의 쪽을 그린다. 첫 문장(High, 3쪽)은 상자 있음, 둘째(Mid, 5쪽)는 위치 없음 안내
  const pane = page.getByTestId('review-page');
  const canvas = pane.locator('canvas');
  await expect(canvas).toHaveAttribute('data-render-state', 'done', {
    timeout: 20_000,
  });
  await expect(pane.getByTestId('page-heading')).toHaveText(
    review.pageHeading(3),
  );
  const highlight = pane.getByTestId('highlight');
  await expect(highlight).toHaveAttribute('data-level', 'High');
  await expect(pane.getByTestId('position-missing')).toHaveCount(0);
  // 상자 자리 = 캔버스 왼쪽 위 + pt × 배율: 지은 결과의 첫 상자 [72, 120, 500, 134].
  // 배율은 쪽 칸 폭에 맞춘 값이라(밴드 GFS1 fitScale) 캔버스 폭 ÷ 쪽 폭(pdfOf 595pt)으로 잰다
  const canvasBox = (await canvas.boundingBox())!;
  const lightBox = (await highlight.boundingBox())!;
  const scale = canvasBox.width / 595;
  expect(scale).toBeLessThanOrEqual(1);
  expect(Math.abs(lightBox.x - canvasBox.x - 72 * scale)).toBeLessThanOrEqual(
    1,
  );
  expect(Math.abs(lightBox.y - canvasBox.y - 120 * scale)).toBeLessThanOrEqual(
    1,
  );
  expect(Math.abs(lightBox.width - 428 * scale)).toBeLessThanOrEqual(1);
  await page
    .getByTestId('sentence-list')
    .locator('button[data-item="1"]')
    .click();
  await expect(pane.getByTestId('position-missing')).toHaveText(
    GW_TEXT.review.positionMissing,
  );
  await expect(pane.getByTestId('highlight')).toHaveCount(0);
  await expect(pane.getByTestId('page-heading')).toHaveText(
    review.pageHeading(5),
  );
  await expect(pane.locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
  );
  expect(errors).toEqual([]);
  expect(missing).toEqual([]);
});

// ── 밴드 FW2 ④: GW-05 문장 검토 + 05a·05b·05c ──
const review = GW_TEXT.reviewScreen;
const sentence = (page: Page, index: number) =>
  page.getByTestId('sentence-list').locator(`button[data-item="${index}"]`);
const markOf = (page: Page, index: number) =>
  sentence(page, index).locator('[data-review]');
const pick = (page: Page, name: string) =>
  page
    .getByTestId('review-detail')
    .getByRole('group', { name: GW_TEXT.review.groupLabel })
    .getByRole('button', { name });

test('GW-04 [확정] → GW-05 에서 05b(확정 확인)가 열린 채 시작한다(run-101, 미검토 3)', async ({
  page,
}) => {
  await open(page, '/greenwash/runs/run-101/result');
  await page.getByRole('button', { name: result.confirm }).click();
  await expect(page.locator('[data-screen="review"]')).toBeVisible();
  expect(screenOf(page)).toBe('review');
  const dialog = page.getByRole('dialog', { name: GW_TEXT.confirm.title });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText(GW_TEXT.confirm.unreviewedWarning(3));
  // [취소]로 닫으면 GW-05 그대로(확정하지 않음)
  await dialog.getByRole('button', { name: GW_TEXT.confirm.cancel }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('review-state')).toHaveAttribute(
    'data-state',
    'in_review',
  );
});

test('GW-05(run-101): 채택 → 진행 +1, 둘째 표시 뒤 첫 표시 남음, 05a 사유 없이 오류, 확정 → 05b 미검토 경고 → 05c 잠김, [요약으로] → [결과 보기] 로 다시 읽은 검토의 미검토 0', async ({
  page,
}) => {
  const { errors, missing } = await open(
    page,
    '/greenwash/runs/run-101/review',
  );
  const tally = page.getByTestId('review-tally');
  const progress = page.getByTestId('review-progress');
  await expect(tally).toHaveText(review.tally(1, 1, 3));
  await expect(progress).toHaveAttribute('data-reviewed', '2');
  // 씨앗 문서는 PDF 가 없다: 미리보기 안내. 첫 문장(position 있음)은 위치 없음 안내가 없다
  await expect(page.getByTestId('preview-unavailable')).toHaveText(
    review.previewUnavailable,
  );
  await expect(page.getByTestId('position-missing')).toHaveCount(0);
  // 1번 채택 → 진행 3/5
  await sentence(page, 1).click();
  await expect(sentence(page, 1)).toHaveAttribute('aria-current', 'true');
  await pick(page, GW_TEXT.review.adopted).click();
  await expect(markOf(page, 1)).toHaveAttribute('data-review', 'adopted');
  await expect(progress).toHaveAttribute('data-reviewed', '3');
  await expect(progress).toContainText(review.progress(3, 5));
  // 3번(position null) — PDF 가 없어 쪽을 못 보여 주므로 위치 없음 안내도 없다(미리보기 안내 하나, C3). 제외 → 05a: 사유 없이 [제외]는 오류
  await sentence(page, 3).click();
  await expect(sentence(page, 3)).toHaveAttribute('aria-current', 'true');
  await expect(page.getByTestId('position-missing')).toHaveCount(0);
  await expect(page.getByTestId('preview-unavailable')).toHaveCount(1);
  await pick(page, GW_TEXT.review.excluded).click();
  const exclude = page.getByRole('dialog', { name: GW_TEXT.exclude.title });
  await expect(exclude).toBeVisible();
  await exclude
    .getByRole('button', { name: GW_TEXT.exclude.submit, exact: true })
    .click();
  await expect(exclude.getByRole('alert')).toHaveText(
    GW_TEXT.exclude.reasonRequired,
  );
  await exclude
    .getByRole('radio', { name: GW_TEXT.exclude.reasons.not_claim })
    .click();
  await exclude
    .getByRole('button', { name: GW_TEXT.exclude.submit, exact: true })
    .click();
  await expect(exclude).toHaveCount(0);
  await expect(markOf(page, 3)).toHaveAttribute('data-review', 'excluded');
  // 둘째 표시 뒤에도 첫 표시(1번 채택)와 씨앗 표시(0 채택·2 제외)가 남는다(본문은 marks 전부)
  await expect(markOf(page, 1)).toHaveAttribute('data-review', 'adopted');
  await expect(markOf(page, 0)).toHaveAttribute('data-review', 'adopted');
  await expect(markOf(page, 2)).toHaveAttribute('data-review', 'excluded');
  // 저장 뒤 끝에 「 · 자동 저장됨 HH:MM」(밴드 GW2R ② Q6)
  await expect(tally).toHaveText(
    /^채택 2 · 제외 2 · 미검토 1 · 자동 저장됨 \d\d:\d\d$/,
  );
  // 확정 → 05b 미검토 1 경고 → [확정] → 05c
  await page.getByRole('button', { name: review.confirm, exact: true }).click();
  const confirm = page.getByRole('dialog', { name: GW_TEXT.confirm.title });
  await expect(confirm).toContainText(GW_TEXT.confirm.unreviewedWarning(1));
  await confirm
    .getByRole('button', { name: GW_TEXT.confirm.submit, exact: true })
    .click();
  await expect(confirm).toHaveCount(0);
  await expect(page.locator('[data-lock-banner]')).toBeVisible();
  await expect(page.getByTestId('review-state')).toHaveAttribute(
    'data-state',
    'confirmed',
  );
  await expect(
    page.getByRole('button', { name: review.confirm, exact: true }),
  ).toHaveCount(0);
  await expect(
    page
      .getByTestId('review-detail')
      .getByRole('group', { name: GW_TEXT.review.groupLabel }),
  ).toHaveCount(0);
  await expect(page.getByTestId('review-detail')).toContainText(review.locked);
  // [내려받기](밴드 GDL1 — 옛 [엑셀 내보내기 · 확정본]을 갈음): 받기 모달의 「점검 결과 엑셀 · 확정본」 줄이 확정본을 내려받는다
  await page.getByTestId('gw-downloads').click();
  const confirmedDialog = page.getByTestId('gw-download-dialog');
  const confirmedExcel = confirmedDialog.getByTestId(
    'gw-download-dialog-file-excel',
  );
  await expect(confirmedExcel).toHaveText(GW_TEXT.downloads.excelConfirmed);
  const confirmedDownload = page.waitForEvent('download');
  await confirmedExcel.click();
  expect((await confirmedDownload).suggestedFilename()).toBe(
    'greenwash-run-101-confirmed.xlsx',
  );
  await confirmedDialog
    .getByRole('button', { name: GW_TEXT.downloads.close })
    .click();
  await expect(confirmedDialog).toHaveCount(0);
  // 새로고침 없이 [요약으로] → GW-04 → [결과 보기] → GW-05: 다시 연 화면이 getReview 로 읽은 값으로 센다 [N9][2R1]
  await page.getByRole('button', { name: review.back }).click();
  await expect(page.locator('[data-screen="result"]')).toHaveAttribute(
    'data-result-state',
    'ready',
  );
  await page.getByRole('button', { name: result.viewResult }).click();
  await expect(page.locator('[data-screen="review"]')).toHaveAttribute(
    'data-review-state',
    'confirmed',
  );
  await expect(tally).toHaveAttribute('data-pending', '0');
  await expect(tally).toHaveText(review.tally(3, 2, 0));
  await expect(progress).toHaveAttribute('data-reviewed', '5');
  await expect(page.locator('[data-lock-banner]')).toBeVisible();
  expect(errors).toEqual([]);
  expect(missing).toEqual([]);
});

test('GW-05c(run-105 확정): 잠금 띠(확정 일시·사람), 등급 탭 마지막 「제외」, [확정]·검토 버튼 없음', async ({
  page,
}) => {
  await open(page, '/greenwash/runs/run-105/review');
  await expect(page.locator('[data-lock-banner]')).toContainText(
    '2026-10-03 15:30',
  );
  const levels = page.getByRole('tablist', { name: review.levelTabsLabel });
  await expect(levels.getByRole('tab').last()).toHaveText(
    review.levelTabs.excluded,
  );
  await expect(
    page.getByRole('button', { name: review.confirm, exact: true }),
  ).toHaveCount(0);
  await expect(
    page
      .getByTestId('review-detail')
      .getByRole('group', { name: GW_TEXT.review.groupLabel }),
  ).toHaveCount(0);
});

// ── 밴드 RT1: 주소·새로고침·뒤로 가기(경로 표 src/app/router.tsx) ──

const pathOf = (page: Page) => {
  const url = new URL(page.url());
  return url.pathname + url.search;
};

test('목록 → 실행 열기(GW-04) → 검토(GW-05) → [요약으로]: 주소가 경로 표대로 바뀐다', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash');
  expect(pathOf(page)).toBe('/greenwash');
  await page
    .getByRole('row', {
      name: list.rowLabel(
        '목-지속가능경영보고서-2026.pdf',
        list.rowOpen.result,
      ),
    })
    .getByRole('cell')
    .first()
    .click();
  await expect(page.locator('[data-screen="result"]')).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash/runs/run-101/result');
  await expect(page.locator('[data-run-id]')).toHaveAttribute(
    'data-run-id',
    'run-101',
  );
  await page.getByRole('button', { name: result.continueReview }).click();
  await expect(page.locator('[data-screen="review"]')).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash/runs/run-101/review');
  await page.getByRole('button', { name: review.back }).first().click();
  await expect(page.locator('[data-screen="result"]')).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash/runs/run-101/result');
  // 메뉴 → 목록: 목록에는 실행 id 가 없다(data-run-id 없음)
  await page
    .getByRole('navigation')
    .getByRole('button', { name: shell.menu.greenwash })
    .click();
  await expect(h2(page, list.title)).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash');
  await expect(page.locator('[data-run-id]')).toHaveCount(0);
  // 뒤로 가기는 앱 안의 앞 화면으로
  await page.goBack();
  await expect(page.locator('[data-screen="result"]')).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash/runs/run-101/result');
  expect(errors).toEqual([]);
});

test('GW-04 [확정] → 05b → 새로고침하면 05b 없음(검토·같은 실행 그대로), 뒤로 → 앞으로도 05b 없음', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash/runs/run-101/result');
  await page.getByRole('button', { name: result.confirm }).click();
  const dialog = page.getByRole('dialog', { name: GW_TEXT.confirm.title });
  await expect(dialog).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash/runs/run-101/review');
  // 표식은 주소·history.state 어디에도 없다
  const state = await page.evaluate(() => JSON.stringify(history.state));
  expect(state).not.toMatch(/confirm/i);

  const reviewShown = async () => {
    await expect(page.locator('[data-screen="review"]')).toBeVisible();
    await expect(page.getByTestId('review-state')).toHaveAttribute(
      'data-state',
      'in_review',
    );
  };
  await page.reload();
  await reviewShown();
  expect(pathOf(page)).toBe('/greenwash/runs/run-101/review');
  await expect(page.locator('[data-run-id]')).toHaveAttribute(
    'data-run-id',
    'run-101',
  );
  await expect(dialog).toHaveCount(0);

  await page.goBack();
  await expect(page.locator('[data-screen="result"]')).toBeVisible();
  await page.goForward();
  await reviewShown();
  await expect(dialog).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('목록 → 새 점검 → 시작(GW-03) → 끝남(GW-04) → 뒤로 = 목록(다 쓴 양식·끝난 GW-03 이 아님)', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash?autofinish=1');
  await page.getByRole('button', { name: list.newCheck }).click();
  await expect(h2(page, words.title)).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash/new');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  // 썸네일이 다 그려진 뒤에 시작한다(그리는 중에 화면을 떠나면 올린 파일의 blob 주소를 놓친 콘솔 오류가 난다 — 위 autofinish 시험과 같다)
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await page.getByLabel(words.parts.names.ceo, { exact: true }).fill('3');
  await page.getByRole('button', { name: words.start }).click();
  await expect(page.locator('[data-screen="status"]')).toBeVisible();
  await page.getByRole('button', { name: status.viewResult }).click();
  await expect(page.locator('[data-screen="result"]')).toHaveAttribute(
    'data-result-state',
    'ready',
  );
  expect(pathOf(page)).toBe('/greenwash/runs/run-1/result');
  await page.goBack();
  await expect(h2(page, list.title)).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash?autofinish=1');
  expect(errors).toEqual([]);
});

test('/ 를 열면 /greenwash 목록(replace), 옛 주소(?view=·?screen=)도 넘기지 않고 목록, 콘솔 오류 0', async ({
  page,
}) => {
  const { errors, missing } = await open(page, '/');
  await expect(h2(page, list.title)).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash');
  await page.goto('/?view=greenwash&screen=status&mock=failed');
  await expect(h2(page, list.title)).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash');
  expect(errors).toEqual([]);
  expect(missing).toEqual([]);
});

test('깊은 주소를 바로 열어도 자산(js·css·font·worker·json·pdf)이 HTML 로 오지 않는다, 404·콘솔 오류 0', async ({
  page,
}) => {
  // 먼저 자산 응답을 본다(깨진 base 면 js 가 HTML 로 와서 화면이 뜨지 않는다 — 그 까닭이 먼저 드러나게).
  const review = await open(page, '/greenwash/runs/run-1/review?mock=done');
  await page.waitForLoadState('networkidle');
  expect(review.htmlAssets).toEqual([]);
  await expect(page.locator('[data-screen="review"]')).toBeVisible();
  await expect(page.getByTestId('review-state')).toBeVisible();
  await page.waitForLoadState('networkidle');
  expect(review.htmlAssets).toEqual([]);
  expect(review.missing).toEqual([]);
  expect(review.errors).toEqual([]);

  const viewer = await open(page, '/dev/viewer?data=sample/compare.json');
  await page.waitForLoadState('networkidle');
  expect(viewer.htmlAssets).toEqual([]);
  await expect(
    page.locator('[data-document-id="a"] [data-page="1"] canvas'),
  ).toHaveAttribute('data-render-state', 'done', { timeout: 20_000 });
  await page.waitForLoadState('networkidle');
  expect(viewer.htmlAssets).toEqual([]);
  // 404 는 실제 자료 목록 하나뿐(시험에는 실제 자료가 없다 — 뷰어는 없으면 예시만 보인다). 앱 뿌리의 /local/ 이다(/dev/local/ 이 아니다).
  expect(viewer.missing).toEqual([
    new URL('/local/index.json', page.url()).href,
  ]);
  // 그 404 의 콘솔 글(Failed to load resource … 404) 하나만 뺀다 — 404 가 그 하나뿐임은 바로 위가 못박았다.
  expect(viewer.errors.filter((error) => !/status of 404/.test(error))).toEqual(
    [],
  );
});

test('화면을 옮겨도 스크롤 위치가 그대로다(맨 위로 보내지 않는다 — 다듬기 몫)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1400, height: 400 });
  await open(page, '/greenwash/intro');
  const start = page.getByRole('button', { name: intro.start });
  await expect(start).toBeVisible();
  // 목록 쪽 끝보다 작은 위치에 세운다 — 그래야 「위치를 지킴」(그대로)·「맨 위로 보냄」(0)·「맨 아래로 보냄」(쪽 끝)이 셋 다 다른 값이다(밴드 GWT1)
  await page.evaluate(() => window.scrollTo(0, 120));
  const before = await page.evaluate(() => window.scrollY);
  expect(before).toBe(120);
  // 누름은 dispatchEvent: 실제 click 은 단추를 창 안으로 스크롤한 뒤 눌러 세운 위치를 바꾼다. 실제 누름으로 [시작하기]가 목록에 닿는 것은
  // 「GW-00 → [시작하기] → GW-01 문서 목록 → …」 시험이 따로 잰다
  await start.dispatchEvent('click');
  // [시작하기]는 문서 목록으로(sid:MARC-ENT-603)
  await expect(h2(page, list.title)).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash');
  // 새 화면이 그려진 뒤에도 이동 전 위치 그대로다(맨 위로도, 맨 아래로도 보내지 않는다). 세운 위치가 목록 쪽 끝보다 작아야 이 등호가 그 둘을 가른다
  const { scrollY, maxY } = await page.evaluate(() => ({
    scrollY: window.scrollY,
    maxY: document.documentElement.scrollHeight - window.innerHeight,
  }));
  expect(before).toBeLessThan(maxY);
  expect(scrollY).toBe(before);
});

/** GW-05 세 칸(목록 · 쪽 · 상세)의 폭. 칸 줄 = 검토 수(review-tally)와 상세(review-detail)를 함께 담은 가장 가까운 조상. */
async function reviewColumns(page: Page): Promise<number[]> {
  return page.getByTestId('review-tally').evaluate((tally) => {
    let card: Element | null = tally;
    while (
      card?.parentElement &&
      !card.parentElement.querySelector('[data-testid="review-detail"]')
    )
      card = card.parentElement;
    return [...card!.parentElement!.children].map(
      (column) => column.getBoundingClientRect().width,
    );
  });
}

test('최소 폭 1280(sid:MARC-ENT-213): 1200 폭이면 화면 전체가 가로로 스크롤된다(줄이지 않는다)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1200, height: 900 });
  const { errors } = await open(page, '/greenwash');
  await expect(page.locator('[data-app-shell]')).toBeVisible();
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    shell: document.querySelector('[data-app-shell]')!.getBoundingClientRect()
      .width,
  }));
  expect(widths.scroll).toBeGreaterThanOrEqual(1280);
  expect(widths.shell).toBeGreaterThanOrEqual(1280);
  expect(errors).toEqual([]);
});

test('GW-05 세 칸: 1280 폭(1440 미만)은 280 · 나머지 · 320(±1)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { errors } = await open(page, '/greenwash/runs/run-101/review');
  await expect(page.getByTestId('review-detail')).toBeVisible();
  const columns = await reviewColumns(page);
  expect(Math.abs(columns[0]! - 280)).toBeLessThanOrEqual(1);
  expect(Math.abs(columns[2]! - 320)).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});

test('GW-05 세 칸: 1440 폭은 320 · 나머지 · 384(±1)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { errors } = await open(page, '/greenwash/runs/run-101/review');
  await expect(page.getByTestId('review-detail')).toBeVisible();
  const columns = await reviewColumns(page);
  expect(Math.abs(columns[0]! - 320)).toBeLessThanOrEqual(1);
  expect(Math.abs(columns[2]! - 384)).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});

// 밴드 GFS1(sid:MARC-ISSUE-449): 쪽 그림은 쪽 칸 안쪽 폭에 맞춰 줄어든다(fitScale) — 옛 「넘치면 왼쪽부터 놓고 가로 스크롤」을 갈음한다.
test('GW-05 쪽 칸: 1280 폭에서 쪽 그림이 칸 폭에 맞춰 줄어 가로로 넘치지 않고 첫 문장 상자의 등급 태그가 쪽 칸 안에 다 들어온다, 1920 폭에서는 가운데', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { errors } = await open(page, '/greenwash/new?autofinish=1');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await page.getByLabel(words.parts.names.ceo, { exact: true }).fill('3');
  await page.getByRole('button', { name: words.start }).click();
  await page.getByRole('button', { name: status.viewResult }).click();
  await page.getByRole('button', { name: result.continueReview }).click();
  const pane = page.getByTestId('review-page');
  await expect(pane.locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
    { timeout: 20_000 },
  );
  const measured = await pane.getByTestId('page-scroll').evaluate((box) => {
    const rect = (element: Element) => element.getBoundingClientRect();
    const canvas = rect(box.querySelector('canvas')!);
    const tag = rect(
      box.querySelector('[data-testid="highlight"] [data-level]')!,
    );
    const outer = rect(box);
    const card = box.closest('[data-testid="review-page"]')!.parentElement!;
    return {
      card: [card.scrollWidth, card.clientWidth],
      overflow: box.scrollWidth > box.clientWidth,
      canvasLeft: canvas.left,
      canvasRight: canvas.right,
      boxLeft: outer.left,
      tag: [tag.left, tag.top, tag.right, tag.bottom],
      box: [outer.left, outer.top, outer.right, outer.bottom],
    };
  });
  // 쪽 칸도 바깥 카드(가운데 칸)도 가로로 넘치지 않는다 — 쪽 그림 양 끝이 쪽 칸 안
  expect(measured.overflow).toBe(false);
  expect(measured.card[0]).toBe(measured.card[1]);
  expect(measured.canvasLeft).toBeGreaterThanOrEqual(measured.boxLeft);
  expect(measured.canvasRight).toBeLessThanOrEqual(measured.box[2]!);
  const [tagLeft, tagTop, tagRight, tagBottom] = measured.tag;
  const [boxLeft, boxTop, boxRight, boxBottom] = measured.box;
  expect(tagLeft).toBeGreaterThanOrEqual(boxLeft!);
  expect(tagTop).toBeGreaterThanOrEqual(boxTop!);
  expect(tagRight).toBeLessThanOrEqual(boxRight!);
  expect(tagBottom).toBeLessThanOrEqual(boxBottom!);
  // 넓은 폭(1920)에서도 가운데(넘치지 않을 때 safe center = center)
  await page.setViewportSize({ width: 1920, height: 900 });
  await expect
    .poll(() =>
      pane.getByTestId('page-scroll').evaluate((box) => {
        const outer = box.getBoundingClientRect();
        const canvas = box.querySelector('canvas')!.getBoundingClientRect();
        return Math.round(
          canvas.left - outer.left - (outer.right - canvas.right),
        );
      }),
    )
    .toBe(0);
  expect(errors).toEqual([]);
});

// ── 밴드 GP1: 시연 전 손질(리허설 LR1·LR2, 디자인 대조 GW3R) ──
test('GW-05 긴 근거(실호출 씨앗 run-106) 1280 폭: 어느 문장을 골라도 쪽 전체가 1280 을 넘지 않고 근거 칩이 상세 칸 안(sid:MARC-ISSUE-201·202 1번)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { errors } = await open(page, '/greenwash/runs/run-106/review');
  await expect(page.getByTestId('review-detail')).toBeVisible();
  const rows = page.getByTestId('sentence-list').locator('button[data-item]');
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
  let measuredChips = 0;
  for (let index = 0; index < count; index++) {
    await rows.nth(index).click();
    await expect(page.getByTestId('review-detail')).toHaveAttribute(
      'data-item',
      String(index),
    );
    const measured = await page.evaluate(() => {
      const detail = document
        .querySelector('[data-testid="review-detail"]')!
        .getBoundingClientRect();
      const chips = [...document.querySelectorAll('[data-testid="chips"] > *')];
      // 칩 글의 줄 상자가 모두 칩 상자 안인가(줄을 바꿔도 칩이 같이 커진다 — 키트 Badge 의 h-5 고정이면 글이 밖으로 샌다)
      const spills = chips.filter((chip) => {
        const box = chip.getBoundingClientRect();
        const range = document.createRange();
        range.selectNodeContents(chip);
        return [...range.getClientRects()].some(
          (line) =>
            line.bottom > box.bottom + 0.5 ||
            line.top < box.top - 0.5 ||
            line.right > box.right + 0.5,
        );
      }).length;
      const rects = chips.map((chip) => chip.getBoundingClientRect());
      return {
        scroll: document.documentElement.scrollWidth,
        chips: chips.length,
        spills,
        over: rects.filter(
          (chip) => chip.right > detail.right + 0.5 || chip.left < detail.left,
        ).length,
      };
    });
    expect(measured.scroll, `문장 ${index}`).toBeLessThanOrEqual(1280);
    expect(measured.over, `문장 ${index}`).toBe(0);
    expect(measured.spills, `문장 ${index}`).toBe(0);
    measuredChips += measured.chips;
  }
  // 빈 검사가 아니다(칩이 든 문장을 쟀다)
  expect(measuredChips).toBeGreaterThan(0);
  // 쪽 그림 배율(밴드 GFS1 fitScale, 검증 권고 R2): 캔버스 폭 ÷ 쪽 폭(지은 PDF 842pt) = (쪽 칸 안쪽 폭 ÷ 842, 0.01 내림).
  // 쪽 폭을 배율로 나누지 않고 재면 배율이 1 과 줄인 값을 오가므로, 두 번(사이 300ms) 재서 둘 다 맞아야 한다
  const pane = page.getByTestId('review-page');
  await expect(pane.locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
    { timeout: 20_000 },
  );
  const scaleOf = () =>
    pane.getByTestId('page-scroll').evaluate((box) => {
      const style = getComputedStyle(box);
      const inner =
        box.clientWidth -
        parseFloat(style.paddingLeft) -
        parseFloat(style.paddingRight);
      return {
        drawn: box.querySelector('canvas')!.getBoundingClientRect().width / 842,
        expected: Math.min(1, Math.floor((inner / 842) * 100) / 100),
      };
    });
  for (let sample = 0; sample < 2; sample++) {
    if (sample > 0) await page.waitForTimeout(300);
    const { drawn, expected } = await scaleOf();
    expect(expected).toBeLessThan(1);
    expect(Math.abs(drawn - expected), `배율 ${sample}`).toBeLessThanOrEqual(
      0.01,
    );
  }
  expect(errors).toEqual([]);
});

test('GW-05 목록 배지(GW3R A1): meta 가 길어도(파트 둘·근거 없음) 검토 표시·등급 배지는 한 줄(1280)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await open(page, '/greenwash/runs/run-101/review');
  await expect(page.getByTestId('review-detail')).toBeVisible();
  // 배지 글의 줄 상자 수(키트 Badge 는 높이 고정이라 상자 높이로는 꺾임이 안 보인다 — 글의 줄을 센다)
  const lines = await page
    .getByTestId('sentence-list')
    .locator('[data-review], [data-level]')
    .evaluateAll((marks) =>
      marks.map((mark) => {
        const range = document.createRange();
        range.selectNodeContents(mark);
        const rects = [...range.getClientRects()].filter(
          (rect) => rect.width > 0,
        );
        // 글이 차지한 높이(위 끝 ~아래 끝)가 한 줄 높이의 1.5배 안이면 한 줄(점 같은 작은 상자도 같은 줄 안)
        const top = Math.min(...rects.map((rect) => rect.top));
        const bottom = Math.max(...rects.map((rect) => rect.bottom));
        const line = parseFloat(getComputedStyle(mark).lineHeight);
        return {
          lines: bottom - top < line * 1.5 ? 1 : 2,
          text: mark.textContent,
        };
      }),
    );
  expect(lines.length).toBeGreaterThan(0);
  for (const { lines: count, text } of lines) expect(count, text ?? '').toBe(1);
});

test('파트 이름(sid:MARC-ISSUE-314 디자인 결정 (나)): 서버 값 「기후/환경 토픽」을 받은 결과·검토가 「기후·환경」을 그린다', async ({
  page,
}) => {
  const climate = GW_TEXT.newCheck.parts.names.climate;
  const { errors } = await open(page, '/greenwash/runs/run-106/result');
  await expect(
    page.getByRole('table', { name: result.partsTableLabel }),
  ).toContainText(climate);
  await page.getByRole('tab', { name: result.termsTabs.parts }).click();
  await expect(page.locator('[data-part] h4')).toContainText([climate]);
  await expect(page.locator('main')).not.toContainText('기후/환경 토픽');
  await page.goto('/greenwash/runs/run-106/review');
  await expect(page.getByTestId('review-detail')).toBeVisible();
  await expect(
    page.getByRole('tab', { name: new RegExp(`^${climate} \\d+$`) }),
  ).toBeVisible();
  await expect(page.getByTestId('review-detail')).toContainText(climate);
  await expect(page.getByTestId('sentence-list')).toContainText(climate);
  await expect(page.locator('main')).not.toContainText('기후/환경 토픽');
  // 거르기는 서버 이름 그대로(파트 탭을 누르면 그 파트 문장만)
  await page
    .getByRole('tab', { name: new RegExp(`^${climate} \\d+$`) })
    .click();
  await expect(
    page.getByTestId('sentence-list').locator('button[data-item]').first(),
  ).toContainText(climate);
  expect(errors).toEqual([]);
});

test('GW3R A4·A5·A7·A8: 통계 숫자 display-03, 양식 라벨 칸 바탕·오른쪽 선, 목록 안내는 표 카드 안, 「점검 안내」 → GW-00', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await open(page, '/greenwash');
  await expect(listRows(page).first()).toBeVisible();
  // A7: 안내 상자는 표와 같은 카드 안
  const sameCard = await page.getByTestId('list-notice').evaluate((notice) => {
    const table = document.querySelector('table')!;
    let card: Element | null = notice.parentElement;
    while (card && !card.contains(table)) card = card.parentElement;
    return card !== null && card.tagName !== 'MAIN' && card !== document.body;
  });
  expect(sameCard).toBe(true);
  // A8: 제목 줄 오른쪽 「점검 안내」 → GW-00
  await page.getByRole('link', { name: list.introLink }).click();
  await expect(page.locator('[data-screen="intro"]')).toBeVisible();
  expect(pathOf(page)).toBe('/greenwash/intro');
  // A4: GW-04 통계 숫자(1280 = 토큰 sm 28px, 700)
  await page.goto('/greenwash/runs/run-101/result');
  const value = page.getByTestId('stat-value').first();
  await expect(value).toBeVisible();
  const font = await value.evaluate((node) => {
    const style = getComputedStyle(node.parentElement!);
    return [style.fontSize, style.fontWeight];
  });
  expect(font).toEqual(['28px', '700']);
  // A5: GW-02 양식 줄 라벨 칸(보고연도) — 바탕 support-grey-subtle(#FAFBFB)·오른쪽 1px 선·줄 높이 64 이상
  await page.goto('/greenwash/new');
  const label = page.getByText(words.year.label, { exact: true }).first();
  const look = await label.evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      background: style.backgroundColor,
      right: style.borderRightWidth,
      row: node.parentElement!.getBoundingClientRect().height,
    };
  });
  expect(look.background).toBe('rgb(250, 251, 251)');
  expect(look.right).toBe('1px');
  expect(look.row).toBeGreaterThanOrEqual(64);
});

test('GW-02 큰 파일(GP1 §1-8): 50MB 넘는 파일은 고를 때 막고 「50MB 이하 PDF 만 올릴 수 있어요」, 파일 줄·문서 없음', async ({
  page,
}, testInfo) => {
  await open(page, '/greenwash/new');
  // 51MB(버퍼 한도 50MB 를 넘어 파일로 넘긴다 — 테스트 출력 폴더, git 밖)
  const { writeFileSync } = await import('node:fs');
  const file = testInfo.outputPath('지어낸-큰-보고서.pdf');
  writeFileSync(
    file,
    Buffer.concat([pdfOf(1), Buffer.alloc(51 * 1024 * 1024, 0x20)]),
  );
  await page.locator('input[type="file"]').setInputFiles(file);
  await expect(page.getByText(words.upload.tooLarge(50))).toBeVisible();
  await expect(page.getByTestId('file-meta')).toHaveCount(0);
  // 안내 글의 한도와 같은 수(한 상수)
  await expect(page.getByText(words.upload.formats(300, 50))).toBeVisible();
});

test('GW-02 쪽 썸네일(GP3 SC5): 그림은 PDF 쪽 비율 그대로(±1%) 칸 폭을 채우고, 칠한 쪽은 종이째 파트 바탕', async ({
  page,
}) => {
  // 1440 폭: 칸(약 107)이 그림 본래 폭(595pt × 0.2 = 119)보다 좁다 — 옛 꼴은 여기서 폭만 줄어 가로로 약 19% 눌렸다.
  await page.setViewportSize({ width: 1440, height: 900 });
  const { errors } = await open(page, '/greenwash/new');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await thumbs(page).nth(3).click();
  await expect(thumbs(page).nth(3)).toHaveAttribute('data-parts', 'ceo');
  const measure = (index: number) =>
    thumbs(page)
      .nth(index)
      .evaluate((button) => {
        const frame = button.querySelector<HTMLElement>('[data-thumb-frame]')!;
        const canvas = frame.querySelector('canvas')!;
        const drawn = canvas.getBoundingClientRect();
        return {
          ratio: drawn.width / drawn.height,
          cell: button.getBoundingClientRect().width,
          frame: frame.getBoundingClientRect().width,
          frameInner: frame.clientWidth,
          drawn: drawn.width,
          natural: canvas.width,
          frameBackground: getComputedStyle(frame).backgroundColor,
          blend: getComputedStyle(canvas).mixBlendMode,
        };
      });
  const pageRatio = 595 / 842;
  for (const index of [0, 3]) {
    const look = await measure(index);
    // 그림이 줄어든 자리에서 잰다(빈 검사가 아니다)
    expect(look.natural).toBeGreaterThan(look.cell);
    expect(Math.abs(look.ratio / pageRatio - 1)).toBeLessThanOrEqual(0.01);
    // 종이 = 칸 폭(시안 .g-th .pg width 100%)
    expect(Math.abs(look.frame - look.cell)).toBeLessThanOrEqual(1);
    // 그림 = 틀 안쪽(틀 안쪽 여백이 되살아나 종이와 틀 사이에 띠가 생기면 빨강)
    expect(Math.abs(look.drawn - look.frameInner)).toBeLessThanOrEqual(1);
  }
  const plain = await measure(0);
  const painted = await measure(3);
  expect(plain.frameBackground).toBe('rgb(255, 255, 255)');
  expect(painted.frameBackground).not.toBe('rgb(255, 255, 255)');
  expect(painted.blend).toBe('multiply');
  expect(errors).toEqual([]);
});

test('GP3 시안 값: 작은 회색 글 400 · 안 고른 파트 칩 틀(대상 단어 칩은 「3. 점검 설정」 카드와 함께 지움 — sid:MARC-ENT-603) · 목록 「–」 색 · 소개 등급 줄 73 · 결과 수 카드 안쪽 24', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const style = (selector: string) =>
    page
      .locator(selector)
      .first()
      .evaluate((node) => {
        const css = getComputedStyle(node);
        return {
          weight: css.fontWeight,
          size: css.fontSize,
          color: css.color,
          background: css.backgroundColor,
          border: `${css.borderTopWidth} ${css.borderTopColor}`,
          padding: css.padding,
          radius: css.borderRadius,
          height: node.getBoundingClientRect().height,
        };
      });
  const tertiary = 'rgb(111, 119, 129)';

  // GW-02 새 점검(SC1·SC4·SC6·SC8)
  await open(page, '/greenwash/new');
  await upload(page, '목-보고서-60쪽.pdf', 60);
  await expect(page.getByTestId('file-meta')).toBeVisible();
  expect(await style('[data-testid="file-meta"]')).toMatchObject({
    weight: '400',
    color: tertiary,
  });
  expect(await style('[data-part-key][aria-checked="false"]')).toMatchObject({
    border: '1px rgb(209, 213, 217)',
    padding: '0px 14px',
  });
  // 대상 단어 칩은 「3. 점검 설정」 카드와 함께 지웠다(시안 댓글 — sid:MARC-ENT-603)
  await expect(page.locator('[data-term]')).toHaveCount(0);

  // GW-02a 글자 없는 PDF: 파일 꼬리도 회색(경고는 아래 상자)
  await open(page, '/greenwash/new');
  await page.locator('input[type="file"]').setInputFiles({
    name: '목-스캔-24쪽.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from(
      writePdf(
        Array.from({ length: 24 }, () => ({
          width: 595,
          height: 842,
          rotate: 0,
          marks: [],
          texts: [],
          tables: [],
        })),
      ),
    ),
  });
  await expect(page.getByTestId('no-text')).toBeVisible();
  expect(await style('[data-testid="file-meta"]')).toMatchObject({
    weight: '400',
    color: tertiary,
  });

  // GW-01 목록(SC1 「점검 안내」 · SC3 빈 칸)
  await open(page, '/greenwash');
  await expect(page.getByRole('link', { name: list.introLink })).toBeVisible();
  expect(await style('a[href="/greenwash/intro"]')).toMatchObject({
    weight: '400',
  });
  const dash = page.locator('tbody td span', { hasText: list.none }).first();
  await expect(dash).toBeVisible();
  expect(await dash.evaluate((node) => getComputedStyle(node).color)).toBe(
    tertiary,
  );

  // GW-00 소개(SC2): 줄 높이 56 + 위아래 8 → 73
  await open(page, '/greenwash/intro');
  await expect(
    page.locator('[data-screen="intro"] tbody td').first(),
  ).toBeVisible();
  expect(await style('[data-screen="intro"] tbody td')).toMatchObject({
    padding: '8px 16px',
    height: 73,
  });

  // GW-04 결과(SC11 · SC1)
  await open(page, '/greenwash/runs/run-101/result');
  await expect(page.getByTestId('stat-total')).toBeVisible();
  expect(await style('[data-testid="stat-total"] > *')).toMatchObject({
    padding: '24px',
  });
  expect(await style('[data-testid="parts-note"]')).toMatchObject({
    weight: '400',
    color: tertiary,
  });
});

// ── 밴드 GP4: 사용자 확인 버그 둘(10-25 USR2) ──

/** GP4_SHOTS 를 주면 그 폴더에 화면을 떠 둔다(보고의 전·후 그림 — 단언에는 쓰지 않는다). */
async function gp4Shot(
  page: Page,
  name: string,
  clip?: { x: number; y: number; width: number; height: number },
) {
  const dir = process.env.GP4_SHOTS;
  if (!dir) return;
  // 끝이 있는 움직임(떠오름 등)이 다 끝난 뒤에 뜬다
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every(
        (animation) =>
          animation.playState !== 'running' ||
          animation.effect?.getTiming().iterations === Infinity,
      ),
  );
  await page.screenshot({ path: `${dir}/${name}.png`, clip });
}

/** 쪽마다 문장 상자 자리(목 결과의 [72, 120 + i·40, 500, 134 + i·40] — High i=0 · Low i=2)에 진한 글자를 둔 PDF(지어낸 글). */
function pdfWithInk(pageCount: number): Buffer {
  const pages: SamplePage[] = Array.from({ length: pageCount }, () => ({
    width: 595,
    height: 842,
    rotate: 0,
    marks: [],
    texts: [120, 160, 200].map((top) => ({
      x: 72,
      top,
      size: 12,
      str: 'MMMMMMMMMM',
    })),
    tables: [],
  }));
  return Buffer.from(writePdf(pages));
}

/** 새 점검(&autofinish=1, 목 이름 표의 60쪽 파일) → CEO 3쪽만 → 시작. 끝난 GW-03 에서 멈춘다. */
async function gp4Finished(page: Page, pdf: Buffer) {
  const { errors } = await open(page, '/greenwash/new?autofinish=1');
  await page.locator('input[type="file"]').setInputFiles({
    name: '목-보고서-60쪽.pdf',
    mimeType: 'application/pdf',
    buffer: pdf,
  });
  await expect(doneCanvases(page)).toHaveCount(40, { timeout: 20_000 });
  await page.getByLabel(words.parts.names.ceo, { exact: true }).fill('3');
  await page.getByRole('button', { name: words.start }).click();
  await expect(page.locator('[data-screen="status"]')).toHaveAttribute(
    'data-run-state',
    'done',
  );
  return errors;
}

test('GP4 버그 1: 끝난 GW-03 은 STEP 띠 아래에 끝남 카드(「점검이 끝났어요」 · 「… 끝남 · n문장을 찾았어요」 · [결과 보기]) — 머리에는 [목록으로]만, 저절로 넘기지 않고, [결과 보기] → 결과 요약', async ({
  page,
}) => {
  const errors = await gp4Finished(page, pdfOf(60));
  const card = page.getByTestId('done-card');
  await expect(card).toBeVisible();
  await expect(
    card.getByText(status.title.done, { exact: true }),
  ).toBeVisible();
  await expect(card.getByTestId('done-meta')).toHaveText(
    /^\d{4}-\d{2}-\d{2} \d{2}:\d{2} 끝남 · 3개의 그린워싱 리스크 문장을 찾았어요$/,
  );
  // 시안 .g-small = 400 12px text-tertiary(검증 B1)
  await expect(card.getByTestId('done-meta')).toHaveCSS('font-weight', '400');
  // 카드는 STEP 띠 아래(빈 화면이 아니다) — 그린 높이가 있다
  const flow = (await page
    .getByRole('list', { name: GW_TEXT.stepFlow.label })
    .boundingBox())!;
  const box = (await card.boundingBox())!;
  expect(box.y).toBeGreaterThanOrEqual(flow.y + flow.height);
  expect(box.height).toBeGreaterThan(40);
  // [결과 보기]는 카드 한 자리
  const view = page.getByRole('button', { name: status.viewResult });
  await expect(view).toHaveCount(1);
  await expect(
    card.getByRole('button', { name: status.viewResult }),
  ).toBeVisible();
  // 인식 실패 페이지가 없는 끝남은 파랑 줄 없음
  await expect(page.getByTestId('missed-pages')).toHaveCount(0);
  await gp4Shot(page, 'status-done');
  expect(screenOf(page)).toBe('status');
  await view.click();
  await expect(page.locator('[data-screen="result"]')).toHaveAttribute(
    'data-result-state',
    'ready',
  );
  expect(errors).toEqual([]);
});

test('GP4 버그 1: 인식 실패 페이지가 있는 끝남(run-101) — 끝남 카드 안에 「인식 실패 페이지 1개 (7페이지)」과 [결과 보기]', async ({
  page,
}) => {
  const { errors } = await open(page, '/greenwash/runs/run-101');
  const card = page.getByTestId('done-card');
  await expect(card).toBeVisible();
  await expect(
    card.getByText(status.title.done, { exact: true }),
  ).toBeVisible();
  await expect(card.getByTestId('missed-pages')).toHaveText(
    status.failedPages([7]),
  );
  await expect(
    card.getByRole('button', { name: status.viewResult }),
  ).toBeVisible();
  await gp4Shot(page, 'status-done-missed');
  await card.getByRole('button', { name: status.viewResult }).click();
  await expect(page.locator('[data-screen="result"]')).toHaveAttribute(
    'data-result-state',
    'ready',
  );
  expect(errors).toEqual([]);
});

/** PNG 한 장의 픽셀 밝기(0~255, 행 차례) — 브라우저에서 풀어 읽는다(새 의존 0). */
async function lumaOf(page: Page, png: Buffer) {
  return page.evaluate(async (b64) => {
    const blob = await (await fetch(`data:image/png;base64,${b64}`)).blob();
    const bitmap = await createImageBitmap(blob);
    const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    const context = canvas.getContext('2d')!;
    context.drawImage(bitmap, 0, 0);
    const { data } = context.getImageData(0, 0, bitmap.width, bitmap.height);
    const out: number[] = [];
    for (let i = 0; i < data.length; i += 4)
      out.push(0.299 * data[i]! + 0.587 * data[i + 1]! + 0.114 * data[i + 2]!);
    return out;
  }, png.toString('base64'));
}

test('GP4 버그 2: 고른 문장 상자(High · Low)의 바탕은 곱하기로 섞여 PDF 글자가 비친다 — 상자 안 글자 픽셀이 바탕만 칠한 자리보다 100 넘게 어둡다', async ({
  page,
}) => {
  const errors = await gp4Finished(page, pdfWithInk(60));
  await page.getByRole('button', { name: status.viewResult }).click();
  await page.getByRole('button', { name: result.continueReview }).click();
  const pane = page.getByTestId('review-page');
  await expect(pane.locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
    { timeout: 20_000 },
  );
  // 목 결과 차례: 0 High(상자) · 1 Mid(위치 없음) · 2 Low(상자)
  for (const [index, level] of [
    [0, 'High'],
    [2, 'Low'],
  ] as const) {
    await sentence(page, index).click();
    const highlight = pane.getByTestId('highlight');
    await expect(highlight).toHaveAttribute('data-level', level);
    // 움직임(gw-m-mark 떠오름·빛남)이 다 끝난 뒤에 잰다
    await expect
      .poll(() =>
        highlight.evaluate(
          (node) =>
            node
              .getAnimations({ subtree: true })
              .filter((animation) => animation.playState === 'running').length,
        ),
      )
      .toBe(0);
    const box = (await highlight.boundingBox())!;
    // 글자 칸(왼쪽 100px — 「MMMMMMMMMM」)과 바탕만 칠한 칸(오른쪽, 글자 없음). 위아래 2px 는 뺀다
    const ink = await lumaOf(
      page,
      await page.screenshot({
        clip: { x: box.x + 2, y: box.y + 2, width: 96, height: box.height - 4 },
      }),
    );
    const fill = await lumaOf(
      page,
      await page.screenshot({
        clip: {
          x: box.x + 250,
          y: box.y + 2,
          width: 100,
          height: box.height - 4,
        },
      }),
    );
    const fillMean = fill.reduce((a, b) => a + b, 0) / fill.length;
    const inkMin = Math.min(...ink);
    // 바탕은 칠해져 있다(흰 종이 255 보다 어둡다 — 「subtle 채움」을 걷어 내지 않았다)
    expect(fillMean).toBeLessThan(250);
    // 글자 자리 어두움이 남는다(덮이면 글자 칸도 바탕색 그대로라 차이가 0 에 가깝다)
    expect(inkMin).toBeLessThan(fillMean - 100);
    await gp4Shot(page, `review-${level}`, {
      x: box.x - 24,
      y: box.y - 40,
      width: Math.min(box.width + 48, 520),
      height: box.height + 64,
    });
  }
  expect(errors).toEqual([]);
});

test('GW-02 보고연도 셀렉터(AV2 디자인 대조 R1): 폭 140 · 도움 글이 오른쪽이라 줄 높이 64', async ({
  page,
}) => {
  await open(page, '/greenwash/new');
  const select = page.getByRole('combobox', { name: words.year.label });
  await expect(select).toBeVisible();
  expect((await select.boundingBox())!.width).toBe(140);
  const row = select.locator(
    'xpath=ancestor::div[contains(@class, "min-h-16")][1]',
  );
  expect((await row.boundingBox())!.height).toBe(64);
});

// ── 밴드 GP5(sid:MARC-TICK-290 · sid:MARC-ISSUE-344 R2): 검토 줄 「확정됨 · 바꿀 수 없음」은 시안 굵기 500(pre-caption-02) ──

test('GW-05c(run-105 확정): 검토 줄 「확정됨 · 바꿀 수 없음」 12 · 500(옛 400)', async ({
  page,
}) => {
  await open(page, '/greenwash/runs/run-105/review');
  const locked = page.getByTestId('review-detail').getByText(review.locked);
  await expect(locked).toBeVisible();
  await expect(locked).toHaveCSS('font-weight', '500');
  await expect(locked).toHaveCSS('font-size', '12px');
});

// ── 밴드 GP6(sid:MARC-TICK-300 · sid:MARC-ISSUE-344 SB4): 목록 검색 칸은 시안 폭 300(옛 w-64 = 256) ──

test('GW-01 목록: 검색 칸 폭 300', async ({ page }) => {
  await open(page, '/greenwash');
  const search = page.getByRole('textbox', { name: list.searchLabel });
  await expect(search).toBeVisible();
  // 폭은 겉(SearchField 의 div)에 준다 — 입력은 w-full
  const field = search.locator('xpath=..');
  const box = (await field.boundingBox())!;
  await gp4Shot(page, 'list-search', {
    x: box.x - 24,
    y: box.y - 24,
    width: Math.min(box.width + 360, 900),
    height: box.height + 48,
  });
  expect(box.width).toBe(300);
});

// 밴드 GRJ1 ③(GW-05 r4 — 결정 MARC-ENT-617): 목 저장소의 실호출 씨앗(run-106)에서 근거 칩 하나를 지우고 [재판단] → 도는 중 →
// 끝남(「재판단 · 때 · 사람」·목록 「재판단」 딱지). 목의 재판단은 만든 뒤 검토 읽기 둘째 번(다시 읽기 간격 뒤)에 끝난다.
test('GW-05 r4: 근거 칩 [지우기] → [재판단] → 도는 중 → 끝남(재판단 줄·첫 판단 접힘·목록 딱지). 콘솔 오류·404 0', async ({
  page,
}) => {
  const rejudge = GW_TEXT.reviewScreen.rejudge;
  const { errors, missing } = await open(
    page,
    '/greenwash/runs/run-106/review',
  );
  const detail = page.getByTestId('review-detail');
  await expect(detail).toBeVisible();
  const evidence = detail.getByTestId('evidence');
  // 칩이 있는 첫 문장을 고른다
  const rows = page.getByTestId('sentence-list').getByRole('button');
  for (let i = 0; i < (await rows.count()); i++) {
    await rows.nth(i).click();
    if ((await evidence.locator('[data-chip]').count()) > 0) break;
  }
  const button = detail.getByTestId('rejudge');
  await expect(button).toBeDisabled();
  await evidence.getByTestId('evidence-edit').click();
  await evidence
    .locator('[data-chip="0"]')
    .getByRole('button', { name: rejudge.remove })
    .click();
  await expect(evidence.locator('[data-chip="0"]')).toHaveAttribute(
    'data-removed',
    'true',
  );
  await expect(detail.getByTestId('evidence-changed')).toHaveText(
    rejudge.changed(1, 0),
  );
  await expect(button).toBeEnabled();
  await button.click();
  await expect(detail.getByTestId('rejudge-running')).toHaveText(
    rejudge.running,
  );
  await expect(detail.getByTestId('rejudge-judged')).toBeVisible({
    timeout: 10_000,
  });
  await expect(detail.getByTestId('first-judgment')).toBeVisible();
  await expect(
    page.locator('[data-testid="sentence-list"] [data-rejudged]'),
  ).toHaveCount(1);
  expect(errors).toEqual([]);
  expect(missing).toEqual([]);
});
