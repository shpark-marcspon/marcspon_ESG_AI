// 데이터 검증 틀과 경로 컴포넌트(밴드 DV2a ② — app/translation/TranslationRoutes.tsx 꼴). app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다.
//   - 틀(DataverifyLayout): AppShell(메뉴 여섯 — app/shell/moduleMenu.tsx 한 자리, currentId validation)·인사말·[관리자 화면](운영 관리자)·[로그아웃].
//     저장소는 틀이 처음 그려질 때 한 번 만든다(router context 의 DataverifyRuntime — 화면 사이 이동에서 살아남는다). 기본은 실어댑터,
//     목 저장소는 없다(발주서 §1-3). 파일을 올리지 않는다(문서 없는 흐름 — sendUpload 0). 세션이 끝나면 저장소가 쥔 열쇠를 버린다.
//   - 경로 컴포넌트(…Route): 화면(pages)은 라우터를 모른다. 콜백 props 를 여기서 navigate 로 잇는다.
// /dataverify 는 검증 목록(DV-01·01a — DV2b)이고, 거름 없는 첫 쪽이 0건이면 같은 주소에서 DV-00 을 그린다(QB5 (가) · 판 메모 dv-a-00).
//   /dataverify/intro 는 늘 DV-00(목록의 「검증 안내」).
// 이동(발주서 §2-2): [검증 시작] → DV-03 replace · [결과 보기]·[진행 보기]·[다시 실행] push · [목록으로]·[취소] → /dataverify · [새 검증] → DV-02 ·
//   DV-04 에서 아직 끝나지 않은 실행(409) → DV-03 replace.
// 운영 관리자도 쓴다(업로드·실행·결과 — sid:MARC-ENT-388). 셸 글은 DV_TEXT.shell(TR_TEXT.shell 을 옮겨 적음 — 가져오지 않는다).
// followSessionEnd 는 app/translation/TranslationRoutes.tsx 를 옮겨 적었다(공통화는 후속 — sid:MARC-ISSUE-335).
import { useCallback, useState } from 'react';

import { ArrowLeftIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Outlet, getRouteApi, useNavigate } from '@tanstack/react-router';
import type { NavigateOptions } from '@tanstack/react-router';

import { createDataverifyServerStore } from '../../entities/dataverify/api/index.ts';
import type { DataverifyStore } from '../../entities/dataverify/api/index.ts';
import { DV_TEXT } from '../../entities/dataverify/config/text.ts';
import { useSession } from '../../entities/session/hooks/index.ts';
import { IntroScreen } from '../../pages/dataverify-intro/index.ts';
import { ListScreen } from '../../pages/dataverify-list/index.ts';
import { NewScreen } from '../../pages/dataverify-new/index.ts';
import { ResultScreen } from '../../pages/dataverify-result/index.ts';
import { StatusScreen } from '../../pages/dataverify-status/index.ts';
import { AppShell } from '../../shared/ui/app-shell/index.ts';
import { Button } from '../../shared/ui/button/index.ts';
import { HeaderGreeting } from '../../shared/ui/header-greeting/index.ts';
import { moduleMenu, moduleTarget } from '../shell/moduleMenu.tsx';
import type { CreateDataverifyStore } from './runtime.ts';

/** 세션 스냅샷을 읽고 바뀜을 받는 것(세션 저장소의 표면 둘 — 구독만 한다). */
interface SessionFeed {
  getSnapshot(): { status: string };
  subscribe(listener: () => void): () => void;
}

/** 세션이 끝날 때마다(signedIn 을 벗어나는 전이) end 를 한 번 부른다(TranslationRoutes.tsx 를 옮겨 적음). */
export function followSessionEnd(session: SessionFeed, end: () => void) {
  let signedIn = session.getSnapshot().status === 'signedIn';
  return session.subscribe(() => {
    const now = session.getSnapshot().status === 'signedIn';
    if (signedIn && !now) end();
    signedIn = now;
  });
}

