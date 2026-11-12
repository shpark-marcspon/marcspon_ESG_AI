// @vitest-environment jsdom
// 밴드 GW1R ③(발주서 §3 C — GW-04·05 검토): 진짜 실어댑터 + 거르지 않는 가짜 서버(서버 규칙: 표시 → in_review, 확정 → 미검토 채택·confirmedBy).
//   채택 → PUT(marks 전부 오름차순, state 없음) · [확정] → 05b → 확정 전 GET → PUT state confirmed·marks 셋 → 잠금 띠 「확정자 가」
//   확정 전 GET 이 다름 → PUT 0 · 「다른 창에서 …」 + [새로 불러오기] → 화면이 서버 값 · 확정 PUT 409 REVIEW_LOCKED → 확정 화면 + 회색 「이미 확정된 점검이에요」
//   확정 PUT 409 RUN_NOT_DONE → 그 글 · 서버가 in_review·marks [] 면 in_review 그대로(ISSUE-220 (3)) · dry-run 실행은 dry-run 안내(ISSUE-121 (a))
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
  fakeDocument,
  fakeGreenwashServer,
  fakeResult,
  fakeRun,
  fakeSteps,
  refusal,
  serverStoreOf,
} from '../../../entities/greenwash/api/testing.ts';
import type { FakeGreenwashServer } from '../../../entities/greenwash/api/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { ReviewScreen } from './ReviewScreen.tsx';

afterEach(cleanup);

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
const review = GW_TEXT.review;
const CONFIRMER = { id: 9, name: '확정자 가' };
const neverOpen: OpenPdf = () => new Promise(() => {});

/** 끝난 실행 12(문장 셋, 검토 pending). 지금 사용자 = 확정자 가. */
function doneServer() {
  const server = fakeGreenwashServer({
    currentUser: CONFIRMER,
    documents: [fakeDocument(3)],
    runs: [fakeRun(12, 3, { status: 'processing', steps: fakeSteps(2) })],
  });
  server.advance(12, { status: 'done' });
  return server;
}

async function draw(
  server: FakeGreenwashServer,
  { initialConfirm = false } = {},
) {
  const { store } = serverStoreOf(server);
  await act(async () => {
    render(
      <ReviewScreen
        store={store}
        openPdf={neverOpen}
        runId="12"
        initialConfirm={initialConfirm}
        onBack={vi.fn()}
        onList={vi.fn()}
      />,
    );
  });
  await screen.findByTestId('review-detail');
}

const reviewPuts = (server: FakeGreenwashServer) =>
  server.calls.filter(
    (call) =>
      call.method === 'PUT' && call.path === '/greenwash/runs/12/review',
  );
const reviewGets = (server: FakeGreenwashServer) =>
  server.count('GET /greenwash/runs/12/review');
const state = () =>
  screen.getByTestId('review-state').getAttribute('data-state');

const choice = (name: string) =>
  within(
    within(screen.getByTestId('review-detail')).getByRole('group', {
      name: review.groupLabel,
    }),
  ).getByRole('button', { name });
const rows = () =>
  within(screen.getByTestId('sentence-list')).getAllByRole('button');

async function adoptRow(index: number) {
  await act(async () => {
    fireEvent.click(rows()[index]!);
  });
  await act(async () => {
    fireEvent.click(choice(review.adopted));
  });
  await act(async () => {});
}

async function confirmIn05b() {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: words.confirm }));
  });
  const dialog = screen.getByRole('dialog', { name: GW_TEXT.confirm.title });
  await act(async () => {
    fireEvent.click(
      within(dialog).getByRole('button', { name: GW_TEXT.confirm.submit }),
    );
  });
  await act(async () => {});
  await act(async () => {});
}

