// @vitest-environment jsdom
// S19 자산/시설 판(밴드 W12-0b1 ③)의 단위 칸 — S12-07(값 파일 ⑧, sid:MARC-ENT-644 덧) 드롭다운 하나(판의 나머지는 GhgIndexPoolScreen.test.tsx).
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
  fakeCodes,
  fakeGhgServer,
  fakePoolOptions,
  portsOf,
} from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import type { PoolOptions } from '../../../entities/ghg/model/index.ts';
import { FacilityPanel } from './FacilityPanel.tsx';

afterEach(cleanup);

const words = GHG_TEXT.pool;

function panel(options: PoolOptions, leafId: string | null = null) {
  const server = fakeGhgServer();
  render(
    <FacilityPanel
      port={portsOf(server).pool}
      options={options}
      codes={fakeCodes()}
      leafId={leafId}
      parentId="5"
      thisYear={2026}
      onCreated={vi.fn()}
      onSaved={vi.fn()}
      onDeleted={vi.fn()}
      onCancelNew={vi.fn()}
    />,
  );
  return server;
}
const unitBox = () =>
  screen.getByRole('combobox', { name: words.unit }) as HTMLSelectElement;

describe('S19 자산/시설 판 — S12-07 단위 칸 하나', () => {
  it('드롭다운 하나(「단위 종류」 칸 0) · 빈 값 「선택안함」 · 종류 이름이 묶음 머리(서버 차례 · 모르는 kind 는 글자 그대로) · 묶음 안 = 그 종류 단위', () => {
    const options = fakePoolOptions();
    options.units.push({ kind: 'heat', units: ['Gcal'] });
    panel(options);
    const box = unitBox();
    expect(screen.getAllByRole('combobox')).toHaveLength(2);
    expect(document.body.textContent).not.toContain('단위 종류');
    expect(box.value).toBe('');
    expect(box.options[0]!.textContent).toBe(words.unitNone);
    expect(box.options[0]!.value).toBe('');
    const groups = [...box.querySelectorAll('optgroup')];
    expect(groups.map((group) => group.label)).toStrictEqual([
      '질량',
      '부피',
      '에너지',
      '전력',
      'heat',
    ]);
    expect(
      groups.map((group) =>
        [...group.querySelectorAll('option')].map((one) => one.textContent),
      ),
    ).toStrictEqual(options.units.map((one) => one.units));
    // 묶음 밖 고를 거리는 「선택안함」 하나뿐.
    expect(
      [...box.children].filter((child) => child.tagName === 'OPTION'),
    ).toHaveLength(1);
  });

  it('ⓘ 툴팁: 이름 「단위 설명」 · 설명 = 값 파일 글 · 머리는 「단위」 + 필수 점', () => {
    panel(fakePoolOptions());
    const info = screen.getByRole('button', { name: words.unitInfoLabel });
    expect(info.getAttribute('aria-describedby')).toBe(
      'ghg-leaf-unit-info-text',
    );
    expect(
      document.getElementById('ghg-leaf-unit-info-text')!.textContent,
    ).toBe(words.unitInfo);
    expect(words.unitInfo).toBe(
      '배출량을 셀 때 쓰는 투입량의 단위예요. 하나만 고를 수 있어요.',
    );
    const label = document.querySelector('label[for="ghg-leaf-unit"]')!;
    expect(label.textContent).toBe(words.unit);
    expect(label.querySelector('[data-required-mark]')).not.toBeNull();
  });

  it('고르면 종류는 그 묶음에서(에너지 GJ → kind energy) · 「선택안함」으로 되돌리면 둘 다 빔 → 저장은 필수 글 + 단위 칸 초점 · 요청 0', async () => {
    const server = panel(fakePoolOptions());
    fireEvent.change(
      screen.getByRole('combobox', { name: words.facilityCode }),
      {
        target: { value: '3' },
      },
    );
    fireEvent.change(unitBox(), { target: { value: 'energy|GJ' } });
    expect(unitBox().value).toBe('energy|GJ');
    expect(unitBox().selectedOptions[0]!.textContent).toBe('GJ');
    expect(
      (unitBox().selectedOptions[0]!.parentElement as HTMLOptGroupElement)
        .label,
    ).toBe('에너지');
    fireEvent.change(unitBox(), { target: { value: '' } });
    expect(unitBox().value).toBe('');
    fireEvent.click(screen.getByRole('button', { name: words.save }));
    await waitFor(() =>
      expect(screen.getByTestId('ghg-leaf-unit-error').textContent).toBe(
        words.required,
      ),
    );
    expect(document.activeElement?.id).toBe('ghg-leaf-unit');
    expect(unitBox().getAttribute('aria-invalid')).toBe('true');
    expect(server.count('POST /inventory/admin/ghg-index/facilities')).toBe(0);
    fireEvent.change(unitBox(), { target: { value: 'mass|kg' } });
    expect(screen.queryByTestId('ghg-leaf-unit-error')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: words.save }));
    await waitFor(() =>
      expect(
        server.bodies('POST /inventory/admin/ghg-index/facilities'),
      ).toHaveLength(1),
    );
    expect(
      (
        server.bodies('POST /inventory/admin/ghg-index/facilities')[0] as {
          unit: unknown;
        }
      ).unit,
    ).toStrictEqual({ kind: 'mass', unit: 'kg' });
  });

  it('있는 잎을 열면 그 단위가 골라져 보임 · 지금 값이 목록에 없으면 그 글자 그대로 한 줄 더함(지움 0)', async () => {
    panel(fakePoolOptions(), '20');
    await waitFor(() => expect(unitBox().value).toBe('volume|kL'));
    expect(unitBox().selectedOptions[0]!.textContent).toBe('kL');
    cleanup();

    const options = fakePoolOptions();
    options.units = options.units.map((one) =>
      one.kind === 'volume' ?
        { ...one, units: one.units.filter((unit) => unit !== 'kL') }
      : one,
    );
    panel(options, '20');
    await waitFor(() => expect(unitBox().value).toBe('volume|kL'));
    const extra = unitBox().selectedOptions[0]!;
    expect(extra.textContent).toBe('kL');
    expect(extra.parentElement!.tagName).toBe('SELECT');
    expect(
      [...unitBox().querySelectorAll('option')].filter(
        (one) => one.textContent === 'kL',
      ),
    ).toHaveLength(1);
  });

  it('목록이 비면 드롭다운 막힘 · 자리 글 「선택안함」 그대로', () => {
    const options = fakePoolOptions();
    options.units = [];
    panel(options);
    expect(unitBox().disabled).toBe(true);
    expect(unitBox().selectedOptions[0]!.textContent).toBe(words.unitNone);
  });
});
