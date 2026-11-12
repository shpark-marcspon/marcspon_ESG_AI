// @vitest-environment jsdom
// 그린워싱 배지 둘과 단계 띠(밴드 FW1 ①).
// 모든 값이 글자를 가진다(색만으로 알리지 않는다). 모르는 값은 타입 오류(typecheck 가 @ts-expect-error 줄을 지킨다).
import { cleanup, render, screen, within } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { RISK_BADGE_LOOK, RISK_LEVELS, RiskBadge } from './RiskBadge.tsx';
import {
  RUN_STATUS_KINDS,
  RUN_STATUS_LOOK,
  RunStatusBadge,
} from './RunStatusBadge.tsx';
import type { RunStatus } from './RunStatusBadge.tsx';
import { StepFlow } from './StepFlow.tsx';

afterEach(cleanup);

const SAMPLE: Record<RunStatus['kind'], RunStatus> = {
  analyzing: { kind: 'analyzing', progress: 62 },
  failed: { kind: 'failed' },
  pending: { kind: 'pending' },
  reviewing: { kind: 'reviewing', reviewed: 14, total: 22 },
  confirmed: { kind: 'confirmed', by: '담당자 B', at: '10-06' },
};

describe('RiskBadge', () => {
  it('모든 등급이 글자를 가진다', () => {
    for (const level of RISK_LEVELS) {
      expect(RISK_BADGE_LOOK[level].label.trim()).not.toBe('');
      const { container, unmount } = render(<RiskBadge level={level} />);
      expect(container.textContent?.trim()).toBe(RISK_BADGE_LOOK[level].label);
      unmount();
    }
  });

  it('건수를 주면 글자 뒤에 붙는다. 점은 화면 읽기에서 숨긴다', () => {
    const { container } = render(<RiskBadge level="high" count={9} />);
    expect(container.textContent).toBe('High 9');
    expect(container.querySelector('[aria-hidden]')).not.toBeNull();
  });

  it('숫자만 꼴(display="count"): 등급 글자 없이 건수, 점은 남는다. 0 이면 등급과 상관없이 회색 「0」', () => {
    const { container, rerender } = render(
      <RiskBadge level="high" count={9} display="count" />,
    );
    const badge = () => container.querySelector('[data-level]')!;
    expect(container.textContent).toBe('9');
    expect(badge().querySelector('[aria-hidden]')).not.toBeNull();
    expect(badge().className).toContain('bg-support-error-subtle');
    rerender(<RiskBadge level="high" count={0} display="count" />);
    expect(container.textContent).toBe('0');
    expect(badge().className).toContain('bg-background-tertiary');
    expect(badge().className).not.toContain('bg-support-error-subtle');
    rerender(<RiskBadge level="mid" count={0} display="count" />);
    expect(badge().className).toContain('bg-background-tertiary');
    // 글자 꼴은 0 이어도 등급 색 그대로(「High 0」)
    rerender(<RiskBadge level="high" count={0} />);
    expect(container.textContent).toBe('High 0');
    expect(badge().className).toContain('bg-support-error-subtle');
  });

  it('등급마다 다른 키트 변형이다(같은 색 둘이 없다)', () => {
    const variants = RISK_LEVELS.map((level) => RISK_BADGE_LOOK[level].variant);
    expect(new Set(variants).size).toBe(RISK_LEVELS.length);
  });

  it('모르는 등급은 타입 오류다', () => {
    // @ts-expect-error — 'extreme' 은 RiskLevel 이 아니다
    const element = <RiskBadge level="extreme" />;
    expect(element).toBeTruthy();
  });
});

