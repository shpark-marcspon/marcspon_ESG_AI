// PDF 보기(밴드 TRW6 ③, 6c v174 TR-P05·P05a). 라우터를 모른다 — 저장소·실행 id·문서 id·여는 함수(openPdf, 틀이 pdf.js 를 넘김)·콜백 props.
// - 셋 칸: 왼쪽 페이지 목록(「번역 N곳 · 이슈 N · 확인할 곳 N」·[페이지 전체]/[확인할 곳] 거름) · 가운데 쪽 그림(원본 PDF → PageCanvas) + 상자 ·
//   오른쪽 짝 칸(고른 상자의 원문 → 번역, 안 고르면 그 쪽 짝 차례대로). 견주기면 목록 꼴은 짝 칸 머리 탭 [A][B] ·
//   상세 꼴은 「번역」 머리 줄 전환 [A][B][둘 다](밴드 TRW8 ④ 개정 — sid:MARC-ENT-502 가 W10 「[둘 다] 없음」을 갈음. 「둘 다」 = 번역 A·B 칸을 쌓고
//   이슈를 문체마다 묶음 · 쪽 위 상자는 바꾸기 직전 문체 · 이전·다음 항목에도 그대로).
// - 표(밴드 TRW7 ③b-2, sid:MARC-ENT-488): 칸을 맞춘 표는 짝 하나 — 짝 칸에 원문·번역 격자 둘(GridTable). 쪽 위 칸 상자 누름 = 그 표 짝 + 칸(cell)
//   → 두 격자의 같은 칸 강조 · 「n행 m열」. 쪽 위 고른 상자는 늘 하나(isOn). [이전 짝]·[다음 짝]·짝 수는 표 단위.
// - 항목 칸(밴드 TRW8 ③~⑦·②, 디자인 74 처방): 화면 글은 「항목」(코드 이름 pair·testid 그대로). 고른 채 문체를 바꾸면 같은 unit 의 항목에 머묾(samePairIn) ·
//   상세 맨 위 한 줄 [← 목록으로] ‹ n / N › · 목록 꼴은 line 탭 [항목 N][검수 이슈 N](고른 탭은 쪽 넘김·문체 바꿈에도 그대로) · 목록 줄 끝 「이슈 N」 ·
//   짝 칸 표는 overflow-x-auto 상자 안에서 가로로 밂.
// - 셈은 model/pdfView(상자·짝·경고)·pdfAttach(이슈·용어 붙이기 — 서버 0, 글자로 찾음). 이슈·용어는 결과(useResult)의 고른 문체에서.
// - focus(요약 표 줄에서 왔을 때만): 그 쪽 · 그 짝을 고르고 머리 띠 한 줄. 다른 상자를 누르면 띠는 사라진다(판 TR-P05).
// - 상태: layout not_found(또는 거절 — 문체 없음) → 한 줄 + [← 결과 요약] · not_done → 한 줄 · failed → [다시 시도].
//   원본 PDF missing/failed → 뷰어 자리에만 「원본 PDF 를 불러오지 못했어요」(+[다시 시도] failed 만) — 쪽 목록·짝 칸은 그대로.
// 스크롤·움직임(밴드 TRW7 ②, 그린워싱 GW-05 꼴 — 그린워싱 땅은 가져오지 않고 옮겨 적음):
//   - 가운데(쪽) 칸·오른쪽(짝) 칸 sticky(STICKY_STYLE), 쪽 그림은 칸 안 pdf-page-scroll 에서 스크롤 · 짝 칸은 overflow-y-auto. 왼쪽 쪽 목록은 창 스크롤.
//   - 고른 상자 → 쪽 칸 안 가운데(fitInside — 고를 때·표에서 왔을 때·쪽 그림 크기 바뀔 때) · 쪽이 바뀌면 쪽 칸 맨 위 + 쪽 목록 지금 줄 nearest ·
//     고름이 바뀌면 짝 칸 맨 위 · 짝 칸 이슈·용어 줄 누름 → 그 밑줄 center. 부드러운 스크롤 없음(즉시 — 그린워싱대로).
//   - 움직임은 shared/ui/motion 의 기존 클래스만: 고른 상자 gw-m-mark(빛 blue-600, 다시 고르면 key 로 다시) · 「이슈 N」·띠 gw-m-rise · 짝 칸 몸 gw-m-fade.
import { Fragment, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode, RefObject } from 'react';

import {
  ArrowLeftIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import type { TranslationStore } from '../../../../entities/translation/api/index.ts';
import { TR_TEXT } from '../../../../entities/translation/config/text.ts';
import {
  useBatch,
  useLayout,
  useResult,
  useRunInfo,
  useRunPdf,
} from '../../../../entities/translation/hooks/index.ts';
import type { RunPdfState } from '../../../../entities/translation/hooks/index.ts';
import {
  PART_KEYS,
  batchViewOf,
  isPdfFlow,
} from '../../../../entities/translation/model/index.ts';
import type {
  LayoutVariantLabel,
  TranslationLayout,
} from '../../../../entities/translation/model/index.ts';
import {
  PartTabs,
  StatusBadge,
  useObjectUrl,
} from '../../../../entities/translation/ui/index.ts';
import type { PartTab } from '../../../../entities/translation/ui/index.ts';
import { Button, IconButton } from '../../../../shared/ui/button/index.ts';
import { LoadFailure } from '../../../../shared/ui/load-failure/index.ts';
import {
  LoadSkeleton,
  useDelayed,
} from '../../../../shared/ui/load-skeleton/index.ts';
// 움직임 클래스(gw-m-*)만 쓴다 — CSS 는 이 표면이 싣는다(shared/ui/motion/index.ts 머리).
import '../../../../shared/ui/motion/index.ts';
import {
  PageInfo,
  PageInfoIcon,
} from '../../../../shared/ui/page-info/index.ts';
import { RiskBadge } from '../../../../shared/ui/risk-badge/index.ts';
import {
  Tabs,
  TabsList,
  TabsTrigger,
} from '../../../../shared/ui/tabs/index.ts';
import { PageCanvas, usePdf } from '../../../../widgets/doc-viewer/index.ts';
import type { OpenPdf } from '../../../../widgets/doc-viewer/index.ts';
import {
  attachToPairs,
  copyTextOf,
  issuesOf,
  looseWarningsOf,
  missesOf,
  pairMarksOf,
  pdfPageLinesOf,
  pdfPageOf,
  pdfStageOf,
  pipeTableOf,
  samePairIn,
  variantLabelsOf,
} from '../../model/index.ts';
import type {
  MarkPiece,
  PdfBox,
  PdfCellAt,
  PdfGrid,
  PdfOpenFocus,
  PdfPageView,
  PdfPair,
  PdfWarning,
  QaIssue,
} from '../../model/index.ts';
import { PairCopy } from './PairCopy.tsx';
import type { CopyText } from './PairCopy.tsx';
import { fitScale, pageBoxOf, screenRectOf, settleWidth } from './boxRect.ts';

const words = TR_TEXT.pdfView;

/** 쪽 그림 배율의 위끝(1 포인트 = 1 CSS 픽셀 — A4 595 폭). 가운데 칸이 좁으면 칸 폭에 맞춰 줄인다(fitScale — 밴드 TRW6 ⑤). */
const SCALE = 1;

/** 판 변수 shadow normal(0 0 5px 2px rgba(0,0,0,.1) — 디자인 74 D4). 키트에 그림자 토큰이 없어(shared/ui/dialog DialogContent 머리) 임의 값. */
const SHADOW_NORMAL = 'shadow-[0_0_5px_2px_rgb(0_0_0/0.1)]';

/** 쪽 칸·짝 칸 sticky 의 위 틈(px)과 칸 높이. 그린워싱 GR/ReviewScreen.tsx:129-135 에서 옮겨 적음(74 답 Q7 — 같은 값). */
const STICKY_GAP = 24;
const STICKY_STYLE = {
  top: STICKY_GAP,
  maxHeight: `calc(100dvh - ${STICKY_GAP * 2}px)`,
};
/** 고른 상자를 쪽 칸 안으로 맞출 때 위에 더 두는 자리(⚠·「이슈 N」 — 그린워싱 TAG_ROOM 24 그대로). */
const TAG_ROOM = 24;

/** scroller 만 움직여 target 을 보이게(창은 움직이지 않는다 — 칸이 sticky). 그린워싱 GR/ReviewPagePane.tsx:511-523 fitInside 를 옮겨 적음:
 *  세로는 위 여유까지 다 보이지 않으면 가운데로, 가로는 왼쪽 끝이 칸 밖일 때만 왼쪽 끝을 여유 자리에. */
function fitInside(scroller: HTMLElement, target: HTMLElement) {
  const outer = scroller.getBoundingClientRect();
  const inner = target.getBoundingClientRect();
  const top = inner.top - TAG_ROOM;
  if (top < outer.top || inner.bottom > outer.bottom)
    scroller.scrollTop +=
      (top + inner.bottom) / 2 - (outer.top + outer.bottom) / 2;
  if (inner.left < outer.left || inner.left > outer.right - TAG_ROOM)
    scroller.scrollLeft += inner.left - outer.left - TAG_ROOM;
}

/** 칸의 안쪽 폭(CSS 픽셀). ResizeObserver 가 없는 곳(jsdom)이면 0 — fitScale 이 위끝 배율로 둔다.
 *  잰 폭은 settleWidth 로 거른다(밴드 TRW13 A — 창 스크롤바가 생겼다 사라지며 배율이 오가는 순환을 끊음). */
function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null) return;
    setWidth(element.clientWidth);
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() =>
      setWidth((held) => settleWidth(held, element.clientWidth)),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

