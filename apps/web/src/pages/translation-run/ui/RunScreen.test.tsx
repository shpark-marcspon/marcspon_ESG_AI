// @vitest-environment jsdom
// 묶음 화면(밴드 TRW1a ③ — 발주서 §3-3 12). 진짜 실어댑터 + 가짜 영문번역 서버(짧은 폴링).
//   active → StageCard·폴링 → done 이 되면 결과 · 한 파트 rejected → 실패 카드 다시 단추 0 · done → Word 셋(요약 files 에 없는 것은 꺼짐 — TRP2 TE13) ·
//   [모두 받기] 409 too_large → 판 글 하나(단추 실패 글 0) · 409 nothing → 받을 것 없음 글(noFiles) · missing 2 → 빠짐 글 · 404 → 찾을 수 없음 · 일부만 시작 → 띠 · digest null → 「–」.
import { useState } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  fakeDocument,
  fakeLayout,
  fakeOptions,
  fakeRun,
  fakeSteps,
  fakeTranslationServer,
  refusal,
  serverStoreOf,
} from '../../../entities/translation/api/testing.ts';
import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import type { PartTabKey } from '../../../entities/translation/ui/index.ts';
import { RunScreen } from './RunScreen.tsx';
import type { RunScreenProps } from './RunScreen.tsx';

const BATCH = '0b9f1a2c-3d4e-4f50-8a6b-7c8d9e0f1a2b';
const flush = () => act(async () => {});
const WAIT = { timeout: 3000 };

// jsdom 의 URL 에는 createObjectURL 이 없다 — 시험 동안만(DownloadButton 시험 꼴).
const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };
let saved: string[] = [];
beforeEach(() => {
  saved = [];
  URL.createObjectURL = vi.fn(() => 'blob:fake');
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    saved.push(this.download);
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  URL.createObjectURL = original.create;
  URL.revokeObjectURL = original.revoke;
});

type Server = ReturnType<typeof fakeTranslationServer>;

function draw(
  server: Server,
  props: {
    part?: PartTabKey;
    notStarted?: {
      started: ('ceo' | 'story' | 'general')[];
      failed: ('ceo' | 'story' | 'general')[];
    };
    batchKey?: string;
  } = {},
) {
  const onTab = vi.fn();
  const onBack = vi.fn();
  render(
    <RunScreen
      store={serverStoreOf(server, { pollMs: 20 })}
      documentId="12"
      batchKey={props.batchKey ?? BATCH}
      {...(props.part === undefined ? {} : { part: props.part })}
      {...(props.notStarted === undefined ?
        {}
      : { notStarted: props.notStarted })}
      onTab={onTab}
      onBack={onBack}
    />,
  );
  return { onTab, onBack };
}

const twoParts = () =>
  fakeTranslationServer({
    documents: [fakeDocument(12, { fileName: 'sample_a_extract.txt' })],
    runs: [
      fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
      fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH), {
        status: 'processing',
        steps: fakeSteps(1, { status: 'running', done: 2, total: 6 }),
      }),
    ],
  });

describe('RunScreen (§3-3 12)', () => {
  it('active → 진행 카드·폴링, 끝나면 결과로(제목도 바뀜)', async () => {
    const server = twoParts();
    server.advance(30, { status: 'done' });
    draw(server, { part: 'story' });
    await waitFor(
      () => expect(screen.getByText(TR_TEXT.screenTitle.running)).toBeTruthy(),
      WAIT,
    );
    expect(document.querySelector('[data-stage]')).not.toBeNull();
    expect(screen.getByText(TR_TEXT.stage.pages(2, 6))).toBeTruthy();
    server.advance(31, { status: 'done' });
    await waitFor(
      () => expect(screen.getByText(TR_TEXT.screenTitle.done)).toBeTruthy(),
      WAIT,
    );
    await waitFor(
      () => expect(screen.getByText(TR_TEXT.issues.title)).toBeTruthy(),
      WAIT,
    );
  });

  it('한 파트 rejected → 실패 카드, 다시 단추 0(목록으로만)', async () => {
    const server = twoParts();
    server.advance(30, { status: 'done' });
    server.advance(31, {
      status: 'done',
      outcome: 'rejected',
      rejectionKind: 'too_large',
    });
    const { onBack } = draw(server, { part: 'story' });
    await waitFor(
      () =>
        expect(
          screen.getByText(TR_TEXT.rejection.too_large.reason, {
            exact: false,
          }),
        ).toBeTruthy(),
      WAIT,
    );
    expect(screen.queryByText(TR_TEXT.failure.retryPart)).toBeNull();
    expect(screen.queryByText(TR_TEXT.failure.retrySingle)).toBeNull();
    fireEvent.click(
      screen.getAllByRole('button', { name: TR_TEXT.failure.back }).at(-1)!,
    );
    expect(onBack).toHaveBeenCalled();
  });

  // [밴드 TRW4] CEO 한도는 입력 화면이 막는다 — 서버가 그래도 ceo_page_limit 로 거절하면 일반 실패 글(빈 글 0, 「CEO … 넘음」 0).
  it('서버 ceo_page_limit 거절 → 일반 실패 글, 「분량 많음」 거절은 그대로', async () => {
    const server = twoParts();
    server.advance(30, {
      status: 'done',
      outcome: 'rejected',
      rejectionKind: 'ceo_page_limit',
    });
    server.advance(31, {
      status: 'done',
      outcome: 'rejected',
      rejectionKind: 'too_large',
    });
    draw(server, { part: 'ceo' });
    await waitFor(
      () => expect(screen.getByTestId('part-failure')).toBeTruthy(),
      WAIT,
    );
    const card = screen.getByTestId('part-failure').textContent!;
    expect(card).toContain('이 파트를 시작하지 않았어요.');
    // 카드 머리의 파트 이름(「CEO 메시지 1~3페이지」)은 남는다 — 한도 글(「CEO 메시지는 …」·「넘음」·「최대」)만 없다.
    expect(card).not.toMatch(/CEO 메시지는|넘음|최대/);
    cleanup();
    draw(server, { part: 'story' });
    await waitFor(
      () =>
        expect(screen.getByTestId('part-failure').textContent).toContain(
          '분량이 많아 시작하지 않았어요.',
        ),
      WAIT,
    );
  });

  // [밴드 TRW1b] 서버 오류 파트에는 [이 파트만 다시](결정 sid:MARC-ENT-393) — 옛 「단추 0」을 갈음.
  it('서버 오류(failed) 파트 → [이 파트만 다시]', async () => {
    const server = twoParts();
    server.advance(31, { status: 'failed', errorCode: 'step_error' });
    draw(server, { part: 'story' });
    await waitFor(
      () =>
        expect(
          screen.getByText(TR_TEXT.failure.serverError, { exact: false }),
        ).toBeTruthy(),
      WAIT,
    );
    expect(
      screen.getByRole('button', { name: TR_TEXT.failure.retryPart }),
    ).toBeTruthy();
  });

  // [TRP2 TE13 → TRW14 ①] 머리 [내려받기] → 받기 모달: Word 셋을 늘 그리고 만들지 않은 파일은 끈 줄(aria-disabled) + (?) 까닭.
  //   옛 「머리 Word 단추 셋 · 내려받기 카드(있는 파일 설명)」를 갈음 — 같은 뜻(꺼짐·받기·설명)을 모달에서 단언한다.
  const fileRow = (key: string) =>
    screen.getByTestId(`part-download-dialog-file-${key}`);
  const disabledOf = (key: string) =>
    fileRow(key).getAttribute('aria-disabled');
  const openDownloads = async () => {
    const opener = await waitFor(
      () => screen.getByTestId('part-downloads'),
      WAIT,
    );
    fireEvent.click(opener);
    return screen.getByTestId('part-download-dialog');
  };

  it('done 파트 → [내려받기] → 모달 줄 셋, 자동 수정 없음이면 그 줄만 꺼짐(+ 까닭) · 병기 번역본은 받음', async () => {
    const server = twoParts();
    server.advance(30, {
      status: 'done',
      files: { bilingual: true, qa: true, autofix: false },
    });
    draw(server, { part: 'ceo' });
    const dialog = await openDownloads();
    expect(
      [...dialog.querySelectorAll('[data-file]')].map((li) =>
        li.getAttribute('data-file'),
      ),
    ).toEqual(['bilingual', 'review', 'autofix']);
    expect(disabledOf('autofix')).toBe('true');
    expect(disabledOf('bilingual')).toBeNull();
    expect(disabledOf('review')).toBeNull();
    expect(
      screen
        .getByTestId('part-download-dialog-help-autofix')
        .getAttribute('aria-label'),
    ).toBe(
      `${TR_TEXT.result.fileMissingLabel}: ${TR_TEXT.result.fileMissing.autofix}`,
    );
    expect(
      screen.queryByTestId('part-download-dialog-help-bilingual'),
    ).toBeNull();
    fireEvent.click(fileRow('autofix'));
    fireEvent.click(fileRow('bilingual'));
    await waitFor(
      () => expect(saved).toEqual(['translation-bilingual-single.docx']),
      WAIT,
    );
  });

  it('done 파트 → 검수 결과 Word 가 없으면(qa 없음) 그 줄만 꺼짐(검수 까닭) · 설명은 셋 다 늘 보임 · 내려받기 카드 0(검증 ③ B1 → TRW14 Q7)', async () => {
    const server = twoParts();
    server.advance(30, {
      status: 'done',
      files: { bilingual: true, qa: false, autofix: true },
    });
    draw(server, { part: 'ceo' });
    const dialog = await openDownloads();
    expect(disabledOf('review')).toBe('true');
    expect(disabledOf('bilingual')).toBeNull();
    expect(disabledOf('autofix')).toBeNull();
    expect(
      screen
        .getByTestId('part-download-dialog-help-review')
        .getAttribute('aria-label'),
    ).toContain(TR_TEXT.result.fileMissing.review);
    for (const key of ['bilingual', 'review', 'autofix'] as const)
      expect(dialog.textContent).toContain(TR_TEXT.result.fileNotes[key]);
    expect(dialog.textContent).toContain(TR_TEXT.result.wordNote);
    expect(screen.queryByTestId('downloads')).toBeNull();
  });

  it('[모두 받기] 409 too_large → 판 글 하나, 단추 실패 글 0', async () => {
    const server = twoParts();
    server.settings.archiveTooLarge = true;
    server.advance(30, { status: 'done' });
    draw(server);
    const button = await waitFor(
      () => screen.getByTestId('download-all'),
      WAIT,
    );
    fireEvent.click(button);
    await waitFor(
      () => expect(screen.getByText(TR_TEXT.all.archiveTooLarge)).toBeTruthy(),
      WAIT,
    );
    expect(screen.getByTestId('download-all-error').textContent).toBe('');
    expect(saved).toEqual([]);
  });

  it('[모두 받기] 409 NO_FINISHED_PARTS → 받을 것 없음 글(끈 단추와 같은 글), 단추 실패 글 0', async () => {
    const server = twoParts();
    server.advance(30, { status: 'done' });
    // 화면이 단추를 켠 뒤 서버 쪽에서 받을 것이 사라진 경합(TRP1 W4).
    server.override[`GET /translation/documents/12/batches/${BATCH}/archive`] =
      () => refusal(409, 'NO_FINISHED_PARTS');
    draw(server);
    fireEvent.click(
      await waitFor(() => screen.getByTestId('download-all'), WAIT),
    );
    await waitFor(
      () =>
        expect(screen.getByTestId('archive-error').textContent).toBe(
          TR_TEXT.all.noFiles,
        ),
      WAIT,
    );
    expect(screen.getByTestId('download-all-error').textContent).toBe('');
    expect(saved).toEqual([]);
  });

  it('[모두 받기] 빠짐 2 → zip 받고 빠짐 글', async () => {
    const server = twoParts();
    server.settings.archiveMissing = '2';
    server.advance(30, { status: 'done' });
    draw(server);
    fireEvent.click(
      await waitFor(() => screen.getByTestId('download-all'), WAIT),
    );
    await waitFor(
      () =>
        expect(screen.getByText(TR_TEXT.all.archiveMissing(2))).toBeTruthy(),
      WAIT,
    );
    expect(saved).toEqual([`translation-12-${BATCH.slice(0, 8)}.zip`]);
  });

  it('404 → 찾을 수 없음([목록으로])', async () => {
    const { onBack } = draw(twoParts(), {
      batchKey: 'aaaaaaaa-0000-4000-8000-000000000000',
    });
    await waitFor(
      () => expect(screen.getByText(TR_TEXT.run.missing)).toBeTruthy(),
      WAIT,
    );
    fireEvent.click(screen.getByRole('button', { name: TR_TEXT.run.back }));
    expect(onBack).toHaveBeenCalled();
  });

  it('일부만 시작 → 띠(실제 파트 이름), 못 만든 파트 탭은 실패 카드 단추 0', async () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH))],
    });
    draw(server, {
      part: 'general',
      notStarted: { started: ['ceo'], failed: ['general'] },
    });
    await waitFor(
      () =>
        expect(screen.getByTestId('partial-start').textContent).toBe(
          TR_TEXT.partialStart(['CEO 메시지'], ['일반']),
        ),
      WAIT,
    );
    // 일부 시작 띠는 주황(important) — 하나도 못 시작한 TR-02 의 빨강과 다르다(TRP1 W2, 디자인 2e 답).
    expect(screen.getByTestId('partial-start').getAttribute('data-tone')).toBe(
      'important',
    );
    expect(
      screen.getByText(TR_TEXT.rejection.no_pages.reason, { exact: false }),
    ).toBeTruthy();
    expect(screen.queryByText(TR_TEXT.failure.retryPart)).toBeNull();
  });

  it('요약 없는 끝난 파트(옛 실행) 수치는 「–」(0 아님)', async () => {
    const server = twoParts();
    server.advance(30, { status: 'done', noDigest: true });
    server.advance(31, { status: 'done' });
    draw(server);
    await waitFor(
      () => expect(screen.getByText(TR_TEXT.all.title)).toBeTruthy(),
      WAIT,
    );
    await flush();
    const tiles = [...document.querySelectorAll('[data-stat]')].map(
      (tile) => tile.textContent ?? '',
    );
    expect(tiles.some((text) => text.includes(TR_TEXT.stats.none))).toBe(true);
  });
});

