// @vitest-environment jsdom
// GW-05 r4 근거 고치기·재판단(밴드 GRJ1 ③ — 결정 MARC-ENT-617, 시안 r4 ①~④·r5). 진짜 실어댑터 + 시험용 가짜 서버(흉내 규칙은
// rejudgeRules.ts 한 벌 — 재판단은 만든 뒤 검토 GET 둘째 번에 끝난다). 도는 중 다시 읽기는 가짜 시계로 돌린다. 값은 지어낸 것이다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  MOCK_FAIL_MARK,
  MOCK_NONRISK_MARK,
  fakeDocument,
  fakeGreenwashServer,
  fakeRun,
  fakeSteps,
  refusal,
  serverStoreOf,
} from '../../../entities/greenwash/api/testing.ts';
import type { FakeGreenwashServer } from '../../../entities/greenwash/api/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import { REJUDGE_POLL_MS } from '../../../entities/greenwash/hooks/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { ReviewScreen } from './ReviewScreen.tsx';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

beforeAll(() => {
  Object.assign(URL, {
    createObjectURL: vi.fn(() => 'blob:지어낸'),
    revokeObjectURL: vi.fn(),
  });
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

const words = GW_TEXT.reviewScreen;
const say = words.rejudge;
const USER = { id: 7, name: '담당자 가' };
const neverOpen: OpenPdf = () => new Promise(() => {});
const CHIPS = ['지어낸 사실 가', '지어낸 사실 나'];

/** 끝난 실행 12(문장 셋 High·Mid·Low, 검토 pending). 첫 문장에만 근거 칩 둘. */
function doneServer() {
  const server = fakeGreenwashServer({
    currentUser: USER,
    documents: [fakeDocument(3)],
    runs: [fakeRun(12, 3, { status: 'processing', steps: fakeSteps(2) })],
  });
  server.advance(12, { status: 'done' });
  const run = server.runs.get(12)!;
  run.result = {
    ...run.result!,
    items: run.result!.items.map((item, i) =>
      i === 0 ? { ...item, confirmedInEvidence: CHIPS } : item,
    ),
  };
  return server;
}

async function draw(server: FakeGreenwashServer) {
  const { store } = serverStoreOf(server);
  await act(async () => {
    render(
      <ReviewScreen
        store={store}
        openPdf={neverOpen}
        runId="12"
        onBack={vi.fn()}
        onList={vi.fn()}
      />,
    );
  });
  await act(async () => {});
  await act(async () => {});
}

const detail = () => screen.getByTestId('review-detail');
const evidence = () => within(detail()).getByTestId('evidence');
const rejudgeButton = () =>
  within(detail()).getByTestId('rejudge') as HTMLButtonElement;
const rows = () =>
  within(screen.getByTestId('sentence-list')).getAllByRole('button');
const gets = (server: FakeGreenwashServer) =>
  server.count('GET /greenwash/runs/12/review');
const posts = (server: FakeGreenwashServer) =>
  server.calls.filter(
    (c) => c.method === 'POST' && c.path.endsWith('/rejudge'),
  );
const puts = (server: FakeGreenwashServer) =>
  server.calls.filter((c) => c.method === 'PUT');

async function click(element: HTMLElement) {
  await act(async () => {
    fireEvent.click(element);
  });
  await act(async () => {});
}

/** 근거 칸에서 초점이 나간다(칸을 벗어나면 저장). */
async function leaveEvidence(to: HTMLElement = rejudgeButton()) {
  await act(async () => {
    fireEvent.focusOut(evidence(), { relatedTarget: to });
  });
  await act(async () => {});
}

async function addPiece(text: string, page: number | null) {
  await click(within(evidence()).getByTestId('evidence-add-open'));
  const box = within(evidence()).getByLabelText(say.addText);
  await act(async () => {
    fireEvent.change(box, { target: { value: text } });
  });
  if (page !== null)
    await act(async () => {
      fireEvent.change(within(evidence()).getByLabelText(say.addPage), {
        target: { value: String(page) },
      });
    });
  await click(within(evidence()).getByRole('button', { name: say.add }));
}

async function tick() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(REJUDGE_POLL_MS);
  });
  await act(async () => {});
}

