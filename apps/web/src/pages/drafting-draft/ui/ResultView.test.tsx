// @vitest-environment jsdom
// RP-04 결과 세 칸(밴드 RPW1 ③ 시험 S6 — 발주서 §2-3). 진짜 실어댑터 + 가짜 원고작성 서버 + 가짜 openPdf(그리기만 흉내).
//   머리 셈·점 다섯 · bullet·잎 갈래 글 · 칩/bullet → 그 쪽 · 두 층 수 == 손셈(sentence null 이면 문단만) · rejected 숫자·서버 글 0 ·
//   NotRun.reason·failure.message 0 · 띠(목차·문서 조건, 표지, added, removed 빠짐) · 다시 만들기 본문 셋 · 409 거절 한 줄 ·
//   matched false · projectId 다름 → 찾지 못함 · PDF 한 벌·missing·failed · docx 이름(받기 모달 — RPW13) · 앞 실행 위 다시 짓는 중(⑦) 단추 끔·모달 줄 꺼짐.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import type { PendingRuns } from '../../../entities/drafting/api/index.ts';
import {
  fakeDraftingServer,
  fakeResult,
  refusal,
  storeOf,
  unreachable,
} from '../../../entities/drafting/api/testing.ts';
import type { ResultWire } from '../../../entities/drafting/api/testing.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import type {
  Bullet,
  OutlineNode,
} from '../../../entities/drafting/model/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { ResultView } from './ResultView.tsx';
import { RunScreen } from './RunScreen.tsx';

const words = DR_TEXT.result;
const flush = () => act(async () => {});
const SERVER_WORDS = '지어낸-서버글';

const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };
beforeAll(() => {
  URL.createObjectURL = vi.fn(() => 'blob:fake-pdf');
  URL.revokeObjectURL = vi.fn();
});
afterAll(() => {
  URL.createObjectURL = original.create;
  URL.revokeObjectURL = original.revoke;
});
afterEach(cleanup);

const node = (
  key: string,
  parentKey: string | null,
  depth: number,
  requirement = '',
): OutlineNode => ({
  key,
  parentKey,
  depth,
  title: `지어낸 ${key}`,
  requirement,
});

/** a(1) ─ a1 … a6(2). */
const OUTLINE = [
  node('a', null, 1),
  node('a1', 'a', 2, '지어낸 요구 하나'),
  ...['a2', 'a3', 'a4', 'a5', 'a6'].map((key) => node(key, 'a', 2)),
];

/** a1 의 bullet 셋: 칩(2·3쪽 — 2쪽 블록 b1 둘 겹침 + b2, 3쪽은 문장 없음) · 근거 없음 · 원문에 없는 숫자. */
const A1_BULLETS: Bullet[] = [
  {
    text: '지어낸 첫 bullet',
    unsupported: false,
    sources: [
      {
        documentId: 101,
        blockId: 'b1',
        page: 2,
        blockBox: [72, 100, 300, 140],
        sentence: {
          index: 0,
          boxes: [
            [72, 100, 200, 112],
            [72, 114, 180, 126],
          ],
        },
      },
      {
        documentId: 101,
        blockId: 'b1',
        page: 2,
        blockBox: [72, 100, 300, 140],
        sentence: { index: 1, boxes: [[72, 128, 150, 140]] },
      },
      {
        documentId: 101,
        blockId: 'b2',
        page: 2,
        blockBox: [72, 200, 300, 260],
        sentence: { index: 0, boxes: [[72, 200, 280, 212]] },
      },
      {
        documentId: 101,
        blockId: 'b3',
        page: 3,
        blockBox: [50, 400, 500, 480],
        sentence: null,
      },
    ],
  },
  { text: '지어낸 근거 없는 bullet', unsupported: true, sources: [] },
  {
    text: '지어낸 숫자 bullet',
    unsupported: true,
    sources: [
      {
        documentId: 101,
        blockId: 'b4',
        page: 3,
        blockBox: [10, 10, 20, 20],
        sentence: null,
      },
    ],
  },
];

const leafOf = (
  key: string,
  outcome: ResultWire['leaves'][number]['outcome'],
  pages = [2, 3],
): ResultWire['leaves'][number] => ({
  key,
  titlePath: ['지어낸 a', `지어낸 ${key}`],
  pages,
  reusedFrom: null,
  outcome,
});

const LEAVES: ResultWire['leaves'] = [
  leafOf('a1', { status: 'done', bullets: A1_BULLETS }),
  leafOf('a2', {
    status: 'done',
    bullets: [{ text: '지어낸 a2', unsupported: false, sources: [] }],
  }),
  leafOf('a3', { status: 'no_material' }, []),
  leafOf('a4', {
    status: 'failed',
    failure: { kind: 'timeout', message: SERVER_WORDS },
  }),
  leafOf('a5', { status: 'not_run', reason: SERVER_WORDS }),
];

const PDF = new Uint8Array([37, 80, 68, 70]);

/** 프로젝트 1(문서 101·목차) · 실행 301 done · 결과 심음. */
async function seeded(
  patch: Parameters<typeof fakeResult>[2] = {},
  options: Parameters<typeof fakeDraftingServer>[0] = {},
) {
  const server = fakeDraftingServer({
    projects: [
      { id: 1, name: '지어낸 보고서', year: 2026 },
      { id: 2, name: '지어낸 다른 보고서', year: 2026 },
    ],
    pdfs: { 101: PDF },
    ...options,
  });
  server.seedProject(1, { documentId: server.seedDocument(), nodes: OUTLINE });
  const started = await storeOf(server).startRun({ projectId: 1 }, null);
  const runId = started.kind === 'ok' ? started.value.runId : 0;
  server.runPatch(runId, { status: 'done' });
  server.results.set(
    runId,
    fakeResult(server, runId, { leaves: LEAVES, ...patch }),
  );
  return { server, runId };
}

