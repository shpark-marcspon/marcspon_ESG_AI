// 그린워싱 실어댑터를 빌드 결과에서(밴드 GW1R ② — 발주서 §3 E). 목 표지 없이 열면 기본 저장소가 실어댑터다.
// 서버는 e2e/greenwash-server.ts 의 흉내(page.route). 서명 올리기는 같은 출처 /fake-upload/<id>(저장소 CORS 는 sid:MARC-ISSUE-222 몫).
// PDF 는 tools/pdf-writer.ts 로 메모리에서 만든다(디스크에 .pdf 를 두지 않는다). 쪽 수는 브라우저의 pdf.js 가 센다(Q2).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { readFileSync, writeFileSync } from 'node:fs';

import { GW_TEXT } from '../src/entities/greenwash/config/text.ts';
import { writePdf } from '../tools/pdf-writer.ts';
import type { SamplePage } from '../tools/sample-layout.ts';
import { fakeGreenwashApi, steps } from './greenwash-server.ts';
import type { FakeDoc, FakeRun } from './greenwash-server.ts';
import { signIn } from './session.ts';

const words = GW_TEXT.newCheck;
const status = GW_TEXT.status;
const list = GW_TEXT.list;

test.beforeEach(({ page }) => signIn(page));

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

/** 콘솔 오류를 모은다. */
function consoleErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  return errors;
}

test('GW-02 → GW-03: 7쪽 PDF → POST /api/documents → PUT /fake-upload(크기 그대로·Authorization 없음) → confirm → 보고연도 2025 → PATCH /api/documents/12 {reportYear} → POST /api/runs → failed no_text_layer 카드 → [새 점검]', async ({
  page,
}) => {
  const api = await fakeGreenwashApi(page);
  const errors = consoleErrors(page);
  await page.goto('/greenwash/new');
  const pdf = pdfOf(7);
  await page.locator('input[type="file"]').setInputFiles({
    name: '지어낸 스캔.pdf',
    mimeType: 'application/pdf',
    buffer: pdf,
  });
  await expect(page.getByTestId('file-meta')).toContainText(
    words.upload.pageMeta(7),
  );
  // 보고연도 칸은 모든 빌드에 있다(밴드 GW2R ③ Q8 — 옛 「실어댑터 빌드엔 없음」을 갈음). 수정본 칸은 없다(밴드 GW2R ①)
  await expect(page.getByLabel(words.year.label)).toHaveCount(1);
  await expect(page.getByText('수정본 연결')).toHaveCount(0);
  // 「3. 점검 설정」 카드를 지워 기본 단어 목록을 읽지 않는다(시안 댓글 — sid:MARC-ENT-603)
  expect(api.keys()).toEqual([
    'POST /documents',
    'PUT /fake-upload/12',
    'POST /documents/12/confirm',
  ]);
  const created = api.calls[0]!;
  expect(created.body).toEqual({
    fileName: '지어낸 스캔.pdf',
    sizeBytes: pdf.length,
  });
  expect(created.authorization).toMatch(/^Bearer /);
  const put = api.calls[1]!;
  expect(put.size).toBe(pdf.length);
  expect(put.authorization).toBeNull();

  await page.getByLabel(words.parts.names.ceo, { exact: true }).fill('8');
  await page.getByLabel(words.parts.names.ceo, { exact: true }).blur();
  await expect(page.getByText(words.parts.rangeError.over(8, 7))).toBeVisible();
  await page.getByLabel(words.parts.names.ceo, { exact: true }).fill('1~2');
  await page.getByLabel(words.year.label).selectOption('2025');
  // 쪽 썸네일 7장이 다 그려진 뒤 떠난다 — 그리기·blob 읽기 도중에 떠나면 화면이 object URL 을 놓고 PDF 를 닫아
  // 콘솔에 ERR_FILE_NOT_FOUND·Transport destroyed 가 남는다(부하에서만, sid:MARC-ISSUE-419)
  await expect(
    page.getByTestId('thumbnails').locator('canvas[data-render-state="done"]'),
  ).toHaveCount(7);
  await page.getByRole('button', { name: words.start }).click();
  await expect(page).toHaveURL(/\/greenwash\/runs\/13$/);
  // 연도는 실행 전 문서 PATCH(본문 정확히 {reportYear}) → 그 뒤 POST /runs(옵션에 연도 없음) — 발주서 §3 E ①
  const patchAt = api.keys().indexOf('PATCH /documents/12');
  const runAt = api.keys().indexOf('POST /runs');
  expect(patchAt).toBeGreaterThan(-1);
  expect(runAt).toBeGreaterThan(patchAt);
  expect(api.calls[patchAt]!.body).toEqual({ reportYear: 2025 });
  expect(api.calls[patchAt]!.authorization).toMatch(/^Bearer /);
  const run = api.calls[runAt]!;
  expect(run.body).toEqual({
    module: 'greenwash',
    documentId: 12,
    // 소문자 UUID(서버 LK1 — 밴드 GP6). 무늬는 칸 규칙상 api 를 가져오지 않고 적는다
    launchKey: expect.stringMatching(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    ),
    options: { parts: { ceo: [1, 2], company: [], climate: [] } },
  });
  expect(api.docs.get(12)!.reportYear).toBe(2025);

  const card = page.getByTestId('failure');
  await expect(card).toHaveAttribute('data-failure', 'no_text_layer');
  await expect(page.getByTestId('failure-info')).toHaveText(
    words.upload.noText,
  );
  await expect(page.getByTestId('failure-file')).toContainText(
    '지어낸 스캔.pdf',
  );
  // 파일 줄 「n쪽 · 텍스트 없음」(228 S2 — 밴드 GW2R ②)
  await expect(page.getByTestId('failure-file')).toContainText('텍스트 없음');
  await expect(page.getByTestId('failure-note')).toHaveCount(0);
  await expect(page.getByRole('button', { name: status.rerun })).toHaveCount(0);
  await page.getByRole('button', { name: status.noText.newCheck }).click();
  await expect(page).toHaveURL(/\/greenwash\/new$/);
  expect(errors).toEqual([]);
});

const NOW = '2026-10-18T09:00:00+09:00';
const doc = (id: number, fileName: string, extra: Partial<FakeDoc> = {}) => ({
  id,
  fileName,
  sizeBytes: 1000,
  uploaded: true,
  pageCount: 10,
  uploadedAt: NOW,
  uploadedBy: { userId: 1, name: '지어낸-user01' },
  ...extra,
});
const run = (
  id: number,
  documentId: number,
  extra: Partial<FakeRun> = {},
): FakeRun => ({
  id,
  documentId,
  status: 'processing',
  steps: steps(2, { status: 'running', done: 3, total: 10 }),
  options: { parts: { ceo: [], company: [], climate: [1, 2, 3] } },
  errorCode: null,
  createdAt: `2026-10-18T09:0${id % 10}:00+09:00`,
  result: null,
  review: null,
  ...extra,
});

