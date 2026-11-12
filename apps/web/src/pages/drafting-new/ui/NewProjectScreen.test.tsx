// @vitest-environment jsdom
// RP-02 새 보고서 프로젝트 · 전년도 보고서 올림(밴드 RPW1 ① 시험 S3 — 발주서 §2-1·§2-0 ②④). 진짜 실어댑터 + 가짜 원고작성 서버.
//   회사 고름 0 · 보고연도·이름 기본값 · 이름 칸 오류(빈·81자 — 코드 포인트) · .pdf 만 · [다음] 차례(만들기 → POST /documents → 서명 PUT → confirm →
//   PUT …/document → onDone) · hasText 거짓이면 달지 않고 「텍스트를 찾지 못했어요」 · hasText null 이면 PUT 에 맡김(422 → 같은 글) ·
//   올림 실패 → 「PDF 를 읽지 못했어요」, 프로젝트는 남고 다시 누르면 만들기를 건너뜀 · 만들기 422 fields · 만들기 실패 · 회사 거절 ·
//   다시 올리기(이름·연도 보기만, 만들기 0, 없는 프로젝트) · 서버 message 0.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { DraftingStore } from '../../../entities/drafting/api/index.ts';
import {
  fakeDraftingServer,
  refusal,
  storeOf,
  unreachable,
} from '../../../entities/drafting/api/testing.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import {
  NewProjectScreen,
  nameProblem,
  yearChoices,
} from './NewProjectScreen.tsx';

