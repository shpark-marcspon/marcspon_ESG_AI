// 검토 표를 실제 브라우저(머리 없는 Chromium)에서 본다. jsdom 에는 배치가 없어, 「보이는 만큼만 그린다」와 스크롤은 여기서만 진짜로 확인된다.
// 기다림은 전부 상태를 물어서 한다(시간에 기대지 않는다): expect(...) 가 조건이 될 때까지 다시 묻는다.
//
// 기대값은 화면과 따로 센다: 가짜 5,000행을 같은 씨앗으로 다시 만들어, 이 파일 안에서 손으로 세듯 센다(업무 로직의 함수를 쓰지 않는다).
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { makeFakeInput } from '../src/pages/demo-table/fakeRows.ts';

const ROWS = 5000;
const fake = makeFakeInput(ROWS).rows;

/** 그 행의 지금 배출량: 수정값이 있으면 그 값, 없으면 대표 후보의 값. */
const emissionOf = (row: (typeof fake)[number]) =>
  row.review.edit ?
    row.review.edit.emission
  : (row.ai.candidates[0]?.emission ?? null);
const countOf = (status: string) =>
  fake.filter((row) => row.review.status === status).length;
const finalTotalBefore = fake
  .filter((row) => row.review.status === 'finalized')
  .reduce((sum, row) => sum + emissionOf(row)!, 0);
/** 일괄 최종 확정이 되는 행: 반영 또는 수정이고 배출량이 있다. */
const finalizable = fake.filter(
  (row) =>
    (row.review.status === 'accepted' || row.review.status === 'edited') &&
    emissionOf(row) !== null,
);

const scrollBox = (page: Page) => page.getByTestId('rt-scroll');
const summary = (page: Page) => page.getByTestId('rt-summary');
const statusCount = (page: Page, status: string) =>
  summary(page).locator(`[data-status-count="${status}"]`);
const finalTotal = async (page: Page) =>
  Number(await summary(page).getAttribute('data-final-total'));
const row = (page: Page, id: string) => page.locator(`[data-row-id="${id}"]`);

/**
 * 배출량 숫자의 기대 글자. 화면의 꼴(model/format.ts)을 가져오지 않고 결정의 규칙(sid:MARC-ENT-272)으로 따로 적는다:
 * 소수 셋째까지, 끝 0 뺌, 0 < 값 < 0.0005 는 「<0.001」. 단위 글자는 tCO2eq.
 */
const emissionText = (value: number) =>
  value > 0 && value < 0.0005 ?
    '<0.001'
  : new Intl.NumberFormat('ko', { maximumFractionDigits: 3 }).format(value);

/** 스크롤 길이가 기대값이 될 때까지 묻는다. scrollHeight 는 정수로 반올림되고 행의 높이는 소수일 수 있어 1px 까지 봐준다. */
const expectScrollHeight = (page: Page, expected: number) =>
  expect
    .poll(
      async () =>
        Math.abs(
          (await scrollBox(page).evaluate((box) => box.scrollHeight)) -
            expected,
        ) <= 1,
      { message: `스크롤 길이가 ${expected} 여야 한다` },
    )
    .toBe(true);

async function openFake(page: Page, extra = '') {
  await page.goto(`/dev/table?data=fake&rows=${ROWS}${extra}`);
  await expect(page.locator('[data-row-id]').first()).toBeVisible();
}

