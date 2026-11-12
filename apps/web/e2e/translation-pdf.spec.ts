// 영문번역 PDF 길을 빌드 결과에서(밴드 TRW6 ② S4a). 서버는 e2e/translation-pdf-server.ts 의 흉내(page.route, TRS3 §1 꼴).
// 합성 PDF(3쪽)는 tools/pdf-writer.ts 의 writePdf 로 메모리에서 짓는다(디스크에 .pdf 0).
//   목록 [PDF로 새 번역] → /translation/pdf/new → PDF 올림 → confirm 쪽 수 3 으로 그리드(pages 경로 0) → 일반 1~3 → [번역 시작] →
//   POST /runs 본문 flowId "translation.pdf@158" · Idempotency-Key → 여기서 멈춤(묶음 읽기는 ④ — 발주서 ★④).
// PDF 보기(③): 끝난 PDF 실행 30 의 보기 주소로 바로 → 쪽 캔버스 그려짐 · data-box 수 == member 수 + bbox 있는 칸 수(표 테두리·묶음은 하나) ·
//   상자 누름 → 짝 칸 원문·번역 · [← 결과 요약] → 묶음 화면 그 파트 탭(?part=story).
// 묶음 길(④ S4b — TRS3 병합 뒤): [번역 시작] → 묶음 화면 「PDF 읽는 중」 → 끝남(요약) → [PDF로 보기] → data-box 수 · 상자 → 짝 · [B] · 다음 페이지 ·
//   [← 결과 요약] → 검수 이슈 「자리」 → 그 상자 고름 → 목록 「PDF」 1. 실패 파트 [다시 실행] → 둘째 POST /runs flowId·옵션 같음·새 launchKey(E1) ·
//   no_text_layer 실패 칸.
// 스크롤·움직임(밴드 TRW7 ② S3 — 긴 layout 12쪽, 1280×800·1440×900): sticky 쪽 칸·짝 칸 · 고른 상자 → 쪽 칸 안 · 쪽 넘김 → 쪽 칸 맨 위 ·
//   이슈 줄 → 밑줄 · [← 결과 요약] → 눌렀던 줄 강조 · 움직임 두 갈래(no-preference / reduce).
// TRW6_SHOTS 가 있으면 그 폴더에 1440 입력·보기 화면 그림. TRW7_SHOTS 가 있으면 보기 1440·1280(밴드 TRW7 ①).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { TR_TEXT } from '../src/entities/translation/config/text.ts';
import { writePdf } from '../tools/pdf-writer.ts';
import { signIn } from './session.ts';
import {
  LONG_PAGES,
  PDF_DOC_ID,
  PDF_RUN_ID,
  fakeTranslationPdfApi,
  layoutOf,
  longLayout,
  pdfLayout,
  wideTableLayout,
} from './translation-pdf-server.ts';

const words = TR_TEXT.newTranslation;
const PDF = Buffer.from(
  writePdf(
    [1, 2, 3].map((n) => ({
      width: 595,
      height: 842,
      rotate: 0 as const,
      marks: [],
      texts: [{ x: 72, top: 72, size: 18, str: `Made-up page ${n}` }],
      tables: [],
    })),
  ),
);
const XLSX = Buffer.from([80, 75, 3, 4, 1, 2]);

test('TR-01 [PDF로 새 번역] → TR-P02: PDF 3쪽 올림 → 그리드 3 → 일반 1~3 → POST /runs 본문 flowId pdf · Idempotency-Key', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const api = await fakeTranslationPdfApi(page);
  await signIn(page);
  await page.goto('/translation');

  await page.getByTestId('new-pdf').click();
  await expect(page).toHaveURL(/\/translation\/pdf\/new$/);
  await expect(
    page.getByRole('heading', { name: TR_TEXT.pdfNew.title }),
  ).toBeVisible();
  await expect(page.getByTestId('pdf-range-guide')).toBeVisible();

  await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
    name: 'made_up_report.pdf',
    mimeType: 'application/pdf',
    buffer: PDF,
  });
  await expect(page.getByTestId('file-meta')).toContainText('총 3페이지');
  await expect(page.getByTestId('page-grid')).toBeVisible();
  await expect(page.locator('[data-page]')).toHaveCount(3);
  await expect(page.getByTestId('pdf-no-text')).toHaveCount(0);
  expect(api.keys()).not.toContain('GET /translation/documents/12/pages');

  await page.locator('[data-part-field="general"]').fill('1~3');
  await page
    .getByTestId('glossary-client')
    .locator('input[type="file"]')
    .setInputFiles({
      name: 'glossary.xlsx',
      mimeType:
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      buffer: XLSX,
    });
  await expect(
    page.getByTestId('glossary-client').getByText(TR_TEXT.glossary.pairs(2)),
  ).toBeVisible();
  await page.getByLabel(words.company.name).fill('Sample Corp');
  await page.getByLabel(words.company.subject).fill('virtual services');
  await page.getByLabel(words.company.standards).fill('GRI');
  await expect(page.getByTestId('preflight')).toContainText(
    TR_TEXT.pdfNew.preflight.headerFooterValue,
  );
  await expect(page.getByTestId('start-blocked')).toHaveCount(0);

  const dir = process.env.TRW6_SHOTS;
  if (dir)
    await page.screenshot({
      path: `${dir}/trw6-p02-input.png`,
      fullPage: true,
    });

  await page.getByTestId('start').click();
  await expect.poll(() => api.runCalls().length).toBe(1);
  const [call] = api.runCalls();
  const body = call!.body as {
    module: string;
    flowId?: string;
    documentId: number;
    options: { part: string; pages: { start: number; end: number } };
  };
  expect(body.flowId).toBe('translation.pdf@158');
  expect(body.module).toBe('translation');
  expect(body.documentId).toBe(12);
  expect(body.options.part).toBe('general');
  expect(body.options.pages).toEqual({ start: 1, end: 3 });
  expect(call!.idempotencyKey).toMatch(/^[0-9a-f-]{36}$/);
  expect(api.keys()).not.toContain('GET /translation/documents/12/pages');
});

