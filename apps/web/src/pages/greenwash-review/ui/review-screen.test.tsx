// @vitest-environment jsdom
// 밴드 FW2 ④: GW-05 문장 검토 + 05a·05b·05c. 세 칸·파트 탭·등급 탭·진행, 쪽 칸(상자 있음 = 등급 색 상자 + 태그 / 위치 없음 = 회색 안내,
// 한 결과 안에 둘이 섞임 — 발주서 덧붙임 1·2), PDF 없음 안내, 채택·제외 PUT 본문(marks 전부, 첫 표시도 state 없음 — 결함 D1, 둘째 표시 뒤 첫 표시 남음),
// 05a(사유 없음·「기타」 + 빈 설명 오류), 05b(GW-04 [확정]으로 들어오면 열린 채, 미검토 경고, 확정 본문은 미검토를 채택으로 채움), 05c(잠김).
// 글자는 문구 표(GW_TEXT) 값으로 단언한다.
// 밴드 LE1 ②: 불러오기 꼴(스켈레톤 300ms, 결과·검토 실패 → 본문 전체 실패 꼴 + 실패한 쪽만 [다시 시도], 없음 → [목록으로] 하나, 제목 줄 [요약으로] 숨김),
// dry-run 은 검토 읽기 상태와 무관(디자인 의심 (a)), 확정 저장 실패면 05b 를 닫는다(디자인 의심 (b)), 미리보기 칸 실패 + [다시 시도].
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../../../entities/greenwash/api/index.ts';
import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { nextEdits } from '../../../entities/greenwash/api/mock/index.ts';
import {
  deferredCalls,
  fakeStore,
} from '../../../entities/greenwash/api/mock/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type {
  CheckRowsSource,
  GreenwashReview,
  Level,
  ResultPosition,
  ReviewEdit,
  ReviewUpdate,
  ScanResult,
} from '../../../entities/greenwash/model/index.ts';
// 위험 라벨은 화면이 그리는 값 하나(RiskBadge 의 글자 = PARTS_TEXT.risk)로 단언한다 — 그린워싱 칸은 shared/ui/text.ts 를 못 가져온다(sid:MARC-ISSUE-308).
import { RISK_BADGE_LOOK } from '../../../shared/ui/risk-badge/index.ts';
import type { OpenPdf, PdfHandle } from '../../../widgets/doc-viewer/index.ts';
import { ReviewScreen } from './ReviewScreen.tsx';

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
  // jsdom 에는 object URL 이 없다(쪽 그림은 File → object URL → openPdf).
  URL.createObjectURL = vi.fn(() => 'blob:fake');
  URL.revokeObjectURL = vi.fn();
});

const words = GW_TEXT.reviewScreen;

const item = (
  page: number,
  parts: string[],
  level: Level,
  position: ResultPosition | null,
  evidence: number[],
) => ({
  page,
  parts,
  sentence: `문장 ${page}`,
  level,
  riskTags: level === 'Low' ? ['선언적 문장'] : ['미래 약속'],
  confirmedInEvidence: level === 'High' ? ['표가 있음'] : [],
  missingFields: level === 'Low' ? [] : ['기준연도'],
  reasonBullets: ['사유'],
  fixParagraph: '방향',
  evidencePages: evidence,
  evidenceInternal: '',
  position,
  exampleSentence: level === 'High' ? '예시 문장이에요' : null,
});

/** 문장 셋: 0 High(2쪽, 상자 있음) · 1 Mid(3쪽, 위치 없음, 근거 없음) · 2 Low(5쪽, 위치 없음). */
function resultJson() {
  const items = [
    // 두 줄짜리 자리: 상자 둘의 left·right 가 달라 합집합(바깥 상자)이 어느 한 상자와도 다르다(감독 R1)
    item(
      2,
      ['CEO'],
      'High',
      {
        page: 2,
        boxes: [
          [72, 100, 500, 114],
          [60, 116, 480, 130],
        ],
      },
      [6],
    ),
    item(3, ['회사'], 'Mid', null, []),
    item(5, ['기후'], 'Low', null, [5]),
  ];
  return {
    schemaVersion: 'greenwash.result@1',
    source: {
      fileName: '목-가상.pdf',
      sha256: 'c'.repeat(64),
      pageCount: 30,
    },
    config: {
      checker: {
        maxCandidatesPerPage: 3,
        maxCharsPageText: 1,
        evidenceK: 1,
        maxCharsPerChunk: 1,
        useEvidenceFailopen: false,
        maxCharsEvidenceTotal: 1,
        reportLevels: [],
        debug: false,
        debugPages: 0,
        batchEval: false,
        promptVersion: 'v',
      },
      chunking: {
        chunkSize: 1,
        chunkOverlap: 0,
        separators: [],
        normalize: true,
        embeddingBatchSize: 1,
      },
      chat: { temperature: 0, maxTokens: 1 },
    },
    models: { chat: 'c', embedding: 'e' },
    promptVersion: 'v',
    parts: [
      { name: 'CEO', pages: [2] },
      { name: '회사', pages: [3] },
      { name: '기후', pages: [5] },
    ],
    pages: [2, 3, 5],
    extraTerms: [],
    items,
    candidateStats: {
      raw: 3,
      hardDropped: 0,
      nonEnvDropped: 0,
      promoDropped: 0,
      tableDropped: 0,
      kept: 3,
      failedPages: [],
    },
    counts: { total: 3, byLevel: { High: 1, Mid: 1, Low: 1 }, byPart: {} },
    wordCounts: { total: [], pages: [] },
    dryRun: null,
    report: { file: 'greenwash-report.xlsx' },
  };
}

const reviewOf = (
  state: GreenwashReview['state'],
  marks: GreenwashReview['marks'] = [],
): GreenwashReview => ({
  schemaVersion: 'greenwash.review@3',
  evidence: [],
  rejudges: [],
  runId: 1,
  state,
  confirmedAt: state === 'confirmed' ? '2026-10-16T10:20:00+09:00' : null,
  confirmedBy: state === 'confirmed' ? { id: 1, name: '가상 사람' } : null,
  marks,
  edits: [],
});

/** 가짜 PDF: 그리기는 곧 끝난다. */
const fakeOpenPdf: OpenPdf = async () =>
  ({
    renderPage: () => ({ done: Promise.resolve(), cancel() {} }),
    close() {},
  }) satisfies PdfHandle;

/** 목처럼 PUT 을 갈아 끼우는 가짜 저장소. bodies 에 보낸 본문이 쌓인다. */
function reviewStore(
  options: {
    review?: GreenwashReview;
    pdf?: File | null;
    result?: unknown;
    /** 확정된 검토의 confirmedBy 이름(null 이면 confirmedBy 가 null). 주지 않으면 review 그대로(reviewOf 는 「가상 사람」). */
    confirmedBy?: string | null;
  } = {},
) {
  let current = options.review ?? reviewOf('pending');
  if (current.state === 'confirmed' && options.confirmedBy !== undefined)
    current = {
      ...current,
      confirmedBy:
        options.confirmedBy === null ?
          null
        : { id: 1, name: options.confirmedBy },
    };
  const bodies: ReviewUpdate[] = [];
  const store = fakeStore({
    // 쪽 그림의 PDF 는 실행의 문서에서(밴드 FW2 ⑤ M2)
    getRun: vi.fn(async () => ({ documentId: 'doc-1' }) as never),
    listCheckRows: vi.fn(async (): Promise<CheckRowsSource> => ({
      currentUserId: 'u',
      companyName: '가상 회사',
      documents: [
        {
          documentId: 'doc-1',
          fileName: '목-가상.pdf',
          pageCount: 30,
          reportYear: null,
          previousDocumentId: null,
          uploadedAt: '2026-10-15T09:00:00+09:00',
          uploadedBy: { userId: 'u', name: '가상 올린 이' },
        },
      ],
      runs: [
        {
          runId: 'run-1',
          documentId: 'doc-1',
          createdAt: '2026-10-15T09:00:00+09:00',
          progress: { state: 'done' } as never,
          levelCounts: null,
          review: {
            state: current.state,
            reviewed: current.marks.length,
            total: 3,
            confirmedAt: current.confirmedAt,
            confirmedBy: current.confirmedBy?.name ?? null,
          },
        },
      ],
    })),
    getResult: vi.fn(async () => options.result ?? resultJson()),
    getReview: vi.fn(async () => current),
    putReview: vi.fn(async (_runId: string, update: ReviewUpdate) => {
      bodies.push(update);
      if (current.state === 'confirmed')
        throw new StoreError('review_locked', '확정됨');
      // 서버 규칙(결함 D1): 표시가 있으면 pending → in_review, confirmed 면 확정.
      const state =
        update.state === 'confirmed' ? 'confirmed'
        : current.state === 'pending' && update.marks.length > 0 ? 'in_review'
        : current.state;
      current = {
        ...current,
        state,
        confirmedAt: state === 'confirmed' ? '2026-10-16T11:00:00+09:00' : null,
        confirmedBy:
          state === 'confirmed' ? { id: 2, name: '지금 사람' } : null,
        marks: update.marks.map((mark) => ({ ...mark })),
      };
      return current;
    }),
    openDocumentPdf: vi.fn(async () =>
      options.pdf === undefined ?
        new File(['%PDF'], '목-가상.pdf', { type: 'application/pdf' })
      : options.pdf,
    ),
  });
  return { store, bodies };
}

async function renderReview(
  store: GreenwashStore,
  props: { initialConfirm?: boolean } = {},
) {
  const onBack = vi.fn();
  const onList = vi.fn();
  await act(async () => {
    render(
      <ReviewScreen
        store={store}
        openPdf={fakeOpenPdf}
        runId="run-1"
        onBack={onBack}
        onList={onList}
        {...props}
      />,
    );
  });
  // 결과·검토·둘레·PDF 읽기와 그리기를 기다린다
  await act(async () => {});
  await act(async () => {});
  return { onBack, onList };
}

const rowsOf = () =>
  within(screen.getByTestId('sentence-list')).getAllByRole('button');
const detail = () => screen.getByTestId('review-detail');
const choice = (name: string) =>
  within(
    within(detail()).getByRole('group', { name: GW_TEXT.review.groupLabel }),
  ).getByRole('button', { name });

async function clickRow(index: number) {
  await act(async () => {
    fireEvent.click(rowsOf()[index]!);
  });
  await act(async () => {});
}