describe('GW-05 실어댑터(밴드 GW1R ③ §3 C)', () => {
  it('채택 → PUT 본문은 marks 전부(오름차순)·state 없음, 서버 답의 in_review 를 그린다', async () => {
    const server = doneServer();
    await draw(server);
    expect(state()).toBe('pending');
    await adoptRow(2);
    await adoptRow(0);
    const puts = reviewPuts(server);
    expect(puts.map((call) => call.body)).toEqual([
      { marks: [{ itemIndex: 2, decision: 'adopted', excludeReason: null }] },
      {
        marks: [
          { itemIndex: 0, decision: 'adopted', excludeReason: null },
          { itemIndex: 2, decision: 'adopted', excludeReason: null },
        ],
      },
    ]);
    expect(state()).toBe('in_review');
  });

  it('[확정] → 05b → 확정 전 GET → PUT state confirmed·marks 셋 → 잠금 띠 「확정자 가」', async () => {
    const server = doneServer();
    await draw(server);
    await adoptRow(1);
    const getsBefore = reviewGets(server);
    await confirmIn05b();
    expect(reviewGets(server)).toBe(getsBefore + 1);
    const keys = server.calls
      .slice(-2)
      .map((call) => `${call.method} ${call.path}`);
    expect(keys).toEqual([
      'GET /greenwash/runs/12/review',
      'PUT /greenwash/runs/12/review',
    ]);
    expect(reviewPuts(server).at(-1)!.body).toEqual({
      state: 'confirmed',
      marks: [0, 1, 2].map((itemIndex) => ({
        itemIndex,
        decision: 'adopted',
        excludeReason: null,
      })),
    });
    expect(state()).toBe('confirmed');
    const banner = document.querySelector('[data-lock-banner]')!;
    expect(banner.textContent).toContain(CONFIRMER.name);
    expect(screen.queryByTestId('save-error')).toBeNull();
  });

  it('확정 전 GET 이 다르면 PUT 0 · 「다른 창에서 …」 + [새로 불러오기] → 화면이 서버 값', async () => {
    const server = doneServer();
    await draw(server);
    // 다른 창에서 표시를 바꿨다(서버 검토만 바뀜)
    server.runs.get(12)!.review = {
      state: 'in_review',
      marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
      confirmedAt: null,
      confirmedBy: null,
    };
    expect(state()).toBe('pending');
    await confirmIn05b();
    expect(reviewPuts(server)).toEqual([]);
    // 줄은 05b 모달 안(228 S3 — 밴드 GW2R ②): 모달은 열린 채, 잠금 안내 자리에 오류 줄 + [새로 불러오기], [확정]은 막힘
    const dialog = screen.getByRole('dialog');
    const line = within(dialog).getByTestId('confirm-blocked');
    expect(line.getAttribute('role')).toBe('alert');
    expect(line.textContent).toBe(words.saveStale);
    expect(words.saveStale).toBe(
      '다른 창에서 검토 내용이 바뀌었어요. 새로 불러온 뒤 다시 확정해 주세요.',
    );
    expect(
      (
        within(dialog).getByRole('button', {
          name: GW_TEXT.confirm.submit,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(screen.queryByTestId('save-error')).toBeNull();
    const gets = reviewGets(server);
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole('button', { name: words.reload }),
      );
    });
    await act(async () => {});
    expect(reviewGets(server)).toBe(gets + 1);
    expect(state()).toBe('in_review');
    expect(screen.queryByTestId('confirm-blocked')).toBeNull();
    expect(screen.queryByTestId('save-error')).toBeNull();
    expect(reviewPuts(server)).toEqual([]);
  });

  it('확정 PUT 409 REVIEW_LOCKED → 다시 읽어 확정 화면(잠금 띠) — 「이미 확정된 점검이에요」 줄은 겹치므로 없음(S4), 오류 줄 아님', async () => {
    const server = doneServer();
    await draw(server);
    // 확정 전 GET 과 PUT 사이에 다른 사람이 확정했다
    server.override['PUT /greenwash/runs/12/review'] = () => {
      server.runs.get(12)!.review = {
        state: 'confirmed',
        marks: [0, 1, 2].map((itemIndex) => ({
          itemIndex,
          decision: 'adopted',
          excludeReason: null,
        })),
        confirmedAt: '2026-10-19T09:00:00+09:00',
        confirmedBy: { id: 8, name: '다른 사람' },
      };
      return refusal(409, 'REVIEW_LOCKED');
    };
    await confirmIn05b();
    expect(state()).toBe('confirmed');
    // 잠금 띠가 보이므로 「이미 확정된 점검이에요」 줄은 그리지 않는다(228 S4 · 디자인 답 D5 — 밴드 GW2R ②). 오류 줄도 아니다
    expect(screen.queryByTestId('save-info')).toBeNull();
    expect(words.alreadyConfirmed).toBe('이미 확정된 점검이에요');
    expect(document.body.textContent).not.toContain(words.alreadyConfirmed);
    expect(screen.queryByTestId('save-error')).toBeNull();
    expect(document.querySelector('[data-lock-banner]')!.textContent).toContain(
      '다른 사람',
    );
  });

  it('확정 PUT 409 RUN_NOT_DONE → 「분석이 아직 끝나지 않아 …」', async () => {
    const server = doneServer();
    await draw(server);
    server.override['PUT /greenwash/runs/12/review'] = () =>
      refusal(409, 'RUN_NOT_DONE');
    await confirmIn05b();
    expect(screen.getByTestId('save-error').textContent).toBe(
      words.saveRunNotDone,
    );
    expect(state()).toBe('pending');
  });

  it('끝나지 않은 실행: 결과 GET 409 RUN_NOT_DONE 은 「결과를 찾을 수 없어요」(없음 꼴 — 실패 꼴이 아니다, Q12)', async () => {
    const server = fakeGreenwashServer({
      documents: [fakeDocument(3)],
      runs: [fakeRun(12, 3, { status: 'processing', steps: fakeSteps(2) })],
    });
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
    const box = await screen.findByTestId('load-failure');
    expect(box.getAttribute('data-kind')).toBe('missing');
    expect(box.textContent).toContain(words.missing.result);
    expect(server.count('GET /greenwash/runs/12/result')).toBeGreaterThan(0);
  });

  it('서버가 in_review·marks [] 를 주면 in_review 를 그대로 그린다(ISSUE-220 (3) — 표시 수로 다시 짓지 않는다)', async () => {
    const server = doneServer();
    server.runs.get(12)!.review = {
      state: 'in_review',
      marks: [],
      confirmedAt: null,
      confirmedBy: null,
    };
    await draw(server);
    expect(state()).toBe('in_review');
  });
});

describe('GW-05 확정 못 박기(밴드 GW1R ④ — 검증 권고 R6~R9)', () => {
  it('[R6] 05b [확정]을 잇달아 두 번 눌러도 확정 전 GET·PUT 은 한 번씩', async () => {
    const server = doneServer();
    await draw(server);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.confirm }));
    });
    const dialog = screen.getByRole('dialog', { name: GW_TEXT.confirm.title });
    const submit = within(dialog).getByRole('button', {
      name: GW_TEXT.confirm.submit,
    });
    const gets = reviewGets(server);
    await act(async () => {
      fireEvent.click(submit);
      fireEvent.click(submit);
    });
    await act(async () => {});
    await act(async () => {});
    expect(reviewGets(server)).toBe(gets + 1);
    expect(reviewPuts(server)).toHaveLength(1);
    expect(state()).toBe('confirmed');
  });

  it('[R7] 확정 PUT 409 REVIEW_LOCKED 의 정보 줄은 회색 꼴(data-tone default) — 오류 꼴이 아니다', async () => {
    const server = doneServer();
    await draw(server);
    server.override['PUT /greenwash/runs/12/review'] = () => {
      server.runs.get(12)!.review = {
        state: 'confirmed',
        marks: [0, 1, 2].map((itemIndex) => ({
          itemIndex,
          decision: 'adopted',
          excludeReason: null,
        })),
        confirmedAt: '2026-10-19T09:00:00+09:00',
        confirmedBy: { id: 8, name: '다른 사람' },
      };
      return refusal(409, 'REVIEW_LOCKED');
    };
    await confirmIn05b();
    // 잠금 띠가 보이면 정보 줄은 없다(228 S4 · D5 — 밴드 GW2R ②). 오류 꼴도 없다
    expect(screen.queryByTestId('save-info')).toBeNull();
    expect(document.querySelector('[data-lock-banner]')).not.toBeNull();
    expect(document.querySelector('[data-tone="error"]')).toBeNull();
  });

  it('[R8] 확정 전 GET 이 이미 confirmed 면 PUT 0 · 확정 화면 + 회색 「이미 확정된 점검이에요」', async () => {
    const server = doneServer();
    await draw(server);
    server.runs.get(12)!.review = {
      state: 'confirmed',
      marks: [0, 1, 2].map((itemIndex) => ({
        itemIndex,
        decision: 'adopted',
        excludeReason: null,
      })),
      confirmedAt: '2026-10-19T09:00:00+09:00',
      confirmedBy: { id: 8, name: '다른 사람' },
    };
    await confirmIn05b();
    expect(reviewPuts(server)).toEqual([]);
    expect(state()).toBe('confirmed');
    // 잠금 띠가 보이면 「이미 확정된 점검이에요」 줄은 없다(228 S4 · D5 — 밴드 GW2R ②)
    expect(screen.queryByTestId('save-info')).toBeNull();
    expect(document.querySelector('[data-lock-banner]')).not.toBeNull();
    expect(screen.queryByTestId('save-error')).toBeNull();
  });

  it('[R9] 확정 전 GET 의 marks 가 같은 수라도 결정이 다르면 PUT 0 · stale', async () => {
    const server = doneServer();
    await draw(server);
    await adoptRow(0);
    expect(reviewPuts(server)).toHaveLength(1);
    // 다른 창에서 같은 문장을 제외로 바꿨다(표시 수는 1 그대로)
    server.runs.get(12)!.review = {
      state: 'in_review',
      marks: [
        { itemIndex: 0, decision: 'excluded', excludeReason: '기타: 지어낸' },
      ],
      confirmedAt: null,
      confirmedBy: null,
    };
    await confirmIn05b();
    expect(reviewPuts(server)).toHaveLength(1);
    // stale 줄은 05b 모달 안(228 S3 — 밴드 GW2R ②)
    expect(
      within(screen.getByRole('dialog')).getByTestId('confirm-blocked')
        .textContent,
    ).toBe(words.saveStale);
  });
});

