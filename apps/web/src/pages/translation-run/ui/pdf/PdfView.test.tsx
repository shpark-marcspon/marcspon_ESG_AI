// @vitest-environment jsdom
// PDF 보기 화면(밴드 TRW6 ③ S3 — 가짜 서버 + 가짜 openPdf): 상자 수 · 누름 → 짝 · 빈 곳 → 차례 · 표식(focus)·띠 ·
// 이슈·용어 붙이기 표지 · 페이지만 · A·B 탭 하나씩([둘 다] 0) · layout 404/409 · 원본 PDF missing/failed · [← 결과 요약].
// 값은 전부 지어낸 것이다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  fakeDocument,
  fakeLayout,
  fakeOptions,
  fakeRun,
  fakeTranslationServer,
  refusal,
  serverStoreOf,
} from '../../../../entities/translation/api/testing.ts';
import { TR_TEXT } from '../../../../entities/translation/config/text.ts';
import type {
  OpenPdf,
  PdfHandle,
} from '../../../../widgets/doc-viewer/index.ts';
import type { PdfOpenFocus } from '../../model/index.ts';
import { PdfView } from './PdfView.tsx';

const words = TR_TEXT.pdfView;
const WAIT = { timeout: 3000 };
const PDF_BYTES = new Uint8Array([37, 80, 68, 70, 45, 49, 46, 55]);

const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };
beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:fake-pdf');
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => {
  cleanup();
  URL.createObjectURL = original.create;
  URL.revokeObjectURL = original.revoke;
});

/** 가짜 PDF(그리기는 곧 끝남). 연 주소를 남긴다. */
function fakePdf() {
  const opened: string[] = [];
  const openPdf: OpenPdf = async (url) => {
    opened.push(url);
    return {
      renderPage: () => ({ done: Promise.resolve(), cancel() {} }),
      close() {},
    } satisfies PdfHandle;
  };
  return { opened, openPdf };
}

type Json = Record<string, unknown>;

/**
 * 쪽 12 하나의 layout(fakeLayout 꼴) — 결과(가짜 서버)의 이슈 구간 「Made-up text」가 BLOCK 1 둘째 번역에,
 * 용어 「지어낸용어」가 BLOCK 1 첫 원문에 있게 고친다. compare 면 B 문체를 더한다.
 */
function layoutOf({ compare = false }: { compare?: boolean } = {}): Json {
  const layout = fakeLayout(12) as Json & {
    units: { members: { source: string }[] }[];
    variants: Json[];
  };
  layout.units[0]!.members[0]!.source = '지어낸용어 대응 전략';
  const a = layout.variants[0]! as { units: Json[] };
  a.units[0] = {
    tag: 'BLOCK 1',
    page: 12,
    level: 'block',
    translations: ['Climate Strategy', 'Made-up text about cuts'],
  };
  if (compare)
    layout.variants.push({
      label: 'B',
      stage: 'translated',
      units: [
        {
          tag: 'BLOCK 1',
          page: 12,
          level: 'group',
          translations: ['B style merged'],
        },
        { tag: 'TABLE 1', page: 12, level: 'table', translations: ['B table'] },
        { tag: null, page: 12, level: 'source_only', translations: null },
      ],
      unplaced: [{ page: 12, text: 'Stray B' }],
    });
  return layout;
}

function serverOf(
  layout: Json | null = layoutOf(),
  { pdf = true }: { pdf?: boolean } = {},
) {
  const server = fakeTranslationServer({
    documents: [
      fakeDocument(12, {
        fileName: 'made_up.pdf',
        ...(pdf ? { pdf: PDF_BYTES } : {}),
      }),
    ],
    runs: [
      fakeRun(30, 12, fakeOptions('story', 12, 12, 'b-1'), {
        flowId: 'translation.pdf@158',
      }),
    ],
  });
  server.advance(30, {
    status: 'done',
    ...(layout === null ? {} : { layout }),
  });
  return server;
}

function draw(
  server: ReturnType<typeof serverOf>,
  focus: PdfOpenFocus | null = null,
  copy: (text: string) => Promise<void> = vi.fn(async () => {}),
) {
  const onBack = vi.fn();
  const pdf = fakePdf();
  render(
    <PdfView
      store={serverStoreOf(server)}
      runId="30"
      documentId="12"
      openPdf={pdf.openPdf}
      focus={focus}
      copy={copy}
      onBack={onBack}
    />,
  );
  return { onBack, opened: pdf.opened };
}

const boxes = () => [...document.querySelectorAll('[data-box]')];
const box = (id: string) =>
  document.querySelector(`[data-box="${id}"]`) as HTMLElement;
const pairs = () => screen.getByTestId('pdf-pairs');
/** 목록 꼴 line 탭(밴드 TRW8 ⑥) — radix 탭은 mouseDown 으로 고른다. */
const listTab = (n: 0 | 1) =>
  within(screen.getByTestId('pdf-list-tabs')).getAllByRole('tab')[n]!;
function openIssueTab() {
  fireEvent.mouseDown(listTab(1), { button: 0 });
}
/** 상세 「번역」 머리 줄 전환(밴드 TRW8 ④ 개정 — sid:MARC-ENT-502): 0 A · 1 B · 2 둘 다. 상세 꼴엔 맨 위 문체 탭이 없다. */
const styleSwitch = (n: 0 | 1 | 2) =>
  within(screen.getByTestId('pdf-style-switch')).getAllByRole('tab')[n]!;
function pickStyle(n: 0 | 1 | 2) {
  fireEvent.mouseDown(styleSwitch(n), { button: 0 });
}
/** 목록 꼴 맨 위 문체 탭 목록(없으면 null). */
const topStyleTabs = () =>
  within(pairs()).queryByRole('tablist', {
    name: TR_TEXT.run.styleTabsLabel,
  });