describe('GW-05 문장 검토', () => {
  it('세 칸: 문장 줄 셋(첫 줄 aria-current), 진행 「검토 0/3」·「채택 0 · 제외 0 · 미검토 3」, 파트 탭(전체 3 · 파트별 1), 등급 탭 마지막 「미검토」', async () => {
    const { store } = reviewStore();
    await renderReview(store);
    expect(screen.getByRole('heading', { level: 2 }).textContent).toContain(
      words.title,
    );
    expect(screen.getByText(words.meta('목-가상.pdf', 3))).toBeTruthy();
    expect(rowsOf()).toHaveLength(3);
    expect(rowsOf()[0]!.getAttribute('aria-current')).toBe('true');
    expect(rowsOf()[1]!.getAttribute('aria-current')).toBeNull();
    expect(screen.getByTestId('review-progress').textContent).toContain(
      words.progress(0, 3),
    );
    expect(screen.getByTestId('review-tally').textContent).toBe(
      words.tally(0, 0, 3),
    );
    const parts = screen.getByRole('tablist', { name: words.partTabsLabel });
    expect(
      within(parts)
        .getAllByRole('tab')
        .map((tab) => tab.textContent),
    ).toEqual([
      words.partTab(words.allParts, 3),
      words.partTab('CEO', 1),
      words.partTab('회사', 1),
      words.partTab('기후', 1),
    ]);
    const levels = screen.getByRole('tablist', { name: words.levelTabsLabel });
    expect(within(levels).getAllByRole('tab').at(-1)!.textContent).toBe(
      words.levelTabs.pending,
    );
    // 근거 쪽이 없는 줄은 「· 근거 없음」
    expect(rowsOf()[1]!.textContent).toContain(
      words.rowMeta(['회사'], 3, true),
    );
  });

  it('쪽 칸: position 있으면 등급 색 상자 + 태그(안내 없음), null 이면 회색 안내 + 상자 없음 — 한 결과 안에 둘이 섞인다', async () => {
    const { store } = reviewStore();
    await renderReview(store);
    // 0번(High, 2쪽, 상자 있음)
    const highlight = screen.getByTestId('highlight');
    expect(highlight.getAttribute('data-level')).toBe('High');
    // 바깥 상자 = 합집합 [60, 100, 500, 130](첫 상자만이면 72·100·428·14)
    expect(highlight.style.left).toBe('60px');
    expect(highlight.style.top).toBe('100px');
    expect(highlight.style.width).toBe('440px');
    expect(highlight.style.height).toBe('30px');
    // 문장 상자(테두리)는 위치 칸보다 사방 4px 바깥(디자인 대조 C4). 위치 칸의 자리·크기는 위 그대로
    const frame = highlight.querySelector('span[aria-hidden]') as HTMLElement;
    expect([
      frame.style.top,
      frame.style.right,
      frame.style.bottom,
      frame.style.left,
    ]).toEqual(['-4px', '-4px', '-4px', '-4px']);
    expect(
      within(highlight).getByText(RISK_BADGE_LOOK.high.label),
    ).toBeTruthy();
    expect(screen.queryByTestId('position-missing')).toBeNull();
    expect(screen.getByTestId('page-heading').textContent).toBe(
      words.pageHeading(2),
    );
    const pageImage = screen.getByRole('img', {
      name: words.pageImage(2, 'High'),
    });
    // 쪽 그림자는 디자인 값 그대로(이슈 453 — 없는 클래스 shadow-normal 은 그림자를 안 그렸다)
    expect(pageImage.parentElement!.className).toContain(
      'shadow-[0_0_5px_2px_rgb(0_0_0/0.1)]',
    );
    expect(
      document.querySelector('canvas')?.getAttribute('data-render-state'),
    ).toBe('done');
    // 1번(Mid, 3쪽, 위치 없음)
    await clickRow(1);
    expect(rowsOf()[1]!.getAttribute('aria-current')).toBe('true');
    expect(screen.getByTestId('position-missing').textContent).toBe(
      GW_TEXT.review.positionMissing,
    );
    expect(screen.queryByTestId('highlight')).toBeNull();
    expect(screen.getByTestId('page-heading').textContent).toBe(
      words.pageHeading(3),
    );
    expect(
      screen.getByRole('img', { name: words.pageImage(3, null) }),
    ).toBeTruthy();
  });

  it('쪽 이동: [다음 쪽]이면 그 문장의 쪽을 떠나 상자가 없다, 다른 문장을 고르면 그 문장의 쪽으로', async () => {
    const { store } = reviewStore();
    await renderReview(store);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.nextPage }));
    });
    expect(screen.getByTestId('page-of').textContent).toBe(words.pageOf(3, 30));
    expect(screen.queryByTestId('highlight')).toBeNull();
    await clickRow(2);
    expect(screen.getByTestId('page-of').textContent).toBe(words.pageOf(5, 30));
    await clickRow(0);
    expect(screen.getByTestId('page-of').textContent).toBe(words.pageOf(2, 30));
    expect(screen.getByTestId('highlight')).toBeTruthy();
  });

  it('PDF 가 없으면(씨앗 문서) 「미리보기를 열 수 없어요」 하나만, 위치 없는 문장의 안내는 없다(쪽을 못 보여 준다. C3)', async () => {
    const { store } = reviewStore({ pdf: null });
    await renderReview(store);
    expect(screen.getByTestId('preview-unavailable').textContent).toBe(
      words.previewUnavailable,
    );
    expect(screen.queryByTestId('highlight')).toBeNull();
    await clickRow(1);
    expect(rowsOf()[1]!.getAttribute('aria-current')).toBe('true');
    expect(screen.queryByTestId('position-missing')).toBeNull();
    expect(screen.getByTestId('preview-unavailable')).toBeTruthy();
  });

  it('상세: 머리는 「참고한 근거 페이지 …」만(문장 페이지 「n페이지 · 」 지움 — 시안 댓글 중복 정보, sid:MARC-ENT-603), 근거 확인은 「근거에서 확인됨」만, 근거 쪽이 없으면 안내. 위험 유형·「빠진 근거」·예시 문장 칸은 없다(v115 GW-05_r2 — 밴드 GW2R ①)', async () => {
    const { store } = reviewStore();
    await renderReview(store);
    expect(
      within(detail()).getByTestId('detail-evidence-pages').textContent,
    ).toBe('참고한 근거 페이지 6');
    expect(detail().textContent).not.toContain('2페이지 · ');
    const evidence = within(detail()).getByTestId('evidence');
    expect(evidence.textContent).toContain(words.confirmedInEvidence);
    expect(evidence.textContent).toContain('표가 있음');
    // 결과 문장에 riskTags·missingFields·exampleSentence 가 있어도 그리지 않는다
    expect(detail().textContent).not.toMatch(
      /빠진 근거|기준연도|위험 유형|미래 약속|예시 문장/,
    );
    expect(within(detail()).queryByTestId('example')).toBeNull();
    expect(within(detail()).queryByTestId('no-evidence')).toBeNull();
    // Mid: 근거 쪽 없음 → 안내, 확인됨 없음 → 근거 칸은 칩 0 으로 남는다(r4 ① — 근거를 찾지 못한 문장도 고칠 수 있으면 [+ 근거 더하기], GRJ1)
    await clickRow(1);
    expect(within(detail()).getByTestId('no-evidence').textContent).toBe(
      words.noEvidence,
    );
    // 근거가 없으면 머리에 근거 페이지 글을 그리지 않는다(아래 안내가 말한다)
    expect(within(detail()).queryByTestId('detail-evidence-pages')).toBeNull();
    const empty = within(detail()).getByTestId('evidence');
    expect(within(empty).getByTestId('chips').children).toHaveLength(0);
    expect(within(empty).getByTestId('evidence-edit')).toBeTruthy();
    expect(detail().textContent).not.toMatch(/빠진 근거|기준연도|미래 약속/);
    // Low: 칩 0 · [고치기] 있음
    await clickRow(2);
    expect(
      within(within(detail()).getByTestId('evidence')).getByTestId('chips')
        .children,
    ).toHaveLength(0);
  });

  it('채택: PUT 이 끝난 뒤 표시·진행 +1. 첫 표시 본문에 state 를 싣지 않고(결함 D1), 둘째 표시 본문에 첫 표시가 남는다(marks 전부)', async () => {
    const { store, bodies } = reviewStore();
    await renderReview(store);
    await act(async () => {
      fireEvent.click(choice(GW_TEXT.review.adopted));
    });
    expect(bodies[0]).toEqual({
      marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
    });
    expect(screen.getByTestId('review-progress').textContent).toContain(
      words.progress(1, 3),
    );
    expect(
      rowsOf()[0]!.querySelector('[data-review]')?.getAttribute('data-review'),
    ).toBe('adopted');
    expect(screen.getByTestId('review-state').getAttribute('data-state')).toBe(
      'in_review',
    );
    // 제목 줄 배지는 n 없이 「검토 중」(n 은 왼쪽 진행에만. 디자인 대조 C6)
    expect(
      screen.getByTestId('review-state').querySelector('[data-status]')
        ?.textContent,
    ).toBe(GW_TEXT.runStatus.reviewing);
    // 검토 화면은 목록 원재료를 읽지 않는다 — 확정한 사람은 검토의 confirmedBy 에서(밴드 WC1 ①)
    expect(store.listCheckRows).not.toHaveBeenCalled();
    await clickRow(2);
    await act(async () => {
      fireEvent.click(choice(GW_TEXT.review.adopted));
    });
    expect(bodies[1]).toEqual({
      marks: [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
        { itemIndex: 2, decision: 'adopted', excludeReason: null },
      ],
    });
    // 저장 뒤 끝에 「 · 자동 저장됨 HH:MM」(밴드 GW2R ② Q6 — 시각 값은 「자동 저장」 시험이 고정 시계로 잰다)
    expect(screen.getByTestId('review-tally').textContent).toMatch(
      /^채택 2 · 제외 0 · 미검토 1 · 자동 저장됨 \d\d:\d\d$/,
    );
  });

  it('05a: 사유 없이 [제외]는 오류, 「기타」 + 빈 설명은 설명 칸 아래 오류(PUT 없음), 설명을 쓰면 「기타: 설명」으로 저장', async () => {
    const { store, bodies } = reviewStore();
    await renderReview(store);
    await clickRow(1);
    await act(async () => {
      fireEvent.click(choice(GW_TEXT.review.excluded));
    });
    const dialog = screen.getByRole('dialog', { name: GW_TEXT.exclude.title });
    expect(dialog.textContent).toContain(words.quoteMeta(['회사'], 3, 'Mid'));
    const submit = within(dialog).getByRole('button', {
      name: GW_TEXT.exclude.submit,
    });
    fireEvent.click(submit);
    expect(within(dialog).getByRole('alert').textContent).toBe(
      GW_TEXT.exclude.reasonRequired,
    );
    fireEvent.click(
      within(dialog).getByRole('radio', {
        name: GW_TEXT.exclude.reasons.other,
      }),
    );
    fireEvent.change(
      within(dialog).getByRole('textbox', { name: GW_TEXT.exclude.noteLabel }),
      { target: { value: '   ' } },
    );
    await act(async () => {
      fireEvent.click(submit);
    });
    expect(within(dialog).getByRole('alert').textContent).toBe(
      words.noteRequired,
    );
    const note = within(dialog).getByRole('textbox', {
      name: GW_TEXT.exclude.noteLabel,
    });
    expect(note.getAttribute('aria-invalid')).toBe('true');
    expect(bodies).toHaveLength(0);
    fireEvent.change(note, { target: { value: ' 홍보 문구예요 ' } });
    await act(async () => {
      fireEvent.click(submit);
    });
    await act(async () => {});
    expect(bodies[0]).toEqual({
      marks: [
        {
          itemIndex: 1,
          decision: 'excluded',
          excludeReason: `${GW_TEXT.exclude.reasons.other}: 홍보 문구예요`,
        },
      ],
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    // 저장 뒤 끝에 「 · 자동 저장됨 HH:MM」(밴드 GW2R ② Q6 — 시각 값은 「자동 저장」 시험이 고정 시계로 잰다)
    expect(screen.getByTestId('review-tally').textContent).toMatch(
      /^채택 0 · 제외 1 · 미검토 2 · 자동 저장됨 \d\d:\d\d$/,
    );
  });

  it('05b: GW-04 [확정]으로 들어오면(initialConfirm) 열린 채 시작, 미검토 경고, [확정] 본문은 미검토를 채택으로 채운 marks 전부 → 05c', async () => {
    const { store, bodies } = reviewStore({
      review: reviewOf('in_review', [
        { itemIndex: 1, decision: 'excluded', excludeReason: '기타: 가' },
      ]),
    });
    const { onList, onBack } = await renderReview(store, {
      initialConfirm: true,
    });
    // 확정 전에는 [목록으로 돌아가기]가 없다(확정 뒤에만 — sid:MARC-ENT-603)
    expect(screen.queryByTestId('confirmed-to-list')).toBeNull();
    const dialog = screen.getByRole('dialog', { name: GW_TEXT.confirm.title });
    expect(dialog.textContent).toContain(GW_TEXT.confirm.unreviewedWarning(2));
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole('button', { name: GW_TEXT.confirm.submit }),
      );
    });
    await act(async () => {});
    expect(bodies[0]).toEqual({
      state: 'confirmed',
      marks: [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
        { itemIndex: 1, decision: 'excluded', excludeReason: '기타: 가' },
        { itemIndex: 2, decision: 'adopted', excludeReason: null },
      ],
    });
    // 05c: 잠금 띠(확정 일시 + 다시 읽은 확정한 사람), 버튼 없음, 등급 탭 마지막 「제외」, 검토 줄 「확정됨 · 바꿀 수 없음」
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.querySelector('[data-lock-banner]')?.textContent).toBe(
      GW_TEXT.lock.banner({ by: '지금 사람', at: '2026-10-16 11:00' }),
    );
    expect(screen.queryByRole('button', { name: words.confirm })).toBeNull();
    expect(
      within(detail()).queryByRole('group', {
        name: GW_TEXT.review.groupLabel,
      }),
    ).toBeNull();
    expect(within(detail()).getByText(words.locked)).toBeTruthy();
    const levels = screen.getByRole('tablist', { name: words.levelTabsLabel });
    expect(within(levels).getAllByRole('tab').at(-1)!.textContent).toBe(
      words.levelTabs.excluded,
    );
    // 머리 [내려받기]는 켜져 있다(밴드 GDL1 — 옛 [엑셀 내보내기 · 확정본]을 갈음. 모달 줄의 누름은 server-review 시험이 잰다)
    const opener = screen.getByTestId('gw-downloads');
    expect(opener.getAttribute('aria-disabled')).toBeNull();
    expect(opener.querySelector('svg[aria-hidden]')).not.toBeNull();
    expect(opener.textContent).toBe(GW_TEXT.downloads.title);
    expect(screen.getByTestId('review-tally').textContent).toBe(
      words.tally(2, 1, 0),
    );
    // 05c 제목 줄: [요약으로] 옆 같은 꼴 [목록으로 돌아가기] → onList(목록 /greenwash — 시안 댓글, sid:MARC-ENT-603)
    const toList = screen.getByRole('button', { name: words.toList });
    const back = screen.getByRole('button', { name: words.back });
    expect(toList.getAttribute('data-testid')).toBe('confirmed-to-list');
    expect(toList.className).toBe(back.className);
    expect(back.nextElementSibling).toBe(toList);
    fireEvent.click(toList);
    expect(onList).toHaveBeenCalledTimes(1);
    expect(onBack).not.toHaveBeenCalled();
  });

  it('05b: [확정] 버튼으로 연다. 미검토가 0이면 경고 문장이 없다', async () => {
    const all = [0, 1, 2].map((i) => ({
      itemIndex: i,
      decision: 'adopted' as const,
      excludeReason: null,
    }));
    const { store } = reviewStore({ review: reviewOf('in_review', all) });
    await renderReview(store);
    expect(screen.queryByRole('dialog')).toBeNull();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.confirm }));
    });
    const dialog = screen.getByRole('dialog', { name: GW_TEXT.confirm.title });
    expect(dialog.querySelector('[data-unreviewed]')).toBeNull();
  });

  it('확정된 검토(05c)는 initialConfirm 이어도 05b 를 열지 않는다. 잠금 띠의 사람은 둘레 값', async () => {
    const { store } = reviewStore({
      review: reviewOf('confirmed', [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
      ]),
    });
    await renderReview(store, { initialConfirm: true });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.querySelector('[data-lock-banner]')?.textContent).toBe(
      GW_TEXT.lock.banner({ by: '가상 사람', at: '2026-10-16 10:20' }),
    );
    // 05c 도 위험 유형·「빠진 근거」·예시 문장 칸이 없다(v115 GW-05c_r2 — 밴드 GW2R ①)
    expect(within(detail()).getByTestId('evidence').textContent).toContain(
      words.confirmedInEvidence,
    );
    expect(detail().textContent).not.toMatch(
      /빠진 근거|기준연도|위험 유형|미래 약속|예시 문장/,
    );
  });

  it('[요약으로]는 onBack. 등급 탭 「미검토」는 표시 없는 줄만', async () => {
    const { store } = reviewStore({
      review: reviewOf('in_review', [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
      ]),
    });
    const { onBack } = await renderReview(store);
    const levels = screen.getByRole('tablist', { name: words.levelTabsLabel });
    await act(async () => {
      fireEvent.mouseDown(
        within(levels).getByRole('tab', { name: words.levelTabs.pending }),
      );
    });
    expect(rowsOf().map((row) => row.getAttribute('data-item'))).toEqual([
      '1',
      '2',
    ]);
    fireEvent.click(screen.getByRole('button', { name: words.back }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it('저장이 409(잠김)면 「이미 확정된 검토라 바꿀 수 없어요」(role="alert") + 다시 읽은 잠긴 상태(05c)', async () => {
    const { store } = reviewStore({ review: reviewOf('in_review') });
    await renderReview(store);
    // 다른 곳에서 이미 확정됐다: PUT 은 review_locked, 다시 읽으면 confirmed
    store.putReview = vi.fn(async () => {
      throw new StoreError('review_locked', '확정됨');
    });
    store.getReview = vi.fn(async () =>
      reviewOf('confirmed', [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
      ]),
    );
    await act(async () => {
      fireEvent.click(choice(GW_TEXT.review.adopted));
    });
    await act(async () => {});
    expect(screen.getByTestId('save-error').getAttribute('role')).toBe('alert');
    expect(screen.getByTestId('save-error').textContent).toBe(words.saveLocked);
    expect(screen.getByTestId('review-state').getAttribute('data-state')).toBe(
      'confirmed',
    );
    expect(document.querySelector('[data-lock-banner]')).not.toBeNull();
  });

  it.each([
    ['run_not_done', words.saveRunNotDone],
    ['no_review', words.saveNoReview],
  ] as const)(
    '저장이 409(%s)면 그 까닭의 글(일반 실패 글이 아니다)',
    async (code, text) => {
      const { store } = reviewStore({ review: reviewOf('in_review') });
      await renderReview(store);
      store.putReview = vi.fn(async () => {
        throw new StoreError(code, '409');
      });
      await act(async () => {
        fireEvent.click(choice(GW_TEXT.review.adopted));
      });
      await act(async () => {});
      expect(screen.getByTestId('save-error').textContent).toBe(text);
      expect(text).not.toMatch(/\.$/);
    },
  );

  it('읽기 갈래: 결과 없음 → 회색 「결과를 찾을 수 없어요」(role="alert") + [목록으로] 하나, 제목 줄 [요약으로] 없음', async () => {
    const { store } = reviewStore();
    store.getResult = vi.fn(async () => {
      throw new StoreError('not_found', '없음');
    });
    const { onList, onBack } = await renderReview(store);
    const alert = screen.getByRole('alert');
    expect(alert.getAttribute('data-kind')).toBe('missing');
    expect(alert.querySelector('[data-tone]')?.textContent).toBe(
      words.missing.result,
    );
    expect(
      document
        .querySelector('[data-screen="review"]')
        ?.getAttribute('data-review-state'),
    ).toBe('missing');
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      GW_TEXT.load.toList,
    ]);
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.toList }));
    expect(onList).toHaveBeenCalledTimes(1);
    expect(onBack).not.toHaveBeenCalled();
  });

  it('미리보기는 실행(getRun)의 문서로 연다 — 목록 읽기가 거절돼도 그린다. 실행 읽기가 없음(404)이면 「불러오는 중」이 아니라 회색 안내(단추 없음), 그 밖의 거절이면 실패 칸', async () => {
    const { store } = reviewStore();
    store.listCheckRows = vi.fn(async () => {
      throw new Error('목록 거절');
    });
    await renderReview(store);
    expect(screen.getByTestId('highlight')).toBeTruthy();
    expect(store.openDocumentPdf).toHaveBeenCalledWith('doc-1');
    cleanup();
    const second = reviewStore().store;
    second.getRun = vi.fn(async () => {
      throw new StoreError('not_found', '없음');
    });
    await renderReview(second);
    expect(screen.queryByText(words.previewLoading)).toBeNull();
    // 없음(ENT-260 ③): 다시 해도 같으니 [다시 시도] 없이 previewUnavailable
    expect(screen.queryByTestId('preview-failed')).toBeNull();
    expect(screen.getByTestId('preview-unavailable').textContent).toBe(
      words.previewUnavailable,
    );
    expect(
      within(screen.getByTestId('review-page')).queryByRole('button', {
        name: GW_TEXT.load.retry,
      }),
    ).toBeNull();
    cleanup();
    const third = reviewStore().store;
    third.getRun = vi.fn(async () => {
      throw new Error('망');
    });
    await renderReview(third);
    expect(screen.queryByText(words.previewLoading)).toBeNull();
    expect(screen.getByTestId('preview-failed-text').textContent).toBe(
      words.previewFailed,
    );
  });

  it('「미검토」 탭에서 [채택]을 두 번 눌러도 다음 문장은 채택되지 않는다. 저장 중 버튼은 aria-disabled 이고 초점이 남는다', async () => {
    const { store, bodies } = reviewStore();
    let release: () => void = () => {};
    const put = store.putReview;
    store.putReview = vi.fn(
      (runId: string, update: ReviewUpdate) =>
        new Promise<unknown>((resolve) => {
          release = () => resolve(put(runId, update));
        }),
    );
    await renderReview(store);
    const levels = screen.getByRole('tablist', { name: words.levelTabsLabel });
    await act(async () => {
      fireEvent.mouseDown(
        within(levels).getByRole('tab', { name: words.levelTabs.pending }),
      );
    });
    const adopt = choice(GW_TEXT.review.adopted);
    adopt.focus();
    await act(async () => {
      fireEvent.click(adopt);
    });
    // 저장 중: 진짜 disabled 가 아니라 aria-disabled, 초점은 그 버튼에
    expect(adopt.getAttribute('aria-disabled')).toBe('true');
    expect((adopt as HTMLButtonElement).disabled).toBe(false);
    expect(document.activeElement).toBe(adopt);
    await act(async () => {
      fireEvent.click(adopt);
    });
    await act(async () => {
      release();
    });
    await act(async () => {});
    // 저장 뒤 0번은 미검토 탭에서 빠지고 상세는 1번(새로 그린 부품). 옛 버튼을 다시 눌러도 아무 일 없다
    expect(detail().getAttribute('data-item')).toBe('1');
    await act(async () => {
      fireEvent.click(adopt);
    });
    await act(async () => {});
    expect(store.putReview).toHaveBeenCalledTimes(1);
    expect(bodies).toEqual([
      {
        marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
      },
    ]);
  });

  it('「미검토」 탭에서 채택해 상세가 다음 문장으로 바뀌면, 앞 상세가 초점을 가졌을 때만 새 상세의 검토 줄 첫 단추로 초점을 잇는다(sid:MARC-ISSUE-105 1)', async () => {
    const { store } = reviewStore();
    await renderReview(store);
    const levels = screen.getByRole('tablist', { name: words.levelTabsLabel });
    await act(async () => {
      fireEvent.mouseDown(
        within(levels).getByRole('tab', { name: words.levelTabs.pending }),
      );
    });
    // jsdom 의 click 은 초점을 주지 않는다 — 누르기 전에 그 단추에 초점
    const adopt = choice(GW_TEXT.review.adopted);
    adopt.focus();
    await act(async () => {
      fireEvent.click(adopt);
    });
    await act(async () => {});
    expect(detail().getAttribute('data-item')).toBe('1');
    const first = within(detail())
      .getByTestId('review-row')
      .querySelector('button');
    expect(first).not.toBeNull();
    expect(document.activeElement).toBe(first);
    // 초점이 상세 밖(body)이면 옮기지 않는다
    (document.activeElement as HTMLElement).blur();
    await act(async () => {
      fireEvent.click(choice(GW_TEXT.review.adopted));
    });
    await act(async () => {});
    expect(detail().getAttribute('data-item')).toBe('2');
    expect(document.activeElement).toBe(document.body);
  });

  it('05a [제외] 제출 뒤 초점은 그 문장의 검토 줄로 돌아온다. 설명을 고치면 설명 오류가 사라진다', async () => {
    const { store } = reviewStore();
    await renderReview(store);
    await clickRow(1);
    const exclude = choice(GW_TEXT.review.excluded);
    exclude.focus();
    await act(async () => {
      fireEvent.click(exclude);
    });
    const dialog = screen.getByRole('dialog', { name: GW_TEXT.exclude.title });
    fireEvent.click(
      within(dialog).getByRole('radio', {
        name: GW_TEXT.exclude.reasons.other,
      }),
    );
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole('button', { name: GW_TEXT.exclude.submit }),
      );
    });
    expect(within(dialog).getByRole('alert').textContent).toBe(
      words.noteRequired,
    );
    fireEvent.change(
      within(dialog).getByRole('textbox', { name: GW_TEXT.exclude.noteLabel }),
      { target: { value: '가' } },
    );
    expect(within(dialog).queryByRole('alert')).toBeNull();
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole('button', { name: GW_TEXT.exclude.submit }),
      );
    });
    // Radix 모달 닫힘의 초점 사건은 setTimeout(0) 뒤에 온다
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    await act(async () => {});
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(detail().getAttribute('data-item')).toBe('1');
    expect(
      within(detail())
        .getByTestId('review-row')
        .contains(document.activeElement),
    ).toBe(true);
  });

  it('잠금 띠 글자(디자인 결정 sid:MARC-TICK-73 노트 7O60U5DTjjM2GHugu2Es9): 「{일시} {이름}님이 …」, 이름이 비면 「{일시}에 …」', async () => {
    const confirmedOne = reviewOf('confirmed', [
      { itemIndex: 0, decision: 'adopted', excludeReason: null },
    ]);
    await renderReview(reviewStore({ review: confirmedOne }).store);
    expect(document.querySelector('[data-lock-banner]')?.textContent).toBe(
      '2026-10-16 10:20 가상 사람님이 확정했어요. 채택·제외를 더 바꿀 수 없고, 엑셀은 확정본(채택한 문장)으로 나가요.',
    );
    cleanup();
    await renderReview(
      reviewStore({ review: confirmedOne, confirmedBy: null }).store,
    );
    expect(document.querySelector('[data-lock-banner]')?.textContent).toBe(
      '2026-10-16 10:20에 확정했어요. 채택·제외를 더 바꿀 수 없고, 엑셀은 확정본(채택한 문장)으로 나가요.',
    );
  });
});

