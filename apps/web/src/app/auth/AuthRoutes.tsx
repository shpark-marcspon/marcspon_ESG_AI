// 로그인 경로 컴포넌트(밴드 LG1 ②). app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다 — 화면은 진입 청크에 들지 않는다.
// 화면(pages)은 라우터를 모른다: 세션 저장소는 router context 에서 꺼내 콜백으로 넘긴다. 이동은 하지 않는다 —
// 세션이 바뀌면 followSession 이 가드를 다시 돌려 첫 화면·/login 으로 넘긴다(app/auth/guard.ts).
import { getRouteApi } from '@tanstack/react-router';

import { useSession } from '../../entities/session/hooks/index.ts';
import { LoginScreen } from '../../pages/login/index.ts';
import { PasswordChangeScreen } from '../../pages/password-change/index.ts';

const rootApi = getRouteApi('__root__');

export function LoginRoute() {
  const { session } = rootApi.useRouteContext();
  const state = useSession(session);
  return (
    <LoginScreen
      notice={state.status === 'signedOut' ? state.notice : null}
      onLogin={session.login}
      onDismissNotice={session.dismissNotice}
      onRetry={session.retryRestore}
    />
  );
}

/** 첫 로그인 비밀번호 바꾸기(CM-02). 가드가 isInitial 이고 임시 비밀번호가 메모리에 있을 때만 들여보낸다. */
export function PasswordRoute() {
  const { session } = rootApi.useRouteContext();
  const state = useSession(session);
  // 로그아웃·만료로 세션이 비면 가드가 /login 으로 넘길 때까지 아무것도 그리지 않는다.
  if (state.status !== 'signedIn') return null;
  return (
    <PasswordChangeScreen
      username={state.user.username}
      onChange={session.changePassword}
      onLogout={() => void session.logout()}
    />
  );
}
