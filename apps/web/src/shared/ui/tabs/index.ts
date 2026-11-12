// 탭의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
// 이름은 키트 tabs 와 같다: 키트를 바로 쓰던 화면은 import 경로만 바꾸면 된다.
export { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/Tabs.tsx';
export type { TabsProps } from './ui/Tabs.tsx';