describe('GW-05 불러오기·오류 꼴(밴드 LE1)', () => {
  const dryRunJson = () => ({
    ...resultJson(),
    items: [],
    candidateStats: null,
    counts: null,
    report: null,
    dryRun: {
      pagesChecked: 1,
      pagesWithText: 1,
      pagesTruncated: 0,
      chunks: 1,
      embeddingIndex: dryTally,
      ruleCandidates: 0,
      lower: {
        chat: dryTally,
        chatByKind: dryKinds,
        embeddingQueries: dryTally,
        judged: 0,
      },
      upper: {
        chat: dryTally,
        chatByKind: dryKinds,
        embeddingQueries: dryTally,
        outputTokensMax: 0,
        evidenceChars: 0,
        evidenceCapReached: false,
      },
      perPage: [],
    },
  });

  it('검토 읽기 실패 → 본문 전체 실패 꼴 「검토를 불러오지 못했어요」 + [다시 시도]·[목록으로], [다시 시도]는 검토만 다시 읽는다', async () => {
    const { store } = reviewStore();
    const getReview = store.getReview;
    store.getReview = vi
      .fn<GreenwashStore['getReview']>()
      .mockRejectedValueOnce(new Error('망'))
      .mockImplementation(getReview);
    await renderReview(store);
    const alert = screen.getByRole('alert');
    expect(alert.getAttribute('data-kind')).toBe('failed');
    expect(alert.querySelector('[data-tone]')?.textContent).toBe(
      words.failed.review,
    );
    expect(document.querySelector('[aria-busy]')).toBeNull();
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      GW_TEXT.load.retry,
      GW_TEXT.load.toList,
    ]);
    expect(screen.queryByRole('button', { name: words.back })).toBeNull();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    });
    await act(async () => {});
    expect(store.getReview).toHaveBeenCalledTimes(2);
    expect(store.getResult).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByTestId('sentence-list')).toBeTruthy();
  });

  it('결과·검토 둘 다 실패면 결과의 글, [다시 시도] 한 번에 결과·검토를 함께 다시 읽고(각 2번) 둘 다 받으면 본문', async () => {
    const { store } = reviewStore();
    const getResult = store.getResult;
    const getReview = store.getReview;
    store.getResult = vi
      .fn<GreenwashStore['getResult']>()
      .mockRejectedValueOnce(new Error('망'))
      .mockImplementation(getResult);
    store.getReview = vi
      .fn<GreenwashStore['getReview']>()
      .mockRejectedValueOnce(new Error('망'))
      .mockImplementation(getReview);
    await renderReview(store);
    expect(
      screen.getByRole('alert').querySelector('[data-tone]')?.textContent,
    ).toBe(words.failed.result);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    });
    await act(async () => {});
    expect(store.getResult).toHaveBeenCalledTimes(2);
    expect(store.getReview).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByTestId('sentence-list')).toBeTruthy();
  });

  it('결과만 실패·검토는 읽는 중(미룸)이면 [다시 시도]는 결과만 다시 읽는다(getReview 1번)', async () => {
    const { store } = reviewStore();
    store.getResult = vi.fn(async () => {
      throw new Error('망');
    });
    const pendingReview = deferredCalls<unknown>();
    store.getReview = pendingReview.fn as never;
    await renderReview(store);
    expect(
      screen.getByRole('alert').querySelector('[data-tone]')?.textContent,
    ).toBe(words.failed.result);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    });
    expect(store.getResult).toHaveBeenCalledTimes(2);
    expect(store.getReview).toHaveBeenCalledTimes(1);
  });

  it('결과만 실패·검토는 없음(404)이면 [다시 시도]는 결과만 다시 읽는다(getReview 1번) — 그다음은 검토 없음 꼴', async () => {
    const { store } = reviewStore();
    const getResult = store.getResult;
    store.getResult = vi
      .fn<GreenwashStore['getResult']>()
      .mockRejectedValueOnce(new Error('망'))
      .mockImplementation(getResult);
    store.getReview = vi.fn(async () => {
      throw new StoreError('not_found', '없음');
    });
    await renderReview(store);
    expect(
      screen.getByRole('alert').querySelector('[data-tone]')?.textContent,
    ).toBe(words.failed.result);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    });
    await act(async () => {});
    expect(store.getResult).toHaveBeenCalledTimes(2);
    expect(store.getReview).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole('alert').querySelector('[data-tone]')?.textContent,
    ).toBe(words.missing.review);
  });

  it('미룬 읽기: 바깥 [data-screen] 은 0ms·299ms 에도 aria-busy(스켈레톤은 없음), 300ms 에는 스켈레톤 하나(카드엔 aria-busy 없음). 제목 줄 [요약으로]·STEP 3 은 처음부터. ready 뒤 [aria-busy] 0', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    try {
      const { store } = reviewStore();
      const pending = deferredCalls<unknown>();
      store.getResult = pending.fn as never;
      const view = render(
        <ReviewScreen
          store={store}
          openPdf={fakeOpenPdf}
          runId="run-1"
          onBack={() => {}}
          onList={() => {}}
        />,
      );
      expect(screen.getByRole('button', { name: words.back })).toBeTruthy();
      expect(
        screen.getByRole('list', { name: GW_TEXT.stepFlow.label }),
      ).toBeTruthy();
      const outer = () => view.container.querySelector('[data-screen]')!;
      expect(outer().getAttribute('aria-busy')).toBe('true');
      expect(screen.queryByTestId('review-skeleton')).toBeNull();
      act(() => vi.advanceTimersByTime(299));
      expect(outer().getAttribute('aria-busy')).toBe('true');
      expect(screen.queryByTestId('review-skeleton')).toBeNull();
      act(() => vi.advanceTimersByTime(1));
      expect(screen.getAllByTestId('review-skeleton')).toHaveLength(1);
      const skeleton = screen.getByTestId('review-skeleton');
      expect(skeleton.getAttribute('aria-busy')).toBeNull();
      expect(outer().getAttribute('aria-busy')).toBe('true');
      expect(skeleton.textContent).toBe(words.loading);
      // 화면 꼴 스켈레톤(밴드 GL2): 낭독 글은 role="status" 하나 · 공용 카드 0
      expect(skeleton.getAttribute('role')).toBe('status');
      expect(skeleton.getAttribute('aria-label')).toBe(words.loading);
      expect(screen.getAllByRole('status')).toHaveLength(1);
      expect(screen.queryByTestId('load-skeleton')).toBeNull();
      await act(async () => pending.calls[0]!.resolve(resultJson()));
      await act(async () => {});
      expect(screen.getByTestId('sentence-list')).toBeTruthy();
      expect(screen.queryByTestId('review-skeleton')).toBeNull();
      expect(view.container.querySelector('[aria-busy]')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('미룬 읽기의 제목 줄(밴드 GL1): 제목 「문장 검토」는 처음부터 진짜 글, 설명(파일 이름·문장 수)만 막대 자리 → 받으면 설명 글', async () => {
    const { store } = reviewStore();
    const pending = deferredCalls<unknown>();
    store.getResult = pending.fn as never;
    render(
      <ReviewScreen
        store={store}
        openPdf={fakeOpenPdf}
        runId="run-1"
        onBack={() => {}}
        onList={() => {}}
      />,
    );
    expect(screen.getByRole('heading', { level: 2 }).textContent).toContain(
      words.title,
    );
    expect(screen.queryByTestId('title-pending')).toBeNull();
    expect(screen.getByTestId('description-pending')).toBeTruthy();
    await act(async () => pending.calls[0]!.resolve(resultJson()));
    await act(async () => {});
    expect(screen.getByTestId('sentence-list')).toBeTruthy();
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(screen.getByText(/^목-가상\.pdf · \d+문장$/)).toBeTruthy();
  });

  it('(a) 결과가 dry-run 이면 검토 읽기가 404 여도 dry-run 안내(없음 꼴이 아니다)', async () => {
    const { store } = reviewStore({ result: dryRunJson() });
    store.getReview = vi.fn(async () => {
      throw new StoreError('not_found', '없음');
    });
    await renderReview(store);
    expect(screen.getByTestId('dry-run').textContent).toBe(
      GW_TEXT.result.dryRun,
    );
    expect(screen.queryByRole('alert')).toBeNull();
    expect(
      document
        .querySelector('[data-screen="review"]')
        ?.getAttribute('data-review-state'),
    ).toBe('dry-run');
    expect(document.querySelector('[aria-busy]')).toBeNull();
  });

  it('(b) 확정 저장이 거절되면 05b 를 닫고 본문의 save-error 가 보인다', async () => {
    const { store } = reviewStore({ review: reviewOf('in_review') });
    await renderReview(store, { initialConfirm: true });
    store.putReview = vi.fn(async () => {
      throw new StoreError('run_not_done', '409');
    });
    const dialog = screen.getByRole('dialog', { name: GW_TEXT.confirm.title });
    await act(async () => {
      fireEvent.click(
        within(dialog).getByRole('button', { name: GW_TEXT.confirm.submit }),
      );
    });
    await act(async () => {});
    expect(store.putReview).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('save-error').textContent).toBe(
      words.saveRunNotDone,
    );
  });

  it('미리보기 칸 실패: 회색 칸 + 작은 [다시 시도] → 누르면 실행·PDF 를 다시 읽어 쪽을 그린다', async () => {
    const { store } = reviewStore();
    const getRun = store.getRun;
    store.getRun = vi
      .fn<GreenwashStore['getRun']>()
      .mockRejectedValueOnce(new Error('망'))
      .mockImplementation(getRun);
    await renderReview(store);
    const cell = screen.getByTestId('preview-failed');
    expect(cell.getAttribute('role')).toBe('status');
    expect(screen.getByTestId('preview-failed-text').textContent).toBe(
      words.previewFailed,
    );
    await act(async () => {
      fireEvent.click(
        within(cell).getByRole('button', { name: GW_TEXT.load.retry }),
      );
    });
    await act(async () => {});
    await act(async () => {});
    expect(store.getRun).toHaveBeenCalledTimes(2);
    expect(screen.queryByTestId('preview-failed')).toBeNull();
    expect(screen.getByTestId('highlight')).toBeTruthy();
  });

  describe('GW-05 [다시 시도] 뒤 초점(밴드 LA1 ②)', () => {
    /** 실패를 차례로 낸 뒤 원래 읽기로 돌아가는 가짜. */
    function failing<A extends unknown[], R>(
      real: (...args: A) => Promise<R>,
      times: number,
    ) {
      const fn = vi.fn(real);
      for (let n = 0; n < times; n += 1)
        fn.mockRejectedValueOnce(new Error(`망 ${n}`));
      return fn;
    }
    const click = async (button: HTMLElement) => {
      await act(async () => {
        fireEvent.click(button);
      });
      await act(async () => {});
      await act(async () => {});
    };

    it('본문: 첫 실패에서는 body 그대로 → [다시 시도] → 또 실패면 새 [다시 시도] → [다시 시도] → 받으면 본문 제목 줄 h2', async () => {
      const { store } = reviewStore();
      store.getResult = failing(store.getResult, 2);
      await renderReview(store);
      expect(screen.getByRole('alert')).toBeTruthy();
      expect(document.activeElement).toBe(document.body);
      const first = screen.getByRole('button', { name: GW_TEXT.load.retry });
      await click(first);
      const second = screen.getByRole('button', { name: GW_TEXT.load.retry });
      expect(second).not.toBe(first);
      expect(document.activeElement).toBe(second);
      await click(second);
      expect(screen.getByTestId('sentence-list')).toBeTruthy();
      expect(document.activeElement).toBe(
        document.querySelector('[data-screen="review"] h2'),
      );
    });

    it('dry-run: 결과 실패 → [다시 시도] → dry-run 이면 그 제목 줄 h2, [aria-busy] 0', async () => {
      const { store } = reviewStore({ result: dryRunJson() });
      store.getResult = failing(store.getResult, 1);
      await renderReview(store);
      expect(document.activeElement).toBe(document.body);
      await click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
      expect(screen.getByTestId('dry-run')).toBeTruthy();
      expect(document.activeElement).toBe(
        screen.getByRole('heading', { level: 2, name: words.title }),
      );
      expect(document.querySelector('[aria-busy]')).toBeNull();
    });

    it('미리보기 칸: 첫 실패에서는 body 그대로 → [다시 시도] → 또 실패면 새 [다시 시도] → [다시 시도] → 받으면 칸 머리 h3', async () => {
      const { store } = reviewStore();
      store.getRun = failing(store.getRun, 2);
      await renderReview(store);
      const cellRetry = () =>
        within(screen.getByTestId('preview-failed')).getByRole('button', {
          name: GW_TEXT.load.retry,
        });
      expect(document.activeElement).toBe(document.body);
      const first = cellRetry();
      await click(first);
      const second = cellRetry();
      expect(second).not.toBe(first);
      expect(document.activeElement).toBe(second);
      await click(second);
      expect(screen.queryByTestId('preview-failed')).toBeNull();
      expect(screen.getByTestId('highlight')).toBeTruthy();
      const heading = screen.getByTestId('page-heading');
      expect(document.activeElement).toBe(heading);
      // 초점을 받는 h3 는 Button 과 같은 focus-visible 바깥선(밴드 SB2 ①)
      const classes = heading.className.split(/\s+/);
      for (const name of [
        'focus-visible:outline',
        'focus-visible:outline-2',
        'focus-visible:outline-offset-2',
        'focus-visible:outline-border-secondary',
      ])
        expect(classes).toContain(name);
    });

    it('미리보기 칸: [다시 시도] 뒤 없음(404)이면 칸 머리 h3(단추가 없다)', async () => {
      const { store } = reviewStore();
      const getRun = store.getRun;
      store.getRun = vi
        .fn<GreenwashStore['getRun']>()
        .mockRejectedValueOnce(new Error('망'))
        .mockRejectedValueOnce(new StoreError('not_found', '없음'))
        .mockImplementation(getRun);
      await renderReview(store);
      await click(
        within(screen.getByTestId('preview-failed')).getByRole('button', {
          name: GW_TEXT.load.retry,
        }),
      );
      expect(screen.getByTestId('preview-unavailable')).toBeTruthy();
      expect(document.activeElement).toBe(screen.getByTestId('page-heading'));
    });
  });
});

