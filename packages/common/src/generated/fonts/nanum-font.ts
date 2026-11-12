import localFont from "next/font/local";

export const nanum = localFont({
  src: [
    {
      path: "../../../public/fonts/nanum/NanumSquareNeoTTF-eHv.woff2",
      weight: "900",
      style: "normal",
    },
  ],
  variable: "--font-nanum",
  display: "swap",
  preload: true,
});
