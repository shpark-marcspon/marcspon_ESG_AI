// @vitest-environment jsdom
// 밴드 GW2R ③(발주서 §3 C — GW-04 [엑셀 내보내기]) → 밴드 GDL1(머리 [내려받기] → 받기 모달의 엑셀 줄): 진짜 실어댑터 + 거르지 않는 가짜 서버.
//   확정 전 → GET …/report 쿼리 없음 한 번(두 번 눌러도) → 이 탭에서 내려받기(object URL + <a download> 이름 = Content-Disposition) ·
//   확정 → ?confirmed=true · 500 → 그 줄 아래 role="alert" 글 · dry-run → 줄 꺼짐, 눌러도 요청 0. 자료는 모두 지어낸 것이다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  FAKE_CONFIRMER,
  fakeDocument,
  fakeGreenwashServer,
  fakeRun,
  fakeSteps,
  refusal,
  serverStoreOf,
} from '../../../entities/greenwash/api/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import { ResultScreen } from './ResultScreen.tsx';

const words = GW_TEXT.result;
const REPORT = 'GET /greenwash/runs/12/report';

/** 내려받기 흔적: object URL 의 Blob 과 <a download> 이름. */
let saved: { name: string; href: string }[] = [];
let blobs: Blob[] = [];

beforeEach(() => {
  saved = [];
  blobs = [];
  URL.createObjectURL = vi.fn((blob: Blob) => {
    blobs.push(blob);
    return `blob:지어낸-${blobs.length}`;
  });
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    saved.push({ name: this.download, href: this.href });
  });
});
// 바꾼 전역을 시험마다 되돌린다(검증 권고 R7)
const { createObjectURL, revokeObjectURL } = URL;
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  URL.createObjectURL = createObjectURL;
  URL.revokeObjectURL = revokeObjectURL;
});

function doneServer({ dryRun = false, confirmed = false } = {}) {
  const server = fakeGreenwashServer({
    documents: [fakeDocument(3)],
    runs: [
      fakeRun(12, 3, { status: 'processing', steps: fakeSteps(2), dryRun }),
    ],
  });
  server.advance(12, { status: 'done' });
  if (confirmed)
    server.runs.get(12)!.review = {
      state: 'confirmed',
      marks: [0, 1, 2].map((itemIndex) => ({
        itemIndex,
        decision: 'adopted',
        excludeReason: null,
      })),
      confirmedAt: '2026-10-19T10:00:00+09:00',
      confirmedBy: FAKE_CONFIRMER,
    };
  return server;
}

async function draw(
  server: ReturnType<typeof fakeGreenwashServer>,
  ready?: () => Promise<unknown>,
) {
  const { store } = serverStoreOf(server);
  render(
    <ResultScreen
      store={store}
      runId="12"
      onBack={() => {}}
      onReview={() => {}}
      onConfirm={() => {}}
    />,
  );
  // 머리 [내려받기] → 받기 모달의 엑셀 줄 단추(밴드 GDL1 — 옛 [엑셀 내보내기]). ready 를 기다린 뒤 연다
  const opener = await screen.findByTestId('gw-downloads');
  await ready?.();
  fireEvent.click(opener);
  return screen.getByTestId('gw-download-dialog-file-excel');
}
const problem = () => screen.queryByTestId('gw-download-dialog-problem-excel');

describe('GW-04 [내려받기] 받기 모달 엑셀 줄 실어댑터(밴드 GW2R ③ → GDL1)', () => {
  it('확정 전: 두 번 눌러도 GET 쿼리 없음 한 번 → 받은 Blob 을 Content-Disposition 이름으로 내려받는다', async () => {
    const server = doneServer();
    const excel = await draw(server, () => screen.findByTestId('review-state'));
    await act(async () => {
      fireEvent.click(excel);
      fireEvent.click(excel);
    });
    await act(async () => {});
    expect(server.count(REPORT)).toBe(1);
    const call = server.calls.find((c) => `${c.method} ${c.path}` === REPORT)!;
    expect(call.query.toString()).toBe('');
    expect(saved.map((s) => s.name)).toEqual(['지어낸 보고서 12.xlsx']);
    // <a href> 는 이 탭이 만든 object URL(받은 Blob)
    expect(decodeURIComponent(saved[0]!.href)).toBe('blob:지어낸-1');
    expect(new Uint8Array(await blobs[0]!.arrayBuffer())).toEqual(
      new Uint8Array([80, 75, 3, 4, 1, 2, 3]),
    );
    expect(problem()).toBeNull();
  });

  it('확정된 실행: ?confirmed=true', async () => {
    const server = doneServer({ confirmed: true });
    // 모달이 열리면 바깥은 aria-hidden 이라 [결과 보기](확정 읽음)를 먼저 기다린 뒤 연다
    const excel = await draw(server, () =>
      screen.findByRole('button', { name: words.viewResult }),
    );
    await act(async () => {
      fireEvent.click(excel);
    });
    await act(async () => {});
    const call = server.calls.find((c) => `${c.method} ${c.path}` === REPORT)!;
    expect(call.query.toString()).toBe('confirmed=true');
    expect(saved.map((s) => s.name)).toEqual(['지어낸 보고서 12 확정본.xlsx']);
  });

  it('GET 500 → 그 줄 아래 role="alert" 「엑셀을 내려받지 못했어요. 잠시 뒤 다시 눌러 주세요.」, 내려받기 0 → 다시 누르면 받는다', async () => {
    const server = doneServer();
    server.override[REPORT] = [() => refusal(500, 'INTERNAL_SERVER_ERROR')];
    const excel = await draw(server);
    await act(async () => {
      fireEvent.click(excel);
    });
    await act(async () => {});
    const error = problem()!;
    expect(error.getAttribute('role')).toBe('alert');
    expect(error.textContent).toBe(
      '엑셀을 내려받지 못했어요. 잠시 뒤 다시 눌러 주세요.',
    );
    expect(saved).toEqual([]);
    await act(async () => {
      fireEvent.click(excel);
    });
    await act(async () => {});
    expect(server.count(REPORT)).toBe(2);
    expect(saved).toHaveLength(1);
    expect(problem()).toBeNull();
  });

  it('dry-run 결과: 머리 [내려받기]는 켜고 모달의 엑셀 줄이 꺼진 꼴, 눌러도 요청 0', async () => {
    const server = doneServer({ dryRun: true });
    server.override['GET /greenwash/runs/12/result'] = () =>
      new Response(
        JSON.stringify({
          ...server.runs.get(12)!.result,
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
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    const excel = await draw(server, () => screen.findByTestId('dry-run'));
    expect(
      screen.getByTestId('gw-downloads').getAttribute('aria-disabled'),
    ).toBeNull();
    expect(excel.getAttribute('aria-disabled')).toBe('true');
    await act(async () => {
      fireEvent.click(excel);
    });
    await act(async () => {});
    expect(server.count(REPORT)).toBe(0);
    expect(saved).toEqual([]);
  });
});

const tally = {
  requests: 0,
  inputChars: 0,
  inputTokens: { status: 'measured', encoding: 'x', value: 0 },
};
const kinds = { detect: tally, eval: tally, lowOnly: tally, repair: tally };
