// 어드민 틀과 경로 컴포넌트(밴드 AD1). app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다 — 진입 청크에 어드민 화면이 들지 않는다.
//   - 틀(AdminLayout): AppShell(시안 AD-01_r1 의 LNB·머리 줄)·twp 바깥 div. 자식 경로가 <Outlet /> 자리에 화면을 그린다.
//     가드는 /admin 레이아웃 경로 하나의 beforeLoad 다(router.tsx). 자식 경로마다 달지 않는다(LG1 가지 리뷰 3).
//   - 머리 오른쪽: 인사말 + [로그아웃](shared/ui/header-greeting — 그린워싱 틀과 같은 표시 부품, critic 1 반영 B2). session.logout() 만 부르고
//     이동은 하지 않는다 — 세션이 비면 followSession 이 가드를 다시 돌려 /login 으로 넘긴다(app/auth/guard.ts).
//   - 메뉴(밴드 AD2 ① — AD1 가지 리뷰 4): MENU 항목마다 경로 to. 지금 화면(currentId)은 위치에서 MENU.find 한 줄, 누름은 그 항목의 to 로
//     navigate(항목 id 분기 없음 — to 를 바꾸면 이동도 바뀐다). <a href> 는 쓰지 않는다(쪽을 새로 읽으면 세션 밖 메모리가 사라진다).
//     AD-02~05 는 목 화면이라도 모든 빌드에서 켬(sid:MARC-ENT-285). 「서비스 화면」은 그린워싱 목록(/greenwash)으로 간다(밴드 SV1, sid:MARC-ENT-286).
//     「서비스 화면」은 LNB 맨 아래에 붙는다(AppShell 의 pinBottom — 밴드 WS2, 시안 admin-r1.css margin-top:auto).
//   - 「AI 설정」 하위 줄(밴드 LN1, sid:MARC-ENT-441): 모듈 다섯을 시안 차례로(시안 「Scope 3」 줄은 「온실가스」). 줄마다 제 주소
//     /admin/ai-settings/<모듈 id>(밴드 AM1, sid:MARC-ENT-444). 그린워싱만 켬, 나머지는 disabled — 그 모듈의 슬롯이 생기면 disabled 한 줄만 뗀다.
//     온실가스도 켬(밴드 AD7, sid:MARC-ENT-575) — 슬롯이 아니라 탭 껍데기 /admin/ai-settings/ghg(GhgSettingsRoute, 아래).
//     영문번역도 켬(밴드 TRA1 — 슬롯은 ai-setting-modules.ts 의 translationModule).
//     데이터 검증도 켬(밴드 DVA2 — 슬롯은 ai-setting-modules.ts 의 dataverifyModule).
//     중대성평가도 켬(밴드 IRA2 — 슬롯은 ai-setting-modules.ts 의 materialityModule).
//     보고서 작성은 새 줄로 끝에 더함(밴드 RPA3, sid:MARC-ENT-525 — 슬롯은 ai-setting-modules.ts 의 draftingModule).
//     꺼진 줄은 to 가 있어도 고르지 않는다(menuTarget). 지금 위치는 가장 긴 to 앞머리 맞춤(currentMenuId), 하위 줄을 먼저 본다.
//   - 「AI 설정 › 온실가스」 탭 껍데기(밴드 AD7, sid:MARC-ENT-575): /admin/ai-settings/ghg 아래 탭 둘 — 「온실가스 인덱스」 …/ghg/index(첫 탭·기본,
//     밴드 W12-0b1 ③ S19·S20 공통 풀 — GhgIndexRoute 가 풀 어댑터·코드 목록 어댑터를 짓는다) · 「선택항목」 …/ghg/options(밴드 W12-0a ③ S18 자산/시설명
//     및 코드 — OptionsRoute 가 세션 api 로 entities/ghg 의 코드 목록 어댑터를 짓는다). 위층 메뉴 두 줄은 뗐다. 옛 /admin/ghg-index·/admin/options 는
//     새 자리로 넘긴다(router.tsx 의 /admin beforeLoad). 탭 줄은 shared/ui/tabs(line) — 틀 머리 탭 줄 app/ghg/GhgRoutes.tsx ModuleTabs 꼴.
//   - AD-05 감사 기록(밴드 AD5R)·AD-04 실행 기록(밴드 AD4R)·AD-02 AI 설정(밴드 AD2R)의 경로 컴포넌트도 여기. AD-03 테스트 비교는 1차에서 뺐다(OPW1 ②, sid:MARC-ENT-362).
//   - AiSettingsRoute(밴드 AD2R, 모듈 슬롯 AD2W): 세션의 api 로 모듈 줄(ai-setting-modules.ts)을 지어 경로 칸 module 과 id 가 같은 슬롯 하나를
//     화면에 넘긴다(밴드 AM1). 없는 모듈이면 그린워싱 주소로 넘긴다(replace, version 은 버림). 처음 고를 판은 search version.
//     화면(껍데기)은 모듈을 import 하지 않는다(sid:MARC-ENT-386) — 모듈은 ai-setting-modules.ts 에 한 줄.
//     AD2W ③: 고친 채 메뉴·경로를 옮기면 useBlocker 가 막고 화면의 나가기 창으로 묻는다(화면은 onDirtyChange 로 알리고 leave 로 답을 받는다 —
//     pages 는 라우터를 모른다). 창 닫기·새로고침은 막지 않는다(enableBeforeUnload false — 발주서 Q8 (가)).
//   - AuditRoute(밴드 AD5R): 세션의 api 로 감사 기록 실어댑터를 만들어 화면에 넘긴다. 링크는 「계정」 → /admin/accounts.
//   - RunsRoute(밴드 AD4R): 세션의 api 로 실행 기록 실어댑터를 만들어 화면에 넘긴다. 모의 공급사 안내 띠는 화면이 서버 지표(aiProviderMock)로 정한다.
// 화면(pages)은 라우터를 모른다: 세션 저장소는 router context 에서 꺼내 콜백으로 넘긴다.
//   - AccountsRoute: 세션의 api(Bearer·444 refresh)로 계정 어댑터를 만들어 화면에 넘긴다. 전역 난수(crypto.getRandomValues)와
//     클립보드(navigator.clipboard.writeText)는 여기서 넣는다(entities·pages 는 전역을 모른다 — LG1 N8 과 같은 규칙).
//     계정 수정(사용 중지·이름 고침)도 실서버 PATCH 라 모든 빌드에서 같다(UA1W — 목 덧칠을 걷었다).
import { useCallback, useMemo, useRef } from 'react';

