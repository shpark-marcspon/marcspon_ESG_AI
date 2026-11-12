// 중대성평가 틀이 router context 로 받는 것의 꼴(밴드 IRW1 ② — 데이터 검증 app/dataverify/runtime.ts 꼴). 타입만 둔다 — app/router.tsx 가
// `import type` 으로 가져와도 진입 청크에 아무것도 들지 않는다. 값(실어댑터)은 게으른 틀 모듈(MaterialityRoutes.tsx)이 기본값으로 가져온다.
import type {
  MaterialityServerDeps,
  MaterialityStore,
} from '../../entities/materiality/api/index.ts';

/** 틀이 처음 그려질 때 한 번 부른다(세션 Api 로). 시험은 가짜 서버를 앞에 둔 실어댑터를 넣는다. 목 저장소는 없다. */
export type CreateMaterialityStore = (
  deps: MaterialityServerDeps,
) => MaterialityStore;

/**
 * 라우터 하나에 하나 있는 중대성평가의 메모리 칸(createAppRouter 가 만든다).
 * - control: 틀이 처음 그려질 때 만든 저장소. 화면 사이 이동에서 살아남는다. 저장소가 쥔 「아직 만들어지지 않은 [다시 실행] + 열쇠」가
 *   유일한 기억이고, 세션이 끝나면 비운다(store.forget).
 */
export interface MaterialityRuntime {
  control: { store: MaterialityStore } | null;
}

/** router context 의 중대성평가 칸. createMaterialityStore 는 시험용 선택 인자(없으면 틀 모듈의 기본값 — 실어댑터). */
export interface MaterialityRouterContext {
  createMaterialityStore?: CreateMaterialityStore;
  materiality: MaterialityRuntime;
}
