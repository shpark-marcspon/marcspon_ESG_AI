// IR-01·01a 평가 목록(밴드 IRW1 ③, 시안 v157 IR-01_r1·01a_r1 — 운영 관리자는 같은 일, sid:MARC-ENT-419). 라우터를 모른다.
//   데이터 검증 ListScreen(DV2b) 꼴을 따라 지음(가져오지 않는다).
// - 머리 「평가 목록」(아래 셈·안내 줄은 없다 — 그린워싱과 맞춤, sid:MARC-ENT-625) · 오른쪽 「평가 안내」·카드의 [새 평가]는 콜백을 받을 때만
//   (onIntro?·onNew? — IRW2 가 넘긴다, 안 주면 0).
// - 카드: 상태 박스 탭 넷 → 표 10열(판 차례·글). 내 실행만 거르기·아래 안내 띠는 뺐다(밴드 IRW17 — 1차 댓글 2f094f75·68f3d0fb,
//   고객사·운영 관리자 모두 0. 서버 mine 칸은 두고 화면에서 보내지 않는다).
// - 줄은 GET /materiality/runs 그대로(IR3c 계약 칸만 — 덧붙임 A). null 은 「–」. 기업명 옆 최신 이슈 표시는 뺐다(IRW17 — 0207ff2a).
//   산업 = industryName 들(입력 차례, 「, 」). 리서치 기간 = dateRange(「오늘까지」면 끝 날 = startedAt 한국 날짜, 아직 안 돌았으면 글 그대로).
//   평가 완료 일자 = 완료(done) 줄만 끝난 때(finishedAt)의 한국 날짜 YYYY-MM-DD, 대기·처리 중·실패 줄은 「–」(그린워싱 꼴, sid:MARC-ENT-625).
//   상태 = 대기 / 처리 중 · <판 줄 이름>(currentStep — 모르는 단계면 「처리 중」만) / 완료 / 실패. 영향 두 수는 done 의 요약(없으면 「–」).
// - 상태 탭은 서버 인자(「대기·처리 중」 = status 둘 한 요청). 쪽 넘김 0(새 것 20). 거르기를 바꾸면 다시 실행 실패 글을 지운다(381 m4).
// - 다음 할 일: done → [결과 보기] · queued·processing → [진행 보기] · failed → [다시 실행](store.rerun → 새 IR-03, 거절은 다시 실행 실패 글).
//   줄 누름은 done → IR-04, 그 밖(failed 포함) → 그 실행의 IR-03(누름으로 새 실행을 만들지 않는다 — DV2b 선례, 비용 0).
// - 빈 꼴: 거름 없는 첫 쪽이 0건이면 intro(경로가 IR-00 몸을 넘김 — IRW2 Q9, DV2b 꼴), intro 가 없으면 IR-01 빈 꼴
//   「아직 돌린 평가가 없어요. …」(+[새 평가] — onNew 를 받을 때만, 판). 첫 응답 전에는 0건 판정을 하지 않는다(sid:MARC-ENT-443 ①).
//   거른 빔 → 「조건에 맞는 평가가 없어요」+[거르기 풀기]. 첫 불러오기는 aria-busy 틀 + 300ms 뒤 LoadSkeleton(sid:MARC-ENT-443),
//   그 뒤 다시 읽기는 표 머리 + 스켈레톤 줄(DataTable loading). 실패는 shared load-failure 「평가 목록을 불러오지 못했어요」+[다시 시도].
import { Fragment, useState } from 'react';
import type { ReactNode } from 'react';

