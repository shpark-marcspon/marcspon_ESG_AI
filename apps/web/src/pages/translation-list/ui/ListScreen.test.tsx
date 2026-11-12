// @vitest-environment jsdom
// 번역 목록 화면(밴드 TRW1a ③ — 발주서 §3-3 11). 진짜 실어댑터 + 가짜 영문번역 서버. 키트 Tabs(radix)는 mouseDown 으로 누른다.
//   탭 → state 쿼리 · 「내가 올린 것만」 → mine · 운영 관리자 → 그 칸 0 · 빈 꼴 둘([새 번역]·[거르기 풀기]) · 실패 → [다시 시도] 다시 부름 ·
//   줄·파트 누름 → 문서·묶음 열쇠(·파트). 다시 단추([이 파트만 다시]) 0.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  fakeDocument,
  fakeOptions,
  fakeRun,
  fakeTranslationServer,
  refusal,
  serverStoreOf,
} from '../../../entities/translation/api/testing.ts';
import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { ListScreen } from './ListScreen.tsx';

afterEach(cleanup);

const words = TR_TEXT.list;
const BATCH = '0b9f1a2c-3d4e-4f50-8a6b-7c8d9e0f1a2b';
const flush = () => act(async () => {});
const LIST = 'GET /translation/batches';
const COMPANY = '지어낸 회사'; // 가짜 서버 목록 답 companyName 의 기본(밴드 TRC1)

function seeded() {
  const server = fakeTranslationServer({
    documents: [fakeDocument(12, { fileName: 'sample_a_extract.docx' })],
    runs: [
      fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
      fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH), {
        status: 'failed',
        errorCode: 'step_error',
      }),
    ],
  });
  server.advance(30, { status: 'done' });
  return server;
}

async function draw(
  server: ReturnType<typeof fakeTranslationServer>,
  operator = false,
) {
  const calls = {
    onNewTranslation: vi.fn(),
    onOpenBatch: vi.fn(),
    onOpenPart: vi.fn(),
  };
  render(
    <ListScreen store={serverStoreOf(server)} operator={operator} {...calls} />,
  );
  await flush();
  return calls;
}
const lastQuery = (server: ReturnType<typeof fakeTranslationServer>) =>
  Object.fromEntries(
    server.calls.filter((c) => `${c.method} ${c.path}` === LIST).at(-1)!.query,
  );

