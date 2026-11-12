// @vitest-environment jsdom
// S17 온실가스 데이터 설정(밴드 W12-0b2 ② — 발주서 §3 4). 진짜 선택 실어댑터 + 가짜 온실가스 서버(fakeSelectionOptions — 잎 20·22 고를 수 있음,
//   24 는 기본 계수 없음). 연도는 바깥 상태(경로 흉내 Harness)가 쥔다 — onYear 가 year prop 을 바꾼다.
//   426 줄(체크·부분·흐림 까닭(S12-05 뒤 하나)·J1·hasData 경고·422 두 칸·빈 저장·해마다 따로) · 459(다시 읽기 실패 notice·판 그대로·없는 id 뺌) ·
//   460(확인 창 Enter·닫히면 연 단추로 초점) · 취소·연도 바꿈 확인 · 검색 · 풀 빔 · 시설 0 · 회사 거절 두 역할.
//   sid:MARC-ISSUE-468(밴드 W12-1a ①): B1 까닭 둘째 줄 · D6 NativeSelect · D7 머리 토큰 · D8 ✕ 머리 칸 · D9 경고 머리/몸 · R4·M1 검색 중 부모 체크 ·
//   R5·M4 흐림 · M2 저장 중 막음 · M3 다시 읽는 동안 막음.
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
  fakeGhgServer,
  fakeHeadquarters,
  fakeSelectionOptions,
  json,
  portsOf,
  refusal,
  unreachable,
} from '../../../entities/ghg/api/testing.ts';
import type { FakeGhgServerOptions } from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { IndexSettingsScreen } from './IndexSettingsScreen.tsx';

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

const words = GHG_TEXT.indexSettings;
const YEARS = [2026, 2025, 2024, 2023, 2022];
const TREE = 'GET /inventory/scope12/index-tree';
const SAVE = (year: number) =>
  `PUT /inventory/scope12/index-selections/${year}`;

function setup(
  options: FakeGhgServerOptions = fakeSelectionOptions(),
  { operator = false, year = 2026 } = {},
) {
  const server = fakeGhgServer({ thisYear: 2026, ...options });
  const port = portsOf(server).selection;
  const onSaved = vi.fn();
  const onCancel = vi.fn();
  const onOrganization = vi.fn();
  const years: number[] = [];
  function Harness() {
    const [current, setCurrent] = useState(year);
    return (
      <IndexSettingsScreen
        port={port}
        year={current}
        years={YEARS}
        operator={operator}
        onSaved={onSaved}
        onCancel={onCancel}
        onYear={(next) => {
          years.push(next);
          setCurrent(next);
        }}
        onOrganization={onOrganization}
      />
    );
  }
  render(<Harness />);
  return { server, onSaved, onCancel, onOrganization, years };
}

const ready = () => screen.findByRole('button', { name: words.save });
const box = (name: string) =>
  screen.getByRole('checkbox', { name: words.check(name) });
const notice = () => screen.getByTestId('index-settings-notice').textContent;
const pickYear = (year: number) =>
  fireEvent.change(screen.getByRole('combobox', { name: words.yearLabel }), {
    target: { value: `${year}` },
  });
/** S12C1 da787b28: [저장] → 확인 창 「선택하신 인덱스를 저장할까요?」 → [확인](form). */
const saveConfirmed = async (save?: HTMLElement) => {
  fireEvent.click(save ?? screen.getByRole('button', { name: words.save }));
  fireEvent.submit(
    (await screen.findByTestId('save-confirm')).querySelector('form')!,
  );
};
const bodies = (server: ReturnType<typeof setup>['server'], year = 2026) =>
  server.bodies(SAVE(year));

