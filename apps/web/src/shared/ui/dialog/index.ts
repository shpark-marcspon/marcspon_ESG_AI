// 모달의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
// Content·Title·Footer 는 우리 것이고(Title 은 키트 것을 감싸 기본 글자 24, Footer 는 위 8 을 준다) 나머지는 키트 것을 다시 내보낸다.
export { DIALOG_SIZES, DialogContent } from './ui/DialogContent.tsx';
export type { DialogContentProps, DialogSize } from './ui/DialogContent.tsx';
export { DialogFooter } from './ui/DialogFooter.tsx';
export { DialogTitle } from './ui/DialogTitle.tsx';
export {
  Dialog,
  DialogBody,
  DialogClose,
  DialogCloseIconButton,
  DialogDescription,
  DialogHeader,
  DialogTrigger,
} from './ui/kit.ts';
export type { DialogCloseIconButtonProps } from './ui/kit.ts';
