// RP-04 원문 보기 칸(밴드 RPW1 ③ — 발주서 §2-3, 시안 v188 RP-04_r1 「원문 보기」). 라우터를 모른다.
// - 원본 PDF 는 저장소 openPdf(문서 id 마다 한 벌 — 같은 문서는 다시 받지 않는다) → useObjectUrl → usePdf(여는 함수는 틀이 pdf.js 를 props 로) → PageCanvas.
// - PDF 는 outcome ready 동안 붙여 둔다(RPW2 M3) — 볼 쪽이 없으면 빈 장, 쪽을 다시 골라도 다시 열지 않는다.
// - 머리: 「원문 보기」 · 「‹ 쪽 / 쪽 수 ›」(문서 전체를 한 쪽씩, 끝에서 끔) · 「이 목차의 페이지」 줄(잎 pages — 누르면 그 쪽) · 파일 줄 · 범례 「근거 문단 · 근거 문장」.
// - 쪽 위 두 층(model/evidence marksOf): 옅은 블록 상자 data-layer="block" · 진한 문장 상자 data-layer="sentence"(둘 다 data-block-id) ·
//   그 쪽 출처가 모두 sentence null 이면 옅은 것만 + 「문단까지만 찾았어요」. 쪽 크기 0 이면 상자를 그리지 않는다.
// - PDF missing/failed → 「원본 PDF 를 불러오지 못했어요」(+[다시 시도] failed 만). 영문번역 PdfView.tsx PdfFile·PdfPage 꼴을 옮겨 적음.
import { useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import {
  ChevronLeftIcon,
  ChevronRightIcon,
  InfoIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import type { DraftingStore } from '../../../entities/drafting/api/index.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { usePdfFile } from '../../../entities/drafting/hooks/index.ts';
import type {
  Bullet,
  DraftingResult,
} from '../../../entities/drafting/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
// 움직임 클래스(gw-m-*)만 쓴다 — CSS 는 이 표면이 싣는다(shared/ui/motion/index.ts 머리).
import '../../../shared/ui/motion/index.ts';
import { PageCanvas, usePdf } from '../../../widgets/doc-viewer/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { fitScale, marksOf, screenRectOf } from '../model/index.ts';
import { useObjectUrl } from './useObjectUrl.ts';

const words = DR_TEXT.result.source;

/** 쪽 그림 배율의 위끝(1 pt = 1 CSS 픽셀). 칸이 좁으면 칸 폭에 맞춰 줄인다. */
const SCALE = 1;
/** 근거 두 층(sid:MARC-ENT-514) — 문단은 크림 상자(글이 비치게 곱하기), 문장은 주황 테두리. */
const BLOCK_CLASS =
  'border border-solid border-support-yellow bg-support-yellow-subtle mix-blend-multiply';
const SENTENCE_CLASS = 'border-2 border-solid border-support-orange';
/** 쪽 위 고른 근거 문장 상자의 나타남 — gw-m-mark 의 빛이 currentColor 를 써서 글자 색 = 선 색(밴드 RPW5 #7). */
const SENTENCE_MOTION = 'gw-m-mark text-support-orange';

export interface SourcePaneProps {
  store: DraftingStore;
  openPdf: OpenPdf;
  pdf: DraftingResult['pdf'];
  /** 고른 잎의 쪽(머리 쪽 줄). */
  leafPages: readonly number[];
  /** 지금 보는 쪽(null = 볼 쪽 없음 — 비움). */
  page: number | null;
  onPage(page: number): void;
  /** 고른 bullet(null 이면 상자 없음). */
  bullet: Bullet | null;
}

export function SourcePane({
  store,
  openPdf,
  pdf,
  leafPages,
  page,
  onPage,
  bullet,
}: SourcePaneProps) {
  const { status, retry } = usePdfFile(store, pdf.documentId);
  const view =
    page === null ? null : pdf.pages.find((one) => one.page === page);
  const { marks, paragraphOnly } = marksOf(bullet, page ?? 0);
  const outcome = status.kind === 'loading' ? null : status;
  const failed = outcome !== null && outcome.kind !== 'ready';
  return (
    <section
      data-testid="source-pane"
      aria-label={words.title}
      className="flex min-w-0 flex-col gap-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.title}
        </h3>
        {page !== null && (
          <div className="flex items-center gap-1">
            <PageStep
              label={words.pagePrev}
              disabled={page <= 1}
              onClick={() => onPage(page - 1)}
            >
              <ChevronLeftIcon aria-hidden />
            </PageStep>
            <span
              data-testid="source-page"
              className="tabular-nums text-style-pre-caption-03 text-text-secondary"
            >
              {words.pageOf(page, pdf.pageCount)}
            </span>
            <PageStep
              label={words.pageNext}
              disabled={page >= pdf.pageCount}
              onClick={() => onPage(page + 1)}
            >
              <ChevronRightIcon aria-hidden />
            </PageStep>
          </div>
        )}
      </div>
      {leafPages.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {words.leafPages}
          </span>
          {leafPages.map((one) => (
            <button
              key={one}
              type="button"
              data-page={one}
              aria-pressed={one === page}
              onClick={() => onPage(one)}
              className={cn(
                'flex size-7 items-center justify-center rounded-full tabular-nums text-style-pre-caption-02',
                one === page ?
                  'bg-background-primary-inverse text-text-primary-inverse'
                : 'bg-background-secondary text-text-secondary',
              )}
            >
              {one}
            </button>
          ))}
        </div>
      )}
      <p className="m-0 truncate text-style-pre-caption-03 text-text-tertiary">
        {words.file(pdf.fileName)}
      </p>
      <div
        data-testid="source-legend"
        className="flex flex-wrap items-center gap-3 text-style-pre-caption-03 text-text-secondary"
      >
        <span className="flex items-center gap-1">
          <span
            aria-hidden
            className={cn('box-border inline-block size-3', BLOCK_CLASS)}
          />
          {words.block}
        </span>
        <span className="flex items-center gap-1">
          <span
            aria-hidden
            className={cn('box-border inline-block size-3', SENTENCE_CLASS)}
          />
          {words.sentence}
        </span>
      </div>
      {paragraphOnly && (
        <p
          data-testid="paragraph-only"
          className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-text-tertiary [&_svg]:size-4 [&_svg]:shrink-0"
        >
          <InfoIcon aria-hidden />
          {words.paragraphOnly}
        </p>
      )}
      {failed ?
        <div
          role="alert"
          data-testid="source-failed"
          className="flex flex-wrap items-center gap-2 text-style-pre-body-05 text-text-secondary"
        >
          {words.failed}
          {outcome?.kind === 'failed' && (
            <Button
              variant="outlineGrey"
              shape="round"
              size="sm"
              onClick={retry}
            >
              {DR_TEXT.common.retry}
            </Button>
          )}
        </div>
      : outcome?.kind === 'ready' ?
        <PdfFile
          file={outcome.file}
          openPdf={openPdf}
          view={view ?? null}
          marks={marks}
        />
      : outcome === null && page !== null ?
        <LoadSkeleton />
      : null}
    </section>
  );
}

function PageStep({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick(): void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="flex size-6 items-center justify-center rounded text-text-secondary disabled:text-text-tertiary disabled:opacity-40 [&_svg]:size-4"
    >
      {children}
    </button>
  );
}

interface PageProps {
  openPdf: OpenPdf;
  /** 볼 쪽(null = 빈 장 — 문서는 연 채 둔다). */
  view: { page: number; width: number; height: number } | null;
  marks: ReturnType<typeof marksOf>['marks'];
}

function PdfFile({ file, ...rest }: { file: File } & PageProps) {
  const url = useObjectUrl(file);
  // 파일이 바뀌면 key 로 새로 연다(useObjectUrl 머리).
  return url === null ? null : <PdfPage key={url} url={url} {...rest} />;
}

/** 칸의 안쪽 폭(CSS 픽셀). ResizeObserver 가 없는 곳(jsdom)이면 0 — fitScale 이 위끝 배율로 둔다. */
function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null) return;
    setWidth(element.clientWidth);
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => setWidth(element.clientWidth));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

