// @vitest-environment jsdom
// 새 점검 폼 훅과 실행 상태 훅(밴드 FW1b ①). 목 저장소 대신 시험 안의 가짜 저장소를 쓴다(headless 는 mock 을 모른다).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import type { RunSnapshot } from '../../../entities/greenwash/api/index.ts';
import { liveRunStore } from '../../../entities/greenwash/api/mock/testing.ts';
import type { RunProgress } from '../../../entities/greenwash/model/index.ts';
import { useNewCheckForm } from './useNewCheckForm.ts';
import type { UploadItem } from './useNewCheckForm.ts';

afterEach(cleanup);

const table: Record<string, { pageCount: number; hasText: boolean }> = {
  'a-60.pdf': { pageCount: 60, hasText: true },
  'scan-24.pdf': { pageCount: 24, hasText: false },
  'big-320.pdf': { pageCount: 320, hasText: true },
};

/** 구독하면 현재값(0쪽 진행)을 먼저 보내는 가짜 저장소. 파일 표의 이름만 올릴 수 있다. */
const liveStore = () =>
  liveRunStore((runId) => snapshot(runId, 0), {
    createDocument: vi.fn(async (file: File) => {
      const known = table[file.name];
      if (!known) throw new Error('모름');
      return { documentId: `doc-${file.name}`, ...known };
    }),
    createRun: vi.fn(async () => ({ runId: 'run-7' })),
    getRun: vi.fn(async (runId: string) => snapshot(runId, 0)),
    rerun: vi.fn(async () => ({ runId: 'run-8' })),
    listDocuments: vi.fn(async () => [
      { documentId: 'old-1', fileName: '앞.pdf', uploadedAt: '2026-01-01' },
    ]),
    listDefaultTerms: vi.fn(async () => ['친환경', 'ESG']),
    getDocument: vi.fn(async (documentId: string) => ({
      documentId,
      fileName: '앞.pdf',
      pageCount: 139,
    })),
  });

const progress = (done: number): RunProgress => ({
  state: 'running',
  stage: 'judge',
  judge: { done, total: 44 },
});

const snapshot = (runId: string, done: number): RunSnapshot => ({
  runId,
  documentId: 'd',
  startedAt: '2026-10-15T14:20:00+09:00',
  pageCount: 139,
  checkedPages: 44,
  progress: progress(done),
  rerunOf: null,
  errorCode: null,
  finishedAt: null,
});

const item = (name: string, id = name): UploadItem => ({
  id,
  name,
  date: '2026-10-15',
  file: new File([new Uint8Array([1])], name),
});

const fixedNow = () => new Date(2026, 9, 15, 9, 0);

async function setup(fileName?: string) {
  const fake = liveStore();
  const hook = renderHook(() =>
    useNewCheckForm({ store: fake.store, now: fixedNow }),
  );
  if (fileName) {
    act(() => hook.result.current.onChangeItems([item(fileName)]));
    await waitFor(() => expect(hook.result.current.uploading).toBe(false));
  }
  return { ...fake, hook };
}

