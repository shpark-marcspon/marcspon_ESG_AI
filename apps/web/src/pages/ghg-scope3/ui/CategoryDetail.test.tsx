// @vitest-environment jsdom
// S3-09·S3-10 상세 시험(밴드 S3W2b ② — 발주서 §3 의 2): 카드 누름(C10 안 눌림) · 일부 실패 카드 · 상세 시트 셋 갈래 · 21 시트 머리 열 표 ·
// 생물기원 칸·띠·FCF · 표기 사본 0 · 1000배 안 함 · 검색·정렬·쪽 · [목록] 초점 · 늦은 답. 부품(ResultView)을 바로 그린다. 값은 지어낸 것.
// 밴드 S3W2c ①: 머리 열 표 = 발주서 S3W2c §1-5 「뒤 차례」 · 입력 열 칸(input — 옛 줄 빈 칸 · 에너지 열 셋 갈래 · 수·중량 단위) · 입력 글 검색 · 수 입력 열 정렬.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  FAKE_C3_NOTE,
  FAKE_C12_CODE,
  FAKE_C12_NAME,
  FAKE_FUEL,
  FAKE_GROUP_A,
  FAKE_GROUP_B,
  FAKE_SHEET_ERROR,
  activityRow,
  detailSheetName,
  energyRow,
  failedSheet,
  fakeDetailResult,
  fakeDoneResult,
  fakeInput,
  fakeRowFactor,
  fakeS3Q1Result,
  fakeScope3Server,
  json,
  portOf,
  processedSheet,
  purchaseRow,
  ruleGroupSteps,
  withoutInput,
} from '../../../entities/ghg-scope3/api/testing.ts';
import type { FakeRowEdit } from '../../../entities/ghg-scope3/api/testing.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { saveBlob } from '../../../shared/lib/saveBlob.ts';
import { ResultView } from './ResultView.tsx';
import { cellText, fcfText, windowFactorText } from './detailText.ts';

