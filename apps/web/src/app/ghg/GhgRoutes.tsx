// 온실가스 틀과 경로 컴포넌트(밴드 W12-0a ② — app/materiality/MaterialityRoutes.tsx 꼴). app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다.
//   - 틀(GhgLayout): AppShell(메뉴 여섯 — app/shell/moduleMenu.tsx 한 자리, currentId ghg)·인사말·[관리자 화면](운영 관리자)·[로그아웃].
//     새 router context 칸은 없다 — 실어댑터는 root context 의 session.api 로 짓는다(useMemo, 세션 api 가 같으면 같은 것).
//     쥔 열쇠·기억이 없어 세션 끝에 버릴 것도 없다(followSessionEnd 를 옮겨 적지 않았다 — 보고 「발주서와 다르게 한 것」).
//   - 경로 컴포넌트(…Route): 화면(pages)은 라우터·세션을 모른다. 콜백 props 를 여기서 navigate 로 잇는다.
// /ghg 는 레이아웃 beforeLoad(app/router.tsx)가 /ghg/dashboard 로 넘긴다(밴드 DB1 — S1 대시보드). /ghg/organization = S15 목록 ·
//   …/branches/new = 새 사업장 · …/branches/$branchId = 상세. 행·> → 상세 push · 「사업장 추가」 → new push · [취소]·[목록으로] → 목록 push ·
//   새로 저장(201) → 그 id 의 상세 replace(뒤로 가기가 빈 폼으로 돌아오지 않는다).
// /ghg/inventory?year= = S2 온실가스 데이터 자리 · …/inventory/index-settings?year= = S17(밴드 W12-0b2 ③). 연도는 search(router.tsx 가
//   네 자리 정수로 거름) — 없거나 고를 수 있는 해(yearsOf — 올해부터 다섯) 밖이면 전년도(defaultYearOf —
//   Scope 3 와 같음, sid:MARC-ENT-578)로 replace. 연도 바꿈은 replace, 화면 사이 이동은 push.
//   S17 저장 → S2 자리 push + 기록 state ghgSaved(주소에 싣지 않는다 — router.tsx 의 search 검사에 없는 열쇠) → 머리 옆 「저장됐어요」.
//   S2 는 처음 그린 값을 쥐고 기록 state 의 ghgSaved 를 곧바로 걷는다(replace — 새로 고침·뒤로 왔다 앞으로에 다시 뜨지 않게, sid:MARC-ISSUE-468 R7).
//   S2 연도 바꿈은 「저장됐어요」도 걷는다.
// 틀 본문 머리 탭 줄 「대시보드 · 온실가스 데이터 · 조직구조」(발주서 Q3 · 밴드 DB1 ③ 맨 앞 대시보드 — sid:MARC-ENT-597): 지금 경로 앞머리로 고른 탭(사업장 상세·새 사업장도 「조직구조」), 누르면 push.
//   Scope 3 자리(/ghg/scope3 — 밴드 S3W1 ③, app/ghg/Scope3Routes.tsx)도 「온실가스 데이터」.
// 「온실가스 데이터」 제목 아래 Scope 탭 줄 「Scope 1&2 · Scope 3」(ScopeTabs — Figma 28023:7468, 밴드 S3W1 ③): S2 자리와 Scope 3 자리가
//   화면 prop tabs 로 그린다. 누르면 지금 연도를 실어 push — 받는 화면의 고를 수 있는 해 밖이면 그 화면이 기본 해로 replace(useYear 꼴).
// 운영 관리자도 같은 화면이다(인사말·[관리자 화면]·[로그아웃]만 다름 — sid:MARC-ENT-469 4). useOperator·머리는 MaterialityRoutes.tsx 를
//   옮겨 적었다(가져오지 않는다 — 남의 모듈 땅, 공통화는 후속 sid:MARC-ISSUE-335).
import { useEffect, useMemo, useState } from 'react';

import { ArrowLeftIcon } from '@marcspon/common/generated/icons/MyIcons';
import {
  Outlet,
  getRouteApi,
  useLocation,
  useNavigate,
} from '@tanstack/react-router';
import type { NavigateOptions } from '@tanstack/react-router';

