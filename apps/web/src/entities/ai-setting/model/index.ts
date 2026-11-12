// AI 설정 model 칸의 공개 표면(밴드 AD2W — 모듈 슬롯 꼴·처음 고름·판 이름, ③④ 판 초안·글 셈). 순수 함수와 타입만 있다(app/guards/layers.test.ts).
//   slice 밖에서 부르는 이름만 둔다(slice 안은 정의 파일을 상대 경로로 — sid:MARC-ISSUE-278 닫는 조건, 검증 ④ B1).
//   옛 목 자료의 꼴(setting.ts·criteria.ts·assemble.ts)은 밴드 AD2W ① 에서 걷었다(sid:MARC-ISSUE-278 — 쓰는 곳 0).
export {
  DEFAULT_VERSION_KEY,
  firstPick,
  promptLabel,
  versionLabel,
  versionName,
} from './slot.ts';
export { codepoints, pyStrip } from './chars.ts';
export { promptFieldOf } from './fields.ts';
export {
  bodyOf,
  changedModels,
  changes,
  draftOf,
  modelErrors,
  nextNumber,
  promptErrors,
  saveFormProblems,
  withRoute,
} from './draft.ts';
export type {
  Changes,
  Draft,
  ModelDraft,
  ModelErrors,
  PromptErrors,
} from './draft.ts';
export type {
  AiSettingModule,
  AiSettingPort,
  FixedGroup,
  FlowProps,
  ModelSlot,
  ModuleComponent,
  ModuleDraftSlot,
  ModuleRefused,
  PromptEntry,
  PromptGroup,
  PromptModel,
  PromptModelOutcome,
  SaveOutcome,
  SlotAt,
  VersionPage,
  VersionPageOutcome,
  VersionRow,
  VersionStatus,
} from './slot.ts';
