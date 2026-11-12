// 중대성평가 IRO 칸 아래 안내 글(밴드 IRA3 — 발주서 Q5, sid:MARC-ENT-569). 모듈 줄(app/admin/ai-setting-modules.ts)의 promptNote 가 부르기만 한다.
//   자리 지킴 칸 넷(model REQUIRED_PLACEHOLDERS) → 자리 안내(IRA2 꼴 그대로 — 막지 않음, 지우면 서버 400 이 칸 오류로).
//   1부 입력 글 셋(regulation_prefix·keywords_prefix·controversy_prefix — 그 user 호출에 기본 틀이 붙는 칸) → inputNote(시안 v211).
//   그 밖 칸(지시 글·신뢰 출처 둘·모르는 칸·옛 판의 가변 입력 셋)은 null.
//   모양이 없는 순수 함수지만 문구 표(config)와 자리 표(model)를 함께 읽어 ui 칸에 둔다(config 는 ui 만 가져온다 — app/guards/layers.test.ts).
import { MATERIALITY_SETTING_TEXT } from '../config/text.ts';
import { REQUIRED_PLACEHOLDERS } from '../model/index.ts';

/** 1부 입력 글 칸(그 user 호출에 기본 틀 글이 붙는다 — 서버 prompt_model_155 GROUPS). */
export const INPUT_PREFIXES: readonly string[] = [
  'regulation_prefix',
  'keywords_prefix',
  'controversy_prefix',
];

/** 칸 key → 칸 아래 안내 글(없으면 null). */
export function materialityPromptNote(prompt: string): string | null {
  const words = MATERIALITY_SETTING_TEXT;
  if (INPUT_PREFIXES.includes(prompt)) return words.inputNote;
  const slots = REQUIRED_PLACEHOLDERS[prompt];
  if (!slots) return null;
  const place = words.placeholders;
  const from = place.from[prompt];
  if (from === undefined) return `${place.whitelist(slots)} · ${place.tail}`;
  return `${place.lead(slots)} — ${from} · ${place.tail}`;
}