import { S3_TEXT } from '../../entities/ghg-scope3/config/text.ts';
import { SPARKLE } from '../../entities/ghg-scope3/model/index.ts';
import {
  createGhgDashboardPort,
  createGhgEntryPort,
  createGhgOrganizationPort,
  createGhgPoolAdminPort,
  createGhgSelectionPort,
} from '../../entities/ghg/api/index.ts';
import type {
  GhgDashboardPort,
  GhgEntryPort,
  GhgOrganizationPort,
  GhgPoolAdminPort,
  GhgSelectionPort,
} from '../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../entities/ghg/config/text.ts';
import {
  defaultYearOf,
  yearIn,
  yearsOf,
} from '../../entities/ghg/model/index.ts';
import { useSession } from '../../entities/session/hooks/index.ts';
import { BranchScreen } from '../../pages/ghg-branch/index.ts';
import { DashboardScreen } from '../../pages/ghg-dashboard/index.ts';
import { IndexSettingsScreen } from '../../pages/ghg-index-settings/index.ts';
import { InventoryScreen } from '../../pages/ghg-inventory/index.ts';
import { OrganizationScreen } from '../../pages/ghg-organization/index.ts';
import { AppShell } from '../../shared/ui/app-shell/index.ts';
import { Button } from '../../shared/ui/button/index.ts';
import { HeaderGreeting } from '../../shared/ui/header-greeting/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../shared/ui/tabs/index.ts';
import { moduleMenu, moduleTarget } from '../shell/moduleMenu.tsx';

const layoutApi = getRouteApi('/ghg');
const branchApi = getRouteApi('/ghg/organization/branches/$branchId');
const inventoryApi = getRouteApi('/ghg/inventory');
const indexSettingsApi = getRouteApi('/ghg/inventory/index-settings');
const dashboardApi = getRouteApi('/ghg/dashboard');

const shell = GHG_TEXT.shell;
const MENU = moduleMenu(shell.menu);
const tabs = GHG_TEXT.inventory.tabs;
const TABS = [
  { value: 'dashboard', to: '/ghg/dashboard', also: null },
  { value: 'inventory', to: '/ghg/inventory', also: '/ghg/scope3' },
  { value: 'organization', to: '/ghg/organization', also: null },
] as const;
const SCOPE_TABS = [
  { value: 'scope12', to: '/ghg/inventory' },
  { value: 'scope3', to: '/ghg/scope3' },
] as const;

/** 지금 세션이 운영 관리자인가(머리 인사말·[관리자 화면]을 가른다 — MaterialityRoutes.tsx 를 옮겨 적음). */
export function useOperator(): boolean {
  const state = useSession(layoutApi.useRouteContext().session);
  return state.status === 'signedIn' && state.user.kind === 'admin';
}

/** 조직구조 실어댑터(세션 api 하나에 하나). */
export function useOrganizationPort(): GhgOrganizationPort {
  const api = layoutApi.useRouteContext().session.api;
  return useMemo(() => createGhgOrganizationPort({ api }), [api]);
}

/** 선택 실어댑터(세션 api 하나에 하나). */
export function useSelectionPort(): GhgSelectionPort {
  const api = layoutApi.useRouteContext().session.api;
  return useMemo(() => createGhgSelectionPort({ api }), [api]);
}

/** 입력 실어댑터(세션 api 하나에 하나 — S2 리스트, 밴드 W12-1a). */
export function useEntryPort(): GhgEntryPort {
  const api = layoutApi.useRouteContext().session.api;
  return useMemo(() => createGhgEntryPort({ api }), [api]);
}

/** 대시보드 실어댑터(세션 api 하나에 하나 — S1, 밴드 DB1). */
export function useDashboardPort(): GhgDashboardPort {
  const api = layoutApi.useRouteContext().session.api;
  return useMemo(() => createGhgDashboardPort({ api }), [api]);
}

/** 풀 실어댑터(운영 관리자만 — S3 상세 S8 [배출계수 수정], 밴드 W12-3 Q5 · 선례 app/admin/AdminRoutes.tsx). 고객사는 null. */
export function usePoolPort(operator: boolean): GhgPoolAdminPort | null {
  const api = layoutApi.useRouteContext().session.api;
  return useMemo(
    () => (operator ? createGhgPoolAdminPort({ api }) : null),
    [api, operator],
  );
}

/** 이동 하나. */
export function useGo() {
  const navigate = useNavigate();
  return (options: NavigateOptions) => void navigate(options);
}

