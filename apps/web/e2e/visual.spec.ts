// 시각 비교 첫 판(밴드 VS1 — sid:MARC-ISSUE-198, 결정 sid:MARC-ENT-326). 목 자료로 화면을 열어 1440·1280 두 폭을 찍는다.
//   - 화면마다 한 번 열고 1440 을 찍은 뒤 창을 1280 으로 줄여 다시 찍는다(감독 처분 Q6 (가)). 찍는 범위는 창 크기(Q5).
//   - 자리 단언(e2e/layout-asserts.ts — 가로 스크롤·셀렉터 ▾·GW-05 칩·낱말 안 꺾임·말줄임(KA1))은 기준 그림이 없어도 늘 돈다.
//   - 기준 그림(e2e/visual-baseline.ts 의 폴더)이 없는 장은 그림 견주기만 건너뛰고 annotation visual-baseline-missing 을 단다.
//     묶음 끝에 한 줄(「VISUAL 기준 없음 n/m …」)을 낸다(Q3 (가) — 시험은 통과).
//   - 빨강이면 apps/web/test-results/<시험 폴더>/<이름>-expected·-actual·-diff.png 세 장(find apps/web/test-results -name '*-diff.png').
// 흉내는 기존 도우미만 쓴다(session·greenwash-server·translation-server·dataverify-server·materiality-server·accounts·ai-settings·
// ai-prompt-model·run-logs·audit). 화면에 닿는 길은 그 화면의 기존 스펙을 베꼈다. 시각·씨앗 값은 고정이라 덮개(mask)가 없다.
// 기준 갱신은 main 에서 apps/web/scripts/visual-update.sh 로만(생김새를 바꾸는 밴드는 빨개질 장 이름을 보고에 적는다).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { existsSync } from 'node:fs';

import { TR_TEXT } from '../src/entities/translation/config/text.ts';
import { accountRow, fakeAccountsApi } from './accounts.ts';
import { fakePromptModelApi } from './ai-prompt-model.ts';
import { fakeAiSettingApi } from './ai-settings.ts';
import { auditRow, fakeAuditApi } from './audit.ts';
import { fakeDataverifyApi } from './dataverify-server.ts';
// 이름이 use 로 시작해 React 훅 규칙에 걸린다(훅이 아니다 — sessionStorage 표지를 심는 도우미) — 다른 이름으로 들인다.
import { useMockStore as greenwashMockStore } from './greenwash-server.ts';
import {
  assertChipsInsideCard,
  assertNoHorizontalScroll,
  assertSelectChevrons,
  assertTruncatedOneLine,
  assertWordsUnbroken,
} from './layout-asserts.ts';
import { fakeMaterialityApi } from './materiality-server.ts';
import { fakeRunLogApi, runRow } from './run-logs.ts';
import { fakeAuthApi, signIn } from './session.ts';
import { fakeTranslationApi } from './translation-server.ts';
import { baselineDir } from './visual-baseline.ts';

const WIDTHS = [1440, 1280] as const;
const HEIGHT = 900;
const FIXED_TIME = '2026-10-20T10:00:00+09:00';

test.use({ locale: 'ko-KR', timezoneId: 'Asia/Seoul' });

interface Screen {
  /** 화면 id(시안 번호). 그림 이름은 「<id 소문자>-<state>-<폭>.png」. */
  id: string;
  state: string;
  /** 흉내를 달고 주소를 연다(창 폭 1440, 고정 시각은 이미 걸림). */
  open(page: Page): Promise<void>;
  /** 셀렉터 ▾ 를 잰 개수가 1 이상이어야 하는 화면(빈 검사 막기). */
  selectors?: boolean;
  /** GW-05 칩 카드 안 단언. */
  chips?: boolean;
  /** 찍을 때 창 위 끝에 둘 칸(없으면 쪽 맨 위). 폭을 바꾸면 스크롤 자리가 움직여 폭마다 다시 맞춘다. */
  anchor?: string;
  /** 낱말 가운데서 안 꺾임(밴드 KA1 — 앱 바탕 keep-all). root 안에서 낱말마다 한 번 이상 찾고 두 폭 다 잰다. 낱말은 VS1 6c 검토 그대로. */
  unbroken?: { root: string; words: string[] }[];
  /** 한 줄 말줄임 + title(밴드 KA1 — AD-04 올린 사람). root 안 글이 text 인 칸. */
  truncated?: { root: string; text: string }[];
}

