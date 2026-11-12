// 세션과 경로를 잇는 자리(밴드 LG1 ②). app/router.tsx 가 정적으로 가져온다(진입 청크 — 가드는 화면보다 먼저 돈다).
//   - createAppSession: 세션 저장소에 전역 fetch 와 sessionStorage 를 넣는다(넣는 자리는 app/ — N8). 시험은 가짜를 준다.
//   - guardSession: 경로의 beforeLoad. 저장소의 기억된 부팅 복원(ready)을 기다린 뒤 가드 표(guardOf)대로 넘긴다(replace).
//     복원은 React effect 밖, 이 약속 하나로만 돈다(StrictMode 이중 effect 가 refresh 를 두 번 내지 않게 — 발주서 §2).
//     isInitial 인데 임시 비밀번호가 메모리에 없으면(새로고침) revoke → 세션 비움 → /login 에 「임시 비밀번호로 다시 로그인해 주세요」(critic 1 반영 B2).
//   - followSession: 세션이 바뀌면(로그인·로그아웃·만료·비밀번호 바꿈) 라우터를 무효로 해 가드를 다시 돌린다. 화면은 이동을 하지 않는다 —
//     로그인 뒤 첫 화면, 만료 뒤 /login 은 모두 가드가 정한다. 첫 복원은 가드가 기다리므로 넘긴다.
// 로그인 뒤 원래 주소로 돌아가기는 하지 않는다(열린 리다이렉트 막음 — 감독 판단 7).
import { redirect } from '@tanstack/react-router';

import { createSessionStore } from '../../entities/session/api/index.ts';
import type {
  SessionSend,
  SessionStorageLike,
  SessionStore,
} from '../../entities/session/api/index.ts';
import {
  SESSION_PATHS,
  areaOf,
  guardOf,
} from '../../entities/session/model/index.ts';
import type { SessionState } from '../../entities/session/model/index.ts';
import { appHref } from '../../shared/lib/address.ts';

/** router context 의 세션 칸. */
export interface SessionContext {
  session: SessionStore;
}

/** 시험용: 통신 함수·보관소·바탕 주소. */
export interface AppSessionOptions {
  send: SessionSend;
  storage: SessionStorageLike;
  baseUrl?: string;
}

/** 보관소를 부를 때마다 sessionStorage 를 읽는다(막힌 창에서 읽기 자체가 던져도 저장소가 받아 「없음」으로 본다). */
const browserStorage: SessionStorageLike = {
  getItem: (key) => globalThis.sessionStorage.getItem(key),
  setItem: (key, value) => globalThis.sessionStorage.setItem(key, value),
  removeItem: (key) => globalThis.sessionStorage.removeItem(key),
};

export function createAppSession(options?: AppSessionOptions): SessionStore {
  if (options) return createSessionStore(options);
  return createSessionStore({
    send: (request) => globalThis.fetch(request),
    storage: browserStorage,
    // 앱 뿌리 기준 절대 주소(쪽 주소 기준으로 풀리지 않게 — shared/lib/address.ts).
    baseUrl: appHref('api'),
  });
}

/** 가드가 세션을 끝내는 동안에는 followSession 이 라우터를 무효로 하지 않는다(가드가 이미 넘긴다). */
const ending = new WeakSet<SessionStore>();

export async function guardSession({
  context,
  location,
}: {
  context: SessionContext;
  location: { pathname: string };
}): Promise<void> {
  const { session } = context;
  await session.ready();
  const decision = guardOf(session.getSnapshot(), location.pathname, {
    temporaryPassword: session.hasTemporaryPassword(),
  });
  if (decision.kind === 'relogin') {
    ending.add(session);
    try {
      await session.end('relogin');
    } finally {
      ending.delete(session);
    }
    if (areaOf(location.pathname) !== 'login')
      throw redirect({ to: SESSION_PATHS.login, replace: true });
    return;
  }
  if (decision.kind === 'redirect')
    throw redirect({ to: decision.to, replace: true });
}

/**
 * `/` 와 모르는 주소(splat)의 beforeLoad: 늘 첫 화면으로 넘긴다. 주소의 갈래로 보지 않는다 —
 * /greenwash/xyz 는 갈래가 greenwash 라 guardSession 이면 「그대로」가 되어 빈 화면에 남는다.
 */
export const guardLanding = ({ context }: { context: SessionContext }) =>
  guardSession({ context, location: { pathname: '/' } });

/** 가드가 다시 봐야 하는 바뀜인가: 로그인 여부, 사용자, isInitial. 안내만 바뀐 것은 아니다. */
function changed(before: SessionState, after: SessionState): boolean {
  if (before.status !== after.status) return true;
  if (before.status !== 'signedIn' || after.status !== 'signedIn') return false;
  return (
    before.user.id !== after.user.id ||
    before.user.isInitial !== after.user.isInitial
  );
}

export function followSession(
  session: SessionStore,
  invalidate: () => void,
): () => void {
  let before = session.getSnapshot();
  return session.subscribe(() => {
    const after = session.getSnapshot();
    const was = before;
    before = after;
    if (was.status === 'restoring' || ending.has(session)) return;
    if (changed(was, after)) invalidate();
  });
}