describe('S17 판', () => {
  it('머리(시안): 브레드크럼·제목 「온실가스 데이터 설정」 · 열 넷 · 항목 뒤 (수) · 체크는 배출활동·자산/시설 열만 · 경로 줄', async () => {
    setup();
    await ready();
    expect(screen.getByRole('heading', { name: words.title })).toBeTruthy();
    expect(
      screen.getByRole('navigation', { name: words.breadcrumbLabel })
        .textContent,
    ).toBe('온실가스 데이터인덱스 설정');
    for (const name of Object.values(words.columns))
      expect(screen.getByRole('region', { name })).toBeTruthy();
    const scope = screen.getByRole('region', { name: words.columns.scope });
    expect(within(scope).queryAllByRole('checkbox')).toHaveLength(0);
    expect(scope.textContent).toContain('지어낸 직접배출(3)');
    expect(
      within(
        screen.getByRole('region', { name: words.columns.source_type }),
      ).queryAllByRole('checkbox'),
    ).toHaveLength(0);
    expect(box('지어낸 액체연료')).toBeTruthy();
    expect(screen.getByTestId('index-path').textContent).toBe(
      '지어낸 직접배출지어낸 고정연소지어낸 액체연료',
    );
  });

  it('GX2 S12-05 「선택한 인덱스」 표는 나무 차례 — 서버 평평한 차례가 앞인 잎(이동연소 24)도 고정연소 잎 뒤', async () => {
    const options = fakeSelectionOptions();
    // 이동연소 잎 24 의 sortOrder 를 맨 앞으로 — 서버 평평한 차례(단 → sortOrder)에서 24 가 20·22 보다 앞.
    options.pool = {
      ...options.pool!,
      nodes: options.pool!.nodes.map((node) =>
        node.id === '24' ? { ...node, sortOrder: 0 } : node,
      ),
      // 24 를 고를 수 있게 기본 계수 하나(지어낸).
      factors: [
        ...options.pool!.factors,
        {
          id: '31',
          facilityNodeId: '24',
          sortOrder: 31,
          isDefault: true,
          versions: [{ ...options.pool!.factors[0]!.versions[0]! }],
        },
      ],
    };
    setup(options);
    await ready();
    fireEvent.click(box('지어낸 보일러'));
    fireEvent.click(screen.getByRole('button', { name: /지어낸 이동연소/ }));
    fireEvent.click(await waitFor(() => box('지어낸 도로수송')));
    await waitFor(() =>
      expect(
        document.querySelectorAll('[data-testid^="chosen-"]').length,
      ).toBeGreaterThan(1),
    );
    const order = [
      ...document.querySelectorAll('tr[data-testid^="chosen-"]'),
    ].map((tr) => tr.getAttribute('data-testid'));
    expect(order).toContain('chosen-24');
    expect(order.indexOf('chosen-20')).toBeLessThan(order.indexOf('chosen-24'));
  });

  it('체크 → 「선택한 인덱스」 표 · 부분 「−」 · 부모 체크 → 고를 수 있는 자식 전부 · 행 ✕ · 전체 해제(확인 없이)', async () => {
    setup();
    await ready();
    fireEvent.click(box('지어낸 보일러'));
    expect(box('지어낸 액체연료').getAttribute('aria-checked')).toBe('mixed');
    expect(screen.getByTestId('chosen-20').textContent).toContain(
      '지어낸 직접배출지어낸 고정연소지어낸 액체연료지어낸 보일러',
    );
    fireEvent.click(box('지어낸 액체연료'));
    expect(box('지어낸 액체연료').getAttribute('aria-checked')).toBe('true');
    expect(screen.getByTestId('chosen-22')).toBeTruthy();
    fireEvent.click(
      screen.getByRole('button', { name: words.removeChosen('지어낸 발전기') }),
    );
    expect(screen.queryByTestId('chosen-22')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: words.clearAll }));
    expect(screen.queryByTestId('chosen-20')).toBeNull();
    expect(screen.queryByTestId('leave-confirm')).toBeNull();
  });

  it('S12-05 흐림 까닭 하나: 계수 없음 「기본 배출계수가 없어요」 — 체크 꺼짐 · 시설 0 잎은 흐림 없이 고름', async () => {
    setup(fakeSelectionOptions());
    await ready();
    fireEvent.click(screen.getByRole('button', { name: /지어낸 이동연소/ }));
    fireEvent.click(screen.getByRole('button', { name: /지어낸 도로수송/ }));
    const car = box('지어낸 사업장 차량');
    expect(car.hasAttribute('disabled')).toBe(true);
    expect(
      document.getElementById(car.getAttribute('aria-describedby')!)
        ?.textContent,
    ).toBe(words.noFactor);
    cleanup();
    setup({ ...fakeSelectionOptions(), branches: [fakeHeadquarters()] });
    await ready();
    const gen = box('지어낸 발전기'); // 이 회사에 그 자산/시설 0(본사만) · 기본 계수 있음
    expect(gen.hasAttribute('disabled')).toBe(false);
    expect(gen.hasAttribute('aria-describedby')).toBe(false);
    expect(screen.queryByTestId('ghg-why-line-22')).toBeNull();
    fireEvent.click(gen);
    expect(box('지어낸 발전기').getAttribute('aria-checked')).toBe('true');
  });

  it('J1: 처음 고른 못 고를 잎 — 해제 → 다시 고름 → 저장 본문에 실림', async () => {
    const { server, onSaved } = setup({ chosen: { 2026: ['20', '22'] } });
    await ready();
    const gen = box('지어낸 발전기');
    expect(gen.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(gen);
    expect(box('지어낸 발전기').getAttribute('aria-checked')).toBe('false');
    expect(box('지어낸 발전기').hasAttribute('disabled')).toBe(false);
    fireEvent.click(box('지어낸 발전기'));
    await saveConfirmed();
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(2026));
    expect(bodies(server)).toEqual([{ facilityNodeIds: [20, 22] }]);
  });

  it('검색: 이름 부분 일치 — 맞는 항목과 조상만 · 없으면 「검색 결과가 없어요」', async () => {
    setup();
    await ready();
    fireEvent.change(screen.getByLabelText(words.searchLabel), {
      target: { value: '도로' },
    });
    const scope = screen.getByRole('region', { name: words.columns.scope });
    expect(scope.textContent).toContain('지어낸 직접배출');
    expect(scope.textContent).not.toContain('지어낸 간접배출');
    expect(screen.getByTestId('index-path').textContent).toContain(
      '지어낸 도로수송',
    );
    fireEvent.change(screen.getByLabelText(words.searchLabel), {
      target: { value: '없는 이름' },
    });
    expect(screen.getByText(words.emptySearch)).toBeTruthy();
  });

  it('풀 빔 · 시설 0 → 안내 + [조직구조로]', async () => {
    setup({ thisYear: 2026, pool: { nodes: [], factors: [] } });
    expect(await screen.findByTestId('empty-pool')).toBeTruthy();
    expect(screen.getByText(words.emptyPool)).toBeTruthy();
    cleanup();
    const { onOrganization } = setup({ thisYear: 2026, branches: [] });
    await ready();
    expect(screen.getByTestId('no-facilities').textContent).toContain(
      words.noFacilities,
    );
    // GX2 S12-05: 글↔[조직구조로] 사이 8(안쪽 줄 gap-2).
    expect(screen.getByTestId('no-facilities-line').className).toContain(
      'gap-2',
    );
    fireEvent.click(screen.getByRole('button', { name: words.toOrganization }));
    expect(onOrganization).toHaveBeenCalled();
  });
});

