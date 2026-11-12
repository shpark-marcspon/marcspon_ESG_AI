import { Icon, type IconProps } from "../icon-base";

export const LoadingbarIcon = (props: IconProps) => (
  <Icon viewBox="0 0 49 50" fill="none" {...props}>
    <circle cx="24" cy="25" r="22" stroke="#E0E0E0" strokeWidth="4" />
    <path
      d="M24 2.92001C26.8996 2.92001 29.7708 3.49113 32.4497 4.60075C35.1285 5.71038 37.5626 7.33678 39.6129 9.3871C41.6632 11.4374 43.2896 13.8715 44.3993 16.5504C45.5089 19.2292 46.08 22.1004 46.08 25C46.08 27.8996 45.5089 30.7708 44.3993 33.4497C43.2896 36.1285 41.6632 38.5626 39.6129 40.6129C37.5626 42.6633 35.1285 44.2897 32.4496 45.3993C29.7708 46.5089 26.8996 47.08 24 47.08"
      stroke="url(#paint0_linear_4030_3830)"
      strokeWidth="4"
      strokeLinecap="round"
    />
    <rect x="31" y="27" width="4" height="6" rx="2" fill="#F25B2B" />
    <rect x="25" y="25" width="4" height="8" rx="2" fill="#F25B2B" />
    <rect x="19" y="21" width="4" height="12" rx="2" fill="#F25B2B" />
    <rect x="13" y="16" width="4" height="17" rx="2" fill="#F25B2B" />
    <defs>
      <linearGradient
        id="paint0_linear_4030_3830"
        x1="24"
        y1="2.92001"
        x2="24"
        y2="47.08"
        gradientUnits="userSpaceOnUse"
      >
        <stop stopColor="#F79D80" />
        <stop offset="1" stopColor="#F25B2B" />
      </linearGradient>
    </defs>
  </Icon>
);
