// GW-01 문서 목록(밴드 FW2 ②). 시안 GW-01_r1(캔버스 v74·v76 같음)의 구성:
//   제목 줄(「문서 목록」, 운영 관리자만 meta 「작업 회사 …」 — sid:MARC-ENT-603) → 카드 하나: 거르기 줄(검색 · 보고연도 · 상태 박스 탭 여섯 ·
//   「내가 올린 것만」 · 오른쪽 [새 점검]) → 표(FK2 DataTable) → 카드 안 아래 안내 상자(PageInfo, GW3R A7). 제목 줄 오른쪽 「점검 안내」 → GW-00.
// 줄과 거르기는 headless useCheckList(→ domain buildCheckRows·filterCheckRows). 이 파일은 그리기와 이동만.
//   - 줄 누르기: 결과가 있는 줄(검토 대기·검토 중·검토 완료) → GW-04, AI 점검 중·멈춤 → GW-03. 줄 안 [다음 할 일] 버튼은 줄 누르기를 일으키지
//     않는다(DataTable 의 칸 안 컨트롤 규칙, sid:MARC-ISSUE-85 1). 누를 수 있는 줄은 rowLabel 로 이름을 단다.
//   - 다음 할 일: 진행 보기 → GW-03, 다시 실행 → rerun 뒤 새 실행의 GW-03(거절되면 role="alert"), 검토하기·검토 이어 하기 → GW-05,
//     결과 보기 → GW-05(잠긴 상태).
//   - 보고연도는 네이티브 select(키트 Select 고쳐 쓰기는 sid:MARC-ISSUE-85 7, 이 밴드 밖). 「보고연도 전체」는 지은 글.
//   - 상태 탭은 키트 Tabs(box). 표가 그 탭의 패널이다. 버전 칸은 없다(v115 GW-01_r2 — 수정본 뺌, sid:MARC-ENT-354 2, 밴드 GW2R ①).
//   - 페이지 나누기는 하지 않는다(목 ≤ 20건. 무효 조건: 서버 목록은 {count, isNext, results}).
//   - 불러오기(밴드 LE1·GL1, sid:MARC-ENT-260·443): 표는 첫 그림부터 머리줄 + 자리 잡은 스켈레톤 줄(DataTable loading 은 날 값, 막대는
//     표가 300ms 뒤에. 줄 높이가 진짜 줄과 같아 받은 뒤 카드가 줄었다 늘지 않는다 — sid:MARC-ISSUE-316). 막대 폭은 열 meta.skeleton.
//     설명 줄(운영 관리자의 작업 회사)은 받기 전 같은 높이의 막대 자리(descriptionPending). 표 옆 숨긴 글은 300ms 뒤에(useDelayed).
//     숨긴 글의 role="status" 는 늘 두고 글만 넣고 뺀다(밴드 LA1 ①). aria-busy 는 DataTable 이 표에 단다.
//     표 몸의 빈 자리(empty)는 ready 면 빈 목록 글, failed 면 실패 상자(「문서 목록을 불러오지 못했어요」 + [다시 시도]. 목록 화면이라
//     [목록으로]는 없다). 로딩 중에는 표가 empty 를 그리지 않는다.
//     [다시 시도] 뒤 초점(밴드 LA1 ②, useRetryFocus): 또 실패면 새 [다시 시도], 받으면 제목 줄 h2(tabIndex -1).
//   - 표 아래 튕김·칸 폭(밴드 GL3, sid:MARC-ISSUE-397·374): 표 자리는 최소 머리줄 + 스켈레톤 줄 5(TABLE_MIN_HEIGHT)라 줄이 적게 와도
//     안내 띠가 올라오지 않는다(남는 자리는 흰 바탕 — 6c 답 (a)). 표는 layout="fixed" + 짧은 칸 meta.width(그 칸 max-content + 칸 안쪽 32,
//     목 씨앗·흉내 서버 줄로 잰 값), 문서명은 남은 폭(긴 이름은 한 줄 말줄임 + title) — 빈 스켈레톤·막대·진짜 줄이 같은 칸 폭을 쓴다.
import { useId } from 'react';