// S3Q1: [원본 다운로드]가 부르는 저장(브라우저 다운로드)을 가로챈다 — 이 파일의 다른 시험은 저장하지 않는다.
vi.mock('../../../shared/lib/saveBlob.ts', () => ({ saveBlob: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.mocked(saveBlob).mockClear();
});

const t = S3_TEXT;
type Body = Record<string, unknown>;

function show(result: Body) {
  const server = fakeScope3Server({
    runs: [{ id: 7, status: 'done', reportYear: 2025, result }],
  });
  render(
    <ResultView
      port={portOf(server)}
      runId="7"
      year={2025}
      onUpload={() => {}}
    />,
  );
  return server;
}
const cardOf = (id: string) =>
  screen
    .getAllByTestId('s3-result-card')
    .find((card) => card.getAttribute('data-category') === id)!;
const open = async (id: string) => {
  await screen.findByTestId('s3-result');
  fireEvent.click(within(cardOf(id)).getByRole('button'));
  return screen.findByTestId('s3-detail');
};
const headersOf = (table: HTMLElement) =>
  within(table)
    .getAllByRole('columnheader')
    .map((cell) => cell.textContent);
/** 시트 표의 데이터 열 머리(앞 체크·뒤 히스토리 열을 뺌 — 두 열은 아래 S3W3b 시험이 본다). 창 안 표는 headersOf. */
const dataHeadersOf = (table: HTMLElement) => headersOf(table).slice(1, -1);
const tableOf = (sheet: string) =>
  within(
    screen
      .getAllByTestId('s3-sheet')
      .find((one) => one.getAttribute('data-sheet') === sheet)!,
  ).getByRole('table');
const cellsOf = (table: HTMLElement, column: number) =>
  within(table)
    .getAllByTestId('s3-row')
    .map((row) => row.querySelectorAll('td')[column]!.textContent);
/** 머리 글로 열을 찾아 그 칸들(열 차례가 바뀌어도 단언이 열을 놓치지 않게 — S3W2c). */
const cellsBy = (table: HTMLElement, header: string) => {
  const at = headersOf(table).indexOf(header);
  if (at < 0) throw new Error(`머리 없음 ${header}`);
  return cellsOf(table, at);
};

/**
 * 21 시트 머리 열(발주서 S3W2c §1-5 「뒤 차례」 — 입력 열 포함, 서버에 없는 열 0). 배출량 열은 끝에 (tCO2eq).
 * 꼬리는 S3R3 Q6(e6 F1): 배출량 → 비율 → (생물기원) → 계수 → (FCF) → (출처). C11 은 머리 여덟(S3R3 Q4).
 */
const E = '온실가스 배출량(tCO2eq)';
const T = [E, '배출량 비율', '배출계수'];
const B = [E, '배출량 비율', '생물기원 CO2(tCO2eq)', '배출계수', 'FCF'];
const HEADERS: Record<string, string[]> = {
  c1: [
    '행',
    '국가',
    '사업장',
    '그룹명',
    '품목명',
    '연간지출금액(원)',
    ...T,
    '출처',
  ],
  C2: [
    '행',
    '국가',
    '사업장',
    '그룹명',
    '자산명',
    '연간취득금액(원)',
    ...T,
    '출처',
  ],
  c3: ['행', '연료·에너지명', '연간 사용량', ...T],
  'c4-1': ['행', '자재명/품목명', '연간운송량', '운송거리(km)', ...T],
  'c4-2': ['행', '국가', '사업장', '자재명/품목명', '연간운송금액', ...T],
  c5: ['행', '사업장명', '폐기물', '처리 방법', '연간처리량', ...B],
  'c6-1': [
    '행',
    '교통 수단',
    '인원수',
    '이동거리(km)',
    '왕복계수',
    '연간이동횟수',
    ...T,
  ],
  'c6-2': [
    '행',
    '국가',
    '출장주체',
    '출장항목',
    '인원수',
    '연간 지출 금액',
    ...T,
  ],
  c7: ['행', '교통수단', '이동거리(km)', '인원수', '연간근무일수', ...T],
  'c8-1': ['행', '국가', '임차자산명', '에너지 종류', '연간사용량', ...T],
  'c8-2': [
    '행',
    '국가',
    '임차자산명',
    '에너지 종류',
    '건물전체 면적',
    '사용 면적',
    '건물전체 연간사용량',
    ...T,
  ],
  'c8-3': [
    '행',
    '국가',
    '임차자산명',
    '에너지 종류',
    '건물전체 인원수',
    '자사 인원수',
    '건물전체 연간사용량',
    ...T,
  ],
  'c9-1': ['행', '운송수단', '제품명', '연간운송량', '운송거리(km)', ...T],
  'c9-2': ['행', '국가', '사업장', '제품명', '운송수단', '연간운송금액', ...T],
  c11: [
    '행',
    '제품명',
    '제품수량',
    '에너지명',
    '제품당 연간 에너지 사용량',
    '평균사용기간 (개월)',
    ...T,
  ],
  c12: ['행', '제품명', '판매량', '제품 중량', ...B],
  'c13-1': ['행', '국가', '임대자산명', '에너지 종류', '연간사용량', ...T],
  'c13-2': [
    '행',
    '국가',
    '임대자산명',
    '에너지 종류',
    '건물 전체 면적',
    '사용 면적',
    '건물전체 연간사용량',
    ...T,
  ],
  'c13-3': [
    '행',
    '국가',
    '임대자산명',
    '에너지 종류',
    '건물 전체 인원수',
    '자사 인원수',
    '건물전체 연간사용량',
    ...T,
  ],
  c14: [
    '행',
    '국가',
    '프랜차이즈 명',
    '가맹점 수',
    '연료 종류',
    '연료 사용량',
    ...T,
  ],
  c15: [
    '행',
    '기업명',
    '지분율(%)',
    '피투자 Scope 1',
    '피투자 Scope 2',
    '총 온실가스 배출량(tCO2eq)',
    '배출량 비율',
  ],
};
const CATEGORY_OF = (head: string) => `C${head.slice(1).split('-')[0]}`;

describe('카드 누름 — C10 빼고 열넷 · 일부 실패 카드', () => {
  it('C10 만 단추 없음 · 나머지 열넷은 단추 하나(빈·실패 카드도)', async () => {
    show(
      fakeDoneResult({
        sheets: [
          processedSheet('c1_x', 'Category1', [purchaseRow('1')]),
          failedSheet('c3_x', 'Category3'),
        ],
      }),
    );
    await screen.findByTestId('s3-result');
    for (const card of screen.getAllByTestId('s3-result-card')) {
      const buttons = within(card).queryAllByRole('button');
      expect(buttons.length, card.getAttribute('data-category')!).toBe(
        card.getAttribute('data-category') === 'C10' ? 0 : 1,
      );
    }
    expect(cardOf('C10').querySelector('[tabindex]')).toBeNull();
  });

  it('일부 실패: 성공 시트 합 + 「일부 시트 계산 실패」 · 다 실패: 「계산 실패」만', async () => {
    show(fakeDetailResult());
    await screen.findByTestId('s3-result');
    const c4 = cardOf('C4');
    expect(c4.getAttribute('data-state')).toBe('value');
    expect(within(c4).getByTestId('s3-card-total').textContent).toBe('6tCO2eq');
    expect(within(c4).getByTestId('s3-card-partial').textContent).toBe(
      t.result.cardPartial(1),
    );
    cleanup();
    show(
      fakeDoneResult({
        sheets: [
          failedSheet('c4-1_x', 'Category4'),
          failedSheet('c4-2_x', 'Category4'),
        ],
      }),
    );
    await screen.findByTestId('s3-result');
    expect(cardOf('C4').getAttribute('data-state')).toBe('failed');
    expect(within(cardOf('C4')).getByTestId('s3-card-total').textContent).toBe(
      t.result.cardFailed,
    );
    expect(within(cardOf('C4')).queryByTestId('s3-card-partial')).toBeNull();
  });
});

describe('일부 실패 경계(검증 권고 R3)', () => {
  it('성공 시트는 있으나 수가 없음 + 실패 시트 → 「-」 + 「일부 시트 계산 실패」(「계산 실패」 아님)', async () => {
    show(
      fakeDoneResult({
        sheets: [
          processedSheet('c4-1_x', 'Category4', [
            activityRow('transport_distance', null),
          ]),
          failedSheet('c4-2_x', 'Category4'),
        ],
      }),
    );
    await screen.findByTestId('s3-result');
    expect(cardOf('C4').getAttribute('data-state')).toBe('empty');
    expect(within(cardOf('C4')).getByTestId('s3-card-total').textContent).toBe(
      t.result.empty,
    );
    expect(
      within(cardOf('C4')).getByTestId('s3-card-partial').textContent,
    ).toBe(t.result.cardPartial(1));
  });
});

describe('상세 — 시트 셋 갈래 · 머리 열 표 · 서버 글 0', () => {
  it('C4: processed 표 + failed 까닭 글(서버 error 0) · C6: processed + empty 까닭 글', async () => {
    show(fakeDetailResult());
    const detail = await open('C4');
    const sheets = within(detail).getAllByTestId('s3-sheet');
    expect(sheets.map((s) => s.getAttribute('data-status'))).toEqual([
      'processed',
      'processed',
      'failed',
    ]);
    expect(sheets.map((s) => s.querySelector('h4')!.textContent)).toEqual([
      detailSheetName('c4-1'),
      detailSheetName('c4-2'),
      `${detailSheetName('c4-2')} 둘`,
    ]);
    expect(within(sheets[2]!).getByTestId('s3-sheet-reason').textContent).toBe(
      t.detail.sheetFailed,
    );
    expect(document.body.textContent).not.toContain(FAKE_SHEET_ERROR);
    expect(within(detail).getByTestId('s3-detail-partial').textContent).toBe(
      t.result.cardPartial(1),
    );
    fireEvent.click(within(detail).getByTestId('s3-detail-back'));
    const c6 = await open('C6');
    const six = within(c6).getAllByTestId('s3-sheet');
    expect(six.map((s) => s.getAttribute('data-status'))).toEqual([
      'processed',
      'processed',
      'empty',
    ]);
    expect(within(six[2]!).getByTestId('s3-sheet-reason').textContent).toBe(
      t.detail.sheetEmpty,
    );
  });

  it('21 시트 머리 열 = 발주서 §1-5 표(뺀 열 0) · 꼴은 시트 이름 앞머리로', async () => {
    show(fakeDetailResult());
    await screen.findByTestId('s3-result');
    const seen = new Set<string>();
    for (const category of [
      'C1',
      'C2',
      'C3',
      'C4',
      'C5',
      'C6',
      'C7',
      'C8',
      'C9',
      'C11',
      'C12',
      'C13',
      'C14',
      'C15',
    ]) {
      fireEvent.click(within(cardOf(category)).getByRole('button'));
      const detail = await screen.findByTestId('s3-detail');
      for (const [head, headers] of Object.entries(HEADERS)) {
        if (CATEGORY_OF(head) !== category) continue;
        expect(dataHeadersOf(tableOf(detailSheetName(head))), head).toEqual(
          headers,
        );
        seen.add(head);
      }
      fireEvent.click(within(detail).getByTestId('s3-detail-back'));
      await screen.findByTestId('s3-result');
    }
    expect(seen.size).toBe(21);
  });
});

describe('표 칸 — 표기 · 행 번호 · 비율 · 생물기원 · FCF · 추정', () => {
  it('C1: 행 번호(#n → 5·6·6-2) · 줄 그대로(그룹으로 합치지 않음) · 출처 · 지수 <0.001 · 비율은 시트 합', async () => {
    show(fakeDetailResult());
    await open('C1');
    const table = tableOf(detailSheetName('c1'));
    expect(cellsBy(table, '행')).toEqual(['5', '6', '6-2']);
    expect(cellsBy(table, '그룹명')).toEqual([
      FAKE_GROUP_A,
      FAKE_GROUP_B,
      FAKE_GROUP_A,
    ]);
    expect(cellsBy(table, '출처')).toEqual(['US EPA', 'US EPA', 'US EPA']);
    expect(cellsBy(table, E)).toEqual(['3', '1', '<0.001']);
    // 3 / 4.00001 · 1 / 4.00001 · 아주 작음
    expect(cellsBy(table, '배출량 비율')).toEqual(['75.0%', '25.0%', '0.0%']);
    expect(cellsBy(table, '배출계수')[0]).toBe('0.1 kgCO2e/KRW');
  });

  it('C1 이름 두 칸(그룹명·품목명)도 한 줄 — 접지 않고 표 안 가로 밀기(GX4 ①)', async () => {
    show(fakeDetailResult());
    await open('C1');
    const table = tableOf(detailSheetName('c1'));
    for (const header of ['그룹명', '품목명']) {
      const at = headersOf(table).indexOf(header);
      expect(at).toBeGreaterThan(0);
      for (const row of within(table).getAllByTestId('s3-row')) {
        const td = row.querySelectorAll('td')[at]!;
        expect(td.querySelector(':scope > .whitespace-nowrap')).not.toBeNull();
      }
    }
  });

  it('C1 출처: 코드 글자 0 · manual_title 만 「· 기타」 회색 글과 hover(뱃지 0) · none 은 빈 칸', async () => {
    const coded = (source: string, id: string) =>
      purchaseRow('1', `c1_x!${id}`, {
        factor: { title: null, value: '0.1', unit: null, source },
      });
    show(
      fakeDoneResult({
        sheets: [
          processedSheet('c1_x', 'Category1', [
            coded('manual_keyword', '2'),
            coded('manual_title', '3'),
            coded('none', '4'),
            coded('지어낸 코드', '5'),
          ]),
        ],
      }),
    );
    await open('C1');
    const table = tableOf('c1_x');
    expect(cellsBy(table, '출처')).toEqual([
      'US EPA',
      'US EPA · 기타',
      S3_TEXT.result.empty,
      S3_TEXT.result.empty,
    ]);
    // S3WS2: 출처 칸에는 뱃지가 없다 — 「· 기타」는 회색 글, hover 는 칸 글에.
    const other = within(table).getByText('· 기타');
    expect(other.className.split(' ')).toContain('text-text-tertiary');
    expect(other.parentElement?.title).toBe(
      '맞는 품목이 없어 ‘기타’ 계수로 셈했어요',
    );
    expect(within(table).queryByText('추정')).toBeNull();
  });
  it('C5: 생물기원 칸·띠(tCO2eq — kg 로 ×1000 0) · FCF %(×100) · 처리 방법 · 추정 표시', async () => {
    show(fakeDetailResult());
    const detail = await open('C5');
    expect(within(detail).getByTestId('s3-detail-biogenic').textContent).toBe(
      '1.75tCO2eq',
    );
    // [Figma] 띠 글 — 인자 둘(카드 합 20 · 생물기원 합 1.75), 단위 tCO2eq(ENT-264), brand 바탕(S3W2c ② Q9).
    const notice = within(detail).getByTestId('s3-biogenic-notice');
    expect(notice.textContent).toBe(
      '총 배출량 20 tCO2eq는 생물기원 CO2 1.75 tCO2eq를 제외한 값입니다. 매립 배출원은 재질과 무관하게 화석기원으로 전량 포함됩니다.',
    );
    expect(notice.getAttribute('data-tone')).toBe('important');
    // S3R3 Q7(e6 506 ②): 이 띠만 글자색 brand — 공용 important 의 orange-dark 는 빠지고 글자 꼴(pre-body-06)은 남는다.
    expect(notice.className.split(' ')).toContain('text-text-brand');
    expect(notice.className.split(' ')).not.toContain(
      'text-support-orange-dark',
    );
    expect(notice.className.split(' ')).toContain('text-style-pre-body-06');
    const table = tableOf(detailSheetName('c5'));
    expect(cellsBy(table, '처리 방법')).toEqual([
      '지어낸 처리',
      '지어낸 다른 처리',
    ]);
    expect(cellsBy(table, '생물기원 CO2(tCO2eq)')).toEqual(['1.25', '0.5']);
    expect(cellsBy(table, 'FCF')).toEqual(['10%', '10%']);
    expect(cellsBy(table, E)).toEqual(['5추정', '15']);
    expect(within(table).getAllByTestId('s3-estimate')).toHaveLength(1);
  });

  it('C11(S3R3 Q4·Q5): 제품당 연간 에너지 사용량 = 줄 activity(값 + 단위) · 평균사용기간 (개월) = input.useMonths · 키 열다섯 옛 줄은 「-」', async () => {
    show(fakeDetailResult());
    await open('C11');
    const old = tableOf(detailSheetName('c11'));
    expect(cellsBy(old, '평균사용기간 (개월)')).toEqual(['-']);
    expect(cellsBy(old, '제품당 연간 에너지 사용량')).toEqual(['1.5 kg']);
    expect(cellsBy(old, '제품수량')).toEqual(['7']);
    cleanup();
    const body = fakeDetailResult();
    const sheet = (body.sheets as { sheet: string; rows: Body[] }[]).find(
      (one) => one.sheet === detailSheetName('c11'),
    )!;
    sheet.rows = [
      { ...sheet.rows[0]!, input: fakeInput('c11') },
      {
        ...sheet.rows[0]!,
        rowId: `${detailSheetName('c11')}!4`,
        co2e: '0',
        input: fakeInput('c11', { useMonths: '지어낸 이삼년' }),
      },
    ];
    show(body);
    await open('C11');
    const table = tableOf(detailSheetName('c11'));
    expect(cellsBy(table, '평균사용기간 (개월)')).toEqual(['18', '-']);
  });

  it('C6-1: 편도 km 그대로 + 왕복계수 열(곱하지 않음) · C15 계수 열 0 · C12 생물기원', async () => {
    show(fakeDetailResult());
    await open('C6');
    const table = tableOf(detailSheetName('c6-1'));
    expect(cellsBy(table, '이동거리(km)')).toEqual(['300']);
    expect(cellsBy(table, '왕복계수')).toEqual(['2']);
    // 수단 칸은 코드(bus) 대신 이름표(GX3 ④). 짧은 칸은 한 줄, 이름 칸만 접는다(GX3 ②).
    const label = within(table).getByText('버스');
    expect(within(table).queryByText('bus')).toBeNull();
    expect(label.closest('.whitespace-nowrap')).not.toBeNull();
    expect(
      within(table).getByText('300').closest('.whitespace-nowrap'),
    ).not.toBeNull();
    // 검색은 화면 글자(이름표)로 찾는다(값 파일 GX3 ④).
    fireEvent.change(
      screen.getByRole('textbox', { name: t.detail.searchLabel }),
      { target: { value: '버스' } },
    );
    expect(
      within(tableOf(detailSheetName('c6-1'))).getByText('버스'),
    ).toBeTruthy();
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    const c12 = await open('C12');
    expect(within(c12).getByTestId('s3-detail-biogenic').textContent).toBe(
      '0.75tCO2eq',
    );
  });
});

/** C1 한 시트에 n 줄(그룹 가·나 번갈아, co2e 1…n). */
function longC1(n: number): Body {
  const rows = Array.from({ length: n }, (_, i) =>
    purchaseRow(String(i + 1), `c1_x!${i + 2}`, {
      group: {
        ...(purchaseRow('0').group as Body),
        name: i % 2 === 0 ? FAKE_GROUP_A : FAKE_GROUP_B,
      },
    }),
  );
  return fakeDoneResult({
    sheets: [processedSheet('c1_x', 'Category1', rows)],
  });
}

describe('검색 · 정렬 · 쪽(검색·정렬 뒤에 쪽)', () => {
  it('51 줄이면 쪽 둘 · 50 이면 쪽 나눔 0', async () => {
    show(longC1(51));
    await open('C1');
    expect(screen.getAllByTestId('s3-row')).toHaveLength(50);
    expect(screen.getByTestId('s3-page').textContent).toBe(
      t.detail.pageStatus(1, 2),
    );
    fireEvent.click(screen.getByRole('button', { name: t.detail.nextPage }));
    expect(screen.getAllByTestId('s3-row')).toHaveLength(1);
    cleanup();
    show(longC1(50));
    await open('C1');
    expect(screen.getAllByTestId('s3-row')).toHaveLength(50);
    expect(screen.queryByTestId('s3-pager')).toBeNull();
  });

  it('검색은 쪽 앞에서(전체 줄을 거름) · 검색하면 첫 쪽으로 · 맞는 줄 없음 글', async () => {
    show(longC1(120));
    await open('C1');
    fireEvent.click(screen.getByRole('button', { name: t.detail.nextPage }));
    expect(screen.getByTestId('s3-page').textContent).toBe(
      t.detail.pageStatus(2, 3),
    );
    fireEvent.change(
      screen.getByRole('textbox', { name: t.detail.searchLabel }),
      {
        target: { value: '묶음 나' },
      },
    );
    expect(screen.getByTestId('s3-page').textContent).toBe(
      t.detail.pageStatus(1, 2),
    );
    const table = tableOf('c1_x');
    expect(new Set(cellsBy(table, '그룹명'))).toEqual(new Set([FAKE_GROUP_B]));
    fireEvent.change(
      screen.getByRole('textbox', { name: t.detail.searchLabel }),
      {
        target: { value: '없는 낱말' },
      },
    );
    expect(screen.queryAllByTestId('s3-row')).toEqual([]);
    expect(screen.getByText(t.detail.noMatch)).toBeTruthy();
    // 지우면 옛 쪽(2)이 아니라 첫 쪽(가지 리뷰 L1).
    fireEvent.change(
      screen.getByRole('textbox', { name: t.detail.searchLabel }),
      { target: { value: '' } },
    );
    expect(screen.getByTestId('s3-page').textContent).toBe(
      t.detail.pageStatus(1, 3),
    );
  });

  it('정렬은 쪽 앞에서: 배출량 내림이면 첫 쪽 첫 줄이 전체 최대 · aria-sort', async () => {
    show(longC1(120));
    await open('C1');
    const table = tableOf('c1_x');
    const head = within(table).getByRole('columnheader', {
      name: /온실가스 배출량/,
    });
    fireEvent.click(within(head).getByRole('button'));
    expect(head.getAttribute('aria-sort')).toBe('ascending');
    fireEvent.click(within(head).getByRole('button'));
    expect(head.getAttribute('aria-sort')).toBe('descending');
    expect(cellsBy(tableOf('c1_x'), E)[0]).toBe('120');
    // 정렬을 바꾸면 첫 쪽으로(검증 권고 R4).
    fireEvent.click(screen.getByRole('button', { name: t.detail.nextPage }));
    expect(screen.getByTestId('s3-page').textContent).toBe(
      t.detail.pageStatus(2, 3),
    );
    fireEvent.click(within(head).getByRole('button'));
    expect(screen.getByTestId('s3-page').textContent).toBe(
      t.detail.pageStatus(1, 3),
    );
    // 행 칸은 정렬하지 않는다.
    const rowHead = within(table).getAllByRole('columnheader')[0]!;
    expect(within(rowHead).queryByRole('button')).toBeNull();
  });
});

describe('검색이 닿는 표 · 열 때 초점(감독 처분 R5·R6)', () => {
  it('R5: 글자 칸 없는 표(generic — S3W2c 뒤 21 꼴은 다 글 열이 있다)는 검색어가 있어도 줄 그대로 · 글자 칸 있는 표가 없으면 검색 칸 0', async () => {
    const odd = {
      ...activityRow('waste', '2', null, '지어낸 표!3'),
      kind: 'brand_new',
    };
    show(
      fakeDoneResult({
        sheets: [
          processedSheet('c4-1_x', 'Category4', [
            activityRow('transport_distance', '1', undefined, 'c4-1_x!3', {
              input: fakeInput('c4-1'),
            }),
          ]),
          processedSheet('지어낸 표', 'Category4', [odd]),
          processedSheet('지어낸 다른 표', 'Category5', [odd]),
        ],
      }),
    );
    await open('C4');
    fireEvent.change(
      screen.getByRole('textbox', { name: t.detail.searchLabel }),
      { target: { value: '없는 낱말' } },
    );
    expect(cellsOf(tableOf('지어낸 표'), 1)).toEqual(['3']);
    expect(within(tableOf('c4-1_x')).queryAllByTestId('s3-row')).toEqual([]);
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C5');
    expect(
      screen.queryByRole('textbox', { name: t.detail.searchLabel }),
    ).toBeNull();
  });

  it('R6: 열면 초점은 [목록] 단추 · 닫으면 누른 카드', async () => {
    show(fakeDetailResult());
    await open('C3');
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByTestId('s3-detail-back')),
    );
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(cardOf('C3')).getByRole('button'),
      ),
    );
  });
});

