// @vitest-environment jsdom
// S3 데이터 상세(밴드 W12-1b ① — 발주서 §3 2). 진짜 입력 어댑터 + 가짜 온실가스 서버. 자료는 다 지어낸 것.
import type { ReactElement } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render as renderPlain,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { GhgEntryPort } from '../../../entities/ghg/api/index.ts';
import {
  fakeEntryOptions,
  fakeGhgServer,
  fakeHeadquarters,
  fakeSelectionOptions,
  json,
  portsOf,
  refusal,
} from '../../../entities/ghg/api/testing.ts';
import type { FakeGhgServerOptions } from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { Toaster } from '../../../shared/ui/toast/index.ts';
import { EntryDetailDialog, withComma } from './EntryDetailDialog.tsx';
import { COLUMN, minTableWidth } from './EntrySiteBlock.tsx';
import { thumbOf } from './ScrollBar.tsx';

afterEach(cleanup);
/** S12-04: 「저장됐어요」는 공용 토스트 — 화면 host(InventoryScreen) 대신 시험이 <Toaster> 를 곁에 둔다. */
const render = (ui: ReactElement) =>
  renderPlain(
    <>
      {ui}
      <Toaster />
    </>,
  );
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

const words = GHG_TEXT.entry;
const X = '/inventory/scope12/years/2025/indexes/20';
const SAVE_PLANT = `PUT ${X}/sites/2/rows`;
const SAVE_HEAD = `PUT ${X}/sites/1/rows`;
const DETAIL = `GET ${X}`;
const REMOVE = `POST ${X}/rows/delete`;

/** 씨앗: 제1공장(사업장 2)에 코드 1 줄 넷(4·5 행 있음, 6·7 비어 있음), 본사(사업장 1)에 행 하나. */
function options(over: FakeGhgServerOptions = {}): FakeGhgServerOptions {
  const base = fakeEntryOptions();
  const [head, plant] = base.branches!;
  const code = {
    facilityCodeId: '1',
    facilityCode: 'F0001',
    facilityName: '지어낸 보일러',
  };
  return {
    ...base,
    thisYear: 2026,
    branches: [
      head!,
      {
        ...plant!,
        facilities: [
          ...plant!.facilities,
          { id: '5', ...code, detailName: '2호기' },
          { id: '6', ...code, detailName: '3호기' },
          { id: '7', ...code, detailName: '4호기' },
        ],
      },
    ],
    ...over,
  };
}

async function open(
  over: FakeGhgServerOptions = {},
  {
    seed = true,
    operator = false,
    locked = false,
    pool = false,
    wrap = (real: GhgEntryPort): GhgEntryPort => real,
  } = {},
) {
  const server = fakeGhgServer(options(over));
  const ports = portsOf(server);
  const port = ports.entry;
  if (seed) {
    const first = await port.saveRows(2025, '20', '2', [
      {
        siteFacilityId: 4,
        unit: 'kL',
        na: false,
        values: [
          { slot: '2025-01', amount: '12.5', estimated: false },
          { slot: '2025-02', amount: '3', estimated: false },
        ],
      },
      {
        siteFacilityId: 5,
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-02', amount: '8', estimated: false }],
      },
    ]);
    if (first.kind !== 'ok') throw new Error(`심기 실패 ${first.kind}`);
    const headLine = first.value.sites.find((s) => s.siteId === '1')!
      .facilities[0]!;
    const second = await port.saveRows(2025, '20', '1', [
      {
        siteFacilityId: Number(headLine.id),
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-03', amount: '1', estimated: false }],
      },
    ]);
    if (second.kind !== 'ok') throw new Error(`심기 실패 ${second.kind}`);
  }
  if (locked) await port.lock(2025, '20');
  const onClose = vi.fn();
  render(
    <EntryDetailDialog
      port={wrap(port)}
      year={2025}
      nodeId="20"
      operator={operator}
      pool={pool ? ports.pool : null}
      onClose={onClose}
    />,
  );
  return { server, port, onClose };
}

const ready = () => screen.findByTestId('entry-site-2');
const plant = () => within(screen.getByTestId('entry-site-2'));
const headBlock = () => within(screen.getByTestId('entry-site-1'));
const amountCell = (key: string, slot: string) =>
  screen.getByTestId(`entry-amount-${key}:${slot}`) as HTMLInputElement;
const type = (key: string, slot: string, value: string) =>
  fireEvent.change(amountCell(key, slot), { target: { value } });
/** 모달 아래 [저장] 하나(W12-1c ① — sid:MARC-ENT-529). */
const saveAll = () => fireEvent.click(screen.getByTestId('entry-save'));
/** 잠금 아이콘 단추 → (확인 창이 뜨면) 확인. 고객사는 고친 것 없어도 창(R6). */
const lockNow = async () => {
  fireEvent.click(screen.getByRole('button', { name: words.lock }));
  fireEvent.submit(
    (await screen.findByTestId('entry-lock-confirm')).querySelector('form')!,
  );
};
const lastBody = (server: ReturnType<typeof fakeGhgServer>, key: string) =>
  server.bodies(key).at(-1);

const keyOfHead = () =>
  screen
    .getByTestId('entry-site-1')
    .querySelector('[data-testid^="entry-row-"]')!
    .getAttribute('data-testid')!
    .replace('entry-row-', '');
const headLineId = async (port: GhgEntryPort) => {
  const out = await port.detail(2025, '20');
  if (out.kind !== 'ok') throw new Error(`상세 실패 ${out.kind}`);
  return out.value.sites.find((s) => s.siteId === '1')!.rows[0]!.siteFacilityId;
};

/** 상세 읽기를 판(서버 사진)은 부를 때 뜨고 답만 늦게 오게 잡는다 — hold() 뒤 부른 읽기가 release() 까지 멈춘다. */
function lateDetail() {
  let gate: Promise<void> | null = null;
  let open_ = () => {};
  return {
    wrap: (real: GhgEntryPort): GhgEntryPort => ({
      ...real,
      detail: async (...args) => {
        const out = await real.detail(...args);
        if (gate) await gate;
        return out;
      },
    }),
    hold: () => {
      gate = new Promise<void>((resolve) => {
        open_ = resolve;
      });
    },
    release: () =>
      act(async () => {
        open_();
        await new Promise((resolve) => setTimeout(resolve, 0));
      }),
  };
}

describe('늦게 온 읽기(가지 리뷰)', () => {
  /** r2 를 지운다 — 그 뒤 다시 읽기가 답을 못 받은 채 남는다. */
  const removeSecondRow = async (hold: () => void) => {
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.selectLabel('2호기') }),
    );
    fireEvent.click(plant().getByRole('button', { name: words.remove }));
    const confirm = await screen.findByTestId('entry-remove');
    hold();
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.removeOk }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-remove')).toBeNull(),
    );
  };

  it('삭제 뒤 읽기가 늦게 오고 그사이 다른 블록을 저장하면 옛 읽기를 버린다', async () => {
    const late = lateDetail();
    const { server } = await open({}, { wrap: late.wrap });
    await ready();
    const headKey = keyOfHead();
    await removeSecondRow(late.hold);
    await waitFor(() => expect(server.count(REMOVE)).toBe(1));
    type(headKey, '2025-03', '77');
    saveAll();
    await screen.findByTestId('toast');
    await late.release();
    expect(amountCell(headKey, '2025-03').value).toBe('77');
    expect(screen.getByTestId('toast')).toBeTruthy();
  });

  it('삭제 뒤 읽기가 늦게 오고 그사이 잠그면 옛 읽기를 버린다', async () => {
    const late = lateDetail();
    const { server } = await open({}, { wrap: late.wrap });
    await ready();
    await removeSecondRow(late.hold);
    await waitFor(() => expect(server.count(REMOVE)).toBe(1));
    await lockNow();
    await screen.findByTestId('entry-locked');
    await late.release();
    expect(screen.getByTestId('entry-locked')).toBeTruthy();
    expect(amountCell('r1', '2025-01').disabled).toBe(true);
  });
});

describe('블록 저장 본문 — saveBody 그대로', () => {
  it('바뀐 칸만 · 칸은 amount·estimated 둘 다 · 행 unit·na·siteFacilityId · id 정수 · 금액 글자 · 안 바뀐 행 뺌', async () => {
    const { server } = await open();
    await ready();
    type('r1', '2025-02', '4.50');
    saveAll();
    await screen.findByTestId('toast');
    expect(lastBody(server, SAVE_PLANT)).toStrictEqual({
      rows: [
        {
          rowId: 1,
          siteFacilityId: 4,
          unit: 'kL',
          na: false,
          values: [{ slot: '2025-02', amount: '4.50', estimated: false }],
        },
      ],
    });
  });

  it('추정만 바꿔도 칸에 금액이 실린다(S12-03 — 잠금 옆 단추 하나로 켬)', async () => {
    const { server } = await open();
    await ready();
    fireEvent.click(screen.getByTestId('entry-estimated'));
    expect(
      screen.getByTestId('entry-estimated').getAttribute('aria-pressed'),
    ).toBe('true');
    saveAll();
    await screen.findByTestId('toast');
    // 본문 전체: 제1공장 저장된 행 둘(r1·r2) — 모든 칸(빈 칸 포함) 추정 참 · 금액은 심은 값 그대로.
    const MONTHS = Array.from(
      { length: 12 },
      (_, at) => `2025-${`${at + 1}`.padStart(2, '0')}`,
    );
    const filled = (amounts: Record<string, string>) =>
      MONTHS.map((slot) => ({
        slot,
        amount: amounts[slot] ?? null,
        estimated: true,
      }));
    expect(lastBody(server, SAVE_PLANT)).toStrictEqual({
      rows: [
        {
          rowId: 1,
          siteFacilityId: 4,
          unit: 'kL',
          na: false,
          values: filled({ '2025-01': '12.5', '2025-02': '3' }),
        },
        {
          rowId: 2,
          siteFacilityId: 5,
          unit: 'kL',
          na: false,
          values: filled({ '2025-02': '8' }),
        },
      ],
    });
  });

  it('칸을 비우면 amount null · 단위 바꿈은 행으로 나간다', async () => {
    const { server } = await open({ entryUnits: ['L'] });
    await ready();
    type('r1', '2025-02', '');
    fireEvent.change(
      plant().getByRole('combobox', { name: words.unitLabel('1호기') }),
      { target: { value: 'L' } },
    );
    saveAll();
    await screen.findByTestId('toast');
    expect(lastBody(server, SAVE_PLANT)).toStrictEqual({
      rows: [
        {
          rowId: 1,
          siteFacilityId: 4,
          unit: 'L',
          na: false,
          values: [{ slot: '2025-02', amount: null, estimated: false }],
        },
      ],
    });
  });

  it('바꾼 것이 없으면 요청 0 + 아래 한 줄 「바꾼 내용이 없어요」(사업장·메모 둘 다 0)', async () => {
    const { server } = await open();
    await ready();
    const before = server.calls.length;
    saveAll();
    await waitFor(() =>
      expect(screen.getByTestId('entry-foot-notice').textContent).toBe(
        '바꾼 내용이 없어요',
      ),
    );
    expect(server.calls.length).toBe(before);
    expect(screen.queryByTestId('toast')).toBeNull();
  });

  it('모달 [저장] 하나 — 블록 [저장]·[메모 저장] 0 · 바뀐 사업장만 화면 차례 PUT · 메모 마지막 · 둘 다 응답으로 갈음', async () => {
    const { server } = await open();
    await ready();
    expect(plant().queryByRole('button', { name: words.save })).toBeNull();
    expect(headBlock().queryByRole('button', { name: words.save })).toBeNull();
    expect(screen.queryByRole('button', { name: '메모 저장' })).toBeNull();
    expect(screen.getAllByRole('button', { name: words.save })).toHaveLength(1);
    const headKey = keyOfHead();
    type('r1', '2025-02', '4.5');
    type(headKey, '2025-03', '77');
    fireEvent.change(screen.getByRole('textbox', { name: words.memoLabel }), {
      target: { value: '지어낸 메모' },
    });
    const from = server.calls.length;
    saveAll();
    await screen.findByTestId('toast');
    const writes = server.calls
      .slice(from)
      .filter((call) => call.method === 'PUT')
      .map((call) => `${call.method} ${call.path}`);
    // 화면 차례 = 상세 sites 차례(본사 → 제1공장), 메모는 마지막.
    const order = [...document.querySelectorAll('[data-testid^="entry-site-"]')]
      .map((el) => el.getAttribute('data-testid')!.replace('entry-site-', ''))
      .map((id) => `PUT ${X}/sites/${id}/rows`);
    expect(writes).toEqual([...order, `PUT ${X}/memo`]);
    expect(lastBody(server, SAVE_HEAD)).toStrictEqual({
      rows: [
        {
          rowId: Number(headKey.slice(1)),
          siteFacilityId: Number(await headLineId(portsOf(server).entry)),
          unit: 'kL',
          na: false,
          values: [{ slot: '2025-03', amount: '77', estimated: false }],
        },
      ],
    });
    expect(lastBody(server, `PUT ${X}/memo`)).toStrictEqual({
      memo: '지어낸 메모',
    });
    expect(amountCell(headKey, '2025-03').value).toBe('77');
    expect(amountCell('r1', '2025-02').value).toBe('4.5');
    expect(screen.getByTestId('toast').textContent).toBe('저장됐어요');
  });

  it('바뀐 사업장만 PUT — 본사만 고치면 제1공장 PUT 0 · 메모 안 바뀌면 메모 PUT 0', async () => {
    const { server } = await open();
    await ready();
    const headKey = keyOfHead();
    type(headKey, '2025-03', '77');
    const plantBefore = server.count(SAVE_PLANT);
    saveAll();
    await screen.findByTestId('toast');
    expect(server.count(SAVE_PLANT)).toBe(plantBefore);
    expect(server.count(`PUT ${X}/memo`)).toBe(0);
    expect(lastBody(server, SAVE_HEAD)).toMatchObject({
      rows: [{ values: [{ slot: '2025-03', amount: '77', estimated: false }] }],
    });
  });

  it('S12-04 「저장됐어요」는 공용 토스트 하나 — 제목 줄·블록 안 0 · 모달 밖(body 끝) · aria-hidden 아님(★D) · 고쳐도 남고 다시 저장하면 새 것', async () => {
    await open();
    await ready();
    type('r1', '2025-02', '4.5');
    saveAll();
    const saved = await screen.findByTestId('toast');
    expect(saved.getAttribute('role')).toBe('status');
    expect(saved.textContent).toBe(words.saved);
    expect(screen.getAllByText(words.saved)).toHaveLength(1);
    expect(plant().queryByText(words.saved)).toBeNull();
    expect(screen.getByRole('dialog').contains(saved)).toBe(false);
    expect(saved.closest('[aria-hidden="true"]')).toBeNull();
    expect(document.body.lastElementChild!.contains(saved)).toBe(true);
    type('r1', '2025-02', '4.6');
    expect(screen.getAllByTestId('toast')).toHaveLength(1);
    saveAll();
    await waitFor(() => expect(screen.getAllByTestId('toast')).toHaveLength(2));
  });

  it('남이 바꾼 칸은 응답으로 새 값이 보이고, 그 블록 본문에는 내가 고친 칸만 간다(가지 리뷰 — 모달 저장 한 번)', async () => {
    const { server, port } = await open();
    await ready();
    const headKey = keyOfHead();
    type(headKey, '2025-03', '77');
    const other = await port.saveRows(2025, '20', '1', [
      {
        rowId: Number(headKey.slice(1)),
        siteFacilityId: Number(await headLineId(port)),
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-02', amount: '9', estimated: false }],
      },
    ]);
    expect(other.kind).toBe('ok');
    type('r1', '2025-02', '4.5');
    saveAll();
    await screen.findByTestId('toast');
    expect(amountCell(headKey, '2025-02').value).toBe('9');
    expect(amountCell(headKey, '2025-03').value).toBe('77');
    expect(lastBody(server, SAVE_HEAD)).toMatchObject({
      rows: [{ values: [{ slot: '2025-03', amount: '77', estimated: false }] }],
    });
    const body = lastBody(server, SAVE_HEAD) as {
      rows: { values: unknown[] }[];
    };
    expect(body.rows[0]!.values).toHaveLength(1);
  });

  it('저장한 뒤 다시 누르면 바뀐 것이 없다(before 가 응답으로 바뀜)', async () => {
    const { server } = await open();
    await ready();
    type('r1', '2025-02', '4.5');
    saveAll();
    await screen.findByTestId('toast');
    const sent = server.count(SAVE_PLANT);
    saveAll();
    await waitFor(() =>
      expect(screen.getByTestId('entry-foot-notice').textContent).toBe(
        words.nothingToSave,
      ),
    );
    expect(server.count(SAVE_PLANT)).toBe(sent);
  });
});

describe('검사와 거절', () => {
  it('누를 때 검사: 요청 0 · 첫 오류 칸 초점 · 칸 아래 붉은 글 · 고치면 걷힘', async () => {
    const { server } = await open();
    await ready();
    const sent = server.count(SAVE_PLANT);
    type('r2', '2025-04', '0.1234567');
    // S12C1 768f5c80: 부호·글자는 칸에서 걸러지므로 형식 오류는 거른 뒤에도 남는 꼴(앞 소수점)로.
    type('r1', '2025-03', '.5');
    saveAll();
    await waitFor(() =>
      expect(document.activeElement).toBe(amountCell('r1', '2025-03')),
    );
    expect(server.count(SAVE_PLANT)).toBe(sent);
    expect(amountCell('r1', '2025-03').getAttribute('aria-invalid')).toBe(
      'true',
    );
    const row1 = within(screen.getByTestId('entry-row-r1'));
    const row2 = within(screen.getByTestId('entry-row-r2'));
    expect(row1.getByText(words.amountFormat)).toBeTruthy();
    expect(row2.getByText(words.amountDecimals)).toBeTruthy();
    type('r1', '2025-03', '1');
    expect(row1.queryByText(words.amountFormat)).toBeNull();
  });

  it('GX2 M-7 줄 없는 블록 → 「[추가]를 눌러…」 한 줄 · 줄 있는 블록은 0 · S12-03 출처 칸 title = 계수 이름', async () => {
    await open({}, { seed: false });
    await ready();
    expect(screen.getByTestId('entry-empty-2').textContent).toBe(
      words.rowsEmpty,
    );
    expect(
      screen.getByTestId('entry-empty-2').querySelector('td')!.colSpan,
    ).toBe(
      screen.getByTestId('entry-site-2').querySelectorAll('thead th').length,
    );
    cleanup();
    await open();
    await ready();
    expect(screen.queryByTestId('entry-empty-2')).toBeNull();
    const factor = screen.getByTestId('entry-factor-r1');
    expect(factor.getAttribute('title')).toBe(factor.textContent);
    expect(factor.textContent).not.toBe('');
  });

  it('S12C1 768f5c80 숫자만: 친 글·붙여넣은 글의 쉼표·글자·부호·빈칸·둘째 소수점을 칸에서 거름 → 쉼표 글 0 · 거른 글자로 저장', async () => {
    const { server } = await open();
    await ready();
    const sent = server.count(SAVE_PLANT);
    // GX2 S12-03 쉼표(앞 단언 — 「1,000」 이 칸에 남아 쉼표 전용 글)는 거름으로 갈음: 칸에 쉼표가 들어가지 않는다.
    type('r1', '2025-03', '1,000');
    expect(amountCell('r1', '2025-03').value).toBe('1000');
    type('r1', '2025-03', '가a-');
    expect(amountCell('r1', '2025-03').value).toBe('');
    // 붙여넣기(jsdom 은 붙여넣은 글을 칸 값 바꿈으로 받음) — 섞인 글.
    type('r1', '2025-03', ' 1,2a3.4.5 t');
    expect(amountCell('r1', '2025-03').value).toBe('123.45');
    type('r1', '2025-03', '-0.5');
    expect(amountCell('r1', '2025-03').value).toBe('0.5');
    saveAll();
    await waitFor(() => expect(server.count(SAVE_PLANT)).toBe(sent + 1));
    const row1 = within(screen.getByTestId('entry-row-r1'));
    expect(row1.queryByText(words.amountComma)).toBeNull();
    expect(row1.queryByText(words.amountFormat)).toBeNull();
    expect(JSON.stringify(lastBody(server, SAVE_PLANT))).toContain('"0.5"');
  });

  it('422 는 본문 차례로 같은 칸에 — 안 바뀐 첫 행 + 바뀐 둘째 행이면 rows.0 = 화면 둘째 행', async () => {
    const { server } = await open();
    await ready();
    server.override[SAVE_PLANT] = () =>
      refusal(422, 'VALIDATION_ERROR', {
        'rows.0.values.0.amount': ['서버 글은 화면에 싣지 않음'],
      });
    type('r2', '2025-05', '9');
    saveAll();
    await waitFor(() =>
      expect(document.activeElement).toBe(amountCell('r2', '2025-05')),
    );
    expect(amountCell('r1', '2025-01').getAttribute('aria-invalid')).toBeNull();
    expect(amountCell('r2', '2025-05').getAttribute('aria-invalid')).toBe(
      'true',
    );
    expect(screen.queryByText('서버 글은 화면에 싣지 않음')).toBeNull();
    expect(screen.queryByTestId('toast')).toBeNull();
  });

  it('422 단위 칸 · 칸을 못 찾는 열쇠는 블록 한 줄', async () => {
    const { server } = await open();
    await ready();
    server.override[SAVE_PLANT] = [
      () => refusal(422, 'VALIDATION_ERROR', { 'rows.0.unit': ['x'] }),
      () => refusal(422, 'VALIDATION_ERROR', { rows: ['x'] }),
    ];
    type('r1', '2025-02', '5');
    saveAll();
    await within(screen.getByTestId('entry-row-r1')).findByText(
      words.unitRejected,
    );
    saveAll();
    await waitFor(() =>
      expect(screen.getByTestId('entry-notice-2').textContent).toBe(
        words.saveFailed,
      ),
    );
  });

  it('409 locked → 한 줄 + 상세 다시 읽음 → 잠긴 판', async () => {
    const { server, port } = await open();
    await ready();
    type('r1', '2025-02', '5');
    await port.lock(2025, '20');
    const reads = server.count(DETAIL);
    saveAll();
    await waitFor(() =>
      expect(screen.getByTestId('entry-notice-2').textContent).toBe(
        words.locked,
      ),
    );
    await waitFor(() => expect(server.count(DETAIL)).toBe(reads + 1));
    await screen.findByTestId('entry-locked');
    expect(amountCell('r1', '2025-01').disabled).toBe(true);
  });

  it('회사 거절·끊김은 한 줄(판 그대로, 고침 그대로)', async () => {
    const { server } = await open({}, { operator: true });
    await ready();
    server.override[SAVE_PLANT] = [
      () => refusal(400, 'COMPANY_AMBIGUOUS'),
      () => refusal(500, 'SERVER_ERROR'),
    ];
    type('r1', '2025-02', '5');
    saveAll();
    await waitFor(() =>
      expect(screen.getByTestId('entry-notice-2').textContent).toBe(
        GHG_TEXT.companyOperator.ambiguous,
      ),
    );
    expect(amountCell('r1', '2025-02').value).toBe('5');
    saveAll();
    await waitFor(() =>
      expect(screen.getByTestId('entry-notice-2').textContent).toBe(
        words.saveFailed,
      ),
    );
  });
});