// 검증 권고 R6: confirm 의 hasText false 꼴 — 안내 한 줄, 시작은 막지 않음(W4).
test('TR-P02 hasText false → 「텍스트가 없는 PDF」 안내 한 줄', async ({
  page,
}) => {
  await fakeTranslationPdfApi(page, { hasText: false });
  await signIn(page);
  await page.goto('/translation/pdf/new');
  await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
    name: 'made_up_scan.pdf',
    mimeType: 'application/pdf',
    buffer: PDF,
  });
  await expect(page.getByTestId('pdf-no-text')).toHaveText(
    TR_TEXT.pdfNew.upload.noText,
  );
  await expect(page.getByTestId('page-grid')).toBeVisible();
});

test('TR-P05 PDF 보기: 쪽 캔버스 · 상자 수 == member + bbox 칸 · 누름 → 짝 · [← 결과 요약] → 그 파트 탭', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const layout = pdfLayout();
  const members = layout.units.reduce(
    (sum, unit) => sum + unit.members.length,
    0,
  );
  const cells = layout.units
    .flatMap((unit) => unit.cells ?? [])
    .filter((cell) => cell.bbox !== null).length;
  // block member 둘 · 표 테두리 하나(member 하나) · 꼬리말 하나 + bbox 있는 칸 하나.
  expect(members + cells).toBe(5);
  await fakeTranslationPdfApi(page, {
    done: { pdf: PDF, layout, result: true },
  });
  await signIn(page);
  await page.goto(
    `/translation/documents/${PDF_DOC_ID}/batches/b-1/pdf/${PDF_RUN_ID}`,
  );
  await expect(page.locator('[data-screen="translation-pdf"]')).toBeVisible();
  await expect(
    page.locator('[data-testid="pdf-page"] canvas[data-render-state="done"]'),
  ).toBeVisible();
  await expect(page.locator('[data-box]')).toHaveCount(members + cells);

  await page.locator('[data-box="p1-b2"]').click();
  await expect(page.getByTestId('pdf-pair-source')).toHaveText(
    '지어낸 회사는 2030년까지 배출을 줄인다',
  );
  await expect(page.getByTestId('pdf-pair-translation')).toHaveText(
    'By 2030, Made-up Co. cuts',
  );
  await expect(page.locator('[data-box="p1-b2"]')).toHaveAttribute(
    'data-selected',
    'true',
  );

  // TRW7 ① — 판 v182 TR-P05 꼴: 범례 줄 · 고른 짝 번역에 이슈 밑줄 · 표 테두리 짝은 표로.
  await expect(page.getByTestId('pdf-legend')).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator('[data-testid="pdf-pair-translation"] mark[data-mark]')
        .count(),
    )
    .toBeGreaterThanOrEqual(1);
  const shots = process.env.TRW7_SHOTS;
  if (shots) {
    await page.screenshot({
      path: `${shots}/trw7-p05-1440.png`,
      fullPage: true,
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.screenshot({
      path: `${shots}/trw7-p05-1280.png`,
      fullPage: true,
    });
    await page.setViewportSize({ width: 1440, height: 900 });
  }
  // TRW7 ③b-2(sid:MARC-ENT-488): 칸을 맞춘 표는 짝 하나 — 원문·번역 격자 둘(같은 행·열), 칸 상자 누름 → 두 격자의 같은 칸.
  await page.locator('[data-box="p1-t1#cell"]').click();
  const grids = [
    page.getByTestId('pdf-pair-source-grid'),
    page.getByTestId('pdf-pair-translation-grid'),
  ];
  for (const grid of grids) {
    await expect(grid).toBeVisible();
    await expect(grid.locator('td[data-on]')).toHaveCount(0);
  }
  expect(await grids[0]!.locator('td').count()).toBe(
    await grids[1]!.locator('td').count(),
  );
  await page.locator('[data-box="p1-t1:r0c0"]').click();
  for (const grid of grids)
    await expect(grid.locator('td[data-on]')).toHaveAttribute(
      'data-cell',
      '0:0',
    );
  await expect(page.locator('[data-box][data-selected]')).toHaveCount(1);

  const dir = process.env.TRW6_SHOTS;
  if (dir)
    await page.screenshot({
      path: `${dir}/trw6-p05-view.png`,
      fullPage: true,
    });

  await page.getByTestId('pdf-back').click();
  await expect(page).toHaveURL(
    new RegExp(
      `/translation/documents/${PDF_DOC_ID}/batches/b-1\\?part=story$`,
    ),
  );
});

// ── 밴드 TRW6 ④ S4b: 묶음 화면을 지나는 길(TRS3 두 칸 — inputKind·latest.flowId) ──

const BATCH_URL =
  /\/translation\/documents\/12\/batches\/[0-9a-f-]{36}(\?.*)?$/;

/** 목록 → [PDF로 새 번역] → 3쪽 PDF 올림 → 일반 1~3 → (견주기) → [번역 시작] → 묶음 화면. */
async function startPdf(
  page: Page,
  compare: boolean,
  ranges: Partial<Record<'story' | 'general', string>> = { general: '1~3' },
) {
  await page.goto('/translation');
  await page.getByTestId('new-pdf').click();
  await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
    name: 'made_up_report.pdf',
    mimeType: 'application/pdf',
    buffer: PDF,
  });
  await expect(page.locator('[data-page]')).toHaveCount(3);
  for (const [part, range] of Object.entries(ranges))
    await page.locator(`[data-part-field="${part}"]`).fill(range);
  await page
    .getByTestId('glossary-client')
    .locator('input[type="file"]')
    .setInputFiles({
      name: 'glossary.xlsx',
      mimeType:
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      buffer: XLSX,
    });
  await expect(
    page.getByTestId('glossary-client').getByText(TR_TEXT.glossary.pairs(2)),
  ).toBeVisible();
  await page.getByLabel(words.company.name).fill('Sample Corp');
  await page.getByLabel(words.company.subject).fill('virtual services');
  await page.getByLabel(words.company.standards).fill('GRI');
  if (compare) await page.getByRole('radio', { name: words.style.AB }).check();
  await page.getByTestId('start').click();
  await expect(page).toHaveURL(BATCH_URL);
}

