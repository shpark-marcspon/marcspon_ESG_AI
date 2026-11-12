// @vitest-environment jsdom
// 실패 카드(밴드 TRW0b, 발주서 §3-4, 결정 sid:MARC-ENT-393): 서버 오류·일부 쪽 → [이 파트만 다시] 하나(누르면 onRetry 한 번) ·
// single → [다시 실행] · 막음(rejected) → 단추 0·까닭 글(다섯 각각)·파일 줄 · 콜백 없으면 단추 0 · 「실패한 쪽만 다시」 없음.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { TR_TEXT } from '../config/text.ts';
import { REJECTION_KEYS } from '../model/index.ts';
import { PartFailureCard } from './PartFailureCard.tsx';
import { rejectionText } from './labels.ts';

afterEach(cleanup);

const FILE_LINE = 'sample_report_ko_extract.docx · 스토리 4~41쪽(38쪽)';

describe('PartFailureCard', () => {
  it.each(['server_error', 'partial'] as const)(
    '%s: [이 파트만 다시] 하나, 누르면 onRetry 한 번, 안내 글',
    (kind) => {
      const onRetry = vi.fn();
      render(<PartFailureCard kind={kind} onRetry={onRetry} />);
      const buttons = screen.getAllByRole('button');
      expect(buttons).toHaveLength(1);
      expect(buttons[0]!.textContent).toBe(TR_TEXT.failure.retryPart);
      fireEvent.click(buttons[0]!);
      expect(onRetry).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId('part-failure-guide').textContent).toBe(
        TR_TEXT.failure.retryGuide,
      );
    },
  );

  it('서버 오류 글과 일부 쪽 글', () => {
    const { rerender } = render(<PartFailureCard kind="server_error" />);
    expect(screen.getByTestId('part-failure').textContent).toContain(
      TR_TEXT.failure.serverError,
    );
    rerender(<PartFailureCard kind="partial" />);
    expect(screen.getByTestId('part-failure').textContent).toContain(
      TR_TEXT.failure.partial,
    );
  });

  // [밴드 TRW1b] 보내는 동안(retrying) 단추 꺼짐 — 누름이 onRetry 를 부르지 않음.
  it('retrying → 다시 단추 꺼짐(누름 0)', () => {
    const onRetry = vi.fn();
    render(<PartFailureCard kind="server_error" retrying onRetry={onRetry} />);
    const button = screen.getByRole('button', {
      name: TR_TEXT.failure.retryPart,
    });
    expect(button.hasAttribute('disabled')).toBe(true);
    fireEvent.click(button);
    expect(onRetry).not.toHaveBeenCalled();
  });

  it('single → [다시 실행](파트 하나)', () => {
    const onRetry = vi.fn();
    render(<PartFailureCard kind="server_error" single onRetry={onRetry} />);
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      TR_TEXT.failure.retrySingle,
    ]);
    fireEvent.click(screen.getByRole('button'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it.each(REJECTION_KEYS)(
    'rejected(%s): onRetry 가 있어도 다시 단추 0, 파일 줄 · 까닭 · 안내',
    (reason) => {
      const onRetry = vi.fn();
      render(
        <PartFailureCard
          kind="rejected"
          reason={reason}
          fileLine={FILE_LINE}
          onRetry={onRetry}
        />,
      );
      expect(screen.queryAllByRole('button')).toHaveLength(0);
      const card = screen.getByTestId('part-failure');
      const { reason: text, guide } = rejectionText(reason);
      expect(card.textContent).toContain(FILE_LINE);
      expect(card.textContent).toContain(text);
      expect(screen.getByTestId('part-failure-guide').textContent).toBe(guide);
      expect(card.textContent).not.toMatch(/비용/);
    },
  );

  it('rejected 에 [목록으로]만(onBack)', () => {
    const onBack = vi.fn();
    render(
      <PartFailureCard
        kind="rejected"
        reason="too_large"
        onRetry={vi.fn()}
        onBack={onBack}
      />,
    );
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      TR_TEXT.failure.back,
    ]);
    fireEvent.click(screen.getByRole('button'));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('콜백이 없으면 단추를 그리지 않는다 · 「실패한 쪽만 다시」 없음', () => {
    render(<PartFailureCard kind="partial" />);
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.queryByTestId('part-failure-guide')).toBeNull();
    expect(screen.getByTestId('part-failure').textContent).not.toMatch(
      /실패한 쪽만/,
    );
  });

  // [밴드 TRW6 W8·W6] PDF 파트 갈래 — 서버 문장 0, 읽지 못함·텍스트 없음은 다시 단추 0.
  describe('PDF 파트', () => {
    it('unreadable(unsupported_input 거절) → 읽지 못함 한 줄, NOT_STARTED 까닭·안내 0, 단추 0', () => {
      render(
        <PartFailureCard
          kind="rejected"
          reason="bad_file"
          pdf="unreadable"
          fileLine={FILE_LINE}
        />,
      );
      const card = screen.getByTestId('part-failure');
      expect(card.textContent).toContain(TR_TEXT.failure.pdf.unreadable);
      expect(card.textContent).not.toContain(rejectionText('bad_file').reason);
      expect(screen.queryByTestId('part-failure-guide')).toBeNull();
      expect(screen.queryAllByRole('button')).toHaveLength(0);
    });

    it('no_text(no_text_layer 실패) → 텍스트 없음 한 줄, onRetry 를 받아도 다시 단추·안내 0', () => {
      const onRetry = vi.fn();
      render(
        <PartFailureCard kind="server_error" pdf="no_text" onRetry={onRetry} />,
      );
      const card = screen.getByTestId('part-failure');
      expect(card.textContent).toContain(TR_TEXT.failure.pdf.noText);
      expect(card.textContent).not.toContain(TR_TEXT.failure.serverError);
      expect(screen.queryAllByRole('button')).toHaveLength(0);
      expect(screen.queryByTestId('part-failure-guide')).toBeNull();
      expect(screen.queryByTestId('part-failure-pdf-note')).toBeNull();
    });

    it('run(그 밖 PDF 파트) → [이 파트만 다시] 그대로 + 회색 한 줄', () => {
      render(
        <PartFailureCard kind="server_error" pdf="run" onRetry={vi.fn()} />,
      );
      expect(
        screen.getByRole('button', { name: TR_TEXT.failure.retryPart }),
      ).toBeTruthy();
      expect(screen.getByTestId('part-failure-pdf-note').textContent).toBe(
        TR_TEXT.failure.pdf.retryNote,
      );
    });

    it('too_large 는 pdf 갈래 없이 기존 TOO_LARGE 글(429 정본)', () => {
      render(<PartFailureCard kind="rejected" reason="too_large" />);
      expect(screen.getByTestId('part-failure').textContent).toContain(
        rejectionText('too_large').reason,
      );
    });

    it('워드 파트(pdf 없음) → 회색 줄 0', () => {
      render(<PartFailureCard kind="server_error" onRetry={vi.fn()} />);
      expect(screen.queryByTestId('part-failure-pdf-note')).toBeNull();
    });
  });
});