afterEach(cleanup);
beforeAll(() => {
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

const words = DR_TEXT.create;
const NOW = new Date('2026-10-30T09:00:00+09:00');
const flush = () => act(async () => {});
type Server = ReturnType<typeof fakeDraftingServer>;

function setup(
  server: Server = fakeDraftingServer(),
  {
    projectId = null,
    operator = false,
    reupload,
    patch = {},
  }: {
    projectId?: number | null;
    operator?: boolean;
    reupload?: boolean;
    patch?: Partial<DraftingStore>;
  } = {},
) {
  const onDone = vi.fn();
  const onCancel = vi.fn();
  render(
    <NewProjectScreen
      store={{ ...storeOf(server), ...patch }}
      projectId={projectId}
      reupload={reupload ?? projectId !== null}
      operator={operator}
      now={NOW}
      onDone={onDone}
      onCancel={onCancel}
    />,
  );
  return { server, onDone, onCancel };
}

const pdf = (name = '지어낸 전년도.pdf') =>
  new File(['%PDF-1.4 지어낸'], name, { type: 'application/pdf' });
async function pick(file = pdf()) {
  fireEvent.change(
    document.querySelector<HTMLInputElement>('input[type="file"]')!,
    { target: { files: [file] } },
  );
  await flush();
}
const nextButton = () => screen.getByRole('button', { name: words.next });
async function next() {
  await waitFor(() =>
    expect(nextButton().hasAttribute('disabled')).toBe(false),
  );
  fireEvent.click(nextButton());
  await flush();
}
const problem = () => screen.getByTestId('create-problem');
const order = (server: Server) =>
  server.calls.map((call) => `${call.method} ${call.path}`);

describe('RP-02 새로 — 칸', () => {
  it('회사 고름 0 · 보고연도 기본 올해(내년부터 다섯) · 이름 기본 「<해> 지속가능경영보고서」', async () => {
    setup();
    await flush();
    expect(screen.queryByLabelText('회사')).toBeNull();
    const year = screen.getByLabelText(words.yearLabel) as HTMLSelectElement;
    expect(year.value).toBe('2026');
    expect([...year.options].map((option) => option.value)).toEqual([
      '2027',
      '2026',
      '2025',
      '2024',
      '2023',
    ]);
    const name = screen.getByLabelText(words.nameLabel) as HTMLInputElement;
    expect(name.value).toBe(words.nameDefault(2026));
    fireEvent.change(year, { target: { value: '2025' } });
    expect(name.value).toBe(words.nameDefault(2025));
  });

  it('이름 칸 오류 — 빈 글 · 81자(코드 포인트), [다음] 꺼짐', async () => {
    expect(nameProblem('  ')).toBe(words.nameRequired);
    expect(nameProblem('😀'.repeat(80))).toBeNull();
    expect(nameProblem('😀'.repeat(81))).toBe(words.nameTooLong(80));
    setup();
    await pick();
    const name = screen.getByLabelText(words.nameLabel);
    fireEvent.change(name, { target: { value: '   ' } });
    fireEvent.blur(name);
    expect(await screen.findByText(words.nameRequired)).not.toBeNull();
    expect(nextButton().hasAttribute('disabled')).toBe(true);
  });

  it('PDF 를 고르기 전엔 [다음] 꺼짐 · .pdf 밖은 받지 않음', async () => {
    setup();
    await flush();
    expect(nextButton().hasAttribute('disabled')).toBe(true);
    await pick(new File(['지어낸'], '지어낸.docx'));
    expect(
      await screen.findByText(words.notPdf, { exact: false }),
    ).not.toBeNull();
    expect(nextButton().hasAttribute('disabled')).toBe(true);
  });

  it('yearChoices — 내년부터 다섯, 2000~2100 안', () => {
    expect(yearChoices(new Date('2100-06-01'))).toEqual([
      2100, 2099, 2098, 2097,
    ]);
  });
});

describe('RP-02 새로 — [다음]', () => {
  it('차례: 만들기 → POST /documents → 서명 PUT → confirm → PUT …/document → onDone(id)', async () => {
    const { server, onDone } = setup();
    await pick();
    await next();
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(1));
    expect(order(server)).toEqual([
      'POST /drafting/projects',
      'POST /documents',
      'POST /documents/101/confirm',
      'PUT /drafting/projects/1/document',
    ]);
    expect(server.bodies('POST /drafting/projects')).toEqual([
      { year: 2026, name: words.nameDefault(2026) },
    ]);
    expect(server.uploads).toHaveLength(1);
    expect(server.uploads[0]!.method).toBe('PUT');
    expect(server.bodies('PUT /drafting/projects/1/document')).toEqual([
      { documentId: 101 },
    ]);
  });

  it('이름은 앞뒤 공백을 걷어 보낸다', async () => {
    const { server } = setup();
    await pick();
    fireEvent.change(screen.getByLabelText(words.nameLabel), {
      target: { value: '  지어낸 보고서  ' },
    });
    await next();
    await waitFor(() =>
      expect(server.count('POST /drafting/projects')).toBe(1),
    );
    expect(server.bodies('POST /drafting/projects')[0]).toEqual({
      year: 2026,
      name: '지어낸 보고서',
    });
  });

  it('hasText 거짓 → 달지 않고 「텍스트를 찾지 못했어요」', async () => {
    const { server, onDone } = setup(fakeDraftingServer({ noText: true }));
    await pick();
    await next();
    await waitFor(() => expect(problem().dataset.problem).toBe('noText'));
    expect(problem().textContent).toBe(words.noText);
    // 밴드 WT1(sid:MARC-ENT-625, 시안 v233 RP-02): 「텍스트」 낱말.
    expect(problem().textContent).toBe(
      '이 PDF 에서 텍스트를 찾지 못했어요. 스캔본이면 텍스트 선택이 가능한 PDF 로 다시 만들어 올려 주세요',
    );
    expect(server.count('PUT /drafting/projects/1/document')).toBe(0);
    expect(onDone).not.toHaveBeenCalled();
  });

  it('hasText null → PUT 에 맡김(422 DOCUMENT_NO_TEXT_LAYER → 같은 글)', async () => {
    const server = fakeDraftingServer({ textUnknown: true });
    server.override['PUT /drafting/projects/1/document'] = () =>
      refusal(422, 'DOCUMENT_NO_TEXT_LAYER');
    const { onDone } = setup(server);
    await pick();
    await next();
    await waitFor(() => expect(problem().dataset.problem).toBe('noText'));
    expect(server.count('PUT /drafting/projects/1/document')).toBe(1);
    expect(onDone).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toContain('지어낸-서버글');
  });

  it('hasText null 이고 PUT 이 받으면 onDone', async () => {
    const { onDone } = setup(fakeDraftingServer({ textUnknown: true }));
    await pick();
    await next();
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(1));
  });

  it('올림 실패 → 「PDF 를 읽지 못했어요」 · 프로젝트는 남고 다시 누르면 만들기를 건너뜀', async () => {
    const server = fakeDraftingServer();
    server.override['POST /documents'] = [unreachable];
    const { onDone } = setup(server);
    await pick();
    await next();
    await waitFor(() => expect(problem().dataset.problem).toBe('readFailed'));
    expect(problem().textContent).toBe(words.readFailed);
    expect(server.count('POST /drafting/projects')).toBe(1);
    expect(
      (screen.getByLabelText(words.nameLabel) as HTMLInputElement).disabled,
    ).toBe(true);
    await next();
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(1));
    expect(server.count('POST /drafting/projects')).toBe(1);
  });

  it('달기 실패(끊김) → 「PDF 를 읽지 못했어요」', async () => {
    const server = fakeDraftingServer();
    server.override['PUT /drafting/projects/1/document'] = [unreachable];
    setup(server);
    await pick();
    await next();
    await waitFor(() => expect(problem().dataset.problem).toBe('readFailed'));
  });

  it('만들기 422 fields.name → 이름 칸 아래 한 줄(서버 message 0)', async () => {
    const server = fakeDraftingServer();
    server.override['POST /drafting/projects'] = () =>
      refusal(422, 'VALIDATION_ERROR', { name: ['지어낸-서버글-칸'] });
    const { onDone } = setup(server);
    await pick();
    await next();
    expect(await screen.findByText(words.nameRequired)).not.toBeNull();
    expect(server.count('POST /documents')).toBe(0);
    expect(onDone).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toContain('지어낸-서버글');
  });

  it('만들기 422 fields.year → 보고연도 아래 한 줄', async () => {
    const server = fakeDraftingServer();
    server.override['POST /drafting/projects'] = () =>
      refusal(422, 'VALIDATION_ERROR', { year: ['지어낸-서버글-칸'] });
    setup(server);
    await pick();
    await next();
    expect(await screen.findByText(words.yearInvalid)).not.toBeNull();
  });

  it('만들기 실패(끊김) → 「프로젝트를 만들지 못했어요」', async () => {
    const server = fakeDraftingServer();
    server.override['POST /drafting/projects'] = [unreachable];
    setup(server);
    await pick();
    await next();
    await waitFor(() => expect(problem().dataset.problem).toBe('createFailed'));
    expect(problem().textContent).toBe(words.createFailed);
  });

  it.each([
    [false, DR_TEXT.company.ambiguous],
    [true, DR_TEXT.companyOperator.ambiguous],
  ])('회사 거절(운영 관리자 %s) → 회사 글', async (operator, text) => {
    setup(fakeDraftingServer({ company: 'COMPANY_AMBIGUOUS' }), { operator });
    await pick();
    await next();
    await waitFor(() => expect(problem().dataset.problem).toBe('company'));
    expect(problem().textContent).toBe(text);
  });
});

