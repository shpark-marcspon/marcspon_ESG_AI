// @vitest-environment jsdom
// (밴드 FS1 ③: screen-fixes.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 밴드 FW2 ⓪: FW1b 디자인 대조의 고칠 것과 sid:MARC-ISSUE-99 화면 고침. 글자는 문구 표(GW_TEXT) 값으로 단언한다.
// 실제 크기·색·스크롤은 e2e/greenwash.spec.ts 가 잰다(jsdom 에는 CSS 가 없다).
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

import type { RunSnapshot } from '../../../entities/greenwash/api/index.ts';
import { snapshotStore } from '../../../entities/greenwash/api/mock/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type { RunProgress } from '../../../entities/greenwash/model/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { NewCheckScreen } from './NewCheckScreen.tsx';
import { OVERLAP_LOOK } from './partLook.ts';

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

/** PDF 를 열지 않는 openPdf(썸네일은 이 시험에서 그리지 않는다). */

const words = GW_TEXT.newCheck;

const run = (progress: RunProgress): RunSnapshot => ({
  runId: 'run-1',
  documentId: 'doc-1',
  startedAt: '2026-10-16T09:00:00+09:00',
  pageCount: 139,
  checkedPages: 44,
  progress,
  rerunOf: null,
  errorCode: null,
  finishedAt: null,
});

/** 실행 하나만 아는 가짜 저장소(구독은 조금 뒤에 그 실행을, 없으면 onMissing). */
const runStore = (snapshot?: RunSnapshot) =>
  snapshotStore(snapshot, {
    createDocument: vi.fn(async () => ({
      documentId: 'doc-1',
      pageCount: 60,
      hasText: true,
    })),
    createRun: vi.fn(async () => ({ runId: 'run-9' })),
    rerun: vi.fn(async () => ({ runId: 'run-2' })),
  });

const neverOpen: OpenPdf = () => new Promise(() => {});

describe('GW-02 새 점검', () => {
  it('파트 고르기: radiogroup 의 radio 셋, 고른 것만 Tab 으로 닿고 방향키로 고르며 초점이 따라간다. 필수 점·aria-required 없음', () => {
    render(
      <NewCheckScreen
        store={runStore()}
        openPdf={neverOpen}
        onCancel={() => {}}
        onStarted={() => {}}
      />,
    );
    const group = screen.getByRole('radiogroup', {
      name: words.parts.groupLabel,
    });
    const radios = within(group).getAllByRole('radio');
    expect(radios).toHaveLength(3);
    const checked = () =>
      radios.map((radio) => radio.getAttribute('aria-checked'));
    expect(checked()).toEqual(['true', 'false', 'false']);
    expect(radios.map((radio) => radio.tabIndex)).toEqual([0, -1, -1]);
    radios[0]!.focus();
    fireEvent.keyDown(radios[0]!, { key: 'ArrowRight' });
    expect(checked()).toEqual(['false', 'true', 'false']);
    expect(document.activeElement).toBe(radios[1]);
    fireEvent.keyDown(radios[1]!, { key: 'End' });
    expect(checked()).toEqual(['false', 'false', 'true']);
    fireEvent.keyDown(radios[2]!, { key: 'ArrowDown' });
    expect(checked()).toEqual(['true', 'false', 'false']);
    fireEvent.keyDown(radios[0]!, { key: 'ArrowLeft' });
    expect(checked()).toEqual(['false', 'false', 'true']);
    expect(radios[2]!.className.split(/\s+/)).toContain('font-bold');
    // 알약은 md(36)
    expect(radios[0]!.className.split(/\s+/)).toContain('h-9');
    // 필수 점·aria-required 없음, 범례는 묶음과 같은 이름을 달지 않는다
    for (const key of ['ceo', 'company', 'climate'] as const) {
      const input = screen.getByLabelText(words.parts.names[key], {
        selector: 'input',
      });
      expect(input.hasAttribute('aria-required')).toBe(false);
      expect(input.id).not.toMatch(/^gw-part-/);
    }
    expect(
      screen.queryAllByRole('list', { name: words.parts.groupLabel }),
    ).toHaveLength(0);
  });

  it('쪽 끝 버튼은 md, [점검 시작] 을 누르면 사유는 칸 아래에 두고 첫 사유의 칸으로 초점(파일 없음 → 드롭존)', async () => {
    render(
      <NewCheckScreen
        store={runStore()}
        openPdf={neverOpen}
        onCancel={() => {}}
        onStarted={() => {}}
      />,
    );
    const start = screen.getByRole('button', { name: words.start });
    const cancel = screen.getByRole('button', { name: words.cancel });
    for (const button of [start, cancel])
      expect(button.className.split(/\s+/)).toContain('h-9');
    await act(async () => {
      fireEvent.click(start);
    });
    const error = screen.getByTestId('start-problems');
    expect(error.textContent).toBe(words.problems.no_file);
    // 드롭존 바로 아래(같은 올리기 칸 안), 버튼 위 모은 줄은 없다
    const zone = screen.getByRole('button', {
      name: new RegExp(words.upload.guide),
    });
    expect(
      zone.compareDocumentPosition(error) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // 초점 대상(드롭존)은 FileDropzone 안이라 이 글은 role="alert" 로 읽힌다(감독 R2)
    expect(error.getAttribute('role')).toBe('alert');
    await waitFor(() => expect(document.activeElement).toBe(zone));
  });

  it('파일이 있고 세 파트가 비면 파트 칸 묶음 아래 오류, 초점은 첫 파트 칸', async () => {
    render(
      <NewCheckScreen
        store={runStore()}
        openPdf={neverOpen}
        onCancel={() => {}}
        onStarted={() => {}}
      />,
    );
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await act(async () => {
      fireEvent.change(input, {
        target: {
          files: [
            new File([new Uint8Array([1])], 'a.pdf', {
              type: 'application/pdf',
            }),
          ],
        },
      });
    });
    await screen.findByTestId('file-meta');
    // 파일 줄 한 줄에 「60쪽 · 크기」(물음 6)
    const meta = screen.getByTestId('file-meta');
    expect(meta.textContent).toBe(
      words.upload.fileMeta(
        words.upload.pageMeta(60),
        words.upload.fileSize(1),
      ),
    );
    expect(meta.closest('li')?.textContent).toContain('a.pdf');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.start }));
    });
    expect(screen.getByTestId('no-parts').textContent).toBe(
      words.problems.no_parts,
    );
    const ceo = screen.getByLabelText(words.parts.names.ceo, {
      selector: 'input',
    });
    await waitFor(() => expect(document.activeElement).toBe(ceo));
    // 파트 없음 오류는 초점이 간 CEO 칸의 설명으로 이어진다(감독 R2)
    expect(ceo.getAttribute('aria-describedby')?.split(' ')).toContain(
      screen.getByTestId('no-parts').id,
    );
  });
});

