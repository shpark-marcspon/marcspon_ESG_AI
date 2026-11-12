// 영문번역 시연 길을 빌드 결과에서(밴드 TRW1a ③ — 발주서 §3-3 13). 서버는 e2e/translation-server.ts 의 흉내(page.route).
// txt 추출본([PAGE 1]~[PAGE 5])은 메모리에서 짓는다(디스크에 .docx·.txt·.xlsx 0). 쪽 수는 서버가 [PAGE n] 최댓값으로 센다(5 — 그리드, 밴드 TRP6).
//   새 번역 → 스토리 1~3 · 일반 4~5 → [번역 시작] → POST /runs 둘(같은 batchId·같은 launchKey, 둘은 다름, Idempotency-Key 다름) →
//   묶음 화면 진행 → 끝남 → 파트 표 [Word] 내려받음 → [모두 받기] 409 → 판 글. 운영 관리자 한 번(목록에 「내가 올린 것만」 0).
import { expect, test } from '@playwright/test';

import { TR_TEXT } from '../src/entities/translation/config/text.ts';
import { signIn } from './session.ts';
import { fakeTranslationApi } from './translation-server.ts';

const words = TR_TEXT.newTranslation;
const TXT = Buffer.from(
  [
    '[PAGE 1]',
    'a',
    '[PAGE 2]',
    'b',
    '[PAGE 3]',
    'c',
    '[PAGE 4]',
    'd',
    '[PAGE 5]',
    'e',
  ].join('\n'),
  'utf8',
);
const XLSX = Buffer.from([80, 75, 3, 4, 1, 2]);

test('TR-02 → TR-03·04: txt 올림 → 스토리 1~3·일반 4~5 → POST /runs 둘(같은 batchId·launchKey) → 끝남 → [Word] 받음 → [모두 받기] 409 글', async ({
  page,
}) => {
  const api = await fakeTranslationApi(page, { archiveTooLarge: true });
  await signIn(page);
  await page.goto('/translation/new');

  await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
    name: 'sample_extract.txt',
    mimeType: 'text/plain',
    buffer: TXT,
  });
  await expect(page.getByTestId('file-meta')).toBeVisible();
  // 서버가 센 쪽 수(5)로 그리드가 뜨고, 글자 칸 안내(쪽 수를 모를 때만)는 없다(밴드 TRP6).
  await expect(page.getByTestId('page-grid')).toBeVisible();
  await expect(page.getByTestId('range-basis')).toHaveCount(0);

  await page.locator('[data-part-field="story"]').fill('1~3');
  await page.locator('[data-part-field="general"]').fill('4~5');
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
  await expect(page.getByTestId('start-blocked')).toHaveCount(0);
  await page.getByTestId('start').click();

  await expect(page).toHaveURL(
    /\/translation\/documents\/12\/batches\/[0-9a-f-]{36}$/,
  );
  const bodies = api.runBodies();
  expect(bodies).toHaveLength(2);
  const batchIds = bodies.map((body) => body.options.batchId);
  const launchKeys = bodies.map((body) => body.launchKey);
  expect(new Set(batchIds).size).toBe(1);
  expect(new Set(launchKeys).size).toBe(1);
  expect(batchIds[0]).not.toBe(launchKeys[0]);
  expect(bodies.map((body) => body.options.part)).toEqual(['story', 'general']);
  expect(bodies.map((body) => body.options.ceoPageLimit)).toEqual([null, null]);
  const idem = api.calls
    .filter((call) => call.method === 'POST' && call.path === '/runs')
    .map((call) => call.idempotencyKey);
  expect(new Set(idem).size).toBe(2);
  // 서명 PUT 에는 Authorization 이 없다.
  const put = api.calls.find((call) => call.path.startsWith('/fake-upload/'))!;
  expect(put.authorization).toBeNull();
  expect(put.size).toBe(TXT.length);

  // 폴링이 진행 → 끝남으로.
  await expect(
    page.getByRole('heading', { name: TR_TEXT.screenTitle.done }),
  ).toBeVisible({ timeout: 15_000 });

  // [TRP2 TC18·TC3·TC2] 1400 폭에서 수 칸 넷이 한 줄 · 파트별 표 머리 칸 바탕 #FAFBFB·왼쪽 정렬 · 완료 배지 바탕 #E2F8F0.
  const summary = page.getByTestId('all-summary');
  const tiles = summary.locator('[data-stat]');
  await expect(tiles).toHaveCount(4);
  const tops = await Promise.all(
    (await tiles.all()).map(async (tile) => (await tile.boundingBox())!.y),
  );
  expect(new Set(tops).size).toBe(1);
  const head = summary.locator('th').first();
  await expect(head).toHaveCSS('background-color', 'rgb(250, 251, 251)');
  await expect(head).toHaveCSS('text-align', 'left');
  await expect(summary.locator('[data-state="done"]').first()).toHaveCSS(
    'background-color',
    'rgb(226, 248, 240)',
  );

  // [TRP3 TB2] [모두 받기] solid-black 바탕 #383C40 · 파트 표 [Word] sm 높이 28.
  await expect(page.getByTestId('download-all')).toHaveCSS(
    'background-color',
    'rgb(56, 60, 64)',
  );
  await expect(
    page.getByRole('button', { name: TR_TEXT.all.word }).first(),
  ).toHaveCSS('height', '28px');

  // [전체] 탭 파트 표의 [Word] → 자동 수정 병기본 내려받음.
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: TR_TEXT.all.word }).first().click();
  expect((await download).suggestedFilename()).toBe(
    'translation-autofix-single.docx',
  );

  // [모두 받기] 409 ARCHIVE_TOO_LARGE → 판 글 하나, 단추 실패 글 0.
  await page.getByTestId('download-all').click();
  await expect(page.getByText(TR_TEXT.all.archiveTooLarge)).toBeVisible();
  await expect(page.getByTestId('download-all-error')).toHaveText('');
});

