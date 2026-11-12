// @vitest-environment jsdom
// RP-04 진행(밴드 RPW1 ② 시험 S5 — 발주서 §2-2·§2-0 ④⑦). 진짜 실어댑터 + 가짜 원고작성 서버(runPatch 로 단계를 옮긴다).
//   진행 줄 셋(extract 수 없음 · map · draft n/m) · 폴링이 done·failed 에서 멈춤 · failed 빨간 띠 + [전체 다시 만들기](base 0) ·
//   base 실행은 진행 카드 0 · 다른 프로젝트의 실행 → 찾지 못함 · 시작 거절 한 줄 · 서버 글 0.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import type { DraftingStore } from '../../../entities/drafting/api/index.ts';
import {
  fakeDraftingServer,
  fakeOutline,
  storeOf,
  unreachable,
} from '../../../entities/drafting/api/testing.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { minuteOf } from '../../../entities/drafting/model/index.ts';
import type { RunStep } from '../../../entities/drafting/model/index.ts';
import { RunScreen } from './RunScreen.tsx';

afterEach(cleanup);

const words = DR_TEXT.run;
const POLL = 15;
const flush = () => act(async () => {});
const sleep = (ms: number) =>
  act(() => new Promise<void>((resolve) => setTimeout(resolve, ms)));

/** 프로젝트 1·2(문서·목차 달림)와 프로젝트 1 의 실행 하나. */
async function seeded(options = {}) {
  const server = fakeDraftingServer({
    projects: [
      { id: 1, name: '지어낸 보고서', year: 2026 },
      { id: 2, name: '지어낸 다른 보고서', year: 2026 },
    ],
    ...options,
  });
  for (const id of [1, 2])
    server.seedProject(id, {
      documentId: server.seedDocument(),
      nodes: fakeOutline(),
    });
  const started = await storeOf(server).startRun({ projectId: 1 }, null);
  const runId = started.kind === 'ok' ? started.value.runId : 0;
  return { server, runId };
}

const steps = (
  extract: RunStep['status'],
  map: RunStep['status'],
  draft: RunStep['status'],
  draftCount: [number, number] | null = null,
): RunStep[] => [
  { step: 'extract', status: extract, done: 2, total: 5 },
  { step: 'map', status: map, done: null, total: null },
  {
    step: 'draft',
    status: draft,
    done: draftCount?.[0] ?? null,
    total: draftCount?.[1] ?? null,
  },
  { step: 'report', status: 'pending', done: null, total: null },
];

function setup(
  server: ReturnType<typeof fakeDraftingServer>,
  runId: number | null,
  projectId: number | null = 1,
  patch: Partial<DraftingStore> = {},
) {
  const onRun = vi.fn();
  const onList = vi.fn();
  const onPickRun = vi.fn();
  render(
    <RunScreen
      store={{
        ...storeOf(server, {
          newKey: () => 'idem-2',
          newLaunchKey: () => 'launch-2',
        }),
        ...patch,
      }}
      projectId={projectId}
      runId={runId}
      operator={false}
      onRun={onRun}
      onPickRun={onPickRun}
      onList={onList}
      openPdf={() =>
        Promise.reject(new Error('시험 — 결과 칸은 ResultView.test'))
      }
      pollMs={POLL}
    />,
  );
  return { onRun, onList, onPickRun };
}

const getRuns = (
  server: ReturnType<typeof fakeDraftingServer>,
  runId: number,
) => server.count(`GET /runs/${runId}`);
const row = (name: string) =>
  document.querySelector<HTMLElement>(`[data-step="${name}"]`)!;

