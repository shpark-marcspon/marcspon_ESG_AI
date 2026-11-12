// 이 화면만 쓰는 업무 로직의 공개 표면(밴드 FS1 ③ M-c). 옛 entities/greenwash/model 의 form·paint 를 옮겨 왔다(새 점검 화면 하나만 쓴다).
export { validateNewCheck } from './form.ts';
export type { FormInput, FormProblem } from './form.ts';
export { paintModeAt, paintRange, togglePage } from './paint.ts';
export type { PaintMode } from './paint.ts';