test('S4b: [번역 시작] → 「PDF 읽는 중」 → 요약 [PDF로 보기] → 상자 수·짝·[B]·다음 페이지 → [← 결과 요약] → 「자리」 → 그 상자 · 목록 「PDF」', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const api = await fakeTranslationPdfApi(page);
  await signIn(page);
  await startPdf(page, true);
  const [first] = api.runCalls();
  expect((first!.body as { flowId?: string }).flowId).toBe(
    'translation.pdf@158',
  );

  // 처리 중: PDF 흐름의 준비 단계 = 「PDF 읽는 중」.
  await expect(page.getByTestId('stage-card')).toContainText(
    TR_TEXT.stage.prepareNowPdf,
  );
  api.setRun(20, 'done');

  // 끝남(① 요약): [PDF로 보기] · 검수 이슈 「자리」(1·2쪽 붙음, 3쪽 페이지만).
  await expect(page.getByTestId('open-pdf')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId('qa-issue-place')).toHaveCount(3);
  await page.getByTestId('open-pdf').click();
  await expect(page).toHaveURL(/\/batches\/[0-9a-f-]{36}\/pdf\/20$/);

  // ② 보기: 1쪽 상자 수 == member 수 + bbox 있는 칸 수(묶음·표 테두리는 하나).
  const one = pdfLayout(1);
  const boxes =
    one.units.reduce((sum, unit) => sum + unit.members.length, 0) +
    one.units
      .flatMap((unit) => unit.cells ?? [])
      .filter((cell) => cell.bbox !== null).length;
  await expect(
    page.locator('[data-testid="pdf-page"] canvas[data-render-state="done"]'),
  ).toBeVisible();
  await expect(page.locator('[data-box]')).toHaveCount(boxes);
  await page.locator('[data-box="p1-b2"]').click();
  await expect(page.getByTestId('pdf-pair-translation')).toHaveText(
    'By 2030, Made-up Co. cuts',
  );
  // [B] → 그 문체 단위로 다시 셈 → 다시 고르면 B 글. 항목을 고른 채라 상세 「번역」 머리 줄 전환(밴드 TRW8 ④ 개정 — sid:MARC-ENT-502).
  await page
    .getByTestId('pdf-style-switch')
    .getByRole('tab', {
      name: TR_TEXT.pdfView.pair.styles.one('B'),
      exact: true,
    })
    .click();
  await page.locator('[data-box="p1-b2"]').click();
  await expect(page.getByTestId('pdf-pair-translation')).toHaveText(
    layoutOf(['A', 'B'], 3).variants[1]!.units[0]!.translations![1]!,
  );
  // 다음 페이지 → 2쪽 상자.
  await page.getByRole('button', { name: TR_TEXT.pdfView.next }).click();
  await expect(page.getByTestId('pdf-page-of')).toHaveText(
    TR_TEXT.pdfView.pageOf(2, 2),
  );
  await expect(page.locator('[data-box="p2-b2"]')).toBeVisible();

  const dir = process.env.TRW6_SHOTS;
  if (dir)
    await page.screenshot({
      path: `${dir}/trw6-s4b-view.png`,
      fullPage: true,
    });

  // [← 결과 요약] → 묶음 화면 그 파트 탭 → 검수 이슈 「자리」(1쪽) → ② 의 그 상자 고름.
  await page.getByTestId('pdf-back').click();
  await expect(page).toHaveURL(/\?part=general$/);
  await page.getByTestId('qa-issue-place').first().click();
  await expect(page).toHaveURL(/\/pdf\/20$/);
  await expect(page.getByTestId('pdf-from-table')).toBeVisible();
  await expect(page.locator('[data-box="p1-b2"]')).toHaveAttribute(
    'data-selected',
    'true',
  );

  // 목록: 그 줄 파일명 앞 「PDF」 하나.
  await page.goto('/translation');
  await expect(page.getByTestId('batch-pdf-mark')).toHaveCount(1);
  await expect(page.getByTestId('batch-pdf-mark')).toHaveText(
    TR_TEXT.list.pdfMark,
  );
});

test('S4b E1: PDF 파트 서버 오류 → 회색 한 줄 · [다시 실행] → 둘째 POST /runs flowId·옵션 같음·새 launchKey', async ({
  page,
}) => {
  const api = await fakeTranslationPdfApi(page);
  await signIn(page);
  await startPdf(page, false);
  api.setRun(20, { failed: 'step_error' });
  await expect(page.getByTestId('part-failure-pdf-note')).toHaveText(
    TR_TEXT.failure.pdf.retryNote,
    { timeout: 10_000 },
  );
  await page.getByRole('button', { name: TR_TEXT.failure.retrySingle }).click();
  await expect.poll(() => api.runCalls().length).toBe(2);
  const [a, b] = api
    .runCalls()
    .map(
      (call) =>
        call.body as { flowId?: string; launchKey: string; options: unknown },
    );
  expect(b!.flowId).toBe('translation.pdf@158');
  expect(JSON.stringify(b!.options)).toBe(JSON.stringify(a!.options));
  expect(b!.launchKey).not.toBe(a!.launchKey);
  expect(api.runCalls()[1]!.idempotencyKey).not.toBe(
    api.runCalls()[0]!.idempotencyKey,
  );
  await expect(page.getByTestId('stage-card')).toContainText(
    TR_TEXT.stage.prepareNowPdf,
    { timeout: 10_000 },
  );
});

test('S4b: no_text_layer 실패 칸 → 텍스트 없는 PDF 한 줄 · 다시 단추 0 · 서버 문장 0', async ({
  page,
}) => {
  const api = await fakeTranslationPdfApi(page);
  await signIn(page);
  await startPdf(page, false);
  api.setRun(20, { failed: 'no_text_layer' });
  await expect(page.getByTestId('part-failure')).toContainText(
    TR_TEXT.failure.pdf.noText,
    { timeout: 10_000 },
  );
  await expect(
    page.getByRole('button', { name: TR_TEXT.failure.retrySingle }),
  ).toHaveCount(0);
  await expect(page.getByTestId('part-failure-pdf-note')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText('지어낸 실패 글');
});

// 밴드 TRW6 ⑤(6c B1): 1280 에서 쪽 그림이 짝 칸을 덮었다 — 가운데 칸 폭에 맞춰 쪽 그림·상자를 같은 배율로 줄인다.
for (const width of [1280, 1440])
  test(`TR-P05 ${width}: 쪽 그림·상자가 가운데 칸 안 · 짝 칸과 겹침 0 · 상자는 쪽 그림과 같은 배율`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await fakeTranslationPdfApi(page, { done: { pdf: PDF } });
    await signIn(page);
    await page.goto(
      `/translation/documents/${PDF_DOC_ID}/batches/b-1/pdf/${PDF_RUN_ID}`,
    );
    const canvas = page.locator(
      '[data-testid="pdf-page"] canvas[data-render-state="done"]',
    );
    await expect(canvas).toBeVisible();
    const pageBox = (await page.getByTestId('pdf-page').boundingBox())!;
    const frame = (await page.getByTestId('pdf-page-frame').boundingBox())!;
    const pairs = (await page.getByTestId('pdf-pairs').boundingBox())!;
    // 가운데 칸 안 · 짝 칸과 겹침 0.
    expect(pageBox.x + pageBox.width).toBeLessThanOrEqual(
      frame.x + frame.width + 0.5,
    );
    expect(pageBox.x + pageBox.width).toBeLessThanOrEqual(pairs.x);
    // 상자(p1-b2 — bbox 72,100,520,160)는 쪽 그림과 같은 배율: 폭 비 == (520−72) ÷ 595.
    const canvasBox = (await canvas.boundingBox())!;
    const box = (await page.locator('[data-box="p1-b2"]').boundingBox())!;
    expect(box.width / canvasBox.width).toBeCloseTo((520 - 72) / 595, 2);
    expect((box.x - canvasBox.x) / canvasBox.width).toBeCloseTo(72 / 595, 2);
    expect(box.x + box.width).toBeLessThanOrEqual(pairs.x);
    const dir = process.env.TRW6_SHOTS;
    if (dir)
      await page.screenshot({
        path: `${dir}/trw6-p05-${width}.png`,
        fullPage: true,
      });
  });

