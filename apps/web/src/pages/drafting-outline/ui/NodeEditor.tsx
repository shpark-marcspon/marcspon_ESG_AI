// RP-03 오른쪽 편집 칸(밴드 RPW7 §1-B, 판 v197 `.rp-ed`). 머리 한 줄(경로 · 단계 배지 · [삭제]) + 이름 · 요구 + 안내. 순서·단계는 트리(끌기·줄 아이콘·Tab)에서만(RPW12 · `MARC-ENT-656`).
// 아래 단계가 있는 목차: 요구 글 없으면 칸 숨기고 한 줄, 글이 남았으면 회색 읽기 전용 + [글 지우기]. 안 지우면 저장 본문에 그대로 간다(저장 꼴 0 — 감독 답). 다시 잎이 되면 칸에 글이 돌아온다.
import { useId } from 'react';
import type { KeyboardEvent, RefObject } from 'react';

import { TrashIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import { Input } from '@marcspon/ui/components/input';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { lengthOf } from '../../../entities/drafting/model/index.ts';
import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from '../../../shared/ui/form-rows/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { REQUIREMENT_MAX, TITLE_MAX } from '../model/index.ts';
import type { FieldProblem } from '../model/index.ts';

const words = DR_TEXT.outline;

/** 값 칸 — 입력 위아래로 쌓는다. */
const VALUE_CLASS = cn(FORM_VALUE_CLASS, 'flex-col justify-center gap-1.5');

export function NodeEditor({
  node,
  path,
  leaf,
  leaves,
  problems,
  disabled,
  nameRef,
  onEdit,
  onNameEnter,
  onRemove,
}: {
  node: OutlineNode;
  path: string[];
  /** 아래 단계가 없는가. */
  leaf: boolean;
  /** 초안 지을 목차 수(안내). */
  leaves: number;
  problems: FieldProblem[];
  disabled: boolean;
  nameRef: RefObject<HTMLInputElement>;
  onEdit(patch: Partial<Pick<OutlineNode, 'title' | 'requirement'>>): void;
  /** 이름 칸 Enter — 같은 단계 새 줄. */
  onNameEnter(): void;
  onRemove(): void;
}) {
  const titleId = useId();
  const requirementId = useId();
  const titleBad = problems.includes('title');
  const requirementBad = problems.includes('requirement');
  const requirementCount = lengthOf(node.requirement);
  const onNameKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return;
    // 한글 조합 중 Enter 는 조합을 끝낼 뿐 — 그대로 받으면 줄이 둘 생긴다(사파리는 조합 끝난 뒤 keyCode 229 로 한 번 더 온다).
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    onNameEnter();
  };
  return (
    <>
      <div className="flex items-start gap-2">
        <div
          data-testid="node-path"
          className="flex min-w-0 flex-1 flex-wrap items-center gap-1 text-style-pre-caption-02 text-text-tertiary [overflow-wrap:anywhere]"
        >
          {path.map((title) => `${title} › `).join('')}
          <b className="min-w-0 max-w-full text-text-secondary">{node.title}</b>
          <Badge variant="grey" size="sm">
            {words.depthBadges[node.depth - 1]}
          </Badge>
        </div>
        <Button
          variant="text"
          size="sm"
          disabled={disabled}
          onClick={onRemove}
          className="min-w-0 shrink-0 px-2 text-support-error hover:bg-support-error-subtle hover:text-support-error"
        >
          <TrashIcon aria-hidden />
          {words.removeShort}
        </Button>
      </div>
      <div className={FORM_ROWS_CLASS}>
        <div className={FORM_ROW_CLASS}>
          <label htmlFor={titleId} className={FORM_LABEL_CLASS}>
            {words.nameLabel}
            <RequiredMark />
          </label>
          <div className={VALUE_CLASS}>
            <Input
              ref={nameRef}
              id={titleId}
              value={node.title}
              disabled={disabled}
              aria-invalid={titleBad || undefined}
              aria-describedby={titleBad ? `${titleId}-error` : undefined}
              onChange={(event) => onEdit({ title: event.target.value })}
              onKeyDown={onNameKey}
              className={cn('w-3/5', titleBad && 'border-support-error')}
            />
            {titleBad && (
              <p
                id={`${titleId}-error`}
                className="m-0 text-style-pre-caption-03 text-support-error"
              >
                {words.titleProblem(TITLE_MAX)}
              </p>
            )}
          </div>
        </div>
        <div className={FORM_ROW_CLASS}>
          {leaf ?
            <label htmlFor={requirementId} className={FORM_LABEL_CLASS}>
              {words.requirementLabel}
            </label>
          : <span className={FORM_LABEL_CLASS}>{words.requirementLabel}</span>}
          <div className={VALUE_CLASS}>
            {!leaf && node.requirement === '' && (
              <span
                data-testid="requirement-upper"
                className="text-style-pre-body-06 text-text-tertiary"
              >
                {words.upperHint}
              </span>
            )}
            {!leaf && node.requirement !== '' && (
              <>
                <div
                  data-testid="requirement-leftover"
                  aria-readonly
                  className="box-border whitespace-pre-wrap break-words rounded-component border border-solid border-border-quaternary bg-background-secondary p-3 text-style-pre-body-06 text-text-tertiary"
                >
                  {node.requirement}
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-style-pre-body-06 text-text-tertiary">
                    {words.upperLeftover}
                  </span>
                  <Button
                    variant="outlineGrey"
                    shape="round"
                    size="sm"
                    disabled={disabled}
                    onClick={() => onEdit({ requirement: '' })}
                  >
                    {words.clearRequirement}
                  </Button>
                </div>
                {/* 판에 없는 틈: 상한을 넘은 채 상위가 되면 저장이 막히니 까닭을 함께 보인다. */}
                {requirementBad && (
                  <p className="m-0 text-style-pre-caption-03 text-support-error">
                    {words.requirementProblem(REQUIREMENT_MAX)}
                  </p>
                )}
              </>
            )}
            {leaf && (
              <>
                <Textarea
                  id={requirementId}
                  value={node.requirement}
                  disabled={disabled}
                  rows={5}
                  aria-invalid={requirementBad || undefined}
                  aria-describedby={`${requirementId}-hint`}
                  onChange={(event) =>
                    onEdit({ requirement: event.target.value })
                  }
                  className={cn(
                    'max-h-[calc(1.6em*12+24px)] min-h-[108px] overflow-y-auto [field-sizing:content]',
                    requirementBad && 'border-support-error',
                  )}
                />
                <p
                  id={`${requirementId}-hint`}
                  className={cn(
                    'm-0 flex justify-between gap-3 text-style-pre-caption-03',
                    requirementBad ? 'text-support-error' : (
                      'text-text-tertiary'
                    ),
                  )}
                >
                  <span>
                    {requirementBad ?
                      words.requirementProblem(REQUIREMENT_MAX)
                    : words.requirementHint}
                  </span>
                  <span
                    data-testid="requirement-count"
                    className="shrink-0 whitespace-nowrap tabular-nums"
                  >
                    {words.requirementCount(requirementCount, REQUIREMENT_MAX)}
                  </span>
                </p>
              </>
            )}
          </div>
        </div>
      </div>
      <PageInfo data-testid="outline-guide">{words.guide(leaves)}</PageInfo>
    </>
  );
}