function fakeOpenPdf() {
  const rendered: number[] = [];
  const openPdf: OpenPdf = vi.fn(async () => ({
    renderPage: (page: number) => {
      rendered.push(page);
      return { done: Promise.resolve(), cancel() {} };
    },
    close() {},
  }));
  return { openPdf, rendered };
}

async function setup(
  server: ReturnType<typeof fakeDraftingServer>,
  runId: number,
  {
    projectId = 1,
    pendingRuns,
  }: { projectId?: number; pendingRuns?: PendingRuns } = {},
) {
  const onRun = vi.fn();
  const onList = vi.fn();
  const { openPdf, rendered } = fakeOpenPdf();
  let key = 0;
  render(
    <ResultView
      store={storeOf(server, {
        newKey: () => `idem-${(key += 1)}`,
        newLaunchKey: () => `launch-${key}`,
        ...(pendingRuns ? { pendingRuns } : {}),
      })}
      openPdf={openPdf}
      projectId={projectId}
      runId={runId}
      operator={false}
      onRun={onRun}
      onList={onList}
    />,
  );
  await flush();
  await flush();
  return { onRun, onList, openPdf, rendered };
}

/** 받기 모달(밴드 RPW13) — 머리 [내려받기]는 늘 켬. 받을 수 없으면 모달 안 「개조식 초안」 줄만 꺼지고 (?) 에 까닭, 눌러도 docx 0. */
async function expectDownloadOff(
  server: ReturnType<typeof fakeDraftingServer>,
  runIds: readonly number[],
  reason: string,
) {
  const head = screen.getByTestId('result-download');
  expect(head.hasAttribute('disabled')).toBe(false);
  expect(head.getAttribute('aria-disabled')).toBeNull();
  fireEvent.click(head);
  const dialog = screen.getByRole('dialog', { name: '내려받기' });
  const file = within(dialog).getByTestId('result-download-dialog-file-docx');
  expect(file.getAttribute('aria-disabled')).toBe('true');
  const help = within(dialog).getByTestId('result-download-dialog-help-docx');
  expect(help.getAttribute('aria-label')).toBe(`없는 까닭: ${reason}`);
  fireEvent.focus(help);
  expect((await screen.findByRole('tooltip')).textContent).toBe(reason);
  fireEvent.click(file);
  await flush();
  for (const id of runIds)
    expect(server.count(`GET /drafting/runs/${id}/result.docx`)).toBe(0);
}

const treeRow = (key: string) =>
  within(screen.getByTestId('result-tree'))
    .getAllByRole('option')
    .find((row) => row.getAttribute('data-key') === key)!;
const layers = (layer: 'block' | 'sentence') =>
  document.querySelectorAll<HTMLElement>(`[data-layer="${layer}"]`);
const bullets = () => screen.getAllByTestId('bullet');
const posts = (server: ReturnType<typeof fakeDraftingServer>) =>
  server.bodies('POST /runs') as { options: unknown }[];

describe('RP-04 결과 — 세 칸', () => {
  it('머리 셈(잎만) · 점 다섯(결과에 없는 잎 = 아직) · 첫 잎 고름 · 요구 · 찾은 페이지', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    expect(screen.getByTestId('result-counts').textContent).toBe(
      words.counts(6, 2, 1, 1, 2),
    );
    expect(
      ['a', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6'].map(
        (key) => treeRow(key).getAttribute('data-dot') ?? '-',
      ),
    ).toEqual([
      '-',
      'unsupported',
      'done',
      'no_material',
      'failed',
      'not_run',
      'not_run',
    ]);
    expect(screen.getByTestId('leaf-title').textContent).toBe('1.1 지어낸 a1');
    expect(screen.getByTestId('leaf-meta').textContent).toBe(
      words.leafMeta(3, [2, 3]),
    );
    expect(screen.getByText('지어낸 요구 하나')).not.toBeNull();
  });

  it('bullet 갈래 글 — 칩(출처 쪽마다) · 근거 없음 · 원문에 없는 숫자', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const [first, second, third] = bullets();
    expect(
      within(first!)
        .getAllByTestId('source-chip')
        .map((chip) => chip.textContent),
    ).toEqual([words.chip(2), words.chip(3)]);
    expect(within(second!).getByTestId('bullet-note').textContent).toBe(
      words.noSource,
    );
    expect(within(third!).getByTestId('bullet-note').textContent).toBe(
      words.notInSource,
    );
    expect(within(third!).queryAllByTestId('source-chip')).toHaveLength(0);
  });

  it('잎 갈래 글 셋 — 맞는 자료 없음 · 못 만듦 · 아직(서버 reason·message 0)', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const states: Record<string, string> = {
      a3: words.noMaterial,
      a4: words.leafFailed,
      a5: words.notRun,
      a6: words.notRun,
    };
    for (const [key, text] of Object.entries(states)) {
      fireEvent.click(treeRow(key));
      expect(screen.getByTestId('leaf-state').textContent).toBe(text);
    }
    expect(document.body.textContent).not.toContain(SERVER_WORDS);
  });
});

