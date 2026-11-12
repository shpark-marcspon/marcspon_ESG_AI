// 그린워싱 목 저장소의 공개 표면(밴드 FW1b ①). app/greenwash(GreenwashRoutes.tsx 의 기본 저장소와 경로 표 시험)와 화면 폴더의 시험만 가져온다(app/guards/layers.test.ts).
// 같은 api 칸의 store.ts 와 model/index.ts 만 가져오고 패키지는 쓰지 않는다. 값은 모두 지어낸 것이다.
export {
  MOCK_DEFAULT_TERMS,
  MOCK_DOCUMENTS,
  MOCK_FILES,
  MOCK_SCENARIOS,
  MockUploadRejected,
  createMockStore,
  effectiveCounts,
  nextEdits,
  step,
} from './mockStore.ts';
export type {
  MockScenario,
  MockStoreControl,
  MockStoreOptions,
} from './mockStore.ts';
