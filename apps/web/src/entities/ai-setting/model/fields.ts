// AI 설정 저장 거절의 칸 경로 풀이(밴드 AD2W ④). 순수 함수만 있다.
//   서버 프롬프트 글 받기 거절(400 AI_PROMPT_*)의 fields 경로 `prompts.steps.<i>.prompts.<j>.text|memo`(apps/api-py core/calc/ai_settings.py — 422 와 같은 규칙)
//   → (묶음 i, 칸 j, 칸 종류) — 입력 prompts.steps[i] 는 묶음 i(ai.prompt-model@3). 모르는 경로(prompts·prompts.steps·prompts.steps.<i>.prompts 등)는 null — 쓰는 화면이 버리지 않고 창의 일반 줄로 보인다.

interface PromptField {
  group: number;
  prompt: number;
  field: 'text' | 'memo';
}

/** 칸 경로 하나 → 칸 자리(모르는 꼴이면 null). */
export function promptFieldOf(path: string): PromptField | null {
  const hit =
    /^prompts\.steps\.(0|[1-9]\d*)\.prompts\.(0|[1-9]\d*)\.(text|memo)$/.exec(
      path,
    );
  if (!hit) return null;
  return {
    group: Number(hit[1]),
    prompt: Number(hit[2]),
    field: hit[3] as PromptField['field'],
  };
}