describe('PdfView (S3)', () => {
  it('쪽 그림 + 상자 수 = block member 둘 + 표 테두리 하나 + bbox 있는 칸 하나 + 꼬리말 하나 · 원본 PDF 주소로 연다', async () => {
    const { opened } = draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(opened).toEqual(['blob:fake-pdf']);
    expect(document.querySelector('canvas')).not.toBeNull();
    expect(boxes().map((each) => each.getAttribute('data-look'))).toEqual([
      'block',
      'block',
      'table_border',
      'cell',
      'source_only',
    ]);
    expect(screen.getByTestId('pdf-page-of').textContent).toBe(
      words.pageOf(12, 1),
    );
    // 쪽 목록: 「12페이지 번역 2곳 · 이슈 2」(이슈 하나 + 용어 하나).
    const line = document.querySelector('[data-page="12"]')!;
    expect(line.textContent).toContain(words.pageLine.places(12, 2));
    expect(line.textContent).toContain(words.pageLine.issues(2));
  });

  it('상자 누름 → 짝 칸 원문 → 번역 · 빈 곳 누름 → 그 쪽 짝 차례', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(within(pairs()).getByText(words.pair.listTitle(12, 4))).toBeTruthy();
    // 표는 짝 하나(밴드 TRW7 ③b-2, sid:MARC-ENT-488): 칸 상자 누름 → 표 짝 · 두 격자의 같은 칸.
    fireEvent.click(box('p12-t1:r0c0'));
    expect(screen.getByTestId('pdf-pair').getAttribute('data-kind')).toBe(
      'table',
    );
    const on = (testId: string) =>
      screen.getByTestId(testId).querySelector('td[data-on]')!.textContent;
    expect(on('pdf-pair-source-grid')).toBe('구분');
    expect(on('pdf-pair-translation-grid')).toBe('Category');
    expect(box('p12-t1:r0c0').getAttribute('data-selected')).toBe('true');
    // 꼬리말: 원문만 · 번역 칸 없음.
    fireEvent.click(box('p12-b9'));
    expect(screen.queryByTestId('pdf-pair-translation')).toBeNull();
    expect(screen.getByText(words.pair.sourceOnly)).toBeTruthy();
    fireEvent.click(screen.getByTestId('pdf-page'));
    expect(screen.queryByTestId('pdf-pair')).toBeNull();
    expect(within(pairs()).getByText(words.pair.listTitle(12, 4))).toBeTruthy();
  });

  it('붙이기: 이슈(번역에서)·용어(원문에서)가 맞은 상자에 「이슈 N」 · 짝 칸 목록', async () => {
    draw(serverOf());
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
      WAIT,
    );
    // 용어 「지어낸용어」는 첫 member 원문에.
    expect(box('p12-b1').getAttribute('data-issues')).toBe('1');
    expect(box('p12-t1#cell').getAttribute('data-issues')).toBeNull();
    expect(box('p12-b2').textContent).toContain(words.badge(1));
    fireEvent.click(box('p12-b2'));
    const list = screen.getByTestId('pdf-pair-issues');
    expect(list.textContent).toContain(words.issuesTitle(1));
    // TRW7 ①: 「고칠 부분 → 제안」 한 줄이 판 .tp-il 두 줄(고칠 부분 / 제안)로 바뀜.
    expect(within(list).getByTestId('pdf-issue-span').textContent).toBe(
      `${words.issueLine.span}Made-up text`,
    );
    expect(within(list).getByTestId('pdf-issue-suggestion').textContent).toBe(
      `${words.issueLine.suggestion}Invented text`,
    );
    fireEvent.click(box('p12-b1'));
    expect(screen.getByTestId('pdf-misses').textContent).toContain(
      '지어낸용어 → Made-up Term',
    );
  });

  it('못 찾은 이슈는 상자 표지 0 · 짝 칸 맨 위 「이 페이지 전체」 목록', async () => {
    const layout = layoutOf();
    const a = (layout.variants as { units: Json[] }[])[0]!;
    a.units[0] = { ...a.units[0]!, translations: ['Climate', 'Other words'] };
    draw(serverOf(layout));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(box('p12-b2').getAttribute('data-issues')).toBeNull();
    // 밴드 TRW8 ⑥: 「페이지 전체」 묶음은 [검수 이슈] 탭 안(맨 아래).
    openIssueTab();
    expect(screen.getByTestId('pdf-page-issues').textContent).toContain(
      words.pageIssuesTitle(1),
    );
  });

  it('focus: 그 쪽 · 그 짝을 고르고 띠 한 줄 · 다른 상자를 누르면 띠가 사라진다', async () => {
    draw(serverOf(), {
      page: 12,
      pair: 1,
      label: 'A',
      from: { where: '12페이지 둘째 문단', type: '어색한 표현' },
    });
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-selected')).toBe('true'),
      WAIT,
    );
    expect(screen.getByTestId('pdf-from-table').textContent).toBe(
      words.fromTable('12페이지 둘째 문단', '어색한 표현'),
    );
    fireEvent.click(box('p12-b1'));
    expect(screen.queryByTestId('pdf-from-table')).toBeNull();
  });

  it('견주기: 짝 칸 탭 [A][B] 하나씩([둘 다] 0) · B 로 바꾸면 B 의 level·번역·단계 · unplaced', async () => {
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    // 문체 탭 목록만(밴드 TRW8 ⑥ — 짝 칸에 목록 꼴 line 탭이 더 있다).
    const tabs = within(
      within(pairs()).getByRole('tablist', {
        name: TR_TEXT.run.styleTabsLabel,
      }),
    ).getAllByRole('tab');
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      words.styleOf('A'),
      words.styleOf('B'),
    ]);
    expect(screen.getByTestId('pdf-stage').textContent).toBe(
      words.stage.autofix,
    );
    expect(screen.queryByTestId('pdf-unplaced')).toBeNull();
    // Radix 탭은 mousedown 으로 바뀐다.
    fireEvent.mouseDown(tabs[1]!, { button: 0 });
    await waitFor(
      () =>
        expect(screen.getByTestId('pdf-stage').textContent).toBe(
          words.stage.translated,
        ),
      WAIT,
    );
    // B: BLOCK 1 은 묶음 하나, 표는 칸 없이 하나 → 상자 셋.
    expect(boxes().map((each) => each.getAttribute('data-look'))).toEqual([
      'group',
      'table',
      'source_only',
    ]);
    fireEvent.click(boxes()[0]!);
    expect(screen.getByTestId('pdf-pair-translation').textContent).toBe(
      'B style merged',
    );
    expect(screen.getByTestId('pdf-unplaced').textContent).toContain(
      words.unplaced(1),
    );
  });

  // 검증 B1: 표식의 문체로 연다 — B 탭 「자리」(B 의 짝 0 = 묶음)는 B 탭·B 의 묶음 상자.
  it('표식 label B → B 탭으로 열고 B 의 그 짝(묶음)을 고름', async () => {
    draw(serverOf(layoutOf({ compare: true })), {
      page: 12,
      pair: 0,
      label: 'B',
      from: { where: '12페이지 첫째 문단', type: '어색한 표현' },
    });
    await waitFor(
      () =>
        expect(screen.getByTestId('pdf-stage').textContent).toBe(
          words.stage.translated,
        ),
      WAIT,
    );
    await waitFor(() => expect(boxes()).toHaveLength(3), WAIT);
    expect(boxes()[0]!.getAttribute('data-look')).toBe('group');
    expect(boxes()[0]!.getAttribute('data-selected')).toBe('true');
    expect(screen.getByTestId('pdf-pair-translation').textContent).toBe(
      'B style merged',
    );
  });

  // 밴드 TRS6 커밋 ②: 묶음(group) 번역 한 덩이 안의 빈 줄이 화면에서 문단으로 보인다(번역 쪽만 whitespace-pre-line).
  it('묶음 번역의 문단 줄바꿈은 번역 쪽 <p> 에서 살아 있다 · 원문 쪽 class 는 그대로', async () => {
    const layout = layoutOf({ compare: true });
    const b = (layout.variants as { units: Json[] }[])[1]!;
    b.units[0] = { ...b.units[0]!, translations: ['가상 제목\n\n가상 본문'] };
    draw(serverOf(layout), {
      page: 12,
      pair: 0,
      label: 'B',
      from: { where: '12페이지 첫째 문단', type: '어색한 표현' },
    });
    await waitFor(() => expect(boxes()).toHaveLength(3), WAIT);
    const translated = screen.getByTestId('pdf-pair-translation');
    expect(translated.textContent).toBe('가상 제목\n\n가상 본문');
    expect(translated.className).toContain('whitespace-pre-line');
    for (const source of screen.getAllByTestId('pdf-pair-source'))
      expect(source.className).not.toContain('whitespace-pre-line');
  });

  // 밴드 TRW7 ③a W10: 요약 「확인할 곳」 칸에서 오면 쪽 목록이 「확인할 곳」 거르기로 열린다.
  it('표식 filter checks → 쪽 목록 [확인할 곳] 눌린 채로 · 없으면 [페이지 전체]', async () => {
    draw(serverOf(), {
      page: 12,
      pair: null,
      label: 'A',
      from: null,
      filter: 'checks',
    });
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    const pressed = () =>
      [...document.querySelectorAll('nav button[aria-pressed="true"]')].map(
        (b) => b.textContent,
      );
    expect(pressed()).toHaveLength(1);
    expect(pressed()[0]).toContain(words.filters.checks(0).split(' ')[0]!);
    cleanup();
    draw(serverOf(), { page: 12, pair: null, label: 'A', from: null });
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(pressed()[0]).toContain(words.filters.all(0).split(' ')[0]!);
  });

  it('표식 label 이 layout 문체에 없으면 첫 문체 · 고름 0(쪽은 그대로)', async () => {
    draw(serverOf(layoutOf({ compare: true })), {
      page: 12,
      pair: 0,
      label: 'single',
      from: null,
    });
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(screen.getByTestId('pdf-stage').textContent).toBe(
      words.stage.autofix,
    );
    expect(document.querySelector('[data-box][data-selected]')).toBeNull();
  });

  // 검증 R13 → 밴드 TRW8 ④: 항목을 고른 뒤 문체를 바꾸면 새 문체 쪽의 같은 unit 항목에 머문다(앞 문체의 짝 자리 번호를 그대로 쓰지 않음).
  it('항목을 고른 뒤 [B] 탭 → 같은 unit 항목(B 묶음)을 고른 채 · 쪽 위 그 상자 · 단계 줄 B', async () => {
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b2'));
    expect(screen.getByTestId('pdf-pair')).toBeTruthy();
    pickStyle(1);
    await waitFor(() => expect(boxes()).toHaveLength(3), WAIT);
    // B 의 BLOCK 1 은 묶음 — 같은 unit 의 항목(1 / 3).
    expect(screen.getByTestId('pdf-pair').getAttribute('data-kind')).toBe(
      'group',
    );
    expect(screen.getByTestId('pdf-pair-position').textContent).toBe(
      words.pair.position(1, 3),
    );
    expect(screen.getByTestId('pdf-pair-translation').textContent).toBe(
      'B style merged',
    );
    const on = [...document.querySelectorAll('[data-box][data-selected]')];
    expect(on.map((each) => each.getAttribute('data-box'))).toEqual([
      'p12-b1#group',
    ]);
    expect(screen.getByTestId('pdf-stage').getAttribute('data-stage')).toBe(
      'translated',
    );
    // [A] 로 돌아가면 묶음(member 없음) → 같은 unit 의 첫 항목.
    pickStyle(0);
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(screen.getByTestId('pdf-pair-position').textContent).toBe(
      words.pair.position(1, 4),
    );
    expect(box('p12-b1').getAttribute('data-selected')).toBe('true');
  });

  // 검증 R11: 그림뿐 쪽 — 쪽 띠 · 상자 0 · 목록 줄 「그림뿐인 페이지」.
  it('그림뿐 쪽(imageOnlyPages)으로 넘기면 쪽 띠 · 상자 0', async () => {
    const layout = layoutOf() as Json & {
      pages: Json[];
      skipped: { imageOnlyPages: number[] };
    };
    layout.pages.push({ page: 13, width: 595, height: 842, textLayer: 'none' });
    layout.skipped.imageOnlyPages = [13];
    draw(serverOf(layout));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(screen.queryByTestId('pdf-image-only')).toBeNull();
    const line = document.querySelector('nav [data-page="13"]') as HTMLElement;
    expect(line.textContent).toContain(words.pageLine.imageOnly(13));
    fireEvent.click(line);
    await waitFor(() => screen.getByTestId('pdf-image-only'), WAIT);
    expect(screen.getByTestId('pdf-image-only').textContent).toBe(
      words.imageOnly,
    );
    expect(boxes()).toHaveLength(0);
  });

  it('한 문체 실행은 탭 0', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    // 문체 탭 0(밴드 TRW8 ⑥ — 목록 꼴 line 탭 둘은 문체와 상관없이 있다).
    expect(
      within(pairs()).queryByRole('tablist', {
        name: TR_TEXT.run.styleTabsLabel,
      }),
    ).toBeNull();
    expect(within(pairs()).getAllByRole('tab')).toHaveLength(2);
  });

  it('layout 404 → 한 줄 + [← 결과 요약] · 상자 0', async () => {
    const { onBack } = draw(serverOf(null));
    await waitFor(() => screen.getByTestId('pdf-not-found'), WAIT);
    expect(screen.getByTestId('pdf-not-found').textContent).toBe(
      words.notFound,
    );
    expect(boxes()).toHaveLength(0);
    fireEvent.click(screen.getByTestId('pdf-back'));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('layout 409(끝나지 않음) → 진행 한 줄', async () => {
    const server = serverOf();
    server.override['GET /translation/runs/30/layout'] = () =>
      refusal(409, 'RUN_NOT_DONE');
    draw(server);
    await waitFor(() => screen.getByTestId('pdf-not-done'), WAIT);
    expect(screen.getByTestId('pdf-not-done').textContent).toBe(words.notDone);
  });

  it('원본 PDF 없음(409) → 뷰어 자리에만 한 줄, [다시 시도] 0 · 짝 목록은 그대로', async () => {
    draw(serverOf(layoutOf(), { pdf: false }));
    await waitFor(() => screen.getByTestId('pdf-file-failed'), WAIT);
    expect(screen.getByTestId('pdf-file-failed').textContent).toBe(
      words.pdfFailed,
    );
    expect(screen.queryByText(words.retry)).toBeNull();
    expect(within(pairs()).getByText(words.pair.listTitle(12, 4))).toBeTruthy();
  });

  it('원본 PDF 실패(500) → [다시 시도] → 다시 받으면 쪽 그림', async () => {
    const server = serverOf();
    server.override['GET /documents/12/file'] = () => refusal(500, 'INTERNAL');
    draw(server);
    await waitFor(() => screen.getByText(words.retry), WAIT);
    delete server.override['GET /documents/12/file'];
    await act(async () => {
      fireEvent.click(screen.getByText(words.retry));
    });
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
  });

  // TRW7 ① S1 — 판 v182 TR-P05 꼴(범례 · 쪽 머리 · 쪽 목록 묶음 · 밑줄 번호 · 이슈 줄 · 표 짝).
  describe('보기 꼴 (TRW7 ① S1)', () => {
    /** BLOCK 1 둘째 번역과 A 문체 단계를 바꾼 layout. */
    function layoutWith(translation: string, stage: 'autofix' | 'translated') {
      const layout = layoutOf();
      const a = (layout.variants as Json[])[0]! as {
        stage: string;
        units: Json[];
      };
      a.stage = stage;
      a.units[0] = {
        ...a.units[0]!,
        translations: ['Climate Strategy', translation],
      };
      return layout;
    }
    const marks = (testId: string) => [
      ...document.querySelectorAll(`[data-testid="${testId}"] mark`),
    ];

    it('범례: 판 종류 아홉이 늘 전부(그 쪽에 없는 종류도)', async () => {
      draw(serverOf());
      await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
      const legend = screen.getByTestId('pdf-legend');
      expect(legend.getAttribute('aria-label')).toBe(words.legend.label);
      expect(
        [...legend.querySelectorAll('li')].map((li) => li.textContent),
      ).toEqual([
        words.legend.block,
        words.legend.group,
        words.legend.cell,
        words.legend.table,
        words.legend.visual,
        words.legend.sourceOnly,
        words.legend.missing,
        `⚠${words.legend.check}`,
        `${words.legend.issueSample}${words.legend.issue}`,
      ]);
    });

    it('쪽 머리 「12페이지 [스토리]」 · 쪽 목록 묶음 머리 · 두 줄 줄', async () => {
      draw(serverOf());
      await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
      await waitFor(
        () =>
          expect(screen.getByTestId('pdf-page-title').textContent).toBe(
            `${words.pageTitle(12)}${TR_TEXT.parts.names.story}`,
          ),
        WAIT,
      );
      expect(screen.getByTestId('pdf-page-group').textContent).toBe(
        words.group(TR_TEXT.parts.names.story, 12, 12),
      );
      const line = document.querySelector('nav [data-page="12"]')!;
      expect(line.getAttribute('aria-current')).toBe('page');
      expect(line.children).toHaveLength(2);
      expect(line.children[0]!.textContent).toBe(words.pageLine.title(12));
    });

    it('고른 상자는 판 .bx-sel 꼴(파랑 굵은 선) · 안 고른 상자는 아님', async () => {
      draw(serverOf());
      await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
      fireEvent.click(box('p12-b2'));
      expect(box('p12-b2').getAttribute('data-selected')).toBe('true');
      expect(box('p12-b2').className).toContain('outline-blue-600');
      expect(box('p12-b1').className).not.toContain('outline-blue-600');
    });

    it('이슈 밑줄은 번역 글에(번호 1) · 용어 밑줄은 원문 글에 · 목록 줄 번호와 같다', async () => {
      draw(serverOf());
      await waitFor(
        () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
        WAIT,
      );
      fireEvent.click(box('p12-b2'));
      const issue = marks('pdf-pair-translation');
      expect(issue).toHaveLength(1);
      expect(issue[0]!.getAttribute('data-mark')).toBe('issue');
      expect(issue[0]!.getAttribute('data-n')).toBe('1');
      expect(issue[0]!.textContent).toBe('Made-up text');
      expect(marks('pdf-pair-source')).toHaveLength(0);
      // 번호는 ::after — 글은 그대로.
      expect(screen.getByTestId('pdf-pair-translation').textContent).toBe(
        'Made-up text about cuts',
      );
      const row = screen
        .getByTestId('pdf-pair-issues')
        .querySelector('[data-issue-line]')!;
      expect(row.getAttribute('data-issue-line')).toBe('1');
      // 심각도 배지(요약 표와 같은 RiskBadge).
      expect(row.querySelector('[data-level="low"]')).not.toBeNull();
      fireEvent.click(box('p12-b1'));
      const term = marks('pdf-pair-source');
      expect(term.map((each) => each.getAttribute('data-mark'))).toEqual([
        'term',
      ]);
      expect(term[0]!.textContent).toBe('지어낸용어');
      expect(
        screen
          .getByTestId('pdf-misses')
          .querySelector('[data-term-line]')!
          .getAttribute('data-term-line'),
      ).toBe(term[0]!.getAttribute('data-n'));
      expect(screen.getByTestId('pdf-misses').textContent).toContain(
        words.termLine.note,
      );
    });

    // 검증 B1: 같은 짝에 이슈 하나 + 용어 하나 — 이슈 1, 용어는 이어서 2(판 ①②), 밑줄 번호 == 목록 줄 번호.
    it('한 짝에 이슈·용어가 같이 붙으면 이슈 1 · 용어 2 — 밑줄 번호와 목록 줄 번호가 같다', async () => {
      const layout = layoutOf() as Json & {
        units: { members: { source: string }[] }[];
      };
      layout.units[0]!.members[0]!.source = '기후 대응 전략';
      layout.units[0]!.members[1]!.source = '지어낸용어 로 배출을 줄인다';
      draw(serverOf(layout));
      await waitFor(
        () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('2'),
        WAIT,
      );
      fireEvent.click(box('p12-b2'));
      const issue = marks('pdf-pair-translation');
      const term = marks('pdf-pair-source');
      expect(issue.map((m) => m.getAttribute('data-n'))).toEqual(['1']);
      expect(term.map((m) => m.getAttribute('data-mark'))).toEqual(['term']);
      expect(term.map((m) => m.getAttribute('data-n'))).toEqual(['2']);
      expect(
        screen
          .getByTestId('pdf-pair-issues')
          .querySelector('[data-issue-line]')!
          .getAttribute('data-issue-line'),
      ).toBe('1');
      expect(
        screen
          .getByTestId('pdf-misses')
          .querySelector('[data-term-line]')!
          .getAttribute('data-term-line'),
      ).toBe('2');
    });

    it('자동 수정 문체 + 제안 글이 번역에 있으면 제안 글에 밑줄 · 「자동 수정에서 고쳤어요」', async () => {
      draw(
        serverOf(layoutWith('Made-up text, now Invented text here', 'autofix')),
      );
      await waitFor(
        () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
        WAIT,
      );
      fireEvent.click(box('p12-b2'));
      expect(marks('pdf-pair-translation').map((m) => m.textContent)).toEqual([
        'Invented text',
      ]);
      expect(screen.getByTestId('pdf-issue-fixed').textContent).toBe(
        words.issueLine.fixed,
      );
    });

    it('자동 수정 전 문체(translated)면 같은 글이어도 고칠 부분에 밑줄 · 「고쳤어요」 0', async () => {
      draw(
        serverOf(
          layoutWith('Made-up text, now Invented text here', 'translated'),
        ),
      );
      await waitFor(
        () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
        WAIT,
      );
      fireEvent.click(box('p12-b2'));
      expect(marks('pdf-pair-translation').map((m) => m.textContent)).toEqual([
        'Made-up text',
      ]);
      expect(screen.queryByTestId('pdf-issue-fixed')).toBeNull();
    });

    it('자동 수정 문체라도 제안 글이 없으면 고칠 부분에 밑줄 · 「고쳤어요」 0', async () => {
      draw(serverOf());
      await waitFor(
        () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
        WAIT,
      );
      fireEvent.click(box('p12-b2'));
      expect(marks('pdf-pair-translation').map((m) => m.textContent)).toEqual([
        'Made-up text',
      ]);
      expect(screen.queryByTestId('pdf-issue-fixed')).toBeNull();
    });

    // 밴드 TRW7 ③b-2(sid:MARC-ENT-488): 칸을 맞춘 표는 pipe 글 대신 원문·번역 격자 둘(같은 행·열). pipe 표는 칸을 못 맞춘 표(table level) 글에만.
    // 검증 ③b-2 B1: 칸을 못 맞춘 표(level table)는 격자 0 — pipe 글은 표(행·열)로 · 「표 전체」 안내.
    it('표 수준(level table) 짝: pipe 원문·번역은 <table>(행·열) · 「표 전체」 안내 · 격자 0', async () => {
      const layout = layoutOf() as Json & {
        units: Json[];
        variants: (Json & { units: Json[] })[];
      };
      const table = layout.units.findIndex((unit) => unit.tag === 'TABLE 1');
      layout.variants[0]!.units[table] = {
        tag: 'TABLE 1',
        page: 12,
        level: 'table',
        translations: [
          '| Category | 2025 |\n| --- | --- |\n| Emissions | 1,200 |',
        ],
      };
      draw(serverOf(layout));
      await waitFor(() => expect(box('p12-t1#table')).not.toBeNull(), WAIT);
      expect(document.querySelector('[data-look="cell"]')).toBeNull();
      fireEvent.click(box('p12-t1#table'));
      for (const testId of [
        'pdf-pair-source-table',
        'pdf-pair-translation-table',
      ]) {
        const element = screen.getByTestId(testId);
        expect(element.tagName).toBe('TABLE');
        expect(element.querySelectorAll('thead th')).toHaveLength(2);
        expect(element.querySelectorAll('tbody tr')).toHaveLength(1);
      }
      expect(
        screen.getByTestId('pdf-pair-translation-table').textContent,
      ).toContain('Emissions');
      expect(screen.getByTestId('pdf-pair').textContent).toContain(
        words.pair.tableWhole,
      );
      expect(screen.queryByTestId('pdf-pair-source-grid')).toBeNull();
      expect(screen.queryByTestId('pdf-pair-translation-grid')).toBeNull();
    });

    it('표 짝 2×2: 칸 누름 → 두 격자에서 그 칸 하나만 강조(같은 행 다른 칸 0) · 표에 붙은 「이슈 N」은 테두리에만(칸 상자 0)', async () => {
      const layout = layoutOf() as Json & {
        units: (Json & { members: { source: string }[]; cells?: Json[] })[];
        variants: (Json & { units: Json[] })[];
      };
      // 용어 「지어낸용어」를 BLOCK 1 에서 빼고 표 칸 원문에 둔다 → 표 짝에 붙음.
      layout.units[0]!.members[0]!.source = '대응 전략';
      const table = layout.units.findIndex((unit) => unit.tag === 'TABLE 1');
      // 표 짝 원문 = 표 member 글(pipe) — 붙이기는 그 글에서 찾는다(규칙 그대로).
      layout.units[table]!.members[0]!.source =
        '| 구분 | 2025 |\n| --- | --- |\n| 지어낸용어 | 1,200 |';
      layout.units[table]!.cells = [
        [0, 0, '구분'],
        [0, 1, '2025'],
        [1, 0, '지어낸용어'],
        [1, 1, '1,200'],
      ].map(([row, col, source]) => ({
        row,
        col,
        id: `p12-t1:r${row}c${col}`,
        bbox: [
          60 + Number(col) * 70,
          204 + Number(row) * 14,
          120 + Number(col) * 70,
          216 + Number(row) * 14,
        ],
        source,
      }));
      layout.variants[0]!.units[table] = {
        tag: 'TABLE 1',
        page: 12,
        level: 'cell',
        translations: null,
        cells: [
          { row: 0, col: 0, text: 'Category' },
          { row: 1, col: 0, text: 'Made-up term' },
        ],
      };
      draw(serverOf(layout));
      await waitFor(
        () => expect(box('p12-t1#cell')?.getAttribute('data-issues')).toBe('1'),
        WAIT,
      );
      for (const id of [
        'p12-t1:r0c0',
        'p12-t1:r0c1',
        'p12-t1:r1c0',
        'p12-t1:r1c1',
      ]) {
        expect(box(id).getAttribute('data-issues')).toBeNull();
        expect(
          box(id).querySelector('[data-testid="pdf-box-badge"]'),
        ).toBeNull();
      }
      fireEvent.click(box('p12-t1:r1c1'));
      for (const testId of [
        'pdf-pair-source-grid',
        'pdf-pair-translation-grid',
      ]) {
        const on = screen.getByTestId(testId).querySelectorAll('td[data-on]');
        expect([...on].map((td) => td.getAttribute('data-cell'))).toEqual([
          '1:1',
        ]);
      }
      const text = (testId: string) =>
        [...screen.getByTestId(testId).querySelectorAll('td')].map(
          (td) => td.textContent,
        );
      expect(text('pdf-pair-source-grid')).toEqual([
        '구분',
        '2025',
        '지어낸용어',
        '1,200',
      ]);
      // 번역 없는 칸(숫자)은 원문 값.
      expect(text('pdf-pair-translation-grid')).toEqual([
        'Category',
        '2025',
        'Made-up term',
        '1,200',
      ]);
      expect(screen.getByTestId('pdf-pair-cell').textContent).toBe(
        words.cellAt(2, 2),
      );
    });

    it('표 짝: 테두리 누름 → 원문·번역 격자 둘(같은 행·열 · 강조 0 · 「n행 m열」 0) · 칸 누름 → 같은 짝 · 두 격자 같은 칸 강조 · 「n행 m열」', async () => {
      draw(serverOf());
      await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
      fireEvent.click(box('p12-t1#cell'));
      const source = screen.getByTestId('pdf-pair-source-grid');
      const translation = screen.getByTestId('pdf-pair-translation-grid');
      for (const grid of [source, translation]) {
        expect(grid.tagName).toBe('TABLE');
        expect(grid.getAttribute('data-table-rows')).toBe('1');
        expect(grid.getAttribute('data-table-cols')).toBe('1');
        expect(grid.querySelectorAll('td[data-on]')).toHaveLength(0);
      }
      expect(screen.queryByTestId('pdf-pair-source')).toBeNull();
      expect(screen.queryByTestId('pdf-pair-cell')).toBeNull();
      // 칸을 맞춘 표에는 「표 전체」 안내 0(검증 ③b-2 B1).
      expect(screen.getByTestId('pdf-pair').textContent).not.toContain(
        words.pair.tableWhole,
      );
      expect(box('p12-t1#cell').getAttribute('data-selected')).toBe('true');
      const position = screen.getByTestId('pdf-pair').textContent;
      fireEvent.click(box('p12-t1:r0c0'));
      expect(screen.getByTestId('pdf-pair-cell').textContent).toBe(
        words.cellAt(1, 1),
      );
      expect(screen.getByTestId('pdf-pair-position').textContent).toBe(
        words.pair.position(3, 4),
      );
      expect(position).toContain(words.pair.position(3, 4));
      // 쪽 위 고른 상자는 늘 하나 — 칸을 고르면 테두리는 풀린다.
      expect(box('p12-t1#cell').getAttribute('data-selected')).toBeNull();
      expect(box('p12-t1:r0c0').getAttribute('data-selected')).toBe('true');
      for (const testId of [
        'pdf-pair-source-grid',
        'pdf-pair-translation-grid',
      ]) {
        const cells = screen
          .getByTestId(testId)
          .querySelectorAll('td[data-on]');
        expect(cells).toHaveLength(1);
        expect(cells[0]!.getAttribute('data-cell')).toBe('0:0');
      }
      // [다음 짝]은 표 단위 — 칸을 세지 않고 꼬리말로.
      fireEvent.click(screen.getByRole('button', { name: words.pair.next }));
      expect(screen.getByTestId('pdf-pair').getAttribute('data-kind')).toBe(
        'source_only',
      );
    });
  });
});

