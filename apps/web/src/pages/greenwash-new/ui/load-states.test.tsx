// @vitest-environment jsdom
// GW-02 「3. 점검 설정」 카드(근거 검색 범위·대상 단어)는 지웠다(시안 댓글 1차 반영 — sid:MARC-ENT-603). 카드는 보이기만 했고 실행에 싣는 값이
// 없었다(extraTerms 늘 []). 옛 시험(밴드 GW2R ① 대상 단어 읽기 상태·[더 보기]·[다시 시도] 초점)은 카드와 함께 걷고, 「카드 없음 + 읽기 호출 0」을 단언한다.
// 옛 시험(밴드 LE1 ② 이전 문서 목록 실패 — 수정본 대상 칸)은 수정본 칸을 빼며 지웠다.
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { fakeStore } from '../../../entities/greenwash/api/mock/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { NewCheckScreen } from './NewCheckScreen.tsx';

const words = GW_TEXT.newCheck;
const neverOpen: OpenPdf = () => new Promise(() => {});

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

describe('GW-02 「3. 점검 설정」 카드 없음(sid:MARC-ENT-603)', () => {
  it('카드·대상 단어 칸·근거 범위 줄이 없고, 기본 단어 목록·이전 문서 목록을 부르지 않는다. [점검 시작]은 그대로', () => {
    const listDefaultTerms = vi.fn(async () => ['가람', '나래']);
    const store = fakeStore({ listDefaultTerms });
    render(
      <NewCheckScreen
        store={store}
        openPdf={neverOpen}
        onCancel={() => {}}
        onStarted={() => {}}
      />,
    );
    expect(document.querySelector('[data-card="settings"]')).toBeNull();
    expect(screen.queryByTestId('default-terms')).toBeNull();
    expect(screen.queryByText('3. 점검 설정')).toBeNull();
    expect(screen.queryByText('근거 검색 범위')).toBeNull();
    expect(screen.queryByText('대상 단어')).toBeNull();
    expect('settings' in words).toBe(false);
    expect(listDefaultTerms).not.toHaveBeenCalled();
    expect(store.listDocuments).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: words.start })).toBeTruthy();
    // 남은 카드는 둘(1. 문서 올리기 · 2. 파트별 페이지 범위) — 번호 3 은 없다
    expect(screen.getByText(words.upload.heading)).toBeTruthy();
    expect(screen.getByText(words.parts.heading)).toBeTruthy();
    expect(screen.queryByText(/^3\. /)).toBeNull();
  });
});
