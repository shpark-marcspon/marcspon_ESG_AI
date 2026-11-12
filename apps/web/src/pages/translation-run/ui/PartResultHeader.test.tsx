// @vitest-environment jsdom
// 파트 결과 머리(밴드 TRW0b, 발주서 §3-9 → TRW14 ①): [내려받기] 하나 → 받기 모달(파일 셋, 없는 것은 꺼진 줄 + 까닭) ·
// [이 파트만 다시]는 onRetry + 서버 오류·일부 쪽만 · single → [다시 실행] · 완료에는 다시 단추 0.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { PartResultHeader } from './PartResultHeader.tsx';
import type { PartResultHeaderProps } from './PartResultHeader.tsx';

afterEach(cleanup);

const file = async () => ({ blob: new Blob(['x']), fileName: 'f.docx' });
const BASE: PartResultHeaderProps = {
  part: 'story',
  range: { from: 4, to: 41 },
  state: 'done',
  round: 2,
  style: 'B',
  glossaryCount: 164,
  started: '2026-10-19 14:10',
  finished: '14:22',
  files: { bilingual: file, review: file, autofix: file },
};
const words = TR_TEXT.result;
/** [내려받기](part-downloads)를 뺀 단추. */
const retryButtons = () =>
  screen
    .queryAllByRole('button')
    .filter((b) => b.getAttribute('data-testid') !== 'part-downloads');
const row = (key: string) =>
  screen.getByTestId(`part-download-dialog-file-${key}`);