describe('지금 결과 덧씌움(S3W3a ②) — 꼴은 b·c, 속성과 합까지', () => {
  const edited = (rowEdits: FakeRowEdit[]) => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({
            sheets: [
              processedSheet('c1_x', 'Category1', [
                purchaseRow('1', 'c1_x!2'),
                purchaseRow('3', 'c1_x!3'),
                purchaseRow('5', 'c1_x!4'),
              ]),
            ],
          }),
          edits: rowEdits,
        },
      ],
    });
    render(
      <ResultView
        port={portOf(server)}
        runId="7"
        year={2025}
        onUpload={() => {}}
      />,
    );
  };

  it('제외 줄: 표에 남고 data-excluded · 고친 줄: data-edited 와 고친 값', async () => {
    edited([
      { rowId: 'c1_x!2', category: 'C1', excluded: true },
      { rowId: 'c1_x!3', category: 'C1', factor: fakeRowFactor() },
    ]);
    const detail = await open('C1');
    const rows = within(detail).getAllByTestId('s3-row');
    expect(rows).toHaveLength(3);
    expect(rows[0]!.getAttribute('data-excluded')).toBe('true');
    expect(rows[0]!.getAttribute('data-edited')).toBeNull();
    expect(rows[1]!.getAttribute('data-edited')).toBe('true');
    expect(rows[1]!.getAttribute('data-excluded')).toBeNull();
    expect(rows[1]!.textContent).toContain('7.25');
    expect(rows[2]!.getAttribute('data-excluded')).toBeNull();
  });

  it('머리 합(서버)과 덧씌운 표 합의 표기가 같다', async () => {
    edited([
      { rowId: 'c1_x!2', category: 'C1', excluded: true },
      { rowId: 'c1_x!3', category: 'C1', factor: fakeRowFactor() },
    ]);
    const detail = await open('C1');
    expect(within(detail).getByTestId('s3-detail-total').textContent).toBe(
      '12.25tCO2eq',
    );
  });

  it('applied 사건 줄은 본문 값 · data-edited 없음', async () => {
    edited([
      {
        rowId: 'c1_x!3',
        category: 'C1',
        factor: fakeRowFactor({ choice: 'applied', co2e: '3' }),
      },
    ]);
    const detail = await open('C1');
    const rows = within(detail).getAllByTestId('s3-row');
    expect(rows[1]!.getAttribute('data-edited')).toBeNull();
    expect(within(detail).getByTestId('s3-detail-total').textContent).toBe(
      '9tCO2eq',
    );
  });
});

