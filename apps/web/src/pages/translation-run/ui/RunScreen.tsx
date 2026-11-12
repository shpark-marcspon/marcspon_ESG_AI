// 묶음 화면(밴드 TRW1a ③, 시안 TR-03·04·04a 확정 판 v136 — 한 화면). 라우터를 모른다 — 저장소·주소 값·콜백 props 를 받는다.
// - useBatch 폴링(active 동안). 404 → 「찾을 수 없어요」(목록으로), 폴링 실패 → LoadFailure([다시 시도]).
// - 머리: 화면 제목(screenTitle) · 「파일 · 올림 · 파트 n」(돌면 「이 창을 닫아도…」) · [목록으로] · 단계 띠.
// - 일부 파트만 시작했으면 띠(감독 판단 4 ⓐ — runtime 메모리, 새로 고침이면 없음). 못 만든 파트는 탭이 「실패」이고 실패 카드(다시 단추 0).
//   띠는 서버 묶음에 있는 파트를 「시작함」으로 옮겨 짓는다(카드 거름과 같은 기준 — 끊김 다시 보냄으로 서버가 만든 파트, 밴드 TRW1b). 못 한 파트가 0 이면 띠 0.
// - 파트 탭([전체] + 파트, 파트가 하나면 탭 없이 그 파트): [전체] = 수치 칸 + 파트별 표(Word = 그 파트 자동 수정 병기본) + [모두 받기](zip —
//   409 둘은 단추 옆 글, 실패 글과 겹치지 않게 {kind:'handled'}). 파트 탭 = 진행 중 StageCard / 실패 PartFailureCard /
//   끝남 PartResultHeader([내려받기] → 받기 모달 — 요약 files 에 있는 것만 켬, 밴드 TRW14) + 결과(useResult) 이슈 표·용어집 미반영·확인할 쪽·단계 줄.
// - [이 파트만 다시](밴드 TRW1b, 결정 sid:MARC-ENT-393 — 파트 하나면 [다시 실행]): 서버 오류 카드·일부 쪽 결과 머리에만. 거절·못 만든 파트·
//   `run-` 열쇠 묶음(batchId 없는 옛 실행)은 단추 0. 누르면 store.retryPart 한 번(보내는 동안·새 회차를 받기 전까지 단추 꺼짐) →
//   됨: useBatch.restart(받은 값을 들고 폴링 다시 — 탭 그대로) · 안 됨: 단추 아래 retryFailed 한 줄, 단추 다시 켬. [전체] 탭에는 단추 0(판 TR-04).
// - A·B 견주기면 파트 탭 아래 스타일 탭(키트 Tabs box) — 결과·Word 가 고른 문체를 따른다.
// - PDF 파트(밴드 TRW6 ③, 6c v174 TR-P04): 실행 정보(useRunInfo)의 resultShapes 에 layout@1 이 있는 끝난 파트에만 [PDF로 보기].
//   검수 이슈·용어집 미반영 표에 「자리」 칸(layout 을 받은 뒤 — 붙이기는 pdfAttach) → 누르면 onOpenPdf(그 자리). 워드 파트는 표·DOM 그대로.
//   PDF 파트 판별(밴드 TRW6 ④)은 묶음 latest.flowId(TRS3 칸) — 실행 정보는 PDF 흐름의 끝난 파트만 읽는다(워드 파트 GET /runs/{id} 0 더함, R14).
//   실패 칸(W8): PDF 흐름이면 errorCode no_text_layer → 텍스트 없음 · 거절 bad_file → 읽지 못함 · 그 밖 → 다시 단추 + 회색 한 줄. 진행 중 첫 단계 「PDF 읽는 중」.
// - 첫 불러오기(밴드 TRP5, sid:MARC-ENT-443 ④): 묶음을 받기 전에는 제목·설명 자리(titlePending·descriptionPending)와 [목록으로]를 먼저 그리고
//   단계 띠(지금 단계 없음)를 그리고, 본문 LoadSkeleton 은 300ms(useDelayed) 뒤. 파트 결과(useResult)의 LoadSkeleton 도 300ms 뒤.
import { useRef, useState } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import type {
  FileDownload,
  TranslationStore,
} from '../../../entities/translation/api/index.ts';
import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import {
  useBatch,
  useLayout,
  useResult,
  useRunInfo,
} from '../../../entities/translation/hooks/index.ts';
import {
  LAYOUT_SHAPE,
  PART_KEYS,
  batchViewOf,
  doneCount,
  failureKindOf,
  isActive,
  isPdfFlow,
  pageCountOf,
  screenTitleKey,
  stageOf,
} from '../../../entities/translation/model/index.ts';
import type {
  BatchView,
  DigestVariant,
  PartKey,
  PartView,
  TabState,
  TranslationBatchDetail,
  TranslationLayout,
  VariantLabel,
} from '../../../entities/translation/model/index.ts';
import {
  PartFailureCard,
  PartTabs,
  StageCard,
  StatTiles,
  StatusBadge,
  remainingLine,
  screenTitle,
} from '../../../entities/translation/ui/index.ts';
import type {
  PartTab,
  PartTabKey,
  StatTile,
  StatusLook,
} from '../../../entities/translation/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { PageTitle } from '../../../shared/ui/card/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
import { useDelayed } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { StepFlow } from '../../../shared/ui/step-flow/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';
import {
  checkRowsOf,
  issuesOf,
  missesOf,
  numbersOf,
  pdfPageLinesOf,
  pdfPageOf,
  placesOf,
  reviewedRangeOf,
  stepLineOf,
  sumNumbers,
  variantLabelsOf,
} from '../model/index.ts';
import type {
  CheckRow,
  PartNumbers,
  PdfOpenFocus,
  PdfPlace,
  QaIssue,
  StepValue,
} from '../model/index.ts';
import { AllSummary } from './AllSummary.tsx';
import type { AllSummaryRow } from './AllSummary.tsx';
import { GlossaryMissTable } from './GlossaryMissTable.tsx';
import type { MissRow } from './GlossaryMissTable.tsx';
import { PagesToCheck, ResultNotices, StepLine } from './PagesToCheck.tsx';
import { PartResultHeader } from './PartResultHeader.tsx';
import { QaIssueTable } from './QaIssueTable.tsx';

const names = TR_TEXT.parts.names;
const run = TR_TEXT.run;
const result = TR_TEXT.result;