// 밴드 TRW7 ② S2 — 스크롤·움직임(그린워싱 GW-05 꼴). jsdom 에는 레이아웃이 없어 「불렸나·인자·클래스·새 요소」만 — 위치는 e2e(S3).
describe('PdfView 스크롤·움직임 (TRW7 ② S2)', () => {
  type Into = (arg?: boolean | ScrollIntoViewOptions) => void;
  let into: ReturnType<typeof vi.fn<Into>>;
  const saved = Element.prototype.scrollIntoView;
  beforeEach(() => {
    into = vi.fn<Into>();
    Element.prototype.scrollIntoView = into;
  });
  afterEach(() => {
    Element.prototype.scrollIntoView = saved;
  });
  /** scrollTop 을 읽고 쓸 수 있게(jsdom 은 늘 0). */
  function scrollable(element: HTMLElement, start: number) {
    let value = start;
    Object.defineProperty(element, 'scrollTop', {
      configurable: true,
      get: () => value,
      set: (next: number) => {
        value = next;
      },
    });
    return () => value;
  }
  /** 쪽 13(글 없는 쪽)을 더한 layout. */
  function twoPages() {
    const layout = layoutOf() as Json & { pages: Json[] };
    layout.pages.push({ page: 13, width: 595, height: 842, textLayer: 'none' });
    return layout;
  }

  it('sticky: 쪽 칸·짝 칸 top 24 · maxHeight calc(100dvh - 48px), 쪽 그림은 pdf-page-scroll 안', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    for (const testId of ['pdf-page-pane', 'pdf-pairs']) {
      const pane = screen.getByTestId(testId);
      expect(pane.className).toContain('sticky');
      expect(pane.style.top).toBe('24px');
      expect(pane.style.maxHeight).toBe('calc(100dvh - 48px)');
    }
    const scroller = screen.getByTestId('pdf-page-scroll');
    expect(scroller.className).toContain('overflow-auto');
    expect(scroller.contains(screen.getByTestId('pdf-page'))).toBe(true);
    expect(screen.getByTestId('pdf-pairs').className).toContain(
      'overflow-y-auto',
    );
  });

  it('쪽 바뀜 → 쪽 칸 scrollTop 0 · 쪽 목록 지금 줄 scrollIntoView(nearest) 한 번 — 처음 그릴 때는 0', async () => {
    draw(serverOf(twoPages()));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(into).not.toHaveBeenCalled();
    const top = scrollable(screen.getByTestId('pdf-page-scroll'), 300);
    const line = document.querySelector('nav [data-page="13"]') as HTMLElement;
    fireEvent.click(line);
    await waitFor(() => screen.getByTestId('pdf-image-only'), WAIT);
    expect(top()).toBe(0);
    expect(into).toHaveBeenCalledTimes(1);
    expect(into).toHaveBeenCalledWith({ block: 'nearest' });
    expect(into.mock.contexts[0]).toBe(line);
  });

  it('상자 고름 → 짝 칸 scrollTop 0 · 같은 상자 다시 골라도 0', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    const top = scrollable(pairs(), 200);
    fireEvent.click(box('p12-b2'));
    expect(top()).toBe(0);
    scrollable(pairs(), 150);
    const again = scrollable(pairs(), 150);
    fireEvent.click(box('p12-b2'));
    expect(again()).toBe(0);
  });

  it('짝 칸 이슈 줄 누름 → 그 번호 밑줄 scrollIntoView(center) · 용어 줄도', async () => {
    draw(serverOf());
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
      WAIT,
    );
    fireEvent.click(box('p12-b2'));
    const line = within(screen.getByTestId('pdf-pair-issues')).getByRole(
      'button',
    );
    fireEvent.click(line);
    const mark = screen
      .getByTestId('pdf-pair')
      .querySelector('mark[data-n="1"]');
    expect(mark).not.toBeNull();
    expect(into).toHaveBeenLastCalledWith({ block: 'center' });
    expect(into.mock.contexts.at(-1)).toBe(mark);
    // 용어(원문 밑줄) — BLOCK 1 첫 member.
    fireEvent.click(box('p12-b1'));
    fireEvent.click(
      within(screen.getByTestId('pdf-misses')).getByRole('button'),
    );
    expect(into.mock.contexts.at(-1)).toBe(
      screen.getByTestId('pdf-pair').querySelector('mark[data-mark="term"]'),
    );
  });

  it('쪽 전체 목록(짝 안 고름)의 줄은 단추 아님', async () => {
    const layout = layoutOf();
    const a = (layout.variants as { units: Json[] }[])[0]!;
    a.units[0] = { ...a.units[0]!, translations: ['Climate', 'Other words'] };
    draw(serverOf(layout));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    openIssueTab(); // 밴드 TRW8 ⑥: 「페이지 전체」는 [검수 이슈] 탭 안.
    const list = await waitFor(
      () => screen.getByTestId('pdf-page-issues'),
      WAIT,
    );
    expect(list.querySelector('[data-issue-line]')).not.toBeNull();
    expect(within(list).queryByRole('button')).toBeNull();
  });

  it('짝 [다음 짝]/[이전 짝] → 쪽 위 고름(data-selected)도 옮김', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b1'));
    fireEvent.click(screen.getByRole('button', { name: words.pair.next }));
    expect(box('p12-b2').getAttribute('data-selected')).toBe('true');
    expect(box('p12-b1').getAttribute('data-selected')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: words.pair.prev }));
    expect(box('p12-b1').getAttribute('data-selected')).toBe('true');
  });

  it('움직임: 고른 상자 gw-m-mark(blue-600 빛) · 같은 상자 다시 고름 → 새 요소 · 안 고른 상자 0', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(document.querySelector('.gw-m-mark')).toBeNull();
    fireEvent.click(box('p12-b2'));
    const first = box('p12-b2').querySelector('[data-testid="pdf-box-mark"]')!;
    expect(first.className).toContain('gw-m-mark');
    expect(first.className).toContain('text-blue-600');
    expect(document.querySelectorAll('.gw-m-mark')).toHaveLength(1);
    fireEvent.click(box('p12-b2'));
    const second = box('p12-b2').querySelector('[data-testid="pdf-box-mark"]')!;
    expect(second).not.toBe(first);
    expect(second.className).toContain('gw-m-mark');
  });

  it('움직임: 짝 칸 몸 gw-m-fade — 고른 짝이 바뀌면 새 요소 · 「이슈 N」·띠 gw-m-rise', async () => {
    draw(serverOf(), {
      page: 12,
      pair: 1,
      label: 'A',
      from: { where: '12페이지 둘째 문단', type: '어색한 표현' },
    });
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
      WAIT,
    );
    expect(screen.getByTestId('pdf-from-table').className).toContain(
      'gw-m-rise',
    );
    const badges = [
      ...document.querySelectorAll('[data-testid="pdf-box-badge"]'),
    ];
    expect(badges.length).toBeGreaterThan(0);
    for (const badge of badges) expect(badge.className).toContain('gw-m-rise');
    const body = screen.getByTestId('pdf-pairs-body');
    expect(body.className).toContain('gw-m-fade');
    fireEvent.click(box('p12-b1'));
    const next = screen.getByTestId('pdf-pairs-body');
    expect(next).not.toBe(body);
    expect(next.className).toContain('gw-m-fade');
  });

  it('움직임 CSS 는 공용 표면 import 로 싣는다(motion.css 를 직접 가져오지 않음)', () => {
    // 시험은 apps/web 에서 돈다(vitest 뿌리).
    const source = readFileSync(
      join(process.cwd(), 'src/pages/translation-run/ui/pdf/PdfView.tsx'),
      'utf8',
    );
    expect(source).toContain("import '../../../../shared/ui/motion/index.ts';");
    expect(source).not.toContain('motion.css');
    expect(source).not.toMatch(/animation\s*:/);
  });
});