describe('겹친 쪽 꼴(디자인 대조 물음 5, 밴드 PL1 ①)', () => {
  it('짝과 상관없이 중립 꼴: 틀 2px border-primary + 흰 바탕, 바깥선·주황·파랑 없음', () => {
    for (const part of [OVERLAP_LOOK.frame, OVERLAP_LOOK.swatch]) {
      const classes = part.split(/\s+/);
      expect(classes).toEqual(
        expect.arrayContaining([
          'border-2',
          'border-border-primary',
          'bg-background-primary',
        ]),
      );
      expect(classes.some((name) => name.startsWith('outline'))).toBe(false);
      expect(part).not.toMatch(/orange|blue/);
    }
  });
});

describe('GW-02a 글자 없는 PDF(v115 GW-02a_r2, 밴드 GW2R ①)', () => {
  it('파일 줄 「24쪽 · 크기 · 텍스트 없음」, 빨강 안내 새 글, 그 아래 「확인하는 법」 회색 줄, [점검 시작] 꺼짐, 파트·설정 카드 없음', async () => {
    const store = runStore();
    vi.mocked(store.createDocument).mockResolvedValue({
      documentId: 'doc-scan',
      pageCount: 24,
      hasText: false,
    });
    render(
      <NewCheckScreen
        store={store}
        openPdf={neverOpen}
        onCancel={() => {}}
        onStarted={() => {}}
      />,
    );
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await act(async () => {
      fireEvent.change(input, {
        target: {
          files: [
            new File([new Uint8Array([1])], '지어낸 스캔.pdf', {
              type: 'application/pdf',
            }),
          ],
        },
      });
    });
    const meta = await screen.findByTestId('file-meta');
    expect(meta.textContent).toBe('총 24페이지 · 1KB · 텍스트 없음');
    const notice = screen.getByTestId('no-text');
    expect(notice.textContent).toBe(words.upload.noText);
    expect(words.upload.noText).toBe(
      '이 PDF는 텍스트를 선택할 수 없어요(스캔본·이미지로 만든 PDF). 텍스트를 선택할 수 있는 PDF로 다시 올려 주세요.',
    );
    const how = screen.getByText(words.upload.noTextHow);
    expect(
      notice.compareDocumentPosition(how) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      (screen.getByRole('button', { name: words.start }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(document.querySelector('[data-card="parts"]')).toBeNull();
    expect(document.querySelector('[data-card="settings"]')).toBeNull();
  });
});
