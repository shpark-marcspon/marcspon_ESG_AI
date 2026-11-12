// 모듈 틀 다섯(그린워싱·영문번역·데이터 검증·중대성평가·온실가스)의 셸 메뉴 한 자리(밴드 DV2a ② H4 — 플랫폼-웹 78 허락 10-23).
//   옛 GreenwashRoutes.tsx·TranslationRoutes.tsx 의 MENU 사본 둘을 걷고 여기로 올렸다. *Routes.tsx 에 MENU 사본을 다시 두지 않는다.
//   글은 부르는 쪽의 문구 표(X_TEXT.shell.menu)를 받는다 — 문구는 옮기지 않는다. shared 만 가져온다(app/guards/layers.test.ts).
import {
  ChartSquareIcon,
  DashboardIcon,
  FileCheckIcon,
  FileIcon,
  GlobeIcon,
  InventoryIcon,
  SearchCheckIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import type { AppShellMenuItem } from '../../shared/ui/app-shell/index.ts';

/** 항목 일곱(메뉴 차례): id · 키트 아이콘 · 끔. 옛 사본 그대로이고 validation·materiality·ghg 를 켰고 끝에 drafting 을 더했다(그 밖 끔은 아직 없는 모듈). */
const ITEMS = [
  ['dashboard', DashboardIcon, true],
  ['ghg', InventoryIcon, false],
  ['greenwash', SearchCheckIcon, false],
  ['materiality', ChartSquareIcon, false],
  ['validation', FileCheckIcon, false],
  ['translation', GlobeIcon, false],
  ['drafting', FileIcon, false],
] as const;

export type ModuleMenuId = (typeof ITEMS)[number][0];
/** 부르는 쪽 문구 표의 메뉴 글(GW_TEXT·TR_TEXT·DV_TEXT 의 shell.menu). */
export type ModuleMenuLabels = Readonly<Record<ModuleMenuId, string>>;

export const moduleMenu = (
  labels: ModuleMenuLabels,
): readonly AppShellMenuItem[] =>
  ITEMS.map(([id, Icon, disabled]) => ({
    id,
    label: labels[id],
    icon: <Icon aria-hidden />,
    disabled,
  }));

/** 메뉴 항목을 눌렀을 때 갈 모듈 첫 주소. 켜지지 않은 항목은 null(가지 않는다). */
export function moduleTarget(
  id: string,
):
  | '/greenwash'
  | '/translation'
  | '/dataverify'
  | '/materiality'
  | '/ghg'
  | '/drafting'
  | null {
  if (id === 'greenwash') return '/greenwash';
  if (id === 'translation') return '/translation';
  if (id === 'validation') return '/dataverify';
  if (id === 'materiality') return '/materiality';
  if (id === 'ghg') return '/ghg';
  if (id === 'drafting') return '/drafting';
  return null;
}
