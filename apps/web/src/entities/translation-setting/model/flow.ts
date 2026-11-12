// AD-02 영문번역 탭의 처리 흐름 띠(밴드 TRA1 — 시안 AD-02-TR r1 「처리 흐름」). 마디 차례와 번역 묶음의 소묶음 표만 둔다(이름 0 — 이름은 서버 label).
//   번호 마디 다섯 = 프롬프트 묶음 다섯(서버 translation/flows/prompt_model_158.py GROUPS 의 key — 번호 = 흐름 차례). 응답에 없는 key 의 마디는 누를 수 없다.
//   번역 묶음의 칸 아홉은 계약에 보이는 차례·소묶음이 없어(발주서 S2) 웹 표로 셋에 나눈다(차례 = 시안): 모든 파트 공통 넷 → 파트마다 하나 셋 → 고른 문체 하나 둘.
//   표에 없는 key 는 끝 「그 밖」(other)에 서버 차례대로. 다른 묶음은 소묶음 없이 서버 차례 그대로.

/** 번호 마디의 묶음 key(흐름 차례). */
export const FLOW_GROUPS = [
  'translate',
  'polish',
  'editorial_qa',
  'review',
  'autofix',
] as const;
export type FlowGroup = (typeof FLOW_GROUPS)[number];

/** 번역 묶음의 소묶음(차례 = 시안). */
export const TRANSLATE_SECTIONS = [
  {
    key: 'common',
    prompts: [
      'style_rules',
      'subject_fragment_rules',
      'terminology_note',
      'table_rules',
    ],
  },
  { key: 'part', prompts: ['tone_ceo_message', 'tone_story', 'tone_general'] },
  { key: 'style', prompts: ['style_a', 'style_b'] },
] as const;
export type SectionKey = (typeof TRANSLATE_SECTIONS)[number]['key'] | 'other';

/** 서버 묶음(label = 서버 묶음 이름). */
type Groups = readonly {
  key: string;
  label: string;
  prompts: readonly { key: string; label: string }[];
}[];

/** 흐름 마디 하나: 묶음 key · 서버 묶음 자리(없으면 null) · 이름(서버 label) · 번호(흐름 차례 + 1). */
export interface FlowNode {
  key: FlowGroup;
  group: number | null;
  label: string | null;
  n: number;
}

/** 서버 묶음에서 번호 마디 다섯을 찾는다. */
export function flowNodes(groups: Groups): FlowNode[] {
  return FLOW_GROUPS.map((key, index) => {
    const group = groups.findIndex((one) => one.key === key);
    return {
      key,
      group: group >= 0 ? group : null,
      label: group >= 0 ? groups[group]!.label : null,
      n: index + 1,
    };
  });
}

/** 칸 고름의 칸 하나: 서버 key·label · 묶음 안 자리. */
export interface SectionPrompt {
  key: string;
  label: string;
  prompt: number;
}

/** 칸 고름의 소묶음 하나(key null = 소묶음 없는 묶음 — 머리 줄 0). */
export interface Section {
  key: SectionKey | null;
  prompts: SectionPrompt[];
}

/** 묶음 하나의 칸을 소묶음으로. 번역 묶음만 웹 표로 나누고(빈 소묶음은 뺌), 모르는 key 는 끝 「그 밖」. */
export function promptSections(group: {
  key: string;
  prompts: readonly { key: string; label: string }[];
}): Section[] {
  const all = group.prompts.map(({ key, label }, prompt): SectionPrompt => ({
    key,
    label,
    prompt,
  }));
  if (group.key !== 'translate') return [{ key: null, prompts: all }];
  const known = new Set<string>(
    TRANSLATE_SECTIONS.flatMap((section) => section.prompts),
  );
  const sections: Section[] = TRANSLATE_SECTIONS.map((section) => ({
    key: section.key,
    prompts: section.prompts.flatMap((key) =>
      all.filter((one) => one.key === key),
    ),
  }));
  sections.push({
    key: 'other',
    prompts: all.filter((one) => !known.has(one.key)),
  });
  return sections.filter((section) => section.prompts.length > 0);
}

/** 묶음 하나에서 보이는 차례의 첫 칸 자리(소묶음 차례 — 빈 묶음은 0). 처음 펼침·마디 누름이 고른다. */
export const firstShown = (group: {
  key: string;
  prompts: readonly { key: string; label: string }[];
}): number => promptSections(group)[0]?.prompts[0]?.prompt ?? 0;
