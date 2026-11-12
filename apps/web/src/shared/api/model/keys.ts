// 변경 뒤에 무효로 표시할 조회의 키.
//
// openapi-react-query 는 조회의 키를 [메서드, 경로] 또는 [메서드, 경로, init] 으로 만든다(client.test.ts 의 「키의 꼴」이 단언한다).
// TanStack Query 의 무효화는 키의 앞부분이 같으면 걸리므로 ["get"] 하나로 조회 전부가 걸린다.
// 변경의 키는 ["post", 경로] 라 여기에 걸리지 않는다.
//
// 한계: 묶음을 고르지 않는다. 사업장을 하나 만들어도 기준정보까지 다시 받는다. 화면이 몇 개일 때의 연습용 선택이다.

/** 변경이 성공하면 이 키로 시작하는 조회를 전부 무효로 표시한다. */
export const INVALIDATE_AFTER_MUTATION = ['get'] as const;
