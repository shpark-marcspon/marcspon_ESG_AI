// 경로 표 하나(밴드 RT1). TanStack Router 를 코드로 적는다(파일 기반 라우팅·코드 생성은 쓰지 않는다).
//
//   /                               → 첫 화면으로 넘김(search 는 버린다. 옛 주소 ?view=·?screen=·?run= 은 넘기지 않는다 — 사용자 결정 2026-10-16)
//   /login  CM-01 로그인            /password  CM-02 첫 로그인 비밀번호 바꾸기
//   /admin                          어드민 틀(밴드 AD1) — /admin 은 /admin/accounts 로 넘김   /admin/accounts  AD-01 계정 관리(운영 관리자 첫 화면)
//   /admin/ai-settings/$module(?version=)   AD-02 AI 설정(module = 슬롯 id — 밴드 AM1. 옛 /admin/ai-settings 는 …/greenwash 로 넘김)
//   /admin/runs  AD-04 실행 기록   /admin/audit  AD-05 감사 기록
//   /admin/ai-settings/ghg          AI 설정 › 온실가스 탭 껍데기(밴드 AD7, sid:MARC-ENT-575 — 모듈 칸 $module 보다 고정 경로가 먼저 맞는다). 맨 주소는 …/ghg/index 로 넘김
//   /admin/ai-settings/ghg/index    탭 「온실가스 인덱스」(S19·S20 공통 풀 — 밴드 W12-0b1)   …/ghg/options  탭 「선택항목」(S18 자산/시설명 및 코드 — 밴드 W12-0a)
//                                   (옛 /admin/ghg-index·/admin/options 는 새 자리로 넘김 — 경로는 남기고 화면은 없다)
//                                   (AD-02·04·05 는 실서버 — 밴드 AD2R·AD4R·AD5R. AD-03 테스트 비교는 1차에서 뺐다 — OPW1 ②, sid:MARC-ENT-362.
//                                    그 옛 주소는 「그 밖」이라 첫 화면으로 간다)
//   /greenwash                      GW-01 목록              /greenwash/intro   GW-00 소개      /greenwash/new   GW-02·02a 새 점검
//   /greenwash/runs/$runId          GW-03 처리 상태          …/$runId/result    GW-04 결과      …/$runId/review  GW-05·05a~c 검토
//   /translation                    TR-01 번역 목록          /translation/new   TR-02 새 번역(밴드 TRW1a — 실서버)   /translation/intro  TR-00 번역 안내(밴드 TRP3)
//   /translation/documents/$documentId/batches/$batchKey(?part=all|ceo|story|general)   TR-03·04 묶음 화면
//   /translation/pdf/new            TR-P02 PDF 새 번역(밴드 TRW6)
//   /translation/documents/$documentId/batches/$batchKey/pdf/$runId   TR-P05 PDF 보기(밴드 TRW6)
//   /dataverify                     DV-01 검증 목록(빈 목록이면 DV-00 — 밴드 DV2b)   /dataverify/intro  DV-00   /dataverify/new  DV-02 새 검증(밴드 DV2a — 실서버)
//   /dataverify/runs/$runId         DV-03 처리 상태          …/$runId/result    DV-04·04a 결과
//   /materiality                    IR-01·01a 평가 목록(밴드 IRW1 — 실서버)   /materiality/intro  IR-00   /materiality/new  IR-02 새 평가(밴드 IRW2)
//   /materiality/runs/$runId        IR-03 처리 상태          …/$runId/result    IR-04·04a 결과(밴드 IRW1 — 실서버)
//   /ghg                            온실가스 — /ghg/dashboard 로 넘김(레이아웃 beforeLoad, 밴드 DB1)   /ghg/organization  S15 조직구조(밴드 W12-0a)
//   /ghg/dashboard(?year=)          S1 대시보드 온실가스 탭(밴드 DB1 — year 는 같은 거름, 기본 해는 전년도)
//   /ghg/organization/branches/new  S15 새 사업장           …/branches/$branchId  S15 사업장 상세
//   /ghg/inventory(?year=)          S2 온실가스 데이터 자리(밴드 W12-0b2 — 표는 W12-1)   …/inventory/index-settings(?year=)  S17 인덱스 설정
//                                   (year 는 정수로 거른다 — 없거나 고를 수 있는 해 밖이면 경로 컴포넌트가 올해로 replace)
//   /ghg/scope3(?year=)             S3-01 Scope 3 첫 화면(밴드 S3W1 — year 는 같은 거름, 기본 해는 전년도)
//   /drafting                       RP-01 보고서 프로젝트 목록(밴드 RPW1 — 빈 목록이면 빈 상태 그 자리)   /drafting/new  RP-02 새 프로젝트
//   /drafting/intro                 RP-00 작성 안내(밴드 RPW6 — RP-01 머리 「작성 안내」 링크로만, 빈 목록 넘김 없음)
//   /drafting/projects/$projectId/document   RP-02 전년도 보고서 다시 올리기
//   /drafting/projects/$projectId/outline    RP-03 목차 설정(밴드 RPW1 ②)
//   /drafting/projects/$projectId/runs/$runId   RP-04 개조식 초안(진행·결과 — 밴드 RPW1 ②③)
//                                   ($projectId·$runId 는 글자 그대로 — 정수로 바꾸는 자리는 entities/drafting/model idOf 하나)
//   /dev/viewer /dev/table /dev/api /dev/parts   데모 넷 — 개발 서버이거나 VITE_DEMOS=1 로 빌드했을 때만 경로가 있다
//   그 밖                           → 첫 화면으로 넘김(루트 아래 splat 경로)
//
// 가드(밴드 LG1, app/auth/guard.ts): /·/login·/password·/admin·/greenwash 와 splat 의 beforeLoad 가 세션의 부팅 복원을 기다린 뒤
//   가드 표대로 넘긴다(replace). 첫 화면: 안 로그인 /login, isInitial /password, 운영 관리자 /admin/accounts, 고객사 사용자 /greenwash.
//   /dev/* 데모는 가드 밖이다(개발 서버·VITE_DEMOS=1 빌드에만 있다). 세션 저장소는 router context 의 session 칸이다.
//   가드는 레이아웃 경로(/admin·/greenwash)에만 단다 — 자식 경로에는 beforeLoad 가 없다(app/admin/router.test.tsx 가 경로 트리로 본다).
//   /admin 자신은 가드 뒤 /admin/accounts 로 넘긴다(critic 1 반영 B1 — 레이아웃 beforeLoad 안, guard.ts 는 감싸기만). /admin/zzz 는 루트 splat.
//
// 청크 규칙: 이 파일과 main.tsx 는 그린워싱 화면·pdfjs.ts·목 저장소를 정적으로 가져오지 않는다. 화면은 모두 lazyRouteComponent 로
//   게으르게 부른다 — 그린워싱의 진입 청크에 데모가, 데모의 진입 청크에 TanStack Query·PDF 썸네일이 들지 않는다.
//   데모 경로는 DEMOS 가 참일 때만 만든다(DEMOS 는 빌드 때 정해지는 상수라, 거짓이면 데모의 import() 가 빌드에서 지워진다.
//   scripts/check-no-demos.sh 가 dist 에서 데모 표식 글자를 찾아 0건인지 본다).
// search 는 URLSearchParams 그대로 글자로 읽고 쓴다(TanStack 의 기본은 값을 JSON 으로 읽어 `demo=1` 이 숫자가 된다).
// 스크롤: 화면을 바꿔도 지금처럼 그대로 둔다(TanStack 은 기본으로 이동마다 맨 위로 보낸다 — scrollRestoration 을 거짓 함수로 둬 끈다).
//   맨 위로 보내기는 다듬기 몫.
import {
  Outlet,
  createRootRouteWithContext,
  createRoute,
  createRouter,
  lazyRouteComponent,
  redirect,
} from '@tanstack/react-router';
import type { RouterHistory } from '@tanstack/react-router';

