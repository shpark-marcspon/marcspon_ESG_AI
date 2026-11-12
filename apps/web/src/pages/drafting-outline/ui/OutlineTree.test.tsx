// @vitest-environment jsdom
// RP-03 트리 칸·편집 칸 손질(밴드 RPW7 §2 — §1-E 표 한 줄 = 시험 하나). 진짜 실어댑터 + 가짜 원고작성 서버, 지어낸 값만. 끌기 손은 e2e/drafting-outline.spec.ts.
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
const flush = () => act(async () => {});
const PUT = 'PUT /drafting/projects/1/outline';

const node = (
  key: string,
  parentKey: string | null,
  depth: number,
  requirement = '',
): OutlineNode => ({
  key,
  parentKey,
  depth,
  title: `가상 ${key}`,
  requirement,
});

/** 1 a · 1.1 b · 1.1.1 c · 1.1.1.1 d · 1.2 e · 2 f. */
const LIST = () => [
  node('a', null, 1),
  node('b', 'a', 2),
  node('c', 'b', 3),
  node('d', 'c', 4),
  node('e', 'a', 2, '가상 요구 e'),
  node('f', null, 1),
];

async function setup(nodes: OutlineNode[] | null = LIST()) {
  const server = fakeDraftingServer({
    projects: [{ id: 1, name: '가상 보고서', year: 2026 }],
  });
  server.seedProject(1, {
    documentId: server.seedDocument(),
    ...(nodes ? { nodes } : {}),
  });
  let n = 0;
  render(
    <OutlineScreen
      store={storeOf(server)}
      projectId={1}
      operator={false}
      onRun={vi.fn()}
      onList={vi.fn()}
      nodeKey={() => `n${(n += 1)}`}
    />,
  );
  await flush();
  return server;
}

const row = (key: string) =>
  document.querySelector<HTMLElement>(`[data-key="${key}"]`)!;
const keys = () =>
  screen
    .getAllByRole('option')
    .map(
      (one) =>
        `${one.getAttribute('data-key')}:${one.getAttribute('data-depth')}`,
    );
const selectedKey = () =>
  screen
    .getAllByRole('option')
    .find((one) => one.getAttribute('aria-selected') === 'true')!
    .getAttribute('data-key');
const nameInput = () =>
  screen.getByLabelText(words.nameLabel) as HTMLInputElement;
const button = (name: string) => screen.getByRole('button', { name });
/** 그 줄을 고르고 초점을 준다. */
const focusOn = (key: string) => {
  fireEvent.click(row(key));
  row(key).focus();
  return row(key);
};
const key = (target: Element, name: string, more = {}) =>
  fireEvent.keyDown(target, { key: name, ...more });

