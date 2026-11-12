// 온실가스 Scope 3 첫 화면(S3-01·02·03·07) 시연 길을 빌드 결과에서(밴드 S3W1 ③ — 발주서 §2-3 e2e). 서버는 e2e/ghg-scope3-server.ts 의 흉내
// (page.route — S3K1 판·BASE 판), S2 자리는 e2e/ghg-server.ts 의 흉내. 컨테이너 0. 올릴 파일은 메모리에서 짓는다(디스크에 .xlsx 0).
//   S2 → 「Scope 3」 탭(같은 해 → 범위 밖이라 전년도) → [다음] → C10 못 고름 · 0 이면 [확인] 끔 → 둘 고름 → 「고른 카테고리 2개」 →
//   양식 내려받기(실어댑터 GET 한 번 · 받은 이름 — S3W2a) → 21MB 크기 글(요청 0) → 올림(PUT 바이트·confirm·POST /runs 깊은 같음 —
//   카테고리 0 실림) → 진행 → 완료(S3-08 카드 — S3W2a) · 실패 → 다시 계산(같은 문서·options 새 POST) · 닫고 새로고침 → 재접속 · BASE 판 422·운영 관리자 403 글 ·
//   운영 관리자(S3K1 판) 같은 흐름. S3W2b ③: 카드 누름 → 상세(시트 셋 갈래·일부 실패·쪽·검색·정렬·생물기원·[목록] 초점) · 새로고침 → 목록.
//   S3W4 ③: 상세 그룹·이름 칸 → 그룹별 배출계수 창(AI 그룹 별·규칙·물러선 그룹 별 없음·탄소기원·입력칸 0·틀 960·Esc·X·바깥 누름·초점 돌아옴).
//   S3W3c2 ②: 창 [수정] → 추천·직접 입력·적용 되돌림 → 사유 → 표·카드 합 · C12·잠김·C5 막힘 · 화면이 낸 POST 몸 ↔ openapi 세 갈래 · 사유 창 바깥 누름.
// 흉내 밖 /api/ 요청은 덫(503)으로 적고 끝에 0 인지 본다(ghg-server.spec.ts 꼴).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { S3_TEXT } from '../src/entities/ghg-scope3/config/text.ts';
import { GHG_TEXT } from '../src/entities/ghg/config/text.ts';
import {
  createScope3Ledger,
  e2eRowFactor,
  fakeScope3Api,
} from './ghg-scope3-server.ts';
import {
  E2E_C3_NOTE,
  E2E_C12_CODE,
  E2E_C12_NAME,
  E2E_EDITED_CO2E,
  E2E_ERROR_MESSAGE,
  E2E_GROUP_B,
  E2E_LONE_SITE,
  E2E_REJECT_DETAIL,
  E2E_SHEET_ERROR,
  E2E_SOURCE_TEXT,
  E2E_TREATMENT,
  TEMPLATE_NAME,
  attachmentOf,
  e2eDetailResult,
  e2eDoneResult,
  e2eRejectedResult,
  e2eS3Q1Result,
  e2eSheet,
  e2eTreatments,
  originalMediaType,
} from './ghg-scope3-server.ts';
import type { E2eRowEdit, Scope3ApiOptions } from './ghg-scope3-server.ts';
import { fakeGhgApi } from './ghg-server.ts';
import { signIn } from './session.ts';

const screenWords = S3_TEXT.screen;
const categoryWords = S3_TEXT.categoryDialog;
const uploadWords = S3_TEXT.uploadDialog;
const progressWords = S3_TEXT.progressDialog;
/** 서울 올해와 Scope 3 기본 해(전년도). */
const THIS_YEAR = new Date(Date.now() + 9 * 60 * 60 * 1000).getUTCFullYear();
const LAST = THIS_YEAR - 1;
type Json = Record<string, unknown>;
/** 지어낸 통합 템플릿(「PK」 머리만). */
const XLSX = Buffer.from([80, 75, 3, 4, 5, 5, 5, 5]);
const XLSX_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
/** 진행 → 끝남(폴링 2초)까지 기다림. */
const RUN_WAIT = { timeout: 20_000 };

/** 흉내 밖 /api/ 요청을 적고 503 으로 끊는다(흉내보다 먼저 건다). */
async function trapUnrouted(page: Page) {
  const unrouted: string[] = [];
  await page.route(/\/api\//, (route) => {
    const url = new URL(route.request().url());
    unrouted.push(`${route.request().method()} ${url.pathname}`);
    return route.fulfill({ status: 503, body: '' });
  });
  return unrouted;
}

async function open(
  page: Page,
  kind: 'service' | 'admin' = 'service',
  options: Scope3ApiOptions = {},
) {
  const unrouted = await trapUnrouted(page);
  await fakeGhgApi(page);
  const api = await fakeScope3Api(page, {
    ...options,
    operator: kind === 'admin',
  });
  await signIn(
    page,
    kind === 'admin' ? { kind, username: 'ops.admin' } : { kind },
  );
  return { unrouted, api };
}

const uploadDialog = (page: Page) => page.getByTestId('s3-upload-dialog');
const progressDialog = (page: Page) => page.getByTestId('s3-progress-dialog');

/** [다음] → 카테고리 둘(C1·C6) → [확인] → 올리기 창. */
async function chooseTwo(page: Page) {
  await page.getByRole('button', { name: screenWords.start }).click();
  const dialog = page.getByTestId('s3-category-dialog');
  await expect(dialog).toBeVisible();
  const confirm = dialog.getByRole('button', { name: categoryWords.confirm });
  await expect(confirm).toBeDisabled();
  await dialog
    .getByRole('checkbox', {
      name: categoryWords.item(1, S3_TEXT.categories.C1),
    })
    .click();
  await dialog
    .getByRole('checkbox', {
      name: categoryWords.item(6, S3_TEXT.categories.C6),
    })
    .click();
  await confirm.click();
  await expect(uploadDialog(page)).toBeVisible();
  await expect(page.getByTestId('s3-chosen-count')).toHaveText(
    uploadWords.chosen(2),
  );
}

/** 올리기 창에 파일 하나를 고른다. */
const pickFile = (page: Page, name: string, buffer: Buffer) =>
  uploadDialog(page)
    .locator('input[type="file"]')
    .setInputFiles({ name, mimeType: XLSX_TYPE, buffer });

/** 작은 xlsx 를 고르고 [데이터 업로드]. */
async function uploadSmall(page: Page) {
  await pickFile(page, 'scope3-sample.xlsx', XLSX);
  await uploadDialog(page)
    .getByRole('button', { name: uploadWords.submit })
    .click();
}

test('고객사(S3K1 판): S2 → 「Scope 3」 탭 → 카테고리 둘 → 양식 받음 · 21MB 글 → 올림 → POST /runs 깊은 같음 → 진행 → 카드 15', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await page.goto(`/ghg/inventory?year=${THIS_YEAR}`);
  await expect(page.getByTestId('inventory-empty')).toBeVisible(); // S12-02a: 초기 창 없음
  const scopeTabs = page.getByRole('tablist', { name: S3_TEXT.scopeTabsLabel });
  await expect(
    scopeTabs.getByRole('tab', { name: S3_TEXT.scopeTabs.scope12 }),
  ).toHaveAttribute('aria-selected', 'true');
  await scopeTabs.getByRole('tab', { name: S3_TEXT.scopeTabs.scope3 }).click();
  // 올해는 Scope 3 의 고를 수 있는 해 밖이라 전년도로.
  await expect(page).toHaveURL(new RegExp(`/ghg/scope3\\?year=${LAST}$`));
  await expect(page.locator('[data-screen="ghg-scope3"]')).toBeVisible();
  await expect(
    page.getByRole('tab', { name: GHG_TEXT.inventory.tabs.inventory }),
  ).toHaveAttribute('aria-selected', 'true');
  await expect(
    page.getByRole('combobox', { name: screenWords.yearLabel }),
  ).toHaveValue(`${LAST}`);

  // C10 은 고를 수 없다.
  await page.getByRole('button', { name: screenWords.start }).click();
  await expect(
    page.locator('[data-category="C10"]').getByRole('checkbox'),
  ).toBeDisabled();
  await page
    .getByTestId('s3-category-dialog')
    .getByRole('button', { name: categoryWords.cancel })
    .click();
  await chooseTwo(page);

  // 양식: 실어댑터가 GET /inventory/scope3/template 을 받는다(S3W2a Q2).
  const download = page.waitForEvent('download');
  await uploadDialog(page)
    .getByRole('button', { name: uploadWords.templateDownload })
    .click();
  expect((await download).suggestedFilename()).toBe(TEMPLATE_NAME);
  await expect(
    uploadDialog(page).getByText(uploadWords.templateFailed),
  ).toHaveCount(0);
  expect(api.count('GET /inventory/scope3/template')).toBe(1);

  // 21MB → 크기 글, 요청 0.
  await pickFile(page, 'big.xlsx', Buffer.alloc(21 * 1024 * 1024));
  await expect(page.getByTestId('s3-upload-problem')).toHaveText(
    S3_TEXT.fileProblem.size,
  );
  expect(api.count('POST /documents')).toBe(0);

  await uploadSmall(page);
  await expect(progressDialog(page)).toBeVisible();
  expect(api.calls.find((call) => call.path === '/documents')!.body).toEqual({
    fileName: 'scope3-sample.xlsx',
    sizeBytes: XLSX.length,
    reportYear: LAST,
  });
  const put = api.calls.find((call) =>
    call.path.startsWith('/fake-upload-s3/'),
  )!;
  expect(put.method).toBe('PUT');
  expect(put.size).toBe(XLSX.length);
  expect(put.authorization).toBeNull();
  expect(api.count('POST /documents/31/confirm')).toBe(1);
  const [run] = api.runBodies();
  expect(run).toEqual({
    module: 'inventory.scope3',
    flowId: 'scope3.colab@157',
    documentId: 31,
    launchKey: expect.any(String),
    options: { reportYear: LAST },
  });
  // 고른 카테고리는 화면 표시만 — 어느 요청에도 실리지 않는다.
  expect(JSON.stringify(api.calls.map((call) => call.body))).not.toMatch(
    /"C[0-9]+"/,
  );

  await expect(page.getByTestId('s3-done')).toBeVisible(RUN_WAIT);
  await expect(
    page.getByTestId('s3-done').getByTestId('s3-result-card'),
  ).toHaveCount(15);
  await expect(progressDialog(page)).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('실패 → [배출량 재계산하기] → 같은 문서·options 로 새 POST(이어 돌기 0) → 완료', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'service', {
    runScripts: [
      ['processing', 'failed'],
      ['processing', 'done'],
    ],
  });
  await page.goto(`/ghg/scope3?year=${LAST}`);
  await chooseTwo(page);
  await uploadSmall(page);
  await expect(progressDialog(page)).toHaveAttribute(
    'data-view',
    'failed',
    RUN_WAIT,
  );
  await expect(progressDialog(page).getByRole('alert').first()).toHaveText(
    progressWords.failedTitle,
  );
  await progressDialog(page)
    .getByRole('button', { name: progressWords.retry })
    .click();
  await expect(page.getByTestId('s3-done')).toBeVisible(RUN_WAIT);
  const bodies = api.runBodies();
  expect(bodies).toHaveLength(2);
  const strip = ({ launchKey: _key, ...rest }: Record<string, unknown>) => rest;
  expect(strip(bodies[1]!)).toEqual(strip(bodies[0]!));
  expect(bodies[1]).not.toHaveProperty('resumeFromRunId');
  expect(bodies[1]!.launchKey).not.toBe(bodies[0]!.launchKey);
  expect(api.count('POST /documents')).toBe(1);
  expect(unrouted).toEqual([]);
});

test('진행 중 창을 닫음 → 화면 진행 글 → 새로고침 → 재접속(진행 창 다시)', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runScripts: [['processing']],
  });
  await page.goto(`/ghg/scope3?year=${LAST}`);
  await chooseTwo(page);
  await uploadSmall(page);
  await expect(progressDialog(page)).toHaveAttribute('data-view', 'running');
  await progressDialog(page)
    .getByRole('button', { name: progressWords.close })
    .click();
  await expect(progressDialog(page)).toHaveCount(0);
  await expect(page.getByTestId('s3-running')).toBeVisible();
  await page.reload();
  await expect(progressDialog(page)).toHaveAttribute(
    'data-view',
    'running',
    RUN_WAIT,
  );
  await expect(
    page.getByRole('button', { name: screenWords.start, includeHidden: true }),
  ).toBeDisabled();
  expect(unrouted).toEqual([]);
});

test('진행 셈: 흉내 steps 가 바뀌면 창의 수가 따라가고 창을 닫아도 화면에 같은 줄', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runScripts: [Array(8).fill('processing')],
  });
  await page.goto(`/ghg/scope3?year=${LAST}`);
  await chooseTwo(page);
  await uploadSmall(page);
  const line = progressDialog(page).getByTestId('s3-progress-count');
  await expect(line).toHaveText(progressWords.countDone(14, 1), RUN_WAIT);
  await expect(line).toHaveText(progressWords.countDone(14, 2), RUN_WAIT);
  await shoot(page, 'progress');
  await progressDialog(page)
    .getByRole('button', { name: progressWords.close })
    .click();
  await expect(
    page.getByTestId('s3-running').getByTestId('s3-progress-count'),
  ).toHaveText(progressWords.countDone(14, 3), RUN_WAIT);
  expect(unrouted).toEqual([]);
});

test('빈 해 안내: 다른 해에 결과가 있으면 띠 → [Y년 보기] → 그 해 결과 · 어느 해에도 없으면 띠 없음', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  await page.goto(`/ghg/scope3?year=${LAST}`);
  await expect(
    page.getByRole('button', { name: screenWords.start }),
  ).toBeVisible();
  await expect(page.getByTestId('s3-year-hint')).toHaveCount(0);
  await page.goto(`/ghg/scope3?year=${LAST - 2}`);
  await chooseTwo(page);
  await uploadSmall(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await page.goto(`/ghg/scope3?year=${LAST}`);
  const line = page.getByTestId('s3-year-hint');
  await expect(line).toContainText(screenWords.yearHint(LAST, LAST - 2));
  await shoot(page, 'year-hint');
  await line
    .getByRole('button', { name: screenWords.yearHintGo(LAST - 2) })
    .click();
  await expect(page).toHaveURL(new RegExp(`year=${LAST - 2}`));
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await expect(line).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('BASE 판: 고객사 422 → 「아직 … 시작할 수 없어요」(문서는 남음)', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'service', { server: 'base' });
  await page.goto(`/ghg/scope3?year=${LAST}`);
  await chooseTwo(page);
  await uploadSmall(page);
  await expect(page.getByTestId('s3-upload-problem')).toHaveText(
    uploadWords.flowNotRunnable,
  );
  expect(api.count('POST /documents')).toBe(1);
  expect(api.count('POST /documents/31/confirm')).toBe(1);
  expect(api.runBodies()).toHaveLength(1);
  await expect(progressDialog(page)).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('BASE 판 운영 관리자: 403 → 「운영 관리자는 아직 … 시작할 수 없어요」', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'admin', { server: 'base' });
  await page.goto(`/ghg/scope3?year=${LAST}`);
  await chooseTwo(page);
  await uploadSmall(page);
  await expect(page.getByTestId('s3-upload-problem')).toHaveText(
    uploadWords.operatorForbidden,
  );
  expect(unrouted).toEqual([]);
});

