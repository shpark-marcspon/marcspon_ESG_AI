// 새 비밀번호의 규칙(밴드 LG1 ③, 시안 CM-02). 규칙은 「8자 이상」 하나다(MARC-ENT-282 — 서버 검사기를 줄이는 것은 백엔드 몫).
// 서버 검사기는 UA1 에서 「8자 이상」 하나로 줄었다 — 400 PASSWORD_REJECTED 의 글은 서버에 갈래가 남아 화면이 그대로 띄운다(방어).
/** 새 비밀번호의 최소 길이. */
export const MIN_PASSWORD_LENGTH = 8;

/** 글자 수(코드 포인트 — 서버 Django 검사기의 len 과 같다). */
const lengthOf = (value: string) => Array.from(value).length;

export function meetsLength(password: string): boolean {
  return lengthOf(password) >= MIN_PASSWORD_LENGTH;
}

/** 확인 칸을 채웠는데 새 비밀번호와 다른가(빈 확인 칸은 아직 다르다고 하지 않는다). */
export function confirmMismatch(password: string, confirm: string): boolean {
  return confirm !== '' && confirm !== password;
}

/** [비밀번호 바꾸고 시작하기] 는 8자 이상이고 두 칸이 같을 때만 켜진다. */
export function canSubmitPassword(password: string, confirm: string): boolean {
  return meetsLength(password) && password === confirm;
}
