// @vitest-environment jsdom
// S15 조직구조 목록(밴드 W12-0a ② — 발주서 §3 4). 진짜 실어댑터 + 가짜 온실가스 서버(entities/ghg/api/testing.ts).
//   검색(→ q, 쪽 1로) · 쪽 넘김 · 일괄 사용취소(본사 빠짐·ids 정수)·사용 · 고른 것 0 이면 단추 셋 꺼짐 · 본사 행(체크박스·토글 꺼짐) ·
//   삭제 확인 창 → POST /branches/delete · 거절 글(본사·사용 중·회사 셋·읽기 실패) · 행 토글 실패면 되돌림 · 행·> → onOpen · 추가 → onNew ·
//   서버 message 는 그리지 않는다.
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

import { createGhgOrganizationPort } from '../../../entities/ghg/api/index.ts';
import {
  fakeBranch,
  fakeGhgServer,
  fakeHeadquarters,
  refusal,
  unreachable,
} from '../../../entities/ghg/api/testing.ts';
import type { FakeGhgServerOptions } from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { createApi } from '../../../shared/api/index.ts';
import { OrganizationScreen, SEARCH_DELAY_MS } from './OrganizationScreen.tsx';

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

const words = GHG_TEXT.organization;
const BASE = 'http://test.local/api';
const LIST = 'GET /branches';

function setup(options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer({
    baseUrl: BASE,
    branches: [
      fakeHeadquarters(),
      fakeBranch(7, '제1공장'),
      fakeBranch(8, '제2공장', { inventoryEnabled: false }),
    ],
    ...options,
  });
  const port = createGhgOrganizationPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  const onOpen = vi.fn();
  const onNew = vi.fn();
  render(<OrganizationScreen port={port} onOpen={onOpen} onNew={onNew} />);
  return { server, onOpen, onNew };
}

const rowOf = (id: string) =>
  document.querySelector<HTMLElement>(`tr[data-branch-id="${id}"]`)!;
const rowsShown = () =>
  [...document.querySelectorAll('tr[data-branch-id]')].map((row) =>
    row.getAttribute('data-branch-id'),
  );
const ready = () =>
  waitFor(() => expect(rowsShown().length).toBeGreaterThan(0));
const checkboxOf = (id: string) =>
  within(rowOf(id)).getByRole('checkbox') as HTMLButtonElement;
const switchOf = (id: string) =>
  within(rowOf(id)).getByRole('switch') as HTMLButtonElement;
const button = (name: string) => screen.getByRole('button', { name });
const notice = () => screen.getByTestId('organization-notice');
const listQueries = (server: ReturnType<typeof setup>['server']) =>
  server.calls
    .filter((call) => `${call.method} ${call.path}` === LIST)
    .map((call) => Object.fromEntries(call.query));