describe('GW-05 [새로 불러오기] 차례(밴드 GW1R ⑤ M1)', () => {
  it('[새로 불러오기] GET 을 붙잡은 채 표시를 저장하고 GET 을 놓으면, 늦은 답이 저장된 표시를 덮지 않는다', async () => {
    const server = doneServer();
    await draw(server);
    // 다른 창: 1번 문장 채택 → 확정 시도는 stale
    const other = {
      state: 'in_review' as const,
      marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
      confirmedAt: null,
      confirmedBy: null,
    };
    server.runs.get(12)!.review = { ...other, marks: [...other.marks] };
    await confirmIn05b();
    // stale 줄은 05b 모달 안(228 S3 — 밴드 GW2R ②)
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByTestId('confirm-blocked').textContent).toBe(
      words.saveStale,
    );
    // [새로 불러오기] 의 GET 을 붙잡는다(그때의 서버 값 — 1번만)
    let release: (() => void) | null = null;
    server.override['GET /greenwash/runs/12/review'] = [
      () =>
        new Promise<Response>((resolve) => {
          release = () =>
            resolve(
              new Response(
                JSON.stringify({
                  schemaVersion: 'greenwash.review@3',
                  evidence: [],
                  rejudges: [],
                  runId: 12,
                  edits: [],
                  ...other,
                }),
                {
                  status: 200,
                  headers: { 'Content-Type': 'application/json' },
                },
              ),
            );
        }),
    ];
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole('button', { name: words.reload }),
      );
    });
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole('button', { name: GW_TEXT.confirm.cancel }),
      );
    });
    // 모달을 닫고(취소) 붙잡힌 사이 2번 문장을 채택 → PUT 이 받아들여진다(서버는 marks 를 갈아 끼움)
    await adoptRow(2);
    expect(reviewPuts(server).at(-1)!.body).toEqual({
      marks: [{ itemIndex: 2, decision: 'adopted', excludeReason: null }],
    });
    const adoptedShown = () =>
      within(rows()[2]!).queryByText(review.adopted) !== null;
    expect(adoptedShown()).toBe(true);
    await act(async () => {
      release!();
    });
    await act(async () => {});
    // 늦은 GET(1번만 채택)이 화면을 덮지 않는다 — 2번 채택이 남는다
    expect(adoptedShown()).toBe(true);
  });
});

