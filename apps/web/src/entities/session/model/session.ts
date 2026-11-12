// 로그인 세션의 꼴과 첫 화면·가드의 순수 함수(밴드 LG1 ①). React·DOM·통신을 모른다.
// 계약 타입(TokenPairOut·UserMeOut)은 shared/api 가 다시 내보낸 것을 타입으로만 가져온다.
//
// 가드 표(발주서 §3, critic 1 반영 B2):
//   상태              업무 주소(/greenwash/**·/admin/**)   /login       /password
//   복원 중           기다림                                기다림       기다림
//   안 로그인         /login                                그대로       /login
//   isInitial         /password                             /password    그대로
//     └ 임시 비밀번호가 메모리에 없음(새로고침 등) → 세션을 끝내고 /login(안내 한 줄)
//   admin             /admin/**·/greenwash/** 그대로        첫 화면      첫 화면
//   service           /admin/** → /greenwash                첫 화면      첫 화면
// 운영 관리자는 그린워싱도 연다(밴드 SV1, sid:MARC-ENT-286 — 읽기만은 그린워싱 틀이 맡는다). 첫 화면은 그대로 /admin/accounts.
// `/` 와 모르는 주소는 늘 첫 화면으로 간다. 로그인 뒤 원래 주소로 돌아가기는 하지 않는다(열린 리다이렉트 막음 — 감독 판단 7).
import type { Schemas } from '../../../shared/api/index.ts';

/** 로그인·refresh·비밀번호 바꾸기가 내는 토큰 짝. */
export type TokenPair = Schemas['TokenPairOut'];
/** GET /users/me 의 사용자. */
export type SessionUser = Schemas['UserMeOut'];
export type SessionKind = SessionUser['kind'];

/** 로그인 화면이 띄우는 한 줄 안내의 까닭: 세션 만료 · 잠김 · 처음부터 다시 로그인 · 부팅 복원이 서버에 닿지 못함. */
export type SessionNotice = 'expired' | 'locked' | 'relogin' | 'unreachable';

/** 세션의 상태. 임시 비밀번호는 여기에 싣지 않는다(useSession 스냅샷에 들지 않게 — N4). */
export type SessionState =
  | { status: 'restoring' }
  | { status: 'signedOut'; notice: SessionNotice | null }
  | { status: 'signedIn'; user: SessionUser };

/** refresh 토큰을 두는 sessionStorage 키(하나). access 는 메모리에만 둔다(감독 판단 2). */
export const REFRESH_STORAGE_KEY = 'esg.session.refresh';

/** 세션이 정하는 주소들. 어드민 자리표·비밀번호 바꾸기 주소는 감독 판단 9 그대로(AD1 이 따른다). */
export const SESSION_PATHS = {
  login: '/login',
  password: '/password',
  adminHome: '/admin/accounts',
  serviceHome: '/greenwash',
} as const;
export type SessionPath = (typeof SESSION_PATHS)[keyof typeof SESSION_PATHS];

/** 주소의 갈래. other 는 `/` 와 모르는 주소(늘 첫 화면으로). */
export type SessionArea =
  | 'login'
  | 'password'
  | 'admin'
  | 'greenwash'
  | 'translation'
  | 'dataverify'
  | 'materiality'
  | 'ghg'
  | 'drafting'
  | 'other';

const under = (pathname: string, base: string) =>
  pathname === base || pathname.startsWith(`${base}/`);

export function areaOf(pathname: string): SessionArea {
  if (pathname === SESSION_PATHS.login) return 'login';
  if (pathname === SESSION_PATHS.password) return 'password';
  if (under(pathname, '/admin')) return 'admin';
  if (under(pathname, '/greenwash')) return 'greenwash';
  if (under(pathname, '/translation')) return 'translation';
  if (under(pathname, '/dataverify')) return 'dataverify';
  if (under(pathname, '/materiality')) return 'materiality';
  if (under(pathname, '/ghg')) return 'ghg';
  if (under(pathname, '/drafting')) return 'drafting';
  return 'other';
}

/** 그 상태의 첫 화면. 복원 중이면 null(아직 모른다). */
export function landingOf(state: SessionState): SessionPath | null {
  if (state.status === 'restoring') return null;
  if (state.status === 'signedOut') return SESSION_PATHS.login;
  if (state.user.isInitial) return SESSION_PATHS.password;
  return state.user.kind === 'admin' ?
      SESSION_PATHS.adminHome
    : SESSION_PATHS.serviceHome;
}

export type GuardDecision =
  | { kind: 'wait' }
  | { kind: 'stay' }
  | { kind: 'redirect'; to: SessionPath }
  /** isInitial 인데 임시 비밀번호가 메모리에 없다: revoke(결과 무시) → 세션 비움 → /login 에 안내(critic 1 반영 B2). */
  | { kind: 'relogin' };

/** 그 상태에서 그 주소를 열 수 있는가. temporaryPassword = 로그인 때 친 임시 비밀번호가 메모리에 있는가. */
export function guardOf(
  state: SessionState,
  pathname: string,
  { temporaryPassword }: { temporaryPassword: boolean },
): GuardDecision {
  const landing = landingOf(state);
  if (state.status === 'restoring' || landing === null) return { kind: 'wait' };
  if (state.status === 'signedIn' && state.user.isInitial && !temporaryPassword)
    return { kind: 'relogin' };
  // 그 상태가 머물 수 있는 갈래들. 그 밖은 모두 첫 화면으로.
  const own: readonly SessionArea[] =
    state.status === 'signedOut' ? ['login']
    : state.user.isInitial ? ['password']
    : state.user.kind === 'admin' ?
      [
        'admin',
        'greenwash',
        'translation',
        'dataverify',
        'materiality',
        'ghg',
        'drafting',
      ]
    : [
        'greenwash',
        'translation',
        'dataverify',
        'materiality',
        'ghg',
        'drafting',
      ];
  return own.includes(areaOf(pathname)) ?
      { kind: 'stay' }
    : { kind: 'redirect', to: landing };
}
