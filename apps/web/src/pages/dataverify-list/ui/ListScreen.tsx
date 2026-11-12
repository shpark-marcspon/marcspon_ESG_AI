// DV-01·01a 검증 목록(밴드 DV2b, 시안 v148 DV-01_r1·01a_r1 — 운영 관리자는 같은 일, sid:MARC-ENT-388 (가)). 라우터를 모른다.
// - 머리 「검증 목록」(아래 셈·안내 줄은 없다 — 그린워싱과 맞춤, sid:MARC-ENT-625) · 오른쪽 「검증 안내」(→ DV-00).
// - 카드: 거르기 줄(파일명 검색 · 보고연도 · 상태 박스 탭 넷 · 「내가 올린 것만」(고객사만) · [새 검증]) → 표 → 안내 띠(판 글).
// - 줄은 GET /dataverify/runs 그대로(DV1g 계약 칸만 — 판의 「(핵심 n)」·「1회차」는 계약에 없어 그리지 않는다). null 은 「–」.
//   파일명 = source 가 파일이면 그 이름(한 줄 · 넘치면 「…」 · 올리면 전체 이름), 붙여 넣기면 「붙여 넣은 데이터 · <만든 시각>」, 옛 실행(null)은 「–」.
//   어긋남 = checks.fail · 계산 못 함 = checks.notComputed(done 만 — 그 밖 「–」). 상태 = 대기 / 검증 중 · <지금 단계> / 완료(+일부 단계 못 함) / 실패.
// - 상태 탭·mine 은 서버 인자(「대기·처리 중」 = status 둘 한 요청). 파일명 검색·보고연도는 받은 20건 안에서(sid:MARC-ENT-432). 쪽 넘김 0(QB4).
// - 다음 할 일: done → [결과 보기] · queued·processing → [진행 보기] · failed → [다시 실행](store.rerun → 새 DV-03, 거절은 DV-02 시작 실패 글).
//   줄 누름은 done → DV-04, 그 밖 → 그 실행의 DV-03(실패 줄을 눌러 실행을 새로 만들지는 않는다 — 다시 실행은 단추로만).
// - 빈 꼴: 거름 없는 첫 쪽이 0건이면 intro(경로가 DV-00 을 넘김 — QB5 (가)), 없으면 판 빈 글. 거른 빔 → 「조건에 맞는 검증이 없어요」+[거르기 풀기].
//   첫 불러오기(useFirstLoad)도 다시 읽기(탭·mine·다시 시도)와 같은 목록 틀 — 제목(설명 줄 없음 — 막대 자리도 없다, ENT-625) + 거르기 줄 + 표 머리 +
//   자리 잡은 스켈레톤 줄 5(DataTable loading, 막대는 표가 300ms 뒤에 — 밴드 DV4, sid:MARC-ENT-443 ②③, 그린워싱 GL1 꼴). 바깥 틀 aria-busy.
//   표 앞 숨긴 상태 글(role="status", 늘 둠)에 읽는 동안 300ms 뒤 「불러오는 중」(useDelayed) — 첫 읽기·다시 읽기 모두.
//   첫 응답 전에는 intro 판정을 하지 않는다(①) — 0건이 오면 그때 intro 로.
//   표는 layout="fixed" + 짧은 칸 잰 폭(1280 max-content+32, 밴드 DVW1 ②-3) — 스켈레톤·빈·진짜 줄의 칸 폭이 같다. 다시 읽기 스켈레톤 줄 수 = 직전에 그린 줄 수(1~20).
//   실패는 shared load-failure 「검증 목록을 불러오지 못했어요」+[다시 시도].
import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import {
  CircleWarningIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { Label } from '@marcspon/ui/components/label';

import type {
  DataverifyRunRow,
  DataverifyStore,
} from '../../../entities/dataverify/api/index.ts';
import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import { useRuns } from '../../../entities/dataverify/hooks/index.ts';
import { STAGES, atText } from '../../../entities/dataverify/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import {
  useDelayed,
  useFirstLoad,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';
import {
  LIST_TABS,
  NO_SCREEN_FILTER,
  filterRows,
  statusesOf,
  yearsOf,
} from '../model/index.ts';
import type { ListTab, ScreenFilter } from '../model/index.ts';

const words = DV_TEXT.list;
const dash = DV_TEXT.dash;
const stepNames: Readonly<Record<string, string>> = DV_TEXT.status.stepNames;

type Next = 'result' | 'progress' | 'rerun';

export interface ListScreenProps {
  store: DataverifyStore;
  /** 운영 관리자인가(「내가 올린 것만」 숨김 — DV-01a). */
  operator: boolean;
  /** 거름 없는 첫 쪽이 0건일 때 표 대신 그릴 것(경로가 DV-00 을 넘긴다 — QB5 (가)). 없으면 판의 빈 글. */
  intro?: ReactNode;
  onIntro(): void;
  onNewCheck(): void;
  onViewResult(runId: string): void;
  /** [진행 보기]·실패 줄 누름·[다시 실행]이 만든 새 실행. */
  onViewStatus(runId: string): void;
}

/** 화면 줄(표가 그리는 것 — 파일명 글은 거르기도 쓴다). */
interface Row {
  run: DataverifyRunRow;
  label: string;
  /** 파일 이름인가(「–」·붙여 넣은 줄은 흐린 글이 아니고 그대로 — 옛 실행만 흐림). */
  known: boolean;
  reportingYear: string | null;
  next: Next;
}

/** 출처 → 파일명 칸 글: 파일 이름 · 「붙여 넣은 데이터 · 만든 시각」 · 옛 실행 「–」. */
export function labelOf(run: DataverifyRunRow): string {
  if (run.source === null) return dash;
  return run.source.kind === 'file' ?
      run.source.name
    : DV_TEXT.source.pastedAt(atText(run.createdAt));
}

const nextOf = (run: DataverifyRunRow): Next =>
  run.status === 'done' ? 'result'
  : run.status === 'failed' ? 'rerun'
  : 'progress';

const rowOf = (run: DataverifyRunRow): Row => ({
  run,
  label: labelOf(run),
  known: run.source !== null,
  reportingYear: run.reportingYear,
  next: nextOf(run),
});

const muted = <span className="text-text-tertiary">{dash}</span>;

/** ISO → 「YYYY-MM-DD」(한국 시각). 읽을 수 없으면 받은 글자 그대로(atText = formatKst 와 같다 — 그린워싱 kstDate 꼴, ENT-625). */
function kstDate(iso: string): string {
  const full = atText(iso);
  return full === iso ? iso : full.slice(0, 10);
}
const numberOr = (value: number | null | undefined) =>
  value === null || value === undefined ?
    muted
  : <span className="tabular-nums">{value}</span>;

function StatusBadges({ run }: { run: DataverifyRunRow }) {
  switch (run.status) {
    case 'queued':
      return <Badge variant="grey">{words.badge.queued}</Badge>;
    case 'processing':
      return (
        <Badge variant="orange">
          {words.badge.processing(
            run.currentStep === null ?
              null
            : (stepNames[run.currentStep] ?? null),
          )}
        </Badge>
      );
    case 'failed':
      return <Badge variant="error">{words.badge.failed}</Badge>;
    case 'done': {
      const someFailed =
        run.stages !== null &&
        STAGES.some((stage) => run.stages![stage].status === 'failed');
      return (
        <span className="inline-flex items-center gap-1.5">
          <Badge variant="success">{words.badge.done}</Badge>
          {someFailed && (
            <Badge variant="orange" data-testid="some-failed">
              {words.badge.someFailed}
            </Badge>
          )}
        </span>
      );
    }
  }
}

export function ListScreen({
  store,
  operator,
  intro,
  onIntro,
  onNewCheck,
  onViewResult,
  onViewStatus,
}: ListScreenProps) {
  const mineId = useId();
  const yearId = useId();
  const [tab, setTab] = useState<ListTab>('all');
  const [mine, setMine] = useState(false);
  const [filter, setFilter] = useState<ScreenFilter>(NO_SCREEN_FILTER);
  const [rerunning, setRerunning] = useState<number | null>(null);
  const [rerunFailed, setRerunFailed] = useState(false);
  const showMine = !operator;
  const statuses = statusesOf(tab);
  const { status, retry } = useRuns(store, {
    ...(statuses === undefined ? {} : { status: statuses }),
    mine: showMine && mine,
    offset: 0,
  });
  const loading = status.state === 'loading';
  // 첫 응답 전에는 0건 → DV-00 판정을 하지 않는다(nothingYet 은 ready 뒤에만 — sid:MARC-ENT-443 ①). firstLoad 는 바깥 틀 aria-busy 만.
  const firstLoad = useFirstLoad(status.state);
  // 숨긴 상태 글만 300ms 뒤에(sid:MARC-ENT-260). 표는 날 값을 받아 스스로 늦춘다(그린워싱 GL1 꼴).
  const announceLoading = useDelayed(loading);

  const all = status.state === 'ready' ? status.page.results.map(rowOf) : [];
  const rows = filterRows(all, filter);
  const years = yearsOf(all);
  const serverFiltered = tab !== 'all' || (showMine && mine);
  const filtered =
    serverFiltered || filter.query.trim() !== '' || filter.year !== null;
  const nothingYet =
    status.state === 'ready' && !serverFiltered && status.page.count === 0;

  const clear = () => {
    setTab('all');
    setMine(false);
    setFilter(NO_SCREEN_FILTER);
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

  const columns: DataTableColumnDef<Row>[] = [
    {
      id: 'fileName',
      header: words.columns.fileName,
      enableSorting: false,
      cell: ({ row }) =>
        row.original.known ?
          <span
            data-testid="file-name"
            title={row.original.label}
            className="block max-w-80 truncate text-text-primary"
          >
            {row.original.label}
          </span>
        : muted,
    },
    {
      id: 'reportingYear',
      header: words.columns.reportingYear,
      enableSorting: false,
      meta: { align: 'center', skeleton: 40, width: 80 },
      cell: ({ row }) => row.original.run.reportingYear ?? muted,
    },
    {
      id: 'createdBy',
      header: words.columns.createdBy,
      enableSorting: false,
      meta: { skeleton: [40, 64], width: 120 },
      cell: ({ row }) => row.original.run.createdBy.name,
    },
    {
      id: 'itemCount',
      header: words.columns.itemCount,
      enableSorting: false,
      meta: { align: 'right', skeleton: [24, 32], width: 84 },
      cell: ({ row }) => numberOr(row.original.run.itemCount),
    },
    {
      id: 'lastRun',
      header: words.columns.lastRun,
      enableSorting: false,
      meta: { skeleton: 112, width: 153 },
      cell: ({ row }) => {
        const finished = row.original.run.finishedAt;
        return finished === null ? muted : (
            <span className="tabular-nums">{kstDate(finished)}</span>
          );
      },
    },
    {
      id: 'mismatches',
      header: words.columns.mismatches,
      enableSorting: false,
      meta: { align: 'center', skeleton: [24, 32], width: 68 },
      cell: ({ row }) => numberOr(row.original.run.checks?.fail),
    },
    {
      id: 'uncomputable',
      header: words.columns.uncomputable,
      enableSorting: false,
      meta: { align: 'center', skeleton: [24, 32], width: 87 },
      cell: ({ row }) => numberOr(row.original.run.checks?.notComputed),
    },
    {
      id: 'status',
      header: words.columns.status,
      enableSorting: false,
      meta: { skeleton: [48, 80], width: 160 },
      cell: ({ row }) => (
        <span data-testid="row-status" data-status={row.original.run.status}>
          <StatusBadges run={row.original.run} />
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
          // 도는 동안은 aria-disabled + 도는 표시(누름은 Button 이 막는다 — 그린워싱 목록과 같은 꼴).
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
  /** 직전에 그린 줄 수(1~20) — 다시 읽는 동안 스켈레톤 줄 수로 써 아래 안내 띠가 덜 튄다. 첫 읽기는 5(GL1 꼴). */
  const lastRows = useRef(5);
  useEffect(() => {
    if (status.state === 'ready')
      lastRows.current = Math.min(Math.max(rows.length, 1), 20);
  }, [status.state, rows.length]);

  if (nothingYet && intro !== undefined) return <>{intro}</>;

  return (
    <div
      data-screen="dataverify-list"
      {...(firstLoad ?
        { 'data-list-state': 'loading', 'aria-busy': true }
      : {})}
      className="flex flex-col gap-6"
    >
      <PageTitle
        title={words.title}
        actions={
          <a
            href="/dataverify/intro"
            onClick={(event) => {
              event.preventDefault();
              onIntro();
            }}
            className="text-style-pre-caption-03 text-text-secondary"
          >
            {words.introLink}
          </a>
        }
      />
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <SearchField
              aria-label={words.search}
              placeholder={words.search}
              value={filter.query}
              onChange={(event) =>
                setFilter((prev) => ({ ...prev, query: event.target.value }))
              }
              className="w-[300px]"
            />
            <label htmlFor={yearId} className="sr-only">
              {words.yearLabel}
            </label>
            <NativeSelect
              id={yearId}
              value={filter.year ?? ''}
              onChange={(event) =>
                setFilter((prev) => ({
                  ...prev,
                  year: event.target.value === '' ? null : event.target.value,
                }))
              }
            >
              <option value="">{words.yearAll}</option>
              {years.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </NativeSelect>
            <Tabs
              value={tab}
              onValueChange={(value) => setTab(value as ListTab)}
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
            {/* 운영 관리자는 「내가 올린 것만」이 없다(판 DV-01a). 거르기 값은 거짓 그대로다. */}
            {showMine && (
              <div className="flex items-center gap-2">
                <Checkbox
                  id={mineId}
                  checked={mine}
                  onCheckedChange={(checked) => setMine(checked === true)}
                />
                <Label
                  htmlFor={mineId}
                  className="cursor-pointer text-style-pre-body-06 text-text-secondary"
                >
                  {words.mineOnly}
                </Label>
              </div>
            )}
          </div>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={onNewCheck}
          >
            <PlusIcon aria-hidden />
            {words.newCheck}
          </Button>
        </div>

        {rerunFailed && (
          <PageInfo
            tone="error"
            role="alert"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="list-rerun-error"
          >
            {DV_TEXT.newCheck.errors.startFailed}
          </PageInfo>
        )}

        {/* 라이브 영역은 늘 두고 글만 넣고 뺀다(글과 함께 마운트되면 낭독이 빠질 수 있다 — 밴드 LA1 ①) */}
        <span className="sr-only" role="status">
          {announceLoading ? words.loading : null}
        </span>
        <DataTable
          table={table}
          aria-label={words.title}
          loading={loading}
          layout="fixed"
          skeletonRows={lastRows.current}
          onClickRow={(row) => {
            const id = String(row.run.id);
            if (row.run.status === 'done') onViewResult(id);
            else onViewStatus(id);
          }}
          rowLabel={(row) =>
            `${row.label} — ${words.next[row.next === 'result' ? 'result' : 'progress']}`
          }
          empty={
            status.state === 'failed' ?
              <LoadFailure
                kind="failed"
                message={words.loadFailed}
                retryLabel={words.retry}
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
                    <Button
                      variant="solidBlack"
                      shape="round"
                      size="md"
                      onClick={onNewCheck}
                    >
                      <PlusIcon aria-hidden />
                      {words.newCheck}
                    </Button>
                  }
                />

            : null
          }
        />
        <PageInfo icon={<PageInfoIcon />} data-testid="list-notice">
          {words.notice}
        </PageInfo>
      </Card>
    </div>
  );
}
