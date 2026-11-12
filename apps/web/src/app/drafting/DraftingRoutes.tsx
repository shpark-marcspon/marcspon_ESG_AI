// 원고작성 틀과 경로 컴포넌트(밴드 RPW1 ① — app/ghg/GhgRoutes.tsx 꼴). app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다.
//   - 틀(DraftingLayout): AppShell(모듈 메뉴 — app/shell/moduleMenu.tsx 한 자리, currentId drafting)·인사말·
//     [관리자 화면](운영 관리자)·[로그아웃]. STEP 띠는 제목 아래라 화면(RP-02·03·04)이 그린다(RPW2 B2).
//     새 router context 칸은 없다 — 실어댑터는 root context 의 session.api 와 서명 PUT 함수 sendUpload 로 짓는다(useMemo, 세션 api 가 같으면 같은 것).
//   - 경로 컴포넌트(…Route): 화면(pages)은 라우터·세션을 모른다. 콜백 props 를 여기서 navigate 로 잇는다.
// 이동: RP-01 머리 「작성 안내」 → /drafting/intro push(RP-00, 밴드 RPW6) · RP-00 [시작하기] → /drafting/new push ·
//   RP-01 [새 프로젝트] → /drafting/new push · 줄의 「다음 할 일」 → 다시 올리기·RP-03·RP-04 push · RP-02 [다음] 끝 → RP-03 replace
//   (뒤로 가기가 다 올린 RP-02 로 돌아오지 않는다) · [취소] → 목록 push.
// RP-03(…/outline) [초안 만들기]·「초안 화면으로」 → RP-04 push · RP-04 [전체 다시 만들기] → 새 실행 replace(경계 ②).
//   RP-03 은 고친 채 나가면 useBlocker 가 막고 화면의 나가기 창으로 묻는다(app/admin AiSettingsRoute 꼴).
// useOperator·useGo 는 GhgRoutes.tsx:63-67·:84-88, sendUpload 는 TranslationRoutes.tsx:37-51 을 옮겨 적었다(가져오지 않는다 — 남의 모듈 땅).
import { useCallback, useMemo, useRef } from 'react';

import { ArrowLeftIcon } from '@marcspon/common/generated/icons/MyIcons';
import {
  Outlet,
  getRouteApi,
  useBlocker,
  useNavigate,
} from '@tanstack/react-router';
import type { NavigateOptions } from '@tanstack/react-router';

import { createDraftingStore } from '../../entities/drafting/api/index.ts';
import type { DraftingStore } from '../../entities/drafting/api/index.ts';
import { DR_TEXT } from '../../entities/drafting/config/text.ts';
import { idOf } from '../../entities/drafting/model/index.ts';
import type { NextStep } from '../../entities/drafting/model/index.ts';
import { useSession } from '../../entities/session/hooks/index.ts';
import { RunScreen } from '../../pages/drafting-draft/index.ts';
import { IntroScreen } from '../../pages/drafting-intro/index.ts';
import { ListScreen } from '../../pages/drafting-list/index.ts';
import { NewProjectScreen } from '../../pages/drafting-new/index.ts';
import { OutlineScreen } from '../../pages/drafting-outline/index.ts';
import { AppShell } from '../../shared/ui/app-shell/index.ts';
import { Button } from '../../shared/ui/button/index.ts';
import { HeaderGreeting } from '../../shared/ui/header-greeting/index.ts';
import { openPdf as pdfjsOpenPdf } from '../../widgets/doc-viewer/pdfjs.ts';
import { moduleMenu, moduleTarget } from '../shell/moduleMenu.tsx';

const layoutApi = getRouteApi('/drafting');
const documentApi = getRouteApi('/drafting/projects/$projectId/document');
const outlineApi = getRouteApi('/drafting/projects/$projectId/outline');
const runApi = getRouteApi('/drafting/projects/$projectId/runs/$runId');

const shell = DR_TEXT.shell;
const MENU = moduleMenu(shell.menu);

/** 서명 주소로 파일 본문을 올린다(TranslationRoutes.tsx:37-51 을 옮겨 적음). Authorization 을 싣지 않는다(서명이 권한이다). */
export async function sendUpload(
  url: string,
  method: string,
  file: File,
  signal?: AbortSignal,
): Promise<void> {
  // 쿠키·리퍼러·캐시를 싣지 않는다(서명 주소는 저장소 출처).
  const response = await globalThis.fetch(url, {
    method,
    body: file,
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    cache: 'no-store',
    ...(signal ? { signal } : {}),
  });
  if (!response.ok) throw new Error(`upload failed ${response.status}`);
}

/** 지금 세션이 운영 관리자인가(머리 인사말·[관리자 화면]·회사 거절 글을 가른다 — GhgRoutes.tsx 를 옮겨 적음). */
export function useOperator(): boolean {
  const state = useSession(layoutApi.useRouteContext().session);
  return state.status === 'signedIn' && state.user.kind === 'admin';
}