// 밴드 TRW7 ③b-1 — 디자인 74 판 차이 D1~D6·D8(band-reports/TRW7-design-diff.md) · 파트 탭(W8, 감독 답 Q1 — 파트 탭만).
describe('PdfView 판 차이·채움·파트 탭 (TRW7 ③b-1)', () => {
  it('세 칸: 틈 16 · 쪽 목록·쪽 칸·짝 칸은 흰 카드(radius dialog, 테두리 0) · 쪽 자리 tertiary · 쪽 그림 그림자(테두리 0)', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    const nav = screen.getByRole('navigation');
    expect(nav.parentElement!.className).toContain('gap-4');
    expect(nav.parentElement!.className).not.toContain('gap-6');
    for (const card of [
      nav,
      screen.getByTestId('pdf-page-pane'),
      screen.getByTestId('pdf-pairs'),
    ]) {
      expect(card.className).toContain('rounded-dialog');
      expect(card.className).toContain('bg-background-primary');
      expect(card.className).not.toMatch(/(^|\s)border(\s|$)/);
    }
    expect(screen.getByTestId('pdf-page-pane').className).toContain('p-4');
    expect(screen.getByTestId('pdf-pairs').className).toContain('p-5');
    const scroller = screen.getByTestId('pdf-page-scroll');
    expect(scroller.className).toContain('bg-background-tertiary');
    expect(scroller.className).toContain('p-6');
    const sheet = screen.getByTestId('pdf-page');
    expect(sheet.className).toContain('shadow-[0_0_5px_2px_rgb(0_0_0/0.1)]');
    expect(sheet.className).toContain('bg-white');
    expect(sheet.className).not.toMatch(/(^|\s)border(\s|$)/);
  });

  it('단계 띠: 체크 아이콘 — autofix 는 success, translated 는 tertiary', async () => {
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    const icon = () => screen.getByTestId('pdf-stage').querySelector('svg')!;
    expect(screen.getByTestId('pdf-stage').getAttribute('data-stage')).toBe(
      'autofix',
    );
    expect(icon().getAttribute('class')).toContain('text-support-success');
    // Radix 탭은 mousedown 으로 바뀐다.
    fireEvent.mouseDown(screen.getByRole('tab', { name: words.styleOf('B') }), {
      button: 0,
    });
    await waitFor(() =>
      expect(screen.getByTestId('pdf-stage').getAttribute('data-stage')).toBe(
        'translated',
      ),
    );
    expect(icon().getAttribute('class')).toContain('text-text-tertiary');
  });

  it('채움: 상자 바탕은 따로 칸(pdf-box-fill)에 mix-blend-multiply — 단추엔 바탕 0 · 고른 상자는 불투명 blue-100 · 배지·⚠·빛엔 multiply 0', async () => {
    draw(serverOf(), {
      page: 12,
      pair: 1,
      label: 'A',
      from: null,
    });
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
      WAIT,
    );
    for (const each of boxes())
      expect(each.className).not.toMatch(/(^|\s)bg-(?!transparent)/);
    const fillOf = (id: string) =>
      box(id).querySelector<HTMLElement>('[data-testid="pdf-box-fill"]');
    // 안 고른 문단: 판 알파 그대로(35%) · multiply.
    expect(fillOf('p12-b1')!.className).toContain('bg-blue-100/35');
    expect(fillOf('p12-b1')!.className).toContain('mix-blend-multiply');
    // 고른 문단: 불투명 blue-100 · multiply.
    const picked = fillOf('p12-b2')!;
    expect(picked.className).toMatch(/(^|\s)bg-blue-100(\s|$)/);
    expect(picked.className).toContain('mix-blend-multiply');
    // 표 테두리·칸은 채움 없음(판 .bx-t·.bx-c).
    expect(fillOf('p12-t1#cell')).toBeNull();
    // 섞이지 않는 층: 「이슈 N」·빛은 채움 칸의 형제이고 multiply 0.
    const badge = box('p12-b2').querySelector('[data-testid="pdf-box-badge"]')!;
    const mark = box('p12-b2').querySelector('[data-testid="pdf-box-mark"]')!;
    for (const layer of [badge, mark]) {
      expect(layer.className).not.toContain('mix-blend');
      expect(picked.contains(layer)).toBe(false);
    }
    // 쌓임 맥락: 단추·쪽 그림 틀에 z-index·isolate 0(열면 곱하기가 그 안에 갇힌다).
    for (const element of [box('p12-b2'), screen.getByTestId('pdf-page')]) {
      expect(element.className).not.toMatch(/(^|\s)(z-|isolate)/);
      expect(element.style.zIndex).toBe('');
    }
  });

  describe('파트 탭', () => {
    const KEY = 'aaaaaaaa-0000-4000-8000-00000000000b';
    /** 30 = PDF 스토리 12쪽, 31 = PDF 일반 13쪽, 32 = 워드 CEO(끝남) — 같은 묶음. */
    function partsServer({
      second = true,
      running = false,
    }: { second?: boolean; running?: boolean } = {}) {
      const server = fakeTranslationServer({
        documents: [
          fakeDocument(12, { fileName: 'made_up.pdf', pdf: PDF_BYTES }),
        ],
        runs: [
          fakeRun(30, 12, fakeOptions('story', 12, 12, KEY), {
            flowId: 'translation.pdf@158',
          }),
          ...(second ?
            [
              fakeRun(31, 12, fakeOptions('general', 13, 13, KEY), {
                flowId: 'translation.pdf@158',
              }),
            ]
          : []),
          // running: 32 를 진행 중인 PDF CEO 파트로(검증 R6 — 끝나지 않은 파트는 탭 0).
          running ?
            fakeRun(32, 12, fakeOptions('ceo_message', 1, 3, KEY), {
              flowId: 'translation.pdf@158',
            })
          : fakeRun(32, 12, fakeOptions('ceo_message', 1, 3, KEY)),
        ],
      });
      server.advance(30, { status: 'done', layout: layoutOf() });
      if (second)
        server.advance(31, { status: 'done', layout: fakeLayout(13) });
      if (!running) server.advance(32, { status: 'done' });
      return server;
    }
    function drawParts(server: ReturnType<typeof partsServer>) {
      const onOpenPart = vi.fn();
      render(
        <PdfView
          store={serverStoreOf(server)}
          runId="30"
          documentId="12"
          openPdf={fakePdf().openPdf}
          focus={null}
          copy={vi.fn(async () => {})}
          onBack={vi.fn()}
          batchKey={KEY}
          onOpenPart={onOpenPart}
        />,
      );
      return onOpenPart;
    }

    it('끝난 PDF 파트 둘 → 탭 둘(워드 파트·[전체] 0) · 지금 파트 눌림 · 다른 파트 누름 → onOpenPart(그 runId) · 지금 파트 누름 → 0', async () => {
      const onOpenPart = drawParts(partsServer());
      const tabs = await waitFor(() => {
        const found = screen.getAllByRole('tab', { name: /스토리|일반/ });
        expect(found).toHaveLength(2);
        return found;
      }, WAIT);
      expect(
        screen
          .getByTestId('pdf-part-tabs')
          .querySelectorAll('[role="tab"][data-tab]'),
      ).toHaveLength(2);
      expect(screen.queryByRole('tab', { name: /전체/ })).toBeNull();
      expect(
        screen.queryByRole('tab', {
          name: new RegExp(TR_TEXT.parts.names.ceo),
        }),
      ).toBeNull();
      const story = tabs.find(
        (tab) => tab.getAttribute('data-tab') === 'story',
      )!;
      const general = tabs.find(
        (tab) => tab.getAttribute('data-tab') === 'general',
      )!;
      expect(story.getAttribute('aria-selected')).toBe('true');
      // 몸(보기)은 탭 안에 그대로.
      await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
      expect(
        screen
          .getByTestId('pdf-part-tabs')
          .contains(screen.getByTestId('pdf-pairs')),
      ).toBe(true);
      fireEvent.mouseDown(general, { button: 0 });
      fireEvent.click(general);
      await waitFor(() => expect(onOpenPart).toHaveBeenCalledWith('31'));
      onOpenPart.mockClear();
      fireEvent.mouseDown(story, { button: 0 });
      fireEvent.click(story);
      expect(onOpenPart).not.toHaveBeenCalled();
    });

    it('진행 중 PDF 파트는 탭 0(끝난 PDF 파트 둘만)', async () => {
      drawParts(partsServer({ running: true }));
      await waitFor(
        () =>
          expect(
            screen
              .getByTestId('pdf-part-tabs')
              .querySelectorAll('[role="tab"][data-tab]'),
          ).toHaveLength(2),
        WAIT,
      );
      expect(
        screen
          .getByTestId('pdf-part-tabs')
          .querySelector('[role="tab"][data-tab="ceo"]'),
      ).toBeNull();
    });

    it('끝난 PDF 파트 하나 → 탭 줄 0 · 몸은 그대로', async () => {
      drawParts(partsServer({ second: false }));
      await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
      expect(screen.queryByRole('tab', { name: /스토리/ })).toBeNull();
    });

    it('batchKey·onOpenPart 를 안 넘기면 묶음을 읽지 않음(탭 0)', async () => {
      const server = partsServer();
      draw(server);
      await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
      expect(screen.queryByTestId('pdf-part-tabs')).toBeNull();
      expect(screen.queryByRole('tab', { name: /스토리/ })).toBeNull();
    });
  });
});