test.describe('가짜 5,000행', () => {
  test('DOM 에는 보이는 만큼의 행만 있고, 끝까지 스크롤하면 마지막 행에 닿는다', async ({
    page,
  }) => {
    await openFake(page);
    await expect(summary(page)).toHaveAttribute('data-total', String(ROWS));
    const atTop = await page.locator('[data-row-id]').count();
    expect(atTop).toBeGreaterThan(10);
    expect(atTop).toBeLessThan(60);
    await expect(page.locator('[data-index="0"]')).toBeVisible();

    await scrollBox(page).evaluate((box) => (box.scrollTop = box.scrollHeight));
    const last = page.locator(`[data-index="${ROWS - 1}"]`);
    await expect(last).toBeVisible();
    await expect(last).toHaveAttribute('data-row-id', fake[ROWS - 1]!.id);
    await expect(page.locator('[data-index="0"]')).toHaveCount(0);
    expect(await page.locator('[data-row-id]').count()).toBeLessThan(60);
    // 마지막 행의 아래 끝이 스크롤 상자 안에 있다(스크롤 길이가 모자라지 않다).
    const [boxBottom, rowBottom] = await Promise.all([
      scrollBox(page).evaluate((box) => box.getBoundingClientRect().bottom),
      last.evaluate((element) => element.getBoundingClientRect().bottom),
    ]);
    expect(rowBottom).toBeLessThanOrEqual(boxBottom + 1);
  });

  test('요약의 처음 숫자가 따로 센 것과 같다', async ({ page }) => {
    await openFake(page);
    for (const status of [
      'pending',
      'accepted',
      'declined',
      'edited',
      'rerequested',
      'rejected',
      'finalized',
    ]) {
      await expect(statusCount(page, status)).toHaveAttribute(
        'data-count',
        String(countOf(status)),
      );
    }
    expect(await finalTotal(page)).toBeCloseTo(finalTotalBefore, 3);
    // 속성만이 아니라 눈에 보이는 글자도 같은 수다.
    await expect(statusCount(page, 'pending')).toHaveText(
      `검토대기 ${countOf('pending').toLocaleString('ko')}`,
    );
    await expect(summary(page)).toContainText(
      `확정 합계 ${emissionText(finalTotalBefore)} tCO2eq`,
    );
  });

  test('일괄 최종 확정: 화면에 없는 행까지 바뀌고, 건너뛴 수가 맞다', async ({
    page,
  }) => {
    await openFake(page);
    await page.getByRole('button', { name: '일괄 최종 확정' }).click();
    const result = page.getByTestId('rt-bulk-result');
    await expect(result).toHaveAttribute('data-targeted', String(ROWS));
    await expect(result).toHaveAttribute(
      'data-applied',
      String(finalizable.length),
    );
    await expect(result).toHaveAttribute(
      'data-skipped',
      String(ROWS - finalizable.length),
    );
    await expect(statusCount(page, 'finalized')).toHaveAttribute(
      'data-count',
      String(countOf('finalized') + finalizable.length),
    );
    await expect(statusCount(page, 'pending')).toHaveAttribute(
      'data-count',
      String(countOf('pending')),
    );
    expect(await finalTotal(page)).toBeCloseTo(
      finalTotalBefore +
        finalizable.reduce((sum, r) => sum + emissionOf(r)!, 0),
      3,
    );

    // 맨 끝 쪽에 있던(화면에 그려진 적 없는) 반영 행을 찾아가 본다.
    const far = finalizable[finalizable.length - 1]!;
    await page.getByLabel('글자로 걸러 보기').fill(String(far.raw.itemName));
    await expect(row(page, far.id)).toHaveAttribute('data-status', 'finalized');
  });

  test('상태로 걸러 본 뒤의 일괄 최종 확정은 걸러 본 행만 바꾼다', async ({
    page,
  }) => {
    await openFake(page);
    const accepted = fake.filter((r) => r.review.status === 'accepted');
    const able = accepted.filter((r) => emissionOf(r) !== null);
    await page.getByLabel('상태로 걸러 보기').selectOption('accepted');
    await expect(page.getByTestId('rt-shown')).toHaveAttribute(
      'data-shown',
      String(accepted.length),
    );
    await page.getByRole('button', { name: '일괄 최종 확정' }).click();
    const result = page.getByTestId('rt-bulk-result');
    await expect(result).toHaveAttribute(
      'data-targeted',
      String(accepted.length),
    );
    await expect(result).toHaveAttribute('data-applied', String(able.length));

    await page.getByLabel('상태로 걸러 보기').selectOption('');
    await expect(statusCount(page, 'finalized')).toHaveAttribute(
      'data-count',
      String(countOf('finalized') + able.length),
    );
    // 걸러 본 결과 밖에 있던 수정 행은 그대로다(확정할 수 있는 행이었는데도).
    await expect(statusCount(page, 'edited')).toHaveAttribute(
      'data-count',
      String(countOf('edited')),
    );
    await expect(statusCount(page, 'accepted')).toHaveAttribute(
      'data-count',
      String(accepted.length - able.length),
    );
  });

  test('정렬하면 순서가 바뀌고 DOM 의 행 수는 그대로 적다', async ({
    page,
  }) => {
    await openFake(page);
    await page.getByRole('button', { name: '배출량(tCO2eq)' }).click();
    const withEmission = fake.filter((r) => emissionOf(r) !== null);
    const smallest = [...withEmission].sort(
      (a, b) => emissionOf(a)! - emissionOf(b)!,
    )[0]!;
    await expect(page.locator('[data-index="0"]')).toHaveAttribute(
      'data-row-id',
      smallest.id,
    );
    await page.getByRole('button', { name: '배출량(tCO2eq)' }).click();
    const largest = Math.max(...withEmission.map((r) => emissionOf(r)!));
    await expect(
      page.locator('[data-index="0"] [data-column="emission"]'),
    ).toHaveText(emissionText(largest));
    expect(await page.locator('[data-row-id]').count()).toBeLessThan(60);
  });

  test('키보드: End 로 마지막 행까지 가고, 그 행이 화면에 들어온다', async ({
    page,
  }) => {
    await openFake(page);
    await scrollBox(page).focus();
    await page.keyboard.press('ArrowDown');
    await expect(page.locator('[data-active]')).toHaveAttribute(
      'data-index',
      '0',
    );
    await page.keyboard.press('End');
    await expect(page.locator('[data-active]')).toHaveAttribute(
      'data-index',
      String(ROWS - 1),
    );
    await expect(page.locator('[data-active]')).toBeInViewport();
  });

  test('펼친 행은 높이가 달라지고, 스크롤 길이가 그만큼 늘어난다', async ({
    page,
  }) => {
    await openFake(page);
    const first = page.locator('[data-index="0"]');
    const closed = await first.evaluate(
      (element) => element.getBoundingClientRect().height,
    );
    const before = await scrollBox(page).evaluate((box) => box.scrollHeight);
    expect(before).toBe(ROWS * closed);

    await first.getByLabel('펼치기').click();
    await expect(first.getByLabel('접기')).toBeVisible();
    const open = await first.evaluate(
      (element) => element.getBoundingClientRect().height,
    );
    expect(open).toBeGreaterThan(closed + 40);
    // 잰 높이가 가상 스크롤에 반영될 때까지 스크롤 길이를 묻는다(펼친 직후에는 아직 어림값이다).
    // 「아래 행이 겹치지 않는다」는 보지 않는다. 행을 흐름대로 쌓으므로 브라우저가 밀어내, 측정과 무관하게 늘 참이다(카드 화면도 같다).
    await expectScrollHeight(page, before + (open - closed));

    await first.getByLabel('접기').click();
    await expectScrollHeight(page, before);
  });

  test('카드 화면: 펼친 카드가 커진 만큼 스크롤 길이가 늘어난다', async ({
    page,
  }) => {
    // 카드도 표의 행과 같은 행 창(RowStack)에 흐름대로 쌓인다. 펼친 카드 아래의 카드는 브라우저가 밀어내므로 겹치지 않는 것은 늘 참이고,
    // 여기서 볼 것은 잰 높이가 가상 스크롤에 들어오는가다: 안 들어오면 스크롤 길이가 펼치기 전 그대로라 끝의 카드에 닿지 못한다.
    // 넓은 화면에서는 펼친 내용이 카드의 최소 높이 안에 한 줄로 들어가 높이가 안 변한다(그러면 이 검사는 아무것도 보지 않는다).
    // 그래서 화면을 좁히고, 후보가 둘 이상이라 펼치면 확실히 커지는 카드를 고른다.
    await page.setViewportSize({ width: 480, height: 900 });
    await openFake(page, '&screen=cards');
    const index = fake.findIndex(
      (r, i) => i < 8 && r.ai.candidates.length >= 2,
    );
    expect(index).toBeGreaterThanOrEqual(0);
    const card = page.locator(`[data-index="${index}"]`);
    const height = () =>
      card.evaluate((element) => element.getBoundingClientRect().height);
    const closed = await height();
    const total = await scrollBox(page).evaluate((box) => box.scrollHeight);

    await card.getByLabel('펼치기').click();
    await expect(card.getByLabel('접기')).toBeVisible();
    // 전제: 이 카드는 펼치면 커진다. 커지지 않으면 아래의 검사가 뜻이 없으므로 여기서 떨어지게 한다.
    const grown = (await height()) - closed;
    expect(grown).toBeGreaterThan(30);
    await expectScrollHeight(page, total + grown);
  });

  test('둘째 화면(카드)도 같은 5,000행을 보이는 만큼만 그리고, 일괄 동작이 같은 수를 낸다', async ({
    page,
  }) => {
    await openFake(page, '&screen=cards');
    expect(await page.locator('[data-row-id]').count()).toBeLessThan(40);
    await page.getByRole('button', { name: '일괄 최종 확정' }).click();
    await expect(page.getByTestId('rt-bulk-result')).toHaveAttribute(
      'data-applied',
      String(finalizable.length),
    );
    await scrollBox(page).evaluate((box) => (box.scrollTop = box.scrollHeight));
    await expect(page.locator(`[data-index="${ROWS - 1}"]`)).toBeVisible();
  });
});