describe('RP-04 진행 — 줄 셋', () => {
  it('extract 「전년도 보고서 읽는 중」(수 없음) · map · draft 「목차 n/m」 · report 줄 없음', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'done', 'running', [4, 8]),
    });
    setup(server, runId);
    await waitFor(() =>
      expect(screen.getByTestId('run-progress')).not.toBeNull(),
    );
    expect(screen.getByTestId('run-heading').textContent).toBe(words.making);
    expect(row('extract').textContent).toContain(words.steps.extract);
    expect(row('extract').textContent).not.toMatch(/\d\/\d/);
    expect(row('map').getAttribute('data-status')).toBe('done');
    expect(row('draft').textContent).toContain(words.stepCount(4, 8));
    expect(row('draft').getAttribute('data-status')).toBe('running');
    expect(document.querySelector('[data-step="report"]')).toBeNull();
  });

  it('map 줄은 서버 셈(묶음)이 값이어도 수·막대 없음 · draft 줄만 「목차 n/m」 + 막대(RPQ1)', async () => {
    const { server, runId } = await seeded();
    const counted = steps('done', 'done', 'running', [2, 3]).map((step) =>
      step.step === 'map' ? { ...step, done: 1, total: 1 } : step,
    );
    server.runPatch(runId, { status: 'processing', steps: counted });
    setup(server, runId);
    await screen.findByTestId('run-progress');
    expect(row('map').querySelector('[data-testid="step-count"]')).toBeNull();
    expect(row('map').querySelector('[role="progressbar"]')).toBeNull();
    expect(row('map').textContent).not.toMatch(/\d\/\d/);
    expect(
      row('draft').querySelector('[data-testid="step-count"]')?.textContent,
    ).toBe(words.stepCount(2, 3));
    expect(row('draft').querySelector('[role="progressbar"]')).not.toBeNull();
  });

  it('폴링 — 읽기 실패 한두 번은 진행 보기 그대로 다시 읽고, 연달아 셋이면 실패 화면 · 첫 읽기 실패는 바로 실패 화면', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('running', 'pending', 'pending'),
    });
    const real = storeOf(server);
    let fails = 0;
    const getRun: DraftingStore['getRun'] = (id) =>
      fails > 0 ?
        (fails--, Promise.resolve({ kind: 'failed' }))
      : real.getRun(id);
    setup(server, runId, 1, { getRun });
    await screen.findByTestId('run-progress');
    fails = 2;
    await waitFor(() => expect(fails).toBe(0));
    await sleep(POLL * 4);
    expect(screen.getByTestId('run-progress')).not.toBeNull();
    expect(screen.queryByText(words.runLoadFailed)).toBeNull();
    fails = 3;
    await screen.findByText(words.runLoadFailed);
    expect(screen.queryByTestId('run-progress')).toBeNull();
    cleanup();
    setup(server, runId, 1, {
      getRun: () => Promise.resolve({ kind: 'failed' }),
    });
    await screen.findByText(words.runLoadFailed);
  });

  it('폴링 — 진행 중엔 다시 읽고, done 에서 멈춤', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('running', 'pending', 'pending'),
    });
    setup(server, runId);
    await waitFor(() => expect(getRuns(server, runId)).toBeGreaterThan(2));
    server.runPatch(runId, {
      status: 'done',
      steps: steps('done', 'done', 'done', [3, 3]),
    });
    // done → 결과 칸(심은 결과가 없어 「찾지 못함」 — 결과 세 칸은 ResultView.test).
    await waitFor(() =>
      expect(screen.getByText(DR_TEXT.result.resultMissing)).not.toBeNull(),
    );
    const seen = getRuns(server, runId);
    await sleep(POLL * 5);
    expect(getRuns(server, runId)).toBe(seen);
  });

  it('failed — 폴링 멈춤 · 빨간 띠(숫자·서버 글 0) · [전체 다시 만들기] = POST /runs {projectId}(base 0) → 새 실행', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'failed',
      steps: steps('done', 'failed', 'pending'),
    });
    const { onRun, onList } = setup(server, runId);
    await waitFor(() =>
      expect(screen.getByTestId('run-failed')).not.toBeNull(),
    );
    const seen = getRuns(server, runId);
    await sleep(POLL * 5);
    expect(getRuns(server, runId)).toBe(seen);
    const band = screen.getByTestId('run-failed');
    expect(band.textContent).toContain(words.failed);
    expect(band.textContent).not.toMatch(/\d/);
    // D#2: 띠 안 단추 0 · 띠 뒤 outline 단추 + 안내 한 줄.
    expect(band.querySelector('button')).toBeNull();
    // 머리 단추 — 목록으로(onOutline 을 안 준 setup) · 눌러 이동.
    fireEvent.click(
      screen.getByRole('button', { name: DR_TEXT.common.toList }),
    );
    expect(onList).toHaveBeenCalledTimes(1);
    const again = screen.getByRole('button', { name: words.restartAll });
    expect(
      band.compareDocumentPosition(again) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(again.className).not.toContain('bg-background-primary-inverse');
    expect(screen.getByTestId('run-failed-hint').textContent).toBe(
      words.failedHint,
    );
    fireEvent.click(again);
    await flush();
    const posts = server.bodies('POST /runs');
    expect(posts.at(-1)).toEqual({
      module: 'drafting',
      launchKey: 'launch-2',
      options: { projectId: 1 },
    });
    expect(onRun).toHaveBeenCalledWith(server.runs().at(-1)!.id);
  });

  it('[전체 다시 만들기] 409 AI_SETTING_UNUSABLE → 시작 거절 한 줄(설정 화면 이름 0)', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, { status: 'failed' });
    const { onRun } = setup(server, runId);
    await waitFor(() =>
      expect(screen.getByTestId('run-failed')).not.toBeNull(),
    );
    server.override['POST /runs'] = () =>
      new Response(
        JSON.stringify({
          error: {
            code: 'AI_SETTING_UNUSABLE',
            message: '지어낸-서버글',
            fields: null,
          },
        }),
        { status: 409, headers: { 'Content-Type': 'application/json' } },
      );
    fireEvent.click(screen.getByRole('button', { name: words.restartAll }));
    await flush();
    expect(screen.getByTestId('start-refused').textContent).toBe(
      DR_TEXT.startRefused,
    );
    expect(document.body.textContent).not.toContain('AI 설정');
    expect(document.body.textContent).not.toContain('지어낸-서버글');
    expect(onRun).not.toHaveBeenCalled();
  });
});