export interface RunScreenProps {
  store: TranslationStore;
  documentId: string;
  batchKey: string;
  /** ?part= (없으면 [전체] — 파트가 하나면 그 파트). */
  part?: PartTabKey;
  /** 이 탭에서 [번역 시작]했을 때 못 만든 파트(감독 판단 4 ⓐ). */
  notStarted?: { started: readonly PartKey[]; failed: readonly PartKey[] };
  onBack(): void;
  /** 파트 탭 바꿈(주소 ?part= replace). */
  onTab(part: PartTabKey): void;
  /** PDF 파트 [PDF로 보기]·표 「자리」(밴드 TRW6 ③). focus null = 첫 쪽. 없으면 단추·칸 0. row = 누른 표 줄(밴드 TRW7 ② — 돌아올 때 강조). */
  onOpenPdf?(runId: string, focus: PdfOpenFocus | null, row?: SummaryRow): void;
  /** PDF 보기에서 [← 결과 요약]으로 돌아왔을 때 눌렀던 표 줄(한 번 쓰는 표식 — 틀이 지운다). 그 실행의 그 문체 표에서 옅은 파랑으로 남고 화면 안. */
  returned?: SummaryRow & { runId: string; label: VariantLabel };
}

/** 요약 표 줄 하나(그 표의 입력 차례 — issuesOf·missesOf 차례). */
interface SummaryRow {
  table: 'issues' | 'misses';
  index: number;
}

/** 화면에 그릴 파트 하나: 서버 묶음의 파트, 또는 못 만든 파트(서버에 없음). */
type ScreenPart =
  { kind: 'server'; view: PartView } | { kind: 'not_started'; part: PartKey };

const stateOf = (part: ScreenPart): TabState =>
  part.kind === 'server' ? part.view.state : 'failed';
const keyOf = (part: ScreenPart): PartKey =>
  part.kind === 'server' ? part.view.part : part.part;

/** 끝난 파트인가(결과가 있다 — 완료·일부 쪽). */
const finished = (state: TabState) =>
  state === 'done' || state === 'failed_partial';

/** 「스토리 4~41쪽(38쪽)」. */
function partTitle(view: PartView): string {
  return view.range === null ?
      names[view.part]
    : result.title(names[view.part], view.rangeText!, pageCountOf(view.range));
}

const styleText = (view: PartView) =>
  view.style === null ? TR_TEXT.stats.none : TR_TEXT.list.styles[view.style];

/** 고른 문체의 요약(견주기면 A·B 가운데, 아니면 single). */
function digestVariantOf(
  view: PartView,
  label: VariantLabel,
): DigestVariant | undefined {
  const variants = view.run.digest?.variants ?? [];
  return variants.find((v) => v.label === label) ?? variants[0];
}

/** 그 스타일의 요약만(견주기 [전체] 탭 — 없는 스타일을 다른 스타일로 메우지 않는다). */
const styleVariantOf = (view: PartView, style: 'A' | 'B') =>
  view.run.digest?.variants.find((v) => v.label === style);

export function RunScreen({
  store,
  documentId,
  batchKey,
  part,
  notStarted,
  onBack,
  onTab,
  onOpenPdf,
  returned,
}: RunScreenProps) {
  const { status, retry, restart } = useBatch(store, documentId, batchKey);
  if (status.state === 'loading') return <Pending onBack={onBack} />;
  if (status.state === 'missing')
    return (
      <div data-screen="translation-run">
        <LoadFailure
          kind="missing"
          message={run.missing}
          onList={onBack}
          listLabel={run.back}
        />
      </div>
    );
  if (status.state === 'failed')
    return (
      <div data-screen="translation-run">
        <LoadFailure
          kind="failed"
          message={run.loadFailed}
          onRetry={retry}
          retryLabel={TR_TEXT.list.retry}
          onList={onBack}
          listLabel={run.back}
        />
      </div>
    );
  return (
    <Loaded
      store={store}
      batch={status.batch}
      part={part}
      notStarted={notStarted}
      onBack={onBack}
      onTab={onTab}
      onRestart={restart}
      {...(onOpenPdf === undefined ? {} : { onOpenPdf })}
      {...(returned === undefined ? {} : { returned })}
    />
  );
}

/** 묶음을 받기 전: 제목·설명 자리 + [목록으로] + 단계 띠 — 본문 LoadSkeleton 은 300ms 뒤(받은 뒤 제목 줄이 밀리지 않게). */
function Pending({ onBack }: { onBack(): void }) {
  const late = useDelayed(true);
  return (
    <div
      data-screen="translation-run"
      aria-busy
      className="flex flex-col gap-6"
    >
      <PageTitle
        title={null}
        titlePending
        descriptionPending
        actions={
          <Button
            variant="outlineGrey"
            shape="round"
            size="md"
            onClick={onBack}
          >
            {run.back}
          </Button>
        }
      />
      {/* 단계 셋은 데이터 없이 그릴 수 있다 — 지금 단계 표시 없이(current 0) 자리만(감독 판단, 받은 뒤 본문이 밀리지 않게) */}
      <StepFlow
        current={0}
        steps={TR_TEXT.newTranslation.steps}
        label={TR_TEXT.newTranslation.stepsLabel}
        prefix={TR_TEXT.newTranslation.stepPrefix}
      />
      {late && <LoadSkeleton />}
    </div>
  );
}

