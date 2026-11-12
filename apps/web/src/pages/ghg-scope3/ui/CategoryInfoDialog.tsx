// S3-02a 카테고리 설명 창(sid:MARC-ENT-528 — 값 파일 GX3 ①, Figma 28024:1803 · 판 S3-02a 「그대로」). 보기 전용 창이고 단추는 [확인] 하나다.
// 카테고리 선택 창 머리의 (?) 단추가 연다(그 창 위에 뜨는 두 번째 창 — Esc·바깥 누름은 이 창만 닫고, 고른 값은 그대로).
// 틀 960 · 안쪽 32 · 섹션 사이 32. 제목은 DialogTitle 기본(24 Bold). ✕ 없음. 표 머리는 서 있고 몸만 세로로 민다(낮은 뷰포트에서 [확인]이 화면 안).
// 열 때 초점은 [확인], 닫으면 returnFocus(연 (?) 단추)로.
import { useRef } from 'react';

import { CircleQuestionIcon } from '@marcspon/common/generated/icons/MyIcons';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { CATEGORIES } from '../../../entities/ghg-scope3/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

const words = S3_TEXT.categoryInfo;

/** 표 머리 칸(값 파일 ① — 높이 40 · 회색 바탕 · body-05 tertiary · 아래 선 tertiary). */
const HEAD =
  'box-border flex h-10 items-center border-0 border-b border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary';
/** 표 줄 칸(최소 56 · 안쪽 8/16 · 아래 선 quaternary · body-06 secondary). */
const CELL =
  'box-border flex min-h-14 items-center border-0 border-b border-solid border-border-quaternary px-4 py-2 text-style-pre-body-06 text-text-secondary';

export interface CategoryInfoDialogProps {
  returnFocus(): HTMLElement | null;
  onClose(): void;
}

export function CategoryInfoDialog({
  returnFocus,
  onClose,
}: CategoryInfoDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="lg"
        aria-describedby={undefined}
        data-testid="s3-category-info"
        className="w-[960px] max-w-[calc(100vw-64px)] gap-8 overflow-hidden"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          confirmRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const target = returnFocus();
          if (target?.isConnected) target.focus();
        }}
      >
        <DialogTitle>{words.title}</DialogTitle>
        <div
          role="table"
          aria-label={words.title}
          className="flex min-h-0 flex-col border-0 border-t border-solid border-border-tertiary"
        >
          <div role="rowgroup">
            <div role="row" className="flex">
              <div
                role="columnheader"
                className={`${HEAD} w-[200px] shrink-0 gap-1.5`}
              >
                {words.columns.category}
                <CircleQuestionIcon
                  aria-hidden
                  className="size-4 text-text-secondary"
                />
              </div>
              <div
                role="columnheader"
                className={`${HEAD} min-w-0 flex-1 justify-center`}
              >
                {words.columns.description}
              </div>
            </div>
          </div>
          <div
            role="rowgroup"
            data-testid="s3-category-info-body"
            className="min-h-0 overflow-y-auto [scrollbar-width:thin]"
          >
            {CATEGORIES.map((category) => (
              <div
                key={category.id}
                role="row"
                data-category={category.id}
                className="flex"
              >
                <div role="cell" className={`${CELL} w-[200px] shrink-0`}>
                  {S3_TEXT.categoryDialog.item(
                    category.number,
                    S3_TEXT.categories[category.id],
                  )}
                </div>
                <div
                  role="cell"
                  className={`${CELL} min-w-0 flex-1 justify-center text-center`}
                >
                  {words.descriptions[category.id]}
                </div>
              </div>
            ))}
          </div>
        </div>
        <DialogFooter className="justify-center">
          <Button
            ref={confirmRef}
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={onClose}
          >
            {words.confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