import type { OpenPdf } from '../widgets/doc-viewer/index.ts';
import type { AdminRouterContext } from './admin/runtime.ts';
import {
  createAppSession,
  followSession,
  guardLanding,
  guardSession,
} from './auth/guard.ts';
import type { AppSessionOptions, SessionContext } from './auth/guard.ts';
import type {
  CreateDataverifyStore,
  DataverifyRouterContext,
} from './dataverify/runtime.ts';
import type {
  AppRouterContext,
  CreateGreenwashStore,
  GreenwashSearch,
} from './greenwash/runtime.ts';
import type {
  CreateMaterialityStore,
  MaterialityRouterContext,
} from './materiality/runtime.ts';
import type {
  CreateTranslationStore,
  TranslationRouterContext,
  TranslationSearch,
} from './translation/runtime.ts';

/** 데모 넷을 여는 빌드인가(개발 서버, 또는 VITE_DEMOS=1 빌드). */
export const DEMOS = import.meta.env.DEV || import.meta.env.VITE_DEMOS === '1';

/** mock= 이 받는 값. 목 저장소의 MOCK_SCENARIOS 와 같다(app/greenwash/router.test.tsx 가 견준다) — 목을 가져오면 진입 청크에 들어 글자로 둔다. */
export const MOCK_SEARCH_VALUES = ['running', 'failed', 'done'] as const;

