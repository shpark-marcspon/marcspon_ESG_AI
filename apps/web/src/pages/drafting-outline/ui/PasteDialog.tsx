// RP-03a 목차 붙여넣기 창(밴드 RPW9 §1-C·D, 디자인 e6 RP-03a·a1·a2 `.rp-pmodal`). 왼쪽 글 칸 · 오른쪽 미리보기 · 아래 넣는 법과 단추.
// 글을 바꿀 때마다 바로 읽는다(누르는 단추 0 — 해석은 model/paste.ts, 순수). 미리보기 줄은 트리 줄 꼴 그대로이고 고치지 않는다.
// 넣기 꺼짐 = 빈 글 · 읽은 줄 0 · 한도 넘음 · busy. 못 읽은 줄만 있으면 켜짐. 「바꾸기」는 지금 목차가 있으면 확인 창을 한 번 더(겹친 창 — Esc 는 위 창만).
// 초점: 열 때 글 칸 · 그냥 닫히면 연 단추(DialogContent 의 되돌리기) · 넣고 닫히면 쓰는 쪽(onInserted)이 넣은 첫 줄로.
// 닫았다 다시 열면 빈 글 · 「붙이기」 — 쓰는 쪽이 열릴 때만 그린다(상태가 새로 선다).
import { useDeferredValue, useId, useMemo, useRef, useState } from 'react';