test('운영 관리자(S3K1 판): 같은 화면·같은 흐름 → 완료', async ({ page }) => {
  const { unrouted, api } = await open(page, 'admin');
  await page.goto(`/ghg/scope3?year=${LAST}`);
  await expect(page.getByText(GHG_TEXT.shell.adminGreeting)).toBeVisible();
  await chooseTwo(page);
  await uploadSmall(page);
  await expect(page.getByTestId('s3-done')).toBeVisible(RUN_WAIT);
  expect(api.runBodies()[0]!.options).toEqual({ reportYear: LAST });
  expect(unrouted).toEqual([]);
});

// ── S3W2a ③ — S3-08 카드 · 실패 수 · rejected · 실패 갈래 · 운영 관리자 · 새로고침 · 흉내 ↔ openapi ──
const resultWords = S3_TEXT.result;
const card = (page: Page, id: string) =>
  page.locator(`[data-testid="s3-result-card"][data-category="${id}"]`);
const total = (page: Page, id: string) =>
  card(page, id).getByTestId('s3-card-total');

/** 올림 → 실행 → 끝(카테고리 둘). */
async function runOnce(page: Page) {
  await page.goto(`/ghg/scope3?year=${LAST}`);
  await chooseTwo(page);
  await uploadSmall(page);
}

test('S3-08: 올림 → 진행 → 카드 15(지수 <0.001 · 긴 꼬리 · 시트 둘 합 · C10·빈 「-」 · 생물기원 둘째 줄) · C10 빼고 눌림(S3W2b) · 새로고침해도 카드', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await runOnce(page);
  const done = page.getByTestId('s3-done');
  await expect(done.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await expect(total(page, 'C1')).toHaveText('<0.001tCO2eq');
  await expect(total(page, 'C3')).toHaveText('0.3tCO2eq');
  await expect(total(page, 'C4')).toHaveText('1,234.75tCO2eq');
  await expect(total(page, 'C10')).toHaveText(resultWords.empty);
  await expect(total(page, 'C14')).toHaveText(resultWords.empty);
  await expect(card(page, 'C5').getByTestId('s3-card-biogenic')).toHaveText(
    `${resultWords.biogenicLabel} 0.5 tCO2eq`,
  );
  await expect(card(page, 'C12').getByTestId('s3-card-biogenic')).toHaveText(
    `${resultWords.biogenicLabel} <0.001 tCO2eq`,
  );
  await expect(page.getByTestId('s3-card-biogenic')).toHaveCount(2);
  await expect(card(page, 'C1')).toContainText(resultWords.cards.C1);
  await expect(page.getByTestId('s3-result-notice')).toHaveText(
    'AI 제안값은 참고용이에요. 최종 값은 담당자가 직접 확인해 주세요',
  );
  await expect(page.getByTestId('s3-problems')).toHaveCount(0);
  // 카드 합 글꼴(S3W2c ② e6 대조 1·3 — 24/700 brand, 단위 14/400 tertiary).
  const sum = total(page, 'C4').locator('span');
  await expect(sum.first()).toHaveClass(
    'text-style-pre-display-04 text-text-brand tabular-nums',
  );
  await expect(sum.nth(1)).toHaveClass(
    'text-style-pre-body-05 text-text-tertiary',
  );
  // S3W2b ②: C10 빼고 카드 열넷이 단추(상세는 아래 S3-09 시험들).
  await expect(
    page.getByTestId('s3-result-card').getByRole('button'),
  ).toHaveCount(14);
  await expect(card(page, 'C10').getByRole('button')).toHaveCount(0);
  await expect(
    page.getByTestId('s3-result-card').getByRole('link'),
  ).toHaveCount(0);
  await card(page, 'C1').getByRole('button').click();
  await expect(page.getByTestId('s3-detail')).toHaveAttribute(
    'data-category',
    'C1',
  );
  await page.getByTestId('s3-detail-back').click();
  await expect(done.getByTestId('s3-result-card')).toHaveCount(15);
  await expect(page.getByTestId('s3-steps')).toHaveCount(0);
  expect(api.count('GET /inventory/scope3/runs/51/result')).toBe(1);
  await page.reload();
  await expect(done.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await expect(total(page, 'C4')).toHaveText('1,234.75tCO2eq');
  expect(api.count('GET /inventory/scope3/runs/51/result')).toBe(2);
  expect(unrouted).toEqual([]);
});

test('S3-08: done 안의 실패 수 한 줄(시트 1 · AI 호출 2) · 실패 카드 「계산 실패」 · 시트 오류 글 0', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eDoneResult({ problems: true })],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-problems')).toHaveText(
    '시트 1개와 일부 줄을 계산하지 못했어요',
    RUN_WAIT,
  );
  await expect(total(page, 'C15')).toHaveText(resultWords.cardFailed);
  await expect(page.locator('body')).not.toContainText(E2E_SHEET_ERROR);
  expect(unrouted).toEqual([]);
});

test('rejected → 카드 0 · 까닭 글(detail 0) · [데이터 업로드] → 카테고리 창', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eRejectedResult('legacy_template')],
  });
  await runOnce(page);
  const box = page.getByTestId('s3-rejected');
  await expect(box).toContainText(
    resultWords.rejected.legacy_template,
    RUN_WAIT,
  );
  await expect(page.getByTestId('s3-result-card')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText(E2E_REJECT_DETAIL);
  await box.getByRole('button', { name: resultWords.upload }).click();
  await expect(page.getByTestId('s3-category-dialog')).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('실패 setup_error → 창에 설정 글 + [닫기]만(S3W2c ② 11) · 닫으면 화면 줄도 같은 글·단추 0 · 서버 글 0', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runScripts: [['processing', 'failed']],
    runErrors: ['setup_error'],
  });
  await runOnce(page);
  const dialog = progressDialog(page);
  await expect(dialog).toHaveAttribute('data-view', 'failed', RUN_WAIT);
  await expect(dialog).toContainText(
    '지금은 계산할 수 없어요. 운영 관리자에게 알려 주세요',
  );
  await expect(
    dialog.getByRole('button', { name: progressWords.retry }),
  ).toHaveCount(0);
  await expect(
    dialog.getByRole('button', { name: resultWords.upload }),
  ).toHaveCount(0);
  // 본문의 [닫기](✕ 와 같은 이름 — 둘 다 닫는다).
  const closes = dialog.getByRole('button', { name: progressWords.close });
  await expect(closes).toHaveCount(2);
  await closes.last().click();
  await expect(dialog).toHaveCount(0);
  const line = page.getByTestId('s3-failed');
  await expect(line.getByTestId('s3-failed-body')).toHaveText(
    progressWords.failureBody.setup,
  );
  await expect(line.getByRole('button')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText(E2E_ERROR_MESSAGE);
  expect(unrouted).toEqual([]);
});

test('실패 file(object_missing) → [재계산] 0 · [데이터 업로드] → 카테고리 창', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'service', {
    runScripts: [['processing', 'failed']],
    runErrors: ['object_missing'],
  });
  await runOnce(page);
  const dialog = progressDialog(page);
  await expect(dialog).toHaveAttribute('data-view', 'failed', RUN_WAIT);
  await expect(dialog).toContainText(progressWords.failureBody.file);
  await expect(
    dialog.getByRole('button', { name: progressWords.retry }),
  ).toHaveCount(0);
  await dialog.getByRole('button', { name: resultWords.upload }).click();
  await expect(page.getByTestId('s3-category-dialog')).toBeVisible();
  expect(api.runBodies()).toHaveLength(1);
  expect(unrouted).toEqual([]);
});

test('done 인데 결과 없음(404) → 「불러오지 못했어요」 + [데이터 업로드] → 카테고리 창(S3W2a ⑤)', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'service', {
    runResults: [null],
  });
  await runOnce(page);
  const failed = page.getByTestId('s3-result-failed');
  await expect(failed).toContainText(resultWords.loadFailed, RUN_WAIT);
  expect(api.count('GET /inventory/scope3/runs/51/result')).toBe(1);
  await failed.getByRole('button', { name: resultWords.upload }).click();
  await expect(page.getByTestId('s3-category-dialog')).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('운영 관리자(S3K1 판): 같은 흐름 → 카드 15', async ({ page }) => {
  const { unrouted } = await open(page, 'admin');
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await expect(total(page, 'C4')).toHaveText('1,234.75tCO2eq');
  expect(unrouted).toEqual([]);
});

// ── S3W2b ③ — 카드 누름 → 상세 S3-09·S3-10 · 시트 셋 갈래 · 검색·정렬·쪽 · [목록] 초점 · 일부 실패 카드 · 새로고침 → 목록 ──
const detailWords = S3_TEXT.detail;
const detail = (page: Page) => page.getByTestId('s3-detail');
const sheetOf = (page: Page, name: string) =>
  detail(page).locator(`[data-testid="s3-sheet"][data-sheet="${name}"]`);
const rowsOf = (page: Page, name: string) =>
  sheetOf(page, name).getByTestId('s3-row');
/** 그 시트 표의 n 번째 데이터 열 칸 글(보이는 쪽 — 앞 체크 열을 뺀 번호, S3W3b). */
const columnOf = (page: Page, name: string, n: number) =>
  rowsOf(page, name).locator(`td:nth-child(${n + 2})`);
/** 시트 표의 데이터 열 머리(앞 체크·뒤 히스토리 열을 뺌 — 두 열은 S3W3b 시험이 본다). */
const dataHeads = (page: Page, name: string) =>
  sheetOf(page, name).locator('th:not(:first-child):not(:last-child)');
/** 머리 글로 열을 찾아 그 칸들(열 차례가 바뀌어도 단언이 열을 놓치지 않게 — S3W2c). */
const columnBy = async (page: Page, name: string, header: string) => {
  const heads = await sheetOf(page, name)
    .getByRole('columnheader')
    .allTextContents();
  const n = heads.indexOf(header);
  expect(n, `${name} 머리 ${header}`).toBeGreaterThanOrEqual(0);
  return columnOf(page, name, n - 1);
};
const E = '온실가스 배출량(tCO2eq)';
const openCard = async (page: Page, id: string) => {
  await card(page, id).getByRole('button').click();
  await expect(detail(page)).toHaveAttribute('data-category', id);
  // 열면 초점은 [목록](감독 처분 R6).
  await expect(detail(page).getByTestId('s3-detail-back')).toBeFocused();
};
const back = async (page: Page, id: string) => {
  await detail(page).getByTestId('s3-detail-back').click();
  await expect(card(page, id).getByRole('button')).toBeFocused();
};

test('S3-09: 카드 누름 → 상세(시트 둘 + 실패 하나 · empty) · 일부 실패 카드 합 · [목록] 초점 · C10 안 눌림 · 서버 글 0', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eDetailResult()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  // 일부 실패 카드: 성공 시트 합(4 + 1) + 둘째 줄.
  await expect(total(page, 'C4')).toHaveText('5tCO2eq');
  await expect(card(page, 'C4').getByTestId('s3-card-partial')).toHaveText(
    resultWords.cardPartial(1),
  );
  await expect(card(page, 'C10').getByRole('button')).toHaveCount(0);
  await expect(
    page.getByTestId('s3-result-card').getByRole('button'),
  ).toHaveCount(14);

  await openCard(page, 'C4');
  const four = detail(page).getByTestId('s3-sheet');
  await expect(four).toHaveCount(3);
  await expect(four.locator('h4')).toHaveText([
    e2eSheet('C4-1'),
    e2eSheet('C4-2'),
    `${e2eSheet('C4-2')} 둘`,
  ]);
  await expect(four.nth(2)).toHaveAttribute('data-status', 'failed');
  await expect(four.nth(2).getByTestId('s3-sheet-reason')).toHaveText(
    detailWords.sheetFailed,
  );
  await expect(detail(page).getByTestId('s3-detail-partial')).toHaveText(
    resultWords.cardPartial(1),
  );
  await expect(page.locator('body')).not.toContainText(E2E_SHEET_ERROR);
  await back(page, 'C4');

  await openCard(page, 'C6');
  const six = detail(page).getByTestId('s3-sheet');
  await expect(six.nth(2)).toHaveAttribute('data-status', 'empty');
  await expect(six.nth(2).getByTestId('s3-sheet-reason')).toHaveText(
    detailWords.sheetEmpty,
  );
  await back(page, 'C6');
  expect(unrouted).toEqual([]);
});

test('S3-09: C1 55 줄 — 행 번호 · 줄 그대로 · 쪽 50 · 검색은 쪽 앞(첫 쪽으로) · 정렬은 쪽 앞 · 새로고침 → 목록', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eDetailResult()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C1');
  const c1 = e2eSheet('C1');
  await expect(rowsOf(page, c1)).toHaveCount(50);
  // 행 번호 차례: 서버 끝에 있던 같은 엑셀 줄 둘(#1·#2 → 4 · 4-2)이 첫 쪽 맨 앞.
  await expect(columnOf(page, c1, 0).first()).toHaveText('4');
  await expect(columnOf(page, c1, 0).nth(1)).toHaveText('4-2');
  await expect(columnOf(page, c1, 0).nth(2)).toHaveText('5');
  await expect((await columnBy(page, c1, E)).nth(2)).toHaveText('<0.001');
  await expect(detail(page).getByTestId('s3-page')).toHaveText(
    detailWords.pageStatus(1, 2),
  );
  await detail(page)
    .getByRole('button', { name: detailWords.nextPage })
    .click();
  await expect(rowsOf(page, c1)).toHaveCount(5);
  await expect(columnOf(page, c1, 0)).toHaveText([
    '53',
    '54',
    '55',
    '56',
    '57',
  ]);
  // 검색 → 첫 쪽 · 그룹 나 줄만(26 — 쪽 하나).
  await detail(page)
    .getByRole('textbox', { name: detailWords.searchLabel })
    .fill('묶음 나');
  await expect(rowsOf(page, c1)).toHaveCount(26);
  await expect(detail(page).getByTestId('s3-pager')).toHaveCount(0);
  await expect(await columnBy(page, c1, '그룹명')).toHaveText(
    Array.from({ length: 26 }, () => E2E_GROUP_B),
  );
  await detail(page)
    .getByRole('textbox', { name: detailWords.searchLabel })
    .fill('');
  // 정렬: 배출량 내림 → 첫 쪽 첫 줄이 전체 최대(52 — 둘째 쪽에 있던 줄).
  const head = sheetOf(page, c1).getByRole('columnheader', {
    name: /온실가스 배출량/,
  });
  await head.getByRole('button').click();
  await head.getByRole('button').click();
  await expect(head).toHaveAttribute('aria-sort', 'descending');
  await expect((await columnBy(page, c1, E)).first()).toHaveText('52');
  await page.reload();
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await expect(detail(page)).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('S3-10: C5 생물기원 칸·띠(tCO2eq) · FCF %(×100) · 처리 방법 · 추정 표시 · C6-1 왕복계수 열', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eDetailResult()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C5');
  await expect(detail(page).getByTestId('s3-detail-biogenic')).toHaveText(
    '2tCO2eq',
  );
  // [Figma] 띠 글 — 카드 합 4 · 생물기원 합 2(S3W2c ② Q9).
  const notice = detail(page).getByTestId('s3-biogenic-notice');
  await expect(notice).toHaveText(
    '총 배출량 4 tCO2eq는 생물기원 CO2 2 tCO2eq를 제외한 값입니다. 매립 배출원은 재질과 무관하게 화석기원으로 전량 포함됩니다.',
  );
  await expect(notice).toHaveAttribute('data-tone', 'important');
  // S3R3 Q7(e6 506 ②): 이 띠만 글자색 brand(공용 important 의 orange-dark 빠짐, 글자 꼴 그대로).
  await expect(notice).toHaveClass(/(^| )text-text-brand( |$)/);
  await expect(notice).not.toHaveClass(/text-support-orange-dark/);
  await expect(notice).toHaveClass(/(^| )text-style-pre-body-06( |$)/);
  // S3R3 Q6(e6 F1) 꼬리: 배출량 → 비율 → 생물기원 → 계수 → FCF.
  await expect(dataHeads(page, e2eSheet('C5'))).toHaveText([
    '행',
    '사업장명',
    '폐기물',
    '처리 방법',
    '연간처리량',
    E,
    '배출량 비율',
    '생물기원 CO2(tCO2eq)',
    '배출계수',
    'FCF',
  ]);
  await expect(
    detail(page).getByRole('textbox', { name: detailWords.searchLabel }),
  ).toHaveAttribute('placeholder', '검색');
  const c5 = e2eSheet('C5');
  await expect(await columnBy(page, c5, '처리 방법')).toHaveText([
    E2E_TREATMENT,
    '흉내 다른 처리',
  ]);
  await expect(await columnBy(page, c5, E)).toHaveText(['3추정', '1']);
  await expect(await columnBy(page, c5, '생물기원 CO2(tCO2eq)')).toHaveText([
    '1.5',
    '0.5',
  ]);
  await expect(await columnBy(page, c5, 'FCF')).toHaveText(['20%', '20%']);
  await shoot(page, 'c5-table');
  await back(page, 'C5');
  await openCard(page, 'C6');
  await expect(dataHeads(page, e2eSheet('C6-1'))).toContainText([
    '이동거리(km)',
    '왕복계수',
  ]);
  expect(unrouted).toEqual([]);
});