describe('RP-04 결과 — 원문 보기 두 층', () => {
  it('bullet 누름 → 첫 출처 쪽 · 옅은 블록(겹침 하나) 둘 · 진한 문장 넷 · 자리 = 손셈(위 원점)', async () => {
    const { server, runId } = await seeded();
    const { rendered } = await setup(server, runId);
    expect(layers('block')).toHaveLength(0);
    fireEvent.click(within(bullets()[0]!).getByText(/지어낸 첫 bullet/));
    await waitFor(() => expect(layers('block')).toHaveLength(2));
    expect(screen.getByTestId('source-page').textContent).toBe(
      words.source.pageOf(2, 3),
    );
    expect(rendered).toContain(2);
    expect(layers('block')).toHaveLength(2);
    expect(layers('sentence')).toHaveLength(4);
    const b1 = layers('block')[0]!;
    expect(b1.getAttribute('data-block-id')).toBe('b1');
    expect(b1.style.left).toBe('72px');
    expect(b1.style.top).toBe('100px');
    expect(b1.style.width).toBe('228px');
    expect(b1.style.height).toBe('40px');
    expect(layers('sentence')[2]!.style.top).toBe('128px');
    expect(screen.queryByTestId('paragraph-only')).toBeNull();
  });

  it('칩 3쪽 → sentence null — 옅은 것만 + 「문단까지만 찾았어요」 · 고른 칩', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const chip = within(bullets()[0]!).getAllByTestId('source-chip')[1]!;
    fireEvent.click(chip);
    await waitFor(() => expect(layers('block')).toHaveLength(1));
    expect(chip.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('source-page').textContent).toBe(
      words.source.pageOf(3, 3),
    );
    expect(layers('block')).toHaveLength(1);
    expect(layers('sentence')).toHaveLength(0);
    expect(screen.getByTestId('paragraph-only').textContent).toBe(
      words.source.paragraphOnly,
    );
  });

  it('PDF 는 문서마다 한 벌 — 쪽·bullet·잎을 바꿔도 GET …/file 하나', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    fireEvent.click(within(bullets()[0]!).getByText(/지어낸 첫 bullet/));
    await flush();
    fireEvent.click(within(bullets()[0]!).getAllByTestId('source-chip')[1]!);
    await flush();
    fireEvent.click(treeRow('a2'));
    await flush();
    fireEvent.click(treeRow('a1'));
    await flush();
    expect(server.count('GET /documents/101/file')).toBe(1);
  });

  it('PDF missing → 한 줄(다시 시도 없음) · failed → 한 줄 + [다시 시도]', async () => {
    const missing = await seeded({}, { pdfs: {} });
    await setup(missing.server, missing.runId);
    expect(screen.getByTestId('source-failed').textContent).toBe(
      words.source.failed,
    );
    expect(
      within(screen.getByTestId('source-failed')).queryByRole('button'),
    ).toBeNull();
    cleanup();
    const failed = await seeded();
    failed.server.override['GET /documents/101/file'] = () =>
      new Response('', { status: 500 });
    await setup(failed.server, failed.runId);
    expect(
      within(screen.getByTestId('source-failed')).getByRole('button', {
        name: DR_TEXT.common.retry,
      }),
    ).not.toBeNull();
  });
});

describe('RP-04 결과 — 실행 갈래', () => {
  it('rejected — 빨간 띠(숫자·서버 글 0) · 잎 전부 아직 · [내려받기] 켬 + 모달 줄 꺼짐·까닭', async () => {
    const { server, runId } = await seeded({
      status: {
        status: 'rejected',
        code: 'over_budget',
        stage: 'before_draft',
        message: `${SERVER_WORDS} 12,345`,
      },
    });
    await setup(server, runId);
    const band = screen.getByTestId('result-rejected');
    expect(band.textContent).toBe(words.rejected);
    expect(band.textContent).not.toMatch(/\d/);
    expect(document.body.textContent).not.toContain(SERVER_WORDS);
    expect(
      ['a1', 'a2', 'a3'].map((key) => treeRow(key).getAttribute('data-dot')),
    ).toEqual(['not_run', 'not_run', 'not_run']);
    await expectDownloadOff(
      server,
      [runId],
      '이번 실행은 만들지 못해 받을 파일이 없어요',
    );
  });

  it('base.matched false → 회색 한 줄 · matched true 면 0', async () => {
    const { server, runId } = await seeded({
      base: { runId: 300, outlineId: 200, matched: false, reason: 'document' },
    });
    await setup(server, runId);
    expect(screen.getByTestId('result-not-matched').textContent).toBe(
      words.notMatched,
    );
    cleanup();
    const again = await seeded({
      base: { runId: 300, outlineId: 200, matched: true, reason: null },
    });
    await setup(again.server, again.runId);
    expect(screen.queryByTestId('result-not-matched')).toBeNull();
  });

  it('결과의 projectId 가 주소와 다름 → 찾지 못함', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId, { projectId: 2 });
    expect(screen.queryByTestId('run-result')).toBeNull();
    expect(screen.getByText(words.resultMissing)).not.toBeNull();
  });
});

