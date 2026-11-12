// 시각 비교의 기준 그림 자리(밴드 VS1 — 결정 sid:MARC-ENT-326). 기준 그림은 git 밖 이 맥 한 자리: main 체크아웃의 형제 폴더
// `esg-app.visual-baseline/`. 어느 워크트리에서 돌려도 같은 곳이 나오게 공용 .git(git-common-dir)에서 센다(워크트리 상대 경로 0).
//   - VISUAL_BASELINE_DIR: 임시 기준 자리(심은 파손·잡음 실측 전용). 절대 경로만 받는다.
//   - 폴더를 만들지 않는다. 만드는 것은 갱신 스크립트(apps/web/scripts/visual-update.sh) 하나다.
//   - 갱신 자물쇠(guardBaselineUpdate): -u·--update-snapshots 로 도는데 임시 자리도, 갱신 스크립트의 표지(VISUAL_UPDATE_MAIN=1)도 없으면
//     설정 단계에서 멈춘다 — 밴드 워크트리가 공용 폴더의 진짜 기준을 쓰는 길을 막는다.
// playwright.config.ts 가 이 파일을 읽는다(설정과 일꾼 프로세스 둘 다). 시각 스펙(visual.spec.ts)도 같은 셈을 쓴다.
import { execFileSync } from 'node:child_process';
import { basename, dirname, isAbsolute, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** 기준 그림 폴더(절대 경로). */
export function baselineDir(): string {
  const override = process.env.VISUAL_BASELINE_DIR;
  if (override !== undefined && override !== '') {
    if (!isAbsolute(override))
      throw new Error(`VISUAL_BASELINE_DIR 는 절대 경로만 받는다: ${override}`);
    return override;
  }
  const common = execFileSync(
    'git',
    ['rev-parse', '--path-format=absolute', '--git-common-dir'],
    { cwd: fileURLToPath(new URL('.', import.meta.url)), encoding: 'utf8' },
  ).trim();
  // …/esg-app/.git → …/esg-app(main 체크아웃) → 그 형제 …/esg-app.visual-baseline
  const main = dirname(common);
  return join(dirname(main), `${basename(main)}.visual-baseline`);
}

/** 이번 실행이 기준을 쓰려 하는가(-u · --update-snapshots · --update-snapshots=…). */
export const updatingSnapshots = (argv: readonly string[] = process.argv) =>
  argv.some(
    (arg) =>
      arg === '-u' ||
      arg === '--update-snapshots' ||
      arg.startsWith('--update-snapshots='),
  );

/** 기준 갱신 자물쇠. 갱신은 main 에서 갱신 스크립트로만(임시 자리는 예외). */
export function guardBaselineUpdate(argv: readonly string[] = process.argv) {
  if (!updatingSnapshots(argv)) return;
  if (process.env.VISUAL_BASELINE_DIR) return;
  if (process.env.VISUAL_UPDATE_MAIN === '1') return;
  throw new Error(
    '기준 갱신은 main 에서 apps/web/scripts/visual-update.sh 로만(임시 자리는 VISUAL_BASELINE_DIR=<절대 경로>)',
  );
}