describe('useNewCheckForm: 파일', () => {
  it('새 항목은 uploading 으로 두고 createDocument 를 부르고, 끝나면 문서와 쪽 수가 생긴다', async () => {
    const { store, hook } = await setup();
    act(() => hook.result.current.onChangeItems([item('a-60.pdf')]));
    expect(hook.result.current.items[0]!.status).toBe('uploading');
    expect(hook.result.current.uploading).toBe(true);
    await waitFor(() => expect(hook.result.current.document).not.toBeNull());
    expect(store.createDocument).toHaveBeenCalledOnce();
    expect(hook.result.current.items[0]!.status).toBeUndefined();
    expect(hook.result.current.document).toMatchObject({
      pageCount: 60,
      hasText: true,
      fileName: 'a-60.pdf',
    });
  });

  it('거절되면 항목이 failed 가 되고 문서는 없다', async () => {
    const { hook } = await setup();
    act(() => hook.result.current.onChangeItems([item('모름.pdf')]));
    await waitFor(() =>
      expect(hook.result.current.items[0]!.status).toBe('failed'),
    );
    expect(hook.result.current.document).toBeNull();
  });

  it('올리는 중에 지운 항목의 거절이 늦게 와도, 그 사이 같은 id 로 다시 넣은 항목을 실패로 바꾸지 않는다(검증 권고 2)', async () => {
    const { store, hook } = await setup();
    const rejects: ((error: Error) => void)[] = [];
    vi.mocked(store.createDocument).mockImplementationOnce(
      () => new Promise((_, no) => rejects.push(no)),
    );
    act(() => hook.result.current.onChangeItems([item('모름.pdf', 'x')]));
    act(() => hook.result.current.onChangeItems([]));
    // 같은 id 로 다시 넣는다(이번 것은 바로 성공)
    act(() => hook.result.current.onChangeItems([item('a-60.pdf', 'x')]));
    await waitFor(() => expect(hook.result.current.document).not.toBeNull());
    await act(async () => rejects[0]!(new Error('모름')));
    expect(hook.result.current.items[0]!.status).toBeUndefined();
  });

  it('지우면(목록에서 빠지면) 문서도 놓는다', async () => {
    const { hook } = await setup('a-60.pdf');
    expect(hook.result.current.document).not.toBeNull();
    act(() => hook.result.current.onChangeItems([]));
    expect(hook.result.current.document).toBeNull();
  });

  it('글자 없는 PDF 는 성공이지만 시작 버튼을 끈다', async () => {
    const { hook } = await setup('scan-24.pdf');
    expect(hook.result.current.document?.hasText).toBe(false);
    expect(hook.result.current.canStart).toBe(false);
  });
});

describe('useNewCheckForm: 쪽', () => {
  it('글자 칸: 오류가 없을 때만 쪽 집합을 바꾸고, 글자는 그대로 둔다', async () => {
    const { hook } = await setup('a-60.pdf');
    act(() => hook.result.current.setPartText('climate', '25~37'));
    expect(hook.result.current.fields.climate.pages).toHaveLength(13);
    act(() => hook.result.current.setPartText('climate', '25~37, 150'));
    expect(hook.result.current.fields.climate).toMatchObject({
      text: '25~37, 150',
      error: { code: 'over_page_count', page: 150, pageCount: 60 },
    });
    expect(hook.result.current.fields.climate.pages).toHaveLength(13);
    act(() => hook.result.current.setPartText('climate', '25~37, 50'));
    expect(hook.result.current.fields.climate.error).toBeNull();
    expect(hook.result.current.fields.climate.pages).toHaveLength(14);
  });

  it('문서가 정해지면 글자를 쪽 수로 다시 읽는다', async () => {
    const { hook } = await setup();
    act(() => hook.result.current.setPartText('ceo', '70'));
    expect(hook.result.current.fields.ceo.error).toBeNull();
    act(() => hook.result.current.onChangeItems([item('a-60.pdf')]));
    await waitFor(() =>
      expect(hook.result.current.fields.ceo.error?.code).toBe(
        'over_page_count',
      ),
    );
  });

  it('누르기는 고른 파트에서 토글하고 글자를 압축 꼴로 다시 쓴다', async () => {
    const { hook } = await setup('a-60.pdf');
    act(() => hook.result.current.setActivePart('ceo'));
    act(() => hook.result.current.pressPage(5));
    act(() => hook.result.current.pressPage(4));
    expect(hook.result.current.fields.ceo.text).toBe('4~5');
    act(() => hook.result.current.pressPage(5));
    expect(hook.result.current.fields.ceo.text).toBe('4');
    expect(hook.result.current.fields.company.text).toBe('');
  });

  it('끌기는 시작 쪽의 방향으로 칠하고, 겹친 쪽과 합계가 셈된다', async () => {
    const { hook } = await setup('a-60.pdf');
    act(() => hook.result.current.setActivePart('company'));
    act(() => hook.result.current.beginPaint(5));
    act(() => hook.result.current.paintTo(9));
    act(() => hook.result.current.paintTo(14));
    act(() => hook.result.current.endPaint());
    expect(hook.result.current.fields.company.text).toBe('5~14');
    act(() => hook.result.current.setPartText('ceo', '4~5'));
    expect(hook.result.current.checkedPages).toBe(11);
    // 칠한 쪽에서 시작하면 빼기
    act(() => hook.result.current.beginPaint(10));
    act(() => hook.result.current.paintTo(14));
    act(() => hook.result.current.endPaint());
    expect(hook.result.current.fields.company.text).toBe('5~9');
    // 끌기가 끝나면 paintTo 는 아무것도 안 한다
    act(() => hook.result.current.paintTo(20));
    expect(hook.result.current.fields.company.text).toBe('5~9');
  });
});