// ── 흉내 자료(지어낸 값) ──

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

/** 새 번역 양식: txt 올림 → 스토리 1~3 · 일반 4~5 (translation-server.spec.ts 의 흐름). */
async function translationForm(page: Page) {
  await fakeTranslationApi(page);
  await signIn(page);
  await page.goto('/translation/new');
  await page.locator('[data-card="file"] input[type="file"]').setInputFiles({
    name: 'sample_extract.txt',
    mimeType: 'text/plain',
    buffer: TXT,
  });
  await expect(page.getByTestId('file-meta')).toBeVisible();
  await expect(page.getByTestId('page-grid')).toBeVisible();
  await page.locator('[data-part-field="story"]').fill('1~3');
  await page.locator('[data-part-field="general"]').fill('4~5');
}

/** 새 번역을 끝까지(끝남 묶음 화면). style = 스타일 라디오 값. */
async function translationDone(page: Page, style: 'B' | 'AB') {
  await translationForm(page);
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
  const words = TR_TEXT.newTranslation;
  await page.getByLabel(words.company.name).fill('Sample Corp');
  await page.getByLabel(words.company.subject).fill('virtual services');
  await page.getByLabel(words.company.standards).fill('GRI');
  await page.locator(`input[type="radio"][value="${style}"]`).check();
  await page.getByTestId('start').click();
  await expect(
    page.getByRole('heading', { name: TR_TEXT.screenTitle.done }),
  ).toBeVisible({ timeout: 15_000 });
}

async function admin(page: Page) {
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
}

