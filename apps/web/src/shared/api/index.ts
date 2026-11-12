// 서버 호출 클라이언트의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(layers.test.ts 가 지킨다).
//
// ★ 연습용 선택이고 패칭 컨벤션이 아니다. 기반 밴드가 정한다.
//   이 폴더의 이름, 실패의 갈래, 「변경 뒤 조회 전부를 무효로」는 화면 하나를 서버에 이어 보려고 고른 것이다.
//   QueryClient 와 그 기본값(다시 시도, 신선한 시간, 버리는 시간)은 여기에 없다. 쓰는 화면이 만든다.
//
//   model/     실패의 갈래와 가름, 변경 뒤 무효로 표시할 키. React·DOM·통신을 모른다. 계약 타입을 다시 내보낸다
//   client.ts  층 밖의 어댑터 하나. createApi({ baseUrl, fetch? }) → openapi-fetch 클라이언트와 $api
//   hooks/     변경에 성공하면 조회를 무효로 표시하는 훅
//   ui/ 는 없다: 클라이언트에는 모양이 없다
//
// 계약 타입은 apps/api-py/generated/api.d.ts 에서 `import type` 으로만 온다(번들에 들지 않는다).
export * from './model/index.ts';
export * from './hooks/index.ts';
export { createApi } from './client.ts';
export type { Api, CreateApiOptions } from './client.ts';
