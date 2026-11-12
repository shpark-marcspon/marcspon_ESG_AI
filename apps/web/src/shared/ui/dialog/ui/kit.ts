// 모달에서 키트 것을 그대로 쓰는 부분. Content 와 Overlay 만 우리 것(DialogContent.tsx)이다.
// 여기의 DialogTitle 은 키트 원형이다. 폴더 안 새 코드는 ./DialogTitle.tsx 를 쓴다(공개 표면 index.ts 도 그것을 내보낸다).
// 루트 Dialog 에는 variant 를 주지 않는다(우리 Content 는 default 꼴로 고정이다. DialogContent.tsx 머리말).
export {
  Dialog,
  DialogBody,
  DialogClose,
  DialogCloseIconButton,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@marcspon/ui/components/dialog';
export type { DialogCloseIconButtonProps } from '@marcspon/ui/components/dialog';
