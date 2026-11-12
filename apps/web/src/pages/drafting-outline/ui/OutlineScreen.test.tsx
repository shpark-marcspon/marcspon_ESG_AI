// @vitest-environment jsdom
// RP-03 목차 설정(밴드 RPW1 ② 시험 S4 — 발주서 §2-2·§2-0 ⑧). 진짜 실어댑터 + 가짜 원고작성 서버.
//   불러옴·빈 목차 · 단추 일곱(소소에서 아래 단계 끔) · 지우기 확인 창 · key 보존 · 저장 본문(칸 다섯 = outline@1 마디) ·
//   422 두 갈래(줄 · 목차 위 한 줄) · 저장 실패 [다시 시도] · 미저장 물음 · [초안 만들기] 본문·요청 하나 · 409 AI_SETTING_UNUSABLE 한 줄 ·
//   앞 실행 있으면 「초안 화면으로」(POST /runs 0) · 없는 프로젝트 · 회사 거절.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  fakeDraftingServer,
  fakeOutline,
  refusal,
  storeOf,
  unreachable,
} from '../../../entities/drafting/api/testing.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import { OutlineScreen } from './OutlineScreen.tsx';

afterEach(cleanup);
beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

const words = DR_TEXT.outline;
const flush = () => act(async () => {});
type Server = ReturnType<typeof fakeDraftingServer>;
const PUT_OUTLINE = 'PUT /drafting/projects/1/outline';

/** 새 마디 key — n1, n2, … 차례로(한 번 낸 값은 다시 내지 않음 · 지금 목록과 겹치면 화면이 다음 값을 받음). */
const keys = () => {
  let n = 0;
  return () => `n${(n += 1)}`;
};

/** 프로젝트 1(문서 달림) — nodes 를 주면 목차도. */
function seeded(nodes?: OutlineNode[], options = {}) {
  const server = fakeDraftingServer({
    projects: [{ id: 1, name: '지어낸 보고서', year: 2026 }],
    ...options,
  });
  server.seedProject(1, {
    documentId: server.seedDocument(),
    ...(nodes ? { nodes } : {}),
  });
  return server;
}

async function setup(
  server: Server,
  {
    projectId = 1,
    operator = false,
  }: { projectId?: number | null; operator?: boolean } = {},
) {
  const onRun = vi.fn();
  const onList = vi.fn();
  const onDirtyChange = vi.fn();
  render(
    <OutlineScreen
      store={storeOf(server, {
        newKey: () => 'idem-1',
        newLaunchKey: () => 'launch-1',
      })}
      projectId={projectId}
      operator={operator}
      onRun={onRun}
      onList={onList}
      onDirtyChange={onDirtyChange}
      nodeKey={keys()}
    />,
  );
  await flush();
  return { onRun, onList, onDirtyChange };
}

const button = (name: string) => screen.getByRole('button', { name });
const disabled = (name: string) => button(name).hasAttribute('disabled');
/** 고른 줄 아이콘 넷(위로·아래로·올리기·내리기) — 편집 칸의 「순서 · 단계」 줄은 걷혔다(RPW12), 순서는 트리 줄 아이콘으로만. */
const order = (name: string) =>
  within(screen.getByTestId('tree-icons')).getByRole('button', { name });
const rows = () =>
  within(screen.getByTestId('outline-tree'))
    .getAllByRole('option')
    .map(
      (row) =>
        `${row.getAttribute('data-key')}:${row.getAttribute('data-depth')}`,
    );
const pickRow = (key: string) =>
  fireEvent.click(
    screen
      .getAllByRole('option')
      .find((row) => row.getAttribute('data-key') === key)!,
  );
const nameInput = () =>
  screen.getByLabelText(words.nameLabel) as HTMLInputElement;
const notice = () => screen.getByTestId('outline-notice');