describe('§1-E 줄 키보드', () => {
  it('↓ — 아래 줄 고름 + 초점 따라감 · 창 스크롤 막음', async () => {
    await setup();
    const prevented = !key(focusOn('a'), 'ArrowDown');
    expect(prevented).toBe(true);
    expect(selectedKey()).toBe('b');
    expect(document.activeElement).toBe(row('b'));
  });

  it('↑ — 위 줄 고름 + 초점 따라감', async () => {
    await setup();
    key(focusOn('c'), 'ArrowUp');
    expect(selectedKey()).toBe('b');
    expect(document.activeElement).toBe(row('b'));
  });

  it('↑↓ 끝에서 멈춤(돌지 않음)', async () => {
    await setup();
    key(focusOn('a'), 'ArrowUp');
    expect(selectedKey()).toBe('a');
    key(focusOn('f'), 'ArrowDown');
    expect(selectedKey()).toBe('f');
  });

  it('Enter — 이름 칸 초점(글 선택 없음)', async () => {
    await setup();
    key(focusOn('c'), 'Enter');
    expect(document.activeElement).toBe(nameInput());
    expect(nameInput().selectionStart).toBe(nameInput().selectionEnd);
    expect(keys()).toEqual(['a:1', 'b:2', 'c:3', 'd:4', 'e:2', 'f:1']);
  });

  it('Space — 고르기', async () => {
    await setup();
    row('e').focus();
    key(row('e'), ' ');
    expect(selectedKey()).toBe('e');
  });

  it('Tab — 한 단계 내리기 · 초점은 그 줄', async () => {
    await setup();
    const prevented = !key(focusOn('e'), 'Tab');
    expect(prevented).toBe(true);
    expect(keys()).toEqual(['a:1', 'b:2', 'c:3', 'd:4', 'e:3', 'f:1']);
    expect(document.activeElement).toBe(row('e'));
  });

  it('Tab — 못 옮겨도 preventDefault · 데이터·dirty 그대로', async () => {
    await setup();
    const prevented = !key(focusOn('b'), 'Tab');
    expect(prevented).toBe(true);
    expect(keys()).toEqual(['a:1', 'b:2', 'c:3', 'd:4', 'e:2', 'f:1']);
    expect(screen.queryByTestId('outline-dirty')).toBeNull();
    expect(document.activeElement).toBe(row('b'));
  });

  it('Alt+↑ — 하위와 함께 한 칸 위로 · 초점은 옮긴 줄 · 창 스크롤 막음(RPW12)', async () => {
    await setup();
    const prevented = !key(focusOn('e'), 'ArrowUp', { altKey: true });
    expect(prevented).toBe(true);
    expect(keys()).toEqual(['a:1', 'e:2', 'b:2', 'c:3', 'd:4', 'f:1']);
    expect(selectedKey()).toBe('e');
    expect(document.activeElement).toBe(row('e'));
    expect(screen.getByTestId('outline-dirty').textContent).toBe(words.dirty);
  });

  it('Alt+↓ — 하위(c·d)와 함께 한 칸 아래로 · 초점은 옮긴 줄(RPW12)', async () => {
    await setup();
    key(focusOn('b'), 'ArrowDown', { altKey: true });
    expect(keys()).toEqual(['a:1', 'e:2', 'b:2', 'c:3', 'd:4', 'f:1']);
    expect(selectedKey()).toBe('b');
    expect(document.activeElement).toBe(row('b'));
  });

  it('Alt+↑↓ 끝에서 0 — 목록·고름·dirty 그대로 · 초점 남음(RPW12)', async () => {
    await setup();
    const before = keys();
    key(focusOn('b'), 'ArrowUp', { altKey: true });
    key(focusOn('e'), 'ArrowDown', { altKey: true });
    key(focusOn('f'), 'ArrowDown', { altKey: true });
    key(focusOn('a'), 'ArrowUp', { altKey: true });
    expect(keys()).toEqual(before);
    expect(selectedKey()).toBe('a');
    expect(document.activeElement).toBe(row('a'));
    expect(screen.queryByTestId('outline-dirty')).toBeNull();
  });

  it('초점 복구 — 뒤 형제가 있는 줄을 Shift+Tab(DOM 이 옮겨짐) → 초점 그 줄 → 이어 Tab = 단계 내려감', async () => {
    await setup([
      node('a', null, 1),
      node('b', 'a', 2),
      node('c', 'b', 3),
      node('x', 'b', 3),
      node('e', 'a', 2),
    ]);
    key(focusOn('c'), 'Tab', { shiftKey: true });
    expect(keys()).toEqual(['a:1', 'b:2', 'x:3', 'c:2', 'e:2']);
    expect(document.activeElement).toBe(row('c'));
    key(document.activeElement!, 'Tab');
    expect(keys()).toEqual(['a:1', 'b:2', 'x:3', 'c:3', 'e:2']);
    expect(document.activeElement).toBe(row('c'));
  });

  it('초점 복구 — 줄 아이콘을 누른 뒤에도 초점은 그 줄', async () => {
    await setup();
    focusOn('e');
    const up = within(row('e')).getByRole('button', { name: words.up });
    up.focus();
    fireEvent.click(up);
    expect(keys()).toEqual(['a:1', 'e:2', 'b:2', 'c:3', 'd:4', 'f:1']);
    expect(document.activeElement).toBe(row('e'));
  });

  it('Delete — 확인 창 · 닫으면 초점은 고른 줄 · 지운 뒤엔 새로 고른 줄', async () => {
    await setup();
    key(focusOn('c'), 'Delete');
    let dialog = await screen.findByTestId('remove-dialog');
    expect(dialog.textContent).toContain(words.removeChildren(1));
    fireEvent.click(within(dialog).getByRole('button', { name: words.cancel }));
    await waitFor(() => expect(document.activeElement).toBe(row('c')));
    key(row('c'), 'Delete');
    dialog = await screen.findByTestId('remove-dialog');
    fireEvent.click(
      within(dialog).getByRole('button', { name: words.removeYes }),
    );
    expect(keys()).toEqual(['a:1', 'b:2', 'e:2', 'f:1']);
    expect(selectedKey()).toBe('e');
    await waitFor(() => expect(document.activeElement).toBe(row('e')));
  });

  it('Backspace — 줄에 초점일 때 Delete 와 같다', async () => {
    await setup();
    key(focusOn('f'), 'Backspace');
    expect(await screen.findByTestId('remove-dialog')).toBeTruthy();
  });

  it('요구 칸·이름 칸의 키는 목록을 건드리지 않는다', async () => {
    await setup();
    fireEvent.click(row('e'));
    const area = screen.getByLabelText(words.requirementLabel);
    for (const name of ['ArrowUp', 'ArrowDown', 'Tab', 'Delete', 'Enter']) {
      key(area, name);
      expect(selectedKey()).toBe('e');
    }
    for (const name of ['ArrowUp', 'ArrowDown', 'Tab', 'Delete', 'Backspace'])
      key(nameInput(), name);
    expect(selectedKey()).toBe('e');
    expect(keys()).toEqual(['a:1', 'b:2', 'c:3', 'd:4', 'e:2', 'f:1']);
    expect(screen.queryByTestId('remove-dialog')).toBeNull();
  });

  it('이름 칸 Enter — 같은 단계 새 줄 + 글 전체 선택', async () => {
    await setup();
    fireEvent.click(row('b'));
    key(nameInput(), 'Enter');
    expect(keys()).toEqual(['a:1', 'b:2', 'c:3', 'd:4', 'n1:2', 'e:2', 'f:1']);
    expect(selectedKey()).toBe('n1');
    expect(document.activeElement).toBe(nameInput());
    expect(nameInput().selectionStart).toBe(0);
    expect(nameInput().selectionEnd).toBe(words.newTitle.length);
  });

  it('이름 칸 Enter — 한글 조합 중이면 줄이 늘지 않는다', async () => {
    await setup();
    fireEvent.click(row('b'));
    key(nameInput(), 'Enter', { isComposing: true });
    expect(keys()).toHaveLength(6);
  });

  it('busy — 줄 키 · 더하기 0', async () => {
    const server = await setup();
    fireEvent.change(nameInput(), { target: { value: '가상 고침' } });
    let open!: () => void;
    const gate = new Promise<void>((resolve) => (open = resolve));
    server.override[PUT] = [
      async () => {
        await gate;
        return new Response(JSON.stringify({ outlineId: 1, revision: 1 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      },
    ];
    focusOn('e');
    fireEvent.click(button(words.save));
    await flush();
    const before = keys();
    for (const name of ['Tab', 'ArrowUp', 'Delete', 'Enter'])
      key(row('e'), name);
    key(row('e'), 'ArrowUp', { altKey: true });
    expect(keys()).toEqual(before);
    expect(selectedKey()).toBe('e');
    expect(screen.queryByTestId('remove-dialog')).toBeNull();
    expect(button(words.addTop).hasAttribute('disabled')).toBe(true);
    await act(async () => open());
  });
});

describe('§1-A 트리 틀', () => {
  it('탭 멈춤 — 고른 줄 하나만 0, 나머지 −1 · 아이콘 −1', async () => {
    await setup();
    fireEvent.click(row('c'));
    expect(
      screen
        .getAllByRole('option')
        .filter((one) => one.getAttribute('tabindex') === '0')
        .map((one) => one.getAttribute('data-key')),
    ).toEqual(['c']);
    for (const icon of within(screen.getByTestId('tree-icons')).getAllByRole(
      'button',
    ))
      expect(icon.getAttribute('tabindex')).toBe('-1');
  });

  it('아이콘 다섯은 고른 줄에만 · 이름 · 켜짐 = 옮길 수 있는 쪽', async () => {
    await setup();
    expect(screen.getAllByTestId('tree-icons')).toHaveLength(1);
    fireEvent.click(row('b'));
    const icons = within(screen.getByTestId('tree-icons')).getAllByRole(
      'button',
    );
    expect(icons.map((one) => one.getAttribute('aria-label'))).toEqual([
      words.up,
      words.down,
      words.outdent,
      words.indent,
      words.remove,
    ]);
    expect(icons.map((one) => one.hasAttribute('disabled'))).toEqual([
      true, // 첫 형제
      false,
      false,
      true, // 앞 형제 없음
      false,
    ]);
  });

  it('줄 꼴 — 들여쓰기 16 + 16×(단계−1) · 대제목 굵게 · 단계 글자', async () => {
    await setup();
    expect(row('a').style.paddingLeft).toBe('16px');
    expect(row('d').style.paddingLeft).toBe('64px');
    expect(row('f').className).toContain('font-bold');
    expect(row('e').className).not.toContain('font-bold');
    expect(within(row('d')).getByTestId('tree-marks').textContent).toContain(
      words.depths[3],
    );
  });

  it('더하기 셋 — 같은 단계는 아래 단계 끝 뒤 · 대제목은 그 대제목 뒤 · 소소에서 아래 단계 꺼짐 · 초점·글 선택', async () => {
    await setup();
    fireEvent.click(row('b'));
    fireEvent.click(button(words.addSibling));
    expect(keys()).toEqual(['a:1', 'b:2', 'c:3', 'd:4', 'n1:2', 'e:2', 'f:1']);
    expect(document.activeElement).toBe(nameInput());
    expect(nameInput().selectionEnd).toBe(words.newTitle.length);
    fireEvent.click(row('c'));
    fireEvent.click(button(words.addTop));
    expect(keys()).toEqual([
      'a:1',
      'b:2',
      'c:3',
      'd:4',
      'n1:2',
      'e:2',
      'n2:1',
      'f:1',
    ]);
    expect(document.activeElement).toBe(nameInput());
    expect(nameInput().selectionStart).toBe(0);
    fireEvent.click(row('b'));
    fireEvent.click(button(words.addChild));
    expect(keys()).toContain('n3:3');
    expect(document.activeElement).toBe(nameInput());
    expect(nameInput().selectionEnd).toBe(words.newTitle.length);
    fireEvent.click(row('d'));
    expect(button(words.addChild).hasAttribute('disabled')).toBe(true);
    expect(button(words.addSibling).hasAttribute('disabled')).toBe(false);
  });

  it('빈 상태 — 한 덩어리 + 대제목 더하기 하나 · 두 칸 0 · 더하면 이름 칸 초점', async () => {
    await setup(null);
    expect(screen.getByTestId('outline-empty').textContent).toBe(words.empty);
    expect(screen.queryByTestId('outline-tree')).toBeNull();
    expect(screen.queryByTestId('outline-editor')).toBeNull();
    expect(screen.queryByRole('button', { name: words.addSibling })).toBeNull();
    fireEvent.click(button(words.addTop));
    expect(keys()).toEqual(['n1:1']);
    expect(document.activeElement).toBe(nameInput());
    expect(nameInput().selectionEnd).toBe(words.newTitle.length);
  });

  it('판 글자 — 도움말 · 요구 안내 끝 · 삭제 단추 · 머리 N개는 14줄 넘을 때만', async () => {
    await setup();
    expect(screen.getByTestId('outline-help').textContent).toBe(
      '↑↓ 고르기 · Alt+↑↓ 옮기기 · Enter 이름 고치기 · Tab 한 단계 내리기 · Shift+Tab 올리기 · Delete 지우기',
    );
    expect(screen.getByRole('listbox').getAttribute('aria-describedby')).toBe(
      screen.getByTestId('outline-help').id,
    );
    expect(screen.queryByTestId('tree-total')).toBeNull();
    fireEvent.click(row('e'));
    expect(document.body.textContent).toContain('기준으로 써요 · 2,000자까지');
    // [삭제] 는 올려도 글이 빨강 그대로(판 `.rp-del:hover` 는 바탕만).
    expect(button(words.removeShort).className).toContain(
      'hover:text-support-error',
    );
    cleanup();
    const many = Array.from({ length: 15 }, (_, at) => node(`r${at}`, null, 1));
    await setup(many);
    expect(screen.getByTestId('tree-total').textContent).toBe('15개');
    cleanup();
    await setup(many.slice(0, 14));
    expect(screen.queryByTestId('tree-total')).toBeNull();
  });
});

describe('§1-B 편집 칸', () => {
  it('머리 한 줄 — 경로 · 이름 · 단계 배지 · 삭제 · 이름 칸 60%(순서 단추 줄은 RPW12 에서 걷음)', async () => {
    await setup();
    fireEvent.click(row('c'));
    const head = screen.getByTestId('node-path');
    expect(head.textContent).toContain('가상 a › 가상 b › 가상 c');
    expect(head.textContent).toContain(words.depthBadges[2]);
    expect(nameInput().className).toContain('w-3/5');
    const editor = within(screen.getByTestId('outline-editor'));
    expect(editor.queryByRole('button', { name: words.remove })).toBeNull();
    fireEvent.click(editor.getByRole('button', { name: words.removeShort }));
    expect(await screen.findByTestId('remove-dialog')).toBeTruthy();
  });

  it('안내는 편집 칸 맨 아래 PageInfo', async () => {
    await setup();
    const guide = within(screen.getByTestId('outline-editor')).getByTestId(
      'outline-guide',
    );
    expect(guide.textContent).toBe(words.guide(3));
  });

  it('상위 · 글 없음 — 칸 숨기고 한 줄', async () => {
    await setup();
    fireEvent.click(row('b'));
    expect(screen.getByTestId('requirement-upper').textContent).toBe(
      words.upperHint,
    );
    expect(screen.queryByLabelText(words.requirementLabel)).toBeNull();
  });

  it('잎 — 칸 그대로 · 글 따라 늘어나는 클래스', async () => {
    await setup();
    fireEvent.click(row('d'));
    const area = screen.getByLabelText(words.requirementLabel);
    expect(area.className).toContain('[field-sizing:content]');
    expect(area.className).toContain('min-h-[108px]');
    expect(area.className).not.toContain('min-h-20');
    expect(screen.queryByTestId('requirement-upper')).toBeNull();
  });

  it('상위 · 글 남음 — 읽기 전용 + 안 지우면 저장 본문에 그대로 · 다시 잎이면 칸에 글', async () => {
    const server = await setup();
    fireEvent.click(row('e'));
    fireEvent.click(button(words.addChild));
    fireEvent.click(row('e'));
    const left = screen.getByTestId('requirement-leftover');
    expect(left.textContent).toBe('가상 요구 e');
    expect(left.getAttribute('aria-readonly')).toBe('true');
    expect(document.body.textContent).toContain(words.upperLeftover);
    fireEvent.click(button(words.save));
    await flush();
    const [body] = server.bodies(PUT) as { nodes: OutlineNode[] }[];
    expect(body!.nodes.find((one) => one.key === 'e')!.requirement).toBe(
      '가상 요구 e',
    );
    // 아래 단계를 지우면 다시 잎.
    fireEvent.click(row('n1'));
    fireEvent.click(button(words.removeShort));
    fireEvent.click(
      within(await screen.findByTestId('remove-dialog')).getByRole('button', {
        name: words.removeYes,
      }),
    );
    fireEvent.click(row('e'));
    expect(
      (screen.getByLabelText(words.requirementLabel) as HTMLTextAreaElement)
        .value,
    ).toBe('가상 요구 e');
  });

  it('상위 · 글 남음 — [글 지우기] → 한 줄 · 저장 본문 빈 글', async () => {
    const server = await setup();
    fireEvent.click(row('e'));
    fireEvent.click(button(words.addChild));
    fireEvent.click(row('e'));
    fireEvent.click(button(words.clearRequirement));
    expect(screen.getByTestId('requirement-upper')).toBeTruthy();
    expect(screen.queryByTestId('requirement-leftover')).toBeNull();
    fireEvent.click(button(words.save));
    await flush();
    const [body] = server.bodies(PUT) as { nodes: OutlineNode[] }[];
    expect(body!.nodes.find((one) => one.key === 'e')!.requirement).toBe('');
  });

  it('상위 · 글이 상한을 넘음 — 저장을 누르면 까닭을 함께 보인다', async () => {
    const long = '가'.repeat(2001);
    await setup([node('a', null, 1, long), node('b', 'a', 2)]);
    fireEvent.change(nameInput(), { target: { value: '가상 고침' } });
    fireEvent.click(button(words.save));
    await flush();
    expect(screen.getByText(words.requirementProblem(2000))).toBeTruthy();
    expect(button(words.clearRequirement)).toBeTruthy();
  });
});

describe('RPW8 재대조', () => {
  /** 고른 줄로 간 focus 호출의 옵션들(줄 li 에 간 것만). */
  const spyRowFocus = () => {
    const calls: unknown[] = [];
    const original = HTMLElement.prototype.focus;
    const spy = vi
      .spyOn(HTMLElement.prototype, 'focus')
      .mockImplementation(function (this: HTMLElement, options) {
        if (this.getAttribute('role') === 'option') calls.push(options);
        original.call(this, options);
      });
    return { calls, restore: () => spy.mockRestore() };
  };

  it('④ 「목차 이름」 label 안 글 뒤에 필수 점 · 요구·순서 칸에는 0', async () => {
    await setup();
    fireEvent.click(row('d'));
    const label = document.querySelector(`label[for="${nameInput().id}"]`)!;
    expect(label.textContent).toBe(words.nameLabel);
    expect(label.lastElementChild?.hasAttribute('data-required-mark')).toBe(
      true,
    );
    const editor = screen.getByTestId('outline-editor');
    expect(editor.querySelectorAll('[data-required-mark]')).toHaveLength(1);
  });

  it('N2 [삭제] 는 경로·이름·배지 묶음 밖 형제 · shrink-0 · 묶음은 min-w-0 flex-1 flex-wrap', async () => {
    await setup();
    fireEvent.click(row('c'));
    const head = screen.getByTestId('node-path');
    const remove = within(screen.getByTestId('outline-editor')).getByRole(
      'button',
      { name: words.removeShort },
    );
    expect(head.contains(remove)).toBe(false);
    expect(remove.parentElement).toBe(head.parentElement);
    expect(head.nextElementSibling).toBe(remove);
    expect(remove.className).toContain('shrink-0');
    expect(remove.className).not.toContain('ml-auto');
    for (const one of ['min-w-0', 'flex-1', 'flex-wrap'])
      expect(head.className.split(' ')).toContain(one);
    expect(head.parentElement!.className).toContain('items-start');
    expect(head.querySelector('b')!.className).not.toContain('break-all');
  });

  it('N1 키보드 ↓ — 줄 초점에 focusVisible 옵션 없음(테두리 보임)', async () => {
    await setup();
    const target = focusOn('a');
    const { calls, restore } = spyRowFocus();
    key(target, 'ArrowDown');
    restore();
    expect(document.activeElement).toBe(row('b'));
    expect(calls).toEqual([{ preventScroll: true }]);
  });

  it('N1 손잡이 클릭 — 줄 초점이 focusVisible:false', async () => {
    await setup();
    const { calls, restore } = spyRowFocus();
    fireEvent.click(
      row('c').querySelector<HTMLElement>('[data-testid="tree-grip"]')!,
    );
    restore();
    expect(selectedKey()).toBe('c');
    expect(document.activeElement).toBe(row('c'));
    expect(calls).toEqual([{ preventScroll: true, focusVisible: false }]);
  });

  it('N1 창 닫힘 — 줄 초점에 focusVisible 옵션 없음', async () => {
    await setup();
    key(focusOn('c'), 'Delete');
    const dialog = await screen.findByTestId('remove-dialog');
    const { calls, restore } = spyRowFocus();
    fireEvent.click(within(dialog).getByRole('button', { name: words.cancel }));
    await waitFor(() => expect(document.activeElement).toBe(row('c')));
    restore();
    expect(calls).toContainEqual({ preventScroll: true });
    expect(calls).not.toContainEqual(
      expect.objectContaining({ focusVisible: false }),
    );
  });
});
