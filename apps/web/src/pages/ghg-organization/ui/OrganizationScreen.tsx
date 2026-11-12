// S15 조직구조 목록(밴드 W12-0a ② — 스펙 ② S15, 꼴은 AD-01 pages/admin-accounts 의 표·고르기·확인 창). 라우터·세션을 모른다:
//   실어댑터(port)와 이동 콜백(onOpen·onNew)을 props 로 받는다. 고객사 사용자·운영 관리자 같은 화면(sid:MARC-ENT-469 4 — 서버가 작업 회사를 정함).
//   - 제목 「조직구조」만(회사 머리 띠는 1차에 뺌 — Q4). 「사업장」 탭 하나라 탭 줄을 그리지 않는다. ≡ 손잡이 0(469-5).
//   - 사업장명 검색: 멈춘 뒤 300ms 에 서버 q 로(AD-01 꼴), 쪽은 1로. 받은 줄을 웹에서 다시 거르지 않는다.
//   - 표: 체크박스 · 사업장명 · 인벤토리 사용 토글 · 행 끝 >. 행(고르기·토글 밖)이나 > 를 누르면 상세(onOpen) · Tab+Enter(sid:MARC-ENT-599).
//     본사 행은 체크박스 비활성 · 토글은 켜진 채 비활성(흐림) [스펙 확인]. 행 토글은 바로 POST /branches/inventory — 기다리는 동안 꺼짐,
//     실패면 되돌리고 한 줄.
//   - 단추: 「인벤토리 사용취소」「인벤토리 사용」(고른 행 일괄 — 끄기는 본사를 뺌, model inventoryTargets) · 「사업장 삭제」(확인 창) ·
//     「사업장 추가」. 고른 것이 없으면 앞 셋은 꺼짐(aria-disabled — Tab 에 남는다). 쓰기 뒤 고름을 비우고 목록을 다시 읽는다.
//   - 상태: 불러오는 중(스켈레톤 줄) · 검색 결과 없음 · 읽기 실패 + [다시 시도] · 회사 거절(글 한 줄, 다시 시도 없음 — 설정 잘못) ·
//     쓰기 거절 HEADQUARTERS_LOCKED·IN_USE·그 밖은 단추 줄 옆 한 줄. 서버 message 는 그리지 않는다.
//   - 밴드 W12-0b1 ①(sid:MARC-ISSUE-426): 쓰기의 회사 거절은 회사 글(L4) · 회사 글은 운영 관리자면 companyOperator(operator prop —
//     pages 는 세션을 모른다) · 행 토글 기다림 표시는 끝난 요청의 줄만 걷는다(L2 — 다른 줄 토글이 걸려 있어도 남는다).
import { useEffect, useRef, useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';

import {
  ChevronRightIcon,
  CircleWarningIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { Switch } from '@marcspon/ui/components/switch';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  CompanyRefusal,
  GhgOrganizationPort,
  WriteOutcome,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { useBranches } from '../../../entities/ghg/hooks/index.ts';
import {
  canToggleInventory,
  deleteTargets,
  inventoryTargets,
  isSelectable,
} from '../../../entities/ghg/model/index.ts';
import type { Branch } from '../../../entities/ghg/model/index.ts';
import { Button, buttonVariants } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  ROW_FOCUS,
  ROW_HOVER,
  clickableRowProps,
} from '../../../shared/ui/data-table/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import {
  SkeletonRows,
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import type { SkeletonColumn } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';

const words = GHG_TEXT.organization;

/** 검색을 보내기 전에 기다리는 ms(멈춘 뒤 — AD-01 과 같다). */
export const SEARCH_DELAY_MS = 300;

export interface OrganizationScreenProps {
  port: GhgOrganizationPort;
  /** 행·> → 사업장 상세. */
  onOpen(id: string): void;
  /** 「사업장 추가」 → 새 사업장. */
  onNew(): void;
  /** 운영 관리자 세션인가(회사 거절 글을 가른다 — app/ghg 의 useOperator). */
  operator?: boolean;
}

/** 누를 수 있는 줄(DataTable 과 같은 셋 — 커서·hover·초점). 누를 수 없는 줄은 셋 다 없다(결정 599 규칙 2). */
const CLICKABLE_ROW = ['cursor-pointer', ROW_HOVER, ROW_FOCUS];

/** 단추 줄 옆 한 줄(쓰기 거절·실패). */
type Notice =
  | 'headquartersLocked'
  | 'inUse'
  | 'writeFailed'
  | { company: CompanyRefusal }
  | null;

const headClass =
  'h-10 whitespace-nowrap border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-left text-style-pre-body-05 text-text-tertiary';
/** GX2 S12-04: 체크는 20(size lg — 같은 모듈 입력 창과 같이). */
const cellClass =
  'h-14 whitespace-nowrap border-0 border-b border-solid border-border-tertiary px-4 text-left';
const COLUMN_COUNT = 4;
/** 로딩 줄의 막대(열 차례 — 고르기·사업장명·토글·>). */
const SKELETON_COLUMNS: readonly SkeletonColumn[] = [
  { width: 16 },
  {},
  { width: 40 },
  { width: 16, align: 'center' },
];
const COLUMN_WIDTHS: readonly (number | null)[] = [48, null, 160, 64];

/** 쓰기 결과 → 단추 줄 옆 한 줄(성공이면 null). */
function noticeOf(outcome: WriteOutcome<unknown>): Notice {
  if (outcome.kind === 'ok') return null;
  if (outcome.kind === 'refused') return { company: outcome.company };
  if (outcome.kind === 'rejected' && outcome.code === 'HEADQUARTERS_LOCKED')
    return 'headquartersLocked';
  if (outcome.kind === 'rejected' && outcome.code === 'IN_USE') return 'inUse';
  return 'writeFailed';
}

/** 꺼짐을 aria-disabled 로 그리는 단추(Tab 에 남는다 — AD-01 꼴). */
function GatedButton({
  off,
  onPress,
  children,
}: {
  off: boolean;
  onPress(event: MouseEvent<HTMLButtonElement>): void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-disabled={off || undefined}
      className={cn(
        buttonVariants({ variant: 'outlineGrey', size: 'sm' }),
        off && 'cursor-not-allowed opacity-40',
      )}
      onClick={(event) => {
        if (!off) onPress(event);
      }}
    >
      {children}
    </button>
  );
}

export function OrganizationScreen({
  port,
  onOpen,
  onNew,
  operator = false,
}: OrganizationScreenProps) {
  const companyText = operator ? GHG_TEXT.companyOperator : GHG_TEXT.company;
  const [query, setQuery] = useState('');
  const [sentQuery, setSentQuery] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => {
    if (query === sentQuery) return;
    const timer = setTimeout(() => {
      setSentQuery(query);
      setPage(1);
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [query, sentQuery]);
  const list = useBranches(port, sentQuery, page);
  const status = list.status;
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  /** 행 토글을 보내는 동안 보이는 값(id → 바뀐 값). */
  const [toggling, setToggling] = useState<ReadonlyMap<string, boolean>>(
    new Map(),
  );
  /** 답이 아직 안 온 행 토글의 줄 id(다시 읽은 값이 와도 이 줄의 보이는 값은 남긴다 — L2). */
  const inFlight = useRef<Set<string>>(new Set());
  const [confirm, setConfirm] = useState<HTMLElement | null>(null);
  const loading = useDelayed(status.state === 'loading');
  const retryFocus = useRetryFocus<HTMLHeadingElement>(
    status.state === 'loading' ? 'loading'
    : status.state === 'ready' ? 'ready'
    : 'failed',
  );

  const shown = status.state === 'ready' ? status.value.results : [];
  // 지운 뒤 쪽이 비면 앞 쪽으로.
  const pageEmptied =
    status.state === 'ready' && shown.length === 0 && page > 1;
  useEffect(() => {
    if (pageEmptied) setPage((before) => Math.max(1, before - 1));
  }, [pageEmptied]);
  // 고름은 보이는 줄 중 고를 수 있는 것으로 한정한다(본사·다른 쪽 줄이 일괄에 끼지 않게).
  const selectable = shown.filter(isSelectable);
  const chosen = selectable.filter((branch) => selected.has(branch.id));
  const none = chosen.length === 0 || busy;
  const allChosen =
    selectable.length > 0 &&
    selectable.every((branch) => selected.has(branch.id));

  const toggle = (id: string, on: boolean) =>
    setSelected((before) => {
      const next = new Set(before);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  const toggleAll = (on: boolean) =>
    setSelected(
      on ? new Set(selectable.map((branch) => branch.id)) : new Set(),
    );

  /** 쓰기 하나: 한 줄을 비우고 → 보냄 → 한 줄·고름 비움·목록 다시 읽기. */
  const write = async (send: () => Promise<WriteOutcome<unknown>>) => {
    setBusy(true);
    setNotice(null);
    const outcome = await send();
    setBusy(false);
    setNotice(noticeOf(outcome));
    if (outcome.kind === 'ok') setSelected(new Set());
    list.reload();
    return outcome;
  };
  const setInventory = (enabled: boolean) => {
    const ids = inventoryTargets(chosen, enabled);
    if (ids.length === 0) return;
    void write(() => port.setInventory(ids, enabled));
  };
  const remove = async () => {
    const ids = deleteTargets(chosen);
    if (ids.length > 0) await write(() => port.deleteBranches(ids));
    setConfirm(null);
  };
  const toggleRow = async (branch: Branch) => {
    const next = !(toggling.get(branch.id) ?? branch.inventoryEnabled);
    setToggling((before) => new Map(before).set(branch.id, next));
    setNotice(null);
    inFlight.current.add(branch.id);
    const outcome = await port.setInventory([branch.id], next);
    inFlight.current.delete(branch.id);
    setNotice(noticeOf(outcome));
    // 받은 뒤 다시 읽는다 — 실패면 보이는 값을 걷어 서버 값으로 되돌린다.
    if (outcome.kind !== 'ok')
      setToggling((before) => {
        const out = new Map(before);
        out.delete(branch.id);
        return out;
      });
    list.reload();
  };
  // 다시 읽은 값이 오면 끝난 요청의 보이는 값만 걷는다(걸려 있는 줄은 남김).
  useEffect(() => {
    if (status.state !== 'ready') return;
    setToggling((before) => {
      const out = new Map(
        [...before].filter(([id]) => inFlight.current.has(id)),
      );
      return out.size === before.size ? before : out;
    });
  }, [status]);

  const body = (content: ReactNode) => (
    <tr>
      <td colSpan={COLUMN_COUNT} className="p-0">
        {content}
      </td>
    </tr>
  );

  if (status.state === 'refused')
    return (
      <div data-screen="ghg-organization" className="flex flex-col gap-6">
        <PageTitle title={words.title} />
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

  const pages = status.state === 'ready' ? status.value.totalPages : 1;

  return (
    <div data-screen="ghg-organization" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        headingRef={retryFocus.doneRef}
        actions={
          <Button variant="solidGrey" shape="round" size="md" onClick={onNew}>
            <PlusIcon aria-hidden />
            {words.add}
          </Button>
        }
      />
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SearchField
            aria-label={words.searchLabel}
            placeholder={words.searchPlaceholder}
            value={query}
            maxLength={200}
            onChange={(event) => setQuery(event.target.value)}
            className="w-52"
          />
          <div className="flex flex-wrap items-center gap-2">
            <p
              role="alert"
              data-testid="organization-notice"
              className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
            >
              {notice && (
                <>
                  <CircleWarningIcon aria-hidden />
                  {typeof notice === 'object' ?
                    companyText[notice.company]
                  : words[notice]}
                </>
              )}
            </p>
            <GatedButton off={none} onPress={() => setInventory(false)}>
              {words.disableSelected}
            </GatedButton>
            <GatedButton off={none} onPress={() => setInventory(true)}>
              {words.enableSelected}
            </GatedButton>
            <GatedButton
              off={none}
              onPress={(event) => setConfirm(event.currentTarget)}
            >
              {words.deleteSelected}
            </GatedButton>
          </div>
        </div>
        <span className="sr-only" role="status">
          {loading ? GHG_TEXT.common.loading : null}
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
                    size="lg"
                    className="align-middle"
                    aria-label={words.selectAll}
                    checked={
                      allChosen ? true
                      : chosen.length > 0 ?
                        'indeterminate'
                      : false
                    }
                    disabled={selectable.length === 0}
                    onCheckedChange={(checked) => toggleAll(checked === true)}
                  />
                </th>
                <th scope="col" className={headClass}>
                  {words.columns.name}
                </th>
                <th scope="col" className={headClass}>
                  {words.columns.inventory}
                </th>
                <th scope="col" className={headClass}>
                  <span className="sr-only">{words.openColumn}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {status.state === 'loading' ?
                <SkeletonRows columns={SKELETON_COLUMNS} />
              : status.state === 'failed' ?
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
                      {words.loadFailed}
                    </PageInfo>
                    <Button
                      ref={retryFocus.actionRef}
                      variant="solidBlack"
                      shape="round"
                      size="md"
                      onClick={retryFocus.arm(list.retry)}
                    >
                      {GHG_TEXT.common.retry}
                    </Button>
                  </div>,
                )
              : shown.length === 0 ?
                // GX2 M-8: 「검색 결과가 없어요」는 검색 중(보낸 검색어 있음)일 때만. 검색 아닐 때 0 → 다음 할 일.
                body(
                  sentQuery.trim() !== '' ?
                    <Empty title={words.emptySearch} />
                  : <Empty
                      title={words.empty}
                      description={words.emptyGuide}
                    />,
                )
              : shown.map((branch) => {
                  const pending = toggling.has(branch.id);
                  const enabled =
                    toggling.get(branch.id) ?? branch.inventoryEnabled;
                  return (
                    <tr
                      key={branch.id}
                      data-branch-id={branch.id}
                      data-headquarters={branch.isHeadquarters || undefined}
                      aria-label={branch.name}
                      className={cn(CLICKABLE_ROW)}
                      // 고르기·토글·> 는 제 일을 한다(공용 isFromControl 이 거름 — 행 누름으로 번지지 않게).
                      {...clickableRowProps(branch.id, onOpen)}
                    >
                      <td className={cellClass}>
                        <Checkbox
                          size="lg"
                          className="align-middle"
                          aria-label={words.selectRow(branch.name)}
                          checked={selected.has(branch.id)}
                          disabled={!isSelectable(branch)}
                          onCheckedChange={(checked) =>
                            toggle(branch.id, checked === true)
                          }
                        />
                      </td>
                      <td
                        className={cn(
                          cellClass,
                          'whitespace-normal break-all text-text-primary',
                        )}
                      >
                        {branch.name}
                      </td>
                      <td className={cellClass}>
                        <Switch
                          aria-label={words.toggleRow(branch.name)}
                          checked={enabled}
                          disabled={!canToggleInventory(branch) || pending}
                          onCheckedChange={() => void toggleRow(branch)}
                        />
                      </td>
                      <td className={cn(cellClass, 'text-center')}>
                        <button
                          type="button"
                          aria-label={words.openRow(branch.name)}
                          className="inline-flex size-8 items-center justify-center rounded-control border-0 bg-transparent p-0 text-text-tertiary hover:bg-background-overlay-subtle focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-secondary [&_svg]:size-4"
                          onClick={() => onOpen(branch.id)}
                        >
                          <ChevronRightIcon aria-hidden />
                        </button>
                      </td>
                    </tr>
                  );
                })
              }
            </tbody>
          </table>
        </div>
        {pages > 1 && (
          <nav
            aria-label={words.pagerLabel}
            className="flex items-center justify-center gap-3 text-style-pre-body-06 text-text-secondary"
          >
            <Button
              variant="outlineGrey"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              {words.prev}
            </Button>
            <span data-testid="page-of">{words.pageOf(page, pages)}</span>
            <Button
              variant="outlineGrey"
              size="sm"
              disabled={page >= pages}
              onClick={() => setPage(page + 1)}
            >
              {words.next}
            </Button>
          </nav>
        )}
      </Card>
      {confirm && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open && !busy) setConfirm(null);
          }}
        >
          <DialogContent
            size="sm"
            data-testid="delete-dialog"
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              confirm.focus();
            }}
          >
            <DialogTitle className="text-center text-style-pre-heading-02">
              {words.deleteConfirm}
            </DialogTitle>
            <DialogFooter>
              <Button
                variant="outlineBlack"
                shape="round"
                size="md"
                disabled={busy}
                onClick={() => setConfirm(null)}
              >
                {words.cancel}
              </Button>
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                loading={busy}
                onClick={() => void remove()}
              >
                {words.confirmDelete}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