test.describe('손으로 쓴 예시(8행)', () => {
  // 예시의 값(tCO2eq): s1 은 검토대기, 후보 셋(1.8 / 3 / 3.6). s4 만 최종확정(0.28).
  test('한 행을 수정하고 확정하면 요약이 바뀐다. 원본값과 수정값이 둘 다 보인다', async ({
    page,
  }) => {
    await page.goto('/dev/table?data=sample');
    await expect(summary(page)).toHaveAttribute('data-final-total', '0.28');
    const s1 = row(page, 's1');
    await s1.getByLabel('펼치기').click();
    await s1.getByLabel('후보 2 고르기').check();
    await expect(s1).toHaveAttribute('data-status', 'edited');
    await expect(s1.getByTestId('rt-original')).toContainText('1.8 tCO2eq');
    await expect(s1.getByTestId('rt-edited')).toContainText('3 tCO2eq');
    // 확정 전에는 결과 합계가 그대로고, 임시 합계에만 든다.
    await expect(summary(page)).toHaveAttribute('data-final-total', '0.28');

    await s1.getByRole('button', { name: '최종 확정' }).click();
    await expect(s1).toHaveAttribute('data-status', 'finalized');
    // 3 + 0.28 은 부동소수 합이라 속성 글자가 「3.2800000000000002」다. 글자가 아니라 수로 견준다.
    await expect.poll(() => finalTotal(page)).toBeCloseTo(3.28, 6);
    await expect(statusCount(page, 'finalized')).toHaveAttribute(
      'data-count',
      '2',
    );
    await expect(statusCount(page, 'pending')).toHaveAttribute(
      'data-count',
      '1',
    );
  });

  test('계산이 늦게 답하는 동안은 재계산 대기이고 최종 확정 단추가 잠긴다', async ({
    page,
  }) => {
    // 대역이 답을 일부러 늦춘다. 기다림은 시간에 기대지 않고 화면의 상태를 묻는다.
    await page.goto('/dev/table?data=sample&calcDelay=600');
    const s1 = row(page, 's1');
    await s1.getByLabel('펼치기').click();
    await s1.getByLabel('후보 3 고르기').check();
    await expect(summary(page)).toHaveAttribute('data-recalc-pending', '1');
    await expect(s1.getByRole('button', { name: '최종 확정' })).toBeDisabled();
    await expect(summary(page)).toHaveAttribute('data-recalc-pending', '0');
    await expect(s1.getByTestId('rt-edited')).toContainText('3.6 tCO2eq');
    await expect(s1.getByRole('button', { name: '최종 확정' })).toBeEnabled();
  });

  test('사유 없는 반려는 거부되고, 후보 없는 행은 반영 단추가 잠겨 있다', async ({
    page,
  }) => {
    await page.goto('/dev/table?data=sample');
    const s1 = row(page, 's1');
    await s1.getByLabel('펼치기').click();
    await s1.getByRole('button', { name: '반려' }).click();
    await expect(s1.getByRole('alert')).toContainText('사유');
    await expect(s1).toHaveAttribute('data-status', 'pending');
    const s5 = row(page, 's5');
    await s5.getByLabel('펼치기').click();
    await expect(
      s5.getByRole('button', { name: '반영', exact: true }),
    ).toBeDisabled();
  });
});