describe('RP-03 — 불러옴·빈 목차', () => {
  it('저장된 목차를 트리로(번호·단계) · 머리 셈 · 첫 줄 고름', async () => {
    await setup(seeded(fakeOutline()));
    expect(rows()).toEqual(['n1:1', 'n2:2', 'n3:2', 'n4:3']);
    expect(screen.getByTestId('outline-counts').textContent).toBe(
      words.counts([1, 2, 1, 0], 2),
    );
    expect(nameInput().value).toBe('지어낸 환경');
    expect(screen.queryByTestId('outline-dirty')).toBeNull();
  });

  it('목차 0 — 빈 글 · [초안 만들기] 꺼짐 + 「목차를 하나 이상」 · [대제목 더하기]로 첫 줄', async () => {
    await setup(seeded());
    expect(screen.getByTestId('outline-empty').textContent).toBe(words.empty);
    expect(disabled(words.start)).toBe(true);
    expect(screen.getByTestId('need-nodes').textContent).toBe(words.needNodes);
    fireEvent.click(button(words.addTop));
    expect(rows()).toEqual(['n1:1']);
    expect(nameInput().value).toBe(words.newTitle);
    expect(disabled(words.start)).toBe(false);
    expect(screen.getByTestId('outline-dirty').textContent).toBe(words.dirty);
  });

  it('없는 프로젝트(404)·주소 id 틀림(요청 0) · 회사 거절', async () => {
    await setup(seeded(), { projectId: 9 });
    expect(screen.getByText(words.projectMissing)).not.toBeNull();
    cleanup();
    const server = seeded();
    await setup(server, { projectId: null });
    expect(screen.getByText(words.projectMissing)).not.toBeNull();
    expect(server.calls).toHaveLength(0);
    cleanup();
    await setup(seeded(undefined, { company: 'COMPANY_INACTIVE' }), {
      operator: true,
    });
    expect(screen.getByTestId('company-refusal').textContent).toBe(
      DR_TEXT.companyOperator.inactive,
    );
  });
});

describe('RP-03 — 단추 일곱', () => {
  it('아래 단계 더하기 · 위로 · 아래로 · 올리기 · 내리기 — 트리와 단추 켜짐이 셈대로', async () => {
    await setup(seeded(fakeOutline()));
    pickRow('n2');
    expect(order(words.up).hasAttribute('disabled')).toBe(true);
    expect(order(words.down).hasAttribute('disabled')).toBe(false);
    expect(order(words.indent).hasAttribute('disabled')).toBe(true);
    fireEvent.click(order(words.down));
    expect(rows()).toEqual(['n1:1', 'n3:2', 'n4:3', 'n2:2']);
    fireEvent.click(order(words.indent));
    expect(rows()).toEqual(['n1:1', 'n3:2', 'n4:3', 'n2:3']);
    fireEvent.click(order(words.outdent));
    fireEvent.click(order(words.outdent));
    expect(rows()).toEqual(['n1:1', 'n3:2', 'n4:3', 'n2:1']);
    fireEvent.click(order(words.up));
    expect(rows()).toEqual(['n2:1', 'n1:1', 'n3:2', 'n4:3']);
    pickRow('n4');
    fireEvent.click(button(words.addChild));
    expect(rows()).toEqual(['n2:1', 'n1:1', 'n3:2', 'n4:3', 'n5:4']);
    // 새 줄(소소)이 골라져 있다 — 아래 단계 더하기 끔.
    expect(nameInput().value).toBe(words.newTitle);
    expect(disabled(words.addChild)).toBe(true);
  });

  it('이 목차 지우기 — 확인 창(하위 수) · 취소면 그대로 · 지우기면 하위와 함께', async () => {
    await setup(seeded(fakeOutline()));
    pickRow('n3');
    fireEvent.click(button(words.remove));
    const dialog = await screen.findByTestId('remove-dialog');
    expect(dialog.textContent).toContain(words.removeChildren(1));
    fireEvent.click(within(dialog).getByRole('button', { name: words.cancel }));
    expect(rows()).toEqual(['n1:1', 'n2:2', 'n3:2', 'n4:3']);
    fireEvent.click(button(words.remove));
    fireEvent.click(
      within(await screen.findByTestId('remove-dialog')).getByRole('button', {
        name: words.removeYes,
      }),
    );
    expect(rows()).toEqual(['n1:1', 'n2:2']);
  });

  it('지운 마디의 key 를 새 마디가 다시 얻지 않는다(검증 R4)', async () => {
    await setup(seeded(fakeOutline()));
    fireEvent.click(button(words.addTop));
    expect(rows()).toEqual(['n1:1', 'n2:2', 'n3:2', 'n4:3', 'n5:1']);
    fireEvent.click(button(words.remove));
    fireEvent.click(
      within(await screen.findByTestId('remove-dialog')).getByRole('button', {
        name: words.removeYes,
      }),
    );
    expect(rows()).toEqual(['n1:1', 'n2:2', 'n3:2', 'n4:3']);
    pickRow('n1');
    fireEvent.click(button(words.addChild));
    expect(rows()).toEqual(['n1:1', 'n2:2', 'n3:2', 'n4:3', 'n6:2']);
  });

  it('고친 줄 점 · 요구 글자 수(코드 포인트)', async () => {
    await setup(seeded(fakeOutline()));
    pickRow('n2');
    fireEvent.change(nameInput(), { target: { value: '지어낸 고친 이름' } });
    fireEvent.change(screen.getByLabelText(words.requirementLabel), {
      target: { value: '😀😀😀' },
    });
    const changed = screen
      .getAllByRole('option')
      .filter((row) => row.hasAttribute('data-changed'))
      .map((row) => row.getAttribute('data-key'));
    expect(changed).toEqual(['n2']);
    expect(screen.getByTestId('requirement-count').textContent).toBe(
      '3 / 2,000',
    );
  });
});