describe('GW-05 r4 근거 고치기·재판단', () => {
  it('근거를 고치기 전 [재판단]은 꺼져 hover 글, 지우면 줄그음·[되살리기]·바뀜 한 줄·켜짐, 되살리면 다시 꺼짐', async () => {
    await draw(doneServer());
    expect(rejudgeButton().disabled).toBe(true);
    expect(rejudgeButton().parentElement?.getAttribute('title')).toBe(
      say.buttonOff,
    );
    await click(within(evidence()).getByTestId('evidence-edit'));
    const first = () => within(evidence()).getByTestId('chips').children[0]!;
    await click(
      within(first() as HTMLElement).getByRole('button', { name: say.remove }),
    );
    expect(first().getAttribute('data-removed')).toBe('true');
    expect(within(detail()).getByTestId('evidence-changed').textContent).toBe(
      say.changed(1, 0),
    );
    expect(rejudgeButton().disabled).toBe(false);
    await click(
      within(first() as HTMLElement).getByRole('button', { name: say.restore }),
    );
    expect(first().getAttribute('data-removed')).toBeNull();
    expect(within(detail()).queryByTestId('evidence-changed')).toBeNull();
    expect(rejudgeButton().disabled).toBe(true);
  });

  it('칸을 벗어나면 PUT evidence → [재판단] POST → 도는 중(뼈대·한 줄·「재판단 중…」·목록 돌림) → 끝남(새 등급·「재판단 · 때 · 사람」·첫 판단 접힘·목록 딱지), 다시 읽기 멈춤', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    const chip0 = within(evidence()).getByTestId('chips')
      .children[0] as HTMLElement;
    await click(within(chip0).getByRole('button', { name: say.remove }));
    await addPiece('지어낸 더한 조각', 2);
    expect(
      within(evidence()).getByText(`지어낸 더한 조각 ${say.addedPage(2)}`),
    ).toBeTruthy();
    expect(within(evidence()).getByText(say.addedMark)).toBeTruthy();
    expect(within(detail()).getByTestId('evidence-changed').textContent).toBe(
      say.changed(1, 1),
    );
    await leaveEvidence();
    expect(puts(server).at(-1)?.body).toEqual({
      marks: [],
      evidence: [
        {
          itemIndex: 0,
          removed: [0],
          added: [{ text: '지어낸 더한 조각', page: 2 }],
        },
      ],
    });
    await click(rejudgeButton());
    expect(posts(server).map((c) => c.path)).toEqual([
      '/greenwash/runs/12/items/0/rejudge',
    ]);
    // 도는 중
    expect(within(detail()).getByTestId('rejudge-running').textContent).toBe(
      say.running,
    );
    expect(within(detail()).getByTestId('rejudge-skeleton')).toBeTruthy();
    expect(within(detail()).queryByTestId('field-reasonBullets')).toBeNull();
    expect(rejudgeButton().textContent).toBe(say.buttonRunning);
    expect(rejudgeButton().disabled).toBe(true);
    expect(within(rows()[0]!).getByTestId('row-rejudging')).toBeTruthy();
    // 다른 문장으로 옮겨 가도 된다
    await click(rows()[1]!);
    expect(within(detail()).queryByTestId('rejudge-running')).toBeNull();
    await click(rows()[0]!);
    // 다시 읽기 한 번 → 끝남(가짜 서버: 만든 뒤 GET 둘째 번)
    await tick();
    expect(within(detail()).queryByTestId('rejudge-running')).toBeNull();
    expect(within(detail()).getByTestId('rejudge-judged').textContent).toBe(
      say.judged('10-19 10:00', USER.name),
    );
    expect(
      within(detail())
        .getByRole('button', { name: /등급 고르기/ })
        .getAttribute('data-level-pick'),
    ).toBe('low');
    expect(
      within(detail()).getByTestId('first-judgment').textContent,
    ).toContain(say.firstJudgment);
    expect(within(rows()[0]!).getByText(say.rejudgedMark)).toBeTruthy();
    expect(within(rows()[0]!).queryByTestId('row-rejudging')).toBeNull();
    // 줄그음 사라지고 더한 조각은 남는다
    const list = within(evidence()).getByTestId('chips');
    expect(list.querySelector('[data-removed]')).toBeNull();
    expect(list.querySelector('[data-added]')?.textContent).toContain(
      '지어낸 더한 조각',
    );
    expect(rejudgeButton().disabled).toBe(true);
    // running 0 → 다시 읽지 않는다
    const seen = gets(server);
    await tick();
    await tick();
    expect(gets(server)).toBe(seen);
    // 끝난 뒤 근거 칸 아래 바뀜 줄은 꺼져 있고(기준 판단이 보낸 근거와 같다), 조각을 하나 더 더하면 다시 나온다(밴드 GRJ4 N3 — sid:MARC-ISSUE-639)
    expect(within(detail()).queryByTestId('evidence-changed')).toBeNull();
    await click(within(evidence()).getByTestId('evidence-edit'));
    expect(within(detail()).queryByTestId('evidence-changed')).toBeNull();
    await addPiece('지어낸 끝난 뒤 조각', null);
    expect(within(detail()).getByTestId('evidence-changed').textContent).toBe(
      say.changed(0, 1),
    );
    expect(rejudgeButton().disabled).toBe(false);
  });

  it('리스크 아님(r5): 등급 자리 회색 딱지 + 한 줄, 목록 회색 딱지, High 탭에 없고 전체에만', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await draw(doneServer());
    await click(within(evidence()).getByTestId('evidence-edit'));
    await addPiece(`${MOCK_NONRISK_MARK} 지어낸 조각`, null);
    await leaveEvidence();
    await click(rejudgeButton());
    await tick();
    expect(within(detail()).getByText(say.nonRisk)).toBeTruthy();
    expect(within(detail()).getByTestId('nonrisk-note').textContent).toBe(
      say.nonRiskNote,
    );
    expect(
      within(detail()).queryByRole('button', { name: /등급 고르기/ }),
    ).toBeNull();
    expect(within(rows()[0]!).getByText(say.nonRisk)).toBeTruthy();
    const high = screen.getByRole('tab', {
      name: new RegExp(`^${words.levelTabs.High}`),
    });
    await act(async () => {
      fireEvent.mouseDown(high);
      fireEvent.click(high);
    });
    // 첫 문장(첫 판단 High)이 빠져 High 탭이 빈다
    expect(screen.queryByText(say.nonRiskNote)).toBeNull();
    expect(screen.queryByTestId('sentence-list')).toBeNull();
    expect(screen.getAllByText(words.listEmpty).length).toBeGreaterThan(0);
  });

  it('실패(r4 ④): 빨간 한 줄 + [다시 시도], 근거 고침은 남고 [재판단] 켜짐, 앞 판단 그대로', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await addPiece(`${MOCK_FAIL_MARK} 지어낸 조각`, null);
    await leaveEvidence();
    await click(rejudgeButton());
    await tick();
    const failed = within(detail()).getByTestId('rejudge-failed');
    expect(failed.getAttribute('role')).toBe('alert');
    expect(failed.textContent).toContain(say.failed);
    expect(within(detail()).queryByTestId('rejudge-judged')).toBeNull();
    expect(
      within(evidence()).getByTestId('chips').querySelector('[data-added]'),
    ).toBeTruthy();
    expect(rejudgeButton().disabled).toBe(false);
    await click(within(failed).getByRole('button', { name: say.retry }));
    expect(posts(server)).toHaveLength(2);
  });

  it('③ 고친 칸: 고친 뒤 재판단이 끝나면 칸 머리 「AI 판단이 바뀌었어요」, 접기 안은 새 AI 값', async () => {
    const server = doneServer();
    const run = server.runs.get(12)!;
    run.review = {
      ...run.review!,
      state: 'in_review',
      edits: [
        {
          itemIndex: 0,
          level: null,
          reasonBullets: null,
          fixParagraph: {
            value: '사람이 고친 수정 방향.',
            editedAt: '2026-10-19T09:00:00+09:00',
            editedBy: USER,
          },
        },
      ],
      rejudges: [
        {
          runId: 9001,
          itemIndex: 0,
          status: 'done',
          reads: 2,
          added: [],
          judged: {
            runId: 9001,
            judgedAt: '2026-10-19T10:00:00+09:00',
            judgedBy: USER,
            outcome: 'judged',
            level: 'Mid',
            riskTags: [],
            confirmedInEvidence: ['다시 본 사실'],
            missingFields: [],
            reasonBullets: ['다시 본 사유.'],
            fixParagraph: '다시 본 수정 방향.',
            evidencePages: [],
            added: [],
          },
        },
      ],
    };
    await draw(server);
    const fix = within(detail()).getByTestId('field-fixParagraph');
    expect(fix.querySelector('[data-ai-changed]')?.textContent).toBe(
      words.edit.aiChanged,
    );
    expect(fix.textContent).toContain('사람이 고친 수정 방향.');
    expect(fix.querySelector('[data-ai-original]')?.textContent).toContain(
      '다시 본 수정 방향.',
    );
    // 고치지 않은 사유 칸은 기준 판단 값 그대로, 머리 안내 없음
    const reasons = within(detail()).getByTestId('field-reasonBullets');
    expect(reasons.textContent).toContain('다시 본 사유.');
    expect(reasons.querySelector('[data-ai-changed]')).toBeNull();
  });

  it('④ B1: 재판단이 도는 동안 [확정]은 꺼지고 까닭 한 줄, 끝나면 켜짐 · 다른 탭이 건 재판단으로 확정 PUT 이 409 면 같은 뜻의 글', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = doneServer();
    await draw(server);
    const confirmButton = () =>
      screen.getByRole('button', { name: words.confirm }) as HTMLButtonElement;
    expect(confirmButton().disabled).toBe(false);
    expect(screen.queryByTestId('confirm-waits')).toBeNull();
    await click(within(evidence()).getByTestId('evidence-edit'));
    const chip0 = within(evidence()).getByTestId('chips')
      .children[0] as HTMLElement;
    await click(within(chip0).getByRole('button', { name: say.remove }));
    await leaveEvidence();
    await click(rejudgeButton());
    expect(within(detail()).getByTestId('rejudge-running')).toBeTruthy();
    expect(confirmButton().disabled).toBe(true);
    expect(screen.getByTestId('confirm-waits').textContent).toBe(
      say.confirmWaits,
    );
    await tick();
    expect(within(detail()).getByTestId('rejudge-judged')).toBeTruthy();
    expect(confirmButton().disabled).toBe(false);
    expect(screen.queryByTestId('confirm-waits')).toBeNull();
    // 다른 탭이 건 재판단(이 화면은 모름): 확정 PUT 409 REJUDGE_RUNNING → 다시 읽고 같은 뜻의 오류 줄, 잠기지 않음
    server.override['PUT /greenwash/runs/12/review'] = [
      () => refusal(409, 'REJUDGE_RUNNING'),
    ];
    await click(confirmButton());
    const dialog = screen.getByRole('dialog', { name: GW_TEXT.confirm.title });
    await click(
      within(dialog).getByRole('button', { name: GW_TEXT.confirm.submit }),
    );
    await act(async () => {});
    expect(screen.getByTestId('save-error').textContent).toBe(say.confirmWaits);
    expect(server.runs.get(12)!.review!.state).not.toBe('confirmed');
  });

  it('409 rejudge_running·nothing_to_rejudge 는 그 글, 확정 뒤에는 근거 [고치기]·[재판단]이 없다', async () => {
    const server = doneServer();
    server.override['POST /greenwash/runs/12/items/0/rejudge'] = [
      () => refusal(409, 'REJUDGE_RUNNING'),
      () => refusal(409, 'NOTHING_TO_REJUDGE'),
    ];
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    const chip0 = within(evidence()).getByTestId('chips')
      .children[0] as HTMLElement;
    await click(within(chip0).getByRole('button', { name: say.remove }));
    await leaveEvidence();
    await click(rejudgeButton());
    expect(screen.getByText(say.saveRunning)).toBeTruthy();
    await click(rejudgeButton());
    expect(screen.getByText(say.saveNothing)).toBeTruthy();
    cleanup();

    const locked = doneServer();
    const run = locked.runs.get(12)!;
    run.review = {
      ...run.review!,
      state: 'confirmed',
      confirmedAt: '2026-10-19T11:00:00+09:00',
      confirmedBy: USER,
    };
    await draw(locked);
    expect(within(evidence()).queryByTestId('evidence-edit')).toBeNull();
    expect(within(detail()).queryByTestId('rejudge')).toBeNull();
  });

  // 밴드 GRJ2(sid:MARC-TICK-568): 「추가」 뒤 상자가 사라져 칸 blur 가 오지 않았다 — 칸 벗어남(leaveEvidence) 없이 곧바로 [재판단].
  const methods = (server: FakeGreenwashServer) =>
    server.calls
      .filter(
        (c) =>
          c.method === 'PUT' ||
          (c.method === 'POST' && c.path.endsWith('/rejudge')),
      )
      .map((c) => c.method);

  it('GRJ2 R1: 조각 「추가」 뒤 곧바로 [재판단] — PUT(근거 실림)이 POST 보다 먼저, 409 아님', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await addPiece('지어낸 더한 조각', 2);
    await click(rejudgeButton());
    expect(methods(server)).toEqual(['PUT', 'POST']);
    expect(puts(server)[0]?.body).toEqual({
      marks: [],
      evidence: [
        {
          itemIndex: 0,
          removed: [],
          added: [{ text: '지어낸 더한 조각', page: 2 }],
        },
      ],
    });
    expect(screen.queryByText(say.saveNothing)).toBeNull();
    expect(within(detail()).getByTestId('rejudge-running')).toBeTruthy();
  });

  it('GRJ2 R2: 「추가」 뒤 아무것도 안 누르고 화면을 다시 그려도 더한 조각이 남는다', async () => {
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await addPiece('지어낸 남는 조각', null);
    cleanup();
    await draw(server);
    expect(
      within(evidence()).getByTestId('chips').querySelector('[data-added]')
        ?.textContent,
    ).toContain('지어낸 남는 조각');
  });

  it('GRJ2 R3: 칩 「지우기」 뒤 곧바로 [재판단] — PUT 이 POST 보다 먼저', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    const chip0 = within(evidence()).getByTestId('chips')
      .children[0] as HTMLElement;
    await click(within(chip0).getByRole('button', { name: say.remove }));
    await click(rejudgeButton());
    expect(methods(server)).toEqual(['PUT', 'POST']);
    expect(puts(server)[0]?.body).toEqual({
      marks: [],
      evidence: [{ itemIndex: 0, removed: [0], added: [] }],
    });
    expect(screen.queryByText(say.saveNothing)).toBeNull();
    expect(within(detail()).getByTestId('rejudge-running')).toBeTruthy();
  });

  it('GRJ2 R4: 근거 저장이 거절되면 [재판단]은 POST 를 보내지 않고 초안이 칸에 남는다', async () => {
    const server = doneServer();
    server.override['PUT /greenwash/runs/12/review'] = [
      () => refusal(400, 'INVALID_REVIEW'),
      () => refusal(400, 'INVALID_REVIEW'),
      () => refusal(400, 'INVALID_REVIEW'),
    ];
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await addPiece('지어낸 거절될 조각', null);
    await click(rejudgeButton());
    expect(posts(server)).toHaveLength(0);
    expect(puts(server).length).toBeGreaterThan(0);
    expect(evidence().getAttribute('data-editing')).toBe('true');
    expect(
      within(evidence()).getByTestId('chips').querySelector('[data-added]')
        ?.textContent,
    ).toContain('지어낸 거절될 조각');
    expect(screen.getByTestId('save-error')).toBeTruthy();
  });

  it('GRJ2: 「추가」·「취소」 뒤 초점은 칸 안 [+ 근거 더하기], 저장된 뒤 칸을 벗어나면 PUT 없이 닫는다', async () => {
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await addPiece('지어낸 초점 조각', null);
    expect(document.activeElement).toBe(
      within(evidence()).getByTestId('evidence-add-open'),
    );
    await click(within(evidence()).getByTestId('evidence-add-open'));
    await click(within(evidence()).getByRole('button', { name: say.cancel }));
    expect(document.activeElement).toBe(
      within(evidence()).getByTestId('evidence-add-open'),
    );
    expect(puts(server)).toHaveLength(1);
    await leaveEvidence();
    expect(puts(server)).toHaveLength(1);
    expect(evidence().getAttribute('data-editing')).toBeNull();
  });
});

