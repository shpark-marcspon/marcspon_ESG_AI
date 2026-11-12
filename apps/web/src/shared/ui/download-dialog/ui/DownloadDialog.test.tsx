// @vitest-environment jsdom
// 공용 받기 모달(밴드 TRW14 §2): 켜짐·꺼짐 · (?) 툴팁 · 받기 한 번 · 실패는 그 줄만 · 닫으면 초점은 연 단추 · 이 폴더 원문에 한국어 0.
import { useState } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DownloadDialog } from './DownloadDialog.tsx';
import type {
  DownloadDialogFile,
  DownloadDialogProps,
} from './DownloadDialog.tsx';

afterEach(cleanup);

const blob = new Blob(['fake']);
const ok = (fileName: string) => vi.fn(async () => ({ blob, fileName }));

function filesOf(
  over: Partial<Record<string, Partial<DownloadDialogFile>>> = {},
) {
  const base: DownloadDialogFile[] = [
    {
      key: 'alpha',
      name: 'Fake file alpha',
      description: 'Alpha description line',
      fileLabel: 'Alpha.docx',
      icon: <svg data-testid="icon-alpha" />,
      download: ok('alpha-fake.docx'),
    },
    {
      key: 'beta',
      name: 'Fake file beta',
      description: 'Beta description line',
      fileLabel: 'Beta.docx',
      icon: <svg />,
      download: ok('beta-fake.docx'),
    },
    {
      key: 'gamma',
      name: 'Fake file gamma',
      description: 'Gamma description line',
      fileLabel: 'Gamma.docx',
      icon: <svg />,
      download: ok('gamma-fake.docx'),
    },
  ];
  return base.map((f) => ({ ...f, ...over[f.key] }));
}

function show(props: Partial<DownloadDialogProps> = {}) {
  const save = vi.fn();
  const onClose = vi.fn();
  const files = props.files ?? filesOf();
  render(
    <DownloadDialog
      title="Fake downloads"
      footnote="Fake footnote"
      closeLabel="Close"
      helpLabel="Why"
      failedText="Fake failure text"
      busyLabel="Fake busy"
      files={files}
      onClose={onClose}
      returnFocus={() => null}
      save={save}
      {...props}
    />,
  );
  return { save, onClose, files };
}

const fileButton = (key: string) =>
  screen.getByTestId(`download-dialog-file-${key}`);

