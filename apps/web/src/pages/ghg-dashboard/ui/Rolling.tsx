// 대시보드 제목 숫자 굴림 칸(밴드 DB4 — 발주서 §2-③ · 감독 판단 3·4). 셈은 model(roll*) · 때는 hooks(useRoll) — 이 파일은 그리기만.
//   굴리는 동안: 끝 글자를 보이지 않게 깔아 칸 폭을 잡고(흔들림 0 — tabular-nums 와 함께) 그 위 같은 칸에 프레임 글자를 그린다.
//   화면 읽기에는 끝 글자만(프레임·깔개 aria-hidden, 끝 글자 sr-only). 다 굴면 끝 글자 하나만 — BASE 와 같은 꼴·같은 글자.
//   인벤토리 카드에 같은 꼴의 칸이 하나 더 있다(pages 끼리는 가져오지 않는다 — pages/ghg-inventory/ui/EmissionCard.tsx).
import { useRoll } from '../../../entities/ghg/hooks/index.ts';

export function Rolling({
  text,
  delay,
  still = false,
  align = 'end',
}: {
  /** 끝 글자(지금 그리는 문자열 그대로). */
  text: string;
  /** 시작 지연 ms(그 카드의 떠오름 또는 도넛 쓸기 지연). */
  delay: number;
  /** 움직이지 않음(덮개 뒤 판). */
  still?: boolean;
  /** 프레임 글자를 칸 안 어디에 맞추나(오른쪽 맞춤 숫자 · 도넛 가운데). */
  align?: 'end' | 'center';
}) {
  const frame = useRoll(text, { delay, enabled: !still });
  if (frame === null) return <>{text}</>;
  const side = align === 'end' ? 'text-right' : 'text-center';
  return (
    <span data-rolling="" className="inline-grid">
      <span aria-hidden className="invisible [grid-area:1/1]">
        {text}
      </span>
      <span aria-hidden className={`[grid-area:1/1] ${side}`}>
        {frame}
      </span>
      <span className="sr-only">{text}</span>
    </span>
  );
}
