// @vitest-environment jsdom
// S18 선택항목 > 자산/시설명 및 코드(밴드 W12-0a ③ — 발주서 §3 8). 진짜 실어댑터 + 가짜 온실가스 서버.
//   목록(만든 차례·이름만 — 코드 글자 0·≡ 0) · 추가(빈 칸이면 [저장] 흐림 → POST {name}) · 수정(PATCH 경로 id 정수, code 그대로) ·
//   겹침(웹 검사 — 요청 0 · 서버 422 fields.name 같은 자리) · 삭제(고른 것 0 이면 꺼짐 → 확인 창 → {ids 정수}) · 409 IN_USE 한 줄(목록 그대로) ·
//   NOT_FOUND 한 줄 + 다시 읽음 · 빈 목록 + [항목 추가] · 읽기 실패 + [다시 시도] · 서버 message 0.
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
  fakeGhgServer,
  portsOf,
  refusal,
  unreachable,
} from '../../../entities/ghg/api/testing.ts';
import type { FakeGhgServerOptions } from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { FacilityCodesScreen } from './FacilityCodesScreen.tsx';

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

const words = GHG_TEXT.facilityCodes;
const LIST = 'GET /admin/facility-codes';

function setup(options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer(options);
  render(<FacilityCodesScreen port={portsOf(server).admin} />);
  return { server };
}

const names = () =>
  [...document.querySelectorAll('tr[data-code-id]')].map(
    (row) => row.querySelectorAll('td')[1]!.textContent,
  );
const ready = () => waitFor(() => expect(names().length).toBeGreaterThan(0));
const button = (name: string) => screen.getByRole('button', { name });
const notice = () => screen.getByTestId('options-notice');
const rowCheckbox = (name: string) =>
  screen.getByRole('checkbox', { name: words.selectRow(name) });

async function openAdd() {
  fireEvent.click(button(words.add));
  return screen.findByTestId('code-dialog');
}
const field = (dialog: HTMLElement) =>
  within(dialog).getByRole('textbox', { name: words.field });
const saveOf = (dialog: HTMLElement) =>
  within(dialog).getByRole('button', { name: words.save }) as HTMLButtonElement;

