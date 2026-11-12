// GW-04 결과 요약(밴드 FW2 ③, v115 GW-04_r2 — 밴드 GW2R). 구성:
//   제목 줄(문서명 + 검토 상태 배지, meta 「시각 · n회차 · 문서 쪽 가운데 점검 쪽 · 검토 n/전체」,
//   오른쪽 [내려받기] · [확정] · [검토 이어 하기]) → StepFlow STEP 3 → 안내 셋(이미지, 확정 전, 실패한 쪽) → 통계 넷 →
//   두 칸(파트별 결과 표 + 겹침 안내 | 그린워싱 리스크 단어 빈도: 문서 전체/파트별 박스 탭, 「추가」 배지는 옛 실행만).
//   v115 에서 뺀 것(sid:MARC-ENT-354·366): 「수정본」 배지, 「자주 나온 위험 유형」, meta 「추가 단어 n개」, 확정 전 안내의 앞 버전 비교 문장.
// 셈은 모두 domain(summary.ts), 결과·검토 읽기는 headless(useResult·useReview·useRunSummary). 이 파일은 그리기만.
//   - [내려받기](밴드 GDL1 — GW-04 r4 · GW-04a r1, 옛 [엑셀 내보내기]를 갈음): 받기 모달(GwDownloads)의 점검 결과 엑셀 한 줄.
//     확정이면 확정본(?confirmed=true), 아니면 확정 전 결과(쿼리 없음) — store.getReport 를 넘긴다.
//     dry-run 결과(엑셀 없음)여도 머리 단추는 켜고, 모달의 줄이 꺼진 꼴(누름이 요청하지 않는다). 실패는 그 줄 아래 role="alert"(D3).
//   - 「앞 버전과 비교」 카드는 그리지 않는다: 계약의 GET /greenwash/compare(greenwash.compare@1)는 지금 501 이고 화면 짝은 아직 없다.
//   - 확정된 실행이면 [확정]을 숨기고 [검토 이어 하기] 대신 [결과 보기](→ GW-05 잠김).
//   - dry-run 결과(items 없음)는 PageInfo 하나와 단어 빈도만.
//   - 파트 이름은 결과의 parts[].name 을 화면 이름으로(partName — 기후/환경 토픽 → 기후·환경, sid:MARC-ISSUE-314), 쪽은 구간 압축 글자(formatPageRange).
//   - 단어 빈도 「파트별」은 파트마다 묶음 하나씩(시안은 문서 전체만 그렸다 — 디자인 물을 것).
//   - 불러오기(밴드 LE1, sid:MARC-ENT-260, 시안 CM-03): 읽는 중은 제목 줄([목록으로] 그대로)·STEP 3 을 두고 본문 자리에 스켈레톤(300ms 뒤).
//     스켈레톤은 받은 뒤 꼴을 닮은 ResultSkeleton(안내 띠 둘 · 통계 넷 · 두 칸 — 밴드 GL2, 카드 하나였을 때 본문이 받은 뒤 줄었다).
//     제목(파일 이름)·설명(meta)은 데이터에서 오니 읽는 중엔 막대 자리(titlePending·descriptionPending — 고정 제목 「결과 요약」을 쓰면
//     받은 뒤 글이 바뀌었다. 밴드 GL1, sid:MARC-ENT-443 ③④).
//     꼴 오류·읽기 실패는 하나의 실패 꼴(STEP 3 + 「결과를 불러오지 못했어요」 + [다시 시도]·[목록으로]), 없음은 회색 「결과를 찾을 수 없어요」 +
//     [목록으로] 하나. 실패·없음에서는 제목 줄 [목록으로]를 빼고 상자의 것 하나만 둔다. 둘레·검토 배지 실패는 조용히.
//     읽는 동안 내내(스켈레톤 300ms 전에도) 화면 바깥 틀에 aria-busy(밴드 LA1 ①). 스켈레톤 카드는 role="status" 만.
//     [다시 시도] 뒤 초점(밴드 LA1 ②, useRetryFocus): 또 실패·없음이면 상자의 첫 단추, 받으면 본문 제목 줄 h2(tabIndex -1).
//   - 기본 단어를 읽지 못하면(null) 「추가」 배지와 막대의 data-extra 를 끈다(빈 목록으로 보면 추가 단어가 모두 「추가」 — 틀린 정보).
import { useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';

import { Badge } from '@marcspon/ui/components/badge';

import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import {
  useResult,
  useReview,
} from '../../../entities/greenwash/hooks/index.ts';
import {
  LEVELS,
  formatKst,
  formatKstTime,
  formatPageRange,
  isScanResult,
  joinReview,
  reviewTally,
} from '../../../entities/greenwash/model/index.ts';
import type {
  GreenwashResult,
  GreenwashReview,
  ReviewEdit,
  ReviewRejudge,
  TermCount,
} from '../../../entities/greenwash/model/index.ts';
import {
  CountUp,
  GwDownloads,
  LoadFailure,
  RiskBadge,
  RunStatusBadge,
  StepFlow,
  partName,
} from '../../../entities/greenwash/ui/index.ts';
import type {
  RiskLevel,
  RunStatus,
} from '../../../entities/greenwash/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import {
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../../shared/ui/tabs/index.ts';
import { useDefaultTerms, useRunSummary } from '../hooks/index.ts';
import {
  failedPagesOf,
  isExtraTermRow,
  levelCountsOf,
  partSummaries,
  termFrequency,
} from '../model/index.ts';
import type { PartSummary } from '../model/index.ts';
import { ResultSkeleton } from './ResultSkeleton.tsx';

const words = GW_TEXT.result;

const RISK: Record<(typeof LEVELS)[number], RiskLevel> = {
  High: 'high',
  Mid: 'mid',
  Low: 'low',
};

export interface ResultScreenProps {
  store: GreenwashStore;
  runId: string;
  onBack(): void;
  /** [검토 이어 하기]·[결과 보기] → GW-05. */
  onReview(): void;
  /** [확정] → GW-05 의 확정 확인(05b, ④). */
  onConfirm(): void;
  /** 거짓이면 [확정]을 숨긴다(로그인하지 않은 세션 — 운영 관리자도 고객사 사용자와 같이 쓴다, sid:MARC-ENT-409). 기본 참. */
  canWrite?: boolean;
}

export function ResultScreen({
  store,
  runId,
  onBack,
  onReview,
  onConfirm,
  canWrite = true,
}: ResultScreenProps) {
  const { status: result, retry } = useResult(store, runId);
  const review = useReview(store, runId);
  const summary = useRunSummary(store, runId);
  const defaultTerms = useDefaultTerms(store);
  const skeleton = useDelayed(result.state === 'loading');
  // 없음·꼴 오류·실패는 모두 상자(첫 단추)로 — 초점 훅에는 failed 하나
  const retryFocus = useRetryFocus<HTMLHeadingElement>(
    result.state === 'loading' || result.state === 'ready' ?
      result.state
    : 'failed',
  );

  const back = (
    <Button variant="outlineGrey" shape="round" size="md" onClick={onBack}>
      {words.back}
    </Button>
  );

  if (result.state !== 'ready')
    return (
      <div
        data-screen="result"
        data-result-state={result.state}
        aria-busy={result.state === 'loading' || undefined}
        className="flex flex-col gap-6"
      >
        {result.state === 'loading' ?
          <>
            <PageTitle
              title={words.title}
              titlePending
              pendingLabel={GW_TEXT.load.titlePending}
              descriptionPending
              actions={back}
            />
            <StepFlow current={3} />
            {skeleton && <ResultSkeleton label={words.loading} />}
          </>
        : result.state === 'missing' ?
          <>
            <PageTitle title={words.title} />
            <LoadFailure
              kind="missing"
              message={words.missing}
              listLabel={GW_TEXT.load.toList}
              onList={onBack}
              actionRef={retryFocus.actionRef}
            />
          </>
        : <>
            <PageTitle title={words.title} />
            <StepFlow current={3} />
            <LoadFailure
              kind="failed"
              message={words[result.state]}
              retryLabel={GW_TEXT.load.retry}
              listLabel={GW_TEXT.load.toList}
              onRetry={retryFocus.arm(retry)}
              onList={onBack}
              actionRef={retryFocus.actionRef}
            />
          </>
        }
      </div>
    );

  const data = result.result;
  const reviewDoc =
    review.status.state === 'ready' ? review.status.review : null;
  const confirmed = reviewDoc?.state === 'confirmed';
  const total = data.items.length;
  const lastRun = summary.state === 'ready' ? summary.run : null;

  return (
    <div
      data-screen="result"
      data-result-state="ready"
      className="flex flex-col gap-6"
    >
      <PageTitle
        headingRef={retryFocus.doneRef}
        title={
          <span className="inline-flex flex-wrap items-center gap-2">
            <span>{data.source.fileName}</span>
            {reviewDoc && (
              <span data-testid="review-state" data-state={reviewDoc.state}>
                <RunStatusBadge
                  status={reviewBadge(data, reviewDoc)}
                  showCount={false}
                />
              </span>
            )}
          </span>
        }
        description={words.meta({
          at: lastRun ? formatKst(lastRun.createdAt) : null,
          ordinal: summary.state === 'ready' ? summary.ordinal : null,
          pageCount: data.source.pageCount,
          checked: data.pages.length,
          reviewed: reviewDoc ? reviewedOf(data, reviewDoc) : null,
          total,
          // 이 탭에서 저장한 때(확정이면 없음 — 디자인 답 D2, 밴드 GW2R ② Q6)
          savedAt:
            confirmed || review.savedAt === null ?
              null
            : formatKstTime(review.savedAt),
        })}
        actions={
          <>
            <GwDownloads
              confirmed={confirmed}
              scan={isScanResult(data)}
              load={() => store.getReport(runId, confirmed)}
            />
            {isScanResult(data) && !confirmed && canWrite && (
              <Button
                variant="outlineBlack"
                shape="round"
                size="md"
                onClick={onConfirm}
              >
                {words.confirm}
              </Button>
            )}
            {isScanResult(data) && (
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                onClick={onReview}
              >
                {/* 운영 관리자도 고객사와 같은 주 단추(sid:MARC-ENT-409 J1b — 「결과 보기」 갈래를 걷음) */}
                {confirmed ? words.viewResult : words.continueReview}
              </Button>
            )}
          </>
        }
      />
      <StepFlow current={3} />

      <PageInfo icon={<PageInfoIcon />} data-testid="image-notice">
        {words.imageNotice}
      </PageInfo>
      {isScanResult(data) ?
        <ScanBody
          result={data}
          // 검토를 읽었으면 효력 등급(고친 등급 ?? AI)으로 센다, 읽는 중·못 읽음이면 AI 셈(밴드 G1b-3 ③ — 디자인 80 회신 Q8)
          edits={reviewDoc?.edits ?? []}
          // 재판단 기준 판단도(밴드 GRJ1 ③ B1 — 고친 등급 ?? 기준 판단 ?? AI, 리스크 아님은 세 등급 밖)
          rejudges={reviewDoc?.rejudges ?? []}
          confirmed={confirmed}
          defaultTerms={defaultTerms}
        />
      : <>
          <PageInfo icon={<PageInfoIcon />} data-testid="dry-run">
            {words.dryRun}
          </PageInfo>
          <TermsCard result={data} defaultTerms={defaultTerms} />
        </>
      }
    </div>
  );
}

/** 검토한 문장 수 = 결과 문장과 이은 표시 가운데 채택·제외(GW-05 와 같은 셈 — reviewTally, 밴드 FW2 ⑤). */
function reviewedOf(result: GreenwashResult, review: GreenwashReview): number {
  return reviewTally(joinReview(result.items, review.marks)).reviewed;
}

function reviewBadge(
  result: GreenwashResult,
  review: GreenwashReview,
): RunStatus {
  if (review.state === 'pending') return { kind: 'pending' };
  if (review.state === 'in_review')
    return {
      kind: 'reviewing',
      reviewed: reviewedOf(result, review),
      total: result.items.length,
    };
  return { kind: 'confirmed' };
}

function ScanBody({
  result,
  edits,
  rejudges,
  confirmed,
  defaultTerms,
}: {
  result: GreenwashResult;
  /** 검토의 고침(검토를 못 읽었으면 []). 등급 합·파트 표를 효력 등급으로 센다. */
  edits: readonly ReviewEdit[];
  /** 검토의 재판단 줄(검토를 못 읽었으면 []). */
  rejudges: readonly ReviewRejudge[];
  confirmed: boolean;
  defaultTerms: readonly string[] | null;
}) {
  const failed = failedPagesOf(result);
  const counts = levelCountsOf(result.items, edits, rejudges);
  const parts = partSummaries(result, edits, rejudges);
  return (
    <>
      {!confirmed && (
        <PageInfo
          tone="important"
          icon={<PageInfoIcon />}
          data-testid="unconfirmed-notice"
        >
          {words.unconfirmedNotice}
        </PageInfo>
      )}
      {failed.length > 0 && (
        // 파랑 정보 줄(css .g-info--caution — 공용 PageInfo 에 tone 이 없어 바탕·글 색만 덮는다) + 회색 쪽 칩(v115 GW-04_r2, Q7·Q12)
        <PageInfo
          icon={<PageInfoIcon />}
          data-testid="failed-pages"
          className="bg-support-blue-subtle text-support-blue-dark"
        >
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>{words.missedPages(failed.length)}</span>
            <span className="inline-flex flex-wrap gap-1">
              {failed.map((page) => (
                <Badge key={page} variant="grey" size="sm" data-page={page}>
                  {words.missedPage(page)}
                </Badge>
              ))}
            </span>
            <span>{words.missedNote}</span>
          </span>
        </PageInfo>
      )}

      <ul
        aria-label={words.statsLabel}
        className="m-0 grid list-none grid-cols-4 gap-4 p-0"
      >
        <Stat
          testId="stat-total"
          label={words.stats.total}
          value={result.items.length}
          order={0}
        />
        {LEVELS.map((level, index) => (
          <Stat
            key={level}
            order={index + 1}
            testId={`stat-${RISK[level]}`}
            label={
              <>
                <RiskBadge level={RISK[level]} />
                {words.stats[level]}
              </>
            }
            value={counts[level]}
          />
        ))}
      </ul>

      <div className="grid grid-cols-2 items-start gap-6">
        <Card className="gw-m-rise flex flex-col gap-4" style={rise(4)}>
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.partsHeading}
          </h3>
          <PartsTable parts={parts} />
          <p
            data-testid="parts-note"
            className="m-0 text-style-pre-caption-03 text-text-tertiary"
          >
            {words.partsNote(
              parts.reduce((sum, part) => sum + part.total, 0),
              result.items.length,
            )}
          </p>
        </Card>
        <TermsCard result={result} defaultTerms={defaultTerms} />
      </div>
    </>
  );
}

