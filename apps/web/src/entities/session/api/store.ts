// 세션 저장소(밴드 LG1 ①). 토큰 보관, 모든 요청에 Bearer, 444 면 refresh 한 번, 로그인·복원·비밀번호 바꾸기·로그아웃.
// 통신 함수(send)와 보관소(storage)는 쓰는 쪽(app/)이 넣는다 — 이 칸은 전역 통신·보관소를 모른다(N8).
//
// 토큰 보관(감독 판단 2): access 는 메모리에만, refresh 는 보관소(sessionStorage) 키 하나에. 세션을 비우면 둘 다 지운다.
//   남는 틈: 「탭 복제」는 sessionStorage 를 복사해 두 탭이 같은 refresh 로 rotate 를 겨룬다 → 서버가 재사용으로 보고 계보를 끊어
//   두 탭 다 로그아웃된다(받아들임). 토큰·임시 비밀번호는 로그로 내지 않는다.
// 서버 계약(발주서 §1): access 가 틀리거나 만료면 444 TOKEN_NOT_VALID(401 이 아니다). refresh 는 rotate — 옛 것은 즉시 죽고,
//   죽은 것을 다시 내면 그 계보 전부가 끊긴다. 그래서 refresh 는 한 번에 하나만 낸다:
//   - refreshOnce: 진행 중인 refresh 약속 하나를 같이 쓴다(동시 444 셋이어도 refresh 한 번). 부팅 복원도 이것을 쓴다(N3).
//     rotate 된 refresh 는 약속이 풀리기 전에 보관소에 쓴다.
//   - ready: 부팅 복원 약속 하나를 기억한다. StrictMode 의 이중 effect·가드 여럿이 불러도 refresh 는 한 번이다.
//   - 444 를 받은 요청이 보낸 access 가 이미 바뀌었으면(다른 요청이 refresh 를 끝냈으면) refresh 하지 않고 새 access 로 다시 보낸다.
// 가로채기 범위(critic 1 반영 B3): /auth/*(login·refresh·revoke)는 감싸지 않은 클라이언트로 보낸다. 다시 보낼 때는
//   Authorization 을 새 access 로 바꿔 단 요청을 보낸다(보내기 전에 clone 해 둔 원 요청에서).
// 401·403 은 refresh 하지 않는다. 403 PASSWORD_CHANGE_REQUIRED 는 사용자를 isInitial 로 표시한다(가드가 /password 로 — N5).
// 고객사 로그인의 companySubdomain 은 보내지 않는다(MARC-ENT-283 — 서버가 아이디로 찾는 바꿈은 백엔드 몫).
import { asFailure, createApi } from '../../../shared/api/index.ts';
import type { Api, ApiFailure } from '../../../shared/api/index.ts';
import { REFRESH_STORAGE_KEY } from '../model/index.ts';
import type {
  SessionNotice,
  SessionState,
  SessionUser,
  TokenPair,
} from '../model/index.ts';

/** 통신 함수. app/ 이 전역 것을 넣고 시험이 가짜를 넣는다. */
export type SessionSend = (request: Request) => Promise<Response>;

/** refresh 토큰 보관소(sessionStorage 의 꼴 중 셋). */
export interface SessionStorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface CreateSessionStoreOptions {
  send: SessionSend;
  storage: SessionStorageLike;
  /** 서버의 바탕 주소. 기본 '/api'(같은 출처, MARC-ENT-198). */
  baseUrl?: string;
  /** 로그아웃·세션 끝내기의 revoke 를 기다리는 상한(ms). 넘으면 결과를 기다리지 않고 비운다. 기본 REVOKE_TIMEOUT_MS. */
  revokeTimeoutMs?: number;
  /** 부팅 복원(refresh·/users/me)을 기다리는 상한(ms). 넘으면 안 로그인으로(보관소의 refresh 는 남긴다). 기본 RESTORE_TIMEOUT_MS. */
  restoreTimeoutMs?: number;
}

