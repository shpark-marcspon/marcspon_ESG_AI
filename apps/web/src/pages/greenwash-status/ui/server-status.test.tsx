// @vitest-environment jsdom
// 밴드 GW1R ②(발주서 §3 C — GW-03): 진짜 실어댑터 + 거르지 않는 가짜 서버.
//   failed no_text_layer → GW-02a 글·[새 점검]·파일 줄 「텍스트 없음」, failureNote·[다시 실행] 없음
//   failed step_error(extract 에서 멈춤 — 같은 단계라도 code 가 다르면 일반 실패) → 일반 실패 글·failureNote·[다시 실행] → 새 실행
//   읽기 500 → 「점검 상태를 불러오지 못했어요」+[다시 시도][목록으로] → [다시 시도] 는 다시 구독
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  fakeDocument,
  fakeGreenwashServer,
  fakeRun,
  fakeSteps,
  refusal,
  serverStoreOf,
} from '../../../entities/greenwash/api/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import { StatusScreen } from './StatusScreen.tsx';

afterEach(cleanup);

const words = GW_TEXT.status;

function failedServer(errorCode: string) {
  return fakeGreenwashServer({
    documents: [fakeDocument(3, { fileName: '지어낸 스캔본.pdf' })],
    runs: [
      fakeRun(12, 3, {
        status: 'failed',
        // 둘 다 extract 에서 멈춘다 — 화면은 단계가 아니라 code 로 가른다
        steps: fakeSteps(0, { status: 'failed' }),
        errorCode,
        startedAt: '2026-10-18T09:00:01+09:00',
      }),
    ],
  });
}

function draw(
  server = failedServer('no_text_layer'),
  { canWrite = true }: { canWrite?: boolean } = {},
) {
  const { store } = serverStoreOf(server);
  const handlers = {
    onBack: vi.fn(),
    onRerun: vi.fn(),
    onNewCheck: vi.fn(),
  };
  render(
    <StatusScreen store={store} runId="12" canWrite={canWrite} {...handlers} />,
  );
  return { server, ...handlers };
}

describe('GW-03 실어댑터(밴드 GW1R ② §3 C)', () => {
  it('failed no_text_layer → GW-02a 글·[새 점검]·「텍스트 없음」 파일 줄, 덧글·[다시 실행] 없음', async () => {
    const { server, onNewCheck } = draw();
    const card = await screen.findByTestId('failure');
    expect(card.getAttribute('data-failure')).toBe('no_text_layer');
    expect(screen.getByTestId('failure-info').textContent).toBe(
      GW_TEXT.newCheck.upload.noText,
    );
    const file = await screen.findByTestId('failure-file');
    // 파일 줄: 이름 + 회색 「총 10페이지 · 텍스트 없음」(228 S2 — 밴드 GW2R ②)
    expect(file.textContent).toBe('지어낸 스캔본.pdf총 10페이지 · 텍스트 없음');
    expect(screen.queryByTestId('failure-note')).toBeNull();
    expect(screen.queryByRole('button', { name: words.rerun })).toBeNull();
    fireEvent.click(
      screen.getByRole('button', { name: words.noText.newCheck }),
    );
    expect(onNewCheck).toHaveBeenCalledTimes(1);
    // 파일 이름은 문서 조회로(실행 응답에 없다)
    expect(server.count('GET /documents/3')).toBe(1);
    expect(server.count('GET /runs/12')).toBe(1);
  });

  it('쓰지 못하는 세션(canWrite 거짓 — 로그인하지 않음)이면 [새 점검] 도 없다 — [목록으로] 만', async () => {
    draw(failedServer('no_text_layer'), { canWrite: false });
    await screen.findByTestId('failure-file');
    expect(
      screen.queryByRole('button', { name: words.noText.newCheck }),
    ).toBeNull();
    expect(
      screen.getAllByRole('button', { name: words.back }).length,
    ).toBeGreaterThan(0);
  });

  it('failed step_error(extract) → 일반 실패 글·덧글 없음·[다시 실행] → GET /runs/12 → POST /runs → 13', async () => {
    const { server, onRerun } = draw(failedServer('step_error'));
    const card = await screen.findByTestId('failure');
    expect(card.getAttribute('data-failure')).toBeNull();
    expect(screen.getByTestId('failure-info').textContent).toBe(words.failure);
    // 덧글(failureNote)은 없다(디자인 답 D4 — 밴드 GW2R ②)
    expect(screen.queryByTestId('failure-note')).toBeNull();
    expect(screen.queryByTestId('failure-file')).toBeNull();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.rerun }));
    });
    await vi.waitFor(() => expect(onRerun).toHaveBeenCalledWith('13'));
    expect(server.calls.at(-1)).toMatchObject({
      method: 'POST',
      path: '/runs',
      body: { module: 'greenwash', documentId: 3 },
    });
  });

  it('읽기 500 → 「점검 상태를 불러오지 못했어요」+[다시 시도][목록으로], [다시 시도] → 다시 구독해 실행을 그린다', async () => {
    const server = failedServer('step_error');
    server.override['GET /runs/12'] = [
      () => refusal(500, 'INTERNAL_SERVER_ERROR'),
    ];
    const { onBack } = draw(server);
    const failure = await screen.findByTestId('load-failure');
    expect(failure.getAttribute('data-kind')).toBe('failed');
    expect(failure.textContent).toContain(words.loadFailed);
    expect(words.loadFailed).toBe('점검 상태를 불러오지 못했어요');
    expect(
      document
        .querySelector('[data-run-state]')
        ?.getAttribute('data-run-state'),
    ).toBe('failed');
    expect(screen.queryByTestId('failure')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.toList }));
    expect(onBack).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    await screen.findByTestId('failure');
    expect(server.count('GET /runs/12')).toBe(2);
    expect(screen.queryByTestId('load-failure')).toBeNull();
  });
});