// ── 밴드 TRW7 ② S3: 스크롤·움직임(그린워싱 GW-05 꼴 — 긴 layout) ──

const LONG_PDF = Buffer.from(
  writePdf(
    Array.from({ length: LONG_PAGES }, (_, n) => ({
      width: 595,
      height: 842,
      rotate: 0 as const,
      marks: [],
      texts: [{ x: 72, top: 72, size: 18, str: `Made-up page ${n + 1}` }],
      tables: [],
    })),
  ),
);

/** 요소의 상자가 뷰포트 안에 다 들어오는가(그린워싱 e2e/greenwash-server.spec.ts:707 inViewport 를 옮겨 적음 — 그 땅은 가져오지 않는다). */
async function inViewport(page: Page, locator: ReturnType<Page['locator']>) {
  const box = (await locator.boundingBox())!;
  const view = page.viewportSize()!;
  return (
    box.y >= -0.5 &&
    box.x >= -0.5 &&
    box.y + box.height <= view.height + 0.5 &&
    box.x + box.width <= view.width + 0.5
  );
}

/** inner 가 outer 안에 다 들어오는가(±0.5 — 같은 파일 :721 inside 를 옮겨 적음). */
async function inside(
  inner: ReturnType<Page['locator']>,
  outer: ReturnType<Page['locator']>,
) {
  const a = (await inner.boundingBox())!;
  const b = (await outer.boundingBox())!;
  return (
    a.y >= b.y - 0.5 &&
    a.x >= b.x - 0.5 &&
    a.y + a.height <= b.y + b.height + 0.5 &&
    a.x + a.width <= b.x + b.width + 0.5
  );
}

/** 끝난 PDF 실행 30 의 보기(긴 layout · 결과 — 쪽마다 이슈 하나가 맨 아래 상자 b8 에 붙음). 움직임은 기본(no-preference). */
async function openLong(page: Page, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await fakeTranslationPdfApi(page, {
    done: {
      pdf: LONG_PDF,
      layout: longLayout(),
      result: true,
      pages: LONG_PAGES,
    },
  });
  await signIn(page);
  await page.goto(
    `/translation/documents/${PDF_DOC_ID}/batches/b-1/pdf/${PDF_RUN_ID}`,
  );
  await expect(
    page.locator('[data-testid="pdf-page"] canvas[data-render-state="done"]'),
  ).toBeVisible();
  await expect(page.locator('[data-box]')).toHaveCount(10);
}

const scrollTopOf = (page: Page) =>
  page.getByTestId('pdf-page-scroll').evaluate((element) => element.scrollTop);
const pageLine = (page: Page, n: number) =>
  page.locator(`nav [data-page="${n}"]`);

