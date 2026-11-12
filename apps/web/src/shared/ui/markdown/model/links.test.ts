// 앞처리가 믿지 않는 긴 글에서 멈추지 않는다(밴드 MD1 검증 반영). 문턱은 부하로 깜빡이지 않게 넉넉히 둔다 — 고치기 전에는 몇 초에서 몇 분이었다.
import { describe, expect, it } from 'vitest';

import { type TreeNode, remarkLinks } from './links.ts';

const LIMIT_MS = 200;
const LONG = 50_000;

function literal(url: string): TreeNode {
  return { type: 'link', url, children: [{ type: 'text', value: url }] };
}

function run(children: TreeNode[]) {
  const started = performance.now();
  remarkLinks()({ type: 'paragraph', children });
  return performance.now() - started;
}

describe('긴 글', () => {
  it('주소 끝 한글 5만 자', () => {
    const url = 'https://example.org/a';
    const children = [literal(url + '가'.repeat(LONG))];
    expect(run(children)).toBeLessThan(LIMIT_MS);
    expect(children[0]!.url).toBe(url);
    expect(children[1]!.value).toHaveLength(LONG);
  });

  it('주소 안 한글 5만 자 뒤에 다른 글자가 오면 떼지 않는다', () => {
    const url = `https://example.org/${'가'.repeat(LONG)}a`;
    const children = [literal(url)];
    expect(run(children)).toBeLessThan(LIMIT_MS);
    expect(children).toHaveLength(1);
    expect(children[0]!.url).toBe(url);
  });

  it.each([
    ['공백', `이름${' '.repeat(LONG)}(`],
    ['쉼표와 괄호', `${',a'.repeat(LONG / 2)}(b (`],
  ])('이름 앞 글이 긴 꼴: %s', (_, head) => {
    const children = [
      { type: 'text', value: head },
      literal('https://example.org/a'),
      { type: 'text', value: ')' },
    ];
    expect(run(children)).toBeLessThan(LIMIT_MS);
  });
});