const dryTally = {
  requests: 0,
  inputChars: 0,
  inputTokens: { status: 'measured', encoding: 'x', value: 0 },
};
const dryKinds = {
  detect: dryTally,
  eval: dryTally,
  lowOnly: dryTally,
  repair: dryTally,
};

describe('GW-05 고침(밴드 G1b-3 ③ — GW-05_r2·05c_r2)', () => {
  const ME = { id: 5, name: '가상 담당' };
  const SAVED_AT = '2026-10-22T14:28:00+09:00';
  const PERSON_A = { id: 11, name: '가상 고친이 A' };
  const PERSON_B = { id: 12, name: '가상 고친이 B' };
  const levelLow: ReviewEdit = {
    itemIndex: 0,
    level: {
      value: 'Low',
      editedAt: '2026-10-15T14:28:00+09:00',
      editedBy: PERSON_A,
    },
    reasonBullets: null,
    fixParagraph: null,
  };

  /** 서버 규칙(목 nextEdits — 정규화·칸별 때·사람·400)대로 PUT 을 받는 가짜 저장소. bodies 에 보낸 본문이 쌓인다. */
  function editStore(
    first: GreenwashReview,
    options: { put?: (update: ReviewUpdate) => Promise<unknown> } = {},
  ) {
    let current = first;
    const bodies: ReviewUpdate[] = [];
    const result = resultJson() as unknown as ScanResult;
    const store = fakeStore({
      getRun: vi.fn(async () => ({ documentId: 'doc-1' }) as never),
      getResult: vi.fn(async () => resultJson()),
      getReview: vi.fn(async () => current),
      putReview: vi.fn(async (_runId: string, update: ReviewUpdate) => {
        bodies.push(update);
        if (options.put) return options.put(update);
        if (current.state === 'confirmed')
          throw new StoreError('review_locked', '확정됨');
        const edits =
          update.edits == null ?
            current.edits
          : nextEdits(result, current.edits, update.edits, {
              at: SAVED_AT,
              by: ME,
            });
        if (typeof edits === 'string') throw new StoreError('rejected', edits);
        const touched =
          update.marks.length > 0 || (update.edits != null && edits.length > 0);
        current = {
          ...current,
          state:
            update.state === 'confirmed' ? 'confirmed'
            : current.state === 'pending' && touched ? 'in_review'
            : current.state,
          marks: update.marks.map((mark) => ({ ...mark })),
          edits: structuredClone(edits) as ReviewEdit[],
        };
        return current;
      }),
    });
    return { store, bodies };
  }

  const field = (column: 'reasonBullets' | 'fixParagraph') =>
    within(detail()).getByTestId(`field-${column}`);
  const editButton = (column: 'reasonBullets' | 'fixParagraph') =>
    within(field(column)).getByRole('button', { name: '고치기' });
  const levelButton = () =>
    within(detail()).getByRole('button', { name: '등급 고르기' });

  async function pickLevel(level: Level) {
    await act(async () => {
      fireEvent.keyDown(levelButton(), { key: 'Enter' });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('menuitemradio', { name: level }));
    });
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
    await act(async () => {});
  }

  it('목록·tally·탭은 보이는 등급(고친 값 ?? AI): 고친 줄에 「고침」, 「… · 고친 문장 n」, Low 탭에 High → Low 로 고친 문장', async () => {
    const { store } = editStore({
      ...reviewOf('in_review'),
      edits: [
        levelLow,
        {
          itemIndex: 2,
          level: null,
          reasonBullets: null,
          fixParagraph: {
            value: '고친 방향',
            editedAt: '2026-10-16T09:05:00+09:00',
            editedBy: PERSON_B,
          },
        },
      ],
    });
    await renderReview(store);
    const rows = rowsOf();
    expect(
      rows.map((row) =>
        row.querySelector('[data-level]')!.getAttribute('data-level'),
      ),
    ).toEqual(['low', 'mid', 'low']);
    expect(
      rows.map(
        (row) => row.querySelector('[data-edited]')?.textContent ?? null,
      ),
    ).toEqual(['고침', null, '고침']);
    expect(screen.getByTestId('review-tally').textContent).toBe(
      '채택 0 · 제외 0 · 미검토 3 · 고친 문장 2',
    );
    const levels = screen.getByRole('tablist', { name: words.levelTabsLabel });
    await act(async () => {
      fireEvent.mouseDown(within(levels).getByRole('tab', { name: 'Low' }));
      fireEvent.click(within(levels).getByRole('tab', { name: 'Low' }));
    });
    expect(rowsOf().map((row) => row.getAttribute('data-item'))).toEqual([
      '0',
      '2',
    ]);
  });

  it('등급 고르기: 고르면 PUT 하나(본문 원문 — marks 그대로 + 고침 전부), 같은 등급을 고르면 PUT 0', async () => {
    const marks = [
      { itemIndex: 1, decision: 'adopted' as const, excludeReason: null },
    ];
    const { store, bodies } = editStore(reviewOf('in_review', marks));
    await renderReview(store);
    expect(within(detail()).getByText('등급')).toBeTruthy();
    expect(levelButton().getAttribute('data-level-pick')).toBe('high');
    await pickLevel('High');
    expect(bodies).toEqual([]);
    await pickLevel('Mid');
    expect(bodies).toEqual([
      {
        marks,
        edits: [
          {
            itemIndex: 0,
            level: 'Mid',
            reasonBullets: null,
            fixParagraph: null,
          },
        ],
      },
    ]);
    // 저장 뒤: 보이는 등급 Mid, 「고침」, AI 원래 판단(등급) 접기 — 고친 사람·시각
    expect(levelButton().getAttribute('data-level-pick')).toBe('mid');
    const original = detail().querySelector('[data-ai-original="level"]')!;
    expect(original.querySelector('summary')!.textContent).toBe(
      'AI 원래 판단 보기 · 고친 사람 가상 담당 · 10-22 14:28',
    );
    expect(original.hasAttribute('open')).toBe(false);
    expect(
      original.querySelector('[data-level]')!.getAttribute('data-level'),
    ).toBe('high');
    expect(rowsOf()[0]!.querySelector('[data-edited]')).not.toBeNull();
  });

  it('판정 사유가 「- 」로 시작하는 AI 항목이면 [고치기]를 열었다 그대로 떠나도 저장하지 않는다(글 칸에 그대로, 밴드 GP1 검증 R2)', async () => {
    const { store, bodies } = editStore(reviewOf('pending'));
    const dashed = resultJson();
    dashed.items[0]!.reasonBullets = ['- 지어낸 항목', '둘째'];
    store.getResult = vi.fn(async () => dashed) as never;
    await renderReview(store);
    await act(async () => {
      fireEvent.click(editButton('reasonBullets'));
    });
    const box = within(field('reasonBullets')).getByRole('textbox', {
      name: words.reasonHeading,
    }) as HTMLTextAreaElement;
    expect(box.value).toBe('- 지어낸 항목\n둘째');
    await act(async () => {
      fireEvent.blur(box);
    });
    await act(async () => {});
    expect(bodies).toEqual([]);
    expect(within(field('reasonBullets')).queryByRole('textbox')).toBeNull();
    expect(
      [
        ...field('reasonBullets').querySelector('ul')!.querySelectorAll('li'),
      ].map((li) => li.textContent),
    ).toEqual(['- 지어낸 항목', '둘째']);
  });

  it('AI 값에 앞뒤 공백·줄바꿈·빈 항목이 있어도 [고치기]를 열었다 그대로 떠나면 저장하지 않는다(사유·수정 방향, sid:MARC-ISSUE-282)', async () => {
    const { store, bodies } = editStore(reviewOf('pending'));
    const messy = resultJson();
    messy.items[0]!.reasonBullets = [
      '  지어낸 사유 하나 ',
      '',
      '   ',
      '- 지어낸 사유 둘\n',
    ];
    messy.items[0]!.fixParagraph = '\n  지어낸 수정 방향.  \n';
    store.getResult = vi.fn(async () => messy) as never;
    await renderReview(store);
    for (const column of ['reasonBullets', 'fixParagraph'] as const) {
      await act(async () => {
        fireEvent.click(editButton(column));
      });
      const box = within(field(column)).getByRole('textbox', {
        name:
          column === 'reasonBullets' ? words.reasonHeading : words.fixHeading,
      });
      await act(async () => {
        fireEvent.blur(box);
      });
      await act(async () => {});
      expect(within(field(column)).queryByRole('textbox')).toBeNull();
    }
    expect(bodies).toEqual([]);
  });

  it('판정 사유 [고치기] → 「고치는 중 · 칸을 벗어나면 저장돼요」 글 칸 → 칸을 벗어나면 PUT 하나(줄 = 항목, 「- 」·빈 줄 뗌) → 닫히고 「고침」', async () => {
    const { store, bodies } = editStore(reviewOf('pending'));
    await renderReview(store);
    await act(async () => {
      fireEvent.click(editButton('reasonBullets'));
    });
    const box = within(field('reasonBullets')).getByRole('textbox', {
      name: words.reasonHeading,
    }) as HTMLTextAreaElement;
    // 칸에는 목록 표지 없이 항목 글만, 커서는 끝(sid:MARC-ISSUE-315)
    expect(box.value).toBe('사유');
    expect(box.selectionStart).toBe('사유'.length);
    expect(field('reasonBullets').textContent).toContain(
      '고치는 중 · 칸을 벗어나면 저장돼요',
    );
    await act(async () => {
      fireEvent.change(box, {
        target: { value: '- 새 사유 하나\n\n  새 사유 둘  ' },
      });
    });
    expect(bodies).toEqual([]);
    await act(async () => {
      fireEvent.blur(box);
    });
    await act(async () => {});
    expect(bodies).toEqual([
      {
        marks: [],
        edits: [
          {
            itemIndex: 0,
            level: null,
            reasonBullets: ['새 사유 하나', '새 사유 둘'],
            fixParagraph: null,
          },
        ],
      },
    ]);
    expect(within(field('reasonBullets')).queryByRole('textbox')).toBeNull();
    // 보이는 목록(첫 ul — AI 원래 판단 접기 안의 목록은 그 뒤)
    expect(
      [
        ...field('reasonBullets').querySelector('ul')!.querySelectorAll('li'),
      ].map((li) => li.textContent),
    ).toEqual(['새 사유 하나', '새 사유 둘']);
    expect(
      field('reasonBullets').querySelector(
        '[data-ai-original="reasonBullets"] summary',
      )!.textContent,
    ).toBe('AI 원래 판단 보기 · 고친 사람 가상 담당 · 10-22 14:28');
    expect(
      field('reasonBullets').querySelector('[data-edited]')!.textContent,
    ).toBe('고침');
    // 고침만 있어도 pending → in_review(서버 규칙)
    expect(screen.getByTestId('review-state').getAttribute('data-state')).toBe(
      'in_review',
    );
  });

  it('수정 방향: 글을 안 바꾸고 칸을 벗어나면 PUT 0·닫힘, 바꾸면 PUT 하나(서버가 앞뒤 공백을 지움)', async () => {
    const { store, bodies } = editStore(reviewOf('in_review'));
    await renderReview(store);
    await act(async () => {
      fireEvent.click(editButton('fixParagraph'));
    });
    let box = within(field('fixParagraph')).getByRole('textbox', {
      name: words.fixHeading,
    });
    await act(async () => {
      fireEvent.blur(box);
    });
    expect(bodies).toEqual([]);
    expect(within(field('fixParagraph')).queryByRole('textbox')).toBeNull();
    await act(async () => {
      fireEvent.click(editButton('fixParagraph'));
    });
    box = within(field('fixParagraph')).getByRole('textbox', {
      name: words.fixHeading,
    });
    await act(async () => {
      fireEvent.change(box, { target: { value: '  고친 수정 방향 ' } });
      fireEvent.blur(box);
    });
    await act(async () => {});
    expect(bodies.map((body) => body.edits)).toEqual([
      [
        {
          itemIndex: 0,
          level: null,
          reasonBullets: null,
          fixParagraph: '  고친 수정 방향 ',
        },
      ],
    ]);
    expect(field('fixParagraph').textContent).toContain('고친 수정 방향');
  });

  it('저장이 안 되면(400 — 빈 사유) 칸을 연 채 글을 남기고 오류 줄', async () => {
    const { store, bodies } = editStore(reviewOf('in_review'));
    await renderReview(store);
    await act(async () => {
      fireEvent.click(editButton('reasonBullets'));
    });
    const box = within(field('reasonBullets')).getByRole('textbox', {
      name: words.reasonHeading,
    });
    await act(async () => {
      fireEvent.change(box, { target: { value: '-   \n\n' } });
      fireEvent.blur(box);
    });
    await act(async () => {});
    expect(bodies).toHaveLength(1);
    const still = within(field('reasonBullets')).getByRole(
      'textbox',
    ) as HTMLTextAreaElement;
    expect(still.value).toBe('-   \n\n');
    expect(screen.getByTestId('save-error').textContent).toBe(
      words.saveRejected,
    );
  });

  it('저장 중에는 등급 고르기가 꺼진다 — 눌러도 메뉴가 안 열리고 요청 0', async () => {
    const put = deferredCalls<unknown>();
    const { store, bodies } = editStore(reviewOf('in_review'), {
      put: put.fn,
    });
    await renderReview(store);
    await act(async () => {
      fireEvent.click(choice(GW_TEXT.review.adopted));
    });
    expect(bodies).toHaveLength(1);
    expect(levelButton().hasAttribute('disabled')).toBe(true);
    await act(async () => {
      fireEvent.keyDown(levelButton(), { key: 'Enter' });
      fireEvent.pointerDown(levelButton());
      fireEvent.click(levelButton());
    });
    expect(screen.queryByRole('menuitemradio')).toBeNull();
    expect(bodies).toHaveLength(1);
  });

  it('칸마다 고친 사람·시각, 「AI 원래 판단 보기」 세 칸 각각(접힘, 펼치면 AI 값)', async () => {
    const { store } = editStore({
      ...reviewOf('in_review'),
      edits: [
        {
          itemIndex: 0,
          level: levelLow.level,
          reasonBullets: {
            value: ['고친 사유'],
            editedAt: '2026-10-16T09:05:00+09:00',
            editedBy: PERSON_B,
          },
          fixParagraph: {
            value: '고친 방향',
            editedAt: '2026-10-17T18:40:00+09:00',
            editedBy: PERSON_A,
          },
        },
      ],
    });
    await renderReview(store);
    const originals = [
      ...detail().querySelectorAll('details[data-ai-original]'),
    ];
    expect(
      originals.map((d) => [
        d.getAttribute('data-ai-original'),
        d.querySelector('summary')!.textContent,
        d.hasAttribute('open'),
      ]),
    ).toEqual([
      [
        'level',
        'AI 원래 판단 보기 · 고친 사람 가상 고친이 A · 10-15 14:28',
        false,
      ],
      [
        'reasonBullets',
        'AI 원래 판단 보기 · 고친 사람 가상 고친이 B · 10-16 09:05',
        false,
      ],
      [
        'fixParagraph',
        'AI 원래 판단 보기 · 고친 사람 가상 고친이 A · 10-17 18:40',
        false,
      ],
    ]);
    expect(originals[1]!.textContent).toContain('사유');
    expect(originals[2]!.textContent).toContain('방향');
    expect(field('fixParagraph').querySelector('p')!.textContent).toBe(
      '고친 방향',
    );
    // 안내(GW-05_r2 :103)
    expect(within(detail()).getByTestId('review-row').textContent).toContain(
      '제외하면 사유를 적어야 해요 · 등급·판정 사유·수정 방향은 고친 값으로 엑셀에 담기고, AI 원래 판단도 함께 남아요',
    );
  });

  it('05a 제외 사유 모달의 등급은 보이는 등급', async () => {
    const { store } = editStore({
      ...reviewOf('in_review'),
      edits: [levelLow],
    });
    await renderReview(store);
    await act(async () => {
      fireEvent.click(choice(GW_TEXT.review.excluded));
    });
    expect(screen.getByRole('dialog').textContent).toContain(
      words.quoteMeta(['CEO'], 2, 'Low'),
    );
  });

  it('05c(확정): 등급 고르기·[고치기] 없음, 「고침」·잠김 글·AI 원래 판단 접기는 남음, 「고친 문장」 토막 없음', async () => {
    const { store, bodies } = editStore({
      ...reviewOf('confirmed'),
      marks: [0, 1, 2].map((itemIndex) => ({
        itemIndex,
        decision: 'adopted' as const,
        excludeReason: null,
      })),
      edits: [
        {
          ...levelLow,
          fixParagraph: {
            value: '고친 방향',
            editedAt: '2026-10-17T18:40:00+09:00',
            editedBy: PERSON_A,
          },
        },
      ],
    });
    await renderReview(store);
    expect(
      within(detail()).queryByRole('button', { name: '등급 고르기' }),
    ).toBeNull();
    expect(
      within(detail()).queryAllByRole('button', { name: '고치기' }),
    ).toEqual([]);
    expect(detail().querySelectorAll('[data-edited]')).toHaveLength(2);
    expect(field('fixParagraph').textContent).toContain(
      '확정해서 잠김 · AI 원래 판단은 엑셀에 함께 담겨요',
    );
    expect(field('reasonBullets').textContent).not.toContain('확정해서 잠김');
    expect(
      [...detail().querySelectorAll('details[data-ai-original]')].map((d) =>
        d.getAttribute('data-ai-original'),
      ),
    ).toEqual(['level', 'fixParagraph']);
    expect(screen.getByTestId('review-tally').textContent).toBe(
      '채택 3 · 제외 0 · 미검토 0',
    );
    expect(bodies).toEqual([]);
  });

  it('읽기만(canWrite 거짓)이면 등급 고르기·[고치기] 없음 — 「고침」·접기만', async () => {
    const { store } = editStore({
      ...reviewOf('in_review'),
      edits: [levelLow],
    });
    await act(async () => {
      render(
        <ReviewScreen
          store={store}
          openPdf={fakeOpenPdf}
          runId="run-1"
          onBack={() => {}}
          onList={() => {}}
          canWrite={false}
        />,
      );
    });
    await act(async () => {});
    await act(async () => {});
    expect(
      within(detail()).queryByRole('button', { name: '등급 고르기' }),
    ).toBeNull();
    expect(
      within(detail()).queryAllByRole('button', { name: '고치기' }),
    ).toEqual([]);
    expect(detail().querySelector('[data-ai-original="level"]')).not.toBeNull();
  });

  // 밴드 GR1(sid:MARC-ISSUE-281 1·3 — 디자인 e9 답): 저장 경합
  describe('저장 경합(밴드 GR1)', () => {
    const tallyText = () => screen.getByTestId('review-tally').textContent;
    const confirmHeader = () =>
      within(
        screen.getByRole('heading', { level: 2 }).closest('header') ??
          document.body,
      ).getAllByRole('button', { name: words.confirm })[0]!;
    async function openFix(text: string) {
      await act(async () => {
        fireEvent.click(editButton('fixParagraph'));
      });
      const box = within(field('fixParagraph')).getByRole('textbox', {
        name: words.fixHeading,
      });
      await act(async () => {
        fireEvent.change(box, { target: { value: text } });
      });
      return box;
    }

    it('고친 칸의 blur 저장이 도는 동안 [채택]·[제외]·머리 [확정]이 꺼지고 목록 머리 끝이 「저장하고 있어요」, 끝나면 「자동 저장됨」', async () => {
      const put = deferredCalls<unknown>();
      const { store } = editStore(reviewOf('in_review'), { put: put.fn });
      await renderReview(store);
      const box = await openFix('가상으로 고친 수정 방향');
      await act(async () => {
        fireEvent.blur(box);
      });
      expect(tallyText()).toContain('저장하고 있어요');
      expect(tallyText()).not.toContain('자동 저장됨');
      for (const name of [GW_TEXT.review.adopted, GW_TEXT.review.excluded])
        expect(choice(name).getAttribute('aria-disabled')).toBe('true');
      expect(confirmHeader().hasAttribute('disabled')).toBe(true);
      await act(async () => {
        put.calls[0]!.resolve({
          ...reviewOf('in_review'),
          edits: [
            {
              itemIndex: 0,
              level: null,
              reasonBullets: null,
              fixParagraph: {
                value: '가상으로 고친 수정 방향',
                editedAt: SAVED_AT,
                editedBy: ME,
              },
            },
          ],
        });
      });
      await act(async () => {});
      expect(tallyText()).not.toContain('저장하고 있어요');
      expect(tallyText()).toContain('자동 저장됨');
      expect(confirmHeader().hasAttribute('disabled')).toBe(false);
    });

    it('blur 저장과 같은 틱에 들어간 [채택](끌 수 없는 갈래)은 보내지 않고 「저장 중이에요」 알림(role="status")이 잠깐 보인다', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      try {
        const put = deferredCalls<unknown>();
        const { store, bodies } = editStore(reviewOf('in_review'), {
          put: put.fn,
        });
        await renderReview(store);
        const box = await openFix('가상으로 고친 수정 방향');
        const adopt = choice(GW_TEXT.review.adopted);
        // 누름의 mousedown 이 칸을 벗어나게 하고(blur 저장), 화면이 다시 그려지기 전에 click 이 닿는다
        await act(async () => {
          fireEvent.blur(box);
          fireEvent.click(adopt);
        });
        expect(bodies).toHaveLength(1);
        const notice = screen.getByTestId('save-busy');
        expect(notice.getAttribute('role')).toBe('status');
        expect(notice.textContent).toBe(words.saveBusy);
        await act(async () => {
          vi.advanceTimersByTime(3000);
        });
        expect(screen.queryByTestId('save-busy')).toBeNull();
      } finally {
        vi.useRealTimers();
      }
    });

    it('고치던 중 다른 문장을 고르고 그 blur 저장이 안 되면 그 문장으로 돌아와 쓰던 글이 연 칸에 남는다', async () => {
      const put = deferredCalls<unknown>();
      const { store } = editStore(reviewOf('in_review'), { put: put.fn });
      await renderReview(store);
      expect(detail().getAttribute('data-item')).toBe('0');
      const box = await openFix('가상으로 고친 수정 방향 — 잃으면 안 됨');
      // 다른 줄을 누르면 mousedown 이 먼저 초점을 그 줄로 옮긴다(칸의 blur 저장) — 그 뒤 click
      await act(async () => {
        rowsOf()[1]!.focus();
      });
      expect(document.activeElement).not.toBe(box);
      await clickRow(1);
      expect(detail().getAttribute('data-item')).toBe('1');
      await act(async () => {
        put.calls[0]!.reject(new StoreError('rejected', '가상 거절'));
      });
      await act(async () => {});
      expect(put.fn).toHaveBeenCalledTimes(1);
      expect(detail().getAttribute('data-item')).toBe('0');
      const kept = within(field('fixParagraph')).getByRole(
        'textbox',
      ) as HTMLTextAreaElement;
      expect(kept.value).toBe('가상으로 고친 수정 방향 — 잃으면 안 됨');
      expect(screen.getByTestId('save-error').textContent).toBe(
        words.saveRejected,
      );
    });
  });
});

