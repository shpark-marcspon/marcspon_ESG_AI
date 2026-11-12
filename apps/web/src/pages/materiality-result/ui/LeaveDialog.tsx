// 나가기 물음(판 IR-04 r3 「바꾼 채 다른 탭이나 거르기로 나가려 할 때」 — 밴드 IRW11 Q9). pages/drafting-outline/ui/OutlineScreen.tsx 의
// 나가기 창 꼴을 공용 shared/ui/dialog 로 화면 안에 새로 지었다(가져오지 않는다 — 남의 page 땅).
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

const words = IR_TEXT.result.edit;

export function LeaveDialog({
  onStay,
  onLeave,
  onCloseAutoFocus,
}: {
  onStay(): void;
  onLeave(): void;
  /** 창이 닫힐 때 초점 자리(공용 DialogContent 가 먼저 부른다 — preventDefault 하면 연 자리로 돌려주지 않는다). */
  onCloseAutoFocus?: (event: Event) => void;
}) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onStay();
      }}
    >
      <DialogContent
        size="sm"
        data-testid="leave-dialog"
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <DialogTitle className="text-center text-style-pre-heading-02">
          {words.leaveTitle}
        </DialogTitle>
        <DialogDescription className="text-center">
          {words.leaveBody}
        </DialogDescription>
        <DialogFooter>
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            onClick={onStay}
          >
            {words.leaveStay}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={onLeave}
          >
            {words.leaveGo}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
