// GW-05 r4 ① 「근거 확인」 칸 — 보기와 고치기(밴드 GRJ1 ③, 결정 MARC-ENT-617). 상태는 부르는 쪽(Detail)이 쥔다: 이 칸은
// 지금 근거(지운 칩 차례·더한 조각)를 그리고 바꾼 값을 onDraft 로 올린다. 부르는 쪽은 바뀔 때마다 저장하고(밴드 GRJ2), 칸을
// 벗어날 때 onLeave 로 닫는다(서버 값과 같으면 PUT 없이).
//   - 「추가」·「취소」로 입력 상자가 사라지면 초점을 칸 안([+ 근거 더하기])으로 돌린다 — 지운 요소에서는 blur 가 오지 않아
//     칸 벗어남이 끊기지 않게(sid:MARC-TICK-568).
//   - 고칠 수 없으면(재판단이 도는 중·확정 뒤) 고치는 중이어도 보기 꼴 — 단추·입력 상자 없음, 쓰던 입력 상자 글은 버림,
//     초안 바뀜을 올리지 않는다(밴드 GRJ3, sid:MARC-TICK-569 — 서버도 도는 문장의 근거 PUT 을 409 rejudge_running 으로 막는다).
//   - 보기: 기준 판단 칩(지운 칩은 재판단 전까지 줄그음·흐림으로 남는다) + 더한 조각(「직접 더함」 · 「(n페이지)」).
//   - 고치기: 줄마다 [지우기](지운 칩은 [되살리기]), 더한 조각도 [지우기], [+ 근거 더하기] → 글 칸·페이지 고르기(선택)·[더하기][취소].
//   - 칩도 더한 조각도 없고 고칠 수 없으면 칸을 그리지 않는다(근거를 찾지 못한 문장도 고칠 수 있으면 칸이 있다 — r4 Low 예시).
// 무효 조건: 미리보기에서 글을 골라 페이지를 채우는 것(r4 회색 안내)은 이 밴드에 없다 — 페이지는 고르기로만.
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { PlusIcon, TrashIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type { EvidenceAdded } from '../../../entities/greenwash/model/index.ts';
import { AddedMark } from '../../../entities/greenwash/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';

const words = GW_TEXT.reviewScreen;
const say = words.rejudge;

export interface EvidenceDraft {
  removed: readonly number[];
  added: readonly EvidenceAdded[];
}

export function EvidenceEditor({
  chips,
  draft,
  editable,
  editing,
  pageCount,
  onStart,
  onDraft,
  onLeave,
  footer,
}: {
  /** 기준 판단의 「근거에서 확인됨」. */
  chips: readonly string[];
  draft: EvidenceDraft;
  /** 고칠 수 있는가(확정 전 + 쓰기). */
  editable: boolean;
  editing: boolean;
  /** 페이지 고르기의 끝(문서 쪽 수). */
  pageCount: number;
  onStart(): void;
  onDraft(next: EvidenceDraft): void;
  /** 고치는 중에 초점이 칸 밖으로 나감(저장할 때). */
  onLeave(): void;
  /** 칸 아래 한 줄(바뀜 안내 — 부르는 쪽이 짓는다). */
  footer?: ReactNode;
}) {
  const removed = new Set(draft.removed);
  const [adding, setAdding] = useState<{ text: string; page: string } | null>(
    null,
  );
  const textId = useId();
  const pageId = useId();
  const sectionRef = useRef<HTMLElement>(null);
  /** 입력 상자를 닫은 뒤 초점을 [+ 근거 더하기]로 돌릴 것인가. */
  const refocus = useRef(false);
  useLayoutEffect(() => {
    if (adding !== null || !refocus.current) return;
    refocus.current = false;
    sectionRef.current
      ?.querySelector<HTMLElement>('[data-testid="evidence-add-open"]')
      ?.focus();
  }, [adding]);
  const closeAdding = () => {
    refocus.current = true;
    setAdding(null);
  };
  /** 고치기 단추·입력 상자를 그리는가 — 고치는 중이어도 고칠 수 없으면(재판단이 도는 중·확정 뒤) 보기 꼴(밴드 GRJ3). */
  const open = editing && editable;
  // 도는 동안 열려 있던 입력 상자의 쓰던 글은 버린다(닫힌 뒤 다시 열면 빈 상자 — 초점은 돌리지 않는다)
  useEffect(() => {
    if (!open) setAdding(null);
  }, [open]);
  if (!editable && chips.length === 0 && draft.added.length === 0) return null;

  /** 고칠 수 없으면(도는 중) 초안 바뀜을 올리지 않는다(그물 — 단추도 그리지 않는다). */
  const draftTo = (next: EvidenceDraft) => {
    if (open) onDraft(next);
  };
  const toggle = (index: number) => {
    const next = new Set(removed);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    draftTo({ ...draft, removed: [...next].sort((a, b) => a - b) });
  };
  const dropAdded = (at: number) =>
    draftTo({ ...draft, added: draft.added.filter((_, i) => i !== at) });
  const addPiece = () => {
    if (adding === null || adding.text.trim() === '') return;
    draftTo({
      ...draft,
      added: [
        ...draft.added,
        {
          text: adding.text.trim(),
          page: adding.page === '' ? null : Number(adding.page),
        },
      ],
    });
    closeAdding();
  };

  return (
    <section
      ref={sectionRef}
      className="flex flex-col gap-2 border-0 border-t border-solid border-border-quaternary py-4"
      data-testid="evidence"
      data-editing={editing ? 'true' : undefined}
      onBlur={(event) => {
        if (!open) return;
        const next = event.relatedTarget;
        if (next instanceof Node && event.currentTarget.contains(next)) return;
        onLeave();
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <h4 className="m-0 inline-flex flex-wrap items-center gap-1.5 text-style-pre-body-04 text-text-primary">
          {words.evidenceHeading}
          {open && (
            <span className="text-style-pre-caption-03 text-text-tertiary">
              {words.edit.editing}
            </span>
          )}
        </h4>
        {editable && !editing && (
          <Button
            variant="outlineGrey"
            shape="round"
            size="sm"
            onClick={onStart}
            data-testid="evidence-edit"
          >
            {words.edit.start}
          </Button>
        )}
      </div>
      <div className="flex items-start gap-3">
        <span className="w-24 shrink-0 text-style-pre-caption-03 leading-6 text-text-tertiary">
          {words.confirmedInEvidence}
        </span>
        <ul
          className="m-0 flex min-w-0 flex-1 list-none flex-col gap-1.5 p-0"
          data-testid="chips"
        >
          {chips.map((chip, index) => {
            const gone = removed.has(index);
            return (
              <li
                key={`chip:${index}`}
                data-chip={index}
                data-removed={gone ? 'true' : undefined}
                className="flex items-start gap-1.5"
              >
                <Badge
                  variant="grey"
                  size="sm"
                  className={cn(
                    'h-auto w-auto max-w-full justify-start whitespace-normal break-words py-0.5',
                    gone && 'line-through opacity-50',
                  )}
                >
                  {chip}
                </Badge>
                {open && (
                  <Button
                    variant="text"
                    shape="square"
                    size="xs"
                    className="ml-auto"
                    leftIcon={gone ? undefined : <TrashIcon aria-hidden />}
                    onClick={() => toggle(index)}
                  >
                    {gone ? say.restore : say.remove}
                  </Button>
                )}
              </li>
            );
          })}
          {draft.added.map((piece, at) => (
            <li
              key={`added:${at}`}
              data-added={at}
              className="flex items-start gap-1.5 text-style-pre-caption-02 text-text-secondary"
            >
              <AddedMark />
              <span className="min-w-0 break-words">
                {piece.text}
                {piece.page !== null && ` ${say.addedPage(piece.page)}`}
              </span>
              {open && (
                <Button
                  variant="text"
                  shape="square"
                  size="xs"
                  className="ml-auto"
                  leftIcon={<TrashIcon aria-hidden />}
                  onClick={() => dropAdded(at)}
                >
                  {say.remove}
                </Button>
              )}
            </li>
          ))}
        </ul>
      </div>
      {open &&
        (adding === null ?
          <Button
            variant="text"
            shape="square"
            size="xs"
            className="self-start"
            leftIcon={<PlusIcon aria-hidden />}
            onClick={() => setAdding({ text: '', page: '' })}
            data-testid="evidence-add-open"
          >
            {say.addOpen}
          </Button>
        : <div
            className="flex flex-col gap-2 rounded-component bg-background-secondary p-3"
            data-testid="evidence-add"
          >
            <label
              htmlFor={textId}
              className="text-style-pre-caption-03 text-text-tertiary"
            >
              {say.addText}
            </label>
            <Textarea
              id={textId}
              autoFocus
              rows={3}
              value={adding.text}
              onChange={(event) =>
                setAdding({ ...adding, text: event.currentTarget.value })
              }
              className="text-style-pre-body-06 text-text-secondary"
            />
            <label
              htmlFor={pageId}
              className="text-style-pre-caption-03 text-text-tertiary"
            >
              {say.addPage}
            </label>
            <select
              id={pageId}
              value={adding.page}
              onChange={(event) =>
                setAdding({ ...adding, page: event.currentTarget.value })
              }
              className="h-8 rounded-component border border-solid border-border-tertiary bg-background-primary px-2 text-style-pre-caption-02 text-text-secondary"
            >
              <option value="">{say.addNoPage}</option>
              {Array.from({ length: pageCount }, (_, i) => i + 1).map(
                (page) => (
                  <option key={page} value={String(page)}>
                    {say.pageOption(page)}
                  </option>
                ),
              )}
            </select>
            <div className="flex justify-end gap-2">
              <Button
                variant="outlineGrey"
                shape="round"
                size="sm"
                onClick={closeAdding}
              >
                {say.cancel}
              </Button>
              <Button
                variant="solidBlack"
                shape="round"
                size="sm"
                disabled={adding.text.trim() === ''}
                onClick={addPiece}
              >
                {say.add}
              </Button>
            </div>
          </div>)}
      {footer}
    </section>
  );
}
