import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * Tailwind v3 + tailwind-merge v1용 프로젝트 병합 규칙.
 * text-style-*가 색상 유틸리티와 충돌해 제거되지 않도록 별도 그룹으로 둔다.
 */
const twMerge = extendTailwindMerge({
  classGroups: {
    "text-style": [{ "text-style": [() => true] }],
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
