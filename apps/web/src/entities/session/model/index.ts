// 세션 model 칸의 공개 표면(밴드 LG1 ①). 순수 함수와 타입만 있다(app/guards/layers.test.ts).
export {
  REFRESH_STORAGE_KEY,
  SESSION_PATHS,
  areaOf,
  guardOf,
  landingOf,
} from './session.ts';
export type {
  GuardDecision,
  SessionArea,
  SessionKind,
  SessionNotice,
  SessionPath,
  SessionState,
  SessionUser,
  TokenPair,
} from './session.ts';