import {
  ChevronDownIcon,
  ChevronUpIcon,
  CircleWarningIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import {
  RadioGroup,
  RadioGroupItem,
} from '@marcspon/ui/components/radio-group';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import {
  MAX_LEAVES,
  MAX_NODES,
  REQUIREMENT_MAX,
  TITLE_MAX,
  numbersOf,
  parsePaste,
  pasteCounts,
} from '../model/index.ts';
import type { BadReason, PasteHow, PasteRow } from '../model/index.ts';
import { indentOf } from './rowLook.ts';

const words = DR_TEXT.outline;
const paste = words.paste;

const reasonText = (reason: BadReason) =>
  reason === 'titleLong' ? paste.reasons.titleLong(TITLE_MAX)
  : reason === 'requirementLong' ?
    paste.reasons.requirementLong(REQUIREMENT_MAX)
  : paste.reasons[reason];

export interface PasteDialogProps {
  /** 지금 목차(붙이기 셈·번호·확인 창 수). */
  nodes: readonly OutlineNode[];
  busy: boolean;
  /** 넣지 않고 닫힘(취소·Esc·바깥 누름). */
  onClose(): void;
  /** 넣기 — 쓰는 쪽이 목차에 넣고 창을 닫는다. */
  onInsert(rows: PasteRow[], how: PasteHow): void;
  /** 넣고 닫힌 뒤(초점을 넣은 첫 줄로). */
  onInserted(): void;
}

export function PasteDialog({
  nodes,
  busy,
  onClose,
  onInsert,
  onInserted,
}: PasteDialogProps) {
  const ids = useId();
  const [text, setText] = useState('');
  const [how, setHow] = useState<PasteHow>('append');
  const [badOpen, setBadOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const inserted = useRef(false);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const insertRef = useRef<HTMLButtonElement>(null);
  /** 확인 창이 떠 있다 — 닫힘이 끝날 때(onCloseAutoFocus)까지 참. 겹친 창의 Esc 가 바깥 창까지 닫던 것을 막는다(e2e S10b 로 잼). */
  const confirmUp = useRef(false);
  // 긴 붙여넣기에서 글 칸이 굳지 않게 — 읽기는 한 박자 늦어도 된다.
  const deferred = useDeferredValue(text);
  const read = useMemo(() => parsePaste(deferred), [deferred]);
  const rows = useMemo(() => (read.kind === 'read' ? read.rows : []), [read]);
  const bad = read.kind === 'read' ? read.bad : [];
  const counts = pasteCounts(nodes, rows, how);
  // 번호는 넣을 자리에 맞춰 — 붙이기면 지금 마지막 대제목 다음부터.
  const numbers = useMemo(() => {
    const fresh = rows.map((row, at): OutlineNode => ({
      key: `p${at}`,
      parentKey: null,
      depth: row.depth,
      title: row.title,
      requirement: '',
    }));
    return how === 'append' ?
        numbersOf([...nodes, ...fresh]).slice(nodes.length)
      : numbersOf(fresh);
  }, [rows, nodes, how]);
  const canInsert =
    read.kind === 'read' && rows.length > 0 && counts.over === null && !busy;
  const overText =
    counts.over === null ? null
    : counts.over === 'nodes' ?
      paste.tooManyNodes(
        MAX_NODES,
        how === 'append' ? counts.total.nodes : null,
      )
    : paste.tooManyLeaves(
        MAX_LEAVES,
        how === 'append' ? counts.total.leaves : null,
      );

  /** 누른 때의 글로 다시 읽는다(미뤄 읽은 값이 한 박자 늦었을 수 있다). */
  const now = () => {
    const fresh = parsePaste(text);
    const found = fresh.kind === 'read' ? fresh.rows : [];
    return pasteCounts(nodes, found, how).over === null ? found : [];
  };
  const insert = () => {
    const found = now();
    setConfirming(false);
    if (found.length === 0) return;
    inserted.current = true;
    onInsert(found, how);
  };
  const onInsertClick = () => {
    if (!canInsert || now().length === 0) return;
    if (how === 'replace' && nodes.length > 0) {
      confirmUp.current = true;
      setConfirming(true);
    } else insert();
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        data-testid="paste-dialog"
        className={cn(
          // 위에서 64px 에 선다(RPW10 #2, 시안 `.rp-pover` padding-top 64) — 글·띠가 바뀌어도 창 위 끝이 그대로. 낮은 화면은 창 안에서 스크롤(키트 overflow-auto).
          'top-16 w-[960px] max-w-[calc(100vw-64px)] gap-6 [translate:-50%_0]',
          'max-h-[calc(100vh-128px)]',
        )}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          textRef.current?.focus();
        }}
        onEscapeKeyDown={(event) => {
          // 두 창이 같은 Esc 를 받는다(바깥 창이 먼저 — 막으면 안쪽도 닫지 않는다). 확인 창이 떠 있으면 바깥은 그대로 두고 확인 창만 닫는다.
          if (!confirmUp.current) return;
          event.preventDefault();
          setConfirming(false);
        }}
        onCloseAutoFocus={(event) => {
          // 넣었으면 초점은 넣은 첫 줄로(빈 상태에서 연 단추는 넣은 뒤 없어진다).
          if (!inserted.current) return;
          event.preventDefault();
          onInserted();
        }}
      >
        <DialogTitle className="text-style-pre-heading-02">
          {paste.title}
        </DialogTitle>
        <DialogDescription className="sr-only">
          {paste.guide.join(' · ')}
        </DialogDescription>
        <div className="grid grid-cols-2 items-stretch gap-6">
          <div className="flex min-w-0 flex-col gap-3">
            <Textarea
              ref={textRef}
              data-testid="paste-text"
              aria-label={paste.inputLabel}
              aria-describedby={`${ids}-guide`}
              placeholder={paste.placeholder}
              wrap="off"
              spellCheck={false}
              value={text}
              onChange={(event) => setText(event.target.value)}
              className="min-h-[420px] resize-none overflow-auto whitespace-pre text-style-pre-body-06 leading-[1.7] [tab-size:4]"
            />
            <ul
              id={`${ids}-guide`}
              data-testid="paste-guide"
              className="m-0 list-disc pl-4 text-style-pre-caption-03 text-text-tertiary"
            >
              {paste.guide.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
          <section
            aria-labelledby={`${ids}-preview`}
            data-testid="paste-preview"
            className="flex min-h-[420px] min-w-0 flex-col overflow-hidden rounded-component border border-solid border-border-tertiary bg-background-primary"
          >
            <div className="flex items-center justify-between gap-2 border-0 border-b border-solid border-border-quaternary px-4 py-3 text-style-pre-body-04 text-text-primary">
              <span id={`${ids}-preview`}>{paste.preview}</span>
              <span
                aria-live="polite"
                data-testid="paste-counts"
                className="text-style-pre-caption-03 text-text-tertiary tabular-nums"
              >
                {rows.length > 0 &&
                  paste.previewCounts(counts.nodes, counts.leaves)}
              </span>
            </div>
            {overText !== null && (
              <PageInfo
                id={`${ids}-over`}
                role="alert"
                tone="error"
                data-testid="paste-over"
                icon={<CircleWarningIcon aria-hidden />}
                className="mx-3 mt-3"
              >
                {overText}
              </PageInfo>
            )}
            {bad.length > 0 && (
              <>
                <PageInfo
                  tone="important"
                  data-testid="paste-bad"
                  icon={<CircleWarningIcon aria-hidden />}
                  className="mx-3 mt-3 [&>div]:flex [&>div]:flex-1 [&>div]:items-center [&>div]:gap-2"
                >
                  <span>{paste.badSummary(bad.length)}</span>
                  <Button
                    variant="text"
                    size="xs"
                    aria-expanded={badOpen}
                    aria-controls={`${ids}-bad`}
                    data-testid="paste-bad-toggle"
                    onClick={() => setBadOpen((open) => !open)}
                    className="ml-auto h-auto min-h-0 px-0 text-inherit underline [&_svg]:size-3.5"
                  >
                    {badOpen ? paste.badClose : paste.badOpen}
                    {badOpen ?
                      <ChevronUpIcon aria-hidden />
                    : <ChevronDownIcon aria-hidden />}
                  </Button>
                </PageInfo>
                <ul
                  id={`${ids}-bad`}
                  data-testid="paste-bad-list"
                  hidden={!badOpen}
                  className="mx-3 mb-0 mt-2 list-disc rounded-component bg-background-secondary py-2 pl-8 pr-4 text-[13px] leading-[1.7] text-text-secondary"
                >
                  {bad.map((one) => (
                    <li key={one.line}>
                      <b className="font-bold tabular-nums text-text-primary">
                        {paste.badLine(one.line)}
                      </b>
                      {` · ${reasonText(one.reason)}`}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {rows.length === 0 ?
              <p
                data-testid="paste-empty"
                className="m-0 flex flex-1 items-center justify-center p-6 text-style-pre-body-06 text-text-tertiary"
              >
                {paste.previewEmpty}
              </p>
            : <ul
                aria-label={paste.preview}
                data-testid="paste-rows"
                className="m-0 box-border flex max-h-[504px] list-none flex-col overflow-y-auto py-1 pl-0 pr-0"
              >
                {rows.slice(0, MAX_NODES).map((row, at) => (
                  <li
                    key={`${row.line}`}
                    data-depth={row.depth}
                    style={{ paddingLeft: `${indentOf(row.depth)}px` }}
                    className={cn(
                      'box-border flex min-h-9 items-center gap-2 border-0 border-l-[3px] border-solid border-l-transparent py-1 pr-4 text-style-pre-body-06',
                      row.depth === 1 ?
                        'font-bold text-text-primary'
                      : 'text-text-secondary',
                    )}
                  >
                    <span
                      data-testid="paste-number"
                      className="inline-block min-w-11 shrink-0 whitespace-nowrap text-style-pre-caption-02 tabular-nums text-text-tertiary"
                    >
                      {numbers[at]}
                    </span>
                    <span
                      data-testid="paste-title"
                      title={row.title}
                      className="line-clamp-2 min-w-0 flex-1 break-words"
                    >
                      {row.title}
                    </span>
                    <span className="flex shrink-0 items-center gap-1 font-normal">
                      {row.requirement.length > 0 && (
                        <span
                          data-testid="paste-requirement"
                          title={paste.requirementMarkTitle}
                          className="rounded-control bg-background-secondary px-1 text-style-pre-caption-02 text-text-tertiary"
                        >
                          {paste.requirementMark}
                        </span>
                      )}
                      <span className="text-style-pre-caption-02 text-text-quaternary">
                        {words.depths[row.depth - 1]}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            }
          </section>
        </div>
        <div className="flex items-center justify-between gap-4 border-0 border-t border-solid border-border-quaternary pt-2">
          <RadioGroup
            aria-label={paste.howLabel}
            value={how}
            onValueChange={(value) => setHow(value as PasteHow)}
            className="flex gap-6 pt-4"
          >
            {(['append', 'replace'] as const).map((one) => (
              <label
                key={one}
                className="flex items-center gap-2 text-style-pre-body-06 text-text-secondary"
              >
                <RadioGroupItem value={one} data-testid={`paste-${one}`} />
                {paste[one]}
              </label>
            ))}
          </RadioGroup>
          <div className="flex items-center gap-2 pt-4">
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              onClick={onClose}
            >
              {words.cancel}
            </Button>
            <Button
              variant="solidBlack"
              shape="round"
              size="md"
              ref={insertRef}
              data-testid="paste-insert"
              disabled={!canInsert}
              aria-describedby={overText !== null ? `${ids}-over` : undefined}
              onClick={onInsertClick}
            >
              {paste.insert(rows.length > 0 ? rows.length : null)}
            </Button>
          </div>
        </div>
        {confirming && (
          <Dialog
            open
            onOpenChange={(open) => {
              if (!open) setConfirming(false);
            }}
          >
            <DialogContent
              size="sm"
              role="alertdialog"
              data-testid="paste-confirm"
              onCloseAutoFocus={(event) => {
                // [취소]·Esc 는 [목차에 넣기]로(누름이 초점을 옮기지 않는 브라우저도 있다). 넣었으면 바깥 창이 정한다.
                event.preventDefault();
                confirmUp.current = false;
                if (!inserted.current) insertRef.current?.focus();
              }}
            >
              <DialogTitle className="text-center text-style-pre-heading-02">
                {paste.confirmTitle}
              </DialogTitle>
              <DialogDescription className="text-center">
                {paste.confirmBody(nodes.length, rows.length)}
              </DialogDescription>
              <DialogFooter>
                <Button
                  variant="outlineBlack"
                  shape="round"
                  size="md"
                  onClick={() => setConfirming(false)}
                >
                  {words.cancel}
                </Button>
                <Button
                  variant="solidBlack"
                  shape="round"
                  size="md"
                  onClick={insert}
                >
                  {paste.confirmYes}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </DialogContent>
    </Dialog>
  );
}