describe('S17 저장', () => {
  it('저장: PUT 본문 잎만(정수, 서버 차례) → onSaved(같은 연도) · 빈 고름도 막지 않고 []', async () => {
    const { server, onSaved } = setup();
    await ready();
    fireEvent.click(box('지어낸 발전기'));
    fireEvent.click(box('지어낸 보일러'));
    await saveConfirmed();
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(2026));
    expect(bodies(server)).toEqual([{ facilityNodeIds: [20, 22] }]);
    cleanup();
    const second = setup();
    await ready();
    await saveConfirmed();
    await waitFor(() => expect(second.onSaved).toHaveBeenCalledWith(2026));
    expect(bodies(second.server)).toEqual([{ facilityNodeIds: [] }]);
    expect(second.server.chosenIn(2026)).toEqual([]);
  });

  it('hasData 경고: 뺀 잎 가운데 데이터 있는 n → 「…인덱스 1개…」 · 취소 → PUT 0·초점 [저장] · Enter(form) → PUT', async () => {
    const options = {
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20', '22'] },
    };
    const server = fakeGhgServer({ thisYear: 2026, ...options });
    server.selectionData.add('20');
    const onSaved = vi.fn();
    render(
      <IndexSettingsScreen
        port={portsOf(server).selection}
        year={2026}
        years={YEARS}
        onSaved={onSaved}
        onCancel={vi.fn()}
        onYear={vi.fn()}
        onOrganization={vi.fn()}
      />,
    );
    const save = await ready();
    fireEvent.click(box('지어낸 보일러'));
    fireEvent.click(save);
    const dialog = await screen.findByTestId('data-warning');
    expect(dialog.textContent).toContain(words.dataWarning(1));
    fireEvent.click(within(dialog).getByRole('button', { name: words.cancel }));
    await waitFor(() =>
      expect(screen.queryByTestId('data-warning')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(save));
    expect(server.count(SAVE(2026))).toBe(0);
    fireEvent.click(save);
    const again = await screen.findByTestId('data-warning');
    expect(document.activeElement).toBe(
      within(again).getByRole('button', { name: words.confirm }),
    );
    fireEvent.submit(again.querySelector('form')!);
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(2026));
    expect(server.bodies(SAVE(2026))).toEqual([{ facilityNodeIds: [22] }]);
    // S12C1 da787b28: 데이터 경고가 뜬 저장은 그 창 하나만 — 저장 확인 창이 연달아 뜨지 않는다.
    expect(screen.queryByTestId('save-confirm')).toBeNull();
  });

  it('S12C1 da787b28 저장 확인 창: [저장] → 「선택하신 인덱스를 저장할까요?」 [취소][확인] · 취소 → PUT 0·초점 [저장] · 확인 → PUT 한 번', async () => {
    const { server, onSaved } = setup();
    const save = await ready();
    fireEvent.click(box('지어낸 보일러'));
    fireEvent.click(save);
    const dialog = await screen.findByTestId('save-confirm');
    expect(within(dialog).getByRole('heading').textContent).toBe(
      '선택하신 인덱스를 저장할까요?',
    );
    expect(
      within(dialog)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual(['취소', '확인']);
    expect(screen.queryByTestId('data-warning')).toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: words.cancel }));
    await waitFor(() =>
      expect(screen.queryByTestId('save-confirm')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(save));
    expect(server.count(SAVE(2026))).toBe(0);
    expect(onSaved).not.toHaveBeenCalled();
    fireEvent.click(save);
    const again = await screen.findByTestId('save-confirm');
    expect(document.activeElement).toBe(
      within(again).getByRole('button', { name: words.confirm }),
    );
    fireEvent.submit(again.querySelector('form')!);
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(2026));
    expect(server.bodies(SAVE(2026))).toEqual([{ facilityNodeIds: [20] }]);
  });

  it('422 fields.facilityNodeIds → 한 줄 + 트리 다시 읽음(고른 것은 서버 것 · 없는 잎 id 뺌 — 459 M4)', async () => {
    const { server } = setup({
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    await ready();
    fireEvent.click(box('지어낸 발전기'));
    server.override[SAVE(2026)] = () =>
      refusal(422, 'VALIDATION_ERROR', { facilityNodeIds: ['지어낸'] });
    server.override[TREE] = () =>
      json(200, {
        year: 2026,
        nodes: [
          {
            id: '1',
            level: 'scope',
            name: '지어낸 직접배출',
            parentId: null,
            availableCount: 1,
            selected: false,
          },
          {
            id: '3',
            level: 'source_type',
            name: '지어낸 고정연소',
            parentId: '1',
            availableCount: 1,
            selected: false,
          },
          {
            id: '5',
            level: 'activity',
            name: '지어낸 액체연료',
            parentId: '3',
            availableCount: 1,
            selected: false,
          },
          {
            id: '22',
            level: 'facility',
            name: '지어낸 발전기',
            parentId: '5',
            facilityCodeId: '2',
            availableCount: 1,
            selected: false,
            hasFactor: true,
            hasData: false,
          },
        ],
      });
    const before = server.count(TREE);
    await saveConfirmed();
    await waitFor(() => expect(notice()).toBe(words.badNodes));
    expect(server.count(TREE)).toBe(before + 1);
    await waitFor(() =>
      expect(box('지어낸 발전기').getAttribute('aria-checked')).toBe('false'),
    );
    expect(screen.queryByTestId('chosen-20')).toBeNull();
    expect(screen.queryByTestId('chosen-22')).toBeNull();
  });

  it('422 fields.year → 「고를 수 없는 연도예요」 + 올해로(onYear)', async () => {
    const { server, years } = setup(fakeSelectionOptions(), { year: 2024 });
    await ready();
    server.override[SAVE(2024)] = () =>
      refusal(422, 'VALIDATION_ERROR', { year: ['지어낸'] });
    await saveConfirmed();
    await waitFor(() => expect(years).toEqual([2026]));
    expect(notice()).toBe(words.badYear);
  });

  it('회사 거절 두 역할: 첫 읽기 → 화면 자리 회사 글(고객사·운영 관리자) · 저장 거절 → 한 줄', async () => {
    setup({ thisYear: 2026, company: 'COMPANY_AMBIGUOUS' });
    expect((await screen.findByTestId('company-refusal')).textContent).toBe(
      GHG_TEXT.company.ambiguous,
    );
    cleanup();
    setup({ thisYear: 2026, company: 'COMPANY_INACTIVE' }, { operator: true });
    expect((await screen.findByTestId('company-refusal')).textContent).toBe(
      GHG_TEXT.companyOperator.inactive,
    );
    cleanup();
    const { server } = setup(fakeSelectionOptions(), { operator: true });
    await ready();
    server.override[SAVE(2026)] = () => refusal(400, 'COMPANY_NOT_FOUND');
    await saveConfirmed();
    await waitFor(() =>
      expect(notice()).toBe(GHG_TEXT.companyOperator.not_found),
    );
  });
});