/** 원고작성 실어댑터(세션 api 하나에 하나). */
export function useDraftingStore(): DraftingStore {
  const api = layoutApi.useRouteContext().session.api;
  return useMemo(() => createDraftingStore({ api, sendUpload }), [api]);
}

/** 이동 하나. */
export function useGo() {
  const navigate = useNavigate();
  return (options: NavigateOptions) => void navigate(options);
}

/** 프로젝트 실행의 RP-04 로. */
const toRun = (
  projectId: number,
  runId: number,
  replace = false,
): NavigateOptions => ({
  to: '/drafting/projects/$projectId/runs/$runId',
  params: { projectId: String(projectId), runId: String(runId) },
  replace,
});

/** 프로젝트의 RP-03 으로. */
const toOutline = (projectId: number, replace = false): NavigateOptions => ({
  to: '/drafting/projects/$projectId/outline',
  params: { projectId: String(projectId) },
  replace,
});

export function DraftingLayout() {
  const context = layoutApi.useRouteContext();
  const go = useGo();
  const operator = useOperator();

  return (
    <div className="twp">
      <AppShell
        menu={MENU}
        currentId="drafting"
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

/** /drafting — RP-01 보고서 프로젝트 목록. */
export function ListRoute() {
  const store = useDraftingStore();
  const go = useGo();
  const operator = useOperator();
  const onNext = (projectId: number, next: NextStep) => {
    if (next.to === 'upload')
      go({
        to: '/drafting/projects/$projectId/document',
        params: { projectId: String(projectId) },
      });
    else if (next.to === 'outline') go(toOutline(projectId));
    else go(toRun(projectId, next.runId));
  };
  return (
    <ListScreen
      store={store}
      operator={operator}
      onNew={() => go({ to: '/drafting/new' })}
      onNext={onNext}
      onIntro={() => go({ to: '/drafting/intro' })}
    />
  );
}

/** /drafting/intro — RP-00 작성 안내(밴드 RPW6). [시작하기]는 두 종류 사용자 모두(RP-01 [새 프로젝트]와 같다) → /drafting/new push. */
export function IntroRoute() {
  const go = useGo();
  return <IntroScreen onStart={() => go({ to: '/drafting/new' })} />;
}

/** /drafting/new — RP-02 새 프로젝트. 다 달면 RP-03 replace. */
export function NewRoute() {
  const store = useDraftingStore();
  const go = useGo();
  const operator = useOperator();
  return (
    <NewProjectScreen
      store={store}
      projectId={null}
      operator={operator}
      onCancel={() => go({ to: '/drafting' })}
      onDone={(projectId) => go(toOutline(projectId, true))}
    />
  );
}

/** /drafting/projects/$projectId/document — RP-02 전년도 보고서 다시 올리기. 주소 id 가 정수가 아니면 찾지 못함과 같다(요청 0). */
export function DocumentRoute() {
  const store = useDraftingStore();
  const go = useGo();
  const operator = useOperator();
  const { projectId } = documentApi.useParams();
  return (
    <NewProjectScreen
      key={projectId}
      store={store}
      projectId={idOf(projectId)}
      reupload
      operator={operator}
      onCancel={() => go({ to: '/drafting' })}
      onDone={(done) => go(toOutline(done, true))}
    />
  );
}

/** /drafting/projects/$projectId/outline — RP-03 목차 설정. 고친 채 나가면 막고 묻는다. */
export function OutlineRoute() {
  const store = useDraftingStore();
  const go = useGo();
  const operator = useOperator();
  const { projectId } = outlineApi.useParams();
  const id = idOf(projectId);
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
    <OutlineScreen
      key={projectId}
      store={store}
      projectId={id}
      operator={operator}
      onList={() => go({ to: '/drafting' })}
      onRun={(runId) => id !== null && go(toRun(id, runId))}
      onDirtyChange={onDirtyChange}
      leave={{
        pending: blocker.status === 'blocked',
        proceed: () => blocker.proceed?.(),
        reset: () => blocker.reset?.(),
      }}
    />
  );
}

/** /drafting/projects/$projectId/runs/$runId — RP-04 개조식 초안(진행 · 결과 세 칸). pdf.js 여는 함수는 여기서만 가져와 props 로(context.openPdf 가 있으면 그것 — 시험의 가짜). */
export function RunRoute() {
  const store = useDraftingStore();
  const context = layoutApi.useRouteContext();
  const go = useGo();
  const operator = useOperator();
  const { projectId, runId } = runApi.useParams();
  const id = idOf(projectId);
  return (
    <RunScreen
      key={`${projectId}/${runId}`}
      store={store}
      projectId={id}
      runId={idOf(runId)}
      operator={operator}
      onList={() => go({ to: '/drafting' })}
      {...(id !== null ? { onOutline: () => go(toOutline(id)) } : {})}
      onRun={(next) => id !== null && go(toRun(id, next, true))}
      onPickRun={(next) => id !== null && go(toRun(id, next))}
      openPdf={context.openPdf ?? pdfjsOpenPdf}
    />
  );
}