describe('[목록] · 초점 · 늦은 답', () => {
  it('[목록] → 카드 목록, 초점은 연 카드 단추로', async () => {
    show(fakeDetailResult());
    const detail = await open('C8');
    expect(within(detail).getAllByTestId('s3-sheet')).toHaveLength(3);
    fireEvent.click(within(detail).getByTestId('s3-detail-back'));
    await screen.findByTestId('s3-result');
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(cardOf('C8')).getByRole('button'),
      ),
    );
  });

  it('runId 가 바뀌면 상세가 닫히고 그 결과의 목록(늦은 답은 버림)', async () => {
    const server = fakeScope3Server({
      runs: [
        { id: 5, status: 'done', reportYear: 2025, result: fakeDetailResult() },
        {
          id: 4,
          status: 'done',
          reportYear: 2024,
          result: fakeDoneResult({
            sheets: [processedSheet('c1_y', 'Category1', [purchaseRow('9')])],
          }),
        },
      ],
    });
    const port = portOf(server);
    const { rerender } = render(
      <ResultView port={port} runId="5" year={2025} onUpload={() => {}} />,
    );
    await open('C1');
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override['GET /inventory/scope3/runs/4/result'] = [
      () => gate.then(() => json(200, fakeDoneResult())),
    ];
    rerender(
      <ResultView port={port} runId="4" year={2024} onUpload={() => {}} />,
    );
    expect(screen.queryByTestId('s3-detail')).toBeNull();
    release();
    await screen.findByTestId('s3-result');
    expect(screen.queryByTestId('s3-detail')).toBeNull();
  });

  it('모르는 kind 줄은 행·배출량만(화면이 죽지 않음)', async () => {
    show(
      fakeDoneResult({
        sheets: [
          processedSheet('c5_x', 'Category5', [
            {
              ...activityRow('waste', '2', '0.5', 'c5_x!3'),
              kind: 'brand_new',
            },
          ]),
        ],
      }),
    );
    await open('C5');
    const table = tableOf('c5_x');
    expect(cellsBy(table, '행')).toEqual(['3']);
    expect(cellsBy(table, E)).toEqual(['2']);
    expect(cellsBy(table, '처리 방법')).toEqual([t.result.empty]);
    // basic 줄도 입력 열은 그린다(S3W2c Q1 — 가짜 기본 input).
    expect(cellsBy(table, '사업장명')).toEqual(['지어낸 사업장']);
  });
});

describe('입력 열(S3W2c ① — 결과 줄 input · sid:MARC-ENT-539)', () => {
  const D = t.result.empty;

  it('C1: 국가·사업장·품목명은 input 글자 그대로 · null 은 「-」 · 옛 줄(칸 없음)은 입력 열만 「-」(다른 칸 그대로)', async () => {
    show(fakeDetailResult());
    await open('C1');
    const table = tableOf(detailSheetName('c1'));
    expect(cellsBy(table, '국가')).toEqual([
      '지어낸 나라 c1',
      '지어낸 나라 c1',
      D,
    ]);
    expect(cellsBy(table, '사업장')).toEqual(['지어낸 사업장 c1', D, D]);
    expect(cellsBy(table, '품목명')).toEqual([
      '지어낸 이름 c1',
      '지어낸 이름 c1',
      D,
    ]);
    expect(cellsBy(table, '그룹명')[2]).toBe(FAKE_GROUP_A);
    expect(cellsBy(table, E)[2]).toBe('<0.001');
    expect(document.body.textContent).not.toMatch(/다시 (계산|산정)/);
  });

  it('C6-2·C8-2·C9-2·C12·C15: 시트마다 그 처리기 키 · 수는 수 표기(오른쪽) · 중량은 weightUnit', async () => {
    show(fakeDetailResult());
    await open('C6');
    const six = tableOf(detailSheetName('c6-2'));
    expect(cellsBy(six, '출장주체')).toEqual(['지어낸 사업장 c6-2']);
    expect(cellsBy(six, '출장항목')).toEqual(['지어낸 수단 c6-2']);
    expect(cellsBy(six, '인원수')).toEqual(['3']);
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C8');
    const eight = tableOf(detailSheetName('c8-2'));
    expect(cellsBy(eight, '임차자산명')).toEqual(['지어낸 이름 c8-2']);
    expect(cellsBy(eight, '에너지 종류')).toEqual(['지어낸 에너지 c8-2']);
    expect(cellsBy(eight, '건물전체 면적')).toEqual(['120']);
    expect(cellsBy(eight, '사용 면적')).toEqual(['30']);
    const area =
      within(eight).getAllByRole('columnheader')[
        headersOf(eight).indexOf('건물전체 면적')
      ]!;
    expect(within(area).getByRole('button')).toBeTruthy();
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C9');
    const nine = tableOf(detailSheetName('c9-2'));
    expect(cellsBy(nine, '운송수단')).toEqual(['지어낸 수단 c9-2']);
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C12');
    const twelve = tableOf(detailSheetName('c12'));
    expect(cellsBy(twelve, '제품명')).toEqual(['지어낸 이름 c12']);
    expect(cellsBy(twelve, '판매량')).toEqual(['1,250']);
    expect(cellsBy(twelve, '제품 중량')).toEqual(['0.5 kg']);
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C15');
    expect(cellsBy(tableOf(detailSheetName('c15')), '기업명')).toEqual([
      '지어낸 이름 c15',
    ]);
  });

  it('에너지 열(Q3): input 의 energy · 옛 줄은 계수 이름 · input 있고 energy null 은 「-」', async () => {
    show(fakeDetailResult());
    await open('C13');
    expect(cellsBy(tableOf(detailSheetName('c13-1')), '에너지 종류')).toEqual([
      FAKE_FUEL,
    ]);
    expect(cellsBy(tableOf(detailSheetName('c13-1')), '국가')).toEqual([D]);
    expect(cellsBy(tableOf(detailSheetName('c13-2')), '에너지 종류')).toEqual([
      '지어낸 에너지 c13-2',
    ]);
    expect(cellsBy(tableOf(detailSheetName('c13-3')), '에너지 종류')).toEqual([
      D,
    ]);
    expect(cellsBy(tableOf(detailSheetName('c13-3')), '자사 인원수')).toEqual([
      '4',
    ]);
  });

  it('입력 글로 검색 · 수 입력 열로 정렬(옛 줄은 늘 뒤)', async () => {
    show(fakeDetailResult());
    await open('C1');
    fireEvent.change(
      screen.getByRole('textbox', { name: t.detail.searchLabel }),
      { target: { value: '사업장 C1' } },
    );
    expect(cellsBy(tableOf(detailSheetName('c1')), '행')).toEqual(['5']);
    cleanup();
    const sale = (sales: string | null, rowId: string) =>
      energyRow('product_eol', '1', '0', rowId, {
        input: sales === null ? null : fakeInput('c12', { sales }),
      });
    show(
      fakeDoneResult({
        sheets: [
          processedSheet('c12_x', 'Category12', [
            sale('20.0', 'c12_x!3'),
            sale(null, 'c12_x!4'),
            sale('5.0', 'c12_x!5'),
          ]),
        ],
      }),
    );
    await open('C12');
    const table = tableOf('c12_x');
    const head = within(table).getByRole('columnheader', { name: /판매량/ });
    fireEvent.click(within(head).getByRole('button'));
    expect(cellsBy(tableOf('c12_x'), '행')).toEqual(['5', '3', '4']);
    fireEvent.click(within(head).getByRole('button'));
    expect(cellsBy(tableOf('c12_x'), '행')).toEqual(['3', '5', '4']);
  });
});

describe('S3W2c ② — 띠 null · 검색 칸 · 꼴 틀린 input 줄(검증 권고 R1)', () => {
  it('띠: 합이 없으면 그 자리 「-」(단위 없이)', async () => {
    show(
      fakeDoneResult({
        sheets: [
          processedSheet('c12_x', 'Category12', [
            energyRow('product_eol', null, null, 'c12_x!3'),
          ]),
        ],
      }),
    );
    const detail = await open('C12');
    expect(within(detail).getByTestId('s3-biogenic-notice').textContent).toBe(
      '총 배출량 -는 생물기원 CO2 -를 제외한 값입니다. 매립 배출원은 재질과 무관하게 화석기원으로 전량 포함됩니다.',
    );
  });

  it('검색 칸: 자리글 「검색」[Figma] · 폭 최소 300', async () => {
    show(fakeDetailResult());
    await open('C1');
    const search = screen.getByRole('textbox', { name: t.detail.searchLabel });
    expect(search.getAttribute('placeholder')).toBe('검색');
    // className 은 SearchField 바깥 칸에 붙는다 — 그 칸이 검색 글칸을 품는다.
    expect(document.querySelector('.min-w-\\[300px\\]')?.contains(search)).toBe(
      true,
    );
    expect(document.querySelector('.w-60')).toBeNull();
  });

  it('꼴 틀린 input 줄은 입력 열만 「-」 — 줄의 다른 칸(그룹·배출량)은 그대로', async () => {
    show(
      fakeDoneResult({
        sheets: [
          processedSheet('c1_x', 'Category1', [
            purchaseRow('2', 'c1_x!3', {
              input: { ...fakeInput('c1'), extra: '지어낸' },
            }),
            purchaseRow('1', 'c1_x!4', { input: fakeInput('c1') }),
          ]),
        ],
      }),
    );
    await open('C1');
    const table = tableOf('c1_x');
    expect(cellsBy(table, '국가')).toEqual([t.result.empty, '지어낸 나라 c1']);
    expect(cellsBy(table, '품목명')).toEqual([
      t.result.empty,
      '지어낸 이름 c1',
    ]);
    expect(cellsBy(table, '그룹명')).toEqual(['지어낸 묶음', '지어낸 묶음']);
    expect(cellsBy(table, E)).toEqual(['2', '1']);
  });
});

