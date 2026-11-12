// DV-04·04a 결과(밴드 DV2a ③, 시안 v148 DV-04_r1·DV-04a_r1 + 2e ①②③⑥⑦). 라우터를 모른다 — 저장소와 콜백 props 를 받는다.
// 머리(출처 글 — 파일 이름·「붙여 넣은 데이터」, 출처 없는 옛 실행·실행을 못 읽음은 기업명(DV2b) · 배지 완료 · 「일부 단계 못 함」 · 메타 「<끝> 끝남 · 기업 · 보고연도 · 테마 환경 n항목(핵심 n) · 연도」 — 「1회차」 0)
//   · [다시 실행]·[내려받기] → STEP 3 → 단계 줄 → 띠(2e ③ — 모두 주황, 계산 계획 → 검토 → 인사이트 차례 · 테마 없음 경고) → 칸 넷(2e ②)
//   → 계산 계획 표(done 일 때만) → 검증 결과 표(「어긋남·계산 못 함만」, 펼침 = 계산 식 2e ①, 도구 오류 줄 2e ⑥)
//   → 리스크 표(unparsed 원문 · 빈 표 · 실패 · 실패 + 일부 원문, 출처 0 이면 칸 숨김) · 검토 글(md 서식 — 공통 MarkdownText, 밴드 DV10)이 끝.
// [내려받기](밴드 DV15 — DV-04b r1, sid:MARC-ENT-662 꼴 · sid:MARC-ENT-663 자리): 머리 단추 하나가 공용 받기 모달(shared/ui/download-dialog)을 연다.
//   모달 = 결과 엑셀 한 줄(꺼진 줄·각주 없음), 저장은 부품이 한다. 옛 맨 아래 결과 엑셀 카드는 걷었다.
// 실행(GET /runs/{id})은 끝 시각·파일 목록에만 쓴다 — [내려받기]는 files 에 dataverify-report.xlsx 가 있을 때만(없으면 단추 0 — DV-04a 도 같다).
// 결과가 아직이면(409 RUN_NOT_DONE) onNotDone(쓰는 쪽이 DV-03 으로 replace). 없음 → 「결과를 찾을 수 없어요」, 그 밖 → CM-03 꼴.
// 서버 message·failure.message 는 보이지 않는다. 없는 값은 「–」.
// 검증 결과·리스크 표 = 공용 DataTable(rowSpanOf·renderExpanded·rowAttrs, 밴드 DVW1 · sid:MARC-ISSUE-384). 긴 칸 위아래 12 는 칸 안 감싸개 — DataTable 칸 클래스 계약 없음.
import { useEffect, useId, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';

import {
  ChevronDownIcon,
  ChevronUpIcon,
  CircleWarningIcon,
  DownloadIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import type { BadgeProps } from '@marcspon/ui/components/badge';

import type { DataverifyStore } from '../../../entities/dataverify/api/index.ts';
import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import {
  useRerun,
  useResult,
  useRun,
} from '../../../entities/dataverify/hooks/index.ts';
import {
  REPORT_FILE_NAME,
  STAGES,
  atText,
  decimalSum,
  hasNoTarget,
  isWebLink,
  notices,
  onlyProblems,
  resultCounts,
  someStageFailed,
  stageState,
} from '../../../entities/dataverify/model/index.ts';
import type {
  CheckLine,
  CheckSummary,
  DataverifyResult,
  DataverifyRun,
  InsightRow,
  Notice,
  StageState,
  Verdict,
  WebSource,
  YearLine,
} from '../../../entities/dataverify/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { DownloadDialog } from '../../../shared/ui/download-dialog/index.ts';
import { ReportXlsxIcon } from '../../../shared/ui/file-type-icon/index.ts';
import { LinkChip } from '../../../shared/ui/link-chip/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import {
  LoadSkeleton,
  useDelayed,
} from '../../../shared/ui/load-skeleton/index.ts';
import { MarkdownText } from '../../../shared/ui/markdown/index.ts';
import { CountUp } from '../../../shared/ui/motion/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { StepFlow } from '../../../shared/ui/step-flow/index.ts';

const words = DV_TEXT.result;
const common = DV_TEXT.common;
const dash = DV_TEXT.dash;

const STAGE_BADGE: Record<StageState, BadgeProps['variant']> = {
  done: 'success',
  partial: 'success',
  failed: 'error',
  not_run: 'grey',
};
const VERDICT_BADGE: Record<Verdict, BadgeProps['variant']> = {
  ok: 'success',
  mismatch: 'error',
  uncomputable: 'orange',
};

export interface ResultScreenProps {
  store: DataverifyStore;
  runId: string;
  /** [목록으로](불러오지 못함·없음). */
  onBack(): void;
  /** [다시 실행]으로 새 실행이 생겼을 때. */
  onRerun(runId: string): void;
  /** 아직 끝나지 않은 실행(409) — 쓰는 쪽이 DV-03 으로 replace. */
  onNotDone(): void;
}

export function ResultScreen({
  store,
  runId,
  onBack,
  onRerun,
  onNotDone,
}: ResultScreenProps) {
  const { status: result, retry } = useResult(store, runId);
  const { status: run } = useRun(store, runId);
  const rerun = useRerun(store, runId);
  const notDone = result.state === 'not_done';
  useEffect(() => {
    if (notDone) onNotDone();
  }, [notDone, onNotDone]);
  const loading =
    result.state === 'loading' || notDone || run.state === 'loading';
  const skeleton = useDelayed(loading);

  if (result.state !== 'ready' || run.state === 'loading')
    return (
      <div
        data-screen="dataverify-result"
        data-result-state={loading ? 'loading' : result.state}
        aria-busy={loading || undefined}
        className="flex flex-col gap-6"
      >
        {/* 읽는 동안은 제목·메타 자리만(셸 제목을 그렸다가 출처 제목으로 바꾸지 않는다 — 밴드 DV2e, sid:MARC-ENT-443 ④). */}
        <PageTitle
          title={DV_TEXT.shell.title}
          titlePending={loading}
          descriptionPending={loading}
        />
        {result.state === 'missing' ?
          <LoadFailure
            kind="missing"
            message={common.notFound}
            listLabel={common.toList}
            onList={onBack}
          />
        : result.state === 'failed' ?
          <LoadFailure
            kind="failed"
            message={words.loadFailed}
            retryLabel={common.retry}
            listLabel={common.toList}
            onRetry={retry}
            onList={onBack}
          />
        : skeleton && <LoadSkeleton />}
      </div>
    );

  const readyRun = run.state === 'ready' ? run.run : null;
  const download =
    readyRun !== null && readyRun.files.includes(REPORT_FILE_NAME) ?
      <HeadDownload load={() => store.reportFile(runId)} />
    : null;
  return (
    <ResultView
      result={result.result}
      run={readyRun}
      download={download}
      rerunError={rerun.failed}
      rerunButton={
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          loading={rerun.rerunning}
          onClick={async () => {
            const next = await rerun.rerun();
            if (next !== null) onRerun(next);
          }}
        >
          {common.rerun}
        </Button>
      }
    />
  );
}

function ResultView({
  result,
  run,
  download,
  rerunError,
  rerunButton,
}: {
  result: DataverifyResult;
  run: DataverifyRun | null;
  download: ReactNode;
  rerunError: boolean;
  rerunButton: ReactNode;
}) {
  const { lines, summary, risks } = resultCounts(result);
  const { company, scope, plan, review } = result;
  const finished =
    run === null ? dash : atText(run.finishedAt ?? run.createdAt);
  const bands = notices(result);
  const noTarget = hasNoTarget(result);
  return (
    <div data-screen="dataverify-result" className="flex flex-col gap-6">
      <PageTitle
        title={
          <span className="inline-flex flex-wrap items-center gap-2">
            {DV_TEXT.source.title(run?.source ?? null, company.name)}
            <Badge variant="success">{words.done}</Badge>
            {someStageFailed(result) && (
              <Badge variant="orange" data-testid="some-failed">
                {words.someFailed}
              </Badge>
            )}
          </span>
        }
        description={
          <span data-testid="meta">
            {words.meta(
              finished,
              company.name,
              company.reportingYear,
              scope.itemCount,
              scope.keyItemCount,
              DV_TEXT.yearSpan(scope.years),
            )}
          </span>
        }
        actions={
          <>
            {rerunButton}
            {download}
          </>
        }
      />
      {rerunError && (
        <PageInfo
          tone="error"
          role="alert"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="rerun-error"
        >
          {DV_TEXT.newCheck.errors.startFailed}
        </PageInfo>
      )}
      <StepFlow
        current={3}
        steps={DV_TEXT.steps.items.map((item) => item.label)}
        label={DV_TEXT.steps.label}
      />

      {/* 「단계」 400 12 · 이름 400 16 · 사이 「·」(시안 DV-04 .g-row — 영문번역 PagesToCheck StepLine 꼴, 밴드 DV3 W11) */}
      <p
        data-testid="stages"
        className="m-0 flex flex-wrap items-center gap-x-2 text-style-pre-body-03 text-text-secondary"
      >
        <span className="text-style-pre-caption-03 text-text-tertiary">
          {words.stagesLabel}
        </span>
        {STAGES.map((stage, index) => {
          const state = stageState(result, stage);
          return (
            <span
              key={stage}
              data-stage={stage}
              data-state={state}
              className="inline-flex items-center gap-1"
            >
              {index > 0 && (
                <span aria-hidden className="mr-2 text-text-quaternary">
                  ·
                </span>
              )}
              {words.stageNames[stage]}
              <Badge variant={STAGE_BADGE[state]}>
                {words.stageState[state]}
              </Badge>
              {state === 'partial' && (
                <span className="text-style-pre-caption-03 text-text-tertiary">
                  {words.partialTag}
                </span>
              )}
            </span>
          );
        })}
      </p>

      {bands.map((notice) => (
        <PageInfo
          key={notice}
          tone="important"
          icon={<PageInfoIcon />}
          data-testid="band"
          data-notice={notice}
          className="gw-m-rise"
        >
          {bandText(notice, result, summary)}
        </PageInfo>
      ))}
      {noTarget && (
        <PageInfo
          tone="important"
          icon={<PageInfoIcon />}
          data-testid="band"
          data-notice="no_target"
          className="gw-m-rise"
        >
          {DV_TEXT.notices.noTarget}
        </PageInfo>
      )}

      <Cards summary={summary} risks={risks} result={result} />

      {plan.status === 'done' && <PlanCard formulas={plan.formulas} />}

      <ChecksCard
        lines={lines}
        failed={review.status === 'failed'}
        places={summary.places}
        tolerance={result.tolerance}
      />

      <RisksCard result={result} />

      {review.status === 'done' && (
        <FoldCard
          card="review"
          title={words.reviewTitle}
          lead={words.reviewLead}
        >
          <MarkdownText data-testid="review-text">{review.report}</MarkdownText>
        </FoldCard>
      )}
    </div>
  );
}

/** 머리 [내려받기](outlineGrey round md + 받기 아이콘 왼쪽 — 다섯 모듈 같은 꼴, 디자인 c3 11-11) — 누르면 공용 받기 모달(열 때만 그린다, 닫히면 초점은 이 단추로). 단추 자체는 받지 않는다. */
function HeadDownload({
  load,
}: {
  load: () => Promise<{ blob: Blob; fileName: string }>;
}) {
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const text = words.downloads;
  return (
    <>
      <Button
        ref={opener}
        variant="outlineGrey"
        shape="round"
        size="md"
        data-testid="download-head"
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        <DownloadIcon aria-hidden />
        {common.download}
      </Button>
      {open && (
        <DownloadDialog
          testId="download-dialog"
          title={common.download}
          closeLabel={text.close}
          helpLabel={text.help}
          failedText={common.downloadFailed}
          busyLabel={text.busy}
          files={[
            {
              key: 'report',
              name: text.reportName,
              description: text.reportNote,
              fileLabel: REPORT_FILE_NAME,
              icon: <ReportXlsxIcon />,
              download: load,
            },
          ]}
          onClose={() => setOpen(false)}
          returnFocus={() => opener.current}
        />
      )}
    </>
  );
}

function bandText(
  notice: Notice,
  result: DataverifyResult,
  summary: CheckSummary,
): string {
  const text = DV_TEXT.notices;
  if (notice === 'review_partial')
    return text.review_partial.band(
      result.plan.status === 'done' ? result.plan.formulas.length : 0,
    );
  if (notice === 'review_failed')
    return text.review_failed.band(summary.places);
  return text[notice].band;
}

interface PlanRow {
  no: number;
  formula: string;
}

/** 계산 계획 표(정적 — 정렬 없음. 산식 한 열 — 번호 열은 검증 결과·검토 글 번호와 이어지지 않아 걷었다, 밴드 DV17). */
const PLAN_COLUMNS: DataTableColumnDef<PlanRow>[] = [
  {
    id: 'formula',
    accessorKey: 'formula',
    header: words.planHead[0],
    enableSorting: false,
    cell: ({ row }) => (
      <span className="whitespace-pre-wrap">{row.original.formula}</span>
    ),
  },
];

/** 표 긴 칸 위아래 12(시안 .e-table 긴 칸 mod-r1.css 8). 공용 DataTable 을 고치지 않고 칸 자손으로 덮는다. */
const ROW_PADDING = '[&_td]:py-3';

function PlanCard({ formulas }: { formulas: readonly string[] }) {
  const table = useDataTable({
    data: formulas.map((formula, index) => ({ no: index + 1, formula })),
    columns: PLAN_COLUMNS,
    getRowId: (row) => String(row.no),
  });
  return (
    <FoldCard
      card="plan"
      title={words.planTitle}
      lead={words.planLead(formulas.length)}
    >
      <DataTable
        table={table}
        aria-label={words.planTitle}
        layout="fixed"
        className={ROW_PADDING}
      />
    </FoldCard>
  );
}

function Cards({
  summary,
  risks,
  result,
}: {
  summary: CheckSummary;
  risks: number | null;
  result: DataverifyResult;
}) {
  const cards = words.cards;
  const { insight } = result;
  // 큰 수가 「–」인 갈래: 표로 못 나눔(done) · 못 함(실패·돌지 않음) — 2e ②.
  const risksSub =
    insight.status !== 'done' ? cards.risksNone
    : risks === null ? cards.risksUnparsed
    : cards.risksSub;
  return (
    // 검산 넷(검산 = 맞음 + 어긋남 + 계산 못 함) ┃ 리스크 — 시안 v212 DV-04 r2 .dv-kv(좁으면 두 칸·선 숨김, 밴드 DV7).
    <div
      data-testid="cards"
      className="grid grid-cols-2 gap-4 lg:grid-cols-[repeat(4,minmax(0,1fr))_auto_minmax(0,1fr)]"
    >
      <Stat
        order={0}
        id="checks"
        label={cards.checks}
        value={summary.places}
        unit={cards.units.checks}
        sub={cards.checksSub}
      />
      <Stat
        order={1}
        id="ok"
        label={cards.ok}
        value={summary.okYears}
        unit={cards.units.ok}
        sub={cards.okSub(result.tolerance)}
      />
      <Stat
        order={2}
        id="mismatches"
        label={cards.mismatches}
        value={summary.mismatches}
        unit={cards.units.mismatches}
        sub={cards.mismatchesSub(result.tolerance)}
      />
      <Stat
        order={3}
        id="uncomputable"
        label={cards.uncomputable}
        value={summary.uncomputable}
        unit={cards.units.uncomputable}
        sub={cards.uncomputableSub(
          summary.nonNumeric,
          summary.divisionByZero,
          summary.toolErrors,
        )}
      />
      <span
        data-testid="cards-sep"
        aria-hidden="true"
        className="my-2 hidden w-0.5 self-stretch rounded-[2px] bg-border-tertiary lg:block"
      />
      <Stat
        order={4}
        id="risks"
        label={cards.risks}
        value={risks}
        unit={cards.units.risks}
        sub={risksSub}
      />
    </div>
  );
}

/** 수 칸(시안 .g-stat — 영문번역 StatTiles 꼴, 밴드 DV3 W8). 수는 display-03(32 를 주는 토큰이 없다), 단위는 작은 글. stat-<id> 는 수와 단위를 함께 감싼다(글 「2회」). */
/** 칸마다 70ms 씩 늦게 떠오른다(entities/translation/ui/StatTiles.tsx:12-14 의 rise 를 옮겨 적음 — 밴드 DV3 ②-4). */
const rise = (order: number) =>
  ({ '--gw-m-delay': `${order * 70}ms` }) as CSSProperties;

function Stat({
  order,
  id,
  label,
  value,
  unit,
  sub,
}: {
  order: number;
  id: string;
  label: string;
  value: number | null;
  unit: string;
  sub: string;
}) {
  return (
    <Card
      className="gw-m-rise flex flex-col gap-1.5 p-6"
      style={rise(order)}
      data-stat={id}
    >
      <span className="text-style-pre-body-05 text-text-tertiary">{label}</span>
      <span
        data-testid={`stat-${id}`}
        className="text-style-pre-display-03 tabular-nums text-text-primary"
      >
        {value === null ?
          dash
        : <>
            <CountUp value={value} durationMs={800} />
            <small className="ml-1 text-style-pre-body-05 text-text-tertiary">
              {unit}
            </small>
          </>
        }
      </span>
      <span className="text-style-pre-caption-03 text-text-tertiary">
        {sub}
      </span>
    </Card>
  );
}

function ChecksCard({
  lines,
  failed,
  places,
  tolerance,
}: {
  lines: readonly CheckLine[];
  failed: boolean;
  places: number;
  tolerance: string;
}) {
  const [problems, setProblems] = useState(false);
  const shown = problems ? onlyProblems(lines) : lines;
  return (
    <FoldCard
      card="checks"
      title={words.checksTitle}
      lead={
        failed ?
          words.checksLeadFailed(places, tolerance)
        : words.checksLead(tolerance)
      }
      stacked
      tools={
        lines.length > 0 && (
          <label className="flex items-center gap-2 text-style-pre-body-06 text-text-secondary">
            <input
              type="checkbox"
              data-testid="only-problems"
              checked={problems}
              onChange={(event) => setProblems(event.target.checked)}
            />
            {words.onlyProblems}
          </label>
        )
      }
    >
      {lines.length === 0 ?
        <Empty testId="no-checks">{words.noChecks}</Empty>
      : shown.length === 0 ?
        <Empty testId="no-problems">{words.noProblems(tolerance)}</Empty>
        // 거르기를 바꾸면 표가 새로 붙어 비친다(밴드 DV3 ②-6 — 펼침이 지워지는 것은 전과 같다)
      : <div key={String(problems)} className="gw-m-fade">
          <ChecksTable lines={shown} all={lines} />
        </div>
      }
      <p className="m-0 text-style-pre-caption-02 text-text-tertiary">
        {words.checksFootnote}
      </p>
    </FoldCard>
  );
}

/** 검증 결과 표의 줄: 도구 오류 줄 하나 · 검사 줄은 해마다 한 줄(규칙·항목은 첫 해 줄이 rowSpan 으로 덮는다). 순번(line.no)은 줄 id·data-line 에만 — 화면 열 없음(밴드 DV17). */
type CheckRow =
  | { id: string; kind: 'error'; line: Extract<CheckLine, { kind: 'error' }> }
  | {
      id: string;
      kind: 'year';
      line: Extract<CheckLine, { kind: 'check' }>;
      year: YearLine;
      index: number;
    };

/** 해 줄의 첫 줄이 덮는 열(규칙·항목). */
const SPAN_COLUMNS: readonly string[] = ['rule', 'items'];

/**
 * 표 줄. 해 줄 id 는 거르기 전 줄의 「<순번>-<해 차례>」 — 거르기(onlyProblems)는 순번을 다시 매기고 해를 빼지만
 * 해 객체는 그대로 넘기므로 원래 자리로 찾는다(같은 해 글이 둘이어도 겹치지 않는다).
 */
function checkRows(
  lines: readonly CheckLine[],
  all: readonly CheckLine[],
): CheckRow[] {
  const origin = new Map<YearLine, string>();
  for (const line of all)
    if (line.kind === 'check')
      line.years.forEach((year, index) =>
        origin.set(year, `${line.no}-${index}`),
      );
  return lines.flatMap((line): CheckRow[] =>
    line.kind === 'error' ?
      [{ id: `${line.no}-e`, kind: 'error', line }]
    : line.years.map((year, index) => ({
        id: origin.get(year) ?? `${line.no}-${index}`,
        kind: 'year',
        line,
        year,
        index,
      })),
  );
}

/** 없는 값 「–」(흐린 글). */
const muted = () => <span className="text-text-tertiary">{dash}</span>;

/** 열 일곱(정렬 없음 — rowSpan 표). 차이·계산 식은 오른쪽. */
function checkColumns(
  open: ReadonlySet<string>,
  toggle: (id: string) => void,
): DataTableColumnDef<CheckRow>[] {
  const head = words.checksHead;
  const column = (
    header: string,
    id: string,
    cell: (row: CheckRow) => ReactNode,
    align?: 'right',
  ): DataTableColumnDef<CheckRow> => ({
    id,
    header,
    enableSorting: false,
    meta: align === undefined ? {} : { align },
    cell: ({ row }) => cell(row.original),
  });
  return [
    column(head[0], 'rule', (row) =>
      row.line.rule === null ? muted() : words.rules[row.line.rule],
    ),
    column(head[1], 'items', (row) =>
      row.kind === 'error' ?
        muted()
      : <div data-testid="items" className={SPAN_BODY}>
          {itemLines(row.line).map((text, index) => (
            <span key={index} className="block">
              {text}
            </span>
          ))}
        </div>,
    ),
    column(head[2], 'year', (row) =>
      row.kind === 'error' || row.year.year === null ? muted() : row.year.year,
    ),
    column(head[3], 'verdict', (row) => {
      const verdict = row.kind === 'error' ? 'uncomputable' : row.year.verdict;
      return (
        <Badge variant={VERDICT_BADGE[verdict]}>
          {words.verdicts[verdict]}
        </Badge>
      );
    }),
    column(
      head[4],
      'diff',
      (row) =>
        row.kind === 'error' || row.year.diff === null ?
          muted()
        : <span className="tabular-nums">{row.year.diff}</span>,
      'right',
    ),
    column(head[5], 'note', (row) =>
      row.kind === 'error' ? <div className={LONG_BODY}>{words.notes.tool}</div>
      : row.year.note === null ? muted()
      : <div className={LONG_BODY}>{words.notes[row.year.note]}</div>,
    ),
    column(
      head[6],
      'formula',
      (row) =>
        row.kind === 'error' ?
          muted()
        : <Button
            variant="outlineGrey"
            shape="round"
            size="sm"
            aria-expanded={open.has(row.id)}
            onClick={() => toggle(row.id)}
          >
            {open.has(row.id) ? words.hide : words.show}
          </Button>,
      'right',
    ),
  ];
}

/** 펼침 상태(줄 id 집합)를 갖는다. 거르기 감싸개 안에 있어 거르기를 바꾸면 다시 붙어 펼침이 지워진다(밴드 DV3 ②-6 그대로). */
function ChecksTable({
  lines,
  all,
}: {
  lines: readonly CheckLine[];
  /** 거르기 전 줄(해 줄 id 의 원래 자리). */
  all: readonly CheckLine[];
}) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const toggle = (id: string) =>
    setOpen((now) => {
      const next = new Set(now);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const table = useDataTable({
    data: checkRows(lines, all),
    columns: checkColumns(open, toggle),
    getRowId: (row) => row.id,
  });
  return (
    <DataTable
      table={table}
      aria-label={words.checksTitle}
      rowSpanOf={(row, column) =>
        row.kind === 'year' && SPAN_COLUMNS.includes(column) ?
          row.index === 0 ?
            row.line.years.length
          : 0
        : undefined
      }
      renderExpanded={(row) =>
        row.kind === 'year' && open.has(row.id) ?
          <FormulaDetail line={row.line} year={row.year} />
        : null
      }
      rowAttrs={(row) =>
        row.kind === 'error' ?
          { 'data-line': String(row.line.no), 'data-kind': 'error' }
        : { 'data-line': String(row.line.no), 'data-verdict': row.year.verdict }
      }
    />
  );
}

/** 항목 칸 줄(판 DV-04 꼴 — 이름형은 여러 줄, 단건은 한 줄). */
function itemLines(line: Extract<CheckLine, { kind: 'check' }>) {
  const items = words.items;
  const view = line.items;
  if (view.rule === 'ratio')
    return (view.byName ? items.ratioByName : items.ratioRaw)(
      view.numerator,
      view.denominator,
      view.expected,
    );
  return (view.byName ? items.sumByName : items.sumRaw)(
    view.target,
    view.addends,
  );
}

/** 펼침 줄 하나(머리 · 머리 뒤 작은 글 · 값). */
interface DetailRow {
  key: 'formula' | 'input' | 'actual' | 'verdict' | 'diff';
  hint?: string;
  value: string;
}

/**
 * 계산 식 펼침의 이름 단 줄 다섯(밴드 DV6 ①): 계산식(항목 칸 줄을 이은 것) · 입력값(파일에 적힌 값 — 합계는 대상, 비율은 적힌 %)
 * · 실제값(다시 계산한 값 — 합계는 더한 값들의 10진 합, 비율은 계산한 %) · 판정 · 차이(+ 허용 오차 안/넘음 — 허용 오차 0 인 검산은 차이만, 밴드 DV16).
 * 계산 못 함은 입력값·실제값·차이 「–」, 실제값 뒤에 이유. 꼴 밖(raw)은 null — 원문 한 줄.
 */
function detailRows(
  line: Extract<CheckLine, { kind: 'check' }>,
  year: YearLine,
): DetailRow[] | null {
  const ex = year.explanation;
  if (ex.kind === 'raw') return null;
  const rows = words.explainRows;
  const formula: DetailRow = {
    key: 'formula',
    value: itemLines(line).join(' '),
  };
  const verdict: DetailRow = {
    key: 'verdict',
    value: words.verdicts[year.verdict],
  };
  const input = (value: string): DetailRow => ({
    key: 'input',
    hint: rows.inputHint,
    value,
  });
  const actual = (value: string): DetailRow => ({
    key: 'actual',
    hint: rows.actualHint,
    value,
  });
  if (ex.kind === 'sum')
    return [
      formula,
      input(ex.target),
      actual(
        rows.actualWith(decimalSum(ex.addends) ?? dash, {
          kind: 'sum',
          addends: ex.addends,
        }),
      ),
      verdict,
      {
        key: 'diff',
        value: rows.diffValue(
          ex.diff,
          'value',
          ex.tolerance,
          ex.within,
          line.items.rule === 'sum' ? line.items.unit : null,
        ),
      },
    ];
  if (ex.kind === 'ratio')
    return [
      formula,
      input(rows.percent(ex.expected)),
      actual(
        rows.actualWith(rows.percent(ex.percent), {
          kind: 'ratio',
          numerator: ex.numerator,
          denominator: ex.denominator,
        }),
      ),
      verdict,
      {
        key: 'diff',
        value: rows.diffValue(ex.diff, 'percent', ex.tolerance, ex.within),
      },
    ];
  const reason =
    ex.kind === 'non_numeric' ?
      words.explain.nonNumeric
    : words.explain.divisionByZero;
  return [
    formula,
    input(dash),
    actual(`${dash} · ${reason}`),
    verdict,
    { key: 'diff', value: dash },
  ];
}

/** 계산 식 펼침(밴드 DV6 ① — 이름 단 줄 다섯, 꼴 밖은 2e ① 그대로 원문 한 줄). */
function FormulaDetail({
  line,
  year,
}: {
  line: Extract<CheckLine, { kind: 'check' }>;
  year: YearLine;
}) {
  const rows = detailRows(line, year);
  if (rows === null)
    return (
      <span data-testid="formula">
        <span className="mr-2 text-style-pre-caption-03 text-text-tertiary">
          {words.formula}
        </span>
        {year.explanation.kind === 'raw' ? year.explanation.text : ''}
      </span>
    );
  return (
    <dl
      data-testid="formula"
      aria-label={words.formula}
      className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1"
    >
      {rows.map((row) => (
        <div key={row.key} data-detail={row.key} className="contents">
          <dt className="text-style-pre-caption-03 text-text-tertiary">
            {words.explainRows[row.key]}
            {row.hint !== undefined && (
              <span className="ml-1">({row.hint})</span>
            )}
          </dt>
          <dd className="tabular-nums whitespace-pre-wrap">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function RisksCard({ result }: { result: DataverifyResult }) {
  const { insight } = result;
  // 세 단계 모두 돌지 않음(테마 없음)이면 리스크 카드도 없다 — 띠가 알린다.
  if (insight.status === 'not_run') return null;
  return (
    <FoldCard card="risks" title={words.risksTitle} lead={words.risksLead}>
      {insight.status === 'failed' ?
        insight.partialText === null ?
          <Empty testId="risks-failed">{words.risksFailed}</Empty>
        : <>
            <Empty testId="risks-partial">{words.risksPartialText}</Empty>
            <Raw>{insight.partialText}</Raw>
          </>

      : insight.rowsParsed === 'unparsed' ?
        <>
          <Empty testId="risks-unparsed">{words.risksUnparsed}</Empty>
          <Raw>{insight.report}</Raw>
        </>
      : insight.rows.length === 0 ?
        <Empty testId="risks-empty">{words.risksEmpty}</Empty>
      : <RisksTable rows={insight.rows} />}
      {insight.status === 'done' && insight.sources.length > 0 && (
        <div data-testid="sources" className="flex flex-col gap-2">
          <h4 className="m-0 text-style-pre-body-04 text-text-primary">
            {words.sources}
          </h4>
          <ul className="m-0 flex list-none flex-wrap items-center gap-x-2 gap-y-1.5 p-0">
            {insight.sources.map((source, index) => (
              <SourceLine key={index} source={source} />
            ))}
          </ul>
        </div>
      )}
    </FoldCard>
  );
}

/** 칩 칸 상한 = 칩 상한(LinkChip CHIP). 칩의 100% 는 flex 항목인 칸을 줄이지 못해, 칸이 ul 기준으로 먼저 줄어야 칩 뒤 빈 자리가 없다(밴드 DV11). */
const CHIP_CELL = 'min-w-0 max-w-[min(100%,calc(theme(spacing.16)*5))]';

/**
 * 출처 한 줄 = 공통 링크 칩(보드 CM-04 r1 · 밴드 DV10). 제목이 있으면 칩 이름 = 제목, 없으면 칩이 주소에서 짓는다.
 * 주소는 받은 글자 그대로 칩에 넘긴다(utm 떼기는 칩이 한다 — 밴드 DV12). 칩이 못 되는 값은 링크 0 인 회색 글(칩과 같은 글 크기) — 제목이 있으면 「제목 · 값」(밴드 DV11).
 */
function SourceLine({ source }: { source: WebSource }) {
  if (isWebLink(source.url))
    return (
      <li className={CHIP_CELL}>
        <LinkChip url={source.url} label={source.title ?? undefined} />
      </li>
    );
  const title = source.title?.trim() ?? '';
  const value = source.url.trim();
  return (
    <li className="min-w-0 max-w-full">
      <LinkChip
        url={source.url}
        label={title !== '' && value !== '' ? `${title} · ${value}` : title}
        className="text-style-pre-caption-02"
      />
    </li>
  );
}

/** 긴 칸(메모·리스크 글) 위아래 12 — 칸 안 감싸개(DataTable 칸 클래스 계약 없음 — DT1 감독 판단 10-28). */
const LONG_BODY = 'py-3';
const RISK_BODY = `${LONG_BODY} whitespace-pre-wrap`;
/**
 * 묶음 칸(항목 — 순번·규칙과 같이 rowSpan) 감싸개는 아래 12 만(밴드 TA1, sid:MARC-ISSUE-600). 위 여백은 공용 DataTable 묶음 칸이
 * (h-14 − 1lh) / 2 로 단다 — 첫 줄이 옆 한 줄 칸 글 높이에 서고 순번·규칙 칸과도 같다.
 */
const SPAN_BODY = 'pb-3';

const riskLong = (text: string) => <div className={RISK_BODY}>{text}</div>;

/** 리스크 표 열 다섯(정렬 없음). 관찰·리스크·해석은 긴 칸. */
const RISK_COLUMNS: DataTableColumnDef<InsightRow>[] = [
  {
    id: 'area',
    accessorKey: 'area',
    header: words.risksHead[0],
    enableSorting: false,
  },
  {
    id: 'indicator',
    accessorKey: 'indicator',
    header: words.risksHead[1],
    enableSorting: false,
  },
  {
    id: 'observation',
    header: words.risksHead[2],
    enableSorting: false,
    cell: ({ row }) => riskLong(row.original.observation),
  },
  {
    id: 'risk',
    header: words.risksHead[3],
    enableSorting: false,
    cell: ({ row }) => riskLong(row.original.risk),
  },
  {
    id: 'interpretation',
    header: words.risksHead[4],
    enableSorting: false,
    cell: ({ row }) => riskLong(row.original.interpretation),
  },
];

function RisksTable({ rows }: { rows: readonly InsightRow[] }) {
  const table = useDataTable({
    data: [...rows],
    columns: RISK_COLUMNS,
    getRowId: (_, index) => String(index),
  });
  return (
    <DataTable
      table={table}
      aria-label={words.risksTitle}
      rowAttrs={() => ({ 'data-testid': 'risk-row' })}
    />
  );
}

/**
 * 접는 카드(계산 계획·검증 결과·리스크·검토 글 — 밴드 DV17, 온실가스 EmissionCard 머리 단추 꼴을 옮겨 적음).
 * 머리 = 제목·꼬리 글(+ tools) · 오른쪽 끝 셰브론 단추. 기본 펼침, 접히면 머리(tools 빼고)만 남고 몸은 그리지 않는다. 상태는 화면 안에만.
 */
function FoldCard({
  card,
  title,
  lead,
  stacked = false,
  tools,
  children,
}: {
  card: 'plan' | 'checks' | 'risks' | 'review';
  title: string;
  lead: string;
  /** 꼬리 글을 제목 아래로 쌓는다(검증 결과). 아니면 제목 왼쪽·꼬리 글 오른쪽 한 줄. */
  stacked?: boolean;
  /** 머리 오른쪽 거르기 등(펼쳤을 때만). */
  tools?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(true);
  const bodyId = `dv-${card}-${useId().replace(/:/g, '')}`;
  return (
    <Card className="flex flex-col gap-4" data-card={card}>
      <div className={`flex gap-4 ${stacked ? 'items-start' : 'items-center'}`}>
        <div className="min-w-0 flex-1">
          <CardHead inline={!stacked} title={title} lead={lead} />
        </div>
        {open && tools}
        <button
          type="button"
          data-testid="fold"
          aria-expanded={open}
          aria-controls={bodyId}
          aria-label={open ? words.fold(title) : words.unfold(title)}
          className="flex size-8 shrink-0 items-center justify-center rounded-md text-text-secondary hover:bg-background-secondary focus-visible:outline-2 [&_svg]:size-5"
          onClick={() => setOpen((now) => !now)}
        >
          {open ?
            <ChevronUpIcon aria-hidden />
          : <ChevronDownIcon aria-hidden />}
        </button>
      </div>
      {open && (
        <div id={bodyId} className="flex flex-col gap-4">
          {children}
        </div>
      )}
    </Card>
  );
}

/** 카드 머리. inline 이면 제목 왼쪽·꼬리 글 오른쪽 한 줄(시안 DV-04 .g-between — 밴드 DV3 J1), 아니면 쌓는다. 꼬리 글 400 12. */
function CardHead({
  title,
  lead,
  inline = false,
}: {
  title: string;
  lead: string;
  inline?: boolean;
}) {
  return (
    <div
      className={
        inline ?
          'flex flex-wrap items-center justify-between gap-4'
        : 'flex flex-col gap-1'
      }
    >
      <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
        {title}
      </h3>
      <span className="text-style-pre-caption-03 text-text-tertiary">
        {lead}
      </span>
    </div>
  );
}

function Empty({ children, testId }: { children: ReactNode; testId: string }) {
  return (
    <p
      data-testid={testId}
      className="m-0 text-style-pre-body-06 text-text-tertiary"
    >
      {children}
    </p>
  );
}

/** AI 가 쓴 원문(md 서식 — 공통 MarkdownText, 원 HTML 은 그리지 않는다 · 밴드 DV10). */
function Raw({ children }: { children: string }) {
  return <MarkdownText data-testid="raw">{children}</MarkdownText>;
}