test('S3-09 입력 열(S3W2c): 국가·사업장·이름·수단·면적·판매량·중량 · 옛 줄 「-」 · 입력 글로 검색 · 수 입력 열 정렬', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eDetailResult()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C1');
  const c1 = e2eSheet('C1');
  await expect(dataHeads(page, c1)).toHaveText([
    '행',
    '국가',
    '사업장',
    '그룹명',
    '품목명',
    '연간지출금액(원)',
    E,
    '배출량 비율',
    '배출계수',
    '출처',
  ]);
  await expect((await columnBy(page, c1, '국가')).nth(2)).toHaveText(
    '흉내 나라 C1',
  );
  await expect((await columnBy(page, c1, '품목명')).nth(2)).toHaveText(
    '흉내 이름 C1',
  );
  // 옛 줄(첫 쪽 앞 — input 칸 없음)은 입력 열만 「-」, 배출량은 그대로.
  await expect((await columnBy(page, c1, '행')).nth(1)).toHaveText('4-2');
  await expect((await columnBy(page, c1, '국가')).nth(1)).toHaveText('-');
  await expect((await columnBy(page, c1, '사업장')).nth(1)).toHaveText('-');
  await expect((await columnBy(page, c1, E)).nth(1)).toHaveText('0.25');
  await detail(page)
    .getByRole('button', { name: detailWords.nextPage })
    .click();
  // 입력 글로 검색 → 그 줄 하나(첫 쪽으로).
  await detail(page)
    .getByRole('textbox', { name: detailWords.searchLabel })
    .fill('외딴');
  await expect(rowsOf(page, c1)).toHaveCount(1);
  await expect(await columnBy(page, c1, '사업장')).toHaveText([E2E_LONE_SITE]);
  await expect(await columnBy(page, c1, '행')).toHaveText(['6']);
  await back(page, 'C1');
  await openCard(page, 'C6');
  const c62 = e2eSheet('C6-2');
  await expect(await columnBy(page, c62, '출장주체')).toHaveText([
    '흉내 사업장 C6-2',
  ]);
  await expect(await columnBy(page, c62, '출장항목')).toHaveText([
    '흉내 수단 C6-2',
  ]);
  await expect(await columnBy(page, c62, '인원수')).toHaveText(['6']);
  await back(page, 'C6');
  await openCard(page, 'C8');
  const c82 = e2eSheet('C8-2');
  await expect(await columnBy(page, c82, '건물전체 면적')).toHaveText(['250']);
  await expect(await columnBy(page, c82, '사용 면적')).toHaveText(['50']);
  await expect(await columnBy(page, c82, '에너지 종류')).toHaveText([
    '흉내 에너지 C8-2',
  ]);
  await back(page, 'C8');
  await openCard(page, 'C12');
  const c12 = e2eSheet('C12');
  await expect(await columnBy(page, c12, '판매량')).toHaveText(['3,400']);
  await expect(await columnBy(page, c12, '제품 중량')).toHaveText(['1.5 g']);
  await back(page, 'C12');
  // S3R3 Q4·Q5: C11 두 열 — 제품당 연간 에너지 사용량(줄 activity) · 평균사용기간 (개월)(input.useMonths). !3 은 키 열다섯 옛 줄 「-」.
  await openCard(page, 'C11');
  const c11 = e2eSheet('C11');
  await expect(dataHeads(page, c11)).toHaveText([
    '행',
    '제품명',
    '제품수량',
    '에너지명',
    '제품당 연간 에너지 사용량',
    '평균사용기간 (개월)',
    E,
    '배출량 비율',
    '배출계수',
  ]);
  await expect(await columnBy(page, c11, '행')).toHaveText(['3', '4']);
  await expect(await columnBy(page, c11, '평균사용기간 (개월)')).toHaveText([
    '-',
    '30.5',
  ]);
  await expect(
    await columnBy(page, c11, '제품당 연간 에너지 사용량'),
  ).toHaveText(['1 kg', '1 kg']);
  await expect(await columnBy(page, c11, '제품수량')).toHaveText(['9', '9']);
  await back(page, 'C11');
  // S3R3 Q6: C3 꼬리(생물기원 없음) — 배출량 → 비율 → 계수.
  await openCard(page, 'C3');
  await expect(dataHeads(page, e2eSheet('C3'))).toHaveText([
    '행',
    '연료·에너지명',
    '연간 사용량',
    E,
    '배출량 비율',
    '배출계수',
  ]);
  await back(page, 'C3');
  await openCard(page, 'C15');
  await expect(await columnBy(page, e2eSheet('C15'), '기업명')).toHaveText([
    '흉내 이름 C15',
  ]);
  await expect(
    sheetOf(page, e2eSheet('C15')).getByRole('columnheader', {
      name: '배출계수',
      exact: true,
    }),
  ).toHaveCount(0);
  await back(page, 'C15');
  // 수 입력 열(가맹점 수) 정렬: 오름 2 · 15, 내림 15 · 2.
  await openCard(page, 'C14');
  const c14 = e2eSheet('C14');
  const stores = sheetOf(page, c14).getByRole('columnheader', {
    name: /가맹점 수/,
  });
  await stores.getByRole('button').click();
  await expect(stores).toHaveAttribute('aria-sort', 'ascending');
  await expect(await columnBy(page, c14, '가맹점 수')).toHaveText(['2', '15']);
  await stores.getByRole('button').click();
  await expect(await columnBy(page, c14, '가맹점 수')).toHaveText(['15', '2']);
  expect(unrouted).toEqual([]);
});