/** 기본 저장소: 실어댑터(목은 없다 — 실어댑터 실패를 목으로 메우지 않는다). */
export const createDefaultDataverifyStore: CreateDataverifyStore = (deps) =>
  createDataverifyServerStore(deps);

const layoutApi = getRouteApi('/dataverify');
const statusApi = getRouteApi('/dataverify/runs/$runId');
const resultApi = getRouteApi('/dataverify/runs/$runId/result');

const shell = DV_TEXT.shell;
const MENU = moduleMenu(shell.menu);

/** 지금 세션이 운영 관리자인가(머리 인사말·[관리자 화면]을 가른다). */
export function useOperator(): boolean {
  const state = useSession(layoutApi.useRouteContext().session);
  return state.status === 'signedIn' && state.user.kind === 'admin';
}

/** 데이터 검증 저장소(틀이 만든 뒤에만 있다). */
export function useDataverify(): DataverifyStore {
  const runtime = layoutApi.useRouteContext().dataverify;
  if (!runtime.control)
    throw new Error('dataverify store missing (layout renders first)');
  return runtime.control.store;
}

/** 이동 하나. */
export function useGo() {
  const navigate = useNavigate();
  return (options: NavigateOptions) => void navigate(options);
}

export function DataverifyLayout() {
  const context = layoutApi.useRouteContext();
  const runtime = context.dataverify;
  // 처음 그려질 때 한 번(StrictMode 의 두 번 부르기에도 하나).
  useState(() => {
    if (runtime.control) return runtime.control;
    const made = {
      store: (context.createDataverifyStore ?? createDefaultDataverifyStore)({
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
        currentId="validation"
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

/** /dataverify — 검증 목록. 거름 없는 첫 쪽이 비면 DV-00(주소 그대로). */
export function ListRoute() {
  const store = useDataverify();
  const operator = useOperator();
  const go = useGo();
  return (
    <ListScreen
      store={store}
      operator={operator}
      intro={<IntroRoute />}
      onIntro={() => go({ to: '/dataverify/intro' })}
      onNewCheck={() => go({ to: '/dataverify/new' })}
      onViewResult={(runId) =>
        go({ to: '/dataverify/runs/$runId/result', params: { runId } })
      }
      onViewStatus={(runId) =>
        go({ to: '/dataverify/runs/$runId', params: { runId } })
      }
    />
  );
}

export function IntroRoute() {
  const go = useGo();
  return <IntroScreen onStart={() => go({ to: '/dataverify/new' })} />;
}

export function NewRoute() {
  const store = useDataverify();
  const go = useGo();
  return (
    <NewScreen
      store={store}
      onCancel={() => go({ to: '/dataverify' })}
      onStarted={(runId) =>
        go({
          to: '/dataverify/runs/$runId',
          params: { runId },
          replace: true,
        })
      }
    />
  );
}

export function StatusRoute() {
  const store = useDataverify();
  const go = useGo();
  const { runId } = statusApi.useParams();
  return (
    <StatusScreen
      key={runId}
      store={store}
      runId={runId}
      onBack={() => go({ to: '/dataverify' })}
      onViewResult={(id) =>
        go({ to: '/dataverify/runs/$runId/result', params: { runId: id } })
      }
      onRerun={(id) =>
        go({ to: '/dataverify/runs/$runId', params: { runId: id } })
      }
      onNewCheck={() => go({ to: '/dataverify/new' })}
    />
  );
}

export function ResultRoute() {
  const store = useDataverify();
  const navigate = useNavigate();
  const go = useGo();
  const { runId } = resultApi.useParams();
  const onNotDone = useCallback(
    () =>
      void navigate({
        to: '/dataverify/runs/$runId',
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
      onBack={() => go({ to: '/dataverify' })}
      onRerun={(id) =>
        go({ to: '/dataverify/runs/$runId', params: { runId: id } })
      }
      onNotDone={onNotDone}
    />
  );
}
