// 온실가스 S15 조직구조 시연 길을 빌드 결과에서(밴드 W12-0a ② — 발주서 §2-2 e2e). 서버는 e2e/ghg-server.ts 의 흉내(page.route), 컨테이너 0.
//   고객사 메뉴 「온실가스」 → /ghg → /ghg/organization · 검색 · 일괄 사용취소(ids 정수·본사 빠짐) · [사업장 추가] → 모달 둘 → POST 본문 깊은 같음
//   → 상세 replace → 줄 삭제 + PUT(남은 줄 id 정수) · 본사 행 꺼짐 · 운영 관리자 같은 화면 · 회사 거절 한 갈래.
// ③ S18: 운영 관리자 어드민 메뉴 「AI 설정 › 온실가스」 → 탭 「선택항목」 → /admin/ai-settings/ghg/options 목록(밴드 AD7 — 옛 /admin/options 는 넘김) · 추가 · 수정(PATCH 경로 code_id 정수) · 삭제(ids 정수) · 겹침 거절 · 메뉴 current.
// ① W12-0b1(sid:MARC-ISSUE-426 L3): 코드 지우기는 삭제 표시 — 지운 코드를 쓰는 본사 줄은 이름 그대로 저장 통과 · 모달 드롭다운에서 빠지고 이름 가나다.
// K1b-3(sid:MARC-ISSUE-427): 상세를 연 뒤 다른 탭이 저장(흉내 bumpBranch) → [저장] 409 STALE → 「다른 곳에서 바뀌었어요」 → [다시 불러오기]
//   → 다른 탭이 더한 줄이 보임(줄 n → n+1) → 저장 200(본문 updatedAt = 다시 읽은 판) · 운영 관리자 같은 갈래.
// 흉내 밖 /api/ 요청은 덫(503)으로 적고 끝에 0 인지 본다(IRA2 꼴).
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { writeFileSync } from 'node:fs';

import { ACCOUNT_TEXT } from '../src/entities/account/config/text.ts';
import { GHG_TEXT } from '../src/entities/ghg/config/text.ts';
import { accountRow, fakeAccountsApi } from './accounts.ts';
import { fakeGhgApi } from './ghg-server.ts';
import type { GhgApiOptions } from './ghg-server.ts';
import { signIn } from './session.ts';

const words = GHG_TEXT.organization;
const branch = GHG_TEXT.branch;
const modal = GHG_TEXT.facilityModal;

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
  options: GhgApiOptions = {},
) {
  const unrouted = await trapUnrouted(page);
  const api = await fakeGhgApi(page, options);
  await signIn(
    page,
    kind === 'admin' ? { kind, username: 'ops.admin' } : { kind },
  );
  return { unrouted, api };
}

/** S12-04: 「저장됐어요」 공용 토스트(창 밖 — body 끝 포털, role=status) 가운데 가장 새 것(새 것이 위). */
const savedToast = (page: Page, text: string) =>
  page.getByRole('status').filter({ hasText: text }).first();

const row = (page: Page, name: string) =>
  page.locator('tr[data-branch-id]').filter({ hasText: name });

test('고객사: 메뉴 「온실가스」 → /ghg/dashboard(밴드 DB1) → 「조직구조」 탭 · 본사 행 꺼짐 · 검색 · 일괄 사용취소', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await page.goto('/materiality');
  const nav = page.getByRole('navigation', { name: GHG_TEXT.shell.menuLabel });
  await nav.getByRole('button', { name: GHG_TEXT.shell.menu.ghg }).click();
  await expect(page).toHaveURL(/\/ghg\/dashboard\?year=\d{4}$/);
  await page
    .getByRole('tablist', { name: GHG_TEXT.inventory.tabsLabel })
    .getByRole('tab', { name: GHG_TEXT.inventory.tabs.organization })
    .click();
  await expect(page).toHaveURL(/\/ghg\/organization$/);
  await expect(page.getByRole('heading', { name: words.title })).toBeVisible();
  await expect(nav.locator('[aria-current="page"]')).toHaveText(
    GHG_TEXT.shell.menu.ghg,
  );
  await expect(page.locator('tr[data-branch-id]')).toHaveCount(3);
  const hq = row(page, '본사');
  await expect(hq.getByRole('checkbox')).toBeDisabled();
  await expect(hq.getByRole('switch')).toBeDisabled();
  await expect(hq.getByRole('switch')).toHaveAttribute('aria-checked', 'true');

  await page.getByRole('checkbox', { name: words.selectAll }).click();
  await page.getByRole('button', { name: words.disableSelected }).click();
  await expect(row(page, '제1공장').getByRole('switch')).toHaveAttribute(
    'aria-checked',
    'false',
  );
  expect(api.bodies('POST /branches/inventory')).toEqual([
    { ids: [2, 3], enabled: false },
  ]);

  await page.getByRole('textbox', { name: words.searchLabel }).fill('제2');
  await expect(page.locator('tr[data-branch-id]')).toHaveCount(1);
  expect(api.calls.at(-1)!.query).toContain('q=%EC%A0%9C2');
  // 출발 화면(중대성평가 목록)의 요청은 이 흉내 밖이다.
  expect(
    unrouted.filter((u) => !u.startsWith('GET /api/materiality/')),
  ).toEqual([]);
});

test('/ghg 는 /ghg/dashboard 로 넘긴다(replace — 밴드 DB1)', async ({
  page,
}) => {
  const { unrouted } = await open(page);
  await page.goto('/ghg');
  await expect(page).toHaveURL(/\/ghg\/dashboard\?year=\d{4}$/);
  await expect(page.locator('[data-screen="ghg-dashboard"]')).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('[사업장 추가] → 모달 둘 → POST 본문 → 상세 replace → 줄 삭제 + PUT(남은 줄 id 정수)', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await page.goto('/ghg/organization');
  await page.getByRole('button', { name: words.add }).click();
  await expect(page).toHaveURL(/\/ghg\/organization\/branches\/new$/);
  await page
    .getByRole('textbox', { name: branch.name, exact: true })
    .fill(' 제3공장 ');

  const addLine = async (code: string, detail: string) => {
    await page.getByRole('button', { name: branch.addLine }).click();
    const dialog = page.getByTestId('facility-dialog');
    await dialog.getByRole('combobox', { name: modal.code }).selectOption({
      label: code,
    });
    await dialog.getByRole('textbox', { name: modal.detail }).fill(detail);
    await dialog.getByRole('button', { name: modal.save }).click();
    await expect(dialog).toHaveCount(0);
  };
  await addLine('지어낸 보일러', '1호기');
  await addLine('지어낸 발전기', '비상용');
  // 모달 저장은 화면 목록에만 — 요청 0.
  expect(api.calls.filter((c) => c.method !== 'GET')).toEqual([]);

  await page.getByRole('button', { name: branch.save }).click();
  await expect(page).toHaveURL(/\/ghg\/organization\/branches\/10$/);
  expect(api.bodies('POST /branches')).toEqual([
    {
      name: '제3공장',
      inventoryEnabled: true,
      facilities: [
        { facilityCodeId: 1, detailName: '1호기' },
        { facilityCodeId: 2, detailName: '비상용' },
      ],
    },
  ]);
  await expect(
    page.getByRole('heading', { name: branch.titleEdit }),
  ).toBeVisible();
  await page
    .getByRole('checkbox', { name: branch.selectLine('지어낸 보일러 1호기') })
    .click();
  await page.getByRole('button', { name: branch.removeLines }).click();
  await page.getByRole('button', { name: branch.save }).click();
  await expect(page.getByTestId('branch-saved')).toHaveText(branch.saved);
  expect(api.bodies('PUT /branches/10')).toEqual([
    {
      name: '제3공장',
      inventoryEnabled: true,
      facilities: [{ id: 11, facilityCodeId: 2, detailName: '비상용' }],
      // POST 201 의 판 글자 그대로(밴드 K1b-3).
      updatedAt: '2026-10-29T09:00:00.000001+09:00',
    },
  ]);
  // 뒤로 가기는 빈 폼이 아니라 목록으로.
  await page.goBack();
  await expect(page).toHaveURL(/\/ghg\/organization$/);
  expect(unrouted).toEqual([]);
});

test('운영 관리자: 같은 화면 · 인사말 · [관리자 화면] 단추', async ({
  page,
}) => {
  const { unrouted } = await open(page, 'admin');
  await page.goto('/ghg/organization');
  await expect(page.getByText(GHG_TEXT.shell.adminGreeting)).toBeVisible();
  await expect(page.locator('tr[data-branch-id]')).toHaveCount(3);
  await expect(
    page.getByRole('button', { name: GHG_TEXT.shell.toAdmin }),
  ).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('회사 거절(사용 중지) → 글 한 줄 · 다시 시도 없음', async ({ page }) => {
  const { unrouted } = await open(page, 'admin', {
    company: 'COMPANY_INACTIVE',
  });
  await page.goto('/ghg/organization');
  // 운영 관리자 세션은 「운영 관리자에게 문의」가 없는 글(W12-0b1 ① — sid:MARC-ISSUE-426 회사 글).
  await expect(page.getByTestId('company-refusal')).toHaveText(
    GHG_TEXT.companyOperator.inactive,
  );
  await expect(
    page.getByRole('button', { name: GHG_TEXT.common.retry }),
  ).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('S18 운영 관리자: 메뉴 「AI 설정 › 온실가스」 → 탭 「선택항목」 → 목록 · 추가 · 겹침 · 수정(PATCH 정수 id) · 삭제(ids 정수)', async ({
  page,
}) => {
  const codes = GHG_TEXT.facilityCodes;
  const shell = ACCOUNT_TEXT.shell;
  const unrouted = await trapUnrouted(page);
  const api = await fakeGhgApi(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAccountsApi(page, [accountRow(1)]);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await nav.getByRole('button', { name: shell.menu.aiSettingsGhg }).click();
  await expect(page).toHaveURL(/\/admin\/ai-settings\/ghg\/index$/);
  await page.getByRole('tab', { name: shell.menu.options }).click();
  await expect(page).toHaveURL(/\/admin\/ai-settings\/ghg\/options$/);
  await expect(nav.locator('[aria-current="page"]')).toHaveText([
    shell.menu.aiSettings,
    shell.menu.aiSettingsGhg,
  ]);
  const rows = page.locator('tr[data-code-id]');
  await expect(rows).toHaveCount(3);
  await expect(page.locator('main')).not.toContainText('F0001');

  // 추가 — 빈 칸이면 [저장] 흐림.
  await page.getByRole('button', { name: codes.add }).first().click();
  const dialog = page.getByTestId('code-dialog');
  await expect(dialog.getByRole('button', { name: codes.save })).toBeDisabled();
  await dialog
    .getByRole('textbox', { name: codes.field })
    .fill('지어낸 냉동기');
  await dialog.getByRole('button', { name: codes.save }).click();
  await expect(rows).toHaveCount(4);
  expect(api.bodies('POST /admin/facility-codes')).toEqual([
    { name: '지어낸 냉동기' },
  ]);

  // 겹침 — 웹 검사(요청 0).
  await page.getByRole('button', { name: codes.add }).first().click();
  await dialog
    .getByRole('textbox', { name: codes.field })
    .fill('지어낸 보일러');
  await dialog.getByRole('button', { name: codes.save }).click();
  await expect(dialog.getByTestId('code-duplicate')).toHaveText(
    codes.duplicate,
  );
  expect(api.bodies('POST /admin/facility-codes')).toHaveLength(1);
  await dialog.getByRole('button', { name: codes.cancel }).click();

  // 수정 — 경로 code_id 정수.
  await page
    .getByRole('button', { name: `지어낸 발전기 ${codes.edit}` })
    .click();
  await dialog
    .getByRole('textbox', { name: codes.field })
    .fill('지어낸 비상발전기');
  await dialog.getByRole('button', { name: codes.save }).click();
  await expect(rows.nth(1)).toContainText('지어낸 비상발전기');
  expect(api.bodies('PATCH /admin/facility-codes/2')).toEqual([
    { name: '지어낸 비상발전기' },
  ]);

  // 삭제 — ids 정수.
  await page
    .getByRole('checkbox', { name: codes.selectRow('지어낸 보일러') })
    .click();
  await page.getByRole('button', { name: codes.deleteSelected }).click();
  await page
    .getByTestId('delete-dialog')
    .getByRole('button', { name: codes.confirmDelete })
    .click();
  await expect(rows).toHaveCount(3);
  expect(api.bodies('POST /admin/facility-codes/delete')).toEqual([
    { ids: [1] },
  ]);
  expect(unrouted).toEqual([]);
});

test('W12-0b1 ① 운영 관리자: 「선택항목」에서 지운 코드 — 본사 줄은 이름 그대로 저장 통과 · 모달 목록에서 빠짐(이름 가나다)', async ({
  page,
}) => {
  const codes = GHG_TEXT.facilityCodes;
  const { unrouted, api } = await open(page, 'admin');
  await page.goto('/admin/options');
  await page
    .getByRole('checkbox', { name: codes.selectRow('지어낸 보일러') })
    .click();
  await page.getByRole('button', { name: codes.deleteSelected }).click();
  await page
    .getByTestId('delete-dialog')
    .getByRole('button', { name: codes.confirmDelete })
    .click();
  await expect(page.locator('tr[data-code-id]')).toHaveCount(2);

  await page.goto('/ghg/organization/branches/1');
  await expect(
    page.getByRole('checkbox', {
      name: branch.selectLine('지어낸 보일러 1호기'),
    }),
  ).toBeVisible();
  await page.getByRole('button', { name: branch.save }).click();
  await expect(page.getByTestId('branch-saved')).toHaveText(branch.saved);
  expect(api.bodies('PUT /branches/1')).toEqual([
    {
      name: '본사',
      inventoryEnabled: true,
      facilities: [{ id: 1, facilityCodeId: 1, detailName: '1호기' }],
      updatedAt: '2026-10-28T09:00:00.000001+09:00',
    },
  ]);
  await page.getByRole('button', { name: branch.addLine }).click();
  const options = page
    .getByTestId('facility-dialog')
    .getByRole('combobox', { name: modal.code })
    .locator('option:not([value=""])');
  await expect(options).toHaveText(['지어낸 발전기', '지어낸 사업장 차량']);
  expect(unrouted).toEqual([]);
});

// ── 밴드 K1b-3: 낡은 판(409 STALE) → [다시 불러오기] ──
const branchLines = (page: Page) => page.locator('tr[data-line-key]');

test('K1b-3 고객사: 상세를 연 뒤 다른 탭이 줄을 더해 저장 → [저장] 409 「다른 곳에서 바뀌었어요」 · 폼 그대로 → [다시 불러오기] 확인 → 그 줄이 보임 → 저장 200', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await page.goto('/ghg/organization/branches/2');
  const name = page.getByRole('textbox', { name: branch.name, exact: true });
  await expect(name).toHaveValue('제1공장');
  await expect(branchLines(page)).toHaveCount(0);
  api.bumpBranch(2, { codeId: 2, detailName: '다른 탭 줄' });
  await name.fill('제1공장 고침');
  await page.getByRole('button', { name: branch.save }).click();
  await expect(page.getByTestId('branch-line')).toHaveText(branch.stale);
  await expect(name).toHaveValue('제1공장 고침');
  expect(api.bodies('PUT /branches/2')).toEqual([
    {
      name: '제1공장 고침',
      inventoryEnabled: true,
      facilities: [],
      updatedAt: '2026-10-28T09:00:00.000001+09:00',
    },
  ]);
  // 아무것도 쓰이지 않았다.
  expect(api.branches.find((b) => b.id === 2)!.name).toBe('제1공장');

  await page.getByRole('button', { name: branch.reload }).click();
  const dialog = page.getByTestId('reload-dialog');
  await expect(dialog.getByText(branch.reloadConfirm)).toBeVisible();
  await dialog.getByRole('button', { name: branch.reloadConfirmOk }).click();
  await expect(branchLines(page)).toHaveCount(1);
  await expect(
    page.getByRole('checkbox', {
      name: branch.selectLine('지어낸 발전기 다른 탭 줄'),
    }),
  ).toBeVisible();
  await expect(name).toHaveValue('제1공장');
  await expect(page.getByTestId('branch-line')).toHaveText('');

  await name.fill('제1공장 고침');
  await page.getByRole('button', { name: branch.save }).click();
  await expect(page.getByTestId('branch-saved')).toHaveText(branch.saved);
  expect(api.bodies('PUT /branches/2').at(-1)).toEqual({
    name: '제1공장 고침',
    inventoryEnabled: true,
    facilities: [{ id: 10, facilityCodeId: 2, detailName: '다른 탭 줄' }],
    updatedAt: '2026-10-29T09:00:00.000001+09:00',
  });
  expect(unrouted).toEqual([]);
});

test('K1b-3 운영 관리자: 고친 것 없이 [저장] 409 → [다시 불러오기]는 확인 창 없이 → 줄 n → n+1', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'admin');
  await page.goto('/ghg/organization/branches/1');
  await expect(branchLines(page)).toHaveCount(1);
  api.bumpBranch(1, { codeId: 3, detailName: '다른 탭 차량' });
  await page.getByRole('button', { name: branch.save }).click();
  await expect(page.getByTestId('branch-line')).toHaveText(branch.stale);
  await page.getByRole('button', { name: branch.reload }).click();
  await expect(branchLines(page)).toHaveCount(2);
  await expect(page.getByTestId('reload-dialog')).toHaveCount(0);
  await page.getByRole('button', { name: branch.save }).click();
  await expect(page.getByTestId('branch-saved')).toHaveText(branch.saved);
  expect(unrouted).toEqual([]);
});

// ── 밴드 W12-0b1 ③: S19 온실가스 인덱스 · S20 배출계수(운영 관리자 공통 풀) ──
const pool = GHG_TEXT.pool;
const factorText = GHG_TEXT.factor;
const column = (page: Page, level: string) =>
  page.locator(`section[data-column="${level}"]`);
/** 그 열에서 노드 id 의 고르기 단추(작은 메뉴 단추 말고). */
const nodeButton = (page: Page, level: string, id: string | number) =>
  column(page, level).locator(`li[data-node-id="${id}"] > button`).first();

async function addNode(
  page: Page,
  level: 'scope' | 'source_type' | 'activity',
  name: string,
) {
  await column(page, level)
    .getByRole('button', { name: pool.add[level] })
    .click();
  const dialog = page.getByTestId('name-dialog');
  await dialog.getByRole('textbox').fill(name);
  await dialog.getByRole('button', { name: pool.save }).click();
  await expect(dialog).toBeHidden();
  await column(page, level)
    .getByRole('button', { name, exact: false })
    .first()
    .click();
}

test('W12-0b1 ③ S19 운영 관리자: 메뉴 「AI 설정 › 온실가스」 → 첫 탭 「온실가스 인덱스」 → 4열 · 범위 → 유형 → 활동 추가 · 자산/시설 추가(POST 정수 id) · 메뉴 current', async ({
  page,
}) => {
  const shell = ACCOUNT_TEXT.shell;
  const unrouted = await trapUnrouted(page);
  const api = await fakeGhgApi(page);
  await signIn(page, { kind: 'admin', username: 'ops.admin' });
  await fakeAccountsApi(page, [accountRow(1)]);
  await page.goto('/admin/accounts');
  await expect(page.locator('[data-screen="admin-accounts"]')).toBeAttached();
  const nav = page.getByRole('navigation', { name: shell.menuLabel });
  await nav.getByRole('button', { name: shell.menu.aiSettingsGhg }).click();
  await expect(page).toHaveURL(/\/admin\/ai-settings\/ghg\/index$/);
  await expect(
    page.getByRole('tab', { name: shell.menu.ghgIndex }),
  ).toHaveAttribute('aria-selected', 'true');
  await expect(nav.locator('[aria-current="page"]')).toHaveText([
    shell.menu.aiSettings,
    shell.menu.aiSettingsGhg,
  ]);
  await expect(page.getByRole('heading', { name: pool.title })).toHaveCount(0);
  await expect(page.locator('section[data-column] h3')).toHaveText([
    pool.columns.scope,
    pool.columns.source_type,
    pool.columns.activity,
    pool.columns.facility,
  ]);
  // 처음은 왼쪽부터 첫 항목(배출활동까지) — 판은 닫힘(Q7).
  await expect(column(page, 'facility').locator('li[data-node-id]')).toHaveText(
    ['지어낸 보일러', '지어낸 발전기'],
  );
  await expect(page.getByTestId('facility-panel')).toHaveCount(0);

  await addNode(page, 'scope', '지어낸 기타배출');
  await addNode(page, 'source_type', '지어낸 공정배출');
  await addNode(page, 'activity', '지어낸 공정연료');
  expect(api.bodies('POST /inventory/admin/ghg-index/nodes')).toEqual([
    { level: 'scope', name: '지어낸 기타배출' },
    { level: 'source_type', parentId: 100, name: '지어낸 공정배출' },
    { level: 'activity', parentId: 101, name: '지어낸 공정연료' },
  ]);
  await expect(column(page, 'facility')).toContainText(pool.emptyColumn);

  await column(page, 'facility')
    .getByRole('button', { name: pool.add.facility })
    .click();
  const panel = page.getByTestId('facility-panel');
  await expect(panel.locator('h2')).toHaveText(pool.facilityTitleNew);
  await panel
    .getByRole('combobox', { name: pool.facilityCode })
    .selectOption({ label: '지어낸 보일러' });
  await panel
    .getByRole('combobox', { name: pool.unit, exact: true })
    .selectOption({ label: 't' });
  await page
    .getByTestId('facility-actions')
    .getByRole('button', { name: pool.save })
    .click();
  await expect(panel.locator('h2')).toHaveText('지어낸 보일러');
  await expect(
    column(page, 'facility').locator('[aria-current="true"]'),
  ).toHaveText('지어낸 보일러');
  expect(api.bodies('POST /inventory/admin/ghg-index/facilities')).toEqual([
    {
      parentId: 102,
      facilityCodeId: 1,
      unit: { kind: 'mass', unit: 't' },
      tooltip: '',
    },
  ]);
  expect(unrouted).toEqual([]);
});

test('W12-0b1 ③ S20 운영 관리자: 계수 추가(가스 셋 켬 — 본문 Decimal 글자 깊은 같음) · 기본 바꿈 PUT defaultFactorId 정수 · 자식 있는 노드 지움 409 글', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'admin');
  await page.goto('/admin/ghg-index');
  await nodeButton(page, 'facility', 20).click();
  const panel = page.getByTestId('facility-panel');
  await expect(panel.locator('h2')).toHaveText('지어낸 보일러');
  await expect(panel.locator('tr[data-factor-id]')).toHaveCount(2);

  // 계수 추가 — 가스 셋 켬.
  await panel.getByRole('button', { name: pool.addFactor }).click();
  const dialog = page.getByTestId('factor-dialog');
  await dialog
    .getByLabel(factorText.name, { exact: true })
    .fill('지어낸 새 계수');
  await dialog
    .getByLabel(factorText.source, { exact: true })
    .fill('지어낸 출처');
  await dialog
    .getByRole('combobox', { name: factorText.baseYear })
    .selectOption('2024');
  await dialog
    .getByRole('combobox', { name: factorText.tier })
    .selectOption('1');
  await dialog
    .getByRole('combobox', { name: factorText.country })
    .selectOption('KR');
  await dialog
    .getByRole('combobox', { name: factorText.industry })
    .selectOption('other');
  await dialog
    .getByRole('combobox', {
      name: `${factorText.inputUnit} ${factorText.unitKind}`,
    })
    .selectOption('volume');
  await dialog
    .getByRole('combobox', {
      name: `${factorText.inputUnit} ${factorText.unitName}`,
      exact: true,
    })
    .selectOption('kL');
  const gases: [string, string, string][] = [
    ['CO2', '74100.50', '1'],
    ['CH4', '3', '28'],
    ['N2O', '0.6', '265'],
  ];
  for (const [gas, factor, gwp] of gases) {
    await dialog
      .getByRole('switch', { name: factorText.gasToggle(gas) })
      .click();
    await dialog
      .getByRole('textbox', { name: factorText.gasFactor(gas) })
      .fill(factor);
    await dialog
      .getByRole('textbox', { name: factorText.gasGwp(gas) })
      .fill(gwp);
  }
  await dialog.getByRole('button', { name: factorText.save }).click();
  await expect(dialog).toBeHidden();
  await expect(panel.locator('tr[data-factor-id]')).toHaveCount(3);
  expect(
    api.bodies('POST /inventory/admin/ghg-index/facilities/20/factors'),
  ).toEqual([
    {
      name: '지어낸 새 계수',
      source: '지어낸 출처',
      baseYear: 2024,
      tier: 1,
      countryCode: 'KR',
      industryCode: 'other',
      inputUnit: { kind: 'volume', unit: 'kL' },
      emissionUnit: { kind: 'mass', unit: 'tCO2-eq' },
      ncvEnabled: false,
      ncv: null,
      ncvUnit: null,
      factorUnit: null,
      note: '',
      gases: ['CO2', 'CH4', 'N2O', 'HFCs', 'PFCs', 'SF6', 'NF3'].map((gas) => {
        const on = gases.find(([name]) => name === gas);
        return on ?
            { gas, enabled: true, factor: on[1], gwp: on[2] }
          : { gas, enabled: false };
      }),
    },
  ]);

  // 기본 바꿈 — 토글만 바꿔도 [저장] 켜짐 → PUT defaultFactorId 정수.
  const save = page
    .getByTestId('facility-actions')
    .getByRole('button', { name: pool.save });
  await expect(save).toBeDisabled();
  await panel
    .getByRole('switch', { name: pool.defaultToggle('지어낸 등유 계수') })
    .click();
  await save.click();
  await expect(savedToast(page, pool.saved)).toHaveText(pool.saved);
  expect(api.bodies('PUT /inventory/admin/ghg-index/facilities/20')).toEqual([
    {
      facilityCodeId: 1,
      unit: { kind: 'volume', unit: 'kL' },
      tooltip: '지어낸 툴팁',
      defaultFactorId: 23,
    },
  ]);

  // 자식 있는 노드 지움 → 409 HAS_CHILDREN 글.
  await column(page, 'scope')
    .getByRole('button', { name: pool.menuLabel('지어낸 직접배출') })
    .click();
  await column(page, 'scope')
    .getByRole('group', { name: pool.menuLabel('지어낸 직접배출') })
    .getByRole('button', { name: pool.remove })
    .click();
  await page
    .getByTestId('pool-delete-dialog')
    .getByRole('button', { name: pool.confirmDelete })
    .click();
  await expect(page.getByTestId('pool-notice')).toHaveText(pool.hasChildren);
  expect(api.bodies('POST /inventory/admin/ghg-index/nodes/delete')).toEqual([
    { ids: [1] },
  ]);
  expect(unrouted).toEqual([]);
});

// 검증 R2(② 커밋 전): 흉내의 /facility-codes 이름 가나다 차례와 /branches q 대소문자 무시가 e2e 에서 물리게 —
// 지운 코드 없이 셋(만든 차례 보일러·발전기·사업장 차량 ≠ 가나다) · 영문 이름 사업장을 소문자 q 로.
test('W12-0b1 ③ 흉내 차례: 줄 추가 모달의 코드는 이름 가나다(만든 차례 아님) · 사업장 검색 q 는 대소문자 무시', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  api.branches.push({
    id: 9,
    name: 'Plant-East',
    isHeadquarters: false,
    inventoryEnabled: true,
    lines: [],
    updatedAt: '2026-10-28T09:00:00.000001+09:00',
  });
  await page.goto('/ghg/organization');
  await expect(page.locator('tr[data-branch-id]')).toHaveCount(4);
  await page.getByRole('textbox', { name: words.searchLabel }).fill('plant');
  await expect(page.locator('tr[data-branch-id]')).toHaveCount(1);
  await expect(page.locator('tr[data-branch-id]')).toContainText('Plant-East');

  await page.goto('/ghg/organization/branches/1');
  await page.getByRole('button', { name: branch.addLine }).click();
  await expect(
    page
      .getByTestId('facility-dialog')
      .getByRole('combobox', { name: modal.code })
      .locator('option:not([value=""])'),
  ).toHaveText(['지어낸 발전기', '지어낸 보일러', '지어낸 사업장 차량']);
  expect(unrouted).toEqual([]);
});

