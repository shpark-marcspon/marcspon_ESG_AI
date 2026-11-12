// S18 설정 > 선택항목 > 자산/시설명 및 코드(밴드 W12-0a ③ — 스펙 ② S18, 꼴은 AD-01 pages/admin-accounts 의 표·고르기·확인 창). 운영 관리자만
//   (/admin 가드 — 모든 고객사 공통 목록 하나, sid:MARC-ENT-469 3). 라우터를 모른다: 실어댑터(port)를 props 로 받는다.
//   - 제목 「선택항목」 · 항목 고르기(「자산/시설명 및 코드」 하나 — 다른 선택항목 여섯은 범위 밖) · 표(체크박스·이름·「수정」, 줄 = [수정](sid:MARC-ENT-599), ≡ 손잡이 0 —
//     순서는 서버가 정한 만든 차례) · 「항목 삭제」(고른 것 0 이면 꺼짐 → 확인 창) · 「항목 추가」.
//   - 모달(추가·수정 같은 꼴): 「자산/시설명 및 코드*」 글 하나 · [저장]은 빈 칸이면 흐림(스펙 [확인] — Policy 「늘 켬」과 다름) ·
//     겹침 → 「이미 있는 항목이에요」(웹 검사 + 서버 422 fields.name 같은 자리). 수정은 이름만 — code 는 그대로(화면에 코드 글자 0).
//   - 상태: 빈 목록 「등록된 항목이 없어요」 + [항목 추가] · 읽기 실패 한 줄 + [다시 시도] · 지움 409 IN_USE → 「사용 중인 항목은 삭제할 수 없어요」
//     (뒤 밴드 S12a 가 더함 — 목록 그대로) · NOT_FOUND → 한 줄 + 다시 읽음. 서버 message 는 그리지 않는다.
import { cloneElement, useState } from 'react';
import type { KeyboardEvent, MouseEvent, ReactNode } from 'react';

import {
  CircleWarningIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  FacilityCodeAdminPort,
  WriteOutcome,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { useAdminFacilityCodes } from '../../../entities/ghg/hooks/index.ts';
import type { AdminFacilityCode } from '../../../entities/ghg/model/index.ts';
import { Button, buttonVariants } from '../../../shared/ui/button/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import {
  ROW_FOCUS,
  ROW_HOVER,
  isActivationKey,
  isFromControl,
} from '../../../shared/ui/data-table/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  SkeletonRows,
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import type { SkeletonColumn } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { CodeDialog } from './CodeDialog.tsx';

const words = GHG_TEXT.facilityCodes;

export interface FacilityCodesScreenProps {
  port: FacilityCodeAdminPort;
}

/** 누를 수 있는 줄(DataTable 과 같은 셋 — 커서·hover·초점). 누를 수 없는 줄은 셋 다 없다(결정 599 규칙 2). */
const CLICKABLE_ROW = ['cursor-pointer', ROW_HOVER, ROW_FOCUS];

/**
 * 누를 수 있는 줄 — 공용 clickableRowProps(shared/ui/data-table hooks/useDataTable.ts)와 같은 갈래(칸 안 컨트롤은 무시,
 * Enter·Space 는 줄 자신에 초점이 있을 때만, preventDefault). 창을 닫으면 초점을 돌릴 자리로 그 줄(<tr>)을 넘긴다.
 */
function rowOpener(open: (from: HTMLElement) => void) {
  return {
    tabIndex: 0 as const,
    onClick: (event: MouseEvent<HTMLElement>) => {
      if (isFromControl(event.target, event.currentTarget)) return;
      open(event.currentTarget);
    },
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      if (!isActivationKey(event.key)) return;
      if (event.target !== event.currentTarget) return;
      event.preventDefault();
      open(event.currentTarget);
    },
  };
}

/** 열린 모달과 연 단추(닫히면 그리로 초점). */
type Open =
  | { kind: 'add'; from: HTMLElement }
  | { kind: 'edit'; code: AdminFacilityCode; from: HTMLElement }
  | { kind: 'delete'; from: HTMLElement }
  | null;
/** 단추 줄 옆 한 줄. */
type Notice = 'inUse' | 'notFound' | 'writeFailed' | null;

const headClass =
  'h-10 whitespace-nowrap border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-left text-style-pre-body-05 text-text-tertiary';
const cellClass =
  'h-14 whitespace-nowrap border-0 border-b border-solid border-border-tertiary px-4 text-left';
const COLUMN_COUNT = 3;
const SKELETON_COLUMNS: readonly SkeletonColumn[] = [
  { width: 16 },
  {},
  { width: [48, 64], align: 'center' },
];
const COLUMN_WIDTHS: readonly (number | null)[] = [48, null, 96];

/** 쓰기 결과 → 한 줄(성공이면 null). */
export function noticeOf(outcome: WriteOutcome<unknown>): Notice {
  if (outcome.kind === 'ok') return null;
  if (outcome.kind === 'rejected' && outcome.code === 'IN_USE') return 'inUse';
  if (outcome.kind === 'rejected' && outcome.code === 'NOT_FOUND')
    return 'notFound';
  return 'writeFailed';
}

