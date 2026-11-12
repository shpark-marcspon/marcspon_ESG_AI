// 출처 칸 글(상세 표·창이 같이 쓴다 — 밴드 S3WS2 꼴). 갈래 값 → 책 이름, usepa-estimate 는 뒤 회색 「· 기타」와 hover 글. raw 는 서버 글자 그대로(시트 이름·고친 출처 — S3W3c1). 없으면 「-」.
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { SOURCE_ESTIMATE } from '../../../entities/ghg-scope3/model/index.ts';
import type { SourceCell } from '../../../entities/ghg-scope3/model/index.ts';
import { cellText } from './detailText.ts';

const words = S3_TEXT.detail;

export function SourceText({ source }: { source: SourceCell }) {
  const book = cellText(source, 'source');
  if (source.raw || source.text !== SOURCE_ESTIMATE) return book;
  return (
    <span title={words.sourceEstimateHint}>
      {book} <span className="text-text-tertiary">{words.sourceOther}</span>
    </span>
  );
}