test('운영 관리자(S3K1 판): 같은 길 — 카드 누름 → 상세 → [목록]', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'admin', {
    runResults: [e2eDetailResult()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C12');
  await expect(detail(page).getByTestId('s3-detail-biogenic')).toHaveText(
    '0.75tCO2eq',
  );
  await back(page, 'C12');
  expect(unrouted).toEqual([]);
});

// ── S3W4 ③ — 상세 칸 → S3-12 그룹별 배출계수 창(읽기 전용) ──
const windowWords = detailWords.factorWindow;
const factorWindow = (page: Page) =>
  page.getByRole('dialog', { name: windowWords.title });
/** 사진 자리(러너 손 확인용 — 값이 없으면 찍지 않는다). */
const SHOTS = process.env.S3W4_SHOTS;
const shoot = async (page: Page, name: string) => {
  if (!SHOTS) return;
  for (const width of [1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    // 여는 움직임(200ms)이 끝난 그림.
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${SHOTS}/${name}-${width}.png` });
  }
};

test('S3-12: C1 AI 그룹 칸 → 창(별·기준단위·출처·계수·틀 960 · 보기 꼴 [수정] 80×36·입력칸 0) · Esc·X·바깥 누름 → 초점은 누른 칸', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eDetailResult()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C1');
  // 행 번호 차례라 앞 둘은 4 · 4-2 — 시드의 첫 줄(AI 그룹)은 셋째.
  const opener = rowsOf(page, e2eSheet('C1'))
    .nth(2)
    .getByTestId('s3-window-open');
  await opener.click();
  const box = factorWindow(page);
  await expect(box).toBeVisible();
  await expect(
    box.getByRole('img', { name: windowWords.aiGroup }),
  ).toHaveAttribute('title', windowWords.aiGroup);
  await expect(box.getByTestId('s3-window-basic')).toContainText(
    windowWords.won,
  );
  await expect(box.getByTestId('s3-window-basic')).toContainText('US EPA');
  await expect(box.getByTestId('s3-window-basic')).toContainText('흉내 식');
  await expect(box.getByTestId('s3-window-carbon')).toHaveCount(0);
  await expect(box.getByRole('columnheader')).toHaveText([
    '타이틀',
    '배출계수 (kg CO2e /원)',
    '출처',
  ]);
  await expect(box.locator('tbody td')).toHaveText([
    '흉내 항목',
    '0.1',
    'US EPA',
  ]);
  // 틀 960(공용 lg 를 덮음) · 보기 꼴 입력칸 0 · 단추는 닫기와 [수정] 둘(S3W3c2 — [수정] btn--md 80×36).
  expect(await box.evaluate((one: HTMLElement) => one.offsetWidth)).toBe(960);
  await expect(box.getByRole('button')).toHaveCount(2);
  const edit = box.getByTestId('s3-factor-edit');
  await expect(edit).toHaveText('수정');
  // 여는 애니메이션의 scale 을 피해 틀 크기(offset)로 잰다 — 960 과 같은 셈.
  expect(
    await edit.evaluate((one: HTMLElement) => [
      one.offsetWidth,
      one.offsetHeight,
    ]),
  ).toEqual([80, 36]);
  await expect(box.locator('input, select, textarea')).toHaveCount(0);
  await shoot(page, 'c1-ai');
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.keyboard.press('Escape');
  await expect(box).toHaveCount(0);
  await expect(opener).toBeFocused();
  // 키보드로 다시 열고 X.
  await page.keyboard.press('Enter');
  await expect(box).toBeVisible();
  await box.getByRole('button', { name: windowWords.close }).click();
  await expect(box).toHaveCount(0);
  await expect(opener).toBeFocused();
  // 바깥 누름.
  await page.keyboard.press('Space');
  await expect(box).toBeVisible();
  // 연 직후 자동 클릭으로는 안 닫힘(e2e 2회 관찰), 움직임 끝난 뒤엔 닫힘. 원인 미확정.
  await box.evaluate((one) =>
    Promise.all(one.getAnimations().map((motion) => motion.finished)),
  );
  await page.mouse.click(8, 8);
  await expect(box).toHaveCount(0);
  await expect(opener).toBeFocused();
  expect(unrouted).toEqual([]);
});

test('S3-12: 규칙·물러선 그룹 별 없음 · C5 탄소기원(FCF 끝 0 뺀 %) · C12 「해당없음」·빈 산식 · 입력칸 0', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eDetailResult()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  const box = factorWindow(page);
  const openRow = async (sheet: string, n: number) => {
    await rowsOf(page, sheet).nth(n).getByTestId('s3-window-open').click();
    await expect(box).toBeVisible();
  };
  await openCard(page, 'C1');
  for (const n of [3, 4]) {
    await openRow(e2eSheet('C1'), n);
    await expect(box.getByTestId('s3-ai-star')).toHaveCount(0);
    if (n === 3) await shoot(page, 'c1-rule');
    await page.setViewportSize({ width: 1400, height: 900 });
    await page.keyboard.press('Escape');
    await expect(box).toHaveCount(0);
  }
  await back(page, 'C1');
  await openCard(page, 'C5');
  await openRow(e2eSheet('C5'), 0);
  await expect(box.getByTestId('s3-ai-star')).toHaveCount(0);
  await expect(box.getByTestId('s3-window-basic')).toContainText('kg');
  const carbon = box.getByTestId('s3-window-carbon');
  await expect(carbon).toContainText(windowWords.biogenic);
  await expect(box.getByTestId('s3-window-fcf')).toHaveText('20%');
  await expect(box.getByRole('columnheader').nth(1)).toHaveText(
    '배출계수 (kg CO2e /kg)',
  );
  await expect(box.locator('input, select, textarea')).toHaveCount(0);
  await shoot(page, 'c5');
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.keyboard.press('Escape');
  await expect(box).toHaveCount(0);
  await back(page, 'C5');
  await openCard(page, 'C12');
  await openRow(e2eSheet('C12'), 0);
  await expect(box.getByTestId('s3-window-carbon')).toContainText('해당없음');
  await expect(box.getByTestId('s3-window-fcf')).toHaveText('-');
  await expect(
    box
      .getByTestId('s3-window-basic')
      .getByText(windowWords.emission, { exact: true })
      .locator('xpath=following-sibling::dd'),
  ).toHaveText('-');
  await page.keyboard.press('Escape');
  await expect(box).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

// ── S3W3a ③ 잠금 · 570 경고 · 총합 ──
const lockWords = S3_TEXT.lock;
const warnWords = S3_TEXT.rerunWarning;
const LOCK_PATH = '/inventory/scope3/years/';
const lockCalls = (
  api: Awaited<ReturnType<typeof fakeScope3Api>>,
  method: string,
) =>
  api.calls.filter(
    (one) =>
      one.method === method &&
      one.path.startsWith(LOCK_PATH) &&
      one.path.endsWith('/lock'),
  );
/** 둘째 실행의 결과: C2·C3 값만 다르다. */
function secondResult(): Json {
  const body = e2eDoneResult();
  const sheets = body.sheets as Json[];
  (sheets[1]!.rows as Json[])[0]!.co2e = '22';
  (sheets[2]!.rows as Json[])[0]!.co2e = '33';
  return body;
}
/** 결과 화면에서 다시 올린다(카테고리 둘 → 작은 파일). */
async function runAgain(page: Page) {
  const dialog = page.getByTestId('s3-category-dialog');
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole('checkbox', {
      name: categoryWords.item(1, S3_TEXT.categories.C1),
    })
    .click();
  await dialog.getByRole('button', { name: categoryWords.confirm }).click();
  await expect(uploadDialog(page)).toBeVisible();
  await uploadSmall(page);
}

test('S3W3a 고객사 잠그기: 확인 창 → 본 실행 runId → 상세가 남고 풀기 단추 0 · 잠근 사람·때 · 초점 [목록] · 카드 자물쇠 · 총합', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await expect(page.getByTestId('s3-scope-total')).toContainText(
    resultWords.scopeTotalLabel,
  );
  await expect(page.getByTestId('s3-card-lock')).toHaveCount(15);
  await openCard(page, 'C2');
  await detail(page).getByTestId('s3-lock').click();
  const window = page.getByTestId('s3-lock-confirm');
  await expect(window).toContainText(lockWords.lockConfirmPlain);
  await window.getByRole('button', { name: lockWords.lockOk }).click();
  await expect(detail(page).getByTestId('s3-locked-mark')).toBeVisible();
  await expect(detail(page).getByTestId('s3-lock')).toHaveCount(0);
  await expect(detail(page).getByTestId('s3-locked-info')).toContainText(
    '흉내 담당자',
  );
  await expect(detail(page).getByTestId('s3-detail-back')).toBeFocused();
  expect(lockCalls(api, 'POST').map((one) => one.search)).toEqual([
    `?runId=${api.runs[0]!.id}`,
  ]);
  await detail(page).getByTestId('s3-detail-back').click();
  await expect(card(page, 'C2').getByTestId('s3-card-lock')).toHaveAttribute(
    'data-locked',
    'true',
  );
  expect(unrouted).toEqual([]);
});

test('S3W3a 잠근 카테고리는 새 실행 뒤 핀 값·핀 줄 · 다른 카드는 새 값 · 운영 관리자 풀기(핀 ≠ 기준 확인) → 새 값', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'admin', {
    runResults: [e2eDoneResult(), secondResult()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C2');
  await detail(page).getByTestId('s3-lock').click();
  await expect(detail(page).getByTestId('s3-lock')).toHaveAttribute(
    'data-locked',
    'true',
  );
  await expect(page.getByTestId('s3-lock-confirm')).toHaveCount(0);
  await detail(page).getByTestId('s3-detail-back').click();
  await page
    .getByTestId('s3-done')
    .getByRole('button', { name: resultWords.upload })
    .click();
  await runAgain(page);
  await expect(total(page, 'C3')).toHaveText('33tCO2eq', RUN_WAIT);
  await expect(total(page, 'C2')).toHaveText('2tCO2eq');

  await openCard(page, 'C2');
  await expect(detail(page).getByTestId('s3-detail-total')).toHaveText(
    '2tCO2eq',
  );
  await detail(page).getByTestId('s3-lock').click();
  const window = page.getByTestId('s3-unlock-confirm');
  await expect(window).toContainText(lockWords.unlockTitle);
  await expect(window).toContainText(lockWords.unlockBody(0));
  await expect(
    window.getByRole('button', { name: lockWords.cancel }),
  ).toBeFocused();
  await window.getByRole('button', { name: lockWords.cancel }).click();
  await expect(window).toHaveCount(0);
  expect(lockCalls(api, 'DELETE')).toEqual([]);
  await detail(page).getByTestId('s3-lock').click();
  await window.getByRole('button', { name: lockWords.unlockOk }).click();
  await expect(detail(page).getByTestId('s3-detail-total')).toHaveText(
    '22tCO2eq',
  );
  expect(lockCalls(api, 'DELETE')).toHaveLength(1);
  expect(unrouted).toEqual([]);
});

test('S3W3a 570 경고: 고친 행이 있으면 창(초점 취소) · 취소면 안 감 · 계속이면 카테고리 창', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runEdits: [
      [
        { rowId: 'p', category: 'C2', excluded: true },
        { rowId: 'p', category: 'C7', factor: e2eRowFactor() },
      ],
    ],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  const upload = page
    .getByTestId('s3-done')
    .getByRole('button', { name: resultWords.upload });
  await upload.click();
  const window = page.getByTestId('s3-rerun-warning');
  await expect(window).toContainText(warnWords.title(2));
  await expect(
    window.getByRole('button', { name: warnWords.cancel }),
  ).toBeFocused();
  await window.getByRole('button', { name: warnWords.cancel }).click();
  await expect(window).toHaveCount(0);
  await expect(page.getByTestId('s3-category-dialog')).toHaveCount(0);
  await expect(upload).toBeFocused();
  await upload.click();
  await window.getByRole('button', { name: warnWords.confirm }).click();
  await expect(page.getByTestId('s3-category-dialog')).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('S3W3a 570 경고: 고친 행이 0 이면 창 없이 바로 · 카드 합은 서버 지금 합', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  await runOnce(page);
  await expect(total(page, 'C4')).toHaveText('1,234.75tCO2eq', RUN_WAIT);
  await page
    .getByTestId('s3-done')
    .getByRole('button', { name: resultWords.upload })
    .click();
  await expect(page.getByTestId('s3-category-dialog')).toBeVisible();
  await expect(page.getByTestId('s3-rerun-warning')).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

// ── S3W3b: 줄 제외·복구·히스토리 ──
const editWords = S3_TEXT.rowEdit;
const c8 = [e2eSheet('C8-1'), e2eSheet('C8-2')] as const;
const pickIn = (page: Page, name: string, n = 0) =>
  rowsOf(page, name).nth(n).getByTestId('s3-pick-row');
const reasonWindow = (page: Page) => page.getByTestId('s3-reason');
const sendReason = async (page: Page, text: string) => {
  await page.getByTestId('s3-reason-input').fill(text);
  await reasonWindow(page)
    .getByRole('button', { name: editWords.reason.confirm })
    .click();
  await expect(reasonWindow(page)).toHaveCount(0);
};
const editCalls = (
  api: Awaited<ReturnType<typeof open>>['api'],
  what: 'exclusions' | 'restorations',
) =>
  api.calls.filter(
    (one) => one.method === 'POST' && one.path.endsWith(`/${what}`),
  );
const openDetailRun = async (page: Page, runEdits?: E2eRowEdit[][]) => {
  const opened = await open(page, 'service', {
    runResults: [e2eDetailResult()],
    ...(runEdits ? { runEdits } : {}),
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  return opened;
};

// ── S3W3c1: 입구 전 카테고리 · 고친 줄 표 칸 · C15 줄(쓰기 0 — 사건은 시드) ──
test('S3W3c1 입구: C3 에너지·C6-1 수단·C8-1 이름 → 창(기준단위·출처 시트 글자·별·탄소기원 0) · 닫으면 초점은 칸', async ({
  page,
}) => {
  const { unrouted, api } = await openDetailRun(page);
  const box = factorWindow(page);
  for (const [id, head, shot] of [
    ['C3', 'C3', 'c3'],
    ['C6', 'C6-1', 'c6-1'],
    ['C7', 'C7', 'c7'],
    ['C8', 'C8-1', 'c8-1'],
  ] as const) {
    await openCard(page, id);
    const opener = rowsOf(page, e2eSheet(head))
      .first()
      .getByTestId('s3-window-open');
    await expect(opener).toHaveCount(1);
    await opener.click();
    await expect(box).toBeVisible();
    await expect(box.getByTestId('s3-window-basic')).toContainText('흉내 시트');
    await expect(box.getByTestId('s3-window-factor')).toContainText(
      '흉내 시트',
    );
    await expect(box.getByTestId('s3-window-carbon')).toHaveCount(0);
    await expect(box.getByTestId('s3-ai-star')).toHaveCount(0);
    await shoot(page, shot);
    await page.keyboard.press('Escape');
    await expect(box).toHaveCount(0);
    await expect(opener).toBeFocused();
    await back(page, id);
  }
  expect(
    api.calls.filter(
      (one) => one.method === 'POST' && one.path.endsWith('/factors'),
    ),
  ).toEqual([]);
  expect(unrouted).toEqual([]);
});

test('S3W3c1 고친 줄: 표 계수·배출량·카드 합이 고친 값 · 창 제목·값·출처 한 벌·산식 「-」 · 여는 칸·검색은 본문', async ({
  page,
}) => {
  const rowId = `${e2eSheet('C7')}!3`;
  const { unrouted } = await openDetailRun(page, [
    [
      {
        rowId,
        category: 'C7',
        factor: e2eRowFactor({
          title: '흉내 새 제목',
          value: '1e-05',
          source: 'usepa',
          unit: 'kgCO2e/km',
        }),
      },
    ],
  ]);
  await expect(total(page, 'C7')).toHaveText('7.25tCO2eq');
  await openCard(page, 'C7');
  await expect(detail(page).getByTestId('s3-detail-total')).toContainText(
    '7.25',
  );
  const row = rowsOf(page, e2eSheet('C7')).first();
  await expect(row).toContainText('0.00001 kgCO2e/km');
  const opener = row.getByTestId('s3-window-open');
  await expect(opener).not.toContainText('흉내 새 제목');
  await opener.click();
  const box = factorWindow(page);
  const body = box.getByTestId('s3-window-factor');
  await expect(body).toContainText('흉내 새 제목');
  await expect(body).toContainText('0.00001');
  await expect(body).toContainText('usepa');
  await expect(body).not.toContainText('US EPA');
  await expect(
    box
      .getByTestId('s3-window-basic')
      .getByText(windowWords.emission, { exact: true })
      .locator('xpath=following-sibling::*'),
  ).toHaveText('-');
  await shoot(page, 'edited-c7');
  await page.keyboard.press('Escape');
  await expect(box).toHaveCount(0);
  await detail(page).getByTestId('s3-detail-search').fill('흉내 새 제목');
  await expect(rowsOf(page, e2eSheet('C7'))).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('S3W3c1 C15: 표 위 오른쪽 한 줄 · 이름 칸은 글 그대로(창 0)', async ({
  page,
}) => {
  const { unrouted } = await openDetailRun(page);
  await openCard(page, 'C15');
  await expect(page.getByTestId('s3-sheet-no-factor-edit')).toHaveText(
    detailWords.noFactorEdit,
  );
  const row = rowsOf(page, e2eSheet('C15')).first();
  await expect(row).toContainText('흉내 이름 C15');
  await expect(row.getByTestId('s3-window-open')).toHaveCount(0);
  await shoot(page, 'c15');
  expect(unrouted).toEqual([]);
});

test('S3W3b 고름 → 제외(사유) → 앞 글·비율 「-」·합 줆·체크 풀림 → 복구 → 합 되돌아옴 · 시트 둘 한 요청', async ({
  page,
}) => {
  const { unrouted, api } = await openDetailRun(page);
  await openCard(page, 'C8');
  const before = await detail(page)
    .getByTestId('s3-detail-total')
    .textContent();
  await expect(detail(page).getByTestId('s3-exclude')).toBeDisabled();
  await pickIn(page, c8[0]).focus();
  await page.keyboard.press('Space');
  await expect(pickIn(page, c8[0])).toBeFocused();
  await expect(pickIn(page, c8[0])).toBeChecked();
  await pickIn(page, c8[1]).click();
  await detail(page).getByTestId('s3-exclude').click();
  await expect(page.getByTestId('s3-reason-input')).toBeFocused();
  await sendReason(page, '지어낸 제외 사유');
  await expect(detail(page).getByTestId('s3-edit-notice')).toHaveText(
    editWords.excluded(2),
  );
  await expect(detail(page).getByTestId('s3-detail-back')).toBeFocused();
  const [one, ...others] = editCalls(api, 'exclusions');
  expect(others).toEqual([]);
  expect(one!.body).toEqual({
    rowIds: [`${c8[0]}!3`, `${c8[1]}!3`],
    reason: '지어낸 제외 사유',
  });
  await expect(rowsOf(page, c8[0]).first()).toHaveAttribute(
    'data-excluded',
    'true',
  );
  await expect(columnOf(page, c8[0], 1).first()).toContainText(
    `${editWords.excludedLead} - `,
  );
  const share = await columnBy(page, c8[0], '배출량 비율');
  await expect(share.first()).toHaveText(resultWords.empty);
  await expect(detail(page).getByTestId('s3-detail-total')).not.toHaveText(
    before!,
  );
  await expect(pickIn(page, c8[0])).not.toBeChecked();
  await pickIn(page, c8[0]).click();
  await pickIn(page, c8[1]).click();
  await detail(page).getByTestId('s3-restore').click();
  await sendReason(page, '지어낸 복구 사유');
  await expect(detail(page).getByTestId('s3-edit-notice')).toHaveText(
    editWords.restored(2),
  );
  await expect(detail(page).getByTestId('s3-detail-total')).toHaveText(before!);
  await expect(rowsOf(page, c8[0]).first()).not.toHaveAttribute(
    'data-excluded',
    'true',
  );
  expect(unrouted).toEqual([]);
});

test('S3W3b 잠긴 카테고리: 체크·단추 막힘 · 막힌 단추 툴팁 · 히스토리는 열림', async ({
  page,
}) => {
  const { unrouted } = await openDetailRun(page);
  await openCard(page, 'C3');
  await detail(page).getByTestId('s3-lock').click();
  await page
    .getByTestId('s3-lock-confirm')
    .getByRole('button', { name: lockWords.lockOk })
    .click();
  await expect(detail(page).getByTestId('s3-locked-mark')).toBeVisible();
  const sheet = e2eSheet('C3');
  await expect(pickIn(page, sheet)).toBeDisabled();
  await expect(detail(page).getByTestId('s3-exclude')).toBeDisabled();
  await expect(detail(page).getByTestId('s3-restore')).toBeDisabled();
  await detail(page).getByTestId('s3-edit-locked').first().hover();
  await expect(page.getByRole('tooltip')).toContainText(editWords.locked);
  await rowsOf(page, sheet).getByTestId('s3-history-open').click();
  await expect(page.getByTestId('s3-history-empty')).toHaveText(
    editWords.history.empty,
  );
  expect(unrouted).toEqual([]);
});

test('S3W3b 히스토리 창: 세 종류 글 · 빈 이력 · [확인] 뒤 초점은 누른 단추 · 틀 980', async ({
  page,
}) => {
  const c5 = e2eSheet('C5');
  const rowId = `${c5}!3`;
  const { unrouted } = await openDetailRun(page, [
    [
      {
        rowId,
        category: 'C5',
        excluded: true,
        factor: e2eRowFactor(),
      },
    ],
  ]);
  await openCard(page, 'C5');
  await pickIn(page, c5, 0).click();
  await detail(page).getByTestId('s3-restore').click();
  await sendReason(page, '지어낸 복구 사유');
  await expect(rowsOf(page, c5).first()).not.toHaveAttribute(
    'data-excluded',
    'true',
  );
  const opener = rowsOf(page, c5).first().getByTestId('s3-history-open');
  await opener.click();
  const box = page.getByTestId('s3-history');
  await expect(box.getByTestId('s3-history-kind')).toHaveCount(3);
  for (const kind of Object.values(editWords.history.kinds))
    await expect(
      box.getByTestId('s3-history-kind').filter({ hasText: kind }),
    ).toHaveCount(1);
  await expect(box.getByRole('columnheader')).toHaveText([
    editWords.history.at,
    editWords.history.by,
    editWords.history.reason,
  ]);
  await expect(box).toHaveCSS('width', '980px');
  await box.getByTestId('s3-history-close').click();
  await expect(box).toHaveCount(0);
  await expect(opener).toBeFocused();
  const other = rowsOf(page, c5).nth(1).getByTestId('s3-history-open');
  await other.click();
  await expect(page.getByTestId('s3-history-empty')).toHaveText(
    editWords.history.empty,
  );
  await page.keyboard.press('Escape');
  await expect(other).toBeFocused();
  expect(unrouted).toEqual([]);
});

// ── S3W3c2 ②: 계수 수정 꼴 · 쓰기 흐름 · C12·잠김 막힘 · 화면이 낸 몸 ↔ openapi ──
const factorEditWords = detailWords.factorEdit;
const factorBodySchemas = (() => {
  const doc = JSON.parse(
    readFileSync(
      resolve(
        dirname(fileURLToPath(import.meta.url)),
        '../../api-py/generated/openapi.json',
      ),
      'utf8',
    ),
  ) as { components: { schemas: Record<string, Json> } };
  return {
    body: doc.components.schemas.Scope3RowEditFactorIn!,
    custom: doc.components.schemas.Scope3RowEditCustomIn!,
  };
})();
const factorCalls = (api: Awaited<ReturnType<typeof open>>['api']) =>
  api.calls.filter(
    (one) => one.method === 'POST' && one.path.endsWith('/factors'),
  );
/** 화면이 낸 몸을 openapi 꼴과 걸음(required·더한 키 0·갈래마다 null 짝). */
const expectFactorBody = (body: unknown, choice: string) => {
  const one = body as Json;
  const { body: schema, custom } = factorBodySchemas;
  const required = [...(schema.required as string[])].sort();
  expect(Object.keys(one).sort()).toEqual(required);
  expect(Object.keys(schema.properties as Json).sort()).toEqual(required);
  expect(schema.additionalProperties).toBe(false);
  expect(one.choice).toBe(choice);
  expect(typeof one.rowId).toBe('string');
  expect(typeof one.reason).toBe('string');
  if (choice === 'recommended') expect(Number.isInteger(one.rank)).toBe(true);
  else expect(one.rank).toBeNull();
  if (choice === 'custom') {
    const keys = [...(custom.required as string[])].sort();
    expect(Object.keys(one.custom as Json).sort()).toEqual(keys);
    expect(custom.additionalProperties).toBe(false);
    for (const key of keys)
      expect(typeof (one.custom as Json)[key]).toBe('string');
  } else expect(one.custom).toBeNull();
};
const editFactor = async (page: Page, sheet: string, n = 0) => {
  await rowsOf(page, sheet).nth(n).getByTestId('s3-window-open').click();
  const box = factorWindow(page);
  await expect(box).toBeVisible();
  await box.getByTestId('s3-factor-edit').click();
  await expect(box).toHaveAttribute('data-mode', 'edit');
  return box;
};
const saveWithReason = async (page: Page, reason: string) => {
  await factorWindow(page).getByTestId('s3-factor-save').click();
  await expect(page.getByTestId('s3-reason-input')).toBeFocused();
  await sendReason(page, reason);
  await expect(factorWindow(page)).toHaveCount(0);
  await expect(detail(page).getByTestId('s3-factor-notice')).toHaveText(
    factorEditWords.saved,
  );
};

test('S3W3c2 구매 줄 추천 → 사유 → 계수·배출량·카드 합이 서버 값 · 화면 몸 = openapi(recommended)', async ({
  page,
}) => {
  const { unrouted, api } = await openDetailRun(page);
  await expect(total(page, 'C2')).toHaveText('2tCO2eq');
  await openCard(page, 'C2');
  const sheet = e2eSheet('C2');
  const box = await editFactor(page, sheet);
  await expect(box.getByTestId('s3-factor-applied')).toContainText('흉내 항목');
  await expect(box.getByTestId('s3-factor-recommendation')).toHaveCount(1);
  await expect(box.getByTestId('s3-factor-pick-applied')).toBeChecked();
  await shoot(page, 'edit-c2');
  await box.getByTestId('s3-factor-pick-rank').click();
  await saveWithReason(page, '지어낸 추천 사유');
  const [call, ...rest] = factorCalls(api);
  expect(rest).toEqual([]);
  expectFactorBody(call!.body, 'recommended');
  expect(call!.body).toEqual({
    rowId: `${sheet}!3`,
    choice: 'recommended',
    rank: 1,
    custom: null,
    reason: '지어낸 추천 사유',
  });
  const row = rowsOf(page, sheet).first();
  await expect(row).toContainText(E2E_EDITED_CO2E);
  await expect(row).toContainText('0.2');
  await expect(detail(page).getByTestId('s3-detail-total')).toContainText(
    E2E_EDITED_CO2E,
  );
  await expect(detail(page).getByTestId('s3-detail-back')).toBeFocused();
  await back(page, 'C2');
  await expect(total(page, 'C2')).toHaveText(`${E2E_EDITED_CO2E}tCO2eq`);
  expect(unrouted).toEqual([]);
});

test('S3W3c2 직접 입력(C7): 빈 칸 필수 글 → 채움 → 저장 · 출처만 바꿔 또 저장 → POST 둘 · 히스토리 계수 줄 둘 · 몸 = openapi(custom)', async ({
  page,
}) => {
  const { unrouted, api } = await openDetailRun(page);
  await openCard(page, 'C7');
  const sheet = e2eSheet('C7');
  let box = await editFactor(page, sheet);
  await box.getByTestId('s3-factor-pick-custom').click();
  await box.getByTestId('s3-factor-save').click();
  for (const name of ['title', 'value', 'source'])
    await expect(box.getByTestId(`s3-factor-${name}-error`)).toHaveText(
      factorEditWords.required,
    );
  await expect(box.getByTestId('s3-factor-title')).toBeFocused();
  await expect(page.getByTestId('s3-reason')).toHaveCount(0);
  await shoot(page, 'edit-c7-required');
  await box.getByTestId('s3-factor-title').fill('지어낸 계수 제목');
  await box.getByTestId('s3-factor-value').fill('0.00002');
  await box.getByTestId('s3-factor-source').fill('지어낸 출처 하나');
  await saveWithReason(page, '지어낸 직접 사유');
  box = await editFactor(page, sheet);
  await expect(box.getByTestId('s3-factor-pick-custom')).toBeChecked();
  await expect(box.getByTestId('s3-factor-value')).toHaveValue('0.00002');
  await box.getByTestId('s3-factor-source').fill('지어낸 출처 둘');
  await saveWithReason(page, '지어낸 출처 사유');
  const calls = factorCalls(api);
  expect(calls).toHaveLength(2);
  for (const one of calls) expectFactorBody(one.body, 'custom');
  expect((calls[1]!.body as Json).custom).toEqual({
    title: '지어낸 계수 제목',
    value: '0.00002',
    source: '지어낸 출처 둘',
  });
  await rowsOf(page, sheet).first().getByTestId('s3-history-open').click();
  const history = page.getByTestId('s3-history');
  await expect(
    history
      .getByTestId('s3-history-kind')
      .filter({ hasText: editWords.history.kinds.factor }),
  ).toHaveCount(2);
  await expect(history.getByTestId('s3-history-change').first()).toContainText(
    `${editWords.history.arrow}0.00002`,
  );
  expect(unrouted).toEqual([]);
});

test('S3W3c2 고친 줄을 적용으로 되돌림 → 합이 처음 · 몸 = openapi(applied) · 사유 창 바깥 누름은 위 창만(★D)', async ({
  page,
}) => {
  const rowId = `${e2eSheet('C7')}!3`;
  const { unrouted, api } = await openDetailRun(page, [
    [{ rowId, category: 'C7', factor: e2eRowFactor({ unit: 'kgCO2e/km' }) }],
  ]);
  await expect(total(page, 'C7')).toHaveText(`${E2E_EDITED_CO2E}tCO2eq`);
  await openCard(page, 'C7');
  const box = await editFactor(page, e2eSheet('C7'));
  await expect(box.getByTestId('s3-factor-pick-custom')).toBeChecked();
  await box.getByTestId('s3-factor-pick-applied').click();
  await box.getByTestId('s3-factor-save').click();
  const reason = page.getByTestId('s3-reason');
  await expect(reason).toBeVisible();
  // 바깥 누름(사유 창 밖 = 아래 창 위): 사유 창만 닫히고 수정 꼴은 남는다.
  const lower = page.getByTestId('s3-factor-window');
  const under = await lower.boundingBox();
  // Radix 는 바깥 누름 듣기를 연 다음 틱에 단다 — 그 전 누름은 버려지므로 닫힐 때까지 다시 누른다(아래 창 안이라 아래 창은 안 닫힌다).
  await expect(async () => {
    await page.mouse.click(under!.x + 24, under!.y + 24);
    await expect(reason).toHaveCount(0, { timeout: 1000 });
  }).toPass();
  await expect(lower).toHaveAttribute('data-mode', 'edit');
  // 위 창이 닫히면 아래 창이 다시 읽기 프로그램에 보인다(aria-hidden 풀림).
  await expect(box).toBeVisible();
  await saveWithReason(page, '지어낸 되돌림 사유');
  const [call] = factorCalls(api);
  expectFactorBody(call!.body, 'applied');
  await back(page, 'C7');
  await expect(total(page, 'C7')).toHaveText('7tCO2eq');
  expect(unrouted).toEqual([]);
});

test('S3W3c2 막힘: C12 창은 열리고 [수정] 막힘·왼쪽 글 · 잠근 C3 은 막힌 [수정] 툴팁 · C5 수정 꼴은 추천 0·FCF 입력 0', async ({
  page,
}) => {
  const { unrouted, api } = await openDetailRun(page);
  await openCard(page, 'C12');
  await rowsOf(page, e2eSheet('C12'))
    .first()
    .getByTestId('s3-window-open')
    .click();
  const box = factorWindow(page);
  await expect(box.getByTestId('s3-factor-edit')).toBeDisabled();
  await expect(box.getByTestId('s3-factor-blocked')).toHaveText(
    factorEditWords.c12,
  );
  await shoot(page, 'c12-blocked');
  await page.keyboard.press('Escape');
  await back(page, 'C12');
  await openCard(page, 'C5');
  const c5 = await editFactor(page, e2eSheet('C5'));
  await expect(c5.getByTestId('s3-factor-recommended')).toHaveCount(0);
  await expect(c5.getByTestId('s3-window-carbon').locator('input')).toHaveCount(
    0,
  );
  await expect(c5.locator('input')).toHaveCount(3);
  await shoot(page, 'edit-c5');
  await page.keyboard.press('Escape');
  await back(page, 'C5');
  await openCard(page, 'C3');
  await detail(page).getByTestId('s3-lock').click();
  await page
    .getByTestId('s3-lock-confirm')
    .getByRole('button', { name: lockWords.lockOk })
    .click();
  await expect(detail(page).getByTestId('s3-locked-mark')).toBeVisible();
  await rowsOf(page, e2eSheet('C3'))
    .first()
    .getByTestId('s3-window-open')
    .click();
  await expect(box.getByTestId('s3-factor-edit')).toBeDisabled();
  await box.getByTestId('s3-factor-locked').hover();
  await expect(page.getByRole('tooltip')).toContainText(editWords.locked);
  expect(factorCalls(api)).toEqual([]);
  expect(unrouted).toEqual([]);
});

test.describe('흉내 ↔ openapi(브라우저 없음)', () => {
  type Schema = Record<string, unknown>;
  const openapi = JSON.parse(
    readFileSync(
      resolve(
        dirname(fileURLToPath(import.meta.url)),
        '../../api-py/generated/openapi.json',
      ),
      'utf8',
    ),
  ) as {
    paths: Record<string, Record<string, Schema>>;
    components: { schemas: Record<string, Schema> };
  };
  const schemas = openapi.components.schemas;
  const deref = (schema: Schema): Schema =>
    typeof schema.$ref === 'string' ?
      deref(schemas[schema.$ref.replace('#/components/schemas/', '')]!)
    : schema;
  const kindOf = (value: unknown) =>
    value === null ? 'null'
    : Array.isArray(value) ? 'array'
    : Number.isInteger(value) ? 'integer'
    : typeof value;
  /** 스키마를 따라 걸어 내려간다(src 의 server.test.ts 와 같은 셈 — e2e 는 src 를 가져오지 않는다). 객체 칸은 집합이 같아야 한다. */
  function gaps(
    value: unknown,
    raw: Schema,
    at: string,
    kinds: Set<string>,
  ): string[] {
    if ((raw as unknown) === true) return []; // additionalProperties: true(RunOut.options)
    const schema = deref(raw);
    const union = (schema.oneOf ?? schema.anyOf) as Schema[] | undefined;
    if (union) {
      const disc = schema.discriminator as
        { propertyName: string; mapping: Record<string, string> } | undefined;
      if (disc) {
        const target =
          disc.mapping[String((value as Schema | null)?.[disc.propertyName])];
        return target ?
            gaps(value, { $ref: target }, at, kinds)
          : [`${at}: 판별 없음`];
      }
      const fit = union.find(
        (one) => gaps(value, one, at, new Set()).length === 0,
      );
      return fit ?
          gaps(value, fit, at, kinds)
        : [`${at}: 어느 갈래에도 안 맞음`];
    }
    if ('const' in schema && value !== schema.const) return [`${at}: const`];
    if (Array.isArray(schema.enum) && !schema.enum.includes(value))
      return [`${at}: enum 밖 ${String(value)}`];
    const kind = kindOf(value);
    if (schema.type !== kind)
      return [`${at}: ${String(schema.type)} ≠ ${kind}`];
    if (kind === 'array')
      return (value as unknown[]).flatMap((item, i) =>
        gaps(item, schema.items as Schema, `${at}[${i}]`, kinds),
      );
    if (
      schema.format === 'date-time' &&
      Number.isNaN(Date.parse(value as string))
    )
      return [`${at}: date-time 아님 ${String(value)}`];
    if (kind !== 'object') return [];
    const object = value as Schema;
    const properties = schema.properties as Record<string, Schema> | undefined;
    if (!properties)
      return Object.entries(object).flatMap(([key, one]) =>
        gaps(one, schema.additionalProperties as Schema, `${at}.${key}`, kinds),
      );
    if (typeof object.kind === 'string') kinds.add(object.kind);
    // S3W2c: required 는 다 있음 + properties 밖 칸 0(줄의 NotRequired input 하나 — 옛 결과 줄). input 안은 required 열다섯
    //   + 선택 useMonths 하나(S3R3 — 키 열다섯 옛 저장 결과도 맞음, 감독 처분 Q3). 아래 시험이 그 밖으로 넓어지지 않았음을 본다.
    const required = (schema.required as string[] | undefined) ?? [];
    const have = Object.keys(object);
    const missing = required.filter((key) => !have.includes(key));
    const unknown = have.filter((key) => !(key in properties));
    if (missing.length > 0 || unknown.length > 0)
      return [
        `${at}: 칸 ${have.sort().join(',')} ≠ ${Object.keys(properties).sort().join(',')}`,
      ];
    return have.flatMap((key) =>
      gaps(object[key], properties[key]!, `${at}.${key}`, kinds),
    );
  }
  const resultSchema = (
    openapi.paths['/inventory/scope3/runs/{run_id}/result']!.get!
      .responses as Record<string, { content: Record<string, Schema> }>
  )['200']!.content['application/json']!.schema as Schema;

  test('S3Q1: 새 칸 흉내(treatments 갈래 셋·옛 줄 · sourceText 있음/없음) = openapi · 「기타」·칸 더함·sourceText 수는 빨강', () => {
    expect(gaps(e2eS3Q1Result(), resultSchema, '$', new Set())).toEqual([]);
    const c12 = () => {
      const body = e2eS3Q1Result();
      const sheet = (body.sheets as Schema[]).find(
        (one) => one.sheet === 'c12_흉내',
      )!;
      return { body, row: (sheet.rows as Schema[])[0]! };
    };
    const plants: ((row: Schema) => void)[] = [
      (row) =>
        (((row.treatments as Schema).parts as Schema[])[2]!.treatment = '기타'),
      (row) => ((row.treatments as Schema).extra = 1),
      (row) => ((row.treatments as Schema).shareTotal = 1),
      (row) => ((row.factor as Schema).sourceText = 3),
    ];
    for (const plant of plants) {
      const { body, row } = c12();
      plant(row);
      expect(gaps(body, resultSchema, '$', new Set())).not.toEqual([]);
    }
    expect(e2eTreatments('nan').shareTotal).toBeNull();
  });

  test('S3Q1: 원본 경로가 openapi 에 있고(GET 하나) 흉내의 Content-Type 은 그 200 content 셋 안 · 이름 머리는 서버 꼴', () => {
    const op = openapi.paths['/inventory/scope3/runs/{run_id}/original']!;
    expect(Object.keys(op)).toEqual(['get']);
    expect(op.get!.operationId).toBe('inventory_scope3_original_get');
    const content = Object.keys(
      (op.get!.responses as Record<string, { content: Schema }>)['200']!
        .content,
    );
    for (const name of ['흉내.xlsx', 'a.XLS', 'noext'])
      expect(content).toContain(originalMediaType(name));
    expect(attachmentOf('a.xlsx')).toBe('attachment; filename="a.xlsx"');
    expect(attachmentOf('흉내.xlsx')).toBe(
      `attachment; filename*=utf-8''${encodeURIComponent('흉내.xlsx')}`,
    );
  });

  test('결과 본문(기본·실패 있음·거절) = openapi · 시트 다섯 갈래 · 줄 kind 열넷 · 걸음은 칸 이름 틀림을 잡는다', () => {
    const kinds = new Set<string>();
    const bodies = [
      e2eDoneResult(),
      e2eDoneResult({ problems: true }),
      e2eDetailResult(),
      e2eRejectedResult('reader_problem'),
    ];
    for (const body of bodies)
      expect(gaps(body, resultSchema, '$', kinds)).toEqual([]);
    expect(kinds.size).toBe(14);
    // 상세 본문 하나만으로도 kind 열넷(S3W2b ①).
    const detailKinds = new Set<string>();
    expect(gaps(e2eDetailResult(), resultSchema, '$', detailKinds)).toEqual([]);
    expect(detailKinds.size).toBe(14);
    const statuses = new Set(
      [
        ...(bodies[0]!.sheets as Schema[]),
        ...(bodies[1]!.sheets as Schema[]),
      ].map((sheet) => sheet.status),
    );
    expect([...statuses].sort()).toEqual([
      'empty',
      'failed',
      'not_target',
      'not_yet_supported',
      'processed',
    ]);
    const bad = e2eDoneResult();
    const row = (bad.sheets as { rows: Schema[] }[])[0]!.rows[0]!;
    row.co2_e = row.co2e;
    delete row.co2e;
    expect(gaps(bad, resultSchema, '$', new Set())).not.toEqual([]);
  });

  test('S3W2c·S3R3·S3Q1 걸음: 줄에서 빠져도 되는 칸은 input(에너지 줄은 S3Q1 treatments 더) · input 안은 required 열다섯 + 선택 useMonths · 흉내에 input 있는 줄과 없는 줄 둘 다', () => {
    const expected: Record<string, string[]> = {
      ColabRowJson: ['input'],
      ColabActivityRowJson: ['input'],
      ColabEnergyRowJson: ['input', 'treatments'], // S3Q1: C12 처리방법별 칸(product_eol 만)
    };
    for (const [name, want] of Object.entries(expected)) {
      const schema = schemas[name]!;
      const optional = Object.keys(schema.properties as Schema)
        .filter((key) => !(schema.required as string[]).includes(key))
        .sort();
      expect(optional, name).toEqual(want);
    }
    const input = schemas.ColabRowInputJson!;
    expect(input.additionalProperties).toBe(false);
    const inputOptional = Object.keys(input.properties as Schema).filter(
      (key) => !(input.required as string[]).includes(key),
    );
    expect(inputOptional).toEqual(['useMonths']);
    expect([...(input.required as string[])].sort()).toEqual(
      Object.keys(input.properties as Schema)
        .filter((key) => key !== 'useMonths')
        .sort(),
    );
    const plants: ((cells: Schema) => void)[] = [
      (cells) => delete cells.stores,
      (cells) => (cells.extra = null),
      (cells) => (cells.people = 3),
      (cells) => (cells.useMonths = 18),
    ];
    for (const plant of plants) {
      const body = e2eDoneResult();
      const first = (body.sheets as { rows: Schema[] }[])[0]!.rows[0]!;
      first.input = { ...(first.input as Schema) };
      plant(first.input as Schema);
      expect(gaps(body, resultSchema, '$', new Set())).not.toEqual([]);
    }
    const rows = (e2eDetailResult().sheets as { rows?: Schema[] }[]).flatMap(
      (sheet) => sheet.rows ?? [],
    );
    expect(rows.some((one) => 'input' in one)).toBe(true);
    expect(rows.some((one) => !('input' in one))).toBe(true);
    // S3R3 ★ 흉내 input 은 일부러 둔 키 열다섯 옛 줄(상세 C11 !3) 하나 빼고 전부 키 열여섯 — 그 옛 줄도 꼴에 맞다.
    const sizes = [e2eDoneResult(), e2eDetailResult()]
      .flatMap((body) =>
        (body.sheets as { rows?: Schema[] }[]).flatMap(
          (sheet) => sheet.rows ?? [],
        ),
      )
      .flatMap((one) => (one.input ? [Object.keys(one.input).length] : []));
    expect(sizes.filter((size) => size === 15)).toHaveLength(1);
    expect(sizes.filter((size) => size !== 15 && size !== 16)).toEqual([]);
    expect(gaps(e2eDetailResult(), resultSchema, '$', new Set())).toEqual([]);
  });

  test('S3W4: 흉내 그룹 단계 셋 갈래 · 구매 줄만 group · 남의 줄 enum 은 빨강 · 「해당없음」·빈 산식 줄 있음', () => {
    const body = e2eDetailResult();
    const rows = (body.sheets as { rows?: Schema[] }[]).flatMap(
      (sheet) => sheet.rows ?? [],
    );
    const origins = rows.flatMap((one) =>
      (one.originSteps as Schema[])
        .filter((one) => one.step === 'group')
        .map((one) => one.origin),
    );
    expect([...new Set(origins)].sort()).toEqual(['ai', 'estimate', 'rule']);
    for (const one of rows) {
      const steps = (one.originSteps as Schema[]).map((one) => one.step);
      if (one.kind === 'purchase') expect(steps).toContain('group');
      else expect(steps).not.toContain('group');
    }
    expect(
      rows.some((one) => (one.biogenic as Schema | null)?.note === '해당없음'),
    ).toBe(true);
    expect(rows.some((one) => one.formula === '')).toBe(true);
    for (const kind of ['purchase', 'waste', 'product_eol']) {
      const bad = e2eDetailResult();
      const row = (bad.sheets as { rows?: Schema[] }[])
        .flatMap((sheet) => sheet.rows ?? [])
        .find((one) => one.kind === kind)!;
      row.originSteps = [
        {
          step: kind === 'purchase' ? 'mapping' : 'group',
          origin: 'ai',
          via: '흉내',
        },
      ];
      expect(gaps(bad, resultSchema, '$', new Set())).not.toEqual([]);
    }
  });

  // ★ S3W3a: 장부의 답을 경로별 200 스키마로 걷는다(상태 번호 포함). factor 값·null 둘 다.
  const answerSchema = (path: string, method: string) =>
    (
      openapi.paths[path]![method]!.responses as Record<
        string,
        { content: Record<string, Schema> }
      >
    )['200']!.content['application/json']!.schema as Schema;
  const ledgerOf = (operator = true) => {
    const runs = [
      {
        id: 51,
        flowId: 'scope3.colab@157',
        options: { reportYear: LAST },
        result: e2eDetailResult(),
      },
    ];
    const ledger = createScope3Ledger(runs, () => 'done', operator);
    const row = (
      (e2eDetailResult().sheets as Json[]).find(
        (sheet) =>
          sheet.status === 'processed' && sheet.category === 'Category1',
      )!.rows as Json[]
    ).map((one) => one.rowId as string);
    ledger.seed(51, [
      { rowId: row[0]!, category: 'C1', excluded: true },
      { rowId: row[1]!, category: 'C1', factor: e2eRowFactor() },
      { rowId: row[2]!, category: 'C1', excluded: true, by: null },
    ]);
    return { ledger, row };
  };
  const Y = '/inventory/scope3/years/{year}';
  const LOCK = `${Y}/categories/{category}/lock`;
  const R = '/inventory/scope3/runs/{run_id}';
  const none = new URLSearchParams();

  test('S3W3a 장부 답 여덟 = openapi 200 · factor 값·null 둘 다 · 칸을 빼면 빨강', () => {
    const { ledger, row } = ledgerOf();
    const y = `/inventory/scope3/years/${LAST}`;
    const r = '/inventory/scope3/runs/51';
    const cases: [string, string, URLSearchParams, unknown, string, string][] =
      [
        ['GET', y, none, undefined, Y, 'get'],
        ['GET', `${r}/edits`, none, undefined, `${R}/edits`, 'get'],
        ['GET', `${r}/history`, none, undefined, `${R}/history`, 'get'],
        [
          'POST',
          `${r}/categories/C1/exclusions`,
          none,
          { rowIds: [row[3]], reason: '흉내' },
          `${R}/categories/{category}/exclusions`,
          'post',
        ],
        [
          'POST',
          `${r}/categories/C1/restorations`,
          none,
          { rowIds: [row[0]], reason: '흉내' },
          `${R}/categories/{category}/restorations`,
          'post',
        ],
        [
          'POST',
          `${r}/categories/C1/factors`,
          none,
          {
            rowId: row[3],
            choice: 'custom',
            rank: null,
            custom: { title: '흉내', value: '0.5', source: '흉내' },
            reason: '흉내',
          },
          `${R}/categories/{category}/factors`,
          'post',
        ],
        [
          'POST',
          `${y}/categories/C1/lock`,
          new URLSearchParams({ runId: '51' }),
          undefined,
          LOCK,
          'post',
        ],
        ['DELETE', `${y}/categories/C1/lock`, none, undefined, LOCK, 'delete'],
      ];
    for (const [method, path, query, body, schema, verb] of cases) {
      const reply = ledger.answerOf(method, path, query, body)!;
      expect(`${path} ${reply.status}`).toBe(`${path} 200`);
      expect(
        gaps(reply.body, answerSchema(schema, verb), '$', new Set()),
      ).toEqual([]);
    }
    // 쓰기로 생긴 사건도 걷는다(시드 사건만 걸으면 쓰기 길의 kind 를 못 본다) — 세 갈래가 다 나온다.
    const after = ledger.answerOf('GET', `${r}/history`, none, undefined)!
      .body as Json;
    expect(
      gaps(after, answerSchema(`${R}/history`, 'get'), '$', new Set()),
    ).toEqual([]);
    expect(
      [...new Set((after.results as Json[]).map((one) => one.kind))].sort(),
    ).toEqual(['exclude', 'factor', 'restore']);
    const { ledger: fresh } = ledgerOf();
    const edits = fresh.answerOf('GET', `${r}/edits`, none, undefined)!
      .body as Json;
    const rows = edits.rows as Json[];
    expect(rows.some((one) => one.factor === null)).toBe(true);
    expect(rows.some((one) => one.factor !== null)).toBe(true);
    const missing = structuredClone(edits);
    delete (missing.rows as Json[])[0]!.factor;
    expect(
      gaps(missing, answerSchema(`${R}/edits`, 'get'), '$', new Set()),
    ).not.toEqual([]);
    const page = fresh.answerOf('GET', `${r}/history`, none, undefined)!
      .body as Json;
    for (const key of ['factor', 'batchId', 'by']) {
      const bad = structuredClone(page);
      delete (bad.results as Json[])[0]![key];
      expect(
        gaps(bad, answerSchema(`${R}/history`, 'get'), '$', new Set()),
      ).not.toEqual([]);
    }
    const badKind = structuredClone(page);
    (badKind.results as Json[])[0]!.kind = 'edit';
    expect(
      gaps(badKind, answerSchema(`${R}/history`, 'get'), '$', new Set()),
    ).not.toEqual([]);
  });

  test('S3W3a 장부 ⑩: 사건 없는 줄 applied 는 사건 0 · 같은 고름 두 번은 사건 하나', () => {
    const { ledger, row } = ledgerOf();
    const r = '/inventory/scope3/runs/51';
    const send = (choice: string, rowId: string) =>
      ledger.answerOf('POST', `${r}/categories/C1/factors`, none, {
        rowId,
        choice,
        rank: choice === 'recommended' ? 1 : null,
        custom: null,
        reason: '흉내',
      })!.body as Json;
    const count = () =>
      (ledger.answerOf('GET', `${r}/history`, none, undefined)!.body as Json)
        .count;
    const before = count();
    expect(send('applied', row[3]!).rows).toEqual([]);
    expect(count()).toBe(before);
    send('recommended', row[3]!);
    send('recommended', row[3]!);
    expect(count()).toBe((before as number) + 1);
  });

  // ★ 거울(K2): 같은 표를 S/api/server.test.ts 「가짜 계수 규칙」 에 글자로 한 벌 더 둔다 — 한쪽을 고치면 다른 쪽도 고친다. 기대 값은 서버 scope3_factors.py·scope3_edits.py 에서 옮긴 리터럴이다.
  const mirror = (() => {
    const KINDS = [
      'transport_spend',
      'travel_spend',
      'transport_distance',
      'travel_distance',
      'commute',
      'fuel_energy',
      'leased_asset',
      'leased_out_asset',
      'product_use',
      'franchise',
    ];
    const RECS = [
      { title: '지어낸 가', value: '0.2', expectedCo2e: '0.3' },
      { title: '지어낸 나', value: null, expectedCo2e: null },
      { title: '지어낸 다', value: '1e-05', expectedCo2e: '0.6' },
    ];
    const SHEETS = [
      {
        status: 'processed',
        sheet: 'c1',
        category: 'Category1',
        rows: [
          {
            rowId: 'P!2',
            kind: 'purchase',
            co2e: '5',
            factor: {
              title: '지어낸 원안',
              value: '0.1',
              unit: 'kgCO2e/KRW',
              column: '2024\n판',
              source: 'db_keyword',
            },
            recommendations: RECS,
          },
          {
            rowId: 'P!3',
            kind: 'purchase',
            co2e: null,
            factor: {
              title: null,
              value: null,
              unit: 'kgCO2e/KRW',
              column: null,
              source: 'none',
            },
            recommendations: [],
          },
          ...KINDS.map((kind) => ({
            rowId: `K!${kind}`,
            kind,
            co2e: '1',
            factor: {
              title: 't',
              value: '1',
              unit: 'kg',
              sheet: '지어낸 시트',
            },
          })),
        ],
      },
      {
        status: 'processed',
        sheet: 'c3',
        category: 'Category3',
        rows: [
          { rowId: 'E!2', kind: 'fuel_energy', co2e: null, factor: null },
          {
            rowId: 'E!3',
            kind: 'fuel_energy',
            co2e: '1',
            factor: { title: 't', value: '1', sheet: '지어낸 시트' },
          },
        ],
      },
      {
        status: 'processed',
        sheet: 'c5',
        category: 'Category5',
        rows: [
          {
            rowId: 'W!2',
            kind: 'waste',
            co2e: '1',
            biogenic: { biogenicCo2e: '0.25', fcf: '0.5' },
            factor: {
              title: 't',
              value: '1',
              unit: 'kg',
              sheet: '지어낸 시트',
            },
          },
          {
            rowId: 'W!3',
            kind: 'waste',
            co2e: '1',
            biogenic: { biogenicCo2e: null, fcf: null },
            factor: {
              title: 't',
              value: '1',
              unit: 'kg',
              sheet: '지어낸 시트',
            },
          },
        ],
      },
      {
        status: 'processed',
        sheet: 'c12',
        category: 'Category12',
        rows: [
          {
            rowId: 'L!2',
            kind: 'product_eol',
            co2e: '1',
            factor: {
              title: 't',
              value: '1',
              unit: 'kg',
              sheet: '지어낸 시트',
            },
          },
        ],
      },
      {
        status: 'processed',
        sheet: 'c15',
        category: 'Category15',
        rows: [{ rowId: 'I!2', kind: 'investment', co2e: '1', factor: null }],
      },
    ];
    const base = { rowId: 'P!2', rank: null, custom: null, reason: '지어낸' };
    const custom = (over: Record<string, unknown>) => ({
      ...base,
      choice: 'custom',
      custom: { title: '지어낸', value: '0.5', source: '지어낸', ...over },
    });
    const pick = (rank: number, rowId = 'P!2') => ({
      ...base,
      rowId,
      choice: 'recommended',
      rank,
    });
    const LONG = '가'.repeat(201);
    const LONGEST = '😀'.repeat(200);
    const { rank: _rank, ...noRank } = base;
    const TABLE: [
      string,
      number,
      string,
      unknown,
      number,
      string | null,
      string[],
    ][] = [
      [
        'rank 키 없음',
        51,
        'C1',
        { ...noRank, choice: 'applied' },
        422,
        'VALIDATION_ERROR',
        ['rank'],
      ],
      [
        '더한 키',
        51,
        'C1',
        { ...base, choice: 'applied', 더한칸: 1 },
        422,
        'VALIDATION_ERROR',
        ['더한칸'],
      ],
      [
        '모르는 고름',
        51,
        'C1',
        { ...base, choice: 'other' },
        422,
        'VALIDATION_ERROR',
        ['choice'],
      ],
      [
        '추천인데 순위 없음',
        51,
        'C1',
        { ...base, choice: 'recommended' },
        422,
        'VALIDATION_ERROR',
        ['rank'],
      ],
      [
        '적용인데 순위',
        51,
        'C1',
        { ...base, choice: 'applied', rank: 1 },
        422,
        'VALIDATION_ERROR',
        ['rank'],
      ],
      ['순위 범위 밖', 51, 'C1', pick(5), 422, 'VALIDATION_ERROR', ['rank']],
      [
        '직접인데 입력 없음',
        51,
        'C1',
        { ...base, choice: 'custom' },
        422,
        'VALIDATION_ERROR',
        ['custom'],
      ],
      [
        '적용인데 입력',
        51,
        'C1',
        { ...custom({}), choice: 'applied' },
        422,
        'VALIDATION_ERROR',
        ['custom'],
      ],
      [
        '값 지수',
        51,
        'C1',
        custom({ value: '1e-3' }),
        422,
        'VALIDATION_ERROR',
        ['custom.value'],
      ],
      [
        '값 음수',
        51,
        'C1',
        custom({ value: '-1' }),
        422,
        'VALIDATION_ERROR',
        ['custom.value'],
      ],
      [
        '값 0',
        51,
        'C1',
        custom({ value: '0.0' }),
        422,
        'VALIDATION_ERROR',
        ['custom.value'],
      ],
      [
        '값 소수 11자리',
        51,
        'C1',
        custom({ value: '0.12345678901' }),
        422,
        'VALIDATION_ERROR',
        ['custom.value'],
      ],
      [
        '값 소수 10자리',
        51,
        'C1',
        custom({ value: '0.1234567890' }),
        200,
        null,
        [],
      ],
      [
        '제목 빈 글',
        51,
        'C1',
        custom({ title: '  ' }),
        422,
        'VALIDATION_ERROR',
        ['custom.title'],
      ],
      [
        '제목 201자',
        51,
        'C1',
        custom({ title: LONG }),
        422,
        'VALIDATION_ERROR',
        ['custom.title'],
      ],
      [
        '제목 200 코드 포인트',
        51,
        'C1',
        custom({ title: LONGEST }),
        200,
        null,
        [],
      ],
      [
        '출처 201자',
        51,
        'C1',
        custom({ source: LONG }),
        422,
        'VALIDATION_ERROR',
        ['custom.source'],
      ],
      [
        '사유 빈 글',
        51,
        'C1',
        { ...base, choice: 'applied', reason: ' ' },
        422,
        'VALIDATION_ERROR',
        ['reason'],
      ],
      [
        '사유 301자',
        51,
        'C1',
        { ...base, choice: 'applied', reason: '가'.repeat(301) },
        422,
        'VALIDATION_ERROR',
        ['reason'],
      ],
      [
        '사유 300 코드 포인트',
        51,
        'C1',
        { ...base, choice: 'applied', reason: '😀'.repeat(300) },
        200,
        null,
        [],
      ],
      ...KINDS.map((kind): (typeof TABLE)[number] => [
        `식 있는 kind ${kind}`,
        51,
        'C1',
        { ...custom({}), rowId: `K!${kind}` },
        200,
        null,
        [],
      ]),
      [
        '없는 실행',
        99,
        'C1',
        { ...base, choice: 'applied' },
        404,
        'NOT_FOUND',
        [],
      ],
      [
        '없는 카테고리',
        51,
        'C10',
        { ...base, choice: 'applied' },
        404,
        'NOT_FOUND',
        [],
      ],
      [
        '옛 실행은 줄을 보기 전에 stale',
        50,
        'C1',
        { ...base, rowId: '없음', choice: 'applied' },
        409,
        'STALE_RUN',
        [],
      ],
      [
        '없는 줄(단수 rowId)',
        51,
        'C1',
        { ...base, rowId: '없음', choice: 'applied' },
        422,
        'VALIDATION_ERROR',
        ['rowId'],
      ],
      [
        '계수 객체 없음',
        51,
        'C3',
        { ...base, rowId: 'E!2', choice: 'applied' },
        409,
        'FACTOR_NOT_EDITABLE',
        [],
      ],
      [
        '단위 없음',
        51,
        'C3',
        { ...base, rowId: 'E!3', choice: 'applied' },
        409,
        'FACTOR_NOT_EDITABLE',
        [],
      ],
      [
        '식 없는 C12',
        51,
        'C12',
        { ...base, rowId: 'L!2', choice: 'applied' },
        409,
        'FACTOR_NOT_EDITABLE',
        [],
      ],
      [
        '식 없는 C15',
        51,
        'C15',
        { ...base, rowId: 'I!2', choice: 'applied' },
        409,
        'FACTOR_NOT_EDITABLE',
        [],
      ],
      [
        '409 가 없는 순위보다 앞',
        51,
        'C12',
        pick(1, 'L!2'),
        409,
        'FACTOR_NOT_EDITABLE',
        [],
      ],
      ['없는 순위', 51, 'C1', pick(4), 422, 'VALIDATION_ERROR', ['rank']],
      ['값 null 순위', 51, 'C1', pick(2), 422, 'VALIDATION_ERROR', ['rank']],
      [
        '추천 없는 줄',
        51,
        'C1',
        pick(1, 'P!3'),
        422,
        'VALIDATION_ERROR',
        ['rank'],
      ],
      [
        '값 null 줄은 받는다',
        51,
        'C1',
        { ...custom({}), rowId: 'P!3' },
        200,
        null,
        [],
      ],
      ['셋째 자리 추천', 51, 'C1', pick(3), 200, null, []],
    ];
    const fresh = () =>
      createScope3Ledger(
        [50, 51].map((id) => ({
          id,
          flowId: 'scope3.colab@157',
          options: { reportYear: 2025 },
          result: {
            status: 'done',
            schemaVersion: 'scope3.colab.result@1',
            factorBook: { sheet: '지어낸 계수표', column: '2024' },
            sheets: SHEETS,
          },
        })),
        () => 'done',
        true,
      );
    return { TABLE, fresh, base, custom, pick };
  })();
  const postFactor = (
    ledger: ReturnType<typeof mirror.fresh>,
    run: number,
    category: string,
    body: unknown,
  ) =>
    ledger.answerOf(
      'POST',
      `/inventory/scope3/runs/${run}/categories/${category}/factors`,
      none,
      body,
    )!;
  const pickedOf = (reply: { body: unknown }) =>
    ((reply.body as Json).rows as Json[])[0]!.factor as Json;

  test('S3W3c1 거울: 흉내 판정 차례 표 = 서버 코드·칸', () => {
    for (const [
      name,
      run,
      category,
      body,
      status,
      code,
      fields,
    ] of mirror.TABLE) {
      const reply = postFactor(mirror.fresh(), run, category, body);
      const error = (reply.body as Json).error as Json | undefined;
      expect(reply.status, name).toBe(status);
      expect(error?.code ?? null, name).toBe(code);
      expect(Object.keys((error?.fields as Json) ?? {}).sort(), name).toEqual(
        fields,
      );
    }
    const ledger = mirror.fresh();
    ledger.answerOf(
      'POST',
      '/inventory/scope3/years/2025/categories/C1/lock',
      new URLSearchParams({ runId: '51' }),
      undefined,
    );
    const missing = { ...mirror.base, rowId: '없음', choice: 'applied' };
    expect(
      ((postFactor(ledger, 51, 'C1', missing).body as Json).error as Json).code,
    ).toBe('LOCKED');
    expect(
      postFactor(ledger, 51, 'C1', { ...missing, reason: ' ' }).status,
    ).toBe(422);
  });

  test('S3W3c1 거울: 사건 값 — repr 꼴·추천 글자·AI 원안·단위·applied·생물기원은 줄에서', () => {
    for (const [sent, kept] of [
      ['0.50', '0.5'],
      ['2', '2.0'],
      ['0.00001', '1e-05'],
    ] as const) {
      const body = mirror.custom({
        value: sent,
        title: ' 가 ',
        source: ' 나 ',
      });
      expect(pickedOf(postFactor(mirror.fresh(), 51, 'C1', body))).toEqual({
        choice: 'custom',
        rank: null,
        title: '가',
        value: kept,
        source: '나',
        unit: 'kgCO2e/KRW',
        co2e: E2E_EDITED_CO2E,
        biogenicCo2e: null,
        ai: {
          title: '지어낸 원안',
          value: '0.1',
          source: '지어낸 계수표 2024 판',
          co2e: '5',
        },
      });
    }
    expect(
      pickedOf(postFactor(mirror.fresh(), 51, 'C1', mirror.pick(3))),
    ).toMatchObject({
      choice: 'recommended',
      rank: 3,
      title: '지어낸 다',
      value: '1e-05',
      source: '지어낸 계수표 2024 판',
    });
    const ledger = mirror.fresh();
    const rowId = 'W!2';
    postFactor(ledger, 51, 'C5', { ...mirror.custom({}), rowId });
    const back = postFactor(ledger, 51, 'C5', {
      ...mirror.base,
      rowId,
      choice: 'applied',
    });
    expect(pickedOf(back)).toEqual({
      choice: 'applied',
      rank: null,
      title: 't',
      value: '1',
      source: '지어낸 시트',
      unit: 'kg',
      co2e: '1',
      biogenicCo2e: '0.25',
      ai: { title: 't', value: '1', source: '지어낸 시트', co2e: '1' },
    });
    const biogenic = (rowId: string, category: string) =>
      pickedOf(
        postFactor(mirror.fresh(), 51, category, {
          ...mirror.custom({}),
          rowId,
        }),
      ).biogenicCo2e;
    expect(biogenic('W!2', 'C5')).toBe('0.75');
    expect(biogenic('W!3', 'C5')).toBe('0.0');
    expect(biogenic('P!2', 'C1')).toBeNull();
  });

  test('S3W3c1 장부 recommended·custom·applied 답 = openapi · 거절 몸 = ErrorBody · 칸을 빼면 빨강', () => {
    const { ledger, row } = ledgerOf();
    const schema = answerSchema(`${R}/categories/{category}/factors`, 'post');
    const send = (body: Json) =>
      ledger.answerOf(
        'POST',
        '/inventory/scope3/runs/51/categories/C1/factors',
        none,
        { rowId: row[3], rank: null, custom: null, reason: '흉내', ...body },
      )!;
    const answers = [
      send({ choice: 'recommended', rank: 1 }),
      send({
        choice: 'custom',
        custom: { title: '흉내', value: '0.50', source: '흉내' },
      }),
      send({ choice: 'applied' }),
    ];
    for (const reply of answers) {
      expect(reply.status).toBe(200);
      expect(gaps(reply.body, schema, '$', new Set())).toEqual([]);
    }
    for (const key of ['unit', 'ai', 'biogenicCo2e']) {
      const bad = structuredClone(answers[1]!.body) as Json;
      delete ((bad.rows as Json[])[0]!.factor as Json)[key];
      expect(gaps(bad, schema, '$', new Set())).not.toEqual([]);
    }
    for (const body of [
      { choice: 'recommended', rank: 4 },
      { choice: 'custom', custom: { title: '', value: 'x', source: '' } },
      { choice: 'applied', rowId: '없음' },
    ]) {
      const reply = send(body);
      expect(reply.status).toBe(422);
      expect(gaps(reply.body, schemas.ErrorBody!, '$', new Set())).toEqual([]);
    }
  });

  test('S3W3c1 추천을 실은 결과 본문 = openapi · 값 null 자리 · 칸 이름을 틀리면 빨강', () => {
    const body = e2eDetailResult();
    const row = (
      (body.sheets as Json[]).find(
        (sheet) =>
          sheet.status === 'processed' && sheet.category === 'Category1',
      )!.rows as Json[]
    )[0]!;
    row.recommendations = [
      { title: '흉내 가', value: null, expectedCo2e: null },
      { title: '흉내 나', value: '1e-05', expectedCo2e: '0.3' },
    ];
    expect(gaps(body, resultSchema, '$', new Set())).toEqual([]);
    const renamed = structuredClone(body);
    const item = (
      (
        (renamed.sheets as Json[]).find(
          (sheet) =>
            sheet.status === 'processed' && sheet.category === 'Category1',
        )!.rows as Json[]
      )[0]!.recommendations as Json[]
    )[0]!;
    item.expected = item.expectedCo2e;
    delete item.expectedCo2e;
    expect(gaps(renamed, resultSchema, '$', new Set())).not.toEqual([]);
  });

  test('S3W3a 장부 거절: 상태 번호·code(서버 판정 차례)', () => {
    const { ledger, row } = ledgerOf(false);
    const y = `/inventory/scope3/years/${LAST}`;
    const r = '/inventory/scope3/runs/51';
    const code = (reply: { status: number; body: unknown } | null) => {
      // 거절 몸도 openapi ErrorBody 로 걷는다(legacyCode 는 required).
      expect(gaps(reply!.body, schemas.ErrorBody!, '$', new Set())).toEqual([]);
      return `${reply!.status} ${((reply!.body as Json).error as Json).code as string}`;
    };
    expect(
      code(
        ledger.answerOf('DELETE', `${y}/categories/C1/lock`, none, undefined),
      ),
    ).toBe('403 FORBIDDEN');
    expect(
      code(
        ledger.answerOf(
          'POST',
          `${y}/categories/C1/lock`,
          new URLSearchParams({ runId: '9' }),
          undefined,
        ),
      ),
    ).toBe('404 NOT_FOUND');
    expect(
      code(
        ledger.answerOf(
          'POST',
          `/inventory/scope3/years/${LAST - 1}/categories/C1/lock`,
          new URLSearchParams({ runId: '51' }),
          undefined,
        ),
      ),
    ).toBe('409 NOT_COMPUTED');
    ledger.answerOf(
      'POST',
      `${y}/categories/C1/lock`,
      new URLSearchParams({ runId: '51' }),
      undefined,
    );
    expect(
      code(
        ledger.answerOf('POST', `${r}/categories/C1/exclusions`, none, {
          rowIds: [row[0]],
          reason: '흉내',
        }),
      ),
    ).toBe('409 LOCKED');
    expect(
      code(
        ledger.answerOf('POST', `${r}/categories/C1/factors`, none, {
          rowId: row[0],
          choice: 'applied',
          reason: '흉내',
        }),
      ),
    ).toBe('422 VALIDATION_ERROR');
  });

  test('S3W3b 화면이 낸 몸·쿼리 = openapi: Scope3RowEditIn 칸 그대로 · rowIds 겹침 0 · 히스토리 쿼리 이름 · rowId 늘 실림 · 칸을 더하면 빨강', async ({
    page,
  }) => {
    const { api } = await openDetailRun(page);
    await openCard(page, 'C5');
    const c5 = e2eSheet('C5');
    await pickIn(page, c5, 0).click();
    await pickIn(page, c5, 1).click();
    await detail(page).getByTestId('s3-exclude').click();
    await sendReason(page, '지어낸 제외 사유');
    await expect(rowsOf(page, c5).first()).toHaveAttribute(
      'data-excluded',
      'true',
    );
    await pickIn(page, c5, 0).click();
    await detail(page).getByTestId('s3-restore').click();
    await sendReason(page, '지어낸 복구 사유');
    await expect(rowsOf(page, c5).first()).not.toHaveAttribute(
      'data-excluded',
      'true',
    );
    await rowsOf(page, c5).first().getByTestId('s3-history-open').click();
    await expect(page.getByTestId('s3-history-row').first()).toBeVisible();
    const paths = {
      exclusions:
        '/inventory/scope3/runs/{run_id}/categories/{category}/exclusions',
      restorations:
        '/inventory/scope3/runs/{run_id}/categories/{category}/restorations',
    } as const;
    for (const what of ['exclusions', 'restorations'] as const) {
      const schema = (
        openapi.paths[paths[what]]!.post!.requestBody as {
          content: Record<string, { schema: Schema }>;
        }
      ).content['application/json']!.schema;
      const bodies = editCalls(api, what).map((one) => one.body);
      expect(bodies.length).toBeGreaterThan(0);
      for (const body of bodies) {
        expect(gaps(body, schema, '$', new Set())).toEqual([]);
        const { rowIds } = body as { rowIds: string[] };
        expect(new Set(rowIds).size).toBe(rowIds.length);
        expect(rowIds.length).toBeGreaterThan(0);
        expect(
          gaps({ ...(body as Schema), 더한칸: 1 }, schema, '$', new Set()),
        ).not.toEqual([]);
      }
    }
    const allowed = (
      openapi.paths['/inventory/scope3/runs/{run_id}/history']!.get!
        .parameters as { name: string; in: string }[]
    )
      .filter((one) => one.in === 'query')
      .map((one) => one.name);
    const reads = api.calls.filter(
      (one) => one.method === 'GET' && one.path.endsWith('/history'),
    );
    expect(reads.length).toBeGreaterThan(0);
    for (const read of reads) {
      const query = new URLSearchParams(read.search);
      expect([...query.keys()].filter((key) => !allowed.includes(key))).toEqual(
        [],
      );
      expect(query.get('rowId')).toBe(`${c5}!3`);
    }
  });

  test('RunOut(진행·끝·실패 둘) = openapi RunOut 칸·꼴 그대로', async ({
    page,
  }) => {
    const api = await fakeScope3Api(page);
    const runOut = schemas.RunOut!;
    const base = {
      id: 51,
      documentId: 31,
      flowId: 'scope3.colab@157',
      options: { reportYear: LAST },
      at: 0,
      result: null,
    };
    for (const [script, errorCode] of [
      [['queued'], 'internal'],
      [['done'], 'internal'],
      [['failed'], 'setup_error'],
      [['failed'], 'object_missing'],
    ] as const) {
      const out = api.runOut({ ...base, script: [...script], errorCode });
      expect(gaps(out, runOut, '$', new Set())).toEqual([]);
    }
  });
});

// ── S3D1 ②: S3-15 데이터 다운로드(결과 → 창 → XLSX) · 화면이 낸 GET ↔ openapi 경로 ──
const downloadWords = S3_TEXT.download;
const EXPORT_NAME = `${LAST}_가상회사_Scope3_데이터.xlsx`;
const exportPaths = (() => {
  const doc = JSON.parse(
    readFileSync(
      resolve(
        dirname(fileURLToPath(import.meta.url)),
        '../../api-py/generated/openapi.json',
      ),
      'utf8',
    ),
  ) as { paths: Record<string, Record<string, Json>> };
  return doc.paths;
})();

/** 데이터 엑셀 경로를 흉내 위에 건다(나중에 건 route 가 이긴다) — 받은 요청 경로를 적는다. */
async function routeExport(page: Page, status: 200 | 404 = 200) {
  const seen: string[] = [];
  await page.route(/\/api\/inventory\/scope3\/years\/\d+\/export$/, (route) => {
    const url = new URL(route.request().url());
    seen.push(`${route.request().method()} ${url.pathname}`);
    if (status === 404)
      return route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'NOT_FOUND',
            message: '지어낸-NOT_FOUND',
            fields: null,
          },
        }),
      });
    return route.fulfill({
      status: 200,
      headers: {
        'Content-Type': XLSX_TYPE,
        'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent(EXPORT_NAME)}`,
        'X-Content-Type-Options': 'nosniff',
      },
      body: XLSX,
    });
  });
  return seen;
}