describe('칸 = 서버 slots', () => {
  const heads = (block: HTMLElement) =>
    [...block.querySelectorAll('th[data-slot]')].map((th) => th.textContent);

  it('월 12 · 분기 4 · 연 1 — 블록마다 다르고 머리 글·주기 글이 그에 맞음', async () => {
    await open(
      { entryPeriod: { '2': 'quarter', '1': 'year' } },
      { seed: false },
    );
    await ready();
    expect(heads(screen.getByTestId('entry-site-2'))).toEqual([
      '1분기',
      '2분기',
      '3분기',
      '4분기',
    ]);
    expect(heads(screen.getByTestId('entry-site-1'))).toEqual(['연간']);
    // S12C1 c3a27892: 사업장 이름 옆 주기 글(「분기별」·「연간」)은 지움 — 칸 머리만.
    expect(screen.queryByTestId('entry-period-2')).toBeNull();
    expect(screen.queryByTestId('entry-period-1')).toBeNull();
    expect(screen.getByTestId('entry-site-2').textContent).not.toContain(
      '분기별',
    );
    cleanup();
    await open({}, { seed: false });
    await ready();
    const months = heads(screen.getByTestId('entry-site-2'));
    expect(months).toHaveLength(12);
    expect(months[0]).toBe('1월');
    expect(months[11]).toBe('12월');
    expect(screen.queryByTestId('entry-period-2')).toBeNull();
    expect(screen.getByTestId('entry-site-2').textContent).not.toContain(
      '월별',
    );
    // 입력주기 변경 단추는 그대로.
    expect(screen.getByTestId('entry-period-open-2')).toBeTruthy();
  });

  it('분기 블록에 새 행 값을 넣으면 분기 칸 글자로 나간다', async () => {
    const { server } = await open(
      { entryPeriod: { '2': 'quarter' } },
      { seed: false },
    );
    await ready();
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    const add = await screen.findByTestId('entry-add');
    fireEvent.click(
      within(add).getByRole('checkbox', { name: words.addPick('1호기') }),
    );
    fireEvent.click(within(add).getByRole('button', { name: words.addOk }));
    await waitFor(() => expect(screen.queryByTestId('entry-add')).toBeNull());
    type('n4', '2025-Q2', '6');
    saveAll();
    await screen.findByTestId('toast');
    expect(lastBody(server, SAVE_PLANT)).toStrictEqual({
      rows: [
        {
          siteFacilityId: 4,
          unit: 'kL',
          na: false,
          values: [{ slot: '2025-Q2', amount: '6', estimated: false }],
        },
      ],
    });
  });
});

describe('N/A', () => {
  it('켜면 칸 비활성(칸 추정 표식 0 — S12-03) · 본문 na 참 · 배출량 칸 「N/A」 · 끄면 돌아옴', async () => {
    const { server } = await open();
    await ready();
    const na = plant().getByRole('checkbox', {
      name: words.naLabel('1호기'),
    });
    fireEvent.click(na);
    expect(amountCell('r1', '2025-01').disabled).toBe(true);
    expect(screen.queryByTestId('entry-estimated-r1:2025-01')).toBeNull(); // S12-03: 칸 표식 0
    expect(screen.getByTestId('entry-emission-r1').textContent).toBe('N/A');
    saveAll();
    await screen.findByTestId('toast');
    expect(lastBody(server, SAVE_PLANT)).toStrictEqual({
      rows: [
        {
          rowId: 1,
          siteFacilityId: 4,
          unit: 'kL',
          na: true,
          values: [],
        },
      ],
    });
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.naLabel('1호기') }),
    );
    expect(amountCell('r1', '2025-01').disabled).toBe(false);
  });

  it('머리 (i) 이름이 툴팁 글', async () => {
    await open();
    await ready();
    expect(plant().getByRole('button', { name: words.naTip })).toBeTruthy();
  });

  it('빈 값 셋(Q7, S12C1 9ddc00eb): null 빈칸(「-」 아님) · 0 「0」 · 셈 문제는 까닭 글', async () => {
    const { server, port } = await open({ entryEmission: '0' });
    const out = await port.detail(2025, '20');
    if (out.kind !== 'ok') throw new Error('읽기 실패');
    await ready();
    cleanup();
    const site = out.value.sites.find((s) => s.siteId === '2')!;
    server.override[DETAIL] = () =>
      json(200, {
        ...out.value,
        sites: out.value.sites.map((s) =>
          s !== site ? s : (
            {
              ...s,
              rows: [
                { ...s.rows[0]!, emission: null },
                {
                  ...s.rows[1]!,
                  emission: null,
                  emissionProblem: 'factor_unit_invalid',
                },
              ],
            }
          ),
        ),
      });
    render(
      <EntryDetailDialog
        port={port}
        year={2025}
        nodeId="20"
        operator={false}
        onClose={() => {}}
      />,
    );
    await ready();
    expect(screen.getByTestId('entry-emission-r1').textContent).toBe('');
    const problem = screen.getByTestId('entry-emission-r2');
    expect(problem.textContent).toContain(words.noEmission);
    expect(problem.textContent).toContain(
      words.emissionProblem['factor_unit_invalid'],
    );
    // #22: 까닭 글만 줄바꿈 + break-keep · 칸(숫자·N/A)은 nowrap 그대로.
    const reason = within(problem).getByText(
      words.emissionProblem['factor_unit_invalid']!,
    );
    expect(reason.className).toContain('break-keep');
    expect(reason.className).toContain('whitespace-normal');
    expect(problem.className).toContain('whitespace-nowrap');
    expect(within(problem).getByText(words.noEmission).className).not.toContain(
      'break-keep',
    );
    // W12-1d N1(판 .f12b-num · .f12b-emx): 칸 오른쪽 · 까닭 두 줄도 오른쪽 끝.
    expect(problem.className.split(/\s+/)).toContain('text-right');
    const head = [...document.querySelectorAll('thead th')].filter((th) =>
      th.textContent?.startsWith(words.head.emission),
    );
    expect(head.length).toBeGreaterThan(0);
    for (const th of head) {
      expect(th.className.split(/\s+/)).toContain('text-right');
      expect(th.className.split(/\s+/)).not.toContain('text-left');
    }
    const lines = within(problem).getByTestId('entry-emission-problem');
    expect(lines.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['items-end', 'text-right']),
    );
  });
});

describe('추가·삭제', () => {
  it('추가: addable 만 고를 수 있고 새 행은 화면에만 · 저장 때 rowId 없이', async () => {
    const { server } = await open();
    await ready();
    const sent = server.count(SAVE_PLANT);
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    const add = await screen.findByTestId('entry-add');
    expect(
      within(add).queryByRole('checkbox', { name: words.addPick('1호기') }),
    ).toBeNull();
    fireEvent.click(
      within(add).getByRole('checkbox', { name: words.addPick('3호기') }),
    );
    fireEvent.click(within(add).getByRole('button', { name: words.addOk }));
    await screen.findByTestId('entry-row-n6');
    expect(server.count(SAVE_PLANT)).toBe(sent);
    saveAll();
    await screen.findByTestId('toast');
    expect(lastBody(server, SAVE_PLANT)).toStrictEqual({
      rows: [{ siteFacilityId: 6, unit: 'kL', na: false, values: [] }],
    });
    expect(screen.queryByTestId('entry-row-n6')).toBeNull();
  });

  it('삭제: 체크 → 확인 모달 → {ids:[정수]} → 다시 읽음 · 지운 행 사라짐 · 다른 행 고침 지킴', async () => {
    const { server } = await open();
    await ready();
    type('r1', '2025-02', '5');
    const remove = plant().getByRole('button', { name: words.remove });
    expect((remove as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.selectLabel('2호기') }),
    );
    fireEvent.click(remove);
    const confirm = await screen.findByTestId('entry-remove');
    expect(server.count(REMOVE)).toBe(0);
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.removeOk }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-row-r2')).toBeNull(),
    );
    expect(lastBody(server, REMOVE)).toStrictEqual({ ids: [2] });
    expect(amountCell('r1', '2025-02').value).toBe('5');
  });

  it('화면에만 있는 새 행 삭제는 요청 0', async () => {
    const { server } = await open();
    await ready();
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    const add = await screen.findByTestId('entry-add');
    fireEvent.click(
      within(add).getByRole('checkbox', { name: words.addPick('3호기') }),
    );
    fireEvent.click(within(add).getByRole('button', { name: words.addOk }));
    await screen.findByTestId('entry-row-n6');
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.selectLabel('3호기') }),
    );
    fireEvent.click(plant().getByRole('button', { name: words.remove }));
    const confirm = await screen.findByTestId('entry-remove');
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.removeOk }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-row-n6')).toBeNull(),
    );
    expect(server.count(REMOVE)).toBe(0);
  });

  it('삭제 404 → 한 줄 + 상세 다시 읽음', async () => {
    const { server } = await open();
    await ready();
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.selectLabel('2호기') }),
    );
    fireEvent.click(plant().getByRole('button', { name: words.remove }));
    server.override[REMOVE] = () => refusal(404, 'NOT_FOUND');
    const reads = server.count(DETAIL);
    const confirm = await screen.findByTestId('entry-remove');
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.removeOk }),
    );
    await waitFor(() =>
      expect(screen.getByTestId('entry-notice-2').textContent).toBe(words.gone),
    );
    await waitFor(() => expect(server.count(DETAIL)).toBe(reads + 1));
  });
});

describe('메모·소수점', () => {
  it('메모: 모달 [저장]으로 · {memo} · 제목 옆 저장됐어요 · 쓰기로 셈', async () => {
    const { server, onClose } = await open();
    await ready();
    fireEvent.change(screen.getByRole('textbox', { name: words.memoLabel }), {
      target: { value: '지어낸 메모' },
    });
    saveAll();
    await screen.findByTestId('toast');
    expect(server.count(SAVE_PLANT)).toBe(1);
    expect(lastBody(server, `PUT ${X}/memo`)).toStrictEqual({
      memo: '지어낸 메모',
    });
    fireEvent.click(screen.getByRole('button', { name: words.close }));
    await waitFor(() => expect(onClose).toHaveBeenCalledWith(true));
  });

  it('메모 2,000자 넘음 → 요청 0 · 칸 아래 글 · 422 도 같은 자리', async () => {
    const { server } = await open();
    await ready();
    const box = screen.getByRole('textbox', { name: words.memoLabel });
    fireEvent.change(box, { target: { value: '가'.repeat(2001) } });
    type('r1', '2025-02', '4.5');
    const before = server.calls.length;
    saveAll();
    await screen.findByTestId('entry-memo-error');
    // 검사 먼저 — 메모가 걸리면 사업장 PUT 도 0 · 초점은 메모 칸.
    expect(server.calls.length).toBe(before);
    await waitFor(() => expect(document.activeElement).toBe(box));
    fireEvent.change(box, { target: { value: '짧음' } });
    server.override[`PUT ${X}/memo`] = () =>
      refusal(422, 'VALIDATION_ERROR', { memo: ['x'] });
    saveAll();
    await screen.findByTestId('entry-memo-error');
    expect(screen.queryByTestId('toast')).toBeNull();
  });

  it('소수점: PUT decimals → 표시만 다시 · 입력 칸은 글자 그대로', async () => {
    const { server } = await open({ entryEmission: '1.23456' });
    await ready();
    expect(screen.getByTestId('entry-emission-r1').textContent).toBe('1.23');
    fireEvent.change(
      screen.getByRole('combobox', { name: words.decimalsLabel }),
      {
        target: { value: '3' },
      },
    );
    await waitFor(() =>
      expect(screen.getByTestId('entry-emission-r1').textContent).toBe('1.235'),
    );
    expect(
      lastBody(server, 'PUT /inventory/scope12/years/2025/decimals'),
    ).toStrictEqual({ decimals: 3 });
    expect(amountCell('r1', '2025-01').value).toBe('12.5');
  });
});

describe('닫기', () => {
  it('고침 없이 닫으면 확인 없이 onClose(false)', async () => {
    const { onClose } = await open();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: words.close }));
    await waitFor(() => expect(onClose).toHaveBeenCalledWith(false));
  });

  it('저장 안 한 고침 → 나가기 확인 · 취소하면 그대로 · Enter(form) 로 나감', async () => {
    const { onClose } = await open();
    await ready();
    type('r1', '2025-02', '5');
    fireEvent.click(screen.getByRole('button', { name: words.close }));
    const confirm = await screen.findByTestId('entry-leave');
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.cancel }),
    );
    await waitFor(() => expect(screen.queryByTestId('entry-leave')).toBeNull());
    expect(amountCell('r1', '2025-02').value).toBe('5');
    fireEvent.click(screen.getByRole('button', { name: words.close }));
    const again = await screen.findByTestId('entry-leave');
    fireEvent.submit(again.querySelector('form')!);
    await waitFor(() => expect(onClose).toHaveBeenCalledWith(false));
  });

  it('저장 안 한 메모도 나가기 확인', async () => {
    await open();
    await ready();
    fireEvent.change(screen.getByRole('textbox', { name: words.memoLabel }), {
      target: { value: '고침' },
    });
    fireEvent.click(screen.getByRole('button', { name: words.close }));
    await screen.findByTestId('entry-leave');
  });

  it('모달 Enter: 삭제 확인은 form 제출 · 닫히면 초점이 연 단추로', async () => {
    const { server } = await open();
    await ready();
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.selectLabel('2호기') }),
    );
    const remove = plant().getByRole('button', { name: words.remove });
    remove.focus();
    fireEvent.click(remove);
    const confirm = await screen.findByTestId('entry-remove');
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.cancel }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-remove')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(remove));
    fireEvent.click(remove);
    const again = await screen.findByTestId('entry-remove');
    fireEvent.submit(again.querySelector('form')!);
    await waitFor(() => expect(lastBody(server, REMOVE)).toEqual({ ids: [2] }));
    // 지운 뒤 [삭제]가 꺼지면 초점은 그 블록 [추가]로(블록 [저장]이 없어짐 — W12-1c ①).
    await waitFor(() =>
      expect(document.activeElement).toBe(
        plant().getByRole('button', { name: words.add }),
      ),
    );
  });

  it('추가 고르기: Enter(form) · 닫히면 초점이 [추가]로', async () => {
    await open();
    await ready();
    const add = plant().getByRole('button', { name: words.add });
    add.focus();
    fireEvent.click(add);
    const dialog = await screen.findByTestId('entry-add');
    fireEvent.click(
      within(dialog).getByRole('checkbox', { name: words.addPick('3호기') }),
    );
    fireEvent.submit(dialog.querySelector('form')!);
    await screen.findByTestId('entry-row-n6');
    await waitFor(() => expect(document.activeElement).toBe(add));
  });
});

describe('잠긴 판', () => {
  it('입력·추가·삭제·N/A·단위·저장·메모·소수점 비활성 · 머리 자물쇠', async () => {
    await open({}, { locked: true });
    await ready();
    await screen.findByTestId('entry-locked');
    expect(amountCell('r1', '2025-01').disabled).toBe(true);
    for (const name of [words.add, words.remove])
      expect(
        (plant().getByRole('button', { name }) as HTMLButtonElement).disabled,
      ).toBe(true);
    expect(
      (screen.getByRole('button', { name: words.save }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      (
        plant().getByRole('checkbox', {
          name: words.naLabel('1호기'),
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(
      (
        plant().getByRole('combobox', {
          name: words.unitLabel('1호기'),
        }) as HTMLSelectElement
      ).disabled,
    ).toBe(true);
    expect(
      (
        screen.getByRole('textbox', {
          name: words.memoLabel,
        }) as HTMLTextAreaElement
      ).disabled,
    ).toBe(true);
    expect(
      (
        screen.getByRole('combobox', {
          name: words.decimalsLabel,
        }) as HTMLSelectElement
      ).disabled,
    ).toBe(true);
  });
});

describe('머리·읽기 갈래', () => {
  it('이름 · 경로 응답 path · 3개년 데이터 상세 · 큰 모달 폭', async () => {
    const { server, port } = await open();
    const out = await port.detail(2025, '20');
    if (out.kind !== 'ok') throw new Error('읽기 실패');
    server.override[DETAIL] = () =>
      json(200, {
        ...out.value,
        totals: {
          years: [2023, 2024, 2025],
          all: { '2023': null, '2024': '0', '2025': '10.126' },
          bySite: [
            { siteId: '2', siteName: '제1공장', values: { '2025': '4' } },
          ],
        },
      });
    await ready();
    cleanup();
    render(
      <EntryDetailDialog
        port={port}
        year={2025}
        nodeId="20"
        operator={false}
        onClose={() => {}}
      />,
    );
    await ready();
    expect(screen.getByTestId('entry-path').textContent).toBe(
      out.value.path.join(' > '),
    );
    const all = within(screen.getByTestId('entry-total-all'));
    expect(all.getByText(words.total)).toBeTruthy();
    expect(
      [...screen.getByTestId('entry-total-all').querySelectorAll('td')].map(
        (td) => td.textContent,
      ),
    ).toEqual([words.total, '', '0', '10.13', out.value.unit]);
    expect(
      screen.getByTestId('entry-total-2').querySelector('td')!.textContent,
    ).toBe('•제1공장');
    const dialog = document.querySelector('[data-screen="ghg-entry-detail"]')!;
    expect(dialog.className).toContain('w-[calc(100vw-64px)]');
    expect(screen.getByTestId('entry-scroll-2').className).toContain(
      'overflow-x-auto',
    );
    // W12-1d Q10: 표 자체 가로 막대 숨김(위 막대가 끌기·자리를 맡음).
    expect(screen.getByTestId('entry-scroll-2').className.split(/\s+/)).toEqual(
      expect.arrayContaining([
        '[scrollbar-width:none]',
        '[&::-webkit-scrollbar]:hidden',
      ]),
    );
  });

  it('상세 404 → 모달 안 「찾을 수 없어요」 + 닫기', async () => {
    const server = fakeGhgServer(options());
    const onClose = vi.fn();
    render(
      <EntryDetailDialog
        port={portsOf(server).entry}
        year={2025}
        nodeId="999"
        operator={false}
        onClose={onClose}
      />,
    );
    await screen.findByText(words.notFound);
    const closers = screen.getAllByRole('button', { name: words.close });
    fireEvent.click(closers.at(-1)!);
    expect(onClose).toHaveBeenCalledWith(false);
  });

  it('읽기 실패 → 다시 시도 · 회사 거절은 역할 글', async () => {
    const server = fakeGhgServer(options());
    server.override[DETAIL] = [() => refusal(500, 'SERVER_ERROR')];
    render(
      <EntryDetailDialog
        port={portsOf(server).entry}
        year={2025}
        nodeId="20"
        operator={false}
        onClose={() => {}}
      />,
    );
    const failure = await screen.findByTestId('entry-load-failure');
    fireEvent.click(
      within(failure).getByRole('button', { name: GHG_TEXT.common.retry }),
    );
    await ready();
    cleanup();
    const other = fakeGhgServer(options({ company: 'COMPANY_INACTIVE' }));
    render(
      <EntryDetailDialog
        port={portsOf(other).entry}
        year={2025}
        nodeId="20"
        operator={false}
        onClose={() => {}}
      />,
    );
    const refused = await screen.findByTestId('entry-company-refusal');
    expect(refused.textContent).toContain(GHG_TEXT.company.inactive);
  });

  it('숨김(본문 안에서만): 담당자·참고자료·계산식·계수 수정 단추 0 (입력 주기 변경·복구는 W12-2 에서 보임)', async () => {
    await open();
    await ready();
    const dialog = document.querySelector<HTMLElement>(
      '[data-screen="ghg-entry-detail"]',
    )!;
    const text = dialog.textContent ?? '';
    for (const word of [
      '담당자',
      '참고자료',
      '계산식',
      '배출계수 수정',
      'Scope 3',
    ])
      expect(text, word).not.toContain(word);
  });
});

describe('저장 중(검증 R2)', () => {
  it('응답을 기다리는 동안 그 블록 입력이 꺼지고, 끝나면 켜진다', async () => {
    const server = fakeGhgServer(options());
    const real = portsOf(server).entry;
    await real.saveRows(2025, '20', '2', [
      {
        siteFacilityId: 4,
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-01', amount: '1', estimated: false }],
      },
    ]);
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    render(
      <EntryDetailDialog
        port={{
          ...real,
          saveRows: async (...args) => {
            await gate;
            return real.saveRows(...args);
          },
        }}
        year={2025}
        nodeId="20"
        operator={false}
        onClose={() => {}}
      />,
    );
    await ready();
    type('r1', '2025-02', '5');
    saveAll();
    await waitFor(() =>
      expect(amountCell('r1', '2025-02').disabled).toBe(true),
    );
    release();
    await screen.findByTestId('toast');
    expect(amountCell('r1', '2025-02').disabled).toBe(false);
    expect(amountCell('r1', '2025-02').value).toBe('5');
  });
});

describe('잠금(② — Q8)', () => {
  it('고객사: [잠금] → POST → 응답으로 갈음(비활성·잠근 사람) · S2 다시 읽게 쓰기로 셈 · 풀기 단추 0', async () => {
    const { server, onClose } = await open();
    await ready();
    expect(screen.queryByRole('button', { name: words.unlock })).toBeNull();
    await lockNow();
    await screen.findByTestId('entry-locked');
    expect(server.count(`POST ${X}/lock`)).toBe(1);
    expect(screen.getByTestId('entry-locked-by').textContent).toContain(
      '지어낸-사람',
    );
    expect(amountCell('r1', '2025-01').disabled).toBe(true);
    expect(screen.queryByRole('button', { name: words.unlock })).toBeNull();
    expect(screen.queryByRole('button', { name: words.lock })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: words.close }));
    await waitFor(() => expect(onClose).toHaveBeenCalledWith(true));
  });

  it('운영 관리자: [잠금 해제] → DELETE → 다시 입력 · [잠금] 다시', async () => {
    const { server } = await open({}, { operator: true, locked: true });
    await ready();
    fireEvent.click(screen.getByRole('button', { name: words.unlock }));
    await screen.findByRole('button', { name: words.lock });
    expect(server.count(`DELETE ${X}/lock`)).toBe(1);
    expect(amountCell('r1', '2025-01').disabled).toBe(false);
    expect(screen.queryByTestId('entry-locked')).toBeNull();
  });

  it('잠그기 확인 창은 첫 초점이 [취소] — Enter 한 번에 잠기지 않는다(sid:MARC-ISSUE-587, e6)', async () => {
    await open();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: words.lock }));
    const confirm = await screen.findByTestId('entry-lock-confirm');
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(confirm).getByRole('button', { name: words.cancel }),
      ),
    );
  });

  it('고침이 있으면 잠그기 전 확인 — 취소: 요청 0 · 고침 그대로(검증 R6)', async () => {
    const { server } = await open();
    await ready();
    type('r1', '2025-02', '5');
    fireEvent.click(screen.getByRole('button', { name: words.lock }));
    const confirm = await screen.findByTestId('entry-lock-confirm');
    expect(confirm.textContent).toContain(
      '변경 내용을 저장하지 않고 잠글까요?',
    );
    expect(server.count(`POST ${X}/lock`)).toBe(0);
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.cancel }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-lock-confirm')).toBeNull(),
    );
    expect(server.count(`POST ${X}/lock`)).toBe(0);
    expect(amountCell('r1', '2025-02').value).toBe('5');
    expect(screen.queryByTestId('entry-locked')).toBeNull();
  });

  it('고침이 있으면 잠그기 전 확인 — 확인: 잠금 · 응답으로 갈음(고침 버림 · 검증 R6)', async () => {
    const { server } = await open();
    await ready();
    type('r1', '2025-02', '5');
    fireEvent.click(screen.getByRole('button', { name: words.lock }));
    const confirm = await screen.findByTestId('entry-lock-confirm');
    fireEvent.submit(confirm.querySelector('form')!);
    await screen.findByTestId('entry-locked');
    expect(server.count(`POST ${X}/lock`)).toBe(1);
    expect(amountCell('r1', '2025-02').value).toBe('3');
  });

  it('잠금·풀기 쓰기를 기다리는 동안 단추를 막아 요청이 겹치지 않는다 · 실패하면 다시 켠다(검증 R5)', async () => {
    const server = fakeGhgServer(options());
    const real = portsOf(server).entry;
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    let locks = 0;
    let unlocks = 0;
    render(
      <EntryDetailDialog
        port={{
          ...real,
          lock: async (...args) => {
            locks += 1;
            await gate;
            return real.lock(...args);
          },
          unlock: async (...args) => {
            unlocks += 1;
            await gate;
            return real.unlock(...args);
          },
        }}
        year={2025}
        nodeId="20"
        operator
        onClose={() => {}}
      />,
    );
    await ready();
    const lock = screen.getByRole<HTMLButtonElement>('button', {
      name: words.lock,
    });
    fireEvent.click(lock);
    await waitFor(() => expect(lock.disabled).toBe(true));
    fireEvent.click(lock);
    expect(locks).toBe(1);
    release();
    await screen.findByTestId('entry-locked');
    const unlock = screen.getByRole<HTMLButtonElement>('button', {
      name: words.unlock,
    });
    expect(unlock.disabled).toBe(false);
    server.override[`DELETE ${X}/lock`] = [() => refusal(403, 'FORBIDDEN')];
    fireEvent.click(unlock);
    expect(unlock.disabled).toBe(true);
    fireEvent.click(unlock);
    expect(unlocks).toBe(1);
    await waitFor(() =>
      expect(screen.getByTestId('entry-notice').textContent).toBe(
        words.forbidden,
      ),
    );
    expect(unlock.disabled).toBe(false);
  });

  it('거절 한 줄: 풀기 403 · 회사 둘 400(역할 글)', async () => {
    const { server } = await open({}, { operator: true, locked: true });
    await ready();
    server.override[`DELETE ${X}/lock`] = [
      () => refusal(403, 'FORBIDDEN'),
      () => refusal(400, 'COMPANY_AMBIGUOUS'),
    ];
    fireEvent.click(screen.getByRole('button', { name: words.unlock }));
    await waitFor(() =>
      expect(screen.getByTestId('entry-notice').textContent).toBe(
        words.forbidden,
      ),
    );
    fireEvent.click(screen.getByRole('button', { name: words.unlock }));
    await waitFor(() =>
      expect(screen.getByTestId('entry-notice').textContent).toBe(
        GHG_TEXT.companyOperator.ambiguous,
      ),
    );
    expect(screen.getByTestId('entry-locked')).toBeTruthy();
  });
});