function PdfPage({ url, openPdf, view, marks }: { url: string } & PageProps) {
  const loaded = usePdf(url, openPdf);
  const fit = useWidth();
  const scale = fitScale(fit.width, view?.width ?? 0, SCALE);
  const size =
    view !== null && view.width > 0 && view.height > 0 ?
      { width: view.width * scale, height: view.height * scale }
    : null;
  return (
    <div ref={fit.ref} data-testid="source-frame" className="w-full min-w-0">
      {view === null ?
        null
      : loaded.state === 'loading' ?
        <LoadSkeleton />
      : loaded.state === 'error' ?
        <p
          role="alert"
          data-testid="source-failed"
          className="m-0 text-style-pre-body-05 text-text-secondary"
        >
          {words.failed}
        </p>
      : <div
          data-testid="source-sheet"
          data-page={view.page}
          className="relative bg-white shadow-[0_0_5px_2px_rgb(0_0_0/0.1)]"
          style={size ?? undefined}
        >
          <PageCanvas
            pdf={loaded.pdf}
            pageNumber={view.page}
            scale={scale}
            rotation={0}
          />
          {marks.map((mark, index) => {
            const rect = screenRectOf(mark.box, view, scale);
            return rect === null ? null : (
                <span
                  key={`${mark.layer}/${mark.blockId}/${index}`}
                  aria-hidden
                  data-layer={mark.layer}
                  data-block-id={mark.blockId}
                  className={cn(
                    'pointer-events-none absolute rounded-sm',
                    mark.layer === 'block' ?
                      BLOCK_CLASS
                    : cn(SENTENCE_CLASS, SENTENCE_MOTION),
                  )}
                  style={rect}
                />
              );
          })}
        </div>
      }
    </div>
  );
}