test('S3-15: 결과 → [데이터 다운로드](업로드 오른쪽 끝) → 창 → Scope 3 데이터 → 서버 이름으로 내려받음 · GET 경로 = openapi · 닫으면 초점은 단추', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  const seen = await routeExport(page);
  await runOnce(page);
  await expect(
    page.getByTestId('s3-done').getByTestId('s3-result-card'),
  ).toHaveCount(15, RUN_WAIT);
  const openButton = page.getByTestId('s3-download-open');
  const upload = page
    .getByTestId('s3-result')
    .getByRole('button', { name: resultWords.upload });
  await expect(openButton).toHaveText(resultWords.download);
  const [left, right] = [
    await upload.boundingBox(),
    await openButton.boundingBox(),
  ];
  expect(left!.x + left!.width).toBeLessThanOrEqual(right!.x);
  await openButton.click();
  const dialog = page.getByTestId('s3-download');
  await expect(dialog).toContainText(
    '온실가스 인벤토리에서 관리 중인 데이터예요',
  );
  await expect(dialog.getByTestId('s3-download-file')).toHaveCount(1);
  const downloading = page.waitForEvent('download');
  await dialog.getByTestId('s3-download-file').click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe(EXPORT_NAME);
  expect(seen).toEqual([`GET /api/inventory/scope3/years/${LAST}/export`]);
  expect(
    Object.keys(exportPaths['/inventory/scope3/years/{year}/export']!),
  ).toEqual(['get']);
  await dialog.getByRole('button', { name: downloadWords.ok }).click();
  await expect(dialog).toHaveCount(0);
  await expect(openButton).toBeFocused();
  expect(unrouted).toEqual([]);
});