/** 들어올 때의 시차(밴드 GA1 — n 번째 칸은 70ms 씩 늦게). */
function rise(order: number): CSSProperties {
  return { '--gw-m-delay': `${order * 70}ms` } as CSSProperties;
}

function Stat({
  label,
  value,
  testId,
  order,
}: {
  label: ReactNode;
  value: number;
  testId: string;
  /** 들어오는 차례(시차). */
  order: number;
}) {
  return (
    <li data-testid={testId} className="gw-m-rise" style={rise(order)}>
      {/* 안쪽 24(시안 .g-stat padding space-6, GW3R2 SC11 — Card 기본 p-8 을 덮음) */}
      <Card className="flex flex-col gap-1.5 p-6">
        <span className="flex items-center gap-1.5 text-style-pre-body-05 text-text-tertiary">
          {label}
        </span>
        {/* 숫자는 display-03(시안 .g-stat .v 700 32/1.3 — 데스크톱 토큰은 28/1.4, 32 를 주는 토큰이 없다. GW3R A4·GW3R2 SC11) */}
        <span className="text-style-pre-display-03 tabular-nums text-text-primary">
          <span data-testid="stat-value">
            <CountUp value={value} durationMs={800} />
          </span>
          <small className="ml-1 text-style-pre-body-05 text-text-tertiary">
            {words.sentences}
          </small>
        </span>
      </Card>
    </li>
  );
}