// [TRP2 TE10] 고른 탭이 진행·대기면 탭 줄과 진행 카드가 한 카드. 감싸개는 늘 같은 요소(critic B1 — ←/→ 초점이 빠지지 않게).
describe('RunScreen 한 카드(TRP2 TE10)', () => {
  /** 탭을 누르면 주소 값이 바뀌는 것처럼 part 를 들고 있는 감싸개. */
  function Routed({ server }: { server: Server }) {
    const [part, setPart] = useState<PartTabKey>('ceo');
    return (
      <RunScreen
        store={serverStoreOf(server, { pollMs: 20 })}
        documentId="12"
        batchKey={BATCH}
        part={part}
        onTab={setPart}
        onBack={() => {}}
      />
    );
  }
  const panel = () => screen.getByTestId('part-panel');

  it('대기 탭: tablist 와 stage-card 가 같은 카드 안 → ArrowRight 로 끝남 탭: 카드 꼴 빠짐, 초점은 끝남 탭 단추, 감싸개는 같은 요소', async () => {
    const server = twoParts();
    server.advance(31, { status: 'done' });
    render(<Routed server={server} />);
    await waitFor(
      () => expect(screen.getByTestId('stage-card')).toBeTruthy(),
      WAIT,
    );
    const first = panel();
    expect(first.getAttribute('data-one-card')).toBe('true');
    expect(first.className.split(/\s+/)).toEqual(
      expect.arrayContaining([
        'rounded-dialog',
        'bg-background-primary',
        'p-8',
      ]),
    );
    expect(first.contains(screen.getByRole('tablist'))).toBe(true);
    expect(first.contains(screen.getByTestId('stage-card'))).toBe(true);
    // 진행 카드는 bare(div) — 카드 안에 카드 없음.
    expect(screen.getByTestId('stage-card').tagName).toBe('DIV');

    const ceoTab = screen.getByRole('tab', { selected: true });
    act(() => ceoTab.focus());
    fireEvent.keyDown(ceoTab, { key: 'ArrowRight' });
    await waitFor(() =>
      expect(
        screen.getByRole('tab', { selected: true }).getAttribute('data-tab'),
      ).toBe('story'),
    );
    expect(document.activeElement?.getAttribute('data-tab')).toBe('story');
    expect(panel()).toBe(first);
    expect(panel().getAttribute('data-one-card')).toBeNull();
    expect(panel().className).not.toMatch(/rounded-dialog/);
    expect(screen.queryByTestId('stage-card')).toBeNull();
  });
});

// 밴드 TRP4 ②-6·②-9: 일부 시작 띠 gw-m-rise · 진행 → 결과면 결과 맨 위 div 가 gw-m-fade 로 새로 붙음 ·
//   A·B 견주기에서 스타일 탭 A → B 는 그 div 만 새 노드(결과 다시 부름 0 — 키는 FinishedPart 가 아니라 맨 위 div 에).
describe('RunScreen 움직임(TRP4)', () => {
  /** 결과 자리의 맨 위 div(FinishedPart) — 수 칸에서 가장 가까운 gw-m-fade. */
  const resultTop = () =>
    document.querySelector('[data-stat]')?.closest('.gw-m-fade') ?? null;

  it('ⓐ 일부 시작 띠에 gw-m-rise', async () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH))],
    });
    draw(server, {
      part: 'general',
      notStarted: { started: ['ceo'], failed: ['general'] },
    });
    await waitFor(
      () => expect(screen.getByTestId('partial-start')).toBeTruthy(),
      WAIT,
    );
    expect(
      screen.getByTestId('partial-start').classList.contains('gw-m-rise'),
    ).toBe(true);
  });

  it('ⓑ 진행 파트가 끝나면 결과 자리의 맨 위 div 에 gw-m-fade, stage-card 는 없다', async () => {
    const server = twoParts();
    server.advance(30, { status: 'done' });
    draw(server, { part: 'story' });
    await waitFor(
      () => expect(screen.getByTestId('stage-card')).toBeTruthy(),
      WAIT,
    );
    expect(resultTop()).toBeNull();
    // 밴드 WT1(sid:MARC-ENT-625, 시안 v233 TR-03): 진행 카드의 안심 줄(「몇 페이지를 못 옮겨도…」) 지움 · 머리 「이 창을 닫아도 번역은 계속돼요」 그대로.
    expect(screen.queryByTestId('stage-caution')).toBeNull();
    expect(screen.queryByText(/몇 페이지를 못 옮겨도/)).toBeNull();
    expect(document.body.textContent).toContain(TR_TEXT.stage.keepsRunning);
    server.advance(31, { status: 'done' });
    await waitFor(() => expect(resultTop()).not.toBeNull(), WAIT);
    expect(resultTop()!.classList.contains('gw-m-fade')).toBe(true);
    expect(screen.queryByTestId('stage-card')).toBeNull();
  });

  it('ⓒ A·B 견주기 결과에서 스타일 탭 A → B: 맨 위 div 는 새 노드, 결과 부름 수는 그대로', async () => {
    const compare = { style: { compareAb: true, single: 'B' } };
    const server = fakeTranslationServer({
      documents: [fakeDocument(12, { fileName: 'sample_a_extract.txt' })],
      runs: [
        fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH, compare)),
        fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH, compare)),
      ],
    });
    server.advance(30, { status: 'done' });
    server.advance(31, { status: 'done' });
    draw(server, { part: 'story' });
    await waitFor(
      () => expect(screen.getByText(TR_TEXT.issues.title)).toBeTruthy(),
      WAIT,
    );
    const key = 'GET /translation/runs/31/result';
    const calls = server.count(key);
    expect(calls).toBeGreaterThan(0);
    const before = resultTop()!;
    expect(before.classList.contains('gw-m-fade')).toBe(true);
    const tabB = screen.getByRole('tab', {
      name: TR_TEXT.run.styleTab('B'),
    });
    fireEvent.mouseDown(tabB);
    await waitFor(() =>
      expect(tabB.getAttribute('aria-selected')).toBe('true'),
    );
    await waitFor(() => expect(resultTop()).not.toBe(before));
    expect(resultTop()!.classList.contains('gw-m-fade')).toBe(true);
    await flush();
    expect(server.count(key)).toBe(calls);
  });
});

