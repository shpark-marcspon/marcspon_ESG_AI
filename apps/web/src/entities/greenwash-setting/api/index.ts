// 그린워싱 AI 설정 판 api 칸의 공개 표면(실서버 AD2R). 시험용 가짜 서버(testing.ts)는 여기서 내보내지 않는다(시험만 직접 가져온다).
export {
  GREENWASH_SETTING_PAGE,
  createGreenwashSettingServerPort,
} from './server.ts';
export type {
  CreateGreenwashSettingServerPortOptions,
  GreenwashSettingServerPort,
  SettingApplyOutcome,
  SettingCreateOutcome,
  SettingDefaultOutcome,
  SettingListOutcome,
  SettingOutcome,
} from './server.ts';
