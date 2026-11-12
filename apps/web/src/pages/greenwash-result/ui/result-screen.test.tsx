// @vitest-environment jsdom
// 밴드 FW2 ③: GW-04 결과 요약. 통계 수 = 문장 수, 실패한 쪽 안내(있을 때만), 「추가」 배지(기본 목록과 겹친 줄에는 없음),
// 파트별 표·겹침 안내, 위험 유형(Low 제외), 머리 [내려받기] → 받기 모달(밴드 GDL1 — 옛 [엑셀 내보내기]), 확정이면 [확정] 숨김·[결과 보기], dry-run, 읽기 갈래.
// 글자는 문구 표(GW_TEXT) 값으로 단언한다.
// 밴드 LE1 ②: 불러오기 꼴(스켈레톤 300ms, 실패 꼴 + [다시 시도]·[목록으로], 없음 꼴 + [목록으로] 하나), 기본 단어를 못 읽으면 「추가」 배지 0.
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../../../entities/greenwash/api/index.ts';
import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import {
  deferredCalls,
  fakeStore,
} from '../../../entities/greenwash/api/mock/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import { useReview } from '../../../entities/greenwash/hooks/index.ts';
import type {
  CheckRowsSource,
  GreenwashReview,
  Level,
} from '../../../entities/greenwash/model/index.ts';
import { ResultScreen } from './ResultScreen.tsx';

afterEach(cleanup);
// 엑셀 시험이 바꾸는 전역을 시험마다 되돌린다(밴드 GW2R ④ — 검증 권고 R7)
const { createObjectURL, revokeObjectURL } = URL;
afterEach(() => {
  URL.createObjectURL = createObjectURL;
  URL.revokeObjectURL = revokeObjectURL;
});

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

const words = GW_TEXT.result;
const dl = GW_TEXT.downloads;

/** 머리 [내려받기]를 눌러 받기 모달을 열고 엑셀 줄 단추를 돌려준다(밴드 GDL1). */
function openDownloads() {
  fireEvent.click(screen.getByTestId('gw-downloads'));
  return screen.getByTestId('gw-download-dialog-file-excel');
}

/** 내려받은 파일 이름을 모은다(saveBlob 의 a.click). 되돌리기는 restore(). */
function catchSaves() {
  const saved: string[] = [];
  URL.createObjectURL = vi.fn(() => 'blob:지어낸');
  URL.revokeObjectURL = vi.fn();
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, 'click')
    .mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
  return { saved, restore: () => click.mockRestore() };
}

const item = (page: number, parts: string[], level: Level, tags: string[]) => ({
  page,
  parts,
  sentence: `문장 ${page}`,
  level,
  riskTags: level === 'Low' ? ['선언적 문장'] : tags,
  confirmedInEvidence: [],
  missingFields: [],
  reasonBullets: ['사유'],
  fixParagraph: '방향',
  evidencePages: [],
  evidenceInternal: '',
  position: null,
  exampleSentence: null,
});

function resultJson(extra: Record<string, unknown> = {}) {
  const items = [
    item(2, ['CEO'], 'High', ['미래 약속', '절대 표현']),
    item(4, ['회사', '기후'], 'Mid', ['미래 약속']),
    item(5, ['기후'], 'Low', []),
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
      { name: '회사', pages: [3, 4] },
      { name: '기후', pages: [4, 5, 6] },
    ],
    pages: [2, 3, 4, 5, 6],
    extraTerms: ['초록 물결', '탄소 중립'],
    items,
    candidateStats: {
      raw: 3,
      hardDropped: 0,
      nonEnvDropped: 0,
      promoDropped: 0,
      tableDropped: 0,
      kept: 3,
      failedPages: [
        { page: 6, error: 'x' },
        { page: 3, error: 'y' },
      ],
    },
    counts: {
      total: 3,
      byLevel: { High: 1, Mid: 1, Low: 1 },
      byPart: {},
    },
    wordCounts: {
      total: [
        { term: '친환경', count: 4 },
        { term: '초록 물결', count: 2 },
        { term: '탄소중립', count: 1 },
      ],
      pages: [
        {
          page: 2,
          counts: [
            { term: '친환경', count: 3 },
            { term: '초록 물결', count: 2 },
          ],
        },
        { page: 5, counts: [{ term: '탄소중립', count: 1 }] },
      ],
    },
    dryRun: null,
    report: { file: 'greenwash-report.xlsx' },
    ...extra,
  };
}

const review = (
  state: GreenwashReview['state'],
  marks = 0,
): GreenwashReview => ({
  schemaVersion: 'greenwash.review@3',
  evidence: [],
  rejudges: [],
  runId: 1,
  state,
  confirmedAt: state === 'confirmed' ? '2026-10-16T10:00:00+09:00' : null,
  confirmedBy: state === 'confirmed' ? { id: 1, name: '가상 사람' } : null,
  marks: Array.from({ length: marks }, (_, i) => ({
    itemIndex: i,
    decision: 'adopted' as const,
    excludeReason: null,
  })),
  edits: [],
});