describe('RP-04 결과 — 띠', () => {
  it('목차·문서 그대로면 차이를 읽지 않음 · 띠 0', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    expect(server.count(`GET /drafting/projects/1/outline/changes`)).toBe(0);
    expect(screen.queryByTestId('result-band')).toBeNull();
  });

  it('rejected — 바뀐 목차·이 목차 다시 만들기는 꺼짐, 전체 다시 만들기는 켬', async () => {
    const { server, runId } = await seeded({
      status: {
        status: 'rejected',
        code: 'over_budget',
        stage: 'before_draft',
        message: SERVER_WORDS,
      },
    });
    server.seedProject(1, {
      nodes: OUTLINE.map((one) =>
        one.key === 'a2' ? { ...one, requirement: '지어낸 새 요구' } : one,
      ),
    });
    await setup(server, runId);
    const button = (name: string) =>
      screen.getByRole<HTMLButtonElement>('button', { name });
    expect(button(words.rebuildChanged).disabled).toBe(true);
    expect(button(words.rebuildOne).disabled).toBe(true);
    expect(button(DR_TEXT.run.restartAll).disabled).toBe(false);
  });

  it('접은 트리의 줄은 번호·제목을 이름으로 · Space 는 고르고 쪽을 내리지 않는다', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    expect(treeRow('a2').hasAttribute('aria-label')).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: words.treeFold }));
    expect(treeRow('a2').getAttribute('aria-label')).toBe('1.2 지어낸 a2');
    expect(within(treeRow('a2')).getByTestId('tree-dot')).not.toBeNull();
    // fireEvent 는 preventDefault 되면 거짓을 돌려준다.
    expect(fireEvent.keyDown(treeRow('a2'), { key: ' ' })).toBe(false);
    expect(treeRow('a2').getAttribute('aria-selected')).toBe('true');
  });

  it('목차를 고침 → 「바뀐 목차 2개」 · 「바뀜」 표지 · added 글 · 지운 잎은 트리에서 빠짐', async () => {
    const { server, runId } = await seeded();
    server.seedProject(1, {
      nodes: [
        ...OUTLINE.filter((one) => one.key !== 'a6').map((one) =>
          one.key === 'a2' ? { ...one, title: '지어낸 고친 a2' } : one,
        ),
        node('a7', 'a', 2),
      ],
    });
    await setup(server, runId);
    expect(server.count('GET /drafting/projects/1/outline/changes')).toBe(1);
    expect(screen.getByTestId('band-count').textContent).toBe(
      `${words.changed} · ${words.changedCount(2)}`,
    );
    expect(
      screen
        .getAllByTestId('changed-mark')
        .map((mark) => mark.closest('[data-key]')!.getAttribute('data-key')),
    ).toEqual(['a2', 'a7']);
    expect(treeRow('a6')).toBeUndefined();
    fireEvent.click(treeRow('a7'));
    expect(screen.getByTestId('leaf-state').textContent).toContain(
      words.notRun,
    );
    expect(screen.getByTestId('leaf-added').textContent).toBe(words.added);
    expect(screen.queryByTestId('band-reuploaded')).toBeNull();
  });

  it('문서만 다시 올림 → 「전년도 보고서를 다시 올렸어요」(목차 수 0 이면 단추 없음)', async () => {
    const { server, runId } = await seeded();
    server.seedProject(1, { documentId: server.seedDocument() });
    await setup(server, runId);
    expect(screen.getByTestId('band-reuploaded').textContent).toBe(
      words.reuploaded,
    );
    expect(screen.queryByTestId('band-count')).toBeNull();
    expect(screen.queryByRole('button', { name: words.rebuildChanged })).toBe(
      null,
    );
  });
});

describe('RP-04 결과 — 다시 만들기·내려받기', () => {
  it('다시 만들기 셋의 본문 — 전체 base 0 · 바뀐 목차 rebuild [] · 이 목차 rebuild [key] → 새 실행', async () => {
    const { server, runId } = await seeded();
    server.seedProject(1, {
      nodes: OUTLINE.map((one) =>
        one.key === 'a2' ? { ...one, requirement: '지어낸 새 요구' } : one,
      ),
    });
    const { onRun } = await setup(server, runId);
    fireEvent.click(
      screen.getByRole('button', { name: DR_TEXT.run.restartAll }),
    );
    await flush();
    fireEvent.click(screen.getByRole('button', { name: words.rebuildChanged }));
    await flush();
    fireEvent.click(screen.getByRole('button', { name: words.rebuildOne }));
    await flush();
    expect(
      posts(server)
        .slice(1)
        .map((body) => body.options),
    ).toEqual([
      { projectId: 1 },
      { projectId: 1, base: { runId, rebuild: [] } },
      { projectId: 1, base: { runId, rebuild: ['a1'] } },
    ]);
    expect(onRun).toHaveBeenCalledTimes(3);
  });

  it('409 AI_SETTING_UNUSABLE → 한 줄(설정 화면 이름·서버 글 0) · 이동 0', async () => {
    const { server, runId } = await seeded();
    server.override['POST /runs'] = () => refusal(409, 'AI_SETTING_UNUSABLE');
    const { onRun } = await setup(server, runId);
    fireEvent.click(screen.getByRole('button', { name: words.rebuildOne }));
    await flush();
    const line = screen.getByTestId('start-refused');
    expect(line.textContent).toBe(DR_TEXT.startRefused);
    expect(document.body.textContent).not.toContain('AI 설정');
    expect(onRun).not.toHaveBeenCalled();
  });

  it('M5 다시 만들기 연결 실패 = 연결 글(거절 글 0) · 열쇠 표의 칸은 지금 목차 판', async () => {
    const { server, runId } = await seeded();
    server.override['POST /runs'] = [unreachable];
    const pendingRuns: PendingRuns = new Map();
    const { onRun } = await setup(server, runId, { pendingRuns });
    fireEvent.click(screen.getByRole('button', { name: words.rebuildOne }));
    await flush();
    expect(screen.getByTestId('start-refused').textContent).toBe(
      DR_TEXT.startFailed,
    );
    expect(onRun).not.toHaveBeenCalled();
    const outlineId = server.project(1)!.outline!.outlineId;
    expect([...pendingRuns.keys()].map((slot) => slot.split('|')[1])).toEqual([
      String(outlineId),
    ]);
  });

  it('[내려받기] — 받기 모달 → 「개조식 초안」 줄 [Word] 로 docx 를 받아 Content-Disposition 이름으로 저장', async () => {
    const { server, runId } = await seeded();
    const names: string[] = [];
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        names.push(this.download);
      });
    await setup(server, runId);
    const head = screen.getByTestId('result-download');
    expect(head.textContent).toBe('내려받기');
    expect(head.getAttribute('aria-haspopup')).toBe('dialog');
    // 밴드 RPW14: 다섯 모듈 통일 꼴 — outline-grey round md + 왼쪽 받기 아이콘(aria-hidden), 접근 이름은 「내려받기」 그대로.
    for (const c of ['border-button-grey', 'rounded-full', 'h-9'])
      expect(head.classList.contains(c), c).toBe(true);
    expect(head.classList.contains('bg-button-black')).toBe(false);
    const icon = head.querySelector('svg');
    expect(icon).toBeTruthy();
    expect(icon!.getAttribute('aria-hidden')).toBe('true');
    expect(head.firstChild).toBe(icon);
    expect(screen.getByRole('button', { name: '내려받기' })).toBe(head);
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(head);
    // 머리 단추는 모달만 연다 — 아직 받지 않음.
    expect(server.count(`GET /drafting/runs/${runId}/result.docx`)).toBe(0);
    const dialog = screen.getByRole('dialog', { name: '내려받기' });
    const rows = dialog.querySelectorAll('li[data-file]');
    expect([...rows].map((row) => row.getAttribute('data-file'))).toEqual([
      'docx',
    ]);
    expect(dialog.textContent).toContain('개조식 초안');
    expect(dialog.textContent).toContain(
      '지금 보는 실행의 개조식 전부를 한 파일로 내려받아요',
    );
    const file = within(dialog).getByTestId('result-download-dialog-file-docx');
    expect(file.textContent).toBe('Word');
    expect(file.getAttribute('aria-disabled')).toBeNull();
    expect(
      within(dialog).queryByTestId('result-download-dialog-help-docx'),
    ).toBeNull();
    fireEvent.click(file);
    await waitFor(() => expect(names).toEqual(['지어낸 초안.docx']));
    expect(server.count(`GET /drafting/runs/${runId}/result.docx`)).toBe(1);
    click.mockRestore();
  });

  it('[내려받기] 실패 — 그 줄 아래 alert 한 줄 · 저장 0', async () => {
    const { server, runId } = await seeded();
    const names: string[] = [];
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        names.push(this.download);
      });
    server.override[`GET /drafting/runs/${runId}/result.docx`] = () =>
      new Response('', { status: 500 });
    await setup(server, runId);
    fireEvent.click(screen.getByTestId('result-download'));
    fireEvent.click(screen.getByTestId('result-download-dialog-file-docx'));
    const problem = await screen.findByTestId(
      'result-download-dialog-problem-docx',
    );
    expect(problem.getAttribute('role')).toBe('alert');
    expect(problem.textContent).toBe('파일을 받지 못했어요. 다시 눌러 주세요.');
    expect(names).toEqual([]);
    click.mockRestore();
  });

  it('[내려받기] 모달 — [닫기]·Esc 뒤 초점이 머리 단추', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const head = screen.getByTestId('result-download');
    fireEvent.click(head);
    act(() => document.body.focus());
    fireEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: '닫기' }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(document.activeElement).toBe(head);
    fireEvent.click(head);
    act(() => document.body.focus());
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(document.activeElement).toBe(head);
  });
});