test('GW-01: 실어댑터 목록 줄 넷 — 34%·쪽 수 「–」·no_text_layer 줄은 [다시 실행] 없음·step_error 줄은 있음', async ({
  page,
}) => {
  const api = await fakeGreenwashApi(page, {
    documents: [
      doc(1, '지어낸 분석.pdf', { pageCount: null }),
      doc(2, '지어낸 스캔.pdf'),
      doc(3, '지어낸 멈춤.pdf'),
      doc(4, '지어낸 대기.pdf'),
    ],
    runs: [
      run(5, 1),
      run(6, 2, {
        status: 'failed',
        steps: steps(0, { status: 'failed' }),
        errorCode: 'no_text_layer',
      }),
      run(7, 3, {
        status: 'failed',
        steps: steps(0, { status: 'failed' }),
        errorCode: 'step_error',
      }),
      run(8, 4, { status: 'queued', steps: steps(0) }),
    ],
  });
  const errors = consoleErrors(page);
  await page.goto('/greenwash');
  const rows = page
    .getByRole('table', { name: list.tableLabel })
    .locator('tbody tr');
  await expect(rows).toHaveCount(4);
  const rowOf = (name: string) => rows.filter({ hasText: name });
  await expect(rowOf('지어낸 분석.pdf')).toContainText('34%');
  await expect(rowOf('지어낸 분석.pdf')).toContainText(list.none);
  await expect(rowOf('지어낸 스캔.pdf').locator('[data-next]')).toHaveCount(0);
  await expect(
    rowOf('지어낸 멈춤.pdf').locator('[data-next="rerun"]'),
  ).toHaveText(list.next.rerun);
  expect(api.keys()).toEqual(['GET /greenwash/checks']);
  expect(errors).toEqual([]);
});

test('setup_error(index 에서 멈춤 — 실서버 꼴): GW-01 줄 [다시 실행] 빈칸 → GW-03 오류 카드 「서비스 설정 문제로 …」·[목록으로]만(밴드 GW2R ② — 발주서 §3 E ③)', async ({
  page,
}) => {
  const api = await fakeGreenwashApi(page, {
    documents: [doc(2, '지어낸 설정.pdf'), doc(3, '지어낸 멈춤.pdf')],
    runs: [
      run(6, 2, {
        status: 'failed',
        steps: steps(1, { status: 'failed' }),
        errorCode: 'setup_error',
      }),
      run(7, 3, {
        status: 'failed',
        steps: steps(1, { status: 'failed' }),
        errorCode: 'step_error',
      }),
    ],
  });
  const errors = consoleErrors(page);
  await page.goto('/greenwash');
  const rows = page
    .getByRole('table', { name: list.tableLabel })
    .locator('tbody tr');
  await expect(rows).toHaveCount(2);
  const setup = rows.filter({ hasText: '지어낸 설정.pdf' });
  await expect(setup.locator('[data-next]')).toHaveCount(0);
  await expect(setup.getByTestId('row-status')).toHaveText('멈춤');
  await expect(
    rows.filter({ hasText: '지어낸 멈춤.pdf' }).locator('[data-next="rerun"]'),
  ).toHaveText(list.next.rerun);
  await setup.locator('td').first().click();
  await expect(page).toHaveURL(/\/greenwash\/runs\/6$/);
  const card = page.getByTestId('failure');
  await expect(card).toHaveAttribute('data-failure', 'setup_error');
  await expect(page.getByTestId('failure-info')).toHaveText(
    status.setupFailure,
  );
  await expect(card.getByRole('button')).toHaveText([status.back]);
  await expect(page.getByRole('button', { name: status.rerun })).toHaveCount(0);
  expect(api.keys().filter((key) => key.startsWith('POST'))).toEqual([]);
  expect(errors).toEqual([]);
});

/** 지어낸 결과(greenwash.result@1, 문장 셋 — 목 빌더로 한 번 뽑은 것. 실제 보고서 문장 0). */
const RESULT = JSON.parse(
  readFileSync(new URL('./greenwash-result.json', import.meta.url), 'utf8'),
) as Record<string, unknown>;