const SCREENS: Screen[] = [
  {
    id: 'login',
    state: 'empty',
    open: async (page) => {
      await fakeAuthApi(page, {});
      await page.goto('/login');
    },
  },
  {
    id: 'GW-01',
    state: 'seeds',
    selectors: true,
    open: async (page) => {
      await signIn(page);
      await greenwashMockStore(page);
      await page.goto('/greenwash');
    },
  },
  {
    id: 'GW-02',
    state: 'empty',
    selectors: true,
    open: async (page) => {
      await signIn(page);
      await greenwashMockStore(page);
      await page.goto('/greenwash/new');
    },
  },
  {
    id: 'GW-03',
    state: 'done-run101',
    open: async (page) => {
      await signIn(page);
      await greenwashMockStore(page);
      await page.goto('/greenwash/runs/run-101');
      await expect(page.getByTestId('done-card')).toBeVisible();
    },
  },
  {
    id: 'GW-04',
    state: 'run101',
    open: async (page) => {
      await signIn(page);
      await greenwashMockStore(page);
      await page.goto('/greenwash/runs/run-101/result');
    },
  },
  {
    id: 'GW-05',
    state: 'review-run106',
    chips: true,
    open: async (page) => {
      await signIn(page);
      await greenwashMockStore(page);
      await page.goto('/greenwash/runs/run-106/review');
      await expect(page.getByTestId('review-detail')).toBeVisible();
      // 밴드 GVS1: 목의 지은 PDF(상자 자리에 지어낸 글)로 쪽을 그린다. 첫 문장(10쪽)은 위치가 없고 둘째(11쪽)는 상자가 창 아래 끝이라 셋째(12쪽, 상자 위끝 149pt)를 고른다.
      await page
        .getByTestId('sentence-list')
        .locator('button[data-item="2"]')
        .click();
      const pane = page.getByTestId('review-page');
      await expect(pane.locator('canvas')).toHaveAttribute(
        'data-render-state',
        'done',
        { timeout: 20_000 },
      );
      await expect(pane.getByTestId('highlight').first()).toBeVisible();
    },
  },
  {
    id: 'TR-01',
    state: 'empty',
    open: async (page) => {
      await fakeTranslationApi(page);
      await signIn(page);
      await page.goto('/translation');
    },
  },
  {
    id: 'TR-02',
    state: 'parts',
    anchor: '[data-card="parts"]',
    open: translationForm,
  },
  {
    id: 'TR-03',
    state: 'done-story',
    selectors: true,
    unbroken: [
      { root: '[data-screen="translation-run"]', words: ['대조', '검수하지'] },
    ],
    open: async (page) => {
      await translationDone(page, 'B');
      await page.locator('[role="tab"]').nth(1).click();
      // 파트 탭의 검수 표(유형 FilterSelect)가 그려질 때까지 — 늦게 붙으면 셀렉터 0 으로 잰다
      await expect(
        page.locator('button[data-filter-value]').first(),
      ).toBeVisible();
    },
  },
  {
    id: 'TR-04',
    state: 'ab-all',
    open: async (page) => {
      await translationDone(page, 'AB');
    },
  },
  {
    id: 'DV-01',
    state: 'rows',
    selectors: true,
    open: async (page) => {
      const api = await fakeDataverifyApi(page);
      api.seed(11, {
        input: inputOfDataverify(),
        source: { kind: 'file', name: '가상데이터_2025.json' },
      });
      api.seed(12, { input: inputOfDataverify(), source: { kind: 'paste' } });
      await signIn(page);
      await page.goto('/dataverify');
      await expect(page.locator('tbody tr')).toHaveCount(2);
    },
  },
  {
    id: 'DV-02',
    state: 'empty',
    open: async (page) => {
      await fakeDataverifyApi(page);
      await signIn(page);
      await page.goto('/dataverify/new');
    },
  },
  {
    id: 'DV-04',
    state: 'run11',
    open: async (page) => {
      const api = await fakeDataverifyApi(page);
      api.seed(11, {
        input: inputOfDataverify(),
        source: { kind: 'file', name: '가상데이터_2025.json' },
      });
      await signIn(page);
      await page.goto('/dataverify/runs/11/result');
      await expect(
        page.locator('[data-card="plan"] table td').first(),
      ).toBeVisible();
    },
  },
  {
    id: 'IR-00',
    state: 'intro',
    unbroken: [
      {
        root: '[data-screen="materiality-intro"]',
        words: ['증가', '가운데', '넣어요', '서브토픽마다'],
      },
    ],
    open: async (page) => {
      await fakeMaterialityApi(page);
      await signIn(page);
      await page.goto('/materiality/intro');
    },
  },
  {
    id: 'IR-01',
    state: 'rows',
    open: async (page) => {
      const api = await fakeMaterialityApi(page);
      api.seed(3, 'done');
      await signIn(page);
      await page.goto('/materiality');
      await expect(page.locator('tbody tr')).toHaveCount(1);
    },
  },
  {
    id: 'IR-02',
    state: 'value-chain',
    anchor: '[data-testid="value-chain"]',
    selectors: true,
    unbroken: [{ root: '[data-card="company"]', words: ['(선택)'] }],
    open: async (page) => {
      await fakeMaterialityApi(page);
      await signIn(page);
      await page.goto('/materiality/new');
    },
  },
  {
    id: 'IR-04',
    state: 'run3',
    selectors: true,
    open: async (page) => {
      const api = await fakeMaterialityApi(page);
      api.seed(3, 'done');
      await signIn(page);
      await page.goto('/materiality/runs/3/result');
      await expect(page.locator('tr[data-row="impact"]').first()).toBeVisible();
    },
  },
  {
    id: 'AD-01',
    state: 'rows',
    selectors: true,
    open: async (page) => {
      await admin(page);
      await fakeAccountsApi(page, [
        accountRow(1),
        accountRow(2, { isLocked: true }),
        accountRow(3, { isActive: false }),
      ]);
      await page.goto('/admin/accounts');
      await expect(page.locator('tbody tr')).toHaveCount(3);
    },
  },
  {
    id: 'AD-02',
    state: 'greenwash-model',
    selectors: true,
    open: async (page) => {
      await admin(page);
      await fakeAiSettingApi(page);
      await fakePromptModelApi(page);
      await fakeRunLogApi(page, [runRow(1)]);
      await page.goto('/admin/ai-settings');
      await expect(
        page.locator('[data-screen="admin-ai-settings"]'),
      ).toBeVisible();
      // 모델 설정 칸(ModelCard — 모델 고르기 NativeSelect)을 연 꼴
      await page.getByRole('button', { name: /^모델 설정/ }).click();
      await expect(page.locator('[data-step] select').first()).toBeVisible();
    },
  },
  {
    id: 'AD-04',
    state: 'rows',
    selectors: true,
    // run-logs.ts 의 runRow 올린 사람(createdByName) — 96 칸에 안 들어가는 이름
    truncated: [{ root: 'tr[data-run-id]', text: '지어낸 담당자' }],
    open: async (page) => {
      await admin(page);
      await fakeRunLogApi(page, [
        runRow(3, {
          createdAt: '2026-10-15T16:02:00+09:00',
          isTest: true,
          review: 'in_review',
          aiSetting: { id: 3, name: 'v3' },
        }),
        runRow(2, {
          createdAt: '2026-10-15T15:00:00+09:00',
          module: 'dataverify',
          aiSetting: { id: null, name: 'colab-2026-01-15-v1' },
        }),
        runRow(1, {
          createdAt: '2026-10-15T14:00:00+09:00',
          review: 'pending',
        }),
      ]);
      await page.goto('/admin/runs');
      await expect(page.locator('tr[data-run-id]')).toHaveCount(3);
    },
  },
  {
    id: 'AD-05',
    state: 'rows',
    selectors: true,
    open: async (page) => {
      await admin(page);
      await fakeAuditApi(
        page,
        [
          auditRow(3, {
            at: '2026-10-15T16:02:00+09:00',
            actorKind: 'admin',
            actorUserId: 1,
            actorName: '지어낸 관리자',
            actorUsername: 'ops.admin',
            companyId: null,
            action: 'setting_change',
            event: 'user_created',
            targetKind: 'user',
            targetId: 12,
            targetLabel: 'user12',
          }),
          auditRow(2, { at: '2026-10-15T15:00:00+09:00' }),
          auditRow(1, { at: '2026-10-15T14:00:00+09:00', result: 'failure' }),
        ],
        [],
      );
      await page.goto('/admin/audit');
      await expect(page.locator('[data-screen="admin-audit"]')).toBeVisible();
    },
  },
];

