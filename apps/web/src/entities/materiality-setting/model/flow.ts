// AD-02 중대성평가 IRO 탭의 처리 흐름 띠(밴드 IRA2 — 시안 AD-02-IR r1 「처리 흐름」 .fa--ir). 마디 차례와 자리 표만 둔다(이름 0 — 이름은 서버 label).
//   번호 마디 다섯 = 프롬프트 묶음 다섯(서버 materiality/flows/prompt_model_155.py GROUPS 의 key — 번호 = 흐름 차례). 신뢰 출처 목록 묶음은 번호 없는 마디 하나.
//   응답에 없는 key 의 마디는 누를 수 없다. 칸은 서버 차례 그대로라 소묶음이 없다.
//   자리 표(REQUIRED_PLACEHOLDERS — DVA2 이슈 sid:MARC-ISSUE-370 처분 (가) 꼴): 서버가 지키는 자리(engines/colab_155/texts.py REQUIRED, 차례 = PLACEHOLDERS)의 웹 표.
//   판 칸에 있는 넷만(밴드 IRA3 — 1부 가변 입력 셋은 판 칸이 아니다, sid:MARC-ENT-569).
//   칸 아래 안내 글이 쓰고(막지 않음 — 지움은 서버 400 AI_PROMPT_PLACEHOLDER_MISSING 이 칸 오류로), 칠하기·모르는 자리 경고는 없다.

/** 번호 마디의 묶음 key(흐름 차례). */
export const FLOW_GROUPS = [
  'regulation',
  'controversy',
  'impact',
  'financial',
  'pathway',
] as const;
export type FlowGroup = (typeof FLOW_GROUPS)[number];
/** 번호 없는 마디의 묶음 key(신뢰 출처 목록 — 규제·정책 지시 글에 끼워진다). */
export const WHITELIST_GROUP = 'whitelist';
/** temperature 를 싣지 않는 모델 칸 key(분석 모델 — 서버 prompt_model_155.ANALYSIS, sid:MARC-ENT-468). */
export const ANALYSIS_SLOT = 'analysis';

const PART2 = [
  '{기업명}',
  '{산업 정의}',
  '{가치사슬 활동}',
  '{토픽}',
  '{서브토픽}',
  '{서브토픽 설명}',
  '{컨트로버시 리서치의 답}',
  '{규제·정책 리서치의 답}',
];

/** 칸 key → 지워선 안 되는 자리(차례 = 서버 표). 표에 없는 칸(지시 글·접두·신뢰 출처)은 통째로 바꿔도 된다. */
export const REQUIRED_PLACEHOLDERS: Readonly<
  Record<string, readonly string[]>
> = {
  regulation_system: ['{신뢰 출처 목록}'],
  impact_input: PART2,
  financial_input: PART2,
  pathway_input: ['{재무 영향 정의의 답}'],
};

/** 서버 묶음(label = 서버 묶음 이름). */
type Groups = readonly {
  key: string;
  label: string;
}[];

/** 흐름 마디 하나: 묶음 key · 서버 묶음 자리(없으면 null) · 이름(서버 label) · 번호(흐름 차례 + 1, 신뢰 출처는 null). */
export interface FlowNode {
  key: FlowGroup | typeof WHITELIST_GROUP;
  group: number | null;
  label: string | null;
  n: number | null;
}

/** 서버 묶음에서 번호 마디 다섯과 신뢰 출처 마디(끝)를 찾는다. */
export function flowNodes(groups: Groups): FlowNode[] {
  const find = (key: string) => {
    const group = groups.findIndex((one) => one.key === key);
    return {
      group: group >= 0 ? group : null,
      label: group >= 0 ? groups[group]!.label : null,
    };
  };
  return [
    ...FLOW_GROUPS.map((key, index) => ({ key, ...find(key), n: index + 1 })),
    { key: WHITELIST_GROUP, ...find(WHITELIST_GROUP), n: null },
  ];
}
