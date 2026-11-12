// RP-03 왼쪽 트리 칸(밴드 RPW7 §1-A·§1-D·§1-E, 판 v197 `.rp-tree--ed`). 틀: 머리 → 더하기 셋 → 목록(14줄 넘으면 안쪽 스크롤) → 단축키 도움말.
// 줄 키보드(§1-E)는 줄에 초점이 있을 때만(event.target === currentTarget) — 요구 칸·이름 칸의 글 편집은 건드리지 않는다.
//   탭 멈춤은 고른 줄 하나. 줄의 Tab 을 단계 바꿈으로 쓰므로 나가는 길은 Enter → 이름 칸 → 평소 Tab 차례다(Shift+Tab 으로 더하기 줄에 가지는 못한다).
//   그래서 줄 안 아이콘은 탭 차례에 넣지 않는다(tabIndex −1) — 키보드는 단축키(↑↓ 고르기 · Alt+↑↓ 옮기기 · Tab/Shift+Tab 단계), 터치는 아이콘 탭(편집 칸 「순서 · 단계」 단추 넷은 RPW12 에서 걷음).
// 고른 줄 보이기는 목록 scrollTop 만 움직인다(fitRow) — scrollIntoView 는 창까지 움직인다. 줄 초점도 preventScroll(OutlineScreen).
import { useId, useLayoutEffect, useRef } from 'react';
import type { KeyboardEvent, PointerEvent, ReactNode, RefObject } from 'react';

import {
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  PlusIcon,
  TrashIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';
import { cn } from '@marcspon/ui/lib/utils';

import { createPortal } from 'react-dom';

import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  descendantsOf,
  indent,
  moveDown,
  moveUp,
  movesOf,
  numbersOf,
  outdent,
} from '../model/index.ts';
import type { Drop, FieldProblem } from '../model/index.ts';
import { fitRow } from './fitRow.ts';
import { indentOf } from './rowLook.ts';
import { useTreeDrag } from './useTreeDrag.ts';
import type { TreeDragView } from './useTreeDrag.ts';

const words = DR_TEXT.outline;

/** 목록이 이 줄 수를 넘으면 머리에 「N개」(판 긴 목차 예시). */
const LONG_TREE = 14;

/** 손잡이 점 여섯(판 `.rp-grip` svg). */
const gripDots = (
  <svg viewBox="0 0 12 18" fill="currentColor" aria-hidden>
    {[3, 9, 15].map((cy) =>
      [3, 9].map((cx) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={1.5} />
      )),
    )}
  </svg>
);

export interface OutlineTreeProps {
  nodes: OutlineNode[];
  at: number | null;
  changed: ReadonlySet<string>;
  rowProblems(key: string): FieldProblem[];
  busy: boolean;
  /** 창이 떠 있어 끌기를 받지 않는다(끄는 중이면 취소). */
  dragOff: boolean;
  listRef: RefObject<HTMLUListElement>;
  /** focus — 고른 줄로 초점: 'row' 키보드(테두리 보임) · 'rowQuiet' 포인터(테두리 없음, RPW8 N1). */
  onSelect(index: number, focus?: 'row' | 'rowQuiet'): void;
  onAddTop(): void;
  onAddSibling(): void;
  onAddChild(): void;
  /** [붙여넣기] — 붙여넣기 창을 연다(RPW9 A3). */
  onPaste(): void;
  /** 줄 Enter — 이름 칸으로. */
  onEnterName(): void;
  /** 순서·단계 바꿈(못 옮기면 그대로) — 초점은 고른 줄에. */
  onMove(move: typeof moveUp, index: number): void;
  onRemove(index: number): void;
  onDrop(index: number, drop: Drop): void;
  /** 끌기가 끝남 — 초점을 고른 줄로(테두리 없이). */
  onDragEnd(): void;
}