for (const [width, height] of [
  [1280, 800],
  [1440, 900],
] as const) {
  test(`TRW7 S3 ${width}: sticky — 쪽 목록 ${LONG_PAGES}쪽째 누름 → 창이 내려가도 쪽 칸·짝 칸·그 줄이 뷰포트 안`, async ({
    page,
  }) => {
    await openLong(page, width, height);
    for (const testId of ['pdf-page-pane', 'pdf-pairs'])
      await expect(page.getByTestId(testId)).toHaveCSS('position', 'sticky');
    // 왼쪽 쪽 목록은 창 스크롤 그대로(W4 — 검증 B2).
    await expect(
      page.locator(`nav[aria-label="${TR_TEXT.pdfView.open}"]`),
    ).not.toHaveCSS('position', 'sticky');
    await pageLine(page, LONG_PAGES).click();
    await expect(page.getByTestId('pdf-page-of')).toHaveText(
      TR_TEXT.pdfView.pageOf(LONG_PAGES, LONG_PAGES),
    );
    // 창이 정말 내려갔는지 먼저(critic b — 안 내려갔으면 sticky 를 잰 것이 아니다).
    await expect
      .poll(() => page.evaluate(() => window.scrollY))
      .toBeGreaterThan(0);
    await expect
      .poll(() => inViewport(page, page.getByTestId('pdf-page-pane')))
      .toBe(true);
    await expect
      .poll(() => inViewport(page, page.getByTestId('pdf-pairs')))
      .toBe(true);
    await expect
      .poll(() => inViewport(page, pageLine(page, LONG_PAGES)))
      .toBe(true);
  });

  test(`TRW7 S3 ${width}: 고른 상자 → 쪽 칸 안(fitInside) · 쪽 넘김 → 쪽 칸 맨 위 · 쪽 목록 지금 줄 뷰포트 안`, async ({
    page,
  }) => {
    await openLong(page, width, height);
    const scroller = page.getByTestId('pdf-page-scroll');
    const footer = page.locator('[data-box="p1-b9"]');
    // 누름은 dispatchEvent — Playwright 의 스크롤 맞춤 없이 화면(fitInside)만 칸을 움직이게.
    const windowY = () => page.evaluate(() => window.scrollY);
    const before = await windowY();
    await footer.dispatchEvent('click');
    await expect(footer).toHaveAttribute('data-selected', 'true');
    if (width === 1440)
      // 맨 아래 꼬리말 상자는 처음엔 칸 밖 — 칸이 내려가야 한다(critic a: 넘김 전 scrollTop > 0 을 먼저).
      await expect.poll(() => scrollTopOf(page)).toBeGreaterThan(0);
    else
      // 1280: 쪽 그림이 칸에 다 들어간다(넘침 0 — 맞출 것이 없다, 보고 「6c 대조에 넘길 것」).
      expect(
        await scroller.evaluate(
          (element) => element.scrollHeight - element.clientHeight,
        ),
      ).toBeLessThanOrEqual(1);
    await expect.poll(() => inside(footer, scroller)).toBe(true);
    // 칸만 움직이고 창은 그대로(W5 버린 안 — 창 전체 scrollIntoView, 검증 B2).
    expect(Math.abs((await windowY()) - before)).toBeLessThanOrEqual(0.5);

    await page
      .getByRole('button', { name: TR_TEXT.pdfView.next, exact: true })
      .click();
    await expect(page.getByTestId('pdf-page-of')).toHaveText(
      TR_TEXT.pdfView.pageOf(2, LONG_PAGES),
    );
    await expect.poll(() => scrollTopOf(page)).toBe(0);
    await expect.poll(() => inViewport(page, pageLine(page, 2))).toBe(true);
  });

  test(`TRW7 S3 ${width}: 짝 칸 이슈 줄 누름 → 그 밑줄이 짝 칸 안`, async ({
    page,
  }) => {
    await openLong(page, width, height);
    const bottom = page.locator('[data-box="p1-b8"]');
    await expect(bottom).toHaveAttribute('data-issues', '1');
    await bottom.dispatchEvent('click');
    const line = page.locator(
      '[data-testid="pdf-pair-issues"] [data-issue-line="1"] button',
    );
    await line.click();
    const mark = page.locator('[data-testid="pdf-pair"] mark[data-n="1"]');
    await expect(mark).toBeVisible();
    await expect
      .poll(() => inside(mark, page.getByTestId('pdf-pairs')))
      .toBe(true);
  });

  test(`TRW7 S3 ${width}: 움직임 — 고른 상자 gw-m-mark·짝 칸 몸 gw-m-fade, 줄인 움직임이면 none`, async ({
    page,
  }) => {
    await openLong(page, width, height);
    const animation = (selector: string) =>
      page
        .locator(selector)
        .evaluate((element) => getComputedStyle(element).animationName);
    await page.locator('[data-box="p1-b2"]').dispatchEvent('click');
    expect(
      await animation('[data-box="p1-b2"] [data-testid="pdf-box-mark"]'),
    ).toBe('gw-m-mark-in, gw-m-mark-glow');
    expect(await animation('[data-testid="pdf-pairs-body"]')).toBe('gw-m-fade');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.locator('[data-box="p1-b3"]').dispatchEvent('click');
    expect(
      await animation('[data-box="p1-b3"] [data-testid="pdf-box-mark"]'),
    ).toBe('none');
    expect(await animation('[data-testid="pdf-pairs-body"]')).toBe('none');
  });
}

test('TRW7 S3: 「자리」 → PDF 보기 → [← 결과 요약] → 눌렀던 줄이 옅은 파랑으로 남고 화면 안', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const api = await fakeTranslationPdfApi(page);
  await signIn(page);
  await startPdf(page, false);
  api.setRun(20, 'done');
  await expect(page.getByTestId('qa-issue-place')).toHaveCount(3, {
    timeout: 10_000,
  });
  await expect(page.locator('tr[data-returned]')).toHaveCount(0);
  await page.getByTestId('qa-issue-place').nth(1).click();
  await expect(page).toHaveURL(/\/pdf\/20$/);
  await expect(page.getByTestId('pdf-from-table')).toBeVisible();
  await page.getByTestId('pdf-back').click();
  const row = page.locator('[data-testid="qa-issues"] tr[data-returned]');
  await expect(row).toHaveCount(1);
  await expect(row.getByTestId('qa-issue-place')).toHaveText(
    TR_TEXT.pdfView.placeUnit(2, 2),
  );
  await expect.poll(() => inViewport(page, row)).toBe(true);
  const look = await row
    .locator('td')
    .first()
    .evaluate((cell) => {
      const style = getComputedStyle(cell);
      return { background: style.backgroundColor, shadow: style.boxShadow };
    });
  expect(look.background).not.toBe('rgba(0, 0, 0, 0)');
  expect(look.shadow).toContain('inset');
});

// ── 밴드 TRW7 ③a S4b: 요약 머리 [PDF로 보기] · [전체] 「확인할 곳」 칸 → 보기가 「확인할 곳」 거르기로 ──
test('TRW7 S4b: PDF 묶음 머리 「PDF」·[PDF로 보기] → 보기 · [전체] 「확인할 곳」 칸 → 그 쪽·거르기', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const api = await fakeTranslationPdfApi(page, {
    warnings: [{ code: 'tag_extra', page: 2, tag: null, variant: 'single' }],
  });
  await signIn(page);
  await startPdf(page, false, { story: '1~2', general: '3' });
  api.runCalls().forEach((_, n) => api.setRun(20 + n, 'done'));
  const head = page.locator('[data-screen="translation-run"] > *').first();
  await expect(head.getByTestId('run-pdf-mark')).toHaveText(
    TR_TEXT.list.pdfMark,
  );
  await expect(head.getByTestId('open-pdf')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId('open-pdf')).toHaveCount(1);
  await head.getByTestId('open-pdf').click();
  await expect(page).toHaveURL(/\/pdf\/20$/);
  await expect(page.getByTestId('pdf-page-of')).toHaveText(
    TR_TEXT.pdfView.pageOf(1, 2),
  );
  await page.getByTestId('pdf-back').click();
  await page.locator('[role="tab"][data-tab="all"]').click();
  const tile = page.locator('[data-stat="checks"]');
  await expect(tile.getByTestId('stat-value')).toHaveText('1');
  await tile.getByTestId('stat-open').click();
  await expect(page).toHaveURL(/\/pdf\/20$/);
  await expect(page.getByTestId('pdf-page-of')).toHaveText(
    TR_TEXT.pdfView.pageOf(2, 2),
  );
  await expect(
    page.getByRole('button', {
      name: TR_TEXT.pdfView.filters.checks(1),
      exact: true,
    }),
  ).toHaveAttribute('aria-pressed', 'true');
});