describe('S18 자산/시설명 및 코드', () => {
  it('제목·항목 고르기 하나 · 이름만(코드 글자 0) 만든 차례 · 쪽 크기 100', async () => {
    const { server } = setup();
    await ready();
    expect(screen.queryByRole('heading', { name: words.title })).toBeNull();
    const picker = screen.getByRole('combobox', { name: words.itemLabel });
    expect(
      within(picker)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual([words.item]);
    expect(names()).toEqual([
      '지어낸 보일러',
      '지어낸 발전기',
      '지어낸 사업장 차량',
    ]);
    expect(document.body.textContent).not.toMatch(/F000\d/);
    expect(Object.fromEntries(server.calls[0]!.query)).toEqual({
      page: '1',
      pageSize: '100',
    });
  });

  it('추가: 빈 칸이면 [저장] 흐림 · 이름 → POST {name} → 다시 읽어 보임', async () => {
    const { server } = setup();
    await ready();
    const dialog = await openAdd();
    expect(field(dialog).getAttribute('placeholder')).toBe(words.placeholder);
    // 서버 CodeName 상한 100 자(넘으면 422 fields.name 이 겹침 글로 보인다).
    expect(field(dialog).getAttribute('maxlength')).toBe('100');
    expect(saveOf(dialog).disabled).toBe(true);
    fireEvent.change(field(dialog), { target: { value: '   ' } });
    expect(saveOf(dialog).disabled).toBe(true);
    fireEvent.change(field(dialog), { target: { value: ' 지어낸 냉동기 ' } });
    expect(saveOf(dialog).disabled).toBe(false);
    fireEvent.click(saveOf(dialog));
    await waitFor(() =>
      expect(server.bodies('POST /admin/facility-codes')).toEqual([
        { name: '지어낸 냉동기' },
      ]),
    );
    await waitFor(() => expect(names()).toContain('지어낸 냉동기'));
    expect(screen.queryByTestId('code-dialog')).toBeNull();
    expect(server.count(LIST)).toBe(2);
  });

  it('겹침: 웹 검사 → 「이미 있는 항목이에요」 · 요청 0 · 서버 422 fields.name 도 같은 자리', async () => {
    const { server } = setup();
    await ready();
    const dialog = await openAdd();
    fireEvent.change(field(dialog), { target: { value: ' 지어낸 보일러' } });
    fireEvent.click(saveOf(dialog));
    expect(within(dialog).getByTestId('code-duplicate').textContent).toBe(
      words.duplicate,
    );
    expect(server.count('POST /admin/facility-codes')).toBe(0);
    server.override['POST /admin/facility-codes'] = () =>
      refusal(422, 'VALIDATION_ERROR', { name: ['x'] });
    fireEvent.change(field(dialog), { target: { value: '지어낸 새 것' } });
    fireEvent.click(saveOf(dialog));
    await waitFor(() =>
      expect(within(dialog).getByTestId('code-duplicate').textContent).toBe(
        words.duplicate,
      ),
    );
    expect(document.body.textContent).not.toContain('지어낸-');
  });

  it('수정: 이름만 바꿈 → PATCH /admin/facility-codes/2 {name} · 자기 이름 그대로는 겹침 아님', async () => {
    const { server } = setup();
    await ready();
    fireEvent.click(button(`지어낸 발전기 ${words.edit}`));
    const dialog = await screen.findByTestId('code-dialog');
    expect(within(dialog).getByText(words.editTitle)).not.toBeNull();
    expect((field(dialog) as HTMLInputElement).value).toBe('지어낸 발전기');
    fireEvent.change(field(dialog), { target: { value: '지어낸 비상발전기' } });
    fireEvent.click(saveOf(dialog));
    await waitFor(() =>
      expect(server.bodies('PATCH /admin/facility-codes/2')).toEqual([
        { name: '지어낸 비상발전기' },
      ]),
    );
    await waitFor(() => expect(names()[1]).toBe('지어낸 비상발전기'));
    expect(server.codes()[1]!.code).toBe('F0002');
  });

  it('수정 NOT_FOUND → 한 줄 + 다시 읽음', async () => {
    const { server } = setup();
    await ready();
    server.override['PATCH /admin/facility-codes/1'] = () =>
      refusal(404, 'NOT_FOUND');
    fireEvent.click(button(`지어낸 보일러 ${words.edit}`));
    const dialog = await screen.findByTestId('code-dialog');
    fireEvent.change(field(dialog), { target: { value: '지어낸 다른 것' } });
    fireEvent.click(saveOf(dialog));
    await waitFor(() => expect(notice().textContent).toBe(words.notFound));
    await waitFor(() => expect(server.count(LIST)).toBe(2));
  });

  it('삭제: 고른 것 0 이면 꺼짐 · 확인 창 → {ids:[1,3]} → 목록에서 빠짐', async () => {
    const { server } = setup();
    await ready();
    expect(button(words.deleteSelected).getAttribute('aria-disabled')).toBe(
      'true',
    );
    fireEvent.click(button(words.deleteSelected));
    expect(screen.queryByTestId('delete-dialog')).toBeNull();
    fireEvent.click(rowCheckbox('지어낸 보일러'));
    fireEvent.click(rowCheckbox('지어낸 사업장 차량'));
    fireEvent.click(button(words.deleteSelected));
    const dialog = await screen.findByTestId('delete-dialog');
    expect(within(dialog).getByText(words.deleteConfirm)).not.toBeNull();
    fireEvent.click(
      within(dialog).getByRole('button', { name: words.confirmDelete }),
    );
    await waitFor(() =>
      expect(server.bodies('POST /admin/facility-codes/delete')).toEqual([
        { ids: [1, 3] },
      ]),
    );
    await waitFor(() => expect(names()).toEqual(['지어낸 발전기']));
  });

  it('삭제 409 IN_USE → 「사용 중인 항목은 삭제할 수 없어요」 · 목록 그대로', async () => {
    const { server } = setup();
    await ready();
    server.override['POST /admin/facility-codes/delete'] = () =>
      refusal(409, 'IN_USE');
    fireEvent.click(rowCheckbox('지어낸 보일러'));
    fireEvent.click(button(words.deleteSelected));
    fireEvent.click(
      within(await screen.findByTestId('delete-dialog')).getByRole('button', {
        name: words.confirmDelete,
      }),
    );
    await waitFor(() => expect(notice().textContent).toBe(words.inUse));
    expect(names()).toHaveLength(3);
  });

  it('빈 목록 → 「등록된 항목이 없어요」 + [항목 추가]', async () => {
    setup({ codes: [] });
    expect(await screen.findByText(words.empty)).not.toBeNull();
    expect(screen.getAllByRole('button', { name: words.add })).toHaveLength(2);
  });

  it('읽기 실패 → 한 줄 + [다시 시도]', async () => {
    const { server } = setup();
    server.override[LIST] = [unreachable];
    expect(await screen.findByText(words.loadFailed)).not.toBeNull();
    fireEvent.click(button(GHG_TEXT.common.retry));
    await ready();
    expect(document.activeElement).toBe(button(words.add));
  });
});

// 밴드 RC1(sid:MARC-ENT-599): 줄 전체 = [수정](같은 창) · Tab+Enter·Space · 체크·[수정]은 줄 클릭 안 일으킴 · 닫으면 초점이 연 줄.
describe('S18 줄 클릭(밴드 RC1)', () => {
  const row = (name: string) =>
    [...document.querySelectorAll<HTMLElement>('tr[data-code-id]')].find(
      (tr) => tr.querySelectorAll('td')[1]!.textContent === name,
    )!;
  const dialogs = () => screen.queryAllByTestId('code-dialog');

  it('이름 칸을 누르면 [수정]과 같은 창(이름 칸에 그 이름) · 닫으면 초점이 그 줄', async () => {
    setup();
    await ready();
    const tr = row('지어낸 발전기');
    fireEvent.click(tr.querySelectorAll('td')[1]!);
    const dialog = await screen.findByTestId('code-dialog');
    expect(within(dialog).getByText(words.editTitle)).not.toBeNull();
    expect((field(dialog) as HTMLInputElement).value).toBe('지어낸 발전기');
    fireEvent.click(within(dialog).getByRole('button', { name: words.cancel }));
    await waitFor(() => expect(dialogs()).toHaveLength(0));
    await waitFor(() => expect(document.activeElement).toBe(tr));
  });

  it('줄에 초점 → Enter · Space 로 같은 창', async () => {
    setup();
    await ready();
    for (const key of ['Enter', ' ']) {
      const tr = row('지어낸 보일러');
      tr.focus();
      fireEvent.keyDown(tr, { key });
      const dialog = await screen.findByTestId('code-dialog');
      expect((field(dialog) as HTMLInputElement).value).toBe('지어낸 보일러');
      fireEvent.click(
        within(dialog).getByRole('button', { name: words.cancel }),
      );
      await waitFor(() => expect(dialogs()).toHaveLength(0));
    }
  });

  it('체크박스·[수정]은 줄 클릭을 일으키지 않음(수정 창은 하나)', async () => {
    setup();
    await ready();
    fireEvent.click(rowCheckbox('지어낸 발전기'));
    expect(dialogs()).toHaveLength(0);
    expect(rowCheckbox('지어낸 발전기').getAttribute('aria-checked')).toBe(
      'true',
    );
    fireEvent.click(button(`지어낸 발전기 ${words.edit}`));
    await screen.findByTestId('code-dialog');
    expect(dialogs()).toHaveLength(1);
  });

  it('체크박스에 초점 → Enter·Space 는 줄 열기 아님(창 0)', async () => {
    setup();
    await ready();
    const box = rowCheckbox('지어낸 발전기');
    box.focus();
    for (const key of ['Enter', ' ']) fireEvent.keyDown(box, { key });
    expect(dialogs()).toHaveLength(0);
  });

  it('누를 수 있는 줄의 꼴: tabindex 0 · 이름 = 코드 이름 · DataTable 클래스', async () => {
    setup();
    await ready();
    const tr = row('지어낸 보일러');
    expect(tr.getAttribute('tabindex')).toBe('0');
    expect(tr.getAttribute('aria-label')).toBe('지어낸 보일러');
    for (const name of [
      'cursor-pointer',
      'hover:bg-background-secondary',
      'focus-visible:outline-border-secondary',
    ])
      expect(tr.classList.contains(name), name).toBe(true);
  });

  it('빈 목록 줄은 누를 수 없음(tabindex·커서·hover 0)', async () => {
    setup({ codes: [] });
    const empty = await screen.findByText(words.empty);
    const tr = empty.closest('tr')!;
    expect(tr.getAttribute('tabindex')).toBeNull();
    expect(tr.className).not.toContain('cursor-pointer');
    expect(tr.className).not.toContain('hover:bg-');
  });
});

// 밴드 W12-0b1 ① N5(sid:MARC-ISSUE-426): 쪽 넘김 이름은 「페이지 넘김」(sid:MARC-ENT-459 「페이지」).
describe('S18 쪽 넘김 이름(W12-0b1 ① N5)', () => {
  it('101개 → 쪽 넘김 nav 이름 「페이지 넘김」', async () => {
    setup({
      codes: Array.from({ length: 101 }, (_, i) => ({
        id: String(i + 1),
        code: `F${String(i + 1).padStart(4, '0')}`,
        name: `지어낸 코드 ${i + 1}`,
      })),
    });
    await ready();
    expect(
      screen.getByRole('navigation', { name: '페이지 넘김' }),
    ).not.toBeNull();
    expect(words.pagerLabel).toBe('페이지 넘김');
  });
});
