// @vitest-environment jsdom
// S1 대시보드 온실가스 탭(밴드 DB1 ②). 진짜 대시보드 실어댑터 + 가짜 온실가스 서버(dashboards 씨앗 — openapi 꼴, 새 칸 scope3FailedSheets 포함).
//   연도는 바깥 상태(Harness)가 쥔다 — onYear 가 year prop 을 바꾼다.
//   값 있는 해(총합·Scope 셋·범례·사업장 합 큰 차례·배출원 상위 5·몫 %·C 번호 이름) · Scope 3 빠짐 n(총합 옆·Scope 3 카드 옆 둘, 범례 0) ·
//   Scope 3 없음(총합 옆 「Scope 3 결과 없음」만, Scope 3 자리 「-」) · 전부 실패한 해(「없음」만) · 미설정 덮개(Scope 3 도 없을 때만 —
//   뒤 판 aria-hidden·inert, [바로가기] → onSetup) · Scope 3 만 있는 미설정(덮지 않음) · 회사 거절 · 불러오기 실패 → [다시 시도] · 연도 바꿈 · ›.
//   숨김: 시장기반·지역기반·「ESG 데이터」 글이 없다.
//   밴드 DB2(sid:MARC-ENT-598 — e6 ①~⑤): 세 해 따로 읽기 · Scope 카드 3개년 막대(차례 −2·−1·고른 해 · 고른 해 말풍선 늘 · 앞 해 올림/초점) ·
//   앞 해 없음·0·실패(「없음」, 오류 띠 0) · 「전년 대비」(증가·감소 · Scope 3 빠짐/없음·Scope 1·2 없음 때 숨김 · DB1 ⑦ 글과 한 줄에 같이 안 나옴).
//   감독 판단 13: 도넛 가운데 합계 글 18→14 · 범례 이름 칸 꺾지 않음(그려진 폭은 getBoundingClientRect 흉내).
//   밴드 DB3(sid:MARC-TICK-538 — 움직임 e6 ②~④ · 넘김 R1~R3·e6 정함 3): jsdom 은 matchMedia·애니메이션이 없어 클래스와 style 로 잰다 —
//   자리(카드 줄·도넛·3개년·사업장별·배출원별·빈 상태·덮개) · 때(늦게 온 앞 해 = 같은 노드 · 해 바꿈 = 새 노드) ·
//   막대 칸 배치 클래스 · 앞 해 회사 거절 · 배출원별 단 0→1→2 · 자리 폭이 넓어지면 단이 0 으로 돌아옴(ResizeObserver 흉내).
import { act, useState } from 'react';

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import type { GhgDashboardPort } from '../../../entities/ghg/api/index.ts';
import {
  dashboardOut,
  fakeDashboard,
  fakeGhgServer,
  fakeScope2OnlyDashboard,
  portsOf,
  unreachable,
} from '../../../entities/ghg/api/testing.ts';
import type { FakeGhgServerOptions } from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { DashboardScreen } from './DashboardScreen.tsx';

afterEach(cleanup);

const words = GHG_TEXT.dashboard;
const YEARS = [2026, 2025, 2024, 2023, 2022];
const KEY = 'GET /inventory/scope12/dashboard';
const WAIT = { timeout: 3000 };

function setup(
  options: FakeGhgServerOptions = {},
  {
    operator = false,
    year = 2025,
    wrap = (port: GhgDashboardPort) => port,
  }: {
    operator?: boolean;
    year?: number;
    wrap?: (port: GhgDashboardPort) => GhgDashboardPort;
  } = {},
) {
  const server = fakeGhgServer(options);
  const port = wrap(portsOf(server).dashboard);
  const calls = {
    setup: vi.fn(),
    inventory: vi.fn(),
    organization: vi.fn(),
  };
  function Harness() {
    const [shown, setShown] = useState(year);
    return (
      <DashboardScreen
        port={port}
        year={shown}
        years={YEARS}
        operator={operator}
        onYear={setShown}
        onSetup={calls.setup}
        onInventory={calls.inventory}
        onOrganization={calls.organization}
      />
    );
  }
  render(<Harness />);
  return { server, calls };
}

const shown = () =>
  waitFor(
    () =>
      expect(
        screen.queryByTestId('dashboard-emission') ??
          screen.queryByTestId('load-failure') ??
          screen.queryByTestId('company-refusal'),
      ).not.toBeNull(),
    WAIT,
  );
const text = (id: string) => screen.getByTestId(id).textContent;
const yearsAsked = (server: ReturnType<typeof fakeGhgServer>) =>
  server.calls
    .filter((call) => `${call.method} ${call.path}` === KEY)
    .map((call) => call.query.get('year'));
const mark = (id: string) => screen.queryByTestId(`${id}-mark`)?.textContent;