describe('RP-03 — 저장', () => {
  it('저장 본문 = 칸 다섯(outline@1 마디)·차례 그대로 · key 는 고쳐도 그대로 · 새 마디만 새 key', async () => {
    const server = seeded(fakeOutline());
    await setup(server);
    pickRow('n2');
    fireEvent.change(nameInput(), { target: { value: '  지어낸 고친 이름 ' } });
    fireEvent.click(order(words.down));
    fireEvent.click(button(words.addTop));
    fireEvent.click(button(words.save));
    await flush();
    const [body] = server.bodies(PUT_OUTLINE) as { nodes: OutlineNode[] }[];
    expect(body!.nodes.map((one) => Object.keys(one).sort())).toEqual(
      body!.nodes.map(() => Object.keys(fakeOutline()[0]!).sort()),
    );
    expect(body!.nodes.map((one) => one.key)).toEqual([
      'n1',
      'n3',
      'n4',
      'n2',
      'n5',
    ]);
    expect(body!.nodes[3]).toEqual({
      key: 'n2',
      parentKey: 'n1',
      depth: 2,
      title: '지어낸 고친 이름',
      requirement: '지어낸 요구 가',
    });
    expect(notice().getAttribute('data-notice')).toBe('saved');
    expect(screen.queryByTestId('outline-dirty')).toBeNull();
    expect(server.project(1)!.outline!.outline.nodes).toEqual(body!.nodes);
  });

  it('화면 검사 — 빈 이름이면 보내지 않고 그 줄·칸에 오류', async () => {
    const server = seeded(fakeOutline());
    await setup(server);
    pickRow('n3');
    fireEvent.change(nameInput(), { target: { value: '   ' } });
    fireEvent.click(button(words.save));
    await flush();
    expect(server.count(PUT_OUTLINE)).toBe(0);
    expect(screen.getByText(words.titleProblem(200))).not.toBeNull();
    expect(
      screen
        .getAllByRole('option')
        .filter((row) => row.hasAttribute('data-problem'))
        .map((row) => row.getAttribute('data-key')),
    ).toEqual(['n3']);
  });

  it('422 fields nodes.<i>.requirement → 그 줄 · nodes(구조) → 목차 위 한 줄 · 서버 글 0', async () => {
    const server = seeded(fakeOutline());
    server.override[PUT_OUTLINE] = [
      () =>
        refusal(422, 'VALIDATION_ERROR', {
          'nodes.1.requirement': ['지어낸 서버 글'],
        }),
      () => refusal(422, 'VALIDATION_ERROR', { nodes: ['지어낸 서버 글'] }),
    ];
    await setup(server);
    pickRow('n2');
    fireEvent.change(nameInput(), { target: { value: '지어낸 다른 이름' } });
    fireEvent.click(button(words.save));
    await flush();
    expect(screen.getByText(words.requirementProblem(2000))).not.toBeNull();
    expect(notice().textContent).toBe('');
    fireEvent.click(button(words.save));
    await flush();
    expect(notice().getAttribute('data-notice')).toBe('saveRejected');
    expect(notice().textContent).toBe(words.saveRejected);
    expect(document.body.textContent).not.toContain('지어낸 서버 글');
  });

  it('저장 실패(끊김) → 「저장하지 못했어요」 + [다시 시도]로 다시 보냄', async () => {
    const server = seeded(fakeOutline());
    server.override[PUT_OUTLINE] = [unreachable];
    await setup(server);
    pickRow('n2');
    fireEvent.change(nameInput(), { target: { value: '지어낸 다른 이름' } });
    fireEvent.click(button(words.save));
    await flush();
    expect(notice().textContent).toContain(words.saveFailed);
    fireEvent.click(
      within(notice()).getByRole('button', { name: DR_TEXT.common.retry }),
    );
    await flush();
    expect(server.count(PUT_OUTLINE)).toBe(2);
    expect(notice().getAttribute('data-notice')).toBe('saved');
  });

  it('미저장 — onDirtyChange 로 알림 · 틀이 막으면 묻는 창([계속 고치기] reset · [나가기] proceed)', async () => {
    const server = seeded(fakeOutline());
    const onDirtyChange = vi.fn();
    const props = {
      store: storeOf(server),
      projectId: 1,
      operator: false,
      onRun: vi.fn(),
      onList: vi.fn(),
      onDirtyChange,
    };
    const { rerender } = render(<OutlineScreen {...props} />);
    await flush();
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
    pickRow('n2');
    fireEvent.change(nameInput(), { target: { value: '지어낸 다른 이름' } });
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    const leave = { pending: true, proceed: vi.fn(), reset: vi.fn() };
    rerender(<OutlineScreen {...props} leave={leave} />);
    const dialog = screen.getByTestId('leave-dialog');
    fireEvent.click(
      within(dialog).getByRole('button', { name: words.leaveStay }),
    );
    expect(leave.reset).toHaveBeenCalledTimes(1);
    fireEvent.click(
      within(dialog).getByRole('button', { name: words.leaveGo }),
    );
    expect(leave.proceed).toHaveBeenCalledTimes(1);
  });
});