test('운영 관리자: 목록에 「내가 올린 것만」 0 · 운영 관리자 meta', async ({
  page,
}) => {
  await fakeTranslationApi(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await page.goto('/translation');
  await expect(
    page.getByRole('heading', { name: TR_TEXT.list.title }),
  ).toBeVisible();
  // [WT1] 운영 관리자 설명 줄은 「작업 회사 {company}」 하나(sid:MARC-ENT-625).
  await expect(
    page.getByText(TR_TEXT.list.metaOperator('지어낸 회사'), { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('checkbox', { name: TR_TEXT.list.mineOnly }),
  ).toHaveCount(0);
  await expect(page.getByText(TR_TEXT.shell.adminGreeting)).toBeVisible();
});

test('TR-01 「번역 안내」 → TR-00 → [시작하기] → TR-01', async ({ page }) => {
  await fakeTranslationApi(page);
  await signIn(page);
  await page.goto('/translation');
  // [WT1] 고객사 사용자는 목록 머리 설명 줄 없음(sid:MARC-ENT-625). 다 그려짐 신호는 빈 목록 글(받은 뒤에만 보임).
  await expect(page.getByText(TR_TEXT.list.empty)).toBeVisible();
  await expect(page.getByText(/작업 회사|번역 \d+건/)).toHaveCount(0);

  // [TRP3 TE1] 목록 머리 링크 → TR-00(sid:MARC-ENT-435).
  await page.getByRole('link', { name: TR_TEXT.list.introLink }).click();
  await expect(page).toHaveURL(/\/translation\/intro$/);
  const intro = TR_TEXT.intro;
  // 소개 제목은 text-brand(orange.500 #F25C2C), 안내 상자는 기본 톤 바탕(grey.100 #F3F4F5).
  await expect(
    page.getByRole('heading', { level: 3, name: intro.heading }),
  ).toHaveCSS('color', 'rgb(242, 92, 44)');
  await expect(page.getByTestId('intro-info')).toHaveCSS(
    'background-color',
    'rgb(243, 244, 245)',
  );
  // 그림 한 장(단언 아님): 1440 폭 TR-00.
  await page.setViewportSize({ width: 1440, height: 900 });
  const shot = test.info().outputPath('TR-00-1440.png');
  await page.screenshot({ path: shot, fullPage: true });
  await test.info().attach('TR-00-1440', {
    path: shot,
    contentType: 'image/png',
  });

  // [WS1] [시작하기] → 목록(새 번역이 아니다 — sid:MARC-ENT-625). 빈 목록에도 [새 번역]이 있다(맴돎 없음).
  await page.getByRole('button', { name: intro.start }).click();
  await expect(page).toHaveURL(/\/translation$/);
  const empty = page.getByTestId('list-empty');
  await expect(empty).toContainText(TR_TEXT.list.empty);
  await expect(page.locator('[data-card="file"]')).toHaveCount(0);
  await empty
    .getByRole('button', { name: TR_TEXT.list.newTranslation, exact: true })
    .click();
  await expect(page).toHaveURL(/\/translation\/new$/);
  await expect(page.locator('[data-card="file"]')).toBeVisible();
});

// [TRP4 ⓔ] 결과 화면 수 칸의 움직임: 기본(no-preference)이면 Card 의 계산 animation-name 이 gw-m-rise,
//   줄임 움직임이면 같은 요소가 none(클래스는 붙어 있어도 효과 0). 영문번역 청크가 공용 motion.css 를 싣는다는 실제 브라우저 확인.
//   진행 카드(ⓕ)는 뺐다 — 흉내 서버는 묶음 읽기마다 한 걸음(대기 → 진행 → 끝남)이고 들어오는 탭이 [전체](진행 카드 없음)라 보이는 자리가 없다.
test('TR-04 움직임: 수 칸 Card animation-name gw-m-rise → 줄임 움직임이면 none', async ({
  page,
}) => {
  await fakeTranslationApi(page);
  await signIn(page);
  await page.goto('/translation/new');
  await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
    name: 'sample_extract.txt',
    mimeType: 'text/plain',
    buffer: TXT,
  });
  await expect(page.getByTestId('file-meta')).toBeVisible();
  await page.locator('[data-part-field="story"]').fill('1~3');
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
  await page.getByTestId('start').click();
  await expect(
    page.getByRole('heading', { name: TR_TEXT.screenTitle.done }),
  ).toBeVisible({ timeout: 15_000 });

  const card = page.locator('[data-stat]').first().locator('> *');
  await expect(card).toHaveClass(/gw-m-rise/);
  await expect(card).toHaveCSS('animation-name', 'gw-m-rise');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(card).toHaveCSS('animation-name', 'none');
  await expect(card).toHaveClass(/gw-m-rise/);
});

// [밴드 TRW1b §3-2 10] [이 파트만 다시](결정 sid:MARC-ENT-393·405): 두 파트 시작 → 일반이 서버 오류 → 그 탭 [이 파트만 다시] →
//   POST /runs 셋째의 options = 둘째(일반)의 options 그대로(batchId 같음) · launchKey 는 처음과 다름 → 탭 진행 → 끝남.
test('TR-03 [이 파트만 다시]: 서버 오류 파트 → 같은 옵션·같은 batchId·새 launchKey → 진행 → 끝남', async ({
  page,
}) => {
  const api = await fakeTranslationApi(page, { failParts: ['general'] });
  await signIn(page);
  await page.goto('/translation/new');
  await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
    name: 'sample_extract.txt',
    mimeType: 'text/plain',
    buffer: TXT,
  });
  await expect(page.getByTestId('file-meta')).toBeVisible();
  await page.locator('[data-part-field="story"]').fill('1~3');
  await page.locator('[data-part-field="general"]').fill('4~5');
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
  await page.getByTestId('start').click();
  await expect(
    page.getByRole('heading', { name: TR_TEXT.screenTitle.needs_retry }),
  ).toBeVisible({ timeout: 15_000 });

  await page.getByRole('tab', { name: TR_TEXT.parts.names.general }).click();
  await page.getByRole('button', { name: TR_TEXT.failure.retryPart }).click();
  await expect(page.getByTestId('stage-card')).toBeVisible({
    timeout: 15_000,
  });
  const bodies = api.runBodies();
  expect(bodies).toHaveLength(3);
  const [story, general, again] = bodies as [
    (typeof bodies)[number],
    (typeof bodies)[number],
    (typeof bodies)[number],
  ];
  expect(again.options).toEqual(general.options);
  expect(again.options.batchId).toBe(story.options.batchId);
  expect(again.launchKey).not.toBe(story.launchKey);
  expect(again.launchKey).not.toBe(again.options.batchId);
  // 스토리 20 · 일반 21(흉내 서버 차례) — 일반의 실행을 읽고 다시 보냄.
  expect(api.keys()).toContain('GET /runs/21');
  await expect(
    page.getByRole('heading', { name: TR_TEXT.screenTitle.done }),
  ).toBeVisible({ timeout: 15_000 });
});
