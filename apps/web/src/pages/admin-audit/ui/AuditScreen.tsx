// AD-05 감사 기록(밴드 AD2 ①, 실서버 AD5R ②, 시안 AD-05_r1·디자인 원문 캔버스 v99). 서버 경로 둘(GET /audit-logs·/audit-logs/actors).
// 라우터·세션·전역 시계를 모른다: 어댑터(port)·시계(now)·링크 콜백(hrefOf·onOpen)을 props 로 받는다.
//   제목 줄 → 카드 하나: 거르기 줄(검색·기간·사람·행동 + 건수) → 표 → [더 보기] → 안내 띠. 예시 데이터 띠·바닥글은 AD5R 에서 걷었다(sid:MARC-ENT-285).
//   - 읽기 화면이라 쓰기 단추가 없다. 거르기는 서버 쿼리(model 의 auditQuery — 빈·공백 q 는 빼고, 날짜는 KST 로 세어 조인다).
//     검색은 멈춘 뒤 300ms 에 보낸다(입력 150자). 거르기가 바뀌면 첫 쪽부터.
//   - 0건(디자인 원문 2): 기간만 걸렸으면 빈 상태 「<기간> 기록이 없어요」·「기간을 넓혀 보세요.」(전체 기간이면 「아직 기록이 없어요」만),
//     검색·사람·행동이 걸렸으면 「조건에 맞는 기록이 없어요」 + [거르기 풀기](기간까지 전체로).
//   - 건수: 다 불러오지 않았으면 「{전부}건 중 {실린}건」, 다 불러왔으면 「{전부}건」(전부 = 서버 count).
//   - 사람 고르기는 행위자 목록(actorOptions — 이름 차례). 사람을 찾지 못한 줄의 대체 글(관리 명령·없는 아이디·알 수 없는 사람)은 회색.
//   - 링크 토막은 「계정」(AD-01)과 「AI 설정」(AD-02 — 판이 있으면 그 판, 밴드 AD4X ③). 보통 누름은 onOpen(경로 컴포넌트가 navigate), 새 탭 누름은 href 그대로.
//   - 불러오기(MARC-ENT-260·MARC-ENT-443, 밴드 LD1): 첫 그림부터 표 몸에 자리 잡은 스켈레톤 줄 5(막대는 300ms 뒤 — SkeletonRows), 로딩 중 빈 상태 없음.
//     숨긴 상태 글·aria-busy 는 300ms 뒤. 실패는 CM-03 꼴 실패 상자 + [다시 시도].
//     더 보기 실패는 단추 자리에 한 줄 글 + [다시 시도](CM-03 칸 하나 실패 꼴).
import { Fragment, useEffect, useMemo, useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import type { BadgeProps } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

import type { AuditServerPort } from '../../../entities/audit-log/api/index.ts';
import { AUDIT_TEXT } from '../../../entities/audit-log/config/text.ts';
import {
  AUDIT_ACTIONS,
  AUDIT_NO_FILTER,
  AUDIT_PERIODS,
  AUDIT_QUERY_MAX,
  actorOptions,
  auditQuery,
  formatAuditTime,
  toEntry,
} from '../../../entities/audit-log/model/index.ts';
import type {
  AuditAction,
  AuditFilter,
  AuditLink,
  AuditPeriod,
} from '../../../entities/audit-log/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { FilterSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  SkeletonRows,
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import type { SkeletonColumn } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import { useAuditLog } from '../hooks/index.ts';

const words = AUDIT_TEXT;

type BadgeVariant = NonNullable<BadgeProps['variant']>;
/** 행동 → 키트 badge 변형(시안: 설정 변경 orange, 확정 success, 그 밖 grey — 로그아웃도 grey). 색은 여기 한 곳에만. */
export const ACTION_LOOK = {
  login: 'grey',
  logout: 'grey',
  upload: 'grey',
  run: 'grey',
  download: 'grey',
  setting_change: 'orange',
  adopt: 'grey',
  exclude: 'grey',
  confirm: 'success',
} as const satisfies Record<AuditAction, BadgeVariant>;

/** 검색을 보내기 전에 기다리는 ms(멈춘 뒤). */
export const SEARCH_DELAY_MS = 300;

/** [거르기 풀기]: 검색·사람·행동을 비우고 기간은 전체. */
const NO_FILTER_AT_ALL: AuditFilter = { ...AUDIT_NO_FILTER, period: 'all' };

export interface AuditScreenProps {
  port: AuditServerPort;
  /** 시계(「오늘」을 KST 로 센다). 기본은 지금. */
  now?: () => Date;
  /** 링크 토막의 주소(새 탭으로 열 때). */
  hrefOf(link: AuditLink): string;
  /** 링크 토막을 눌렀을 때(경로 컴포넌트가 navigate). */
  onOpen(link: AuditLink): void;
}

const headClass =
  'h-10 whitespace-nowrap border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-left text-style-pre-body-05 text-text-tertiary';
const cellClass =
  'h-14 whitespace-nowrap border-0 border-b border-solid border-border-tertiary px-4 text-left align-middle';
const COLUMN_COUNT = 5;
/** 로딩 줄의 막대(열 차례 — 때·사람·행동·대상·결과). 폭은 6c 짧은 칸 값(날짜 112 · 상태 48~80), 그 밖은 긴 글. */
const SKELETON_COLUMNS: readonly SkeletonColumn[] = [
  { width: 112 },
  {},
  { width: [48, 80] },
  {},
  { width: [48, 80] },
];
/**
 * 열 폭(px, 같은 차례 — 밴드 DT1 ②, J3·sid:MARC-ISSUE-374). 옛 머리 칸 w-40·w-28·w-28·(없음)·w-40 을 <colgroup> 으로 옮겼다(값 그대로, 재지 않음).
 * 대상(null)은 폭 없음 — 남은 폭.
 */
const COLUMN_WIDTHS: readonly (number | null)[] = [160, 112, 112, null, 160];

/** 보통 누름만 가로챈다(새 탭·새 창 누름은 브라우저에 맡긴다). */
const plainClick = (event: MouseEvent) =>
  event.button === 0 &&
  !event.metaKey &&
  !event.ctrlKey &&
  !event.shiftKey &&
  !event.altKey;

export function AuditScreen({
  port,
  now = () => new Date(),
  hrefOf,
  onOpen,
}: AuditScreenProps) {
  const [filter, setFilter] = useState<AuditFilter>(AUDIT_NO_FILTER);
  // 검색 칸의 글은 바로 보이고, 서버로는 멈춘 뒤 300ms 에 간다.
  const [sentQuery, setSentQuery] = useState(filter.query);
  useEffect(() => {
    if (filter.query === sentQuery) return;
    const timer = setTimeout(() => setSentQuery(filter.query), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [filter.query, sentQuery]);
  const log = useAuditLog(
    port,
    auditQuery({ ...filter, query: sentQuery }, now()),
  );
  const loading = useDelayed(log.state.phase === 'loading');
  const retryFocus = useRetryFocus<HTMLHeadingElement>(log.state.phase);
  const state = log.state;
  const shown = useMemo(
    () =>
      state.phase === 'ready' ?
        state.rows.map((row) => toEntry(row, words.entry))
      : [],
    [state],
  );
  const actors = useMemo(
    () =>
      state.phase === 'ready' ?
        actorOptions(state.actors, words.entry.actor)
      : [],
    [state],
  );
  /** 기간 말고 다른 거르기(보낸 검색·사람·행동)가 있는가 — 0건 꼴을 가른다(디자인 원문 2). */
  const narrowed =
    sentQuery.trim() !== '' ||
    filter.actorUserId !== 'all' ||
    filter.action !== 'all';
  /** 거르기를 바꾼다(검색 칸 밖 — 기다린 검색 글도 바로 맞춘다). */
  const refilter = (next: AuditFilter) => {
    setFilter(next);
    setSentQuery(next.query);
  };

  const body = (content: ReactNode) => (
    <tr>
      <td colSpan={COLUMN_COUNT} className="p-0">
        {content}
      </td>
    </tr>
  );

  return (
    <div data-screen="admin-audit" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        headingRef={retryFocus.doneRef}
        description={words.description}
      />
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <SearchField
              aria-label={words.searchLabel}
              placeholder={words.searchPlaceholder}
              value={filter.query}
              maxLength={AUDIT_QUERY_MAX}
              onChange={(event) =>
                setFilter({ ...filter, query: event.target.value })
              }
              className="w-52"
            />
            <FilterSelect<AuditPeriod>
              label={words.period.label}
              aria-label={words.period.name}
              value={filter.period}
              options={AUDIT_PERIODS.map((period) => ({
                value: period,
                label: words.period.options[period],
              }))}
              onChange={(period) => refilter({ ...filter, period })}
            />
            <FilterSelect<string>
              label={words.actor.label}
              aria-label={words.actor.name}
              value={String(filter.actorUserId)}
              options={[
                { value: 'all', label: words.actor.all },
                ...actors.map((actor) => ({
                  value: String(actor.value),
                  label: actor.label,
                })),
              ]}
              onChange={(actor) =>
                refilter({
                  ...filter,
                  actorUserId: actor === 'all' ? 'all' : Number(actor),
                })
              }
            />
            <FilterSelect<AuditAction | 'all'>
              label={words.action.label}
              aria-label={words.action.name}
              value={filter.action}
              options={[
                { value: 'all', label: words.action.all },
                ...AUDIT_ACTIONS.map((action) => ({
                  value: action,
                  label: words.actions[action],
                })),
              ]}
              onChange={(action) => refilter({ ...filter, action })}
            />
          </div>
          {state.phase === 'ready' && (
            <span
              data-testid="count"
              className="text-style-pre-caption-03 text-text-tertiary"
            >
              {state.isNext ?
                words.countOf(state.count, state.rows.length)
              : words.count(state.count)}
            </span>
          )}
        </div>
        {/* 라이브 영역은 늘 두고 글만 넣고 뺀다(밴드 LA1 ①). */}
        <span className="sr-only" role="status">
          {loading ? words.loading : null}
        </span>
        <div className="w-full overflow-x-auto">
          <table
            aria-label={words.tableLabel}
            aria-busy={loading || undefined}
            className="w-full table-fixed border-separate border-spacing-0 text-style-pre-body-06 text-text-secondary"
          >
            <colgroup>
              {COLUMN_WIDTHS.map((width, index) => (
                <col
                  key={index}
                  style={width === null ? undefined : { width }}
                />
              ))}
            </colgroup>
            <thead>
              <tr>
                <th scope="col" className={headClass}>
                  {words.columns.at}
                </th>
                <th scope="col" className={headClass}>
                  {words.columns.actor}
                </th>
                <th scope="col" className={headClass}>
                  {words.columns.action}
                </th>
                <th scope="col" className={headClass}>
                  {words.columns.target}
                </th>
                <th scope="col" className={headClass}>
                  {words.columns.result}
                </th>
              </tr>
            </thead>
            <tbody>
              {state.phase === 'loading' ?
                <SkeletonRows columns={SKELETON_COLUMNS} />
              : state.phase === 'failed' ?
                body(
                  <div
                    role="alert"
                    data-testid="load-failure"
                    className="flex flex-col items-start gap-4 py-6"
                  >
                    <PageInfo
                      tone="error"
                      icon={<CircleWarningIcon aria-hidden />}
                      className="w-full"
                    >
                      {words.failed}
                    </PageInfo>
                    <Button
                      ref={retryFocus.actionRef}
                      variant="solidBlack"
                      shape="round"
                      size="md"
                      onClick={retryFocus.arm(log.retry)}
                    >
                      {words.retry}
                    </Button>
                  </div>,
                )
              : shown.length === 0 && !narrowed ?
                // 기간만 거른 0건: 빈 상태 두 줄(전체 기간이면 한 줄), [거르기 풀기] 없음.
                body(
                  <Empty
                    data-testid="empty"
                    className="min-h-[120px]"
                    title={
                      filter.period === 'all' ?
                        words.emptyAll
                      : words.emptyPeriod(words.period.options[filter.period])
                    }
                    description={
                      filter.period === 'all' ? undefined : words.widenPeriod
                    }
                  />,
                )
              : shown.length === 0 ?
                body(
                  <div
                    data-testid="no-match"
                    className="flex min-h-[120px] flex-col items-center justify-center gap-3"
                  >
                    <p className="m-0 text-style-pre-body-06 text-text-tertiary">
                      {words.noMatch}
                    </p>
                    <Button
                      variant="outlineGrey"
                      shape="round"
                      size="sm"
                      onClick={() => refilter(NO_FILTER_AT_ALL)}
                    >
                      {words.clearFilter}
                    </Button>
                  </div>,
                )
              : shown.map((entry) => (
                  <tr key={entry.id} data-audit-id={entry.id}>
                    <td className={cn(cellClass, 'tabular-nums')}>
                      {formatAuditTime(entry.at)}
                    </td>
                    <td
                      className={cn(
                        cellClass,
                        entry.actorMissing && 'text-text-tertiary',
                      )}
                      data-actor-missing={entry.actorMissing || undefined}
                    >
                      {entry.actor}
                    </td>
                    <td className={cellClass}>
                      <Badge
                        variant={ACTION_LOOK[entry.action]}
                        data-action={entry.action}
                      >
                        {words.actions[entry.action]}
                      </Badge>
                    </td>
                    <td className={cn(cellClass, 'whitespace-normal')}>
                      {entry.target.length === 0 ?
                        words.noTarget
                      : entry.target.map((part, index) => {
                          const { link } = part;
                          return (
                            <Fragment key={index}>
                              {index > 0 && ' · '}
                              {link ?
                                <a
                                  href={hrefOf(link)}
                                  onClick={(event) => {
                                    if (!plainClick(event)) return;
                                    event.preventDefault();
                                    onOpen(link);
                                  }}
                                  className="text-text-secondary underline hover:text-text-primary"
                                >
                                  {part.text}
                                </a>
                              : part.text}
                            </Fragment>
                          );
                        })
                      }
                    </td>
                    <td className={cellClass}>
                      {entry.failure === null ?
                        words.success
                      : <span
                          data-failure
                          className="text-support-error-accent"
                        >
                          {words.failure(entry.failure)}
                        </span>
                      }
                    </td>
                  </tr>
                ))
              }
            </tbody>
          </table>
        </div>
        {state.phase === 'ready' && state.isNext && (
          <div className="flex justify-center" data-testid="more">
            {state.more === 'failed' ?
              <div
                role="alert"
                className="flex items-center gap-3 text-style-pre-body-06 text-text-tertiary"
              >
                <span>{words.moreFailed}</span>
                <Button
                  variant="outlineGrey"
                  shape="round"
                  size="sm"
                  onClick={log.more}
                >
                  {words.retry}
                </Button>
              </div>
            : <Button
                variant="outlineGrey"
                shape="round"
                size="md"
                loading={state.more === 'loading'}
                onClick={log.more}
              >
                {words.more}
              </Button>
            }
          </div>
        )}
        <PageInfo icon={<PageInfoIcon />}>{words.notice}</PageInfo>
      </Card>
    </div>
  );
}
