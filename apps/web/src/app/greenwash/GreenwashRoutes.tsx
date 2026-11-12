// 그린워싱 틀과 경로 컴포넌트(밴드 RT1 §1-3·1-4). app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다 — 진입 청크에 그린워싱이 들지 않는다.
// 옛 GreenwashPage(쿼리 읽기·목 저장소·pdfjs)와 GreenwashApp(셸·화면 전환)을 합쳐 옮겼다.
//   - 틀(GreenwashLayout): AppShell(메뉴 여섯 — app/shell/moduleMenu.tsx 한 자리, 그린워싱·데이터 검증·영문번역 켬)·twp 바깥 div·저장소의 수명. 자식 경로가 <Outlet /> 자리에 화면을 그린다.
//     저장소는 틀이 처음 그려질 때 한 번 만든다. router context 의 GreenwashRuntime 에 두어 화면 사이 이동에서 살아남는다.
//     밴드 GW1R ②: 기본은 실어댑터(세션 Api·서명 PUT·pdf.js 쪽 세기를 여기서 넣는다). 목은 데모 빌드(context.admin.demos)의 탭 표지 뒤로만 —
//     첫 주소의 store=mock(또는 옛 mock=·demo=·autofinish=)이 sessionStorage 에 표지를 적고, 그때의 search 로 목을 만든다.
//     목·어댑터는 DOM·location 을 모른다: search·보관소·전역 통신은 여기서 읽어 넘긴다.
//   - 경로 컴포넌트(…Route): 화면(pages)은 라우터를 모른다. 화면의 콜백 props(onBack·onViewResult·onOpen…)를 여기서 navigate 로 잇는다.
//     params 는 getRouteApi 로 얻는다(router.tsx 와 순환 import 를 피한다).
// 이동 규칙(push / replace)은 발주서 §1-4: GW-02 시작 → GW-03, GW-03 끝남 → GW-04 는 replace. 나머지는 push.
// GW-04 [확정] → GW-05 는 05b(확정 확인)를 연 채 시작한다 — 표식은 GreenwashRuntime.confirmRunId(메모리)로만 넘긴다.
//   GW-05 경로는 useState 초기값에서 표식을 읽기만 하고, 지우기는 마운트 effect 에서 한다(렌더 중에 지우면 dev StrictMode 의 두 번 렌더에서 05b 가 사라진다).
//   다른 모든 이동(go)도 표식을 지운다.
// 메뉴 「그린워싱 점검」은 목록으로 간다. GW-00 은 목록 제목 줄의 「점검 안내」로 들어간다(시안 GW-01_r2, GW3R A8 — 옛 [R9] 「링크 두지 않음」을 갈음).
// 운영 관리자(kind=admin)도 이 틀을 연다(밴드 SV1, sid:MARC-ENT-286). 머리 인사말이 「운영 관리자님 안녕하세요」이고 인사말과 [로그아웃] 사이에
//   [관리자 화면](→ AD-01 계정 관리)이 있다. 갈래는 세션 스냅샷(useSession)에서 틀이 읽는다 — 화면(pages)은 세션을 모른다.
// 데모 띠(밴드 GW2R ② — sid:MARC-ISSUE-227 ①, 디자인 답 4ca4edef): 목 탭 표지가 켜진 탭(mockTab — 데모 빌드만)은 화면 머리에 흰 바탕 정보 띠
//   「데모 자료예요. …」(AD-04 ai-mock-notice 와 같은 꼴 — 공용 PageInfo 0줄). 실서버 탭에는 없다. 표지는 틀이 처음 그려질 때 한 번 읽는다.
// 운영 관리자도 고객사 사용자와 같이 쓴다(업로드·실행·검토 확정 — sid:MARC-ENT-374 3·4번, 화면 꼴 sid:MARC-ENT-409. 밴드 GR3 이 SV1 읽기 전용을 걷음).
//   갈래 고르기는 greenwashAccess 하나다: 로그인한 세션이면 canWrite 참. 거짓은 로그인하지 않은 세션뿐(로그아웃 직후 가드가 넘기기 전) —
//   쓰기 단추(새 점검·시작하기·다시 실행·확정·채택·제외)를 숨기고 /greenwash/new 는 목록으로 replace. 운영 관리자만 다른 것은 머리 인사말·
//   [관리자 화면]·목록의 「내가 올린 것만」 숨김·목록 meta(작업 회사) — useOperator 로 가른다.
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ComponentProps } from 'react';

