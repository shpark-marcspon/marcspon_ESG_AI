// @vitest-environment jsdom
// S15 사업장 상세(밴드 W12-0a ② — 발주서 §3 5). 진짜 실어댑터 + 가짜 온실가스 서버.
//   새로: 이름 빔 → 「필수 입력 항목이에요」 + 이름 칸 초점(요청 0) · 모달 둘(요청 0 — 화면 목록에만) → POST 본문 → onCreated(id) ·
//   있는: 줄 삭제·추가 → PUT 본문(남은 줄 id 정수) → 「저장했어요」 · 겹침 한 줄 · 서버 422 fields.name → 이름 칸 · 본사 토글 꺼짐 ·
//   [취소] 바뀐 것 없음 → onBack, 있음 → 확인 창 · 모달: 빈 코드 목록 안내 · 빔 · 겹침 · NOT_FOUND(읽기·PUT) → 찾지 못함 · 서버 message 0.
//   밴드 K1b-3: PUT 본문 updatedAt = 받은 판 글자(200 뒤 이어받음) · 409 STALE → 폼 그대로 + stale 줄 + [다시 불러오기](고친 것 있으면 확인 창).
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
} from '../../../entities/ghg/api/testing.ts';
import type { FakeGhgServerOptions } from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { createApi } from '../../../shared/api/index.ts';
import { BranchScreen } from './BranchScreen.tsx';

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

const words = GHG_TEXT.branch;
const modal = GHG_TEXT.facilityModal;
const BASE = 'http://test.local/api';

function setup(branchId: string | null, options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer({
    baseUrl: BASE,
    branches: [fakeHeadquarters(), fakeBranch(7, '제1공장')],
    ...options,
  });
  const port = createGhgOrganizationPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  const onBack = vi.fn();
  const onCreated = vi.fn();
  render(
    <BranchScreen
      port={port}
      branchId={branchId}
      onBack={onBack}
      onCreated={onCreated}
    />,
  );
  return { server, onBack, onCreated };
}

const nameBox = () =>
  screen.getByRole('textbox', { name: words.name }) as HTMLInputElement;
const button = (name: string) => screen.getByRole('button', { name });
const writes = (server: ReturnType<typeof setup>['server']) =>
  server.calls.filter((call) => call.method !== 'GET');
const lineKeys = () =>
  [...document.querySelectorAll('tr[data-line-key]')].map((row) =>
    row.getAttribute('data-line-key'),
  );

/** 모달을 열어 코드(이름)와 세부시설명으로 [저장]. */
async function addLine(code: string, detail: string) {
  fireEvent.click(button(words.addLine));
  const dialog = await screen.findByTestId('facility-dialog');
  const select = await within(dialog).findByRole('combobox', {
    name: modal.code,
  });
  const option = within(select).getByRole('option', {
    name: code,
  }) as HTMLOptionElement;
  fireEvent.change(select, { target: { value: option.value } });
  fireEvent.change(
    within(dialog).getByRole('textbox', { name: modal.detail }),
    {
      target: { value: detail },
    },
  );
  fireEvent.click(within(dialog).getByRole('button', { name: modal.save }));
  return dialog;
}

