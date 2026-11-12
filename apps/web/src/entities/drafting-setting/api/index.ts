// 원고작성 AI 설정 판 api 칸의 공개 표면(밴드 RPA3). 시험용 가짜 서버(testing.ts)는 여기서 내보내지 않는다(시험만 직접 가져온다).
export {
  DRAFTING_SETTING_PAGE,
  createDraftingSettingServerPort,
} from './server.ts';
export type {
  CreateDraftingSettingServerPortOptions,
  SettingApplyOutcome,
  SettingCreateInput,
  SettingCreateOutcome,
  SettingListOutcome,
  DraftingSettingServerPort,
} from './server.ts';
