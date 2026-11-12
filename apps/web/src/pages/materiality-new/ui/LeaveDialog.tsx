// 넣은 채 떠날 때 묻는 창(밴드 IRW15 ④ — 결정 MARC-ENT-668). pages/materiality-result/ui/LeaveDialog.tsx(IR-04 고치기 나가기 창)와
// 같은 공용 shared/ui/dialog 부품·꼴로 화면 안에 새로 지었다(가져오지 않는다 — 남의 page 땅). 글은 IR_TEXT.newRun.leave.
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

const words = IR_TEXT.newRun.leave;

export function LeaveDialog({
  onStay,
  onLeave,
}: {
  onStay(): void;
  onLeave(): void;
}) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onStay();
      }}
    >
      <DialogContent size="sm" data-testid="leave-dialog">
        <DialogTitle className="text-center text-style-pre-heading-02">
          {words.title}
        </DialogTitle>
        <DialogDescription className="text-center">
          {words.body}
        </DialogDescription>
        <DialogFooter>
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            onClick={onStay}
          >
            {words.stay}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={onLeave}
          >
            {words.go}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
