// S3-02 카테고리 선택 창(밴드 S3W1 ② — 판 S3-02 [1차]: 담당자 열·편집 숨김, 안내 「카테고리를 선택해 주세요」, C10 비활성).
// 고른 것은 화면 상태로만 쓴다(사용자 10-29 「화면 표시만」 — 요청에 싣지 않는다, sid:MARC-ENT-515). 항목이 많으면 목록이 스크롤된다(판 S3-02c).
// sid:MARC-ISSUE-460 꼴: <form onSubmit> 이라 Enter 가 [확인], 열 때 초점은 첫 고를 수 있는 체크, 닫히면 초점을 returnFocus 로 돌린다.
// 고른 것이 0 이면 [확인]이 꺼진다.
// 꼴(밴드 GX3 — 값 파일 GX3 ① · ② 고침 6~8): 창 960 · 안내는 PageInfo · 표 머리(전체 고름 체크 + 「카테고리」 + (?)) 고정, 목록만 최대 360 으로 민다.
//   줄 최소 56 · 체크 20(키트 size lg). 머리 (?) 는 S3-02a 설명 창을 연다(CategoryInfoDialog — 이 창 위에 뜬다). 줄마다 (?) 는 장식이고
//   마우스를 올리면 그 카테고리 설명 한 줄을 말풍선으로(키보드는 머리 (?) → 설명 창으로 같은 글에 닿는다). C10 까닭은 이름 바로 오른쪽 8.
import { useRef, useState } from 'react';
import type { FormEvent } from 'react';

import { CircleQuestionIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  CATEGORIES,
  toggleCategory,
} from '../../../entities/ghg-scope3/model/index.ts';
import type { CategoryId } from '../../../entities/ghg-scope3/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { CategoryInfoDialog } from './CategoryInfoDialog.tsx';

const words = S3_TEXT.categoryDialog;

export interface CategoryDialogProps {
  /** 처음 고른 것(앞서 고른 것을 다시 보여 준다). */
  initial: readonly CategoryId[];
  /** 닫히면 초점을 돌려줄 단추. */
  returnFocus(): HTMLElement | null;
  onConfirm(chosen: CategoryId[]): void;
  onClose(): void;
}

export function CategoryDialog({
  initial,
  returnFocus,
  onConfirm,
  onClose,
}: CategoryDialogProps) {
  const [chosen, setChosen] = useState<CategoryId[]>(() =>
    CATEGORIES.filter((c) => !c.disabled && initial.includes(c.id)).map(
      (c) => c.id,
    ),
  );
  const firstRef = useRef<HTMLButtonElement>(null);
  const infoRef = useRef<HTMLButtonElement>(null);
  const [info, setInfo] = useState(false);
  const pickable = CATEGORIES.filter((c) => !c.disabled).map((c) => c.id);
  const all =
    chosen.length === 0 ? false
    : chosen.length === pickable.length ? true
    : 'indeterminate';
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (chosen.length > 0) onConfirm(chosen);
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="lg"
        data-testid="s3-category-dialog"
        className="w-[960px] max-w-[calc(100vw-64px)]"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          firstRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const target = returnFocus();
          if (target?.isConnected) target.focus();
        }}
      >
        <form onSubmit={submit} className="flex flex-col gap-8">
          <DialogTitle>{words.title}</DialogTitle>
          <div className="flex flex-col gap-4">
            <PageInfo icon={<PageInfoIcon />} data-testid="s3-category-guide">
              {words.guideLead}
              <b>{words.guideStrong}</b>
              {words.guideTail}
            </PageInfo>
            <TooltipProvider>
              <div
                role="group"
                aria-label={words.listLabel}
                className="flex flex-col border-0 border-t border-solid border-border-tertiary"
              >
                <div
                  data-testid="s3-category-head"
                  className="box-border flex h-10 items-center border-0 border-b border-solid border-border-tertiary bg-support-grey-subtle text-style-pre-body-05 text-text-tertiary"
                >
                  <span className="flex w-[52px] shrink-0 justify-center">
                    <Checkbox
                      size="lg"
                      checked={all}
                      aria-label={words.selectAll}
                      data-testid="s3-category-all"
                      onCheckedChange={() =>
                        setChosen(all === true ? [] : pickable)
                      }
                    />
                  </span>
                  <span className="flex items-center gap-1.5 px-4">
                    {words.column}
                    <button
                      ref={infoRef}
                      type="button"
                      aria-label={words.infoOpen}
                      aria-haspopup="dialog"
                      data-testid="s3-category-info-open"
                      onClick={() => setInfo(true)}
                      className="inline-flex size-6 cursor-pointer items-center justify-center rounded-control border-0 bg-transparent p-0 text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-secondary"
                    >
                      <CircleQuestionIcon aria-hidden className="size-4" />
                    </button>
                  </span>
                </div>
                <div
                  data-testid="s3-category-list"
                  className="flex max-h-[360px] flex-col overflow-y-auto [scrollbar-width:thin]"
                >
                  {CATEGORIES.map((category, index) => {
                    const name = words.item(
                      category.number,
                      S3_TEXT.categories[category.id],
                    );
                    const reasonId = `s3-reason-${category.id}`;
                    return (
                      <label
                        key={category.id}
                        data-category={category.id}
                        className={
                          'box-border flex min-h-14 shrink-0 items-center border-0 border-b border-solid border-border-quaternary text-style-pre-body-06 text-text-secondary' +
                          (category.disabled ? ' cursor-not-allowed' : '')
                        }
                      >
                        <span className="flex w-[52px] shrink-0 justify-center">
                          <Checkbox
                            ref={
                              (
                                index ===
                                CATEGORIES.findIndex((c) => !c.disabled)
                              ) ?
                                firstRef
                              : undefined
                            }
                            size="lg"
                            checked={chosen.includes(category.id)}
                            disabled={category.disabled}
                            aria-describedby={
                              category.disabled ? reasonId : undefined
                            }
                            onCheckedChange={() =>
                              setChosen((now) =>
                                toggleCategory(now, category.id),
                              )
                            }
                          />
                        </span>
                        <span className="flex min-w-0 items-center gap-1.5 px-4 py-2">
                          <span
                            className={
                              category.disabled ?
                                'text-text-quaternary'
                              : undefined
                            }
                          >
                            {name}
                          </span>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span
                                aria-hidden
                                data-testid="s3-category-tip"
                                className="inline-flex text-text-secondary"
                              >
                                <CircleQuestionIcon className="size-4" />
                              </span>
                            </TooltipTrigger>
                            <TooltipContent
                              side="bottom"
                              className="w-[180px] bg-background-secondary-inverse px-3 py-1.5 text-left text-style-pre-body-06"
                              arrowClassName="fill-background-secondary-inverse"
                            >
                              {S3_TEXT.categoryInfo.descriptions[category.id]}
                            </TooltipContent>
                          </Tooltip>
                          {category.disabled && (
                            <span
                              id={reasonId}
                              className="ml-2 text-style-pre-caption-03 text-text-tertiary"
                            >
                              {S3_TEXT.disabledReason}
                            </span>
                          )}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </TooltipProvider>
          </div>
          <DialogFooter>
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              onClick={onClose}
            >
              {words.cancel}
            </Button>
            <Button
              type="submit"
              variant="solidBlack"
              shape="round"
              size="md"
              disabled={chosen.length === 0}
            >
              {words.confirm}
            </Button>
          </DialogFooter>
        </form>
        {info && (
          <CategoryInfoDialog
            returnFocus={() => infoRef.current}
            onClose={() => setInfo(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