describe('ListScreen (§3-3 11)', () => {
  it('머리·묶음 줄, 다시 단추 0 · 일반 사용자 설명 줄 없음(밴드 WT1, sid:MARC-ENT-625)', async () => {
    await draw(seeded());
    expect(screen.getByRole('heading', { name: words.title })).toBeTruthy();
    expect(screen.queryByText(words.metaOperator(COMPANY))).toBeNull();
    expect(screen.queryByText(/번역 \d+건|계정이 시작한 번역/)).toBeNull();
    expect(screen.getByText('sample_a_extract.docx')).toBeTruthy();
    expect(screen.queryByText(TR_TEXT.failure.retryPart)).toBeNull();
    expect(screen.queryByText(TR_TEXT.failure.retrySingle)).toBeNull();
  });

  it('탭 → state 쿼리(전체는 없음)', async () => {
    const server = seeded();
    await draw(server);
    expect(lastQuery(server)).toEqual({ limit: '20', offset: '0' });
    for (const [tab, state] of [
      ['active', 'active'],
      ['done', 'done'],
      ['failed', 'failed'],
    ] as const) {
      fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabs[tab] }));
      await flush();
      expect(lastQuery(server).state).toBe(state);
    }
    fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabs.all }));
    await flush();
    expect(lastQuery(server).state).toBeUndefined();
  });

  it('「내가 올린 것만」 → mine=true', async () => {
    const server = seeded();
    await draw(server);
    fireEvent.click(screen.getByRole('checkbox', { name: words.mineOnly }));
    await flush();
    expect(lastQuery(server).mine).toBe('true');
  });

  it('운영 관리자 → 「내가 올린 것만」 0·설명 줄은 「작업 회사 …」 하나', async () => {
    const server = seeded();
    await draw(server, true);
    expect(screen.queryByRole('checkbox', { name: words.mineOnly })).toBeNull();
    expect(screen.getByText(words.metaOperator(COMPANY)).textContent).toBe(
      `작업 회사 ${COMPANY}`,
    );
    expect(screen.queryByText(/번역 \d+건|계정이 시작한 번역/)).toBeNull();
    expect(screen.queryByText(/운영 관리자 ·/)).toBeNull();
    expect(lastQuery(server).mine).toBeUndefined();
  });

  it('작업 회사는 서버 목록 답 companyName — 운영 관리자만, 비면 줄 없음(TRC1 · 밴드 WT1)', async () => {
    await draw(
      fakeTranslationServer({ companyName: '다른 지어낸 회사' }),
      true,
    );
    expect(
      screen.getByText(words.metaOperator('다른 지어낸 회사')).textContent,
    ).toBe('작업 회사 다른 지어낸 회사');
    cleanup();
    await draw(fakeTranslationServer({ companyName: '다른 지어낸 회사' }));
    expect(screen.queryByText(/작업 회사|다른 지어낸 회사/)).toBeNull();
    cleanup();
    await draw(fakeTranslationServer({ companyName: '' }), true);
    expect(screen.queryByText(/작업 회사/)).toBeNull();
    expect(screen.queryByText(/번역 \d+건|계정이 시작한 번역/)).toBeNull();
  });

  it('빈 꼴: 아무것도 없으면 [새 번역], 거른 빈 꼴은 [거르기 풀기] → 전체로', async () => {
    const empty = fakeTranslationServer();
    const calls = await draw(empty);
    expect(screen.getByTestId('list-empty').textContent).toContain(words.empty);
    fireEvent.click(
      screen.getAllByRole('button', { name: words.newTranslation }).at(-1)!,
    );
    expect(calls.onNewTranslation).toHaveBeenCalled();
    fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabs.done }));
    await flush();
    expect(screen.getByTestId('list-empty-filtered')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: words.clearFilter }));
    await flush();
    expect(lastQuery(empty).state).toBeUndefined();
    expect(screen.getByTestId('list-empty')).toBeTruthy();
  });

  it('불러오기 실패 → [다시 시도] 가 다시 부른다', async () => {
    const server = seeded();
    server.override[LIST] = [() => refusal(500, 'INTERNAL')];
    await draw(server);
    expect(screen.getByText(words.loadFailed)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: words.retry }));
    await flush();
    expect(server.count(LIST)).toBe(2);
    expect(screen.getByText('sample_a_extract.docx')).toBeTruthy();
  });

  it('파일 이름(묶음 펼침)·파트 [결과 보기] → 문서·묶음 열쇠(·파트)', async () => {
    const calls = await draw(seeded());
    fireEvent.click(screen.getAllByText(words.viewResult)[0]!);
    expect(calls.onOpenBatch).toHaveBeenCalledWith('12', BATCH);
    // [TRP2 TE3] 펼침은 파일명 앞 꺾쇠 단추.
    fireEvent.click(screen.getByRole('button', { name: words.expandParts }));
    const results = screen.getAllByText(words.viewResult);
    fireEvent.click(results.at(-1)!);
    expect(calls.onOpenPart).toHaveBeenCalledWith('12', BATCH, 'ceo');
  });
});

// [TRP2 TE2·TE4] 파일명 검색(받은 줄 안에서 거름, 서버 요청·meta 수 그대로) · 0 이면 거른 빈 꼴 · [거르기 풀기]가 검색어도 비움 · 표 아래 안내.
describe('ListScreen 검색·안내(TRP2 TE2·TE4)', () => {
  const OTHER = '1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f';
  function two() {
    const server = fakeTranslationServer({
      documents: [
        fakeDocument(12, { fileName: 'sample_a_extract.docx' }),
        fakeDocument(13, { fileName: '연차보고서_추출본.txt' }),
      ],
      runs: [
        fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
        fakeRun(40, 13, fakeOptions('story', 1, 5, OTHER)),
      ],
    });
    server.advance(30, { status: 'done' });
    server.advance(40, { status: 'done' });
    return server;
  }
  const typeQuery = (value: string) =>
    fireEvent.change(screen.getByLabelText(words.searchLabel), {
      target: { value },
    });

  it('「연차」 → 그 줄만, 요청은 다시 가지 않음', async () => {
    const server = two();
    await draw(server);
    expect(screen.getByText('연차보고서_추출본.txt')).toBeTruthy();
    const before = server.calls.filter(
      (c) => `${c.method} ${c.path}` === LIST,
    ).length;
    typeQuery('연차');
    expect(screen.getByText('연차보고서_추출본.txt')).toBeTruthy();
    expect(screen.queryByText('sample_a_extract.docx')).toBeNull();
    expect(
      server.calls.filter((c) => `${c.method} ${c.path}` === LIST).length,
    ).toBe(before);
    expect(screen.getByTestId('list-guide').textContent).toBe(words.guide);
  });

  it('맞는 줄이 없으면 list-empty-filtered, [거르기 풀기]가 검색어도 비움 · 안내 상자는 표가 있을 때만', async () => {
    await draw(two());
    typeQuery('SAMPLE_A');
    expect(screen.getByText('sample_a_extract.docx')).toBeTruthy();
    typeQuery('없는 이름');
    expect(screen.getByTestId('list-empty-filtered')).toBeTruthy();
    expect(screen.queryByTestId('list-guide')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: words.clearFilter }));
    await flush();
    expect(
      (screen.getByLabelText(words.searchLabel) as HTMLInputElement).value,
    ).toBe('');
    expect(screen.getByText('sample_a_extract.docx')).toBeTruthy();
    expect(screen.getByText('연차보고서_추출본.txt')).toBeTruthy();
  });
});