test.describe('계산 실패', () => {
  test('계산이 실패한 행: 표시가 남고, 확정이 거부되고, 일괄의 건너뛴 까닭에 나오고, 다시 계산하면 풀린다', async ({
    page,
  }) => {
    // 계산 대역이 행마다 첫 계산을 실패한다(둘째부터는 답한다).
    await page.goto('/dev/table?data=sample&calcFail=1');
    const target = row(page, 's1');
    await expect(target).toBeVisible();
    await expect(summary(page)).toHaveAttribute('data-recalc-failed', '0');

    await target.getByLabel('펼치기').click();
    await target.getByLabel('후보 2 고르기').check();
    await expect(target).toHaveAttribute('data-calc-failed', 'true');
    await expect(target).toHaveAttribute('data-status', 'edited');
    // 눈에 보이는 글자: 행의 배출량 칸, 펼친 속의 알림, 요약의 개수.
    await expect(target.locator('[data-column="emission"]')).toHaveText(
      '계산 실패',
    );
    await expect(target.getByTestId('rt-calc-failed')).toContainText(
      '배출량을 계산하지 못했다',
    );
    await expect(summary(page)).toHaveAttribute('data-recalc-failed', '1');
    await expect(summary(page)).toContainText('계산 실패 1');

    // 최종 확정이 잠겨 있고, 일괄로 해도 건너뛴다.
    await expect(
      target.getByRole('button', { name: '최종 확정' }),
    ).toBeDisabled();
    await page.getByLabel('글자로 걸러 보기').fill('수지 원료');
    await page.getByRole('button', { name: '일괄 최종 확정' }).click();
    const result = page.getByTestId('rt-bulk-result');
    await expect(result).toHaveAttribute('data-applied', '0');
    await expect(result).toHaveAttribute('data-skipped', '1');
    await expect(result).toContainText(
      '수정 1개: 계산하지 못했다(계산이 실패했다). 다시 계산해야 한다.',
    );
    await expect(target).toHaveAttribute('data-status', 'edited');

    // 다시 계산 → 이번에는 답이 온다 → 확정된다. 합계에는 고른 후보(둘째)의 값이 든다.
    await target.getByRole('button', { name: '다시 계산' }).click();
    await expect(target).not.toHaveAttribute('data-calc-failed', 'true');
    await expect(target.getByTestId('rt-calc-failed')).toHaveCount(0);
    await expect(summary(page)).toHaveAttribute('data-recalc-failed', '0');
    await expect(target.locator('[data-column="emission"]')).toHaveText('3');
    const before = await finalTotal(page);
    await target.getByRole('button', { name: '최종 확정' }).click();
    await expect(target).toHaveAttribute('data-status', 'finalized');
    expect((await finalTotal(page)) - before).toBeCloseTo(3, 6);
  });

  test('계산 대역이 실패하지 않으면(앞서 있던 주소 그대로) 실패 표시가 없다', async ({
    page,
  }) => {
    await page.goto('/dev/table?data=sample');
    const target = row(page, 's1');
    await target.getByLabel('펼치기').click();
    await target.getByLabel('후보 2 고르기').check();
    await expect(target).toHaveAttribute('data-status', 'edited');
    await expect(target.locator('[data-column="emission"]')).toHaveText('3');
    await expect(page.locator('[data-calc-failed]')).toHaveCount(0);
    await expect(summary(page)).not.toContainText('계산 실패');
  });
});