describe('S17 연도·나가기·읽기 실패', () => {
  it('해마다 따로: 연도 바꿈(바꾼 것 없음) → 바로 그 해 트리를 새로 읽음(앞 해 고름 0)', async () => {
    const { server, years } = setup({
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    await ready();
    expect(screen.getByTestId('chosen-20')).toBeTruthy();
    pickYear(2025);
    expect(years).toEqual([2025]);
    await waitFor(() => expect(screen.queryByTestId('chosen-20')).toBeNull());
    expect(server.calls.at(-1)!.query.get('year')).toBe('2025');
  });

  it('바꾼 것이 있으면 연도 바꿈·[취소] 확인 — 「계속 고르기」는 그대로·초점 돌림, Enter 는 나감', async () => {
    const { onCancel, years } = setup();
    const save = await ready();
    void save;
    fireEvent.click(box('지어낸 보일러'));
    pickYear(2025);
    const dialog = await screen.findByTestId('leave-confirm');
    expect(dialog.textContent).toContain(words.leaveConfirm);
    // GX2 S12-05: 확인 창 꼴(ghg-inventory ConfirmModal 과 같이) — 위 64 · 좌우 16 · 아래 32 · 글↔단추 32 · 머리 text-secondary.
    for (const name of ['pt-16', 'px-4', 'pb-8'])
      expect(dialog.className, name).toContain(name);
    expect(dialog.querySelector('form')!.className).toContain('gap-8');
    expect(
      within(dialog).getByRole('heading', { name: words.leaveConfirm })
        .className,
    ).toContain('text-text-secondary');
    fireEvent.click(within(dialog).getByRole('button', { name: words.stay }));
    await waitFor(() =>
      expect(screen.queryByTestId('leave-confirm')).toBeNull(),
    );
    expect(years).toEqual([]);
    const cancel = screen.getByRole('button', { name: words.cancel });
    fireEvent.click(cancel);
    const again = await screen.findByTestId('leave-confirm');
    fireEvent.click(within(again).getByRole('button', { name: words.stay }));
    await waitFor(() => expect(document.activeElement).toBe(cancel));
    expect(onCancel).not.toHaveBeenCalled();
    fireEvent.click(cancel);
    fireEvent.submit(
      (await screen.findByTestId('leave-confirm')).querySelector('form')!,
    );
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('바꾼 것이 없으면 [취소] 는 바로 onCancel', async () => {
    const { onCancel } = setup();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: words.cancel }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('leave-confirm')).toBeNull();
  });

  it('첫 읽기 실패만 화면 자리 + 다시 시도 → 판', async () => {
    const server = fakeGhgServer({ thisYear: 2026, ...fakeSelectionOptions() });
    server.override[TREE] = [unreachable];
    render(
      <IndexSettingsScreen
        port={portsOf(server).selection}
        year={2026}
        years={YEARS}
        onSaved={vi.fn()}
        onCancel={vi.fn()}
        onYear={vi.fn()}
        onOrganization={vi.fn()}
      />,
    );
    expect((await screen.findByTestId('load-failure')).textContent).toContain(
      words.loadFailed,
    );
    fireEvent.click(
      screen.getByRole('button', { name: GHG_TEXT.common.retry }),
    );
    await ready();
    expect(screen.queryByTestId('load-failure')).toBeNull();
  });

  it('다시 읽기 실패(연도 바꿈) → 한 줄 notice · 판 그대로 · 그 판으로 [저장]은 PUT 대신 다시 읽음', async () => {
    const { server } = setup({
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    await ready();
    server.override[TREE] = [unreachable, unreachable];
    pickYear(2025);
    await waitFor(() => expect(notice()).toBe(words.reloadFailed));
    expect(screen.queryByTestId('load-failure')).toBeNull();
    expect(screen.getByTestId('chosen-20')).toBeTruthy();
    const trees = server.count(TREE);
    await saveConfirmed();
    await waitFor(() => expect(server.count(TREE)).toBe(trees + 1));
    expect(server.count(SAVE(2025))).toBe(0);
    expect(server.count(SAVE(2026))).toBe(0);
  });
  it('늦게 온 앞 해 답은 버린다(검증 B1): 2026 → 2025(느림) → 2024 — 판·notice 는 2024', async () => {
    const { server } = setup({
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    });
    await ready();
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[TREE] = [
      async () => {
        await gate;
        return json(200, {
          year: 2025,
          nodes: [
            {
              id: '1',
              level: 'scope',
              name: '지어낸 직접배출',
              parentId: null,
              availableCount: 1,
              selected: false,
            },
            {
              id: '5',
              level: 'activity',
              name: '지어낸 액체연료',
              parentId: '1',
              availableCount: 1,
              selected: false,
            },
            {
              id: '22',
              level: 'facility',
              name: '지어낸 발전기',
              parentId: '5',
              facilityCodeId: '2',
              availableCount: 1,
              selected: true,
              hasFactor: true,
              hasData: false,
            },
          ],
        });
      },
      () => json(200, { year: 2024, nodes: [] }),
    ];
    pickYear(2025);
    pickYear(2024);
    await waitFor(() =>
      expect(screen.queryByTestId('empty-pool')).not.toBeNull(),
    );
    await act(async () => {
      release();
      await gate;
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(
      (
        screen.getByRole('combobox', {
          name: words.yearLabel,
        }) as HTMLSelectElement
      ).value,
    ).toBe('2024');
    expect(screen.queryByTestId('chosen-22')).toBeNull();
    expect(screen.queryByTestId('empty-pool')).not.toBeNull();
    expect(notice()).toBe('');
  });
});

describe('S17 468 접음(밴드 W12-1a ①)', () => {
  /** 다음 응답 하나를 붙잡는 문 — release 하면 그 답(body)을 낸다. */
  function hold(
    server: ReturnType<typeof setup>['server'],
    key: string,
    body: unknown,
  ) {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[key] = [
      async () => {
        await gate;
        return json(200, body);
      },
    ];
    return () => release();
  }
  const up = (id: string, level: string, parentId: string | null) => ({
    id,
    level,
    name: `지어낸 ${id}단`,
    parentId,
    availableCount: 1,
    selected: false,
  });

  it('B1: 못 고르는 잎의 까닭은 이름 아래 둘째 줄 — 이름 요소에 truncate 0, 까닭은 이름과 다른 줄 요소', async () => {
    setup(fakeSelectionOptions());
    await ready();
    fireEvent.click(screen.getByRole('button', { name: /지어낸 이동연소/ }));
    fireEvent.click(screen.getByRole('button', { name: /지어낸 도로수송/ }));
    const name = screen.getByTestId('ghg-name-24');
    const why = screen.getByTestId('ghg-why-line-24');
    expect(name.textContent).toBe('지어낸 사업장 차량');
    expect(why.textContent).toBe(words.noFactor);
    expect(name.className).not.toContain('truncate');
    expect(name.parentElement!.contains(why)).toBe(false);
    expect(why.parentElement!.contains(name)).toBe(true);
    expect(why.parentElement!.className).toContain('flex-col');
    for (const id of ['1', '4', '6'])
      expect(screen.getByTestId(`ghg-name-${id}`).className).not.toContain(
        'truncate',
      );
  });

  it('D6·D7·D8·D9: 연도는 공용 NativeSelect · 「선택한 인덱스」 머리는 카드 머리 토큰 · ✕ 열 머리 칸 밑줄 · 경고는 머리 + 회색 몸', async () => {
    const options = {
      ...fakeSelectionOptions(),
      chosen: { 2026: ['20'] },
    };
    const { server } = setup(options);
    server.selectionData.add('20');
    const save = await ready();
    const year = screen.getByRole('combobox', { name: words.yearLabel });
    expect(year.className).toContain('appearance-none');
    expect(year.parentElement!.querySelector('svg')).not.toBeNull();
    expect(
      screen.getByRole('heading', { name: words.chosenTitle }).className,
    ).toContain('text-style-pre-heading-02');
    const head = screen.getByTestId('chosen-remove-head');
    expect(head.className).not.toContain('sr-only');
    expect(head.className).toContain('border-y');
    expect(head.textContent).toBe(words.removeColumn);
    fireEvent.click(box('지어낸 보일러'));
    fireEvent.click(save);
    const dialog = await screen.findByTestId('data-warning');
    expect(within(dialog).getByRole('heading').textContent).toBe(
      words.dataWarning(1),
    );
    expect(words.dataWarning(1)).toBe('데이터가 있는 인덱스 1개를 빼요');
    const body = within(dialog).getByText(words.dataWarningBody);
    expect(body.className).toContain('text-text-tertiary');
    expect(dialog.getAttribute('aria-describedby')).toBe(body.id);
  });

  it('R4·M1: 검색 중 부모 체크는 보이는 잎만 — 숨은 고를 수 있는 잎은 더하지 않고 숨은 고른 잎은 빼지 않음', async () => {
    setup({ ...fakeSelectionOptions(), chosen: { 2026: ['22'] } });
    await ready();
    fireEvent.change(screen.getByLabelText(words.searchLabel), {
      target: { value: '보일러' },
    });
    expect(screen.queryByTestId('ghg-node-22')).toBeNull();
    // 표시도 보이는 잎 기준 — 숨은 고른 잎(22)으로 mixed 가 되지 않음(검증 A1).
    expect(box('지어낸 액체연료').getAttribute('aria-checked')).toBe('false');
    fireEvent.click(box('지어낸 액체연료'));
    expect(screen.getByTestId('chosen-20')).toBeTruthy();
    expect(screen.getByTestId('chosen-22')).toBeTruthy();
    expect(box('지어낸 액체연료').getAttribute('aria-checked')).toBe('true');
    fireEvent.click(box('지어낸 액체연료'));
    expect(screen.queryByTestId('chosen-20')).toBeNull();
    expect(screen.getByTestId('chosen-22')).toBeTruthy();
    cleanup();
    setup(fakeSelectionOptions());
    await ready();
    fireEvent.change(screen.getByLabelText(words.searchLabel), {
      target: { value: '보일러' },
    });
    fireEvent.click(box('지어낸 액체연료'));
    expect(screen.getByTestId('chosen-20')).toBeTruthy();
    expect(screen.queryByTestId('chosen-22')).toBeNull();
  });

  it('R5·M4: 고를 잎 0 · 골라진 잎 0 인 배출활동 체크는 흐림(disabled) — 고를 잎이 있으면 켜짐', async () => {
    setup(fakeSelectionOptions());
    await ready();
    expect(box('지어낸 액체연료').hasAttribute('disabled')).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /지어낸 이동연소/ }));
    const road = box('지어낸 도로수송');
    expect(road.hasAttribute('disabled')).toBe(true);
    fireEvent.click(road);
    expect(screen.getByText(words.noneChosen)).toBeTruthy();
  });

  it('M2: 저장 중 연도·[취소]·체크·「전체 해제」·행 ✕ 막음 — 답이 오면 onSaved', async () => {
    const { server, onSaved } = setup(fakeSelectionOptions());
    const save = await ready();
    fireEvent.click(box('지어낸 보일러'));
    const release = hold(server, SAVE(2026), {
      selected: 1,
      hiddenWithData: 0,
    });
    await saveConfirmed(save);
    // 부하 때 기본 1s 를 넘김(검증 R2) — router.test 의 WAIT 꼴.
    await waitFor(
      () =>
        expect(
          screen
            .getByRole('combobox', { name: words.yearLabel })
            .hasAttribute('disabled'),
        ).toBe(true),
      { timeout: 8_000 },
    );
    expect(
      screen
        .getByRole('button', { name: words.cancel })
        .hasAttribute('disabled'),
    ).toBe(true);
    expect(box('지어낸 보일러').hasAttribute('disabled')).toBe(true);
    expect(box('지어낸 액체연료').hasAttribute('disabled')).toBe(true);
    expect(
      screen
        .getByRole('button', { name: words.clearAll })
        .hasAttribute('disabled'),
    ).toBe(true);
    expect(
      screen
        .getByRole('button', { name: words.removeChosen('지어낸 보일러') })
        .hasAttribute('disabled'),
    ).toBe(true);
    fireEvent.click(box('지어낸 보일러'));
    expect(screen.getByTestId('chosen-20')).toBeTruthy();
    await act(async () => {
      release();
    });
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(2026));
    expect(bodies(server)).toEqual([{ facilityNodeIds: [20] }]);
  });

  it('M3: 연도 다시 읽는 동안 판 aria-busy · 체크 막음 — 도착하면 풀림(고친 것을 말없이 덮지 않음)', async () => {
    const { server } = setup(fakeSelectionOptions());
    await ready();
    expect(screen.getByTestId('index-board').hasAttribute('aria-busy')).toBe(
      false,
    );
    const release = hold(server, TREE, {
      year: 2025,
      nodes: [
        up('1', 'scope', null),
        up('3', 'source_type', '1'),
        up('5', 'activity', '3'),
        {
          ...up('20', 'facility', '5'),
          name: '지어낸 보일러',
          facilityCodeId: '1',
          hasFactor: true,
          hasData: false,
        },
      ],
    });
    pickYear(2025);
    await waitFor(() =>
      expect(screen.getByTestId('index-board').getAttribute('aria-busy')).toBe(
        'true',
      ),
    );
    expect(box('지어낸 보일러').hasAttribute('disabled')).toBe(true);
    expect(box('지어낸 액체연료').hasAttribute('disabled')).toBe(true);
    fireEvent.click(box('지어낸 보일러'));
    expect(screen.queryByTestId('chosen-20')).toBeNull();
    expect(
      screen
        .getByRole('button', { name: words.clearAll })
        .hasAttribute('disabled'),
    ).toBe(true);
    await act(async () => {
      release();
    });
    await waitFor(() =>
      expect(screen.getByTestId('index-board').hasAttribute('aria-busy')).toBe(
        false,
      ),
    );
    expect(box('지어낸 보일러').hasAttribute('disabled')).toBe(false);
  });
});