describe('RP-03 — [초안 만들기](§2-0 ⑧)', () => {
  it('저장 → POST /runs {module, launchKey, options:{projectId}}(base 0) + Idempotency-Key → onRun · 두 번 눌러도 요청 하나', async () => {
    const server = seeded(fakeOutline());
    const { onRun } = await setup(server);
    pickRow('n2');
    fireEvent.change(nameInput(), { target: { value: '지어낸 다른 이름' } });
    const start = button(words.start);
    fireEvent.click(start);
    fireEvent.click(start);
    await flush();
    await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
    expect(server.count(PUT_OUTLINE)).toBe(1);
    expect(server.count('POST /runs')).toBe(1);
    expect(server.bodies('POST /runs')).toEqual([
      { module: 'drafting', launchKey: 'launch-1', options: { projectId: 1 } },
    ]);
    const post = server.calls.find((call) => call.path === '/runs')!;
    expect(post.headers.get('Idempotency-Key')).toBe('idem-1');
    expect(onRun).toHaveBeenCalledWith(server.runs()[0]!.id);
  });

  it('고친 것이 없으면 저장 건너뛰고 실행만', async () => {
    const server = seeded(fakeOutline());
    const { onRun } = await setup(server);
    fireEvent.click(button(words.start));
    await flush();
    expect(server.count(PUT_OUTLINE)).toBe(0);
    expect(server.count('POST /runs')).toBe(1);
    expect(onRun).toHaveBeenCalledTimes(1);
  });

  it('409 AI_SETTING_UNUSABLE → 시작 거절 한 줄(설정 화면 이름·서버 글 0) · 이동 0', async () => {
    const server = seeded(fakeOutline(), { aiUnusable: true });
    const { onRun } = await setup(server);
    fireEvent.click(button(words.start));
    await flush();
    expect(notice().textContent).toBe(DR_TEXT.startRefused);
    expect(document.body.textContent).not.toContain('AI 설정');
    expect(onRun).not.toHaveBeenCalled();
  });

  it('앞 실행이 있으면 「초안 화면으로」 — 저장 뒤 그 실행으로(POST /runs 0) · 고쳐 저장하면 바뀜 안내', async () => {
    const server = seeded(fakeOutline());
    const first = await storeOf(server).startRun({ projectId: 1 }, null);
    const runId = first.kind === 'ok' ? first.value.runId : 0;
    const { onRun } = await setup(server);
    expect(screen.queryByRole('button', { name: words.start })).toBeNull();
    pickRow('n2');
    fireEvent.change(nameInput(), { target: { value: '지어낸 다른 이름' } });
    fireEvent.click(button(words.save));
    await flush();
    expect(screen.getByTestId('changed-after-run').textContent).toBe(
      words.changedAfterRun,
    );
    fireEvent.click(button(words.toDraft));
    await flush();
    expect(server.count('POST /runs')).toBe(1);
    expect(onRun).toHaveBeenCalledWith(runId);
  });
});

