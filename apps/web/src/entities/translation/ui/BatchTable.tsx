// 번역 목록의 묶음 표(밴드 TRW0b, 시안 TR-01·01a 확정 판 v136, 결정 sid:MARC-ENT-404). 모양 부품: props 만 받는다.
// - 한 줄 = [번역 시작] 한 번 = 묶음(같은 파일을 다시 번역하면 줄이 하나 더). 맨 <table> 에 DataTable 과 같은 클래스(ui/tableLook.ts, 밴드 TRP2 TC3).
// - 파트가 여럿이면 묶음 줄(파일명 앞 꺾쇠 단추 → 펼침, aria-expanded·aria-controls — TRP2 TE3) 아래 파트 줄(바탕 #F3F4F5). 파트가 하나면 펼치지 않고 그 파트를 묶음 줄에 바로.
// - 파트 줄 = 그 파트의 최신 회차. 앞 회차가 있으면 「회차 n」 단추로 펼침 → 앞 회차 줄(상태·시각만).
//   [이 파트만 다시]·[다시 실행]은 새 줄이 아니라 그 파트의 회차 하나 더(부품은 round 를 받기만).
// - 다음 할 일: 진행·대기 → [진행 보기], 완료·일부 쪽 → [결과 보기], 서버 오류·일부 쪽 → [이 파트만 다시](파트 하나면 [다시 실행]).
//   막은 파트(까닭 있음)는 다시 단추 0(결정 393). 콜백이 없거나 줄의 retryable 이 false 면 그 단추를 그리지 않는다(밴드 TRW1b — batchId 없는 옛 묶음).
// - 운영 관리자도 같은 단추(v136 TR-01a · sid:MARC-ENT-380) — 표는 사용자 종류를 모른다. 「작업 회사」는 화면 머리 meta 한 번(v142, 밴드 TRC1).
// 검색 칸·상태 탭·「내가 올린 것만」·[새 번역]은 화면 몫(TRW1).
// - 원본 PDF 로 시작한 줄(pdf — 묶음 inputKind, 밴드 TRW6 ④)은 파일명 앞 회색 「PDF」 배지(6c v174 TR-01). 워드 줄은 DOM 이 그대로.
// - loading(밴드 TRP5, sid:MARC-ENT-443 ②): 머리줄은 그대로, 몸은 첫 그림부터 자리 잡은 SkeletonRows(칸 = 머리 일곱, 막대는 300ms 뒤) — rows 는 보지 않는다.
//   loading 은 날 값(status.state === 'loading')이고 늦추기는 SkeletonRows 가 한다. 표의 aria-busy 도 여기서 단다.
import { Fragment, useId, useState } from 'react';
import type { ReactNode } from 'react';