export interface PdfViewProps {
  store: TranslationStore;
  runId: string;
  documentId: string;
  openPdf: OpenPdf;
  /** 요약 표 줄에서 왔을 때만(한 번 쓰는 표식은 틀이 지운다). null = 첫 쪽·고름 없음. */
  focus: PdfOpenFocus | null;
  /** 상세 「번역 복사」의 클립보드 쓰기(밴드 TRW14 ③ — app 층이 넣는다. 실패면 reject). */
  copy: CopyText;
  /** [← 결과 요약]. */
  onBack(): void;
  /** 파트 탭(밴드 TRW7 ③b W8): 묶음 열쇠와 다른 파트 실행으로 옮기기. 둘 다 있고 끝난 PDF 파트가 둘 이상일 때만 탭 줄. */
  batchKey?: string;
  onOpenPart?(runId: string): void;
}

export function PdfView({
  store,
  runId,
  documentId,
  openPdf,
  focus,
  copy,
  onBack,
  batchKey,
  onOpenPart,
}: PdfViewProps) {
  const { status, retry } = useLayout(store, runId);
  const late = useDelayed(status.state === 'loading');
  const back = (
    <Button
      variant="outlineGrey"
      shape="round"
      size="md"
      data-testid="pdf-back"
      onClick={onBack}
    >
      {`← ${words.back}`}
    </Button>
  );
  const head = (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <h2 className="m-0 text-style-pre-heading-01 text-text-primary">
        {words.open}
      </h2>
      {back}
    </div>
  );
  let body;
  if (status.state === 'loading') body = late ? <LoadSkeleton /> : null;
  else if (
    status.state === 'not_found' ||
    (status.state === 'ready' && status.layout.variants.length === 0)
  )
    body = <Notice testId="pdf-not-found" text={words.notFound} />;
  else if (status.state === 'not_done')
    body = <Notice testId="pdf-not-done" text={words.notDone} />;
  else if (status.state === 'failed')
    body = (
      <LoadFailure
        kind="failed"
        message={words.loadFailed}
        onRetry={retry}
        retryLabel={TR_TEXT.list.retry}
      />
    );
  else
    body = (
      // runId 로 몸만 새로(밴드 TRW8 ① — 파트 탭: 고름·쪽·문체를 새 파트에서 처음부터). 파트 탭 줄(PartSwitch)은 붙은 채.
      <Ready
        key={runId}
        store={store}
        runId={runId}
        documentId={documentId}
        openPdf={openPdf}
        layout={status.layout}
        focus={focus}
        copy={copy}
      />
    );
  return (
    <div data-screen="translation-pdf" className="flex flex-col gap-6">
      {head}
      {batchKey === undefined || onOpenPart === undefined ?
        body
      : <PartSwitch
          store={store}
          documentId={documentId}
          batchKey={batchKey}
          runId={runId}
          onOpenPart={onOpenPart}
        >
          {body}
        </PartSwitch>
      }
    </div>
  );
}

/**
 * 파트 탭(밴드 TRW7 ③b W8 — 판 v182 TR-P05 .e-tabs, 감독 답 Q1: 파트 탭만 · [전체] 없음). 묶음의 끝난 PDF 흐름 파트마다 탭 하나,
 * 누르면 그 파트 실행의 보기로(같은 경로 · 다른 runId — 부르는 쪽). 탭이 하나뿐이거나 묶음을 못 읽었으면 몸만(PartTabs 머리).
 */
function PartSwitch({
  store,
  documentId,
  batchKey,
  runId,
  onOpenPart,
  children,
}: {
  store: TranslationStore;
  documentId: string;
  batchKey: string;
  runId: string;
  onOpenPart(runId: string): void;
  children: ReactNode;
}) {
  const batch = useBatch(store, documentId, batchKey).status;
  const parts =
    batch.state === 'ready' ?
      batchViewOf(batch.batch)
        .parts.filter(
          (p) =>
            (p.state === 'done' || p.state === 'failed_partial') &&
            isPdfFlow(p.run.flowId),
        )
        .sort((a, b) => PART_KEYS.indexOf(a.part) - PART_KEYS.indexOf(b.part))
    : [];
  const current = parts.find((p) => p.runId === runId);
  if (current === undefined) return <>{children}</>;
  const tabs: PartTab[] = parts.map((p) => ({
    key: p.part,
    label: TR_TEXT.parts.names[p.part],
    state: p.state,
  }));
  return (
    <div data-testid="pdf-part-tabs">
      <PartTabs
        tabs={tabs}
        value={current.part}
        onChange={(key) => {
          const next = parts.find((p) => p.part === key);
          if (next !== undefined && next.runId !== runId)
            onOpenPart(next.runId);
        }}
        aria-label={TR_TEXT.run.tabsLabel}
      >
        {children}
      </PartTabs>
    </div>
  );
}

function Notice({ testId, text }: { testId: string; text: string }) {
  return (
    <PageInfo tone="important" icon={<PageInfoIcon />} data-testid={testId}>
      {text}
    </PageInfo>
  );
}

/** 이 쪽의 이슈·용어(고른 문체 결과에서). 결과를 못 읽었으면 빈 목록 — 상자·짝은 그대로. */
function pageRowsOf(
  result: ReturnType<typeof useResult>['status'],
  label: LayoutVariantLabel,
) {
  if (result.state !== 'ready' || result.result.status !== 'done')
    return {
      issues: [] as QaIssue[],
      misses: [] as ReturnType<typeof missesOf>,
    };
  const variant =
    result.result.variants.find((v) => v.label === label) ??
    result.result.variants[0];
  if (variant === undefined) return { issues: [], misses: [] };
  return { issues: issuesOf(variant).issues, misses: missesOf(variant) };
}

