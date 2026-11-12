// @vitest-environment jsdom
// 밴드 GW2R ②(발주서 §3 C — GW-03 r3): 진짜 실어댑터 + 거르지 않는 가짜 서버.
//   점검 중(파랑 줄) · 끝남(「{끝난 때} 끝남 · {n}문장을 찾았어요」, 인식 실패 페이지 칩은 결과에서만 — 차례 섞인 70·31·58 → 31·58·70) ·
//   멈춤 셋(errorCode 하나로 가름 — 단계로 가르지 않는다: setup_error·step_error 를 index·extract 에 섞어 둔다) · 228 S1·S2·덤.
// 자료는 모두 지어낸 것이다.
import { cleanup, render, screen, within } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import type { FakeRun } from '../../../entities/greenwash/api/testing.ts';
import {
  FAKE_FINISHED_AT,
  fakeDocument,
  fakeGreenwashServer,
  fakeResult,
  fakeRun,
  fakeSteps,
  json,
  refusal,
  serverStoreOf,
} from '../../../entities/greenwash/api/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type { ScanResult } from '../../../entities/greenwash/model/index.ts';
import { StatusScreen } from './StatusScreen.tsx';

afterEach(cleanup);

const words = GW_TEXT.status;
const RESULT_PATH = 'GET /greenwash/runs/12/result';

/** 문장 n 개 · 인식 실패 페이지(받은 차례 그대로)인 결과(지어낸). */
function resultWith(sentences: number, failedPages: number[]): ScanResult {
  const base = fakeResult('지어낸 보고서.pdf', 80, {
    ceo: [],
    company: [],
    climate: [1, 2, 3],
  });
  return {
    ...base,
    items: Array.from({ length: sentences }, (_, i) => ({
      ...base.items[i % base.items.length]!,
    })),
    candidateStats: {
      ...base.candidateStats,
      failedPages: failedPages.map((page) => ({ page, error: '지어낸' })),
    },
  };
}

function serverWith(run: Partial<FakeRun>, pageCount: number | null = 24) {
  return fakeGreenwashServer({
    documents: [fakeDocument(3, { fileName: '지어낸 스캔본.pdf', pageCount })],
    runs: [
      fakeRun(12, 3, {
        startedAt: '2026-10-19T10:20:00+09:00',
        ...run,
      }),
    ],
  });
}

/** 끝난 실행(가짜의 advance — finishedAt = FAKE_FINISHED_AT). 결과 GET 은 주면 그 답. */
function doneServer(answer?: () => Response) {
  const server = serverWith({});
  server.advance(12, { status: 'done' });
  if (answer) server.override[RESULT_PATH] = answer;
  return server;
}

function failedServer(
  errorCode: string,
  failedAt: 'extract' | 'index',
  pageCount: number | null = 24,
) {
  return serverWith(
    {
      status: 'failed',
      steps: fakeSteps(failedAt === 'extract' ? 0 : 1, { status: 'failed' }),
      errorCode,
    },
    pageCount,
  );
}

function draw(server: ReturnType<typeof fakeGreenwashServer>, canWrite = true) {
  const { store } = serverStoreOf(server);
  const handlers = {
    onBack: vi.fn(),
    onRerun: vi.fn(),
    onNewCheck: vi.fn(),
    onViewResult: vi.fn(),
  };
  render(
    <StatusScreen store={store} runId="12" canWrite={canWrite} {...handlers} />,
  );
  return handlers;
}

const currentStep = () =>
  screen
    .getByRole('list', { name: GW_TEXT.stepFlow.label })
    .querySelector('[aria-current="step"]')?.textContent ?? null;
const meta = () =>
  document.querySelector('[data-screen="status"] h2 + p')?.textContent ?? null;
/** 끝남 카드의 「… 끝남 · n문장」 줄(밴드 GP4 — 머리가 아니라 카드). */
const doneMeta = () => screen.queryByTestId('done-meta')?.textContent ?? null;