// ── 밴드 TRW7 ③b-1: 상자 채움 multiply(디자인 74 처방 D8) · 보기 머리 파트 탭(W8, 감독 답 Q1) ──
test('TRW7 ③b-1: 상자 채움은 칠 칸에서 multiply(고른 상자 불투명 blue-100) · 배지·빛·단추는 normal · 쪽 자리 tertiary·쪽 그림 그림자', async ({
  page,
}) => {
  await openLong(page, 1440, 900);
  const picked = page.locator('[data-box="p1-b8"]');
  await expect(picked.getByTestId('pdf-box-badge')).toBeVisible();
  await picked.dispatchEvent('click');
  await expect(picked).toHaveAttribute('data-selected', 'true');
  const style = (locator: ReturnType<Page['locator']>) =>
    locator.evaluate((element) => {
      const css = getComputedStyle(element);
      return {
        blend: css.mixBlendMode,
        background: css.backgroundColor,
        isolation: css.isolation,
        zIndex: css.zIndex,
        shadow: css.boxShadow,
        border: css.borderTopWidth,
      };
    });
  const fill = await style(picked.getByTestId('pdf-box-fill'));
  expect(fill.blend).toBe('multiply');
  // 불투명(알파 1) — rgb(…) 꼴(rgba 아님).
  expect(fill.background).toMatch(/^rgb\(/);
  const other = await style(
    page.locator('[data-box="p1-b1"] [data-testid="pdf-box-fill"]'),
  );
  expect(other.blend).toBe('multiply');
  expect(other.background).toMatch(/^rgba\(/);
  for (const layer of [
    picked,
    picked.getByTestId('pdf-box-mark'),
    picked.getByTestId('pdf-box-badge'),
  ])
    expect((await style(layer)).blend).toBe('normal');
  // 곱하기가 갇히지 않게: 단추·쪽 그림 틀은 쌓임 맥락을 열지 않는다.
  for (const element of [picked, page.getByTestId('pdf-page')]) {
    const css = await style(element);
    expect(css.isolation).toBe('auto');
    expect(css.zIndex).toBe('auto');
  }
  const sheet = await style(page.getByTestId('pdf-page'));
  expect(sheet.shadow).toContain('rgba(0, 0, 0, 0.1) 0px 0px 5px 2px');
  expect(sheet.border).toBe('0px');
  expect((await style(page.getByTestId('pdf-page-scroll'))).background).toBe(
    'rgb(231, 233, 236)',
  );
});

test('TRW7 ③b-1 S4b: 보기 머리 파트 탭(끝난 PDF 파트 둘) → 다른 파트 누름 → …/pdf/<그 runId> replace · 그 파트 쪽 · [← 결과 요약] → 그 파트 탭', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const api = await fakeTranslationPdfApi(page);
  await signIn(page);
  await startPdf(page, false, { story: '1~2', general: '3' });
  api.runCalls().forEach((_, n) => api.setRun(20 + n, 'done'));
  const head = page.locator('[data-screen="translation-run"] > *').first();
  await expect(head.getByTestId('open-pdf')).toBeVisible({ timeout: 10_000 });
  await head.getByTestId('open-pdf').click();
  await expect(page).toHaveURL(/\/pdf\/20$/);
  // 파트 탭만(data-tab) — 밴드 TRW8 ⑥ 의 목록 꼴 line 탭도 이 감싸개 안(몸)에 있다.
  const tabs = page
    .getByTestId('pdf-part-tabs')
    .locator('[role="tab"][data-tab]');
  await expect(tabs).toHaveCount(2);
  await expect(tabs.nth(0)).toHaveAttribute('data-tab', 'story');
  await expect(tabs.nth(0)).toHaveAttribute('aria-selected', 'true');
  const depth = await page.evaluate(() => history.length);
  await tabs.nth(1).click();
  await expect(page).toHaveURL(/\/pdf\/21$/);
  expect(await page.evaluate(() => history.length)).toBe(depth);
  await expect(
    page
      .getByTestId('pdf-part-tabs')
      .locator('[role="tab"][data-tab="general"]'),
  ).toHaveAttribute('aria-selected', 'true');
  // 가짜 서버는 실행마다 같은 layout — 쪽 머리의 파트 배지로 그 파트 보기임을 본다.
  await expect(page.getByTestId('pdf-page-title')).toContainText(
    TR_TEXT.parts.names.general,
  );
  await page.getByTestId('pdf-back').click();
  await expect(page).toHaveURL(/part=general/);
});

// ── 밴드 TRW8 ③~⑦·② — 항목 칸(디자인 74 처방). TRW8_SHOTS 가 있으면 목록·이슈 탭·상세·넓은 표 그림 ──

const ONE_PDF = Buffer.from(
  writePdf([
    {
      width: 595,
      height: 842,
      rotate: 0 as const,
      marks: [],
      texts: [{ x: 72, top: 72, size: 18, str: 'Made-up page 1' }],
      tables: [],
    },
  ]),
);

async function openOne(page: Page, width: number, layout: unknown) {
  await page.setViewportSize({ width, height: 900 });
  await fakeTranslationPdfApi(page, {
    done: { pdf: ONE_PDF, layout, result: true },
  });
  await signIn(page);
  await page.goto(
    `/translation/documents/${PDF_DOC_ID}/batches/b-1/pdf/${PDF_RUN_ID}`,
  );
  await expect(
    page.locator('[data-testid="pdf-page"] canvas[data-render-state="done"]'),
  ).toBeVisible();
}

const shot = async (page: Page, name: string) => {
  const dir = process.env.TRW8_SHOTS;
  if (!dir) return;
  // 몸 칸 gw-m-fade 가 끝난 뒤에 찍는다(그림만 — 단언 아님).
  await page.evaluate(() =>
    Promise.all(document.getAnimations().map((each) => each.finished)),
  );
  await page.screenshot({ path: `${dir}/${name}.png` });
};

for (const width of [1440, 1280]) {
  test(`TRW8 ${width}: 항목 고름 → [B] → 같은 항목에 머묾 · 맨 위 [목록으로]·‹ n / N ›`, async ({
    page,
  }) => {
    // 견주기 layout(A·B 둘 — 쪽 1·2, 둘째 번역만 다름).
    await openOne(page, width, layoutOf(['A', 'B'], 2));
    const pairs = page.getByTestId('pdf-pairs');
    await expect(page.getByTestId('pdf-list-tabs')).toBeVisible();
    await shot(page, `trw8-list-${width}`);
    await page.locator('[data-box="p1-b2"]').click();
    await expect(page.getByTestId('pdf-pair-position')).toHaveText(
      TR_TEXT.pdfView.pair.position(2, 4),
    );
    // 상세 꼴: 맨 위 문체 탭 0 · 「번역」 머리 줄 전환(밴드 TRW8 ④ 개정 — sid:MARC-ENT-502).
    await expect(
      pairs.getByRole('tab', { name: TR_TEXT.pdfView.styleOf('B') }),
    ).toHaveCount(0);
    const styleB = page.getByTestId('pdf-style-switch').getByRole('tab', {
      name: TR_TEXT.pdfView.pair.styles.one('B'),
      exact: true,
    });
    await styleB.click();
    await expect(page.getByTestId('pdf-stage')).toBeVisible();
    await expect(styleB).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('pdf-pair')).toBeVisible();
    await expect(page.getByTestId('pdf-pair-position')).toHaveText(
      TR_TEXT.pdfView.pair.position(2, 4),
    );
    await expect(page.locator('[data-box="p1-b2"]')).toHaveAttribute(
      'data-selected',
      'true',
    );
    // 맨 위 한 줄: [목록으로]·‹·›가 짝 칸 머리 쪽(번역 글보다 위).
    const back = (await page.getByTestId('pdf-pair-back').boundingBox())!;
    const text = (await page
      .getByTestId('pdf-pair-translation')
      .first()
      .boundingBox())!;
    expect(back.y).toBeLessThan(text.y);
    await shot(page, `trw8-detail-${width}`);
  });

  test(`TRW8 ${width}: [검수 이슈] 탭 → 줄 누름 → 그 항목 상세 → [목록으로] → 이슈 탭`, async ({
    page,
  }) => {
    await openOne(page, width, pdfLayout());
    const tabs = page.getByTestId('pdf-list-tabs');
    // 결과의 쪽 1 이슈 하나(「Made-up Co.」 — 항목 2 번역).
    await expect(tabs.getByRole('tab').nth(1)).toHaveText(
      TR_TEXT.pdfView.pair.tabs.issues(1),
    );
    await expect(
      page.locator('button[data-pair="1"][data-issues="1"]'),
    ).toBeVisible();
    await tabs.getByRole('tab').nth(1).click();
    const group = page.getByTestId('pdf-issue-group');
    await expect(group).toHaveCount(1);
    await expect(group).toContainText(TR_TEXT.pdfView.pair.itemOf(2));
    await shot(page, `trw8-issues-${width}`);
    await group.getByRole('button').first().click();
    await expect(page.getByTestId('pdf-pair-position')).toHaveText(
      TR_TEXT.pdfView.pair.position(2, 4),
    );
    await page.getByTestId('pdf-pair-back').click();
    await expect(tabs.getByRole('tab').nth(1)).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(page.getByTestId('pdf-issue-group')).toHaveCount(1);
  });

  test(`TRW8 ${width}: 넓은 표(14열) 항목 → 표 상자 안에서 가로로 밂 · 짝 칸이 쪽 칸과 겹침 0`, async ({
    page,
  }) => {
    await openOne(page, width, wideTableLayout(14));
    await page.locator('[data-box="p1-t1#cell"]').click();
    const scroll = page.getByTestId('pdf-table-scroll').first();
    await expect(scroll).toBeVisible();
    const sizes = await scroll.evaluate((el) => ({
      scroll: el.scrollWidth,
      client: el.clientWidth,
      overflowX: getComputedStyle(el).overflowX,
      cell: el.querySelector('td')!.getBoundingClientRect().width,
    }));
    expect(sizes.overflowX).toBe('auto');
    expect(sizes.scroll).toBeGreaterThan(sizes.client);
    expect(sizes.cell).toBeGreaterThanOrEqual(72);
    const pane = (await page.getByTestId('pdf-page-pane').boundingBox())!;
    const pairs = (await page.getByTestId('pdf-pairs').boundingBox())!;
    expect(pane.x + pane.width).toBeLessThanOrEqual(pairs.x + 0.5);
    // 짝 칸 자체는 가로로 넘치지 않는다(표 상자만 민다).
    const panel = await page
      .getByTestId('pdf-pairs')
      .evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(panel).toBeLessThanOrEqual(0);
    await shot(page, `trw8-wide-${width}`);
  });

  test(`TRW8 ${width}: 상세 [둘 다] → 번역 A·B 칸 위아래 · 맨 위 단계 줄 0 · 다음 항목에도 둘 다`, async ({
    page,
  }) => {
    await openOne(page, width, layoutOf(['A', 'B'], 2));
    await page.locator('[data-box="p1-b2"]').click();
    const switcher = page.getByTestId('pdf-style-switch');
    await switcher
      .getByRole('tab', { name: TR_TEXT.pdfView.pair.styles.both })
      .click();
    const sides = page.getByTestId('pdf-pair-style');
    await expect(sides).toHaveCount(2);
    await expect(sides.nth(0)).toContainText(
      TR_TEXT.pdfView.pair.translationOf('A'),
    );
    await expect(sides.nth(1)).toContainText(
      TR_TEXT.pdfView.pair.translationOf('B'),
    );
    await expect(page.getByTestId('pdf-stage')).toHaveCount(0);
    await shot(page, `trw8-both-${width}`);
    await page
      .getByRole('button', { name: TR_TEXT.pdfView.pair.next, exact: true })
      .click();
    await expect(page.getByTestId('pdf-pair-position')).toHaveText(
      TR_TEXT.pdfView.pair.position(3, 4),
    );
    await expect(sides).toHaveCount(2);
    const a = (await sides.nth(0).boundingBox())!;
    const b = (await sides.nth(1).boundingBox())!;
    expect(a.y + a.height).toBeLessThanOrEqual(b.y + 0.5);
  });

  test(`TRW8 ${width}: 넓은 표 [둘 다] → 격자 셋 · 표 상자마다 가로로 밂 · 짝 칸 넘침 0`, async ({
    page,
  }) => {
    const wide = wideTableLayout(14);
    const layout = {
      ...wide,
      variants: ['A', 'B'].map((label) => ({ ...wide.variants[0]!, label })),
    };
    await openOne(page, width, layout);
    await page.locator('[data-box="p1-t1#cell"]').click();
    await page
      .getByTestId('pdf-style-switch')
      .getByRole('tab', { name: TR_TEXT.pdfView.pair.styles.both })
      .click();
    const scrolls = page.getByTestId('pdf-table-scroll');
    await expect(scrolls).toHaveCount(3);
    for (let n = 0; n < 3; n += 1) {
      const over = await scrolls
        .nth(n)
        .evaluate((el) => el.scrollWidth - el.clientWidth);
      expect(over).toBeGreaterThan(0);
    }
    const panel = await page
      .getByTestId('pdf-pairs')
      .evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(panel).toBeLessThanOrEqual(0);
    await shot(page, `trw8-both-wide-${width}`);
  });
}