// 밴드 TRP5(sid:MARC-ENT-443 ④ · 6c TRP4 재대조 ②): 묶음을 받기 전 제목·설명 자리 + [목록으로] + 단계 띠, 본문 LoadSkeleton 은 300ms 뒤 ·
//   파트 결과 LoadSkeleton 도 300ms 뒤 · 파트 탭을 바로 오가도(전체 탭 안 거침) 처음 보는 파트는 0 에서, 다시 온 파트는 끝 값부터.
describe('RunScreen 첫 불러오기 · 굴림(TRP5)', () => {
  /** 저장소의 한 부름을 release() 때까지 붙잡는다. */
  function holding(server: Server, what: 'subscribeBatch' | 'getResult') {
    const real = serverStoreOf(server, { pollMs: 20 });
    let release = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    const store: typeof real =
      what === 'getResult' ?
        {
          ...real,
          getResult: async (runId) => {
            await gate;
            return real.getResult(runId);
          },
        }
      : {
          ...real,
          subscribeBatch: (...args) => {
            let off = () => {};
            let gone = false;
            void gate.then(() => {
              if (!gone) off = real.subscribeBatch(...args);
            });
            return () => {
              gone = true;
              off();
            };
          },
        };
    return {
      store,
      release: () =>
        act(async () => {
          release();
        }),
    };
  }
  const screenRoot = () =>
    document.querySelector<HTMLElement>('[data-screen="translation-run"]')!;
  const stepFlow = () =>
    screen.getByRole('list', { name: TR_TEXT.newTranslation.stepsLabel });

  it('A-3 묶음 받기 전: 제목·설명 자리 + [목록으로] + 단계 띠(지금 단계 없음), 본문 스켈레톤은 300ms 뒤 → 받으면 같은 자리에 제목 글, 단계 띠는 둘째 그대로', async () => {
    const server = twoParts();
    server.advance(30, { status: 'done' });
    const { store, release } = holding(server, 'subscribeBatch');
    const onBack = vi.fn();
    render(
      <RunScreen
        store={store}
        documentId="12"
        batchKey={BATCH}
        part="story"
        onTab={() => {}}
        onBack={onBack}
      />,
    );
    expect(screen.getByTestId('title-pending')).toBeTruthy();
    expect(screen.getByTestId('description-pending')).toBeTruthy();
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    expect(stepFlow().querySelector('[aria-current]')).toBeNull();
    expect(screenRoot().children[1]).toBe(stepFlow());
    fireEvent.click(screen.getByRole('button', { name: TR_TEXT.run.back }));
    expect(onBack).toHaveBeenCalledTimes(1);
    await waitFor(
      () => expect(screen.getByTestId('load-skeleton')).toBeTruthy(),
      WAIT,
    );
    await release();
    await waitFor(
      () => expect(screen.getByText(TR_TEXT.screenTitle.running)).toBeTruthy(),
      WAIT,
    );
    expect(screen.queryByTestId('title-pending')).toBeNull();
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    expect(
      screen.getByRole('heading', { name: TR_TEXT.screenTitle.running }),
    ).toBe(screenRoot().querySelector('h2'));
    expect(screenRoot().children[1]).toBe(stepFlow());
    expect(stepFlow().querySelector('[aria-current="step"]')).not.toBeNull();
  });

  it('A-4 파트 결과 읽는 중: 300ms 전에는 스켈레톤 없음(수 칸은 있음), 뒤에 스켈레톤 → 받으면 사라짐', async () => {
    const server = twoParts();
    server.advance(30, { status: 'done' });
    server.advance(31, { status: 'done' });
    const { store, release } = holding(server, 'getResult');
    render(
      <RunScreen
        store={store}
        documentId="12"
        batchKey={BATCH}
        part="story"
        onTab={() => {}}
        onBack={() => {}}
      />,
    );
    await waitFor(
      () => expect(document.querySelector('[data-stat]')).not.toBeNull(),
      WAIT,
    );
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    await waitFor(
      () => expect(screen.getByTestId('load-skeleton')).toBeTruthy(),
      WAIT,
    );
    await release();
    await waitFor(
      () => expect(screen.getByText(TR_TEXT.issues.title)).toBeTruthy(),
      WAIT,
    );
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
  });

  it('B-2 움직임 켬: 파트 탭을 바로 오감(ceo → story → ceo) — 처음 보는 story 는 0 에서, 돌아온 ceo 는 첫 그림부터 끝 값', async () => {
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
    // 다른 시험과 기억 열쇠(묶음 id/파트)가 겹치지 않게 이 시험만의 묶음.
    const key = '5e6f7a8b-9c0d-4e1f-8a2b-3c4d5e6f7a8b';
    const server = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [
        fakeRun(40, 12, fakeOptions('ceo_message', 1, 3, key), {
          status: 'processing',
          steps: fakeSteps(1, { status: 'running', done: 3, total: 3 }),
        }),
        fakeRun(41, 12, fakeOptions('story', 4, 9, key), {
          status: 'processing',
          steps: fakeSteps(1, { status: 'running', done: 5, total: 6 }),
        }),
      ],
    });
    const store = serverStoreOf(server, { pollMs: 20 });
    const at = (part: PartTabKey) => (
      <RunScreen
        store={store}
        documentId="12"
        batchKey={key}
        part={part}
        onTab={() => {}}
        onBack={() => {}}
      />
    );
    const pages = () => screen.getByTestId('stage-pages').textContent;
    try {
      const { rerender } = render(at('ceo'));
      await waitFor(
        () => expect(screen.getByTestId('stage-pages')).toBeTruthy(),
        WAIT,
      );
      await waitFor(() => expect(pages()).toBe(TR_TEXT.stage.pages(3, 3)));
      rerender(at('story'));
      expect(pages()).toBe(TR_TEXT.stage.pages(0, 6));
      await waitFor(() => expect(pages()).toBe(TR_TEXT.stage.pages(5, 6)));
      rerender(at('ceo'));
      expect(pages()).toBe(TR_TEXT.stage.pages(3, 3));
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

// [밴드 TRW1b §3-1 5·6] [이 파트만 다시](결정 sid:MARC-ENT-393) · 띠가 서버 묶음과 맞춤.
describe('RunScreen [이 파트만 다시] (TRW1b)', () => {
  /** 새 실행 id 가 앞 실행보다 크게(묶음의 최신 회차). */
  const seeded = (
    runs: ReturnType<typeof fakeRun>[],
  ): ReturnType<typeof fakeTranslationServer> =>
    fakeTranslationServer({
      documents: [fakeDocument(12, { fileName: 'sample_a_extract.txt' })],
      runs,
      nextRunId: 40,
    });
  const failedStory = () =>
    seeded([
      fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
      fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH)),
    ]);
  const posts = (server: Server) => server.count('POST /runs');

  it('서버 오류 파트(파트 둘) → [이 파트만 다시] 두 번 눌러도 POST 한 번 → 그 탭 「진행 중」·스켈레톤 0·탭 그대로', async () => {
    const server = failedStory();
    server.advance(30, { status: 'done' });
    server.advance(31, { status: 'failed', errorCode: 'step_error' });
    const { onTab } = draw(server, { part: 'story' });
    const button = await screen.findByRole(
      'button',
      { name: TR_TEXT.failure.retryPart },
      WAIT,
    );
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(
      () => expect(screen.getByTestId('stage-card')).toBeTruthy(),
      WAIT,
    );
    expect(posts(server)).toBe(1);
    expect(server.count('GET /runs/31')).toBe(1);
    expect(server.runBodies()[0]!.options).toEqual(
      server.runs.get(31)!.options,
    );
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    expect(screen.queryByTestId('part-failure')).toBeNull();
    expect(onTab).not.toHaveBeenCalled();
    expect(screen.getByText(TR_TEXT.screenTitle.running)).toBeTruthy();
  });

  it('보내는 동안 단추 꺼짐(retrying)', async () => {
    const server = failedStory();
    server.advance(31, { status: 'failed', errorCode: 'step_error' });
    let release: () => void = () => {};
    server.override['GET /runs/31'] = () =>
      new Promise<Response>((resolve) => {
        release = () => resolve(refusal(404, 'NOT_FOUND'));
      });
    draw(server, { part: 'story' });
    const button = await screen.findByRole(
      'button',
      { name: TR_TEXT.failure.retryPart },
      WAIT,
    );
    fireEvent.click(button);
    await waitFor(() => expect(button.hasAttribute('disabled')).toBe(true));
    await act(async () => release());
    await waitFor(() => expect(button.hasAttribute('disabled')).toBe(false));
  });

  it('파트 하나(서버 오류) → [다시 실행]', async () => {
    const server = seeded([fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH))]);
    server.advance(31, { status: 'failed', errorCode: 'step_error' });
    draw(server);
    expect(
      await screen.findByRole(
        'button',
        { name: TR_TEXT.failure.retrySingle },
        WAIT,
      ),
    ).toBeTruthy();
    expect(screen.queryByText(TR_TEXT.failure.retryPart)).toBeNull();
  });

  // [밴드 TRW4] 마크스폰 댓글: 「2쪽 실패」가 2곳인지 2번째인지 헷갈림 → 단계 줄은 개수, 번호는 번역하지 못한 페이지 칸 아래.
  it('일부 페이지 실패 2곳 → 단계 줄 「실패한 페이지 2개」, 칸 아래 「5 · 9페이지」', async () => {
    const server = failedStory();
    server.advance(30, { status: 'done' });
    server.advance(31, {
      status: 'done',
      outcome: 'partial',
      failedPages: [5, 9],
    });
    draw(server, { part: 'story' });
    await waitFor(
      () => expect(screen.getByText('실패한 페이지 2개')).toBeTruthy(),
      WAIT,
    );
    expect(screen.getByText('5 · 9페이지')).toBeTruthy();
    expect(screen.queryByText(/\d쪽/)).toBeNull();
  });

  it('일부 쪽 파트 → 결과 머리에 [이 파트만 다시] → POST 한 번', async () => {
    const server = failedStory();
    server.advance(30, { status: 'done' });
    server.advance(31, { status: 'done', outcome: 'partial' });
    draw(server, { part: 'story' });
    await waitFor(
      () => expect(screen.getByTestId('part-result')).toBeTruthy(),
      WAIT,
    );
    const header = screen.getByTestId('part-result');
    const button = Array.from(header.querySelectorAll('button')).find(
      (b) => b.textContent === TR_TEXT.failure.retryPart,
    );
    expect(button).toBeDefined();
    fireEvent.click(button!);
    await waitFor(
      () => expect(screen.getByTestId('stage-card')).toBeTruthy(),
      WAIT,
    );
    expect(posts(server)).toBe(1);
  });

  it('거절 파트·`run-` 열쇠 묶음 → 다시 단추 0', async () => {
    const refused = failedStory();
    refused.advance(31, {
      status: 'done',
      outcome: 'rejected',
      rejectionKind: 'too_large',
    });
    draw(refused, { part: 'story' });
    await waitFor(
      () => expect(screen.getByTestId('part-failure')).toBeTruthy(),
      WAIT,
    );
    expect(screen.queryByText(TR_TEXT.failure.retryPart)).toBeNull();
    cleanup();
    const old = seeded([fakeRun(31, 12, fakeOptions('story', 4, 9, null))]);
    old.advance(31, { status: 'failed', errorCode: 'step_error' });
    draw(old, { batchKey: 'run-31' });
    await waitFor(
      () =>
        expect(
          screen.getByText(TR_TEXT.failure.serverError, { exact: false }),
        ).toBeTruthy(),
      WAIT,
    );
    expect(screen.queryByText(TR_TEXT.failure.retrySingle)).toBeNull();
    expect(screen.queryByText(TR_TEXT.failure.retryPart)).toBeNull();
  });

  it('POST 거절 → 단추 아래 retryFailed 한 줄 + 단추 다시 켜짐 · 다시 누르면 글이 걷힘', async () => {
    const server = failedStory();
    server.advance(31, { status: 'failed', errorCode: 'step_error' });
    server.override['POST /runs'] = [() => refusal(400, 'INVALID_OPTIONS')];
    draw(server, { part: 'story' });
    const button = await screen.findByRole(
      'button',
      { name: TR_TEXT.failure.retryPart },
      WAIT,
    );
    fireEvent.click(button);
    await waitFor(
      () =>
        expect(screen.getByTestId('retry-failed').textContent).toBe(
          TR_TEXT.failure.retryFailed,
        ),
      WAIT,
    );
    expect(button.hasAttribute('disabled')).toBe(false);
    fireEvent.click(button);
    await waitFor(
      () => expect(screen.getByTestId('stage-card')).toBeTruthy(),
      WAIT,
    );
    expect(screen.queryByTestId('retry-failed')).toBeNull();
    expect(posts(server)).toBe(2);
  });

  it('띠: 기억에 failed=[일반] 인데 서버 묶음에 일반이 있음 → 띠 0', async () => {
    const server = seeded([
      fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
      fakeRun(32, 12, fakeOptions('general', 10, 12, BATCH)),
    ]);
    draw(server, { notStarted: { started: ['ceo'], failed: ['general'] } });
    await waitFor(
      () => expect(screen.getByTestId('part-panel')).toBeTruthy(),
      WAIT,
    );
    expect(screen.queryByTestId('partial-start')).toBeNull();
  });

  it('띠: 못 한 둘 가운데 하나만 서버에 있음 → 그 이름은 시작함 쪽', async () => {
    const server = seeded([
      fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
      fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH)),
    ]);
    draw(server, {
      notStarted: { started: ['ceo'], failed: ['story', 'general'] },
    });
    await waitFor(
      () =>
        expect(screen.getByTestId('partial-start').textContent).toBe(
          TR_TEXT.partialStart(['CEO 메시지', '스토리'], ['일반']),
        ),
      WAIT,
    );
  });
});

