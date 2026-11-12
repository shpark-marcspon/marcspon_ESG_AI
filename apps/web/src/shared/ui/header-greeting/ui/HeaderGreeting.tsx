// 머리 줄 오른쪽의 인사말 + 글 단추 [로그아웃](밴드 AD1 ① — critic 1 반영 B2). 어드민 틀과 그린워싱 틀이 같이 쓴다.
// 꼴: 디자인 원문(2026-10-18, sid:MARC-TICK-72 노트) — 인사말 오른쪽 c-textbtn 꼴, 초점 2px border-secondary(Button 의 초점 그대로).
//   [로그아웃]은 md(14/500·36 — 디자인 리뷰 C6, sid:MARC-ISSUE-189). action 은 인사말과 [로그아웃] 사이의 자리 하나(밴드 SV1 — 그린워싱 머리 「관리자 화면」).
// 세션·라우터를 모르는 표시 부품이다: onLogout 은 쓰는 틀이 세션의 logout 을 넘기고, 이동은 그 틀의 가드가 한다.
// onLogout 의 약속이 끝날 때까지 단추는 도는 표시 — 두 번 눌러도 한 번만 부른다.
import * as React from 'react';

import { Button } from '../../button/index.ts';
import { PARTS_TEXT } from '../../text.ts';

export interface HeaderGreetingProps {
  /** 틀마다 다른 인사말(「운영 관리자님 안녕하세요」·「담당자님 안녕하세요」). */
  greeting: string;
  onLogout: () => Promise<void>;
  /** 단추 글. 주지 않으면 문구 표(shared/ui/text.ts)의 값. */
  logoutLabel?: string;
  /** 인사말과 [로그아웃] 사이에 그릴 것. 없으면 인사말과 [로그아웃]뿐이다. */
  action?: React.ReactNode;
}

function HeaderGreeting({
  greeting,
  onLogout,
  logoutLabel = PARTS_TEXT.logout,
  action,
}: HeaderGreetingProps) {
  const [pending, setPending] = React.useState(false);
  // 불러오는 중인 Button 은 누를 수 없다 — 끝나기 전의 두 번째 누름은 닿지 않는다.
  const logout = () => {
    setPending(true);
    // 실패해도 단추는 다시 살린다(로그아웃 실패는 세션 저장소가 맡는다 — 처리 안 된 거절을 남기지 않는다).
    void onLogout()
      .catch(() => {})
      .finally(() => setPending(false));
  };
  return (
    <div className="flex items-center gap-2">
      <span className="text-style-pre-body-04 text-text-secondary">
        {greeting}
      </span>
      {action}
      <Button
        variant="text"
        size="md"
        className="underline"
        loading={pending}
        onClick={logout}
      >
        {logoutLabel}
      </Button>
    </div>
  );
}
HeaderGreeting.displayName = 'HeaderGreeting';

export { HeaderGreeting };