describe('RP-04 진행 — 갈래', () => {
  it('머리 [목차 설정] — 주면 단추, 누르면 onOutline', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, { status: 'failed' });
    const onOutline = vi.fn();
    render(
      <RunScreen
        store={storeOf(server)}
        projectId={1}
        runId={runId}
        operator={false}
        onList={vi.fn()}
        onOutline={onOutline}
        onRun={vi.fn()}
        onPickRun={vi.fn()}
        openPdf={() => Promise.reject(new Error('시험'))}
        pollMs={POLL}
      />,
    );
    fireEvent.click(
      await screen.findByRole('button', { name: words.toOutline }),
    );
    expect(onOutline).toHaveBeenCalledTimes(1);
  });

  it('base 실행 → 진행 카드·머리 0, 앞 결과 자리(RPW2 D#6)', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, { status: 'done' });
    const again = await storeOf(server).startRun(
      {
        projectId: 1,
        base: { runId, rebuild: ['n2'] },
      },
      null,
    );
    const baseRun = again.kind === 'ok' ? again.value.runId : 0;
    server.runPatch(baseRun, {
      status: 'processing',
      steps: steps('done', 'running', 'pending'),
    });
    setup(server, baseRun);
    // 심은 결과가 없어 「찾지 못함」 — 앞 결과 칸은 ResultView.test.
    await screen.findByText(DR_TEXT.result.resultMissing);
    expect(screen.queryByTestId('run-progress')).toBeNull();
    expect(screen.queryByTestId('run-heading')).toBeNull();
  });

  it('다른 프로젝트 주소의 실행 → 찾지 못함 · 없는 실행 404 · 주소 id 틀림(요청 0)', async () => {
    const { server, runId } = await seeded();
    setup(server, runId, 2);
    await waitFor(() =>
      expect(screen.getByText(words.runMissing)).not.toBeNull(),
    );
    cleanup();
    setup(server, 999);
    await waitFor(() =>
      expect(screen.getByText(words.runMissing)).not.toBeNull(),
    );
    cleanup();
    const before = server.calls.length;
    setup(server, null);
    await flush();
    expect(screen.getByText(words.runMissing)).not.toBeNull();
    expect(server.calls.length).toBe(before);
  });
});