// 밴드 TRW2(sid:MARC-ISSUE-380 · 6c 10-26): A·B 견주기 [전체] 탭은 파트 탭의 스타일 고름을 따르지 않는다 —
//   수 칸·표 수치는 「A / B」, [Word] 자리는 [Word A]·[Word B](각 스타일의 자동 수정 병기본, 없는 스타일은 단추 0) · 한 스타일은 그대로.
describe('RunScreen A·B 견주기 [전체] 탭(TRW2)', () => {
  const compare = { style: { compareAb: true, single: 'B' } };
  type Variant = {
    label: string;
    issueCount: number;
    glossaryMisses: number;
    autofixChangedPages: number;
    files: { autofix: string | null };
  };
  /** 끝난 실행 요약의 그 스타일(가짜 서버는 A·B 수가 같아 시험마다 다르게 고친다). */
  const variantOf = (server: Server, runId: number, label: 'A' | 'B') =>
    (server.runs.get(runId)!.digest as { variants: Variant[] }).variants.find(
      (v) => v.label === label,
    )!;
  const setNumbers = (
    variant: Variant,
    issues: number,
    misses: number,
    fixed: number,
  ) => {
    variant.issueCount = issues;
    variant.glossaryMisses = misses;
    variant.autofixChangedPages = fixed;
  };
  // A 합: 이슈 12 · 미반영 1 · 자동 수정 3 / B 합: 7 · 5 · 1
  const compareServer = () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12, { fileName: 'sample_a_extract.txt' })],
      runs: [
        fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH, compare)),
        fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH, compare)),
      ],
    });
    server.advance(30, { status: 'done' });
    server.advance(31, { status: 'done' });
    setNumbers(variantOf(server, 30, 'A'), 5, 1, 1);
    setNumbers(variantOf(server, 30, 'B'), 3, 2, 0);
    setNumbers(variantOf(server, 31, 'A'), 7, 0, 2);
    setNumbers(variantOf(server, 31, 'B'), 4, 3, 1);
    return server;
  };
  function Routed({ server, from }: { server: Server; from: PartTabKey }) {
    const [part, setPart] = useState<PartTabKey>(from);
    return (
      <RunScreen
        store={serverStoreOf(server, { pollMs: 20 })}
        documentId="12"
        batchKey={BATCH}
        part={part}
        onTab={setPart}
        onBack={() => {}}
      />
    );
  }
  const tile = (key: string) => document.querySelector(`[data-stat="${key}"]`)!;
  const tileValue = (key: string) =>
    tile(key).querySelector('[data-testid="stat-value"]')!.textContent;
  const cell = (part: string, id: string) =>
    document
      .querySelector(`[data-part="${part}"]`)!
      .closest('tr')!
      .querySelector(`[data-cell="${id}"]`)!.textContent;
  const sep = TR_TEXT.stats.pairSeparator;

  /** A·B 수치와 단추 둘을 한꺼번에 본다(B 로 바꿨다 돌아온 뒤에도 같은 단언). */
  const expectBoth = () => {
    expect(tileValue('issues')).toBe(`12${sep}7`);
    expect(tileValue('glossaryMiss')).toBe(`1${sep}5`);
    expect(tile('issues').textContent).toContain(
      TR_TEXT.stats.notes.issuesBasis([3, 1]),
    );
    expect(tile('glossaryMiss').textContent).toContain(
      TR_TEXT.stats.pairLabel(TR_TEXT.stats.labels.glossaryMiss),
    );
    expect(cell('ceo', 'issues')).toBe(`5건${sep}3건`);
    expect(cell('ceo', 'misses')).toBe(`1건${sep}2건`);
    expect(cell('ceo', 'fixed')).toBe(`1개${sep}0개`);
    expect(cell('story', 'issues')).toBe(`7건${sep}4건`);
    for (const part of ['ceo', 'story']) {
      expect(screen.getByTestId(`word-${part}-A`).textContent).toContain(
        TR_TEXT.all.wordOf('A'),
      );
      expect(screen.getByTestId(`word-${part}-B`).textContent).toContain(
        TR_TEXT.all.wordOf('B'),
      );
      expect(screen.queryByTestId(`word-${part}`)).toBeNull();
    }
  };

  it('수 칸·파트 줄은 A / B 둘, 표 머리 아랫줄 A / B, [Word A]·[Word B] 는 각 스타일의 자동 수정 병기본을 받음', async () => {
    const server = compareServer();
    draw(server);
    await waitFor(
      () => expect(screen.getByTestId('word-ceo-B')).toBeTruthy(),
      WAIT,
    );
    await waitFor(() => expect(tileValue('issues')).toBe(`12${sep}7`));
    expectBoth();
    expect(
      screen.getByRole('columnheader', {
        name: `${TR_TEXT.all.columns.issues} ${TR_TEXT.all.pairSub}`,
      }),
    ).toBeTruthy();
    fireEvent.click(screen.getByTestId('word-story-B'));
    await waitFor(
      () => expect(saved).toEqual(['translation-autofix-b.docx']),
      WAIT,
    );
    fireEvent.click(screen.getByTestId('word-story-A'));
    await waitFor(
      () =>
        expect(saved).toEqual([
          'translation-autofix-b.docx',
          'translation-autofix-a.docx',
        ]),
      WAIT,
    );
  });

  it('파트 탭에서 스타일 B 로 바꾼 뒤 [전체] 로 돌아와도 A / B 둘 그대로', async () => {
    const server = compareServer();
    render(<Routed server={server} from="story" />);
    const tabB = await screen.findByRole(
      'tab',
      { name: TR_TEXT.run.styleTab('B') },
      WAIT,
    );
    fireEvent.mouseDown(tabB);
    await waitFor(() =>
      expect(tabB.getAttribute('aria-selected')).toBe('true'),
    );
    fireEvent.mouseDown(
      within(
        screen.getByRole('tablist', { name: TR_TEXT.run.tabsLabel }),
      ).getByRole('tab', { name: new RegExp(`^${TR_TEXT.tabs.all}`) }),
    );
    await waitFor(
      () => expect(screen.getByTestId('word-ceo-B')).toBeTruthy(),
      WAIT,
    );
    await waitFor(() => expect(tileValue('issues')).toBe(`12${sep}7`));
    expectBoth();
  });

  it('한 스타일의 자동 수정 병기본이 없으면 그 단추만 없음, 수는 「–」 아님', async () => {
    const server = compareServer();
    variantOf(server, 30, 'B').files.autofix = null;
    draw(server);
    await waitFor(
      () => expect(screen.getByTestId('word-ceo-A')).toBeTruthy(),
      WAIT,
    );
    expect(screen.queryByTestId('word-ceo-B')).toBeNull();
    expect(screen.getByTestId('word-story-B')).toBeTruthy();
    expect(cell('ceo', 'issues')).toBe(`5건${sep}3건`);
  });

  // 검증 R1: [모두 받기] 켬 판정도 숨은 스타일(A)만 보지 않는다.
  it('A 의 자동 수정 병기본이 모두 없고 B 만 있으면 [모두 받기] 켜짐', async () => {
    const server = compareServer();
    for (const runId of [30, 31])
      variantOf(server, runId, 'A').files.autofix = null;
    draw(server);
    await waitFor(
      () => expect(screen.getByTestId('word-ceo-B')).toBeTruthy(),
      WAIT,
    );
    expect(screen.queryByTestId('word-ceo-A')).toBeNull();
    expect(
      screen.getByTestId('download-all').getAttribute('aria-disabled'),
    ).toBeNull();
  });

  it('한 스타일 실행은 그대로: [Word] 하나(글 「Word」) · 표 머리·칸 이름에 A / B 없음', async () => {
    const server = twoParts();
    server.advance(30, { status: 'done' });
    draw(server);
    await waitFor(
      () => expect(screen.getByTestId('word-ceo')).toBeTruthy(),
      WAIT,
    );
    expect(screen.getByTestId('word-ceo').textContent).toContain(
      TR_TEXT.all.word,
    );
    expect(screen.queryByTestId('word-ceo-A')).toBeNull();
    expect(screen.queryByTestId('word-ceo-B')).toBeNull();
    expect(
      screen.getByRole('columnheader', { name: TR_TEXT.all.columns.issues }),
    ).toBeTruthy();
    expect(tile('glossaryMiss').textContent).not.toContain('A / B');
    expect(tileValue('issues')).not.toContain(sep);
  });
});