// 밴드 GRJ3(sid:MARC-TICK-569): 재판단이 도는 동안 근거 칸을 고치지 못하게 — 서버도 도는 문장의 근거 PUT 을 409 로 막는다.
describe('GRJ3 재판단이 도는 동안 근거 칸', () => {
  const methods = (server: FakeGreenwashServer) =>
    server.calls
      .filter(
        (c) =>
          c.method === 'PUT' ||
          (c.method === 'POST' && c.path.endsWith('/rejudge')),
      )
      .map((c) => c.method);
  const chip = (index: number) =>
    within(evidence()).getByTestId('chips').children[index] as HTMLElement;
  const editButtons = () =>
    within(evidence()).queryAllByRole('button', {
      name: new RegExp(`^(${say.remove}|${say.restore})$`),
    });

  /** PUT(또는 method)을 붙잡을 수 있게 server.send 를 감싼다(draw 앞에 — 어댑터가 그때의 send 를 쥔다). */
  function holdPuts(server: FakeGreenwashServer, method = 'PUT') {
    const real = server.send;
    let gate: Promise<void> | null = null;
    let open = () => {};
    server.send = async (request: Request) => {
      if (request.method === method && gate !== null) await gate;
      return real(request);
    };
    return {
      hold() {
        gate = new Promise((resolve) => {
          open = () => {
            gate = null;
            resolve();
          };
        });
      },
      release: async () => {
        await act(async () => {
          open();
        });
        await act(async () => {});
        await act(async () => {});
      },
    };
  }

  it('S1: 고치는 중 칸 벗어남 없이 [재판단] → 도는 동안 [지우기]·[+ 근거 더하기]·입력 상자가 없고 PUT 은 재판단 앞 한 번뿐', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await click(within(chip(0)).getByRole('button', { name: say.remove }));
    // 쓰던 입력 상자를 연 채로 누른다(쓰던 글은 버린다 — 발주서 §1.3)
    await click(within(evidence()).getByTestId('evidence-add-open'));
    await act(async () => {
      fireEvent.change(within(evidence()).getByLabelText(say.addText), {
        target: { value: '지어낸 쓰던 글' },
      });
    });
    await click(rejudgeButton());
    expect(methods(server)).toEqual(['PUT', 'POST']);
    expect(within(detail()).getByTestId('rejudge-running')).toBeTruthy();
    expect(editButtons()).toEqual([]);
    expect(within(evidence()).queryByTestId('evidence-add-open')).toBeNull();
    expect(within(evidence()).queryByTestId('evidence-add')).toBeNull();
    expect(within(evidence()).queryByTestId('evidence-edit')).toBeNull();
    expect(evidence().getAttribute('data-editing')).toBeNull();
    // 칸은 서버 값(지운 칩 줄그음)
    expect(chip(0).getAttribute('data-removed')).toBe('true');
    // 칸을 벗어나도 PUT 이 나가지 않는다
    await leaveEvidence(document.body);
    expect(methods(server)).toEqual(['PUT', 'POST']);
  });

  it('S1b: [재판단]을 누르고 답을 기다리는 동안에도(고치는 중인 채) 칸에 고치기 단추가 없다', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = doneServer();
    const held = holdPuts(server, 'POST');
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await click(within(chip(0)).getByRole('button', { name: say.remove }));
    held.hold();
    await click(rejudgeButton());
    expect(methods(server)).toEqual(['PUT']);
    expect(rejudgeButton().textContent).toBe(say.buttonRunning);
    expect(editButtons()).toEqual([]);
    expect(within(evidence()).queryByTestId('evidence-add-open')).toBeNull();
    await held.release();
    expect(methods(server)).toEqual(['PUT', 'POST']);
    expect(editButtons()).toEqual([]);
  });

  it('S2: 재판단이 409 로 거절되면 칸은 연 채 초안이 남는다', async () => {
    const server = doneServer();
    server.override['POST /greenwash/runs/12/items/0/rejudge'] = [
      () => refusal(409, 'NOTHING_TO_REJUDGE'),
    ];
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await click(within(chip(0)).getByRole('button', { name: say.remove }));
    await click(rejudgeButton());
    expect(methods(server)).toEqual(['PUT', 'POST']);
    expect(screen.getByText(say.saveNothing)).toBeTruthy();
    expect(evidence().getAttribute('data-editing')).toBe('true');
    expect(chip(0).getAttribute('data-removed')).toBe('true');
    expect(
      within(chip(0)).getByRole('button', { name: say.restore }),
    ).toBeTruthy();
    expect(within(evidence()).getByTestId('evidence-add-open')).toBeTruthy();
  });

  it('S3: 재판단이 끝나면 칸은 보기 꼴이고 [고치기]로 다시 열 수 있다', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await addPiece('지어낸 끝남 조각', null);
    // 쓰던 입력 상자를 연 채 [재판단] — 끝난 뒤 다시 열면 상자는 닫혀 있다(쓰던 글은 버렸다)
    await click(within(evidence()).getByTestId('evidence-add-open'));
    await act(async () => {
      fireEvent.change(within(evidence()).getByLabelText(say.addText), {
        target: { value: '지어낸 버릴 글' },
      });
    });
    await click(rejudgeButton());
    await tick();
    expect(within(detail()).getByTestId('rejudge-judged')).toBeTruthy();
    expect(evidence().getAttribute('data-editing')).toBeNull();
    expect(editButtons()).toEqual([]);
    await click(within(evidence()).getByTestId('evidence-edit'));
    expect(evidence().getAttribute('data-editing')).toBe('true');
    expect(editButtons().length).toBeGreaterThan(0);
    expect(within(evidence()).getByTestId('evidence-add-open')).toBeTruthy();
    expect(within(evidence()).queryByTestId('evidence-add')).toBeNull();
    expect(screen.queryByDisplayValue('지어낸 버릴 글')).toBeNull();
  });

  it('S4: 근거 저장이 도는 동안 [재판단]을 두 번 눌러도 PUT 1·POST 1', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = doneServer();
    const held = holdPuts(server);
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    held.hold();
    await click(within(chip(0)).getByRole('button', { name: say.remove }));
    await click(rejudgeButton());
    await click(rejudgeButton());
    // PUT 은 붙잡혀 아직 가짜 서버에 닿지 않았다(기록은 닿을 때) — POST 도 없다
    expect(methods(server)).toEqual([]);
    await held.release();
    expect(methods(server)).toEqual(['PUT', 'POST']);
    expect(within(detail()).getByTestId('rejudge-running')).toBeTruthy();
  });

  it('S5: 칸을 닫았다 다시 열면 마지막으로 보낸 것과 같은 초안도 다시 저장한다(서버 값이 그 사이 바뀜)', async () => {
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await click(within(chip(0)).getByRole('button', { name: say.remove }));
    await click(within(chip(0)).getByRole('button', { name: say.restore }));
    expect(puts(server)).toHaveLength(2);
    await leaveEvidence();
    expect(evidence().getAttribute('data-editing')).toBeNull();
    // 다른 탭이 칩을 지웠다 — 이 화면은 표시 저장의 답으로 그것을 받는다
    const run = server.runs.get(12)!;
    run.review = {
      ...run.review!,
      evidence: [
        {
          itemIndex: 0,
          removed: [0],
          added: [],
          editedAt: '2026-10-19T09:30:00+09:00',
          editedBy: USER,
        },
      ],
    };
    await act(async () => {
      fireEvent.click(
        within(
          within(detail()).getByRole('group', {
            name: GW_TEXT.review.groupLabel,
          }),
        ).getByRole('button', { name: GW_TEXT.review.adopted }),
      );
    });
    await act(async () => {});
    expect(chip(0).getAttribute('data-removed')).toBe('true');
    await click(within(evidence()).getByTestId('evidence-edit'));
    await click(within(chip(0)).getByRole('button', { name: say.restore }));
    expect(puts(server).at(-1)?.body).toEqual({
      marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
      evidence: [],
    });
    expect(server.runs.get(12)!.review!.evidence).toEqual([]);
  });

  it('S6: 다른 탭이 이 문장의 재판단을 걸어 다시 읽은 검토에 running 이 오면 고치던 칸을 닫는다', async () => {
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await click(within(chip(0)).getByRole('button', { name: say.remove }));
    expect(puts(server)).toHaveLength(1);
    // 다른 탭(같은 가짜 서버의 다른 저장소)이 재판단을 건다
    await act(async () => {
      await serverStoreOf(server).store.rejudge('12', 0);
    });
    // 이 화면은 표시 저장의 답으로 도는 줄을 받는다
    await act(async () => {
      fireEvent.click(
        within(
          within(detail()).getByRole('group', {
            name: GW_TEXT.review.groupLabel,
          }),
        ).getByRole('button', { name: GW_TEXT.review.adopted }),
      );
    });
    await act(async () => {});
    expect(within(detail()).getByTestId('rejudge-running')).toBeTruthy();
    expect(evidence().getAttribute('data-editing')).toBeNull();
    expect(editButtons()).toEqual([]);
  });

  it('도는 문장의 근거를 바꾼 PUT 이 409 rejudge_running 이면 확정 글이 아닌 재판단 글(다른 탭이 건 재판단)', async () => {
    const server = doneServer();
    await draw(server);
    await click(within(evidence()).getByTestId('evidence-edit'));
    server.override['PUT /greenwash/runs/12/review'] = [
      () => refusal(409, 'REJUDGE_RUNNING'),
    ];
    await click(within(chip(0)).getByRole('button', { name: say.remove }));
    expect(screen.getByTestId('save-error').textContent).toBe(say.saveRunning);
    expect(screen.queryByText(say.confirmWaits)).toBeNull();
  });
});

