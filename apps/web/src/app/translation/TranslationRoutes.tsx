// 영문번역 틀과 경로 컴포넌트(밴드 TRW1a ② — app/greenwash/GreenwashRoutes.tsx 꼴). app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다.
//   - 틀(TranslationLayout): AppShell(메뉴 여섯 — app/shell/moduleMenu.tsx 한 자리, 그린워싱·데이터 검증·영문번역 켬, currentId translation)·인사말·[관리자 화면](운영 관리자)·[로그아웃].
//     저장소는 틀이 처음 그려질 때 한 번 만든다(router context 의 TranslationRuntime — 화면 사이 이동에서 살아남는다). 기본은 실어댑터,
//     목 저장소는 없다(발주서 §1-3). 세션이 끝나면 일부 시작 기억(notStarted)을 비운다.
//   - 경로 컴포넌트(…Route): 화면(pages)은 라우터를 모른다. 콜백 props 를 여기서 navigate 로 잇는다. params 는 getRouteApi 로.
// 이동 규칙: [번역 시작] → 묶음 화면 replace, 파트 탭 ?part= replace, 그 밖 push.
// PDF 새 번역(밴드 TRW6 ②): 목록 [PDF로 새 번역] → /translation/pdf/new(PdfNewRoute — NewRoute 와 같은 잇기, 화면만 input="pdf").
// PDF 보기(밴드 TRW6 ③): 묶음 화면 [PDF로 보기]·표 「자리」 → …/batches/$batchKey/pdf/$runId(PdfViewRoute, push). 표 줄의 자리는
//   runtime.control.pdfFocus(한 번 쓰는 표식 — GreenwashRoutes.tsx:463 꼴). [← 결과 요약] → 묶음 화면 그 파트 탭(실행 정보 part).
//   보기 머리 파트 탭(밴드 TRW7 ③b) → 같은 경로의 그 파트 runId, replace.
//   pdf.js 여는 함수는 여기서만 가져와 화면에 props 로 넘긴다(context.openPdf 가 있으면 그것 — 시험의 가짜).
//   「번역 복사」의 클립보드 쓰기(copyText — 대체 길 execCommand)도 여기서 넣는다(밴드 TRW14 ③. AdminRoutes copy 꼴).
// 운영 관리자도 쓴다(업로드·실행·결과 — sid:MARC-ENT-380). 메뉴 글은 TR_TEXT.shell(그린워싱 GW_TEXT.shell 을 가져오지 않는다 — 옮겨 적음).
// sendUpload·followSessionEnd 는 app/greenwash/GreenwashRoutes.tsx:108·:143 을 옮겨 적었다(감독 판단 2 — 가져오지 않는다, 공통화는 후속).
import { useEffect, useState } from 'react';

import { ArrowLeftIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Outlet, getRouteApi, useNavigate } from '@tanstack/react-router';
import type { NavigateOptions } from '@tanstack/react-router';

import { useSession } from '../../entities/session/hooks/index.ts';
import { createTranslationServerStore } from '../../entities/translation/api/index.ts';
import type { TranslationStore } from '../../entities/translation/api/index.ts';
import { TR_TEXT } from '../../entities/translation/config/text.ts';
import { useRunInfo } from '../../entities/translation/hooks/index.ts';
import { batchRowId } from '../../entities/translation/model/index.ts';
import { IntroScreen } from '../../pages/translation-intro/index.ts';
import { ListScreen } from '../../pages/translation-list/index.ts';
import { NewTranslationScreen } from '../../pages/translation-new/index.ts';
import { PdfView, RunScreen } from '../../pages/translation-run/index.ts';
import { AppShell } from '../../shared/ui/app-shell/index.ts';
import { Button } from '../../shared/ui/button/index.ts';
import { HeaderGreeting } from '../../shared/ui/header-greeting/index.ts';
import { openPdf as pdfjsOpenPdf } from '../../widgets/doc-viewer/pdfjs.ts';
import { moduleMenu, moduleTarget } from '../shell/moduleMenu.tsx';
import type { CreateTranslationStore, TranslationRuntime } from './runtime.ts';