// ── 밴드 W12-0b2 ③: S2 온실가스 데이터 자리 · S17 인덱스 설정(고객사·운영 관리자) — S12-02a 뒤 초기 세팅 모달 없음 ──
// 흉내 씨앗: 잎 20(보일러 — 본사 줄·기본 계수 있음) 고를 수 있음 · 22(발전기)는 시험이 제1공장 줄과 기본 계수를 넣어 고를 수 있게 ·
// 24(사업장 차량 — 줄 0·계수 0)는 흐림(S12-05 뒤 까닭 = 기본 계수 없음 하나).
const inventory = GHG_TEXT.inventory;
const settings = GHG_TEXT.indexSettings;
/** S12C1 da787b28: S17 [저장] → 확인 창 「선택하신 인덱스를 저장할까요?」 → [확인](데이터 경고가 없을 때). */
const saveSettings = async (page: Page) => {
  await page.getByRole('button', { name: settings.save }).click();
  const confirm = page.getByTestId('save-confirm');
  await expect(confirm.getByRole('heading')).toHaveText(settings.saveConfirm);
  await confirm.getByRole('button', { name: settings.confirm }).click();
};
const TREE = 'GET /inventory/scope12/index-tree';
const ROWS = 'GET /inventory/scope12/rows';
const SAVE = (year: number) =>
  `PUT /inventory/scope12/index-selections/${year}`;