/** doneServer 에서 고른 문장들의 근거 페이지를 비운다(첫 판단). */
function noPagesServer(indexes: readonly number[]) {
  const server = doneServer();
  const run = server.runs.get(12)!;
  run.result = {
    ...run.result!,
    items: run.result!.items.map((item, i) =>
      indexes.includes(i) ? { ...item, evidencePages: [] } : item,
    ),
  };
  return server;
}

const noEvidence = () => within(detail()).queryByTestId('no-evidence');

describe('GRJ4 「근거 조각을 찾지 못했어요」는 근거 조각이 정말 없을 때만(디자인 b2 11-10 — sid:MARC-ISSUE-639)', () => {
  it('N1 첫 판단: 근거 페이지 0 이어도 칩이 있으면 줄이 없다, 칩도 더한 조각도 없으면 지금 글 그대로', async () => {
    await draw(noPagesServer([0, 2]));
    // 문장 0: 페이지 0 · 칩 둘
    expect(within(detail()).queryByTestId('detail-evidence-pages')).toBeNull();
    expect(within(evidence()).getByTestId('chips').children).toHaveLength(2);
    expect(noEvidence()).toBeNull();
    // 칩을 지워도(줄그음으로 남는다) 줄은 없다
    await click(within(evidence()).getByTestId('evidence-edit'));
    for (const chip of [0, 1]) {
      const li = within(evidence()).getByTestId('chips').children[
        chip
      ] as HTMLElement;
      await click(within(li).getByRole('button', { name: say.remove }));
    }
    expect(
      within(evidence())
        .getByTestId('chips')
        .querySelectorAll('[data-removed="true"]'),
    ).toHaveLength(2);
    expect(noEvidence()).toBeNull();
    // 문장 2: 페이지 0 · 칩 0 · 더한 0 → 지금 글
    await click(rows()[2]!);
    expect(within(evidence()).getByTestId('chips').children).toHaveLength(0);
    expect(noEvidence()?.textContent).toBe(words.noEvidence);
  });

  it('N1 재판단: 페이지 없이 더한 조각이 있으면 줄이 없다 — 더하면 빠지고, 재판단이 끝나 기준 판단 페이지가 [] 여도 없다', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const server = noPagesServer([1]);
    await draw(server);
    await click(rows()[1]!);
    expect(noEvidence()?.textContent).toBe(words.noEvidence);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await addPiece('지어낸 페이지 없는 조각', null);
    expect(noEvidence()).toBeNull();
    // 더한 조각을 지우면(조각 0) 다시 나온다
    const added = () =>
      within(evidence())
        .getByTestId('chips')
        .querySelector('[data-added="0"]') as HTMLElement;
    await click(within(added()).getByRole('button', { name: say.remove }));
    expect(noEvidence()?.textContent).toBe(words.noEvidence);
    await addPiece('지어낸 페이지 없는 조각', null);
    expect(noEvidence()).toBeNull();
    await leaveEvidence();
    await click(rejudgeButton());
    await tick();
    expect(within(detail()).getByTestId('rejudge-judged')).toBeTruthy();
    // 기준 판단(재판단)의 근거 페이지는 [](페이지 없는 조각뿐) — 머리 「참고한 근거 페이지」도 없다
    expect(within(detail()).queryByTestId('detail-evidence-pages')).toBeNull();
    expect(
      within(evidence()).getByTestId('chips').querySelector('[data-added]')
        ?.textContent,
    ).toContain('지어낸 페이지 없는 조각');
    expect(noEvidence()).toBeNull();
  });

  it('N4 목록 꼬리 「근거 없음」도 같은 조각 기준: 칩이나 저장된 더한 조각이 있으면 페이지 0 이어도 없다, 둘 다 0 이면 붙는다', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const NONE = '근거 없음';
    await draw(noPagesServer([0, 1, 2]));
    // 문장 0: 페이지 0 · 칩 둘 → 없음 / 문장 1·2: 페이지 0 · 칩 0 · 더한 0 → 붙음
    expect(rows()[0]!.textContent).not.toContain(NONE);
    expect(rows()[1]!.textContent).toContain(NONE);
    expect(rows()[2]!.textContent).toContain(NONE);
    // 문장 1 에 페이지 없는 조각을 더해 저장하면 빠진다(목록은 저장 값으로 센다)
    await click(rows()[1]!);
    await click(within(evidence()).getByTestId('evidence-edit'));
    await addPiece('지어낸 목록 조각', null);
    await leaveEvidence();
    expect(rows()[1]!.textContent).not.toContain(NONE);
    expect(rows()[2]!.textContent).toContain(NONE);
    // 재판단이 끝나 기준 판단 페이지가 [] 여도 없다
    await click(rejudgeButton());
    await tick();
    expect(within(detail()).getByTestId('rejudge-judged')).toBeTruthy();
    expect(rows()[1]!.textContent).not.toContain(NONE);
  });
});
