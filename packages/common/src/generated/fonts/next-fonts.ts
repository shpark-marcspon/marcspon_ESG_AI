import localFont from "next/font/local";

export { nanum } from "./nanum-font";

/**
 * 일반 웹 UI 전용 가변 Pretendard JP.
 *
 * 다국어 글리프 범위를 유지하면서 공통 preload를 정적 5개 파일에서 가변
 * 1개 파일로 줄인다. 보고서/PDF는 report-fonts.ts의 정적 폰트를 사용한다.
 */
export const pretendard = localFont({
  variable: "--font-pretendard",
  /**
   * 폰트 로딩 전 시스템 폰트 노출(FOUT) 방지를 위해 block 유지.
   * 성능 개선은 정적 5개 → 가변 1개 파일 통합으로 확보됨.
   */
  display: "block",
  preload: true,
  fallback: ["sans-serif"],
  src: [
    {
      style: "normal",
      weight: "100 900",
      path: "../../../public/fonts/pretendard/PretendardJPVariable.woff2",
    },
  ],
  declarations: [
    { prop: "ascent-override", value: "95.21%" },
    { prop: "descent-override", value: "24.12%" },
    { prop: "line-gap-override", value: "0%" },
    { prop: "size-adjust", value: "100%" },
  ],
});