describe('ListScreen 「번역 안내」 링크 (밴드 TRP3 TE1-d, sid:MARC-ENT-435)', () => {
  it('onIntro 를 넘기면 링크 href=/translation/intro · 누르면 onIntro 한 번(preventDefault) · 불러오는 중에도 보임', async () => {
    const onIntro = vi.fn();
    render(
      <ListScreen
        store={serverStoreOf(seeded())}
        operator={false}
        onNewTranslation={vi.fn()}
        onIntro={onIntro}
        onOpenBatch={vi.fn()}
        onOpenPart={vi.fn()}
      />,
    );
    // 목록을 받기 전(불러오는 중)에도 머리 링크는 있다.
    expect(screen.getByRole('link', { name: words.introLink })).toBeTruthy();
    await flush();
    const link = screen.getByRole('link', { name: words.introLink });
    expect(link.getAttribute('href')).toBe('/translation/intro');
    expect(link.className).toContain('text-text-secondary');
    expect(fireEvent.click(link)).toBe(false);
    expect(onIntro).toHaveBeenCalledTimes(1);
  });

  it('onIntro 를 넘기지 않으면 링크 0', async () => {
    await draw(seeded());
    expect(
      screen.queryAllByRole('link', { name: words.introLink }),
    ).toHaveLength(0);
  });
});

describe('ListScreen 첫 불러오기 (밴드 TRP5, sid:MARC-ENT-443)', () => {
  /** 목록 답을 open() 때까지 붙잡는 저장소. */
  function held(
    server: ReturnType<typeof fakeTranslationServer>,
    operator = false,
  ) {
    const real = serverStoreOf(server);
    let release = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    const store: typeof real = {
      ...real,
      listBatches: async (query) => {
        await gate;
        return real.listBatches(query);
      },
    };
    render(
      <ListScreen
        store={store}
        operator={operator}
        onNewTranslation={vi.fn()}
        onOpenBatch={vi.fn()}
        onOpenPart={vi.fn()}
      />,
    );
    return () =>
      act(async () => {
        release();
      });
  }
  const skeletonRows = () =>
    document.querySelectorAll(
      '[data-testid="batch-skeleton"] [data-skeleton-row]',
    );

  it('A-1·2 불러오는 중(일반 사용자): 표 머리줄 + 스켈레톤 줄 · 빈 꼴 0 · 설명 자리 0(설명 줄이 없다 — 밴드 WT1) → 0건 받은 뒤에만 빈 꼴', async () => {
    const open = held(fakeTranslationServer({ documents: [], runs: [] }));
    await flush();
    expect(screen.getByRole('heading', { name: words.title })).toBeTruthy();
    expect(screen.getByRole('table').querySelectorAll('thead th')).toHaveLength(
      7,
    );
    expect(skeletonRows()).toHaveLength(5);
    expect(screen.queryByTestId('list-empty')).toBeNull();
    expect(screen.queryByTestId('list-empty-filtered')).toBeNull();
    expect(screen.queryByTestId('list-guide')).toBeNull();
    expect(screen.queryByTestId('description-pending')).toBeNull();
    await open();
    expect(screen.getByTestId('list-empty')).toBeTruthy();
    expect(skeletonRows()).toHaveLength(0);
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(screen.queryByText(/번역 \d+건|계정이 시작한 번역/)).toBeNull();
  });

  it('A-1·2 불러오는 중(운영 관리자): 설명 자리 막대 → 받은 뒤 「작업 회사 …」(그린워싱 꼴 — 밴드 WT1)', async () => {
    const open = held(fakeTranslationServer({ documents: [], runs: [] }), true);
    await flush();
    expect(screen.getByTestId('description-pending')).toBeTruthy();
    expect(screen.queryByText(words.metaOperator(COMPANY))).toBeNull();
    await open();
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(screen.getByText(words.metaOperator(COMPANY))).toBeTruthy();
  });

  it('A-1·2 받은 뒤 줄이 있으면: 스켈레톤 → 묶음 줄, 설명 자리 0', async () => {
    const open = held(seeded());
    await flush();
    expect(skeletonRows()).toHaveLength(5);
    expect(screen.queryByText('sample_a_extract.docx')).toBeNull();
    await open();
    expect(skeletonRows()).toHaveLength(0);
    expect(screen.getByText('sample_a_extract.docx')).toBeTruthy();
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(screen.queryByText(/번역 \d+건/)).toBeNull();
  });
});

