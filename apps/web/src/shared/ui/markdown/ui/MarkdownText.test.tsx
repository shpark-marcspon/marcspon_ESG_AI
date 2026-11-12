// @vitest-environment jsdom
// 마크다운 보기 부품(밴드 MD1). 지어낸 글로 본다: 원 HTML·위험한 링크·그림은 요소가 되지 않고, GFM 은 해당 요소로 그린다.
import { cleanup, render } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { MarkdownText } from './MarkdownText.tsx';

afterEach(cleanup);

function draw(text: string) {
  return render(<MarkdownText>{text}</MarkdownText>).container;
}

function count(root: Element, selector: string) {
  return root.querySelectorAll(selector).length;
}

function expectNewTab(link: Element) {
  expect(link.getAttribute('target')).toBe('_blank');
  const rel = link.getAttribute('rel')!.split(' ');
  expect(rel).toContain('noopener');
  expect(rel).toContain('noreferrer');
}

describe('원 HTML', () => {
  it('H1 블록 script 는 요소가 되지 않고 글자로 보인다', () => {
    const root = draw('<script>alert(1)</script>');
    expect(count(root, 'script')).toBe(0);
    expect(root.textContent).toContain('<script>');
  });

  it('H2 줄 안 img 는 요소가 되지 않고 앞뒤 글은 남는다', () => {
    const root = draw('앞 <img src=x onerror=alert(1)> 뒤');
    expect(count(root, 'img')).toBe(0);
    expect(count(root, '[onerror]')).toBe(0);
    expect(root.textContent).toContain('앞');
    expect(root.textContent).toContain('뒤');
  });

  it('H3 iframe 은 요소가 되지 않는다', () => {
    const root = draw('<iframe src="https://example.com"></iframe>');
    expect(count(root, 'iframe')).toBe(0);
  });
});

describe('링크', () => {
  it.each([
    '[x](javascript:alert(1))',
    '[x](data:text/html,hi)',
    '[x](/rel)',
    '[x](ftp://example.com/a)',
    '[x]()',
    '[x](mailto:a@example.com)',
  ])('L1 %s 는 글자만 남고 주소는 어디에도 없다', (text) => {
    const root = draw(text);
    expect(count(root, 'a')).toBe(0);
    expect(root.textContent).toBe('x');
    expect(count(root, '[href]')).toBe(0);
    for (const word of ['javascript:', 'data:', 'ftp:', 'mailto:', '/rel'])
      expect(root.innerHTML).not.toContain(word);
  });

  it('L2 대문자 스킴도 새 탭 링크다', () => {
    const root = draw('[x](HTTPS://Example.com/a)');
    expect(count(root, 'a')).toBe(1);
    const link = root.querySelector('a')!;
    expect(link.getAttribute('href')).toBe('HTTPS://Example.com/a');
    expectNewTab(link);
  });

  it.each(['보기 https://example.com 끝', '<https://example.com/b>'])(
    'L3 자동 링크 %s',
    (text) => {
      const root = draw(text);
      expect(count(root, 'a')).toBe(1);
      expectNewTab(root.querySelector('a')!);
    },
  );
});

describe('링크 칩과 앞처리', () => {
  function chips(root: Element) {
    return [...root.querySelectorAll('a')].map((link) => [
      link.getAttribute('href'),
      link.getAttribute('aria-label')!.split(' · ')[0],
    ]);
  }

  it('C2 링크는 칩으로 그린다', () => {
    expect(chips(draw('[가상 **기준**서](https://example.org/s)'))).toEqual([
      ['https://example.org/s', '가상 기준서'],
    ]);
  });

  it('P1 주소 끝 한글은 주소에서 떼어 뒤 글로 돌린다', () => {
    const root = draw('보기 https://example.org/a입니다 끝');
    expect(chips(root)).toEqual([['https://example.org/a', 'a']]);
    expect(root.textContent).toContain('입니다 끝');
  });

  it('P2 주소 뒤 「)」 와 한글도 뗀다, 짝이 있는 「)」 는 주소에 둔다', () => {
    const cut = draw('(보기 https://example.org/a)는 끝');
    expect(chips(cut)).toEqual([['https://example.org/a', 'a']]);
    expect(cut.textContent).toContain(')는 끝');
    expect(chips(draw('https://example.org/a(1)는'))).toEqual([
      ['https://example.org/a(1)', 'a(1)'],
    ]);
  });

  it('P3 명시 링크와 꺾쇠 링크의 주소는 손대지 않는다', () => {
    const encoded = 'https://example.org/%EA%B0%80';
    expect(
      draw('[글](https://example.org/가)')
        .querySelector('a')!
        .getAttribute('href'),
    ).toBe(encoded);
    expect(
      draw('<https://example.org/가>').querySelector('a')!.getAttribute('href'),
    ).toBe(encoded);
    expect(
      draw('[https://example.org/가](https://example.org/가)')
        .querySelector('a')!
        .getAttribute('href'),
    ).toBe(encoded);
  });

  it('P4 「출처: 이름 (주소)」 는 이름이 제목인 칩이다', () => {
    const root = draw('출처: 가상 기준서 (https://example.org/s)');
    expect(chips(root)).toEqual([['https://example.org/s', '가상 기준서']]);
    expect(root.textContent!.startsWith('출처: ')).toBe(true);
    expect(root.textContent).not.toContain('(');
    expect(root.textContent).not.toContain(')');
  });

  it('P5 한 줄에 여럿, 목록 안도 같다', () => {
    expect(
      chips(
        draw('- 출처: 가 (https://example.org/a), 나 (https://example.org/b)'),
      ),
    ).toEqual([
      ['https://example.org/a', '가'],
      ['https://example.org/b', '나'],
    ]);
  });

  it('P6 꼴이 안 맞으면 그냥 둔다', () => {
    const root = draw('(https://example.org/s) 와 이름 (https://example.org/t');
    expect(chips(root)).toEqual([
      ['https://example.org/s', 's'],
      ['https://example.org/t', 't'],
    ]);
    expect(root.textContent).toContain('(');
  });

  it('P7 맨 글자 메일 주소는 칩이 아니라 회색 글이다', () => {
    const root = draw('a@example.com 보기');
    expect(count(root, 'a')).toBe(0);
    expect(root.textContent).toContain('a@example.com');
  });
});

