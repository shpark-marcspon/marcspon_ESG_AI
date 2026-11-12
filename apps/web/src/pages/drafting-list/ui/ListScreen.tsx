// RP-01 보고서 프로젝트 목록(밴드 RPW1 ①, 시안 v188 RP-01_r1). 라우터를 모른다 — 콜백 props 를 경로 컴포넌트가 잇는다.
//   중대성평가 ListScreen(IRW1) 꼴을 따라 지음(가져오지 않는다).
// - 회사 칸·회사 거르기는 없다(§2-0 ② — sid:MARC-ENT-374, 서버가 작업 회사를 정한다). 서버는 limit 100 한 번 읽기 — 검색·보고연도·상태
//   탭 거르기는 화면이 그 안에서 한다(count 가 100 을 넘으면 「최근 100건만 보여요」).
// - 줄 상태·잎 셈·「다음 할 일」은 model rowViewOf 하나(서버 사실로만 — §2-0 ③). 다음 할 일: 문서 없음 → 다시 올리기(RP-02),
//   목차 없음·초안 전 → RP-03, 그 밖 → 마지막 실행의 RP-04. 줄 누름도 같은 곳.
// - 빈 꼴: 거름 없는 목록이 0건이면 빈 글 + [새 프로젝트](같은 단추 둘 0 — 머리 단추는 숨김). 거른 빔 → 「조건에 맞는 프로젝트가 없어요」
//   +[거르기 풀기]. 불러오지 못함(CM-03) → LoadFailure +[다시 시도]. 회사 거절 → 회사 글 한 줄(다시 시도 0).
// - 머리 오른쪽 「작성 안내」 링크(밴드 RPW6, sid:MARC-ENT-530 — translation-list 「번역 안내」 꼴). onIntro 를 받을 때만, 목록 상태와
//   상관없이 늘 보인다. 빈 목록은 안내로 넘기지 않는다(지금 꼴 그대로).
import { useState } from 'react';