// ── 밴드 TRW8 ⑧① — 요약 카드 처음부터 5칸 · PDF 보기 파트 탭 줄 유지 ──

const SUMMARY_KEYS = [
  'translated',
  'untranslated',
  'checks',
  'glossaryMiss',
  'issues',
];

test('TRW8 ⑧: 한 파트 PDF 요약 — layout 을 붙잡은 동안도 5칸(셋째 「확인할 곳」 skeleton) → 풀면 같은 5칸·같은 칸 요소에 값', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let release!: () => void;
  const hold = new Promise<void>((resolve) => {
    release = resolve;
  });
  const api = await fakeTranslationPdfApi(page, {
    layoutHold: hold,
    warnings: [{ code: 'tag_extra', page: 2, tag: null, variant: 'single' }],
  });
  await signIn(page);
  await startPdf(page, false, { story: '1~2' });
  api.runCalls().forEach((_, n) => api.setRun(20 + n, 'done'));
  const tiles = page.locator('[data-stat]');
  await expect(page.locator('[data-stat="translated"]')).toBeVisible({
    timeout: 10_000,
  });
  await shot(page, 'trw8-summary-held');
  const keys = () =>
    tiles.evaluateAll((all) =>
      all.map((each) => each.getAttribute('data-stat')),
    );
  expect(await keys()).toEqual(SUMMARY_KEYS);
  const checks = page.locator('[data-stat="checks"]');
  await expect(checks).toHaveAttribute('data-pending', '');
  await expect(checks.locator('[data-skeleton-bar]')).toHaveCount(2);
  const before = await checks.elementHandle();
  release();
  await expect(checks.getByTestId('stat-value')).toHaveText('1');
  await expect(checks).not.toHaveAttribute('data-pending');
  expect(await keys()).toEqual(SUMMARY_KEYS);
  expect(await before!.evaluate((each) => each.isConnected)).toBe(true);
  await shot(page, 'trw8-summary-ready');
  await checks.getByTestId('stat-open').click();
  await expect(page).toHaveURL(/\/pdf\/20$/);
});