describe('S3-12 그룹별 배출계수 창(밴드 S3W4 ②)', () => {
  const w = t.detail.factorWindow;
  const n = detailSheetName;
  const sheetRows = (sheet: string) =>
    within(
      screen
        .getAllByTestId('s3-sheet')
        .find((one) => one.getAttribute('data-sheet') === sheet)!,
    ).getAllByTestId('s3-row');
  const openerIn = (row: HTMLElement) =>
    within(row).getByTestId('s3-window-open');
  const windowOf = async (row: HTMLElement) => {
    fireEvent.click(openerIn(row));
    return screen.findByRole('dialog', { name: w.title });
  };
  const c1 = (rows: Body[]) =>
    fakeDoneResult({
      sheets: [processedSheet(n('c1'), 'Category1', rows)],
    });
  const c5 = (rows: Body[]) =>
    fakeDoneResult({
      sheets: [processedSheet(n('c5'), 'Category5', rows)],
    });
  const c12 = (rows: Body[]) =>
    fakeDoneResult({
      sheets: [processedSheet(n('c12'), 'Category12', rows)],
    });
  const named = { input: fakeInput('c5') };
  const biogenic = (cells: Body) => ({
    biogenic: {
      fossilCo2e: '1',
      biogenicCo2e: '0',
      fcf: null,
      note: null,
      ...cells,
    },
  });

  it('C1: 그룹명 칸만 단추 · AI 그룹 창에 별(aria·title) · 기준단위 원 · 출처 · 산식 · 계수 · 탄소기원 없음', async () => {
    show(fakeDetailResult());
    await open('C1');
    const [row] = sheetRows(n('c1'));
    expect(within(row!).getAllByTestId('s3-window-open')).toHaveLength(1);
    expect(openerIn(row!).textContent).toBe(FAKE_GROUP_A);
    const dialog = await windowOf(row!);
    const star = within(dialog).getByRole('img', { name: w.aiGroup });
    expect(star.getAttribute('title')).toBe(w.aiGroup);
    expect(within(dialog).getByRole('heading', { level: 2 }).textContent).toBe(
      w.title,
    );
    const basic = within(dialog).getByTestId('s3-window-basic');
    expect(within(basic).getByText(w.won)).toBeTruthy();
    expect(within(basic).getByText('US EPA')).toBeTruthy();
    expect(within(basic).getByText('지어낸 식')).toBeTruthy();
    expect(within(basic).queryByText(w.biogenicEmission)).toBeNull();
    expect(within(dialog).queryByTestId('s3-window-carbon')).toBeNull();
    const table = within(dialog).getByRole('table');
    expect(headersOf(table)).toEqual([
      '타이틀',
      '배출계수 (kg CO2e /원)',
      '출처',
    ]);
    expect(
      [...table.querySelectorAll('tbody td')].map((cell) => cell.textContent),
    ).toEqual(['지어낸 항목', '0.1', 'US EPA']);
  });

  it('계수 칸 표기: 분모가 머리와 같으면 수만 · 다르면(변환 실패 줄·빈 단위)·kgCO2 밖은 서버 단위 · 단위 null 은 수만 · 표 칸은 서버 글자 그대로', () => {
    const cell = (unit: string | null) =>
      ({ type: 'number', value: 0.25, unit }) as const;
    const won = { kind: 'won' } as const;
    const on = (unit: string | null) => ({ kind: 'server', unit }) as const;
    expect(windowFactorText(cell('kgCO2e/KRW'), won)).toBe('0.25');
    expect(windowFactorText(cell('kgCO2e/USD'), won)).toBe('0.25 kgCO2e/USD');
    expect(windowFactorText(cell('kgCO2eq/kg'), on('kg'))).toBe('0.25');
    expect(windowFactorText(cell('kgCO2eq/kg'), on('드럼'))).toBe(
      '0.25 kgCO2eq/kg',
    );
    expect(windowFactorText(cell('kgCO2eq/kg'), on(null))).toBe(
      '0.25 kgCO2eq/kg',
    );
    expect(windowFactorText(cell('tCO2eq/kg'), on('kg'))).toBe(
      '0.25 tCO2eq/kg',
    );
    expect(windowFactorText(cell(null), on('kg'))).toBe('0.25');
    // C3(GX4 ② — 감독 판단 안 A): 활동 kWh · 계수 kgCO2eq/kWh 줄은 창 칸이 숫자만(머리 「/kWh」가 단위를 말함).
    expect(
      windowFactorText(
        { type: 'number', value: 0.06819, unit: 'kgCO2eq/kWh' },
        on('kWh'),
      ),
    ).toBe('0.06819');
    expect(cellText(cell('kgCO2e/KRW'), 'factor')).toBe('0.25 kgCO2e/KRW');
  });

  it('FCF 표기: 표·창 같음 — 소수 한 자리까지·끝 0 뺌 · 0 · null · 비율은 한 자리 고정', () => {
    const cell = (value: number | null) =>
      ({ type: 'number', value, unit: null }) as const;
    expect([20, 20.5, 12.34, 0].map(fcfText)).toEqual([
      '20%',
      '20.5%',
      '12.3%',
      '0%',
    ]);
    expect(fcfText(null)).toBe('-');
    expect(
      [20, 20.5, 12.34, 0].map((one) => cellText(cell(one), 'fcf')),
    ).toEqual(['20%', '20.5%', '12.3%', '0%']);
    expect(cellText(cell(null), 'fcf')).toBe('-');
    expect(cellText(cell(20), 'share')).toBe('20.0%');
  });

  it('별 없음: 규칙 그룹(줄 origin 은 ai)·물러선 그룹', async () => {
    show(fakeDetailResult());
    await open('C1');
    const rows = sheetRows(n('c1'));
    for (const row of [rows[1]!, rows[2]!]) {
      const dialog = await windowOf(row);
      expect(within(dialog).queryByTestId('s3-ai-star')).toBeNull();
      fireEvent.click(within(dialog).getByRole('button', { name: w.close }));
      await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    }
  });

  it('보기 꼴: 추천·입력칸 0(가짜에 recommendations 가 있어도) · 제목 줄 단추는 닫기와 [수정] 둘(S3W3c2 — 수정 꼴은 FactorEdit.test)', async () => {
    show(c1([purchaseRow('1', `${n('c1')}!5`)]));
    await open('C1');
    const dialog = await windowOf(sheetRows(n('c1'))[0]!);
    expect(within(dialog).queryByText('지어낸 추천')).toBeNull();
    expect(
      within(dialog)
        .getAllByRole('button')
        .map((one) => one.getAttribute('aria-label') ?? one.textContent),
    ).toEqual([w.close, S3_TEXT.detail.factorEdit.edit]);
    expect(within(dialog).queryByRole('textbox')).toBeNull();
    expect(within(dialog).queryByRole('spinbutton')).toBeNull();
    expect(dialog.querySelector('input, select, textarea')).toBeNull();
  });

  it('출처: manual_title 은 표와 같은 꼴(「US EPA · 기타」 + title, 추정 뱃지 0) · none 은 「-」', async () => {
    const factor = purchaseRow('1').factor as Body;
    show(
      c1([
        purchaseRow('1', `${n('c1')}!5`, {
          factor: { ...factor, source: 'manual_title' },
        }),
        purchaseRow('1', `${n('c1')}!6`, {
          factor: { ...factor, source: 'none' },
        }),
      ]),
    );
    await open('C1');
    const rows = sheetRows(n('c1'));
    const dialog = await windowOf(rows[0]!);
    const basic = within(dialog).getByTestId('s3-window-basic');
    const hint = within(basic).getByTitle(t.detail.sourceEstimateHint);
    expect(hint.textContent).toBe(`US EPA ${t.detail.sourceOther}`);
    expect(within(dialog).queryByTestId('s3-estimate')).toBeNull();
    fireEvent.keyDown(dialog, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    const none = await windowOf(rows[1]!);
    const cells = none.querySelectorAll('tbody td');
    expect(cells[2]!.textContent).toBe('-');
  });

  it('C5: 이름 칸만 단추 · 별 없음 · 기준단위 서버 글자 · 탄소기원(생물기원 CO2·FCF 끝 0 뺀 %·note 글자) · 생물기원 산식 줄 「-」 · 출처 시트 글자', async () => {
    show(
      c5([
        activityRow('waste', '1', '0.5', `${n('c5')}!3`, {
          ...named,
          ...biogenic({ fcf: '0.01', note: '지어낸 소각 근거' }),
          origin: 'ai',
          distance: null,
          mode: null,
        }),
      ]),
    );
    await open('C5');
    const [row] = sheetRows(n('c5'));
    expect(within(row!).getAllByTestId('s3-window-open')).toHaveLength(1);
    expect(openerIn(row!).textContent).toBe('지어낸 이름 c5');
    const dialog = await windowOf(row!);
    expect(within(dialog).queryByTestId('s3-ai-star')).toBeNull();
    const basic = within(dialog).getByTestId('s3-window-basic');
    expect(within(basic).getByText('kg')).toBeTruthy();
    expect(
      within(basic).getByText(w.biogenicEmission).nextSibling?.textContent,
    ).toBe('-');
    const carbon = within(dialog).getByTestId('s3-window-carbon');
    expect(within(carbon).getByText(w.biogenic)).toBeTruthy();
    expect(within(carbon).getByTestId('s3-window-fcf').textContent).toBe('1%');
    expect(within(carbon).getByText('지어낸 소각 근거')).toBeTruthy();
    expect(headersOf(within(dialog).getByRole('table'))[1]).toBe(
      '배출계수 (kg CO2e /kg)',
    );
    // 갈음(K3): 구매 밖 출처는 안 고친 줄도 factor.sheet 글자 그대로.
    expect(dialog.querySelectorAll('tbody td')[2]!.textContent).toBe(
      '지어낸 시트',
    );
  });

  it('FCF: 0 은 「생물기원 CO2」·「0%」(null 아님) · null 은 둘 다 「-」', async () => {
    show(
      c5([
        activityRow('waste', '1', '0.5', `${n('c5')}!3`, {
          ...named,
          ...biogenic({ fcf: '0' }),
        }),
        activityRow('waste', '1', '0', `${n('c5')}!4`, {
          ...named,
          ...biogenic({ note: '해당없음' }),
        }),
      ]),
    );
    await open('C5');
    const rows = sheetRows(n('c5'));
    const zero = await windowOf(rows[0]!);
    const carbon = within(zero).getByTestId('s3-window-carbon');
    expect(within(carbon).getByText(w.biogenic)).toBeTruthy();
    expect(within(carbon).getByTestId('s3-window-fcf').textContent).toBe('0%');
    fireEvent.keyDown(zero, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    const none = await windowOf(rows[1]!);
    const empty = within(none).getByTestId('s3-window-carbon');
    expect(within(empty).queryByText(w.biogenic)).toBeNull();
    expect(within(empty).getByTestId('s3-window-fcf').textContent).toBe('-');
    expect(within(empty).getByText('해당없음')).toBeTruthy();
  });

  it('biogenic null 이면 탄소기원 구분·생물기원 산식 줄이 없다', async () => {
    show(c5([activityRow('waste', '1', undefined, `${n('c5')}!3`, named)]));
    await open('C5');
    const dialog = await windowOf(sheetRows(n('c5'))[0]!);
    expect(within(dialog).queryByTestId('s3-window-carbon')).toBeNull();
    expect(within(dialog).queryByText(w.biogenicEmission)).toBeNull();
  });

  it('C12: 빈 산식 「-」 · 계수 없는 줄 「배출계수가 없어요」 · 타이틀 없으면 「-」', async () => {
    const eol = (line: string, extra: Body) =>
      energyRow('product_eol', '1', '0.5', `${n('c12')}!${line}`, {
        input: fakeInput('c12'),
        ...extra,
      });
    show(
      c12([
        eol('3', { factor: null, formula: '' }),
        eol('4', {
          factor: {
            ...(energyRow('product_eol', '1').factor as Body),
            title: null,
          },
        }),
      ]),
    );
    await open('C12');
    const rows = sheetRows(n('c12'));
    const none = await windowOf(rows[0]!);
    const basic = within(none).getByTestId('s3-window-basic');
    expect(within(basic).getByText(w.emission).nextSibling?.textContent).toBe(
      '-',
    );
    expect(within(none).getByText(w.noFactor)).toBeTruthy();
    fireEvent.keyDown(none, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    const untitled = await windowOf(rows[1]!);
    expect(untitled.querySelectorAll('tbody td')[0]!.textContent).toBe('-');
  });

  it('기준단위가 없으면 값 「-」 · 머리는 단위 꼬리를 뺀다', async () => {
    const amount = activityRow('waste', '1').activity as Body;
    show(
      c5([
        activityRow('waste', '1', '0', `${n('c5')}!3`, {
          ...named,
          activity: { ...amount, unit: '', baseUnit: null },
        }),
      ]),
    );
    await open('C5');
    const dialog = await windowOf(sheetRows(n('c5'))[0]!);
    const basic = within(dialog).getByTestId('s3-window-basic');
    expect(within(basic).getByText(w.baseUnit).nextSibling?.textContent).toBe(
      '-',
    );
    expect(headersOf(within(dialog).getByRole('table'))[1]).toBe('배출계수');
  });

  it('여는 칸 밖은 단추 0: 옛 줄(이름 null)·basic 줄·다른 시트(critic B2)', async () => {
    show(
      fakeDoneResult({
        sheets: [
          processedSheet(n('c5'), 'Category5', [
            withoutInput(activityRow('waste', '1', '0.5', `${n('c5')}!3`)),
            {
              ...activityRow('waste', '1', '0.5', `${n('c5')}!4`, named),
              originSteps: null,
            },
          ]),
          processedSheet(n('c3'), 'Category3', [
            energyRow('fuel_energy', '1', undefined, `${n('c3')}!3`),
            energyRow('fuel_energy', '1', undefined, `${n('c3')}!4`, {
              input: fakeInput('빈 칸'),
            }),
          ]),
        ],
      }),
    );
    await open('C5');
    const rows = sheetRows(n('c5'));
    expect(within(rows[0]!).queryByTestId('s3-window-open')).toBeNull();
    expect(rows[0]!.textContent).toContain('-');
    expect(within(rows[1]!).queryByTestId('s3-window-open')).toBeNull();
    expect(rows[1]!.textContent).toContain('지어낸 이름 c5');
    // 갈음(S3W3c1, sid:MARC-ENT-585): 넷 밖 시트도 그 꼴의 이름 칸 하나가 연다 — 글이 빈 칸만 단추 0.
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C3');
    const fuel = sheetRows(n('c3'))[0]!;
    expect(within(fuel).getAllByTestId('s3-window-open')).toHaveLength(1);
    expect(within(fuel).getByTestId('s3-window-open').textContent).toBe(
      '지어낸 에너지',
    );
    expect(
      within(sheetRows(n('c3'))[1]!).queryByTestId('s3-window-open'),
    ).toBeNull();
  });

  it('C3 창: 기준단위 서버 단위 · 출처 시트 글자 · 탄소기원·별 0 · 계수 없는 줄은 없음 글', async () => {
    show(
      fakeDoneResult({
        sheets: [
          processedSheet(n('c3'), 'Category3', [
            energyRow('fuel_energy', '1', undefined, `${n('c3')}!3`),
            energyRow('fuel_energy', '1', undefined, `${n('c3')}!4`, {
              factor: null,
            }),
          ]),
        ],
      }),
    );
    await open('C3');
    fireEvent.click(openerIn(sheetRows(n('c3'))[0]!));
    let dialog = await screen.findByTestId('s3-factor-window');
    const basic = within(dialog).getByTestId('s3-window-basic');
    expect(within(basic).getByText(w.source).nextSibling?.textContent).toBe(
      '지어낸 시트',
    );
    expect(within(dialog).queryByTestId('s3-window-carbon')).toBeNull();
    expect(within(dialog).queryByTestId('s3-ai-star')).toBeNull();
    fireEvent.keyDown(dialog, { key: 'Escape' });
    await waitFor(() =>
      expect(screen.queryByTestId('s3-factor-window')).toBeNull(),
    );
    fireEvent.click(openerIn(sheetRows(n('c3'))[1]!));
    dialog = await screen.findByTestId('s3-factor-window');
    expect(within(dialog).getByText(w.noFactor)).toBeTruthy();
  });

  it('앞 글과 여는 칸이 다른 꼴: 제외 줄 앞 글은 앞 칸, 여는 칸은 단추 그대로 · 같은 꼴은 앞 글이 단추 밖', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({
            sheets: [
              processedSheet(n('c3'), 'Category3', [
                energyRow('fuel_energy', '1', undefined, `${n('c3')}!3`),
              ]),
              processedSheet(n('c4-2'), 'Category4', [
                activityRow(
                  'transport_spend',
                  '1',
                  undefined,
                  `${n('c4-2')}!3`,
                ),
              ]),
            ],
          }),
          edits: [
            { rowId: `${n('c3')}!3`, category: 'C3', excluded: true },
            { rowId: `${n('c4-2')}!3`, category: 'C4', excluded: true },
          ],
        },
      ],
    });
    render(
      <ResultView
        port={portOf(server)}
        runId="7"
        year={2025}
        onUpload={() => {}}
      />,
    );
    const lead = t.rowEdit.excludedLead;
    await open('C3');
    const same = openerIn(sheetRows(n('c3'))[0]!);
    expect(same.textContent).not.toContain(lead);
    expect(same.parentElement!.textContent).toContain(lead);
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C4');
    const other = openerIn(sheetRows(n('c4-2'))[0]!);
    expect(other.textContent).not.toContain(lead);
    expect(other.parentElement!.textContent).not.toContain(lead);
    expect(sheetRows(n('c4-2'))[0]!.textContent).toContain(lead);
  });

  it('C15: 표 위 한 줄 · 이름 칸은 글 그대로(창 0) · 다른 꼴에는 그 줄 없음', async () => {
    show(
      fakeDoneResult({
        sheets: [
          processedSheet(n('c15'), 'Category15', [
            energyRow('investment', '1', undefined, `${n('c15')}!3`),
          ]),
          processedSheet(n('c3'), 'Category3', [
            energyRow('fuel_energy', '1', undefined, `${n('c3')}!3`),
          ]),
          processedSheet(n('c12'), 'Category12', [
            energyRow('product_eol', '1', '0.5', `${n('c12')}!3`),
          ]),
        ],
      }),
    );
    await open('C15');
    expect(screen.getByTestId('s3-sheet-no-factor-edit').textContent).toBe(
      t.detail.noFactorEdit,
    );
    const row = sheetRows(n('c15'))[0]!;
    expect(row.textContent).toContain('지어낸 품목');
    expect(within(row).queryByTestId('s3-window-open')).toBeNull();
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C3');
    expect(screen.queryByTestId('s3-sheet-no-factor-edit')).toBeNull();
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C12');
    expect(screen.queryByTestId('s3-sheet-no-factor-edit')).toBeNull();
  });

  describe('고친 줄(S3W3c1 C5·C7)', () => {
    const start = (rows: Body[], rowEdits: FakeRowEdit[]) => {
      const server = fakeScope3Server({
        runs: [
          {
            id: 7,
            status: 'done',
            reportYear: 2025,
            result: c1(rows),
            edits: rowEdits,
          },
        ],
      });
      render(
        <ResultView
          port={portOf(server)}
          runId="7"
          year={2025}
          onUpload={() => {}}
        />,
      );
    };
    const id = `${n('c1')}!5`;
    const estimate = { origin: 'estimate' };
    const picked = fakeRowFactor({
      title: '지어낸 새 제목',
      value: '1e-05',
      source: 'usepa',
      unit: 'kgCO2e/KRW',
    });

    it('표: 계수·출처는 고친 값(코드 이름과 같은 글도 글 그대로) · 「추정」 뱃지 뺌 · 안 고친 줄은 그대로 · 이름 칸은 그대로', async () => {
      start(
        [
          purchaseRow('2', id, estimate),
          purchaseRow('1', `${n('c1')}!6`, estimate),
        ],
        [{ rowId: id, category: 'C1', factor: picked }],
      );
      await open('C1');
      const table = tableOf(n('c1'));
      expect(cellsBy(table, '배출계수')).toEqual([
        '0.00001 kgCO2e/KRW',
        '0.1 kgCO2e/KRW',
      ]);
      expect(cellsBy(table, '출처')[0]).toBe('usepa');
      const [fixed, plain] = sheetRows(n('c1'));
      expect(within(fixed!).queryByTestId('s3-estimate')).toBeNull();
      expect(within(plain!).getByTestId('s3-estimate')).toBeTruthy();
      expect(openerIn(fixed!).textContent).toBe('지어낸 묶음');
    });

    it('고친 출처 글이 갈래 값 usepa-estimate 와 같아도 표·창은 글자 그대로 · 「기타」 없음', async () => {
      start(
        [purchaseRow('2', id)],
        [
          {
            rowId: id,
            category: 'C1',
            factor: fakeRowFactor({ source: 'usepa-estimate' }),
          },
        ],
      );
      await open('C1');
      const table = tableOf(n('c1'));
      expect(cellsBy(table, '출처')[0]).toBe('usepa-estimate');
      expect(within(table).queryByText(t.detail.sourceOther)).toBeNull();
      fireEvent.click(openerIn(sheetRows(n('c1'))[0]!));
      const dialog = await screen.findByTestId('s3-factor-window');
      expect(
        within(dialog).getByTestId('s3-window-factor').textContent,
      ).toContain('usepa-estimate');
      expect(within(dialog).queryByText(t.detail.sourceOther)).toBeNull();
    });

    it('창: 제목·값·출처 한 벌 · 산식 「-」 · applied 줄은 본문 산식 그대로', async () => {
      const other = `${n('c1')}!6`;
      start(
        [purchaseRow('2', id), purchaseRow('1', other)],
        [
          { rowId: id, category: 'C1', factor: picked },
          {
            rowId: other,
            category: 'C1',
            factor: fakeRowFactor({ choice: 'applied', title: '딴 제목' }),
          },
        ],
      );
      await open('C1');
      fireEvent.click(openerIn(sheetRows(n('c1'))[0]!));
      let dialog = await screen.findByTestId('s3-factor-window');
      const body = within(dialog).getByTestId('s3-window-factor');
      expect(within(body).getByText('지어낸 새 제목')).toBeTruthy();
      expect(within(body).getByText('0.00001')).toBeTruthy();
      expect(within(body).getByText('usepa')).toBeTruthy();
      const basic = within(dialog).getByTestId('s3-window-basic');
      expect(within(basic).getByText(w.emission).nextSibling?.textContent).toBe(
        '-',
      );
      fireEvent.keyDown(dialog, { key: 'Escape' });
      await waitFor(() =>
        expect(screen.queryByTestId('s3-factor-window')).toBeNull(),
      );
      fireEvent.click(openerIn(sheetRows(n('c1'))[1]!));
      dialog = await screen.findByTestId('s3-factor-window');
      expect(within(dialog).queryByText('딴 제목')).toBeNull();
      expect(
        within(within(dialog).getByTestId('s3-window-basic')).getByText(
          w.emission,
        ).nextSibling?.textContent,
      ).toBe('지어낸 식');
    });
  });

  it('닫기: X·Esc 뒤 초점은 누른 칸(바깥 누름은 jsdom 이 못 재 e2e 가 본다)', async () => {
    show(
      c1([
        purchaseRow('2', `${n('c1')}!5`),
        purchaseRow('1', `${n('c1')}!6`, ruleGroupSteps),
      ]),
    );
    await open('C1');
    const opener = () => openerIn(sheetRows(n('c1'))[0]!);
    const first = opener();
    first.focus();
    const byX = await windowOf(sheetRows(n('c1'))[0]!);
    fireEvent.click(within(byX).getByRole('button', { name: w.close }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(first));
    const byEsc = await windowOf(sheetRows(n('c1'))[0]!);
    fireEvent.keyDown(byEsc, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(first));
    expect(opener()).toBe(first);
  });
});

