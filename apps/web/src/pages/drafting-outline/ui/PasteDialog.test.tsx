// @vitest-environment jsdom
// RP-03a 목차 붙여넣기 창(밴드 RPW9 §2 vitest — 발주서 §1-C·D). 진짜 실어댑터 + 가짜 원고작성 서버, 화면은 OutlineScreen 째로.
//   두 자리 단추 · 열 때 초점 · 미리보기(번호·요구·셈) · 빈 글 · 못 읽은 줄 접힘 · 한도 띠 · 바꾸기 확인 · 넣은 뒤 고른 줄·초점·dirty ·
//   Esc → 연 단추 · 저장 본문 · busy · 화면 글. 시험 글은 모두 지어낸 것.
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

import type { DraftingStore } from '../../../entities/drafting/api/index.ts';
import {
  fakeDraftingServer,
  fakeOutline,
  storeOf,
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
const paste = words.paste;
const flush = () => act(async () => {});
type Server = ReturnType<typeof fakeDraftingServer>;
const PUT_OUTLINE = 'PUT /drafting/projects/1/outline';

const keys = () => {
  let n = 0;
  return () => `n${(n += 1)}`;
};

function seeded(nodes?: OutlineNode[]) {
  const server = fakeDraftingServer({
    projects: [{ id: 1, name: '지어낸 보고서', year: 2026 }],
  });
  server.seedProject(1, {
    documentId: server.seedDocument(),
    ...(nodes ? { nodes } : {}),
  });
  return server;
}

async function setup(
  server: Server,
  wrap: (store: DraftingStore) => DraftingStore = (store) => store,
) {
  render(
    <OutlineScreen
      store={wrap(
        storeOf(server, {
          newKey: () => 'idem-1',
          newLaunchKey: () => 'launch-1',
        }),
      )}
      projectId={1}
      operator={false}
      onRun={vi.fn()}
      onList={vi.fn()}
      nodeKey={keys()}
    />,
  );
  await flush();
}

/** 지어낸 지금 목차 n 줄(대 하나 + 중 n−1). */
const many = (count: number): OutlineNode[] =>
  Array.from({ length: count }, (_, at) => ({
    key: `old${at}`,
    parentKey: at === 0 ? null : 'old0',
    depth: at === 0 ? 1 : 2,
    title: `지어낸 옛 ${at}`,
    requirement: '',
  }));

const button = (name: string) => screen.getByRole('button', { name });
const dialog = () => screen.getByTestId('paste-dialog');
const textBox = () =>
  screen.getByLabelText(paste.inputLabel) as HTMLTextAreaElement;
const type = async (value: string) => {
  fireEvent.change(textBox(), { target: { value } });
  await flush();
};
const insertButton = () => screen.getByTestId('paste-insert');
const numbers = () =>
  screen.queryAllByTestId('paste-number').map((one) => one.textContent);
const treeRows = () =>
  within(screen.getByTestId('outline-tree'))
    .getAllByRole('option')
    .map(
      (row) =>
        `${row.getAttribute('data-key')}:${row.getAttribute('data-depth')}`,
    );
const open = async () => {
  fireEvent.click(button(paste.open));
  await flush();
};

/** 지어낸 붙여넣기 글 — 탭 요구 · 「요구:」 · 다음 줄 요구 · 다섯째 단계 · 201자 이름. */
const SAMPLE = [
  '1. 가상 경영',
  '1.1 가상 재무\t지어낸 요구 가',
  '1.1.1 가상 매출 요구: 지어낸 요구 나',
  '1.1.1.1 가상 지역',
  '1.1.1.1.1 가상 너무 깊음',
  '2. 가상 부록',
  '    요구: 지어낸 요구 다',
  `2.1 ${'가'.repeat(201)}`,
  '2.2 가상 색인',
].join('\n');

describe('RP-03a — 들어가는 자리', () => {
  it('트리 머리 [붙여넣기] → 창 · 열 때 초점은 글 칸', async () => {
    await setup(seeded(fakeOutline()));
    await open();
    expect(dialog()).toBeTruthy();
    expect(document.activeElement).toBe(textBox());
    expect(screen.getByRole('heading', { name: paste.title })).toBeTruthy();
  });

  it('빈 상태 [붙여넣기] → 같은 창 · 바꾸기 확인 없이 바로 넣음', async () => {
    await setup(seeded());
    expect(screen.getByTestId('outline-empty').textContent).toBe(words.empty);
    await open();
    await type('가상 하나\n  가상 둘');
    fireEvent.click(screen.getByTestId('paste-replace'));
    await flush();
    fireEvent.click(insertButton());
    await flush();
    expect(screen.queryByTestId('paste-confirm')).toBeNull();
    expect(screen.queryByTestId('paste-dialog')).toBeNull();
    expect(treeRows()).toEqual(['n1:1', 'n2:2']);
  });

  it('busy(저장 중)이면 [붙여넣기] 꺼짐', async () => {
    await setup(seeded(fakeOutline()), (store) => {
      const held = Object.create(store) as DraftingStore;
      held.saveOutline = () => new Promise(() => {});
      return held;
    });
    expect(button(paste.open).hasAttribute('disabled')).toBe(false);
    fireEvent.change(screen.getByLabelText(words.nameLabel), {
      target: { value: '지어낸 고침' },
    });
    fireEvent.click(button(words.save));
    await flush();
    expect(button(paste.open).hasAttribute('disabled')).toBe(true);
  });
});

describe('RP-03a — 미리보기', () => {
  it('빈 글: 미리보기 빈 글 · [목차에 넣기] 꺼짐(수 없음) · 안내 둘 · 자리글', async () => {
    await setup(seeded(fakeOutline()));
    await open();
    expect(screen.getByTestId('paste-empty').textContent).toBe(
      paste.previewEmpty,
    );
    expect(insertButton().textContent).toBe(paste.insert(null));
    expect(insertButton().hasAttribute('disabled')).toBe(true);
    expect(
      within(screen.getByTestId('paste-guide'))
        .getAllByRole('listitem')
        .map((one) => one.textContent),
    ).toEqual(paste.guide);
    expect(textBox().placeholder).toBe(paste.placeholder);
    expect(screen.getByTestId('paste-counts').textContent).toBe('');
  });

  it('글 → 미리보기 줄 · 번호는 지금 대제목 다음부터 · 바꾸기면 1부터 · 요구 표시 · 머리 셈', async () => {
    await setup(seeded(fakeOutline())); // 지금 대제목 1개
    await open();
    await type(SAMPLE);
    expect(numbers()).toEqual(['2', '2.1', '2.1.1', '2.1.1.1', '3', '3.1']);
    expect(
      screen.getAllByTestId('paste-title').map((one) => one.textContent),
    ).toEqual([
      '가상 경영',
      '가상 재무',
      '가상 매출',
      '가상 지역',
      '가상 부록',
      '가상 색인',
    ]);
    const marks = screen.getAllByTestId('paste-requirement');
    expect(marks).toHaveLength(3);
    expect(marks[0]!.textContent).toBe(paste.requirementMark);
    expect(marks[0]!.getAttribute('title')).toBe(paste.requirementMarkTitle);
    expect(screen.getByTestId('paste-counts').textContent).toBe(
      paste.previewCounts(6, 2),
    );
    expect(insertButton().textContent).toBe(paste.insert(6));
    expect(insertButton().hasAttribute('disabled')).toBe(false);
    fireEvent.click(screen.getByTestId('paste-replace'));
    await flush();
    expect(numbers()).toEqual(['1', '1.1', '1.1.1', '1.1.1.1', '2', '2.1']);
  });

  it('못 읽은 줄: 처음 접힘 → 펼치기 → 행 번호·까닭 · aria-expanded · 넣기는 켜짐', async () => {
    await setup(seeded(fakeOutline()));
    await open();
    await type(SAMPLE);
    expect(screen.getByTestId('paste-bad').textContent).toContain(
      paste.badSummary(2),
    );
    const toggle = screen.getByTestId('paste-bad-toggle');
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(toggle.textContent).toBe(paste.badOpen);
    expect(screen.getByTestId('paste-bad-list').hidden).toBe(true);
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(toggle.textContent).toBe(paste.badClose);
    const list = screen.getByTestId('paste-bad-list');
    expect(list.hidden).toBe(false);
    expect(toggle.getAttribute('aria-controls')).toBe(list.id);
    expect(
      within(list)
        .getAllByRole('listitem')
        .map((one) => one.textContent),
    ).toEqual([
      `${paste.badLine(5)} · ${paste.reasons.tooDeep}`,
      `${paste.badLine(8)} · ${paste.reasons.titleLong(200)}`,
    ]);
    // 글을 바꿔도 펼침 그대로
    await type(`${SAMPLE}\n1.1`);
    expect(
      screen.getByTestId('paste-bad-toggle').getAttribute('aria-expanded'),
    ).toBe('true');
    expect(insertButton().hasAttribute('disabled')).toBe(false);
  });

  it('한도: 지금 290 + 새 11 → 빨간 띠 role=alert(합친 수) · 꺼짐(수는 보임) → 바꾸기면 띠 없음·켜짐', async () => {
    await setup(seeded(many(290)));
    await open();
    await type(
      Array.from({ length: 11 }, (_, at) => `가상 대 ${at}`).join('\n'),
    );
    const band = screen.getByTestId('paste-over');
    expect(band.getAttribute('role')).toBe('alert');
    expect(band.textContent).toBe(paste.tooManyNodes(300, 301));
    expect(insertButton().hasAttribute('disabled')).toBe(true);
    expect(insertButton().textContent).toBe(paste.insert(11));
    expect(insertButton().getAttribute('aria-describedby')).toBe(band.id);
    fireEvent.click(screen.getByTestId('paste-replace'));
    await flush();
    expect(screen.queryByTestId('paste-over')).toBeNull();
    expect(insertButton().hasAttribute('disabled')).toBe(false);
  });

  it('한도: 끝 목차 151 → 끝 목차 띠 · 바꾸기에서 넘으면 괄호 없음', async () => {
    await setup(seeded(fakeOutline())); // 잎 2
    await open();
    await type(
      Array.from({ length: 149 }, (_, at) => `가상 대 ${at}`).join('\n'),
    );
    expect(screen.getByTestId('paste-over').textContent).toBe(
      paste.tooManyLeaves(150, 151),
    );
    fireEvent.click(screen.getByTestId('paste-replace'));
    await flush();
    expect(screen.queryByTestId('paste-over')).toBeNull();
    await type(
      Array.from({ length: 151 }, (_, at) => `가상 대 ${at}`).join('\n'),
    );
    expect(screen.getByTestId('paste-over').textContent).toBe(
      paste.tooManyLeaves(150, null),
    );
  });
});

describe('RP-03a — 넣기', () => {
  it('붙이기: 넣은 첫 줄 고름 · 초점 그 줄 · dirty · 저장 본문 = 앞 줄 그대로 + 새 줄', async () => {
    const server = seeded(fakeOutline());
    await setup(server);
    await open();
    await type('가상 위 요구: 지어낸 위 요구\n  가상 아래\t지어낸 아래 요구');
    fireEvent.click(insertButton());
    await flush();
    expect(screen.queryByTestId('paste-dialog')).toBeNull();
    expect(treeRows()).toEqual([
      'n1:1',
      'n2:2',
      'n3:2',
      'n4:3',
      'n5:1',
      'n6:2',
    ]);
    const picked = screen
      .getAllByRole('option')
      .find((row) => row.getAttribute('aria-selected') === 'true')!;
    expect(picked.getAttribute('data-key')).toBe('n5');
    await waitFor(() => expect(document.activeElement).toBe(picked));
    expect(screen.getByTestId('outline-dirty').textContent).toBe(words.dirty);
    fireEvent.click(button(words.save));
    await flush();
    const [body] = server.bodies(PUT_OUTLINE) as { nodes: OutlineNode[] }[];
    expect(body!.nodes.slice(0, 4)).toEqual(fakeOutline());
    expect(body!.nodes.slice(4)).toEqual([
      {
        key: 'n5',
        parentKey: null,
        depth: 1,
        title: '가상 위',
        requirement: '지어낸 위 요구',
      },
      {
        key: 'n6',
        parentKey: 'n5',
        depth: 2,
        title: '가상 아래',
        requirement: '지어낸 아래 요구',
      },
    ]);
  });

  it('바꾸기: 확인 창(지금 수·새 수) · [취소] → 글·라디오 그대로, 초점 [목차에 넣기] · [바꾸기] → 새 줄만, 옛 key 0', async () => {
    const server = seeded(fakeOutline());
    await setup(server);
    await open();
    await type('가상 하나\n가상 둘');
    fireEvent.click(screen.getByTestId('paste-replace'));
    await flush();
    fireEvent.click(insertButton());
    await flush();
    const confirm = screen.getByTestId('paste-confirm');
    expect(confirm.getAttribute('role')).toBe('alertdialog');
    expect(within(confirm).getByText(paste.confirmTitle)).toBeTruthy();
    expect(within(confirm).getByText(paste.confirmBody(4, 2))).toBeTruthy();
    fireEvent.click(
      within(confirm).getByRole('button', { name: words.cancel }),
    );
    await flush();
    expect(screen.queryByTestId('paste-confirm')).toBeNull();
    expect(textBox().value).toBe('가상 하나\n가상 둘');
    expect(
      screen.getByTestId('paste-replace').getAttribute('aria-checked'),
    ).toBe('true');
    await waitFor(() => expect(document.activeElement).toBe(insertButton()));
    fireEvent.click(insertButton());
    await flush();
    fireEvent.click(
      within(screen.getByTestId('paste-confirm')).getByRole('button', {
        name: paste.confirmYes,
      }),
    );
    await flush();
    expect(screen.queryByTestId('paste-dialog')).toBeNull();
    expect(treeRows()).toEqual(['n5:1', 'n6:1']);
    const first = screen.getAllByRole('option')[0]!;
    expect(first.getAttribute('aria-selected')).toBe('true');
    await waitFor(() => expect(document.activeElement).toBe(first));
    fireEvent.click(button(words.save));
    await flush();
    const [body] = server.bodies(PUT_OUTLINE) as { nodes: OutlineNode[] }[];
    expect(body!.nodes.map((one) => one.key)).toEqual(['n5', 'n6']);
  });

  it('Esc → 창 닫힘 · 초점은 연 단추 · 다시 열면 빈 글 · 붙이기', async () => {
    await setup(seeded(fakeOutline()));
    const opener = button(paste.open);
    opener.focus();
    await open();
    await type('가상 하나');
    fireEvent.click(screen.getByTestId('paste-replace'));
    await flush();
    fireEvent.keyDown(textBox(), { key: 'Escape' });
    await flush();
    expect(screen.queryByTestId('paste-dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(opener));
    expect(treeRows()).toEqual(['n1:1', 'n2:2', 'n3:2', 'n4:3']);
    await open();
    expect(textBox().value).toBe('');
    expect(
      screen.getByTestId('paste-append').getAttribute('aria-checked'),
    ).toBe('true');
  });

  it('[취소] → 넣지 않고 닫힘', async () => {
    await setup(seeded(fakeOutline()));
    await open();
    await type('가상 하나');
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.cancel }),
    );
    await flush();
    expect(screen.queryByTestId('paste-dialog')).toBeNull();
    expect(treeRows()).toHaveLength(4);
  });

  it('화면 글 — 시안 글자', async () => {
    await setup(seeded(fakeOutline()));
    expect(button(paste.open).textContent).toBe('붙여넣기');
    await open();
    expect(paste.title).toBe('목차 붙여넣기');
    expect(screen.getByLabelText(paste.howLabel)).toBeTruthy();
    expect(screen.getByText('지금 목차 뒤에 붙이기')).toBeTruthy();
    expect(screen.getByText('지금 목차를 바꾸기')).toBeTruthy();
    expect(screen.getByText('미리보기')).toBeTruthy();
    expect(paste.tooManyNodes(300, 312)).toBe(
      '목차는 300개까지 넣을 수 있어요(지금 목차와 합쳐 312개)',
    );
    expect(paste.badSummary(2)).toBe('2줄을 읽지 못했어요 — 넣을 때 빠져요');
    expect(paste.confirmBody(13, 11)).toBe(
      '지금 목차 13개가 지워지고 새 목차 11개로 바뀌어요',
    );
    expect(paste.reasons.requirementLong(2000)).toBe(
      '요구 내용이 2,000자를 넘어요',
    );
  });
});

