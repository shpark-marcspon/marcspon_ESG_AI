// 어드민 틀이 router context 로 받는 것의 꼴(밴드 AD1). 타입만 둔다 — app/router.tsx 가 `import type` 으로 가져와도 진입 청크에 아무것도 들지 않는다.

/**
 * 라우터 하나에 하나 있는 어드민의 메모리 칸(createAppRouter 가 만든다).
 * - demos: 데모 빌드인가(createAppRouter 의 demos 인자 && DEMOS). 그린워싱 틀이 목 저장소 탭을 가를 때 읽는다(app/greenwash).
 *   어드민 화면(AD-01·02·04·05)은 모두 실서버라 이 칸을 보지 않는다(AD-02 의 목 저장류는 밴드 AD2W 에서 걷음 — sid:MARC-ISSUE-278).
 */
export interface AdminRuntime {
  demos: boolean;
}

/** router context 의 어드민 칸. */
export interface AdminRouterContext {
  admin: AdminRuntime;
}
