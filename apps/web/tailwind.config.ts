import sharedConfig from '@marcspon/tailwind-config';

import type { Config } from 'tailwindcss';

const config: Pick<Config, 'content' | 'presets' | 'darkMode'> = {
  // 기존 밝은 테마를 유지하고, 에디터가 OS 다크 모드를 자동 적용하지 않게 한다.
  darkMode: 'class',
  content: [
    './src/**/*.{js,ts,jsx,tsx}',
    '../../packages/common/src/**/*.{js,ts,jsx,tsx}',
    '../../packages/ui/src/**/*.{js,ts,jsx,tsx}',
  ],
  presets: [sharedConfig],
};

export default config;
