// S3 사업장 블록 하나(밴드 W12-1b ① — 스펙 ① S3 7·9·10·12~15·19). 칸은 서버 slots(월 12·분기 4·연 1) — 웹이 주기를 셈하지 않는다.
//   상태는 부르는 쪽(EntryDetailDialog)이 쥐고, 여기는 그리고 콜백만 부른다. 저장은 모달 아래 [저장] 하나(밴드 W12-1c ① — sid:MARC-ENT-529).
//   입력 칸은 글자 그대로(Q5). N/A 행은 칸 비활성. 표는 가로 스크롤.
//   W12-1c ②(판 S12-03): 표 꼴 상수(entryTable.ts) · 열 폭 고정(#13 — 체크 52 · 시설명 140 · 단위 140 · 출처 200 · 칸 최소 140) ·
//   표 위 가로 막대(#12 Q5) · N/A·배출량·히스토리 오른쪽 고정(#12 Q4) · 입력 칸 36 꽉(#3) · 체크 20(#4) · 단추 꼴(#5·#6) ·
//   추정은 칸 표식 없이 상세 제목 줄 잠금 옆 단추 하나(S12-03, sid:MARC-ENT-644 — EntryDetailDialog) · 셈 문제 까닭 글만 줄바꿈(#22).
//   W12-2 ②: 머리 단추 차례 [입력 주기 변경] · [삭제] · [추가](판 S12-03_r1) — 잠김·저장 중 끔. 성공 한 줄은 블록 알림 줄(role=status, 공용 토스트 0).
import { useRef } from 'react';
import type { ReactNode, Ref } from 'react';

import { InfoIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';
import { cn } from '@marcspon/ui/lib/utils';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import {
  draftEdited,
  formatAmount,
  slotHeadOf,
} from '../../../entities/ghg/model/index.ts';
import type {
  EntryIndex,
  EntryRowDraft,
  EntrySite,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import { ScrollBar } from './ScrollBar.tsx';
import { CELL, HEAD_CELL, TABLE } from './entryTable.ts';

const words = GHG_TEXT.entry;

/** 열 폭(px, 판 `.f12b-w52`·`-g140`·`-g200`·`-w140`). 칸 열은 최소 140 — 남는 폭을 나눠 가진다. 배출량은 v196 이 웹 꼴대로 더한 열(ENT-531) — 판 `.f12b-w140` 140(감독 처분, 105 를 갈음). */
export const COLUMN = {
  select: 52,
  detail: 140,
  unit: 140,
  factor: 200,
  slotMin: 140,
  na: 140,
  emission: 140,
  history: 140,
} as const;

/** 오른쪽 고정 열 셋(#12 Q4 — N/A · 배출량 · 히스토리). 바탕을 깔고, N/A 왼쪽에 고정 경계선. */
const PIN = {
  na: 'sticky right-[280px] z-[1] border-l border-l-border-tertiary',
  emission: 'sticky right-[140px] z-[1]',
  history: 'sticky right-0 z-[1]',
} as const;
const PIN_BODY = 'bg-background-primary';

/** 블록 표의 최소 폭 — 칸 수에 따라(칸 열 최소 140). */
export const minTableWidth = (slots: number) =>
  COLUMN.select +
  COLUMN.detail +
  COLUMN.unit +
  COLUMN.factor +
  COLUMN.slotMin * slots +
  COLUMN.na +
  COLUMN.emission +
  COLUMN.history;

/** 칸 머리 글(월 「1월」·분기 「1분기」·연 「연간」). 꼴이 아니면 글자 그대로. */
export function slotText(slot: string): string {
  const head = slotHeadOf(slot);
  if (head === null) return slot;
  if (head.kind === 'month') return words.slotMonth(head.n);
  if (head.kind === 'quarter') return words.slotQuarter(head.n);
  return words.slotYear;
}

export interface EntryBlockState {
  drafts: EntryRowDraft[];
  checked: ReadonlySet<string>;
  /** 칸 오류: 「행 열쇠:칸」 또는 「행 열쇠:unit」 → 글. */
  errors: Readonly<Record<string, string>>;
  notice: string | null;
  /** 성공 한 줄(W12-2 S7 「입력 주기가 저장됐어요」 — role=status). 없으면 빈 줄. */
  done?: string | null;
}

export const cellKey = (rowKey: string, slot: string) => `${rowKey}:${slot}`;
/** 블록 제목의 등록 열쇠(칸 열쇠와 겹치지 않게 「site:」). */
export const siteKey = (siteId: string) => `site:${siteId}`;

export interface EntrySiteBlockProps {
  site: EntrySite;
  index: EntryIndex;
  block: EntryBlockState;
  /** 잠긴 판 — 입력·추가·삭제·N/A 비활성(보기만). */
  locked: boolean;
  /** 모달 [저장]이 응답을 기다리는 중 — 응답이 블록을 갈음하므로 그동안 입력을 막는다(검증 R2 를 모달 단위로). */
  busy: boolean;
  /** 칸·단위 요소를 등록(첫 오류 칸 초점). 블록 제목은 `siteKey(siteId)` 로(실패 블록 초점). */
  register(key: string, element: HTMLElement | null): void;
  onChange(key: string, change: (draft: EntryRowDraft) => EntryRowDraft): void;
  onCheck(key: string, on: boolean): void;
  onRemove(): void;
  onAdd(): void;
  removeRef?: Ref<HTMLButtonElement>;
  addRef?: Ref<HTMLButtonElement>;
  /** S8 계수 보기(row.factor ?? index.factor — 밴드 W12-1b ②). */
  onFactor(draft: EntryRowDraft): void;
  /**
   * S12-03 출처 칸 [수정] → S9 바로(Q7 — 운영 관리자만: 부르는 쪽이 pool 이 있을 때만 넘긴다). 저장된 행에만 그리고,
   * disabled(잠김·쓰는 중)거나 그 행을 고친 동안은 끈다. 닫히면 초점은 DialogContent 가 이 단추로 돌린다.
   */
  factorEdit?: {
    disabled: boolean;
    onEdit(draft: EntryRowDraft): void;
  } | null;
  /** S12 히스토리(새 행은 없음). */
  onHistory(draft: EntryRowDraft): void;
  /** S7 입력주기 바꿈 창을 연다(W12-2). */
  onPeriod(): void;
}

function emissionOf(draft: EntryRowDraft, decimals: number): ReactNode {
  if (draft.edited.na) return words.naValue;
  const problem = draft.before?.emissionProblem ?? null;
  if (problem !== null)
    return (
      <span
        className="flex flex-col items-end text-right"
        data-testid="entry-emission-problem"
      >
        <span>{words.noEmission}</span>
        <span className="whitespace-normal break-keep text-style-pre-caption-03 text-text-tertiary">
          {words.emissionProblem[problem] ?? ''}
        </span>
      </span>
    );
  return shownAmount(draft.before?.emission ?? null, decimals);
}

/** S12C1 9ddc00eb: 이 화면은 값 없음을 「-」 대신 빈칸으로(공용 formatAmount 는 S2 목록·카드가 같이 써 그대로). */
export const shownAmount = (text: string | null, decimals: number): string =>
  text === null ? '' : formatAmount(text, decimals);

/**
 * S12C1 768f5c80: 투입량 칸은 숫자만 — 친 글·붙여넣은 글에서 숫자와 첫 소수점 하나 밖(쉼표·글자·빈칸·부호)을 거른다.
 * 저장 값 꼴은 그대로(글자), 저장 때 checkAmount 는 안전망으로 남는다.
 */
export function amountTyped(text: string): string {
  const kept = text.replace(/[^0-9.]/g, '');
  const dot = kept.indexOf('.');
  return dot < 0 ? kept : (
      `${kept.slice(0, dot + 1)}${kept.slice(dot + 1).replace(/\./g, '')}`
    );
}

export function EntrySiteBlock({
  site,
  index,
  block,
  locked,
  busy,
  register,
  onChange,
  onCheck,
  onRemove,
  onAdd,
  removeRef,
  addRef,
  onFactor,
  factorEdit = null,
  onHistory,
  onPeriod,
}: EntrySiteBlockProps) {
  /** 잠긴 판 또는 저장 응답을 기다리는 중 — 응답이 블록을 갈음하므로 그동안 친 글이 사라지지 않게 막는다(검증 R2). */
  const frozen = locked || busy;
  const errorId = (key: string) => `entry-error-${key.replace(':', '-')}`;
  const scroller = useRef<HTMLDivElement>(null);
  return (
    <section
      data-testid={`entry-site-${site.siteId}`}
      className="flex flex-col gap-2"
    >
      <div className="flex flex-wrap items-center gap-2.5">
        <h4
          ref={(element) => register(siteKey(site.siteId), element)}
          tabIndex={-1}
          className="m-0 text-style-pre-body-02 text-text-primary outline-none"
        >
          {site.siteName}
        </h4>
        <p
          role="alert"
          data-testid={`entry-notice-${site.siteId}`}
          className="m-0 text-style-pre-caption-03 text-support-error-accent empty:hidden"
        >
          {block.notice}
        </p>
        <p
          role="status"
          data-testid={`entry-done-${site.siteId}`}
          className="m-0 text-style-pre-caption-03 text-support-success empty:hidden"
        >
          {block.done ?? null}
        </p>
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="solidGrey"
            size="sm"
            aria-label={words.periodChange.label(site.siteName)}
            data-testid={`entry-period-open-${site.siteId}`}
            disabled={frozen}
            onClick={onPeriod}
          >
            {words.periodChange.button}
          </Button>
          <Button
            ref={removeRef}
            variant="solidGrey"
            size="sm"
            disabled={frozen || block.checked.size === 0}
            onClick={onRemove}
          >
            {words.remove}
          </Button>
          <Button
            ref={addRef}
            variant="solidGrey"
            size="sm"
            disabled={frozen}
            onClick={onAdd}
          >
            {words.add}
          </Button>
        </div>
      </div>
      <div className="flex flex-col">
        <ScrollBar target={scroller} testId={`entry-bar-${site.siteId}`} />
        <div
          ref={scroller}
          className="overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          data-testid={`entry-scroll-${site.siteId}`}
        >
          <table
            className={cn(TABLE, 'w-full table-fixed')}
            style={{ minWidth: minTableWidth(site.slots.length) }}
          >
            <colgroup>
              <col style={{ width: COLUMN.select }} />
              <col style={{ width: COLUMN.detail }} />
              <col style={{ width: COLUMN.unit }} />
              <col style={{ width: COLUMN.factor }} />
              {site.slots.map((slot) => (
                <col key={slot} />
              ))}
              <col style={{ width: COLUMN.na }} />
              <col style={{ width: COLUMN.emission }} />
              <col style={{ width: COLUMN.history }} />
            </colgroup>
            <thead>
              <tr>
                <th scope="col" className={cn(HEAD_CELL, 'text-center')}>
                  <span className="sr-only">{words.head.select}</span>
                </th>
                <th scope="col" className={HEAD_CELL}>
                  {words.head.detail}
                </th>
                <th scope="col" className={HEAD_CELL}>
                  {words.head.unit}
                </th>
                <th scope="col" className={HEAD_CELL}>
                  {words.head.factor}
                </th>
                {site.slots.map((slot) => (
                  <th
                    key={slot}
                    scope="col"
                    data-slot={slot}
                    className={HEAD_CELL}
                  >
                    {slotText(slot)}
                  </th>
                ))}
                <th scope="col" className={cn(HEAD_CELL, PIN.na)}>
                  <span className="inline-flex items-center gap-1">
                    {words.head.na}
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            aria-label={words.naTip}
                            className="inline-flex border-0 bg-transparent p-0 text-text-tertiary [&_svg]:size-4"
                          >
                            <InfoIcon aria-hidden />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>{words.naTip}</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </span>
                </th>
                <th
                  scope="col"
                  className={cn(HEAD_CELL, PIN.emission, 'text-right')}
                >
                  {`${words.head.emission} (${index.unit})`}
                </th>
                <th
                  scope="col"
                  className={cn(HEAD_CELL, PIN.history, 'text-center')}
                >
                  {words.historyHead}
                </th>
              </tr>
            </thead>
            <tbody>
              {/* GX2 M-7: 줄이 없는 블록은 다음 할 일 한 줄(넓은 표라 글은 왼쪽에 붙여 가로로 밀어도 보이게). */}
              {block.drafts.length === 0 && (
                <tr data-testid={`entry-empty-${site.siteId}`}>
                  <td
                    colSpan={7 + site.slots.length}
                    className={cn(CELL, 'text-text-tertiary')}
                  >
                    <span className="sticky left-4">{words.rowsEmpty}</span>
                  </td>
                </tr>
              )}
              {block.drafts.map((draft) => {
                const { key, detailName, edited } = draft;
                const unitKey = cellKey(key, 'unit');
                const unitError = block.errors[unitKey];
                const factorName = (draft.before?.factor ?? index.factor).name;
                const options =
                  index.unitOptions.includes(edited.unit) ?
                    index.unitOptions
                  : [edited.unit, ...index.unitOptions];
                return (
                  <tr key={key} data-testid={`entry-row-${key}`}>
                    <td className={cn(CELL, 'text-center')}>
                      <Checkbox
                        size="lg"
                        className="align-middle"
                        aria-label={words.selectLabel(detailName)}
                        disabled={frozen}
                        checked={block.checked.has(key)}
                        onCheckedChange={(on) => onCheck(key, on === true)}
                      />
                    </td>
                    <td className={cn(CELL, 'truncate whitespace-nowrap')}>
                      {detailName}
                    </td>
                    <td className={CELL}>
                      <div
                        ref={(element) => register(unitKey, element)}
                        tabIndex={-1}
                        className="flex flex-col gap-1 outline-none"
                      >
                        <NativeSelect
                          className="w-full min-w-0"
                          aria-label={words.unitLabel(detailName)}
                          aria-invalid={unitError ? true : undefined}
                          disabled={frozen}
                          value={edited.unit}
                          onChange={(event) => {
                            const unit = event.target.value;
                            onChange(key, (old) => ({
                              ...old,
                              edited: { ...old.edited, unit },
                            }));
                          }}
                        >
                          {options.map((unit) => (
                            <option key={unit} value={unit}>
                              {unit}
                            </option>
                          ))}
                        </NativeSelect>
                        {unitError && (
                          <p className="m-0 text-style-pre-caption-03 text-support-error-accent">
                            {unitError}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className={cn(CELL, 'whitespace-nowrap')}>
                      <div className="flex min-w-0 items-center gap-2">
                        <button
                          type="button"
                          aria-label={words.factorLabel(detailName, factorName)}
                          title={factorName}
                          data-testid={`entry-factor-${key}`}
                          className="min-w-0 flex-1 cursor-pointer truncate border-0 bg-transparent p-0 text-left text-text-primary hover:underline focus-visible:outline-2"
                          onClick={() => onFactor(draft)}
                        >
                          {factorName}
                        </button>
                        {factorEdit && draft.before && (
                          <Button
                            variant="outlineGrey"
                            shape="round"
                            size="xs"
                            className="shrink-0 px-2"
                            aria-label={words.factorEdit.cellLabel(detailName)}
                            title={
                              draftEdited(draft) ?
                                words.factorEdit.dirty
                              : undefined
                            }
                            data-testid={`entry-factor-edit-${key}`}
                            disabled={factorEdit.disabled || draftEdited(draft)}
                            onClick={() => factorEdit.onEdit(draft)}
                          >
                            {words.factorEdit.cell}
                          </Button>
                        )}
                      </div>
                    </td>
                    {edited.values.map((value) => {
                      const at = cellKey(key, value.slot);
                      const error = block.errors[at];
                      const off = frozen || edited.na;
                      const slotName = slotText(value.slot);
                      return (
                        <td key={value.slot} className={CELL}>
                          <div className="flex items-center gap-2">
                            <input
                              ref={(element) => register(at, element)}
                              inputMode="decimal"
                              aria-label={words.amountLabel(
                                detailName,
                                slotName,
                              )}
                              aria-invalid={error ? true : undefined}
                              aria-describedby={error ? errorId(at) : undefined}
                              data-testid={`entry-amount-${at}`}
                              disabled={off}
                              value={value.amount ?? ''}
                              className="box-border h-9 w-full min-w-0 flex-1 rounded-component border border-solid border-border-tertiary bg-background-primary px-3 text-right text-style-pre-body-06 text-text-secondary tabular-nums disabled:bg-background-secondary aria-[invalid=true]:border-support-error-accent"
                              onChange={(event) => {
                                const text = amountTyped(event.target.value);
                                onChange(key, (old) => ({
                                  ...old,
                                  edited: {
                                    ...old.edited,
                                    values: old.edited.values.map((slot) =>
                                      slot.slot === value.slot ?
                                        {
                                          ...slot,
                                          amount: text === '' ? null : text,
                                        }
                                      : slot,
                                    ),
                                  },
                                }));
                              }}
                            />
                          </div>
                          {error && (
                            <p
                              id={errorId(at)}
                              className="m-0 mt-1 text-style-pre-caption-03 text-support-error-accent"
                            >
                              {error}
                            </p>
                          )}
                        </td>
                      );
                    })}
                    <td className={cn(CELL, PIN.na, PIN_BODY, 'text-center')}>
                      <Checkbox
                        size="lg"
                        className="align-middle"
                        aria-label={words.naLabel(detailName)}
                        disabled={frozen}
                        checked={edited.na}
                        onCheckedChange={(on) =>
                          onChange(key, (old) => ({
                            ...old,
                            edited: { ...old.edited, na: on === true },
                          }))
                        }
                      />
                    </td>
                    <td
                      data-testid={`entry-emission-${key}`}
                      className={cn(
                        CELL,
                        PIN.emission,
                        PIN_BODY,
                        'whitespace-nowrap text-right tabular-nums',
                      )}
                    >
                      {emissionOf(draft, index.decimals)}
                    </td>
                    <td
                      className={cn(CELL, PIN.history, PIN_BODY, 'text-center')}
                    >
                      {draft.before !== null && (
                        <Button
                          variant="outlineGrey"
                          shape="round"
                          size="sm"
                          aria-label={words.historyLabel(detailName)}
                          data-testid={`entry-history-${key}`}
                          onClick={() => onHistory(draft)}
                        >
                          {words.historyOpen}
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