// 아래는 모양 없는 컴포넌트(RowStack)를 들인 뒤에 더한 것이다. 카드 화면도 표와 같은 행 창을 쓴다:
// 행을 흐름대로 쌓고 묶음을 한꺼번에 내린다(위 「카드 화면: 펼친 카드 아래의 …」의 주석은 그 전의 놓는 법을 말한다).
test.describe('카드 화면(둘째 화면)의 행 창', () => {
  test('5,000행의 끝까지 스크롤하면 마지막 카드에 닿고, 그 아래 끝이 스크롤 상자 안에 있다', async ({
    page,
  }) => {
    await openFake(page, '&screen=cards');
    await expect(summary(page)).toHaveAttribute('data-total', String(ROWS));
    await expect(scrollBox(page)).toHaveAttribute(
      'aria-rowcount',
      String(ROWS),
    );
    const atTop = await page.locator('[data-row-id]').count();
    expect(atTop).toBeGreaterThan(5);
    expect(atTop).toBeLessThan(40);
    await expect(page.locator('[data-index="0"]')).toBeVisible();

    await scrollBox(page).evaluate((box) => (box.scrollTop = box.scrollHeight));
    const last = page.locator(`[data-index="${ROWS - 1}"]`);
    await expect(last).toBeVisible();
    await expect(last).toHaveAttribute('data-row-id', fake[ROWS - 1]!.id);
    await expect(last).toHaveAttribute('aria-rowindex', String(ROWS));
    await expect(page.locator('[data-index="0"]')).toHaveCount(0);
    expect(await page.locator('[data-row-id]').count()).toBeLessThan(40);
    // 끝에 닿은 뒤 잰 높이로 스크롤 길이가 다시 맞춰질 수 있다. 가라앉은 뒤에도 마지막 카드의 아래 끝이 상자 안에 있어야 한다.
    await expect
      .poll(async () => {
        const [boxBottom, rowBottom] = await Promise.all([
          scrollBox(page).evaluate((box) => box.getBoundingClientRect().bottom),
          last.evaluate((element) => element.getBoundingClientRect().bottom),
        ]);
        return rowBottom <= boxBottom + 1;
      })
      .toBe(true);
    // 그려진 카드들은 순서대로, 겹치지 않고 붙어서 쌓여 있다.
    const rects = await page.locator('[data-row-id]').evaluateAll((elements) =>
      elements.map((element) => ({
        index: Number((element as HTMLElement).dataset.index),
        top: element.getBoundingClientRect().top,
        bottom: element.getBoundingClientRect().bottom,
      })),
    );
    for (let i = 1; i < rects.length; i++) {
      expect(rects[i]!.index).toBe(rects[i - 1]!.index + 1);
      expect(
        Math.abs(rects[i]!.top - rects[i - 1]!.bottom),
      ).toBeLessThanOrEqual(1);
    }
  });

  test('키보드: End 로 마지막 카드까지 가고, 그 카드가 화면에 들어온다. 펼친 카드 속의 입력에서 친 글자는 지금 행을 옮기지 않는다', async ({
    page,
  }) => {
    await openFake(page, '&screen=cards');
    await scrollBox(page).focus();
    await page.keyboard.press('ArrowDown');
    await expect(page.locator('[data-active]')).toHaveAttribute(
      'data-index',
      '0',
    );
    await page.keyboard.press('End');
    await expect(page.locator('[data-active]')).toHaveAttribute(
      'data-index',
      String(ROWS - 1),
    );
    await expect(page.locator('[data-active]')).toBeInViewport();

    await page.keyboard.press('Home');
    await expect(page.locator('[data-active]')).toHaveAttribute(
      'data-index',
      '0',
    );
    const index = fake.findIndex(
      (r, i) => i < 8 && r.review.status === 'pending',
    );
    expect(index).toBeGreaterThanOrEqual(0);
    const card = page.locator(`[data-index="${index}"]`);
    await card.getByLabel('펼치기').click();
    await card.getByLabel('반려 사유').pressSequentially('jk');
    await expect(card.getByLabel('반려 사유')).toHaveValue('jk');
    await expect(page.locator('[data-active]')).toHaveAttribute(
      'data-index',
      '0',
    );
  });
});

