// GW-05 가운데 칸: 고른 문장의 쪽(밴드 FW2 ④, 시안 GW-05_r1 캔버스 v76, 발주서 덧붙임 1·2).
//   - 머리: 「n쪽」 + [이전 쪽] 「n / 전체」 [다음 쪽]. 쪽 이동은 이 칸 안의 상태다(문장을 고를 때마다 — 같은 문장이라도 — 그 문장의 쪽으로 돌아간다).
//   - PDF 는 실행의 문서(getRun → openDocumentPdf) → File 을 object URL 로 열어 문서 뷰어의 PageCanvas 로 그린다(썸네일과 같은 길).
//     PDF 가 없으면(목의 씨앗 문서) 쪽 그림 자리에 「미리보기를 열 수 없어요」 안내(지은 글 — 디자인 물을 것).
//   - position 이 있으면 바깥 상자(domain outerBox)를 등급 색 테두리로 얹고 상자 위에 등급 태그. 그 문장의 쪽을 볼 때만 얹는다.
//   - position 이 null 이면 미리보기 위에 회색 안내(GW_TEXT.review.positionMissing)를 띄우고 상자를 얹지 않는다(쪽 이동만).
//     한 결과 안에 두 꼴이 섞인다(덧붙임 1).
//   - 시안의 미리보기 아래 설명 글(「PDF 뷰어 자리 — …」)은 시안 메모라 옮기지 않는다(덧붙임 2).
// 미리보기 칸만 실패(밴드 LE1, sid:MARC-ENT-260 ②, 시안 CM-03 cm-cellfail): PDF 읽기 실패·pdf.js 열기 실패·쪽 그리기 실패 모두 칸 안 회색 상자
//   「미리보기를 열지 못했어요. 문장은 오른쪽에서 확인해 주세요」 + 작은 [다시 시도](useDocumentPdf.retry — 새 File 이라 object URL·pdf.js 를 다시 연다).
//   여는 중 글(previewLoading)은 그대로. PDF 가 없음(previewUnavailable)은 다시 해도 같으니 단추 없이 그대로.
//   실행·PDF 읽기가 없음(404, useDocumentPdf missing)도 같은 회색 안내에 단추 없음(밴드 LA1 ②, sid:MARC-ENT-260 ③).
// [다시 시도] 뒤 초점(밴드 LA1 ②, useRetryFocus): 또 실패면 새 [다시 시도], 읽혔으면(없음 포함) 칸 머리 h3(tabIndex -1).
//   pdf.js 열기·쪽 그리기 실패(OpenedPage)는 useDocumentPdf 가 ready 로 끝난 뒤라 다시 실패해도 초점은 h3 에 간다(맞추지 않는다).
// 배율은 칸 폭에 맞춘다(밴드 GFS1, sid:MARC-ISSUE-449 — 영문번역 TRW6 와 같은 셈 fitScale): min(1, 쪽 칸 안쪽 폭 ÷ 쪽 폭, 0.01 내림).
//   넓은 칸은 1 그대로(키우지 않음), 폭을 못 재면(ResizeObserver 없음 — jsdom) 1. 쪽 그림과 모든 상자가 같은 배율을 쓴다.
//   쪽 폭은 PdfHandle 이 내지 않아 그린 캔버스에서 잰다: renderPage 계약이 캔버스의 CSS 크기(쪽 크기 × 배율)를 정하므로
//   canvas.style.width ÷ 그 배율 = 쪽 폭(pt). 쪽을 넘겨 크기가 바뀌어도 다시 잰다.
//   상자 좌표는 pt(왼쪽 위 원점, 계약 shapes.py Position)라 배율을 곱하면 CSS px 다(회전 0 만).
// 같은 쪽 문장 상자와 역 포커싱(밴드 GP2, sid:MARC-ISSUE-341 — 사용자 10-23, 꼴은 디자인 6c 노트):
//   - 보는 쪽에 position 이 있는 목록의 문장(sentences — 거른 목록 그대로) 전부를 단추로 얹는다. 안 고른 상자는 등급 색 1px 테두리·채움 없음,
//     hover 는 같은 색 2px, focus-visible 은 거기에 2px #8B95A1 outline(offset 2). 고른 상자는 지금 꼴(highlight) 그대로 맨 위.
//   - 겹치면 작은 상자가 위, 크기가 같으면 목록에서 앞 문장이 위(z-index — DOM 차례는 목록 차례 그대로라 Tab 도 목록 차례).
//   - 상자를 누르면(또는 Tab·Enter) onPick. 고른 문장의 단추를 다시 누르면 아무 일 없음.
//   - 고른 상자가 쪽 칸(page-scroll) 밖이면 그 칸만 스크롤해 가운데로(창은 움직이지 않는다 — 칸이 sticky). 쪽 그림 크기가 바뀔 때도 다시 맞춘다.
import { useLayoutEffect, useRef, useState } from 'react';
import type { Ref, RefObject } from 'react';