describe('S15 목록', () => {
  it('제목 「조직구조」 · 본사 먼저 · 탭 줄 0 · 회사 머리 0 · 행 둘째 칸은 이름', async () => {
    setup();
    await ready();
    expect(screen.getByRole('heading', { name: words.title })).not.toBeNull();
    expect(rowsShown()).toEqual(['1', '7', '8']);
    expect(screen.queryByRole('tablist')).toBeNull();
    expect(rowOf('7').textContent).toContain('제1공장');
  });

  it('본사 행: 체크박스 꺼짐 · 토글은 켜진 채 꺼짐', async () => {
    setup();
    await ready();
    expect(checkboxOf('1').disabled).toBe(true);
    expect(switchOf('1').disabled).toBe(true);
    expect(switchOf('1').getAttribute('aria-checked')).toBe('true');
    expect(checkboxOf('7').disabled).toBe(false);
    expect(switchOf('8').getAttribute('aria-checked')).toBe('false');
  });

  it('고른 것이 0 이면 단추 셋 꺼짐(aria-disabled) · 눌러도 요청 0', async () => {
    const { server } = setup();
    await ready();
    for (const name of [
      words.disableSelected,
      words.enableSelected,
      words.deleteSelected,
    ]) {
      expect(button(name).getAttribute('aria-disabled'), name).toBe('true');
      fireEvent.click(button(name));
    }
    expect(server.calls.map((c) => c.method)).toEqual(['GET']);
    fireEvent.click(checkboxOf('7'));
    expect(button(words.deleteSelected).hasAttribute('aria-disabled')).toBe(
      false,
    );
  });

  it('전체 선택 → 본사 빼고 고름 → 「인벤토리 사용취소」 본문 {ids:[7,8], enabled:false} → 다시 읽음', async () => {
    const { server } = setup();
    await ready();
    fireEvent.click(screen.getByRole('checkbox', { name: words.selectAll }));
    expect(checkboxOf('1').getAttribute('aria-checked')).toBe('false');
    fireEvent.click(button(words.disableSelected));
    await waitFor(() =>
      expect(server.bodies('POST /branches/inventory')).toEqual([
        { ids: [7, 8], enabled: false },
      ]),
    );
    await waitFor(() => expect(server.count(LIST)).toBe(2));
    await waitFor(() =>
      expect(switchOf('7').getAttribute('aria-checked')).toBe('false'),
    );
    expect(checkboxOf('7').getAttribute('aria-checked')).toBe('false');
  });

  it('「인벤토리 사용」 본문 {ids, enabled:true}', async () => {
    const { server } = setup();
    await ready();
    fireEvent.click(checkboxOf('8'));
    fireEvent.click(button(words.enableSelected));
    await waitFor(() =>
      expect(server.bodies('POST /branches/inventory')).toEqual([
        { ids: [8], enabled: true },
      ]),
    );
  });

  it('검색: 멈춘 뒤 q 로 · 쪽은 1로 · 결과 없음 글', async () => {
    const { server } = setup({
      branches: [
        fakeHeadquarters(),
        ...Array.from({ length: 21 }, (_, i) => fakeBranch(10 + i, `공장${i}`)),
      ],
    });
    await ready();
    fireEvent.click(button(words.next));
    await waitFor(() => expect(listQueries(server).at(-1)!.page).toBe('2'));
    fireEvent.change(screen.getByRole('textbox', { name: words.searchLabel }), {
      target: { value: '없는이름' },
    });
    await waitFor(
      () =>
        expect(listQueries(server).at(-1)).toEqual({
          q: '없는이름',
          page: '1',
          pageSize: '20',
        }),
      { timeout: SEARCH_DELAY_MS + 1000 },
    );
    await waitFor(() =>
      expect(screen.getByText(words.emptySearch)).not.toBeNull(),
    );
  });

  it('GX2 M-8 사업장 0(검색 아님) → 「등록된 사업장이 없어요」 + 「[사업장 추가]로…」 · 「검색 결과가 없어요」 0', async () => {
    setup({ branches: [] });
    await waitFor(() => expect(screen.getByText(words.empty)).not.toBeNull());
    expect(screen.getByText(words.emptyGuide)).not.toBeNull();
    expect(screen.queryByText(words.emptySearch)).toBeNull();
  });

  it('GX2 S12-04 체크 상자 20(머리·줄 모두 h-5 w-5)', async () => {
    setup();
    await ready();
    const boxes = screen.getAllByRole('checkbox');
    expect(boxes.length).toBeGreaterThan(1);
    for (const box of boxes) {
      expect(box.className).toContain('h-5');
      expect(box.className).toContain('w-5');
    }
  });

  it('쪽 넘김: 다음·이전 → page 쿼리, 「2 / 2」', async () => {
    const { server } = setup({
      branches: [
        fakeHeadquarters(),
        ...Array.from({ length: 21 }, (_, i) => fakeBranch(10 + i, `공장${i}`)),
      ],
    });
    await ready();
    expect(screen.getByTestId('page-of').textContent).toBe(words.pageOf(1, 2));
    fireEvent.click(button(words.next));
    await waitFor(() =>
      expect(screen.getByTestId('page-of').textContent).toBe(
        words.pageOf(2, 2),
      ),
    );
    expect(listQueries(server).at(-1)).toEqual({ page: '2', pageSize: '20' });
    await waitFor(() => expect(rowsShown()).toEqual(['29', '30']));
    fireEvent.click(button(words.prev));
    await waitFor(() => expect(listQueries(server).at(-1)!.page).toBe('1'));
  });

  it('검색한 채 쪽을 넘기면 q 를 그대로 싣는다', async () => {
    const { server } = setup({
      branches: [
        fakeHeadquarters(),
        ...Array.from({ length: 25 }, (_, i) => fakeBranch(10 + i, `공장${i}`)),
      ],
    });
    await ready();
    fireEvent.change(screen.getByRole('textbox', { name: words.searchLabel }), {
      target: { value: '공장' },
    });
    await waitFor(() => expect(listQueries(server).at(-1)!.q).toBe('공장'), {
      timeout: SEARCH_DELAY_MS + 1000,
    });
    await waitFor(() =>
      expect(screen.getByTestId('page-of').textContent).toBe(
        words.pageOf(1, 2),
      ),
    );
    fireEvent.click(button(words.next));
    await waitFor(() =>
      expect(listQueries(server).at(-1)).toEqual({
        q: '공장',
        page: '2',
        pageSize: '20',
      }),
    );
  });

  it('삭제: 확인 창 「선택한 사업장을 삭제할까요?」 → [삭제] → {ids:[7]} → 목록에서 빠짐 · [취소]는 요청 0', async () => {
    const { server } = setup();
    await ready();
    fireEvent.click(checkboxOf('7'));
    fireEvent.click(button(words.deleteSelected));
    const dialog = await screen.findByTestId('delete-dialog');
    expect(within(dialog).getByText(words.deleteConfirm)).not.toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: words.cancel }));
    await waitFor(() =>
      expect(screen.queryByTestId('delete-dialog')).toBeNull(),
    );
    expect(server.count('POST /branches/delete')).toBe(0);
    fireEvent.click(button(words.deleteSelected));
    fireEvent.click(
      within(await screen.findByTestId('delete-dialog')).getByRole('button', {
        name: words.confirmDelete,
      }),
    );
    await waitFor(() =>
      expect(server.bodies('POST /branches/delete')).toEqual([{ ids: [7] }]),
    );
    await waitFor(() => expect(rowsShown()).toEqual(['1', '8']));
  });

  it('거절 글: 본사 409 · 사용 중 409 · 그 밖 실패 — 서버 message 0', async () => {
    const { server } = setup();
    await ready();
    server.override['POST /branches/delete'] = [
      () => refusal(409, 'HEADQUARTERS_LOCKED'),
      () => refusal(409, 'IN_USE'),
      unreachable,
    ];
    const tries: string[] = [
      words.headquartersLocked,
      words.inUse,
      words.writeFailed,
    ];
    for (const text of tries) {
      fireEvent.click(checkboxOf('7'));
      if (checkboxOf('7').getAttribute('aria-checked') !== 'true')
        fireEvent.click(checkboxOf('7'));
      fireEvent.click(button(words.deleteSelected));
      fireEvent.click(
        within(await screen.findByTestId('delete-dialog')).getByRole('button', {
          name: words.confirmDelete,
        }),
      );
      await waitFor(() => expect(notice().textContent).toBe(text));
      expect(document.body.textContent).not.toContain('지어낸-');
    }
  });

  it('행 토글: 바로 {ids:[id], enabled:반대} · 보내는 동안 꺼짐 · 실패면 되돌리고 한 줄', async () => {
    const { server } = setup();
    await ready();
    let answer: (response: Response) => void = () => {};
    server.override['POST /branches/inventory'] = () =>
      new Promise<Response>((resolve) => {
        answer = resolve;
      });
    fireEvent.click(switchOf('7'));
    await waitFor(() => expect(switchOf('7').disabled).toBe(true));
    expect(switchOf('7').getAttribute('aria-checked')).toBe('false');
    expect(server.bodies('POST /branches/inventory')).toEqual([
      { ids: [7], enabled: false },
    ]);
    await act(async () => answer(refusal(500, 'SERVER_ERROR')));
    await waitFor(() => expect(notice().textContent).toBe(words.writeFailed));
    await waitFor(() =>
      expect(switchOf('7').getAttribute('aria-checked')).toBe('true'),
    );
    expect(switchOf('7').disabled).toBe(false);
  });

  it('행(고르기·토글 밖)·> → onOpen(id) · 체크박스는 열지 않음 · 「사업장 추가」 → onNew', async () => {
    const { onOpen, onNew } = setup();
    await ready();
    fireEvent.click(within(rowOf('7')).getByText('제1공장'));
    expect(onOpen).toHaveBeenLastCalledWith('7');
    fireEvent.click(button(words.openRow('제2공장')));
    expect(onOpen).toHaveBeenLastCalledWith('8');
    fireEvent.click(checkboxOf('7'));
    expect(onOpen).toHaveBeenCalledTimes(2);
    fireEvent.click(button(words.add));
    expect(onNew).toHaveBeenCalledTimes(1);
  });

  describe('줄 클릭(밴드 RC1, sid:MARC-ENT-599)', () => {
    it('줄에 초점 → Enter · Space → onOpen(id) · 줄 안 컨트롤의 Enter 는 줄 열기 아님', async () => {
      const { onOpen } = setup();
      await ready();
      const row = rowOf('7');
      row.focus();
      fireEvent.keyDown(row, { key: 'Enter' });
      expect(onOpen).toHaveBeenLastCalledWith('7');
      fireEvent.keyDown(row, { key: ' ' });
      expect(onOpen).toHaveBeenCalledTimes(2);
      checkboxOf('7').focus();
      fireEvent.keyDown(checkboxOf('7'), { key: 'Enter' });
      expect(onOpen).toHaveBeenCalledTimes(2);
    });

    it('체크박스·스위치는 열지 않음 · › 는 onOpen 한 번(두 번 아님) · 본사 줄 비활성 체크·스위치도 열지 않음', async () => {
      const { onOpen, server } = setup();
      server.override['POST /branches/inventory'] = () =>
        new Promise<Response>(() => {});
      await ready();
      fireEvent.click(checkboxOf('7'));
      fireEvent.click(switchOf('7'));
      expect(onOpen).not.toHaveBeenCalled();
      fireEvent.click(button(words.openRow('제1공장')));
      expect(onOpen).toHaveBeenCalledTimes(1);
      expect(checkboxOf('1').disabled).toBe(true);
      expect(switchOf('1').disabled).toBe(true);
      fireEvent.click(checkboxOf('1'));
      fireEvent.click(switchOf('1'));
      expect(onOpen).toHaveBeenCalledTimes(1);
      // 본사 줄도 열 것이 있다(이름 칸).
      fireEvent.click(within(rowOf('1')).getByText('본사'));
      expect(onOpen).toHaveBeenLastCalledWith('1');
    });

    it('누를 수 있는 줄의 꼴: tabindex 0 · 이름 = 사업장명 · DataTable 클래스', async () => {
      setup();
      await ready();
      const row = rowOf('7');
      expect(row.getAttribute('tabindex')).toBe('0');
      expect(row.getAttribute('aria-label')).toBe('제1공장');
      for (const name of [
        'cursor-pointer',
        'hover:bg-background-secondary',
        'focus-visible:outline-border-secondary',
      ])
        expect(row.classList.contains(name), name).toBe(true);
    });

    it('빈 목록 줄은 누를 수 없음(tabindex·커서·hover 0)', async () => {
      setup({ branches: [] });
      const empty = await screen.findByText(words.empty);
      const tr = empty.closest('tr')!;
      expect(tr.getAttribute('tabindex')).toBeNull();
      expect(tr.className).not.toContain('cursor-pointer');
      expect(tr.className).not.toContain('hover:bg-');
    });
  });

  it.each([
    ['COMPANY_AMBIGUOUS', 'ambiguous'],
    ['COMPANY_INACTIVE', 'inactive'],
    ['COMPANY_NOT_FOUND', 'not_found'],
  ] as const)(
    '회사 거절 %s → 글 한 줄 · 다시 시도 없음',
    async (code, kind) => {
      setup({ company: code });
      const line = await screen.findByTestId('company-refusal');
      expect(line.textContent).toBe(GHG_TEXT.company[kind]);
      expect(
        screen.queryByRole('button', { name: GHG_TEXT.common.retry }),
      ).toBeNull();
      expect(screen.queryByRole('table')).toBeNull();
    },
  );

  it('읽기 실패 → 글 + [다시 시도] → 다시 읽음', async () => {
    const { server } = setup();
    server.override[LIST] = [unreachable];
    expect(await screen.findByText(words.loadFailed)).not.toBeNull();
    fireEvent.click(button(GHG_TEXT.common.retry));
    await ready();
    expect(server.count(LIST)).toBe(2);
  });
});