// 펼친 행 속 입력 칸에서 End: 입력 칸 안의 End 는 행 창이 받지 않으므로(그쪽의 키다) 브라우저가 스스로 스크롤 상자를 끝으로 굴린다.
// ★ 펼친 높이가 스크롤 길이에 들어온 것을 확인한 뒤에 누른다. 펼친 행의 잰 높이는 화면이 그려진 뒤 한두 프레임 늦게 스크롤 길이에 들어오고
//   (크기 변화를 지켜보다 아는 길뿐이다), 브라우저의 「끝으로」는 누른 순간의 끝을 목표로 삼는다. 그래서 펼치자마자 기다림 없이 누르면
//   펼친 만큼 모자란 데서 멈췄다. 밴드 PL1 ③ 에서 고쳤다(RowFrame 이 다시 그려진 직후 높이를 잰다) — 기다림 없는 시험은 아래 「펼친 직후 …」.
test.describe('펼친 행 속 입력 칸에서 End', () => {
  const SMALL = 148;
  const small = makeFakeInput(SMALL).rows;
  for (const [name, extra, width] of [
    ['표', '', 1400],
    // 카드는 화면이 넓으면 펼쳐도 높이가 안 변한다(위의 「카드 화면: 펼친 카드 …」). 좁혀서 본다.
    ['카드', '&screen=cards', 480],
  ] as const) {
    test(`${name}: 스크롤이 끝에 닿고 마지막 행이 DOM 에 있다`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`/dev/table?data=fake&rows=${SMALL}${extra}`);
      // 반려 사유 칸이 있는(검토대기) 행 가운데 화면 위쪽에 있는 것.
      const index = small.findIndex(
        (r, i) => i < 8 && r.review.status === 'pending',
      );
      expect(index).toBeGreaterThanOrEqual(0);
      const target = page.locator(`[data-index="${index}"]`);
      await expect(target).toBeVisible();
      const before = await scrollBox(page).evaluate((box) => box.scrollHeight);

      await target.getByLabel('펼치기').click();
      // 전제이자 기다림: 이 행은 펼치면 커지고(안 커지면 이 테스트는 아무것도 보지 않는다), 그 높이가 스크롤 길이에 들어왔다.
      await expect
        .poll(() => scrollBox(page).evaluate((box) => box.scrollHeight))
        .toBeGreaterThan(before + 30);
      await target.getByLabel('반려 사유').press('End');

      // 끝에 닿아 있다(스크롤이 가라앉을 때까지 묻는다. 모자란 데서 멈추면 끝내 참이 되지 않는다).
      await expect
        .poll(
          () =>
            scrollBox(page).evaluate(
              (box) => box.scrollHeight - box.clientHeight - box.scrollTop,
            ),
          { message: '스크롤이 끝에 닿아야 한다(남은 px)' },
        )
        .toBeLessThanOrEqual(1);
      const last = page.locator(`[data-index="${SMALL - 1}"]`);
      await expect(last).toBeVisible();
      const [boxBottom, rowBottom] = await Promise.all([
        scrollBox(page).evaluate((box) => box.getBoundingClientRect().bottom),
        last.evaluate((element) => element.getBoundingClientRect().bottom),
      ]);
      expect(rowBottom).toBeLessThanOrEqual(boxBottom + 1);
    });
  }
});

