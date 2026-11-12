// AD-01 고객사 사용자 계정 관리(밴드 AD1 ②③, 실서버 쓰기·거르기 UA1W ②, 시안 AD-01_r1). 라우터를 모른다: 어댑터(port)와 복사 함수(copy)를 props 로 받는다.
//   제목 줄(「고객사 사용자 계정 관리」 + 설명 + [계정 만들기]) → 안내 띠(두 문장) → 카드 하나: 거르기 줄 → 표 → 표 아래 글.
//   - 상태 칸: statusOf 하나(사용 중지 grey > 잠김 error > 초기화 대기 orange > 사용 중 success — 디자인 원문).
//   - 「만든 날」 칸은 마지막 로그인과 비밀번호 사이(KST YYYY-MM-DD — 디자인 원문 UA1W Q9). 회사 이름은 서버가 실어도 열로 넣지 않는다(1차 회사 한 곳).
//   - 설명 줄의 개수는 거르지 않은 전체 수(total — 감독 판단 Q2). 거른 수(count)나 줄 수가 아니다.
//   - 불러오기(MARC-ENT-260·MARC-ENT-443, 밴드 LD1): 첫 그림부터 표 몸에 자리 잡은 스켈레톤 줄 5(막대는 300ms 뒤 — SkeletonRows), 설명 줄 자리는 막대.
//     로딩 중 Empty 는 그리지 않는다. 숨긴 상태 글·aria-busy 는 300ms 뒤. 실패는 CM-03 꼴 실패 상자 + [다시 시도](디자인 원문).
//     [다시 시도] 뒤 초점: 또 실패면 새 [다시 시도], 받으면 제목(useRetryFocus).
//   - 만들기·초기화·사용 중지 모달은 열 때만 그린다(닫으면 상태째 사라진다 — 임시 비밀번호가 남지 않게). 닫히면 연 단추로 초점(연 단추를 적어 둔다).
//     쓰기 뒤 목록은 줄을 둔 채 다시 받는다.
// ③ 걸러 보기와 계정 수정(UA1W ② — 실서버, 모든 빌드에서 켬):
//   - 검색(아이디·이름)·상태 고르기는 서버 q·status 로 보낸다(accountQuery — 빈 q·NUL 은 보내지 않는다). 검색은 멈춘 뒤 300ms(AD-05 꼴).
//     받은 줄을 웹에서 다시 거르지 않는다.
//   - 고르기 칸으로 고른 뒤 [사용 중지] → AD-01c → 바로 적용(PATCH 를 id 마다 차례로). 고른 계정이 모두 사용 중지면 같은 자리가 [다시 사용](시안 메모 ad-a-01c).
//     모두 성공 → 모달 닫음·고름 비움. 하나라도 실패 → 모달 유지, 모달의 계정과 고름을 실패한 것만으로 줄이고 버튼 줄 위 빨강 한 줄(디자인 원문 Q4).
//     어느 쪽이든 목록은 조용히 다시 받는다.
//   - 이름 칸을 누르거나(단추 — 키보드 Enter·Space) 하면 그 줄이 편집 중(한 번에 한 줄): 이름 칸이 입력 칸, 비밀번호 칸 「편집 중」, [취소]·[저장] 켜짐.
//     편집 중 Esc = [취소], Enter = [저장](디자인 원문). [저장]은 이름 고침에만. 보내는 이름은 nameToSend(다듬음), 같은 이름이면 보내지 않는다.
//     실패는 단추 무리 옆 한 줄(role="alert"): 404 → 편집 끝·목록 다시 받음, 422·그 밖 → 편집 유지(입력 그대로) — 감독 판단 Q5.
// 표는 키트 표 꼴(시안 .a-table)을 손으로 그린다 — 편집 줄 주황 테두리를 DataTable 이 그릴 자리가 없다.
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import {
  CircleWarningIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import type { BadgeProps } from '@marcspon/ui/components/badge';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { Input } from '@marcspon/ui/components/input';
import { cn } from '@marcspon/ui/lib/utils';

import type { AccountsPort } from '../../../entities/account/api/index.ts';
import { ACCOUNT_TEXT } from '../../../entities/account/config/text.ts';
import {
  ACCESS_TTL_MINUTES,
  NO_FILTER,
  STATUS_FILTERS,
  accountQuery,
  formatCreatedDate,
  formatLastLogin,
  isFiltered,
  nameToSend,
  statusOf,
} from '../../../entities/account/model/index.ts';
import type {
  Account,
  AccountFilter,
  AccountStatus,
  StatusFilter,
} from '../../../entities/account/model/index.ts';
import { Button, buttonVariants } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  SkeletonRows,
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import type { SkeletonColumn } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import { useAccountEdits, useAccountList } from '../hooks/index.ts';
import type { RenameResult } from '../hooks/index.ts';
import { allInactive } from '../model/index.ts';
import { ActiveDialog } from './ActiveDialog.tsx';
import { CreateAccountDialog } from './CreateAccountDialog.tsx';
import { ResetPasswordDialog } from './ResetPasswordDialog.tsx';

const words = ACCOUNT_TEXT.list;

type BadgeVariant = NonNullable<BadgeProps['variant']>;
/** 상태 → 키트 badge 변형. 상태 색은 여기 한 곳에만. */
export const STATUS_LOOK = {
  inactive: 'grey',
  locked: 'error',
  initial: 'orange',
  active: 'success',
} as const satisfies Record<AccountStatus, BadgeVariant>;

/** 검색을 보내기 전에 기다리는 ms(멈춘 뒤). */
export const SEARCH_DELAY_MS = 300;

export interface AccountsScreenProps {
  port: AccountsPort;
  /** 클립보드에 쓰기(app/ 이 navigator.clipboard 를 넣는다). */
  copy(text: string): Promise<void>;
}

/** 열린 모달과 연 단추(닫히면 그리로 초점 — 누름이 단추에 초점을 주지 않는 브라우저도 있다). */
type Open =
  | { kind: 'create'; from: HTMLElement }
  | { kind: 'reset'; account: Account; from: HTMLElement }
  | {
      kind: 'active';
      isActive: boolean;
      accounts: Account[];
      /** 앞 적용의 성공·실패 수(실패가 없으면 null — 모달 안 빨강 한 줄). */
      result: { done: number; failed: number } | null;
      from: HTMLElement;
    }
  | null;

/** 편집 중인 줄과 입력 중인 이름. */
interface Editing {
  id: number;
  value: string;
}

const headClass =
  'h-10 whitespace-nowrap border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-left text-style-pre-body-05 text-text-tertiary';
const cellClass =
  'h-14 whitespace-nowrap border-0 border-b border-solid border-border-tertiary px-4 text-left';
/** 편집 중인 줄(시안 .a-edit — 주황 2px 테두리, 회색 바탕). */
const editCellClass =
  'border-y-2 border-support-orange bg-background-secondary first:border-l-2 last:border-r-2';
const COLUMN_COUNT = 7;
/** 로딩 줄의 막대(열 차례 — 고르기·아이디·이름·상태·마지막 로그인·만든 날·비밀번호). 폭은 6c 짧은 칸 값(상태 48~80 · 날짜 112 · 단추 72~88). */
const SKELETON_COLUMNS: readonly SkeletonColumn[] = [
  { width: 16 },
  {},
  {},
  { width: [48, 80] },
  { width: 112 },
  { width: 112 },
  { width: [72, 88], align: 'center' },
];
/**
 * 열 폭(px, SKELETON_COLUMNS 와 같은 차례 — 밴드 DT1 ②, J3·sid:MARC-ISSUE-374). table-fixed + <colgroup> 이라 로딩·받은 뒤 칸 폭이 같다.
 * 아이디 149 는 6c 디자인 리뷰의 받은 뒤 값(잰 내용 폭 76 보다 크다), 그 밖은 칸 내용의 가장 넓은 폭(max-content — 머리 글 포함,
 * 1280×900·e2e 흉내 자료로 잼, 올림) + 좌우 32. 고르기 48 은 옛 w-10 이 그려진 폭과 같다. 이름(null)은 폭 없음 — 남은 폭(감독 판단 10-27).
 * 긴 아이디는 아이디 칸 안에서 줄을 바꾼다(break-all — 말줄임 없이 다 보임).
 */
const COLUMN_WIDTHS: readonly (number | null)[] = [
  48,
  149,
  null,
  84,
  153,
  112,
  88,
];

/** 이름 고침 실패 → 글(단추 무리 옆 한 줄). */
const RENAME_ERROR = {
  missing: words.rename.missing,
  invalid: words.rename.invalid,
  failed: words.rename.failed,
} as const satisfies Partial<Record<RenameResult, string>>;
type RenameError = keyof typeof RENAME_ERROR;

function Head({ children, center }: { children: ReactNode; center?: boolean }) {
  return (
    <th scope="col" className={cn(headClass, center && 'text-center')}>
      {children}
    </th>
  );
}

export function AccountsScreen({ port, copy }: AccountsScreenProps) {
  const [filter, setFilter] = useState<AccountFilter>(NO_FILTER);
  // 검색 칸의 글은 바로 보이고, 서버로는 멈춘 뒤 300ms 에 간다(상태 고르기는 바로).
  const [sentQuery, setSentQuery] = useState(filter.query);
  useEffect(() => {
    if (filter.query === sentQuery) return;
    const timer = setTimeout(() => setSentQuery(filter.query), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [filter.query, sentQuery]);
  const sentFilter = { ...filter, query: sentQuery };
  const list = useAccountList(port, accountQuery(sentFilter));
  const edits = useAccountEdits({ port, onChanged: list.refresh });
  const [open, setOpen] = useState<Open>(null);
  const [selected, setSelected] = useState<ReadonlySet<number>>(new Set());
  const [editing, setEditing] = useState<Editing | null>(null);
  const [renameError, setRenameError] = useState<RenameError | null>(null);
  const applying = edits.applying;
  const loading = useDelayed(list.state.phase === 'loading');
  const retryFocus = useRetryFocus<HTMLHeadingElement>(list.state.phase);
  const state = list.state;
  // 편집이 끝나면(Esc·Enter·[저장]·[취소]) 초점을 그 줄의 이름 칸 단추로 돌린다 — 입력 칸이 사라져 body 로 떨어지지 않게(가지 리뷰).
  const nameButtons = useRef(new Map<number, HTMLButtonElement>());
  const [refocus, setRefocus] = useState<number | null>(null);
  const endEditing = () => {
    if (editing) setRefocus(editing.id);
    setEditing(null);
    setRenameError(null);
  };
  useEffect(() => {
    if (refocus === null || editing) return;
    nameButtons.current.get(refocus)?.focus();
    setRefocus(null);
  }, [refocus, editing]);

  // 받은 줄 그대로 그린다(거르기는 서버가 했다).
  const shown = state.phase === 'ready' ? state.accounts : [];
  // 고름은 보이는 줄로 한정한다 — 거르기에 숨은 고름이 사용 중지에 끼지 않게(가지 리뷰 1).
  const chosen = shown.filter((account) => selected.has(account.id));
  const reactivate = allInactive(chosen);
  const allShownChosen =
    shown.length > 0 && shown.every((account) => selected.has(account.id));
  const someShownChosen = shown.some((account) => selected.has(account.id));
  const nameToSave = editing ? nameToSend(editing.value) : null;

  const toggle = (id: number, on: boolean) =>
    setSelected((before) => {
      const next = new Set(before);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  const toggleShown = (on: boolean) =>
    setSelected((before) => {
      const next = new Set(before);
      for (const account of shown)
        if (on) next.add(account.id);
        else next.delete(account.id);
      return next;
    });

  const save = async () => {
    const account = shown.find((row) => row.id === editing?.id);
    if (!editing || !account || nameToSave === null || applying) return;
    setRenameError(null);
    const result = await edits.rename(account, nameToSave);
    if (result === null) return;
    if (result === 'renamed' || result === 'unchanged') endEditing();
    else if (result === 'missing') {
      endEditing();
      setRenameError('missing');
    } else setRenameError(result);
  };
  const applyActive = async (isActive: boolean, targets: Account[]) => {
    const outcome = await edits.setActive(targets, isActive);
    if (outcome === null) return;
    const { done, failed } = outcome;
    if (failed.length === 0) {
      setSelected(new Set());
      setOpen(null);
      return;
    }
    // 실패한 것만 남긴다(모달의 계정·고름).
    const left = new Set(failed);
    setSelected(left);
    setOpen((current) =>
      current?.kind === 'active' ?
        {
          ...current,
          accounts: current.accounts.filter((account) => left.has(account.id)),
          result: { done: done.length, failed: failed.length },
        }
      : current,
    );
  };

  const body = (content: ReactNode) => (
    <tr>
      <td colSpan={COLUMN_COUNT} className="p-0">
        {content}
      </td>
    </tr>
  );

  return (
    <div data-screen="admin-accounts" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        headingRef={retryFocus.doneRef}
        description={
          state.phase === 'ready' ? words.description(state.total) : undefined
        }
        descriptionPending={state.phase === 'loading'}
        actions={
          <Button
            variant="solidGrey"
            shape="round"
            size="md"
            onClick={(event) =>
              setOpen({ kind: 'create', from: event.currentTarget })
            }
          >
            <PlusIcon aria-hidden />
            {words.create}
          </Button>
        }
      />
      <PageInfo icon={<PageInfoIcon />}>{words.notice}</PageInfo>
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <SearchField
              aria-label={words.searchLabel}
              placeholder={words.searchPlaceholder}
              value={filter.query}
              maxLength={150}
              onChange={(event) =>
                setFilter({ ...filter, query: event.target.value })
              }
              className="w-52"
            />
            <NativeSelect
              aria-label={words.statusLabel}
              value={filter.status}
              onChange={(event) =>
                setFilter({
                  ...filter,
                  status: event.target.value as StatusFilter,
                })
              }
            >
              {STATUS_FILTERS.map((status) => (
                <option key={status} value={status}>
                  {status === 'all' ?
                    words.statusAll
                  : ACCOUNT_TEXT.status[status]}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* 라이브 영역은 늘 두고 글만 넣고 뺀다(이름 고침 실패). */}
            <p
              role="alert"
              data-testid="rename-error"
              className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
            >
              {renameError && (
                <>
                  <CircleWarningIcon aria-hidden />
                  {RENAME_ERROR[renameError]}
                </>
              )}
            </p>
            {/* 꺼짐을 aria-disabled 로(Tab 에 남는다). 공용 Button 은 aria-disabled 를 스스로 정해 네이티브 단추에 꼴만 빌린다. */}
            <button
              type="button"
              aria-disabled={chosen.length === 0 || undefined}
              className={cn(
                buttonVariants({ variant: 'outlineGrey', size: 'sm' }),
                chosen.length === 0 && 'cursor-not-allowed opacity-40',
              )}
              onClick={(event) => {
                if (chosen.length === 0) return;
                setOpen({
                  kind: 'active',
                  isActive: reactivate,
                  accounts: chosen,
                  result: null,
                  from: event.currentTarget,
                });
              }}
            >
              {reactivate ? words.reactivate : words.deactivate}
            </button>
            <Button
              variant="outlineGrey"
              size="sm"
              disabled={!editing || applying}
              onClick={endEditing}
            >
              {words.cancel}
            </Button>
            <Button
              variant="solidBlack"
              size="sm"
              disabled={!editing || nameToSave === null}
              loading={applying && editing !== null}
              onClick={() => void save()}
            >
              {words.save}
            </Button>
          </div>
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
                  <Checkbox
                    aria-label={words.selectAll}
                    checked={
                      allShownChosen ? true
                      : someShownChosen ?
                        'indeterminate'
                      : false
                    }
                    disabled={shown.length === 0}
                    onCheckedChange={(checked) => toggleShown(checked === true)}
                  />
                </th>
                <Head>{words.columns.username}</Head>
                <Head>{words.columns.name}</Head>
                <Head>{words.columns.status}</Head>
                <Head>{words.columns.lastLogin}</Head>
                <Head>{words.columns.createdAt}</Head>
                <Head center>{words.columns.password}</Head>
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
                      onClick={retryFocus.arm(list.retry)}
                    >
                      {words.retry}
                    </Button>
                  </div>,
                )
              : shown.length === 0 ?
                body(
                  <Empty
                    title={isFiltered(sentFilter) ? words.noMatch : words.empty}
                  />,
                )
              : shown.map((account) => {
                  const status = statusOf(account);
                  const isEditing = editing?.id === account.id;
                  const cell = (extra?: string) =>
                    cn(cellClass, isEditing && editCellClass, extra);
                  return (
                    <tr
                      key={account.id}
                      data-account-id={account.id}
                      data-editing={isEditing || undefined}
                    >
                      <td className={cell()}>
                        <Checkbox
                          aria-label={words.select(account.username)}
                          checked={selected.has(account.id)}
                          onCheckedChange={(checked) =>
                            toggle(account.id, checked === true)
                          }
                        />
                      </td>
                      <td
                        className={cell(
                          'whitespace-normal break-all text-text-primary',
                        )}
                      >
                        {account.username}
                      </td>
                      <td className={cell()}>
                        {isEditing ?
                          <Input
                            aria-label={words.nameLabel}
                            autoFocus
                            value={editing.value}
                            aria-invalid={nameToSave === null || undefined}
                            onChange={(event) =>
                              setEditing({
                                id: account.id,
                                value: event.target.value,
                              })
                            }
                            onKeyDown={(event) => {
                              // 한글 조합 중의 Enter·Esc 는 조합을 끝내는 키다(가지 리뷰 2).
                              if (event.nativeEvent.isComposing) return;
                              if (
                                event.key !== 'Escape' &&
                                event.key !== 'Enter'
                              )
                                return;
                              // 키의 기본 동작을 막는다 — 초점이 돌아간 이름 칸 단추가 같은 Enter 로 눌려 다시 편집에 들어가지 않게.
                              event.preventDefault();
                              if (event.key === 'Escape') endEditing();
                              else void save();
                            }}
                            className="min-w-[120px]"
                          />
                        : <button
                            type="button"
                            ref={(node) => {
                              if (node)
                                nameButtons.current.set(account.id, node);
                              else nameButtons.current.delete(account.id);
                            }}
                            aria-label={words.editName(account.username)}
                            className="cursor-text rounded-control border-0 bg-transparent p-0 text-left text-style-pre-body-06 text-text-secondary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary"
                            onClick={() => {
                              setRenameError(null);
                              setEditing({
                                id: account.id,
                                value: account.name,
                              });
                            }}
                          >
                            {account.name}
                          </button>
                        }
                      </td>
                      <td className={cell()}>
                        <Badge
                          variant={STATUS_LOOK[status]}
                          data-status={status}
                        >
                          {ACCOUNT_TEXT.status[status]}
                        </Badge>
                      </td>
                      <td className={cell('tabular-nums')}>
                        {formatLastLogin(account.lastLoginAt) ?? words.never}
                      </td>
                      <td className={cell('tabular-nums')}>
                        {formatCreatedDate(account.createdAt) ?? words.never}
                      </td>
                      <td className={cell('text-center')}>
                        {isEditing ?
                          <span className="text-style-pre-caption-02 text-support-orange">
                            {words.editing}
                          </span>
                        : <Button
                            variant="outlineGrey"
                            shape="round"
                            size="sm"
                            aria-label={words.resetLabel(account.username)}
                            onClick={(event) =>
                              setOpen({
                                kind: 'reset',
                                account,
                                from: event.currentTarget,
                              })
                            }
                          >
                            {words.reset}
                          </Button>
                        }
                      </td>
                    </tr>
                  );
                })
              }
            </tbody>
          </table>
        </div>
        <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
          {words.foot}
        </p>
      </Card>
      {open?.kind === 'create' && (
        <CreateAccountDialog
          port={port}
          copy={copy}
          onChanged={list.refresh}
          returnFocus={open.from}
          onClose={() => setOpen(null)}
        />
      )}
      {open?.kind === 'reset' && (
        <ResetPasswordDialog
          port={port}
          account={open.account}
          copy={copy}
          onChanged={list.refresh}
          returnFocus={open.from}
          onClose={() => setOpen(null)}
        />
      )}
      {open?.kind === 'active' && (
        <ActiveDialog
          isActive={open.isActive}
          accounts={open.accounts}
          ttlMinutes={ACCESS_TTL_MINUTES}
          result={open.result}
          pending={applying}
          returnFocus={open.from}
          onConfirm={() => void applyActive(open.isActive, open.accounts)}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
