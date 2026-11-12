// 온실가스 조직구조의 id 꼴(밴드 W12-0a ① — sid:MARC-ISSUE-92, K1b-1 넘김).
// 응답 id 는 글자(옛 SiteOut 꼴), 요청 id(ids[]·facilities[].id·facilityCodeId·경로 branch_id·code_id)는 정수다.
// 글자 → 정수 바꿈은 이 함수 하나다(entities/ghg/model 밖에서 Number( 를 쓰지 않는다 — 발주서 §1-4).

/** 응답 id 글자를 요청 id 정수로. 양의 정수 글자가 아니면 던진다(요청을 보내지 않는다). */
export function toRequestId(id: string): number {
  if (!/^[1-9][0-9]*$/.test(id))
    throw new RangeError(`not a request id: ${id}`);
  const value = Number(id);
  if (!Number.isSafeInteger(value))
    throw new RangeError(`not a request id: ${id}`);
  return value;
}