describe('RP-04 — 앞 실행 위에서 다시 짓는 중(⑦)', () => {
  it('base 실행 진행 중 — 진행 카드 0 + 앞 결과(다시 짓는 잎 「다시 만드는 중」·단추 셋 끔·내려받기 끔)', async () => {
    const { server, runId } = await seeded();
    const store = storeOf(server);
    const next = await store.startRun(
      {
        projectId: 1,
        base: { runId, rebuild: ['a1'] },
      },
      null,
    );
    const baseRun = next.kind === 'ok' ? next.value.runId : 0;
    server.runPatch(baseRun, { status: 'processing' });
    const { openPdf } = fakeOpenPdf();
    render(
      <RunScreen
        store={store}
        projectId={1}
        runId={baseRun}
        operator={false}
        onRun={vi.fn()}
        onPickRun={vi.fn()}
        onList={vi.fn()}
        openPdf={openPdf}
        pollMs={10_000}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId('run-result')).not.toBeNull(),
    );
    expect(screen.queryByTestId('run-heading')).toBeNull();
    expect(screen.queryByTestId('run-progress')).toBeNull();
    expect(screen.getByTestId('leaf-skeleton')).not.toBeNull();
    expect(treeRow('a1').getAttribute('data-dot')).toBe('rebuilding');
    expect(treeRow('a2').getAttribute('data-dot')).toBe('done');
    expect(screen.getByTestId('leaf-rebuilding').textContent).toBe(
      words.rebuilding,
    );
    expect(screen.getByTestId('leaf-state').textContent).toBe(
      words.rebuildingNote,
    );
    for (const name of [DR_TEXT.run.restartAll, words.rebuildOne])
      expect(
        screen.getByRole('button', { name }).hasAttribute('disabled'),
      ).toBe(true);
    fireEvent.click(treeRow('a2'));
    expect(
      screen
        .getByRole('button', { name: words.rebuildOne })
        .hasAttribute('disabled'),
    ).toBe(true);
    // 다른 잎은 bullet 그대로 · 「만드는 중」 0.
    expect(screen.queryByTestId('leaf-rebuilding')).toBeNull();
    expect(bullets()).toHaveLength(1);
    await expectDownloadOff(
      server,
      [runId, baseRun],
      '다시 만드는 중이에요 · 끝나면 받을 수 있어요',
    );
  });

  it('rebuild [] — 띠 marks 의 잎만 만드는 중 · 안 바뀐 잎은 bullet 그대로(서버 reuse._kept)', async () => {
    const { server, runId } = await seeded();
    server.seedProject(1, {
      nodes: OUTLINE.map((one) =>
        one.key === 'a2' ? { ...one, requirement: '지어낸 새 요구' } : one,
      ),
    });
    const store = storeOf(server);
    const next = await store.startRun(
      {
        projectId: 1,
        base: { runId, rebuild: [] },
      },
      null,
    );
    server.runPatch(next.kind === 'ok' ? next.value.runId : 0, {
      status: 'processing',
    });
    const { openPdf } = fakeOpenPdf();
    render(
      <RunScreen
        store={store}
        projectId={1}
        runId={next.kind === 'ok' ? next.value.runId : 0}
        operator={false}
        onRun={vi.fn()}
        onPickRun={vi.fn()}
        onList={vi.fn()}
        openPdf={openPdf}
        pollMs={10_000}
      />,
    );
    await screen.findByTestId('run-result');
    await waitFor(() =>
      expect(treeRow('a2').getAttribute('data-dot')).toBe('rebuilding'),
    );
    expect(treeRow('a1').getAttribute('data-dot')).toBe('unsupported');
    expect(screen.queryByTestId('leaf-rebuilding')).toBeNull();
    fireEvent.click(treeRow('a2'));
    expect(screen.getByTestId('leaf-rebuilding')).not.toBeNull();
    // 앞 결과에서 done 아닌 잎도 서버가 다시 짓는다.
    expect(treeRow('a3').getAttribute('data-dot')).toBe('rebuilding');
    expect(treeRow('a4').getAttribute('data-dot')).toBe('rebuilding');
  });
});