describe('RP-02 다시 올리기', () => {
  function seeded() {
    return fakeDraftingServer({
      projects: [{ id: 7, name: '지어낸 보고서 가', year: 2025 }],
    });
  }

  it('이름·연도는 보기만 · 만들기 0 · PUT …/7/document → onDone(7)', async () => {
    const { server, onDone } = setup(seeded(), { projectId: 7 });
    expect(await screen.findByTestId('project-name')).not.toBeNull();
    expect(screen.getByTestId('project-name').textContent).toBe(
      '지어낸 보고서 가',
    );
    expect(screen.getByTestId('project-year').textContent).toBe('2025');
    expect(
      screen.getByRole('heading', { name: words.reuploadTitle }),
    ).not.toBeNull();
    await pick();
    await next();
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(7));
    expect(server.count('POST /drafting/projects')).toBe(0);
    expect(server.bodies('PUT /drafting/projects/7/document')).toEqual([
      { documentId: 101 },
    ]);
  });

  it('없는 프로젝트 → 「보고서 프로젝트를 찾지 못했어요」 + [목록으로]', async () => {
    const { onCancel } = setup(seeded(), { projectId: 99 });
    expect(await screen.findByText(words.projectMissing)).not.toBeNull();
    fireEvent.click(
      screen.getByRole('button', { name: DR_TEXT.common.toList }),
    );
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('주소 id 가 틀림(projectId null) → 요청 없이 찾지 못함', async () => {
    const { server } = setup(seeded(), { projectId: null, reupload: true });
    expect(await screen.findByText(words.projectMissing)).not.toBeNull();
    expect(server.calls).toEqual([]);
  });

  it('불러오지 못함 → [다시 시도]', async () => {
    const server = seeded();
    server.override['GET /drafting/projects/7'] = [unreachable];
    setup(server, { projectId: 7 });
    expect(await screen.findByText(words.projectLoadFailed)).not.toBeNull();
    fireEvent.click(screen.getByRole('button', { name: DR_TEXT.common.retry }));
    expect(await screen.findByTestId('project-name')).not.toBeNull();
  });
});

describe('RPW2 ② RP-02 손질', () => {
  const box = () => problem().querySelector('[data-tone="error"]');
  const nextOff = () => nextButton().hasAttribute('disabled');
  const fileCancel = (name = '지어낸 전년도.pdf') =>
    screen.getByRole('button', { name: words.cancelFile(name) });

  it('D#5 다시 올리기 부제는 다시 올리는 글 · 새로는 연도 글', async () => {
    const server = fakeDraftingServer({
      projects: [{ id: 7, name: '지어낸 보고서 가', year: 2025 }],
    });
    setup(server, { projectId: 7 });
    expect(
      await screen.findByText('전년도 보고서 PDF 를 다시 올려요'),
    ).not.toBeNull();
    expect(screen.queryByText(words.lead)).toBeNull();
    cleanup();
    setup();
    await flush();
    expect(screen.getByText(words.lead)).not.toBeNull();
  });

  it('D#5 읽기 실패 = 빨간 상자(아이콘) · [다른 PDF 올리기] 0 · [다음] 다시 누를 수 있음', async () => {
    const server = fakeDraftingServer();
    server.override['POST /documents/101/confirm'] = [unreachable];
    setup(server);
    await pick();
    await next();
    await waitFor(() => expect(problem().dataset.problem).toBe('readFailed'));
    expect(box()?.querySelector('svg')).not.toBeNull();
    expect(screen.queryByRole('button', { name: words.otherPdf })).toBeNull();
    expect(nextOff()).toBe(false);
  });

  it('D#12 텍스트 없음 → 빨간 상자 · [다음] 끔 · [다른 PDF 올리기] 가 파일을 걷고 창을 염 · 새로 고르면 다시 켬', async () => {
    const server = fakeDraftingServer({ noText: true });
    const { onDone } = setup(server);
    await pick();
    await next();
    await waitFor(() => expect(problem().dataset.problem).toBe('noText'));
    expect(box()?.textContent).toBe(words.noText);
    expect(nextOff()).toBe(true);
    const opened = vi
      .spyOn(HTMLInputElement.prototype, 'click')
      .mockImplementation(() => {});
    fireEvent.click(screen.getByRole('button', { name: words.otherPdf }));
    expect(opened).toHaveBeenCalledOnce();
    opened.mockRestore();
    expect(problem().textContent).toBe('');
    expect(screen.queryByText('지어낸 전년도.pdf')).toBeNull();
    expect(nextOff()).toBe(true);
    await pick(pdf('지어낸 다른.pdf'));
    expect(nextOff()).toBe(false);
    expect(onDone).not.toHaveBeenCalled();
    expect(server.count('POST /drafting/projects')).toBe(1);
  });

  it('파일 줄 — 고른 파일의 크기 KB·MB · 날짜 0', async () => {
    setup();
    await pick(new File([new Uint8Array(2048)], '가.pdf'));
    expect(screen.getByTestId('file-size').textContent).toBe('2KB');
    expect(document.body.textContent).not.toMatch(/\d{4}-\d{2}-\d{2}/);
    fireEvent.click(screen.getByRole('button', { name: '가.pdf 지우기' }));
    await flush();
    await pick(new File([new Uint8Array(2_621_440)], '나.pdf'));
    expect(screen.getByTestId('file-size').textContent).toBe('2.5MB');
  });

  it('D3 고르기만 한 파일 줄에 [취소] 0 — 드롭존 ✕ 로 걷음(요청 0) · [다음] 끔', async () => {
    const { server } = setup();
    await pick();
    expect(
      screen.queryByRole('button', {
        name: words.cancelFile('지어낸 전년도.pdf'),
      }),
    ).toBeNull();
    fireEvent.click(
      screen.getByRole('button', {
        name: '지어낸 전년도.pdf 지우기',
      }),
    );
    await flush();
    expect(screen.queryByTestId('file-size')).toBeNull();
    expect(nextOff()).toBe(true);
    expect(server.calls).toEqual([]);
  });

  it('[취소] 올리는 중 = 「올리는 중」 + signal 끊음 → 오류 글 0 · 달기 0 · 프로젝트는 남아 다시 만들지 않음', async () => {
    const server = fakeDraftingServer();
    let signal: AbortSignal | undefined;
    const uploadPdf: DraftingStore['uploadPdf'] = (_file, given) =>
      new Promise((resolve) => {
        signal = given;
        given!.addEventListener('abort', () => resolve({ kind: 'failed' }));
      });
    const { onDone } = setup(server, { patch: { uploadPdf } });
    await pick();
    await next();
    await waitFor(() => expect(signal).toBeDefined());
    expect(screen.getAllByText(words.uploading)).toHaveLength(1);
    const uploading = screen.getByTestId('file-uploading');
    const follows = (a: Element, b: Element) =>
      a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING;
    expect(follows(screen.getByTestId('file-size'), uploading)).toBeTruthy();
    expect(follows(uploading, fileCancel())).toBeTruthy();
    expect(signal!.aborted).toBe(false);
    fireEvent.click(fileCancel());
    await flush();
    expect(signal!.aborted).toBe(true);
    expect(problem().textContent).toBe('');
    expect(screen.queryByText(words.uploading)).toBeNull();
    expect(onDone).not.toHaveBeenCalled();
    expect(server.calls.map((call) => call.path)).toEqual([
      '/drafting/projects',
    ]);
  });
});

describe('RPW3 D3 텍스트 없음', () => {
  it('텍스트 없음 거절 뒤 파일 줄에 [취소] 0 · [다른 PDF 올리기] 는 그대로', async () => {
    setup(fakeDraftingServer({ noText: true }));
    await pick();
    await next();
    await waitFor(() => expect(problem().dataset.problem).toBe('noText'));
    expect(
      screen.queryByRole('button', {
        name: words.cancelFile('지어낸 전년도.pdf'),
      }),
    ).toBeNull();
    expect(screen.getByRole('button', { name: words.otherPdf })).not.toBeNull();
  });
});

describe('RPW5 #4 다시 올리기 첫 불러오기 몸(sid:MARC-ENT-443 ①)', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  /** 프로젝트 읽기를 문으로 막은 다시 올리기 화면. */
  function held() {
    const server = fakeDraftingServer({
      projects: [{ id: 7, name: '지어낸 보고서 가', year: 2025 }],
    });
    let open!: () => void;
    const gate = new Promise<void>((resolve) => (open = resolve));
    const base = storeOf(server);
    setup(server, {
      projectId: 7,
      patch: {
        getProject: async (id) => {
          await gate;
          return base.getProject(id);
        },
      },
    });
    return () => act(async () => open());
  }

  it('받기 전: 제목 아래 299ms 스켈레톤 0 / 300ms 스켈레톤 → 받으면 몸 · 스켈레톤 0', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const release = held();
    await flush();
    expect(
      screen.getByRole('heading', { name: words.reuploadTitle }),
    ).toBeTruthy();
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    act(() => vi.advanceTimersByTime(299));
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByTestId('load-skeleton')).toBeTruthy();
    expect(screen.queryByTestId('project-name')).toBeNull();
    await release();
    await flush();
    expect(screen.getByTestId('project-name')).toBeTruthy();
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
  });

  it('300ms 안에 받으면 스켈레톤을 그린 적이 없다', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const release = held();
    await flush();
    act(() => vi.advanceTimersByTime(200));
    await release();
    await flush();
    act(() => vi.advanceTimersByTime(500));
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    expect(screen.getByTestId('project-name')).toBeTruthy();
  });

  it('새 프로젝트(다시 올리기 아님)는 스켈레톤 0', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    setup();
    await flush();
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
  });
});

// 밴드 WT1(sid:MARC-ENT-625, 시안 v233 RP-02): 드롭존 형식 줄 「텍스트 선택이 가능한 PDF」 · 옛 낱말 0.
describe('WT1 드롭존 형식 줄', () => {
  it('「.pdf 하나 · 텍스트 선택이 가능한 PDF」 · 「글자를 고를」 0', async () => {
    setup();
    await flush();
    expect(words.dropFormats).toBe('.pdf 하나 · 텍스트 선택이 가능한 PDF');
    expect(screen.getByText(words.dropFormats)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/글자를 고를|글자가 없는/);
  });
});
