// @vitest-environment jsdom
// IR-03 처리 상태 화면 시험(밴드 IRW1 ② — 발주서 §3-2 8). 저장소는 가짜 중대성평가 서버를 앞에 둔 실어댑터(목 0), 폴링 간격은 짧게.
//   상태 넷(queued·processing·done·failed) · 정하지 못함 안내 · [다시 실행] 한 번(options 그대로) · 거절 글 · 폴링 실패·모르는 단계·없음 ·
//   진행 수 0 · 서버 message·errorMessage 는 화면에 0 · 첫 불러오기 제목 막대.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  FAKE_STARTED_AT,
  doneRun,
  fakeMaterialityServer,
  fakeRun,
  fakeSteps,
  refusal,
  serverStoreOf,
} from '../../../entities/materiality/api/testing.ts';
import type {
  FakeMaterialityServer,
  FakeRun,
} from '../../../entities/materiality/api/testing.ts';
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import {
  FAKE_COMPANY,
  failed,
  fakeResult,
  notRun,
  subtopic,
} from '../../../entities/materiality/model/testing.ts';
import { StatusScreen } from './StatusScreen.tsx';

afterEach(cleanup);

const words = IR_TEXT.status;
const common = IR_TEXT.common;
const WAIT = { timeout: 3_000 };

function setup(run: FakeRun = fakeRun(7), server?: FakeMaterialityServer) {
  const fake = server ?? fakeMaterialityServer({ runs: [run] });
  const store = serverStoreOf(fake, { pollMs: 5 });
  const props = { onBack: vi.fn(), onViewResult: vi.fn(), onRerun: vi.fn() };
  render(<StatusScreen store={store} runId={String(run.id)} {...props} />);
  return { server: fake, ...props };
}

/** 응답을 붙잡아 두는 서버(첫 불러오기 시험). release() 뒤에야 답한다. */
function held(server: FakeMaterialityServer) {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  return {
    server: {
      ...server,
      send: async (request: Request) => {
        await gate;
        return server.send(request);
      },
    },
    release: () => act(async () => release()),
  };
}

const state = () =>
  document
    .querySelector('[data-screen="materiality-status"]')
    ?.getAttribute('data-run-state');
const lineState = (line: string) =>
  document.querySelector(`[data-line="${line}"]`)?.getAttribute('data-state');
const shown = (text: string) => screen.findByText(text, undefined, WAIT);
const noServerText = () => {
  expect(document.body.textContent).not.toContain('지어낸');
  expect(document.body.textContent).not.toContain('flow_failed');
};
/** 진행 수 0(「4 / 6토픽」·「· 23건」 꼴 — sid:MARC-ISSUE-378). */
const noProgressCount = () =>
  expect(document.body.textContent).not.toMatch(/\d+ \/ \d+|· \d+건/);