const text = (value: unknown) =>
  typeof value === 'string' ? value : undefined;

/** 그린워싱 틀의 search 검사. 아는 키의 아는 값만 남긴다(모르는 값은 버린다 — 옛 MOCK_SCENARIOS 검사와 같은 뜻). */
export function validateGreenwashSearch(
  raw: Record<string, unknown>,
): GreenwashSearch {
  const search: GreenwashSearch = {};
  const mock = MOCK_SEARCH_VALUES.find((value) => value === text(raw.mock));
  if (mock) search.mock = mock;
  if (text(raw.demo) === '1') search.demo = '1';
  if (text(raw.autofinish) === '1') search.autofinish = '1';
  if (text(raw.store) === 'mock') search.store = 'mock';
  return search;
}

/** 영문번역 파트 탭의 값(묶음 화면 ?part=). */
export const TRANSLATION_PARTS = ['all', 'ceo', 'story', 'general'] as const;

/** 영문번역 묶음 화면의 search 검사: part 는 아는 값만 남긴다(모르는 값은 버린다 — 밴드 TRW1a). */
export function validateTranslationSearch(
  raw: Record<string, unknown>,
): TranslationSearch {
  // 모르는 값도 열쇠는 싣는다(undefined) — 라우터가 부모의 날 search 를 덮어 합쳐서, 빼기만 하면 zzz 가 남는다.
  return {
    part: TRANSLATION_PARTS.find((value) => value === text(raw.part)),
  };
}

/** 온실가스 연도 화면(S2 자리·S17)의 search 검사: year 는 네 자리 숫자만 정수로 남긴다(밴드 W12-0b2). 범위는 경로 컴포넌트가 본다.
 *  주소에서 오면 글자, navigate 로 오면 정수다 — 둘 다 같은 글자 검사로 거른다. */
export function validateGhgYearSearch(raw: Record<string, unknown>): {
  year: number | undefined;
} {
  // 모르는 값도 열쇠는 싣는다(undefined) — validateTranslationSearch 와 같은 까닭.
  const year = typeof raw.year === 'number' ? String(raw.year) : text(raw.year);
  return { year: year && /^\d{4}$/.test(year) ? Number(year) : undefined };
}

/** URLSearchParams 그대로(값은 글자). 같은 키가 여럿이면 처음 것. */
function parseSearch(searchStr: string): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of new URLSearchParams(searchStr))
    if (!(key in out)) out[key] = value;
  return out;
}
function stringifySearch(search: Record<string, unknown>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(search))
    if (value !== undefined && value !== null) params.set(key, String(value));
  const query = params.toString();
  return query ? `?${query}` : '';
}

/** 그린워싱 틀 모듈이 내보내는 경로 컴포넌트. */
type GreenwashPart =
  | 'GreenwashLayout'
  | 'ListRoute'
  | 'IntroRoute'
  | 'NewCheckRoute'
  | 'StatusRoute'
  | 'ResultRoute'
  | 'ReviewRoute';
const greenwash = (name: GreenwashPart) =>
  lazyRouteComponent(() => import('./greenwash/GreenwashRoutes.tsx'), name);

/** 영문번역 틀 모듈이 내보내는 경로 컴포넌트(밴드 TRW1a). */
type TranslationPart =
  'TranslationLayout' | 'ListRoute' | 'IntroRoute' | 'NewRoute' | 'RunRoute';
type TranslationPdfPart = 'PdfNewRoute' | 'PdfViewRoute';
const translationPart = (name: TranslationPart | TranslationPdfPart) =>
  lazyRouteComponent(() => import('./translation/TranslationRoutes.tsx'), name);

/** 데이터 검증 틀 모듈이 내보내는 경로 컴포넌트(밴드 DV2a). */
type DataverifyPart =
  | 'DataverifyLayout'
  | 'ListRoute'
  | 'IntroRoute'
  | 'NewRoute'
  | 'StatusRoute'
  | 'ResultRoute';
const dataverifyPart = (name: DataverifyPart) =>
  lazyRouteComponent(() => import('./dataverify/DataverifyRoutes.tsx'), name);

/** 중대성평가 틀 모듈이 내보내는 경로 컴포넌트(밴드 IRW1). */
type MaterialityPart =
  | 'MaterialityLayout'
  | 'ListRoute'
  | 'IntroRoute'
  | 'NewRoute'
  | 'StatusRoute'
  | 'ResultRoute';
const materialityPart = (name: MaterialityPart) =>
  lazyRouteComponent(() => import('./materiality/MaterialityRoutes.tsx'), name);

/** 온실가스 틀 모듈이 내보내는 경로 컴포넌트(밴드 W12-0a). */
type GhgPart =
  | 'GhgLayout'
  | 'OrganizationRoute'
  | 'NewBranchRoute'
  | 'BranchRoute'
  | 'InventoryRoute'
  | 'IndexSettingsRoute'
  | 'DashboardRoute';
