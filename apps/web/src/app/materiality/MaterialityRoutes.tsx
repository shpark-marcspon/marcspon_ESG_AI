// 중대성평가 틀과 경로 컴포넌트(밴드 IRW1 ② — app/dataverify/DataverifyRoutes.tsx 꼴). app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다.
//   - 틀(MaterialityLayout): AppShell(메뉴 여섯 — app/shell/moduleMenu.tsx 한 자리, currentId materiality)·인사말·[관리자 화면](운영 관리자)·[로그아웃].
//     저장소는 틀이 처음 그려질 때 한 번 만든다(router context 의 MaterialityRuntime — 화면 사이 이동에서 살아남는다). 기본은 실어댑터,
//     목 저장소는 없다(발주서 §1-3). 세션이 끝나면 저장소가 쥔 열쇠를 버린다.
//   - 경로 컴포넌트(…Route): 화면(pages)은 라우터를 모른다. 콜백 props 를 여기서 navigate 로 잇는다.
// /materiality 는 평가 목록(IR-01·01a — ③). /materiality/intro(IR-00) · /materiality/new(IR-02) — 밴드 IRW2 ②. 목록의 [평가 안내] → IR-00 ·
//   [새 평가] → IR-02 push, 거름 없는 첫 쪽이 0건이면 목록 자리에 IR-00 몸(IRW2 ③ Q9 — DV2b 꼴). /materiality/intro 는 늘 IR-00.
//   IR-00 [시작하기] → /materiality/new push · IR-02 [취소] → /materiality · [평가 시작] 201 → IR-03 replace.
//   IR-02 에 무엇이든 넣었으면 떠나기(메뉴·뒤로·[취소])를 막고 묻는다(IRW15 ④ — NewRoute).
// 이동(발주서 §2-2·§2-3): [결과 보기]·[진행 보기]·목록 [다시 실행] push · [다시 실행] → 새 IR-03 push · [목록으로] → /materiality · IR-04 에서 아직 끝나지 않은 실행(409) → IR-03 replace.
// 운영 관리자도 같은 화면이다(인사말·[관리자 화면]·[로그아웃]만 다름 — sid:MARC-ENT-419). 셸 글은 IR_TEXT.shell(DV_TEXT.shell 을 옮겨 적음).
// followSessionEnd 는 app/dataverify/DataverifyRoutes.tsx 를 옮겨 적었다(가져오지 않는다 — 남의 모듈 땅, 공통화는 후속 sid:MARC-ISSUE-335).
import { useCallback, useRef, useState } from 'react';

import { ArrowLeftIcon } from '@marcspon/common/generated/icons/MyIcons';
import {
  Outlet,
  getRouteApi,
  useBlocker,
  useNavigate,
} from '@tanstack/react-router';
import type { NavigateOptions } from '@tanstack/react-router';

import { createMaterialityServerStore } from '../../entities/materiality/api/index.ts';
import type { MaterialityStore } from '../../entities/materiality/api/index.ts';
import { IR_TEXT } from '../../entities/materiality/config/text.ts';
import { useSession } from '../../entities/session/hooks/index.ts';
import { IntroScreen } from '../../pages/materiality-intro/index.ts';
import { ListScreen } from '../../pages/materiality-list/index.ts';
import { NewScreen } from '../../pages/materiality-new/index.ts';
import { ResultScreen } from '../../pages/materiality-result/index.ts';
import { StatusScreen } from '../../pages/materiality-status/index.ts';
import { AppShell } from '../../shared/ui/app-shell/index.ts';
import { Button } from '../../shared/ui/button/index.ts';
import { HeaderGreeting } from '../../shared/ui/header-greeting/index.ts';
import { moduleMenu, moduleTarget } from '../shell/moduleMenu.tsx';
import type { CreateMaterialityStore } from './runtime.ts';

/** 세션 스냅샷을 읽고 바뀜을 받는 것(세션 저장소의 표면 둘 — 구독만 한다). */
interface SessionFeed {
  getSnapshot(): { status: string };
  subscribe(listener: () => void): () => void;
}

/** 세션이 끝날 때마다(signedIn 을 벗어나는 전이) end 를 한 번 부른다(DataverifyRoutes.tsx 를 옮겨 적음). */
export function followSessionEnd(session: SessionFeed, end: () => void) {
  let signedIn = session.getSnapshot().status === 'signedIn';
  return session.subscribe(() => {
    const now = session.getSnapshot().status === 'signedIn';
    if (signedIn && !now) end();
    signedIn = now;
  });
}

/** 기본 저장소: 실어댑터(목은 없다 — 실어댑터 실패를 목으로 메우지 않는다). */
export const createDefaultMaterialityStore: CreateMaterialityStore = (deps) =>
  createMaterialityServerStore(deps);

const layoutApi = getRouteApi('/materiality');
const statusApi = getRouteApi('/materiality/runs/$runId');
const resultApi = getRouteApi('/materiality/runs/$runId/result');

const shell = IR_TEXT.shell;
const MENU = moduleMenu(shell.menu);

/** 지금 세션이 운영 관리자인가(머리 인사말·[관리자 화면]을 가른다). */
export function useOperator(): boolean {
  const state = useSession(layoutApi.useRouteContext().session);
  return state.status === 'signedIn' && state.user.kind === 'admin';
}

/** 중대성평가 저장소(틀이 만든 뒤에만 있다). */
export function useMateriality(): MaterialityStore {
  const runtime = layoutApi.useRouteContext().materiality;
  if (!runtime.control)
    throw new Error('materiality store missing (layout renders first)');
  return runtime.control.store;
}