import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CircleWarningIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type {
  Level,
  ResultItem,
} from '../../../entities/greenwash/model/index.ts';
import { RiskBadge } from '../../../entities/greenwash/ui/index.ts';
import type { RiskLevel } from '../../../entities/greenwash/ui/index.ts';
import { useObjectUrl } from '../../../entities/greenwash/ui/index.ts';
import { Button, IconButton } from '../../../shared/ui/button/index.ts';
import { useRetryFocus } from '../../../shared/ui/load-skeleton/index.ts';
import type { RetryPhase } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { PageCanvas, usePdf } from '../../../widgets/doc-viewer/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { useDocumentPdf } from '../hooks/index.ts';
import type { DocumentPdfState } from '../hooks/index.ts';
import { fitScale, outerBox } from '../model/index.ts';

type Box = readonly [number, number, number, number];

const words = GW_TEXT.reviewScreen;

/** 쪽 그림 배율의 위끝(1 포인트 = 1 CSS 픽셀). 쪽 칸이 좁으면 칸 폭에 맞춰 줄인다(fitScale — 밴드 GFS1). */
export const PREVIEW_SCALE = 1;

/** 문장 상자가 글자 둘레보다 사방으로 나가는 폭(포인트, 디자인 대조 C4). 위치 칸(highlight)의 자리·크기는 그대로다. */
const BOX_PAD = 4;

/** 고른 상자를 쪽 칸 안으로 맞출 때 위에 더 두는 자리(등급 태그 -top-6 = 24px). */
const TAG_ROOM = 24;

const RISK: Record<Level, RiskLevel> = { High: 'high', Mid: 'mid', Low: 'low' };

/** 상자 테두리·바탕(등급 색: High 빨강 · Mid 노랑 · Low 회색, 2026-10-16 사용자 결정). 바탕은 곱하기로 섞어 글자가 보이게. */
const BOX_LOOK: Record<Level, string> = {
  High: 'border-support-error-accent bg-support-error-subtle',
  Mid: 'border-support-yellow-dark bg-support-yellow-subtle',
  Low: 'border-text-tertiary bg-background-tertiary',
};
/** 안 고른 문장 상자의 테두리 색(BOX_LOOK 과 같은 border 토큰, 채움 없음 — 디자인 6c). */
const BOX_LINE: Record<Level, string> = {
  High: 'border-support-error-accent',
  Mid: 'border-support-yellow-dark',
  Low: 'border-text-tertiary',
};

/** 쪽 칸에 얹을 목록의 문장 하나(차례·보이는 등급·글·위치). */
export interface PaneSentence {
  index: number;
  level: Level;
  sentence: string;
  position: ResultItem['position'];
}

/** 쪽 위 문장 상자 하나(차례·등급·이름·바깥 상자). */
interface PageBox {
  index: number;
  level: Level;
  label: string;
  box: Box;
}

/** 상자가 나타날 때 빛나는 색(gw-m-mark 의 drop-shadow 가 currentColor 를 쓴다 — 밴드 GA1). */
const GLOW_LOOK: Record<Level, string> = {
  High: 'text-support-error-accent',
  Mid: 'text-support-yellow-dark',
  Low: 'text-text-tertiary',
};