const ghgPart = (name: GhgPart) =>
  lazyRouteComponent(() => import('./ghg/GhgRoutes.tsx'), name);

/** 온실가스 Scope 3 경로 모듈이 내보내는 경로 컴포넌트(밴드 S3W1). */
type Scope3Part = 'Scope3Route';
const scope3Part = (name: Scope3Part) =>
  lazyRouteComponent(() => import('./ghg/Scope3Routes.tsx'), name);
/** 원고작성 틀 모듈이 내보내는 경로 컴포넌트(밴드 RPW1). */
type DraftingPart =
  | 'DraftingLayout'
  | 'ListRoute'
  | 'IntroRoute'
  | 'NewRoute'
  | 'DocumentRoute'
  | 'OutlineRoute'
  | 'RunRoute';
const draftingPart = (name: DraftingPart) =>
  lazyRouteComponent(() => import('./drafting/DraftingRoutes.tsx'), name);

/** 로그인 경로 모듈이 내보내는 경로 컴포넌트. */
type AuthPart = 'LoginRoute' | 'PasswordRoute';
const auth = (name: AuthPart) =>
  lazyRouteComponent(() => import('./auth/AuthRoutes.tsx'), name);

/** 어드민 틀 모듈이 내보내는 경로 컴포넌트(밴드 AD1). */
type AdminPart =
  | 'AdminLayout'
  | 'AccountsRoute'
  | 'AiSettingsRoute'
  | 'RunsRoute'
  | 'AuditRoute'
  | 'GhgSettingsRoute'
  | 'GhgIndexRoute'
  | 'OptionsRoute';
const adminPart = (name: AdminPart) =>
  lazyRouteComponent(() => import('./admin/AdminRoutes.tsx'), name);

/** AD-02 의 search 검사(감독 판단 11): version 은 「v숫자」만 남긴다. */
export function validateAiSettingsSearch(raw: Record<string, unknown>): {
  version?: string;
} {
  const version = text(raw.version);
  return version && /^v\d+$/.test(version) ? { version } : {};
}

/** AD-02 의 처음 모듈(옛 주소·없는 모듈이 가는 곳 — app/admin/ai-setting-modules.ts 의 그린워싱 슬롯 id). */
export const AI_SETTINGS_HOME_MODULE = 'greenwash';

/** 어드민 첫 화면(SESSION_PATHS.adminHome 과 같다 — 세션 model 을 가져오면 진입 청크 규칙 밖이라 글자로 둔다. 경로 시험이 견준다). */
export const ADMIN_HOME = '/admin/accounts';

/** AI 설정 › 온실가스 탭 껍데기의 첫 탭(밴드 AD7 — 맨 주소·옛 /admin/ghg-index 가 가는 곳. app/admin/AdminRoutes.tsx 의 GHG_SETTINGS_TABS 첫 줄과 같다). */
export const GHG_SETTINGS_HOME = '/admin/ai-settings/ghg/index';

/** 옛 어드민 주소 → 새 자리(밴드 AD7, sid:MARC-ENT-575 — e2e·북마크가 안 깨지게. search 는 버린다). */
export const ADMIN_MOVED: Readonly<Record<string, string>> = {
  '/admin/ai-settings/ghg': GHG_SETTINGS_HOME,
  '/admin/ghg-index': GHG_SETTINGS_HOME,
  '/admin/options': '/admin/ai-settings/ghg/options',
};

/** 데모 경로를 만드는 함수. DEMOS 가 거짓인 빌드에는 없다(그래서 데모의 import() 가 빌드에 들지 않는다). */
const demoRoutes =
  DEMOS ?
    (root: AnyRoot) => [
      createRoute({
        getParentRoute: () => root,
        path: 'dev/viewer',
        component: lazyRouteComponent(
          () => import('../pages/demo-viewer/App.tsx'),
          'App',
        ),
      }),
      createRoute({
        getParentRoute: () => root,
        path: 'dev/table',
        component: lazyRouteComponent(
          () => import('../pages/demo-table/TablePage.tsx'),
          'TablePage',
        ),
      }),
      createRoute({
        getParentRoute: () => root,
        path: 'dev/api',
        component: lazyRouteComponent(
          () => import('../pages/demo-api/ApiPage.tsx'),
          'ApiPage',
        ),
      }),
      createRoute({
        getParentRoute: () => root,
        path: 'dev/parts',
        component: lazyRouteComponent(
          () => import('../pages/demo-parts/PartsPage.tsx'),
          'PartsPage',
        ),
      }),
    ]
  : null;