describe('GFM', () => {
  it('G1 표는 그 표만 가로 스크롤하는 감싸개 안에 있다', () => {
    const root = draw('| 가 | 나 |\n| - | - |\n| 1 | 2 |\n| 3 | 4 |');
    expect(count(root, 'table')).toBe(1);
    expect(count(root, 'th')).toBe(2);
    expect(count(root, 'td')).toBe(4);
    const wrapper = root.querySelector('table')!.parentElement!;
    expect(wrapper.hasAttribute('data-markdown-table')).toBe(true);
    expect(wrapper.classList.contains('overflow-x-auto')).toBe(true);
  });

  it('G2 목록', () => {
    expect(count(draw('- 하나\n- 둘'), 'ul>li')).toBe(2);
    expect(count(draw('1. 하나\n2. 둘'), 'ol>li')).toBe(2);
  });

  it('G3 코드 펜스', () => {
    const root = draw('```ts\nconst a = 1;\nconst b = 2;\n```');
    expect(count(root, 'pre>code')).toBe(1);
    expect(root.querySelector('pre>code')!.textContent).toBe(
      'const a = 1;\nconst b = 2;\n',
    );
  });

  it('G4 굵게·지움·줄 코드', () => {
    const root = draw('**굵게** ~~지움~~ `줄코드`');
    expect(count(root, 'strong')).toBe(1);
    expect(count(root, 'del')).toBe(1);
    expect(count(root, 'code')).toBe(1);
    expect(count(root, 'pre')).toBe(0);
  });
});

describe('그림·제목·겉', () => {
  it('I1 그림은 부르지 않고 대체 글자만 남는다', () => {
    const root = draw('![대체 글](https://example.com/a.png)');
    expect(count(root, 'img')).toBe(0);
    expect(count(root, 'a')).toBe(0);
    expect(root.textContent).toBe('대체 글');
    expect(root.innerHTML).not.toContain('example.com');
  });

  it('I2 대체 글자가 없는 그림은 아무것도 남기지 않는다', () => {
    const root = draw('![](https://example.com/a.png)');
    expect(count(root, 'img')).toBe(0);
    expect(root.textContent).toBe('');
  });

  it('T1 제목은 화면 제목 아래 급으로 낮춘다', () => {
    const root = draw('# 큰\n\n### 작은');
    expect(count(root, 'h1,h2,h3,h4')).toBe(0);
    expect(count(root, 'h5')).toBe(1);
    expect(count(root, 'h6')).toBe(1);
  });

  it('F1 각주 머리는 낮춰도 sr-only 를 지킨다', () => {
    const root = draw('글[^1]\n\n[^1]: 풀이');
    const heads = root.querySelectorAll('h5');
    expect(heads.length).toBe(1);
    expect(heads[0]!.textContent).toBe('Footnotes');
    expect(heads[0]!.classList.contains('sr-only')).toBe(true);
    expect(count(root, 'a')).toBe(0);
  });

  it('M1 표는 키보드로 닿는 이름 있는 스크롤 칸이다', () => {
    const wrapper = draw('| 가 |\n| - |\n| 1 |').querySelector(
      '[data-markdown-table]',
    )!;
    expect(wrapper.getAttribute('tabindex')).toBe('0');
    expect(wrapper.getAttribute('role')).toBe('region');
    expect(wrapper.getAttribute('aria-label')).toBe('표');
  });

  it.each([
    ['1200.0', true],
    ['1,300', true],
    ['-5.5%', true],
    ['+10', true],
    ['12 tCO2eq', false],
    ['Scope 1', false],
    ['2024년', false],
  ])('M2 숫자 칸 %s → 오른쪽 %s, 머리는 왼쪽', (value, right) => {
    const root = draw(`| 가 |\n| - |\n| ${value} |`);
    expect(root.querySelector('td')!.classList.contains('text-right')).toBe(
      right,
    );
    expect(root.querySelector('th')!.classList.contains('text-left')).toBe(
      true,
    );
  });

  it('C1 겉 div 에 className·data-testid·표지', () => {
    const { container } = render(
      <MarkdownText className="a-b" data-testid="md">
        글
      </MarkdownText>,
    );
    const outer = container.firstElementChild!;
    expect(outer.classList.contains('a-b')).toBe(true);
    expect(outer.getAttribute('data-testid')).toBe('md');
    expect(outer.hasAttribute('data-markdown')).toBe(true);
  });
});