export interface ReviewPagePaneProps {
  store: GreenwashStore;
  openPdf: OpenPdf;
  /** 실행 id(쪽 그림의 PDF 는 그 실행의 문서에서 — useDocumentPdf). */
  runId: string;
  /** 고른 문장과 그 열쇠(결과 items 의 차례). */
  item: ResultItem;
  /** 고를 때마다 바뀌는 열쇠(같은 문장을 다시 골라도 바뀐다). 바뀌면 쪽 이동을 버리고 그 문장의 쪽으로 돌아간다. */
  pickKey: string;
  /** 문서 전체 쪽 수(결과의 source.pageCount). */
  pageCount: number;
  /** 목록의 문장들(거른 목록 그대로). 보는 쪽에 위치가 있는 것을 상자로 얹는다. 없으면 고른 문장 하나만. */
  sentences?: readonly PaneSentence[];
  /** 고른 문장의 차례(sentences 안에서 고른 상자를 가린다). */
  currentIndex?: number;
  /** 상자를 눌러 문장을 고름(역 포커싱). 고른 문장이면 부르지 않는다. */
  onPick?(index: number): void;
}

export function ReviewPagePane({
  store,
  openPdf,
  runId,
  item,
  pickKey,
  pageCount,
  sentences = [],
  currentIndex,
  onPick,
}: ReviewPagePaneProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { status: pdf, retry: retryPdf } = useDocumentPdf(store, runId);
  const focus = useRetryFocus<HTMLHeadingElement>(PHASE[pdf.state]);
  const retry = focus.arm(retryPdf);
  // 쪽 이동은 고른 문장마다 새로 시작한다(다른 문장을 고르면 그 문장의 쪽).
  const [moved, setMoved] = useState<{ pickKey: string; page: number }>({
    pickKey,
    page: item.page,
  });
  const page = moved.pickKey === pickKey ? moved.page : item.page;
  const goTo = (next: number) => setMoved({ pickKey, page: next });
  const box =
    item.position !== null && item.position.page === page ?
      outerBox(item.position.boxes)
    : null;
  const others: PageBox[] = [];
  for (const sentence of sentences) {
    if (sentence.index === currentIndex) continue;
    if (sentence.position === null || sentence.position.page !== page) continue;
    const outer = outerBox(sentence.position.boxes);
    if (outer === null) continue;
    others.push({
      index: sentence.index,
      level: sentence.level,
      label: words.sentenceBox(page, sentence.level, sentence.sentence),
      box: outer,
    });
  }

  return (
    <div
      className="flex min-h-0 min-w-0 flex-1 flex-col gap-3"
      data-testid="review-page"
    >
      <div className="flex items-center justify-between gap-3">
        <h3
          ref={focus.doneRef}
          tabIndex={-1}
          className="m-0 text-style-pre-body-01 text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary"
          data-testid="page-heading"
        >
          {words.pageHeading(page)}
        </h3>
        <div className="flex items-center gap-2">
          <IconButton
            aria-label={words.prevPage}
            disabled={page <= 1}
            onClick={() => goTo(page - 1)}
          >
            <ChevronLeftIcon aria-hidden />
          </IconButton>
          <span
            className="text-style-pre-caption-03 tabular-nums text-text-tertiary"
            data-testid="page-of"
          >
            {words.pageOf(page, pageCount)}
          </span>
          <IconButton
            aria-label={words.nextPage}
            disabled={page >= pageCount}
            onClick={() => goTo(page + 1)}
          >
            <ChevronRightIcon aria-hidden />
          </IconButton>
        </div>
      </div>
      {/* 쪽을 보여 줄 때만(디자인 대조 C3): 미리보기를 못 열면 미리보기 안내 하나만 남긴다 */}
      {item.position === null && pdf.state === 'ready' && pdf.file !== null && (
        <PageInfo icon={<PageInfoIcon />} data-testid="position-missing">
          {GW_TEXT.review.positionMissing}
        </PageInfo>
      )}
      {/* 쪽 그림은 이 상자 안쪽 폭에 맞춰 줄어든다(밴드 GFS1). safe center: 그래도 넘칠 때(폭을 재기 전 첫 그림)는 왼쪽부터 놓아 왼쪽 끝과 등급 태그가 잘리지 않게(그냥 center 는 양쪽으로 넘쳐 왼쪽을 스크롤로 닿을 수 없었다) */}
      {/* 칸 높이가 정해져 있으면(sticky 카드) 남은 높이를 채우고 안에서 세로로도 스크롤된다(sid:MARC-ISSUE-341) */}
      <div
        ref={scrollRef}
        className="flex min-h-0 flex-1 overflow-auto [justify-content:safe_center] rounded-component bg-background-tertiary p-6"
        data-testid="page-scroll"
      >
        {pdf.state === 'loading' ?
          <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
            {words.previewLoading}
          </p>
        : pdf.state === 'ready' && pdf.file !== null ?
          <PdfPage
            file={pdf.file}
            openPdf={openPdf}
            page={page}
            level={item.level}
            box={box}
            boxLabel={words.sentenceBox(page, item.level, item.sentence)}
            others={others}
            pickKey={pickKey}
            scrollRef={scrollRef}
            onPick={(index) => {
              if (index !== currentIndex) onPick?.(index);
            }}
            onRetry={retry}
          />
        : pdf.state === 'failed' ?
          <PreviewFailed onRetry={retry} actionRef={focus.actionRef} />
        : <Unavailable text={words.previewUnavailable} />}
      </div>
    </div>
  );
}