const history = words.history;
const HISTORY = `GET ${X}/rows/1/history`;
const historyLine = (over: Record<string, unknown>) => ({
  historyId: '1',
  at: '2026-01-02T03:04:05Z',
  kind: 'value',
  slot: null,
  unit: 'kL',
  before: null,
  after: null,
  actor: { kind: 'service', id: '1', name: '지어낸-사람' },
  reason: null,
  restorable: true,
  beforeFactor: null,
  afterFactor: null,
  ...over,
});
const historyPage = (
  results: Record<string, unknown>[],
  over: Record<string, unknown> = {},
) =>
  json(200, {
    count: results.length,
    totalPages: 1,
    page: 1,
    pageSize: 20,
    hasNext: false,
    hasPrevious: false,
    results,
    ...over,
  });

describe('S12 히스토리(②)', () => {
  const openHistory = async () => {
    fireEvent.click(screen.getByTestId('entry-history-r1'));
    return screen.findByTestId('entry-history');
  };

  it('종류 여섯 글 · before→after 차례 · 칸 머리 글 · 빈 값 「-」 · 사유 · 수정일·수정자·단위', async () => {
    const { server } = await open();
    await ready();
    const ref = (name: string) => ({
      versionId: '1',
      customId: null,
      name,
      isCustom: false,
    });
    server.override[HISTORY] = () =>
      historyPage([
        historyLine({
          historyId: '11',
          kind: 'value',
          slot: '2025-03',
          before: '7',
          after: '9',
        }),
        historyLine({
          historyId: '12',
          kind: 'value',
          slot: '2025-Q2',
          before: null,
          after: '4',
        }),
        historyLine({ historyId: '13', kind: 'na_on' }),
        historyLine({ historyId: '14', kind: 'na_off' }),
        historyLine({
          historyId: '15',
          kind: 'factor',
          beforeFactor: ref('지어낸 앞 계수'),
          afterFactor: ref('지어낸 뒤 계수'),
          reason: '지어낸 사유',
        }),
        historyLine({
          historyId: '16',
          kind: 'unit',
          before: 'kL',
          after: 'L',
        }),
        historyLine({
          historyId: '17',
          kind: 'period',
          before: 'month',
          after: 'quarter',
        }),
      ]);
    const sheet = within(await openHistory());
    await sheet.findByTestId('entry-history-11');
    const cell = (id: string) => screen.getByTestId(`entry-history-${id}`);
    expect(cell('11').textContent).toContain('3월 7 → 9');
    expect(cell('12').textContent).toContain('2분기 - → 4');
    expect(cell('13').textContent).toContain('N/A 로 설정했어요');
    expect(cell('14').textContent).toContain('N/A 를 해제했어요');
    expect(cell('15').textContent).toContain(
      '배출계수를 변경했어요. 지어낸 앞 계수 → 지어낸 뒤 계수',
    );
    // W12-4 ③ 571 갈음: 사유 글은 줄 안에 0 — 사유 있는 줄(15)에만 「수정 사유」 단추(본문은 보기 창 — 아래 W12-4 ③).
    expect(cell('15').textContent).not.toContain('지어낸 사유');
    expect(
      within(cell('15')).getByRole('button', { name: history.reasonOpen }),
    ).toBeTruthy();
    expect(
      within(cell('11')).queryByRole('button', { name: history.reasonOpen }),
    ).toBeNull();
    expect(cell('16').textContent).toContain('단위를 변경했어요. kL → L');
    expect(cell('17').textContent).toContain(
      '입력주기를 변경했어요. 월별 → 분기별',
    );
    expect(cell('11').textContent).toContain('2026-01-02 12:04');
    expect(cell('11').textContent).toContain('지어낸-사람');
    expect(cell('11').textContent).toContain('kL');
  });

  it('모르는 kind: 판 실패 없이 「변경했어요」 + 값 숨김', async () => {
    const { server } = await open();
    await ready();
    server.override[HISTORY] = () =>
      historyPage([
        historyLine({
          historyId: '21',
          kind: 'made_up_kind',
          before: '비밀값',
          after: '다른값',
        }),
      ]);
    await openHistory();
    const line = await screen.findByTestId('entry-history-21');
    expect(line.textContent).toContain(history.unknown);
    expect(line.textContent).not.toContain('비밀값');
    expect(line.textContent).toContain('지어낸-사람');
    expect(screen.queryByTestId('entry-history-problem')).toBeNull();
  });

  it('쪽 넘김: 요청 page·pageSize 20 · 이전·다음', async () => {
    const { server } = await open();
    await ready();
    server.override[HISTORY] = [
      () =>
        historyPage([historyLine({ historyId: '31' })], {
          totalPages: 2,
          hasNext: true,
          count: 21,
        }),
      () =>
        historyPage([historyLine({ historyId: '32' })], {
          totalPages: 2,
          page: 2,
          hasPrevious: true,
          count: 21,
        }),
    ];
    const sheet = within(await openHistory());
    await sheet.findByTestId('entry-history-31');
    expect(
      (sheet.getByRole('button', { name: history.prev }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    fireEvent.click(sheet.getByRole('button', { name: history.next }));
    // W12-1d Q13: 점 주황은 전체에서 가장 최근(1쪽 첫 줄)만 — 2쪽 첫 줄은 회색.
    expect(
      within(sheet.getByTestId('entry-history-31')).getByTestId(
        'entry-history-dot',
      ).className,
    ).toContain('bg-text-brand');
    await sheet.findByTestId('entry-history-32');
    expect(sheet.getByTestId('entry-history-page').textContent).toBe('2 / 2');
    const second = within(sheet.getByTestId('entry-history-32')).getByTestId(
      'entry-history-dot',
    );
    expect(second.className).toContain('bg-text-quaternary');
    expect(second.className).not.toContain('bg-text-brand');
    const queries = server.calls
      .filter((call) => `${call.method} ${call.path}` === HISTORY)
      .map((call) => [call.query.get('page'), call.query.get('pageSize')]);
    expect(queries).toEqual([
      ['1', '20'],
      ['2', '20'],
    ]);
  });

  it('404 → 한 줄 + 상세 다시 읽음', async () => {
    const { server } = await open();
    await ready();
    server.override[HISTORY] = () => refusal(404, 'NOT_FOUND');
    const reads = server.count(DETAIL);
    const sheet = within(await openHistory());
    await waitFor(() =>
      expect(sheet.getByTestId('entry-history-problem').textContent).toBe(
        history.gone,
      ),
    );
    await waitFor(() => expect(server.count(DETAIL)).toBe(reads + 1));
  });

  it('복구 단추는 줄마다 하나(restorable 을 따름) · 새 행엔 히스토리 단추 0 · 잠긴 판에서도 열림 · 저장으로 쌓인 줄이 실제로 보임', async () => {
    const { server } = await open({}, { locked: true });
    await ready();
    server.override[HISTORY] = () =>
      historyPage([historyLine({ historyId: '41', restorable: true })]);
    const element = await openHistory();
    await within(element).findByTestId('entry-history-41');
    const restore = within(element).getByTestId('entry-restore-41');
    expect(restore.textContent).toBe(history.restore);
    expect((restore as HTMLButtonElement).disabled).toBe(false);
    expect(within(element).getAllByRole('button')).toHaveLength(2);
    cleanup();
    await open();
    await ready();
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    const add = await screen.findByTestId('entry-add');
    fireEvent.click(
      within(add).getByRole('checkbox', { name: words.addPick('3호기') }),
    );
    fireEvent.click(within(add).getByRole('button', { name: words.addOk }));
    await screen.findByTestId('entry-row-n6');
    expect(screen.queryByTestId('entry-history-n6')).toBeNull();
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.naLabel('1호기') }),
    );
    saveAll();
    await screen.findByTestId('toast');
    const sheet = within(await openHistory());
    // 변경 내용은 조각(「N/A」 강조 + 글)이라 한 덩이 글로 찾는다(W12-1c #16).
    await waitFor(() =>
      expect(
        sheet
          .getAllByTestId('entry-history-change')
          .map((element) => element.textContent),
      ).toContain(history.naOn),
    );
  });
});

describe('S8 계수 보기(②)', () => {
  const factorWords = words.factor;
  const has = (element: Element, wanted: readonly string[]) =>
    expect(element.className.split(/\s+/)).toEqual(
      expect.arrayContaining([...wanted]),
    );
  const custom = {
    customId: '5',
    name: '지어낸 직접입력 계수',
    source: '지어낸 직접 출처',
    baseYear: 2023,
    tier: 2,
    countryCode: 'KR',
    industryCode: '',
    inputUnit: { kind: 'volume', unit: 'kL' },
    ncvEnabled: true,
    ncv: '36.1',
    ncvUnit: { kind: 'energy', unit: 'MJ/L' },
    factorUnit: 'kgGHG/TJ',
    gases: [
      { gas: 'CO2', enabled: true, factor: '74100', gwp: '1' },
      { gas: 'CH4', enabled: false, factor: null, gwp: null },
    ],
    note: '지어낸 비고',
    isCustom: true,
  };

  it('행 factor null → 상세 factor · 판 표시 · 가스 일곱 · 읽기 전용(두 역할 입력·수정 단추 0)', async () => {
    for (const operator of [false, true]) {
      const { port } = await open({}, { operator });
      await ready();
      const out = await port.detail(2025, '20');
      if (out.kind !== 'ok') throw new Error('읽기 실패');
      const button = screen.getByTestId('entry-factor-r1');
      expect(button.textContent).toBe(out.value.factor.name);
      fireEvent.click(button);
      const dialog = await screen.findByTestId('entry-factor');
      expect(dialog.textContent).toContain(out.value.factor.source);
      expect(dialog.textContent).toContain(
        factorWords.versionValue(out.value.factor.version),
      );
      expect(
        dialog.querySelectorAll('tr[data-testid^="entry-gas-"]'),
      ).toHaveLength(out.value.factor.gases.length);
      expect(within(dialog).getAllByRole('button')).toHaveLength(1);
      expect(dialog.querySelectorAll('input,select,textarea')).toHaveLength(0);
      for (const word of ['배출계수 수정', '계산식'])
        expect(dialog.textContent, word).not.toContain(word);
      cleanup();
    }
  });

  it('S12-03a 직접입력 계수 = 저장 뒤 창 꼴(e6 ④): 제목 줄 · 「온실가스 배출량 산식」+주황 「*직접입력」 · 라벨 넷(160 · 앞 둘 필수 점) · 회색 산식 · 가스 표 셋(포함한 가스만 · 가운데) · 비고 상자 · 옛 칸(출처·기준연도·Tier·포함 체크) 0', async () => {
    await open({ entryRowFactor: { '4': custom } });
    await ready();
    expect(screen.getByTestId('entry-factor-r1').textContent).toBe(custom.name);
    expect(screen.getByTestId('entry-factor-r2').textContent).not.toBe(
      custom.name,
    );
    fireEvent.click(screen.getByTestId('entry-factor-r1'));
    const dialog = await screen.findByTestId('entry-factor');
    has(dialog, ['w-[min(1320px,calc(100vw-64px))]']);
    expect(within(dialog).getByRole('heading', { level: 2 }).textContent).toBe(
      factorWords.title,
    );
    const formula = within(dialog).getByTestId('entry-factor-formula');
    expect(formula.querySelector('h3')!.textContent).toBe(
      `${factorWords.formulaHead}${factorWords.customMark}`,
    );
    has(within(dialog).getByTestId('entry-factor-custom-mark'), [
      'text-style-pre-body-04',
      'text-text-brand',
    ]);
    // 캔버스 v246 대조(감독 de 11-10): 제목 display-04 · 묶음 머리 셋 heading-02 · 묶음 안 gap-2.
    has(within(dialog).getByRole('heading', { level: 2 }), [
      'text-style-pre-display-04',
    ]);
    const groups = [...dialog.querySelectorAll('h3')];
    expect(groups.map((h3) => h3.textContent)).toStrictEqual([
      `${factorWords.formulaHead}${factorWords.customMark}`,
      factorWords.basics,
      factorWords.note,
    ]);
    for (const h3 of groups) {
      has(h3, ['text-style-pre-heading-02', 'text-text-primary']);
      has(h3.parentElement!, ['flex', 'flex-col', 'gap-2']);
    }
    expect(
      within(dialog)
        .getByTestId('entry-factor-basics')
        .querySelector('table thead'),
    ).not.toBeNull();
    const fields = within(dialog).getByTestId('entry-factor-fields');
    const labels = [...fields.querySelectorAll('th')];
    expect(labels.map((th) => th.textContent)).toStrictEqual([
      factorWords.name,
      factorWords.inputUnit,
      factorWords.ncv,
      factorWords.ncvUnit,
    ]);
    expect(
      labels.map((th) => th.querySelector('[data-required-mark]') !== null),
    ).toStrictEqual([true, true, false, false]);
    for (const th of labels) {
      has(th, ['w-40', 'bg-support-grey-subtle', 'text-text-tertiary']);
      // 디자인 대조 F3(판 .f12b-kv .k): 안 여백 24 · 오른쪽 1px quaternary · 필수 점은 칸 오른쪽 끝.
      has(th, ['px-6', 'border-r', 'border-border-quaternary']);
      expect(th.className.split(/\s+/)).not.toContain('px-4');
      has(th.firstElementChild!, ['flex', 'w-full', 'justify-between']);
    }
    has(fields, ['border-t', 'border-border-quaternary']);
    // F2: 저장 뒤 창만 묶음 사이 32 · 제목 줄과 「저장한 뒤…」는 한 묶음(그 안 8).
    has(dialog, ['gap-8']);
    const titleRow = within(dialog).getByRole('heading', {
      level: 2,
    }).parentElement!;
    has(titleRow.parentElement!, ['flex', 'flex-col', 'gap-2']);
    expect(titleRow.parentElement!.parentElement).toBe(dialog);
    // 반반: 한 줄에 라벨·값 둘씩.
    expect(
      [...fields.querySelectorAll('tr')].map((tr) => tr.children.length),
    ).toStrictEqual([4, 4]);
    const value = (name: string) =>
      labels.find((th) => th.textContent === name)!.nextElementSibling!
        .textContent;
    expect(value(factorWords.name)).toBe(custom.name);
    expect(value(factorWords.inputUnit)).toBe('부피 · kL');
    expect(value(factorWords.ncv)).toBe('36.1');
    expect(value(factorWords.ncvUnit)).toBe('에너지 · MJ/L');
    const line = within(dialog).getByTestId('entry-factor-formula-text');
    expect(line.textContent).toBe(factorWords.formulaText(['CO2'], true));
    has(line, ['text-style-pre-body-05', 'text-text-tertiary']);
    const heads = [
      ...dialog.querySelectorAll('table:not([data-testid]) thead th'),
    ];
    expect(heads.map((th) => th.textContent)).toStrictEqual([
      factorWords.gas,
      `${factorWords.value} (kgGHG/TJ)`,
      factorWords.gwp,
    ]);
    for (const th of heads) has(th, ['text-center', 'h-10']);
    // 포함한 가스만(끈 CH4 줄 0) · 칸 셋 가운데.
    expect(
      [...dialog.querySelectorAll('tr[data-testid^="entry-gas-"]')].map((tr) =>
        tr.getAttribute('data-testid'),
      ),
    ).toStrictEqual(['entry-gas-CO2']);
    const cells = [
      ...screen.getByTestId('entry-gas-CO2').querySelectorAll('td'),
    ];
    expect(cells.map((td) => td.textContent)).toStrictEqual([
      'CO2',
      '74100',
      '1',
    ]);
    for (const td of cells) has(td, ['text-center', 'border-border-tertiary']);
    const note = within(dialog).getByTestId('entry-factor-note');
    expect(note.textContent).toBe('지어낸 비고');
    has(note, [
      'border-border-tertiary',
      'text-text-tertiary',
      'min-h-14',
      'px-4',
      'py-3',
    ]);
    const body = dialog.textContent ?? '';
    for (const gone of [custom.source, '2023', '기준연도', 'Tier', '버전'])
      expect(body, gone).not.toContain(gone);
    expect(dialog.querySelectorAll('[role="checkbox"]')).toHaveLength(0);
    // 고객사(pool 없음) — [수정] 0.
    expect(within(dialog).queryByTestId('entry-factor-edit-open')).toBeNull();
    expect(within(dialog).getAllByRole('button')).toHaveLength(1);
  });

  it('S12-03a 저장 뒤 창 제목 줄 [수정] 끔: 운영 관리자 켬 · 그 행 고친 동안 끔 + 「저장한 뒤 바꿀 수 있어요」 · 다른 행 켬 · 잠긴 판 끔', async () => {
    const edit = words.factorEdit;
    const s8 = async (row = 'r1') => {
      fireEvent.click(screen.getByTestId(`entry-factor-${row}`));
      return screen.findByTestId('entry-factor');
    };
    const button = (dialog: HTMLElement) =>
      within(dialog).getByTestId('entry-factor-edit-open') as HTMLButtonElement;
    await open(
      { entryRowFactor: { '4': custom } },
      { operator: true, pool: true },
    );
    await ready();
    let dialog = await s8();
    expect(within(dialog).getByTestId('entry-factor-custom-mark')).toBeTruthy();
    expect(button(dialog).textContent).toBe(edit.cell);
    expect(button(dialog).disabled).toBe(false);
    expect(within(dialog).queryByTestId('entry-factor-edit-dirty')).toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: words.close }));
    type('r1', '2025-01', '99');
    dialog = await s8();
    expect(button(dialog).disabled).toBe(true);
    expect(
      within(dialog).getByTestId('entry-factor-edit-dirty').textContent,
    ).toBe(edit.dirty);
    fireEvent.click(button(dialog));
    expect(screen.queryByTestId('entry-factor-edit')).toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: words.close }));
    // 고침이 없는 다른 행(풀 계수 r2)은 아래 단추 켬.
    dialog = await s8('r2');
    expect(button(dialog).disabled).toBe(false);
    cleanup();

    await open(
      { entryRowFactor: { '4': custom } },
      { operator: true, pool: true, locked: true },
    );
    await ready();
    dialog = await s8();
    expect(within(dialog).getByTestId('entry-factor-custom-mark')).toBeTruthy();
    expect(button(dialog).disabled).toBe(true);
    expect(within(dialog).queryByTestId('entry-factor-edit-dirty')).toBeNull();
  });

  it('S12-03a 직접입력 비고가 비면 「-」 · 순발열량 끈 계수는 「쓰지 않음」·기준단위 「-」', async () => {
    await open({
      entryRowFactor: {
        '4': {
          ...custom,
          note: '',
          ncvEnabled: false,
          ncv: null,
          ncvUnit: null,
        },
      },
    });
    await ready();
    fireEvent.click(screen.getByTestId('entry-factor-r1'));
    const dialog = await screen.findByTestId('entry-factor');
    expect(within(dialog).getByTestId('entry-factor-note').textContent).toBe(
      factorWords.empty,
    );
    const labels = [
      ...within(dialog)
        .getByTestId('entry-factor-fields')
        .querySelectorAll('th'),
    ];
    const value = (name: string) =>
      labels.find((th) => th.textContent === name)!.nextElementSibling!
        .textContent;
    expect(value(factorWords.ncv)).toBe(factorWords.ncvOff);
    expect(value(factorWords.ncvUnit)).toBe(factorWords.empty);
  });

  it('풀 계수 보기는 옛 꼴 그대로 — 포함 체크 읽기 전용(켬 주황 · 끔 회색 상자) · 「*직접입력」 0', async () => {
    await open();
    await ready();
    fireEvent.click(screen.getByTestId('entry-factor-r1'));
    const dialog = await screen.findByTestId('entry-factor');
    expect(within(dialog).queryByTestId('entry-factor-custom-mark')).toBeNull();
    expect(within(dialog).queryByTestId('entry-factor-note')).toBeNull();
    // 풀 계수 보기는 F2·F3·F4 전(사이 기본 · 라벨 px-4 · 머리 h-11).
    expect(dialog.className.split(/\s+/)).not.toContain('gap-8');
    for (const th of within(dialog)
      .getByTestId('entry-factor-fields')
      .querySelectorAll('th'))
      expect(th.className.split(/\s+/)).not.toContain('px-6');
    for (const th of dialog.querySelectorAll(
      'table:not([data-testid]) thead th',
    ))
      has(th, ['h-11']);
    // 풀 계수 제목은 옛 꼴 그대로(heading-02).
    has(within(dialog).getByRole('heading', { level: 2 }), [
      'text-style-pre-heading-02',
    ]);
    const boxes = [
      ...dialog.querySelectorAll<HTMLButtonElement>(
        'tr[data-testid^="entry-gas-"] [role="checkbox"]',
      ),
    ];
    expect(boxes.length).toBeGreaterThan(1);
    for (const box of boxes) {
      expect(box.disabled).toBe(true);
      expect(box.className.split(/\s+/)).toEqual(
        expect.arrayContaining([
          'disabled:data-[state=checked]:bg-button-orange',
          'disabled:data-[state=checked]:border-button-orange',
          'disabled:data-[state=checked]:text-background-primary',
          'disabled:cursor-default',
          'disabled:bg-background-tertiary',
        ]),
      );
      expect(box.className).not.toContain(
        'disabled:data-[state=checked]:bg-background-tertiary',
      );
    }
  });
});

