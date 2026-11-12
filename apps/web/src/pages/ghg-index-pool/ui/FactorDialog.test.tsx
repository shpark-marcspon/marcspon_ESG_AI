// @vitest-environment jsdom
// S20 배출계수 추가·수정·읽기 모달(밴드 W12-0b1 ③ — 발주서 §3 9). 진짜 풀 실어댑터 + 가짜 온실가스 서버(fakePool 씨앗 · fakePoolOptions).
//   필수(누를 때 · 첫 오류 칸 초점 · 요청 0) · 켠 가스 0 · 숫자 글자(지수 거절, 보낼 때 글자 그대로) · 순발열량(켜면 값·단위, 산식 글) ·
//   서버 422 fields.<칸>·gases.<가스>.<칸> → 같은 칸 글(R6) · 읽기 → 수정 → PUT 새 판 · 취소 확인 ·
//   R4: 있는 계수에서 순발열량 토글·투입 단위 종류를 바꾸면 factorUnit 을 null 로(서버 기본) — 아니면 서버 422 fields.factorUnit.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  POOL_GASES,
  fakeGhgServer,
  fakePoolOptions,
  portsOf,
  refusal,
} from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { FactorDialog } from './FactorDialog.tsx';

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

const words = GHG_TEXT.factor;
const NEW = 'POST /inventory/admin/ghg-index/facilities/24/factors';
const EDIT = 'PUT /inventory/admin/ghg-factors/21';

function setup(factorId: string | null = null) {
  const server = fakeGhgServer();
  const onSaved = vi.fn();
  const onClose = vi.fn();
  render(
    <FactorDialog
      port={portsOf(server).pool}
      options={fakePoolOptions()}
      facilityId={factorId === null ? '24' : '20'}
      factorId={factorId}
      thisYear={2026}
      returnFocus={null}
      onSaved={onSaved}
      onClose={onClose}
    />,
  );
  return { server, onSaved, onClose };
}

const dialog = () => screen.getByTestId('factor-dialog');
const box = (label: string) =>
  within(dialog()).getByRole('combobox', { name: label });
const text = (label: string) =>
  within(dialog()).getByRole('textbox', { name: label });
const pick = (label: string, value: string) =>
  fireEvent.change(box(label), { target: { value } });
const type = (element: HTMLElement, value: string) =>
  fireEvent.change(element, { target: { value } });
const gasSwitch = (gas: string) =>
  within(dialog()).getByRole('switch', { name: words.gasToggle(gas) });
const save = () =>
  fireEvent.click(within(dialog()).getByRole('button', { name: words.save }));
const errorOf = (field: string) =>
  screen.queryByTestId(`ghg-factor-${field.replace(/\./g, '-')}-error`)
    ?.textContent ?? null;

/** 새 계수 칸을 다 채운다(가스 CO2 하나 켬 — 값은 지어냄). */
function fillNew() {
  type(within(dialog()).getByLabelText(words.name), '지어낸 새 계수');
  type(within(dialog()).getByLabelText(words.source), '지어낸 출처');
  pick(words.baseYear, '2024');
  pick(words.tier, '2');
  pick(words.country, 'KR');
  pick(words.industry, 'other');
  pick(`${words.inputUnit} ${words.unitKind}`, 'volume');
  pick(`${words.inputUnit} ${words.unitName}`, 'kL');
  fireEvent.click(gasSwitch('CO2'));
  type(text(words.gasFactor('CO2')), '74100.5');
  type(text(words.gasGwp('CO2')), '1');
}