import {
  ChevronDownIcon,
  ChevronRightIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { Button, IconButton } from '../../../shared/ui/button/index.ts';
import {
  ROW_FOCUS,
  ROW_HOVER,
  clickableRowProps,
} from '../../../shared/ui/data-table/index.ts';
import { SkeletonRows } from '../../../shared/ui/load-skeleton/index.ts';
import type { SkeletonColumn } from '../../../shared/ui/load-skeleton/index.ts';
import { TR_TEXT } from '../config/text.ts';
import { batchNext, failureKindOf, isActive } from '../model/index.ts';
import type { PartKey, RejectionKey, TabState } from '../model/index.ts';
import {
  PART_STATUS_LOOK,
  PartStatusText,
  StatusBadge,
} from './PartStatusText.tsx';
import { summaryItems } from './labels.ts';
import { TABLE_CLASS, TD_CLASS, TH_CLASS } from './tableLook.ts';

const words = TR_TEXT.list;
const cells = TR_TEXT.cells;
const names = TR_TEXT.parts.names;

export interface BatchPart {
  part: PartKey;
  /** 「4~41」. */
  range: string;
  /** 최신 회차(1부터). */
  round: number;
  /** 최신 회차 시작 시각(보이는 글). */
  started: string;
  state: TabState;
  reason?: RejectionKey;
  pages?: { done: number; total: number };
  /** 앞 회차(새것부터) — 상태와 시각만. */
  earlier: readonly { round: number; state: TabState; at: string }[];
}

export interface BatchRow {
  batchId: string;
  fileName: string;
  /** 올린 시각(보이는 글). */
  uploaded: string;
  style: string;
  uploader: string;
  lastStarted: string;
  parts: readonly BatchPart[];
  /** 다시 단추를 그릴 수 있는 줄인가(기본 참). */
  retryable?: boolean;
  /** 원본 PDF 로 시작한 줄(파일명 앞 「PDF」 배지). 워드 줄은 넘기지 않는다. */
  pdf?: boolean;
}

/** 펼친 파트 줄 칸 바탕(#F3F4F5 — 밴드 TRP2 TC5). */
const PART_CELL = 'bg-background-secondary';
/** 누를 수 있는 파트 줄의 칸. 칸이 secondary 라 hover·초점은 칸에서 tertiary 로(줄 바탕은 칸에 가려 안 보임 — 디자인 74 답, 밴드 TRW7 ③b). */
const PART_CELL_ACTIVE =
  'group-hover/part:bg-background-tertiary group-focus-visible/part:bg-background-tertiary';
/** 누를 수 있는 줄(DataTable 과 같은 셋 — 커서·hover·초점). 누를 수 없는 줄은 셋 다 없다(결정 599 규칙 2). */
const CLICKABLE_ROW = ['cursor-pointer', ROW_HOVER, ROW_FOCUS];

/** 파트의 보기 단추 글 — 진행·대기 → [진행 보기], 완료·일부 쪽 → [결과 보기], 그 밖 null(단추 없음). */
const viewOf = (part: BatchPart) =>
  isActive(part.state) ? words.viewProgress
  : part.state === 'done' || part.state === 'failed_partial' ? words.viewResult
  : null;

const HEADS = [
  'file',
  'part',
  'style',
  'uploader',
  'started',
  'state',
  'next',
] as const;

/** loading 때 칸마다 막대(HEADS 차례 — 파일 긴 글 · 파트·쪽 · 문체 · 담당자 · 시작 날짜 · 상태 · 다음 할 일). */
const SKELETON: readonly SkeletonColumn[] = [
  {},
  { width: [72, 88] },
  { width: [48, 64] },
  { width: [48, 64] },
  { width: 112 },
  { width: [48, 80] },
  { width: [72, 88] },
];

function Td({
  className,
  children,
}: {
  className?: string;
  children?: ReactNode;
}) {
  return <td className={cn(TD_CLASS, className)}>{children}</td>;
}

export interface BatchTableProps {
  rows: readonly BatchRow[];
  /** 처음 펼쳐 둘 묶음. */
  initialOpen?: readonly string[];
  /** 불러오는 중(날 값). 참이면 머리줄 + 스켈레톤 줄만. */
  loading?: boolean;
  onOpenBatch?(batchId: string): void;
  onOpenPart?(batchId: string, part: PartKey): void;
  onRetryPart?(batchId: string, part: PartKey): void;
}

export function BatchTable({
  rows,
  initialOpen = [],
  loading = false,
  onOpenBatch,
  onOpenPart,
  onRetryPart,
}: BatchTableProps) {
  const id = useId();
  const [open, setOpen] = useState<ReadonlySet<string>>(
    () => new Set(initialOpen),
  );
  const toggle = (key: string) =>
    setOpen((now) => {
      const next = new Set(now);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const partActions = (row: BatchRow, part: BatchPart) => {
    const kind = failureKindOf(part);
    const view = viewOf(part);
    const retry =
      (kind === 'server_error' || kind === 'partial') &&
      row.retryable !== false &&
      onRetryPart !== undefined;
    return (
      <div className="flex flex-wrap gap-2">
        {view !== null && onOpenPart !== undefined && (
          <Button
            variant="outlineGrey"
            shape="round"
            size="sm"
            onClick={() => onOpenPart(row.batchId, part.part)}
          >
            {view}
          </Button>
        )}
        {retry && (
          <Button
            variant="outlineBlack"
            shape="round"
            size="sm"
            onClick={() => onRetryPart(row.batchId, part.part)}
          >
            {row.parts.length === 1 ?
              TR_TEXT.failure.retrySingle
            : TR_TEXT.failure.retryPart}
          </Button>
        )}
      </div>
    );
  };

  /** 파트·쪽 칸(회차 펼침 단추 포함). */
  const partCell = (row: BatchRow, part: BatchPart) => {
    const roundsId = `${id}-${row.batchId}-${part.part}-rounds`;
    const key = `${row.batchId}/${part.part}`;
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span>{cells.partRange(names[part.part], part.range)}</span>
        {part.earlier.length > 0 ?
          // 회색 배지 꼴(500 12/20, 0 4, #6F7781/#E7E9EC — 밴드 TRP2 TC5). 단추·aria 그대로.
          <button
            type="button"
            aria-expanded={open.has(key)}
            aria-controls={roundsId}
            onClick={() => toggle(key)}
            className="h-5 cursor-pointer rounded-control border-0 bg-background-tertiary px-1 text-style-pre-caption-02 leading-5 text-text-tertiary"
          >
            {cells.round(part.round)}
          </button>
        : part.round > 1 && (
            <StatusBadge look="grey">{cells.round(part.round)}</StatusBadge>
          )
        }
      </div>
    );
  };

  /** 파트를 여는 줄(그 파트의 보기 단추가 그려질 때만 — 결정 599 규칙 1·2). 단추와 같은 곳을 연다. */
  const partRowProps = (row: BatchRow, part: BatchPart, partName?: string) => {
    const view = viewOf(part);
    if (view === null || onOpenPart === undefined) return undefined;
    return {
      ...clickableRowProps(part.part, (key: PartKey) =>
        onOpenPart(row.batchId, key),
      ),
      'aria-label': words.rowLabel(row.fileName, view, partName),
    };
  };

  const earlierRows = (row: BatchRow, part: BatchPart) => {
    const key = `${row.batchId}/${part.part}`;
    if (part.earlier.length === 0 || !open.has(key)) return null;
    return part.earlier.map((round, index) => (
      <tr
        key={`${key}-${round.round}`}
        id={
          index === 0 ? `${id}-${row.batchId}-${part.part}-rounds` : undefined
        }
        data-earlier={round.round}
      >
        <Td />
        <Td className="pl-6 text-text-tertiary">{cells.round(round.round)}</Td>
        <Td />
        <Td />
        <Td>{round.at}</Td>
        <Td>
          <PartStatusText state={round.state} />
        </Td>
        <Td />
      </tr>
    ));
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="w-full overflow-x-auto">
        <table className={TABLE_CLASS} aria-busy={loading || undefined}>
          <thead>
            <tr>
              {HEADS.map((head) => (
                <th key={head} scope="col" className={TH_CLASS}>
                  {words.columns[head]}
                </th>
              ))}
            </tr>
          </thead>
          {loading && (
            <tbody data-testid="batch-skeleton">
              <SkeletonRows columns={SKELETON} />
            </tbody>
          )}
          {(loading ? [] : rows).map((row) => {
            const single = row.parts.length === 1 ? row.parts[0]! : null;
            const partsId = `${id}-${row.batchId}-parts`;
            const expanded = single === null && open.has(row.batchId);
            const next = batchNext(row.parts);
            // 파트 여럿 → [진행/결과 보기]와 같은 onOpenBatch(감독 판단 a — 펼침은 꺾쇠로만), 파트 하나 → 그 파트의 보기 단추와 같은 곳.
            const batchClick =
              single !== null ? partRowProps(row, single)
              : onOpenBatch === undefined ? undefined
              : {
                  ...clickableRowProps(row.batchId, onOpenBatch),
                  'aria-label': words.rowLabel(
                    row.fileName,
                    next === 'progress' ? words.viewProgress : words.viewResult,
                  ),
                };
            return (
              <tbody key={row.batchId} data-batch={row.batchId}>
                <tr
                  data-row="batch"
                  {...batchClick}
                  className={cn(batchClick && CLICKABLE_ROW)}
                >
                  <Td>
                    {/* 파일명 앞 28 꺾쇠 단추(밴드 TRP2 TE3, 시안 TR-01 「파트 펼치기·접기」). 파트 하나면 같은 폭 빈 자리. 파일명은 맨 글(TC4). */}
                    <div className="flex items-start gap-2">
                      {single === null ?
                        <IconButton
                          aria-label={
                            expanded ? words.collapseParts : words.expandParts
                          }
                          aria-expanded={expanded}
                          aria-controls={partsId}
                          onClick={() => toggle(row.batchId)}
                          // 펼침 ∨ · 접힘 › , #6F7781(밴드 TRP3 ② TE3 — 시안 TR-01 e-icon-btn)
                          className="text-text-tertiary"
                        >
                          {expanded ?
                            <ChevronDownIcon aria-hidden />
                          : <ChevronRightIcon aria-hidden />}
                        </IconButton>
                      : <span aria-hidden className="size-7 shrink-0" />}
                      <div className="flex min-w-0 flex-col gap-0.5">
                        {row.pdf ?
                          <span className="flex items-center gap-1">
                            <span data-testid="batch-pdf-mark">
                              <StatusBadge look="grey">
                                {words.pdfMark}
                              </StatusBadge>
                            </span>
                            <span className="break-all text-style-pre-body-06 text-text-secondary">
                              {row.fileName}
                            </span>
                          </span>
                        : <span className="break-all text-style-pre-body-06 text-text-secondary">
                            {row.fileName}
                          </span>
                        }
                        <span className="text-style-pre-caption-03 text-text-tertiary">
                          {words.uploaded(row.uploaded)}
                        </span>
                      </div>
                    </div>
                  </Td>
                  <Td>
                    {single === null ?
                      words.partCount(row.parts.length)
                    : partCell(row, single)}
                  </Td>
                  <Td>{row.style}</Td>
                  <Td>{row.uploader}</Td>
                  <Td>{row.lastStarted}</Td>
                  <Td>
                    {single === null ?
                      <span
                        data-testid="batch-summary"
                        className="flex flex-wrap gap-1"
                      >
                        {summaryItems(row.parts).map((item) => (
                          <StatusBadge
                            key={item.state}
                            look={PART_STATUS_LOOK[item.state]}
                          >
                            {item.text}
                          </StatusBadge>
                        ))}
                      </span>
                    : <PartStatusText
                        state={single.state}
                        reason={single.reason}
                        pages={single.pages}
                      />
                    }
                  </Td>
                  <Td>
                    {single === null ?
                      onOpenBatch !== undefined && (
                        <Button
                          variant="outlineGrey"
                          shape="round"
                          size="sm"
                          onClick={() => onOpenBatch(row.batchId)}
                        >
                          {next === 'progress' ?
                            words.viewProgress
                          : words.viewResult}
                        </Button>
                      )
                    : partActions(row, single)}
                  </Td>
                </tr>
                {single !== null && earlierRows(row, single)}
                {expanded &&
                  row.parts.map((part, index) => {
                    const partClick = partRowProps(row, part, names[part.part]);
                    const cell = cn(PART_CELL, partClick && PART_CELL_ACTIVE);
                    return (
                      <Fragment key={part.part}>
                        <tr
                          data-row="part"
                          data-part={part.part}
                          id={index === 0 ? partsId : undefined}
                          {...partClick}
                          className={cn(
                            'group/part',
                            partClick && ['cursor-pointer', ROW_FOCUS],
                          )}
                        >
                          <Td className={cell} />
                          <Td className={cell}>{partCell(row, part)}</Td>
                          <Td className={cell}>{row.style}</Td>
                          <Td className={cell} />
                          <Td className={cell}>{part.started}</Td>
                          <Td className={cell}>
                            <PartStatusText
                              state={part.state}
                              reason={part.reason}
                              pages={part.pages}
                            />
                          </Td>
                          <Td className={cell}>{partActions(row, part)}</Td>
                        </tr>
                        {earlierRows(row, part)}
                      </Fragment>
                    );
                  })}
              </tbody>
            );
          })}
        </table>
      </div>
    </div>
  );
}
