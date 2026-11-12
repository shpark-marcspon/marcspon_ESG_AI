// 잠근 때 표기(밴드 S3W3a ③). entities/ghg 의 entryAtText 를 옮겨 적었다(칸끼리 가져오지 않는다).

const KST_MS = 9 * 3_600_000;

/** 한국 시각 글자(읽을 수 없으면 null). */
const kstOf = (iso: string): string | null => {
  const time = Date.parse(iso);
  return Number.isNaN(time) ? null : new Date(time + KST_MS).toISOString();
};

/** 서버 시각 글자 → 「2026-01-02 12:04」(한국 시각). 읽을 수 없으면 받은 글자 그대로. */
export function lockAtText(iso: string): string {
  const text = kstOf(iso);
  return text === null ? iso : `${text.slice(0, 10)} ${text.slice(11, 16)}`;
}

/** 히스토리 수정일시(값 파일 5절) → 「2026.01.02 12:04」(한국 시각). 읽을 수 없으면 받은 글자 그대로. */
export function historyAtText(iso: string): string {
  const text = kstOf(iso);
  return text === null ? iso : (
      `${text.slice(0, 10).replaceAll('-', '.')} ${text.slice(11, 16)}`
    );
}