const createRoot = () =>
  createRootRouteWithContext<
    AppRouterContext &
      SessionContext &
      AdminRouterContext &
      TranslationRouterContext &
      DataverifyRouterContext &
      MaterialityRouterContext
  >()({
    component: Outlet,
  });
type AnyRoot = ReturnType<typeof createRoot>;

export interface AppRouterOptions {
  history: RouterHistory;
  /** 시험용. 없으면 widgets/doc-viewer/pdfjs.ts(틀 모듈이 가져온다). */
  openPdf?: OpenPdf;
  /** 시험용. 없으면 기본 저장소(틀 모듈 — 실어댑터, 데모 빌드의 탭 표지면 목. 밴드 GW1R Q1). */
  createStore?: CreateGreenwashStore;
  /** 시험용. 없으면 영문번역 기본 저장소(틀 모듈 — 실어댑터, 밴드 TRW1a). */
  createTranslationStore?: CreateTranslationStore;
  /** 시험용. 없으면 데이터 검증 기본 저장소(틀 모듈 — 실어댑터, 밴드 DV2a). */
  createDataverifyStore?: CreateDataverifyStore;
  /** 시험용. 없으면 중대성평가 기본 저장소(틀 모듈 — 실어댑터, 밴드 IRW1). */
  createMaterialityStore?: CreateMaterialityStore;
  /**
   * 데모 경로를 넣는가. 기본 DEMOS(vitest 에선 DEV 라 참). DEMOS 가 거짓인 빌드에선 참을 줘도 데모 경로가 없다.
   * 같은 값(demos && DEMOS)을 router context 의 admin.demos 에 싣는다 — 어드민의 목 동작(AD-02 저장류)은 그 칸이 참일 때만 켠다(감독 판단 5, critic 1 반영 B3).
   * AD-01 계정 수정은 실서버라 이 값과 무관하게 켜진다(UA1W).
   */
  demos?: boolean;
  /** 시험용 세션(통신 함수·보관소·바탕 주소). 없으면 전역 fetch 와 sessionStorage(app/auth/guard.ts). */
  session?: AppSessionOptions;
}

