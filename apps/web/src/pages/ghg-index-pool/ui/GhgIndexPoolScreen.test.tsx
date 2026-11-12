// @vitest-environment jsdom
// S19 인벤토리 관리 > 온실가스 인덱스(밴드 W12-0b1 ③ — 발주서 §3 8). 진짜 풀 실어댑터 + 가짜 온실가스 서버(api/testing.ts 의 fakePool 씨앗).
//   열 넷(머리·처음 첫 항목·하위 수) · 고르기 · 검색(q — 맞는 노드와 조상, 추가 단추 0) · 추가 셋(POST 본문 · 422 fields.name) · 수정(PATCH) ·
//   삭제 409 HAS_CHILDREN·IN_USE · 404 한 줄 + 다시 읽음 · 첫 화면 판 닫힘(Q7) · 자산/시설 판 새로(POST 정수 id → 그 잎) · 저장 흐림 ·
//   기본 바꿈 PUT defaultFactorId · IN_USE 잎 PUT 글 · 같은 코드 422 글 · 계수 0 경고 · 계수 지우기.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  fakeGhgServer,
  portsOf,
  refusal,
} from '../../../entities/ghg/api/testing.ts';
import type { FakeGhgServerOptions } from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { GhgIndexPoolScreen } from './GhgIndexPoolScreen.tsx';

afterEach(cleanup);
beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

const words = GHG_TEXT.pool;
const P = '/inventory/admin/ghg-index';

function setup(options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer(options);
  const ports = portsOf(server);
  render(
    <GhgIndexPoolScreen
      port={ports.pool}
      codes={ports.admin}
      thisYear={2026}
    />,
  );
  return { server };
}

const column = (level: string) =>
  document.querySelector<HTMLElement>(`section[data-column="${level}"]`)!;
/** 그 열의 항목 이름(차례대로). */
const namesIn = (level: string) =>
  [...column(level).querySelectorAll('li[data-node-id]')].map(
    (li) => li.querySelector('span')!.textContent,
  );
const chosenIn = (level: string) =>
  column(level).querySelector('[aria-current="true"]')?.textContent ?? null;
/** 그 열에서 이름이 같은 항목의 고르기 단추(작은 메뉴 단추 말고). */
const item = (level: string, name: string) => {
  const li = [...column(level).querySelectorAll('li[data-node-id]')].find(
    (one) => one.querySelector('span')!.textContent === name,
  );
  if (!li) throw new Error(`${level} 열에 ${name} 없음`);
  return li.querySelector('button')!;
};
const ready = () =>
  waitFor(() =>
    expect(namesIn('facility')).toEqual(['지어낸 보일러', '지어낸 발전기']),
  );
const notice = () => screen.getByTestId('pool-notice');
const panel = () => screen.getByTestId('facility-panel');
const actions = () => screen.getByTestId('facility-actions');
const panelSave = () =>
  within(actions()).getByRole('button', {
    name: words.save,
  }) as HTMLButtonElement;
const factorsBox = () =>
  within(panel()).getByRole('region', { name: words.factors });
const line = () => screen.getByTestId('facility-line');

async function openMenu(level: string, name: string, action: string) {
  fireEvent.click(
    within(column(level)).getByRole('button', { name: words.menuLabel(name) }),
  );
  fireEvent.click(
    within(
      within(column(level)).getByRole('group', { name: words.menuLabel(name) }),
    ).getByRole('button', { name: action }),
  );
}
async function nameDialog(name: string) {
  const dialog = await screen.findByTestId('name-dialog');
  fireEvent.change(within(dialog).getByRole('textbox'), {
    target: { value: name },
  });
  fireEvent.click(within(dialog).getByRole('button', { name: words.save }));
  return dialog;
}
async function confirmDelete() {
  const dialog = await screen.findByTestId('pool-delete-dialog');
  expect(dialog.textContent).toContain(words.deleteConfirm);
  fireEvent.click(
    within(dialog).getByRole('button', { name: words.confirmDelete }),
  );
}
async function openLeaf(name: string) {
  await ready();
  fireEvent.click(item('facility', name));
  await waitFor(() =>
    expect(panel().querySelector('h2')!.textContent).toBe(name),
  );
}

