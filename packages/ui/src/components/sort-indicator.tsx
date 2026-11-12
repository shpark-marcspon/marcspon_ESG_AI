import type { SVGProps } from "react";

import { cn } from "../lib/utils";

export type SortDirection = false | "asc" | "desc";

/** 기존 테이블 정렬 아이콘의 path와 활성 색상을 유지한 Tailwind SVG. */
export function SortIndicator({
  className,
  direction,
  ...props
}: Omit<SVGProps<SVGSVGElement>, "direction"> & { direction: SortDirection }) {
  const inactiveColor = "var(--marcspon-token-grey-400, #b0b7bf)";
  const activeColor = "var(--marcspon-token-grey-800, #383c40)";

  return (
    <svg
      aria-hidden
      viewBox="0 0 16 16"
      fill="none"
      className={cn("h-4 w-4 shrink-0", className)}
      {...props}
    >
      <path
        d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z"
        fill={direction === "desc" ? activeColor : inactiveColor}
        stroke={direction === "desc" ? activeColor : inactiveColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z"
        fill={direction === "asc" ? activeColor : inactiveColor}
        stroke={direction === "asc" ? activeColor : inactiveColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
