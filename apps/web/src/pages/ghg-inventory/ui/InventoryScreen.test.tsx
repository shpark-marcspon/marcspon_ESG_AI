// @vitest-environment jsdom
// S2 온실가스 데이터(밴드 W12-0b2 ③ 자리 → W12-1a ③ 리스트 — 발주서 §3 6). 진짜 입력 실어댑터 + 가짜 온실가스 서버(fakeSelectionOptions·fakeEntryOptions).
//   연도는 바깥 상태(경로 흉내 Harness)가 쥔다 — onYear 가 year prop 을 바꾼다.
//   초기 모달 조건(고른 잎 0 — 「해 없음」 아님)·확인·취소·연도 바꿈마다 · n개 · 회사 거절 두 역할 · 459(다시 읽기 실패 notice·판 그대로·
//   늦게 온 앞 해 답 버림) · 460(모달 Enter·닫히면 [인덱스 설정]으로 초점) · 저장됐어요.
//   W12-1a ③: 현황 카드(q 없는 base) · 배출범위 표(서버 years 머리·세로 합침·메모·추정·잠금·「-」) · 서버 검색(300ms 한 번·늦은 답 버림·
//   0 건·422 q·검색은 카드를 안 바꿈) · 숨김 단추 0(본문 안에서만).
import { useState } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  fakeEntryOptions,
  fakeGhgServer,
  fakeSelectionOptions,
  json,
  portsOf,
  refusal,
  unreachable,
} from '../../../entities/ghg/api/testing.ts';
import type { FakeGhgServerOptions } from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { EmissionCard, TONES, TOTAL_FIT, totalClass } from './EmissionCard.tsx';
import { InventoryScreen } from './InventoryScreen.tsx';

afterEach(cleanup);
beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

const words = GHG_TEXT.inventory;
const YEARS = [2026, 2025, 2024, 2023, 2022];
const ROWS = 'GET /inventory/scope12/rows';
const SAVE = (year: number) =>
  `PUT /inventory/scope12/index-selections/${year}`;

function setup(
  options: FakeGhgServerOptions = fakeSelectionOptions(),
  { operator = false, year = 2026, saved = false } = {},
) {
  const server = fakeGhgServer({ thisYear: 2026, ...options });
  const port = portsOf(server).entry;
  const onIndexSettings = vi.fn();
  const years: number[] = [];
  function Harness() {
    const [current, setCurrent] = useState(year);
    return (
      <InventoryScreen
        port={port}
        organization={portsOf(server).port}
        year={current}
        years={YEARS}
        operator={operator}
        saved={saved}
        onYear={(next) => {
          years.push(next);
          setCurrent(next);
        }}
        onIndexSettings={onIndexSettings}
      />
    );
  }
  render(<Harness />);
  return { server, port, onIndexSettings, years };
}

const settings = () =>
  screen.findByRole('button', { name: words.indexSettings });
/** S12-02a: 빈 해 = 빈 상태만(확인 창 0). */
const emptyOnly = async () => {
  const empty = await screen.findByTestId('inventory-empty');
  expect(screen.queryByRole('dialog')).toBeNull();
  return empty;
};
const notice = () => screen.getByTestId('inventory-notice').textContent;
const pickYear = (year: number) =>
  fireEvent.change(screen.getByRole('combobox', { name: words.yearLabel }), {
    target: { value: `${year}` },
  });

/** 리스트 응답 흉내(EntryRowsOut 꼴 — 지어낸 이름·글자). */
function line(
  nodeId: string,
  name: string,
  over: Record<string, unknown> = {},
  [source, activity] = ['지어낸 고정연소', '지어낸 액체연료'],
) {
  return {
    nodeId,
    path: ['Scope 1', source, activity, name],
    values: {},
    hasMemo: false,
    estimated: false,
    locked: false,
    ...over,
  };
}
function rowsOf(
  year: number,
  rows: ReturnType<typeof line>[],
  {
    years = [year - 2, year - 1, year],
    values = {} as Record<string, string | null>,
    decimals = 2,
  } = {},
) {
  return {
    year,
    years,
    decimals,
    unit: 'tCO2-eq',
    configured: true,
    scopes:
      rows.length === 0 ?
        []
      : [{ scopeId: '1', scopeName: 'Scope 1', values, rows }],
  };
}

