// @vitest-environment jsdom
// DV-03 처리 상태 화면 시험(밴드 DV2a ③ — 발주서 §3-3 10). 저장소는 가짜 데이터 검증 서버를 앞에 둔 실어댑터(목 0), 폴링 간격은 짧게.
//   queued·processing(n번째) · done 요약·「확인할 곳」 · failed → [다시 실행] → rerun(options 그대로) · no_target_theme → ④ ·
//   「환경」 빈 목록(경고 없음)은 ② · 단계 실패 「못 함」 · 폴링 실패·없음. 서버 message·errorMessage 는 화면에 0.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  fakeDataverifyServer,
  fakeRun,
  fakeSteps,
  refusal,
  serverStoreOf,
} from '../../../entities/dataverify/api/testing.ts';
import type {
  FakeDataverifyServer,
  FakeRun,
} from '../../../entities/dataverify/api/testing.ts';
import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import {
  fakeChecks,
  fakeInput,
  fakeResult,
  insightFailed,
  noTargetResult,
  planFailed,
  reviewDone,
} from '../../../entities/dataverify/model/testing.ts';
import { PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { StatusScreen } from './StatusScreen.tsx';

afterEach(cleanup);

const words = DV_TEXT.status;
const common = DV_TEXT.common;
const WAIT = { timeout: 3_000 };

function setup(run: Partial<FakeRun> = {}) {
  const server = fakeDataverifyServer({ runs: [fakeRun(7, run)] });
  const store = serverStoreOf(server, { pollMs: 5 });
  const props = {
    onBack: vi.fn(),
    onViewResult: vi.fn(),
    onRerun: vi.fn(),
    onNewCheck: vi.fn(),
  };
  render(<StatusScreen store={store} runId="7" {...props} />);
  return { server, ...props };
}

/** 응답을 붙잡아 두는 서버(첫 불러오기 시험 — 밴드 DV2e). release() 뒤에야 답한다. */
function held(server: FakeDataverifyServer) {
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
    .querySelector('[data-screen="dataverify-status"]')
    ?.getAttribute('data-run-state');
const stepState = (name: string) =>
  document.querySelector(`[data-step="${name}"]`)?.getAttribute('data-state');
const shown = (text: string) => screen.findByText(text, undefined, WAIT);
const noServerText = () =>
  expect(document.body.textContent).not.toContain('지어낸');

describe('DV-03 처리 상태', () => {
  it('queued: 「검증 중이에요」 · 머리 시작·기업명 · 차례 기다림 · 다섯 단계 대기 · 첫째', async () => {
    const { server } = setup();
    await shown(words.running);
    expect(document.body.textContent).toContain(
      words.head('2026-10-19 10:40', '가상건설'),
    );
    expect(screen.getByTestId('queued').textContent).toContain(words.queued);
    expect(screen.getByTestId('progress-nth').textContent).toBe(
      words.progressNth(1),
    );
    for (const name of ['load', 'plan', 'review', 'insight', 'report'])
      expect(stepState(name)).toBe('pending');
    // 대기 글은 판 글(빈 글 0)
    expect(document.body.textContent).toContain(words.stepText.plan.pending);
    expect(screen.queryByTestId('goes-on')).toBeNull();
    noServerText();
    // 끝나지 않은 실행은 결과를 읽지 않는다(done 시험의 toBe(1) 과 짝 — 검증 ③ B1)
    expect(server.count('GET /dataverify/runs/7/result')).toBe(0);
  });

  it('processing: n번째 · 진행 중 단계의 글 · 멈추지 않음 안내 줄 0(sid:MARC-ENT-625) · 수 0', async () => {
    const { server } = setup({
      status: 'processing',
      steps: fakeSteps(2, 'running'),
    });
    await shown(words.stepText.review.running);
    expect(screen.getByTestId('progress-nth').textContent).toBe(
      words.progressNth(3),
    );
    expect(stepState('load')).toBe('done');
    expect(stepState('review')).toBe('running');
    expect(stepState('insight')).toBe('pending');
    expect(screen.queryByTestId('goes-on')).toBeNull();
    expect(document.body.textContent).not.toContain('멈추지 않고 결과까지');
    expect(screen.queryByTestId('queued')).toBeNull();
    // 끝나지 않은 실행은 결과를 읽지 않는다(done 시험의 toBe(1) 과 짝 — 검증 ③ B1)
    expect(server.count('GET /dataverify/runs/7/result')).toBe(0);
  });

  it('진행 중 → 폴링으로 done: 끝남 줄(산식 2개 · 검산 7곳(맞음 2 · 어긋남 1 · 계산 못 함 4) · 리스크 2건) · 확인할 곳 · [결과 보기] → onViewResult', async () => {
    // 맞음 ≠ 어긋남이 되게 합계 줄에 맞은 해를 하나 더 지어 넣는다(맞음·어긋남 자리가 바뀌면 빨강 — 밴드 DV7 검증 R1)
    const checks = fakeChecks();
    const sum = checks.find((check) => check.seq === 3)!;
    sum.years = [
      {
        year: '2022',
        ok: true,
        status: 'OK',
        diff: '0.0',
        note: null,
        explanation:
          'Sum(1100.0 + 290.0) - Target(1390.0) = 0.000000 → within tolerance (0.0).',
      },
      ...(sum.years as unknown[]),
    ];
    const { server, onViewResult } = setup({
      status: 'processing',
      steps: fakeSteps(1, 'running'),
    });
    await shown(words.running);
    act(() =>
      server.advance(7, {
        status: 'done',
        result: fakeResult({ review: reviewDone(true, checks) }),
      }),
    );
    await screen.findByTestId('done-card', undefined, WAIT);
    await shown(
      words.doneLine('2026-10-19 10:58', {
        plan: 2,
        places: 7,
        ok: 2,
        mismatches: 1,
        uncomputable: 4,
        risks: 2,
      }),
    );
    // 글자 그대로(시안 v212 DV-03 r2, 밴드 DV7) — 검산 = 맞음 + 어긋남 + 계산 못 함
    await shown(
      '2026-10-19 10:58 끝남 · 산식 2개 · 검산 7곳(맞음 2 · 어긋남 1 · 계산 못 함 4) · 리스크 2건',
    );
    expect(state()).toBe('done');
    // 기본 결과는 계산 검토 partial(판 DV-04) — 짧은 글 하나
    expect(screen.getByTestId('check-places').textContent).toBe(
      words.checkPlaces([DV_TEXT.notices.review_partial.short]),
    );
    fireEvent.click(screen.getByRole('button', { name: common.viewResult }));
    expect(onViewResult).toHaveBeenCalledWith('7');
    // done 뒤 폴링 멈춤 — 결과는 한 번 읽는다
    expect(server.count('GET /dataverify/runs/7/result')).toBe(1);
  });

  it('done 의 확인할 곳은 줄을 「 · 」로, 같은 글은 한 번(Plan 실패 + 인사이트 실패)', async () => {
    setup({
      status: 'done',
      steps: fakeSteps(5),
      finishedAt: '2026-10-19T10:58:00+09:00',
      files: [],
      result: fakeResult({
        plan: planFailed('provider_error'),
        insight: insightFailed(),
      }),
    });
    await screen.findByTestId('done-card', undefined, WAIT);
    const n = DV_TEXT.notices;
    expect(
      (await screen.findByTestId('check-places', undefined, WAIT)).textContent,
    ).toBe(
      words.checkPlaces([
        n.plan_failed.short,
        n.review_partial.short,
        n.insight_failed.short,
      ]),
    );
  });

  it('③ 끝남 카드(밴드 DV13 — GW-03 r3 꼴): 카드 안에 제목·끝 줄·[결과 보기]·확인할 곳 · 머리는 시작 meta(계속돼요 0)·[목록으로]만 · STEP 3', async () => {
    const { onViewResult, onBack } = setup({
      status: 'done',
      steps: fakeSteps(5),
      finishedAt: '2026-10-19T10:58:00+09:00',
      result: fakeResult(),
    });
    const card = await screen.findByTestId('done-card', undefined, WAIT);
    const places = await screen.findByTestId('check-places', undefined, WAIT);
    expect(card.contains(places)).toBe(true);
    expect(card.textContent).toContain(words.doneTitle);
    expect(screen.getByTestId('done-meta').textContent).toMatch(
      /^2026-10-19 10:58 끝남 · /,
    );
    expect(card.contains(screen.getByTestId('done-meta'))).toBe(true);
    // [결과 보기]는 카드 한 자리(머리 0)
    const view = screen.getAllByRole('button', { name: common.viewResult });
    expect(view).toHaveLength(1);
    expect(card.contains(view[0]!)).toBe(true);
    fireEvent.click(view[0]!);
    expect(onViewResult).toHaveBeenCalledWith('7');
    // 머리: 제목 · 시작 meta(「계속돼요」 토막 없음) · [목록으로]
    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading.textContent).toBe(words.doneTitle);
    const page = document.querySelector('[data-screen="dataverify-status"]')!;
    const head = page.firstElementChild!;
    expect(card.contains(head)).toBe(false);
    expect(head.textContent).toContain(
      words.head('2026-10-19 10:40', '가상건설', false),
    );
    expect(document.body.textContent).not.toContain(words.keepsGoing);
    fireEvent.click(screen.getByRole('button', { name: common.toList }));
    expect(onBack).toHaveBeenCalledTimes(1);
    // 단계 줄은 STEP 3(끝난 실행)
    const flow = screen.getByRole('list', { name: DV_TEXT.steps.label });
    expect(flow.querySelector('[aria-current="step"]')?.textContent).toContain(
      DV_TEXT.steps.items[2]!.label,
    );
  });

  it('done + 결과를 못 읽음: 끝 시각만', async () => {
    const { server } = setup({
      status: 'done',
      steps: fakeSteps(5),
      finishedAt: '2026-10-19T10:58:00+09:00',
      result: fakeResult(),
    });
    server.override['GET /dataverify/runs/7/result'] = () =>
      refusal(500, 'INTERNAL');
    await shown(words.doneLine('2026-10-19 10:58', null));
    expect(screen.queryByTestId('check-places')).toBeNull();
  });

  it('no_target_theme: 「검증할 항목이 없어요」 · [결과 보기]·[새 검증]', async () => {
    const { onNewCheck, onViewResult } = setup({
      status: 'done',
      steps: fakeSteps(5),
      finishedAt: '2026-10-19T10:58:00+09:00',
      result: noTargetResult(),
    });
    await shown(words.noTargetTitle);
    expect(state()).toBe('no_target');
    // 끝난 실행이라 단계 줄 STEP 3(밴드 DV13 ③), 끝남 카드는 없음(④ 카드 그대로)
    expect(
      screen
        .getByRole('list', { name: DV_TEXT.steps.label })
        .querySelector('[aria-current="step"]')?.textContent,
    ).toContain(DV_TEXT.steps.items[2]!.label);
    expect(screen.queryByTestId('done-card')).toBeNull();
    expect(screen.getByTestId('no-target').textContent).toContain(
      words.noTargetBody,
    );
    fireEvent.click(screen.getByRole('button', { name: common.newCheck }));
    expect(onNewCheck).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: common.viewResult }));
    expect(onViewResult).toHaveBeenCalledWith('7');
  });

  it('「환경」이 빈 목록이라 경고가 없으면 ② 끝남(④ 아님)', async () => {
    setup({
      status: 'done',
      steps: fakeSteps(5),
      finishedAt: '2026-10-19T10:58:00+09:00',
      result: fakeResult({
        scope: { themes: ['환경'], itemCount: 0, keyItemCount: 0, years: [] },
      }),
    });
    await screen.findByTestId('done-card', undefined, WAIT);
    expect(state()).toBe('done');
    expect(screen.queryByTestId('no-target')).toBeNull();
  });

  it('failed: 「검증이 멈췄어요」 · 단계 「못 함」(진행 중 글) · [다시 실행] → 같은 options 로 새 실행 → onRerun', async () => {
    const { server, onRerun } = setup({
      status: 'failed',
      steps: fakeSteps(1, 'failed'),
      errorCode: 'flow_failed',
      finishedAt: '2026-10-19T10:58:00+09:00',
    });
    await shown(words.failedTitle);
    expect(stepState('plan')).toBe('failed');
    const plan = document.querySelector('[data-step="plan"]')!;
    expect(plan.textContent).toContain(words.stepText.plan.running);
    expect(plan.textContent).toContain(words.stepBadge.failed);
    expect(screen.getByTestId('failure').textContent).toContain(
      words.failedBody,
    );
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: common.rerun }));
    });
    await vi.waitFor(() => expect(onRerun).toHaveBeenCalledWith('30'), WAIT);
    const [post] = server.posts();
    expect(post!.body).toEqual({
      module: 'dataverify',
      launchKey: expect.stringMatching(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
      ),
      options: server.runs.get(7)!.options,
    });
    noServerText();
    // 끝나지 않은 실행은 결과를 읽지 않는다(done 시험의 toBe(1) 과 짝 — 검증 ③ B1)
    expect(server.count('GET /dataverify/runs/7/result')).toBe(0);
  });

  it('failed: [다시 실행] 거절이면 시작 실패 글 · 이동 0', async () => {
    const { server, onRerun } = setup({
      status: 'failed',
      steps: fakeSteps(1, 'failed'),
      errorCode: 'flow_failed',
    });
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL');
    await shown(words.failedTitle);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: common.rerun }));
    });
    expect(
      (await screen.findByTestId('rerun-error', undefined, WAIT)).textContent,
    ).toBe(DV_TEXT.newCheck.errors.startFailed);
    expect(onRerun).not.toHaveBeenCalled();
    noServerText();
    // 끝나지 않은 실행은 결과를 읽지 않는다(done 시험의 toBe(1) 과 짝 — 검증 ③ B1)
    expect(server.count('GET /dataverify/runs/7/result')).toBe(0);
  });

  it('폴링 실패: 불러오지 못함 + [다시 시도]로 다시 읽음', async () => {
    const { server } = setup();
    server.override['GET /runs/7'] = [() => refusal(500, 'INTERNAL')];
    await shown(words.loadFailed);
    fireEvent.click(screen.getByRole('button', { name: common.retry }));
    await shown(words.running);
  });

  it('없는 실행: 「결과를 찾을 수 없어요」 + [목록으로]', async () => {
    const server = fakeDataverifyServer();
    const onBack = vi.fn();
    render(
      <StatusScreen
        store={serverStoreOf(server, { pollMs: 5 })}
        runId="99"
        onBack={onBack}
        onViewResult={vi.fn()}
        onRerun={vi.fn()}
        onNewCheck={vi.fn()}
      />,
    );
    await shown(common.notFound);
    fireEvent.click(screen.getByRole('button', { name: common.toList }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});

describe('DV-03 머리 제목 = 출처 글(DV2b)', () => {
  it('파일 → 파일 이름 · 붙여 넣기 → 「붙여 넣은 데이터」 · 출처 없는 옛 실행 → 기업명', async () => {
    for (const [source, title] of [
      [{ kind: 'file', name: 'EDK_가상_2025.json' }, 'EDK_가상_2025.json'],
      [{ kind: 'paste' }, DV_TEXT.source.paste],
      [undefined, '가상건설'],
    ] as const) {
      setup({
        options:
          source === undefined ?
            { input: fakeInput() }
          : { input: fakeInput(), source },
      });
      await shown(words.running);
      expect(document.body.textContent).toContain(
        words.head('2026-10-19 10:40', title),
      );
      cleanup();
    }
  });
});

describe('DV-03 첫 불러오기(DV2e)', () => {
  it('응답 전에는 셸 제목 「데이터 검증」이 제목 자리에 없음(제목·머리 줄 막대) → 응답 뒤 상태 제목', async () => {
    const { server, release } = held(
      fakeDataverifyServer({
        runs: [
          fakeRun(7, { status: 'processing', steps: fakeSteps(2, 'running') }),
        ],
      }),
    );
    const store = serverStoreOf(server, { pollMs: 5 });
    render(
      <StatusScreen
        store={store}
        runId="7"
        onBack={vi.fn()}
        onViewResult={vi.fn()}
        onRerun={vi.fn()}
        onNewCheck={vi.fn()}
      />,
    );
    await act(async () => {});
    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading.textContent).not.toContain(DV_TEXT.shell.title);
    expect(screen.getByTestId('title-pending')).toBeTruthy();
    expect(screen.getByTestId('description-pending')).toBeTruthy();
    expect(screen.getByRole('button', { name: common.toList })).toBeTruthy();
    await release();
    await shown(words.running);
    expect(screen.queryByTestId('title-pending')).toBeNull();
  });
});

describe('DV-03 주의 톤(DV2e, sid:MARC-ISSUE-361)', () => {
  it('확인할 곳 · 테마 없음 안내 = 공용 PageInfo tone="caution"(멈추지 않음 안내는 지움 — sid:MARC-ENT-625)', async () => {
    setup({
      status: 'done',
      steps: fakeSteps(5),
      finishedAt: '2026-10-19T10:58:00+09:00',
      files: [],
      result: fakeResult({ plan: planFailed('provider_error') }),
    });
    expect(
      (await screen.findByTestId('check-places', undefined, WAIT)).getAttribute(
        'data-tone',
      ),
    ).toBe('caution');
    cleanup();
    setup({ status: 'processing', steps: fakeSteps(2, 'running') });
    await screen.findByText(words.stepText.review.running, undefined, WAIT);
    expect(screen.queryByTestId('goes-on')).toBeNull();
    cleanup();
    setup({
      status: 'done',
      steps: fakeSteps(5),
      finishedAt: '2026-10-19T10:58:00+09:00',
      result: noTargetResult(),
    });
    const noTarget = await screen.findByTestId('no-target', undefined, WAIT);
    expect(
      noTarget.querySelector('[data-tone]')?.getAttribute('data-tone'),
    ).toBe('caution');
  });
});

describe('DV-03 한 줄 안내 아이콘(DV2c)', () => {
  it('확인할 곳 · 테마 없음 안내의 아이콘 = 공용 PageInfoIcon', async () => {
    const icon = render(<PageInfoIcon />, {
      container: document.createElement('div'),
    }).container.innerHTML;
    const iconIn = (el: Element) => el.querySelector('svg')?.outerHTML;
    setup({
      status: 'done',
      steps: fakeSteps(5),
      finishedAt: '2026-10-19T10:58:00+09:00',
      files: [],
      result: fakeResult({ plan: planFailed('provider_error') }),
    });
    expect(
      iconIn(await screen.findByTestId('check-places', undefined, WAIT)),
    ).toBe(icon);
    cleanup();
    setup({
      status: 'done',
      steps: fakeSteps(5),
      finishedAt: '2026-10-19T10:58:00+09:00',
      result: noTargetResult(),
    });
    expect(
      iconIn(await screen.findByTestId('no-target', undefined, WAIT)),
    ).toBe(icon);
  });
});

describe('DV-03 시안 대조 손질(밴드 DV3 ①)', () => {
  it('J2 「계산 계획을…」은 진행 카드 안 맨 아래 파랑 안내 · 「단계 하나를…」 줄은 없음(ENT-625) · n번째 400 12', async () => {
    setup({ status: 'processing', steps: fakeSteps(2, 'running') });
    const progress = await screen.findByTestId('progress', undefined, WAIT);
    await screen.findByText(words.stepText.review.running, undefined, WAIT);
    const planSkip = screen.getByTestId('plan-skip');
    expect(planSkip.getAttribute('data-tone')).toBe('caution');
    expect(planSkip.textContent).toBe(words.footnote);
    expect(planSkip.querySelector('svg')).not.toBeNull();
    expect(progress.contains(planSkip)).toBe(true);
    expect(progress.lastElementChild).toBe(planSkip);
    expect(screen.queryByTestId('goes-on')).toBeNull();
    // 진행 카드 밖의 caution 안내는 없다(옛 「단계 하나를…」 자리)
    expect(
      [...document.querySelectorAll('[data-tone="caution"]')].filter(
        (node) => !progress.contains(node),
      ),
    ).toHaveLength(0);
    expect(screen.getByTestId('progress-nth').className).toContain(
      'text-style-pre-caption-03',
    );
  });

  it('J2 queued 에도 「계산 계획을…」 안내는 카드 안에 늘 보인다(goes-on 은 없음)', async () => {
    setup({ status: 'queued' });
    const queued = await screen.findByTestId('queued', undefined, WAIT);
    expect(queued.textContent).toContain(words.queued);
    expect(
      screen.getByTestId('progress').contains(screen.getByTestId('plan-skip')),
    ).toBe(true);
    expect(screen.queryByTestId('goes-on')).toBeNull();
  });
});

describe('DV-03 움직임(밴드 DV3 ②)', () => {
  afterEach(() => vi.unstubAllGlobals());
  const motionOn = () =>
    vi.stubGlobal(
      'matchMedia',
      (query: string) =>
        ({
          matches: !query.includes('reduce'),
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
        }) as unknown as MediaQueryList,
    );
  const dotOf = (name: string) =>
    document.querySelector(`[data-step="${name}"] > span[aria-hidden]`)!;

  it('②-1 지금 단계 점에만 gw-m-ring · 끝난 단계 체크에 gw-m-pop', async () => {
    setup({ status: 'processing', steps: fakeSteps(2, 'running') });
    await shown(words.stepText.review.running);
    expect(dotOf('review').classList.contains('gw-m-ring')).toBe(true);
    const others = ['load', 'plan', 'insight', 'report'];
    expect(
      others.filter((name) => dotOf(name).classList.contains('gw-m-ring')),
    ).toEqual([]);
    for (const name of ['load', 'plan'])
      expect(
        dotOf(name).querySelector('svg')!.classList.contains('gw-m-pop'),
      ).toBe(true);
  });

  it('②-2 움직임 켬: 「n번째」가 0 에서 굴러 끝 값이 된다', async () => {
    motionOn();
    const seen: string[] = [];
    const observer = new MutationObserver(() => {
      const nth = document.querySelector('[data-testid="progress-nth"]');
      if (nth && seen[seen.length - 1] !== nth.textContent)
        seen.push(nth.textContent ?? '');
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    try {
      setup({ status: 'processing', steps: fakeSteps(2, 'running') });
      await vi.waitFor(
        () =>
          expect(screen.getByTestId('progress-nth').textContent).toBe(
            words.progressNth(3),
          ),
        WAIT,
      );
    } finally {
      observer.disconnect();
    }
    expect(seen[0]).toBe(words.progressNth(0));
    expect(seen[seen.length - 1]).toBe(words.progressNth(3));
  });

  it('②-3 진행 → 끝남: 「확인할 곳」 띠가 새로 붙으며 gw-m-rise · 검증할 항목 없음 카드도', async () => {
    const { server } = setup({
      status: 'processing',
      steps: fakeSteps(1, 'running'),
    });
    await shown(words.running);
    act(() => server.advance(7, { status: 'done' }));
    // 밴드 DV13 ③: 떠오르는 것은 끝남 카드(GW-03 꼴), 「확인할 곳」 띠는 그 안
    const card0 = await screen.findByTestId('done-card', undefined, WAIT);
    expect(card0.classList.contains('gw-m-rise')).toBe(true);
    const places = await screen.findByTestId('check-places', undefined, WAIT);
    expect(card0.contains(places)).toBe(true);
    cleanup();
    setup({ status: 'done', steps: fakeSteps(5), result: noTargetResult() });
    const card = await screen.findByTestId('no-target', undefined, WAIT);
    expect(card.classList.contains('gw-m-rise')).toBe(true);
  });
});