describe('RP-04 결과 — 판 대조(RPW2 ①)', () => {
  const widthIs = (narrow: boolean) => {
    window.matchMedia = vi.fn((query: string) => ({
      matches: narrow && query === '(max-width: 1280px)',
    })) as unknown as typeof window.matchMedia;
  };
  afterEach(() => {
    Reflect.deleteProperty(window, 'matchMedia');
  });

  it('D#1 띠 단추는 띠 글 감싸개 밖(형제) · 「목차가 바뀌었어요」 굵게', async () => {
    const { server, runId } = await seeded();
    server.seedProject(1, {
      nodes: OUTLINE.map((one) =>
        one.key === 'a2' ? { ...one, title: '지어낸 고친 a2' } : one,
      ),
    });
    await setup(server, runId);
    const text = screen.getByTestId('band-text');
    const button = screen.getByRole('button', { name: words.rebuildChanged });
    expect(text.contains(button)).toBe(false);
    expect(text.parentElement).toBe(button.parentElement);
    expect(text.querySelector('strong')?.textContent).toBe(words.changed);
  });

  it('D#4 1280 이하면 접은 채 시작 · 1440 은 펼침 · 누른 뒤엔 사용자 값', async () => {
    widthIs(true);
    const narrow = await seeded();
    await setup(narrow.server, narrow.runId);
    const tree = () => screen.getByTestId('result-tree');
    expect(tree().getAttribute('data-folded')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: words.treeOpen }));
    expect(tree().getAttribute('data-folded')).toBe('false');
    cleanup();
    widthIs(false);
    const wide = await seeded();
    await setup(wide.server, wide.runId);
    expect(tree().getAttribute('data-folded')).toBe('false');
  });

  it('D#7 두 층 토큰 — 문단 크림 · 문장 주황 테두리 · blue- 0', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    fireEvent.click(within(bullets()[0]!).getByText(/지어낸 첫 bullet/));
    await waitFor(() => expect(layers('block')).toHaveLength(2));
    expect(layers('block')[0]!.className).toContain('bg-support-yellow-subtle');
    expect(layers('sentence')[0]!.className).toContain('border-support-orange');
    const pane = screen.getByTestId('source-pane').innerHTML;
    expect(pane).not.toContain('blue-');
  });

  it('D#8 칩 — 아이콘 · 테두리 알약 · 고른 칩만 검정 · aria-pressed', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const [two, three] = within(bullets()[0]!).getAllByTestId('source-chip');
    expect(two!.querySelector('svg')).not.toBeNull();
    fireEvent.click(three!);
    expect(three!.getAttribute('aria-pressed')).toBe('true');
    expect(two!.getAttribute('aria-pressed')).toBe('false');
    expect(three!.className).toContain('bg-background-primary-inverse');
    expect(two!.className).not.toContain('bg-background-primary-inverse');
  });

  it('R1 다른 bullet 의 같은 쪽 칩은 눌린 것이 아니다', async () => {
    const { server, runId } = await seeded({
      leaves: [
        leafOf('a1', {
          status: 'done',
          bullets: [
            A1_BULLETS[0]!,
            {
              text: '지어낸 같은 쪽 bullet',
              unsupported: false,
              sources: A1_BULLETS[0]!.sources.slice(-1),
            },
          ],
        }),
      ],
    });
    await setup(server, runId);
    const [, three] = within(bullets()[0]!).getAllByTestId('source-chip');
    const [other] = within(bullets()[1]!).getAllByTestId('source-chip');
    fireEvent.click(three!);
    expect(other!.textContent).toBe(three!.textContent);
    expect(three!.getAttribute('aria-pressed')).toBe('true');
    expect(other!.getAttribute('aria-pressed')).toBe('false');
  });

  it('D#9 ‹ › 는 문서 전체를 한 쪽씩 · 끝에서 끔 · 쪽 칩 원형', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const prev = () =>
      screen.getByRole<HTMLButtonElement>('button', {
        name: words.source.pagePrev,
      });
    const next = () =>
      screen.getByRole<HTMLButtonElement>('button', {
        name: words.source.pageNext,
      });
    const page = () => screen.getByTestId('source-page').textContent;
    expect(page()).toBe(words.source.pageOf(2, 3));
    fireEvent.click(prev());
    expect(page()).toBe(words.source.pageOf(1, 3));
    expect(prev().disabled).toBe(true);
    fireEvent.click(next());
    fireEvent.click(next());
    expect(page()).toBe(words.source.pageOf(3, 3));
    expect(next().disabled).toBe(true);
    expect(
      screen.getByTestId('source-pane').querySelector('button[data-page="3"]')!
        .className,
    ).toContain('rounded-full');
  });

  it('D#11 못 만듦 빨간 상자 + 아이콘 · 맞는 자료 없음·아직 흰 상자 + 아이콘', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const tones: Record<string, string> = {
      a3: 'plain',
      a4: 'error',
      a5: 'plain',
    };
    for (const [key, tone] of Object.entries(tones)) {
      fireEvent.click(treeRow(key));
      const state = screen.getByTestId('leaf-state');
      expect(state.getAttribute('data-tone')).toBe(tone);
      expect(state.querySelector('svg')).not.toBeNull();
    }
  });

  it('문단까지만 줄은 범례 줄 밖 · 아이콘', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    fireEvent.click(within(bullets()[0]!).getAllByTestId('source-chip')[1]!);
    const line = await screen.findByTestId('paragraph-only');
    expect(screen.getByTestId('source-legend').contains(line)).toBe(false);
    expect(line.querySelector('svg')).not.toBeNull();
  });

  it('점 눈꼴 셋(RPW12) — 근거 빈 문장·자료 없음·실패·아직은 같은 빈 원 · 완성 채움 · 뜻(data-dot)은 넷이 서로 다름 · 주황·빨강 0', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const cls = (key: string) =>
      within(treeRow(key)).getByTestId('tree-dot').className;
    const open = ['a1', 'a3', 'a4', 'a5'];
    expect(new Set(open.map(cls)).size).toBe(1);
    expect(cls('a1').split(' ')).toEqual(
      expect.arrayContaining([
        'border',
        'border-text-tertiary',
        'bg-transparent',
      ]),
    );
    expect(cls('a2')).not.toBe(cls('a1'));
    expect(cls('a2').split(' ')).toContain('bg-text-primary');
    expect(
      new Set(open.map((key) => treeRow(key).getAttribute('data-dot'))),
    ).toEqual(new Set(['unsupported', 'no_material', 'failed', 'not_run']));
    for (const dot of within(screen.getByTestId('result-tree')).getAllByTestId(
      'tree-dot',
    ))
      expect(dot.className).not.toMatch(/support-(orange|error)/);
  });

  it('트리 — 점이 제목 뒤 · 대제목 굵게 · 머리 부제·탭 · 셈 12px 회색 꼴', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const row = treeRow('a1');
    expect(within(row).getByTestId('tree-dot').className).toContain(
      'rounded-full',
    );
    expect(within(row).getByTestId('tree-marks').className).toContain(
      'float-right',
    );
    expect(treeRow('a').className).toContain('font-bold');
    expect(treeRow('a1').className).not.toContain('font-bold');
    expect(screen.getByTestId('result-subtitle').textContent).toBe(
      words.subtitle(2026, '지어낸 보고서', '지어낸 보고서.pdf'),
    );
    expect(screen.getAllByRole('tab').map((tab) => tab.textContent)).toEqual([
      words.tab,
    ]);
    expect(treeRow('a1').className).toContain('border-l-text-primary');
    expect(treeRow('a2').className).toContain('border-l-transparent');
    expect(screen.getByTestId('result-counts').className).toContain(
      'text-text-tertiary',
    );
  });

  it('bullet — 갈래 글은 빨간 알약 · 고른 bullet 만 왼쪽 검정 막대', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const [first, second] = bullets();
    expect(within(second!).getByTestId('bullet-note').className).toContain(
      'bg-support-error-subtle',
    );
    fireEvent.click(within(first!).getByText(/지어낸 첫 bullet/));
    expect(first!.getAttribute('data-picked')).toBe('true');
    expect(first!.className).toContain('border-l-text-primary');
    expect(second!.className).toContain('border-l-transparent');
  });

  it('M3 부모 줄 → 잎을 골라도 원본 PDF 를 다시 열지 않는다', async () => {
    const { server, runId } = await seeded();
    const { openPdf } = await setup(server, runId);
    await waitFor(() => expect(openPdf).toHaveBeenCalledTimes(1));
    fireEvent.click(treeRow('a'));
    await flush();
    expect(screen.queryByTestId('source-sheet')).toBeNull();
    fireEvent.click(treeRow('a1'));
    await flush();
    await screen.findByTestId('source-sheet');
    expect(openPdf).toHaveBeenCalledTimes(1);
  });
});