// 펼친 직후(기다림 없이) 입력 칸에서 End(sid:MARC-ISSUE-29, 밴드 PL1 ③). 위 시험과 같은 자리를 펼치자마자 누른다.
// 펼친 행의 잰 높이가 스크롤 길이에 늦게 들어오면(크기 변화를 지켜보다 아는 길뿐이면) 그 사이 누른 End 는 옛 끝에서 멈춘다.
// ★ 일부러 기다리지 않는다. CPU 를 6배 느리게 해(Chromium 개발자 도구 기능) 틈을 넓히고, 펼치기와 입력 칸 초점을 쪽 안에서 한 번에 한다
//   (단추를 누르고 입력 칸이 DOM 에 생기는 그 순간 MutationObserver 로 초점). 자동 조작의 기다림이 끼면 틈이 지나가 고치기 전에도 초록이 된다.
//   f832ce4 의 시험을 지금 주소(/dev/table)로 되살린 것이다.
test.describe('펼친 직후 입력 칸에서 End·휠(기다림 없음)', () => {
  const SMALL = 148;
  const small = makeFakeInput(SMALL).rows;
  // how: End = 입력 칸 안의 End, wheel = 스크롤 상자 위에서 휠을 크게 한 번(끝까지).
  // 휠 줄은 기준 코드에서도 초록이다(밴드 PL1 ③ 실측 3/3 — 휠 스크롤은 굴러가는 동안 늘어난 길이까지 따라가 틈에 걸리지 않는다).
  // 틈을 재는 시험이 아니라 고침이 휠을 망치지 않는지 본다. 다시 재기를 지키는 것은 End 줄이다.
  for (const [name, extra, width, how] of [
    ['표', '', 1400, 'End'],
    ['카드', '&screen=cards', 480, 'End'],
    ['표', '', 1400, 'wheel'],
    ['카드', '&screen=cards', 480, 'wheel'],
  ] as const) {
    test(`${name}·${how}: 스크롤이 끝에 닿고 마지막 행이 상자 안에 보인다`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`/dev/table?data=fake&rows=${SMALL}${extra}`);
      const index = small.findIndex(
        (r, i) => i < 8 && r.review.status === 'pending',
      );
      expect(index).toBeGreaterThanOrEqual(0);
      const target = page.locator(`[data-index="${index}"]`);
      await expect(target).toBeVisible();
      const before = await scrollBox(page).evaluate((box) => box.scrollHeight);
      // 휠은 마우스 아래 요소가 받는다. 감속 전에 상자 가운데로 옮겨 둔다.
      const area = (await scrollBox(page).boundingBox())!;
      await page.mouse.move(area.x + area.width / 2, area.y + area.height / 2);
      const devtools = await page.context().newCDPSession(page);
      await devtools.send('Emulation.setCPUThrottlingRate', { rate: 6 });
      await target.evaluate(
        (element) =>
          new Promise<void>((resolve) => {
            const focusWhenThere = () => {
              const input = element.querySelector<HTMLElement>(
                '[aria-label="반려 사유"]',
              );
              if (!input) return;
              observer.disconnect();
              input.focus();
              resolve();
            };
            const observer = new MutationObserver(focusWhenThere);
            observer.observe(element, { childList: true, subtree: true });
            element
              .querySelector<HTMLElement>('[aria-label="펼치기"]')!
              .click();
            focusWhenThere();
          }),
      );
      if (how === 'End') await page.keyboard.press('End');
      else await page.mouse.wheel(0, 100_000);
      await devtools.send('Emulation.setCPUThrottlingRate', { rate: 1 });

      // 전제: 이 행은 펼치면 커진다(펼치기가 안 되면 아래가 아무것도 보지 않고 초록이 된다).
      await expect
        .poll(() => scrollBox(page).evaluate((box) => box.scrollHeight))
        .toBeGreaterThan(before + 30);
      await expect
        .poll(
          () =>
            scrollBox(page).evaluate(
              (box) => box.scrollHeight - box.clientHeight - box.scrollTop,
            ),
          { message: '스크롤이 끝에 닿아야 한다(남은 px)' },
        )
        .toBeLessThanOrEqual(1);
      const last = page.locator(`[data-index="${SMALL - 1}"]`);
      await expect(last).toBeVisible();
      const [boxBottom, rowBottom] = await Promise.all([
        scrollBox(page).evaluate((box) => box.getBoundingClientRect().bottom),
        last.evaluate((element) => element.getBoundingClientRect().bottom),
      ]);
      expect(rowBottom).toBeLessThanOrEqual(boxBottom + 1);
    });
  }
});