/** PDF 읽기 상태 → 초점 훅의 phase(없음은 읽기가 끝난 것 — ready). */
const PHASE: Record<DocumentPdfState['state'], RetryPhase> = {
  loading: 'loading',
  ready: 'ready',
  missing: 'ready',
  failed: 'failed',
};

/** 미리보기 칸 실패(시안 CM-03 cm-cellfail): 회색 칸 + 글 + 작은 [다시 시도]. actionRef 는 [다시 시도]에. */
function PreviewFailed({
  onRetry,
  actionRef,
}: {
  onRetry(): void;
  actionRef?: Ref<HTMLButtonElement>;
}) {
  return (
    <div
      role="status"
      data-testid="preview-failed"
      className="box-border flex min-h-[360px] w-full flex-col items-center justify-center gap-3 rounded-component bg-background-secondary p-6 text-center text-style-pre-body-06 text-text-tertiary"
    >
      <CircleWarningIcon aria-hidden className="size-8 text-text-quaternary" />
      <span data-testid="preview-failed-text">{words.previewFailed}</span>
      <Button
        ref={actionRef}
        variant="outlineGrey"
        shape="round"
        size="sm"
        onClick={onRetry}
      >
        {GW_TEXT.load.retry}
      </Button>
    </div>
  );
}

function Unavailable({ text }: { text: string }) {
  return (
    <PageInfo
      icon={<CircleWarningIcon aria-hidden />}
      data-testid="preview-unavailable"
      className="w-full"
    >
      {text}
    </PageInfo>
  );
}

interface PdfPageProps {
  file: File;
  openPdf: OpenPdf;
  page: number;
  level: Level;
  box: Box | null;
  /** 고른 상자 단추의 이름. */
  boxLabel: string;
  /** 같은 쪽의 안 고른 문장 상자들(목록 차례). */
  others: readonly PageBox[];
  /** 고를 때마다 바뀌는 열쇠(바뀌면 고른 상자를 쪽 칸 안으로 맞춘다). */
  pickKey: string;
  /** 쪽 칸(page-scroll) — 고른 상자를 이 칸 안에서만 스크롤해 맞춘다. */
  scrollRef: RefObject<HTMLDivElement | null>;
  /** 상자를 누름(고른 문장이면 부르는 쪽이 거른다). */
  onPick(index: number): void;
  /** 열기·그리기 실패의 [다시 시도](PDF 를 다시 읽는다). */
  onRetry(): void;
}

/** File 을 object URL 로 열고(바뀌거나 내려가면 revoke — useObjectUrl), 쪽 하나를 그린다. */
function PdfPage({ file, ...rest }: PdfPageProps) {
  const url = useObjectUrl(file);
  if (url === null) return null;
  return <OpenedPage key={url} url={url} {...rest} />;
}