describe('GW-05 dry-run 실행(ISSUE-121 (a) — 실어댑터의 409 NO_REVIEW)', () => {
  it('결과가 dry-run 이고 검토 GET 이 409 NO_REVIEW 면 dry-run 안내(없음·실패 꼴이 아니다)', async () => {
    const tally = {
      requests: 0,
      inputChars: 0,
      inputTokens: { status: 'measured', encoding: 'x', value: 0 },
    };
    const kinds = { detect: tally, eval: tally, lowOnly: tally, repair: tally };
    const parts = { ceo: [1], company: [], climate: [] };
    const server = fakeGreenwashServer({
      documents: [fakeDocument(3)],
      runs: [
        fakeRun(12, 3, {
          status: 'done',
          steps: fakeSteps(6),
          dryRun: true,
          options: { parts },
          result: {
            ...fakeResult('지어낸.pdf', 3, parts),
            items: [],
            candidateStats: null,
            counts: null,
            report: null,
            dryRun: {
              pagesChecked: 1,
              pagesWithText: 1,
              pagesTruncated: 0,
              chunks: 1,
              embeddingIndex: tally,
              ruleCandidates: 0,
              lower: {
                chat: tally,
                chatByKind: kinds,
                embeddingQueries: tally,
                judged: 0,
              },
              upper: {
                chat: tally,
                chatByKind: kinds,
                embeddingQueries: tally,
                outputTokensMax: 0,
                evidenceChars: 0,
                evidenceCapReached: false,
              },
              perPage: [],
            },
          } as never,
        }),
      ],
    });
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
    const info = await screen.findByTestId('dry-run');
    expect(info.textContent).toBe(GW_TEXT.result.dryRun);
    expect(server.count('GET /greenwash/runs/12/review')).toBeGreaterThan(0);
    expect(screen.queryByTestId('load-failure')).toBeNull();
  });
});