test('끝난 실행 GW-03 → 「… 끝남 · 3문장을 찾았어요」·인식 실패 페이지 칩 → [결과 보기] → [내려받기] → 받기 모달 엑셀 줄 → GET /api/greenwash/runs/13/report(쿼리 없음) → 파일 내려받기(밴드 GW2R ③ — 발주서 §3 E ② → GDL1)', async ({
  page,
}) => {
  const api = await fakeGreenwashApi(page, {
    documents: [doc(3, '지어낸 보고서.pdf', { pageCount: 80 })],
    runs: [
      run(13, 3, {
        status: 'done',
        steps: steps(6),
        options: { parts: { ceo: [1], company: [2], climate: [3] } },
        finishedAt: '2026-10-18T10:52:00+09:00',
        // 인식 실패 페이지는 결과에만(차례 섞임 70·31·58)
        result: {
          ...RESULT,
          candidateStats: {
            ...(RESULT.candidateStats as Record<string, unknown>),
            failedPages: [70, 31, 58].map((p) => ({
              page: p,
              error: '지어낸',
            })),
          },
        },
        review: {
          state: 'pending',
          marks: [],
          confirmedAt: null,
          confirmedBy: null,
        },
      }),
    ],
  });
  const errors = consoleErrors(page);
  await page.goto('/greenwash/runs/13');
  await expect(
    page.getByRole('heading', { name: status.title.done, level: 2 }),
  ).toBeVisible();
  await expect(
    page.getByText(
      '2026-10-18 10:52 끝남 · 3개의 그린워싱 리스크 문장을 찾았어요',
    ),
  ).toBeVisible();
  await expect(page.getByTestId('missed-pages')).toHaveText(
    '인식 실패 페이지 3개 (31 · 58 · 70페이지)',
  );
  // 끝남에는 진행 카드(막대·단계 셋)가 없다(판 r3 — sid:MARC-ISSUE-265 (1), 밴드 GP1)
  await expect(page.getByRole('progressbar')).toHaveCount(0);
  await expect(page.locator('li[data-stage]')).toHaveCount(0);
  await page.getByRole('button', { name: status.viewResult }).click();
  await expect(page).toHaveURL(/\/greenwash\/runs\/13\/result$/);
  await page.getByTestId('gw-downloads').click();
  const download = page.waitForEvent('download');
  await page.getByTestId('gw-download-dialog-file-excel').click();
  const file = await download;
  expect(file.suggestedFilename()).toBe('지어낸 보고서 13.xlsx');
  const reports = api.calls.filter(
    (call) => call.path === '/greenwash/runs/13/report',
  );
  expect(reports.map((call) => call.search)).toEqual(['']);
  expect(reports[0]!.authorization).toMatch(/^Bearer /);
  await expect(
    page.getByTestId('gw-download-dialog-problem-excel'),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('GW-05(③): 채택 → PUT 본문 · [확정] → 05b → 확정 전 GET → PUT state confirmed·marks 셋 → 잠금 띠 이름', async ({
  page,
}) => {
  const api = await fakeGreenwashApi(page, {
    documents: [doc(3, '지어낸 보고서.pdf', { pageCount: 7 })],
    runs: [
      run(13, 3, {
        status: 'done',
        steps: steps(6),
        options: { parts: { ceo: [1], company: [2], climate: [3] } },
        result: RESULT,
        review: {
          state: 'pending',
          marks: [],
          confirmedAt: null,
          confirmedBy: null,
        },
      }),
    ],
    confirmer: { id: 9, name: '확정자 가' },
  });
  const errors = consoleErrors(page);
  await page.goto('/greenwash/runs/13/review');
  const review = GW_TEXT.reviewScreen;
  await expect(page.getByTestId('review-state')).toHaveAttribute(
    'data-state',
    'pending',
  );
  // 첫 문장 채택
  await page
    .getByTestId('review-detail')
    .getByRole('group', { name: GW_TEXT.review.groupLabel })
    .getByRole('button', { name: GW_TEXT.review.adopted })
    .click();
  await expect(page.getByTestId('review-state')).toHaveAttribute(
    'data-state',
    'in_review',
  );
  const puts = () =>
    api.calls.filter(
      (call) => call.method === 'PUT' && call.path.endsWith('/review'),
    );
  expect(puts().map((call) => call.body)).toEqual([
    { marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }] },
  ]);
  // [확정] → 05b → 확정 전 GET → PUT
  await page.getByRole('button', { name: review.confirm }).click();
  const dialog = page.getByRole('dialog', { name: GW_TEXT.confirm.title });
  const before = api.keys().length;
  await dialog.getByRole('button', { name: GW_TEXT.confirm.submit }).click();
  await expect(page.getByTestId('review-state')).toHaveAttribute(
    'data-state',
    'confirmed',
  );
  expect(api.keys().slice(before)).toEqual([
    'GET /greenwash/runs/13/review',
    'PUT /greenwash/runs/13/review',
  ]);
  expect(puts().at(-1)!.body).toEqual({
    state: 'confirmed',
    marks: [0, 1, 2].map((itemIndex) => ({
      itemIndex,
      decision: 'adopted',
      excludeReason: null,
    })),
  });
  await expect(page.locator('[data-lock-banner]')).toContainText('확정자 가');
  expect(errors).toEqual([]);
});

test('GW-05 고침(밴드 G1b-3 ③): 등급 고르기·수정 방향 칸을 벗어나면 PUT(edits) → 새로고침해도 남음 → [확정](edits 없음) → 05c 잠김(고르기·[고치기] 없음, 「고침」·AI 원래 판단 남음)', async ({
  page,
}) => {
  const api = await fakeGreenwashApi(page, {
    documents: [doc(3, '지어낸 보고서.pdf', { pageCount: 7 })],
    runs: [
      run(13, 3, {
        status: 'done',
        steps: steps(6),
        options: { parts: { ceo: [1], company: [2], climate: [3] } },
        result: RESULT,
        review: {
          state: 'pending',
          marks: [],
          confirmedAt: null,
          confirmedBy: null,
        },
      }),
    ],
    confirmer: { id: 9, name: '고친이 가' },
  });
  const errors = consoleErrors(page);
  await page.goto('/greenwash/runs/13/review');
  const review = GW_TEXT.reviewScreen;
  const detail = page.getByTestId('review-detail');
  const puts = () =>
    api.calls.filter(
      (call) => call.method === 'PUT' && call.path.endsWith('/review'),
    );
  // 등급 고르기(첫 문장 High → Low): 고르면 바로 PUT
  await detail.getByRole('button', { name: '등급 고르기' }).click();
  await page.getByRole('menuitemradio', { name: 'Low' }).click();
  await expect(page.getByTestId('review-state')).toHaveAttribute(
    'data-state',
    'in_review',
  );
  expect(puts().map((call) => call.body)).toEqual([
    {
      marks: [],
      edits: [
        { itemIndex: 0, level: 'Low', reasonBullets: null, fixParagraph: null },
      ],
    },
  ]);
  // 수정 방향 [고치기] → 글 칸 → 칸을 벗어나면 저장
  const fix = page.getByTestId('field-fixParagraph');
  await fix.getByRole('button', { name: '고치기' }).click();
  await expect(fix).toContainText('고치는 중 · 칸을 벗어나면 저장돼요');
  await fix
    .getByRole('textbox', { name: review.fixHeading })
    .fill('지어낸 고친 방향');
  await page.getByRole('heading', { level: 2 }).click();
  await expect(fix.getByRole('textbox')).toHaveCount(0);
  expect(puts().at(-1)!.body).toEqual({
    marks: [],
    edits: [
      {
        itemIndex: 0,
        level: 'Low',
        reasonBullets: null,
        fixParagraph: '지어낸 고친 방향',
      },
    ],
  });
  // 새로고침해도 남는다(서버 검토)
  await page.reload();
  const first = page.getByTestId('sentence-list').getByRole('button').first();
  await expect(first.locator('[data-level]')).toHaveAttribute(
    'data-level',
    'low',
  );
  await expect(first.locator('[data-edited]')).toHaveText('고침');
  await expect(page.getByTestId('field-fixParagraph')).toContainText(
    '지어낸 고친 방향',
  );
  await expect(detail.locator('details[data-ai-original] summary')).toHaveText([
    'AI 원래 판단 보기 · 고친 사람 고친이 가 · 10-19 10:00',
    'AI 원래 판단 보기 · 고친 사람 고친이 가 · 10-19 10:00',
  ]);
  // 확정: 본문에 edits 없음
  await page.getByRole('button', { name: review.confirm }).click();
  const dialog = page.getByRole('dialog', { name: GW_TEXT.confirm.title });
  await dialog.getByRole('button', { name: GW_TEXT.confirm.submit }).click();
  await expect(page.getByTestId('review-state')).toHaveAttribute(
    'data-state',
    'confirmed',
  );
  expect(Object.keys(puts().at(-1)!.body as object).sort()).toEqual([
    'marks',
    'state',
  ]);
  // 05c: 고르기·[고치기] 없음, 「고침」·잠김 글·AI 원래 판단은 남음
  await expect(detail.getByRole('button', { name: '등급 고르기' })).toHaveCount(
    0,
  );
  await expect(detail.getByRole('button', { name: '고치기' })).toHaveCount(0);
  await expect(detail.locator('[data-edited]')).toHaveCount(2);
  await expect(page.getByTestId('field-fixParagraph')).toContainText(
    '확정해서 잠김 · AI 원래 판단은 엑셀에 함께 담겨요',
  );
  await expect(detail.locator('details[data-ai-original]')).toHaveCount(2);
  expect(errors).toEqual([]);
});

// ── 밴드 GP1 ──
const doneRun = (id: number, documentId: number) =>
  run(id, documentId, {
    status: 'done',
    steps: steps(6),
    options: { parts: { ceo: [1], company: [2], climate: [3] } },
    result: RESULT,
    review: {
      state: 'pending',
      marks: [],
      confirmedAt: null,
      confirmedBy: null,
    },
  });

test('GW-05 판정 사유 고침(sid:MARC-ISSUE-315): [고치기] 뒤 바로 치면 글 끝에 붙고, PUT 의 사유 항목·다시 그린 목록에 표지 「- 」가 섞이지 않는다', async ({
  page,
}) => {
  const api = await fakeGreenwashApi(page, {
    documents: [doc(3, '지어낸 보고서.pdf', { pageCount: 7 })],
    runs: [doneRun(13, 3)],
  });
  const errors = consoleErrors(page);
  await page.goto('/greenwash/runs/13/review');
  const review = GW_TEXT.reviewScreen;
  const field = page.getByTestId('field-reasonBullets');
  await field.getByRole('button', { name: review.edit.start }).click();
  const box = field.getByRole('textbox', { name: review.reasonHeading });
  // 칸 글은 항목 글 그대로(표지 없음)
  await expect(box).toHaveValue(
    '지어낸 사유: 근거 조각에 수치가 보이지 않아요.',
  );
  // 커서를 옮기지 않고 바로 친다(리허설 LR2 의 꼴 — 옛 칸은 커서가 맨 앞이라 「(친 글)- 원래 글」이 됐다)
  await page.keyboard.type(' 지어낸 덧붙임');
  await page.getByRole('heading', { level: 2 }).click();
  await expect(field.getByRole('textbox')).toHaveCount(0);
  const puts = api.calls.filter(
    (call) => call.method === 'PUT' && call.path.endsWith('/review'),
  );
  // 저장 몸은 BASE 에서 글 끝에 쳤을 때와 같은 값(한 줄 = 한 항목, 표지 없이)
  expect(puts.map((call) => call.body)).toEqual([
    {
      marks: [],
      edits: [
        {
          itemIndex: 0,
          level: null,
          reasonBullets: [
            '지어낸 사유: 근거 조각에 수치가 보이지 않아요. 지어낸 덧붙임',
          ],
          fixParagraph: null,
        },
      ],
    },
  ]);
  // 다시 그린 목록(첫 ul — AI 원래 판단 접기 안의 목록은 그 뒤)
  await expect(field.locator('ul').first().locator('li')).toHaveText([
    '지어낸 사유: 근거 조각에 수치가 보이지 않아요. 지어낸 덧붙임',
  ]);
  // 새로고침해도 같다(서버가 돌려준 고친 값)
  await page.reload();
  await expect(
    page.getByTestId('field-reasonBullets').locator('ul').first().locator('li'),
  ).toHaveText([
    '지어낸 사유: 근거 조각에 수치가 보이지 않아요. 지어낸 덧붙임',
  ]);
  expect(errors).toEqual([]);
});

test('GW-04 [내려받기] 받기 모달 엑셀 줄 실패(500): 그 줄 아래 excelFailed 안내, 화면·주소 그대로(밴드 GP1 §1-9 → GDL1)', async ({
  page,
}) => {
  const api = await fakeGreenwashApi(page, {
    documents: [doc(3, '지어낸 보고서.pdf', { pageCount: 7 })],
    runs: [doneRun(13, 3)],
  });
  // 흉내 서버보다 나중에 걸어 먼저 받는다(report 만 500)
  await page.route('**/api/greenwash/runs/13/report', (route) =>
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'INTERNAL', message: '지어낸 실패' },
      }),
    }),
  );
  await page.goto('/greenwash/runs/13/result');
  // GW-04 제목 줄(h2 = 문서 이름 + 상태 배지)
  const heading = page.getByRole('heading', {
    level: 2,
    name: /지어낸 보고서\.pdf/,
  });
  await expect(heading).toBeVisible();
  let downloaded = false;
  page.on('download', () => {
    downloaded = true;
  });
  await page.getByTestId('gw-downloads').click();
  const excel = page.getByTestId('gw-download-dialog-file-excel');
  await excel.click();
  const problem = page.getByTestId('gw-download-dialog-problem-excel');
  await expect(problem).toHaveText(GW_TEXT.result.excelFailed);
  await expect(problem).toHaveAttribute('role', 'alert');
  // 안내는 그 줄 아래(같은 파일 묶음 안 — 옛 「단추 옆」을 갈음)
  const near = await problem.evaluate((error) => {
    const row = error.closest('[data-file="excel"]');
    const button = document.querySelector(
      '[data-testid="gw-download-dialog-file-excel"]',
    )!;
    return (
      row !== null &&
      row.contains(button) &&
      button.compareDocumentPosition(error) === Node.DOCUMENT_POSITION_FOLLOWING
    );
  });
  expect(near).toBe(true);
  // 단추는 다시 켜진다
  await expect(excel).not.toHaveAttribute('aria-disabled', 'true');
  // 화면 그대로: 모달을 닫으면 주소·제목·[내려받기]가 남고 내려받기는 없다
  await page
    .getByTestId('gw-download-dialog')
    .getByRole('button', { name: GW_TEXT.downloads.close })
    .click();
  await expect(page).toHaveURL(/\/greenwash\/runs\/13\/result$/);
  await expect(heading).toBeVisible();
  await expect(page.getByTestId('gw-downloads')).toBeEnabled();
  expect(downloaded).toBe(false);
  // 흉내 서버는 report 를 받지 않았다(가로챈 500 이 먼저)
  expect(api.calls.filter((call) => call.path.endsWith('/report'))).toEqual([]);
});