// [밴드 TRW1b §3-1 7] 목록의 [이 파트만 다시](결정 sid:MARC-ENT-393, 감독 판단 a — 됨이면 묶음 화면 그 파트 탭).
describe('ListScreen [이 파트만 다시] (TRW1b)', () => {
  const retried = () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12, { fileName: 'sample_a_extract.docx' })],
      runs: [
        fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
        fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH), {
          status: 'failed',
          errorCode: 'step_error',
        }),
        fakeRun(32, 12, fakeOptions('general', 10, 12, BATCH)),
      ],
      nextRunId: 40,
    });
    server.advance(30, {
      status: 'done',
      outcome: 'rejected',
      rejectionKind: 'too_large',
    });
    server.advance(32, { status: 'done' });
    return server;
  };
  const expand = () =>
    fireEvent.click(
      screen.getByRole('button', { name: TR_TEXT.list.expandParts }),
    );
  const retryButtons = () =>
    screen.queryAllByRole('button', { name: TR_TEXT.failure.retryPart });

  it('서버 오류 파트 줄만 단추 → 두 번 눌러도 POST 한 번(그 파트 최신 실행) → onOpenPart(문서, 묶음, 파트)', async () => {
    const server = retried();
    const { onOpenPart } = await draw(server);
    expand();
    // 거절(CEO)·완료(일반) 파트에는 단추 0 — 서버 오류(스토리) 하나만.
    expect(retryButtons()).toHaveLength(1);
    fireEvent.click(retryButtons()[0]!);
    fireEvent.click(retryButtons()[0]!);
    await flush();
    await flush();
    expect(server.count('GET /runs/31')).toBe(1);
    expect(server.count('POST /runs')).toBe(1);
    expect(server.runBodies()[0]!.options).toEqual(
      server.runs.get(31)!.options,
    );
    expect(onOpenPart).toHaveBeenCalledTimes(1);
    expect(onOpenPart).toHaveBeenCalledWith('12', BATCH, 'story');
    expect(screen.queryByTestId('retry-failed')).toBeNull();
  });

  it('거절 → 표 위 오류 한 줄 retryFailed, 이동 0', async () => {
    const server = retried();
    server.override['POST /runs'] = () => refusal(400, 'INVALID_OPTIONS');
    const { onOpenPart } = await draw(server);
    expand();
    fireEvent.click(retryButtons()[0]!);
    await flush();
    await flush();
    expect(screen.getByTestId('retry-failed').textContent).toBe(
      TR_TEXT.failure.retryFailed,
    );
    expect(onOpenPart).not.toHaveBeenCalled();
  });

  it('`run-` 열쇠 묶음(batchId 없는 옛 실행)은 다시 단추 0', async () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12, { fileName: 'sample_a_extract.docx' })],
      runs: [
        fakeRun(31, 12, fakeOptions('story', 4, 9, null), {
          status: 'failed',
          errorCode: 'step_error',
        }),
      ],
    });
    await draw(server);
    expect(screen.getByText('sample_a_extract.docx')).toBeTruthy();
    expect(screen.queryByText(TR_TEXT.failure.retrySingle)).toBeNull();
    expect(retryButtons()).toHaveLength(0);
  });
});