import {
  ChartSquareIcon,
  FileCheckIcon,
  LinkOpenIcon,
  SettingIcon,
  UserIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import {
  Navigate,
  Outlet,
  getRouteApi,
  useBlocker,
  useLocation,
  useNavigate,
  useRouter,
} from '@tanstack/react-router';

import { createAccountsPort } from '../../entities/account/api/index.ts';
import { ACCOUNT_TEXT } from '../../entities/account/config/text.ts';
import { createAuditServerPort } from '../../entities/audit-log/api/index.ts';
import { createFacilityCodeAdminPort } from '../../entities/ghg/api/index.ts';
import { createGhgPoolAdminPort } from '../../entities/ghg/api/index.ts';
import { createRunLogServerPort } from '../../entities/run-log/api/index.ts';
import { AccountsScreen } from '../../pages/admin-accounts/index.ts';
import { AiSettingsScreen } from '../../pages/admin-ai-settings/index.ts';
import { AuditScreen } from '../../pages/admin-audit/index.ts';
import { RunsScreen } from '../../pages/admin-runs/index.ts';
import { FacilityCodesScreen } from '../../pages/ghg-facility-codes/index.ts';
import { GhgIndexPoolScreen } from '../../pages/ghg-index-pool/index.ts';
import { AppShell } from '../../shared/ui/app-shell/index.ts';
import type {
  AppShellMenuItem,
  AppShellSubItem,
} from '../../shared/ui/app-shell/index.ts';
import { PageTitle } from '../../shared/ui/card/index.ts';
import { HeaderGreeting } from '../../shared/ui/header-greeting/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../shared/ui/tabs/index.ts';
import { aiSettingModules, aiSettingTitle } from './ai-setting-modules.ts';

const rootApi = getRouteApi('__root__');
const aiSettingsApi = getRouteApi('/admin/ai-settings/$module');

const shell = ACCOUNT_TEXT.shell;

/** 어드민 하위 줄: AppShell 의 하위 줄 + 경로(없으면 꺼진 줄). */
type AdminSubItem = AppShellSubItem & { to?: AdminPath };
/** 어드민 메뉴 항목: AppShell 의 항목 + 그 항목의 경로(없으면 꺼진 항목). */
type AdminMenuItem = Omit<AppShellMenuItem, 'children'> & {
  to?: AdminPath;
  children?: readonly AdminSubItem[];
};
/** AD-02 모듈 칸 낱말(하위 줄 id 꼬리와 같다 — 슬롯 id 도 이 낱말, ai-setting-modules.ts). */
type AiSettingModuleId =
  | 'greenwash'
  | 'ghg'
  | 'materiality'
  | 'dataverify'
  | 'translation'
  | 'drafting';
/** 「AI 설정 › 온실가스」 탭 껍데기의 주소(밴드 AD7 — 모듈 칸 $module 이 아니라 고정 경로 ghg, router.tsx). */
const GHG_SETTINGS = '/admin/ai-settings/ghg';
type GhgSettingsPath =
  | typeof GHG_SETTINGS
  | `${typeof GHG_SETTINGS}/index`
  | `${typeof GHG_SETTINGS}/options`;
type AdminPath =
  | '/admin/accounts'
  | `/admin/ai-settings/${Exclude<AiSettingModuleId, 'ghg'>}`
  | GhgSettingsPath
  | '/admin/runs'
  | '/admin/audit'
  | '/greenwash';

/** AD-02 의 처음 주소(부모 「AI 설정」·없는 모듈이 가는 곳 — router.tsx 의 AI_SETTINGS_HOME_MODULE 과 같다. 경로 시험이 견준다). */
export const AI_SETTINGS_HOME =
  '/admin/ai-settings/greenwash' satisfies AdminPath;

/** 온실가스 탭 껍데기 주소인가(모듈 칸으로 펴지 않는다 — 밴드 AD7). */
const isGhgSettingsPath = (to: AdminPath): to is GhgSettingsPath =>
  to === GHG_SETTINGS || to.startsWith(`${GHG_SETTINGS}/`);

/** 온실가스 탭 껍데기의 탭 둘(밴드 AD7 — 첫 탭이 기본). 이름은 옛 메뉴 글 그대로. 탭을 더하면 이 줄과 router.tsx 의 자식 경로를 함께. */
export const GHG_SETTINGS_TABS = [
  {
    value: 'index',
    label: shell.menu.ghgIndex,
    to: `${GHG_SETTINGS}/index`,
  },
  {
    value: 'options',
    label: shell.menu.options,
    to: `${GHG_SETTINGS}/options`,
  },
] as const satisfies readonly {
  value: string;
  label: string;
  to: GhgSettingsPath;
}[];

/** AD-02 모듈 주소인가(아래 adminLocation 이 경로 칸으로 가른다). 온실가스 탭 껍데기는 아니다. */
const isAiSettingsPath = (
  to: AdminPath,
): to is `/admin/ai-settings/${Exclude<AiSettingModuleId, 'ghg'>}` =>
  to.startsWith('/admin/ai-settings/') && !isGhgSettingsPath(to);

/**
 * AdminPath → 이동할 위치. TanStack 의 to 는 경로 틀 글자만 받아서 AD-02 모듈 주소는 틀 /admin/ai-settings/$module + params 로 편다(밴드 AM1).
 */
export const adminLocation = (to: AdminPath) =>
  isAiSettingsPath(to) ?
    ({
      to: '/admin/ai-settings/$module',
      params: { module: to.slice('/admin/ai-settings/'.length) },
    } as const)
  : ({ to } as const);

/** 어드민 메뉴. 아이콘은 키트 아이콘(시안의 선 아이콘과 꼴이 다르다). */
export const MENU: readonly AdminMenuItem[] = [
  {
    id: 'accounts',
    label: shell.menu.accounts,
    icon: <UserIcon aria-hidden />,
    to: '/admin/accounts',
  },
  {
    id: 'ai-settings',
    label: shell.menu.aiSettings,
    icon: <SettingIcon aria-hidden />,
    to: AI_SETTINGS_HOME,
    childrenLabel: shell.aiSettingsModulesLabel,
    children: [
      {
        id: 'ai-settings-greenwash',
        label: shell.menu.aiSettingsGreenwash,
        to: '/admin/ai-settings/greenwash',
      },
      // 밴드 AD7(sid:MARC-ENT-575): 탭 껍데기 주소 — /admin beforeLoad 가 첫 탭(…/ghg/index)으로 넘기고, to 가 껍데기라 두 탭 어디서든
      // 이 줄이 켜진다(currentMenuId 앞머리 맞춤 — to 를 …/index 로 두면 「선택항목」 탭에서 꺼진다).
      {
        id: 'ai-settings-ghg',
        label: shell.menu.aiSettingsGhg,
        to: GHG_SETTINGS,
      },
      {
        id: 'ai-settings-materiality',
        label: shell.menu.aiSettingsMateriality,
        to: '/admin/ai-settings/materiality',
      },
      {
        id: 'ai-settings-dataverify',
        label: shell.menu.aiSettingsDataverify,
        to: '/admin/ai-settings/dataverify',
      },
      {
        id: 'ai-settings-translation',
        label: shell.menu.aiSettingsTranslation,
        to: '/admin/ai-settings/translation',
      },
      {
        id: 'ai-settings-drafting',
        label: shell.menu.aiSettingsDrafting,
        to: '/admin/ai-settings/drafting',
      },
    ],
  },
  {
    id: 'runs',
    label: shell.menu.runs,
    // 키트 BarIcon 은 LNB 선택 막대(4×48)라 메뉴 아이콘이 아니다(밴드 DT1 C7).
    icon: <ChartSquareIcon aria-hidden />,
    to: '/admin/runs',
  },
  {
    id: 'audit',
    label: shell.menu.audit,
    icon: <FileCheckIcon aria-hidden />,
    to: '/admin/audit',
  },
  {
    id: 'service',
    label: shell.menu.service,
    icon: <LinkOpenIcon aria-hidden />,
    to: '/greenwash',
    pinBottom: true,
  },
];

/** 하위 줄을 먼저, 그다음 위 항목 차례로 편다(LN1). */
const flatMenu = (
  menu: readonly AdminMenuItem[],
): readonly (AdminMenuItem | AdminSubItem)[] => [
  ...menu.flatMap((item) => item.children ?? []),
  ...menu,
];

/**
 * 메뉴 항목(하위 줄 포함) id → 갈 경로(그 항목의 to). to 가 없거나 꺼진 항목이거나 모르는 id 면 undefined — 경로를 id 로 짓지 않는다(①② 검증 사소 1).
 * 꺼진 줄은 to 가 있어도 고르지 않는다(밴드 AM1 — AppShell 도 막지만 함수도).
 */
export const menuTarget = (
  menu: readonly AdminMenuItem[],
  id: string,
): AdminPath | undefined => {
  const item = flatMenu(menu).find((row) => row.id === id);
  return item?.disabled ? undefined : item?.to;
};

/**
 * 메뉴 누름 처리기(③ 검증 블로커 1). 누른 항목의 to(menuTarget)로만 go 를 부르고, to 가 없거나 모르는 id 면 부르지 않는다.
 * AdminLayout 의 onSelect 는 이것 하나다 — 처리기 안에서 경로를 짓지 않게 시험이 가짜 go 로 본다.
 */
export const onMenuSelect =
  (menu: readonly AdminMenuItem[], go: (to: AdminPath) => void) =>
  (id: string) => {
    const to = menuTarget(menu, id);
    if (to) go(to);
  };

/**
 * 지금 위치의 메뉴 항목 id(그 항목의 to 이거나 그 아래). 맞는 것 가운데 가장 긴 to(밴드 AM1 — 하위 줄 주소가 부모 to 와 겹쳐도 제 줄이 켜지게),
 * 길이가 같으면 하위 줄을 먼저 본다. 맞는 것이 없으면 undefined.
 */
export const currentMenuId = (
  pathname: string,
  menu: readonly AdminMenuItem[] = MENU,
) =>
  flatMenu(menu).reduce<AdminMenuItem | AdminSubItem | undefined>(
    (best, item) =>
      (
        item.to &&
        (pathname === item.to || pathname.startsWith(`${item.to}/`)) &&
        item.to.length > (best?.to?.length ?? -1)
      ) ?
        item
      : best,
    undefined,
  )?.id;

export function AdminLayout() {
  const { session } = rootApi.useRouteContext();
  const navigate = useNavigate();
  const pathname = useLocation({ select: (location) => location.pathname });
  const logout = () => session.logout();
  return (
    <div className="twp">
      <AppShell
        menu={MENU}
        currentId={currentMenuId(pathname)}
        onSelect={onMenuSelect(MENU, (to) => void navigate(adminLocation(to)))}
        menuLabel={shell.menuLabel}
        logo={shell.logo}
        title={
          <>
            {shell.title}
            <span className="ml-2 inline-flex h-5 items-center rounded-control bg-support-orange-subtle px-1.5 align-middle text-style-pre-caption-01 text-support-orange-dark">
              {shell.staff}
            </span>
          </>
        }
        headerRight={
          <HeaderGreeting greeting={shell.greeting} onLogout={logout} />
        }
        className="min-h-screen"
      >
        <Outlet />
      </AppShell>
    </div>
  );
}

/** 난수 함수: 브라우저의 암호 난수. */
const random = (array: Uint32Array) => globalThis.crypto.getRandomValues(array);
/** 클립보드에 쓰기(실패는 화면이 글로 알린다). */
const copy = (text: string) => globalThis.navigator.clipboard.writeText(text);

/** AD-01 계정 관리. 표식 data-screen 은 화면이 단다(LG1 의 경로 시험이 찾는다). */
export function AccountsRoute() {
  const { session } = rootApi.useRouteContext();
  // 실서버 넷(목록·만들기·초기화·계정 수정 — UA1W). 모든 빌드에서 같다(MARC-ENT-285 — 서버가 와서 목을 걷었다).
  const port = useMemo(
    () => createAccountsPort({ api: session.api, random }),
    [session],
  );
  return <AccountsScreen port={port} copy={copy} />;
}

/** 감사 기록 화면이 넘기는 링크(머리 import 를 늘리지 않으려 화면 props 에서 뽑는다 — 같은 트랙 AD2W 와 붙은 줄 충돌을 피함). */
type AuditLink = Parameters<Parameters<typeof AuditScreen>[0]['hrefOf']>[0];

/**
 * 감사 기록 링크의 주소: 「계정」 → AD-01, 「AI 설정」 → AD-02 의 그 줄 모듈 주소(module 이 null 이면 그린워싱 — 밴드 AM1, sid:MARC-ISSUE-291)
 * + 판이 있으면 ?version=v<n>, 없으면 쿼리 없이(밴드 AD4X ③). 화면·model 은 라우터를 모른다 — 주소는 여기서 link.kind 로 짓는다.
 * 모르는 모듈 낱말이어도 그대로 싣는다 — AD-02 가 없는 모듈을 그린워싱으로 넘긴다.
 */
export function auditTarget(link: AuditLink) {
  return link.kind === 'accounts' ?
      ({ to: '/admin/accounts' } as const)
    : ({
        to: '/admin/ai-settings/$module',
        params: { module: link.module ?? 'greenwash' },
        search: link.version === null ? {} : { version: link.version },
      } as const);
}

/** AD-05 감사 기록(읽기 화면 — 쓰기 단추 없음). 세션의 api(Bearer·444 refresh)로 감사 어댑터를 만들어 화면에 넘긴다. 시계는 화면의 기본(지금). */
export function AuditRoute() {
  const { session } = rootApi.useRouteContext();
  const port = useMemo(
    () => createAuditServerPort({ api: session.api }),
    [session],
  );
  const router = useRouter();
  const navigate = useNavigate();
  return (
    <AuditScreen
      port={port}
      hrefOf={(link) => router.buildLocation(auditTarget(link)).href}
      onOpen={(link) => void navigate(auditTarget(link))}
    />
  );
}

/**
 * AD-04 실행 기록·지표(읽기 화면 — 쓰기 단추 없음). 세션의 api(Bearer·444 refresh)로 실행 기록 어댑터를 만들어 화면에 넘긴다.
 * 시계는 화면의 기본(지금). 모의 공급사 안내 띠는 화면이 서버 지표 aiProviderMock 으로 정한다(빌드 값 아님 — MP1W).
 */
export function RunsRoute() {
  const { session } = rootApi.useRouteContext();
  const port = useMemo(
    () => createRunLogServerPort({ api: session.api }),
    [session],
  );
  return <RunsScreen port={port} />;
}

/**
 * AD-02 AI 설정(밴드 AD2R — 실서버, AD2W — 모듈 슬롯). 세션의 api(Bearer·444 refresh)로 모듈 줄을 지어 화면에 넘긴다.
 * 모든 빌드에서 같다(운영 관리자 경로 — 데모 덧칠·쓰기 끔 갈래 없음, 발주서 Q12). 처음 고를 판은 search version(「v숫자」만).
 */
export function AiSettingsRoute() {
  const { session } = rootApi.useRouteContext();
  const { module } = aiSettingsApi.useParams();
  const { version } = aiSettingsApi.useSearch();
  const modules = useMemo(() => aiSettingModules(session.api), [session]);
  const slot = modules.find(({ id }) => id === module);
  const dirty = useRef(false);
  const blocker = useBlocker({
    shouldBlockFn: () => dirty.current,
    withResolver: true,
    enableBeforeUnload: false,
  });
  const onDirtyChange = useCallback((now: boolean) => {
    dirty.current = now;
  }, []);
  // 슬롯이 아직 없는 모듈·모르는 낱말 → 그린워싱(replace, version 은 버린다). 화면을 그리지 않으니 고친 것이 없다.
  if (!slot) return <Navigate {...adminLocation(AI_SETTINGS_HOME)} replace />;
  return (
    <AiSettingsScreen
      // 모듈을 바꾸면 고친 것·고른 판이 새로(밴드 AM1).
      key={module}
      modules={[slot]}
      initialVersion={version}
      onDirtyChange={onDirtyChange}
      leave={{
        pending: blocker.status === 'blocked',
        proceed: () => blocker.proceed?.(),
        reset: () => blocker.reset?.(),
      }}
    />
  );
}

/**
 * AI 설정 › 온실가스 탭 껍데기(밴드 AD7, sid:MARC-ENT-575). 탭 줄(지금 경로 앞머리로 고른 탭, 누르면 push) + 자식 경로 자리.
 * 머리는 껍데기가 그린다 — 다른 AI 설정과 같은 글(aiSettingTitle)로 탭 줄 위에, 탭 안 화면은 제목을 그리지 않는다(밴드 AD8, sid:MARC-ISSUE-575).
 * 안내 한 줄은 없다(AI_SETTING_TEXT.description 은 버전 글이라 이 화면 몫이 아니다).
 */
export function GhgSettingsRoute() {
  const pathname = useLocation({ select: (location) => location.pathname });
  const navigate = useNavigate();
  const current = GHG_SETTINGS_TABS.find(
    (tab) => pathname === tab.to || pathname.startsWith(`${tab.to}/`),
  );
  return (
    <div className="flex flex-col gap-6">
      <PageTitle title={aiSettingTitle(shell.menu.aiSettingsGhg)} />
      <Tabs
        value={current?.value ?? ''}
        onValueChange={(value) => {
          const tab = GHG_SETTINGS_TABS.find((one) => one.value === value);
          if (tab) void navigate({ to: tab.to });
        }}
      >
        <TabsList aria-label={shell.menu.aiSettingsGhg}>
          {GHG_SETTINGS_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <Outlet />
    </div>
  );
}

/** 설정 > 선택항목 > 자산/시설명 및 코드(밴드 W12-0a ③ — S18). 세션의 api 로 온실가스 코드 목록 어댑터를 만들어 화면에 넘긴다(AuditRoute·RunsRoute 꼴). */
export function OptionsRoute() {
  const { session } = rootApi.useRouteContext();
  const port = useMemo(
    () => createFacilityCodeAdminPort({ api: session.api }),
    [session],
  );
  return <FacilityCodesScreen port={port} />;
}

/** 인벤토리 관리 > 온실가스 인덱스(밴드 W12-0b1 ③ — S19·S20). 세션의 api 로 풀 어댑터와 코드 목록 어댑터(★G)를 만들어 화면에 넘긴다(OptionsRoute 꼴).
 *  S20 기준연도 드롭다운의 끝(올해)은 여기서 넣는다(pages 는 전역 시계를 모른다). */
export function GhgIndexRoute() {
  const { session } = rootApi.useRouteContext();
  const ports = useMemo(
    () => ({
      pool: createGhgPoolAdminPort({ api: session.api }),
      codes: createFacilityCodeAdminPort({ api: session.api }),
    }),
    [session],
  );
  const thisYear = useMemo(() => new Date().getFullYear(), []);
  return (
    <GhgIndexPoolScreen
      port={ports.pool}
      codes={ports.codes}
      thisYear={thisYear}
    />
  );
}
