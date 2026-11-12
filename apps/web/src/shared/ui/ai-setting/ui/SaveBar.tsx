// AI 설정의 저장 막대(밴드 AD2W ③ — 디자인 판 AD-02_r3 「저장 막대」). 고친 것이 있을 때만 쓰는 화면이 그린다. 도메인을 모른다: 글은 모두 props.
//   옅은 주황 바탕(시안 v148). 왼쪽 「고친 것 n개 · 아직 저장 전이에요」 한 줄(셈 규칙 줄 없음 — 모든 모듈, GW3R A10),
//   오른쪽 [되돌리기](outlineGrey) · [새 버전으로 저장](solidBlack — 주 단추).
//   saveOff 면 [새 버전으로 저장]은 aria-disabled 이고 누름 처리기가 onSave 를 부르지 않는다(네이티브 disabled 0 — AD-02 의 끈 단추와 같은 꼴).
import { cn } from '@marcspon/ui/lib/utils';

import { Button, buttonVariants } from '../../button/index.ts';

export interface SaveBarProps {
  count: string;
  revert: string;
  save: string;
  /** 저장을 끈다(칸 오류가 있을 때). */
  saveOff?: boolean;
  onRevert(): void;
  onSave(): void;
}

export function SaveBar({
  count,
  revert,
  save,
  saveOff = false,
  onRevert,
  onSave,
}: SaveBarProps) {
  return (
    <div
      role="region"
      aria-label={count}
      data-testid="save-bar"
      className="flex flex-wrap items-center justify-between gap-4 rounded-component border border-solid border-support-orange bg-support-orange-subtle px-4 py-3"
    >
      <p className="m-0 text-style-pre-body-05 text-text-primary">{count}</p>
      <div className="flex items-center gap-2">
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          onClick={onRevert}
        >
          {revert}
        </Button>
        <button
          type="button"
          aria-disabled={saveOff || undefined}
          className={cn(
            buttonVariants({
              variant: 'solidBlack',
              shape: 'round',
              size: 'md',
            }),
            saveOff && 'cursor-not-allowed opacity-40',
          )}
          onClick={() => {
            if (!saveOff) onSave();
          }}
        >
          {save}
        </button>
      </div>
    </div>
  );
}