describe('S19 온실가스 인덱스 — 4열', () => {
  it('제목 · 머리 넷 · 처음은 왼쪽부터 첫 항목(배출활동까지) · 하위 수 · 열 끝 추가 넷 · 판은 닫힘(Q7)', async () => {
    setup();
    await ready();
    expect(screen.queryByRole('heading', { name: words.title })).toBeNull();
    expect(
      document.querySelector('[data-screen="admin-ghg-index"]'),
    ).not.toBeNull();
    expect(
      [...document.querySelectorAll('section[data-column] h3')].map(
        (h) => h.textContent,
      ),
    ).toEqual(['배출범위', '배출원 유형', '배출활동', '자산/시설명']);
    expect(namesIn('scope')).toEqual(['지어낸 직접배출', '지어낸 간접배출']);
    expect(namesIn('source_type')).toEqual([
      '지어낸 고정연소',
      '지어낸 이동연소',
    ]);
    expect(namesIn('activity')).toEqual(['지어낸 액체연료']);
    expect(chosenIn('scope')).toContain('지어낸 직접배출');
    expect(chosenIn('source_type')).toContain('지어낸 고정연소');
    expect(chosenIn('activity')).toContain('지어낸 액체연료');
    expect(chosenIn('facility')).toBeNull();
    expect(item('scope', '지어낸 직접배출').textContent).toContain(
      words.childCount(2),
    );
    expect(item('activity', '지어낸 액체연료').textContent).toContain(
      words.childCount(2),
    );
    for (const level of [
      'scope',
      'source_type',
      'activity',
      'facility',
    ] as const)
      expect(
        within(column(level)).getByRole('button', { name: words.add[level] }),
      ).not.toBeNull();
    expect(screen.queryByTestId('facility-panel')).toBeNull();
    // 자산/시설 열에는 작은 메뉴가 없다(잎은 판에서 지운다).
    expect(
      within(column('facility')).queryByRole('button', {
        name: words.menuLabel('지어낸 보일러'),
      }),
    ).toBeNull();
  });

  it('고르면 오른쪽 열이 그 자식 — 이동연소 → 도로수송 → 사업장 차량 · 자식 없는 범위면 아래 열 빔', async () => {
    const { server } = setup();
    await ready();
    fireEvent.click(item('source_type', '지어낸 이동연소'));
    await waitFor(() =>
      expect(namesIn('facility')).toEqual(['지어낸 사업장 차량']),
    );
    expect(namesIn('activity')).toEqual(['지어낸 도로수송']);
    expect(server.calls.map((c) => Object.fromEntries(c.query))).toContainEqual(
      { parentId: '4' },
    );
    fireEvent.click(item('scope', '지어낸 간접배출'));
    await waitFor(() =>
      expect(within(column('source_type')).getByText(words.emptyColumn)),
    );
    expect(namesIn('activity')).toEqual([]);
    // 활동 열은 부모가 없으니 추가 단추도 없다.
    expect(
      within(column('activity')).queryByRole('button', {
        name: words.add.activity,
      }),
    ).toBeNull();
  });

  it('검색: 멈춘 뒤 q 하나 — 맞는 노드와 조상만 · 추가 단추 0 · 비우면 열 읽기로', async () => {
    const { server } = setup();
    await ready();
    fireEvent.change(screen.getByLabelText(words.searchLabel), {
      target: { value: '도로' },
    });
    await waitFor(() =>
      expect(namesIn('activity')).toEqual(['지어낸 도로수송']),
    );
    const queries = server.calls
      .filter((c) => `${c.method} ${c.path}` === `GET ${P}/nodes`)
      .map((c) => Object.fromEntries(c.query));
    expect(queries.filter((q) => 'q' in q)).toEqual([{ q: '도로' }]);
    expect(namesIn('scope')).toEqual(['지어낸 직접배출']);
    expect(namesIn('source_type')).toEqual(['지어낸 이동연소']);
    expect(namesIn('facility')).toEqual([]);
    expect(screen.queryByRole('button', { name: words.add.scope })).toBeNull();
    fireEvent.change(screen.getByLabelText(words.searchLabel), {
      target: { value: '없는 이름' },
    });
    await screen.findByTestId('pool-empty-search');
    fireEvent.change(screen.getByLabelText(words.searchLabel), {
      target: { value: '' },
    });
    await waitFor(() =>
      expect(namesIn('scope')).toEqual(['지어낸 직접배출', '지어낸 간접배출']),
    );
  });
});