describe('쪽 칸의 같은 쪽 문장 상자와 역 포커싱(밴드 GP2, sid:MARC-ISSUE-341)', () => {
  /** 2쪽에 문장 셋(High 넓음 · Mid · Low 좁음, Mid 와 Low 는 겹침) + 3쪽 위치 없는 문장 하나. */
  function samePageResult() {
    const base = resultJson();
    const at = (boxes: [number, number, number, number][]) => ({
      page: 2,
      boxes,
    });
    const items = [
      item(2, ['CEO'], 'High', at([[60, 100, 500, 130]]), [6]),
      item(2, ['CEO'], 'Mid', at([[60, 300, 400, 330]]), [6]),
      item(2, ['CEO'], 'Low', at([[100, 305, 200, 325]]), [6]),
      item(3, ['회사'], 'Mid', null, []),
    ].map((one, index) => ({
      ...one,
      sentence: `지어낸 같은 쪽 문장 ${index}`,
    }));
    return {
      ...base,
      items,
      candidateStats: { ...base.candidateStats, raw: 4, kept: 4 },
      counts: { total: 4, byLevel: { High: 1, Mid: 2, Low: 1 }, byPart: {} },
    };
  }
  const boxes = () => screen.queryAllByTestId('page-box');

  it('고른 문장 말고 같은 쪽 문장 둘이 등급 색 1px 테두리 단추(채움 없음, 이름 = 쪽·등급·문장 앞), 작은 상자가 위, 고른 상자는 그 위', async () => {
    const { store } = reviewStore({ result: samePageResult() });
    await renderReview(store);
    expect(screen.getByTestId('highlight').getAttribute('data-level')).toBe(
      'High',
    );
    expect(boxes().map((box) => box.getAttribute('data-item'))).toEqual([
      '1',
      '2',
    ]);
    const [mid, low] = boxes() as [HTMLElement, HTMLElement];
    expect(mid.tagName).toBe('BUTTON');
    expect(mid.className).toContain('border-support-yellow-dark');
    expect(mid.className).toContain('bg-transparent');
    expect(mid.className).toContain('hover:border-2');
    expect(mid.className).not.toContain('bg-support');
    expect(low.className).toContain('border-text-tertiary');
    expect(mid.getAttribute('aria-label')).toBe(
      words.sentenceBox(2, 'Mid', '지어낸 같은 쪽 문장 1'),
    );
    // 상자 = 바깥 상자 + 사방 4(고른 상자 frame 과 같은 자리)
    expect([mid.style.left, mid.style.top, mid.style.width]).toEqual([
      '56px',
      '296px',
      '348px',
    ]);
    // 작은(Low) 상자가 큰(Mid) 상자 위, 고른 상자의 칠 칸(highlight-fill)은 맨 위 — 차례는 칠 칸이 진다(밴드 GP4: 틀 highlight 는 쌓임 맥락을 열지 않는다)
    expect(Number(low.style.zIndex)).toBeGreaterThan(Number(mid.style.zIndex));
    expect(
      Number(screen.getByTestId('highlight-fill').style.zIndex),
    ).toBeGreaterThan(Number(low.style.zIndex));
    expect(screen.getByTestId('highlight').style.zIndex).toBe('');
    expect(screen.getByTestId('highlight-fill').className).toContain(
      'mix-blend-multiply',
    );
  });

  it('상자를 누르면 그 문장을 고르고(목록 줄 aria-current·상세) 목록이 그 줄로 scrollIntoView(가운데), 고른 상자를 다시 누르면 아무 일 없음', async () => {
    // jsdom 에는 scrollIntoView 가 없다 — 이 시험 동안만 심어 부름을 적는다
    const scrolled: { item: string | null; arg: unknown }[] = [];
    const proto = HTMLElement.prototype as { scrollIntoView?: unknown };
    const before = proto.scrollIntoView;
    proto.scrollIntoView = function (this: HTMLElement, arg?: unknown) {
      scrolled.push({ item: this.getAttribute('data-item'), arg });
    };
    try {
      const { store } = reviewStore({ result: samePageResult() });
      await renderReview(store);
      await act(async () => {
        fireEvent.click(boxes()[1]!);
      });
      await act(async () => {});
      expect(rowsOf()[2]!.getAttribute('aria-current')).toBe('true');
      expect(detail().getAttribute('data-item')).toBe('2');
      expect(screen.getByTestId('highlight').getAttribute('data-level')).toBe(
        'Low',
      );
      expect(scrolled).toEqual([{ item: '2', arg: { block: 'center' } }]);
      // 이제 0번(High)이 옅은 상자, 2번은 고른 상자 단추
      expect(boxes().map((box) => box.getAttribute('data-item'))).toEqual([
        '0',
        '1',
      ]);
      await act(async () => {
        fireEvent.click(screen.getByTestId('page-box-current'));
      });
      await act(async () => {});
      expect(detail().getAttribute('data-item')).toBe('2');
      expect(scrolled).toHaveLength(1);
    } finally {
      proto.scrollIntoView = before;
    }
  });

  it('키보드: 상자 단추에 초점을 두고 Enter 로 고른다(단추 — 공용 Enter·Space)', async () => {
    const { store } = reviewStore({ result: samePageResult() });
    await renderReview(store);
    const mid = screen.getByRole('button', {
      name: words.sentenceBox(2, 'Mid', '지어낸 같은 쪽 문장 1'),
    });
    await act(async () => {
      mid.focus();
    });
    expect(document.activeElement).toBe(mid);
    // jsdom 은 단추의 Enter 를 click 으로 바꾸지 않는다 — 단추 요소이면 브라우저가 바꾼다(e2e 가 잰다). 여기서는 click 으로
    await act(async () => {
      fireEvent.click(mid);
    });
    await act(async () => {});
    expect(detail().getAttribute('data-item')).toBe('1');
  });

  it('목록 필터를 따른다: High 탭이면 다른 등급 상자 0, 위치 없는 문장·다른 쪽 문장은 상자 없음', async () => {
    const { store } = reviewStore({ result: samePageResult() });
    await renderReview(store);
    expect(boxes()).toHaveLength(2);
    const levels = screen.getByRole('tablist', { name: words.levelTabsLabel });
    await act(async () => {
      const tab = within(levels).getByRole('tab', {
        name: new RegExp(`^${words.levelTabs.High}`),
      });
      fireEvent.mouseDown(tab);
      fireEvent.click(tab);
    });
    await act(async () => {});
    expect(rowsOf()).toHaveLength(1);
    expect(boxes()).toHaveLength(0);
    expect(screen.getByTestId('highlight')).toBeTruthy();
  });
});