// 밴드 RC1(sid:MARC-ENT-599 영향 줄 「Scope 3 카테고리 상세는 줄 클릭 없음」): 줄은 초점·커서·hover 0 · 줄(칸 단추 밖)을 눌러도 창 0.
describe('카테고리 상세 표 — 줄 클릭 없음(밴드 RC1)', () => {
  it('s3-row 에 tabindex·cursor-pointer·hover:bg- 0 · 줄을 눌러도 창 0', async () => {
    show(fakeDetailResult());
    await open('C1');
    const rows = within(tableOf(detailSheetName('c1'))).getAllByTestId(
      's3-row',
    );
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      expect(row.getAttribute('tabindex')).toBeNull();
      expect(row.className).not.toContain('cursor-pointer');
      expect(row.className).not.toContain('hover:bg-');
      fireEvent.click(row.querySelectorAll('td')[0]!);
      fireEvent.keyDown(row, { key: 'Enter' });
    }
    expect(screen.queryAllByRole('dialog')).toEqual([]);
  });
});

describe('S3Q1 ① [원본 다운로드](S3-09 — 값 파일 ①)', () => {
  const o = t.original;
  function showWithDocument(extra: Record<string, unknown> = {}) {
    const server = fakeScope3Server({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          documentId: 77,
          result: fakeDetailResult(),
        },
      ],
      ...extra,
    });
    render(
      <ResultView
        port={portOf(server)}
        runId="7"
        year={2025}
        onUpload={() => {}}
      />,
    );
    return server;
  }
  const originalButton = () =>
    screen.getByTestId('s3-original') as HTMLButtonElement;

  it('단추 무리 맨 앞 회색 sm·아이콘 0 · 누르면 그 실행에 올린 파일을 서버 이름으로 저장(창 없음)', async () => {
    const server = showWithDocument();
    await open('C1');
    const tools = screen.getByTestId('s3-detail-tools');
    const buttons = within(tools).getAllByRole('button');
    expect(buttons[0]).toBe(originalButton());
    expect(originalButton().textContent).toBe(o.button);
    expect(originalButton().querySelector('svg')).toBeNull();
    fireEvent.click(originalButton());
    await waitFor(() => expect(vi.mocked(saveBlob)).toHaveBeenCalledTimes(1));
    const [blob, name] = vi.mocked(saveBlob).mock.calls[0]!;
    expect(name).toBe('지어낸.xlsx');
    expect(blob.size).toBe(6);
    expect(server.count('GET /inventory/scope3/runs/7/original')).toBe(1);
    expect(screen.queryAllByRole('dialog')).toEqual([]);
    expect(screen.queryByTestId('s3-original-problem')).toBeNull();
  });

  it('받는 중엔 그 단추만 막고 「받는 중…」 · 두 번 눌러도 한 번만 · 다른 단추는 그대로', async () => {
    const server = showWithDocument();
    let release!: () => void;
    server.override['GET /inventory/scope3/runs/7/original'] = () =>
      new Promise<Response>((done) => {
        release = () =>
          done(new Response(new Uint8Array([1]), { status: 200 }));
      });
    await open('C1');
    fireEvent.click(originalButton());
    await waitFor(() => expect(originalButton().textContent).toBe(o.busy));
    expect(o.busy).toBe('받는 중…'); // e6 11-10: 다른 내려받기와 같은 말줄임표
    expect(originalButton().disabled).toBe(true);
    expect(
      (screen.getByTestId('s3-restore') as HTMLButtonElement).textContent,
    ).toBe(t.rowEdit.restore);
    fireEvent.click(originalButton());
    expect(server.count('GET /inventory/scope3/runs/7/original')).toBe(1);
    release();
    await waitFor(() => expect(originalButton().textContent).toBe(o.button));
    expect(originalButton().disabled).toBe(false);
    expect(vi.mocked(saveBlob)).toHaveBeenCalledTimes(1);
  });

  it('404 「원본 파일이 없어요」 · 그 밖 실패 「받지 못했어요」 — 표 위 줄 아래 alert · 다음 누름에 지운다', async () => {
    const server = showWithDocument();
    server.override['GET /inventory/scope3/runs/7/original'] = [
      () => json(404, { error: { code: 'NOT_FOUND', message: 'x' } }),
      () => json(503, { error: { code: 'STORAGE_UNAVAILABLE', message: 'x' } }),
      () => new Response(new Uint8Array([1]), { status: 200 }),
    ];
    await open('C1');
    fireEvent.click(originalButton());
    const problem = await screen.findByTestId('s3-original-problem');
    expect(problem.getAttribute('role')).toBe('alert');
    expect(problem.textContent).toBe(o.notFound);
    expect(problem.className).toContain('text-support-error-accent');
    expect(screen.getByTestId('s3-detail-tools').nextElementSibling).toBe(
      problem,
    );
    fireEvent.click(originalButton());
    await waitFor(() =>
      expect(screen.getByTestId('s3-original-problem').textContent).toBe(
        o.failed,
      ),
    );
    fireEvent.click(originalButton());
    await waitFor(() =>
      expect(screen.queryByTestId('s3-original-problem')).toBeNull(),
    );
    expect(vi.mocked(saveBlob)).toHaveBeenCalledTimes(1);
  });

  it('그 카테고리 지금 실행이 없는 카드(연도 상태 current null — runId null)는 단추 없음 · 원본 요청 0(검증 권고)', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          documentId: 77,
          result: fakeDetailResult(),
        },
      ],
    });
    const real = await server.send(
      new Request('http://test.local/api/inventory/scope3/years/2025'),
    );
    const year = (await real.json()) as {
      categories: Record<string, unknown>[];
    };
    const c1 = year.categories.find((one) => one.category === 'C1')!;
    expect(c1.current).not.toBeNull(); // 분모: 덮기 전엔 지금 실행이 있다
    year.categories = year.categories.map((one) =>
      one.category === 'C1' ? { ...one, current: null } : one,
    );
    server.override['GET /inventory/scope3/years/2025'] = () => json(200, year);
    render(
      <ResultView
        port={portOf(server)}
        runId="7"
        year={2025}
        onUpload={() => {}}
      />,
    );
    await screen.findByTestId('s3-result');
    fireEvent.click(within(cardOf('C1')).getByRole('button'));
    await screen.findByTestId('s3-detail');
    expect(screen.queryByTestId('s3-original')).toBeNull();
    expect(
      server.calls.filter((call) => call.path.endsWith('/original')),
    ).toEqual([]);
  });

  it('잠겨도 켬(읽기 — 툴팁으로 감싸지 않는다)', async () => {
    showWithDocument({ locks: [{ year: 2025, category: 'C1', runId: 7 }] });
    await open('C1');
    await waitFor(() =>
      expect(
        (screen.getByTestId('s3-exclude') as HTMLButtonElement).disabled,
      ).toBe(true),
    );
    expect(originalButton().disabled).toBe(false);
    expect(originalButton().parentElement?.tagName).not.toBe('SPAN');
    fireEvent.click(originalButton());
    await waitFor(() => expect(vi.mocked(saveBlob)).toHaveBeenCalledTimes(1));
  });
});