describe('RP-04 실행 고르기(경계 ④)', () => {
  /** 프로젝트 1 의 실행 둘(앞 실행 하나 + 새 실행). */
  async function twoRuns() {
    const { server, runId: first } = await seeded();
    const again = await storeOf(server).startRun({ projectId: 1 }, null);
    const second = again.kind === 'ok' ? again.value.runId : 0;
    return { server, first, second };
  }
  const trigger = () => screen.findByRole('button', { name: words.picker });
  const label = (
    server: ReturnType<typeof fakeDraftingServer>,
    runId: number,
    n: number,
    latest: boolean,
  ) => {
    const run = server.runs().find((one) => one.id === runId)!;
    return words.pickerOption(n, minuteOf(run.createdAt), latest);
  };

  it('줄은 새 것 먼저 · 맨 위만 「지금」 · 앞 실행을 고르면 그 실행으로 · 지금 보는 줄을 고르면 가지 않는다', async () => {
    const { server, first, second } = await twoRuns();
    const { onPickRun } = setup(server, second);
    const button = await trigger();
    expect(button.textContent).toBe(label(server, second, 2, true));
    fireEvent.keyDown(button, { key: 'Enter' });
    expect(
      screen.getAllByRole('menuitemradio').map((item) => item.textContent),
    ).toEqual([label(server, second, 2, true), label(server, first, 1, false)]);
    fireEvent.click(
      screen.getByRole('menuitemradio', {
        name: label(server, second, 2, true),
      }),
    );
    expect(onPickRun).not.toHaveBeenCalled();
    fireEvent.keyDown(await trigger(), { key: 'Enter' });
    fireEvent.click(
      screen.getByRole('menuitemradio', {
        name: label(server, first, 1, false),
      }),
    );
    expect(onPickRun).toHaveBeenCalledExactlyOnceWith(first);
    expect(server.count('GET /drafting/projects/1/runs')).toBe(1);
  });

  it('실패한 실행에도 고르기가 있다(앞 실행을 볼 수 있다) · 실행 목록을 못 읽으면 고르기만 숨긴다', async () => {
    const { server, second } = await twoRuns();
    server.runPatch(second, { status: 'failed' });
    setup(server, second);
    await screen.findByTestId('run-failed');
    await trigger();
    cleanup();
    const broken = await seeded();
    broken.server.runPatch(broken.runId, { status: 'failed' });
    setup(broken.server, broken.runId, 1, {
      listRuns: () => Promise.resolve({ kind: 'failed' }),
    });
    await screen.findByTestId('run-failed');
    await flush();
    expect(screen.queryByRole('button', { name: words.picker })).toBeNull();
  });
});

describe('RPW2 ② 진행 꼴 · M5', () => {
  const mark = (name: string) =>
    row(name).querySelector<HTMLElement>('[data-testid="step-mark"]')!;
  const hint = (name: string) =>
    row(name).querySelector('[data-testid="step-hint"]')!.textContent;

  it('완료 = 초록 체크 · 진행 = 주황 번호 · 기다림 = 회색 번호 · 줄마다 설명', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'running', 'pending'),
    });
    setup(server, runId);
    await screen.findByTestId('run-progress');
    expect(mark('extract').querySelector('svg')).not.toBeNull();
    expect(mark('extract').textContent).toBe('');
    expect(mark('extract').className).toContain('bg-support-success');
    expect(mark('map').textContent).toBe('2');
    expect(mark('map').className).toContain('bg-button-orange');
    expect(mark('draft').textContent).toBe('3');
    expect(mark('draft').className).not.toContain('bg-button-orange');
    expect(hint('map')).toBe(words.stepHints.map);
    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('draft 막대 — aria 값 == done/total · 「목차 n/m」 · 「가운데 n번째」', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'done', 'running', [4, 8]),
    });
    setup(server, runId);
    const bar = await screen.findByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('4');
    expect(bar.getAttribute('aria-valuemax')).toBe('8');
    expect(row('draft').contains(bar)).toBe(true);
    expect(row('draft').textContent).toContain('목차 4/8');
    expect(hint('draft')).toBe('목차 8개 가운데 5번째');
  });

  it('M5 [전체 다시 만들기] 연결 실패 = 연결 글 · 거절 = 확인 글(앞 시험)', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, { status: 'failed' });
    server.override['POST /runs'] = [unreachable];
    const { onRun } = setup(server, runId);
    fireEvent.click(
      await screen.findByRole('button', { name: words.restartAll }),
    );
    await flush();
    expect(screen.getByTestId('start-refused').textContent).toBe(
      DR_TEXT.startFailed,
    );
    expect(onRun).not.toHaveBeenCalled();
  });
});