describe('RunStatusBadge', () => {
  it('모든 상태가 빈 글자가 아니다(표와 그린 결과 모두)', () => {
    for (const kind of RUN_STATUS_KINDS) {
      expect(RUN_STATUS_LOOK[kind].label.trim(), kind).not.toBe('');
      const { container, unmount } = render(
        <RunStatusBadge status={SAMPLE[kind]} />,
      );
      const badge = container.querySelector(`[data-status="${kind}"]`)!;
      expect(badge.textContent?.trim(), kind).not.toBe('');
      expect(badge.textContent, kind).toContain(RUN_STATUS_LOOK[kind].label);
      unmount();
    }
  });

  it('상태마다 다른 키트 변형이다', () => {
    const variants = RUN_STATUS_KINDS.map(
      (kind) => RUN_STATUS_LOOK[kind].variant,
    );
    expect(new Set(variants).size).toBe(RUN_STATUS_KINDS.length);
  });

  it('진행률·검토 수·확정한 사람과 날짜를 글자로 보인다', () => {
    render(
      <>
        <RunStatusBadge status={SAMPLE.analyzing} />
        <RunStatusBadge status={{ kind: 'analyzing' }} />
        <RunStatusBadge status={SAMPLE.failed} />
        <RunStatusBadge status={SAMPLE.reviewing} />
        <div data-testid="confirmed">
          <RunStatusBadge status={SAMPLE.confirmed} />
        </div>
      </>,
    );
    // 이름은 시안 댓글 1차 반영(sid:MARC-ENT-603): AI 점검 중 · 검토 대기 · 검토 완료
    expect(screen.getByText('AI 점검 중 62%')).toBeTruthy();
    expect(screen.getByText('AI 점검 중')).toBeTruthy();
    // 멈춘 실행은 「멈춤」(디자인 답 D6 — 탭 「멈춤」·GW-03 「점검이 멈췄어요」와 말을 맞춤, 밴드 GW2R)
    expect(screen.getByText('멈춤')).toBeTruthy();
    expect(screen.getByText('검토 중 14/22')).toBeTruthy();
    const confirmed = screen.getByTestId('confirmed');
    expect(within(confirmed).getByText('검토 완료')).toBeTruthy();
    expect(confirmed.textContent).toContain('10-06 담당자 B');
    expect(confirmed.querySelector('svg[aria-hidden]')).not.toBeNull();
  });

  it('showCount={false} 면 검토 중의 n/전체를 뺀다(상세 화면 제목 줄. 디자인 대조 C6). 다른 상태는 그대로', () => {
    render(
      <>
        <div data-testid="no-count">
          <RunStatusBadge status={SAMPLE.reviewing} showCount={false} />
        </div>
        <div data-testid="analyzing">
          <RunStatusBadge status={SAMPLE.analyzing} showCount={false} />
        </div>
      </>,
    );
    expect(screen.getByTestId('no-count').textContent).toBe('검토 중');
    expect(screen.getByTestId('analyzing').textContent).toBe('AI 점검 중 62%');
  });

  it('확정은 자물쇠를 늘 그린다. 사람·날짜가 둘 다 없으면 그 글자 칸만 그리지 않는다', () => {
    const { container, rerender } = render(
      <RunStatusBadge status={{ kind: 'confirmed' }} />,
    );
    expect(container.querySelector('svg[aria-hidden]')).not.toBeNull();
    expect(container.querySelector('[data-confirmed-by]')).toBeNull();
    expect(container.textContent).toBe('검토 완료');
    rerender(<RunStatusBadge status={{ kind: 'confirmed', at: '10-06' }} />);
    expect(container.querySelector('svg[aria-hidden]')).not.toBeNull();
    expect(container.querySelector('[data-confirmed-by]')!.textContent).toBe(
      '10-06',
    );
  });

  it('모르는 상태는 타입 오류다', () => {
    // @ts-expect-error — 'archived' 는 RunStatus 의 kind 가 아니다
    const element = <RunStatusBadge status={{ kind: 'archived' }} />;
    // @ts-expect-error — 검토 중은 reviewed·total 이 있어야 한다
    const partial = <RunStatusBadge status={{ kind: 'reviewing' }} />;
    expect([element, partial]).toHaveLength(2);
  });
});

describe('StepFlow', () => {
  it('세 단계를 순서 있는 목록으로 그리고, 지금 단계에만 aria-current="step"', () => {
    render(<StepFlow current={2} />);
    const list = screen.getByRole('list', { name: '점검 단계' });
    expect(list.tagName).toBe('OL');
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    const current = list.querySelectorAll('[aria-current="step"]');
    expect(current).toHaveLength(1);
    // 칸마다 본다: 굵은 「STEP 2」와 단계 이름
    const step = within(current[0] as HTMLElement);
    expect(step.getByText('STEP 2').tagName).toBe('B');
    expect(step.getByText('문장 찾기·판정')).toBeTruthy();
    // 화살표는 단계 사이 둘뿐이고 꾸밈이다
    expect(list.querySelectorAll('svg[aria-hidden]')).toHaveLength(2);
  });

  it('범위 밖 단계면 고른 단계가 없다. 단계 이름은 props 로 바꾼다', () => {
    render(<StepFlow current={0} steps={['가', '나']} label="단계" />);
    const list = screen.getByRole('list', { name: '단계' });
    expect(list.querySelectorAll('[aria-current]')).toHaveLength(0);
    expect(within(list).getAllByRole('listitem')).toHaveLength(2);
  });
});