function Loaded({
  store,
  batch,
  part,
  notStarted,
  onBack,
  onTab,
  onRestart,
  onOpenPdf,
  returned,
}: Omit<RunScreenProps, 'documentId' | 'batchKey'> & {
  batch: TranslationBatchDetail;
  onRestart(): void;
}) {
  const view = batchViewOf(batch);
  // 돌아온 표 줄이 B 문체 표였으면 B 탭으로(그 줄이 그 표에 있게).
  const [style, setStyle] = useState<'A' | 'B'>(
    returned?.label === 'B' ? 'B' : 'A',
  );
  const again = useRetryPart(store, view, onRestart);
  const serverParts: ScreenPart[] = view.parts.map((p) => ({
    kind: 'server',
    view: p,
  }));
  const missingParts: ScreenPart[] = (notStarted?.failed ?? [])
    .filter((key) => !view.parts.some((p) => p.part === key))
    .map((key) => ({ kind: 'not_started', part: key }));
  const parts = [...serverParts, ...missingParts].sort(
    (a, b) => PART_KEYS.indexOf(keyOf(a)) - PART_KEYS.indexOf(keyOf(b)),
  );
  const states = parts.map((p) => ({ state: stateOf(p) }));
  const titleKey = screenTitleKey(states);
  const single = parts.length === 1;
  const value: PartTabKey =
    single ? keyOf(parts[0]!)
    : (
      part !== undefined &&
      (part === 'all' || parts.some((p) => keyOf(p) === part))
    ) ?
      part
    : 'all';
  const compare = view.style === 'AB';
  const startedOnServer = (key: PartKey) =>
    view.parts.some((p) => p.part === key);
  // 띠: 서버 묶음에 있는 파트는 시작한 것(카드 거름 missingParts 와 같은 기준).
  const band =
    notStarted === undefined ? null : (
      {
        started: [
          ...notStarted.started,
          ...notStarted.failed.filter(startedOnServer),
        ],
        failed: notStarted.failed.filter((key) => !startedOnServer(key)),
      }
    );
  const label: VariantLabel = compare ? style : 'single';

  const tabs: PartTab[] = [
    {
      key: 'all',
      label: TR_TEXT.tabs.all,
      note: TR_TEXT.tabs.allNote(doneCount(states), parts.length),
    },
    ...parts.map((p) => ({
      key: keyOf(p),
      label: names[keyOf(p)],
      state: stateOf(p),
    })),
  ];
  const fileOf = (runId: string, name: string) => () =>
    store.runFile(runId, name);

  const selected = parts.find((p) => keyOf(p) === value);
  const oneCard = selected?.kind === 'server' && isActive(selected.view.state);
  const meta = [
    run.meta(view.fileName, view.uploaded, parts.length),
    ...(titleKey === 'running' ? [TR_TEXT.stage.keepsRunning] : []),
  ].join(' · ');
  // PDF 묶음(밴드 TRW7 ③a W9 — 판 v182 TR-P04): 머리 파일 이름 앞 「PDF」 + [목록으로][PDF로 보기]. 워드 묶음은 머리 DOM 그대로.
  //   [PDF로 보기] = 고른 파트가 끝난 PDF 파트면 그 파트, [전체] 탭이면 첫 끝난 PDF 파트(감독 답 Q3) — 그 실행에 layout 이 있을 때만.
  const pdfBatch =
    onOpenPdf !== undefined &&
    (batch.inputKind === 'pdf' ||
      view.parts.some((p) => isPdfFlow(p.run.flowId)));
  const pdfPart = (p: ScreenPart | undefined) =>
    (
      p?.kind === 'server' &&
      finished(p.view.state) &&
      isPdfFlow(p.view.run.flowId)
    ) ?
      p.view
    : undefined;
  const pdfTarget =
    !pdfBatch ? undefined
    : value === 'all' ? parts.map(pdfPart).find((v) => v !== undefined)
    : pdfPart(selected);
  const targetInfo = useRunInfo(store, pdfTarget?.runId ?? null).status;
  const canOpenPdf =
    pdfTarget !== undefined &&
    targetInfo.state === 'ready' &&
    targetInfo.info.resultShapes.includes(LAYOUT_SHAPE);
  const backButton = (
    <Button variant="outlineGrey" shape="round" size="md" onClick={onBack}>
      {run.back}
    </Button>
  );

  return (
    <div data-screen="translation-run" className="flex flex-col gap-6">
      <PageTitle
        title={screenTitle(states)}
        description={
          pdfBatch ?
            <span className="inline-flex flex-wrap items-center gap-1.5">
              <span data-testid="run-pdf-mark">
                <StatusBadge look="grey">{TR_TEXT.list.pdfMark}</StatusBadge>
              </span>
              {meta}
            </span>
          : meta
        }
        actions={
          pdfBatch ?
            <div className="flex items-center gap-2">
              {backButton}
              {canOpenPdf && (
                <Button
                  variant="solidBlack"
                  shape="round"
                  size="md"
                  data-testid="open-pdf"
                  onClick={() => onOpenPdf(pdfTarget.runId, null)}
                >
                  {TR_TEXT.pdfView.open}
                </Button>
              )}
            </div>
          : backButton
        }
      />
      <StepFlow
        current={titleKey === 'running' ? 2 : 3}
        steps={TR_TEXT.newTranslation.steps}
        label={TR_TEXT.newTranslation.stepsLabel}
        prefix={TR_TEXT.newTranslation.stepPrefix}
      />
      {band !== null && band.failed.length > 0 && (
        <PageInfo
          tone="important"
          icon={<PageInfoIcon />}
          data-testid="partial-start"
          className="gw-m-rise"
        >
          {TR_TEXT.partialStart(
            PART_KEYS.filter((key) => band.started.includes(key)).map(
              (key) => names[key],
            ),
            band.failed.map((key) => names[key]),
          )}
        </PageInfo>
      )}
      {/* 고른 탭이 진행·대기면 탭 줄과 진행 카드가 한 카드(밴드 TRP2 TE10, 시안 TR-03). 감싸개는 늘 같은 요소이고 클래스만 바꾼다 —
          넣었다 뺐다 하면 Tabs 가 새로 붙어 ←/→ 로 탭을 넘을 때 초점이 빠진다(critic B1). */}
      <section
        data-testid="part-panel"
        data-one-card={oneCard || undefined}
        className={cn(oneCard && ONE_CARD_CLASS)}
      >
        <PartTabs
          tabs={tabs}
          value={value}
          onChange={onTab}
          aria-label={run.tabsLabel}
        >
          {compare && value !== 'all' && (
            <Tabs
              value={style}
              onValueChange={(next) => setStyle(next as 'A' | 'B')}
              variant="box"
            >
              <TabsList aria-label={run.styleTabsLabel}>
                {(['A', 'B'] as const).map((key) => (
                  <TabsTrigger key={key} value={key}>
                    {run.styleTab(key)}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )}
          {value === 'all' ?
            <AllTab
              store={store}
              view={view}
              parts={parts}
              compare={compare}
              fileOf={fileOf}
              onOpenPart={onTab}
              {...(onOpenPdf === undefined ? {} : { onOpenPdf })}
              pdfBatch={pdfBatch}
            />
          : selected === undefined ?
            null
          : selected.kind === 'not_started' ?
            <PartFailureCard
              kind="rejected"
              reason="no_pages"
              fileLine={`${view.fileName} · ${names[selected.part]}`}
              onBack={onBack}
            />
          : <PartTab
              store={store}
              batchId={view.rowId}
              fileName={view.fileName}
              view={selected.view}
              label={label}
              single={single}
              fileOf={fileOf}
              onBack={onBack}
              {...(onOpenPdf === undefined ? {} : { onOpenPdf })}
              {...((
                returned?.runId === selected.view.runId &&
                returned.label === label
              ) ?
                { returned }
              : {})}
              {...again.propsOf(selected.view)}
            />
          }
        </PartTabs>
      </section>
    </div>
  );
}

/** 파트 하나의 [이 파트만 다시](부르는 쪽이 서버 오류·일부 쪽에만 준다). */
interface PartRetry {
  onRetry(): void;
  /** 보내는 중·새 회차를 받기 전(단추 꺼짐). */
  retrying: boolean;
  /** 앞 누름이 거절·끊김(단추 아래 retryFailed 한 줄). */
  failed: boolean;
}

/**
 * [이 파트만 다시] 상태(묶음 화면 하나). 보낸 파트와 그때의 runId 를 들고 있다가, 묶음이 그 파트의 새 회차(다른 runId)를 실어 오면 풀린다.
 * `run-` 열쇠 묶음·거절·완료 파트에는 주지 않는다(결정 sid:MARC-ENT-393, 감독 판단 c).
 */
function useRetryPart(
  store: TranslationStore,
  view: BatchView,
  onRestart: () => void,
) {
  const [sent, setSent] = useState<{ part: PartKey; runId: string } | null>(
    null,
  );
  const [failed, setFailed] = useState<PartKey | null>(null);
  const busy = useRef(false);
  const propsOf = (p: PartView): { retry?: PartRetry } => {
    const kind = failureKindOf(p);
    if (
      view.batchKey.startsWith('run-') ||
      (kind !== 'server_error' && kind !== 'partial')
    )
      return {};
    const retrying =
      sent !== null && sent.part === p.part && sent.runId === p.runId;
    return {
      retry: {
        retrying,
        failed: failed === p.part,
        onRetry: () => {
          if (busy.current || retrying) return;
          busy.current = true;
          setFailed(null);
          setSent({ part: p.part, runId: p.runId });
          store
            .retryPart({
              documentId: view.documentId,
              batchKey: view.batchKey,
              part: p.part,
              runId: p.runId,
            })
            .then(
              () => {
                busy.current = false;
                onRestart();
              },
              () => {
                busy.current = false;
                setSent(null);
                setFailed(p.part);
              },
            );
        },
      },
    };
  };
  return { propsOf };
}

/** 다시 하기가 거절·끊김일 때 단추 아래 한 줄. */
function RetryFailed() {
  return (
    <PageInfo
      tone="error"
      icon={<PageInfoIcon />}
      role="alert"
      data-testid="retry-failed"
    >
      {TR_TEXT.failure.retryFailed}
    </PageInfo>
  );
}

/** 한 카드 꼴(shared Card 와 같은 클래스 — 흰 바탕 · 모서리 16 · 안쪽 32). */
const ONE_CARD_CLASS =
  'box-border min-w-0 rounded-dialog bg-background-primary p-8';

/**
 * PDF 파트들의 「확인할 곳」 합(밴드 TRW7 ③a W10). 파트 열쇠마다 layout 을 하나씩(훅 차례 고정 — 파트는 셋뿐).
 * 끝난 PDF 흐름 파트가 없으면 null(칸 0). 아직 다 못 읽었으면 total null. open = 확인할 곳이 있는 첫 파트·첫 쪽(누름 → 보기 「확인할 곳」 거르기).
 */
/** 한 파트 layout 의 「확인할 곳」 셈(보기 왼쪽과 같은 셈 — pdfPageLinesOf). 그 문체가 layout 에 없으면 첫 문체. images = 그림뿐인 쪽 수. */
function pdfChecksOf(layout: TranslationLayout, label: VariantLabel) {
  const labels = variantLabelsOf(layout);
  const shown = labels.includes(label) ? label : labels[0]!;
  const all = pdfPageLinesOf(layout, shown);
  const lines = all.filter((line) => line.checks > 0);
  return {
    shown,
    total: lines.reduce((sum, line) => sum + line.checks, 0),
    pages: lines.length,
    images: all.filter((line) => line.imageOnly).length,
    first: lines[0]?.page ?? null,
  };
}

function useChecks(
  store: TranslationStore,
  done: readonly PartView[],
  label: VariantLabel,
) {
  const runOf = (key: PartKey) =>
    done.find((p) => p.part === key && isPdfFlow(p.run.flowId)) ?? null;
  const ceo = runOf('ceo');
  const story = runOf('story');
  const general = runOf('general');
  const layouts = [
    [ceo, useLayout(store, ceo?.runId ?? null).status],
    [story, useLayout(store, story?.runId ?? null).status],
    [general, useLayout(store, general?.runId ?? null).status],
  ] as const;
  const present = layouts.filter(([part]) => part !== null);
  if (present.length === 0) return null;
  let total: number | null = 0;
  let pages = 0;
  let images: number | null = 0;
  let open: { runId: string; page: number; label: VariantLabel } | null = null;
  for (const [part, status] of present) {
    if (status.state === 'loading') {
      total = null;
      images = null;
      continue;
    }
    if (status.state !== 'ready') {
      images = null;
      continue;
    }
    const counted = pdfChecksOf(status.layout, label);
    if (total !== null) total += counted.total;
    if (images !== null) images += counted.images;
    pages += counted.pages;
    if (open === null && counted.first !== null)
      open = { runId: part!.runId, page: counted.first, label: counted.shown };
  }
  return { total, pages, images, open };
}

function AllTab({
  store,
  view,
  parts,
  compare,
  fileOf,
  onOpenPart,
  onOpenPdf,
  pdfBatch,
}: {
  store: TranslationStore;
  view: ReturnType<typeof batchViewOf>;
  parts: readonly ScreenPart[];
  /** A·B 견주기 — 수치·[Word] 를 A·B 둘로(밴드 TRW2 · 6c 10-26). 파트 탭의 스타일 고름은 읽지 않는다. */
  compare: boolean;
  fileOf: (runId: string, name: string) => () => Promise<FileDownload>;
  onOpenPart(part: PartKey): void;
  onOpenPdf?: RunScreenProps['onOpenPdf'];
  /** PDF 묶음(Loaded 의 셈) — 늘 다섯 칸(밴드 TRW8 ⑧): 끝난 PDF 파트가 없으면 「확인할 곳 –」, 읽는 중이면 pending. */
  pdfBatch: boolean;
}) {
  const [archive, setArchive] = useState<{
    error?: 'too_large' | 'nothing';
    missing?: number;
  }>({});
  const done = parts.flatMap((p) =>
    p.kind === 'server' && finished(p.view.state) ? [p.view] : [],
  );
  // 한 스타일은 single 요약 하나, 견주기는 A·B 따로(쪽 수·번역한 쪽은 요약 전체의 값이라 스타일과 무관).
  const STYLES = ['A', 'B'] as const;
  const totalOf = (pick: (v: PartView) => DigestVariant | undefined) =>
    sumNumbers(done.map((p) => numbersOf(p.run.digest, pick(p))));
  const total = totalOf((p) => digestVariantOf(p, compare ? 'A' : 'single'));
  const totalA = totalOf((p) => styleVariantOf(p, 'A'));
  const totalB = totalOf((p) => styleVariantOf(p, 'B'));
  const words = TR_TEXT.stats;
  const pairTile = (
    key: 'misses' | 'issues',
    label: string,
  ): Pick<StatTile, 'label' | 'value' | 'pair'> =>
    compare ?
      {
        label: words.pairLabel(label),
        value: null,
        pair: { A: totalA[key], B: totalB[key] },
      }
    : { label, value: total[key] };
  const issuesNote =
    compare ?
      totalA.fixed === null || totalB.fixed === null ?
        null
      : ([totalA.fixed, totalB.fixed] as const)
    : total.fixed;
  const checks = useChecks(
    store,
    onOpenPdf === undefined ? [] : done,
    compare ? 'A' : 'single',
  );
  const stats: StatTile[] = [
    {
      key: 'translated',
      label: words.labels.translated,
      value: total.translated,
      unit: 'page',
      // PDF 묶음은 「총 N페이지 가운데 · 그림뿐인 n페이지 빼고」(밴드 TRW7 ③b — 디자인 74 답 4), 워드는 그대로.
      ...(total.pageCount === null ? {}
      : checks === null ?
        { note: words.notes.outOfParts(total.pageCount, done.length) }
      : { note: words.notes.outOfImages(total.pageCount, checks.images) }),
    },
    {
      key: 'untranslated',
      label: words.labels.untranslated,
      value: total.untranslated,
      unit: 'page',
      ...(total.untranslated === 0 ? { note: words.notes.allTranslated } : {}),
    },
    // PDF 묶음만(밴드 TRW7 ③a W10 — 판 v182 TR-P04): 확인할 곳 = 보기 왼쪽 「확인할 곳 N」과 같은 셈(pdfPageLinesOf checks 합).
    //   PDF 묶음이면 처음부터 셋째 칸(밴드 TRW8 ⑧): 셀 파트가 없으면 값 「–」(감독 답 Q1) · 읽는 중이면 pending.
    ...(!pdfBatch ? []
    : checks === null ?
      [
        {
          key: 'checks',
          label: words.labels.checks,
          value: null,
          unit: 'place' as const,
        },
      ]
    : checks.total === null ?
      [
        {
          key: 'checks',
          label: words.labels.checks,
          value: null,
          unit: 'place' as const,
          pending: true as const,
        },
      ]
    : [
        {
          key: 'checks',
          label: words.labels.checks,
          value: checks.total,
          unit: 'place' as const,
          note: words.notes.checks(checks.pages),
          ...(checks.open === null || onOpenPdf === undefined ?
            {}
          : {
              onOpen: () => {
                const open = checks.open!;
                onOpenPdf(open.runId, {
                  page: open.page,
                  pair: null,
                  label: open.label,
                  from: null,
                  filter: 'checks',
                });
              },
            }),
        },
      ]),
    {
      key: 'glossaryMiss',
      ...pairTile('misses', words.labels.glossaryMiss),
      unit: 'count',
      note: words.notes.summed,
    },
    {
      key: 'issues',
      ...pairTile('issues', words.labels.issues),
      unit: 'count',
      ...(issuesNote === null ?
        {}
      : { note: words.notes.issuesBasis(issuesNote) }),
    },
  ];
  const rows: AllSummaryRow[] = parts.flatMap((p): AllSummaryRow[] => {
    if (p.kind !== 'server') return [];
    const v = p.view;
    const numbersAt = (variant: DigestVariant | undefined): PartNumbers =>
      finished(v.state) ?
        numbersOf(v.run.digest, variant)
      : numbersOf(null, undefined);
    const fileAt = (variant: DigestVariant | undefined) => {
      const autofix = variant?.files.autofix ?? null;
      return finished(v.state) && autofix !== null ?
          fileOf(v.runId, autofix)
        : undefined;
    };
    const head = {
      part: v.part,
      range: v.rangeText ?? words.none,
      round: v.round,
      started: v.startedTime,
      ...(v.finishedTime === undefined ? {} : { finished: v.finishedTime }),
      state: v.state,
      ...(v.reason === undefined ? {} : { reason: v.reason }),
      ...(v.pages === undefined ? {} : { pages: v.pages }),
    };
    if (compare) {
      const a = numbersAt(styleVariantOf(v, 'A'));
      const b = numbersAt(styleVariantOf(v, 'B'));
      const loadWords: NonNullable<AllSummaryRow['loadWords']> = {};
      for (const style of STYLES) {
        const load = fileAt(styleVariantOf(v, style));
        if (load !== undefined) loadWords[style] = load;
      }
      return [
        {
          ...head,
          issues: { A: a.issues, B: b.issues },
          misses: { A: a.misses, B: b.misses },
          fixed: { A: a.fixed, B: b.fixed },
          loadWords,
        },
      ];
    }
    const variant = digestVariantOf(v, 'single');
    const n = numbersAt(variant);
    const loadWord = fileAt(variant);
    return [
      {
        ...head,
        issues: n.issues,
        misses: n.misses,
        fixed: n.fixed,
        ...(loadWord === undefined ? {} : { loadWord }),
      },
    ];
  });
  const anyAutofix = done.some((v) =>
    (compare ?
      STYLES.map((style) => styleVariantOf(v, style))
    : [digestVariantOf(v, 'single')]
    ).some((variant) => (variant?.files.autofix ?? null) !== null),
  );
  const states = parts.map((p) => ({ state: stateOf(p) }));
  return (
    <AllSummary
      stats={stats}
      {...(pdfBatch ? { statColumns: 5 as const } : {})}
      rows={rows}
      compare={compare}
      {...(states.some((s) => isActive(s.state)) ?
        { remainingLine: remainingLine(states) }
      : {})}
      onOpenPart={onOpenPart}
      downloadAll={{
        disabled: !anyAutofix,
        busyLabel: run.downloading,
        ...(archive.error === undefined ? {} : { archiveError: archive.error }),
        ...(archive.missing === undefined ?
          {}
        : { missingCount: archive.missing }),
        load: async () => {
          setArchive({});
          const got = await store.archive(view.documentId, view.batchKey);
          if (got.kind === 'too_large') {
            setArchive({ error: 'too_large' });
            return { kind: 'handled' as const };
          }
          // 받을 것이 없음(409 NO_FINISHED_PARTS)은 단추를 끈 꼴과 같은 뜻 — 그 글(noFiles)을 보인다(TRP1 W4, 일반 실패 글 아님).
          if (got.kind === 'nothing') {
            setArchive({ error: 'nothing' });
            return { kind: 'handled' as const };
          }
          if (got.missing > 0) setArchive({ missing: got.missing });
          return { blob: got.blob, fileName: got.fileName };
        },
      }}
    />
  );
}

function PartTab({
  store,
  batchId,
  fileName,
  view,
  label,
  single,
  fileOf,
  onBack,
  onOpenPdf,
  returned,
  retry,
}: {
  store: TranslationStore;
  /** 묶음 줄 id(진행 카드가 쪽 수를 이미 보였는지의 열쇠). */
  batchId: string;
  fileName: string;
  view: PartView;
  label: VariantLabel;
  single: boolean;
  fileOf: (runId: string, name: string) => () => Promise<FileDownload>;
  onBack(): void;
  onOpenPdf?: RunScreenProps['onOpenPdf'];
  returned?: SummaryRow;
  retry?: PartRetry;
}) {
  const pdf = isPdfFlow(view.run.flowId);
  if (isActive(view.state)) {
    const stage = stageOf(view.run);
    const metaLine = TR_TEXT.stage.meta(
      partTitle(view),
      styleText(view),
      view.started,
    );
    // 파트마다 열쇠를 달아 다른 파트 탭으로 옮기면 새로 붙는다(앞 파트의 쪽 수에서 굴러가지 않게). 대기 → 진행은 같은 열쇠라 그대로.
    const seenKey = `${batchId}/${view.part}`;
    return view.state === 'queued' ?
        <StageCard
          key={seenKey}
          seenKey={seenKey}
          stageIndex={1}
          stages={['todo', 'todo', 'todo']}
          meta={partTitle(view)}
          compact
          bare
          queuedText={TR_TEXT.stage.queued(
            names[view.part],
            view.rangeText ?? TR_TEXT.stats.none,
          )}
        />
      : <StageCard
          key={seenKey}
          seenKey={seenKey}
          stageIndex={stage.stageIndex}
          stages={stage.stages}
          {...(view.pages === undefined ? {} : { pages: view.pages })}
          meta={metaLine}
          bare
          {...(pdf ? { pdf: true } : {})}
        />;
  }
  const kind = failureKindOf(view);
  if (kind === 'server_error' || kind === 'rejected')
    return (
      // 거절(rejected)은 retry 를 받지 않는다(useRetryPart) — 단추 0.
      <div className="flex flex-col gap-3">
        <PartFailureCard
          kind={kind}
          {...(view.reason === undefined ? {} : { reason: view.reason })}
          fileLine={`${fileName} · ${partTitle(view)}`}
          single={single}
          onBack={onBack}
          {...(pdf ? { pdf: pdfFailureOf(view) } : {})}
          {...(retry === undefined ?
            {}
          : { onRetry: retry.onRetry, retrying: retry.retrying })}
        />
        {retry?.failed && <RetryFailed />}
      </div>
    );
  return (
    <FinishedPart
      store={store}
      view={view}
      label={label}
      single={single}
      fileOf={fileOf}
      {...(onOpenPdf === undefined ? {} : { onOpenPdf })}
      {...(returned === undefined ? {} : { returned })}
      {...(retry === undefined ? {} : { again: retry })}
    />
  );
}

/** PDF 흐름 파트의 실패 갈래(W8 — 서버 문장은 보지 않는다). */
function pdfFailureOf(view: PartView): 'run' | 'unreadable' | 'no_text' {
  if (view.run.errorCode === 'no_text_layer') return 'no_text';
  if (view.reason === 'bad_file') return 'unreadable';
  return 'run';
}

function FinishedPart({
  store,
  view,
  label,
  single,
  fileOf,
  onOpenPdf,
  returned,
  again,
}: {
  store: TranslationStore;
  view: PartView;
  label: VariantLabel;
  single: boolean;
  fileOf: (runId: string, name: string) => () => Promise<FileDownload>;
  onOpenPdf?: RunScreenProps['onOpenPdf'];
  returned?: SummaryRow;
  /** 일부 쪽(failed_partial)만 — 결과 머리에 [이 파트만 다시](시안 TR-04a). */
  again?: PartRetry;
}) {
  const { status, retry } = useResult(store, view.runId);
  // PDF 결과 판별 = 실행 정보의 resultShapes 에 layout@1(W3). 못 읽으면 워드 꼴(단추 0).
  // 실행 정보는 PDF 흐름(latest.flowId) 파트만 읽는다 — 워드 파트는 요청 0(R14).
  const info = useRunInfo(
    store,
    onOpenPdf !== undefined && isPdfFlow(view.run.flowId) ? view.runId : null,
  ).status;
  const hasPdf =
    onOpenPdf !== undefined &&
    info.state === 'ready' &&
    info.info.resultShapes.includes(LAYOUT_SHAPE);
  const layout = useLayout(store, hasPdf ? view.runId : null).status;
  // PDF 흐름 파트인지(실행 정보를 기다리지 않는다 — 흐름은 묶음 칸).
  const pdfFiles = isPdfFlow(view.run.flowId);
  const late = useDelayed(status.state === 'loading');
  const variant = digestVariantOf(view, label);
  const files = variant?.files;
  const digest = view.run.digest;
  const n = numbersOf(digest, variant);
  const words = TR_TEXT.stats;
  const name = names[view.part];
  // 파트가 하나뿐인 PDF 묶음([전체] 탭이 없음)은 이 탭에 [전체]와 같은 다섯 칸 — 번역한·번역하지 못한 페이지·확인할 곳·용어집 미반영·검수 이슈
  //   (밴드 TRW7 ③b — 디자인 74 답 1·10-29 확인: 「자동 수정한 페이지」 대신 검수 이슈, 판 P04 W10). 파트가 여럿이면 넷 그대로.
  //   다섯 칸인지는 흐름으로 바로 정한다(밴드 TRW8 ⑧ — 처음부터 5칸): 실행 정보·layout 을 읽는 동안 「확인할 곳」은 pending,
  //   layout 이 없거나 못 읽으면 값 「–」·누름 0(감독 답 Q1).
  const pdfSummary = single && pdfFiles && onOpenPdf !== undefined;
  const checks =
    pdfSummary && hasPdf && layout.state === 'ready' ?
      pdfChecksOf(layout.layout, label)
    : null;
  const checksPending =
    pdfSummary &&
    (info.state === 'loading' || (hasPdf && layout.state === 'loading'));
  const checksTile: StatTile[] =
    !pdfSummary ? []
    : checksPending ?
      [
        {
          key: 'checks',
          label: words.labels.checks,
          value: null,
          unit: 'place',
          pending: true,
        },
      ]
    : checks === null ?
      [
        {
          key: 'checks',
          label: words.labels.checks,
          value: null,
          unit: 'place',
        },
      ]
    : [
        {
          key: 'checks',
          label: words.labels.checks,
          value: checks.total,
          unit: 'place',
          note: words.notes.checks(checks.pages),
          ...(checks.first === null || onOpenPdf === undefined ?
            {}
          : {
              onOpen: () =>
                onOpenPdf(view.runId, {
                  page: checks.first!,
                  pair: null,
                  label: checks.shown,
                  from: null,
                  filter: 'checks',
                }),
            }),
        },
      ];
  const stats: StatTile[] = [
    {
      key: 'translated',
      label: words.labels.translated,
      value: n.translated,
      unit: 'page',
      ...(n.pageCount === null ? {}
      : !pdfSummary ? { note: words.notes.outOf(n.pageCount) }
      : {
          note: words.notes.outOfImages(n.pageCount, checks?.images ?? null),
        }),
    },
    {
      key: 'untranslated',
      label: words.labels.untranslated,
      value: n.failedPages === null ? null : n.failedPages.length,
      unit: 'page',
      ...(n.failedPages === null ? {}
      : n.failedPages.length === 0 ? { note: words.notes.allTranslated }
      : { note: result.failedPagesNote(n.failedPages) }),
    },
    ...checksTile,
    {
      key: 'glossaryMiss',
      label: words.labels.glossaryMiss,
      value: n.misses,
      unit: 'count',
      note:
        n.failedPages !== null && n.failedPages.length > 0 ?
          words.notes.untranslatedCounted(n.failedPages.length)
        : words.notes.partGlossary(name),
    },
    !pdfSummary ?
      {
        key: 'fixed',
        label: words.labels.fixed,
        value: n.fixed,
        unit: 'page',
        note: n.fixed === null ? words.notes.fixNotRun : words.notes.fixedBasis,
      }
    : {
        key: 'issues',
        label: words.labels.issues,
        value: n.issues,
        unit: 'count',
        ...(n.fixed === null ? {} : { note: words.notes.issuesBasis(n.fixed) }),
      },
  ];
  const loaders = {
    ...(files?.bilingual ?
      { bilingual: fileOf(view.runId, files.bilingual) }
    : {}),
    ...(files?.qa ? { review: fileOf(view.runId, files.qa) } : {}),
    ...(files?.autofix ? { autofix: fileOf(view.runId, files.autofix) } : {}),
  };
  const reviewStoppedAt =
    variant?.reviewStatus === 'call_failed' ? variant.reviewStoppedAt : null;
  const end = view.range?.to ?? null;
  // 검수 멈춤은 error, 번역 못 한 쪽은 important(밴드 TRP2 TC24, 시안 TR-04a e-info--invalid·--important). 요약(digest)만으로 짓는다.
  const notices: { tone: 'important' | 'error'; text: string }[] = [
    ...(reviewStoppedAt !== null && end !== null ?
      [
        {
          tone: 'error' as const,
          text: result.notices.reviewStopped(reviewStoppedAt, end),
        },
      ]
    : []),
    ...(n.failedPages !== null && n.failedPages.length > 0 ?
      [
        {
          tone: 'important' as const,
          text: result.notices.untranslated(n.failedPages),
        },
      ]
    : []),
  ];
  // 차례(밴드 TRP2 TE12, 시안 TR-04·04a): 머리 → (단계 줄 · 안내) → 수 칸 → 확인할 쪽 → 이슈 → 용어집 미반영(한 칸 전체).
  //   내려받기 카드는 없앴다(밴드 TRW14 감독 답 Q7 — TR-04a r2 는 머리 [내려받기] → 모달뿐). 결과를 못 읽어도 머리 [내려받기]는 있다.
  return (
    // 스타일 탭을 바꾸면 이 div 만 새로 붙어 비친다 — 훅(useResult)은 FinishedPart 몸이라 다시 부르지 않는다(밴드 TRP4 ②-6)
    <div key={label} className="gw-m-fade flex flex-col gap-6">
      {view.range !== null && (
        <PartResultHeader
          part={view.part}
          range={view.range}
          state={view.state}
          round={view.round}
          style={styleText(view)}
          glossaryCount={view.glossaryCount}
          started={view.started}
          {...(view.finished === undefined ? {} : { finished: view.finished })}
          files={loaders}
          single={single}
          {...(again === undefined ?
            {}
          : { onRetry: again.onRetry, retrying: again.retrying })}
        />
      )}
      {again?.failed && <RetryFailed />}
      {view.state === 'failed_partial' && digest !== null && variant && (
        <StepLine steps={stepLines(stepLineOf(digest, variant))} />
      )}
      {notices.length > 0 && <ResultNotices notices={notices} />}
      <StatTiles
        items={stats}
        {...(pdfSummary ? { columns: 5 as const } : {})}
      />
      {late && <LoadSkeleton />}
      {status.state !== 'loading' && status.state !== 'ready' && (
        <LoadFailure
          kind="failed"
          message={run.resultFailed}
          onRetry={retry}
          retryLabel={TR_TEXT.list.retry}
        />
      )}
      {status.state === 'ready' && status.result.status === 'done' && (
        <ResultBody
          variant={
            status.result.variants.find((v) => v.label === label) ??
            status.result.variants[0]!
          }
          start={view.range?.from ?? null}
          reviewStoppedAt={reviewStoppedAt}
          {...(hasPdf && layout.state === 'ready' ?
            {
              pdf: {
                label,
                pairsOf: (page: number) =>
                  pdfPageOf(layout.layout, label, page).pairs,
                onOpen: (focus: PdfOpenFocus, row: SummaryRow) =>
                  onOpenPdf(view.runId, focus, row),
                ...(returned === undefined ? {} : { returned }),
              },
            }
          : {})}
        />
      )}
    </div>
  );
}

function ResultBody({
  variant,
  start,
  reviewStoppedAt,
  pdf,
}: {
  variant: Parameters<typeof issuesOf>[0];
  start: number | null;
  reviewStoppedAt: number | null;
  /** PDF 파트(layout 을 받은 뒤): 고른 문체의 쪽 짝 · 「자리」 누름. 없으면 「자리」 칸 0. */
  pdf?: {
    /** 짝 자리를 센 문체(요약의 스타일 탭). */
    label: VariantLabel;
    pairsOf(page: number): ReturnType<typeof pdfPageOf>['pairs'];
    onOpen(focus: PdfOpenFocus, row: SummaryRow): void;
    /** 돌아온 표 줄(이 실행·이 문체). */
    returned?: SummaryRow;
  };
}) {
  const { issues } = issuesOf(variant);
  const misses = missesOf(variant);
  const places =
    pdf === undefined ? null : placesOf(pdf.pairsOf, { issues, misses });
  const placeText = (place: PdfPlace) =>
    place.pair === null ?
      TR_TEXT.pdfView.placeWhole(place.page)
    : TR_TEXT.pdfView.placeUnit(place.page, place.pair + 1);
  const issueProps =
    pdf === undefined || places === null ?
      {}
    : {
        placeOf: (issue: QaIssue) =>
          placeText(places.issues[issues.indexOf(issue)]!),
        onRow: (issue: QaIssue) => {
          const index = issues.indexOf(issue);
          const place = places.issues[index]!;
          pdf.onOpen(
            {
              ...place,
              label: pdf.label,
              from: {
                where: placeText(place),
                type: TR_TEXT.issues.types[issue.type],
              },
            },
            { table: 'issues', index },
          );
        },
        ...(pdf.returned?.table === 'issues' ?
          { returned: pdf.returned.index }
        : {}),
      };
  const missProps =
    pdf === undefined || places === null ?
      {}
    : {
        placeOf: (row: MissRow) =>
          placeText(places.misses[misses.indexOf(row)]!),
        onRow: (row: MissRow) => {
          const index = misses.indexOf(row);
          pdf.onOpen(
            { ...places.misses[index]!, label: pdf.label, from: null },
            { table: 'misses', index },
          );
        },
        ...(pdf.returned?.table === 'misses' ?
          { returned: pdf.returned.index }
        : {}),
      };
  const checks = checkRowsOf(variant);
  // 검수가 멈췄으면 기준 글에 검수한 쪽과 건수(TC26). 첫 쪽에서 멈췄으면 쪽 구간이 없어 기본 글.
  const reviewed = reviewedRangeOf(start, reviewStoppedAt);
  const basis =
    reviewed === null ? undefined : (
      TR_TEXT.issues.basisStopped(reviewed.from, reviewed.to, issues.length)
    );
  return (
    <>
      {checks.length > 0 && <PagesToCheck rows={checks.map(checkText)} />}
      <QaIssueTable
        issues={issues}
        {...(basis === undefined ? {} : { basis })}
        {...issueProps}
      />
      <GlossaryMissTable rows={misses} {...missProps} />
    </>
  );
}

/** 확인할 쪽 한 줄 → 글(번역·검수 칸은 배지 변형과 함께 — 밴드 TRP2 TC2, 시안 TR-04a: 실패 orange · 완료·검수함 success · 멈춤 error · 돌리지 않음 grey). */
function checkText(row: CheckRow) {
  const words = result.check;
  return {
    pages: row.pages,
    translate:
      row.translate === 'failed' ?
        { text: words.failed, look: 'orange' as const }
      : { text: words.done, look: 'success' as const },
    review:
      row.review.kind === 'reviewed' ?
        { text: words.reviewed, look: 'success' as const }
      : row.review.kind === 'not_run' ?
        { text: words.notRun, look: 'grey' as const }
      : { text: words.stoppedAt(row.review.page), look: 'error' as const },
    reason: row.reasons
      .map((reason) => {
        switch (reason.kind) {
          case 'call_failed':
            return words.callFailed;
          case 'korean_left':
            return words.koreanLeft;
          case 'not_reviewed_after':
            return words.notReviewedAfter(reason.page);
          case 'review_call_failed':
            return words.reviewCallFailed;
          case 'earlier_stopped':
            return words.earlierStopped;
        }
      })
      .join(' · '),
  };
}

/** 단계 줄 값 → 글. */
function stepLines(line: ReturnType<typeof stepLineOf>) {
  // 값마다 배지 변형(밴드 TRP2 TC2·TC25, 시안 TR-04a): 완료·병기 번역본만 success · 일부 쪽 실패 orange · 멈춤 error · 돌리지 않음 grey.
  const value = (step: StepValue): { text: string; look: StatusLook } => {
    const words = result.stepValues;
    switch (step.kind) {
      case 'done':
        return { text: words.done, look: 'success' };
      case 'failed_pages':
        return { text: words.failedPages(step.n), look: 'orange' };
      case 'stopped_at':
        return { text: words.stoppedAt(step.page), look: 'error' };
      case 'not_run':
        return { text: words.notRun, look: 'grey' };
      case 'bilingual_only':
        return { text: words.bilingualOnly, look: 'success' };
    }
  };
  return (['translate', 'glossary', 'review', 'autofix', 'word'] as const).map(
    (key) => ({ name: result.steps[key], ...value(line[key]) }),
  );
}