export function OutlineTree({
  nodes,
  at,
  changed,
  rowProblems,
  busy,
  dragOff,
  listRef,
  onSelect,
  onAddTop,
  onAddSibling,
  onAddChild,
  onPaste,
  onEnterName,
  onMove,
  onRemove,
  onDrop,
  onDragEnd,
}: OutlineTreeProps) {
  const helpId = useId();
  const numbers = numbersOf(nodes);
  const moves = at === null ? null : movesOf(nodes, at);
  const { view, onGripDown, held } = useTreeDrag({
    listRef,
    nodes,
    disabled: busy || dragOff,
    onPick: (index) => onSelect(index),
    onDrop,
    onEnd: onDragEnd,
  });
  const dragging = view !== null;

  // 고른 줄·차례가 바뀐 뒤 목록 안에서 보이게. 끄는 중에는 손 아래가 움직이지 않게 건드리지 않고, 놓으면(거절·제자리 포함) 그 줄로 돌아온다.
  const fitKey = at === null ? null : nodes[at]?.key;
  const firstFit = useRef(true);
  useLayoutEffect(() => {
    const box = listRef.current;
    // 처음 그릴 때는 굴리지 않는다(쪽을 열자마자 창이 움직이지 않게).
    if (firstFit.current) {
      firstFit.current = false;
      return;
    }
    if (dragging || !box || at === null) return;
    const row = box.querySelector<HTMLElement>('[aria-selected="true"]');
    if (row) fitRow(box, row);
  }, [at, fitKey, nodes.length, dragging, listRef]);

  const onRowKey = (event: KeyboardEvent<HTMLLIElement>, index: number) => {
    if (event.target !== event.currentTarget || busy) return;
    // 손잡이를 잡은 동안 줄 키는 막는다 — 끌던 자리 번호가 어긋나 엉뚱한 줄이 옮겨진다. 막기만 해서 초점도 튀지 않는다.
    if (held()) {
      event.preventDefault();
      return;
    }
    switch (event.key) {
      case 'ArrowUp':
      case 'ArrowDown': {
        event.preventDefault();
        // Alt+↑↓ = 위로·아래로 옮기기(하위와 함께 — RPW12, 디자인 c3). 끝이면 아무 일 없음, 초점은 옮긴 줄(onMove → OutlineScreen).
        if (event.altKey) {
          const up = event.key === 'ArrowUp';
          const can = movesOf(nodes, index);
          if (up ? can.up : can.down) onMove(up ? moveUp : moveDown, index);
          return;
        }
        const next = index + (event.key === 'ArrowUp' ? -1 : 1);
        if (next >= 0 && next < nodes.length) onSelect(next, 'row');
        return;
      }
      case 'Enter':
        event.preventDefault();
        onEnterName();
        return;
      case ' ':
        event.preventDefault();
        onSelect(index);
        return;
      case 'Tab':
        // 못 옮겨도 막는다 — 데이터는 그대로인데 초점만 튀지 않게.
        event.preventDefault();
        onMove(event.shiftKey ? outdent : indent, index);
        return;
      case 'Delete':
      case 'Backspace':
        event.preventDefault();
        onRemove(index);
        return;
    }
  };

  return (
    <div
      data-testid="outline-tree-box"
      className="overflow-hidden rounded-component border border-solid border-border-tertiary"
    >
      <div className="flex items-center justify-between gap-2 border-0 border-b border-solid border-border-quaternary px-4 py-3 text-style-pre-body-04 text-text-primary">
        <span>{words.treeTitle}</span>
        {nodes.length > LONG_TREE && (
          <span
            data-testid="tree-total"
            className="text-style-pre-caption-03 text-text-tertiary"
          >
            {words.treeTotal(nodes.length)}
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-2 border-0 border-b border-solid border-border-quaternary px-4 py-3">
        <AddButton disabled={busy} onClick={onAddTop}>
          {words.addTop}
        </AddButton>
        <AddButton disabled={busy || at === null} onClick={onAddSibling}>
          {words.addSibling}
        </AddButton>
        <AddButton disabled={busy || !moves?.addChild} onClick={onAddChild}>
          {words.addChild}
        </AddButton>
        <Button
          variant="text"
          size="md"
          className="underline"
          disabled={busy}
          onClick={onPaste}
        >
          {words.paste.open}
        </Button>
      </div>
      <TooltipProvider>
        <ul
          ref={listRef}
          role="listbox"
          aria-label={words.treeTitle}
          aria-describedby={helpId}
          data-testid="outline-tree"
          className={cn(
            'm-0 box-border flex max-h-[504px] list-none flex-col overflow-y-auto py-1 pl-0 pr-0',
            dragging && 'select-none [&_*]:!cursor-grabbing',
          )}
        >
          {nodes.map((one, index) => (
            <Row
              key={one.key}
              node={one}
              index={index}
              number={numbers[index]!}
              selected={index === at}
              tabStop={index === (at ?? 0)}
              changed={changed.has(one.key)}
              bad={rowProblems(one.key).length > 0}
              busy={busy}
              view={view}
              moves={index === at ? moves : null}
              onClick={() => onSelect(index)}
              onKeyDown={(event) => onRowKey(event, index)}
              onGripDown={(event) => onGripDown(event, index)}
              onGripClick={() => onSelect(index, 'rowQuiet')}
              onMove={(move) => onMove(move, index)}
              onRemove={() => onRemove(index)}
            />
          ))}
          {view?.line === nodes.length && <DropLine view={view} />}
        </ul>
      </TooltipProvider>
      <p
        id={helpId}
        data-testid="outline-help"
        className="m-0 border-0 border-t border-solid border-border-quaternary px-4 py-2 text-style-pre-caption-03 text-text-tertiary"
      >
        {words.help}
      </p>
      {view && <DragLayer view={view} nodes={nodes} />}
    </div>
  );
}

function AddButton({
  disabled,
  onClick,
  children,
}: {
  disabled: boolean;
  onClick(): void;
  children: ReactNode;
}) {
  return (
    <Button
      variant="outlineGrey"
      shape="round"
      size="sm"
      disabled={disabled}
      onClick={onClick}
    >
      <PlusIcon aria-hidden />
      {children}
    </Button>
  );
}

function Row({
  node,
  index,
  number,
  selected,
  tabStop,
  changed,
  bad,
  busy,
  view,
  moves,
  onClick,
  onKeyDown,
  onGripDown,
  onGripClick,
  onMove,
  onRemove,
}: {
  node: OutlineNode;
  index: number;
  number: string;
  selected: boolean;
  tabStop: boolean;
  changed: boolean;
  bad: boolean;
  busy: boolean;
  view: TreeDragView | null;
  moves: ReturnType<typeof movesOf> | null;
  onClick(): void;
  onKeyDown(event: KeyboardEvent<HTMLLIElement>): void;
  onGripDown(event: PointerEvent): void;
  /** 끌기 전에 놓은 클릭 — 눌림을 막아 초점이 오지 않으니 고르면서 초점도 준다. */
  onGripClick(): void;
  onMove(move: typeof moveUp): void;
  onRemove(): void;
}) {
  const ghost = view !== null && index >= view.index && index < view.end;
  return (
    <>
      {view?.line === index && <DropLine view={view} />}
      <li
        role="option"
        aria-selected={selected}
        data-key={node.key}
        data-depth={node.depth}
        data-changed={changed || undefined}
        data-problem={bad || undefined}
        data-ghost={ghost || undefined}
        tabIndex={tabStop ? 0 : -1}
        onClick={onClick}
        onKeyDown={onKeyDown}
        style={{ paddingLeft: `${indentOf(node.depth)}px` }}
        className={cn(
          'group relative box-border flex min-h-9 cursor-pointer items-center gap-2 border-0 border-l-[3px] border-solid py-1 pr-4 text-style-pre-body-06 hover:bg-background-secondary focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-border-secondary',
          selected ?
            'border-l-text-secondary bg-background-secondary font-bold text-text-primary'
          : 'border-l-transparent text-text-secondary',
          node.depth === 1 && 'font-bold text-text-primary',
          ghost && 'opacity-40',
        )}
      >
        <span
          aria-hidden
          data-testid="tree-grip"
          onPointerDown={onGripDown}
          onClick={onGripClick}
          className={cn(
            'absolute left-1 top-1/2 inline-flex w-2 -translate-y-1/2 cursor-grab touch-none text-text-quaternary before:absolute before:-inset-x-1 before:-inset-y-2 before:content-[""] [&_svg]:h-auto [&_svg]:w-full',
            selected ? 'visible' : 'invisible group-hover:visible',
            busy && 'cursor-default',
          )}
        >
          {gripDots}
        </span>
        <span
          data-testid="tree-title"
          title={node.title}
          className="line-clamp-2 min-w-0 flex-1 break-words"
        >
          {/* 표지는 첫 줄에만 선다 — 번호와 제목은 한 흐름이라 둘째 줄이 칸 폭 전부를 쓴다. */}
          <span
            data-testid="tree-marks"
            className="float-right ml-2 flex h-[1lh] items-center gap-2 font-normal"
          >
            {changed && (
              <span
                role="img"
                aria-label={words.rowChanged}
                className="size-1.5 shrink-0 rounded-full bg-support-blue-dark"
              />
            )}
            {bad && (
              <span className="shrink-0 text-style-pre-caption-03 text-support-error">
                {words.rowProblem}
              </span>
            )}
            {moves && !view && (
              <RowIcons
                moves={moves}
                busy={busy}
                onMove={onMove}
                onRemove={onRemove}
              />
            )}
            <span className="shrink-0 text-style-pre-caption-02 text-text-quaternary">
              {words.depths[node.depth - 1]}
            </span>
          </span>
          <span
            data-testid="tree-number"
            className="mr-2 inline-block min-w-11 whitespace-nowrap text-style-pre-caption-02 tabular-nums text-text-tertiary"
          >
            {number}
          </span>
          <span data-testid="tree-title-text">{node.title}</span>
        </span>
      </li>
    </>
  );
}

/** 고른 줄 오른쪽 아이콘 다섯(판 `.rp-mvs`). 탭 차례에 넣지 않는다(§1-E). */
function RowIcons({
  moves,
  busy,
  onMove,
  onRemove,
}: {
  moves: ReturnType<typeof movesOf>;
  busy: boolean;
  onMove(move: typeof moveUp): void;
  onRemove(): void;
}) {
  const icons: [string, boolean, typeof TrashIcon, () => void][] = [
    [words.up, moves.up, ArrowUpIcon, () => onMove(moveUp)],
    [words.down, moves.down, ArrowDownIcon, () => onMove(moveDown)],
    [words.outdent, moves.outdent, ArrowLeftIcon, () => onMove(outdent)],
    [words.indent, moves.indent, ArrowRightIcon, () => onMove(indent)],
    [words.remove, true, TrashIcon, onRemove],
  ];
  return (
    <span
      data-testid="tree-icons"
      className="inline-flex items-center gap-1"
      onClick={(event) => event.stopPropagation()}
    >
      {icons.map(([label, enabled, Icon, run], at) => (
        <Tooltip key={label}>
          <TooltipTrigger asChild>
            {/* 꺼진 단추도 툴팁이 뜨게 span 으로 감싼다(admin-runs RunsScreen 꼴). */}
            <span className="inline-flex">
              <Button
                variant="outlineGrey"
                shape="square"
                size="xs"
                aria-label={label}
                tabIndex={-1}
                disabled={busy || !enabled}
                onClick={run}
                className={cn(
                  'w-[22px] min-w-0 border-border-tertiary px-0 [&_svg]:size-3.5',
                  at === 4 &&
                    'hover:border-support-error hover:bg-support-error-subtle hover:text-support-error',
                )}
              >
                <Icon aria-hidden />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="top">{label}</TooltipContent>
        </Tooltip>
      ))}
    </span>
  );
}

/** 놓일 선(판 `.rp-drop`) — 왼쪽 끝이 들어갈 단계 자리. */
function DropLine({ view }: { view: TreeDragView }) {
  const bad = view.verdict === 'tooDeep';
  const line = bad ? 'border-support-error' : 'border-border-brand';
  return (
    <li
      role="presentation"
      aria-hidden
      data-testid="drop-line"
      data-depth={view.depth}
      data-bad={bad || undefined}
      style={{ marginLeft: `${indentOf(view.depth) + 3}px` }}
      className="relative h-0 list-none"
    >
      <span
        className={cn(
          'absolute left-0 right-4 -top-px z-[1] border-0 border-t-2 border-solid',
          line,
        )}
      >
        <span
          className={cn(
            'absolute left-0 top-[-5px] box-border size-2 rounded-full border-2 border-solid bg-background-primary',
            line,
          )}
        />
      </span>
    </li>
  );
}

/** 손 옆 표·빨간 툴팁 — 목록이 overflow 라 잘리지 않게 body 로 내보낸다(조상 transform 도 피함). */
function DragLayer({
  view,
  nodes,
}: {
  view: TreeDragView;
  nodes: readonly OutlineNode[];
}) {
  const node = nodes[view.index]!;
  const under = descendantsOf(nodes, view.index);
  return createPortal(
    <>
      <div
        data-testid="drag-chip"
        style={{ left: view.x + 12, top: view.y + 12 }}
        className="pointer-events-none fixed z-tooltip flex max-w-xs items-center gap-1.5 truncate whitespace-nowrap rounded-control border border-solid border-border-tertiary bg-background-primary px-3 py-1 text-style-pre-body-05 text-text-primary shadow-[3px_3px_10px_#00000033] [&_svg]:h-auto [&_svg]:w-2 [&_svg]:shrink-0 [&_svg]:text-text-quaternary"
      >
        {gripDots}
        <span className="truncate">
          {under > 0 ?
            `${node.title} · ${words.dragChildren(under)}`
          : node.title}
        </span>
      </div>
      {view.verdict === 'tooDeep' && (
        <div
          role="tooltip"
          data-testid="drop-tip"
          style={{
            right: window.innerWidth - view.listRight + 16,
            bottom: window.innerHeight - view.lineY + 8,
          }}
          className="pointer-events-none fixed z-tooltip flex max-w-[180px] rounded-component bg-[#2D3748] px-3 py-2 text-style-pre-body-05 text-text-primary-inverse shadow-md"
        >
          {words.tooDeep}
        </div>
      )}
    </>,
    document.body,
  );
}