describe('S2 자리 — 머리·초기 세팅 모달', () => {
  it('머리: 제목 「온실가스 데이터」 · 연도 다섯(올해부터) · [인덱스 설정] → S17 같은 연도 · 일괄 업로드 단추', async () => {
    const { onIndexSettings } = setup({
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    const button = await settings();
    expect(screen.getByRole('heading', { name: words.title })).toBeTruthy();
    const select = screen.getByRole('combobox', {
      name: words.yearLabel,
    }) as HTMLSelectElement;
    expect([...select.options].map((option) => option.value)).toEqual([
      '2026',
      '2025',
      '2024',
      '2023',
      '2022',
    ]);
    expect(select.value).toBe('2026');
    expect(
      screen.getByRole('button', { name: words.bulk.uploadOpen }),
    ).toBeTruthy();
    expect(screen.queryByTestId('toast')).toBeNull();
    fireEvent.click(button);
    expect(onIndexSettings).toHaveBeenCalledWith(2026);
  });

  it('고른 잎 ≥1 → 현황 카드 + 표(고른 잎마다 줄) · 모달 없음 · 빈 상태 없음', async () => {
    setup({ ...fakeSelectionOptions(), chosen: { 2026: ['20', '22'] } });
    expect(await screen.findByTestId('emission-card')).toBeTruthy();
    expect(screen.getByTestId('inventory-row-20')).toBeTruthy();
    expect(screen.getByTestId('inventory-row-22')).toBeTruthy();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.queryByTestId('inventory-empty')).toBeNull();
  });

  it('S12-02a 고른 잎 0 → 빈 상태 두 줄(시안 원문)만 · 확인 창 없음 · S17 안 감', async () => {
    const { onIndexSettings } = setup();
    const empty = await emptyOnly();
    expect(empty.textContent).toBe(`${words.emptyTitle}${words.emptyBody}`);
    expect(onIndexSettings).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(document.body); // 창이 초점을 가져가지 않는다
  });

  it('S12-02a 빈 해에서 [인덱스 설정] → 묻지 않고 바로 onIndexSettings(같은 연도) · 창 0', async () => {
    const { onIndexSettings } = setup(fakeSelectionOptions(), { year: 2025 });
    await emptyOnly();
    fireEvent.click(await settings());
    expect(onIndexSettings).toHaveBeenCalledWith(2025);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('S12-02a 빈 해의 [인덱스 설정]은 한 번 눌러 한 번 부름(확인 단계 없음)', async () => {
    const { onIndexSettings } = setup(fakeSelectionOptions(), { year: 2025 });
    await emptyOnly();
    fireEvent.click(await settings());
    expect(onIndexSettings).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('빈 선택 저장으로 해를 만든 뒤에도(고른 잎 0) 빈 상태만 — 창 없음', async () => {
    const server = fakeGhgServer({ thisYear: 2026, ...fakeSelectionOptions() });
    const port = portsOf(server).selection;
    expect((await port.save(2026, [])).kind).toBe('ok');
    expect(server.count(SAVE(2026))).toBe(1);
    render(
      <InventoryScreen
        port={portsOf(server).entry}
        organization={portsOf(server).port}
        year={2026}
        years={YEARS}
        onYear={vi.fn()}
        onIndexSettings={vi.fn()}
      />,
    );
    expect(await emptyOnly()).toBeTruthy();
  });

  it('연도 바꿈마다: 고른 해(2026 n개) → 2025(고른 0) 빈 상태만 → 2024 도 빈 상태만(창 0)', async () => {
    const { server, years } = setup({
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    await screen.findByTestId('emission-card');
    pickYear(2025);
    expect(years).toEqual([2025]);
    await emptyOnly();
    expect(server.count(ROWS)).toBe(2);
    expect(screen.queryByTestId('emission-card')).toBeNull();
    pickYear(2024);
    await waitFor(() => expect(server.count(ROWS)).toBe(3));
    expect(await emptyOnly()).toBeTruthy();
  });

  it('S12-04 저장 뒤 들어오면(saved) 공용 토스트 「저장됐어요」 하나(role status — 화면이 host)', async () => {
    setup(
      { ...fakeSelectionOptions(), chosen: { 2026: ['20'] } },
      { saved: true },
    );
    await settings();
    const [saved, ...more] = await screen.findAllByTestId('toast');
    expect(more).toHaveLength(0);
    expect(saved!.getAttribute('role')).toBe('status');
    expect(saved!.textContent).toBe(words.saved);
  });

  it('D10·D6(sid:MARC-ISSUE-468): [인덱스 설정]은 제목 줄이 아니라 연도 줄 오른쪽 · 「저장됐어요」는 연도 줄 밖 토스트(S12-04) · 연도는 공용 NativeSelect', async () => {
    setup(
      { ...fakeSelectionOptions(), chosen: { 2026: ['20'] } },
      { saved: true },
    );
    const button = await settings();
    const filters = screen.getByTestId('inventory-filters');
    expect(filters.contains(button)).toBe(true);
    const heading = screen.getByRole('heading', { name: words.title });
    const root = document.querySelector('[data-screen="ghg-inventory"]')!;
    const title = [...root.children].find((child) => child.contains(heading))!;
    expect(title.contains(button)).toBe(false);
    const saved = await screen.findByTestId('toast');
    expect(filters.contains(saved)).toBe(false);
    expect(root.contains(saved)).toBe(false); // 포털 — body 끝
    const year = within(filters).getByRole('combobox', {
      name: words.yearLabel,
    });
    expect(year.className).toContain('appearance-none');
  });
});

describe('S2 자리 — 실패·거절', () => {
  it('첫 읽기 실패 → 화면 자리 한 줄 + 다시 시도 → 읽힘', async () => {
    const server = fakeGhgServer({
      thisYear: 2026,
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    server.override[ROWS] = [unreachable];
    render(
      <InventoryScreen
        port={portsOf(server).entry}
        organization={portsOf(server).port}
        year={2026}
        years={YEARS}
        onYear={vi.fn()}
        onIndexSettings={vi.fn()}
      />,
    );
    const failure = await screen.findByTestId('load-failure');
    expect(failure.textContent).toContain(words.loadFailed);
    expect(
      screen.queryByRole('button', { name: words.indexSettings }),
    ).toBeNull();
    fireEvent.click(
      within(failure).getByRole('button', { name: GHG_TEXT.common.retry }),
    );
    expect(await screen.findByTestId('inventory-row-20')).toBeTruthy();
  });

  it('다시 읽기 실패(연도 바꿈) → 한 줄 notice · 판 그대로 · 모달 안 뜸 · 다음 바꿈에 읽히면 notice 걷음', async () => {
    const { server } = setup({
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    await screen.findByTestId('inventory-row-20');
    server.override[ROWS] = [unreachable];
    pickYear(2025);
    await waitFor(() => expect(notice()).toBe(words.reloadFailed));
    expect(screen.queryByTestId('load-failure')).toBeNull();
    expect(screen.getByTestId('inventory-row-20')).toBeTruthy();
    expect(screen.queryByRole('dialog')).toBeNull();
    pickYear(2024);
    expect(await emptyOnly()).toBeTruthy();
    expect(notice()).toBe('');
  });

  it('늦게 온 앞 해 답은 버린다: 2026 → 2025(느림, 고른 1) → 2024(고른 0) — 판은 2024', async () => {
    const { server } = setup({
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    await screen.findByTestId('inventory-row-20');
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[ROWS] = [
      async () => {
        await gate;
        return json(200, rowsOf(2025, [line('22', '지어낸 발전기')]));
      },
      () => json(200, { ...rowsOf(2024, []), configured: false }),
    ];
    pickYear(2025);
    pickYear(2024);
    await emptyOnly();
    await act(async () => {
      release();
      await gate;
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(screen.getByTestId('inventory-empty')).toBeTruthy();
    expect(screen.queryByTestId('inventory-row-22')).toBeNull();
    expect(
      (
        screen.getByRole('combobox', {
          name: words.yearLabel,
          hidden: true,
        }) as HTMLSelectElement
      ).value,
    ).toBe('2024');
  });

  it('회사 거절 두 역할: 첫 읽기 → 화면 자리 회사 글(고객사·운영 관리자) · 다시 읽기 → 한 줄', async () => {
    setup({ thisYear: 2026, company: 'COMPANY_AMBIGUOUS' });
    expect((await screen.findByTestId('company-refusal')).textContent).toBe(
      GHG_TEXT.company.ambiguous,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
    cleanup();
    setup({ thisYear: 2026, company: 'COMPANY_INACTIVE' }, { operator: true });
    expect((await screen.findByTestId('company-refusal')).textContent).toBe(
      GHG_TEXT.companyOperator.inactive,
    );
    cleanup();
    const { server } = setup({
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    await screen.findByTestId('inventory-row-20');
    server.override[ROWS] = [() => refusal(400, 'COMPANY_NOT_FOUND')];
    pickYear(2025);
    await waitFor(() => expect(notice()).toBe(GHG_TEXT.company.not_found));
    expect(screen.getByTestId('inventory-row-20')).toBeTruthy();
  });
});

const cells = (row: HTMLElement) =>
  within(row)
    .getAllByRole('cell')
    .map((cell) => cell.textContent);
const typeSearch = (text: string) =>
  fireEvent.change(screen.getByLabelText(words.searchLabel), {
    target: { value: text },
  });
const searched = (server: ReturnType<typeof fakeGhgServer>) =>
  server.calls.filter(
    (call) => call.path === '/inventory/scope12/rows' && call.query.has('q'),
  );

describe('S2 리스트(밴드 W12-1a ③) — 표·카드', () => {
  it('표 머리 = 배출원 유형·배출활동·자산/시설 유형·서버 years 세 해·단위·메모·추정치·잠금 · 값은 표시 반올림 글자 · 없는 해 「-」', async () => {
    setup(fakeEntryOptions(), { year: 2025 });
    const row = await screen.findByTestId('inventory-row-20');
    const table = row.closest('table')!;
    const head = words.head;
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((cell) => cell.textContent),
    ).toEqual([
      head.source,
      head.activity,
      head.facility,
      '2023',
      '2024',
      '2025',
      head.unit,
      head.memo,
      head.estimated,
      head.locked,
    ]);
    expect(cells(row).slice(3)).toEqual([
      '-',
      '7.25',
      '12.13',
      'tCO2-eq',
      words.memoChip,
      '',
      '',
    ]);
    expect(
      within(screen.getByTestId('inventory-scope-1')).getByRole('heading')
        .textContent,
    ).toBeTruthy();
  });

  it('GX2 S12-02: 묶음 칸(배출원 유형·배출활동) 머리 폭 150 · 글 상자 118 고정 · 오른쪽 선 · Scope 2 색 support-blue-subtle2', async () => {
    setup(fakeEntryOptions(), { year: 2025 });
    const row = await screen.findByTestId('inventory-row-20');
    const table = row.closest('table')!;
    const heads = within(table).getAllByRole('columnheader');
    for (const th of heads.slice(0, 2))
      expect((th as HTMLElement).style.width).toBe('150px');
    expect((heads[2] as HTMLElement).style.width).toBe('');
    const groups = [...row.querySelectorAll('td.align-top')];
    expect(groups).toHaveLength(2);
    for (const td of groups)
      expect(td.querySelector('span')!.className).toContain('w-[118px]');
    const outer = table.parentElement!;
    for (const name of [
      '[&_td.align-top]:border-r',
      '[&_td.align-top]:border-solid',
      '[&_td.align-top]:border-border-tertiary',
    ])
      expect(outer.className, name).toContain(name);
    expect(TONES[1]).toBe('text-support-blue-subtle2');
  });

  it('값 칸은 응답 decimals 로 표시 반올림(0·3 자리 — 검증 A6)', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    const one = (decimals: number) =>
      json(
        200,
        rowsOf(
          2025,
          [line('20', '지어낸 보일러', { values: { '2025': '2.5' } })],
          { decimals },
        ),
      );
    server.override[ROWS] = [() => one(0), () => one(3)];
    const row = await screen.findByTestId('inventory-row-20');
    expect(cells(row)[5]).toBe('3');
    pickYear(2026);
    await waitFor(() =>
      expect(cells(screen.getByTestId('inventory-row-20'))[5]).toBe('2.5'),
    );
  });

  it('3개년 머리는 서버 years 그대로(웹이 고른 해로 셈하지 않음)', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    server.override[ROWS] = () =>
      json(
        200,
        rowsOf(2025, [line('20', '지어낸 보일러')], {
          years: [2019, 2021, 2025],
        }),
      );
    const row = await screen.findByTestId('inventory-row-20');
    const names = within(row.closest('table')!)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(names.slice(3, 6)).toEqual(['2019', '2021', '2025']);
  });

  it('배출원 유형·배출활동 세로 합침(서버 차례 그대로) · 메모 칩 진함 · 추정 행 표식 · 잠긴 행 표식', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    server.override[ROWS] = () =>
      json(
        200,
        rowsOf(2025, [
          line('20', '지어낸 보일러', {
            hasMemo: true,
            estimated: true,
            locked: true,
          }),
          line('22', '지어낸 발전기'),
          line('23', '지어낸 난로', {}, ['지어낸 고정연소', '지어낸 기체연료']),
        ]),
      );
    const first = await screen.findByTestId('inventory-row-20');
    const [source, activity] = within(first).getAllByRole('cell');
    expect([
      source!.getAttribute('rowspan'),
      activity!.getAttribute('rowspan'),
    ]).toEqual(['3', '2']);
    expect(cells(screen.getByTestId('inventory-row-22'))[0]).toBe(
      '지어낸 발전기',
    );
    expect(cells(screen.getByTestId('inventory-row-23')).slice(0, 2)).toEqual([
      '지어낸 기체연료',
      '지어낸 난로',
    ]);
    const memo = (id: string) =>
      within(screen.getByTestId(`inventory-row-${id}`)).getByText(
        words.memoChip,
      );
    expect([
      memo('20').getAttribute('aria-label'),
      memo('22').getAttribute('aria-label'),
    ]).toEqual([words.memoOn, words.memoOff]);
    expect(memo('20').className).not.toBe(memo('22').className);
    expect(
      within(first).getByTestId('row-estimated').getAttribute('aria-label'),
    ).toBe(words.estimatedLabel);
    expect(
      within(screen.getByTestId('inventory-row-22')).queryByTestId(
        'row-estimated',
      ),
    ).toBeNull();
    const lock = within(first).getByTestId('row-locked');
    expect(lock.getAttribute('aria-label')).toBe(words.lockedLabel);
    expect(
      within(screen.getByTestId('inventory-row-22')).queryByTestId(
        'row-locked',
      ),
    ).toBeNull();
  });

  describe('S2 디자인 대조 1~6(밴드 W12-1b ③ — 판 S12-02_r1)', () => {
    const classes = (element: Element) =>
      (element.getAttribute('class') ?? '').split(/\s+/);
    const expectClasses = (element: Element, wanted: readonly string[]) =>
      expect(classes(element)).toEqual(expect.arrayContaining([...wanted]));
    const rowOf = async (id: string) => {
      const { server } = setup(fakeEntryOptions(), { year: 2025 });
      server.override[ROWS] = () =>
        json(
          200,
          rowsOf(2025, [
            line('20', '지어낸 보일러', {
              hasMemo: true,
              estimated: true,
              locked: true,
            }),
            line('22', '지어낸 발전기'),
          ]),
        );
      await screen.findByTestId('inventory-row-20');
      return within(screen.getByTestId(`inventory-row-${id}`));
    };

    it('1 추정 열: 모든 행 20px 물결 상자 · 추정/아님 색 · 행 바탕 칠 없음 · 칸 폭 92 · 뜻은 aria-label', async () => {
      const on = await rowOf('20');
      const off = within(screen.getByTestId('inventory-row-22'));
      const box = on.getByRole('img', { name: words.estimatedLabel });
      const plain = off.getByRole('img', { name: words.estimatedOff });
      for (const element of [box, plain]) {
        expectClasses(element, ['size-5', 'rounded-[2px]']);
        // W12-1c #7(Q9): S2·S3 가 같은 물결 부품(EstimatedMark.tsx).
        expect(
          element.querySelector('svg[data-mark="estimated-wave"]'),
        ).not.toBeNull();
        expect(element.querySelector('svg')!.getAttribute('stroke')).toBe(
          'currentColor',
        );
        expect(element.querySelectorAll('svg path')).toHaveLength(2);
        // W12-1d N4: 판 S12-03 `.f12b-est` path 둘 · 선 1.4(S3 와 같은 부품).
        expect(
          [...element.querySelectorAll('svg path')].map((d) =>
            d.getAttribute('d'),
          ),
        ).toEqual([
          'M4 8C5.49538 5.33333 8.49538 5.33333 10 8C11.4954 10.6667 14.5046 10.6667 16 8',
          'M4 12C5.49538 9.33333 8.50462 9.33333 10 12C11.4954 14.6667 14.5046 14.6667 16 12',
        ]);
        expect(element.querySelector('svg')!.getAttribute('stroke-width')).toBe(
          '1.4',
        );
        expect(element.textContent).toBe('');
      }
      expectClasses(box, ['bg-background-brand', 'text-text-brand']);
      expectClasses(plain, ['bg-button-white', 'text-text-tertiary']);
      const row = screen.getByTestId('inventory-row-20');
      expect(row.getAttribute('data-tone')).toBeNull();
      // 밴드 RC1: 줄이 누를 수 있게 되어 hover:·focus-visible: 바탕은 있다 — 쉬는 바탕(앞머리 없는 bg-)만 0.
      expect(
        row.className.split(/\s+/).filter((name) => name.startsWith('bg-')),
      ).toEqual([]);
      expect(row.querySelector('td')!.className).not.toContain('bg-');
      expect(
        screen
          .getAllByRole('columnheader', { name: words.head.estimated })[0]!
          .getAttribute('style'),
      ).toContain('92px');
    });

    it('2 「저장됐어요」 → S12-04 토스트: 성공 톤 토큰(e6 ⑤) · 연도 줄 [인덱스 설정] 앞자리 글 0 · 줄 간격 gap-2.5 그대로', async () => {
      setup(
        { ...fakeSelectionOptions(), chosen: { 2026: ['20'] } },
        { saved: true },
      );
      const button = await settings();
      const saved = await screen.findByTestId('toast');
      expectClasses(saved, [
        'bg-background-primary-inverse',
        'text-text-primary-inverse',
      ]);
      expect(button.previousElementSibling?.textContent ?? '').not.toBe(
        words.saved,
      );
      expectClasses(button.parentElement!, ['gap-2.5']);
    });

    it('3 잠금 열: 모든 행 자물쇠 · 작은 상자 · 잠김만 바탕 · 빨강 0 · 누름 동작 0', async () => {
      const on = await rowOf('20');
      const off = within(screen.getByTestId('inventory-row-22'));
      const locked = on.getByRole('img', { name: words.lockedLabel });
      const open = off.getByRole('img', { name: words.unlockedLabel });
      for (const element of [locked, open]) {
        expectClasses(element, ['p-0.5', 'rounded-control']);
        expect(element.querySelector('svg')).not.toBeNull();
        expect(element.getAttribute('class')).not.toContain('error');
        expect(element.closest('button')).toBeNull();
      }
      expectClasses(locked, ['bg-background-brand', 'text-text-brand']);
      expectClasses(open, ['text-text-tertiary']);
      expect(open.getAttribute('class')).not.toContain('bg-');
    });

    it('4 메모 칩: 높이 28 · 최소 폭 56 · 좌우 10 · full · 흰 바탕 1px · 12px · 없음 quaternary / 있음 secondary', async () => {
      const on = await rowOf('20');
      const off = within(screen.getByTestId('inventory-row-22'));
      const chip = on.getByRole('img', { name: words.memoOn });
      const empty = off.getByRole('img', { name: words.memoOff });
      for (const element of [chip, empty]) {
        expectClasses(element, [
          'h-7',
          'min-w-14',
          'px-2.5',
          'rounded-full',
          'border',
          'border-button-grey',
          'bg-button-white',
          'text-style-pre-caption-02',
        ]);
        expect(element.textContent).toBe(words.memoChip);
      }
      expectClasses(chip, ['text-text-secondary']);
      expectClasses(empty, ['text-text-quaternary']);
    });

    it('5 현황 카드: 고리 180 · 가운데 heading-02 + 「총배출량」 body-05 · 범례 이름 84 · 값 body-01 · 줄 사이 gap-0.5 · 칸 사이 gap-2', async () => {
      await rowOf('20');
      const ring = screen.getByTestId('emission-ring');
      expectClasses(ring.parentElement!, ['size-[180px]']);
      expectClasses(screen.getByTestId('emission-total'), [
        'text-style-pre-heading-02',
      ]);
      expectClasses(screen.getByTestId('emission-total-unit'), [
        'text-style-pre-heading-02',
      ]);
      expectClasses(screen.getByTestId('emission-total-label'), [
        'text-style-pre-body-05',
        'text-text-tertiary',
      ]);
      const item = screen.getByTestId('emission-1');
      expectClasses(item, ['gap-2']);
      expectClasses(item.parentElement!, ['gap-0.5']);
      const [, name, value, unit] = [...item.children];
      expectClasses(name!, [
        'w-[84px]',
        'text-style-pre-body-05',
        'text-text-secondary',
      ]);
      expectClasses(value!, ['text-style-pre-body-01', 'text-text-primary']);
      expectClasses(unit!, ['text-style-pre-body-05', 'text-text-tertiary']);
    });

    it('자산/시설 칸 단추: 이름이 비면 aria-label · 이름이 있으면 글이 이름(가지 리뷰)', async () => {
      const { server } = setup(fakeEntryOptions(), { year: 2025 });
      server.override[ROWS] = () =>
        json(200, rowsOf(2025, [line('20', '지어낸 보일러'), line('22', '')]));
      expect(
        (await screen.findByTestId('inventory-open-22')).getAttribute(
          'aria-label',
        ),
      ).toBe(words.openUnnamed);
      expect(
        screen.getByTestId('inventory-open-20').getAttribute('aria-label'),
      ).toBeNull();
    });

    it('6 [인덱스 설정]: 키트 단추 md = 높이 36(h-9)', async () => {
      setup({ ...fakeSelectionOptions(), chosen: { 2026: ['20'] } });
      expectClasses(await settings(), ['h-9']);
    });
  });

  it('현황 카드: 그 해 Scope 값·합(표시 반올림) · 고리 role=img 글 대체 · 접기/펼치기', async () => {
    setup(fakeEntryOptions(), { year: 2025 });
    const card = await screen.findByTestId('emission-card');
    expect(within(card).getByTestId('emission-total').textContent).toBe(
      '12.13',
    );
    expect(within(card).getByTestId('emission-1').textContent).toContain(
      '12.13',
    );
    expect(within(card).getByRole('img').getAttribute('aria-label')).toContain(
      '12.13',
    );
    fireEvent.click(
      within(card).getByRole('button', { name: words.card.collapse }),
    );
    expect(within(card).queryByTestId('emission-total')).toBeNull();
    fireEvent.click(
      within(card).getByRole('button', { name: words.card.expand }),
    );
    expect(within(card).getByTestId('emission-total')).toBeTruthy();
  });

  it('운영 관리자도 같은 화면(표·카드)', async () => {
    setup(fakeEntryOptions(), { year: 2025, operator: true });
    expect(await screen.findByTestId('inventory-row-20')).toBeTruthy();
    expect(screen.getByTestId('emission-card')).toBeTruthy();
  });

  it('1차 숨김: 본문 안에 시장기반·담당자·참고자료·Scope 3 없음 · 일괄 업로드·다운로드 단추는 있음(W12-5)', async () => {
    setup(fakeEntryOptions(), { year: 2025 });
    await screen.findByTestId('inventory-row-20');
    const body = document.querySelector(
      '[data-screen="ghg-inventory"]',
    )!.textContent!;
    for (const word of ['시장기반', '담당자', '참고자료', 'Scope 3'])
      expect(body).not.toContain(word);
    for (const name of [words.bulk.uploadOpen, words.bulk.downloadOpen])
      expect(screen.getByRole('button', { name })).toBeTruthy();
  });
});

describe('S2 리스트(밴드 W12-1a ③) — 서버 검색', () => {
  it('입력이 멈추고 한 번 q 로 보냄(마지막 글) · 표만 바뀜 · 0 건 → 「검색 결과가 없어요」 · 카드는 그대로(base) · 지우면 표 = base', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    await screen.findByTestId('inventory-row-20');
    typeSearch('없');
    typeSearch('없는');
    typeSearch('없는 이름');
    expect(searched(server)).toHaveLength(0);
    expect(await screen.findByTestId('inventory-search-empty')).toBeTruthy();
    expect(screen.getByTestId('inventory-search-empty').textContent).toContain(
      words.searchEmpty,
    );
    expect(searched(server).map((call) => call.query.get('q'))).toEqual([
      '없는 이름',
    ]);
    expect(screen.getByTestId('emission-total').textContent).toBe('12.13');
    typeSearch('보일러');
    expect(await screen.findByTestId('inventory-row-20')).toBeTruthy();
    typeSearch('');
    await waitFor(() =>
      expect(screen.queryByTestId('inventory-search-empty')).toBeNull(),
    );
    expect(screen.getByTestId('inventory-row-20')).toBeTruthy();
  });

  it('연도 읽기 중에 검색해도 새 해 base 는 버리지 않음 — 카드는 새 해(검증 B1)', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    await screen.findByTestId('inventory-row-20');
    expect(screen.getByTestId('emission-total').textContent).toBe('12.13');
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[ROWS] = [
      async () => {
        await gate;
        return json(
          200,
          rowsOf(2024, [line('20', '지어낸 보일러')], {
            values: { '2024': '3' },
          }),
        );
      },
      () => json(200, rowsOf(2024, [line('20', '지어낸 보일러')])),
      () => json(200, rowsOf(2024, [line('20', '지어낸 보일러')])),
    ];
    pickYear(2024);
    typeSearch('보일러');
    await waitFor(() => expect(searched(server)).toHaveLength(1));
    await act(async () => {
      release();
      await gate;
    });
    await waitFor(() =>
      expect(screen.getByTestId('emission-total').textContent).toBe('3'),
    );
  });

  it('검색은 입력이 멈추기 전(300ms 안)에는 보내지 않음(검증 A7)', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    await screen.findByTestId('inventory-row-20');
    typeSearch('보일러');
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 200));
    });
    expect(searched(server)).toHaveLength(0);
    await waitFor(() => expect(searched(server)).toHaveLength(1));
  });

  it('늦게 온 앞 검색 답은 새 답을 덮지 않는다', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    await screen.findByTestId('inventory-row-20');
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[ROWS] = [
      async () => {
        await gate;
        return json(200, rowsOf(2025, [line('22', '지어낸 발전기')]));
      },
      () => json(200, rowsOf(2025, [line('23', '지어낸 난로')])),
    ];
    typeSearch('발전기');
    await waitFor(() => expect(searched(server)).toHaveLength(1));
    typeSearch('난로');
    expect(await screen.findByTestId('inventory-row-23')).toBeTruthy();
    await act(async () => {
      release();
      await gate;
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(screen.getByTestId('inventory-row-23')).toBeTruthy();
    expect(screen.queryByTestId('inventory-row-22')).toBeNull();
  });

  it('422 fields.q → 검색 줄 아래 한 줄(aria-invalid) · 표 그대로 · 다시 실패(끊김) → 한 줄 notice · 판 그대로 · 회사 거절 → 회사 글', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    await screen.findByTestId('inventory-row-20');
    typeSearch('ㄱ'.repeat(101));
    expect(
      (await screen.findByTestId('inventory-search-error')).textContent,
    ).toBe(words.searchInvalid);
    expect(
      screen.getByLabelText(words.searchLabel).getAttribute('aria-invalid'),
    ).toBe('true');
    expect(screen.getByTestId('inventory-row-20')).toBeTruthy();
    server.override[ROWS] = [
      unreachable,
      () => refusal(400, 'COMPANY_INACTIVE'),
    ];
    typeSearch('보일');
    await waitFor(() => expect(notice()).toBe(words.reloadFailed));
    expect(screen.queryByTestId('load-failure')).toBeNull();
    expect(screen.getByTestId('inventory-row-20')).toBeTruthy();
    expect(screen.getByTestId('emission-card')).toBeTruthy();
    typeSearch('보일러');
    await waitFor(() => expect(notice()).toBe(GHG_TEXT.company.inactive));
    expect(screen.getByTestId('inventory-row-20')).toBeTruthy();
    // 검색이 다시 되면 한 줄을 걷는다(검증 A8).
    delete server.override[ROWS];
    typeSearch('보일러 ');
    await waitFor(() => expect(notice()).toBe(''));
  });

  it('연도를 바꾸면 그 해 base 를 읽고 검색어가 있으면 이어 표를 다시 읽음', async () => {
    const { server } = setup(
      {
        ...fakeEntryOptions(),
        chosen: { 2026: ['20'], 2025: ['20'], 2024: [] },
      },
      { year: 2025 },
    );
    await screen.findByTestId('inventory-row-20');
    typeSearch('보일러');
    await waitFor(() => expect(searched(server)).toHaveLength(1));
    pickYear(2026);
    await waitFor(() => expect(searched(server)).toHaveLength(2));
    expect(searched(server).at(-1)!.query.get('year')).toBe('2026');
  });
  it('검색어 있음 → 연도 바꿈 → 검색 다시 읽기 실패: 표는 새 해 base(머리 = 새 해 years) · 한 줄 notice(가지 리뷰 B1)', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    await screen.findByTestId('inventory-row-20');
    typeSearch('보일러');
    await waitFor(() => expect(searched(server)).toHaveLength(1));
    server.override[ROWS] = [
      () => json(200, rowsOf(2026, [line('20', '지어낸 보일러')])),
      unreachable,
    ];
    pickYear(2026);
    await waitFor(() => expect(notice()).toBe(words.reloadFailed));
    const heads = within(
      screen.getByTestId('inventory-row-20').closest('table')!,
    )
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(heads.slice(3, 6)).toEqual(['2024', '2025', '2026']);
  });

  it('검색 422 가 q 가 아닌 칸이면 한 줄 notice(검색 줄 아래 아님)', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    await screen.findByTestId('inventory-row-20');
    server.override[ROWS] = [
      () => refusal(422, 'VALIDATION_ERROR', { year: ['지어낸 연도'] }),
    ];
    typeSearch('보일러');
    await waitFor(() => expect(notice()).toBe(words.reloadFailed));
    expect(screen.queryByTestId('inventory-search-error')).toBeNull();
  });

  it('설정 안 된 해로 바꾸면 남은 검색어로 읽지 않음', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    await screen.findByTestId('inventory-row-20');
    typeSearch('보일러');
    await waitFor(() => expect(searched(server)).toHaveLength(1));
    pickYear(2024);
    expect(await emptyOnly()).toBeTruthy();
    expect(searched(server)).toHaveLength(1);
  });
});

describe('S2 → S3 상세(밴드 W12-1b ①)', () => {
  const openDetail = async () => {
    fireEvent.click(await screen.findByTestId('inventory-open-20'));
    return screen.findByTestId('entry-site-2');
  };

  it('자산/시설 칸이 단추 → 화면 안 모달(주소 바뀜 0 — year 콜백 0) · 잠긴 잎도 열림', async () => {
    const { years } = setup(fakeEntryOptions(), { year: 2025 });
    await openDetail();
    expect(
      document.querySelector('[data-screen="ghg-entry-detail"]'),
    ).not.toBeNull();
    expect(years).toEqual([]);
  });

  it('쓰기가 있었으면 닫을 때 S2 를 다시 읽는다', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    await openDetail();
    const reads = server.count(ROWS);
    fireEvent.click(
      within(screen.getByTestId('entry-site-2')).getByRole('button', {
        name: GHG_TEXT.entry.add,
      }),
    );
    expect(server.count(ROWS)).toBe(reads);
    const add = await screen.findByTestId('entry-add');
    fireEvent.click(
      within(add).getByRole('checkbox', {
        name: GHG_TEXT.entry.addPick('1호기'),
      }),
    );
    fireEvent.click(
      within(add).getByRole('button', { name: GHG_TEXT.entry.addOk }),
    );
    await screen.findByTestId('entry-row-n4');
    fireEvent.click(screen.getByTestId('entry-save'));
    await screen.findByTestId('toast');
    expect(server.count(ROWS)).toBe(reads);
    fireEvent.click(screen.getByRole('button', { name: GHG_TEXT.entry.close }));
    await waitFor(() => expect(server.count(ROWS)).toBe(reads + 1));
    await waitFor(() =>
      expect(
        document.querySelector('[data-screen="ghg-entry-detail"]'),
      ).toBeNull(),
    );
  });

  it('쓰기 없이 닫으면 다시 읽지 않고 초점이 연 단추로', async () => {
    const { server } = setup(fakeEntryOptions(), { year: 2025 });
    const opener = await screen.findByTestId('inventory-open-20');
    opener.focus();
    fireEvent.click(opener);
    await screen.findByTestId('entry-site-2');
    const reads = server.count(ROWS);
    fireEvent.click(screen.getByRole('button', { name: GHG_TEXT.entry.close }));
    await waitFor(() =>
      expect(
        document.querySelector('[data-screen="ghg-entry-detail"]'),
      ).toBeNull(),
    );
    expect(server.count(ROWS)).toBe(reads);
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  describe('줄 클릭(밴드 RC1, sid:MARC-ENT-599)', () => {
    const detail = () =>
      document.querySelectorAll('[data-screen="ghg-entry-detail"]');
    /** 20·22 는 한 묶음(묶인 칸은 20 의 줄 안), 24 는 혼자인 묶음(span 1 칸). */
    const grouped = (server: ReturnType<typeof setup>['server']) => {
      server.override[ROWS] = () =>
        json(
          200,
          rowsOf(2025, [
            line('20', '지어낸 보일러'),
            line('22', ''),
            line('24', '지어낸 버너', {}, ['지어낸 이동연소', '지어낸 도로']),
          ]),
        );
    };
    const valueCell = (row: HTMLElement) =>
      [...row.querySelectorAll('td')].find(
        (cell) =>
          !cell.classList.contains('align-top') &&
          !cell.querySelector('button'),
      )!;

    it('단추 밖 칸(값 칸)을 누르면 시설 단추와 같은 상세', async () => {
      setup(fakeEntryOptions(), { year: 2025 });
      const row = await screen.findByTestId('inventory-row-20');
      fireEvent.click(valueCell(row));
      await screen.findByTestId('entry-site-2');
      expect(detail()).toHaveLength(1);
    });

    it('줄에 초점 → Enter·Space 로 같은 상세 · 닫으면 초점이 그 줄', async () => {
      setup(fakeEntryOptions(), { year: 2025 });
      const row = await screen.findByTestId('inventory-row-20');
      row.focus();
      fireEvent.keyDown(row, { key: 'Enter' });
      await screen.findByTestId('entry-site-2');
      fireEvent.click(
        screen.getByRole('button', { name: GHG_TEXT.entry.close }),
      );
      await waitFor(() => expect(detail()).toHaveLength(0));
      await waitFor(() => expect(document.activeElement).toBe(row));
      fireEvent.keyDown(row, { key: ' ' });
      await screen.findByTestId('entry-site-2');
    });

    it('누를 수 있는 줄의 꼴: tabindex 0 · 이름 = 시설명(빈 이름은 openUnnamed) · DataTable 클래스', async () => {
      const { server } = setup(fakeEntryOptions(), { year: 2025 });
      grouped(server);
      const row = await screen.findByTestId('inventory-row-20');
      expect(row.getAttribute('tabindex')).toBe('0');
      expect(row.getAttribute('aria-label')).toBe('지어낸 보일러');
      expect(
        screen.getByTestId('inventory-row-22').getAttribute('aria-label'),
      ).toBe(words.openUnnamed);
      for (const name of [
        'cursor-pointer',
        'hover:bg-background-secondary',
        'focus-visible:outline-border-secondary',
      ])
        expect(row.classList.contains(name), name).toBe(true);
    });

    it('묶인 칸(묶음 첫 줄의 칸 · span 1 칸)은 눌러도 아무것도 안 엶 · 손가락 커서 아님', async () => {
      const { server } = setup(fakeEntryOptions(), { year: 2025 });
      grouped(server);
      const first = await screen.findByTestId('inventory-row-20');
      const alone = screen.getByTestId('inventory-row-24');
      const shared = [...first.querySelectorAll<HTMLElement>('td.align-top')];
      const single = [...alone.querySelectorAll<HTMLElement>('td.align-top')];
      expect(shared).toHaveLength(2);
      expect(shared[0]!.getAttribute('rowspan')).toBe('2');
      expect(single).toHaveLength(2);
      expect(single[0]!.getAttribute('rowspan')).toBeNull();
      for (const cell of [...shared, ...single]) {
        fireEvent.click(cell);
        fireEvent.click(cell.querySelector('span')!); // 칸 안 글 상자(Group)
      }
      expect(detail()).toHaveLength(0);
      // 묶인 칸의 꼴은 표 감싸개의 [&_td.align-top]: 꼴로 단다(DataTable 을 고치지 않음 — jsdom 은 그 변형을 셈하지 않아 클래스 글로 본다).
      const outer = first.closest('table')!.parentElement!;
      for (const name of [
        '[&_td.align-top]:cursor-default',
        '[&_td.align-top]:bg-background-primary',
        '[&_tr:has(>td.align-top:hover)]:bg-transparent',
      ])
        expect(outer.className.split(/\s+/), name).toContain(name);
      // 묶인 칸 뒤에도 줄은 그대로 열린다(창 하나).
      fireEvent.click(valueCell(first));
      await screen.findByTestId('entry-site-2');
      expect(detail()).toHaveLength(1);
    });
  });

  it('tabs 를 안 넘기면 Scope 탭 줄을 그리지 않는다(W12-1a 그대로)', async () => {
    setup(fakeEntryOptions(), { year: 2025 });
    await openDetail();
    const screenBody = document.querySelector<HTMLElement>(
      '[data-screen="ghg-inventory"]',
    )!;
    expect(screenBody.querySelector('[role="tablist"]')).toBeNull();
  });
});

describe('W12-1c ③ 확인 창 · 현황 카드 합계', () => {
  it('#19 확인 창(S2 최초 설정) → S12-02a 에서 걷음: 빈 해에 창(role=dialog)·그 글 0', async () => {
    setup();
    await emptyOnly();
    expect(
      screen.queryByRole('heading', { name: /인덱스를 설정할까요/ }),
    ).toBeNull();
    expect(document.querySelector('form')).toBeNull();
  });

  const rowsWith = (total: string) => ({
    year: 2026,
    years: [2024, 2025, 2026],
    decimals: 2,
    unit: 'tCO2-eq',
    configured: true,
    scopes: [
      {
        scopeId: '1',
        scopeName: '지어낸 범위',
        values: { '2026': total },
        rows: [],
      },
    ],
  });

  it('#21 J4 합계 — ≤10자 heading-02 · 11자 body-01 · 12자 이상 body-01 + 줄임표(117) + 전체 수 aria-label · 단위·「총배출량」 그대로', () => {
    const cases = [
      ['1234567.12', 'text-style-pre-heading-02', false],
      ['12345678.12', 'text-style-pre-body-01', false],
      ['123456789.12', 'text-style-pre-body-01', true],
    ] as const;
    for (const [total, look, cut] of cases) {
      render(<EmissionCard rows={rowsWith(total)} />);
      const shown = screen.getByTestId('emission-total');
      expect(shown.textContent).toBe(total);
      expect(shown.getAttribute('aria-label')).toBe(total);
      const names = shown.className.split(/\s+/);
      expect(names, total).toContain(look);
      expect(names.includes('truncate'), total).toBe(cut);
      if (cut) expect(names).toContain('max-w-[117px]');
      expect(screen.getByTestId('emission-total-unit').className).toContain(
        'text-style-pre-heading-02',
      );
      cleanup();
    }
    expect(TOTAL_FIT).toEqual({ heading: 10, body: 11 });
    expect(totalClass('-')).toContain('text-style-pre-heading-02');
  });
});
