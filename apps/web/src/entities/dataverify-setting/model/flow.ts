// AD-02 데이터 검증 탭의 처리 흐름 띠(밴드 DVA2 — 시안 AD-02-DV r1 「처리 흐름」 .fa--dv). 마디 차례와 입력 글 자리 표만 둔다(이름 0 — 이름은 서버 label).
//   번호 마디 셋 = 프롬프트 묶음 셋(서버 dataverify/flows/prompt_model_156.py GROUPS 의 key — 번호 = 흐름 차례). 응답에 없는 key 의 마디는 누를 수 없다.
//   칸은 묶음마다 지시 글·입력 글 둘이라 소묶음이 없다(서버 차례 그대로).
//   입력 글 자리(REQUIRED_PLACEHOLDERS — 이슈 sid:MARC-ISSUE-370 처분 (가)): 서버가 지키는 자리(engines/colab_156/prompts.py REQUIRED)의 웹 표.
//   입력 글 칸 아래 안내 글이 쓰고(막지 않음 — 지움은 서버 400 AI_PROMPT_PLACEHOLDER_MISSING 이 칸 오류로), 칠하기·모르는 자리 경고는 없다.

/** 번호 마디의 묶음 key(흐름 차례). */
export const FLOW_GROUPS = ['plan', 'review', 'insight'] as const;
export type FlowGroup = (typeof FLOW_GROUPS)[number];

/** 입력 글 칸 key → 지워선 안 되는 자리(차례 = 서버 표). 지시 글 칸은 자리를 지워도 된다(표에 없음). */
export const REQUIRED_PLACEHOLDERS: Readonly<
  Record<string, readonly string[]>
> = {
  plan_user: [
    '{기업명}',
    '{SASB 산업분류}',
    '{중대토픽}',
    '{보고연도}',
    '{입력 데이터 JSON}',
  ],
  review_user: ['{계산 계획의 산식 목록}', '{입력 데이터 JSON}'],
  insight_user: [
    '{기업명}',
    '{SASB 산업분류}',
    '{중대토픽}',
    '{보고연도}',
    '{입력 데이터 JSON}',
  ],
};

/** 서버 묶음(label = 서버 묶음 이름). */
type Groups = readonly {
  key: string;
  label: string;
}[];

/** 흐름 마디 하나: 묶음 key · 서버 묶음 자리(없으면 null) · 이름(서버 label) · 번호(흐름 차례 + 1). */
export interface FlowNode {
  key: FlowGroup;
  group: number | null;
  label: string | null;
  n: number;
}

/** 서버 묶음에서 번호 마디 셋을 찾는다. */
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