import { ArrowLeftIcon } from '@marcspon/common/generated/icons/MyIcons';
import {
  Navigate,
  Outlet,
  getRouteApi,
  useNavigate,
  useParams,
} from '@tanstack/react-router';
import type { NavigateOptions } from '@tanstack/react-router';

import {
  StoreError,
  createGreenwashServerStore,
} from '../../entities/greenwash/api/index.ts';
import type { GreenwashStore } from '../../entities/greenwash/api/index.ts';
import {
  MOCK_SCENARIOS,
  createMockStore,
} from '../../entities/greenwash/api/mock/index.ts';
import { GW_TEXT } from '../../entities/greenwash/config/text.ts';
import { useSession } from '../../entities/session/hooks/index.ts';
import { IntroScreen } from '../../pages/greenwash-intro/index.ts';
import { ListScreen } from '../../pages/greenwash-list/index.ts';
import { NewCheckScreen } from '../../pages/greenwash-new/index.ts';
import { ResultScreen } from '../../pages/greenwash-result/index.ts';
import { ReviewScreen } from '../../pages/greenwash-review/index.ts';
import { StatusScreen } from '../../pages/greenwash-status/index.ts';
import { AppShell } from '../../shared/ui/app-shell/index.ts';
import { Button } from '../../shared/ui/button/index.ts';
import { HeaderGreeting } from '../../shared/ui/header-greeting/index.ts';
import { PageInfo, PageInfoIcon } from '../../shared/ui/page-info/index.ts';
import type { OpenPdf } from '../../widgets/doc-viewer/index.ts';
import {
  countPdfPages,
  openPdf as pdfjsOpenPdf,
} from '../../widgets/doc-viewer/pdfjs.ts';
import { moduleMenu, moduleTarget } from '../shell/moduleMenu.tsx';
import type {
  CreateGreenwashStore,
  GreenwashRuntime,
  GreenwashSearch,
} from './runtime.ts';

/** 데모 모드의 한 걸음 간격(ms). */
const DEMO_INTERVAL_MS = 400;
/** &autofinish=1 일 때 새 실행이 끝나기까지(ms). GW-03 을 한 번 그린 뒤 끝나게 짧게 둔다. */
const AUTOFINISH_MS = 300;

/** 목 저장소를 쓰는 탭의 표지(sessionStorage — 탭마다, 새로고침·`/` 경유에도 남는다. 밴드 GW1R Q1). */
export const MOCK_TAB_KEY = 'esg.gw.store';
const MOCK_TAB_VALUE = 'mock';

/**
 * 이 탭이 목 저장소를 쓰는가. 데모 빌드(context.admin.demos)에서만: 첫 주소에 store=mock(또는 옛 mock=·demo=·autofinish=)이 있으면
 * 표지를 적고 참, 없으면 표지를 읽는다. demos 가 거짓이면 표지·search 를 모두 무시한다(프로덕션에서 ?mock=done 이 먹지 않게).
 * 보관소를 쓸 수 없으면(사생활 모드 등) 그 주소의 search 만 본다.
 */
export function mockTab(search: GreenwashSearch, demos: boolean): boolean {
  if (!demos) return false;
  const asked =
    search.store === 'mock' ||
    search.mock !== undefined ||
    search.demo !== undefined ||
    search.autofinish !== undefined;
  try {
    if (asked) globalThis.sessionStorage.setItem(MOCK_TAB_KEY, MOCK_TAB_VALUE);
    return (
      asked ||
      globalThis.sessionStorage.getItem(MOCK_TAB_KEY) === MOCK_TAB_VALUE
    );
  } catch {
    return asked;
  }
}

/** 서명 주소로 파일 본문을 올린다. 세션의 Api 를 거치지 않는다 — Authorization 을 싣지 않는다(서명이 권한이다). */
export async function sendUpload(
  url: string,
  method: string,
  file: File,
): Promise<void> {
  // 쿠키·리퍼러·캐시를 싣지 않는다(서명 주소는 저장소 출처 — 밴드 GW1R ⑤ S1).
  const response = await globalThis.fetch(url, {
    method,
    body: file,
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    cache: 'no-store',
  });
  // 앞단 프록시의 413(본문 한도)은 크기 갈래로 — 다시 해도 같다(GP1 §1-8).
  if (response.status === 413)
    throw new StoreError('too_large', '올리기 실패 413');
  if (!response.ok) throw new Error(`올리기 실패 ${response.status}`);
}

