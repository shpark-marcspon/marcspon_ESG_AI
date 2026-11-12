// 움직임(gw-m- 클래스 · CountUp)의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
// 접두는 그린워싱 GA1b 내력, 갈음은 sid:MARC-ISSUE-364. CSS 는 ui/CountUp.tsx 가 싣는다 — 클래스만 쓰는 화면도 이 표면의 값 하나는 가져온다.
export { CountUp, useCountUp } from './ui/CountUp.tsx';