describe('useNewCheckForm: 설정과 시작', () => {
  it('보고연도 기본은 올해(시계 고정). 수정본 대상이 없어 이전 문서 목록을 읽지 않는다(v115 — 밴드 GW2R ①)', async () => {
    const { store, hook } = await setup();
    expect(hook.result.current.reportYear).toBe(2026);
    expect(hook.result.current.yearOptions[0]).toBe(2027);
    expect(hook.result.current.yearOptions).toContain(2026);
    expect(store.listDocuments).not.toHaveBeenCalled();
  });

  it('「3. 점검 설정」 카드를 지우며 대상 단어 읽기도 걷었다: 기본 단어 목록을 부르지 않고, 단어를 내거나 고치는 칸이 없다(시안 댓글 — sid:MARC-ENT-603)', async () => {
    const { store, hook } = await setup('a-60.pdf');
    expect(hook.result.current).not.toHaveProperty('defaultTerms');
    expect(hook.result.current).not.toHaveProperty('retryDefaultTerms');
    expect(hook.result.current).not.toHaveProperty('addTerm');
    expect(hook.result.current).not.toHaveProperty('extraTerms');
    expect(store.listDefaultTerms).not.toHaveBeenCalled();
  });

  it('누르기 전에는 사유가 없고, 누르면 사유를 내고 실행을 만들지 않는다', async () => {
    const { store, hook } = await setup();
    expect(hook.result.current.problems).toEqual([]);
    let runId: string | null = 'x';
    await act(async () => {
      runId = await hook.result.current.start();
    });
    expect(runId).toBeNull();
    expect(hook.result.current.problems).toEqual([{ code: 'no_file' }]);
    expect(store.createRun).not.toHaveBeenCalled();
  });

  it('300쪽 초과·세 파트 비었음은 시작할 때 사유가 된다', async () => {
    const big = await setup('big-320.pdf');
    await act(async () => {
      await big.hook.result.current.start();
    });
    expect(big.hook.result.current.problems[0]!.code).toBe('too_many_pages');
    const empty = await setup('a-60.pdf');
    await act(async () => {
      await empty.hook.result.current.start();
    });
    expect(empty.hook.result.current.problems).toEqual([{ code: 'no_parts' }]);
    // 고치면 사유가 다시 셈된다
    act(() => empty.hook.result.current.setPartText('ceo', '1'));
    expect(empty.hook.result.current.problems).toEqual([]);
  });

  it('다 맞으면 createRun(documentId, 입력) 을 부르고 runId 를 돌려준다', async () => {
    const { store, hook } = await setup('a-60.pdf');
    act(() => hook.result.current.setPartText('ceo', '4~5'));
    let runId: string | null = null;
    await act(async () => {
      runId = await hook.result.current.start();
    });
    expect(runId).toBe('run-7');
    expect(store.createRun).toHaveBeenCalledWith(
      'doc-a-60.pdf',
      {
        parts: { ceo: [4, 5], company: [], climate: [] },
        extraTerms: [],
        reportYear: 2026,
        previousDocumentId: null,
      },
      expect.stringMatching(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
      ),
    );
  });
});