export function FacilityCodesScreen({ port }: FacilityCodesScreenProps) {
  const [page, setPage] = useState(1);
  const list = useAdminFacilityCodes(port, page);
  const status = list.status;
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [open, setOpen] = useState<Open>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  const loading = useDelayed(status.state === 'loading');
  const retryFocus = useRetryFocus<HTMLButtonElement>(
    status.state === 'loading' ? 'loading'
    : status.state === 'ready' ? 'ready'
    : 'failed',
  );

  const shown = status.state === 'ready' ? status.value.results : [];
  const pages = status.state === 'ready' ? status.value.totalPages : 1;
  const chosen = shown.filter((code) => selected.has(code.id));
  const none = chosen.length === 0 || busy;
  const allChosen =
    shown.length > 0 && shown.every((code) => selected.has(code.id));

  const toggle = (id: string, on: boolean) =>
    setSelected((before) => {
      const next = new Set(before);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  const afterWrite = (outcome: WriteOutcome<unknown>) => {
    setNotice(noticeOf(outcome));
    if (outcome.kind === 'ok') setSelected(new Set());
    list.reload();
  };
  const remove = async () => {
    setBusy(true);
    setNotice(null);
    const outcome = await port.remove(chosen.map((code) => code.id));
    setBusy(false);
    setOpen(null);
    afterWrite(outcome);
  };

  const body = (content: ReactNode) => (
    <tr>
      <td colSpan={COLUMN_COUNT} className="p-0">
        {content}
      </td>
    </tr>
  );
  const addButton = (
    <Button
      variant="solidGrey"
      shape="round"
      size="md"
      onClick={(event) => setOpen({ kind: 'add', from: event.currentTarget })}
    >
      <PlusIcon aria-hidden />
      {words.add}
    </Button>
  );

  return (
    <div data-screen="admin-options" className="flex flex-col gap-6">
      <div className="flex justify-end">
        {cloneElement(addButton, { ref: retryFocus.doneRef })}
      </div>
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <NativeSelect
            aria-label={words.itemLabel}
            defaultValue="facility-codes"
          >
            <option value="facility-codes">{words.item}</option>
          </NativeSelect>
          <div className="flex flex-wrap items-center gap-2">
            <p
              role="alert"
              data-testid="options-notice"
              className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
            >
              {notice && (
                <>
                  <CircleWarningIcon aria-hidden />
                  {words[notice]}
                </>
              )}
            </p>
            <button
              type="button"
              aria-disabled={none || undefined}
              className={cn(
                buttonVariants({ variant: 'outlineGrey', size: 'sm' }),
                none && 'cursor-not-allowed opacity-40',
              )}
              onClick={(event) => {
                if (!none)
                  setOpen({ kind: 'delete', from: event.currentTarget });
              }}
            >
              {words.deleteSelected}
            </button>
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
                    aria-label={words.selectAll}
                    checked={
                      allChosen ? true
                      : chosen.length > 0 ?
                        'indeterminate'
                      : false
                    }
                    disabled={shown.length === 0}
                    onCheckedChange={(checked) =>
                      setSelected(
                        checked === true ?
                          new Set(shown.map((code) => code.id))
                        : new Set(),
                      )
                    }
                  />
                </th>
                <th scope="col" className={headClass}>
                  {words.column}
                </th>
                <th scope="col" className={cn(headClass, 'text-center')}>
                  <span className="sr-only">{words.edit}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {status.state === 'loading' ?
                <SkeletonRows columns={SKELETON_COLUMNS} />
              : status.state !== 'ready' ?
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
                body(<Empty title={words.empty} action={addButton} />)
              : shown.map((code) => (
                  <tr
                    key={code.id}
                    data-code-id={code.id}
                    aria-label={code.name}
                    className={cn(CLICKABLE_ROW)}
                    {...rowOpener((from) =>
                      setOpen({ kind: 'edit', code, from }),
                    )}
                  >
                    <td className={cellClass}>
                      <Checkbox
                        aria-label={words.selectRow(code.name)}
                        checked={selected.has(code.id)}
                        onCheckedChange={(checked) =>
                          toggle(code.id, checked === true)
                        }
                      />
                    </td>
                    <td
                      className={cn(
                        cellClass,
                        'whitespace-normal break-all text-text-primary',
                      )}
                    >
                      {code.name}
                    </td>
                    <td className={cn(cellClass, 'text-center')}>
                      <Button
                        variant="outlineGrey"
                        shape="round"
                        size="sm"
                        aria-label={`${code.name} ${words.edit}`}
                        onClick={(event) =>
                          setOpen({
                            kind: 'edit',
                            code,
                            from: event.currentTarget,
                          })
                        }
                      >
                        {words.edit}
                      </Button>
                    </td>
                  </tr>
                ))
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
      {(open?.kind === 'add' || open?.kind === 'edit') && (
        <CodeDialog
          port={port}
          existing={shown}
          editing={open.kind === 'edit' ? open.code : null}
          returnFocus={open.from}
          onDone={(outcome) => {
            setOpen(null);
            afterWrite(outcome);
          }}
          onClose={() => setOpen(null)}
        />
      )}
      {open?.kind === 'delete' && (
        <Dialog
          open
          onOpenChange={(next) => {
            if (!next && !busy) setOpen(null);
          }}
        >
          <DialogContent
            size="sm"
            data-testid="delete-dialog"
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              open.from.focus();
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
                onClick={() => setOpen(null)}
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
