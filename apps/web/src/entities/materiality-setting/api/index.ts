// 중대성평가 IRO AI 설정 판 api 칸의 공개 표면(밴드 IRA2). 시험용 가짜 서버(testing.ts)는 여기서 내보내지 않는다(시험만 직접 가져온다).
export {
  MATERIALITY_SETTING_PAGE,
  createMaterialitySettingServerPort,
} from './server.ts';
export type {
  CreateMaterialitySettingServerPortOptions,
  SettingApplyOutcome,
  SettingCreateInput,
  SettingCreateOutcome,
  SettingListOutcome,
  MaterialitySettingServerPort,
} from './server.ts';
