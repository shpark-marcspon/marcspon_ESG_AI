// 데이터 검증 틀이 router context 로 받는 것의 꼴(밴드 DV2a ② — 영문번역 app/translation/runtime.ts 꼴). 타입만 둔다 — app/router.tsx 가
// `import type` 으로 가져와도 진입 청크에 아무것도 들지 않는다. 값(실어댑터)은 게으른 틀 모듈(DataverifyRoutes.tsx)이 기본값으로 가져온다.
import type {
  DataverifyServerDeps,
  DataverifyStore,
} from '../../entities/dataverify/api/index.ts';

/** 틀이 처음 그려질 때 한 번 부른다(세션 Api 로). 시험은 가짜 서버를 앞에 둔 실어댑터를 넣는다. 목 저장소는 없다. */
export type CreateDataverifyStore = (
  deps: DataverifyServerDeps,
) => DataverifyStore;

/**
 * 라우터 하나에 하나 있는 데이터 검증의 메모리 칸(createAppRouter 가 만든다).
 * - control: 틀이 처음 그려질 때 만든 저장소. 화면 사이 이동에서 살아남는다. 저장소가 쥔 「아직 만들어지지 않은 본문 + 열쇠」가
 *   유일한 기억이고, 세션이 끝나면 비운다(store.forget).
 */
export interface DataverifyRuntime {
  control: { store: DataverifyStore } | null;
}

/** router context 의 데이터 검증 칸. createDataverifyStore 는 시험용 선택 인자(없으면 틀 모듈의 기본값 — 실어댑터). */
export interface DataverifyRouterContext {
  createDataverifyStore?: CreateDataverifyStore;
  dataverify: DataverifyRuntime;
}
