// 원고작성 id 꼴(밴드 RPW1 ① — 발주서 §1-4 ⑦). 서버 id 는 정수다. 주소의 $projectId·$runId 글자를 정수로 바꾸는 자리는 이 함수 하나다
//   (entities/drafting/model 밖에서 Number( 를 쓰지 않는다). 글자 수는 코드 포인트로 센다(서버 len 과 같게 — §1-4 ⑧).

/** 주소 글자 → 서버 id. 양의 정수 글자가 아니면 null(요청하지 않는다). */
export function idOf(text: string): number | null {
  if (!/^[1-9][0-9]*$/.test(text)) return null;
  const value = Number(text);
  return Number.isSafeInteger(value) ? value : null;
}

/** 글자 수(코드 포인트 — 서버 len 과 같다. 「😀」는 1). */
export const lengthOf = (text: string): number => [...text].length;