describe('S1 대시보드', () => {
  it('값 있는 해: 제목·총합·Scope 셋·범례 · 단위 tCO2eq · 숨김 글 0', async () => {
    setup({ dashboards: { 2025: fakeDashboard(2025) } });
    await shown();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      '대시보드',
    );
    expect(text('dashboard-total-value')).toBe('100tCO2eq');
    expect(text('dashboard-scope-1-value')).toBe('60tCO2eq');
    expect(text('dashboard-scope-2-value')).toBe('30tCO2eq');
    expect(text('dashboard-scope-3-value')).toBe('10tCO2eq');
    expect(['1', '2', '3'].map((n) => text(`dashboard-legend-${n}`))).toEqual([
      'Scope 160tCO2eq',
      'Scope 230tCO2eq',
      'Scope 310tCO2eq',
    ]);
    expect(
      within(screen.getByTestId('dashboard-scope-1')).getByRole('heading')
        .textContent,
    ).toBe('Scope 1 배출량');
    expect(mark('dashboard-total-value')).toBeUndefined();
    expect(mark('dashboard-scope-3-value')).toBeUndefined();
    const body = document.body.textContent ?? '';
    for (const hidden of ['시장기반', '지역기반', 'ESG 데이터'])
      expect(body).not.toContain(hidden);
  });

  it('사업장별: 합이 큰 차례 · 막대 조각 둘(Scope 3 없음) · 범례 Scope 1·2 + 단위', async () => {
    setup({ dashboards: { 2025: fakeDashboard(2025) } });
    await shown();
    const sites = screen.getByTestId('dashboard-sites');
    const rows = within(sites).getAllByRole('listitem');
    expect(
      rows
        .filter((row) => row.dataset.testid?.startsWith('dashboard-site-'))
        .map((row) => row.textContent),
    ).toEqual(['제1공장70', '본사20']);
    expect(
      screen.getByTestId('dashboard-site-2').querySelectorAll('[data-part]')
        .length,
    ).toBe(2);
    expect(sites.textContent).toContain('단위: tCO2eq');
    expect(sites.textContent).not.toContain('Scope 3');
  });

  it('배출원별: Scope 1·2 상위 · Scope 3 「C4. 이름」 · 몫 정수 % · 1% 아래 「<1%」', async () => {
    setup({ dashboards: { 2025: fakeDashboard(2025) } });
    await shown();
    const rowsOf = (n: number) =>
      within(screen.getByTestId(`dashboard-source-${n}`))
        .getAllByRole('listitem')
        .map((row) => row.textContent);
    expect(rowsOf(1)).toEqual(['지어낸 고정연소4575%', '지어낸 이동연소1525%']);
    expect(rowsOf(2)).toEqual([
      '지어낸 전기 사용29.899%',
      '지어낸 열 사용0.2<1%',
    ]);
    // e6 고침: 이름 칸은 남는 폭을 다 쓰고 두 줄까지(그 뒤 말줄임) · title 에 전체 이름 · 숫자·% 는 줄바꿈 없음.
    const name = within(
      screen.getByTestId('dashboard-source-1'),
    ).getAllByTestId('dashboard-source-name')[0]!;
    expect(name.className).toContain('line-clamp-2');
    expect(name.className).toContain('flex-1');
    expect(name.closest('li')!.getAttribute('title')).toBe('지어낸 고정연소');
    expect(name.nextElementSibling!.className).toContain('whitespace-nowrap');
    expect(rowsOf(3)).toEqual([
      `C4. ${S3_TEXT.categories.C4}660%`,
      `C1. ${S3_TEXT.categories.C1}440%`,
    ]);
  });

  it('Scope 2 만 고른 회사(검증 B1): 「Scope 2 배출량」 카드에 값 · Scope 1 자리 「-」 · 배출원 Scope 1 「-」 · 막대 색 청록', async () => {
    setup({ dashboards: { 2025: fakeScope2OnlyDashboard(2025) } });
    await shown();
    expect(text('dashboard-scope-1-value')).toBe('-');
    expect(text('dashboard-scope-2-value')).toBe('30tCO2eq');
    expect(text('dashboard-legend-1')).toBe('Scope 1-');
    expect(text('dashboard-legend-2')).toBe('Scope 230tCO2eq');
    expect(screen.queryByTestId('dashboard-source-1-empty')).not.toBeNull();
    expect(
      within(screen.getByTestId('dashboard-source-2'))
        .getAllByRole('listitem')
        .map((row) => row.textContent),
    ).toEqual(['지어낸 전기 사용29.899%', '지어낸 열 사용0.2<1%']);
    const part = screen
      .getByTestId('dashboard-site-2')
      .querySelector('[data-part]')!;
    expect(part.getAttribute('data-part')).toBe('2');
    expect(part.className).toContain('text-support-turquoise');
  });

  it('Scope 3 빠짐 n: 총합 옆·Scope 3 카드 옆 둘에 「시트 n개 빠짐」(결과 화면 글) · 범례 0', async () => {
    setup({
      dashboards: { 2025: fakeDashboard(2025, { scope3FailedSheets: 3 }) },
    });
    await shown();
    const missing = S3_TEXT.result.scopeTotalMissing(3);
    expect(mark('dashboard-total-value')).toBe(missing);
    expect(mark('dashboard-scope-3-value')).toBe(missing);
    expect(mark('dashboard-scope-1-value')).toBeUndefined();
    expect(screen.getByTestId('dashboard-legend-3').textContent).not.toContain(
      missing,
    );
    expect(
      screen.getByTestId('dashboard-total-value-mark').className,
    ).toContain('text-support-error-accent');
  });

  it('Scope 3 결과 없음: Scope 3 자리 「-」 · 총합 = Scope 1+2 + 옆 「Scope 3 결과 없음」만 · Scope 3 배출원 「-」', async () => {
    setup({
      dashboards: {
        2025: fakeDashboard(2025, { scope3: null, sum: '90' }),
      },
    });
    await shown();
    expect(text('dashboard-total-value')).toBe(`90tCO2eq${words.scope3None}`);
    expect(text('dashboard-scope-3-value')).toBe('-');
    expect(mark('dashboard-scope-3-value')).toBeUndefined();
    expect(text('dashboard-legend-3')).toBe('Scope 3-');
  });

  it('Scope 3 전부 실패한 해(합 null · 빠진 시트 n): 「Scope 3 결과 없음」만(「빠짐」 숨김)', async () => {
    setup({
      dashboards: {
        2025: fakeDashboard(2025, {
          scope3: null,
          sum: '90',
          scope3FailedSheets: 4,
        }),
      },
    });
    await shown();
    expect(mark('dashboard-total-value')).toBe(words.scope3None);
    expect(mark('dashboard-scope-3-value')).toBeUndefined();
    expect(document.body.textContent).not.toContain(
      S3_TEXT.result.scopeTotalMissing(4),
    );
  });

  it('미설정 + Scope 3 없음: 덮개(판 글 셋) · 뒤 판 aria-hidden·inert · [바로가기] → onSetup(그 해)', async () => {
    const { calls } = setup();
    await waitFor(
      () => expect(screen.queryByTestId('dashboard-setup')).not.toBeNull(),
      WAIT,
    );
    const setupBox = screen.getByTestId('dashboard-setup');
    expect(setupBox.textContent).toContain(words.setupTitle);
    for (const line of words.setupBody)
      expect(setupBox.textContent).toContain(line);
    const behind = screen.getByTestId('dashboard-emission').closest('[inert]');
    expect(behind).not.toBeNull();
    expect(behind!.getAttribute('aria-hidden')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: words.setupAction }));
    expect(calls.setup).toHaveBeenCalledWith(2025);
  });

  it('미설정이어도 Scope 3 결과가 있으면 덮지 않는다 — Scope 1·2 「-」, Scope 3 값', async () => {
    setup({
      dashboards: {
        2025: dashboardOut(2025, {
          total: { ...dashboardOut(2025).total, scope3: '4', sum: '4' },
        }),
      },
    });
    await shown();
    expect(screen.queryByTestId('dashboard-setup')).toBeNull();
    expect(text('dashboard-scope-1-value')).toBe('-');
    expect(text('dashboard-scope-3-value')).toBe('4tCO2eq');
    expect(text('dashboard-total-value')).toBe('4tCO2eq');
  });

  it('회사 거절: 고객사·운영 관리자 글', async () => {
    setup({ company: 'COMPANY_AMBIGUOUS' }, { operator: true });
    await shown();
    expect(text('company-refusal')).toBe(GHG_TEXT.companyOperator.ambiguous);
  });

  it('불러오기 실패 → [다시 시도] → 다시 읽어 판', async () => {
    // 고른 해 첫 부름만 끊김(해 거른 셈 — 훅 부름 차례에 기대지 않는다).
    let failed = false;
    const { server } = setup({ dashboards: { 2025: fakeDashboard(2025) } });
    server.override[KEY] = () => {
      const call = server.calls.at(-1)!;
      if (call.query.get('year') === '2025' && !failed) {
        failed = true;
        return unreachable();
      }
      return new Response(
        JSON.stringify(
          call.query.get('year') === '2025' ?
            fakeDashboard(2025)
          : dashboardOut(Number(call.query.get('year'))),
        ),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    };
    await shown();
    expect(screen.getByTestId('load-failure').textContent).toContain(
      GHG_TEXT.inventory.loadFailed,
    );
    fireEvent.click(
      screen.getByRole('button', { name: GHG_TEXT.common.retry }),
    );
    await waitFor(
      () => expect(screen.queryByTestId('dashboard-emission')).not.toBeNull(),
      WAIT,
    );
    expect(yearsAsked(server).filter((year) => year === '2025')).toHaveLength(
      2,
    );
  });

  it('연도 바꿈 → onYear → 그 해를 다시 읽음 · › 셋 → onInventory(해)·onOrganization', async () => {
    const { server, calls } = setup({
      dashboards: {
        2025: fakeDashboard(2025),
        2024: fakeDashboard(2024, { sum: '7' }),
      },
    });
    await shown();
    fireEvent.change(screen.getByRole('combobox', { name: words.yearLabel }), {
      target: { value: '2024' },
    });
    await waitFor(
      () => expect(text('dashboard-total-value')).toBe('7tCO2eq'),
      WAIT,
    );
    // 해마다 세 해(고른 해·−1·−2)씩 — 차례가 아니라 집합으로.
    expect(new Set(yearsAsked(server))).toEqual(
      new Set(['2025', '2024', '2023', '2022']),
    );
    expect(yearsAsked(server).filter((year) => year === '2024')).toHaveLength(
      2,
    );
    fireEvent.click(
      screen.getByRole('button', { name: words.more(words.emissionTitle) }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: words.more(words.sourceTitle) }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: words.more(words.siteTitle) }),
    );
    expect(calls.inventory.mock.calls).toEqual([[2024], [2024]]);
    expect(calls.organization).toHaveBeenCalledTimes(1);
  });

  describe('3개년 막대 · 전년 대비(밴드 DB2)', () => {
    /** 지어낸 해 판 — Scope 1·2 뿌리 값과 합을 덮는다(openapi 꼴 그대로). */
    const yearBoard = (
      year: number,
      [one, two, three]: [string, string, string | null],
      patch: Record<string, unknown> = {},
    ) => {
      const value = fakeDashboard(year, {
        scope12: `${Number(one) + Number(two)}`,
        scope3: three,
        sum: `${Number(one) + Number(two) + Number(three ?? 0)}`,
        ...patch,
      });
      value.scopes[0]!.value = one;
      value.scopes[1]!.value = two;
      return value;
    };
    const THREE = {
      2023: yearBoard(2023, ['200', '100', '20']),
      2024: yearBoard(2024, ['300', '100', '40']),
      2025: yearBoard(2025, ['400', '150', '50']),
    };
    const bar = (scope: number, year: number) =>
      screen.getByTestId(`dashboard-scope-${scope}-trend-bar-${year}`);
    const tip = (scope: number, year: number) =>
      screen.queryByTestId(`dashboard-scope-${scope}-trend-tip-${year}`);
    const settled = () =>
      waitFor(
        () =>
          expect(
            screen
              .getAllByTestId(/^dashboard-scope-\d-trend-bar-/)
              .some((node) => node.dataset.kind === 'loading'),
          ).toBe(false),
        WAIT,
      );

    // 밴드 DB4(사용자 11-08): 말풍선은 고른 해도 올림·초점 때만(DB2 의 「고른 해 늘」을 갈음).
    it('세 해 값: 카드마다 막대 셋 · 차례 −2·−1·고른 해 · 고른 해만 진함 · 말풍선은 세 해 모두 올림/초점에만(DB4) · aria-label · 전년 대비 증가', async () => {
      setup({ dashboards: THREE });
      await shown();
      await settled();
      for (const scope of [1, 2, 3]) {
        const trend = screen.getByTestId(`dashboard-scope-${scope}-trend`);
        const columns = within(trend).getAllByTestId(
          /^dashboard-scope-\d-trend-bar-/,
        );
        expect(columns.map((column) => column.textContent?.slice(-4))).toEqual([
          '2023',
          '2024',
          '2025',
        ]);
        expect(trend.querySelectorAll('[data-bar]')).toHaveLength(3);
        expect(trend.textContent).toContain('단위: tCO2eq');
      }
      const bars = [2023, 2024, 2025].map((year) =>
        bar(1, year).querySelector('[data-bar]')!,
      );
      expect(bars.map((node) => node.className.includes('opacity-40'))).toEqual(
        [true, true, false],
      );
      // 눈금 최대 400 → step 100 · 400 = 160px
      expect((bars[2] as HTMLElement).style.height).toBe('160px');
      expect((bars[0] as HTMLElement).style.height).toBe('80px');
      expect(bars[2]!.className).toContain('text-support-purple');
      // 처음 그림: 말풍선 0(고른 해 포함 · 카드 셋 모두)
      expect(
        screen.queryAllByTestId(/^dashboard-scope-\d-trend-tip-/),
      ).toHaveLength(0);
      expect(bar(1, 2024).getAttribute('aria-label')).toBe('2024년 300 tCO2eq');
      expect(bar(1, 2025).getAttribute('aria-label')).toBe('2025년 400 tCO2eq');
      expect(bar(1, 2024).getAttribute('role')).toBe('img');
      expect(bar(1, 2024).tabIndex).toBe(0);
      expect(bar(1, 2025).tabIndex).toBe(0);
      fireEvent.focus(bar(1, 2024));
      expect(tip(1, 2024)?.textContent).toBe('2024300');
      expect(tip(1, 2025)).toBeNull();
      // 겹치면 올린 쪽이 위(감독 판단 6 — 자리 클래스는 그대로)
      expect(tip(1, 2024)!.className).toContain('z-20');
      fireEvent.blur(bar(1, 2024));
      expect(tip(1, 2024)).toBeNull();
      fireEvent.mouseEnter(bar(1, 2025));
      expect(tip(1, 2025)?.textContent).toBe('2025400');
      expect(tip(1, 2025)!.className).toContain('z-10');
      expect(tip(1, 2025)!.className).toContain('right-[29px]');
      fireEvent.mouseLeave(bar(1, 2025));
      expect(tip(1, 2025)).toBeNull();
      fireEvent.mouseEnter(bar(2, 2023));
      expect(tip(2, 2023)?.textContent).toBe('2023100');
      fireEvent.mouseLeave(bar(2, 2023));
      expect(tip(2, 2023)).toBeNull();
      // 600 vs 440 → +36.36…% → 36.4
      expect(text('dashboard-total-change')).toBe(words.yearUp('36.4'));
      expect(screen.queryByTestId('load-failure')).toBeNull();
    });

    it('감소: 「전년 대비 n% 감소」(크기만)', async () => {
      setup({
        dashboards: {
          2024: yearBoard(2024, ['400', '150', '50']),
          2025: yearBoard(2025, ['300', '100', '40']),
        },
      });
      await shown();
      await waitFor(
        () =>
          expect(text('dashboard-total-change')).toBe(words.yearDown('26.7')),
        WAIT,
      );
    });

    it('앞 해 없음(씨앗 없음 = 빈 판): 그 칸 막대·말풍선 0 · 연도 글 있음 · 초점 안 받음 · 전년 대비 숨김 · 오류 띠 0', async () => {
      setup({ dashboards: { 2025: THREE[2025] } });
      await shown();
      await settled();
      for (const year of [2023, 2024]) {
        const column = bar(1, year);
        expect(column.dataset.kind).toBe('none');
        expect(column.querySelector('[data-bar]')).toBeNull();
        expect(column.textContent).toBe(`${year}`);
        expect(column.hasAttribute('tabindex')).toBe(false);
        expect(column.getAttribute('role')).toBeNull();
        fireEvent.mouseEnter(column);
        expect(tip(1, year)).toBeNull();
      }
      // 고른 해도 올림 때만(DB4)
      expect(tip(1, 2025)).toBeNull();
      fireEvent.focus(bar(1, 2025));
      expect(tip(1, 2025)).not.toBeNull();
      expect(screen.queryByTestId('dashboard-total-change')).toBeNull();
      expect(document.body.textContent).not.toContain('전년');
      expect(screen.queryByRole('alert')).toBeNull();
    });

    it('0: 막대 높이 0 · 말풍선 「0」 · 앞 해 총합 0 이면 전년 대비 숨김(서버로는 나오지 않는 지어낸 값)', async () => {
      setup({
        dashboards: {
          2024: yearBoard(2024, ['0', '0', '0']),
          2025: THREE[2025],
        },
      });
      await shown();
      await settled();
      const zero = bar(3, 2024);
      expect(zero.dataset.kind).toBe('value');
      expect(
        (zero.querySelector('[data-bar]') as HTMLElement).style.height,
      ).toBe('0px');
      fireEvent.focus(zero);
      expect(tip(3, 2024)?.textContent).toBe('20240');
      expect(screen.queryByTestId('dashboard-total-change')).toBeNull();
    });

    it('Scope 3 빠짐·없음·Scope 1·2 없음 때 전년 대비 숨김 · 고른 해 빠짐이면 DB1 「시트 n개 빠짐」 그대로(같은 줄에 같이 안 나옴)', async () => {
      setup({
        dashboards: {
          ...THREE,
          2025: yearBoard(2025, ['400', '150', '50'], {
            scope3FailedSheets: 2,
          }),
        },
      });
      await shown();
      await settled();
      expect(mark('dashboard-total-value')).toBe(
        S3_TEXT.result.scopeTotalMissing(2),
      );
      expect(screen.queryByTestId('dashboard-total-change')).toBeNull();
      // Scope 3 일부 실패 해도 막대는 계산된 값으로(e6 ④)
      expect(bar(3, 2025).dataset.kind).toBe('value');
      cleanup();

      setup({
        dashboards: {
          ...THREE,
          2024: yearBoard(2024, ['300', '100', '40'], {
            scope3FailedSheets: 1,
          }),
        },
      });
      await shown();
      await settled();
      expect(screen.queryByTestId('dashboard-total-change')).toBeNull();
      expect(mark('dashboard-total-value')).toBeUndefined();
      cleanup();

      setup({
        dashboards: { ...THREE, 2024: yearBoard(2024, ['300', '100', null]) },
      });
      await shown();
      await settled();
      expect(screen.queryByTestId('dashboard-total-change')).toBeNull();
      expect(bar(3, 2024).dataset.kind).toBe('none');
      expect(bar(1, 2024).dataset.kind).toBe('value');
      cleanup();

      // 감독 판단 11: 앞 해 Scope 1·2 합 없음(Scope 3 만 있는 미설정 해) — 숨김 · 그 해 Scope 3 막대는 그림
      setup({
        dashboards: {
          ...THREE,
          2024: dashboardOut(2024, {
            total: {
              ...dashboardOut(2024).total,
              scope3: '40',
              sum: '40',
            },
          }),
        },
      });
      await shown();
      await settled();
      expect(screen.queryByTestId('dashboard-total-change')).toBeNull();
      expect(bar(3, 2024).dataset.kind).toBe('value');
      expect(bar(1, 2024).dataset.kind).toBe('none');
    });

    it('앞 해 실패: 그 칸 「없음」 · load-failure·role=alert 0 · 고른 해 판 그대로 · 전년 대비 숨김', async () => {
      setup({ dashboards: THREE, dashboardFailures: [2024] });
      await shown();
      await settled();
      expect(bar(1, 2024).dataset.kind).toBe('none');
      expect(bar(1, 2023).dataset.kind).toBe('value');
      expect(screen.queryByTestId('load-failure')).toBeNull();
      expect(screen.queryByRole('alert')).toBeNull();
      expect(text('dashboard-total-value')).toBe('600tCO2eq');
      expect(screen.queryByTestId('dashboard-total-change')).toBeNull();
    });

    it('카드 머리 한 줄: 제목 왼쪽 · 고른 해 합 오른쪽(18 Bold + 단위) · 「빠짐」은 그 아래', async () => {
      setup({
        dashboards: { 2025: fakeDashboard(2025, { scope3FailedSheets: 3 }) },
      });
      await shown();
      const head = screen.getByTestId('dashboard-scope-3-value').parentElement!;
      expect(head.firstElementChild!.textContent).toBe('Scope 3 배출량');
      expect(
        screen.getByTestId('dashboard-scope-3-value').firstElementChild!
          .textContent,
      ).toBe('10tCO2eq');
      expect(
        screen.getByTestId('dashboard-scope-3-value').firstElementChild!
          .firstElementChild!.className,
      ).toContain('text-style-pre-heading-02');
      expect(mark('dashboard-scope-3-value')).toBe(
        S3_TEXT.result.scopeTotalMissing(3),
      );
    });

    describe('감독 판단 13 — 그려진 폭', () => {
      afterEach(() => vi.restoreAllMocks());

      it('도넛 가운데 합계: 폭이 안 지름 − 16 을 넘으면 18 → 14 · 글은 그대로 · 넘지 않으면 18', async () => {
        vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(
          function (this: Element) {
            const html = this as HTMLElement;
            const width =
              html.dataset.testid === 'dashboard-donut-total' ?
                html.dataset.step === '0' ?
                  100
                : 80
              : 0;
            return { left: 0, right: width, width } as DOMRect;
          },
        );
        setup({ dashboards: THREE });
        await shown();
        const total = screen.getByTestId('dashboard-donut-total');
        await waitFor(() => expect(total.dataset.step).toBe('1'));
        expect(total.className).toContain('text-style-pre-body-04');
        expect(total.textContent).toBe('600');
        vi.restoreAllMocks();
        cleanup();
        setup({ dashboards: THREE });
        await shown();
        expect(screen.getByTestId('dashboard-donut-total').className).toContain(
          'text-style-pre-heading-02',
        );
      });

      it('범례(판단 14): 값은 늘 전체(말줄임 0) · 넘치면 셋 다 값 18 → 14 · 그래도 넘치면 단위를 값 아래 줄로 · 이름 꺾지 않음', async () => {
        // 단 0·1 은 넘침, 단 2 는 들어감(그려진 폭 흉내 — 범례 줄만).
        const stepOf = (node: HTMLElement) =>
          node.closest<HTMLElement>('[data-testid="dashboard-legend"]')?.dataset
            .step;
        vi.spyOn(
          HTMLElement.prototype,
          'scrollWidth',
          'get',
        ).mockImplementation(function (this: HTMLElement) {
          return (
              /^dashboard-legend-\d$/.test(this.dataset.testid ?? '') &&
                stepOf(this) !== '2'
            ) ?
              300
            : 0;
        });
        vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(
          200,
        );
        setup({ dashboards: THREE });
        await shown();
        const legend = screen.getByTestId('dashboard-legend');
        await waitFor(() => expect(legend.dataset.step).toBe('2'));
        for (const n of [1, 2, 3]) {
          const row = screen.getByTestId(`dashboard-legend-${n}`);
          const value = row.querySelector('[data-legend-value]')!;
          expect(value.className).toContain('text-style-pre-body-04');
          expect(value.className).toContain('whitespace-nowrap');
          expect(value.className).not.toContain('truncate');
          expect(value.parentElement!.className).toContain('flex-col');
          expect(
            row.querySelector('[data-legend-unit]')!.className,
          ).not.toContain('ml-1');
          expect(
            row.querySelector('span:not([aria-hidden])')!.className,
          ).toContain('whitespace-nowrap');
        }
        expect(text('dashboard-legend-1')).toBe('Scope 1400tCO2eq');
        vi.restoreAllMocks();
        cleanup();
        // 넘치지 않으면 단 0(값 18 · 단위 옆)
        setup({ dashboards: THREE });
        await shown();
        const plain = screen.getByTestId('dashboard-legend');
        expect(plain.dataset.step).toBe('0');
        expect(plain.querySelector('[data-legend-value]')!.className).toContain(
          'text-style-pre-heading-02',
        );
      });
    });
  });

  describe('움직임 · 넘김(밴드 DB3)', () => {
    afterEach(() => {
      vi.restoreAllMocks();
      vi.unstubAllGlobals();
    });

    /** 지어낸 해 판(Scope 1·2 뿌리 값과 합을 덮는다 — openapi 꼴 그대로, DB2 yearBoard 꼴). */
    const yearOf = (
      year: number,
      [one, two, three]: [string, string, string],
    ) => {
      const value = fakeDashboard(year, {
        scope12: `${Number(one) + Number(two)}`,
        scope3: three,
        sum: `${Number(one) + Number(two) + Number(three)}`,
      });
      value.scopes[0]!.value = one;
      value.scopes[1]!.value = two;
      return value;
    };
    const THREE = {
      2023: yearOf(2023, ['200', '100', '20']),
      2024: yearOf(2024, ['300', '100', '40']),
      2025: yearOf(2025, ['400', '150', '50']),
    };
    const delayOf = (node: Element) =>
      (node as HTMLElement).style.getPropertyValue('--gw-m-delay');
    const node = (id: string) => screen.getByTestId(id);
    const bar = (scope: number, year: number) =>
      node(`dashboard-scope-${scope}-trend-bar-${year}`);
    const tip = (scope: number, year: number) =>
      screen.queryByTestId(`dashboard-scope-${scope}-trend-tip-${year}`);
    const settled = () =>
      waitFor(
        () =>
          expect(
            screen
              .getAllByTestId(/^dashboard-scope-\d-trend-bar-/)
              .some((column) => column.dataset.kind === 'loading'),
          ).toBe(false),
        WAIT,
      );

    it('자리 1: 카드 넷·판 둘에 gw-m-rise + 차례 지연(감독 판단 2 — 0·40·80·120·160·160) · 바깥 「온실가스 배출량」 판 0', async () => {
      setup({ dashboards: THREE });
      await shown();
      const cards = [
        'dashboard-total',
        'dashboard-scope-1',
        'dashboard-scope-2',
        'dashboard-scope-3',
        'dashboard-sites',
        'dashboard-sources',
      ].map(node);
      expect(cards.map((card) => card.classList.contains('gw-m-rise'))).toEqual(
        [true, true, true, true, true, true],
      );
      expect(cards.map(delayOf)).toEqual([
        '0ms',
        '40ms',
        '80ms',
        '120ms',
        '160ms',
        '160ms',
      ]);
      expect(node('dashboard-emission').className).not.toMatch(/gw-m-/);
      expect(delayOf(node('dashboard-emission'))).toBe('');
    });

    it('자리 2: 도넛 — mask 안 원 하나에 gw-m-sweep(120ms) · 호에는 없음 · 바탕 고리는 mask 밖 · 두 화면의 mask id 가 겹치지 않음', async () => {
      setup({ dashboards: THREE });
      setup({ dashboards: THREE });
      await waitFor(
        () => expect(screen.getAllByTestId('dashboard-donut')).toHaveLength(2),
        WAIT,
      );
      for (const donut of screen.getAllByTestId('dashboard-donut')) {
        const sweeps = donut.querySelectorAll('.gw-m-sweep');
        expect(sweeps).toHaveLength(1);
        expect(sweeps[0]!.closest('mask')).not.toBeNull();
        expect(delayOf(sweeps[0]!)).toBe('120ms');
        const slices = donut.querySelectorAll('circle[data-slice]');
        expect(slices.length).toBeGreaterThan(0);
        for (const slice of slices) {
          expect(slice.getAttribute('class')).not.toMatch(/gw-m-/);
          expect(slice.closest('g[mask]')).not.toBeNull();
        }
        const base = donut.querySelector(':scope > circle')!;
        expect(base.closest('g[mask]')).toBeNull();
        expect(base.closest('mask')).toBeNull();
      }
      const ids = [...document.querySelectorAll('mask')].map((mask) => mask.id);
      expect(ids).toHaveLength(2);
      expect(new Set(ids).size).toBe(2);
      for (const group of document.querySelectorAll('g[mask]'))
        expect(ids.map((id) => `url(#${id})`)).toContain(
          group.getAttribute('mask'),
        );
    });

    it('자리 3: 3개년 — 막대 셋 gw-m-grow-y + 120·200·280 · 말풍선은 고른 해·앞 해 모두 gw-m-fade 지연 없음(DB4 — 늘 뜨는 760 갈음)', async () => {
      setup({ dashboards: THREE });
      await shown();
      await settled();
      const bars = [2023, 2024, 2025].map((year) =>
        bar(1, year).querySelector('[data-bar]')!,
      );
      expect(bars.map((one) => one.classList.contains('gw-m-grow-y'))).toEqual([
        true,
        true,
        true,
      ]);
      expect(bars.map(delayOf)).toEqual(['120ms', '200ms', '280ms']);
      expect(tip(1, 2025)).toBeNull();
      fireEvent.focus(bar(1, 2025));
      expect(tip(1, 2025)!.classList.contains('gw-m-fade')).toBe(true);
      expect(tip(1, 2025)!.style.animationDelay).toBe('');
      fireEvent.blur(bar(1, 2025));
      fireEvent.focus(bar(1, 2024));
      expect(tip(1, 2024)!.classList.contains('gw-m-fade')).toBe(true);
      expect(tip(1, 2024)!.style.animationDelay).toBe('');
    });

    it('자리 4: 사업장별 줄마다 gw-m-grow 하나(조각 [data-part] 0 · 120 + 줄마다 40) · 배출원별 안쪽 막대 gw-m-grow 120·160·200', async () => {
      setup({ dashboards: THREE });
      await shown();
      const sites = node('dashboard-sites');
      const rows = within(sites)
        .getAllByRole('listitem')
        .filter((row) => row.dataset.testid?.startsWith('dashboard-site-'));
      expect(rows.length).toBeGreaterThan(1);
      rows.forEach((row, at) => {
        const grows = row.querySelectorAll('.gw-m-grow');
        expect(grows).toHaveLength(1);
        expect(delayOf(grows[0]!)).toBe(`${120 + at * 40}ms`);
        for (const part of row.querySelectorAll('[data-part]'))
          expect(part.className).not.toMatch(/gw-m-/);
      });
      expect(
        [1, 2, 3].map((n) => {
          const grows = node(`dashboard-source-${n}`).querySelectorAll(
            '.gw-m-grow',
          );
          return grows.length === 1 ? delayOf(grows[0]!) : grows.length;
        }),
      ).toEqual(['120ms', '160ms', '200ms']);
    });

    it('자리 5: 숫자·「빠짐」·불러오는 중·불러오기 실패·회사 거절에는 gw-m- 0', async () => {
      const motionless = (element: Element) =>
        expect([element.outerHTML.includes('gw-m-'), element.tagName]).toEqual([
          false,
          element.tagName,
        ]);
      setup({
        dashboards: {
          2025: fakeDashboard(2025, { scope3FailedSheets: 2 }),
        },
      });
      // 불러오는 중(LoadSkeleton) — 첫 그림
      motionless(document.querySelector('[data-screen="ghg-dashboard"]')!);
      await shown();
      for (const id of [
        'dashboard-total-value',
        'dashboard-total-value-mark',
        'dashboard-scope-1-value',
        'dashboard-scope-3-value',
        'dashboard-scope-3-value-mark',
        'dashboard-legend',
        'dashboard-donut-total',
      ])
        motionless(node(id));
      for (const name of screen.getAllByTestId('dashboard-source-name'))
        motionless(name.parentElement!);
      cleanup();
      setup({ dashboards: {}, dashboardFailures: [2025] });
      await shown();
      motionless(node('load-failure'));
      cleanup();
      setup({ company: 'COMPANY_INACTIVE' });
      await shown();
      motionless(node('company-refusal'));
      // Scope 3 결과 없음 표시(총합 옆)
      cleanup();
      setup({ dashboards: { 2025: fakeDashboard(2025, { scope3: null }) } });
      await shown();
      expect(mark('dashboard-total-value')).toBe(words.scope3None);
      motionless(node('dashboard-total-value'));
    });

    it('자리 6: 빈 상태 글·덮개 안내에 gw-m-fade · 덮개 뒤 판(aria-hidden)에 gw-m-·--gw-m-delay 0', async () => {
      const empty = fakeDashboard(2025);
      empty.scope3Categories = [];
      setup({ dashboards: { 2025: empty } });
      await shown();
      expect(
        node('dashboard-source-3-empty').classList.contains('gw-m-fade'),
      ).toBe(true);
      cleanup();
      setup({ dashboards: {} });
      await waitFor(() => node('dashboard-covered'), WAIT);
      const cover = node('dashboard-setup').parentElement!;
      expect(cover.classList.contains('gw-m-fade')).toBe(true);
      const behind = node('dashboard-covered').querySelector('[aria-hidden]')!;
      expect(
        behind.querySelector('[data-testid="dashboard-total"]'),
      ).not.toBeNull();
      expect(behind.innerHTML).not.toContain('gw-m-');
      expect(behind.innerHTML).not.toContain('--gw-m-delay');
    });

    it('때 7: 앞 해 둘이 늦게 와도 총 배출량·Scope 1 카드·고른 해 막대가 같은 노드(다시 돌지 않음) · 늦게 온 앞 해 막대는 붙을 때 자람', async () => {
      let release!: () => void;
      const gate = new Promise<void>((done) => {
        release = done;
      });
      setup(
        { dashboards: THREE },
        {
          wrap: (port) => ({
            board: async (year) => {
              if (year !== 2025) await gate;
              return port.board(year);
            },
          }),
        },
      );
      await shown();
      expect(bar(1, 2024).dataset.kind).toBe('loading');
      const total = node('dashboard-total');
      const scope = node('dashboard-scope-1');
      const chosen = bar(1, 2025).querySelector('[data-bar]');
      expect(chosen).not.toBeNull();
      await act(async () => release());
      await settled();
      expect(node('dashboard-total')).toBe(total);
      expect(node('dashboard-scope-1')).toBe(scope);
      expect(bar(1, 2025).querySelector('[data-bar]')).toBe(chosen);
      expect(total.classList.contains('gw-m-rise')).toBe(true);
      // 늦게 온 앞 해 막대(감독 판단 6 — 상태 0, 붙을 때 자람)
      expect(
        bar(1, 2024)
          .querySelector('[data-bar]')!
          .classList.contains('gw-m-grow-y'),
      ).toBe(true);
    });

    it('때 8: 연도를 바꾸면 같은 testId 가 새 노드 + 다시 움직임 클래스', async () => {
      setup({ dashboards: THREE });
      await shown();
      const total = node('dashboard-total');
      const scope = node('dashboard-scope-2');
      fireEvent.change(
        screen.getByRole('combobox', { name: words.yearLabel }),
        {
          target: { value: '2024' },
        },
      );
      await waitFor(
        () => expect(screen.queryByTestId('dashboard-total')).not.toBe(total),
        WAIT,
      );
      await shown();
      expect(node('dashboard-total')).not.toBe(total);
      expect(node('dashboard-scope-2')).not.toBe(scope);
      expect(node('dashboard-total').classList.contains('gw-m-rise')).toBe(
        true,
      );
      expect(delayOf(node('dashboard-scope-2'))).toBe('80ms');
    });

    // 밴드 DB4: 고른 해 말풍선의 들어감 판정(DB3 넘김 R1-2 · RC1 감독 판단 8 — trendTipFits·ResizeObserver 재기)은 걷었다.
    it('DB4: 3개년 막대는 재지 않는다 — 폭을 흉내 내도(좁음·넓음) 처음 말풍선 0 · ResizeObserver 를 3개년 칸에 걸지 않음 · 재기 판 0 · 밀기 0', async () => {
      const watched: Element[] = [];
      vi.stubGlobal(
        'ResizeObserver',
        class {
          observe(node: Element) {
            watched.push(node);
          }
          unobserve() {}
          disconnect() {}
        },
      );
      for (const width of [10, 500]) {
        const spy = vi
          .spyOn(Element.prototype, 'getBoundingClientRect')
          .mockImplementation(
            () => ({ left: 0, right: width, width }) as DOMRect,
          );
        setup({ dashboards: THREE });
        await shown();
        await settled();
        expect(
          screen.queryAllByTestId(/^dashboard-scope-\d-trend-tip-/),
        ).toHaveLength(0);
        expect(document.querySelector('[data-tip-measure]')).toBeNull();
        for (const scope of [1, 2, 3]) {
          const trend = node(`dashboard-scope-${scope}-trend`);
          expect(watched.some((one) => trend.contains(one))).toBe(false);
        }
        fireEvent.mouseEnter(bar(1, 2025));
        expect(tip(1, 2025)).not.toBeNull();
        expect(document.body.innerHTML).not.toContain('translateX');
        expect(document.body.innerHTML).not.toContain('data-shift');
        spy.mockRestore();
        cleanup();
      }
    });

    it('넘김 R1-1: 막대 묶음 퍼센트 자리 클래스 0 · 눈금 글 칸 오른쪽 맞춤(글 + 4) · 막대 칸은 셋으로 나눈 칸 가운데', async () => {
      setup({ dashboards: THREE });
      await shown();
      for (const scope of [1, 2, 3]) {
        const trend = node(`dashboard-scope-${scope}-trend`);
        expect(trend.innerHTML).not.toContain('left-[13.53%]');
        expect(trend.innerHTML).not.toContain('w-[73.14%]');
        expect(trend.innerHTML).not.toContain('gap-7');
        const ticks = trend.querySelector('ol')!;
        expect(ticks.className).toContain('text-right');
        expect(ticks.className).toContain('pr-1');
        for (const tick of within(trend).getAllByTestId(
          `dashboard-scope-${scope}-trend-tick`,
        )) {
          expect(tick.className).toContain('right-1');
          expect(tick.className).not.toContain('left-0');
        }
        const column = bar(scope, 2025).parentElement!;
        expect(column.className).toContain('justify-center');
        expect(column.parentElement!.className).toContain('grid-cols-3');
      }
    });

    it('넘김 R2: 앞 해 하나가 회사 거절이면 그 칸 「없음」(loading 아님) · company-refusal·role=alert 0 · 전년 대비 숨김', async () => {
      setup({
        dashboards: THREE,
        dashboardRefusals: { 2024: 'COMPANY_INACTIVE' },
      });
      await shown();
      await waitFor(() => expect(bar(1, 2024).dataset.kind).toBe('none'), WAIT);
      expect(bar(1, 2023).dataset.kind).toBe('value');
      expect(screen.queryByTestId('company-refusal')).toBeNull();
      expect(screen.queryByRole('alert')).toBeNull();
      expect(screen.queryByTestId('dashboard-total-change')).toBeNull();
      expect(text('dashboard-total-value')).toBe('600tCO2eq');
    });

    /** 배출원별 줄 넘침 흉내: 단 overflowAt 에 든 단에서만 줄(li)이 넘친다. */
    const sourceOverflow = (overflowAt: () => readonly string[]) => {
      vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(
        function (this: HTMLElement) {
          const panel = this.closest<HTMLElement>(
            '[data-testid="dashboard-sources"]',
          );
          if (this.tagName !== 'LI' || !panel) return 0;
          return overflowAt().includes(panel.dataset.step ?? '') ? 300 : 0;
        },
      );
      vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(
        200,
      );
    };

    it('넘김 e6 정함 3: 넘치면 세 칸 같이 숫자 16 → 14 Bold(단 1) · 그래도 넘치면 % 를 숫자 아래 줄(단 2) · 그래도 넘치면 이름 위 줄(단 3) · 숫자 말줄임 0 · 이름 칸 최소 네 자', async () => {
      const figure = (n: number) =>
        node(`dashboard-source-${n}`).querySelector<HTMLElement>(
          '[data-testid="dashboard-source-figure"]',
        )!;
      sourceOverflow(() => ['0']);
      setup({ dashboards: THREE });
      await shown();
      await waitFor(() =>
        expect(node('dashboard-sources').dataset.step).toBe('1'),
      );
      for (const n of [1, 2, 3]) {
        const value = figure(n).querySelector('[data-source-value]')!;
        expect(value.className).toContain('text-style-pre-body-04');
        expect(figure(n).className).not.toContain('flex-col');
      }
      vi.restoreAllMocks();
      cleanup();

      sourceOverflow(() => ['0', '1']);
      setup({ dashboards: THREE });
      await shown();
      await waitFor(() =>
        expect(node('dashboard-sources').dataset.step).toBe('2'),
      );
      for (const n of [1, 2, 3]) {
        expect(figure(n).className).toContain('flex-col');
        expect(figure(n).className).toContain('whitespace-nowrap');
        expect(figure(n).innerHTML).not.toContain('truncate');
        expect(
          figure(n).querySelector('[data-source-value]')!.className,
        ).toContain('text-style-pre-body-04');
      }
      for (const name of screen.getAllByTestId('dashboard-source-name')) {
        expect(name.className).toContain('min-w-14');
        expect(name.className).not.toContain('min-w-0');
      }
      expect(text('dashboard-sources')).toContain('45');
      vi.restoreAllMocks();
      cleanup();

      // 감독 판단 16: 단 2 로도 넘치면 단 3 — 이름이 위 줄 전체 폭(두 줄까지 · title) · 아래 줄 값 14 왼쪽 · % 오른쪽(세 칸 같이)
      sourceOverflow(() => ['0', '1', '2']);
      setup({ dashboards: THREE });
      await shown();
      await waitFor(() =>
        expect(node('dashboard-sources').dataset.step).toBe('3'),
      );
      for (const n of [1, 2, 3]) {
        const row = figure(n).closest('li')!;
        expect(row.className).toContain('flex-col');
        expect(row.getAttribute('title')).toBe(
          row.querySelector('[data-testid="dashboard-source-name"]')!
            .textContent,
        );
        const name = row.firstElementChild!;
        expect(name.getAttribute('data-testid')).toBe('dashboard-source-name');
        expect(name.className).toContain('line-clamp-2');
        expect(name.className).toContain('w-full');
        expect(name.className).toContain('min-w-14');
        expect(figure(n).className).toContain('justify-between');
        expect(figure(n).className).not.toContain('flex-col');
        expect(figure(n).className).toContain('whitespace-nowrap');
        expect(
          figure(n).firstElementChild!.hasAttribute('data-source-value'),
        ).toBe(true);
        expect(
          figure(n).querySelector('[data-source-value]')!.className,
        ).toContain('text-style-pre-body-04');
      }
      vi.restoreAllMocks();
      cleanup();

      setup({ dashboards: THREE });
      await shown();
      expect(node('dashboard-sources').dataset.step).toBe('0');
      expect(
        figure(1).querySelector('[data-source-value]')!.className,
      ).toContain('text-style-pre-body-01');
    });

    it('넘김 R3: 단 2 까지 내린 뒤 자리 폭이 넓어지면(ResizeObserver 흉내) 범례·배출원별 둘 다 단 0 으로 돌아옴', async () => {
      const watchers: (() => void)[] = [];
      vi.stubGlobal(
        'ResizeObserver',
        class {
          constructor(private readonly callback: () => void) {}
          observe() {
            watchers.push(() => this.callback());
          }
          unobserve() {}
          disconnect() {}
        },
      );
      let wide = false;
      const stepOf = (element: HTMLElement) =>
        element.closest<HTMLElement>(
          '[data-testid="dashboard-legend"], [data-testid="dashboard-sources"]',
        )?.dataset.step;
      vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(
        function (this: HTMLElement) {
          const legendRow = /^dashboard-legend-\d$/.test(
            this.dataset.testid ?? '',
          );
          const sourceRow =
            this.tagName === 'LI' &&
            this.closest('[data-testid="dashboard-sources"]') !== null;
          if (!legendRow && !sourceRow) return 0;
          return !wide && stepOf(this) !== '2' ? 300 : 0;
        },
      );
      vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(
        () => (wide ? 400 : 200),
      );
      setup({ dashboards: THREE });
      await shown();
      await waitFor(() => {
        expect(node('dashboard-legend').dataset.step).toBe('2');
        expect(node('dashboard-sources').dataset.step).toBe('2');
      });
      // 첫 관찰(지금 폭을 적음) — 바뀜 아님
      act(() => watchers.forEach((watch) => watch()));
      expect(node('dashboard-legend').dataset.step).toBe('2');
      wide = true;
      act(() => watchers.forEach((watch) => watch()));
      await waitFor(() => {
        expect(node('dashboard-legend').dataset.step).toBe('0');
        expect(node('dashboard-sources').dataset.step).toBe('0');
      });
    });
  });
});