describe('PartResultHeader', () => {
  it('머리: 제목 · 상태 · 회차 · 스타일·용어집·시작·끝남', () => {
    render(<PartResultHeader {...BASE} />);
    const head = screen.getByTestId('part-result').textContent!;
    expect(head).toContain('스토리 4~41페이지(총 38페이지)');
    expect(head).toContain('완료');
    expect(head).toContain('회차 2');
    expect(head).toContain(
      '스타일 B · 고객사 용어집 164개 · 2026-10-19 14:10 시작 · 14:22 끝남',
    );
  });

  // [TRP2 TE13·TE12 → TRW14 ①] 머리에는 [내려받기] 하나. 모달이 Word 셋을 늘 그리고 없는 파일은 끈다(aria-disabled + (?) 까닭).
  //   설명은 셋 다 늘 보인다(옛 카드는 있는 파일만이었다 — TR-04a r2). 파일이 하나도 없어도 [내려받기]는 켠다.
  it('[내려받기] → 모달 줄 셋(차례: 병기 번역본 · 검수 결과 · 자동 수정 병기본), 없는 파일은 aria-disabled + 까닭 · 설명 · 각주', () => {
    const { rerender } = render(<PartResultHeader {...BASE} />);
    const opener = screen.getByTestId('part-downloads');
    expect(opener.textContent).toBe(words.downloadsTitle);
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(opener);
    const dialog = screen.getByRole('dialog');
    expect(dialog.querySelector('h2')?.textContent).toBe(words.downloadsTitle);
    expect(
      [...dialog.querySelectorAll('[data-file]')].map(
        (li) =>
          li.querySelector('button[data-testid^="part-download-dialog-file-"]')!
            .textContent,
      ),
    ).toEqual([words.files.bilingual, words.files.review, words.files.autofix]);
    expect(
      ['bilingual', 'review', 'autofix'].map((k) =>
        row(k).getAttribute('aria-disabled'),
      ),
    ).toEqual([null, null, null]);
    for (const key of ['bilingual', 'review', 'autofix'] as const)
      expect(
        dialog.querySelector(`[data-file="${key}"]`)!.textContent,
      ).toContain(words.fileNotes[key]);
    expect(dialog.textContent).toContain(words.wordNote);
    rerender(
      <PartResultHeader
        {...BASE}
        state="failed_partial"
        files={{ bilingual: file }}
      />,
    );
    expect(
      ['bilingual', 'review', 'autofix'].map((k) =>
        row(k).getAttribute('aria-disabled'),
      ),
    ).toEqual([null, 'true', 'true']);
    expect(
      screen
        .getByTestId('part-download-dialog-help-review')
        .getAttribute('aria-label'),
    ).toBe(`${words.fileMissingLabel}: ${words.fileMissing.review}`);
    expect(
      screen
        .getByTestId('part-download-dialog-help-autofix')
        .getAttribute('aria-label'),
    ).toBe(`${words.fileMissingLabel}: ${words.fileMissing.autofix}`);
    cleanup();
    // 파일 0 이어도 단추는 켜고, 모달에는 셋 다 꺼진 줄
    render(<PartResultHeader {...BASE} files={{}} />);
    const none = screen.getByTestId('part-downloads');
    expect(none.hasAttribute('disabled')).toBe(false);
    fireEvent.click(none);
    expect(
      ['bilingual', 'review', 'autofix'].map((k) =>
        row(k).getAttribute('aria-disabled'),
      ),
    ).toEqual(['true', 'true', 'true']);
    expect(
      screen
        .getByTestId('part-download-dialog-help-bilingual')
        .getAttribute('aria-label'),
    ).toContain(words.fileMissing.bilingual);
  });

  it('받기: 켜진 줄을 누르면 그 Loader 한 번 · 실패면 downloadFailed · [닫기] 뒤 초점은 [내려받기]', async () => {
    const bilingual = vi.fn(async () => {
      throw new Error('fake');
    });
    render(<PartResultHeader {...BASE} files={{ bilingual }} />);
    const opener = screen.getByTestId('part-downloads');
    fireEvent.click(opener);
    fireEvent.click(row('bilingual'));
    fireEvent.click(row('review'));
    expect(bilingual).toHaveBeenCalledTimes(1);
    expect((await screen.findByRole('alert')).textContent).toBe(
      words.downloadFailed,
    );
    fireEvent.click(screen.getByRole('button', { name: words.close }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(document.activeElement).toBe(opener);
  });

  it('일부 쪽 + onRetry → [이 파트만 다시] 한 번, single → [다시 실행]', () => {
    const onRetry = vi.fn();
    const { rerender } = render(
      <PartResultHeader
        {...BASE}
        state="failed_partial"
        files={{}}
        onRetry={onRetry}
      />,
    );
    fireEvent.click(
      screen.getByRole('button', { name: TR_TEXT.failure.retryPart }),
    );
    expect(onRetry).toHaveBeenCalledTimes(1);
    rerender(
      <PartResultHeader
        {...BASE}
        state="failed_partial"
        files={{}}
        onRetry={onRetry}
        single
      />,
    );
    // [내려받기]를 빼면 [다시 실행] 하나.
    expect(retryButtons().map((b) => b.textContent)).toEqual([
      TR_TEXT.failure.retrySingle,
    ]);
  });

  // [밴드 TRW1b] 보내는 동안(retrying) 단추 꺼짐.
  it('일부 쪽 + retrying → [이 파트만 다시] 꺼짐(누름 0)', () => {
    const onRetry = vi.fn();
    render(
      <PartResultHeader
        {...BASE}
        state="failed_partial"
        files={{}}
        onRetry={onRetry}
        retrying
      />,
    );
    const button = screen.getByRole('button', {
      name: TR_TEXT.failure.retryPart,
    });
    expect(button.hasAttribute('disabled')).toBe(true);
    fireEvent.click(button);
    expect(onRetry).not.toHaveBeenCalled();
  });

  it('완료에는 onRetry 가 있어도 다시 단추 0', () => {
    render(<PartResultHeader {...BASE} files={{}} onRetry={vi.fn()} />);
    expect(retryButtons()).toHaveLength(0);
  });

  // 밴드 TRP3 TB2 → TRW14 ①: 머리의 Word 셋(autofix solid-black)은 [내려받기] 하나로 바뀌었다 — outline-grey round sm + 받기 아이콘.
  it('[내려받기] 꼴: border-button-grey · rounded-full · h-7(sm) · 아이콘 · 머리 오른쪽(ml-auto)', () => {
    render(<PartResultHeader {...BASE} />);
    const opener = screen.getByTestId('part-downloads');
    for (const c of ['border-button-grey', 'rounded-full', 'h-7'])
      expect(opener.classList.contains(c), c).toBe(true);
    expect(opener.classList.contains('bg-button-black')).toBe(false);
    expect(opener.querySelector('svg')).toBeTruthy();
    expect(opener.closest('div')!.classList.contains('ml-auto')).toBe(true);
  });
});
