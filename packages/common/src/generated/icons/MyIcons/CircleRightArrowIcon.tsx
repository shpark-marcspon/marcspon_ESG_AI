import { Icon, type IconProps } from "../icon-base";

export const CircleRightArrowIcon = (props: IconProps) => (
  <Icon viewBox="0 0 36 36" fill="none" {...props}>
    <rect
      x="1"
      y="1"
      width="34"
      height="34"
      rx="17"
      stroke="#383C40"
      strokeWidth="2"
    />
    <path
      d="M10 17.75H26.5"
      stroke="#383C40"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M19.75 11L26.5 17.75L19.75 24.5"
      stroke="#383C40"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Icon>
);