// 밴드 DB4(sid:MARC-TICK-543 — 발주서 §3 시험 3~6 · 감독 판단 3·4): 제목 숫자 굴림(대시보드 다섯 — 총 · Scope 셋 · 도넛 가운데).
//   jsdom 에는 matchMedia·rAF 시계가 없어 흉내 낸다(no-preference 참 = 움직임 · reduce 참 = 줄임). 끝 글자는 BASE 486bb14d 에서 같은 씨앗으로
//   뜬 글자(DB4.out/base-text.txt) — 기존 값 단언(위 시험들)은 그대로 두고 여기서는 굴림 뒤 같은 글자인지만 더 본다.
describe('제목 숫자 굴림(밴드 DB4)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  /** matchMedia(움직임 여부)·rAF(손으로 돌리는 시계) 흉내. */
  function motionStubs({ reduce = false }: { reduce?: boolean } = {}) {
    const queue = new Map<number, FrameRequestCallback>();
    let next = 1;
    let now = 1000;
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches:
        reduce ? query.includes(': reduce') : query.includes('no-preference'),
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent: () => false,
    }));
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      const id = next++;
      queue.set(id, callback);
      return id;
    });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => queue.delete(id));
    const advance = (ms: number) =>
      act(() => {
        now += ms;
        const run = [...queue.values()];
        queue.clear();
        run.forEach((callback) => callback(now));
      });
    return {
      advance,
      pending: () => queue.size,
      /** 2초 넘게 돌린다(상한 1,000 의 두 배 — 다 끝남). */
      finish: () => {
        for (let step = 0; step < 50; step += 1) advance(50);
      },
    };
  }

  /** BASE 씨앗과 같은 지어낸 판(소수 셋·하나·둘 · 천 단위 쉼표). */
  const seeded = (year: number) => {
    const value = fakeDashboard(year, {
      sum: '12345.6785',
      scope12: '1250.75',
      scope3: '98765.4321',
    });
    value.scopes[0]!.value = '1250.5';
    value.scopes[1]!.value = '0.25';
    return value;
  };
  /** BASE 486bb14d 의 끝 글자(DB4.out/base-text.txt — 바이트 그대로). 도넛 가운데는 총 배출량과 같은 amount 글자. */
  const BASE_TEXT = {
    'dashboard-total-value': '12,345.679tCO2eq',
    'dashboard-scope-1-value': '1,250.5tCO2eq',
    'dashboard-scope-2-value': '0.25tCO2eq',
    'dashboard-scope-3-value': '98,765.432tCO2eq',
    'dashboard-donut-total': '12,345.679',
  } as const;
  const IDS = Object.keys(BASE_TEXT) as (keyof typeof BASE_TEXT)[];
  const textsNow = () => Object.fromEntries(IDS.map((id) => [id, text(id)]));
  const rollingIn = (id: string) =>
    screen.getByTestId(id).querySelector('[data-rolling]');

  it('시험 2·3: 다섯 자리가 0 에서 굴러 끝 글자 = BASE 바이트 · 굴리는 동안 프레임 소수 자리 = 끝 소수 자리 · 단위·「빠짐」 곁 글은 처음부터 제자리', async () => {
    const clock = motionStubs();
    setup({ dashboards: { 2025: seeded(2025) } });
    await shown();
    for (const id of IDS) expect([id, rollingIn(id)]).not.toEqual([id, null]);
    // 첫 프레임 전 = 0(끝 꼴 소수 자리)
    const frameOf = (id: string) =>
      rollingIn(id)!.querySelector('[aria-hidden]:not(.invisible)')!
        .textContent;
    expect(IDS.map(frameOf)).toEqual([
      '0.000',
      '0.0',
      '0.00',
      '0.000',
      '0.000',
    ]);
    // 단위는 굴림 칸 밖에 처음부터
    expect(screen.getByTestId('dashboard-total-value').textContent).toContain(
      'tCO2eq',
    );
    expect(rollingIn('dashboard-total-value')!.textContent).not.toContain(
      'tCO2eq',
    );
    clock.advance(16);
    clock.advance(300);
    const middle = IDS.map(frameOf);
    expect(middle.map((frame) => frame!.split('.')[1]?.length)).toEqual([
      3, 1, 2, 3, 3,
    ]);
    clock.finish();
    expect(clock.pending()).toBe(0);
    for (const id of IDS) expect([id, rollingIn(id)]).toEqual([id, null]);
    expect(textsNow()).toEqual(BASE_TEXT);
  });

  it('시험 2: 1초 상한 — 총 배출량(지연 0)·Scope 3(120)·도넛 가운데(120)가 첫 프레임부터 1,000ms 에 모두 끝남 · 그 전(819ms)엔 Scope 3·도넛이 아직', async () => {
    const clock = motionStubs();
    setup({ dashboards: { 2025: seeded(2025) } });
    await shown();
    clock.advance(16); // 첫 프레임 = 시작 시각
    clock.advance(700);
    expect(rollingIn('dashboard-total-value')).toBeNull();
    clock.advance(103); // 819 — 120 + 700 = 820 바로 전
    expect(rollingIn('dashboard-scope-3-value')).not.toBeNull();
    expect(rollingIn('dashboard-donut-total')).not.toBeNull();
    clock.advance(181); // 1,000
    for (const id of IDS) expect([id, rollingIn(id)]).toEqual([id, null]);
    expect(textsNow()).toEqual(BASE_TEXT);
  });

  it('시험 4: 움직임 줄임이면 첫 그림부터 끝 글자 · 굴림 칸 0 · rAF 0', async () => {
    const clock = motionStubs({ reduce: true });
    setup({ dashboards: { 2025: seeded(2025) } });
    await shown();
    expect(document.querySelector('[data-rolling]')).toBeNull();
    expect(clock.pending()).toBe(0);
    expect(textsNow()).toEqual(BASE_TEXT);
  });

  it('시험 5: 연도를 바꾸면 다시 굴림(판 key={year}) · 끝 글자는 그 해 글자 · 앞 해가 늦게 와도 고른 해 숫자는 다시 안 굴림', async () => {
    const clock = motionStubs();
    setup({
      dashboards: {
        2025: seeded(2025),
        2024: fakeDashboard(2024, { sum: '7.5' }),
      },
    });
    await shown();
    clock.finish();
    expect(document.querySelector('[data-rolling]')).toBeNull();
    // 앞 해 둘은 따로 읽힌다 — 다 온 뒤에도 굴림 0(같은 노드)
    await waitFor(
      () =>
        expect(
          screen
            .getAllByTestId(/^dashboard-scope-\d-trend-bar-/)
            .some((column) => column.dataset.kind === 'loading'),
        ).toBe(false),
      WAIT,
    );
    expect(document.querySelector('[data-rolling]')).toBeNull();
    expect(textsNow()).toEqual(BASE_TEXT);
    fireEvent.change(screen.getByRole('combobox', { name: words.yearLabel }), {
      target: { value: '2024' },
    });
    await waitFor(
      () => expect(rollingIn('dashboard-total-value')).not.toBeNull(),
      WAIT,
    );
    clock.finish();
    expect(text('dashboard-total-value')).toBe('7.5tCO2eq');
    expect(rollingIn('dashboard-total-value')).toBeNull();
  });

  it('시험 6: 굴리는 동안 화면 읽기에는 끝 글자만(프레임·깔개 aria-hidden · 끝 글자 sr-only 하나) · 막대·도넛 aria 그대로', async () => {
    const clock = motionStubs();
    setup({ dashboards: { 2025: seeded(2025) } });
    await shown();
    clock.advance(16);
    clock.advance(200);
    for (const id of IDS) {
      const box = rollingIn(id)!;
      const spoken = [...box.children].filter(
        (child) => child.getAttribute('aria-hidden') !== 'true',
      );
      expect([id, spoken.map((one) => one.className)]).toEqual([
        id,
        ['sr-only'],
      ]);
      expect([id, spoken[0]!.textContent]).toEqual([
        id,
        BASE_TEXT[id].replace('tCO2eq', ''),
      ]);
      // 깔개(끝 글자 폭 잡기)는 보이지 않음 · 칸은 tabular-nums 안
      expect(box.querySelector('.invisible')!.textContent).toBe(
        spoken[0]!.textContent,
      );
      expect(box.closest('.tabular-nums')).not.toBeNull();
    }
    expect(
      screen.getByTestId('dashboard-donut').getAttribute('aria-hidden'),
    ).toBe('true');
    clock.finish();
  });

  it('덮개 뒤 판(still)은 굴리지 않음', async () => {
    motionStubs();
    setup({
      dashboards: {
        2025: dashboardOut(2025, {
          total: { ...dashboardOut(2025).total, sum: '5.5', scope12: '5.5' },
        }),
      },
    });
    await shown();
    expect(document.querySelector('[data-rolling]')).toBeNull();
  });
});