test('GW-02 서버 413 UPLOAD_TOO_LARGE(GP1 §1-8): 「잠시 뒤 다시」가 아니라 크기 안내, 실행을 만들지 않는다', async ({
  page,
}) => {
  const api = await fakeGreenwashApi(page);
  await page.route('**/api/documents', (route) =>
    route.request().method() === 'POST' ?
      route.fulfill({
        status: 413,
        contentType: 'application/json',
        body: JSON.stringify({
          error: { code: 'UPLOAD_TOO_LARGE', message: '지어낸 한도' },
        }),
      })
    : route.fallback(),
  );
  await page.goto('/greenwash/new');
  await page.locator('input[type="file"]').setInputFiles({
    name: '지어낸 보고서.pdf',
    mimeType: 'application/pdf',
    buffer: pdfOf(2),
  });
  await expect(page.getByTestId('too-large')).toHaveText(
    words.upload.tooLarge(50),
  );
  await expect(page.getByText(words.startRejected)).toHaveCount(0);
  // 파일을 지우면 안내도 사라진다
  await page.getByRole('button', { name: /지어낸 보고서\.pdf .*지우/ }).click();
  await expect(page.getByTestId('too-large')).toHaveCount(0);
  expect(api.calls.filter((call) => call.path === '/runs')).toEqual([]);
});

test('GW-02 끊김 뒤 입력을 바꿔 다시 누름 → 409 IDEMPOTENCY_KEY_REUSED(sid:MARC-ISSUE-312): 안내 + [목록 보기], 다시 눌러도 같은 열쇠 → [목록 보기]는 목록으로', async ({
  page,
}) => {
  await fakeGreenwashApi(page);
  // POST /runs 만 덧댄다: 첫 번은 끊김(실행이 생겼는지 모름), 그 뒤는 같은 열쇠·다른 본문의 409
  const keys: (string | null)[] = [];
  await page.route('**/api/runs', (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    keys.push(route.request().headers()['idempotency-key'] ?? null);
    if (keys.length === 1) return route.abort('connectionreset');
    return route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'IDEMPOTENCY_KEY_REUSED', message: '지어낸 409' },
      }),
    });
  });
  await page.goto('/greenwash/new');
  await page.locator('input[type="file"]').setInputFiles({
    name: '지어낸 보고서.pdf',
    mimeType: 'application/pdf',
    buffer: pdfOf(3),
  });
  await expect(page.getByTestId('file-meta')).toContainText(
    words.upload.pageMeta(3),
  );
  await expect(
    page.getByTestId('thumbnails').locator('canvas[data-render-state="done"]'),
  ).toHaveCount(3);
  const ceo = page.getByLabel(words.parts.names.ceo, { exact: true });
  const start = page.getByRole('button', { name: words.start });
  await ceo.fill('1');
  await start.click();
  await expect(page.getByTestId('start-error')).toHaveText(
    GW_TEXT.runUnreachable.start,
  );
  await expect(page.getByTestId('start-error-to-list')).toHaveCount(0);
  await ceo.fill('1~2');
  await start.click();
  await expect(page.getByTestId('start-error')).toHaveText(
    words.keyReused.message,
  );
  const toList = page.getByRole('button', { name: words.keyReused.toList });
  await expect(toList).toBeVisible();
  await expect(start).toBeEnabled();
  await start.click();
  await expect.poll(() => keys.length).toBe(3);
  await expect(page.getByTestId('start-error')).toHaveText(
    words.keyReused.message,
  );
  expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/);
  expect(new Set(keys)).toEqual(new Set([keys[0]]));
  await toList.click();
  await expect(page).toHaveURL(/\/greenwash$/);
});