/** 목 탭 표지를 지운다(보관소를 쓸 수 없으면 그대로). */
function clearMockTab() {
  try {
    globalThis.sessionStorage.removeItem(MOCK_TAB_KEY);
  } catch {
    // 보관소가 없으면 지울 것도 없다.
  }
}

/** 세션 스냅샷을 읽고 바뀜을 받는 것(세션 저장소의 표면 둘 — 구독만 한다). */
interface SessionFeed {
  getSnapshot(): { status: string };
  subscribe(listener: () => void): () => void;
}

/**
 * 세션이 끝날 때마다(signedIn 을 벗어나는 전이 — 로그아웃·만료·사용 중지) end 를 한 번 부른다(밴드 GW1R ⑤ M3·M4).
 * 다시 로그인했다 끝나면 또 한 번. 해제 함수를 돌려준다.
 */
export function followSessionEnd(session: SessionFeed, end: () => void) {
  let signedIn = session.getSnapshot().status === 'signedIn';
  return session.subscribe(() => {
    const now = session.getSnapshot().status === 'signedIn';
    if (signedIn && !now) end();
    signedIn = now;
  });
}

/** 고른 파일의 쪽 수(pdf.js). 다 세면 object URL 을 놓는다. */
async function countPages(file: File): Promise<number> {
  const url = URL.createObjectURL(file);
  try {
    return await countPdfPages(url);
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * 기본 저장소(밴드 GW1R ②): 실어댑터. 목은 데모 빌드의 탭 표지 뒤로만(deps.mock — 틀이 mockTab 으로 정한다).
 * 목이면 search 의 mock= 은 router.tsx 가 글자 목록으로 걸렀고, 여기서 MOCK_SCENARIOS 로 한 번 더 고른다.
 * 실어댑터 실패를 목으로 메우지 않는다.
 */
export const createDefaultStore: CreateGreenwashStore = (search, deps) => {
  if (deps.mock)
    return createMockStore({
      scenario: MOCK_SCENARIOS.find((scenario) => scenario === search.mock),
      demoIntervalMs: search.demo === '1' ? DEMO_INTERVAL_MS : undefined,
      autoFinishMs: search.autofinish === '1' ? AUTOFINISH_MS : undefined,
    });
  const server = createGreenwashServerStore(deps);
  return {
    store: server.store,
    // 폴링은 구독마다 돈다(해제는 화면이) — 틀이 켜고 끌 타이머가 없다.
    start: () => {},
    stop: () => {},
    forget: server.forget,
  };
};

const layoutApi = getRouteApi('/greenwash');
const statusApi = getRouteApi('/greenwash/runs/$runId');
const resultApi = getRouteApi('/greenwash/runs/$runId/result');
const reviewApi = getRouteApi('/greenwash/runs/$runId/review');

const shell = GW_TEXT.shell;

const MENU = moduleMenu(shell.menu);

/** 세션 스냅샷의 꼴(세션 model 의 타입을 따로 가져오지 않는다 — 층 넓힘 없이 훅의 반환에서). */
type SessionSnapshot = ReturnType<typeof useSession>;

/**
 * 갈래 고르기 하나: 로그인한 세션(고객사 사용자·운영 관리자 — sid:MARC-ENT-374 3번)은 쓴다(canWrite). 저장소는 그대로 넘긴다 —
 * 읽기 전용 저장소(밴드 SV1)는 걷었다(밴드 GR3). 로그인하지 않은 세션의 쓰기는 서버가 401 로 막는다.
 * 경로 컴포넌트는 이 결과만 화면에 넘긴다.
 */
export function greenwashAccess(
  state: SessionSnapshot,
  store: GreenwashStore,
): { canWrite: boolean; store: GreenwashStore } {
  return { canWrite: state.status === 'signedIn', store };
}

/**
 * 그린워싱의 메모리 칸·화면에 넘길 저장소와 쓰기 켬·PDF 여는 구현(router context 에서). 저장소는 틀이 만든 뒤에만 있다.
 * 저장소는 늘 greenwashAccess 를 거친다 — control 자체는 감싸지 않는다(같은 탭에서 다른 사람이 다시 로그인할 수 있다, 렌더마다 갈래로 고름).
 */
function useGreenwash(): {
  runtime: GreenwashRuntime;
  store: GreenwashStore;
  canWrite: boolean;
  openPdf: OpenPdf;
} {
  const context = layoutApi.useRouteContext();
  const runtime = context.greenwash;
  const state = useSession(context.session);
  const control = runtime.control;
  const access = useMemo(
    () => (control ? greenwashAccess(state, control.store) : null),
    [state, control],
  );
  if (!access) throw new Error('그린워싱 저장소가 없다(틀이 먼저 그려진다)');
  return {
    runtime,
    store: access.store,
    canWrite: access.canWrite,
    openPdf: context.openPdf ?? pdfjsOpenPdf,
  };
}

/**
 * 지금 세션이 운영 관리자인가(세션 스냅샷이 바뀌면 다시 그린다). 머리 인사말·[관리자 화면]·목록의 「내가 올린 것만」 숨김과 meta 만
 * 이것으로 가른다(sid:MARC-ENT-409 남김). 쓰기 켬은 greenwashAccess(로그인했는가)가 가른다 — 운영 관리자도 쓴다.
 */
function useOperator(): boolean {
  const state = useSession(layoutApi.useRouteContext().session);
  return state.status === 'signedIn' && state.user.kind === 'admin';
}

/** 이동 하나. [확정] 표식을 지우고 navigate 한다(표식을 싣는 것은 GW-04 [확정] 하나뿐 — confirm 인자). 렌더 사이에 같은 함수다. */
function useGo() {
  const navigate = useNavigate();
  const runtime = layoutApi.useRouteContext().greenwash;
  return useCallback(
    (options: NavigateOptions, confirmRunId: string | null = null) => {
      runtime.confirmRunId = confirmRunId;
      void navigate(options);
    },
    [navigate, runtime],
  );
}

export function GreenwashLayout() {
  const context = layoutApi.useRouteContext();
  const search = layoutApi.useSearch();
  const runtime = context.greenwash;
  // 목 탭인가(데모 띠와 저장소 고르기가 같은 답을 쓴다 — 처음 그려질 때 한 번).
  const [demo] = useState(() => mockTab(search, context.admin.demos));
  // 처음 그려질 때 한 번(StrictMode 의 두 번 부르기에도 ??= 로 하나).
  const [control] = useState(() => {
    if (runtime.control) return runtime.control;
    const made = (context.createStore ?? createDefaultStore)(search, {
      api: context.session.api,
      sendUpload,
      countPages,
      mock: demo,
    });
    runtime.control = made;
    // 세션이 끝나면(로그아웃만이 아니라 만료·사용 중지도) 이 탭에서 올린 File·쪽 수를 비우고 목 표지를 지운다(Q11, M3·M4).
    // 구독은 저장소와 같이 라우터 수명이다 — 틀이 내려간 뒤(가드가 /login 으로 넘김) 끝나도 받는다.
    followSessionEnd(context.session, () => {
      made.forget?.();
      clearMockTab();
    });
    return made;
  });
  useEffect(() => {
    control.start();
    return () => control.stop();
  }, [control]);
  const go = useGo();
  const operator = useOperator();
  // 실행을 보는 화면에서만 있다(목록·새 점검·소개에선 없다).
  const { runId } = useParams({ strict: false });
  // 이 탭에서 올린 File·센 쪽 수와 목 표지는 세션 끝 구독이 비운다(위 followSessionEnd — 로그아웃도 세션 끝이다).
  const logout = () => {
    return context.session.logout();
  };

  return (
    <div className="twp" data-run-id={runId}>
      <AppShell
        menu={MENU}
        currentId="greenwash"
        onSelect={(id) => {
          const to = moduleTarget(id);
          if (to) go({ to });
        }}
        menuLabel={shell.menuLabel}
        logo={shell.logo}
        title={shell.title}
        headerRight={
          // 인사말 + [로그아웃](밴드 AD1 — 감독 판단 6 의 예외 한 자리). 이동은 followSession → 가드가 한다.
          // 운영 관리자만 사이에 [관리자 화면](디자인 원문: md outline-grey round, 왼쪽 화살표 16 — 밴드 SV1).
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
            onLogout={logout}
          />
        }
        className="min-h-screen"
      >
        {demo && (
          // 흰 바탕 정보 띠(AD-04 ai-mock-notice 꼴 — 바탕만 카드와 같은 흰 surface·모서리 16)
          <PageInfo
            icon={<PageInfoIcon />}
            data-testid="gw-demo-notice"
            className="mb-6 rounded-dialog bg-background-primary"
          >
            {shell.demoNotice}
          </PageInfo>
        )}
        <Outlet />
      </AppShell>
    </div>
  );
}

type ListTarget = Parameters<ComponentProps<typeof ListScreen>['onOpen']>[0];

/** 목록의 줄·다음 할 일이 고른 실행 화면. */
function openTarget(target: ListTarget): NavigateOptions {
  const params = { runId: target.runId };
  switch (target.screen) {
    case 'status':
      return { to: '/greenwash/runs/$runId', params };
    case 'result':
      return { to: '/greenwash/runs/$runId/result', params };
    case 'review':
      return { to: '/greenwash/runs/$runId/review', params };
  }
}

export function ListRoute() {
  const { store, canWrite } = useGreenwash();
  const operator = useOperator();
  const go = useGo();
  return (
    <ListScreen
      store={store}
      canWrite={canWrite}
      operator={operator}
      onNewCheck={() => go({ to: '/greenwash/new' })}
      onOpen={(target) => go(openTarget(target))}
      onIntro={() => go({ to: '/greenwash/intro' })}
    />
  );
}

export function IntroRoute() {
  const { canWrite } = useGreenwash();
  const go = useGo();
  return (
    <IntroScreen
      canWrite={canWrite}
      // [시작하기]는 문서 목록으로(기존 점검을 먼저 보게 — 시안 댓글, sid:MARC-ENT-603). 빈 목록이면 거르기 줄의 [새 점검]이 있다.
      onStart={() => go({ to: '/greenwash' })}
    />
  );
}

export function NewCheckRoute() {
  const { store, canWrite, openPdf } = useGreenwash();
  const go = useGo();
  // 쓰지 못하는 세션(로그인하지 않음)이 주소로 열면 목록으로 replace(감독 판단 7 — beforeLoad 를 달지 않고 경로 컴포넌트에서). 운영 관리자는 연다.
  if (!canWrite) return <Navigate to="/greenwash" replace />;
  return (
    <NewCheckScreen
      store={store}
      openPdf={openPdf}
      onCancel={() => go({ to: '/greenwash' })}
      // replace: 뒤로 가기로 다 쓴 양식에 돌아가지 않게.
      onStarted={(id) =>
        go({
          to: '/greenwash/runs/$runId',
          params: { runId: id },
          replace: true,
        })
      }
    />
  );
}

export function StatusRoute() {
  const { store, canWrite } = useGreenwash();
  const { runId } = statusApi.useParams();
  const go = useGo();
  return (
    <StatusScreen
      store={store}
      canWrite={canWrite}
      runId={runId}
      onBack={() => go({ to: '/greenwash' })}
      // 글자 없는 PDF 로 멈춘 실행의 [새 점검](밴드 GW1R ② Q7): push — 뒤로 가기로 이 실패 화면에 돌아온다.
      onNewCheck={() => go({ to: '/greenwash/new' })}
      onRerun={(id) =>
        go({ to: '/greenwash/runs/$runId', params: { runId: id } })
      }
      // [결과 보기]: replace — 뒤로 가기가 끝난 GW-03 이 아니라 그 앞(목록)으로 간다.
      onViewResult={(id) =>
        go({
          to: '/greenwash/runs/$runId/result',
          params: { runId: id },
          replace: true,
        })
      }
    />
  );
}

export function ResultRoute() {
  const { store, canWrite } = useGreenwash();
  const { runId } = resultApi.useParams();
  const go = useGo();
  const review = {
    to: '/greenwash/runs/$runId/review',
    params: { runId },
  } as const;
  return (
    <ResultScreen
      store={store}
      canWrite={canWrite}
      runId={runId}
      onBack={() => go({ to: '/greenwash' })}
      onReview={() => go(review)}
      onConfirm={() => go(review, runId)}
    />
  );
}

export function ReviewRoute() {
  const { runId } = reviewApi.useParams();
  // 실행이 바뀌면 표식 읽기와 화면을 새로 시작한다(옛 ReviewScreen key={runId} 의 자리 — 여기 하나로).
  return <ReviewOf key={runId} runId={runId} />;
}

function ReviewOf({ runId }: { runId: string }) {
  const { runtime, store, canWrite, openPdf } = useGreenwash();
  const go = useGo();
  // 읽기만 한다(지우기는 아래 effect). 렌더 중에 지우면 StrictMode 의 두 번째 렌더가 표식을 못 본다.
  const [askConfirm] = useState(() => runtime.confirmRunId === runId);
  useEffect(() => {
    runtime.confirmRunId = null;
  }, [runtime]);
  return (
    <ReviewScreen
      store={store}
      canWrite={canWrite}
      openPdf={openPdf}
      runId={runId}
      initialConfirm={askConfirm && canWrite}
      onBack={() =>
        go({ to: '/greenwash/runs/$runId/result', params: { runId } })
      }
      onList={() => go({ to: '/greenwash' })}
    />
  );
}
