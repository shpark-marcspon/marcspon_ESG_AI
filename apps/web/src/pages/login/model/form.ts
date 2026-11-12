// 로그인 칸의 판정(밴드 LG1 ②, 시안 CM-01). 순수 함수.
/** 두 칸 다 차야 [로그인] 이 켜진다(시안에 꺼짐 상태가 없어 추정 — 발주서 §3). 아이디의 앞뒤 빈칸은 빈 것으로 본다. */
export function canSubmitLogin(username: string, password: string): boolean {
  return username.trim() !== '' && password !== '';
}