test('S3-15: 그 해 결과가 없다는 404 → 창에 「받을 데이터가 없어요」(내려받기 0) · [취소] 로 닫힘', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  const seen = await routeExport(page, 404);
  await runOnce(page);
  await expect(
    page.getByTestId('s3-done').getByTestId('s3-result-card'),
  ).toHaveCount(15, RUN_WAIT);
  await page.getByTestId('s3-download-open').click();
  const dialog = page.getByTestId('s3-download');
  await dialog.getByTestId('s3-download-file').click();
  await expect(dialog.getByRole('alert')).toHaveText(downloadWords.notFound);
  expect(seen).toHaveLength(1);
  await dialog.getByRole('button', { name: downloadWords.cancel }).click();
  await expect(dialog).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('S3-15: rejected(그 해 지금 결과 없음)에는 [데이터 다운로드]가 없다', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eRejectedResult('legacy_template')],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-rejected')).toContainText(
    resultWords.rejected.legacy_template,
    RUN_WAIT,
  );
  await expect(page.getByTestId('s3-download-open')).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

// ── S3Q1 — [원본 다운로드] · C12 처리방법별 비중표 · 출처 글 ──
const originalWords = S3_TEXT.original;

test('S3Q1 ①: 상세 표 위 줄 맨 앞 [원본 다운로드] → 그 실행에 올린 파일을 올린 이름·같은 바이트로 내려받음 · GET 경로 = openapi', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C1');
  const tools = detail(page).getByTestId('s3-detail-tools');
  const first = tools.getByRole('button').first();
  await expect(first).toHaveText(originalWords.button);
  await expect(first).toBeEnabled();
  const downloading = page.waitForEvent('download');
  await first.click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe('scope3-sample.xlsx');
  const saved = readFileSync((await download.path())!);
  expect(saved.length).toBe(XLSX.length);
  expect(saved.equals(XLSX)).toBe(true);
  expect(api.count('GET /inventory/scope3/runs/51/original')).toBe(1);
  await expect(detail(page).getByTestId('s3-original-problem')).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('S3Q1 ②: C12 창 — 5열 · 처리방법 셋 + 합계(서버 값) · 타이틀(제품명/코드)·출처 첫 줄만 · 라디오·입력칸 0 · 비중 없는 줄 「-」 · 옛 줄(칸 없음)은 한 줄 표', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eS3Q1Result()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C12');
  const box = factorWindow(page);
  const openRow = async (n: number) => {
    await rowsOf(page, 'c12_흉내').nth(n).getByTestId('s3-window-open').click();
    await expect(box).toBeVisible();
  };
  const close = async () => {
    await page.keyboard.press('Escape');
    await expect(box).toHaveCount(0);
  };
  await openRow(0);
  const table = box.getByTestId('s3-window-treatments');
  await expect(table.getByRole('columnheader')).toHaveText([
    windowWords.columnTitle,
    windowWords.columnTreatment,
    windowWords.columnShare,
    windowWords.columnFactor('kg'),
    windowWords.columnSource,
  ]);
  const lines = table.getByTestId('s3-window-treatment');
  await expect(lines).toHaveCount(3);
  await expect(lines.nth(0).locator('td')).toHaveText([
    `${E2E_C12_NAME}${E2E_C12_CODE}`,
    '매립',
    '20%',
    '0.013',
    '폐기물 배출계수 표',
  ]);
  await expect(lines.nth(1).locator('td')).toHaveText(['소각', '30%', '3.4']);
  await expect(lines.nth(2).locator('td')).toHaveText([
    '재활용',
    '50%',
    '0.0186',
  ]);
  await expect(
    table.getByTestId('s3-window-treatment-total').locator('td'),
  ).toHaveText(['', windowWords.total, '100%', '0.5', '']);
  await expect(box.getByRole('radio')).toHaveCount(0);
  await expect(box.getByRole('textbox')).toHaveCount(0);
  await close();
  await openRow(1);
  // 비중이 하나도 없는 줄(average): 비중 칸·합계 비중 모두 「-」(% 글 0 — 첫 줄만 타이틀 칸이 있어 열 번호로 고르지 않는다).
  await expect(box.getByTestId('s3-window-treatments')).not.toContainText('%');
  await expect(
    box.getByTestId('s3-window-treatment-total').locator('td').nth(2),
  ).toHaveText('-');
  await close();
  await openRow(2);
  await expect(
    box.getByTestId('s3-window-treatment-total').locator('td').nth(3),
  ).toHaveText('-');
  await close();
  await openRow(3);
  await expect(box.getByTestId('s3-window-treatments')).toHaveCount(0);
  await expect(
    box.getByTestId('s3-window-factor').locator('tbody tr'),
  ).toHaveCount(1);
  expect(unrouted).toEqual([]);
});

