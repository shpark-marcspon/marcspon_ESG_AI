// 세션 api 칸의 공개 표면(밴드 LG1 ①). 시험용 가짜 서버(testing.ts)는 여기서 내보내지 않는다(시험만 직접 가져온다).
export {
  RESTORE_TIMEOUT_MS,
  REVOKE_TIMEOUT_MS,
  createSessionStore,
} from './store.ts';
export type {
  CreateSessionStoreOptions,
  LoginOutcome,
  PasswordChangeOutcome,
  SessionSend,
  SessionStorageLike,
  SessionStore,
} from './store.ts';
