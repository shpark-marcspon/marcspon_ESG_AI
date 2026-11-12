import { Icon, type IconProps } from "../icon-base";

export const PlusIcon = (props: IconProps) => (
  <Icon viewBox="0 0 24 24" fill="none" {...props}>
    <path
      d="M12 5L12 19M19 12L5 12"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </Icon>
);
