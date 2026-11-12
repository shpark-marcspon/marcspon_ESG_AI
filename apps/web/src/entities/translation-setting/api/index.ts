// 영문번역 AI 설정 판 api 칸의 공개 표면(밴드 TRA1). 시험용 가짜 서버(testing.ts)는 여기서 내보내지 않는다(시험만 직접 가져온다).
export {
  TRANSLATION_SETTING_PAGE,
  createTranslationSettingServerPort,
} from './server.ts';
export type {
  CreateTranslationSettingServerPortOptions,
  SettingApplyOutcome,
  SettingCreateInput,
  SettingCreateOutcome,
  SettingListOutcome,
  TranslationSettingServerPort,
} from './server.ts';