describe('모달 [저장] 하나(W12-1c ① — sid:MARC-ENT-529 · Q1·Q2)', () => {
  it('검사 먼저 — 첫 블록 맞음 · 둘째 블록 형식 오류면 요청 0 · 그 칸 초점 · 칸 아래 글', async () => {
    const { server } = await open();
    await ready();
    const headKey = keyOfHead();
    type(headKey, '2025-03', '77');
    type('r1', '2025-04', '1.');
    fireEvent.change(screen.getByRole('textbox', { name: words.memoLabel }), {
      target: { value: '지어낸 메모' },
    });
    const before = server.calls.length;
    saveAll();
    await waitFor(() =>
      expect(document.activeElement).toBe(amountCell('r1', '2025-04')),
    );
    expect(server.calls.length).toBe(before);
    expect(
      within(screen.getByTestId('entry-row-r1')).getByText(words.amountFormat),
    ).toBeTruthy();
    expect(amountCell(headKey, '2025-03').value).toBe('77');
    expect(screen.queryByTestId('toast')).toBeNull();
  });

  it('검사 먼저 — 두 블록 다 형식 오류면 초점은 화면 차례 첫 블록(본사) 칸 · 요청 0 · 두 블록 다 칸 아래 글 · 메모도 넘으면 초점은 여전히 칸', async () => {
    const { server } = await open();
    await ready();
    const headKey = keyOfHead();
    type('r1', '2025-04', '1.');
    type(headKey, '2025-03', '.5');
    const box = screen.getByRole('textbox', { name: words.memoLabel });
    fireEvent.change(box, { target: { value: '가'.repeat(2001) } });
    const before = server.calls.length;
    saveAll();
    await waitFor(() =>
      expect(document.activeElement).toBe(amountCell(headKey, '2025-03')),
    );
    expect(server.calls.length).toBe(before);
    expect(headBlock().getByText(words.amountFormat)).toBeTruthy();
    expect(plant().getByText(words.amountFormat)).toBeTruthy();
    expect(screen.getByTestId('entry-memo-error')).toBeTruthy();
  });

  it('중간 실패 — 앞 블록은 응답으로 갈음 · 실패 블록 고침 지킴 · 「일부 사업장은 저장하지 못했어요」 · 블록 한 줄 · 실패 블록 제목 초점 · 메모 PUT 0', async () => {
    const { server } = await open();
    await ready();
    server.override[SAVE_PLANT] = () => refusal(500, 'SERVER_ERROR');
    const headKey = keyOfHead();
    type(headKey, '2025-03', '77');
    type('r1', '2025-02', '4.5');
    fireEvent.change(screen.getByRole('textbox', { name: words.memoLabel }), {
      target: { value: '지어낸 메모' },
    });
    saveAll();
    await waitFor(() =>
      expect(screen.getByTestId('entry-foot-notice').textContent).toBe(
        '일부 사업장은 저장하지 못했어요',
      ),
    );
    expect(server.count(SAVE_HEAD)).toBe(2);
    expect(server.count(`PUT ${X}/memo`)).toBe(0);
    expect(screen.getByTestId('entry-notice-2').textContent).toBe(
      words.saveFailed,
    );
    expect(screen.getByTestId('entry-notice-1').textContent).toBe('');
    expect(amountCell('r1', '2025-02').value).toBe('4.5');
    expect(amountCell(headKey, '2025-03').value).toBe('77');
    expect(screen.queryByTestId('toast')).toBeNull();
    await waitFor(() =>
      expect(document.activeElement).toBe(
        plant().getByRole('heading', { level: 4 }),
      ),
    );
    // 고쳐 다시 누르면 남은 사업장 + 메모만 간다.
    delete server.override[SAVE_PLANT];
    const headSent = server.count(SAVE_HEAD);
    saveAll();
    await screen.findByTestId('toast');
    expect(server.count(SAVE_HEAD)).toBe(headSent);
    expect(server.count(`PUT ${X}/memo`)).toBe(1);
    expect(screen.getByTestId('entry-foot-notice').textContent).toBe('');
  });

  it('첫 사업장에서 실패하면 멈춤 — 뒤 사업장 PUT 0 · 메모 PUT 0 · 「일부」 글 없이 블록 한 줄만', async () => {
    const { server } = await open();
    await ready();
    server.override[SAVE_HEAD] = () => refusal(500, 'SERVER_ERROR');
    const headKey = keyOfHead();
    type(headKey, '2025-03', '77');
    type('r1', '2025-02', '4.5');
    fireEvent.change(screen.getByRole('textbox', { name: words.memoLabel }), {
      target: { value: '지어낸 메모' },
    });
    const plantBefore = server.count(SAVE_PLANT);
    saveAll();
    await waitFor(() =>
      expect(screen.getByTestId('entry-notice-1').textContent).toBe(
        words.saveFailed,
      ),
    );
    expect(server.count(SAVE_PLANT)).toBe(plantBefore);
    expect(server.count(`PUT ${X}/memo`)).toBe(0);
    expect(screen.getByTestId('entry-foot-notice').textContent).toBe('');
    expect(amountCell('r1', '2025-02').value).toBe('4.5');
  });

  it('둘째 사업장 422 → 그 칸 초점 · 「일부」 글 · 첫 사업장은 저장됨', async () => {
    const { server } = await open();
    await ready();
    server.override[SAVE_PLANT] = () =>
      refusal(422, 'VALIDATION_ERROR', {
        'rows.0.values.0.amount': ['x'],
      });
    const headKey = keyOfHead();
    type(headKey, '2025-03', '77');
    type('r2', '2025-05', '9');
    saveAll();
    await waitFor(() =>
      expect(document.activeElement).toBe(amountCell('r2', '2025-05')),
    );
    expect(screen.getByTestId('entry-foot-notice').textContent).toBe(
      '일부 사업장은 저장하지 못했어요',
    );
    expect(lastBody(server, SAVE_HEAD)).toMatchObject({
      rows: [{ values: [{ slot: '2025-03', amount: '77', estimated: false }] }],
    });
  });

  it('저장하는 동안 입력·메모·소수점·잠금·추가·삭제·[저장]이 꺼지고 닫기도 막힌다(critic 권고 1) — 끝나면 켜진다', async () => {
    const server = fakeGhgServer(options());
    const real = portsOf(server).entry;
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const onClose = vi.fn();
    render(
      <EntryDetailDialog
        port={{
          ...real,
          memo: async (...args) => {
            await gate;
            return real.memo(...args);
          },
        }}
        year={2025}
        nodeId="20"
        operator={false}
        onClose={onClose}
      />,
    );
    await ready();
    const box = screen.getByRole<HTMLTextAreaElement>('textbox', {
      name: words.memoLabel,
    });
    fireEvent.change(box, { target: { value: '지어낸 메모' } });
    saveAll();
    const off = () => [
      box,
      screen.getByRole<HTMLSelectElement>('combobox', {
        name: words.decimalsLabel,
      }),
      screen.getByRole<HTMLButtonElement>('button', { name: words.lock }),
      screen.getByRole<HTMLButtonElement>('button', { name: words.save }),
      ...within(screen.getByTestId('entry-site-1'))
        .getAllByRole<HTMLButtonElement>('button')
        .filter((b) =>
          ([words.add, words.remove] as string[]).includes(b.textContent!),
        ),
    ];
    await waitFor(() => expect(box.disabled).toBe(true));
    for (const element of off()) expect(element.disabled).toBe(true);
    fireEvent.click(screen.getAllByRole('button', { name: words.close })[0]!);
    expect(onClose).not.toHaveBeenCalled();
    release();
    await screen.findByTestId('toast');
    expect(box.value).toBe('지어낸 메모');
    expect(box.disabled).toBe(false);
    expect(
      screen.getByRole<HTMLButtonElement>('button', { name: words.save })
        .disabled,
    ).toBe(false);
  });
});

describe('잠금 아이콘 · 확인 창(W12-1c ① #10·#20 R6)', () => {
  it('제목 옆 아이콘 단추 — 글자 단추 0 · 이름·툴팁 「잠금」 / 운영 관리자 잠김은 「잠금 해제」 / 고객사 잠김은 그림(누름 0)', async () => {
    await open();
    await ready();
    const lock = screen.getByRole('button', { name: '잠금' });
    expect(lock.textContent).toBe('');
    expect(lock.querySelector('svg')).not.toBeNull();
    expect(lock.className).toContain('p-0.5');
    expect(lock.className).toContain('rounded-control');
    fireEvent.focus(lock);
    expect((await screen.findByRole('tooltip')).textContent).toContain('잠금');
    // S12-03: 잠금은 추정치 단추와 한 묶음(entry-lock-row) — 그 묶음이 제목 옆.
    expect(screen.getByRole('heading', { level: 2 }).parentElement).toBe(
      lock.parentElement!.parentElement,
    );
    cleanup();

    await open({}, { locked: true });
    await ready();
    expect(screen.queryByRole('button', { name: '잠금' })).toBeNull();
    expect(screen.queryByRole('button', { name: '잠금 해제' })).toBeNull();
    const picture = screen.getByRole('img', { name: words.lockedLabel });
    expect(picture.tagName).not.toBe('BUTTON');
    cleanup();

    await open({}, { locked: true, operator: true });
    await ready();
    const unlock = screen.getByRole('button', { name: '잠금 해제' });
    expect(unlock.textContent).toBe('');
    fireEvent.focus(unlock);
    expect((await screen.findByRole('tooltip')).textContent).toContain(
      '잠금 해제',
    );
  });

  it('R6 — 고객사 고친 것 없음 → 창 「잠그면 운영 관리자만 풀 수 있어요. 잠글까요?」(취소: 요청 0) · 고친 것 있음 → 「변경 내용을…」 · 운영 관리자 고친 것 없음 → 바로', async () => {
    const { server } = await open();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: words.lock }));
    const plain = await screen.findByTestId('entry-lock-confirm');
    expect(plain.textContent).toContain(
      '잠그면 운영 관리자만 풀 수 있어요. 잠글까요?',
    );
    expect(within(plain).getByRole('button', { name: '잠그기' })).toBeTruthy();
    fireEvent.click(within(plain).getByRole('button', { name: words.cancel }));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-lock-confirm')).toBeNull(),
    );
    expect(server.count(`POST ${X}/lock`)).toBe(0);
    type('r1', '2025-02', '5');
    fireEvent.click(screen.getByRole('button', { name: words.lock }));
    expect(
      (await screen.findByTestId('entry-lock-confirm')).textContent,
    ).toContain('변경 내용을 저장하지 않고 잠글까요?');
    cleanup();

    const admin = await open({}, { operator: true });
    await ready();
    fireEvent.click(screen.getByRole('button', { name: words.lock }));
    await screen.findByTestId('entry-locked');
    expect(screen.queryByTestId('entry-lock-confirm')).toBeNull();
    expect(admin.server.count(`POST ${X}/lock`)).toBe(1);
  });
});

describe('상세 모달 꼴(W12-1c ② — 판 S12-03 v196)', () => {
  const classes = (element: Element) => element.className.split(/\s+/);
  const has = (element: Element, wanted: readonly string[]) => {
    for (const name of wanted) expect(classes(element), name).toContain(name);
  };
  const HEAD = [
    'h-11',
    'bg-support-grey-subtle',
    'text-style-pre-body-05',
    'text-text-tertiary',
    'border-y',
    'border-border-tertiary',
    'px-4',
    'py-2',
  ];
  const BODY = [
    'h-14',
    'border-b',
    'border-border-quaternary',
    'align-middle',
    'px-4',
    'py-2',
  ];

  it('#1 #2 표 머리·칸 꼴 — 블록·총합이 같은 상수(머리 44 · 회색 바탕 · body-05 · 위아래 선 / 칸 56 · 옅은 선 · 가운데)', async () => {
    await open();
    await ready();
    for (const table of [
      screen.getByTestId('entry-totals'),
      screen.getByTestId('entry-scroll-2').querySelector('table')!,
    ]) {
      for (const th of table.querySelectorAll('th')) has(th, HEAD);
      for (const td of table.querySelectorAll('tbody td')) has(td, BODY);
      expect(classes(table)).toContain('border-separate');
    }
    expect(
      screen.getByTestId('entry-scroll-2').querySelector('th')!.className,
    ).not.toContain('text-style-pre-caption-02');
  });

  it('#3 #4 #13 입력 칸 36 꽉 · 오른쪽 정렬 · 체크 20 · 열 폭이 블록마다 같음(52·140·140·200 · 칸 최소 140)', async () => {
    await open();
    await ready();
    const input = amountCell('r1', '2025-01');
    has(input, [
      'h-9',
      'w-full',
      'rounded-component',
      'border-border-tertiary',
      'px-3',
      'text-right',
      'text-style-pre-body-06',
    ]);
    expect(classes(input)).not.toContain('w-24');
    for (const box of [
      plant().getByRole('checkbox', { name: words.selectLabel('1호기') }),
      plant().getByRole('checkbox', { name: words.naLabel('1호기') }),
    ])
      has(box, ['h-5', 'w-5']);
    const widthsOf = (site: string) => {
      const table = screen
        .getByTestId(`entry-scroll-${site}`)
        .querySelector('table')!;
      return {
        cols: [...table.querySelectorAll('col')].map((col) => col.style.width),
        min: table.style.minWidth,
        slots: table.querySelectorAll('th[data-slot]').length,
      };
    };
    const head = widthsOf('1');
    const plantCols = widthsOf('2');
    expect(head.cols.slice(0, 4)).toEqual(['52px', '140px', '140px', '200px']);
    expect(plantCols.cols.slice(0, 4)).toEqual(head.cols.slice(0, 4));
    expect(plantCols.cols.slice(-3)).toEqual(['140px', '140px', '140px']);
    expect(plantCols.min).toBe(`${minTableWidth(plantCols.slots)}px`);
    expect(minTableWidth(12)).toBe(
      52 + 140 + 140 + 200 + 140 * 12 + 140 + 140 + 140,
    );
    expect(COLUMN.emission).toBe(140);
  });

  it('#5 #6 [삭제][추가] 회색 단추 · 히스토리 「히스토리 확인」 알약', async () => {
    await open();
    await ready();
    for (const name of [words.remove, words.add])
      has(plant().getByRole('button', { name }), ['bg-button-grey', 'h-7']);
    const history = screen.getByTestId('entry-history-r1');
    expect(history.textContent).toBe('히스토리 확인');
    has(history, ['rounded-full', 'h-7', 'border-button-grey']);
  });

  it('#7 → S12-03 추정치 단추 하나: 잠금 바로 옆(사이 4) · 잠금과 같은 크기 · 물결 그림(판 .f12b-est — 디자인 대조 F1) · 켬 brand 바탕·글 / 끔 회색 글·바탕 없음(S12C1 e3f9708d) · aria-pressed · 이름 「{자산/시설명} 추정치」 · 칸 표식 0', async () => {
    await open();
    await ready();
    expect(
      document.querySelector('[data-testid^="entry-estimated-r"]'),
    ).toBeNull();
    const mark = screen.getByTestId('entry-estimated');
    const row = screen.getByTestId('entry-lock-row');
    expect(row.contains(mark)).toBe(true);
    has(row, ['gap-1']);
    expect(mark.previousElementSibling).toBe(screen.getByTestId('entry-lock'));
    expect(mark.textContent).toBe('');
    expect(
      mark.querySelector('svg[data-mark="estimated-wave"]'),
    ).not.toBeNull();
    expect(mark.getAttribute('aria-label')).toBe(
      words.estimatedAll(
        screen.getByRole('heading', { level: 2 }).textContent!,
      ),
    );
    // 켬 = 목록 추정치 열 estimatedBox(true). 끔 = 같은 크기·모양에 회색 글·바탕 없음(S12C1 e3f9708d — 이웃 잠금 열림 꼴, 옛 「같은 그림 opacity-40」 을 갈음).
    const shape = ['size-5', 'rounded-[2px]', 'p-0'];
    const on = ['bg-background-brand', 'text-text-brand'];
    const off = ['bg-transparent', 'text-text-tertiary'];
    expect(mark.getAttribute('aria-pressed')).toBe('false');
    has(mark, [...shape, ...off]);
    for (const old of [...on, 'opacity-40', 'bg-button-white'])
      expect(classes(mark), old).not.toContain(old);
    // 이웃 잠금 단추(열림)와 같은 글색·바탕.
    has(screen.getByTestId('entry-lock'), off);
    fireEvent.click(mark);
    expect(mark.getAttribute('aria-pressed')).toBe('true');
    has(mark, [...shape, ...on]);
    for (const old of [...off, 'opacity-40'])
      expect(classes(mark), old).not.toContain(old);
    has(mark, ['disabled:opacity-40']);
    fireEvent.click(mark);
    expect(mark.getAttribute('aria-pressed')).toBe('false');
    has(mark, off);
    for (const old of [
      'bg-background-secondary',
      'text-text-primary',
      'text-text-quaternary',
      'rounded-control',
    ])
      expect(classes(mark), old).not.toContain(old);
  });

  it('#8 #9 제목 display-04 · 사업장 body-02 primary · 「데이터 입력」 구역 제목 · 「경로」 라벨 + 값', async () => {
    await open();
    await ready();
    has(screen.getByRole('heading', { level: 2 }), [
      'text-style-pre-display-04',
    ]);
    has(plant().getByRole('heading', { level: 4 }), [
      'text-style-pre-body-02',
      'text-text-primary',
    ]);
    const input = screen.getByRole('heading', { name: '데이터 입력' });
    has(input, ['text-style-pre-heading-02']);
    expect(
      input.closest('section')!.contains(screen.getByTestId('entry-site-2')),
    ).toBe(true);
    const path = screen.getByTestId('entry-path');
    const label = path.previousElementSibling!;
    expect(label.textContent).toBe('경로');
    has(label, ['w-16']);
    has(path.parentElement!, ['text-style-pre-body-05', 'text-text-tertiary']);
  });

  it('#11 v196 총합 표 — 「사업장」 머리 · 연도 머리에 단위 없음 · 맨 끝 「단위」 열 · 총합 줄 회색·body-04 · • · 쉼표 · 값 왼쪽 · 소수점 고르기 폭 120', async () => {
    const { server, port } = await open();
    const out = await port.detail(2025, '20');
    if (out.kind !== 'ok') throw new Error('읽기 실패');
    server.override[DETAIL] = () =>
      json(200, {
        ...out.value,
        totals: {
          years: [2024, 2025],
          all: { '2024': '1234567.5', '2025': '999' },
          bySite: [
            { siteId: '2', siteName: '제1공장', values: { '2025': '1000' } },
          ],
        },
      });
    await ready();
    cleanup();
    render(
      <EntryDetailDialog
        port={port}
        year={2025}
        nodeId="20"
        operator={false}
        onClose={() => {}}
      />,
    );
    await ready();
    const totals = screen.getByTestId('entry-totals');
    expect(
      [...totals.querySelectorAll('th')].map((th) => th.textContent),
    ).toEqual(['사업장', '2024', '2025', '단위']);
    const all = [
      ...screen.getByTestId('entry-total-all').querySelectorAll('td'),
    ];
    expect(all.map((td) => td.textContent)).toEqual([
      '총합',
      '1,234,567.5',
      '999',
      out.value.unit,
    ]);
    for (const td of all) {
      has(td, ['bg-support-grey-subtle', 'text-style-pre-body-04']);
      // W12-1d N0: cn 으로 CELL 의 body-06 이 지워져 덧씌움이 이김.
      expect(classes(td)).not.toContain('text-style-pre-body-06');
      expect(classes(td)).not.toContain('text-right');
    }
    const site = [
      ...screen.getByTestId('entry-total-2').querySelectorAll('td'),
    ];
    expect(site.map((td) => td.textContent)).toEqual([
      '•제1공장',
      '',
      '1,000',
      out.value.unit,
    ]);
    expect(classes(site[0]!)).not.toContain('bg-support-grey-subtle');
    const decimals = screen.getByRole('combobox', {
      name: words.decimalsLabel,
    });
    has(decimals.parentElement!, ['w-[120px]']);
    expect(decimals.closest('label')!.textContent).toContain('소수점');
    has(decimals.closest('label')!, ['text-style-pre-caption-02', 'gap-2']);
    // 쉼표는 총합 표만(Q6) — 행 배출량 칸은 그대로.
    expect(screen.getByTestId('entry-emission-r1').textContent).not.toContain(
      ',',
    );
  });

  it('#11 쉼표 함수 — 정수부만 · 부호 · 소수 · 「-」·숫자 아님 그대로', () => {
    expect(withComma('1234567.125')).toBe('1,234,567.125');
    expect(withComma('-1234')).toBe('-1,234');
    expect(withComma('999')).toBe('999');
    expect(withComma('0.5')).toBe('0.5');
    expect(withComma('-')).toBe('-');
    expect(withComma('지어낸')).toBe('지어낸');
  });

  it('#12 표 위 가로 막대(12 · 회색 바탕 · 주황 커서 · aria-hidden) · N/A·배출량·히스토리 오른쪽 고정(sticky)', async () => {
    await open();
    await ready();
    const bar = screen.getByTestId('entry-bar-2');
    expect(bar.getAttribute('aria-hidden')).toBe('true');
    has(bar, ['h-3', 'bg-background-quaternary']);
    has(screen.getByTestId('entry-bar-2-cursor'), ['bg-text-brand', 'h-1.5']);
    expect(bar.nextElementSibling).toBe(screen.getByTestId('entry-scroll-2'));
    const heads = [
      ...screen.getByTestId('entry-scroll-2').querySelectorAll('thead th'),
    ].slice(-3);
    expect(heads[0]!.textContent).toBe('N/A');
    expect(heads[1]!.textContent).toMatch(/^배출량 \(.+\)$/);
    expect(heads[2]!.textContent).toBe('히스토리');
    has(heads[0]!, ['sticky', 'right-[280px]', 'border-l']);
    has(heads[1]!, ['sticky', 'right-[140px]']);
    has(heads[2]!, ['sticky', 'right-0']);
    // 본문 고정 칸 셋 다: sticky · right-* · 바탕(스크롤되는 칸이 비치지 않게).
    const cells = [
      ...screen.getByTestId('entry-row-r1').querySelectorAll('td'),
    ].slice(-3);
    expect(cells[1]).toBe(screen.getByTestId('entry-emission-r1'));
    for (const [td, right] of [
      [cells[0]!, 'right-[280px]'],
      [cells[1]!, 'right-[140px]'],
      [cells[2]!, 'right-0'],
    ] as const)
      has(td, ['sticky', right, 'bg-background-primary']);
    has(cells[0]!, ['border-l']);
    expect(COLUMN.history + COLUMN.emission).toBe(280);
  });

  it('#12 커서 셈 — 보이는 비율만큼 폭 · 스크롤 비율만큼 자리 · 넘침 없으면 꽉', () => {
    expect(thumbOf(1000, 500, 1000, 0)).toEqual({ left: 0, width: 500 });
    expect(thumbOf(1000, 500, 1000, 500)).toEqual({ left: 500, width: 500 });
    expect(thumbOf(1000, 500, 1000, 250)).toEqual({ left: 250, width: 500 });
    expect(thumbOf(1000, 800, 800, 0)).toEqual({ left: 0, width: 1000 });
    expect(thumbOf(100, 10, 10000, 0).width).toBe(24);
  });

  it('#14 메모 최소 88 · 안쪽 12·16 · 모서리 8 · 1px tertiary · 구역 사이 32 · 블록 사이 12', async () => {
    await open();
    await ready();
    const memo = screen.getByRole('textbox', { name: words.memoLabel });
    has(memo, [
      'min-h-[88px]',
      'px-4',
      'py-3',
      'rounded-component',
      'border-border-tertiary',
    ]);
    const blocks = screen.getByTestId('entry-site-2').parentElement!;
    has(blocks, ['gap-3']);
    has(blocks.closest('section')!.parentElement!, ['gap-8']);
  });

  it('숨김·뺌 그대로 — 행 배출량 열 있음 · 추정 뜻 글·툴팁 0 · 담당자·참고자료·계산식 0', async () => {
    await open();
    await ready();
    const dialog = document.querySelector('[data-screen="ghg-entry-detail"]')!;
    expect(screen.getByTestId('entry-emission-r1')).toBeTruthy();
    for (const word of [
      '추정치란',
      '추정 표식',
      '담당자',
      '참고자료',
      '계산식',
    ])
      expect(dialog.textContent).not.toContain(word);
  });
});