import {
  CircleWarningIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { Label } from '@marcspon/ui/components/label';

import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import {
  CHECK_ROW_TABS,
  canRerun,
  formatKst,
  formatKstMonthDay,
} from '../../../entities/greenwash/model/index.ts';
import type {
  CheckRow,
  CheckRowStatus,
  CheckRowTab,
  NextAction,
} from '../../../entities/greenwash/model/index.ts';
import {
  LoadFailure,
  RiskBadge,
  RunStatusBadge,
} from '../../../entities/greenwash/ui/index.ts';
import type { RunStatus } from '../../../entities/greenwash/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../../shared/ui/tabs/index.ts';
import { useCheckList } from '../hooks/index.ts';

const words = GW_TEXT.list;

/** 줄 누르기·다음 할 일이 가는 곳. */
export type ListTarget =
  | { screen: 'status'; runId: string }
  | { screen: 'result'; runId: string }
  | { screen: 'review'; runId: string };

export interface ListScreenProps {
  store: GreenwashStore;
  /** [새 점검]. */
  onNewCheck(): void;
  /** 줄 누르기·다음 할 일. */
  onOpen(target: ListTarget): void;
  /** 쓰기(새 점검·다시 실행 등)를 켜는가. 거짓이면 쓰기 단추를 숨긴다(로그인하지 않은 세션 — 운영 관리자도 고객사 사용자와 같이 쓴다, sid:MARC-ENT-409). 기본 참. */
  canWrite?: boolean;
  /**
   * 운영 관리자인가(GW-01b, sid:MARC-ENT-409 남김). 참이면 「내가 올린 것만」을 숨기고(올린 문서가 없다) 제목 줄 meta 를
   * 「작업 회사 …」로 쓴다. 줄의 다음 할 일·안내 글·쓰기 단추는 고객사 사용자와 같다. 기본 거짓.
   */
  operator?: boolean;
  /** 제목 줄 오른쪽 「점검 안내」(GW-00 으로 — 시안 GW-01_r2·01b_r1, GW3R A8). 없으면 링크를 그리지 않는다. */
  onIntro?(): void;
}

/** 줄 누르기의 갈 곳: 결과가 있으면 GW-04, 아니면 GW-03. */
function rowTarget(row: CheckRow): ListTarget | null {
  if (!row.lastRun || !row.status) return null;
  const runId = row.lastRun.runId;
  return row.status === 'running' || row.status === 'failed' ?
      { screen: 'status', runId }
    : { screen: 'result', runId };
}

function badgeOf(row: CheckRow): RunStatus | null {
  const status: CheckRowStatus | null = row.status;
  const review = row.lastRun?.review ?? null;
  switch (status) {
    case 'running':
      return { kind: 'analyzing', progress: row.percent ?? undefined };
    case 'failed':
      return { kind: 'failed' };
    case 'pending':
      return { kind: 'pending' };
    case 'in_review':
      return {
        kind: 'reviewing',
        reviewed: review?.reviewed ?? 0,
        total: review?.total ?? 0,
      };
    case 'confirmed':
      return {
        kind: 'confirmed',
        by: review?.confirmedBy ?? undefined,
        at:
          review?.confirmedAt ?
            formatKstMonthDay(review.confirmedAt)
          : undefined,
      };
    default:
      return null;
  }
}

/** High·Mid·Low 열: 결과 등급 → RiskBadge 등급, 머리 글. */
const LEVEL_COLUMNS = [
  { level: 'High', risk: 'high', header: words.columns.high, width: 62 },
  { level: 'Mid', risk: 'mid', header: words.columns.mid, width: 66 },
  { level: 'Low', risk: 'low', header: words.columns.low, width: 66 },
] as const;

/** 표 자리 최소 높이: 머리줄 40 + 스켈레톤 줄 5 × 56(DataTable 기본 줄 수·줄 높이) + 머리줄 위 선 1(border-collapse 바깥 선 — 잰 표 높이 321). */
const TABLE_MIN_HEIGHT = 'min-h-[321px]';

/** ISO → 「YYYY-MM-DD」(한국 시각). 읽을 수 없으면 받은 글자 그대로(formatKst 와 같다). */
function kstDate(iso: string): string {
  const full = formatKst(iso);
  return full === iso ? iso : full.slice(0, 10);
}

const muted = <span className="text-text-tertiary">{words.none}</span>;

export function ListScreen({
  store,
  onNewCheck,
  onOpen,
  canWrite = true,
  operator = false,
  onIntro,
}: ListScreenProps) {
  const list = useCheckList(store);
  const loading = list.status.state === 'loading';
  // 숨긴 상태 글만 300ms 뒤에(sid:MARC-ENT-260). 표는 날 값을 받아 스스로 늦춘다.
  const announceLoading = useDelayed(loading);
  const retryFocus = useRetryFocus<HTMLHeadingElement>(list.status.state);
  const yearId = useId();
  const mineId = useId();

  const act = async (row: CheckRow, next: NextAction) => {
    const runId = row.lastRun!.runId;
    switch (next) {
      case 'view_progress':
        return onOpen({ screen: 'status', runId });
      case 'rerun': {
        const created = await list.rerun(runId);
        if (created !== null) onOpen({ screen: 'status', runId: created });
        return;
      }
      default:
        return onOpen({ screen: 'review', runId });
    }
  };

  // 열 정의는 그릴 때마다 짓는다(줄 안 버튼이 act 를 부른다. 목록이 짧다).
  const columns: DataTableColumnDef<CheckRow>[] = [
    {
      id: 'fileName',
      header: words.columns.fileName,
      enableSorting: false,
      meta: { skeleton: 'long' },
      // 한 줄 말줄임 + title 에 전체 이름(6c 답, 밴드 GL3 — 실행 기록 표 문서 칸과 같은 꼴). 줄 높이는 늘 56.
      cell: ({ row }) => (
        <span
          className="block truncate text-text-primary"
          title={row.original.doc.fileName}
        >
          {row.original.doc.fileName}
        </span>
      ),
    },
    {
      id: 'reportYear',
      header: words.columns.reportYear,
      enableSorting: false,
      meta: { align: 'center', skeleton: 40, width: 80 },
      cell: ({ row }) => row.original.doc.reportYear ?? muted,
    },
    {
      id: 'uploadedBy',
      header: words.columns.uploadedBy,
      enableSorting: false,
      meta: { width: 115 },
      cell: ({ row }) => row.original.doc.uploadedBy.name,
    },
    {
      id: 'pageCount',
      header: words.columns.pageCount,
      enableSorting: false,
      meta: { align: 'right', skeleton: [24, 32], width: 84 },
      // 쪽 수를 모르면 「–」(다른 빈 값과 같은 꼴 — 디자인 답 ①, 밴드 GW1R ②). 값이 오면 그대로 숫자.
      cell: ({ row }) =>
        row.original.doc.pageCount === null ?
          muted
        : <span className="tabular-nums">{row.original.doc.pageCount}</span>,
    },
    {
      id: 'lastRun',
      header: words.columns.lastRun,
      enableSorting: false,
      meta: { skeleton: 112, width: 153 },
      // 「AI점검 완료 일자」(시안 댓글, sid:MARC-ENT-603): 마지막 실행이 done 일 때 끝난 때(checks@1 runs[].finishedAt)의
      // 한국 날짜. 실패·도는 중·끝난 때 없음(옛 서버)은 「–」(GCB1 — 감독 Q-A1 (나)).
      cell: ({ row }) => {
        const lastRun = row.original.lastRun;
        return lastRun?.progress.state === 'done' && lastRun.finishedAt ?
            <span className="tabular-nums">{kstDate(lastRun.finishedAt)}</span>
          : muted;
      },
    },
    ...LEVEL_COLUMNS.map(
      ({ level, risk, header, width }): DataTableColumnDef<CheckRow> => ({
        id: level,
        header,
        enableSorting: false,
        meta: { align: 'center', width },
        cell: ({ row }) => {
          const counts = row.original.lastRun?.levelCounts;
          if (!counts) return muted;
          return (
            <span data-testid={`count-${risk}`} className="inline-flex">
              <RiskBadge level={risk} count={counts[level]} display="count" />
            </span>
          );
        },
      }),
    ),
    {
      id: 'status',
      header: words.columns.status,
      enableSorting: false,
      meta: { skeleton: [48, 80], width: 149 },
      cell: ({ row }) => {
        const badge = badgeOf(row.original);
        return badge ?
            <span data-testid="row-status" data-status={row.original.status}>
              {/* 목록은 「검토 중」만(n/전체는 검토 화면 진행에 — 시안 댓글, sid:MARC-ENT-603) */}
              <RunStatusBadge status={badge} showCount={false} />
            </span>
          : muted;
      },
    },
    {
      id: 'next',
      header: words.columns.next,
      enableSorting: false,
      meta: { align: 'center', skeleton: [72, 88], width: 122 },
      cell: ({ row }) => {
        const next = row.original.next;
        if (!next) return muted;
        if (next === 'rerun') {
          // 쓰지 못하는 세션(로그인하지 않음)이면 [다시 실행] 자리는 빈칸(대체 글 없음 — 디자인 원문 3). 운영 관리자는 고객사와 같다(sid:MARC-ENT-409 J1c).
          // 글자 없는 PDF·서비스 설정 문제로 멈춘 실행도 빈칸(같은 입력으로 다시 돌려도 같은 끝 — 디자인 원문 2, 밴드 GW1R ②·GW2R ② Q5).
          // 가름은 실패 code 하나다(canRerun — 단계·글로 가르지 않는다).
          if (!canWrite || !canRerun(row.original.lastRun?.errorCode))
            return null;
          // 도는 동안은 aria-disabled + 도는 표시(누름은 Button 이 캡처 단계에서 막고, 초점은 남는다 — 밴드 FW2 ⑤ M1)
          const busy = list.rerunning === row.original.lastRun?.runId;
          // 답이 끊긴 실행도 켜 둔다 — 다시 누르면 그 실행의 열쇠로 보내 실행은 하나다(밴드 GR2, sid:MARC-ISSUE-225 · GR1 검증 R2)
          return (
            <Button
              asChild
              loading={busy}
              variant="outlineGrey"
              shape="round"
              size="sm"
            >
              <button
                type="button"
                data-next={next}
                onClick={() => void act(row.original, next)}
              >
                {words.next[next]}
              </button>
            </Button>
          );
        }
        // 운영 관리자도 고객사와 같은 다음 할 일(sid:MARC-ENT-409 J1b — 「결과 보기」 갈래를 걷음).
        return (
          <Button
            variant="outlineGrey"
            shape="round"
            size="sm"
            data-next={next}
            onClick={() => void act(row.original, next)}
          >
            {words.next[next]}
          </Button>
        );
      },
    },
  ];

  const table = useDataTable({
    data: list.rows as CheckRow[],
    columns,
    getRowId: (row) => row.doc.documentId,
  });

  const filtered =
    list.filter.query.trim() !== '' ||
    list.filter.reportYear !== null ||
    list.filter.tab !== 'all' ||
    list.filter.mineOnly;

  return (
    <div data-screen="list" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        headingRef={retryFocus.doneRef}
        // 설명 줄은 운영 관리자의 작업 회사만(고객사 사용자의 「회사 · 문서 n건 · 실행 n회 · …」 줄은 지움 — 시안 댓글, sid:MARC-ENT-603)
        description={
          operator && list.status.state === 'ready' ?
            words.metaOperator(list.companyName)
          : undefined
        }
        descriptionPending={operator && loading}
        actions={
          onIntro && (
            <a
              href="/greenwash/intro"
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
        <Tabs
          value={list.filter.tab}
          onValueChange={(value) => list.setTab(value as CheckRowTab)}
          variant="box"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <SearchField
                aria-label={words.searchLabel}
                placeholder={words.searchPlaceholder}
                value={list.filter.query}
                onChange={(event) => list.setQuery(event.target.value)}
                className="w-[300px]"
              />
              <label htmlFor={yearId} className="sr-only">
                {words.yearLabel}
              </label>
              <NativeSelect
                id={yearId}
                value={list.filter.reportYear ?? ''}
                onChange={(event) =>
                  list.setReportYear(
                    event.target.value === '' ?
                      null
                    : Number(event.target.value),
                  )
                }
              >
                <option value="">{words.yearAll}</option>
                {list.years.map((year) => (
                  <option key={year} value={year}>
                    {words.year(year)}
                  </option>
                ))}
              </NativeSelect>
              <TabsList aria-label={words.tabsLabel}>
                {CHECK_ROW_TABS.map((tab) => (
                  <TabsTrigger key={tab} value={tab}>
                    {words.tabs[tab]}
                  </TabsTrigger>
                ))}
              </TabsList>
              {/* 운영 관리자는 올린 문서가 없어 「내가 올린 것만」을 숨긴다(GW-01b, sid:MARC-ENT-409 J1a). 거르기 값은 기본 거짓 그대로다. */}
              {!operator && (
                <div className="flex items-center gap-2">
                  <Checkbox
                    id={mineId}
                    checked={list.filter.mineOnly}
                    onCheckedChange={(checked) =>
                      list.setMineOnly(checked === true)
                    }
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
            {canWrite && (
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                onClick={onNewCheck}
              >
                <PlusIcon aria-hidden />
                {words.newCheck}
              </Button>
            )}
          </div>

          {list.rerunError !== null && (
            <PageInfo
              tone="error"
              role="alert"
              icon={<CircleWarningIcon aria-hidden />}
              data-testid="list-rerun-error"
              data-error={list.rerunError.error}
              className="mt-4"
            >
              {list.rerunError.error === 'unreachable' ?
                <span className="inline-flex flex-wrap items-center gap-2">
                  {GW_TEXT.runUnreachable.rerun}
                  <Button
                    variant="outlineGrey"
                    shape="round"
                    size="sm"
                    onClick={list.retry}
                  >
                    {words.reload}
                  </Button>
                </span>
              : words.rerunRejected}
            </PageInfo>
          )}
          <TabsContent
            value={list.filter.tab}
            data-testid="list-table-area"
            className={`mt-4 ${TABLE_MIN_HEIGHT}`}
          >
            {/* 라이브 영역은 늘 두고 글만 넣고 뺀다(글과 함께 마운트되면 낭독이 빠질 수 있다 — 밴드 LA1 ①) */}
            <span className="sr-only" role="status">
              {announceLoading ? words.loading : null}
            </span>
            <DataTable
              table={table}
              aria-label={words.tableLabel}
              layout="fixed"
              loading={loading}
              onClickRow={(row) => {
                const target = rowTarget(row);
                if (target) onOpen(target);
              }}
              // 실행이 없는 문서 줄은 누를 수 없다(갈 곳이 없다 — 검증 N1)
              isRowClickable={(row) => rowTarget(row) !== null}
              rowLabel={(row) =>
                words.rowLabel(
                  row.doc.fileName,
                  rowTarget(row)?.screen === 'result' ?
                    words.rowOpen.result
                  : words.rowOpen.status,
                )
              }
              empty={
                list.status.state === 'ready' ?
                  <Empty
                    title={words.emptyTitle}
                    description={filtered ? words.emptyFiltered : undefined}
                  />
                : list.status.state === 'failed' ?
                  <LoadFailure
                    kind="failed"
                    message={words.loadFailed}
                    onRetry={retryFocus.arm(list.retry)}
                    actionRef={retryFocus.actionRef}
                  />
                : null
              }
            />
          </TabsContent>
        </Tabs>
        {/* 표 카드 안 회색 상자(시안 .e-info, GW3R A7) */}
        <PageInfo icon={<PageInfoIcon />} data-testid="list-notice">
          {words.notice}
        </PageInfo>
      </Card>
    </div>
  );
}