describe('새 사업장', () => {
  it('이름 빔 → 필수 글 + 이름 칸 초점 · 요청 0', async () => {
    const { server } = setup(null);
    fireEvent.click(button(words.save));
    expect(screen.getByTestId('name-error').textContent).toBe(words.required);
    await waitFor(() => expect(document.activeElement).toBe(nameBox()));
    expect(nameBox().getAttribute('aria-invalid')).toBe('true');
    expect(server.calls).toEqual([]);
  });

  it('모달 둘은 화면 목록에만(요청은 GET /facility-codes 뿐) → [저장] POST 본문 → onCreated(새 id)', async () => {
    const { server, onCreated } = setup(null);
    fireEvent.change(nameBox(), { target: { value: ' 제3공장 ' } });
    await addLine('지어낸 보일러', '1호기');
    await waitFor(() =>
      expect(screen.queryByTestId('facility-dialog')).toBeNull(),
    );
    await addLine('지어낸 발전기', ' 비상용 ');
    await waitFor(() => expect(lineKeys()).toHaveLength(2));
    expect(writes(server)).toEqual([]);
    fireEvent.click(button(words.save));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith('8'));
    expect(server.bodies('POST /branches')).toEqual([
      {
        name: '제3공장',
        inventoryEnabled: true,
        facilities: [
          { facilityCodeId: 1, detailName: '1호기' },
          { facilityCodeId: 2, detailName: '비상용' },
        ],
      },
    ]);
  });

  it('겹침(같은 코드·세부시설명) — 모달이 막는다 · 저장 단추 Policy 는 늘 켬', async () => {
    setup(null);
    await addLine('지어낸 보일러', '1호기');
    await waitFor(() => expect(lineKeys()).toHaveLength(1));
    const dialog = await addLine('지어낸 보일러', ' 1호기 ');
    expect(within(dialog).getByTestId('facility-duplicate').textContent).toBe(
      words.duplicateFacility,
    );
    expect(lineKeys()).toHaveLength(1);
    expect(button(words.save).hasAttribute('disabled')).toBe(false);
  });

  it('GX2 L-8 시설명 드롭다운은 가나다(서버 차례와 달라도)', async () => {
    setup(null, {
      codes: [
        { id: '1', code: 'F1', name: '지어낸 용제' },
        { id: '2', code: 'F2', name: '지어낸 경유' },
        { id: '3', code: 'F3', name: 'B-지어낸 유' },
      ],
    });
    fireEvent.click(button(words.addLine));
    const dialog = await screen.findByTestId('facility-dialog');
    await waitFor(() =>
      expect(dialog.querySelectorAll('option[value="1"]')).toHaveLength(1),
    );
    const names = [...dialog.querySelectorAll('option')]
      .filter((o) => o.value !== '')
      .map((o) => o.textContent);
    // 가짜 서버는 글자 값 차례(서버 DB 정렬 흉내 — 영문이 앞). 웹은 가나다(한글 먼저).
    expect(names).toEqual(['지어낸 경유', '지어낸 용제', 'B-지어낸 유']);
  });

  it('모달: 빈 칸 → 필수 글 · 코드 목록이 비면 안내 글', async () => {
    setup(null, { codes: [] });
    fireEvent.click(button(words.addLine));
    const dialog = await screen.findByTestId('facility-dialog');
    expect((await within(dialog).findByTestId('no-codes')).textContent).toBe(
      modal.noCodes,
    );
    fireEvent.click(within(dialog).getByRole('button', { name: modal.save }));
    expect(within(dialog).getByText(words.required)).not.toBeNull();
  });

  it('서버 422 fields.name(겹치는 이름) → 이름 칸 글 · 서버 message 0', async () => {
    setup(null);
    fireEvent.change(nameBox(), { target: { value: '제1공장' } });
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(screen.getByTestId('name-error').textContent).toBe(
        words.nameTaken,
      ),
    );
    expect(document.body.textContent).not.toContain('지어낸 이름 겹침');
  });

  it('[취소]: 바꾼 것 없음 → 바로 onBack · 있음 → 확인 창 → [나가기]', async () => {
    const { onBack } = setup(null);
    fireEvent.click(button(words.cancel));
    expect(onBack).toHaveBeenCalledTimes(1);
    fireEvent.change(nameBox(), { target: { value: '제9공장' } });
    fireEvent.click(button(words.cancel));
    const dialog = await screen.findByTestId('leave-dialog');
    expect(within(dialog).getByText(words.leaveConfirm)).not.toBeNull();
    expect(onBack).toHaveBeenCalledTimes(1);
    fireEvent.click(within(dialog).getByRole('button', { name: words.leave }));
    expect(onBack).toHaveBeenCalledTimes(2);
  });
});

