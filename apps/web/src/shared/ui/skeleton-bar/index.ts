// 스켈레톤 막대 하나의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
// load-skeleton 에서 떼어 냈다(밴드 DT1, sid:MARC-ISSUE-373 — LD1 검증 권고 2): card(PageTitle 자리 잡기)와 load-skeleton(LoadSkeleton 이 Card 를 씀)이
//   서로 가져오던 고리를 끊는다. 둘 다 여기서 막대를 가져온다.
export { SkeletonBar } from './ui/SkeletonBar.tsx';
export type { SkeletonBarProps } from './ui/SkeletonBar.tsx';