describe('RPW2 ② RP-03 손질 · M5', () => {
  const POSTS = 'POST /runs';
  const idems = (server: Server) =>
    server.calls
      .filter((call) => `${call.method} ${call.path}` === POSTS)
      .map((call) => call.headers.get('Idempotency-Key'));
  const notice2 = () => screen.getByTestId('outline-notice');

  it('머리 — [목록으로] 가 카드 위(제목 줄) · 부제 연도 겹침 0', async () => {
    const server = fakeDraftingServer({
      projects: [{ id: 1, name: '2026 지어낸 보고서', year: 2026 }],
    });
    server.seedProject(1, {
      documentId: server.seedDocument(),
      nodes: fakeOutline(),
    });
    const { onList } = await setup(server);
    expect(
      screen.getByText('2026 지어낸 보고서', { exact: false }),
    ).not.toBeNull();
    expect(document.body.textContent).not.toContain('2026 · 2026');
    const list = button(words.toList);
    const card = document.querySelector('[data-card="outline"]')!;
    expect(
      list.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    fireEvent.click(list);
    expect(onList).toHaveBeenCalledOnce();
  });

  it('STEP 2 띠가 제목 뒤(목차를 다 읽은 화면)', async () => {
    await setup(seeded(fakeOutline()));
    const title = screen.getByRole('heading', { level: 2, name: words.title });
    const step = screen.getByRole('list', { name: DR_TEXT.steps.label });
    expect(
      title.compareDocumentPosition(step) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(step.querySelector('[aria-current="step"]')?.textContent).toContain(
      DR_TEXT.steps.items[1],
    );
  });

  it('라벨 왼쪽 칸 — 이름·요구가 양식 줄 라벨(폭 160)', async () => {
    await setup(seeded(fakeOutline()));
    for (const label of [words.nameLabel, words.requirementLabel])
      expect(screen.getByText(label).className).toContain('w-40');
  });

  it('편집 칸에 「순서 · 단계」 줄 0 — 글·순서 단추 넷 0, [삭제]만 남음(RPW12)', async () => {
    await setup(seeded(fakeOutline()));
    pickRow('n2');
    const editor = screen.getByTestId('outline-editor');
    expect(within(editor).queryByText('순서 · 단계')).toBeNull();
    for (const name of [words.up, words.down, words.outdent, words.indent])
      expect(within(editor).queryByRole('button', { name })).toBeNull();
    expect(
      within(editor)
        .getAllByRole('button')
        .map((one) => one.textContent?.trim()),
    ).toEqual([words.removeShort]);
  });

  it('저장 시각 — 처음 0 · 저장 응답 뒤 「YYYY-MM-DD HH:MM 저장」', async () => {
    await setup(seeded(fakeOutline()));
    expect(screen.queryByTestId('outline-saved-at')).toBeNull();
    fireEvent.change(nameInput(), { target: { value: '지어낸 고침' } });
    fireEvent.click(button(words.save));
    await flush();
    expect(screen.getByTestId('outline-saved-at').textContent).toMatch(
      /^ · \d{4}-\d{2}-\d{2} \d{2}:\d{2} 저장$/,
    );
  });

  it('저장 실패면 저장 시각 0', async () => {
    const server = seeded(fakeOutline());
    server.override[PUT_OUTLINE] = [unreachable];
    await setup(server);
    fireEvent.change(nameInput(), { target: { value: '지어낸 고침' } });
    fireEvent.click(button(words.save));
    await flush();
    expect(screen.queryByTestId('outline-saved-at')).toBeNull();
  });

  it('M5 시작 연결 실패 = 연결 글(거절 글 0) · 같은 판이면 같은 열쇠', async () => {
    const server = seeded(fakeOutline());
    server.override[POSTS] = [unreachable];
    const { onRun } = await setup(server);
    fireEvent.click(button(words.start));
    await flush();
    expect(notice2().textContent).toBe(DR_TEXT.startFailed);
    expect(notice2().textContent).not.toBe(DR_TEXT.startRefused);
    expect(onRun).not.toHaveBeenCalled();
    fireEvent.click(button(words.start));
    await flush();
    expect(idems(server)).toEqual(['idem-1', 'idem-1']);
    expect(onRun).toHaveBeenCalledOnce();
  });

  it('M5 고쳐 저장하면 새 판 = 표의 다른 칸(같은 열쇠를 다시 쓰지 않음)', async () => {
    const server = seeded(fakeOutline());
    server.override[POSTS] = [unreachable, unreachable];
    let n = 0;
    render(
      <OutlineScreen
        store={storeOf(server, {
          newKey: () => `idem-${(n += 1)}`,
          newLaunchKey: () => `launch-${n}`,
        })}
        projectId={1}
        operator={false}
        onRun={vi.fn()}
        onList={vi.fn()}
        nodeKey={keys()}
      />,
    );
    await flush();
    fireEvent.click(button(words.start));
    await flush();
    fireEvent.change(nameInput(), { target: { value: '지어낸 고침' } });
    fireEvent.click(button(words.start));
    await flush();
    expect(idems(server)).toEqual(['idem-1', 'idem-2']);
  });
});

describe('RPW3 목차 설정 손질', () => {
  const lead = '2026 · 지어낸 보고서';

  it('D2 트리 제목 두 줄 감쌈 + title 에 전체 제목 · 들여쓰기 줄임', async () => {
    await setup(seeded(fakeOutline()));
    const row = screen
      .getAllByRole('option')
      .find((one) => one.getAttribute('data-depth') === '2')!;
    const title = within(row).getByTestId('tree-title');
    expect(title.className).toContain('line-clamp-2');
    expect(title.className).not.toContain('truncate');
    expect(title.getAttribute('title')).toBe(
      within(row).getByTestId('tree-title-text').textContent,
    );
    expect(row.style.paddingLeft).toBe('32px');
    expect(title.contains(within(row).getByTestId('tree-marks'))).toBe(true);
    expect(within(row).getByTestId('tree-marks').className).toContain(
      'float-right',
    );
  });

  it('D5 부제 = 연도·이름 · 전년도 보고서 파일 이름 · 쪽 수는 아는 값만', async () => {
    const server = seeded(fakeOutline());
    await setup(server);
    expect(
      await screen.findByText(
        `${lead} · 전년도 보고서 지어낸 전년도 보고서.pdf`,
        { exact: false },
      ),
    ).not.toBeNull();
    expect(words.leadFile('가.pdf', null)).toBe(' · 전년도 보고서 가.pdf');
    expect(words.leadFile('가.pdf', 152)).toBe(
      ' · 전년도 보고서 가.pdf 152페이지',
    );
  });

  it('D5 문서를 못 읽으면 부제는 연도·이름 그대로 · 화면은 산다', async () => {
    const server = fakeDraftingServer({
      projects: [{ id: 1, name: '지어낸 보고서', year: 2026 }],
    });
    const documentId = server.seedDocument();
    server.seedProject(1, { documentId, nodes: fakeOutline() });
    server.override[`GET /documents/${documentId}`] = [unreachable];
    await setup(server);
    await flush();
    expect(server.count(`GET /documents/${documentId}`)).toBe(1);
    expect(screen.getByText(lead)).not.toBeNull();
    expect(screen.getByTestId('outline-tree')).not.toBeNull();
  });

  it('D6 번짐 — 저장 5xx 는 「저장하지 못했어요」 + [다시 시도](확인 글 0)', async () => {
    const server = seeded(fakeOutline());
    server.override[PUT_OUTLINE] = [() => refusal(500, 'INTERNAL_ERROR')];
    await setup(server);
    pickRow('n2');
    fireEvent.change(nameInput(), { target: { value: '지어낸 다른 이름' } });
    fireEvent.click(button(words.save));
    await flush();
    expect(notice().dataset.notice).toBe('saveFailed');
    expect(button(DR_TEXT.common.retry)).not.toBeNull();
  });
});

describe('RPW5 #4 첫 불러오기 몸(sid:MARC-ENT-443 ①)', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  /** 프로젝트 읽기를 문으로 막은 RP-03. */
  function held() {
    const server = seeded(fakeOutline());
    let open!: () => void;
    const gate = new Promise<void>((resolve) => (open = resolve));
    const base = storeOf(server, {
      newKey: () => 'idem-1',
      newLaunchKey: () => 'launch-1',
    });
    render(
      <OutlineScreen
        store={{
          ...base,
          getProject: async (id) => {
            await gate;
            return base.getProject(id);
          },
        }}
        projectId={1}
        operator={false}
        onRun={vi.fn()}
        onList={vi.fn()}
        onDirtyChange={vi.fn()}
        nodeKey={keys()}
      />,
    );
    return () => act(async () => open());
  }

  it('받기 전: 제목 아래 299ms 스켈레톤 0 / 300ms 스켈레톤 → 받으면 편집 몸 · 스켈레톤 0', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const release = held();
    await flush();
    expect(screen.getByRole('heading', { name: words.title })).toBeTruthy();
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    act(() => vi.advanceTimersByTime(299));
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByTestId('load-skeleton')).toBeTruthy();
    await release();
    await flush();
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    expect(rows().length).toBeGreaterThan(0);
  });

  it('300ms 안에 받으면 스켈레톤을 그린 적이 없다', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const release = held();
    await flush();
    act(() => vi.advanceTimersByTime(200));
    await release();
    await flush();
    act(() => vi.advanceTimersByTime(500));
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    expect(rows().length).toBeGreaterThan(0);
  });
});
