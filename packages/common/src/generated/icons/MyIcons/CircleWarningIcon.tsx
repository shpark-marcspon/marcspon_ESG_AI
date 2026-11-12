import { Icon, type IconProps } from "../icon-base";

export const CircleWarningIcon = (props: IconProps) => (
  <Icon viewBox="0 0 16 16" fill="none" {...props}>
    <path
      d="M2 8C2 4.68629 4.68629 2 8 2C11.3137 2 14 4.68629 14 8C14 11.3137 11.3137 14 8 14C4.68629 14 2 11.3137 2 8Z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M8 5L8 8.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx="8" cy="10.75" r="0.75" fill="currentColor" />
  </Icon>
);