function OpenedPage({
  url,
  openPdf,
  page,
  level,
  box,
  boxLabel,
  others,
  pickKey,
  scrollRef,
  onPick,
  onRetry,
}: Omit<PdfPageProps, 'file'> & { url: string }) {
  const loaded = usePdf(url, openPdf);
  const sheetRef = useRef<HTMLDivElement>(null);
  const pickedRef = useRef<HTMLButtonElement>(null);
  const ready = loaded.state === 'ready';
  const scale = useFitScale(ready, sheetRef, scrollRef);
  // 고른 상자를 쪽 칸 안으로: 고를 때마다, 그리고 쪽 그림 크기가 정해질 때(캔버스는 그린 뒤에야 크기가 생긴다)
  useLayoutEffect(() => {
    const sheet = sheetRef.current;
    if (!ready || sheet === null) return;
    const fit = () => {
      const scroller = scrollRef.current;
      const target = pickedRef.current;
      if (scroller === null || target === null) return;
      fitInside(scroller, target);
    };
    fit();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(fit);
    observer.observe(sheet);
    return () => observer.disconnect();
  }, [ready, pickKey, page, scrollRef]);
  if (loaded.state === 'loading')
    return (
      <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
        {words.previewLoading}
      </p>
    );
  if (loaded.state === 'error') return <PreviewFailed onRetry={onRetry} />;
  // 겹침 차례: 넓이가 큰 것부터 아래(작은 상자가 위), 같으면 목록 뒤 문장이 아래. 고른 상자는 그 위.
  const area = (b: Box) => (b[2] - b[0]) * (b[3] - b[1]);
  const stack = others
    .map((other, order) => ({ order, size: area(other.box) }))
    .sort((a, b) => b.size - a.size || b.order - a.order);
  const layer = new Map(stack.map((entry, z) => [entry.order, z + 1]));
  return (
    <div
      ref={sheetRef}
      className="relative shrink-0 self-start bg-background-primary shadow-[0_0_5px_2px_rgb(0_0_0/0.1)]"
    >
      <div
        role="img"
        aria-label={words.pageImage(page, box === null ? null : level)}
      >
        <PageCanvas
          pdf={loaded.pdf}
          pageNumber={page}
          scale={scale}
          rotation={0}
          errorFallback={<PreviewFailed onRetry={onRetry} />}
        />
      </div>
      {others.map((other, order) => (
        <button
          key={other.index}
          type="button"
          data-testid="page-box"
          data-item={other.index}
          data-level={other.level}
          aria-label={other.label}
          onClick={() => onPick(other.index)}
          className={cn(
            'absolute box-border cursor-pointer rounded-sm border border-solid bg-transparent p-0 hover:border-2 focus-visible:border-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary',
            BOX_LINE[other.level],
          )}
          style={{ ...padded(other.box, scale), zIndex: layer.get(order) }}
        />
      ))}
      {box !== null && (
        <>
          {/* 고른 문장도 단추(Tab 으로 닿는다). 다시 눌러도 아무 일 없다. 꼴은 아래 highlight 가 그린다 */}
          <button
            ref={pickedRef}
            type="button"
            data-testid="page-box-current"
            aria-label={boxLabel}
            aria-current="true"
            className="absolute box-border cursor-pointer rounded-sm border-0 bg-transparent p-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary"
            style={{ ...padded(box, scale), zIndex: others.length + 1 }}
          />
          <div
            // 문장(상자 자리)이 바뀔 때마다 새로 그려 다시 움직이게 한다(밴드 GA1)
            key={box.join(',')}
            data-testid="highlight"
            data-level={level}
            // 자리 틀만 — zIndex 를 주지 않는다(쌓임 맥락을 열면 안쪽 칠 칸의 곱하기 섞기가 이 틀 안에 갇혀 바탕색이 PDF 글자를 덮는다 — GP2 회귀, 밴드 GP4)
            className="pointer-events-none absolute"
            style={{
              left: box[0] * scale,
              top: box[1] * scale,
              width: (box[2] - box[0]) * scale,
              height: (box[3] - box[1]) * scale,
            }}
          >
            {/* 칠 칸: 쌓임 맥락의 뿌리에서 섞는다(zIndex 와 mix-blend-multiply 를 같은 칸에 — 옅은 상자 위 차례는 그대로) */}
            <span
              aria-hidden
              data-testid="highlight-fill"
              className={cn(
                'gw-m-mark absolute box-border rounded-sm border-2 border-solid mix-blend-multiply',
                BOX_LOOK[level],
                GLOW_LOOK[level],
              )}
              style={{
                top: -BOX_PAD * scale,
                right: -BOX_PAD * scale,
                bottom: -BOX_PAD * scale,
                left: -BOX_PAD * scale,
                zIndex: others.length + 2,
              }}
            />
            {/* 등급 태그는 칠 칸의 형제(섞이지 않는다), 그 위 */}
            <RiskBadge
              level={RISK[level]}
              aria-hidden
              className="gw-m-rise absolute -top-6 left-0"
              style={{ zIndex: others.length + 3 }}
            />
          </div>
        </>
      )}
    </div>
  );
}