describe('RPW3 D5 진행 머리', () => {
  it('진행·실패의 실행 고르기는 내용 폭 줄 안(화면 폭 전부 0)', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('running', 'pending', 'pending'),
    });
    setup(server, runId);
    const picker = await screen.findByRole('button', { name: words.picker });
    const line = screen.getByTestId('run-picker-row');
    expect(line.contains(picker)).toBe(true);
    expect(line.className).toContain('flex-wrap');
  });

  it('E2 실행 중 머리 = 부제 + 고르기 + 잎 수 · 실행이 센 값이 먼저', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('running', 'pending', 'pending'),
    });
    setup(server, runId);
    const subtitle = await screen.findByTestId('run-subtitle');
    await waitFor(() =>
      expect(subtitle.textContent).toContain('전년도 보고서'),
    );
    expect(subtitle.textContent).not.toContain('페이지');
    const counts = await screen.findByTestId('run-counts');
    expect(counts.textContent).toMatch(/^목차 \d+개$/);
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'done', 'running', [1, 37]),
    });
    await waitFor(() =>
      expect(screen.getByTestId('run-counts').textContent).toBe(
        words.headCount(37),
      ),
    );
  });

  it('E2 프로젝트를 못 읽어도 머리 자리는 그대로 — 부제·셈 글 0', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('running', 'pending', 'pending'),
    });
    setup(server, runId, 1, {
      getProject: () => Promise.resolve({ kind: 'failed' }),
    });
    await screen.findByTestId('run-progress');
    await flush();
    const subtitle = screen.getByTestId('run-subtitle');
    expect(subtitle.textContent).toBe('');
    expect(subtitle.className).toContain('min-h-[1lh]');
    expect(screen.getByTestId('run-picker-row').className).toContain('min-h-9');
    expect(screen.queryByTestId('run-counts')).toBeNull();
  });

  it('E2 실패한 실행은 지금 목차로 세지 않는다', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'failed',
      steps: steps('failed', 'pending', 'pending'),
    });
    setup(server, runId);
    await screen.findByTestId('run-failed');
    await flush();
    expect(screen.getByTestId('run-subtitle').textContent).not.toBe('');
    expect(screen.queryByTestId('run-counts')).toBeNull();
  });

  it('실패한 base 실행도 고르기는 내용 폭 줄 안', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, { status: 'done' });
    const next = await storeOf(server).startRun(
      { projectId: 1, base: { runId, rebuild: ['a1'] } },
      null,
    );
    const failed = next.kind === 'ok' ? next.value.runId : 0;
    server.runPatch(failed, { status: 'failed' });
    setup(server, failed);
    await screen.findByTestId('run-failed');
    const picker = await screen.findByRole('button', { name: words.picker });
    expect(screen.getByTestId('run-picker-row').contains(picker)).toBe(true);
  });
});