test('TRW8 ①: PDF 보기 파트 탭 누름 → 탭 줄은 한 번도 빠지지 않고(같은 요소) 새 파트 몸만 새로', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const api = await fakeTranslationPdfApi(page);
  await signIn(page);
  await startPdf(page, false, { story: '1~2', general: '3' });
  api.runCalls().forEach((_, n) => api.setRun(20 + n, 'done'));
  const head = page.locator('[data-screen="translation-run"] > *').first();
  await expect(head.getByTestId('open-pdf')).toBeVisible({ timeout: 10_000 });
  await head.getByTestId('open-pdf').click();
  await expect(page).toHaveURL(/\/pdf\/20$/);
  const bar = page.getByTestId('pdf-part-tabs');
  await expect(bar.locator('[role="tab"][data-tab]')).toHaveCount(2);
  const kept = await bar.elementHandle();
  // 탭 줄이 DOM 에서 빠지는 순간을 센다(toBeVisible 은 다시 붙으면 통과라 그 사이를 못 봄).
  await page.evaluate(() => {
    const seen = window as unknown as { tabsGone: number };
    seen.tabsGone = 0;
    new MutationObserver(() => {
      if (document.querySelector('[data-testid="pdf-part-tabs"]') === null)
        seen.tabsGone += 1;
    }).observe(document.body, { childList: true, subtree: true });
  });
  await bar.locator('[role="tab"][data-tab="general"]').click();
  await expect(bar).toBeVisible();
  await expect(page).toHaveURL(/\/pdf\/21$/);
  await expect(page.getByTestId('pdf-page-title')).toContainText(
    TR_TEXT.parts.names.general,
  );
  await expect(bar).toBeVisible();
  await expect(bar.locator('[role="tab"][data-tab="general"]')).toHaveAttribute(
    'aria-selected',
    'true',
  );
  expect(
    await page.evaluate(
      () => (window as unknown as { tabsGone: number }).tabsGone,
    ),
  ).toBe(0);
  expect(await kept!.evaluate((each) => each.isConnected)).toBe(true);
});

for (const width of [1440, 1280]) {
  test(`TRW10 ${width}: 견주기 머리글·꼬리말 → 「번역」 머리 줄 아래 안내 한 줄 · [둘 다] → 칸마다`, async ({
    page,
  }) => {
    const shotOf = async (name: string) => {
      const dir = process.env.TRW10_SHOTS;
      if (!dir) return;
      // 몸 칸 gw-m-fade 가 끝난 뒤에 찍는다(그림만 — 단언 아님).
      await page.evaluate(() =>
        Promise.all(document.getAnimations().map((each) => each.finished)),
      );
      await page.screenshot({ path: `${dir}/trw10-hf-${name}-${width}.png` });
    };
    await openOne(page, width, layoutOf(['A', 'B'], 2));
    await page.locator('[data-box="p1-b9"]').click();
    const line = page.getByTestId('pdf-pair-source-only');
    await expect(line).toHaveCount(1);
    await expect(line).toHaveText(TR_TEXT.pdfView.pair.sourceOnly);
    const head = page
      .getByTestId('pdf-pair')
      .getByText(TR_TEXT.pdfView.pair.translation, { exact: true });
    const headBox = (await head.boundingBox())!;
    const lineBox = (await line.boundingBox())!;
    expect(lineBox.y).toBeGreaterThanOrEqual(headBox.y + headBox.height);
    await shotOf('A');
    await page
      .getByTestId('pdf-style-switch')
      .getByRole('tab', { name: TR_TEXT.pdfView.pair.styles.both, exact: true })
      .click();
    await expect(page.getByTestId('pdf-pair-style')).toHaveCount(2);
    await expect(line).toHaveCount(2);
    await shotOf('both');
  });
}