describe('GW-05 자동 저장 표시·[새로 불러오기] 실패(밴드 GW2R ② — Q6·D2, sid:MARC-ISSUE-227 ②)', () => {
  afterEach(() => vi.useRealTimers());

  const tally = () => screen.getByTestId('review-tally').textContent;

  it('저장 전에는 토막 없음 → 채택 PUT 이 받아들여지면 「 · 자동 저장됨 14:31」(한국 시각) → PUT 500 이면 토막 그대로(시각이 흘러도)', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-10-19T05:31:20Z'));
    const server = doneServer();
    await draw(server);
    expect(tally()).toBe(words.tally(0, 0, 3));
    await adoptRow(0);
    expect(tally()).toBe('채택 1 · 제외 0 · 미검토 2 · 자동 저장됨 14:31');
    // 저장 실패는 시각을 바꾸지 않는다(P16)
    vi.setSystemTime(new Date('2026-10-19T05:40:00Z'));
    server.override['PUT /greenwash/runs/12/review'] = () =>
      refusal(500, 'INTERNAL_SERVER_ERROR');
    await adoptRow(1);
    expect(screen.getByTestId('save-error').textContent).toBe(
      words.saveRejected,
    );
    expect(tally()).toBe('채택 1 · 제외 0 · 미검토 2 · 자동 저장됨 14:31');
  });

  it('확정된 검토는 토막 없음(확정 PUT 이 받아들여진 뒤에도)', async () => {
    const server = doneServer();
    await draw(server);
    await adoptRow(0);
    expect(tally()).toMatch(/자동 저장됨 \d\d:\d\d$/);
    await confirmIn05b();
    expect(state()).toBe('confirmed');
    expect(tally()).not.toContain('자동 저장됨');
  });

  it('stale → [새로 불러오기] GET 500 → 보던 검토 그대로(화면 전체 실패 아님), 모달 안 글만 「새로 불러오지 못했어요. …」, [새로 불러오기] 남고 [확정] 막힘 → 다시 누르면 받아 막힘 풂', async () => {
    const server = doneServer();
    await draw(server);
    await adoptRow(0);
    server.runs.get(12)!.review = {
      state: 'in_review',
      marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
      confirmedAt: null,
      confirmedBy: null,
    };
    await confirmIn05b();
    const dialog = screen.getByRole('dialog');
    server.override['GET /greenwash/runs/12/review'] = [
      () => refusal(500, 'INTERNAL_SERVER_ERROR'),
    ];
    // 모달이 열려 뒤는 보조기기에서 숨는다(aria-hidden) — 줄 글은 DOM 으로 읽는다
    const shownRows = () =>
      [...screen.getByTestId('sentence-list').querySelectorAll('button')].map(
        (row) => row.textContent,
      );
    const shownBefore = shownRows();
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole('button', { name: words.reload }),
      );
    });
    await act(async () => {});
    const line = within(dialog).getByTestId('confirm-blocked');
    expect(line.textContent).toBe(words.reloadFailed);
    expect(words.reloadFailed).toBe(
      '새로 불러오지 못했어요. 잠시 뒤 다시 눌러 주세요.',
    );
    expect(line.getAttribute('role')).toBe('alert');
    expect(
      within(dialog).getByRole('button', { name: words.reload }),
    ).toBeTruthy();
    expect(
      (
        within(dialog).getByRole('button', {
          name: GW_TEXT.confirm.submit,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    // 화면 전체가 「불러오지 못함」으로 바뀌지 않았다 — 보던 검토(내 채택 0번) 그대로
    expect(screen.queryByTestId('load-failure')).toBeNull();
    expect(screen.getByTestId('review-detail')).toBeTruthy();
    expect(shownRows()).toEqual(shownBefore);
    expect(reviewPuts(server)).toHaveLength(1);
    // 다시 누르면(이번엔 서버 답) 받아서 서버 값으로, 막힘이 풀린다
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole('button', { name: words.reload }),
      );
    });
    await act(async () => {});
    expect(screen.queryByTestId('confirm-blocked')).toBeNull();
    expect(
      (
        within(screen.getByRole('dialog')).getByRole('button', {
          name: GW_TEXT.confirm.submit,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  });
});

describe('GW-05c [내려받기] → 받기 모달 「점검 결과 엑셀 · 확정본」(밴드 GW2R ③ Q9 → GDL1)', () => {
  it('확정 뒤 모달의 엑셀 줄을 누르면 GET /greenwash/runs/12/report?confirmed=true 한 번 → 확정본 이름으로 내려받는다, [닫기] 뒤 초점은 [내려받기]', async () => {
    const names: string[] = [];
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        names.push(this.download);
      });
    const server = doneServer();
    await draw(server);
    await confirmIn05b();
    expect(state()).toBe('confirmed');
    const opener = screen.getByTestId('gw-downloads');
    fireEvent.click(opener);
    const dialog = screen.getByTestId('gw-download-dialog');
    const excel = screen.getByTestId('gw-download-dialog-file-excel');
    expect(excel.textContent).toBe(GW_TEXT.downloads.excelConfirmed);
    expect(dialog.querySelector('[data-file="excel"]')!.textContent).toContain(
      GW_TEXT.downloads.excelNote,
    );
    expect(excel.getAttribute('aria-disabled')).toBeNull();
    await act(async () => {
      fireEvent.click(excel);
    });
    await act(async () => {});
    const reports = server.calls.filter(
      (call) => call.path === '/greenwash/runs/12/report',
    );
    expect(reports.map((call) => call.query.toString())).toEqual([
      'confirmed=true',
    ]);
    expect(names).toEqual(['지어낸 보고서 12 확정본.xlsx']);
    click.mockRestore();
    fireEvent.click(
      within(dialog).getByRole('button', { name: GW_TEXT.downloads.close }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('gw-download-dialog')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});