function PartsTable({ parts }: { parts: readonly PartSummary[] }) {
  const columns: DataTableColumnDef<PartSummary>[] = [
    {
      id: 'name',
      header: words.partColumns.name,
      enableSorting: false,
      cell: ({ row }) => partName(row.original.name),
    },
    {
      id: 'pages',
      header: words.partColumns.pages,
      enableSorting: false,
      meta: { align: 'right' },
      cell: ({ row }) => (
        <span className="tabular-nums">
          {formatPageRange(row.original.pages)}
        </span>
      ),
    },
    ...LEVELS.map((level): DataTableColumnDef<PartSummary> => ({
      id: level,
      header: level,
      enableSorting: false,
      meta: { align: 'center' },
      cell: ({ row }) => (
        <span data-testid={`part-${RISK[level]}`} className="inline-flex">
          <RiskBadge
            level={RISK[level]}
            count={row.original.counts[level]}
            display="count"
          />
        </span>
      ),
    })),
  ];
  const table = useDataTable({
    data: parts as PartSummary[],
    columns,
    getRowId: (row) => row.name,
  });
  return <DataTable table={table} aria-label={words.partsTableLabel} />;
}

interface BarRow {
  key: string;
  label: ReactNode;
  count: number;
  extra?: boolean;
}

/** 가로 막대 목록(이름 · 막대 · 수). 막대 길이는 그 목록의 가장 큰 수에 견준다. */
function Bars({ rows, testId }: { rows: readonly BarRow[]; testId: string }) {
  const max = Math.max(1, ...rows.map((row) => row.count));
  return (
    <ul data-testid={testId} className="m-0 flex list-none flex-col gap-2 p-0">
      {rows.map((row, index) => (
        <li
          key={row.key}
          data-term={row.key}
          data-extra={row.extra ? 'true' : undefined}
          className="flex items-center gap-3 text-style-pre-body-06 text-text-secondary"
        >
          <span className="flex w-32 shrink-0 items-center gap-1.5">
            {row.label}
          </span>
          <span
            aria-hidden
            className="h-2.5 flex-1 overflow-hidden rounded-control bg-background-secondary"
          >
            <span
              className="gw-m-grow block h-full rounded-control bg-grey-500"
              style={{
                width: `${(row.count / max) * 100}%`,
                ...rise(5 + index),
              }}
            />
          </span>
          <span className="w-10 shrink-0 text-right tabular-nums text-text-tertiary">
            {row.count}
          </span>
        </li>
      ))}
    </ul>
  );
}