describe('GW-03 r3 — 점검 중', () => {
  it('제목 「점검 중이에요」, 「점검은 계속돼요」, 진행 카드 끝 파랑 줄 없음(「몇 페이지를 못 읽어도 …」 지움 — sid:MARC-ENT-603), STEP 2, 결과는 읽지 않는다', async () => {
    const server = serverWith({
      status: 'processing',
      steps: fakeSteps(2, { status: 'running', done: 3, total: 10 }),
    });
    draw(server);
    await screen.findByRole('heading', { name: words.title.running });
    expect(meta()).toContain('이 창을 닫아도 점검은 계속돼요');
    expect(screen.queryByTestId('running-note')).toBeNull();
    expect(document.body.textContent).not.toContain('멈추지 않고 끝까지');
    expect(screen.getByRole('progressbar', { name: '점검 진행' })).toBeTruthy();
    expect(currentStep()).toContain('STEP 2');
    expect(screen.queryByTestId('missed-pages')).toBeNull();
    expect(server.count(RESULT_PATH)).toBe(0);
  });
});

describe('GW-03 진행 막대 — 움직임 켬(밴드 GP4 R2)', () => {
  it('% 글자가 굴러가는 도중에도 막대의 aria-valuenow 는 끝 값이다', async () => {
    // jsdom 에는 matchMedia 가 없어 숫자가 굴러가지 않는다 — 움직임 켬으로 심는다
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
    try {
      draw(
        serverWith({
          status: 'processing',
          steps: fakeSteps(2, { status: 'running', done: 6, total: 10 }),
        }),
      );
      const bar = await screen.findByRole('progressbar', { name: '점검 진행' });
      const end = bar.getAttribute('aria-valuenow');
      expect(Number(end)).toBeGreaterThan(0);
      // 글자가 바뀔 때마다 (글자, aria) 쌍을 모은다 — 글자가 끝 값에 닿을 때까지
      const seen: [string | null, string | null][] = [];
      await vi.waitFor(() => {
        seen.push([
          screen.getByTestId('progress-percent').textContent,
          bar.getAttribute('aria-valuenow'),
        ]);
        expect(screen.getByTestId('progress-percent').textContent).toBe(
          `${end}%`,
        );
      });
      expect(seen.every(([, aria]) => aria === end)).toBe(true);
      // 도중의 글자(끝 값이 아닌 것)를 적어도 하나 보았다 — 굴러갔다
      expect(seen.some(([text]) => text !== `${end}%`)).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe('GW-03 r3 — 끝남', () => {
  it('「{끝난 때} 끝남 · 22개의 그린워싱 리스크 문장을 찾았어요」 + 파랑 줄 「인식 실패 페이지 3개 (31 · 58 · 70페이지)」(결과의 70·31·58 을 오름차순) + [결과 보기], STEP 3', async () => {
    const server = doneServer(() => json(200, resultWith(22, [70, 31, 58])));
    const { onViewResult } = draw(server);
    await screen.findByRole('heading', { name: words.title.done });
    expect(words.title.done).toBe('점검이 끝났어요');
    // FAKE_FINISHED_AT = 2026-10-19T10:52:00+09:00
    expect(FAKE_FINISHED_AT).toBe('2026-10-19T10:52:00+09:00');
    const line = await screen.findByTestId('missed-pages');
    expect(doneMeta()).toBe(
      '2026-10-19 10:52 끝남 · 22개의 그린워싱 리스크 문장을 찾았어요',
    );
    expect(line.textContent).toBe('인식 실패 페이지 3개 (31 · 58 · 70페이지)');
    expect(line.className).toContain('bg-support-blue-subtle');
    expect(server.count(RESULT_PATH)).toBe(1);
    expect(currentStep()).toContain('STEP 3');
    screen.getByRole('button', { name: words.viewResult }).click();
    expect(onViewResult).toHaveBeenCalledWith('12');
    expect(screen.queryByTestId('running-note')).toBeNull();
    expect(screen.queryByTestId('failure')).toBeNull();
    // 밴드 GP4: 끝남 카드 하나에 이름 · 끝남 줄 · 인식 실패 페이지 · [결과 보기](머리에는 [목록으로]와 시작 meta 만)
    const card = screen.getByTestId('done-card');
    expect(within(card).getByText(words.title.done)).toBeTruthy();
    expect(card.contains(line)).toBe(true);
    expect(
      within(card).getByRole('button', { name: words.viewResult }),
    ).toBeTruthy();
    expect(
      screen.getAllByRole('button', { name: words.viewResult }),
    ).toHaveLength(1);
    expect(meta()).toMatch(/^2026-10-19 10:20 시작 · 점검할 페이지 \d+개$/);
  });

  it('끝나도 저절로 넘기지 않는다 — 끝남 카드와 결과를 다 그린 뒤에도 onViewResult 0(밴드 GP4)', async () => {
    const server = doneServer(() => json(200, resultWith(4, [])));
    const { onViewResult } = draw(server);
    await screen.findByTestId('done-card');
    await vi.waitFor(() =>
      expect(doneMeta()).toBe(
        '2026-10-19 10:52 끝남 · 4개의 그린워싱 리스크 문장을 찾았어요',
      ),
    );
    expect(server.count(RESULT_PATH)).toBe(1);
    expect(onViewResult).not.toHaveBeenCalled();
  });

  it('인식 실패 페이지가 비면 파랑 줄이 없다(문장 수는 그대로)', async () => {
    draw(doneServer(() => json(200, resultWith(5, []))));
    await vi.waitFor(() =>
      expect(doneMeta()).toBe(
        '2026-10-19 10:52 끝남 · 5개의 그린워싱 리스크 문장을 찾았어요',
      ),
    );
    expect(screen.queryByTestId('missed-pages')).toBeNull();
  });

  it('결과 GET 500 → 문장 수·칩 두 토막만 조용히 빠진다(「… 끝남」과 [결과 보기]는 그대로, 오류 글 없음)', async () => {
    const server = doneServer(() => refusal(500, 'INTERNAL_SERVER_ERROR'));
    draw(server);
    await screen.findByRole('heading', { name: words.title.done });
    await vi.waitFor(() => expect(server.count(RESULT_PATH)).toBe(1));
    await vi.waitFor(() => expect(doneMeta()).toBe('2026-10-19 10:52 끝남'));
    expect(screen.queryByTestId('missed-pages')).toBeNull();
    expect(screen.getByRole('button', { name: words.viewResult })).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('dry-run 결과면 문장 수 토막을 뺀다', async () => {
    const scan = resultWith(3, []);
    const dryRun = {
      ...scan,
      items: [],
      candidateStats: null,
      counts: null,
      report: null,
      dryRun: {
        kinds: Object.fromEntries(
          ['detect', 'eval', 'lowOnly', 'repair'].map((kind) => [
            kind,
            {
              requests: 0,
              inputChars: 0,
              inputTokens: { status: 'measured', encoding: 'x', value: 0 },
            },
          ]),
        ),
      },
    };
    const server = doneServer(() => json(200, dryRun));
    draw(server);
    await vi.waitFor(() => expect(server.count(RESULT_PATH)).toBe(1));
    await screen.findByRole('heading', { name: words.title.done });
    await vi.waitFor(() => expect(doneMeta()).toBe('2026-10-19 10:52 끝남'));
  });
});

describe('GW-03 r3 — 멈춤 셋(errorCode 하나로 가름)', () => {
  it('일반(step_error, index 에서 멈춤): 새 글 · [다시 실행][목록으로] · 덧글 없음 · STEP 2', async () => {
    draw(failedServer('step_error', 'index'));
    const card = await screen.findByTestId('failure');
    expect(card.getAttribute('data-failure')).toBeNull();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      '점검이 멈췄어요',
    );
    expect(screen.getByTestId('failure-info').textContent).toBe(
      '점검을 끝내지 못했어요. [다시 실행]을 누르면 같은 파일로 처음부터 다시 점검해요.',
    );
    expect(
      within(card)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual([words.rerun, words.back]);
    expect(screen.queryByTestId('failure-note')).toBeNull();
    expect(currentStep()).toContain('STEP 2');
  });

  it('일반(step_error, extract 에서 멈춤): 같은 일반 카드 · [다시 실행] — 텍스트 추출에서 멈췄으니 STEP 1(228 덤)', async () => {
    draw(failedServer('step_error', 'extract'));
    const card = await screen.findByTestId('failure');
    expect(card.getAttribute('data-failure')).toBeNull();
    expect(
      within(card).getByRole('button', { name: words.rerun }),
    ).toBeTruthy();
    expect(screen.queryByTestId('failure-file')).toBeNull();
    expect(currentStep()).toContain('STEP 1');
    expect(currentStep()).not.toContain('STEP 2');
  });

  it('setup_error(index 에서 멈춤 — 실서버 꼴): 오류 카드 꼴 · D1 글 · [목록으로]만(다시 실행·새 점검 없음)', async () => {
    const { onBack } = draw(failedServer('setup_error', 'index'));
    const card = await screen.findByTestId('failure');
    expect(card.getAttribute('data-failure')).toBe('setup_error');
    const info = screen.getByTestId('failure-info');
    expect(info.textContent).toBe(
      '서비스 설정 문제로 점검을 시작하지 못했어요. 운영 관리자에게 알려 주세요.',
    );
    expect(info.getAttribute('data-tone')).toBe('error');
    expect(
      within(card)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual([words.back]);
    expect(screen.queryByRole('button', { name: words.rerun })).toBeNull();
    expect(
      screen.queryByRole('button', { name: words.noText.newCheck }),
    ).toBeNull();
    expect(screen.queryByTestId('failure-note')).toBeNull();
    within(card).getByRole('button', { name: words.back }).click();
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('setup_error(extract 에서 멈춤이어도) 같은 카드 — 단계로 가르지 않는다', async () => {
    draw(failedServer('setup_error', 'extract'));
    const card = await screen.findByTestId('failure');
    expect(card.getAttribute('data-failure')).toBe('setup_error');
    expect(screen.queryByRole('button', { name: words.rerun })).toBeNull();
  });

  it('쓰지 못하는 세션(canWrite 거짓 — 로그인하지 않음)도 setup_error·일반 글은 고객사 글 그대로, [다시 실행]만 숨김(sid:MARC-ENT-409 C1 — 운영 관리자 글 갈래 걷음)', async () => {
    draw(failedServer('setup_error', 'index'), false);
    await screen.findByTestId('failure');
    expect(screen.getByTestId('failure-info').textContent).toBe(
      words.setupFailure,
    );
    cleanup();
    draw(failedServer('step_error', 'index'), false);
    await screen.findByTestId('failure');
    expect(screen.getByTestId('failure-info').textContent).toBe(words.failure);
    expect(screen.queryByRole('button', { name: words.rerun })).toBeNull();
    expect('failureReadOnly' in words).toBe(false);
  });

  it('no_text_layer(extract): 파일 줄이 안내 위 · 「24쪽 · 텍스트 없음」 · [새 점검][목록으로] · STEP 1(228 S2·덤)', async () => {
    const { onNewCheck } = draw(failedServer('no_text_layer', 'extract'));
    const file = await screen.findByTestId('failure-file');
    expect(file.textContent).toBe('지어낸 스캔본.pdf총 24페이지 · 텍스트 없음');
    const info = screen.getByTestId('failure-info');
    expect(
      file.compareDocumentPosition(info) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(info.textContent).toBe(GW_TEXT.newCheck.upload.noText);
    const card = screen.getByTestId('failure');
    expect(
      within(card)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual([words.noText.newCheck, words.back]);
    within(card).getByRole('button', { name: words.noText.newCheck }).click();
    expect(onNewCheck).toHaveBeenCalledTimes(1);
    expect(currentStep()).toContain('STEP 1');
  });

  it('no_text_layer 인데 쪽 수를 모르면 파일 줄은 「이름 · 텍스트 없음」꼴(쪽 토막 없음)', async () => {
    draw(failedServer('no_text_layer', 'extract', null));
    const file = await screen.findByTestId('failure-file');
    expect(file.textContent).toBe('지어낸 스캔본.pdf텍스트 없음');
  });
});

describe('228 S1 — 불러오지 못함에도 STEP 띠', () => {
  it('상태 읽기 500 → STEP 띠가 있고 켜진 단계는 없다', async () => {
    const server = failedServer('step_error', 'index');
    server.override['GET /runs/12'] = [
      () => refusal(500, 'INTERNAL_SERVER_ERROR'),
    ];
    draw(server);
    await screen.findByTestId('load-failure');
    expect(
      screen.getByRole('list', { name: GW_TEXT.stepFlow.label }),
    ).toBeTruthy();
    expect(currentStep()).toBeNull();
  });
});
