// S12 수정 히스토리(밴드 W12-1b ② — 스펙 ① S12, 28556:24923). 행마다, 화면 아래에서 올라오는 판.
//   W12-2 ②: 열 차례 수정일 · 수정자 · 히스토리 복구 · 단위 · 변경 내용(스펙 :144). [복구] 켬 = restorable && (kind ≠ factor || 운영 관리자 —
//   W12-3 Q8) && 그 행 고침 없음(Q5 — 판 위 한 줄). value·period 줄은 확인 창(value 줄 「이 기록으로 되돌릴까요?」 · period 줄은 S7 안내 글 + 고친 블록이면
//   Q4 한 줄) → POST restore {} · factor 줄은 S11 사유 창(EntryReasonDialog — W12-3 ③) → POST restore {reason}. → onRestored(상세 갈음은 부르는 쪽) ·
//   1쪽 다시 읽음. 거절은 서버 차례대로 한 줄(Q6) — 422 fields.reason 만 사유 창 칸에 남긴다. 사유 있는 줄은 「변경 내용」 칸 오른쪽 끝에 「수정 사유」
//   단추(복구와 같은 outlineGrey round sm — 모서리 full·좌우 10, Figma 29429:28326 「같은 꼴 이웃」 — 복구도 W12-4 ③ 부터 round) → 보기 창(EntryReasonViewDialog, 사유 전체). 줄 안 사유 글·툴팁은 0(W12-4 ③, e6 이 거둠 — sid:MARC-ISSUE-571).
//   종류 글은 changeParts 한 곳(changeText 는 그 조각을 이은 글 — 글자 차례 1b 그대로). 모르는 종류는 판 실패가 아니라 값 없이 한 줄. 404 → 한 줄 + 상세 다시 읽음(onGone).
//   W12-1c #16(Figma 28556:24923): 화면 가득한 폭(상세 모달과 같은 calc(100vw-64px), 아래에서 올라옴 그대로) · 머리 회색 가운데 ·
//   줄 앞 점(전체 맨 위 = 1쪽 첫 줄만 주황 · 나머지 회색 — W12-1d Q13, 서버가 최신 먼저) · 수정자 주황 · 변경 내용: 칸 이름 회색 + 앞 값 → 뒤 값 주황 굵게 · 화살표 주황 · 「N/A」 주황 굵게.
import { useEffect, useRef, useState } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import type {
  EntryWrite,
  GhgEntryPort,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { entryAtText } from '../../../entities/ghg/model/index.ts';
import type {
  EntryHistory,
  EntryHistoryPage,
  EntryIndex,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogCloseIconButton,
  DialogContent,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
import { ConfirmModal } from './ConfirmModal.tsx';
import { EntryReasonDialog } from './EntryReasonDialog.tsx';
import { EntryReasonViewDialog } from './EntryReasonViewDialog.tsx';
import { slotText } from './EntrySiteBlock.tsx';
import { CELL, HEAD_CELL, TABLE } from './entryTable.ts';

const words = GHG_TEXT.entry;
const text = words.history;
const HEAD = cn(HEAD_CELL, 'text-center');
const ARROW = ' → ';

const shown = (value: string | null) => value ?? text.emptyValue;
const periodWord = (value: string | null) =>
  value === null ? text.emptyValue : (words.period[value] ?? value);

/** 변경 내용 조각 — 칸 이름(label) · 앞 값(before) · 화살표(arrow) · 뒤 값(after) · 강조 글(mark, 「N/A」) · 그냥 글(text). */
export interface ChangePart {
  kind: 'label' | 'before' | 'arrow' | 'after' | 'mark' | 'text';
  text: string;
}

/** 「<머리 글>앞 → 뒤」 꼴의 글을 조각으로 — 머리 글은 글 함수가 낸 것을 그대로 잘라 쓴다(글자 차례 1b 와 같게). */
function framed(
  whole: string,
  before: string,
  after: string,
  head: ChangePart['kind'] = 'text',
): ChangePart[] {
  const tail = `${before}${ARROW}${after}`;
  const lead = whole.endsWith(tail) ? whole.slice(0, -tail.length) : null;
  if (lead === null) return [{ kind: 'text', text: whole }];
  return [
    ...(lead === '' ? [] : [{ kind: head, text: lead }]),
    { kind: 'before', text: before },
    { kind: 'arrow', text: ARROW },
    { kind: 'after', text: after },
  ];
}

/** 「N/A …」 글 — 앞의 「N/A」만 강조. */
function marked(whole: string): ChangePart[] {
  const na = words.naValue;
  return whole.startsWith(na) ?
      [
        { kind: 'mark', text: na },
        { kind: 'text', text: whole.slice(na.length) },
      ]
    : [{ kind: 'text', text: whole }];
}

/** 변경 내용 조각(before → after 차례). */
export function changeParts(line: EntryHistory): ChangePart[] {
  switch (line.kind) {
    case 'value': {
      const before = shown(line.before);
      const after = shown(line.after);
      return line.slot === null ?
          framed(text.value(before, after), before, after)
        : framed(
            text.slotValue(slotText(line.slot), before, after),
            before,
            after,
            'label',
          );
    }
    case 'na_on':
      return marked(text.naOn);
    case 'na_off':
      return marked(text.naOff);
    case 'factor': {
      const before = line.beforeFactor?.name ?? text.emptyValue;
      const after = line.afterFactor?.name ?? text.emptyValue;
      return framed(text.factor(before, after), before, after);
    }
    case 'unit': {
      const before = shown(line.before);
      const after = shown(line.after);
      return framed(text.unitChange(before, after), before, after);
    }
    case 'period': {
      const before = periodWord(line.before);
      const after = periodWord(line.after);
      return framed(text.periodChange(before, after), before, after);
    }
    default:
      return [{ kind: 'text', text: text.unknown }];
  }
}

/** 변경 내용 한 줄(조각을 이은 글). */
export function changeText(line: EntryHistory): string {
  return changeParts(line)
    .map((part) => part.text)
    .join('');
}

const PART_CLASS: Record<ChangePart['kind'], string> = {
  label: 'text-text-tertiary',
  before: '',
  arrow: 'text-text-brand',
  after: 'text-style-pre-body-04 text-text-brand',
  mark: 'text-style-pre-body-04 text-text-brand',
  text: '',
};

type Loaded =
  | { state: 'loading' }
  | { state: 'ready'; page: EntryHistoryPage }
  | { state: 'problem'; message: string };

/** 복구 쓰기 뒤 한 줄(성공 status · 거절 alert). */
type RestoreNote = { tone: 'done' | 'problem'; text: string } | null;

/** [복구] 켬(W12-2 Q5 · W12-3 Q8): 서버 restorable · 계수 줄은 운영 관리자만 · 그 행 고침 없음. */
export const canRestore = (
  line: EntryHistory,
  rowDirty: boolean,
  operator: boolean,
) => line.restorable && (line.kind !== 'factor' || operator) && !rowDirty;

export function EntryHistoryDialog({
  port,
  year,
  nodeId,
  rowId,
  operator,
  rowDirty = false,
  blockDirty = false,
  onRestored = () => {},
  onGone,
  onClose,
}: {
  port: GhgEntryPort;
  year: number;
  nodeId: string;
  rowId: string;
  operator: boolean;
  /** 그 행에 저장 안 한 고침 — [복구] 끔 + 판 위 한 줄(Q5). */
  rowDirty?: boolean;
  /** 그 행의 블록에 저장 안 한 고침 — period 줄 확인 창에 Q4 한 줄. */
  blockDirty?: boolean;
  /** 복구 성공 — 응답 상세(부르는 쪽이 갈음: value 는 고침 지킴, period 는 그 블록 응답 그대로). */
  onRestored?(index: EntryIndex, line: EntryHistory): void;
  /** 행이 없어짐(404)·잠김(409) — 상세를 다시 읽는다. */
  onGone(): void;
  onClose(): void;
}) {
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });
  const [confirming, setConfirming] = useState<EntryHistory | null>(null);
  /** factor 줄 [복구]의 사유 창(W12-3 ③) · 서버가 사유를 거절한 글. */
  const [asking, setAsking] = useState<EntryHistory | null>(null);
  /** 보는 줄 사유와 연 단추(닫히면 초점을 돌린다 — W12-4 ③). */
  const [viewing, setViewing] = useState<{
    reason: string;
    opener: HTMLElement;
  } | null>(null);
  const [reasonProblem, setReasonProblem] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [note, setNote] = useState<RestoreNote>(null);
  const asked = useRef(0);
  const companyText = operator ? GHG_TEXT.companyOperator : GHG_TEXT.company;

  /** 1쪽부터 다시 읽는다(복구가 맨 위에 새 줄을 쌓는다). */
  const again = () => {
    setPage(1);
    setReload((n) => n + 1);
  };

  /** 복구 거절 → 한 줄(Q6 — 서버 차례: 404 · 422 historyId · 403 · 409 LOCKED · 409 RESTORE_STALE · 그 밖). */
  const refusalOf = (out: Exclude<EntryWrite<EntryIndex>, { kind: 'ok' }>) => {
    if (out.kind === 'notFound') {
      onGone();
      return text.gone;
    }
    if (out.kind === 'locked') {
      onGone();
      again();
      return words.locked;
    }
    if (out.kind === 'forbidden') return text.restoreForbidden;
    if (out.kind === 'refused') return companyText[out.company];
    if (out.kind === 'rejected' && out.code === 'RESTORE_STALE') {
      again();
      return text.restoreStale;
    }
    if (
      out.kind === 'rejected' &&
      out.code === 'VALIDATION_ERROR' &&
      'historyId' in out.fields
    ) {
      again();
      return text.restoreRejected;
    }
    return text.restoreFailed;
  };

  /** reason 은 factor 줄만(사유 창에서 지운 글) — value·period 줄은 본문 {}(W12-3 Q8). */
  const restore = async (line: EntryHistory, reason?: string) => {
    setConfirming(null);
    setRestoring(true);
    setNote(null);
    setReasonProblem(null);
    const out = await (reason === undefined ?
      port.restore(year, nodeId, rowId, line.historyId)
    : port.restore(year, nodeId, rowId, line.historyId, reason));
    setRestoring(false);
    if (out.kind === 'ok') {
      setAsking(null);
      onRestored(out.value, line);
      setNote({ tone: 'done', text: text.restored });
      again();
      return;
    }
    if (
      reason !== undefined &&
      out.kind === 'rejected' &&
      out.code === 'VALIDATION_ERROR' &&
      'reason' in out.fields
    ) {
      setReasonProblem(words.reason.rejected);
      return;
    }
    setAsking(null);
    setNote({ tone: 'problem', text: refusalOf(out) });
  };

  useEffect(() => {
    const ticket = ++asked.current;
    void port.history(year, nodeId, rowId, page).then((out) => {
      if (ticket !== asked.current) return;
      if (out.kind === 'ok') setLoaded({ state: 'ready', page: out.value });
      else if (out.kind === 'notFound') {
        setLoaded({ state: 'problem', message: text.gone });
        onGone();
      } else if (out.kind === 'refused')
        setLoaded({ state: 'problem', message: companyText[out.company] });
      else setLoaded({ state: 'problem', message: text.loadFailed });
    });
    // 쪽이 바뀔 때·복구 뒤(reload)만 읽는다(나머지는 모달이 떠 있는 동안 그대로).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, reload]);

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="lg"
        data-testid="entry-history"
        className="bottom-0 top-auto w-[calc(100vw-64px)] rounded-b-none [translate:-50%_0]"
      >
        <DialogCloseIconButton aria-label={words.close} />
        <DialogTitle className="text-style-pre-heading-02">
          {text.title}
        </DialogTitle>
        {loaded.state === 'loading' && (
          <LoadSkeleton label={GHG_TEXT.common.loading} />
        )}
        {loaded.state === 'problem' && (
          <p
            role="alert"
            data-testid="entry-history-problem"
            className="m-0 text-style-pre-caption-03 text-support-error-accent"
          >
            {loaded.message}
          </p>
        )}
        {rowDirty && (
          <p
            data-testid="entry-history-dirty"
            className="m-0 text-style-pre-caption-03 text-text-tertiary"
          >
            {text.restoreDirty}
          </p>
        )}
        {note && (
          <p
            role={note.tone === 'done' ? 'status' : 'alert'}
            data-testid="entry-history-note"
            className={cn(
              'm-0 text-style-pre-caption-03',
              note.tone === 'done' ?
                'text-support-success'
              : 'text-support-error-accent',
            )}
          >
            {note.text}
          </p>
        )}
        {loaded.state === 'ready' && (
          <>
            {loaded.page.results.length === 0 ?
              <p className="m-0 text-style-pre-body-06 text-text-tertiary">
                {text.empty}
              </p>
            : <table className={`${TABLE} w-full`}>
                <thead>
                  <tr>
                    <th scope="col" className={HEAD}>
                      {text.at}
                    </th>
                    <th scope="col" className={HEAD}>
                      {text.actor}
                    </th>
                    <th scope="col" className={HEAD}>
                      {text.restoreHead}
                    </th>
                    <th scope="col" className={HEAD}>
                      {text.unit}
                    </th>
                    <th scope="col" className={HEAD}>
                      {text.change}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {loaded.page.results.map((line, at) => (
                    <tr
                      key={line.historyId}
                      data-testid={`entry-history-${line.historyId}`}
                    >
                      <td className={cn(CELL, 'whitespace-nowrap text-center')}>
                        <span className="inline-flex items-center gap-2">
                          <span
                            aria-hidden
                            data-testid="entry-history-dot"
                            className={`size-1.5 shrink-0 rounded-full ${
                              loaded.page.page === 1 && at === 0 ?
                                'bg-text-brand'
                              : 'bg-text-quaternary'
                            }`}
                          />
                          {entryAtText(line.at)}
                        </span>
                      </td>
                      <td
                        className={cn(
                          CELL,
                          'whitespace-nowrap text-center text-text-brand',
                        )}
                      >
                        {line.actor.name ?? text.emptyValue}
                      </td>
                      <td className={cn(CELL, 'whitespace-nowrap text-center')}>
                        <Button
                          variant="outlineGrey"
                          shape="round"
                          size="sm"
                          aria-label={text.restoreLabel(entryAtText(line.at))}
                          data-testid={`entry-restore-${line.historyId}`}
                          disabled={
                            restoring || !canRestore(line, rowDirty, operator)
                          }
                          onClick={() =>
                            line.kind === 'factor' ?
                              setAsking(line)
                            : setConfirming(line)
                          }
                        >
                          {text.restore}
                        </Button>
                      </td>
                      <td className={cn(CELL, 'whitespace-nowrap text-center')}>
                        {line.unit}
                      </td>
                      <td className={CELL}>
                        <div className="flex items-start gap-4">
                          <span
                            className="block min-w-0 flex-1"
                            data-testid="entry-history-change"
                          >
                            {changeParts(line).map((part, i) => (
                              <span
                                key={i}
                                data-part={part.kind}
                                className={PART_CLASS[part.kind] || undefined}
                              >
                                {part.text}
                              </span>
                            ))}
                          </span>
                          {line.reason && (
                            <Button
                              variant="outlineGrey"
                              shape="round"
                              size="sm"
                              className="shrink-0"
                              data-testid={`entry-history-reason-${line.historyId}`}
                              onClick={(event) =>
                                setViewing({
                                  reason: line.reason!,
                                  opener: event.currentTarget,
                                })
                              }
                            >
                              {text.reasonOpen}
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
            {loaded.page.totalPages > 1 && (
              <div className="flex items-center justify-center gap-2.5">
                <Button
                  variant="outlineGrey"
                  size="sm"
                  disabled={!loaded.page.hasPrevious}
                  onClick={() => setPage(loaded.page.page - 1)}
                >
                  {text.prev}
                </Button>
                <span
                  data-testid="entry-history-page"
                  className="text-style-pre-caption-02 text-text-tertiary tabular-nums"
                >
                  {text.page(loaded.page.page, loaded.page.totalPages)}
                </span>
                <Button
                  variant="outlineGrey"
                  size="sm"
                  disabled={!loaded.page.hasNext}
                  onClick={() => setPage(loaded.page.page + 1)}
                >
                  {text.next}
                </Button>
              </div>
            )}
          </>
        )}
        {confirming && (
          <ConfirmModal
            title={
              confirming.kind === 'period' ?
                blockDirty ?
                  `${words.periodChange.notice} ${words.periodChange.dirty}`
                : words.periodChange.notice
              : text.restoreConfirm
            }
            cancel={words.cancel}
            confirm={text.restoreOk}
            returnFocus={() => null}
            testId="entry-restore-confirm"
            onClose={() => setConfirming(null)}
            onConfirm={() => void restore(confirming)}
          />
        )}
        {viewing && (
          <EntryReasonViewDialog
            reason={viewing.reason}
            returnFocus={() => viewing.opener}
            onClose={() => setViewing(null)}
          />
        )}
        {asking && (
          <EntryReasonDialog
            busy={restoring}
            problem={reasonProblem}
            testId="entry-restore-reason"
            onConfirm={(reason) => void restore(asking, reason)}
            onClose={() => {
              setAsking(null);
              setReasonProblem(null);
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