describe('S19 열 1~3 추가·수정·삭제', () => {
  it('추가 셋: 범위 {level, name} · 유형·활동 {level, parentId 정수, name} → 새 항목이 그 열에 · 하위 수 늘어남', async () => {
    const { server } = setup();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: words.add.scope }));
    await nameDialog('지어낸 기타배출');
    await waitFor(() => expect(namesIn('scope')).toContain('지어낸 기타배출'));
    fireEvent.click(
      screen.getByRole('button', { name: words.add.source_type }),
    );
    await nameDialog('지어낸 공정배출');
    await waitFor(() =>
      expect(namesIn('source_type')).toContain('지어낸 공정배출'),
    );
    fireEvent.click(screen.getByRole('button', { name: words.add.activity }));
    await nameDialog('지어낸 기체연료');
    await waitFor(() =>
      expect(namesIn('activity')).toContain('지어낸 기체연료'),
    );
    expect(server.bodies(`POST ${P}/nodes`)).toEqual([
      { level: 'scope', name: '지어낸 기타배출' },
      { level: 'source_type', parentId: 1, name: '지어낸 공정배출' },
      { level: 'activity', parentId: 3, name: '지어낸 기체연료' },
    ]);
    await waitFor(() =>
      expect(item('scope', '지어낸 직접배출').textContent).toContain(
        words.childCount(3),
      ),
    );
  });

  it('글자 모달: 빈 이름 → 「필수 입력 항목이에요」 요청 0 · 422 fields.name → 「같은 이름이 이미 있어요」(모달 그대로)', async () => {
    const { server } = setup();
    await ready();
    fireEvent.click(
      screen.getByRole('button', { name: words.add.source_type }),
    );
    const dialog = await nameDialog('   ');
    expect(within(dialog).getByText(words.required)).not.toBeNull();
    expect(server.count(`POST ${P}/nodes`)).toBe(0);
    await nameDialog('지어낸 고정연소');
    await waitFor(() =>
      expect(within(dialog).getByText(words.nameTaken)).not.toBeNull(),
    );
    expect(server.count(`POST ${P}/nodes`)).toBe(1);
    expect(screen.getByTestId('name-dialog')).not.toBeNull();
  });

  it('수정: 작은 메뉴 「수정」 → 이름이 채워진 모달 → PATCH 경로 정수 {name}', async () => {
    const { server } = setup();
    await ready();
    await openMenu('activity', '지어낸 액체연료', words.edit);
    const dialog = await screen.findByTestId('name-dialog');
    expect(
      (within(dialog).getByRole('textbox') as HTMLInputElement).value,
    ).toBe('지어낸 액체연료');
    await nameDialog('지어낸 액체연료 고침');
    await waitFor(() =>
      expect(namesIn('activity')).toEqual(['지어낸 액체연료 고침']),
    );
    expect(server.bodies(`PATCH ${P}/nodes/5`)).toEqual([
      { name: '지어낸 액체연료 고침' },
    ]);
  });

  it('삭제: 자식 있음 409 HAS_CHILDREN · 쓰이는 노드 409 IN_USE · 지움 → 열에서 빠짐 · {ids 정수}', async () => {
    const { server } = setup();
    await ready();
    await openMenu('scope', '지어낸 직접배출', words.remove);
    await confirmDelete();
    await waitFor(() => expect(notice().textContent).toBe(words.hasChildren));
    expect(namesIn('scope')).toContain('지어낸 직접배출');

    server.poolInUse.nodes.add('2');
    await openMenu('scope', '지어낸 간접배출', words.remove);
    await confirmDelete();
    await waitFor(() => expect(notice().textContent).toBe(words.inUseDelete));

    server.poolInUse.nodes.clear();
    await openMenu('scope', '지어낸 간접배출', words.remove);
    await confirmDelete();
    await waitFor(() => expect(namesIn('scope')).toEqual(['지어낸 직접배출']));
    expect(notice().textContent).toBe('');
    expect(server.bodies(`POST ${P}/nodes/delete`)).toEqual([
      { ids: [1] },
      { ids: [2] },
      { ids: [2] },
    ]);
  });

  it('삭제 404: 「이미 삭제된 항목이에요…」 한 줄 + 다시 읽음 · 글 갈래는 서버 message 를 쓰지 않음', async () => {
    const { server } = setup();
    await ready();
    server.override[`POST ${P}/nodes/delete`] = () => refusal(404, 'NOT_FOUND');
    const before = server.count(`GET ${P}/nodes`);
    await openMenu('activity', '지어낸 액체연료', words.remove);
    await confirmDelete();
    await waitFor(() => expect(notice().textContent).toBe(words.notFound));
    expect(server.count(`GET ${P}/nodes`)).toBeGreaterThan(before);
    expect(document.body.textContent).not.toContain('지어낸-');
  });
});