// RPW10 — 디자인 재대조(RPW9 디자인 검토 「고칠 것」 #1~#3). 자리·크기의 실제 값은 e2e/drafting-paste.spec.ts 가 잰다.
describe('RP-03a — 디자인 재대조(RPW10)', () => {
  /** 띠 아이콘이 띠 글자색을 따르는 선 아이콘(CircleWarningIcon)인가 — 박힌 빨강(WarnIcon #D91F0A 팔각형) 0. */
  const expectLineIcon = (band: HTMLElement) => {
    const svgs = band.querySelectorAll('svg');
    const icon = svgs[0]!;
    expect(icon.getAttribute('viewBox')).toBe('0 0 16 16');
    expect(icon.querySelector('circle')?.getAttribute('fill')).toBe(
      'currentColor',
    );
    const strokes = [...icon.querySelectorAll('path')].map((path) =>
      path.getAttribute('stroke'),
    );
    expect(strokes).toEqual(['currentColor', 'currentColor']);
    expect(band.querySelector('[fill="#D91F0A"]')).toBeNull();
    expect(band.querySelector('clipPath')).toBeNull();
  };

  it('#1 못 읽은 줄 띠·한도 띠의 아이콘 = 선 아이콘(currentColor) · WarnIcon 0', async () => {
    await setup(seeded(many(290)));
    await open();
    await type(SAMPLE);
    await type(
      [SAMPLE, ...Array.from({ length: 11 }, (_, at) => `가상 대 ${at}`)].join(
        '\n',
      ),
    );
    expectLineIcon(screen.getByTestId('paste-bad'));
    expectLineIcon(screen.getByTestId('paste-over'));
  });

  it('#2 붙여넣기 창은 위에 고정(top-16 · 세로 translate 0 · max-h 100vh-128) · 확인 창은 가운데 그대로', async () => {
    await setup(seeded(fakeOutline()));
    await open();
    const own = dialog().className.split(/\s+/);
    expect(own).toContain('top-16');
    expect(own).toContain('[translate:-50%_0]');
    expect(own).toContain('max-h-[calc(100vh-128px)]');
    expect(own).not.toContain('top-1/2');
    expect(own).not.toContain('[translate:-50%_-50%]');
    await type('가상 하나');
    fireEvent.click(screen.getByTestId('paste-replace'));
    await flush();
    fireEvent.click(insertButton());
    await flush();
    const confirm = screen.getByTestId('paste-confirm').className.split(/\s+/);
    expect(confirm).toContain('top-1/2');
    expect(confirm).toContain('[translate:-50%_-50%]');
    expect(confirm).not.toContain('top-16');
  });

  it('#3 [붙여넣기] 단추 둘(트리 머리·빈 상태) = 14px(body-05)·높이 36(h-9) · 밑줄 · 옆 더하기 칩은 그대로', async () => {
    const look = (element: HTMLElement) => element.className.split(/\s+/);
    await setup(seeded(fakeOutline()));
    const head = look(button(paste.open));
    expect(head).toEqual(
      expect.arrayContaining(['h-9', 'text-style-pre-body-05', 'underline']),
    );
    expect(head).not.toContain('h-7');
    expect(look(button(words.addSibling))).not.toContain('h-9');
    cleanup();
    await setup(seeded());
    const empty = look(button(paste.open));
    expect(empty).toEqual(
      expect.arrayContaining(['h-9', 'text-style-pre-body-05', 'underline']),
    );
    expect(empty).not.toContain('h-7');
  });
});
