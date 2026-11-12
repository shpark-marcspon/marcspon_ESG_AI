// 처리 흐름 띠의 마디 차례(밴드 AS3b ② — 발주서 §3-4). 서버 칸 key 는 사본 픽스처로 견준다(서버를 import 하지 않는다).
import { describe, expect, it } from 'vitest';

import { FLOW_KEYS, flowNodes } from './flow.ts';

/** 서버 PROMPT_IDS 사본(greenwash/flows/prompt_model_e0.py — 묶음 judge 하나, 칸 차례). */
const SERVER_PROMPT_IDS = ['detect', 'eval', 'repair', 'low_only'];
const GROUPS = [
  {
    key: 'judge',
    prompts: SERVER_PROMPT_IDS.map((key) => ({ key, label: `지어낸 ${key}` })),
  },
];

describe('흐름 마디', () => {
  it('번호 마디 key 차례 = 서버 칸 key 차례', () => {
    expect([...FLOW_KEYS]).toEqual(SERVER_PROMPT_IDS);
  });

  it('마디는 서버 자리·label·묶음 안 번호를 key 로 찾는다(웹 상수 이름 0)', () => {
    expect(flowNodes(GROUPS)).toEqual(
      SERVER_PROMPT_IDS.map((key, index) => ({
        key,
        at: { group: 0, prompt: index },
        label: `지어낸 ${key}`,
        n: index + 1,
      })),
    );
  });

  it('응답에 없는 key 는 자리·이름·번호 null(누를 수 없는 마디) · 다른 묶음에 있어도 찾는다', () => {
    const nodes = flowNodes([
      { key: 'a', prompts: [{ key: 'eval', label: '지어낸 판정' }] },
      {
        key: 'b',
        prompts: [
          { key: 'x', label: '지어낸 딴' },
          { key: 'detect', label: '지어낸 찾기' },
        ],
      },
    ]);
    expect(nodes.map((node) => [node.key, node.at, node.n])).toEqual([
      ['detect', { group: 1, prompt: 1 }, 2],
      ['eval', { group: 0, prompt: 0 }, 1],
      ['repair', null, null],
      ['low_only', null, null],
    ]);
  });
});