describe('S19 자산/시설 판', () => {
  it('새로: 열 끝 추가 → 빈 판([저장] 늘 켬 · 빈 칸 필수 글 요청 0) → POST {parentId 정수, facilityCodeId 정수, unit, tooltip} → 그 잎 고름', async () => {
    const { server } = setup();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: words.add.facility }));
    await waitFor(() =>
      expect(panel().querySelector('h2')!.textContent).toBe(
        words.facilityTitleNew,
      ),
    );
    expect(panelSave().disabled).toBe(false);
    fireEvent.click(panelSave());
    expect(within(panel()).getByText(words.required)).not.toBeNull();
    expect(document.activeElement?.id).toBe('ghg-leaf-code');
    expect(server.count(`POST ${P}/facilities`)).toBe(0);
    // 코드 드롭다운 = 이름만(코드 글자 0).
    const code = within(panel()).getByRole('combobox', {
      name: words.facilityCode,
    });
    expect(code.textContent).not.toContain('F000');
    fireEvent.change(code, { target: { value: '3' } });
    fireEvent.change(
      within(panel()).getByRole('combobox', { name: words.unit }),
      { target: { value: 'mass|t' } },
    );
    fireEvent.click(panelSave());
    await waitFor(() =>
      expect(namesIn('facility')).toContain('지어낸 사업장 차량'),
    );
    expect(server.bodies(`POST ${P}/facilities`)).toEqual([
      {
        parentId: 5,
        facilityCodeId: 3,
        unit: { kind: 'mass', unit: 't' },
        tooltip: '',
      },
    ]);
    await waitFor(() =>
      expect(chosenIn('facility')).toBe('지어낸 사업장 차량'),
    );
    await waitFor(() =>
      expect(panel().querySelector('h2')!.textContent).toBe(
        '지어낸 사업장 차량',
      ),
    );
  });

  it('잎 고름 → 판: 고친 것이 없으면 [저장] 흐림 · 툴팁 고침 → 켬 · [취소] → 흐림 · 저장 → PUT · 「저장됐어요」', async () => {
    const { server } = setup();
    await openLeaf('지어낸 보일러');
    expect(panelSave().disabled).toBe(true);
    const tooltip = within(panel()).getByRole('textbox', {
      name: words.tooltip,
    });
    fireEvent.change(tooltip, { target: { value: '지어낸 새 툴팁' } });
    expect(panelSave().disabled).toBe(false);
    fireEvent.click(
      within(actions()).getByRole('button', { name: words.cancel }),
    );
    expect(panelSave().disabled).toBe(true);
    fireEvent.change(tooltip, { target: { value: '지어낸 새 툴팁' } });
    fireEvent.click(panelSave());
    await waitFor(() =>
      expect(screen.getByTestId('toast').textContent).toBe(words.saved),
    );
    expect(server.bodies(`PUT ${P}/facilities/20`)).toEqual([
      {
        facilityCodeId: 1,
        unit: { kind: 'volume', unit: 'kL' },
        tooltip: '지어낸 새 툴팁',
      },
    ]);
    expect(panelSave().disabled).toBe(true);
  });

  it('기본 배출계수 토글만 바꿔도 저장 켜짐 → PUT 에 defaultFactorId 정수', async () => {
    const { server } = setup();
    await openLeaf('지어낸 보일러');
    const toggle = within(panel()).getByRole('switch', {
      name: words.defaultToggle('지어낸 등유 계수'),
    });
    expect(toggle.getAttribute('aria-checked')).toBe('false');
    fireEvent.click(toggle);
    expect(panelSave().disabled).toBe(false);
    fireEvent.click(panelSave());
    await waitFor(() =>
      expect(server.bodies(`PUT ${P}/facilities/20`)).toEqual([
        {
          facilityCodeId: 1,
          unit: { kind: 'volume', unit: 'kL' },
          tooltip: '지어낸 툴팁',
          defaultFactorId: 23,
        },
      ]),
    );
    await waitFor(() =>
      expect(
        within(panel())
          .getByRole('switch', {
            name: words.defaultToggle('지어낸 등유 계수'),
          })
          .getAttribute('aria-checked'),
      ).toBe('true'),
    );
  });

  it('쓰이는 잎: 단위 바꿈 → 409 IN_USE → 잎 PUT 글(지우기 글 아님) · 툴팁만이면 지남', async () => {
    const { server } = setup();
    server.poolInUse.nodes.add('20');
    await openLeaf('지어낸 보일러');
    fireEvent.change(
      within(panel()).getByRole('combobox', { name: words.unit }),
      { target: { value: 'volume|L' } },
    );
    fireEvent.click(panelSave());
    await waitFor(() => expect(line().textContent).toBe(words.inUseSave));
    expect(line().textContent).not.toBe(words.inUseDelete);
    fireEvent.click(
      within(actions()).getByRole('button', { name: words.cancel }),
    );
    fireEvent.change(
      within(panel()).getByRole('textbox', { name: words.tooltip }),
      { target: { value: '지어낸 툴팁만' } },
    );
    fireEvent.click(panelSave());
    await waitFor(() =>
      expect(screen.getByTestId('toast').textContent).toBe(words.saved),
    );
  });

  it('같은 활동에 같은 코드 → 422 fields.facilityCodeId → 「이 배출활동에 같은 자산/시설이 이미 있어요」', async () => {
    setup();
    await openLeaf('지어낸 발전기');
    fireEvent.change(
      within(panel()).getByRole('combobox', { name: words.facilityCode }),
      { target: { value: '1' } },
    );
    fireEvent.click(panelSave());
    await waitFor(() => expect(line().textContent).toBe(words.codeTaken));
  });

  it('계수 0 잎: 빈 상태 「등록된 배출계수가 없어요」 + 판 위 경고(스펙 글)', async () => {
    setup();
    await ready();
    fireEvent.click(item('source_type', '지어낸 이동연소'));
    await waitFor(() =>
      expect(namesIn('facility')).toEqual(['지어낸 사업장 차량']),
    );
    fireEvent.click(item('facility', '지어낸 사업장 차량'));
    await waitFor(() =>
      expect(screen.getByTestId('no-default').textContent).toBe(
        words.noDefault,
      ),
    );
    expect(within(panel()).getByText(words.noFactors)).not.toBeNull();
    expect(
      within(factorsBox())
        .getByRole('button', { name: words.removeFactors })
        .getAttribute('aria-disabled'),
    ).toBe('true');
  });

  it('계수 지우기: 체크 → 확인 창 → {ids 정수} → 표에서 빠지고 남은 첫 행이 기본 · 쓰이는 계수 409 IN_USE 글', async () => {
    const { server } = setup();
    server.poolInUse.factors.add('23');
    await openLeaf('지어낸 보일러');
    const pick = (name: string) =>
      fireEvent.click(
        within(panel()).getByRole('checkbox', {
          name: words.selectFactor(name),
        }),
      );
    pick('지어낸 등유 계수');
    fireEvent.click(
      within(factorsBox()).getByRole('button', { name: words.removeFactors }),
    );
    const confirm = async () => {
      const dialog = await screen.findByTestId('facility-delete-dialog');
      expect(dialog.textContent).toContain(words.deleteFactorsConfirm);
      fireEvent.click(
        within(dialog).getByRole('button', { name: words.confirmDelete }),
      );
    };
    await confirm();
    await waitFor(() => expect(line().textContent).toBe(words.inUseDelete));
    pick('지어낸 경유 계수');
    fireEvent.click(
      within(factorsBox()).getByRole('button', { name: words.removeFactors }),
    );
    await confirm();
    await waitFor(() =>
      expect(panel().querySelectorAll('tr[data-factor-id]')).toHaveLength(1),
    );
    expect(
      within(panel())
        .getByRole('switch', { name: words.defaultToggle('지어낸 등유 계수') })
        .getAttribute('aria-checked'),
    ).toBe('true');
    expect(server.bodies('POST /inventory/admin/ghg-factors/delete')).toEqual([
      { ids: [23] },
      { ids: [21] },
    ]);
  });

  it('GX2 D3·D1·D5·D4·S12-07: 계수 행 이름 칸 누름 → S20 읽기 꼴(몸 100vh−240 · 필수 점 0) · 체크 누름은 안 엶 · ⋮ 아이콘 · 라벨 한 줄', async () => {
    setup();
    await openLeaf('지어낸 보일러');
    // S12-07: 판 라벨 칸 200 · 줄바꿈 0.
    const codeLabel = within(panel())
      .getByText(words.facilityCode)
      .closest('label')!;
    expect(codeLabel.className).toContain('w-[200px]');
    expect(codeLabel.className).toContain('whitespace-nowrap');
    expect(codeLabel.className).not.toContain('w-40');
    const firstRow = panel().querySelector('tr[data-factor-id]')!;
    // 체크 상자 누름은 제 일(행 열기로 번지지 않음).
    fireEvent.click(within(firstRow as HTMLElement).getByRole('checkbox'));
    expect(screen.queryByTestId('factor-dialog')).toBeNull();
    fireEvent.click(firstRow.querySelectorAll('td')[1]!);
    const dialog = await screen.findByTestId('factor-dialog');
    await waitFor(() => expect(dialog.getAttribute('data-mode')).toBe('view'));
    await waitFor(() =>
      expect(within(dialog).getByTestId('factor-body')).toBeTruthy(),
    );
    expect(within(dialog).getByTestId('factor-body').className).toContain(
      'max-h-[calc(100vh-240px)]',
    );
    expect(dialog.querySelectorAll('[data-required-mark]')).toHaveLength(0);
    fireEvent.click(
      within(dialog).getByRole('button', { name: GHG_TEXT.factor.edit }),
    );
    expect(
      dialog.querySelectorAll('[data-required-mark]').length,
    ).toBeGreaterThan(0);
    // D4: 열 1~3 메뉴는 ⋮(DotsThreeVertical — 점 셋 세로).
    const menus = [
      ...column('scope').querySelectorAll('button[aria-expanded]'),
    ];
    expect(menus.length).toBeGreaterThan(0);
    for (const menu of menus) {
      const icon = menu.querySelector('svg')!;
      expect(icon.getAttribute('data-icon')).toBe('dots-vertical');
      expect(icon.querySelectorAll('path')).toHaveLength(3);
    }
  });

  it('S20 계수 저장 뒤: 모달 닫힘 · 토스트 「저장됐어요」(S12-04) · 표에 새 행(다시 읽음)', async () => {
    const { server } = setup();
    await openLeaf('지어낸 보일러');
    expect(screen.queryByTestId('toast')).toBeNull(); // S12-04: 판 글 대신 토스트
    fireEvent.click(
      within(factorsBox()).getByRole('button', { name: words.addFactor }),
    );
    const dialog = await screen.findByTestId('factor-dialog');
    const f = GHG_TEXT.factor;
    const pick = (name: string, value: string) =>
      fireEvent.change(within(dialog).getByRole('combobox', { name }), {
        target: { value },
      });
    fireEvent.change(within(dialog).getByLabelText(f.name), {
      target: { value: '지어낸 새 계수' },
    });
    fireEvent.change(within(dialog).getByLabelText(f.source), {
      target: { value: '지어낸 출처' },
    });
    pick(f.baseYear, '2024');
    pick(f.tier, '1');
    pick(f.country, 'KR');
    pick(f.industry, 'other');
    pick(`${f.inputUnit} ${f.unitKind}`, 'volume');
    pick(`${f.inputUnit} ${f.unitName}`, 'kL');
    fireEvent.click(
      within(dialog).getByRole('switch', { name: f.gasToggle('CO2') }),
    );
    fireEvent.change(
      within(dialog).getByRole('textbox', { name: f.gasFactor('CO2') }),
      {
        target: { value: '2.5' },
      },
    );
    fireEvent.change(
      within(dialog).getByRole('textbox', { name: f.gasGwp('CO2') }),
      {
        target: { value: '1' },
      },
    );
    fireEvent.click(within(dialog).getByRole('button', { name: f.save }));
    await waitFor(() =>
      expect(screen.queryByTestId('factor-dialog')).toBeNull(),
    );
    expect(screen.getByTestId('toast').textContent).toBe(words.saved);
    await waitFor(() =>
      expect(panel().querySelectorAll('tr[data-factor-id]')).toHaveLength(3),
    );
    expect(
      server.count('POST /inventory/admin/ghg-index/facilities/20/factors'),
    ).toBe(1);
  });

  it('잎 지우기: 판 머리 「삭제」 → 확인 창 → nodes/delete {ids 정수} → 판 닫히고 열에서 빠짐', async () => {
    const { server } = setup();
    await openLeaf('지어낸 발전기');
    fireEvent.click(
      within(actions()).getByRole('button', { name: words.removeFacility }),
    );
    const dialog = await screen.findByTestId('facility-delete-dialog');
    expect(dialog.textContent).toContain(words.deleteFacilityConfirm);
    fireEvent.click(
      within(dialog).getByRole('button', { name: words.confirmDelete }),
    );
    await waitFor(() => expect(namesIn('facility')).toEqual(['지어낸 보일러']));
    expect(screen.queryByTestId('facility-panel')).toBeNull();
    expect(server.bodies(`POST ${P}/nodes/delete`)).toEqual([{ ids: [22] }]);
  });
});

