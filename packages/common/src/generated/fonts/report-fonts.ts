import localFont from "next/font/local";

/**
 * 보고서 전용 정적 Pretendard JP.
 *
 * PDF 페이지 분할과 Adobe 호환성을 위해 가변 폰트 대신 weight별 정적 파일을
 * 사용한다. 일반 앱에서는 이 모듈을 import하지 않아 정적 폰트가 공통 preload
 * 대상에 포함되지 않도록 한다.
 */
export const pretendardReport = localFont({
  variable: "--font-pretendard",
  display: "block",
  preload: false,
  fallback: ["sans-serif"],
  src: [
    {
      style: "normal",
      weight: "300",
      path: "../../../public/fonts/pretendard/PretendardJP-Light.woff2",
    },
    {
      style: "normal",
      weight: "400",
      path: "../../../public/fonts/pretendard/PretendardJP-Regular.woff2",
    },
    {
      style: "normal",
      weight: "500",
      path: "../../../public/fonts/pretendard/PretendardJP-Medium.woff2",
    },
    {
      style: "normal",
      weight: "600",
      path: "../../../public/fonts/pretendard/PretendardJP-SemiBold.woff2",
    },
    {
      style: "normal",
      weight: "700",
      path: "../../../public/fonts/pretendard/PretendardJP-Bold.woff2",
    },
  ],
  declarations: [
    { prop: "ascent-override", value: "95.21%" },
    { prop: "descent-override", value: "24.12%" },
    { prop: "line-gap-override", value: "0%" },
    { prop: "size-adjust", value: "100%" },
  ],
});