import {
  CircleWarningIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';

import type { DraftingStore } from '../../../entities/drafting/api/index.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { useProjects } from '../../../entities/drafting/hooks/index.ts';
import {
  PROJECT_FILTERS,
  dayOf,
  inFilter,
  matchesQuery,
  rowViewOf,
  yearsOfRows,
} from '../../../entities/drafting/model/index.ts';
import type {
  NextStep,
  ProjectFilter,
  ProjectRow,
  ProjectState,
  RowView,
} from '../../../entities/drafting/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { FilterSelect } from '../../../shared/ui/filter-select/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import { useDelayed } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';

const words = DR_TEXT.list;

export interface ListScreenProps {
  store: DraftingStore;
  /** 운영 관리자인가(회사 거절 글을 가른다). */
  operator: boolean;
  onNew(): void;
  /** 줄의 「다음 할 일」·줄 누름 — 그 프로젝트의 다음 자리. */
  onNext(projectId: number, next: NextStep): void;
  /** 머리 「작성 안내」 링크 → RP-00(밴드 RPW6). 없으면 링크 0. */
  onIntro?(): void;
}

interface Row {
  project: ProjectRow;
  view: RowView;
}

/** 보고연도 고름의 「전체」 값. */
const ALL_YEARS = 'all';

const BADGE: Record<ProjectState, 'grey' | 'orange' | 'error' | 'success'> = {
  no_document: 'grey',
  no_outline: 'grey',
  no_draft: 'grey',
  drafting: 'orange',
  done: 'success',
  partial: 'orange',
  outline_changed: 'orange',
  failed: 'error',
};

const NOWRAP =
  '[&_th]:whitespace-nowrap [&_td:not([colspan])]:whitespace-nowrap';
const WRAP = 'whitespace-normal break-keep';

function stateText(view: RowView): string {
  if (view.state === 'drafting' && view.progress)
    return words.drafting(view.progress.done, view.progress.total);
  return words.states[view.state];
}

export function ListScreen({
  store,
  operator,
  onNew,
  onNext,
  onIntro,
}: ListScreenProps) {
  const [query, setQuery] = useState('');
  const [year, setYear] = useState<string>(ALL_YEARS);
  const [filter, setFilter] = useState<ProjectFilter>('all');
  const { status, retry } = useProjects(store);
  // 숨긴 상태 글만 300ms 뒤에(sid:MARC-ENT-260). 표는 날 값을 받아 스스로 늦춘다.
  const announceLoading = useDelayed(status.state === 'loading');
  const companyText = operator ? DR_TEXT.companyOperator : DR_TEXT.company;

  const all: Row[] =
    status.state === 'ready' ?
      status.value.results.map((project) => ({
        project,
        view: rowViewOf(project),
      }))
    : [];
  const rows = all.filter(
    (row) =>
      matchesQuery(row.project, query) &&
      (year === ALL_YEARS || String(row.project.year) === year) &&
      inFilter(filter, row.view.state),
  );
  const filtered =
    query.trim() !== '' || year !== ALL_YEARS || filter !== 'all';
  const nothingYet = status.state === 'ready' && all.length === 0;
  const years = yearsOfRows(all.map((row) => row.project));

  const clear = () => {
    setQuery('');
    setYear(ALL_YEARS);
    setFilter('all');
  };
  const open = (row: Row) => onNext(row.project.id, row.view.next);

  const columns: DataTableColumnDef<Row>[] = [
    {
      id: 'project',
      header: words.columns.project,
      enableSorting: false,
      meta: { skeleton: [120, 200] },
      cell: ({ row }) => (
        <span
          data-project-id={row.original.project.id}
          className="flex flex-col"
        >
          <span className={`${WRAP} text-text-primary`}>
            {row.original.project.name}
          </span>
          <span
            data-testid="document-name"
            className={`${WRAP} text-style-pre-caption-03 text-text-tertiary`}
          >
            {row.original.project.documentName ?? words.noDocumentName}
          </span>
        </span>
      ),
    },
    {
      id: 'year',
      header: words.columns.year,
      enableSorting: false,
      meta: { skeleton: [32, 40], width: 96 },
      cell: ({ row }) => (
        <span className="tabular-nums">{row.original.project.year}</span>
      ),
    },
    {
      id: 'leaves',
      header: words.columns.leaves,
      enableSorting: false,
      meta: { skeleton: [48, 72], width: 120 },
      cell: ({ row }) => {
        const leaves = row.original.view.leaves;
        return (
          <span data-testid="row-leaves" className="tabular-nums">
            {leaves ?
              words.leaves(leaves.drafted, leaves.total)
            : <span className="text-text-tertiary">{words.noLeaves}</span>}
          </span>
        );
      },
    },
    {
      id: 'state',
      header: words.columns.state,
      enableSorting: false,
      meta: { skeleton: [64, 104], width: 184 },
      cell: ({ row }) => (
        <span
          data-testid="row-state"
          data-state={row.original.view.state}
          className="whitespace-normal"
        >
          <Badge
            variant={BADGE[row.original.view.state]}
            className="h-auto w-auto whitespace-normal py-0.5"
          >
            {stateText(row.original.view)}
          </Badge>
        </span>
      ),
    },
    {
      id: 'createdAt',
      header: words.columns.createdAt,
      enableSorting: false,
      meta: { skeleton: [72, 80], width: 120 },
      cell: ({ row }) => (
        <span className="tabular-nums">
          {dayOf(row.original.project.createdAt)}
        </span>
      ),
    },
    {
      id: 'next',
      header: words.columns.next,
      enableSorting: false,
      meta: { align: 'center', skeleton: [64, 80], width: 128 },
      cell: ({ row }) => (
        <Button
          variant="outlineGrey"
          shape="round"
          size="sm"
          data-next={row.original.view.next.to}
          onClick={(event) => {
            event.stopPropagation();
            open(row.original);
          }}
        >
          {words.next[row.original.view.state]}
        </Button>
      ),
    },
  ];

  const table = useDataTable({
    data: rows,
    columns,
    getRowId: (row) => String(row.project.id),
  });

  const introLink = onIntro && (
    <a
      href="/drafting/intro"
      onClick={(event) => {
        event.preventDefault();
        onIntro();
      }}
      className="text-style-pre-caption-03 text-text-secondary"
    >
      {words.introLink}
    </a>
  );

  if (status.state === 'refused')
    return (
      <div data-screen="drafting-list" className="flex flex-col gap-6">
        <PageTitle title={words.title} actions={introLink} />
        <PageInfo
          role="alert"
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="company-refusal"
        >
          {companyText[status.company]}
        </PageInfo>
      </div>
    );

  const newButton = (
    <Button variant="solidBlack" shape="round" size="md" onClick={onNew}>
      <PlusIcon aria-hidden />
      {words.newProject}
    </Button>
  );

  return (
    <div data-screen="drafting-list" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        description={
          status.state === 'ready' ?
            <span
              data-testid="list-summary"
              className="text-style-pre-caption-03 text-text-tertiary tabular-nums"
            >
              {words.summary(status.value.count)}
            </span>
          : undefined
        }
        descriptionPending={status.state === 'loading'}
        actions={introLink}
      />
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <SearchField
              aria-label={words.search}
              placeholder={words.search}
              value={query}
              maxLength={80}
              onChange={(event) => setQuery(event.target.value)}
              className="w-[300px]"
            />
            <FilterSelect
              aria-label={words.yearLabel}
              value={year}
              options={[
                { value: ALL_YEARS, label: words.yearAll },
                ...years.map((one) => ({
                  value: String(one),
                  label: words.yearOption(one),
                })),
              ]}
              onChange={setYear}
            />
            <Tabs
              value={filter}
              onValueChange={(value) => setFilter(value as ProjectFilter)}
              variant="box"
            >
              <TabsList aria-label={words.filterLabel}>
                {PROJECT_FILTERS.map((key) => (
                  <TabsTrigger key={key} value={key}>
                    {words.filters[key]}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
          {!nothingYet && newButton}
        </div>
        {/* 라이브 영역은 늘 두고 글만 넣고 뺀다 — 300ms 뒤에(greenwash-list 꼴, 밴드 RPW5 #3) */}
        <span className="sr-only" role="status">
          {announceLoading ? DR_TEXT.common.loading : null}
        </span>
        <DataTable
          table={table}
          aria-label={words.tableLabel}
          className={NOWRAP}
          layout="fixed"
          loading={status.state === 'loading'}
          onClickRow={open}
          rowLabel={(row) =>
            `${row.project.name} — ${words.next[row.view.state]}`
          }
          empty={
            status.state === 'failed' || status.state === 'not_found' ?
              <LoadFailure
                kind="failed"
                message={words.failed}
                retryLabel={DR_TEXT.common.retry}
                onRetry={retry}
              />
            : status.state === 'ready' ?
              filtered && !nothingYet ?
                <Empty
                  data-testid="list-empty-filtered"
                  title={words.filteredEmpty}
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
                  action={newButton}
                />

            : null
          }
        />
        {status.state === 'ready' &&
          status.value.count > status.value.results.length && (
            <p
              data-testid="list-more"
              className="m-0 text-style-pre-caption-03 text-text-tertiary"
            >
              {words.more}
            </p>
          )}
        {/* 표 카드 안 아래 회색 상자(판 RP-01 .e-info — 다른 모듈 목록과 같은 자리, 밴드 RPW5 #2) */}
        <PageInfo icon={<PageInfoIcon />} data-testid="list-notice">
          {words.notice}
        </PageInfo>
      </Card>
    </div>
  );
}
