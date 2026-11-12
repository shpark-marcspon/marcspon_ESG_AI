// AI 설정의 적용 확인 창(밴드 AD2R ④ — sid:MARC-ENT-350 「적용은 모듈 공통」, 캔버스 v110 AD-02-CM ③ · AD-01c 모달 꼴).
// 도메인을 모른다: 제목·본문·단추 글·실패 글은 모두 props 로 받는다. 적용은 넣어 준 onConfirm 하나(쓰는 화면이 서버에 보낸다).
//   - [취소](outlineBlack) · [적용](solidBlack — 주 단추). pending 이면 [적용]은 불러오는 중이고 다시 눌러도 onConfirm 을 부르지 않으며, 창도 닫히지 않는다.
//   - failure 가 있으면 버튼 줄 바로 위 빨강 한 줄(AD-01c 실패 줄 꼴). 창은 닫히지 않는다.
//   - 닫히면 연 단추로 초점을 돌린다(returnFocus 가 있으면).
//   - 밴드 AD2W ③: 되돌리기·나가기 확인 창(r3 ⑤⑥ — 같은 가운데 정렬 꼴)도 이 창으로 그린다. 표식만 testId 로 가른다(기본 apply-confirm).
import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';

import { Button } from '../../button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../dialog/index.ts';

export interface ApplyConfirmProps {
  title: string;
  body: string;
  cancel: string;
  confirm: string;
  /** 앞 적용이 실패했으면 그 글(없으면 null). */
  failure: string | null;
  pending: boolean;
  returnFocus?: HTMLElement | null;
  /** 시험이 찾는 표식(기본 apply-confirm). */
  testId?: string;
  onConfirm(): void;
  onClose(): void;
}

export function ApplyConfirm({
  title,
  body,
  cancel,
  confirm,
  failure,
  pending,
  returnFocus,
  testId = 'apply-confirm',
  onConfirm,
  onClose,
}: ApplyConfirmProps) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !pending) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid={testId}
        onCloseAutoFocus={(event) => {
          if (!returnFocus) return;
          event.preventDefault();
          returnFocus.focus();
        }}
      >
        <DialogTitle className="text-center text-style-pre-heading-02">
          {title}
        </DialogTitle>
        <DialogDescription className="m-0 text-center text-style-pre-body-06 text-text-secondary">
          {body}
        </DialogDescription>
        {failure !== null && (
          <p
            role="alert"
            data-testid="apply-failure"
            className="m-0 flex items-center justify-center gap-1 text-style-pre-caption-03 text-support-error-accent [&_svg]:size-4 [&_svg]:shrink-0"
          >
            <CircleWarningIcon aria-hidden />
            {failure}
          </p>
        )}
        <DialogFooter>
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            disabled={pending}
            onClick={onClose}
          >
            {cancel}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            loading={pending}
            onClick={() => {
              if (pending) return;
              onConfirm();
            }}
          >
            {confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
