// 그린워싱 AI 설정 판 model 칸의 공개 표면(밴드 AD2R ①, 대상 단어 초안 AS3b ①).
export {
  CRITERION_IDS,
  CRITERION_TEXT_MAX,
  DEFAULT_KEY,
  SETTING_STATUSES,
  criterionTextProblem,
  firstPick,
  idOut,
  saveBody,
  versionRows,
} from './setting.ts';
export type {
  Setting,
  SettingCreate,
  SettingCriteria,
  SettingDefault,
  SettingList,
  SettingRow,
  SettingStatus,
  SettingSummary,
  SettingTerm,
  VersionBadge,
  VersionRow,
} from './setting.ts';
export {
  TERMS_CODES,
  TERMS_MAX,
  TERM_CHARS,
  addTerm,
  addedTexts,
  refusedRow,
  removeTerms,
  switchTerm,
  termChanges,
  termKey,
  termProblem,
  termsBase,
  termsBlocked,
  termsChanged,
  termsCount,
  termsRefusal,
} from './terms.ts';
export type {
  Term,
  TermProblem,
  TermsChangedWords,
  TermsCode,
  TermsDraft,
} from './terms.ts';
export { FLOW_KEYS, flowNodes } from './flow.ts';
export type { FlowKey, FlowNode } from './flow.ts';