// 밴드 GP2(sid:MARC-ISSUE-341): 긴 목록에서 미리보기·상세 고정 + 같은 쪽 문장 상자·역 포커싱.
/** 지어낸 문장 26개(쪽 1·2·3 에 9·9·8, 모두 위치 있음 — 쪽 아래쪽까지). RESULT 의 꼴에 items·셈만 갈음. */
function longResult() {
  const levels = ['High', 'Mid', 'Low'] as const;
  const parts = ['CEO 메시지', '회사소개', '기후/환경 토픽'];
  const base = (RESULT.items as Record<string, unknown>[])[0]!;
  const items = Array.from({ length: 26 }, (_, index) => {
    const page =
      index < 9 ? 1
      : index < 18 ? 2
      : 3;
    const row =
      index < 9 ? index
      : index < 18 ? index - 9
      : index - 18;
    // 마지막 문장(25)은 쪽 맨 아래(760pt) — 미리보기 칸 안에서 스크롤해야 보인다
    const top = index === 25 ? 760 : 90 + row * 80;
    return {
      ...base,
      page,
      parts: [parts[page - 1]!],
      sentence: `[지어낸 ${index}] ${page}쪽 ${row + 1}번째 환경 주장 문장이에요.`,
      level: levels[index % 3]!,
      evidencePages: [page],
      position: { page, boxes: [[72, top, 480, top + 16]] },
    };
  });
  const byLevel = { High: 0, Mid: 0, Low: 0 };
  for (const one of items) byLevel[one.level] += 1;
  return {
    ...RESULT,
    items,
    candidateStats: {
      ...(RESULT.candidateStats as Record<string, unknown>),
      raw: 26,
      kept: 26,
    },
    counts: { total: 26, byLevel, byPart: {} },
  };
}

async function openLongReview(
  page: Page,
  state: 'pending' | 'confirmed' = 'pending',
) {
  await page.setViewportSize({ width: 1280, height: 800 });
  await fakeGreenwashApi(page, {
    documents: [doc(3, '지어낸 긴 보고서.pdf', { pageCount: 3 })],
    runs: [
      run(13, 3, {
        status: 'done',
        steps: steps(6),
        options: { parts: { ceo: [1], company: [2], climate: [3] } },
        result: longResult(),
        review: {
          state,
          marks: [],
          confirmedAt: state === 'confirmed' ? NOW : null,
          confirmedBy:
            state === 'confirmed' ? { id: 9, name: '확정자 가' } : null,
        },
      }),
    ],
  });
  const errors = consoleErrors(page);
  await page.goto('/greenwash/runs/13/review');
  const pane = page.getByTestId('review-page');
  await expect(pane.locator('canvas')).toHaveAttribute(
    'data-render-state',
    'done',
    { timeout: 20_000 },
  );
  return { errors, pane };
}

const listRow = (page: Page, index: number) =>
  page.getByTestId('sentence-list').locator(`button[data-item="${index}"]`);

/** 요소의 상자가 뷰포트(1280×800) 안에 다 들어오는가. */
async function inViewport(
  page: Page,
  testIdOrLocator: ReturnType<Page['locator']>,
) {
  const box = (await testIdOrLocator.boundingBox())!;
  const view = page.viewportSize()!;
  return (
    box.y >= -0.5 &&
    box.x >= -0.5 &&
    box.y + box.height <= view.height + 0.5 &&
    box.x + box.width <= view.width + 0.5
  );
}

/** inner 가 outer 안에 다 들어오는가(±0.5). */
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

for (const state of ['pending', 'confirmed'] as const) {
  test(`GW-05 미리보기 고정(sid:MARC-ISSUE-341, ${state}): 1280×800·26문장 — 맨 아래 문장을 고르면 쪽이 스크롤돼도 미리보기 칸·하이라이트·상세가 뷰포트 안`, async ({
    page,
  }) => {
    const { errors, pane } = await openLongReview(page, state);
    await expect(
      page.getByTestId('sentence-list').locator('button[data-item]'),
    ).toHaveCount(26);
    await listRow(page, 25).click();
    await expect(listRow(page, 25)).toHaveAttribute('aria-current', 'true');
    await expect(pane.getByTestId('page-heading')).toHaveText(
      GW_TEXT.reviewScreen.pageHeading(3),
    );
    await expect(pane.locator('canvas')).toHaveAttribute(
      'data-render-state',
      'done',
    );
    // 목록은 쪽 스크롤로 내려갔다(칸이 따로 스크롤되지 않는다)
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(300);
    const card = page.getByTestId('review-page-card');
    await expect(card).toHaveCSS('position', 'sticky');
    expect(await inViewport(page, card)).toBe(true);
    const highlight = pane.getByTestId('highlight');
    await expect(highlight).toHaveAttribute('data-level', 'Mid');
    // 하이라이트가 쪽 칸(page-scroll) 안 — 칸 안에서 세로로 스크롤해 맞춘다. 1280 에서는 상자(416)가 칸보다 넓어
    // 가로는 왼쪽 끝과 등급 태그가 칸 안인지만 잰다(쪽 그림은 왼쪽부터 — 위 「GW-05 쪽 칸」 시험과 같은 꼴)
    const scroller = pane.getByTestId('page-scroll');
    const frame = (await highlight
      .locator('span[aria-hidden]')
      .first()
      .boundingBox())!;
    const area = (await scroller.boundingBox())!;
    expect(frame.y).toBeGreaterThanOrEqual(area.y);
    expect(frame.y + frame.height).toBeLessThanOrEqual(area.y + area.height);
    expect(frame.x).toBeGreaterThanOrEqual(area.x);
    expect(await inside(highlight.locator('[data-level]'), scroller)).toBe(
      true,
    );
    // 고른 하이라이트(칠 칸)가 쪽 칸 안 — 1280×800 에서는 칸 폭에 맞춰 줄어든 쪽(밴드 GFS1)이 칸에 다 들어 세로 스크롤 없이도 맞다
    expect(await inside(pane.getByTestId('highlight-fill'), scroller)).toBe(
      true,
    );
    // 낮은 창(1280×560)에서는 쪽이 칸보다 높다 — 같은 문장을 다시 고르면 쪽 칸만 세로로 스크롤해 하이라이트를 칸 안으로(fitInside)
    await page.setViewportSize({ width: 1280, height: 560 });
    await expect
      .poll(() =>
        scroller.evaluate((box) => box.scrollHeight > box.clientHeight),
      )
      .toBe(true);
    await listRow(page, 25).click();
    await expect
      .poll(() => scroller.evaluate((box) => box.scrollTop))
      .toBeGreaterThan(0);
    expect(await inside(pane.getByTestId('highlight-fill'), scroller)).toBe(
      true,
    );
    await page.setViewportSize({ width: 1280, height: 800 });
    // 상세도 sticky(감독 판단 — 같이 보기): 상세가 그 문장이고 검토 줄(확정 전 [채택])이 뷰포트 안
    const detail = page.getByTestId('review-detail');
    await expect(detail).toHaveAttribute('data-item', '25');
    expect(await inViewport(page, page.getByTestId('review-detail-card'))).toBe(
      true,
    );
    if (state === 'pending')
      expect(
        await inViewport(
          page,
          detail
            .getByRole('group', { name: GW_TEXT.review.groupLabel })
            .getByRole('button', { name: GW_TEXT.review.adopted }),
        ),
      ).toBe(true);
    expect(errors).toEqual([]);
  });
}

