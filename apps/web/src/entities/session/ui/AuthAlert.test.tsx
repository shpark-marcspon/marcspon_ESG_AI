// @vitest-environment jsdom
// 로그인 카드 안내 띠의 아이콘(AV2 모듈 몫 마지막 줄): info·important 는 PageInfoIcon(선 i — 공용 안내 아이콘), 잠김은 자물쇠, 오류는 경고.
import { cleanup, render } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { AuthAlert } from './AuthAlert.tsx';

afterEach(cleanup);

/** PageInfoIcon 이 그리는 svg 의 안쪽(꼴 비교용). */
function pageInfoIconMarkup() {
  const { container, unmount } = render(<PageInfoIcon />);
  const markup = container.querySelector('svg')!.innerHTML;
  unmount();
  return markup;
}

function iconOf(props: Partial<Parameters<typeof AuthAlert>[0]>) {
  const { container } = render(
    <AuthAlert role="status" reason="지어낸 까닭" {...props}>
      지어낸 글
    </AuthAlert>,
  );
  return container.querySelector('svg')!;
}

describe('AuthAlert 아이콘', () => {
  it.each(['info', 'important'] as const)(
    'tone %s 는 PageInfoIcon 꼴(선 i: path 가 stroke 만) · aria-hidden',
    (tone) => {
      const expected = pageInfoIconMarkup();
      const svg = iconOf({ tone });
      expect(svg.getAttribute('aria-hidden')).toBe('true');
      expect(svg.innerHTML).toBe(expected);
      for (const path of svg.querySelectorAll('path')) {
        expect([null, 'none']).toContain(path.getAttribute('fill'));
        expect(path.getAttribute('stroke')).toBeTruthy();
      }
    },
  );

  it('오류·잠김은 PageInfoIcon 이 아니다', () => {
    const expected = pageInfoIconMarkup();
    expect(iconOf({ tone: 'error' }).innerHTML).not.toBe(expected);
    cleanup();
    expect(iconOf({ lock: true }).innerHTML).not.toBe(expected);
  });
});
