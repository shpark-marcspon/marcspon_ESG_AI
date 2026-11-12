// AD-02 model 칸의 공개 표면(밴드 AD2S ②). 순수 함수와 타입만 — 글은 인자로 받는다. 칸 밖에서 부르는 이름만 둔다.
export { changeList, componentLines, modelName, modelUses } from './lines.ts';
export type { ChangeWords } from './lines.ts';
export { refusalOf, slotKey } from './refusal.ts';
export type { RefusalShown, RefusalWords, SlotRefusals } from './refusal.ts';
