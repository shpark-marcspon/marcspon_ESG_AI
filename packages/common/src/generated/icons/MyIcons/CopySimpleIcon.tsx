import { Icon, type IconProps } from "../icon-base";

export const CopySimpleIcon = (props: IconProps) => (
  <Icon viewBox="0 0 16 16" fill="none" {...props}>
    <path
      d="M11.5 4.5L2.5 4.5L2.5 13.5L11.5 13.5L11.5 4.5Z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M4.5 2.5L13.5 2.5L13.5 11.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Icon>
);