test('S3Q2: 제품명이 빈 C12 줄(input.name null — openapi ColabRowInputJson 꼴)도 회색 「이름 없음」 단추 · aria 「<n>번 줄 배출계수 보기」 · 누르면 처리방법 표 · rowspan 두 칸 위 맞춤', async ({
  page,
}) => {
  const body = e2eS3Q1Result();
  const sheet = (body.sheets as Json[]).find((one) => one.sheet === 'c12_흉내');
  const rows = (sheet?.rows ?? []) as Json[];
  expect(rows.length).toBeGreaterThan(0);
  rows[0] = { ...rows[0], input: { ...(rows[0]!.input as Json), name: null } };
  const { unrouted } = await open(page, 'service', { runResults: [body] });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C12');
  const opener = rowsOf(page, 'c12_흉내').nth(0).getByTestId('s3-window-open');
  await expect(opener).toHaveText(windowWords.noName);
  await expect(opener).toHaveAttribute('aria-label', windowWords.openAria('3'));
  await expect(opener).toHaveClass(/(^|\s)text-text-tertiary(\s|$)/);
  await expect(
    rowsOf(page, 'c12_흉내').nth(1).getByTestId('s3-window-open'),
  ).not.toHaveAttribute('aria-label', /.+/);
  await opener.click();
  const box = factorWindow(page);
  await expect(box).toBeVisible();
  const spans = box.getByTestId('s3-window-treatments').locator('td[rowspan]');
  await expect(spans).toHaveCount(2);
  for (const n of [0, 1])
    await expect(spans.nth(n)).toHaveCSS('vertical-align', 'top');
  // 제품명이 비면 타이틀 칸은 코드(S3Q1 Q8 갈래 그대로).
  await expect(spans.nth(0)).toHaveText(E2E_C12_CODE);
  expect(unrouted).toEqual([]);
});

