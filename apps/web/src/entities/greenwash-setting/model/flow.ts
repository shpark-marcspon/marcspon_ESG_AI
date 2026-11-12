// AD-02 그린워싱 탭의 처리 흐름 띠(밴드 AS3b ② — 셋째 열을 갈음). 마디 차례만 둔다(이름 0 — 마디 이름은 서버 label, sid:MARC-ENT-384).
//   번호 마디 넷의 key 차례 = 서버 PROMPT_IDS(greenwash/flows/prompt_model_e0.py — 묶음 judge 하나의 칸 차례). 글(갈래·도는 횟수)은 config/text.ts.

/** 번호 마디의 칸 key(흐름 차례 — 서버 PROMPT_IDS 와 같다). */
export const FLOW_KEYS = ['detect', 'eval', 'repair', 'low_only'] as const;
export type FlowKey = (typeof FLOW_KEYS)[number];

/** 흐름 마디 하나: key · 서버 자리(묶음·칸 — 응답에 없으면 null) · 이름(서버 label) · 번호(묶음 안 칸 차례 + 1). */
export interface FlowNode {
  key: FlowKey;
  at: { group: number; prompt: number } | null;
  label: string | null;
  n: number | null;
}

/** 서버 묶음·칸(key·label)에서 번호 마디 넷을 찾는다(없는 key 는 누를 수 없는 마디). */
export function flowNodes(
  groups: readonly {
    key: string;
    prompts: readonly { key: string; label: string }[];
  }[],
): FlowNode[] {
  return FLOW_KEYS.map((key) => {
    for (const [group, one] of groups.entries()) {
      const prompt = one.prompts.findIndex((entry) => entry.key === key);
      if (prompt >= 0)
        return {
          key,
          at: { group, prompt },
          label: one.prompts[prompt]!.label,
          n: prompt + 1,
        };
    }
    return { key, at: null, label: null, n: null };
  });
}