describe('있는 사업장', () => {
  it('본사: 이름·줄 그대로 · 토글은 켜진 채 꺼짐', async () => {
    setup('1');
    await waitFor(() => expect(nameBox().value).toBe('본사'));
    const toggle = screen.getByRole('switch', { name: words.inventory });
    // GX2 L-11: 이름은 aria-label 로 직접.
    expect(toggle.getAttribute('aria-label')).toBe(words.inventory);
    // GX2 S12-04a: 체크 20(h-5 w-5) · 줄 56(h-14).
    const boxes = screen.getAllByRole('checkbox');
    expect(boxes.length).toBeGreaterThan(1);
    for (const box of boxes) {
      expect(box.className).toContain('h-5');
      expect(box.className).toContain('w-5');
    }
    expect(boxes.at(-1)!.closest('td')!.className).toContain('h-14');
    expect(toggle.getAttribute('aria-checked')).toBe('true');
    expect((toggle as HTMLButtonElement).disabled).toBe(true);
    expect(lineKeys()).toEqual(['saved-1']);
  });

  it('줄 삭제 + 추가 → PUT 본문(남은 줄 id 정수 · 새 줄 id 없음) → 다시 그림 + 「저장했어요」', async () => {
    const { server } = setup('1');
    await waitFor(() => expect(lineKeys()).toEqual(['saved-1']));
    await addLine('지어낸 발전기', '2호기');
    await waitFor(() => expect(lineKeys()).toHaveLength(2));
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(screen.getByTestId('branch-saved').textContent).toBe(words.saved),
    );
    expect(server.bodies('PUT /branches/1')).toEqual([
      {
        name: '본사',
        inventoryEnabled: true,
        facilities: [
          { id: 1, facilityCodeId: 1, detailName: '1호기' },
          { facilityCodeId: 2, detailName: '2호기' },
        ],
        updatedAt: '2026-10-28T09:00:00.000001+09:00',
      },
    ]);
    expect(lineKeys()).toEqual(['saved-1', 'saved-2']);
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: words.selectLine('지어낸 보일러 1호기'),
      }),
    );
    fireEvent.click(button(words.removeLines));
    expect(lineKeys()).toEqual(['saved-2']);
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(server.bodies('PUT /branches/1')).toHaveLength(2),
    );
    // 둘째 저장은 첫 200 의 판을 이어받는다(낡은 판으로 409 가 나지 않는다).
    expect(server.bodies('PUT /branches/1')[1]).toEqual({
      name: '본사',
      inventoryEnabled: true,
      facilities: [{ id: 2, facilityCodeId: 2, detailName: '2호기' }],
      updatedAt: '2026-10-29T09:00:00.000001+09:00',
    });
    await waitFor(() =>
      expect(screen.getByTestId('branch-saved').textContent).toBe(words.saved),
    );
    expect(screen.getByTestId('branch-line').textContent).toBe('');
  });

  it('사업장 토글 끔 → PUT inventoryEnabled false', async () => {
    const { server } = setup('7');
    await waitFor(() => expect(nameBox().value).toBe('제1공장'));
    fireEvent.click(screen.getByRole('switch', { name: words.inventory }));
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(server.bodies('PUT /branches/7')).toEqual([
        {
          name: '제1공장',
          inventoryEnabled: false,
          facilities: [],
          updatedAt: '2026-10-28T10:07:00.000001+09:00',
        },
      ]),
    );
  });

  it('PUT 422 fields.facilities(겹침) → 겹침 글 · 폼 그대로', async () => {
    const { server } = setup('1');
    await waitFor(() => expect(nameBox().value).toBe('본사'));
    server.override['PUT /branches/1'] = () =>
      refusal(422, 'VALIDATION_ERROR', { facilities: ['x'] });
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(screen.getByTestId('branch-line').textContent).toBe(
        words.duplicateFacility,
      ),
    );
    expect(nameBox().value).toBe('본사');
    expect(lineKeys()).toEqual(['saved-1']);
  });

  it('POST 422 fields.facilityCodeId(지운 코드) → 코드 글 · 폼 그대로', async () => {
    const { server, onCreated } = setup(null);
    fireEvent.change(nameBox(), { target: { value: '제3공장' } });
    await addLine('지어낸 보일러', '1호기');
    await waitFor(() => expect(lineKeys()).toHaveLength(1));
    server.override['POST /branches'] = () =>
      refusal(422, 'VALIDATION_ERROR', { facilityCodeId: ['x'] });
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(screen.getByTestId('branch-line').textContent).toBe(
        words.codeGone,
      ),
    );
    expect(nameBox().value).toBe('제3공장');
    expect(lineKeys()).toHaveLength(1);
    expect(onCreated).not.toHaveBeenCalled();
  });

  it('PUT 409 IN_USE · HEADQUARTERS_LOCKED → 한 줄 · 404 → 다시 읽어도 없으면 찾지 못함(M1 사업장도 없음 갈래)', async () => {
    const { server } = setup('7');
    await waitFor(() => expect(nameBox().value).toBe('제1공장'));
    server.override['PUT /branches/7'] = [
      () => refusal(409, 'IN_USE'),
      () => refusal(409, 'HEADQUARTERS_LOCKED'),
      () => refusal(404, 'NOT_FOUND'),
    ];
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(screen.getByTestId('branch-line').textContent).toBe(words.inUse),
    );
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(screen.getByTestId('branch-line').textContent).toBe(
        words.headquartersLocked,
      ),
    );
    // 다시 읽기(GET)도 404 — 다른 곳에서 지운 사업장.
    server.override['GET /branches/7'] = () => refusal(404, 'NOT_FOUND');
    fireEvent.click(button(words.save));
    expect(await screen.findByText(words.notFound)).not.toBeNull();
    expect(document.body.textContent).not.toContain('지어낸-');
  });

  it('없는 id(404) → 찾지 못함 + [목록으로] → onBack', async () => {
    const { onBack } = setup('99');
    expect(await screen.findByText(words.notFound)).not.toBeNull();
    fireEvent.click(button(words.toList));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('회사 거절 → 글 한 줄', async () => {
    setup('7', { company: 'COMPANY_AMBIGUOUS' });
    expect((await screen.findByTestId('company-refusal')).textContent).toBe(
      GHG_TEXT.company.ambiguous,
    );
  });
});