test('GW-05 역 포커싱(sid:MARC-ISSUE-341): 같은 쪽 문장은 등급 색 1px 상자(hover 2px) — 누르면 그 줄을 고르고 목록이 그 줄로 스크롤, 미리보기는 그대로 · 키보드(Shift+Tab·Enter)로도 · focus-visible outline 2px #8B95A1', async ({
  page,
}) => {
  const { errors, pane } = await openLongReview(page);
  // 맨 아래 문장(3쪽)을 골라 쪽을 내린 뒤 1쪽으로 넘긴다
  await listRow(page, 25).click();
  await expect(pane.getByTestId('page-heading')).toHaveText(
    GW_TEXT.reviewScreen.pageHeading(3),
  );
  // 3쪽의 다른 문장 일곱(18~24)이 옅은 상자, 고른 25 는 highlight
  const boxes = pane.getByTestId('page-box');
  await expect(boxes).toHaveCount(7);
  const first = boxes.first();
  await expect(first).toHaveAttribute('data-item', '18');
  await expect(first).toHaveCSS('border-top-width', '1px');
  await expect(first).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
  await first.hover();
  await expect(first).toHaveCSS('border-top-width', '2px');
  await pane
    .getByRole('button', { name: GW_TEXT.reviewScreen.prevPage })
    .click();
  await pane
    .getByRole('button', { name: GW_TEXT.reviewScreen.prevPage })
    .click();
  await expect(pane.getByTestId('page-heading')).toHaveText(
    GW_TEXT.reviewScreen.pageHeading(1),
  );
  await expect(pane.getByTestId('highlight')).toHaveCount(0);
  await expect(boxes).toHaveCount(9);
  const scrolledBefore = await page.evaluate(() => window.scrollY);
  expect(await inViewport(page, listRow(page, 1))).toBe(false);
  // 1쪽 1번 문장 상자를 누름 → 그 줄 고름 + 목록이 그 줄로(위로) 스크롤, 미리보기는 그 쪽 그대로
  await pane.locator('[data-testid="page-box"][data-item="1"]').click();
  await expect(listRow(page, 1)).toHaveAttribute('aria-current', 'true');
  await expect(page.getByTestId('review-detail')).toHaveAttribute(
    'data-item',
    '1',
  );
  await expect(pane.getByTestId('highlight')).toHaveCount(1);
  await expect.poll(() => inViewport(page, listRow(page, 1))).toBe(true);
  expect(await page.evaluate(() => window.scrollY)).toBeLessThan(
    scrolledBefore,
  );
  // 쪽 맨 위 가까이로 올라오면 칸은 제 자리(흐름)로 돌아가므로 칸 전체가 아니라 하이라이트가 뷰포트 안인지 잰다
  expect(await inViewport(page, pane.getByTestId('highlight'))).toBe(true);
  // 고른 상자를 다시 눌러도 그대로
  await pane.getByTestId('page-box-current').click();
  await expect(listRow(page, 1)).toHaveAttribute('aria-current', 'true');
  // 키보드: 고른 상자에서 Shift+Tab → 앞 상자(목록 차례 마지막 옅은 상자 8번), outline 2px #8B95A1, Enter 로 고름
  await pane.getByTestId('page-box-current').focus();
  await page.keyboard.press('Shift+Tab');
  const focused = pane.locator('[data-testid="page-box"][data-item="8"]');
  await expect(focused).toBeFocused();
  await expect(focused).toHaveCSS('outline-style', 'solid');
  await expect(focused).toHaveCSS('outline-width', '2px');
  await expect(focused).toHaveCSS('outline-color', 'rgb(139, 149, 161)');
  await page.keyboard.press('Enter');
  await expect(listRow(page, 8)).toHaveAttribute('aria-current', 'true');
  await expect.poll(() => inViewport(page, listRow(page, 8))).toBe(true);
  expect(errors).toEqual([]);
});

test('GW-05 서비스 화면 값(GP2 개정 1 — GW3R2 SC1·SC13~16): 고른 줄 왼쪽 막대 3px · 「n쪽」 700 16 · 「검토 n/m」 700 · 「등급」 16 · 줄 꼬리 작은 회색 글 400', async ({
  page,
}) => {
  const { errors, pane } = await openLongReview(page);
  await expect(listRow(page, 0)).toHaveCSS('border-left-width', '3px');
  const heading = pane.getByTestId('page-heading');
  await expect(heading).toHaveCSS('font-weight', '700');
  await expect(heading).toHaveCSS('font-size', '16px');
  await expect(page.getByTestId('review-progress')).toHaveCSS(
    'font-weight',
    '700',
  );
  await expect(
    page
      .getByTestId('review-detail')
      .getByText(GW_TEXT.reviewScreen.edit.levelLabel, { exact: true }),
  ).toHaveCSS('font-size', '16px');
  await expect(page.getByTestId('review-tally')).toHaveCSS(
    'font-weight',
    '400',
  );
  expect(errors).toEqual([]);
});

// ── 첫 불러오기 밀림(밴드 GL1, sid:MARC-ENT-443) ──
// 그린워싱 읽기를 문(gate)으로 붙잡아 두고(조건으로 연다 — 고정 시간 대기 없음), 받기 전·뒤의 제목 줄·그 아래 부품·표 머리줄·첫 줄의
// getBoundingClientRect 를 잰다. 목표: 받은 뒤 아무것도 밀리지 않는다(위·높이 차 ≤ 1px). GL1_SHOTS 가 있으면 그 폴더에 그림과 잰 값.

/** 그린워싱 읽기를 붙잡는다. 돌려준 함수를 부르면 그때부터 흉내 서버로 넘긴다(route 는 나중에 단 것이 이긴다). */
async function holdGreenwashApi(page: Page) {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  for (const glob of [
    '**/api/documents',
    '**/api/documents/**',
    '**/api/runs',
    '**/api/runs/**',
    '**/api/greenwash/**',
  ])
    await page.route(glob, async (route) => {
      await opened;
      await route.fallback();
    });
  return open;
}

type Rects = Record<string, { top: number; height: number } | null>;

/** 화면 틀의 제목 줄(PageTitle)·그 아래 둘·(있으면) 표 머리줄과 첫 줄. */
function measure(page: Page): Promise<Rects> {
  return page.evaluate(() => {
    const rect = (node: Element | null | undefined) => {
      if (!node) return null;
      const box = node.getBoundingClientRect();
      return { top: box.top, height: box.height };
    };
    const screen = document.querySelector('[data-screen]');
    const h2 = screen?.querySelector('h2');
    return {
      h2: rect(h2),
      titleRow: rect(screen?.firstElementChild),
      second: rect(screen?.children[1]),
      third: rect(screen?.children[2]),
      thead: rect(screen?.querySelector('thead')),
      firstRow: rect(screen?.querySelector('tbody tr')),
    };
  });
}

/** 받기 전·뒤 차(위·높이). 두 쪽에 다 있는 자리만. */
function drift(before: Rects, after: Rects, keys: string[]) {
  return Object.fromEntries(
    keys.map((key) => {
      const a = before[key];
      const b = after[key];
      return [
        key,
        a && b ?
          {
            top: Math.round((b.top - a.top) * 10) / 10,
            height: Math.round((b.height - a.height) * 10) / 10,
          }
        : null,
      ];
    }),
  );
}

