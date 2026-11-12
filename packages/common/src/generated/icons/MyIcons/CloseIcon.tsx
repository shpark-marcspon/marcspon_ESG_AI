import { Icon, type IconProps } from "../icon-base";

export const CloseIcon = (props: IconProps) => (
  <Icon viewBox="0 0 24 24" fill="none" {...props}>
    <path
      d="M18 6L6 18M18 18L6 6"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </Icon>
);
