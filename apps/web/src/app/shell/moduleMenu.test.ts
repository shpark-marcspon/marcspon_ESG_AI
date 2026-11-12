// 모듈 메뉴 한 자리 시험(밴드 DV2a ② H4). 항목 여섯의 id·아이콘·끔·차례가 옛 사본 둘(BASE 926e7f98 의 GreenwashRoutes.tsx:191-227 ·
//   TranslationRoutes.tsx:81-117 — 둘은 같았다)과 같고 「데이터 검증」·「중대성평가」를 켰는지, 글은 받은 그대로인지, 누른 항목의 주소를 본다.
import type { ReactElement } from 'react';

import * as Icons from '@marcspon/common/generated/icons/MyIcons';

import { describe, expect, it } from 'vitest';

import { moduleMenu, moduleTarget } from './moduleMenu.tsx';

/** 옛 사본의 차례·아이콘·끔(validation·materiality 는 옛 사본에서 끔 → 이제 켬) + 끝에 새 항목 drafting(RPW1 ④). */
const COPIES = [
  ['dashboard', Icons.DashboardIcon, true],
  ['ghg', Icons.InventoryIcon, true],
  ['greenwash', Icons.SearchCheckIcon, false],
  ['materiality', Icons.ChartSquareIcon, true],
  ['validation', Icons.FileCheckIcon, true],
  ['translation', Icons.GlobeIcon, false],
  ['drafting', Icons.FileIcon, false],
] as const;
/** 지어낸 글(부르는 쪽 문구 표 자리) — 항목마다 다르게. */
const LABELS = Object.fromEntries(COPIES.map(([id]) => [id, `menu-${id}`]));
const menu = moduleMenu(LABELS as Parameters<typeof moduleMenu>[0]);

describe('moduleMenu', () => {
  it('일곱 항목의 id·아이콘·차례는 옛 사본 + 끝에 drafting · 글은 받은 문구 표 그대로', () => {
    expect(menu.map((item) => item.id)).toEqual(COPIES.map(([id]) => id));
    menu.forEach((item, index) => {
      const icon = item.icon as ReactElement<{ 'aria-hidden'?: boolean }>;
      expect(icon.type, item.id).toBe(COPIES[index]![1]);
      expect(icon.props['aria-hidden'], item.id).toBe(true);
      expect(item.label).toBe(`menu-${item.id}`);
    });
  });

  it('켬 여섯·끔 하나 — 옛 사본에서 「데이터 검증」·「중대성평가」·「온실가스」가 켬으로 바뀜(IRW1 H4·W12-0a H3)', () => {
    const ids = (on: boolean) =>
      menu.filter((item) => !item.disabled === on).map((item) => item.id);
    expect(ids(true)).toEqual([
      'ghg',
      'greenwash',
      'materiality',
      'validation',
      'translation',
      'drafting',
    ]);
    expect(ids(false)).toEqual(['dashboard']);
    const changed = menu.filter(
      (item, index) => Boolean(item.disabled) !== COPIES[index]![2],
    );
    expect(changed.map((i) => i.id)).toEqual([
      'ghg',
      'materiality',
      'validation',
    ]);
  });
});

describe('moduleTarget', () => {
  it('켜진 여섯은 모듈 첫 주소, 그 밖은 null', () => {
    expect(moduleTarget('greenwash')).toBe('/greenwash');
    expect(moduleTarget('translation')).toBe('/translation');
    expect(moduleTarget('validation')).toBe('/dataverify');
    expect(moduleTarget('materiality')).toBe('/materiality');
    expect(moduleTarget('ghg')).toBe('/ghg');
    expect(moduleTarget('drafting')).toBe('/drafting');
    for (const id of ['dashboard', 'zzz', ''])
      expect(moduleTarget(id), id).toBeNull();
  });
});