// 밴드 W12-0b1 ①(sid:MARC-ISSUE-426): M1 PUT 404 다시 읽어 가름 · L1 저장 중 잠금 · 운영 관리자 회사 글 · N2·N3·N6.
describe('있는 사업장 — 426 고침(W12-0b1 ①)', () => {
  function mount(
    branchId: string | null,
    options: FakeGhgServerOptions = {},
    operator = false,
  ) {
    const server = fakeGhgServer({
      baseUrl: BASE,
      branches: [fakeHeadquarters(), fakeBranch(7, '제1공장')],
      ...options,
    });
    const port = createGhgOrganizationPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    render(
      <BranchScreen
        port={port}
        branchId={branchId}
        onBack={vi.fn()}
        onCreated={vi.fn()}
        operator={operator}
      />,
    );
    return { server };
  }

  it('M1: PUT 404(낡은 줄 id) → 다시 읽어 사업장이 있으면 폼 그대로 + 「다른 곳에서 바뀌었어요」 한 줄', async () => {
    const { server } = mount('7');
    await waitFor(() => expect(nameBox().value).toBe('제1공장'));
    fireEvent.change(nameBox(), { target: { value: '제1공장 고침' } });
    server.override['PUT /branches/7'] = () => refusal(404, 'NOT_FOUND');
    const reads = server.count('GET /branches/7');
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(screen.getByTestId('branch-line').textContent).toBe(words.stale),
    );
    expect(server.count('GET /branches/7')).toBe(reads + 1);
    expect(nameBox().value).toBe('제1공장 고침');
    expect(screen.queryByText(words.notFound)).toBeNull();
    expect(document.body.textContent).not.toContain('지어낸-');
    // 밴드 K1b-3: 이 갈래에도 [다시 불러오기].
    expect(button(words.reload)).not.toBeNull();
  });

  it('L1: 저장 요청이 걸린 동안 폼이 잠긴다(입력·추가·삭제·취소·저장 꺼짐) — 응답 뒤 풀림', async () => {
    const { server } = mount('1');
    await waitFor(() => expect(nameBox().value).toBe('본사'));
    let answer: () => void = () => {};
    server.override['PUT /branches/1'] = () =>
      new Promise<Response>((resolve) => {
        answer = () =>
          resolve(
            new Response(JSON.stringify(fakeHeadquarters()), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
      });
    fireEvent.click(button(words.save));
    const form = screen.getByTestId('branch-form');
    const off = (node: Element) => node.matches(':disabled');
    await waitFor(() =>
      expect((form as HTMLFieldSetElement).disabled).toBe(true),
    );
    expect(off(nameBox())).toBe(true);
    expect(off(button(words.addLine))).toBe(true);
    expect(off(button(words.removeLines))).toBe(true);
    expect(off(button(words.cancel))).toBe(true);
    expect(off(screen.getByText(words.save).closest('button')!)).toBe(true);
    expect(off(screen.getByRole('checkbox', { name: words.selectAll }))).toBe(
      true,
    );
    await act(async () => answer());
    await waitFor(() =>
      expect((form as HTMLFieldSetElement).disabled).toBe(false),
    );
    expect(off(nameBox())).toBe(false);
    expect(screen.getByTestId('branch-saved').textContent).toBe(words.saved);
  });

  it('N2 제목 「사업장 정보」(새로는 「사업장 추가」) · N3 인벤토리 값 칸 items-center · N6 codeGone 끝 마침표 0', async () => {
    mount('7');
    expect(
      await screen.findByRole('heading', { name: '사업장 정보' }),
    ).not.toBeNull();
    const toggle = screen.getByRole('switch', { name: words.inventory });
    expect(toggle.parentElement!.className.split(' ')).toContain(
      'items-center',
    );
    expect(words.codeGone.endsWith('.')).toBe(false);
    cleanup();
    mount(null);
    expect(
      await screen.findByRole('heading', { name: words.titleNew }),
    ).not.toBeNull();
    expect(words.titleNew).toBe('사업장 추가');
  });

  it.each([
    ['COMPANY_AMBIGUOUS', 'ambiguous'],
    ['COMPANY_INACTIVE', 'inactive'],
    ['COMPANY_NOT_FOUND', 'not_found'],
  ] as const)(
    '회사 거절 %s: 고객사 사용자는 company 글 · 운영 관리자는 companyOperator 글',
    async (code, kind) => {
      mount('7', { company: code });
      expect((await screen.findByTestId('company-refusal')).textContent).toBe(
        GHG_TEXT.company[kind],
      );
      cleanup();
      mount('7', { company: code }, true);
      expect((await screen.findByTestId('company-refusal')).textContent).toBe(
        GHG_TEXT.companyOperator[kind],
      );
    },
  );

  it.each([false, true])(
    'PUT 회사 거절(400 COMPANY_INACTIVE) → 한 줄은 회사 글(운영 관리자 %s 이면 companyOperator)',
    async (operator) => {
      const { server } = mount('7', {}, operator);
      await waitFor(() => expect(nameBox().value).toBe('제1공장'));
      server.override['PUT /branches/7'] = () =>
        refusal(400, 'COMPANY_INACTIVE');
      fireEvent.click(button(words.save));
      await waitFor(() =>
        expect(screen.getByTestId('branch-line').textContent).toBe(
          (operator ? GHG_TEXT.companyOperator : GHG_TEXT.company).inactive,
        ),
      );
    },
  );

  it.each([false, true])(
    'M1: PUT 404 뒤 다시 읽기가 회사 거절 → 한 줄은 회사 글(saveFailed 아님, 운영 관리자 %s)',
    async (operator) => {
      const { server } = mount('7', {}, operator);
      await waitFor(() => expect(nameBox().value).toBe('제1공장'));
      server.override['PUT /branches/7'] = () => refusal(404, 'NOT_FOUND');
      server.override['GET /branches/7'] = () =>
        refusal(400, 'COMPANY_INACTIVE');
      fireEvent.click(button(words.save));
      await waitFor(() =>
        expect(screen.getByTestId('branch-line').textContent).toBe(
          (operator ? GHG_TEXT.companyOperator : GHG_TEXT.company).inactive,
        ),
      );
      expect(screen.getByTestId('branch-line').textContent).not.toBe(
        words.saveFailed,
      );
      expect(nameBox().value).toBe('제1공장');
    },
  );

  it('L1·M1: PUT 404 뒤 다시 읽는 동안에도 폼은 잠긴 채 — 다시 읽기 답 뒤 풀림', async () => {
    const { server } = mount('7');
    await waitFor(() => expect(nameBox().value).toBe('제1공장'));
    server.override['PUT /branches/7'] = () => refusal(404, 'NOT_FOUND');
    let answer: () => void = () => {};
    server.override['GET /branches/7'] = () =>
      new Promise<Response>((resolve) => {
        answer = () =>
          resolve(
            new Response(JSON.stringify(fakeBranch(7, '제1공장')), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
      });
    fireEvent.click(button(words.save));
    const form = screen.getByTestId('branch-form') as HTMLFieldSetElement;
    await waitFor(() =>
      expect(server.count('GET /branches/7')).toBeGreaterThanOrEqual(2),
    );
    expect(form.disabled).toBe(true);
    await act(async () => answer());
    await waitFor(() =>
      expect(screen.getByTestId('branch-line').textContent).toBe(words.stale),
    );
    expect(form.disabled).toBe(false);
  });
});

// 밴드 K1b-3(sid:MARC-ISSUE-427): 낡은 판 409 STALE — 폼 그대로 + 한 줄 + [다시 불러오기].
describe('있는 사업장 — 낡은 판(K1b-3)', () => {
  it('다른 탭이 저장한 뒤 [저장] → 409 STALE: 폼 그대로 + stale 줄 + [다시 불러오기] · 고친 것 있으면 확인 창 — [계속 고치기]는 폼 그대로', async () => {
    const { server } = setup('7');
    await waitFor(() => expect(nameBox().value).toBe('제1공장'));
    server.bumpBranch('7', { facilityCodeId: '2', detailName: '다른 탭 줄' });
    fireEvent.change(nameBox(), { target: { value: '제1공장 고침' } });
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(screen.getByTestId('branch-line').textContent).toBe(words.stale),
    );
    expect(server.bodies('PUT /branches/7')).toEqual([
      {
        name: '제1공장 고침',
        inventoryEnabled: true,
        facilities: [],
        updatedAt: '2026-10-28T10:07:00.000001+09:00',
      },
    ]);
    // 아무것도 쓰이지 않았다 — 다른 탭의 줄 그대로.
    expect(server.branches().find((b) => b.id === '7')).toMatchObject({
      name: '제1공장',
      facilities: [expect.objectContaining({ detailName: '다른 탭 줄' })],
    });
    expect(nameBox().value).toBe('제1공장 고침');
    expect(lineKeys()).toEqual([]);
    const reads = server.count('GET /branches/7');
    fireEvent.click(button(words.reload));
    const dialog = await screen.findByTestId('reload-dialog');
    expect(within(dialog).getByText(words.reloadConfirm)).not.toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: words.stay }));
    await waitFor(() =>
      expect(screen.queryByTestId('reload-dialog')).toBeNull(),
    );
    expect(server.count('GET /branches/7')).toBe(reads);
    expect(nameBox().value).toBe('제1공장 고침');
    expect(screen.getByTestId('branch-line').textContent).toBe(words.stale);
  });

  it('확인 → 다시 읽어 폼·판을 새로(다른 탭 줄이 보임) → 그 판으로 저장 200', async () => {
    const { server } = setup('7');
    await waitFor(() => expect(nameBox().value).toBe('제1공장'));
    server.bumpBranch('7', { facilityCodeId: '2', detailName: '다른 탭 줄' });
    const fresh = server.branches().find((b) => b.id === '7')!;
    fireEvent.change(nameBox(), { target: { value: '제1공장 고침' } });
    fireEvent.click(button(words.save));
    await waitFor(() => expect(button(words.reload)).not.toBeNull());
    const reads = server.count('GET /branches/7');
    fireEvent.click(button(words.reload));
    const dialog = await screen.findByTestId('reload-dialog');
    fireEvent.click(
      within(dialog).getByRole('button', { name: words.reloadConfirmOk }),
    );
    await waitFor(() =>
      expect(lineKeys()).toEqual([`saved-${fresh.facilities[0]!.id}`]),
    );
    expect(server.count('GET /branches/7')).toBe(reads + 1);
    expect(nameBox().value).toBe('제1공장');
    expect(screen.getByTestId('branch-line').textContent).toBe('');
    expect(screen.queryByRole('button', { name: words.reload })).toBeNull();
    fireEvent.change(nameBox(), { target: { value: '제1공장 고침' } });
    fireEvent.click(button(words.save));
    await waitFor(() =>
      expect(screen.getByTestId('branch-saved').textContent).toBe(words.saved),
    );
    expect(server.bodies('PUT /branches/7').at(-1)).toMatchObject({
      name: '제1공장 고침',
      updatedAt: fresh.updatedAt,
    });
    expect(server.branches().find((b) => b.id === '7')).toMatchObject({
      name: '제1공장 고침',
      facilities: [expect.objectContaining({ detailName: '다른 탭 줄' })],
    });
  });

  it('고친 것이 없으면 확인 창 없이 바로 다시 읽음 · 다시 읽기가 404 면 찾지 못함', async () => {
    const { server } = setup('7');
    await waitFor(() => expect(nameBox().value).toBe('제1공장'));
    server.bumpBranch('7');
    fireEvent.click(button(words.save));
    await waitFor(() => expect(button(words.reload)).not.toBeNull());
    const reads = server.count('GET /branches/7');
    fireEvent.click(button(words.reload));
    await waitFor(() =>
      expect(server.count('GET /branches/7')).toBe(reads + 1),
    );
    expect(screen.queryByTestId('reload-dialog')).toBeNull();
    await waitFor(() =>
      expect(screen.getByTestId('branch-line').textContent).toBe(''),
    );
    // 다시 한 번 낡게 만들고, 이번엔 그사이 지워진 사업장.
    server.bumpBranch('7');
    fireEvent.click(button(words.save));
    await waitFor(() => expect(button(words.reload)).not.toBeNull());
    server.override['GET /branches/7'] = () => refusal(404, 'NOT_FOUND');
    fireEvent.click(button(words.reload));
    expect(await screen.findByText(words.notFound)).not.toBeNull();
  });

  it('새 사업장(POST)은 판을 싣지 않는다 · STALE 은 PUT 에만', async () => {
    const { server, onCreated } = setup(null);
    fireEvent.change(nameBox(), { target: { value: '제3공장' } });
    fireEvent.click(button(words.save));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith('8'));
    expect(server.bodies('POST /branches')).toStrictEqual([
      { name: '제3공장', inventoryEnabled: true, facilities: [] },
    ]);
  });
});