/** 그림 이름(확장자 포함 — 틀의 {arg}{ext}). */
const shotName = (screen: Screen, width: number) =>
  `${screen.id.toLowerCase()}-${screen.state}-${width}.png`;

/** 불러오기가 끝났는가: 뼈대·바쁨 표지 0, PDF 캔버스는 다 그림. 글꼴도 다 받음. */
async function settled(page: Page) {
  // 화면이 그려졌는가(뼈대 0 만 보면 앱이 붙기 전의 빈 쪽도 통과한다)
  await expect(page.getByRole('heading').first()).toBeVisible();
  await page.waitForLoadState('networkidle');
  await expect
    .poll(
      () =>
        page.evaluate(
          () =>
            document.querySelectorAll(
              '[aria-busy="true"], [data-testid="load-skeleton"], [data-skeleton-row], [data-skeleton-bar], [data-testid="title-pending"], [data-testid="description-pending"], canvas[data-render-state]:not([data-render-state="done"])',
            ).length,
        ),
      { timeout: 15_000 },
    )
    .toBe(0);
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

/** 찍는 자리를 고정한다: 초점을 풀고(초점 테두리·스크롤 끌림 0) 칸을 창 위 끝에, 없으면 쪽 맨 위. */
async function frame(page: Page, anchor: string | undefined) {
  await page.evaluate((selector) => {
    (document.activeElement as HTMLElement | null)?.blur();
    if (selector)
      document.querySelector(selector)!.scrollIntoView({ block: 'start' });
    else window.scrollTo(0, 0);
  }, anchor);
}

const missing: string[] = [];
let compared = 0;

test.afterAll(() => {
  const total = missing.length + compared;
  if (missing.length > 0)
    console.log(
      `VISUAL 기준 없음 ${missing.length}/${total} — 그림 견주기 건너뜀(자리 단언은 돎) · 기준 폴더 ${baselineDir()}`,
    );
  else if (total > 0)
    console.log(
      `VISUAL 기준 ${total}/${total} 견줌 · 기준 폴더 ${baselineDir()}`,
    );
});

for (const screen of SCREENS) {
  test(`${screen.id} ${screen.state} ${WIDTHS.join('·')}`, async ({ page }) => {
    await page.setViewportSize({ width: WIDTHS[0], height: HEIGHT });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.clock.setFixedTime(FIXED_TIME);
    await screen.open(page);
    for (const width of WIDTHS) {
      await test.step(`${width}`, async () => {
        if (width !== WIDTHS[0])
          await page.setViewportSize({ width, height: HEIGHT });
        await settled(page);
        await frame(page, screen.anchor);
        const where = `${screen.id} ${screen.state} ${width}`;
        await assertNoHorizontalScroll(page, where);
        const selectCount = await assertSelectChevrons(page, where);
        if (screen.selectors)
          expect(
            selectCount,
            `${where}: 잰 셀렉터 0 — 빈 검사`,
          ).toBeGreaterThan(0);
        let chipCount = 0;
        if (screen.chips) {
          chipCount = await assertChipsInsideCard(page, where);
          expect(chipCount, `${where}: 잰 칩 0 — 빈 검사`).toBeGreaterThan(0);
        }
        let wordCount = 0;
        for (const { root, words } of screen.unbroken ?? [])
          wordCount += await assertWordsUnbroken(page, where, root, words);
        let truncatedCount = 0;
        for (const { root, text } of screen.truncated ?? [])
          truncatedCount += await assertTruncatedOneLine(
            page,
            where,
            root,
            text,
          );
        test.info().annotations.push({
          type: 'visual-measured',
          description: `${where} 셀렉터 ${selectCount} · 칩 ${chipCount} · 낱말 ${wordCount} · 말줄임 ${truncatedCount}`,
        });
        const name = shotName(screen, width);
        // 갱신 실행(visual-update.sh · 임시 자리의 --update-snapshots)은 없는 기준도 찍는다.
        if (
          test.info().config.updateSnapshots === 'none' &&
          !existsSync(test.info().snapshotPath(name, { kind: 'screenshot' }))
        ) {
          missing.push(name);
          test.info().annotations.push({
            type: 'visual-baseline-missing',
            description: name,
          });
          return;
        }
        compared++;
        await expect.soft(page).toHaveScreenshot(name);
      });
    }
  });
}

// 데이터 검증 입력(dataverify-server.spec.ts 의 inputOf 와 같은 꼴 — 지어낸 「가상건설」).
function inputOfDataverify() {
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
  return {
    schemaVersion: 'dataverify.input@1',
    company: {
      name: '가상건설',
      sasbIndustry: 'Engineering & Construction Services',
      materialTopics: ['기후변화 대응'],
      reportingYear: '2025',
    },
    data: {
      환경: [
        item({}),
        item({ ID: 'E-002', 소분류: 'Scope 2', 핵심데이터: 'N' }),
      ],
      사회: [item({ ID: 'S-001', 테마: '사회' })],
    },
  };
}