// 밴드 TRW6 ② S2: [PDF로 새 번역](6c v174 TR-01 — 머리와 빈 꼴 둘 다, [새 번역] 왼쪽). onNewPdf 가 없으면 0.
describe('ListScreen [PDF로 새 번역] (TRW6 ②)', () => {
  async function drawWithPdf(server: ReturnType<typeof fakeTranslationServer>) {
    const onNewPdf = vi.fn();
    const onNewTranslation = vi.fn();
    render(
      <ListScreen
        store={serverStoreOf(server)}
        operator={false}
        onNewTranslation={onNewTranslation}
        onNewPdf={onNewPdf}
        onOpenBatch={vi.fn()}
        onOpenPart={vi.fn()}
      />,
    );
    await flush();
    return { onNewPdf, onNewTranslation };
  }

  it('머리: [PDF로 새 번역] 이 [새 번역] 앞, 누르면 onNewPdf 한 번(onNewTranslation 0)', async () => {
    const { onNewPdf, onNewTranslation } = await drawWithPdf(seeded());
    const head = screen.getByTestId('new-pdf');
    expect(head.textContent).toBe(words.newPdf);
    const next = head.nextElementSibling!;
    expect(next.textContent).toBe(words.newTranslation);
    // 밴드 TRW14 ②(TR-01 c3 스펙): 단추 글은 「Word로 새 번역」(머리·빈 꼴 같은 상수).
    expect(next.textContent).toBe('Word로 새 번역');
    fireEvent.click(head);
    expect(onNewPdf).toHaveBeenCalledTimes(1);
    expect(onNewTranslation).not.toHaveBeenCalled();
  });

  it('빈 꼴에도 [새 번역] 앞에 있다', async () => {
    const { onNewPdf } = await drawWithPdf(fakeTranslationServer());
    const empty = screen.getByTestId('list-empty');
    const button = within(empty).getByTestId('new-pdf-empty');
    expect(button.nextElementSibling!.textContent).toBe(words.newTranslation);
    fireEvent.click(button);
    expect(onNewPdf).toHaveBeenCalledTimes(1);
  });

  // 밴드 TRW7 ③a D5(판 v182 TR-01): 빈 꼴 [새 번역]에도 머리와 같은 ＋.
  it('빈 꼴 [새 번역] 앞에 ＋ 아이콘(머리 단추와 같은 꼴)', async () => {
    await drawWithPdf(fakeTranslationServer());
    const empty = screen.getByTestId('list-empty');
    const button = within(empty).getByRole('button', {
      name: words.newTranslation,
    });
    expect(button.querySelector('svg[aria-hidden]')).not.toBeNull();
  });

  it('onNewPdf 가 없으면 단추 0', async () => {
    await draw(fakeTranslationServer());
    expect(screen.queryByTestId('new-pdf')).toBeNull();
    expect(screen.queryByTestId('new-pdf-empty')).toBeNull();
  });
});

// 밴드 TRW6 ④: 묶음 inputKind(TRS3 칸)가 pdf 인 줄만 파일명 앞 「PDF」 — 다른 묶음(워드) 줄은 0.
describe('ListScreen PDF 줄 (TRW6 ④)', () => {
  const OTHER = '1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f';
  it('PDF 흐름 묶음 줄 하나에만 「PDF」 · 워드 묶음 줄은 0', async () => {
    const server = fakeTranslationServer({
      documents: [
        fakeDocument(12, { fileName: 'sample_a_extract.docx' }),
        fakeDocument(14, { fileName: 'made_up_report.pdf' }),
      ],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 1, 3, BATCH)),
        fakeRun(31, 14, fakeOptions('general', 1, 3, OTHER), {
          flowId: 'translation.pdf@158',
        }),
      ],
    });
    server.advance(30, { status: 'done' });
    server.advance(31, { status: 'done' });
    await draw(server);
    await waitFor(() => screen.getByText('made_up_report.pdf'));
    const marks = screen.getAllByTestId('batch-pdf-mark');
    expect(marks).toHaveLength(1);
    expect(marks[0]!.textContent).toBe(words.pdfMark);
    expect(
      document
        .querySelector('[data-batch="14/' + OTHER + '"]')
        ?.contains(marks[0]!),
    ).toBe(true);
  });
});