// 밴드 W12-0b1 ①(sid:MARC-ISSUE-426): L2 토글 기다림 · L4 쓰기의 회사 거절 · 운영 관리자 회사 글 · N4·N5·sr-only 머리.
describe('S15 목록 — 426 고침(W12-0b1 ①)', () => {
  function mount(options: FakeGhgServerOptions = {}, operator = false) {
    const server = fakeGhgServer({
      baseUrl: BASE,
      branches: [
        fakeHeadquarters(),
        fakeBranch(7, '제1공장'),
        fakeBranch(8, '제2공장', { inventoryEnabled: false }),
      ],
      ...options,
    });
    const port = createGhgOrganizationPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    render(
      <OrganizationScreen
        port={port}
        onOpen={vi.fn()}
        onNew={vi.fn()}
        operator={operator}
      />,
    );
    return { server };
  }

  it('L2: 토글 둘을 잇달아 → 첫 응답 뒤 다시 읽어도 둘째 행의 기다림 표시(꺼짐·바뀐 값)는 남는다', async () => {
    const { server } = mount();
    await ready();
    const answers: ((response: Response) => void)[] = [];
    server.override['POST /branches/inventory'] = () =>
      new Promise<Response>((resolve) => {
        answers.push(resolve);
      });
    fireEvent.click(switchOf('7'));
    fireEvent.click(switchOf('8'));
    await waitFor(() => expect(answers).toHaveLength(2));
    const reads = server.count(LIST);
    await act(async () => answers[0]!(new Response('{"count":1}')));
    await waitFor(() => expect(server.count(LIST)).toBe(reads + 1));
    await waitFor(() => expect(switchOf('7').disabled).toBe(false));
    expect(switchOf('8').disabled).toBe(true);
    expect(switchOf('8').getAttribute('aria-checked')).toBe('true');
    await act(async () => answers[1]!(new Response('{"count":1}')));
    await waitFor(() => expect(switchOf('8').disabled).toBe(false));
  });

  it.each([
    ['COMPANY_AMBIGUOUS', 'ambiguous'],
    ['COMPANY_INACTIVE', 'inactive'],
    ['COMPANY_NOT_FOUND', 'not_found'],
  ] as const)(
    'L4: 쓰기의 회사 거절 %s → 회사 글(writeFailed 아님) · 운영 관리자면 companyOperator',
    async (code, kind) => {
      for (const operator of [false, true]) {
        const { server } = mount({}, operator);
        await ready();
        server.override['POST /branches/inventory'] = () => refusal(400, code);
        fireEvent.click(switchOf('7'));
        const text = (operator ? GHG_TEXT.companyOperator : GHG_TEXT.company)[
          kind
        ];
        await waitFor(() => expect(notice().textContent).toBe(text));
        expect(notice().textContent).not.toBe(words.writeFailed);
        cleanup();
      }
    },
  );

  it.each([
    ['COMPANY_AMBIGUOUS', 'ambiguous'],
    ['COMPANY_INACTIVE', 'inactive'],
    ['COMPANY_NOT_FOUND', 'not_found'],
  ] as const)(
    '운영 관리자: 읽기 회사 거절 %s → 「운영 관리자에게 문의」가 없는 글',
    async (code, kind) => {
      mount({ company: code }, true);
      const line = await screen.findByTestId('company-refusal');
      expect(line.textContent).toBe(GHG_TEXT.companyOperator[kind]);
      expect(line.textContent).not.toContain('운영 관리자');
    },
  );

  it('N4 검색 자리채움 「사업장명 검색」 · N5 쪽 넘김 이름 「페이지 넘김」 · > 열 sr-only 머리 「상세 보기」', async () => {
    mount({
      branches: [
        fakeHeadquarters(),
        ...Array.from({ length: 25 }, (_, i) => fakeBranch(10 + i, `지점${i}`)),
      ],
    });
    await ready();
    expect(
      (
        screen.getByRole('textbox', {
          name: words.searchLabel,
        }) as HTMLInputElement
      ).placeholder,
    ).toBe('사업장명 검색');
    expect(
      screen.getByRole('navigation', { name: '페이지 넘김' }),
    ).not.toBeNull();
    expect(
      screen.getByRole('columnheader', { name: '상세 보기' }),
    ).not.toBeNull();
  });
});
