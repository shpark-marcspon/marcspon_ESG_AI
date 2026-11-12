// 토스트(밴드 S12Q1 ② — 공용 부품, 플랫폼-웹 a8 허락 band-handoffs/S12Q1-permits.md)의 공개 표면.
// 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
export { Toaster, TOAST_DURATION_MS, TOAST_MAX } from './ui/Toaster.tsx';
export type { ToasterProps } from './ui/Toaster.tsx';
export { clearToasts, dismissToast, toast } from './ui/store.ts';
export type { ToastInput, ToastTone } from './ui/store.ts';
