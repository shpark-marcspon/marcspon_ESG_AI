// 불러오기 스켈레톤의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
// 첫 불러오기 규칙 넷(밴드 LD1, sid:MARC-ENT-443 — sid:MARC-ENT-260 의 300ms 늦추기·틀 유지 위에 얹는다):
//   ① 첫 불러오기 동안 빈/안내 판정을 하지 않는다(로딩 꼴만) — useFirstLoad 가 거짓일 때만 Empty·안내
//   ② 표는 빈 표 대신 자리 잡은 스켈레톤 줄 — SkeletonRows(DataTable 은 loading 하나로)
//   ③ 미리 아는 글(제목·설명)은 처음부터 그린다 — 데이터에서 오는 것만 PageTitle titlePending·descriptionPending
//   ④ 결과 화면은 제목 자리 먼저 — PageTitle titlePending + 본문 LoadSkeleton
//
//   model/     SkeletonWidth 와 줄별 막대 폭(정해진 차례). 순수 TypeScript
//   hooks/     useDelayed: 300ms(LOAD_DELAY_MS) 이어서 참이어야 참. 모양을 모른다
//              useFirstLoad: 마운트 뒤 첫 응답 전인가(빈/안내 판정은 이것이 거짓일 때만)
//              useRetryFocus: [다시 시도] 뒤 초점(실패면 새 [다시 시도], 성공이면 받은 마디). 첫 진입에서는 옮기지 않는다
//   ui/        SkeletonRows(표 몸 줄) · LoadSkeleton(결과 카드). 클래스 이름은 여기에만 있다. 막대 하나는 shared/ui/skeleton-bar(밴드 DT1 — card 와의 고리를 끊음)
export * from './model/index.ts';
export * from './hooks/index.ts';
export { LoadSkeleton } from './ui/LoadSkeleton.tsx';
export type { LoadSkeletonProps } from './ui/LoadSkeleton.tsx';
export { SkeletonRows } from './ui/SkeletonRows.tsx';
export type { SkeletonColumn, SkeletonRowsProps } from './ui/SkeletonRows.tsx';