describe('S20 배출계수 — 새로', () => {
  it('[저장]은 늘 켬 · 빈 칸이면 칸마다 「필수 입력 항목이에요」 · 첫 오류 칸(배출계수명) 초점 · 켠 가스 0 글 · 요청 0', async () => {
    const { server } = setup();
    expect(
      within(dialog()).getByRole('button', { name: words.save }),
    ).not.toHaveProperty('disabled', true);
    save();
    expect(errorOf('name')).toBe(words.required);
    expect(errorOf('source')).toBe(words.required);
    expect(errorOf('baseYear')).toBe(words.required);
    expect(errorOf('inputUnit')).toBe(words.required);
    expect(errorOf('gases')).toBe(words.noGas);
    await waitFor(() =>
      expect(document.activeElement?.id).toBe('ghg-factor-name'),
    );
    expect(server.count(NEW)).toBe(0);
  });

  it('기준연도 1990~올해 · Tier 1·2·3 · 배출량 기준단위 기본값 · 가스 일곱(켠 줄만 칸 살아남)', () => {
    setup();
    const years = within(box(words.baseYear))
      .getAllByRole('option')
      .map((o) => o.getAttribute('value'))
      .filter(Boolean);
    expect(years[0]).toBe('2026');
    expect(years.at(-1)).toBe('1990');
    expect(years).toHaveLength(37);
    expect(
      within(box(words.tier))
        .getAllByRole('option')
        .map((o) => o.getAttribute('value'))
        .filter(Boolean),
    ).toEqual(['1', '2', '3']);
    expect((box(words.emissionUnit) as HTMLSelectElement).value).toBe(
      'tCO2-eq',
    );
    expect(
      [...dialog().querySelectorAll('tr[data-gas]')].map((r) =>
        r.getAttribute('data-gas'),
      ),
    ).toEqual(POOL_GASES);
    expect((text(words.gasFactor('CH4')) as HTMLInputElement).disabled).toBe(
      true,
    );
    fireEvent.click(gasSwitch('CH4'));
    expect((text(words.gasFactor('CH4')) as HTMLInputElement).disabled).toBe(
      false,
    );
  });

  it('숫자 칸: 지수·0 → 「0보다 큰 숫자를…」(요청 0) · 고치면 POST 본문 깊은 같음(Decimal 글자 그대로 · 끈 가스는 {gas, enabled:false})', async () => {
    const { server, onSaved } = setup();
    fillNew();
    type(text(words.gasFactor('CO2')), '7.41e4');
    type(text(words.gasGwp('CO2')), '0');
    save();
    expect(errorOf('gases.CO2.factor')).toBe(words.number);
    expect(errorOf('gases.CO2.gwp')).toBe(words.number);
    expect(server.count(NEW)).toBe(0);
    type(text(words.gasFactor('CO2')), '74100.50');
    type(text(words.gasGwp('CO2')), '1');
    save();
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(server.bodies(NEW)).toEqual([
      {
        name: '지어낸 새 계수',
        source: '지어낸 출처',
        baseYear: 2024,
        tier: 2,
        countryCode: 'KR',
        industryCode: 'other',
        inputUnit: { kind: 'volume', unit: 'kL' },
        emissionUnit: { kind: 'mass', unit: 'tCO2-eq' },
        ncvEnabled: false,
        ncv: null,
        ncvUnit: null,
        factorUnit: null,
        note: '',
        gases: POOL_GASES.map((gas) =>
          gas === 'CO2' ?
            { gas, enabled: true, factor: '74100.50', gwp: '1' }
          : { gas, enabled: false },
        ),
      },
    ]);
  });

  it('순발열량: 켜면 값·단위 필수 · 산식 글이 켬 꼴로 · 계수 칸 머리는 옵션 기본(켬 kg/TJ · 끔 「kg/<투입 단위>」 글자 그대로)', async () => {
    const { server } = setup();
    fillNew();
    const head = () => screen.getByTestId('factor-unit-head').textContent;
    expect(head()).toBe(words.factorUnit('kg/<투입 단위>'));
    expect(dialog().querySelector('tr[data-gas="CO2"]')!.textContent).toContain(
      words.formulaWithoutNcv('CO2'),
    );
    fireEvent.click(within(dialog()).getByRole('switch', { name: words.ncv }));
    expect(head()).toBe(words.factorUnit('kg/TJ'));
    expect(dialog().querySelector('tr[data-gas="CO2"]')!.textContent).toContain(
      words.formulaWithNcv('CO2'),
    );
    save();
    expect(errorOf('ncv')).toBe(words.required);
    expect(errorOf('ncvUnit')).toBe(words.required);
    expect(server.count(NEW)).toBe(0);
    type(
      within(dialog()).getByLabelText(words.ncv, { selector: 'input' }),
      '35.3',
    );
    pick(`${words.ncvUnit} ${words.unitKind}`, 'energy');
    pick(`${words.ncvUnit} ${words.unitName}`, 'MJ');
    save();
    await waitFor(() => expect(server.count(NEW)).toBe(1));
    expect(server.bodies(NEW)[0]).toMatchObject({
      ncvEnabled: true,
      ncv: '35.3',
      ncvUnit: { kind: 'energy', unit: 'MJ' },
      factorUnit: null,
    });
  });

  it('서버 422: fields.name · gases.<가스>.factor(점 열쇠) → 같은 칸 글 · 첫 칸 초점 · 서버 message 0(R6)', async () => {
    const { server, onSaved } = setup();
    server.override[NEW] = () =>
      refusal(422, 'VALIDATION_ERROR', {
        name: ['지어낸'],
        'gases.CO2.factor': ['지어낸'],
      });
    fillNew();
    save();
    await waitFor(() =>
      expect(errorOf('gases.CO2.factor')).toBe(words.invalid),
    );
    expect(errorOf('name')).toBe(words.invalid);
    expect(document.activeElement?.id).toBe('ghg-factor-name');
    expect(onSaved).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toContain('지어낸-');
    // 그 칸을 고치면 그 칸 글만 걷힌다.
    type(text(words.gasFactor('CO2')), '74100');
    expect(errorOf('gases.CO2.factor')).toBeNull();
    expect(errorOf('name')).toBe(words.invalid);
  });

  it('취소: 바꾼 것이 없으면 바로 닫음 · 있으면 「저장하지 않고 닫을까요?」 → 계속 입력 / 닫기', async () => {
    const first = setup();
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.cancel }),
    );
    expect(first.onClose).toHaveBeenCalledTimes(1);
    cleanup();
    const { onClose } = setup();
    type(within(dialog()).getByLabelText(words.name), '지어낸');
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.cancel }),
    );
    const leave = await screen.findByTestId('factor-leave-dialog');
    expect(leave.textContent).toContain(words.leaveConfirm);
    fireEvent.click(within(leave).getByRole('button', { name: words.stay }));
    await waitFor(() =>
      expect(screen.queryByTestId('factor-leave-dialog')).toBeNull(),
    );
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.cancel }),
    );
    fireEvent.click(
      within(await screen.findByTestId('factor-leave-dialog')).getByRole(
        'button',
        { name: words.leave },
      ),
    );
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe('S20 배출계수 — 있는 계수', () => {
  it('읽기 꼴: 칸 꺼짐 · 「버전 1」(GX2 S12-08) · [수정] → 쓰기 꼴 → PUT 새 판(본문 깊은 같음)', async () => {
    const { server, onSaved } = setup('21');
    await waitFor(() =>
      expect(screen.getByTestId('factor-version').textContent).toBe(
        words.version(1),
      ),
    );
    expect(words.version(1)).toBe('버전 1');
    expect(dialog().getAttribute('data-mode')).toBe('view');
    const name = within(dialog()).getByLabelText(
      words.name,
    ) as HTMLInputElement;
    expect(name.value).toBe('지어낸 경유 계수');
    expect(name.disabled).toBe(true);
    expect(
      within(dialog()).queryByRole('button', { name: words.save }),
    ).toBeNull();
    fireEvent.click(within(dialog()).getByRole('button', { name: words.edit }));
    expect(dialog().getAttribute('data-mode')).toBe('edit');
    expect(name.disabled).toBe(false);
    type(name, '지어낸 경유 계수 고침');
    save();
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(onSaved.mock.calls[0]![0]).toMatchObject({ version: 2 });
    expect(server.bodies(EDIT)).toHaveLength(1);
    expect(server.bodies(EDIT)[0]).toMatchObject({
      name: '지어낸 경유 계수 고침',
      ncvEnabled: true,
      ncv: '35.3',
      factorUnit: 'kg/TJ',
      gases: expect.arrayContaining([
        { gas: 'CO2', enabled: true, factor: '1.5', gwp: '1' },
        { gas: 'HFCs', enabled: false },
      ]),
    });
  });

  it('R4: 순발열량을 끄면 factorUnit 이 null(서버 기본 — 머리 글도 기본) → PUT 이 지남 · 투입 단위 종류를 바꿔도 null', async () => {
    const { server, onSaved } = setup('21');
    await screen.findByTestId('factor-version');
    fireEvent.click(within(dialog()).getByRole('button', { name: words.edit }));
    expect(screen.getByTestId('factor-unit-head').textContent).toBe(
      words.factorUnit('kg/TJ'),
    );
    fireEvent.click(within(dialog()).getByRole('switch', { name: words.ncv }));
    expect(screen.getByTestId('factor-unit-head').textContent).toBe(
      words.factorUnit('kg/<투입 단위>'),
    );
    save();
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    expect(server.bodies(EDIT)[0]).toMatchObject({
      ncvEnabled: false,
      ncv: null,
      ncvUnit: null,
      factorUnit: null,
    });
    cleanup();

    // 순발열량은 그대로 두고 투입 단위 종류만 바꿈 — factorUnit null(그 종류 안 단위만 바꾸면 그대로).
    const second = setup('21');
    await screen.findByTestId('factor-version');
    fireEvent.click(within(dialog()).getByRole('button', { name: words.edit }));
    pick(`${words.inputUnit} ${words.unitName}`, 'L');
    pick(`${words.inputUnit} ${words.unitKind}`, 'mass');
    pick(`${words.inputUnit} ${words.unitName}`, 't');
    save();
    await waitFor(() => expect(second.onSaved).toHaveBeenCalledTimes(1));
    expect(second.server.bodies(EDIT)[0]).toMatchObject({
      inputUnit: { kind: 'mass', unit: 't' },
      factorUnit: null,
    });
  });

  it('R4: 서버가 factorUnit 을 거르면(422 fields.factorUnit) 계수 칸 머리 아래에 그 칸 글 · 초점은 머리', async () => {
    const { server } = setup('21');
    server.override[EDIT] = () =>
      refusal(422, 'VALIDATION_ERROR', { factorUnit: ['지어낸'] });
    await screen.findByTestId('factor-version');
    fireEvent.click(within(dialog()).getByRole('button', { name: words.edit }));
    save();
    await waitFor(() => expect(errorOf('factorUnit')).toBe(words.invalid));
    expect(document.activeElement).toBe(screen.getByTestId('factor-unit-head'));
  });

  it('읽기 실패 → 「배출계수를 불러오지 못했어요…」 · [수정] 꺼짐', async () => {
    const server = fakeGhgServer();
    server.override['GET /inventory/admin/ghg-factors/21'] = () =>
      refusal(404, 'NOT_FOUND');
    render(
      <FactorDialog
        port={portsOf(server).pool}
        options={fakePoolOptions()}
        facilityId="20"
        factorId="21"
        thisYear={2026}
        returnFocus={null}
        onSaved={() => {}}
        onClose={() => {}}
      />,
    );
    await waitFor(() =>
      expect(within(dialog()).getByRole('alert').textContent).toBe(
        words.loadFailed,
      ),
    );
    expect(
      (
        within(dialog()).getByRole('button', {
          name: words.edit,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });
});

describe('단위 종류 글(밴드 W12-0b2 ① — 디자인 74 대조 B1)', () => {
  it('투입량 기준단위 종류 칸: 질량·부피·에너지·전력(영문 kind 0) · 모르는 kind 는 글자 그대로', () => {
    const options = fakePoolOptions();
    options.units.push({ kind: 'heat', units: ['Gcal'] });
    render(
      <FactorDialog
        port={portsOf(fakeGhgServer()).pool}
        options={options}
        facilityId="24"
        factorId={null}
        thisYear={2026}
        returnFocus={null}
        onSaved={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    const labels = within(box(`${words.inputUnit} ${words.unitKind}`))
      .getAllByRole('option')
      .map((option) => option.textContent);
    expect(labels).toEqual([
      words.unitKind,
      '질량',
      '부피',
      '에너지',
      '전력',
      'heat',
    ]);
  });
});

describe('W12-4 ① 573 드롭다운 꼴 — 공통 NativeSelect(sid:MARC-ENT-430)', () => {
  const OLD = ['h-10', 'rounded-control', 'border-border-secondary'];
  const classes = (element: Element) =>
    (element.getAttribute('class') ?? '').split(/\s+/);
  it('계수 창 고르기 상자마다: appearance-none · 옛 날 select 꼴 0 · 감싼 칸 w-full · ▾ 아이콘 하나 · 빈 [저장] 뒤 aria-invalid="true" + 칸 글', () => {
    setup();
    const boxes = within(dialog()).getAllByRole('combobox');
    expect(boxes.length).toBeGreaterThanOrEqual(5);
    for (const select of boxes) {
      const look = classes(select);
      expect(look).toContain('appearance-none');
      for (const word of OLD) expect(look).not.toContain(word);
      const wrap = select.parentElement!;
      expect(wrap.tagName).toBe('SPAN');
      expect(classes(wrap)).toEqual(
        expect.arrayContaining(['w-full', 'min-w-0']),
      );
      expect(wrap.querySelectorAll('svg')).toHaveLength(1);
    }
    save();
    const invalid = within(dialog())
      .getAllByRole('combobox')
      .filter((select) => select.getAttribute('aria-invalid') === 'true');
    expect(invalid.length).toBeGreaterThan(0);
    for (const select of invalid.filter((one) =>
      one.hasAttribute('aria-describedby'),
    )) {
      const described = select.getAttribute('aria-describedby')!;
      expect(document.getElementById(described)?.textContent).toBeTruthy();
    }
  });
});