describe('RPW3 결과 손질', () => {
  async function rebuilding(
    rebuild: string[],
    leaves = LEAVES,
    nodes?: OutlineNode[],
  ) {
    const { server, runId } = await seeded({ leaves });
    if (nodes) server.seedProject(1, { nodes });
    const store = storeOf(server);
    const next = await store.startRun(
      { projectId: 1, base: { runId, rebuild } },
      null,
    );
    const baseRun = next.kind === 'ok' ? next.value.runId : 0;
    server.runPatch(baseRun, { status: 'processing' });
    const { openPdf } = fakeOpenPdf();
    render(
      <RunScreen
        store={store}
        projectId={1}
        runId={baseRun}
        operator={false}
        onRun={vi.fn()}
        onPickRun={vi.fn()}
        onList={vi.fn()}
        openPdf={openPdf}
        pollMs={10_000}
      />,
    );
    await screen.findByTestId('run-result');
    await flush();
  }

  it('D2 잎 제목 두 줄 감쌈 + title · 들여쓰기 줄임 · 점은 줄 위쪽 맞춤', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const title = within(treeRow('a1')).getByTestId('tree-title');
    expect(title.className).toContain('line-clamp-2');
    expect(title.className).not.toContain('truncate');
    expect(title.getAttribute('title')).toBe('지어낸 a1');
    expect(treeRow('a1').style.paddingLeft).toBe('21px');
    expect(treeRow('a1').className).toContain('items-start');
    const marks = within(treeRow('a1')).getByTestId('tree-marks');
    expect(title.contains(marks)).toBe(true);
    expect(marks.className).toContain('float-right');
  });

  it('D4 못 만듦·아직도 함께 지으면 회색 한 줄 · 파란 점에 고리 · 그 잎을 고르면 「다시 만드는 중」', async () => {
    await rebuilding(['a1']);
    expect(screen.getByTestId('result-rebuilding-more').textContent).toBe(
      words.rebuildingMore,
    );
    const dot = within(treeRow('a4')).getByTestId('tree-dot').className;
    expect(dot).toContain('ring-support-blue-subtle');
    expect(dot.split(' ')).toContain('ring');
    expect(treeRow('a4').getAttribute('data-dot')).toBe('rebuilding');
    fireEvent.click(treeRow('a4'));
    expect(screen.getByTestId('leaf-rebuilding').textContent).toBe(
      words.rebuilding,
    );
    expect(screen.getByTestId('leaf-skeleton')).not.toBeNull();
  });

  it('D4 고른 목차만 지으면 회색 한 줄 0', async () => {
    const all = OUTLINE.filter((one) => one.key !== 'a').map((one) =>
      leafOf(one.key, {
        status: 'done',
        bullets: [{ text: '지어낸 줄', unsupported: false, sources: [] }],
      }),
    );
    await rebuilding(['a1'], all);
    expect(treeRow('a1').getAttribute('data-dot')).toBe('rebuilding');
    expect(screen.queryByTestId('result-rebuilding-more')).toBeNull();
  });

  it('D4 띠만 있고 rebuild [] — 바뀐 잎만 지으면 회색 한 줄 0', async () => {
    const all = OUTLINE.filter((one) => one.key !== 'a').map((one) =>
      leafOf(one.key, {
        status: 'done',
        bullets: [{ text: '지어낸 줄', unsupported: false, sources: [] }],
      }),
    );
    await rebuilding(
      [],
      all,
      OUTLINE.map((one) =>
        one.key === 'a1' || one.key === 'a2' ?
          { ...one, requirement: '지어낸 새 요구' }
        : one,
      ),
    );
    await waitFor(() =>
      expect(treeRow('a2').getAttribute('data-dot')).toBe('rebuilding'),
    );
    expect(treeRow('a1').getAttribute('data-dot')).toBe('rebuilding');
    expect(screen.queryByTestId('result-rebuilding-more')).toBeNull();
  });

  it('D5 base 실행 진행 중 실행 고르기는 결과 머리 안(셈과 한 줄) · 위 따로 줄 0', async () => {
    await rebuilding(['a1']);
    const picker = await screen.findByRole('button', {
      name: DR_TEXT.run.picker,
    });
    expect(picker.closest('[data-testid="run-result"]')).not.toBeNull();
    expect(screen.queryByTestId('run-picker-row')).toBeNull();
    expect(
      picker.parentElement!.closest('div.flex-wrap')!.textContent,
    ).toContain(screen.getByTestId('result-counts').textContent!);
  });

  it('D5 결과 있는 실패 — 띠 아래 [전체 다시 만들기] + 안내(04c 꼴) · 머리 단추 0 · 띠 안 단추 0', async () => {
    const { server, runId } = await seeded({
      status: {
        status: 'rejected',
        code: 'over_budget',
        stage: 'before_draft',
        message: SERVER_WORDS,
      },
    });
    await setup(server, runId);
    expect(screen.getByTestId('result-rejected-hint').textContent).toBe(
      DR_TEXT.run.failedHint,
    );
    const restart = screen.getAllByRole('button', {
      name: DR_TEXT.run.restartAll,
    });
    expect(restart).toHaveLength(1);
    expect(
      restart[0]!.compareDocumentPosition(
        screen.getByTestId('result-rejected'),
      ) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
    expect(
      within(screen.getByTestId('result-rejected')).queryByRole('button'),
    ).toBeNull();
  });

  it('D5 결과에 없는 잎도 경로 줄(지금 목차에서)', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    fireEvent.click(treeRow('a6'));
    expect(screen.getByTestId('leaf-path').textContent).toBe('지어낸 a › ');
  });
});