/** 틀 본문 머리 탭 줄 — 지금 경로 앞머리로 고른 탭, 누르면 push. */
function ModuleTabs() {
  const pathname = useLocation({ select: (location) => location.pathname });
  const go = useGo();
  const current = TABS.find((tab) =>
    [tab.to, tab.also].some(
      (to) => to && (pathname === to || pathname.startsWith(`${to}/`)),
    ),
  );
  return (
    <Tabs
      value={current?.value ?? ''}
      onValueChange={(value) => {
        const tab = TABS.find((one) => one.value === value);
        if (tab) go({ to: tab.to });
      }}
    >
      <TabsList aria-label={GHG_TEXT.inventory.tabsLabel}>
        {TABS.map((tab) => (
          <TabsTrigger key={tab.value} value={tab.value}>
            {tabs[tab.value]}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

/** Scope 탭 줄의 고른 탭(값 파일 GX3 ② 고침 1 — 판 S3-01 `.f-tab.on`): 글·밑줄 brand, 안 고른 탭 tertiary(키트 page 꼴 그대로). 공용 Tabs 는 건드리지 않는다. 글과 반짝이(GX4 ④)는 한 줄 가운데 · 사이 4. */
const SCOPE_TAB_CLASS =
  'inline-flex min-w-24 items-center justify-center gap-1 data-[state=active]:border-text-brand data-[state=active]:text-text-brand';

/** 「Scope 3」 탭 글 오른쪽 AI 반짝이 16(Figma 28029:2849, GX4 ④): 늘 · 글과 사이 4 · 색은 글을 따라감(currentColor) · 읽지 않음(탭 이름은 「Scope 3」 그대로). */
function ScopeSparkle() {
  return (
    <svg
      aria-hidden="true"
      data-testid="s3-tab-sparkle"
      viewBox="0 0 16.5 16.5"
      fill="none"
      className="size-4 shrink-0"
    >
      <path
        d={SPARKLE}
        fill="currentColor"
        stroke="currentColor"
        strokeWidth="0.5"
      />
    </svg>
  );
}

/** 「온실가스 데이터」 제목 아래 Scope 탭 줄 — 지금 경로로 고른 탭, 누르면 그 연도를 실어 push. */
export function ScopeTabs({ year }: { year: number }) {
  const pathname = useLocation({ select: (location) => location.pathname });
  const go = useGo();
  const current = SCOPE_TABS.find((tab) => pathname === tab.to);
  return (
    <Tabs
      variant="page"
      value={current?.value ?? ''}
      onValueChange={(value) => {
        const tab = SCOPE_TABS.find((one) => one.value === value);
        if (tab) go({ to: tab.to, search: { year } });
      }}
    >
      <TabsList aria-label={S3_TEXT.scopeTabsLabel}>
        {SCOPE_TABS.map((tab) => (
          <TabsTrigger
            key={tab.value}
            value={tab.value}
            className={SCOPE_TAB_CLASS}
          >
            {S3_TEXT.scopeTabs[tab.value]}
            {tab.value === 'scope3' && <ScopeSparkle />}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

export function GhgLayout() {
  const context = layoutApi.useRouteContext();
  const go = useGo();
  const operator = useOperator();

  return (
    <div className="twp">
      <AppShell
        menu={MENU}
        currentId="ghg"
        onSelect={(id) => {
          const to = moduleTarget(id);
          if (to) go({ to });
        }}
        menuLabel={shell.menuLabel}
        logo={shell.logo}
        title={shell.title}
        headerRight={
          <HeaderGreeting
            greeting={operator ? shell.adminGreeting : shell.greeting}
            action={
              operator ?
                <Button
                  variant="outlineGrey"
                  shape="round"
                  size="md"
                  onClick={() => go({ to: '/admin/accounts' })}
                >
                  <ArrowLeftIcon aria-hidden />
                  {shell.toAdmin}
                </Button>
              : undefined
            }
            onLogout={() => context.session.logout()}
          />
        }
        className="min-h-screen"
      >
        <div className="flex flex-col gap-6">
          <ModuleTabs />
          <Outlet />
        </div>
      </AppShell>
    </div>
  );
}

/** /ghg/organization — S15 조직구조 목록. */
export function OrganizationRoute() {
  const port = useOrganizationPort();
  const go = useGo();
  const operator = useOperator();
  return (
    <OrganizationScreen
      port={port}
      onOpen={(branchId) =>
        go({
          to: '/ghg/organization/branches/$branchId',
          params: { branchId },
        })
      }
      onNew={() => go({ to: '/ghg/organization/branches/new' })}
      operator={operator}
    />
  );
}

/** /ghg/organization/branches/new — 새 사업장. 201 → 상세 replace. */
export function NewBranchRoute() {
  const port = useOrganizationPort();
  const go = useGo();
  const operator = useOperator();
  return (
    <BranchScreen
      port={port}
      branchId={null}
      operator={operator}
      onBack={() => go({ to: '/ghg/organization' })}
      onCreated={(branchId) =>
        go({
          to: '/ghg/organization/branches/$branchId',
          params: { branchId },
          replace: true,
        })
      }
    />
  );
}

/** /ghg/organization/branches/$branchId — 사업장 상세. */
export function BranchRoute() {
  const port = useOrganizationPort();
  const go = useGo();
  const operator = useOperator();
  const { branchId } = branchApi.useParams();
  return (
    <BranchScreen
      key={branchId}
      port={port}
      branchId={branchId}
      operator={operator}
      onBack={() => go({ to: '/ghg/organization' })}
      onCreated={(id) =>
        go({
          to: '/ghg/organization/branches/$branchId',
          params: { branchId: id },
          replace: true,
        })
      }
    />
  );
}

/** 주소의 연도 — 고를 수 있는 해 밖(없음·범위 밖)이면 전년도(defaultYearOf, sid:MARC-ENT-578)로 replace 하고 null(그동안 화면을 그리지 않는다). */
function useYear(
  year: number | undefined,
  to: '/ghg/inventory' | '/ghg/inventory/index-settings' | '/ghg/dashboard',
) {
  const years = useMemo(() => yearsOf(new Date()), []);
  const fallback = useMemo(() => defaultYearOf(new Date()), []);
  const navigate = useNavigate();
  const known = yearIn(year, years);
  useEffect(() => {
    if (known === null)
      void navigate({ to, search: { year: fallback }, replace: true });
  }, [known, navigate, to, fallback]);
  return { year: known, years };
}

/** /ghg/dashboard?year= — S1 대시보드 온실가스 탭(밴드 DB1). 연도 바꿈은 replace · [바로가기]·› 는 push. */
export function DashboardRoute() {
  const port = useDashboardPort();
  const go = useGo();
  const operator = useOperator();
  const search = dashboardApi.useSearch();
  const { year, years } = useYear(search.year, '/ghg/dashboard');
  if (year === null) return null;
  return (
    <DashboardScreen
      port={port}
      year={year}
      years={years}
      operator={operator}
      onYear={(next) =>
        go({ to: '/ghg/dashboard', search: { year: next }, replace: true })
      }
      onSetup={(next) =>
        go({ to: '/ghg/inventory/index-settings', search: { year: next } })
      }
      onInventory={(next) =>
        go({ to: '/ghg/inventory', search: { year: next } })
      }
      onOrganization={() => go({ to: '/ghg/organization' })}
    />
  );
}

/** /ghg/inventory?year= — S2 온실가스 데이터 자리. */
export function InventoryRoute() {
  const port = useEntryPort();
  const organization = useOrganizationPort();
  const go = useGo();
  const operator = useOperator();
  const pool = usePoolPort(operator);
  const search = inventoryApi.useSearch();
  const saved = useLocation({
    select: (location) =>
      'ghgSaved' in location.state && location.state.ghgSaved === true,
  });
  // 처음 그린 값을 쥐고 기록에서는 걷는다(R7 — Q10).
  const [shownSaved, setShownSaved] = useState(saved);
  useEffect(() => {
    if (saved)
      go({
        to: '/ghg/inventory',
        search: (old) => old,
        replace: true,
        state: (old) => ({ ...old, ghgSaved: false }),
      });
    // go 는 그릴 때마다 새 함수다 — 걷기는 saved 로만.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saved]);
  const { year, years } = useYear(search.year, '/ghg/inventory');
  if (year === null) return null;
  return (
    <InventoryScreen
      port={port}
      organization={organization}
      year={year}
      years={years}
      operator={operator}
      pool={pool}
      saved={shownSaved}
      tabs={<ScopeTabs year={year} />}
      onYear={(next) => {
        setShownSaved(false);
        go({ to: '/ghg/inventory', search: { year: next }, replace: true });
      }}
      onIndexSettings={(next) =>
        go({ to: '/ghg/inventory/index-settings', search: { year: next } })
      }
      onOrganization={() => go({ to: '/ghg/organization' })}
    />
  );
}

/** /ghg/inventory/index-settings?year= — S17 인덱스 설정. */
export function IndexSettingsRoute() {
  const port = useSelectionPort();
  const go = useGo();
  const operator = useOperator();
  const search = indexSettingsApi.useSearch();
  const { year, years } = useYear(search.year, '/ghg/inventory/index-settings');
  if (year === null) return null;
  return (
    <IndexSettingsScreen
      port={port}
      year={year}
      years={years}
      operator={operator}
      onSaved={(next) =>
        go({
          to: '/ghg/inventory',
          search: { year: next },
          state: (old) => ({ ...old, ghgSaved: true }),
        })
      }
      onCancel={() => go({ to: '/ghg/inventory', search: { year } })}
      onYear={(next) =>
        go({
          to: '/ghg/inventory/index-settings',
          search: { year: next },
          replace: true,
        })
      }
      onOrganization={() => go({ to: '/ghg/organization' })}
    />
  );
}
