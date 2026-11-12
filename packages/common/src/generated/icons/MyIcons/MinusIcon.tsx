import { Icon, type IconProps } from "../icon-base";

export const MinusIcon = (props: IconProps) => (
  <Icon viewBox="0 0 24 24" fill="none" {...props}>
    <path
      d="M5 12L19 12"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Icon>
);