function resultStore(
  overrides: Partial<GreenwashStore> = {},
  json: unknown = resultJson(),
  rev: GreenwashReview = review('in_review', 1),
): GreenwashStore {
  return fakeStore({
    listDefaultTerms: vi.fn(async () => ['친환경', '탄소중립']),
    listCheckRows: vi.fn(async (): Promise<CheckRowsSource> => ({
      currentUserId: 'me',
      companyName: '회사',
      documents: [
        {
          documentId: 'd2',
          fileName: '목-가상.pdf',
          reportYear: 2026,
          previousDocumentId: 'd1',
          pageCount: 30,
          uploadedAt: '2026-10-01T09:00:00+09:00',
          uploadedBy: { userId: 'me', name: '나' },
        },
      ],
      runs: [
        {
          runId: 'run-0',
          documentId: 'd2',
          createdAt: '2026-10-01T09:00:00+09:00',
          progress: {
            state: 'failed',
            stage: 'judge',
            judge: { done: 0, total: 5 },
          },
          levelCounts: null,
          review: null,
        },
        {
          runId: 'run-1',
          documentId: 'd2',
          createdAt: '2026-10-02T05:20:00Z',
          progress: {
            state: 'done',
            stage: 'summarize',
            judge: { done: 5, total: 5 },
          },
          levelCounts: { High: 1, Mid: 1, Low: 1 },
          review: null,
        },
      ],
    })),
    getResult: vi.fn(async () => json),
    getReview: vi.fn(async () => rev),
    ...overrides,
  });
}

async function renderResult(store = resultStore()) {
  const onReview = vi.fn();
  const onConfirm = vi.fn();
  render(
    <ResultScreen
      store={store}
      runId="run-1"
      onBack={() => {}}
      onReview={onReview}
      onConfirm={onConfirm}
    />,
  );
  await screen.findByText(
    words.meta({
      at: '2026-10-02 14:20',
      ordinal: 2,
      pageCount: 30,
      checked: 5,
      reviewed: 1,
      total: 3,
    }),
  );
  return { onReview, onConfirm };
}