/** 바깥 상자(pt) → 사방 BOX_PAD 를 더한 CSS 자리(문장 상자 테두리 자리 — 고른 상자의 frame 과 같다). */
function padded(b: Box, scale: number) {
  return {
    left: (b[0] - BOX_PAD) * scale,
    top: (b[1] - BOX_PAD) * scale,
    width: (b[2] - b[0] + 2 * BOX_PAD) * scale,
    height: (b[3] - b[1] + 2 * BOX_PAD) * scale,
  };
}

/**
 * 쪽 칸(scroller) 안쪽 폭에 맞춘 배율(밴드 GFS1). 칸과 쪽 그림(sheet)의 크기가 바뀔 때마다 다시 잰다.
 * 쪽 폭(pt) = 그린 캔버스의 CSS 폭 ÷ 그때의 배율 — PdfHandle.renderPage 계약이 캔버스 CSS 크기를 정한다(style.width).
 * 아직 그리지 않은 새 캔버스(style.width 없음 — 기본 300px)는 재지 않는다. 쪽 그림에 테두리가 없어 칸 폭에서 뺄 것은 안쪽 여백뿐이다.
 */
function useFitScale(
  ready: boolean,
  sheetRef: RefObject<HTMLDivElement | null>,
  scrollRef: RefObject<HTMLDivElement | null>,
) {
  const [available, setAvailable] = useState(0);
  const [pageWidth, setPageWidth] = useState(0);
  const scale = fitScale(available, pageWidth, PREVIEW_SCALE);
  // 잴 때 캔버스가 그려진 배율(그린 뒤에 적는다 — 캔버스는 배율이 바뀌면 새로 만들어진다)
  const scaleRef = useRef(scale);
  useLayoutEffect(() => {
    scaleRef.current = scale;
  });
  useLayoutEffect(() => {
    const sheet = sheetRef.current;
    const scroller = scrollRef.current;
    if (!ready || sheet === null || scroller === null) return;
    if (typeof ResizeObserver === 'undefined') return;
    const measure = () => {
      const style = getComputedStyle(scroller);
      setAvailable(
        scroller.clientWidth -
          (parseFloat(style.paddingLeft) || 0) -
          (parseFloat(style.paddingRight) || 0),
      );
      const drawn = parseFloat(
        sheet.querySelector('canvas')?.style.width ?? '',
      );
      // 0.01pt 로 반올림(배율을 곱했다 나눈 부동소수 끝자리로 배율이 흔들리지 않게)
      if (drawn > 0)
        setPageWidth(Math.round((drawn / scaleRef.current) * 100) / 100);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(scroller);
    observer.observe(sheet);
    return () => observer.disconnect();
  }, [ready, sheetRef, scrollRef]);
  return scale;
}

/** scroller 만 움직여 target 을 보이게: 세로는 등급 태그(상자 위 24px)까지 다 보이지 않으면 가운데로,
 *  가로는 상자 왼쪽 끝(태그 자리)이 칸 밖일 때만 왼쪽 끝을 칸 안쪽 여백 자리에 놓는다(쪽 그림은 왼쪽부터 놓는 꼴 그대로). */
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