// PDF 파트(밴드 TRW6 ③ S3 ①): 실행 정보 resultShapes 의 layout@1 → [PDF로 보기] · 표 「자리」 칸 → onOpenPdf(그 자리). 워드 파트는 BASE 그대로.
describe('RunScreen PDF 파트 (TRW6)', () => {
  /** 파트 둘: 30 = PDF(layout 있음 — 「Made-up text」가 BLOCK 1 둘째 번역에), 31 = 워드. */
  function pdfServer({ warnings = [] }: { warnings?: unknown[] } = {}) {
    const layout = fakeLayout(4) as Record<string, unknown> & {
      variants: { label: string; units: Record<string, unknown>[] }[];
    };
    if (warnings.length > 0) layout.warnings = warnings;
    layout.variants[0]!.label = 'single';
    layout.variants[0]!.units[0] = {
      tag: 'BLOCK 1',
      page: 4,
      level: 'block',
      translations: ['Climate Strategy', 'Made-up text about cuts'],
    };
    const server = fakeTranslationServer({
      documents: [fakeDocument(12, { fileName: 'made_up.pdf' })],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 4, 5, BATCH), {
          flowId: 'translation.pdf@158',
        }),
        fakeRun(31, 12, fakeOptions('general', 6, 7, BATCH)),
      ],
    });
    server.advance(30, { status: 'done', layout });
    server.advance(31, { status: 'done' });
    return server;
  }

  function drawPdf(
    server: Server,
    part: PartTabKey,
    returned?: NonNullable<RunScreenProps['returned']>,
  ) {
    const onOpenPdf = vi.fn();
    render(
      <RunScreen
        store={serverStoreOf(server, { pollMs: 20 })}
        documentId="12"
        batchKey={BATCH}
        part={part}
        onTab={vi.fn()}
        onBack={vi.fn()}
        onOpenPdf={onOpenPdf}
        {...(returned === undefined ? {} : { returned })}
      />,
    );
    return onOpenPdf;
  }

  it('[PDF로 보기]는 layout 있는 끝난 파트에만 → onOpenPdf(runId, null)', async () => {
    const server = pdfServer();
    const onOpenPdf = drawPdf(server, 'story');
    await waitFor(() => screen.getByTestId('open-pdf'), WAIT);
    expect(screen.getByTestId('open-pdf').textContent).toBe(
      TR_TEXT.pdfView.open,
    );
    fireEvent.click(screen.getByTestId('open-pdf'));
    expect(onOpenPdf).toHaveBeenCalledWith('30', null);
  });

  it('검수 이슈 「자리」: 붙은 줄 → 그 쪽·그 짝(띠 글 재료), 못 붙은 줄 → 그 쪽만 · 용어 줄은 띠 없음', async () => {
    const server = pdfServer();
    const onOpenPdf = drawPdf(server, 'story');
    await waitFor(
      () => expect(screen.getAllByTestId('qa-issue-place')).toHaveLength(2),
      WAIT,
    );
    const places = screen.getAllByTestId('qa-issue-place');
    // 쪽 4: 짝 자리 1(BLOCK 1 둘째 member) — 「4페이지 둘째 문단」. 쪽 5 는 layout 에 없어 그 쪽만.
    expect(places.map((place) => place.textContent)).toEqual([
      TR_TEXT.pdfView.placeUnit(4, 2),
      TR_TEXT.pdfView.placeWhole(5),
    ]);
    fireEvent.click(places[0]!);
    expect(onOpenPdf).toHaveBeenLastCalledWith(
      '30',
      {
        page: 4,
        pair: 1,
        label: 'single',
        from: {
          where: TR_TEXT.pdfView.placeUnit(4, 2),
          type: TR_TEXT.issues.types.unnatural,
        },
      },
      { table: 'issues', index: 0 },
    );
    fireEvent.click(places[1]!);
    expect(onOpenPdf).toHaveBeenLastCalledWith(
      '30',
      {
        page: 5,
        pair: null,
        label: 'single',
        from: {
          where: TR_TEXT.pdfView.placeWhole(5),
          type: TR_TEXT.issues.types.unnatural,
        },
      },
      { table: 'issues', index: 1 },
    );
    // 용어 「지어낸용어」는 원문에 없어 그 쪽만 · 띠 없음.
    fireEvent.click(screen.getByTestId('glossary-miss-place'));
    expect(onOpenPdf).toHaveBeenLastCalledWith(
      '30',
      {
        page: 4,
        pair: null,
        label: 'single',
        from: null,
      },
      { table: 'misses', index: 0 },
    );
  });

  // 검증 B1·R12: 견주기 — 짝 자리는 고른 문체로 세고 표식에 그 문체를 싣는다(A block 둘 · B group 하나).
  it('견주기: B 탭의 「자리」는 B 의 짝 자리 + label B · 용어 둘째 줄은 그 줄의 짝', async () => {
    const layout = fakeLayout(4) as Record<string, unknown> & {
      variants: Record<string, unknown>[];
    };
    const a = layout.variants[0] as { units: Record<string, unknown>[] };
    a.units[0] = {
      tag: 'BLOCK 1',
      page: 4,
      level: 'block',
      translations: ['Climate Strategy', 'Made-up text about cuts'],
    };
    layout.variants.push({
      label: 'B',
      stage: 'translated',
      units: [
        {
          tag: 'BLOCK 1',
          page: 4,
          level: 'group',
          translations: ['Merged Made-up text'],
        },
        a.units[1],
        a.units[2],
      ],
      unplaced: [],
    });
    const compare = { style: { compareAb: true, single: 'B' } };
    const server = fakeTranslationServer({
      documents: [fakeDocument(12, { fileName: 'made_up.pdf' })],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 4, 4, BATCH, compare), {
          flowId: 'translation.pdf@158',
        }),
      ],
    });
    server.advance(30, { status: 'done', layout });
    // 용어 두 줄(원문 BLOCK 1 의 첫·둘째 member 에 하나씩).
    const result = server.runs.get(30)!.result as {
      variants: { glossaryCheck: Record<string, unknown>[] }[];
    };
    for (const variant of result.variants)
      variant.glossaryCheck = [
        { pageNum: 4, termKo: '기후', termEn: 'Climate', sourceCount: 1 },
        {
          pageNum: 4,
          termKo: '지어낸 회사',
          termEn: 'Made-up Co.',
          sourceCount: 1,
        },
      ];
    const onOpenPdf = drawPdf(server, 'story');
    await waitFor(
      () =>
        expect(screen.getAllByTestId('glossary-miss-place')).toHaveLength(2),
      WAIT,
    );
    // A: 이슈는 둘째 문단(짝 1) · 용어 둘째 줄 → 짝 1.
    fireEvent.click(screen.getAllByTestId('glossary-miss-place')[1]!);
    expect(onOpenPdf).toHaveBeenLastCalledWith(
      '30',
      {
        page: 4,
        pair: 1,
        label: 'A',
        from: null,
      },
      { table: 'misses', index: 1 },
    );
    fireEvent.click(screen.getByTestId('qa-issue-place'));
    expect(onOpenPdf).toHaveBeenLastCalledWith(
      '30',
      expect.objectContaining({ page: 4, pair: 1, label: 'A' }),
      { table: 'issues', index: 0 },
    );
    const tabB = screen.getByRole('tab', { name: TR_TEXT.run.styleTab('B') });
    fireEvent.mouseDown(tabB, { button: 0 });
    await waitFor(() =>
      expect(tabB.getAttribute('aria-selected')).toBe('true'),
    );
    // B: 묶음 하나(짝 0) — 「4페이지 첫째 문단」.
    await waitFor(
      () =>
        expect(screen.getByTestId('qa-issue-place').textContent).toBe(
          TR_TEXT.pdfView.placeUnit(4, 1),
        ),
      WAIT,
    );
    fireEvent.click(screen.getByTestId('qa-issue-place'));
    expect(onOpenPdf).toHaveBeenLastCalledWith(
      '30',
      expect.objectContaining({ page: 4, pair: 0, label: 'B' }),
      { table: 'issues', index: 0 },
    );
  });

  // 밴드 TRW7 ② W5 ⓕ: 돌아온 줄 — 그 실행·문체·표의 그 줄만 data-returned, 옅은 파랑 꼴은 표 바깥 클래스(DataTable 줄 클래스 없음).
  it('returned: 그 실행의 이슈 둘째 줄만 data-returned · 강조 꼴 · 용어 표 0', async () => {
    const server = pdfServer();
    drawPdf(server, 'story', {
      runId: '30',
      label: 'single',
      table: 'issues',
      index: 1,
    });
    await waitFor(() => screen.getAllByTestId('qa-issue-place'), WAIT);
    const rows = [
      ...screen.getByTestId('qa-issues').querySelectorAll('tbody tr'),
    ];
    expect(rows.map((row) => row.hasAttribute('data-returned'))).toEqual([
      false,
      true,
    ]);
    const wrap = rows[1]!.closest('table')!.parentElement!;
    expect(wrap.className).toContain('[&_tr[data-returned]>td]:bg-blue-100');
    expect(wrap.className).toContain(
      'shadow-[inset_3px_0_0_theme(colors.blue.600)]',
    );
    expect(
      screen.getByTestId('glossary-miss').querySelector('tr[data-returned]'),
    ).toBeNull();
  });

  it('returned 가 다른 실행·다른 문체면 강조 0', async () => {
    const server = pdfServer();
    drawPdf(server, 'story', {
      runId: '30',
      label: 'A',
      table: 'issues',
      index: 0,
    });
    await waitFor(() => screen.getAllByTestId('qa-issue-place'), WAIT);
    expect(document.querySelector('tr[data-returned]')).toBeNull();
  });

  it('워드 파트: returned 를 받아도 표 DOM 이 BASE 그대로(줄 표시·바깥 클래스 0)', async () => {
    const plain = pdfServer();
    const first = drawPdf(plain, 'general');
    expect(first).toBeTruthy();
    await waitFor(() => screen.getByTestId('qa-issues-body'), WAIT);
    await flush();
    // radix 의 자동 id(:r4: 꼴)는 그릴 때마다 달라 지운다.
    const html = (testId: string) =>
      screen.getByTestId(testId).innerHTML.replace(/:r[0-9a-z]+:/g, ':r:');
    const before = { issues: html('qa-issues'), misses: html('glossary-miss') };
    cleanup();
    const server = pdfServer();
    drawPdf(server, 'general', {
      runId: '31',
      label: 'single',
      table: 'issues',
      index: 0,
    });
    await waitFor(() => screen.getByTestId('qa-issues-body'), WAIT);
    await flush();
    expect(html('qa-issues')).toBe(before.issues);
    expect(html('glossary-miss')).toBe(before.misses);
  });

  // 밴드 TRW7 ③a W9·W10·D6 (S4).
  describe('PDF 묶음 머리·수 칸·내려받기 글 (TRW7 ③a S4)', () => {
    const header = () =>
      document.querySelector('[data-screen="translation-run"]')!
        .firstElementChild as HTMLElement;

    it('머리: 「PDF」 배지 · [목록으로][PDF로 보기] 차례 · solidBlack · 몸 안 따로 단추 0', async () => {
      const onOpenPdf = drawPdf(pdfServer(), 'story');
      const open = await waitFor(() => screen.getByTestId('open-pdf'), WAIT);
      expect(screen.getAllByTestId('open-pdf')).toHaveLength(1);
      expect(header().contains(open)).toBe(true);
      expect(open.className).toContain('bg-button-black');
      const buttons = [...open.parentElement!.querySelectorAll('button')];
      expect(buttons.map((b) => b.textContent)).toEqual([
        TR_TEXT.run.back,
        TR_TEXT.pdfView.open,
      ]);
      expect(within(header()).getByTestId('run-pdf-mark').textContent).toBe(
        TR_TEXT.list.pdfMark,
      );
      fireEvent.click(open);
      expect(onOpenPdf).toHaveBeenLastCalledWith('30', null);
    });

    it('[전체] 탭의 [PDF로 보기] → 첫 끝난 PDF 파트 · 워드 파트 탭에선 단추 0(배지는 남음)', async () => {
      const onOpenPdf = drawPdf(pdfServer(), 'all');
      fireEvent.click(
        await waitFor(() => screen.getByTestId('open-pdf'), WAIT),
      );
      expect(onOpenPdf).toHaveBeenLastCalledWith('30', null);
      cleanup();
      drawPdf(pdfServer(), 'general');
      await waitFor(() => screen.getByTestId('qa-issues-body'), WAIT);
      await flush();
      expect(screen.queryByTestId('open-pdf')).toBeNull();
      expect(screen.getByTestId('run-pdf-mark')).toBeTruthy();
    });

    it('[전체] 수 칸 다섯 — 확인할 곳 == 보기의 셈 · 누르면 그 파트·첫 쪽·「확인할 곳」 거르기', async () => {
      const warnings = [
        { code: 'tag_missing', page: 4, tag: 'BLOCK 3', variant: 'single' },
        { code: 'tag_extra', page: 4, tag: null, variant: 'single' },
      ];
      const server = pdfServer({ warnings });
      const onOpenPdf = drawPdf(server, 'all');
      const tile = await waitFor(() => {
        const found = document.querySelector('[data-stat="checks"]');
        expect(found?.querySelector('[data-testid="stat-open"]')).toBeTruthy();
        return found as HTMLElement;
      }, WAIT);
      expect(
        [...document.querySelectorAll('[data-stat]')].map((li) =>
          li.getAttribute('data-stat'),
        ),
      ).toEqual([
        'translated',
        'untranslated',
        'checks',
        'glossaryMiss',
        'issues',
      ]);
      expect(tile.parentElement!.className).toContain('lg:grid-cols-5');
      expect(tile.textContent).toContain(TR_TEXT.stats.labels.checks);
      expect(tile.textContent).toContain(TR_TEXT.stats.notes.checks(1));
      await waitFor(() =>
        expect(
          tile.querySelector('[data-testid="stat-value"]')!.textContent,
        ).toBe('2'),
      );
      fireEvent.click(tile.querySelector('[data-testid="stat-open"]')!);
      expect(onOpenPdf).toHaveBeenLastCalledWith('30', {
        page: 4,
        pair: null,
        label: 'single',
        from: null,
        filter: 'checks',
      });
    });

    it('워드 묶음: 머리 DOM 이 BASE 그대로(배지 0 · [PDF로 보기] 0 · onOpenPdf 유무와 같음)', async () => {
      const wordServer = () => {
        const server = fakeTranslationServer({
          documents: [fakeDocument(12, { fileName: 'made_up.docx' })],
          runs: [fakeRun(31, 12, fakeOptions('general', 6, 7, BATCH))],
        });
        server.advance(31, { status: 'done' });
        return server;
      };
      drawPdf(wordServer(), 'general');
      await waitFor(() => screen.getByTestId('qa-issues-body'), WAIT);
      await flush();
      const withPdf = header().outerHTML;
      expect(screen.queryByTestId('run-pdf-mark')).toBeNull();
      expect(screen.queryByTestId('open-pdf')).toBeNull();
      cleanup();
      draw(wordServer(), { part: 'general' });
      await waitFor(() => screen.getByTestId('qa-issues-body'), WAIT);
      await flush();
      expect(header().outerHTML).toBe(withPdf);
    });

    // [TRW7 ③a D6 → TRW14 ①] 새 설명 글에는 [PAGE n] 이 없어 PDF·워드 가름을 없앴다 — 두 흐름 다 같은 글, 받기는 그 파트 loaders.
    it('PDF 파트 · 워드 파트 받기 모달 설명은 같은 글(「[PAGE n]」 0)', async () => {
      const noteOf = () =>
        screen
          .getByTestId('part-download-dialog')
          .querySelector('[data-file="autofix"]')!.textContent!;
      drawPdf(pdfServer(), 'story');
      fireEvent.click(
        await waitFor(() => screen.getByTestId('part-downloads'), WAIT),
      );
      const pdfNote = noteOf();
      expect(pdfNote).toContain(TR_TEXT.result.fileNotes.autofix);
      expect(pdfNote).not.toContain('[PAGE n]');
      cleanup();
      drawPdf(pdfServer(), 'general');
      fireEvent.click(
        await waitFor(() => screen.getByTestId('part-downloads'), WAIT),
      );
      expect(noteOf()).toBe(pdfNote);
    });
  });

  // 밴드 TRW7 ③b — 디자인 74 답 1·4: 한 파트 PDF 묶음은 파트 탭에 다섯 칸, 「번역한 페이지」 아래 「그림뿐인 n페이지 빼고」.
  describe('PDF 수 칸 — 한 파트 다섯 칸 · 그림뿐인 쪽 글 (TRW7 ③b)', () => {
    /** 30 = PDF 스토리 하나뿐(4~5쪽, 5쪽은 글 층 없음 = 그림뿐) · 4쪽 경고 둘. */
    function singlePdf() {
      const layout = fakeLayout(4) as Record<string, unknown> & {
        pages: Record<string, unknown>[];
        variants: { label: string }[];
      };
      layout.variants[0]!.label = 'single';
      layout.pages.push({
        page: 5,
        width: 595,
        height: 842,
        textLayer: 'none',
      });
      layout.warnings = [
        { code: 'tag_missing', page: 4, tag: 'BLOCK 3', variant: 'single' },
        { code: 'tag_extra', page: 4, tag: null, variant: 'single' },
      ];
      const server = fakeTranslationServer({
        documents: [fakeDocument(12, { fileName: 'made_up.pdf' })],
        runs: [
          fakeRun(30, 12, fakeOptions('story', 4, 5, BATCH), {
            flowId: 'translation.pdf@158',
          }),
        ],
      });
      server.advance(30, { status: 'done', layout });
      return server;
    }
    const statKeys = () =>
      [...document.querySelectorAll('[data-stat]')].map((li) =>
        li.getAttribute('data-stat'),
      );

    it('한 파트: 파트 탭 다섯 칸([전체]와 같음 — 확인할 곳 셋째 · 검수 이슈 다섯째) · lg:grid-cols-5 · 번역한 페이지 아래 「그림뿐인 1페이지 빼고」 · 누름 → 확인할 곳 거르기', async () => {
      const onOpenPdf = drawPdf(singlePdf(), 'story');
      const tile = await waitFor(() => {
        const found = document.querySelector('[data-stat="checks"]');
        expect(found?.querySelector('[data-testid="stat-open"]')).toBeTruthy();
        return found as HTMLElement;
      }, WAIT);
      expect(statKeys()).toEqual([
        'translated',
        'untranslated',
        'checks',
        'glossaryMiss',
        'issues',
      ]);
      expect(tile.parentElement!.className).toContain('lg:grid-cols-5');
      expect(
        tile.querySelector('[data-testid="stat-value"]')!.textContent,
      ).toBe('2');
      expect(tile.textContent).toContain(TR_TEXT.stats.notes.checks(1));
      const translated = document.querySelector('[data-stat="translated"]')!;
      expect(translated.textContent).toContain(
        TR_TEXT.stats.notes.outOfImages(2, 1),
      );
      expect(TR_TEXT.stats.notes.outOfImages(2, 1)).toContain(
        '그림뿐인 1페이지 빼고',
      );
      fireEvent.click(tile.querySelector('[data-testid="stat-open"]')!);
      expect(onOpenPdf).toHaveBeenLastCalledWith('30', {
        page: 4,
        pair: null,
        label: 'single',
        from: null,
        filter: 'checks',
      });
    });

    it('파트 여럿: 파트 탭은 넷 그대로(확인할 곳 0 · 「총 N페이지 가운데」) · [전체] 번역한 페이지 아래는 그림뿐 0 → 앞 마디만', async () => {
      drawPdf(pdfServer(), 'story');
      await waitFor(() => screen.getByTestId('open-pdf'), WAIT);
      await flush();
      expect(statKeys()).toEqual([
        'translated',
        'untranslated',
        'glossaryMiss',
        'fixed',
      ]);
      const translated = document.querySelector('[data-stat="translated"]')!;
      expect(translated.parentElement!.className).toContain('lg:grid-cols-4');
      expect(translated.textContent).not.toContain('그림뿐인');
      cleanup();
      drawPdf(pdfServer(), 'all');
      await waitFor(
        () =>
          expect(document.querySelector('[data-stat="checks"]')).toBeTruthy(),
        WAIT,
      );
      const all = document.querySelector('[data-stat="translated"]')!;
      await waitFor(() =>
        expect(all.textContent).not.toContain(
          TR_TEXT.stats.notes.outOfParts(4, 2).split(' · ')[1]!,
        ),
      );
      expect(TR_TEXT.stats.notes.outOfImages(4, 0)).toBe(
        TR_TEXT.stats.notes.outOf(4),
      );
      expect(TR_TEXT.stats.notes.outOfImages(4, null)).toBe(
        TR_TEXT.stats.notes.outOf(4),
      );
    });

    /** layout 답을 풀 때까지 붙잡는 서버(밴드 TRW8 ⑧ — 읽는 동안의 칸). */
    function holdLayout(server: Server) {
      let release!: () => void;
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      const held: Server = {
        ...server,
        send: async (request: Request) => {
          if (new URL(request.url).pathname.endsWith('/layout')) await gate;
          return server.send(request);
        },
      };
      return { held, release };
    }
    const stat = (key: string) =>
      document.querySelector(`[data-stat="${key}"]`) as HTMLElement | null;

    it('⑧ 한 파트: layout 을 붙잡은 동안도 다섯 칸(확인할 곳 셋째 pending · 검수 이슈 다섯째 · lg:grid-cols-5 · 메모는 처음부터 outOfImages 꼴) → 풀면 같은 li 에 값', async () => {
      const { held, release } = holdLayout(singlePdf());
      drawPdf(held, 'story');
      await waitFor(() => expect(stat('translated')).not.toBeNull(), WAIT);
      await flush();
      expect(statKeys()).toEqual([
        'translated',
        'untranslated',
        'checks',
        'glossaryMiss',
        'issues',
      ]);
      const li = stat('checks')!;
      expect(li.parentElement!.className).toContain('lg:grid-cols-5');
      expect(li.getAttribute('data-pending')).toBe('');
      expect(li.querySelectorAll('[data-skeleton-bar]')).toHaveLength(2);
      expect(li.querySelector('[data-testid="stat-value"]')).toBeNull();
      expect(li.querySelector('[data-testid="stat-open"]')).toBeNull();
      expect(stat('translated')!.textContent).toContain(
        TR_TEXT.stats.notes.outOfImages(2, null),
      );
      release();
      await waitFor(
        () =>
          expect(li.querySelector('[data-testid="stat-open"]')).not.toBeNull(),
        WAIT,
      );
      expect(stat('checks')).toBe(li);
      expect(li.hasAttribute('data-pending')).toBe(false);
      expect(li.querySelector('[data-testid="stat-value"]')!.textContent).toBe(
        '2',
      );
      expect(statKeys()).toEqual([
        'translated',
        'untranslated',
        'checks',
        'glossaryMiss',
        'issues',
      ]);
      expect(stat('translated')!.textContent).toContain(
        TR_TEXT.stats.notes.outOfImages(2, 1),
      );
    });

    it('⑧ 한 파트: layout 이 없으면(404) 다섯 칸 그대로 · 확인할 곳 「–」 · 누름 0 · pending 0', async () => {
      const server = fakeTranslationServer({
        documents: [fakeDocument(12, { fileName: 'made_up.pdf' })],
        runs: [
          fakeRun(30, 12, fakeOptions('story', 4, 5, BATCH), {
            flowId: 'translation.pdf@158',
          }),
        ],
      });
      server.advance(30, { status: 'done' });
      drawPdf(server, 'story');
      await waitFor(() => screen.getByTestId('qa-issues-body'), WAIT);
      await waitFor(
        () => expect(stat('checks')?.hasAttribute('data-pending')).toBe(false),
        WAIT,
      );
      await flush();
      expect(statKeys()).toEqual([
        'translated',
        'untranslated',
        'checks',
        'glossaryMiss',
        'issues',
      ]);
      const li = stat('checks')!;
      expect(li.querySelector('[data-testid="stat-value"]')!.textContent).toBe(
        TR_TEXT.stats.none,
      );
      expect(li.querySelector('button')).toBeNull();
    });

    it('⑧ [전체]: PDF 묶음인데 끝난 PDF 파트 0(달리는 중) → 다섯 칸 · 확인할 곳 「–」 · lg:grid-cols-5', async () => {
      const server = fakeTranslationServer({
        documents: [fakeDocument(12, { fileName: 'made_up.pdf' })],
        runs: [
          fakeRun(30, 12, fakeOptions('story', 4, 5, BATCH), {
            flowId: 'translation.pdf@158',
          }),
          fakeRun(31, 12, fakeOptions('general', 6, 7, BATCH)),
        ],
      });
      server.advance(31, { status: 'done' });
      drawPdf(server, 'all');
      await waitFor(() => expect(stat('translated')).not.toBeNull(), WAIT);
      await flush();
      expect(statKeys()).toEqual([
        'translated',
        'untranslated',
        'checks',
        'glossaryMiss',
        'issues',
      ]);
      const li = stat('checks')!;
      expect(li.parentElement!.className).toContain('lg:grid-cols-5');
      expect(li.querySelector('[data-testid="stat-value"]')!.textContent).toBe(
        TR_TEXT.stats.none,
      );
      expect(li.querySelector('button')).toBeNull();
    });

    it('⑧ [전체]: 끝난 PDF 파트 layout 을 붙잡은 동안 확인할 곳 pending → 풀면 같은 li 에 값', async () => {
      const { held, release } = holdLayout(pdfServer());
      drawPdf(held, 'all');
      await waitFor(() => expect(stat('checks')).not.toBeNull(), WAIT);
      await flush();
      const li = stat('checks')!;
      expect(li.getAttribute('data-pending')).toBe('');
      expect(statKeys()).toHaveLength(5);
      release();
      await waitFor(
        () => expect(li.hasAttribute('data-pending')).toBe(false),
        WAIT,
      );
      expect(stat('checks')).toBe(li);
      expect(li.querySelector('[data-testid="stat-value"]')!.textContent).toBe(
        '0',
      );
    });

    it('워드 파트 하나: 넷 그대로(확인할 곳 0)', async () => {
      const server = fakeTranslationServer({
        documents: [fakeDocument(12, { fileName: 'made_up.docx' })],
        runs: [fakeRun(31, 12, fakeOptions('general', 6, 7, BATCH))],
      });
      server.advance(31, { status: 'done' });
      drawPdf(server, 'general');
      await waitFor(() => screen.getByTestId('qa-issues-body'), WAIT);
      await flush();
      expect(statKeys()).toEqual([
        'translated',
        'untranslated',
        'glossaryMiss',
        'fixed',
      ]);
    });
  });

  it('워드 파트(resultShapes 에 layout 없음): [PDF로 보기] 0 · 「자리」 칸 0 · layout 을 읽지 않음', async () => {
    const server = pdfServer();
    drawPdf(server, 'general');
    await waitFor(() => screen.getByTestId('qa-issues-body'), WAIT);
    await flush();
    // 밴드 TRW6 ④(R14): 워드 파트(latest.flowId colab)는 실행 정보를 읽지 않는다 — PDF 판별은 묶음 칸.
    expect(server.count('GET /runs/31')).toBe(0);
    expect(screen.queryByTestId('open-pdf')).toBeNull();
    expect(screen.queryByTestId('qa-issue-place')).toBeNull();
    expect(screen.queryByTestId('glossary-miss-place')).toBeNull();
    expect(
      screen.queryByRole('columnheader', { name: TR_TEXT.pdfView.place }),
    ).toBeNull();
    expect(server.count('GET /translation/runs/31/layout')).toBe(0);
  });

  it('onOpenPdf 를 안 넘기면(옛 잇기) PDF 파트도 단추·칸 0', async () => {
    const server = pdfServer();
    draw(server, { part: 'story' });
    await waitFor(() => screen.getByTestId('qa-issues-body'), WAIT);
    await flush();
    expect(screen.queryByTestId('open-pdf')).toBeNull();
    expect(screen.queryByTestId('qa-issue-place')).toBeNull();
  });
});