describe('GW-04 결과 요약', () => {
  it('제목 줄: 파일명·검토 상태, meta(한국 시각·2회차·쪽·검토 n/전체). 수정본 배지·「추가 단어 n개」는 없다(v115 GW-04_r2 — 밴드 GW2R ①)', async () => {
    await renderResult();
    expect(screen.getByText('목-가상.pdf')).toBeTruthy();
    expect(screen.queryByTestId('revision-badge')).toBeNull();
    expect(document.body.textContent).not.toContain('수정본');
    expect(document.body.textContent).not.toContain('추가 단어');
    expect(screen.getByTestId('review-state').getAttribute('data-state')).toBe(
      'in_review',
    );
  });

  it('검토 n 은 결과 문장과 이은 표시만 센다(reviewTally — GW-05 와 같은 셈): 문장 밖을 가리키는 표시는 빼고 「검토 1/3」', async () => {
    const outside: GreenwashReview = {
      ...review('in_review', 1),
      marks: [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
        { itemIndex: 9, decision: 'adopted', excludeReason: null },
      ],
    };
    await renderResult(resultStore({}, resultJson(), outside));
    expect(document.body.textContent).toContain('검토 1/3');
    expect(document.body.textContent).not.toContain('검토 2/3');
    // 제목 줄 배지는 n 없이 「검토 중」. n 은 meta 의 「검토 1/3」에만(디자인 대조 C6)
    expect(
      document.querySelector('[data-testid="review-state"] [data-status]')
        ?.textContent,
    ).toBe(GW_TEXT.runStatus.reviewing);
  });

  it('통계 넷: 지적된 문장 = 문장 수, 등급마다 수', async () => {
    await renderResult();
    const value = (id: string) =>
      within(screen.getByTestId(id)).getByTestId('stat-value').textContent;
    expect(
      ['stat-total', 'stat-high', 'stat-mid', 'stat-low'].map(value),
    ).toEqual(['3', '1', '1', '1']);
  });

  it('안내: 이미지(늘), 확정 전(확정 전만), 실패한 쪽(오름차순)', async () => {
    await renderResult();
    expect(screen.getByTestId('image-notice').textContent).toBe(
      words.imageNotice,
    );
    expect(screen.getByTestId('unconfirmed-notice').textContent).toBe(
      words.unconfirmedNotice,
    );
    // v115 GW-04_r2: 앞 버전 비교 끝 문장을 뺀 글 그대로(밴드 GW2R ①)
    expect(words.unconfirmedNotice).toBe(
      '아직 확정 전이에요. 지금 내려받는 엑셀에는 「확정 전 결과」라고 표시돼요. 확정하면 채택한 문장만 담긴 확정본이 나가요.',
    );
    // 인식 실패 페이지 줄(v115 GW-04_r2 · Q7 — 밴드 GW2R ②, 낱말은 sid:MARC-ENT-603): 파랑 줄 「인식 실패 페이지 2개」 + 회색 칩(오름차순) + 「이 페이지의 문장은 결과에 없어요」(D9, 마침표 없음)
    const missed = screen.getByTestId('failed-pages');
    expect(missed.textContent).toBe(
      '인식 실패 페이지 2개3페이지6페이지이 페이지의 문장은 결과에 없어요',
    );
    expect(
      [...missed.querySelectorAll('[data-page]')].map(
        (chip) => chip.textContent,
      ),
    ).toEqual(['3페이지', '6페이지']);
    expect(missed.className).toContain('bg-support-blue-subtle');
    expect(missed.textContent).not.toContain('다시 점검');
    expect(missed.querySelector('button')).toBeNull();
  });

  it('인식 실패 페이지가 하나면 「인식 실패 페이지 1개」 + 칩 하나(밴드 GW2R ② — 옛 「7쪽은 분석하지 못했어요」 글을 갈음, 낱말 sid:MARC-ENT-603)', async () => {
    const json = resultJson();
    json.candidateStats.failedPages = [{ page: 7, error: 'x' }];
    await renderResult(resultStore({}, json));
    expect(screen.getByTestId('failed-pages').textContent).toBe(
      '인식 실패 페이지 1개7페이지이 페이지의 문장은 결과에 없어요',
    );
  });

  it('실패한 쪽이 없으면 그 안내가 없다', async () => {
    const json = resultJson();
    json.candidateStats.failedPages = [];
    await renderResult(resultStore({}, json));
    expect(screen.queryByTestId('failed-pages')).toBeNull();
  });

  it('파트별 표(이름은 결과 그대로, 쪽은 구간 압축)와 겹침 안내(합 4 > 전체 3)', async () => {
    await renderResult();
    const table = screen.getByRole('table', { name: words.partsTableLabel });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(
      rows.map((row) => within(row).getAllByRole('cell')[0]!.textContent),
    ).toEqual(['CEO', '회사', '기후']);
    expect(within(rows[2]!).getAllByRole('cell')[1]!.textContent).toBe('4~6');
    expect(screen.getByTestId('parts-note').textContent).toBe(
      words.partsNote(4, 3),
    );
  });

  it('위험 유형 카드가 없다(v115 GW-04_r2 — sid:MARC-ENT-366, 밴드 GW2R ①): 결과 문장에 riskTags 가 있어도', async () => {
    await renderResult();
    expect(screen.queryByTestId('risk-bars')).toBeNull();
    expect(document.body.textContent).not.toContain('위험 유형');
    expect(document.body.textContent).not.toContain('미래 약속');
  });

  it('단어 빈도: 「추가」는 추가 단어이고 기본 목록에 없는 줄만(탄소 중립 ↔ 탄소중립 줄에는 없음), 파트별 탭', async () => {
    await renderResult();
    const total = screen.getByTestId('terms-total');
    const extra = within(total)
      .getAllByRole('listitem')
      .map((li) => [
        li.getAttribute('data-term'),
        li.getAttribute('data-extra'),
      ]);
    expect(extra).toEqual([
      ['친환경', null],
      ['초록 물결', 'true'],
      ['탄소중립', null],
    ]);
    const tab = screen.getByRole('tab', { name: words.termsTabs.parts });
    await act(async () => {
      fireEvent.mouseDown(tab);
      fireEvent.click(tab);
    });
    const parts = screen
      .getByTestId('terms')
      .querySelectorAll('section[data-part]');
    expect([...parts].map((p) => p.getAttribute('data-part'))).toEqual([
      'CEO',
      '회사',
      '기후',
    ]);
    // 기후(4·5·6쪽): 5쪽의 탄소중립 1, 회사(3·4쪽): 단어 없음
    expect(parts[2]!.textContent).toContain('탄소중립');
    expect(parts[1]!.textContent).toContain(words.termsEmpty);
  });

  it('BMP 밖 글자 30자 단어(CJK 확장 B — UTF-16 60)가 든 결과도 열린다: 거울(zod 4 .max)이 코드 포인트로 센다(GWB1, sid:MARC-ISSUE-320)', async () => {
    const wide = Array.from({ length: 30 }, (_, i) =>
      String.fromCodePoint(0x20000 + i),
    ).join('');
    const base = resultJson();
    await renderResult(
      resultStore(
        {},
        resultJson({
          extraTerms: [wide],
          terms: ['친환경', '탄소중립', wide],
          wordCounts: {
            total: [...base.wordCounts.total, { term: wide, count: 1 }],
            pages: base.wordCounts.pages,
          },
        }),
      ),
    );
    const total = screen.getByTestId('terms-total');
    expect(
      within(total)
        .getAllByRole('listitem')
        .map((li) => li.getAttribute('data-term')),
    ).toContain(wide);
  });

  it('머리 [내려받기]는 켜져 있고(밴드 GDL1 — 옛 [엑셀 내보내기]를 갈음) 받기 모달의 「점검 결과 엑셀」 줄: 확정 전이면 getReport(run, false) 한 번 → 내려받기, 화면 이동 없음. [확정]·[검토 이어 하기]', async () => {
    const { saved, restore } = catchSaves();
    const getReport = vi.fn(async () => ({
      blob: new Blob(['지어낸']),
      fileName: '지어낸 보고서.xlsx',
    }));
    const { onReview, onConfirm } = await renderResult(
      resultStore({ getReport }),
    );
    const opener = screen.getByTestId('gw-downloads');
    expect(opener.getAttribute('aria-disabled')).toBeNull();
    expect((opener as HTMLButtonElement).disabled).toBe(false);
    expect(opener.querySelector('svg[aria-hidden]')).not.toBeNull();
    expect(opener.textContent).toBe(dl.title);
    expect(opener.className).toContain('rounded-full');
    // 열기 전에는 요청 0
    expect(getReport).not.toHaveBeenCalled();
    const excel = openDownloads();
    const dialog = screen.getByTestId('gw-download-dialog');
    expect(within(dialog).getByRole('heading').textContent).toBe(dl.title);
    // 묶음 이름 · 설명 한 줄 · 단추 안 이름(확정 전) · 각주 없음
    const row = dialog.querySelector('[data-file="excel"]')!;
    expect(row.textContent).toContain(dl.excel);
    expect(row.textContent).not.toContain(dl.excelConfirmed);
    expect(row.textContent).toContain(dl.excelNote);
    expect(excel.textContent).toBe(dl.excel);
    expect(dialog.querySelectorAll('[data-file]').length).toBe(1);
    expect(excel.getAttribute('aria-disabled')).toBeNull();
    expect(screen.queryByTestId('gw-download-dialog-help-excel')).toBeNull();
    await act(async () => {
      fireEvent.click(excel);
    });
    expect(getReport.mock.calls).toEqual([['run-1', false]]);
    expect(saved).toEqual(['지어낸 보고서.xlsx']);
    restore();
    expect(onReview).not.toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
    // [닫기] → 모달 내림, 초점은 머리 [내려받기]로
    fireEvent.click(within(dialog).getByRole('button', { name: dl.close }));
    await waitFor(() =>
      expect(screen.queryByTestId('gw-download-dialog')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(opener));
    fireEvent.click(screen.getByRole('button', { name: words.confirm }));
    fireEvent.click(screen.getByRole('button', { name: words.continueReview }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onReview).toHaveBeenCalledTimes(1);
  });

  it('받기 모달 엑셀 줄이 실패하면 그 줄 아래 role="alert" excelFailed, 다시 누르면 지우고 다시 받는다(밴드 GDL1 — 옛 단추 옆 alert)', async () => {
    const { saved, restore } = catchSaves();
    const getReport = vi
      .fn<GreenwashStore['getReport']>()
      .mockRejectedValueOnce(new StoreError('unreachable', '실패'))
      .mockResolvedValueOnce({
        blob: new Blob(['지어낸']),
        fileName: '지어낸 보고서.xlsx',
      });
    await renderResult(resultStore({ getReport }));
    const excel = openDownloads();
    await act(async () => {
      fireEvent.click(excel);
    });
    const problem = screen.getByTestId('gw-download-dialog-problem-excel');
    expect(problem.getAttribute('role')).toBe('alert');
    expect(problem.textContent).toBe(words.excelFailed);
    expect(saved).toEqual([]);
    // 단추는 다시 켜져 있다
    expect(excel.getAttribute('aria-disabled')).toBeNull();
    await act(async () => {
      fireEvent.click(excel);
    });
    expect(screen.queryByTestId('gw-download-dialog-problem-excel')).toBeNull();
    expect(getReport).toHaveBeenCalledTimes(2);
    expect(saved).toEqual(['지어낸 보고서.xlsx']);
    restore();
  });

  it('확정된 실행: [확정] 숨김, [결과 보기], 확정 전 안내 없음', async () => {
    const getReport = vi.fn(async () => ({
      blob: new Blob(['지어낸']),
      fileName: '지어낸 확정본.xlsx',
    }));
    const store = resultStore(
      { getReport },
      resultJson(),
      review('confirmed', 3),
    );
    render(
      <ResultScreen
        store={store}
        runId="run-1"
        onBack={() => {}}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    expect(
      await screen.findByRole('button', { name: words.viewResult }),
    ).toBeTruthy();
    expect(screen.queryByRole('button', { name: words.confirm })).toBeNull();
    expect(screen.queryByTestId('unconfirmed-notice')).toBeNull();
    // 받기 모달(밴드 GDL1): 이름은 확정본, 받는 파일도 확정본(getReport(run, true))
    const { saved, restore } = catchSaves();
    const excel = openDownloads();
    const row = screen
      .getByTestId('gw-download-dialog')
      .querySelector('[data-file="excel"]')!;
    expect(row.textContent).toContain(dl.excelConfirmed);
    expect(row.textContent).toContain(dl.excelNote);
    expect(excel.textContent).toBe(dl.excelConfirmed);
    await act(async () => {
      fireEvent.click(excel);
    });
    expect(getReport.mock.calls).toEqual([['run-1', true]]);
    expect(saved).toEqual(['지어낸 확정본.xlsx']);
    restore();
  });

  it('dry-run: 안내 하나와 단어 빈도만(통계·파트 표 없음, [확정] 없음)', async () => {
    const json = resultJson({
      items: [],
      candidateStats: null,
      counts: null,
      report: null,
      dryRun: {
        pagesChecked: 1,
        pagesWithText: 1,
        pagesTruncated: 0,
        chunks: 1,
        embeddingIndex: tally,
        ruleCandidates: 0,
        lower: {
          chat: tally,
          chatByKind: kinds,
          embeddingQueries: tally,
          judged: 0,
        },
        upper: {
          chat: tally,
          chatByKind: kinds,
          embeddingQueries: tally,
          outputTokensMax: 0,
          evidenceChars: 0,
          evidenceCapReached: false,
        },
        perPage: [],
      },
    });
    render(
      <ResultScreen
        store={resultStore({}, json)}
        runId="run-1"
        onBack={() => {}}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    expect((await screen.findByTestId('dry-run')).textContent).toBe(
      words.dryRun,
    );
    expect(screen.getByTestId('terms-total')).toBeTruthy();
    expect(screen.queryByTestId('stat-total')).toBeNull();
    expect(screen.queryByRole('button', { name: words.confirm })).toBeNull();
    // dry-run 은 엑셀이 없다(밴드 GDL1 — 옛 꺼진 [엑셀 내보내기]를 갈음): 머리 [내려받기]는 켜고, 모달의 엑셀 줄이 꺼진 꼴 +
    // 이름 옆 (?) 「없는 까닭: 시험 실행이라 …」, 눌러도 요청 0 · 실패 글 0
    const opener = screen.getByTestId('gw-downloads');
    expect(opener.getAttribute('aria-disabled')).toBeNull();
    expect((opener as HTMLButtonElement).disabled).toBe(false);
    const excel = openDownloads();
    expect(excel.getAttribute('aria-disabled')).toBe('true');
    expect(excel.className).toContain('opacity-40');
    expect(excel.className).toContain('cursor-not-allowed');
    expect(excel.textContent).toBe(dl.excel);
    const help = screen.getByTestId('gw-download-dialog-help-excel');
    expect(help.getAttribute('aria-label')).toBe(
      `${dl.missingLabel}: ${dl.excelMissing}`,
    );
    fireEvent.click(excel);
    await act(async () => {});
    expect(screen.queryByTestId('gw-download-dialog-problem-excel')).toBeNull();
  });

  it('읽기 갈래: 없음 → 회색 「찾을 수 없어요」 + [목록으로] 하나, 꼴 오류 → 「불러오지 못했어요」 + [다시 시도]·[목록으로](role="alert")', async () => {
    const onBack = vi.fn();
    render(
      <ResultScreen
        store={resultStore({
          getResult: vi.fn(async () => {
            throw new StoreError('not_found', '없음');
          }),
        })}
        runId="run-1"
        onBack={onBack}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    const missing = await screen.findByRole('alert');
    expect(missing.getAttribute('data-kind')).toBe('missing');
    expect(missing.querySelector('[data-tone]')?.textContent).toBe(
      words.missing,
    );
    expect(
      missing.querySelector('[data-tone]')?.getAttribute('data-tone'),
    ).toBe('default');
    // [목록으로]는 상자의 것 하나(제목 줄 것은 뺀다), [다시 시도] 없음
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      GW_TEXT.load.toList,
    ]);
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.toList }));
    expect(onBack).toHaveBeenCalledTimes(1);
    expect(
      screen.queryByRole('list', { name: GW_TEXT.stepFlow.label }),
    ).toBeNull();
    expect(document.querySelector('[aria-busy]')).toBeNull();
    cleanup();
    render(
      <ResultScreen
        store={resultStore({}, { nope: true })}
        runId="run-1"
        onBack={() => {}}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    const invalid = await screen.findByRole('alert');
    expect(invalid.getAttribute('data-kind')).toBe('failed');
    expect(invalid.querySelector('[data-tone]')?.textContent).toBe(
      words.invalid,
    );
    expect(words.invalid).toBe(words.failed);
    expect(document.querySelector('[aria-busy]')).toBeNull();
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      GW_TEXT.load.retry,
      GW_TEXT.load.toList,
    ]);
    expect(
      screen.getByRole('list', { name: GW_TEXT.stepFlow.label }),
    ).toBeTruthy();
    expect(
      screen.getByRole('heading', { level: 2, name: words.title }),
    ).toBeTruthy();
  });

  it('[다시 시도]: 꼴 오류(invalid)에서 누른 직후 실패 상자가 사라지고(두 번째 읽기를 미뤄 둠), 받으면 본문', async () => {
    const second = deferredCalls<unknown>();
    const getResult = vi
      .fn<GreenwashStore['getResult']>()
      .mockResolvedValueOnce({ nope: true } as never)
      .mockImplementation(second.fn as never);
    render(
      <ResultScreen
        store={resultStore({ getResult })}
        runId="run-1"
        onBack={() => {}}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    expect(getResult).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('alert')).toBeNull();
    // 다시 읽는 동안은 첫 불러오기와 같은 꼴 — 제목은 막대 자리(밴드 GL1)
    expect(
      screen
        .getByRole('heading', { level: 2, name: GW_TEXT.load.titlePending })
        .closest('[data-screen="result"]')
        ?.getAttribute('data-result-state'),
    ).toBe('loading');
    expect(screen.queryByText(words.title)).toBeNull();
    await act(async () => second.calls[0]!.resolve(resultJson()));
    expect(await screen.findByTestId('stat-total')).toBeTruthy();
  });

  it('LA1 ② 초점: 첫 실패에서는 body 그대로 → [다시 시도] → 또 실패면 새 [다시 시도] → [다시 시도] → 받으면 본문 제목 줄 h2', async () => {
    const reads = deferredCalls<unknown>();
    const view = render(
      <ResultScreen
        store={resultStore({ getResult: reads.fn as never })}
        runId="run-1"
        onBack={() => {}}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    await act(async () => reads.calls[0]!.reject(new Error('망')));
    expect(document.activeElement).toBe(document.body);
    const first = screen.getByRole('button', { name: GW_TEXT.load.retry });
    fireEvent.click(first);
    await act(async () => reads.calls[1]!.reject(new Error('또 망')));
    const second = screen.getByRole('button', { name: GW_TEXT.load.retry });
    expect(second).not.toBe(first);
    expect(document.activeElement).toBe(second);
    fireEvent.click(second);
    await act(async () => reads.calls[2]!.resolve(resultJson()));
    expect(await screen.findByTestId('stat-total')).toBeTruthy();
    expect(document.activeElement).toBe(
      view.container.querySelector('[data-screen="result"] h2'),
    );
  });

  it('LA1 ② 초점: [다시 시도] 뒤 없음(404)이면 상자의 첫 단추 [목록으로]', async () => {
    const reads = deferredCalls<unknown>();
    render(
      <ResultScreen
        store={resultStore({ getResult: reads.fn as never })}
        runId="run-1"
        onBack={() => {}}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    await act(async () => reads.calls[0]!.reject(new Error('망')));
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    await act(async () =>
      reads.calls[1]!.reject(new StoreError('not_found', '없음')),
    );
    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: GW_TEXT.load.toList }),
    );
  });

  it('「추가 배지는 …」 안내는 문서 전체에 추가 단어 줄이 있을 때만: 있으면 보이고, 추가로 센 줄이 0 이면 없다(C2)', async () => {
    await renderResult();
    expect(screen.getAllByTestId('extra-badge').length).toBeGreaterThan(0);
    expect(screen.getByTestId('extra-note').textContent).toBe(words.extraNote);
    cleanup();
    // 추가 단어가 모두 기본 목록에도 있으면 추가로 센 줄이 0 이다(배지 0)
    await renderResult(
      resultStore({
        listDefaultTerms: vi.fn(async () => [
          '친환경',
          '탄소중립',
          '초록 물결',
          '탄소 중립',
        ]),
      }),
    );
    expect(screen.queryAllByTestId('extra-badge')).toEqual([]);
    expect(screen.queryByTestId('extra-note')).toBeNull();
  });

  it('기본 단어를 읽지 못하면 「추가」 배지 0, 막대의 data-extra 도 없다, 안내 글 extraNote 도 없다(C2)', async () => {
    await renderResult(
      resultStore({
        listDefaultTerms: vi.fn(async () => {
          throw new Error('망');
        }),
      }),
    );
    const total = screen.getByTestId('terms-total');
    const rows = within(total).getAllByRole('listitem');
    expect(rows.map((li) => li.getAttribute('data-term'))).toEqual([
      '친환경',
      '초록 물결',
      '탄소중립',
    ]);
    expect(rows.map((li) => li.getAttribute('data-extra'))).toEqual([
      null,
      null,
      null,
    ]);
    expect(screen.queryAllByTestId('extra-badge')).toEqual([]);
    expect(screen.queryByTestId('extra-note')).toBeNull();
  });

  it('미룬 결과: 바깥 [data-screen] 은 0ms·299ms 에도 aria-busy(스켈레톤은 없음), 300ms 에는 스켈레톤(숨긴 글, 카드엔 aria-busy 없음). 틀(제목 줄 자리·[목록으로]·STEP 3)은 처음부터 — 제목·설명은 막대(「결과 요약」 글 0, 밴드 GL1). ready 뒤 [aria-busy] 0·파일 이름 제목', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    try {
      const pending = deferredCalls<unknown>();
      const view = render(
        <ResultScreen
          store={resultStore({ getResult: pending.fn as never })}
          runId="run-1"
          onBack={() => {}}
          onReview={() => {}}
          onConfirm={() => {}}
        />,
      );
      expect(
        screen.getByRole('heading', {
          level: 2,
          name: GW_TEXT.load.titlePending,
        }),
      ).toBeTruthy();
      expect(screen.queryByText(words.title)).toBeNull();
      expect(screen.getByTestId('title-pending')).toBeTruthy();
      expect(screen.getByTestId('description-pending')).toBeTruthy();
      expect(screen.getByRole('button', { name: words.back })).toBeTruthy();
      expect(
        screen.getByRole('list', { name: GW_TEXT.stepFlow.label }),
      ).toBeTruthy();
      const outer = () => view.container.querySelector('[data-screen]')!;
      expect(outer().getAttribute('aria-busy')).toBe('true');
      expect(screen.queryByTestId('result-skeleton')).toBeNull();
      act(() => vi.advanceTimersByTime(299));
      expect(outer().getAttribute('aria-busy')).toBe('true');
      expect(screen.queryByTestId('result-skeleton')).toBeNull();
      act(() => vi.advanceTimersByTime(1));
      const skeleton = screen.getByTestId('result-skeleton');
      expect(skeleton.getAttribute('aria-busy')).toBeNull();
      expect(outer().getAttribute('aria-busy')).toBe('true');
      expect(skeleton.textContent).toBe(words.loading);
      // 화면 꼴 스켈레톤(밴드 GL2): 낭독 글은 role="status" 하나 · 공용 카드 0
      expect(skeleton.getAttribute('role')).toBe('status');
      expect(skeleton.getAttribute('aria-label')).toBe(words.loading);
      expect(screen.getAllByRole('status')).toHaveLength(1);
      expect(screen.queryByTestId('load-skeleton')).toBeNull();
      await act(async () => pending.calls[0]!.resolve(resultJson()));
      expect(screen.queryByTestId('result-skeleton')).toBeNull();
      expect(screen.getByTestId('stat-total')).toBeTruthy();
      expect(view.container.querySelector('[aria-busy]')).toBeNull();
      expect(screen.queryByTestId('title-pending')).toBeNull();
      expect(screen.queryByTestId('description-pending')).toBeNull();
      expect(screen.getByRole('heading', { level: 2 }).textContent).toContain(
        '목-가상.pdf',
      );
    } finally {
      vi.useRealTimers();
    }
  });
});