describe('곁 창 · 확인 창(W12-1c ③)', () => {
  const classes = (element: Element) => element.className.split(/\s+/);
  const has = (element: Element, wanted: readonly string[]) => {
    for (const name of wanted) expect(classes(element), name).toContain(name);
  };

  it('#15 추가 창 — 폭 980 · 표(전체 선택 · 「자산/시설명」 · 「상세 시설명」 · 줄 56 · 체크 20) · [취소] [확인] · 전체 선택은 보이는 것만 · 일부면 indeterminate', async () => {
    const { port } = await open();
    await ready();
    const out = await port.detail(2025, '20');
    if (out.kind !== 'ok') throw new Error('읽기 실패');
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    let add = await screen.findByTestId('entry-add');
    has(add, ['w-[980px]']);
    expect(
      [...add.querySelectorAll('thead th')].map((th) => th.textContent),
    ).toEqual(['', '자산/시설명', '상세 시설명']);
    for (const th of add.querySelectorAll('thead th')) has(th, ['h-11']);
    const rows = [...add.querySelectorAll('tbody tr')];
    expect(rows.map((tr) => tr.querySelectorAll('td')[1]!.textContent)).toEqual(
      rows.map(() => out.value.name),
    );
    expect(rows.map((tr) => tr.querySelectorAll('td')[2]!.textContent)).toEqual(
      ['3호기', '4호기'],
    );
    for (const td of add.querySelectorAll('tbody td')) has(td, ['h-14']);
    const all = within(add).getByRole('checkbox', { name: words.addAll });
    has(all, ['h-5', 'w-5']);
    // W12-1d N3: 같은 모듈 넷과 같은 낱말(글 원문).
    expect(all.getAttribute('aria-label')).toBe('전체 선택');
    expect(add.textContent).not.toContain('및 코드');
    expect(within(add).getByRole('button', { name: '확인' })).toBeTruthy();
    expect(within(add).queryByRole('button', { name: '추가' })).toBeNull();
    fireEvent.click(
      within(add).getByRole('checkbox', { name: words.addPick('3호기') }),
    );
    expect(all.getAttribute('aria-checked')).toBe('mixed');
    fireEvent.click(all);
    expect(all.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(all);
    expect(all.getAttribute('aria-checked')).toBe('false');
    fireEvent.click(
      within(add).getByRole('checkbox', { name: words.addPick('3호기') }),
    );
    fireEvent.click(within(add).getByRole('button', { name: '확인' }));
    await screen.findByTestId('entry-row-n6');
    // 다시 열면 이미 더한 3호기는 안 보이고, 모두 선택은 보이는 4호기만.
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    add = await screen.findByTestId('entry-add');
    expect(add.querySelectorAll('tbody tr')).toHaveLength(1);
    fireEvent.click(within(add).getByRole('checkbox', { name: words.addAll }));
    fireEvent.click(within(add).getByRole('button', { name: '확인' }));
    await screen.findByTestId('entry-row-n7');
    expect(screen.getAllByTestId('entry-row-n6')).toHaveLength(1);
  });

  it('#16 #1 #2 히스토리 — 화면 가득 폭 · 머리 회색 가운데(표 꼴 상수) · 줄 앞 점(1쪽 맨 위 주황 · 나머지 회색) · 수정자 주황 · 칸 이름 회색 · 화살표 주황 · 뒤 값 주황 굵게 · 「N/A」 주황 굵게', async () => {
    const { server } = await open();
    await ready();
    server.override[HISTORY] = () =>
      historyPage([
        historyLine({
          historyId: '51',
          kind: 'value',
          slot: '2025-03',
          before: '7',
          after: '9',
        }),
        historyLine({ historyId: '52', kind: 'na_on' }),
        historyLine({
          historyId: '53',
          kind: 'unit',
          before: 'kL',
          after: 'L',
        }),
      ]);
    fireEvent.click(screen.getByTestId('entry-history-r1'));
    const sheet = await screen.findByTestId('entry-history');
    await within(sheet).findByTestId('entry-history-51');
    has(sheet, ['w-[calc(100vw-64px)]']);
    expect(classes(sheet)).not.toContain('w-[800px]');
    for (const th of sheet.querySelectorAll('thead th'))
      has(th, ['h-11', 'bg-support-grey-subtle', 'text-center']);
    for (const td of sheet.querySelectorAll('tbody td'))
      has(td, ['h-14', 'border-border-quaternary']);
    const dots = within(sheet).getAllByTestId('entry-history-dot');
    expect(dots).toHaveLength(3);
    has(dots[0]!, ['bg-text-brand']);
    has(dots[1]!, ['bg-text-quaternary']);
    has(dots[2]!, ['bg-text-quaternary']);
    const row = screen.getByTestId('entry-history-51');
    has(row.querySelectorAll('td')[1]!, ['text-text-brand']);
    // W12-1d N0: CELL 의 text-secondary 가 지워져 주황이 이김.
    expect(classes(row.querySelectorAll('td')[1]!)).not.toContain(
      'text-text-secondary',
    );
    const part = (id: string, kind: string) =>
      screen
        .getByTestId(`entry-history-${id}`)
        .querySelector(`[data-part="${kind}"]`)!;
    expect(part('51', 'label').textContent).toBe('3월 ');
    has(part('51', 'label'), ['text-text-tertiary']);
    expect(part('51', 'before').textContent).toBe('7');
    expect(part('51', 'before').className).not.toContain('text-text-brand');
    has(part('51', 'arrow'), ['text-text-brand']);
    expect(part('51', 'after').textContent).toBe('9');
    has(part('51', 'after'), ['text-text-brand', 'text-style-pre-body-04']);
    expect(part('52', 'mark').textContent).toBe('N/A');
    has(part('52', 'mark'), ['text-text-brand', 'text-style-pre-body-04']);
    has(part('53', 'after'), ['text-text-brand']);
    expect(
      screen
        .getByTestId('entry-history-53')
        .querySelector('[data-testid="entry-history-change"]')!.textContent,
    ).toBe('단위를 변경했어요. kL → L');
  });

  it('#17 #18 #1 #2 계수 보기 — 폭 1320 상한 · 라벨 표(160 · 회색) · 「버전」·「버전 n」 · 단위 종류 한글 · 순발열량 기준단위 따로 · 「포함여부」「온실가스 종류」 · 「판」·영문 kind 0', async () => {
    const { port } = await open();
    await ready();
    const out = await port.detail(2025, '20');
    if (out.kind !== 'ok') throw new Error('읽기 실패');
    fireEvent.click(screen.getByTestId('entry-factor-r1'));
    const dialog = await screen.findByTestId('entry-factor');
    has(dialog, ['w-[min(1320px,calc(100vw-64px))]']);
    const fields = within(dialog).getByTestId('entry-factor-fields');
    const labels = [...fields.querySelectorAll('th')];
    for (const th of labels) {
      has(th, [
        'w-40',
        'bg-support-grey-subtle',
        'text-text-tertiary',
        'h-14',
        'text-style-pre-body-05',
      ]);
      // W12-1d N0: CELL 의 body-06·text-secondary 가 지워짐.
      expect(classes(th)).not.toContain('text-style-pre-body-06');
      expect(classes(th)).not.toContain('text-text-secondary');
    }
    const label = (name: string) =>
      labels.find((th) => th.textContent === name)!.nextElementSibling!
        .textContent;
    expect(label('버전')).toBe(`버전 ${out.value.factor.version}`);
    const kind = out.value.factor.inputUnit.kind;
    expect(label('투입량 기준단위')).toBe(
      `${GHG_TEXT.pool.unitKinds[kind] ?? kind} · ${out.value.factor.inputUnit.unit}`,
    );
    expect(GHG_TEXT.pool.unitKinds[kind]).toBeTruthy();
    expect(labels.map((th) => th.textContent)).toContain('순발열량 기준단위');
    // GX2 S12-03a: 순발열량은 값만(켬 0) · 산식 줄 = 포함한 가스마다 판 묶음을 「+」로.
    const factor = out.value.factor;
    expect(label('순발열량')).toBe(
      factor.ncvEnabled ? (factor.ncv ?? '-') : '쓰지 않음',
    );
    expect(label('순발열량')).not.toContain('켬');
    const included = factor.gases.filter((g) => g.enabled).map((g) => g.gas);
    expect(included.length).toBeGreaterThan(0);
    const pool = GHG_TEXT.factor;
    expect(label('산식')).toBe(
      included
        .map(
          (gas) =>
            `(${factor.ncvEnabled ? pool.formulaWithNcv(gas) : pool.formulaWithoutNcv(gas)})`,
        )
        .join(' + '),
    );
    if (factor.ncvEnabled)
      expect(label('산식')).toContain('(투입량 × 순발열량 ÷ 10^6) × ');
    for (const off of factor.gases.filter((g) => !g.enabled))
      expect(label('산식')).not.toContain(`${off.gas} 배출계수`);
    const body = dialog.textContent ?? '';
    for (const word of ['volume', 'mass', 'energy', 'electricity'])
      expect(body, word).not.toContain(word);
    expect(body).not.toMatch(/[0-9]판|판 \/|^판$/);
    expect(labels.map((th) => th.textContent)).not.toContain('판');
    const heads = [
      ...dialog.querySelectorAll('table:not([data-testid]) thead th'),
    ];
    // W12-1d N2: 판 S12-03a 차례 — 「포함여부」 → 「온실가스 종류」(머리·칸 같이).
    expect(heads.map((th) => th.textContent).slice(0, 2)).toEqual([
      '포함여부',
      '온실가스 종류',
    ]);
    const gasRow = dialog.querySelector('tr[data-testid^="entry-gas-"]')!;
    const gasCells = gasRow.querySelectorAll('td');
    expect(gasCells[0]!.querySelector('[role="checkbox"]')).not.toBeNull();
    expect(gasCells[1]!.textContent).toBe(
      gasRow.getAttribute('data-testid')!.replace('entry-gas-', ''),
    );
    for (const th of heads) has(th, ['h-11', 'bg-support-grey-subtle']);
  });

  it('#19 확인 창(삭제·나가기·잠금 같은 부품): 위 64 · 좌우 16 · 아래 32 · 글↔단추 32 · 글 text-secondary', async () => {
    await open();
    await ready();
    type('r1', '2025-02', '5');
    fireEvent.click(screen.getAllByRole('button', { name: words.close })[0]!);
    const leave = await screen.findByTestId('entry-leave');
    has(leave, ['w-[420px]', 'pt-16', 'px-4', 'pb-8']);
    // p-8(키트) 은 남지만 px·pt·pb 가 CSS 에서 뒤라 이긴다 — 잰 값은 e2e(위 64).
    has(leave.querySelector('form')!, ['gap-8']);
    has(within(leave).getByRole('heading'), ['text-text-secondary']);
  });
});

// ── 밴드 W12-2 ②: S7 입력주기 · S12 [복구] · 511 늦은 읽기 · 가짜 총합 · 머리 가운데 · h3 토큰 ──
const periodText = words.periodChange;
const PERIOD_PLANT = `PUT ${X}/sites/2/period`;
const slotHeads = (siteId: string) =>
  screen.getByTestId(`entry-site-${siteId}`).querySelectorAll('th[data-slot]');

/** 블록 머리 [입력 주기 변경] → 창 → 고르기(Enter 로 열고 menuitemradio) → [선택 완료]. */
async function pickPeriod(siteId: string, label: string, submit = true) {
  fireEvent.click(screen.getByTestId(`entry-period-open-${siteId}`));
  const dialog = await screen.findByTestId('entry-period');
  await act(async () => {
    fireEvent.keyDown(within(dialog).getByTestId('entry-period-select'), {
      key: 'Enter',
    });
  });
  await act(async () => {
    fireEvent.click(screen.getByRole('menuitemradio', { name: label }));
  });
  const ok = within(dialog).getByTestId(
    'entry-period-submit',
  ) as HTMLButtonElement;
  if (submit && !ok.disabled) fireEvent.click(ok);
  return { dialog, ok };
}

describe('W12-2 ② S7 입력주기', () => {
  it('[입력 주기 변경] → 창(제목·안내 글·자리글·년도·분기·월) → 분기 → PUT {period} 한 번 → 칸 넷 · 블록 알림 줄 · 다른 블록 고침 지킴', async () => {
    const { server } = await open();
    await ready();
    const headKey = keyOfHead();
    type(headKey, '2025-03', '55');
    expect(slotHeads('2')).toHaveLength(12);
    fireEvent.click(screen.getByTestId('entry-period-open-2'));
    const dialog = await screen.findByTestId('entry-period');
    expect(within(dialog).getByRole('heading').textContent).toBe(
      periodText.title,
    );
    expect(within(dialog).getByTestId('entry-period-notice').textContent).toBe(
      periodText.notice,
    );
    expect(within(dialog).queryByTestId('entry-period-dirty')).toBeNull();
    expect(within(dialog).getByTestId('entry-period-select').textContent).toBe(
      periodText.placeholder,
    );
    expect(
      (within(dialog).getByTestId('entry-period-submit') as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    await act(async () => {
      fireEvent.keyDown(within(dialog).getByTestId('entry-period-select'), {
        key: 'Enter',
      });
    });
    expect(
      screen.getAllByRole('menuitemradio').map((item) => item.textContent),
    ).toEqual(['년도', '분기', '월']);
    // 지금 주기(월)를 고르면 [선택 완료] 끔
    await act(async () => {
      fireEvent.click(screen.getByRole('menuitemradio', { name: '월' }));
    });
    expect(
      (within(dialog).getByTestId('entry-period-submit') as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    // 메뉴가 초점을 트리거로 돌려준 뒤에 다시 연다(앞서 열면 돌아오는 초점에 새 메뉴가 닫힌다 — W12-5 흔들림).
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(dialog).getByTestId('entry-period-select'),
      ),
    );
    await act(async () => {
      fireEvent.keyDown(within(dialog).getByTestId('entry-period-select'), {
        key: 'Enter',
      });
    });
    const quarter = await screen.findByRole('menuitemradio', { name: '분기' });
    await act(async () => {
      fireEvent.click(quarter);
    });
    fireEvent.click(within(dialog).getByTestId('entry-period-submit'));
    await waitFor(() => expect(slotHeads('2')).toHaveLength(4));
    expect(server.bodies(PERIOD_PLANT)).toStrictEqual([{ period: 'quarter' }]);
    expect(screen.getByTestId('entry-done-2').textContent).toBe(
      periodText.saved,
    );
    expect(screen.getByTestId('entry-done-2').getAttribute('role')).toBe(
      'status',
    );
    expect(screen.queryByTestId('entry-period')).toBeNull();
    // 다른 블록(본사) 고침은 그대로 · 블록 칸 갈음은 응답 그대로(옛 월 값 숨김)
    expect(amountCell(headKey, '2025-03').value).toBe('55');
    expect(screen.queryByTestId('entry-amount-r1:2025-01')).toBeNull();
    expect(amountCell('r1', '2025-Q1').value).toBe('');
  });

  it('Q4 고친 블록이면 안내 줄 뒤 「저장하지 않은 입력은 사라져요.」 · 바꾸면 그 블록 고침은 응답으로 갈음', async () => {
    await open();
    await ready();
    type('r1', '2025-02', '99');
    const { dialog } = await pickPeriod('2', '년도', false);
    expect(within(dialog).getByTestId('entry-period-dirty').textContent).toBe(
      periodText.dirty,
    );
    fireEvent.click(within(dialog).getByTestId('entry-period-submit'));
    await waitFor(() => expect(slotHeads('2')).toHaveLength(1));
    expect(amountCell('r1', '2025').value).toBe('');
  });

  it('잠긴 판에서 [입력 주기 변경] 끔 · 고객사·운영 관리자 둘 다 켬', async () => {
    await open({}, { locked: true });
    await ready();
    expect(
      (screen.getByTestId('entry-period-open-2') as HTMLButtonElement).disabled,
    ).toBe(true);
    cleanup();
    await open({}, { operator: true });
    await ready();
    expect(
      (screen.getByTestId('entry-period-open-2') as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it('거절 갈래: 422 period → 블록 한 줄 · 409 잠김 → 잠김 글 + 상세 다시 읽음 · 404 → 바뀜 글 + 다시 읽음', async () => {
    const { server } = await open();
    await ready();
    server.override[PERIOD_PLANT] = [
      () => refusal(422, 'VALIDATION_ERROR', { period: ['x'] }),
      () => refusal(409, 'LOCKED'),
      () => refusal(404, 'NOT_FOUND'),
    ];
    for (const want of [periodText.rejected, words.locked, words.gone]) {
      const reads = server.count(DETAIL);
      await pickPeriod('2', '분기');
      await waitFor(() =>
        expect(screen.getByTestId('entry-notice-2').textContent).toBe(want),
      );
      if (want !== periodText.rejected)
        await waitFor(() => expect(server.count(DETAIL)).toBe(reads + 1));
      expect(slotHeads('2')).toHaveLength(12);
      expect(screen.getByTestId('entry-done-2').textContent).toBe('');
    }
  });

  it('주기 쓰는 동안 그 블록 입력·[저장] 끔 → 끝나면 켜짐', async () => {
    let let_go = () => {};
    const { server } = await open(
      {},
      {
        wrap: (real) => ({
          ...real,
          period: async (...args) => {
            await new Promise<void>((resolve) => {
              let_go = resolve;
            });
            return real.period(...args);
          },
        }),
      },
    );
    await ready();
    await pickPeriod('2', '분기');
    await waitFor(() =>
      expect(amountCell('r1', '2025-01').disabled).toBe(true),
    );
    expect(
      (screen.getByTestId('entry-save') as HTMLButtonElement).disabled,
    ).toBe(true);
    await act(async () => let_go());
    await waitFor(() => expect(slotHeads('2')).toHaveLength(4));
    expect(amountCell('r1', '2025-Q1').disabled).toBe(false);
    expect(server.count(PERIOD_PLANT)).toBe(1);
  });

  it('주기 바꿈 전에 떠난 읽기(삭제 뒤)가 늦게 와도 버린다 — 칸 넷 그대로', async () => {
    const late = lateDetail();
    const { server } = await open({}, { wrap: late.wrap });
    await ready();
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.selectLabel('2호기') }),
    );
    fireEvent.click(plant().getByRole('button', { name: words.remove }));
    const confirm = await screen.findByTestId('entry-remove');
    late.hold();
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.removeOk }),
    );
    await waitFor(() => expect(server.count(REMOVE)).toBe(1));
    await pickPeriod('2', '분기');
    await waitFor(() => expect(slotHeads('2')).toHaveLength(4));
    expect(server.count(PERIOD_PLANT)).toBe(1);
    await late.release();
    expect(slotHeads('2')).toHaveLength(4);
    expect(screen.getByTestId('entry-done-2').textContent).toBe(
      periodText.saved,
    );
  });
});

describe('W12-2 ② S12 [복구]', () => {
  const HISTORY1 = `GET ${X}/rows/1/history`;
  const RESTORE = (h: string) => `POST ${X}/rows/1/history/${h}/restore`;
  const openHistory1 = async () => {
    fireEvent.click(screen.getByTestId('entry-history-r1'));
    return screen.findByTestId('entry-history');
  };
  const restoreButton = (id: string) =>
    screen.getByTestId(`entry-restore-${id}`) as HTMLButtonElement;

  it('열 차례 수정일·수정자·히스토리 복구·단위·변경 내용 · 단추 수 = 줄 수 · 켬 = restorable 참 & (factor 아님 | 운영 관리자 — W12-3 Q8)', async () => {
    for (const operator of [false, true]) {
      const { server } = await open({}, { operator });
      await ready();
      server.override[HISTORY1] = () =>
        historyPage([
          historyLine({ historyId: '51', restorable: false }),
          historyLine({ historyId: '52', restorable: true }),
          historyLine({ historyId: '53', kind: 'factor', restorable: true }),
          historyLine({ historyId: '54', kind: 'period', restorable: true }),
          historyLine({ historyId: '55', kind: 'na_on', restorable: false }),
        ]);
      const sheet = await openHistory1();
      await within(sheet).findByTestId('entry-history-51');
      expect(
        [...sheet.querySelectorAll('thead th')].map((th) => th.textContent),
      ).toEqual(['수정일', '수정자', '히스토리 복구', '단위', '변경 내용']);
      const all = within(sheet).getAllByRole('button', {
        name: /기록 복구$/,
      }) as HTMLButtonElement[];
      expect(all).toHaveLength(5);
      // W12-3 ③ 갈음: 계수 줄(53)은 고객사 끔 · 운영 관리자 켬(사유 창 — 아래 W12-3 #6).
      expect(
        all.filter((b) => !b.disabled).map((b) => b.dataset.testid),
      ).toEqual(
        operator ?
          ['entry-restore-52', 'entry-restore-53', 'entry-restore-54']
        : ['entry-restore-52', 'entry-restore-54'],
      );
      expect(restoreButton('53').disabled).toBe(!operator);
      cleanup();
    }
  });

  it('value 줄 [복구] → 확인 「이 기록으로 되돌릴까요?」 → POST 본문 {} → 칸 값 바뀜 · 「복구했어요」 · 1쪽 다시 읽음(새 줄 맨 위·맨 위 끔)', async () => {
    const { server } = await open();
    await ready();
    type('r1', '2025-01', '20');
    saveAll();
    await screen.findByTestId('toast');
    const sheet = within(await openHistory1());
    await sheet.findByTestId('entry-history-1');
    const reads = server.count(HISTORY1);
    expect(restoreButton('1').disabled).toBe(false);
    fireEvent.click(restoreButton('1'));
    const confirm = await screen.findByTestId('entry-restore-confirm');
    expect(within(confirm).getByRole('heading').textContent).toBe(
      history.restoreConfirm,
    );
    fireEvent.submit(confirm.querySelector('form')!);
    await waitFor(() =>
      expect(sheet.getByTestId('entry-history-note').textContent).toBe(
        history.restored,
      ),
    );
    expect(server.bodies(RESTORE('1'))).toStrictEqual([{}]);
    await waitFor(() => expect(server.count(HISTORY1)).toBe(reads + 1));
    expect(amountCell('r1', '2025-01').value).toBe('12.5');
    const rows = sheet.getAllByTestId(/^entry-history-\d+$/);
    expect(rows[0]!.textContent).toContain('1월 20 → 12.5');
    expect(
      (
        within(rows[0]!).getByRole('button', {
          name: /기록 복구$/,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });

  it('Q5 그 행이 고쳐진 동안 [복구] 전부 끔 + 판 위 「저장한 뒤 복구할 수 있어요」 · 다른 행 고침은 상관없음', async () => {
    await open();
    await ready();
    type('r2', '2025-02', '1');
    let sheet = within(await openHistory1());
    await sheet.findByTestId('entry-history-1');
    expect(sheet.queryByTestId('entry-history-dirty')).toBeNull();
    expect(restoreButton('1').disabled).toBe(false);
    fireEvent.click(sheet.getByRole('button', { name: words.close }));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-history')).toBeNull(),
    );
    type('r1', '2025-02', '7');
    sheet = within(await openHistory1());
    await sheet.findByTestId('entry-history-1');
    expect(sheet.getByTestId('entry-history-dirty').textContent).toBe(
      history.restoreDirty,
    );
    expect(
      sheet
        .getAllByRole('button', { name: /기록 복구$/ })
        .every((b) => (b as HTMLButtonElement).disabled),
    ).toBe(true);
  });

  it('Q6 거절 갈래(서버 차례) 한 줄씩: 404 · 422 historyId · 403 · 409 LOCKED · 409 RESTORE_STALE · 그 밖', async () => {
    const { server } = await open();
    await ready();
    server.override[HISTORY1] = () =>
      historyPage([
        historyLine({ historyId: '2', restorable: false }),
        historyLine({ historyId: '1', restorable: true }),
      ]);
    const cases: [() => Response, string, 'detail' | 'history' | null][] = [
      [() => refusal(404, 'NOT_FOUND'), history.gone, 'detail'],
      [
        () => refusal(422, 'VALIDATION_ERROR', { historyId: ['x'] }),
        history.restoreRejected,
        'history',
      ],
      [() => refusal(403, 'FORBIDDEN'), history.restoreForbidden, null],
      [() => refusal(409, 'LOCKED'), words.locked, 'detail'],
      [() => refusal(409, 'RESTORE_STALE'), history.restoreStale, 'history'],
      [() => refusal(500, 'SOMETHING_ELSE'), history.restoreFailed, null],
    ];
    const sheet = within(await openHistory1());
    await sheet.findByTestId('entry-history-1');
    for (const [answer, want, reread] of cases) {
      server.override[RESTORE('1')] = answer;
      const details = server.count(DETAIL);
      const histories = server.count(HISTORY1);
      await waitFor(() => expect(restoreButton('1').disabled).toBe(false));
      fireEvent.click(restoreButton('1'));
      fireEvent.submit(
        (await screen.findByTestId('entry-restore-confirm')).querySelector(
          'form',
        )!,
      );
      await waitFor(() =>
        expect(sheet.getByTestId('entry-history-note').textContent).toBe(want),
      );
      expect(sheet.getByTestId('entry-history-note').getAttribute('role')).toBe(
        'alert',
      );
      if (reread === 'detail')
        await waitFor(() => expect(server.count(DETAIL)).toBe(details + 1));
      if (reread === 'history')
        await waitFor(() => expect(server.count(HISTORY1)).toBe(histories + 1));
    }
  });

  it('period 줄 [복구] → 확인 글 = S7 안내 글 + Q4 한 줄(같은 블록 다른 행 고침) → 블록 주기 되돌림 · 옛 값 다시 보임 · 그 고침은 응답으로 갈음(월→분기→월→분기 뒤 after=월 줄)', async () => {
    const { server, onClose } = await open();
    await ready();
    for (const label of ['분기', '월', '분기']) {
      const n = server.count(PERIOD_PLANT);
      await pickPeriod('2', label);
      await waitFor(() => expect(server.count(PERIOD_PLANT)).toBe(n + 1));
    }
    await waitFor(() => expect(slotHeads('2')).toHaveLength(4));
    // 검증 R5: 같은 블록의 다른 행(r2)을 고쳐 둔다 — 칸 값은 주기가 바뀌면 어차피 사라지므로 주기를 넘어 남는 행 칸(N/A)으로.
    // r1 줄 [복구]는 켜진 채(Q5 는 그 행만), 확인 글에 Q4 한 줄.
    const na2 = () =>
      plant().getByRole('checkbox', {
        name: words.naLabel('2호기'),
      });
    expect(na2().getAttribute('aria-checked')).toBe('false');
    fireEvent.click(na2());
    expect(na2().getAttribute('aria-checked')).toBe('true');
    const sheet = within(await openHistory1());
    const lines = await sheet.findAllByTestId(/^entry-history-\d+$/);
    const toMonth = lines.find((line) =>
      line.textContent?.includes('분기별 → 월별'),
    )!;
    const button = within(toMonth).getByRole('button', {
      name: /기록 복구$/,
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    const confirm = await screen.findByTestId('entry-restore-confirm');
    expect(within(confirm).getByRole('heading').textContent).toBe(
      `${periodText.notice} ${periodText.dirty}`,
    );
    fireEvent.submit(confirm.querySelector('form')!);
    await waitFor(() => expect(slotHeads('2')).toHaveLength(12));
    expect(amountCell('r1', '2025-01').value).toBe('12.5');
    fireEvent.click(
      within(screen.getByTestId('entry-history')).getAllByRole('button', {
        name: words.close,
      })[0]!,
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-history')).toBeNull(),
    );
    // 그 블록은 응답 그대로 — r2 N/A 고침은 사라지고 남은 고침 0: 닫을 때 나가기 확인 없음.
    expect(na2().getAttribute('aria-checked')).toBe('false');
    fireEvent.click(screen.getAllByRole('button', { name: words.close })[0]!);
    expect(screen.queryByTestId('entry-leave')).toBeNull();
    await waitFor(() => expect(onClose).toHaveBeenCalledWith(true));
  });
});

describe('W12-2 ② 511 늦은 읽기 — 메모·소수점', () => {
  /** r2 를 지우고 그 뒤 다시 읽기를 잡아 둔다(쓰기보다 먼저 떠난 읽기). */
  const removeSecondHeld = async (hold: () => void) => {
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.selectLabel('2호기') }),
    );
    fireEvent.click(plant().getByRole('button', { name: words.remove }));
    const confirm = await screen.findByTestId('entry-remove');
    hold();
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.removeOk }),
    );
  };

  it('메모 저장 뒤 그 전에 떠난 읽기가 늦게 와도 메모·나가기 확인이 옛 값으로 안 돌아감 · 지운 행 뒤 읽기는 그대로 적용', async () => {
    const late = lateDetail();
    const { server, onClose } = await open({}, { wrap: late.wrap });
    await ready();
    await removeSecondHeld(late.hold);
    await waitFor(() => expect(server.count(REMOVE)).toBe(1));
    fireEvent.change(screen.getByRole('textbox', { name: words.memoLabel }), {
      target: { value: '지어낸 늦은 메모' },
    });
    saveAll();
    await screen.findByTestId('toast');
    await late.release();
    expect(
      (
        screen.getByRole('textbox', {
          name: words.memoLabel,
        }) as HTMLTextAreaElement
      ).value,
    ).toBe('지어낸 늦은 메모');
    expect(screen.queryByTestId('entry-row-r2')).toBeNull();
    fireEvent.click(screen.getAllByRole('button', { name: words.close })[0]!);
    expect(screen.queryByTestId('entry-leave')).toBeNull();
    await waitFor(() => expect(onClose).toHaveBeenCalledWith(true));
  });

  it('소수점 저장 뒤 그 전에 떠난 읽기가 늦게 와도 자릿수·표시가 옛 값으로 안 돌아감', async () => {
    const late = lateDetail();
    const { server } = await open(
      { entryEmission: '1.23456' },
      { wrap: late.wrap },
    );
    await ready();
    await removeSecondHeld(late.hold);
    await waitFor(() => expect(server.count(REMOVE)).toBe(1));
    fireEvent.change(
      screen.getByRole('combobox', { name: words.decimalsLabel }),
      { target: { value: '3' } },
    );
    await waitFor(() =>
      expect(screen.getByTestId('entry-emission-r1').textContent).toBe('1.235'),
    );
    await late.release();
    expect(screen.getByTestId('entry-emission-r1').textContent).toBe('1.235');
    expect(
      (
        screen.getByRole('combobox', {
          name: words.decimalsLabel,
        }) as HTMLSelectElement
      ).value,
    ).toBe('3');
    expect(screen.queryByTestId('entry-row-r2')).toBeNull();
  });
});