// 표 화면의 접근성 구조. 머리글 줄이 grid 안의 첫 행이어야 한다(전에는 grid 밖에 떠 있었고, 행 수와 순서에 들어 있지 않았다).
// 브라우저가 실제로 만든 접근성 트리를 읽는다(Chromium 의 개발자 도구 기능). 요소의 속성만 보는 것은 jsdom 테스트가 한다.
test.describe('표의 접근성 구조', () => {
  interface AxNode {
    nodeId: string;
    ignored: boolean;
    role?: { value: string };
    name?: { value: string };
    childIds?: string[];
  }

  test('접근성 트리에서 grid 의 첫 행이 머리글 줄이고 그 칸은 columnheader 다. 자료 행은 그 뒤에 온다', async ({
    page,
  }) => {
    await page.goto('/dev/table?data=sample');
    await expect(page.locator('[data-row-id]').first()).toBeVisible();
    const devtools = await page.context().newCDPSession(page);
    const { nodes } = (await devtools.send('Accessibility.getFullAXTree')) as {
      nodes: AxNode[];
    };
    const byId = new Map(nodes.map((node) => [node.nodeId, node]));
    /** 접근성 트리에서의 자식. 무시되는 마디(역할 없는 div 등)는 건너뛰고 그 아래로 내려간다. */
    const children = (node: AxNode): AxNode[] =>
      (node.childIds ?? []).flatMap((id) => {
        const child = byId.get(id)!;
        return (
            child.ignored ||
              child.role?.value === 'generic' ||
              child.role?.value === 'none'
          ) ?
            children(child)
          : [child];
      });
    const rowsUnder = (node: AxNode): AxNode[] =>
      children(node).flatMap((child) =>
        child.role?.value === 'row' ? [child]
        : child.role?.value === 'rowgroup' ? rowsUnder(child)
        : [],
      );

    const grids = nodes.filter(
      (node) => !node.ignored && node.role?.value === 'grid',
    );
    expect(grids).toHaveLength(1);
    const rows = rowsUnder(grids[0]!);
    // 예시 8행 + 머리글 1줄. 트리 전체에서 행은 이것뿐이다(grid 밖에 뜬 행이 없다).
    expect(rows).toHaveLength(9);
    expect(
      nodes.filter((node) => !node.ignored && node.role?.value === 'row'),
    ).toHaveLength(9);

    const headerCells = children(rows[0]!);
    expect(headerCells.map((cell) => cell.role?.value)).toEqual(
      Array.from({ length: headerCells.length }, () => 'columnheader'),
    );
    expect(headerCells.length).toBeGreaterThan(3);
    expect(headerCells.map((cell) => cell.name?.value)).toContain(
      '배출량(tCO2eq)',
    );
    for (const dataRow of rows.slice(1))
      expect(
        children(dataRow).every((cell) => cell.role?.value === 'gridcell'),
      ).toBe(true);

    await expect(page.getByRole('grid')).toHaveAttribute('aria-rowcount', '9');
    await expect(page.locator('[data-row-id="s1"]')).toHaveAttribute(
      'aria-rowindex',
      '2',
    );
  });

  test('머리글 줄은 스크롤해도 제자리에 있고, 머리글의 칸과 행의 칸이 같은 세로줄에 놓인다', async ({
    page,
  }) => {
    await openFake(page);
    await expect(page.getByRole('grid')).toHaveAttribute(
      'aria-rowcount',
      String(ROWS + 1),
    );
    const header = page.getByRole('grid').getByRole('row').first();
    await expect(header).toHaveAttribute('aria-rowindex', '1');
    const place = () =>
      header.evaluate(
        (element) =>
          element.getBoundingClientRect().toJSON() as {
            top: number;
            left: number;
            width: number;
            height: number;
            bottom: number;
          },
      );
    const atTop = await place();
    // 머리글 줄 바로 아래에서 스크롤 상자가 시작한다.
    expect(
      await scrollBox(page).evaluate((box) => box.getBoundingClientRect().top),
    ).toBe(atTop.bottom);

    await scrollBox(page).evaluate((box) => (box.scrollTop = box.scrollHeight));
    const last = page.locator(`[data-index="${ROWS - 1}"]`);
    await expect(last).toBeVisible();
    await expect(last).toHaveAttribute('aria-rowindex', String(ROWS + 1));
    expect(await place()).toEqual(atTop);
    await expect(header).toBeInViewport({ ratio: 1 });

    // 머리글의 칸과 마지막 행의 칸: 왼쪽 끝과 너비가 칸마다 같다.
    const lefts = (target: typeof header, selector: string) =>
      target
        .locator(selector)
        .evaluateAll((cells) =>
          cells.map((cell) => [
            Math.round(cell.getBoundingClientRect().left),
            Math.round(cell.getBoundingClientRect().width),
          ]),
        );
    const headerCells = await lefts(header, '[role="columnheader"]');
    expect(headerCells.length).toBeGreaterThan(3);
    expect(await lefts(last, '[role="gridcell"]')).toEqual(headerCells);
  });
});