const tally = {
  requests: 0,
  inputChars: 0,
  inputTokens: { status: 'measured', encoding: 'x', value: 0 },
};
const kinds = { detect: tally, eval: tally, lowOnly: tally, repair: tally };

describe('GW-04 자동 저장 표시(밴드 GW2R ② Q6·D2)', () => {
  afterEach(() => vi.useRealTimers());

  it('같은 탭(같은 저장소)에서 검토 PUT 이 받아들여진 뒤 GW-04 를 열면 meta 끝에 「 · 자동 저장됨 14:31」, 저장 전·다른 저장소면 없음', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-10-19T05:31:40Z'));
    const store = resultStore({
      putReview: vi.fn(async (_runId, update) => ({
        ...review('in_review', 1),
        marks: update.marks,
      })),
    });
    // GW-05 자리: 같은 저장소로 표시 하나를 저장한다
    const hook = renderHook(() => useReview(store, 'run-1'));
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    expect(hook.result.current.savedAt).toBeNull();
    await act(async () => {
      await hook.result.current.mark({ itemIndex: 1, decision: 'adopted' });
    });
    expect(hook.result.current.savedAt).toBe('2026-10-19T05:31:40.000Z');
    hook.unmount();
    render(
      <ResultScreen
        store={store}
        runId="run-1"
        onBack={() => {}}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    await screen.findByText(/ · 자동 저장됨 14:31$/);
    cleanup();
    // 다른 저장소(다른 탭 꼴)에는 없다
    await renderResult();
    expect(document.body.textContent).not.toContain('자동 저장됨');
  });
});

