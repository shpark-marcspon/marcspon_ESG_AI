// 화면 뼈대의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
// 모양만 있는 부품이라 ui 층 하나다.
export { AppShell } from './ui/AppShell.tsx';
export type {
  AppShellMenuItem,
  AppShellProps,
  AppShellSubItem,
} from './ui/AppShell.tsx';