/** revoke 를 기다리는 상한(5초 — ② 검증 사소 지적 5, 감독). 서버가 답하지 않아도 화면이 로그인 상태에 묶이지 않게. */
export const REVOKE_TIMEOUT_MS = 5_000;
/** 부팅 복원을 기다리는 상한(10초 — 가지 리뷰 지적 2, 감독). 서버가 답하지 않아도 화면이 빈 채로 묶이지 않게. */
export const RESTORE_TIMEOUT_MS = 10_000;

export type LoginOutcome =
  | { ok: true }
  /** invalid = 아이디·비밀번호가 맞지 않음(422 꼴 틀림도 — MARC-ENT-282), locked = 5번 틀려 10분 잠김, failed = 그 밖(연결·5xx). */
  | { ok: false; reason: 'invalid' | 'locked' | 'failed' };

export type PasswordChangeOutcome =
  | { ok: true }
  /** rejected = 서버가 새 비밀번호를 받지 않음, failed = 그 밖(연결·5xx), ended = 세션이 끝나 로그인 화면으로(안내는 상태의 notice). */
  | { ok: false; reason: 'rejected' | 'failed' | 'ended' };

export interface SessionStore {
  getSnapshot(): SessionState;
  subscribe(listener: () => void): () => void;
  /** 부팅 복원(보관소의 refresh 로, 한 번만). 풀리면 상태가 restoring 이 아니다. */
  ready(): Promise<void>;
  login(username: string, password: string): Promise<LoginOutcome>;
  /** 첫 로그인 비밀번호 바꾸기. 지금 비밀번호는 로그인 때 친 임시 비밀번호(메모리)를 보낸다(감독 판단 1 (가)). */
  changePassword(newPassword: string): Promise<PasswordChangeOutcome>;
  /** 로그아웃: revoke(결과 무시) → 세션 비움. */
  logout(): Promise<void>;
  /** 세션을 끝낸다: revoke(결과 무시) → 세션 비움 → 로그인 화면에 notice. */
  end(notice: SessionNotice | null): Promise<void>;
  /** 로그인 때 친 임시 비밀번호가 메모리에 있는가(isInitial 일 때만 든다). */
  hasTemporaryPassword(): boolean;
  /** 로그인 화면의 안내를 내린다. */
  dismissNotice(): void;
  /**
   * 부팅 복원을 한 번 더(로그인 화면의 unreachable [다시 시도]). 보관소에 refresh 가 있을 때만 — 없으면 안내를 내린다.
   * 상태를 restoring 으로 되돌리지 않는다(로그인 화면이 그대로 있다). 진행 중이면 그 약속을 같이 쓴다.
   */
  retryRestore(): Promise<void>;
  /** 세션이 실린 클라이언트(Bearer, 444 에 refresh 한 번). 다른 화면이 서버를 부를 때 쓴다. */
  api: Api;
}

const AUTH_PATH = /\/auth\/[^/]+$/;

/** refresh 한 번의 결과(refreshOnce). */
type RefreshResult = 'ok' | 'rejected' | 'unreachable';

const codeOf = (failure: ApiFailure) =>
  failure.kind === 'api' ? failure.code : null;

function withBearer(request: Request, access: string | null): Request {
  if (access === null) return request;
  const headers = new Headers(request.headers);
  headers.set('Authorization', `Bearer ${access}`);
  return new Request(request, { headers });
}