export function createAppRouter({
  history,
  openPdf,
  createStore,
  createTranslationStore,
  createDataverifyStore,
  createMaterialityStore,
  demos = DEMOS,
  session: sessionOptions,
}: AppRouterOptions) {
  const root = createRoot();
  const session = createAppSession(sessionOptions);

  // `/` 는 첫 화면으로(search 는 버린다 — 옛 ?view=·?screen=·?run= 주소도 여기서 첫 화면에 떨어진다). 가드가 늘 넘긴다.
  const index = createRoute({
    getParentRoute: () => root,
    path: '/',
    beforeLoad: guardLanding,
  });

  // 모르는 주소(/zzz, /greenwash/xyz, /greenwash/runs/x/zzz …)는 첫 화면으로. notFoundRoute 는 쓰지 않는다(낡은 API).
  const unknown = createRoute({
    getParentRoute: () => root,
    path: '$',
    beforeLoad: guardLanding,
  });

  const login = createRoute({
    getParentRoute: () => root,
    path: 'login',
    beforeLoad: guardSession,
    component: auth('LoginRoute'),
  });
  const password = createRoute({
    getParentRoute: () => root,
    path: 'password',
    beforeLoad: guardSession,
    component: auth('PasswordRoute'),
  });
  // 어드민 틀(밴드 AD1). 가드는 이 레이아웃 경로 하나 — 자식 경로에는 beforeLoad 를 달지 않는다(LG1 가지 리뷰 3).
  // guardSession 이 먼저 돈다(고객사 사용자는 여기서 /greenwash 로). 그 뒤 /admin 자신이면 첫 화면으로(critic 1 반영 B1).
  const admin = createRoute({
    getParentRoute: () => root,
    path: 'admin',
    beforeLoad: async (args) => {
      await guardSession(args);
      const { pathname } = args.location;
      if (pathname === '/admin' || pathname === '/admin/')
        throw redirect({ to: ADMIN_HOME, replace: true });
      // 옛 AD-02 주소(모듈 칸 없음)는 그린워싱 모듈 주소로(밴드 AM1 — search version 은 실어 간다). 자식 경로에 beforeLoad 를 달지 않으려 여기서.
      if (
        pathname === '/admin/ai-settings' ||
        pathname === '/admin/ai-settings/'
      )
        throw redirect({
          to: '/admin/ai-settings/$module',
          params: { module: AI_SETTINGS_HOME_MODULE },
          search: validateAiSettingsSearch(args.location.search),
          replace: true,
        });
      // 온실가스 탭 껍데기 맨 주소·옛 두 주소(밴드 AD7). 끝 / 는 떼고 본다.
      const moved = ADMIN_MOVED[pathname.replace(/\/$/, '')];
      if (moved) throw redirect({ to: moved, replace: true });
    },
    component: adminPart('AdminLayout'),
  });
  const accounts = createRoute({
    getParentRoute: () => admin,
    path: 'accounts',
    component: adminPart('AccountsRoute'),
  });

  // AD-02 AI 설정·AD-04 실행 기록·AD-05 감사 기록(밴드 AD2R·AD4R·AD5R — 실서버, AdminRoutes). 자식 경로라 beforeLoad 는 없다(가드는 /admin 하나). search 검사는 beforeLoad 가 아니다.
  // AD-02 는 모듈 칸 하나로 그 모듈 슬롯을 그린다(밴드 AM1). /admin/ai-settings 자신은 그리지 않는다 — /admin 의 beforeLoad 가 넘긴다.
  const aiSettings = createRoute({
    getParentRoute: () => admin,
    path: 'ai-settings',
    validateSearch: validateAiSettingsSearch,
  });
  const aiSettingsModule = createRoute({
    getParentRoute: () => aiSettings,
    path: '$module',
    component: adminPart('AiSettingsRoute'),
  });
  const runs = createRoute({
    getParentRoute: () => admin,
    path: 'runs',
    component: adminPart('RunsRoute'),
  });
  const audit = createRoute({
    getParentRoute: () => admin,
    path: 'audit',
    component: adminPart('AuditRoute'),
  });
  // AI 설정 › 온실가스 탭 껍데기(밴드 AD7, sid:MARC-ENT-575). 고정 경로 ghg 라 형제 $module(AiSettingsRoute — 없는 모듈은 그린워싱)이 ghg 를 삼키지 않는다.
  // 탭 둘: index = S19·S20 온실가스 인덱스(밴드 W12-0b1 ③), options = S18 자산/시설명 및 코드(밴드 W12-0a ③). 맨 주소는 /admin beforeLoad 가 넘긴다.
  // 셋째 탭 자리는 없다. 자식 경로라 beforeLoad 는 없다(가드는 /admin 하나).
  const aiSettingsGhg = createRoute({
    getParentRoute: () => aiSettings,
    path: 'ghg',
    component: adminPart('GhgSettingsRoute'),
  });
  const ghgIndex = createRoute({
    getParentRoute: () => aiSettingsGhg,
    path: 'index',
    component: adminPart('GhgIndexRoute'),
  });
  const options = createRoute({
    getParentRoute: () => aiSettingsGhg,
    path: 'options',
    component: adminPart('OptionsRoute'),
  });
  // 옛 주소 둘(밴드 AD7): 경로만 남겨 /admin beforeLoad 가 넘기게 한다(경로가 없으면 루트 splat 이 첫 화면으로 보낸다). 화면은 없다.
  const movedGhgIndex = createRoute({
    getParentRoute: () => admin,
    path: 'ghg-index',
  });
  const movedOptions = createRoute({
    getParentRoute: () => admin,
    path: 'options',
  });

  const shell = createRoute({
    getParentRoute: () => root,
    path: 'greenwash',
    validateSearch: validateGreenwashSearch,
    beforeLoad: guardSession,
    component: greenwash('GreenwashLayout'),
  });
  // createRoute 의 path 는 글자 그대로 타입이 되어야 해서 하나씩 적는다.
  const list = createRoute({
    getParentRoute: () => shell,
    path: '/',
    component: greenwash('ListRoute'),
  });
  const intro = createRoute({
    getParentRoute: () => shell,
    path: 'intro',
    component: greenwash('IntroRoute'),
  });
  const newCheck = createRoute({
    getParentRoute: () => shell,
    path: 'new',
    component: greenwash('NewCheckRoute'),
  });
  const status = createRoute({
    getParentRoute: () => shell,
    path: 'runs/$runId',
    component: greenwash('StatusRoute'),
  });
  const result = createRoute({
    getParentRoute: () => shell,
    path: 'runs/$runId/result',
    component: greenwash('ResultRoute'),
  });
  const review = createRoute({
    getParentRoute: () => shell,
    path: 'runs/$runId/review',
    component: greenwash('ReviewRoute'),
  });
  // 영문번역 틀(밴드 TRW1a). 가드는 이 레이아웃 경로 하나 — 자식 경로에는 beforeLoad 가 없다(그린워싱 틀과 같다).
  const translation = createRoute({
    getParentRoute: () => root,
    path: 'translation',
    beforeLoad: guardSession,
    component: translationPart('TranslationLayout'),
  });
  const translationList = createRoute({
    getParentRoute: () => translation,
    path: '/',
    component: translationPart('ListRoute'),
  });
  const translationIntro = createRoute({
    getParentRoute: () => translation,
    path: 'intro',
    component: translationPart('IntroRoute'),
  });
  const translationNew = createRoute({
    getParentRoute: () => translation,
    path: 'new',
    component: translationPart('NewRoute'),
  });
  const translationRun = createRoute({
    getParentRoute: () => translation,
    path: 'documents/$documentId/batches/$batchKey',
    validateSearch: validateTranslationSearch,
    component: translationPart('RunRoute'),
  });
  const translationPdfNew = createRoute({
    getParentRoute: () => translation,
    path: 'pdf/new',
    component: translationPart('PdfNewRoute'),
  });
  const translationPdfView = createRoute({
    getParentRoute: () => translation,
    path: 'documents/$documentId/batches/$batchKey/pdf/$runId',
    component: translationPart('PdfViewRoute'),
  });
  // 데이터 검증 틀(밴드 DV2a). 가드는 이 레이아웃 경로 하나 — 자식 경로에는 beforeLoad 가 없다(영문번역 틀과 같다).
  const dataverify = createRoute({
    getParentRoute: () => root,
    path: 'dataverify',
    beforeLoad: guardSession,
    component: dataverifyPart('DataverifyLayout'),
  });
  const dataverifyList = createRoute({
    getParentRoute: () => dataverify,
    path: '/',
    component: dataverifyPart('ListRoute'),
  });
  const dataverifyIntro = createRoute({
    getParentRoute: () => dataverify,
    path: 'intro',
    component: dataverifyPart('IntroRoute'),
  });
  const dataverifyNew = createRoute({
    getParentRoute: () => dataverify,
    path: 'new',
    component: dataverifyPart('NewRoute'),
  });
  const dataverifyStatus = createRoute({
    getParentRoute: () => dataverify,
    path: 'runs/$runId',
    component: dataverifyPart('StatusRoute'),
  });
  const dataverifyResult = createRoute({
    getParentRoute: () => dataverify,
    path: 'runs/$runId/result',
    component: dataverifyPart('ResultRoute'),
  });
  // 중대성평가 틀(밴드 IRW1). 가드는 이 레이아웃 경로 하나 — 자식 경로에는 beforeLoad 가 없다(데이터 검증 틀과 같다).
  const materiality = createRoute({
    getParentRoute: () => root,
    path: 'materiality',
    beforeLoad: guardSession,
    component: materialityPart('MaterialityLayout'),
  });
  const materialityList = createRoute({
    getParentRoute: () => materiality,
    path: '/',
    component: materialityPart('ListRoute'),
  });
  const materialityStatus = createRoute({
    getParentRoute: () => materiality,
    path: 'runs/$runId',
    component: materialityPart('StatusRoute'),
  });
  const materialityResult = createRoute({
    getParentRoute: () => materiality,
    path: 'runs/$runId/result',
    component: materialityPart('ResultRoute'),
  });
  const materialityIntro = createRoute({
    getParentRoute: () => materiality,
    path: 'intro',
    component: materialityPart('IntroRoute'),
  });
  const materialityNew = createRoute({
    getParentRoute: () => materiality,
    path: 'new',
    component: materialityPart('NewRoute'),
  });
  // 온실가스 틀(밴드 W12-0a). 가드는 이 레이아웃 경로 하나 — 자식 경로에는 beforeLoad 가 없다(중대성평가 틀과 같다).
  // /ghg 자신은 가드 뒤 /ghg/dashboard 로 넘긴다(/admin 꼴 — 레이아웃 beforeLoad 안. 밴드 DB1 이 갈음함 — 전에는 /ghg/organization).
  const ghg = createRoute({
    getParentRoute: () => root,
    path: 'ghg',
    beforeLoad: async (args) => {
      await guardSession(args);
      const { pathname } = args.location;
      if (pathname === '/ghg' || pathname === '/ghg/')
        throw redirect({
          to: '/ghg/dashboard',
          search: { year: undefined },
          replace: true,
        });
    },
    component: ghgPart('GhgLayout'),
  });
  const ghgOrganization = createRoute({
    getParentRoute: () => ghg,
    path: 'organization',
    component: ghgPart('OrganizationRoute'),
  });
  const ghgBranchNew = createRoute({
    getParentRoute: () => ghg,
    path: 'organization/branches/new',
    component: ghgPart('NewBranchRoute'),
  });
  const ghgBranch = createRoute({
    getParentRoute: () => ghg,
    path: 'organization/branches/$branchId',
    component: ghgPart('BranchRoute'),
  });
  // S2 자리·S17(밴드 W12-0b2 ③). 자식 경로라 beforeLoad 는 없다(가드는 /ghg 하나).
  const ghgInventory = createRoute({
    getParentRoute: () => ghg,
    path: 'inventory',
    validateSearch: validateGhgYearSearch,
    component: ghgPart('InventoryRoute'),
  });
  const ghgIndexSettings = createRoute({
    getParentRoute: () => ghg,
    path: 'inventory/index-settings',
    validateSearch: validateGhgYearSearch,
    component: ghgPart('IndexSettingsRoute'),
  });
  // S3-01 Scope 3(밴드 S3W1 ③). 거름은 S2 자리와 같다 — 범위·기본 해(전년도)는 경로 컴포넌트가 본다.
  const ghgScope3 = createRoute({
    getParentRoute: () => ghg,
    path: 'scope3',
    validateSearch: validateGhgYearSearch,
    component: scope3Part('Scope3Route'),
  });
  // S1 대시보드 온실가스 탭(밴드 DB1 ③). 거름은 S2 자리와 같다 — 범위·기본 해(전년도)는 경로 컴포넌트가 본다.
  const ghgDashboard = createRoute({
    getParentRoute: () => ghg,
    path: 'dashboard',
    validateSearch: validateGhgYearSearch,
    component: ghgPart('DashboardRoute'),
  });
  // 원고작성 틀(밴드 RPW1). 가드는 이 레이아웃 경로 하나(ghg 꼴) — /drafting 자신이 RP-01 이라 넘김은 없다. 자식 경로에는 beforeLoad 가 없다.
  const drafting = createRoute({
    getParentRoute: () => root,
    path: 'drafting',
    beforeLoad: guardSession,
    component: draftingPart('DraftingLayout'),
  });
  const draftingList = createRoute({
    getParentRoute: () => drafting,
    path: '/',
    component: draftingPart('ListRoute'),
  });
  const draftingIntro = createRoute({
    getParentRoute: () => drafting,
    path: 'intro',
    component: draftingPart('IntroRoute'),
  });
  const draftingNew = createRoute({
    getParentRoute: () => drafting,
    path: 'new',
    component: draftingPart('NewRoute'),
  });
  const draftingDocument = createRoute({
    getParentRoute: () => drafting,
    path: 'projects/$projectId/document',
    component: draftingPart('DocumentRoute'),
  });
  const draftingOutline = createRoute({
    getParentRoute: () => drafting,
    path: 'projects/$projectId/outline',
    component: draftingPart('OutlineRoute'),
  });
  const draftingRun = createRoute({
    getParentRoute: () => drafting,
    path: 'projects/$projectId/runs/$runId',
    component: draftingPart('RunRoute'),
  });
  const routeTree = root.addChildren([
    index,
    login,
    password,
    admin.addChildren([
      accounts,
      aiSettings.addChildren([
        aiSettingsModule,
        aiSettingsGhg.addChildren([ghgIndex, options]),
      ]),
      runs,
      audit,
      movedGhgIndex,
      movedOptions,
    ]),
    shell.addChildren([list, intro, newCheck, status, result, review]),
    translation.addChildren([
      translationList,
      translationIntro,
      translationNew,
      translationRun,
      translationPdfNew,
      translationPdfView,
    ]),
    dataverify.addChildren([
      dataverifyList,
      dataverifyIntro,
      dataverifyNew,
      dataverifyStatus,
      dataverifyResult,
    ]),
    materiality.addChildren([
      materialityList,
      materialityIntro,
      materialityNew,
      materialityStatus,
      materialityResult,
    ]),
    ghg.addChildren([
      ghgDashboard,
      ghgOrganization,
      ghgBranchNew,
      ghgBranch,
      ghgInventory,
      ghgIndexSettings,
      ghgScope3,
    ]),
    drafting.addChildren([
      draftingList,
      draftingIntro,
      draftingNew,
      draftingDocument,
      draftingOutline,
      draftingRun,
    ]),
    ...(demos && demoRoutes ? demoRoutes(root) : []),
    unknown,
  ]);

  const router = createRouter({
    routeTree,
    history,
    context: {
      openPdf,
      createStore,
      createTranslationStore,
      createDataverifyStore,
      createMaterialityStore,
      greenwash: { control: null, confirmRunId: null },
      translation: { control: null, notStarted: new Map() },
      dataverify: { control: null },
      materiality: { control: null },
      session,
      admin: {
        demos: demos && DEMOS,
      },
    },
    parseSearch,
    stringifySearch,
    scrollRestoration: () => false,
  });
  // 로그인·로그아웃·만료·비밀번호 바꿈 → 가드를 다시 돌린다(첫 화면·/login 으로 넘기는 것은 가드 하나다).
  followSession(session, () => void router.invalidate());
  return router;
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