// 밴드 TRW8 ③~⑦·② — 항목 칸(디자인 74 처방, sid:MARC-ISSUE-454).
describe('PdfView 항목 칸 (TRW8)', () => {
  /** 쪽 12·13 둘 — 13쪽에는 이슈·용어 0. */
  function twoPages(compare = false) {
    const layout = layoutOf({ compare }) as Json & {
      pages: Json[];
      units: Json[];
      variants: (Json & { units: Json[] })[];
    };
    layout.pages.push({
      page: 13,
      width: 595.28,
      height: 841.89,
      textLayer: 'present',
    });
    layout.units.push({
      tag: 'BLOCK 9',
      page: 13,
      kind: 'block',
      members: [
        {
          id: 'p13-b1',
          key: 'k-1301',
          kind: 'paragraph',
          bbox: [56.7, 72.0, 320.4, 94.1],
          source: '다음 쪽 글',
        },
      ],
    });
    for (const variant of layout.variants)
      variant.units.push({
        tag: 'BLOCK 9',
        page: 13,
        level: 'block',
        translations: ['Next page words'],
      });
    return layout;
  }

  it('③ 글: 목록 머리 「12페이지 항목 4개」 · 상세 「3 / 4」 · 이전/다음 항목 · [목록으로] · 「짝」 글자 0', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(within(pairs()).getByText(words.pair.listTitle(12, 4))).toBeTruthy();
    expect(words.pair.listTitle(12, 4)).toBe('12페이지 항목 4개');
    expect(pairs().textContent).not.toContain('짝');
    fireEvent.click(box('p12-t1#cell'));
    expect(screen.getByTestId('pdf-pair-position').textContent).toBe('3 / 4');
    expect(screen.getByRole('button', { name: '이전 항목' }).tagName).toBe(
      'BUTTON',
    );
    expect(screen.getByRole('button', { name: '다음 항목' })).toBeTruthy();
    expect(screen.getByTestId('pdf-pair-back').textContent).toBe('목록으로');
    expect(pairs().textContent).not.toContain('짝');
  });

  it('④ 표 칸을 고른 채 문체 바꿈: 새 항목에 같은 칸이 있으면 칸 유지 · 없으면(표 전체) 칸만 버림', async () => {
    const layout = layoutOf({ compare: true }) as Json & {
      variants: (Json & { units: Json[] })[];
    };
    // B 도 칸을 맞춘 표(같은 1×1) — 칸 유지 갈래.
    layout.variants[1]!.units[1] = {
      tag: 'TABLE 1',
      page: 12,
      level: 'cell',
      translations: null,
      cells: [{ row: 0, col: 0, text: 'B category' }],
    };
    draw(serverOf(layout));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-t1:r0c0'));
    pickStyle(1);
    await waitFor(
      () =>
        expect(screen.getByTestId('pdf-stage').getAttribute('data-stage')).toBe(
          'translated',
        ),
      WAIT,
    );
    expect(screen.getByTestId('pdf-pair-cell').textContent).toBe(
      words.cellAt(1, 1),
    );
    const on = screen
      .getByTestId('pdf-pair-translation-grid')
      .querySelectorAll('td[data-on]');
    expect(on).toHaveLength(1);
    expect(on[0]!.textContent).toBe('B category');
    expect(box('p12-t1:r0c0').getAttribute('data-selected')).toBe('true');
    cleanup();

    // B 가 표 전체(level table) — 같은 unit 항목은 고르고 칸은 버림.
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-t1:r0c0'));
    pickStyle(1);
    await waitFor(() => expect(boxes()).toHaveLength(3), WAIT);
    expect(screen.getByTestId('pdf-pair').getAttribute('data-kind')).toBe(
      'table',
    );
    expect(screen.queryByTestId('pdf-pair-cell')).toBeNull();
    expect(screen.getByTestId('pdf-pair-position').textContent).toBe(
      words.pair.position(2, 3),
    );
  });

  it('④ 새 문체에 그 unit 이 없으면 목록으로', async () => {
    const layout = layoutOf({ compare: true }) as Json & {
      variants: (Json & { units: Json[] })[];
    };
    // B 에서 꼬리말 unit(마지막)을 뺀다 — placed 없음 → 그 unit 항목 0.
    layout.variants[1]!.units.splice(2, 1);
    draw(serverOf(layout));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b9'));
    expect(screen.getByTestId('pdf-pair')).toBeTruthy();
    pickStyle(1);
    await waitFor(
      () =>
        expect(screen.getByTestId('pdf-stage').getAttribute('data-stage')).toBe(
          'translated',
        ),
      WAIT,
    );
    expect(screen.queryByTestId('pdf-pair')).toBeNull();
    expect(screen.getByTestId('pdf-list-tabs')).toBeTruthy();
    expect(document.querySelector('[data-box][data-selected]')).toBeNull();
  });

  it('⑤ 상세 맨 위 한 줄: [목록으로] → ‹ → 위치 → › 차례 · 맨 아래 단추 줄 0 · 끝에서 disabled · [목록으로] → 목록', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b1'));
    const detail = screen.getByTestId('pdf-pair');
    const nav = screen.getByTestId('pdf-pair-nav');
    expect(detail.firstElementChild).toBe(nav);
    const order = [
      ...nav.querySelectorAll('button, [data-testid="pdf-pair-position"]'),
    ].map(
      (each) =>
        each.getAttribute('aria-label') ?? each.getAttribute('data-testid'),
    );
    expect(order).toEqual([
      'pdf-pair-back',
      words.pair.prev,
      'pdf-pair-position',
      words.pair.next,
    ]);
    // 이동 단추는 맨 위 줄에만(셋) — 그 밖의 단추는 「번역」 머리 줄 「번역 복사」 하나(밴드 TRW14 ③)와 이슈·용어 줄뿐(맨 아래 단추 줄 0).
    expect(nav.querySelectorAll('button')).toHaveLength(3);
    expect(
      detail.querySelectorAll('[data-testid="pdf-pair-copy"]'),
    ).toHaveLength(1);
    const outside = [...detail.querySelectorAll('button')].filter(
      (each) =>
        !nav.contains(each) &&
        each.getAttribute('data-testid') !== 'pdf-pair-copy',
    );
    expect(outside.length).toBeGreaterThan(0);
    for (const each of outside)
      expect(each.closest('[data-term-line],[data-issue-line]')).not.toBeNull();
    expect(
      (
        screen.getByRole('button', {
          name: words.pair.prev,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(
      (
        screen.getByRole('button', {
          name: words.pair.next,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
    // 아이콘 단추(IconButton md) · 목록으로 단추 안 화살표 아이콘.
    expect(
      screen.getByRole('button', { name: words.pair.next }).className,
    ).toContain('size-7');
    expect(
      screen.getByTestId('pdf-pair-back').querySelector('svg'),
    ).not.toBeNull();
    fireEvent.click(box('p12-b9'));
    expect(
      (
        screen.getByRole('button', {
          name: words.pair.next,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByTestId('pdf-pair-back'));
    expect(screen.queryByTestId('pdf-pair')).toBeNull();
    expect(document.querySelector('[data-box][data-selected]')).toBeNull();
  });

  it('⑥ 탭 둘 「항목 4」·「검수 이슈 2」 · 기본 항목 탭(이슈 줄 0) · 이슈 탭: 「항목 k」 묶음 · 번호 == 상세 밑줄 번호 · 줄 누름 → 상세 · [목록으로] → 이슈 탭', async () => {
    draw(serverOf());
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
      WAIT,
    );
    expect(listTab(0).textContent).toBe(words.pair.tabs.items(4));
    expect(listTab(1).textContent).toBe(words.pair.tabs.issues(2));
    expect(listTab(0).getAttribute('aria-selected')).toBe('true');
    expect(
      pairs().querySelector('[data-issue-line],[data-term-line]'),
    ).toBeNull();
    openIssueTab();
    const groups = screen.getAllByTestId('pdf-issue-group');
    // 항목 차례: 용어(항목 1 — b1 원문) · 이슈(항목 2 — b2 번역).
    expect(groups.map((g) => g.getAttribute('data-pair'))).toEqual(['0', '1']);
    expect(groups[0]!.textContent).toContain(words.pair.itemOf(1));
    expect(groups[1]!.textContent).toContain(words.pair.itemOf(2));
    expect(
      groups[0]!
        .querySelector('[data-term-line]')!
        .getAttribute('data-term-line'),
    ).toBe('1');
    const line = groups[1]!.querySelector('[data-issue-line]')!;
    expect(line.getAttribute('data-issue-line')).toBe('1');
    fireEvent.click(within(groups[1]! as HTMLElement).getByRole('button'));
    expect(screen.getByTestId('pdf-pair-position').textContent).toBe(
      words.pair.position(2, 4),
    );
    expect(box('p12-b2').getAttribute('data-selected')).toBe('true');
    expect(
      screen
        .getByTestId('pdf-pair-translation')
        .querySelector('mark[data-mark="issue"]')!
        .getAttribute('data-n'),
    ).toBe(line.getAttribute('data-issue-line'));
    expect(screen.queryByTestId('pdf-list-tabs')).toBeNull();
    fireEvent.click(screen.getByTestId('pdf-pair-back'));
    expect(listTab(1).getAttribute('aria-selected')).toBe('true');
    expect(screen.getAllByTestId('pdf-issue-group')).toHaveLength(2);
  });

  it('⑥ 한 항목에 이슈·용어 → 이슈 탭 번호 1·2(상세와 같음) · 페이지 전체 묶음은 맨 아래', async () => {
    const layout = layoutOf() as Json & {
      units: { members: { source: string }[] }[];
      variants: (Json & { units: Json[] })[];
    };
    layout.units[0]!.members[0]!.source = '기후 대응 전략';
    layout.units[0]!.members[1]!.source = '지어낸용어 로 배출을 줄인다';
    draw(serverOf(layout));
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('2'),
      WAIT,
    );
    openIssueTab();
    const group = screen.getByTestId('pdf-issue-group');
    expect(
      group.querySelector('[data-issue-line]')!.getAttribute('data-issue-line'),
    ).toBe('1');
    expect(
      group.querySelector('[data-term-line]')!.getAttribute('data-term-line'),
    ).toBe('2');
    cleanup();

    const loose = layoutOf();
    const a = (loose.variants as { units: Json[] }[])[0]!;
    a.units[0] = { ...a.units[0]!, translations: ['Climate', 'Other words'] };
    draw(serverOf(loose));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    openIssueTab();
    const tab = screen.getByTestId('pdf-issue-tab');
    expect(tab.lastElementChild).toBe(screen.getByTestId('pdf-page-whole'));
    expect(screen.getByTestId('pdf-page-whole').textContent).toContain(
      words.pair.pageWhole,
    );
    expect(screen.getByTestId('pdf-page-whole').textContent).toContain(
      words.pageIssuesNote,
    );
  });

  it('⑥ 고른 탭은 쪽 넘김에도 그대로 · 0건 쪽 → 「검수 이슈 0」 + 한 줄', async () => {
    draw(serverOf(twoPages()));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    openIssueTab();
    fireEvent.click(screen.getByRole('button', { name: words.next }));
    await waitFor(() => expect(boxes()).toHaveLength(1), WAIT);
    expect(listTab(1).getAttribute('aria-selected')).toBe('true');
    expect(listTab(1).textContent).toBe(words.pair.tabs.issues(0));
    expect(screen.getByTestId('pdf-no-issues').textContent).toBe(
      words.pair.noIssues,
    );
  });

  it('⑦ 목록 줄: 번호 칸 따로 · 「이슈 N」 == 쪽 위 상자 data-issues · 0 이면 배지 0 · 줄 꼴', async () => {
    draw(serverOf());
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
      WAIT,
    );
    const rows = [...pairs().querySelectorAll('button[data-pair]')];
    expect(rows).toHaveLength(4);
    const sources = [
      '지어낸용어 대응 전략',
      '지어낸 회사는 2030년까지 배출을 줄인다',
      '| 구분 | 2025 |\n| --- | --- |\n| 배출량 | 1,200 |',
      '2026 지속가능경영보고서 12',
    ];
    rows.forEach((row, n) => {
      expect(
        row.querySelector('[data-testid="pdf-pair-number"]')!.textContent,
      ).toBe(String(n + 1));
      // 원문 줄은 번호를 앞에 붙이지 않는다(글 그대로).
      expect(
        row.querySelector('[data-testid="pdf-pair-line-source"]')!.textContent,
      ).toBe(sources[n]);
      expect(row.className).toContain('rounded-component');
      expect(row.className).toContain('hover:bg-background-tertiary');
    });
    const byBox = ['p12-b1', 'p12-b2', 'p12-t1#cell', 'p12-b9'].map((id) =>
      box(id).getAttribute('data-issues'),
    );
    expect(rows.map((row) => row.getAttribute('data-issues'))).toEqual(byBox);
    expect(rows[0]!.textContent).toContain(words.badge(1));
    expect(rows[1]!.textContent).toContain(words.badge(1));
    expect(rows[2]!.querySelector('[data-testid="pdf-pair-badge"]')).toBeNull();
    expect(rows[3]!.querySelector('[data-testid="pdf-pair-badge"]')).toBeNull();
  });

  it('② 표는 overflow-x-auto 상자 안 — 격자 둘 · pipe 표 · 칸 최소 폭', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-t1#cell'));
    for (const testId of [
      'pdf-pair-source-grid',
      'pdf-pair-translation-grid',
    ]) {
      const table = screen.getByTestId(testId);
      expect(table.parentElement!.getAttribute('data-testid')).toBe(
        'pdf-table-scroll',
      );
      expect(table.parentElement!.className).toContain('overflow-x-auto');
      expect(table.querySelector('td')!.className).toContain('min-w-[72px]');
    }
    cleanup();
    const layout = layoutOf() as Json & {
      units: (Json & { members: { source: string }[] })[];
      variants: (Json & { units: Json[] })[];
    };
    const table = layout.units.findIndex((unit) => unit.tag === 'TABLE 1');
    layout.units[table]!.members[0]!.source =
      '| 구분 | 2025 |\n| --- | --- |\n| 지어낸 값 | 1,200 |';
    layout.variants[0]!.units[table] = {
      tag: 'TABLE 1',
      page: 12,
      level: 'table',
      translations: ['| Item | 2025 |\n| --- | --- |\n| Made-up | 1,200 |'],
    };
    draw(serverOf(layout));
    await waitFor(() => expect(boxes()).toHaveLength(4), WAIT);
    fireEvent.click(box('p12-t1#table'));
    const pipe = screen.getAllByTestId('pdf-pair-source-table')[0]!;
    expect(pipe.parentElement!.className).toContain('overflow-x-auto');
    expect(pipe.querySelector('th')!.className).toContain('min-w-[72px]');
  });
});

describe('PdfView 상세 문체 전환 「둘 다」 (TRW8 ①b — sid:MARC-ENT-502)', () => {
  type Into = (arg?: boolean | ScrollIntoViewOptions) => void;
  let into: ReturnType<typeof vi.fn<Into>>;
  const saved = Element.prototype.scrollIntoView;
  beforeEach(() => {
    into = vi.fn<Into>();
    Element.prototype.scrollIntoView = into;
  });
  afterEach(() => {
    Element.prototype.scrollIntoView = saved;
  });
  const sides = () => screen.queryAllByTestId('pdf-pair-style');
  const styleOf = (each: Element) => each.getAttribute('data-style');

  it('자리: 목록 꼴은 맨 위 탭 · 상세 꼴은 맨 위 탭 0 + 「번역」 머리 줄 전환 [A][B][둘 다](「번역 스타일」) · [목록으로] → 맨 위 탭 · 한 문체 실행은 전환 0', async () => {
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(topStyleTabs()).not.toBeNull();
    expect(screen.queryByTestId('pdf-style-switch')).toBeNull();
    fireEvent.click(box('p12-b2'));
    expect(topStyleTabs()).toBeNull();
    const list = within(pairs()).getByRole('tablist', {
      name: words.pair.styles.label,
    });
    expect(list).toBe(screen.getByTestId('pdf-style-switch'));
    expect(words.pair.styles.label).toBe('번역 스타일');
    expect(
      within(list)
        .getAllByRole('tab')
        .map((tab) => tab.textContent),
    ).toEqual(['A', 'B', '둘 다']);
    expect(styleSwitch(0).getAttribute('aria-selected')).toBe('true');
    // 「번역」 머리 줄 오른쪽 — 같은 줄의 첫 칸이 「번역」.
    const row = list.closest('[data-testid="pdf-pair"] > div > div')!;
    expect(row.firstElementChild!.textContent).toBe(words.pair.translation);
    expect(row.lastElementChild!.contains(list)).toBe(true);
    fireEvent.click(screen.getByTestId('pdf-pair-back'));
    expect(topStyleTabs()).not.toBeNull();
    cleanup();

    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b2'));
    expect(screen.getByTestId('pdf-pair')).toBeTruthy();
    expect(screen.queryByTestId('pdf-style-switch')).toBeNull();
    expect(
      within(pairs()).queryByRole('tablist', { name: words.pair.styles.label }),
    ).toBeNull();
  });

  it('둘 다: 원문 아래 「번역 A」·「번역 B」 칸(그 문체 번역 · 칸 머리 옆 단계) · 맨 위 단계 줄 0 · 원문 밑줄 0 · 쪽 위는 A 그대로', async () => {
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
      WAIT,
    );
    fireEvent.click(box('p12-b2'));
    expect(screen.getByTestId('pdf-stage')).toBeTruthy();
    expect(sides()).toHaveLength(0);
    pickStyle(2);
    expect(styleSwitch(2).getAttribute('aria-selected')).toBe('true');
    expect(sides().map(styleOf)).toEqual(['A', 'B']);
    const [a, b] = sides() as [HTMLElement, HTMLElement];
    expect(a.firstElementChild!.textContent).toContain(
      words.pair.translationOf('A'),
    );
    expect(b.firstElementChild!.textContent).toContain(
      words.pair.translationOf('B'),
    );
    expect(words.pair.translationOf('B')).toBe('번역 B');
    expect(within(a).getByTestId('pdf-pair-translation').textContent).toBe(
      'Made-up text about cuts',
    );
    expect(within(b).getByTestId('pdf-pair-translation').textContent).toBe(
      'B style merged',
    );
    expect(
      within(a).getByTestId('pdf-style-stage').getAttribute('data-stage'),
    ).toBe('autofix');
    expect(
      within(b).getByTestId('pdf-style-stage').getAttribute('data-stage'),
    ).toBe('translated');
    expect(screen.queryByTestId('pdf-stage')).toBeNull();
    // 원문이 먼저, 그 아래 A·B.
    const source = screen.getAllByTestId('pdf-pair-source')[0]!;
    expect(
      source.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      screen
        .getByTestId('pdf-pair')
        .querySelectorAll('[data-testid="pdf-pair-source"] mark'),
    ).toHaveLength(0);
    // 쪽 위는 바꾸기 직전 문체(A) — 상자 다섯 · 고른 상자 그대로.
    expect(boxes()).toHaveLength(5);
    expect(box('p12-b2').getAttribute('data-selected')).toBe('true');
  });

  it('둘 다: 이슈는 「스타일 A 이슈 n」·「스타일 B 이슈 n」 묶음 · 번호는 문체마다 1 부터 · 줄 누름 → 그 문체 칸의 밑줄만', async () => {
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(
      () => expect(box('p12-b2')?.getAttribute('data-issues')).toBe('1'),
      WAIT,
    );
    fireEvent.click(box('p12-b2'));
    pickStyle(2);
    const groups = screen.getAllByTestId('pdf-style-issues');
    expect(groups.map(styleOf)).toEqual(['A', 'B']);
    // A: 이 항목(b2 번역)의 이슈 하나 · B: 묶음(BLOCK 1) 원문의 용어 하나.
    expect(groups[0]!.querySelector('h4')!.textContent).toBe(
      words.pair.issuesOf('A', 1),
    );
    expect(groups[1]!.querySelector('h4')!.textContent).toBe(
      words.pair.issuesOf('B', 1),
    );
    expect(words.pair.issuesOf('B', 1)).toBe('스타일 B 이슈 1');
    expect(
      groups[0]!
        .querySelector('[data-issue-line]')!
        .getAttribute('data-issue-line'),
    ).toBe('1');
    expect(groups[0]!.querySelector('[data-term-line]')).toBeNull();
    expect(
      groups[1]!
        .querySelector('[data-term-line]')!
        .getAttribute('data-term-line'),
    ).toBe('1');
    expect(groups[1]!.querySelector('[data-issue-line]')).toBeNull();
    // 한 문체 상세의 묶음 머리(「검수 이슈 n」)는 없다.
    expect(pairs().textContent).not.toContain(words.issuesTitle(1));
    const [a] = sides() as [HTMLElement];
    const mark = a.querySelector('mark[data-mark="issue"][data-n="1"]');
    expect(mark).not.toBeNull();
    fireEvent.click(within(groups[0]!).getByRole('button'));
    expect(into).toHaveBeenLastCalledWith({ block: 'center' });
    expect(into.mock.contexts.at(-1)).toBe(mark);
    // B 용어 1 의 밑줄은 B 칸에 없다(원문 밑줄 0) — A 칸의 「1」로 가지 않는다.
    const calls = into.mock.calls.length;
    fireEvent.click(within(groups[1]!).getByRole('button'));
    expect(into.mock.calls.length).toBe(calls);
  });

  it('고른 것 유지: 둘 다 → 다음 항목에도 둘 다 · [B] → B 한 문체(쪽 위 B · 같은 unit) · [목록으로] → 맨 위 탭 B', async () => {
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b1'));
    const sourceMarks = () =>
      pairs().querySelectorAll('[data-testid="pdf-pair-source"] mark');
    // 한 문체면 용어 밑줄이 원문에 · 「둘 다」면 원문 밑줄 0(용어 번호가 문체마다 다름).
    expect(sourceMarks()).toHaveLength(1);
    pickStyle(2);
    expect(sides()).toHaveLength(2);
    expect(sourceMarks()).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: words.pair.next }));
    expect(screen.getByTestId('pdf-pair-position').textContent).toBe(
      words.pair.position(2, 4),
    );
    expect(styleSwitch(2).getAttribute('aria-selected')).toBe('true');
    expect(sides().map(styleOf)).toEqual(['A', 'B']);
    expect(
      within(sides()[0]! as HTMLElement).getByTestId('pdf-pair-translation')
        .textContent,
    ).toBe('Made-up text about cuts');
    pickStyle(1);
    await waitFor(() => expect(boxes()).toHaveLength(3), WAIT);
    expect(sides()).toHaveLength(0);
    expect(styleSwitch(1).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('pdf-stage').getAttribute('data-stage')).toBe(
      'translated',
    );
    expect(screen.getByTestId('pdf-pair').getAttribute('data-kind')).toBe(
      'group',
    );
    fireEvent.click(screen.getByTestId('pdf-pair-back'));
    const top = within(topStyleTabs()!).getAllByRole('tab');
    expect(top[1]!.getAttribute('aria-selected')).toBe('true');
  });

  it('둘 다 → [목록으로] → 맨 위 탭은 바꾸기 직전 문체 · 다른 항목을 열어도 둘 다', async () => {
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b2'));
    pickStyle(2);
    fireEvent.click(screen.getByTestId('pdf-pair-back'));
    const top = within(topStyleTabs()!).getAllByRole('tab');
    expect(top[0]!.getAttribute('aria-selected')).toBe('true');
    expect(boxes()).toHaveLength(5);
    fireEvent.click(box('p12-b1'));
    expect(sides().map(styleOf)).toEqual(['A', 'B']);
  });

  it('R1: 목록 탭 [검수 이슈]는 맨 위 문체 탭을 바꿔도 그대로', async () => {
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    openIssueTab();
    expect(listTab(1).getAttribute('aria-selected')).toBe('true');
    fireEvent.mouseDown(within(topStyleTabs()!).getAllByRole('tab')[1]!, {
      button: 0,
    });
    await waitFor(() => expect(boxes()).toHaveLength(3), WAIT);
    expect(listTab(1).getAttribute('aria-selected')).toBe('true');
    expect(listTab(0).getAttribute('aria-selected')).toBe('false');
    expect(screen.getByTestId('pdf-issue-tab')).toBeTruthy();
    fireEvent.mouseDown(within(topStyleTabs()!).getAllByRole('tab')[0]!, {
      button: 0,
    });
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(listTab(1).getAttribute('aria-selected')).toBe('true');
    expect(screen.getAllByTestId('pdf-issue-group')).toHaveLength(2);
  });

  it('둘 다 · 표: 격자 셋(원문 · A · B) 각각 가로 스크롤 상자 안 · 고른 칸은 셋 다 강조', async () => {
    const layout = layoutOf({ compare: true }) as Json & {
      variants: (Json & { units: Json[] })[];
    };
    layout.variants[1]!.units[1] = {
      tag: 'TABLE 1',
      page: 12,
      level: 'cell',
      translations: null,
      cells: [{ row: 0, col: 0, text: 'B category' }],
    };
    draw(serverOf(layout));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-t1:r0c0'));
    pickStyle(2);
    const grids = [
      screen.getByTestId('pdf-pair-source-grid'),
      ...screen.getAllByTestId('pdf-pair-translation-grid'),
    ];
    expect(grids).toHaveLength(3);
    expect(
      screen
        .getAllByTestId('pdf-pair-translation-grid')
        .map((grid) =>
          grid.closest('[data-style]')!.getAttribute('data-style'),
        ),
    ).toEqual(['A', 'B']);
    for (const grid of grids) {
      expect(grid.parentElement!.getAttribute('data-testid')).toBe(
        'pdf-table-scroll',
      );
      expect(grid.querySelectorAll('td[data-on]')).toHaveLength(1);
    }
    expect(grids[2]!.querySelector('td[data-on]')!.textContent).toBe(
      'B category',
    );
  });

  it('둘 다 · 다른 문체에 그 unit 이 없으면 그 칸에 한 줄', async () => {
    const layout = layoutOf({ compare: true }) as Json & {
      variants: (Json & { units: Json[] })[];
    };
    layout.variants[1]!.units.splice(2, 1);
    draw(serverOf(layout));
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b9'));
    pickStyle(2);
    expect(sides().map(styleOf)).toEqual(['A', 'B']);
    expect(
      within(sides()[1]! as HTMLElement).getByTestId('pdf-pair-no-same')
        .textContent,
    ).toBe(words.pair.noSame);
    expect(
      within(sides()[0]! as HTMLElement).queryByTestId('pdf-pair-no-same'),
    ).toBeNull();
  });
});

describe('머리글·꼬리말 상세 안내 줄 · TRW10', () => {
  const onlyLines = () => screen.queryAllByTestId('pdf-pair-source-only');
  const textCount = () =>
    within(pairs()).getAllByText(words.pair.sourceOnly).length;
  const openFooter = async (layout: Json) => {
    draw(serverOf(layout));
    await waitFor(() => expect(box('p12-b9')).toBeTruthy(), WAIT);
    fireEvent.click(box('p12-b9'));
  };
  /** 견주기 layout 에서 B 의 머리글·꼬리말만 뺀 것. */
  const noFooterInB = (): Json => {
    const layout = layoutOf({ compare: true }) as Json & {
      variants: { units: { level: string }[] }[];
    };
    const b = layout.variants[1]!;
    b.units = b.units.filter((unit) => unit.level !== 'source_only');
    return layout;
  };

  it('견주기 A·B: 빈 「번역」 자리에 회색 한 줄 · 맨 아래 note 0 · 번역 글 0', async () => {
    await openFooter(layoutOf({ compare: true }));
    for (const style of [0, 1] as const) {
      pickStyle(style);
      const lines = onlyLines();
      expect(lines).toHaveLength(1);
      expect(lines[0]!.textContent).toBe(words.pair.sourceOnly);
      expect(lines[0]!.className).toContain('text-text-tertiary');
      expect(lines[0]!.className).toContain('text-style-pre-caption-03');
      expect(within(pairs()).getByText(words.pair.translation)).toBeTruthy();
      expect(screen.getByTestId('pdf-style-switch')).toBeTruthy();
      expect(textCount()).toBe(1);
      expect(screen.queryByTestId('pdf-pair-translation')).toBeNull();
    }
  });

  it('둘 다: 문체 칸마다 한 줄(합 2) · 칸 밖 0', async () => {
    await openFooter(layoutOf({ compare: true }));
    pickStyle(2);
    const sides = screen.getAllByTestId('pdf-pair-style');
    expect(sides).toHaveLength(2);
    for (const side of sides)
      expect(within(side).getAllByTestId('pdf-pair-source-only')).toHaveLength(
        1,
      );
    expect(onlyLines()).toHaveLength(2);
    expect(textCount()).toBe(2);
  });

  it('둘 다 · 한 문체에만 그 항목: 없는 칸은 noSame 그대로 · 있는 칸만 한 줄', async () => {
    await openFooter(noFooterInB());
    pickStyle(2);
    const [a, b] = screen.getAllByTestId('pdf-pair-style') as [
      HTMLElement,
      HTMLElement,
    ];
    expect(within(a).getAllByTestId('pdf-pair-source-only')).toHaveLength(1);
    expect(within(a).queryByTestId('pdf-pair-no-same')).toBeNull();
    expect(within(b).getByTestId('pdf-pair-no-same').textContent).toBe(
      words.pair.noSame,
    );
    expect(within(b).queryByTestId('pdf-pair-source-only')).toBeNull();
  });

  /** 견주기 layout 에서 한 문체의 머리글·꼬리말 자리(unit 2)만 번역이 붙은 block 으로 바꾼 것. */
  const footerTranslatedIn = (style: 0 | 1): Json => {
    const layout = layoutOf({ compare: true }) as Json & {
      variants: { units: Json[] }[];
    };
    layout.variants[style]!.units[2] = {
      tag: 'BLOCK 9',
      page: 12,
      level: 'block',
      translations: ['Made-up footer line'],
    };
    return layout;
  };

  it('둘 다 · 같은 항목이 B 에서는 번역 있음: A 칸만 한 줄 · B 칸은 번역 글', async () => {
    await openFooter(footerTranslatedIn(1));
    pickStyle(2);
    const [a, b] = screen.getAllByTestId('pdf-pair-style') as [
      HTMLElement,
      HTMLElement,
    ];
    expect(within(a).getAllByTestId('pdf-pair-source-only')).toHaveLength(1);
    expect(within(a).queryByTestId('pdf-pair-translation')).toBeNull();
    expect(within(b).queryByTestId('pdf-pair-source-only')).toBeNull();
    expect(within(b).getByTestId('pdf-pair-translation').textContent).toBe(
      'Made-up footer line',
    );
  });

  it('둘 다 · 뒤집은 꼴(A 는 번역 · B 를 골라 들어감): A 칸은 번역 글 · B 칸만 한 줄', async () => {
    await openFooter(footerTranslatedIn(0));
    pickStyle(1);
    expect(onlyLines()).toHaveLength(1);
    pickStyle(2);
    const [a, b] = screen.getAllByTestId('pdf-pair-style') as [
      HTMLElement,
      HTMLElement,
    ];
    expect(within(a).queryByTestId('pdf-pair-source-only')).toBeNull();
    expect(within(a).getByTestId('pdf-pair-translation').textContent).toBe(
      'Made-up footer line',
    );
    expect(within(b).getAllByTestId('pdf-pair-source-only')).toHaveLength(1);
    expect(within(b).queryByTestId('pdf-pair-translation')).toBeNull();
  });

  it('한 문체 실행: 새 줄 0 · 「번역」 머리 줄 0 · 맨 아래 note 그대로', async () => {
    await openFooter(layoutOf());
    expect(onlyLines()).toHaveLength(0);
    expect(within(pairs()).queryByText(words.pair.translation)).toBeNull();
    expect(textCount()).toBe(1);
  });
});

// 밴드 TRW14 ③(TR-P05 c3 스펙): 상세 「번역」 머리 줄 오른쪽 끝 「번역 복사」 · 「둘 다」는 문체 칸마다 · 목록 꼴·원문 칸·번역 없는 짝 0.
describe('PdfView 상세 「번역 복사」 (TRW14 ③)', () => {
  const copyButtons = () =>
    screen
      .queryAllByRole('button')
      .filter((b) =>
        b.getAttribute('data-testid')?.startsWith('pdf-pair-copy'),
      );

  it('한 문체: 단추 하나(머리 줄 오른쪽 끝, 「번역 복사」) → copy 가 그 글로 · 성공 글 role=status · 약 2초 뒤 사라짐', async () => {
    const copy = vi.fn<(text: string) => Promise<void>>(async () => {});
    draw(serverOf(), null, copy);
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b2'));
    const button = screen.getByTestId('pdf-pair-copy');
    expect(copyButtons()).toEqual([button]);
    expect(button.getAttribute('aria-label')).toBe(words.pair.copy.label);
    expect(words.pair.copy.label).toBe('번역 복사');
    // 「번역」 머리 줄의 마지막 칸 안
    const row = button.closest('[data-testid="pdf-pair"] > div > div')!;
    expect(row.firstElementChild!.textContent).toBe(words.pair.translation);
    expect(row.lastElementChild!.contains(button)).toBe(true);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      fireEvent.click(button);
      await act(async () => {});
      expect(copy).toHaveBeenCalledTimes(1);
      expect(copy.mock.calls[0]![0]).toBe('Made-up text about cuts');
      const note = screen.getByTestId('pdf-pair-copy-note');
      expect(note.getAttribute('role')).toBe('status');
      expect(note.textContent).toBe(words.pair.copy.done);
      expect(words.pair.copy.done).toBe('번역을 복사했어요');
      await act(async () => {
        vi.advanceTimersByTime(2100);
      });
      expect(note.textContent).toBe('');
    } finally {
      vi.useRealTimers();
    }
  });

  it('copy 가 reject 하면 실패 글 「복사하지 못했어요」', async () => {
    const copy = vi.fn(async () => {
      throw new Error('fake');
    });
    draw(serverOf(), null, copy);
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b2'));
    fireEvent.click(screen.getByTestId('pdf-pair-copy'));
    await waitFor(() =>
      expect(screen.getByTestId('pdf-pair-copy-note').textContent).toBe(
        words.pair.copy.failed,
      ),
    );
    expect(words.pair.copy.failed).toBe('복사하지 못했어요');
  });

  it('둘 다: 문체 칸 머리마다 단추 하나(「번역 A 복사」·「번역 B 복사」) · 각자 제 문체 글만 · 머리 줄에는 0', async () => {
    const copy = vi.fn<(text: string) => Promise<void>>(async () => {});
    draw(serverOf(layoutOf({ compare: true })), null, copy);
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    fireEvent.click(box('p12-b2'));
    pickStyle(2);
    const [a, b] = screen.getAllByTestId('pdf-pair-style') as [
      HTMLElement,
      HTMLElement,
    ];
    expect(screen.queryByTestId('pdf-pair-copy')).toBeNull();
    const copyA = within(a).getByRole('button', {
      name: words.pair.copy.labelOf('A'),
    });
    const copyB = within(b).getByRole('button', {
      name: words.pair.copy.labelOf('B'),
    });
    expect(copyButtons()).toEqual([copyA, copyB]);
    fireEvent.click(copyB);
    fireEvent.click(copyA);
    await act(async () => {});
    expect(copy.mock.calls.map(([text]) => text)).toEqual([
      'B style merged',
      'Made-up text about cuts',
    ]);
  });

  it('목록 꼴(항목 안 고름)과 원문 칸에는 단추 0 · 번역 없는 짝(머리글·꼬리말)에도 0', async () => {
    draw(serverOf());
    await waitFor(() => expect(boxes()).toHaveLength(5), WAIT);
    expect(copyButtons()).toHaveLength(0);
    fireEvent.click(box('p12-b2'));
    expect(copyButtons()).toHaveLength(1);
    // 원문 칸(첫 묶음)에는 없다
    const source = screen.getAllByTestId('pdf-pair-source')[0]!;
    expect(
      source.closest('div')!.querySelector('[data-testid^="pdf-pair-copy"]'),
    ).toBeNull();
    cleanup();
    // 머리글·꼬리말(source_only) — 한 문체·「둘 다」 둘 다 0(Q8: 꺼진 단추도 아님)
    draw(serverOf(layoutOf({ compare: true })));
    await waitFor(() => expect(box('p12-b9')).toBeTruthy(), WAIT);
    fireEvent.click(box('p12-b9'));
    expect(screen.getByTestId('pdf-pair')).toBeTruthy();
    expect(copyButtons()).toHaveLength(0);
    pickStyle(2);
    expect(screen.getAllByTestId('pdf-pair-style')).toHaveLength(2);
    expect(copyButtons()).toHaveLength(0);
  });
});
