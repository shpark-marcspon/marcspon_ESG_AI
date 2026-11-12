// S3-12 창의 AI 그룹 별(밴드 S3W4 ② — Q9). 같은 꼴 생성 아이콘이 없어 보드 svg(캔버스 v214 S3-12_r2, Figma 29209:30194)를 옮겼다. 색은 토큰 text-brand.
// 별은 제목 밖 형제다(창 이름에 섞이지 않게 — critic R2). hover 글은 감싼 칸의 title, 읽는 글은 aria-label.
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { SPARKLE } from '../../../entities/ghg-scope3/model/index.ts';

const label = S3_TEXT.detail.factorWindow.aiGroup;

export function AiGroupStar() {
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      data-testid="s3-ai-star"
      className="inline-flex size-4 shrink-0 text-text-brand"
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 16.5 16.5"
        fill="none"
        className="size-4"
      >
        <path
          d={SPARKLE}
          fill="currentColor"
          stroke="currentColor"
          strokeWidth="0.5"
        />
      </svg>
    </span>
  );
}