/** 서명 주소로 파일 본문을 올린다(GreenwashRoutes.tsx:108 을 옮겨 적음). Authorization 을 싣지 않는다(서명이 권한이다). */
export async function sendUpload(
  url: string,
  method: string,
  file: File,
): Promise<void> {
  // 쿠키·리퍼러·캐시를 싣지 않는다(서명 주소는 저장소 출처).
  const response = await globalThis.fetch(url, {
    method,
    body: file,
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`upload failed ${response.status}`);
}

/** 세션 스냅샷을 읽고 바뀜을 받는 것(세션 저장소의 표면 둘 — 구독만 한다). */
interface SessionFeed {
  getSnapshot(): { status: string };
  subscribe(listener: () => void): () => void;
}

/** 세션이 끝날 때마다(signedIn 을 벗어나는 전이) end 를 한 번 부른다(GreenwashRoutes.tsx:143 을 옮겨 적음). */
export function followSessionEnd(session: SessionFeed, end: () => void) {
  let signedIn = session.getSnapshot().status === 'signedIn';
  return session.subscribe(() => {
    const now = session.getSnapshot().status === 'signedIn';
    if (signedIn && !now) end();
    signedIn = now;
  });
}

/** 기본 저장소: 실어댑터(목은 없다 — 실어댑터 실패를 목으로 메우지 않는다). */
export const createDefaultTranslationStore: CreateTranslationStore = (deps) =>
  createTranslationServerStore(deps);

const layoutApi = getRouteApi('/translation');
const runApi = getRouteApi(
  '/translation/documents/$documentId/batches/$batchKey',
);
const pdfApi = getRouteApi(
  '/translation/documents/$documentId/batches/$batchKey/pdf/$runId',
);

const shell = TR_TEXT.shell;

const MENU = moduleMenu(shell.menu);

/** 지금 세션이 운영 관리자인가(머리 인사말·[관리자 화면]·목록의 「내가 올린 것만」 숨김을 가른다). */
export function useOperator(): boolean {
  const state = useSession(layoutApi.useRouteContext().session);
  return state.status === 'signedIn' && state.user.kind === 'admin';
}

/** 영문번역의 메모리 칸과 저장소(틀이 만든 뒤에만 있다). */
export function useTranslation(): {
  runtime: TranslationRuntime;
  store: TranslationStore;
} {
  const runtime = layoutApi.useRouteContext().translation;
  if (!runtime.control)
    throw new Error('translation store missing (layout renders first)');
  return { runtime, store: runtime.control.store };
}

/** 이동 하나. */
export function useGo() {
  const navigate = useNavigate();
  return (options: NavigateOptions) => void navigate(options);
}

export function TranslationLayout() {
  const context = layoutApi.useRouteContext();
  const runtime = context.translation;
  // 처음 그려질 때 한 번(StrictMode 의 두 번 부르기에도 하나).
  useState(() => {
    if (runtime.control) return runtime.control;
    const made = {
      pdfFocus: null,
      summaryFocus: null,
      store: (context.createTranslationStore ?? createDefaultTranslationStore)({
        api: context.session.api,
        sendUpload,
      }),
    };
    runtime.control = made;
    // 세션이 끝나면 일부 시작 기억을 비운다(다른 사람이 같은 탭에서 로그인할 수 있다). 구독은 라우터 수명.
    followSessionEnd(context.session, () => runtime.notStarted.clear());
    return made;
  });
  const go = useGo();
  const operator = useOperator();

  return (
    <div className="twp">
      <AppShell
        menu={MENU}
        currentId="translation"
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

export function ListRoute() {
  const { store } = useTranslation();
  const operator = useOperator();
  const go = useGo();
  const batch = (documentId: string, batchKey: string) =>
    ({
      to: '/translation/documents/$documentId/batches/$batchKey',
      params: { documentId, batchKey },
    }) as const;
  return (
    <ListScreen
      store={store}
      operator={operator}
      onNewTranslation={() => go({ to: '/translation/new' })}
      onNewPdf={() => go({ to: '/translation/pdf/new' })}
      onIntro={() => go({ to: '/translation/intro' })}
      onOpenBatch={(documentId, batchKey) => go(batch(documentId, batchKey))}
      onOpenPart={(documentId, batchKey, part) =>
        go({ ...batch(documentId, batchKey), search: { part } })
      }
    />
  );
}

/** TR-00 번역 안내(밴드 TRP3). [시작하기] → 번역 목록(push — 빈 목록에도 [새 번역], WS1 sid:MARC-ENT-625). */
export function IntroRoute() {
  const go = useGo();
  return <IntroScreen onStart={() => go({ to: '/translation' })} />;
}

export function NewRoute() {
  return <NewTranslation input="word" />;
}

/** TR-P02 PDF 새 번역(밴드 TRW6 ②). */
export function PdfNewRoute() {
  return <NewTranslation input="pdf" />;
}

/** 새 번역 두 꼴의 잇기(취소 → 목록, 시작 → 묶음 화면 replace). */
function NewTranslation({ input }: { input: 'word' | 'pdf' }) {
  const { runtime, store } = useTranslation();
  const context = layoutApi.useRouteContext();
  const go = useGo();
  return (
    <NewTranslationScreen
      store={store}
      input={input}
      openPdf={context.openPdf ?? pdfjsOpenPdf}
      onCancel={() => go({ to: '/translation' })}
      onStarted={({ documentId, batchKey, started, failed }) => {
        if (failed.length > 0)
          runtime.notStarted.set(batchRowId(documentId, batchKey), {
            started: [...started],
            failed: [...failed],
          });
        // replace: 뒤로 가기로 다 쓴 양식에 돌아가지 않게.
        go({
          to: '/translation/documents/$documentId/batches/$batchKey',
          params: { documentId, batchKey },
          replace: true,
        });
      }}
    />
  );
}

export function RunRoute() {
  const { runtime, store } = useTranslation();
  const { documentId, batchKey } = runApi.useParams();
  const { part } = runApi.useSearch();
  const go = useGo();
  const notStarted = runtime.notStarted.get(batchRowId(documentId, batchKey));
  // PDF 보기에서 돌아왔을 때 눌렀던 표 줄 — 읽기만 하고 지우기는 effect(PdfViewOf 꼴, StrictMode 두 번째 렌더도 보게).
  //   표식을 남긴 묶음이 아니면(PDF 보기 → 목록 → 다른 묶음, 또는 같은 경로에서 묶음만 바뀜) 쓰지 않는다 — 그 묶음의 첫 탭·표는 BASE 그대로.
  const [mark] = useState(() => runtime.control!.summaryFocus);
  const returned =
    (
      mark !== null &&
      mark.documentId === documentId &&
      mark.batchKey === batchKey
    ) ?
      {
        runId: mark.runId,
        label: mark.label,
        table: mark.table,
        index: mark.index,
      }
    : null;
  useEffect(() => {
    runtime.control!.summaryFocus = null;
  }, [runtime]);
  return (
    <RunScreen
      // 묶음이 바뀌면 화면 상태(스타일 탭·받기 글)를 새로.
      key={`${documentId}/${batchKey}`}
      store={store}
      documentId={documentId}
      batchKey={batchKey}
      {...(part === undefined ? {} : { part })}
      {...(notStarted === undefined ? {} : { notStarted })}
      {...(returned === null ? {} : { returned })}
      onBack={() => go({ to: '/translation' })}
      onOpenPdf={(runId, focus, row) => {
        runtime.control!.pdfFocus = focus === null ? null : { runId, ...focus };
        runtime.control!.summaryFocus =
          focus === null || row === undefined ?
            null
          : { documentId, batchKey, runId, label: focus.label, ...row };
        go({
          to: '/translation/documents/$documentId/batches/$batchKey/pdf/$runId',
          params: { documentId, batchKey, runId },
        });
      }}
      // 탭은 replace — 뒤로 가기가 탭마다 쌓이지 않게.
      onTab={(next) =>
        go({
          to: '/translation/documents/$documentId/batches/$batchKey',
          params: { documentId, batchKey },
          search: { part: next },
          replace: true,
        })
      }
    />
  );
}

/** TR-P05 PDF 보기(밴드 TRW6 ③). 실행이 바뀌면 표식 읽기와 화면을 새로. */
export function PdfViewRoute() {
  const { runId } = pdfApi.useParams();
  // key 없음(밴드 TRW8 ①): 파트 탭(같은 경로 다른 runId)에 보기 전체가 새로 붙으면 파트 탭 줄이 묶음을 다시 읽느라 잠깐 사라진다.
  //   runId 로 새로 붙는 것은 PdfView 의 몸(Ready)만.
  return <PdfViewOf runId={runId} />;
}

function PdfViewOf({ runId }: { runId: string }) {
  const { runtime, store } = useTranslation();
  const context = layoutApi.useRouteContext();
  const { documentId, batchKey } = pdfApi.useParams();
  const go = useGo();
  const info = useRunInfo(store, runId).status;
  // 읽기만 한다(지우기는 아래 effect). 렌더 중에 지우면 StrictMode 의 두 번째 렌더가 표식을 못 본다.
  // 표식은 처음 붙을 때의 runId 에 한 번만 쓴다 — 파트 탭으로 옮기면 버린다(되돌아와도 띠·고름 0, 밴드 TRW8 ①).
  const [first, setFirst] = useState(() => {
    const mark = runtime.control!.pdfFocus;
    if (mark === null || mark.runId !== runId) return { runId, focus: null };
    const { page, pair, label, from, filter } = mark;
    return {
      runId,
      focus: {
        page,
        pair,
        label,
        from,
        ...(filter === undefined ? {} : { filter }),
      },
    };
  });
  // 「그리기 중 props 로 state 고치기」 꼴(shared/lib/useLoad 의 useSameKey 와 같음).
  if (first.runId !== runId && first.focus !== null)
    setFirst({ runId: first.runId, focus: null });
  const focus = first.runId === runId ? first.focus : null;
  useEffect(() => {
    runtime.control!.pdfFocus = null;
  }, [runtime]);
  const part = info.state === 'ready' ? info.info.part : null;
  return (
    <PdfView
      store={store}
      runId={runId}
      documentId={documentId}
      openPdf={context.openPdf ?? pdfjsOpenPdf}
      copy={(text) => copyText(text)}
      focus={focus}
      onBack={() =>
        go({
          to: '/translation/documents/$documentId/batches/$batchKey',
          params: { documentId, batchKey },
          ...(part === null ? {} : { search: { part } }),
        })
      }
      batchKey={batchKey}
      // 파트 탭(밴드 TRW7 ③b W8): 같은 경로의 다른 runId — replace(묶음 화면 탭과 같이 뒤로 가기가 탭마다 쌓이지 않게).
      onOpenPart={(next) =>
        go({
          to: '/translation/documents/$documentId/batches/$batchKey/pdf/$runId',
          params: { documentId, batchKey, runId: next },
          replace: true,
        })
      }
    />
  );
}

/**
 * 클립보드에 글 쓰기(밴드 TRW14 ③ — PDF 보기 「번역 복사」). 전역(navigator·document)은 app 층이 넣는다(pages 는 전역을 모른다).
 *   1) navigator.clipboard.writeText(보안 맥락·권한이 있을 때).
 *   2) 없거나 거절되면 숨긴 textarea + document.execCommand('copy')(옛 길 — http 사내망 등).
 *   둘 다 안 되면 reject — 화면이 「복사하지 못했어요」를 띄운다. scope 는 시험이 바꾼다(router.test.tsx).
 */
export async function copyText(
  text: string,
  scope: { navigator?: Navigator; document: Document } = {
    navigator: globalThis.navigator,
    document: globalThis.document,
  },
): Promise<void> {
  const clipboard = scope.navigator?.clipboard;
  if (clipboard !== undefined && typeof clipboard.writeText === 'function') {
    try {
      await clipboard.writeText(text);
      return;
    } catch {
      // 아래 옛 길로
    }
  }
  const { document } = scope;
  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.top = '0';
  area.style.left = '0';
  area.style.opacity = '0';
  const before = document.activeElement as HTMLElement | null;
  document.body.appendChild(area);
  let done = false;
  try {
    area.select();
    done = document.execCommand('copy');
  } catch {
    done = false;
  } finally {
    area.remove();
    before?.focus?.();
  }
  if (!done) throw new Error('copy failed');
}