describe('S3Q1 ② C12 처리방법별 비중표 보기 · ③ 출처 글(값 파일 ②·③)', () => {
  const w = t.detail.factorWindow;
  const rowsIn = (sheet: string) =>
    within(
      screen
        .getAllByTestId('s3-sheet')
        .find((one) => one.getAttribute('data-sheet') === sheet)!,
    ).getAllByTestId('s3-row');
  const windowAt = async (sheet: string, index: number) => {
    fireEvent.click(
      within(rowsIn(sheet)[index]!).getByTestId('s3-window-open'),
    );
    return screen.findByRole('dialog', { name: w.title });
  };
  const cells = (row: HTMLElement) =>
    Array.from(row.querySelectorAll('td')).map((cell) => cell.textContent);

  it('5열 · 처리방법 셋(서버 차례) + 합계 줄 · 타이틀(제품명/코드)·출처는 첫 줄만(rowspan) · 비중 % · 합계는 서버 값', async () => {
    show(fakeS3Q1Result());
    await open('C12');
    const dialog = await windowAt('c12_지어낸', 0);
    const table = within(dialog).getByTestId('s3-window-treatments');
    expect(headersOf(table)).toEqual([
      w.columnTitle,
      w.columnTreatment,
      w.columnShare,
      w.columnFactor('kg'),
      w.columnSource,
    ]);
    const lines = within(table).getAllByTestId('s3-window-treatment');
    expect(lines.map(cells)).toEqual([
      [
        `${FAKE_C12_NAME}${FAKE_C12_CODE}`,
        '매립',
        '10%',
        '0.013',
        '폐기물 배출계수 표',
      ],
      ['소각', '12.5%', '3.4'],
      ['재활용', '77.5%', '0.0186'],
    ]);
    const title = lines[0]!.querySelector('td')!;
    expect(title.getAttribute('rowspan')).toBe('3');
    expect(within(title).getByTestId('s3-window-code').textContent).toBe(
      FAKE_C12_CODE,
    );
    expect(
      cells(within(table).getByTestId('s3-window-treatment-total')),
    ).toEqual(['', w.total, '100%', '0.5', '']);
  });

  it('보기만: 라디오·입력칸·[취소][저장] 0 · [수정]은 C12 막힘 글 그대로', async () => {
    show(fakeS3Q1Result());
    await open('C12');
    const dialog = await windowAt('c12_지어낸', 0);
    expect(within(dialog).queryAllByRole('radio')).toEqual([]);
    expect(within(dialog).queryAllByRole('textbox')).toEqual([]);
    expect(within(dialog).queryByText(t.detail.factorEdit.cancel)).toBeNull();
    expect(within(dialog).queryByText(t.detail.factorEdit.save)).toBeNull();
    expect(within(dialog).getByText(t.detail.noFactorEdit)).toBeTruthy();
  });

  it('코드 없는 줄은 타이틀 한 줄 · NaN 줄(390)은 비중·합계 「-」 · 옛 줄(칸 없음)은 지금 한 줄 표', async () => {
    show(fakeS3Q1Result());
    await open('C12');
    let dialog = await windowAt('c12_지어낸', 1);
    expect(within(dialog).queryByTestId('s3-window-code')).toBeNull();
    fireEvent.keyDown(dialog, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    dialog = await windowAt('c12_지어낸', 3);
    const table = within(dialog).getByTestId('s3-window-treatments');
    expect(
      cells(within(table).getAllByTestId('s3-window-treatment')[0]!)[2],
    ).toBe('-');
    expect(
      cells(within(table).getByTestId('s3-window-treatment-total')).slice(2, 4),
    ).toEqual(['-', '-']);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    dialog = await windowAt('c12_지어낸', 4);
    expect(within(dialog).queryByTestId('s3-window-treatments')).toBeNull();
    expect(
      within(dialog)
        .getByTestId('s3-window-factor')
        .querySelectorAll('tbody tr'),
    ).toHaveLength(1);
  });

  it('S3Q2(sid:MARC-ENT-599 · c3 11-11): 제품명이 빈 C12 줄도 회색 「이름 없음」 단추 · aria 「<n>번 줄 배출계수 보기」 · 누르면 창', async () => {
    show(fakeS3Q1Result());
    await open('C12');
    const opener = within(rowsIn('c12_지어낸')[2]!).getByTestId(
      's3-window-open',
    );
    expect(opener.textContent).toBe(w.noName);
    expect(opener.getAttribute('aria-label')).toBe(w.openAria('5'));
    expect(opener.getAttribute('aria-label')).toBe('5번 줄 배출계수 보기');
    expect(opener.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['text-text-tertiary', 'hover:underline']),
    );
    expect(opener.className.split(/\s+/)).not.toContain('text-text-secondary');
    const named = within(rowsIn('c12_지어낸')[0]!).getByTestId(
      's3-window-open',
    );
    expect(named.getAttribute('aria-label')).toBeNull();
    expect(named.className.split(/\s+/)).toContain('text-text-secondary');
    fireEvent.click(opener);
    const dialog = await screen.findByRole('dialog', { name: w.title });
    expect(within(dialog).getByTestId('s3-window-treatments')).toBeTruthy();
  });

  it('S3Q2: 처리방법 표 rowspan 두 칸(타이틀·출처)만 위 맞춤 + 위 여백 16 · 다른 칸 0', async () => {
    show(fakeS3Q1Result());
    await open('C12');
    const dialog = await windowAt('c12_지어낸', 0);
    const table = within(dialog).getByTestId('s3-window-treatments');
    const classes = (cell: Element) => cell.className.split(/\s+/);
    const spans = Array.from(table.querySelectorAll('td[rowspan]'));
    expect(spans).toHaveLength(2);
    for (const cell of spans)
      expect(classes(cell)).toEqual(
        expect.arrayContaining(['align-top', 'pt-4']),
      );
    for (const cell of table.querySelectorAll('td:not([rowspan])')) {
      expect(classes(cell)).not.toContain('align-top');
      expect(classes(cell)).not.toContain('pt-4');
    }
  });

  it('출처 칸: 서버 sourceText(C3 줄 비고) · 없으면 지금 꼴(시트 이름)', async () => {
    show(fakeS3Q1Result());
    await open('C3');
    let dialog = await windowAt('c3_지어낸', 0);
    expect(
      within(dialog).getByTestId('s3-window-factor').textContent,
    ).toContain(FAKE_C3_NOTE);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    dialog = await windowAt('c3_지어낸', 1);
    const text = within(dialog).getByTestId('s3-window-factor').textContent;
    expect(text).toContain('에너지_C3');
    expect(text).not.toContain(FAKE_C3_NOTE);
    expect(FAKE_FUEL).toBeTruthy();
  });
});

describe('상세 머리 — C3 「확인 필요 — 2차에서 보정」(밴드 S3N1)', () => {
  const body = () =>
    fakeDoneResult({
      sheets: [
        processedSheet('s1', 'Category1', [purchaseRow('12')]),
        processedSheet('s3', 'Category3', [energyRow('leased_asset', '3.5')]),
      ],
    });

  it('C3 상세 머리 이름 옆에 고정 안내 — 글 표 그대로 · 툴팁 0', async () => {
    show(body());
    const detail = await open('C3');
    const head = within(detail).getByTestId('s3-detail-card');
    const mark = within(head).getByTestId('s3-adjust-later');
    expect(mark.textContent).toBe(t.result.adjustLater);
    expect(mark.parentElement!.textContent).toBe(
      `${t.result.cards.C3} ${t.result.adjustLater}`,
    );
    expect(within(detail).getAllByTestId('s3-adjust-later')).toHaveLength(1);
    expect(mark.closest('[title]')).toBeNull();
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('C1 상세에는 없다', async () => {
    show(body());
    const detail = await open('C1');
    expect(within(detail).queryByTestId('s3-adjust-later')).toBeNull();
  });
});
