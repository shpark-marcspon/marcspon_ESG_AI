// AD-02 보고서 작성 탭의 처리 흐름 띠(밴드 RPA3 — 시안 AD-02-RP r1 「처리 흐름」 .fa-rp). 마디 차례와 자리 표만 둔다(이름 0 — 이름은 서버 label).
//   번호 마디 둘 = 프롬프트 묶음 둘(서버 drafting/flows/prompt_model_v2.py GROUPS 의 key — 번호 = 흐름 차례: 목차 달기(S2) · 초안 짓기(S3)).
//   응답에 없는 key 의 마디는 누를 수 없다. 칸은 서버 차례 그대로라 소묶음이 없다.
//   자리 표(REQUIRED_PLACEHOLDERS — DVA2 이슈 sid:MARC-ISSUE-370 처분 (가) 꼴): 서버가 지키는 자리(prompt_model_v2.py PLACEHOLDERS·REQUIRED — 입력 글 둘,
//   자리 글자는 engines/v2/texts.py 의 OUTLINE_SLOT·PAGES_SLOT·TITLE_SLOT·REQUIREMENT_SLOT — 재료 자리 v2 `{페이지 글}`)의 웹 표. 칸 아래 안내 글이 쓰고(막지 않음 — 지움은 서버 400
//   AI_PROMPT_PLACEHOLDER_MISSING 이 칸 오류로), 칠하기·모르는 자리 경고는 없다. 지시 글 둘은 자리가 없다.

/** 번호 마디의 묶음 key(흐름 차례). */
export const FLOW_GROUPS = ['map', 'draft'] as const;
export type FlowGroup = (typeof FLOW_GROUPS)[number];

/** 칸 key → 지워선 안 되는 자리(차례 = 서버 표). 표에 없는 칸(지시 글 둘)은 통째로 바꿔도 된다. */
export const REQUIRED_PLACEHOLDERS: Readonly<
  Record<string, readonly string[]>
> = {
  map_user: ['{목차}', '{페이지 글}'],
  draft_user: ['{제목 경로}', '{요구 내용}', '{페이지 글}'],
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

/** 서버 묶음에서 번호 마디 둘을 찾는다. */
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
