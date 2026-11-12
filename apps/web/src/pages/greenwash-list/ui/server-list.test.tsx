// @vitest-environment jsdom
// 밴드 GW1R ②(발주서 §3 C — GW-01): 진짜 실어댑터 + 거르지 않는 가짜 서버로 목록을 그린다. 화면이 서버 꼴을 그대로 쓰는지(어댑터가 맞춘 값)를 본다.
//   ①「내가 올린 것만」= 지금 사용자 7 의 줄 ②「확정자 가」 ③ judge 3/10 → 34% ④ no_text_layer 줄엔 [다시 실행] 없음(빈칸)·step_error 줄엔 있음
//   ⑤ 쪽 수 모름은 「–」, checks 500 → 「문서 목록을 불러오지 못했어요」(목 씨앗 줄 0).
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  FAKE_CONFIRMER,
  fakeSteps,
  listedGreenwashServer,
  refusal,
  serverStoreOf,
} from '../../../entities/greenwash/api/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import { ListScreen } from './ListScreen.tsx';

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

const words = GW_TEXT.list;

function draw(server = listedGreenwashServer()) {
  const { store } = serverStoreOf(server);
  const onOpen = vi.fn();
  render(<ListScreen store={store} onNewCheck={vi.fn()} onOpen={onOpen} />);
  return { server, onOpen };
}

/** 파일 이름으로 그 줄(tr). */
const rowOf = async (fileName: string) =>
  (await screen.findByText(fileName)).closest('tr')!;
const shownNames = () =>
  [...document.querySelectorAll('tbody tr')].map(
    (row) => row.querySelector('td')?.textContent ?? '',
  );

describe('GW-01 실어댑터(밴드 GW1R ② §3 C)', () => {
  it('GET /greenwash/checks 한 번, 줄 넷 — 34%·「확정자 가」·쪽 수 「–」', async () => {
    const { server } = draw();
    const analyzing = await rowOf('지어낸 분석 보고서.pdf');
    expect(server.count('GET /greenwash/checks')).toBe(1);
    expect(shownNames()).toHaveLength(4);
    expect(analyzing.textContent).toContain('34%');
    const confirmed = await rowOf('지어낸 확정 보고서.pdf');
    expect(
      confirmed.querySelector('[data-confirmed-by]')?.textContent,
    ).toContain(FAKE_CONFIRMER.name);
    // ⑤ 쪽 수: 아는 것은 숫자, 모르는 것(null)은 「–」
    const cells = (row: Element) =>
      [...row.querySelectorAll('td')].map((cell) => cell.textContent);
    const pageColumn = [...document.querySelectorAll('thead th')].findIndex(
      (cell) => cell.textContent === words.columns.pageCount,
    );
    expect(cells(confirmed)[pageColumn]).toBe('40');
    expect(cells(analyzing)[pageColumn]).toBe(words.none);
  });

  it('「내가 올린 것만」은 지금 사용자(7)가 올린 줄만 — 서버의 id 숫자를 글자로 맞춰 견준다', async () => {
    draw();
    await rowOf('지어낸 분석 보고서.pdf');
    fireEvent.click(screen.getByRole('checkbox', { name: words.mineOnly }));
    expect(shownNames().sort()).toEqual(
      ['지어낸 멈춘 보고서.pdf', '지어낸 확정 보고서.pdf'].sort(),
    );
  });

  it('실패 줄: no_text_layer 는 [다시 실행] 없이 빈칸, step_error 는 [다시 실행] → 새 실행', async () => {
    const { server, onOpen } = draw();
    const noText = await rowOf('지어낸 스캔 보고서.pdf');
    const stepError = await rowOf('지어낸 멈춘 보고서.pdf');
    // 둘 다 extract 에서 멈춘 실패다 — 가름은 errorCode 하나
    expect(noText.querySelector('[data-next]')).toBeNull();
    const lastCell = [...noText.querySelectorAll('td')].at(-1)!;
    expect(lastCell.textContent).toBe('');
    const rerun = stepError.querySelector<HTMLButtonElement>(
      '[data-next="rerun"]',
    )!;
    expect(rerun.textContent).toBe(words.next.rerun);
    fireEvent.click(rerun);
    await vi.waitFor(() =>
      expect(onOpen).toHaveBeenCalledWith({ screen: 'status', runId: '13' }),
    );
    expect(server.count('GET /runs/8')).toBe(1);
    expect(server.calls.at(-1)).toMatchObject({
      method: 'POST',
      path: '/runs',
      body: {
        module: 'greenwash',
        documentId: 4,
        options: { parts: { ceo: [], company: [], climate: [1, 2, 3] } },
      },
    });
  });

  it('setup_error 줄도 [다시 실행] 없이 빈칸, index 에서 멈춘 step_error 줄은 [다시 실행](밴드 GW2R ② Q5 — 가름은 errorCode, 단계 아님)', async () => {
    const server = listedGreenwashServer();
    // 실서버 꼴: setup_error 는 index 에서 멈춘다. 같은 index 에서 멈춘 step_error 와 섞어 둔다
    Object.assign(server.runs.get(8)!, {
      errorCode: 'setup_error',
      steps: fakeSteps(1, { status: 'failed' }),
    });
    Object.assign(server.runs.get(7)!, {
      errorCode: 'step_error',
      steps: fakeSteps(1, { status: 'failed' }),
    });
    draw(server);
    const setup = await rowOf('지어낸 멈춘 보고서.pdf');
    const stepError = await rowOf('지어낸 스캔 보고서.pdf');
    expect(setup.querySelector('[data-next]')).toBeNull();
    expect([...setup.querySelectorAll('td')].at(-1)!.textContent).toBe('');
    expect(stepError.querySelector('[data-next="rerun"]')?.textContent).toBe(
      words.next.rerun,
    );
    // 두 줄 다 상태 배지는 「멈춤」(디자인 답 D6)
    for (const row of [setup, stepError])
      expect(row.querySelector('[data-testid="row-status"]')?.textContent).toBe(
        '멈춤',
      );
  });

  it('checks 500 → 「문서 목록을 불러오지 못했어요」+ [다시 시도], 목 씨앗 줄은 없다', async () => {
    const server = listedGreenwashServer();
    // 처음 한 번만 500(다시 시도는 서버 답)
    server.override['GET /greenwash/checks'] = [
      () => refusal(500, 'INTERNAL_SERVER_ERROR'),
    ];
    draw(server);
    const failure = await screen.findByTestId('load-failure');
    expect(failure.textContent).toContain(words.loadFailed);
    expect(words.loadFailed).toBe('문서 목록을 불러오지 못했어요');
    expect(document.querySelectorAll('tbody tr[data-row]').length).toBe(0);
    expect(document.body.textContent).not.toMatch(/목-|지어낸 확정/);
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    await rowOf('지어낸 확정 보고서.pdf');
    expect(server.count('GET /greenwash/checks')).toBe(2);
  });
});
