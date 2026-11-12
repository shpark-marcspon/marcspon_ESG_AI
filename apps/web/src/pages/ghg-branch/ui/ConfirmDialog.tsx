// 확인 창 하나(밴드 W12-0a ② — AD-01 ActiveDialog 꼴: 가운데 제목 + [취소]·[확인]). 닫히면 연 단추로 초점.
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

export interface ConfirmDialogProps {
  title: string;
  cancel: string;
  confirm: string;
  returnFocus: HTMLElement;
  testId: string;
  onConfirm(): void;
  onClose(): void;
}

export function ConfirmDialog({
  title,
  cancel,
  confirm,
  returnFocus,
  testId,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid={testId}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (returnFocus.isConnected) returnFocus.focus();
        }}
      >
        <DialogTitle className="text-center text-style-pre-heading-02">
          {title}
        </DialogTitle>
        <DialogFooter>
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            onClick={onClose}
          >
            {cancel}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={onConfirm}
          >
            {confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