async function shot(page: Page, name: string, data?: unknown) {
  const dir = process.env.GL1_SHOTS;
  if (!dir) return;
  await page.screenshot({ path: `${dir}/${name}.png` });
  if (data !== undefined)
    writeFileSync(`${dir}/${name}.json`, JSON.stringify(data, null, 2));
}

const settledRun = () =>
  run(13, 3, {
    status: 'done',
    steps: steps(6),
    options: { parts: { ceo: [1], company: [2], climate: [3] } },
    finishedAt: '2026-10-18T10:52:00+09:00',
    result: RESULT,
    review: {
      state: 'in_review',
      marks: [],
      confirmedAt: null,
      confirmedBy: null,
    },
  });

for (const screenCase of [
  {
    name: 'list',
    path: '/greenwash',
    // 받기 전: 표 줄 자리의 막대(300ms 뒤) · 받은 뒤: 진짜 줄
    loading: '[data-skeleton-row] [data-skeleton-bar]',
    ready: 'tbody tr:not([data-skeleton-row])',
    // 줄 수가 다르면 표 아래는 달라진다 — 표 위·머리줄·첫 줄까지
    keys: ['h2', 'titleRow', 'second', 'thead', 'firstRow'],
  },
  {
    name: 'result',
    path: '/greenwash/runs/13/result',
    loading: '[data-testid="result-skeleton"]',
    ready: '[data-result-state="ready"] [data-testid="review-state"]',
    keys: ['h2', 'titleRow', 'second', 'third'],
  },
  {
    name: 'status',
    path: '/greenwash/runs/13',
    loading: '[data-testid="status-skeleton"]',
    ready: '[data-screen="status"][data-run-state="done"]',
    keys: ['h2', 'titleRow', 'second', 'third'],
  },
  {
    name: 'review',
    path: '/greenwash/runs/13/review',
    loading: '[data-testid="review-skeleton"]',
    ready: '[data-testid="sentence-list"]',
    keys: ['h2', 'titleRow', 'second', 'third'],
  },
])
  test(`첫 불러오기 밀림 0(밴드 GL1, sid:MARC-ENT-443): ${screenCase.name} — 받기 전·뒤 제목 줄·그 아래 부품${screenCase.name === 'list' ? '·표 머리줄·첫 줄' : ''}의 위·높이 차 ≤ 1px`, async ({
    page,
  }) => {
    // 실행 있는 문서 다섯(목록 줄 = 스켈레톤 줄 수 — 목록 카드 높이까지 같아야 한다)
    await fakeGreenwashApi(page, {
      documents: [
        doc(3, '지어낸 보고서.pdf', { pageCount: 80, reportYear: 2026 }),
        ...[4, 5, 6, 7].map((id) => doc(id, `지어낸 문서 ${id}.pdf`)),
      ],
      runs: [settledRun(), ...[4, 5, 6, 7].map((id) => run(20 + id, id))],
    });
    const release = await holdGreenwashApi(page);
    const errors = consoleErrors(page);
    await page.goto(screenCase.path);
    await expect(page.locator(screenCase.loading).first()).toBeVisible();
    const before = await measure(page);
    await shot(page, `${screenCase.name}-loading`, before);
    release();
    await expect(page.locator(screenCase.ready).first()).toBeVisible();
    await expect(page.locator('[data-screen][aria-busy]')).toHaveCount(0);
    await expect(page.getByTestId('description-pending')).toHaveCount(0);
    // 끝이 있는 움직임(끝남 카드의 떠오름 등)이 다 끝난 뒤에 잰다
    await page.waitForFunction(() =>
      document
        .getAnimations()
        .every(
          (animation) =>
            animation.playState !== 'running' ||
            animation.effect?.getTiming().iterations === Infinity,
        ),
    );
    const after = await measure(page);
    const moved = drift(before, after, screenCase.keys);
    await shot(page, `${screenCase.name}-ready`, { after, moved });
    for (const key of screenCase.keys) {
      expect(moved[key], key).not.toBeNull();
      expect(Math.abs(moved[key]!.top), `${key} top`).toBeLessThanOrEqual(1);
      // 셋째(본문 첫 부품)는 스켈레톤 카드 → 진짜 내용이라 높이는 다르다 — 위만 본다
      if (key !== 'third')
        expect(
          Math.abs(moved[key]!.height),
          `${key} height`,
        ).toBeLessThanOrEqual(1);
    }
    expect(errors).toEqual([]);
  });

// ── 화면 꼴 스켈레톤(밴드 GL2, sid:MARC-ENT-443) ──
// GL1 의 문(holdGreenwashApi)으로 읽기를 붙잡고 1440×900(LR4 와 같은 창)에서 잰다. 셋째 자식부터 끝까지를 본문으로 보고,
// 받기 전·뒤 본문 높이(셋째 위 → 끝 자식 아래) 차 ≤ 48px, 위쪽(h2·제목 줄·단계 띠)은 위·높이 차 ≤ 1px. GL2_SHOTS 가 있으면 그림과 잰 값.

type Blocks = {
  top: Rects;
  body: { top: number; height: number } | null;
  blocks: { name: string; top: number; height: number }[];
};

/** 위쪽 셋(h2·제목 줄·단계 띠)과 본문(셋째 자식부터 끝까지)의 자리. 블록 이름은 testid · aria-label · 태그. */
function measureBody(page: Page): Promise<Blocks> {
  return page.evaluate(() => {
    const rect = (node: Element | null | undefined) => {
      if (!node) return null;
      const box = node.getBoundingClientRect();
      return { top: box.top, height: box.height };
    };
    const screen = document.querySelector('[data-screen]')!;
    const children = Array.from(screen.children).slice(2);
    const blocks = children.map((node) => {
      const box = node.getBoundingClientRect();
      const name =
        node.getAttribute('data-testid') ??
        node.getAttribute('aria-label') ??
        node.querySelector('[role="tablist"]')?.getAttribute('aria-label') ??
        `${node.tagName.toLowerCase()}.${node.className.split(' ')[0] ?? ''}`;
      return {
        name,
        top: Math.round(box.top * 10) / 10,
        height: Math.round(box.height * 10) / 10,
      };
    });
    const first = children[0]?.getBoundingClientRect();
    const last = children.at(-1)?.getBoundingClientRect();
    return {
      top: {
        h2: rect(screen.querySelector('h2')),
        titleRow: rect(screen.firstElementChild),
        second: rect(screen.children[1]),
      },
      body:
        first && last ?
          { top: first.top, height: last.bottom - first.top }
        : null,
      blocks,
    };
  });
}

async function shotGl2(page: Page, name: string, data: unknown) {
  const dir = process.env.GL2_SHOTS;
  if (!dir) return;
  await page.screenshot({ path: `${dir}/${name}.png`, fullPage: true });
  writeFileSync(`${dir}/${name}.json`, JSON.stringify(data, null, 2));
}

const runningRun = () =>
  run(13, 3, {
    steps: steps(2, { status: 'running', done: 4, total: 10 }),
    options: { parts: { ceo: [1], company: [2], climate: [3] } },
  });

