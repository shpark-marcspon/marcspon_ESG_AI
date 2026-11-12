// 그린워싱 틀이 router context 로 받는 것의 꼴(밴드 RT1 §1-3). 타입만 둔다 — app/router.tsx 가 `import type` 으로 가져와도 진입 청크에 아무것도 들지 않는다.
// 값(목 저장소·PDF 여는 구현)은 게으른 틀 모듈(GreenwashRoutes.tsx)이 기본값으로 정적으로 가져온다. 시험은 createAppRouter 에 가짜를 넣는다.
import type {
  GreenwashServerDeps,
  GreenwashStore,
} from '../../entities/greenwash/api/index.ts';
import type { OpenPdf } from '../../widgets/doc-viewer/index.ts';

/** 그린워싱 틀 경로의 search(router.tsx 의 검사 함수가 고른 것만 남는다. 모르는 값은 버린다). */
export interface GreenwashSearch {
  /** 목 실행 하나를 미리 만든다(id 는 늘 run-1). */
  mock?: 'running' | 'failed' | 'done';
  /** 진행을 시간으로 흘린다. */
  demo?: '1';
  /** 이 세션에서 만든 실행을 곧 끝낸다(e2e 가 GW-03 → 결과로 가는 길). */
  autofinish?: '1';
  /** 이 탭을 목 저장소로(데모 빌드에서만 먹는다 — 탭 표지 esg.gw.store=mock 에 적는다, 밴드 GW1R Q1). */
  store?: 'mock';
}

/** 그린워싱 틀이 쓰는 저장소와 그 수명. 목 저장소(MockStoreControl)와 실어댑터(틀이 감싼다)가 이 꼴을 맞춘다. */
export interface GreenwashStoreControl {
  store: GreenwashStore;
  start(): void;
  stop(): void;
  /** 이 탭의 기억(올린 File·센 쪽 수)을 비운다 — 로그아웃 때(실어댑터만, 밴드 GW1R Q11). */
  forget?(): void;
}

/** 저장소를 만들 때 틀이 넣는 것: 실어댑터의 의존(세션 Api·서명 PUT·쪽 세기)과 목 갈래 여부. */
export interface GreenwashStoreDeps extends GreenwashServerDeps {
  /** 목 저장소를 쓰는 탭인가(데모 빌드 context.admin.demos 이고 탭 표지가 있을 때만 참 — 틀이 정한다, 밴드 GW1R Q1). */
  mock: boolean;
}

/** 틀이 처음 그려질 때 한 번 부른다(그때의 search 와 의존으로). */
export type CreateGreenwashStore = (
  search: GreenwashSearch,
  deps: GreenwashStoreDeps,
) => GreenwashStoreControl;

/**
 * 라우터 하나에 하나 있는 그린워싱의 메모리 칸(createAppRouter 가 만든다). React context 를 새로 만들지 않고 router context 에 싣는다.
 * - control: 틀이 처음 그려질 때 만든 저장소. 화면 사이 이동과 틀이 다시 그려져도 살아남는다.
 * - confirmRunId: GW-04 [확정] → GW-05 로 넘기는 한 번 쓰는 표식(그 실행 id). 주소·search·history.state 어디에도 싣지 않는다 —
 *   새로고침·주소 공유·뒤로/앞으로로 확인 모달(05b)이 다시 뜨면 안 된다(확정은 되돌릴 수 없다).
 */
export interface GreenwashRuntime {
  control: GreenwashStoreControl | null;
  confirmRunId: string | null;
}

/** router context. openPdf·createStore 는 시험용 선택 인자(없으면 틀 모듈의 기본값). */
export interface AppRouterContext {
  openPdf?: OpenPdf;
  createStore?: CreateGreenwashStore;
  greenwash: GreenwashRuntime;
}