describe('W12-2 ② 가짜 총합·머리 가운데·h3 토큰', () => {
  it('가짜 총합: 저장된 행이 있으면 고른 해 칸이 비지 않음 · 값 없는 해는 빈칸(S12C1 9ddc00eb)', async () => {
    await open();
    await ready();
    const lines = screen
      .getByTestId('entry-totals')
      .querySelectorAll('tbody tr');
    expect(lines.length).toBeGreaterThanOrEqual(1);
    const cells = (key: string) =>
      [...screen.getByTestId(`entry-total-${key}`).querySelectorAll('td')].map(
        (td) => td.textContent,
      );
    // 열: 이름 · 2023 · 2024 · 2025 · 단위 — 제1공장 행 둘·본사 행 하나(지어낸 고정 1.5). formatAmount 는 자리를 자르기만 하고 0 을 채우지 않는다
    expect(cells('all').slice(1, 4)).toEqual(['', '', '4.5']);
    expect(cells('2').slice(1, 4)).toEqual(['', '', '3']);
    expect(cells('1')[3]).toBe('1.5');
  });

  it('머리 칸: 추가 창·히스토리 머리 class 에 text-center 있고 text-left 없음', async () => {
    const { server } = await open();
    await ready();
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    const add = await screen.findByTestId('entry-add');
    const addHeads = [...add.querySelectorAll('thead th')];
    expect(addHeads.length).toBeGreaterThan(0);
    expect(addHeads[0]!.className).toContain('text-center');
    expect(addHeads[0]!.className).not.toContain('text-left');
    fireEvent.click(within(add).getByRole('button', { name: words.cancel }));
    await waitFor(() => expect(screen.queryByTestId('entry-add')).toBeNull());
    server.override[`GET ${X}/rows/1/history`] = () =>
      historyPage([historyLine({ historyId: '61' })]);
    fireEvent.click(screen.getByTestId('entry-history-r1'));
    const sheet = await screen.findByTestId('entry-history');
    await within(sheet).findByTestId('entry-history-61');
    const heads = [...sheet.querySelectorAll('thead th')];
    expect(heads).toHaveLength(5);
    for (const th of heads) {
      expect(th.className).toContain('text-center');
      expect(th.className).not.toContain('text-left');
    }
  });

  it('세 h3(시설 목록·계수 목록·온실가스 종류) class = text-style-pre-heading-02 · heading-03 0', () => {
    const here = dirname(fileURLToPath(import.meta.url));
    for (const file of [
      '../../ghg-branch/ui/BranchScreen.tsx',
      '../../ghg-index-pool/ui/FacilityPanel.tsx',
      '../../ghg-index-pool/ui/FactorDialog.tsx',
    ]) {
      const source = readFileSync(resolve(here, file), 'utf8');
      const h3 = [...source.matchAll(/<h3[\s\S]*?className="([^"]*)"/g)].map(
        (m) => m[1],
      );
      expect(h3.length, file).toBeGreaterThan(0);
      for (const name of h3)
        expect(name, file).toContain('text-style-pre-heading-02');
      // 없는 토큰(셋째 단계) 0 — 글자 그대로 적지 않는다(§4 grep 이 이 시험 파일을 세지 않게).
      expect(source, file).not.toMatch(/pre-heading-0[3]/);
    }
  });
});

