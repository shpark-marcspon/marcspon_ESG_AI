import { Icon, type IconProps } from "../icon-base";

export const AlarmNewIcon = (props: IconProps) => (
  <Icon viewBox="0 0 16 16" fill="none" {...props}>
    <rect
      width="14"
      height="12"
      rx="5"
      transform="matrix(1 0 0 -1 1 14)"
      fill="#383C40"
    />
    <path
      d="M5.4502 11.3996V4.59961H6.8108L8.74808 8.22444L9.42387 9.69273H9.46892C9.39684 8.98611 9.28871 8.08679 9.28871 7.31594V4.59961H10.5502V11.3996H9.1896L7.27034 7.7656L6.59454 6.30649H6.54949C6.60355 7.04064 6.72069 7.89408 6.72069 8.6741V11.3996H5.4502Z"
      fill="white"
    />
  </Icon>
);