export function createSessionStore({
  send,
  storage,
  baseUrl = '/api',
  revokeTimeoutMs = REVOKE_TIMEOUT_MS,
  restoreTimeoutMs = RESTORE_TIMEOUT_MS,
}: CreateSessionStoreOptions): SessionStore {
  // /auth/* 는 가로채지 않는 클라이언트로(B3).
  const plain = createApi({ baseUrl, fetch: send }).client;
  let access: string | null = null;
  let temporary: string | null = null;
  let state: SessionState = { status: 'restoring' };
  const listeners = new Set<() => void>();
  let restoring: Promise<void> | null = null;
  let retrying: Promise<void> | null = null;
  let refreshing: Promise<RefreshResult> | null = null;
  // 세션을 비울 때마다 늘린다: 비운 뒤에 끝난 요청이 토큰·사용자를 되살리지 않게.
  let generation = 0;

  const set = (next: SessionState) => {
    state = next;
    for (const listener of listeners) listener();
  };

  // 보관소는 사생활 창 등에서 던질 수 있다. 던지면 「없음」으로 본다(그러면 새로고침마다 로그인부터).
  const readRefresh = () => {
    try {
      return storage.getItem(REFRESH_STORAGE_KEY);
    } catch {
      return null;
    }
  };
  const writeRefresh = (refresh: string) => {
    try {
      storage.setItem(REFRESH_STORAGE_KEY, refresh);
    } catch {
      // 못 쓰면 이 탭의 메모리 access 만으로 간다.
    }
  };
  const removeRefresh = () => {
    try {
      storage.removeItem(REFRESH_STORAGE_KEY);
    } catch {
      // 지우지 못하면 다음 복원의 refresh 가 444 로 끝난다.
    }
  };

  const savePair = (pair: TokenPair) => {
    writeRefresh(pair.refresh);
    access = pair.access;
  };

  /**
   * 안 로그인으로. 메모리(access·임시 비밀번호)와 진행 중인 refresh 약속을 버린다 — 로그아웃·다시 로그인 뒤에 옛 약속의 결과를
   * 받지 않게(가지 리뷰 지적 4). keepRefresh 면 보관소의 refresh 는 남긴다(연결 끊김·복원 상한 — 다음 복원이 다시 낸다).
   */
  const signOut = (
    notice: SessionNotice | null,
    { keepRefresh = false } = {},
  ) => {
    generation++;
    access = null;
    temporary = null;
    refreshing = null;
    if (!keepRefresh) removeRefresh();
    set({ status: 'signedOut', notice });
  };
  const clear = (notice: SessionNotice | null) => signOut(notice);

  /**
   * refresh 한 번. 결과: ok / rejected(444 — 서버가 refresh 를 받지 않음, 세션을 비웠다) / unreachable(연결 끊김·5xx·꼴 밖의 답).
   * unreachable 이면 세션을 비우지 않고 보관소의 refresh 를 그대로 둔다 — 다음 요청이 다시 refresh 한다(가지 리뷰 지적 1).
   * 응답을 잃은 rotate 였다면 다음 refresh 가 재사용 탐지로 444 → 비움이라 끝 상태가 같고, 아니었다면 세션이 산다.
   */
  const refreshOnce = (): Promise<RefreshResult> => {
    if (refreshing) return refreshing;
    const started = generation;
    const attempt = (async (): Promise<RefreshResult> => {
      const refresh = readRefresh();
      if (refresh === null) {
        clear('expired');
        return 'rejected';
      }
      try {
        const { data } = await plain.POST('/auth/refresh', {
          body: { refresh },
        });
        if (started !== generation) return 'rejected';
        if (!data) throw { kind: 'network' } satisfies ApiFailure;
        savePair(data);
        return 'ok';
      } catch (error) {
        if (started !== generation) return 'rejected';
        const failure = asFailure(error);
        if (failure.kind === 'api' && failure.status === 444) {
          clear('expired');
          return 'rejected';
        }
        return 'unreachable';
      }
    })();
    refreshing = attempt;
    void attempt.finally(() => {
      // 그사이 세션을 비웠으면(signOut 이 이미 지움) 다른 약속을 지우지 않는다.
      if (refreshing === attempt) refreshing = null;
    });
    return attempt;
  };

  /** 403 PASSWORD_CHANGE_REQUIRED 면 사용자를 isInitial 로 표시한다. */
  const notePasswordRequired = async (response: Response) => {
    const body: unknown = await response
      .clone()
      .json()
      .catch(() => null);
    const code = (body as { error?: { code?: unknown } } | null)?.error?.code;
    if (code === 'PASSWORD_CHANGE_REQUIRED' && state.status === 'signedIn')
      set({ status: 'signedIn', user: { ...state.user, isInitial: true } });
  };

  const authed: SessionSend = async (request) => {
    if (AUTH_PATH.test(new URL(request.url).pathname)) return send(request);
    const spare = request.clone();
    const used = access;
    const started = generation;
    const first = await send(withBearer(request, used));
    if (first.status === 403) await notePasswordRequired(first);
    if (first.status !== 444) return first;
    // 보내는 사이에 세션이 비었으면(로그아웃·잠김·처음부터) 늦게 온 444 로 refresh 하지 않는다 — 그 안내를 「만료」로 덮지 않게.
    if (started !== generation) return first;
    const renewed =
      access !== null && access !== used ? 'ok' : await refreshOnce();
    // refresh 를 못 했으면(444 로 비웠거나 닿지 못했거나) 원 444 를 그대로 돌려준다.
    if (renewed !== 'ok' || access === null) return first;
    const second = await send(withBearer(spare, access));
    if (second.status === 403) await notePasswordRequired(second);
    if (second.status === 444 && started === generation) clear('expired');
    return second;
  };
  const api = createApi({ baseUrl, fetch: authed });

  /**
   * GET /users/me 로 사용자를 싣는다. 서버가 거절하면(401 USER_UNAVAILABLE 등) 세션을 비우고(그 notice 로) 거짓.
   * keepOnUnreachable 이면 연결 끊김·5xx·꼴 밖의 답에는 보관소의 refresh 를 남기고 안 로그인으로(부팅 복원 — 지적 1).
   */
  const loadUser = async (
    onFailure: SessionNotice | null,
    { keepOnUnreachable = false } = {},
  ) => {
    const started = generation;
    let user: SessionUser | undefined;
    let failure: ApiFailure | null = null;
    try {
      ({ data: user } = await api.client.GET('/users/me'));
    } catch (error) {
      failure = asFailure(error);
    }
    if (started !== generation) return false;
    if (!user) {
      const unreachable =
        failure === null || failure.kind !== 'api' || failure.status >= 500;
      if (keepOnUnreachable && unreachable)
        signOut('unreachable', { keepRefresh: true });
      else clear(onFailure);
      return false;
    }
    set({ status: 'signedIn', user });
    return true;
  };

  const restore = async () => {
    if (readRefresh() === null) {
      set({ status: 'signedOut', notice: null });
      return;
    }
    const refreshed = await refreshOnce();
    // 닿지 못했으면 안 로그인으로 두되 보관소의 refresh 는 남기고 unreachable 안내(다음 새로고침·[다시 시도]가 다시 복원한다).
    // unreachable 은 그 세대가 그대로일 때만 온다(refreshOnce) — 상한·로그인이 먼저 왔으면 여기 닿지 않는다.
    if (refreshed === 'unreachable' && state.status !== 'signedIn')
      signOut('unreachable', { keepRefresh: true });
    if (refreshed !== 'ok') return;
    // 복원 중 401 USER_UNAVAILABLE(계정 꺼짐 등)도 세션을 비우고 로그인 화면으로(N5).
    await loadUser('expired', { keepOnUnreachable: true });
  };

  /**
   * 부팅 복원에 상한을 씌운다. 넘으면 unreachable 안내로 안 로그인(보관소 refresh 는 남김) — 늦게 온 결과는 generation 이 막는다.
   * [다시 시도](retryRestore)도 이것을 쓴다: 그때는 상태가 signedOut 이라 세대로 가른다(그사이 로그인·비움이 있었으면 건드리지 않음).
   */
  const restoreWithin = async () => {
    const started = generation;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const late = new Promise<void>((resolve) => {
      timer = setTimeout(() => {
        if (started === generation && state.status !== 'signedIn')
          signOut('unreachable', { keepRefresh: true });
        resolve();
      }, restoreTimeoutMs);
    });
    try {
      await Promise.race([restore(), late]);
    } finally {
      clearTimeout(timer);
    }
  };

  const end = async (notice: SessionNotice | null) => {
    const refresh = readRefresh();
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      if (refresh !== null)
        await Promise.race([
          plain.POST('/auth/revoke', { body: { refresh } }),
          new Promise<void>((resolve) => {
            timer = setTimeout(resolve, revokeTimeoutMs);
          }),
        ]);
    } catch {
      // revoke 결과와 무관하게 비운다(B2). 이미 낸 access 는 서버에서 만료(30분)까지 통한다.
    } finally {
      clearTimeout(timer);
      clear(notice);
    }
  };

  return {
    getSnapshot: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => void listeners.delete(listener);
    },
    ready: () => {
      restoring ??= restoreWithin();
      return restoring;
    },
    login: async (username, password) => {
      const started = generation;
      let pair: TokenPair | undefined;
      try {
        // companySubdomain 은 보내지 않는다(MARC-ENT-283).
        ({ data: pair } = await plain.POST('/auth/login', {
          body: { username, password },
        }));
      } catch (error) {
        const code = codeOf(asFailure(error));
        if (code === 'ACCOUNT_LOCKED') return { ok: false, reason: 'locked' };
        if (code === 'INVALID_CREDENTIALS' || code === 'VALIDATION_ERROR')
          return { ok: false, reason: 'invalid' };
        return { ok: false, reason: 'failed' };
      }
      if (!pair || started !== generation)
        return { ok: false, reason: 'failed' };
      // 그사이 돌던 [다시 시도]의 refresh·/users/me 가 늦게 와 이 로그인을 덮지 않게 세대를 넘긴다.
      generation++;
      refreshing = null;
      savePair(pair);
      temporary = pair.isInitial ? password : null;
      return (await loadUser(null)) ?
          { ok: true }
        : { ok: false, reason: 'failed' };
    },
    changePassword: async (newPassword) => {
      if (temporary === null) {
        await end('relogin');
        return { ok: false, reason: 'ended' };
      }
      let pair: TokenPair | undefined;
      try {
        ({ data: pair } = await api.client.POST('/users/me/password', {
          body: { currentPassword: temporary, newPassword },
        }));
      } catch (error) {
        // 444 로 refresh 까지 실패했으면 authed 가 이미 세션을 비웠다.
        if (state.status !== 'signedIn') return { ok: false, reason: 'ended' };
        const code = codeOf(asFailure(error));
        // 서버 message(한다체)는 보이지 않는다. 화면이 code 로 해요체 글을 띄운다(감독 판단 5).
        // 422 VALIDATION_ERROR(새 비밀번호의 꼴 — 가지 리뷰 지적 7)도 같은 글.
        if (code === 'PASSWORD_REJECTED' || code === 'VALIDATION_ERROR')
          return { ok: false, reason: 'rejected' };
        const notice: SessionNotice | undefined =
          code === 'CURRENT_PASSWORD_MISMATCH' ? 'relogin'
          : code === 'ACCOUNT_LOCKED' ? 'locked'
          : code === 'USER_UNAVAILABLE' ? 'expired'
          : undefined;
        if (notice === undefined) return { ok: false, reason: 'failed' };
        await end(notice);
        return { ok: false, reason: 'ended' };
      }
      if (!pair || state.status !== 'signedIn')
        return { ok: false, reason: 'failed' };
      savePair(pair);
      temporary = null;
      set({
        status: 'signedIn',
        user: { ...state.user, isInitial: pair.isInitial },
      });
      return { ok: true };
    },
    logout: () => end(null),
    end,
    hasTemporaryPassword: () => temporary !== null,
    dismissNotice: () => {
      if (state.status === 'signedOut' && state.notice !== null)
        set({ status: 'signedOut', notice: null });
    },
    retryRestore: () => {
      if (state.status !== 'signedOut') return Promise.resolve();
      if (readRefresh() === null) {
        if (state.notice !== null) set({ status: 'signedOut', notice: null });
        return Promise.resolve();
      }
      retrying ??= restoreWithin().finally(() => {
        retrying = null;
      });
      return retrying;
    },
    api,
  };
}