describe('W12-4 ③ 571 수정 사유 보기 창(Figma 29431:28330 · 줄 단추 29429:28326)', () => {
  const HISTORY1 = `GET ${X}/rows/1/history`;
  /** 지어낸 긴 사유(500자 — 서버 상한, 자름·말줄임 0 확인용). */
  const LONG = `지어낸 긴 사유 ${'가나다라마바사아자차'.repeat(50)}`.slice(
    0,
    500,
  );
  const TWO_LINES = '지어낸 첫 줄 사유\n지어낸 둘째 줄 사유';
  const seed = (server: ReturnType<typeof fakeGhgServer>) => {
    server.override[HISTORY1] = () =>
      historyPage([
        historyLine({ historyId: '61', kind: 'factor', reason: LONG }),
        historyLine({ historyId: '62', kind: 'factor', reason: TWO_LINES }),
        historyLine({ historyId: '63', kind: 'value', reason: null }),
      ]);
  };
  const openSheet = async () => {
    fireEvent.click(screen.getByTestId('entry-history-r1'));
    const sheet = await screen.findByTestId('entry-history');
    await within(sheet).findByTestId('entry-history-61');
    return sheet;
  };
  const bodyOf = (view: HTMLElement) =>
    within(view).getByTestId('entry-reason-view-body');

  it('사유 있는 줄만 「수정 사유」 단추(보이는 글 = 접근 이름, 복구와 같은 꼴) · 「변경 내용」 칸 안 · 줄 안 사유 글·툴팁 0', async () => {
    const { server } = await open();
    seed(server);
    await ready();
    const sheet = await openSheet();
    const opens = within(sheet).getAllByRole('button', {
      name: history.reasonOpen,
    });
    expect(opens.map((b) => b.dataset.testid)).toEqual([
      'entry-history-reason-61',
      'entry-history-reason-62',
    ]);
    expect(within(sheet).queryByTestId('entry-history-reason-63')).toBeNull();
    for (const button of opens) {
      expect(button.getAttribute('aria-label')).toBeNull();
      expect(button.textContent).toBe(history.reasonOpen);
      // 같은 줄 [복구]와 같은 꼴(outlineGrey sm).
      const restore = within(button.closest('tr')!).getByTestId(
        `entry-restore-${button.dataset.testid!.replace('entry-history-reason-', '')}`,
      );
      for (const word of restore.className.split(/\s+/).filter(Boolean))
        expect(button.className.split(/\s+/)).toContain(word);
      // 값(값 표 571 「같은 꼴 이웃」 — btn--sm 모서리 full · 좌우 10 · 높이 28): 둘 다 round sm.
      for (const one of [button, restore])
        expect(one.className.split(/\s+/)).toEqual(
          expect.arrayContaining(['rounded-full', 'px-2.5', 'h-7']),
        );
      // 「변경 내용」(마지막) 칸 안.
      const cells = [...button.closest('tr')!.querySelectorAll('td')];
      expect(cells.at(-1)!.contains(button)).toBe(true);
    }
    expect(within(sheet).queryByTestId('entry-history-reason')).toBeNull();
    expect(sheet.textContent).not.toContain(history.reason(TWO_LINES));
    expect(sheet.textContent).not.toContain(LONG);
  });

  it('단추 → 창: 제목 「수정 사유」 · 본문 = 그 줄 사유 전체(500자 · 말줄임 0 · 줄바꿈 그대로) · 초점 [확인] · [확인]으로 닫힘 → 초점 = 연 단추', async () => {
    const { server } = await open();
    seed(server);
    await ready();
    const sheet = await openSheet();
    const opener = within(sheet).getByTestId('entry-history-reason-61');
    opener.focus();
    fireEvent.click(opener);
    const view = await screen.findByTestId('entry-reason-view');
    expect(within(view).getByRole('heading').textContent).toBe(
      history.reasonView.title,
    );
    const body = bodyOf(view);
    expect(body.textContent).toBe(LONG);
    expect(body.textContent).toHaveLength(500);
    const look = body.className.split(/\s+/);
    expect(look).toEqual(
      expect.arrayContaining([
        'whitespace-pre-wrap',
        'break-all',
        'max-h-[320px]',
        'overflow-y-auto',
      ]),
    );
    expect(look).not.toContain('truncate');
    const ok = within(view).getByRole('button', {
      name: history.reasonView.ok,
    });
    await waitFor(() => expect(document.activeElement).toBe(ok));
    fireEvent.click(ok);
    await waitFor(() =>
      expect(screen.queryByTestId('entry-reason-view')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(opener));
    // 판(히스토리)은 그대로.
    expect(screen.getByTestId('entry-history')).toBeTruthy();
  });

  it('둘째 줄 단추 → 둘째 사유(줄 섞임 0, 줄바꿈 그대로) · Esc 로 닫힘 → 초점 = 그 단추', async () => {
    const { server } = await open();
    seed(server);
    await ready();
    const sheet = await openSheet();
    const second = within(sheet).getByTestId('entry-history-reason-62');
    fireEvent.click(second);
    const view = await screen.findByTestId('entry-reason-view');
    expect(bodyOf(view).textContent).toBe(TWO_LINES);
    expect(bodyOf(view).textContent).not.toContain(LONG.slice(0, 20));
    fireEvent.keyDown(view, { key: 'Escape' });
    await waitFor(() =>
      expect(screen.queryByTestId('entry-reason-view')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(second));
    expect(screen.getByTestId('entry-history')).toBeTruthy();
  });
});

describe('W12-3 ③ S8 [배출계수 수정] · S9 · S11 · 계수 줄 복구', () => {
  const edit = words.factorEdit;
  const reasonWords = words.reason;
  const PUT_FACTOR = `PUT ${X}/rows/1/factor`;
  const HISTORY1 = `GET ${X}/rows/1/history`;
  const RESTORE = (h: string) => `POST ${X}/rows/1/history/${h}/restore`;
  const byId = (id: string) => document.getElementById(id) as HTMLElement;

  const openS8 = async (row = 'r1') => {
    fireEvent.click(screen.getByTestId(`entry-factor-${row}`));
    return screen.findByTestId('entry-factor');
  };
  const openS9 = async () => {
    const s8 = await openS8();
    fireEvent.click(within(s8).getByTestId('entry-factor-edit-open'));
    const s9 = await screen.findByTestId('entry-factor-edit');
    await within(s9).findByTestId('entry-factor-pick');
    return s9;
  };
  /** S8 이 떠 있는 채로 S9 를 다시 연다. */
  const openS9Again = async () => {
    fireEvent.click(screen.getByTestId('entry-factor-edit-open'));
    const s9 = await screen.findByTestId('entry-factor-edit');
    await within(s9).findByTestId('entry-factor-pick');
    return s9;
  };
  const next = () => fireEvent.click(screen.getByTestId('entry-factor-next'));
  const giveReason = async (text: string, testId = 'entry-reason') => {
    const dialog = await screen.findByTestId(testId);
    fireEvent.change(within(dialog).getByTestId('entry-reason-input'), {
      target: { value: text },
    });
    fireEvent.submit(dialog.querySelector('form')!);
    return dialog;
  };
  const pick = (name: string) =>
    fireEvent.click(screen.getByRole('checkbox', { name: edit.pick(name) }));
  /** 직접 입력 칸 채움(지어낸 값). 순발열량 끔 · CO2 하나 켬. */
  const fillCustom = (input: { kind: string; unit: string }) => {
    const set = (id: string, value: string) =>
      fireEvent.change(byId(id), { target: { value } });
    set('entry-custom-name', '지어낸 직접 계수');
    set('entry-custom-source', '지어낸 직접 출처');
    set('entry-custom-baseYear', '2024');
    set('entry-custom-tier', '2');
    set('entry-custom-countryCode', 'KR');
    set('entry-custom-industryCode', 'other');
    set('entry-custom-inputUnit', input.kind);
    set('entry-custom-inputUnit-unit', input.unit);
    fireEvent.click(
      screen.getByRole('switch', { name: GHG_TEXT.factor.gasToggle('CO2') }),
    );
    set('entry-custom-gases-CO2-factor', '1.25');
    set('entry-custom-gases-CO2-gwp', '1');
  };

  it('#1 배선: pool 없음(고객사) → 단추 0 · 운영 관리자 저장된 행 → 단추 · 잠김 끔 · 그 행 고친 동안 끔 + 「저장한 뒤 바꿀 수 있어요」 · 새 행 보기는 단추 0', async () => {
    await open({}, { operator: false });
    await ready();
    let s8 = await openS8();
    expect(within(s8).queryByTestId('entry-factor-edit-open')).toBeNull();
    expect(s8.textContent).not.toContain(edit.button);
    cleanup();

    await open({}, { operator: true, pool: true });
    await ready();
    s8 = await openS8();
    const button = within(s8).getByTestId(
      'entry-factor-edit-open',
    ) as HTMLButtonElement;
    expect(button.textContent).toBe(edit.button);
    expect(button.disabled).toBe(false);
    expect(within(s8).queryByTestId('entry-factor-edit-dirty')).toBeNull();
    cleanup();

    await open({}, { operator: true, pool: true, locked: true });
    await ready();
    s8 = await openS8();
    expect(
      (within(s8).getByTestId('entry-factor-edit-open') as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    cleanup();

    await open({}, { operator: true, pool: true });
    await ready();
    type('r1', '2025-01', '99');
    s8 = await openS8();
    expect(
      (within(s8).getByTestId('entry-factor-edit-open') as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(within(s8).getByTestId('entry-factor-edit-dirty').textContent).toBe(
      edit.dirty,
    );
    fireEvent.click(within(s8).getByRole('button', { name: words.close }));
    // 다른 행(r2)은 고침이 없어 켬.
    s8 = await openS8('r2');
    expect(
      (within(s8).getByTestId('entry-factor-edit-open') as HTMLButtonElement)
        .disabled,
    ).toBe(false);
    fireEvent.click(within(s8).getByRole('button', { name: words.close }));
    // 새 행(저장 전)은 계수 보기만 — 단추 0.
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    const add = await screen.findByTestId('entry-add');
    fireEvent.click(
      within(add).getByRole('checkbox', { name: words.addPick('3호기') }),
    );
    fireEvent.click(within(add).getByRole('button', { name: words.addOk }));
    await screen.findByTestId('entry-row-n6');
    s8 = await openS8('n6');
    expect(within(s8).queryByTestId('entry-factor-edit-open')).toBeNull();
  });

  it('#2 S9 선택: 머리 다섯 · 풀 계수 줄 + 「직접 입력」 · 지금 계수 고름 · 같으면 [다음] 끔 → 다른 계수 → 사유 → PUT {factorId, reason} 한 번 → 배출량 바뀜 · 창 셋 닫힘 · 블록 알림 · 히스토리 사유', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    const before = screen.getByTestId('entry-emission-r1').textContent;
    const reads = server.count(DETAIL);
    const s9 = await openS9();
    expect(within(s9).getByRole('heading').textContent).toBe(edit.title);
    expect(
      [...s9.querySelectorAll('thead th')].slice(1).map((th) => th.textContent),
    ).toEqual(['배출계수명', '출처', '산업', '투입량 기준단위', 'Tier']);
    const rows = s9.querySelectorAll('tbody tr');
    expect(rows).toHaveLength(3);
    expect(rows[2]!.textContent).toContain(edit.custom);
    expect(rows[0]!.textContent).toContain('지어낸 경유 계수');
    expect(rows[0]!.textContent).toContain('지어낸 에너지');
    // 지금 계수(행 계수 없음 = 기본 21) 고름 · 같으면 [다음] 끔.
    expect(
      (
        screen.getByRole('checkbox', {
          name: edit.pick('지어낸 경유 계수'),
        }) as HTMLButtonElement
      ).getAttribute('data-state'),
    ).toBe('checked');
    expect(
      (screen.getByTestId('entry-factor-next') as HTMLButtonElement).disabled,
    ).toBe(true);
    pick('지어낸 등유 계수');
    next();
    await giveReason('  지어낸 바꿈 사유  ');
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    expect(server.bodies(PUT_FACTOR)).toStrictEqual([
      { factorId: 23, reason: '지어낸 바꿈 사유' },
    ]);
    expect(screen.queryByTestId('entry-factor')).toBeNull();
    expect(screen.queryByTestId('entry-reason')).toBeNull();
    const after = screen.getByTestId('entry-emission-r1').textContent;
    expect(after).not.toBe(before);
    expect(after).toContain('2.23');
    expect(screen.getByTestId('entry-done-2').textContent).toBe(edit.done);
    // asked 올림: 성공 뒤 상세 다시 읽기 0(응답 그대로).
    expect(server.count(DETAIL)).toBe(reads);
    fireEvent.click(screen.getByTestId('entry-history-r1'));
    const sheet = await screen.findByTestId('entry-history');
    // W12-4 ③ 571 갈음: 줄 안 사유 글(「사유: …」 말줄임·툴팁) 0 → 「수정 사유」 단추 → 보기 창 본문 = 그 사유.
    const opens = await within(sheet).findAllByRole('button', {
      name: history.reasonOpen,
    });
    expect(opens).toHaveLength(1);
    expect(sheet.textContent).not.toContain(history.reason('지어낸 바꿈 사유'));
    fireEvent.click(opens[0]!);
    const view = await screen.findByTestId('entry-reason-view');
    expect(within(view).getByTestId('entry-reason-view-body').textContent).toBe(
      '지어낸 바꿈 사유',
    );
    expect(server.count(HISTORY1)).toBeGreaterThan(0);
  });

  it('#2 Q7 바꿈 전에 떠난 읽기(삭제 뒤)가 늦게 와도 버린다 — 배출량이 옛 계수로 안 돌아감', async () => {
    const late = lateDetail();
    const { server } = await open(
      {},
      { operator: true, pool: true, wrap: late.wrap },
    );
    await ready();
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.selectLabel('2호기') }),
    );
    fireEvent.click(plant().getByRole('button', { name: words.remove }));
    const confirm = await screen.findByTestId('entry-remove');
    late.hold();
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.removeOk }),
    );
    await waitFor(() => expect(server.count(REMOVE)).toBe(1));
    await openS9();
    pick('지어낸 등유 계수');
    next();
    await giveReason('지어낸 사유');
    await waitFor(() =>
      expect(screen.getByTestId('entry-emission-r1').textContent).toContain(
        '2.23',
      ),
    );
    await late.release();
    expect(screen.getByTestId('entry-emission-r1').textContent).toContain(
      '2.23',
    );
  });

  it('#2 Y1 바꾼 뒤 닫으면 onClose(true) — S2 가 다시 읽는다', async () => {
    const { onClose } = await open({}, { operator: true, pool: true });
    await ready();
    await openS9();
    pick('지어낸 등유 계수');
    next();
    await giveReason('지어낸 사유');
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    const detail = document.querySelector(
      '[data-screen="ghg-entry-detail"]',
    ) as HTMLElement;
    fireEvent.click(within(detail).getByRole('button', { name: words.close }));
    expect(screen.queryByTestId('entry-leave')).toBeNull();
    expect(onClose).toHaveBeenCalledWith(true);
  });

  it('#2 Y5 Q7 같은 블록 다른 행의 저장 안 한 고침은 계수 바꿈 뒤에도 남는다', async () => {
    await open({}, { operator: true, pool: true });
    await ready();
    type('r2', '2025-02', '41');
    await openS9();
    pick('지어낸 등유 계수');
    next();
    await giveReason('지어낸 사유');
    await waitFor(() =>
      expect(screen.getByTestId('entry-emission-r1').textContent).toContain(
        '2.23',
      ),
    );
    expect(amountCell('r2', '2025-02').value).toBe('41');
  });

  it('#3 Y2 S9 [이전]·✕: 바꾼 것 없으면 바로 닫힘 · 고른 것을 바꾸면 「저장하지 않고 닫을까요?」(계속 입력 → 그대로 · 닫기 → 닫힘, 요청 0)', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    let s9 = await openS9();
    fireEvent.click(within(s9).getByRole('button', { name: edit.prev }));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    expect(screen.queryByTestId('entry-factor-edit-leave')).toBeNull();
    s9 = await openS9Again();
    pick('지어낸 등유 계수');
    fireEvent.click(within(s9).getByRole('button', { name: edit.prev }));
    const leave = await screen.findByTestId('entry-factor-edit-leave');
    expect(within(leave).getByRole('heading').textContent).toBe(
      GHG_TEXT.factor.leaveConfirm,
    );
    // W12-4 ② 564: 초기 모달만 초점 「취소」 — 남의 ConfirmModal 은 기본('confirm') 그대로 확인 단추.
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(leave).getByRole('button', { name: GHG_TEXT.factor.leave }),
      ),
    );
    fireEvent.click(
      within(leave).getByRole('button', { name: GHG_TEXT.factor.stay }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit-leave')).toBeNull(),
    );
    expect(screen.getByTestId('entry-factor-edit')).toBeTruthy();
    fireEvent.click(within(s9).getByRole('button', { name: edit.prev }));
    fireEvent.submit(
      (await screen.findByTestId('entry-factor-edit-leave')).querySelector(
        'form',
      )!,
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    expect(server.count(PUT_FACTOR)).toBe(0);
  });

  it('#3 S9 직접 입력: [다음] 때 validateFactor — 첫 오류 칸 초점 · 요청 0 → 채우면 S11 → 본문 {custom(배출량 단위 = 기본), reason} · [이전]은 고름으로', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    const s9 = await openS9();
    pick(edit.custom);
    next();
    await within(s9).findByTestId('entry-custom-form');
    expect(within(s9).getByRole('heading', { level: 2 }).textContent).toBe(
      edit.customTitle,
    );
    expect(byId('entry-custom-emissionUnit')).toBeNull();
    next();
    await waitFor(() =>
      expect(document.activeElement?.id).toBe('entry-custom-name'),
    );
    expect(screen.getByTestId('entry-custom-name-error').textContent).toBe(
      GHG_TEXT.factor.required,
    );
    expect(screen.queryByTestId('entry-reason')).toBeNull();
    fireEvent.click(within(s9).getByRole('button', { name: edit.prev }));
    expect(s9.getAttribute('data-step')).toBe('pick');
    next();
    fillCustom({ kind: 'volume', unit: 'kL' });
    next();
    await giveReason('지어낸 직접 사유');
    await waitFor(() => expect(server.bodies(PUT_FACTOR)).toHaveLength(1));
    const body = server.bodies(PUT_FACTOR)[0] as {
      custom: Record<string, unknown>;
      reason: string;
    };
    expect(body.reason).toBe('지어낸 직접 사유');
    expect(body.custom.emissionUnit).toStrictEqual({
      kind: 'mass',
      unit: 'tCO2-eq',
    });
    expect(body.custom.inputUnit).toStrictEqual({ kind: 'volume', unit: 'kL' });
    expect(body.custom.ncvEnabled).toBe(false);
    await waitFor(() =>
      expect(screen.getByTestId('entry-emission-r1').textContent).toMatch(
        /^3\./,
      ),
    );
  });

  it('S12-03a 직접 입력 저장 뒤: S9 만 닫히고 S8 이 새 계수로 다시 열림(저장 뒤 창) → 제목 줄 [수정] → S9 직접 입력 단계 · 저장 값으로 채움 · [이전] outline-grey · 안 바꾸면 ✕ 바로 닫힘 · 고쳐 다시 → 본문에 채운 값', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    await openS9();
    pick(edit.custom);
    next();
    fillCustom({ kind: 'volume', unit: 'kL' });
    next();
    await giveReason('지어낸 직접 사유');
    await waitFor(() => expect(server.bodies(PUT_FACTOR)).toHaveLength(1));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    let s8 = screen.getByTestId('entry-factor');
    expect(within(s8).getByTestId('entry-factor-custom-mark')).toBeTruthy();
    expect(
      within(s8).getByTestId('entry-factor-fields').querySelector('td')!
        .textContent,
    ).toBe('지어낸 직접 계수');
    expect(within(s8).getByTestId('entry-gas-CO2').textContent).toContain(
      '1.25',
    );
    expect(screen.getByTestId('entry-done-2').textContent).toBe(edit.done);
    const open03a = within(s8).getByTestId(
      'entry-factor-edit-open',
    ) as HTMLButtonElement;
    expect(open03a.textContent).toBe(edit.cell);
    expect(open03a.disabled).toBe(false);
    // 제목 줄 오른쪽(제목과 같은 줄) · 아래 단추 줄 0.
    expect(open03a.parentElement!.querySelector('h2')!.textContent).toBe(
      words.factor.title,
    );
    expect(s8.textContent).not.toContain(edit.button);
    fireEvent.click(open03a);
    let s9 = await screen.findByTestId('entry-factor-edit');
    expect(s9.getAttribute('data-step')).toBe('custom');
    // 디자인 대조 F6: 직접 입력 단계 사이는 32 그대로.
    expect(s9.className.split(/\s+/)).toContain('gap-8');
    await within(s9).findByTestId('entry-custom-form');
    expect(within(s9).getByRole('heading', { level: 2 }).textContent).toBe(
      edit.customTitle,
    );
    const valueOf = (id: string) => (byId(id) as HTMLInputElement).value;
    expect(
      [
        'entry-custom-name',
        'entry-custom-source',
        'entry-custom-baseYear',
        'entry-custom-tier',
        'entry-custom-countryCode',
        'entry-custom-industryCode',
        'entry-custom-inputUnit',
        'entry-custom-inputUnit-unit',
        'entry-custom-gases-CO2-factor',
        'entry-custom-gases-CO2-gwp',
      ].map(valueOf),
    ).toStrictEqual([
      '지어낸 직접 계수',
      '지어낸 직접 출처',
      '2024',
      '2',
      'KR',
      'other',
      'volume',
      'kL',
      '1.25',
      '1',
    ]);
    expect(
      screen
        .getByRole('switch', { name: GHG_TEXT.factor.gasToggle('CO2') })
        .getAttribute('aria-checked'),
    ).toBe('true');
    // R1(b2): 직접 입력 단계의 [이전]도 outline-grey.
    const prev = within(s9).getByRole('button', { name: edit.prev });
    expect(prev.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['bg-button-white', 'border-button-grey']),
    );
    // 저장 값 = 처음 판 → 안 바꾸고 ✕ 는 확인 없이 닫힘 · S8 남음 · 요청 0.
    fireEvent.click(within(s9).getByRole('button', { name: words.close }));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    expect(screen.queryByTestId('entry-factor-edit-leave')).toBeNull();
    expect(screen.getByTestId('entry-factor')).toBeTruthy();
    expect(server.bodies(PUT_FACTOR)).toHaveLength(1);
    // 고쳐 다시 저장 → 채운 값이 본문에 실림 · S8 이 고친 이름으로.
    fireEvent.click(screen.getByTestId('entry-factor-edit-open'));
    s9 = await screen.findByTestId('entry-factor-edit');
    await within(s9).findByTestId('entry-custom-form');
    fireEvent.change(byId('entry-custom-name'), {
      target: { value: '지어낸 고친 계수' },
    });
    next();
    await giveReason('지어낸 고침 사유');
    await waitFor(() => expect(server.bodies(PUT_FACTOR)).toHaveLength(2));
    const body = server.bodies(PUT_FACTOR)[1] as {
      custom: Record<string, unknown>;
    };
    expect(body.custom).toMatchObject({
      name: '지어낸 고친 계수',
      source: '지어낸 직접 출처',
      baseYear: 2024,
      tier: 2,
      inputUnit: { kind: 'volume', unit: 'kL' },
      gases: expect.arrayContaining([
        { gas: 'CO2', enabled: true, factor: '1.25', gwp: '1' },
      ]),
    });
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    s8 = screen.getByTestId('entry-factor');
    expect(
      within(s8).getByTestId('entry-factor-fields').querySelector('td')!
        .textContent,
    ).toBe('지어낸 고친 계수');
  });

  it('S12-03a 저장 뒤 창에서 고른 단계로 [이전] → 다시 「직접 입력」 [다음] 은 채운 칸 그대로(빈 판으로 안 돌아감)', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    await openS9();
    pick(edit.custom);
    next();
    fillCustom({ kind: 'volume', unit: 'kL' });
    next();
    await giveReason('지어낸 직접 사유');
    await waitFor(() => expect(server.bodies(PUT_FACTOR)).toHaveLength(1));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    fireEvent.click(screen.getByTestId('entry-factor-edit-open'));
    const s9 = await screen.findByTestId('entry-factor-edit');
    await within(s9).findByTestId('entry-custom-form');
    fireEvent.click(within(s9).getByRole('button', { name: edit.prev }));
    expect(s9.getAttribute('data-step')).toBe('pick');
    await within(s9).findByTestId('entry-factor-pick');
    next();
    await within(s9).findByTestId('entry-custom-form');
    expect((byId('entry-custom-name') as HTMLInputElement).value).toBe(
      '지어낸 직접 계수',
    );
  });

  it('S12-03a 출처 칸 [수정](S9 바로)은 직접입력 행이어도 고름 단계에서 열고 「직접 입력」 [다음] 은 빈 판(e6 덧)', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    await openS9();
    pick(edit.custom);
    next();
    fillCustom({ kind: 'volume', unit: 'kL' });
    next();
    await giveReason('지어낸 직접 사유');
    await waitFor(() => expect(server.bodies(PUT_FACTOR)).toHaveLength(1));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    fireEvent.click(
      within(screen.getByTestId('entry-factor')).getByRole('button', {
        name: words.close,
      }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor')).toBeNull(),
    );
    fireEvent.click(screen.getByTestId('entry-factor-edit-r1'));
    const s9 = await screen.findByTestId('entry-factor-edit');
    expect(s9.getAttribute('data-step')).toBe('pick');
    await within(s9).findByTestId('entry-factor-pick');
    next();
    await within(s9).findByTestId('entry-custom-form');
    expect((byId('entry-custom-name') as HTMLInputElement).value).toBe('');
  });

  it('W12-4 ① 573 직접 입력 고르기 상자: 공통 NativeSelect 꼴(appearance-none · 옛 꼴 0 · ▾ 하나 · w-full) · 빈 [다음] 뒤 aria-invalid="true" + 칸 글', async () => {
    await open({}, { operator: true, pool: true });
    await ready();
    const s9 = await openS9();
    pick(edit.custom);
    next();
    const form = await within(s9).findByTestId('entry-custom-form');
    const classes = (element: Element) =>
      (element.getAttribute('class') ?? '').split(/\s+/);
    const boxes = within(form).getAllByRole('combobox');
    expect(boxes.length).toBeGreaterThanOrEqual(5);
    for (const select of boxes) {
      const look = classes(select);
      expect(look).toContain('appearance-none');
      for (const word of ['h-10', 'rounded-control', 'border-border-secondary'])
        expect(look).not.toContain(word);
      const wrap = select.parentElement!;
      expect(wrap.tagName).toBe('SPAN');
      expect(classes(wrap)).toEqual(
        expect.arrayContaining(['w-full', 'min-w-0']),
      );
      expect(wrap.querySelectorAll('svg')).toHaveLength(1);
    }
    next();
    await waitFor(() =>
      expect(
        within(form)
          .getAllByRole('combobox')
          .some((select) => select.getAttribute('aria-invalid') === 'true'),
      ).toBe(true),
    );
    // 단위 이름 칸(-unit)은 BASE 부터 aria-describedby 가 없다(종류 칸이 글을 가리킴) — 있는 칸만 글을 본다.
    for (const select of within(form)
      .getAllByRole('combobox')
      .filter(
        (one) =>
          one.getAttribute('aria-invalid') === 'true' &&
          one.hasAttribute('aria-describedby'),
      ))
      expect(
        document.getElementById(select.getAttribute('aria-describedby')!)
          ?.textContent,
      ).toBeTruthy();
  });

  it('#4 S11: 빈 사유·빈칸만·501자 → 요청 0 · 칸 글 · 500자는 보냄 · 서버 422 reason → 같은 칸 · 창 꼴(제목·주의 띠·안내·내용·자리글·세기 0)', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    await openS9();
    pick('지어낸 등유 계수');
    next();
    const dialog = await screen.findByTestId('entry-reason');
    expect(within(dialog).getByRole('heading').textContent).toBe(
      reasonWords.title,
    );
    expect(within(dialog).getByTestId('entry-reason-warning').textContent).toBe(
      reasonWords.warning,
    );
    expect(dialog.textContent).toContain(reasonWords.guide);
    expect(within(dialog).getByLabelText(reasonWords.label)).toBeTruthy();
    expect(
      within(dialog)
        .getByTestId('entry-reason-input')
        .getAttribute('placeholder'),
    ).toBe(reasonWords.placeholder);
    expect(dialog.textContent).not.toMatch(/\d+\s*\/\s*\d+/);
    for (const [text, why] of [
      ['', reasonWords.required],
      ['   ', reasonWords.required],
      ['가'.repeat(501), reasonWords.tooLong(500)],
    ] as const) {
      await giveReason(text);
      expect(
        within(dialog).getByTestId('entry-reason-input-error').textContent,
      ).toBe(why);
    }
    expect(reasonWords.tooLong(500)).toBe('500자까지 쓸 수 있어요');
    expect(server.count(PUT_FACTOR)).toBe(0);
    server.override[PUT_FACTOR] = () =>
      refusal(422, 'VALIDATION_ERROR', { reason: ['지어낸'] });
    await giveReason(` ${'가'.repeat(500)} `);
    await waitFor(() =>
      expect(
        within(dialog).getByTestId('entry-reason-input-error').textContent,
      ).toBe(reasonWords.rejected),
    );
    expect(server.bodies(PUT_FACTOR)).toStrictEqual([
      { factorId: 23, reason: '가'.repeat(500) },
    ]);
    expect(screen.getByTestId('entry-reason')).toBeTruthy();
  });

  it('#5 548: 422 custom.inputUnit(가짜 흉내 — GWh) → 사유 창 닫힘 · 직접 입력 투입 단위 칸 아래 그 글 · ncvUnit·factorUnit 은 각 칸 · 고쳐 다시 → 200', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    const s9 = await openS9();
    pick(edit.custom);
    next();
    fillCustom({ kind: 'electricity', unit: 'GWh' });
    next();
    await giveReason('지어낸 단위 사유');
    await waitFor(() =>
      expect(
        screen.getByTestId('entry-custom-inputUnit-error').textContent,
      ).toBe(edit.unitProblem['custom.inputUnit']),
    );
    expect(screen.queryByTestId('entry-reason')).toBeNull();
    expect(s9.getAttribute('data-step')).toBe('custom');
    // Y7: 548 글이 붙은 칸으로 초점.
    await waitFor(() =>
      expect(document.activeElement?.id).toBe('entry-custom-inputUnit'),
    );
    expect(edit.unitProblem['custom.inputUnit']).toBe(
      '이 시설의 단위로 바꿀 수 없는 단위예요',
    );
    for (const field of ['ncvUnit', 'factorUnit']) {
      server.override[PUT_FACTOR] = () =>
        refusal(422, 'VALIDATION_ERROR', { [`custom.${field}`]: ['지어낸'] });
      next();
      await giveReason('지어낸 단위 사유');
      await waitFor(() =>
        expect(
          screen.getByTestId(`entry-custom-${field}-error`).textContent,
        ).toBe(edit.unitProblem[`custom.${field}`]),
      );
    }
    delete server.override[PUT_FACTOR];
    fireEvent.change(byId('entry-custom-inputUnit'), {
      target: { value: 'volume' },
    });
    fireEvent.change(byId('entry-custom-inputUnit-unit'), {
      target: { value: 'kL' },
    });
    expect(screen.queryByTestId('entry-custom-inputUnit-error')).toBeNull();
    next();
    await giveReason('지어낸 단위 사유');
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    expect(screen.getByTestId('entry-emission-r1').textContent).toMatch(/^3\./);
  });

  it('#5 그 밖 거절: forbidden · 404(다시 읽음) · 409 잠김(다시 읽음) · 500 → S9 한 줄', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    await openS9();
    pick('지어낸 등유 계수');
    for (const [answer, text, reread] of [
      [() => refusal(403, 'FORBIDDEN'), edit.forbidden, false],
      [() => refusal(404, 'NOT_FOUND'), words.gone, true],
      [() => refusal(409, 'LOCKED'), words.locked, true],
      [() => json(500, {}), edit.failed, false],
    ] as const) {
      server.override[PUT_FACTOR] = answer;
      const reads = server.count(DETAIL);
      next();
      await giveReason('지어낸 사유');
      await waitFor(() =>
        expect(screen.getByTestId('entry-factor-edit-line').textContent).toBe(
          text,
        ),
      );
      expect(screen.queryByTestId('entry-reason')).toBeNull();
      await waitFor(() =>
        expect(server.count(DETAIL)).toBe(reread ? reads + 1 : reads),
      );
    }
  });

  it('#5b 558: 422 fields.factorId → 사유 창 닫힘 · 고르기 단계 줄에 서버 글 그대로 · 다시 읽지 않음 · 다른 계수로 다시 → 200', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    const s9 = await openS9();
    pick('지어낸 등유 계수');
    for (const text of ['지어낸 단위 거절이에요', '지어낸 지운 계수예요']) {
      server.override[PUT_FACTOR] = () =>
        refusal(422, 'VALIDATION_ERROR', { factorId: [text] });
      const reads = server.count(DETAIL);
      next();
      await giveReason('지어낸 사유');
      await waitFor(() =>
        expect(screen.getByTestId('entry-factor-edit-line').textContent).toBe(
          text,
        ),
      );
      expect(screen.queryByTestId('entry-reason')).toBeNull();
      expect(s9.getAttribute('data-step')).toBe('pick');
      expect(server.count(DETAIL)).toBe(reads);
    }
    delete server.override[PUT_FACTOR];
    next();
    expect(screen.queryByTestId('entry-factor-edit-line')).toBeNull();
    await giveReason('지어낸 사유');
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
  });

  it('#6 계수 줄 복구: 고객사 끔 · 운영 관리자 켬 → 사유 창 → 본문 {reason} → 계수 되돌아옴 · value 줄은 {} · 고친 행 끔 · 422 reason 은 창 칸 · forbidden 한 줄', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    // 계수 둘 바꿈(21→23→21 은 0 바뀜이라 23 → 직접 입력) — 맨 위 줄은 복구 불가, 그 아래 factor 줄을 되돌린다.
    await openS9();
    pick('지어낸 등유 계수');
    next();
    await giveReason('지어낸 첫 사유');
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    await openS9();
    pick(edit.custom);
    next();
    fillCustom({ kind: 'volume', unit: 'kL' });
    next();
    await giveReason('지어낸 둘째 사유');
    await waitFor(() =>
      expect(screen.getByTestId('entry-emission-r1').textContent).toMatch(
        /^3\./,
      ),
    );
    fireEvent.click(screen.getByTestId('entry-history-r1'));
    const sheet = await screen.findByTestId('entry-history');
    await within(sheet).findAllByRole('button', { name: history.reasonOpen });
    const factorRows = within(sheet)
      .getAllByTestId(/^entry-history-\d+$/)
      .filter((row) => row.textContent?.includes('배출계수를 변경했어요'));
    expect(factorRows).toHaveLength(2);
    const older = factorRows[1]!.dataset.testid!.replace('entry-history-', '');
    const button = screen.getByTestId(
      `entry-restore-${older}`,
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    server.override[RESTORE(older)] = () =>
      refusal(422, 'VALIDATION_ERROR', { reason: ['지어낸'] });
    fireEvent.click(button);
    expect(screen.queryByTestId('entry-restore-confirm')).toBeNull();
    const dialog = await giveReason('지어낸 복구 사유', 'entry-restore-reason');
    await waitFor(() =>
      expect(
        within(dialog).getByTestId('entry-reason-input-error').textContent,
      ).toBe(reasonWords.rejected),
    );
    delete server.override[RESTORE(older)];
    await giveReason('  지어낸 복구 사유  ', 'entry-restore-reason');
    await waitFor(() =>
      expect(within(sheet).getByTestId('entry-history-note').textContent).toBe(
        history.restored,
      ),
    );
    expect(server.bodies(RESTORE(older)).at(-1)).toStrictEqual({
      reason: '지어낸 복구 사유',
    });
    expect(screen.queryByTestId('entry-restore-reason')).toBeNull();
    // 첫 바꿈의 뒤 계수(23)로 되돌아옴.
    await waitFor(() =>
      expect(screen.getByTestId('entry-emission-r1').textContent).toContain(
        '2.23',
      ),
    );
    // forbidden 갈래는 한 줄(사유 창 닫음).
    server.override[RESTORE(older)] = () => refusal(403, 'FORBIDDEN');
    const again = await within(sheet).findByTestId(`entry-restore-${older}`);
    await waitFor(() =>
      expect((again as HTMLButtonElement).disabled).toBe(false),
    );
    fireEvent.click(again);
    await giveReason('지어낸 사유', 'entry-restore-reason');
    await waitFor(() =>
      expect(within(sheet).getByTestId('entry-history-note').textContent).toBe(
        history.restoreForbidden,
      ),
    );
    expect(screen.queryByTestId('entry-restore-reason')).toBeNull();
  });

  it('#6 고객사: factor 줄 [복구] 끔 · value 줄 복구 본문 {} 그대로 · 고친 행이면 factor 줄도 끔(운영 관리자)', async () => {
    for (const operator of [false, true]) {
      const { server } = await open({}, { operator, pool: operator });
      await ready();
      server.override[HISTORY1] = () =>
        historyPage([
          historyLine({ historyId: '61', restorable: false }),
          historyLine({ historyId: '62', kind: 'factor', restorable: true }),
          historyLine({ historyId: '63', restorable: true }),
        ]);
      fireEvent.click(screen.getByTestId('entry-history-r1'));
      const sheet = await screen.findByTestId('entry-history');
      await within(sheet).findByTestId('entry-history-62');
      const factorButton = within(sheet).getByTestId(
        'entry-restore-62',
      ) as HTMLButtonElement;
      expect(factorButton.disabled).toBe(!operator);
      // 서버 기록에 없는 줄이라 404 — 본문 꼴만 잰다.
      fireEvent.click(within(sheet).getByTestId('entry-restore-63'));
      const confirm = await screen.findByTestId('entry-restore-confirm');
      fireEvent.submit(confirm.querySelector('form')!);
      await waitFor(() => expect(server.count(RESTORE('63'))).toBe(1));
      expect(server.bodies(RESTORE('63'))).toStrictEqual([{}]);
      cleanup();
    }
    await open({}, { operator: true, pool: true });
    await ready();
    type('r1', '2025-01', '77');
    fireEvent.click(screen.getByTestId('entry-history-r1'));
    const sheet = await screen.findByTestId('entry-history');
    await within(sheet).findByTestId('entry-history-dirty');
    for (const button of within(sheet).queryAllByRole('button', {
      name: /기록 복구$/,
    }))
      expect((button as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('S12-05 자산/시설 없는 잎의 상세(sid:MARC-ENT-644)', () => {
  /** 잎 22(기본 계수 있음)를 고른 해 — 이 회사엔 그 코드의 자산/시설이 없다(본사만) → 상세 sites 0. */
  async function openBare(withOrganization = true) {
    const server = fakeGhgServer({
      ...fakeSelectionOptions(),
      branches: [fakeHeadquarters()],
      chosen: { 2025: ['22'] },
    });
    const port = portsOf(server).entry;
    const onOrganization = vi.fn();
    const onClose = vi.fn();
    render(
      <EntryDetailDialog
        port={port}
        year={2025}
        nodeId="22"
        operator={false}
        onClose={onClose}
        onOrganization={withOrganization ? onOrganization : undefined}
      />,
    );
    await screen.findByTestId('entry-save');
    return { onOrganization, onClose };
  }

  it('sites 0 → 「데이터 입력」 자리에 안내 한 줄 + [조직구조로] · 블록 0 · 누르면 onOrganization', async () => {
    const { onOrganization } = await openBare();
    const line = screen.getByTestId('entry-no-facilities-line');
    expect(line.textContent).toContain(words.noFacilities);
    expect(line.className).toContain('gap-2');
    expect(document.querySelector('[data-testid^="entry-site-"]')).toBeNull();
    fireEvent.click(
      within(line).getByRole('button', { name: words.toOrganization }),
    );
    expect(onOrganization).toHaveBeenCalledTimes(1);
  });

  it('고친 것(메모)이 있으면 [조직구조로]는 나가기 확인을 거친다 — 취소면 안 감 · 확인이면 onOrganization', async () => {
    const { onOrganization, onClose } = await openBare();
    fireEvent.change(screen.getByRole('textbox', { name: words.memoLabel }), {
      target: { value: '지어낸 메모' },
    });
    const go = () =>
      fireEvent.click(
        screen.getByRole('button', { name: words.toOrganization }),
      );
    go();
    const confirm = await screen.findByTestId('entry-leave');
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.cancel }),
    );
    await waitFor(() => expect(screen.queryByTestId('entry-leave')).toBeNull());
    expect(onOrganization).not.toHaveBeenCalled();
    go();
    fireEvent.submit(
      (await screen.findByTestId('entry-leave')).querySelector('form')!,
    );
    expect(onOrganization).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('onOrganization 이 없으면 안내 글만(단추 0) · sites 가 있으면 안내 0', async () => {
    await openBare(false);
    expect(screen.getByTestId('entry-no-facilities-line').textContent).toBe(
      words.noFacilities,
    );
    expect(
      screen.queryByRole('button', { name: words.toOrganization }),
    ).toBeNull();
    cleanup();
    await open();
    await screen.findByTestId('entry-site-2');
    expect(screen.queryByTestId('entry-no-facilities')).toBeNull();
  });
});

describe('S12-03 추정치 단추 하나(sid:MARC-ENT-644 · 발주서 Q6)', () => {
  type Body = {
    rows: {
      rowId?: number;
      siteFacilityId: number;
      na: boolean;
      values: { slot: string; amount: string | null; estimated: boolean }[];
    }[];
  };
  const mark = () => screen.getByTestId('entry-estimated');
  const pressed = () => mark().getAttribute('aria-pressed');

  it('켬: N/A 아닌 모든 줄·칸(빈 칸 포함)이 추정 · 금액은 그대로 · 다시 누르면 전부 끔 → 고친 것 0', async () => {
    const { server } = await open();
    await ready();
    expect(pressed()).toBe('false');
    fireEvent.click(mark());
    expect(pressed()).toBe('true');
    fireEvent.click(mark());
    expect(pressed()).toBe('false');
    const before = server.calls.length;
    saveAll();
    await waitFor(() =>
      expect(screen.getByTestId('entry-foot-notice').textContent).toBe(
        '바꾼 내용이 없어요',
      ),
    );
    expect(server.calls.length).toBe(before);
    fireEvent.click(mark());
    saveAll();
    await screen.findByTestId('toast');
    for (const key of [SAVE_PLANT, SAVE_HEAD]) {
      const body = lastBody(server, key) as Body;
      expect(body.rows.length).toBeGreaterThan(0);
      for (const row of body.rows) {
        expect(row.values.length).toBe(12); // 빈 칸도 실림
        expect(row.values.every((v) => v.estimated)).toBe(true);
      }
    }
    const r1 = (lastBody(server, SAVE_PLANT) as Body).rows.find(
      (row) => row.rowId === 1,
    )!;
    expect(r1.values.find((v) => v.slot === '2025-02')!.amount).toBe('3');
  });

  it('섞임: 칸 하나라도 추정이면 켜짐(목록 뜻) · 누르면 전부 끔', async () => {
    const { server, port } = await open();
    const out = await port.saveRows(2025, '20', '2', [
      {
        rowId: 1,
        siteFacilityId: 4,
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-02', amount: '3', estimated: true }],
      },
    ]);
    expect(out.kind).toBe('ok');
    cleanup();
    render(
      <EntryDetailDialog
        port={portsOf(server).entry}
        year={2025}
        nodeId="20"
        operator={false}
        onClose={vi.fn()}
      />,
    );
    await ready();
    expect(pressed()).toBe('true');
    fireEvent.click(mark());
    expect(pressed()).toBe('false');
    saveAll();
    await screen.findByTestId('toast');
    expect(lastBody(server, SAVE_PLANT)).toStrictEqual({
      rows: [
        {
          rowId: 1,
          siteFacilityId: 4,
          unit: 'kL',
          na: false,
          values: [{ slot: '2025-02', amount: '3', estimated: false }],
        },
      ],
    });
  });

  it('N/A 줄은 켜지 않음 · N/A 줄 추정만으로는 켜짐 아님', async () => {
    const { server } = await open();
    await ready();
    fireEvent.click(
      plant().getByRole('checkbox', { name: words.naLabel('1호기') }),
    );
    fireEvent.click(mark());
    saveAll();
    await screen.findByTestId('toast');
    const r1 = (lastBody(server, SAVE_PLANT) as Body).rows.find(
      (row) => row.rowId === 1,
    )!;
    expect(r1.na).toBe(true);
    expect(r1.values.every((v) => !v.estimated)).toBe(true);
    const others = (lastBody(server, SAVE_PLANT) as Body).rows.filter(
      (row) => row.rowId !== 1,
    );
    expect(others.length).toBeGreaterThan(0);
    expect(others.every((row) => row.values.every((v) => v.estimated))).toBe(
      true,
    );
  });

  it('켜진 동안 [추가]한 줄도 추정 · 잠긴 판·저장 중 단추 끔', async () => {
    const { server } = await open();
    await ready();
    fireEvent.click(mark());
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    const add = await screen.findByTestId('entry-add');
    fireEvent.click(within(add).getAllByRole('checkbox')[0]!);
    fireEvent.click(within(add).getByRole('button', { name: words.addOk }));
    await waitFor(() =>
      expect(
        document.querySelector('[data-testid^="entry-row-n"]'),
      ).not.toBeNull(),
    );
    saveAll();
    await screen.findByTestId('toast');
    const fresh = (lastBody(server, SAVE_PLANT) as Body).rows.find(
      (row) => row.rowId === undefined,
    )!;
    expect(fresh.values).toHaveLength(12); // 분모: 빈 새 줄인데 칸이 실렸다 = 추정이 켜짐
    expect(fresh.values.every((v) => v.estimated)).toBe(true);
    cleanup();
    await open({}, { locked: true });
    await ready();
    expect((mark() as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('S12-03 추정치 단추 — 저장 중', () => {
  it('[저장]이 응답을 기다리는 동안 추정치 단추 끔 · 끝나면 켬', async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await open(
      {},
      {
        wrap: (real) => ({
          ...real,
          saveRows: async (...args) => {
            await gate;
            return real.saveRows(...args);
          },
        }),
      },
    );
    await ready();
    const mark = () =>
      screen.getByTestId('entry-estimated') as HTMLButtonElement;
    expect(mark().disabled).toBe(false);
    type('r1', '2025-02', '4.5');
    saveAll();
    await waitFor(() => expect(mark().disabled).toBe(true));
    await act(async () => {
      release();
      await gate;
    });
    await screen.findByTestId('toast');
    await waitFor(() => expect(mark().disabled).toBe(false));
  });
});

describe('S12-03 출처 칸 [수정] → S9 바로(Q7·Q8)', () => {
  const has = (element: Element, wanted: readonly string[]) => {
    for (const one of wanted)
      expect(element.className.split(/\s+/), one).toContain(one);
  };
  const classes = (element: Element) => element.className.split(/\s+/);
  const editOf = (row: string) =>
    screen.queryByTestId(
      `entry-factor-edit-${row}`,
    ) as HTMLButtonElement | null;

  it('고객사(pool 없음) → 단추 0 · 운영 관리자 저장된 행만 · 잠김 끔 · 그 행 고친 동안 끔(「저장한 뒤 바꿀 수 있어요」)', async () => {
    await open({}, { operator: false });
    await ready();
    expect(editOf('r1')).toBeNull();
    cleanup();
    await open({}, { operator: true, pool: true });
    await ready();
    const button = editOf('r1')!;
    expect(button.textContent).toBe(words.factorEdit.cell);
    expect(button.getAttribute('aria-label')).toBe(
      words.factorEdit.cellLabel('1호기'),
    );
    expect(button.disabled).toBe(false);
    type('r1', '2025-02', '9');
    expect(editOf('r1')!.disabled).toBe(true);
    expect(editOf('r1')!.getAttribute('title')).toBe(words.factorEdit.dirty);
    // 저장 안 된 새 행은 [수정] 0.
    fireEvent.click(plant().getByRole('button', { name: words.add }));
    const add = await screen.findByTestId('entry-add');
    fireEvent.click(within(add).getAllByRole('checkbox')[0]!);
    fireEvent.click(within(add).getByRole('button', { name: words.addOk }));
    const fresh = await waitFor(() => {
      const found = document.querySelector('[data-testid^="entry-row-n"]');
      expect(found).not.toBeNull();
      return found!;
    });
    expect(
      fresh.querySelector('[data-testid^="entry-factor-edit-"]'),
    ).toBeNull();
    cleanup();
    await open({}, { operator: true, pool: true, locked: true });
    await ready();
    expect(editOf('r1')!.disabled).toBe(true);
  });

  it('누르면 S8 없이 S9 · 그 행의 계수(잎 기본과 다름)가 처음 고름 · [이전]으로 닫히면 초점 [수정]', async () => {
    const { server, port } = await open({}, { operator: true, pool: true });
    await ready();
    // 분모: r1 의 계수를 잎 기본(경유 21)이 아닌 등유(23)로 바꿔 둔 판으로 다시 연다.
    const moved = await port.setRowFactor(
      2025,
      '20',
      '1',
      { factorId: '23' },
      '지어낸 사유',
    );
    expect(moved.kind).toBe('ok');
    cleanup();
    render(
      <EntryDetailDialog
        port={port}
        year={2025}
        nodeId="20"
        operator
        pool={portsOf(server).pool}
        onClose={vi.fn()}
      />,
    );
    await ready();
    const button = editOf('r1')!;
    button.focus();
    fireEvent.click(button);
    const s9 = await screen.findByTestId('entry-factor-edit');
    await within(s9).findByTestId('entry-factor-pick');
    expect(screen.queryByTestId('entry-factor')).toBeNull();
    const checked = within(s9)
      .getAllByRole('checkbox')
      .filter((box) => box.getAttribute('aria-checked') === 'true');
    expect(checked).toHaveLength(1);
    expect(checked[0]!.getAttribute('aria-label')).toBe(
      words.factorEdit.pick('지어낸 등유 계수'),
    );
    fireEvent.click(
      within(s9).getByRole('button', { name: words.factorEdit.prev }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(editOf('r1')));
  });

  it('S9 꼴(값 파일 ③): 열 52·300·136×4 · 출처 가운데 · 머리 40 고정 · 표 몸 세로 스크롤 · [이전] outline-grey', async () => {
    await open({}, { operator: true, pool: true });
    await ready();
    fireEvent.click(editOf('r1')!);
    const s9 = await screen.findByTestId('entry-factor-edit');
    const table = await within(s9).findByTestId('entry-factor-pick');
    expect(
      [...table.querySelectorAll('col')].map((col) => col.className),
    ).toEqual([
      'w-[52px]',
      'w-[300px]',
      'w-[136px]',
      'w-[136px]',
      'w-[136px]',
      'w-[136px]',
    ]);
    const heads = table.querySelectorAll('th');
    has(heads[2] as HTMLElement, ['text-center', 'h-10', 'sticky', 'top-0']);
    // 디자인 대조 F5: 왼쪽은 배출계수명뿐 — 출처·산업·투입량 기준단위·Tier 머리·칸 가운데.
    expect(classes(heads[1] as HTMLElement)).not.toContain('text-center');
    for (const index of [2, 3, 4, 5])
      has(heads[index] as HTMLElement, ['text-center']);
    const firstRow = table.querySelector('tbody tr')!;
    const tds = firstRow.querySelectorAll('td');
    expect(classes(tds[1]!)).not.toContain('text-center');
    for (const index of [2, 3, 4, 5]) has(tds[index]!, ['text-center']);
    // F6: 고름 단계 사이 24 · 직접 입력 단계는 32.
    has(s9, ['gap-6']);
    expect(classes(s9)).not.toContain('gap-8');
    has(within(s9).getByTestId('entry-factor-pick-scroll'), [
      'overflow-y-auto',
    ]);
    has(within(s9).getByRole('button', { name: words.factorEdit.prev }), [
      'bg-button-white',
    ]);
  });

  it('빈 풀 → 표 자리 「등록된 배출계수가 없어요」 + 「직접 입력」 줄 · 읽기 실패 → 공용 load-failure + [다시 시도]', async () => {
    const { server } = await open({}, { operator: true, pool: true });
    await ready();
    server.override['GET /inventory/admin/ghg-index/facilities/20'] = () =>
      json(200, {
        id: '20',
        parentId: '5',
        facilityCodeId: '1',
        facilityCode: 'F0001',
        facilityName: '지어낸 보일러',
        unit: { kind: 'volume', unit: 'kL' },
        tooltip: '',
        factors: [],
      });
    fireEvent.click(editOf('r1')!);
    let s9 = await screen.findByTestId('entry-factor-edit');
    const empty = await within(s9).findByTestId('entry-factor-pick-empty');
    expect(empty.textContent).toBe(GHG_TEXT.pool.noFactors);
    // 디자인 대조 F7: 빈 줄 높이 96(판 .f12d-stmsg).
    has(empty.querySelector('td')!, ['h-24']);
    expect(
      within(s9).getByRole('checkbox', {
        name: words.factorEdit.pick(words.factorEdit.custom),
      }),
    ).toBeTruthy();
    fireEvent.click(
      within(s9).getByRole('button', { name: words.factorEdit.prev }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('entry-factor-edit')).toBeNull(),
    );
    server.override['GET /inventory/admin/ghg-index/facilities/20'] = () =>
      json(500, {});
    fireEvent.click(editOf('r1')!);
    s9 = await screen.findByTestId('entry-factor-edit');
    const failed = await within(s9).findByTestId('entry-factor-pick-failed');
    expect(within(failed).getByTestId('load-failure').textContent).toContain(
      words.factorEdit.loadFailed,
    );
    expect(
      within(failed).getByRole('button', { name: GHG_TEXT.common.retry }),
    ).toBeTruthy();
  });
});