describe('RPW5 #5·#6 진행 줄 꼴(IR-03·DV-03 LineRow) · 움직임 클래스', () => {
  const mark = (name: string) =>
    row(name).querySelector<HTMLElement>('[data-testid="step-mark"]')!;

  it('줄 rounded-component px-4 py-3 · 지금 줄 bg-background-brand · 점 size-7 caption-01 · 이름 body-04 굵게 · 설명 body-06 · 막대 h-2', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'done', 'running', [1, 4]),
    });
    setup(server, runId);
    await waitFor(() =>
      expect(screen.getByTestId('run-progress')).toBeTruthy(),
    );
    for (const name of ['extract', 'map', 'draft'])
      expect(row(name).className).toContain('rounded-component px-4 py-3');
    expect(row('draft').className).toContain('bg-background-brand');
    expect(row('draft').getAttribute('aria-current')).toBe('step');
    expect(row('extract').className).not.toContain('bg-background-brand');
    expect(row('extract').getAttribute('aria-current')).toBeNull();
    expect(mark('draft').className).toContain('size-7');
    expect(mark('draft').className).toContain('text-style-pre-caption-01');
    const name = row('draft').querySelector('b')!;
    expect(name.textContent).toBe(words.steps.draft);
    expect(name.className).toContain('text-style-pre-body-04');
    expect(
      row('draft').querySelector('[data-testid="step-hint"]')!.className,
    ).toContain('text-style-pre-body-06');
    expect(screen.getByRole('progressbar').className).toContain('h-2');
  });

  it('RPW7 516 ① 상태 글 — caption-02 + 상태별 색(IR-03 STATE_LOOK 값)', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'running', 'pending'),
    });
    setup(server, runId);
    await waitFor(() =>
      expect(screen.getByTestId('run-progress')).toBeTruthy(),
    );
    const state = (name: string) =>
      row(name).querySelector('[data-testid="step-state"]')!.className;
    for (const name of ['extract', 'map', 'draft'])
      expect(state(name)).toContain('text-style-pre-caption-02');
    expect(state('extract')).toContain('text-text-tertiary');
    expect(state('map')).toContain('text-support-orange-dark');
    expect(state('draft')).toContain('text-text-quaternary');
    cleanup();
    const failed = await seeded();
    failed.server.runPatch(failed.runId, {
      status: 'processing',
      steps: steps('done', 'failed', 'pending'),
    });
    setup(failed.server, failed.runId);
    await waitFor(() =>
      expect(screen.getByTestId('run-progress')).toBeTruthy(),
    );
    expect(state('map')).toContain('text-support-error');
  });

  it('실패 단계 줄은 bg-support-error-subtle', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'failed', 'pending'),
    });
    setup(server, runId);
    await waitFor(() =>
      expect(screen.getByTestId('run-progress')).toBeTruthy(),
    );
    expect(row('map').className).toContain('bg-support-error-subtle');
    expect(row('draft').className).not.toContain('bg-support-error-subtle');
  });

  it('카드 gw-m-rise · 지금 점만 gw-m-ring · 끝난 체크 gw-m-pop · draft 막대 gw-m-flow + gw-m-width', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'done', 'running', [1, 4]),
    });
    setup(server, runId);
    await waitFor(() =>
      expect(screen.getByTestId('run-progress')).toBeTruthy(),
    );
    expect(screen.getByTestId('run-progress').className).toContain('gw-m-rise');
    expect(mark('draft').className).toContain('gw-m-ring');
    expect(mark('extract').className).not.toContain('gw-m-ring');
    expect(
      mark('extract').querySelector('svg')!.getAttribute('class'),
    ).toContain('gw-m-pop');
    const fill = screen.getByTestId('step-bar-fill');
    expect(fill.className).toContain('gw-m-flow');
    expect(fill.className).toContain('gw-m-width');
  });
});

describe('RPW5 #4 첫 불러오기 몸(sid:MARC-ENT-443 ①)', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('받기 전: 제목·STEP 띠 아래 299ms 스켈레톤 0 / 300ms 스켈레톤 → 받으면 진행 카드 · 스켈레톤 0', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'running', 'pending'),
    });
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    let open!: () => void;
    const gate = new Promise<void>((resolve) => (open = resolve));
    const base = storeOf(server);
    setup(server, runId, 1, {
      getRun: async (id) => {
        await gate;
        return base.getRun(id);
      },
    });
    await flush();
    expect(screen.getByRole('heading', { name: words.title })).toBeTruthy();
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    act(() => vi.advanceTimersByTime(299));
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByTestId('load-skeleton')).toBeTruthy();
    await act(async () => open());
    await flush();
    expect(screen.getByTestId('run-progress')).toBeTruthy();
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
  });

  it('300ms 안에 받으면 스켈레톤을 그린 적이 없다', async () => {
    const { server, runId } = await seeded();
    server.runPatch(runId, {
      status: 'processing',
      steps: steps('done', 'running', 'pending'),
    });
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    let open!: () => void;
    const gate = new Promise<void>((resolve) => (open = resolve));
    const base = storeOf(server);
    setup(server, runId, 1, {
      getRun: async (id) => {
        await gate;
        return base.getRun(id);
      },
    });
    await flush();
    act(() => vi.advanceTimersByTime(200));
    await act(async () => open());
    await flush();
    act(() => vi.advanceTimersByTime(500));
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    expect(screen.getByTestId('run-progress')).toBeTruthy();
  });
});
