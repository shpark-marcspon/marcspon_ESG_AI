// @vitest-environment jsdom
// 검토·확정·비교 표시 부품(밴드 FW1 ②). 모양만 있는 부품: 값은 props 로 받고 콜백만 부른다.
import { useState } from 'react';

import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { COMPARE_KINDS, COMPARE_LOOK, CompareBadge } from './CompareBadge.tsx';
import { ConfirmReviewDialog } from './ConfirmReviewDialog.tsx';
import { ExcludeReasonDialog } from './ExcludeReasonDialog.tsx';
import type { ExcludeReasonValue } from './ExcludeReasonDialog.tsx';
import { LockBanner } from './LockBanner.tsx';
import { REVIEW_VALUES, ReviewChoice, ReviewMark } from './ReviewChoice.tsx';
import { VersionFlowStrip } from './VersionFlowStrip.tsx';

afterEach(cleanup);

// 키트 radio-group(Radix)은 단추 크기를 ResizeObserver 로 잰다. jsdom 에는 없어서 아무것도 하지 않는 것을 둔다.
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

describe('ExcludeReasonDialog', () => {
  function Harness({
    onSubmit,
  }: {
    onSubmit: (value: ExcludeReasonValue) => void;
  }) {
    const [open, setOpen] = useState(true);
    return (
      <ExcludeReasonDialog
        open={open}
        onOpenChange={setOpen}
        quote="「온실가스 배출량을 크게 줄였습니다.」"
        quoteMeta="기후·환경 30쪽 · Mid"
        onSubmit={onSubmit}
      />
    );
  }

  it('사유 없이 [제외] 를 누르면 칸 아래 오류가 보이고 onSubmit 은 불리지 않는다. 버튼은 꺼져 있지 않다', () => {
    const onSubmit = vi.fn();
    render(<Harness onSubmit={onSubmit} />);
    const dialog = screen.getByRole('dialog', {
      name: '이 문장을 제외할까요?',
    });
    const submit = within(dialog).getByRole('button', { name: '제외' });
    expect((submit as HTMLButtonElement).disabled).toBe(false);
    expect(within(dialog).queryByRole('alert')).toBeNull();
    fireEvent.click(submit);
    expect(onSubmit).not.toHaveBeenCalled();
    expect(within(dialog).getByRole('alert').textContent).toBe(
      '필수 선택 항목이에요',
    );
    const group = within(dialog).getByRole('radiogroup', { name: '제외 사유' });
    expect(group.getAttribute('aria-invalid')).toBe('true');
    expect(group.getAttribute('aria-describedby')).toBe(
      within(dialog).getByRole('alert').id,
    );
  });

  it('사유를 고르면 오류가 사라지고, [제외] 에서 {reason, note} 로 한 번 부른다', () => {
    const onSubmit = vi.fn();
    render(<Harness onSubmit={onSubmit} />);
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: '제외' }));
    expect(within(dialog).getByRole('alert')).toBeTruthy();
    fireEvent.click(
      within(dialog).getByRole('radio', {
        name: '근거가 문서에 있음(AI 가 놓침)',
      }),
    );
    expect(within(dialog).queryByRole('alert')).toBeNull();
    fireEvent.change(within(dialog).getByRole('textbox', { name: '설명' }), {
      target: { value: '  32쪽 표에 기준연도가 있음 ' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: '제외' }));
    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit).toHaveBeenCalledWith({
      reason: 'evidence_in_doc',
      note: '32쪽 표에 기준연도가 있음',
    });
  });

  it('인용 문장이 대화 상자의 설명으로 이어진다', () => {
    render(<Harness onSubmit={vi.fn()} />);
    const dialog = screen.getByRole('dialog');
    const describedBy = dialog.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy!)!.textContent).toContain(
      '「온실가스 배출량을 크게 줄였습니다.」',
    );
  });

  it('text 에 undefined 칸이 와도 기본 문구를 지킨다(사유도)', () => {
    render(
      <ExcludeReasonDialog
        open
        onOpenChange={() => {}}
        quote="「문장」"
        onSubmit={vi.fn()}
        text={{
          title: undefined,
          submit: '빼기',
          reasons: { other: undefined, not_claim: '주장 아님' },
        }}
      />,
    );
    const dialog = screen.getByRole('dialog', {
      name: '이 문장을 제외할까요?',
    });
    expect(within(dialog).getByRole('button', { name: '빼기' })).toBeTruthy();
    expect(within(dialog).getByRole('radio', { name: '기타' })).toBeTruthy();
    expect(
      within(dialog).getByRole('radio', { name: '주장 아님' }),
    ).toBeTruthy();
  });

  it('사유 라디오는 셋(「등급이 맞지 않음」 뺌 — 시안 댓글, sid:MARC-ENT-603)이고 인용 문장이 보인다. [취소] 로 닫힌다', () => {
    render(<Harness onSubmit={vi.fn()} />);
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getAllByRole('radio')).toHaveLength(3);
    expect(
      within(dialog).queryByRole('radio', { name: '등급이 맞지 않음' }),
    ).toBeNull();
    expect(dialog.textContent).not.toContain('등급이 맞지 않음');
    expect(dialog.textContent).toContain(
      '「온실가스 배출량을 크게 줄였습니다.」',
    );
    fireEvent.click(within(dialog).getByRole('button', { name: '취소' }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});

describe('ConfirmReviewDialog', () => {
  const open = (count: number, onConfirm = vi.fn()) =>
    render(
      <ConfirmReviewDialog
        open
        onOpenChange={() => {}}
        unreviewedCount={count}
        onConfirm={onConfirm}
      />,
    );

  it('미검토 0 이면 경고가 없다', () => {
    open(0);
    const dialog = screen.getByRole('dialog', { name: '검토를 확정할까요?' });
    expect(dialog.querySelector('[data-unreviewed]')).toBeNull();
    expect(dialog.textContent).not.toContain('미검토');
    expect(dialog.hasAttribute('aria-describedby')).toBe(false);
  });

  it('미검토 n>0 이면 n 이 글자에 있고 대화 상자의 설명으로 이어진다', () => {
    open(8);
    const dialog = screen.getByRole('dialog');
    const warning = dialog.querySelector('[data-unreviewed]')!;
    expect(warning.textContent).toContain('미검토 문장 8개');
    expect(dialog.getAttribute('aria-describedby')).toBe(warning.id);
  });

  it('pending 이면 [확정] 은 도는 표시를 보이고 눌러도 onConfirm 을 부르지 않는다(두 번 누름 막기)', () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmReviewDialog
        open
        onOpenChange={() => {}}
        unreviewedCount={0}
        onConfirm={onConfirm}
        pending
        text={{ submit: undefined }}
      />,
    );
    const confirm = screen.getByRole('button', { name: /확정/ });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    expect(confirm.getAttribute('aria-busy')).toBe('true');
    fireEvent.click(confirm);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('제목은 Alert 꼴(pre-heading-02, 가운데)이고 [확정] 은 onConfirm 만 부른다', () => {
    const onConfirm = vi.fn();
    open(0, onConfirm);
    const title = screen.getByRole('heading', { name: '검토를 확정할까요?' });
    const classes = title.className.split(/\s+/);
    expect(classes.filter((name) => name.startsWith('text-style-'))).toEqual([
      'text-style-pre-heading-02',
    ]);
    expect(classes).toContain('text-center');
    fireEvent.click(screen.getByRole('button', { name: '확정' }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(screen.getByRole('dialog')).toBeTruthy();
  });
});

describe('ReviewChoice · ReviewMark', () => {
  it('고르는 꼴: 지금 값만 aria-pressed=true, 누르면 onChange 만 부른다', () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <ReviewChoice value="unreviewed" onChange={onChange} />,
    );
    const group = screen.getByRole('group', { name: '검토' });
    const adopt = within(group).getByRole('button', { name: '채택' });
    const exclude = within(group).getByRole('button', { name: '제외' });
    expect(adopt.getAttribute('aria-pressed')).toBe('false');
    expect(exclude.getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(exclude);
    expect(onChange).toHaveBeenCalledWith('excluded');
    // 값은 쓰는 쪽이 바꾼다: props 가 그대로면 눌린 꼴도 그대로다
    expect(exclude.getAttribute('aria-pressed')).toBe('false');
    rerender(<ReviewChoice value="adopted" onChange={onChange} />);
    expect(adopt.getAttribute('aria-pressed')).toBe('true');
    expect(exclude.getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(adopt);
    expect(onChange).toHaveBeenLastCalledWith('adopted');
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it('읽기 전용 꼴: 세 값 모두 글자가 있다', () => {
    for (const value of REVIEW_VALUES) {
      const { container, unmount } = render(<ReviewMark value={value} />);
      expect(container.textContent?.trim(), value).not.toBe('');
      unmount();
    }
  });
});

describe('CompareBadge', () => {
  it('일곱 분류 모두 빈 글자가 아니고 계약 값의 글자를 쓴다', () => {
    expect(COMPARE_KINDS).toHaveLength(7);
    for (const kind of COMPARE_KINDS) {
      expect(COMPARE_LOOK[kind].label.trim(), kind).not.toBe('');
      const { container, unmount } = render(<CompareBadge kind={kind} />);
      expect(container.querySelector('[data-compare]')?.textContent, kind).toBe(
        COMPARE_LOOK[kind].badge,
      );
      unmount();
    }
    expect(COMPARE_LOOK.resolved_deleted.label).toBe('해소 · 문장 삭제');
    expect(COMPARE_LOOK.out_of_scope.label).toBe('범위 밖');
  });

  it('모르는 분류는 타입 오류다', () => {
    // @ts-expect-error — 'resolved' 는 CompareKind 가 아니다
    const element = <CompareBadge kind="resolved" />;
    expect(element).toBeTruthy();
  });
});

describe('LockBanner · VersionFlowStrip', () => {
  it('잠금 띠의 문구 함수는 사람·일시를 따로 받는다', () => {
    const text = vi.fn(
      ({ by, at }: { by: string; at: string }) => `${by} · ${at}`,
    );
    const { container } = render(
      <LockBanner at="2026-10-16 10:20" by="담당자 A" text={text} />,
    );
    expect(text).toHaveBeenCalledWith({
      by: '담당자 A',
      at: '2026-10-16 10:20',
    });
    expect(container.textContent).toBe('담당자 A · 2026-10-16 10:20');
  });

  it('잠금 띠는 확정한 일시·사람을 글자로 보인다', () => {
    const { container } = render(
      <LockBanner at="2026-10-16 10:20" by="담당자 A" />,
    );
    expect(container.textContent).toContain(
      '2026-10-16 10:20 담당자 A님이 확정했어요',
    );
    expect(container.querySelector('svg[aria-hidden]')).not.toBeNull();
  });

  it('버전 흐름: 버전마다 High·Mid 건수, 고른 두 버전에 「비교 대상」·「이번」 글자', () => {
    render(
      <VersionFlowStrip
        versions={[
          { id: 'v1', name: 'v1', high: 9, mid: 10 },
          { id: 'v2', name: 'v2', high: 4, mid: 8, pick: 'base' },
          { id: 'v3', name: 'v3', high: 3, mid: 7, pick: 'current' },
        ]}
      />,
    );
    const list = screen.getByRole('list', { name: '버전 흐름' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    // 칸마다 본다: 이름, 등급 건수 둘(배지 하나씩), 고른 표시
    const first = within(items[0]!);
    expect(first.getByText('v1')).toBeTruthy();
    expect(first.getByText('High 9')).toBeTruthy();
    expect(first.getByText('Mid 10')).toBeTruthy();
    expect(first.queryByText('비교 대상')).toBeNull();
    expect(first.queryByText('이번')).toBeNull();
    expect(within(items[1]!).getByText('비교 대상')).toBeTruthy();
    expect(within(items[1]!).getByText('High 4')).toBeTruthy();
    expect(within(items[2]!).getByText('이번')).toBeTruthy();
    expect(within(items[2]!).getByText('Mid 7')).toBeTruthy();
    expect(list.querySelectorAll('svg[aria-hidden]')).toHaveLength(2);
  });
});