test('W12-0b2 ③ 고객사: 탭 「온실가스 데이터」 → 고른 0 빈 상태(창 없음 — S12-02a) → [인덱스 설정] → S17 → 잎 둘(흐린 잎 못 고름) → 저장 PUT 정수 id → 「2개」 · 연도 바꿈 → 다른 해 0 빈 상태 · 전체 해제 → []', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  api.branches[1]!.lines.push({ id: 30, codeId: 2, detailName: '1호기' });
  api.poolFactors.push({
    id: 25,
    leafId: 22,
    isDefault: true,
    versions: [],
  });
  // W12-4 ② 564: 연도 없이 들어가면 전년도(sid:MARC-ENT-578 — 고를 수 있는 해는 그대로 올해부터).
  const year = api.thisYear - 1;
  await page.goto('/ghg/organization');
  await expect(page.getByRole('heading', { name: words.title })).toBeVisible();
  const tabs = page.getByRole('tablist', { name: inventory.tabsLabel });
  await expect(
    tabs.getByRole('tab', { name: inventory.tabs.organization }),
  ).toHaveAttribute('aria-selected', 'true');
  await tabs.getByRole('tab', { name: inventory.tabs.inventory }).click();
  await expect(page).toHaveURL(new RegExp(`/ghg/inventory\\?year=${year}$`));

  const dialogs = page.getByRole('dialog');
  await expect(page.getByTestId('inventory-empty')).toContainText(
    inventory.emptyTitle,
  );
  await expect(dialogs).toHaveCount(0); // S12-02a: 묻는 창 없음
  await page.getByRole('button', { name: inventory.indexSettings }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ghg/inventory/index-settings\\?year=${year}$`),
  );
  await expect(
    page.getByRole('heading', { name: settings.title }),
  ).toBeVisible();
  await page
    .getByRole('checkbox', { name: settings.check('지어낸 보일러') })
    .click();
  await page
    .getByRole('checkbox', { name: settings.check('지어낸 발전기') })
    .click();
  await page.getByRole('button', { name: /지어낸 이동연소/ }).click();
  await page.getByRole('button', { name: /지어낸 도로수송/ }).click();
  const blocked = page.getByRole('checkbox', {
    name: settings.check('지어낸 사업장 차량'),
  });
  await expect(blocked).toBeDisabled();
  await expect(page.getByTestId('ghg-node-24')).toContainText(
    settings.noFactor,
  );
  await saveSettings(page);

  await expect(page).toHaveURL(new RegExp(`/ghg/inventory\\?year=${year}$`));
  await expect(page.getByTestId('inventory-row-20')).toBeVisible();
  await expect(page.getByTestId('inventory-row-22')).toBeVisible();
  await expect(savedToast(page, inventory.saved)).toHaveText(inventory.saved);
  await expect(dialogs).toHaveCount(0);
  expect(api.bodies(SAVE(year))).toEqual([{ facilityNodeIds: [20, 22] }]);

  // 연도 바꿈 → 다른 해는 고른 0(해마다 따로) → 빈 상태만(창 없음 — S17 로 가지 않음).
  await page
    .getByRole('combobox', { name: inventory.yearLabel })
    .selectOption(`${year - 1}`);
  await expect(page).toHaveURL(
    new RegExp(`/ghg/inventory\\?year=${year - 1}$`),
  );
  await expect(page.getByTestId('inventory-empty')).toContainText(
    inventory.emptyTitle,
  );
  await expect(dialogs).toHaveCount(0);
  await expect(page).toHaveURL(
    new RegExp(`/ghg/inventory\\?year=${year - 1}$`),
  );
  // S2 는 리스트(rows)를, S17 은 트리를 읽는다(밴드 W12-1a ③).
  const queries = (key: string) =>
    api.calls
      .filter((call) => `${call.method} ${call.path}` === key)
      .map((call) => call.query);
  expect(queries(TREE)).toEqual([`?year=${year}`]);
  expect(queries(ROWS)).toEqual([
    `?year=${year}`,
    `?year=${year}`,
    `?year=${year - 1}`,
  ]);

  // 처음 해(전년도)로 돌아와 [인덱스 설정] → 전체 해제 → 저장 PUT [] → 고른 0 이라 빈 상태(창 없음).
  await page
    .getByRole('combobox', { name: inventory.yearLabel })
    .selectOption(`${year}`);
  await expect(page.getByTestId('inventory-row-22')).toBeVisible();
  await page.getByRole('button', { name: inventory.indexSettings }).click();
  await page.getByRole('button', { name: settings.clearAll }).click();
  await saveSettings(page);
  await expect(page).toHaveURL(new RegExp(`/ghg/inventory\\?year=${year}$`));
  await expect(page.getByTestId('inventory-empty')).toBeVisible();
  await expect(dialogs).toHaveCount(0);
  expect(api.bodies(SAVE(year))).toEqual([
    { facilityNodeIds: [20, 22] },
    { facilityNodeIds: [] },
  ]);
  expect(unrouted).toEqual([]);
});

test('W12-0b2 ③ 운영 관리자: /ghg/inventory → 전년도로 replace(W12-4 ②) · 빈 상태(창 없음) → [인덱스 설정] → S17', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'admin');
  await page.goto('/ghg/inventory');
  await expect(page).toHaveURL(
    new RegExp(`/ghg/inventory\\?year=${api.thisYear - 1}$`),
  );
  await expect(page.getByText(GHG_TEXT.shell.adminGreeting)).toBeVisible();
  await expect(page.getByTestId('inventory-empty')).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: inventory.indexSettings }).click();
  await expect(
    page.getByRole('heading', { name: settings.title }),
  ).toBeVisible();
  await expect(
    page.getByRole('checkbox', { name: settings.check('지어낸 보일러') }),
  ).toBeEnabled();
  expect(unrouted).toEqual([]);
});

test('W12-4 ② 564 → S12-02a: 빈 해에 초기 모달 없음 · Enter 를 눌러도 URL 그대로 · S17 안 감 · 인덱스 쓰기 0', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = api.thisYear - 1;
  await page.goto('/ghg/inventory');
  await expect(page).toHaveURL(new RegExp(`/ghg/inventory\\?year=${year}$`));
  await expect(page.getByTestId('inventory-empty')).toContainText(
    inventory.emptyTitle,
  );
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`/ghg/inventory\\?year=${year}$`));
  await expect(page.getByRole('heading', { name: settings.title })).toHaveCount(
    0,
  );
  expect(
    api.calls.filter(
      (call) =>
        call.method === 'PUT' &&
        call.path.startsWith('/inventory/scope12/index-selections'),
    ),
  ).toEqual([]);
  expect(unrouted).toEqual([]);
});

test('W12-0b2 ③ 회사 거절(모호) → S2 자리 회사 글 · 창 없음', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'service', {
    company: 'COMPANY_AMBIGUOUS',
  });
  await page.goto(`/ghg/inventory?year=${api.thisYear}`);
  await expect(page.getByTestId('company-refusal')).toHaveText(
    GHG_TEXT.company.ambiguous,
  );
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

/** 입력 리스트 씨앗(밴드 W12-1a ③): 올해 잎 20·22 · 앞 해 잎 20 · 값·표시는 지어낸 글자. */
function seedRows(api: Awaited<ReturnType<typeof open>>['api']) {
  const year = api.thisYear;
  api.selections.set(year, new Set([20, 22]));
  api.selections.set(year - 1, new Set([20]));
  api.entryValues.set(20, { [`${year - 1}`]: '7.25', [`${year}`]: '12.125' });
  api.entryValues.set(22, { [`${year}`]: '0.5' });
  api.scopeValues.set(1, { [`${year - 1}`]: '7.25', [`${year}`]: '12.625' });
  api.entryMarks.set(20, { hasMemo: true, estimated: true, locked: true });
  return year;
}

test('W12-1a ③ 고객사 S2 표: 3개년 머리 = 서버 years · 세로 합침 · 메모·추정·자물쇠 · 「-」 · 현황 카드 · 연도 바꿈 → 그 해 · 숨김 단추 0', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedRows(api);
  await page.goto(`/ghg/inventory?year=${year}`);
  const row = page.getByTestId('inventory-row-20');
  await expect(row).toBeVisible();
  const table = page.getByRole('table', {
    name: inventory.tableLabel('지어낸 직접배출'),
  });
  await expect(table.getByRole('columnheader')).toHaveText([
    inventory.head.source,
    inventory.head.activity,
    inventory.head.facility,
    `${year - 2}`,
    `${year - 1}`,
    `${year}`,
    inventory.head.unit,
    inventory.head.memo,
    inventory.head.estimated,
    inventory.head.locked,
  ]);
  await expect(row.getByRole('cell').first()).toHaveAttribute('rowspan', '2');
  await expect(row.getByRole('cell')).toHaveText([
    '지어낸 고정연소',
    '지어낸 액체연료',
    '지어낸 보일러',
    '-',
    '7.25',
    '12.13',
    'tCO2-eq',
    inventory.memoChip,
    '',
    '',
  ]);
  await expect(
    row.getByRole('img', { name: inventory.estimatedLabel }),
  ).toBeVisible();
  await expect(row.getByRole('img', { name: inventory.memoOn })).toBeVisible();
  await expect(
    row.getByRole('img', { name: inventory.lockedLabel }),
  ).toBeVisible();
  const other = page.getByTestId('inventory-row-22');
  await expect(
    other.getByRole('img', { name: inventory.memoOff }),
  ).toBeVisible();
  await expect(other.getByTestId('row-locked')).toHaveCount(0);
  await expect(page.getByTestId('emission-total')).toHaveText('12.63');
  const body = page.locator('[data-screen="ghg-inventory"]');
  for (const name of [/시장기반/, /담당자/])
    await expect(body.getByRole('button', { name })).toHaveCount(0);
  for (const name of [inventory.bulk.uploadOpen, inventory.bulk.downloadOpen])
    await expect(body.getByRole('button', { name })).toBeVisible();
  await expect(body).not.toContainText('참고자료');

  await page
    .getByRole('combobox', { name: inventory.yearLabel })
    .selectOption(`${year - 1}`);
  await expect(page.getByTestId('inventory-row-22')).toHaveCount(0);
  await expect(table.getByRole('columnheader').nth(5)).toHaveText(
    `${year - 1}`,
  );
  await expect(page.getByTestId('emission-total')).toHaveText('7.25');
  expect(unrouted).toEqual([]);
});

test('W12-1a ③ 고객사 S2 검색: 요청 q · 표만 바뀜(카드 그대로) · 0 건 글', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedRows(api);
  await page.goto(`/ghg/inventory?year=${year}`);
  await expect(page.getByTestId('inventory-row-22')).toBeVisible();
  await page.getByLabel(inventory.searchLabel).fill('발전기');
  await expect(page.getByTestId('inventory-row-20')).toHaveCount(0);
  await expect(page.getByTestId('inventory-row-22')).toBeVisible();
  await expect(page.getByTestId('emission-total')).toHaveText('12.63');
  expect(
    api.calls
      .filter((call) => `${call.method} ${call.path}` === ROWS)
      .map((call) => new URLSearchParams(call.query).get('q')),
  ).toEqual([null, '발전기']);
  await page.getByLabel(inventory.searchLabel).fill('없는 이름');
  await expect(page.getByTestId('inventory-search-empty')).toContainText(
    inventory.searchEmpty,
  );
  await expect(page.getByTestId('emission-card')).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('W12-1a ③ 운영 관리자 S2: 같은 표·카드', async ({ page }) => {
  const { unrouted, api } = await open(page, 'admin');
  const year = seedRows(api);
  await page.goto(`/ghg/inventory?year=${year}`);
  await expect(page.getByTestId('inventory-row-20')).toBeVisible();
  await expect(page.getByTestId('emission-card')).toBeVisible();
  await expect(page.getByText(GHG_TEXT.shell.adminGreeting)).toBeVisible();
  expect(unrouted).toEqual([]);
});

// ── 밴드 W12-1b ②: S3 상세 입력(흉내 — 서버 actions/entries.py 를 따름). 숨김 단언은 data-screen 안에서만, 탭 수·탭 글 단언 0.
const entryWords = GHG_TEXT.entry;
const X = (year: number) => `/inventory/scope12/years/${year}/indexes/20`;

/** 잎 20(코드 1): 본사 줄 1 + 제1공장 줄 둘 — 제1공장은 분기. */
function seedEntry(api: Awaited<ReturnType<typeof open>>['api']) {
  const year = seedRows(api);
  api.entryMarks.delete(20);
  api.branches
    .find((b) => b.id === 2)!
    .lines.push(
      { id: 41, codeId: 1, detailName: '지어낸 2호기' },
      { id: 42, codeId: 1, detailName: '지어낸 3호기' },
    );
  api.entryPeriods.set(`${year}:20:2`, 'quarter'); // R1 — 열쇠 해:잎:사업장
  return year;
}

async function openEntry(page: Page, year: number) {
  await page.goto(`/ghg/inventory?year=${year}`);
  await page.getByTestId('inventory-open-20').click();
  const dialog = page.locator('[data-screen="ghg-entry-detail"]');
  await expect(dialog.getByTestId('entry-site-1')).toBeVisible();
  return dialog;
}

async function addRow(page: Page, site: string, name: string) {
  const block = page.getByTestId(`entry-site-${site}`);
  await block.getByRole('button', { name: entryWords.add }).click();
  const add = page.getByTestId('entry-add');
  await add.getByRole('checkbox', { name: entryWords.addPick(name) }).click();
  await add.getByRole('button', { name: entryWords.addOk }).click();
  await expect(add).toHaveCount(0);
  return block;
}

/** 모달 아래 [저장] 하나(W12-1c ① — sid:MARC-ENT-529). */
const saveAll = (dialog: ReturnType<Page['locator']>) =>
  dialog.getByTestId('entry-save').click();

const close = (dialog: ReturnType<Page['locator']>) =>
  dialog.getByRole('button', { name: entryWords.close }).first().click();

test('W12-1b S3 고객사: 칸 → 상세 → 새 행 저장(rowId 없음) → 값 둘·추정만 저장 PUT 깊은 같음 → 닫으면 S2 값 · 분기 블록 칸 넷 · 숨김 0', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const dialog = await openEntry(page, year);
  await expect(dialog.getByTestId('entry-path')).toHaveText(
    '지어낸 직접배출 > 지어낸 고정연소 > 지어낸 액체연료 > 지어낸 보일러',
  );
  await expect(
    dialog.getByTestId('entry-site-1').locator('th[data-slot]'),
  ).toHaveCount(12);
  await expect(
    dialog.getByTestId('entry-site-2').locator('th[data-slot]'),
  ).toHaveText(['1분기', '2분기', '3분기', '4분기']);

  await addRow(page, '1', '1호기');
  await dialog.getByTestId(`entry-amount-n1:${year}-01`).fill('10.5');
  await dialog.getByTestId(`entry-amount-n1:${year}-02`).fill('3');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  const SAVE = `PUT ${X(year)}/sites/1/rows`;
  expect(api.bodies(SAVE).at(-1)).toEqual({
    rows: [
      {
        siteFacilityId: 1,
        unit: 'kL',
        na: false,
        values: [
          { slot: `${year}-01`, amount: '10.5', estimated: false },
          { slot: `${year}-02`, amount: '3', estimated: false },
        ],
      },
    ],
  });

  await dialog.getByTestId(`entry-amount-r1:${year}-02`).fill('4.25');
  await dialog.getByTestId(`entry-amount-r1:${year}-03`).fill('6');
  // S12-03: 추정은 칸 표식 없이 잠금 옆 단추 하나 — 켜면 N/A 아닌 줄의 모든 칸(빈 칸 포함).
  await expect(
    dialog.locator('[data-testid^="entry-estimated-r"]'),
  ).toHaveCount(0);
  const estimate = dialog.getByTestId('entry-estimated');
  await expect(estimate).toHaveAttribute('aria-pressed', 'false');
  await estimate.click();
  await expect(estimate).toHaveAttribute('aria-pressed', 'true');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  await expect.poll(() => api.bodies(SAVE).length).toBe(2);
  const months = Array.from(
    { length: 12 },
    (_, at) => `${year}-${`${at + 1}`.padStart(2, '0')}`,
  );
  const typed: Record<string, string> = {
    [`${year}-01`]: '10.5',
    [`${year}-02`]: '4.25',
    [`${year}-03`]: '6',
  };
  expect(api.bodies(SAVE).at(-1)).toEqual({
    rows: [
      {
        rowId: 1,
        siteFacilityId: 1,
        unit: 'kL',
        na: false,
        values: months.map((slot) => ({
          slot,
          amount: typed[slot] ?? null,
          estimated: true,
        })),
      },
    ],
  });

  // W12-2 ②: [입력 주기 변경]은 블록마다 하나 보인다(분모 = 블록 둘). 복구는 히스토리 창 안에만.
  await expect(dialog.locator('[data-testid^="entry-site-"]')).toHaveCount(2);
  await expect(
    dialog.getByRole('button', { name: entryWords.periodChange.button }),
  ).toHaveCount(2);
  await expect(dialog.getByRole('button', { name: /복구/ })).toHaveCount(0);
  for (const name of [/배출계수 수정/, /계산식/, /담당자/, /참고자료/])
    await expect(dialog.getByRole('button', { name })).toHaveCount(0);
  await expect(dialog).not.toContainText('Scope 3');

  await close(dialog);
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('inventory-row-20')).toContainText('42.5');
  await expect(
    page.getByTestId('inventory-row-20').getByTestId('row-estimated'),
  ).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('W12-1b S3: N/A → 히스토리 글 · 삭제 {ids:[정수]} · 메모 → S2 칩 · 422 칸 · 계수 보기 읽기 전용', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const dialog = await openEntry(page, year);
  const plant = await addRow(page, '2', '지어낸 2호기');
  await addRow(page, '2', '지어낸 3호기');
  await dialog.getByTestId(`entry-amount-n41:${year}-Q2`).fill('5');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  expect(api.bodies(`PUT ${X(year)}/sites/2/rows`).at(-1)).toEqual({
    rows: [
      {
        siteFacilityId: 41,
        unit: 'kL',
        na: false,
        values: [{ slot: `${year}-Q2`, amount: '5', estimated: false }],
      },
      { siteFacilityId: 42, unit: 'kL', na: false, values: [] },
    ],
  });

  // 서버가 그 금액을 거절 → 같은 칸(본문 차례 ≠ 화면 차례).
  api.entryRejectAmount.value = '777';
  await dialog.getByTestId(`entry-amount-r2:${year}-Q3`).fill('777');
  await saveAll(dialog);
  await expect(
    dialog.getByTestId(`entry-amount-r2:${year}-Q3`),
  ).toHaveAttribute('aria-invalid', 'true');
  await expect(dialog.getByTestId(`entry-amount-r2:${year}-Q3`)).toBeFocused();
  await expect(
    dialog.getByTestId(`entry-amount-r1:${year}-Q3`),
  ).not.toHaveAttribute('aria-invalid', 'true');
  await dialog.getByTestId(`entry-amount-r2:${year}-Q3`).fill('');

  await plant
    .getByRole('checkbox', { name: entryWords.naLabel('지어낸 2호기') })
    .click();
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  await dialog.getByTestId('entry-history-r1').click();
  const sheet = page.getByTestId('entry-history');
  await expect(sheet).toContainText(entryWords.history.naOn);
  // W12-2 ②: [복구]는 줄마다 하나(분모 = 줄 수) · 맨 위(N/A 켬) 줄은 꺼짐.
  const historyLines = sheet.locator('tbody tr[data-testid^="entry-history-"]');
  await expect(historyLines).toHaveCount(2);
  await expect(
    sheet.getByRole('button', { name: entryWords.history.restore }),
  ).toHaveCount(2);
  await expect(
    historyLines
      .first()
      .getByRole('button', { name: entryWords.history.restore }),
  ).toBeDisabled();
  const viewport = page.viewportSize()!;
  await expect
    .poll(async () => {
      const box = await sheet.boundingBox();
      return Math.round(box!.y + box!.height);
    })
    .toBe(viewport.height);
  await sheet.getByRole('button', { name: entryWords.close }).click();
  await expect(sheet).toHaveCount(0);

  await dialog.getByTestId('entry-factor-r1').click();
  const factor = page.getByTestId('entry-factor');
  await expect(factor.locator('tr[data-testid^="entry-gas-"]')).toHaveCount(7);
  await expect(factor.getByRole('button')).toHaveCount(1);
  await factor.getByRole('button', { name: entryWords.close }).click();
  await expect(factor).toHaveCount(0);

  await plant
    .getByRole('checkbox', { name: entryWords.selectLabel('지어낸 3호기') })
    .click();
  await plant.getByRole('button', { name: entryWords.remove }).click();
  await page
    .getByTestId('entry-remove')
    .getByRole('button', { name: entryWords.removeOk })
    .click();
  await expect(dialog.getByTestId('entry-row-r2')).toHaveCount(0);
  expect(api.bodies(`POST ${X(year)}/rows/delete`).at(-1)).toEqual({
    ids: [2],
  });

  await dialog
    .getByRole('textbox', { name: entryWords.memoLabel })
    .fill('지어낸 메모');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  await close(dialog);
  await expect(dialog).toHaveCount(0);
  await expect(
    page
      .getByTestId('inventory-row-20')
      .getByRole('img', { name: inventory.memoOn }),
  ).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('W12-1c ① 모달 [저장] 하나: 블록 [저장]·[메모 저장] 0 · 사업장 둘을 고쳐 한 번 → PUT 둘 화면 차례 · 메모 PUT 하나 · 제목 옆 저장됐어요', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const dialog = await openEntry(page, year);
  await expect(
    dialog.getByRole('button', { name: entryWords.save }),
  ).toHaveCount(1);
  await expect(dialog.getByRole('button', { name: '메모 저장' })).toHaveCount(
    0,
  );
  await addRow(page, '1', '1호기');
  await addRow(page, '2', '지어낸 2호기');
  await dialog.getByTestId(`entry-amount-n1:${year}-01`).fill('2');
  await dialog.getByTestId(`entry-amount-n41:${year}-Q1`).fill('7');
  await dialog
    .getByRole('textbox', { name: entryWords.memoLabel })
    .fill('지어낸 메모 둘');
  const from = api.calls.length;
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toHaveText(entryWords.saved);
  expect(
    api.calls
      .slice(from)
      .filter((call) => call.method === 'PUT')
      .map((call) => call.path),
  ).toEqual([
    `${X(year)}/sites/1/rows`,
    `${X(year)}/sites/2/rows`,
    `${X(year)}/memo`,
  ]);
  expect(api.bodies(`PUT ${X(year)}/sites/2/rows`).at(-1)).toEqual({
    rows: [
      {
        siteFacilityId: 41,
        unit: 'kL',
        na: false,
        values: [{ slot: `${year}-Q1`, amount: '7', estimated: false }],
      },
    ],
  });
  expect(api.bodies(`PUT ${X(year)}/memo`).at(-1)).toEqual({
    memo: '지어낸 메모 둘',
  });
  expect(unrouted).toEqual([]);
});

test('W12-1c ② 1280 창: 칸 12 블록 — N/A·배출량·히스토리 머리가 모달 안 오른쪽에 보임 · 막대 12 · 끝까지 스크롤하면 커서 오른쪽 끝 · 블록 둘 「상세 시설명」 열 x 같음 · 입력 칸 36 · 머리 44', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const dialog = await openEntry(page, year);
  await addRow(page, '1', '1호기');
  await addRow(page, '2', '지어낸 2호기');
  const content = dialog;
  const box = (await content.boundingBox())!;
  const inner = { left: box.x + 32, right: box.x + box.width - 32 };
  const block = dialog.getByTestId('entry-site-1');
  await expect(block.locator('th[data-slot]')).toHaveCount(12);
  for (const name of [
    'N/A',
    entryWords.head.emission,
    entryWords.historyHead,
  ]) {
    const head = block.locator('thead th').filter({ hasText: name }).first();
    await expect(head).toBeVisible();
    const rect = (await head.boundingBox())!;
    expect(rect.x).toBeGreaterThanOrEqual(inner.left);
    expect(rect.x + rect.width).toBeLessThanOrEqual(inner.right + 1);
  }
  const bar = dialog.getByTestId('entry-bar-1');
  await expect(bar).toBeVisible();
  expect(Math.round((await bar.boundingBox())!.height)).toBe(12);
  const scroller = dialog.getByTestId('entry-scroll-1');
  const cursor = dialog.getByTestId('entry-bar-1-cursor');
  const barBox = (await bar.boundingBox())!;
  expect((await cursor.boundingBox())!.x).toBeLessThan(barBox.x + 1);
  await scroller.evaluate((el) => {
    el.scrollLeft = el.scrollWidth;
  });
  await expect
    .poll(async () => {
      const c = (await cursor.boundingBox())!;
      return Math.round(barBox.x + barBox.width - (c.x + c.width));
    })
    .toBe(0);
  await scroller.evaluate((el) => {
    el.scrollLeft = 0;
  });
  await expect
    .poll(async () => (await cursor.boundingBox())!.x)
    .toBeLessThan(barBox.x + 1);
  // 커서 끌기 → 표가 스크롤된다(Q5 맞물림 반대 방향).
  const start = (await cursor.boundingBox())!;
  await page.mouse.move(start.x + start.width / 2, start.y + start.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    start.x + start.width / 2 + 200,
    start.y + start.height / 2,
    { steps: 5 },
  );
  await page.mouse.up();
  expect(await scroller.evaluate((el) => el.scrollLeft)).toBeGreaterThan(0);
  await scroller.evaluate((el) => {
    el.scrollLeft = 0;
  });
  const detailX = async (site: string) =>
    (await dialog
      .getByTestId(`entry-site-${site}`)
      .locator('thead th')
      .nth(1)
      .boundingBox())!.x;
  expect(Math.round(await detailX('1'))).toBe(Math.round(await detailX('2')));
  const input = dialog.getByTestId(`entry-amount-n1:${year}-01`);
  expect(Math.round((await input.boundingBox())!.height)).toBe(36);
  expect(
    Math.round((await block.locator('thead th').first().boundingBox())!.height),
  ).toBe(44);
  expect(unrouted).toEqual([]);
});

test('W12-1c ③ 1280 창: 카드 합계 문턱 양쪽(11자 body-01 폭 ≤ 117 · 12자 줄임표) · 히스토리 폭 = 창 − 64 · 계수 폭 ≤ 1320 · 추가 창 980 · 확인 창 위 안쪽 64', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  for (const [total, cut] of [
    ['12345678.12', false],
    ['123456789.12', true],
  ] as const) {
    api.scopeValues.set(1, { [`${year}`]: total });
    await page.goto(`/ghg/inventory?year=${year}`);
    const shown = page.getByTestId('emission-total');
    await expect(shown).toHaveText(total);
    await page.evaluate(() => document.fonts.ready);
    const size = await shown.evaluate((el) => ({
      width: el.getBoundingClientRect().width,
      scroll: el.scrollWidth,
      client: el.clientWidth,
      overflow: getComputedStyle(el).textOverflow,
    }));
    expect(size.width).toBeLessThanOrEqual(117);
    if (cut) {
      expect(size.overflow).toBe('ellipsis');
      expect(size.scroll).toBeGreaterThan(size.client);
      await expect(shown).toHaveAttribute('aria-label', total);
    } else expect(size.scroll).toBeLessThanOrEqual(Math.ceil(size.client));
  }
  api.scopeValues.delete(1);

  const dialog = await openEntry(page, year);
  await page
    .getByTestId('entry-site-1')
    .getByRole('button', { name: entryWords.add })
    .click();
  const add = page.getByTestId('entry-add');
  await expect(add).toBeVisible();
  await expect
    .poll(async () => Math.round((await add.boundingBox())!.width))
    .toBe(980);
  await add
    .getByRole('checkbox', { name: entryWords.addPick('1호기') })
    .click();
  await add.getByRole('button', { name: entryWords.addOk }).click();
  await dialog.getByTestId(`entry-amount-n1:${year}-01`).fill('2');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();

  await dialog.getByTestId('entry-history-r1').click();
  const sheet = page.getByTestId('entry-history');
  await expect
    .poll(async () => Math.round((await sheet.boundingBox())!.width))
    .toBe(1280 - 64);
  await sheet.getByRole('button', { name: entryWords.close }).click();
  await expect(sheet).toHaveCount(0);

  await dialog.getByTestId('entry-factor-r1').click();
  const factor = page.getByTestId('entry-factor');
  await expect(factor).toBeVisible();
  // 여는 애니메이션(잠깐 작게 시작) 뒤 값 — 1280 창이면 상한 1320 보다 창 − 64 가 작다.
  await expect
    .poll(async () => Math.round((await factor.boundingBox())!.width))
    .toBe(1280 - 64);
  expect(1280 - 64).toBeLessThanOrEqual(1320);
  await factor.getByRole('button', { name: entryWords.close }).click();
  await expect(factor).toHaveCount(0);

  await dialog.getByTestId(`entry-amount-r1:${year}-02`).fill('3');
  await dialog.getByRole('button', { name: entryWords.close }).first().click();
  const leave = page.getByTestId('entry-leave');
  await expect(leave).toBeVisible();
  await expect
    .poll(async () => Math.round((await leave.boundingBox())!.width))
    .toBe(420);
  const pad = await leave.evaluate((el) => {
    const style = getComputedStyle(el);
    return [
      style.paddingTop,
      style.paddingRight,
      style.paddingBottom,
      style.paddingLeft,
    ];
  });
  expect(pad).toEqual(['64px', '16px', '32px', '16px']);
  const title = leave.getByRole('heading');
  const footer = leave.getByRole('button', { name: entryWords.cancel });
  const gap =
    (await footer.boundingBox())!.y -
    ((await title.boundingBox())!.y + (await title.boundingBox())!.height);
  expect(Math.round(gap)).toBe(32);
  expect(unrouted).toEqual([]);
});

test('W12-1d 1280 창: 덧씌움이 이김(총합 줄 700 · 수정자 주황 · 계수 라벨 500) · 배출량 칸 오른쪽 · 포함 체크 켬 주황 / 끔 회색 · 표 기본 막대 숨김', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const dialog = await openEntry(page, year);
  const orange = await page.evaluate(() => {
    const probe = document.createElement('span');
    probe.className = 'text-text-brand';
    document.body.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  });
  expect(orange).toBe('rgb(242, 92, 44)');
  // 끔 상자 = 키트 disabled 바탕(background-tertiary — 판 끔 회색과 같은 토큰).
  const grey = await page.evaluate(() => {
    const probe = document.createElement('span');
    probe.className = 'bg-background-tertiary';
    document.body.append(probe);
    const color = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return color;
  });

  // 행 하나를 더해 저장(배출량 칸·히스토리 줄이 생긴다).
  await addRow(page, '1', '1호기');
  await dialog.getByTestId(`entry-amount-n1:${year}-01`).fill('2');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();

  // 총합 줄(분모 먼저).
  const sumCells = dialog.getByTestId('entry-total-all').locator('td');
  expect(await sumCells.count()).toBeGreaterThan(0);
  for (const weight of await sumCells.evaluateAll((tds) =>
    tds.map((td) => getComputedStyle(td).fontWeight),
  ))
    expect(weight).toBe('700');

  // 배출량 칸 오른쪽 · 표 스크롤 상자 기본 막대 숨김(헤드리스는 막대 높이 0 이라 높이로는 못 잼 — 꼴 값으로).
  const emission = dialog.getByTestId('entry-emission-r1');
  await expect(emission).toBeVisible();
  expect(await emission.evaluate((el) => getComputedStyle(el).textAlign)).toBe(
    'right',
  );
  const scrollers = dialog.locator('[data-testid^="entry-scroll-"]');
  expect(await scrollers.count()).toBeGreaterThan(0);
  for (const width of await scrollers.evaluateAll((els) =>
    els.map((el) => getComputedStyle(el).scrollbarWidth),
  ))
    expect(width).toBe('none');

  // 히스토리 수정자 주황.
  await dialog.getByTestId('entry-history-r1').click();
  const sheet = page.getByTestId('entry-history');
  const lines = sheet.locator('tbody tr[data-testid^="entry-history-"]');
  await expect(lines.first()).toBeVisible();
  expect(await lines.count()).toBeGreaterThan(0);
  for (const color of await lines.evaluateAll((trs) =>
    trs.map((tr) => getComputedStyle(tr.querySelectorAll('td')[1]!).color),
  ))
    expect(color).toBe(orange);
  await sheet.getByRole('button', { name: entryWords.close }).click();
  await expect(sheet).toHaveCount(0);

  // 계수 창 — 라벨 500 · 포함 체크 켬 주황 / 끔 회색.
  await dialog.getByTestId('entry-factor-r1').click();
  const factor = page.getByTestId('entry-factor');
  await expect(factor).toBeVisible();
  const labels = factor.getByTestId('entry-factor-fields').locator('th');
  expect(await labels.count()).toBeGreaterThan(0);
  for (const weight of await labels.evaluateAll((ths) =>
    ths.map((th) => getComputedStyle(th).fontWeight),
  ))
    expect(weight).toBe('500');
  const boxes = factor.locator(
    'tr[data-testid^="entry-gas-"] [role="checkbox"]',
  );
  expect(await boxes.count()).toBeGreaterThan(1);
  const looks = await boxes.evaluateAll((els) =>
    els.map((el) => ({
      on: el.getAttribute('aria-checked') === 'true',
      disabled: (el as HTMLButtonElement).disabled,
      bg: getComputedStyle(el).backgroundColor,
    })),
  );
  expect(looks.filter((look) => look.on).length).toBeGreaterThan(0);
  expect(looks.filter((look) => !look.on).length).toBeGreaterThan(0);
  for (const look of looks) {
    expect(look.disabled).toBe(true);
    if (look.on) expect(look.bg).toBe(orange);
    else {
      expect(look.bg).not.toBe(orange);
      expect(look.bg).toBe(grey);
    }
  }
  expect(unrouted).toEqual([]);
});

test('W12-1b 잠금: 고객사 [잠금] → 비활성 · S2 자물쇠 · 풀기 0 / 운영 관리자 풀기', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const dialog = await openEntry(page, year);
  await addRow(page, '1', '1호기');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  await dialog.getByRole('button', { name: entryWords.lock }).click();
  // R6: 고객사는 고친 것이 없어도 확인 창.
  const confirm = page.getByTestId('entry-lock-confirm');
  await expect(confirm).toContainText(entryWords.lockConfirmPlain);
  await confirm.getByRole('button', { name: entryWords.lockOk }).click();
  await expect(dialog.getByTestId('entry-locked')).toBeVisible();
  await expect(dialog.getByTestId('entry-locked-by')).toContainText(
    '지어낸-사람',
  );
  await expect(dialog.getByTestId(`entry-amount-r1:${year}-01`)).toBeDisabled();
  await expect(
    dialog.getByRole('button', { name: entryWords.unlock }),
  ).toHaveCount(0);
  await close(dialog);
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByTestId('inventory-row-20').getByTestId('row-locked'),
  ).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('W12-1b 운영 관리자: 잠긴 인덱스 [잠금 해제] → DELETE → 입력 켜짐', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'admin');
  const year = seedEntry(api);
  const dialog = await openEntry(page, year);
  await addRow(page, '1', '1호기');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  await dialog.getByRole('button', { name: entryWords.lock }).click();
  await dialog.getByRole('button', { name: entryWords.unlock }).click();
  await expect(dialog.getByTestId('entry-locked')).toHaveCount(0);
  await expect(dialog.getByTestId(`entry-amount-r1:${year}-01`)).toBeEnabled();
  expect(
    api.calls.filter(
      (call) => `${call.method} ${call.path}` === `DELETE ${X(year)}/lock`,
    ),
  ).toHaveLength(1);
  expect(unrouted).toEqual([]);
});

test('W12-1b 회사 거절: 상세를 열 때 모호 → 모달 안 회사 글(운영 관리자)', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'admin');
  const year = seedEntry(api);
  await page.route(/\/indexes\/20(\?|$)/, (route) =>
    route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'COMPANY_AMBIGUOUS', message: 'x', fields: {} },
      }),
    }),
  );
  await page.goto(`/ghg/inventory?year=${year}`);
  await page.getByTestId('inventory-open-20').click();
  await expect(page.getByTestId('entry-company-refusal')).toContainText(
    GHG_TEXT.companyOperator.ambiguous,
  );
  expect(unrouted).toEqual([]);
});

// ── 밴드 W12-2 ①: 흉내 ↔ openapi — 새 경로 둘(입력주기 PUT · 복구 POST)의 요청·응답 칸을 generated/openapi.json 과 견준다(응답 ⊆ · 요청 =).
test('W12-2 ① 흉내 ↔ openapi: period·restore 응답 칸 ⊆ EntryIndexOut · 히스토리 칸 ⊆ EntryHistoryOut(restorable 필수) · 요청 칸 = EntryPeriodIn·EntryRestoreIn', async ({
  page,
}) => {
  const { readFileSync } = await import('node:fs');
  const openapi = JSON.parse(
    readFileSync(
      new URL('../../api-py/generated/openapi.json', import.meta.url),
      'utf8',
    ),
  ) as {
    components: {
      schemas: Record<
        string,
        { properties: Record<string, unknown>; required?: string[] }
      >;
    };
  };
  const schemas = openapi.components.schemas;
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  await page.goto(`/ghg/inventory?year=${year}`);
  await expect(page.getByTestId('inventory-row-20')).toBeVisible();
  const call = (method: string, path: string, body?: unknown) =>
    page.evaluate(
      async ([m, p, b]) => {
        const res = await fetch(`/api${p as string}`, {
          method: m as string,
          headers: { 'content-type': 'application/json' },
          body: b === undefined ? undefined : JSON.stringify(b),
        });
        return { status: res.status, json: await res.json() };
      },
      [method, path, body] as const,
    );
  const saved = await call('PUT', `${X(year)}/sites/1/rows`, {
    rows: [
      {
        siteFacilityId: 1,
        unit: 'kL',
        na: false,
        values: [{ slot: `${year}-01`, amount: '2', estimated: false }],
      },
    ],
  });
  expect(saved.status).toBe(200);
  const period = await call('PUT', `${X(year)}/sites/1/period`, {
    period: 'quarter',
  });
  expect(period.status).toBe(200);
  const keys = (o: object) => Object.keys(o).sort();
  const within = (name: string, o: object) =>
    expect(
      keys(o).filter((k) => !(k in schemas[name]!.properties)),
      name,
    ).toEqual([]);
  within('EntryIndexOut', period.json);
  within('EntrySiteOut', period.json.sites[0]);
  within('EntryTotalsOut', period.json.totals);
  const history = await call(
    'GET',
    `${X(year)}/rows/1/history?page=1&pageSize=20`,
  );
  expect(history.json.results).toHaveLength(2);
  for (const line of history.json.results) within('EntryHistoryOut', line);
  expect(schemas.EntryHistoryOut!.required).toContain('restorable');
  expect(
    history.json.results.map((l: { restorable: boolean }) => l.restorable),
  ).toEqual([false, false]); // 맨 위 period · 분기 아래의 월 value(낡음)
  const restore = await call(
    'POST',
    `${X(year)}/rows/1/history/${history.json.results[1].historyId}/restore`,
    {},
  );
  expect([restore.status, restore.json.error.code]).toEqual([
    409,
    'RESTORE_STALE',
  ]);
  // 요청 = openapi(이 시험이 보낸 본문 열쇠 ⊆ 꼴 · 꼴의 열쇠는 웹 거울 ENTRY_REQUEST_FIELDS 가 vitest 에서 잰다)
  expect(keys(schemas.EntryPeriodIn!.properties)).toEqual(['period']);
  expect(keys(schemas.EntryRestoreIn!.properties)).toEqual(['reason']);
  expect(api.bodies(`PUT ${X(year)}/sites/1/period`)).toEqual([
    { period: 'quarter' },
  ]);
  expect(unrouted).toEqual([]);
});

// ── 밴드 W12-3 ②: 흉내 ↔ openapi 한 걸음 — 계수 바꿈 PUT(풀·직접입력)·548·factor 줄 복구(사유)·R1·R3·R4 ──
test('W12-3 ② 흉내 ↔ openapi: PUT factor 응답 ⊆ EntryIndexOut·EntryRowOut·EntryFactorOut|EntryCustomFactorOut · 히스토리 참조 ⊆ EntryFactorRefOut · 548 422 · R1·R3·R4 · 고객사 403', async ({
  page,
}) => {
  const { readFileSync } = await import('node:fs');
  const openapi = JSON.parse(
    readFileSync(
      new URL('../../api-py/generated/openapi.json', import.meta.url),
      'utf8',
    ),
  ) as {
    components: {
      schemas: Record<string, { properties: Record<string, unknown> }>;
    };
  };
  const schemas = openapi.components.schemas;
  const { unrouted, api } = await open(page, 'admin');
  const year = seedEntry(api);
  // R1 대조용: 잎 22(코드 2)도 제1공장(분기 — 잎 20 의 블록 주기)에 줄 하나
  api.branches
    .find((b) => b.id === 2)!
    .lines.push({ id: 43, codeId: 2, detailName: '지어낸 발전기 1호' });
  await page.goto(`/ghg/inventory?year=${year}`);
  await expect(page.getByTestId('inventory-row-20')).toBeVisible();
  const call = (method: string, path: string, body?: unknown) =>
    page.evaluate(
      async ([m, p, b]) => {
        const res = await fetch(`/api${p as string}`, {
          method: m as string,
          headers: { 'content-type': 'application/json' },
          body: b === undefined ? undefined : JSON.stringify(b),
        });
        return { status: res.status, json: await res.json() };
      },
      [method, path, body] as const,
    );
  const keys = (o: object) => Object.keys(o).sort();
  const within = (name: string, o: object) =>
    expect(
      keys(o).filter((k) => !(k in schemas[name]!.properties)),
      name,
    ).toEqual([]);
  const saved = await call('PUT', `${X(year)}/sites/1/rows`, {
    rows: [
      {
        siteFacilityId: 1,
        unit: 'kL',
        na: false,
        values: [{ slot: `${year}-01`, amount: '2', estimated: false }],
      },
    ],
  });
  expect(saved.status).toBe(200);
  const rowOf = (out: { sites: { siteId: string; rows: object[] }[] }) =>
    out.sites.find((s) => s.siteId === '1')!.rows[0] as {
      emission: string | null;
      factor: Record<string, unknown> | null;
    };
  // 풀 계수(잎 20 의 둘째 23) → 응답 꼴 ⊆ · 배출량은 그 계수 글자
  const pooled = await call('PUT', `${X(year)}/rows/1/factor`, {
    factorId: 23,
    reason: '지어낸 사유',
  });
  expect(pooled.status).toBe(200);
  within('EntryIndexOut', pooled.json);
  within('EntryRowOut', rowOf(pooled.json));
  within('EntryFactorOut', rowOf(pooled.json).factor!);
  expect(rowOf(pooled.json).emission).toBe('2.23');
  // 직접입력 → EntryCustomFactorOut 꼴
  const body = {
    name: '지어낸 직접 계수',
    source: '지어낸 출처',
    baseYear: 2024,
    tier: 1,
    countryCode: 'KR',
    industryCode: 'energy_industries',
    inputUnit: { kind: 'volume', unit: 'kL' },
    emissionUnit: { kind: 'mass', unit: 'tCO2-eq' },
    ncvEnabled: false,
    ncv: null,
    ncvUnit: null,
    factorUnit: null,
    note: '',
    gases: [{ gas: 'CO2', enabled: true, factor: '2.5', gwp: '1' }],
  };
  expect(keys(body)).toEqual(keys(schemas.GhgFactorIn!.properties));
  const custom = await call('PUT', `${X(year)}/rows/1/factor`, {
    custom: body,
    reason: '지어낸 사유 둘',
  });
  expect(custom.status).toBe(200);
  within('EntryCustomFactorOut', rowOf(custom.json).factor!);
  // 548 흉내: 잎 kL 로 셈할 수 없는 투입 단위 → 422 custom.inputUnit
  const mismatch = await call('PUT', `${X(year)}/rows/1/factor`, {
    custom: { ...body, inputUnit: { kind: 'electricity', unit: 'GWh' } },
    reason: '지어낸 사유',
  });
  expect([mismatch.status, keys(mismatch.json.error.fields)]).toEqual([
    422,
    ['custom.inputUnit'],
  ]);
  // 히스토리 참조 ⊆ EntryFactorRefOut · R4 사유 501 → 422 reason · 복구(사유) = 그 줄 after · R3 before = 지금(직접입력)
  const history = await call(
    'GET',
    `${X(year)}/rows/1/history?page=1&pageSize=20`,
  );
  const toPool = history.json.results.find(
    (l: { kind: string; afterFactor: { versionId: string | null } | null }) =>
      l.kind === 'factor' && l.afterFactor?.versionId === '2301',
  );
  within('EntryHistoryOut', toPool);
  within('EntryFactorRefOut', toPool.beforeFactor);
  within('EntryFactorRefOut', toPool.afterFactor);
  const tooLong = await call(
    'POST',
    `${X(year)}/rows/1/history/${toPool.historyId}/restore`,
    { reason: '가'.repeat(501) },
  );
  expect([tooLong.status, keys(tooLong.json.error.fields)]).toEqual([
    422,
    ['reason'],
  ]);
  const restored = await call(
    'POST',
    `${X(year)}/rows/1/history/${toPool.historyId}/restore`,
    { reason: '지어낸 복구 사유' },
  );
  expect(restored.status).toBe(200);
  expect(rowOf(restored.json).factor!.factorId).toBe('23');
  const after = await call(
    'GET',
    `${X(year)}/rows/1/history?page=1&pageSize=20`,
  );
  expect([
    after.json.results[0].reason,
    after.json.results[0].beforeFactor.isCustom,
    after.json.results[0].afterFactor.versionId,
  ]).toEqual(['지어낸 복구 사유', true, '2301']);
  // R1: 제1공장 분기(seedEntry — 그 해·잎 20)는 지난 해·다른 잎의 블록 주기를 안 바꿈
  const lastYear = await call(
    'GET',
    `/inventory/scope12/years/${year - 1}/indexes/20`,
  );
  expect(
    lastYear.json.sites.find((s: { siteId: string }) => s.siteId === '2')
      .period,
  ).toBe('month');
  const otherLeaf = await call(
    'GET',
    `/inventory/scope12/years/${year}/indexes/22`,
  );
  const leaf22Plant = otherLeaf.json.sites.find(
    (s: { siteId: string }) => s.siteId === '2',
  );
  expect(leaf22Plant.period).toBe('month'); // 잎 20 의 분기가 잎 22 로 새지 않음
  const leaf20 = await call(
    'GET',
    `/inventory/scope12/years/${year}/indexes/20`,
  );
  expect(
    leaf20.json.sites.find((s: { siteId: string }) => s.siteId === '2').period,
  ).toBe('quarter');
  expect(keys(schemas.EntryRowFactorIn!.properties)).toEqual([
    'custom',
    'factorId',
    'reason',
  ]);
  expect(unrouted).toEqual([]);
});

test('W12-3 ② 고객사 PUT factor 403(흉내 차례: 모르는 칸 422 가 먼저)', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'service', { admin: false });
  const year = seedEntry(api);
  await page.goto(`/ghg/inventory?year=${year}`);
  await expect(page.getByTestId('inventory-row-20')).toBeVisible();
  const put = (body: unknown) =>
    page.evaluate(
      async ([p, b]) => {
        const res = await fetch(`/api${p}`, {
          method: 'PUT',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(b),
        });
        return res.status;
      },
      [`${X(year)}/rows/1/factor`, body] as const,
    );
  expect(await put({ factorId: 23, reason: '지어낸', x: 1 })).toBe(422);
  expect(await put({ factorId: 23, reason: '지어낸' })).toBe(403);
  expect(unrouted).toEqual([]);
});

// ── 밴드 W12-2 ②: S7 입력주기 · S12 [복구] · 총합 · 히스토리 머리 가운데(발주서 §3 #1·#2·#4·#5) ──
const periodWords = entryWords.periodChange;
const restoreWords = entryWords.history;

/** 블록 머리 [입력 주기 변경] → 창(안내 글) → 고르기 → [선택 완료] → 블록 성공 줄. */
async function pickPeriod(page: Page, site: string, label: string) {
  await page.getByTestId(`entry-period-open-${site}`).click();
  const sheet = page.getByTestId('entry-period');
  await expect(sheet).toContainText(periodWords.notice);
  await sheet.getByTestId('entry-period-select').click();
  await page.getByRole('menuitemradio', { name: label }).click();
  await sheet.getByTestId('entry-period-submit').click();
  await expect(sheet).toHaveCount(0);
  await expect(page.getByTestId(`entry-done-${site}`)).toHaveText(
    periodWords.saved,
  );
}

/** 히스토리 창의 n 째 줄 [복구] → 확인 창 → [복구]. */
async function restoreLine(page: Page, line: ReturnType<Page['locator']>) {
  await line.getByRole('button', { name: restoreWords.restore }).click();
  const confirm = page.getByTestId('entry-restore-confirm');
  await confirm.getByRole('button', { name: restoreWords.restoreOk }).click();
  await expect(confirm).toHaveCount(0);
}

test('W12-2 ② S7 고객사 1280: 월 → 분기 칸 넷(옛 값 숨김) → 월 → 분기 · 히스토리 after=월 period 줄 [복구] → 칸 12 · 옛 값 다시 보임', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const dialog = await openEntry(page, year);
  const heads = dialog.getByTestId('entry-site-1').locator('th[data-slot]');
  await expect(heads).toHaveCount(12);
  await addRow(page, '1', '1호기');
  await dialog.getByTestId(`entry-amount-n1:${year}-01`).fill('7');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();

  const PERIOD = `PUT ${X(year)}/sites/1/period`;
  await pickPeriod(page, '1', '분기');
  await expect(heads).toHaveText(['1분기', '2분기', '3분기', '4분기']);
  await expect(dialog.getByTestId(`entry-amount-r1:${year}-01`)).toHaveCount(0);
  expect(api.bodies(PERIOD)).toEqual([{ period: 'quarter' }]);
  // 다른 블록(제1공장 분기)은 그대로.
  await expect(
    dialog.getByTestId('entry-site-2').locator('th[data-slot]'),
  ).toHaveCount(4);

  // 맨 위 period 줄은 복구가 꺼지므로 월 → 분기 → 월 → 분기 로 after=월 줄을 맨 위에서 내린다(C0 감독 수용).
  await pickPeriod(page, '1', '월');
  await expect(heads).toHaveCount(12);
  await pickPeriod(page, '1', '분기');
  await expect(heads).toHaveCount(4);
  expect(api.bodies(PERIOD)).toEqual([
    { period: 'quarter' },
    { period: 'month' },
    { period: 'quarter' },
  ]);

  await dialog.getByTestId('entry-history-r1').click();
  const sheet = page.getByTestId('entry-history');
  const lines = sheet.locator('tbody tr[data-testid^="entry-history-"]');
  // 줄 넷 = period 셋(새 것 먼저) + value 하나.
  await expect(lines).toHaveCount(4);
  await expect(
    lines.nth(0).getByRole('button', { name: restoreWords.restore }),
  ).toBeDisabled();
  await expect(
    lines.nth(3).getByRole('button', { name: restoreWords.restore }),
  ).toBeDisabled();
  const periodId = (await lines.nth(1).getAttribute('data-testid'))!.replace(
    'entry-history-',
    '',
  );
  await restoreLine(page, lines.nth(1));
  await expect(sheet.getByTestId('entry-history-note')).toHaveText(
    restoreWords.restored,
  );
  expect(
    api.bodies(`POST ${X(year)}/rows/1/history/${periodId}/restore`),
  ).toEqual([{}]);
  await sheet.getByRole('button', { name: entryWords.close }).click();
  await expect(sheet).toHaveCount(0);
  await expect(heads).toHaveCount(12);
  await expect(dialog.getByTestId(`entry-amount-r1:${year}-01`)).toHaveValue(
    '7',
  );
  expect(api.bodies(PERIOD)).toHaveLength(3);
  expect(unrouted).toEqual([]);
});

test('W12-2 ② S12 고객사 1280: value 줄 [복구] → 칸 값 바뀜 · 맨 위 줄 꺼짐 · 계수 줄 꺼짐 · 총합 줄 고른 해 ≠ 「-」 · 히스토리 머리 가운데', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const dialog = await openEntry(page, year);
  await addRow(page, '1', '1호기');
  await dialog.getByTestId(`entry-amount-n1:${year}-01`).fill('7');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();

  // §3 #4: 총합 줄 수 ≥ 1 → 전체 줄 고른 해 칸 ≠ 「-」(열: 이름 · 해들 · 단위 — 고른 해는 마지막 해).
  const totals = dialog.getByTestId('entry-totals');
  expect(await totals.locator('tbody tr').count()).toBeGreaterThanOrEqual(1);
  const allCells = dialog.getByTestId('entry-total-all').locator('td');
  const yearCell = allCells.nth((await allCells.count()) - 2);
  await expect(yearCell).not.toHaveText('-');
  await expect(yearCell).not.toHaveText('');

  // 계수 줄을 사이에 심고(고객사 화면엔 계수 바꿀 길 없음) 값 하나 더 저장 → 줄 셋.
  api.entryNote(year, 20, 1, { kind: 'factor', unit: 'kL' });
  await dialog.getByTestId(`entry-amount-r1:${year}-01`).fill('9');
  await saveAll(dialog);
  await expect
    .poll(() => api.bodies(`PUT ${X(year)}/sites/1/rows`).length)
    .toBe(2);

  await dialog.getByTestId('entry-history-r1').click();
  const sheet = page.getByTestId('entry-history');
  const lines = sheet.locator('tbody tr[data-testid^="entry-history-"]');
  await expect(lines).toHaveCount(3);
  const buttons = sheet.getByRole('button', { name: restoreWords.restore });
  await expect(buttons).toHaveCount(3);
  await expect(buttons.nth(0)).toBeDisabled(); // 맨 위(9)
  await expect(buttons.nth(1)).toBeDisabled(); // 계수 줄
  await expect(buttons.nth(2)).toBeEnabled(); // 7 로 되돌림

  // §3 #5: 히스토리 머리 다섯 다 가운데.
  const headCells = sheet.locator('thead th');
  await expect(headCells).toHaveCount(5);
  for (let i = 0; i < 5; i += 1)
    await expect(headCells.nth(i)).toHaveCSS('text-align', 'center');

  const valueId = (await lines.nth(2).getAttribute('data-testid'))!.replace(
    'entry-history-',
    '',
  );
  await restoreLine(page, lines.nth(2));
  await expect(sheet.getByTestId('entry-history-note')).toHaveText(
    restoreWords.restored,
  );
  expect(
    api.bodies(`POST ${X(year)}/rows/1/history/${valueId}/restore`),
  ).toEqual([{}]);
  await expect(lines).toHaveCount(4);
  await sheet.getByRole('button', { name: entryWords.close }).click();
  await expect(sheet).toHaveCount(0);
  await expect(dialog.getByTestId(`entry-amount-r1:${year}-01`)).toHaveValue(
    '7',
  );
  expect(unrouted).toEqual([]);
});

// ── 밴드 W12-3 ③: S8 [배출계수 수정] → S9 → S11 · 548 칸 글 · 계수 줄 복구(발주서 §3 #2·#5·#6) ──
const editWords = entryWords.factorEdit;
const reasonWords = entryWords.reason;

/** 저장된 행 r1 의 S8 → [배출계수 수정] → S9(표가 뜰 때까지). */
async function openFactorEdit(page: Page) {
  await page.getByTestId('entry-factor-r1').click();
  const s8 = page.getByTestId('entry-factor');
  await s8.getByTestId('entry-factor-edit-open').click();
  const s9 = page.getByTestId('entry-factor-edit');
  await expect(s9.getByTestId('entry-factor-pick')).toBeVisible();
  return s9;
}

/** S11 사유 → [확인]. */
async function writeReason(page: Page, text: string, testId = 'entry-reason') {
  const dialog = page.getByTestId(testId);
  await dialog.getByTestId('entry-reason-input').fill(text);
  await dialog.getByRole('button', { name: reasonWords.confirm }).click();
  return dialog;
}

/** 직접 입력 칸 채움(지어낸 값 — 순발열량 끔 · CO2 하나). */
async function fillCustom(page: Page, kind: string, unit: string) {
  const s9 = page.getByTestId('entry-factor-edit');
  await s9.locator('#entry-custom-name').fill('지어낸 직접 계수');
  await s9.locator('#entry-custom-source').fill('지어낸 직접 출처');
  await s9.locator('#entry-custom-baseYear').selectOption('2024');
  await s9.locator('#entry-custom-tier').selectOption('2');
  await s9.locator('#entry-custom-countryCode').selectOption('KR');
  await s9.locator('#entry-custom-industryCode').selectOption('other');
  await s9.locator('#entry-custom-inputUnit').selectOption(kind);
  await s9.locator('#entry-custom-inputUnit-unit').selectOption(unit);
  await s9
    .getByRole('switch', { name: factorText.gasToggle('CO2') })
    .first()
    .click();
  await s9.locator('#entry-custom-gases-CO2-factor').fill('1.25');
  await s9.locator('#entry-custom-gases-CO2-gwp').fill('1');
}

/** 본사 블록에 행 하나를 저장(r1) — 계수 바꿈의 대상. */
async function savedRow(page: Page, year: number) {
  const dialog = await openEntry(page, year);
  await addRow(page, '1', '1호기');
  await dialog.getByTestId(`entry-amount-n1:${year}-01`).fill('7');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  return dialog;
}

test('W12-3 ③ 운영 관리자 1280: S8 [배출계수 수정] → S9 등유 계수 → 사유 → PUT {factorId, reason} · 배출량 칸 바뀜 · 블록 알림 · 히스토리 factor 줄 사유 글 · 창 폭 960·640', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const { unrouted, api } = await open(page, 'admin');
  const year = seedEntry(api);
  const dialog = await savedRow(page, year);
  const emission = dialog.getByTestId('entry-emission-r1');
  const before = await emission.textContent();
  const s9 = await openFactorEdit(page);
  // 열림 움직임(zoom-in-95) 중 상자는 0.95 배라 계산된 폭으로 잰다.
  await expect(s9).toHaveCSS('width', '960px');
  await expect(
    s9.getByRole('heading', { name: editWords.title }),
  ).toBeVisible();
  // 분모: 줄 = 풀 계수 둘 + 「직접 입력」.
  await expect(s9.locator('tbody tr')).toHaveCount(3);
  await expect(s9.getByTestId('entry-factor-next')).toBeDisabled();
  await s9
    .getByRole('checkbox', { name: editWords.pick('지어낸 등유 계수') })
    .click();
  await s9.getByTestId('entry-factor-next').click();
  const reason = page.getByTestId('entry-reason');
  await expect(reason).toBeVisible();
  // 열림 움직임(zoom-in-95) 중 상자는 0.95 배라 계산된 폭으로 잰다.
  await expect(reason).toHaveCSS('width', '640px');
  await writeReason(page, '지어낸 바꿈 사유');
  await expect(s9).toHaveCount(0);
  await expect(page.getByTestId('entry-factor')).toHaveCount(0);
  const FACTOR = `PUT ${X(year)}/rows/1/factor`;
  expect(api.bodies(FACTOR)).toEqual([
    { factorId: 23, reason: '지어낸 바꿈 사유' },
  ]);
  await expect(emission).not.toHaveText(before ?? '');
  await expect(emission).toContainText('2.23');
  await expect(page.getByTestId('entry-done-1')).toHaveText(editWords.done);
  await dialog.getByTestId('entry-history-r1').click();
  const sheet = page.getByTestId('entry-history');
  // W12-4 ③ 571 갈음: 줄 안 사유 글 0 → 「수정 사유」 단추 하나 → 보기 창 본문 = 그 사유(창 꼴은 아래 W12-4 ③ test).
  await expect(
    sheet.getByRole('button', { name: restoreWords.reasonOpen }),
  ).toHaveCount(1);
  await expect(sheet).not.toContainText(
    restoreWords.reason('지어낸 바꿈 사유'),
  );
  await sheet.getByRole('button', { name: restoreWords.reasonOpen }).click();
  await expect(page.getByTestId('entry-reason-view-body')).toHaveText(
    '지어낸 바꿈 사유',
  );
  expect(unrouted).toEqual([]);
});

test('W12-4 ③ 571 운영 관리자 1280: 사유 남김 → 히스토리 「수정 사유」 단추(사유 있는 줄만) → 「수정 사유」 창 폭 640 · 본문 = 사유 전체 · 초점 [확인] → Enter 로 닫힘 → 초점 = 단추', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const { unrouted, api } = await open(page, 'admin');
  const year = seedEntry(api);
  const dialog = await savedRow(page, year);
  const s9 = await openFactorEdit(page);
  await s9
    .getByRole('checkbox', { name: editWords.pick('지어낸 등유 계수') })
    .click();
  await s9.getByTestId('entry-factor-next').click();
  const text = `지어낸 보기 사유 ${'가나다라마바사아자차'.repeat(30)}`;
  await writeReason(page, text);
  await expect(page.getByTestId('entry-factor-edit')).toHaveCount(0);
  await dialog.getByTestId('entry-history-r1').click();
  const sheet = page.getByTestId('entry-history');
  // 분모: 줄 둘(value 저장 · factor 바꿈) 중 사유 있는 factor 줄만 단추.
  await expect(sheet.locator('tbody tr')).toHaveCount(2);
  const opener = sheet.getByRole('button', { name: restoreWords.reasonOpen });
  await expect(opener).toHaveCount(1);
  await opener.click();
  const view = page.getByTestId('entry-reason-view');
  await expect(view.getByRole('heading')).toHaveText(
    restoreWords.reasonView.title,
  );
  // 열림 움직임(zoom-in-95) 중 상자는 0.95 배라 계산된 폭으로 잰다.
  await expect(view).toHaveCSS('width', '640px');
  const body = view.getByTestId('entry-reason-view-body');
  await expect(body).toHaveText(text);
  // 말줄임 0: 가로 넘침 없이 여러 줄로 감김(글자 그대로만으로는 CSS 말줄임을 못 가른다).
  const box = await body.evaluate((el) => ({
    scroll: el.scrollWidth,
    client: el.clientWidth,
    height: el.getBoundingClientRect().height,
    line: parseFloat(getComputedStyle(el).lineHeight),
  }));
  expect(box.scroll).toBeLessThanOrEqual(box.client);
  expect(box.height).toBeGreaterThan(box.line * 1.5);
  const ok = view.getByRole('button', { name: restoreWords.reasonView.ok });
  await expect(ok).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(view).toHaveCount(0);
  await expect(opener).toBeFocused();
  await expect(sheet).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('W12-3 ③ 548 직접 입력 1280: GWh(잎 단위로 못 바꿈) → 422 custom.inputUnit · 사유 창 닫힘 · 투입 단위 칸 아래 글 → kL 로 고쳐 → 200 · 배출량 3.<id>', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const { unrouted, api } = await open(page, 'admin');
  const year = seedEntry(api);
  const dialog = await savedRow(page, year);
  const s9 = await openFactorEdit(page);
  await s9
    .getByRole('checkbox', { name: editWords.pick(editWords.custom) })
    .click();
  await s9.getByTestId('entry-factor-next').click();
  await expect(s9.getByTestId('entry-custom-form')).toBeVisible();
  await fillCustom(page, 'electricity', 'GWh');
  await s9.getByTestId('entry-factor-next').click();
  await writeReason(page, '지어낸 단위 사유');
  await expect(page.getByTestId('entry-reason')).toHaveCount(0);
  await expect(s9.getByTestId('entry-custom-inputUnit-error')).toHaveText(
    editWords.unitProblem['custom.inputUnit']!,
  );
  const FACTOR = `PUT ${X(year)}/rows/1/factor`;
  expect(api.bodies(FACTOR)).toHaveLength(1);
  await s9.locator('#entry-custom-inputUnit').selectOption('volume');
  await s9.locator('#entry-custom-inputUnit-unit').selectOption('kL');
  await s9.getByTestId('entry-factor-next').click();
  await writeReason(page, '지어낸 단위 사유');
  await expect(s9).toHaveCount(0);
  expect(api.bodies(FACTOR)).toHaveLength(2);
  // W12-2 검증 W7: 직접입력 행 배출량은 3.<customId>(가짜 셈 흉내).
  await expect(dialog.getByTestId('entry-emission-r1')).toHaveText(/^3\.\d+/);
  expect(unrouted).toEqual([]);
});

test('S12-03a 직접 입력 저장 뒤 1440: S9 만 닫히고 S8 저장 뒤 창(「*직접입력」 · 제목 줄 [수정] · ✕ 와 안 겹침 · 가스 표 셋) → [수정] → 직접 입력 단계 · 저장 값으로 채움 · 안 바꾸고 ✕ 는 확인 없이 닫힘', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { unrouted, api } = await open(page, 'admin');
  const year = seedEntry(api);
  await savedRow(page, year);
  const s9 = await openFactorEdit(page);
  await s9
    .getByRole('checkbox', { name: editWords.pick(editWords.custom) })
    .click();
  await s9.getByTestId('entry-factor-next').click();
  await fillCustom(page, 'volume', 'kL');
  await s9.getByTestId('entry-factor-next').click();
  await writeReason(page, '지어낸 직접 사유');
  await expect(s9).toHaveCount(0);
  const FACTOR = `PUT ${X(year)}/rows/1/factor`;
  expect(api.bodies(FACTOR)).toHaveLength(1);
  const s8 = page.getByTestId('entry-factor');
  await expect(s8).toBeVisible();
  await expect(s8.getByTestId('entry-factor-custom-mark')).toHaveText(
    entryWords.factor.customMark,
  );
  await expect(
    s8.getByTestId('entry-factor-fields').locator('td').first(),
  ).toHaveText('지어낸 직접 계수');
  await expect(s8.locator('table:not([data-testid]) thead th')).toHaveCount(3);
  await expect(s8.getByTestId('entry-gas-CO2').locator('td')).toHaveText([
    'CO2',
    '1.25',
    '1',
  ]);
  const edit03a = s8.getByTestId('entry-factor-edit-open');
  await expect(edit03a).toHaveText(editWords.cell);
  const box = (await s8.boundingBox())!;
  const title = (await s8.getByRole('heading', { level: 2 }).boundingBox())!;
  const button = (await edit03a.boundingBox())!;
  const close = (await s8
    .getByRole('button', { name: entryWords.close })
    .boundingBox())!;
  // 폭 1320 · 제목과 한 줄(세로 가운데 ±4) · 오른쪽 · ✕ 와 안 겹침 · 폭 80 이상.
  expect(Math.round(box.width)).toBe(1320);
  expect(
    Math.abs(button.y + button.height / 2 - (title.y + title.height / 2)),
  ).toBeLessThanOrEqual(4);
  expect(button.x).toBeGreaterThan(box.x + box.width / 2);
  expect(button.width).toBeGreaterThanOrEqual(80);
  const overlaps =
    button.x < close.x + close.width &&
    close.x < button.x + button.width &&
    button.y < close.y + close.height &&
    close.y < button.y + button.height;
  expect(overlaps).toBe(false);
  await edit03a.click();
  const again = page.getByTestId('entry-factor-edit');
  await expect(again).toHaveAttribute('data-step', 'custom');
  await expect(again.getByTestId('entry-custom-form')).toBeVisible();
  await expect(again.locator('#entry-custom-name')).toHaveValue(
    '지어낸 직접 계수',
  );
  await expect(again.locator('#entry-custom-baseYear')).toHaveValue('2024');
  await expect(again.locator('#entry-custom-inputUnit-unit')).toHaveValue('kL');
  await expect(again.locator('#entry-custom-gases-CO2-factor')).toHaveValue(
    '1.25',
  );
  await again.getByRole('button', { name: entryWords.close }).click();
  await expect(again).toHaveCount(0);
  await expect(page.getByTestId('entry-factor-edit-leave')).toHaveCount(0);
  await expect(s8).toBeVisible();
  expect(api.bodies(FACTOR)).toHaveLength(1);
  expect(unrouted).toEqual([]);
});

test('W12-3 ③ 계수 줄 복구 1280: 운영 관리자 둘째 factor 줄 [복구] → 사유 창 → {reason} → 배출량 등유로(고객사 꺼짐은 W12-2 S12 시험)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const first = await open(page, 'admin');
  const year = seedEntry(first.api);
  const dialog = await savedRow(page, year);
  for (const pickName of ['지어낸 등유 계수', '지어낸 경유 계수']) {
    const s9 = await openFactorEdit(page);
    await s9.getByRole('checkbox', { name: editWords.pick(pickName) }).click();
    await s9.getByTestId('entry-factor-next').click();
    await writeReason(page, `지어낸 사유 ${pickName}`);
    await expect(s9).toHaveCount(0);
  }
  await dialog.getByTestId('entry-history-r1').click();
  const sheet = page.getByTestId('entry-history');
  const factorLines = sheet
    .locator('tbody tr[data-testid^="entry-history-"]')
    .filter({ hasText: '배출계수를 변경했어요' });
  // 분모: factor 줄 둘(새 것 먼저) — 맨 위는 꺼짐, 둘째는 켬.
  await expect(factorLines).toHaveCount(2);
  await expect(
    factorLines.nth(0).getByRole('button', { name: restoreWords.restore }),
  ).toBeDisabled();
  const older = (await factorLines.nth(1).getAttribute('data-testid'))!.replace(
    'entry-history-',
    '',
  );
  await factorLines
    .nth(1)
    .getByRole('button', { name: restoreWords.restore })
    .click();
  await expect(page.getByTestId('entry-restore-confirm')).toHaveCount(0);
  await writeReason(page, '지어낸 복구 사유', 'entry-restore-reason');
  await expect(sheet.getByTestId('entry-history-note')).toHaveText(
    restoreWords.restored,
  );
  expect(
    first.api.bodies(`POST ${X(year)}/rows/1/history/${older}/restore`),
  ).toEqual([{ reason: '지어낸 복구 사유' }]);
  await sheet.getByRole('button', { name: entryWords.close }).click();
  await expect(dialog.getByTestId('entry-emission-r1')).toContainText('2.23');
  expect(first.unrouted).toEqual([]);
});

test('W12-3 ③ 고객사 1280: 저장된 행 S8 에 [배출계수 수정] 0(pool null)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const { unrouted, api } = await open(page, 'service');
  const year = seedEntry(api);
  const dialog = await savedRow(page, year);
  // 분모: 행 계수 단추는 보임.
  await dialog.getByTestId('entry-factor-r1').click();
  const s8 = page.getByTestId('entry-factor');
  await expect(s8).toBeVisible();
  await expect(s8.getByTestId('entry-factor-edit-open')).toHaveCount(0);
  await expect(s8).not.toContainText(editWords.button);
  expect(unrouted).toEqual([]);
});

// ── 밴드 W12-5: S5 다운로드 · 양식 받기 · S4 올리기 · 흉내 ↔ openapi. 값은 지어낸 것이다. ──
const XLSX_BYTES = Buffer.from([0x50, 0x4b, 0x03, 0x04, 0x09]);
const bulk = inventory.bulk;
const pickXlsx = (dialog: Locator) =>
  dialog.locator('input[type="file"]').setInputFiles({
    name: '지어낸.xlsx',
    mimeType:
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: XLSX_BYTES,
  });

// 밴드 DB2: DB2_SHOTS 를 주면 사진(대시보드 셋 · 받기·올리기 창 — 원시는 워크트리 밖 DB2.out/shots).
const DB2_SHOTS = process.env.DB2_SHOTS;

/** 움직임이 다 끝날 때까지 기다린다(밴드 DB3 — 그 뒤에 그려진 자리를 잰다. 움직이는 도중의 rect 로 재지 않는다). */
const motionDone = (page: Page) =>
  page.evaluate(() =>
    Promise.all(
      document.getAnimations().map((motion) => motion.finished.catch(() => {})),
    ),
  );

/**
 * 고른 해 말풍선(밴드 DB4 — 사용자 11-08 「호버 하면 나오면」, DB3 넘김 R1-2 의 「들면 늘」을 갈음): 처음엔 0 ·
 * 그 막대에 올리면 뜸(자리: 막대 왼쪽 — 오른쪽 끝 ≤ 막대 왼쪽 − 4) · 떠나면 0 · 초점에 뜸 · 초점을 놓으면 0.
 */
async function chosenTip(page: Page, scope: number, year: number) {
  const tip = page.getByTestId(`dashboard-scope-${scope}-trend-tip-${year}`);
  const column = page.getByTestId(`dashboard-scope-${scope}-trend-bar-${year}`);
  await expect(tip).toHaveCount(0);
  await column.hover();
  await expect(tip).toBeVisible();
  const box = (await tip.boundingBox())!;
  const bar = (await column.locator('[data-bar]').boundingBox())!;
  expect(box.x + box.width).toBeLessThanOrEqual(bar.x - 4 + 0.5);
  await page.mouse.move(0, 0);
  await expect(tip).toHaveCount(0);
  await column.focus();
  await expect(tip).toBeVisible();
  await column.blur();
  await expect(tip).toHaveCount(0);
}

test('W12-5 ② S5 줄을 눌러 내려받고 · 양식 받기 ①② 로 내려받는다', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  await page.goto(`/ghg/inventory?year=${year}`);
  await expect(page.getByTestId('inventory-row-20')).toBeVisible();

  await page.getByRole('button', { name: bulk.downloadOpen }).click();
  const box = page.getByTestId('entry-download');
  await expect(box).not.toContainText('보고서');
  // 밴드 DB2 ③: 받기 줄 아이콘 사진(DB2_SHOTS 를 줄 때만).
  if (DB2_SHOTS) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.evaluate(() =>
      Promise.all(document.getAnimations().map((motion) => motion.finished)),
    );
    await page.screenshot({ path: `${DB2_SHOTS}/entry-download-1440.png` });
  }
  const saved = page.waitForEvent('download');
  await box.getByTestId('entry-download-2').click();
  expect((await saved).suggestedFilename()).toBe('지어낸 데이터.xlsx');
  const asked = api.calls.filter((call) => call.path.endsWith('/export'));
  expect(asked.map((call) => call.query)).toEqual(['?scope=2']);
  await box.getByRole('button', { name: bulk.download.ok }).click();
  await expect(box).toHaveCount(0);

  await page.getByRole('button', { name: bulk.uploadOpen }).click();
  await page.getByTestId('entry-template-open').click();
  const form = page.getByTestId('entry-template');
  const next = form.getByTestId('entry-template-next');
  await expect(next).toBeDisabled();
  await form.getByTestId('entry-template-scope').selectOption('1');
  await next.click();
  const site = form.getByTestId('entry-template-site');
  await expect(site).toBeEnabled();
  await site.selectOption('2');
  const template = page.waitForEvent('download');
  await next.click();
  expect((await template).suggestedFilename()).toBe('지어낸 양식.xlsx');
  await expect(form).toHaveCount(0);
  await expect(page.getByTestId('entry-template-open')).toBeFocused();
  const sent = api.calls.filter((call) => call.path.endsWith('/template'));
  expect(sent.map((call) => call.query)).toEqual(['?scope=1&siteId=2']);
  expect(unrouted).toEqual([]);
});

test('W12-5 ③ S4: 칸 오류 목록 → 표를 바꾼 뒤 끊김은 결과를 모른다고 말함 → 올려서 표 값·알림 줄', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  await page.goto(`/ghg/inventory?year=${year}`);
  await expect(page.getByTestId('inventory-row-20')).toBeVisible();
  await page.getByRole('button', { name: bulk.uploadOpen }).click();
  const dialog = page.getByTestId('entry-upload');
  const submit = dialog.getByTestId('entry-upload-submit');
  await expect(submit).toBeDisabled();
  // 밴드 DB2 ③: 양식 상자 아이콘 사진(DB2_SHOTS 를 줄 때만).
  if (DB2_SHOTS) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.evaluate(() =>
      Promise.all(document.getAnimations().map((motion) => motion.finished)),
    );
    await page.screenshot({ path: `${DB2_SHOTS}/entry-upload-1440.png` });
  }
  await pickXlsx(dialog);

  api.uploadAnswers.push(
    {
      status: 422,
      code: 'INVALID_UPLOAD',
      fields: { '월!C3': ['지어낸 칸 글'], more: ['그 밖에 1개가 더 있어요'] },
    },
    {
      abort: true,
      apply: () => api.entryValues.set(20, { [`${year}`]: '77.5' }),
    },
    { status: 200, body: { added: 0, filled: 2, unchanged: 1, unresolved: 3 } },
  );
  await submit.click();
  const lines = dialog.getByTestId('entry-upload-lines');
  await expect(lines).toContainText('월 시트 C3 지어낸 칸 글');
  await expect(lines.getByRole('listitem').last()).toHaveText(
    '그 밖에 1개가 더 있어요',
  );

  await submit.click();
  await expect(dialog.getByTestId('entry-upload-problem')).toHaveText(
    bulk.upload.unknownRead,
  );
  await expect(dialog).toBeVisible();
  await expect(page.getByTestId('inventory-row-20')).toContainText('77.5');

  await submit.click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId('inventory-uploaded')).toHaveText(
    `${bulk.filled(2)} ${bulk.unresolved(3)}`,
  );
  const sent = api.calls.filter((call) => call.path.endsWith('/uploads'));
  expect(sent.map((call) => call.size)).toEqual([5, 5, 5]);
  expect(sent.map((call) => call.query)).toEqual(['', '', '']);
  expect(unrouted).toEqual([]);
});

test('W12-5 ① 흉내 ↔ openapi: 올리기 200·오류 열쇠 · Content-Type · 쿼리 · 미디어 · 상태 번호', async ({
  page,
}) => {
  const { readFileSync } = await import('node:fs');
  interface Operation {
    parameters?: { name: string }[];
    requestBody?: { content: Record<string, unknown> };
    responses: Record<string, { content?: Record<string, unknown> }>;
  }
  const openapi = JSON.parse(
    readFileSync(
      new URL('../../api-py/generated/openapi.json', import.meta.url),
      'utf8',
    ),
  ) as {
    paths: Record<string, Record<string, Operation>>;
    components: { schemas: Record<string, { required?: string[] }> };
  };
  const route = (name: string) =>
    openapi.paths[`/inventory/scope12/years/{year}/${name}`]!;
  const upload = route('uploads').post!;
  const template = route('template').get!;
  const exported = route('export').get!;
  const schemas = openapi.components.schemas;
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  await page.goto(`/ghg/inventory?year=${year}`);
  await expect(page.getByTestId('inventory-row-20')).toBeVisible();
  const media = Object.keys(upload.requestBody!.content)[0]!;
  const post = (size: number) =>
    page.evaluate(
      async ([path, type, length]) => {
        const res = await fetch(path as string, {
          method: 'POST',
          headers: { 'content-type': type as string },
          body: new Uint8Array(length as number),
        });
        return { status: res.status, json: await res.json() };
      },
      [`/api/inventory/scope12/years/${year}/uploads`, media, size] as const,
    );
  const get = (path: string) =>
    page.evaluate(async (url) => {
      const res = await fetch(url);
      return { status: res.status, type: res.headers.get('content-type') };
    }, `/api/inventory/scope12/years/${year}/${path}`);
  const sorted = (keys: readonly string[]) => [...keys].sort();

  // ⓐ 200 열쇠 = required
  const fine = await post(1);
  expect(fine.status).toBe(200);
  expect(sorted(Object.keys(fine.json))).toEqual(
    sorted(schemas.EntryUploadOut!.required!),
  );
  // ⓑ Content-Type · ⓒ 쿼리
  const sent = api.calls.filter((call) => call.path.endsWith('/uploads'));
  expect(Object.keys(upload.requestBody!.content)).toContain(
    sent[0]!.contentType,
  );
  expect(sent[0]!.query).toBe('');
  const names = (operation: Operation) =>
    (operation.parameters ?? []).map((parameter) => parameter.name);
  for (const name of ['scope', 'siteId'])
    expect(names(template)).toContain(name);
  expect(names(exported)).toContain('scope');
  expect(names(exported)).not.toContain('basis');
  // ⓓ 미디어
  for (const [path, operation] of [
    ['template?scope=1&siteId=2', template],
    ['export?scope=all', exported],
  ] as const) {
    const out = await get(path);
    expect(out.status).toBe(200);
    expect(Object.keys(operation.responses['200']!.content!)).toEqual([
      out.type,
    ]);
  }
  // ⓔ 오류 열쇠 · ⓕ 상태 번호
  api.uploadAnswers.push(
    { status: 422, code: 'INVALID_UPLOAD', fields: { file: ['지어낸'] } },
    { status: 409, code: 'LOCKED' },
  );
  // 413 은 서버 올리기 경로 상한(20MB — MARC-ENT-593) + 1 바이트
  const answers = [
    await post(1),
    await post(1),
    await post(20 * 1024 * 1024 + 1),
  ];
  expect(answers.map((answer) => answer.status)).toEqual([422, 409, 413]);
  for (const answer of answers)
    expect(sorted(Object.keys(answer.json.error))).toEqual(
      sorted(schemas.ErrorDetail!.required!),
    );
  for (const status of ['200', '400', '404', '409', '413', '422'])
    expect(Object.keys(upload.responses)).toContain(status);
  // 상한 그대로(20MB)는 받는다 — 전역 2.5MB 가 아니다
  expect((await post(20 * 1024 * 1024)).status).toBe(200);
  expect(unrouted).toEqual([]);
});

// 밴드 DB1 ②③: 대시보드 한 길 — /ghg → /ghg/dashboard?year=(전년도) · 탭 줄 맨 앞 「대시보드」 고른 탭 · 심은 판(openapi 꼴)의 값 ·
//   Scope 3 빠짐 n 두 자리 · 연도 바꿈 → 미설정 덮개 · 「온실가스 데이터」 탭 → /ghg/inventory. DB1_SHOTS 를 주면 1280·1440 사진.
const DB1_SHOTS = process.env.DB1_SHOTS;
const dash = GHG_TEXT.dashboard;

test('대시보드: /ghg 첫 화면 · 탭 맨 앞 고름 · 값 · Scope 3 빠짐 · 미설정 덮개', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = new Date().getFullYear() - 1;
  api.dashboards.set(year, {
    year,
    configured: true,
    decimals: 2,
    basis: 'location',
    unit: 'tCO2-eq',
    complete: true,
    scopes: [
      {
        scopeId: '1',
        scopeName: '지어낸 범위 가',
        scopeOrder: 1,
        value: '1250.5',
        topSources: [
          {
            nodeId: '11',
            name: '지어낸 고정연소 보일러 및 가열로 설비',
            value: '1000.5',
            share: '80.0',
          },
          {
            nodeId: '12',
            name: '지어낸 이동연소',
            value: '250',
            share: '20.0',
          },
        ],
      },
      {
        scopeId: '2',
        scopeName: '지어낸 범위 나',
        scopeOrder: 2,
        value: '749.5',
        topSources: [
          {
            nodeId: '21',
            name: '지어낸 전기 사용',
            value: '749.5',
            share: '100.0',
          },
        ],
      },
    ],
    total: {
      scope12: '2000',
      scope2Market: null,
      scope3: '500',
      sum: '2500',
      scope3FailedSheets: 2,
    },
    bySite: [
      {
        siteId: '1',
        siteName: '본사',
        scopes: [
          { scopeId: '1', value: '250.5' },
          { scopeId: '2', value: '249.5' },
        ],
        scope3: null,
      },
      {
        siteId: '2',
        siteName: '제1공장',
        scopes: [
          { scopeId: '1', value: '1000' },
          { scopeId: '2', value: '500' },
        ],
        scope3: null,
      },
    ],
    scope3Categories: [
      {
        category: 'C1',
        name: '구매 상품 및 서비스',
        value: '300',
        share: '60.0',
      },
      {
        category: 'C4',
        name: '업스트림 운송 및 유통',
        value: '200',
        share: '40.0',
      },
    ],
  });
  await page.goto('/ghg');
  await expect(page).toHaveURL(new RegExp(`/ghg/dashboard\\?year=${year}$`));
  const tabs = page.getByRole('tablist', {
    name: GHG_TEXT.inventory.tabsLabel,
  });
  await expect(tabs.getByRole('tab')).toHaveText([
    GHG_TEXT.inventory.tabs.dashboard,
    GHG_TEXT.inventory.tabs.inventory,
    GHG_TEXT.inventory.tabs.organization,
  ]);
  await expect(
    tabs.getByRole('tab', { name: GHG_TEXT.inventory.tabs.dashboard }),
  ).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByTestId('dashboard-total-value')).toContainText(
    '2,500',
  );
  await expect(page.getByTestId('dashboard-total-value-mark')).toHaveText(
    '시트 2개 빠짐',
  );
  await expect(page.getByTestId('dashboard-scope-3-value-mark')).toHaveText(
    '시트 2개 빠짐',
  );
  for (const width of [1280, 1440]) {
    await page.setViewportSize({ width, height: 1100 });
    await expect(page.getByTestId('dashboard-sources')).toBeVisible();
    await motionDone(page);
    if (DB1_SHOTS)
      await page.screenshot({
        path: `${DB1_SHOTS}/dashboard-${width}.png`,
        fullPage: true,
      });
  }
  await page
    .getByRole('combobox', { name: dash.yearLabel })
    .selectOption(String(year - 1));
  await expect(page.getByTestId('dashboard-setup')).toContainText(
    dash.setupTitle,
  );
  if (DB1_SHOTS)
    await page.screenshot({
      path: `${DB1_SHOTS}/dashboard-empty-1440.png`,
      fullPage: true,
    });
  await tabs
    .getByRole('tab', { name: GHG_TEXT.inventory.tabs.inventory })
    .click();
  await expect(page).toHaveURL(/\/ghg\/inventory\?year=\d{4}$/);
  // 밴드 DB2: 해마다 세 해(고른 해·−1·−2)씩 따로 — 차례가 아니라 집합으로.
  expect(
    new Set(
      api.calls
        .filter((call) => call.path === '/inventory/scope12/dashboard')
        .map((call) => call.query),
    ),
  ).toEqual(
    new Set([year, year - 1, year - 2, year - 3].map((y) => `?year=${y}`)),
  );
  expect(unrouted).toEqual([]);
});

// 밴드 DB2 ②: 3개년 막대·전년 대비 한 길(sid:MARC-ENT-598 — e6 ①~⑤). 세 해를 심고(지어낸 값, openapi 꼴) Scope 카드 셋의 막대 칸 ·
//   고른 해 말풍선 · 「전년 대비」 · −2 해 막대 초점 → 말풍선 · 앞 해를 지운 해로 바꾸면 전년 대비 숨김. DB2_SHOTS 를 주면 1280·1440·앞 해 없음 사진.

/** 지어낸 해 판(openapi Scope12DashboardOut 꼴 — 값 셋과 합만 다르다). */
const dashboardOf = (
  year: number,
  [one, two, three]: [number, number, number],
) => ({
  year,
  configured: true,
  decimals: 2,
  basis: 'location',
  unit: 'tCO2-eq',
  complete: true,
  scopes: [
    {
      scopeId: '1',
      scopeName: '지어낸 범위 가',
      scopeOrder: 1,
      value: `${one}`,
      topSources: [
        {
          nodeId: '11',
          name: '지어낸 고정연소',
          value: `${one}`,
          share: '100.0',
        },
      ],
    },
    {
      scopeId: '2',
      scopeName: '지어낸 범위 나',
      scopeOrder: 2,
      value: `${two}`,
      topSources: [
        {
          nodeId: '21',
          name: '지어낸 전기 사용',
          value: `${two}`,
          share: '100.0',
        },
      ],
    },
  ],
  total: {
    scope12: `${one + two}`,
    scope2Market: null,
    scope3: `${three}`,
    sum: `${one + two + three}`,
    scope3FailedSheets: 0,
  },
  bySite: [
    {
      siteId: '1',
      siteName: '본사',
      scopes: [
        { scopeId: '1', value: `${one}` },
        { scopeId: '2', value: `${two}` },
      ],
      scope3: null,
    },
  ],
  scope3Categories: [
    {
      category: 'C1',
      name: '구매 상품 및 서비스',
      value: `${three}`,
      share: '100.0',
    },
  ],
});

test('대시보드 3개년 막대: 카드 셋 막대 칸 · 고른 해 말풍선 · 전년 대비 · 앞 해 초점 말풍선 · 앞 해 없으면 숨김', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = new Date().getFullYear() - 1;
  api.dashboards.set(
    year - 2,
    dashboardOf(year - 2, [520400.5, 310200, 90500]),
  );
  api.dashboards.set(
    year - 1,
    dashboardOf(year - 1, [610300, 280100.25, 120000]),
  );
  api.dashboards.set(year, dashboardOf(year, [705000.75, 250400, 140200]));
  await page.goto(`/ghg/dashboard?year=${year}`);
  for (const scope of [1, 2, 3]) {
    const trend = page.getByTestId(`dashboard-scope-${scope}-trend`);
    await expect(trend.locator('[data-bar]')).toHaveCount(3);
    await motionDone(page);
    // 밴드 DB4: 고른 해 말풍선도 올림·초점 때만(DB3 넘김 R1-2 의 「들면 늘」 갈음).
    await chosenTip(page, scope, year);
  }
  // (1,095,600.75 − 1,010,400.25) ÷ 1,010,400.25 × 100 = 8.43…
  await expect(page.getByTestId('dashboard-total-change')).toHaveText(
    dash.yearUp('8.4'),
  );
  const earliest = page.getByTestId(`dashboard-scope-1-trend-bar-${year - 2}`);
  await expect(
    page.getByTestId(`dashboard-scope-1-trend-tip-${year - 2}`),
  ).toHaveCount(0);
  await earliest.focus();
  await expect(
    page.getByTestId(`dashboard-scope-1-trend-tip-${year - 2}`),
  ).toHaveText(`${year - 2}520,400.5`);
  await earliest.blur();
  for (const width of [1280, 1440]) {
    await page.setViewportSize({ width, height: 1100 });
    await expect(page.getByTestId('dashboard-sources')).toBeVisible();
    await motionDone(page);
    // 밴드 DB4(DB3 넘김 R1-2 갈음): 고른 해 말풍선은 처음 0 · 올림·초점에 뜸(막대 왼쪽).
    //   도넛 합계는 넘쳐서 14 로 내림(마지막 단 — 이 값은 14 로도 92.7 > 84.5, 보고) · 범례 이름 한 줄.
    for (const scope of [1, 2, 3]) await chosenTip(page, scope, year);
    const donut = page.getByTestId('dashboard-donut-total');
    await expect(donut).toHaveAttribute('data-step', '1');
    const legendName = page
      .getByTestId('dashboard-legend-1')
      .getByText('Scope 1', { exact: true });
    expect((await legendName.boundingBox())!.height).toBeLessThan(30);
    // 판단 14: 범례 값은 전체(말줄임 0) — 세 줄 다 넘침 없음(단 18→14→단위 아래 줄로 맞춤).
    await expect
      .poll(() =>
        page
          .getByTestId('dashboard-legend')
          .evaluate((list) =>
            [...list.children].every(
              (row) => row.scrollWidth <= row.clientWidth + 0.5,
            ),
          ),
      )
      .toBe(true);
    await expect(
      page.getByTestId('dashboard-legend-1').locator('[data-legend-value]'),
    ).toHaveText('705,000.75');
    if (DB2_SHOTS)
      await page.screenshot({
        path: `${DB2_SHOTS}/dashboard-${width}.png`,
        fullPage: true,
      });
  }
  // e6 「추정으로 남긴 것」 1·2·4 실측(1440 — 사진을 찍을 때만 적는다).
  if (DB2_SHOTS) {
    const box = async (locator: Locator) => (await locator.boundingBox())!;
    const card = await box(page.getByTestId('dashboard-scope-1'));
    const trend = await box(page.getByTestId('dashboard-scope-1-trend'));
    // 밴드 DB4: 말풍선은 올림 때만 — 재기 전에 고른 해 막대에 올린다.
    await page.getByTestId(`dashboard-scope-1-trend-bar-${year}`).hover();
    const tip = await box(
      page.getByTestId(`dashboard-scope-1-trend-tip-${year}`),
    );
    const ticks = page.getByTestId('dashboard-scope-1-trend-tick');
    const bottom = await box(ticks.last());
    const floor = await box(
      page
        .getByTestId(`dashboard-scope-1-trend-bar-${year}`)
        .locator('[data-bar]'),
    );
    writeFileSync(
      `${DB2_SHOTS}/measure-1440.json`,
      JSON.stringify({
        cardHeight: card.height,
        trendHeight: trend.height,
        tipHeight: tip.height,
        donutTotalWidthAt14: (await page
          .getByTestId('dashboard-donut-total')
          .boundingBox())!.width,
        legendStep: await page
          .getByTestId('dashboard-legend')
          .getAttribute('data-step'),
        zeroTickCenterMinusBarBottom:
          bottom.y + bottom.height / 2 - (floor.y + floor.height),
      }),
    );
  }
  // 앞 해를 지운 판: 고른 해의 −1 이 빈 판(씨앗 없음) → 전년 대비 숨김 · 그 칸 「없음」
  api.dashboards.delete(year - 1);
  await page
    .getByRole('combobox', { name: dash.yearLabel })
    .selectOption(String(year - 1));
  await page
    .getByRole('combobox', { name: dash.yearLabel })
    .selectOption(String(year));
  await expect(
    page.getByTestId(`dashboard-scope-1-trend-bar-${year - 1}`),
  ).toHaveAttribute('data-kind', 'none');
  await motionDone(page);
  await chosenTip(page, 1, year);
  await expect(page.getByTestId('dashboard-total-change')).toHaveCount(0);
  await expect(page.getByRole('alert')).toHaveCount(0);
  if (DB2_SHOTS)
    await page.screenshot({
      path: `${DB2_SHOTS}/dashboard-noprev-1440.png`,
      fullPage: true,
    });
  expect(unrouted).toEqual([]);
});

// 밴드 DB3(sid:MARC-TICK-538 — 움직임 band-handoffs/DB3-motion-values.md e6 ①~④ · 넘김 R1·e6 정함 3·R3): 대시보드 한 길.
//   움직임 켬: 첫 그림에 다섯 이름 · 모든 endTime ≤ 1,000 · 해 바꿈 → 다시 · 같은 해 기다림 → 도는 것 0 · 움직임 줄임: 애니메이션 0 · 끝 상태 그대로.
//   1280·1440 큰 값: −2 해 막대가 눈금 글 칸 오른쪽 · 막대 사이 같음 · 고른 해 말풍선(DB4 — 올림·초점만) · 배출원별 줄 넘침 0 · 넓히면 단이 돌아옴.
//   DB3_SHOTS 를 주면 사진(움직임이 끝난 뒤 — 원시는 워크트리 밖 DB3.out/shots).
const DB3_SHOTS = process.env.DB3_SHOTS;
/** 이 화면에 다는 움직임 이름(e6 ② — motion.css). */
const GHG_MOTIONS = [
  'gw-m-rise',
  'gw-m-sweep',
  'gw-m-grow-y',
  'gw-m-grow',
  'gw-m-fade',
];
/** 한 화면 총 길이 상한(e6 ①). */
const SCREEN_CAP_MS = 1000;

/** 지금 문서의 CSS 애니메이션(이름 · 끝 때 · 도는 중인가). */
const motionsOf = (page: Page) =>
  page.evaluate(() =>
    document.getAnimations().map((motion) => ({
      name: (motion as CSSAnimation).animationName ?? '',
      end: Number(motion.effect?.getComputedTiming().endTime ?? 0),
      running: motion.playState === 'running',
    })),
  );

test('대시보드 움직임(밴드 DB3): 첫 그림 다섯 이름·1초 안 · 해 바꿈 다시 · 같은 해 0 · 움직임 줄임 0 · 1280·1440 배치 · 배출원별 단 돌아옴', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = new Date().getFullYear() - 1;
  // 큰 값(지어낸 — DB2 3개년 e2e 씨앗 값 그대로): 배출원별 줄이 1280 에서 단이 내려가는 자리.
  const big = (at: number, values: [number, number, number]) => {
    const board = dashboardOf(at, values) as ReturnType<typeof dashboardOf> & {
      bySite: unknown[];
    };
    // 배출원별 상위 값(지어낸 여덟 자리 — 감독 판단 16): 1280 은 단 3(이름 위 줄)까지 내려가고 1440 은 그보다 낮다(R3 넓힘을 재는 길이).
    for (const scope of board.scopes)
      scope.topSources[0]!.value = '70500120.75';
    board.bySite.push({
      siteId: '2',
      siteName: '제1공장',
      scopes: [
        { scopeId: '1', value: '10' },
        { scopeId: '2', value: '20' },
      ],
      scope3: null,
    });
    return board;
  };
  api.dashboards.set(year - 2, big(year - 2, [520400.5, 310200, 90500]));
  api.dashboards.set(year - 1, big(year - 1, [610300, 280100.25, 120000]));
  // 고른 해는 Scope 3 카테고리를 비워 빈 상태 글(gw-m-fade)도 한 자리 — 큰 값이면 고른 해 말풍선이 안 들어 fade 가 그것뿐일 수 있다.
  const chosenBoard = big(year, [705000.75, 250400, 140200]);
  chosenBoard.scope3Categories = [];
  api.dashboards.set(year, chosenBoard);

  // ── 움직임 켬(기본 — playwright.config 에 reducedMotion 없음): 1440 에서 첫 그림
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto(`/ghg/dashboard?year=${year}`);
  await expect(page.getByTestId('dashboard-total')).toBeVisible();
  const first = await motionsOf(page);
  // e6 「추정」 1: keyframes 안 var(--gw-m-round) 가 먹는다 — 첫 그림 도중 mask 원 dashoffset 이 0 이 아니다(from 이 ROUND ≈ 395.2).
  const sweeping = await page
    .locator('[data-sweep]')
    .evaluate((node) => parseFloat(getComputedStyle(node).strokeDashoffset));
  expect(sweeping).toBeGreaterThan(0);
  const names = new Set(first.map((motion) => motion.name));
  for (const name of GHG_MOTIONS)
    expect([name, names.has(name)]).toEqual([name, true]);
  const ghg = first.filter((motion) => motion.name.startsWith('gw-m-'));
  expect(ghg.length).toBeGreaterThan(10);
  expect(Math.max(...ghg.map((motion) => motion.end))).toBeLessThanOrEqual(
    SCREEN_CAP_MS,
  );
  // 이름·endTime 표(보고 — 사진을 찍을 때만 적는다).
  if (DB3_SHOTS)
    writeFileSync(
      `${DB3_SHOTS}/motions-1440.json`,
      JSON.stringify(
        [
          ...new Set(ghg.map((motion) => `${motion.name} ${motion.end}`)),
        ].sort(),
        null,
        1,
      ),
    );
  await motionDone(page);
  const stepAt1440 = await page
    .getByTestId('dashboard-sources')
    .getAttribute('data-step');
  if (DB3_SHOTS)
    await page.screenshot({
      path: `${DB3_SHOTS}/dashboard-1440.png`,
      fullPage: true,
    });

  // ── 같은 해에서 아무것도 안 바꾸고 기다림 → 도는 애니메이션 0
  await page.waitForTimeout(300);
  expect((await motionsOf(page)).filter((motion) => motion.running)).toEqual(
    [],
  );

  // ── 1280 · 1440(넘김 R1-1 · R1-2 · e6 정함 3)
  const measured: unknown[] = [{ width: 1440, firstStep: stepAt1440 }];
  for (const width of [1280, 1440]) {
    await page.setViewportSize({ width, height: 1100 });
    await expect(page.getByTestId('dashboard-sources')).toBeVisible();
    await motionDone(page);
    for (const scope of [1, 2, 3]) {
      const trend = page.getByTestId(`dashboard-scope-${scope}-trend`);
      const ticks = (await trend.locator('ol').boundingBox())!;
      const columns = await Promise.all(
        [year - 2, year - 1, year].map(
          async (at) =>
            (await page
              .getByTestId(`dashboard-scope-${scope}-trend-bar-${at}`)
              .boundingBox())!,
        ),
      );
      // R1-1: −2 해 막대 칸 왼쪽 ≥ 눈금 글 칸 오른쪽 · 막대 셋 사이 같음(±1)
      expect(columns[0]!.x).toBeGreaterThanOrEqual(ticks.x + ticks.width);
      const gaps = [
        columns[1]!.x - columns[0]!.x,
        columns[2]!.x - columns[1]!.x,
      ];
      expect(Math.abs(gaps[0]! - gaps[1]!)).toBeLessThanOrEqual(1);
      // R1-2 → 밴드 DB4: 고른 해 말풍선은 올림·초점 때만
      await chosenTip(page, scope, year);
    }
    measured.push({
      width,
      step: await page
        .getByTestId('dashboard-sources')
        .getAttribute('data-step'),
      legendStep: await page
        .getByTestId('dashboard-legend')
        .getAttribute('data-step'),
    });
    // e6 정함 3: 배출원별 줄 넘침 0(넘친 줄을 「폭 단 · 그려진 폭/칸 폭 · 글」로 — 빈 목록 기대) · 이름 칸 ≥ 글 네 자(56)
    await expect
      .poll(() =>
        page
          .getByTestId('dashboard-sources')
          .evaluate((panel) =>
            [...panel.querySelectorAll('li')]
              .filter((row) => row.scrollWidth > row.clientWidth + 0.5)
              .map(
                (row) =>
                  `${window.innerWidth} ${panel.dataset.step} ${row.scrollWidth}/${row.clientWidth} ${row.textContent}`,
              ),
          ),
      )
      .toEqual([]);
    for (const name of await page.getByTestId('dashboard-source-name').all())
      expect((await name.boundingBox())!.width).toBeGreaterThanOrEqual(
        56 - 0.5,
      );
    if (width === 1280) {
      // 1280 큰 값은 처음 1440 보다 단이 내려간다(같으면 이 길이 R3 을 재지 못함).
      await expect
        .poll(async () =>
          Number(
            await page
              .getByTestId('dashboard-sources')
              .getAttribute('data-step'),
          ),
        )
        .toBeGreaterThan(Number(stepAt1440));
      if (DB3_SHOTS)
        await page.screenshot({
          path: `${DB3_SHOTS}/dashboard-1280.png`,
          fullPage: true,
        });
    } else {
      // R3: 1440 으로 넓히면 처음 1440 에서 잰 단으로 돌아옴
      await expect(page.getByTestId('dashboard-sources')).toHaveAttribute(
        'data-step',
        stepAt1440!,
      );
    }
  }

  if (DB3_SHOTS)
    writeFileSync(
      `${DB3_SHOTS}/measure.json`,
      JSON.stringify(measured, null, 1),
    );

  // ── 연도 바꿈 → 다시 움직임
  await page
    .getByRole('combobox', { name: dash.yearLabel })
    .selectOption(String(year - 1));
  await expect(page.getByTestId('dashboard-total')).toBeVisible();
  expect(
    (await motionsOf(page)).some(
      (motion) => motion.name === 'gw-m-rise' && motion.running,
    ),
  ).toBe(true);
  await motionDone(page);

  // ── 앞 해 없음 판(R1-2 다른 갈래 사진)
  await page
    .getByRole('combobox', { name: dash.yearLabel })
    .selectOption(String(year - 2));
  await expect(page.getByTestId('dashboard-total')).toBeVisible();
  await motionDone(page);
  await expect(
    page.getByTestId(`dashboard-scope-1-trend-bar-${year - 3}`),
  ).toHaveAttribute('data-kind', 'none');
  await chosenTip(page, 1, year - 2);
  if (DB3_SHOTS)
    await page.screenshot({
      path: `${DB3_SHOTS}/dashboard-noprev-1440.png`,
      fullPage: true,
    });

  // ── 움직임 줄임: 다시 엶 → 애니메이션 0 · 끝 상태 그대로(막대 transform none · 도넛 mask dashoffset 0)
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto(`/ghg/dashboard?year=${year}`);
  await expect(page.getByTestId('dashboard-total')).toBeVisible();
  await expect(page.locator('[data-bar]')).toHaveCount(9);
  expect(await motionsOf(page)).toEqual([]);
  for (const bar of await page.locator('[data-bar]').all())
    expect(await bar.evaluate((node) => getComputedStyle(node).transform)).toBe(
      'none',
    );
  expect(
    await page
      .locator('[data-sweep]')
      .evaluate((node) => getComputedStyle(node).strokeDashoffset),
  ).toMatch(/^0(px)?$/);
  if (DB3_SHOTS)
    await page.screenshot({
      path: `${DB3_SHOTS}/dashboard-reduced-1440.png`,
      fullPage: true,
    });
  expect(unrouted).toEqual([]);
});

// 밴드 RC1(sid:MARC-ENT-599): S2 표 줄 전체 = 시설 단추와 같은 상세 · Tab+Enter · 닫으면 초점이 그 줄 · 묶인 칸(배출원 유형·배출활동)은 열지 않음.
test('RC1 고객사 S2 줄 클릭: 값 칸 → 상세 · 줄 Enter → 상세 · 닫으면 초점 그 줄 · 묶인 칸은 열지 않음(커서 default · 줄 바탕 그대로)', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  await page.goto(`/ghg/inventory?year=${year}`);
  const row = page.getByTestId('inventory-row-20');
  const dialog = page.locator('[data-screen="ghg-entry-detail"]');
  const value = row.locator('td:not(.align-top)').nth(2); // 자산/시설 · 해 셋 중 둘째 — 단추 밖
  await expect(value).toBeVisible();

  // 1. 값 칸 클릭 → 상세.
  await value.click();
  await expect(dialog.getByTestId('entry-site-1')).toBeVisible();
  await expect(dialog).toHaveCount(1);
  await close(dialog);
  await expect(dialog).toHaveCount(0);

  // 2. 줄에 초점 → Enter → 같은 상세 → 닫으면 초점이 그 줄.
  await row.focus();
  await page.keyboard.press('Enter');
  await expect(dialog.getByTestId('entry-site-1')).toBeVisible();
  await close(dialog);
  await expect(dialog).toHaveCount(0);
  await expect(row).toBeFocused();

  // 3. 묶인 칸: 커서 default · 올려도 그 줄 바탕 그대로(값 칸에 올리면 바뀜 — 잰 값이 움직이는지 대조) · 눌러도 열리지 않음.
  const group = row.locator('td.align-top').first();
  await expect(group).toHaveCSS('cursor', 'default');
  await expect(value).toHaveCSS('cursor', 'pointer');
  const rowBg = () =>
    row.evaluate((element) => getComputedStyle(element).backgroundColor);
  // 2. 에서 줄에 남은 초점(focus-visible 바탕)을 걷고 잰다.
  await row.evaluate((element) => (element as HTMLElement).blur());
  await page.mouse.move(1, 1);
  const resting = await rowBg();
  await value.hover();
  await expect.poll(rowBg).not.toBe(resting);
  await group.hover();
  await expect.poll(rowBg).toBe(resting);
  await group.click();
  await row.locator('td.align-top').nth(1).click();
  // 묶인 칸 뒤 값 칸을 누르면 창은 하나(묶인 칸이 열었으면 둘째 클릭은 창에 가려진다).
  await value.click();
  await expect(dialog.getByTestId('entry-site-1')).toBeVisible();
  await expect(dialog).toHaveCount(1);
  await close(dialog);

  expect(unrouted).toEqual([]);
});

// 밴드 DB4(sid:MARC-TICK-543 — 발주서 §3 e2e · 감독 판단 3·4): 3개년 말풍선 올림·초점만 · 인벤토리 고리 쓸기 · 제목 숫자 굴림(여섯 자리).
//   움직임 켬: 대시보드 첫 그림(움직임 끝난 뒤도) 말풍선 0 → 고른 해 hover 뜸 · 인벤토리 고리 gw-m-sweep(endTime ≤ 1,000) ·
//   굴림 끝 글자 = 움직임 줄임 판 글자(바이트) · 움직임 줄임: 고리 애니메이션 0 · 굴림 칸 0.
//   DB4_SHOTS 를 주면 사진(원시는 워크트리 밖 DB4.out/shots).
const DB4_SHOTS = process.env.DB4_SHOTS;
/** 굴리는 여섯 자리(대시보드 다섯 · 인벤토리 하나). */
const ROLLED_DASHBOARD = [
  'dashboard-total-value',
  'dashboard-scope-1-value',
  'dashboard-scope-2-value',
  'dashboard-scope-3-value',
  'dashboard-donut-total',
];
/** 굴림이 끝날 때까지(굴림 칸 0) 기다린 뒤 글자들. */
async function rolledTexts(page: Page, ids: readonly string[]) {
  await expect(page.locator('[data-rolling]')).toHaveCount(0);
  return Promise.all(ids.map((id) => page.getByTestId(id).textContent()));
}
/** 고리(emission-ring) 안의 CSS 애니메이션(이름 · 끝 때). */
const ringMotionsOf = (page: Page) =>
  page.evaluate(() =>
    document
      .getAnimations()
      .filter((motion) => {
        const target = (motion.effect as KeyframeEffect | null)?.target;
        return !!target?.closest('[data-testid="emission-ring"]');
      })
      .map((motion) => ({
        name: (motion as CSSAnimation).animationName ?? '',
        end: Number(motion.effect?.getComputedTiming().endTime ?? 0),
      })),
  );

test('DB4: 대시보드 말풍선 첫 그림 0 → 고른 해 hover 뜸 · 숫자 굴림 끝 글자 = 움직임 줄임 판 · 인벤토리 고리 쓸기 ≤ 1초 · 움직임 줄임 0', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = new Date().getFullYear() - 1;
  // 지어낸 값(소수 둘·하나 · 천 단위 쉼표 — 굴림이 소수를 지키는지)
  api.dashboards.set(
    year - 1,
    dashboardOf(year - 1, [610300, 280100.25, 120000]),
  );
  api.dashboards.set(year, dashboardOf(year, [705000.75, 250400.5, 140200]));
  await page.setViewportSize({ width: 1440, height: 1100 });

  // ── 대시보드(움직임 켬)
  await page.goto(`/ghg/dashboard?year=${year}`);
  await expect(page.getByTestId('dashboard-total')).toBeVisible();
  // 첫 그림에 다섯 자리가 굴림 칸으로 붙는다(1초 안에 끝 — 붙자마자 센다)
  expect(await page.locator('[data-rolling]').count()).toBe(5);
  const tips = page.getByTestId(/^dashboard-scope-\d-trend-tip-/);
  await expect(tips).toHaveCount(0);
  await motionDone(page);
  const moving = await rolledTexts(page, ROLLED_DASHBOARD);
  await expect(tips).toHaveCount(0);
  if (DB4_SHOTS)
    await page.screenshot({
      path: `${DB4_SHOTS}/dashboard-1440-first.png`,
      fullPage: true,
    });
  const chosen = page.getByTestId(`dashboard-scope-1-trend-bar-${year}`);
  await chosen.hover();
  await expect(
    page.getByTestId(`dashboard-scope-1-trend-tip-${year}`),
  ).toBeVisible();
  await expect(tips).toHaveCount(1);
  await motionDone(page);
  if (DB4_SHOTS)
    await page.screenshot({
      path: `${DB4_SHOTS}/dashboard-1440-hover.png`,
      fullPage: true,
    });
  await page.mouse.move(0, 0);
  await expect(tips).toHaveCount(0);

  // ── 인벤토리(움직임 켬): 고리 쓸기 하나 · endTime ≤ 1,000
  const inventoryYear = seedEntry(api);
  await page.goto(`/ghg/inventory?year=${inventoryYear}`);
  await expect(page.getByTestId('emission-ring')).toBeVisible();
  expect(
    await page.getByTestId('emission-total').locator('[data-rolling]').count(),
  ).toBe(1);
  const ring = await ringMotionsOf(page);
  expect(ring.map((motion) => motion.name)).toEqual(['gw-m-sweep']);
  expect(ring[0]!.end).toBeLessThanOrEqual(1000);
  await motionDone(page);
  const [movingTotal] = await rolledTexts(page, ['emission-total']);
  if (DB4_SHOTS)
    await page
      .getByTestId('emission-card')
      .screenshot({ path: `${DB4_SHOTS}/inventory-card-1440.png` });
  // 접고 펴면 다시 안 쓸림(같은 해 — 감독 판단 2)
  await page.getByRole('button', { name: inventory.card.collapse }).click();
  await page.getByRole('button', { name: inventory.card.expand }).click();
  await expect(page.getByTestId('emission-ring')).toBeVisible();
  expect(await ringMotionsOf(page)).toEqual([]);
  await expect(page.locator('[data-rolling]')).toHaveCount(0);

  // ── 움직임 줄임: 굴림 칸 0 · 고리 애니메이션 0 · 글자가 움직임 켬 판의 끝 글자와 같음
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto(`/ghg/dashboard?year=${year}`);
  await expect(page.getByTestId('dashboard-total')).toBeVisible();
  await expect(page.getByTestId('dashboard-scope-1-value')).toContainText(
    'tCO2eq',
  );
  expect(await page.locator('[data-rolling]').count()).toBe(0);
  const still = await Promise.all(
    ROLLED_DASHBOARD.map((id) => page.getByTestId(id).textContent()),
  );
  expect(moving).toEqual(still);
  await page.goto(`/ghg/inventory?year=${inventoryYear}`);
  await expect(page.getByTestId('emission-ring')).toBeVisible();
  expect(await page.locator('[data-rolling]').count()).toBe(0);
  expect(await ringMotionsOf(page)).toEqual([]);
  expect(await page.getByTestId('emission-total').textContent()).toBe(
    movingTotal,
  );
  expect(unrouted).toEqual([]);
});

// 밴드 DB5(sid:MARC-TICK-544 — 발주서 §3 e2e · 감독 판단 1): 인벤토리 범례 값 칸도 가운데 합과 같은 때 굴림.
//   움직임 켬: 첫 그림에 범례 값(0·「-」 빼고) 굴림 칸 · 끝 글자 = 움직임 줄임 판 글자(바이트) · 접고 펴면 0.
//   DB5_SHOTS 를 주면 인벤토리 카드 1440 끝 상태 사진(원시는 워크트리 밖 DB5.out/shots). Scope 3 카드는 jsdom 만(ResultView.test).
const DB5_SHOTS = process.env.DB5_SHOTS;
const legendValues = (page: Page) =>
  page.locator(
    '[data-testid="emission-card"] li[data-testid^="emission-"] [data-testid$="-value"]',
  );

test('DB5: 인벤토리 범례 값 굴림 — 첫 그림에 굴림 칸 · 끝 글자 = 움직임 줄임 판 · 접고 펴면 0', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await page.setViewportSize({ width: 1440, height: 1100 });
  const inventoryYear = seedEntry(api);
  await page.goto(`/ghg/inventory?year=${inventoryYear}`);
  await expect(page.getByTestId('emission-ring')).toBeVisible();
  // 붙자마자 센다(1초 안에 끝): 굴릴 수 있는 범례 값(양수)마다 굴림 칸 하나
  const rollingNow = await legendValues(page).evaluateAll(
    (nodes) =>
      nodes.filter((node) => node.querySelector('[data-rolling]')).length,
  );
  expect(rollingNow).toBeGreaterThan(0);
  await motionDone(page);
  await expect(page.locator('[data-rolling]')).toHaveCount(0);
  const moving = await legendValues(page).allTextContents();
  expect(moving.length).toBeGreaterThan(0);
  if (DB5_SHOTS)
    await page
      .getByTestId('emission-card')
      .screenshot({ path: `${DB5_SHOTS}/inventory-card-1440.png` });
  await page.getByRole('button', { name: inventory.card.collapse }).click();
  await page.getByRole('button', { name: inventory.card.expand }).click();
  await expect(page.getByTestId('emission-ring')).toBeVisible();
  await expect(page.locator('[data-rolling]')).toHaveCount(0);

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto(`/ghg/inventory?year=${inventoryYear}`);
  await expect(page.getByTestId('emission-ring')).toBeVisible();
  expect(await page.locator('[data-rolling]').count()).toBe(0);
  expect(await legendValues(page).allTextContents()).toEqual(moving);
  expect(unrouted).toEqual([]);
});

// ── 밴드 S12Q1 ④: Scope 1·2 의견 1차(sid:MARC-ENT-644) — S12-05 시설 0 잎 · S12-04 토스트 · S12-03 추정 하나 · 출처 [수정] ──

test('S12-05 고객사: 자산/시설 없는 잎(기본 계수 있음) → S17 에서 흐림 없이 고름 → 저장 200 → S2 줄 → 상세 「데이터 입력」 안내 + [조직구조로] → /ghg/organization', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  // 잎 22(코드 2): 기본 계수만 넣고 자산/시설 줄은 넣지 않는다 — 이 회사엔 그 코드의 자산/시설 0.
  api.poolFactors.push({
    id: 25,
    leafId: 22,
    isDefault: true,
    versions: [...api.poolFactors.find((f) => f.id === 21)!.versions],
  });
  const year = api.thisYear - 1;
  await page.goto(`/ghg/inventory/index-settings?year=${year}`);
  const leaf = page.getByRole('checkbox', {
    name: settings.check('지어낸 발전기'),
  });
  await expect(leaf).toBeEnabled();
  await expect(page.getByTestId('ghg-why-line-22')).toHaveCount(0);
  await expect(page.getByTestId('ghg-name-22').locator('..')).toContainText(
    '(0)',
  );
  await leaf.click();
  await saveSettings(page);
  await expect(page).toHaveURL(new RegExp(`/ghg/inventory\\?year=${year}$`));
  expect(api.bodies(SAVE(year))).toEqual([{ facilityNodeIds: [22] }]);
  await expect(savedToast(page, inventory.saved)).toBeVisible();
  await page.getByTestId('inventory-open-22').click();
  const dialog = page.locator('[data-screen="ghg-entry-detail"]');
  const line = dialog.getByTestId('entry-no-facilities-line');
  await expect(line).toContainText(entryWords.noFacilities);
  await expect(dialog.locator('[data-testid^="entry-site-"]')).toHaveCount(0);
  await line.getByRole('button', { name: entryWords.toOrganization }).click();
  await expect(page).toHaveURL(/\/ghg\/organization$/);
  await expect(page.getByRole('heading', { name: words.title })).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('S12-04 토스트: 상세 [저장] → 창 위(z·hit) 「저장됐어요」 role=status · 머리 아래 24 가운데 · 3초 뒤 사라짐 · 움직임 줄임이면 움직임 0', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const dialog = await savedRow(page, year); // 본사 r1 저장 — 토스트 하나
  const toast = savedToast(page, entryWords.saved);
  await expect(toast).toBeVisible();
  await expect(page.getByTestId('toast')).toHaveCount(1);
  // 들어오는 움직임(위에서 8 내려옴 220ms)이 끝난 자리 = 머리(64) 아래 24.
  await expect
    .poll(async () => Math.round((await toast.boundingBox())!.y))
    .toBe(88);
  const box = (await toast.boundingBox())!;
  const width = page.viewportSize()!.width;
  expect(Math.abs(box.x + box.width / 2 - width / 2)).toBeLessThanOrEqual(1);
  // 창(모달) 위: 토스트 가운데 점을 누르면 토스트가 맞는다(덮개·창 아님).
  const hit = await page.evaluate(
    ([x, y]) =>
      document.elementFromPoint(x!, y!)?.closest('[data-testid="toast"]') !==
      null,
    [box.x + box.width / 2, box.y + box.height / 2],
  );
  expect(hit).toBe(true);
  await expect(toast).toHaveCSS('animation-name', 'toast-m-in');
  await expect(page.getByTestId('toast')).toHaveCount(0, { timeout: 5000 });
  await expect(dialog).toBeVisible();

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await dialog.getByTestId(`entry-amount-r1:${year}-02`).fill('4.5');
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  await expect(savedToast(page, entryWords.saved)).toHaveCSS(
    'animation-name',
    'none',
  );
  expect(unrouted).toEqual([]);
});

test('S12-03 추정 하나: 상세 잠금 옆 단추 켬 → [저장] → 닫으면 S2 목록 「추정치」 ≈ · 다시 열어 끔 → 저장 → ≈ 0', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  const year = seedEntry(api);
  const listMark = page
    .getByTestId('inventory-row-20')
    .getByRole('img', { name: inventory.estimatedLabel });
  let dialog = await savedRow(page, year); // 본사 r1 저장(추정 0)
  await expect(listMark).toHaveCount(0);
  await dialog.getByTestId('entry-estimated').click();
  await expect(dialog.getByTestId('entry-estimated')).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await saveAll(dialog);
  await expect(savedToast(page, entryWords.saved)).toBeVisible();
  await close(dialog);
  await expect(dialog).toHaveCount(0);
  await expect(listMark).toBeVisible();
  dialog = await openEntry(page, year);
  await expect(dialog.getByTestId('entry-estimated')).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await dialog.getByTestId('entry-estimated').click();
  await saveAll(dialog);
  await expect(dialog.getByTestId('entry-estimated')).toHaveAttribute(
    'aria-pressed',
    'false',
  );
  await close(dialog);
  await expect(listMark).toHaveCount(0);
  expect(unrouted).toEqual([]);
});

test('S12-03 출처 칸 [수정](운영 관리자): S8 없이 S9 → 등유 계수 → 사유 → PUT {factorId} · 닫히면 초점 [수정]', async ({
  page,
}) => {
  const { unrouted, api } = await open(page, 'admin');
  const year = seedEntry(api);
  await savedRow(page, year);
  const edit = page.getByTestId('entry-factor-edit-r1');
  await expect(edit).toHaveText(editWords.cell);
  await edit.click();
  const s9 = page.getByTestId('entry-factor-edit');
  await expect(s9.getByTestId('entry-factor-pick')).toBeVisible();
  await expect(page.getByTestId('entry-factor')).toHaveCount(0);
  await expect(s9).toHaveCSS('width', '960px');
  await s9
    .getByRole('checkbox', { name: editWords.pick('지어낸 등유 계수') })
    .click();
  await s9.getByTestId('entry-factor-next').click();
  await writeReason(page, '지어낸 칸 사유');
  await expect(s9).toHaveCount(0);
  expect(api.bodies(`PUT ${X(year)}/rows/1/factor`)).toEqual([
    { factorId: 23, reason: '지어낸 칸 사유' },
  ]);
  await expect(page.getByTestId('entry-done-1')).toHaveText(editWords.done);
  await expect(edit).toBeFocused();
  expect(unrouted).toEqual([]);
});