describe('GW-04 효력 등급(밴드 G1b-3 ③ — 디자인 80 회신 Q8)', () => {
  const statValues = () =>
    ['stat-total', 'stat-high', 'stat-mid', 'stat-low'].map(
      (id) =>
        within(screen.getByTestId(id)).getByTestId('stat-value').textContent,
    );
  /** 파트 표의 등급 칸(파트 차례 CEO · 회사 · 기후). */
  const partColumn = (risk: 'high' | 'mid' | 'low') =>
    screen.getAllByTestId(`part-${risk}`).map((cell) => cell.textContent);

  it('검토를 읽는 중이면 AI 셈, 읽으면 고친 등급으로 — 등급 합과 파트 × 등급 둘 다', async () => {
    const reads = deferredCalls<unknown>();
    const store = resultStore({ getReview: reads.fn });
    render(
      <ResultScreen
        store={store}
        runId="run-1"
        onBack={() => {}}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    await screen.findByTestId('stat-high');
    // 읽는 중: AI 셈(문장 0 High[CEO] · 1 Mid[회사·기후] · 2 Low[기후])
    expect(statValues()).toEqual(['3', '1', '1', '1']);
    expect(partColumn('high')).toEqual(['1', '0', '0']);
    expect(partColumn('low')).toEqual(['0', '0', '1']);
    const edited: GreenwashReview = {
      ...review('in_review', 1),
      edits: [
        {
          itemIndex: 0,
          level: {
            value: 'Low',
            editedAt: '2026-10-22T09:00:00+09:00',
            editedBy: { id: 1, name: '가상 고친이' },
          },
          reasonBullets: null,
          fixParagraph: null,
        },
        {
          itemIndex: 1,
          level: {
            value: 'High',
            editedAt: '2026-10-22T09:00:00+09:00',
            editedBy: { id: 1, name: '가상 고친이' },
          },
          reasonBullets: null,
          fixParagraph: null,
        },
      ],
    };
    await act(async () => {
      reads.calls[0]!.resolve(edited);
    });
    // 읽음: 0 High → Low, 1 Mid → High(두 파트 다)
    await waitFor(() => expect(statValues()).toEqual(['3', '1', '0', '2']));
    expect(partColumn('high')).toEqual(['0', '1', '1']);
    expect(partColumn('mid')).toEqual(['0', '0', '0']);
    expect(partColumn('low')).toEqual(['1', '0', '1']);
  });

  it('GRJ1 ④ M2: 검토의 rejudges 가 요약에 닿는다 — done 재판단은 기준 판단 등급으로, 리스크 아님은 세 칸 밖(등급 합·파트 × 등급)', async () => {
    const reads = deferredCalls<unknown>();
    const store = resultStore({ getReview: reads.fn });
    render(
      <ResultScreen
        store={store}
        runId="run-1"
        onBack={() => {}}
        onReview={() => {}}
        onConfirm={() => {}}
      />,
    );
    await screen.findByTestId('stat-high');
    expect(statValues()).toEqual(['3', '1', '1', '1']);
    const judged = {
      runId: 9001,
      judgedAt: '2026-11-09T14:32:00+09:00',
      judgedBy: { id: 1, name: '가상 판단이' },
      riskTags: [],
      confirmedInEvidence: ['지어낸 다시 본 사실'],
      missingFields: [],
      reasonBullets: ['지어낸 다시 본 사유.'],
      evidencePages: [],
      added: [{ text: '지어낸 조각', page: 2 }],
    };
    const rejudged: GreenwashReview = {
      ...review('in_review', 1),
      rejudges: [
        {
          itemIndex: 1,
          status: 'done',
          count: 1,
          current: {
            ...judged,
            outcome: 'judged',
            level: 'High',
            fixParagraph: '지어낸 방향.',
          },
        },
        {
          itemIndex: 2,
          status: 'done',
          count: 1,
          current: {
            ...judged,
            runId: 9002,
            outcome: 'nonrisk',
            level: null,
            fixParagraph: '',
          },
        },
      ],
    };
    await act(async () => {
      reads.calls[0]!.resolve(rejudged);
    });
    // 1 Mid[회사·기후] → High(재판단), 2 Low[기후] → 리스크 아님(세지 않음). 지적된 문장 수는 결과 문장 수 그대로
    await waitFor(() => expect(statValues()).toEqual(['3', '2', '0', '0']));
    expect(partColumn('high')).toEqual(['1', '1', '1']);
    expect(partColumn('mid')).toEqual(['0', '0', '0']);
    expect(partColumn('low')).toEqual(['0', '0', '0']);
  });
});