describe('IR-03 처리 상태', () => {
  it('queued: 「평가 중이에요」 · 머리 접수·기업명·토픽 수 · 대기 배지 + 차례 글 · 줄 여섯 대기', async () => {
    setup();
    await shown(words.title);
    expect(document.body.textContent).toContain(
      words.queuedLine('2026-10-19 14:00', FAKE_COMPANY, '2'),
    );
    expect(screen.getByTestId('queued').textContent).toContain(words.waiting);
    expect(screen.getByTestId('queued').textContent).toContain(
      IR_TEXT.badge.queued,
    );
    for (const line of [
      'regulation',
      'controversy',
      'impact',
      'financial',
      'pathway',
      'report',
    ])
      expect(lineState(line)).toBe('pending');
    expect(screen.getByTestId('progress-now').textContent).toBe(
      words.lines.regulation.name,
    );
    noProgressCount();
  });

  it('processing: 머리 시작 · 지금 줄 · 판 줄 글 · 진행 수 0', async () => {
    setup(
      fakeRun(7, {
        status: 'processing',
        startedAt: FAKE_STARTED_AT,
        steps: fakeSteps(4, 'running'),
      }),
    );
    await shown(words.title);
    expect(document.body.textContent).toContain(
      words.startedLine('2026-10-19 14:02', FAKE_COMPANY, '2'),
    );
    expect(lineState('regulation')).toBe('done');
    expect(lineState('controversy')).toBe('running');
    expect(lineState('impact')).toBe('pending');
    expect(screen.getByTestId('progress-now').textContent).toBe(
      words.lines.controversy.name,
    );
    expect(screen.getByText(words.lines.controversy.text)).toBeTruthy();
    // d7f723b8 — 재무 영향 경로 줄 글(IRW17)
    expect(
      screen.getByText(
        '원인 → 비즈니스 영향 → 재무 영향에 따라 리스크·기회를 식별해요',
      ),
    ).toBeTruthy();
    expect(document.body.textContent).not.toContain('리스크·기회마다 원인');
    expect(screen.queryByTestId('queued')).toBeNull();
    noProgressCount();
  });

  it('processing(IRW6): 진행 중 줄 끝·머리에 「1 / 2토픽」 · 끝난 줄 수 0 · 「건」 0', async () => {
    setup(
      fakeRun(7, {
        status: 'processing',
        startedAt: FAKE_STARTED_AT,
        steps: fakeSteps(3, 'running', {
          regulation: [2, 2],
          controversy: [1, 2],
        }),
      }),
    );
    await shown(words.title);
    const line = (name: string) =>
      document.querySelector(`[data-line="${name}"]`)!;
    expect(lineState('controversy')).toBe('running');
    expect(line('controversy').textContent).toContain(
      `${words.lines.controversy.text} · 1 / 2토픽`,
    );
    expect(
      line('controversy').querySelector('[data-testid="line-count"]')
        ?.textContent,
    ).toBe('1 / 2토픽');
    expect(screen.getByTestId('progress-now').textContent).toBe(
      '컨트로버시 리서치 1 / 2토픽',
    );
    expect(lineState('regulation')).toBe('done');
    expect(
      line('regulation').querySelector('[data-testid="line-count"]'),
    ).toBeNull();
    expect(screen.getAllByTestId('line-count')).toHaveLength(1);
    expect(document.body.textContent).not.toMatch(/· \d+건/);
  });

  it('processing(IRW6): impact running (3,5) → 「3 / 5서브토픽」', async () => {
    setup(
      fakeRun(7, {
        status: 'processing',
        startedAt: FAKE_STARTED_AT,
        steps: fakeSteps(6, 'running', { impact: [3, 5] }),
      }),
    );
    await shown(words.title);
    expect(lineState('impact')).toBe('running');
    expect(screen.getByTestId('line-count').textContent).toBe('3 / 5서브토픽');
    expect(screen.getByTestId('progress-now').textContent).toBe(
      `${words.lines.impact.name} 3 / 5서브토픽`,
    );
  });

  it('input 을 못 읽으면 기업명·토픽 수 「–」', async () => {
    setup(fakeRun(7, { options: { input: { schemaVersion: 'x' } } }));
    await shown(words.title);
    expect(document.body.textContent).toContain(
      words.queuedLine('2026-10-19 14:00', '–', '–'),
    );
  });

  it('done: 머리 「<기업> · 중대성평가」 · 끝남 줄(영향 수) · [결과 보기](저절로 넘어가지 않음) · 정하지 못함 0 이면 안내 0', async () => {
    const { onViewResult } = setup(doneRun(7));
    await shown(words.doneTitle);
    expect(state()).toBe('done');
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      IR_TEXT.titleOf(FAKE_COMPANY),
    );
    await screen.findByText(
      words.doneLine('2026-10-19 14:39', '3', '3'),
      undefined,
      WAIT,
    );
    // 20be9a06 — 「평가가 끝났어요」는 제목 하나 · 아래 줄의 「끝남」 0(IRW17)
    expect(document.body.textContent!.split('평가가 끝났어요').length - 1).toBe(
      1,
    );
    expect(screen.getByTestId('done-line').textContent).toBe(
      '2026-10-19 14:39 · 환경·사회 영향 3 · 재무 영향 경로 3',
    );
    expect(screen.getByTestId('done').textContent).not.toContain('끝남');
    expect(screen.queryByTestId('undecided')).toBeNull();
    expect(onViewResult).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: common.viewResult }));
    expect(onViewResult).toHaveBeenCalledWith('7');
  });

  it('done + 정하지 못한 서브토픽: important 안내(전체·m)', async () => {
    const result = fakeResult({}, [
      {
        topic: '가상토픽 A',
        description: 'x',
        subtopics: [
          subtopic('서브 가', { impact: failed() }),
          subtopic('서브 나', { financial: notRun(), pathway: notRun() }),
          subtopic('서브 다'),
        ],
      },
    ]);
    setup(doneRun(7, { result }));
    const info = await screen.findByTestId('undecided', undefined, WAIT);
    expect(info.textContent).toBe(words.undecided(3, 2));
    expect(info.getAttribute('data-tone')).toBe('important');
  });

  it('done 인데 결과를 못 읽으면 수 「–」', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    server.override['GET /materiality/runs/7/result'] = () =>
      refusal(500, 'INTERNAL');
    setup(doneRun(7), server);
    await screen.findByText(
      words.doneLine('2026-10-19 14:39', '–', '–'),
      undefined,
      WAIT,
    );
  });

  it('failed: 실패 줄 · error 안내 · [다시 실행] 한 번 → 새 실행(options 그대로) · 서버 글 0', async () => {
    const run = fakeRun(7, {
      status: 'failed',
      startedAt: FAKE_STARTED_AT,
      finishedAt: '2026-10-19T14:10:00+09:00',
      steps: fakeSteps(6, 'failed'),
      errorCode: 'flow_failed',
    });
    const { server, onRerun } = setup(run);
    await shown(common.rerunAgain);
    expect(state()).toBe('failed');
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      IR_TEXT.titleOf(FAKE_COMPANY),
    );
    expect(lineState('impact')).toBe('failed');
    const button = screen.getByRole('button', { name: common.rerun });
    fireEvent.click(button);
    fireEvent.click(button);
    await vi.waitFor(() => expect(onRerun).toHaveBeenCalledWith('30'), WAIT);
    expect(server.posts()).toHaveLength(1);
    expect(server.runs.get(30)!.options).toEqual(run.options);
    noServerText();
  });

  it('[다시 실행] 거절 → 「다시 실행하지 못했어요 …」 · 이동 0', async () => {
    const { server, onRerun } = setup(
      fakeRun(7, { status: 'failed', steps: fakeSteps(1, 'failed') }),
    );
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL');
    fireEvent.click(
      await screen.findByRole('button', { name: common.rerun }, WAIT),
    );
    expect(
      (await screen.findByTestId('rerun-error', undefined, WAIT)).textContent,
    ).toBe(common.rerunFailed);
    expect(onRerun).not.toHaveBeenCalled();
    noServerText();
  });

  it('[목록으로] → onBack', async () => {
    const { onBack } = setup();
    await shown(words.title);
    fireEvent.click(screen.getByRole('button', { name: common.toList }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('폴링 실패 → load-failure + [다시 시도] · 없는 실행 → 「평가를 찾을 수 없어요」', async () => {
    const server = fakeMaterialityServer({ runs: [fakeRun(7)] });
    server.override['GET /runs/7'] = [() => refusal(500, 'INTERNAL')];
    setup(fakeRun(7), server);
    await shown(words.loadFailed);
    fireEvent.click(screen.getByRole('button', { name: common.retry }));
    await shown(words.title);
    cleanup();
    setup(fakeRun(8), fakeMaterialityServer());
    await shown(common.notFound);
  });

  it('모르는 단계 이름 → load-failure', async () => {
    setup(
      fakeRun(7, {
        steps: [
          ...fakeSteps(0),
          { step: 'later_step', status: 'pending', done: null, total: null },
        ],
      }),
    );
    await shown(words.loadFailed);
    expect(state()).toBe('failed_load');
  });

  it('첫 불러오기: 제목 막대(셸 제목 0) · 답 뒤 상태 제목', async () => {
    const { server, release } = held(
      fakeMaterialityServer({ runs: [fakeRun(7)] }),
    );
    setup(fakeRun(7), server as unknown as FakeMaterialityServer);
    expect(state()).toBe('loading');
    expect(
      document
        .querySelector('[data-screen="materiality-status"]')
        ?.getAttribute('aria-busy'),
    ).toBe('true');
    expect(screen.getByRole('heading', { level: 2 }).textContent).not.toBe(
      IR_TEXT.shell.title,
    );
    await release();
    await shown(words.title);
  });
});

describe('IR-03 시안 대조 손질(밴드 IRW1b)', () => {
  const STAY = '이 창을 닫아도 평가는 계속돼요';
  const body = () => document.body.textContent ?? '';

  it('W7 「이 창을 닫아도…」는 queued·processing 에만 — done·failed 머리 줄에는 0', async () => {
    setup();
    await shown(words.title);
    expect(body()).toContain(STAY);
    cleanup();
    setup(
      fakeRun(7, {
        status: 'processing',
        startedAt: FAKE_STARTED_AT,
        steps: fakeSteps(4, 'running'),
      }),
    );
    await shown(words.title);
    expect(body()).toContain(STAY);
    cleanup();
    setup(doneRun(7));
    await shown(words.doneTitle);
    expect(body()).toContain(`${FAKE_COMPANY} · 토픽 2개`);
    expect(body()).not.toContain(STAY);
    cleanup();
    setup(
      fakeRun(7, {
        status: 'failed',
        startedAt: FAKE_STARTED_AT,
        steps: fakeSteps(6, 'failed'),
      }),
    );
    await shown(common.rerunAgain);
    expect(body()).toContain(
      words.startedLine('2026-10-19 14:02', FAKE_COMPANY, '2', false),
    );
    expect(body()).not.toContain(STAY);
  });

  it('J3 지금 단계 점 고리 · 끝난 체크 튀어나옴 · 끝남 카드 떠오름', async () => {
    setup(
      fakeRun(7, {
        status: 'processing',
        startedAt: FAKE_STARTED_AT,
        steps: fakeSteps(4, 'running'),
      }),
    );
    await shown(words.title);
    const dot = (line: string) =>
      document.querySelector(`[data-line="${line}"] > span`)!;
    expect(dot('controversy').className).toContain('gw-m-ring');
    expect(dot('impact').className).not.toContain('gw-m-ring');
    expect(
      dot('regulation').querySelector('svg')!.getAttribute('class'),
    ).toContain('gw-m-pop');
    cleanup();
    setup(doneRun(7));
    await shown(words.doneTitle);
    expect(screen.getByTestId('done').className).toContain('gw-m-rise');
  });
});
