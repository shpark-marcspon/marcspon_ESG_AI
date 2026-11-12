import type { SVGProps } from "react";

/** 기존 Chakra DotsThreeVerticalIcon과 동일한 SVG를 사용하는 공통 아이콘. */
export function DotsThreeVerticalIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true" {...props}>
      <path
        d="M8 8.75C8.41421 8.75 8.75 8.41421 8.75 8C8.75 7.58579 8.41421 7.25 8 7.25C7.58579 7.25 7.25 7.58579 7.25 8C7.25 8.41421 7.58579 8.75 8 8.75Z"
        fill="currentColor"
      />
      <path
        d="M8 4.5C8.41421 4.5 8.75 4.16421 8.75 3.75C8.75 3.33579 8.41421 3 8 3C7.58579 3 7.25 3.33579 7.25 3.75C7.25 4.16421 7.58579 4.5 8 4.5Z"
        fill="currentColor"
      />
      <path
        d="M8 13C8.41421 13 8.75 12.6642 8.75 12.25C8.75 11.8358 8.41421 11.5 8 11.5C7.58579 11.5 7.25 11.8358 7.25 12.25C7.25 12.6642 7.58579 13 8 13Z"
        fill="currentColor"
      />
    </svg>
  );
}