// 밴드 RC1(sid:MARC-ENT-599): 계수 줄 전체·Tab+Enter·Space → S20 읽기 꼴 · 체크·기본 토글·› 는 줄 클릭 안 일으킴 · 닫으면 초점이 연 자리.
describe('S19 계수 줄 클릭(밴드 RC1)', () => {
  const rows = () => [
    ...panel().querySelectorAll<HTMLElement>('tr[data-factor-id]'),
  ];
  const dialogs = () => screen.queryAllByTestId('factor-dialog');
  const closeDialog = async () => {
    const dialog = await screen.findByTestId('factor-dialog');
    await waitFor(() => expect(dialog.getAttribute('data-mode')).toBe('view'));
    fireEvent.click(
      within(dialog).getByRole('button', { name: GHG_TEXT.factor.close }),
    );
    await waitFor(() => expect(dialogs()).toHaveLength(0));
  };

  it('줄에 초점 → Enter · Space 로 읽기 꼴 · 닫으면 초점이 그 줄 · 이름 칸 클릭도 닫으면 그 줄', async () => {
    setup();
    await openLeaf('지어낸 보일러');
    const row = rows()[0]!;
    for (const key of ['Enter', ' ']) {
      row.focus();
      fireEvent.keyDown(row, { key });
      await closeDialog();
      await waitFor(() => expect(document.activeElement).toBe(row));
    }
    fireEvent.click(row.querySelectorAll('td')[1]!);
    await closeDialog();
    await waitFor(() => expect(document.activeElement).toBe(row));
  });

  it('› 로 열면 닫을 때 초점은 › 그대로', async () => {
    setup();
    await openLeaf('지어낸 보일러');
    const row = rows()[0]!;
    const name = row.querySelectorAll('td')[1]!.textContent!;
    const open = within(row).getByRole('button', {
      name: words.openFactor(name),
    });
    open.focus();
    fireEvent.click(open);
    expect(dialogs()).toHaveLength(1);
    await closeDialog();
    await waitFor(() => expect(document.activeElement).toBe(open));
  });

  it('체크박스·기본 토글은 줄 클릭 안 일으킴 · 체크·› 에 초점이 있을 때 Enter·Space 도 줄 열기 아님', async () => {
    setup();
    await openLeaf('지어낸 보일러');
    const row = rows()[1] ?? rows()[0]!;
    const box = within(row).getByRole('checkbox');
    fireEvent.click(box);
    fireEvent.click(within(row).getByRole('switch'));
    expect(dialogs()).toHaveLength(0);
    box.focus();
    for (const key of ['Enter', ' ']) fireEvent.keyDown(box, { key });
    expect(dialogs()).toHaveLength(0);
    const open = row.querySelector<HTMLElement>('[data-factor-open]')!;
    open.focus();
    fireEvent.keyDown(open, { key: 'Enter' });
    expect(dialogs()).toHaveLength(0);
  });

  it('누를 수 있는 줄의 꼴: tabindex 0 · 이름 = 배출계수명 · DataTable 클래스', async () => {
    setup();
    await openLeaf('지어낸 보일러');
    const row = rows()[0]!;
    expect(row.getAttribute('tabindex')).toBe('0');
    expect(row.getAttribute('aria-label')).toBe(
      row.querySelectorAll('td')[1]!.textContent,
    );
    for (const name of [
      'cursor-pointer',
      'hover:bg-background-secondary',
      'focus-visible:outline-border-secondary',
    ])
      expect(row.classList.contains(name), name).toBe(true);
  });

  it('「계수 없음」 줄은 누를 수 없음(tabindex·커서·hover 0)', async () => {
    setup();
    await ready();
    fireEvent.click(item('source_type', '지어낸 이동연소'));
    await waitFor(() =>
      expect(namesIn('facility')).toEqual(['지어낸 사업장 차량']),
    );
    fireEvent.click(item('facility', '지어낸 사업장 차량'));
    const empty = await within(panel()).findByText(words.noFactors);
    const tr = empty.closest('tr')!;
    expect(tr.getAttribute('tabindex')).toBeNull();
    expect(tr.className).not.toContain('cursor-pointer');
    expect(tr.className).not.toContain('hover:bg-');
  });
});
