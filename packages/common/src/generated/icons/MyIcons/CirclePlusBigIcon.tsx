import { Icon, type IconProps } from "../icon-base";

export const CirclePlusBigIcon = (props: IconProps) => (
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
      d="M18 9L18 18M18 18V27M18 18H27M18 18H9"
      stroke="#383C40"
      strokeWidth="2"
      strokeLinecap="round"
    />
  </Icon>
);