describe('RPW5 #7 결과 움직임 클래스', () => {
  it('세 칸 첫 그림 gw-m-rise', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    for (const id of ['result-tree', 'leaf-pane', 'source-card'])
      expect(screen.getByTestId(id).className).toContain('gw-m-rise');
  });

  it('잎을 바꾸면 bullet 칸이 새 마디로(key = 잎) gw-m-fade', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    const first = screen.getByTestId('leaf-fade');
    expect(first.className).toContain('gw-m-fade');
    const firstKey = first.getAttribute('data-leaf');
    const other = firstKey === 'a2' ? 'a1' : 'a2';
    fireEvent.click(treeRow(other));
    await flush();
    const next = screen.getByTestId('leaf-fade');
    expect(next.getAttribute('data-leaf')).toBe(other);
    expect(next).not.toBe(first);
    expect(first.isConnected).toBe(false);
    expect(next.className).toContain('gw-m-fade');
  });

  it('원문 보기 근거 문장 상자만 gw-m-mark · 빛 색 = 선 색(text-support-orange) · 문단 상자는 0', async () => {
    const { server, runId } = await seeded();
    await setup(server, runId);
    fireEvent.click(within(bullets()[0]!).getByText(/지어낸 첫 bullet/));
    await waitFor(() => expect(layers('sentence').length).toBeGreaterThan(0));
    for (const box of layers('sentence')) {
      expect(box.className).toContain('gw-m-mark');
      expect(box.className).toContain('border-support-orange');
      expect(box.className).toContain('text-support-orange');
    }
    for (const box of layers('block'))
      expect(box.className).not.toContain('gw-m-mark');
  });
});