function TermsCard({
  result,
  defaultTerms,
}: {
  result: GreenwashResult;
  defaultTerms: readonly string[] | null;
}) {
  const [scope, setScope] = useState<'total' | 'parts'>('total');
  const rowsOf = (terms: readonly TermCount[]): BarRow[] =>
    terms.map((term) => {
      // 기본 단어를 못 읽었으면 「추가」를 가를 수 없다 — 배지·data-extra 를 끈다(밴드 LE1).
      const extra =
        defaultTerms !== null &&
        isExtraTermRow(term.term, result.extraTerms, defaultTerms);
      return {
        key: term.term,
        count: term.count,
        extra,
        label: (
          <>
            <span>{term.term}</span>
            {extra && (
              <Badge variant="grey" size="sm" data-testid="extra-badge">
                {words.extraBadge}
              </Badge>
            )}
          </>
        ),
      };
    });
  const empty = (
    <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
      {words.termsEmpty}
    </p>
  );
  const total = termFrequency(result, { kind: 'total' });
  const totalRows = rowsOf(total);
  // 「추가 배지는 …」 안내는 문서 전체 빈도에 추가 단어 줄이 하나라도 있을 때만(디자인 대조 C2 — 배지 없이 배지 설명이 나왔다)
  const anyExtra = totalRows.some((row) => row.extra);
  return (
    <Card
      className="gw-m-rise flex flex-col gap-4"
      style={rise(5)}
      data-testid="terms"
    >
      <Tabs
        value={scope}
        onValueChange={(value) => setScope(value as 'total' | 'parts')}
        variant="box"
      >
        <div className="flex items-center justify-between gap-3">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.termsHeading}
          </h3>
          <TabsList aria-label={words.termsTabsLabel}>
            <TabsTrigger value="total">{words.termsTabs.total}</TabsTrigger>
            <TabsTrigger value="parts">{words.termsTabs.parts}</TabsTrigger>
          </TabsList>
        </div>
        <p className="m-0 mt-4 text-style-pre-caption-03 text-text-tertiary">
          {words.termsNote}
        </p>
        <TabsContent value="total" className="mt-4">
          {total.length === 0 ?
            empty
          : <Bars testId="terms-total" rows={totalRows} />}
        </TabsContent>
        <TabsContent value="parts" className="mt-4 flex flex-col gap-5">
          {result.parts.map((part) => {
            const terms = termFrequency(result, {
              kind: 'part',
              name: part.name,
            });
            return (
              <section
                key={part.name}
                className="flex flex-col gap-2"
                data-part={part.name}
              >
                <h4 className="m-0 text-style-pre-body-04 text-text-primary">
                  {partName(part.name)}
                </h4>
                {terms.length === 0 ?
                  empty
                : <Bars testId="terms-part" rows={rowsOf(terms)} />}
              </section>
            );
          })}
        </TabsContent>
      </Tabs>
      {anyExtra && (
        <p
          className="m-0 text-style-pre-caption-03 text-text-tertiary"
          data-testid="extra-note"
        >
          {words.extraNote}
        </p>
      )}
    </Card>
  );
}