import {
  CircleWarningIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';

import type {
  MaterialityRunRow,
  MaterialityStore,
} from '../../../entities/materiality/api/index.ts';
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import { useRuns } from '../../../entities/materiality/hooks/index.ts';
import {
  LIST_TABS,
  kstDay,
  lineOfStep,
  nextOf,
  periodOf,
  rowTargetOf,
  statusesOf,
} from '../../../entities/materiality/model/index.ts';
import type {
  ListTab,
  NextAction,
} from '../../../entities/materiality/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import {
  LoadSkeleton,
  useDelayed,
  useFirstLoad,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';

const words = IR_TEXT.list;
const dash = IR_TEXT.dash;
const lineNames = IR_TEXT.status.lines;

export interface ListScreenProps {
  store: MaterialityStore;
  /** 운영 관리자인가(IR-01a). 내 실행만 거르기·안내 띠를 뺀 뒤(IRW17) 화면 차이는 없다 — 경로(app/)가 넘기는 꼴은 둔다. */
  operator: boolean;
  /** 거름 없는 첫 쪽이 0건일 때 표 대신 그릴 것(경로가 IR-00 몸을 넘긴다 — IRW2 Q9). 없으면 판의 빈 글. */
  intro?: ReactNode;
  /** 「평가 안내」(IR-00 — IRW2 가 넘긴다). 없으면 그리지 않는다. */
  onIntro?: () => void;
  /** [새 평가](IR-02 — IRW2 가 넘긴다). 없으면 그리지 않는다. */
  onNew?: () => void;
  onViewResult(runId: string): void;
  /** [진행 보기]·done 아닌 줄 누름·[다시 실행]이 만든 새 실행. */
  onViewStatus(runId: string): void;
}

interface Row {
  run: MaterialityRunRow;
  next: NextAction;
}

const muted = <span className="text-text-tertiary">{dash}</span>;

/** ISO → 「YYYY-MM-DD」(한국 시각). 읽을 수 없으면 받은 글자 그대로(그린워싱 kstDate 꼴, ENT-625). */
const kstDate = (iso: string): string => kstDay(iso) ?? iso;
const numberOr = (value: number | null) =>
  value === null ? muted : <span className="tabular-nums">{value}</span>;

/** 원문의 「~」 앞뒤를 띄운다(「2025-01-01~오늘까지」 → 「2025-01-01 ~ 오늘까지」 — 디자인 대조 W8). 「~」 가 없으면 그대로. */
const RAW_RANGE = /^\s*(.*?)\s*~\s*(.*?)\s*$/;

/** 리서치 기간 두 덩이(「<시작> ~」·「<끝>」 — 판 N2, 덩이 안은 한 줄). 못 읽거나 아직 끝 날을 모르면 원문을 「~」 에서 나눔
 *  (앞이 비면 「~」 만 — 앞 빈칸 0, 381 W8), 「~」 가 없으면 원문 한 덩이, 없으면 null. */
function periodParts(run: MaterialityRunRow): readonly string[] | null {
  if (run.dateRange === null) return null;
  const period = periodOf(run.dateRange, kstDay(run.startedAt));
  let start: string;
  let end: string;
  if (period.kind === 'range') ({ start, end } = period);
  else {
    const raw = RAW_RANGE.exec(period.text);
    if (raw === null) return [period.text];
    [start, end] = [raw[1]!, raw[2]!];
  }
  const head = start === '' ? '~' : `${start} ~`;
  return end === '' ? [head] : [head, end];
}

/** 표 꼴(디자인 대조 W2): 머리·짧은 칸은 한 줄(nowrap), 산업·회사·작성자 글만 줄바꿈(WRAP), 그래도 넘치면 DataTable 감싸개(카드 안)가 가로 스크롤.
 *  공용 DataTable 을 고치지 않고 칸 자손으로 덮는다(데이터 검증 DV3 ROW_PADDING 꼴). 빈 꼴·불러오기 실패 줄(colSpan)은 빼 줄바꿈 그대로.
 *  열 폭은 고정(밴드 IRW4, layout fixed — 스켈레톤↔진짜 줄 같은 폭): 짧은 칸 meta.width = 1280 에서 잰 max-content(칸 안쪽 32 포함),
 *  회사는 1440 에 맞춘 136. 고정 폭에서 nowrap 글은 옆 칸 위로 넘치니 길이가 정해지지 않은 사용자 글(회사·작성자)은 WRAP span 으로 칸 안 줄바꿈.
 *  WRAP 은 keep-all — 낱말 중간 줄바꿈 0(IRW5, 433 ②). */
const NOWRAP =
  '[&_th]:whitespace-nowrap [&_td:not([colspan])]:whitespace-nowrap';
const WRAP = 'whitespace-normal break-keep';
/** 상태 칸: 배지 글이 줄을 바꿀 수 있게(키트 배지는 높이·w-max 가 박혀 있어 className 으로 덮는다 — packages/ui 0줄). */
const BADGE_WRAP = 'h-auto w-auto whitespace-normal py-0.5';

function StatusBadge({ run }: { run: MaterialityRunRow }) {
  switch (run.status) {
    case 'queued':
      return (
        <Badge variant="grey" className={BADGE_WRAP}>
          {IR_TEXT.badge.queued}
        </Badge>
      );
    case 'processing': {
      const line =
        run.currentStep === null ? null : lineOfStep(run.currentStep);
      return (
        <Badge variant="orange" className={BADGE_WRAP}>
          {words.processing(line === null ? null : lineNames[line].name)}
        </Badge>
      );
    }
    case 'failed':
      return (
        <Badge variant="error" className={BADGE_WRAP}>
          {IR_TEXT.badge.failed}
        </Badge>
      );
    case 'done':
      return (
        <Badge variant="success" className={BADGE_WRAP}>
          {IR_TEXT.badge.done}
        </Badge>
      );
  }
}

export function ListScreen({
  store,
  intro,
  onIntro,
  onNew,
  onViewResult,
  onViewStatus,
}: ListScreenProps) {
  const [tab, setTab] = useState<ListTab>('all');
  const [rerunning, setRerunning] = useState<number | null>(null);
  const [rerunFailed, setRerunFailed] = useState(false);
  const statuses = statusesOf(tab);
  const { status, retry } = useRuns(store, {
    ...(statuses === undefined ? {} : { status: statuses }),
    offset: 0,
  });
  const loading = status.state === 'loading';
  const firstLoad = useFirstLoad(status.state);
  const skeleton = useDelayed(firstLoad);

  const rows: Row[] =
    status.state === 'ready' ?
      status.page.results.map((run) => ({ run, next: nextOf(run.status) }))
    : [];
  const filtered = tab !== 'all';
  const nothingYet =
    status.state === 'ready' && !filtered && status.page.count === 0;

  /** 거르기를 바꾸면 앞 거르기의 다시 실행 실패 글은 지운다(381 m4). */
  const changeTab = (next: ListTab) => {
    setRerunFailed(false);
    setTab(next);
  };
  const clear = () => {
    setRerunFailed(false);
    setTab('all');
  };

  const rerun = async (runId: number) => {
    if (rerunning !== null) return;
    setRerunning(runId);
    setRerunFailed(false);
    try {
      const out = await store.rerun(String(runId));
      if (out.kind === 'started') onViewStatus(out.runId);
      else setRerunFailed(true);
    } catch {
      setRerunFailed(true);
    } finally {
      setRerunning(null);
    }
  };

  const act = (row: Row) => {
    const id = String(row.run.id);
    if (row.next === 'result') onViewResult(id);
    else if (row.next === 'progress') onViewStatus(id);
    else void rerun(row.run.id);
  };

  /** 줄 누름: done → 결과, 그 밖(failed 포함) → 그 실행의 처리 상태(새 실행 0). */
  const onRowClick = (row: Row) => {
    const id = String(row.run.id);
    if (rowTargetOf(row.run.status) === 'result') onViewResult(id);
    else onViewStatus(id);
  };

  const columns: DataTableColumnDef<Row>[] = [
    {
      id: 'company',
      header: words.columns.company,
      enableSorting: false,
      // 1440 카드 안 1192 − 나머지 아홉 1053 = 139 에서 3 틈(반올림·막대 1px 넘침 막기 — IRW4 감독). 1280 은 BASE 처럼 카드 안 가로 스크롤.
      meta: { width: 136 },
      cell: ({ row }) => (
        <span
          data-run-id={row.original.run.id}
          className="inline-flex flex-wrap items-center gap-1.5"
        >
          {row.original.run.companyName === null ?
            muted
          : <span className={`${WRAP} text-text-primary`}>
              {row.original.run.companyName}
            </span>
          }
        </span>
      ),
    },
    {
      id: 'industry',
      header: words.columns.industry,
      enableSorting: false,
      // 판 N2(Q10, 부록 A7): 산업 168 · 상태 136(웹 th 는 border-box·px-4 — 판 content-box 136·104)
      meta: { skeleton: [80, 160], width: 168 },
      cell: ({ row }) =>
        row.original.run.industries === null ?
          muted
        : <span data-testid="industry" className={WRAP}>
            {row.original.run.industries
              .map((industry) => industry.industryName)
              .join(words.industryJoiner)}
          </span>,
    },
    {
      id: 'topics',
      header: words.columns.topics,
      enableSorting: false,
      meta: { align: 'right', skeleton: [16, 24], width: 56 },
      cell: ({ row }) => numberOr(row.original.run.topicCount),
    },
    {
      id: 'period',
      header: words.columns.period,
      enableSorting: false,
      // 긴 덩이 하나 + 32(min-content — 1440 에서 두 덩이 두 줄)
      meta: { skeleton: 160, width: 124 },
      cell: ({ row }) => {
        const parts = periodParts(row.original.run);
        return parts === null ? muted : (
            <span
              data-testid="period"
              className="whitespace-normal tabular-nums"
            >
              {/* 빈칸은 두 덩이 사이(줄바꿈 되는 부모)에 — 덩이 안에 두면 바꿀 자리가 없다(검증 3 B1). */}
              {parts.map((part, index) => (
                <Fragment key={index}>
                  {index > 0 && ' '}
                  <span className="whitespace-nowrap">{part}</span>
                </Fragment>
              ))}
            </span>
          );
      },
    },
    {
      id: 'createdBy',
      header: words.columns.createdBy,
      enableSorting: false,
      meta: { skeleton: [40, 64], width: 96 },
      cell: ({ row }) => (
        <span className={WRAP}>{row.original.run.createdBy.name}</span>
      ),
    },
    {
      id: 'lastRun',
      header: words.columns.lastRun,
      enableSorting: false,
      meta: { skeleton: 112, width: 153 },
      cell: ({ row }) => {
        const { run } = row.original;
        return run.status === 'done' && run.finishedAt !== null ?
            <span className="tabular-nums">{kstDate(run.finishedAt)}</span>
          : muted;
      },
    },
    {
      id: 'impact',
      header: words.columns.impact,
      enableSorting: false,
      meta: { align: 'right', skeleton: [24, 32], width: 111 },
      cell: ({ row }) => numberOr(row.original.run.impactRows),
    },
    {
      id: 'pathway',
      header: words.columns.pathway,
      enableSorting: false,
      meta: { align: 'right', skeleton: [24, 32], width: 111 },
      cell: ({ row }) => numberOr(row.original.run.pathwayRows),
    },
    {
      id: 'status',
      header: words.columns.status,
      enableSorting: false,
      meta: { skeleton: [48, 80], width: 136 },
      cell: ({ row }) => (
        <span
          data-testid="row-status"
          data-status={row.original.run.status}
          className="whitespace-normal"
        >
          <StatusBadge run={row.original.run} />
        </span>
      ),
    },
    {
      id: 'next',
      header: words.columns.next,
      enableSorting: false,
      meta: { align: 'center', skeleton: [72, 88], width: 98 },
      cell: ({ row }) => {
        const next = row.original.next;
        if (next === 'rerun')
          // 도는 동안은 aria-disabled + 도는 표시(누름은 Button 이 막는다 — 데이터 검증 목록과 같은 꼴).
          return (
            <Button
              asChild
              loading={rerunning === row.original.run.id}
              variant="outlineGrey"
              shape="round"
              size="sm"
            >
              <button
                type="button"
                data-next={next}
                onClick={() => act(row.original)}
              >
                {words.next[next]}
              </button>
            </Button>
          );
        return (
          <Button
            variant="outlineGrey"
            shape="round"
            size="sm"
            data-next={next}
            onClick={() => act(row.original)}
          >
            {words.next[next]}
          </Button>
        );
      },
    },
  ];

  const table = useDataTable({
    data: rows,
    columns,
    getRowId: (row) => String(row.run.id),
  });

  if (firstLoad)
    return (
      <div
        data-screen="materiality-list"
        data-list-state="loading"
        aria-busy
        className="flex flex-col gap-6"
      >
        {skeleton && <LoadSkeleton />}
      </div>
    );

  if (nothingYet && intro !== undefined) return <>{intro}</>;

  return (
    <div data-screen="materiality-list" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        actions={
          onIntro === undefined ? undefined : (
            <a
              href="/materiality/intro"
              onClick={(event) => {
                event.preventDefault();
                onIntro();
              }}
              className="text-style-pre-caption-03 text-text-secondary"
            >
              {words.introLink}
            </a>
          )
        }
      />
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <Tabs
              value={tab}
              onValueChange={(value) => changeTab(value as ListTab)}
              variant="box"
            >
              <TabsList aria-label={words.tabsLabel}>
                {LIST_TABS.map((key) => (
                  <TabsTrigger key={key} value={key}>
                    {words.tabs[key]}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
          {/* 빈 꼴(intro 없음)은 [새 평가]를 빈 글 아래에 둔다(판) — 같은 단추 둘 0. */}
          {onNew !== undefined && !nothingYet && (
            <Button
              variant="solidBlack"
              shape="round"
              size="md"
              onClick={onNew}
            >
              <PlusIcon aria-hidden />
              {words.newRun}
            </Button>
          )}
        </div>

        {rerunFailed && (
          <PageInfo
            tone="error"
            role="alert"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="list-rerun-error"
          >
            {IR_TEXT.common.rerunFailed}
          </PageInfo>
        )}

        <DataTable
          table={table}
          aria-label={words.title}
          className={NOWRAP}
          layout="fixed"
          loading={loading}
          onClickRow={onRowClick}
          rowLabel={(row) =>
            `${row.run.companyName ?? dash} — ${words.next[row.run.status === 'done' ? 'result' : 'progress']}`
          }
          empty={
            status.state === 'failed' ?
              <LoadFailure
                kind="failed"
                message={words.loadFailed}
                retryLabel={IR_TEXT.common.retry}
                onRetry={retry}
              />
            : status.state === 'ready' ?
              filtered ?
                <Empty
                  data-testid="list-empty-filtered"
                  title={words.emptyFiltered}
                  action={
                    <Button
                      variant="outlineGrey"
                      shape="round"
                      size="md"
                      onClick={clear}
                    >
                      {words.clearFilter}
                    </Button>
                  }
                />
              : <Empty
                  data-testid="list-empty"
                  title={words.empty}
                  action={
                    onNew === undefined ? undefined : (
                      <Button
                        variant="solidBlack"
                        shape="round"
                        size="md"
                        onClick={onNew}
                      >
                        <PlusIcon aria-hidden />
                        {words.newRun}
                      </Button>
                    )
                  }
                />

            : null
          }
        />
      </Card>
    </div>
  );
}
