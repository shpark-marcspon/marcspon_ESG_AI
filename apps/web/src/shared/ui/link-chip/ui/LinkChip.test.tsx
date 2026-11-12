// @vitest-environment jsdom
// 링크 칩(밴드 MD1, 보드 CM-04 r1). 지어낸 주소로 본다.
import { cleanup, render } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { LinkChip } from './LinkChip.tsx';

afterEach(cleanup);

function chip(url: string, label?: string) {
  const { container } = render(<LinkChip url={url} label={label} />);
  return { root: container, link: container.querySelector('a') };
}

const NEW_TAB = '새 탭에서 열려요';

describe('칩', () => {
  it('제목·도메인·새 탭·툴팁', () => {
    const { link } = chip('https://www.example.org/standard', '가상 기준서');
    expect(link!.getAttribute('href')).toBe('https://www.example.org/standard');
    expect(link!.getAttribute('target')).toBe('_blank');
    expect(link!.getAttribute('rel')).toBe('noopener noreferrer');
    expect(link!.getAttribute('title')).toBe(
      'https://www.example.org/standard',
    );
    expect(link!.getAttribute('aria-label')).toBe(
      `가상 기준서 · example.org · ${NEW_TAB}`,
    );
    expect(link!.textContent).toBe('example.org가상 기준서↗');
  });

  it('제목이 없으면 경로 앞부분, 도메인은 뱃지에만', () => {
    const { link } = chip('https://example.net/reports/2024-a?b=1');
    expect(link!.getAttribute('aria-label')).toBe(
      `reports/2024-a · example.net · ${NEW_TAB}`,
    );
  });

  it.each([
    ['https://example.org/a', 'https://example.org/a'],
    ['https://www.example.org/a', 'example.org/a'],
    ['http://www.example.org/a', 'www.example.org/a'],
    ['https://example.org/%EA%B0%80', 'https://example.org/가'],
  ])('제목이 주소 자체면 제목이 아니다 %s', (url, label) => {
    const { link } = chip(url, label);
    expect(link!.getAttribute('aria-label')).toMatch(/^(a|가) · example\.org/);
  });

  it('경로가 빈 주소는 도메인을 제목으로', () => {
    expect(chip('https://example.org/').link!.getAttribute('aria-label')).toBe(
      `example.org · example.org · ${NEW_TAB}`,
    );
  });

  it('utm_ 꼬리만 뗀 주소가 툴팁이고 href 는 그대로다', () => {
    const url =
      'https://www.example.org/p?utm_source=x&ref=list&UTM_medium=y#c';
    const { link } = chip(url, '글');
    expect(link!.getAttribute('title')).toBe(
      'https://www.example.org/p?ref=list#c',
    );
    expect(link!.getAttribute('href')).toBe(url);
  });

  it.each([
    ['https://e.test/a?utm_source=openai', 'https://e.test/a'],
    ['https://e.test/a?b=1&utm_source=openai', 'https://e.test/a?b=1'],
    ['https://e.test/a?utm_source=openai&b=1#c', 'https://e.test/a?b=1#c'],
    ['https://e.test/a?utm_source=openai#c', 'https://e.test/a#c'],
    ['https://e.test/a?UTM_SOURCE=OpenAI&b=1', 'https://e.test/a?b=1'],
    ['https://e.test/a?utm_source=openai&', 'https://e.test/a'],
    ['https://e.test/a?&utm_source=openai&', 'https://e.test/a'],
    ['https://e.test/a?q=a%20b&utm_source=openai', 'https://e.test/a?q=a%20b'],
    [
      'https://e.test/a?q=a+b&x=%EA%B0%80&utm_source=openai',
      'https://e.test/a?q=a+b&x=%EA%B0%80',
    ],
    ['  https://e.test/?utm_source=openai  ', 'https://e.test/'],
  ])('href 에서 utm_source=openai 만 뗀다 %s', (url, href) => {
    expect(chip(url, '글').link!.getAttribute('href')).toBe(href);
  });

  it.each([
    'https://e.test/a?',
    'https://e.test/a?b=1&',
    'https://e.test/a?utm_source=news&utm_medium=openai',
    'https://e.test/a?utm_source=openai2',
    'https://e.test/a#utm_source=openai',
    'https://e.test/a?b=1#?utm_source=openai',
  ])('뗄 것이 없으면 href 는 받은 글자 그대로 %s', (url) => {
    expect(chip(url, '글').link!.getAttribute('href')).toBe(url);
  });

  it('href 와 툴팁은 규칙이 다르다: 툴팁은 utm_ 전부, href 는 utm_source=openai 만', () => {
    const { link } = chip(
      'https://e.test/a?utm_source=openai&utm_medium=x&b=1',
      '글',
    );
    expect(link!.getAttribute('href')).toBe(
      'https://e.test/a?utm_medium=x&b=1',
    );
    expect(link!.getAttribute('title')).toBe('https://e.test/a?b=1');
  });

  it('utm_ 을 떼어도 남은 쿼리는 다시 인코딩하지 않는다(%20 이 + 로 안 바뀜)', () => {
    const { link } = chip('https://example.org/p?utm_a=1&q=a%20b', '글');
    expect(link!.getAttribute('title')).toBe('https://example.org/p?q=a b');
    expect(link!.getAttribute('title')).not.toContain('+');
  });

  it('제목·주소의 앞뒤 공백과 제어·방향 글자를 뗀다', () => {
    const { link } = chip(
      '  https://example.org/a%E2%80%AEb  ',
      '  가‮나\u0007  ',
    );
    expect(link!.getAttribute('href')).toBe('https://example.org/a%E2%80%AEb');
    expect(link!.getAttribute('title')).toBe('https://example.org/ab');
    expect(link!.getAttribute('aria-label')).toBe(
      `가나 · example.org · ${NEW_TAB}`,
    );
  });

  it('「/」 가 아주 많은 주소도 금방 끝난다', () => {
    const started = performance.now();
    const { link } = chip(`https://example.org/a${'/'.repeat(50_000)}b`);
    expect(performance.now() - started).toBeLessThan(200);
    expect(link).not.toBeNull();
  });

  it('사용자 정보로 호스트를 속이지 못한다', () => {
    const { link } = chip('https://example.org@example.net/a', '글');
    expect(link!.getAttribute('aria-label')).toBe(
      `글 · example.net · ${NEW_TAB}`,
    );
  });
});

describe('칩이 아닌 값', () => {
  it.each([
    ['example.org/reg-1', undefined, 'example.org/reg-1'],
    ['ftp://example.org/a', undefined, 'ftp://example.org/a'],
    ['mailto:a@example.org', '메일', '메일'],
    ['', '주소 없음', '주소 없음'],
    ['javascript:alert(1)', '  글‮ ', '글'],
  ])('%s 는 회색 글', (url, label, shown) => {
    const { root, link } = chip(url, label);
    expect(link).toBeNull();
    expect(root.textContent).toBe(shown);
    const span = root.firstElementChild!;
    expect(span.tagName).toBe('SPAN');
    expect(span.classList.contains('text-text-tertiary')).toBe(true);
    expect(span.hasAttribute('title')).toBe(false);
    expect(span.hasAttribute('href')).toBe(false);
  });
});