for (const screenCase of [
  {
    name: 'result',
    path: '/greenwash/runs/13/result',
    run: settledRun,
    ready: '[data-result-state="ready"] [data-testid="review-state"]',
  },
  {
    name: 'status-running',
    path: '/greenwash/runs/13',
    run: runningRun,
    ready: '[data-screen="status"][data-run-state="running"]',
  },
  {
    name: 'status-done',
    path: '/greenwash/runs/13',
    run: settledRun,
    ready: '[data-screen="status"][data-run-state="done"]',
    // 꼴은 점검 중 진행 카드 하나라 끝남 카드(106)로 받으면 본문이 줄어든다 — 끝난 실행은 목록에서 결과 화면으로 바로 간다(GL2 감독 판단)
    maxBody: 345,
  },
  {
    name: 'review',
    path: '/greenwash/runs/13/review',
    run: settledRun,
    ready: '[data-testid="sentence-list"]',
    // 준비 뒤 본문 높이는 칸 폭에 맞춘 쪽 그림 높이에 달린다(밴드 GFS1 fitScale — 1440 에서 잰 차 59px). 꼴(스켈레톤)은 6c 그대로
    maxBody: 64,
  },
])
  test(`화면 꼴 스켈레톤(밴드 GL2, sid:MARC-ENT-443): ${screenCase.name} — 받기 전·뒤 위쪽 셋 차 ≤ 1px · 본문 높이 차 ≤ 48px(1440×900)`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await fakeGreenwashApi(page, {
      documents: [doc(3, '지어낸 보고서.pdf', { pageCount: 80 })],
      runs: [screenCase.run()],
    });
    const release = await holdGreenwashApi(page);
    const errors = consoleErrors(page);
    await page.goto(screenCase.path);
    // 300ms 늦추기 뒤 스켈레톤(카드든 화면 꼴이든 role="status" 하나)
    await expect(
      page.locator('[data-screen][aria-busy] [role="status"]'),
    ).toBeVisible();
    const before = await measureBody(page);
    await shotGl2(page, `${screenCase.name}-loading`, before);
    release();
    await expect(page.locator(screenCase.ready).first()).toBeVisible();
    await expect(page.locator('[data-screen][aria-busy]')).toHaveCount(0);
    await page.waitForFunction(() =>
      document
        .getAnimations()
        .every(
          (animation) =>
            animation.playState !== 'running' ||
            animation.effect?.getTiming().iterations === Infinity,
        ),
    );
    const after = await measureBody(page);
    const moved = drift(before.top, after.top, ['h2', 'titleRow', 'second']);
    const body =
      before.body && after.body ?
        {
          top: Math.round((after.body.top - before.body.top) * 10) / 10,
          height:
            Math.round((after.body.height - before.body.height) * 10) / 10,
        }
      : null;
    await shotGl2(page, `${screenCase.name}-ready`, { after, moved, body });
    for (const key of ['h2', 'titleRow', 'second']) {
      expect(moved[key], key).not.toBeNull();
      expect(Math.abs(moved[key]!.top), `${key} top`).toBeLessThanOrEqual(1);
      expect(Math.abs(moved[key]!.height), `${key} height`).toBeLessThanOrEqual(
        1,
      );
    }
    expect(body).not.toBeNull();
    expect(Math.abs(body!.top), 'body top').toBeLessThanOrEqual(1);
    expect(Math.abs(body!.height), 'body height').toBeLessThanOrEqual(
      screenCase.maxBody ?? 48,
    );
    expect(errors).toEqual([]);
  });

// ── 목록 첫 불러오기 표 아래·칸 폭(밴드 GL3, sid:MARC-ISSUE-397·374) ──
// GL1 의 문으로 읽기를 붙잡고 두 창(1440×900·1280×800)에서 줄 2·0 을 받는다. 받기 전·뒤 h2·제목 줄·표 카드·머리줄·(줄 2) 첫 줄의
// 위·높이와 안내 띠(list-notice) 위가 같고(≤ 1px), 머리 칸 폭이 빈 스켈레톤 줄 → 막대 → 진짜 줄 내내 같다(≤ 1px). 가로 넘침은 없다.
// GL3_SHOTS 가 있으면 그 폴더에 그림과 잰 값.

type ListRects = { rects: Rects; widths: number[]; overflow: number };

function measureList(page: Page): Promise<ListRects> {
  return page.evaluate(() => {
    const rect = (node: Element | null | undefined) => {
      if (!node) return null;
      const box = node.getBoundingClientRect();
      return { top: box.top, height: box.height };
    };
    const screen = document.querySelector('[data-screen="list"]')!;
    const notice = screen.querySelector('[data-testid="list-notice"]');
    return {
      rects: {
        h2: rect(screen.querySelector('h2')),
        titleRow: rect(screen.firstElementChild),
        card: rect(screen.children[1]),
        thead: rect(screen.querySelector('thead')),
        firstRow: rect(screen.querySelector('tbody tr')),
        notice: notice && {
          top: notice.getBoundingClientRect().top,
          height: 0,
        },
      },
      widths: Array.from(screen.querySelectorAll('thead th')).map(
        (th) => Math.round(th.getBoundingClientRect().width * 10) / 10,
      ),
      overflow:
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    };
  });
}

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
])
  for (const rowCount of [2, 0])
    test(`목록 첫 불러오기(밴드 GL3, sid:MARC-ISSUE-397·374): ${viewport.width}×${viewport.height} · 줄 ${rowCount} — 받기 전·뒤 표 카드·안내 띠 차 ≤ 1px, 칸 폭 그대로, 가로 넘침 0`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      const ids = [3, 4].slice(0, rowCount);
      await fakeGreenwashApi(page, {
        documents: ids.map((id) => doc(id, `지어낸 문서 ${id}.pdf`)),
        runs: ids.map((id) => run(20 + id, id)),
      });
      const release = await holdGreenwashApi(page);
      const errors = consoleErrors(page);
      const name = `${viewport.width}-rows${rowCount}`;
      const dir = process.env.GL3_SHOTS;
      await page.goto('/greenwash');
      await expect(page.locator('[data-skeleton-row]').first()).toBeAttached();
      const bare = await measureList(page);
      await expect(
        page.locator('[data-skeleton-row] [data-skeleton-bar]').first(),
      ).toBeVisible();
      const before = await measureList(page);
      if (dir) await page.screenshot({ path: `${dir}/${name}-loading.png` });
      release();
      await expect(page.locator('[data-screen][aria-busy]')).toHaveCount(0);
      await expect(page.locator('[data-skeleton-row]')).toHaveCount(0);
      await expect(page.locator('tbody tr')).toHaveCount(Math.max(rowCount, 1));
      const after = await measureList(page);
      const keys = ['h2', 'titleRow', 'card', 'thead', 'notice'].concat(
        rowCount > 0 ? ['firstRow'] : [],
      );
      const moved = drift(before.rects, after.rects, keys);
      if (dir) {
        await page.screenshot({ path: `${dir}/${name}-ready.png` });
        writeFileSync(
          `${dir}/${name}.json`,
          JSON.stringify({ bare, before, after, moved }, null, 2),
        );
      }
      for (const key of keys) {
        expect(moved[key], key).not.toBeNull();
        expect(Math.abs(moved[key]!.top), `${key} top`).toBeLessThanOrEqual(1);
        expect(
          Math.abs(moved[key]!.height),
          `${key} height`,
        ).toBeLessThanOrEqual(1);
      }
      for (const [index, width] of after.widths.entries()) {
        expect(
          Math.abs(width - bare.widths[index]!),
          `칸 ${index} 빈 줄→진짜`,
        ).toBeLessThanOrEqual(1);
        expect(
          Math.abs(width - before.widths[index]!),
          `칸 ${index} 막대→진짜`,
        ).toBeLessThanOrEqual(1);
      }
      expect(after.overflow, '가로 넘침').toBeLessThanOrEqual(0);
      expect(errors).toEqual([]);
    });