describe('쪽 그림 배율을 쪽 칸 폭에 맞춤(밴드 GFS1, sid:MARC-ISSUE-449)', () => {
  /** 쪽마다 폭(pt)이 다른 가짜 PDF: renderPage 계약대로 캔버스 CSS 폭 = 쪽 폭 × 배율. */
  const sizedOpenPdf: OpenPdf = async () =>
    ({
      renderPage: (pageNumber, canvas, scale) => {
        canvas.style.width = `${(pageNumber === 2 ? 842 : 595) * scale}px`;
        return { done: Promise.resolve(), cancel() {} };
      },
      close() {},
    }) satisfies PdfHandle;
  /** 부르면 크기 바뀜을 알리는 ResizeObserver(jsdom 에는 배치가 없어 손으로 알린다). */
  const callbacks = new Set<() => void>();
  class RecordingObserver {
    constructor(private readonly callback: () => void) {}
    observe() {
      callbacks.add(this.callback);
    }
    unobserve() {}
    disconnect() {
      callbacks.delete(this.callback);
    }
  }
  const resize = async (scrollerWidth: number) => {
    Object.defineProperty(screen.getByTestId('page-scroll'), 'clientWidth', {
      configurable: true,
      value: scrollerWidth,
    });
    await act(async () => {
      for (const callback of [...callbacks]) callback();
    });
    await act(async () => {});
  };
  const px = (value: string) => parseFloat(value);
  const canvasWidth = () =>
    px(screen.getByTestId('review-page').querySelector('canvas')!.style.width);

  /** 2쪽에 고른 문장(High)과 다른 문장(Mid, 바깥 상자 [60, 300, 400, 330]) — 다른 문장 상자의 배율도 잰다(검증 권고 R1). */
  function twoOnPage2() {
    const base = resultJson();
    const items = [
      ...base.items,
      item(2, ['CEO'], 'Mid', { page: 2, boxes: [[60, 300, 400, 330]] }, [6]),
    ];
    return {
      ...base,
      items,
      candidateStats: { ...base.candidateStats, raw: 4, kept: 4 },
      counts: { total: 4, byLevel: { High: 1, Mid: 2, Low: 1 }, byPart: {} },
    };
  }

  async function renderSized() {
    const saved = globalThis.ResizeObserver;
    vi.stubGlobal('ResizeObserver', RecordingObserver);
    const { store } = reviewStore({ result: twoOnPage2() });
    await act(async () => {
      render(
        <ReviewScreen
          store={store}
          openPdf={sizedOpenPdf}
          runId="run-1"
          onBack={vi.fn()}
          onList={vi.fn()}
        />,
      );
    });
    await act(async () => {});
    await act(async () => {});
    return () => {
      vi.stubGlobal('ResizeObserver', saved);
      callbacks.clear();
    };
  }

  it('좁은 칸(600) · 넓은 쪽(842pt) → 배율 0.71: 쪽 그림과 고른 상자·칠 칸이 같은 배율, 쪽 그림은 칸 안', async () => {
    const restore = await renderSized();
    try {
      // 재기 전(칸 폭 모름)은 1
      expect(canvasWidth()).toBe(842);
      await resize(600);
      expect(canvasWidth()).toBeCloseTo(842 * 0.71, 5);
      expect(canvasWidth()).toBeLessThanOrEqual(600);
      // 바깥 상자 [60, 100, 500, 130] × 0.71
      const highlight = screen.getByTestId('highlight');
      expect(px(highlight.style.left)).toBeCloseTo(60 * 0.71, 5);
      expect(px(highlight.style.top)).toBeCloseTo(100 * 0.71, 5);
      expect(px(highlight.style.width)).toBeCloseTo(440 * 0.71, 5);
      expect(px(highlight.style.height)).toBeCloseTo(30 * 0.71, 5);
      const fill = screen.getByTestId('highlight-fill');
      expect(px(fill.style.left)).toBeCloseTo(-4 * 0.71, 5);
      const current = screen.getByTestId('page-box-current');
      expect(px(current.style.width)).toBeCloseTo(448 * 0.71, 5);
      // 다른 문장 상자(바깥 상자 폭 340 + 사방 4)도 같은 배율
      const other = screen.getByTestId('page-box');
      expect(px(other.style.width)).toBeCloseTo((340 + 8) * 0.71, 5);
      expect(px(other.style.left)).toBeCloseTo((60 - 4) * 0.71, 5);
    } finally {
      restore();
    }
  });

  it('넓은 칸(1000) → 1 그대로(키우지 않음)', async () => {
    const restore = await renderSized();
    try {
      await resize(1000);
      expect(canvasWidth()).toBe(842);
      expect(screen.getByTestId('highlight').style.width).toBe('440px');
    } finally {
      restore();
    }
  });

  it('쪽을 넘겨 쪽 폭이 바뀌면(842 → 595pt) 다시 잰다: 칸 600 에서 0.71 → 1', async () => {
    const restore = await renderSized();
    try {
      await resize(600);
      expect(canvasWidth()).toBeCloseTo(842 * 0.71, 5);
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: words.nextPage }));
      });
      await act(async () => {});
      // 3쪽(595pt)을 0.71 로 그린 뒤 크기 바뀜 → 쪽 폭 595 → 배율 1
      expect(canvasWidth()).toBeCloseTo(595 * 0.71, 5);
      await resize(600);
      expect(canvasWidth()).toBe(595);
      // 다시 2쪽 → 842 를 1 로 그린 뒤 다시 0.71
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: words.prevPage }));
      });
      await act(async () => {});
      await resize(600);
      expect(canvasWidth()).toBeCloseTo(842 * 0.71, 5);
    } finally {
      restore();
    }
  });
});
