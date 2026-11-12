// 비밀번호 안내 모달(밴드 LG1 ②, 시안 CM-01b). 제목·본문·[확인] 하나. 크기 sm(420 — cm-r1.css 10-16 의 「그린워싱과 같은 꼴」).
// 닫히면 연 자리(「비밀번호를 잊으셨나요?」 글 단추)로 초점이 돌아간다: Trigger 로 열고, 공용 DialogContent 가 연 자리로 돌린다.
import type { ReactNode } from 'react';

import { SESSION_TEXT } from '../../../entities/session/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  DialogTrigger,
} from '../../../shared/ui/dialog/index.ts';

const words = SESSION_TEXT.forgot;

export function ForgotPasswordDialog({ trigger }: { trigger: ReactNode }) {
  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent size="sm">
        <DialogTitle className="text-center text-style-pre-heading-02">
          {words.title}
        </DialogTitle>
        <DialogDescription className="m-0 text-center text-style-pre-body-06 text-text-secondary">
          {words.body}
        </DialogDescription>
        <DialogFooter>
          <DialogClose asChild>
            <Button
              variant="solidBlack"
              shape="round"
              size="md"
              className="min-w-24"
            >
              {words.confirm}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