/** 이동 하나. */
export function useGo() {
  const navigate = useNavigate();
  return (options: NavigateOptions) => void navigate(options);
}

export function MaterialityLayout() {
  const context = layoutApi.useRouteContext();
  const runtime = context.materiality;
  // 처음 그려질 때 한 번(StrictMode 의 두 번 부르기에도 하나).
  useState(() => {
    if (runtime.control) return runtime.control;
    const made = {
      store: (context.createMaterialityStore ?? createDefaultMaterialityStore)({
        api: context.session.api,
      }),
    };
    runtime.control = made;
    // 세션이 끝나면 쥔 열쇠를 버린다(다른 사람이 같은 탭에서 로그인할 수 있다). 구독은 라우터 수명.
    followSessionEnd(context.session, () => made.store.forget());
    return made;
  });
  const go = useGo();
  const operator = useOperator();

  return (
    <div className="twp">
      <AppShell
        menu={MENU}
        currentId="materiality"
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
        <Outlet />
      </AppShell>
    </div>
  );
}

/** /materiality — 평가 목록. */
export function ListRoute() {
  const store = useMateriality();
  const operator = useOperator();
  const go = useGo();
  return (
    <ListScreen
      store={store}
      operator={operator}
      intro={<IntroRoute />}
      onIntro={() => go({ to: '/materiality/intro' })}
      onNew={() => go({ to: '/materiality/new' })}
      onViewResult={(runId) =>
        go({ to: '/materiality/runs/$runId/result', params: { runId } })
      }
      onViewStatus={(runId) =>
        go({ to: '/materiality/runs/$runId', params: { runId } })
      }
    />
  );
}

/** /materiality/intro — 평가 안내(IR-00). */
export function IntroRoute() {
  const go = useGo();
  return <IntroScreen onStart={() => go({ to: '/materiality/new' })} />;
}

/** /materiality/new — 새 평가(IR-02). 201 → IR-03 replace(뒤로 가기가 빈 폼으로 돌아오지 않는다).
 *  넣은 값이 처음 꼴과 다르면 경로 이동(왼쪽 메뉴·뒤로·[취소] 등)을 막고 화면이 묻는다(밴드 IRW15 ④ — ResultRoute 꼴, 결정 MARC-ENT-668).
 *  시작 요청을 기다리는 동안(화면이 dirty false 를 준다)과 201 뒤 IR-03 이동은 막지 않는다. 브라우저 닫기·새로 고침은 브라우저 기본 창. */
export function NewRoute() {
  const store = useMateriality();
  const go = useGo();
  const dirty = useRef(false);
  const blocker = useBlocker({
    shouldBlockFn: () => dirty.current,
    withResolver: true,
    enableBeforeUnload: () => dirty.current,
  });
  const onDirtyChange = useCallback((now: boolean) => {
    dirty.current = now;
  }, []);
  return (
    <NewScreen
      store={store}
      onCancel={() => go({ to: '/materiality' })}
      onStarted={(runId) => {
        // 시작됐다 — 넣은 값은 실행에 실렸으니 막지 않는다(화면의 다음 그리기를 기다리지 않는다).
        dirty.current = false;
        go({
          to: '/materiality/runs/$runId',
          params: { runId },
          replace: true,
        });
      }}
      onDirtyChange={onDirtyChange}
      leave={{
        pending: blocker.status === 'blocked',
        proceed: () => blocker.proceed?.(),
        reset: () => blocker.reset?.(),
      }}
    />
  );
}

export function StatusRoute() {
  const store = useMateriality();
  const go = useGo();
  const { runId } = statusApi.useParams();
  return (
    <StatusScreen
      key={runId}
      store={store}
      runId={runId}
      onBack={() => go({ to: '/materiality' })}
      onViewResult={(id) =>
        go({ to: '/materiality/runs/$runId/result', params: { runId: id } })
      }
      onRerun={(id) =>
        go({ to: '/materiality/runs/$runId', params: { runId: id } })
      }
    />
  );
}

/** /materiality/runs/$runId/result — IR-04. 편집 줄에 바꾼 글이 있으면 경로 이동(왼쪽 메뉴·뒤로·[다시 실행] 등)을 막고 화면이 묻는다
 *  (밴드 IRW11 Q9 — app/drafting/DraftingRoutes.tsx OutlineRoute 꼴). 브라우저 닫기·새로 고침은 브라우저 기본 창. */
export function ResultRoute() {
  const store = useMateriality();
  const navigate = useNavigate();
  const go = useGo();
  const { runId } = resultApi.useParams();
  const dirty = useRef(false);
  const blocker = useBlocker({
    shouldBlockFn: () => dirty.current,
    withResolver: true,
    enableBeforeUnload: () => dirty.current,
  });
  const onDirtyChange = useCallback((now: boolean) => {
    dirty.current = now;
  }, []);
  const onNotDone = useCallback(
    () =>
      void navigate({
        to: '/materiality/runs/$runId',
        params: { runId },
        replace: true,
      }),
    [navigate, runId],
  );
  return (
    <ResultScreen
      key={runId}
      store={store}
      runId={runId}
      onBack={() => go({ to: '/materiality' })}
      onRerun={(id) =>
        go({ to: '/materiality/runs/$runId', params: { runId: id } })
      }
      onNotDone={onNotDone}
      onDirtyChange={onDirtyChange}
      leave={{
        pending: blocker.status === 'blocked',
        proceed: () => blocker.proceed?.(),
        reset: () => blocker.reset?.(),
      }}
    />
  );
}
