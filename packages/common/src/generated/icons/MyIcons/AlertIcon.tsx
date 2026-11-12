import { Icon, type IconProps } from "../icon-base";

export const AlertIcon = (props: IconProps) => (
  <Icon viewBox="0 0 16 16" fill="none" {...props}>
    <path
      d="M14 8C14 11.3137 11.3137 14 8 14C4.68629 14 2 11.3137 2 8C2 4.68629 4.68629 2 8 2C11.3137 2 14 4.68629 14 8Z"
      fill="#383C40"
    />
    <path
      d="M8 8V5M8 10.2236V10.25"
      stroke="white"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Icon>
);