describe('DownloadDialog', () => {
  it('머리 · 묶음 셋(이름 · 설명 늘 보임 · 파일 단추) · 각주 · [닫기] 하나', () => {
    show();
    expect(screen.getByRole('dialog')).toHaveProperty(
      'textContent',
      expect.stringContaining('Fake downloads'),
    );
    expect(
      [...document.querySelectorAll('[data-file]')].map((li) =>
        li.getAttribute('data-file'),
      ),
    ).toEqual(['alpha', 'beta', 'gamma']);
    expect(screen.getByText('Beta description line')).toBeTruthy();
    expect(fileButton('alpha').textContent).toContain('Alpha.docx');
    expect(screen.getByTestId('icon-alpha')).toBeTruthy();
    expect(screen.getByText('Fake footnote')).toBeTruthy();
    expect(
      screen
        .getAllByRole('button', { name: 'Close' })
        .map((b) => b.textContent),
    ).toEqual(['Close']);
  });

  it('켜짐·꺼짐: 꺼진 단추는 aria-disabled=true 이고 누름이 download 를 부르지 않는다', async () => {
    const files = filesOf({
      beta: { disabledReason: 'Only after fake review' },
    });
    const { save } = show({ files });
    expect(
      ['alpha', 'beta', 'gamma'].map((k) =>
        fileButton(k).getAttribute('aria-disabled'),
      ),
    ).toEqual([null, 'true', null]);
    fireEvent.click(fileButton('beta'));
    await act(async () => {});
    expect(files[1]!.download).not.toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
    fireEvent.click(fileButton('gamma'));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(files[2]!.download).toHaveBeenCalledTimes(1);
  });

  it('(?) 툴팁: 초점·호버 때 그 이유가 보이고, 꺼진 파일 단추에는 툴팁이 없다', async () => {
    show({
      files: filesOf({ beta: { disabledReason: 'Only after fake review' } }),
    });
    // (?) 는 꺼진 줄에만
    expect(screen.queryByTestId('download-dialog-help-alpha')).toBeNull();
    const help = screen.getByTestId('download-dialog-help-beta');
    expect(help.tagName).toBe('BUTTON');
    expect(help.getAttribute('aria-label')).toBe('Why: Only after fake review');
    expect(screen.queryByRole('tooltip')).toBeNull();
    // 꺼진 파일 단추에 호버·초점 → 툴팁 없음
    fireEvent.pointerMove(fileButton('beta'));
    fireEvent.focus(fileButton('beta'));
    await act(async () => {});
    expect(screen.queryByRole('tooltip')).toBeNull();
    expect(fileButton('beta').getAttribute('data-state')).toBeNull();
    // (?) 호버 → 이유
    fireEvent.pointerMove(help);
    expect((await screen.findByRole('tooltip')).textContent).toBe(
      'Only after fake review',
    );
    fireEvent.pointerLeave(help);
    await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull());
    // (?) 초점 → 이유
    fireEvent.focus(help);
    expect((await screen.findByRole('tooltip')).textContent).toBe(
      'Only after fake review',
    );
  });

  it('받기 한 번: 받는 동안 두 번 눌러도 download 1회 · save 1회(이름 그대로) · 도는 표시', async () => {
    let finish!: (v: { blob: Blob; fileName: string }) => void;
    const download = vi.fn(
      () =>
        new Promise<{ blob: Blob; fileName: string }>((r) => {
          finish = r;
        }),
    );
    const { save } = show({ files: filesOf({ alpha: { download } }) });
    fireEvent.click(fileButton('alpha'));
    fireEvent.click(fileButton('alpha'));
    expect(download).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('status', { name: 'Fake busy' })).toBeTruthy();
    expect(fileButton('alpha').getAttribute('aria-busy')).toBe('true');
    await act(async () => finish({ blob, fileName: 'alpha-fake.docx' }));
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith(blob, 'alpha-fake.docx');
    expect(screen.queryByRole('status', { name: 'Fake busy' })).toBeNull();
  });

  it('실패: 그 줄 아래 role=alert 에 failedText, 다른 줄에는 없다 · 다시 누르면 지운다', async () => {
    const download = vi
      .fn<() => Promise<{ blob: Blob; fileName: string }>>()
      .mockRejectedValueOnce(new Error('fake'))
      .mockResolvedValueOnce({ blob, fileName: 'beta-fake.docx' });
    const { save } = show({ files: filesOf({ beta: { download } }) });
    fireEvent.click(fileButton('beta'));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Fake failure text');
    expect(alert.querySelectorAll('svg[aria-hidden="true"]')).toHaveLength(1);
    // alert 는 내용에서 이름을 얻지 않는다(ARIA) — 읽히는 것은 내용이다: 이름 붙임 없음 · aria-hidden 을 뺀 글 = failedText.
    expect(alert.hasAttribute('aria-label')).toBe(false);
    expect(alert.hasAttribute('aria-labelledby')).toBe(false);
    const spoken = alert.cloneNode(true) as HTMLElement;
    spoken.querySelectorAll('[aria-hidden="true"]').forEach((n) => n.remove());
    expect(spoken.textContent).toBe('Fake failure text');
    expect(alert.closest('[data-file]')?.getAttribute('data-file')).toBe(
      'beta',
    );
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    expect(save).not.toHaveBeenCalled();
    fireEvent.click(fileButton('beta'));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('초점: [닫기] 뒤 연 단추가 document.activeElement 다', async () => {
    function Host() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" id="opener" onClick={() => setOpen(true)}>
            Open
          </button>
          {open && (
            <DownloadDialog
              title="Fake downloads"
              closeLabel="Close"
              helpLabel="Why"
              failedText="Fake failure text"
              busyLabel="Fake busy"
              files={filesOf()}
              onClose={() => setOpen(false)}
              returnFocus={() => document.getElementById('opener')}
              save={() => {}}
            />
          )}
        </>
      );
    }
    render(<Host />);
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    expect(screen.getByRole('dialog')).toBeTruthy();
    // 초점을 모달 밖 다른 요소로 옮겨 두어도(돌림이 Radix 기본이 아니라 returnFocus 인지 보려고) 닫으면 연 단추로
    act(() => document.body.focus());
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(document.activeElement?.id).toBe('opener');
  });

  // [TRW14 §1-1] 글은 전부 props — 이 폴더 원문(주석을 뺀 코드)에 한국어 글자 0.
  it('이 폴더 원문(주석 뺀 코드)에 한국어 글자가 없다', () => {
    const root = join(dirname(fileURLToPath(import.meta.url)), '..');
    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((name) => {
        const path = join(dir, name);
        return (
          statSync(path).isDirectory() ? walk(path)
          : /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path]
          : []
        );
      });
    const sources = walk(root);
    expect(sources.length).toBeGreaterThanOrEqual(2);
    for (const path of sources) {
      const code = readFileSync(path, 'utf8')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
      expect({ path, hangul: code.match(/[ㄱ-ㆎ가-힣]+/g) }).toEqual({
        path,
        hangul: null,
      });
    }
  });
});