// 밴드 TRW6 ④: PDF 파트 판별은 묶음 latest.flowId(TRS3 칸) — 실패 칸 W8 셋 · [이 파트만 다시] flowId · 「PDF 읽는 중」 · 서버 문장 0(P8).
describe('RunScreen PDF 파트 ④ (TRW6 — latest.flowId)', () => {
  const PDF = 'translation.pdf@158';
  /** 30 = 워드 CEO(끝남), 31 = PDF 스토리. */
  function pdfStory() {
    return fakeTranslationServer({
      documents: [fakeDocument(12, { fileName: 'made_up.pdf' })],
      runs: [
        fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
        fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH), { flowId: PDF }),
      ],
      nextRunId: 40,
    });
  }
  const card = () => screen.getByTestId('part-failure');
  const posts = (server: Server) => server.count('POST /runs');
  const retryButton = () =>
    screen.queryByRole('button', { name: TR_TEXT.failure.retryPart });

  it('no_text_layer 실패 → 텍스트 없는 PDF 한 줄 · 다시 단추·회색 줄 0 · 실행 정보 읽기 0', async () => {
    const server = pdfStory();
    server.advance(30, { status: 'done' });
    server.advance(31, { status: 'failed', errorCode: 'no_text_layer' });
    draw(server, { part: 'story' });
    await waitFor(() => card(), WAIT);
    expect(card().textContent).toContain(TR_TEXT.failure.pdf.noText);
    expect(card().textContent).not.toContain(TR_TEXT.failure.serverError);
    expect(retryButton()).toBeNull();
    expect(screen.queryByTestId('part-failure-pdf-note')).toBeNull();
    expect(server.count('GET /runs/31')).toBe(0);
  });

  it('거절 unsupported_input(bad_file) → 읽지 못함 한 줄 · 서버 거절 문장 0(P8)', async () => {
    const server = pdfStory();
    server.advance(30, { status: 'done' });
    server.advance(31, {
      status: 'done',
      outcome: 'rejected',
      rejectionKind: 'unsupported_input',
    });
    draw(server, { part: 'story' });
    await waitFor(() => card(), WAIT);
    await flush();
    expect(card().textContent).toContain(TR_TEXT.failure.pdf.unreadable);
    expect(card().textContent).not.toContain(TR_TEXT.rejection.bad_file.reason);
    expect(screen.queryByTestId('part-failure-guide')).toBeNull();
    expect(retryButton()).toBeNull();
    expect(document.body.textContent).not.toContain('지어낸');
  });

  it('PDF 서버 오류 → [이 파트만 다시] + 회색 한 줄 · 누르면 POST 본문 flowId 같음·옵션 그대로·새 launchKey(E1)', async () => {
    const server = pdfStory();
    server.advance(30, { status: 'done' });
    server.advance(31, { status: 'failed', errorCode: 'step_error' });
    draw(server, { part: 'story' });
    const button = await screen.findByRole(
      'button',
      { name: TR_TEXT.failure.retryPart },
      WAIT,
    );
    expect(screen.getByTestId('part-failure-pdf-note').textContent).toBe(
      TR_TEXT.failure.pdf.retryNote,
    );
    fireEvent.click(button);
    await waitFor(() => expect(posts(server)).toBe(1), WAIT);
    const body = server.runBodies()[0] as unknown as Record<string, unknown>;
    expect(body.flowId).toBe(PDF);
    expect(JSON.stringify(body.options)).toBe(
      JSON.stringify(server.runs.get(31)!.options),
    );
    expect(body.launchKey).not.toBe(server.runs.get(31)!.launchKey);
    // 실행 정보 읽기는 retryPart 의 한 번뿐(실패 칸이 따로 읽지 않는다).
    expect(server.count('GET /runs/31')).toBe(1);
  });

  it('워드 서버 오류 파트는 회색 한 줄 0(DOM 그대로)', async () => {
    const server = pdfStory();
    server.advance(30, { status: 'failed', errorCode: 'step_error' });
    server.advance(31, { status: 'done' });
    draw(server, { part: 'ceo' });
    await screen.findByRole(
      'button',
      { name: TR_TEXT.failure.retryPart },
      WAIT,
    );
    expect(screen.queryByTestId('part-failure-pdf-note')).toBeNull();
  });

  it('W6: retry_source_not_found 거절은 일반 실패 꼴(서버 오류 글 + 다시 단추)', async () => {
    const server = pdfStory();
    server.advance(30, { status: 'done' });
    server.advance(31, {
      status: 'done',
      outcome: 'rejected',
      rejectionKind: 'retry_source_not_found',
    });
    draw(server, { part: 'story' });
    await waitFor(() => card(), WAIT);
    expect(card().getAttribute('data-kind')).toBe('server_error');
    expect(card().textContent).toContain(TR_TEXT.failure.serverError);
    expect(retryButton()).toBeTruthy();
  });

  it('PDF 파트 준비 단계 진행 중 → 「PDF 읽는 중」 · 워드 파트는 BASE 글(P9)', async () => {
    const server = pdfStory();
    const preparing = fakeSteps(0, { status: 'running' });
    server.advance(30, { status: 'processing', steps: preparing });
    server.advance(31, { status: 'processing', steps: preparing });
    draw(server, { part: 'story' });
    await waitFor(() => screen.getByTestId('stage-card'), WAIT);
    const stage = () => screen.getByTestId('stage-card').textContent ?? '';
    expect(stage()).toContain(TR_TEXT.stage.prepareNowPdf);
    expect(stage()).not.toContain(TR_TEXT.stage.prepareNow);
    cleanup();
    draw(server, { part: 'ceo' });
    await waitFor(() => screen.getByTestId('stage-card'), WAIT);
    expect(stage()).toContain(TR_TEXT.stage.prepareNow);
    expect(stage()).not.toContain('PDF');
  });
});