test('S3Q1 ③: 출처 칸 — 서버 sourceText(C3 줄 비고·C5 머리 글) · 없으면 지금 꼴(시트 이름)', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'service', {
    runResults: [e2eS3Q1Result()],
  });
  await runOnce(page);
  await expect(page.getByTestId('s3-result-card')).toHaveCount(15, RUN_WAIT);
  await openCard(page, 'C3');
  const box = factorWindow(page);
  await rowsOf(page, 'c3_흉내').nth(0).getByTestId('s3-window-open').click();
  await expect(box.getByTestId('s3-window-factor')).toContainText(E2E_C3_NOTE);
  await page.keyboard.press('Escape');
  await expect(box).toHaveCount(0);
  await rowsOf(page, 'c3_흉내').nth(1).getByTestId('s3-window-open').click();
  await expect(box.getByTestId('s3-window-factor')).toContainText('에너지_C3');
  await expect(box.getByTestId('s3-window-factor')).not.toContainText(
    E2E_C3_NOTE,
  );
  await page.keyboard.press('Escape');
  await back(page, 'C3');
  await openCard(page, 'C5');
  await rowsOf(page, 'c5_흉내').nth(0).getByTestId('s3-window-open').click();
  await expect(box.getByTestId('s3-window-factor')).toContainText(
    E2E_SOURCE_TEXT,
  );
  expect(unrouted).toEqual([]);
});
