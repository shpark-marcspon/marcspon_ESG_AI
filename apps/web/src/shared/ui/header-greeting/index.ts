// 머리 줄 인사말 + [로그아웃]의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
// 모양만 있는 부품이라 ui 층 하나다. 세션을 모른다 — 로그아웃은 쓰는 틀이 onLogout 으로 넘긴다.
export { HeaderGreeting } from './ui/HeaderGreeting.tsx';
export type { HeaderGreetingProps } from './ui/HeaderGreeting.tsx';