function Ready({
  store,
  runId,
  documentId,
  openPdf,
  layout,
  focus,
  copy,
}: {
  store: TranslationStore;
  runId: string;
  documentId: string;
  openPdf: OpenPdf;
  layout: TranslationLayout;
  focus: PdfOpenFocus | null;
  copy: CopyText;
}) {
  const labels = variantLabelsOf(layout);
  const pages = layout.pages.map((each) => each.page);
  // 표식은 요약에서 고른 문체로 센 자리 — 그 문체가 layout 에 있으면 그 문체로 열고, 없으면 첫 문체·고름 0(다른 문체의 짝을 고르지 않게).
  const sameStyle = focus !== null && labels.includes(focus.label);
  const [label, setLabel] = useState<LayoutVariantLabel>(
    sameStyle ? focus.label : labels[0]!,
  );
  const [page, setPage] = useState<number>(
    focus !== null && pages.includes(focus.page) ? focus.page : pages[0]!,
  );
  const [selected, setSelected] = useState<number | null>(
    sameStyle && pages.includes(focus.page) ? focus.pair : null,
  );
  /** 고른 표 짝 안의 칸(쪽 위 칸 상자를 눌렀을 때만 — 밴드 TRW7 ③b-2, sid:MARC-ENT-488). 짝을 바꾸면 비운다. */
  const [cell, setCell] = useState<PdfCellAt | null>(null);
  const [banner, setBanner] = useState(focus?.from ?? null);
  /** 목록 꼴의 탭(밴드 TRW8 ⑥). 쪽 넘김·문체 바꿈·상세 다녀옴에도 그대로 — 이슈를 쪽마다 훑는 흐름. */
  const [listTab, setListTab] = useState<ListTab>('items');
  /** 상세의 「둘 다」(밴드 TRW8 ④ 개정 — sid:MARC-ENT-502). label 은 바꾸기 직전 A·B 그대로(쪽 위 상자·목록은 label) · 이전·다음·목록 다녀옴에도 그대로. */
  const [both, setBoth] = useState(false);
  const [filter, setFilter] = useState<'all' | 'checks'>(
    focus?.filter ?? 'all',
  );
  const result = useResult(store, runId).status;
  const pdf = useRunPdf(store, documentId);
  const info = useRunInfo(store, runId).status;
  const partName =
    info.state === 'ready' && info.info.part !== null ?
      TR_TEXT.parts.names[info.info.part]
    : null;

  /** 이 쪽을 한 문체로 본 것(쪽 그림·목록은 label · 「둘 다」 상세는 문체마다). */
  const sideOf = (each: LayoutVariantLabel): PageSide => {
    const sideRows = pageRowsOf(result, each);
    const sideView = pdfPageOf(layout, each, page);
    const issues = sideRows.issues.filter((issue) => issue.page === page);
    const misses = sideRows.misses.filter((miss) => miss.page === page);
    return {
      view: sideView,
      issues,
      misses,
      attached: attachToPairs(sideView.pairs, {
        issues: issues.map((issue) => issue.span),
        misses: misses.map((miss) => miss.ko),
      }),
    };
  };
  const rows = pageRowsOf(result, label);
  const lines = pdfPageLinesOf(layout, label);
  const {
    view,
    issues: pageIssues,
    misses: pageMisses,
    attached,
  } = sideOf(label);
  const countOf = (pair: number) => {
    const found = attached.byPair.get(pair);
    return found === undefined ? 0 : found.issues.length + found.misses.length;
  };
  const issueCount = (at: number) =>
    rows.issues.filter((issue) => issue.page === at).length +
    rows.misses.filter((miss) => miss.page === at).length;
  const shownLines = lines.filter(
    (line) => filter === 'all' || line.checks > 0,
  );
  const checksTotal = lines.reduce((sum, line) => sum + line.checks, 0);
  const at = pages.indexOf(page);
  /** 고를 때마다 늘어난다(같은 상자를 다시 골라도) — 상자 맞춤·gw-m-mark 를 다시 하는 열쇠. */
  const [pick, setPick] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pairsRef = useRef<HTMLElement>(null);
  const navRef = useRef<HTMLElement>(null);
  // 쪽이 바뀌면(처음 그릴 때는 아님) 쪽 칸 맨 위 + 쪽 목록 지금 줄을 창 안으로(목록은 창 스크롤).
  const shownPage = useRef(page);
  useLayoutEffect(() => {
    if (shownPage.current === page) return;
    shownPage.current = page;
    if (scrollRef.current !== null) scrollRef.current.scrollTop = 0;
    navRef.current
      ?.querySelector<HTMLElement>(`button[data-page="${page}"]`)
      ?.scrollIntoView?.({ block: 'nearest' });
  }, [page]);
  // 고름·쪽·문체가 바뀌면 짝 칸 맨 위로.
  useLayoutEffect(() => {
    if (pairsRef.current !== null) pairsRef.current.scrollTop = 0;
  }, [selected, pick, page, label]);

  const choose = (pair: number | null, at: PdfCellAt | null = null) => {
    setSelected(pair);
    setCell(pair === null ? null : at);
    setBanner(null);
    if (pair !== null) setPick((count) => count + 1);
  };
  const goPage = (next: number) => {
    setPage(next);
    setSelected(null);
    setCell(null);
    setBanner(null);
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="m-0 text-style-pre-body-06 text-text-secondary">
        {words.lead}
      </p>
      {banner !== null && (
        <PageInfo
          tone="caution"
          icon={<PageInfoIcon />}
          data-testid="pdf-from-table"
          className="gw-m-rise"
        >
          {words.fromTable(banner.where, banner.type)}
        </PageInfo>
      )}
      <div className="grid grid-cols-[220px_minmax(0,1fr)_380px] items-start gap-4">
        <nav
          ref={navRef}
          aria-label={words.open}
          className="flex flex-col overflow-hidden rounded-dialog bg-background-primary"
        >
          <div className="flex gap-2 border-0 border-b border-solid border-border-quaternary p-4">
            <FilterButton
              on={filter === 'all'}
              onClick={() => setFilter('all')}
              text={words.filters.all(lines.length)}
            />
            <FilterButton
              on={filter === 'checks'}
              onClick={() => setFilter('checks')}
              text={words.filters.checks(checksTotal)}
            />
          </div>
          {partName !== null && pages.length > 0 && (
            <p
              data-testid="pdf-page-group"
              className="m-0 bg-background-secondary px-4 pb-1.5 pt-2.5 text-[12px] font-bold leading-[1.4] text-text-tertiary"
            >
              {words.group(partName, pages[0]!, pages[pages.length - 1]!)}
            </p>
          )}
          <ul className="m-0 flex list-none flex-col p-0">
            {shownLines.map((line) => {
              const issues = issueCount(line.page);
              const text = [
                line.imageOnly ?
                  words.pageLine.imageOnlyOnly
                : words.pageLine.placesOnly(line.places),
                ...(issues > 0 ? [words.pageLine.issues(issues)] : []),
                ...(line.checks > 0 ?
                  [words.pageLine.checks(line.checks)]
                : []),
                ...(line.only !== null ? [words.only(line.only)] : []),
              ].join(' · ');
              const current = line.page === page;
              // 판 .tp-pg — 두 줄(쪽 · 셈). 줄 사이 빈칸은 글을 이어 읽게(「12페이지 번역 8곳 · …」) 남긴다.
              return (
                <li key={line.page}>
                  <button
                    type="button"
                    data-page={line.page}
                    aria-current={current ? 'page' : undefined}
                    className={cn(
                      'flex w-full cursor-pointer flex-col gap-0.5 border-0 border-b border-l-[3px] border-solid border-b-border-quaternary border-l-transparent bg-transparent px-4 py-2.5 text-left',
                      current &&
                        'border-l-text-secondary bg-background-secondary',
                    )}
                    onClick={() => goPage(line.page)}
                  >
                    <span className="flex items-center justify-between gap-2 text-[14px] font-semibold leading-[1.5] text-text-primary">
                      {words.pageLine.title(line.page)}
                      {line.checks > 0 && (
                        <span
                          data-testid="page-check-dot"
                          aria-hidden
                          className="size-2 shrink-0 rounded-full bg-support-orange"
                        />
                      )}
                    </span>{' '}
                    <span className="text-[12px] leading-[1.4] text-text-tertiary">
                      {text}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <section
          data-testid="pdf-page-pane"
          className="sticky flex min-w-0 flex-col gap-3 rounded-dialog bg-background-primary p-4"
          style={STICKY_STYLE}
        >
          <div className="flex items-center justify-between gap-3">
            <h3
              data-testid="pdf-page-title"
              className="m-0 flex items-center gap-2 text-[16px] font-bold leading-[1.4] text-text-primary"
            >
              {words.pageTitle(page)}
              {partName !== null && (
                <StatusBadge look="grey">{partName}</StatusBadge>
              )}
            </h3>
            <div className="flex items-center gap-2">
              <span
                data-testid="pdf-page-of"
                className="text-style-pre-body-06 tabular-nums text-text-tertiary"
              >
                {words.pageOf(page, pages.length)}
              </span>
              <Button
                variant="outlineGrey"
                shape="round"
                size="sm"
                disabled={at <= 0}
                onClick={() => goPage(pages[at - 1]!)}
              >
                {words.prev}
              </Button>
              <Button
                variant="outlineGrey"
                shape="round"
                size="sm"
                disabled={at >= pages.length - 1}
                onClick={() => goPage(pages[at + 1]!)}
              >
                {words.next}
              </Button>
            </div>
          </div>
          <Legend />
          {view.imageOnly && (
            <PageInfo
              tone="important"
              icon={<PageInfoIcon />}
              data-testid="pdf-image-only"
            >
              {words.imageOnly}
            </PageInfo>
          )}
          {/* 쪽 그림은 이 칸 안에서 스크롤한다(남은 높이를 채움). 판 .tp-page — tertiary 바탕 · 안쪽 여백 24 = 상자 밖 ⚠·「이슈 N」 자리(가로 스크롤이 생기지 않게).
              scrollbar-gutter stable: 스크롤바 자리를 늘 비워 둬 칸 폭이 스크롤바와 무관(밴드 TRW13 A — 가로 쪽에서 스크롤바 생김·사라짐 ↔ 배율 순환) */}
          <div
            ref={scrollRef}
            data-testid="pdf-page-scroll"
            className="min-h-0 flex-1 overflow-auto rounded-component bg-background-tertiary p-6 [scrollbar-gutter:stable]"
          >
            <PdfPane
              pdf={pdf.status}
              onRetry={pdf.retry}
              openPdf={openPdf}
              view={view}
              selected={selected}
              cell={cell}
              pick={pick}
              scrollRef={scrollRef}
              countOf={countOf}
              onSelect={choose}
            />
          </div>
          {view.unplaced.length > 0 && (
            <details
              data-testid="pdf-unplaced"
              className="text-style-pre-body-06"
            >
              <summary className="cursor-pointer text-text-secondary">
                {words.unplaced(view.unplaced.length)}
              </summary>
              <ol className="m-0 mt-2 flex flex-col gap-1 pl-5">
                {view.unplaced.map((text, n) => (
                  <li key={n}>{text}</li>
                ))}
              </ol>
            </details>
          )}
        </section>

        <PairPanel
          panelRef={pairsRef}
          copy={copy}
          pick={pick}
          layout={layout}
          labels={labels}
          label={label}
          onLabel={(next) => {
            // 고른 항목에 머문다(밴드 TRW8 ④): 새 문체 쪽에서 같은 unit(블록이면 같은 member 먼저)의 항목 · 표 칸은 같은 칸이 있을 때만. 못 찾으면 목록.
            const now = selected === null ? undefined : view.pairs[selected];
            const same =
              now === undefined ? null : (
                samePairIn(pdfPageOf(layout, next, page), now, cell)
              );
            setLabel(next);
            setSelected(same?.pair ?? null);
            setCell(same?.cell ?? null);
          }}
          both={both}
          onBoth={setBoth}
          sideOf={sideOf}
          view={view}
          selected={selected}
          cell={cell}
          onSelect={choose}
          attached={attached}
          pageIssues={pageIssues}
          pageMisses={pageMisses}
          countOf={countOf}
          listTab={listTab}
          onListTab={setListTab}
        />
      </div>
    </div>
  );
}

type ListTab = 'items' | 'issues';

/** 한 문체로 본 이 쪽: 항목·이 쪽 이슈·용어·붙인 자리. */
interface PageSide {
  view: PdfPageView;
  issues: QaIssue[];
  misses: ReturnType<typeof missesOf>;
  attached: ReturnType<typeof attachToPairs>;
}

/** 「둘 다」 번역 칸 하나(문체마다): 그 문체 쪽에서 같은 unit 의 항목(없으면 pair 없음) · 그 항목의 이슈·용어 · 자동 수정 단계. */
interface StyleSide {
  label: LayoutVariantLabel;
  pair: PdfPair | undefined;
  cell: PdfCellAt | null;
  issues: readonly QaIssue[];
  misses: ReturnType<typeof missesOf>;
  stage: 'autofix' | 'translated' | null;
}

const BOTH = 'both';

function FilterButton({
  on,
  onClick,
  text,
}: {
  on: boolean;
  onClick(): void;
  text: string;
}) {
  return (
    <Button
      variant={on ? 'solidBlack' : 'outlineGrey'}
      shape="round"
      size="sm"
      aria-pressed={on}
      onClick={onClick}
    >
      {text}
    </Button>
  );
}

/** 뷰어 자리: 원본 PDF 상태 → 쪽 그림 + 상자. */
function PdfPane({
  pdf,
  onRetry,
  ...rest
}: {
  pdf: RunPdfState;
  onRetry(): void;
} & PageProps) {
  if (pdf.state === 'loading') return <LoadSkeleton />;
  if (pdf.state !== 'ready')
    return (
      <div
        data-testid="pdf-file-failed"
        className="flex flex-col items-start gap-3 rounded-lg border border-border-primary p-6"
      >
        <p className="m-0 text-style-pre-body-05 text-text-secondary">
          {words.pdfFailed}
        </p>
        {pdf.state === 'failed' && (
          <Button
            variant="outlineGrey"
            shape="round"
            size="sm"
            onClick={onRetry}
          >
            {words.retry}
          </Button>
        )}
      </div>
    );
  return <PdfFile file={pdf.file} {...rest} />;
}

interface PageProps {
  openPdf: OpenPdf;
  view: PdfPageView;
  selected: number | null;
  /** 고른 표 칸(없으면 null). */
  cell: PdfCellAt | null;
  /** 고름 열쇠(Ready 의 pick). */
  pick: number;
  /** 쪽 칸 스크롤 칸(pdf-page-scroll). */
  scrollRef: RefObject<HTMLDivElement>;
  countOf(pair: number): number;
  onSelect(pair: number | null, cell?: PdfCellAt | null): void;
}

function PdfFile({ file, ...rest }: { file: File } & PageProps) {
  const url = useObjectUrl(file);
  // 파일이 바뀌면 key 로 새로 연다(useObjectUrl 머리).
  return url === null ? null : <PdfPage key={url} url={url} {...rest} />;
}

function PdfPage({
  url,
  openPdf,
  view,
  selected,
  cell,
  pick,
  scrollRef,
  countOf,
  onSelect,
}: { url: string } & PageProps) {
  const loaded = usePdf(url, openPdf);
  const fit = useWidth();
  // 쪽 그림·상자는 같은 배율(상자 좌표 셈 screenRectOf 그대로 — R10). 쪽 그림은 테두리 없이 그림자(판 .tp-sheet)라 칸 폭 그대로.
  const scale = fitScale(fit.width, view.width, SCALE);
  return (
    <div ref={fit.ref} data-testid="pdf-page-frame" className="w-full min-w-0">
      {loaded.state === 'loading' ?
        <LoadSkeleton />
      : loaded.state === 'error' ?
        <p
          data-testid="pdf-file-failed"
          className="m-0 text-style-pre-body-05 text-text-secondary"
        >
          {words.pdfFailed}
        </p>
      : <PageImage
          pdf={loaded.pdf}
          scale={scale}
          view={view}
          selected={selected}
          cell={cell}
          pick={pick}
          scrollRef={scrollRef}
          countOf={countOf}
          onSelect={onSelect}
        />
      }
    </div>
  );
}

function PageImage({
  pdf,
  scale,
  view,
  selected,
  cell,
  pick,
  scrollRef,
  countOf,
  onSelect,
}: {
  pdf: Extract<ReturnType<typeof usePdf>, { state: 'ready' }>['pdf'];
  scale: number;
} & Omit<PageProps, 'openPdf'>) {
  const size = pageBoxOf(view, scale);
  const sheetRef = useRef<HTMLDivElement>(null);
  // 고른 상자를 쪽 칸 안으로: 고를 때마다, 그리고 쪽 그림 크기가 정해질 때(캔버스는 그린 뒤에야 크기가 생긴다 — 그린워싱 GR/ReviewPagePane.tsx:336-350 꼴).
  useLayoutEffect(() => {
    const sheet = sheetRef.current;
    if (sheet === null || selected === null) return;
    const fit = () => {
      const scroller = scrollRef.current;
      const target = sheet.querySelector<HTMLElement>('[data-selected]');
      if (scroller === null || target === null) return;
      fitInside(scroller, target);
    };
    fit();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(fit);
    observer.observe(sheet);
    return () => observer.disconnect();
  }, [selected, cell, pick, view.page, scrollRef]);
  return (
    <div
      ref={sheetRef}
      data-testid="pdf-page"
      data-page={view.page}
      className={cn('relative mx-auto w-fit bg-white', SHADOW_NORMAL)}
      onClick={() => onSelect(null)}
    >
      <PageCanvas pdf={pdf} pageNumber={view.page} scale={scale} rotation={0} />
      {size !== null &&
        view.boxes.map((box) => (
          <BoxButton
            key={box.id}
            box={box}
            view={view}
            scale={scale}
            on={isOn(box, selected, cell)}
            pick={pick}
            // 칸 상자는 표 짝을 가리키지만 「이슈 N」은 표 테두리에만(칸마다 같은 수를 되풀이하지 않게).
            count={box.cell === undefined ? countOf(box.pair) : 0}
            onSelect={onSelect}
          />
        ))}
    </div>
  );
}

/** 고른 상자: 짝이 같고, 표 칸 상자면 그 칸을 골랐을 때만 · 표 테두리(칸 아님)는 칸을 안 골랐을 때만 — 쪽 위 고른 상자는 늘 하나. */
function isOn(box: PdfBox, selected: number | null, cell: PdfCellAt | null) {
  if (selected !== box.pair) return false;
  if (box.cell === undefined) return cell === null;
  return (
    cell !== null && cell.row === box.cell.row && cell.col === box.cell.col
  );
}

// 상자 꼴(밴드 TRW7 ①, 6c v182 TR-P05 .bx-*) — outline 으로 그려 쪽 그림 위 자리를 옮기지 않는다.
//   block .bx-p · group .bx-g · table(칸을 못 맞춘 표) .bx-tw · table_border .bx-t · cell .bx-c · source_only .bx-hf · missing .bx-m.
const BOX_LOOK: Readonly<Record<PdfBox['look'], string>> = {
  block: 'outline outline-1 outline-offset-2 outline-blue-500',
  group: 'outline-dashed outline-[1.5px] outline-offset-4 outline-blue-500',
  table: 'outline outline-2 outline-offset-[3px] outline-green-600',
  table_border:
    'outline outline-[1.5px] outline-offset-[3px] outline-green-600',
  cell: 'outline outline-1 outline-offset-0 outline-green-600/60 rounded-[1px]',
  source_only: 'outline outline-1 outline-offset-2 outline-grey-300',
  missing:
    'outline-dashed outline-[1.5px] outline-offset-2 outline-support-error',
};
/** 상자 채움(밴드 TRW7 ③b — 디자인 74 처방 D8, sid:MARC-ENT-488): 상자 단추가 아니라 따로 칸에 칠하고 mix-blend-multiply 로 쪽 그림과 곱한다 —
 *  흰 종이만 물들고 검은 글자는 그대로(그린워싱 GR/ReviewPagePane.tsx:425-430 칠 칸 꼴). 알파는 판 값 그대로, 고른 상자만 불투명.
 *  「이슈 N」·⚠·gw-m-mark 빛은 칠 칸의 형제라 섞이지 않는다. 쌓임 맥락: 단추·쪽 그림 틀(pdf-page)에 z-index·transform·opacity 를 주지 않는다. */
const FILL_LOOK: Readonly<Partial<Record<PdfBox['look'], string>>> = {
  block: 'bg-blue-100/35',
  group: 'bg-blue-100/25',
  table: 'bg-green-100/70',
  source_only: 'bg-grey-100/80',
  missing: 'bg-red-100/35',
};
const SELECTED_FILL = 'bg-blue-100';
/** 그림 안 글(.bx-v). */
const VISUAL_LOOK =
  'outline outline-[1.5px] outline-offset-[3px] outline-grey-800';
/** 고른 상자(.bx-sel — 둘레 6px 는 blue-500 #175eff 16%). 채움은 SELECTED_FILL. */
const SELECTED_LOOK =
  'outline outline-2 outline-offset-2 outline-blue-600 shadow-[0_0_0_6px_rgb(23_94_255/0.16)]';

/** 범례 색 칸(.tp-sw · .sw-*). */
const SWATCHES = [
  ['block', 'border border-blue-500 bg-blue-100/35'],
  ['group', 'border-[1.5px] border-dashed border-blue-500'],
  ['cell', 'border-[1.5px] border-green-600'],
  ['table', 'border-2 border-green-600 bg-green-100'],
  ['visual', 'border-[1.5px] border-grey-800'],
  ['sourceOnly', 'border border-grey-300 bg-grey-100'],
  ['missing', 'border-[1.5px] border-dashed border-support-error'],
] as const;

/** 상자 범례 한 줄(판 .tp-legend — 그 쪽에 있는 종류와 상관없이 늘 전부). */
function Legend() {
  return (
    <ul
      data-testid="pdf-legend"
      aria-label={words.legend.label}
      className="m-0 flex list-none flex-wrap items-center gap-x-[9px] gap-y-1 p-0 text-[12px] leading-[1.4] text-text-tertiary"
    >
      {SWATCHES.map(([key, look]) => (
        <li
          key={key}
          data-legend={key}
          className="inline-flex items-center gap-1"
        >
          <i
            aria-hidden
            className={cn(
              'box-border inline-block h-[11px] w-[14px] rounded-[2px] border-solid',
              look,
            )}
          />
          {words.legend[key]}
        </li>
      ))}
      <li data-legend="check" className="inline-flex items-center gap-1">
        <b aria-hidden className="text-[13px] leading-none text-support-orange">
          ⚠
        </b>
        {words.legend.check}
      </li>
      <li data-legend="issue" className="inline-flex items-center gap-1">
        <b
          aria-hidden
          className="inline-block rounded-full bg-grey-900 px-1.5 text-[10px] leading-[1.5] text-white"
        >
          {words.legend.issueSample}
        </b>
        {words.legend.issue}
      </li>
    </ul>
  );
}

function BoxButton({
  box,
  view,
  scale,
  on,
  pick,
  count,
  onSelect,
}: {
  box: PdfBox;
  view: PdfPageView;
  scale: number;
  on: boolean;
  pick: number;
  count: number;
  onSelect(pair: number | null, cell?: PdfCellAt | null): void;
}) {
  const rect = screenRectOf(box.bbox, view, scale);
  if (rect === null) return null;
  const pair = view.pairs[box.pair]!;
  const kind = box.visual ? words.kinds.visual : words.kinds[pair.kind];
  const fill = on ? SELECTED_FILL : FILL_LOOK[box.look];
  return (
    <button
      type="button"
      data-box={box.id}
      data-look={box.look}
      data-selected={on || undefined}
      data-warned={box.warned || undefined}
      data-issues={count > 0 ? count : undefined}
      aria-label={words.boxLabel(view.page, box.pair + 1, kind)}
      aria-pressed={on}
      className={cn(
        'absolute cursor-pointer rounded-[2px] border-0 bg-transparent p-0',
        BOX_LOOK[box.look],
        box.visual && VISUAL_LOOK,
        on && SELECTED_LOOK,
      )}
      style={{
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
      }}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(box.pair, box.cell ?? null);
      }}
    >
      {fill !== undefined && (
        <span
          aria-hidden
          data-testid="pdf-box-fill"
          className={cn(
            'pointer-events-none absolute inset-0 rounded-[inherit] mix-blend-multiply',
            fill,
          )}
        />
      )}
      {on && (
        // 고른 상자가 나타남(gw-m-mark — 빛 색은 currentColor = 고른 선 blue-600, 74 답 Q6). 다시 고르면 key 로 다시 움직인다(그린워싱 key={box} 꼴).
        <span
          key={pick}
          aria-hidden
          data-testid="pdf-box-mark"
          className="gw-m-mark pointer-events-none absolute -inset-0.5 rounded-[2px] text-blue-600 outline outline-2 outline-blue-600"
        />
      )}
      {box.warned && (
        <span
          aria-hidden
          className="absolute -right-[11px] -top-[11px] grid size-[18px] place-items-center rounded-full bg-white text-[12px] font-bold leading-none text-support-orange shadow-[0_0_5px_2px_rgb(0_0_0/0.1)]"
        >
          ⚠
        </span>
      )}
      {count > 0 && (
        <span
          data-testid="pdf-box-badge"
          className="gw-m-rise absolute -bottom-[9px] -right-2 z-[1] whitespace-nowrap rounded-full bg-grey-900 px-[7px] py-px text-[9.5px] font-bold leading-[1.45] text-white shadow-[0_0_0_2px_#fff]"
        >
          {words.badge(count)}
        </span>
      )}
    </button>
  );
}

/** 짝 칸: 머리(문체 탭 · 단계 한 줄) · 경고 · 고른 짝 또는 그 쪽 짝 차례. */
function PairPanel({
  panelRef,
  copy,
  pick,
  layout,
  labels,
  label,
  onLabel,
  both,
  onBoth,
  sideOf,
  view,
  selected,
  cell,
  onSelect,
  attached,
  pageIssues,
  pageMisses,
  countOf,
  listTab,
  onListTab,
}: {
  panelRef: RefObject<HTMLElement>;
  copy: CopyText;
  pick: number;
  layout: TranslationLayout;
  labels: readonly LayoutVariantLabel[];
  label: LayoutVariantLabel;
  onLabel(label: LayoutVariantLabel): void;
  /** 상세의 「둘 다」. */
  both: boolean;
  onBoth(both: boolean): void;
  sideOf(label: LayoutVariantLabel): PageSide;
  view: PdfPageView;
  selected: number | null;
  cell: PdfCellAt | null;
  onSelect(pair: number | null): void;
  attached: ReturnType<typeof attachToPairs>;
  pageIssues: readonly QaIssue[];
  pageMisses: ReturnType<typeof missesOf>;
  /** 항목의 이슈 + 용어 수(쪽 위 상자 「이슈 N」과 같은 셈). */
  countOf(pair: number): number;
  listTab: ListTab;
  onListTab(tab: ListTab): void;
}) {
  const stage = pdfStageOf(layout, label);
  const pair = selected === null ? undefined : view.pairs[selected];
  // 경고: 고른 짝의 단위에 걸린 것 · 단위가 없는(쪽) 것 · 쪽에 매이지 않은 것.
  const warnings = [
    ...view.warnings.filter(
      (warning) =>
        warning.unit === null ||
        (pair !== undefined && warning.unit === pair.unit),
    ),
    ...looseWarningsOf(layout, label),
  ];
  const ordinalOf = (unit: number) =>
    view.pairs.findIndex((each) => each.unit === unit) + 1;
  const found = selected === null ? undefined : attached.byPair.get(selected);
  const issues = (found?.issues ?? []).map((n) => pageIssues[n]!);
  const misses = (found?.misses ?? []).map((n) => pageMisses[n]!);
  // 상세 꼴은 맨 위 탭 대신 「번역」 머리 줄 전환(밴드 TRW8 ④ 개정 — sid:MARC-ENT-502). 문체가 하나면 전환 0.
  const switcher =
    labels.length > 1 ?
      {
        labels,
        value: both ? BOTH : label,
        onChange: (next: string) => {
          onBoth(next === BOTH);
          if (next !== BOTH && next !== label)
            onLabel(next as LayoutVariantLabel);
        },
      }
    : undefined;
  const showBoth = both && switcher !== undefined && pair !== undefined;
  const sides: StyleSide[] | null =
    !showBoth ? null : (
      labels.map((each) => {
        if (each === label)
          return { label: each, pair, cell, issues, misses, stage };
        const side = sideOf(each);
        const same = samePairIn(side.view, pair, cell);
        const got =
          same === null ? undefined : side.attached.byPair.get(same.pair);
        return {
          label: each,
          pair: same === null ? undefined : side.view.pairs[same.pair],
          cell: same?.cell ?? null,
          issues: (got?.issues ?? []).map((n) => side.issues[n]!),
          misses: (got?.misses ?? []).map((n) => side.misses[n]!),
          stage: pdfStageOf(layout, each),
        };
      })
    );
  return (
    <aside
      ref={panelRef}
      data-testid="pdf-pairs"
      className="sticky flex flex-col gap-3 overflow-y-auto rounded-dialog bg-background-primary p-5"
      style={STICKY_STYLE}
    >
      {labels.length > 1 && pair === undefined && (
        <Tabs
          value={label}
          onValueChange={(next) => onLabel(next as LayoutVariantLabel)}
          variant="box"
        >
          <TabsList aria-label={TR_TEXT.run.styleTabsLabel}>
            {labels.map((each) => (
              <TabsTrigger key={each} value={each}>
                {words.styleOf(each)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      )}
      {stage !== null && sides === null && (
        <p
          data-testid="pdf-stage"
          data-stage={stage}
          className="m-0 flex items-center gap-1.5 rounded-component bg-background-secondary px-3 py-2 text-[13px] font-medium leading-[1.5] text-text-secondary"
        >
          {/* 판 .tp-stage — 자동 수정을 마쳤으면 success, 손대지 않은 글이면(.off) tertiary */}
          <StageCheck stage={stage} className="size-[15px]" />
          {words.stage[stage]}
        </p>
      )}
      {warnings.map((warning, n) => (
        <WarningLine
          key={n}
          warning={warning}
          ordinal={warning.unit === null ? null : ordinalOf(warning.unit)}
        />
      ))}
      {/* 짝 칸 몸: 고른 짝·쪽·문체가 바뀌면 새로 붙어 비친다(gw-m-fade — 그린워싱 상세 칸 꼴) */}
      <div
        key={`${label}:${sides === null ? 'one' : BOTH}:${view.page}:${selected ?? 'list'}:${pick}`}
        data-testid="pdf-pairs-body"
        className="gw-m-fade"
      >
        {pair === undefined ?
          <PairList
            view={view}
            onSelect={onSelect}
            attached={attached}
            pageIssues={pageIssues}
            pageMisses={pageMisses}
            stage={stage}
            countOf={countOf}
            tab={listTab}
            onTab={onListTab}
          />
        : <PairDetail
            view={view}
            index={selected!}
            pair={pair}
            cell={cell}
            issues={issues}
            misses={misses}
            stage={stage}
            onSelect={onSelect}
            switcher={switcher}
            sides={sides}
            copy={copy}
          />
        }
      </div>
    </aside>
  );
}

/** 자동 수정 단계 표(판 .tp-stage 의 체크) — 마쳤으면 success, 손대지 않은 글이면(.off) tertiary. */
function StageCheck({
  stage,
  className,
}: {
  stage: 'autofix' | 'translated';
  className: string;
}) {
  return (
    <CheckIcon
      aria-hidden
      className={cn(
        'shrink-0',
        className,
        stage === 'autofix' ? 'text-support-success' : 'text-text-tertiary',
      )}
    />
  );
}

/** 상세 「번역」 머리 줄 오른쪽 전환 `A | B | 둘 다`(밴드 TRW8 ④ 개정 — sid:MARC-ENT-502 · box 탭, 키트 box 높이 h-8). */
function StyleSwitch({
  labels,
  value,
  onChange,
}: {
  labels: readonly LayoutVariantLabel[];
  value: string;
  onChange(next: string): void;
}) {
  return (
    <Tabs value={value} onValueChange={onChange} variant="box">
      <TabsList
        data-testid="pdf-style-switch"
        aria-label={words.pair.styles.label}
      >
        {labels.map((each) => (
          <TabsTrigger key={each} value={each}>
            {words.pair.styles.one(each)}
          </TabsTrigger>
        ))}
        <TabsTrigger value={BOTH}>{words.pair.styles.both}</TabsTrigger>
      </TabsList>
    </Tabs>
  );
}

function WarningLine({
  warning,
  ordinal,
}: {
  warning: PdfWarning;
  ordinal: number | null;
}) {
  return (
    <p
      data-testid="pdf-warning"
      data-code={warning.code}
      className="m-0 rounded-md bg-background-brand px-3 py-2 text-style-pre-body-06 text-text-primary"
    >
      {`⚠ ${words.warnings[warning.code]}`}
      {warning.page !== null && (
        <span className="ml-2 text-text-tertiary">
          {words.warningAt(warning.page, ordinal)}
        </span>
      )}
      {warning.only !== null && (
        <span className="ml-2 text-text-tertiary">
          {words.only(warning.only)}
        </span>
      )}
    </p>
  );
}

const firstOf = (texts: readonly string[] | null) =>
  texts === null ? null : texts.join(' ');

/** 목록 꼴(밴드 TRW8 ⑥⑦): line 탭 [항목 N](목록만) · [검수 이슈 N](이 쪽 이슈·용어 전부 — 항목마다 묶고 맨 아래 「페이지 전체」). */
function PairList({
  view,
  onSelect,
  attached,
  pageIssues,
  pageMisses,
  stage,
  countOf,
  tab,
  onTab,
}: {
  view: PdfPageView;
  onSelect(pair: number): void;
  attached: ReturnType<typeof attachToPairs>;
  pageIssues: readonly QaIssue[];
  pageMisses: ReturnType<typeof missesOf>;
  stage: 'autofix' | 'translated' | null;
  countOf(pair: number): number;
  tab: ListTab;
  onTab(tab: ListTab): void;
}) {
  const issueTotal = pageIssues.length + pageMisses.length;
  return (
    <div className="flex flex-col gap-3">
      <Tabs
        value={tab}
        onValueChange={(next) => onTab(next as ListTab)}
        variant="line"
      >
        <TabsList data-testid="pdf-list-tabs">
          <TabsTrigger value="items">
            {words.pair.tabs.items(view.pairs.length)}
          </TabsTrigger>
          <TabsTrigger value="issues">
            {words.pair.tabs.issues(issueTotal)}
          </TabsTrigger>
        </TabsList>
      </Tabs>
      {tab === 'items' ?
        <ItemList view={view} onSelect={onSelect} countOf={countOf} />
      : <PageIssues
          view={view}
          onSelect={onSelect}
          attached={attached}
          pageIssues={pageIssues}
          pageMisses={pageMisses}
          stage={stage}
        />
      }
    </div>
  );
}

/** 항목 목록(밴드 TRW8 ⑦): 번호 칸 · 원문 한 줄/번역 한 줄 · 「이슈 N」(0 이면 없음). */
function ItemList({
  view,
  onSelect,
  countOf,
}: {
  view: PdfPageView;
  onSelect(pair: number): void;
  countOf(pair: number): number;
}) {
  return (
    <>
      <h3 className="m-0 text-style-pre-body-05 text-text-primary">
        {words.pair.listTitle(view.page, view.pairs.length)}
      </h3>
      <ol className="m-0 flex list-none flex-col gap-1 p-0">
        {view.pairs.map((pair, n) => {
          const count = countOf(n);
          return (
            <li key={n}>
              <button
                type="button"
                data-pair={n}
                data-issues={count > 0 ? count : undefined}
                className={cn(
                  'grid w-full cursor-pointer grid-cols-[20px_minmax(0,1fr)_auto] items-start gap-x-2 gap-y-0.5 rounded-component border-0 bg-transparent px-2 py-1.5 text-left text-style-pre-body-06 hover:bg-background-tertiary',
                  pair.translation === null && 'text-text-tertiary',
                )}
                onClick={() => onSelect(n)}
              >
                <span
                  data-testid="pdf-pair-number"
                  className="w-5 pt-px text-style-pre-caption-03 tabular-nums text-text-tertiary"
                >
                  {n + 1}
                </span>
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span
                    data-testid="pdf-pair-line-source"
                    className="line-clamp-1"
                  >
                    {pair.source.join(' ')}
                  </span>
                  {pair.translation !== null && (
                    <span className="line-clamp-1 text-text-secondary">
                      {firstOf(pair.translation)}
                    </span>
                  )}
                </span>
                {count > 0 ?
                  <span data-testid="pdf-pair-badge">
                    <StatusBadge look="grey">{words.badge(count)}</StatusBadge>
                  </span>
                : <span />}
              </button>
            </li>
          );
        })}
      </ol>
    </>
  );
}

/** 검수 이슈 탭(밴드 TRW8 ⑥): 항목 차례대로 「항목 k」 묶음(번호는 그 항목 상세와 같음 — 이슈 1..i, 용어 i+1..) · 줄 누름 → 그 항목 상세 ·
 *  맨 아래 항목에 못 붙은 「페이지 전체」(지금 꼴 — 줄은 단추 아님). 0건이면 한 줄. */
function PageIssues({
  view,
  onSelect,
  attached,
  pageIssues,
  pageMisses,
  stage,
}: {
  view: PdfPageView;
  onSelect(pair: number): void;
  attached: ReturnType<typeof attachToPairs>;
  pageIssues: readonly QaIssue[];
  pageMisses: ReturnType<typeof missesOf>;
  stage: 'autofix' | 'translated' | null;
}) {
  const wholeIssues = pageIssues.filter((_, n) =>
    attached.pageOnly.issues.includes(n),
  );
  const wholeMisses = pageMisses.filter((_, n) =>
    attached.pageOnly.misses.includes(n),
  );
  if (pageIssues.length + pageMisses.length === 0)
    return (
      <p
        data-testid="pdf-no-issues"
        className="m-0 text-style-pre-body-06 text-text-tertiary"
      >
        {words.pair.noIssues}
      </p>
    );
  return (
    <div data-testid="pdf-issue-tab" className="flex flex-col gap-4">
      {view.pairs.map((pair, n) => {
        const found = attached.byPair.get(n);
        if (
          found === undefined ||
          found.issues.length + found.misses.length === 0
        )
          return null;
        const issues = found.issues.map((at) => pageIssues[at]!);
        const misses = found.misses.map((at) => pageMisses[at]!);
        const fixed = pairMarksOf(pair, issues, misses, stage).fixed;
        return (
          <div
            key={n}
            data-testid="pdf-issue-group"
            data-pair={n}
            className="flex flex-col gap-1"
          >
            <span className="text-style-pre-caption-03 text-text-tertiary">
              {words.pair.itemOf(n + 1)}
            </span>
            {issues.length > 0 && (
              <IssueList
                testId="pdf-group-issues"
                issues={issues}
                fixed={fixed}
                onLine={() => onSelect(n)}
              />
            )}
            {misses.length > 0 && (
              <MissList
                testId="pdf-group-misses"
                misses={misses}
                from={issues.length + 1}
                onLine={() => onSelect(n)}
              />
            )}
          </div>
        );
      })}
      {(wholeIssues.length > 0 || wholeMisses.length > 0) && (
        <div data-testid="pdf-page-whole" className="flex flex-col gap-1">
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {words.pair.pageWhole}
          </span>
          {wholeIssues.length > 0 && (
            <IssueList
              testId="pdf-page-issues"
              title={words.pageIssuesTitle(wholeIssues.length)}
              issues={wholeIssues}
              note={words.pageIssuesNote}
            />
          )}
          {wholeMisses.length > 0 && (
            <MissList
              title={words.pageMissesTitle(wholeMisses.length)}
              misses={wholeMisses}
            />
          )}
        </div>
      )}
    </div>
  );
}

const NOTE_OF: Partial<Record<PdfPair['kind'], string>> = {
  group: words.pair.group,
  source_only: words.pair.sourceOnly,
};

function PairDetail({
  view,
  index,
  pair,
  cell,
  issues,
  misses,
  stage,
  onSelect,
  switcher,
  sides,
  copy,
}: {
  view: PdfPageView;
  index: number;
  pair: PdfPair;
  /** 표 짝 안에서 고른 칸(쪽 위 칸 상자를 눌렀을 때). */
  cell: PdfCellAt | null;
  issues: readonly QaIssue[];
  misses: ReturnType<typeof missesOf>;
  stage: 'autofix' | 'translated' | null;
  onSelect(pair: number | null): void;
  /** 「번역」 머리 줄 전환(문체가 둘 이상일 때만). */
  switcher:
    | {
        labels: readonly LayoutVariantLabel[];
        value: string;
        onChange(next: string): void;
      }
    | undefined;
  /** 「둘 다」면 문체마다 번역 칸(null = 한 문체). */
  sides: readonly StyleSide[] | null;
  copy: CopyText;
}) {
  const kind = pair.visual ? words.kinds.visual : words.kinds[pair.kind];
  const marks = pairMarksOf(pair, issues, misses, stage);
  const copyText = copyTextOf(pair);
  const rootRef = useRef<HTMLDivElement>(null);
  // 이슈·용어 줄 누름 → 짝 칸 안 그 번호의 밑줄로(못 찾은 줄은 밑줄이 없어 그대로). 즉시(behavior 기본값).
  // 「둘 다」면 번호가 문체마다 1 부터라 그 문체 칸(data-style) 안에서 찾는다.
  const toMark = (n: number, style?: LayoutVariantLabel) =>
    rootRef.current
      ?.querySelector<HTMLElement>(
        style === undefined ?
          `mark[data-n="${n}"]`
        : `[data-style="${style}"] mark[data-n="${n}"]`,
      )
      ?.scrollIntoView?.({ block: 'center' });
  // 표 짝 하나(밴드 TRW7 ③b-2, sid:MARC-ENT-488): 칸을 맞춘 표는 격자(grid) 둘, 못 맞춘 표(table level)는 글 그대로 + 안내.
  const grid = pair.grid;
  const cellCount = grid?.cells.length ?? 0;
  const tableWhole = pair.kind === 'table' && grid === undefined;
  const note =
    pair.visual ? words.pair.visual
    : tableWhole ? words.pair.tableWhole
    : NOTE_OF[pair.kind];
  return (
    <div
      ref={rootRef}
      data-testid="pdf-pair"
      data-kind={pair.kind}
      className="flex flex-col gap-3"
    >
      {/* 맨 위 한 줄(밴드 TRW8 ⑤): [← 목록으로] · ‹ n / N › — 긴 항목에서도 스크롤 없이 닿게 */}
      <div
        data-testid="pdf-pair-nav"
        className="flex items-center justify-between gap-2"
      >
        <Button
          variant="outlineGrey"
          shape="round"
          size="sm"
          data-testid="pdf-pair-back"
          onClick={() => onSelect(null)}
        >
          <ArrowLeftIcon aria-hidden className="size-4" />
          {words.pair.unselect}
        </Button>
        <div className="flex items-center gap-1">
          <IconButton
            size="md"
            aria-label={words.pair.prev}
            disabled={index <= 0}
            onClick={() => onSelect(index - 1)}
          >
            <ChevronLeftIcon aria-hidden />
          </IconButton>
          <span
            data-testid="pdf-pair-position"
            className="text-style-pre-caption-03 tabular-nums text-text-tertiary"
          >
            {words.pair.position(index + 1, view.pairs.length)}
          </span>
          <IconButton
            size="md"
            aria-label={words.pair.next}
            disabled={index >= view.pairs.length - 1}
            onClick={() => onSelect(index + 1)}
          >
            <ChevronRightIcon aria-hidden />
          </IconButton>
        </div>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-style-pre-body-05 text-text-primary">
          {kind}
          {grid !== undefined && cell !== null && (
            <span
              data-testid="pdf-pair-cell"
              className="ml-2 text-style-pre-caption-03 text-text-tertiary"
            >
              {words.cellAt(cell.row + 1, cell.col + 1)}
            </span>
          )}
          {cellCount > 0 && (
            <span className="ml-2 text-style-pre-caption-03 text-text-tertiary">
              {words.cellCount(cellCount)}
            </span>
          )}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-style-pre-caption-03 text-text-tertiary">
          {words.pair.source}
        </span>
        {grid !== undefined ?
          <GridTable
            grid={grid}
            side="source"
            cell={cell}
            testId="pdf-pair-source-grid"
          />
        : pair.source.map((text, n) => (
            <PairLine
              key={n}
              text={text}
              // 「둘 다」면 원문 밑줄 0 — 용어 번호가 문체마다 달라 한 원문에 둘을 겹치지 않는다(번호는 각 번역 칸·이슈 묶음).
              pieces={sides === null ? marks.source[n]! : [{ text }]}
              testId="pdf-pair-source"
              tone="source"
            />
          ))
        }
      </div>
      {(pair.kind !== 'source_only' || switcher !== undefined) && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-style-pre-caption-03 text-text-tertiary">
              {words.pair.translation}
            </span>
            {/* 「번역 복사」(밴드 TRW14 ③): 머리 줄 오른쪽 끝(전환 오른쪽). 「둘 다」면 문체 칸 머리마다, 번역 없는 짝에는 0(Q8). */}
            <span className="flex items-center gap-2">
              {switcher !== undefined && <StyleSwitch {...switcher} />}
              {sides === null && copyText !== null && (
                <PairCopy text={copyText} copy={copy} />
              )}
            </span>
          </div>
          {sides === null ?
            pair.kind === 'source_only' ?
              <SourceOnlyLine />
            : <TranslationBody
                pair={pair}
                cell={cell}
                pieces={marks.translation}
              />

          : sides.map((side) => (
              <div
                key={side.label}
                data-testid="pdf-pair-style"
                data-style={side.label}
                className="flex flex-col gap-1"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5 text-style-pre-caption-03 text-text-tertiary">
                    {words.pair.translationOf(side.label)}
                    {side.stage !== null && (
                      <span
                        data-testid="pdf-style-stage"
                        data-stage={side.stage}
                        className="inline-flex items-center gap-0.5"
                      >
                        <StageCheck stage={side.stage} className="size-3" />
                        {words.stage[side.stage]}
                      </span>
                    )}
                  </span>
                  {side.pair !== undefined &&
                    copyTextOf(side.pair) !== null && (
                      <PairCopy
                        text={copyTextOf(side.pair)!}
                        copy={copy}
                        label={words.pair.copy.labelOf(side.label)}
                        testId={`pdf-pair-copy-${side.label}`}
                      />
                    )}
                </div>
                {side.pair === undefined ?
                  <p
                    data-testid="pdf-pair-no-same"
                    className="m-0 text-style-pre-caption-03 text-text-tertiary"
                  >
                    {words.pair.noSame}
                  </p>
                : side.pair.kind === 'source_only' ?
                  <SourceOnlyLine />
                : <TranslationBody
                    pair={side.pair}
                    cell={side.cell}
                    pieces={
                      pairMarksOf(
                        side.pair,
                        side.issues,
                        side.misses,
                        side.stage,
                      ).translation
                    }
                  />
                }
              </div>
            ))
          }
        </div>
      )}
      {/* 견주기 실행의 머리글·꼬리말은 안내를 빈 「번역」 자리로(디자인 74 R4, 이슈 494) */}
      {note !== undefined &&
        !(note === words.pair.sourceOnly && switcher !== undefined) && (
          <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
            {note}
          </p>
        )}
      {sides !== null ?
        sides.map((side) => {
          const total = side.issues.length + side.misses.length;
          if (total === 0) return null;
          const fixed =
            side.pair === undefined ?
              []
            : pairMarksOf(side.pair, side.issues, side.misses, side.stage)
                .fixed;
          return (
            <div
              key={side.label}
              data-testid="pdf-style-issues"
              data-style={side.label}
              className="flex flex-col gap-1"
            >
              <h4 className="m-0 text-[13px] font-bold leading-[1.5] text-text-primary">
                {words.pair.issuesOf(side.label, total)}
              </h4>
              {side.issues.length > 0 && (
                <IssueList
                  testId="pdf-pair-issues"
                  issues={side.issues}
                  fixed={fixed}
                  onLine={(n) => toMark(n, side.label)}
                />
              )}
              {side.misses.length > 0 && (
                <MissList
                  misses={side.misses}
                  from={side.issues.length + 1}
                  onLine={(n) => toMark(n, side.label)}
                />
              )}
            </div>
          );
        })
      : <>
          {issues.length > 0 && (
            <IssueList
              testId="pdf-pair-issues"
              title={words.issuesTitle(issues.length)}
              issues={issues}
              fixed={marks.fixed}
              onLine={toMark}
            />
          )}
          {misses.length > 0 && (
            <MissList
              title={words.missesTitle(misses.length)}
              misses={misses}
              from={issues.length + 1}
              onLine={toMark}
            />
          )}
        </>
      }
    </div>
  );
}

/** 견주기 실행의 머리글·꼬리말: 빈 번역 자리의 안내 한 줄. */
function SourceOnlyLine() {
  return (
    <p
      data-testid="pdf-pair-source-only"
      className="m-0 text-style-pre-caption-03 text-text-tertiary"
    >
      {words.pair.sourceOnly}
    </p>
  );
}

/** 항목 번역 쪽 하나: 표 격자(칸을 맞춘 표) · 번역 없음 · 글 줄(밑줄 조각). 한 문체 상세와 「둘 다」의 문체 칸이 같이 쓴다. */
function TranslationBody({
  pair,
  cell,
  pieces,
}: {
  pair: PdfPair;
  cell: PdfCellAt | null;
  pieces: MarkPiece[][] | null;
}) {
  if (pair.kind === 'source_only') return null;
  if (pair.grid !== undefined)
    return (
      <GridTable
        grid={pair.grid}
        side="translation"
        cell={cell}
        testId="pdf-pair-translation-grid"
      />
    );
  if (pair.translation === null)
    return (
      <p
        data-testid="pdf-pair-none"
        className={cn(
          TEXT_CLASS,
          'border-[1.5px] border-dashed border-support-error text-support-error-accent',
        )}
      >
        {words.pair.none}
      </p>
    );
  return pair.translation.map((text, n) => (
    <PairLine
      key={n}
      text={text}
      pieces={pieces?.[n] ?? [{ text }]}
      testId="pdf-pair-translation"
      tone="translation"
    />
  ));
}

/** 번호 동그라미(판 .tp-mk — 이슈 검은 원 · 용어 흰 원 테두리). 밑줄 끝 번호와 같은 꼴. */
const NUMBER_LOOK = {
  issue: 'bg-grey-900 text-white',
  term: 'bg-white text-grey-900 shadow-[inset_0_0_0_1.5px_#1c1e21]',
} as const;

function NumberDot({ kind, n }: { kind: 'issue' | 'term'; n: number }) {
  return (
    <span
      aria-hidden
      className={cn(
        'mt-0.5 box-border inline-grid h-4 min-w-4 place-items-center self-start justify-self-start rounded-full px-[3px] text-[10px] font-bold leading-none',
        NUMBER_LOOK[kind],
      )}
    >
      {n}
    </span>
  );
}

const LINE_CLASS =
  'grid grid-cols-[22px_minmax(0,1fr)] gap-x-2 gap-y-1 border-0 border-t border-solid border-border-quaternary px-2 py-2.5 text-[13px] leading-[1.55] text-text-secondary';
const LINE_KEY_CLASS =
  'inline-block min-w-[52px] text-[12px] text-text-tertiary';

/** 목록 줄 하나: onLine 이 있으면(짝 칸) 누를 수 있는 단추 — 누르면 그 번호의 밑줄로. 없으면(쪽 전체 목록) 줄 그대로. */
function LineShell({
  n,
  onLine,
  children,
  ...attrs
}: {
  n: number;
  onLine: ((n: number) => void) | undefined;
  children: ReactNode;
} & Record<`data-${string}`, number>) {
  if (onLine === undefined)
    return (
      <li {...attrs} className={LINE_CLASS}>
        {children}
      </li>
    );
  return (
    <li {...attrs}>
      <button
        type="button"
        className={cn(
          LINE_CLASS,
          'w-full cursor-pointer border-x-0 border-b-0 bg-transparent text-left',
        )}
        onClick={() => onLine(n)}
      >
        {children}
      </button>
    </li>
  );
}

/** 검수 이슈 줄들(판 .tp-il): 번호 · 유형 · 심각도 · 「자동 수정에서 고쳤어요」 · 고칠 부분 / 제안 두 줄. */
function IssueList({
  testId,
  title,
  issues,
  fixed,
  note,
  onLine,
}: {
  testId: string;
  /** 없으면 머리 0(검수 이슈 탭의 항목 묶음 — 머리는 「항목 k」). */
  title?: string;
  issues: readonly QaIssue[];
  /** 줄 누름(번호) — 짝 칸만. */
  onLine?(n: number): void;
  /** 줄마다 「자동 수정에서 고쳤어요」(없으면 전부 아님). */
  fixed?: readonly boolean[];
  note?: string;
}) {
  return (
    <div data-testid={testId} className="flex flex-col gap-1">
      {title !== undefined && (
        <h4 className="m-0 text-[13px] font-bold leading-[1.5] text-text-primary">
          {title}
        </h4>
      )}
      <ol className="m-0 flex list-none flex-col p-0">
        {issues.map((issue, n) => (
          <LineShell key={n} n={n + 1} data-issue-line={n + 1} onLine={onLine}>
            <NumberDot kind="issue" n={n + 1} />
            <span className="flex flex-wrap items-center gap-1.5 font-semibold text-text-primary">
              {TR_TEXT.issues.types[issue.type]}
              <RiskBadge level={issue.severity} />
              {fixed?.[n] === true && (
                <span
                  data-testid="pdf-issue-fixed"
                  className="text-[12px] font-medium leading-[1.4] text-support-success"
                >
                  {words.issueLine.fixed}
                </span>
              )}
            </span>
            <span />
            <span data-testid="pdf-issue-span">
              <span className={LINE_KEY_CLASS}>{words.issueLine.span}</span>
              {issue.span}
            </span>
            <span />
            <span data-testid="pdf-issue-suggestion">
              <span className={LINE_KEY_CLASS}>
                {words.issueLine.suggestion}
              </span>
              {issue.suggestion}
            </span>
          </LineShell>
        ))}
      </ol>
      {note !== undefined && (
        <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
          {note}
        </p>
      )}
    </div>
  );
}

/** 용어집 미반영 줄들: 번호(이슈 다음부터 — 판 ①②) · 「국문 → 영문」 · 「번역에 지정한 영문이 없어요」. */
function MissList({
  testId = 'pdf-misses',
  title,
  misses,
  from = 1,
  onLine,
}: {
  testId?: string;
  /** 없으면 머리 0(검수 이슈 탭의 항목 묶음). */
  title?: string;
  misses: ReturnType<typeof missesOf>;
  /** 첫 줄 번호. */
  from?: number;
  /** 줄 누름(번호) — 짝 칸만. */
  onLine?(n: number): void;
}) {
  return (
    <div data-testid={testId} className="flex flex-col gap-1">
      {title !== undefined && (
        <h4 className="m-0 text-[13px] font-bold leading-[1.5] text-text-primary">
          {title}
        </h4>
      )}
      <ol className="m-0 flex list-none flex-col p-0">
        {misses.map((miss, n) => (
          <LineShell
            key={n}
            n={from + n}
            data-term-line={from + n}
            onLine={onLine}
          >
            <NumberDot kind="term" n={from + n} />
            <span className="font-semibold text-text-primary">
              {words.termLine.pair(miss.ko, miss.en)}
            </span>
            <span />
            <span className="text-[12px] text-text-tertiary">
              {words.termLine.note}
            </span>
          </LineShell>
        ))}
      </ol>
    </div>
  );
}

/** 밑줄 꼴(판 .tp-u 실선 · .tp-ug 점선) + 끝 번호(.tp-mk). 번호는 ::after 라 글(textContent)은 그대로다. */
const MARK_LOOK = {
  issue:
    'underline decoration-grey-900 decoration-2 underline-offset-4 after:bg-grey-900 after:text-white',
  term: 'underline decoration-grey-900 decoration-dashed decoration-[1.5px] underline-offset-4 after:bg-white after:text-grey-900 after:shadow-[inset_0_0_0_1.5px_#1c1e21]',
} as const;
const MARK_NUMBER =
  'bg-transparent text-inherit after:ml-[3px] after:box-border after:inline-grid after:h-4 after:min-w-4 after:place-items-center after:rounded-full after:px-[3px] after:align-[2px] after:text-[10px] after:font-bold after:leading-none after:content-[attr(data-n)]';

function PairText({ pieces }: { pieces: readonly MarkPiece[] }) {
  return pieces.map((piece, n) =>
    piece.mark === undefined ?
      <Fragment key={n}>{piece.text}</Fragment>
    : <mark
        key={n}
        data-mark={piece.mark.kind}
        data-n={piece.mark.n}
        className={cn(MARK_NUMBER, MARK_LOOK[piece.mark.kind])}
      >
        {piece.text}
      </mark>,
  );
}

/** 표 짝 격자 한쪽(원문 또는 번역 — 밴드 TRW7 ③b-2, sid:MARC-ENT-488). 두 격자는 같은 행·열 · 빈 칸은 비움 ·
 *  고른 칸은 두 격자에서 같은 자리를 강조(판 .tp-on — blue-100 + 왼쪽 3px blue-600). 꼴은 .tp-mtbl(PairTable)과 같음. */
function GridTable({
  grid,
  side,
  cell,
  testId,
}: {
  grid: PdfGrid;
  side: 'source' | 'translation';
  cell: PdfCellAt | null;
  testId: string;
}) {
  const at = new Map(
    grid.cells.map((each) => [`${each.row}:${each.col}`, each] as const),
  );
  const base =
    'min-w-[72px] border border-solid border-border-quaternary px-1.5 py-1 text-left align-top';
  return (
    <TableScroll>
      <table
        data-testid={testId}
        data-table-rows={grid.rows}
        data-table-cols={grid.cols}
        className={cn(
          'w-full border-collapse text-[12px] leading-[1.4]',
          side === 'translation' ? 'bg-blue-100/55' : 'bg-background-secondary',
        )}
      >
        <tbody>
          {Array.from({ length: grid.rows }, (_, row) => (
            <tr key={row}>
              {Array.from({ length: grid.cols }, (_, col) => {
                const found = at.get(`${row}:${col}`);
                const on =
                  cell !== null && cell.row === row && cell.col === col;
                return (
                  <td
                    key={col}
                    data-cell={`${row}:${col}`}
                    data-on={on || undefined}
                    className={cn(
                      base,
                      on &&
                        'bg-blue-100 shadow-[inset_3px_0_0_theme(colors.blue.600)]',
                    )}
                  >
                    {found === undefined ?
                      ''
                    : side === 'source' ?
                      found.source
                    : found.translation}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}

/** 짝 칸 표 감싸개(밴드 TRW8 ② — 디자인 74 TRW7 후속 2): 칸 수십 개 표는 칸 폭을 줄이지 않고 이 상자 안에서 가로로 민다(칸 최소 72 — 감독 답 Q5). */
function TableScroll({ children }: { children: ReactNode }) {
  return (
    <div data-testid="pdf-table-scroll" className="overflow-x-auto">
      {children}
    </div>
  );
}

/** pipe 꼴 표 글(판 .tp-mtbl). */
function PairTable({
  table,
  testId,
}: {
  table: NonNullable<ReturnType<typeof pipeTableOf>>;
  testId: string;
}) {
  const cell =
    'min-w-[72px] border border-solid border-border-quaternary px-1.5 py-1 text-left align-top';
  return (
    <TableScroll>
      <table
        data-testid={testId}
        data-table-rows={table.rows.length}
        data-table-cols={table.cols}
        className="w-full border-collapse text-[12px] leading-[1.4]"
      >
        <thead>
          <tr>
            {table.head.map((text, n) => (
              <th
                key={n}
                className={cn(cell, 'bg-background-secondary font-semibold')}
              >
                {text}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, r) => (
            <tr key={r}>
              {row.map((text, n) => (
                <td key={n} className={cell}>
                  {text}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}

const TEXT_CLASS =
  'm-0 rounded-component px-3 py-2.5 text-[14px] leading-[1.65] text-text-primary';

/** 짝 글 줄 하나: pipe 꼴 표면 표, 아니면 문단(밑줄 조각). */
function PairLine({
  text,
  pieces,
  testId,
  tone,
}: {
  text: string;
  pieces: readonly MarkPiece[];
  testId: string;
  tone: 'source' | 'translation';
}) {
  const table = pipeTableOf(text);
  if (table !== null)
    return <PairTable table={table} testId={`${testId}-table`} />;
  return (
    <p
      data-testid={testId}
      className={cn(
        TEXT_CLASS,
        tone === 'source' ?
          'bg-background-secondary'
        : 'whitespace-pre-line bg-blue-100/55',
      )}
    >
      <PairText pieces={pieces} />
    </p>
  );
}
